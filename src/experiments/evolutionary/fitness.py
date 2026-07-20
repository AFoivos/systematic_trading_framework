from __future__ import annotations

"""Reusable weighted fitness, robustness extraction, and hard constraints."""

from dataclasses import dataclass
import math
from statistics import median, pstdev
from typing import Any, Mapping, Sequence

import pandas as pd

from src.experiments.evolutionary.schemas import EvolutionarySpec, FitnessSpec
from src.experiments.optuna_search import compute_derived_metrics, get_nested_value


class MissingMetricError(ValueError):
    """Raised when a required metric is absent or non-finite."""


@dataclass(frozen=True)
class FitnessResult:
    score: float
    rejected: bool
    reason: str | None
    components: dict[str, float]
    resolved_metrics: dict[str, Any]


@dataclass(frozen=True)
class PromotionResult:
    passed: bool
    failures: tuple[str, ...]
    metrics: dict[str, Any]


def _result_evaluation(result: Any) -> dict[str, Any]:
    evaluation = getattr(result, "evaluation", {}) or {}
    return dict(evaluation) if isinstance(evaluation, Mapping) else {}


def _fold_rows(result: Any) -> list[dict[str, Any]]:
    evaluation = _result_evaluation(result)
    raw = evaluation.get("fold_backtest_summaries", []) or []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [dict(row) for row in raw if isinstance(row, Mapping)]


def _fold_metric(row: Mapping[str, Any], key: str) -> float | None:
    metrics = row.get("metrics", {}) or {}
    if not isinstance(metrics, Mapping):
        return None
    raw = metrics.get(key)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _fold_derived_metrics(result: Any) -> dict[str, float]:
    rows = _fold_rows(result)
    if not rows:
        return {}
    returns: list[float] = []
    sharpes: list[float] = []
    active = 0
    for row in rows:
        fold_return = _fold_metric(row, "cumulative_return")
        if fold_return is None:
            fold_return = _fold_metric(row, "net_pnl")
        fold_sharpe = _fold_metric(row, "sharpe")
        turnover = _fold_metric(row, "total_turnover")
        if fold_return is not None:
            returns.append(fold_return)
        if fold_sharpe is not None:
            sharpes.append(fold_sharpe)
        if any(
            value is not None and abs(value) > 1.0e-12
            for value in (fold_return, turnover)
        ):
            active += 1
    out: dict[str, float] = {"active_fold_count": float(active)}
    if returns:
        out.update(
            {
                "fold_positive_ratio": float(sum(value > 0.0 for value in returns) / len(returns)),
                "worst_fold_cumulative_return": float(min(returns)),
            }
        )
    if sharpes:
        out.update(
            {
                "fold_median_sharpe": float(median(sharpes)),
                "fold_sharpe_std": float(pstdev(sharpes)) if len(sharpes) > 1 else 0.0,
            }
        )
    return out


def _walk_forward_derived_metrics(result: Any) -> dict[str, float]:
    evaluation = _result_evaluation(result)
    robustness = evaluation.get("robustness", {}) or {}
    if not isinstance(robustness, Mapping):
        return {}
    walk_forward = robustness.get("walk_forward", {}) or {}
    if not isinstance(walk_forward, Mapping):
        return {}
    rows = walk_forward.get("folds", []) or []
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return {}
    sharpes: list[float] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        try:
            value = float(row.get("sharpe"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            sharpes.append(value)
    if not sharpes:
        return {}
    return {"walk_forward_median_sharpe": float(median(sharpes))}


def _trade_frame(result: Any) -> pd.DataFrame | None:
    backtest = getattr(result, "backtest", None)
    trades = getattr(backtest, "trades", None)
    return trades if isinstance(trades, pd.DataFrame) and not trades.empty else None


def _trade_concentration_metrics(result: Any) -> dict[str, float]:
    trades = _trade_frame(result)
    if trades is None or "asset" not in trades.columns:
        return {}
    pnl_col = next(
        (column for column in ("net_return", "realized_r", "net_pnl") if column in trades.columns),
        None,
    )
    if pnl_col is None:
        return {}
    pnl = pd.to_numeric(trades[pnl_col], errors="coerce")
    usable = trades.loc[pnl.notna(), ["asset"]].copy()
    usable["pnl"] = pnl.loc[pnl.notna()].astype(float)
    if usable.empty:
        return {}
    by_asset = usable.groupby(usable["asset"].astype(str), sort=True)["pnl"].sum()
    absolute_asset = by_asset.abs()
    total_absolute = float(absolute_asset.sum())
    if not math.isfinite(total_absolute) or total_absolute <= 0.0:
        return {}
    asset_shares = absolute_asset / total_absolute
    out = {
        "maximum_asset_pnl_share": float(asset_shares.max()),
        "asset_pnl_hhi": float((asset_shares**2).sum()),
    }
    config = getattr(result, "config", {}) or {}
    if not isinstance(config, Mapping):
        return out
    portfolio = config.get("portfolio", {}) or {}
    groups = dict(portfolio.get("asset_groups", {}) or {}) if isinstance(portfolio, Mapping) else {}
    if not groups or any(asset not in groups for asset in by_asset.index):
        return out
    by_group = absolute_asset.groupby(
        absolute_asset.index.map(lambda asset: str(groups[asset]))
    ).sum()
    total_group_absolute = float(by_group.sum())
    if total_group_absolute > 0.0 and math.isfinite(total_group_absolute):
        group_shares = by_group / total_group_absolute
        out["maximum_group_pnl_share"] = float(group_shares.max())
        out["group_pnl_hhi"] = float((group_shares**2).sum())
    return out


def _matb_candidate_count(result: Any) -> float | None:
    data = getattr(result, "data", None)
    frames = data.values() if isinstance(data, Mapping) else [data]
    total = 0
    observed = False
    for frame in frames:
        if not isinstance(frame, pd.DataFrame) or "matb_candidate" not in frame.columns:
            continue
        observed = True
        total += int(pd.to_numeric(frame["matb_candidate"], errors="coerce").fillna(0.0).eq(1.0).sum())
    return float(total) if observed else None


def _completed_trades_per_year(result: Any) -> float | None:
    trades = _trade_frame(result)
    if trades is None:
        return None
    timestamps: pd.Series | None = None
    backtest = getattr(result, "backtest", None)
    returns = getattr(backtest, "net_returns", None)
    if returns is None:
        returns = getattr(backtest, "returns", None)
    if isinstance(getattr(returns, "index", None), pd.DatetimeIndex):
        timestamps = pd.Series(returns.index)
    for column in ("entry_timestamp", "signal_timestamp", "exit_timestamp"):
        if timestamps is not None:
            break
        if column in trades.columns:
            candidate = pd.to_datetime(trades[column], errors="coerce", utc=True).dropna()
            if not candidate.empty:
                timestamps = candidate
                break
    if timestamps is None or len(timestamps) < 2:
        return None
    span_days = (timestamps.max() - timestamps.min()).total_seconds() / 86400.0
    if span_days <= 0.0:
        return None
    return float(len(trades) / (span_days / 365.25))


def _try_numeric(result: Any, path: str) -> float | None:
    try:
        value = float(get_nested_value(result, path))
    except Exception:
        return None
    return value if math.isfinite(value) else None


def compute_evolutionary_derived_metrics(
    result: Any,
    *,
    context: Mapping[str, Any],
) -> dict[str, float]:
    """Derive only auditable metrics from an ExperimentResult and decoded context."""
    derived = dict(compute_derived_metrics(result))
    derived.update(_fold_derived_metrics(result))
    derived.update(_walk_forward_derived_metrics(result))
    concentration = _trade_concentration_metrics(result)
    derived.update(concentration)
    candidate_count = _matb_candidate_count(result)
    if candidate_count is not None:
        derived["matb_candidate_count"] = candidate_count
    trades_per_year = _completed_trades_per_year(result)
    if trades_per_year is not None:
        derived["completed_trades_per_year"] = trades_per_year

    primary_return = _try_numeric(result, "evaluation.primary_summary.mtm_cumulative_return")
    if primary_return is None:
        primary_return = _try_numeric(result, "evaluation.primary_summary.cumulative_return")
    cost_x2 = _try_numeric(result, "evaluation.robustness.cost_stress.cost_x2.cumulative_return")
    delay_1 = _try_numeric(result, "evaluation.robustness.entry_delay.delay_1_bars.cumulative_return")
    if primary_return is not None and cost_x2 is not None:
        derived["cost_sensitivity"] = abs(primary_return - cost_x2)
    if primary_return is not None and delay_1 is not None:
        derived["delay_sensitivity"] = abs(primary_return - delay_1)
        if primary_return > 0.0:
            derived["delay_1_retention_ratio"] = float(delay_1 / primary_return)

    required_context = (
        "asset_count",
        "baseline_asset_count",
        "group_count",
        "baseline_group_count",
        "maximum_group_asset_share",
    )
    if all(key in context for key in required_context) and all(
        key in derived for key in ("maximum_asset_pnl_share", "maximum_group_pnl_share")
    ):
        asset_fraction = float(context["asset_count"]) / max(float(context["baseline_asset_count"]), 1.0)
        group_deficit = 1.0 - float(context["group_count"]) / max(
            float(context["baseline_group_count"]), 1.0
        )
        robustness_penalty = 0.0
        if "cost_sensitivity" in derived:
            robustness_penalty += min(abs(derived["cost_sensitivity"]), 1.0)
        if "delay_sensitivity" in derived:
            robustness_penalty += min(abs(derived["delay_sensitivity"]), 1.0)
        robustness_penalty /= 2.0
        derived["matb_complexity"] = float(
            0.15 * asset_fraction
            + 0.20 * group_deficit
            + 0.15 * float(context["maximum_group_asset_share"])
            + 0.20 * derived["maximum_asset_pnl_share"]
            + 0.20 * derived["maximum_group_pnl_share"]
            + 0.10 * robustness_penalty
        )
    return derived


def resolve_metric(result: Any, path: str, *, context: Mapping[str, Any]) -> Any:
    """Resolve result, derived, or decoder-context metrics without fallback values."""
    if path == "genome":
        return dict(context)
    if path.startswith("genome."):
        return get_nested_value(context, path[len("genome.") :])
    if path == "derived":
        return compute_evolutionary_derived_metrics(result, context=context)
    if path.startswith("derived."):
        derived = compute_evolutionary_derived_metrics(result, context=context)
        return get_nested_value(derived, path[len("derived.") :])
    return get_nested_value(result, path)


def _comparison_passes(value: Any, *, operator: str, threshold: Any) -> bool:
    if operator == "finite":
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False
    if operator == "eq":
        return value == threshold
    if operator == "ne":
        return value != threshold
    if operator == "in":
        return value in threshold
    try:
        numeric = float(value)
        numeric_threshold = float(threshold)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(numeric) or not math.isfinite(numeric_threshold):
        return False
    if operator == "lt":
        return numeric < numeric_threshold
    if operator == "le":
        return numeric <= numeric_threshold
    if operator == "gt":
        return numeric > numeric_threshold
    if operator == "ge":
        return numeric >= numeric_threshold
    return False


def _validate_evaluation_policy(result: Any, fitness: FitnessSpec) -> None:
    evaluation = _result_evaluation(result)
    scope = evaluation.get("scope")
    if scope not in fitness.evaluation_policy.allowed_scopes:
        raise MissingMetricError(
            f"Evaluation scope {scope!r} is not allowed; expected one of "
            f"{list(fitness.evaluation_policy.allowed_scopes)!r}."
        )
    if fitness.evaluation_policy.require_walk_forward:
        fold_count = 0
        robustness = evaluation.get("robustness", {}) or {}
        if isinstance(robustness, Mapping):
            walk_forward = robustness.get("walk_forward", {}) or {}
            if isinstance(walk_forward, Mapping):
                try:
                    fold_count = int(walk_forward.get("fold_count", 0) or 0)
                except (TypeError, ValueError):
                    fold_count = 0
        if fold_count <= 0:
            fold_count = len(_fold_rows(result))
        if fold_count <= 0:
            raise MissingMetricError("Fitness requires walk-forward folds, but none were available.")


def failed_fitness(spec: EvolutionarySpec, reason: str) -> FitnessResult:
    return FitnessResult(
        score=float(spec.fitness.failure_score),
        rejected=True,
        reason=str(reason),
        components={},
        resolved_metrics={},
    )


def score_candidate(
    result: Any,
    spec: EvolutionarySpec,
    *,
    context: Mapping[str, Any],
) -> FitnessResult:
    """Score a candidate; missing metrics and hard-gate failures reject fail-closed."""
    resolved: dict[str, Any] = {}
    components: dict[str, float] = {}
    try:
        _validate_evaluation_policy(result, spec.fitness)
        for constraint in spec.fitness.hard_constraints:
            try:
                value = resolve_metric(result, constraint.metric_path, context=context)
            except Exception as exc:
                raise MissingMetricError(
                    f"Hard constraint {constraint.name!r} is missing metric "
                    f"{constraint.metric_path!r}."
                ) from exc
            resolved[constraint.metric_path] = value
            if not _comparison_passes(
                value,
                operator=constraint.operator,
                threshold=constraint.threshold,
            ):
                return failed_fitness(
                    spec,
                    f"Hard constraint {constraint.name!r} failed: "
                    f"{constraint.metric_path}={value!r} {constraint.operator} "
                    f"{constraint.threshold!r}.",
                )

        score = 0.0
        for component in spec.fitness.components:
            try:
                raw_value = resolve_metric(result, component.metric_path, context=context)
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError("metric is non-finite")
            except Exception as exc:
                if component.missing_policy == "penalize":
                    assert component.missing_penalty is not None
                    contribution = float(component.missing_penalty)
                    components[component.name] = contribution
                    score += contribution
                    continue
                raise MissingMetricError(
                    f"Fitness component {component.name!r} is missing finite metric "
                    f"{component.metric_path!r}."
                ) from exc
            resolved[component.metric_path] = value
            transformed = value
            if component.transform == "abs":
                transformed = abs(value)
            elif component.transform == "negative_abs":
                transformed = -abs(value)
            contribution = float(component.weight) * transformed
            components[component.name] = contribution
            score += contribution
        if not math.isfinite(score):
            raise MissingMetricError("Weighted fitness resolved to a non-finite score.")
        return FitnessResult(
            score=float(score),
            rejected=False,
            reason=None,
            components=components,
            resolved_metrics=resolved,
        )
    except Exception as exc:
        return failed_fitness(spec, f"{type(exc).__name__}: {exc}")


def evaluate_promotion(
    result: Any,
    spec: EvolutionarySpec,
    *,
    context: Mapping[str, Any],
) -> PromotionResult:
    """Evaluate strict post-search gates without changing fitness or rejection state."""
    if not spec.promotion.enabled:
        return PromotionResult(passed=False, failures=(), metrics={})

    failures: list[str] = []
    metrics: dict[str, Any] = {}
    for gate in spec.promotion.gates:
        try:
            value = resolve_metric(result, gate.metric_path, context=context)
        except Exception:
            failures.append(
                f"{gate.name}: missing metric {gate.metric_path!r} "
                f"(missing_policy={gate.missing_policy})"
            )
            continue
        metrics[gate.metric_path] = value
        if not _comparison_passes(
            value,
            operator=gate.operator,
            threshold=gate.threshold,
        ):
            failures.append(
                f"{gate.name}: {gate.metric_path}={value!r} "
                f"{gate.operator} {gate.threshold!r}"
            )
    return PromotionResult(
        passed=not failures,
        failures=tuple(failures),
        metrics=metrics,
    )


__all__ = [
    "FitnessResult",
    "MissingMetricError",
    "PromotionResult",
    "compute_evolutionary_derived_metrics",
    "evaluate_promotion",
    "failed_fitness",
    "resolve_metric",
    "score_candidate",
]
