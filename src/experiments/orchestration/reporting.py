from __future__ import annotations

import inspect
import math
from typing import Any

import pandas as pd
import yaml

from src.backtesting.engine import BacktestResult
from src.evaluation.metrics import compute_backtest_metrics
from src.experiments.schemas import EvaluationPayload, MonitoringPayload
from src.monitoring.drift import compute_feature_drift
from src.portfolio import PortfolioPerformance


def _yaml_block(value: Any) -> str:
    return yaml.safe_dump(value, sort_keys=False).rstrip()


def _format_report_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        magnitude = abs(value)
        if magnitude == 0.0:
            return "0.0"
        if magnitude >= 1000 or magnitude < 1e-4:
            return f"{value:.3e}"
        return f"{value:.6f}"
    return str(value)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_None_\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_report_value(value) for value in row) + " |")
    return "\n".join(lines) + "\n"


def _stage_tail_markdown(stage_tails: dict[str, Any]) -> list[str]:
    stages = list(dict(stage_tails or {}).get("stages", []) or [])
    if not stages:
        return []

    lines: list[str] = ["## Stage Tail Trace"]
    for stage_payload in stages:
        lines.extend(
            [
                "",
                f"### {stage_payload.get('stage', 'stage')}",
                _markdown_table(
                    ["Metric", "Value"],
                    [
                        ["asset_count", stage_payload.get("asset_count")],
                        ["shown_asset_count", stage_payload.get("shown_asset_count")],
                        ["tail_limit", stage_payload.get("limit")],
                        ["max_columns", stage_payload.get("max_columns")],
                        ["max_assets", stage_payload.get("max_assets")],
                    ],
                ),
            ]
        )
        for asset_payload in list(stage_payload.get("assets", []) or []):
            lines.extend(
                [
                    f"#### Asset: {asset_payload.get('asset')}",
                    _markdown_table(
                        ["Metric", "Value"],
                        [
                            ["rows", asset_payload.get("rows")],
                            ["row_delta", asset_payload.get("row_delta")],
                            ["column_count", asset_payload.get("column_count")],
                            ["column_delta", asset_payload.get("column_delta")],
                            ["added_columns", ", ".join(list(asset_payload.get("added_columns", []) or []))],
                            ["removed_columns", ", ".join(list(asset_payload.get("removed_columns", []) or []))],
                            ["shown_columns", ", ".join(list(asset_payload.get("shown_columns", []) or []))],
                            ["truncated_columns", ", ".join(list(asset_payload.get("truncated_columns", []) or []))],
                        ],
                    ),
                ]
            )
            tail_rows = list(asset_payload.get("tail_rows", []) or [])
            if tail_rows:
                tail_df = pd.DataFrame(tail_rows)
                lines.extend(
                    [
                        "",
                        "```text",
                        tail_df.to_string(index=False),
                        "```",
                    ]
                )
            else:
                lines.append("_Empty tail._")
    return lines


def _dict_metric_rows(payload: dict[str, Any], *, prefix: str | None = None) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            for inner_key, inner_value in value.items():
                rows.append([f"{key}.{inner_key}" if prefix is None else f"{prefix}{key}.{inner_key}", inner_value])
        elif not isinstance(value, list):
            rows.append([key if prefix is None else f"{prefix}{key}", value])
    return rows


def _safe_meta_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _extract_drifted_features(monitoring: dict[str, Any], limit: int = 8) -> list[tuple[str, str, float]]:
    drifted: list[tuple[str, str, float]] = []
    for asset, asset_report in sorted(dict(monitoring.get("per_asset", {}) or {}).items()):
        per_feature = dict(asset_report.get("per_feature", {}) or {})
        for feature, details in per_feature.items():
            if bool(details.get("is_drifted", False)):
                drifted.append((asset, feature, float(details.get("psi", 0.0))))
    drifted.sort(key=lambda item: abs(item[2]), reverse=True)
    return drifted[:limit]


def _interface_ref(obj: Any) -> str:
    module = getattr(obj, "__module__", type(obj).__module__)
    qualname = getattr(obj, "__qualname__", getattr(obj, "__name__", type(obj).__name__))
    return f"{module}.{qualname}"


def _interface_signature(obj: Any) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "(...)"


def _interface_line(label: str, obj: Any, *, note: str | None = None) -> str:
    line = f"- `{label}` -> `{_interface_ref(obj)}{_interface_signature(obj)}`"
    if note:
        line += f"  \n  {note}"
    return line


def _resolved_reward_snapshot(cfg: dict[str, Any]) -> dict[str, Any]:
    env_cfg = dict(cfg.get("model", {}).get("env", {}) or {})
    reward_cfg = dict(env_cfg.get("reward", {}) or {})
    risk_cfg = dict(cfg.get("risk", {}) or {})
    return {
        "cost_per_turnover": reward_cfg.get("cost_per_turnover", risk_cfg.get("cost_per_turnover", 0.0)),
        "slippage_per_turnover": reward_cfg.get("slippage_per_turnover", risk_cfg.get("slippage_per_turnover", 0.0)),
        "inventory_penalty": reward_cfg.get("inventory_penalty", 0.0),
        "drawdown_penalty": reward_cfg.get("drawdown_penalty", 0.0),
        "switching_penalty": reward_cfg.get("switching_penalty", 0.0),
    }


def _resolved_execution_snapshot(cfg: dict[str, Any]) -> dict[str, Any]:
    env_cfg = dict(cfg.get("model", {}).get("env", {}) or {})
    dd_cfg = dict(cfg.get("risk", {}).get("dd_guard", {}) or {})
    return {
        "min_holding_bars": env_cfg.get("min_holding_bars", 0),
        "action_hysteresis": env_cfg.get("action_hysteresis", 0.0),
        "dd_guard_enabled": dd_cfg.get("enabled", False),
        "max_drawdown": dd_cfg.get("max_drawdown", 0.2),
        "cooloff_bars": dd_cfg.get("cooloff_bars", 20),
    }


def _build_pipeline_trace_markdown(
    *,
    cfg: dict[str, Any],
    summary_payload: dict[str, Any],
) -> str:
    from src.backtesting.engine import BacktestResult, run_backtest
    from src.experiments.contracts import validate_data_contract
    from src.models.runtime import resolve_runtime_for_model
    from src.experiments.orchestration.artifacts import save_artifacts, write_experiment_report_from_run_dir
    from src.experiments.orchestration.backtest_stage import run_portfolio_backtest, run_single_asset_backtest
    from src.experiments.orchestration.data_stage import load_asset_frames, save_processed_snapshot_if_enabled
    from src.experiments.orchestration.execution_stage import build_execution_output
    from src.experiments.orchestration.feature_stage import (
        apply_feature_steps,
        apply_signal_step,
        apply_signals_to_assets,
        apply_steps_to_assets,
    )
    from src.experiments.orchestration.model_stage import apply_model_step, apply_model_to_assets
    from src.experiments.orchestration.pipeline import run_experiment_pipeline
    from src.experiments.registry import get_feature_fn, get_model_fn, get_signal_fn
    from src.experiments.runner import _load_asset_frames, run_experiment
    from src.experiments.schemas import EvaluationPayload, ExecutionPayload, MonitoringPayload, StorageContext
    from src.models.rl.envs import PortfolioTradingEnv, RLExecutionConfig, RLRewardConfig, SingleAssetTradingEnv
    from src.models.rl.sb3 import train_sb3_model
    from src.portfolio.construction import PortfolioPerformance, compute_portfolio_performance
    from src.src_data.loaders import load_ohlcv, load_ohlcv_panel
    from src.src_data.pit import apply_pit_hardening
    from src.src_data.validation import validate_ohlcv

    data_cfg = dict(cfg.get("data", {}) or {})
    model_cfg = dict(cfg.get("model", {}) or {})
    signals_cfg = dict(cfg.get("signals", {}) or {})
    risk_cfg = dict(cfg.get("risk", {}) or {})
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    portfolio_cfg = dict(cfg.get("portfolio", {}) or {})
    monitoring_cfg = dict(cfg.get("monitoring", {}) or {})
    execution_cfg = dict(cfg.get("execution", {}) or {})
    model_kind = str(model_cfg.get("kind", "none"))
    is_portfolio = bool(portfolio_cfg.get("enabled", False))
    resolved_features = summary_payload.get("resolved_feature_columns", []) or []

    lines: list[str] = ["## Pipeline Trace", ""]

    lines.extend(
        [
            "### 1. Entry Point",
            _interface_line("runner.run_experiment", run_experiment),
            _interface_line("runner._load_asset_frames", _load_asset_frames),
            _interface_line("pipeline.run_experiment_pipeline", run_experiment_pipeline),
            "",
            "```yaml",
            _yaml_block({"config_path": cfg.get("config_path", ""), "runtime": cfg.get("runtime", {})}),
            "```",
            "",
        ]
    )

    lines.extend(
        [
            "### 2. Data Load And PIT",
            _interface_line("data_stage.load_asset_frames", load_asset_frames),
            _interface_line("src_data.loaders.load_ohlcv", load_ohlcv),
            _interface_line("src_data.loaders.load_ohlcv_panel", load_ohlcv_panel),
            _interface_line("src_data.pit.apply_pit_hardening", apply_pit_hardening),
            _interface_line("src_data.validation.validate_ohlcv", validate_ohlcv),
            _interface_line("experiments.contracts.validate_data_contract", validate_data_contract),
            _interface_line("schemas.StorageContext", StorageContext, note="Context object persisted into snapshot metadata."),
            _interface_line("data_stage.save_processed_snapshot_if_enabled", save_processed_snapshot_if_enabled),
            "",
            "```yaml",
            _yaml_block({"data": data_cfg}),
            "```",
            "",
        ]
    )

    feature_steps = list(cfg.get("features", []) or [])
    lines.extend(
        [
            "### 3. Feature Engineering",
            _interface_line("feature_stage.apply_steps_to_assets", apply_steps_to_assets),
            _interface_line("feature_stage.apply_feature_steps", apply_feature_steps),
        ]
    )
    for step in feature_steps:
        name = str(step.get("step", "unknown"))
        params = dict(step.get("params", {}) or {})
        try:
            fn = get_feature_fn(name)
            lines.append(_interface_line(f"feature[{name}]", fn, note=f"params={params}"))
        except KeyError:
            lines.append(f"- `feature[{name}]` -> unresolved registry entry")
    lines.extend(
        [
            "",
            "```yaml",
            _yaml_block({"features": feature_steps, "resolved_feature_columns": resolved_features}),
            "```",
            "",
        ]
    )

    lines.extend(
        [
            "### 4. Model And Training",
            _interface_line("model_stage.apply_model_to_assets", apply_model_to_assets),
            _interface_line("feature_stage.apply_model_step", apply_model_step),
        ]
    )
    if model_kind != "none":
        model_fn = get_model_fn(model_kind)
        lines.append(_interface_line(f"model[{model_kind}]", model_fn))
    lines.append(_interface_line("modeling.runtime.resolve_runtime_for_model", resolve_runtime_for_model))
    if model_kind in {"ppo_agent", "dqn_agent", "ppo_portfolio_agent", "dqn_portfolio_agent"}:
        env_cls = PortfolioTradingEnv if model_kind in {"ppo_portfolio_agent", "dqn_portfolio_agent"} else SingleAssetTradingEnv
        lines.extend(
            [
                _interface_line("models.rl.envs.RLRewardConfig", RLRewardConfig),
                _interface_line("models.rl.envs.RLExecutionConfig", RLExecutionConfig),
                _interface_line(f"models.rl.envs.{env_cls.__name__}", env_cls),
                _interface_line("models.rl.sb3.train_sb3_model", train_sb3_model),
            ]
        )
    lines.extend(
        [
            "",
            "```yaml",
            _yaml_block(
                {
                    "model": model_cfg,
                    "resolved_reward_config": _resolved_reward_snapshot(cfg),
                    "resolved_execution_config": _resolved_execution_snapshot(cfg),
                }
            ),
            "```",
            "",
        ]
    )

    lines.extend(
        [
            "### 5. Signal Stage",
            _interface_line("feature_stage.apply_signals_to_assets", apply_signals_to_assets),
            _interface_line("feature_stage.apply_signal_step", apply_signal_step),
        ]
    )
    signal_kind = str(signals_cfg.get("kind", "none"))
    if signal_kind != "none":
        try:
            signal_fn = get_signal_fn(signal_kind)
            lines.append(_interface_line(f"signal[{signal_kind}]", signal_fn, note=f"params={dict(signals_cfg.get('params', {}) or {})}"))
        except KeyError:
            lines.append(f"- `signal[{signal_kind}]` -> unresolved registry entry")
    else:
        lines.append("- `signals.kind=none` -> model-emitted signal path is used directly.")
    lines.extend(
        [
            "",
            "```yaml",
            _yaml_block({"signals": signals_cfg}),
            "```",
            "",
        ]
    )

    lines.extend(
        [
            "### 6. Backtest",
            _interface_line(
                "backtest_stage.run_portfolio_backtest" if is_portfolio else "backtest_stage.run_single_asset_backtest",
                run_portfolio_backtest if is_portfolio else run_single_asset_backtest,
            ),
            _interface_line(
                "portfolio.construction.compute_portfolio_performance" if is_portfolio else "backtesting.engine.run_backtest",
                compute_portfolio_performance if is_portfolio else run_backtest,
            ),
            _interface_line(
                "portfolio.construction.PortfolioPerformance" if is_portfolio else "backtesting.engine.BacktestResult",
                PortfolioPerformance if is_portfolio else BacktestResult,
            ),
            "",
            "```yaml",
            _yaml_block({"backtest": backtest_cfg, "risk": risk_cfg, "portfolio": portfolio_cfg}),
            "```",
            "",
        ]
    )

    lines.extend(
        [
            "### 7. Monitoring And Execution",
            _interface_line("reporting.compute_monitoring_report", compute_monitoring_report),
            _interface_line("execution_stage.build_execution_output", build_execution_output),
            _interface_line("schemas.MonitoringPayload", MonitoringPayload),
            _interface_line("schemas.ExecutionPayload", ExecutionPayload),
            _interface_line(
                "reporting.build_portfolio_evaluation" if is_portfolio else "reporting.build_single_asset_evaluation",
                build_portfolio_evaluation if is_portfolio else build_single_asset_evaluation,
            ),
            _interface_line("schemas.EvaluationPayload", EvaluationPayload),
            "",
            "```yaml",
            _yaml_block({"monitoring": monitoring_cfg, "execution": execution_cfg}),
            "```",
            "",
        ]
    )

    lines.extend(
        [
            "### 8. Artifact And Report",
            _interface_line("artifacts.save_artifacts", save_artifacts),
            _interface_line("artifacts.write_experiment_report_from_run_dir", write_experiment_report_from_run_dir),
            _interface_line("reporting.build_experiment_report_markdown", build_experiment_report_markdown),
            "",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def build_experiment_diagnostics(
    *,
    cfg: dict[str, Any],
    summary_payload: dict[str, Any],
    run_metadata: dict[str, Any],
) -> list[str]:
    diagnostics: list[str] = []
    primary = dict(summary_payload.get("summary", {}) or {})
    evaluation = dict(summary_payload.get("evaluation", {}) or {})
    monitoring = dict(summary_payload.get("monitoring", {}) or {})
    policy_summary = dict(evaluation.get("model_oos_policy_summary", {}) or {})

    gross_pnl = float(primary.get("gross_pnl", 0.0) or 0.0)
    net_pnl = float(primary.get("net_pnl", 0.0) or 0.0)
    total_cost = float(primary.get("total_cost", 0.0) or 0.0)
    avg_turnover = float(primary.get("avg_turnover", 0.0) or 0.0)
    hit_rate = primary.get("hit_rate")

    if gross_pnl <= 0:
        diagnostics.append(
            "Gross PnL is non-positive, so the dominant problem is missing edge rather than execution drag."
        )
    elif net_pnl <= 0 and total_cost > gross_pnl:
        diagnostics.append(
            "Costs exceed the available gross edge; the next improvement must come from lower turnover or stronger abstention."
        )

    if isinstance(hit_rate, (int, float)) and abs(float(hit_rate) - 0.5) <= 0.03 and gross_pnl <= 0:
        diagnostics.append(
            "Hit rate is close to coin-flip while gross PnL is negative, which is consistent with weak or noisy signal quality."
        )

    if avg_turnover >= 0.10:
        diagnostics.append("Average turnover is still high relative to the available edge; the policy is likely over-reactive.")
    elif avg_turnover <= 0.01 and gross_pnl <= 0:
        diagnostics.append(
            "Turnover is already low, so more cost tuning alone is unlikely to rescue the run."
        )

    env_cfg = dict(cfg.get("model", {}).get("env", {}) or {})
    max_signal_abs = float(env_cfg.get("max_signal_abs", 1.0) or 1.0)
    mean_abs_signal = float(policy_summary.get("mean_abs_signal", 0.0) or 0.0)
    flat_rate = float(policy_summary.get("flat_rate", 0.0) or 0.0)
    if max_signal_abs > 0 and mean_abs_signal / max_signal_abs >= 0.85:
        diagnostics.append(
            "The policy spends most of its time near the configured signal cap, so it is saturating instead of sizing dynamically."
        )
    if flat_rate <= 0.001:
        diagnostics.append(
            "The policy never meaningfully abstains; it chooses direction almost all the time instead of learning a true hold state."
        )

    fold_summaries = list(evaluation.get("fold_backtest_summaries", []) or [])
    positive_folds = 0
    negative_folds = 0
    for fold in fold_summaries:
        metrics = dict(fold.get("metrics", {}) or {})
        fold_net = float(metrics.get("net_pnl", 0.0) or 0.0)
        positive_folds += int(fold_net > 0)
        negative_folds += int(fold_net < 0)
    if positive_folds > 0 and negative_folds > 0:
        diagnostics.append(
            "Fold outcomes are mixed, which points to regime dependence rather than a stable cross-period edge."
        )

    model_meta = dict(run_metadata.get("model_meta", {}) or {})
    policy_by_fold = {
        int(fold.get("fold", -1)): dict(fold.get("policy_metrics", {}) or {})
        for fold in list(model_meta.get("folds", []) or [])
    }
    reward_mismatch = False
    for fold in fold_summaries:
        fold_id = int(fold.get("fold", -1))
        backtest_metrics = dict(fold.get("metrics", {}) or {})
        policy_metrics = policy_by_fold.get(fold_id, {})
        if float(backtest_metrics.get("net_pnl", 0.0) or 0.0) > 0 and float(policy_metrics.get("mean_reward", 0.0) or 0.0) < 0:
            reward_mismatch = True
            break
    if reward_mismatch:
        diagnostics.append(
            "At least one fold has positive backtest PnL but negative RL reward, which suggests the training reward is misaligned with the evaluation objective."
        )

    drifted = _extract_drifted_features(monitoring, limit=5)
    if drifted:
        diagnostics.append(
            "Feature drift is present in OOS inputs; the largest drifted features are "
            + ", ".join(feature for _, feature, _ in drifted)
            + "."
        )

    if not diagnostics:
        diagnostics.append("No single dominant pathology stood out from the generated artifacts.")
    return diagnostics


def build_experiment_report_markdown(
    *,
    cfg: dict[str, Any],
    summary_payload: dict[str, Any],
    run_metadata: dict[str, Any],
    chart_paths: dict[str, str],
    artifact_paths: dict[str, str],
) -> str:
    primary = dict(summary_payload.get("summary", {}) or {})
    evaluation = dict(summary_payload.get("evaluation", {}) or {})
    monitoring = dict(summary_payload.get("monitoring", {}) or {})
    model_meta = dict(run_metadata.get("model_meta", {}) or {})
    data_cfg = dict(cfg.get("data", {}) or {})
    model_cfg = dict(cfg.get("model", {}) or {})
    runtime_cfg = dict(cfg.get("runtime", {}) or {})
    data_stats = dict(summary_payload.get("data_stats", {}) or {})
    policy_summary = dict(evaluation.get("model_oos_policy_summary", {}) or {})
    resolved_features = summary_payload.get("resolved_feature_columns", []) or []
    stage_tails = dict(summary_payload.get("stage_tails", {}) or {})

    symbols = data_cfg.get("symbols") or ([data_cfg.get("symbol")] if data_cfg.get("symbol") else [])
    run_name = str(cfg.get("logging", {}).get("run_name", cfg.get("config_path", "experiment")))
    lines: list[str] = [
        f"# Experiment Report: {run_name}",
        "",
        "## Overview",
        f"- Config path: `{cfg.get('config_path', '')}`",
        f"- Model kind: `{model_cfg.get('kind', 'none')}`",
        f"- Symbols: `{', '.join(str(symbol) for symbol in symbols) if symbols else 'n/a'}`",
        f"- Data source: `{data_cfg.get('source', 'n/a')}` at interval `{data_cfg.get('interval', 'n/a')}`",
        f"- Data window: `{data_cfg.get('start', 'n/a')}` to `{data_stats.get('end', data_cfg.get('end', 'latest'))}`",
        f"- Rows / columns: `{data_stats.get('rows', 'n/a')}` rows, `{data_stats.get('columns', 'n/a')}` columns",
        f"- Target: `{model_cfg.get('target', {}).get('kind', 'n/a')}` horizon `{model_cfg.get('target', {}).get('horizon', 'n/a')}`",
        f"- Feature count: `{model_meta.get('contracts', {}).get('n_features', len(summary_payload.get('resolved_feature_columns', []) or []))}`",
        f"- Runtime seed: `{runtime_cfg.get('seed', 'n/a')}`",
        "",
        _build_pipeline_trace_markdown(cfg=cfg, summary_payload=summary_payload).rstrip(),
        "",
        "## Primary Summary",
        _markdown_table(["Metric", "Value"], [[key, value] for key, value in primary.items()]),
    ]

    stage_tail_lines = _stage_tail_markdown(stage_tails)
    if stage_tail_lines:
        lines.extend(["", *stage_tail_lines])

    if policy_summary:
        lines.extend(
            [
                "## OOS Policy Summary",
                _markdown_table(["Metric", "Value"], [[key, value] for key, value in policy_summary.items()]),
            ]
        )

    model_summary_rows: list[list[Any]] = []
    for label, payload in (
        ("classification", _safe_meta_dict(evaluation.get("model_oos_summary"))),
        ("regression", _safe_meta_dict(evaluation.get("model_oos_regression_summary"))),
        ("volatility", _safe_meta_dict(evaluation.get("model_oos_volatility_summary"))),
    ):
        model_summary_rows.extend(_dict_metric_rows(payload, prefix=f"{label}."))
    if model_summary_rows:
        lines.extend(
            [
                "",
                "## Model OOS Diagnostics",
                _markdown_table(["Metric", "Value"], model_summary_rows),
            ]
        )

    prediction_diagnostics = _safe_meta_dict(model_meta.get("prediction_diagnostics"))
    if prediction_diagnostics:
        lines.extend(
            [
                "",
                "## Prediction Diagnostics",
                _markdown_table(["Metric", "Value"], _dict_metric_rows(prediction_diagnostics)),
            ]
        )

    missing_value_diagnostics = _safe_meta_dict(model_meta.get("missing_value_diagnostics"))
    if missing_value_diagnostics:
        lines.extend(
            [
                "",
                "## Missing-Value Diagnostics",
                _markdown_table(["Metric", "Value"], _dict_metric_rows(missing_value_diagnostics)),
            ]
        )

    label_distribution = _safe_meta_dict(model_meta.get("label_distribution"))
    if label_distribution:
        label_rows: list[list[Any]] = []
        for label, payload in sorted(label_distribution.items()):
            label_rows.extend(_dict_metric_rows(_safe_meta_dict(payload), prefix=f"{label}."))
        if label_rows:
            lines.extend(
                [
                    "",
                    "## Label Distribution",
                    _markdown_table(["Metric", "Value"], label_rows),
                ]
            )

    target_distribution = _safe_meta_dict(model_meta.get("target_distribution"))
    if target_distribution:
        distribution_rows: list[list[Any]] = []
        for label, payload in sorted(target_distribution.items()):
            if label == "folds":
                continue
            distribution_rows.extend(_dict_metric_rows(_safe_meta_dict(payload), prefix=f"{label}."))
        if distribution_rows:
            lines.extend(
                [
                    "",
                    "## Target Distribution",
                    _markdown_table(["Metric", "Value"], distribution_rows),
                ]
            )

    feature_importance = _safe_meta_dict(model_meta.get("feature_importance"))
    top_features = list(feature_importance.get("top_features", []) or [])
    if top_features:
        lines.extend(
            [
                "",
                "## Feature Importance",
                _markdown_table(
                    ["Rank", "Feature", "Mean Importance", "Mean Importance Normalized", "Fold Count", "Source"],
                    [
                        [
                            row.get("rank"),
                            row.get("feature"),
                            row.get("mean_importance", row.get("importance")),
                            row.get("mean_importance_normalized", row.get("importance_normalized")),
                            row.get("fold_count"),
                            row.get("source"),
                        ]
                        for row in top_features
                    ],
                ),
            ]
        )

    exposure_rows = [
        ["gross_pnl", primary.get("gross_pnl")],
        ["net_pnl", primary.get("net_pnl")],
        ["total_cost", primary.get("total_cost")],
        ["cost_drag", primary.get("cost_drag")],
        ["cost_to_gross_pnl", primary.get("cost_to_gross_pnl")],
        ["avg_turnover", primary.get("avg_turnover")],
        ["total_turnover", primary.get("total_turnover")],
        ["mean_abs_signal", policy_summary.get("mean_abs_signal")],
        ["signal_turnover", policy_summary.get("signal_turnover")],
        ["flat_rate", policy_summary.get("flat_rate")],
    ]
    lines.extend(
        [
            "",
            "## Cost / Exposure / Turnover",
            _markdown_table(["Metric", "Value"], exposure_rows),
        ]
    )

    lines.extend(
        [
        "## Diagnostics",
        ]
    )
    for item in build_experiment_diagnostics(cfg=cfg, summary_payload=summary_payload, run_metadata=run_metadata):
        lines.append(f"- {item}")

    if chart_paths:
        lines.extend(["", "## Charts"])
        for label, rel_path in chart_paths.items():
            title = label.replace("_", " ").title()
            lines.extend([f"### {title}", f"![{title}]({rel_path})", ""])

    fold_summaries = list(evaluation.get("fold_backtest_summaries", []) or [])
    if fold_summaries:
        policy_by_fold = {
            int(fold.get("fold", -1)): dict(fold.get("policy_metrics", {}) or {})
            for fold in list(model_meta.get("folds", []) or [])
        }
        rows: list[list[Any]] = []
        for fold in fold_summaries:
            fold_id = int(fold.get("fold", -1))
            metrics = dict(fold.get("metrics", {}) or {})
            policy = policy_by_fold.get(fold_id, {})
            rows.append(
                [
                    fold_id,
                    fold.get("test_rows"),
                    metrics.get("gross_pnl"),
                    metrics.get("net_pnl"),
                    metrics.get("total_cost"),
                    metrics.get("sharpe"),
                    metrics.get("avg_turnover"),
                    policy.get("mean_reward"),
                    policy.get("mean_abs_signal"),
                    policy.get("signal_turnover"),
                    policy.get("flat_rate"),
                ]
            )
        lines.extend(
            [
                "",
                "## Fold Breakdown",
                _markdown_table(
                    [
                        "Fold",
                        "Rows",
                        "Gross PnL",
                        "Net PnL",
                        "Cost",
                        "Sharpe",
                        "Avg Turnover",
                        "Mean Reward",
                        "Mean Abs Signal",
                        "Signal Turnover",
                        "Flat Rate",
                    ],
                    rows,
                ),
            ]
        )

    model_folds = list(model_meta.get("folds", []) or [])
    if model_folds:
        model_fold_rows: list[list[Any]] = []
        for fold in model_folds:
            train_availability = _safe_meta_dict(fold.get("train_feature_availability"))
            test_availability = _safe_meta_dict(fold.get("test_feature_availability"))
            model_fold_rows.append(
                [
                    fold.get("fold"),
                    fold.get("train_rows_raw", fold.get("train_rows")),
                    fold.get("train_rows"),
                    fold.get("train_rows_dropped_missing", 0),
                    fold.get("test_rows"),
                    fold.get("test_pred_rows"),
                    fold.get("test_rows_missing_features", fold.get("test_rows_without_prediction", 0)),
                    train_availability.get("missing_rows"),
                    test_availability.get("missing_rows"),
                    _safe_meta_dict(fold.get("classification_metrics")).get("evaluation_rows")
                    or _safe_meta_dict(fold.get("regression_metrics")).get("evaluation_rows"),
                ]
            )
        lines.extend(
            [
                "",
                "## Model Fold Diagnostics",
                _markdown_table(
                    [
                        "Fold",
                        "Train Raw",
                        "Train Used",
                        "Train Missing Drop",
                        "Test Rows",
                        "Pred Rows",
                        "Test Missing / No Pred",
                        "Train Feature Missing",
                        "Test Feature Missing",
                        "Eval Rows",
                    ],
                    model_fold_rows,
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## Monitoring",
            f"- Drifted feature count: `{monitoring.get('drifted_feature_count', 0)}` / `{monitoring.get('feature_count', 0)}`",
        ]
    )
    drift_rows = [[asset, feature, psi] for asset, feature, psi in _extract_drifted_features(monitoring, limit=10)]
    if drift_rows:
        lines.append(_markdown_table(["Asset", "Feature", "PSI"], drift_rows))
    else:
        lines.append("_No drifted features were flagged._")

    lines.extend(
        [
            "",
            "## Feature Set",
            _markdown_table(
                ["Order", "Feature"],
                (
                    [
                        [idx + 1, feature]
                        for idx, feature in enumerate(resolved_features)
                    ]
                    if isinstance(resolved_features, list)
                    else [
                        [idx + 1, f"{asset}:{feature}"]
                        for idx, (asset, feature) in enumerate(
                            [
                                (str(asset), str(feature))
                                for asset, features in sorted(dict(resolved_features).items())
                                for feature in list(features or [])
                            ]
                        )
                    ]
                ),
            ),
            "## Feature Steps",
            "```yaml",
            yaml.safe_dump(summary_payload.get("config_features", []), sort_keys=False).rstrip(),
            "```",
            "",
            "## Config Snapshot",
            "```yaml",
            yaml.safe_dump(
                {
                    "data": cfg.get("data", {}),
                    "model": cfg.get("model", {}),
                    "signals": cfg.get("signals", {}),
                    "risk": cfg.get("risk", {}),
                    "backtest": cfg.get("backtest", {}),
                    "portfolio": cfg.get("portfolio", {}),
                    "runtime": cfg.get("runtime", {}),
                },
                sort_keys=False,
            ).rstrip(),
            "```",
            "",
            "## Artifact Inventory",
        ]
    )
    for key, path in artifact_paths.items():
        lines.append(f"- `{key}`: `{path}`")

    return "\n".join(lines).rstrip() + "\n"


def compute_subset_metrics(
    *,
    net_returns: pd.Series,
    turnover: pd.Series,
    costs: pd.Series,
    gross_returns: pd.Series,
    periods_per_year: int,
    mask: pd.Series,
) -> dict[str, float]:
    aligned_mask = mask.reindex(net_returns.index).fillna(False).astype(bool)
    if not bool(aligned_mask.any()):
        return {}
    return compute_backtest_metrics(
        net_returns=net_returns.loc[aligned_mask],
        periods_per_year=periods_per_year,
        turnover=turnover.loc[aligned_mask],
        costs=costs.loc[aligned_mask],
        gross_returns=gross_returns.loc[aligned_mask],
    )


def build_fold_backtest_summaries(
    *,
    source_index: pd.Index,
    net_returns: pd.Series,
    turnover: pd.Series,
    costs: pd.Series,
    gross_returns: pd.Series,
    periods_per_year: int,
    folds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fold in folds:
        start = int(fold["test_start"])
        end = int(fold["test_end"])
        fold_index = source_index[start:end]
        mask = pd.Series(net_returns.index.isin(fold_index), index=net_returns.index)
        summary = compute_subset_metrics(
            net_returns=net_returns,
            turnover=turnover,
            costs=costs,
            gross_returns=gross_returns,
            periods_per_year=periods_per_year,
            mask=mask,
        )
        out.append(
            {
                "fold": int(fold["fold"]),
                "test_rows": int(fold.get("test_rows", end - start)),
                "metrics": summary,
            }
        )
    return out


def build_single_asset_evaluation(
    asset: str,
    df: pd.DataFrame,
    *,
    performance: BacktestResult,
    model_meta: dict[str, Any],
    periods_per_year: int,
) -> dict[str, Any]:
    evaluation = EvaluationPayload(
        scope="timeline",
        primary_summary=dict(performance.summary),
        timeline_summary=dict(performance.summary),
    ).to_dict()

    if "pred_is_oos" not in df.columns:
        return evaluation

    oos_mask = df["pred_is_oos"].reindex(performance.returns.index).fillna(False).astype(bool)
    oos_summary = compute_subset_metrics(
        net_returns=performance.returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        mask=oos_mask,
    )
    fold_summaries = build_fold_backtest_summaries(
        source_index=df.index,
        net_returns=performance.returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        folds=list(model_meta.get("folds", []) or []),
    )

    return EvaluationPayload(
        scope="strict_oos_only",
        primary_summary=oos_summary or dict(performance.summary),
        timeline_summary=dict(performance.summary),
        oos_only_summary=oos_summary,
        extra={
            "oos_rows": int(oos_mask.sum()),
            "oos_coverage": float(oos_mask.mean()) if len(oos_mask) > 0 else 0.0,
            "fold_backtest_summaries": fold_summaries,
            "model_oos_summary": dict(model_meta.get("oos_classification_summary", {}) or {}),
            "model_oos_regression_summary": dict(model_meta.get("oos_regression_summary", {}) or {}),
            "model_oos_volatility_summary": dict(model_meta.get("oos_volatility_summary", {}) or {}),
            "model_oos_policy_summary": dict(model_meta.get("oos_policy_summary", {}) or {}),
            "asset": asset,
        },
    ).to_dict()


def build_portfolio_evaluation(
    asset_frames: dict[str, pd.DataFrame],
    *,
    performance: PortfolioPerformance,
    model_meta: dict[str, Any],
    periods_per_year: int,
    alignment: str,
) -> dict[str, Any]:
    evaluation = EvaluationPayload(
        scope="timeline",
        primary_summary=dict(performance.summary),
        timeline_summary=dict(performance.summary),
    ).to_dict()

    if not model_meta:
        return evaluation

    oos_by_asset: dict[str, pd.Series] = {}
    if "per_asset" in model_meta:
        for asset in sorted(model_meta["per_asset"]):
            frame = asset_frames.get(asset)
            if frame is not None and "pred_is_oos" in frame.columns:
                oos_by_asset[asset] = frame["pred_is_oos"].astype(float)
    elif "pred_is_oos" in next(iter(asset_frames.values())).columns:
        only_asset = next(iter(sorted(asset_frames)))
        oos_by_asset[only_asset] = asset_frames[only_asset]["pred_is_oos"].astype(float)

    if not oos_by_asset:
        return evaluation

    oos_df = pd.concat(oos_by_asset, axis=1, join=alignment).sort_index()
    if isinstance(oos_df.columns, pd.MultiIndex):
        oos_df.columns = oos_df.columns.get_level_values(0)
    oos_mask = oos_df.reindex(performance.net_returns.index).fillna(0.0).astype(bool).all(axis=1)
    oos_summary = compute_subset_metrics(
        net_returns=performance.net_returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        mask=oos_mask,
    )
    return EvaluationPayload(
        scope="strict_oos_only",
        primary_summary=oos_summary or dict(performance.summary),
        timeline_summary=dict(performance.summary),
        oos_only_summary=oos_summary,
        extra={
            "oos_active_dates": int(oos_mask.sum()),
            "oos_date_coverage": float(oos_mask.mean()) if len(oos_mask) > 0 else 0.0,
            "model_oos_summary": dict(model_meta.get("oos_classification_summary", {}) or {}),
            "model_oos_regression_summary": dict(model_meta.get("oos_regression_summary", {}) or {}),
            "model_oos_volatility_summary": dict(model_meta.get("oos_volatility_summary", {}) or {}),
            "model_oos_policy_summary": dict(model_meta.get("oos_policy_summary", {}) or {}),
            "folds_by_asset": {
                asset: list(meta.get("folds", []) or [])
                for asset, meta in dict(model_meta.get("per_asset", {}) or {}).items()
            },
        },
    ).to_dict()


def compute_monitoring_for_asset(
    df: pd.DataFrame,
    *,
    meta: dict[str, Any],
    monitoring_cfg: dict[str, Any],
) -> dict[str, Any] | None:
    feature_cols = list(meta.get("feature_cols", []) or [])
    if not feature_cols or "pred_is_oos" not in df.columns:
        return None

    oos_mask = df["pred_is_oos"].astype(bool)
    ref = df.loc[~oos_mask, feature_cols]
    cur = df.loc[oos_mask, feature_cols]
    if ref.empty or cur.empty:
        return None

    return compute_feature_drift(
        ref,
        cur,
        feature_cols=feature_cols,
        psi_threshold=float(monitoring_cfg.get("psi_threshold", 0.2)),
        n_bins=int(monitoring_cfg.get("n_bins", 10)),
    )


def compute_monitoring_report(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_meta: dict[str, Any],
    monitoring_cfg: dict[str, Any],
) -> dict[str, Any]:
    if not bool(monitoring_cfg.get("enabled", False)):
        return {}

    per_asset: dict[str, Any] = {}
    if "per_asset" in model_meta:
        for asset, meta in sorted(dict(model_meta.get("per_asset", {}) or {}).items()):
            report = compute_monitoring_for_asset(
                asset_frames[asset],
                meta=meta,
                monitoring_cfg=monitoring_cfg,
            )
            if report:
                per_asset[asset] = report
    elif model_meta:
        only_asset = next(iter(sorted(asset_frames)))
        report = compute_monitoring_for_asset(
            asset_frames[only_asset],
            meta=model_meta,
            monitoring_cfg=monitoring_cfg,
        )
        if report:
            per_asset[only_asset] = report

    if not per_asset:
        return {}

    return MonitoringPayload(
        asset_count=int(len(per_asset)),
        drifted_feature_count=int(
            sum(int(report.get("drifted_feature_count", 0)) for report in per_asset.values())
        ),
        feature_count=int(sum(int(report.get("feature_count", 0)) for report in per_asset.values())),
        per_asset=per_asset,
    ).to_dict()


__all__ = [
    "build_fold_backtest_summaries",
    "build_portfolio_evaluation",
    "build_experiment_diagnostics",
    "build_experiment_report_markdown",
    "build_single_asset_evaluation",
    "compute_monitoring_for_asset",
    "compute_monitoring_report",
    "compute_subset_metrics",
]
