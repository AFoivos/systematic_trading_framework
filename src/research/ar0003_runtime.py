"""Approved AR-0003 panel construction and deterministic discovery evaluation.

This module is deliberately STF-native.  It verifies frozen source files before
reading them, builds causal per-asset features, constructs next-open executable
targets from observed bid/ask quotes, and evaluates discovery-stage
cross-sectional predictions.  It neither constructs a portfolio nor accesses
validation/prospective evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.experiments.alpha_discovery_statistics import (
    adjust_pvalues,
    newey_west_conditional_mean_summary,
    segmented_moving_block_bootstrap_summary,
    stable_hypothesis_seed,
)
from src.research.dataset import (
    PanelResearchDataset,
    PredictionEligibilitySpec,
    ResearchSegment,
    ResearchSegmentPurpose,
    SegmentBoundary,
    compute_research_dataset_fingerprint,
    validate_research_dataset,
)
from src.research.trend_quality import (
    TrendQualityScorePolicy,
    build_multi_horizon_trend_quality_score,
    evaluate_multi_horizon_trend_quality_score,
)
from src.src_data.research_roles import EvidenceRole
from src.utils.run_metadata import file_sha256


BAR_DELTA = pd.Timedelta(minutes=30)
FEATURE_COLUMNS = (
    "log_return_16",
    "log_return_32",
    "log_return_64",
    "path_efficiency_16",
    "path_efficiency_32",
    "path_efficiency_48",
    "realized_volatility_16",
    "realized_volatility_32",
    "realized_volatility_64",
    "realized_volatility_192",
    "volatility_ratio_32_192",
)
REQUIRED_SOURCE_COLUMNS = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "bid_open",
    "ask_open",
)


class AR0003RuntimeError(RuntimeError):
    """Raised when frozen AR-0003 data or inference gates fail closed."""


@dataclass(frozen=True)
class AR0003BuiltPanel:
    """In-memory, fingerprinted R1 panels plus execution-only diagnostics."""

    panels: Mapping[int, pd.DataFrame]
    metadata: Mapping[int, PanelResearchDataset]
    enriched: pd.DataFrame
    source_quality: Mapping[str, Any]


def _project_path(value: str | Path, *, project_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _finite_numeric(frame: pd.DataFrame, columns: tuple[str, ...], *, asset: str) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise AR0003RuntimeError(f"{asset} contains non-finite {column} values.")


def _load_one_source(
    asset: str,
    source: Mapping[str, Any],
    *,
    project_root: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = _project_path(str(source["path"]), project_root=project_root)
    if not path.is_file():
        raise AR0003RuntimeError(f"Frozen source file is missing for {asset}: {path}")
    actual_sha = file_sha256(path)
    if actual_sha != source["sha256"]:
        raise AR0003RuntimeError(
            f"Frozen source SHA-256 mismatch for {asset}: expected={source['sha256']}, "
            f"actual={actual_sha}."
        )
    frame = pd.read_csv(path)
    missing = sorted(set(REQUIRED_SOURCE_COLUMNS).difference(frame.columns))
    if missing:
        raise AR0003RuntimeError(f"{asset} source is missing columns: {missing}.")
    frame = frame.loc[:, list(REQUIRED_SOURCE_COLUMNS)].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    if frame["timestamp"].duplicated().any() or not frame["timestamp"].is_monotonic_increasing:
        raise AR0003RuntimeError(f"{asset} timestamps must be unique and increasing.")
    frame = frame.loc[frame["timestamp"].ge(start) & frame["timestamp"].lt(end)].copy()
    if frame.empty:
        raise AR0003RuntimeError(f"{asset} has no rows inside the frozen sample.")
    numeric_columns = tuple(column for column in REQUIRED_SOURCE_COLUMNS if column != "timestamp")
    _finite_numeric(frame, numeric_columns, asset=asset)
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if (frame[["open", "high", "low", "close", "bid_open", "ask_open"]] <= 0.0).any().any():
        raise AR0003RuntimeError(f"{asset} contains non-positive prices.")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any() or (
        frame["low"] > frame[["open", "close", "high"]].min(axis=1)
    ).any():
        raise AR0003RuntimeError(f"{asset} violates OHLC ordering.")
    if (frame["ask_open"] < frame["bid_open"]).any():
        raise AR0003RuntimeError(f"{asset} contains negative observed open spreads.")
    frame["asset_id"] = asset
    gaps = frame["timestamp"].diff().ne(BAR_DELTA)
    quality = {
        "asset_id": asset,
        "path": str(source["path"]),
        "sha256": actual_sha,
        "rows": int(len(frame)),
        "first_timestamp": frame["timestamp"].iloc[0].isoformat(),
        "last_timestamp": frame["timestamp"].iloc[-1].isoformat(),
        "non_30m_transitions": int(gaps.iloc[1:].sum()),
        "observed_bid_ask": True,
        "minute_reconstruction_claimed": False,
    }
    return frame.reset_index(drop=True), quality


def _trailing_contiguous(timestamps: pd.Series, window: int) -> pd.Series:
    exact_from_previous = timestamps.diff().eq(BAR_DELTA).astype("int8")
    return exact_from_previous.rolling(window=window, min_periods=window).sum().eq(window)


def _forward_contiguous(timestamps: pd.Series, horizon: int) -> pd.Series:
    next_transition = timestamps.shift(-1).sub(timestamps).eq(BAR_DELTA).astype("int8")
    transitions = horizon + 1
    return (
        next_transition.iloc[::-1]
        .rolling(window=transitions, min_periods=transitions)
        .sum()
        .iloc[::-1]
        .eq(transitions)
    )


def build_ar0003_asset_features_and_targets(frame: pd.DataFrame) -> pd.DataFrame:
    """Build one asset's causal features and next-open executable targets."""

    out = frame.copy()
    close = out["close"]
    timestamps = out["timestamp"]
    one_bar_log_return = np.log(close / close.shift(1)).where(
        _trailing_contiguous(timestamps, 1)
    )
    for window in (16, 32, 64):
        contiguous = _trailing_contiguous(timestamps, window)
        out[f"log_return_{window}"] = np.log(close / close.shift(window)).where(contiguous)
    absolute_change = one_bar_log_return.abs()
    for window in (16, 32, 48):
        path = absolute_change.rolling(window=window, min_periods=window).sum()
        displacement = np.log(close / close.shift(window)).abs()
        out[f"path_efficiency_{window}"] = (displacement / path.where(path > 0.0)).where(
            _trailing_contiguous(timestamps, window)
        )
    for window in (16, 32, 64, 192):
        variance_sum = one_bar_log_return.pow(2).rolling(
            window=window, min_periods=window
        ).sum()
        out[f"realized_volatility_{window}"] = np.sqrt(variance_sum).where(
            _trailing_contiguous(timestamps, window)
        )
    out["volatility_ratio_32_192"] = out["realized_volatility_32"] / out[
        "realized_volatility_192"
    ].where(out["realized_volatility_192"] > 0.0)

    entry_mid = (out["bid_open"].shift(-1) + out["ask_open"].shift(-1)) / 2.0
    entry_spread = out["ask_open"].shift(-1) - out["bid_open"].shift(-1)
    for horizon in (16, 32):
        contiguous = _forward_contiguous(timestamps, horizon)
        exit_mid = (
            out["bid_open"].shift(-(horizon + 1))
            + out["ask_open"].shift(-(horizon + 1))
        ) / 2.0
        exit_spread = (
            out["ask_open"].shift(-(horizon + 1))
            - out["bid_open"].shift(-(horizon + 1))
        )
        for multiplier in (1.0, 1.25, 1.5):
            suffix = str(multiplier).replace(".", "_")
            long_entry = entry_mid + multiplier * entry_spread / 2.0
            long_exit = exit_mid - multiplier * exit_spread / 2.0
            short_entry = entry_mid - multiplier * entry_spread / 2.0
            short_exit = exit_mid + multiplier * exit_spread / 2.0
            out[f"long_return_h{horizon}_cost_{suffix}"] = (
                long_exit / long_entry - 1.0
            ).where(contiguous & long_entry.gt(0.0))
            out[f"short_return_h{horizon}_cost_{suffix}"] = (
                (short_entry - short_exit) / short_entry
            ).where(contiguous & short_entry.gt(0.0))
        out[f"future_executable_return_h{horizon}"] = out[
            f"long_return_h{horizon}_cost_1_0"
        ]
    return out


def _segments(last_timestamp: pd.Timestamp) -> tuple[ResearchSegment, ...]:
    return (
        ResearchSegment(
            segment_id="training",
            purpose=ResearchSegmentPurpose.TRAINING,
            start_timestamp="2020-01-06T00:00:00Z",
            end_timestamp="2024-01-01T00:00:00Z",
            boundary=SegmentBoundary.LEFT_CLOSED_RIGHT_OPEN,
        ),
        ResearchSegment(
            segment_id="tuning",
            purpose=ResearchSegmentPurpose.TUNING,
            start_timestamp="2024-01-01T00:00:00Z",
            end_timestamp="2025-01-01T00:00:00Z",
            boundary=SegmentBoundary.LEFT_CLOSED_RIGHT_OPEN,
        ),
        ResearchSegment(
            segment_id="screening",
            purpose=ResearchSegmentPurpose.SCREENING,
            start_timestamp="2025-01-01T00:00:00Z",
            end_timestamp=last_timestamp.isoformat(),
            boundary=SegmentBoundary.CLOSED,
        ),
    )


def _panel_for_horizon(
    enriched: pd.DataFrame,
    *,
    horizon: int,
    cfg: Mapping[str, Any],
) -> tuple[pd.DataFrame, PanelResearchDataset]:
    target_column = f"future_executable_return_h{horizon}"
    columns = ["timestamp", "asset_id", *FEATURE_COLUMNS, target_column]
    panel = enriched.loc[:, columns].copy()
    screening = panel["timestamp"].ge(pd.Timestamp("2025-01-01T00:00:00Z"))
    complete_features = panel[list(FEATURE_COLUMNS)].notna().all(axis=1)
    complete_target = panel[target_column].notna()
    panel["prediction_eligible"] = screening & complete_features & complete_target
    reason = np.select(
        [~screening, ~complete_features, ~complete_target],
        ["outside_screening_segment", "feature_warmup", "missing_target"],
        default="",
    )
    panel["prediction_ineligibility_reason"] = pd.Series(reason, index=panel.index, dtype="object")
    panel = panel.sort_values(["timestamp", "asset_id"], kind="mergesort").reset_index(drop=True)
    fingerprint = compute_research_dataset_fingerprint(panel)
    source_fingerprints = dict(cfg["dataset_contract"]["source_snapshot_fingerprints"])
    metadata = PanelResearchDataset(
        dataset_id=f"{cfg['dataset_contract']['dataset_id']}-H{horizon}",
        asset_ids=tuple(cfg["asset_universe"]["asset_ids"]),
        feature_names=FEATURE_COLUMNS,
        feature_set_reference="AR0003_PANEL_V1_CAUSAL_FEATURES",
        target_name=f"future_executable_return_h{horizon}",
        target_column=target_column,
        target_specification_reference=(
            f"observed_bid_ask_open_t_plus_1_to_open_t_plus_{horizon + 1}"
        ),
        target_horizon_bars=horizon,
        dataset_fingerprint=fingerprint,
        source_snapshot_fingerprints=source_fingerprints,
        evidence_role=EvidenceRole.DISCOVERY,
        timezone="UTC",
        sample_start_timestamp=panel["timestamp"].iloc[0].isoformat(),
        sample_end_timestamp=panel["timestamp"].iloc[-1].isoformat(),
        segments=_segments(panel["timestamp"].iloc[-1]),
        prediction_eligibility=PredictionEligibilitySpec(),
        transformation_metadata={
            "builder_version": "AR0003_PANEL_V1",
            "source_bar_policy": "OBSERVED_PROVIDER_30M_BARS_NO_MINUTE_RECONSTRUCTION",
            "gap_policy": "INVALIDATE_ANY_FEATURE_OR_TARGET_WINDOW_CROSSING_A_GAP",
            "feature_information_time": "CLOSE_T",
            "entry_boundary": "OPEN_T_PLUS_1",
            "exit_boundary": f"OPEN_T_PLUS_{horizon + 1}",
            "cost_source": "OBSERVED_BID_ASK",
            "evidence_role": "DISCOVERY",
        },
    )
    validate_research_dataset(panel, metadata)
    return panel, metadata


def build_ar0003_panel(cfg: Mapping[str, Any], *, project_root: Path) -> AR0003BuiltPanel:
    """Verify frozen inputs and build both horizon panels without filling gaps."""

    universe = cfg["asset_universe"]
    start = pd.Timestamp(universe["sample_start_inclusive"])
    end = pd.Timestamp(universe["sample_end_exclusive"])
    enriched_assets: list[pd.DataFrame] = []
    source_reports: list[dict[str, Any]] = []
    for asset in universe["asset_ids"]:
        source_frame, report = _load_one_source(
            asset,
            universe["source_files"][asset],
            project_root=project_root,
            start=start,
            end=end,
        )
        enriched_assets.append(build_ar0003_asset_features_and_targets(source_frame))
        source_reports.append(report)
    enriched = pd.concat(enriched_assets, ignore_index=True).sort_values(
        ["timestamp", "asset_id"], kind="mergesort"
    ).reset_index(drop=True)
    resources = cfg["resource_policy"]
    if len(enriched) > int(resources["max_rows"]):
        raise AR0003RuntimeError(
            f"AR-0003 row preflight failed: observed={len(enriched)}, "
            f"maximum={resources['max_rows']}."
        )
    if enriched["asset_id"].nunique() > int(resources["max_assets"]):
        raise AR0003RuntimeError("AR-0003 asset-count preflight failed.")
    panels: dict[int, pd.DataFrame] = {}
    metadata: dict[int, PanelResearchDataset] = {}
    for horizon in (16, 32):
        panels[horizon], metadata[horizon] = _panel_for_horizon(
            enriched, horizon=horizon, cfg=cfg
        )
    quality = {
        "contract": "FROZEN_SOURCE_SHA256_THEN_CAUSAL_PANEL_BUILD",
        "source_bar_policy": universe["source_bar_policy"],
        "asset_count": len(source_reports),
        "row_count": int(len(enriched)),
        "sample_first_observed": enriched["timestamp"].iloc[0].isoformat(),
        "sample_last_observed": enriched["timestamp"].iloc[-1].isoformat(),
        "sources": source_reports,
        "gaps_filled": False,
        "rows_densified": False,
        "minute_reconstruction_claimed": False,
    }
    return AR0003BuiltPanel(
        panels=panels,
        metadata=metadata,
        enriched=enriched,
        source_quality=quality,
    )


def _full_rank_ic_timeline(
    diagnostics: Mapping[str, Any], *, start: str, end: str
) -> pd.DataFrame:
    timeline = pd.DataFrame(
        {"timestamp": pd.date_range(start=start, end=pd.Timestamp(end) - BAR_DELTA, freq="30min", tz="UTC")}
    )
    rows = pd.DataFrame(diagnostics["periods"])
    if rows.empty:
        timeline["rank_ic"] = np.nan
        return timeline
    rows["timestamp"] = pd.to_datetime(rows["timestamp"], utc=True)
    rows["rank_ic"] = pd.to_numeric(rows["rank_correlation"], errors="coerce")
    return timeline.merge(rows[["timestamp", "rank_ic"]], on="timestamp", how="left")


def _portable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _portable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if isfinite(float(value)) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def evaluate_ar0003(
    cfg: Mapping[str, Any], built: AR0003BuiltPanel
) -> dict[str, Any]:
    """Evaluate the frozen primary member first, then all 12 registered variants."""

    robustness = cfg["robustness_family"]
    primary_identity = (0.70, (0.20, 0.80), 32)
    identities = [primary_identity]
    identities.extend(
        identity
        for identity in product(
            robustness["path_efficiency_percentiles"],
            map(tuple, robustness["volatility_percentile_intervals"]),
            robustness["forward_horizons_bars"],
        )
        if identity != primary_identity
    )
    if len(identities) != int(robustness["total_variants"]):
        raise AR0003RuntimeError("Frozen AR-0003 robustness family cardinality drifted.")

    inference = cfg["multiple_testing"]
    variant_rows: list[dict[str, Any]] = []
    primary_predictions: pd.DataFrame | None = None
    primary_diagnostics: dict[str, Any] | None = None
    enriched_targets = built.enriched.set_index(["timestamp", "asset_id"])
    scored_by_horizon: dict[int, pd.DataFrame] = {}
    for horizon in (16, 32):
        panel = built.panels[horizon]
        # Score transformations are same-timestamp only and are invariant to
        # the robustness cutoffs. Compute each horizon once, then apply the 12
        # frozen eligibility policies without refitting or re-ranking.
        screening_panel = panel.loc[
            panel["timestamp"].ge(pd.Timestamp("2025-01-01T00:00:00Z"))
        ]
        scored_by_horizon[horizon] = build_multi_horizon_trend_quality_score(
            screening_panel,
            policy=TrendQualityScorePolicy(
                minimum_assets_per_timestamp=cfg["asset_universe"]["minimum_assets_per_timestamp"]
            ),
        )
    for index, (quality_cutoff, volatility_interval, horizon) in enumerate(identities):
        scored = scored_by_horizon[int(horizon)].copy(deep=False)
        complete = scored[
            [
                "trend_score",
                "quality_score",
                "alpha_score",
                "volatility_ratio_32_192",
                "quality_cross_sectional_percentile",
                "volatility_ratio_cross_sectional_percentile",
            ]
        ].notna().all(axis=1)
        scored["ar0003_score_eligible"] = (
            scored["prediction_eligible"].astype(bool)
            & complete
            & scored["trend_agreement_eligible"].astype(bool)
            & scored["quality_cross_sectional_percentile"].ge(float(quality_cutoff))
            & scored["volatility_ratio_cross_sectional_percentile"].between(
                float(volatility_interval[0]),
                float(volatility_interval[1]),
                inclusive="both",
            )
        )
        diagnostics = evaluate_multi_horizon_trend_quality_score(
            scored,
            executable_target_column=f"future_executable_return_h{horizon}",
            minimum_assets_per_timestamp=cfg["asset_universe"]["minimum_assets_per_timestamp"],
            quantile_fraction=cfg["cross_sectional_evaluation"]["top_fraction"],
            include_prediction_records=False,
        )
        timeline = _full_rank_ic_timeline(
            diagnostics,
            start="2025-01-01T00:00:00Z",
            end="2026-04-28T00:00:00Z",
        )
        finite = timeline["rank_ic"].notna().to_numpy(dtype=bool)
        timeline_values = timeline["rank_ic"].to_numpy(dtype=float)
        continuity = np.zeros(len(timeline), dtype=int)
        strata = timeline["timestamp"].dt.year.to_numpy(dtype=int)
        identity = (
            f"pe={quality_cutoff:.2f}|vol={volatility_interval[0]:.2f}-"
            f"{volatility_interval[1]:.2f}|h={horizon}"
        )
        row: dict[str, Any] = {
            "variant_index": index,
            "identity": identity,
            "is_primary": index == 0,
            "path_efficiency_percentile": float(quality_cutoff),
            "volatility_percentile_interval": [float(value) for value in volatility_interval],
            "forward_horizon_bars": int(horizon),
            "status": "COMPLETED",
            "rank_ic_periods": int(finite.sum()),
            "mean_rank_ic": diagnostics["mean_rank_correlation"],
            "median_rank_ic": diagnostics["median_rank_correlation"],
            "rank_ic_dispersion": diagnostics["rank_correlation_dispersion"],
            "positive_rank_ic_periods": diagnostics["positive_period_count"],
            "top_minus_bottom_executable_return": diagnostics["mean_top_bottom_target_spread"],
        }
        try:
            if int(finite.sum()) < int(cfg["temporal_stability"]["minimum_period_threshold"]):
                raise AR0003RuntimeError(
                    f"Only {int(finite.sum())} valid rank-IC periods; frozen minimum is "
                    f"{cfg['temporal_stability']['minimum_period_threshold']}."
                )
            hac = newey_west_conditional_mean_summary(
                timeline_values,
                condition=np.ones(len(timeline), dtype=bool),
                eligible=finite,
                continuity_segment_ids=continuity,
                stratum_ids=strata,
                lag_bars=int(inference["hac_lag_bars"]),
            )
            bootstrap_cfg = inference["bootstrap"]
            bootstrap = segmented_moving_block_bootstrap_summary(
                timeline_values,
                condition=np.ones(len(timeline), dtype=bool),
                eligible=finite,
                continuity_segment_ids=continuity,
                stratum_ids=strata,
                block_length_bars=int(bootstrap_cfg["block_length_bars"]),
                resamples=int(bootstrap_cfg["resamples"]),
                confidence_level=float(bootstrap_cfg["confidence_level"]),
                minimum_valid_resample_fraction=float(bootstrap_cfg["minimum_valid_resample_fraction"]),
                seed=stable_hypothesis_seed(int(bootstrap_cfg["base_seed"]), identity),
            )
            row["hac"] = hac.to_dict()
            row["bootstrap"] = bootstrap.to_dict()
            row["raw_p_value"] = hac.p_value
        except Exception as exc:
            row["status"] = "INVALID"
            row["failure_reason"] = str(exc)
            row["raw_p_value"] = 1.0
        variant_rows.append(row)

        eligible_scored = scored.loc[scored["ar0003_score_eligible"]].copy()
        eligible_scored = eligible_scored.join(
            enriched_targets[
                [
                    f"long_return_h{horizon}_cost_1_0",
                    f"short_return_h{horizon}_cost_1_0",
                    f"long_return_h{horizon}_cost_1_25",
                    f"short_return_h{horizon}_cost_1_25",
                    f"long_return_h{horizon}_cost_1_5",
                    f"short_return_h{horizon}_cost_1_5",
                ]
            ],
            on=["timestamp", "asset_id"],
        )
        for multiplier, suffix in ((1.0, "1_0"), (1.25, "1_25"), (1.5, "1_5")):
            directional = np.where(
                eligible_scored["alpha_score"].ge(0.0),
                eligible_scored[f"long_return_h{horizon}_cost_{suffix}"],
                eligible_scored[f"short_return_h{horizon}_cost_{suffix}"],
            )
            finite_directional = np.asarray(directional, dtype=float)
            finite_directional = finite_directional[np.isfinite(finite_directional)]
            row[f"mean_directional_return_cost_{multiplier:.2f}x"] = (
                float(np.mean(finite_directional)) if len(finite_directional) else None
            )
        if index == 0:
            primary_predictions = eligible_scored[
                [
                    "timestamp", "asset_id", "alpha_score", "trend_score",
                    "quality_score", "quality_cross_sectional_percentile",
                    "volatility_ratio_cross_sectional_percentile",
                    f"future_executable_return_h{horizon}",
                ]
            ].copy()
            primary_predictions["directional_executable_return"] = np.where(
                eligible_scored["alpha_score"].ge(0.0),
                eligible_scored[f"long_return_h{horizon}_cost_1_0"],
                eligible_scored[f"short_return_h{horizon}_cost_1_0"],
            )
            primary_diagnostics = diagnostics

    adjusted = adjust_pvalues(
        [float(row["raw_p_value"]) for row in variant_rows],
        method="BY",
        total_hypotheses=int(inference["deterministic_family_size"]),
        missing_hypothesis_p_value=1.0,
    )
    for row, adjusted_value in zip(variant_rows, adjusted):
        row["global_by_adjusted_p_value"] = float(adjusted_value)
        row["passes_global_by_0_05"] = bool(
            row["status"] == "COMPLETED"
            and float(adjusted_value) <= float(inference["false_discovery_rate"])
        )
        bootstrap_lower = (row.get("bootstrap") or {}).get("confidence_lower")
        row["discovery_eligible"] = bool(
            inference["discovery_eligibility_gate"]
            == "POSITIVE_MEAN_AND_BOOTSTRAP_LOWER_GT_ZERO_AND_GLOBAL_BY"
            and row["status"] == "COMPLETED"
            and row["mean_rank_ic"] is not None
            and float(row["mean_rank_ic"]) > 0.0
            and bootstrap_lower is not None
            and float(bootstrap_lower) > 0.0
            and row["passes_global_by_0_05"]
        )

    assert primary_predictions is not None and primary_diagnostics is not None
    by_year: list[dict[str, Any]] = []
    primary_predictions["year"] = primary_predictions["timestamp"].dt.year
    for year, group in primary_predictions.groupby("year", sort=True):
        per_time = group.groupby("timestamp", sort=True).apply(
            lambda sample: sample["alpha_score"].rank(method="average").corr(
                sample["future_executable_return_h32"].rank(method="average")
            ),
            include_groups=False,
        )
        by_year.append(
            {
                "year": int(year),
                "n": int(len(group)),
                "timestamp_count": int(group["timestamp"].nunique()),
                "mean_directional_executable_return": float(group["directional_executable_return"].mean()),
                "mean_rank_ic": float(per_time.mean()) if per_time.notna().any() else None,
                "coverage": float(len(group) / max(1, built.panels[32].loc[built.panels[32]["timestamp"].dt.year.eq(year)].shape[0])),
                "hit_rate": float(group["directional_executable_return"].gt(0.0).mean()),
            }
        )
    per_asset: list[dict[str, Any]] = []
    eligible_total = built.panels[32].loc[built.panels[32]["prediction_eligible"]].groupby("asset_id").size()
    for asset, group in primary_predictions.groupby("asset_id", sort=True):
        per_asset.append(
            {
                "asset_id": str(asset),
                "prediction_rows": int(len(group)),
                "eligible_base_rows": int(eligible_total.get(asset, 0)),
                "score_regime_coverage": float(len(group) / max(1, int(eligible_total.get(asset, 0)))),
                "spearman_score_target": _portable(group["alpha_score"].corr(group["future_executable_return_h32"], method="spearman")),
                "mean_directional_executable_return": float(group["directional_executable_return"].mean()),
                "hit_rate": float(group["directional_executable_return"].gt(0.0).mean()),
            }
        )
    breadth = {
        "total_alternatives": len(variant_rows),
        "completed": sum(row["status"] == "COMPLETED" for row in variant_rows),
        "failed": 0,
        "invalid": sum(row["status"] == "INVALID" for row in variant_rows),
        "eligible_global_by": sum(row["passes_global_by_0_05"] for row in variant_rows),
        "eligible": sum(row["discovery_eligible"] for row in variant_rows),
        "selected": 0,
        "automatic_candidate_promotion": False,
        "secondary_lightgbm_enabled": False,
    }
    return _portable(
        {
            "variants": variant_rows,
            "primary_diagnostics": primary_diagnostics,
            "primary_predictions": primary_predictions.drop(columns="year"),
            "temporal_stability": by_year,
            "per_asset_diagnostics": per_asset,
            "search_breadth": breadth,
            "evidence_role": "DISCOVERY",
            "canonical_validation_required": True,
            "portfolio_backtest_performed": False,
            "prospective_final_accessed": False,
        }
    )


__all__ = [
    "AR0003BuiltPanel",
    "AR0003RuntimeError",
    "FEATURE_COLUMNS",
    "build_ar0003_asset_features_and_targets",
    "build_ar0003_panel",
    "evaluate_ar0003",
]
