from __future__ import annotations

from typing import Any, Mapping

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
    _aggregate_policy_summary,
    _align_feature_panel,
    _build_execution_config,
    _build_portfolio_bundle,
    _build_portfolio_constraints,
    _build_reward_config,
    _coerce_positive_int,
    _contiguous_segments,
    _policy_summary,
    _portfolio_action_spec,
    _rollout_portfolio_policy,
    _single_asset_rl_meta,
    _validate_execution_lag,
    _validate_rl_feature_columns,
)
from src.models.rl.envs import PortfolioTradingEnv
from src.models.rl.sb3 import make_vec_env, train_sb3_model


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
    pred_is_oos_col = str(model_cfg.get("pred_is_oos_col") or "pred_is_oos")
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
    execution_config = _build_execution_config(model_cfg)
    if alignment != "inner":
        raise ValueError("Portfolio RL currently requires inner alignment.")

    first_frame = next(iter(asset_frames.values()))
    feature_cols = infer_feature_columns(
        first_frame,
        explicit_cols=model_cfg.get("feature_cols"),
        feature_selectors=model_cfg.get("feature_selectors"),
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
        frame[pred_is_oos_col] = False

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
                    execution_config=execution_config,
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
            execution_config=execution_config,
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
                frame.loc[common_index, pred_is_oos_col] = True
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
        asset_oos_mask = asset_frame[pred_is_oos_col].astype(bool)
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
            signal_col=signal_col,
            action_col=None,
            pred_is_oos_col=pred_is_oos_col,
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
                [output_frames[asset].loc[output_frames[asset][pred_is_oos_col], signal_col] for asset in asset_names],
                axis=0,
            ),
            rewards=portfolio_rewards.dropna(),
        ),
        "aggregated_per_asset_policy_summary": _aggregate_policy_summary(per_asset_meta),
        "runtime": runtime_meta,
        "folds": folds,
        "returns_col": effective_returns_col,
        "signal_col": signal_col,
        "pred_is_oos_col": pred_is_oos_col,
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
    """
    Apply the registered ``ppo_portfolio_agent`` RL model transformation.
    
    This RL model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: ppo_portfolio_agent
          params:
            asset_frames: <required>
            returns_col: null
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    
    Parameters
    ----------
    asset_frames:
        Configuration parameter accepted by this RL model.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    """
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
    """
    Apply the registered ``dqn_portfolio_agent`` RL model transformation.
    
    This RL model uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        model:
          kind: dqn_portfolio_agent
          params:
            asset_frames: <required>
            returns_col: null
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    
    Parameters
    ----------
    asset_frames:
        Configuration parameter accepted by this RL model.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``null``.
    """
    return _train_portfolio_rl(
        asset_frames,
        model_cfg,
        model_kind="dqn_portfolio_agent",
        algorithm="dqn",
        returns_col=returns_col,
    )


__all__ = ["train_dqn_portfolio_agent", "train_ppo_portfolio_agent"]
