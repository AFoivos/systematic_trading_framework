from __future__ import annotations

from pathlib import Path

from src.experiments.contracts import validate_data_contract
from src.experiments.orchestration import (
    ExperimentResult,
    align_asset_column as _align_asset_column,
    apply_feature_steps as _apply_feature_steps,
    apply_model_pipeline_to_assets as _apply_model_pipeline_to_assets,
    apply_model_step as _apply_model_step,
    apply_model_to_assets as _apply_model_to_assets,
    apply_signal_step as _apply_signal_step,
    apply_signals_to_assets as _apply_signals_to_assets,
    apply_steps_to_assets as _apply_steps_to_assets,
    build_execution_output as _build_execution_output,
    build_fold_backtest_summaries as _build_fold_backtest_summaries,
    build_portfolio_constraints as _build_portfolio_constraints,
    build_portfolio_evaluation as _build_portfolio_evaluation,
    build_single_asset_evaluation as _build_single_asset_evaluation,
    build_storage_context as _build_storage_context,
    compute_monitoring_for_asset as _compute_monitoring_for_asset,
    compute_monitoring_report as _compute_monitoring_report,
    compute_subset_metrics as _compute_subset_metrics,
    data_stats_payload as _data_stats_payload,
    default_dataset_id as _default_dataset_id,
    pit_config_hash as _pit_config_hash,
    redact_sensitive_values as _redact_sensitive_values,
    resolve_symbols as _resolve_symbols,
    resolve_vol_col as _resolve_vol_col,
    resolved_feature_columns as _resolved_feature_columns,
    run_experiment_pipeline,
    run_portfolio_backtest as _run_portfolio_backtest,
    run_single_asset_backtest as _run_single_asset_backtest,
    save_artifacts as _save_artifacts,
    save_processed_snapshot_if_enabled,
    slugify as _slugify,
    snapshot_context_matches as _snapshot_context_matches,
    stable_json_dumps as _stable_json_dumps,
    validate_returns_frame as _validate_returns_frame,
    validate_returns_series as _validate_returns_series,
)
from src.src_data.loaders import load_ohlcv, load_ohlcv_panel
from src.src_data.pit import apply_pit_hardening
from src.src_data.validation import validate_ohlcv


def _load_asset_frames(
    data_cfg: dict[str, object],
):
    from src.experiments.orchestration import load_asset_frames

    return load_asset_frames(
        data_cfg,
        load_ohlcv_fn=load_ohlcv,
        load_ohlcv_panel_fn=load_ohlcv_panel,
        apply_pit_hardening_fn=apply_pit_hardening,
        validate_ohlcv_fn=validate_ohlcv,
        validate_data_contract_fn=validate_data_contract,
    )


def run_experiment(config_path: str | Path) -> ExperimentResult:
    """
    Run experiment end to end while keeping `src.experiments.runner` as the stable entrypoint.
    """
    return run_experiment_pipeline(
        config_path,
        load_asset_frames_fn=_load_asset_frames,
        save_processed_snapshot_fn=save_processed_snapshot_if_enabled,
    )


def print_experiment_completion(result: ExperimentResult) -> None:
    """
    Render only the concise completion summary to stdout.

    Artifacts are still created and returned in `result.artifacts`, but are intentionally omitted
    from terminal output to keep interactive runs less noisy.
    """
    print("Experiment completed")
    print("Primary summary:")
    for k, v in result.evaluation.get("primary_summary", {}).items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a config-based trading experiment.")
    parser.add_argument("config", help="Path to experiment YAML (relative to config/ or absolute).")
    args = parser.parse_args()

    result = run_experiment(args.config)
    print_experiment_completion(result)


__all__ = [
    "ExperimentResult",
    "_align_asset_column",
    "_apply_feature_steps",
    "_apply_model_pipeline_to_assets",
    "_apply_model_step",
    "_apply_model_to_assets",
    "_apply_signal_step",
    "_apply_signals_to_assets",
    "_apply_steps_to_assets",
    "_build_execution_output",
    "_build_fold_backtest_summaries",
    "_build_portfolio_constraints",
    "_build_portfolio_evaluation",
    "_build_single_asset_evaluation",
    "_build_storage_context",
    "_compute_monitoring_for_asset",
    "_compute_monitoring_report",
    "_compute_subset_metrics",
    "_data_stats_payload",
    "_default_dataset_id",
    "_load_asset_frames",
    "_pit_config_hash",
    "_redact_sensitive_values",
    "_resolve_symbols",
    "_resolve_vol_col",
    "_resolved_feature_columns",
    "_run_portfolio_backtest",
    "_run_single_asset_backtest",
    "_save_artifacts",
    "_slugify",
    "_snapshot_context_matches",
    "_stable_json_dumps",
    "_validate_returns_frame",
    "_validate_returns_series",
    "load_ohlcv",
    "load_ohlcv_panel",
    "print_experiment_completion",
    "run_experiment",
]
