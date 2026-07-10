from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult
from src.utils.trade_path import (
    normalize_dynamic_exit_config,
    normalize_partial_exit_config,
    simulate_barrier_trade_outcome,
    simulate_long_trade_path,
    simulate_short_trade_path,
)
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


def _finite_positive(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"{field} must be finite and > 0.")
    return out


def _apply_mark_to_market_trade_path(
    mark_to_market_returns: pd.Series,
    *,
    closes: np.ndarray,
    entry_idx: int,
    exit_idx: int,
    entry_price: float,
    exit_price: float,
    size: float,
    is_short: bool,
    total_cost: float,
) -> None:
    """
    Add a close-to-close floating PnL path for one completed event trade.

    The legacy manual-barrier contract books the whole trade at the exit bar. This diagnostic
    path keeps that contract intact while exposing the open-trade drawdown that a live account
    would have experienced between entry and exit.
    """
    previous_price = float(entry_price)
    for bar_idx in range(int(entry_idx), int(exit_idx) + 1):
        mark_price = float(exit_price) if bar_idx == int(exit_idx) else float(closes[bar_idx])
        if not np.isfinite(mark_price) or mark_price <= 0.0 or previous_price <= 0.0:
            previous_price = mark_price
            continue
        if is_short:
            gross_return = float(size) * (1.0 - mark_price / previous_price)
        else:
            gross_return = float(size) * (mark_price / previous_price - 1.0)
        cost = float(total_cost) if bar_idx == int(exit_idx) else 0.0
        mark_to_market_returns.iloc[bar_idx] += gross_return - cost
        previous_price = mark_price


def _leg_raw_return(*, is_short: bool, entry_price: float, exit_price: float) -> float:
    if is_short:
        return 1.0 - float(exit_price) / float(entry_price)
    return float(exit_price) / float(entry_price) - 1.0


def _leg_slippage_adjusted_return(
    *,
    is_short: bool,
    entry_price: float,
    exit_price: float,
    slippage_per_unit_turnover: float,
) -> float:
    slip = float(slippage_per_unit_turnover)
    if is_short:
        adjusted_entry = float(entry_price) * (1.0 - slip)
        adjusted_exit = float(exit_price) * (1.0 + slip)
        return 1.0 - adjusted_exit / adjusted_entry
    adjusted_entry = float(entry_price) * (1.0 + slip)
    adjusted_exit = float(exit_price) * (1.0 - slip)
    return adjusted_exit / adjusted_entry - 1.0


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
    max_holding_bars: int | None = 16,
    cost_per_unit_turnover: float = 0.0,
    slippage_per_unit_turnover: float = 0.0,
    max_leverage: float = 1.0,
    periods_per_year: int = 252,
    dynamic_exits: dict[str, Any] | None = None,
    partial_exits: dict[str, Any] | None = None,
    allow_short: bool = False,
    stop_mode: str = "fixed_return",
    vol_col: str | None = None,
) -> BacktestResult:
    """
    Event-based backtest for manual rule signals.

    Signal is read at bar close `t`; entry is executed at the next bar open `t+1`. Exits are
    evaluated from the entry bar onward using stop loss, take profit, or max holding. Set
    ``max_holding_bars=None`` to disable the time exit; an open final trade is then marked to the
    final dataset close. No pyramiding, averaging down, martingale sizing, or risk escalation is
    applied.

    Dynamic exits are opt-in. With `dynamic_exits.enabled=false` or no dynamic exit config, the
    engine keeps the legacy stop/take-profit/max-holding behavior.

    Partial exits are also opt-in. With `partial_exits.enabled=false` or no partial-exit config,
    the legacy single-exit accounting path is preserved.

    With ``stop_mode="volatility_stop"``, ``vol_col`` must contain a positive point-in-time
    volatility or ATR-over-price estimate. Stop and take-profit distances are then computed as
    ``vol_col * stop_loss_r`` and ``vol_col * take_profit_r`` from the signal bar.
    """
    stop_mode = str(stop_mode)
    if stop_mode not in {"fixed_return", "volatility_stop"}:
        raise ValueError("stop_mode must be 'fixed_return' or 'volatility_stop'.")
    if max_holding_bars is not None and int(max_holding_bars) <= 0:
        raise ValueError("max_holding_bars must be positive.")
    if float(take_profit_r) <= 0.0 or float(stop_loss_r) <= 0.0:
        raise ValueError("take_profit_r and stop_loss_r must be positive.")
    if float(risk_per_trade) <= 0.0:
        raise ValueError("risk_per_trade must be positive.")
    if float(max_leverage) <= 0.0:
        raise ValueError("max_leverage must be positive.")
    if float(cost_per_unit_turnover) < 0.0 or float(slippage_per_unit_turnover) < 0.0:
        raise ValueError("cost_per_unit_turnover and slippage_per_unit_turnover must be >= 0.")
    dynamic_cfg = normalize_dynamic_exit_config(dynamic_exits)
    partial_cfg = normalize_partial_exit_config(partial_exits)
    partial_enabled = bool(partial_cfg.get("enabled", False))
    needs_volatility = stop_mode == "volatility_stop" or bool(dynamic_cfg["atr_trailing"]["enabled"])
    if needs_volatility and (vol_col is None or not str(vol_col).strip()):
        raise ValueError("vol_col is required for volatility_stop or dynamic_exits.atr_trailing.")
    required_cols = [signal_col, open_col, high_col, low_col, close_col]
    if needs_volatility:
        required_cols.append(str(vol_col))
    _require_columns(df, required_cols)

    frame = df.copy()
    signal = pd.to_numeric(frame[signal_col], errors="coerce").fillna(0.0).astype(float)
    if allow_short:
        signal = signal.clip(lower=-float(max_leverage), upper=float(max_leverage))
    else:
        signal = signal.clip(lower=0.0, upper=float(max_leverage))
    index = frame.index
    opens = pd.to_numeric(frame[open_col], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(frame[high_col], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(frame[low_col], errors="coerce").to_numpy(dtype=float)
    closes = pd.to_numeric(frame[close_col], errors="coerce").to_numpy(dtype=float)
    signals = signal.to_numpy(dtype=float)
    volatility = (
        pd.to_numeric(frame[str(vol_col)], errors="coerce").to_numpy(dtype=float)
        if needs_volatility
        else None
    )

    net_returns = pd.Series(0.0, index=index, name="returns", dtype=float)
    gross_returns = pd.Series(0.0, index=index, name="gross_returns", dtype=float)
    costs = pd.Series(0.0, index=index, name="costs", dtype=float)
    positions = pd.Series(0.0, index=index, name="positions", dtype=float)
    turnover_events = pd.Series(0.0, index=index, name="turnover", dtype=float)
    mark_to_market_returns = pd.Series(0.0, index=index, name="mark_to_market_returns", dtype=float)
    trades: list[dict[str, Any]] = []

    i = 0
    n = len(frame)
    while i < n - 1:
        raw_signal = float(signal.iloc[i])
        if raw_signal == 0.0:
            i += 1
            continue
        if raw_signal < 0.0 and not allow_short:
            i += 1
            continue

        entry_idx = i + 1
        entry_open = _finite_price(frame.iloc[entry_idx][open_col], field=f"{open_col}[entry]")
        raw_size = min(abs(raw_signal), float(max_leverage))
        if stop_mode == "volatility_stop":
            assert volatility is not None
            signal_volatility = _finite_positive(
                volatility[i],
                field=f"{vol_col}[signal]",
            )
            stop_distance_pct = max(signal_volatility * float(stop_loss_r), 1e-8)
            target_distance_pct = max(signal_volatility * float(take_profit_r), 1e-8)
            risk_sized_cap = float(risk_per_trade) / stop_distance_pct
            size = min(raw_size, risk_sized_cap, float(max_leverage))
        else:
            size = raw_size
            stop_distance_pct = max(float(risk_per_trade) * float(stop_loss_r), 1e-8)
            target_distance_pct = max(float(risk_per_trade) * float(take_profit_r), 1e-8)
        max_exit_idx = (
            n - 1
            if max_holding_bars is None
            else min(n - 1, entry_idx + int(max_holding_bars) - 1)
        )
        is_short = raw_signal < 0.0
        outcome: dict[str, Any] | None = None
        if not partial_enabled:
            outcome = simulate_barrier_trade_outcome(
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                signals=signals,
                signal_idx=i,
                side=-1 if is_short else 1,
                take_profit_r=float(take_profit_r),
                stop_loss_r=float(stop_loss_r),
                risk_per_trade=float(risk_per_trade),
                max_holding_bars=max_holding_bars,
                cost_per_unit_turnover=float(cost_per_unit_turnover),
                slippage_per_unit_turnover=float(slippage_per_unit_turnover),
                max_leverage=float(max_leverage),
                stop_mode=stop_mode,
                volatility=volatility,
                vol_col=str(vol_col) if vol_col is not None else None,
                dynamic_exits=dynamic_cfg,
                entry_price_mode="next_open",
                tie_break="conservative",
                allow_partial_horizon=True,
                apply_risk_sizing=True,
                signal_size=raw_signal,
                legacy_same_bar_stop_reason=not bool(dynamic_cfg.get("enabled", False)),
            )
            if not bool(outcome["valid"]):
                raise ValueError(f"manual barrier outcome invalid: {outcome['exit_reason']}")
            stop_price = float(outcome["stop_loss_price"])
            take_profit_price = float(outcome["take_profit_price"])
            path = {
                "exit_idx": int(outcome["exit_idx"]),
                "raw_exit_price": float(outcome["raw_exit_price"]),
                "exit_reason": str(outcome["exit_reason"]),
                "bars_held": int(outcome["bars_held"]),
                "max_favorable_r": float(outcome["max_favorable_r"]),
                "max_adverse_r": float(outcome["max_adverse_r"]),
                "breakeven_activated": bool(outcome["breakeven_activated"]),
                "profit_lock_activated": bool(outcome["profit_lock_activated"]),
                "effective_stop_price": float(outcome["effective_stop_price"]),
                "partial_exits": [],
            }
        elif is_short:
            stop_price = entry_open * (1.0 + stop_distance_pct)
            take_profit_price = entry_open * (1.0 - target_distance_pct)
            path = simulate_short_trade_path(
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                signals=signals,
                entry_idx=entry_idx,
                max_exit_idx=max_exit_idx,
                entry_price=entry_open,
                initial_stop_price=stop_price,
                take_profit_price=take_profit_price,
                dynamic_exits=dynamic_cfg,
                partial_exits=partial_cfg,
                volatility=volatility,
                tie_break="conservative",
                legacy_same_bar_stop_reason=not bool(dynamic_cfg.get("enabled", False)),
            )
        else:
            stop_price = entry_open * (1.0 - stop_distance_pct)
            take_profit_price = entry_open * (1.0 + target_distance_pct)
            path = simulate_long_trade_path(
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                signals=signals,
                entry_idx=entry_idx,
                max_exit_idx=max_exit_idx,
                entry_price=entry_open,
                initial_stop_price=stop_price,
                take_profit_price=take_profit_price,
                dynamic_exits=dynamic_cfg,
                partial_exits=partial_cfg,
                volatility=volatility,
                tie_break="conservative",
                legacy_same_bar_stop_reason=not bool(dynamic_cfg.get("enabled", False)),
            )

        exit_idx = int(path["exit_idx"])
        raw_exit_price = _finite_price(path["raw_exit_price"], field=f"{close_col}[exit]")
        exit_reason = str(path["exit_reason"])
        if max_holding_bars is None and exit_reason == "max_holding_close":
            exit_reason = "end_of_data_close"
        bars_held = int(path["bars_held"])

        slip = float(slippage_per_unit_turnover)
        entry_price = entry_open * (1.0 - slip) if is_short else entry_open * (1.0 + slip)
        exit_price = raw_exit_price * (1.0 + slip) if is_short else raw_exit_price * (1.0 - slip)
        partial_events = list(path.get("partial_exits", []) or []) if partial_enabled else []
        if partial_events:
            partial_fraction_total = float(sum(float(event["fraction"]) for event in partial_events))
            remaining_fraction = max(1.0 - partial_fraction_total, 0.0)
            exit_legs = [
                {
                    "fraction": float(event["fraction"]),
                    "exit_idx": int(event["exit_idx"]),
                    "raw_exit_price": float(event["raw_exit_price"]),
                    "trigger_r": float(event["trigger_r"]),
                }
                for event in partial_events
            ]
            if remaining_fraction > 1e-12:
                exit_legs.append(
                    {
                        "fraction": remaining_fraction,
                        "exit_idx": exit_idx,
                        "raw_exit_price": raw_exit_price,
                        "trigger_r": np.nan,
                    }
                )
            else:
                exit_reason = "partial_exit_complete"
            gross_before_cost = 0.0
            gross_after_slippage = 0.0
            exit_turnover_fraction = 0.0
            for leg in exit_legs:
                leg_fraction = float(leg["fraction"])
                leg_return = _leg_raw_return(
                    is_short=is_short,
                    entry_price=entry_open,
                    exit_price=float(leg["raw_exit_price"]),
                )
                leg_slipped_return = _leg_slippage_adjusted_return(
                    is_short=is_short,
                    entry_price=entry_open,
                    exit_price=float(leg["raw_exit_price"]),
                    slippage_per_unit_turnover=slip,
                )
                gross_before_cost += size * leg_fraction * leg_return
                gross_after_slippage += size * leg_fraction * leg_slipped_return
                exit_turnover_fraction += leg_fraction
            slippage_drag = max(gross_before_cost - gross_after_slippage, 0.0)
            fixed_cost = size * (1.0 + exit_turnover_fraction) * float(cost_per_unit_turnover)
            total_cost = fixed_cost + slippage_drag
            net_return = gross_before_cost - total_cost
        else:
            if outcome is not None:
                size = float(outcome["size"])
                stop_distance_pct = float(outcome["stop_distance_pct"])
                target_distance_pct = float(outcome["target_distance_pct"])
                entry_price = float(outcome["entry_price"])
                exit_price = float(outcome["exit_price"])
                gross_before_cost = float(outcome["gross_return"])
                slippage_drag = float(outcome["slippage_drag"])
                total_cost = float(outcome["cost_paid"])
                net_return = float(outcome["net_return"])
            else:
                if is_short:
                    gross_before_cost = size * (1.0 - raw_exit_price / entry_open)
                    gross_after_slippage = size * (1.0 - exit_price / entry_price)
                else:
                    gross_before_cost = size * (raw_exit_price / entry_open - 1.0)
                    gross_after_slippage = size * (exit_price / entry_price - 1.0)
                slippage_drag = max(gross_before_cost - gross_after_slippage, 0.0)
                fixed_cost = size * 2.0 * float(cost_per_unit_turnover)
                total_cost = fixed_cost + slippage_drag
                net_return = gross_before_cost - total_cost
        risk_capital = max(size * stop_distance_pct, 1e-12)
        trade_r = net_return / risk_capital
        partial_realized_r = (
            sum(
                float(event["fraction"])
                * _leg_raw_return(
                    is_short=is_short,
                    entry_price=entry_open,
                    exit_price=float(event["raw_exit_price"]),
                )
                / stop_distance_pct
                for event in partial_events
            )
            if partial_events
            else 0.0
        )

        if partial_events:
            turnover_events.iloc[entry_idx] += size
            entry_fixed_cost = size * float(cost_per_unit_turnover)
            costs.iloc[entry_idx] += entry_fixed_cost
            net_returns.iloc[entry_idx] -= entry_fixed_cost
            for event in partial_events:
                event_idx = int(event["exit_idx"])
                event_fraction = float(event["fraction"])
                event_price = float(event["raw_exit_price"])
                turnover_events.iloc[event_idx] += size * event_fraction
                event_gross = size * event_fraction * _leg_raw_return(
                    is_short=is_short,
                    entry_price=entry_open,
                    exit_price=event_price,
                )
                event_slipped = size * event_fraction * _leg_slippage_adjusted_return(
                    is_short=is_short,
                    entry_price=entry_open,
                    exit_price=event_price,
                    slippage_per_unit_turnover=slip,
                )
                event_cost = size * event_fraction * float(cost_per_unit_turnover) + max(
                    event_gross - event_slipped,
                    0.0,
                )
                gross_returns.iloc[event_idx] += event_gross
                costs.iloc[event_idx] += event_cost
                net_returns.iloc[event_idx] += event_gross - event_cost
            final_fraction = max(1.0 - sum(float(event["fraction"]) for event in partial_events), 0.0)
            if final_fraction > 1e-12:
                turnover_events.iloc[exit_idx] += size * final_fraction
                final_gross = size * final_fraction * _leg_raw_return(
                    is_short=is_short,
                    entry_price=entry_open,
                    exit_price=raw_exit_price,
                )
                final_slipped = size * final_fraction * _leg_slippage_adjusted_return(
                    is_short=is_short,
                    entry_price=entry_open,
                    exit_price=raw_exit_price,
                    slippage_per_unit_turnover=slip,
                )
                final_cost = size * final_fraction * float(cost_per_unit_turnover) + max(
                    final_gross - final_slipped,
                    0.0,
                )
                gross_returns.iloc[exit_idx] += final_gross
                costs.iloc[exit_idx] += final_cost
                net_returns.iloc[exit_idx] += final_gross - final_cost
        else:
            gross_returns.iloc[exit_idx] += gross_before_cost
            costs.iloc[exit_idx] += total_cost
            net_returns.iloc[exit_idx] += net_return
            if partial_enabled:
                turnover_events.iloc[entry_idx] += size
                turnover_events.iloc[exit_idx] += size
        _apply_mark_to_market_trade_path(
            mark_to_market_returns,
            closes=closes,
            entry_idx=entry_idx,
            exit_idx=exit_idx,
            entry_price=entry_open,
            exit_price=raw_exit_price,
            size=size,
            is_short=is_short,
            total_cost=total_cost,
        )
        if exit_idx > entry_idx:
            if partial_events:
                signed_size = -size if is_short else size
                remaining_position = signed_size
                segment_start = entry_idx
                for event in sorted(partial_events, key=lambda item: (int(item["exit_idx"]), int(item["rule_index"]))):
                    event_idx = int(event["exit_idx"])
                    if event_idx > segment_start:
                        positions.iloc[segment_start:event_idx] = remaining_position
                    remaining_position -= signed_size * float(event["fraction"])
                    segment_start = max(segment_start, event_idx)
                if exit_idx > segment_start:
                    positions.iloc[segment_start:exit_idx] = remaining_position
            else:
                positions.iloc[entry_idx:exit_idx] = -size if is_short else size

        trade_record = {
            "signal_timestamp": index[i],
            "entry_timestamp": index[entry_idx],
            "exit_timestamp": index[exit_idx],
            "side": "short" if is_short else "long",
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
            "max_favorable_r": float(path["max_favorable_r"]),
            "max_adverse_r": float(path["max_adverse_r"]),
            "breakeven_activated": bool(path["breakeven_activated"]),
            "profit_lock_activated": bool(path["profit_lock_activated"]),
            "effective_stop_price": float(path["effective_stop_price"]),
            "stop_mode": stop_mode,
        }
        if partial_events:
            partial_fraction_total = float(sum(float(event["fraction"]) for event in partial_events))
            remaining_fraction = max(1.0 - partial_fraction_total, 0.0)
            partial_trigger_rs = [float(event["trigger_r"]) for event in partial_events]
            partial_prices = [float(event["raw_exit_price"]) for event in partial_events]
            partial_bars = [int(event["exit_idx"]) - entry_idx + 1 for event in partial_events]
            trade_record.update(
                {
                    "partial_exit_count": int(len(partial_events)),
                    "partial_exit_fraction_total": partial_fraction_total,
                    "partial_exit_realized_r": float(partial_realized_r),
                    "partial_exit_avg_r": (
                        float(partial_realized_r / partial_fraction_total)
                        if partial_fraction_total > 0.0
                        else np.nan
                    ),
                    "remaining_fraction": float(remaining_fraction),
                    "partial_exit_trigger_rs": ",".join(str(value) for value in partial_trigger_rs),
                    "partial_exit_prices": ",".join(str(value) for value in partial_prices),
                    "partial_exit_bars": ",".join(str(value) for value in partial_bars),
                }
            )
        trades.append(trade_record)
        i = exit_idx + 1

    turnover = turnover_events if partial_enabled else (positions - positions.shift(1).fillna(0.0)).abs()
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
    mark_to_market_equity = (1.0 + mark_to_market_returns).cumprod()
    mark_to_market_equity.name = "mark_to_market_equity"
    mark_to_market_summary = compute_backtest_metrics(
        net_returns=mark_to_market_returns,
        periods_per_year=int(periods_per_year),
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
        mark_to_market_returns=mark_to_market_returns,
        mark_to_market_equity_curve=mark_to_market_equity,
        mark_to_market_summary=mark_to_market_summary,
    )


__all__ = ["run_manual_barrier_backtest"]
