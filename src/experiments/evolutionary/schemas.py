from __future__ import annotations

"""Strict dataclass schema for repository evolutionary-search specifications."""

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import yaml

from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path


GeneKind = Literal["bool", "categorical", "int", "float"]
Direction = Literal["maximize", "minimize"]
_COMPARISON_OPERATORS = {"finite", "eq", "ne", "lt", "le", "gt", "ge", "in"}


def _mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be a mapping.")
    return dict(value)


def _sequence(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field} must be a list.")
    return list(value)


def _reject_unknown(payload: Mapping[str, Any], allowed: set[str], *, field: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{field} has unsupported keys: {unknown}.")


def _required_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _finite(value: Any, *, field: str) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field} must be numeric.") from exc
    if not math.isfinite(resolved):
        raise ValueError(f"{field} must be finite.")
    return resolved


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


@dataclass(frozen=True)
class SearchSpec:
    name: str
    family: str
    backend: str
    seed: int
    population_size: int
    generations: int
    crossover_probability: float
    mutation_probability: float
    storage: str | None
    resume: bool
    duplicate_policy: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SearchSpec":
        data = _mapping(raw, field="search")
        allowed = {
            "name",
            "family",
            "backend",
            "seed",
            "population_size",
            "generations",
            "crossover_probability",
            "mutation_probability",
            "storage",
            "resume",
            "duplicate_policy",
        }
        _reject_unknown(data, allowed, field="search")
        backend = _required_text(data.get("backend"), field="search.backend")
        if backend != "optuna_nsga2":
            raise ValueError("search.backend must be 'optuna_nsga2'.")
        if isinstance(data.get("seed"), bool) or not isinstance(data.get("seed"), int):
            raise TypeError("search.seed must be an integer.")
        crossover = _finite(data.get("crossover_probability"), field="search.crossover_probability")
        mutation = _finite(data.get("mutation_probability"), field="search.mutation_probability")
        if not 0.0 <= crossover <= 1.0 or not 0.0 <= mutation <= 1.0:
            raise ValueError("search crossover/mutation probabilities must be in [0, 1].")
        storage = data.get("storage")
        if storage is not None and (not isinstance(storage, str) or not storage.strip()):
            raise TypeError("search.storage must be null or a non-empty string.")
        if not isinstance(data.get("resume"), bool):
            raise TypeError("search.resume must be boolean.")
        duplicate_policy = _required_text(
            data.get("duplicate_policy"), field="search.duplicate_policy"
        )
        if duplicate_policy not in {"reuse", "reject", "reevaluate"}:
            raise ValueError(
                "search.duplicate_policy must be one of: reuse, reject, reevaluate."
            )
        population_size = _positive_int(
            data.get("population_size"), field="search.population_size"
        )
        if population_size < 2:
            raise ValueError("search.population_size must be >= 2 for NSGA-II.")
        return cls(
            name=_required_text(data.get("name"), field="search.name"),
            family=_required_text(data.get("family"), field="search.family"),
            backend=backend,
            seed=int(data["seed"]),
            population_size=population_size,
            generations=_positive_int(data.get("generations"), field="search.generations"),
            crossover_probability=crossover,
            mutation_probability=mutation,
            storage=storage.strip() if isinstance(storage, str) else None,
            resume=bool(data["resume"]),
            duplicate_policy=duplicate_policy,
        )


@dataclass(frozen=True)
class BaseExperimentSpec:
    config: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BaseExperimentSpec":
        data = _mapping(raw, field="base_experiment")
        _reject_unknown(data, {"config"}, field="base_experiment")
        return cls(config=_required_text(data.get("config"), field="base_experiment.config"))


@dataclass(frozen=True)
class GeneSpec:
    name: str
    kind: GeneKind
    choices: tuple[Any, ...] = ()
    low: int | float | None = None
    high: int | float | None = None
    step: int | float | None = None
    log: bool = False

    @classmethod
    def from_dict(cls, name: str, raw: Mapping[str, Any]) -> "GeneSpec":
        data = _mapping(raw, field=f"genome.genes.{name}")
        _reject_unknown(
            data,
            {"type", "choices", "low", "high", "step", "log"},
            field=f"genome.genes.{name}",
        )
        kind = _required_text(data.get("type"), field=f"genome.genes.{name}.type")
        if kind not in {"bool", "categorical", "int", "float"}:
            raise ValueError(f"genome.genes.{name}.type is unsupported: {kind!r}.")
        choices: tuple[Any, ...] = ()
        low: int | float | None = None
        high: int | float | None = None
        step: int | float | None = None
        log = data.get("log", False)
        if not isinstance(log, bool):
            raise TypeError(f"genome.genes.{name}.log must be boolean.")
        if kind == "categorical":
            raw_choices = _sequence(data.get("choices"), field=f"genome.genes.{name}.choices")
            if not raw_choices:
                raise ValueError(f"genome.genes.{name}.choices must not be empty.")
            if any(isinstance(item, (dict, list, tuple, set)) for item in raw_choices):
                raise TypeError(f"genome.genes.{name}.choices must contain scalar values.")
            if len({repr(item) for item in raw_choices}) != len(raw_choices):
                raise ValueError(f"genome.genes.{name}.choices must not contain duplicates.")
            choices = tuple(raw_choices)
            if set(data) - {"type", "choices"}:
                raise ValueError(
                    f"categorical gene {name!r} accepts only type and choices."
                )
        elif kind in {"int", "float"}:
            if "low" not in data or "high" not in data:
                raise ValueError(f"numeric gene {name!r} requires low and high.")
            low_value = _finite(data["low"], field=f"genome.genes.{name}.low")
            high_value = _finite(data["high"], field=f"genome.genes.{name}.high")
            if low_value >= high_value:
                raise ValueError(f"genome.genes.{name} must satisfy low < high.")
            if kind == "int":
                if int(low_value) != low_value or int(high_value) != high_value:
                    raise TypeError(f"integer gene {name!r} bounds must be integers.")
                low, high = int(low_value), int(high_value)
            else:
                low, high = low_value, high_value
            if data.get("step") is not None:
                step_value = _finite(data["step"], field=f"genome.genes.{name}.step")
                if step_value <= 0:
                    raise ValueError(f"genome.genes.{name}.step must be > 0.")
                if kind == "int" and int(step_value) != step_value:
                    raise TypeError(f"integer gene {name!r} step must be an integer.")
                step = int(step_value) if kind == "int" else step_value
            if log and step is not None:
                raise ValueError(f"numeric gene {name!r} cannot combine log=true with step.")
        else:
            if set(data) != {"type"}:
                raise ValueError(f"boolean gene {name!r} accepts only the type key.")
        return cls(
            name=name,
            kind=kind,  # type: ignore[arg-type]
            choices=choices,
            low=low,
            high=high,
            step=step,
            log=log,
        )


@dataclass(frozen=True)
class SeedCandidateSpec:
    name: str
    genome: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, index: int) -> "SeedCandidateSpec":
        data = _mapping(raw, field=f"genome.seed_candidates[{index}]")
        _reject_unknown(data, {"name", "genome"}, field=f"genome.seed_candidates[{index}]")
        return cls(
            name=_required_text(data.get("name"), field=f"genome.seed_candidates[{index}].name"),
            genome=_mapping(data.get("genome"), field=f"genome.seed_candidates[{index}].genome"),
        )


def _validate_decoder_params(decoder: str, raw: Any) -> dict[str, Any]:
    data = _mapping(raw, field="genome.decoder_params")
    if decoder == "ethusd_feature_gate_v1":
        _reject_unknown(
            data,
            {"feature_families", "family_genes", "threshold_genes", "gate_genes"},
            field="genome.decoder_params",
        )
        families = _mapping(data.get("feature_families"), field="genome.decoder_params.feature_families")
        family_genes = _mapping(data.get("family_genes"), field="genome.decoder_params.family_genes")
        threshold_genes = _mapping(data.get("threshold_genes"), field="genome.decoder_params.threshold_genes")
        gate_genes = _mapping(data.get("gate_genes"), field="genome.decoder_params.gate_genes")
        _reject_unknown(threshold_genes, {"upper", "lower"}, field="genome.decoder_params.threshold_genes")
        _reject_unknown(
            gate_genes,
            {"atr_lower", "atr_upper", "range_to_atr_lower", "bollinger_bandwidth_rank_lower"},
            field="genome.decoder_params.gate_genes",
        )
        if set(families) != set(family_genes):
            raise ValueError("feature_families and family_genes must define the same family names.")
        seen_columns: set[str] = set()
        for family, raw_columns in families.items():
            _required_text(family, field="genome.decoder_params.feature_families key")
            columns = _sequence(raw_columns, field=f"genome.decoder_params.feature_families.{family}")
            if not columns or any(not isinstance(column, str) or not column.strip() for column in columns):
                raise ValueError(f"feature family {family!r} must be a non-empty list[str].")
            duplicate = seen_columns.intersection(columns)
            if duplicate:
                raise ValueError(f"feature families overlap on columns: {sorted(duplicate)}.")
            seen_columns.update(columns)
        for mapping_name, mapping_value in (
            ("family_genes", family_genes),
            ("threshold_genes", threshold_genes),
            ("gate_genes", gate_genes),
        ):
            for key, value in mapping_value.items():
                _required_text(value, field=f"genome.decoder_params.{mapping_name}.{key}")
        return data

    if decoder == "matb_asset_module_v1":
        _reject_unknown(
            data,
            {"asset_genes", "asset_groups", "module_gene"},
            field="genome.decoder_params",
        )
        asset_genes = _mapping(data.get("asset_genes"), field="genome.decoder_params.asset_genes")
        asset_groups = _mapping(data.get("asset_groups"), field="genome.decoder_params.asset_groups")
        if not asset_genes or set(asset_genes) != set(asset_groups):
            raise ValueError("asset_genes and asset_groups must define the same non-empty asset universe.")
        for asset, gene in asset_genes.items():
            _required_text(asset, field="genome.decoder_params.asset_genes key")
            _required_text(gene, field=f"genome.decoder_params.asset_genes.{asset}")
            _required_text(asset_groups[asset], field=f"genome.decoder_params.asset_groups.{asset}")
        _required_text(data.get("module_gene"), field="genome.decoder_params.module_gene")
        return data

    raise ValueError(f"Unsupported genome.decoder: {decoder!r}.")


_CONSTRAINT_KEYS = {
    "enabled_count": {"kind", "genes", "minimum", "maximum"},
    "decoded_list_length": {"kind", "path", "minimum", "maximum"},
    "ordered_pair": {"kind", "lower_gene", "upper_gene", "relation", "ignore_values"},
    "distinct_groups": {"kind", "genes", "groups", "minimum", "maximum"},
    "any_enabled": {"kind", "genes"},
}


def _validate_genome_constraint(raw: Any, *, index: int) -> dict[str, Any]:
    data = _mapping(raw, field=f"genome.constraints[{index}]")
    kind = _required_text(data.get("kind"), field=f"genome.constraints[{index}].kind")
    allowed = _CONSTRAINT_KEYS.get(kind)
    if allowed is None:
        raise ValueError(f"Unsupported genome constraint kind: {kind!r}.")
    _reject_unknown(data, allowed, field=f"genome.constraints[{index}]")
    if kind in {"enabled_count", "distinct_groups", "any_enabled"}:
        genes = _sequence(data.get("genes"), field=f"genome.constraints[{index}].genes")
        if not genes or any(not isinstance(gene, str) or not gene.strip() for gene in genes):
            raise ValueError(f"genome.constraints[{index}].genes must be a non-empty list[str].")
    if kind in {"enabled_count", "decoded_list_length", "distinct_groups"}:
        if data.get("minimum") is None and data.get("maximum") is None:
            raise ValueError(f"genome.constraints[{index}] requires minimum and/or maximum.")
        for bound in ("minimum", "maximum"):
            if data.get(bound) is not None:
                value = data[bound]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f"genome.constraints[{index}].{bound} must be an integer >= 0.")
        if data.get("minimum") is not None and data.get("maximum") is not None:
            if int(data["minimum"]) > int(data["maximum"]):
                raise ValueError(f"genome.constraints[{index}] has minimum > maximum.")
    if kind == "decoded_list_length":
        _required_text(data.get("path"), field=f"genome.constraints[{index}].path")
    if kind == "ordered_pair":
        _required_text(data.get("lower_gene"), field=f"genome.constraints[{index}].lower_gene")
        _required_text(data.get("upper_gene"), field=f"genome.constraints[{index}].upper_gene")
        if data.get("relation") != "lt":
            raise ValueError("ordered_pair currently supports relation: lt only.")
        _sequence(data.get("ignore_values", []), field=f"genome.constraints[{index}].ignore_values")
    if kind == "distinct_groups":
        groups = _mapping(data.get("groups"), field=f"genome.constraints[{index}].groups")
        if not groups or any(not isinstance(value, str) or not value.strip() for value in groups.values()):
            raise ValueError(f"genome.constraints[{index}].groups must map genes to group names.")
    return data


@dataclass(frozen=True)
class GenomeSpec:
    decoder: str
    decoder_version: int
    decoder_params: dict[str, Any]
    genes: dict[str, GeneSpec]
    constraints: tuple[dict[str, Any], ...]
    seed_candidates: tuple[SeedCandidateSpec, ...]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GenomeSpec":
        data = _mapping(raw, field="genome")
        _reject_unknown(
            data,
            {"decoder", "decoder_version", "decoder_params", "genes", "constraints", "seed_candidates"},
            field="genome",
        )
        decoder = _required_text(data.get("decoder"), field="genome.decoder")
        decoder_version = _positive_int(data.get("decoder_version"), field="genome.decoder_version")
        raw_genes = _mapping(data.get("genes"), field="genome.genes")
        if not raw_genes:
            raise ValueError("genome.genes must not be empty.")
        genes = {
            _required_text(name, field="genome.genes key"): GeneSpec.from_dict(str(name), spec)
            for name, spec in raw_genes.items()
        }
        constraints = tuple(
            _validate_genome_constraint(item, index=index)
            for index, item in enumerate(_sequence(data.get("constraints", []), field="genome.constraints"))
        )
        seeds = tuple(
            SeedCandidateSpec.from_dict(item, index=index)
            for index, item in enumerate(
                _sequence(data.get("seed_candidates", []), field="genome.seed_candidates")
            )
        )
        if not seeds:
            raise ValueError("genome.seed_candidates must contain at least one candidate.")
        seed_names = [seed.name for seed in seeds]
        if len(set(seed_names)) != len(seed_names):
            raise ValueError("genome.seed_candidates names must be unique.")
        decoder_params = _validate_decoder_params(decoder, data.get("decoder_params"))
        for index, constraint in enumerate(constraints):
            kind = str(constraint["kind"])
            referenced: list[str] = []
            if kind in {"enabled_count", "distinct_groups", "any_enabled"}:
                referenced.extend(str(value) for value in constraint["genes"])
            elif kind == "ordered_pair":
                referenced.extend(
                    [str(constraint["lower_gene"]), str(constraint["upper_gene"])]
                )
            unknown = sorted(set(referenced) - set(genes))
            if unknown:
                raise ValueError(
                    f"genome.constraints[{index}] references unknown genes: {unknown}."
                )
            if kind in {"enabled_count", "distinct_groups", "any_enabled"}:
                non_boolean = [name for name in referenced if genes[name].kind != "bool"]
                if non_boolean:
                    raise ValueError(
                        f"genome.constraints[{index}] requires boolean genes: {non_boolean}."
                    )
            if kind == "distinct_groups" and set(constraint["groups"]) != set(referenced):
                raise ValueError(
                    f"genome.constraints[{index}].groups must exactly map its genes."
                )

        if decoder == "ethusd_feature_gate_v1":
            family_genes = list(dict(decoder_params["family_genes"]).values())
            threshold_genes = list(dict(decoder_params["threshold_genes"]).values())
            gate_genes = list(dict(decoder_params["gate_genes"]).values())
            decoder_genes = [str(value) for value in family_genes + threshold_genes + gate_genes]
            if len(set(decoder_genes)) != len(decoder_genes):
                raise ValueError("ETHUSD decoder gene references must be unique.")
            unknown = sorted(set(decoder_genes) - set(genes))
            if unknown:
                raise ValueError(f"ETHUSD decoder references unknown genes: {unknown}.")
            unused = sorted(set(genes) - set(decoder_genes))
            if unused:
                raise ValueError(f"ETHUSD spec declares genes unused by its decoder: {unused}.")
            if any(genes[str(name)].kind != "bool" for name in family_genes):
                raise ValueError("ETHUSD feature-family genes must be boolean.")
            if any(genes[str(name)].kind != "categorical" for name in threshold_genes + gate_genes):
                raise ValueError("ETHUSD threshold and gate genes must be categorical.")
            for name in gate_genes:
                if "disabled" not in genes[str(name)].choices:
                    raise ValueError(f"ETHUSD gate gene {name!r} must include choice 'disabled'.")
        else:
            asset_genes = [str(value) for value in dict(decoder_params["asset_genes"]).values()]
            module_gene = str(decoder_params["module_gene"])
            decoder_genes = asset_genes + [module_gene]
            unknown = sorted(set(decoder_genes) - set(genes))
            if unknown:
                raise ValueError(f"MATB decoder references unknown genes: {unknown}.")
            if len(set(asset_genes)) != len(asset_genes):
                raise ValueError("MATB asset_genes values must be unique.")
            if module_gene in asset_genes:
                raise ValueError("MATB module_gene must be distinct from every asset gene.")
            unused = sorted(set(genes) - set(decoder_genes))
            if unused:
                raise ValueError(f"MATB spec declares genes unused by its decoder: {unused}.")
            if any(genes[name].kind != "bool" for name in decoder_genes):
                raise ValueError("MATB asset and module genes must be boolean.")

        return cls(
            decoder=decoder,
            decoder_version=decoder_version,
            decoder_params=decoder_params,
            genes=genes,
            constraints=constraints,
            seed_candidates=seeds,
        )


@dataclass(frozen=True)
class FitnessComponentSpec:
    name: str
    metric_path: str
    weight: float
    transform: str
    missing_policy: str
    missing_penalty: float | None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, index: int) -> "FitnessComponentSpec":
        data = _mapping(raw, field=f"fitness.components[{index}]")
        _reject_unknown(
            data,
            {"name", "metric_path", "weight", "transform", "missing_policy", "missing_penalty"},
            field=f"fitness.components[{index}]",
        )
        transform = _required_text(data.get("transform", "identity"), field=f"fitness.components[{index}].transform")
        if transform not in {"identity", "abs", "negative_abs"}:
            raise ValueError(f"fitness.components[{index}].transform is unsupported.")
        missing_policy = _required_text(
            data.get("missing_policy", "reject"),
            field=f"fitness.components[{index}].missing_policy",
        )
        if missing_policy not in {"reject", "penalize"}:
            raise ValueError(f"fitness.components[{index}].missing_policy must be reject or penalize.")
        missing_penalty = data.get("missing_penalty")
        if missing_policy == "penalize" and missing_penalty is None:
            raise ValueError(f"fitness.components[{index}] requires missing_penalty when penalize is used.")
        if missing_policy == "reject" and missing_penalty is not None:
            raise ValueError(f"fitness.components[{index}] cannot set missing_penalty with reject.")
        return cls(
            name=_required_text(data.get("name"), field=f"fitness.components[{index}].name"),
            metric_path=_required_text(
                data.get("metric_path"), field=f"fitness.components[{index}].metric_path"
            ),
            weight=_finite(data.get("weight"), field=f"fitness.components[{index}].weight"),
            transform=transform,
            missing_policy=missing_policy,
            missing_penalty=(
                _finite(missing_penalty, field=f"fitness.components[{index}].missing_penalty")
                if missing_penalty is not None
                else None
            ),
        )


@dataclass(frozen=True)
class HardConstraintSpec:
    name: str
    metric_path: str
    operator: str
    threshold: Any
    missing_policy: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, index: int) -> "HardConstraintSpec":
        data = _mapping(raw, field=f"fitness.hard_constraints[{index}]")
        _reject_unknown(
            data,
            {"name", "metric_path", "operator", "threshold", "missing_policy"},
            field=f"fitness.hard_constraints[{index}]",
        )
        operator = _required_text(data.get("operator"), field=f"fitness.hard_constraints[{index}].operator")
        if operator not in _COMPARISON_OPERATORS:
            raise ValueError(f"fitness.hard_constraints[{index}].operator is unsupported.")
        if operator != "finite" and "threshold" not in data:
            raise ValueError(f"fitness.hard_constraints[{index}] requires threshold.")
        if operator == "in":
            threshold = data.get("threshold")
            if not isinstance(threshold, Sequence) or isinstance(threshold, (str, bytes)):
                raise TypeError(
                    f"fitness.hard_constraints[{index}].threshold must be a list for operator 'in'."
                )
        missing_policy = _required_text(
            data.get("missing_policy", "reject"),
            field=f"fitness.hard_constraints[{index}].missing_policy",
        )
        if missing_policy != "reject":
            raise ValueError("Hard constraints currently require missing_policy: reject.")
        return cls(
            name=_required_text(data.get("name"), field=f"fitness.hard_constraints[{index}].name"),
            metric_path=_required_text(
                data.get("metric_path"), field=f"fitness.hard_constraints[{index}].metric_path"
            ),
            operator=operator,
            threshold=data.get("threshold"),
            missing_policy=missing_policy,
        )


@dataclass(frozen=True)
class PromotionGateSpec:
    name: str
    metric_path: str
    operator: str
    threshold: Any
    missing_policy: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, index: int) -> "PromotionGateSpec":
        field = f"promotion.gates[{index}]"
        data = _mapping(raw, field=field)
        _reject_unknown(
            data,
            {"name", "metric_path", "operator", "threshold", "missing_policy"},
            field=field,
        )
        operator = _required_text(data.get("operator"), field=f"{field}.operator")
        if operator not in _COMPARISON_OPERATORS:
            raise ValueError(f"{field}.operator is unsupported.")
        if operator != "finite" and "threshold" not in data:
            raise ValueError(f"{field} requires threshold.")
        if operator == "in":
            threshold = data.get("threshold")
            if not isinstance(threshold, Sequence) or isinstance(threshold, (str, bytes)):
                raise TypeError(f"{field}.threshold must be a list for operator 'in'.")
        missing_policy = _required_text(
            data.get("missing_policy", "fail"), field=f"{field}.missing_policy"
        )
        if missing_policy != "fail":
            raise ValueError("Promotion gates require missing_policy: fail.")
        return cls(
            name=_required_text(data.get("name"), field=f"{field}.name"),
            metric_path=_required_text(data.get("metric_path"), field=f"{field}.metric_path"),
            operator=operator,
            threshold=data.get("threshold"),
            missing_policy=missing_policy,
        )


@dataclass(frozen=True)
class PromotionSpec:
    enabled: bool
    gates: tuple[PromotionGateSpec, ...]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "PromotionSpec":
        if raw is None:
            return cls(enabled=False, gates=())
        data = _mapping(raw, field="promotion")
        _reject_unknown(data, {"enabled", "gates"}, field="promotion")
        if not isinstance(data.get("enabled"), bool):
            raise TypeError("promotion.enabled must be boolean.")
        gates = tuple(
            PromotionGateSpec.from_dict(item, index=index)
            for index, item in enumerate(
                _sequence(data.get("gates", []), field="promotion.gates")
            )
        )
        names = [gate.name for gate in gates]
        if len(set(names)) != len(names):
            raise ValueError("promotion.gates names must be unique.")
        if bool(data["enabled"]) and not gates:
            raise ValueError("promotion.gates must not be empty when promotion.enabled=true.")
        if not bool(data["enabled"]) and gates:
            raise ValueError("promotion.gates must be empty when promotion.enabled=false.")
        return cls(enabled=bool(data["enabled"]), gates=gates)


@dataclass(frozen=True)
class EvaluationPolicySpec:
    allowed_scopes: tuple[str, ...]
    require_walk_forward: bool
    forbidden_metric_tokens: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EvaluationPolicySpec":
        data = _mapping(raw, field="fitness.evaluation_policy")
        _reject_unknown(
            data,
            {"allowed_scopes", "require_walk_forward", "forbidden_metric_tokens"},
            field="fitness.evaluation_policy",
        )
        scopes = tuple(
            _required_text(item, field="fitness.evaluation_policy.allowed_scopes[]")
            for item in _sequence(data.get("allowed_scopes"), field="fitness.evaluation_policy.allowed_scopes")
        )
        if not scopes:
            raise ValueError("fitness.evaluation_policy.allowed_scopes must not be empty.")
        if not isinstance(data.get("require_walk_forward"), bool):
            raise TypeError("fitness.evaluation_policy.require_walk_forward must be boolean.")
        tokens = tuple(
            _required_text(item, field="fitness.evaluation_policy.forbidden_metric_tokens[]").lower()
            for item in _sequence(
                data.get("forbidden_metric_tokens", []),
                field="fitness.evaluation_policy.forbidden_metric_tokens",
            )
        )
        return cls(
            allowed_scopes=scopes,
            require_walk_forward=bool(data["require_walk_forward"]),
            forbidden_metric_tokens=tokens,
        )


@dataclass(frozen=True)
class FitnessSpec:
    mode: str
    direction: Direction
    components: tuple[FitnessComponentSpec, ...]
    hard_constraints: tuple[HardConstraintSpec, ...]
    failure_score: float
    evaluation_policy: EvaluationPolicySpec

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FitnessSpec":
        data = _mapping(raw, field="fitness")
        _reject_unknown(
            data,
            {"mode", "direction", "components", "hard_constraints", "failure_score", "evaluation_policy"},
            field="fitness",
        )
        mode = _required_text(data.get("mode"), field="fitness.mode")
        if mode != "weighted_sum":
            raise ValueError("fitness.mode currently supports only 'weighted_sum'.")
        direction = _required_text(data.get("direction"), field="fitness.direction")
        if direction not in {"maximize", "minimize"}:
            raise ValueError("fitness.direction must be maximize or minimize.")
        components = tuple(
            FitnessComponentSpec.from_dict(item, index=index)
            for index, item in enumerate(
                _sequence(data.get("components"), field="fitness.components")
            )
        )
        if not components:
            raise ValueError("fitness.components must not be empty.")
        component_names = [component.name for component in components]
        if len(set(component_names)) != len(component_names):
            raise ValueError("fitness.components names must be unique.")
        hard_constraints = tuple(
            HardConstraintSpec.from_dict(item, index=index)
            for index, item in enumerate(
                _sequence(data.get("hard_constraints", []), field="fitness.hard_constraints")
            )
        )
        constraint_names = [constraint.name for constraint in hard_constraints]
        if len(set(constraint_names)) != len(constraint_names):
            raise ValueError("fitness.hard_constraints names must be unique.")
        all_paths = [component.metric_path for component in components] + [
            constraint.metric_path for constraint in hard_constraints
        ]
        policy = EvaluationPolicySpec.from_dict(data.get("evaluation_policy"))
        for path in all_paths:
            lowered = path.lower()
            forbidden = [token for token in policy.forbidden_metric_tokens if token in lowered]
            if forbidden:
                raise ValueError(
                    f"Fitness metric path {path!r} contains forbidden holdout token(s): {forbidden}."
                )
        return cls(
            mode=mode,
            direction=direction,  # type: ignore[arg-type]
            components=components,
            hard_constraints=hard_constraints,
            failure_score=_finite(data.get("failure_score"), field="fitness.failure_score"),
            evaluation_policy=policy,
        )


@dataclass(frozen=True)
class ExecutionSpec:
    logging_enabled: bool
    save_candidate_configs: bool
    save_failed_candidates: bool
    candidate_output_dir: str
    maximum_parallel_workers: int

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ExecutionSpec":
        data = _mapping(raw, field="execution")
        allowed = {
            "logging_enabled",
            "save_candidate_configs",
            "save_failed_candidates",
            "candidate_output_dir",
            "maximum_parallel_workers",
        }
        _reject_unknown(data, allowed, field="execution")
        for key in ("logging_enabled", "save_candidate_configs", "save_failed_candidates"):
            if not isinstance(data.get(key), bool):
                raise TypeError(f"execution.{key} must be boolean.")
        return cls(
            logging_enabled=bool(data["logging_enabled"]),
            save_candidate_configs=bool(data["save_candidate_configs"]),
            save_failed_candidates=bool(data["save_failed_candidates"]),
            candidate_output_dir=_required_text(
                data.get("candidate_output_dir"), field="execution.candidate_output_dir"
            ),
            maximum_parallel_workers=_positive_int(
                data.get("maximum_parallel_workers"),
                field="execution.maximum_parallel_workers",
            ),
        )


@dataclass(frozen=True)
class FrequencyAnalysisSpec:
    enabled: bool
    elite_fraction: float
    elite_minimum_candidates: int
    include_final_generation: bool

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "FrequencyAnalysisSpec":
        if raw is None:
            return cls(
                enabled=False,
                elite_fraction=0.10,
                elite_minimum_candidates=5,
                include_final_generation=True,
            )
        data = _mapping(raw, field="artifacts.frequency_analysis")
        allowed = {
            "enabled",
            "elite_fraction",
            "elite_minimum_candidates",
            "include_final_generation",
        }
        _reject_unknown(data, allowed, field="artifacts.frequency_analysis")
        for key in ("enabled", "include_final_generation"):
            if not isinstance(data.get(key), bool):
                raise TypeError(f"artifacts.frequency_analysis.{key} must be boolean.")
        elite_fraction = _finite(
            data.get("elite_fraction"),
            field="artifacts.frequency_analysis.elite_fraction",
        )
        if not 0.0 < elite_fraction <= 1.0:
            raise ValueError("artifacts.frequency_analysis.elite_fraction must be in (0, 1].")
        return cls(
            enabled=bool(data["enabled"]),
            elite_fraction=elite_fraction,
            elite_minimum_candidates=_positive_int(
                data.get("elite_minimum_candidates"),
                field="artifacts.frequency_analysis.elite_minimum_candidates",
            ),
            include_final_generation=bool(data["include_final_generation"]),
        )


@dataclass(frozen=True)
class ArtifactSpec:
    output_dir: str
    save_evaluations: bool
    save_generation_summary: bool
    save_feature_frequency: bool
    save_gate_frequency: bool
    save_asset_frequency: bool
    save_group_frequency: bool
    save_module_frequency: bool
    save_best_candidates: bool
    save_pareto_front: bool
    frequency_analysis: FrequencyAnalysisSpec

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ArtifactSpec":
        data = _mapping(raw, field="artifacts")
        allowed = {
            "output_dir",
            "save_evaluations",
            "save_generation_summary",
            "save_feature_frequency",
            "save_gate_frequency",
            "save_asset_frequency",
            "save_group_frequency",
            "save_module_frequency",
            "save_best_candidates",
            "save_pareto_front",
            "frequency_analysis",
        }
        _reject_unknown(data, allowed, field="artifacts")
        bool_keys = allowed - {"output_dir", "frequency_analysis"}
        for key in bool_keys:
            if not isinstance(data.get(key), bool):
                raise TypeError(f"artifacts.{key} must be boolean.")
        return cls(
            output_dir=_required_text(data.get("output_dir"), field="artifacts.output_dir"),
            frequency_analysis=FrequencyAnalysisSpec.from_dict(
                data.get("frequency_analysis")
            ),
            **{key: bool(data[key]) for key in bool_keys},
        )


@dataclass(frozen=True)
class EvolutionarySpec:
    schema_version: int
    metadata: dict[str, Any]
    search: SearchSpec
    base_experiment: BaseExperimentSpec
    genome: GenomeSpec
    fitness: FitnessSpec
    promotion: PromotionSpec
    execution: ExecutionSpec
    artifacts: ArtifactSpec
    spec_path: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, spec_path: str | Path) -> "EvolutionarySpec":
        data = _mapping(raw, field="evolutionary spec")
        allowed = {
            "schema_version",
            "metadata",
            "search",
            "base_experiment",
            "genome",
            "fitness",
            "promotion",
            "execution",
            "artifacts",
        }
        _reject_unknown(data, allowed, field="evolutionary spec")
        if data.get("schema_version") != 1:
            raise ValueError("evolutionary spec schema_version must be 1.")
        metadata = _mapping(data.get("metadata", {}), field="metadata")
        _reject_unknown(
            metadata,
            {
                "description",
                "budget_class",
                "final_holdout_policy",
                "drawdown_metric_note",
            },
            field="metadata",
        )
        for key, value in metadata.items():
            _required_text(value, field=f"metadata.{key}")
        fitness = FitnessSpec.from_dict(data.get("fitness"))
        promotion = PromotionSpec.from_dict(data.get("promotion"))
        for gate in promotion.gates:
            lowered = gate.metric_path.lower()
            forbidden = [
                token for token in fitness.evaluation_policy.forbidden_metric_tokens
                if token in lowered
            ]
            if forbidden:
                raise ValueError(
                    f"Promotion metric path {gate.metric_path!r} contains forbidden "
                    f"holdout token(s): {forbidden}."
                )
        return cls(
            schema_version=1,
            metadata=metadata,
            search=SearchSpec.from_dict(data.get("search")),
            base_experiment=BaseExperimentSpec.from_dict(data.get("base_experiment")),
            genome=GenomeSpec.from_dict(data.get("genome")),
            fitness=fitness,
            promotion=promotion,
            execution=ExecutionSpec.from_dict(data.get("execution")),
            artifacts=ArtifactSpec.from_dict(data.get("artifacts")),
            spec_path=str(Path(spec_path).resolve()),
        )

    @property
    def base_config_path(self) -> Path:
        path = Path(self.base_experiment.config)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return enforce_safe_absolute_path(path)

    @property
    def output_dir(self) -> Path:
        path = Path(self.artifacts.output_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return enforce_safe_absolute_path(path)

    def to_manifest_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["genome"]["genes"] = {
            name: asdict(gene) for name, gene in self.genome.genes.items()
        }
        return payload


def load_evolutionary_spec(path: str | Path) -> EvolutionarySpec:
    """Load and strictly validate one evolutionary-search YAML without executing it."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    resolved = enforce_safe_absolute_path(resolved)
    if not resolved.is_file():
        raise FileNotFoundError(f"Evolutionary spec does not exist: {resolved}")
    with resolved.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return EvolutionarySpec.from_dict(payload, spec_path=resolved)


__all__ = [
    "ArtifactSpec",
    "BaseExperimentSpec",
    "EvaluationPolicySpec",
    "EvolutionarySpec",
    "ExecutionSpec",
    "FitnessComponentSpec",
    "FitnessSpec",
    "FrequencyAnalysisSpec",
    "GeneSpec",
    "GenomeSpec",
    "HardConstraintSpec",
    "PromotionGateSpec",
    "PromotionSpec",
    "SearchSpec",
    "SeedCandidateSpec",
    "load_evolutionary_spec",
]
