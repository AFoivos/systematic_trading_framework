from __future__ import annotations

"""Optuna NSGA-II-backed evolutionary orchestration over existing experiments."""

from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import tempfile
from threading import Lock
from typing import Any, Mapping, Sequence

import yaml

from src.experiments.evolutionary.archive import EvolutionaryArchive
from src.experiments.evolutionary.contracts import (
    decoder_contract_hash,
    search_contract_hash,
)
from src.experiments.evolutionary.decoders import DecodedCandidate, decode_candidate
from src.experiments.evolutionary.fitness import (
    evaluate_promotion,
    failed_fitness,
    score_candidate,
)
from src.experiments.evolutionary.genome import (
    GenomeValidationError,
    sample_genome,
    validate_seed_candidates,
)
from src.experiments.evolutionary.schemas import EvolutionarySpec, load_evolutionary_spec
from src.utils.config import load_experiment_config
from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path
from src.utils.run_metadata import compute_config_hash, file_sha256


def _require_optuna() -> Any:
    try:
        import optuna
    except Exception as exc:
        raise ImportError(
            "Evolutionary search requires the repository's Optuna dependency. "
            "Install the project dependencies before running "
            "src.experiments.evolutionary.cli."
        ) from exc
    return optuna


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _trial_parent_ids(trial: Any) -> tuple[int, ...]:
    attrs = dict(getattr(trial, "system_attrs", {}) or {})
    for key, value in attrs.items():
        if "parent" in str(key).lower() and isinstance(value, (list, tuple)):
            return tuple(int(item) for item in value)
    return ()


def _trial_generation(trial: Any, *, population_size: int) -> int:
    attrs = dict(getattr(trial, "system_attrs", {}) or {})
    for key, value in attrs.items():
        if "generation" in str(key).lower():
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return int(getattr(trial, "number", 0)) // int(population_size)


def _prepare_storage(storage: str | None) -> str | None:
    if storage is None:
        return None
    prefix = "sqlite:///"
    if not storage.startswith(prefix):
        return storage
    raw_path = storage[len(prefix) :]
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = enforce_safe_absolute_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{path}"


def _run_experiment_config(candidate: DecodedCandidate) -> Any:
    from src.experiments.runner import run_experiment

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".yaml",
        prefix=f"evolutionary_{candidate.candidate_hash[:12]}_",
        delete=False,
    ) as handle:
        yaml.safe_dump(candidate.config, handle, sort_keys=False)
        path = Path(handle.name)
    try:
        return run_experiment(path)
    finally:
        path.unlink(missing_ok=True)


def validate_evolutionary_spec(
    spec_path: str | Path,
) -> tuple[EvolutionarySpec, dict[str, Any], list[DecodedCandidate]]:
    """Validate schema, base experiment, decoder consistency, and every seed only."""
    spec = load_evolutionary_spec(spec_path)
    if not spec.base_config_path.is_file():
        raise FileNotFoundError(
            f"base_experiment.config does not exist: {spec.base_config_path}"
        )
    if spec.search.resume and spec.search.storage is None:
        raise ValueError("search.resume=true requires persistent search.storage.")
    if spec.execution.maximum_parallel_workers != 1:
        raise ValueError(
            "Deterministic evolutionary v1 requires execution.maximum_parallel_workers=1."
        )
    EvolutionaryArchive(spec)  # Validate output containment without creating directories.
    base_config = load_experiment_config(spec.base_config_path)
    validate_seed_candidates(spec.genome)
    total_budget = spec.search.population_size * spec.search.generations
    if len(spec.genome.seed_candidates) > total_budget:
        raise ValueError(
            "genome.seed_candidates cannot exceed the declared search candidate budget."
        )
    decoded_seeds = [
        decode_candidate(base_config, seed.genome, spec, generation=0, parent_ids=())
        for seed in spec.genome.seed_candidates
    ]
    hashes = [candidate.candidate_hash for candidate in decoded_seeds]
    if len(set(hashes)) != len(hashes):
        raise GenomeValidationError("Seed candidates decode to duplicate candidate hashes.")
    return spec, base_config, decoded_seeds


def _existing_candidates(study: Any) -> dict[str, dict[str, Any]]:
    existing: dict[str, dict[str, Any]] = {}
    for trial in list(getattr(study, "trials", []) or []):
        attrs = dict(getattr(trial, "user_attrs", {}) or {})
        candidate_id = attrs.get("candidate_hash")
        value = getattr(trial, "value", None)
        if (
            isinstance(candidate_id, str)
            and value is not None
            and attrs.get("duplicate_of") is None
        ):
            existing[candidate_id] = {
                "trial": int(trial.number),
                "value": float(value),
                "rejected": bool(attrs.get("rejected", False)),
                "failure_reason": attrs.get("failure_reason"),
                "fitness_components": dict(attrs.get("fitness_components", {}) or {}),
                "resolved_metrics": dict(attrs.get("resolved_metrics", {}) or {}),
                "promotion_passed": bool(attrs.get("promotion_passed", False)),
                "promotion_failures": list(attrs.get("promotion_failures", []) or []),
                "promotion_metrics": dict(attrs.get("promotion_metrics", {}) or {}),
            }
    return existing


def _set_trial_identity(trial: Any, candidate: DecodedCandidate) -> None:
    trial.set_user_attr("base_config_hash", candidate.base_config_hash)
    trial.set_user_attr("candidate_hash", candidate.candidate_hash)
    trial.set_user_attr("decoded_config_hash", candidate.decoded_config_hash)
    trial.set_user_attr("decoder_contract_hash", candidate.decoder_contract_hash)
    trial.set_user_attr("decoder", candidate.decoder)
    trial.set_user_attr("decoder_version", candidate.decoder_version)
    trial.set_user_attr("decoder_context", _jsonable(candidate.context))
    trial.set_user_attr("generation", candidate.generation)
    trial.set_user_attr("genome", _jsonable(candidate.genome))
    trial.set_user_attr("parent_ids", list(candidate.parent_ids))
    trial.set_user_attr("search_contract_hash", candidate.search_contract_hash)


def _reject_trial(trial: Any, *, spec: EvolutionarySpec, reason: str) -> float:
    fitness = failed_fitness(spec, reason)
    trial.set_user_attr("failure_reason", fitness.reason)
    trial.set_user_attr("rejected", True)
    trial.set_user_attr("fitness_components", {})
    trial.set_user_attr("promotion_failures", [])
    trial.set_user_attr("promotion_metrics", {})
    trial.set_user_attr("promotion_passed", False)
    trial.set_user_attr("resolved_metrics", {})
    return fitness.score


def _handle_duplicate(
    trial: Any,
    *,
    spec: EvolutionarySpec,
    duplicate: Mapping[str, Any] | None,
) -> tuple[bool, float | None]:
    """Apply the declared duplicate policy without running the experiment again."""
    if duplicate is None or int(duplicate["trial"]) == int(trial.number):
        return False, None
    if spec.search.duplicate_policy == "reevaluate":
        return False, None
    trial.set_user_attr("duplicate_of", int(duplicate["trial"]))
    if spec.search.duplicate_policy == "reject":
        return True, _reject_trial(
            trial,
            spec=spec,
            reason=f"duplicate_candidate:{duplicate['trial']}",
        )
    trial.set_user_attr("duplicate_reused", True)
    trial.set_user_attr("rejected", bool(duplicate["rejected"]))
    if duplicate.get("failure_reason") is not None:
        trial.set_user_attr("failure_reason", duplicate["failure_reason"])
    for key in (
        "fitness_components",
        "resolved_metrics",
        "promotion_passed",
        "promotion_failures",
        "promotion_metrics",
    ):
        trial.set_user_attr(key, _jsonable(duplicate[key]))
    return True, float(duplicate["value"])


def _validate_and_set_study_contract(
    study: Any,
    *,
    search_name: str,
    decoder_hash: str,
    search_hash: str,
    base_config_hash: str,
) -> None:
    expected = {
        "search_name": search_name,
        "decoder_contract_hash": decoder_hash,
        "search_contract_hash": search_hash,
    }
    attrs = dict(getattr(study, "user_attrs", {}) or {})
    has_existing_state = bool(list(getattr(study, "trials", []) or [])) or bool(attrs)
    if has_existing_state:
        for key, value in expected.items():
            if attrs.get(key) != value:
                raise ValueError(
                    f"Optuna study resume contract mismatch for {key!r}: "
                    f"existing={attrs.get(key)!r}, requested={value!r}."
                )
    for key, value in expected.items():
        study.set_user_attr(key, value)
    study.set_user_attr("base_config_hash", base_config_hash)


def run_evolutionary_search(spec_path: str | Path) -> Any:
    """Run a validated evolutionary spec through existing experiment/backtest machinery."""
    spec, base_config, decoded_seeds = validate_evolutionary_spec(spec_path)
    base_config_hash, _ = compute_config_hash(base_config)
    resolved_decoder_contract_hash = decoder_contract_hash(spec)
    resolved_search_contract_hash = search_contract_hash(
        spec,
        base_config_hash=base_config_hash,
        resolved_decoder_contract_hash=resolved_decoder_contract_hash,
    )
    optuna = _require_optuna()
    archive = EvolutionaryArchive(spec)
    archive.validate_run_destination()
    archive.validate_resume_contract(
        search_name=spec.search.name,
        decoder_contract_hash=resolved_decoder_contract_hash,
        search_contract_hash=resolved_search_contract_hash,
    )
    sampler = optuna.samplers.NSGAIISampler(
        population_size=spec.search.population_size,
        mutation_prob=spec.search.mutation_probability,
        crossover_prob=spec.search.crossover_probability,
        seed=spec.search.seed,
    )
    storage = _prepare_storage(spec.search.storage)
    study = optuna.create_study(
        study_name=spec.search.name,
        storage=storage,
        load_if_exists=spec.search.resume,
        direction=spec.fitness.direction,
        sampler=sampler,
    )
    _validate_and_set_study_contract(
        study,
        search_name=spec.search.name,
        decoder_hash=resolved_decoder_contract_hash,
        search_hash=resolved_search_contract_hash,
        base_config_hash=base_config_hash,
    )
    if not list(study.trials):
        for seed in spec.genome.seed_candidates:
            study.enqueue_trial(dict(seed.genome), user_attrs={"seed_candidate": seed.name})

    try:
        optuna_version = version("optuna")
    except PackageNotFoundError:  # pragma: no cover - _require_optuna already succeeded.
        optuna_version = "unknown"
    total_budget = spec.search.population_size * spec.search.generations
    archive.initialize(
        {
            "backend": spec.search.backend,
            "base_config": str(spec.base_config_path),
            "base_config_hash": base_config_hash,
            "budget": {
                "generations": spec.search.generations,
                "population_size": spec.search.population_size,
                "total_candidates": total_budget,
            },
            "checkpoint_storage": storage,
            "decoder": spec.genome.decoder,
            "decoder_contract_hash": resolved_decoder_contract_hash,
            "decoder_version": spec.genome.decoder_version,
            "duplicate_policy": spec.search.duplicate_policy,
            "optuna_version": optuna_version,
            "resume": spec.search.resume,
            "sampler": "optuna.samplers.NSGAIISampler",
            "search_name": spec.search.name,
            "search_contract_hash": resolved_search_contract_hash,
            "seed": spec.search.seed,
            "spec": spec.to_manifest_dict(),
            "spec_path": spec.spec_path,
            "spec_sha256": file_sha256(spec.spec_path),
            "status": "running",
        }
    )

    seen = _existing_candidates(study)
    seen_lock = Lock()
    candidate_configs: dict[str, dict[str, Any]] = {
        seed.candidate_hash: seed.config for seed in decoded_seeds
    }

    def objective(trial: Any) -> float:
        generation = _trial_generation(
            trial, population_size=spec.search.population_size
        )
        parent_ids = _trial_parent_ids(trial)
        try:
            genome = sample_genome(trial, spec.genome)
            candidate = decode_candidate(
                base_config,
                genome,
                spec,
                generation=generation,
                parent_ids=parent_ids,
            )
            _set_trial_identity(trial, candidate)
        except Exception as exc:
            sampled = dict(getattr(trial, "params", {}) or {})
            trial.set_user_attr("base_config_hash", base_config_hash)
            trial.set_user_attr("decoder_contract_hash", resolved_decoder_contract_hash)
            trial.set_user_attr("decoder", spec.genome.decoder)
            trial.set_user_attr("decoder_version", spec.genome.decoder_version)
            trial.set_user_attr("generation", generation)
            trial.set_user_attr("genome", _jsonable(sampled))
            trial.set_user_attr("parent_ids", list(parent_ids))
            trial.set_user_attr("search_contract_hash", resolved_search_contract_hash)
            return _reject_trial(
                trial,
                spec=spec,
                reason=f"decode_failed: {type(exc).__name__}: {exc}",
            )

        with seen_lock:
            duplicate = seen.get(candidate.candidate_hash)
            handled, duplicate_value = _handle_duplicate(
                trial,
                spec=spec,
                duplicate=duplicate,
            )
            if handled:
                assert duplicate_value is not None
                return duplicate_value

        candidate_configs[candidate.candidate_hash] = candidate.config
        archive.write_candidate_config(candidate.candidate_hash, candidate.config)
        try:
            result = _run_experiment_config(candidate)
            fitness = score_candidate(result, spec, context=candidate.context)
        except Exception as exc:
            score = _reject_trial(
                trial,
                spec=spec,
                reason=f"evaluation_failed: {type(exc).__name__}: {exc}",
            )
            with seen_lock:
                attrs = dict(getattr(trial, "user_attrs", {}) or {})
                seen[candidate.candidate_hash] = {
                    "trial": int(trial.number),
                    "value": float(score),
                    "rejected": True,
                    "failure_reason": attrs.get("failure_reason"),
                    "fitness_components": {},
                    "resolved_metrics": {},
                    "promotion_passed": False,
                    "promotion_failures": list(attrs.get("promotion_failures", []) or []),
                    "promotion_metrics": {},
                }
            return score

        trial.set_user_attr("fitness_components", _jsonable(fitness.components))
        trial.set_user_attr("resolved_metrics", _jsonable(fitness.resolved_metrics))
        trial.set_user_attr("rejected", fitness.rejected)
        if fitness.reason is not None:
            trial.set_user_attr("failure_reason", fitness.reason)
        if fitness.rejected:
            promotion_passed = False
            promotion_failures = []
            promotion_metrics: dict[str, Any] = {}
        else:
            promotion = evaluate_promotion(result, spec, context=candidate.context)
            promotion_passed = promotion.passed
            promotion_failures = list(promotion.failures)
            promotion_metrics = promotion.metrics
        trial.set_user_attr("promotion_passed", promotion_passed)
        trial.set_user_attr("promotion_failures", _jsonable(promotion_failures))
        trial.set_user_attr("promotion_metrics", _jsonable(promotion_metrics))
        with seen_lock:
            seen[candidate.candidate_hash] = {
                "trial": int(trial.number),
                "value": float(fitness.score),
                "rejected": bool(fitness.rejected),
                "failure_reason": fitness.reason,
                "fitness_components": fitness.components,
                "resolved_metrics": fitness.resolved_metrics,
                "promotion_passed": promotion_passed,
                "promotion_failures": promotion_failures,
                "promotion_metrics": promotion_metrics,
            }
        return float(fitness.score)

    finished_states = {"COMPLETE", "FAIL", "PRUNED"}
    finished_count = sum(
        getattr(getattr(trial, "state", None), "name", "") in finished_states
        for trial in list(study.trials)
    )
    remaining = max(total_budget - finished_count, 0)
    try:
        if remaining:
            study.optimize(
                objective,
                n_trials=remaining,
                n_jobs=spec.execution.maximum_parallel_workers,
                catch=(Exception,),
            )
        artifacts = archive.write_study_artifacts(
            study, candidate_configs=candidate_configs
        )
        archive.update_manifest(
            {
                "artifacts": artifacts,
                "completed_trials": len(study.trials),
                "status": "completed",
            }
        )
        study.set_user_attr("evolutionary_artifacts", json.loads(json.dumps(artifacts)))
        return study
    except BaseException:
        artifacts = archive.write_study_artifacts(
            study, candidate_configs=candidate_configs
        )
        archive.update_manifest(
            {
                "artifacts": artifacts,
                "completed_trials": len(study.trials),
                "status": "interrupted",
            }
        )
        raise


__all__ = ["run_evolutionary_search", "validate_evolutionary_spec"]
