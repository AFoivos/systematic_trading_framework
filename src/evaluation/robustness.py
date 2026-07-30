from __future__ import annotations

from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics


def _metric_subset(summary: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "cumulative_return",
        "annualized_return",
        "annualized_vol",
        "sharpe",
        "sortino",
        "calmar",
        "max_drawdown",
        "profit_factor",
        "hit_rate",
        "bar_return_profit_factor",
        "conventional_sharpe",
        "return_over_vol_sharpe",
        "profit_factor_scope",
        "metric_scope",
        "annualization_mode",
        "sharpe_legacy_alias",
        "gross_pnl",
        "net_pnl",
        "total_cost",
        "cost_drag",
        "cost_to_gross_pnl",
        "gross_return_sum",
        "net_return_sum",
        "cost_return_sum",
        "avg_turnover",
        "total_turnover",
    )
    out: dict[str, Any] = {}
    for key in keys:
        value = summary.get(key)
        if isinstance(value, str):
            out[key] = value
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isnan(numeric):
            out[key] = numeric
    return out


def summarize_returns(
    returns: pd.Series,
    *,
    periods_per_year: int,
    turnover: pd.Series | None = None,
    costs: pd.Series | None = None,
    gross_returns: pd.Series | None = None,
) -> dict[str, Any]:
    summary = compute_backtest_metrics(
        net_returns=returns.astype(float).fillna(0.0),
        periods_per_year=int(periods_per_year),
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )
    return _metric_subset(summary)


def cost_multiplier_stress(
    *,
    gross_returns: pd.Series,
    costs: pd.Series,
    periods_per_year: int,
    multipliers: Iterable[float],
    turnover: pd.Series | None = None,
    evaluation_mask: pd.Series | None = None,
    evaluation_metadata: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    gross = gross_returns.astype(float).fillna(0.0)
    base_costs = costs.reindex(gross.index).fillna(0.0).astype(float)
    base_turnover = turnover.reindex(gross.index).fillna(0.0).astype(float) if turnover is not None else None
    if evaluation_mask is not None:
        mask = evaluation_mask.reindex(gross.index).fillna(False).astype(bool)
        gross = gross.loc[mask]
        base_costs = base_costs.loc[mask]
        if base_turnover is not None:
            base_turnover = base_turnover.loc[mask]
    scope = dict(evaluation_metadata or {})
    out: dict[str, dict[str, Any]] = {}
    for multiplier in multipliers:
        mult = float(multiplier)
        if mult < 0.0:
            raise ValueError("cost stress multipliers must be >= 0.")
        stressed = gross - base_costs * mult
        metrics = summarize_returns(
            stressed,
            periods_per_year=periods_per_year,
            turnover=base_turnover,
            costs=base_costs * mult,
            gross_returns=gross,
        )
        metrics.update(scope)
        out[f"cost_x{mult:g}"] = metrics
    return out


def calendar_walk_forward_diagnostics(
    returns: pd.Series,
    *,
    periods_per_year: int,
    frequency: str = "YE",
    oos_mask: pd.Series | None = None,
    active_eligible_mask: pd.Series | None = None,
) -> dict[str, Any]:
    series = returns.dropna().astype(float)
    if series.empty:
        return {
            "total_calendar_periods": 0,
            "active_oos_periods": 0,
            "positive_active_periods": 0,
            "positive_active_period_ratio": 0.0,
            "calendar_periods": [],
        }
    if not isinstance(series.index, pd.DatetimeIndex):
        return {
            "total_calendar_periods": 0,
            "active_oos_periods": 0,
            "positive_active_periods": 0,
            "positive_active_period_ratio": 0.0,
            "calendar_periods": [],
            "error": "returns index is not a DatetimeIndex",
        }

    scoped = (
        oos_mask.reindex(series.index).fillna(False).astype(bool)
        if oos_mask is not None
        else pd.Series(True, index=series.index, dtype=bool)
    )
    active = (
        active_eligible_mask.reindex(series.index).fillna(False).astype(bool) & scoped
        if active_eligible_mask is not None
        else scoped.copy()
    )
    period_rows: list[dict[str, Any]] = []
    for period_end, calendar_returns in series.groupby(pd.Grouper(freq=str(frequency))):
        calendar_returns = calendar_returns.dropna()
        if calendar_returns.empty:
            continue
        period_scope = scoped.reindex(calendar_returns.index).fillna(False).astype(bool)
        period_active = active.reindex(calendar_returns.index).fillna(False).astype(bool)
        evaluation_returns = calendar_returns.loc[period_scope]
        is_active = bool(period_active.any()) and not evaluation_returns.empty
        row: dict[str, Any] = {
            "period": str(period_end),
            "calendar_start": calendar_returns.index.min().isoformat(),
            "calendar_end": calendar_returns.index.max().isoformat(),
            "calendar_rows": int(len(calendar_returns)),
            "oos_rows": int(period_scope.sum()),
            "active_eligible_rows": int(period_active.sum()),
            "is_active_oos_period": is_active,
        }
        if is_active:
            row.update(summarize_returns(evaluation_returns, periods_per_year=periods_per_year))
            row["evaluation_start"] = evaluation_returns.index.min().isoformat()
            row["evaluation_end"] = evaluation_returns.index.max().isoformat()
            row["evaluation_rows"] = int(len(evaluation_returns))
        else:
            row["inactive_reason"] = (
                "no_oos_predictions" if int(period_scope.sum()) == 0 else "no_active_eligible_rows"
            )
        period_rows.append(row)

    if not period_rows:
        return {
            "total_calendar_periods": 0,
            "active_oos_periods": 0,
            "positive_active_periods": 0,
            "positive_active_period_ratio": 0.0,
            "calendar_periods": [],
        }

    active_rows = [row for row in period_rows if bool(row.get("is_active_oos_period", False))]
    cumulative = np.array([float(row.get("cumulative_return", 0.0)) for row in active_rows], dtype=float)
    sharpe = np.array([float(row.get("sharpe", 0.0)) for row in active_rows], dtype=float)
    max_dd = np.array([float(row.get("max_drawdown", 0.0)) for row in active_rows], dtype=float)
    positive_count = int((cumulative > 0.0).sum())
    summary: dict[str, Any] = {
        "aggregation_kind": "calendar_periods",
        "total_calendar_periods": int(len(period_rows)),
        "active_oos_periods": int(len(active_rows)),
        "positive_active_periods": positive_count,
        "positive_active_period_ratio": float(positive_count / max(len(active_rows), 1)),
        "calendar_periods": period_rows,
    }
    if active_rows:
        summary.update({
            "min_active_period_cumulative_return": float(np.nanmin(cumulative)),
            "median_active_period_cumulative_return": float(np.nanmedian(cumulative)),
            "mean_active_period_cumulative_return": float(np.nanmean(cumulative)),
            "mean_active_period_sharpe": float(np.nanmean(sharpe)),
            "std_active_period_sharpe": float(np.nanstd(sharpe)),
            "worst_active_period_max_drawdown": float(np.nanmin(max_dd)),
        })
    return summary


def gap_penalty_stress(
    *,
    returns: pd.Series,
    positions: pd.Series | pd.DataFrame,
    periods_per_year: int,
    gap_loss_per_exposure: float,
    max_gap_multiple: float = 3.0,
    evaluation_mask: pd.Series | None = None,
    evaluation_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    series = returns.astype(float).fillna(0.0)
    if series.empty or not isinstance(series.index, pd.DatetimeIndex):
        return {"enabled": False, "reason": "requires non-empty DatetimeIndex returns"}
    if float(gap_loss_per_exposure) <= 0.0:
        return {"enabled": False, "reason": "gap_loss_per_exposure <= 0"}

    diffs = series.index.to_series().diff().dropna()
    if diffs.empty:
        return {"enabled": False, "reason": "insufficient timestamps"}
    expected = diffs.median()
    threshold = expected * float(max_gap_multiple)
    gap_mask = series.index.to_series().diff().gt(threshold).reindex(series.index).fillna(False)
    if isinstance(positions, pd.DataFrame):
        exposure = positions.abs().sum(axis=1)
    else:
        exposure = positions.abs()
    prior_exposure = exposure.reindex(series.index).shift(1).fillna(0.0).astype(float)
    penalties = pd.Series(0.0, index=series.index, dtype=float)
    penalties.loc[gap_mask] = prior_exposure.loc[gap_mask] * float(gap_loss_per_exposure)
    stressed = series - penalties
    if evaluation_mask is not None:
        selected = evaluation_mask.reindex(stressed.index).fillna(False).astype(bool)
        stressed = stressed.loc[selected]
    metrics = summarize_returns(stressed, periods_per_year=periods_per_year)
    metrics.update(dict(evaluation_metadata or {}))
    return {
        "enabled": True,
        "gap_count": int(gap_mask.sum()),
        "penalized_gap_count": int(penalties.gt(0.0).sum()),
        "total_gap_penalty": float(penalties.sum()),
        "gap_loss_per_exposure": float(gap_loss_per_exposure),
        "max_gap_multiple": float(max_gap_multiple),
        "expected_bar_seconds": float(expected.total_seconds()),
        "threshold_seconds": float(threshold.total_seconds()),
        "metrics": metrics,
    }


__all__ = [
    "calendar_walk_forward_diagnostics",
    "cost_multiplier_stress",
    "gap_penalty_stress",
    "summarize_returns",
]
