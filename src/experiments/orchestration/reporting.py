from __future__ import annotations

import inspect
import math
import re
from typing import Any, TYPE_CHECKING

import numpy as np
import pandas as pd
import yaml

from src.backtesting.engine import BacktestResult
from src.evaluation.metrics import compute_backtest_metrics, compute_ftmo_style_metrics
from src.experiments.schemas import EvaluationPayload, MonitoringPayload
from src.experiments.support.baseline_diagnostics import (
    compute_baseline_vwap_rms_ema_ppo_mfi_atr_diagnostics,
)
from src.experiments.support.c2_diagnostics import compute_c2_regime_aware_momentum_diagnostics
from src.experiments.support.ehlers_continuation_long_diagnostics import (
    compute_ehlers_continuation_long_diagnostics,
)
from src.experiments.support.ehlers_continuation_short_diagnostics import (
    compute_ehlers_continuation_short_diagnostics,
)
from src.experiments.support.stc_roofing_hilbert_diagnostics import (
    compute_stc_roofing_hilbert_diagnostics,
)

if TYPE_CHECKING:
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


def _scalar_metric_rows(payload: dict[str, Any]) -> list[list[Any]]:
    return [[key, value] for key, value in payload.items() if not isinstance(value, (dict, list))]


def _performance_breakdown_rows(section: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for group_name, buckets in sorted(section.items()):
        if not isinstance(buckets, dict):
            continue
        for bucket, payload in sorted(dict(buckets).items()):
            metrics = _safe_meta_dict(payload)
            rows.append(
                [
                    group_name,
                    bucket,
                    metrics.get("trade_count"),
                    metrics.get("gross_pnl"),
                    metrics.get("cost"),
                    metrics.get("net_pnl"),
                    metrics.get("profit_factor"),
                    metrics.get("hit_rate"),
                ]
            )
    return rows


def _safe_meta_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _classify_feature_family(feature: str) -> str | None:
    try:
        from src.models.common.runtime import classify_feature_family
    except ModuleNotFoundError:
        return None
    return classify_feature_family(feature)


def _extract_drifted_features(monitoring: dict[str, Any], limit: int = 8) -> list[tuple[str, str, float]]:
    drifted: list[tuple[str, str, float]] = []
    for asset, asset_report in sorted(dict(monitoring.get("per_asset", {}) or {}).items()):
        per_feature = dict(asset_report.get("per_feature", {}) or {})
        for feature, details in per_feature.items():
            if bool(details.get("is_drifted", False)):
                drifted.append((asset, feature, float(details.get("psi", 0.0))))
    drifted.sort(key=lambda item: abs(item[2]), reverse=True)
    return drifted[:limit]


def _feature_family_drift_rows(monitoring: dict[str, Any]) -> list[list[Any]]:
    bucket: dict[str, dict[str, float]] = {}
    for _, asset_report in sorted(dict(monitoring.get("per_asset", {}) or {}).items()):
        per_feature = dict(asset_report.get("per_feature", {}) or {})
        for feature, details in per_feature.items():
            family = _classify_feature_family(str(feature)) or "unclassified"
            info = bucket.setdefault(
                family,
                {
                    "feature_count": 0.0,
                    "drifted_feature_count": 0.0,
                    "psi_sum": 0.0,
                    "max_psi": 0.0,
                },
            )
            psi = abs(float(details.get("psi", 0.0) or 0.0))
            info["feature_count"] += 1.0
            info["psi_sum"] += psi
            info["max_psi"] = max(info["max_psi"], psi)
            if bool(details.get("is_drifted", False)):
                info["drifted_feature_count"] += 1.0

    rows: list[list[Any]] = []
    for family, info in sorted(bucket.items(), key=lambda kv: (-kv[1]["max_psi"], kv[0])):
        feature_count = max(info["feature_count"], 1.0)
        rows.append(
            [
                family,
                int(info["feature_count"]),
                int(info["drifted_feature_count"]),
                float(info["drifted_feature_count"] / feature_count),
                float(info["psi_sum"] / feature_count),
                float(info["max_psi"]),
            ]
        )
    return rows


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
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    dd_cfg = dict(cfg.get("risk", {}).get("dd_guard", {}) or {})
    return {
        "backtest_min_holding_bars": backtest_cfg.get("min_holding_bars", 0),
        "min_holding_bars": env_cfg.get("min_holding_bars", 0),
        "action_hysteresis": env_cfg.get("action_hysteresis", 0.0),
        "dd_guard_enabled": dd_cfg.get("enabled", False),
        "max_drawdown": dd_cfg.get("max_drawdown", 0.2),
        "cooloff_bars": dd_cfg.get("cooloff_bars", 20),
        "rearm_drawdown": dd_cfg.get("rearm_drawdown", dd_cfg.get("max_drawdown", 0.2)),
    }


def _build_pipeline_trace_markdown(
    *,
    cfg: dict[str, Any],
    summary_payload: dict[str, Any],
) -> str:
    from src.backtesting.engine import BacktestResult, run_backtest
    from src.experiments.contracts import validate_data_contract
    from src.models.common.runtime import resolve_runtime_for_model
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
    from src.experiments.orchestration.model_stage import apply_model_pipeline_to_assets, apply_model_step, apply_model_to_assets
    from src.experiments.orchestration.pipeline import run_experiment_pipeline
    from src.features.registry import get_feature_fn
    from src.models.registry import get_model_fn
    from src.signals.registry import get_signal_fn
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
    model_stages_cfg = list(cfg.get("model_stages", []) or [])
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
            _interface_line("model_stage.apply_model_pipeline_to_assets", apply_model_pipeline_to_assets),
            _interface_line("model_stage.apply_model_to_assets", apply_model_to_assets),
            _interface_line("feature_stage.apply_model_step", apply_model_step),
        ]
    )
    if model_stages_cfg:
        for idx, stage_cfg in enumerate(model_stages_cfg, start=1):
            stage_name = str(stage_cfg.get("name", f"stage_{idx}"))
            stage_kind = str(stage_cfg.get("kind", "none"))
            stage_order = int(stage_cfg.get("stage", idx) or idx)
            enabled = bool(stage_cfg.get("enabled", True))
            if not enabled:
                lines.append(f"- `model_stage[{stage_name}]` -> disabled (stage={stage_order})")
                continue
            model_fn = get_model_fn(stage_kind)
            lines.append(_interface_line(f"model_stage[{stage_order}:{stage_name}:{stage_kind}]", model_fn))
    elif model_kind != "none":
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
                    "model_stages": model_stages_cfg,
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
    drift_filter = dict(
        dict(cfg.get("model", {}) or {}).get("feature_selectors", {}) or {}
    ).get("drift_filter", {}) or {}
    if bool(dict(drift_filter).get("enabled", False)):
        ratio_threshold = float(dict(drift_filter).get("family_drift_ratio_threshold", 0.5) or 0.5)
        for row in _feature_family_drift_rows(monitoring):
            family, _, _, drift_ratio, _, _ = row
            if float(drift_ratio) > ratio_threshold:
                diagnostics.append(
                    f"Feature drift filter warning: family '{family}' has drift ratio "
                    f"{float(drift_ratio):.3f}, above threshold {ratio_threshold:.3f}."
                )
        if str(dict(drift_filter).get("action", "warn")) == "drop":
            diagnostics.append(
                "Feature drift filter action='drop' is recorded but same-run dropping is not applied, "
                "to avoid using OOS drift information inside the evaluated fold."
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
    target_meta = _safe_meta_dict(model_meta.get("target"))
    data_cfg = dict(cfg.get("data", {}) or {})
    model_cfg = dict(cfg.get("model", {}) or {})
    runtime_cfg = dict(cfg.get("runtime", {}) or {})
    data_stats = dict(summary_payload.get("data_stats", {}) or {})
    policy_summary = dict(evaluation.get("model_oos_policy_summary", {}) or {})
    resolved_features = summary_payload.get("resolved_feature_columns", []) or []
    stage_tails = dict(summary_payload.get("stage_tails", {}) or {})
    ftmo_metrics = _safe_meta_dict(evaluation.get("ftmo_metrics"))
    ftmo_objective = _safe_meta_dict(evaluation.get("ftmo_objective"))
    risk_guard_summary = _safe_meta_dict(evaluation.get("risk_guard_summary"))
    feature_diagnostics = _safe_meta_dict(evaluation.get("feature_diagnostics"))
    orb_diagnostics = _safe_meta_dict(evaluation.get("orb_diagnostics"))
    trade_diagnostics = _safe_meta_dict(evaluation.get("trade_diagnostics"))
    baseline_diagnostics = _safe_meta_dict(evaluation.get("baseline_diagnostics"))
    c2_diagnostics = _safe_meta_dict(evaluation.get("c2_diagnostics"))
    stc_diagnostics = _safe_meta_dict(evaluation.get("stc_roofing_hilbert_diagnostics"))
    ehlers_diagnostics = _safe_meta_dict(evaluation.get("ehlers_continuation_long_diagnostics"))
    ehlers_short_diagnostics = _safe_meta_dict(evaluation.get("ehlers_continuation_short_diagnostics"))
    robustness_diagnostics = _safe_meta_dict(evaluation.get("robustness"))

    symbols = data_cfg.get("symbols") or ([data_cfg.get("symbol")] if data_cfg.get("symbol") else [])
    run_name = str(cfg.get("logging", {}).get("run_name", cfg.get("config_path", "experiment")))
    model_stages = list(model_meta.get("stages", []) or [])
    model_label = str(model_cfg.get("kind", "none"))
    if model_stages:
        ordered = " -> ".join(f"{stage.get('name')}:{stage.get('kind')}" for stage in model_stages)
        model_label = f"multi_stage ({ordered})"
    target_cfg = dict(model_cfg.get("target", {}) or {})
    target_kind = target_meta.get("kind", target_cfg.get("kind", "n/a"))
    target_horizon = target_meta.get("max_holding", target_meta.get("horizon", target_cfg.get("horizon", "n/a")))
    feature_pipeline = dict(model_meta.get("feature_pipeline", {}) or {})
    reported_feature_count = feature_pipeline.get(
        "actual_model_feature_count",
        model_meta.get("contracts", {}).get("n_features", len(summary_payload.get("resolved_feature_columns", []) or [])),
    )
    lines: list[str] = [
        f"# Experiment Report: {run_name}",
        "",
        "## Overview",
        f"- Config path: `{cfg.get('config_path', '')}`",
        f"- Model kind: `{model_label}`",
        f"- Symbols: `{', '.join(str(symbol) for symbol in symbols) if symbols else 'n/a'}`",
        f"- Data source: `{data_cfg.get('source', 'n/a')}` at interval `{data_cfg.get('interval', 'n/a')}`",
        f"- Data window: `{data_cfg.get('start', 'n/a')}` to `{data_stats.get('end', data_cfg.get('end', 'latest'))}`",
        f"- Rows / columns: `{data_stats.get('rows', 'n/a')}` rows, `{data_stats.get('columns', 'n/a')}` columns",
        f"- Target: `{target_kind}` horizon `{target_horizon}`",
        f"- Feature count: `{reported_feature_count}`",
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

    warnings = list(model_meta.get("warnings", []) or [])
    if bool(dict(cfg.get("backtest", {}) or {}).get("dynamic_exits", {}).get("enabled", False)):
        warnings.append(
            "Backtest dynamic exits are enabled. The current pre-model r_multiple target still labels "
            "manual candidates with barrier semantics and does not use final model_filtered_long_signal "
            "for signal-off exits."
        )
    if warnings:
        lines.extend(["", "## Warnings", *[f"- {warning}" for warning in warnings]])

    if orb_diagnostics:
        scalar_keys = [
            "orb_candidate_count",
            "orb_candidate_rate",
            "orb_accepted_trade_count",
            "orb_long_candidate_count",
            "orb_short_candidate_count",
            "average_orb_range_width_atr",
            "breakout_success_rate",
        ]
        lines.extend(
            [
                "",
                "## Opening Range Breakout Diagnostics",
                _markdown_table(
                    ["Metric", "Value"],
                    [[key, orb_diagnostics.get(key)] for key in scalar_keys if key in orb_diagnostics],
                ),
            ]
        )
        breakdown_rows: list[list[Any]] = []
        for section in (
            "candidate_count_by_asset",
            "trade_count_by_asset",
            "pnl_by_asset",
            "gross_pnl_by_asset",
            "cost_by_asset",
            "success_rate_by_asset",
            "candidate_count_by_session",
            "trade_count_by_session",
            "pnl_by_session",
            "success_rate_by_session",
        ):
            values = dict(orb_diagnostics.get(section, {}) or {})
            for key, value in sorted(values.items()):
                breakdown_rows.append([section, key, value])
        if breakdown_rows:
            lines.append(_markdown_table(["Section", "Key", "Value"], breakdown_rows))

    if ftmo_metrics:
        lines.extend(
            [
                "",
                "## FTMO Metrics",
                _markdown_table(["Metric", "Value"], _dict_metric_rows(ftmo_metrics)),
            ]
        )
    if ftmo_objective:
        lines.extend(
            [
                "",
                "## FTMO Objective",
                _markdown_table(["Metric", "Value"], _dict_metric_rows(ftmo_objective)),
            ]
        )
    if risk_guard_summary:
        lines.extend(
            [
                "",
                "## Risk Guard",
                _markdown_table(["Metric", "Value"], _dict_metric_rows(risk_guard_summary)),
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

    dense_diagnostic_links = [
        [label.replace("diagnostics_", ""), f"[open]({rel_path})"]
        for label, rel_path in sorted(artifact_paths.items())
        if str(label).startswith("diagnostics_") and not str(rel_path).lower().endswith(".png")
    ]
    if dense_diagnostic_links:
        lines.extend(
            [
                "",
                "## Dense Forecast Diagnostics",
                _markdown_table(["Artifact", "Link"], dense_diagnostic_links),
            ]
        )

    if model_stages:
        stage_rows = [
            [
                stage.get("name"),
                stage.get("stage"),
                stage.get("kind"),
                dict(stage.get("prediction_diagnostics", {}) or {}).get("predicted_rows"),
                dict(stage.get("prediction_diagnostics", {}) or {}).get("oos_prediction_coverage"),
                dict(stage.get("oos_classification_summary", {}) or {}).get("evaluation_rows")
                or dict(stage.get("oos_regression_summary", {}) or {}).get("evaluation_rows")
                or dict(stage.get("oos_volatility_summary", {}) or {}).get("evaluation_rows"),
                ", ".join(list(stage.get("feature_cols", []) or [])),
            ]
            for stage in model_stages
        ]
        lines.extend(
            [
                "",
                "## Multi-Stage Summary",
                _markdown_table(
                    ["Stage", "Order", "Kind", "Predicted Rows", "OOS Coverage", "Eval Rows", "Feature Cols"],
                    stage_rows,
                ),
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

    if trade_diagnostics:
        trade_path_diagnostics = _safe_meta_dict(trade_diagnostics.get("trade_path"))
        trade_rows = _scalar_metric_rows({k: v for k, v in trade_diagnostics.items() if k != "trade_path"})
        if trade_rows:
            lines.extend(
                [
                    "",
                    "## Trade Diagnostics",
                    _markdown_table(["Metric", "Value"], trade_rows),
                ]
            )
        if trade_path_diagnostics:
            lines.extend(["", "## Trade Path Diagnostics"])
            sections = [
                ("Losing Trades Could-Have-Been-Profitable", "could_have_been_profitable"),
                ("Capture / Giveback", "capture_giveback"),
                ("MAE Before Win", "mae_before_win"),
                ("Conditional Probabilities", "conditional_probabilities"),
                ("Timing Diagnostics", "timing"),
                ("Counterfactual Exits", "counterfactual"),
            ]
            for title, key in sections:
                payload = _safe_meta_dict(trade_path_diagnostics.get(key))
                rows = _dict_metric_rows(payload)
                if rows:
                    lines.extend([f"### {title}", _markdown_table(["Metric", "Value"], rows)])
            target_candidates = _safe_meta_dict(trade_path_diagnostics.get("target_candidates"))
            if target_candidates:
                rows = _dict_metric_rows(target_candidates)
                if rows:
                    lines.extend(["### Target / Candidate Trade Diagnostics", _markdown_table(["Metric", "Value"], rows)])
            exit_quality = _safe_meta_dict(trade_path_diagnostics.get("exit_reason_quality"))
            if exit_quality:
                rows = []
                for reason, payload in sorted(exit_quality.items()):
                    metrics = _safe_meta_dict(payload)
                    rows.append(
                        [
                            reason,
                            metrics.get("trade_count"),
                            metrics.get("avg_r"),
                            metrics.get("median_r"),
                            metrics.get("win_rate"),
                            metrics.get("avg_mfe_r"),
                            metrics.get("avg_mae_r"),
                            metrics.get("avg_giveback_r"),
                            metrics.get("avg_bars_held"),
                            metrics.get("profit_factor"),
                            metrics.get("stop_after_positive_rate"),
                            metrics.get("stop_after_0_5r_rate"),
                            metrics.get("stop_after_1r_rate"),
                        ]
                    )
                lines.extend(
                    [
                        "### Exit Reason Quality",
                        _markdown_table(
                            [
                                "Exit Reason",
                                "Trades",
                                "Avg R",
                                "Median R",
                                "Win Rate",
                                "Avg MFE",
                                "Avg MAE",
                                "Avg Giveback",
                                "Avg Bars",
                                "Profit Factor",
                                "Stop After +",
                                "Stop After 0.5R",
                                "Stop After 1R",
                            ],
                            rows,
                        ),
                    ]
                )
            warnings_rows = [[warning] for warning in list(trade_path_diagnostics.get("warnings", []) or [])]
            if warnings_rows:
                lines.extend(["### Diagnostic Warnings", _markdown_table(["Warning"], warnings_rows)])

    if baseline_diagnostics:
        primary_rows = _dict_metric_rows(_safe_meta_dict(baseline_diagnostics.get("primary")))
        breakdown_rows = _performance_breakdown_rows(
            {
                "asset": _safe_meta_dict(baseline_diagnostics.get("performance_by_asset")),
                "side": _safe_meta_dict(baseline_diagnostics.get("performance_by_side")),
                "year": _safe_meta_dict(baseline_diagnostics.get("performance_by_year")),
                "volatility_regime": _safe_meta_dict(
                    baseline_diagnostics.get("performance_by_volatility_regime")
                ),
            }
        )
        lines.extend(["", "## Baseline VWAP/RMS Diagnostics"])
        if primary_rows:
            lines.extend(
                [
                    "### Primary",
                    _markdown_table(["Metric", "Value"], primary_rows),
                ]
            )
        trade_count_by_asset = _safe_meta_dict(baseline_diagnostics.get("trade_count_by_asset"))
        if trade_count_by_asset:
            lines.extend(
                [
                    "### Trade Count By Asset",
                    _markdown_table(
                        ["Asset", "Trades"],
                        [[asset, count] for asset, count in sorted(trade_count_by_asset.items())],
                    ),
                ]
            )
        if breakdown_rows:
            lines.extend(
                [
                    "### Performance Breakdowns",
                    _markdown_table(
                        ["Group", "Bucket", "Trades", "Gross PnL", "Cost", "Net PnL", "Profit Factor", "Hit Rate"],
                        breakdown_rows,
                    ),
                ]
            )

    if c2_diagnostics:
        signal_count_rows = _dict_metric_rows(_safe_meta_dict(c2_diagnostics.get("signal_counts")))
        position_rows = _dict_metric_rows(_safe_meta_dict(c2_diagnostics.get("position_diagnostics")))
        side_rows = _dict_metric_rows(_safe_meta_dict(c2_diagnostics.get("side_diagnostics")))
        breakdown_rows = _performance_breakdown_rows(
            _safe_meta_dict(c2_diagnostics.get("regime_diagnostics"))
        )
        lines.extend(["", "## C2 Diagnostics"])
        if signal_count_rows:
            lines.extend(
                [
                    "### Signal Counts",
                    _markdown_table(["Metric", "Value"], signal_count_rows),
                ]
            )
        if position_rows:
            lines.extend(
                [
                    "### Position Diagnostics",
                    _markdown_table(["Metric", "Value"], position_rows),
                ]
            )
        if side_rows:
            lines.extend(
                [
                    "### Side Diagnostics",
                    _markdown_table(["Metric", "Value"], side_rows),
                ]
            )
        if breakdown_rows:
            lines.extend(
                [
                    "### Regime And Year Diagnostics",
                    _markdown_table(
                        ["Group", "Bucket", "Trades", "Gross PnL", "Cost", "Net PnL", "Profit Factor", "Hit Rate"],
                        breakdown_rows,
                    ),
                ]
            )

    if stc_diagnostics:
        signal_count_rows = _dict_metric_rows(_safe_meta_dict(stc_diagnostics.get("signal_counts")))
        performance_rows = _dict_metric_rows(_safe_meta_dict(stc_diagnostics.get("performance_diagnostics")))
        side_rows = _performance_breakdown_rows(
            {"side": _safe_meta_dict(stc_diagnostics.get("side_diagnostics"))}
        )
        year_rows = _performance_breakdown_rows(
            {"year": _safe_meta_dict(stc_diagnostics.get("performance_by_year"))}
        )
        volatility_rows = _performance_breakdown_rows(
            {"volatility_regime": _safe_meta_dict(stc_diagnostics.get("performance_by_volatility_regime"))}
        )
        lines.extend(["", "## STC Roofing Hilbert Diagnostics"])
        if signal_count_rows:
            lines.extend(
                [
                    "### Signal Counts",
                    _markdown_table(["Metric", "Value"], signal_count_rows),
                ]
            )
        if performance_rows:
            lines.extend(
                [
                    "### Performance",
                    _markdown_table(["Metric", "Value"], performance_rows),
                ]
            )
        if side_rows:
            lines.extend(
                [
                    "### Side Diagnostics",
                    _markdown_table(
                        ["Group", "Bucket", "Trades", "Gross PnL", "Cost", "Net PnL", "Profit Factor", "Hit Rate"],
                        side_rows,
                    ),
                ]
            )
        if year_rows:
            lines.extend(
                [
                    "### Year Diagnostics",
                    _markdown_table(
                        ["Group", "Bucket", "Trades", "Gross PnL", "Cost", "Net PnL", "Profit Factor", "Hit Rate"],
                        year_rows,
                    ),
                ]
            )
        if volatility_rows:
            lines.extend(
                [
                    "### Volatility Regime Diagnostics",
                    _markdown_table(
                        ["Group", "Bucket", "Trades", "Gross PnL", "Cost", "Net PnL", "Profit Factor", "Hit Rate"],
                        volatility_rows,
                    ),
                ]
            )

    if ehlers_diagnostics:
        signal_count_rows = _dict_metric_rows(_safe_meta_dict(ehlers_diagnostics.get("signal_counts")))
        overlap_rows = _dict_metric_rows(_safe_meta_dict(ehlers_diagnostics.get("overlap_diagnostics")))
        position_rows = _dict_metric_rows(_safe_meta_dict(ehlers_diagnostics.get("position_diagnostics")))
        performance_rows = _dict_metric_rows(_safe_meta_dict(ehlers_diagnostics.get("performance_diagnostics")))
        year_rows = _performance_breakdown_rows(
            {"year": _safe_meta_dict(ehlers_diagnostics.get("performance_by_year"))}
        )
        lines.extend(["", "## Ehlers Continuation Long Diagnostics"])
        if signal_count_rows:
            lines.extend(
                [
                    "### Signal Counts",
                    _markdown_table(["Metric", "Value"], signal_count_rows),
                ]
            )
        if overlap_rows:
            lines.extend(
                [
                    "### Overlap Diagnostics",
                    _markdown_table(["Metric", "Value"], overlap_rows),
                ]
            )
        if position_rows:
            lines.extend(
                [
                    "### Position Diagnostics",
                    _markdown_table(["Metric", "Value"], position_rows),
                ]
            )
        if performance_rows:
            lines.extend(
                [
                    "### Performance Diagnostics",
                    _markdown_table(["Metric", "Value"], performance_rows),
                ]
            )
        if year_rows:
            lines.extend(
                [
                    "### Year Diagnostics",
                    _markdown_table(
                        ["Group", "Bucket", "Trades", "Gross PnL", "Cost", "Net PnL", "Profit Factor", "Hit Rate"],
                        year_rows,
                    ),
                ]
            )

    if ehlers_short_diagnostics:
        signal_count_rows = _dict_metric_rows(_safe_meta_dict(ehlers_short_diagnostics.get("signal_counts")))
        overlap_rows = _dict_metric_rows(_safe_meta_dict(ehlers_short_diagnostics.get("overlap_diagnostics")))
        position_rows = _dict_metric_rows(_safe_meta_dict(ehlers_short_diagnostics.get("position_diagnostics")))
        performance_rows = _dict_metric_rows(_safe_meta_dict(ehlers_short_diagnostics.get("performance_diagnostics")))
        year_rows = _performance_breakdown_rows(
            {"year": _safe_meta_dict(ehlers_short_diagnostics.get("performance_by_year"))}
        )
        lines.extend(["", "## Ehlers Continuation Short Diagnostics"])
        if signal_count_rows:
            lines.extend(
                [
                    "### Signal Counts",
                    _markdown_table(["Metric", "Value"], signal_count_rows),
                ]
            )
        if overlap_rows:
            lines.extend(
                [
                    "### Overlap Diagnostics",
                    _markdown_table(["Metric", "Value"], overlap_rows),
                ]
            )
        if position_rows:
            lines.extend(
                [
                    "### Position Diagnostics",
                    _markdown_table(["Metric", "Value"], position_rows),
                ]
            )
        if performance_rows:
            lines.extend(
                [
                    "### Performance Diagnostics",
                    _markdown_table(["Metric", "Value"], performance_rows),
                ]
            )
        if year_rows:
            lines.extend(
                [
                    "### Year Diagnostics",
                    _markdown_table(
                        ["Group", "Bucket", "Trades", "Gross PnL", "Cost", "Net PnL", "Profit Factor", "Hit Rate"],
                        year_rows,
                    ),
                ]
            )

    if robustness_diagnostics:
        lines.extend(["", "## Robustness Diagnostics"])
        for label, section in (
            ("Cost Stress", "cost_stress"),
            ("Entry Delay", "entry_delay"),
            ("Walk Forward", "walk_forward"),
            ("Gap Stress", "gap_stress"),
        ):
            rows = _dict_metric_rows(_safe_meta_dict(robustness_diagnostics.get(section)))
            if rows:
                lines.extend(
                    [
                        f"### {label}",
                        _markdown_table(["Metric", "Value"], rows),
                    ]
                )

    if target_meta:
        target_rows: list[list[Any]] = []
        for key in (
            "kind",
            "label_mode",
            "max_holding",
            "max_holding_bars",
            "upper_mult",
            "lower_mult",
            "neutral_label",
            "tie_break",
            "entry_price_mode",
            "vol_window",
            "min_vol",
            "labeled_rows",
            "positive_rate",
            "target_r_min",
            "take_profit_r",
            "stop_loss_r",
            "stop_mode",
            "upper_barrier_count",
            "lower_barrier_count",
            "neutral_count",
            "take_profit_count",
            "stop_loss_count",
            "max_holding_close_count",
            "unavailable_tail_count",
            "invalid_entry_count",
            "avg_trade_r",
            "median_trade_r",
            "q25_trade_r",
            "q75_trade_r",
            "avg_bars_held",
            "median_bars_held",
            "avg_hit_step",
            "median_hit_step",
            "meta_labeling",
            "candidate_rows",
            "candidate_col",
            "add_r_multiple",
            "r_col",
            "oriented_r_col",
        ):
            if key in target_meta:
                target_rows.append([key, target_meta.get(key)])
        for section_key in ("label_distribution", "exit_reason_counts"):
            distribution = _safe_meta_dict(target_meta.get(section_key))
            for metric, value in _dict_metric_rows(distribution):
                target_rows.append([f"{section_key}.{metric}", value])
        for section_key in ("event_r_distribution", "oriented_r_distribution"):
            distribution = _safe_meta_dict(target_meta.get(section_key))
            for metric, value in distribution.items():
                target_rows.append([f"{section_key}.{metric}", value])
        if target_rows:
            lines.extend(
                [
                    "",
                    "## Target Diagnostics",
                    _markdown_table(["Metric", "Value"], target_rows),
                ]
            )
        winner_loser_features = _safe_meta_dict(target_meta.get("winner_loser_feature_summary"))
        if winner_loser_features:
            rows: list[list[Any]] = []
            for feature, payload in sorted(winner_loser_features.items()):
                feature_payload = _safe_meta_dict(payload)
                rows.append(
                    [
                        feature,
                        feature_payload.get("winner_rows"),
                        feature_payload.get("loser_rows"),
                        feature_payload.get("winner_mean"),
                        feature_payload.get("loser_mean"),
                        feature_payload.get("mean_diff"),
                        feature_payload.get("winner_median"),
                        feature_payload.get("loser_median"),
                    ]
                )
            lines.extend(
                [
                    "",
                    "## Target Winner Vs Loser Diagnostics",
                    _markdown_table(
                        [
                            "Feature",
                            "Winner Rows",
                            "Loser Rows",
                            "Winner Mean",
                            "Loser Mean",
                            "Mean Diff",
                            "Winner Median",
                            "Loser Median",
                        ],
                        rows,
                    ),
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

    feature_diag_rows: list[list[Any]] = []
    per_asset_feature_diag = dict(feature_diagnostics.get("per_asset", {}) or {})
    if per_asset_feature_diag:
        for asset, payload in sorted(per_asset_feature_diag.items()):
            feature_diag_rows.append(
                [
                    asset,
                    payload.get("resolved_feature_count"),
                    payload.get("missing_feature_rows"),
                    ", ".join(list(dict(payload.get("feature_selection", {}) or {}).get("enabled_families", []) or [])),
                    _format_report_value(dict(payload.get("feature_selection", {}) or {}).get("profile")),
                ]
            )
    if feature_diag_rows:
        lines.extend(
            [
                "",
                "## Feature Diagnostics",
                _markdown_table(
                    ["Asset", "Resolved Features", "Missing Rows", "Enabled Families", "Profile"],
                    feature_diag_rows,
                ),
            ]
        )

    feature_stability_rows: list[list[Any]] = []
    if per_asset_feature_diag:
        for asset, payload in sorted(per_asset_feature_diag.items()):
            stability = dict(payload.get("feature_importance_stability", {}) or {})
            for row in list(stability.get("top_features", []) or [])[:5]:
                feature_stability_rows.append(
                    [
                        asset,
                        row.get("feature"),
                        row.get("family"),
                        row.get("fold_count"),
                        row.get("fold_coverage"),
                        row.get("mean_rank"),
                        row.get("mean_importance_normalized"),
                    ]
                )
    if feature_stability_rows:
        lines.extend(
            [
                "",
                "## Feature Importance Stability",
                _markdown_table(
                    ["Asset", "Feature", "Family", "Fold Count", "Fold Coverage", "Mean Rank", "Mean Importance Norm"],
                    feature_stability_rows,
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
        ["long_rate", policy_summary.get("long_rate")],
        ["short_rate", policy_summary.get("short_rate")],
        ["trade_rate", policy_summary.get("trade_rate")],
        ["executed_trade_count", policy_summary.get("executed_trade_count")],
        ["avg_signal_executed", policy_summary.get("avg_signal_executed")],
        ["avg_pred_prob_executed", policy_summary.get("avg_pred_prob_executed")],
        ["avg_realized_r_executed", policy_summary.get("avg_realized_r_executed")],
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
            if str(rel_path).lower().endswith((".html", ".htm")):
                lines.extend([f"### {title}", f"[Open interactive {title}]({rel_path})", ""])
            else:
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
                    fold.get("train_rows_not_labeled", 0),
                    fold.get("train_rows_without_fit", fold.get("train_rows_dropped_missing", 0)),
                    fold.get("test_rows"),
                    fold.get("test_pred_rows"),
                    fold.get("test_rows_missing_features", 0),
                    fold.get("test_rows_not_candidates", 0),
                    fold.get("test_rows_without_prediction", fold.get("test_rows_missing_features", 0)),
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
                        "Train Missing Features",
                        "Train Not Labeled",
                        "Train Without Fit",
                        "Test Rows",
                        "Pred Rows",
                        "Test Missing Features",
                        "Test Not Candidates",
                        "Test Without Prediction",
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

    family_drift_rows = _feature_family_drift_rows(monitoring)
    if family_drift_rows:
        lines.extend(
            [
                "",
                "## Drift By Family",
                _markdown_table(
                    ["Family", "Feature Count", "Drifted Count", "Drifted Ratio", "Mean Abs PSI", "Max Abs PSI"],
                    family_drift_rows,
                ),
            ]
        )

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


def build_portfolio_fold_backtest_summaries(
    *,
    asset_frames: dict[str, pd.DataFrame],
    performance: PortfolioPerformance,
    model_meta: dict[str, Any],
    periods_per_year: int,
) -> list[dict[str, Any]]:
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    if not per_asset_meta:
        return []

    by_fold: dict[int, dict[str, Any]] = {}
    for asset, meta in sorted(per_asset_meta.items()):
        frame = asset_frames.get(asset)
        if frame is None:
            continue
        for fold in list(meta.get("folds", []) or []):
            fold_id = int(fold.get("fold", -1))
            start = int(fold["test_start"])
            end = int(fold["test_end"])
            fold_index = frame.index[start:end]
            entry = by_fold.setdefault(
                fold_id,
                {
                    "fold": fold_id,
                    "asset_indices": {},
                    "asset_test_rows": {},
                },
            )
            entry["asset_indices"][asset] = pd.Index(fold_index)
            entry["asset_test_rows"][asset] = int(len(fold_index))

    out: list[dict[str, Any]] = []
    for fold_id in sorted(by_fold):
        entry = by_fold[fold_id]
        indices = list(entry["asset_indices"].values())
        if not indices:
            continue
        common_index = indices[0]
        for asset_index in indices[1:]:
            common_index = common_index.intersection(asset_index)
        common_index = common_index.intersection(performance.net_returns.index)
        if len(common_index) == 0:
            continue

        mask = pd.Series(performance.net_returns.index.isin(common_index), index=performance.net_returns.index)
        summary = compute_subset_metrics(
            net_returns=performance.net_returns,
            turnover=performance.turnover,
            costs=performance.costs,
            gross_returns=performance.gross_returns,
            periods_per_year=periods_per_year,
            mask=mask,
        )
        out.append(
            {
                "fold": int(fold_id),
                "test_rows": int(len(common_index)),
                "common_oos_rows": int(len(common_index)),
                "asset_test_rows": dict(entry["asset_test_rows"]),
                "metrics": summary,
            }
        )
    return out


def _portfolio_feature_diagnostics(model_meta: dict[str, Any]) -> dict[str, Any]:
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    if not per_asset_meta:
        feature_selection = dict(model_meta.get("feature_selection", {}) or {})
        return {
            "profile": feature_selection.get("profile"),
            "enabled_families": list(feature_selection.get("enabled_families", []) or []),
            "per_asset": {},
        }

    per_asset: dict[str, Any] = {}
    profiles = set()
    enabled_family_sets: set[tuple[str, ...]] = set()
    resolved_counts: list[int] = []
    missing_feature_rows_total = 0
    family_totals: dict[str, int] = {}
    for asset, meta in sorted(per_asset_meta.items()):
        feature_selection = dict(meta.get("feature_selection", {}) or {})
        feature_pipeline = dict(meta.get("feature_pipeline", {}) or {})
        profile = feature_selection.get("profile")
        if profile:
            profiles.add(str(profile))
        enabled_families = tuple(str(item) for item in list(feature_selection.get("enabled_families", []) or []))
        if enabled_families:
            enabled_family_sets.add(enabled_families)
        resolved_feature_count = int(
            feature_pipeline.get(
                "resolved_feature_count",
                feature_selection.get("resolved_feature_count", len(meta.get("feature_cols", []) or [])),
            )
        )
        model_feature_count = int(
            feature_pipeline.get(
                "actual_model_feature_count",
                feature_pipeline.get("model_feature_count", len(meta.get("feature_cols", []) or [])),
            )
        )
        reported_feature_count = int(
            feature_pipeline.get("reported_feature_count", model_feature_count)
        )
        if reported_feature_count != model_feature_count:
            raise AssertionError("reported_feature_count must equal actual model_feature_count.")
        family_counts = dict(meta.get("feature_family_counts", {}) or feature_selection.get("family_counts", {}) or {})
        missing_feature_rows = int(dict(meta.get("missing_value_diagnostics", {}) or {}).get("test_rows_missing_features", 0) or 0)
        resolved_counts.append(resolved_feature_count)
        missing_feature_rows_total += missing_feature_rows
        for family, count in family_counts.items():
            try:
                family_totals[str(family)] = int(family_totals.get(str(family), 0)) + int(count)
            except (TypeError, ValueError):
                continue
        per_asset[asset] = {
            "resolved_feature_count": resolved_feature_count,
            "model_feature_count": model_feature_count,
            "reported_feature_count": reported_feature_count,
            "raw_feature_count": int(feature_pipeline.get("raw_feature_count", 0) or 0),
            "selected_feature_count": int(feature_pipeline.get("selected_feature_count", model_feature_count) or 0),
            "dropped_missing_count": int(feature_pipeline.get("dropped_missing_count", 0) or 0),
            "dropped_constant_count": int(feature_pipeline.get("dropped_constant_count", 0) or 0),
            "dropped_selector_count": int(feature_pipeline.get("dropped_selector_count", 0) or 0),
            "final_feature_names": list(feature_pipeline.get("final_feature_names", meta.get("feature_cols", []) or []) or []),
            "feature_family_counts": family_counts,
            "missing_feature_rows": missing_feature_rows,
            "feature_selection": feature_selection,
            "feature_pipeline": feature_pipeline,
            "feature_importance_stability": dict(meta.get("feature_importance_stability", {}) or {}),
        }
    return {
        "profile": next(iter(profiles)) if len(profiles) == 1 else None,
        "enabled_families": list(next(iter(enabled_family_sets))) if len(enabled_family_sets) == 1 else [],
        "summary": {
            "asset_count": int(len(per_asset)),
            "min_resolved_feature_count": int(min(resolved_counts)) if resolved_counts else 0,
            "max_resolved_feature_count": int(max(resolved_counts)) if resolved_counts else 0,
            "mean_resolved_feature_count": float(np.mean(resolved_counts)) if resolved_counts else 0.0,
            "total_missing_feature_rows": int(missing_feature_rows_total),
            "feature_family_totals": family_totals,
        },
        "per_asset": per_asset,
    }


def _signal_execution_summary(
    frame: pd.DataFrame,
    *,
    signal_col: str | None,
    oos_mask: pd.Series | None,
    prob_col: str | None = None,
    realized_r_col: str | None = None,
    execution: pd.Series | None = None,
) -> dict[str, Any]:
    if not signal_col or signal_col not in frame.columns:
        return {}
    mask = pd.Series(True, index=frame.index, dtype=bool)
    if oos_mask is not None:
        mask = oos_mask.reindex(frame.index, fill_value=False).astype(bool)
    signal = frame.loc[mask, signal_col].astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if signal.empty:
        return {
            "evaluation_rows": 0,
            "signal_rows": 0,
            "mean_abs_signal": None,
            "signal_turnover": None,
            "long_rate": None,
            "short_rate": None,
            "flat_rate": None,
            "executed_trade_count": 0,
            "trade_rate": None,
            "avg_signal_executed": None,
            "avg_pred_prob_executed": None,
            "avg_realized_r_executed": None,
        }

    exec_signal = signal
    if execution is not None:
        exec_signal = execution.reindex(signal.index).astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    executed = exec_signal.abs() > 1e-12
    out: dict[str, Any] = {
        "evaluation_rows": int(len(signal)),
        "signal_rows": int(len(signal)),
        "mean_abs_signal": float(signal.abs().mean()),
        "signal_turnover": float(signal.diff().abs().fillna(signal.abs()).mean()),
        "long_rate": float((signal > 0.0).mean()),
        "short_rate": float((signal < 0.0).mean()),
        "flat_rate": float((signal == 0.0).mean()),
        "executed_trade_count": int(executed.sum()),
        "trade_rate": float(executed.mean()),
        "avg_signal_executed": float(signal.loc[executed].mean()) if bool(executed.any()) else None,
        "avg_pred_prob_executed": None,
        "avg_realized_r_executed": None,
    }
    if prob_col and prob_col in frame.columns and bool(executed.any()):
        probs = frame[prob_col].reindex(signal.index).astype(float)
        out["avg_pred_prob_executed"] = float(probs.loc[executed].dropna().mean()) if probs.loc[executed].notna().any() else None
    if realized_r_col and realized_r_col in frame.columns and bool(executed.any()):
        realized_r = frame[realized_r_col].reindex(signal.index).astype(float)
        out["avg_realized_r_executed"] = (
            float(realized_r.loc[executed].dropna().mean()) if realized_r.loc[executed].notna().any() else None
        )
    return out


def _trade_diagnostics_from_trades(trades: pd.DataFrame | None) -> dict[str, Any]:
    if trades is None:
        return {}
    if trades.empty:
        return {
            "trade_count": 0,
            "average_r": None,
            "median_r": None,
        }
    out: dict[str, Any] = {"trade_count": int(len(trades))}
    if "trade_r" in trades.columns:
        trade_r = pd.to_numeric(trades["trade_r"], errors="coerce").dropna().astype(float)
        out["average_r"] = float(trade_r.mean()) if not trade_r.empty else None
        out["median_r"] = float(trade_r.median()) if not trade_r.empty else None
    if "exit_reason" in trades.columns:
        for reason, count in trades["exit_reason"].astype(str).value_counts().sort_index().items():
            out[f"exit_reason_counts.{reason}"] = int(count)
    for col in ("max_favorable_r", "max_adverse_r"):
        if col in trades.columns:
            values = pd.to_numeric(trades[col], errors="coerce").dropna().astype(float)
            out[f"avg_{col}"] = float(values.mean()) if not values.empty else None
            out[f"median_{col}"] = float(values.median()) if not values.empty else None
    for col in ("breakeven_activated", "profit_lock_activated"):
        if col in trades.columns:
            out[f"{col}_count"] = int(pd.Series(trades[col]).fillna(False).astype(bool).sum())
    return out


def _portfolio_forecast_quality_summary(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_meta: dict[str, Any],
    signal_col: str,
    quantiles: int = 10,
) -> dict[str, Any]:
    predictions: list[pd.Series] = []
    realized: list[pd.Series] = []
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    for asset, frame in sorted(asset_frames.items()):
        meta = dict(per_asset_meta.get(asset, {}) or model_meta or {})
        target_meta = dict(meta.get("target", {}) or {})
        target_col = str(target_meta.get("label_col") or target_meta.get("fwd_col") or "")
        pred_col = signal_col if signal_col and signal_col in frame.columns else str(meta.get("pred_ret_col") or "")
        if not pred_col or not target_col or pred_col not in frame.columns or target_col not in frame.columns:
            continue
        oos_col = str(meta.get("pred_is_oos_col") or model_meta.get("pred_is_oos_col") or "pred_is_oos")
        if oos_col in frame.columns:
            mask = frame[oos_col].astype(bool)
        else:
            mask = pd.Series(True, index=frame.index, dtype=bool)
        pair = frame.loc[mask, [pred_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if pair.empty:
            continue
        predictions.append(pair[pred_col].astype(float).reset_index(drop=True))
        realized.append(pair[target_col].astype(float).reset_index(drop=True))

    if not predictions:
        return {
            "evaluation_rows": 0,
            "prediction_correlation": None,
            "rank_ic": None,
            "quantile_monotonicity": None,
            "quantile_count": 0,
        }

    prediction = pd.concat(predictions, ignore_index=True)
    realized_return = pd.concat(realized, ignore_index=True)
    from src.evaluation.model_diagnostics import (
        prediction_quantile_table,
        prediction_realized_metrics,
        quantile_monotonicity,
    )

    metrics = prediction_realized_metrics(prediction, realized_return)
    quantile_table = prediction_quantile_table(
        prediction,
        realized_return,
        expected_net_return=prediction,
        quantiles=quantiles,
    )
    monotonicity = quantile_monotonicity(quantile_table)
    return {
        "evaluation_rows": int(metrics.get("evaluation_rows", 0) or 0),
        "prediction_correlation": metrics.get("correlation"),
        "rank_ic": metrics.get("spearman_rank_correlation"),
        "calibration_slope": metrics.get("calibration_slope"),
        "directional_accuracy": metrics.get("directional_accuracy"),
        "quantile_monotonicity": monotonicity.get("monotonicity"),
        "quantile_increasing_steps": monotonicity.get("monotonic_increasing_steps"),
        "quantile_count": monotonicity.get("quantile_count"),
    }


def _weighted_signal_summary(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [dict(item) for item in summaries if int(dict(item).get("signal_rows", 0) or 0) > 0]
    if not valid:
        return {}
    total_rows = sum(int(item.get("signal_rows", 0) or 0) for item in valid)
    out: dict[str, Any] = {
        "evaluation_rows": int(sum(int(item.get("evaluation_rows", 0) or 0) for item in valid)),
        "signal_rows": int(total_rows),
        "executed_trade_count": int(sum(int(item.get("executed_trade_count", 0) or 0) for item in valid)),
    }
    for key in (
        "mean_abs_signal",
        "signal_turnover",
        "long_rate",
        "short_rate",
        "flat_rate",
        "trade_rate",
        "avg_signal_executed",
        "avg_pred_prob_executed",
        "avg_realized_r_executed",
    ):
        numerator = 0.0
        denominator = 0
        for item in valid:
            value = item.get(key)
            rows = int(item.get("signal_rows", 0) or 0)
            if value is None or rows <= 0:
                continue
            numerator += float(value) * rows
            denominator += rows
        out[key] = float(numerator / denominator) if denominator > 0 else None
    return out


def _target_realized_r_col(target_meta: dict[str, Any]) -> str | None:
    return (
        str(target_meta.get("oriented_r_col"))
        if target_meta.get("oriented_r_col") is not None
        else (str(target_meta.get("r_col")) if target_meta.get("r_col") is not None else None)
    )


def _candidate_success_rate(frame: pd.DataFrame, *, mask: pd.Series, label_col: str | None) -> float | None:
    if not label_col or label_col not in frame.columns:
        return None
    labels = pd.to_numeric(frame[label_col].reindex(frame.index), errors="coerce")
    valid = mask.reindex(frame.index).fillna(False).astype(bool) & labels.notna()
    if not bool(valid.any()):
        return None
    return float(labels.loc[valid].mean())


def _safe_float_sum(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    return float(numeric.sum()) if not numeric.empty else 0.0


def _orb_pnl_attribution(
    asset_frames: dict[str, pd.DataFrame],
    *,
    performance: PortfolioPerformance | BacktestResult,
    returns_col: str,
    returns_type: str,
    alignment: str,
) -> dict[str, dict[str, float]]:
    if hasattr(performance, "applied_weights"):
        applied_weights = getattr(performance, "applied_weights")
        if applied_weights is None:
            return {"pnl_by_asset": {}, "gross_pnl_by_asset": {}, "cost_by_asset": {}, "pnl_by_session": {}}
        weights = applied_weights.astype(float)
        costs = performance.costs.reindex(weights.index).fillna(0.0).astype(float)
    else:
        only_asset = next(iter(sorted(asset_frames)))
        weights = pd.DataFrame({only_asset: performance.positions.astype(float)})
        costs = performance.costs.reindex(weights.index).fillna(0.0).astype(float)

    returns_by_asset: dict[str, pd.Series] = {}
    session_by_asset: dict[str, pd.Series] = {}
    for asset, frame in sorted(asset_frames.items()):
        if returns_col not in frame.columns:
            continue
        returns = frame[returns_col].astype(float)
        if returns_type == "log":
            returns = np.expm1(returns)
        returns_by_asset[asset] = returns
        if "orb_session_name" in frame.columns:
            session_by_asset[asset] = frame["orb_session_name"].shift(1)

    if not returns_by_asset:
        return {"pnl_by_asset": {}, "gross_pnl_by_asset": {}, "cost_by_asset": {}, "pnl_by_session": {}}

    returns_df = pd.concat(returns_by_asset, axis=1, join=alignment).sort_index()
    if isinstance(returns_df.columns, pd.MultiIndex):
        returns_df.columns = returns_df.columns.get_level_values(0)
    returns_df = returns_df.reindex(index=weights.index, columns=weights.columns)
    prev_weights = weights.shift(1).fillna(0.0)
    gross_contrib = (prev_weights * returns_df.fillna(0.0)).astype(float)
    turnover_by_asset = weights.diff().abs().fillna(weights.abs()).astype(float)
    turnover_total = turnover_by_asset.sum(axis=1).replace(0.0, np.nan)
    cost_alloc = turnover_by_asset.div(turnover_total, axis=0).mul(costs, axis=0).fillna(0.0)
    net_contrib = gross_contrib - cost_alloc

    pnl_by_asset = {str(col): _safe_float_sum(net_contrib[col]) for col in net_contrib.columns}
    gross_pnl_by_asset = {str(col): _safe_float_sum(gross_contrib[col]) for col in gross_contrib.columns}
    cost_by_asset = {str(col): _safe_float_sum(cost_alloc[col]) for col in cost_alloc.columns}

    pnl_by_session: dict[str, float] = {}
    for asset, sessions in session_by_asset.items():
        if asset not in net_contrib.columns:
            continue
        aligned_sessions = sessions.reindex(net_contrib.index)
        valid = aligned_sessions.notna() & prev_weights[asset].abs().gt(1e-12)
        if not bool(valid.any()):
            continue
        for session_name, values in net_contrib.loc[valid, asset].groupby(aligned_sessions.loc[valid].astype(str)):
            pnl_by_session[str(session_name)] = pnl_by_session.get(str(session_name), 0.0) + _safe_float_sum(values)

    return {
        "pnl_by_asset": pnl_by_asset,
        "gross_pnl_by_asset": gross_pnl_by_asset,
        "cost_by_asset": cost_by_asset,
        "pnl_by_session": dict(sorted(pnl_by_session.items())),
    }


def _compute_orb_diagnostics(
    asset_frames: dict[str, pd.DataFrame],
    *,
    performance: PortfolioPerformance | BacktestResult,
    signal_col: str | None,
    returns_col: str,
    returns_type: str,
    alignment: str,
    label_col: str | None,
    pred_is_oos_col: str = "pred_is_oos",
) -> dict[str, Any]:
    if not any("orb_candidate" in frame.columns for frame in asset_frames.values()):
        return {}

    candidate_count_by_asset: dict[str, int] = {}
    trade_count_by_asset: dict[str, int] = {}
    success_rate_by_asset: dict[str, float | None] = {}
    candidate_count_by_session: dict[str, int] = {}
    trade_count_by_session: dict[str, int] = {}
    success_values_by_session: dict[str, list[float]] = {}
    range_width_values: list[pd.Series] = []
    total_rows = 0
    total_candidates = 0
    total_accepted = 0
    long_candidates = 0
    short_candidates = 0

    for asset, frame in sorted(asset_frames.items()):
        if "orb_candidate" not in frame.columns:
            continue
        oos_mask = (
            frame[pred_is_oos_col].fillna(False).astype(bool)
            if pred_is_oos_col in frame.columns
            else pd.Series(True, index=frame.index, dtype=bool)
        )
        candidate = frame["orb_candidate"].fillna(0.0).astype(float).ne(0.0) & oos_mask
        side = frame.get("orb_side", pd.Series(0.0, index=frame.index)).astype(float)
        if signal_col and signal_col in frame.columns:
            accepted = candidate & frame[signal_col].fillna(0.0).astype(float).abs().gt(1e-12)
        else:
            accepted = pd.Series(False, index=frame.index, dtype=bool)

        sessions = frame.get("orb_session_name", pd.Series(pd.NA, index=frame.index)).astype("object")
        sessions = sessions.where(sessions.notna(), other="unknown").astype(str)
        candidate_count = int(candidate.sum())
        accepted_count = int(accepted.sum())
        candidate_count_by_asset[asset] = candidate_count
        trade_count_by_asset[asset] = accepted_count
        success_rate_by_asset[asset] = _candidate_success_rate(frame, mask=candidate, label_col=label_col)
        total_rows += int(oos_mask.sum())
        total_candidates += candidate_count
        total_accepted += accepted_count
        long_candidates += int((candidate & side.gt(0.0)).sum())
        short_candidates += int((candidate & side.lt(0.0)).sum())

        if "orb_range_width_atr" in frame.columns and candidate_count > 0:
            range_width_values.append(frame.loc[candidate, "orb_range_width_atr"].astype(float))

        for session_name, count in candidate.groupby(sessions).sum().items():
            if session_name == "unknown":
                continue
            candidate_count_by_session[session_name] = candidate_count_by_session.get(session_name, 0) + int(count)
        for session_name, count in accepted.groupby(sessions).sum().items():
            if session_name == "unknown":
                continue
            trade_count_by_session[session_name] = trade_count_by_session.get(session_name, 0) + int(count)
        if label_col and label_col in frame.columns:
            labels = pd.to_numeric(frame[label_col], errors="coerce")
            valid = candidate & labels.notna()
            for session_name, values in labels.loc[valid].groupby(sessions.loc[valid]):
                if session_name == "unknown":
                    continue
                success_values_by_session.setdefault(str(session_name), []).extend(values.astype(float).tolist())

    pnl_payload = _orb_pnl_attribution(
        asset_frames,
        performance=performance,
        returns_col=returns_col,
        returns_type=returns_type,
        alignment=alignment,
    )
    range_values = pd.concat(range_width_values).dropna() if range_width_values else pd.Series(dtype=float)
    success_rates = {
        session: float(np.mean(values)) if values else None
        for session, values in sorted(success_values_by_session.items())
    }
    breakout_success_values = [
        value
        for value in success_rate_by_asset.values()
        if value is not None and np.isfinite(float(value))
    ]
    primary = {
        "orb_candidate_count": int(total_candidates),
        "orb_candidate_rate": float(total_candidates / max(total_rows, 1)),
        "orb_accepted_trade_count": int(total_accepted),
        "orb_long_candidate_count": int(long_candidates),
        "orb_short_candidate_count": int(short_candidates),
        "average_orb_range_width_atr": float(range_values.mean()) if not range_values.empty else None,
        "breakout_success_rate": float(np.mean(breakout_success_values)) if breakout_success_values else None,
    }
    return {
        **primary,
        "candidate_count_by_asset": dict(sorted(candidate_count_by_asset.items())),
        "trade_count_by_asset": dict(sorted(trade_count_by_asset.items())),
        "candidate_count_by_session": dict(sorted(candidate_count_by_session.items())),
        "trade_count_by_session": dict(sorted(trade_count_by_session.items())),
        "success_rate_by_asset": dict(sorted(success_rate_by_asset.items())),
        "success_rate_by_session": success_rates,
        **pnl_payload,
        "primary_summary_fields": primary,
    }


def _compute_ftmo_objective(
    *,
    primary_summary: dict[str, Any],
    ftmo_metrics: dict[str, float],
    weekly_return_target: float | None,
    weekly_drawdown_limit: float | None,
) -> dict[str, float]:
    target_scale = abs(float(weekly_return_target)) if weekly_return_target not in (None, 0.0) else 1.0
    drawdown_scale = abs(float(weekly_drawdown_limit)) if weekly_drawdown_limit not in (None, 0.0) else 1.0
    mean_weekly_component = float(ftmo_metrics.get("weekly_return_mean", 0.0) / target_scale)
    target_hit_component = float(ftmo_metrics.get("weekly_target_hit_ratio", 0.0))
    instability_penalty = float(ftmo_metrics.get("weekly_return_std", 0.0) / target_scale)
    weekly_drawdown_penalty = float(abs(min(ftmo_metrics.get("worst_weekly_drawdown", 0.0), 0.0)) / drawdown_scale)
    weekly_breach_penalty = float(
        ftmo_metrics.get("weekly_drawdown_breach_count", 0.0) / max(ftmo_metrics.get("week_count", 0.0), 1.0)
    )
    daily_breach_penalty = float(
        ftmo_metrics.get("daily_loss_breach_count", 0.0) / max(ftmo_metrics.get("day_count", 0.0), 1.0)
    )
    max_loss_penalty = float(ftmo_metrics.get("max_total_loss_breach_count", 0.0))
    cost_penalty = float(primary_summary.get("cost_to_gross_pnl", 0.0) or 0.0)
    concentration_penalty = float(ftmo_metrics.get("best_day_concentration", 0.0) or 0.0)
    ftmo_score = (
        mean_weekly_component
        + target_hit_component
        - instability_penalty
        - weekly_drawdown_penalty
        - weekly_breach_penalty
        - daily_breach_penalty
        - max_loss_penalty
        - cost_penalty
        - concentration_penalty
    )
    return {
        "score": float(ftmo_score),
        "mean_weekly_component": mean_weekly_component,
        "target_hit_component": target_hit_component,
        "instability_penalty": instability_penalty,
        "weekly_drawdown_penalty": weekly_drawdown_penalty,
        "weekly_breach_penalty": weekly_breach_penalty,
        "daily_breach_penalty": daily_breach_penalty,
        "max_loss_penalty": max_loss_penalty,
        "cost_penalty": cost_penalty,
        "concentration_penalty": concentration_penalty,
    }


def _mark_to_market_primary_fields(performance: Any) -> dict[str, float]:
    summary = dict(getattr(performance, "mark_to_market_summary", {}) or {})
    if not summary:
        return {}
    fields: dict[str, float] = {}
    for key in ("cumulative_return", "annualized_return", "sharpe", "max_drawdown", "profit_factor"):
        if key in summary:
            fields[f"mtm_{key}"] = summary[key]
    return fields


def build_single_asset_evaluation(
    asset: str,
    df: pd.DataFrame,
    *,
    performance: BacktestResult,
    model_meta: dict[str, Any],
    periods_per_year: int,
    backtest_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trade_diagnostics = _trade_diagnostics_from_trades(performance.trades)
    c2_diagnostics = compute_c2_regime_aware_momentum_diagnostics(
        df,
        performance=performance,
        signal_col=str(dict(backtest_cfg or {}).get("signal_col", "c2_signal")),
    )
    baseline_diagnostics = compute_baseline_vwap_rms_ema_ppo_mfi_atr_diagnostics(
        {asset: df},
        performance=performance,
        signal_col=str(dict(backtest_cfg or {}).get("signal_col", "signal_side")),
    )
    stc_diagnostics = compute_stc_roofing_hilbert_diagnostics(
        df,
        performance=performance,
        signal_col=str(dict(backtest_cfg or {}).get("signal_col", "stc_roofing_signal")),
    )
    ehlers_diagnostics = compute_ehlers_continuation_long_diagnostics(
        df,
        performance=performance,
        signal_col=str(dict(backtest_cfg or {}).get("signal_col", "ehlers_continuation_signal")),
    )
    ehlers_short_diagnostics = compute_ehlers_continuation_short_diagnostics(
        df,
        performance=performance,
        signal_col=str(dict(backtest_cfg or {}).get("signal_col", "ehlers_continuation_signal")),
    )
    primary_summary = dict(performance.summary)
    for key in ("trade_count", "average_r", "median_r"):
        if key in trade_diagnostics:
            primary_summary[key] = trade_diagnostics[key]
    primary_summary.update(_mark_to_market_primary_fields(performance))
    evaluation = EvaluationPayload(
        scope="timeline",
        primary_summary=primary_summary,
        timeline_summary=dict(performance.summary),
        extra={
            "trade_diagnostics": trade_diagnostics,
            "baseline_diagnostics": baseline_diagnostics,
            "c2_diagnostics": c2_diagnostics,
            "stc_roofing_hilbert_diagnostics": stc_diagnostics,
            "ehlers_continuation_long_diagnostics": ehlers_diagnostics,
            "ehlers_continuation_short_diagnostics": ehlers_short_diagnostics,
            "mark_to_market_summary": dict(getattr(performance, "mark_to_market_summary", {}) or {}),
        },
    ).to_dict()

    pred_is_oos_col = str(model_meta.get("pred_is_oos_col") or "pred_is_oos")
    if pred_is_oos_col not in df.columns:
        return evaluation

    oos_mask = df[pred_is_oos_col].reindex(performance.returns.index).fillna(False).astype(bool)
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
    target_meta = dict(model_meta.get("target", {}) or {})
    policy_summary = dict(model_meta.get("oos_policy_summary", {}) or {})
    policy_summary.update(
        _signal_execution_summary(
            df,
            signal_col=str(dict(backtest_cfg or {}).get("signal_col", "")),
            oos_mask=oos_mask,
            prob_col=model_meta.get("pred_prob_col"),
            realized_r_col=_target_realized_r_col(target_meta),
            execution=performance.positions,
        )
    )
    orb_diagnostics = _compute_orb_diagnostics(
        {asset: df},
        performance=performance,
        signal_col=str(dict(backtest_cfg or {}).get("signal_col", "")),
        returns_col=str(dict(backtest_cfg or {}).get("returns_col", "")),
        returns_type=str(dict(backtest_cfg or {}).get("returns_type", "simple")),
        alignment="inner",
        label_col=str(target_meta.get("label_col")) if target_meta.get("label_col") is not None else None,
        pred_is_oos_col=pred_is_oos_col,
    )
    primary_summary = dict(oos_summary or performance.summary)
    primary_summary.update(dict(orb_diagnostics.get("primary_summary_fields", {}) or {}))
    for key in ("trade_count", "average_r", "median_r"):
        if key in trade_diagnostics:
            primary_summary[key] = trade_diagnostics[key]
    primary_summary.update(_mark_to_market_primary_fields(performance))
    for key in ("flat_rate", "long_rate", "short_rate"):
        if policy_summary.get(key) is not None:
            primary_summary[key] = policy_summary[key]

    return EvaluationPayload(
        scope="strict_oos_only",
        primary_summary=primary_summary,
        timeline_summary=dict(performance.summary),
        oos_only_summary=oos_summary,
        extra={
            "oos_rows": int(oos_mask.sum()),
            "oos_coverage": float(oos_mask.mean()) if len(oos_mask) > 0 else 0.0,
            "fold_backtest_summaries": fold_summaries,
            "model_oos_summary": dict(model_meta.get("oos_classification_summary", {}) or {}),
            "model_oos_regression_summary": dict(model_meta.get("oos_regression_summary", {}) or {}),
            "model_oos_volatility_summary": dict(model_meta.get("oos_volatility_summary", {}) or {}),
            "model_oos_policy_summary": policy_summary,
            "orb_diagnostics": orb_diagnostics,
            "trade_diagnostics": trade_diagnostics,
            "baseline_diagnostics": baseline_diagnostics,
            "c2_diagnostics": c2_diagnostics,
            "stc_roofing_hilbert_diagnostics": stc_diagnostics,
            "ehlers_continuation_long_diagnostics": ehlers_diagnostics,
            "ehlers_continuation_short_diagnostics": ehlers_short_diagnostics,
            "mark_to_market_summary": dict(getattr(performance, "mark_to_market_summary", {}) or {}),
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
    risk_cfg: dict[str, Any] | None = None,
    backtest_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trade_diagnostics = _trade_diagnostics_from_trades(getattr(performance, "trades", None))
    baseline_diagnostics = compute_baseline_vwap_rms_ema_ppo_mfi_atr_diagnostics(
        asset_frames,
        performance=performance,
        signal_col=str(dict(backtest_cfg or {}).get("signal_col", "signal_side")),
    )
    primary_summary = dict(performance.summary)
    for key in ("trade_count", "average_r", "median_r"):
        if key in trade_diagnostics:
            primary_summary[key] = trade_diagnostics[key]
    primary_summary.update(_mark_to_market_primary_fields(performance))
    evaluation = EvaluationPayload(
        scope="timeline",
        primary_summary=primary_summary,
        timeline_summary=dict(performance.summary),
        extra={
            "trade_diagnostics": trade_diagnostics,
            "baseline_diagnostics": baseline_diagnostics,
            "mark_to_market_summary": dict(getattr(performance, "mark_to_market_summary", {}) or {}),
            "risk_guard_summary": dict(performance.risk_guard_summary or {}),
        },
    ).to_dict()

    if not model_meta:
        return evaluation

    pred_is_oos_col = str(model_meta.get("pred_is_oos_col") or "pred_is_oos")
    oos_by_asset: dict[str, pd.Series] = {}
    if "per_asset" in model_meta:
        for asset, asset_meta in sorted(dict(model_meta.get("per_asset", {}) or {}).items()):
            asset_pred_is_oos_col = str(dict(asset_meta or {}).get("pred_is_oos_col") or pred_is_oos_col)
            frame = asset_frames.get(asset)
            if frame is not None and asset_pred_is_oos_col in frame.columns:
                oos_by_asset[asset] = frame[asset_pred_is_oos_col].astype(float)
    elif pred_is_oos_col in next(iter(asset_frames.values())).columns:
        only_asset = next(iter(sorted(asset_frames)))
        oos_by_asset[only_asset] = asset_frames[only_asset][pred_is_oos_col].astype(float)

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
    primary_summary = dict(oos_summary or performance.summary)
    for key in (
        "trade_count",
        "position_change_count",
        "rebalance_count",
        "discrete_trade_count",
        "barrier_trade_count",
    ):
        if key in performance.summary:
            primary_summary[key] = performance.summary[key]
    for key in ("trade_count", "average_r", "median_r"):
        if key in trade_diagnostics:
            primary_summary[key] = trade_diagnostics[key]
    primary_summary.update(_mark_to_market_primary_fields(performance))
    portfolio_guard_cfg = dict(dict(risk_cfg or {}).get("portfolio_guard", {}) or {})
    ftmo_metrics = compute_ftmo_style_metrics(
        net_returns=performance.net_returns.loc[oos_mask],
        weekly_return_target=portfolio_guard_cfg.get("weekly_return_target"),
        max_daily_loss=portfolio_guard_cfg.get("max_daily_loss"),
        weekly_drawdown_limit=portfolio_guard_cfg.get("weekly_drawdown"),
        max_total_loss=portfolio_guard_cfg.get("max_total_loss"),
        weekly_anchor=str(portfolio_guard_cfg.get("weekly_anchor", "W-FRI") or "W-FRI"),
    )
    ftmo_objective = _compute_ftmo_objective(
        primary_summary=primary_summary,
        ftmo_metrics=ftmo_metrics,
        weekly_return_target=portfolio_guard_cfg.get("weekly_return_target"),
        weekly_drawdown_limit=portfolio_guard_cfg.get("weekly_drawdown"),
    )
    fold_summaries = build_portfolio_fold_backtest_summaries(
        asset_frames=asset_frames,
        performance=performance,
        model_meta=model_meta,
        periods_per_year=periods_per_year,
    )
    signal_col = str(dict(backtest_cfg or {}).get("signal_col", ""))
    per_asset_policy: list[dict[str, Any]] = []
    per_asset_policy_map: dict[str, dict[str, Any]] = {}
    if "per_asset" in model_meta:
        for asset, meta in sorted(dict(model_meta.get("per_asset", {}) or {}).items()):
            frame = asset_frames.get(asset)
            if frame is None:
                continue
            asset_pred_is_oos_col = str(dict(meta or {}).get("pred_is_oos_col") or pred_is_oos_col)
            asset_oos = frame[asset_pred_is_oos_col].astype(bool) if asset_pred_is_oos_col in frame.columns else None
            weights = None
            if performance.applied_weights is not None and asset in performance.applied_weights.columns:
                weights = performance.applied_weights[asset]
            target_meta = dict(meta.get("target", {}) or {})
            summary = _signal_execution_summary(
                frame,
                signal_col=signal_col,
                oos_mask=asset_oos,
                prob_col=meta.get("pred_prob_col"),
                realized_r_col=_target_realized_r_col(target_meta),
                execution=weights,
            )
            per_asset_policy.append(summary)
            per_asset_policy_map[asset] = summary
    else:
        only_asset = next(iter(sorted(asset_frames)))
        frame = asset_frames[only_asset]
        asset_oos = frame[pred_is_oos_col].astype(bool) if pred_is_oos_col in frame.columns else None
        weights = None
        if performance.applied_weights is not None and only_asset in performance.applied_weights.columns:
            weights = performance.applied_weights[only_asset]
        summary = _signal_execution_summary(
            frame,
            signal_col=signal_col,
            oos_mask=asset_oos,
            prob_col=model_meta.get("pred_prob_col"),
            realized_r_col=_target_realized_r_col(dict(model_meta.get("target", {}) or {})),
            execution=weights,
        )
        per_asset_policy.append(summary)
        per_asset_policy_map[only_asset] = summary
    policy_summary = dict(model_meta.get("oos_policy_summary", {}) or {})
    policy_summary.update(_weighted_signal_summary(per_asset_policy))
    forecast_quality = _portfolio_forecast_quality_summary(
        asset_frames,
        model_meta=model_meta,
        signal_col=signal_col,
        quantiles=10,
    )
    target_meta = dict(model_meta.get("target", {}) or {})
    orb_diagnostics = _compute_orb_diagnostics(
        asset_frames,
        performance=performance,
        signal_col=signal_col,
        returns_col=str(dict(backtest_cfg or {}).get("returns_col", "")),
        returns_type=str(dict(backtest_cfg or {}).get("returns_type", "simple")),
        alignment=alignment,
        label_col=str(target_meta.get("label_col")) if target_meta.get("label_col") is not None else None,
        pred_is_oos_col=pred_is_oos_col,
    )
    primary_summary.update(dict(orb_diagnostics.get("primary_summary_fields", {}) or {}))
    for key in (
        "prediction_correlation",
        "rank_ic",
        "calibration_slope",
        "directional_accuracy",
        "quantile_monotonicity",
    ):
        if forecast_quality.get(key) is not None:
            primary_summary[key] = forecast_quality[key]
    for key in ("flat_rate", "long_rate", "short_rate"):
        if policy_summary.get(key) is not None:
            primary_summary[key] = policy_summary[key]
    return EvaluationPayload(
        scope="strict_oos_only",
        primary_summary=primary_summary,
        timeline_summary=dict(performance.summary),
        oos_only_summary=oos_summary,
        extra={
            "oos_active_dates": int(oos_mask.sum()),
            "oos_date_coverage": float(oos_mask.mean()) if len(oos_mask) > 0 else 0.0,
            "fold_backtest_summaries": fold_summaries,
            "ftmo_metrics": ftmo_metrics,
            "ftmo_objective": ftmo_objective,
            "risk_guard_summary": dict(performance.risk_guard_summary or {}),
            "feature_diagnostics": _portfolio_feature_diagnostics(model_meta),
            "model_oos_summary": dict(model_meta.get("oos_classification_summary", {}) or {}),
            "model_oos_regression_summary": dict(model_meta.get("oos_regression_summary", {}) or {}),
            "model_oos_volatility_summary": dict(model_meta.get("oos_volatility_summary", {}) or {}),
            "model_oos_policy_summary": policy_summary,
            "forecast_quality": forecast_quality,
            "signal_diagnostics_by_asset": per_asset_policy_map,
            "orb_diagnostics": orb_diagnostics,
            "trade_diagnostics": trade_diagnostics,
            "baseline_diagnostics": baseline_diagnostics,
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
    pred_is_oos_col = str(meta.get("pred_is_oos_col") or "pred_is_oos")
    if not feature_cols or pred_is_oos_col not in df.columns:
        return None

    oos_mask = df[pred_is_oos_col].astype(bool)
    ref = df.loc[~oos_mask, feature_cols]
    cur = df.loc[oos_mask, feature_cols]
    if ref.empty or cur.empty:
        return None

    try:
        from src.monitoring.drift import compute_feature_drift
    except ModuleNotFoundError:
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
    "build_portfolio_fold_backtest_summaries",
    "build_portfolio_evaluation",
    "build_experiment_diagnostics",
    "build_experiment_report_markdown",
    "build_single_asset_evaluation",
    "compute_monitoring_for_asset",
    "compute_monitoring_report",
    "compute_subset_metrics",
]
