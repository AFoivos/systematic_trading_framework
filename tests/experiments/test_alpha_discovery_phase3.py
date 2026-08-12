from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.experiments.alpha_discovery_scanner import (
    MULTIPLE_TESTING_FAMILY_COLUMNS,
    AlphaDiscoveryScannerError,
    FrozenBinEdges,
    ScannerSettings,
    apply_frozen_states,
    fit_discovery_quintiles,
    preregistered_interaction_pairs,
    scan_conditional_effects,
)
from src.experiments.alpha_discovery_statistics import (
    adjust_pvalues,
    chronological_block_ids,
    moving_block_bootstrap_summary,
)
from src.experiments.alpha_discovery_targets import build_alpha_discovery_targets
from src.experiments.orchestration.alpha_discovery_artifacts import (
    AlphaDiscoveryArtifactError,
    AlphaDiscoveryArtifactLayout,
    write_alpha_discovery_artifacts,
)
from src.experiments.orchestration.alpha_discovery_pipeline import (
    execute_approved_alpha_discovery,
)
from src.features.alpha_discovery_primitives import (
    CONTINUOUS_FEATURE_COLUMNS,
    build_alpha_discovery_features,
)
from src.src_data.research_access import (
    LoadedResearchData,
    ProspectiveAccessAuthorization,
    ProspectiveFinalDataAccess,
)
from src.src_data.research_roles import EvidenceRole, SourceClassification
from src.utils.alpha_discovery_config import (
    compute_alpha_specification_hash,
    validate_alpha_discovery_config,
)

CONFIG = Path("config/research/alpha_discovery/AR-0001_ethusd_30m.yaml")
SPECIFICATION_HASH = "e04d48ae21b812aedc0d2c0060855f92becdc13f6cd1c387d04652d550acfe09"


def _canonical_frame(length: int = 600) -> pd.DataFrame:
    index = np.arange(length, dtype=float)
    generator = np.random.default_rng(8102026)
    innovations = generator.normal(0.0, 0.003, size=length)
    log_returns = (
        0.0002
        + 0.0015 * np.sin(index / 7.0)
        + 0.0008 * np.cos(index / 2.7)
        + innovations
    )
    log_close = np.log(100.0) + np.cumsum(log_returns)
    mid_close = np.exp(log_close)
    mid_open = mid_close * (1.0 + 0.0008 * np.sin(index / 5.0))
    amplitude = 0.0015 + 0.0005 * (1.0 + np.sin(index / 11.0))
    mid_high = np.maximum(mid_open, mid_close) * (1.0 + amplitude)
    mid_low = np.minimum(mid_open, mid_close) * (1.0 - amplitude)
    spread = 0.08 + 0.02 * (1.0 + np.cos(index / 13.0))
    half_spread = spread / 2.0
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
        }
    )


def _approved_config() -> dict:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    original_hash = compute_alpha_specification_hash(cfg)
    cfg["status"] = "APPROVED_TO_RUN"
    cfg["approval"] = {
        "approved_to_run": True,
        "approved_by": "phase3-synthetic-test",
        "approved_at": "2026-08-12T12:00:00+00:00",
        "approved_specification_hash": original_hash,
    }
    cfg["runtime"]["perform_alpha_calculation"] = True
    cfg["blockers"] = []
    assert compute_alpha_specification_hash(cfg) == original_hash
    validate_alpha_discovery_config(cfg)
    return cfg


def test_primitive_features_are_close_t_only_and_have_exact_formulas() -> None:
    frame = _canonical_frame(260)
    features = build_alpha_discovery_features(frame)
    log_close = np.log(frame["mid_close"])
    row = 210

    assert features.loc[row, "log_return_4"] == pytest.approx(
        log_close.iloc[row] - log_close.iloc[row - 4]
    )
    expected_path = (
        abs(log_close.iloc[row] - log_close.iloc[row - 8])
        / np.abs(np.diff(log_close.iloc[row - 8 : row + 1])).sum()
    )
    assert features.loc[row, "path_efficiency_8"] == pytest.approx(expected_path)
    expected_volatility = np.sqrt(
        np.square(np.diff(log_close.iloc[row - 16 : row + 1])).sum()
    )
    assert features.loc[row, "realized_volatility_16"] == pytest.approx(
        expected_volatility
    )
    assert features.loc[row, "normalized_range"] == pytest.approx(
        (frame.loc[row, "mid_high"] - frame.loc[row, "mid_low"])
        / frame.loc[row, "mid_close"]
    )
    assert features.loc[row, "close_location"] == pytest.approx(
        (frame.loc[row, "mid_close"] - frame.loc[row, "mid_low"])
        / (frame.loc[row, "mid_high"] - frame.loc[row, "mid_low"])
    )

    changed_future = frame.copy()
    future_rows = changed_future.index > row
    changed_future.loc[future_rows, ["mid_high", "mid_low", "mid_close"]] *= 1.7
    changed_features = build_alpha_discovery_features(changed_future)
    pd.testing.assert_frame_equal(
        features.loc[:row].reset_index(drop=True),
        changed_features.loc[:row].reset_index(drop=True),
    )


def test_future_targets_use_exact_shifts_and_executable_quote_sides() -> None:
    mid_open = np.arange(100.0, 108.0)
    mid_close = mid_open + 0.5
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=8, freq="30min", tz="UTC"),
            "mid_open": mid_open,
            "mid_close": mid_close,
            "bid_open": mid_open - 0.1,
            "bid_high": mid_open + 0.9,
            "bid_low": mid_open - 0.6,
            "ask_open": mid_open + 0.1,
            "ask_high": mid_open + 1.1,
            "ask_low": mid_open - 0.4,
        }
    )
    targets = build_alpha_discovery_targets(frame, horizons=[2])

    assert targets.loc[0, "mid_close_to_close_h2"] == pytest.approx(
        mid_close[2] / mid_close[0] - 1.0
    )
    assert targets.loc[0, "next_open_to_future_open_h2"] == pytest.approx(
        mid_open[3] / mid_open[1] - 1.0
    )
    assert targets.loc[0, "executable_long_h2"] == pytest.approx(
        (mid_open[3] - 0.1) / (mid_open[1] + 0.1) - 1.0
    )
    assert targets.loc[0, "executable_short_h2"] == pytest.approx(
        ((mid_open[1] - 0.1) - (mid_open[3] + 0.1)) / (mid_open[1] - 0.1)
    )
    assert targets.loc[0, "long_mfe_h2"] == pytest.approx(
        max(mid_open[1:3] + 0.9) / (mid_open[1] + 0.1) - 1.0
    )
    assert targets.loc[0, "long_mae_h2"] == pytest.approx(
        min(mid_open[1:3] - 0.6) / (mid_open[1] + 0.1) - 1.0
    )
    assert targets.loc[0, "short_mfe_h2"] == pytest.approx(
        ((mid_open[1] - 0.1) - min(mid_open[1:3] - 0.4)) / (mid_open[1] - 0.1)
    )
    assert targets.loc[0, "short_mae_h2"] == pytest.approx(
        ((mid_open[1] - 0.1) - max(mid_open[1:3] + 1.1)) / (mid_open[1] - 0.1)
    )
    expected_future_volatility = np.sqrt(
        np.square(np.diff(np.log(mid_close[:3]))).sum()
    )
    assert targets.loc[0, "future_realized_volatility_h2"] == pytest.approx(
        expected_future_volatility
    )
    assert targets["executable_long_h2"].tail(3).isna().all()


def test_discovery_quintiles_are_hash_bound_and_never_refit_on_application(
    monkeypatch,
) -> None:
    features = build_alpha_discovery_features(_canonical_frame(360))
    frozen = fit_discovery_quintiles(
        features,
        snapshot_id="SYNTHETIC-DISCOVERY-V1",
        specification_hash=SPECIFICATION_HASH,
    )
    round_tripped = FrozenBinEdges.from_dict(frozen.to_dict())
    assert round_tripped == frozen
    original_hash = frozen.edge_hash
    original_edges = copy.deepcopy(frozen.edges)

    validation = features.copy()
    validation.loc[:, list(CONTINUOUS_FEATURE_COLUMNS)] += 1_000_000.0

    def forbidden_refit(*args, **kwargs):
        raise AssertionError("Validation application attempted to refit quantiles.")

    monkeypatch.setattr(np, "quantile", forbidden_refit)
    states = apply_frozen_states(validation, frozen)
    assert frozen.edge_hash == original_hash
    assert frozen.edges == original_edges
    for feature in CONTINUOUS_FEATURE_COLUMNS:
        finite = validation[feature].notna()
        assert (states.loc[finite, f"{feature}_state"] == "Q5").all()


def test_only_preregistered_path_efficiency_volatility_interactions_exist() -> None:
    pairs = preregistered_interaction_pairs()
    assert len(pairs) == 9
    assert len(set(pairs)) == 9
    assert all(left.startswith("path_efficiency_") for left, _ in pairs)
    assert all(right.startswith("realized_volatility_") for _, right in pairs)


def test_block_bootstrap_and_fdr_are_deterministic_and_correct() -> None:
    values = np.sin(np.arange(80, dtype=float) / 5.0) / 100.0 + 0.001
    first = moving_block_bootstrap_summary(
        values,
        block_length=8,
        resamples=199,
        confidence_level=0.95,
        seed=17,
    )
    second = moving_block_bootstrap_summary(
        values,
        block_length=8,
        resamples=199,
        confidence_level=0.95,
        seed=17,
    )
    assert first == second
    assert first.n == 80
    assert first.block_length == 8
    assert first.confidence_lower <= first.mean <= first.confidence_upper

    p_values = np.array([0.01, 0.04, 0.03, 0.002, np.nan])
    bh = adjust_pvalues(p_values, method="BH")
    by = adjust_pvalues(p_values, method="BY")
    np.testing.assert_allclose(bh[:4], [0.02, 0.04, 0.04, 0.008])
    np.testing.assert_allclose(
        by[:4],
        [
            0.041666666666666664,
            0.08333333333333333,
            0.08333333333333333,
            0.016666666666666666,
        ],
    )
    assert np.isnan(bh[-1]) and np.isnan(by[-1])
    assert np.all(by[:4] >= bh[:4])
    np.testing.assert_array_equal(
        chronological_block_ids(10, block_count=3),
        [0, 0, 0, 0, 1, 1, 1, 2, 2, 2],
    )


@pytest.fixture(scope="module")
def synthetic_scan():
    frame = _canonical_frame(600)
    features = build_alpha_discovery_features(frame)
    targets = build_alpha_discovery_targets(frame, horizons=[1])
    frozen = fit_discovery_quintiles(
        features,
        snapshot_id="SYNTHETIC-DISCOVERY-V1",
        specification_hash=SPECIFICATION_HASH,
    )
    settings = ScannerSettings(
        block_length_bars=8,
        bootstrap_resamples=31,
        confidence_level=0.90,
        seed=23,
        minimum_observations=2,
        chronological_blocks=3,
    )
    result = scan_conditional_effects(
        features,
        targets,
        frozen_bins=frozen,
        settings=settings,
        horizons=[1],
    )
    return frame, features, targets, frozen, settings, result


def test_conditional_scanner_scope_family_and_temporal_outputs(synthetic_scan) -> None:
    _, _, _, frozen, _, result = synthetic_scan
    effects = result.effects
    stability = result.temporal_stability

    assert len(effects) == 632
    assert set(effects["dimension"]) == {1, 2}
    assert len(stability) == 632 * 3
    assert effects["bin_edge_hash"].eq(frozen.edge_hash).all()
    assert effects["net_cost_scope"].eq("OBSERVED_BID_ASK_SPREAD_ONLY").all()
    assert set(effects["direction"]) == {"LONG", "SHORT"}
    assert set(effects["horizon"]) == {1}

    interactions = effects.loc[effects["dimension"] == 2]
    expected_interactions = {
        f"{left}_x_{right}" for left, right in preregistered_interaction_pairs()
    }
    assert set(interactions["preregistered_interaction"]) == expected_interactions
    assert (
        interactions["feature_family"].eq("path_efficiency_x_realized_volatility").all()
    )
    assert not (effects["dimension"] > 2).any()

    for _, family in effects.groupby(
        list(MULTIPLE_TESTING_FAMILY_COLUMNS), dropna=False
    ):
        finite_count = int(family["p_value"].notna().sum())
        assert family["multiple_testing_family_size"].eq(finite_count).all()
    finite = effects["p_value"].notna()
    assert (
        effects.loc[finite, "p_value_by"] >= effects.loc[finite, "p_value_bh"]
    ).all()


def test_conditional_scanner_is_end_to_end_deterministic(synthetic_scan) -> None:
    _, features, targets, frozen, settings, first = synthetic_scan
    second = scan_conditional_effects(
        features,
        targets,
        frozen_bins=frozen,
        settings=settings,
        horizons=[1],
    )
    pd.testing.assert_frame_equal(first.effects, second.effects)
    pd.testing.assert_frame_equal(first.temporal_stability, second.temporal_stability)


class _SyntheticManifest:
    snapshot_id = "SYNTHETIC-DISCOVERY-V1"
    sha256 = "1" * 64
    evidence_role = EvidenceRole.DISCOVERY
    source_classification = SourceClassification.VALIDATED_MARKET_DATA
    quality = {"status": "PASS", "research_eligible": True, "issues": []}

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "sha256": self.sha256,
            "evidence_role": self.evidence_role.value,
            "source_classification": self.source_classification.value,
            "quality": self.quality,
        }


def test_artifact_write_is_atomic_complete_and_immutable(
    synthetic_scan, tmp_path, monkeypatch
) -> None:
    frame, _, _, _, _, scan = synthetic_scan
    cfg = _approved_config()
    loaded = LoadedResearchData(frame=frame, manifest=_SyntheticManifest())
    monkeypatch.chdir(tmp_path)
    layout = AlphaDiscoveryArtifactLayout.from_config(cfg)

    result = write_alpha_discovery_artifacts(
        layout=layout,
        cfg=cfg,
        loaded=loaded,
        scan=scan,
    )
    assert result.run_manifest_path.is_file()
    assert (result.run_root / "contracts/resolved_specification.yaml").is_file()
    assert (result.run_root / "hypotheses/frozen_quintile_edges.json").is_file()
    assert (result.run_root / "reports/conditional_effects.csv").is_file()
    assert (result.run_root / "reports/temporal_stability.csv").is_file()
    manifest = json.loads(result.run_manifest_path.read_text(encoding="utf-8"))
    assert manifest["runtime_assertions"]["prospective_access"] is False
    assert manifest["runtime_assertions"]["signal_optimization"] is False
    assert manifest["conditional_effect_count"] == 632
    with pytest.raises(AlphaDiscoveryArtifactError, match="already exists"):
        write_alpha_discovery_artifacts(
            layout=layout,
            cfg=cfg,
            loaded=loaded,
            scan=scan,
        )


def test_approved_execution_boundary_rejects_prospective_access_object() -> None:
    cfg = _approved_config()
    prospective = ProspectiveFinalDataAccess(
        ProspectiveAccessAuthorization(
            explicitly_authorized=True,
            approved_by="phase3-synthetic-test",
            approved_at="2026-08-12T12:00:00+00:00",
            frozen_spec_sha256=SPECIFICATION_HASH,
            purpose="negative boundary test only",
        )
    )
    with pytest.raises(TypeError, match="DiscoveryDataAccess"):
        execute_approved_alpha_discovery(cfg, discovery_access=prospective)


def test_scanner_rejects_non_preregistered_horizon(synthetic_scan) -> None:
    _, features, targets, frozen, settings, _ = synthetic_scan
    with pytest.raises(AlphaDiscoveryScannerError, match="preregistered"):
        scan_conditional_effects(
            features,
            targets,
            frozen_bins=frozen,
            settings=settings,
            horizons=[3],
        )
