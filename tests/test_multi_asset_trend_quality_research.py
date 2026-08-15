from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest
import yaml

from src.experiments.orchestration.cross_sectional_alpha_pipeline import (
    CrossSectionalAlphaExecutionRefused,
    run_alpha_discovery_v3_pipeline,
)
from src.pipelines.registry import get_pipeline_fn
from src.research import (
    TrendQualityResearchError,
    build_multi_horizon_trend_quality_score,
    evaluate_multi_horizon_trend_quality_score,
)
from src.utils.alpha_discovery_config import (
    compute_alpha_specification_hash,
    validate_alpha_discovery_any_config,
)
from src.utils.alpha_discovery_v3_config import AR0003_ROBUSTNESS_VARIANTS


CONFIG = Path(
    "config/research/alpha_discovery/AR-0003_multi_asset_trend_quality.yaml"
)
SCHEMA = Path(
    "config/research/alpha_discovery/alpha_discovery_v3_spec.schema.json"
)
ASSETS = tuple(f"ASSET_{letter}" for letter in "ABCDEF")


def _panel() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    timestamps = pd.date_range("2026-01-01T00:00:00Z", periods=4, freq="30min")
    for time_index, timestamp in enumerate(timestamps):
        for asset_index, asset_id in enumerate(ASSETS):
            level = float(asset_index + 1 + time_index / 10.0)
            rows.append(
                {
                    "timestamp": timestamp,
                    "asset_id": asset_id,
                    "log_return_16": level / 100.0,
                    "log_return_32": level / 80.0,
                    "log_return_64": level / 60.0,
                    "path_efficiency_16": level / 10.0,
                    "path_efficiency_32": level / 12.0,
                    "path_efficiency_48": level / 14.0,
                    "realized_volatility_32": level / 100.0,
                    "realized_volatility_192": 0.10,
                    "prediction_eligible": True,
                    "executable_return_h32": level / 1000.0,
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["timestamp", "asset_id"], kind="mergesort"
    ).reset_index(drop=True)


def test_ar0003_is_hash_bound_specification_only_and_registered() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    validate_alpha_discovery_any_config(cfg)
    assert cfg["status"] == "SPECIFICATION_ONLY"
    assert cfg["approval"]["approved_to_run"] is False
    assert cfg["runtime"]["perform_alpha_calculation"] is False
    assert cfg["asset_universe"]["status"] == "UNRESOLVED"
    assert cfg["asset_universe"]["asset_ids"] == []
    assert cfg["dataset_contract"]["status"] == "UNAVAILABLE"
    assert compute_alpha_specification_hash(cfg) == cfg["specification_hash"]
    assert cfg["robustness_family"]["total_variants"] == (
        AR0003_ROBUSTNESS_VARIANTS
    )
    assert get_pipeline_fn("alpha_discovery_v3") is run_alpha_discovery_v3_pipeline
    assert json.loads(SCHEMA.read_text(encoding="utf-8"))["$schema"].endswith(
        "2020-12/schema"
    )


def test_ar0003_refuses_before_data_access_and_cannot_fake_readiness() -> None:
    with pytest.raises(CrossSectionalAlphaExecutionRefused, match="before data access"):
        run_alpha_discovery_v3_pipeline(CONFIG)

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    invented = copy.deepcopy(cfg)
    invented["asset_universe"]["asset_ids"] = ["EURUSD", "US100"]
    with pytest.raises(ValueError, match="unresolved.*cannot contain invented"):
        validate_alpha_discovery_any_config(invented)


def test_primary_score_uses_exact_formula_and_same_timestamp_cross_sections() -> None:
    frame = _panel()
    scored = build_multi_horizon_trend_quality_score(frame)
    timestamp = frame["timestamp"].iloc[0]
    group = scored.loc[scored["timestamp"] == timestamp]
    row = group.iloc[3]

    expected_trend = float(
        np.median(
            [
                row["cross_sectional_zscore_log_return_16"],
                row["cross_sectional_zscore_log_return_32"],
                row["cross_sectional_zscore_log_return_64"],
            ]
        )
    )
    expected_quality = float(
        np.median(
            [
                row["path_efficiency_16"],
                row["path_efficiency_32"],
                row["path_efficiency_48"],
            ]
        )
    )
    assert row["trend_score"] == pytest.approx(expected_trend)
    assert row["quality_score"] == pytest.approx(expected_quality)
    assert row["alpha_score"] == pytest.approx(expected_trend * expected_quality)
    assert row["trend_agreement_count"] == 3
    assert row["trend_direction"] == 1

    changed_future = frame.copy()
    final_timestamp = changed_future["timestamp"].max()
    changed_future.loc[
        changed_future["timestamp"] == final_timestamp,
        ["log_return_16", "path_efficiency_16", "realized_volatility_32"],
    ] *= 1000.0
    rescored = build_multi_horizon_trend_quality_score(changed_future)
    past = frame["timestamp"] < final_timestamp
    columns = [
        "trend_score",
        "quality_score",
        "alpha_score",
        "quality_cross_sectional_percentile",
        "volatility_ratio_cross_sectional_percentile",
        "ar0003_score_eligible",
    ]
    pdt.assert_frame_equal(
        scored.loc[past, columns].reset_index(drop=True),
        rescored.loc[past, columns].reset_index(drop=True),
    )


def test_primary_score_preserves_missing_and_rejects_noncanonical_panel() -> None:
    frame = _panel()
    frame.loc[0, "path_efficiency_16"] = np.nan
    scored = build_multi_horizon_trend_quality_score(frame)
    assert pd.isna(scored.loc[0, "quality_score"])
    assert bool(scored.loc[0, "ar0003_score_eligible"]) is False

    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(TrendQualityResearchError, match="unique"):
        build_multi_horizon_trend_quality_score(duplicated)

    unsorted = frame.iloc[[1, 0, *range(2, len(frame))]].reset_index(drop=True)
    with pytest.raises(TrendQualityResearchError, match="canonically sorted"):
        build_multi_horizon_trend_quality_score(unsorted)


def test_cross_sectional_output_is_portable_screening_not_portfolio_evidence() -> None:
    scored = build_multi_horizon_trend_quality_score(_panel())
    # Isolate the portable diagnostic contract from the restrictive primary
    # regime so every deterministic cross-section is observable in this test.
    scored["ar0003_score_eligible"] = True
    diagnostics = evaluate_multi_horizon_trend_quality_score(
        scored,
        executable_target_column="executable_return_h32",
        minimum_assets_per_timestamp=5,
        quantile_fraction=0.20,
    )

    assert diagnostics["screening_stage"] == "DISCOVERY"
    assert diagnostics["canonical_validation_required"] is True
    assert diagnostics["portfolio_interpretation"] is False
    assert diagnostics["valid_period_count"] == 4
    assert diagnostics["mean_rank_correlation"] == pytest.approx(1.0)
    assert diagnostics["mean_top_bottom_target_spread"] > 0.0
    assert len(diagnostics["prediction_records"]) == len(scored)
    assert all(
        record["model_fit_required"] is False
        for record in diagnostics["prediction_records"]
    )
    json.dumps(diagnostics, allow_nan=False)
