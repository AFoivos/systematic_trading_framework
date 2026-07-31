from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.metrics import (
    annualized_return,
    annualized_volatility,
    calmar_ratio,
    hit_rate,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
)

from src.risk.eurusd_ftmo_ml_v2_sizing import add_volatility_factor, drawdown_scale
from src.utils.eurusd_ftmo_ml_v2_contract import (
    BASE_NOTIONAL_MULTIPLE,
    COMMISSION_PIPS_PER_SIDE,
    DAILY_CIRCUIT_BREAKER,
    FTMO_TIMEZONE,
    PERIODS_PER_YEAR,
    PIP_SIZE,
    SLIPPAGE_PIPS_PER_SIDE,
)


@dataclass
class BacktestResult:
    positions: pd.DataFrame
    orders: pd.DataFrame
    equity_curve: pd.DataFrame
    metrics: dict[str, Any]
    daily_returns: pd.DataFrame
    monthly_returns: pd.DataFrame


def _circuit_limited_target(current: float, requested: float) -> float:
    """Permit exits/reductions but never an absolute exposure increase."""
    if current == 0.0:
        return 0.0
    if requested == 0.0:
        return 0.0
    if np.sign(requested) != np.sign(current):
        return 0.0
    return float(np.sign(current) * min(abs(current), abs(requested)))


def _turnover_split(current: float, target: float) -> tuple[float, float]:
    if current == target:
        return 0.0, 0.0
    if current == 0.0:
        return abs(target), 0.0
    if target == 0.0:
        return 0.0, abs(current)
    if np.sign(current) != np.sign(target):
        return abs(target), abs(current)
    if abs(target) > abs(current):
        return abs(target) - abs(current), 0.0
    return 0.0, abs(current) - abs(target)


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return float(numerator / denominator) if np.isfinite(denominator) and denominator != 0.0 else None


def run_bar_backtest(
    market: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    initial_equity: float = 1.0,
) -> BacktestResult:
    required_market = {"mid_open", "bid_open", "ask_open", "spread_open", "logret1"}
    missing_market = sorted(required_market.difference(market.columns))
    if missing_market:
        raise KeyError(f"Missing backtest market columns: {missing_market}")
    if "directional_signal" not in signals.columns:
        raise KeyError("signals must contain directional_signal.")
    if not market.index.equals(signals.index):
        raise ValueError("Market and signal indexes must match exactly.")
    if initial_equity <= 0.0:
        raise ValueError("initial_equity must be positive.")

    sized_market = add_volatility_factor(market)
    directional = signals["directional_signal"].astype(float)
    raw_target = directional * BASE_NOTIONAL_MULTIPLE * sized_market["volatility_factor"]
    raw_target = raw_target.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    utc_index = market.index.tz_localize("UTC") if market.index.tz is None else market.index.tz_convert("UTC")
    local_dates = utc_index.tz_convert(FTMO_TIMEZONE).date

    equity = float(initial_equity)
    equity_peak = float(initial_equity)
    position = 0.0
    daily_start_balance = float(initial_equity)
    current_local_date: object | None = None
    circuit_active = False
    position_records: list[dict[str, Any]] = []
    order_records: list[dict[str, Any]] = []

    for loc, timestamp in enumerate(market.index):
        equity_before = equity
        if loc == 0:
            open_return = 0.0
        else:
            open_return = float(market["mid_open"].iloc[loc] / market["mid_open"].iloc[loc - 1] - 1.0)
        gross_return = position * open_return
        gross_pnl = equity_before * gross_return
        marked_equity = equity_before + gross_pnl

        local_date = local_dates[loc]
        if current_local_date != local_date:
            current_local_date = local_date
            daily_start_balance = marked_equity
            circuit_active = False
        daily_loss_before = marked_equity / daily_start_balance - 1.0
        if daily_loss_before <= DAILY_CIRCUIT_BREAKER:
            circuit_active = True

        equity_peak = max(equity_peak, marked_equity)
        drawdown_before = marked_equity / equity_peak - 1.0
        scale = float(drawdown_scale(drawdown_before))
        requested_target = float(raw_target.iloc[loc] * scale)
        actual_target = (
            _circuit_limited_target(position, requested_target)
            if circuit_active
            else requested_target
        )
        delta = actual_target - position
        turnover = abs(delta)
        entry_turnover, exit_turnover = _turnover_split(position, actual_target)
        mid_open = float(market["mid_open"].iloc[loc])
        spread_open = float(market["ask_open"].iloc[loc] - market["bid_open"].iloc[loc])
        spread_return = turnover * spread_open / (2.0 * mid_open)
        commission_return = turnover * COMMISSION_PIPS_PER_SIDE * PIP_SIZE / mid_open
        slippage_return = turnover * SLIPPAGE_PIPS_PER_SIDE * PIP_SIZE / mid_open
        total_cost_return = spread_return + commission_return + slippage_return
        total_cost = marked_equity * total_cost_return
        equity = marked_equity * (1.0 - total_cost_return)
        net_return = equity / equity_before - 1.0
        position_before = position
        position = actual_target
        equity_peak = max(equity_peak, equity)
        drawdown_after = equity / equity_peak - 1.0
        daily_loss_after = equity / daily_start_balance - 1.0
        if daily_loss_after <= DAILY_CIRCUIT_BREAKER:
            circuit_active = True

        position_records.append(
            {
                "timestamp": timestamp,
                "directional_signal": float(directional.iloc[loc]),
                "volatility_factor": float(sized_market["volatility_factor"].iloc[loc]) if pd.notna(sized_market["volatility_factor"].iloc[loc]) else np.nan,
                "raw_position_multiple": float(raw_target.iloc[loc]),
                "drawdown_scale": scale,
                "target_position_multiple": requested_target,
                "actual_position_multiple": position,
                "position_before": position_before,
                "turnover": turnover,
                "gross_return": gross_return,
                "spread_cost_return": spread_return,
                "commission_return": commission_return,
                "slippage_return": slippage_return,
                "total_cost_return": total_cost_return,
                "net_return": net_return,
                "gross_pnl": gross_pnl,
                "net_pnl": equity - equity_before,
                "equity": equity,
                "equity_peak": equity_peak,
                "drawdown": drawdown_after,
                "ftmo_date": str(local_date),
                "daily_start_balance": daily_start_balance,
                "daily_loss": daily_loss_after,
                "daily_circuit_active": circuit_active,
            }
        )
        if turnover > 0.0:
            execution_price = float(market["ask_open"].iloc[loc] if delta > 0.0 else market["bid_open"].iloc[loc])
            order_records.append(
                {
                    "timestamp": timestamp,
                    "side": "buy" if delta > 0.0 else "sell",
                    "position_before": position_before,
                    "position_after": position,
                    "quantity_multiple": turnover,
                    "entry_turnover": entry_turnover,
                    "exit_turnover": exit_turnover,
                    "mid_open": mid_open,
                    "execution_price": execution_price,
                    "spread_cost_return": spread_return,
                    "commission_return": commission_return,
                    "slippage_return": slippage_return,
                    "total_cost_return": total_cost_return,
                    "daily_circuit_active": circuit_active,
                }
            )

    positions = pd.DataFrame.from_records(position_records).set_index("timestamp")
    orders = pd.DataFrame.from_records(order_records)
    if not orders.empty:
        orders = orders.set_index("timestamp")
    equity_curve = positions[["equity", "equity_peak", "drawdown", "gross_return", "net_return"]].copy()
    daily = positions["net_return"].groupby(positions.index.normalize()).apply(
        lambda values: (1.0 + values).prod() - 1.0
    ).rename("return").to_frame()
    monthly = positions["net_return"].groupby(positions.index.to_period("M")).apply(
        lambda values: (1.0 + values).prod() - 1.0
    ).rename("return").to_frame()
    metrics = compute_strategy_metrics(positions=positions, orders=orders, candidates=None)
    return BacktestResult(positions, orders, equity_curve, metrics, daily, monthly)


def compute_strategy_metrics(
    *,
    positions: pd.DataFrame,
    orders: pd.DataFrame,
    candidates: pd.DataFrame | None,
) -> dict[str, Any]:
    returns = positions["net_return"].astype(float)
    gross_returns = positions["gross_return"].astype(float)
    costs = positions["total_cost_return"].astype(float)
    equity = positions["equity"].astype(float)
    annual_vol = annualized_volatility(returns, PERIODS_PER_YEAR)
    ann_return = annualized_return(returns, PERIODS_PER_YEAR)
    gross_compound = float((1.0 + gross_returns).prod() - 1.0)
    net_compound = float((1.0 + returns).prod() - 1.0)
    total_cost = float(costs.sum())
    accepted = pd.DataFrame()
    if candidates is not None and not candidates.empty:
        accepted = candidates.loc[candidates.get("confidence", 0.0).fillna(0.0) > 0.0]
    trade_returns = accepted["net_return"].astype(float) if "net_return" in accepted else pd.Series(dtype=float)
    entry_cost = 0.0
    exit_cost = 0.0
    if not orders.empty:
        cost_per_turnover = orders["total_cost_return"] / orders["quantity_multiple"].replace(0.0, np.nan)
        entry_cost = float((cost_per_turnover * orders["entry_turnover"]).fillna(0.0).sum())
        exit_cost = float((cost_per_turnover * orders["exit_turnover"]).fillna(0.0).sum())
    metrics: dict[str, Any] = {
        "cumulative_return": net_compound,
        "annualized_return": ann_return,
        "annualized_vol": annual_vol,
        "sharpe": sharpe_ratio(returns, PERIODS_PER_YEAR),
        "sortino": sortino_ratio(returns, PERIODS_PER_YEAR),
        "calmar": calmar_ratio(returns, PERIODS_PER_YEAR),
        "max_drawdown": max_drawdown(equity),
        "profit_factor": profit_factor(returns),
        "hit_rate": hit_rate(returns),
        "avg_turnover": float(positions["turnover"].mean()),
        "total_turnover": float(positions["turnover"].sum()),
        "gross_pnl": float(positions["gross_pnl"].sum()),
        "net_pnl": float(equity.iloc[-1] - equity.iloc[0] + positions["net_pnl"].iloc[0]) if len(equity) else 0.0,
        "total_cost": total_cost,
        "cost_drag": gross_compound - net_compound,
        "cost_to_gross_pnl": _safe_ratio(total_cost, float(positions["gross_pnl"].sum())),
        "gross_return_sum": float(gross_returns.sum()),
        "net_return_sum": float(returns.sum()),
        "cost_return_sum": total_cost,
        "conventional_sharpe": sharpe_ratio(returns, PERIODS_PER_YEAR),
        "return_over_vol_sharpe": _safe_ratio(ann_return, annual_vol),
        "bar_return_profit_factor": profit_factor(returns),
        "evaluation_scope": "strict_oos_2022_plus",
        "evaluation_start": positions.index.min().isoformat() if len(positions) else None,
        "evaluation_end": positions.index.max().isoformat() if len(positions) else None,
        "evaluation_rows": int(len(positions)),
        "trade_count": int(len(accepted)),
        "completed_trade_count": int(len(accepted)),
        "win_rate": float((trade_returns > 0.0).mean()) if len(trade_returns) else 0.0,
        "trade_return_profit_factor": profit_factor(trade_returns),
        "trade_r_profit_factor": profit_factor(trade_returns),
        "trade_profit_factor": profit_factor(trade_returns),
        "entry_trade_cost": entry_cost,
        "exit_trade_cost": exit_cost,
        "holding_trade_cost": 0.0,
        "total_trade_cost": entry_cost + exit_cost,
        "position_transition_count": int((positions["turnover"] > 0.0).sum()),
        "turnover_event_count": int(len(orders)),
        "exposed_bar_count": int((positions["actual_position_multiple"].abs() > 0.0).sum()),
    }
    return metrics


__all__ = ["BacktestResult", "compute_strategy_metrics", "run_bar_backtest"]
