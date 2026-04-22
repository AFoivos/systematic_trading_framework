from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import tempfile
from typing import Any, Literal, Mapping, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from src.experiments.optuna_runtime import optuna_fold_reporting_context
from src.utils.config import load_experiment_config
from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path
from src.utils.run_metadata import build_artifact_manifest

ParameterKind = Literal["int", "float", "categorical", "bool"]
ObjectiveDirection = Literal["maximize", "minimize"]
ConstraintOperator = Literal["lt", "le", "gt", "ge"]

_DEFAULT_OBJECTIVE_PATH = "evaluation.primary_summary.sharpe"
_DEFAULT_SAMPLER = "tpe"
_RUN_DIR_TZ = ZoneInfo("Europe/Athens")


def _run_dir_timestamp(now: datetime | None = None) -> str:
    timestamp = now if now is not None else datetime.now(_RUN_DIR_TZ)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=_RUN_DIR_TZ)
    else:
        timestamp = timestamp.astimezone(_RUN_DIR_TZ)
    return timestamp.strftime("%Y%m%d_%H%M%S_%f")


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


_POSITION_EPS = 1.0e-12
_WEEKLY_PARTICIPATION_FREQ = "W-FRI"


def _strict_oos_mask(result: Any, index: Any) -> Any:
    evaluation = getattr(result, "evaluation", {}) or {}
    if not isinstance(evaluation, Mapping) or evaluation.get("scope") != "strict_oos_only":
        return None

    data = getattr(result, "data", None)
    if isinstance(data, Mapping):
        masks = [
            frame["pred_is_oos"].astype(bool)
            for frame in data.values()
            if hasattr(frame, "columns") and "pred_is_oos" in frame.columns
        ]
        if masks:
            return (
                pd.concat(masks, axis=1, join="inner")
                .reindex(index)
                .fillna(False)
                .astype(bool)
                .all(axis=1)
            )
    elif hasattr(data, "columns") and "pred_is_oos" in data.columns:
        return data["pred_is_oos"].reindex(index).fillna(False).astype(bool)
    return None


def _apply_strict_oos_filter(result: Any, values: Any) -> Any:
    oos_mask = _strict_oos_mask(result, values.index)
    if oos_mask is None:
        return values
    return values.loc[oos_mask]


def _count_true_values(values: Any) -> float:
    total = values.sum()
    if hasattr(total, "sum"):
        total = total.sum()
    return float(total)


def _count_true_bars(values: Any) -> float:
    if getattr(values, "ndim", 1) == 2:
        values = values.any(axis=1)
    return float(values.sum())


def _position_path(result: Any) -> Any:
    backtest = getattr(result, "backtest", None)
    positions = getattr(backtest, "positions", None)
    if positions is not None:
        return positions.astype(float)
    portfolio_weights = getattr(result, "portfolio_weights", None)
    if portfolio_weights is not None:
        return portfolio_weights.astype(float)
    return None


def _compute_turnover_event_count(result: Any) -> float:
    backtest = getattr(result, "backtest", None)
    turnover = getattr(backtest, "turnover", None)
    if turnover is None:
        return 0.0

    series = _apply_strict_oos_filter(result, turnover.astype(float))
    return _count_true_bars(series.abs() > _POSITION_EPS)


def _compute_exposure_bar_count(result: Any) -> float:
    positions = _position_path(result)
    if positions is None:
        return 0.0
    positions = _apply_strict_oos_filter(result, positions)
    return _count_true_bars(positions.abs() > _POSITION_EPS)


def _entry_exit_events(result: Any) -> tuple[Any | None, Any | None]:
    positions = _position_path(result)
    if positions is None:
        return None, None
    previous_positions = positions.shift(1).fillna(0.0)
    current_exposed = positions.abs() > _POSITION_EPS
    previous_exposed = previous_positions.abs() > _POSITION_EPS
    sign_changed = (
        current_exposed
        & previous_exposed
        & positions.gt(0.0).ne(previous_positions.gt(0.0))
    )
    entries = current_exposed & (~previous_exposed | sign_changed)
    exits = previous_exposed & (~current_exposed | sign_changed)
    entries = _apply_strict_oos_filter(result, entries)
    exits = _apply_strict_oos_filter(result, exits)
    return entries, exits


def _entry_exit_counts(result: Any) -> tuple[float, float]:
    entries, exits = _entry_exit_events(result)
    if entries is None or exits is None:
        return 0.0, 0.0
    return _count_true_values(entries), _count_true_values(exits)


def _weekly_entry_participation_metrics(result: Any) -> dict[str, float]:
    entries, _ = _entry_exit_events(result)
    if entries is None or not isinstance(entries.index, pd.DatetimeIndex) or entries.empty:
        return {
            "total_week_count": 0.0,
            "active_week_count": 0.0,
            "inactive_week_count": 0.0,
            "active_week_ratio": 0.0,
            "min_entries_per_week": 0.0,
            "median_entries_per_week": 0.0,
            "mean_entries_per_week": 0.0,
        }

    entries = entries.sort_index()
    if getattr(entries, "ndim", 1) == 2:
        entry_counts_by_bar = entries.astype(int).sum(axis=1)
    else:
        entry_counts_by_bar = entries.astype(int)

    weekly_counts = entry_counts_by_bar.resample(_WEEKLY_PARTICIPATION_FREQ).sum().fillna(0.0)
    total_week_count = float(len(weekly_counts))
    if total_week_count <= 0.0:
        active_week_count = 0.0
    else:
        active_week_count = float((weekly_counts > 0.0).sum())
    inactive_week_count = max(total_week_count - active_week_count, 0.0)
    active_week_ratio = active_week_count / total_week_count if total_week_count > 0.0 else 0.0
    return {
        "total_week_count": total_week_count,
        "active_week_count": active_week_count,
        "inactive_week_count": inactive_week_count,
        "active_week_ratio": float(active_week_ratio),
        "min_entries_per_week": float(weekly_counts.min()) if total_week_count > 0.0 else 0.0,
        "median_entries_per_week": float(weekly_counts.median()) if total_week_count > 0.0 else 0.0,
        "mean_entries_per_week": float(weekly_counts.mean()) if total_week_count > 0.0 else 0.0,
    }


def _fold_activity_counts(result: Any) -> tuple[float, float, float]:
    evaluation = getattr(result, "evaluation", {}) or {}
    if not isinstance(evaluation, Mapping):
        return 0.0, 0.0, 0.0
    fold_summaries = evaluation.get("fold_backtest_summaries", []) or []
    if not isinstance(fold_summaries, Sequence) or isinstance(fold_summaries, (str, bytes)):
        return 0.0, 0.0, 0.0

    active_count = 0
    profitable_count = 0
    losing_count = 0
    for fold_summary in fold_summaries:
        if not isinstance(fold_summary, Mapping):
            continue
        metrics = fold_summary.get("metrics", {}) or {}
        if not isinstance(metrics, Mapping):
            continue
        numeric_metrics: dict[str, float] = {}
        for key in ("total_turnover", "net_pnl", "gross_pnl"):
            try:
                value = float(metrics.get(key, 0.0) or 0.0)
            except Exception:
                value = 0.0
            numeric_metrics[key] = value
        if any(abs(value) > _POSITION_EPS for value in numeric_metrics.values()):
            active_count += 1
        net_pnl = numeric_metrics["net_pnl"]
        if net_pnl > _POSITION_EPS:
            profitable_count += 1
        elif net_pnl < -_POSITION_EPS:
            losing_count += 1
    return float(active_count), float(profitable_count), float(losing_count)


def compute_derived_metrics(result: Any) -> dict[str, float]:
    """
    Compute convenience metrics that are not part of the current canonical evaluation payload.
    """
    entry_count, exit_count = _entry_exit_counts(result)
    turnover_event_count = _compute_turnover_event_count(result)
    active_fold_count, profitable_fold_count, losing_fold_count = _fold_activity_counts(result)
    metrics = {
        "turnover_event_count": turnover_event_count,
        # Backward-compatible alias. Historically this meant "bars with non-zero turnover",
        # not completed trade round trips; prefer `turnover_event_count` in new YAML configs.
        "trade_count": turnover_event_count,
        "entry_count": entry_count,
        "exit_count": exit_count,
        "round_trip_count": min(entry_count, exit_count),
        "exposure_bar_count": _compute_exposure_bar_count(result),
        "active_fold_count": active_fold_count,
        "profitable_fold_count": profitable_fold_count,
        "losing_fold_count": losing_fold_count,
    }
    metrics.update(_weekly_entry_participation_metrics(result))
    return metrics


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
    trial_number: int | str | None = None,
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
    if logging_enabled and trial_number is not None:
        trial_token = (
            f"trial_{trial_number:04d}"
            if isinstance(trial_number, int)
            else f"trial_{str(trial_number).strip()}"
        )
        base_run_name = str(logging_cfg.get("run_name") or "optuna_trial").strip() or "optuna_trial"
        logging_cfg["run_name"] = f"{base_run_name}_{trial_token}"
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
            trial_number=getattr(trial, "number", None),
        )
        if logging_enabled:
            trial.set_user_attr("experiment_run_name", trial_config.get("logging", {}).get("run_name"))
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
        result_artifacts = dict(getattr(result, "artifacts", {}) or {})
        if result_artifacts.get("run_dir"):
            trial.set_user_attr("experiment_run_dir", result_artifacts["run_dir"])
        if result_artifacts.get("report"):
            trial.set_user_attr("experiment_report", result_artifacts["report"])
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


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def _trial_state_name(trial: Any) -> str:
    state = getattr(trial, "state", None)
    return str(getattr(state, "name", state))


def _trial_duration_seconds(trial: Any) -> float | None:
    started = getattr(trial, "datetime_start", None)
    completed = getattr(trial, "datetime_complete", None)
    if started is None or completed is None:
        return None
    try:
        return float((completed - started).total_seconds())
    except Exception:
        return None


def _flat_trial_row(trial: Any) -> dict[str, Any]:
    user_attrs = dict(getattr(trial, "user_attrs", {}) or {})
    primary_summary = dict(user_attrs.get("primary_summary", {}) or {})
    derived_metrics = dict(user_attrs.get("derived_metrics", {}) or {})

    row: dict[str, Any] = {
        "number": getattr(trial, "number", None),
        "state": _trial_state_name(trial),
        "value": getattr(trial, "value", None),
        "datetime_start": _jsonable(getattr(trial, "datetime_start", None)),
        "datetime_complete": _jsonable(getattr(trial, "datetime_complete", None)),
        "duration_seconds": _trial_duration_seconds(trial),
        "trial_failed": user_attrs.get("trial_failed"),
        "exception": user_attrs.get("exception"),
        "experiment_run_name": user_attrs.get("experiment_run_name"),
        "experiment_run_dir": user_attrs.get("experiment_run_dir"),
        "experiment_report": user_attrs.get("experiment_report"),
    }
    for key, value in sorted(derived_metrics.items()):
        row[f"derived_{key}"] = value
    for key in (
        "sharpe",
        "sortino",
        "calmar",
        "annualized_return",
        "annualized_vol",
        "cumulative_return",
        "net_pnl",
        "gross_pnl",
        "total_cost",
        "profit_factor",
        "hit_rate",
        "total_turnover",
        "max_drawdown",
        "cost_to_gross_pnl",
    ):
        if key in primary_summary:
            row[f"summary_{key}"] = primary_summary[key]
    for key, value in sorted(dict(getattr(trial, "params", {}) or {}).items()):
        row[f"param_{key}"] = value
    return row


def _trial_sort_key(trial: Any, *, direction: ObjectiveDirection) -> tuple[int, float, int]:
    state_name = _trial_state_name(trial)
    value = getattr(trial, "value", None)
    is_complete = 0 if state_name == "COMPLETE" and value is not None else 1
    numeric_value = float(value) if value is not None else math.nan
    if not math.isfinite(numeric_value):
        numeric_value = -math.inf if direction == "maximize" else math.inf
    ranked_value = -numeric_value if direction == "maximize" else numeric_value
    return (is_complete, ranked_value, int(getattr(trial, "number", 0) or 0))


def _resolve_optuna_report_dir(output_dir: str | Path, *, run_name: str) -> Path:
    base_dir = Path(output_dir)
    if not base_dir.is_absolute():
        base_dir = PROJECT_ROOT / base_dir
    base_dir = enforce_safe_absolute_path(base_dir.resolve())
    timestamp = _run_dir_timestamp()
    safe_run_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in run_name).strip("_")
    if not safe_run_name:
        safe_run_name = "optuna_study"
    return base_dir / f"{safe_run_name}_{timestamp}_{uuid4().hex[:8]}"


def _study_best_trial_payload(study: Any, *, direction: ObjectiveDirection) -> dict[str, Any]:
    trials = list(getattr(study, "trials", []) or [])
    complete_trials = [
        trial
        for trial in trials
        if _trial_state_name(trial) == "COMPLETE" and getattr(trial, "value", None) is not None
    ]
    if not complete_trials:
        return {}
    try:
        best_trial = getattr(study, "best_trial")
    except Exception:
        best_trial = sorted(complete_trials, key=lambda trial: _trial_sort_key(trial, direction=direction))[0]
    user_attrs = dict(getattr(best_trial, "user_attrs", {}) or {})
    return {
        "number": getattr(best_trial, "number", None),
        "value": getattr(best_trial, "value", None),
        "state": _trial_state_name(best_trial),
        "params": dict(getattr(best_trial, "params", {}) or {}),
        "primary_summary": dict(user_attrs.get("primary_summary", {}) or {}),
        "derived_metrics": dict(user_attrs.get("derived_metrics", {}) or {}),
        "experiment_run_name": user_attrs.get("experiment_run_name"),
        "experiment_run_dir": user_attrs.get("experiment_run_dir"),
        "experiment_report": user_attrs.get("experiment_report"),
        "trial_failed": user_attrs.get("trial_failed"),
        "exception": user_attrs.get("exception"),
    }


def build_study_report_payload(
    study: Any,
    *,
    config_path: str | Path,
    search_space: Sequence[SearchDimension | Mapping[str, Any]],
    objective: ObjectiveSpec | Mapping[str, Any] | None = None,
    pruning: PruningSpec | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a compact, JSON-serializable Optuna study summary for logs.
    """
    objective_spec = normalize_objective_spec(objective)
    pruning_spec = normalize_pruning_spec(pruning)
    normalized_space = normalize_search_space(search_space)
    trials = list(getattr(study, "trials", []) or [])
    state_counts: dict[str, int] = {}
    for trial in trials:
        state_name = _trial_state_name(trial)
        state_counts[state_name] = state_counts.get(state_name, 0) + 1

    clean_complete_trials = [
        trial
        for trial in trials
        if _trial_state_name(trial) == "COMPLETE"
        and getattr(trial, "value", None) is not None
        and not bool(dict(getattr(trial, "user_attrs", {}) or {}).get("trial_failed"))
    ]
    top_trials = sorted(clean_complete_trials, key=lambda trial: _trial_sort_key(trial, direction=objective_spec.direction))[:10]

    return _jsonable(
        {
            "study_name": getattr(study, "study_name", None),
            "config_path": str(Path(config_path)),
            "objective": objective_spec,
            "pruning": pruning_spec,
            "search_space": [dimension for dimension in normalized_space],
            "state_counts": state_counts,
            "trial_count": len(trials),
            "clean_complete_count": len(clean_complete_trials),
            "best_trial": _study_best_trial_payload(study, direction=objective_spec.direction),
            "top_trials": [
                {
                    "number": getattr(trial, "number", None),
                    "value": getattr(trial, "value", None),
                    "params": dict(getattr(trial, "params", {}) or {}),
                    "primary_summary": dict(dict(getattr(trial, "user_attrs", {}) or {}).get("primary_summary", {}) or {}),
                    "derived_metrics": dict(dict(getattr(trial, "user_attrs", {}) or {}).get("derived_metrics", {}) or {}),
                    "experiment_run_name": dict(getattr(trial, "user_attrs", {}) or {}).get("experiment_run_name"),
                    "experiment_run_dir": dict(getattr(trial, "user_attrs", {}) or {}).get("experiment_run_dir"),
                    "experiment_report": dict(getattr(trial, "user_attrs", {}) or {}).get("experiment_report"),
                }
                for trial in top_trials
            ],
        }
    )


def _build_study_report_markdown(payload: Mapping[str, Any]) -> str:
    best_trial = dict(payload.get("best_trial", {}) or {})
    state_counts = dict(payload.get("state_counts", {}) or {})
    lines = [
        "# Optuna Study Report",
        "",
        f"- Study: `{payload.get('study_name') or 'n/a'}`",
        f"- Base config: `{payload.get('config_path')}`",
        f"- Objective: `{dict(payload.get('objective', {}) or {}).get('metric_path')}` "
        f"({dict(payload.get('objective', {}) or {}).get('direction')})",
        f"- Trials: `{payload.get('trial_count')}`",
        f"- Clean complete trials: `{payload.get('clean_complete_count')}`",
        f"- State counts: `{state_counts}`",
        "",
        "## Best Trial",
    ]
    if best_trial:
        summary = dict(best_trial.get("primary_summary", {}) or {})
        derived = dict(best_trial.get("derived_metrics", {}) or {})
        lines.extend(
            [
                f"- Number: `{best_trial.get('number')}`",
                f"- Objective value: `{best_trial.get('value')}`",
                f"- Sharpe: `{summary.get('sharpe', 'n/a')}`",
                f"- Profit factor: `{summary.get('profit_factor', 'n/a')}`",
                f"- Max drawdown: `{summary.get('max_drawdown', 'n/a')}`",
                f"- Total turnover: `{summary.get('total_turnover', 'n/a')}`",
                "- Turnover event count: "
                f"`{derived.get('turnover_event_count', derived.get('trade_count', 'n/a'))}`",
                f"- Entry count: `{derived.get('entry_count', 'n/a')}`",
                f"- Round trip count: `{derived.get('round_trip_count', 'n/a')}`",
                "- Active weeks: "
                f"`{derived.get('active_week_count', 'n/a')}/{derived.get('total_week_count', 'n/a')}`",
                f"- Active week ratio: `{derived.get('active_week_ratio', 'n/a')}`",
                f"- Experiment run name: `{best_trial.get('experiment_run_name', 'n/a')}`",
                f"- Experiment run dir: `{best_trial.get('experiment_run_dir', 'n/a')}`",
                "",
                "### Best Params",
            ]
        )
        for key, value in sorted(dict(best_trial.get("params", {}) or {}).items()):
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("No complete best trial was available.")

    lines.extend(["", "## Top Trials"])
    top_trials = list(payload.get("top_trials", []) or [])
    if not top_trials:
        lines.append("No clean complete trials were available.")
    else:
        lines.append(
            "| trial | objective | sharpe | profit_factor | max_drawdown | "
            "turnover_events | entries | round_trips | total_turnover |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for trial in top_trials:
            summary = dict(trial.get("primary_summary", {}) or {})
            derived = dict(trial.get("derived_metrics", {}) or {})
            lines.append(
                f"| {trial.get('number')} | {trial.get('value')} | {summary.get('sharpe', '')} | "
                f"{summary.get('profit_factor', '')} | {summary.get('max_drawdown', '')} | "
                f"{derived.get('turnover_event_count', derived.get('trade_count', ''))} | "
                f"{derived.get('entry_count', '')} | {derived.get('round_trip_count', '')} | "
                f"{summary.get('total_turnover', '')} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_study_report(
    study: Any,
    *,
    output_dir: str | Path,
    run_name: str | None = None,
    config_path: str | Path,
    search_space: Sequence[SearchDimension | Mapping[str, Any]],
    objective: ObjectiveSpec | Mapping[str, Any] | None = None,
    pruning: PruningSpec | Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """
    Persist one Optuna study report under the experiment logs directory.
    """
    objective_spec = normalize_objective_spec(objective)
    report_run_name = run_name or f"optuna_{getattr(study, 'study_name', None) or Path(config_path).stem}"
    run_dir = _resolve_optuna_report_dir(output_dir, run_name=report_run_name)
    run_dir.mkdir(parents=True, exist_ok=False)

    payload = build_study_report_payload(
        study,
        config_path=config_path,
        search_space=search_space,
        objective=objective_spec,
        pruning=pruning,
    )
    summary_path = run_dir / "study_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)

    trials_path = run_dir / "trials.csv"
    trial_rows = [_jsonable(_flat_trial_row(trial)) for trial in list(getattr(study, "trials", []) or [])]
    fieldnames = sorted({key for row in trial_rows for key in row})
    with trials_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trial_rows)

    report_path = run_dir / "report.md"
    report_path.write_text(_build_study_report_markdown(payload), encoding="utf-8")

    artifacts = {
        "run_dir": str(run_dir),
        "study_summary": str(summary_path),
        "trials": str(trials_path),
        "report": str(report_path),
    }
    manifest = build_artifact_manifest(artifacts)
    manifest_path = run_dir / "artifact_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)
    artifacts["manifest"] = str(manifest_path)
    return artifacts


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
    report_output_dir: str | Path | None = None,
    report_run_name: str | None = None,
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
    if report_output_dir is not None:
        study.set_user_attr(
            "report_artifacts",
            write_study_report(
                study,
                output_dir=report_output_dir,
                run_name=report_run_name,
                config_path=config_path,
                search_space=search_space,
                objective=objective_spec,
                pruning=pruning_spec,
            ),
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


def load_optuna_spec_yaml(path: str | Path) -> dict[str, Any]:
    """
    Load a full Optuna YAML spec containing a base experiment config and search metadata.
    """
    resolved_path = Path(path).resolve()
    with resolved_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, Mapping):
        raise ValueError("Optuna spec YAML must be a mapping.")
    spec = dict(payload)
    base_config = spec.get("base_config")
    if not isinstance(base_config, str) or not base_config.strip():
        raise ValueError("Optuna spec YAML must define a non-empty 'base_config'.")
    study = spec.get("study", {}) or {}
    if not isinstance(study, Mapping):
        raise ValueError("Optuna spec 'study' must be a mapping when provided.")
    report = spec.get("report", {}) or {}
    if not isinstance(report, Mapping):
        raise ValueError("Optuna spec 'report' must be a mapping when provided.")
    spec["study"] = dict(study)
    spec["report"] = dict(report)
    spec["search_space"] = load_search_space_yaml(resolved_path)
    spec["objective"] = normalize_objective_spec(spec.get("objective"))
    spec["pruning"] = normalize_pruning_spec(spec.get("pruning"))
    return spec


def run_optuna_spec(
    spec_path: str | Path,
    *,
    n_trials: int | None = None,
    timeout: float | None = None,
    n_jobs: int | None = None,
    sampler: str | None = None,
    seed: int | None = None,
    study_name: str | None = None,
    storage: str | None = None,
    load_if_exists: bool | None = None,
    logging_enabled: bool | None = None,
    report_output_dir: str | Path | None = None,
    report_run_name: str | None = None,
    no_report: bool = False,
) -> Any:
    """
    Run an Optuna study from a repository Optuna spec YAML.
    """
    spec = load_optuna_spec_yaml(spec_path)
    study_cfg = dict(spec.get("study", {}) or {})
    overrides = {
        "n_trials": n_trials,
        "timeout": timeout,
        "n_jobs": n_jobs,
        "sampler": sampler,
        "seed": seed,
        "study_name": study_name,
        "storage": storage,
        "load_if_exists": load_if_exists,
        "logging_enabled": logging_enabled,
    }
    for key, value in overrides.items():
        if value is not None:
            study_cfg[key] = value

    report_cfg = dict(spec.get("report", {}) or {})
    report_enabled = bool(report_cfg.get("enabled", True)) and not bool(no_report)
    resolved_report_output_dir: str | Path | None = None
    resolved_report_run_name: str | None = None
    if report_enabled:
        resolved_report_output_dir = (
            report_output_dir
            or report_cfg.get("output_dir")
            or load_experiment_config(spec["base_config"])["logging"]["output_dir"]
        )
        resolved_report_run_name = (
            report_run_name
            or report_cfg.get("run_name")
            or f"optuna_{study_cfg.get('study_name') or Path(str(spec['base_config'])).stem}"
        )

    return optimize_experiment(
        spec["base_config"],
        search_space=spec["search_space"],
        objective=spec["objective"],
        pruning=spec["pruning"],
        report_output_dir=resolved_report_output_dir,
        report_run_name=resolved_report_run_name,
        **study_cfg,
    )


def _print_cli_summary(study: Any) -> None:
    print("Optuna study completed")
    print(f"Study: {getattr(study, 'study_name', 'n/a')}")
    try:
        best_trial = getattr(study, "best_trial")
    except Exception:
        best_trial = None
    if best_trial is not None:
        print(f"Best trial: {getattr(best_trial, 'number', 'n/a')}")
        print(f"Best value: {getattr(best_trial, 'value', 'n/a')}")
        print(f"Best params: {dict(getattr(best_trial, 'params', {}) or {})}")
    user_attrs = dict(getattr(study, "user_attrs", {}) or {})
    report_artifacts = dict(user_attrs.get("report_artifacts", {}) or {})
    if report_artifacts.get("report"):
        print(f"Report: {report_artifacts['report']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an Optuna study from a repository Optuna YAML spec.")
    parser.add_argument("spec", help="Path to an Optuna YAML spec.")
    parser.add_argument("--n-trials", type=int, default=None, help="Override study.n_trials.")
    parser.add_argument("--timeout", type=float, default=None, help="Override study.timeout in seconds.")
    parser.add_argument("--n-jobs", type=int, default=None, help="Override study.n_jobs.")
    parser.add_argument("--sampler", choices=("tpe", "random"), default=None, help="Override study.sampler.")
    parser.add_argument("--seed", type=int, default=None, help="Override study.seed.")
    parser.add_argument("--study-name", default=None, help="Override study.study_name.")
    parser.add_argument("--storage", default=None, help="Override study.storage.")
    parser.add_argument("--load-if-exists", action="store_true", default=None, help="Override study.load_if_exists=true.")
    parser.add_argument(
        "--logging-enabled",
        action="store_true",
        default=None,
        help="Enable per-trial experiment logging artifacts.",
    )
    parser.add_argument("--report-output-dir", default=None, help="Directory for the Optuna study report.")
    parser.add_argument("--report-run-name", default=None, help="Run name for the Optuna study report.")
    parser.add_argument("--no-report", action="store_true", help="Do not write the Optuna study report.")
    args = parser.parse_args(argv)

    study = run_optuna_spec(
        args.spec,
        n_trials=args.n_trials,
        timeout=args.timeout,
        n_jobs=args.n_jobs,
        sampler=args.sampler,
        seed=args.seed,
        study_name=args.study_name,
        storage=args.storage,
        load_if_exists=args.load_if_exists,
        logging_enabled=args.logging_enabled,
        report_output_dir=args.report_output_dir,
        report_run_name=args.report_run_name,
        no_report=args.no_report,
    )
    _print_cli_summary(study)
    return 0


__all__ = [
    "ConstraintPenalty",
    "ObjectiveSpec",
    "PruningSpec",
    "SearchDimension",
    "build_study_objective",
    "build_study_report_payload",
    "compute_derived_metrics",
    "extract_objective_value",
    "get_nested_value",
    "load_optuna_spec_yaml",
    "load_search_space_yaml",
    "main",
    "normalize_config_path",
    "normalize_objective_spec",
    "normalize_pruning_spec",
    "normalize_search_space",
    "optimize_experiment",
    "prepare_trial_config",
    "run_optuna_spec",
    "sample_trial_parameters",
    "score_experiment_result",
    "set_nested_value",
    "write_study_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
