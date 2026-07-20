from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import numpy as np
import pandas as pd

from src.models.rl.risk_env import (
    RiskRewardConfig,
    RiskTradeConfig,
    SingleAssetRiskTradingEnv,
)
from src.models.rl.sb3 import build_policy_kwargs
from src.models.rl.walk_forward import (
    PolicyEvaluation,
    PolicyMetrics,
    SlidingWindowFold,
    build_sliding_window_folds,
    evaluate_checkpoints_then_test,
    evaluate_consistency_gate,
)


_PIPELINE_PARAM_KEYS = {
    "artifact_dir",
    "checkpoint_interval",
    "checkpoint_drawdown_penalty",
    "run_name",
}

_RL_PERFORMANCE_COLUMNS = {
    "net_return": "rl_net_return",
    "equity": "rl_equity",
    "reward": "rl_reward",
    "drawdown": "rl_drawdown",
    "position_leverage": "rl_position_leverage",
    "transaction_cost_return": "rl_transaction_cost_return",
    "fold": "rl_fold",
}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not np.isfinite(value):
            return None
        return value
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _trim_causal_warmup(
    frame: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    execution_columns: Sequence[str],
) -> tuple[pd.DataFrame, int]:
    required = list(dict.fromkeys([*feature_columns, *execution_columns]))
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise KeyError(f"PPO risk pipeline is missing required columns: {missing}")
    values = frame.loc[:, required].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    finite_rows = np.isfinite(values).all(axis=1)
    valid_positions = np.flatnonzero(finite_rows)
    if valid_positions.size == 0:
        raise ValueError("PPO risk pipeline has no rows with finite feature and execution inputs.")
    first_valid = int(valid_positions[0])
    if not bool(finite_rows[first_valid:].all()):
        invalid_after_warmup = np.flatnonzero(~finite_rows[first_valid:]) + first_valid
        examples = [str(frame.index[int(position)]) for position in invalid_after_warmup[:5]]
        raise ValueError(
            "Non-finite inputs are allowed only in the leading causal feature warmup; "
            f"invalid timestamps after warmup={examples}."
        )
    return frame.iloc[first_valid:].copy(), first_valid


def _fit_train_normalizer(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if values.ndim != 2 or len(values) == 0 or not bool(np.isfinite(values).all()):
        raise ValueError("Normalizer fit requires a non-empty finite 2D training matrix.")
    mean = values.mean(axis=0, dtype=np.float64)
    std = values.std(axis=0, dtype=np.float64)
    std = np.where(std < 1e-8, 1.0, std)
    return mean.astype(np.float32), std.astype(np.float32)


def _apply_normalizer(values: np.ndarray, *, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    normalized = (values.astype(np.float32, copy=False) - mean) / std
    if not bool(np.isfinite(normalized).all()):
        raise ValueError("Feature normalization produced non-finite values.")
    return normalized.astype(np.float32, copy=False)


def _make_env(
    *,
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    atr_column: str,
    lookback_window: int,
    trade_config: RiskTradeConfig,
    reward_config: RiskRewardConfig,
    start_step: int,
    end_step: int,
    env_cfg: Mapping[str, Any],
) -> SingleAssetRiskTradingEnv:
    return SingleAssetRiskTradingEnv(
        frame=frame,
        feature_columns=feature_columns,
        atr_column=atr_column,
        lookback_window=lookback_window,
        trade_config=trade_config,
        reward_config=reward_config,
        open_column=str(env_cfg.get("open_column", "open")),
        high_column=str(env_cfg.get("high_column", "high")),
        low_column=str(env_cfg.get("low_column", "low")),
        close_column=str(env_cfg.get("close_column", "close")),
        start_step=int(start_step),
        end_step=int(end_step),
        allow_raw_ohlc_features=bool(env_cfg.get("allow_raw_ohlc_features", False)),
    )


def _train_ppo_checkpoints(
    *,
    env: SingleAssetRiskTradingEnv,
    params: Mapping[str, Any],
    seed: int,
    checkpoint_dir: Path,
) -> list[tuple[str, int]]:
    from stable_baselines3 import PPO

    total_timesteps = int(params.get("total_timesteps", 5_000))
    checkpoint_interval = int(params.get("checkpoint_interval", total_timesteps))
    if total_timesteps <= 0 or checkpoint_interval <= 0:
        raise ValueError("total_timesteps and checkpoint_interval must be > 0.")
    n_steps = max(int(params.get("n_steps", 128)), 2)
    batch_size = min(max(int(params.get("batch_size", 64)), 1), n_steps)
    policy_kwargs = build_policy_kwargs(dict(params))
    model = PPO(
        policy=str(params.get("policy", "MlpPolicy")),
        env=env,
        learning_rate=float(params.get("learning_rate", 3e-4)),
        n_steps=n_steps,
        batch_size=batch_size,
        gamma=float(params.get("gamma", 0.99)),
        gae_lambda=float(params.get("gae_lambda", 0.95)),
        clip_range=float(params.get("clip_range", 0.2)),
        ent_coef=float(params.get("ent_coef", 0.0)),
        vf_coef=float(params.get("vf_coef", 0.5)),
        max_grad_norm=float(params.get("max_grad_norm", 0.5)),
        policy_kwargs=policy_kwargs,
        seed=int(seed),
        verbose=0,
        device=str(params.get("device", "cpu")),
    )
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoints: list[tuple[str, int]] = []
    planned_steps = 0
    while planned_steps < total_timesteps:
        chunk = min(checkpoint_interval, total_timesteps - planned_steps)
        model.learn(
            total_timesteps=int(chunk),
            progress_bar=False,
            reset_num_timesteps=planned_steps == 0,
        )
        planned_steps += int(chunk)
        actual_steps = int(model.num_timesteps)
        base_path = checkpoint_dir / f"ppo_step_{actual_steps:09d}"
        model.save(str(base_path))
        checkpoints.append((str(base_path.with_suffix(".zip")), actual_steps))
    env.close()
    return checkpoints


def _load_ppo(checkpoint: str, *, device: str):
    from stable_baselines3 import PPO

    return PPO.load(checkpoint, device=device)


def _rollout_policy(model: Any, env: SingleAssetRiskTradingEnv) -> PolicyEvaluation:
    """Run one chronological split and retain the environment's own PnL path and trades."""
    observation, _ = env.reset()
    rewards: list[float] = []
    drawdowns: list[float] = []
    trace: list[dict[str, Any]] = []
    previous_equity = float(env.equity)
    terminated = False
    while not terminated:
        action, _ = model.predict(observation, deterministic=True)
        observation, reward, terminated, truncated, info = env.step(action)
        if truncated:
            raise RuntimeError("Risk trading evaluation does not support truncated episodes.")
        rewards.append(float(reward))
        drawdowns.append(float(info["drawdown"]))
        equity = float(info["equity"])
        net_return = float(equity / previous_equity - 1.0)
        transaction_cost_return = float(info["transaction_cost"] / previous_equity)
        trace.append(
            {
                "timestamp": info["timestamp"],
                "decision_timestamp": info["decision_timestamp"],
                "action": int(info["action"]),
                "position": int(info["position"]),
                "position_leverage": float(info["position_leverage"]),
                "reward": float(reward),
                "equity": equity,
                "net_return": net_return,
                "transaction_cost_return": transaction_cost_return,
                "drawdown": float(info["drawdown"]),
            }
        )
        previous_equity = equity
    metrics = PolicyMetrics(
        cumulative_reward=float(np.sum(rewards, dtype=float)),
        max_drawdown=float(max(drawdowns, default=0.0)),
        total_return=float(env.equity / env.trade_config.initial_equity - 1.0),
        final_equity=float(env.equity),
        trade_count=int(len(env.trades)),
        evaluation_steps=int(len(rewards)),
    )
    trades = tuple(dict(trade) for trade in env.trades)
    env.close()
    return PolicyEvaluation(metrics=metrics, trades=trades, trace=tuple(trace))


def _fold_boundary_payload(
    *,
    fold: SlidingWindowFold,
    index: pd.Index,
    warmup_rows_trimmed: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = fold.to_dict()
    payload.update(
        {
            "warmup_rows_trimmed": int(warmup_rows_trimmed),
            "train_start_time": index[fold.train_start],
            "train_end_time": index[fold.train_end - 1],
            "validation_start_time": index[fold.validation_start],
            "validation_end_time": index[fold.validation_end - 1],
            "test_start_time": index[fold.test_start],
            "test_end_time": index[fold.test_end - 1],
            "interval_semantics": "integer boundaries are half-open [start, end)",
        }
    )
    return payload


def train_ppo_risk_agent(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, object | None, dict[str, Any]]:
    """Train leakage-safe fixed-window PPO folds and return environment-native OOS results.

    Each fold fits normalization on its fixed training window only, trains PPO only on that
    window, scores checkpoints on train-tail and validation, and touches test only after a
    checkpoint has been selected. The consistency gate runs after every held-out fold. The
    selected model from the last fold is returned as champion only when that gate passes.

    YAML declaration::

        model:
          kind: ppo_risk_agent
          feature_cols: [close_ret, atr_over_close]
          split:
            method: walk_forward
            train_size: 1000
            validation_size: 200
            test_size: 200
            expanding: false
          env:
            execution_lag_bars: 1
            atr_column: atr_14
            max_leverage: 3.0

    Required input columns
    ----------------------
    All configured ``model.feature_cols`` plus open, high, low, close, and the configured ATR
    execution column. Feature values must be finite after the leading causal warmup.

    Parameters
    ----------
    df:
        Chronologically ordered feature and execution frame for one asset.
    model_cfg:
        Resolved PPO risk model, environment, split, and runtime configuration.
    returns_col:
        Compatibility argument retained by the model registry; environment PnL is authoritative.
    """
    del returns_col
    model_cfg = dict(model_cfg or {})
    params = dict(model_cfg.get("params", {}) or {})
    env_cfg = dict(model_cfg.get("env", {}) or {})
    split_cfg = dict(model_cfg.get("split", {}) or {})
    runtime_cfg = dict(model_cfg.get("runtime", {}) or {})

    feature_columns = tuple(str(column) for column in (model_cfg.get("feature_cols") or ()))
    if not feature_columns:
        raise ValueError("ppo_risk_agent requires explicit model.feature_cols.")
    atr_column = str(env_cfg.get("atr_column", "atr_14"))
    execution_columns = (
        str(env_cfg.get("open_column", "open")),
        str(env_cfg.get("high_column", "high")),
        str(env_cfg.get("low_column", "low")),
        str(env_cfg.get("close_column", "close")),
        atr_column,
    )
    frame, warmup_rows_trimmed = _trim_causal_warmup(
        df,
        feature_columns=feature_columns,
        execution_columns=execution_columns,
    )
    feature_values = frame.loc[:, feature_columns].to_numpy(dtype=np.float32, copy=True)
    lookback_window = int(env_cfg.get("lookback_window", env_cfg.get("window_size", 1)))
    if lookback_window <= 0:
        raise ValueError("model.env.lookback_window must be > 0.")
    trade_config = RiskTradeConfig.from_mapping(env_cfg)
    reward_config = RiskRewardConfig.from_mapping(env_cfg.get("reward"))

    if split_cfg.get("method", "walk_forward") != "walk_forward":
        raise ValueError("ppo_risk_agent requires model.split.method='walk_forward'.")
    if bool(split_cfg.get("expanding", False)):
        raise ValueError("ppo_risk_agent requires a sliding fixed-size train window (expanding=false).")
    train_size = int(split_cfg["train_size"])
    validation_size = int(split_cfg["validation_size"])
    test_size = int(split_cfg["test_size"])
    train_tail_size = int(split_cfg.get("train_tail_size", validation_size))
    if train_tail_size <= 0 or train_tail_size > train_size:
        raise ValueError("model.split.train_tail_size must be in [1, train_size].")
    if train_size <= lookback_window:
        raise ValueError("model.split.train_size must exceed model.env.lookback_window.")
    folds = build_sliding_window_folds(
        n_samples=len(frame),
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step_size=(int(split_cfg["step_size"]) if split_cfg.get("step_size") is not None else None),
        max_folds=(int(split_cfg["max_folds"]) if split_cfg.get("max_folds") is not None else None),
    )

    run_name = str(params.get("run_name", "ppo_risk_agent"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_root = (
        Path(str(params.get("artifact_dir", "logs/rl"))).resolve()
        / f"{run_name}_{timestamp}_{uuid4().hex[:8]}"
    )
    seed = int(runtime_cfg.get("seed", 7))
    checkpoint_drawdown_penalty = float(params.get("checkpoint_drawdown_penalty", 0.0))
    device = str(params.get("device", "cpu"))

    signal_col = str(model_cfg.get("signal_col") or "signal_rl")
    action_col = str(model_cfg.get("action_col") or "action_rl")
    pred_is_oos_col = str(model_cfg.get("pred_is_oos_col") or "pred_is_oos")
    out = df.copy()
    out[signal_col] = pd.Series(np.nan, index=out.index, dtype="float32")
    out[action_col] = pd.Series(np.nan, index=out.index, dtype="float32")
    out[pred_is_oos_col] = False
    for column in _RL_PERFORMANCE_COLUMNS.values():
        out[column] = pd.Series(np.nan, index=out.index, dtype="float64")

    fold_records: list[dict[str, Any]] = []
    selected_checkpoint_paths: list[str] = []
    test_returns: list[float] = []

    for fold in folds:
        fold_dir = artifact_root / f"fold_{fold.fold:03d}"
        train_values = feature_values[fold.train_start : fold.train_end]
        normalizer_mean, normalizer_std = _fit_train_normalizer(train_values)
        normalized_values = _apply_normalizer(
            feature_values,
            mean=normalizer_mean,
            std=normalizer_std,
        )
        normalized_frame = frame.copy()
        normalized_frame.loc[:, feature_columns] = normalized_values

        train_env = _make_env(
            frame=normalized_frame,
            feature_columns=feature_columns,
            atr_column=atr_column,
            lookback_window=lookback_window,
            trade_config=trade_config,
            reward_config=reward_config,
            start_step=fold.train_start + lookback_window - 1,
            end_step=fold.train_end - 1,
            env_cfg=env_cfg,
        )
        checkpoints = _train_ppo_checkpoints(
            env=train_env,
            params=params,
            seed=seed + fold.fold,
            checkpoint_dir=fold_dir / "checkpoints",
        )

        # start_step is an observation close; the first scored bar is its next-open execution.
        train_tail_execution_start = max(
            fold.train_start + lookback_window,
            fold.train_end - train_tail_size,
        )
        split_ranges = {
            "train_tail": (train_tail_execution_start - 1, fold.train_end - 1),
            "validation": (fold.validation_start - 1, fold.validation_end - 1),
            "test": (fold.test_start - 1, fold.test_end - 1),
        }

        def evaluator(checkpoint: str, split_name: str) -> PolicyEvaluation:
            if split_name not in split_ranges:
                raise ValueError(f"Unsupported checkpoint evaluation split: {split_name}")
            split_start, split_end = split_ranges[split_name]
            model = _load_ppo(checkpoint, device=device)
            evaluation_env = _make_env(
                frame=normalized_frame,
                feature_columns=feature_columns,
                atr_column=atr_column,
                lookback_window=lookback_window,
                trade_config=trade_config,
                reward_config=reward_config,
                start_step=split_start,
                end_step=split_end,
                env_cfg=env_cfg,
            )
            return _rollout_policy(model, evaluation_env)

        selected = evaluate_checkpoints_then_test(
            checkpoints=checkpoints,
            evaluator=evaluator,
            drawdown_penalty=checkpoint_drawdown_penalty,
        )
        selection = selected.selection
        selected_checkpoint_paths.append(selection.checkpoint)
        test_returns.append(float(selected.test.metrics.total_return))

        test_trace = list(selected.test.trace)
        for row in test_trace:
            timestamp_value = row["timestamp"]
            out.loc[timestamp_value, signal_col] = float(row["position"])
            out.loc[timestamp_value, action_col] = float(row["action"])
            out.loc[timestamp_value, _RL_PERFORMANCE_COLUMNS["net_return"]] = float(row["net_return"])
            out.loc[timestamp_value, _RL_PERFORMANCE_COLUMNS["equity"]] = float(row["equity"])
            out.loc[timestamp_value, _RL_PERFORMANCE_COLUMNS["reward"]] = float(row["reward"])
            out.loc[timestamp_value, _RL_PERFORMANCE_COLUMNS["drawdown"]] = float(row["drawdown"])
            out.loc[timestamp_value, _RL_PERFORMANCE_COLUMNS["position_leverage"]] = float(
                row["position_leverage"]
            )
            out.loc[timestamp_value, _RL_PERFORMANCE_COLUMNS["transaction_cost_return"]] = float(
                row["transaction_cost_return"]
            )
            out.loc[timestamp_value, _RL_PERFORMANCE_COLUMNS["fold"]] = float(fold.fold)
        out.loc[frame.index[fold.test_start : fold.test_end], pred_is_oos_col] = True

        boundaries = _fold_boundary_payload(
            fold=fold,
            index=frame.index,
            warmup_rows_trimmed=warmup_rows_trimmed,
        )
        fold_record = {
            "fold": int(fold.fold),
            "split_boundaries": boundaries,
            "normalization": {
                "fit_split": "train",
                "fit_start": int(fold.train_start),
                "fit_end": int(fold.train_end),
                "feature_columns": list(feature_columns),
                "mean": normalizer_mean.tolist(),
                "std": normalizer_std.tolist(),
            },
            "selected_checkpoint": selection.checkpoint,
            "checkpoint_step": int(selection.step),
            "checkpoint_score": float(selection.checkpoint_score),
            "checkpoint_score_basis": (
                "min(train_tail, validation) where split score is "
                "mean_reward_per_step - checkpoint_drawdown_penalty * max_drawdown"
            ),
            "train_tail_score": float(selection.train_tail_score),
            "validation_score": float(selection.validation_score),
            "train_tail_metrics": selection.train_tail_metrics.to_dict(),
            "validation_metrics": selection.validation_metrics.to_dict(),
            "test_metrics": selected.test.metrics.to_dict(),
            "trades": list(selected.test.trades),
            "consistency_gate": None,
        }
        fold_records.append(fold_record)
        _write_json(fold_dir / "split_boundaries.json", boundaries)
        _write_json(fold_dir / "trades.json", {"trades": list(selected.test.trades)})
        _write_json(fold_dir / "result.json", fold_record)

    gate_cfg = dict(env_cfg.get("consistency_gate", {}) or {})
    gate = evaluate_consistency_gate(
        test_returns=test_returns,
        minimum_profitable_fold_ratio=float(gate_cfg.get("minimum_profitable_fold_ratio", 0.5)),
        minimum_median_test_return=float(gate_cfg.get("minimum_median_test_return", 0.0)),
        last_fold_checkpoint=selected_checkpoint_paths[-1],
    )
    gate_payload = gate.to_dict()
    for fold_record in fold_records:
        fold_record["consistency_gate"] = gate_payload
        _write_json(artifact_root / f"fold_{int(fold_record['fold']):03d}" / "result.json", fold_record)
    _write_json(artifact_root / "consistency_gate.json", gate_payload)
    _write_json(
        artifact_root / "run_summary.json",
        {
            "model_kind": "ppo_risk_agent",
            "artifact_root": artifact_root,
            "feature_columns": list(feature_columns),
            "folds": fold_records,
            "consistency_gate": gate_payload,
            "checkpoint_score_basis": (
                "mean_reward_per_step - checkpoint_drawdown_penalty * max_drawdown"
            ),
        },
    )

    champion = _load_ppo(gate.champion_checkpoint, device=device) if gate.champion_checkpoint else None
    oos_rows = int(out[pred_is_oos_col].sum())
    signal_rows = int(out.loc[out[pred_is_oos_col], signal_col].notna().sum())
    total_test_reward = float(sum(float(record["test_metrics"]["cumulative_reward"]) for record in fold_records))
    total_test_steps = int(
        sum(int(record["test_metrics"]["evaluation_steps"]) for record in fold_records)
    )
    meta = {
        "model_kind": "ppo_risk_agent",
        "algorithm": "ppo",
        "feature_cols": list(feature_columns),
        "feature_columns": list(feature_columns),
        "signal_col": signal_col,
        "action_col": action_col,
        "pred_is_oos_col": pred_is_oos_col,
        "warmup_rows_trimmed": int(warmup_rows_trimmed),
        "folds": _json_safe(fold_records),
        "consistency_gate": gate_payload,
        "champion_checkpoint": gate.champion_checkpoint,
        "artifact_root": str(artifact_root),
        "performance_source": "rl_environment",
        "rl_environment_columns": dict(_RL_PERFORMANCE_COLUMNS),
        "test_rows": oos_rows,
        "prediction_diagnostics": {
            "oos_rows": oos_rows,
            "predicted_rows": signal_rows,
            "non_oos_prediction_rows": 0,
            "missing_oos_prediction_rows": int(oos_rows - signal_rows),
            "oos_prediction_coverage": float(signal_rows / max(oos_rows, 1)),
            "alignment_ok": True,
        },
        "oos_policy_summary": {
            "evaluation_rows": oos_rows,
            "signal_rows": signal_rows,
            "total_reward": total_test_reward,
            "mean_reward": float(total_test_reward / max(total_test_steps, 1)),
        },
        "checkpoint_selection_uses": ["train_tail", "validation"],
        "checkpoint_score_basis": (
            "mean_reward_per_step - checkpoint_drawdown_penalty * max_drawdown"
        ),
        "test_evaluation_order": "after_checkpoint_selection",
        "reporting_contract": (
            "RL environment equity, returns, exits, costs, and trades are authoritative; "
            "signal_rl is diagnostic output and must not be backtested again."
        ),
        "pipeline_params": {key: params[key] for key in sorted(_PIPELINE_PARAM_KEYS) if key in params},
    }
    return out, champion, meta


__all__ = ["train_ppo_risk_agent"]
