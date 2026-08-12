from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

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


def test_ar0001_is_a_valid_frozen_spec_but_not_approved() -> None:
    cfg = load_experiment_config(CONFIG)

    validate_alpha_discovery_config(cfg)
    assert cfg["status"] == "SPECIFICATION_ONLY"
    assert cfg["runtime"] == {
        "perform_alpha_calculation": False,
        "run_backtests": False,
        "access_prospective_final": False,
    }
    assert cfg["snapshot_reference"]["source_classification"] == "LEGACY_MARKET_DATA"
    assert cfg["snapshot_reference"]["expected_sha256"] == (
        "efcde7cbd74ad8d8d450bf6d7bf8127919fe3e54ebbd7715f79e6310f64b9b7d"
    )
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


def test_specification_only_pipeline_refuses_before_data_access(monkeypatch) -> None:
    def forbidden_constructor(*args, **kwargs):
        raise AssertionError(
            "DiscoveryDataAccess must not be constructed for SPECIFICATION_ONLY"
        )

    monkeypatch.setattr(
        "src.experiments.orchestration.alpha_discovery_pipeline.DiscoveryDataAccess",
        forbidden_constructor,
    )
    with pytest.raises(AlphaDiscoveryExecutionRefused, match="before data access"):
        run_alpha_discovery_pipeline(CONFIG)


def test_artifact_layout_is_stable_and_inside_existing_experiment_root() -> None:
    cfg = load_experiment_config(CONFIG)
    layout = AlphaDiscoveryArtifactLayout.from_config(cfg)

    assert layout.run_root == Path(
        "logs/experiments/alpha_discovery/AR-0001/" + cfg["specification_hash"][:16]
    )
    assert layout.registry == layout.run_root / "registry"
    assert layout.data_quality == layout.run_root / "data_quality"
