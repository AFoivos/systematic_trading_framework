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
        "breakeven": {"enabled": False, "trigger_r": 0.8, "lock_r": 0.0},
        "profit_lock": {"enabled": False, "trigger_r": 1.2, "lock_r": 0.3},
        "atr_trailing": {"enabled": False, "activation_r": 0.0, "distance_mult": 1.0},
        "no_progress": {"enabled": False, "bars": 6, "min_favorable_r": 0.2, "exit_price": "close"},
    }
    if not enabled:
        return disabled_defaults

    signal_off = dict(cfg.get("signal_off_exit", {}) or {})
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

    for path in ("signal_off_exit", "no_progress"):
        exit_price = out[path]["exit_price"]
        if exit_price not in {"close", "next_open"}:
            raise ValueError(f"dynamic_exits.{path}.exit_price must be 'close' or 'next_open'.")
    if out["signal_off_exit"]["min_bars_held"] < 0:
        raise ValueError("dynamic_exits.signal_off_exit.min_bars_held must be >= 0.")
    if out["no_progress"]["bars"] <= 0:
        raise ValueError("dynamic_exits.no_progress.bars must be > 0.")
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
        max_favorable_r = max(max_favorable_r, float((bar_high - entry) / risk_distance))
        max_adverse_r = min(max_adverse_r, float((bar_low - entry) / risk_distance))

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

        stop_hit = bar_low <= effective_stop_price
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
                effective_stop_price=effective_stop_price,
                take_profit_price=take_profit,
                stop_reason=stop_reason,
            )
            if legacy_same_bar_stop_reason and exit_reason == "stop_loss":
                exit_reason = "stop_and_target_same_bar_stop_first"
            break
        if stop_hit:
            exit_idx = idx
            raw_exit_price = effective_stop_price
            exit_reason = stop_reason
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
        max_favorable_r = max(max_favorable_r, float((entry - bar_low) / risk_distance))
        max_adverse_r = min(max_adverse_r, float((entry - bar_high) / risk_distance))

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

        stop_hit = bar_high >= effective_stop_price
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
                effective_stop_price=effective_stop_price,
                take_profit_price=take_profit,
                stop_reason=stop_reason,
            )
            if legacy_same_bar_stop_reason and exit_reason == "stop_loss":
                exit_reason = "stop_and_target_same_bar_stop_first"
            break
        if stop_hit:
            exit_idx = idx
            raw_exit_price = effective_stop_price
            exit_reason = stop_reason
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
    "normalize_dynamic_exit_config",
    "normalize_partial_exit_config",
    "simulate_long_trade_path",
    "simulate_short_trade_path",
]
