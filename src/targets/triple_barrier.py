from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def build_triple_barrier_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build a binary triple-barrier target.

    Labels:
    - 1.0 when the upper barrier is touched first
    - 0.0 when the lower barrier is touched first
    - NaN (default) when neither barrier is touched before the vertical barrier
    """
    cfg = dict(target_cfg or {})
    price_col = str(cfg.get("price_col", "close"))
    open_col = str(cfg.get("open_col", "open"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    returns_col = cfg.get("returns_col")
    volatility_col = cfg.get("volatility_col")
    label_col = str(cfg.get("label_col", "label"))
    event_ret_col = str(cfg.get("event_ret_col", "tb_event_ret"))
    max_holding = int(cfg.get("max_holding", cfg.get("horizon", 24)))
    upper_mult = float(cfg.get("upper_mult", 2.0))
    lower_mult = float(cfg.get("lower_mult", upper_mult))
    neutral_label = str(cfg.get("neutral_label", "drop"))
    tie_break = str(cfg.get("tie_break", "closest_to_open"))
    vol_window = int(cfg.get("vol_window", 24))
    min_vol = float(cfg.get("min_vol", 1e-4))

    if max_holding <= 0:
        raise ValueError("triple_barrier max_holding must be a positive integer.")
    if upper_mult <= 0 or lower_mult <= 0:
        raise ValueError("triple_barrier upper_mult and lower_mult must be > 0.")
    if vol_window <= 1:
        raise ValueError("triple_barrier vol_window must be > 1.")
    if min_vol <= 0:
        raise ValueError("triple_barrier min_vol must be > 0.")
    if neutral_label not in {"drop", "lower", "upper"}:
        raise ValueError("triple_barrier neutral_label must be one of: drop, lower, upper.")
    if tie_break not in {"closest_to_open", "upper", "lower"}:
        raise ValueError("triple_barrier tie_break must be one of: closest_to_open, upper, lower.")

    required = [price_col, open_col, high_col, low_col]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for triple_barrier target: {missing}")

    out = df.copy()
    if volatility_col is not None:
        vol_source_col = str(volatility_col)
        if vol_source_col not in out.columns:
            raise KeyError(f"triple_barrier volatility_col '{vol_source_col}' not found in DataFrame")
        vol = out[vol_source_col].astype(float)
    else:
        if returns_col is not None:
            ret_source_col = str(returns_col)
            if ret_source_col not in out.columns:
                raise KeyError(f"triple_barrier returns_col '{ret_source_col}' not found in DataFrame")
            returns = out[ret_source_col].astype(float)
        else:
            returns = out[price_col].astype(float).pct_change()
        vol = returns.rolling(vol_window, min_periods=vol_window).std()
        vol_source_col = f"triple_barrier_vol_{vol_window}"
        out[vol_source_col] = vol.astype("float32")

    prices = out[price_col].astype(float).to_numpy(dtype=float)
    opens = out[open_col].astype(float).to_numpy(dtype=float)
    highs = out[high_col].astype(float).to_numpy(dtype=float)
    lows = out[low_col].astype(float).to_numpy(dtype=float)
    vols = vol.astype(float).clip(lower=min_vol).to_numpy(dtype=float)

    labels = np.full(len(out), np.nan, dtype=float)
    event_rets = np.full(len(out), np.nan, dtype=float)
    upper_levels = np.full(len(out), np.nan, dtype=float)
    lower_levels = np.full(len(out), np.nan, dtype=float)
    hit_steps = np.full(len(out), np.nan, dtype=float)

    def _resolve_double_touch(bar_open: float, upper_level: float, lower_level: float) -> float:
        if tie_break == "upper":
            return 1.0
        if tie_break == "lower":
            return 0.0
        upper_distance = abs(bar_open - upper_level)
        lower_distance = abs(bar_open - lower_level)
        if upper_distance < lower_distance:
            return 1.0
        if lower_distance < upper_distance:
            return 0.0
        return 1.0 if bar_open >= (upper_level + lower_level) / 2.0 else 0.0

    full_horizon_cutoff = len(out) - max_holding
    for start_idx in range(len(out)):
        entry_price = float(prices[start_idx])
        if not np.isfinite(entry_price) or entry_price <= 0.0:
            continue
        if start_idx >= full_horizon_cutoff:
            # Keep tail rows unlabeled when the full vertical barrier horizon is unavailable.
            continue

        horizon_end = min(len(out), start_idx + max_holding + 1)
        if horizon_end <= start_idx + 1:
            continue

        sigma = float(vols[start_idx])
        upper_level = entry_price * (1.0 + upper_mult * sigma)
        lower_level = entry_price * max(1.0 - lower_mult * sigma, 1e-12)
        upper_levels[start_idx] = upper_level
        lower_levels[start_idx] = lower_level

        chosen_label: float | None = None
        chosen_step: int | None = None
        chosen_return: float | None = None

        for step_idx in range(start_idx + 1, horizon_end):
            hit_upper = bool(highs[step_idx] >= upper_level)
            hit_lower = bool(lows[step_idx] <= lower_level)
            if hit_upper and hit_lower:
                chosen_label = _resolve_double_touch(opens[step_idx], upper_level, lower_level)
            elif hit_upper:
                chosen_label = 1.0
            elif hit_lower:
                chosen_label = 0.0

            if chosen_label is not None:
                chosen_step = step_idx - start_idx
                if chosen_label == 1.0:
                    chosen_return = upper_level / entry_price - 1.0
                else:
                    chosen_return = lower_level / entry_price - 1.0
                break

        if chosen_label is None:
            terminal_idx = horizon_end - 1
            chosen_return = prices[terminal_idx] / entry_price - 1.0
            if neutral_label == "lower":
                chosen_label = 0.0
            elif neutral_label == "upper":
                chosen_label = 1.0
            else:
                chosen_label = np.nan
            chosen_step = terminal_idx - start_idx

        labels[start_idx] = chosen_label
        event_rets[start_idx] = chosen_return
        hit_steps[start_idx] = float(chosen_step) if chosen_step is not None else np.nan

    fwd_col = str(cfg.get("fwd_col", event_ret_col))
    out[event_ret_col] = event_rets.astype("float32")
    if event_ret_col != fwd_col:
        out[fwd_col] = out[event_ret_col]
    out[label_col] = labels.astype("float32")
    out[f"{label_col}_hit_step"] = hit_steps.astype("float32")
    out[f"{label_col}_upper_barrier"] = upper_levels.astype("float32")
    out[f"{label_col}_lower_barrier"] = lower_levels.astype("float32")

    label_series = pd.Series(labels, index=out.index)
    valid = label_series.notna()
    positive_rate = float(label_series.loc[valid].mean()) if bool(valid.any()) else np.nan
    upper_count = int((label_series == 1.0).sum())
    lower_count = int((label_series == 0.0).sum())
    neutral_count = int(label_series.isna().sum())
    hit_step_series = pd.Series(hit_steps, index=out.index).dropna()
    meta = {
        "kind": "triple_barrier",
        "price_col": price_col,
        "open_col": open_col,
        "high_col": high_col,
        "low_col": low_col,
        "returns_col": returns_col,
        "volatility_col": volatility_col,
        "vol_source_col": vol_source_col,
        "max_holding": max_holding,
        "horizon": max_holding,
        "label_col": label_col,
        "fwd_col": fwd_col,
        "event_ret_col": event_ret_col,
        "upper_mult": upper_mult,
        "lower_mult": lower_mult,
        "neutral_label": neutral_label,
        "tie_break": tie_break,
        "vol_window": vol_window,
        "min_vol": min_vol,
        "labeled_rows": int(valid.sum()),
        "positive_rate": positive_rate,
        "upper_barrier_count": upper_count,
        "lower_barrier_count": lower_count,
        "neutral_count": neutral_count,
        "avg_hit_step": float(hit_step_series.mean()) if not hit_step_series.empty else None,
        "median_hit_step": float(hit_step_series.median()) if not hit_step_series.empty else None,
    }
    return out, label_col, fwd_col, meta


__all__ = ["build_triple_barrier_target"]
