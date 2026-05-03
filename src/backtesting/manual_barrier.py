from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult
from src.evaluation.metrics import compute_backtest_metrics


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for manual barrier backtest: {missing}")


def _finite_price(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"{field} must be a finite positive price.")
    return out


def run_manual_barrier_backtest(
    df: pd.DataFrame,
    *,
    signal_col: str,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    take_profit_r: float = 1.8,
    stop_loss_r: float = 1.0,
    risk_per_trade: float = 0.006,
    max_holding_bars: int = 16,
    cost_per_unit_turnover: float = 0.0,
    slippage_per_unit_turnover: float = 0.0,
    max_leverage: float = 1.0,
    periods_per_year: int = 252,
) -> BacktestResult:
    """
    Event-based long-only backtest for manual rule signals.

    Signal is read at bar close `t`; entry is executed at the next bar open `t+1`. Exits are
    evaluated from the entry bar onward using stop loss, take profit, or max holding. No
    pyramiding, averaging down, martingale sizing, or risk escalation is applied.

    TODO: add optional, explicitly-configured exit policies without changing the default engine
    contract: signal-off exits, break-even stop, profit-lock stop, and no-progress exits.
    """
    _require_columns(df, [signal_col, open_col, high_col, low_col, close_col])
    if int(max_holding_bars) <= 0:
        raise ValueError("max_holding_bars must be positive.")
    if float(take_profit_r) <= 0.0 or float(stop_loss_r) <= 0.0:
        raise ValueError("take_profit_r and stop_loss_r must be positive.")
    if float(risk_per_trade) <= 0.0:
        raise ValueError("risk_per_trade must be positive.")
    if float(max_leverage) <= 0.0:
        raise ValueError("max_leverage must be positive.")
    if float(cost_per_unit_turnover) < 0.0 or float(slippage_per_unit_turnover) < 0.0:
        raise ValueError("cost_per_unit_turnover and slippage_per_unit_turnover must be >= 0.")

    frame = df.copy()
    signal = pd.to_numeric(frame[signal_col], errors="coerce").fillna(0.0).astype(float)
    signal = signal.clip(lower=0.0, upper=float(max_leverage))
    index = frame.index

    net_returns = pd.Series(0.0, index=index, name="returns", dtype=float)
    gross_returns = pd.Series(0.0, index=index, name="gross_returns", dtype=float)
    costs = pd.Series(0.0, index=index, name="costs", dtype=float)
    positions = pd.Series(0.0, index=index, name="positions", dtype=float)
    trades: list[dict[str, Any]] = []

    i = 0
    n = len(frame)
    while i < n - 1:
        raw_signal = float(signal.iloc[i])
        if raw_signal <= 0.0:
            i += 1
            continue

        entry_idx = i + 1
        entry_open = _finite_price(frame.iloc[entry_idx][open_col], field=f"{open_col}[entry]")
        size = min(raw_signal, float(max_leverage))
        stop_distance_pct = max(float(risk_per_trade) * float(stop_loss_r), 1e-8)
        target_distance_pct = max(float(risk_per_trade) * float(take_profit_r), 1e-8)
        stop_price = entry_open * (1.0 - stop_distance_pct)
        take_profit_price = entry_open * (1.0 + target_distance_pct)

        exit_idx: int | None = None
        raw_exit_price = np.nan
        exit_reason = "max_holding_close"
        bars_held = 0
        max_exit_idx = min(n - 1, entry_idx + int(max_holding_bars) - 1)

        for j in range(entry_idx, max_exit_idx + 1):
            bar = frame.iloc[j]
            bar_low = _finite_price(bar[low_col], field=f"{low_col}[{j}]")
            bar_high = _finite_price(bar[high_col], field=f"{high_col}[{j}]")
            bars_held += 1
            stop_hit = bar_low <= stop_price
            target_hit = bar_high >= take_profit_price
            if stop_hit and target_hit:
                exit_idx = j
                raw_exit_price = stop_price
                exit_reason = "stop_and_target_same_bar_stop_first"
                break
            if stop_hit:
                exit_idx = j
                raw_exit_price = stop_price
                exit_reason = "stop_loss"
                break
            if target_hit:
                exit_idx = j
                raw_exit_price = take_profit_price
                exit_reason = "take_profit"
                break

        if exit_idx is None:
            exit_idx = max_exit_idx
            raw_exit_price = _finite_price(frame.iloc[exit_idx][close_col], field=f"{close_col}[exit]")
            exit_reason = "max_holding_close"

        slip = float(slippage_per_unit_turnover)
        entry_price = entry_open * (1.0 + slip)
        exit_price = raw_exit_price * (1.0 - slip)
        gross_before_cost = size * (raw_exit_price / entry_open - 1.0)
        gross_after_slippage = size * (exit_price / entry_price - 1.0)
        slippage_drag = max(gross_before_cost - gross_after_slippage, 0.0)
        fixed_cost = size * 2.0 * float(cost_per_unit_turnover)
        total_cost = fixed_cost + slippage_drag
        net_return = gross_before_cost - total_cost
        risk_capital = max(size * stop_distance_pct, 1e-12)
        trade_r = net_return / risk_capital

        gross_returns.iloc[exit_idx] += gross_before_cost
        costs.iloc[exit_idx] += total_cost
        net_returns.iloc[exit_idx] += net_return
        if exit_idx > entry_idx:
            positions.iloc[entry_idx:exit_idx] = size

        trades.append(
            {
                "signal_timestamp": index[i],
                "entry_timestamp": index[entry_idx],
                "exit_timestamp": index[exit_idx],
                "side": "long",
                "signal": raw_signal,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "raw_entry_price": entry_open,
                "raw_exit_price": raw_exit_price,
                "take_profit_price": take_profit_price,
                "stop_loss_price": stop_price,
                "target_price": take_profit_price,
                "position_size": size,
                "gross_return": gross_before_cost,
                "cost_paid": total_cost,
                "net_return": net_return,
                "trade_r": trade_r,
                "bars_held": int(bars_held),
                "exit_reason": exit_reason,
            }
        )
        i = exit_idx + 1

    turnover = (positions - positions.shift(1).fillna(0.0)).abs()
    turnover.name = "turnover"
    equity_curve = (1.0 + net_returns).cumprod()
    equity_curve.name = "equity"
    summary = compute_backtest_metrics(
        net_returns=net_returns,
        periods_per_year=int(periods_per_year),
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )
    return BacktestResult(
        equity_curve=equity_curve,
        returns=net_returns,
        gross_returns=gross_returns,
        costs=costs,
        positions=positions,
        turnover=turnover,
        summary=summary,
        trades=pd.DataFrame(trades),
    )


__all__ = ["run_manual_barrier_backtest"]
