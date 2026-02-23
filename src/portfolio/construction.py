from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics
from src.portfolio.constraints import PortfolioConstraints, apply_constraints
from src.portfolio.optimizer import optimize_mean_variance


@dataclass
class PortfolioPerformance:
    equity_curve: pd.Series
    net_returns: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    turnover: pd.Series
    summary: dict[str, float]


def signal_to_raw_weights(
    signal_t: pd.Series,
    *,
    long_short: bool = True,
    gross_target: float = 1.0,
) -> pd.Series:
    if not isinstance(signal_t, pd.Series):
        raise TypeError("signal_t must be a pandas Series.")

    s = signal_t.astype(float).fillna(0.0)
    if long_short:
        s = s - float(s.mean())
    else:
        s = s.clip(lower=0.0)

    denom = float(np.abs(s).sum())
    if denom <= 0:
        return pd.Series(0.0, index=s.index, dtype=float)
    return s / denom * float(gross_target)


def build_weights_from_signals_over_time(
    signals: pd.DataFrame,
    *,
    constraints: PortfolioConstraints | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    long_short: bool = True,
    gross_target: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not isinstance(signals, pd.DataFrame):
        raise TypeError("signals must be a pandas DataFrame.")

    constraints = constraints or PortfolioConstraints()
    signals_df = signals.astype(float).sort_index().copy()

    weights = pd.DataFrame(index=signals_df.index, columns=signals_df.columns, dtype=float)
    diagnostics_rows: list[dict[str, float]] = []
    prev_w: pd.Series | None = None

    for ts, sig_t in signals_df.iterrows():
        raw_w = signal_to_raw_weights(
            sig_t,
            long_short=long_short,
            gross_target=min(float(gross_target), float(constraints.max_gross_leverage)),
        )
        constrained_w, diag = apply_constraints(
            raw_w,
            constraints=constraints,
            prev_weights=prev_w,
            asset_to_group=asset_to_group,
        )
        weights.loc[ts] = constrained_w
        diagnostics_rows.append(
            {
                "timestamp": ts,
                "net_exposure": float(diag["net_exposure"]),
                "gross_exposure": float(diag["gross_exposure"]),
                "turnover": float(diag["turnover"]),
            }
        )
        prev_w = constrained_w

    diagnostics = pd.DataFrame(diagnostics_rows).set_index("timestamp")
    return weights.fillna(0.0), diagnostics


def build_optimized_weights_over_time(
    expected_returns: pd.DataFrame,
    *,
    covariance_by_date: Mapping[pd.Timestamp, pd.DataFrame] | None = None,
    constraints: PortfolioConstraints | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    risk_aversion: float = 5.0,
    trade_aversion: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not isinstance(expected_returns, pd.DataFrame):
        raise TypeError("expected_returns must be a pandas DataFrame.")

    constraints = constraints or PortfolioConstraints()
    mu_df = expected_returns.astype(float).sort_index().copy()

    weights = pd.DataFrame(index=mu_df.index, columns=mu_df.columns, dtype=float)
    meta_rows: list[dict[str, float | bool | str]] = []
    prev_w: pd.Series | None = None

    cov_dict = dict(covariance_by_date or {})

    for ts, mu_t in mu_df.iterrows():
        cov_t = cov_dict.get(pd.Timestamp(ts))
        w_t, meta = optimize_mean_variance(
            mu_t,
            covariance=cov_t,
            constraints=constraints,
            prev_weights=prev_w,
            asset_to_group=asset_to_group,
            risk_aversion=risk_aversion,
            trade_aversion=trade_aversion,
        )
        weights.loc[ts] = w_t
        meta_rows.append(
            {
                "timestamp": ts,
                "solver_success": bool(meta["solver_success"]),
                "used_fallback": bool(meta["used_fallback"]),
                "net_exposure": float(meta["net_exposure"]),
                "gross_exposure": float(meta["gross_exposure"]),
                "turnover": float(meta["turnover"]),
            }
        )
        prev_w = w_t

    diagnostics = pd.DataFrame(meta_rows).set_index("timestamp")
    return weights.fillna(0.0), diagnostics


def compute_portfolio_performance(
    weights: pd.DataFrame,
    asset_returns: pd.DataFrame,
    *,
    cost_per_turnover: float = 0.0,
    slippage_per_turnover: float = 0.0,
    periods_per_year: int = 252,
) -> PortfolioPerformance:
    if not isinstance(weights, pd.DataFrame):
        raise TypeError("weights must be a pandas DataFrame.")
    if not isinstance(asset_returns, pd.DataFrame):
        raise TypeError("asset_returns must be a pandas DataFrame.")

    common_index = asset_returns.index.intersection(weights.index)
    common_cols = asset_returns.columns.intersection(weights.columns)
    if len(common_index) == 0 or len(common_cols) == 0:
        raise ValueError("weights and asset_returns have no common index/columns.")

    w = weights.reindex(index=common_index, columns=common_cols).fillna(0.0).astype(float)
    r = asset_returns.reindex(index=common_index, columns=common_cols).fillna(0.0).astype(float)

    prev_w = w.shift(1).fillna(0.0)
    turnover = (w - prev_w).abs().sum(axis=1)
    gross_returns = (w.shift(1).fillna(0.0) * r).sum(axis=1)
    costs = (cost_per_turnover + slippage_per_turnover) * turnover
    net_returns = gross_returns - costs

    equity = (1.0 + net_returns).cumprod()
    equity.name = "equity"
    gross_returns.name = "gross_returns"
    net_returns.name = "net_returns"
    costs.name = "costs"
    turnover.name = "turnover"

    summary = compute_backtest_metrics(
        net_returns=net_returns,
        periods_per_year=periods_per_year,
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )

    return PortfolioPerformance(
        equity_curve=equity,
        net_returns=net_returns,
        gross_returns=gross_returns,
        costs=costs,
        turnover=turnover,
        summary=summary,
    )


__all__ = [
    "PortfolioPerformance",
    "signal_to_raw_weights",
    "build_weights_from_signals_over_time",
    "build_optimized_weights_over_time",
    "compute_portfolio_performance",
]
