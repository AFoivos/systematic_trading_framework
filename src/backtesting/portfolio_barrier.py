from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import (
    compute_backtest_metrics,
    equity_curve_from_returns,
    hit_rate,
    profit_factor,
)
from src.portfolio import PortfolioConstraints, PortfolioPerformance
from src.portfolio.construction import compute_weight_transition_accounting
from src.targets.directional_triple_barrier import resolve_directional_barrier_double_touch
from src.utils.trade_path import compute_trade_pnl, simulate_strategy_path_trade_outcome

_ALLOWED_ENTRY_PRICE_MODES = frozenset({"current_close", "next_open"})
_ALLOWED_TIE_BREAKS = frozenset({"closest_to_open", "profit", "stop"})
_ALLOWED_EVENT_TIME_REMAP_POLICIES = frozenset({"next_aligned", "skip"})


def _validate_strategy_path_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    cfg = dict(config or {})
    if not cfg:
        return {"kind": "none", "enabled": False}
    kind = str(cfg.get("kind", "none"))
    if kind in {"", "none"}:
        return {"kind": "none", "enabled": False}
    if kind != "matb":
        raise ValueError("portfolio_barrier strategy_path.kind must be 'none' or 'matb'.")
    entry_price_mode = str(cfg.get("entry_price_mode", "next_open"))
    tie_break = str(cfg.get("tie_break", "closest_to_open"))
    if entry_price_mode != "next_open":
        raise ValueError("portfolio_barrier MATB strategy_path requires entry_price_mode='next_open'.")
    if tie_break != "closest_to_open":
        raise ValueError("portfolio_barrier MATB strategy_path requires tie_break='closest_to_open'.")
    entry_delay_bars = cfg.get("entry_delay_bars", 0)
    max_holding_bars = cfg.get("max_holding_bars", 1440)
    if isinstance(entry_delay_bars, bool) or int(entry_delay_bars) < 0:
        raise ValueError("portfolio_barrier strategy_path.entry_delay_bars must be >= 0.")
    if isinstance(max_holding_bars, bool) or int(max_holding_bars) <= 0:
        raise ValueError("portfolio_barrier strategy_path.max_holding_bars must be > 0.")
    trailing_activation_r = float(cfg.get("trailing_activation_r", 1.5))
    if not np.isfinite(trailing_activation_r) or trailing_activation_r < 0.0:
        raise ValueError(
            "portfolio_barrier strategy_path.trailing_activation_r must be finite and >= 0."
        )
    return {
        "kind": "matb",
        "enabled": True,
        "entry_price_mode": entry_price_mode,
        "entry_delay_bars": int(entry_delay_bars),
        "stop_loss_atr": _positive_float(
            cfg.get("stop_loss_atr", cfg.get("stop_loss_r", 2.0)),
            field="strategy_path.stop_loss_atr",
        ),
        "emergency_profit_r": _positive_float(
            cfg.get("emergency_profit_r", 8.0),
            field="strategy_path.emergency_profit_r",
        ),
        "trailing_activation_r": trailing_activation_r,
        "trailing_distance_atr": _positive_float(
            cfg.get("trailing_distance_atr", 2.5),
            field="strategy_path.trailing_distance_atr",
        ),
        "max_holding_bars": int(max_holding_bars),
        "tie_break": tie_break,
        "strict_bid_ask": bool(cfg.get("strict_bid_ask", True)),
        "allow_partial_horizon": bool(cfg.get("allow_partial_horizon", False)),
        "trend_score_col": str(cfg.get("trend_score_col", "matb_trend_score")),
        "bid_open_col": str(cfg.get("bid_open_col", "bid_open")),
        "bid_high_col": str(cfg.get("bid_high_col", "bid_high")),
        "bid_low_col": str(cfg.get("bid_low_col", "bid_low")),
        "bid_close_col": str(cfg.get("bid_close_col", "bid_close")),
        "ask_open_col": str(cfg.get("ask_open_col", "ask_open")),
        "ask_high_col": str(cfg.get("ask_high_col", "ask_high")),
        "ask_low_col": str(cfg.get("ask_low_col", "ask_low")),
        "ask_close_col": str(cfg.get("ask_close_col", "ask_close")),
    }


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
) -> pd.Series:
    oos_by_asset: dict[str, pd.Series] = {}
    missing_assets: list[str] = []
    for asset, frame in sorted(frames.items()):
        if pred_is_oos_col not in frame.columns:
            missing_assets.append(asset)
            continue
        raw = frame[pred_is_oos_col]
        invalid = raw.isna()
        if bool(invalid.any()):
            first_invalid = raw.index[invalid][0]
            raise ValueError(
                "portfolio_barrier subset='test' requires a non-missing "
                f"'{pred_is_oos_col}' flag for every row; asset '{asset}' is missing it "
                f"at {first_invalid!r}."
            )
        oos_by_asset[asset] = raw.astype(bool)
    if missing_assets:
        raise ValueError(
            "portfolio_barrier subset='test' requires "
            f"'{pred_is_oos_col}' for every asset; missing for {missing_assets}."
        )
    oos_df = pd.concat(oos_by_asset, axis=1, join=alignment).sort_index()
    if isinstance(oos_df.columns, pd.MultiIndex):
        oos_df.columns = oos_df.columns.get_level_values(0)
    aligned = oos_df.reindex(index)
    if bool(aligned.isna().any().any()):
        missing_rows = aligned.index[aligned.isna().any(axis=1)]
        raise ValueError(
            "portfolio_barrier subset='test' cannot prove OOS membership on the aligned "
            f"calendar; first incomplete timestamp is {missing_rows[0]!r}."
        )
    return aligned.astype(bool).all(axis=1)


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
    dynamic_exit: Mapping[str, Any] | None = None,
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

    dynamic_cfg = dict(dynamic_exit or {})
    dynamic_enabled = bool(dynamic_cfg.get("enabled", False))
    dynamic_exit_col = str(dynamic_cfg.get("exit_col", "")) if dynamic_enabled else ""
    dynamic_reason_col = str(dynamic_cfg.get("reason_col", "")) if dynamic_enabled else ""
    dynamic_flags = (
        frame[dynamic_exit_col].fillna(False).astype(bool).to_numpy()
        if dynamic_enabled and dynamic_exit_col in frame.columns
        else np.zeros(len(frame), dtype=bool)
    )
    dynamic_reasons = frame[dynamic_reason_col] if dynamic_enabled and dynamic_reason_col in frame.columns else None

    chosen_type: str | None = None
    chosen_idx: int | None = None
    exit_price: float | None = None
    dynamic_signal_idx: int | None = None
    dynamic_reason: str | None = None
    path_mfe = -np.inf
    path_mae = np.inf
    time_to_mfe = 0
    time_to_mae = 0
    horizon_end = (
        len(frame)
        if vertical_barrier_bars is None
        else min(len(frame), signal_idx + int(vertical_barrier_bars) + 1)
    )

    barrier_last_idx = horizon_end - 1
    # A dynamic exit detected on the final vertical-barrier close is allowed to execute at
    # the following *real* asset open.  No intrabar event is evaluated on that extra bar.
    scan_end = min(len(frame), barrier_last_idx + 2) if vertical_barrier_bars is not None else len(frame)
    scheduled_dynamic = False
    gap_exit = False
    for step_idx in range(signal_idx + 1, scan_end):
        if scheduled_dynamic:
            chosen_type = "dynamic"
            chosen_idx = step_idx
            exit_price = float(opens[step_idx])
            if not np.isfinite(exit_price) or exit_price <= 0.0:
                return None
            break
        bar_open = float(opens[step_idx])
        if not np.isfinite(bar_open) or bar_open <= 0.0:
            return None
        if side > 0.0:
            bar_mfe = (float(highs[step_idx]) - entry_price) / risk_distance
            bar_mae = (float(lows[step_idx]) - entry_price) / risk_distance
        else:
            bar_mfe = (entry_price - float(lows[step_idx])) / risk_distance
            bar_mae = (entry_price - float(highs[step_idx])) / risk_distance
        if np.isfinite(bar_mfe) and bar_mfe > path_mfe:
            path_mfe = float(bar_mfe)
            time_to_mfe = int(step_idx - signal_idx)
        if np.isfinite(bar_mae) and bar_mae < path_mae:
            path_mae = float(bar_mae)
            time_to_mae = int(step_idx - signal_idx)
        if side > 0.0:
            gap_type = (
                "stop"
                if bar_open <= stop_level
                else "profit"
                if bar_open >= profit_level
                else None
            )
        else:
            gap_type = (
                "stop"
                if bar_open >= stop_level
                else "profit"
                if bar_open <= profit_level
                else None
            )
        if gap_type is not None:
            chosen_type = gap_type
            chosen_idx = step_idx
            exit_price = bar_open
            gap_exit = True
            break
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
        if dynamic_enabled and bool(dynamic_flags[step_idx]) and step_idx + 1 < len(frame):
            scheduled_dynamic = True
            dynamic_signal_idx = step_idx
            if dynamic_reasons is not None and pd.notna(dynamic_reasons.iloc[step_idx]):
                dynamic_reason = str(dynamic_reasons.iloc[step_idx])
            else:
                dynamic_reason = "stale_context"
            continue
        if step_idx == barrier_last_idx:
            chosen_idx = step_idx
            exit_price = float(closes[step_idx])
            chosen_type = "end_of_data" if vertical_barrier_bars is None else "neutral"
            break

    if chosen_type is None:
        chosen_idx = barrier_last_idx
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
            else str(dynamic_reason or "stale_context")
            if chosen_type == "dynamic"
            else "end_of_data_close"
            if chosen_type == "end_of_data"
            else "vertical"
        ),
        "bars_held": int(chosen_idx - signal_idx),
        "max_favorable_r": float(path_mfe) if np.isfinite(path_mfe) else np.nan,
        "max_adverse_r": float(path_mae) if np.isfinite(path_mae) else np.nan,
        "time_to_mfe": int(time_to_mfe),
        "time_to_mae": int(time_to_mae),
        "dynamic_exit_signal_time": frame.index[dynamic_signal_idx] if dynamic_signal_idx is not None else pd.NaT,
        "dynamic_exit_execution_time": frame.index[chosen_idx] if chosen_type == "dynamic" else pd.NaT,
        "dynamic_exit_reason": dynamic_reason if chosen_type == "dynamic" else pd.NA,
        "exit_at_open": bool(gap_exit or chosen_type == "dynamic"),
        "gap_exit": bool(gap_exit),
    }


def _simulate_strategy_path_event(
    frame: pd.DataFrame,
    *,
    signal_idx: int,
    side: float,
    open_col: str,
    high_col: str,
    low_col: str,
    close_col: str,
    volatility_col: str,
    strategy_path: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Adapt the shared MATB simulator to the portfolio event contract."""
    cfg = dict(strategy_path)

    def _array(column: str) -> np.ndarray:
        return pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)

    quote_columns = {
        "bid_opens": str(cfg["bid_open_col"]),
        "bid_highs": str(cfg["bid_high_col"]),
        "bid_lows": str(cfg["bid_low_col"]),
        "bid_closes": str(cfg["bid_close_col"]),
        "ask_opens": str(cfg["ask_open_col"]),
        "ask_highs": str(cfg["ask_high_col"]),
        "ask_lows": str(cfg["ask_low_col"]),
        "ask_closes": str(cfg["ask_close_col"]),
    }
    quote_presence = {key: column in frame.columns for key, column in quote_columns.items()}
    if any(quote_presence.values()) and not all(quote_presence.values()) and bool(cfg["strict_bid_ask"]):
        missing = [quote_columns[key] for key, present in quote_presence.items() if not present]
        raise KeyError(f"portfolio_barrier MATB strict bid/ask execution is missing columns: {missing}")
    quotes = {
        key: _array(column) if all(quote_presence.values()) else None
        for key, column in quote_columns.items()
    }
    outcome = simulate_strategy_path_trade_outcome(
        opens=_array(open_col),
        highs=_array(high_col),
        lows=_array(low_col),
        closes=_array(close_col),
        volatility=_array(volatility_col),
        trend_score=_array(str(cfg["trend_score_col"])),
        signal_idx=int(signal_idx),
        side=side,
        entry_price_mode=str(cfg["entry_price_mode"]),
        entry_delay_bars=int(cfg["entry_delay_bars"]),
        stop_loss_atr=float(cfg["stop_loss_atr"]),
        emergency_profit_r=float(cfg["emergency_profit_r"]),
        trailing_activation_r=float(cfg["trailing_activation_r"]),
        trailing_distance_atr=float(cfg["trailing_distance_atr"]),
        max_holding_bars=int(cfg["max_holding_bars"]),
        tie_break=str(cfg["tie_break"]),
        strict_bid_ask=bool(cfg["strict_bid_ask"]),
        allow_partial_horizon=bool(cfg["allow_partial_horizon"]),
        **quotes,
    )
    if not bool(outcome["valid"]):
        return None
    entry_idx = int(outcome["entry_idx"])
    exit_idx = int(outcome["exit_idx"])
    return {
        "signal_idx": int(signal_idx),
        "entry_idx": entry_idx,
        "exit_idx": exit_idx,
        "signal_time": frame.index[signal_idx],
        "entry_time": frame.index[entry_idx],
        "exit_time": frame.index[exit_idx],
        "entry_price": float(outcome["entry_price"]),
        "exit_price": float(outcome["exit_price"]),
        "atr": float(_array(volatility_col)[signal_idx]),
        "risk_distance": float(outcome["risk_distance"]),
        "take_profit_price": float(outcome["emergency_profit_price"]),
        "stop_loss_price": float(outcome["initial_stop_price"]),
        "effective_stop_price": float(outcome["effective_stop_price"]),
        "hit_type": str(outcome["hit_type"]),
        "exit_reason": str(outcome["exit_reason"]),
        "bars_held": int(outcome["bars_held"]),
        "hit_step": int(outcome["hit_step"]),
        "max_favorable_r": float(outcome["max_favorable_r"]),
        "max_adverse_r": float(outcome["max_adverse_r"]),
        "time_to_mfe": int(outcome["time_to_mfe"]),
        "time_to_mae": int(outcome["time_to_mae"]),
        "dynamic_exit_signal_time": pd.NaT,
        "dynamic_exit_execution_time": pd.NaT,
        "dynamic_exit_reason": pd.NA,
        "exit_at_open": bool(outcome["exit_at_open"]),
        "gap_exit": bool(outcome["gap_exit"]),
        "execution_source": str(outcome["execution_source"]),
        "trailing_activated": bool(outcome["trailing_activated"]),
    }


def _mark_to_market_trade_path(
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
) -> pd.Series:
    contribution = pd.Series(0.0, index=aligned_index, dtype=float)
    active_index = aligned_index[(aligned_index >= entry_time) & (aligned_index <= exit_time)]
    if len(active_index) == 0:
        return contribution
    # Missing native bars remain missing.  This routine must not manufacture a mark or an
    # execution price by forward-filling an OHLC series onto another asset's timestamp.
    closes = pd.to_numeric(frame[close_col], errors="coerce").reindex(active_index)
    previous_price = float(entry_price)
    for ts in active_index:
        mark_price = float(exit_price) if ts == exit_time else float(closes.loc[ts])
        if not np.isfinite(mark_price) or mark_price <= 0.0 or previous_price <= 0.0:
            continue
        if side > 0.0:
            gross_return = abs(float(weight)) * (mark_price / previous_price - 1.0)
        else:
            gross_return = abs(float(weight)) * (1.0 - mark_price / previous_price)
        cost = float(total_cost) if ts == exit_time else 0.0
        contribution.loc[ts] += gross_return - cost
        previous_price = mark_price
    return contribution


def _apply_mark_to_market_trade_path(
    mark_to_market_returns: pd.Series,
    **kwargs: Any,
) -> pd.Series:
    contribution = _mark_to_market_trade_path(**kwargs)
    mark_to_market_returns.loc[contribution.index] += contribution
    return contribution


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
    shared = compute_trade_pnl(
        side=side,
        weight=weight,
        entry_price=entry_price,
        exit_price=exit_price,
        risk_distance=risk_distance,
        cost_per_unit_turnover=cost_per_turnover,
        slippage_per_unit_turnover=slippage_per_turnover,
    )
    return {
        "gross_return": float(shared["gross_return"]),
        "net_return": float(shared["net_return"]),
        "cost": float(shared["cost"]),
        "fixed_cost": float(shared["fixed_cost"]),
        "slippage": float(shared["slippage"]),
        "realized_r": float(shared["net_r"]),
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


def _spread_adjusted_execution_prices(
    frame: pd.DataFrame,
    *,
    event: Mapping[str, Any],
    side: float,
    entry_price_mode: str,
    bid_col: str,
    ask_col: str,
    point_size: float,
) -> dict[str, float]:
    entry_row = frame.iloc[int(event["entry_idx"])]
    exit_row = frame.iloc[int(event["exit_idx"])]

    def _quotes(row: pd.Series, *, label: str) -> tuple[float, float, float]:
        bid = float(pd.to_numeric(pd.Series([row[bid_col]]), errors="coerce").iloc[0])
        ask = float(pd.to_numeric(pd.Series([row[ask_col]]), errors="coerce").iloc[0])
        if not np.isfinite(bid) or not np.isfinite(ask) or bid <= 0.0 or ask < bid:
            raise ValueError(f"invalid {label} bid/ask quote")
        return bid, ask, float(ask - bid)

    entry_bid, entry_ask, entry_spread = _quotes(entry_row, label="entry")
    exit_bid, exit_ask, exit_spread = _quotes(exit_row, label="exit")
    raw_entry = float(event["entry_price"])
    raw_exit = float(event["exit_price"])

    if entry_price_mode == "next_open":
        entry_price = entry_ask if side > 0.0 else entry_bid
    else:
        entry_price = raw_entry + 0.5 * entry_spread if side > 0.0 else raw_entry - 0.5 * entry_spread

    if bool(event.get("exit_at_open", False)):
        exit_price = exit_bid if side > 0.0 else exit_ask
    else:
        exit_price = raw_exit - 0.5 * exit_spread if side > 0.0 else raw_exit + 0.5 * exit_spread
    if not np.isfinite(entry_price) or not np.isfinite(exit_price) or entry_price <= 0.0 or exit_price <= 0.0:
        raise ValueError("spread-adjusted execution price is invalid")

    return {
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "entry_spread_points": float(entry_spread / point_size),
        "exit_spread_points": float(exit_spread / point_size),
    }


def _resolve_dynamic_exit_for_trade(
    cfg: Mapping[str, Any], *, side: float, module: str | None
) -> dict[str, Any]:
    """Resolve side- and optional module-aware dynamic exit columns for one trade."""
    base = dict(cfg or {})
    if not bool(base.get("enabled", False)):
        return {"enabled": False}
    module_cfg = dict(dict(base.get("module_exit_columns", {}) or {}).get(str(module or ""), {}) or {})
    long_col = module_cfg.get("long_exit_col", base.get("long_exit_col"))
    short_col = module_cfg.get("short_exit_col", base.get("short_exit_col"))
    reason_col = (
        module_cfg.get("long_reason_col", module_cfg.get("reason_col", base.get("long_reason_col", base.get("reason_col"))))
        if side > 0.0
        else module_cfg.get("short_reason_col", module_cfg.get("reason_col", base.get("short_reason_col", base.get("reason_col"))))
    )
    return {
        "enabled": True,
        "exit_col": str(long_col if side > 0.0 else short_col),
        "reason_col": str(reason_col),
    }


def _validate_dynamic_exit_config(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    out = dict(cfg or {})
    if not out:
        return {"enabled": False}
    if not isinstance(out.get("enabled", False), bool):
        raise ValueError("portfolio_barrier dynamic_exit.enabled must be boolean.")
    if not bool(out.get("enabled", False)):
        return {"enabled": False}
    if str(out.get("execution", "next_open")) != "next_open":
        raise ValueError("portfolio_barrier dynamic_exit.execution currently supports only 'next_open'.")
    for key in ("long_exit_col", "short_exit_col"):
        if not isinstance(out.get(key), str) or not str(out[key]).strip():
            raise ValueError(f"portfolio_barrier dynamic_exit.{key} must be a non-empty string.")
    legacy_reason = out.get("reason_col")
    side_reasons = (out.get("long_reason_col"), out.get("short_reason_col"))
    if not (
        isinstance(legacy_reason, str) and legacy_reason.strip()
    ) and not all(isinstance(value, str) and value.strip() for value in side_reasons):
        raise ValueError(
            "portfolio_barrier dynamic_exit requires reason_col or both long_reason_col and short_reason_col."
        )
    for key in ("reason_col", "long_reason_col", "short_reason_col"):
        if key in out and (not isinstance(out[key], str) or not str(out[key]).strip()):
            raise ValueError(f"portfolio_barrier dynamic_exit.{key} must be a non-empty string.")
    module_exit_columns = out.get("module_exit_columns", {}) or {}
    if not isinstance(module_exit_columns, Mapping):
        raise ValueError("portfolio_barrier dynamic_exit.module_exit_columns must be a mapping.")
    for module, module_cfg in module_exit_columns.items():
        if not isinstance(module, str) or not module.strip() or not isinstance(module_cfg, Mapping):
            raise ValueError("portfolio_barrier dynamic_exit.module_exit_columns must map names to mappings.")
        for key in ("long_exit_col", "short_exit_col", "reason_col", "long_reason_col", "short_reason_col"):
            if key in module_cfg and (not isinstance(module_cfg[key], str) or not str(module_cfg[key]).strip()):
                raise ValueError(f"portfolio_barrier dynamic_exit.module_exit_columns.{module}.{key} must be a string.")
    return out


def _validate_correlation_guard_config(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    out = dict(cfg or {})
    if not out:
        return {"enabled": False}
    if not isinstance(out.get("enabled", False), bool):
        raise ValueError("portfolio_barrier correlation_guard.enabled must be boolean.")
    if not bool(out.get("enabled", False)):
        return {"enabled": False}
    returns_col = out.get("returns_col", "close_ret")
    if not isinstance(returns_col, str) or not returns_col.strip():
        raise ValueError("portfolio_barrier correlation_guard.returns_col must be a non-empty string.")
    window = _positive_int(out.get("window_bars", 960), field="correlation_guard.window_bars")
    minimum = _positive_int(out.get("minimum_observations", 240), field="correlation_guard.minimum_observations")
    if minimum > window:
        raise ValueError("portfolio_barrier correlation_guard.minimum_observations must be <= window_bars.")
    maximum = float(out.get("maximum_abs_correlation", 0.80))
    if not np.isfinite(maximum) or not 0.0 < maximum <= 1.0:
        raise ValueError("portfolio_barrier correlation_guard.maximum_abs_correlation must be in (0, 1].")
    if not isinstance(out.get("same_direction_only", True), bool):
        raise ValueError("portfolio_barrier correlation_guard.same_direction_only must be boolean.")
    if str(out.get("action", "reject")) != "reject":
        raise ValueError("portfolio_barrier correlation_guard.action currently supports only 'reject'.")
    out.update({"returns_col": returns_col, "window_bars": window, "minimum_observations": minimum, "maximum_abs_correlation": maximum})
    return out


def _evaluate_correlation_guard(
    frames: Mapping[str, pd.DataFrame],
    *,
    asset: str,
    timestamp: Any,
    side: float,
    active_by_asset: Mapping[str, Mapping[str, Any]],
    cfg: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare returns on timestamp intersection strictly before the candidate signal bar."""
    if not bool(cfg.get("enabled", False)):
        return {"passed": True, "max_correlation": np.nan, "rejected_against": pd.NA, "insufficient_history": False}
    returns_col = str(cfg["returns_col"])
    target_returns = pd.to_numeric(frames[asset][returns_col], errors="coerce")
    correlations: list[tuple[str, float]] = []
    insufficient = False
    for active_asset, active in sorted(active_by_asset.items()):
        if bool(cfg.get("same_direction_only", True)) and float(active.get("side", 0.0)) != float(side):
            continue
        active_returns = pd.to_numeric(frames[active_asset][returns_col], errors="coerce")
        pair = pd.concat(
            [target_returns.loc[target_returns.index < timestamp], active_returns.loc[active_returns.index < timestamp]],
            axis=1,
            join="inner",
        ).dropna().tail(int(cfg["window_bars"]))
        if len(pair) < int(cfg["minimum_observations"]):
            insufficient = True
            continue
        correlation = float(pair.iloc[:, 0].corr(pair.iloc[:, 1]))
        if np.isfinite(correlation):
            correlations.append((active_asset, correlation))
        else:
            insufficient = True
    if not correlations:
        return {"passed": True, "max_correlation": np.nan, "rejected_against": pd.NA, "insufficient_history": insufficient}
    rejected_asset, correlation = sorted(correlations, key=lambda item: (-abs(item[1]), item[0]))[0]
    passed = abs(correlation) <= float(cfg["maximum_abs_correlation"])
    return {
        "passed": bool(passed),
        "max_correlation": float(correlation),
        "rejected_against": pd.NA if passed else rejected_asset,
        "insufficient_history": bool(insufficient),
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
    annualization_mode: str = "fixed_periods",
    allow_short: bool = True,
    asset_params: Mapping[str, Mapping[str, Any]] | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    portfolio_guard: Mapping[str, Any] | None = None,
    event_time_remap_policy: str = "skip",
    max_cost_r: float | None = None,
    dynamic_exit: Mapping[str, Any] | None = None,
    strategy_path: Mapping[str, Any] | None = None,
    correlation_guard: Mapping[str, Any] | None = None,
    liquidate_at_end: bool = False,
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
    annualization_mode = str(annualization_mode)
    tie_break = str(tie_break)
    subset = str(subset)
    event_time_remap_policy = str(event_time_remap_policy)
    if entry_price_mode not in _ALLOWED_ENTRY_PRICE_MODES:
        raise ValueError("portfolio_barrier entry_price_mode must be one of: current_close, next_open.")
    if annualization_mode not in {"fixed_periods", "calendar_daily"}:
        raise ValueError("portfolio_barrier annualization_mode must be 'fixed_periods' or 'calendar_daily'.")
    if not isinstance(allow_short, bool):
        raise ValueError("portfolio_barrier allow_short must be boolean.")
    if tie_break not in _ALLOWED_TIE_BREAKS:
        raise ValueError("portfolio_barrier tie_break must be one of: closest_to_open, profit, stop.")
    if subset not in {"full", "test"}:
        raise ValueError("portfolio_barrier subset must be 'full' or 'test'.")
    if event_time_remap_policy not in _ALLOWED_EVENT_TIME_REMAP_POLICIES:
        raise ValueError("portfolio_barrier event_time_remap_policy must be 'next_aligned' or 'skip'.")
    if not isinstance(liquidate_at_end, bool):
        raise ValueError("portfolio_barrier liquidate_at_end must be boolean.")

    profit_barrier_r = _positive_float(profit_barrier_r, field="profit_barrier_r")
    stop_barrier_r = _positive_float(stop_barrier_r, field="stop_barrier_r")
    vertical_barrier_bars = _positive_int_or_none(vertical_barrier_bars, field="vertical_barrier_bars")
    cost_per_turnover = float(cost_per_turnover)
    slippage_per_turnover = float(slippage_per_turnover)
    if cost_per_turnover < 0.0 or slippage_per_turnover < 0.0:
        raise ValueError("portfolio_barrier costs and slippage must be >= 0.")
    if max_cost_r is not None:
        max_cost_r = _positive_float(max_cost_r, field="max_cost_r")
    dynamic_exit_cfg = _validate_dynamic_exit_config(dynamic_exit)
    strategy_path_cfg = _validate_strategy_path_config(strategy_path)
    if bool(strategy_path_cfg.get("enabled", False)) and bool(dynamic_exit_cfg.get("enabled", False)):
        raise ValueError("portfolio_barrier strategy_path and dynamic_exit cannot both be enabled.")
    if bool(strategy_path_cfg.get("enabled", False)) and entry_price_mode != "next_open":
        raise ValueError(
            "portfolio_barrier MATB strategy_path requires top-level entry_price_mode='next_open'."
        )
    correlation_guard_cfg = _validate_correlation_guard_config(correlation_guard)

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
        if bool(strategy_path_cfg.get("enabled", False)):
            asset_required_columns.append(str(strategy_path_cfg["trend_score_col"]))
        if params.get("max_spread_points") is not None:
            default_bid_col = (
                str(strategy_path_cfg["bid_open_col"])
                if bool(strategy_path_cfg.get("enabled", False))
                else "bid_open"
            )
            default_ask_col = (
                str(strategy_path_cfg["ask_open_col"])
                if bool(strategy_path_cfg.get("enabled", False))
                else "ask_open"
            )
            asset_required_columns.extend(
                [
                    str(params.get("spread_bid_col", default_bid_col)),
                    str(params.get("spread_ask_col", default_ask_col)),
                ]
            )
            _positive_float(params.get("point_size"), field=f"asset_params.{asset}.point_size")
            _positive_float(
                params.get("max_spread_points"),
                field=f"asset_params.{asset}.max_spread_points",
            )
        _require_columns(frame, asset=asset, columns=asset_required_columns)
        if bool(correlation_guard_cfg.get("enabled", False)):
            _require_columns(frame, asset=asset, columns=[str(correlation_guard_cfg["returns_col"])])
    signals = _align_signal_index(frames, signal_col=signal_col, alignment=alignment)
    if signals.empty:
        raise ValueError("portfolio_barrier aligned signal frame is empty.")

    constraints = constraints or PortfolioConstraints(enforce_target_net_exposure=False)
    if constraints.enforce_target_net_exposure:
        raise ValueError(
            "portfolio_barrier cannot enforce target_net_exposure with its event-by-event "
            "allocator; set enforce_target_net_exposure=false or use a joint portfolio engine."
        )
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
    skipped_short_disabled = 0
    skipped_turnover_limit = 0
    turnover_sized_trade_count = 0
    risk_sized_trade_count = 0
    correlation_guard_rejections = 0
    correlation_guard_checked = 0
    correlation_guard_insufficient_history = 0
    correlation_guard_events: list[dict[str, Any]] = []
    guard_equity = 1.0
    guard_peak_equity = 1.0
    guard_daily_start_equity = 1.0
    guard_daily_date: Any | None = None
    guard_daily_blocked_date: Any | None = None
    guard_permanent_flat = False
    guard_trigger_count = 0
    daily_loss_trigger_count = 0
    flattened_trade_count = 0
    cancelled_pending_trade_count = 0
    portfolio_bankrupt = False
    bankruptcy_time: Any | None = None
    mark_to_market_equity_state = 1.0

    def _flatten_active_positions(trigger_timestamp: Any, *, reason: str) -> None:
        nonlocal flattened_trade_count, cancelled_pending_trade_count
        for active_asset, active in list(active_by_asset.items()):
            original_exit_time = active["exit_time"]
            if original_exit_time <= trigger_timestamp:
                continue
            trade = trades[int(active["trade_index"])]
            original_pnl = dict(active["pnl"])
            original_path = active["mtm_contribution"]

            gross_returns.loc[original_exit_time] -= float(original_pnl["gross_return"])
            net_returns.loc[original_exit_time] -= float(original_pnl["net_return"])
            costs.loc[original_exit_time] -= float(original_pnl["cost"])
            turnover.loc[active["entry_time"]] -= abs(float(active["weight"]))
            turnover.loc[original_exit_time] -= abs(float(active["weight"]))
            mark_to_market_returns.loc[original_path.index] -= original_path
            weights.loc[
                (weights.index >= active["entry_time"]) & (weights.index <= original_exit_time),
                active_asset,
            ] = 0.0

            if trigger_timestamp < active["entry_time"]:
                trade["cancelled"] = True
                trade["exit_reason"] = f"{reason}_cancelled"
                trade["hit_type"] = "cancelled"
                trade["gross_return"] = 0.0
                trade["net_return"] = 0.0
                trade["cost"] = 0.0
                trade["fixed_cost"] = 0.0
                trade["slippage"] = 0.0
                trade["realized_r"] = np.nan
                trade["trade_r"] = np.nan
                cancelled_pending_trade_count += 1
                active_by_asset.pop(active_asset, None)
                continue

            frame = frames[active_asset]
            if trigger_timestamp in frame.index:
                flatten_time = trigger_timestamp
                flatten_price = float(frame.loc[flatten_time, close_col])
                exit_at_open = False
            else:
                native_candidates = frame.index[
                    (frame.index > trigger_timestamp) & frame.index.isin(weights.index)
                ]
                if len(native_candidates) == 0:
                    raise RuntimeError(
                        "portfolio_barrier could not execute a risk flatten for "
                        f"'{active_asset}' after {trigger_timestamp!r}."
                    )
                flatten_time = native_candidates[0]
                flatten_price = float(frame.loc[flatten_time, open_col])
                exit_at_open = True
            if not np.isfinite(flatten_price) or flatten_price <= 0.0:
                raise RuntimeError(
                    f"portfolio_barrier risk flatten for '{active_asset}' has no valid price."
                )

            replacement_pnl = _realized_trade_pnl(
                side=float(active["side"]),
                weight=float(active["weight"]),
                entry_price=float(active["entry_price"]),
                exit_price=flatten_price,
                risk_distance=float(active["risk_distance"]),
                cost_per_turnover=cost_per_turnover,
                slippage_per_turnover=slippage_per_turnover,
            )
            gross_returns.loc[flatten_time] += float(replacement_pnl["gross_return"])
            net_returns.loc[flatten_time] += float(replacement_pnl["net_return"])
            costs.loc[flatten_time] += float(replacement_pnl["cost"])
            turnover.loc[active["entry_time"]] += abs(float(active["weight"]))
            turnover.loc[flatten_time] += abs(float(active["weight"]))
            replacement_path = _apply_mark_to_market_trade_path(
                mark_to_market_returns,
                frame=frame,
                aligned_index=weights.index,
                close_col=close_col,
                entry_time=active["entry_time"],
                exit_time=flatten_time,
                entry_price=float(active["entry_price"]),
                exit_price=flatten_price,
                weight=float(active["weight"]),
                side=float(active["side"]),
                total_cost=float(replacement_pnl["cost"]),
            )
            weights.loc[
                (weights.index >= active["entry_time"]) & (weights.index < flatten_time),
                active_asset,
            ] = float(active["weight"])

            trade["planned_exit_time"] = trade["exit_time"]
            trade["planned_exit_price"] = trade["exit_price"]
            trade["exit_time"] = flatten_time
            trade["exit_timestamp"] = flatten_time
            trade["exit_price"] = flatten_price
            trade["exit_time_remapped"] = False
            trade["exit_reason"] = reason
            trade["hit_type"] = reason
            trade["gross_return"] = float(replacement_pnl["gross_return"])
            trade["net_return"] = float(replacement_pnl["net_return"])
            trade["cost"] = float(replacement_pnl["cost"])
            trade["fixed_cost"] = float(replacement_pnl["fixed_cost"])
            trade["slippage"] = float(replacement_pnl["slippage"])
            trade["realized_r"] = float(replacement_pnl["realized_r"])
            trade["trade_r"] = float(replacement_pnl["realized_r"])
            trade["exit_at_open"] = bool(exit_at_open)
            trade["cancelled"] = False
            if active["entry_time"] in frame.index and flatten_time in frame.index:
                trade["bars_held"] = int(
                    frame.index.get_loc(flatten_time) - frame.index.get_loc(active["entry_time"])
                )
                trade["hit_step"] = trade["bars_held"]
            active["exit_time"] = flatten_time
            active["pnl"] = dict(replacement_pnl)
            active["mtm_contribution"] = replacement_path
            flattened_trade_count += 1
            active_by_asset.pop(active_asset, None)

    for timestamp, signal_row in signals.iterrows():
        timestamp_date = pd.Timestamp(timestamp).date()
        if guard_daily_date != timestamp_date:
            guard_daily_date = timestamp_date
            guard_daily_start_equity = guard_equity
            guard_daily_blocked_date = None
        if timestamp in net_returns.index:
            if not portfolio_bankrupt:
                current_mtm_return = float(mark_to_market_returns.loc[timestamp])
                next_mark_to_market_equity = mark_to_market_equity_state * (
                    1.0 + current_mtm_return
                )
                if not np.isfinite(next_mark_to_market_equity) or next_mark_to_market_equity <= 0.0:
                    portfolio_bankrupt = True
                    bankruptcy_time = timestamp
                    mark_to_market_equity_state = 0.0
                    guard_permanent_flat = True
                    _flatten_active_positions(timestamp, reason="bankruptcy")
                    weights.loc[weights.index >= timestamp, :] = 0.0
                else:
                    mark_to_market_equity_state = float(next_mark_to_market_equity)
            guard_return = (
                float(mark_to_market_returns.loc[timestamp])
                if guard_equity_source == "mark_to_market"
                else float(net_returns.loc[timestamp])
            )
            guard_equity = max(guard_equity * (1.0 + guard_return), 0.0)
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
                _flatten_active_positions(timestamp, reason="kill_switch")
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
            if side < 0.0 and not allow_short:
                skipped_short_disabled += 1
                continue
            correlation_result = _evaluate_correlation_guard(
                frames,
                asset=asset,
                timestamp=timestamp,
                side=side,
                active_by_asset=active_by_asset,
                cfg=correlation_guard_cfg,
            )
            if bool(correlation_guard_cfg.get("enabled", False)):
                correlation_guard_checked += 1
                correlation_guard_insufficient_history += int(correlation_result["insufficient_history"])
            if not bool(correlation_result["passed"]):
                correlation_guard_rejections += 1
                correlation_guard_events.append(
                    {
                        "timestamp": timestamp,
                        "asset": asset,
                        "side": "long" if side > 0.0 else "short",
                        "entry_max_active_correlation": correlation_result["max_correlation"],
                        "entry_correlation_guard_passed": False,
                        "entry_correlation_rejected_against": correlation_result["rejected_against"],
                        "entry_correlation_insufficient_history": correlation_result["insufficient_history"],
                    }
                )
                continue
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
            module_col = str(dynamic_exit_cfg.get("module_col", "signal_module"))
            signal_module = str(frame.iloc[signal_idx].get(module_col, "")) if module_col in frame.columns else ""
            trade_dynamic_exit = _resolve_dynamic_exit_for_trade(
                dynamic_exit_cfg, side=side, module=signal_module
            )
            if bool(strategy_path_cfg.get("enabled", False)):
                event = _simulate_strategy_path_event(
                    frame,
                    signal_idx=signal_idx,
                    side=side,
                    open_col=open_col,
                    high_col=high_col,
                    low_col=low_col,
                    close_col=close_col,
                    volatility_col=asset_volatility_col,
                    strategy_path=strategy_path_cfg,
                )
            else:
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
                    dynamic_exit=trade_dynamic_exit,
                )
            if event is None:
                skipped_tail += 1
                continue
            asset_max_spread_raw = params.get("max_spread_points")
            spread_points: float | None = None
            exit_spread_points: float | None = None
            asset_max_spread: float | None = None
            execution_entry_price = float(event["entry_price"])
            execution_exit_price = float(event["exit_price"])
            if asset_max_spread_raw is not None and event.get("execution_source") == "bid_ask":
                asset_max_spread = _positive_float(
                    asset_max_spread_raw,
                    field=f"asset_params.{asset}.max_spread_points",
                )
                point_size = _positive_float(
                    params.get("point_size"),
                    field=f"asset_params.{asset}.point_size",
                )
                entry_row = frame.iloc[int(event["entry_idx"])]
                exit_row = frame.iloc[int(event["exit_idx"])]
                bid_col = str(params.get("spread_bid_col", strategy_path_cfg["bid_open_col"]))
                ask_col = str(params.get("spread_ask_col", strategy_path_cfg["ask_open_col"]))
                try:
                    entry_bid = float(entry_row[bid_col])
                    entry_ask = float(entry_row[ask_col])
                    exit_bid = float(exit_row[bid_col])
                    exit_ask = float(exit_row[ask_col])
                except (KeyError, TypeError, ValueError):
                    skipped_invalid_spread += 1
                    continue
                if not all(
                    np.isfinite(value) and value > 0.0
                    for value in (entry_bid, entry_ask, exit_bid, exit_ask)
                ) or entry_ask < entry_bid or exit_ask < exit_bid:
                    skipped_invalid_spread += 1
                    continue
                spread_points = float((entry_ask - entry_bid) / point_size)
                exit_spread_points = float((exit_ask - exit_bid) / point_size)
                if spread_points > asset_max_spread:
                    skipped_spread_filter += 1
                    continue
            elif asset_max_spread_raw is not None:
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
                try:
                    spread_execution = _spread_adjusted_execution_prices(
                        frame,
                        event=event,
                        side=side,
                        entry_price_mode=entry_price_mode,
                        bid_col=bid_col,
                        ask_col=ask_col,
                        point_size=point_size,
                    )
                except (KeyError, TypeError, ValueError):
                    skipped_invalid_spread += 1
                    continue
                spread_points = float(spread_execution["entry_spread_points"])
                exit_spread_points = float(spread_execution["exit_spread_points"])
                if spread_points > asset_max_spread:
                    skipped_spread_filter += 1
                    continue
                execution_entry_price = float(spread_execution["entry_price"])
                execution_exit_price = float(spread_execution["exit_price"])
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
            if entry_remapped or exit_remapped:
                raise ValueError(
                    "portfolio_barrier event_time_remap_policy='next_aligned' cannot safely "
                    "reuse native execution prices at remapped timestamps; use 'skip' or "
                    "align the asset calendars before backtesting."
                )
            remapped_entry_timestamps += int(entry_remapped)
            remapped_exit_timestamps += int(exit_remapped)

            risk_per_trade = params.get("risk_per_trade")
            if risk_per_trade is not None:
                risk_fraction = max(float(event["risk_distance"]) / execution_entry_price, 1e-12)
                risk_sized_cap = float(risk_per_trade) / risk_fraction
                sized_abs_weight = min(abs(float(weight)), risk_sized_cap)
                if sized_abs_weight <= 1e-12:
                    skipped_no_capacity += 1
                    continue
                if sized_abs_weight < abs(float(weight)) - 1e-12:
                    risk_sized_trade_count += 1
                weight = float(np.sign(weight)) * sized_abs_weight
            if constraints.turnover_limit is not None:
                turnover_limit = float(constraints.turnover_limit)
                if entry_time == exit_time:
                    remaining_turnover = max(
                        turnover_limit - float(turnover.loc[entry_time]),
                        0.0,
                    ) / 2.0
                else:
                    remaining_turnover = min(
                        max(turnover_limit - float(turnover.loc[entry_time]), 0.0),
                        max(turnover_limit - float(turnover.loc[exit_time]), 0.0),
                    )
                turnover_sized_weight = min(abs(float(weight)), remaining_turnover)
                if turnover_sized_weight <= 1e-12:
                    skipped_turnover_limit += 1
                    continue
                if turnover_sized_weight < abs(float(weight)) - 1e-12:
                    turnover_sized_trade_count += 1
                weight = float(np.sign(weight)) * turnover_sized_weight

            asset_max_cost_r_raw = params.get("max_cost_r", max_cost_r)
            asset_max_cost_r = (
                None
                if asset_max_cost_r_raw is None
                else _positive_float(asset_max_cost_r_raw, field=f"asset_params.{asset}.max_cost_r")
            )
            cost_filter_stats = _estimated_roundtrip_cost_filter_stats(
                weight=weight,
                entry_price=execution_entry_price,
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
                entry_price=execution_entry_price,
                exit_price=execution_exit_price,
                risk_distance=float(event["risk_distance"]),
                cost_per_turnover=cost_per_turnover,
                slippage_per_turnover=slippage_per_turnover,
            )
            gross_returns.loc[exit_time] += pnl["gross_return"]
            net_returns.loc[exit_time] += pnl["net_return"]
            costs.loc[exit_time] += pnl["cost"]
            turnover.loc[entry_time] += abs(weight)
            turnover.loc[exit_time] += abs(weight)
            mtm_contribution = _apply_mark_to_market_trade_path(
                mark_to_market_returns,
                frame=frame,
                aligned_index=weights.index,
                close_col=close_col,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=execution_entry_price,
                exit_price=execution_exit_price,
                weight=weight,
                side=side,
                total_cost=float(pnl["cost"]),
            )

            active_index = weights.index[(weights.index >= entry_time) & (weights.index <= exit_time)]
            if len(active_index) > 0:
                weights.loc[active_index, asset] = weight

            current_gross += abs(weight)
            side_name = "long" if side > 0.0 else "short"
            raw_price_pnl = _realized_trade_pnl(
                side=side,
                weight=weight,
                entry_price=float(event["entry_price"]),
                exit_price=float(event["exit_price"]),
                risk_distance=float(event["risk_distance"]),
                cost_per_turnover=cost_per_turnover,
                slippage_per_turnover=slippage_per_turnover,
            )
            trade = {
                "asset": asset,
                "asset_group": group if group is not None else "ungrouped",
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
                "planned_exit_time": raw_exit_time,
                "side": side_name,
                "signal": float(signal_value),
                "signal_module": signal_module or pd.NA,
                "position_weight": float(weight),
                "entry_price": execution_entry_price,
                "exit_price": execution_exit_price,
                "raw_entry_price": float(event["entry_price"]),
                "raw_exit_price": float(event["exit_price"]),
                "planned_exit_price": execution_exit_price,
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
                "hit_step": int(event.get("hit_step", event["bars_held"])),
                "bars_held": int(event["bars_held"]),
                "max_favorable_r": float(event["max_favorable_r"]),
                "max_adverse_r": float(event["max_adverse_r"]),
                "time_to_mfe": int(event["time_to_mfe"]),
                "time_to_mae": int(event["time_to_mae"]),
                "gross_return": pnl["gross_return"],
                "net_return": pnl["net_return"],
                "realized_r": pnl["realized_r"],
                "trade_r": pnl["realized_r"],
                "risk_fraction": cost_filter_stats["risk_fraction"],
                "risk_contribution": abs(float(weight)) * cost_filter_stats["risk_fraction"],
                "estimated_cost": cost_filter_stats["estimated_cost"],
                "estimated_cost_r": cost_filter_stats["estimated_cost_r"],
                "max_cost_r": asset_max_cost_r,
                "spread_points": spread_points,
                "entry_spread_points": spread_points,
                "exit_spread_points": exit_spread_points,
                "max_spread_points": asset_max_spread,
                "observed_spread_cost": float(raw_price_pnl["gross_return"] - pnl["gross_return"]),
                "execution_source": event.get("execution_source", "midpoint_adjusted"),
                "spread_embedded_in_gross_return": bool(event.get("execution_source") == "bid_ask"),
                "trailing_activated": bool(event.get("trailing_activated", False)),
                "effective_stop_price": event.get("effective_stop_price", event["stop_loss_price"]),
                "cost": pnl["cost"],
                "fixed_cost": pnl["fixed_cost"],
                "slippage": pnl["slippage"],
                "was_oos": bool(oos_mask.loc[timestamp]) if oos_mask is not None else True,
                "dynamic_exit_signal_time": event.get("dynamic_exit_signal_time", pd.NaT),
                "dynamic_exit_execution_time": event.get("dynamic_exit_execution_time", pd.NaT),
                "dynamic_exit_reason": event.get("dynamic_exit_reason", pd.NA),
                "entry_max_active_correlation": correlation_result["max_correlation"],
                "entry_correlation_guard_passed": bool(correlation_result["passed"]),
                "entry_correlation_rejected_against": correlation_result["rejected_against"],
                "entry_correlation_insufficient_history": bool(correlation_result["insufficient_history"]),
                "entry_cluster": frame.iloc[signal_idx].get("entry_cluster", pd.NA),
                "entry_context_age_bars": frame.iloc[signal_idx].get("entry_context_age_bars", np.nan),
                "entry_macro_context_age_bars": frame.iloc[signal_idx].get("entry_macro_context_age_bars", np.nan),
                "entry_laggard_gap": frame.iloc[signal_idx].get("entry_laggard_gap", np.nan),
                "signal_strength": frame.iloc[signal_idx].get("signal_strength", np.nan),
                "entry_relay_score": frame.iloc[signal_idx].get("entry_relay_score", np.nan),
                "gap_exit": bool(event.get("gap_exit", False)),
                "exit_at_open": bool(event.get("exit_at_open", False)),
                "cancelled": False,
            }
            trades.append(trade)
            active_by_asset[asset] = {
                "asset": asset,
                "trade_index": len(trades) - 1,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "weight": weight,
                "side": side,
                "entry_price": execution_entry_price,
                "risk_distance": float(event["risk_distance"]),
                "pnl": dict(pnl),
                "mtm_contribution": mtm_contribution,
            }

    for series in (gross_returns, net_returns, costs, turnover, mark_to_market_returns):
        series.loc[series.abs() < 1e-15] = 0.0
    terminal_gross_exposure_before_liquidation = (
        float(weights.iloc[-1].abs().sum()) if not weights.empty else 0.0
    )
    if liquidate_at_end and not weights.empty:
        weights.iloc[-1] = 0.0

    equity_curve = equity_curve_from_returns(net_returns)
    equity_curve.name = "equity"
    mark_to_market_equity = equity_curve_from_returns(mark_to_market_returns)
    mark_to_market_equity.name = "mark_to_market_equity"
    summary = compute_backtest_metrics(
        net_returns=net_returns,
        periods_per_year=int(periods_per_year),
        annualization_mode=annualization_mode,
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )
    mark_to_market_summary = compute_backtest_metrics(
        net_returns=mark_to_market_returns,
        periods_per_year=int(periods_per_year),
        annualization_mode=annualization_mode,
    )

    trades_df = pd.DataFrame(trades)
    if not trades_df.empty and "cancelled" in trades_df.columns:
        trades_df = trades_df.loc[~trades_df["cancelled"].fillna(False).astype(bool)].copy()
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
                "dynamic_exit_signal_time",
                "dynamic_exit_execution_time",
                "dynamic_exit_reason",
                "entry_max_active_correlation",
                "entry_correlation_guard_passed",
                "entry_correlation_rejected_against",
                "entry_correlation_insufficient_history",
            ]
        )
    else:
        trade_r = pd.to_numeric(trades_df["realized_r"], errors="coerce").dropna().astype(float)
        trade_net_returns = (
            pd.to_numeric(trades_df["net_return"], errors="coerce").dropna().astype(float)
        )
        trade_profit_factor = profit_factor(trade_net_returns)
        trade_hit_rate = hit_rate(trade_net_returns)
        summary["trade_count"] = float(len(trades_df))
        summary["average_r"] = float(trade_r.mean()) if not trade_r.empty else np.nan
        summary["median_r"] = float(trade_r.median()) if not trade_r.empty else np.nan
        summary["win_rate"] = trade_hit_rate
        summary["profit_factor"] = trade_profit_factor
        summary["hit_rate"] = trade_hit_rate
        summary["metric_scope"] = "trade_ledger"
        mark_to_market_summary["profit_factor"] = trade_profit_factor
        mark_to_market_summary["hit_rate"] = trade_hit_rate
        mark_to_market_summary["metric_scope"] = "trade_ledger"
    if trades_df.empty:
        summary["metric_scope"] = "trade_ledger"
        mark_to_market_summary["metric_scope"] = "trade_ledger"
    summary.update(
        {
            "bankrupt": bool(portfolio_bankrupt),
            "bankruptcy_time": bankruptcy_time,
            "liquidate_at_end": bool(liquidate_at_end),
            "terminal_gross_exposure_before_liquidation": terminal_gross_exposure_before_liquidation,
            "terminal_gross_exposure": (
                float(weights.iloc[-1].abs().sum()) if not weights.empty else 0.0
            ),
        }
    )
    mark_to_market_summary.update(
        {
            "bankrupt": bool(portfolio_bankrupt),
            "bankruptcy_time": bankruptcy_time,
        }
    )
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
    for group_name in sorted(set(asset_groups.values())):
        group_assets = [
            asset for asset in weights.columns if asset_groups.get(str(asset)) == group_name
        ]
        if not group_assets:
            continue
        diagnostics[f"group_{group_name}_gross_exposure"] = (
            weights[group_assets].abs().sum(axis=1).astype(float)
        )
        diagnostics[f"group_{group_name}_net_exposure"] = (
            weights[group_assets].sum(axis=1).astype(float)
        )

    if trades_df.empty:
        pnl_contribution_by_asset: dict[str, float] = {}
        pnl_contribution_by_group: dict[str, float] = {}
        risk_contribution_by_asset: dict[str, float] = {}
        risk_contribution_by_group: dict[str, float] = {}
    else:
        numeric_net = pd.to_numeric(trades_df["net_return"], errors="coerce").fillna(0.0)
        numeric_risk = pd.to_numeric(
            trades_df.get("risk_contribution", pd.Series(0.0, index=trades_df.index)),
            errors="coerce",
        ).fillna(0.0)
        pnl_contribution_by_asset = {
            str(key): float(value)
            for key, value in numeric_net.groupby(trades_df["asset"].astype(str)).sum().items()
        }
        pnl_contribution_by_group = {
            str(key): float(value)
            for key, value in numeric_net.groupby(trades_df["asset_group"].astype(str)).sum().items()
        }
        risk_contribution_by_asset = {
            str(key): float(value)
            for key, value in numeric_risk.groupby(trades_df["asset"].astype(str)).sum().items()
        }
        risk_contribution_by_group = {
            str(key): float(value)
            for key, value in numeric_risk.groupby(trades_df["asset_group"].astype(str)).sum().items()
        }

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
            "flattened_trade_count": int(flattened_trade_count),
            "cancelled_pending_trade_count": int(cancelled_pending_trade_count),
            "bankrupt": bool(portfolio_bankrupt),
            "bankruptcy_time": bankruptcy_time,
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
            "skipped_short_disabled": int(skipped_short_disabled),
            "skipped_turnover_limit": int(skipped_turnover_limit),
            "turnover_sized_trade_count": int(turnover_sized_trade_count),
            "correlation_guard_enabled": bool(correlation_guard_cfg.get("enabled", False)),
            "correlation_guard_checked": int(correlation_guard_checked),
            "correlation_guard_rejections": int(correlation_guard_rejections),
            "correlation_guard_insufficient_history": int(correlation_guard_insufficient_history),
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
        "annualization_mode": annualization_mode,
        "allow_short": allow_short,
        "cost_per_turnover_applied": cost_per_turnover,
        "profit_barrier_r": float(profit_barrier_r),
        "stop_barrier_r": float(stop_barrier_r),
        "vertical_barrier_bars": None if vertical_barrier_bars is None else int(vertical_barrier_bars),
        "volatility_col": volatility_col,
        "tie_break": tie_break,
        "event_time_remap_policy": event_time_remap_policy,
        "liquidate_at_end": bool(liquidate_at_end),
        "terminal_gross_exposure_before_liquidation": terminal_gross_exposure_before_liquidation,
        "terminal_gross_exposure": (
            float(weights.iloc[-1].abs().sum()) if not weights.empty else 0.0
        ),
        "bankrupt": bool(portfolio_bankrupt),
        "bankruptcy_time": bankruptcy_time,
        "max_cost_r": max_cost_r,
        "asset_params": dict(asset_params_by_asset),
        "asset_groups": dict(asset_groups),
        "pnl_contribution_by_asset": pnl_contribution_by_asset,
        "pnl_contribution_by_group": pnl_contribution_by_group,
        "risk_contribution_by_asset": risk_contribution_by_asset,
        "risk_contribution_by_group": risk_contribution_by_group,
        "portfolio_limit_rejections": {
            "no_capacity": int(skipped_no_capacity),
            "max_open_trades": int(skipped_max_open_trades),
            "group_max_open_trades": int(skipped_group_max_open_trades),
            "group_exposure_cap": int(skipped_group_cap),
            "turnover_limit": int(skipped_turnover_limit),
        },
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
        "skipped_short_disabled": int(skipped_short_disabled),
        "skipped_turnover_limit": int(skipped_turnover_limit),
        "turnover_sized_trade_count": int(turnover_sized_trade_count),
        "flattened_trade_count": int(flattened_trade_count),
        "cancelled_pending_trade_count": int(cancelled_pending_trade_count),
        "daily_loss_trigger_count": int(daily_loss_trigger_count),
        "risk_sized_trade_count": int(risk_sized_trade_count),
        "remapped_entry_timestamps": int(remapped_entry_timestamps),
        "remapped_exit_timestamps": int(remapped_exit_timestamps),
        "ignored_open_signals": int(ignored_open_signals),
        "oos_filtered": bool(oos_mask is not None),
        "dynamic_exit": dict(dynamic_exit_cfg),
        "strategy_path": dict(strategy_path_cfg),
        "correlation_guard": {
            **dict(correlation_guard_cfg),
            "checked": int(correlation_guard_checked),
            "rejections": int(correlation_guard_rejections),
            "insufficient_history": int(correlation_guard_insufficient_history),
        },
        "correlation_guard_events": correlation_guard_events,
    }
    return performance, weights, diagnostics, meta


__all__ = ["run_portfolio_barrier_backtest"]
