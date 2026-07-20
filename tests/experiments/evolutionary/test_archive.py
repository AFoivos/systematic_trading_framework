from __future__ import annotations

import csv
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.experiments.evolutionary.archive import EvolutionaryArchive
from src.experiments.evolutionary.schemas import load_evolutionary_spec


ETH_SPEC = Path(
    "config/evolutionary/ethusd_foundation/ga_ethusd_feature_gate_v1.yaml"
)
MATB_SPEC = Path("config/evolutionary/matb/ga_matb_asset_module_v1.yaml")


def _spec(path: Path, output_dir: Path):
    source = load_evolutionary_spec(path)
    return replace(
        source,
        artifacts=replace(source.artifacts, output_dir=str(output_dir)),
    )


def _trial(
    number: int,
    value: float,
    *,
    generation: int,
    context: dict[str, object],
    rejected: bool = False,
    duplicate_of: int | None = None,
    promoted: bool = False,
):
    attrs = {
        "candidate_hash": f"{number + 1:064x}",
        "decoder_context": context,
        "fitness_components": {},
        "generation": generation,
        "genome": {},
        "promotion_failures": [] if promoted else ["gate_failed"],
        "promotion_metrics": {"metric": value},
        "promotion_passed": promoted,
        "rejected": rejected,
        "resolved_metrics": {},
    }
    if duplicate_of is not None:
        attrs["duplicate_of"] = duplicate_of
    return SimpleNamespace(
        number=number,
        value=value,
        values=[value],
        state=SimpleNamespace(name="COMPLETE"),
        user_attrs=attrs,
        system_attrs={},
        datetime_start=None,
        datetime_complete=None,
    )


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_resume_archive_requires_matching_name_and_contract_hashes(tmp_path: Path) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    (root / "search_manifest.json").write_text(
        json.dumps(
            {
                "search_name": "expected",
                "decoder_contract_hash": "decoder",
                "search_contract_hash": "search",
            }
        ),
        encoding="utf-8",
    )
    archive = EvolutionaryArchive(_spec(ETH_SPEC, root))

    archive.validate_resume_contract(
        search_name="expected",
        decoder_contract_hash="decoder",
        search_contract_hash="search",
    )
    with pytest.raises(ValueError, match="search_name"):
        archive.validate_resume_contract(
            search_name="different",
            decoder_contract_hash="decoder",
            search_contract_hash="search",
        )
    with pytest.raises(ValueError, match="decoder_contract_hash"):
        archive.validate_resume_contract(
            search_name="expected",
            decoder_contract_hash="different",
            search_contract_hash="search",
        )
    with pytest.raises(ValueError, match="search_contract_hash"):
        archive.validate_resume_contract(
            search_name="expected",
            decoder_contract_hash="decoder",
            search_contract_hash="different",
        )


def test_non_resume_rejects_non_empty_output_directory(tmp_path: Path) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    (root / "existing.txt").write_text("owned", encoding="utf-8")
    source = _spec(ETH_SPEC, root)
    archive = EvolutionaryArchive(
        replace(source, search=replace(source.search, resume=False))
    )

    with pytest.raises(FileExistsError, match="resume=false"):
        archive.validate_run_destination()


def test_resume_archive_fails_closed_when_manifest_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    (root / "orphan.txt").write_text("existing", encoding="utf-8")
    archive = EvolutionaryArchive(_spec(ETH_SPEC, root))

    with pytest.raises(ValueError, match="without search_manifest.json"):
        archive.validate_resume_contract(
            search_name="search",
            decoder_contract_hash="decoder",
            search_contract_hash="contract",
        )


def test_frequency_reports_use_accepted_unique_elite_and_final_generation_trials(
    tmp_path: Path,
) -> None:
    root = tmp_path / "eth"
    spec = _spec(ETH_SPEC, root)
    archive = EvolutionaryArchive(spec)
    accepted = [
        _trial(
            index,
            float(index),
            generation=0 if index < 4 else 1,
            context={
                "enabled_feature_families": ["returns_lags"],
                "enabled_gates": ["atr_lower"],
            },
        )
        for index in range(6)
    ]
    duplicate = _trial(
        6,
        100.0,
        generation=1,
        context={"enabled_feature_families": [], "enabled_gates": []},
        duplicate_of=0,
    )
    rejected = _trial(
        7,
        200.0,
        generation=1,
        context={"enabled_feature_families": [], "enabled_gates": []},
        rejected=True,
    )
    study = SimpleNamespace(trials=[*accepted, duplicate, rejected], best_trials=[])

    archive.write_study_artifacts(study, candidate_configs={})

    assert _csv_rows(root / "feature_family_frequency.csv")[0][
        "evaluated_candidates"
    ] == "6"
    assert _csv_rows(root / "feature_family_frequency_elite.csv")[0][
        "evaluated_candidates"
    ] == "5"
    assert _csv_rows(root / "feature_family_frequency_final_generation.csv")[0][
        "evaluated_candidates"
    ] == "2"
    assert (root / "gate_frequency_elite.csv").is_file()
    assert (root / "gate_frequency_final_generation.csv").is_file()


def test_elite_selection_respects_minimize_direction(tmp_path: Path) -> None:
    source = _spec(ETH_SPEC, tmp_path / "minimize")
    spec = replace(source, fitness=replace(source.fitness, direction="minimize"))
    archive = EvolutionaryArchive(spec)
    trials = [
        _trial(
            index,
            value,
            generation=0,
            context={"enabled_feature_families": [], "enabled_gates": []},
        )
        for index, value in enumerate([5.0, 1.0, 3.0, 2.0, 4.0, 9.0])
    ]

    elite = archive._elite_trials(trials)

    assert [trial.value for trial in elite] == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_matb_frequency_and_promotion_artifacts_are_separate_from_fitness(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matb"
    spec = _spec(MATB_SPEC, root)
    archive = EvolutionaryArchive(spec)
    promoted = _trial(
        0,
        1.0,
        generation=0,
        context={
            "selected_assets": ["SPX500", "US100", "GER40", "NIKKEI225"],
            "selected_groups": ["equity_indices"],
            "use_high_volatility_regime_filter": True,
        },
        promoted=True,
    )
    not_promoted = _trial(
        1,
        2.0,
        generation=1,
        context={
            "selected_assets": ["SPX500", "XAUUSD", "USOIL", "EURUSD"],
            "selected_groups": ["equity_indices", "metals", "energy", "fx"],
            "use_high_volatility_regime_filter": False,
        },
    )
    duplicate = _trial(
        2,
        1.0,
        generation=1,
        context=promoted.user_attrs["decoder_context"],
        duplicate_of=0,
        promoted=True,
    )
    study = SimpleNamespace(trials=[promoted, not_promoted, duplicate], best_trials=[])
    promoted_id = promoted.user_attrs["candidate_hash"]

    archive.write_study_artifacts(
        study,
        candidate_configs={promoted_id: {"schema_version": 1}},
    )

    promotion_rows = _csv_rows(root / "promotion_report.csv")
    assert {
        "trial",
        "candidate_hash",
        "fitness",
        "promotion_passed",
        "failed_gate_count",
        "failed_gates",
        "promotion_metrics",
    }.issubset(promotion_rows[0])
    assert promotion_rows[0]["failed_gate_count"] == "0"
    assert promotion_rows[1]["failed_gate_count"] == "1"
    assert (root / "promoted_candidates" / f"{promoted_id}.yaml").is_file()
    assert len(list((root / "promoted_candidates").glob("*.yaml"))) == 1
    for name in ("asset", "group", "module"):
        assert (root / f"{name}_frequency.csv").is_file()
        assert (root / f"{name}_frequency_elite.csv").is_file()
        assert (root / f"{name}_frequency_final_generation.csv").is_file()
