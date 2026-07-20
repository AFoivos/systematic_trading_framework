from __future__ import annotations

"""Shared trade-path simulation helpers used by targets and backtests."""

from typing import Any, Mapping

import numpy as np


def _enabled(section: Mapping[str, Any]) -> bool:
    return bool(dict(section or {}).get("enabled", False))


def normalize_dynamic_exit_config(dynamic_exits: Mapping[str, Any] | None) -> dict[str, Any]:
    cfg = dict(dynamic_exits or {})
    enabled = bool(cfg.get("enabled", False))
    disabled_defaults = {
        "enabled": False,
        "signal_off_exit": {"enabled": False, "min_bars_held": 1, "exit_price": "next_open"},
        "forecast_decay": {
            "enabled": False,
            "min_bars_held": 1,
            "exit_price": "next_open",
            "long_hold_threshold": 0.70,
            "long_exit_threshold": 0.0,
            "short_hold_threshold": -0.85,
            "short_exit_threshold": 0.0,
        },
        "trend_break": {
            "enabled": False,
            "min_bars_held": 1,
            "exit_price": "next_open",
            "min_disagreeing_indicators": 2,
            "indicator_cols": [],
            "long_weakening_level": 0.0,
            "short_weakening_level": 0.0,
        },
        "breakeven": {"enabled": False, "trigger_r": 0.8, "lock_r": 0.0},
        "profit_lock": {"enabled": False, "trigger_r": 1.2, "lock_r": 0.3},
        "atr_trailing": {"enabled": False, "activation_r": 0.0, "distance_mult": 1.0},
        "no_progress": {"enabled": False, "bars": 6, "min_favorable_r": 0.2, "exit_price": "close"},
    }
    if not enabled:
        return disabled_defaults

    signal_off = dict(cfg.get("signal_off_exit", {}) or {})
    forecast_decay = dict(cfg.get("forecast_decay", {}) or {})
    trend_break = dict(cfg.get("trend_break", {}) or {})
    breakeven = dict(cfg.get("breakeven", {}) or {})
    profit_lock = dict(cfg.get("profit_lock", {}) or {})
    atr_trailing = dict(cfg.get("atr_trailing", {}) or {})
    no_progress = dict(cfg.get("no_progress", {}) or {})

    out = {
        "enabled": enabled,
        "signal_off_exit": {
            "enabled": enabled and _enabled(signal_off),
            "min_bars_held": int(signal_off.get("min_bars_held", 1)),
            "exit_price": str(signal_off.get("exit_price", "next_open")),
        },
        "forecast_decay": {
            "enabled": enabled and _enabled(forecast_decay),
            "min_bars_held": int(forecast_decay.get("min_bars_held", 1)),
            "exit_price": str(forecast_decay.get("exit_price", "next_open")),
            "long_hold_threshold": float(forecast_decay.get("long_hold_threshold", 0.70)),
            "long_exit_threshold": float(forecast_decay.get("long_exit_threshold", 0.0)),
            "short_hold_threshold": float(forecast_decay.get("short_hold_threshold", -0.85)),
            "short_exit_threshold": float(forecast_decay.get("short_exit_threshold", 0.0)),
        },
        "trend_break": {
            "enabled": enabled and _enabled(trend_break),
            "min_bars_held": int(trend_break.get("min_bars_held", 1)),
            "exit_price": str(trend_break.get("exit_price", "next_open")),
            "min_disagreeing_indicators": int(trend_break.get("min_disagreeing_indicators", 2)),
            "indicator_cols": list(trend_break.get("indicator_cols", []) or []),
            "long_weakening_level": float(trend_break.get("long_weakening_level", 0.0)),
            "short_weakening_level": float(trend_break.get("short_weakening_level", 0.0)),
        },
        "breakeven": {
            "enabled": enabled and _enabled(breakeven),
            "trigger_r": float(breakeven.get("trigger_r", 0.8)),
            "lock_r": float(breakeven.get("lock_r", 0.0)),
        },
        "profit_lock": {
            "enabled": enabled and _enabled(profit_lock),
            "trigger_r": float(profit_lock.get("trigger_r", 1.2)),
            "lock_r": float(profit_lock.get("lock_r", 0.3)),
        },
        "atr_trailing": {
            "enabled": enabled and _enabled(atr_trailing),
            "activation_r": float(atr_trailing.get("activation_r", 0.0)),
            "distance_mult": float(atr_trailing.get("distance_mult", 1.0)),
        },
        "no_progress": {
            "enabled": enabled and _enabled(no_progress),
            "bars": int(no_progress.get("bars", 6)),
            "min_favorable_r": float(no_progress.get("min_favorable_r", 0.2)),
            "exit_price": str(no_progress.get("exit_price", "close")),
        },
    }

    for path in ("signal_off_exit", "forecast_decay", "trend_break", "no_progress"):
        exit_price = out[path]["exit_price"]
        if exit_price not in {"close", "next_open"}:
            raise ValueError(f"dynamic_exits.{path}.exit_price must be 'close' or 'next_open'.")
    for path in ("signal_off_exit", "forecast_decay", "trend_break"):
        if out[path]["min_bars_held"] < 0:
            raise ValueError(f"dynamic_exits.{path}.min_bars_held must be >= 0.")
    if out["no_progress"]["bars"] <= 0:
        raise ValueError("dynamic_exits.no_progress.bars must be > 0.")
    if out["forecast_decay"]["long_exit_threshold"] > out["forecast_decay"]["long_hold_threshold"]:
        raise ValueError("dynamic_exits.forecast_decay.long_exit_threshold must be <= long_hold_threshold.")
    if out["forecast_decay"]["short_exit_threshold"] < out["forecast_decay"]["short_hold_threshold"]:
        raise ValueError("dynamic_exits.forecast_decay.short_exit_threshold must be >= short_hold_threshold.")
    if out["trend_break"]["min_disagreeing_indicators"] <= 0:
        raise ValueError("dynamic_exits.trend_break.min_disagreeing_indicators must be > 0.")
    for path in ("breakeven", "profit_lock"):
        if out[path]["trigger_r"] <= 0.0:
            raise ValueError(f"dynamic_exits.{path}.trigger_r must be > 0.")
    if out["atr_trailing"]["activation_r"] < 0.0:
        raise ValueError("dynamic_exits.atr_trailing.activation_r must be >= 0.")
    if out["atr_trailing"]["distance_mult"] <= 0.0:
        raise ValueError("dynamic_exits.atr_trailing.distance_mult must be > 0.")
    if out["no_progress"]["min_favorable_r"] < 0.0:
        raise ValueError("dynamic_exits.no_progress.min_favorable_r must be >= 0.")
    return out


def normalize_partial_exit_config(partial_exits: Mapping[str, Any] | None) -> dict[str, Any]:
    cfg = dict(partial_exits or {})
    enabled = bool(cfg.get("enabled", False))
    disabled_defaults: dict[str, Any] = {"enabled": False, "rules": []}
    if not enabled:
        return disabled_defaults

    raw_rules = cfg.get("rules", []) or []
    if not isinstance(raw_rules, list):
        raise ValueError("partial_exits.rules must be a list.")

    rules: list[dict[str, Any]] = []
    total_fraction = 0.0
    for idx, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, Mapping):
            raise ValueError(f"partial_exits.rules[{idx}] must be a mapping.")
        trigger_r = float(raw_rule.get("trigger_r"))
        fraction = float(raw_rule.get("fraction"))
        exit_price = str(raw_rule.get("exit_price", "trigger"))
        if not np.isfinite(trigger_r) or trigger_r <= 0.0:
            raise ValueError(f"partial_exits.rules[{idx}].trigger_r must be > 0.")
        if not np.isfinite(fraction) or not 0.0 < fraction < 1.0:
            raise ValueError(f"partial_exits.rules[{idx}].fraction must be in (0, 1).")
        if exit_price not in {"trigger", "close", "next_open"}:
            raise ValueError(f"partial_exits.rules[{idx}].exit_price must be one of: trigger, close, next_open.")
        total_fraction += fraction
        rules.append(
            {
                "trigger_r": float(trigger_r),
                "fraction": float(fraction),
                "exit_price": exit_price,
            }
        )

    if total_fraction >= 1.0:
        raise ValueError("partial_exits.rules fractions must sum to < 1.0.")
    rules.sort(key=lambda rule: float(rule["trigger_r"]))
    return {"enabled": True, "rules": rules}


def _exit_on_price_mode(
    *,
    mode: str,
    current_idx: int,
    opens: np.ndarray,
    closes: np.ndarray,
) -> tuple[int, float]:
    if mode == "next_open" and current_idx + 1 < len(opens):
        return current_idx + 1, float(opens[current_idx + 1])
    return current_idx, float(closes[current_idx])


def _dynamic_exit_on_price_mode(
    *,
    mode: str,
    current_idx: int,
    max_exit_idx: int,
    opens: np.ndarray,
    closes: np.ndarray,
) -> tuple[int, float] | None:
    if mode == "next_open":
        next_idx = int(current_idx) + 1
        if next_idx <= int(max_exit_idx) and next_idx < len(opens):
            return next_idx, float(opens[next_idx])
        return None
    return int(current_idx), float(closes[current_idx])


def _partial_exit_price(
    *,
    mode: str,
    trigger_price: float,
    current_idx: int,
    opens: np.ndarray,
    closes: np.ndarray,
) -> tuple[int, float]:
    if mode == "trigger":
        return current_idx, float(trigger_price)
    return _exit_on_price_mode(mode=mode, current_idx=current_idx, opens=opens, closes=closes)


def _double_touch_exit(
    *,
    tie_break: str,
    bar_open: float,
    effective_stop_price: float,
    take_profit_price: float,
    stop_reason: str,
) -> tuple[float, str]:
    if tie_break in {"conservative", "stop_loss"}:
        return float(effective_stop_price), stop_reason
    if tie_break == "take_profit":
        return float(take_profit_price), "take_profit"
    if tie_break == "closest_to_open":
        stop_distance = abs(float(bar_open) - float(effective_stop_price))
        target_distance = abs(float(bar_open) - float(take_profit_price))
        if target_distance < stop_distance:
            return float(take_profit_price), "take_profit"
        return float(effective_stop_price), stop_reason
    raise ValueError("tie_break must be one of: conservative, take_profit, stop_loss, closest_to_open.")


def _empty_barrier_outcome(
    *,
    signal_idx: int,
    side: int,
    exit_reason: str,
) -> dict[str, Any]:
    return {
        "valid": False,
        "signal_idx": int(signal_idx),
        "entry_idx": None,
        "exit_idx": None,
        "side": int(side),
        "side_name": "short" if int(side) < 0 else "long",
        "raw_entry_price": np.nan,
        "raw_exit_price": np.nan,
        "entry_price": np.nan,
        "exit_price": np.nan,
        "stop_loss_price": np.nan,
        "take_profit_price": np.nan,
        "effective_stop_price": np.nan,
        "exit_reason": str(exit_reason),
        "hit_type": str(exit_reason),
        "hit_step": np.nan,
        "bars_held": np.nan,
        "size": np.nan,
        "stop_distance_pct": np.nan,
        "target_distance_pct": np.nan,
        "gross_return": np.nan,
        "net_return": np.nan,
        "gross_r": np.nan,
        "net_r": np.nan,
        "cost_paid": np.nan,
        "slippage_drag": np.nan,
        "max_favorable_r": np.nan,
        "max_adverse_r": np.nan,
        "time_to_mfe": np.nan,
        "time_to_mae": np.nan,
        "breakeven_activated": False,
        "profit_lock_activated": False,
    }


def leg_raw_return(*, is_short: bool, entry_price: float, exit_price: float) -> float:
    if is_short:
        return 1.0 - float(exit_price) / float(entry_price)
    return float(exit_price) / float(entry_price) - 1.0


def leg_slippage_adjusted_return(
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


def compute_trade_pnl(
    *,
    side: int | float,
    weight: float,
    entry_price: float,
    exit_price: float,
    risk_distance: float,
    cost_per_unit_turnover: float = 0.0,
    slippage_per_unit_turnover: float = 0.0,
) -> dict[str, float]:
    """Compute one side-oriented trade PnL with a shared R convention."""
    side_int = 1 if float(side) > 0.0 else -1 if float(side) < 0.0 else 0
    size = abs(float(weight))
    entry = float(entry_price)
    exit_ = float(exit_price)
    risk = float(risk_distance)
    fixed_cost_rate = float(cost_per_unit_turnover)
    slippage_rate = float(slippage_per_unit_turnover)
    if side_int == 0:
        raise ValueError("compute_trade_pnl side must be non-zero.")
    if not np.isfinite(size) or size <= 0.0:
        raise ValueError("compute_trade_pnl weight must have finite positive magnitude.")
    if not np.isfinite(entry) or entry <= 0.0 or not np.isfinite(exit_) or exit_ <= 0.0:
        raise ValueError("compute_trade_pnl entry_price and exit_price must be finite and > 0.")
    if not np.isfinite(risk) or risk <= 0.0:
        raise ValueError("compute_trade_pnl risk_distance must be finite and > 0.")
    if fixed_cost_rate < 0.0 or slippage_rate < 0.0:
        raise ValueError("compute_trade_pnl costs and slippage must be >= 0.")

    is_short = side_int < 0
    gross_return = size * leg_raw_return(
        is_short=is_short,
        entry_price=entry,
        exit_price=exit_,
    )
    gross_after_slippage = size * leg_slippage_adjusted_return(
        is_short=is_short,
        entry_price=entry,
        exit_price=exit_,
        slippage_per_unit_turnover=slippage_rate,
    )
    slippage_cost = max(float(gross_return - gross_after_slippage), 0.0)
    fixed_cost = size * 2.0 * fixed_cost_rate
    total_cost = fixed_cost + slippage_cost
    net_return = gross_return - total_cost
    risk_capital = max(size * risk / entry, 1e-12)
    return {
        "gross_return": float(gross_return),
        "net_return": float(net_return),
        "cost": float(total_cost),
        "fixed_cost": float(fixed_cost),
        "slippage": float(slippage_cost),
        "gross_r": float(gross_return / risk_capital),
        "net_r": float(net_return / risk_capital),
        "transaction_cost_r": float(total_cost / risk_capital),
        "risk_fraction": float(risk / entry),
    }


def _empty_strategy_path_outcome(
    *,
    signal_idx: int,
    side: int,
    exit_reason: str,
) -> dict[str, Any]:
    return {
        "valid": False,
        "signal_idx": int(signal_idx),
        "entry_idx": None,
        "exit_idx": None,
        "side": int(side),
        "entry_price": np.nan,
        "exit_price": np.nan,
        "initial_stop_price": np.nan,
        "emergency_profit_price": np.nan,
        "effective_stop_price": np.nan,
        "risk_distance": np.nan,
        "gross_return": np.nan,
        "net_return": np.nan,
        "gross_r": np.nan,
        "net_r": np.nan,
        "transaction_cost_r": np.nan,
        "max_favorable_r": np.nan,
        "max_adverse_r": np.nan,
        "bars_held": np.nan,
        "hit_step": np.nan,
        "exit_reason": str(exit_reason),
        "hit_type": str(exit_reason),
        "execution_source": "unavailable",
        "exit_at_open": False,
        "gap_exit": False,
        "trailing_activated": False,
    }


def _strategy_path_array(
    values: np.ndarray | None,
    *,
    expected_length: int,
    field: str,
) -> np.ndarray | None:
    if values is None:
        return None
    resolved = np.asarray(values, dtype=float)
    if len(resolved) != expected_length:
        raise ValueError(f"strategy_path {field} must match the OHLC array length.")
    return resolved


def simulate_strategy_path_trade_outcome(
    *,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volatility: np.ndarray,
    trend_score: np.ndarray,
    signal_idx: int,
    side: int | float,
    bid_opens: np.ndarray | None = None,
    bid_highs: np.ndarray | None = None,
    bid_lows: np.ndarray | None = None,
    bid_closes: np.ndarray | None = None,
    ask_opens: np.ndarray | None = None,
    ask_highs: np.ndarray | None = None,
    ask_lows: np.ndarray | None = None,
    ask_closes: np.ndarray | None = None,
    entry_price_mode: str = "next_open",
    entry_delay_bars: int = 0,
    stop_loss_atr: float = 2.0,
    emergency_profit_r: float = 8.0,
    trailing_activation_r: float = 1.5,
    trailing_distance_atr: float = 2.5,
    max_holding_bars: int = 1440,
    tie_break: str = "closest_to_open",
    strict_bid_ask: bool = True,
    allow_partial_horizon: bool = False,
    cost_per_unit_turnover: float = 0.0,
    slippage_per_unit_turnover: float = 0.0,
) -> dict[str, Any]:
    """
    Simulate the shared MATB trade path used by both targets and backtests.

    A signal observed at close ``t`` enters at the next available configured
    open. Initial risk is frozen from volatility at ``t``. The trailing stop is
    updated after the current bar's barrier checks, so an OHLC bar never uses
    its own high to raise a stop and then retroactively hit that stop at its low.
    """
    opens = np.asarray(opens, dtype=float)
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    closes = np.asarray(closes, dtype=float)
    volatility = np.asarray(volatility, dtype=float)
    trend_score = np.asarray(trend_score, dtype=float)
    n = len(opens)
    if not (len(highs) == len(lows) == len(closes) == len(volatility) == len(trend_score) == n):
        raise ValueError("strategy_path OHLC, volatility, and trend_score arrays must have equal length.")
    side_int = 1 if float(side) > 0.0 else -1 if float(side) < 0.0 else 0
    if side_int == 0:
        return _empty_strategy_path_outcome(signal_idx=signal_idx, side=0, exit_reason="no_side")
    if entry_price_mode != "next_open":
        raise ValueError("strategy_path currently requires entry_price_mode='next_open'.")
    if isinstance(entry_delay_bars, bool) or int(entry_delay_bars) < 0:
        raise ValueError("strategy_path entry_delay_bars must be a non-negative integer.")
    if isinstance(max_holding_bars, bool) or int(max_holding_bars) <= 0:
        raise ValueError("strategy_path max_holding_bars must be a positive integer.")
    for field, value in (
        ("stop_loss_atr", stop_loss_atr),
        ("emergency_profit_r", emergency_profit_r),
        ("trailing_distance_atr", trailing_distance_atr),
    ):
        if not np.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"strategy_path {field} must be finite and > 0.")
    if not np.isfinite(float(trailing_activation_r)) or float(trailing_activation_r) < 0.0:
        raise ValueError("strategy_path trailing_activation_r must be finite and >= 0.")
    if tie_break not in {"closest_to_open", "conservative", "stop_loss", "take_profit"}:
        raise ValueError(
            "strategy_path tie_break must be one of: closest_to_open, conservative, stop_loss, take_profit."
        )
    if float(cost_per_unit_turnover) < 0.0 or float(slippage_per_unit_turnover) < 0.0:
        raise ValueError("strategy_path costs and slippage must be >= 0.")

    signal_idx = int(signal_idx)
    if signal_idx < 0 or signal_idx >= n:
        return _empty_strategy_path_outcome(
            signal_idx=signal_idx,
            side=side_int,
            exit_reason="invalid_signal_idx",
        )
    entry_idx = signal_idx + 1 + int(entry_delay_bars)
    if entry_idx >= n:
        return _empty_strategy_path_outcome(signal_idx=signal_idx, side=side_int, exit_reason="unavailable_tail")
    requested_exit_idx = entry_idx + int(max_holding_bars) - 1
    if requested_exit_idx >= n and not allow_partial_horizon:
        return _empty_strategy_path_outcome(signal_idx=signal_idx, side=side_int, exit_reason="unavailable_tail")
    max_exit_idx = min(n - 1, requested_exit_idx)

    quote_arrays = {
        "bid_opens": _strategy_path_array(bid_opens, expected_length=n, field="bid_opens"),
        "bid_highs": _strategy_path_array(bid_highs, expected_length=n, field="bid_highs"),
        "bid_lows": _strategy_path_array(bid_lows, expected_length=n, field="bid_lows"),
        "bid_closes": _strategy_path_array(bid_closes, expected_length=n, field="bid_closes"),
        "ask_opens": _strategy_path_array(ask_opens, expected_length=n, field="ask_opens"),
        "ask_highs": _strategy_path_array(ask_highs, expected_length=n, field="ask_highs"),
        "ask_lows": _strategy_path_array(ask_lows, expected_length=n, field="ask_lows"),
        "ask_closes": _strategy_path_array(ask_closes, expected_length=n, field="ask_closes"),
    }
    supplied_quotes = [value is not None for value in quote_arrays.values()]
    if any(supplied_quotes) and not all(supplied_quotes) and strict_bid_ask:
        raise ValueError("strategy_path strict bid/ask execution requires all bid/ask OHLC arrays.")
    use_quotes = all(supplied_quotes)
    if use_quotes:
        if side_int > 0:
            entry_opens = quote_arrays["ask_opens"]
            path_opens = quote_arrays["bid_opens"]
            path_highs = quote_arrays["bid_highs"]
            path_lows = quote_arrays["bid_lows"]
            path_closes = quote_arrays["bid_closes"]
        else:
            entry_opens = quote_arrays["bid_opens"]
            path_opens = quote_arrays["ask_opens"]
            path_highs = quote_arrays["ask_highs"]
            path_lows = quote_arrays["ask_lows"]
            path_closes = quote_arrays["ask_closes"]
        execution_source = "bid_ask"
    else:
        entry_opens = opens
        path_opens = opens
        path_highs = highs
        path_lows = lows
        path_closes = closes
        execution_source = "midpoint_fallback"
    assert entry_opens is not None
    assert path_opens is not None and path_highs is not None and path_lows is not None and path_closes is not None

    entry_price = float(entry_opens[entry_idx])
    signal_atr = float(volatility[signal_idx])
    if not np.isfinite(entry_price) or entry_price <= 0.0:
        return _empty_strategy_path_outcome(signal_idx=signal_idx, side=side_int, exit_reason="invalid_entry")
    if not np.isfinite(signal_atr) or signal_atr <= 0.0:
        return _empty_strategy_path_outcome(
            signal_idx=signal_idx,
            side=side_int,
            exit_reason="invalid_volatility",
        )
    risk_distance = float(stop_loss_atr) * signal_atr
    initial_stop = entry_price - side_int * risk_distance
    emergency_profit = entry_price + side_int * float(emergency_profit_r) * risk_distance
    if initial_stop <= 0.0 or emergency_profit <= 0.0:
        return _empty_strategy_path_outcome(
            signal_idx=signal_idx,
            side=side_int,
            exit_reason="invalid_barrier",
        )

    effective_stop = float(initial_stop)
    highest_price = float(entry_price)
    lowest_price = float(entry_price)
    max_favorable_r = 0.0
    max_adverse_r = 0.0
    time_to_mfe = 0
    time_to_mae = 0
    trailing_activated = False
    scheduled_trend_flip = False
    exit_idx: int | None = None
    exit_price = np.nan
    exit_reason = "max_holding_exit"
    hit_type = "max_holding"
    exit_at_open = False
    gap_exit = False

    for idx in range(entry_idx, max_exit_idx + 1):
        bar_open = float(path_opens[idx])
        bar_high = float(path_highs[idx])
        bar_low = float(path_lows[idx])
        bar_close = float(path_closes[idx])
        if not all(np.isfinite(value) and value > 0.0 for value in (bar_open, bar_high, bar_low, bar_close)):
            return _empty_strategy_path_outcome(
                signal_idx=signal_idx,
                side=side_int,
                exit_reason="invalid_execution_quote" if use_quotes else "invalid_price_path",
            )

        if scheduled_trend_flip:
            exit_idx = idx
            exit_price = bar_open
            exit_reason = "trend_flip_exit"
            hit_type = "trend_flip"
            exit_at_open = True
            break

        # Excursions include the execution bar, but the current bar's extrema
        # cannot update the stop before this bar's barrier checks.  This keeps
        # diagnostics complete without introducing an OHLC-ordering lookahead.
        prospective_highest = max(highest_price, bar_high)
        prospective_lowest = min(lowest_price, bar_low)
        favorable_r = (
            (prospective_highest - entry_price) / risk_distance
            if side_int > 0
            else (entry_price - prospective_lowest) / risk_distance
        )
        adverse_r = (
            (prospective_lowest - entry_price) / risk_distance
            if side_int > 0
            else (entry_price - prospective_highest) / risk_distance
        )
        if float(favorable_r) > max_favorable_r:
            max_favorable_r = float(favorable_r)
            time_to_mfe = int(idx - entry_idx)
        if float(adverse_r) < max_adverse_r:
            max_adverse_r = float(adverse_r)
            time_to_mae = int(idx - entry_idx)

        prior_stop = float(effective_stop)
        if side_int > 0:
            stop_gap = bar_open <= prior_stop
            profit_gap = bar_open >= emergency_profit
        else:
            stop_gap = bar_open >= prior_stop
            profit_gap = bar_open <= emergency_profit
        if stop_gap or profit_gap:
            exit_idx = idx
            exit_price = bar_open
            exit_reason = "trailing_stop" if stop_gap and prior_stop != initial_stop else "stop_loss" if stop_gap else "emergency_profit"
            hit_type = "stop" if stop_gap else "emergency_profit"
            exit_at_open = True
            gap_exit = True
            break

        if side_int > 0:
            stop_hit = bar_low <= prior_stop
            profit_hit = bar_high >= emergency_profit
        else:
            stop_hit = bar_high >= prior_stop
            profit_hit = bar_low <= emergency_profit
        if stop_hit and profit_hit:
            resolved_price, resolved_reason = _double_touch_exit(
                tie_break=tie_break,
                bar_open=bar_open,
                effective_stop_price=prior_stop,
                take_profit_price=emergency_profit,
                stop_reason="trailing_stop" if prior_stop != initial_stop else "stop_loss",
            )
            exit_idx = idx
            exit_price = float(resolved_price)
            exit_reason = "emergency_profit" if resolved_reason == "take_profit" else str(resolved_reason)
            hit_type = "emergency_profit" if resolved_reason == "take_profit" else "stop"
            break
        if stop_hit:
            exit_idx = idx
            exit_price = prior_stop
            exit_reason = "trailing_stop" if prior_stop != initial_stop else "stop_loss"
            hit_type = "stop"
            break
        if profit_hit:
            exit_idx = idx
            exit_price = emergency_profit
            exit_reason = "emergency_profit"
            hit_type = "emergency_profit"
            break

        highest_price = prospective_highest
        lowest_price = prospective_lowest

        if max_favorable_r >= float(trailing_activation_r):
            current_atr = float(volatility[idx])
            if np.isfinite(current_atr) and current_atr > 0.0:
                trailing_activated = True
                if side_int > 0:
                    candidate_stop = highest_price - float(trailing_distance_atr) * current_atr
                    effective_stop = max(effective_stop, float(candidate_stop))
                else:
                    candidate_stop = lowest_price + float(trailing_distance_atr) * current_atr
                    effective_stop = min(effective_stop, float(candidate_stop))

        if idx < max_exit_idx:
            current_trend = float(trend_score[idx])
            if np.isfinite(current_trend) and (
                (side_int > 0 and current_trend <= 0.0)
                or (side_int < 0 and current_trend >= 0.0)
            ):
                scheduled_trend_flip = True
                continue

        if idx == max_exit_idx:
            exit_idx = idx
            exit_price = bar_close
            exit_reason = "max_holding_exit" if requested_exit_idx < n else "end_of_data_exit"
            hit_type = "max_holding" if requested_exit_idx < n else "end_of_data"
            break

    if exit_idx is None or not np.isfinite(exit_price) or exit_price <= 0.0:
        return _empty_strategy_path_outcome(
            signal_idx=signal_idx,
            side=side_int,
            exit_reason="unavailable_exit",
        )

    pnl = compute_trade_pnl(
        side=side_int,
        weight=1.0,
        entry_price=entry_price,
        exit_price=float(exit_price),
        risk_distance=risk_distance,
        cost_per_unit_turnover=cost_per_unit_turnover,
        slippage_per_unit_turnover=slippage_per_unit_turnover,
    )
    return {
        "valid": True,
        "signal_idx": int(signal_idx),
        "entry_idx": int(entry_idx),
        "exit_idx": int(exit_idx),
        "side": int(side_int),
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "initial_stop_price": float(initial_stop),
        "emergency_profit_price": float(emergency_profit),
        "effective_stop_price": float(effective_stop),
        "risk_distance": float(risk_distance),
        "gross_return": float(pnl["gross_return"]),
        "net_return": float(pnl["net_return"]),
        "gross_r": float(pnl["gross_r"]),
        "net_r": float(pnl["net_r"]),
        "transaction_cost_r": float(pnl["transaction_cost_r"]),
        "max_favorable_r": float(max_favorable_r),
        "max_adverse_r": float(max_adverse_r),
        "time_to_mfe": int(time_to_mfe),
        "time_to_mae": int(time_to_mae),
        "bars_held": int(exit_idx - entry_idx + 1),
        "hit_step": int(exit_idx - entry_idx),
        "exit_reason": str(exit_reason),
        "hit_type": str(hit_type),
        "execution_source": execution_source,
        "exit_at_open": bool(exit_at_open),
        "gap_exit": bool(gap_exit),
        "trailing_activated": bool(trailing_activated),
    }


def simulate_barrier_trade_outcome(
    *,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    signals: np.ndarray | None,
    signal_idx: int,
    side: int | float,
    take_profit_r: float,
    stop_loss_r: float,
    risk_per_trade: float = 0.006,
    max_holding_bars: int | None = 16,
    cost_per_unit_turnover: float = 0.0,
    slippage_per_unit_turnover: float = 0.0,
    max_leverage: float = 1.0,
    stop_mode: str = "fixed_return",
    volatility: np.ndarray | None = None,
    vol_col: str | None = None,
    forecasts: np.ndarray | None = None,
    long_trend_break: np.ndarray | None = None,
    short_trend_break: np.ndarray | None = None,
    dynamic_exits: Mapping[str, Any] | None = None,
    entry_price_mode: str = "next_open",
    tie_break: str = "conservative",
    allow_partial_horizon: bool = True,
    apply_risk_sizing: bool = True,
    signal_size: float | None = None,
    legacy_same_bar_stop_reason: bool = False,
) -> dict[str, Any]:
    """
    Simulate one manual-barrier trade and compute side-oriented return/R outcomes.

    The causal default matches ``manual_barrier``: the signal is observed on bar
    ``signal_idx`` and the trade enters at the next bar open. The lower-level
    long/short path helpers still own intrabar barrier handling; this wrapper
    centralizes entry/exit levels, costs, slippage, and R accounting for both
    backtests and path-dependent targets.
    """
    n = len(opens)
    if not (len(highs) == len(lows) == len(closes) == n):
        raise ValueError("opens/highs/lows/closes must have the same length.")
    side_int = 1 if float(side) > 0.0 else -1 if float(side) < 0.0 else 0
    if side_int == 0:
        return _empty_barrier_outcome(signal_idx=signal_idx, side=0, exit_reason="no_side")
    if stop_mode not in {"fixed_return", "volatility_stop"}:
        raise ValueError("stop_mode must be 'fixed_return' or 'volatility_stop'.")
    if entry_price_mode not in {"next_open", "current_close"}:
        raise ValueError("entry_price_mode must be 'next_open' or 'current_close'.")
    if max_holding_bars is not None and int(max_holding_bars) <= 0:
        raise ValueError("max_holding_bars must be positive when provided.")
    if float(take_profit_r) <= 0.0 or float(stop_loss_r) <= 0.0:
        raise ValueError("take_profit_r and stop_loss_r must be positive.")
    if float(risk_per_trade) <= 0.0:
        raise ValueError("risk_per_trade must be positive.")
    if float(max_leverage) <= 0.0:
        raise ValueError("max_leverage must be positive.")
    if float(cost_per_unit_turnover) < 0.0 or float(slippage_per_unit_turnover) < 0.0:
        raise ValueError("cost_per_unit_turnover and slippage_per_unit_turnover must be >= 0.")

    signal_idx = int(signal_idx)
    if signal_idx < 0 or signal_idx >= n:
        return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="invalid_signal_idx")
    entry_idx = signal_idx + 1 if entry_price_mode == "next_open" else signal_idx
    if entry_idx >= n:
        return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="unavailable_tail")
    path_start_idx = entry_idx if entry_price_mode == "next_open" else signal_idx + 1
    if path_start_idx >= n:
        return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="unavailable_tail")

    if max_holding_bars is None:
        max_exit_idx = n - 1
    else:
        full_max_exit_idx = path_start_idx + int(max_holding_bars) - 1
        if full_max_exit_idx >= n and not allow_partial_horizon:
            return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="unavailable_tail")
        max_exit_idx = min(n - 1, full_max_exit_idx)

    raw_entry_price = float(opens[entry_idx] if entry_price_mode == "next_open" else closes[signal_idx])
    if not np.isfinite(raw_entry_price) or raw_entry_price <= 0.0:
        return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="invalid_entry")

    if stop_mode == "volatility_stop":
        if volatility is None:
            raise ValueError("volatility is required when stop_mode='volatility_stop'.")
        signal_volatility = float(volatility[signal_idx]) if signal_idx < len(volatility) else np.nan
        if not np.isfinite(signal_volatility) or signal_volatility <= 0.0:
            return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="invalid_volatility")
        stop_distance_pct = max(signal_volatility * float(stop_loss_r), 1e-8)
        target_distance_pct = max(signal_volatility * float(take_profit_r), 1e-8)
        risk_sized_cap = float(risk_per_trade) / stop_distance_pct
    else:
        stop_distance_pct = max(float(risk_per_trade) * float(stop_loss_r), 1e-8)
        target_distance_pct = max(float(risk_per_trade) * float(take_profit_r), 1e-8)
        risk_sized_cap = float(max_leverage)

    requested_size = abs(float(signal_size)) if signal_size is not None else float(max_leverage)
    if not np.isfinite(requested_size) or requested_size <= 0.0:
        return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="invalid_size")
    if apply_risk_sizing:
        size = min(requested_size, risk_sized_cap, float(max_leverage))
    else:
        size = min(requested_size, float(max_leverage))
    if not np.isfinite(size) or size <= 0.0:
        return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="invalid_size")

    if side_int < 0:
        stop_price = raw_entry_price * (1.0 + stop_distance_pct)
        take_profit_price = raw_entry_price * (1.0 - target_distance_pct)
        path = simulate_short_trade_path(
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            signals=signals,
            entry_idx=path_start_idx,
            max_exit_idx=max_exit_idx,
            entry_price=raw_entry_price,
            initial_stop_price=stop_price,
            take_profit_price=take_profit_price,
            dynamic_exits=dynamic_exits,
            forecasts=forecasts,
            short_trend_break=short_trend_break,
            volatility=volatility,
            tie_break=tie_break,
            legacy_same_bar_stop_reason=legacy_same_bar_stop_reason,
        )
    else:
        stop_price = raw_entry_price * (1.0 - stop_distance_pct)
        take_profit_price = raw_entry_price * (1.0 + target_distance_pct)
        path = simulate_long_trade_path(
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            signals=signals,
            entry_idx=path_start_idx,
            max_exit_idx=max_exit_idx,
            entry_price=raw_entry_price,
            initial_stop_price=stop_price,
            take_profit_price=take_profit_price,
            dynamic_exits=dynamic_exits,
            forecasts=forecasts,
            long_trend_break=long_trend_break,
            volatility=volatility,
            tie_break=tie_break,
            legacy_same_bar_stop_reason=legacy_same_bar_stop_reason,
        )

    exit_idx = int(path["exit_idx"])
    raw_exit_price = float(path["raw_exit_price"])
    if not np.isfinite(raw_exit_price) or raw_exit_price <= 0.0:
        return _empty_barrier_outcome(signal_idx=signal_idx, side=side_int, exit_reason="invalid_exit")

    is_short = side_int < 0
    slip = float(slippage_per_unit_turnover)
    entry_price = raw_entry_price * (1.0 - slip) if is_short else raw_entry_price * (1.0 + slip)
    exit_price = raw_exit_price * (1.0 + slip) if is_short else raw_exit_price * (1.0 - slip)
    gross_return = size * leg_raw_return(
        is_short=is_short,
        entry_price=raw_entry_price,
        exit_price=raw_exit_price,
    )
    gross_after_slippage = size * leg_slippage_adjusted_return(
        is_short=is_short,
        entry_price=raw_entry_price,
        exit_price=raw_exit_price,
        slippage_per_unit_turnover=slip,
    )
    slippage_drag = max(gross_return - gross_after_slippage, 0.0)
    fixed_cost = size * 2.0 * float(cost_per_unit_turnover)
    total_cost = fixed_cost + slippage_drag
    net_return = gross_return - total_cost
    risk_capital = max(size * stop_distance_pct, 1e-12)

    return {
        "valid": True,
        "signal_idx": int(signal_idx),
        "entry_idx": int(entry_idx),
        "path_start_idx": int(path_start_idx),
        "exit_idx": int(exit_idx),
        "side": int(side_int),
        "side_name": "short" if is_short else "long",
        "raw_entry_price": float(raw_entry_price),
        "raw_exit_price": float(raw_exit_price),
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "stop_loss_price": float(stop_price),
        "take_profit_price": float(take_profit_price),
        "effective_stop_price": float(path["effective_stop_price"]),
        "exit_reason": str(path["exit_reason"]),
        "hit_type": str(path["exit_reason"]),
        "hit_step": int(exit_idx - entry_idx),
        "bars_held": int(path["bars_held"]),
        "size": float(size),
        "stop_distance_pct": float(stop_distance_pct),
        "target_distance_pct": float(target_distance_pct),
        "gross_return": float(gross_return),
        "net_return": float(net_return),
        "gross_r": float(gross_return / risk_capital),
        "net_r": float(net_return / risk_capital),
        "cost_paid": float(total_cost),
        "slippage_drag": float(slippage_drag),
        "max_favorable_r": float(path["max_favorable_r"]),
        "max_adverse_r": float(path["max_adverse_r"]),
        "breakeven_activated": bool(path["breakeven_activated"]),
        "profit_lock_activated": bool(path["profit_lock_activated"]),
    }


def simulate_long_trade_path(
    *,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    signals: np.ndarray | None,
    entry_idx: int,
    max_exit_idx: int,
    entry_price: float,
    initial_stop_price: float,
    take_profit_price: float,
    dynamic_exits: Mapping[str, Any] | None = None,
    partial_exits: Mapping[str, Any] | None = None,
    forecasts: np.ndarray | None = None,
    long_trend_break: np.ndarray | None = None,
    volatility: np.ndarray | None = None,
    tie_break: str = "conservative",
    legacy_same_bar_stop_reason: bool = False,
) -> dict[str, Any]:
    """
    Simulate one long trade path from entry bar through the maximum holding bar.

    The helper is intentionally direction-specific. The current ROC experiment is long-only and
    the caller controls candidate generation and entry timing.
    """
    if entry_idx < 0 or max_exit_idx < entry_idx:
        raise ValueError("entry_idx/max_exit_idx define an empty trade path.")
    if max_exit_idx >= len(opens):
        raise ValueError("max_exit_idx is outside the supplied price arrays.")

    entry = float(entry_price)
    stop = float(initial_stop_price)
    take_profit = float(take_profit_price)
    risk_distance = entry - stop
    if not np.isfinite(entry) or entry <= 0.0:
        raise ValueError("entry_price must be a finite positive price.")
    if not np.isfinite(risk_distance) or risk_distance <= 0.0:
        raise ValueError("initial_stop_price must be below entry_price for a long trade.")
    if not np.isfinite(take_profit) or take_profit <= entry:
        raise ValueError("take_profit_price must be above entry_price for a long trade.")

    dynamic_cfg = normalize_dynamic_exit_config(dynamic_exits)
    partial_cfg = normalize_partial_exit_config(partial_exits)
    partial_rules = list(partial_cfg["rules"]) if partial_cfg["enabled"] else []
    partial_rule_fired = [False] * len(partial_rules)
    partial_exit_events: list[dict[str, Any]] = []
    effective_stop_price = stop
    stop_reason = "stop_loss"
    breakeven_activated = False
    profit_lock_activated = False
    max_favorable_r = 0.0
    max_adverse_r = 0.0
    bars_held = 0
    exit_idx: int | None = None
    raw_exit_price = np.nan
    exit_reason = "max_holding_close"

    for idx in range(entry_idx, max_exit_idx + 1):
        bar_open = float(opens[idx])
        bar_high = float(highs[idx])
        bar_low = float(lows[idx])
        bar_close = float(closes[idx])
        if not all(np.isfinite(value) for value in (bar_open, bar_high, bar_low, bar_close)):
            continue

        bars_held += 1
        bar_favorable_r = float((bar_high - entry) / risk_distance)
        bar_adverse_r = float((bar_low - entry) / risk_distance)
        max_favorable_r = max(max_favorable_r, bar_favorable_r)
        max_adverse_r = min(max_adverse_r, bar_adverse_r)
        prior_stop_price = effective_stop_price
        prior_stop_reason = stop_reason

        if bar_open <= prior_stop_price:
            exit_idx = idx
            raw_exit_price = bar_open
            exit_reason = prior_stop_reason
            break
        if bar_open >= take_profit:
            exit_idx = idx
            raw_exit_price = bar_open
            exit_reason = "take_profit"
            break

        stop_hit = bar_low <= prior_stop_price
        take_profit_hit = bar_high >= take_profit
        partial_rule_hits = [
            (rule_idx, rule, entry + float(rule["trigger_r"]) * risk_distance)
            for rule_idx, rule in enumerate(partial_rules)
            if not partial_rule_fired[rule_idx]
            and bar_high >= entry + float(rule["trigger_r"]) * risk_distance
        ]
        if stop_hit and take_profit_hit:
            exit_idx = idx
            raw_exit_price, exit_reason = _double_touch_exit(
                tie_break=tie_break,
                bar_open=bar_open,
                effective_stop_price=prior_stop_price,
                take_profit_price=take_profit,
                stop_reason=prior_stop_reason,
            )
            if legacy_same_bar_stop_reason and exit_reason == "stop_loss":
                exit_reason = "stop_and_target_same_bar_stop_first"
            break
        if stop_hit:
            exit_idx = idx
            raw_exit_price = prior_stop_price
            exit_reason = prior_stop_reason
            break
        if take_profit_hit:
            for rule_idx, rule, trigger_price in partial_rule_hits:
                partial_idx, partial_price = _partial_exit_price(
                    mode=str(rule["exit_price"]),
                    trigger_price=trigger_price,
                    current_idx=idx,
                    opens=opens,
                    closes=closes,
                )
                if partial_idx > idx:
                    continue
                partial_rule_fired[rule_idx] = True
                partial_exit_events.append(
                    {
                        "rule_index": int(rule_idx),
                        "trigger_r": float(rule["trigger_r"]),
                        "fraction": float(rule["fraction"]),
                        "exit_idx": int(partial_idx),
                        "raw_exit_price": float(partial_price),
                    }
                )
            exit_idx = idx
            raw_exit_price = take_profit
            exit_reason = "take_profit"
            break
        for rule_idx, rule, trigger_price in partial_rule_hits:
            partial_idx, partial_price = _partial_exit_price(
                mode=str(rule["exit_price"]),
                trigger_price=trigger_price,
                current_idx=idx,
                opens=opens,
                closes=closes,
            )
            partial_rule_fired[rule_idx] = True
            partial_exit_events.append(
                {
                    "rule_index": int(rule_idx),
                    "trigger_r": float(rule["trigger_r"]),
                    "fraction": float(rule["fraction"]),
                    "exit_idx": int(partial_idx),
                    "raw_exit_price": float(partial_price),
                }
            )

        if dynamic_cfg["breakeven"]["enabled"] and max_favorable_r >= dynamic_cfg["breakeven"]["trigger_r"]:
            breakeven_activated = True
            candidate_stop = entry + dynamic_cfg["breakeven"]["lock_r"] * risk_distance
            if candidate_stop > effective_stop_price:
                effective_stop_price = float(candidate_stop)
                stop_reason = "breakeven_stop"

        if dynamic_cfg["profit_lock"]["enabled"] and max_favorable_r >= dynamic_cfg["profit_lock"]["trigger_r"]:
            profit_lock_activated = True
            candidate_stop = entry + dynamic_cfg["profit_lock"]["lock_r"] * risk_distance
            if candidate_stop >= effective_stop_price:
                effective_stop_price = float(candidate_stop)
                stop_reason = "profit_lock_stop"

        atr_trailing = dynamic_cfg["atr_trailing"]
        if atr_trailing["enabled"] and max_favorable_r >= atr_trailing["activation_r"] and volatility is not None:
            current_volatility = float(volatility[idx]) if idx < len(volatility) else np.nan
            if np.isfinite(current_volatility) and current_volatility > 0.0:
                trailing_distance = entry * current_volatility * atr_trailing["distance_mult"]
                highest_price = entry + max_favorable_r * risk_distance
                candidate_stop = highest_price - trailing_distance
                if candidate_stop >= effective_stop_price:
                    effective_stop_price = float(candidate_stop)
                    stop_reason = "atr_trailing_stop"

        signal_off = dynamic_cfg["signal_off_exit"]
        if signal_off["enabled"] and bars_held >= signal_off["min_bars_held"] and signals is not None:
            current_signal = float(signals[idx]) if idx < len(signals) and np.isfinite(float(signals[idx])) else 0.0
            if current_signal <= 0.0:
                exit_idx, raw_exit_price = _exit_on_price_mode(
                    mode=signal_off["exit_price"],
                    current_idx=idx,
                    opens=opens,
                    closes=closes,
                )
                exit_reason = "signal_off_exit"
                break

        forecast_decay = dynamic_cfg["forecast_decay"]
        if forecast_decay["enabled"] and bars_held >= forecast_decay["min_bars_held"] and forecasts is not None:
            current_forecast = float(forecasts[idx]) if idx < len(forecasts) else np.nan
            if np.isfinite(current_forecast) and current_forecast <= forecast_decay["long_exit_threshold"]:
                exit_payload = _dynamic_exit_on_price_mode(
                    mode=forecast_decay["exit_price"],
                    current_idx=idx,
                    max_exit_idx=max_exit_idx,
                    opens=opens,
                    closes=closes,
                )
                if exit_payload is not None:
                    exit_idx, raw_exit_price = exit_payload
                    exit_reason = "forecast_decay_exit"
                    break

        trend_break = dynamic_cfg["trend_break"]
        if (
            trend_break["enabled"]
            and bars_held >= trend_break["min_bars_held"]
            and forecasts is not None
            and long_trend_break is not None
        ):
            current_forecast = float(forecasts[idx]) if idx < len(forecasts) else np.nan
            disagreement = bool(long_trend_break[idx]) if idx < len(long_trend_break) else False
            if (
                disagreement
                and np.isfinite(current_forecast)
                and current_forecast <= trend_break["long_weakening_level"]
            ):
                exit_payload = _dynamic_exit_on_price_mode(
                    mode=trend_break["exit_price"],
                    current_idx=idx,
                    max_exit_idx=max_exit_idx,
                    opens=opens,
                    closes=closes,
                )
                if exit_payload is not None:
                    exit_idx, raw_exit_price = exit_payload
                    exit_reason = "trend_break_exit"
                    break

        no_progress = dynamic_cfg["no_progress"]
        if (
            no_progress["enabled"]
            and bars_held >= no_progress["bars"]
            and max_favorable_r < no_progress["min_favorable_r"]
        ):
            exit_idx, raw_exit_price = _exit_on_price_mode(
                mode=no_progress["exit_price"],
                current_idx=idx,
                opens=opens,
                closes=closes,
            )
            exit_reason = "no_progress_exit"
            break

    if exit_idx is None:
        exit_idx = int(max_exit_idx)
        raw_exit_price = float(closes[exit_idx])
        exit_reason = "max_holding_close"

    return {
        "exit_idx": int(exit_idx),
        "raw_exit_price": float(raw_exit_price),
        "exit_reason": str(exit_reason),
        "bars_held": int(bars_held),
        "max_favorable_r": float(max_favorable_r),
        "max_adverse_r": float(max_adverse_r),
        "breakeven_activated": bool(breakeven_activated),
        "profit_lock_activated": bool(profit_lock_activated),
        "effective_stop_price": float(effective_stop_price),
        "partial_exits": partial_exit_events,
    }


def simulate_short_trade_path(
    *,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    signals: np.ndarray | None,
    entry_idx: int,
    max_exit_idx: int,
    entry_price: float,
    initial_stop_price: float,
    take_profit_price: float,
    dynamic_exits: Mapping[str, Any] | None = None,
    partial_exits: Mapping[str, Any] | None = None,
    forecasts: np.ndarray | None = None,
    short_trend_break: np.ndarray | None = None,
    volatility: np.ndarray | None = None,
    tie_break: str = "conservative",
    legacy_same_bar_stop_reason: bool = False,
) -> dict[str, Any]:
    """
    Simulate one short trade path from entry bar through the maximum holding bar.
    """
    if entry_idx < 0 or max_exit_idx < entry_idx:
        raise ValueError("entry_idx/max_exit_idx define an empty trade path.")
    if max_exit_idx >= len(opens):
        raise ValueError("max_exit_idx is outside the supplied price arrays.")

    entry = float(entry_price)
    stop = float(initial_stop_price)
    take_profit = float(take_profit_price)
    risk_distance = stop - entry
    if not np.isfinite(entry) or entry <= 0.0:
        raise ValueError("entry_price must be a finite positive price.")
    if not np.isfinite(risk_distance) or risk_distance <= 0.0:
        raise ValueError("initial_stop_price must be above entry_price for a short trade.")
    if not np.isfinite(take_profit) or take_profit >= entry:
        raise ValueError("take_profit_price must be below entry_price for a short trade.")

    dynamic_cfg = normalize_dynamic_exit_config(dynamic_exits)
    partial_cfg = normalize_partial_exit_config(partial_exits)
    partial_rules = list(partial_cfg["rules"]) if partial_cfg["enabled"] else []
    partial_rule_fired = [False] * len(partial_rules)
    partial_exit_events: list[dict[str, Any]] = []
    effective_stop_price = stop
    stop_reason = "stop_loss"
    breakeven_activated = False
    profit_lock_activated = False
    max_favorable_r = 0.0
    max_adverse_r = 0.0
    bars_held = 0
    exit_idx: int | None = None
    raw_exit_price = np.nan
    exit_reason = "max_holding_close"

    for idx in range(entry_idx, max_exit_idx + 1):
        bar_open = float(opens[idx])
        bar_high = float(highs[idx])
        bar_low = float(lows[idx])
        bar_close = float(closes[idx])
        if not all(np.isfinite(value) for value in (bar_open, bar_high, bar_low, bar_close)):
            continue

        bars_held += 1
        bar_favorable_r = float((entry - bar_low) / risk_distance)
        bar_adverse_r = float((entry - bar_high) / risk_distance)
        max_favorable_r = max(max_favorable_r, bar_favorable_r)
        max_adverse_r = min(max_adverse_r, bar_adverse_r)
        prior_stop_price = effective_stop_price
        prior_stop_reason = stop_reason

        if bar_open >= prior_stop_price:
            exit_idx = idx
            raw_exit_price = bar_open
            exit_reason = prior_stop_reason
            break
        if bar_open <= take_profit:
            exit_idx = idx
            raw_exit_price = bar_open
            exit_reason = "take_profit"
            break

        stop_hit = bar_high >= prior_stop_price
        take_profit_hit = bar_low <= take_profit
        partial_rule_hits = [
            (rule_idx, rule, entry - float(rule["trigger_r"]) * risk_distance)
            for rule_idx, rule in enumerate(partial_rules)
            if not partial_rule_fired[rule_idx]
            and bar_low <= entry - float(rule["trigger_r"]) * risk_distance
        ]
        if stop_hit and take_profit_hit:
            exit_idx = idx
            raw_exit_price, exit_reason = _double_touch_exit(
                tie_break=tie_break,
                bar_open=bar_open,
                effective_stop_price=prior_stop_price,
                take_profit_price=take_profit,
                stop_reason=prior_stop_reason,
            )
            if legacy_same_bar_stop_reason and exit_reason == "stop_loss":
                exit_reason = "stop_and_target_same_bar_stop_first"
            break
        if stop_hit:
            exit_idx = idx
            raw_exit_price = prior_stop_price
            exit_reason = prior_stop_reason
            break
        if take_profit_hit:
            for rule_idx, rule, trigger_price in partial_rule_hits:
                partial_idx, partial_price = _partial_exit_price(
                    mode=str(rule["exit_price"]),
                    trigger_price=trigger_price,
                    current_idx=idx,
                    opens=opens,
                    closes=closes,
                )
                if partial_idx > idx:
                    continue
                partial_rule_fired[rule_idx] = True
                partial_exit_events.append(
                    {
                        "rule_index": int(rule_idx),
                        "trigger_r": float(rule["trigger_r"]),
                        "fraction": float(rule["fraction"]),
                        "exit_idx": int(partial_idx),
                        "raw_exit_price": float(partial_price),
                    }
                )
            exit_idx = idx
            raw_exit_price = take_profit
            exit_reason = "take_profit"
            break
        for rule_idx, rule, trigger_price in partial_rule_hits:
            partial_idx, partial_price = _partial_exit_price(
                mode=str(rule["exit_price"]),
                trigger_price=trigger_price,
                current_idx=idx,
                opens=opens,
                closes=closes,
            )
            partial_rule_fired[rule_idx] = True
            partial_exit_events.append(
                {
                    "rule_index": int(rule_idx),
                    "trigger_r": float(rule["trigger_r"]),
                    "fraction": float(rule["fraction"]),
                    "exit_idx": int(partial_idx),
                    "raw_exit_price": float(partial_price),
                }
            )

        if dynamic_cfg["breakeven"]["enabled"] and max_favorable_r >= dynamic_cfg["breakeven"]["trigger_r"]:
            breakeven_activated = True
            candidate_stop = entry - dynamic_cfg["breakeven"]["lock_r"] * risk_distance
            if candidate_stop < effective_stop_price:
                effective_stop_price = float(candidate_stop)
                stop_reason = "breakeven_stop"

        if dynamic_cfg["profit_lock"]["enabled"] and max_favorable_r >= dynamic_cfg["profit_lock"]["trigger_r"]:
            profit_lock_activated = True
            candidate_stop = entry - dynamic_cfg["profit_lock"]["lock_r"] * risk_distance
            if candidate_stop <= effective_stop_price:
                effective_stop_price = float(candidate_stop)
                stop_reason = "profit_lock_stop"

        atr_trailing = dynamic_cfg["atr_trailing"]
        if atr_trailing["enabled"] and max_favorable_r >= atr_trailing["activation_r"] and volatility is not None:
            current_volatility = float(volatility[idx]) if idx < len(volatility) else np.nan
            if np.isfinite(current_volatility) and current_volatility > 0.0:
                trailing_distance = entry * current_volatility * atr_trailing["distance_mult"]
                lowest_price = entry - max_favorable_r * risk_distance
                candidate_stop = lowest_price + trailing_distance
                if candidate_stop <= effective_stop_price:
                    effective_stop_price = float(candidate_stop)
                    stop_reason = "atr_trailing_stop"

        signal_off = dynamic_cfg["signal_off_exit"]
        if signal_off["enabled"] and bars_held >= signal_off["min_bars_held"] and signals is not None:
            current_signal = float(signals[idx]) if idx < len(signals) and np.isfinite(float(signals[idx])) else 0.0
            if current_signal >= 0.0:
                exit_idx, raw_exit_price = _exit_on_price_mode(
                    mode=signal_off["exit_price"],
                    current_idx=idx,
                    opens=opens,
                    closes=closes,
                )
                exit_reason = "signal_off_exit"
                break

        forecast_decay = dynamic_cfg["forecast_decay"]
        if forecast_decay["enabled"] and bars_held >= forecast_decay["min_bars_held"] and forecasts is not None:
            current_forecast = float(forecasts[idx]) if idx < len(forecasts) else np.nan
            if np.isfinite(current_forecast) and current_forecast >= forecast_decay["short_exit_threshold"]:
                exit_payload = _dynamic_exit_on_price_mode(
                    mode=forecast_decay["exit_price"],
                    current_idx=idx,
                    max_exit_idx=max_exit_idx,
                    opens=opens,
                    closes=closes,
                )
                if exit_payload is not None:
                    exit_idx, raw_exit_price = exit_payload
                    exit_reason = "forecast_decay_exit"
                    break

        trend_break = dynamic_cfg["trend_break"]
        if (
            trend_break["enabled"]
            and bars_held >= trend_break["min_bars_held"]
            and forecasts is not None
            and short_trend_break is not None
        ):
            current_forecast = float(forecasts[idx]) if idx < len(forecasts) else np.nan
            disagreement = bool(short_trend_break[idx]) if idx < len(short_trend_break) else False
            if (
                disagreement
                and np.isfinite(current_forecast)
                and current_forecast >= trend_break["short_weakening_level"]
            ):
                exit_payload = _dynamic_exit_on_price_mode(
                    mode=trend_break["exit_price"],
                    current_idx=idx,
                    max_exit_idx=max_exit_idx,
                    opens=opens,
                    closes=closes,
                )
                if exit_payload is not None:
                    exit_idx, raw_exit_price = exit_payload
                    exit_reason = "trend_break_exit"
                    break

        no_progress = dynamic_cfg["no_progress"]
        if (
            no_progress["enabled"]
            and bars_held >= no_progress["bars"]
            and max_favorable_r < no_progress["min_favorable_r"]
        ):
            exit_idx, raw_exit_price = _exit_on_price_mode(
                mode=no_progress["exit_price"],
                current_idx=idx,
                opens=opens,
                closes=closes,
            )
            exit_reason = "no_progress_exit"
            break

    if exit_idx is None:
        exit_idx = int(max_exit_idx)
        raw_exit_price = float(closes[exit_idx])
        exit_reason = "max_holding_close"

    return {
        "exit_idx": int(exit_idx),
        "raw_exit_price": float(raw_exit_price),
        "exit_reason": str(exit_reason),
        "bars_held": int(bars_held),
        "max_favorable_r": float(max_favorable_r),
        "max_adverse_r": float(max_adverse_r),
        "breakeven_activated": bool(breakeven_activated),
        "profit_lock_activated": bool(profit_lock_activated),
        "effective_stop_price": float(effective_stop_price),
        "partial_exits": partial_exit_events,
    }


__all__ = [
    "compute_trade_pnl",
    "leg_raw_return",
    "leg_slippage_adjusted_return",
    "normalize_dynamic_exit_config",
    "normalize_partial_exit_config",
    "simulate_barrier_trade_outcome",
    "simulate_long_trade_path",
    "simulate_short_trade_path",
    "simulate_strategy_path_trade_outcome",
]
