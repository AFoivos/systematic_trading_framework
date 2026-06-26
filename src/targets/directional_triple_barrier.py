from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.targets.output_aliases import apply_target_output_aliases


def _parse_r_clip(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("directional_triple_barrier r_clip must be a finite number or [low, high] pair.")
    if isinstance(value, (int, float)):
        bound = abs(float(value))
        if not np.isfinite(bound) or bound <= 0.0:
            raise ValueError("directional_triple_barrier r_clip must be > 0 when provided as a scalar.")
        return -bound, bound
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low = float(value[0])
        high = float(value[1])
        if not np.isfinite(low) or not np.isfinite(high) or low >= high:
            raise ValueError("directional_triple_barrier r_clip must satisfy low < high.")
        return low, high
    raise ValueError("directional_triple_barrier r_clip must be a finite number or [low, high] pair.")


def _numeric_summary(values: np.ndarray) -> dict[str, Any]:
    numeric = pd.to_numeric(pd.Series(values, copy=False), errors="coerce").dropna().astype(float)
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


def _as_col(value: Any, default: str, *, field: str) -> str:
    resolved = default if value is None else str(value)
    if not resolved.strip():
        raise ValueError(f"directional_triple_barrier {field} must be a non-empty string.")
    return resolved.strip()


def _finite_positive(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"directional_triple_barrier {field} must be finite and > 0.")
    return out


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"directional_triple_barrier {field} must be a positive integer.")
    try:
        out = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"directional_triple_barrier {field} must be a positive integer.") from exc
    if out <= 0 or float(out) != float(value):
        raise ValueError(f"directional_triple_barrier {field} must be a positive integer.")
    return out


def resolve_directional_barrier_double_touch(
    *,
    bar_open: float,
    profit_level: float,
    stop_level: float,
    tie_break: str,
) -> str:
    """
    Apply the registered ``resolve_directional_barrier_double_touch`` target transformation.
    
    This target uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        target:
          kind: resolve_directional_barrier_double_touch
          params:
            bar_open: <required>
            profit_level: <required>
            stop_level: <required>
            tie_break: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    bar_open:
        Configuration parameter accepted by this target.
    profit_level:
        Configuration parameter accepted by this target.
    stop_level:
        Configuration parameter accepted by this target.
    tie_break:
        Configuration parameter accepted by this target.
    """
    if tie_break == "profit":
        return "profit"
    if tie_break == "stop":
        return "stop"
    profit_distance = abs(bar_open - profit_level)
    stop_distance = abs(bar_open - stop_level)
    if profit_distance < stop_distance:
        return "profit"
    if stop_distance < profit_distance:
        return "stop"
    return "stop"


def _hit_type_for_double_touch(
    *,
    bar_open: float,
    profit_level: float,
    stop_level: float,
    tie_break: str,
) -> str:
    return resolve_directional_barrier_double_touch(
        bar_open=bar_open,
        profit_level=profit_level,
        stop_level=stop_level,
        tie_break=tie_break,
    )


def build_directional_triple_barrier_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``directional_triple_barrier`` target transformation.
    
    This target uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        target:
          kind: directional_triple_barrier
          params:
            add_r_multiple: <configured>
            candidate_col: <configured>
            candidate_out_col: <configured>
            direction_col: <configured>
            entry_price_mode: <configured>
            event_ret_col: <configured>
            fwd_col: <configured>
            high_col: <configured>
            hit_step_col: <configured>
            hit_type_col: <configured>
            horizon: <configured>
            label_col: <configured>
            low_col: <configured>
            lower_barrier_col: <configured>
            lower_mult: <configured>
            max_holding: <configured>
            meta_side_col: <configured>
            min_vol: <configured>
            neutral_label: <configured>
            open_col: <configured>
            oriented_r_col: <configured>
            oriented_ret_col: <configured>
            price_col: <configured>
            profit_barrier_r: <configured>
            r_clip: <configured>
            r_col: <configured>
            side_col: <configured>
            stop_barrier_r: <configured>
            tie_break: <configured>
            upper_barrier_col: <configured>
            upper_mult: <configured>
            vertical_barrier_bars: <configured>
            volatility_col: <configured>
          outputs:
            - configured by candidate_col
            - configured by hit_type_col
            - configured by label_col
    
    Required input columns
    ----------------------
    candidate_out_col:
        Input dataframe column configured by ``candidate_out_col``. Default: ``<configured>``.
    direction_col:
        Input dataframe column configured by ``direction_col``. Default: ``<configured>``.
    event_ret_col:
        Input dataframe column configured by ``event_ret_col``. Default: ``<configured>``.
    fwd_col:
        Input dataframe column configured by ``fwd_col``. Default: ``<configured>``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``<configured>``.
    hit_step_col:
        Input dataframe column configured by ``hit_step_col``. Default: ``<configured>``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``<configured>``.
    lower_barrier_col:
        Input dataframe column configured by ``lower_barrier_col``. Default: ``<configured>``.
    meta_side_col:
        Input dataframe column configured by ``meta_side_col``. Default: ``<configured>``.
    open_col:
        Input dataframe column configured by ``open_col``. Default: ``<configured>``.
    oriented_r_col:
        Input dataframe column configured by ``oriented_r_col``. Default: ``<configured>``.
    oriented_ret_col:
        Input dataframe column configured by ``oriented_ret_col``. Default: ``<configured>``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``<configured>``.
    r_col:
        Input dataframe column configured by ``r_col``. Default: ``<configured>``.
    side_col:
        Input dataframe column configured by ``side_col``. Default: ``<configured>``.
    upper_barrier_col:
        Input dataframe column configured by ``upper_barrier_col``. Default: ``<configured>``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``<configured>``.
    
    Parameters
    ----------
    add_r_multiple:
        Boolean switch controlling optional target behavior. Default: ``<configured>``.
    candidate_col:
        Output dataframe column configured by ``candidate_col``. Default: ``<configured>``.
    candidate_out_col:
        Input dataframe column configured by ``candidate_out_col``. Default: ``<configured>``.
    direction_col:
        Input dataframe column configured by ``direction_col``. Default: ``<configured>``.
    entry_price_mode:
        Mode selector controlling how this target is applied. Default: ``<configured>``.
    event_ret_col:
        Input dataframe column configured by ``event_ret_col``. Default: ``<configured>``.
    fwd_col:
        Input dataframe column configured by ``fwd_col``. Default: ``<configured>``.
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``<configured>``.
    hit_step_col:
        Input dataframe column configured by ``hit_step_col``. Default: ``<configured>``.
    hit_type_col:
        Output dataframe column configured by ``hit_type_col``. Default: ``<configured>``.
    horizon:
        Trailing lookback or forecast horizon controlling this target. Default: ``<configured>``.
    label_col:
        Output dataframe column configured by ``label_col``. Default: ``<configured>``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``<configured>``.
    lower_barrier_col:
        Input dataframe column configured by ``lower_barrier_col``. Default: ``<configured>``.
    lower_mult:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    max_holding:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    meta_side_col:
        Input dataframe column configured by ``meta_side_col``. Default: ``<configured>``.
    min_vol:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    neutral_label:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    open_col:
        Input dataframe column configured by ``open_col``. Default: ``<configured>``.
    oriented_r_col:
        Input dataframe column configured by ``oriented_r_col``. Default: ``<configured>``.
    oriented_ret_col:
        Input dataframe column configured by ``oriented_ret_col``. Default: ``<configured>``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``<configured>``.
    profit_barrier_r:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    r_clip:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    r_col:
        Input dataframe column configured by ``r_col``. Default: ``<configured>``.
    side_col:
        Input dataframe column configured by ``side_col``. Default: ``<configured>``.
    stop_barrier_r:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    tie_break:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    upper_barrier_col:
        Input dataframe column configured by ``upper_barrier_col``. Default: ``<configured>``.
    upper_mult:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    vertical_barrier_bars:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``<configured>``.
    """


    cfg = apply_target_output_aliases(target_cfg)
    price_col = _as_col(cfg.get("price_col"), "close", field="price_col")
    open_col = _as_col(cfg.get("open_col"), "open", field="open_col")
    high_col = _as_col(cfg.get("high_col"), "high", field="high_col")
    low_col = _as_col(cfg.get("low_col"), "low", field="low_col")
    direction_col = _as_col(cfg.get("direction_col", cfg.get("side_col")), "direction", field="direction_col")
    candidate_col = cfg.get("candidate_col")
    candidate_col = str(candidate_col) if candidate_col is not None else None
    volatility_col = _as_col(cfg.get("volatility_col"), "atr_14", field="volatility_col")

    label_col = _as_col(cfg.get("label_col"), "label", field="label_col")
    event_ret_col = _as_col(cfg.get("event_ret_col"), "dtb_event_ret", field="event_ret_col")
    fwd_col = _as_col(cfg.get("fwd_col"), event_ret_col, field="fwd_col")
    candidate_out_col = _as_col(
        cfg.get("candidate_out_col"),
        f"{label_col}_candidate",
        field="candidate_out_col",
    )
    r_col = _as_col(cfg.get("r_col"), "dtb_event_r", field="r_col")
    oriented_r_col = _as_col(cfg.get("oriented_r_col"), "dtb_oriented_r", field="oriented_r_col")
    hit_step_col = _as_col(cfg.get("hit_step_col"), f"{label_col}_hit_step", field="hit_step_col")
    hit_type_col = _as_col(cfg.get("hit_type_col"), f"{label_col}_hit_type", field="hit_type_col")
    upper_barrier_col = _as_col(
        cfg.get("upper_barrier_col"),
        f"{label_col}_upper_barrier",
        field="upper_barrier_col",
    )
    lower_barrier_col = _as_col(
        cfg.get("lower_barrier_col"),
        f"{label_col}_lower_barrier",
        field="lower_barrier_col",
    )
    meta_side_col = _as_col(cfg.get("meta_side_col"), f"{label_col}_meta_side", field="meta_side_col")
    oriented_ret_col = _as_col(
        cfg.get("oriented_ret_col"),
        f"{label_col}_oriented_ret",
        field="oriented_ret_col",
    )

    profit_barrier_r = _finite_positive(
        cfg.get("profit_barrier_r", cfg.get("upper_mult", 1.4)),
        field="profit_barrier_r",
    )
    stop_barrier_r = _finite_positive(
        cfg.get("stop_barrier_r", cfg.get("lower_mult", 1.0)),
        field="stop_barrier_r",
    )
    max_holding = _positive_int(
        cfg.get("vertical_barrier_bars", cfg.get("max_holding", cfg.get("horizon", 4))),
        field="vertical_barrier_bars",
    )
    min_vol = _finite_positive(cfg.get("min_vol", 1e-12), field="min_vol")
    neutral_label = str(cfg.get("neutral_label", "drop"))
    tie_break = str(cfg.get("tie_break", "closest_to_open"))
    entry_price_mode = str(cfg.get("entry_price_mode", "current_close"))
    add_r_multiple = bool(cfg.get("add_r_multiple", False))
    r_clip = _parse_r_clip(cfg.get("r_clip"))

    if neutral_label not in {"drop", "profit", "stop"}:
        raise ValueError("directional_triple_barrier neutral_label must be one of: drop, profit, stop.")
    if tie_break not in {"closest_to_open", "profit", "stop"}:
        raise ValueError("directional_triple_barrier tie_break must be one of: closest_to_open, profit, stop.")
    if entry_price_mode not in {"current_close", "next_open"}:
        raise ValueError("directional_triple_barrier entry_price_mode must be one of: current_close, next_open.")

    required = [price_col, open_col, high_col, low_col, direction_col, volatility_col]
    if candidate_col is not None:
        required.append(candidate_col)
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for directional_triple_barrier target: {missing}")

    out = df.copy()
    prices = out[price_col].astype(float).to_numpy(dtype=float)
    opens = out[open_col].astype(float).to_numpy(dtype=float)
    highs = out[high_col].astype(float).to_numpy(dtype=float)
    lows = out[low_col].astype(float).to_numpy(dtype=float)
    vol = out[volatility_col].astype(float).clip(lower=min_vol).to_numpy(dtype=float)
    direction = np.sign(
        out[direction_col].astype(float).fillna(0.0).clip(lower=-1.0, upper=1.0).to_numpy(dtype=float)
    )
    candidate = direction != 0.0
    if candidate_col is not None:
        candidate &= out[candidate_col].astype(float).fillna(0.0).to_numpy(dtype=float) != 0.0

    labels = np.full(len(out), np.nan, dtype=float)
    event_rets = np.full(len(out), np.nan, dtype=float)
    oriented_rets = np.full(len(out), np.nan, dtype=float)
    event_r = np.full(len(out), np.nan, dtype=float)
    hit_steps = np.full(len(out), np.nan, dtype=float)
    hit_types = np.full(len(out), None, dtype=object)
    upper_levels = np.full(len(out), np.nan, dtype=float)
    lower_levels = np.full(len(out), np.nan, dtype=float)
    evaluated_events = np.full(len(out), False, dtype=bool)
    neutral_events = np.full(len(out), False, dtype=bool)

    full_horizon_cutoff = len(out) - max_holding
    for start_idx in range(len(out)):
        if start_idx >= full_horizon_cutoff:
            continue
        if not candidate[start_idx]:
            continue

        entry_idx = start_idx if entry_price_mode == "current_close" else start_idx + 1
        if entry_idx >= len(out):
            continue
        entry_price = float(prices[start_idx] if entry_price_mode == "current_close" else opens[entry_idx])
        risk_distance = float(stop_barrier_r * vol[start_idx])
        profit_distance = float(profit_barrier_r * vol[start_idx])
        side = float(direction[start_idx])
        if not np.isfinite(entry_price) or entry_price <= 0.0:
            continue
        if not np.isfinite(risk_distance) or risk_distance <= 0.0:
            continue
        if not np.isfinite(profit_distance) or profit_distance <= 0.0:
            continue

        if side > 0.0:
            profit_level = entry_price + profit_distance
            stop_level = entry_price - risk_distance
        else:
            profit_level = entry_price - profit_distance
            stop_level = entry_price + risk_distance

        upper_levels[start_idx] = max(profit_level, stop_level)
        lower_levels[start_idx] = min(profit_level, stop_level)
        evaluated_events[start_idx] = True

        chosen_type: str | None = None
        chosen_step: int | None = None
        exit_price: float | None = None
        horizon_end = min(len(out), start_idx + max_holding + 1)
        for step_idx in range(start_idx + 1, horizon_end):
            if side > 0.0:
                hit_profit = bool(highs[step_idx] >= profit_level)
                hit_stop = bool(lows[step_idx] <= stop_level)
            else:
                hit_profit = bool(lows[step_idx] <= profit_level)
                hit_stop = bool(highs[step_idx] >= stop_level)

            if hit_profit and hit_stop:
                chosen_type = _hit_type_for_double_touch(
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
                chosen_step = step_idx - start_idx
                exit_price = profit_level if chosen_type == "profit" else stop_level
                break

        if chosen_type is None:
            terminal_idx = horizon_end - 1
            chosen_step = terminal_idx - start_idx
            exit_price = float(prices[terminal_idx])
            neutral_events[start_idx] = True
            chosen_type = "neutral"

        raw_return = float(exit_price / entry_price - 1.0)
        oriented_return = raw_return * side
        r_value = float((exit_price - entry_price) * side / risk_distance)

        if chosen_type == "profit":
            labels[start_idx] = 1.0
        elif chosen_type == "stop":
            labels[start_idx] = 0.0
        elif neutral_label == "profit":
            labels[start_idx] = 1.0
        elif neutral_label == "stop":
            labels[start_idx] = 0.0

        event_rets[start_idx] = raw_return
        oriented_rets[start_idx] = oriented_return
        event_r[start_idx] = r_value
        hit_steps[start_idx] = float(chosen_step) if chosen_step is not None else np.nan
        hit_types[start_idx] = chosen_type

    if r_clip is not None:
        event_r = np.clip(event_r, r_clip[0], r_clip[1])
    oriented_r = event_r.copy()

    out[candidate_out_col] = candidate.astype("float32")
    out[meta_side_col] = direction.astype("float32")
    out[oriented_ret_col] = oriented_rets.astype("float32")
    out[event_ret_col] = event_rets.astype("float32")
    if event_ret_col != fwd_col:
        out[fwd_col] = out[event_ret_col]
    out[label_col] = labels.astype("float32")
    out[hit_step_col] = hit_steps.astype("float32")
    out[hit_type_col] = pd.Series(hit_types, index=out.index, dtype="object")
    out[upper_barrier_col] = upper_levels.astype("float32")
    out[lower_barrier_col] = lower_levels.astype("float32")
    if add_r_multiple:
        out[r_col] = event_r.astype("float32")
        out[oriented_r_col] = oriented_r.astype("float32")

    label_series = pd.Series(labels, index=out.index)
    valid = label_series.notna()
    hit_type_series = pd.Series(hit_types, index=out.index, dtype="object")
    hit_step_series = pd.Series(hit_steps, index=out.index).dropna()
    output_cols = [
        label_col,
        event_ret_col,
        fwd_col,
        candidate_out_col,
        hit_step_col,
        hit_type_col,
        upper_barrier_col,
        lower_barrier_col,
        meta_side_col,
        oriented_ret_col,
    ]
    if add_r_multiple:
        output_cols.extend([r_col, oriented_r_col])

    meta = {
        "kind": "directional_triple_barrier",
        "price_col": price_col,
        "open_col": open_col,
        "high_col": high_col,
        "low_col": low_col,
        "direction_col": direction_col,
        "side_col": direction_col,
        "candidate_input_col": candidate_col,
        "candidate_col": candidate_out_col,
        "volatility_col": volatility_col,
        "horizon": int(max_holding),
        "max_holding": int(max_holding),
        "vertical_barrier_bars": int(max_holding),
        "entry_price_mode": entry_price_mode,
        "label_mode": "meta",
        "label_col": label_col,
        "fwd_col": fwd_col,
        "event_ret_col": event_ret_col,
        "output_cols": sorted(set(output_cols)),
        "profit_barrier_r": float(profit_barrier_r),
        "stop_barrier_r": float(stop_barrier_r),
        "neutral_label": neutral_label,
        "tie_break": tie_break,
        "min_vol": min_vol,
        "labeled_rows": int(valid.sum()),
        "candidate_rows": int(candidate.sum()),
        "positive_rate": float(label_series.loc[valid].mean()) if bool(valid.any()) else np.nan,
        "profit_barrier_count": int((hit_type_series == "profit").sum()),
        "stop_barrier_count": int((hit_type_series == "stop").sum()),
        "neutral_count": int(neutral_events.sum()),
        "unavailable_tail_count": int((~evaluated_events).sum()),
        "avg_hit_step": float(hit_step_series.mean()) if not hit_step_series.empty else None,
        "median_hit_step": float(hit_step_series.median()) if not hit_step_series.empty else None,
        "meta_labeling": True,
        "add_r_multiple": bool(add_r_multiple),
        "r_col": r_col if add_r_multiple else None,
        "oriented_r_col": oriented_r_col if add_r_multiple else None,
        "hit_step_col": hit_step_col,
        "hit_type_col": hit_type_col,
        "upper_barrier_col": upper_barrier_col,
        "lower_barrier_col": lower_barrier_col,
        "meta_side_col": meta_side_col,
        "oriented_ret_col": oriented_ret_col,
        "r_clip": list(r_clip) if r_clip is not None else None,
    }
    if add_r_multiple:
        meta["event_r_distribution"] = _numeric_summary(event_r)
        meta["oriented_r_distribution"] = _numeric_summary(oriented_r)
    return out, label_col, fwd_col, meta


__all__ = ["build_directional_triple_barrier_target", "resolve_directional_barrier_double_touch"]
