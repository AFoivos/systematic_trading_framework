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
    values: list[float] = []
    capital = 1.0
    bankrupt = False
    for value in rets.to_numpy(dtype=float):
        if bankrupt:
            values.append(0.0)
            continue
        factor = 1.0 + float(value)
        if not np.isfinite(factor) or factor <= 0.0:
            capital = 0.0
            bankrupt = True
        else:
            capital *= factor
        values.append(float(capital))
    equity = pd.Series(values, index=rets.index, dtype=float)
    equity.name = "equity"
    return equity


def max_drawdown(equity: pd.Series) -> float:
    """
    Handle max drawdown inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if equity.empty:
        return 0.0
    running_peak = equity.astype(float).cummax().clip(lower=1.0)
    dd = equity.astype(float) / running_peak - 1.0
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
        return float("nan")
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


def sharpe_ratio(
    returns: pd.Series,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> float:
    """
    Handle sharpe ratio inside the evaluation layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    rets = returns.dropna().astype(float)
    if len(rets) < 2:
        return 0.0
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive.")
    if risk_free_rate <= -1.0:
        raise ValueError("risk_free_rate must be greater than -1.")
    period_risk_free = (1.0 + float(risk_free_rate)) ** (1.0 / float(periods_per_year)) - 1.0
    excess = rets - period_risk_free
    volatility = float(excess.std(ddof=1))
    if not np.isfinite(volatility) or volatility <= 0.0:
        return 0.0
    return float(np.sqrt(float(periods_per_year)) * excess.mean() / volatility)


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
    rets = returns.dropna().astype(float)
    if rets.empty:
        return 0.0
    excess_mean = float((rets - float(minimum_acceptable_return)).mean())
    down_vol = downside_volatility(
        rets,
        periods_per_year=periods_per_year,
        minimum_acceptable_return=minimum_acceptable_return,
    )
    annualized_excess = excess_mean * float(periods_per_year)
    return float(annualized_excess / down_vol) if down_vol > 0 else 0.0


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
        return float("inf") if gross_profit > 0.0 else 0.0
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


def _compound_returns(returns: pd.Series) -> float:
    values = returns.dropna().astype(float)
    if values.empty:
        return float("nan")
    return float((1.0 + values).prod() - 1.0)


def calendar_daily_returns(returns: pd.Series) -> tuple[pd.Series, float]:
    """Compound intraday returns to a complete UTC daily grid without inventing prices."""
    rets = returns.dropna().astype(float).sort_index()
    if rets.empty:
        return pd.Series(dtype=float), 0.0
    if not isinstance(rets.index, pd.DatetimeIndex):
        raise ValueError("calendar_daily annualization requires a DatetimeIndex.")
    index = rets.index.tz_localize("UTC") if rets.index.tz is None else rets.index.tz_convert("UTC")
    utc_returns = pd.Series(rets.to_numpy(dtype=float), index=index)
    daily = utc_returns.groupby(utc_returns.index.normalize()).apply(_compound_returns).astype(float)
    grid = pd.date_range(daily.index.min(), daily.index.max(), freq="1D", tz="UTC")
    daily = daily.reindex(grid, fill_value=0.0).astype(float)
    daily.name = "daily_return"
    elapsed_days = max((index.max() - index.min()).total_seconds() / 86_400.0, 1.0)
    return daily, float(elapsed_days)


def _count_breach_episodes(flags: pd.Series) -> int:
    active = flags.fillna(False).astype(bool)
    if active.empty:
        return 0
    return int((active & ~active.shift(1, fill_value=False)).sum())


def compute_ftmo_style_metrics(
    *,
    net_returns: pd.Series,
    weekly_return_target: float | None = None,
    max_daily_loss: float | None = None,
    weekly_drawdown_limit: float | None = None,
    max_total_loss: float | None = None,
    weekly_anchor: str = "W-FRI",
) -> dict[str, float]:
    rets = net_returns.dropna().astype(float)
    if rets.empty or not isinstance(rets.index, pd.DatetimeIndex):
        return {
            "week_count": 0.0,
            "day_count": 0.0,
            "weekly_net_return": 0.0,
            "weekly_return_mean": 0.0,
            "weekly_return_median": 0.0,
            "weekly_return_min": 0.0,
            "weekly_return_std": 0.0,
            "weekly_target_hit_count": 0.0,
            "weekly_target_hit_ratio": 0.0,
            "worst_weekly_drawdown": 0.0,
            "weekly_drawdown_breach_count": 0.0,
            "daily_loss_breach_count": 0.0,
            "max_total_loss_breach_count": 0.0,
            "positive_day_count": 0.0,
            "best_day_concentration": 0.0,
            "positive_day_concentration": 0.0,
        }

    rets = rets.sort_index()
    daily_groups = rets.groupby(pd.Grouper(freq="1D"))
    weekly_groups = rets.groupby(pd.Grouper(freq=str(weekly_anchor)))
    daily_returns = daily_groups.apply(_compound_returns).dropna()
    weekly_returns = weekly_groups.apply(_compound_returns).dropna()

    weekly_drawdowns: dict[pd.Timestamp, float] = {}
    for ts, period_returns in weekly_groups:
        values = period_returns.dropna().astype(float)
        if values.empty:
            continue
        weekly_drawdowns[pd.Timestamp(ts)] = max_drawdown(equity_curve_from_returns(values))
    weekly_drawdown_series = pd.Series(weekly_drawdowns, dtype=float).sort_index()

    daily_intraday_loss: dict[pd.Timestamp, float] = {}
    for ts, period_returns in daily_groups:
        values = period_returns.dropna().astype(float)
        if values.empty:
            continue
        daily_intraday_loss[pd.Timestamp(ts)] = float(equity_curve_from_returns(values).min() - 1.0)
    daily_intraday_loss_series = pd.Series(daily_intraday_loss, dtype=float).sort_index()

    positive_days = daily_returns[daily_returns > 0.0]
    positive_day_pnl = float(positive_days.sum()) if not positive_days.empty else 0.0
    best_day_concentration = (
        float(positive_days.max() / positive_day_pnl)
        if positive_day_pnl > 0.0
        else 0.0
    )
    positive_day_concentration = (
        float(((positive_days / positive_day_pnl) ** 2).sum())
        if positive_day_pnl > 0.0
        else 0.0
    )

    total_loss_flags = pd.Series(False, index=rets.index, dtype=bool)
    if max_total_loss is not None:
        total_loss_flags = equity_curve_from_returns(rets).le(1.0 - float(max_total_loss))

    weekly_target = float(weekly_return_target) if weekly_return_target is not None else None
    weekly_target_hits = (
        int((weekly_returns >= weekly_target).sum())
        if weekly_target is not None and not weekly_returns.empty
        else 0
    )
    weekly_drawdown_breaches = (
        int((weekly_drawdown_series <= -float(weekly_drawdown_limit)).sum())
        if weekly_drawdown_limit is not None and not weekly_drawdown_series.empty
        else 0
    )
    daily_loss_breaches = (
        int((daily_intraday_loss_series <= -float(max_daily_loss)).sum())
        if max_daily_loss is not None and not daily_intraday_loss_series.empty
        else 0
    )

    return {
        "week_count": float(len(weekly_returns)),
        "day_count": float(len(daily_returns)),
        "weekly_net_return": float(weekly_returns.mean()) if not weekly_returns.empty else 0.0,
        "weekly_return_mean": float(weekly_returns.mean()) if not weekly_returns.empty else 0.0,
        "weekly_return_median": float(weekly_returns.median()) if not weekly_returns.empty else 0.0,
        "weekly_return_min": float(weekly_returns.min()) if not weekly_returns.empty else 0.0,
        "weekly_return_std": float(weekly_returns.std(ddof=1)) if len(weekly_returns) >= 2 else 0.0,
        "weekly_target_hit_count": float(weekly_target_hits),
        "weekly_target_hit_ratio": (
            float(weekly_target_hits / len(weekly_returns))
            if weekly_target is not None and len(weekly_returns) > 0
            else 0.0
        ),
        "worst_weekly_drawdown": float(weekly_drawdown_series.min()) if not weekly_drawdown_series.empty else 0.0,
        "weekly_drawdown_breach_count": float(weekly_drawdown_breaches),
        "daily_loss_breach_count": float(daily_loss_breaches),
        "max_total_loss_breach_count": float(_count_breach_episodes(total_loss_flags)),
        "positive_day_count": float(len(positive_days)),
        "best_day_concentration": best_day_concentration,
        "positive_day_concentration": positive_day_concentration,
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
    c = costs.dropna().astype(float) if costs is not None else None
    if gross_returns is not None:
        gross = gross_returns.dropna().astype(float)
    elif c is not None:
        aligned_net, aligned_cost = net.align(c, join="outer", fill_value=0.0)
        gross = aligned_net + aligned_cost
    else:
        gross = net.copy()

    gross_pnl = float(equity_curve_from_returns(gross).iloc[-1] - 1.0) if not gross.empty else 0.0
    net_pnl = float(equity_curve_from_returns(net).iloc[-1] - 1.0) if not net.empty else 0.0
    total_cost = float(c.sum()) if c is not None and not c.empty else 0.0
    cost_drag = gross_pnl - net_pnl

    if abs(gross_pnl) > 1e-12:
        cost_to_gross_pnl = float(cost_drag / abs(gross_pnl))
    else:
        cost_to_gross_pnl = 0.0

    return {
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "total_cost": total_cost,
        "cost_drag": float(cost_drag),
        "cost_to_gross_pnl": cost_to_gross_pnl,
        "gross_return_sum": float(gross.sum()) if not gross.empty else 0.0,
        "net_return_sum": float(net.sum()) if not net.empty else 0.0,
        "cost_return_sum": total_cost,
    }


def compute_backtest_metrics(
    *,
    net_returns: pd.Series,
    periods_per_year: int = 252,
    turnover: pd.Series | None = None,
    costs: pd.Series | None = None,
    gross_returns: pd.Series | None = None,
    annualization_mode: str = "fixed_periods",
) -> dict[str, float | str]:
    """
    Compute backtest metrics for the evaluation layer. The helper keeps the calculation isolated
    so the calling pipeline can reuse the same logic consistently across experiments.
    """
    rets = net_returns.dropna().astype(float)
    if annualization_mode not in {"fixed_periods", "calendar_daily"}:
        raise ValueError("annualization_mode must be 'fixed_periods' or 'calendar_daily'.")
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
        base["annualization_mode"] = annualization_mode
        return base
    if annualization_mode == "calendar_daily":
        metric_returns, elapsed_days = calendar_daily_returns(rets)
        daily_equity = equity_curve_from_returns(metric_returns)
        cumulative = float(daily_equity.iloc[-1] - 1.0)
        annualized = float((1.0 + cumulative) ** (365.25 / elapsed_days) - 1.0) if cumulative > -1.0 else float("nan")
        annualized_vol = annualized_volatility(metric_returns, periods_per_year=365.25)
        downside = downside_volatility(metric_returns, periods_per_year=365.25)
        # Daily compounding is solely for annualized statistics. Drawdown must preserve
        # every realized portfolio return, including an intraday drawdown recovered before
        # the UTC day closes.
        maximum_drawdown = max_drawdown(equity_curve_from_returns(rets))
        metrics: dict[str, float | str] = {
            "cumulative_return": cumulative,
            "annualized_return": annualized,
            "annualized_vol": annualized_vol,
            "sharpe": sharpe_ratio(metric_returns, periods_per_year=365.25),
            "sortino": sortino_ratio(metric_returns, periods_per_year=365.25),
            "calmar": float(annualized / abs(maximum_drawdown)) if maximum_drawdown < 0.0 else 0.0,
            "max_drawdown": maximum_drawdown,
            "profit_factor": profit_factor(rets),
            "hit_rate": hit_rate(rets),
            "metric_scope": "bar_returns",
            "annualization_mode": annualization_mode,
            "annualization_elapsed_days": elapsed_days,
            "annualization_daily_observations": float(len(metric_returns)),
        }
    else:
        equity = equity_curve_from_returns(rets)
        metrics = {
            "cumulative_return": float(equity.iloc[-1] - 1.0),
            "annualized_return": annualized_return(rets, periods_per_year=periods_per_year),
            "annualized_vol": annualized_volatility(rets, periods_per_year=periods_per_year),
            "sharpe": sharpe_ratio(rets, periods_per_year=periods_per_year),
            "sortino": sortino_ratio(rets, periods_per_year=periods_per_year),
            "calmar": calmar_ratio(rets, periods_per_year=periods_per_year),
            "max_drawdown": max_drawdown(equity),
            "profit_factor": profit_factor(rets),
            "hit_rate": hit_rate(rets),
            "annualization_mode": annualization_mode,
            "metric_scope": "bar_returns",
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
    "calendar_daily_returns",
    "compute_backtest_metrics",
    "merge_metric_overrides",
    "compute_ftmo_style_metrics",
]
