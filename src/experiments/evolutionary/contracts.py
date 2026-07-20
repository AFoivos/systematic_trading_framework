from __future__ import annotations

"""Deterministic decoder and search contracts for identity and safe resume."""

from dataclasses import asdict
import hashlib
from typing import Any, Mapping

from src.experiments.evolutionary.schemas import EvolutionarySpec
from src.utils.run_metadata import canonical_json_dumps


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_dumps(payload).encode("utf-8")).hexdigest()


def decoder_contract_payload(spec: EvolutionarySpec) -> dict[str, Any]:
    """Return only fields that determine how a genome becomes a clean config."""
    return {
        "decoder": spec.genome.decoder,
        "decoder_version": spec.genome.decoder_version,
        "decoder_params": spec.genome.decoder_params,
        "gene_specs": {
            name: asdict(gene) for name, gene in spec.genome.genes.items()
        },
        "genome_constraints": list(spec.genome.constraints),
    }


def decoder_contract_hash(spec: EvolutionarySpec) -> str:
    return _payload_hash(decoder_contract_payload(spec))


def search_contract_payload(
    spec: EvolutionarySpec,
    *,
    base_config_hash: str,
    resolved_decoder_contract_hash: str | None = None,
) -> dict[str, Any]:
    """Return behavior-affecting search fields, excluding budget and artifact flags."""
    decoder_hash = resolved_decoder_contract_hash or decoder_contract_hash(spec)
    return {
        "base_config_hash": str(base_config_hash),
        "decoder_contract_hash": decoder_hash,
        "search_semantics": {
            "backend": spec.search.backend,
            "seed": spec.search.seed,
            "population_size": spec.search.population_size,
            "crossover_probability": spec.search.crossover_probability,
            "mutation_probability": spec.search.mutation_probability,
            "duplicate_policy": spec.search.duplicate_policy,
        },
        "fitness": {
            "mode": spec.fitness.mode,
            "components": [asdict(component) for component in spec.fitness.components],
            "hard_constraints": [
                asdict(constraint) for constraint in spec.fitness.hard_constraints
            ],
            "failure_score": spec.fitness.failure_score,
            "evaluation_policy": asdict(spec.fitness.evaluation_policy),
        },
        "promotion": asdict(spec.promotion),
        "objective_direction": spec.fitness.direction,
    }


def search_contract_hash(
    spec: EvolutionarySpec,
    *,
    base_config_hash: str,
    resolved_decoder_contract_hash: str | None = None,
) -> str:
    return _payload_hash(
        search_contract_payload(
            spec,
            base_config_hash=base_config_hash,
            resolved_decoder_contract_hash=resolved_decoder_contract_hash,
        )
    )


__all__ = [
    "decoder_contract_hash",
    "decoder_contract_payload",
    "search_contract_hash",
    "search_contract_payload",
]
