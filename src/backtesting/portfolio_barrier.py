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
_ALLOWED_EVENT_TIME_REMAP_POLICIES = frozenset({"next_aligned", "skip"})


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


def _positive_int_or_none(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, field=field)


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
    remaining_group_gross: float | None = None,
) -> float:
    side = float(np.sign(signal_value))
    if side == 0.0:
        return 0.0

    gross_cap = min(float(gross_target), float(constraints.max_gross_leverage))
    remaining_gross = max(gross_cap - float(current_gross), 0.0)
    if remaining_group_gross is not None:
        remaining_gross = min(remaining_gross, max(float(remaining_group_gross), 0.0))
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
    vertical_barrier_bars: int | None,
    tie_break: str,
    asset: str,
) -> dict[str, Any] | None:
    if vertical_barrier_bars is not None and signal_idx >= len(frame) - int(vertical_barrier_bars):
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
    horizon_end = (
        len(frame)
        if vertical_barrier_bars is None
        else min(len(frame), signal_idx + int(vertical_barrier_bars) + 1)
    )

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
        chosen_type = "end_of_data" if vertical_barrier_bars is None else "neutral"

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
            else "end_of_data_close"
            if chosen_type == "end_of_data"
            else "vertical"
        ),
        "bars_held": int(chosen_idx - signal_idx),
    }


def _apply_mark_to_market_trade_path(
    mark_to_market_returns: pd.Series,
    *,
    frame: pd.DataFrame,
    aligned_index: pd.Index,
    close_col: str,
    entry_time: Any,
    exit_time: Any,
    entry_price: float,
    exit_price: float,
    weight: float,
    side: float,
    total_cost: float,
) -> None:
    active_index = aligned_index[(aligned_index >= entry_time) & (aligned_index <= exit_time)]
    if len(active_index) == 0:
        return
    closes = pd.to_numeric(frame[close_col], errors="coerce").reindex(active_index).ffill()
    previous_price = float(entry_price)
    for ts in active_index:
        mark_price = float(exit_price) if ts == exit_time else float(closes.loc[ts])
        if not np.isfinite(mark_price) or mark_price <= 0.0 or previous_price <= 0.0:
            previous_price = mark_price
            continue
        if side > 0.0:
            gross_return = abs(float(weight)) * (mark_price / previous_price - 1.0)
        else:
            gross_return = abs(float(weight)) * (1.0 - mark_price / previous_price)
        cost = float(total_cost) if ts == exit_time else 0.0
        mark_to_market_returns.loc[ts] += gross_return - cost
        previous_price = mark_price


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


def _estimated_roundtrip_cost_filter_stats(
    *,
    weight: float,
    entry_price: float,
    risk_distance: float,
    cost_per_turnover: float,
    slippage_per_turnover: float,
) -> dict[str, float]:
    size = abs(float(weight))
    risk_fraction = float(risk_distance) / float(entry_price)
    fixed_cost = size * 2.0 * float(cost_per_turnover)
    estimated_slippage = size * 2.0 * float(slippage_per_turnover)
    estimated_total_cost = fixed_cost + estimated_slippage
    risk_capital = size * max(risk_fraction, 1e-12)
    return {
        "risk_fraction": float(risk_fraction),
        "estimated_cost": float(estimated_total_cost),
        "estimated_cost_r": float(estimated_total_cost / max(risk_capital, 1e-12)),
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
    vertical_barrier_bars: int | None = 4,
    tie_break: str = "closest_to_open",
    subset: str = "full",
    pred_is_oos_col: str = "pred_is_oos",
    alignment: str = "inner",
    constraints: PortfolioConstraints | None = None,
    gross_target: float = 1.0,
    cost_per_turnover: float = 0.0,
    slippage_per_turnover: float = 0.0,
    periods_per_year: int = 252,
    asset_params: Mapping[str, Mapping[str, Any]] | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    portfolio_guard: Mapping[str, Any] | None = None,
    event_time_remap_policy: str = "next_aligned",
    max_cost_r: float | None = None,
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
    event_time_remap_policy = str(event_time_remap_policy)
    if entry_price_mode not in _ALLOWED_ENTRY_PRICE_MODES:
        raise ValueError("portfolio_barrier entry_price_mode must be one of: current_close, next_open.")
    if tie_break not in _ALLOWED_TIE_BREAKS:
        raise ValueError("portfolio_barrier tie_break must be one of: closest_to_open, profit, stop.")
    if subset not in {"full", "test"}:
        raise ValueError("portfolio_barrier subset must be 'full' or 'test'.")
    if event_time_remap_policy not in _ALLOWED_EVENT_TIME_REMAP_POLICIES:
        raise ValueError("portfolio_barrier event_time_remap_policy must be 'next_aligned' or 'skip'.")

    profit_barrier_r = _positive_float(profit_barrier_r, field="profit_barrier_r")
    stop_barrier_r = _positive_float(stop_barrier_r, field="stop_barrier_r")
    vertical_barrier_bars = _positive_int_or_none(vertical_barrier_bars, field="vertical_barrier_bars")
    cost_per_turnover = float(cost_per_turnover)
    slippage_per_turnover = float(slippage_per_turnover)
    if cost_per_turnover < 0.0 or slippage_per_turnover < 0.0:
        raise ValueError("portfolio_barrier costs and slippage must be >= 0.")
    if max_cost_r is not None:
        max_cost_r = _positive_float(max_cost_r, field="max_cost_r")

    asset_params_by_asset = {str(k): dict(v or {}) for k, v in dict(asset_params or {}).items()}
    asset_groups = {str(k): str(v) for k, v in dict(asset_to_group or {}).items()}
    guard_cfg = dict(portfolio_guard or {})
    guard_enabled = bool(guard_cfg.get("enabled", False))
    max_open_trades = guard_cfg.get("max_open_trades")
    if max_open_trades is not None:
        max_open_trades = _positive_int(max_open_trades, field="portfolio_guard.max_open_trades")
    raw_group_max_open = dict(guard_cfg.get("group_max_open_trades", {}) or {})
    group_max_open_trades = {str(group): _positive_int(value, field=f"portfolio_guard.group_max_open_trades.{group}") for group, value in raw_group_max_open.items()}
    kill_switch_drawdown = guard_cfg.get("kill_switch_max_drawdown", guard_cfg.get("max_drawdown"))
    if kill_switch_drawdown is not None:
        kill_switch_drawdown = _positive_float(kill_switch_drawdown, field="portfolio_guard.kill_switch_max_drawdown")
    max_daily_loss = guard_cfg.get("max_daily_loss_pct")
    if max_daily_loss is not None:
        max_daily_loss = _positive_float(max_daily_loss, field="portfolio_guard.max_daily_loss_pct")
    disable_weekend_trading = bool(guard_cfg.get("disable_weekend_trading", False))
    guard_equity_source = str(guard_cfg.get("equity_source", "realized"))
    if guard_equity_source not in {"realized", "mark_to_market"}:
        raise ValueError(
            "portfolio_barrier portfolio_guard.equity_source must be 'realized' or 'mark_to_market'."
        )

    required_columns = [signal_col, open_col, high_col, low_col, close_col]
    frames = _prepare_asset_frames(asset_frames, required_columns=required_columns)
    for asset, frame in frames.items():
        params = dict(asset_params_by_asset.get(asset, {}) or {})
        asset_volatility_col = str(params.get("volatility_col", params.get("vol_col", volatility_col)))
        asset_required_columns = [asset_volatility_col]
        if params.get("max_spread_points") is not None:
            asset_required_columns.extend(
                [
                    str(params.get("spread_bid_col", "bid_open")),
                    str(params.get("spread_ask_col", "ask_open")),
                ]
            )
            _positive_float(params.get("point_size"), field=f"asset_params.{asset}.point_size")
            _positive_float(
                params.get("max_spread_points"),
                field=f"asset_params.{asset}.max_spread_points",
            )
        _require_columns(frame, asset=asset, columns=asset_required_columns)
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
    mark_to_market_returns = pd.Series(0.0, index=signals.index, name="mark_to_market_returns", dtype=float)

    active_by_asset: dict[str, dict[str, Any]] = {}
    trades: list[dict[str, Any]] = []
    skipped_no_capacity = 0
    skipped_tail = 0
    skipped_unalignable_timestamp = 0
    skipped_cost_filter = 0
    skipped_remapped_event_timestamps = 0
    skipped_remapped_entry_timestamps = 0
    skipped_remapped_exit_timestamps = 0
    remapped_entry_timestamps = 0
    remapped_exit_timestamps = 0
    ignored_open_signals = 0
    skipped_max_open_trades = 0
    skipped_group_max_open_trades = 0
    skipped_group_cap = 0
    skipped_guard = 0
    skipped_daily_loss = 0
    skipped_weekend = 0
    skipped_spread_filter = 0
    skipped_invalid_spread = 0
    risk_sized_trade_count = 0
    guard_equity = 1.0
    guard_peak_equity = 1.0
    guard_daily_start_equity = 1.0
    guard_daily_date: Any | None = None
    guard_daily_blocked_date: Any | None = None
    guard_permanent_flat = False
    guard_trigger_count = 0
    daily_loss_trigger_count = 0

    for timestamp, signal_row in signals.iterrows():
        timestamp_date = pd.Timestamp(timestamp).date()
        if guard_daily_date != timestamp_date:
            guard_daily_date = timestamp_date
            guard_daily_start_equity = guard_equity
            guard_daily_blocked_date = None
        if timestamp in net_returns.index:
            guard_return = (
                float(mark_to_market_returns.loc[timestamp])
                if guard_equity_source == "mark_to_market"
                else float(net_returns.loc[timestamp])
            )
            guard_equity *= 1.0 + guard_return
            guard_peak_equity = max(guard_peak_equity, guard_equity)
            guard_drawdown = float(guard_equity / guard_peak_equity - 1.0) if guard_peak_equity > 0.0 else 0.0
            if (
                guard_enabled
                and kill_switch_drawdown is not None
                and not guard_permanent_flat
                and guard_drawdown <= -float(kill_switch_drawdown)
            ):
                guard_permanent_flat = True
                guard_trigger_count += 1
            daily_loss = (
                float((guard_daily_start_equity - guard_equity) / guard_daily_start_equity)
                if guard_daily_start_equity > 0.0
                else 0.0
            )
            if (
                guard_enabled
                and max_daily_loss is not None
                and guard_daily_blocked_date is None
                and daily_loss >= float(max_daily_loss)
            ):
                guard_daily_blocked_date = timestamp_date
                daily_loss_trigger_count += 1

        for asset, active in list(active_by_asset.items()):
            if active["exit_time"] <= timestamp:
                active_by_asset.pop(asset, None)

        if oos_mask is not None and not bool(oos_mask.loc[timestamp]):
            continue
        if guard_permanent_flat:
            skipped_guard += int(signal_row.fillna(0.0).astype(float).ne(0.0).sum())
            continue
        if guard_daily_blocked_date == timestamp_date:
            skipped_daily_loss += int(signal_row.fillna(0.0).astype(float).ne(0.0).sum())
            continue
        if disable_weekend_trading and pd.Timestamp(timestamp).weekday() >= 5:
            skipped_weekend += int(signal_row.fillna(0.0).astype(float).ne(0.0).sum())
            continue

        current_gross = float(sum(abs(float(active["weight"])) for active in active_by_asset.values()))
        for asset in sorted(frames):
            signal_value = signal_row.get(asset, np.nan)
            if not np.isfinite(signal_value) or float(signal_value) == 0.0:
                continue
            if asset in active_by_asset:
                ignored_open_signals += 1
                continue
            if max_open_trades is not None and len(active_by_asset) >= int(max_open_trades):
                skipped_max_open_trades += 1
                continue
            group = asset_groups.get(asset)
            if group is not None and group_max_open_trades.get(group) is not None:
                current_group_open = sum(
                    1
                    for active_asset in active_by_asset
                    if asset_groups.get(active_asset) == group
                )
                if current_group_open >= int(group_max_open_trades[group]):
                    skipped_group_max_open_trades += 1
                    continue
            frame = frames[asset]
            if timestamp not in frame.index:
                continue
            side = float(np.sign(signal_value))
            remaining_group_gross = None
            if group is not None and constraints.group_max_exposure and group in constraints.group_max_exposure:
                current_group_gross = sum(
                    abs(float(active["weight"]))
                    for active_asset, active in active_by_asset.items()
                    if asset_groups.get(active_asset) == group
                )
                remaining_group_gross = float(constraints.group_max_exposure[group]) - float(current_group_gross)
            weight = _trade_weight(
                float(signal_value),
                constraints=constraints,
                gross_target=gross_target,
                current_gross=current_gross,
                remaining_group_gross=remaining_group_gross,
            )
            if weight == 0.0:
                if remaining_group_gross is not None and remaining_group_gross <= 1e-12:
                    skipped_group_cap += 1
                else:
                    skipped_no_capacity += 1
                continue

            signal_idx = int(frame.index.get_loc(timestamp))
            params = dict(asset_params_by_asset.get(asset, {}) or {})
            asset_profit_barrier_r = float(params.get("profit_barrier_r", params.get("take_profit_r", profit_barrier_r)))
            asset_stop_barrier_r = float(params.get("stop_barrier_r", params.get("stop_loss_r", stop_barrier_r)))
            asset_vertical_barrier_bars = _positive_int_or_none(
                params.get("vertical_barrier_bars", vertical_barrier_bars),
                field=f"asset_params.{asset}.vertical_barrier_bars",
            )
            asset_volatility_col = str(params.get("volatility_col", params.get("vol_col", volatility_col)))
            event = _simulate_barrier_event(
                frame,
                signal_idx=signal_idx,
                side=side,
                open_col=open_col,
                high_col=high_col,
                low_col=low_col,
                close_col=close_col,
                volatility_col=asset_volatility_col,
                entry_price_mode=entry_price_mode,
                profit_barrier_r=asset_profit_barrier_r,
                stop_barrier_r=asset_stop_barrier_r,
                vertical_barrier_bars=asset_vertical_barrier_bars,
                tie_break=tie_break,
                asset=asset,
            )
            if event is None:
                skipped_tail += 1
                continue
            asset_max_spread_raw = params.get("max_spread_points")
            spread_points: float | None = None
            asset_max_spread: float | None = None
            if asset_max_spread_raw is not None:
                asset_max_spread = _positive_float(
                    asset_max_spread_raw,
                    field=f"asset_params.{asset}.max_spread_points",
                )
                point_size = _positive_float(
                    params.get("point_size"),
                    field=f"asset_params.{asset}.point_size",
                )
                bid_col = str(params.get("spread_bid_col", "bid_open"))
                ask_col = str(params.get("spread_ask_col", "ask_open"))
                entry_row = frame.iloc[int(event["entry_idx"])]
                bid = float(pd.to_numeric(pd.Series([entry_row[bid_col]]), errors="coerce").iloc[0])
                ask = float(pd.to_numeric(pd.Series([entry_row[ask_col]]), errors="coerce").iloc[0])
                if not np.isfinite(bid) or not np.isfinite(ask) or ask < bid:
                    skipped_invalid_spread += 1
                    continue
                spread_points = float((ask - bid) / point_size)
                if spread_points > asset_max_spread:
                    skipped_spread_filter += 1
                    continue
            raw_entry_time = event["entry_time"]
            raw_exit_time = event["exit_time"]
            entry_time, entry_remapped = _remap_to_next_aligned_timestamp(weights.index, raw_entry_time)
            exit_time, exit_remapped = _remap_to_next_aligned_timestamp(weights.index, raw_exit_time)
            if entry_time is None or exit_time is None:
                skipped_unalignable_timestamp += 1
                continue
            if event_time_remap_policy == "skip" and (entry_remapped or exit_remapped):
                skipped_remapped_event_timestamps += 1
                skipped_remapped_entry_timestamps += int(entry_remapped)
                skipped_remapped_exit_timestamps += int(exit_remapped)
                continue
            remapped_entry_timestamps += int(entry_remapped)
            remapped_exit_timestamps += int(exit_remapped)

            risk_per_trade = params.get("risk_per_trade")
            if risk_per_trade is not None:
                risk_fraction = max(float(event["risk_distance"]) / float(event["entry_price"]), 1e-12)
                risk_sized_cap = float(risk_per_trade) / risk_fraction
                sized_abs_weight = min(abs(float(weight)), risk_sized_cap)
                if sized_abs_weight <= 1e-12:
                    skipped_no_capacity += 1
                    continue
                if sized_abs_weight < abs(float(weight)) - 1e-12:
                    risk_sized_trade_count += 1
                weight = float(np.sign(weight)) * sized_abs_weight

            asset_max_cost_r_raw = params.get("max_cost_r", max_cost_r)
            asset_max_cost_r = (
                None
                if asset_max_cost_r_raw is None
                else _positive_float(asset_max_cost_r_raw, field=f"asset_params.{asset}.max_cost_r")
            )
            cost_filter_stats = _estimated_roundtrip_cost_filter_stats(
                weight=weight,
                entry_price=float(event["entry_price"]),
                risk_distance=float(event["risk_distance"]),
                cost_per_turnover=cost_per_turnover,
                slippage_per_turnover=slippage_per_turnover,
            )
            if asset_max_cost_r is not None and cost_filter_stats["estimated_cost_r"] > float(asset_max_cost_r):
                skipped_cost_filter += 1
                continue

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
            _apply_mark_to_market_trade_path(
                mark_to_market_returns,
                frame=frame,
                aligned_index=weights.index,
                close_col=close_col,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=float(event["entry_price"]),
                exit_price=float(event["exit_price"]),
                weight=weight,
                side=side,
                total_cost=float(pnl["cost"]),
            )

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
                "volatility_col": asset_volatility_col,
                "profit_barrier_r": asset_profit_barrier_r,
                "stop_barrier_r": asset_stop_barrier_r,
                "vertical_barrier_bars": asset_vertical_barrier_bars,
                "risk_per_trade": risk_per_trade,
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
                "risk_fraction": cost_filter_stats["risk_fraction"],
                "estimated_cost": cost_filter_stats["estimated_cost"],
                "estimated_cost_r": cost_filter_stats["estimated_cost_r"],
                "max_cost_r": asset_max_cost_r,
                "spread_points": spread_points,
                "max_spread_points": asset_max_spread,
                "cost": pnl["cost"],
                "fixed_cost": pnl["fixed_cost"],
                "slippage": pnl["slippage"],
                "was_oos": bool(oos_mask.loc[timestamp]) if oos_mask is not None else True,
            }
            trades.append(trade)

    equity_curve = (1.0 + net_returns).cumprod()
    equity_curve.name = "equity"
    mark_to_market_equity = (1.0 + mark_to_market_returns).cumprod()
    mark_to_market_equity.name = "mark_to_market_equity"
    summary = compute_backtest_metrics(
        net_returns=net_returns,
        periods_per_year=int(periods_per_year),
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )
    mark_to_market_summary = compute_backtest_metrics(
        net_returns=mark_to_market_returns,
        periods_per_year=int(periods_per_year),
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
                "risk_fraction",
                "estimated_cost",
                "estimated_cost_r",
                "max_cost_r",
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
        risk_guard_summary={
            "enabled": bool(guard_enabled),
            "kill_switch_max_drawdown": kill_switch_drawdown,
            "kill_switch_trigger_count": int(guard_trigger_count),
            "permanent_flattened": bool(guard_permanent_flat),
            "skipped_guard": int(skipped_guard),
            "max_open_trades": max_open_trades,
            "skipped_max_open_trades": int(skipped_max_open_trades),
            "group_max_open_trades": dict(group_max_open_trades),
            "skipped_group_max_open_trades": int(skipped_group_max_open_trades),
            "skipped_group_cap": int(skipped_group_cap),
            "max_daily_loss_pct": max_daily_loss,
            "daily_loss_trigger_count": int(daily_loss_trigger_count),
            "skipped_daily_loss": int(skipped_daily_loss),
            "disable_weekend_trading": disable_weekend_trading,
            "skipped_weekend": int(skipped_weekend),
            "equity_source": guard_equity_source,
            "skipped_spread_filter": int(skipped_spread_filter),
            "skipped_invalid_spread": int(skipped_invalid_spread),
        },
        risk_guard_timeline=pd.DataFrame(index=weights.index),
        trades=trades_df,
        mark_to_market_returns=mark_to_market_returns,
        mark_to_market_equity_curve=mark_to_market_equity,
        mark_to_market_summary=mark_to_market_summary,
    )
    meta = {
        "engine": "portfolio_barrier",
        "entry_price_mode": entry_price_mode,
        "profit_barrier_r": float(profit_barrier_r),
        "stop_barrier_r": float(stop_barrier_r),
        "vertical_barrier_bars": None if vertical_barrier_bars is None else int(vertical_barrier_bars),
        "volatility_col": volatility_col,
        "tie_break": tie_break,
        "event_time_remap_policy": event_time_remap_policy,
        "max_cost_r": max_cost_r,
        "asset_params": dict(asset_params_by_asset),
        "asset_groups": dict(asset_groups),
        "trade_count": int(len(trades_df)),
        "skipped_no_capacity": int(skipped_no_capacity),
        "skipped_tail": int(skipped_tail),
        "skipped_unalignable_timestamp": int(skipped_unalignable_timestamp),
        "skipped_cost_filter": int(skipped_cost_filter),
        "skipped_remapped_event_timestamps": int(skipped_remapped_event_timestamps),
        "skipped_remapped_entry_timestamps": int(skipped_remapped_entry_timestamps),
        "skipped_remapped_exit_timestamps": int(skipped_remapped_exit_timestamps),
        "skipped_max_open_trades": int(skipped_max_open_trades),
        "skipped_group_max_open_trades": int(skipped_group_max_open_trades),
        "skipped_group_cap": int(skipped_group_cap),
        "skipped_daily_loss": int(skipped_daily_loss),
        "skipped_weekend": int(skipped_weekend),
        "skipped_spread_filter": int(skipped_spread_filter),
        "skipped_invalid_spread": int(skipped_invalid_spread),
        "daily_loss_trigger_count": int(daily_loss_trigger_count),
        "risk_sized_trade_count": int(risk_sized_trade_count),
        "remapped_entry_timestamps": int(remapped_entry_timestamps),
        "remapped_exit_timestamps": int(remapped_exit_timestamps),
        "ignored_open_signals": int(ignored_open_signals),
        "oos_filtered": bool(oos_mask is not None),
    }
    return performance, weights, diagnostics, meta


__all__ = ["run_portfolio_barrier_backtest"]
