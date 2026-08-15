from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

import src.experiments.orchestration.alpha_discovery_pipeline as pipeline_module
from src.experiments.alpha_discovery_scanner import (
    ConditionUniverse,
    ScannerSettings,
    _adjust_families,
    build_condition_specs,
)
from src.experiments.orchestration.alpha_discovery_pipeline import (
    AlphaDiscoveryExecutionRefused,
    run_alpha_discovery_pipeline,
)
from src.pipelines.registry import get_pipeline_fn
from src.features.alpha_discovery_liquidity import (
    build_alpha_discovery_liquidity_features,
)
from src.utils.alpha_discovery_config import (
    compute_alpha_specification_hash,
    validate_alpha_discovery_any_config,
)
from src.utils.alpha_discovery_v2_config import (
    AR0002_CONDITION_COUNT,
    AR0002_CONTINUOUS_FEATURES,
    AR0002_EFFECT_COUNT,
    AR0002_HORIZONS,
    AR0002_INTERACTION_PAIRS,
)

CONFIG = Path(
    "config/research/alpha_discovery/AR-0002_ethusd_30m_spread_aware.yaml"
)
SCHEMA = Path(
    "config/research/alpha_discovery/alpha_discovery_v2_spec.schema.json"
)


def _canonical_frame(length: int = 260) -> pd.DataFrame:
    index = np.arange(length, dtype=float)
    log_close = np.log(100.0) + np.cumsum(
        0.0002 + 0.002 * np.sin(index / 9.0)
    )
    mid_close = np.exp(log_close)
    mid_open = mid_close * (1.0 + 0.0005 * np.cos(index / 7.0))
    amplitude = 0.001 + 0.0004 * (1.0 + np.sin(index / 13.0))
    mid_high = np.maximum(mid_open, mid_close) * (1.0 + amplitude)
    mid_low = np.minimum(mid_open, mid_close) * (1.0 - amplitude)
    spread_absolute = 0.05 + 0.025 * (1.0 + np.cos(index / 17.0))
    half_spread = spread_absolute / 2.0
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2024-01-01", periods=length, freq="30min", tz="UTC"
            ),
            "mid_open": mid_open,
            "mid_high": mid_high,
            "mid_low": mid_low,
            "mid_close": mid_close,
            "bid_open": mid_open - half_spread,
            "bid_high": mid_high - half_spread,
            "bid_low": mid_low - half_spread,
            "bid_close": mid_close - half_spread,
            "ask_open": mid_open + half_spread,
            "ask_high": mid_high + half_spread,
            "ask_low": mid_low + half_spread,
            "ask_close": mid_close + half_spread,
            "spread_fraction": spread_absolute / mid_close,
            "observed_minute_count": 30,
        }
    )


def test_ar0002_is_valid_specification_only_and_hash_bound() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    validate_alpha_discovery_any_config(cfg)
    assert cfg["status"] == "SPECIFICATION_ONLY"
    assert cfg["approval"]["approved_to_run"] is False
    assert cfg["runtime"]["perform_alpha_calculation"] is False
    assert cfg["prior_research_context"]["evidence_role"] == "DISCOVERY"
    assert cfg["prior_research_context"]["use"] == (
        "POST_HOC_HYPOTHESIS_GENERATION_ONLY"
    )
    assert compute_alpha_specification_hash(cfg) == cfg["specification_hash"]
    assert cfg["multiple_testing"]["global_family_size"] == AR0002_EFFECT_COUNT
    assert get_pipeline_fn("alpha_discovery_v2") is run_alpha_discovery_pipeline
    assert json.loads(SCHEMA.read_text(encoding="utf-8"))["$schema"].endswith(
        "2020-12/schema"
    )


def test_ar0002_approval_can_bind_only_the_exact_scientific_hash() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    approved = copy.deepcopy(cfg)
    approved["status"] = "APPROVED_TO_RUN"
    approved["approval"] = {
        "approved_to_run": True,
        "approved_by": "ar0002-contract-test",
        "approved_at": "2026-08-15T17:00:00+03:00",
        "approved_specification_hash": cfg["specification_hash"],
    }
    approved["runtime"]["perform_alpha_calculation"] = True
    approved["blockers"] = []
    validate_alpha_discovery_any_config(approved)

    drifted = copy.deepcopy(approved)
    drifted["economic_gate"]["minimum_mean_net_return"] = 0.0005
    with pytest.raises(ValueError, match="economic gate"):
        validate_alpha_discovery_any_config(drifted)


def test_ar0002_specification_only_refuses_before_data_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_constructor(*args, **kwargs):
        raise AssertionError("SPECIFICATION_ONLY must refuse before data access")

    monkeypatch.setattr(
        pipeline_module,
        "DiscoveryDataAccess",
        forbidden_constructor,
    )
    with pytest.raises(AlphaDiscoveryExecutionRefused, match="before data access"):
        run_alpha_discovery_pipeline(CONFIG)


def test_spread_fraction_is_close_t_only_and_never_future_fitted() -> None:
    frame = _canonical_frame()
    row = 210
    first = build_alpha_discovery_liquidity_features(frame)

    assert first.loc[row, "spread_fraction"] == pytest.approx(
        frame.loc[row, "spread_fraction"]
    )
    assert bool(first.loc[row, "eligible_feature__spread_fraction"])

    changed_future = frame.copy()
    future = changed_future.index > row
    changed_future.loc[future, "spread_fraction"] *= 10.0
    future_spread = (
        changed_future.loc[future, "spread_fraction"]
        * changed_future.loc[future, "mid_close"]
    )
    changed_future.loc[future, "bid_close"] = (
        changed_future.loc[future, "mid_close"] - future_spread / 2.0
    )
    changed_future.loc[future, "ask_close"] = (
        changed_future.loc[future, "mid_close"] + future_spread / 2.0
    )
    second = build_alpha_discovery_liquidity_features(changed_future)
    pd.testing.assert_frame_equal(
        first.loc[:row].reset_index(drop=True),
        second.loc[:row].reset_index(drop=True),
    )


def test_ar0002_condition_universe_is_exactly_120_states_and_720_effects() -> None:
    universe = ConditionUniverse(
        continuous_features=AR0002_CONTINUOUS_FEATURES,
        interaction_pairs=AR0002_INTERACTION_PAIRS,
    )
    specs = build_condition_specs(universe)

    assert universe.condition_count == AR0002_CONDITION_COUNT == 120
    assert len(specs) == 120
    assert len({(spec["feature_columns"], spec["state"]) for spec in specs}) == 120
    assert len(specs) * len(AR0002_HORIZONS) * 2 == AR0002_EFFECT_COUNT
    assert {spec["dimension"] for spec in specs} == {1, 2}


def test_positive_economic_gate_is_separate_and_binding_for_candidates() -> None:
    effects = pd.DataFrame(
        {
            "feature_family": ["spread_fraction", "spread_fraction"],
            "horizon": [32, 32],
            "target": ["executable_return", "executable_return"],
            "direction": ["LONG", "SHORT"],
            "preregistered_interaction": ["ONE_DIMENSIONAL", "ONE_DIMENSIONAL"],
            "p_value": [0.000001, 0.000001],
            "inference_status": ["ELIGIBLE", "ELIGIBLE"],
            "confidence_lower": [0.0002, -0.003],
            "confidence_upper": [0.004, -0.001],
            "temporal_stability_status": ["STABLE", "STABLE"],
            "mean_net_return": [0.002, -0.002],
        }
    )
    settings = ScannerSettings(
        global_family_size=2,
        minimum_mean_net_return=0.001,
    )

    screened = _adjust_families(effects, settings=settings)

    assert screened["statistical_screen_status"].tolist() == ["PASS", "PASS"]
    assert screened["economic_effect_gate_status"].tolist() == ["PASS", "FAIL"]
    assert screened["candidate_screen_status"].tolist() == ["PASS", "FAIL"]
