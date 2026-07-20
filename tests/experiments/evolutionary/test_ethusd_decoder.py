from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from src.experiments.evolutionary.decoders import decode_candidate
from src.experiments.evolutionary.genome import GenomeValidationError
from src.experiments.evolutionary.schemas import load_evolutionary_spec
from src.utils.config import load_experiment_config


SPEC_PATH = Path(
    "config/evolutionary/ethusd_foundation/ga_ethusd_feature_gate_v1.yaml"
)


def _inputs():
    spec = load_evolutionary_spec(SPEC_PATH)
    base = load_experiment_config(spec.base_config_path)
    seeds = {seed.name: dict(seed.genome) for seed in spec.genome.seed_candidates}
    return spec, base, seeds


def test_baseline_genome_reproduces_baseline_feature_list_and_gates() -> None:
    spec, base, seeds = _inputs()

    decoded = decode_candidate(base, seeds["full_baseline"], spec)

    assert decoded.config["model"]["feature_cols"] == base["model"]["feature_cols"]
    assert (
        decoded.config["signals"]["params"]["activation_filters"]
        == base["signals"]["params"]["activation_filters"]
    )


def test_feature_order_is_base_order_and_contains_no_duplicates() -> None:
    spec, base, seeds = _inputs()
    genome = dict(seeds["deduplicated_volatility_trend"])

    first = decode_candidate(base, genome, spec).config["model"]["feature_cols"]
    second = decode_candidate(base, genome, spec).config["model"]["feature_cols"]

    assert first == second
    assert len(first) == len(set(first))
    assert first == [column for column in base["model"]["feature_cols"] if column in first]


def test_ehlers_trend_and_cycle_can_be_ablated_independently() -> None:
    spec, base, seeds = _inputs()
    families = spec.genome.decoder_params["feature_families"]

    trend_only = dict(seeds["full_baseline"])
    trend_only["use_ehlers_cycle"] = False
    trend_features = decode_candidate(base, trend_only, spec).config["model"]["feature_cols"]
    assert set(families["ehlers_trend"]).issubset(trend_features)
    assert set(families["ehlers_cycle"]).isdisjoint(trend_features)

    cycle_only = dict(seeds["full_baseline"])
    cycle_only["use_ehlers_trend"] = False
    cycle_features = decode_candidate(base, cycle_only, spec).config["model"]["feature_cols"]
    assert set(families["ehlers_cycle"]).issubset(cycle_features)
    assert set(families["ehlers_trend"]).isdisjoint(cycle_features)


def test_feature_families_are_an_exact_non_overlapping_46_column_partition() -> None:
    spec, base, _ = _inputs()
    families = spec.genome.decoder_params["feature_families"]
    flattened = [column for columns in families.values() for column in columns]

    assert len(flattened) == len(set(flattened)) == 46
    assert set(flattened) == set(base["model"]["feature_cols"])


def test_minimum_and_maximum_family_contract_is_declared_and_enforced() -> None:
    spec, base, seeds = _inputs()
    family_constraint = next(
        item for item in spec.genome.constraints if item["kind"] == "enabled_count"
    )
    assert family_constraint["minimum"] == 3
    assert family_constraint["maximum"] == 8
    assert len(family_constraint["genes"]) == 8
    assert len(spec.genome.genes) == 14
    assert set(spec.genome.decoder_params["feature_families"]) == {
        "returns_lags",
        "medium_returns",
        "volatility_atr",
        "bollinger_range",
        "ema_trend",
        "ehlers_trend",
        "ehlers_cycle",
        "candle_structure",
    }
    assert sum(
        len(columns)
        for columns in spec.genome.decoder_params["feature_families"].values()
    ) == 46
    genome = dict(seeds["full_baseline"])
    for gene in family_constraint["genes"]:
        genome[gene] = False
    genome[family_constraint["genes"][0]] = True
    genome[family_constraint["genes"][1]] = True

    with pytest.raises(GenomeValidationError, match="below minimum"):
        decode_candidate(base, genome, spec)


def test_disabled_gate_removes_only_that_activation_filter() -> None:
    spec, base, seeds = _inputs()
    genome = dict(seeds["full_baseline"])
    genome["range_to_atr_lower"] = "disabled"

    filters = decode_candidate(base, genome, spec).config["signals"]["params"]["activation_filters"]

    assert [item["col"] for item in filters] == [
        "atr_pct_rank_192",
        "atr_pct_rank_192",
        "bollinger_bandwidth_rank_192",
    ]


def test_invalid_atr_lower_upper_range_is_rejected() -> None:
    spec, base, seeds = _inputs()
    genome = dict(seeds["full_baseline"])
    genome["atr_percentile_lower"] = 0.80
    genome["atr_percentile_upper"] = 0.70

    with pytest.raises(GenomeValidationError, match="requires atr_percentile_lower < atr_percentile_upper"):
        decode_candidate(base, genome, spec)


def test_decoder_does_not_mutate_base_and_hash_is_stable() -> None:
    spec, base, seeds = _inputs()
    before = deepcopy(base)

    first = decode_candidate(base, seeds["full_baseline"], spec)
    second = decode_candidate(
        base,
        dict(reversed(list(seeds["full_baseline"].items()))),
        spec,
        generation=7,
        parent_ids=(2, 5),
    )

    assert base == before
    assert first.candidate_hash == second.candidate_hash
    assert first.decoded_config_hash == second.decoded_config_hash
    assert first.decoder_contract_hash == second.decoder_contract_hash
    assert first.search_contract_hash == second.search_contract_hash
    assert first.config["research_metadata"]["evolutionary_candidate"]["generation"] == 0
    assert second.config["research_metadata"]["evolutionary_candidate"]["generation"] == 7
