"""Validated evolutionary search infrastructure for experiment configs."""

from importlib import import_module
from typing import Any


_LAZY_ATTRS = {
    "DecodedCandidate": "src.experiments.evolutionary.decoders",
    "EvolutionarySpec": "src.experiments.evolutionary.schemas",
    "FitnessResult": "src.experiments.evolutionary.fitness",
    "PromotionResult": "src.experiments.evolutionary.fitness",
    "candidate_hash": "src.experiments.evolutionary.genome",
    "decode_candidate": "src.experiments.evolutionary.decoders",
    "decoder_contract_hash": "src.experiments.evolutionary.contracts",
    "evaluate_promotion": "src.experiments.evolutionary.fitness",
    "load_evolutionary_spec": "src.experiments.evolutionary.schemas",
    "search_contract_hash": "src.experiments.evolutionary.contracts",
    "score_candidate": "src.experiments.evolutionary.fitness",
    "validate_genome": "src.experiments.evolutionary.genome",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_ATTRS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_LAZY_ATTRS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "DecodedCandidate",
    "EvolutionarySpec",
    "FitnessResult",
    "PromotionResult",
    "candidate_hash",
    "decode_candidate",
    "decoder_contract_hash",
    "evaluate_promotion",
    "load_evolutionary_spec",
    "search_contract_hash",
    "score_candidate",
    "validate_genome",
]
