from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from src.experiments.evolutionary.contracts import (
    decoder_contract_hash,
    search_contract_hash,
)
from src.experiments.evolutionary.decoders import decode_candidate
from src.experiments.evolutionary.schemas import load_evolutionary_spec
from src.utils.config import load_experiment_config
from src.utils.run_metadata import compute_config_hash


SPEC_PATH = Path(
    "config/evolutionary/ethusd_foundation/ga_ethusd_feature_gate_v1.yaml"
)


def _inputs():
    spec = load_evolutionary_spec(SPEC_PATH)
    base = load_experiment_config(spec.base_config_path)
    genome = dict(spec.genome.seed_candidates[0].genome)
    return spec, base, genome


def test_decoder_and_search_contract_hashes_are_deterministic() -> None:
    spec, base, _ = _inputs()
    base_hash, _ = compute_config_hash(base)

    assert decoder_contract_hash(spec) == decoder_contract_hash(spec)
    assert search_contract_hash(
        spec, base_config_hash=base_hash
    ) == search_contract_hash(spec, base_config_hash=base_hash)


def test_decoder_parameter_change_changes_candidate_identity() -> None:
    spec, base, genome = _inputs()
    params = deepcopy(spec.genome.decoder_params)
    params["feature_families"]["ehlers_trend"] = list(
        reversed(params["feature_families"]["ehlers_trend"])
    )
    changed = replace(spec, genome=replace(spec.genome, decoder_params=params))

    baseline = decode_candidate(base, genome, spec)
    modified = decode_candidate(base, genome, changed)

    assert baseline.decoded_config_hash == modified.decoded_config_hash
    assert baseline.decoder_contract_hash != modified.decoder_contract_hash
    assert baseline.candidate_hash != modified.candidate_hash


def test_fitness_only_change_preserves_candidate_identity_but_changes_search_contract() -> None:
    spec, base, genome = _inputs()
    components = list(spec.fitness.components)
    components[0] = replace(components[0], weight=components[0].weight + 0.25)
    changed = replace(spec, fitness=replace(spec.fitness, components=tuple(components)))

    baseline = decode_candidate(base, genome, spec)
    modified = decode_candidate(base, genome, changed)

    assert baseline.decoded_config_hash == modified.decoded_config_hash
    assert baseline.decoder_contract_hash == modified.decoder_contract_hash
    assert baseline.candidate_hash == modified.candidate_hash
    assert baseline.search_contract_hash != modified.search_contract_hash


def test_budget_and_artifact_changes_do_not_change_search_contract() -> None:
    spec, base, _ = _inputs()
    base_hash, _ = compute_config_hash(base)
    changed = replace(
        spec,
        search=replace(spec.search, generations=4),
        artifacts=replace(spec.artifacts, save_generation_summary=False),
    )

    assert search_contract_hash(
        spec, base_config_hash=base_hash
    ) == search_contract_hash(changed, base_config_hash=base_hash)


def test_sampler_semantics_change_search_contract() -> None:
    spec, base, _ = _inputs()
    base_hash, _ = compute_config_hash(base)
    changed = replace(spec, search=replace(spec.search, population_size=16))

    assert search_contract_hash(
        spec, base_config_hash=base_hash
    ) != search_contract_hash(changed, base_config_hash=base_hash)


def test_search_name_is_checked_separately_not_folded_into_contract_hash() -> None:
    spec, base, _ = _inputs()
    base_hash, _ = compute_config_hash(base)
    renamed = replace(spec, search=replace(spec.search, name="renamed_search"))

    assert search_contract_hash(
        spec, base_config_hash=base_hash
    ) == search_contract_hash(renamed, base_config_hash=base_hash)
