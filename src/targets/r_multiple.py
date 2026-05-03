from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


R_MULTIPLE_TARGET_OUTPUT_COLS = [
    "label",
    "r_target_event_ret",
    "r_target_trade_r",
    "r_target_oriented_r",
    "r_target_candidate",
    "r_target_entry_price",
    "r_target_exit_price",
    "r_target_stop_price",
    "r_target_take_profit_price",
    "r_target_exit_reason",
    "r_target_bars_held",
    "r_target_hit_type",
    "r_target_hit_step",
]


def _flatten_cfg(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(target_cfg or {})
    params = cfg.pop("params", None)
    if params is not None:
        if not isinstance(params, dict):
            raise ValueError("r_multiple target params must be a mapping when provided.")
        cfg.update(dict(params))
    return cfg


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for r_multiple target: {missing}")


def _finite_positive(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"r_multiple target {field} must be a finite positive number.")
    return out


def _finite_number(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"r_multiple target {field} must be a finite number.")
    return out


def _resolve_double_touch(
    *,
    tie_break: str,
    bar_open: float,
    stop_price: float,
    take_profit_price: float,
) -> str:
    if tie_break in {"conservative", "stop_loss"}:
        return "stop_loss"
    if tie_break == "take_profit":
        return "take_profit"
    if tie_break == "closest_to_open":
        stop_distance = abs(float(bar_open) - float(stop_price))
        target_distance = abs(float(bar_open) - float(take_profit_price))
        if target_distance < stop_distance:
            return "take_profit"
        return "stop_loss"
    raise ValueError(
        "r_multiple target tie_break must be one of: conservative, take_profit, stop_loss, closest_to_open."
    )


def _numeric_quantile(values: pd.Series, q: float) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    if numeric.empty:
        return None
    return float(numeric.quantile(float(q)))


def _numeric_mean(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    if numeric.empty:
        return None
    return float(numeric.mean())


def _numeric_median(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    if numeric.empty:
        return None
    return float(numeric.median())


def _first_existing_with_prefix(columns: pd.Index, prefix: str) -> str | None:
    matches = [str(col) for col in columns if str(col).startswith(prefix)]
    return sorted(matches)[0] if matches else None


def _diagnostic_feature_columns(out: pd.DataFrame, cfg: dict[str, Any]) -> list[str]:
    configured = cfg.get("diagnostic_feature_cols")
    if configured is not None:
        if not isinstance(configured, list) or any(not isinstance(col, str) or not col for col in configured):
            raise ValueError("r_multiple target diagnostic_feature_cols must be a list[str].")
        return [col for col in configured if col in out.columns]

    candidates = [
        cfg.get("roc_col"),
        "roc_12",
        _first_existing_with_prefix(out.columns, "roc_"),
        cfg.get("regime_vol_ratio_z_col"),
        "regime_vol_ratio_z_24_168",
        _first_existing_with_prefix(out.columns, "regime_vol_ratio_z_"),
        "close_z",
        "close_open_ratio",
        "manual_conviction_score",
    ]
    resolved: list[str] = []
    seen: set[str] = set()
    for raw_col in candidates:
        if raw_col is None:
            continue
        col = str(raw_col)
        if col in out.columns and col not in seen:
            resolved.append(col)
            seen.add(col)
    return resolved


def _winner_loser_feature_summary(
    out: pd.DataFrame,
    *,
    label_col: str,
    feature_cols: list[str],
) -> dict[str, dict[str, Any]]:
    labeled = out[label_col].notna()
    winners = labeled & out[label_col].astype(float).eq(1.0)
    losers = labeled & out[label_col].astype(float).eq(0.0)
    summary: dict[str, dict[str, Any]] = {}
    for col in feature_cols:
        winner_values = pd.to_numeric(out.loc[winners, col], errors="coerce").dropna()
        loser_values = pd.to_numeric(out.loc[losers, col], errors="coerce").dropna()
        winner_mean = _numeric_mean(winner_values)
        loser_mean = _numeric_mean(loser_values)
        summary[col] = {
            "winner_rows": int(len(winner_values)),
            "loser_rows": int(len(loser_values)),
            "winner_mean": winner_mean,
            "loser_mean": loser_mean,
            "mean_diff": (
                float(winner_mean - loser_mean)
                if winner_mean is not None and loser_mean is not None
                else None
            ),
            "winner_median": _numeric_median(winner_values),
            "loser_median": _numeric_median(loser_values),
        }
    return summary


def build_r_multiple_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build a long-only R-multiple label for already-emitted manual strategy candidates.

    Candidate rows are labeled at the signal bar. With `entry_price_mode='next_open'`, the entry
    price is the next bar open and the forward path is used only for target construction.
    """
    cfg = _flatten_cfg(target_cfg)
    candidate_col = str(cfg.get("candidate_col", "manual_long_signal"))
    label_col = str(cfg.get("label_col", "label"))
    fwd_col = str(cfg.get("fwd_col", "r_target_event_ret"))
    candidate_out_col = str(cfg.get("candidate_out_col", "r_target_candidate"))
    price_col = str(cfg.get("price_col", "close"))
    open_col = str(cfg.get("open_col", "open"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    volatility_col = str(cfg.get("volatility_col", "vol_rolling_24"))
    entry_price_mode = str(cfg.get("entry_price_mode", "next_open"))
    side = str(cfg.get("side", "long_only"))
    target_r_min = _finite_number(cfg.get("target_r_min", 1.0), field="target_r_min")
    take_profit_r = _finite_positive(cfg.get("take_profit_r", 2.0), field="take_profit_r")
    stop_loss_r = _finite_positive(cfg.get("stop_loss_r", 1.0), field="stop_loss_r")
    max_holding_bars = int(cfg.get("max_holding_bars", cfg.get("max_holding", 16)))
    stop_mode = str(cfg.get("stop_mode", "volatility_stop"))
    stop_loss_return = _finite_positive(cfg.get("stop_loss_return", 0.005), field="stop_loss_return")
    take_profit_return = _finite_positive(cfg.get("take_profit_return", 0.010), field="take_profit_return")
    tie_break = str(cfg.get("tie_break", "conservative"))
    allow_partial_horizon = bool(cfg.get("allow_partial_horizon", False))

    if side != "long_only":
        raise ValueError("r_multiple target currently supports side='long_only' only.")
    if entry_price_mode not in {"next_open", "current_close"}:
        raise ValueError("r_multiple target entry_price_mode must be one of: next_open, current_close.")
    if max_holding_bars <= 0:
        raise ValueError("r_multiple target max_holding_bars must be positive.")
    if stop_mode not in {"volatility_stop", "fixed_return"}:
        raise ValueError("r_multiple target stop_mode must be one of: volatility_stop, fixed_return.")
    if tie_break not in {"conservative", "take_profit", "stop_loss", "closest_to_open"}:
        raise ValueError(
            "r_multiple target tie_break must be one of: conservative, take_profit, stop_loss, closest_to_open."
        )

    required = [candidate_col, price_col, open_col, high_col, low_col]
    if stop_mode == "volatility_stop":
        required.append(volatility_col)
    _require_columns(df, required)

    out = df.copy()
    n = len(out)
    prices = pd.to_numeric(out[price_col], errors="coerce").to_numpy(dtype=float)
    opens = pd.to_numeric(out[open_col], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(out[high_col], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(out[low_col], errors="coerce").to_numpy(dtype=float)
    vol_values = (
        pd.to_numeric(out[volatility_col], errors="coerce").to_numpy(dtype=float)
        if stop_mode == "volatility_stop"
        else np.full(n, np.nan, dtype=float)
    )
    candidates = pd.to_numeric(out[candidate_col], errors="coerce").fillna(0.0).to_numpy(dtype=float) > 0.0

    labels = np.full(n, np.nan, dtype=float)
    event_rets = np.full(n, np.nan, dtype=float)
    trade_rs = np.full(n, np.nan, dtype=float)
    entry_prices = np.full(n, np.nan, dtype=float)
    exit_prices = np.full(n, np.nan, dtype=float)
    stop_prices = np.full(n, np.nan, dtype=float)
    take_profit_prices = np.full(n, np.nan, dtype=float)
    bars_held_values = np.full(n, np.nan, dtype=float)
    hit_steps = np.full(n, np.nan, dtype=float)
    exit_reasons = np.full(n, None, dtype=object)

    for start_idx in range(n):
        if not candidates[start_idx]:
            continue

        entry_idx = start_idx + 1 if entry_price_mode == "next_open" else start_idx
        if entry_idx >= n:
            exit_reasons[start_idx] = "unavailable_tail"
            continue

        max_exit_idx = entry_idx + max_holding_bars - 1
        if max_exit_idx >= n:
            if not allow_partial_horizon:
                exit_reasons[start_idx] = "unavailable_tail"
                continue
            max_exit_idx = n - 1

        entry_price = float(opens[entry_idx] if entry_price_mode == "next_open" else prices[start_idx])
        if not np.isfinite(entry_price) or entry_price <= 0.0:
            exit_reasons[start_idx] = "invalid_entry"
            continue

        if stop_mode == "volatility_stop":
            volatility_value = float(vol_values[start_idx])
            if not np.isfinite(volatility_value) or volatility_value <= 0.0:
                exit_reasons[start_idx] = "invalid_entry"
                continue
            risk_distance_return = volatility_value * stop_loss_r
            take_profit_distance_return = risk_distance_return * take_profit_r / stop_loss_r
        else:
            risk_distance_return = stop_loss_return
            take_profit_distance_return = take_profit_return

        if not np.isfinite(risk_distance_return) or risk_distance_return <= 0.0:
            exit_reasons[start_idx] = "invalid_entry"
            continue
        if not np.isfinite(take_profit_distance_return) or take_profit_distance_return <= 0.0:
            exit_reasons[start_idx] = "invalid_entry"
            continue

        stop_price = entry_price * max(1.0 - risk_distance_return, 1e-12)
        take_profit_price = entry_price * (1.0 + take_profit_distance_return)
        entry_prices[start_idx] = entry_price
        stop_prices[start_idx] = stop_price
        take_profit_prices[start_idx] = take_profit_price

        exit_idx: int | None = None
        exit_price = np.nan
        exit_reason = "max_holding_close"
        for step_idx in range(entry_idx, max_exit_idx + 1):
            bar_low = float(lows[step_idx])
            bar_high = float(highs[step_idx])
            if not np.isfinite(bar_low) or not np.isfinite(bar_high):
                continue

            stop_hit = bar_low <= stop_price
            take_profit_hit = bar_high >= take_profit_price
            if stop_hit and take_profit_hit:
                exit_reason = _resolve_double_touch(
                    tie_break=tie_break,
                    bar_open=float(opens[step_idx]),
                    stop_price=stop_price,
                    take_profit_price=take_profit_price,
                )
                exit_idx = step_idx
                exit_price = stop_price if exit_reason == "stop_loss" else take_profit_price
                break
            if stop_hit:
                exit_idx = step_idx
                exit_price = stop_price
                exit_reason = "stop_loss"
                break
            if take_profit_hit:
                exit_idx = step_idx
                exit_price = take_profit_price
                exit_reason = "take_profit"
                break

        if exit_idx is None:
            exit_idx = max_exit_idx
            exit_price = float(prices[exit_idx])
            exit_reason = "max_holding_close"
            if not np.isfinite(exit_price) or exit_price <= 0.0:
                exit_reasons[start_idx] = "invalid_entry"
                continue

        trade_ret = exit_price / entry_price - 1.0
        trade_r = trade_ret / risk_distance_return
        event_rets[start_idx] = trade_ret
        trade_rs[start_idx] = trade_r
        exit_prices[start_idx] = exit_price
        bars_held_values[start_idx] = float(exit_idx - entry_idx + 1)
        hit_steps[start_idx] = float(exit_idx - entry_idx)
        exit_reasons[start_idx] = exit_reason
        labels[start_idx] = 1.0 if trade_r >= target_r_min else 0.0

    out[candidate_out_col] = candidates.astype("float32")
    out[fwd_col] = event_rets.astype("float32")
    out["r_target_trade_r"] = trade_rs.astype("float32")
    out["r_target_oriented_r"] = trade_rs.astype("float32")
    out["r_target_entry_price"] = entry_prices.astype("float64")
    out["r_target_exit_price"] = exit_prices.astype("float64")
    out["r_target_stop_price"] = stop_prices.astype("float64")
    out["r_target_take_profit_price"] = take_profit_prices.astype("float64")
    out["r_target_exit_reason"] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out["r_target_bars_held"] = bars_held_values.astype("float32")
    out["r_target_hit_type"] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out["r_target_hit_step"] = hit_steps.astype("float32")
    out[label_col] = labels.astype("float32")

    label_series = pd.Series(labels, index=out.index)
    valid_labels = label_series.notna()
    trade_r_series = pd.Series(trade_rs, index=out.index)
    valid_trade_r = trade_r_series.dropna().astype(float)
    bars_held_series = pd.Series(bars_held_values, index=out.index).dropna().astype(float)
    exit_reason_series = pd.Series(exit_reasons, index=out.index, dtype="object")
    label_counts = label_series.loc[valid_labels].astype(int).value_counts().sort_index()
    exit_counts = exit_reason_series.value_counts(dropna=True).to_dict()

    output_cols = [
        label_col,
        fwd_col,
        "r_target_trade_r",
        "r_target_oriented_r",
        candidate_out_col,
        "r_target_entry_price",
        "r_target_exit_price",
        "r_target_stop_price",
        "r_target_take_profit_price",
        "r_target_exit_reason",
        "r_target_bars_held",
        "r_target_hit_type",
        "r_target_hit_step",
    ]
    diagnostic_cols = _diagnostic_feature_columns(out, cfg)
    winner_loser_summary = _winner_loser_feature_summary(
        out,
        label_col=label_col,
        feature_cols=diagnostic_cols,
    )
    meta = {
        "kind": "r_multiple",
        "label_col": label_col,
        "fwd_col": fwd_col,
        "event_ret_col": fwd_col,
        "candidate_col": candidate_col,
        "candidate_out_col": candidate_out_col,
        "candidate_rows": int(candidates.sum()),
        "labeled_rows": int(valid_labels.sum()),
        "positive_rate": float(label_series.loc[valid_labels].mean()) if bool(valid_labels.any()) else None,
        "target_r_min": target_r_min,
        "take_profit_r": take_profit_r,
        "stop_loss_r": stop_loss_r,
        "max_holding_bars": max_holding_bars,
        "max_holding": max_holding_bars,
        "horizon": max_holding_bars,
        "stop_mode": stop_mode,
        "tie_break": tie_break,
        "entry_price_mode": entry_price_mode,
        "side": side,
        "price_col": price_col,
        "open_col": open_col,
        "high_col": high_col,
        "low_col": low_col,
        "volatility_col": volatility_col if stop_mode == "volatility_stop" else None,
        "take_profit_count": int(exit_counts.get("take_profit", 0)),
        "stop_loss_count": int(exit_counts.get("stop_loss", 0)),
        "max_holding_close_count": int(exit_counts.get("max_holding_close", 0)),
        "unavailable_tail_count": int(exit_counts.get("unavailable_tail", 0)),
        "invalid_entry_count": int(exit_counts.get("invalid_entry", 0)),
        "avg_trade_r": float(valid_trade_r.mean()) if not valid_trade_r.empty else None,
        "median_trade_r": float(valid_trade_r.median()) if not valid_trade_r.empty else None,
        "q25_trade_r": _numeric_quantile(valid_trade_r, 0.25),
        "q75_trade_r": _numeric_quantile(valid_trade_r, 0.75),
        "avg_bars_held": float(bars_held_series.mean()) if not bars_held_series.empty else None,
        "median_bars_held": float(bars_held_series.median()) if not bars_held_series.empty else None,
        "label_distribution": {
            "rows": int(valid_labels.sum()),
            "class_counts": {str(int(key)): int(value) for key, value in label_counts.items()},
            "positive_rate": float(label_series.loc[valid_labels].mean()) if bool(valid_labels.any()) else None,
        },
        "exit_reason_counts": {str(key): int(value) for key, value in exit_counts.items()},
        "winner_loser_feature_summary": winner_loser_summary,
        "output_cols": sorted(set(output_cols)),
        "oriented_r_col": "r_target_oriented_r",
        "r_col": "r_target_trade_r",
        "hit_type_col": "r_target_hit_type",
        "hit_step_col": "r_target_hit_step",
    }
    return out, label_col, fwd_col, meta


__all__ = ["R_MULTIPLE_TARGET_OUTPUT_COLS", "build_r_multiple_target"]
