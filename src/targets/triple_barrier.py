from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _parse_r_clip(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("triple_barrier r_clip must be a finite number or [low, high] pair.")
    if isinstance(value, (int, float)):
        bound = abs(float(value))
        if not np.isfinite(bound) or bound <= 0.0:
            raise ValueError("triple_barrier r_clip must be > 0 when provided as a scalar.")
        return -bound, bound
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low = float(value[0])
        high = float(value[1])
        if not np.isfinite(low) or not np.isfinite(high) or low >= high:
            raise ValueError("triple_barrier r_clip must satisfy low < high.")
        return low, high
    raise ValueError("triple_barrier r_clip must be a finite number or [low, high] pair.")


def _numeric_summary(values: np.ndarray) -> dict[str, Any]:
    series = pd.Series(values, copy=False)
    numeric = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if numeric.empty:
        return {
            "rows": 0,
            "mean": None,
            "median": None,
            "positive_rate": None,
            "q05": None,
            "q25": None,
            "q75": None,
            "q95": None,
        }
    return {
        "rows": int(len(numeric)),
        "mean": float(numeric.mean()),
        "median": float(numeric.median()),
        "positive_rate": float((numeric > 0.0).mean()),
        "q05": float(numeric.quantile(0.05)),
        "q25": float(numeric.quantile(0.25)),
        "q75": float(numeric.quantile(0.75)),
        "q95": float(numeric.quantile(0.95)),
    }


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
    side_col = cfg.get("side_col")
    candidate_col = cfg.get("candidate_col")
    candidate_mode = str(cfg.get("candidate_mode", "all_nonzero"))
    entry_price_mode = str(cfg.get("entry_price_mode", "current_close"))
    raw_label_mode = cfg.get("label_mode")
    label_mode = str(raw_label_mode if raw_label_mode is not None else ("meta" if side_col is not None else "binary"))
    legacy_implicit_meta = bool(raw_label_mode is None and side_col is not None)
    add_r_multiple = bool(cfg.get("add_r_multiple", False))
    r_col = str(cfg.get("r_col", "tb_event_r"))
    oriented_r_col = str(cfg.get("oriented_r_col", "tb_oriented_r"))
    r_clip = _parse_r_clip(cfg.get("r_clip"))

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
    if side_col is not None and not isinstance(side_col, str):
        raise ValueError("triple_barrier side_col must be a string when provided.")
    if candidate_col is not None and not isinstance(candidate_col, str):
        raise ValueError("triple_barrier candidate_col must be a string when provided.")
    if candidate_mode not in {"all_nonzero", "side_change"}:
        raise ValueError("triple_barrier candidate_mode must be one of: all_nonzero, side_change.")
    if entry_price_mode not in {"current_close", "next_open"}:
        raise ValueError("triple_barrier entry_price_mode must be one of: current_close, next_open.")
    if label_mode not in {"binary", "ternary", "meta"}:
        raise ValueError("triple_barrier label_mode must be one of: binary, ternary, meta.")
    if label_mode == "meta" and side_col is None:
        raise ValueError("triple_barrier label_mode='meta' requires side_col.")

    required = [price_col, open_col, high_col, low_col]
    if side_col is not None:
        required.append(side_col)
    if candidate_col is not None:
        required.append(candidate_col)
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
    side_sign_for_barrier = np.zeros(len(out), dtype=float)
    if side_col is not None:
        side_sign_for_barrier = np.sign(
            out[str(side_col)]
            .astype(float)
            .fillna(0.0)
            .clip(lower=-1.0, upper=1.0)
            .to_numpy(dtype=float)
        )

    labels = np.full(len(out), np.nan, dtype=float)
    raw_barrier_labels = np.full(len(out), np.nan, dtype=float)
    event_rets = np.full(len(out), np.nan, dtype=float)
    upper_levels = np.full(len(out), np.nan, dtype=float)
    lower_levels = np.full(len(out), np.nan, dtype=float)
    hit_steps = np.full(len(out), np.nan, dtype=float)
    risk_distances = np.full(len(out), np.nan, dtype=float)
    neutral_events = np.full(len(out), False, dtype=bool)
    evaluated_events = np.full(len(out), False, dtype=bool)
    hit_types = np.full(len(out), None, dtype=object)

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

    def _hit_type_for_price_label(price_label: float, side_sign: float) -> str:
        if label_mode != "meta":
            return "upper" if price_label == 1.0 else "lower"
        if side_sign > 0.0:
            return "profit" if price_label == 1.0 else "stop"
        if side_sign < 0.0:
            return "profit" if price_label == 0.0 else "stop"
        return "neutral"

    full_horizon_cutoff = len(out) - max_holding
    for start_idx in range(len(out)):
        if start_idx >= full_horizon_cutoff:
            # Keep tail rows unlabeled when the full vertical barrier horizon is unavailable.
            continue

        entry_idx = start_idx if entry_price_mode == "current_close" else start_idx + 1
        if entry_idx >= len(out):
            continue

        entry_price = float(prices[start_idx] if entry_price_mode == "current_close" else opens[entry_idx])
        if not np.isfinite(entry_price) or entry_price <= 0.0:
            continue
        start_side = float(side_sign_for_barrier[start_idx])
        if label_mode == "meta" and start_side == 0.0:
            continue

        horizon_end = min(len(out), start_idx + max_holding + 1)
        scan_start = start_idx + 1
        if horizon_end <= scan_start:
            continue

        sigma = float(vols[start_idx])
        risk_distance = float(lower_mult * sigma)
        if label_mode == "meta" and start_side < 0.0:
            upper_level = entry_price * (1.0 + lower_mult * sigma)
            lower_level = entry_price * max(1.0 - upper_mult * sigma, 1e-12)
        else:
            upper_level = entry_price * (1.0 + upper_mult * sigma)
            lower_level = entry_price * max(1.0 - lower_mult * sigma, 1e-12)
        upper_levels[start_idx] = upper_level
        lower_levels[start_idx] = lower_level
        risk_distances[start_idx] = risk_distance
        evaluated_events[start_idx] = True

        chosen_label: float | None = None
        chosen_step: int | None = None
        chosen_return: float | None = None
        hit_barrier = False

        for step_idx in range(scan_start, horizon_end):
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
                hit_barrier = True
                if chosen_label == 1.0:
                    chosen_return = upper_level / entry_price - 1.0
                else:
                    chosen_return = lower_level / entry_price - 1.0
                hit_types[start_idx] = _hit_type_for_price_label(float(chosen_label), start_side)
                break

        if chosen_label is None:
            terminal_idx = horizon_end - 1
            chosen_return = prices[terminal_idx] / entry_price - 1.0
            neutral_events[start_idx] = True
            hit_types[start_idx] = "neutral"
            if neutral_label == "lower":
                chosen_label = 0.0
            elif neutral_label == "upper":
                chosen_label = 1.0
            else:
                chosen_label = np.nan
            chosen_step = terminal_idx - start_idx

        if hit_barrier:
            raw_barrier_labels[start_idx] = chosen_label
        if label_mode == "ternary":
            if hit_barrier:
                labels[start_idx] = 1.0 if chosen_label == 1.0 else -1.0
            else:
                labels[start_idx] = 0.0
        else:
            labels[start_idx] = chosen_label
        event_rets[start_idx] = chosen_return
        hit_steps[start_idx] = float(chosen_step) if chosen_step is not None else np.nan

    fwd_col = str(cfg.get("fwd_col", event_ret_col))
    raw_label_series = pd.Series(raw_barrier_labels.copy(), index=out.index)
    candidate_out_col = None
    meta_label_enabled = label_mode == "meta"
    candidate_rows = None
    event_r = np.full(len(out), np.nan, dtype=float)
    oriented_r = np.full(len(out), np.nan, dtype=float)
    finite_risk = np.isfinite(risk_distances) & (risk_distances > 0.0) & np.isfinite(event_rets)
    event_r[finite_risk] = event_rets[finite_risk] / risk_distances[finite_risk]
    if r_clip is not None:
        event_r = np.clip(event_r, r_clip[0], r_clip[1])

    if meta_label_enabled:
        side_series = out[str(side_col)].astype(float).fillna(0.0).clip(lower=-1.0, upper=1.0)
        side_sign = np.sign(side_series.to_numpy(dtype=float))
        candidate_mask = side_series.ne(0.0)
        if candidate_col is not None:
            raw_candidate = out[str(candidate_col)].astype(float).fillna(0.0)
            candidate_mask &= raw_candidate.ne(0.0)
        elif candidate_mode == "side_change":
            prev_side = side_series.shift(1).fillna(0.0)
            candidate_mask &= side_series.ne(prev_side)

        oriented_rets = event_rets * side_sign
        oriented_r = event_r * side_sign
        if r_clip is not None:
            oriented_r = np.clip(oriented_r, r_clip[0], r_clip[1])
        meta_labels = np.full(len(out), np.nan, dtype=float)
        candidate_values = candidate_mask.to_numpy(dtype=bool)
        if legacy_implicit_meta:
            finite_oriented_ret = np.isfinite(oriented_rets)
            meta_labels[candidate_values & finite_oriented_ret] = (
                oriented_rets[candidate_values & finite_oriented_ret] > 0.0
            ).astype(float)
        else:
            hit_type_values = np.asarray(hit_types, dtype=object)
            profit_mask = candidate_values & (hit_type_values == "profit")
            failure_mask = candidate_values & (hit_type_values == "stop")
            if neutral_label != "drop":
                failure_mask |= candidate_values & (hit_type_values == "neutral")
            meta_labels[profit_mask] = 1.0
            meta_labels[failure_mask] = 0.0
        labels = meta_labels
        candidate_rows = int(candidate_mask.sum())

        candidate_out_col = str(cfg.get("candidate_out_col", f"{label_col}_candidate"))
        out[candidate_out_col] = candidate_mask.astype("float32")
        out[f"{label_col}_meta_side"] = side_sign.astype("float32")
        out[f"{label_col}_oriented_ret"] = oriented_rets.astype("float32")
    elif side_col is not None:
        side_series = out[str(side_col)].astype(float).fillna(0.0).clip(lower=-1.0, upper=1.0)
        side_sign = np.sign(side_series.to_numpy(dtype=float))
        oriented_r = event_r * side_sign
        if r_clip is not None:
            oriented_r = np.clip(oriented_r, r_clip[0], r_clip[1])
        out[f"{label_col}_meta_side"] = side_sign.astype("float32")
        out[f"{label_col}_oriented_ret"] = (event_rets * side_sign).astype("float32")
    else:
        oriented_r = event_r.copy()

    out[event_ret_col] = event_rets.astype("float32")
    if event_ret_col != fwd_col:
        out[fwd_col] = out[event_ret_col]
    if add_r_multiple:
        out[r_col] = event_r.astype("float32")
        out[oriented_r_col] = oriented_r.astype("float32")
    out[label_col] = labels.astype("float32")
    out[f"{label_col}_hit_step"] = hit_steps.astype("float32")
    out[f"{label_col}_hit_type"] = pd.Series(hit_types, index=out.index, dtype="object")
    out[f"{label_col}_upper_barrier"] = upper_levels.astype("float32")
    out[f"{label_col}_lower_barrier"] = lower_levels.astype("float32")

    label_series = pd.Series(labels, index=out.index)
    valid = label_series.notna()
    positive_rate = float(label_series.loc[valid].mean()) if bool(valid.any()) else np.nan
    upper_count = int((raw_label_series == 1.0).sum())
    lower_count = int((raw_label_series == 0.0).sum())
    neutral_count = int(neutral_events.sum())
    hit_type_series = pd.Series(hit_types, index=out.index, dtype="object")
    hit_step_series = pd.Series(hit_steps, index=out.index).dropna()
    output_cols = [
        label_col,
        event_ret_col,
        fwd_col,
        f"{label_col}_hit_step",
        f"{label_col}_hit_type",
        f"{label_col}_upper_barrier",
        f"{label_col}_lower_barrier",
    ]
    if add_r_multiple:
        output_cols.extend([r_col, oriented_r_col])
    if candidate_out_col is not None:
        output_cols.append(candidate_out_col)
        output_cols.extend([f"{label_col}_meta_side", f"{label_col}_oriented_ret"])
    elif side_col is not None:
        output_cols.extend([f"{label_col}_meta_side", f"{label_col}_oriented_ret"])
    output_cols = sorted(set(output_cols))
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
        "entry_price_mode": entry_price_mode,
        "label_mode": label_mode,
        "legacy_implicit_meta": bool(legacy_implicit_meta),
        "label_col": label_col,
        "fwd_col": fwd_col,
        "event_ret_col": event_ret_col,
        "output_cols": output_cols,
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
        "profit_barrier_count": int((hit_type_series == "profit").sum()),
        "stop_barrier_count": int((hit_type_series == "stop").sum()),
        "neutral_count": neutral_count,
        "unavailable_tail_count": int((~evaluated_events).sum()),
        "avg_hit_step": float(hit_step_series.mean()) if not hit_step_series.empty else None,
        "median_hit_step": float(hit_step_series.median()) if not hit_step_series.empty else None,
        "meta_labeling": bool(meta_label_enabled),
        "side_col": str(side_col) if side_col is not None else None,
        "candidate_input_col": str(candidate_col) if candidate_col is not None else None,
        "candidate_col": candidate_out_col,
        "candidate_mode": candidate_mode if meta_label_enabled else None,
        "candidate_rows": candidate_rows,
        "add_r_multiple": bool(add_r_multiple),
        "r_col": r_col if add_r_multiple else None,
        "oriented_r_col": oriented_r_col if add_r_multiple else None,
        "r_clip": list(r_clip) if r_clip is not None else None,
    }
    if add_r_multiple:
        meta["event_r_distribution"] = _numeric_summary(event_r)
        meta["oriented_r_distribution"] = _numeric_summary(oriented_r)
    return out, label_col, fwd_col, meta


__all__ = ["build_triple_barrier_target"]
