from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.experiments.evolutionary.runner import validate_evolutionary_spec
from src.experiments.evolutionary.schemas import EvolutionarySpec, load_evolutionary_spec


ETH_SPEC = Path(
    "config/evolutionary/ethusd_foundation/ga_ethusd_feature_gate_v1.yaml"
)
MATB_SPEC = Path("config/evolutionary/matb/ga_matb_asset_module_v1.yaml")


def _payload(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", [ETH_SPEC, MATB_SPEC])
def test_repository_evolutionary_specs_load_strictly(path: Path) -> None:
    spec = load_evolutionary_spec(path)

    assert spec.schema_version == 1
    assert spec.search.backend == "optuna_nsga2"
    assert spec.base_config_path.is_file()
    assert spec.execution.maximum_parallel_workers == 1
    assert spec.search.population_size == 8
    assert spec.search.generations == 2
    assert spec.search.resume is True
    assert spec.search.storage is not None
    assert spec.artifacts.frequency_analysis.enabled is True
    if path == MATB_SPEC:
        assert (
            spec.metadata["drawdown_metric_note"]
            == "actual_mtm_max_drawdown_not_target_vol_normalized"
        )


def test_unknown_top_level_key_is_rejected() -> None:
    payload = _payload(ETH_SPEC)
    payload["misspelled_block"] = {}

    with pytest.raises(ValueError, match="unsupported keys.*misspelled_block"):
        EvolutionarySpec.from_dict(payload, spec_path=ETH_SPEC)


def test_unknown_gene_key_is_rejected() -> None:
    payload = _payload(ETH_SPEC)
    payload["genome"]["genes"]["forecast_upper"]["unexpected"] = 1

    with pytest.raises(ValueError, match="unsupported keys.*unexpected"):
        EvolutionarySpec.from_dict(payload, spec_path=ETH_SPEC)


def test_missing_metric_cannot_silently_default_to_zero() -> None:
    payload = _payload(ETH_SPEC)
    component = payload["fitness"]["components"][0]
    component["missing_policy"] = "penalize"

    with pytest.raises(ValueError, match="requires missing_penalty"):
        EvolutionarySpec.from_dict(payload, spec_path=ETH_SPEC)


def test_validate_only_contract_decodes_all_seed_candidates_without_writes() -> None:
    output_existed = load_evolutionary_spec(ETH_SPEC).output_dir.exists()
    spec, _, seeds = validate_evolutionary_spec(ETH_SPEC)

    assert len(seeds) == len(spec.genome.seed_candidates)
    assert spec.output_dir.exists() is output_existed


def test_resume_requires_persistent_storage(tmp_path: Path) -> None:
    payload = deepcopy(_payload(ETH_SPEC))
    payload["search"]["resume"] = True
    payload["search"]["storage"] = None
    path = tmp_path / "resume_without_storage.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="resume=true requires persistent search.storage"):
        validate_evolutionary_spec(path)


def test_promotion_schema_is_strict_and_missing_metrics_fail_closed() -> None:
    payload = deepcopy(_payload(MATB_SPEC))
    payload["promotion"]["gates"][0]["missing_policy"] = "ignore"

    with pytest.raises(ValueError, match="require missing_policy: fail"):
        EvolutionarySpec.from_dict(payload, spec_path=MATB_SPEC)


def test_frequency_analysis_schema_rejects_unknown_keys() -> None:
    payload = deepcopy(_payload(ETH_SPEC))
    payload["artifacts"]["frequency_analysis"]["top_n"] = 10

    with pytest.raises(ValueError, match="unsupported keys.*top_n"):
        EvolutionarySpec.from_dict(payload, spec_path=ETH_SPEC)


def test_promotion_paths_cannot_reference_final_holdout() -> None:
    payload = deepcopy(_payload(MATB_SPEC))
    payload["promotion"]["gates"][0]["metric_path"] = "evaluation.final_holdout.sharpe"

    with pytest.raises(ValueError, match="forbidden holdout token"):
        EvolutionarySpec.from_dict(payload, spec_path=MATB_SPEC)


def test_matb_viability_and_promotion_thresholds_are_separate() -> None:
    spec = load_evolutionary_spec(MATB_SPEC)
    viability = {
        item.name: (item.operator, item.threshold)
        for item in spec.fitness.hard_constraints
    }
    promotion = {
        item.name: (item.operator, item.threshold)
        for item in spec.promotion.gates
    }

    assert viability == {
        "finite_objective": ("finite", None),
        "minimum_candidates": ("ge", 100),
        "completed_trades_per_year": ("ge", 5),
        "active_calendar_folds": ("ge", 2),
        "viability_maximum_mtm_drawdown": ("ge", -0.25),
    }
    assert promotion == {
        "minimum_mtm_sharpe": ("ge", 0.50),
        "positive_median_fold_sharpe": ("gt", 0.0),
        "positive_fold_ratio": ("ge", 0.60),
        "cost_x2_positive": ("gt", 0.0),
        "delay_1_retention": ("ge", 0.60),
        "maximum_asset_pnl_share": ("le", 0.30),
        "maximum_group_pnl_share": ("le", 0.50),
        "maximum_actual_mtm_drawdown_not_target_vol_normalized": ("ge", -0.10),
        "completed_trades_per_year": ("ge", 60),
        "minimum_candidates": ("ge", 800),
    }
