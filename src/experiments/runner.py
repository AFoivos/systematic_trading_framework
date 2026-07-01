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
    Render a concise but useful completion log to stdout.

    The primary summary stays first for fast terminal scanning. Follow-up
    sections include enough model, diagnostics, monitoring, and artifact context
    to debug a run without dumping entire fold payloads or per-feature reports.
    """
    print("Experiment completed")
    print("Primary summary:")
    for k, v in result.evaluation.get("primary_summary", {}).items():
        print(f"  {k}: {v}")
    _print_evaluation_context(result.evaluation)
    _print_model_context(result.model_meta)
    _print_monitoring_context(result.monitoring)
    _print_artifact_context(result.artifacts)


def _print_mapping(title: str, payload: dict[str, object]) -> None:
    clean = {str(k): v for k, v in payload.items() if v is not None}
    if not clean:
        return
    print(f"{title}:")
    for key, value in clean.items():
        print(f"  {key}: {value}")


def _print_evaluation_context(evaluation: dict[str, object]) -> None:
    if not evaluation:
        return
    context_keys = (
        "scope",
        "oos_rows",
        "oos_coverage",
    )
    context = {key: evaluation.get(key) for key in context_keys if key in evaluation}
    _print_mapping("Evaluation context", context)


def _print_model_context(model_meta: dict[str, object]) -> None:
    if not model_meta:
        return
    overview_keys = (
        "model_kind",
        "n_folds",
        "train_rows",
        "test_pred_rows",
        "oos_rows",
        "oos_prediction_coverage",
        "pred_prob_col",
        "pred_is_oos_col",
    )
    overview = {key: model_meta.get(key) for key in overview_keys if key in model_meta}
    _print_mapping("Model overview", overview)

    classification = dict(model_meta.get("oos_classification_summary", {}) or {})
    _print_mapping(
        "OOS classification",
        {
            "evaluation_rows": classification.get("evaluation_rows"),
            "accuracy": classification.get("accuracy"),
            "roc_auc": classification.get("roc_auc"),
            "log_loss": classification.get("log_loss"),
            "brier": classification.get("brier"),
            "positive_rate": classification.get("positive_rate"),
        },
    )

    prediction = dict(model_meta.get("prediction_diagnostics", {}) or {})
    prediction_dist = dict(prediction.get("probability_distribution", {}) or prediction.get("prediction_distribution", {}) or {})
    _print_mapping(
        "Prediction diagnostics",
        {
            "oos_rows": prediction.get("oos_rows"),
            "predicted_rows": prediction.get("predicted_rows"),
            "missing_oos_prediction_rows": prediction.get("missing_oos_prediction_rows"),
            "oos_prediction_coverage": prediction.get("oos_prediction_coverage"),
            "alignment_ok": prediction.get("alignment_ok"),
            "prob_min": prediction_dist.get("min"),
            "prob_q25": prediction_dist.get("q25"),
            "prob_median": prediction_dist.get("median"),
            "prob_q75": prediction_dist.get("q75"),
            "prob_max": prediction_dist.get("max"),
        },
    )

    _print_mapping("Missing/value diagnostics", dict(model_meta.get("missing_value_diagnostics", {}) or {}))

    target = dict(model_meta.get("target", {}) or {})
    _print_mapping(
        "Target diagnostics",
        {
            "kind": target.get("kind"),
            "candidate_rows": target.get("candidate_rows"),
            "labeled_rows": target.get("labeled_rows"),
            "positive_rate": target.get("positive_rate"),
            "profit_barrier_count": target.get("profit_barrier_count"),
            "stop_barrier_count": target.get("stop_barrier_count"),
            "neutral_count": target.get("neutral_count"),
        },
    )


def _print_monitoring_context(monitoring: dict[str, object]) -> None:
    if not monitoring:
        return
    _print_mapping(
        "Monitoring",
        {
            "asset_count": monitoring.get("asset_count"),
            "feature_count": monitoring.get("feature_count"),
            "drifted_feature_count": monitoring.get("drifted_feature_count"),
        },
    )
    per_asset = dict(monitoring.get("per_asset", {}) or {})
    for asset, raw_payload in per_asset.items():
        payload = dict(raw_payload or {})
        per_feature = dict(payload.get("per_feature", {}) or {})
        drifted = [
            str(name)
            for name, feature_payload in per_feature.items()
            if bool(dict(feature_payload or {}).get("is_drifted", False))
        ]
        if drifted:
            print(f"  {asset} drifted_features: {', '.join(drifted[:10])}")


def _print_artifact_context(artifacts: dict[str, str]) -> None:
    if not artifacts:
        return
    preferred_keys = (
        "run_dir",
        "summary",
        "report",
        "report_html",
        "run_metadata",
        "prediction_diagnostics",
        "missing_value_diagnostics",
        "monitoring",
        "fold_model_summary",
        "trade_events",
    )
    shown = {key: artifacts.get(key) for key in preferred_keys if artifacts.get(key)}
    _print_mapping("Artifacts", shown)
    remaining = max(0, len(artifacts) - len(shown))
    if remaining:
        print(f"  additional_artifacts: {remaining}")


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
