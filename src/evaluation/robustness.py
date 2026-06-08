from __future__ import annotations

from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics


def _metric_subset(summary: Mapping[str, Any]) -> dict[str, float]:
    keys = (
        "cumulative_return",
        "annualized_return",
        "annualized_vol",
        "sharpe",
        "max_drawdown",
        "profit_factor",
        "hit_rate",
    )
    out: dict[str, float] = {}
    for key in keys:
        value = summary.get(key)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(numeric):
            out[key] = numeric
    return out


def summarize_returns(
    returns: pd.Series,
    *,
    periods_per_year: int,
    turnover: pd.Series | None = None,
    costs: pd.Series | None = None,
    gross_returns: pd.Series | None = None,
) -> dict[str, float]:
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
) -> dict[str, dict[str, float]]:
    gross = gross_returns.astype(float).fillna(0.0)
    base_costs = costs.reindex(gross.index).fillna(0.0).astype(float)
    out: dict[str, dict[str, float]] = {}
    for multiplier in multipliers:
        mult = float(multiplier)
        if mult < 0.0:
            raise ValueError("cost stress multipliers must be >= 0.")
        stressed = gross - base_costs * mult
        out[f"cost_x{mult:g}"] = summarize_returns(stressed, periods_per_year=periods_per_year)
    return out


def calendar_walk_forward_diagnostics(
    returns: pd.Series,
    *,
    periods_per_year: int,
    frequency: str = "YE",
) -> dict[str, Any]:
    series = returns.dropna().astype(float)
    if series.empty:
        return {
            "fold_count": 0,
            "positive_fold_count": 0,
            "positive_fold_ratio": 0.0,
            "folds": [],
        }
    if not isinstance(series.index, pd.DatetimeIndex):
        return {
            "fold_count": 0,
            "positive_fold_count": 0,
            "positive_fold_ratio": 0.0,
            "folds": [],
            "error": "returns index is not a DatetimeIndex",
        }

    fold_rows: list[dict[str, Any]] = []
    for period_end, fold_returns in series.groupby(pd.Grouper(freq=str(frequency))):
        fold_returns = fold_returns.dropna()
        if fold_returns.empty:
            continue
        metrics = summarize_returns(fold_returns, periods_per_year=periods_per_year)
        fold_rows.append(
            {
                "period": str(period_end),
                "start": fold_returns.index.min().isoformat(),
                "end": fold_returns.index.max().isoformat(),
                "rows": int(len(fold_returns)),
                **metrics,
            }
        )

    if not fold_rows:
        return {
            "fold_count": 0,
            "positive_fold_count": 0,
            "positive_fold_ratio": 0.0,
            "folds": [],
        }

    cumulative = np.array([float(row.get("cumulative_return", 0.0)) for row in fold_rows], dtype=float)
    sharpe = np.array([float(row.get("sharpe", 0.0)) for row in fold_rows], dtype=float)
    max_dd = np.array([float(row.get("max_drawdown", 0.0)) for row in fold_rows], dtype=float)
    positive_count = int((cumulative > 0.0).sum())
    return {
        "fold_count": int(len(fold_rows)),
        "positive_fold_count": positive_count,
        "positive_fold_ratio": float(positive_count / max(len(fold_rows), 1)),
        "min_fold_cumulative_return": float(np.nanmin(cumulative)),
        "median_fold_cumulative_return": float(np.nanmedian(cumulative)),
        "mean_fold_cumulative_return": float(np.nanmean(cumulative)),
        "mean_fold_sharpe": float(np.nanmean(sharpe)),
        "std_fold_sharpe": float(np.nanstd(sharpe)),
        "worst_fold_max_drawdown": float(np.nanmin(max_dd)),
        "folds": fold_rows,
    }


def gap_penalty_stress(
    *,
    returns: pd.Series,
    positions: pd.Series | pd.DataFrame,
    periods_per_year: int,
    gap_loss_per_exposure: float,
    max_gap_multiple: float = 3.0,
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
    return {
        "enabled": True,
        "gap_count": int(gap_mask.sum()),
        "penalized_gap_count": int(penalties.gt(0.0).sum()),
        "total_gap_penalty": float(penalties.sum()),
        "gap_loss_per_exposure": float(gap_loss_per_exposure),
        "max_gap_multiple": float(max_gap_multiple),
        "expected_bar_seconds": float(expected.total_seconds()),
        "threshold_seconds": float(threshold.total_seconds()),
        "metrics": summarize_returns(stressed, periods_per_year=periods_per_year),
    }


__all__ = [
    "calendar_walk_forward_diagnostics",
    "cost_multiplier_stress",
    "gap_penalty_stress",
    "summarize_returns",
]
