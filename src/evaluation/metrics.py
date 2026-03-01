from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd


def equity_curve_from_returns(returns: pd.Series) -> pd.Series:
    """
    Handle equity curve from returns inside the evaluation layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    rets = returns.astype(float).fillna(0.0)
    equity = (1.0 + rets).cumprod()
    equity.name = "equity"
    return equity


def max_drawdown(equity: pd.Series) -> float:
    """
    Handle max drawdown inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if equity.empty:
        return 0.0
    dd = equity / equity.cummax() - 1.0
    return float(dd.min())


def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Handle annualized return inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    rets = returns.dropna().astype(float)
    if rets.empty:
        return 0.0
    cumulative = float((1.0 + rets).prod())
    if cumulative <= 0:
        return -1.0
    return float(cumulative ** (periods_per_year / len(rets)) - 1.0)


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Handle annualized volatility inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    rets = returns.dropna().astype(float)
    if len(rets) < 2:
        return 0.0
    return float(rets.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Handle sharpe ratio inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    ann_ret = annualized_return(returns, periods_per_year=periods_per_year)
    ann_vol = annualized_volatility(returns, periods_per_year=periods_per_year)
    return float(ann_ret / ann_vol) if ann_vol > 0 else 0.0


def downside_volatility(
    returns: pd.Series,
    periods_per_year: int = 252,
    minimum_acceptable_return: float = 0.0,
) -> float:
    """
    Handle downside volatility inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    rets = returns.dropna().astype(float)
    if rets.empty:
        return 0.0
    downside = np.minimum(rets - minimum_acceptable_return, 0.0)
    if downside.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(downside**2)) * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: pd.Series,
    periods_per_year: int = 252,
    minimum_acceptable_return: float = 0.0,
) -> float:
    """
    Handle sortino ratio inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    ann_ret = annualized_return(returns, periods_per_year=periods_per_year)
    down_vol = downside_volatility(
        returns,
        periods_per_year=periods_per_year,
        minimum_acceptable_return=minimum_acceptable_return,
    )
    return float(ann_ret / down_vol) if down_vol > 0 else 0.0


def calmar_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Handle calmar ratio inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    ann_ret = annualized_return(returns, periods_per_year=periods_per_year)
    mdd = max_drawdown(equity_curve_from_returns(returns))
    return float(ann_ret / abs(mdd)) if mdd < 0 else 0.0


def profit_factor(returns: pd.Series) -> float:
    """
    Handle profit factor inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    rets = returns.dropna().astype(float)
    if rets.empty:
        return 0.0
    gross_profit = float(rets[rets > 0].sum())
    gross_loss = float((-rets[rets < 0]).sum())
    if gross_loss <= 0:
        return 0.0
    return float(gross_profit / gross_loss)


def hit_rate(returns: pd.Series) -> float:
    """
    Handle hit rate inside the evaluation layer. The helper isolates one focused responsibility
    so the surrounding code remains modular, readable, and easier to test.
    """
    rets = returns.dropna().astype(float)
    if rets.empty:
        return 0.0
    active = rets[rets != 0.0]
    if active.empty:
        return 0.0
    return float((active > 0.0).mean())


def turnover_stats(turnover: pd.Series | None) -> dict[str, float]:
    """
    Handle turnover stats inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if turnover is None:
        return {"avg_turnover": 0.0, "total_turnover": 0.0}
    t = turnover.dropna().astype(float)
    if t.empty:
        return {"avg_turnover": 0.0, "total_turnover": 0.0}
    return {
        "avg_turnover": float(t.mean()),
        "total_turnover": float(t.sum()),
    }


def cost_attribution(
    *,
    net_returns: pd.Series,
    gross_returns: pd.Series | None,
    costs: pd.Series | None,
) -> dict[str, float]:
    """
    Handle cost attribution inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    net = net_returns.dropna().astype(float)
    gross = gross_returns.dropna().astype(float) if gross_returns is not None else None
    c = costs.dropna().astype(float) if costs is not None else None

    gross_pnl = float(gross.sum()) if gross is not None and not gross.empty else float(net.sum())
    net_pnl = float(net.sum()) if not net.empty else 0.0
    total_cost = float(c.sum()) if c is not None and not c.empty else 0.0
    cost_drag = gross_pnl - net_pnl

    if abs(gross_pnl) > 1e-12:
        cost_to_gross_pnl = float(total_cost / abs(gross_pnl))
    else:
        cost_to_gross_pnl = 0.0

    return {
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "total_cost": total_cost,
        "cost_drag": float(cost_drag),
        "cost_to_gross_pnl": cost_to_gross_pnl,
    }


def compute_backtest_metrics(
    *,
    net_returns: pd.Series,
    periods_per_year: int = 252,
    turnover: pd.Series | None = None,
    costs: pd.Series | None = None,
    gross_returns: pd.Series | None = None,
) -> dict[str, float]:
    """
    Compute backtest metrics for the evaluation layer. The helper keeps the calculation isolated
    so the calling pipeline can reuse the same logic consistently across experiments.
    """
    rets = net_returns.dropna().astype(float)
    if rets.empty:
        base = {
            "cumulative_return": 0.0,
            "annualized_return": 0.0,
            "annualized_vol": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "calmar": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "hit_rate": 0.0,
        }
        base.update(turnover_stats(turnover))
        base.update(
            cost_attribution(
                net_returns=net_returns,
                gross_returns=gross_returns,
                costs=costs,
            )
        )
        return base

    equity = equity_curve_from_returns(rets)

    metrics: dict[str, float] = {
        "cumulative_return": float(equity.iloc[-1] - 1.0),
        "annualized_return": annualized_return(rets, periods_per_year=periods_per_year),
        "annualized_vol": annualized_volatility(rets, periods_per_year=periods_per_year),
        "sharpe": sharpe_ratio(rets, periods_per_year=periods_per_year),
        "sortino": sortino_ratio(rets, periods_per_year=periods_per_year),
        "calmar": calmar_ratio(rets, periods_per_year=periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "profit_factor": profit_factor(rets),
        "hit_rate": hit_rate(rets),
    }
    metrics.update(turnover_stats(turnover))
    metrics.update(
        cost_attribution(
            net_returns=rets,
            gross_returns=gross_returns,
            costs=costs,
        )
    )
    return metrics


def merge_metric_overrides(
    base_metrics: Mapping[str, float],
    overrides: Mapping[str, float] | None,
) -> dict[str, float]:
    """
    Merge metric overrides into one consolidated structure for the evaluation layer. The helper
    keeps reporting logic explicit and prevents ad hoc dictionary assembly across callers.
    """
    out = dict(base_metrics)
    if overrides:
        out.update({str(k): float(v) for k, v in overrides.items()})
    return out


__all__ = [
    "equity_curve_from_returns",
    "max_drawdown",
    "annualized_return",
    "annualized_volatility",
    "sharpe_ratio",
    "downside_volatility",
    "sortino_ratio",
    "calmar_ratio",
    "profit_factor",
    "hit_rate",
    "turnover_stats",
    "cost_attribution",
    "compute_backtest_metrics",
    "merge_metric_overrides",
]

