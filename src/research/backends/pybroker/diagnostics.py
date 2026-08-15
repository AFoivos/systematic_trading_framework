"""OOS predictive and one-bar trading diagnostics for the PyBroker adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.metrics import (
    annualized_return,
    annualized_volatility,
    equity_curve_from_returns,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
)
from src.evaluation.model_metrics import binary_classification_metrics
from src.research.run import SelectionDirection
from src.signals.registry import get_signal_fn

from .contracts import (
    PyBrokerCostMapping,
    PyBrokerInputError,
    PyBrokerSignalPolicy,
)


def _finite_or_none(value: object) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PyBrokerInputError("Screening metrics must be numeric or null.")
    return value if isfinite(float(value)) else None


def sanitize_metrics(
    metrics: Mapping[str, object],
) -> dict[str, int | float | None]:
    """Convert backend diagnostics to the portable DiscoveryTrial metric domain."""

    return {str(name): _finite_or_none(value) for name, value in metrics.items()}


def predictive_metrics(
    *,
    target: pd.Series,
    probability: pd.Series,
) -> dict[str, int | float | None]:
    """Compute classification diagnostics only where OOS target/prediction align."""

    raw = binary_classification_metrics(target, probability)
    return sanitize_metrics(raw)


def framework_long_flat_signal(
    *,
    probability: pd.Series,
    oos_mask: pd.Series,
    policy: PyBrokerSignalPolicy,
    threshold: float,
) -> pd.Series:
    """Use the canonical signal registry instead of a PyBroker indicator universe."""

    frame = pd.DataFrame(
        {
            "pred_prob": probability.astype(float),
            "pred_is_oos": oos_mask.astype(bool),
            "primary_side": 1.0,
        },
        index=probability.index,
    )
    signal_fn = get_signal_fn(policy.signal_family)
    signal = signal_fn(
        frame,
        prob_col="pred_prob",
        side_col="primary_side",
        pred_is_oos_col="pred_is_oos",
        threshold=threshold,
        mode="long_only",
    )
    values = pd.to_numeric(signal, errors="coerce").fillna(0.0).astype(float)
    if not values.isin((0.0, 1.0)).all():
        raise PyBrokerInputError(
            "Framework probability signal must remain long/flat in Phase 3B."
        )
    values.loc[~oos_mask.astype(bool)] = 0.0
    return values


def fold_trading_diagnostics(
    *,
    open_prices: pd.Series,
    signal: pd.Series,
    cost_mapping: PyBrokerCostMapping,
    periods_per_year: int,
) -> tuple[dict[str, int | float | None], pd.DataFrame]:
    """Evaluate close[t] intent over open[t+1] -> open[t+2] within one fold.

    The first test row cannot execute because its signal becomes available only
    at that row's close.  The last test row cannot establish a complete
    open-to-open return interval.  No price or signal is borrowed across fold
    boundaries.
    """

    if len(open_prices) != len(signal) or not open_prices.index.equals(signal.index):
        raise PyBrokerInputError("Fold price/signal alignment is not exact.")
    if periods_per_year < 1:
        raise PyBrokerInputError("periods_per_year must be positive.")

    rows = len(open_prices)
    ledger = pd.DataFrame(
        {
            "position": pd.Series(0.0, index=open_prices.index),
            "gross_return": pd.Series(np.nan, index=open_prices.index),
            "turnover": pd.Series(0.0, index=open_prices.index),
            "net_return": pd.Series(np.nan, index=open_prices.index),
        }
    )
    if rows < 3:
        return (
            sanitize_metrics(
                {
                    "total_return": 0.0,
                    "net_return": 0.0,
                    "gross_total_return": 0.0,
                    "total_cost": 0.0,
                    "annualized_return": 0.0,
                    "volatility": 0.0,
                    "sharpe": 0.0,
                    "net_sharpe": 0.0,
                    "max_drawdown": 0.0,
                    "bar_profit_factor": 0.0,
                    "profit_factor": 0.0,
                    "trade_count": 0,
                    "turnover": 0.0,
                    "execution_return_rows": 0,
                    "dropped_signals_without_in_fold_execution": int(
                        signal.ne(0.0).sum()
                    ),
                }
            ),
            ledger,
        )

    execution_index = open_prices.index[1:-1]
    positions = pd.Series(
        signal.iloc[:-2].to_numpy(dtype=float),
        index=execution_index,
        dtype=float,
    )
    forward_open_return = (
        open_prices.shift(-1).div(open_prices).sub(1.0).loc[execution_index]
    ).astype(float)
    if not np.isfinite(forward_open_return.to_numpy(dtype=float)).all():
        raise PyBrokerInputError(
            "Next-open screening returns contain non-finite values."
        )
    turnover = positions.diff().abs()
    if len(turnover):
        turnover.iloc[0] = abs(float(positions.iloc[0]))
        turnover.iloc[-1] += abs(float(positions.iloc[-1]))
    gross = positions * forward_open_return
    net = (
        gross
        - turnover * cost_mapping.cost_per_turnover
        - positions.abs() * cost_mapping.holding_cost_per_exposed_bar
    )
    if bool((net <= -1.0).any()):
        raise PyBrokerInputError(
            "Configured costs produce a return <= -100%; cost mapping is invalid."
        )
    ledger.loc[execution_index, "position"] = positions
    ledger.loc[execution_index, "gross_return"] = gross
    ledger.loc[execution_index, "turnover"] = turnover
    ledger.loc[execution_index, "net_return"] = net

    previous = positions.shift(1, fill_value=0.0)
    trade_count = int(((positions > 0.0) & (previous <= 0.0)).sum())
    gross_total = float((1.0 + gross).prod() - 1.0) if len(gross) else 0.0
    net_total = float((1.0 + net).prod() - 1.0) if len(net) else 0.0
    factor = profit_factor(net)
    metrics = sanitize_metrics(
        {
            "total_return": net_total,
            "net_return": net_total,
            "gross_total_return": gross_total,
            "total_cost": gross_total - net_total,
            "annualized_return": annualized_return(
                net, periods_per_year=periods_per_year
            ),
            "volatility": annualized_volatility(
                net, periods_per_year=periods_per_year
            ),
            "sharpe": sharpe_ratio(net, periods_per_year=periods_per_year),
            "net_sharpe": sharpe_ratio(
                net, periods_per_year=periods_per_year
            ),
            "max_drawdown": max_drawdown(equity_curve_from_returns(net)),
            "bar_profit_factor": factor,
            "profit_factor": factor,
            "trade_count": trade_count,
            "turnover": float(turnover.sum()),
            "execution_return_rows": int(len(net)),
            "dropped_signals_without_in_fold_execution": int(
                signal.iloc[-2:].ne(0.0).sum()
            ),
        }
    )
    return metrics, ledger


def aggregate_trading_diagnostics(
    *,
    fold_ledgers: Sequence[pd.DataFrame],
    periods_per_year: int,
) -> dict[str, int | float | None]:
    """Aggregate disjoint fold return ledgers without inventing missing rows."""

    non_empty: list[pd.DataFrame] = []
    for fold_order, frame in enumerate(fold_ledgers):
        if frame.empty:
            continue
        observed = frame.loc[frame["net_return"].notna()].copy()
        if observed.empty:
            continue
        observed["_fold_order"] = int(fold_order)
        non_empty.append(observed)
    if non_empty:
        ledger = pd.concat(non_empty).sort_index()
    else:
        ledger = pd.DataFrame(
            columns=(
                "position",
                "gross_return",
                "turnover",
                "net_return",
                "_fold_order",
            )
        )
    if ledger.index.has_duplicates:
        raise PyBrokerInputError(
            "Overlapping test folds produced duplicate trading-return timestamps."
        )
    net = pd.to_numeric(ledger.get("net_return"), errors="coerce").dropna()
    gross = pd.to_numeric(ledger.get("gross_return"), errors="coerce").dropna()
    turnover = pd.to_numeric(ledger.get("turnover"), errors="coerce").fillna(0.0)
    positions = pd.to_numeric(ledger.get("position"), errors="coerce").fillna(0.0)
    if net.empty:
        return sanitize_metrics(
            {
                "total_return": 0.0,
                "net_return": 0.0,
                "gross_total_return": 0.0,
                "total_cost": 0.0,
                "annualized_return": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "net_sharpe": 0.0,
                "max_drawdown": 0.0,
                "bar_profit_factor": 0.0,
                "profit_factor": 0.0,
                "trade_count": 0,
                "turnover": 0.0,
                "execution_return_rows": 0,
            }
        )
    previous = positions.groupby(ledger["_fold_order"]).shift(
        1, fill_value=0.0
    )
    gross_total = float((1.0 + gross).prod() - 1.0)
    net_total = float((1.0 + net).prod() - 1.0)
    factor = profit_factor(net)
    return sanitize_metrics(
        {
            "total_return": net_total,
            "net_return": net_total,
            "gross_total_return": gross_total,
            "total_cost": gross_total - net_total,
            "annualized_return": annualized_return(
                net, periods_per_year=periods_per_year
            ),
            "volatility": annualized_volatility(
                net, periods_per_year=periods_per_year
            ),
            "sharpe": sharpe_ratio(net, periods_per_year=periods_per_year),
            "net_sharpe": sharpe_ratio(
                net, periods_per_year=periods_per_year
            ),
            "max_drawdown": max_drawdown(equity_curve_from_returns(net)),
            "bar_profit_factor": factor,
            "profit_factor": factor,
            "trade_count": int(((positions > 0.0) & (previous <= 0.0)).sum()),
            "turnover": float(turnover.sum()),
            "execution_return_rows": int(len(net)),
        }
    )


def fold_stability_diagnostics(
    fold_metrics: Sequence[Mapping[str, int | float | None]],
    *,
    metric_name: str,
    direction: SelectionDirection,
) -> dict[str, int | float | str | None]:
    """Describe fold concentration without imposing an implicit pass threshold."""

    values = [
        float(item[metric_name])
        for item in fold_metrics
        if item.get(metric_name) is not None
        and isfinite(float(item[metric_name]))
    ]
    positive_fold_count = sum(
        float(item.get("total_return") or 0.0) > 0.0 for item in fold_metrics
    )
    if not values:
        return {
            "metric": metric_name,
            "direction": direction.value,
            "folds_with_metric": 0,
            "mean_fold_metric": None,
            "median_fold_metric": None,
            "worst_fold_metric": None,
            "positive_fold_count": int(positive_fold_count),
            "fold_dispersion": None,
        }
    worst = min(values) if direction is SelectionDirection.MAXIMIZE else max(values)
    return {
        "metric": metric_name,
        "direction": direction.value,
        "folds_with_metric": len(values),
        "mean_fold_metric": float(np.mean(values)),
        "median_fold_metric": float(np.median(values)),
        "worst_fold_metric": float(worst),
        "positive_fold_count": int(positive_fold_count),
        "fold_dispersion": float(np.std(values, ddof=0)),
    }


__all__ = [
    "aggregate_trading_diagnostics",
    "fold_stability_diagnostics",
    "fold_trading_diagnostics",
    "framework_long_flat_signal",
    "predictive_metrics",
    "sanitize_metrics",
]
