from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.features.technical.atr import compute_atr
from src.targets.output_aliases import apply_target_output_aliases


_AMBIGUOUS_POLICIES = frozenset({"exclude", "stop_first", "target_first"})
_ENTRY_PRICE_TYPES = frozenset({"open", "close"})


def _numeric_summary(values: np.ndarray | pd.Series) -> dict[str, float | int | None]:
    series = pd.to_numeric(pd.Series(values, copy=False), errors="coerce").dropna().astype(float)
    if series.empty:
        return {
            "rows": 0,
            "mean": None,
            "median": None,
            "q05": None,
            "q25": None,
            "q75": None,
            "q95": None,
        }
    return {
        "rows": int(len(series)),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "q05": float(series.quantile(0.05)),
        "q25": float(series.quantile(0.25)),
        "q75": float(series.quantile(0.75)),
        "q95": float(series.quantile(0.95)),
    }


def _class_distribution(labels: np.ndarray) -> dict[str, Any]:
    valid = pd.Series(labels, copy=False).dropna().astype(int)
    counts = {str(label): int((valid == label).sum()) for label in (-1, 0, 1)}
    rows = int(len(valid))
    return {
        "rows": rows,
        "class_counts": counts,
        "class_rates": {
            label: (float(count / rows) if rows > 0 else None)
            for label, count in counts.items()
        },
    }


def _validate_intrabar_data(
    intrabar_data: Any,
    *,
    open_col: str,
    high_col: str,
    low_col: str,
) -> pd.DataFrame | None:
    if intrabar_data is None:
        return None
    if not isinstance(intrabar_data, pd.DataFrame):
        raise TypeError("first_passage_barrier intrabar_data must be a pandas DataFrame.")
    if not isinstance(intrabar_data.index, pd.DatetimeIndex):
        raise TypeError("first_passage_barrier intrabar_data must use a DatetimeIndex.")
    missing = [col for col in (open_col, high_col, low_col) if col not in intrabar_data.columns]
    if missing:
        raise KeyError(f"Missing intrabar OHLC columns for first_passage_barrier: {missing}")
    if not intrabar_data.index.is_monotonic_increasing or intrabar_data.index.has_duplicates:
        raise ValueError("first_passage_barrier intrabar_data index must be sorted and unique.")
    return intrabar_data


def _resolve_with_intrabar(
    intrabar: pd.DataFrame | None,
    *,
    parent_start: object,
    parent_end: object,
    upper: float,
    lower: float,
    open_col: str,
    high_col: str,
    low_col: str,
) -> int | None:
    if intrabar is None:
        return None
    try:
        sub = intrabar.loc[(intrabar.index >= parent_start) & (intrabar.index < parent_end)]
    except TypeError:
        return None
    for _, row in sub.iterrows():
        bar_open = float(row[open_col])
        if np.isfinite(bar_open):
            if bar_open >= upper:
                return 1
            if bar_open <= lower:
                return -1
        hit_upper = bool(float(row[high_col]) >= upper)
        hit_lower = bool(float(row[low_col]) <= lower)
        if hit_upper and hit_lower:
            return None
        if hit_upper:
            return 1
        if hit_lower:
            return -1
    return None


def build_first_passage_barrier_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """Build a causal, next-executable-bar first-passage multiclass target.

    A row at position ``t`` anchors ATR at ``t``. The entry is delayed by
    ``entry_delay_bars`` (one bar by default), and the subsequent OHLC path is
    scanned for the first upper/lower ATR barrier touch. Same-parent-bar double
    touches remain unlabeled under the default ``exclude`` policy unless a
    lower-timeframe frame resolves their ordering.

    YAML declaration::

        target:
          kind: first_passage_barrier_multiclass
          horizon_bars: 12
          upper_atr_multiplier: 1.0
          lower_atr_multiplier: 1.0
          atr_period: 14
          atr_col: atr_14
          entry_delay_bars: 1
          entry_price_type: open
          ambiguous_policy: exclude

    Required input columns
    ----------------------
    open_col, high_col, low_col, close_col:
        Sorted, unique OHLC observations. ``atr_col`` is computed causally when
        it is absent.

    Parameters
    ----------
    horizon_bars, entry_delay_bars:
        Future path length and delay to the executable entry bar.
        ``time_to_first_hit`` counts observed path bars from entry, so a touch
        during the entry bar is reported as one regardless of entry delay.
    upper_atr_multiplier, lower_atr_multiplier:
        Barrier distances based on ATR known at feature timestamp ``t``.
    ambiguous_policy:
        One of ``exclude``, ``stop_first``, or ``target_first`` for unresolved
        same-bar double touches.
    """
    cfg = apply_target_output_aliases(target_cfg)
    horizon_bars = int(cfg.get("horizon_bars", cfg.get("horizon", 12)))
    upper_mult = float(cfg.get("upper_atr_multiplier", 1.0))
    lower_mult = float(cfg.get("lower_atr_multiplier", upper_mult))
    atr_period = int(cfg.get("atr_period", 14))
    entry_delay_bars = int(cfg.get("entry_delay_bars", 1))
    entry_price_type = str(cfg.get("entry_price_type", "open")).strip().lower()
    ambiguous_policy = str(cfg.get("ambiguous_policy", "exclude")).strip().lower()
    use_intrabar_resolution = bool(cfg.get("use_intrabar_resolution", False))
    minimum_barrier_to_cost_ratio = float(cfg.get("minimum_barrier_to_cost_ratio", 0.0))
    round_trip_cost = float(cfg.get("round_trip_cost", 0.0))

    open_col = str(cfg.get("open_col", "open"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    close_col = str(cfg.get("close_col", "close"))
    atr_col = str(cfg.get("atr_col", f"atr_{atr_period}"))
    label_col = str(cfg.get("label_col", "first_passage_label"))
    fwd_col = str(cfg.get("fwd_col", "first_passage_exit_return"))

    output_names = {
        "time_to_first_hit": str(cfg.get("time_to_first_hit_col", "time_to_first_hit")),
        "mfe": str(cfg.get("mfe_col", "mfe")),
        "mae": str(cfg.get("mae_col", "mae")),
        "mfe_atr": str(cfg.get("mfe_atr_col", "mfe_atr")),
        "mae_atr": str(cfg.get("mae_atr_col", "mae_atr")),
        "terminal_return": str(cfg.get("terminal_return_col", "terminal_return")),
        "terminal_return_atr": str(cfg.get("terminal_return_atr_col", "terminal_return_atr")),
        "upper_distance": str(cfg.get("upper_distance_col", "upper_distance")),
        "lower_distance": str(cfg.get("lower_distance_col", "lower_distance")),
        "ambiguous": str(cfg.get("ambiguous_col", "ambiguous")),
        "intrabar_resolved": str(cfg.get("intrabar_resolved_col", "intrabar_resolved")),
        "entry_price": str(cfg.get("entry_price_col", "entry_price")),
        "exit_price": str(cfg.get("exit_price_col", "exit_price")),
        "exit_reason": str(cfg.get("exit_reason_col", "exit_reason")),
        "upper_barrier": str(cfg.get("upper_barrier_col", "upper_barrier")),
        "lower_barrier": str(cfg.get("lower_barrier_col", "lower_barrier")),
        "eligible": str(cfg.get("eligible_col", "barrier_cost_eligible")),
        "barrier_cost_ratio": str(cfg.get("barrier_cost_ratio_col", "barrier_cost_ratio")),
        "stop_first_label": str(cfg.get("stop_first_label_col", "first_passage_label_stop_first")),
        "target_first_label": str(cfg.get("target_first_label_col", "first_passage_label_target_first")),
    }

    if horizon_bars <= 0:
        raise ValueError("first_passage_barrier horizon_bars must be positive.")
    if atr_period <= 0:
        raise ValueError("first_passage_barrier atr_period must be positive.")
    if entry_delay_bars <= 0:
        raise ValueError("first_passage_barrier entry_delay_bars must be >= 1.")
    if not np.isfinite(upper_mult) or upper_mult <= 0.0:
        raise ValueError("first_passage_barrier upper_atr_multiplier must be finite and > 0.")
    if not np.isfinite(lower_mult) or lower_mult <= 0.0:
        raise ValueError("first_passage_barrier lower_atr_multiplier must be finite and > 0.")
    if entry_price_type not in _ENTRY_PRICE_TYPES:
        raise ValueError(f"first_passage_barrier entry_price_type must be one of {sorted(_ENTRY_PRICE_TYPES)}.")
    if ambiguous_policy not in _AMBIGUOUS_POLICIES:
        raise ValueError(f"first_passage_barrier ambiguous_policy must be one of {sorted(_AMBIGUOUS_POLICIES)}.")
    if not np.isfinite(minimum_barrier_to_cost_ratio) or minimum_barrier_to_cost_ratio < 0.0:
        raise ValueError("first_passage_barrier minimum_barrier_to_cost_ratio must be finite and >= 0.")
    if not np.isfinite(round_trip_cost) or round_trip_cost < 0.0:
        raise ValueError("first_passage_barrier round_trip_cost must be finite and >= 0.")

    required = [open_col, high_col, low_col, close_col]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for first_passage_barrier target: {missing}")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("first_passage_barrier requires a sorted, unique index.")

    intrabar = _validate_intrabar_data(
        cfg.get("intrabar_data") if use_intrabar_resolution else None,
        open_col=str(cfg.get("intrabar_open_col", open_col)),
        high_col=str(cfg.get("intrabar_high_col", high_col)),
        low_col=str(cfg.get("intrabar_low_col", low_col)),
    )
    intrabar_open_col = str(cfg.get("intrabar_open_col", open_col))
    intrabar_high_col = str(cfg.get("intrabar_high_col", high_col))
    intrabar_low_col = str(cfg.get("intrabar_low_col", low_col))

    out = df.copy()
    if atr_col in out.columns:
        atr = pd.to_numeric(out[atr_col], errors="coerce").astype(float)
        atr_source = atr_col
    else:
        atr = compute_atr(
            pd.to_numeric(out[high_col], errors="coerce"),
            pd.to_numeric(out[low_col], errors="coerce"),
            pd.to_numeric(out[close_col], errors="coerce"),
            window=atr_period,
            method="wilder",
        ).astype(float)
        out[atr_col] = atr.astype("float32")
        atr_source = atr_col

    size = len(out)
    opens = pd.to_numeric(out[open_col], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(out[high_col], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(out[low_col], errors="coerce").to_numpy(dtype=float)
    closes = pd.to_numeric(out[close_col], errors="coerce").to_numpy(dtype=float)
    atr_values = atr.to_numpy(dtype=float)

    labels = np.full(size, np.nan, dtype=float)
    stop_first_labels = np.full(size, np.nan, dtype=float)
    target_first_labels = np.full(size, np.nan, dtype=float)
    exit_returns = np.full(size, np.nan, dtype=float)
    time_to_hit = np.full(size, np.nan, dtype=float)
    mfe = np.full(size, np.nan, dtype=float)
    mae = np.full(size, np.nan, dtype=float)
    mfe_atr = np.full(size, np.nan, dtype=float)
    mae_atr = np.full(size, np.nan, dtype=float)
    terminal_return = np.full(size, np.nan, dtype=float)
    terminal_return_atr = np.full(size, np.nan, dtype=float)
    upper_distance = np.full(size, np.nan, dtype=float)
    lower_distance = np.full(size, np.nan, dtype=float)
    upper_barrier = np.full(size, np.nan, dtype=float)
    lower_barrier = np.full(size, np.nan, dtype=float)
    entry_prices = np.full(size, np.nan, dtype=float)
    exit_prices = np.full(size, np.nan, dtype=float)
    barrier_cost_ratio = np.full(size, np.nan, dtype=float)
    ambiguous = np.zeros(size, dtype=bool)
    intrabar_resolved = np.zeros(size, dtype=bool)
    eligible = np.zeros(size, dtype=bool)
    evaluated = np.zeros(size, dtype=bool)
    exit_reasons = np.full(size, None, dtype=object)

    index = out.index
    for feature_idx in range(size):
        entry_idx = feature_idx + entry_delay_bars
        scan_start = entry_idx if entry_price_type == "open" else entry_idx + 1
        scan_end = scan_start + horizon_bars
        if entry_idx >= size or scan_end > size:
            exit_reasons[feature_idx] = "unavailable_horizon"
            continue

        entry_price = float(opens[entry_idx] if entry_price_type == "open" else closes[entry_idx])
        atr_t = float(atr_values[feature_idx])
        if not np.isfinite(entry_price) or entry_price <= 0.0 or not np.isfinite(atr_t) or atr_t <= 0.0:
            exit_reasons[feature_idx] = "invalid_entry_or_atr"
            continue

        upper_dist = upper_mult * atr_t
        lower_dist = lower_mult * atr_t
        upper_level = entry_price + upper_dist
        lower_level = entry_price - lower_dist
        if lower_level <= 0.0:
            exit_reasons[feature_idx] = "invalid_lower_barrier"
            continue

        entry_prices[feature_idx] = entry_price
        upper_distance[feature_idx] = upper_dist
        lower_distance[feature_idx] = lower_dist
        upper_barrier[feature_idx] = upper_level
        lower_barrier[feature_idx] = lower_level
        evaluated[feature_idx] = True

        if round_trip_cost > 0.0:
            cost_ratio = min(upper_dist / entry_price, lower_dist / entry_price) / round_trip_cost
        else:
            cost_ratio = np.inf
        barrier_cost_ratio[feature_idx] = cost_ratio
        eligible[feature_idx] = bool(cost_ratio >= minimum_barrier_to_cost_ratio)

        terminal_idx = scan_end - 1
        terminal_px = float(closes[terminal_idx])
        if np.isfinite(terminal_px):
            terminal_return[feature_idx] = terminal_px / entry_price - 1.0
            terminal_return_atr[feature_idx] = (terminal_px - entry_price) / atr_t

        chosen_label: int | None = None
        chosen_exit: float | None = None
        chosen_idx: int | None = None
        chosen_reason: str | None = None
        unresolved_ambiguous = False

        for path_idx in range(scan_start, scan_end):
            bar_open = float(opens[path_idx])
            if np.isfinite(bar_open) and bar_open >= upper_level:
                chosen_label, chosen_exit, chosen_reason = 1, bar_open, "upper_gap"
            elif np.isfinite(bar_open) and bar_open <= lower_level:
                chosen_label, chosen_exit, chosen_reason = -1, bar_open, "lower_gap"
            else:
                hit_upper = bool(np.isfinite(highs[path_idx]) and highs[path_idx] >= upper_level)
                hit_lower = bool(np.isfinite(lows[path_idx]) and lows[path_idx] <= lower_level)
                if hit_upper and hit_lower:
                    ambiguous[feature_idx] = True
                    parent_end = index[path_idx + 1] if path_idx + 1 < size else None
                    intrabar_label = None
                    if parent_end is not None:
                        intrabar_label = _resolve_with_intrabar(
                            intrabar,
                            parent_start=index[path_idx],
                            parent_end=parent_end,
                            upper=upper_level,
                            lower=lower_level,
                            open_col=intrabar_open_col,
                            high_col=intrabar_high_col,
                            low_col=intrabar_low_col,
                        )
                    if intrabar_label is not None:
                        chosen_label = int(intrabar_label)
                        intrabar_resolved[feature_idx] = True
                        chosen_exit = upper_level if chosen_label == 1 else lower_level
                        chosen_reason = "upper_intrabar_resolved" if chosen_label == 1 else "lower_intrabar_resolved"
                    else:
                        unresolved_ambiguous = True
                        chosen_reason = "ambiguous"
                    chosen_idx = path_idx
                    break
                if hit_upper:
                    chosen_label, chosen_exit, chosen_reason = 1, upper_level, "upper_barrier"
                elif hit_lower:
                    chosen_label, chosen_exit, chosen_reason = -1, lower_level, "lower_barrier"

            if chosen_label is not None:
                chosen_idx = path_idx
                break

        if chosen_idx is None:
            chosen_idx = terminal_idx
            chosen_label = 0
            chosen_exit = terminal_px
            chosen_reason = "no_hit"

        path_slice = slice(scan_start, chosen_idx + 1)
        path_highs = highs[path_slice]
        path_lows = lows[path_slice]
        if np.isfinite(path_highs).any():
            mfe_value = float(np.nanmax(path_highs) - entry_price)
            mfe[feature_idx] = mfe_value
            mfe_atr[feature_idx] = mfe_value / atr_t
        if np.isfinite(path_lows).any():
            mae_value = float(np.nanmin(path_lows) - entry_price)
            mae[feature_idx] = mae_value
            mae_atr[feature_idx] = mae_value / atr_t

        if unresolved_ambiguous:
            if eligible[feature_idx]:
                stop_first_labels[feature_idx] = -1.0
                target_first_labels[feature_idx] = 1.0
            if ambiguous_policy == "stop_first":
                chosen_label, chosen_exit, chosen_reason = -1, lower_level, "ambiguous_stop_first"
            elif ambiguous_policy == "target_first":
                chosen_label, chosen_exit, chosen_reason = 1, upper_level, "ambiguous_target_first"
            else:
                chosen_label, chosen_exit = None, None
        elif eligible[feature_idx]:
            stop_first_labels[feature_idx] = float(chosen_label)
            target_first_labels[feature_idx] = float(chosen_label)

        exit_reasons[feature_idx] = chosen_reason
        if chosen_label is not None and eligible[feature_idx]:
            labels[feature_idx] = float(chosen_label)
        elif chosen_label is not None and not eligible[feature_idx]:
            exit_reasons[feature_idx] = "barrier_to_cost_filter"
        if chosen_exit is not None and np.isfinite(chosen_exit):
            exit_prices[feature_idx] = float(chosen_exit)
            exit_returns[feature_idx] = float(chosen_exit / entry_price - 1.0)
        if chosen_label in {-1, 1} and chosen_idx is not None:
            time_to_hit[feature_idx] = float(chosen_idx - scan_start + 1)

    out[label_col] = labels.astype("float32")
    out[fwd_col] = exit_returns.astype("float32")
    out[output_names["time_to_first_hit"]] = time_to_hit.astype("float32")
    out[output_names["mfe"]] = mfe.astype("float32")
    out[output_names["mae"]] = mae.astype("float32")
    out[output_names["mfe_atr"]] = mfe_atr.astype("float32")
    out[output_names["mae_atr"]] = mae_atr.astype("float32")
    out[output_names["terminal_return"]] = terminal_return.astype("float32")
    out[output_names["terminal_return_atr"]] = terminal_return_atr.astype("float32")
    out[output_names["upper_distance"]] = upper_distance.astype("float32")
    out[output_names["lower_distance"]] = lower_distance.astype("float32")
    out[output_names["ambiguous"]] = ambiguous
    out[output_names["intrabar_resolved"]] = intrabar_resolved
    out[output_names["entry_price"]] = entry_prices
    out[output_names["exit_price"]] = exit_prices
    out[output_names["exit_reason"]] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out[output_names["upper_barrier"]] = upper_barrier
    out[output_names["lower_barrier"]] = lower_barrier
    out[output_names["eligible"]] = eligible
    out[output_names["barrier_cost_ratio"]] = barrier_cost_ratio
    out[output_names["stop_first_label"]] = stop_first_labels.astype("float32")
    out[output_names["target_first_label"]] = target_first_labels.astype("float32")

    label_distribution = _class_distribution(labels)
    evaluated_count = int(evaluated.sum())
    ambiguous_count = int(ambiguous.sum())
    resolved_count = int(intrabar_resolved.sum())
    unresolved_count = int((ambiguous & ~intrabar_resolved).sum())
    output_cols = [label_col, fwd_col, *output_names.values()]
    meta: dict[str, Any] = {
        "kind": "first_passage_barrier_multiclass",
        "horizon": int(horizon_bars + entry_delay_bars),
        "horizon_bars": horizon_bars,
        "entry_delay_bars": entry_delay_bars,
        "entry_price_type": entry_price_type,
        "upper_atr_multiplier": upper_mult,
        "lower_atr_multiplier": lower_mult,
        "atr_period": atr_period,
        "atr_col": atr_source,
        "atr_anchor": "feature_bar_close_t",
        "ambiguous_policy": ambiguous_policy,
        "use_intrabar_resolution": use_intrabar_resolution,
        "intrabar_data_available": intrabar is not None,
        "minimum_barrier_to_cost_ratio": minimum_barrier_to_cost_ratio,
        "round_trip_cost": round_trip_cost,
        "class_labels": [-1, 0, 1],
        "class_names": {"-1": "lower", "0": "no_hit", "1": "upper"},
        "primary_probability_class": 1,
        "label_col": label_col,
        "fwd_col": fwd_col,
        "ambiguous_col": output_names["ambiguous"],
        "entry_price_col": output_names["entry_price"],
        "eligible_col": output_names["eligible"],
        "stop_first_label_col": output_names["stop_first_label"],
        "target_first_label_col": output_names["target_first_label"],
        "output_cols": list(dict.fromkeys(output_cols)),
        "evaluated_rows": evaluated_count,
        "labeled_rows": int(np.isfinite(labels).sum()),
        "eligible_rows": int(eligible.sum()),
        "unavailable_tail_count": int((np.asarray(exit_reasons, dtype=object) == "unavailable_horizon").sum()),
        "ambiguous_count": ambiguous_count,
        "ambiguous_rate": float(ambiguous_count / evaluated_count) if evaluated_count else None,
        "intrabar_resolved_count": resolved_count,
        "unresolved_ambiguous_count": unresolved_count,
        "unresolved_ambiguous_rate": float(unresolved_count / evaluated_count) if evaluated_count else None,
        "label_distribution": label_distribution,
        "sensitivity": {
            "stop_first": _class_distribution(stop_first_labels),
            "target_first": _class_distribution(target_first_labels),
        },
        "time_to_first_hit_summary": _numeric_summary(time_to_hit),
        "mfe_summary": _numeric_summary(mfe),
        "mae_summary": _numeric_summary(mae),
        "mfe_atr_summary": _numeric_summary(mfe_atr),
        "mae_atr_summary": _numeric_summary(mae_atr),
        "terminal_return_summary": _numeric_summary(terminal_return),
        "exit_reason_counts": {
            str(key): int(value)
            for key, value in pd.Series(exit_reasons, dtype="object").dropna().value_counts().items()
        },
    }
    return out, label_col, fwd_col, meta


__all__ = ["build_first_passage_barrier_target"]
