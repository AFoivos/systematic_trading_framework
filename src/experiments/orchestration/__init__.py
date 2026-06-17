from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_ATTRS = {
    "ExperimentResult": "src.experiments.orchestration.types",
    "aggregate_model_meta": "src.experiments.orchestration.model_stage",
    "align_asset_column": "src.experiments.orchestration.common",
    "apply_feature_steps": "src.experiments.orchestration.feature_stage",
    "apply_model_pipeline_to_assets": "src.experiments.orchestration.model_stage",
    "apply_model_step": "src.experiments.orchestration.model_stage",
    "apply_model_to_assets": "src.experiments.orchestration.model_stage",
    "apply_signal_step": "src.experiments.orchestration.feature_stage",
    "apply_signals_to_assets": "src.experiments.orchestration.feature_stage",
    "apply_steps_to_assets": "src.experiments.orchestration.feature_stage",
    "build_execution_output": "src.experiments.orchestration.execution_stage",
    "build_fold_backtest_summaries": "src.experiments.orchestration.reporting",
    "build_portfolio_constraints": "src.experiments.orchestration.backtest_stage",
    "build_portfolio_evaluation": "src.experiments.orchestration.reporting",
    "build_single_asset_evaluation": "src.experiments.orchestration.reporting",
    "build_storage_context": "src.experiments.orchestration.common",
    "compute_monitoring_for_asset": "src.experiments.orchestration.reporting",
    "compute_monitoring_report": "src.experiments.orchestration.reporting",
    "compute_subset_metrics": "src.experiments.orchestration.reporting",
    "data_stats_payload": "src.experiments.orchestration.common",
    "default_dataset_id": "src.experiments.orchestration.common",
    "load_asset_frames": "src.experiments.orchestration.data_stage",
    "pit_config_hash": "src.experiments.orchestration.common",
    "redact_sensitive_values": "src.experiments.orchestration.common",
    "resolve_symbols": "src.experiments.orchestration.common",
    "resolve_vol_col": "src.experiments.orchestration.backtest_stage",
    "resolved_feature_columns": "src.experiments.orchestration.common",
    "run_experiment_pipeline": "src.experiments.orchestration.pipeline",
    "run_portfolio_backtest": "src.experiments.orchestration.backtest_stage",
    "run_single_asset_backtest": "src.experiments.orchestration.backtest_stage",
    "save_artifacts": "src.experiments.orchestration.artifacts",
    "save_processed_snapshot_if_enabled": "src.experiments.orchestration.data_stage",
    "slugify": "src.experiments.orchestration.common",
    "snapshot_context_matches": "src.experiments.orchestration.common",
    "stable_json_dumps": "src.experiments.orchestration.common",
    "validate_returns_frame": "src.experiments.orchestration.backtest_stage",
    "validate_returns_series": "src.experiments.orchestration.backtest_stage",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_ATTRS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_LAZY_ATTRS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "ExperimentResult",
    "aggregate_model_meta",
    "align_asset_column",
    "apply_feature_steps",
    "apply_model_pipeline_to_assets",
    "apply_model_step",
    "apply_model_to_assets",
    "apply_signal_step",
    "apply_signals_to_assets",
    "apply_steps_to_assets",
    "build_execution_output",
    "build_fold_backtest_summaries",
    "build_portfolio_constraints",
    "build_portfolio_evaluation",
    "build_single_asset_evaluation",
    "build_storage_context",
    "compute_monitoring_for_asset",
    "compute_monitoring_report",
    "compute_subset_metrics",
    "data_stats_payload",
    "default_dataset_id",
    "load_asset_frames",
    "pit_config_hash",
    "redact_sensitive_values",
    "resolve_symbols",
    "resolve_vol_col",
    "resolved_feature_columns",
    "run_experiment_pipeline",
    "run_portfolio_backtest",
    "run_single_asset_backtest",
    "save_artifacts",
    "save_processed_snapshot_if_enabled",
    "slugify",
    "snapshot_context_matches",
    "stable_json_dumps",
    "validate_returns_frame",
    "validate_returns_series",
]
