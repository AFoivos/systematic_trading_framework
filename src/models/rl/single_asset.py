from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.model_metrics import (
    empty_classification_metrics,
    empty_regression_metrics,
    empty_volatility_metrics,
)
from src.evaluation.time_splits import (
    assert_no_forward_label_leakage,
    build_time_splits,
    trim_train_indices_for_horizon,
)
from src.models.common.runtime import infer_feature_columns, resolve_runtime_for_model
from src.models.rl.common import (
    _build_execution_config,
    _build_reward_config,
    _build_single_asset_bundle,
    _coerce_positive_int,
    _contiguous_segments,
    _policy_summary,
    _rollout_single_asset_policy,
    _single_asset_action_spec,
    _single_asset_rl_meta,
    _validate_execution_lag,
    _validate_rl_feature_columns,
)
from src.models.rl.envs import SingleAssetTradingEnv
from src.models.rl.sb3 import make_vec_env, train_sb3_model


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
    pred_is_oos_col = str(model_cfg.get("pred_is_oos_col") or "pred_is_oos")
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
        feature_selectors=model_cfg.get("feature_selectors"),
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
    execution_config = _build_execution_config(model_cfg)
    execution_config = _build_execution_config(model_cfg)

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
    out[pred_is_oos_col] = False

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
                    execution_config=execution_config,
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
            execution_config=execution_config,
        )
        valid_signals = signals.dropna().astype("float32", copy=False)
        valid_actions = actions.dropna().astype("float32", copy=False)
        out.loc[valid_signals.index, signal_col] = valid_signals.to_numpy(dtype=np.float32, copy=False)
        out.loc[valid_actions.index, action_col] = valid_actions.to_numpy(dtype=np.float32, copy=False)
        out.loc[df.index[test_idx], pred_is_oos_col] = True
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
        signal_col=signal_col,
        action_col=action_col,
        pred_is_oos_col=pred_is_oos_col,
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


__all__ = ["train_dqn_agent", "train_ppo_agent"]
