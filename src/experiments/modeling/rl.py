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
from src.experiments.modeling.metrics import (
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
)
from src.experiments.modeling.runtime import infer_feature_columns, resolve_runtime_for_model
from src.models.rl.envs import PortfolioTradingEnv, RLRewardConfig, SingleAssetTradingEnv
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
) -> tuple[pd.Series, pd.Series, pd.Series]:
    rollout_env = SingleAssetTradingEnv(
        features=bundle.features,
        simple_returns=bundle.simple_returns,
        window_size=window_size,
        continuous_actions=continuous_actions,
        max_signal_abs=max_signal_abs,
        discrete_action_values=discrete_action_values,
        reward_config=reward_config,
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


def _train_single_asset_rl(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    *,
    model_kind: str,
    algorithm: str,
    returns_col: str | None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    model_cfg = dict(model_cfg or {})
    model_params = dict(model_cfg.get("params", {}) or {})
    runtime_meta = resolve_runtime_for_model(
        model_cfg=model_cfg,
        model_params=model_params,
        estimator_family="torch",
    )

    signal_col = str(model_cfg.get("signal_col") or "signal_rl")
    action_col = str(model_cfg.get("action_col") or "action_rl")
    backtest_cfg = dict(model_cfg.get("backtest", {}) or {})
    effective_returns_col = str(returns_col or backtest_cfg.get("returns_col") or "close_ret")
    if effective_returns_col not in df.columns:
        raise KeyError(f"RL returns_col '{effective_returns_col}' not found in dataframe.")
    returns_type = str(backtest_cfg.get("returns_type", "simple"))
    target_cfg = dict(model_cfg.get("target", {}) or {})
    target_horizon = _coerce_positive_int(target_cfg.get("horizon", 1), name="model.target.horizon", default=1)
    if target_horizon != 1:
        raise ValueError("RL currently supports only model.target.horizon=1.")

    feature_cols = infer_feature_columns(
        df,
        explicit_cols=model_cfg.get("feature_cols"),
        exclude={signal_col, action_col},
    )
    contracts = _validate_rl_feature_columns(df, feature_cols=feature_cols)

    env_cfg = dict(model_cfg.get("env", {}) or {})
    _validate_execution_lag(env_cfg)
    window_size = _coerce_positive_int(env_cfg.get("window_size", 32), name="model.env.window_size", default=32)
    continuous_actions, max_signal_abs, discrete_action_values = _single_asset_action_spec(
        model_cfg,
        algorithm=algorithm,
    )
    reward_config = _build_reward_config(model_cfg)

    split_cfg = dict(model_cfg.get("split", {}) or {})
    split_method = str(split_cfg.get("method", "time"))
    splits = build_time_splits(
        method=split_method,
        n_samples=len(df),
        split_cfg=split_cfg,
        target_horizon=target_horizon,
    )

    out = df.copy()
    out[signal_col] = pd.Series(np.nan, index=out.index, dtype="float32")
    out[action_col] = pd.Series(np.nan, index=out.index, dtype="float32")
    out["pred_is_oos"] = False

    folds: list[dict[str, Any]] = []
    total_train_rows = 0
    total_test_pred_rows = 0
    oos_mask = pd.Series(False, index=df.index)
    aggregate_rewards = pd.Series(np.nan, index=df.index, dtype="float32")
    last_model: object | None = None

    for split in splits:
        raw_train_idx = np.asarray(split.train_idx, dtype=int)
        safe_train_idx = trim_train_indices_for_horizon(
            raw_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        assert_no_forward_label_leakage(
            safe_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        trimmed_rows = int(len(raw_train_idx) - len(safe_train_idx))
        bundle = _build_single_asset_bundle(
            df,
            feature_cols=feature_cols,
            returns_col=effective_returns_col,
            returns_type=returns_type,
            train_idx=safe_train_idx,
        )
        segments = _contiguous_segments(safe_train_idx)
        env_fns = []
        for segment in segments:
            seg_frame = bundle.features[segment]
            seg_returns = bundle.simple_returns[segment]

            def _factory(
                features=seg_frame,
                simple_returns=seg_returns,
                window_size=window_size,
                continuous_actions=continuous_actions,
                max_signal_abs=max_signal_abs,
                discrete_action_values=discrete_action_values,
                reward_config=reward_config,
            ):
                return SingleAssetTradingEnv(
                    features=features,
                    simple_returns=simple_returns,
                    window_size=window_size,
                    continuous_actions=continuous_actions,
                    max_signal_abs=max_signal_abs,
                    discrete_action_values=discrete_action_values,
                    reward_config=reward_config,
                )

            env_fns.append(_factory)
        if not env_fns:
            raise ValueError(f"RL fold {split.fold} has no valid contiguous training segment.")

        train_envs = make_vec_env(env_fns)
        model, algo_meta = train_sb3_model(
            algorithm=algorithm,
            env=train_envs,
            observation_space=None,
            params=model_params,
            runtime_meta=runtime_meta,
        )
        for train_env in (train_envs if isinstance(train_envs, list) else [train_envs]):
            train_env.close()
        last_model = model

        test_idx = np.asarray(split.test_idx, dtype=int)
        signals, actions, rewards = _rollout_single_asset_policy(
            model=model,
            bundle=bundle,
            indices=test_idx,
            window_size=window_size,
            continuous_actions=continuous_actions,
            max_signal_abs=max_signal_abs,
            discrete_action_values=discrete_action_values,
            reward_config=reward_config,
        )
        valid_signals = signals.dropna().astype("float32", copy=False)
        valid_actions = actions.dropna().astype("float32", copy=False)
        out.loc[valid_signals.index, signal_col] = valid_signals.to_numpy(dtype=np.float32, copy=False)
        out.loc[valid_actions.index, action_col] = valid_actions.to_numpy(dtype=np.float32, copy=False)
        out.loc[df.index[test_idx], "pred_is_oos"] = True
        valid_rewards = rewards.dropna().astype("float32", copy=False)
        aggregate_rewards.loc[valid_rewards.index] = valid_rewards.to_numpy(dtype=np.float32, copy=False)
        oos_mask.loc[df.index[test_idx]] = True

        fold_summary = _policy_summary(signals=signals.loc[df.index[test_idx]], rewards=rewards.loc[df.index[test_idx]])
        total_train_rows += int(len(safe_train_idx))
        total_test_pred_rows += int(signals.loc[df.index[test_idx]].notna().sum())
        folds.append(
            {
                "fold": int(split.fold),
                "train_start": int(split.train_start),
                "train_end": int(split.train_end),
                "effective_train_start": int(safe_train_idx.min()) if len(safe_train_idx) else None,
                "effective_train_end": int(safe_train_idx.max() + 1) if len(safe_train_idx) else None,
                "trimmed_for_horizon_rows": trimmed_rows,
                "test_start": int(split.test_start),
                "test_end": int(split.test_end),
                "train_rows": int(len(safe_train_idx)),
                "test_rows": int(len(test_idx)),
                "test_pred_rows": int(signals.loc[df.index[test_idx]].notna().sum()),
                "classification_metrics": empty_classification_metrics(),
                "regression_metrics": empty_regression_metrics(),
                "volatility_metrics": empty_volatility_metrics(),
                "policy_metrics": fold_summary,
                "rl_algorithm": algo_meta,
            }
        )

    if last_model is None:
        raise ValueError("RL model training failed: no folds were trained.")

    meta = _single_asset_rl_meta(
        model_kind=model_kind,
        runtime_meta=runtime_meta,
        feature_cols=feature_cols,
        contracts=contracts,
        split_method=split_method,
        folds=folds,
        train_rows=total_train_rows,
        test_pred_rows=total_test_pred_rows,
        oos_rows=int(oos_mask.sum()),
        target_horizon=target_horizon,
        returns_col=effective_returns_col,
        reward_summary=_policy_summary(signals=out.loc[oos_mask, signal_col], rewards=aggregate_rewards.loc[oos_mask]),
    )
    return out, last_model, meta


def train_ppo_agent(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    return _train_single_asset_rl(
        df,
        model_cfg,
        model_kind="ppo_agent",
        algorithm="ppo",
        returns_col=returns_col,
    )


def train_dqn_agent(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object, dict[str, Any]]:
    return _train_single_asset_rl(
        df,
        model_cfg,
        model_kind="dqn_agent",
        algorithm="dqn",
        returns_col=returns_col,
    )


def _train_portfolio_rl(
    asset_frames: Mapping[str, pd.DataFrame],
    model_cfg: dict[str, Any],
    *,
    model_kind: str,
    algorithm: str,
    returns_col: str | None,
) -> tuple[dict[str, pd.DataFrame], object, dict[str, Any]]:
    model_cfg = dict(model_cfg or {})
    model_params = dict(model_cfg.get("params", {}) or {})
    runtime_meta = resolve_runtime_for_model(
        model_cfg=model_cfg,
        model_params=model_params,
        estimator_family="torch",
    )
    signal_col = str(model_cfg.get("signal_col") or "signal_rl")
    backtest_cfg = dict(model_cfg.get("backtest", {}) or {})
    portfolio_cfg = dict(model_cfg.get("portfolio", {}) or {})
    alignment = str(model_cfg.get("data_alignment") or model_cfg.get("alignment") or "inner")
    effective_returns_col = str(returns_col or backtest_cfg.get("returns_col") or "close_ret")
    returns_type = str(backtest_cfg.get("returns_type", "simple"))
    target_cfg = dict(model_cfg.get("target", {}) or {})
    target_horizon = _coerce_positive_int(target_cfg.get("horizon", 1), name="model.target.horizon", default=1)
    if target_horizon != 1:
        raise ValueError("Portfolio RL currently supports only model.target.horizon=1.")
    env_cfg = dict(model_cfg.get("env", {}) or {})
    _validate_execution_lag(env_cfg)
    window_size = _coerce_positive_int(env_cfg.get("window_size", 32), name="model.env.window_size", default=32)
    reward_config = _build_reward_config(model_cfg)
    if alignment != "inner":
        raise ValueError("Portfolio RL currently requires inner alignment.")

    first_frame = next(iter(asset_frames.values()))
    feature_cols = infer_feature_columns(
        first_frame,
        explicit_cols=model_cfg.get("feature_cols"),
        exclude={signal_col},
    )
    for asset, frame in asset_frames.items():
        _validate_rl_feature_columns(frame, feature_cols=feature_cols)

    constraints = _build_portfolio_constraints(portfolio_cfg)
    asset_to_group = {str(k): str(v) for k, v in dict(portfolio_cfg.get("asset_groups", {}) or {}).items()}
    long_short = bool(portfolio_cfg.get("long_short", True))
    gross_target = float(portfolio_cfg.get("gross_target", 1.0))

    aligned_index, asset_names, _, _ = _align_feature_panel(
        asset_frames,
        feature_cols=feature_cols,
        returns_col=effective_returns_col,
        alignment=alignment,
    )
    continuous_actions, max_signal_abs, discrete_templates = _portfolio_action_spec(
        model_cfg,
        algorithm=algorithm,
        asset_count=len(asset_names),
    )

    split_cfg = dict(model_cfg.get("split", {}) or {})
    split_method = str(split_cfg.get("method", "time"))
    splits = build_time_splits(
        method=split_method,
        n_samples=len(aligned_index),
        split_cfg=split_cfg,
        target_horizon=target_horizon,
    )

    output_frames = {asset: frame.copy() for asset, frame in sorted(asset_frames.items())}
    for frame in output_frames.values():
        frame[signal_col] = pd.Series(np.nan, index=frame.index, dtype="float32")
        frame["pred_is_oos"] = False

    folds: list[dict[str, Any]] = []
    total_train_rows = 0
    total_test_pred_rows = 0
    last_model: object | None = None
    portfolio_rewards = pd.Series(np.nan, index=aligned_index, dtype="float32")

    for split in splits:
        raw_train_idx = np.asarray(split.train_idx, dtype=int)
        safe_train_idx = trim_train_indices_for_horizon(
            raw_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        assert_no_forward_label_leakage(
            safe_train_idx,
            test_start=int(split.test_start),
            target_horizon=target_horizon,
        )
        trimmed_rows = int(len(raw_train_idx) - len(safe_train_idx))

        bundle = _build_portfolio_bundle(
            asset_frames,
            feature_cols=feature_cols,
            returns_col=effective_returns_col,
            returns_type=returns_type,
            alignment=alignment,
            train_idx=safe_train_idx,
        )
        segments = _contiguous_segments(safe_train_idx)
        env_fns = []
        for segment in segments:
            seg_features = bundle.features[segment]
            seg_returns = bundle.simple_returns[segment]

            def _factory(
                features=seg_features,
                simple_returns=seg_returns,
                asset_names=bundle.asset_names,
                window_size=window_size,
                continuous_actions=continuous_actions,
                max_signal_abs=max_signal_abs,
                discrete_templates=discrete_templates,
                reward_config=reward_config,
                constraints=constraints,
                asset_to_group=asset_to_group,
                long_short=long_short,
                gross_target=gross_target,
            ):
                return PortfolioTradingEnv(
                    features=features,
                    simple_returns=simple_returns,
                    asset_names=asset_names,
                    window_size=window_size,
                    continuous_actions=continuous_actions,
                    max_signal_abs=max_signal_abs,
                    discrete_action_templates=discrete_templates,
                    reward_config=reward_config,
                    constraints=constraints,
                    asset_to_group=asset_to_group,
                    long_short=long_short,
                    gross_target=gross_target,
                )

            env_fns.append(_factory)
        if not env_fns:
            raise ValueError(f"Portfolio RL fold {split.fold} has no valid contiguous training segment.")

        train_envs = make_vec_env(env_fns)
        model, algo_meta = train_sb3_model(
            algorithm=algorithm,
            env=train_envs,
            observation_space=None,
            params=model_params,
            runtime_meta=runtime_meta,
        )
        for train_env in (train_envs if isinstance(train_envs, list) else [train_envs]):
            train_env.close()
        last_model = model

        test_idx = np.asarray(split.test_idx, dtype=int)
        signals_by_asset, rewards = _rollout_portfolio_policy(
            model=model,
            bundle=bundle,
            indices=test_idx,
            window_size=window_size,
            continuous_actions=continuous_actions,
            max_signal_abs=max_signal_abs,
            discrete_action_templates=discrete_templates,
            reward_config=reward_config,
            constraints=constraints,
            asset_to_group=asset_to_group,
            long_short=long_short,
            gross_target=gross_target,
        )
        for asset in bundle.asset_names:
            asset_signal = signals_by_asset[asset]
            frame = output_frames[asset]
            aligned = asset_signal.dropna().astype("float32", copy=False)
            if not aligned.empty:
                common_index = frame.index.intersection(aligned.index)
                frame.loc[common_index, signal_col] = aligned.reindex(common_index).to_numpy(
                    dtype=np.float32,
                    copy=False,
                )
                frame.loc[common_index, "pred_is_oos"] = True
        valid_rewards = rewards.dropna().astype("float32", copy=False)
        portfolio_rewards.loc[valid_rewards.index] = valid_rewards.to_numpy(dtype=np.float32, copy=False)

        total_train_rows += int(len(safe_train_idx))
        total_test_pred_rows += int(len(test_idx))
        folds.append(
            {
                "fold": int(split.fold),
                "train_start": int(split.train_start),
                "train_end": int(split.train_end),
                "effective_train_start": int(safe_train_idx.min()) if len(safe_train_idx) else None,
                "effective_train_end": int(safe_train_idx.max() + 1) if len(safe_train_idx) else None,
                "trimmed_for_horizon_rows": trimmed_rows,
                "test_start": int(split.test_start),
                "test_end": int(split.test_end),
                "train_rows": int(len(safe_train_idx)),
                "test_rows": int(len(test_idx)),
                "test_pred_rows": int(len(test_idx)),
                "classification_metrics": empty_classification_metrics(),
                "regression_metrics": empty_regression_metrics(),
                "volatility_metrics": empty_volatility_metrics(),
                "policy_metrics": _policy_summary(
                    signals=pd.concat(
                        [signals_by_asset[asset].loc[bundle.index[test_idx]] for asset in bundle.asset_names],
                        axis=0,
                    ),
                    rewards=rewards.loc[bundle.index[test_idx]],
                ),
                "rl_algorithm": algo_meta,
            }
        )

    if last_model is None:
        raise ValueError("Portfolio RL model training failed: no folds were trained.")

    per_asset_meta: dict[str, dict[str, Any]] = {}
    for asset in asset_names:
        asset_frame = output_frames[asset]
        asset_oos_mask = asset_frame["pred_is_oos"].astype(bool)
        per_asset_meta[asset] = _single_asset_rl_meta(
            model_kind=model_kind,
            runtime_meta=runtime_meta,
            feature_cols=feature_cols,
            contracts={"n_features": int(len(feature_cols))},
            split_method=split_method,
            folds=folds,
            train_rows=total_train_rows,
            test_pred_rows=int(asset_oos_mask.sum()),
            oos_rows=int(asset_oos_mask.sum()),
            target_horizon=target_horizon,
            returns_col=effective_returns_col,
            reward_summary=_policy_summary(signals=asset_frame.loc[asset_oos_mask, signal_col], rewards=pd.Series(dtype=float)),
        )

    aggregate_meta = {
        "model_kind": model_kind,
        "scope": "portfolio",
        "assets": list(asset_names),
        "feature_cols": list(feature_cols),
        "per_asset": per_asset_meta,
        "train_rows": int(total_train_rows),
        "test_pred_rows": int(total_test_pred_rows),
        "oos_rows": int(total_test_pred_rows),
        "oos_classification_summary": empty_classification_metrics(),
        "oos_regression_summary": empty_regression_metrics(),
        "oos_volatility_summary": empty_volatility_metrics(),
        "oos_policy_summary": _policy_summary(
            signals=pd.concat(
                [output_frames[asset].loc[output_frames[asset]["pred_is_oos"], signal_col] for asset in asset_names],
                axis=0,
            ),
            rewards=portfolio_rewards.dropna(),
        ),
        "aggregated_per_asset_policy_summary": _aggregate_policy_summary(per_asset_meta),
        "runtime": runtime_meta,
        "folds": folds,
        "returns_col": effective_returns_col,
        "contracts": {"n_features": int(len(feature_cols))},
        "anti_leakage": {
            "target_horizon": int(target_horizon),
            "total_trimmed_train_rows": int(sum(int(fold["trimmed_for_horizon_rows"]) for fold in folds)),
        },
    }
    return output_frames, last_model, aggregate_meta


def train_ppo_portfolio_agent(
    asset_frames: Mapping[str, pd.DataFrame],
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[dict[str, pd.DataFrame], object, dict[str, Any]]:
    return _train_portfolio_rl(
        asset_frames,
        model_cfg,
        model_kind="ppo_portfolio_agent",
        algorithm="ppo",
        returns_col=returns_col,
    )


def train_dqn_portfolio_agent(
    asset_frames: Mapping[str, pd.DataFrame],
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[dict[str, pd.DataFrame], object, dict[str, Any]]:
    return _train_portfolio_rl(
        asset_frames,
        model_cfg,
        model_kind="dqn_portfolio_agent",
        algorithm="dqn",
        returns_col=returns_col,
    )


__all__ = [
    "train_dqn_agent",
    "train_dqn_portfolio_agent",
    "train_ppo_agent",
    "train_ppo_portfolio_agent",
]
