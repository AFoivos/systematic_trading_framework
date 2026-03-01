from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics
from src.risk.controls import drawdown_cooloff_multiplier
from src.risk.position_sizing import scale_signal_by_vol

_ALLOWED_MISSING_RETURN_POLICIES = {"raise", "raise_if_exposed", "fill_zero"}


@dataclass
class BacktestResult:
    """
    Store the complete result of a single-asset backtest, including returns, positions, costs,
    turnover, and the precomputed summary metrics consumed by downstream reporting.
    """
    equity_curve: pd.Series
    returns: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    positions: pd.Series
    turnover: pd.Series
    summary: dict


def _apply_missing_return_policy(
    returns: pd.Series,
    *,
    prev_positions: pd.Series,
    missing_return_policy: str,
) -> pd.Series:
    """
    Resolve missing-return handling explicitly so exposed positions cannot silently inherit flat
    PnL from missing market data.
    """
    if missing_return_policy not in _ALLOWED_MISSING_RETURN_POLICIES:
        raise ValueError(
            f"missing_return_policy must be one of {_ALLOWED_MISSING_RETURN_POLICIES}."
        )

    rets = returns.astype(float)
    missing_mask = rets.isna()
    if not bool(missing_mask.any()):
        return rets

    if missing_return_policy == "raise":
        examples = ", ".join(str(ts) for ts in rets.index[missing_mask][:5])
        raise ValueError(f"Missing returns encountered at timestamps: {examples}")

    if missing_return_policy == "raise_if_exposed":
        exposed_missing = missing_mask & prev_positions.ne(0.0)
        if bool(exposed_missing.any()):
            examples = ", ".join(str(ts) for ts in rets.index[exposed_missing][:5])
            raise ValueError(
                "Missing returns encountered while positions were open at timestamps: "
                f"{examples}"
            )

    return rets.fillna(0.0)


def run_backtest(
    df: pd.DataFrame,
    signal_col: str,
    returns_col: str,
    returns_type: Literal["simple", "log"] = "simple",
    missing_return_policy: str = "raise_if_exposed",
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
    Returns are interpreted as simple returns by default. If returns_type="log",
    they are converted to simple returns via expm1 for PnL accounting.
    """
    if signal_col not in df.columns:
        raise KeyError(f"signal_col '{signal_col}' not found in DataFrame")
    if returns_col not in df.columns:
        raise KeyError(f"returns_col '{returns_col}' not found in DataFrame")

    signal = df[signal_col].astype(float).fillna(0.0)
    returns = df[returns_col].astype(float)
    if returns_type == "log":
        returns = np.expm1(returns)
    elif returns_type != "simple":
        raise ValueError("returns_type must be 'simple' or 'log'.")

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

    prev_positions = positions.shift(1).fillna(0.0)
    returns = _apply_missing_return_policy(
        returns,
        prev_positions=prev_positions,
        missing_return_policy=missing_return_policy,
    )
    turnover = (positions - prev_positions).abs()
    costs = (cost_per_unit_turnover + slippage_per_unit_turnover) * turnover
    gross_returns = positions.shift(1).fillna(0.0) * returns
    strat_returns = gross_returns - costs

    if dd_guard:
        equity_raw = (1.0 + strat_returns).cumprod()
        mult = drawdown_cooloff_multiplier(
            equity=equity_raw,
            max_drawdown=max_drawdown,
            cooloff_bars=cooloff_bars,
            min_exposure=0.0,
        )
        positions = positions * mult
        prev_positions = positions.shift(1).fillna(0.0)
        turnover = (positions - prev_positions).abs()
        costs = (cost_per_unit_turnover + slippage_per_unit_turnover) * turnover
        gross_returns = positions.shift(1).fillna(0.0) * returns
        strat_returns = gross_returns - costs

    equity_curve = (1.0 + strat_returns).cumprod()
    equity_curve.name = "equity"

    summary = compute_backtest_metrics(
        net_returns=strat_returns,
        periods_per_year=periods_per_year,
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )

    return BacktestResult(
        equity_curve=equity_curve,
        returns=strat_returns,
        gross_returns=gross_returns,
        costs=costs,
        positions=positions,
        turnover=turnover,
        summary=summary,
    )
