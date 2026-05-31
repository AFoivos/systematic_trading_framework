from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics
from src.portfolio import PortfolioConstraints, PortfolioPerformance
from src.portfolio.construction import compute_weight_transition_accounting
from src.targets.directional_triple_barrier import resolve_directional_barrier_double_touch

_ALLOWED_ENTRY_PRICE_MODES = frozenset({"current_close", "next_open"})
_ALLOWED_TIE_BREAKS = frozenset({"closest_to_open", "profit", "stop"})


def _positive_float(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"portfolio_barrier {field} must be finite and > 0.")
    return out


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"portfolio_barrier {field} must be a positive integer.")
    out = int(value)
    if out <= 0 or float(out) != float(value):
        raise ValueError(f"portfolio_barrier {field} must be a positive integer.")
    return out


def _require_columns(frame: pd.DataFrame, *, asset: str, columns: list[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise KeyError(f"Missing required columns for portfolio_barrier asset '{asset}': {missing}")


def _prepare_asset_frames(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    required_columns: list[str],
) -> dict[str, pd.DataFrame]:
    if not asset_frames:
        raise ValueError("portfolio_barrier requires at least one asset frame.")

    out: dict[str, pd.DataFrame] = {}
    for asset, frame in sorted(asset_frames.items()):
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(f"portfolio_barrier asset '{asset}' must be a pandas DataFrame.")
        _require_columns(frame, asset=str(asset), columns=required_columns)
        prepared = frame.sort_index().copy()
        if prepared.index.has_duplicates:
            raise ValueError(f"portfolio_barrier asset '{asset}' has duplicate timestamps.")
        out[str(asset)] = prepared
    return out


def _align_signal_index(
    frames: Mapping[str, pd.DataFrame],
    *,
    signal_col: str,
    alignment: str,
) -> pd.DataFrame:
    if alignment not in {"inner", "outer"}:
        raise ValueError("portfolio_barrier alignment must be 'inner' or 'outer'.")
    signals = {
        asset: pd.to_numeric(frame[signal_col], errors="coerce").astype(float)
        for asset, frame in sorted(frames.items())
    }
    out = pd.concat(signals, axis=1, join=alignment).sort_index()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    out.columns = [str(column) for column in out.columns]
    return out


def _remap_to_next_aligned_timestamp(index: pd.Index, timestamp: Any) -> tuple[Any | None, bool]:
    if timestamp in index:
        return timestamp, False
    pos = int(index.searchsorted(timestamp, side="left"))
    if pos >= len(index):
        return None, False
    return index[pos], True


def _global_oos_mask(
    frames: Mapping[str, pd.DataFrame],
    *,
    index: pd.Index,
    pred_is_oos_col: str,
    alignment: str,
) -> pd.Series | None:
    oos_by_asset: dict[str, pd.Series] = {}
    for asset, frame in sorted(frames.items()):
        if pred_is_oos_col in frame.columns:
            oos_by_asset[asset] = frame[pred_is_oos_col].astype(float)
    if not oos_by_asset:
        return None
    oos_df = pd.concat(oos_by_asset, axis=1, join=alignment).sort_index()
    if isinstance(oos_df.columns, pd.MultiIndex):
        oos_df.columns = oos_df.columns.get_level_values(0)
    return oos_df.reindex(index).fillna(0.0).astype(bool).all(axis=1)


def _trade_weight(
    signal_value: float,
    *,
    constraints: PortfolioConstraints,
    gross_target: float,
    current_gross: float,
) -> float:
    side = float(np.sign(signal_value))
    if side == 0.0:
        return 0.0

    gross_cap = min(float(gross_target), float(constraints.max_gross_leverage))
    remaining_gross = max(gross_cap - float(current_gross), 0.0)
    if remaining_gross <= 1e-12:
        return 0.0

    side_cap = float(constraints.max_weight) if side > 0.0 else abs(float(constraints.min_weight))
    size = min(abs(float(signal_value)), max(side_cap, 0.0), remaining_gross)
    if size <= 1e-12:
        return 0.0
    return side * size


def _simulate_barrier_event(
    frame: pd.DataFrame,
    *,
    signal_idx: int,
    side: float,
    open_col: str,
    high_col: str,
    low_col: str,
    close_col: str,
    volatility_col: str,
    entry_price_mode: str,
    profit_barrier_r: float,
    stop_barrier_r: float,
    vertical_barrier_bars: int,
    tie_break: str,
    asset: str,
) -> dict[str, Any] | None:
    if signal_idx >= len(frame) - int(vertical_barrier_bars):
        return None

    entry_idx = signal_idx if entry_price_mode == "current_close" else signal_idx + 1
    if entry_idx >= len(frame):
        return None

    opens = pd.to_numeric(frame[open_col], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(frame[high_col], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(frame[low_col], errors="coerce").to_numpy(dtype=float)
    closes = pd.to_numeric(frame[close_col], errors="coerce").to_numpy(dtype=float)
    volatility = pd.to_numeric(frame[volatility_col], errors="coerce").to_numpy(dtype=float)

    entry_price = float(closes[signal_idx] if entry_price_mode == "current_close" else opens[entry_idx])
    atr = float(volatility[signal_idx])
    if not np.isfinite(entry_price) or entry_price <= 0.0:
        raise ValueError(f"portfolio_barrier asset '{asset}' has invalid entry price at signal index {signal_idx}.")
    if not np.isfinite(atr) or atr <= 0.0:
        raise ValueError(f"portfolio_barrier asset '{asset}' has invalid {volatility_col} at signal index {signal_idx}.")

    risk_distance = float(stop_barrier_r * atr)
    profit_distance = float(profit_barrier_r * atr)
    if side > 0.0:
        profit_level = entry_price + profit_distance
        stop_level = entry_price - risk_distance
    else:
        profit_level = entry_price - profit_distance
        stop_level = entry_price + risk_distance

    chosen_type: str | None = None
    chosen_idx: int | None = None
    exit_price: float | None = None
    horizon_end = min(len(frame), signal_idx + int(vertical_barrier_bars) + 1)

    for step_idx in range(signal_idx + 1, horizon_end):
        if side > 0.0:
            hit_profit = bool(highs[step_idx] >= profit_level)
            hit_stop = bool(lows[step_idx] <= stop_level)
        else:
            hit_profit = bool(lows[step_idx] <= profit_level)
            hit_stop = bool(highs[step_idx] >= stop_level)

        if hit_profit and hit_stop:
            chosen_type = resolve_directional_barrier_double_touch(
                bar_open=float(opens[step_idx]),
                profit_level=profit_level,
                stop_level=stop_level,
                tie_break=tie_break,
            )
        elif hit_profit:
            chosen_type = "profit"
        elif hit_stop:
            chosen_type = "stop"

        if chosen_type is not None:
            chosen_idx = step_idx
            exit_price = profit_level if chosen_type == "profit" else stop_level
            break

    if chosen_type is None:
        chosen_idx = horizon_end - 1
        exit_price = float(closes[chosen_idx])
        chosen_type = "neutral"

    assert chosen_idx is not None
    assert exit_price is not None
    return {
        "signal_idx": int(signal_idx),
        "entry_idx": int(entry_idx),
        "exit_idx": int(chosen_idx),
        "signal_time": frame.index[signal_idx],
        "entry_time": frame.index[entry_idx],
        "exit_time": frame.index[chosen_idx],
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "atr": float(atr),
        "risk_distance": float(risk_distance),
        "take_profit_price": float(profit_level),
        "stop_loss_price": float(stop_level),
        "hit_type": chosen_type,
        "exit_reason": (
            "take_profit"
            if chosen_type == "profit"
            else "stop_loss"
            if chosen_type == "stop"
            else "vertical"
        ),
        "bars_held": int(chosen_idx - signal_idx),
    }


def _realized_trade_pnl(
    *,
    side: float,
    weight: float,
    entry_price: float,
    exit_price: float,
    risk_distance: float,
    cost_per_turnover: float,
    slippage_per_turnover: float,
) -> dict[str, float]:
    size = abs(float(weight))
    slip = float(slippage_per_turnover)
    if side > 0.0:
        entry_after_slippage = entry_price * (1.0 + slip)
        exit_after_slippage = exit_price * (1.0 - slip)
        gross_return = size * (exit_price / entry_price - 1.0)
        gross_after_slippage = size * (exit_after_slippage / entry_after_slippage - 1.0)
    else:
        entry_after_slippage = entry_price * (1.0 - slip)
        exit_after_slippage = exit_price * (1.0 + slip)
        gross_return = size * (1.0 - exit_price / entry_price)
        gross_after_slippage = size * (1.0 - exit_after_slippage / entry_after_slippage)

    slippage_cost = max(float(gross_return - gross_after_slippage), 0.0)
    fixed_cost = size * 2.0 * float(cost_per_turnover)
    total_cost = fixed_cost + slippage_cost
    net_return = gross_return - total_cost
    risk_capital = max(size * float(risk_distance) / float(entry_price), 1e-12)
    realized_r = net_return / risk_capital
    return {
        "gross_return": float(gross_return),
        "net_return": float(net_return),
        "cost": float(total_cost),
        "fixed_cost": float(fixed_cost),
        "slippage": float(slippage_cost),
        "realized_r": float(realized_r),
    }


def run_portfolio_barrier_backtest(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    signal_col: str = "signal",
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    volatility_col: str = "atr_14",
    entry_price_mode: str = "next_open",
    profit_barrier_r: float = 1.4,
    stop_barrier_r: float = 1.0,
    vertical_barrier_bars: int = 4,
    tie_break: str = "closest_to_open",
    subset: str = "full",
    pred_is_oos_col: str = "pred_is_oos",
    alignment: str = "inner",
    constraints: PortfolioConstraints | None = None,
    gross_target: float = 1.0,
    cost_per_turnover: float = 0.0,
    slippage_per_turnover: float = 0.0,
    periods_per_year: int = 252,
) -> tuple[PortfolioPerformance, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """
    Event-based multi-asset portfolio backtest using directional triple-barrier exits.

    Signals are read at bar ``t``. With ``entry_price_mode="next_open"``, entry is at the
    next bar open, and exit scanning follows the same horizon semantics as
    ``directional_triple_barrier``: bars ``t+1`` through ``t+vertical_barrier_bars`` are
    inspected for TP/SL, otherwise the trade exits at the vertical bar close.
    """
    signal_col = str(signal_col)
    open_col = str(open_col)
    high_col = str(high_col)
    low_col = str(low_col)
    close_col = str(close_col)
    volatility_col = str(volatility_col)
    entry_price_mode = str(entry_price_mode)
    tie_break = str(tie_break)
    subset = str(subset)
    if entry_price_mode not in _ALLOWED_ENTRY_PRICE_MODES:
        raise ValueError("portfolio_barrier entry_price_mode must be one of: current_close, next_open.")
    if tie_break not in _ALLOWED_TIE_BREAKS:
        raise ValueError("portfolio_barrier tie_break must be one of: closest_to_open, profit, stop.")
    if subset not in {"full", "test"}:
        raise ValueError("portfolio_barrier subset must be 'full' or 'test'.")

    profit_barrier_r = _positive_float(profit_barrier_r, field="profit_barrier_r")
    stop_barrier_r = _positive_float(stop_barrier_r, field="stop_barrier_r")
    vertical_barrier_bars = _positive_int(vertical_barrier_bars, field="vertical_barrier_bars")
    cost_per_turnover = float(cost_per_turnover)
    slippage_per_turnover = float(slippage_per_turnover)
    if cost_per_turnover < 0.0 or slippage_per_turnover < 0.0:
        raise ValueError("portfolio_barrier costs and slippage must be >= 0.")

    required_columns = [signal_col, open_col, high_col, low_col, close_col, volatility_col]
    frames = _prepare_asset_frames(asset_frames, required_columns=required_columns)
    signals = _align_signal_index(frames, signal_col=signal_col, alignment=alignment)
    if signals.empty:
        raise ValueError("portfolio_barrier aligned signal frame is empty.")

    constraints = constraints or PortfolioConstraints()
    gross_target = _positive_float(gross_target, field="gross_target")
    oos_mask = (
        _global_oos_mask(frames, index=signals.index, pred_is_oos_col=pred_is_oos_col, alignment=alignment)
        if subset == "test"
        else None
    )

    weights = pd.DataFrame(0.0, index=signals.index, columns=signals.columns, dtype=float)
    gross_returns = pd.Series(0.0, index=signals.index, name="gross_returns", dtype=float)
    net_returns = pd.Series(0.0, index=signals.index, name="net_returns", dtype=float)
    costs = pd.Series(0.0, index=signals.index, name="costs", dtype=float)
    turnover = pd.Series(0.0, index=signals.index, name="turnover", dtype=float)

    active_by_asset: dict[str, dict[str, Any]] = {}
    trades: list[dict[str, Any]] = []
    skipped_no_capacity = 0
    skipped_tail = 0
    skipped_unalignable_timestamp = 0
    remapped_entry_timestamps = 0
    remapped_exit_timestamps = 0
    ignored_open_signals = 0

    for timestamp, signal_row in signals.iterrows():
        for asset, active in list(active_by_asset.items()):
            if active["exit_time"] <= timestamp:
                active_by_asset.pop(asset, None)

        if oos_mask is not None and not bool(oos_mask.loc[timestamp]):
            continue

        current_gross = float(sum(abs(float(active["weight"])) for active in active_by_asset.values()))
        for asset in sorted(frames):
            signal_value = signal_row.get(asset, np.nan)
            if not np.isfinite(signal_value) or float(signal_value) == 0.0:
                continue
            if asset in active_by_asset:
                ignored_open_signals += 1
                continue
            frame = frames[asset]
            if timestamp not in frame.index:
                continue
            side = float(np.sign(signal_value))
            weight = _trade_weight(
                float(signal_value),
                constraints=constraints,
                gross_target=gross_target,
                current_gross=current_gross,
            )
            if weight == 0.0:
                skipped_no_capacity += 1
                continue

            signal_idx = int(frame.index.get_loc(timestamp))
            event = _simulate_barrier_event(
                frame,
                signal_idx=signal_idx,
                side=side,
                open_col=open_col,
                high_col=high_col,
                low_col=low_col,
                close_col=close_col,
                volatility_col=volatility_col,
                entry_price_mode=entry_price_mode,
                profit_barrier_r=profit_barrier_r,
                stop_barrier_r=stop_barrier_r,
                vertical_barrier_bars=vertical_barrier_bars,
                tie_break=tie_break,
                asset=asset,
            )
            if event is None:
                skipped_tail += 1
                continue
            raw_entry_time = event["entry_time"]
            raw_exit_time = event["exit_time"]
            entry_time, entry_remapped = _remap_to_next_aligned_timestamp(weights.index, raw_entry_time)
            exit_time, exit_remapped = _remap_to_next_aligned_timestamp(weights.index, raw_exit_time)
            if entry_time is None or exit_time is None:
                skipped_unalignable_timestamp += 1
                continue
            remapped_entry_timestamps += int(entry_remapped)
            remapped_exit_timestamps += int(exit_remapped)

            pnl = _realized_trade_pnl(
                side=side,
                weight=weight,
                entry_price=float(event["entry_price"]),
                exit_price=float(event["exit_price"]),
                risk_distance=float(event["risk_distance"]),
                cost_per_turnover=cost_per_turnover,
                slippage_per_turnover=slippage_per_turnover,
            )
            gross_returns.loc[exit_time] += pnl["gross_return"]
            net_returns.loc[exit_time] += pnl["net_return"]
            costs.loc[exit_time] += pnl["cost"]
            turnover.loc[entry_time] += abs(weight)
            turnover.loc[exit_time] += abs(weight)

            active_index = weights.index[(weights.index >= entry_time) & (weights.index <= exit_time)]
            if len(active_index) > 0:
                weights.loc[active_index, asset] = weight

            active_by_asset[asset] = {"exit_time": exit_time, "weight": weight}
            current_gross += abs(weight)
            side_name = "long" if side > 0.0 else "short"
            trade = {
                "asset": asset,
                "signal_time": event["signal_time"],
                "signal_timestamp": event["signal_time"],
                "raw_signal_time": event["signal_time"],
                "entry_time": entry_time,
                "entry_timestamp": entry_time,
                "raw_entry_time": raw_entry_time,
                "raw_entry_timestamp": raw_entry_time,
                "entry_time_remapped": bool(entry_remapped),
                "exit_time": exit_time,
                "exit_timestamp": exit_time,
                "raw_exit_time": raw_exit_time,
                "raw_exit_timestamp": raw_exit_time,
                "exit_time_remapped": bool(exit_remapped),
                "side": side_name,
                "signal": float(signal_value),
                "position_weight": float(weight),
                "entry_price": float(event["entry_price"]),
                "exit_price": float(event["exit_price"]),
                "raw_entry_price": float(event["entry_price"]),
                "raw_exit_price": float(event["exit_price"]),
                "atr_at_entry": float(event["atr"]),
                "atr_at_signal": float(event["atr"]),
                "take_profit_price": float(event["take_profit_price"]),
                "target_price": float(event["take_profit_price"]),
                "stop_loss_price": float(event["stop_loss_price"]),
                "exit_reason": event["exit_reason"],
                "hit_type": event["hit_type"],
                "hit_step": int(event["bars_held"]),
                "bars_held": int(event["bars_held"]),
                "gross_return": pnl["gross_return"],
                "net_return": pnl["net_return"],
                "realized_r": pnl["realized_r"],
                "trade_r": pnl["realized_r"],
                "cost": pnl["cost"],
                "fixed_cost": pnl["fixed_cost"],
                "slippage": pnl["slippage"],
                "was_oos": bool(oos_mask.loc[timestamp]) if oos_mask is not None else True,
            }
            trades.append(trade)

    equity_curve = (1.0 + net_returns).cumprod()
    equity_curve.name = "equity"
    summary = compute_backtest_metrics(
        net_returns=net_returns,
        periods_per_year=int(periods_per_year),
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        trades_df = pd.DataFrame(
            columns=[
                "asset",
                "signal_time",
                "entry_time",
                "exit_time",
                "raw_entry_time",
                "raw_exit_time",
                "entry_time_remapped",
                "exit_time_remapped",
                "side",
                "entry_price",
                "exit_price",
                "atr_at_entry",
                "take_profit_price",
                "stop_loss_price",
                "exit_reason",
                "bars_held",
                "gross_return",
                "net_return",
                "realized_r",
                "cost",
                "slippage",
                "was_oos",
            ]
        )
    else:
        trade_r = pd.to_numeric(trades_df["realized_r"], errors="coerce").dropna().astype(float)
        summary["trade_count"] = float(len(trades_df))
        summary["average_r"] = float(trade_r.mean()) if not trade_r.empty else np.nan
        summary["median_r"] = float(trade_r.median()) if not trade_r.empty else np.nan
        summary["win_rate"] = float((trade_r > 0.0).mean()) if not trade_r.empty else np.nan
    summary.update(compute_weight_transition_accounting(weights, barrier_trade_count=len(trades_df)))

    diagnostics = pd.DataFrame(
        {
            "net_exposure": weights.sum(axis=1).astype(float),
            "gross_exposure": weights.abs().sum(axis=1).astype(float),
            "turnover": turnover.astype(float),
            "open_trade_count": weights.ne(0.0).sum(axis=1).astype(float),
        },
        index=weights.index,
    )

    performance = PortfolioPerformance(
        equity_curve=equity_curve,
        net_returns=net_returns,
        gross_returns=gross_returns,
        costs=costs,
        turnover=turnover,
        summary=summary,
        applied_weights=weights,
        risk_guard_summary={"enabled": False},
        risk_guard_timeline=pd.DataFrame(index=weights.index),
        trades=trades_df,
    )
    meta = {
        "engine": "portfolio_barrier",
        "entry_price_mode": entry_price_mode,
        "profit_barrier_r": float(profit_barrier_r),
        "stop_barrier_r": float(stop_barrier_r),
        "vertical_barrier_bars": int(vertical_barrier_bars),
        "volatility_col": volatility_col,
        "tie_break": tie_break,
        "trade_count": int(len(trades_df)),
        "skipped_no_capacity": int(skipped_no_capacity),
        "skipped_tail": int(skipped_tail),
        "skipped_unalignable_timestamp": int(skipped_unalignable_timestamp),
        "remapped_entry_timestamps": int(remapped_entry_timestamps),
        "remapped_exit_timestamps": int(remapped_exit_timestamps),
        "ignored_open_signals": int(ignored_open_signals),
        "oos_filtered": bool(oos_mask is not None),
    }
    return performance, weights, diagnostics, meta


__all__ = ["run_portfolio_barrier_backtest"]
