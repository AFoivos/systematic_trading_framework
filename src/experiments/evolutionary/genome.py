from __future__ import annotations

"""Genome validation, Optuna sampling, and stable candidate identities."""

import hashlib
import math
from typing import Any, Mapping

from src.experiments.optuna_search import get_nested_value
from src.experiments.evolutionary.schemas import GeneSpec, GenomeSpec
from src.utils.run_metadata import canonical_json_dumps


class GenomeValidationError(ValueError):
    """Raised when a sampled or seeded genome violates its declared contract."""


def canonical_genome(genome: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-stable genome mapping with deterministic key order."""
    return {str(name): genome[name] for name in sorted(genome)}


def candidate_hash(
    genome: Mapping[str, Any],
    *,
    base_config_hash: str,
    decoder_contract_hash: str | None = None,
    decoded_config_hash: str | None = None,
    decoder: str | None = None,
    decoder_version: int | None = None,
) -> str:
    """Hash a genome, base config, decoder contract, and clean decoded config.

    ``decoder`` and ``decoder_version`` remain as a legacy compatibility path for
    callers that cannot yet provide a complete decoder contract hash.
    """
    resolved_decoder_hash = decoder_contract_hash
    if resolved_decoder_hash is None:
        if decoder is None or decoder_version is None:
            raise TypeError(
                "candidate_hash requires decoder_contract_hash, or legacy decoder and "
                "decoder_version arguments."
            )
        legacy_contract = {
            "decoder": str(decoder),
            "decoder_version": int(decoder_version),
        }
        resolved_decoder_hash = hashlib.sha256(
            canonical_json_dumps(legacy_contract).encode("utf-8")
        ).hexdigest()
    payload = {
        "base_config_hash": str(base_config_hash),
        "decoded_config_hash": (
            str(decoded_config_hash) if decoded_config_hash is not None else "legacy_unavailable"
        ),
        "decoder_contract_hash": str(resolved_decoder_hash),
        "genome": canonical_genome(genome),
    }
    return hashlib.sha256(canonical_json_dumps(payload).encode("utf-8")).hexdigest()


def _validate_gene_value(value: Any, gene: GeneSpec) -> None:
    field = f"genome[{gene.name!r}]"
    if gene.kind == "bool":
        if not isinstance(value, bool):
            raise GenomeValidationError(f"{field} must be boolean.")
        return
    if gene.kind == "categorical":
        if not any(value == choice and type(value) is type(choice) for choice in gene.choices):
            raise GenomeValidationError(
                f"{field}={value!r} is not one of the declared choices {list(gene.choices)!r}."
            )
        return
    if isinstance(value, bool):
        raise GenomeValidationError(f"{field} must be numeric, not boolean.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise GenomeValidationError(f"{field} must be numeric.") from exc
    if not math.isfinite(numeric):
        raise GenomeValidationError(f"{field} must be finite.")
    assert gene.low is not None and gene.high is not None
    if numeric < float(gene.low) or numeric > float(gene.high):
        raise GenomeValidationError(
            f"{field}={numeric} is outside [{gene.low}, {gene.high}]."
        )
    if gene.kind == "int" and (not isinstance(value, int) or int(value) != numeric):
        raise GenomeValidationError(f"{field} must be an integer.")
    if gene.step is not None:
        offset = (numeric - float(gene.low)) / float(gene.step)
        if not math.isclose(offset, round(offset), rel_tol=0.0, abs_tol=1e-9):
            raise GenomeValidationError(
                f"{field}={numeric} does not align to declared step {gene.step}."
            )


def _check_bound(value: int, constraint: Mapping[str, Any], *, label: str) -> None:
    minimum = constraint.get("minimum")
    maximum = constraint.get("maximum")
    if minimum is not None and value < int(minimum):
        raise GenomeValidationError(f"{label}={value} is below minimum {minimum}.")
    if maximum is not None and value > int(maximum):
        raise GenomeValidationError(f"{label}={value} exceeds maximum {maximum}.")


def _validate_constraints(
    genome: Mapping[str, Any],
    constraints: tuple[dict[str, Any], ...],
    *,
    decoded_config: Mapping[str, Any] | None,
) -> None:
    for index, constraint in enumerate(constraints):
        kind = str(constraint["kind"])
        label = f"genome.constraints[{index}] ({kind})"
        if kind == "enabled_count":
            enabled = sum(bool(genome[gene]) for gene in constraint["genes"])
            _check_bound(enabled, constraint, label=f"{label} enabled count")
        elif kind == "decoded_list_length":
            if decoded_config is None:
                continue
            try:
                value = get_nested_value(decoded_config, str(constraint["path"]))
            except Exception as exc:
                raise GenomeValidationError(
                    f"{label} cannot resolve decoded path {constraint['path']!r}."
                ) from exc
            if not isinstance(value, list):
                raise GenomeValidationError(f"{label} decoded path must resolve to a list.")
            _check_bound(len(value), constraint, label=f"{label} list length")
        elif kind == "ordered_pair":
            lower = genome[str(constraint["lower_gene"])]
            upper = genome[str(constraint["upper_gene"])]
            ignored = list(constraint.get("ignore_values", []) or [])
            if lower in ignored or upper in ignored:
                continue
            if not float(lower) < float(upper):
                raise GenomeValidationError(
                    f"{label} requires {constraint['lower_gene']} < {constraint['upper_gene']}."
                )
        elif kind == "distinct_groups":
            groups = dict(constraint["groups"])
            selected = {
                str(groups[gene])
                for gene in constraint["genes"]
                if bool(genome[gene])
            }
            _check_bound(len(selected), constraint, label=f"{label} distinct group count")
        elif kind == "any_enabled":
            if not any(bool(genome[gene]) for gene in constraint["genes"]):
                raise GenomeValidationError(f"{label} requires at least one enabled gene.")
        else:  # Schema validation should make this unreachable.
            raise GenomeValidationError(f"Unsupported genome constraint kind: {kind!r}.")


def validate_genome(
    genome: Mapping[str, Any],
    genome_spec: GenomeSpec,
    *,
    decoded_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate exact gene coverage, values, and declared structural constraints."""
    candidate = dict(genome)
    expected = set(genome_spec.genes)
    missing = sorted(expected - set(candidate))
    unknown = sorted(set(candidate) - expected)
    if missing or unknown:
        raise GenomeValidationError(
            f"Genome keys do not match the spec; missing={missing}, unknown={unknown}."
        )
    for name, gene in genome_spec.genes.items():
        _validate_gene_value(candidate[name], gene)
    _validate_constraints(candidate, genome_spec.constraints, decoded_config=decoded_config)
    return canonical_genome(candidate)


def sample_genome(trial: Any, genome_spec: GenomeSpec) -> dict[str, Any]:
    """Sample every declared gene through an Optuna trial."""
    sampled: dict[str, Any] = {}
    for name, gene in genome_spec.genes.items():
        if gene.kind == "bool":
            sampled[name] = trial.suggest_categorical(name, [False, True])
        elif gene.kind == "categorical":
            sampled[name] = trial.suggest_categorical(name, list(gene.choices))
        elif gene.kind == "int":
            assert gene.low is not None and gene.high is not None
            sampled[name] = trial.suggest_int(
                name,
                int(gene.low),
                int(gene.high),
                step=int(gene.step or 1),
                log=gene.log,
            )
        elif gene.kind == "float":
            assert gene.low is not None and gene.high is not None
            sampled[name] = trial.suggest_float(
                name,
                float(gene.low),
                float(gene.high),
                step=float(gene.step) if gene.step is not None else None,
                log=gene.log,
            )
        else:  # pragma: no cover - guarded by schema validation.
            raise GenomeValidationError(f"Unsupported gene type: {gene.kind!r}.")
    return validate_genome(sampled, genome_spec)


def validate_seed_candidates(genome_spec: GenomeSpec) -> None:
    """Validate all seed genomes and reject duplicate canonical seeds."""
    seen: dict[str, str] = {}
    for seed in genome_spec.seed_candidates:
        canonical = validate_genome(seed.genome, genome_spec)
        identity = canonical_json_dumps(canonical)
        if identity in seen:
            raise GenomeValidationError(
                f"Seed candidates {seen[identity]!r} and {seed.name!r} have duplicate genomes."
            )
        seen[identity] = seed.name


__all__ = [
    "GenomeValidationError",
    "candidate_hash",
    "canonical_genome",
    "sample_genome",
    "validate_genome",
    "validate_seed_candidates",
]
