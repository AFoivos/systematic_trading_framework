from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
from pathlib import Path
import tempfile
from typing import Any, Literal, Mapping, Sequence

import yaml

from src.experiments.optuna_runtime import optuna_fold_reporting_context
from src.utils.config import load_experiment_config
from src.utils.paths import PROJECT_ROOT

ParameterKind = Literal["int", "float", "categorical", "bool"]
ObjectiveDirection = Literal["maximize", "minimize"]
ConstraintOperator = Literal["lt", "le", "gt", "ge"]

_DEFAULT_OBJECTIVE_PATH = "evaluation.primary_summary.sharpe"
_DEFAULT_SAMPLER = "tpe"


@dataclass(frozen=True)
class SearchDimension:
    """
    One Optuna-tunable parameter mapped onto an existing experiment config path.

    `path` supports dotted access such as `model.params.learning_rate` or list indices such as
    `features.3.params.ema_spans.0`.
    """

    name: str
    path: str | Sequence[str | int]
    kind: ParameterKind
    low: int | float | None = None
    high: int | float | None = None
    step: int | float | None = None
    log: bool = False
    choices: Sequence[Any] | None = None


@dataclass(frozen=True)
class ObjectiveSpec:
    """
    Describe which numeric experiment output Optuna should optimize.
    """

    metric_path: str = _DEFAULT_OBJECTIVE_PATH
    direction: ObjectiveDirection = "maximize"
    failure_score: float | None = None
    base_metric_weight: float = 1.0
    constraints: Sequence["ConstraintPenalty"] = field(default_factory=tuple)
    stability_weight: float = 0.0
    stability_metric_path: str | None = None
    stability_std_penalty: float = 1.0
    fold_summary_path: str = "evaluation.fold_backtest_summaries"


@dataclass(frozen=True)
class ConstraintPenalty:
    """
    Apply a fixed penalty when a resolved metric violates a threshold.
    """

    metric_path: str
    op: ConstraintOperator
    threshold: float
    penalty: float
    missing_penalty: float | None = None


@dataclass(frozen=True)
class PruningSpec:
    """
    Configure Optuna fold-level pruning when model stages emit intermediate fold payloads.
    """

    enabled: bool = False
    metric_path: str = "classification_metrics.roc_auc"
    direction: ObjectiveDirection = "maximize"
    stage_filter: Sequence[str] = field(default_factory=tuple)
    pruner: str = "median"
    n_startup_trials: int = 5
    n_warmup_steps: int = 0
    interval_steps: int = 1


def _default_failure_score(direction: ObjectiveDirection) -> float:
    if direction == "maximize":
        return -1.0e12
    if direction == "minimize":
        return 1.0e12
    raise ValueError(f"Unsupported objective direction: {direction}")


def _require_optuna() -> Any:
    try:
        import optuna
    except Exception as exc:
        raise ImportError(
            "Optuna search requires the optional 'optuna' dependency. "
            "Install optuna in the project environment before using src.experiments.optuna_search."
        ) from exc
    return optuna


def _coerce_path_token(token: str) -> str | int:
    stripped = token.strip()
    if not stripped:
        raise ValueError("Config path tokens must be non-empty.")
    if stripped.isdigit():
        return int(stripped)
    return stripped


def normalize_config_path(path: str | Sequence[str | int]) -> tuple[str | int, ...]:
    """
    Normalize a config path into concrete dict/list traversal tokens.
    """
    if isinstance(path, str):
        tokens = tuple(_coerce_path_token(part) for part in path.split("."))
    else:
        tokens = tuple(path)
    if not tokens:
        raise ValueError("Config path must contain at least one token.")
    return tokens


def _normalize_search_dimension(raw_dimension: SearchDimension | Mapping[str, Any]) -> SearchDimension:
    if isinstance(raw_dimension, SearchDimension):
        dimension = raw_dimension
    elif isinstance(raw_dimension, Mapping):
        dimension = SearchDimension(**dict(raw_dimension))
    else:
        raise TypeError("search_space entries must be SearchDimension instances or mappings.")

    if not isinstance(dimension.name, str) or not dimension.name.strip():
        raise ValueError("search_space dimensions require a non-empty name.")
    if dimension.kind not in {"int", "float", "categorical", "bool"}:
        raise ValueError(f"Unsupported search dimension kind: {dimension.kind}")

    normalize_config_path(dimension.path)

    if dimension.kind in {"int", "float"}:
        if dimension.low is None or dimension.high is None:
            raise ValueError(f"search_space[{dimension.name}] requires both low and high.")
        if float(dimension.low) >= float(dimension.high):
            raise ValueError(f"search_space[{dimension.name}] must satisfy low < high.")
        if dimension.kind == "int":
            for field_name, value in (("low", dimension.low), ("high", dimension.high)):
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(f"search_space[{dimension.name}].{field_name} must be an integer.")
            if dimension.step is not None and (
                isinstance(dimension.step, bool) or not isinstance(dimension.step, int) or int(dimension.step) <= 0
            ):
                raise ValueError(f"search_space[{dimension.name}].step must be a positive integer when provided.")
        else:
            if dimension.step is not None and float(dimension.step) <= 0.0:
                raise ValueError(f"search_space[{dimension.name}].step must be > 0 when provided.")
            if dimension.log and dimension.step is not None:
                raise ValueError(
                    f"search_space[{dimension.name}] cannot set both log=true and a discrete step."
                )
    else:
        if dimension.kind == "categorical":
            if dimension.choices is None or len(tuple(dimension.choices)) == 0:
                raise ValueError(f"search_space[{dimension.name}] categorical dimensions require non-empty choices.")
        if dimension.kind == "bool" and dimension.choices is not None:
            raise ValueError(f"search_space[{dimension.name}] bool dimensions do not accept explicit choices.")

    return dimension


def normalize_search_space(
    search_space: Sequence[SearchDimension | Mapping[str, Any]],
) -> list[SearchDimension]:
    """
    Normalize and validate an Optuna search space definition.
    """
    if not isinstance(search_space, Sequence) or isinstance(search_space, (str, bytes)):
        raise TypeError("search_space must be a sequence of dimensions.")
    normalized = [_normalize_search_dimension(raw_dimension) for raw_dimension in search_space]
    names = [dimension.name for dimension in normalized]
    if len(names) != len(set(names)):
        raise ValueError("search_space dimension names must be unique.")
    return normalized


def normalize_objective_spec(
    objective: ObjectiveSpec | Mapping[str, Any] | None,
) -> ObjectiveSpec:
    if objective is None:
        spec = ObjectiveSpec()
    elif isinstance(objective, ObjectiveSpec):
        spec = objective
    elif isinstance(objective, Mapping):
        spec = ObjectiveSpec(**dict(objective))
    else:
        raise TypeError("objective must be an ObjectiveSpec or mapping when provided.")

    if spec.direction not in {"maximize", "minimize"}:
        raise ValueError("objective.direction must be 'maximize' or 'minimize'.")
    if not isinstance(spec.metric_path, str) or not spec.metric_path.strip():
        raise ValueError("objective.metric_path must be a non-empty string.")
    if not math.isfinite(float(spec.base_metric_weight)):
        raise ValueError("objective.base_metric_weight must be finite.")
    if not math.isfinite(float(spec.stability_weight)):
        raise ValueError("objective.stability_weight must be finite.")
    if float(spec.stability_std_penalty) < 0.0:
        raise ValueError("objective.stability_std_penalty must be >= 0.")
    if not isinstance(spec.fold_summary_path, str) or not spec.fold_summary_path.strip():
        raise ValueError("objective.fold_summary_path must be a non-empty string.")
    normalized_constraints = tuple(_normalize_constraint_penalty(raw) for raw in spec.constraints)
    stability_metric_path = spec.stability_metric_path
    if float(spec.stability_weight) != 0.0:
        if stability_metric_path is None:
            stability_metric_path = "metrics.sharpe"
        if not isinstance(stability_metric_path, str) or not stability_metric_path.strip():
            raise ValueError("objective.stability_metric_path must be a non-empty string when stability_weight != 0.")
    return ObjectiveSpec(
        metric_path=spec.metric_path,
        direction=spec.direction,
        failure_score=spec.failure_score,
        base_metric_weight=float(spec.base_metric_weight),
        constraints=normalized_constraints,
        stability_weight=float(spec.stability_weight),
        stability_metric_path=stability_metric_path,
        stability_std_penalty=float(spec.stability_std_penalty),
        fold_summary_path=spec.fold_summary_path,
    )


def _normalize_constraint_penalty(
    raw_constraint: ConstraintPenalty | Mapping[str, Any],
) -> ConstraintPenalty:
    if isinstance(raw_constraint, ConstraintPenalty):
        constraint = raw_constraint
    elif isinstance(raw_constraint, Mapping):
        constraint = ConstraintPenalty(**dict(raw_constraint))
    else:
        raise TypeError("objective.constraints entries must be ConstraintPenalty instances or mappings.")

    if not isinstance(constraint.metric_path, str) or not constraint.metric_path.strip():
        raise ValueError("constraint.metric_path must be a non-empty string.")
    if constraint.op not in {"lt", "le", "gt", "ge"}:
        raise ValueError("constraint.op must be one of: lt, le, gt, ge.")
    if not math.isfinite(float(constraint.threshold)):
        raise ValueError("constraint.threshold must be finite.")
    if float(constraint.penalty) < 0.0:
        raise ValueError("constraint.penalty must be >= 0.")
    if constraint.missing_penalty is not None and float(constraint.missing_penalty) < 0.0:
        raise ValueError("constraint.missing_penalty must be >= 0 when provided.")
    return ConstraintPenalty(
        metric_path=constraint.metric_path,
        op=constraint.op,
        threshold=float(constraint.threshold),
        penalty=float(constraint.penalty),
        missing_penalty=float(constraint.missing_penalty) if constraint.missing_penalty is not None else None,
    )


def normalize_pruning_spec(
    pruning: PruningSpec | Mapping[str, Any] | None,
) -> PruningSpec:
    if pruning is None:
        spec = PruningSpec()
    elif isinstance(pruning, PruningSpec):
        spec = pruning
    elif isinstance(pruning, Mapping):
        spec = PruningSpec(**dict(pruning))
    else:
        raise TypeError("pruning must be a PruningSpec or mapping when provided.")

    if spec.direction not in {"maximize", "minimize"}:
        raise ValueError("pruning.direction must be 'maximize' or 'minimize'.")
    if not isinstance(spec.metric_path, str) or not spec.metric_path.strip():
        raise ValueError("pruning.metric_path must be a non-empty string.")
    if str(spec.pruner).strip().lower() not in {"median", "percentile", "none"}:
        raise ValueError("pruning.pruner must be one of: median, percentile, none.")
    if int(spec.n_startup_trials) < 0:
        raise ValueError("pruning.n_startup_trials must be >= 0.")
    if int(spec.n_warmup_steps) < 0:
        raise ValueError("pruning.n_warmup_steps must be >= 0.")
    if int(spec.interval_steps) <= 0:
        raise ValueError("pruning.interval_steps must be > 0.")
    normalized_stage_filter = tuple(str(stage) for stage in spec.stage_filter)
    return PruningSpec(
        enabled=bool(spec.enabled),
        metric_path=spec.metric_path,
        direction=spec.direction,
        stage_filter=normalized_stage_filter,
        pruner=str(spec.pruner).strip().lower(),
        n_startup_trials=int(spec.n_startup_trials),
        n_warmup_steps=int(spec.n_warmup_steps),
        interval_steps=int(spec.interval_steps),
    )


def get_nested_value(payload: Any, path: str | Sequence[str | int]) -> Any:
    """
    Resolve a nested value from mappings, sequences, or dataclass-like objects.
    """
    tokens = normalize_config_path(path)
    current = payload
    if tokens and tokens[0] == "derived":
        current = compute_derived_metrics(payload)
        tokens = tokens[1:]
    for token in tokens:
        if isinstance(current, Mapping):
            if token not in current:
                raise KeyError(f"Path token {token!r} not found in mapping.")
            current = current[token]
        elif isinstance(current, (list, tuple)):
            if not isinstance(token, int):
                raise TypeError(f"Sequence access requires an integer token, got {token!r}.")
            current = current[token]
        else:
            if not isinstance(token, str) or not hasattr(current, token):
                raise AttributeError(f"Path token {token!r} is not available on object {type(current).__name__}.")
            current = getattr(current, token)
    return current


def _single_asset_oos_mask(result: Any) -> Any:
    data = getattr(result, "data", None)
    if not isinstance(data, Mapping) and hasattr(data, "columns") and "pred_is_oos" in data.columns:
        return data["pred_is_oos"].astype(bool)
    return None


def _compute_trade_count(result: Any) -> float:
    backtest = getattr(result, "backtest", None)
    turnover = getattr(backtest, "turnover", None)
    if turnover is None:
        return 0.0

    series = turnover.astype(float)
    oos_mask = _single_asset_oos_mask(result)
    if oos_mask is not None and getattr(result, "evaluation", {}).get("scope") == "strict_oos_only":
        aligned_mask = oos_mask.reindex(series.index).fillna(False).astype(bool)
        if bool(aligned_mask.any()):
            series = series.loc[aligned_mask]
    return float((series.abs() > 1.0e-12).sum())


def compute_derived_metrics(result: Any) -> dict[str, float]:
    """
    Compute convenience metrics that are not part of the current canonical evaluation payload.
    """
    return {
        "trade_count": _compute_trade_count(result),
    }


def _extract_fold_metric_values(
    result: Any,
    *,
    fold_summary_path: str,
    metric_path: str,
) -> list[float]:
    fold_summaries = get_nested_value(result, fold_summary_path)
    if not isinstance(fold_summaries, Sequence) or isinstance(fold_summaries, (str, bytes)):
        raise TypeError("Fold summaries must resolve to a sequence.")

    values: list[float] = []
    for fold_summary in fold_summaries:
        raw_value = get_nested_value(fold_summary, metric_path)
        numeric_value = float(raw_value)
        if math.isfinite(numeric_value):
            values.append(numeric_value)
    return values


def _stability_score(
    result: Any,
    *,
    fold_summary_path: str,
    metric_path: str,
    std_penalty: float,
) -> float:
    values = _extract_fold_metric_values(
        result,
        fold_summary_path=fold_summary_path,
        metric_path=metric_path,
    )
    if not values:
        raise ValueError(
            f"No finite fold metrics found for fold_summary_path={fold_summary_path!r} "
            f"and metric_path={metric_path!r}."
        )
    mean_value = float(sum(values) / len(values))
    if len(values) <= 1:
        std_value = 0.0
    else:
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        std_value = float(math.sqrt(variance))
    return mean_value - float(std_penalty) * std_value


def _constraint_is_violated(value: float, *, op: ConstraintOperator, threshold: float) -> bool:
    if op == "lt":
        return value < threshold
    if op == "le":
        return value <= threshold
    if op == "gt":
        return value > threshold
    if op == "ge":
        return value >= threshold
    raise ValueError(f"Unsupported constraint operator: {op}")


def score_experiment_result(
    result: Any,
    objective: ObjectiveSpec | Mapping[str, Any] | None = None,
) -> float:
    """
    Compute a composite Optuna score from the experiment result.
    """
    spec = normalize_objective_spec(objective)
    score = 0.0
    if float(spec.base_metric_weight) != 0.0:
        score += float(spec.base_metric_weight) * extract_objective_value(result, objective=spec)

    if float(spec.stability_weight) != 0.0:
        assert spec.stability_metric_path is not None  # normalized above
        stability_component = _stability_score(
            result,
            fold_summary_path=spec.fold_summary_path,
            metric_path=spec.stability_metric_path,
            std_penalty=float(spec.stability_std_penalty),
        )
        score += float(spec.stability_weight) * stability_component

    for constraint in spec.constraints:
        try:
            raw_value = get_nested_value(result, constraint.metric_path)
            constraint_value = float(raw_value)
            if not math.isfinite(constraint_value):
                raise ValueError("non-finite constraint value")
        except Exception:
            if constraint.missing_penalty is None:
                raise
            penalty = float(constraint.missing_penalty)
            score = score - penalty if spec.direction == "maximize" else score + penalty
            continue

        if _constraint_is_violated(
            constraint_value,
            op=constraint.op,
            threshold=float(constraint.threshold),
        ):
            penalty = float(constraint.penalty)
            score = score - penalty if spec.direction == "maximize" else score + penalty

    if not math.isfinite(score):
        raise ValueError("Composite objective resolved to a non-finite score.")
    return float(score)


def set_nested_value(config: dict[str, Any], path: str | Sequence[str | int], value: Any) -> None:
    """
    Update an existing nested config field without silently creating new branches.
    """
    tokens = normalize_config_path(path)
    current: Any = config
    for token in tokens[:-1]:
        if isinstance(current, list):
            if not isinstance(token, int):
                raise TypeError(f"List traversal requires integer tokens, got {token!r}.")
            current = current[token]
        elif isinstance(current, dict):
            if token not in current:
                raise KeyError(f"Config path token {token!r} not found while traversing {tokens!r}.")
            current = current[token]
        else:
            raise TypeError(f"Cannot traverse into {type(current).__name__} with token {token!r}.")

    final_token = tokens[-1]
    if isinstance(current, list):
        if not isinstance(final_token, int):
            raise TypeError(f"List assignment requires an integer token, got {final_token!r}.")
        current[final_token] = value
        return
    if isinstance(current, dict):
        if final_token not in current:
            raise KeyError(f"Config path token {final_token!r} not found while assigning {tokens!r}.")
        current[final_token] = value
        return
    raise TypeError(f"Cannot assign into {type(current).__name__} with token {final_token!r}.")


def sample_trial_parameters(
    trial: Any,
    search_space: Sequence[SearchDimension | Mapping[str, Any]],
) -> dict[str, Any]:
    """
    Sample one full parameter set from Optuna for the provided search space.
    """
    params: dict[str, Any] = {}
    for dimension in normalize_search_space(search_space):
        if dimension.kind == "int":
            kwargs: dict[str, Any] = {"low": int(dimension.low), "high": int(dimension.high), "log": bool(dimension.log)}
            if dimension.step is not None:
                kwargs["step"] = int(dimension.step)
            params[dimension.name] = trial.suggest_int(dimension.name, **kwargs)
        elif dimension.kind == "float":
            kwargs = {"low": float(dimension.low), "high": float(dimension.high), "log": bool(dimension.log)}
            if dimension.step is not None:
                kwargs["step"] = float(dimension.step)
            params[dimension.name] = trial.suggest_float(dimension.name, **kwargs)
        elif dimension.kind == "categorical":
            params[dimension.name] = trial.suggest_categorical(dimension.name, list(dimension.choices or []))
        else:
            params[dimension.name] = trial.suggest_categorical(dimension.name, [False, True])
    return params


def prepare_trial_config(
    base_config: Mapping[str, Any],
    *,
    trial_params: Mapping[str, Any],
    search_space: Sequence[SearchDimension | Mapping[str, Any]],
    logging_enabled: bool = False,
) -> dict[str, Any]:
    """
    Materialize one trial-specific config by applying sampled values onto the validated base config.
    """
    cfg = deepcopy(dict(base_config))
    dimensions = normalize_search_space(search_space)
    by_name = {dimension.name: dimension for dimension in dimensions}
    for name, value in dict(trial_params).items():
        if name not in by_name:
            raise KeyError(f"Trial parameter {name!r} does not exist in the configured search space.")
        set_nested_value(cfg, by_name[name].path, value)

    logging_cfg = dict(cfg.get("logging", {}) or {})
    stage_tails = dict(logging_cfg.get("stage_tails", {}) or {})
    stage_tails["enabled"] = False
    stage_tails["stdout"] = False
    stage_tails["report"] = False
    logging_cfg["enabled"] = bool(logging_enabled)
    logging_cfg["stage_tails"] = stage_tails
    cfg["logging"] = logging_cfg
    return cfg


def extract_objective_value(
    result: Any,
    objective: ObjectiveSpec | Mapping[str, Any] | None = None,
) -> float:
    """
    Extract one finite numeric objective from an ExperimentResult-like payload.
    """
    spec = normalize_objective_spec(objective)
    value = get_nested_value(result, spec.metric_path)
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"Objective metric {spec.metric_path!r} resolved to a non-finite value: {value!r}")
    return numeric_value


def _write_trial_config_file(cfg: Mapping[str, Any], *, config_path: str | Path) -> Path:
    tmp_dir = (PROJECT_ROOT / "tmp" / "optuna_trials").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(config_path).stem or "experiment"
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".yaml",
        prefix=f"{stem}_",
        dir=tmp_dir,
        delete=False,
        encoding="utf-8",
    ) as handle:
        yaml.safe_dump(dict(cfg), handle, sort_keys=False)
        return Path(handle.name)


def _run_experiment_from_config(cfg: Mapping[str, Any], *, config_path: str | Path) -> Any:
    from src.experiments.runner import run_experiment

    temp_config_path = _write_trial_config_file(cfg, config_path=config_path)
    try:
        return run_experiment(temp_config_path)
    finally:
        temp_config_path.unlink(missing_ok=True)


def build_study_objective(
    config_path: str | Path,
    *,
    search_space: Sequence[SearchDimension | Mapping[str, Any]],
    objective: ObjectiveSpec | Mapping[str, Any] | None = None,
    pruning: PruningSpec | Mapping[str, Any] | None = None,
    logging_enabled: bool = False,
    catch_exceptions: bool = True,
) -> Any:
    """
    Build an Optuna objective function bound to one validated base experiment config.
    """
    base_config = load_experiment_config(config_path)
    normalized_space = normalize_search_space(search_space)
    objective_spec = normalize_objective_spec(objective)
    pruning_spec = normalize_pruning_spec(pruning)
    failure_score = (
        float(objective_spec.failure_score)
        if objective_spec.failure_score is not None
        else _default_failure_score(objective_spec.direction)
    )
    optuna = _require_optuna() if pruning_spec.enabled else None

    def objective_fn(trial: Any) -> float:
        trial_params = sample_trial_parameters(trial, normalized_space)
        trial.set_user_attr("trial_params", dict(trial_params))
        trial.set_user_attr("objective_metric", objective_spec.metric_path)
        trial.set_user_attr("objective_direction", objective_spec.direction)
        report_state = {"step": 0, "reports": []}
        stage_filter = set(pruning_spec.stage_filter)

        def _fold_reporter(stage: str, fold: int, payload: Mapping[str, Any]) -> None:
            if not pruning_spec.enabled:
                return
            if stage_filter and str(stage) not in stage_filter:
                return
            try:
                raw_value = get_nested_value(payload, pruning_spec.metric_path)
                value = float(raw_value)
            except Exception:
                return
            if not math.isfinite(value):
                return

            step = int(report_state["step"])
            report_state["step"] = step + 1
            report_entry = {
                "stage": str(stage),
                "fold": int(fold),
                "step": step,
                "metric_path": pruning_spec.metric_path,
                "value": value,
            }
            report_state["reports"].append(report_entry)
            trial.report(value, step)
            if trial.should_prune():
                raise optuna.TrialPruned(
                    f"Pruned on stage={stage}, fold={fold}, metric={pruning_spec.metric_path}, value={value}."
                )

        trial_config = prepare_trial_config(
            base_config,
            trial_params=trial_params,
            search_space=normalized_space,
            logging_enabled=logging_enabled,
        )
        try:
            with optuna_fold_reporting_context(_fold_reporter if pruning_spec.enabled else None):
                result = _run_experiment_from_config(trial_config, config_path=config_path)
            score = score_experiment_result(result, objective=objective_spec)
        except Exception as exc:
            if pruning_spec.enabled and optuna is not None and isinstance(exc, optuna.TrialPruned):
                trial.set_user_attr("pruning_reports", list(report_state["reports"]))
                raise
            trial.set_user_attr("trial_failed", True)
            trial.set_user_attr("exception", f"{type(exc).__name__}: {exc}")
            if not catch_exceptions:
                raise
            return failure_score

        trial.set_user_attr("trial_failed", False)
        trial.set_user_attr(
            "primary_summary",
            dict(getattr(result, "evaluation", {}).get("primary_summary", {}) or {}),
        )
        trial.set_user_attr(
            "fold_backtest_summaries",
            list(getattr(result, "evaluation", {}).get("fold_backtest_summaries", []) or []),
        )
        trial.set_user_attr(
            "derived_metrics",
            compute_derived_metrics(result),
        )
        if report_state["reports"]:
            trial.set_user_attr("pruning_reports", list(report_state["reports"]))
        return score

    return objective_fn


def _build_sampler(
    *,
    sampler: str,
    seed: int | None,
) -> Any:
    optuna = _require_optuna()
    normalized = str(sampler).strip().lower()
    if normalized == "tpe":
        return optuna.samplers.TPESampler(seed=seed)
    if normalized == "random":
        return optuna.samplers.RandomSampler(seed=seed)
    raise ValueError("sampler must be one of: tpe, random")


def _build_pruner(pruning: PruningSpec | Mapping[str, Any] | None) -> Any:
    optuna = _require_optuna()
    spec = normalize_pruning_spec(pruning)
    if not spec.enabled or spec.pruner == "none":
        return optuna.pruners.NopPruner()
    if spec.pruner == "median":
        return optuna.pruners.MedianPruner(
            n_startup_trials=int(spec.n_startup_trials),
            n_warmup_steps=int(spec.n_warmup_steps),
            interval_steps=int(spec.interval_steps),
        )
    if spec.pruner == "percentile":
        return optuna.pruners.PercentilePruner(
            50.0,
            n_startup_trials=int(spec.n_startup_trials),
            n_warmup_steps=int(spec.n_warmup_steps),
            interval_steps=int(spec.interval_steps),
        )
    raise ValueError("pruning.pruner must be one of: median, percentile, none")


def optimize_experiment(
    config_path: str | Path,
    *,
    search_space: Sequence[SearchDimension | Mapping[str, Any]],
    objective: ObjectiveSpec | Mapping[str, Any] | None = None,
    pruning: PruningSpec | Mapping[str, Any] | None = None,
    study_name: str | None = None,
    storage: str | None = None,
    load_if_exists: bool = False,
    sampler: str = _DEFAULT_SAMPLER,
    seed: int | None = 7,
    n_trials: int = 50,
    timeout: float | None = None,
    n_jobs: int = 1,
    logging_enabled: bool = False,
    catch_exceptions: bool = True,
) -> Any:
    """
    Run an Optuna study against the existing experiment runner with a config-path based search space.
    """
    if int(n_trials) <= 0:
        raise ValueError("n_trials must be a positive integer.")
    if int(n_jobs) <= 0:
        raise ValueError("n_jobs must be a positive integer.")

    optuna = _require_optuna()
    objective_spec = normalize_objective_spec(objective)
    pruning_spec = normalize_pruning_spec(pruning)
    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        load_if_exists=bool(load_if_exists),
        direction=objective_spec.direction,
        sampler=_build_sampler(sampler=sampler, seed=seed),
        pruner=_build_pruner(pruning_spec),
    )
    study.set_user_attr("config_path", str(Path(config_path)))
    study.set_user_attr("objective_metric", objective_spec.metric_path)
    study.set_user_attr("sampler", str(sampler))
    if pruning_spec.enabled:
        study.set_user_attr("pruning_metric", pruning_spec.metric_path)
        study.set_user_attr("pruning_direction", pruning_spec.direction)
        study.set_user_attr("pruner", pruning_spec.pruner)
    study.optimize(
        build_study_objective(
            config_path,
            search_space=search_space,
            objective=objective_spec,
            pruning=pruning_spec,
            logging_enabled=logging_enabled,
            catch_exceptions=catch_exceptions,
        ),
        n_trials=int(n_trials),
        timeout=timeout,
        n_jobs=int(n_jobs),
    )
    return study


def load_search_space_yaml(path: str | Path) -> list[SearchDimension]:
    """
    Load a YAML search-space file containing either a top-level list or `search_space: [...]`.
    """
    resolved_path = Path(path).resolve()
    with resolved_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    if isinstance(payload, list):
        raw_dimensions = payload
    elif isinstance(payload, dict):
        raw_dimensions = payload.get("search_space")
    else:
        raise ValueError("Search-space YAML must be either a list or a mapping with 'search_space'.")

    if raw_dimensions is None:
        raise ValueError("Search-space YAML must define a non-empty 'search_space'.")
    return normalize_search_space(raw_dimensions)


__all__ = [
    "ConstraintPenalty",
    "ObjectiveSpec",
    "PruningSpec",
    "SearchDimension",
    "build_study_objective",
    "compute_derived_metrics",
    "extract_objective_value",
    "get_nested_value",
    "load_search_space_yaml",
    "normalize_config_path",
    "normalize_objective_spec",
    "normalize_pruning_spec",
    "normalize_search_space",
    "optimize_experiment",
    "prepare_trial_config",
    "sample_trial_parameters",
    "score_experiment_result",
    "set_nested_value",
]
