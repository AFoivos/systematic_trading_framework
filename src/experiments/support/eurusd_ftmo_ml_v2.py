from __future__ import annotations

import hashlib
import importlib.metadata
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.evaluation.metrics import annualized_return, max_drawdown, sharpe_ratio
from src.evaluation.model_metrics import binary_classification_metrics

from src.backtesting.eurusd_ftmo_ml_v2 import compute_strategy_metrics, run_bar_backtest
from src.evaluation.eurusd_ftmo_ml_v2_walk_forward import annual_walk_forward
from src.features.eurusd_ftmo_ml_v2 import build_candidate_feature_frame
from src.features.eurusd_ftmo_ml_v2_contract import feature_schema_hash, verify_reference_feature_contract
from src.signals.eurusd_ftmo_ml_v2_candidates import generate_candidates, validate_and_prepare_market_data
from src.signals.eurusd_ftmo_ml_v2_signal import aggregate_candidate_signals, attach_oos_scores
from src.targets.eurusd_ftmo_candidate_meta import attach_candidate_targets
from src.utils.eurusd_ftmo_ml_v2_contract import (
    COMMON_MODEL_PARAMS,
    FEATURE_COLUMNS,
    MODEL_NUM_LEAVES,
    PERIODS_PER_YEAR,
    REFERENCE_FILENAMES,
    REFERENCE_HASHES,
    STRATEGY_NAME,
    STRATEGY_VERSION,
    PULLBACK_COMPONENTS,
)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_json_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, default=str, allow_nan=False),
        encoding="utf-8",
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(float(value)) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def verify_and_copy_references(source_dir: Path, destination_dir: Path) -> dict[str, Any]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for filename in REFERENCE_FILENAMES:
        source = source_dir / filename
        expected_hash = REFERENCE_HASHES.get(filename)
        if not source.is_file():
            rows.append({"filename": filename, "status": "missing", "expected_sha256": expected_hash})
            continue
        actual_hash = file_sha256(source)
        if expected_hash is not None and actual_hash != expected_hash:
            rows.append(
                {
                    "filename": filename,
                    "status": "hash_mismatch",
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                }
            )
            continue
        destination = destination_dir / filename
        shutil.copy2(source, destination)
        if file_sha256(destination) != actual_hash:
            raise IOError(f"Copied reference failed hash verification: {filename}")
        rows.append(
            {
                "filename": filename,
                "status": "copied",
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
            }
        )
    manifest = {
        "source_directory": str(source_dir),
        "destination_directory": str(destination_dir),
        "files": rows,
        "missing_count": int(sum(row["status"] == "missing" for row in rows)),
        "hash_mismatch_count": int(sum(row["status"] == "hash_mismatch" for row in rows)),
        "copied_count": int(sum(row["status"] == "copied" for row in rows)),
    }
    _write_json(destination_dir / "reference_manifest.json", manifest)
    return manifest


def reconstruction_assumptions(reference_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "documented_reconstruction_not_exact_reproduction",
        "authoritative_reference_manifest": reference_manifest,
        "exactly_recovered": [
            "fixed 151-column order from the supplied implementation brief",
            "four pullback component parameters and state-machine rules",
            "session-fade schedule and filter",
            "three LightGBM parameter sets",
            "annual walk-forward schedule",
            "confidence, aggregation, volatility, sizing, and FTMO overlay constants",
        ],
        "reconstructed_from_documented_formula": [
            "candidate generation and executable next-open labels",
            "bar and candidate feature composition",
            "OOS model training and scoring",
            "bar-level target aggregation and account simulation",
        ],
        "inferred_because_original_source_not_persisted": [
            "rolling standard-deviation ddof=1 where the brief says pandas rolling_std without a ddof",
            "bar-level equity marking at each M30 open for FTMO daily-loss approximation",
            "baseline-only cost_stress.csv when no reference stress grid is available",
        ],
        "not_reproducible_from_available_artifacts": [
            "bit-for-bit annual fold models",
            "candidate-level historical reference predictions",
            "reference candidate signal fixtures",
            "exact historical parity when authoritative data or files are missing",
        ],
        "forbidden_substitutions": [
            "no synthetic replacement for a missing reference file",
            "no parameter optimization to close a parity gap",
            "no RL, DL, calibration, imputation, scaling, or additional models",
        ],
    }


def parity_report_markdown(reference_manifest: dict[str, Any], *, experiment_completed: bool) -> str:
    statuses = {row["filename"]: row["status"] for row in reference_manifest["files"]}
    missing = [name for name, status in statuses.items() if status == "missing"]
    mismatched = [name for name, status in statuses.items() if status == "hash_mismatch"]
    copied = [name for name, status in statuses.items() if status == "copied"]
    lines = [
        "# EURUSD FTMO ML v2 parity report",
        "",
        "> Status: documented reconstruction; not an exact reproduction.",
        "",
        "## Exactly recovered from artifacts",
        "",
        *(f"- `{name}`" for name in copied),
        *( ["- None: no authoritative artifact was available at the configured source path."] if not copied else []),
        "",
        "## Reconstructed from documented formula",
        "",
        "- Four independent pullback state machines and causal next-open execution.",
        "- Session fade using the previous completed UTC daily EMA20 regime.",
        "- Fixed 151-feature candidate matrix and three-model LightGBM ensemble.",
        "- Annual OOS schedule, frozen 2025 holdout, confidence aggregation, and FTMO overlays.",
        "",
        "## Inferred because the original source was not persisted",
        "",
        "- Rolling-standard-deviation `ddof=1` where the brief does not declare a ddof.",
        "- M30 open-to-open equity marking for the daily circuit-breaker approximation.",
        "- Baseline-only cost-stress output when the reference stress grid is unavailable.",
        "",
        "## Not reproducible from available artifacts",
        "",
        *(f"- Missing: `{name}`" for name in missing),
        *(f"- Hash mismatch: `{name}`" for name in mismatched),
        "- Original full v2 research-generation source and annual fold models were not supplied.",
        "- Candidate-level historical reference predictions and fixtures were not supplied.",
        f"- Full experiment completed: `{str(experiment_completed).lower()}`.",
        "",
        "Exact parity may only be claimed after candidate counts, model audit, and period metrics align within a declared tolerance.",
        "No parameters are optimized to close a parity gap.",
        "",
    ]
    return "\n".join(lines)


def _classification_diagnostics(scored: pd.DataFrame) -> dict[str, Any]:
    eligible = scored.loc[scored["pred_is_oos"].fillna(False) & scored["pred_score"].notna()].copy()
    base = binary_classification_metrics(eligible["target_positive_net"], eligible["pred_score"])
    distribution = eligible["pred_score"].describe(percentiles=[0.25, 0.5, 0.75]) if len(eligible) else pd.Series(dtype=float)
    per_year: dict[str, Any] = {}
    for year, group in eligible.groupby(pd.to_datetime(eligible["signal_timestamp"]).dt.year):
        metrics = binary_classification_metrics(group["target_positive_net"], group["pred_score"])
        accepted = group["pred_score"] > 0.60
        per_year[str(year)] = {
            "candidate_count": int(len(group)),
            "roc_auc": metrics.get("roc_auc"),
            "spearman_score_vs_net_return": float(group["pred_score"].corr(group["net_return"], method="spearman")),
            "raw_win_rate": float(group["target_positive_net"].mean()),
            "accepted_fraction_above_0_60": float(accepted.mean()),
            "accepted_win_rate": float(group.loc[accepted, "target_positive_net"].mean()) if accepted.any() else None,
            "accepted_mean_net_return": float(group.loc[accepted, "net_return"].mean()) if accepted.any() else None,
        }
    return {
        **base,
        "positive_rate": float(eligible["target_positive_net"].mean()) if len(eligible) else None,
        "prediction_coverage": float(eligible["pred_score"].notna().mean()) if len(eligible) else 0.0,
        "missing_predictions": int(eligible["pred_score"].isna().sum()),
        "probability_min": float(distribution.get("min", np.nan)) if len(distribution) else None,
        "probability_q25": float(distribution.get("25%", np.nan)) if len(distribution) else None,
        "probability_median": float(distribution.get("50%", np.nan)) if len(distribution) else None,
        "probability_q75": float(distribution.get("75%", np.nan)) if len(distribution) else None,
        "probability_max": float(distribution.get("max", np.nan)) if len(distribution) else None,
        "per_year": per_year,
    }


def _period_metrics(positions: pd.DataFrame) -> pd.DataFrame:
    periods = (
        ("Development 2022", "2022-01-01", "2023-01-01"),
        ("Validation 2023", "2023-01-01", "2024-01-01"),
        ("Validation 2024", "2024-01-01", "2025-01-01"),
        ("Development + validation 2022-2024", "2022-01-01", "2025-01-01"),
        ("Holdout audit 2025-2026-04", "2025-01-01", "2026-04-28"),
        ("Combined OOS 2022-2026-04", "2022-01-01", "2026-04-28"),
        ("Comparable OOS 2023-2026-04", "2023-01-01", "2026-04-28"),
    )
    rows: list[dict[str, Any]] = []
    for name, start, end in periods:
        subset = positions.loc[(positions.index >= start) & (positions.index < end)]
        returns = subset["net_return"] if len(subset) else pd.Series(dtype=float)
        daily = returns.groupby(returns.index.normalize()).apply(lambda values: (1.0 + values).prod() - 1.0) if len(returns) else pd.Series(dtype=float)
        monthly = returns.groupby(returns.index.to_period("M")).apply(lambda values: (1.0 + values).prod() - 1.0) if len(returns) else pd.Series(dtype=float)
        rows.append(
            {
                "period": name,
                "start": start,
                "end_exclusive": end,
                "sharpe": sharpe_ratio(returns, PERIODS_PER_YEAR),
                "cagr": annualized_return(returns, PERIODS_PER_YEAR),
                "mean_monthly_return": float(monthly.mean()) if len(monthly) else 0.0,
                "max_drawdown": max_drawdown(subset["equity"]) if len(subset) else 0.0,
                "worst_intraday_ftmo_day": float(daily.min()) if len(daily) else 0.0,
                "active_trading_days": int((daily != 0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _feature_manifest() -> dict[str, Any]:
    return {
        "feature_count": len(FEATURE_COLUMNS),
        "feature_order": list(FEATURE_COLUMNS),
        "feature_schema_hash": feature_schema_hash(),
        "timing": "sampled at candidate signal close before next-open execution",
        "missing_value_policy": "infinities are converted to NaN; LightGBM handles NaN natively",
        "registered_components": [
            "returns", "atr", "adx", "rsi", "trend", "volatility", "range_position",
            "rolling_zscore", "atr_scaled_distance", "difference", "ratio", "lag", "affine",
            "log", "product", "path_efficiency", "rolling_autocorrelation", "completed_trade_history",
        ],
        "formulas_source": "attached EURUSD FTMO ML Meta-Ensemble v2 implementation brief, sections 9-11",
        "feature_groups": {
            "momentum": {"horizons": [1, 2, 4, 8, 16, 24, 48, 96, 192], "formulas": ["log(mid_close/mid_close.shift(h))/(rolling_std(logret1,48)*sqrt(h))", "(mid_close-mid_close.shift(h))/atr48"]},
            "ema_structure": {"spans": [8, 16, 32, 48, 96, 192, 384, 768], "formulas": ["(mid_close-EMA_span)/atr48", "(EMA_span-EMA_span.shift(8))/(atr48*sqrt(8))"]},
            "rsi": {"periods": [7, 14, 28, 56], "method": "Wilder", "normalization": "(RSI-50)/25"},
            "adx_di": {"period": 14, "method": "Wilder"},
            "volatility": {"rolling_windows": [8, 16, 48, 96, 192, 384], "ddof": 1},
            "range_breakout": {"windows": [24, 48, 96, 192, 384], "prior_range_shift": 1},
            "volume_zscore": {"windows": [48, 192, 960], "shift_statistics": 0, "ddof": 1},
            "path_efficiency": {"windows": [24, 48, 96, 192], "log_prices": True, "clip": True},
            "autocorrelation": {"windows": [48, 192], "lag": 1},
            "completed_trade_history": {"rolling_window": 20, "win_threshold": 0.0, "allow_same_timestamp": False},
            "direction_interactions": "direction multiplied by only the declared dir_* source columns",
        },
    }


def _validate_locked_config(cfg: dict[str, Any]) -> None:
    """Make the YAML authoritative while forbidding silent strategy drift."""
    checks = {
        "pipeline.kind": (dict(cfg.get("pipeline", {}) or {}).get("kind"), "eurusd_ftmo_ml_v2"),
        "strategy.symbol": (dict(cfg.get("strategy", {}) or {}).get("symbol"), "EURUSD"),
        "strategy.timeframe": (dict(cfg.get("strategy", {}) or {}).get("timeframe"), "30m"),
        "model.num_leaves": (tuple(dict(cfg.get("model", {}) or {}).get("num_leaves", ())), MODEL_NUM_LEAVES),
        "model.score_floor": (dict(cfg.get("model", {}) or {}).get("score_floor"), 0.60),
        "model.score_cap": (dict(cfg.get("model", {}) or {}).get("score_cap"), 0.80),
        "risk.base_notional_multiple": (dict(cfg.get("risk", {}) or {}).get("base_notional_multiple"), 22.0),
        "risk.daily_circuit_breaker": (dict(cfg.get("risk", {}) or {}).get("daily_circuit_breaker"), -0.0225),
    }
    for field, (actual, expected) in checks.items():
        if actual != expected:
            raise ValueError(f"Locked strategy config mismatch at {field}: expected {expected!r}, found {actual!r}.")
    model_params = dict(dict(cfg.get("model", {}) or {}).get("common_params", {}) or {})
    if model_params != COMMON_MODEL_PARAMS:
        raise ValueError("model.common_params must exactly match the locked LightGBM contract.")
    pullback = dict(dict(cfg.get("alpha", {}) or {}).get("pullback", {}) or {})
    configured_components = list(pullback.get("components", ()) or ())
    expected_components = [
        {
            "component_id": component.component_id,
            "ema_span": component.ema_span,
            "entry_atr": component.entry_atr,
            "exit_atr": component.exit_atr,
            "maximum_hold_bars": component.maximum_hold_bars,
            "adverse_z_stop": component.adverse_z_stop,
        }
        for component in PULLBACK_COMPONENTS
    ]
    if configured_components != expected_components:
        raise ValueError("alpha.pullback.components must exactly match the four locked components.")


def run_reconstruction(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _validate_locked_config(cfg)
    reference_cfg = dict(cfg.get("references", {}) or {})
    source_dir = Path(reference_cfg.get("source_dir", "/mnt/data"))
    destination_dir = Path(reference_cfg.get("destination_dir", "artifacts/reference/eurusd_ftmo_ml_v2"))
    manifest = verify_and_copy_references(source_dir, destination_dir)
    assumptions = reconstruction_assumptions(manifest)
    _write_json(destination_dir / "reconstruction_assumptions.json", assumptions)
    (destination_dir / "parity_report.md").write_text(
        parity_report_markdown(manifest, experiment_completed=False), encoding="utf-8"
    )
    blocking = [row for row in manifest["files"] if row["filename"] == "eurusd_30m.csv" and row["status"] != "copied"]
    if blocking:
        raise FileNotFoundError(
            "Authoritative eurusd_30m.csv is missing or failed its required hash; "
            f"see {destination_dir / 'reference_manifest.json'}."
        )
    if manifest["hash_mismatch_count"]:
        raise ValueError("One or more authoritative reference artifacts failed hash verification.")
    bundle_path = destination_dir / "eurusd_ftmo_ml_v2_model_bundle.joblib"
    dictionary_path = destination_dir / "eurusd_ftmo_ml_v2_feature_dictionary.csv"
    if bundle_path.is_file() and dictionary_path.is_file():
        verify_reference_feature_contract(bundle_path, dictionary_path)

    data_path = destination_dir / "eurusd_30m.csv"
    raw = pd.read_csv(data_path)
    market, data_validation = validate_and_prepare_market_data(raw, enforce_reference_shape=True)
    candidates = attach_candidate_targets(generate_candidates(market), market)
    candidate_features = build_candidate_feature_frame(market, candidates)
    walk = annual_walk_forward(candidate_features)
    scored = attach_oos_scores(candidate_features, walk.predictions)
    signals = aggregate_candidate_signals(market.index, scored)
    backtest = run_bar_backtest(market, signals)
    backtest.metrics = compute_strategy_metrics(positions=backtest.positions, orders=backtest.orders, candidates=scored)

    output_dir = Path(dict(cfg.get("logging", {}) or {}).get("output_dir", "artifacts/experiments/eurusd_ftmo_ml_v2"))
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostics = _classification_diagnostics(scored)
    period_metrics = _period_metrics(backtest.positions)
    candidate_counts = (
        scored.assign(year=pd.to_datetime(scored["signal_timestamp"]).dt.year)
        .groupby(["strategy_family", "component_id", "year"], dropna=False)
        .size()
        .rename("candidate_count")
        .reset_index()
    )
    coverage_base = scored["signal_timestamp"].ge(pd.Timestamp("2022-01-01"))
    summary = {
        "strategy_name": STRATEGY_NAME,
        "strategy_version": STRATEGY_VERSION,
        "status": "completed_documented_reconstruction",
        "metrics": backtest.metrics,
        "candidate_counts": candidate_counts.to_dict(orient="records"),
        "training_folds": walk.fold_manifest,
        "oos_prediction_coverage": float(scored.loc[coverage_base, "pred_score"].notna().mean()),
        "data_validation": data_validation,
        "no_rl_models": True,
        "no_dl_models": True,
        "additional_models": [],
    }
    model_manifest = {
        "strategy_name": STRATEGY_NAME,
        "strategy_version": STRATEGY_VERSION,
        "data_hash": file_sha256(data_path),
        "data_start": market.index.min().isoformat(),
        "data_end": market.index.max().isoformat(),
        "feature_count": len(FEATURE_COLUMNS),
        "feature_order": list(FEATURE_COLUMNS),
        "feature_schema_hash": feature_schema_hash(),
        "model_parameters": {
            f"model_{leaves}": {**COMMON_MODEL_PARAMS, "num_leaves": leaves}
            for leaves in MODEL_NUM_LEAVES
        },
        "versions": {
            "lightgbm": _version("lightgbm"),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "config_hash": stable_json_hash(cfg),
        "training_start": scored["signal_timestamp"].min().isoformat(),
        "training_end": scored["signal_timestamp"].max().isoformat(),
        "target_definition": "1 iff executable candidate net return after spread, 0.25 pip commission/side and 0.05 pip slippage/side is positive",
        "cost_assumptions": {"commission_pips_per_side": 0.25, "slippage_pips_per_side": 0.05, "spread": "observed bid/ask"},
        "signal_timing": "candidate decision at bar close",
        "execution_timing": "next bar open using direction-specific bid/ask",
        "annual_walk_forward_schedule": walk.fold_manifest,
        "volatility_convention": "M30 log-return ewm std span=960, adjust=False, annualized by sqrt(12096), lagged one bar; expanding median uses lagged history",
    }

    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "metrics.json", backtest.metrics)
    _write_json(output_dir / "model_manifest.json", model_manifest)
    _write_json(output_dir / "feature_manifest.json", _feature_manifest())
    _write_json(output_dir / "classification_diagnostics.json", diagnostics)
    _write_json(output_dir / "reconstruction_assumptions.json", assumptions)
    scored.to_parquet(output_dir / "candidate_trades.parquet", index=False)
    walk.predictions.to_parquet(output_dir / "oos_predictions.parquet", index=False)
    signals.to_parquet(output_dir / "signals.parquet")
    backtest.positions.to_parquet(output_dir / "positions.parquet")
    backtest.orders.to_parquet(output_dir / "orders_or_turnover.parquet")
    backtest.equity_curve.to_parquet(output_dir / "equity_curve.parquet")
    backtest.daily_returns.to_csv(output_dir / "daily_returns.csv")
    backtest.monthly_returns.to_csv(output_dir / "monthly_returns.csv")
    period_metrics.to_csv(output_dir / "period_metrics.csv", index=False)
    walk.final_ensemble.feature_importance().to_csv(output_dir / "feature_importance.csv", index=False)
    pd.DataFrame(
        [{"scenario": "documented_baseline", "commission_pips_per_side": 0.25, "slippage_pips_per_side": 0.05, **backtest.metrics}]
    ).to_csv(output_dir / "cost_stress.csv", index=False)
    (output_dir / "parity_report.md").write_text(
        parity_report_markdown(manifest, experiment_completed=True), encoding="utf-8"
    )
    walk.final_ensemble.save(
        output_dir / "eurusd_ftmo_ml_v2_model_bundle_v2.joblib",
        manifest=model_manifest,
    )
    return {"summary": summary, "output_dir": str(output_dir), "artifacts": sorted(item.name for item in output_dir.iterdir())}


__all__ = [
    "file_sha256",
    "parity_report_markdown",
    "reconstruction_assumptions",
    "run_reconstruction",
    "stable_json_hash",
    "verify_and_copy_references",
]
