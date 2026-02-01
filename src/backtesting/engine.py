from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from src.risk.controls import drawdown_cooloff_multiplier
from src.risk.position_sizing import scale_signal_by_vol


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    returns: pd.Series
    positions: pd.Series
    turnover: pd.Series
    summary: dict


def _compute_summary(returns: pd.Series, periods_per_year: int = 252) -> dict:
    rets = returns.dropna().astype(float)
    if rets.empty:
        return {
            "cumulative_return": 0.0,
            "annualized_return": 0.0,
            "annualized_vol": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }

    equity = (1.0 + rets).cumprod()
    cum_ret = equity.iloc[-1] - 1.0
    ann_ret = (1.0 + cum_ret) ** (periods_per_year / len(rets)) - 1.0
    ann_vol = rets.std(ddof=1) * np.sqrt(periods_per_year)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
    dd = equity / equity.cummax() - 1.0
    max_dd = dd.min()

    return {
        "cumulative_return": float(cum_ret),
        "annualized_return": float(ann_ret),
        "annualized_vol": float(ann_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
    }


def run_backtest(
    df: pd.DataFrame,
    signal_col: str,
    returns_col: str,
    cost_per_unit_turnover: float = 0.0,
    slippage_per_unit_turnover: float = 0.0,
    target_vol: Optional[float] = None,
    vol_col: Optional[str] = None,
    max_leverage: float = 3.0,
    dd_guard: bool = True,
    max_drawdown: float = 0.2,
    cooloff_bars: int = 20,
    periods_per_year: int = 252,
) -> BacktestResult:
    """
    Simple vectorized backtest with optional vol targeting, slippage, and drawdown guard.
    Assumes returns are simple returns (not log). For log returns, results are
    an approximation.
    """
    if signal_col not in df.columns:
        raise KeyError(f"signal_col '{signal_col}' not found in DataFrame")
    if returns_col not in df.columns:
        raise KeyError(f"returns_col '{returns_col}' not found in DataFrame")

    signal = df[signal_col].astype(float).fillna(0.0)
    returns = df[returns_col].astype(float).fillna(0.0)

    positions = signal.copy()

    if target_vol is not None:
        if vol_col is None:
            raise ValueError("vol_col must be provided when target_vol is set")
        if vol_col not in df.columns:
            raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")
        positions = scale_signal_by_vol(
            signal=positions,
            vol=df[vol_col].astype(float),
            target_vol=target_vol,
            max_leverage=max_leverage,
        )

    turnover = positions.diff().abs().fillna(0.0)
    costs = (cost_per_unit_turnover + slippage_per_unit_turnover) * turnover

    strat_returns = positions.shift(1).fillna(0.0) * returns - costs

    if dd_guard:
        equity_raw = (1.0 + strat_returns).cumprod()
        mult = drawdown_cooloff_multiplier(
            equity=equity_raw,
            max_drawdown=max_drawdown,
            cooloff_bars=cooloff_bars,
            min_exposure=0.0,
        )
        positions = positions * mult
        turnover = positions.diff().abs().fillna(0.0)
        costs = (cost_per_unit_turnover + slippage_per_unit_turnover) * turnover
        strat_returns = positions.shift(1).fillna(0.0) * returns - costs

    equity_curve = (1.0 + strat_returns).cumprod()
    equity_curve.name = "equity"

    summary = _compute_summary(strat_returns, periods_per_year=periods_per_year)

    return BacktestResult(
        equity_curve=equity_curve,
