from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

import src.experiments.orchestration.alpha_discovery_pipeline as alpha_discovery_pipeline
from src.experiments.alpha_contracts import (
    AvailableAt,
    BarEvent,
    FeatureAvailability,
    MaterialSpecificationChange,
    ResearchContractError,
    prospective_clock_must_restart,
    require_role_transition_allowed,
    validation_is_contaminated_after_change,
)
from src.experiments.orchestration.alpha_discovery_pipeline import (
    AlphaDiscoveryArtifactLayout,
    AlphaDiscoveryExecutionRefused,
    run_alpha_discovery_pipeline,
)
from src.src_data.research_access import DiscoveryDataAccess
from src.src_data.research_roles import EvidenceRole, ResearchRoleError
from src.utils.alpha_discovery_config import (
    AlphaDiscoveryConfigError,
    compute_alpha_specification_hash,
    validate_alpha_discovery_config,
)
from src.utils.config import load_experiment_config

CONFIG = Path("config/research/alpha_discovery/AR-0001_ethusd_30m.yaml")
SCHEMA = Path("config/research/alpha_discovery/alpha_discovery_spec.schema.json")


def test_available_at_prevents_consume_before_information_exists() -> None:
    close_t = AvailableAt(0, BarEvent.CLOSE)
    open_t = AvailableAt(0, BarEvent.OPEN)
    open_next = AvailableAt(1, BarEvent.OPEN)

    assert close_t.is_available_by(open_next) is True
    assert close_t.is_available_by(open_t) is False
    with pytest.raises(ResearchContractError, match="would be consumed"):
        close_t.require_available_by(open_t, feature_name="close_location")

    feature = FeatureAvailability.from_dict(
        {
            "name": "close_location",
            "available_at": {"bar_offset": 0, "event": "CLOSE"},
        }
    )
    feature.require_consumable_at(open_next)
    with pytest.raises(ResearchContractError, match="Unexpected feature availability"):
        FeatureAvailability.from_dict(
            {
                "name": "close_location",
                "available_at": {"bar_offset": 0, "event": "CLOSE"},
                "silent_override": True,
            }
        )


def test_role_relabeling_and_contamination_rules_are_fail_closed() -> None:
    require_role_transition_allowed(EvidenceRole.DISCOVERY, EvidenceRole.DISCOVERY)
    with pytest.raises(ResearchRoleError, match="cannot become"):
        require_role_transition_allowed(
            EvidenceRole.HISTORICAL_PSEUDO_OOS,
            EvidenceRole.PROSPECTIVE_FINAL,
        )
    changes = [MaterialSpecificationChange.FEATURE_WINDOWS]
    assert validation_is_contaminated_after_change(
        validation_results_viewed=True,
        changed_fields=changes,
    )
    assert prospective_clock_must_restart(changes)
    assert not validation_is_contaminated_after_change(
        validation_results_viewed=False,
        changed_fields=changes,
    )


def test_ar0001_is_a_valid_approved_frozen_spec() -> None:
    cfg = load_experiment_config(CONFIG)

    validate_alpha_discovery_config(cfg)
    assert cfg["status"] == "APPROVED_TO_RUN"
    assert cfg["approval"] == {
        "approved_to_run": True,
        "approved_by": "FGADev",
        "approved_at": "2026-08-12T15:22:00+03:00",
        "approved_specification_hash": cfg["specification_hash"],
    }
    assert cfg["runtime"] == {
        "perform_alpha_calculation": True,
        "run_backtests": False,
        "access_prospective_final": False,
    }
    assert cfg["snapshot_reference"]["source_classification"] == "VALIDATED_MARKET_DATA"
    assert cfg["schema_version"] == 2
    assert cfg["snapshot_reference"]["snapshot_id"] == (
        "ETHUSD-30M-DISCOVERY-PRE-2025-07-01-V1"
    )
    assert cfg["snapshot_reference"]["expected_sha256"] == (
        "f9f5e61bc631f5ea07d5ac335363bab32a6808db9d26981c8b236261eee14fec"
    )
    assert cfg["snapshot_reference"]["readiness"] == "ELIGIBLE"
    assert cfg["snapshot_reference"]["legacy_classifications"] == []
    assert cfg["blockers"] == []
    assert {target["status"] for target in cfg["targets_planned"]} == {
        "IMPLEMENTED_PHASE_3"
    }
    assert cfg["historical_partition"]["cutoff_utc"] == "2025-07-01T00:00:00Z"
    assert cfg["historical_pseudo_oos_reference"]["evidence_role"] == (
        "HISTORICAL_PSEUDO_OOS"
    )
    assert cfg["data_eligibility"]["canonical_bar_policy"] == (
        "FULL_30_OF_30_OBSERVED_MINUTES"
    )
    assert cfg["statistics"]["hac"] == {
        "estimator": "CONDITIONAL_MEAN_RATIO",
        "kernel": "BARTLETT",
        "primary_lag_rule": "FIXED_BARS",
        "primary_lag_bars": 48,
        "sensitivity_lags_bars": [96, 192],
        "sensitivity_role": "DIAGNOSTIC_ONLY_NON_BINDING",
    }
    assert cfg["multiple_testing"]["global_family_size"] == 3792
    assert cfg["multiple_testing"]["binding_method"] == "GLOBAL_BY"
    assert cfg["multiple_testing"]["status"] == "IMPLEMENTED_FROZEN_CONTRACT"
    assert json.loads(SCHEMA.read_text(encoding="utf-8"))["$schema"].endswith(
        "2020-12/schema"
    )


def test_specification_hash_is_reproducible_and_material_changes_are_detected() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    first = compute_alpha_specification_hash(cfg)
    with_clone_path = copy.deepcopy(cfg)
    with_clone_path["config_path"] = "/different/clean/clone/config.yaml"
    assert compute_alpha_specification_hash(with_clone_path) == first
    assert first == cfg["specification_hash"]

    changed = copy.deepcopy(cfg)
    changed["horizons"] = [1, 2, 4, 8, 16, 64]
    assert compute_alpha_specification_hash(changed) != first
    with pytest.raises(AlphaDiscoveryConfigError, match="horizons"):
        validate_alpha_discovery_config(changed)


def test_config_rejects_point_in_time_and_scientific_contract_drift() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    lookahead = copy.deepcopy(cfg)
    lookahead["features"][4]["available_at"] = {"bar_offset": 0, "event": "OPEN"}
    with pytest.raises(AlphaDiscoveryConfigError, match=r"must be close\[t\]"):
        validate_alpha_discovery_config(lookahead)

    drifted = copy.deepcopy(cfg)
    drifted["scientific_contract"]["prospective_clock"] = "DO_NOT_RESTART"
    with pytest.raises(AlphaDiscoveryConfigError, match="prospective_clock"):
        validate_alpha_discovery_config(drifted)


def test_pipeline_enforces_specification_only_and_approved_access_paths(
    monkeypatch, tmp_path: Path
) -> None:
    specification_only = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    specification_only["status"] = "SPECIFICATION_ONLY"
    specification_only["approval"] = {
        "approved_to_run": False,
        "approved_by": None,
        "approved_at": None,
        "approved_specification_hash": None,
    }
    specification_only["runtime"]["perform_alpha_calculation"] = False
    specification_only["blockers"] = [
        "Explicit APPROVED_TO_RUN authorization has not been issued."
    ]
    validate_alpha_discovery_config(specification_only)
    specification_only_path = tmp_path / "specification_only.yaml"
    specification_only_path.write_text(
        yaml.safe_dump(specification_only, sort_keys=False),
        encoding="utf-8",
    )

    def forbidden_constructor(*args, **kwargs):
        raise AssertionError(
            "DiscoveryDataAccess must not be constructed for SPECIFICATION_ONLY"
        )

    monkeypatch.setattr(
        alpha_discovery_pipeline, "DiscoveryDataAccess", forbidden_constructor
    )
    with pytest.raises(AlphaDiscoveryExecutionRefused, match="before data access"):
        run_alpha_discovery_pipeline(specification_only_path)

    captured: dict[str, object] = {}
    approved_result = object()

    def capture_approved_access(cfg, *, discovery_access):
        captured["status"] = cfg["status"]
        captured["discovery_access"] = discovery_access
        return approved_result

    monkeypatch.setattr(
        alpha_discovery_pipeline, "DiscoveryDataAccess", DiscoveryDataAccess
    )
    monkeypatch.setattr(
        alpha_discovery_pipeline,
        "execute_approved_alpha_discovery",
        capture_approved_access,
    )
    result = run_alpha_discovery_pipeline(CONFIG)

    assert result is approved_result
    assert captured["status"] == "APPROVED_TO_RUN"
    assert isinstance(captured["discovery_access"], DiscoveryDataAccess)


def test_artifact_layout_is_stable_and_inside_existing_experiment_root() -> None:
    cfg = load_experiment_config(CONFIG)
    layout = AlphaDiscoveryArtifactLayout.from_config(cfg)

    assert layout.run_root == Path(
        "logs/experiments/alpha_discovery/AR-0001/" + cfg["specification_hash"][:16]
    )
    assert layout.registry == layout.run_root / "registry"
    assert layout.data_quality == layout.run_root / "data_quality"
