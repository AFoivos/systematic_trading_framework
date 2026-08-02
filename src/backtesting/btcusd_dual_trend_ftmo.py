from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.btcusd_dual_trend_ftmo import compute_btcusd_strategy_metrics


@dataclass(frozen=True)
class BTCUSDDualTrendBacktestResult:
    accounting: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, Any]


def _build_trade_ledger(accounting: pd.DataFrame, *, cost_per_turnover: float) -> pd.DataFrame:
    columns = [
        "trade_id",
        "side",
        "entry_timestamp",
        "exit_timestamp",
        "holding_bars",
        "gross_return_sum",
        "net_return",
        "entry_cost",
        "exit_cost",
        "holding_cost",
        "total_cost",
        "completed",
    ]
    if accounting.empty:
        return pd.DataFrame(columns=columns)

    records: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    previous = 0.0

    def finish(timestamp: pd.Timestamp, *, completed: bool = True) -> None:
        nonlocal active
        if active is None:
            return
        active["exit_timestamp"] = timestamp
        active["completed"] = bool(completed)
        active["total_cost"] = float(
            active["entry_cost"] + active["exit_cost"] + active["holding_cost"]
        )
        active["net_return"] = float(active["gross_return_sum"] - active["total_cost"])
        records.append(active)
        active = None

    for offset, (timestamp, row) in enumerate(accounting.iterrows()):
        current = float(row["position"])
        sign_changed = np.sign(current) != np.sign(previous)
        if previous != 0.0 and sign_changed:
            if active is not None:
                active["exit_cost"] += float(cost_per_turnover * abs(previous))
            finish(pd.Timestamp(timestamp))

        if current != 0.0 and (previous == 0.0 or sign_changed):
            active = {
                "trade_id": len(records) + 1,
                "side": "long" if current > 0.0 else "short",
                "entry_timestamp": pd.Timestamp(timestamp),
                "exit_timestamp": pd.NaT,
                "holding_bars": 0,
                "gross_return_sum": 0.0,
                "net_return": 0.0,
                "entry_cost": float(cost_per_turnover * abs(current)),
                "exit_cost": 0.0,
                "holding_cost": 0.0,
                "total_cost": 0.0,
                "completed": False,
            }
        elif current != 0.0 and previous != current and active is not None:
            active["holding_cost"] += float(cost_per_turnover * abs(current - previous))

        if current != 0.0 and active is not None:
            active["holding_bars"] += 1
            active["gross_return_sum"] += float(row["gross_return"])

        if bool(row["forced_liquidation"]) and current != 0.0:
            if active is not None:
                active["exit_cost"] += float(cost_per_turnover * abs(current))
            finish(pd.Timestamp(timestamp))
        previous = float(row["ending_position"])

    if active is not None:
        finish(pd.Timestamp(accounting.index[-1]), completed=False)
    return pd.DataFrame.from_records(records, columns=columns)


def run_btcusd_dual_trend_backtest(
    df: pd.DataFrame,
    *,
    signal_col: str = "signal_position",
    returns_col: str = "dual_execution_return",
    cost_per_turnover: float = 0.0004,
    periods_per_year: int = 17_520,
    liquidate_at_end: bool = True,
    missing_return_policy: str = "raise_if_exposed",
    evaluation_scope: str = "combined",
) -> BTCUSDDualTrendBacktestResult:
    """Account for the position decided at close ``t`` over its next-open interval."""
    missing = sorted({signal_col, returns_col}.difference(df.columns))
    if missing:
        raise KeyError(f"Missing BTCUSD backtest columns: {missing}.")
    if cost_per_turnover < 0.0:
        raise ValueError("cost_per_turnover must be non-negative.")
    if periods_per_year != 365 * 48:
        raise ValueError("BTCUSD periods_per_year must equal 17520.")
    if missing_return_policy != "raise_if_exposed":
        raise ValueError("BTCUSD Dual-Trend v1 requires missing_return_policy='raise_if_exposed'.")
    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        raise ValueError("BTCUSD backtest requires a timezone-aware DatetimeIndex.")
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError("BTCUSD backtest index must be unique and chronological.")

    position = df[signal_col].astype(float).fillna(0.0)
    returns = df[returns_col].astype(float)
    if (~np.isfinite(position.to_numpy(dtype=float))).any():
        raise ValueError("BTCUSD positions must be finite.")
    exposed_missing = position.ne(0.0) & (~np.isfinite(returns.to_numpy(dtype=float)))
    if bool(exposed_missing.any()):
        examples = ", ".join(str(item) for item in returns.index[exposed_missing][:5])
        raise ValueError(f"Missing returns encountered while BTCUSD positions were open: {examples}.")
    realized = returns.where(np.isfinite(returns), 0.0)

    previous = position.shift(1, fill_value=0.0)
    rebalance_turnover = (position - previous).abs()
    forced_liquidation = pd.Series(False, index=df.index, dtype=bool)
    liquidation_turnover = pd.Series(0.0, index=df.index, dtype=float)
    if liquidate_at_end and len(df):
        forced_liquidation.iloc[-1] = bool(position.iloc[-1] != 0.0)
        liquidation_turnover.iloc[-1] = abs(float(position.iloc[-1]))
    turnover = rebalance_turnover + liquidation_turnover
    gross_return = position * realized
    cost_return = float(cost_per_turnover) * turnover
    net_return = gross_return - cost_return
    if net_return.le(-1.0).any():
        timestamp = net_return.index[net_return.le(-1.0)][0]
        raise ValueError(f"BTCUSD backtest equity is exhausted at {timestamp}.")

    equity_values = np.empty(len(df), dtype=float)
    equity_before_values = np.empty(len(df), dtype=float)
    gross_pnl_values = np.empty(len(df), dtype=float)
    cost_values = np.empty(len(df), dtype=float)
    net_pnl_values = np.empty(len(df), dtype=float)
    equity = 1.0
    for offset in range(len(df)):
        equity_before_values[offset] = equity
        gross_pnl_values[offset] = equity * float(gross_return.iloc[offset])
        cost_values[offset] = equity * float(cost_return.iloc[offset])
        equity *= 1.0 + float(net_return.iloc[offset])
        equity_values[offset] = equity
        net_pnl_values[offset] = equity - equity_before_values[offset]

    accounting = df.copy()
    accounting["position_before"] = previous
    accounting["position"] = position
    accounting["ending_position"] = position.where(~forced_liquidation, 0.0)
    accounting["rebalance_turnover"] = rebalance_turnover
    accounting["liquidation_turnover"] = liquidation_turnover
    accounting["turnover"] = turnover
    accounting["gross_return"] = gross_return
    accounting["cost_return"] = cost_return
    accounting["net_return"] = net_return
    accounting["equity_before"] = equity_before_values
    accounting["gross_pnl"] = gross_pnl_values
    accounting["cost"] = cost_values
    accounting["net_pnl"] = net_pnl_values
    accounting["equity"] = equity_values
    accounting["equity_peak"] = accounting["equity"].cummax().clip(lower=1.0)
    accounting["drawdown"] = accounting["equity"] / accounting["equity_peak"] - 1.0
    accounting["forced_liquidation"] = forced_liquidation

    trades = _build_trade_ledger(accounting, cost_per_turnover=float(cost_per_turnover))
    metrics = compute_btcusd_strategy_metrics(
        accounting,
        trades,
        periods_per_year=periods_per_year,
        evaluation_scope=evaluation_scope,
    )
    return BTCUSDDualTrendBacktestResult(accounting=accounting, trades=trades, metrics=metrics)


__all__ = ["BTCUSDDualTrendBacktestResult", "run_btcusd_dual_trend_backtest"]
