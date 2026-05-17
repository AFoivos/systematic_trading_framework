from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.evaluation.model_metrics import (
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
)
from src.models.common.runtime import infer_feature_columns, resolve_runtime_for_model
from src.models.rl.envs import (
    PortfolioTradingEnv,
    RLExecutionConfig,
    RLRewardConfig,
    SingleAssetTradingEnv,
)
from src.models.rl.sb3 import make_vec_env, train_sb3_model
from src.portfolio import PortfolioConstraints


_FORBIDDEN_RL_FEATURE_PREFIXES = ("signal_", "pred_", "target_", "action_")
_DEFAULT_SINGLE_ASSET_GRID = (-1.0, 0.0, 1.0)


@dataclass(frozen=True)
class _SingleAssetBundle:
    index: pd.Index
    features: np.ndarray
    simple_returns: np.ndarray
    feature_cols: list[str]


@dataclass(frozen=True)
class _PortfolioBundle:
    index: pd.Index
    features: np.ndarray
    simple_returns: np.ndarray
    feature_cols: list[str]
    asset_names: tuple[str, ...]


def _validate_rl_feature_columns(df: pd.DataFrame, *, feature_cols: Sequence[str]) -> dict[str, int]:
    if not feature_cols:
        raise ValueError("RL feature contract violated: feature_cols cannot be empty.")
    missing = [col for col in feature_cols if col not in df.columns]
    if missing:
        raise KeyError(f"RL feature contract violated: missing feature columns: {missing}")
    bad = [col for col in feature_cols if col.startswith(_FORBIDDEN_RL_FEATURE_PREFIXES)]
    if bad:
        raise ValueError(f"RL feature contract violated: forbidden feature columns detected: {sorted(set(bad))}")
    non_numeric = [col for col in feature_cols if not pd.api.types.is_numeric_dtype(df[col])]
    if non_numeric:
        raise ValueError(f"RL feature contract violated: non-numeric feature columns: {non_numeric}")
    all_nan = [col for col in feature_cols if df[col].dropna().empty]
    if all_nan:
        raise ValueError(f"RL feature contract violated: all-NaN feature columns: {all_nan}")
    return {"n_features": int(len(feature_cols))}


def _coerce_positive_int(value: Any, *, name: str, default: int) -> int:
    out = int(default if value is None else value)
    if out <= 0:
        raise ValueError(f"{name} must be > 0.")
    return out


def _resolve_max_signal_abs(env_cfg: Mapping[str, Any]) -> float:
    if "max_signal_abs" in env_cfg and "max_position" in env_cfg:
        left = float(env_cfg["max_signal_abs"])
        right = float(env_cfg["max_position"])
        if not np.isclose(left, right):
            raise ValueError("model.env.max_signal_abs and model.env.max_position must match when both are set.")
    max_signal_abs = float(env_cfg.get("max_signal_abs", env_cfg.get("max_position", 1.0)))
    if max_signal_abs <= 0:
        raise ValueError("model.env.max_signal_abs must be > 0.")
    return max_signal_abs


def _validate_execution_lag(env_cfg: Mapping[str, Any]) -> None:
    execution_lag_bars = _coerce_positive_int(
        env_cfg.get("execution_lag_bars", 1),
        name="model.env.execution_lag_bars",
        default=1,
    )
    if execution_lag_bars != 1:
        raise ValueError("RL currently supports only model.env.execution_lag_bars=1.")


def _returns_to_simple(series: pd.Series, *, returns_type: str) -> pd.Series:
    returns = series.astype(float)
    if returns_type == "log":
        return pd.Series(np.expm1(returns.to_numpy(dtype=float)), index=series.index, dtype=float)
    if returns_type == "simple":
        return returns
    raise ValueError("returns_type must be 'simple' or 'log'.")


def _fit_feature_scaler(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.nanmean(values, axis=0).astype(np.float32, copy=False)
    std = np.nanstd(values, axis=0).astype(np.float32, copy=False)
    std = np.where(~np.isfinite(std) | (std < 1e-8), 1.0, std).astype(np.float32, copy=False)
    mean = np.where(np.isfinite(mean), mean, 0.0).astype(np.float32, copy=False)
    return mean, std


def _scale_values(values: np.ndarray, *, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    out = (values.astype(np.float32, copy=False) - mean) / std
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32, copy=False)


def _contiguous_segments(indices: Sequence[int]) -> list[np.ndarray]:
    arr = np.asarray(indices, dtype=int)
    if arr.size == 0:
        return []
    out: list[np.ndarray] = []
    start = 0
    for i in range(1, len(arr)):
        if int(arr[i]) != int(arr[i - 1]) + 1:
            out.append(arr[start:i].copy())
            start = i
    out.append(arr[start:].copy())
    return [segment for segment in out if len(segment) >= 2]


def _build_single_asset_bundle(
    df: pd.DataFrame,
    *,
    feature_cols: Sequence[str],
    returns_col: str,
    returns_type: str,
    train_idx: np.ndarray,
) -> _SingleAssetBundle:
    feature_values = df.loc[:, list(feature_cols)].to_numpy(dtype=np.float32, copy=True)
    train_features = feature_values[np.asarray(train_idx, dtype=int)]
    mean, std = _fit_feature_scaler(train_features)
    scaled = _scale_values(feature_values, mean=mean, std=std)
    simple_returns = _returns_to_simple(df[returns_col], returns_type=returns_type).to_numpy(dtype=np.float32)
    return _SingleAssetBundle(
        index=df.index,
        features=scaled,
        simple_returns=simple_returns.astype(np.float32, copy=False),
        feature_cols=list(feature_cols),
    )


def _align_feature_panel(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    feature_cols: Sequence[str],
    returns_col: str,
    alignment: str,
) -> tuple[pd.Index, tuple[str, ...], np.ndarray, np.ndarray]:
    feature_frames: list[pd.DataFrame] = []
    returns_frames: list[pd.Series] = []
    asset_names = tuple(sorted(asset_frames))
    for asset in asset_names:
        frame = asset_frames[asset]
        missing = [col for col in feature_cols if col not in frame.columns]
        if missing:
            raise KeyError(f"Portfolio RL missing feature columns for asset='{asset}': {missing}")
        if returns_col not in frame.columns:
            raise KeyError(f"Portfolio RL returns_col '{returns_col}' missing for asset='{asset}'.")
        feature_frames.append(frame.loc[:, list(feature_cols)].copy())
        returns_frames.append(frame[returns_col].astype(float).rename(asset))

    if alignment == "outer":
        joined_index = feature_frames[0].index
        for frame in feature_frames[1:]:
            joined_index = joined_index.union(frame.index)
    else:
        joined_index = feature_frames[0].index
        for frame in feature_frames[1:]:
            joined_index = joined_index.intersection(frame.index)
    joined_index = joined_index.sort_values()
    if len(joined_index) < 2:
        raise ValueError("Portfolio RL alignment produced fewer than 2 timestamps.")

    feature_panel = np.stack(
        [
            frame.reindex(joined_index).to_numpy(dtype=np.float32, copy=True)
            for frame in feature_frames
        ],
        axis=1,
    )
    returns_panel = np.column_stack(
        [series.reindex(joined_index).to_numpy(dtype=float, copy=True) for series in returns_frames]
    ).astype(np.float32, copy=False)
    return joined_index, asset_names, feature_panel, returns_panel


def _build_portfolio_bundle(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    feature_cols: Sequence[str],
    returns_col: str,
    returns_type: str,
    alignment: str,
    train_idx: np.ndarray,
) -> _PortfolioBundle:
    index, asset_names, feature_panel, returns_panel = _align_feature_panel(
        asset_frames,
        feature_cols=feature_cols,
        returns_col=returns_col,
        alignment=alignment,
    )
    train_features = feature_panel[np.asarray(train_idx, dtype=int)]
    mean = np.nanmean(train_features, axis=0).astype(np.float32, copy=False)
    std = np.nanstd(train_features, axis=0).astype(np.float32, copy=False)
    mean = np.where(np.isfinite(mean), mean, 0.0).astype(np.float32, copy=False)
    std = np.where(~np.isfinite(std) | (std < 1e-8), 1.0, std).astype(np.float32, copy=False)
    scaled = _scale_values(feature_panel, mean=mean, std=std)
    simple_returns = returns_panel if returns_type == "simple" else np.expm1(returns_panel.astype(float)).astype(np.float32)
    return _PortfolioBundle(
        index=index,
        features=scaled,
        simple_returns=simple_returns.astype(np.float32, copy=False),
        feature_cols=list(feature_cols),
        asset_names=asset_names,
    )


def _build_reward_config(model_cfg: dict[str, Any]) -> RLRewardConfig:
    env_cfg = dict(model_cfg.get("env", {}) or {})
    reward_cfg = dict(env_cfg.get("reward", {}) or {})
    risk_cfg = dict(model_cfg.get("risk", {}) or {})
    return RLRewardConfig(
        cost_per_turnover=float(reward_cfg.get("cost_per_turnover", risk_cfg.get("cost_per_turnover", 0.0))),
        slippage_per_turnover=float(
            reward_cfg.get("slippage_per_turnover", risk_cfg.get("slippage_per_turnover", 0.0))
        ),
        inventory_penalty=float(reward_cfg.get("inventory_penalty", 0.0)),
        drawdown_penalty=float(reward_cfg.get("drawdown_penalty", 0.0)),
        switching_penalty=float(reward_cfg.get("switching_penalty", 0.0)),
    )


def _build_execution_config(model_cfg: dict[str, Any]) -> RLExecutionConfig:
    env_cfg = dict(model_cfg.get("env", {}) or {})
    risk_cfg = dict(model_cfg.get("risk", {}) or {})
    dd_cfg = dict(risk_cfg.get("dd_guard", {}) or {})
    return RLExecutionConfig(
        min_holding_bars=int(env_cfg.get("min_holding_bars", 0)),
        action_hysteresis=float(env_cfg.get("action_hysteresis", 0.0)),
        dd_guard_enabled=bool(dd_cfg.get("enabled", False)),
        max_drawdown=float(dd_cfg.get("max_drawdown", 0.2)),
        cooloff_bars=int(dd_cfg.get("cooloff_bars", 20)),
        rearm_drawdown=float(dd_cfg["rearm_drawdown"]) if dd_cfg.get("rearm_drawdown") is not None else None,
    )


def _single_asset_action_spec(model_cfg: dict[str, Any], *, algorithm: str) -> tuple[bool, float, np.ndarray | None]:
    env_cfg = dict(model_cfg.get("env", {}) or {})
    action_space = str(env_cfg.get("action_space", "continuous" if algorithm == "ppo" else "discrete")).lower()
    if algorithm == "dqn" and action_space != "discrete":
        raise ValueError("DQN requires model.env.action_space='discrete'.")
    if action_space not in {"continuous", "discrete"}:
        raise ValueError("model.env.action_space must be 'continuous' or 'discrete'.")
    max_signal_abs = _resolve_max_signal_abs(env_cfg)
    if action_space == "continuous":
        return True, max_signal_abs, None
    grid = np.asarray(env_cfg.get("position_grid", _DEFAULT_SINGLE_ASSET_GRID), dtype=np.float32)
    if grid.ndim != 1 or len(grid) == 0:
        raise ValueError("model.env.position_grid must be a non-empty 1D list for discrete RL actions.")
    return False, max_signal_abs, grid


def _default_portfolio_action_templates(asset_count: int, *, max_signal_abs: float) -> np.ndarray:
    templates: list[np.ndarray] = [np.zeros(asset_count, dtype=np.float32)]
    templates.append(np.full(asset_count, max_signal_abs, dtype=np.float32))
    templates.append(np.full(asset_count, -max_signal_abs, dtype=np.float32))
    for asset_idx in range(asset_count):
        long_template = np.zeros(asset_count, dtype=np.float32)
        short_template = np.zeros(asset_count, dtype=np.float32)
        long_template[asset_idx] = max_signal_abs
        short_template[asset_idx] = -max_signal_abs
        templates.append(long_template)
        templates.append(short_template)
    return np.stack(templates, axis=0).astype(np.float32, copy=False)


def _portfolio_action_spec(
    model_cfg: dict[str, Any],
    *,
    algorithm: str,
    asset_count: int,
) -> tuple[bool, float, np.ndarray | None]:
    env_cfg = dict(model_cfg.get("env", {}) or {})
    action_space = str(env_cfg.get("action_space", "continuous" if algorithm == "ppo" else "discrete")).lower()
    if algorithm == "dqn" and action_space != "discrete":
        raise ValueError("Portfolio DQN requires model.env.action_space='discrete'.")
    if action_space not in {"continuous", "discrete"}:
        raise ValueError("model.env.action_space must be 'continuous' or 'discrete'.")
    max_signal_abs = _resolve_max_signal_abs(env_cfg)
    if action_space == "continuous":
        return True, max_signal_abs, None

    templates_raw = env_cfg.get("action_templates")
    if templates_raw is None:
        return False, max_signal_abs, _default_portfolio_action_templates(asset_count, max_signal_abs=max_signal_abs)

    templates = np.asarray(templates_raw, dtype=np.float32)
    if templates.ndim != 2 or templates.shape[1] != asset_count or templates.shape[0] == 0:
        raise ValueError("model.env.action_templates must be shaped as [n_actions, n_assets].")
    return False, max_signal_abs, templates


def _build_portfolio_constraints(portfolio_cfg: dict[str, Any]) -> PortfolioConstraints:
    constraints_cfg = dict(portfolio_cfg.get("constraints", {}) or {})
    group_caps = constraints_cfg.get("group_max_exposure")
    return PortfolioConstraints(
        min_weight=float(constraints_cfg.get("min_weight", -1.0)),
        max_weight=float(constraints_cfg.get("max_weight", 1.0)),
        max_gross_leverage=float(constraints_cfg.get("max_gross_leverage", 1.0)),
        target_net_exposure=float(constraints_cfg.get("target_net_exposure", 0.0)),
        turnover_limit=(
            float(constraints_cfg["turnover_limit"])
            if constraints_cfg.get("turnover_limit") is not None
            else None
        ),
        group_max_exposure=(
            {str(k): float(v) for k, v in dict(group_caps or {}).items()}
            if group_caps is not None
            else None
        ),
    )


def _policy_summary(
    *,
    signals: pd.Series,
    rewards: pd.Series,
) -> dict[str, float | int | None]:
    reward_valid = rewards.dropna()
    signal_valid = signals.dropna().astype(float)
    if reward_valid.empty and signal_valid.empty:
        return {
            "evaluation_rows": 0,
            "signal_rows": 0,
            "mean_reward": None,
            "total_reward": None,
            "mean_abs_signal": None,
            "signal_turnover": None,
            "long_rate": None,
            "short_rate": None,
            "flat_rate": None,
        }

    signal_turnover = None
    if len(signal_valid) >= 2:
        signal_turnover = float(signal_valid.diff().abs().dropna().mean())

    return {
        "evaluation_rows": int(len(reward_valid)),
        "signal_rows": int(len(signal_valid)),
        "mean_reward": float(reward_valid.mean()) if not reward_valid.empty else None,
        "total_reward": float(reward_valid.sum()) if not reward_valid.empty else None,
        "mean_abs_signal": float(signal_valid.abs().mean()) if not signal_valid.empty else None,
        "signal_turnover": signal_turnover,
        "long_rate": float((signal_valid > 0).mean()) if not signal_valid.empty else None,
        "short_rate": float((signal_valid < 0).mean()) if not signal_valid.empty else None,
        "flat_rate": float((signal_valid == 0).mean()) if not signal_valid.empty else None,
    }


def _rollout_single_asset_policy(
    *,
    model: object,
    bundle: _SingleAssetBundle,
    indices: np.ndarray,
    window_size: int,
    continuous_actions: bool,
    max_signal_abs: float,
    discrete_action_values: np.ndarray | None,
    reward_config: RLRewardConfig,
    execution_config: RLExecutionConfig,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    rollout_env = SingleAssetTradingEnv(
        features=bundle.features,
        simple_returns=bundle.simple_returns,
        window_size=window_size,
        continuous_actions=continuous_actions,
        max_signal_abs=max_signal_abs,
        discrete_action_values=discrete_action_values,
        reward_config=reward_config,
        execution_config=execution_config,
    )
    signals = pd.Series(np.nan, index=bundle.index, dtype="float32")
    actions = pd.Series(np.nan, index=bundle.index, dtype="float32")
    rewards = pd.Series(np.nan, index=bundle.index, dtype="float32")

    position = 0.0
    equity = 1.0
    running_max = 1.0
    drawdown = 0.0

    for idx in np.asarray(indices, dtype=int):
        obs = rollout_env._build_observation(step=int(idx), position=position, drawdown=drawdown)
        action, _ = model.predict(obs, deterministic=True)
        action_value = rollout_env._map_action(action)
        actions.iat[int(idx)] = np.float32(
            float(np.asarray(action).reshape(-1)[0]) if np.asarray(action).size > 0 else float(action_value)
        )
        signals.iat[int(idx)] = np.float32(action_value)
        if int(idx) >= len(bundle.simple_returns) - 1:
            position = float(action_value)
            continue
        rollout_env.current_step = int(idx)
        rollout_env.position = position
        rollout_env.equity = equity
        rollout_env.running_max = running_max
        rollout_env.drawdown = drawdown
        reward, info = rollout_env._transition(action_value=float(action_value))
        rewards.iat[int(idx)] = np.float32(reward)
        position = float(info["position"])
        equity = float(info["equity"])
        running_max = float(info["running_max"])
        drawdown = float(info["drawdown"])

    return signals, actions, rewards


def _rollout_portfolio_policy(
    *,
    model: object,
    bundle: _PortfolioBundle,
    indices: np.ndarray,
    window_size: int,
    continuous_actions: bool,
    max_signal_abs: float,
    discrete_action_templates: np.ndarray | None,
    reward_config: RLRewardConfig,
    execution_config: RLExecutionConfig,
    constraints: PortfolioConstraints,
    asset_to_group: Mapping[str, str] | None,
    long_short: bool,
    gross_target: float,
) -> tuple[dict[str, pd.Series], pd.Series]:
    rollout_env = PortfolioTradingEnv(
        features=bundle.features,
        simple_returns=bundle.simple_returns,
        asset_names=bundle.asset_names,
        window_size=window_size,
        continuous_actions=continuous_actions,
        max_signal_abs=max_signal_abs,
        discrete_action_templates=discrete_action_templates,
        reward_config=reward_config,
        execution_config=execution_config,
        constraints=constraints,
        asset_to_group=asset_to_group,
        long_short=long_short,
        gross_target=gross_target,
    )
    signals_by_asset = {
        asset: pd.Series(np.nan, index=bundle.index, dtype="float32") for asset in bundle.asset_names
    }
    rewards = pd.Series(np.nan, index=bundle.index, dtype="float32")

    weights = pd.Series(0.0, index=bundle.asset_names, dtype=float)
    equity = 1.0
    running_max = 1.0
    drawdown = 0.0

    for idx in np.asarray(indices, dtype=int):
        obs = rollout_env._build_observation(step=int(idx), weights=weights, drawdown=drawdown)
        action, _ = model.predict(obs, deterministic=True)
        signal_values = rollout_env._map_action(action)
        for asset_idx, asset in enumerate(bundle.asset_names):
            signals_by_asset[asset].iat[int(idx)] = np.float32(signal_values[asset_idx])
        if int(idx) >= len(bundle.index) - 1:
            continue
        rollout_env.current_step = int(idx)
        rollout_env.weights = weights
        rollout_env.equity = equity
        rollout_env.running_max = running_max
        rollout_env.drawdown = drawdown
        reward, info = rollout_env._transition(signal_values=signal_values)
        rewards.iat[int(idx)] = np.float32(reward)
        weights = pd.Series(info["weights"], dtype=float).reindex(bundle.asset_names).fillna(0.0)
        equity = float(info["equity"])
        running_max = float(info["running_max"])
        drawdown = float(info["drawdown"])

    return signals_by_asset, rewards


def _single_asset_rl_meta(
    *,
    model_kind: str,
    runtime_meta: dict[str, Any],
    feature_cols: list[str],
    contracts: dict[str, Any],
    split_method: str,
    folds: list[dict[str, Any]],
    train_rows: int,
    test_pred_rows: int,
    oos_rows: int,
    target_horizon: int,
    returns_col: str,
    reward_summary: dict[str, Any],
    signal_col: str,
    action_col: str | None,
    pred_is_oos_col: str,
) -> dict[str, Any]:
    return {
        "model_kind": model_kind,
        "runtime": runtime_meta,
        "feature_cols": feature_cols,
        "split_method": split_method,
        "split_index": int(folds[0]["test_start"]) if folds else None,
        "n_folds": int(len(folds)),
        "folds": folds,
        "train_rows": int(train_rows),
        "test_pred_rows": int(test_pred_rows),
        "oos_rows": int(oos_rows),
        "oos_prediction_coverage": float(test_pred_rows / max(oos_rows, 1)),
        "oos_classification_summary": empty_classification_metrics(),
        "oos_regression_summary": empty_regression_metrics(),
        "oos_volatility_summary": empty_volatility_metrics(),
        "oos_policy_summary": reward_summary,
        "signal_col": signal_col,
        "action_col": action_col,
        "pred_is_oos_col": pred_is_oos_col,
        "target": {"kind": "forward_return", "horizon": int(target_horizon)},
        "returns_col": returns_col,
        "contracts": contracts,
        "anti_leakage": {
            "target_horizon": int(target_horizon),
            "total_trimmed_train_rows": int(sum(int(fold["trimmed_for_horizon_rows"]) for fold in folds)),
        },
    }


def _aggregate_policy_summary(per_asset_meta: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    total_rows = int(
        sum(int(meta.get("oos_policy_summary", {}).get("evaluation_rows") or 0) for meta in per_asset_meta.values())
    )
    signal_rows = int(
        sum(int(meta.get("oos_policy_summary", {}).get("signal_rows") or 0) for meta in per_asset_meta.values())
    )
    if total_rows <= 0 and signal_rows <= 0:
        return {
            "evaluation_rows": 0,
            "signal_rows": 0,
            "mean_reward": None,
            "total_reward": None,
            "mean_abs_signal": None,
            "signal_turnover": None,
            "long_rate": None,
            "short_rate": None,
            "flat_rate": None,
        }

    weighted_keys = ("mean_reward", "mean_abs_signal", "signal_turnover", "long_rate", "short_rate", "flat_rate")
    out: dict[str, Any] = {"evaluation_rows": total_rows, "signal_rows": signal_rows, "total_reward": 0.0}
    for key in weighted_keys:
        numerator = 0.0
        weight_total = 0
        weight_key = "evaluation_rows" if key == "mean_reward" else "signal_rows"
        for meta in per_asset_meta.values():
            summary = dict(meta.get("oos_policy_summary", {}) or {})
            rows = int(summary.get(weight_key) or 0)
            value = summary.get(key)
            if rows <= 0 or value is None:
                continue
            numerator += float(value) * rows
            weight_total += rows
        out[key] = float(numerator / weight_total) if weight_total > 0 else None
    for meta in per_asset_meta.values():
        summary = dict(meta.get("oos_policy_summary", {}) or {})
        if summary.get("total_reward") is not None:
            out["total_reward"] += float(summary["total_reward"])
    return out

