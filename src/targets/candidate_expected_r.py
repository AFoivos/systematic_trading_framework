from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.targets.output_aliases import apply_target_output_aliases
from src.utils.trade_path import simulate_long_trade_path


CANDIDATE_EXPECTED_R_OUTPUT_COLS = [
    "label",
    "target_trade_r",
    "target_trade_r_clipped",
    "target_event_ret",
    "target_candidate",
    "target_entry_price",
    "target_exit_price",
    "target_stop_price",
    "target_take_profit_price",
    "target_exit_reason",
    "target_bars_held",
    "target_hit_type",
    "target_hit_step",
    "target_mfe_r",
    "target_mae_r",
    "target_time_to_mfe",
    "target_time_to_mae",
]


def _flatten_cfg(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(target_cfg or {})
    params = cfg.pop("params", None)
    if params is not None:
        if not isinstance(params, dict):
            raise ValueError("candidate_expected_r target params must be a mapping when provided.")
        cfg.update(dict(params))
    return cfg


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in dict.fromkeys(columns) if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for candidate_expected_r target: {missing}")


def _finite_positive(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"candidate_expected_r target {field} must be a finite positive number.")
    return out


def _finite_number(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"candidate_expected_r target {field} must be a finite number.")
    return out


def _clip_bounds(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("candidate_expected_r target clip_r must be a two-element list.")
    low = _finite_number(value[0], field="clip_r[0]")
    high = _finite_number(value[1], field="clip_r[1]")
    if low > high:
        raise ValueError("candidate_expected_r target clip_r[0] must be <= clip_r[1].")
    return low, high


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


def _time_to_extreme_r(
    *,
    highs: np.ndarray,
    lows: np.ndarray,
    entry_idx: int,
    max_exit_idx: int,
    entry_price: float,
    risk_distance_price: float,
) -> tuple[float, float, float, float]:
    mfe = -np.inf
    mae = np.inf
    time_to_mfe = np.nan
    time_to_mae = np.nan
    for idx in range(entry_idx, max_exit_idx + 1):
        high = float(highs[idx])
        low = float(lows[idx])
        if not np.isfinite(high) or not np.isfinite(low):
            continue
        favorable = (high - entry_price) / risk_distance_price
        adverse = (low - entry_price) / risk_distance_price
        step = float(idx - entry_idx)
        if favorable > mfe:
            mfe = float(favorable)
            time_to_mfe = step
        if adverse < mae:
            mae = float(adverse)
            time_to_mae = step
    return (
        float(mfe) if np.isfinite(mfe) else np.nan,
        float(mae) if np.isfinite(mae) else np.nan,
        time_to_mfe,
        time_to_mae,
    )


def build_candidate_expected_r_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``candidate_expected_r`` target transformation.

    This target labels only candidate rows and uses future OHLC data solely for
    target construction diagnostics.

    YAML declaration::

        target:
          kind: candidate_expected_r
          candidate_col: signal_candidate
          side: long_only
          entry_price_mode: next_open
          volatility_col: atr_over_price_14

    Required input columns
    ----------------------
    candidate_col:
        Candidate flag column. Default: ``signal_candidate``.
    open_col, high_col, low_col, close_col:
        OHLC columns used to simulate the future trade path.
    volatility_col:
        Required when ``stop_mode`` is ``volatility_stop``.

    Parameters
    ----------
    target_cfg:
        Target configuration mapping. Supports ``params`` nesting.
    """
    cfg = apply_target_output_aliases(_flatten_cfg(target_cfg))
    candidate_col = str(cfg.get("candidate_col", "signal_candidate"))
    side_col = str(cfg.get("side_col", "signal_side"))
    side = str(cfg.get("side", "long_only"))
    entry_price_mode = str(cfg.get("entry_price_mode", "next_open"))
    open_col = str(cfg.get("open_col", "open"))
    high_col = str(cfg.get("high_col", "high"))
    low_col = str(cfg.get("low_col", "low"))
    close_col = str(cfg.get("close_col", "close"))
    price_col = str(cfg.get("price_col", "close"))
    volatility_col = str(cfg.get("volatility_col", "atr_over_price_14"))
    stop_mode = str(cfg.get("stop_mode", "volatility_stop"))
    stop_loss_r = _finite_positive(cfg.get("stop_loss_r", 1.5), field="stop_loss_r")
    take_profit_r = _finite_positive(cfg.get("take_profit_r", 2.5), field="take_profit_r")
    max_holding_bars = int(cfg.get("max_holding_bars", 16))
    target_r_min = _finite_number(cfg.get("target_r_min", 0.75), field="target_r_min")
    clip_low, clip_high = _clip_bounds(cfg.get("clip_r", [-2.0, 3.0]))
    tie_break = str(cfg.get("tie_break", "conservative"))
    allow_partial_horizon = bool(cfg.get("allow_partial_horizon", False))
    stop_loss_return = _finite_positive(cfg.get("stop_loss_return", 0.005), field="stop_loss_return")

    label_col = str(cfg.get("label_col", "label"))
    trade_r_col = str(cfg.get("trade_r_col", "target_trade_r"))
    trade_r_clipped_col = str(cfg.get("trade_r_clipped_col", "target_trade_r_clipped"))
    event_ret_col = str(cfg.get("event_ret_col", cfg.get("fwd_col", "target_event_ret")))
    candidate_out_col = str(cfg.get("candidate_out_col", "target_candidate"))
    entry_price_col = str(cfg.get("entry_price_col", "target_entry_price"))
    exit_price_col = str(cfg.get("exit_price_col", "target_exit_price"))
    stop_price_col = str(cfg.get("stop_price_col", "target_stop_price"))
    take_profit_price_col = str(cfg.get("take_profit_price_col", "target_take_profit_price"))
    exit_reason_col = str(cfg.get("exit_reason_col", "target_exit_reason"))
    bars_held_col = str(cfg.get("bars_held_col", "target_bars_held"))
    hit_type_col = str(cfg.get("hit_type_col", "target_hit_type"))
    hit_step_col = str(cfg.get("hit_step_col", "target_hit_step"))
    mfe_r_col = str(cfg.get("mfe_r_col", "target_mfe_r"))
    mae_r_col = str(cfg.get("mae_r_col", "target_mae_r"))
    time_to_mfe_col = str(cfg.get("time_to_mfe_col", "target_time_to_mfe"))
    time_to_mae_col = str(cfg.get("time_to_mae_col", "target_time_to_mae"))

    if side != "long_only":
        raise ValueError("candidate_expected_r target currently supports side='long_only' only.")
    if entry_price_mode not in {"next_open", "current_close"}:
        raise ValueError("candidate_expected_r target entry_price_mode must be one of: next_open, current_close.")
    if stop_mode not in {"volatility_stop", "fixed_return"}:
        raise ValueError("candidate_expected_r target stop_mode must be one of: volatility_stop, fixed_return.")
    if max_holding_bars <= 0:
        raise ValueError("candidate_expected_r target max_holding_bars must be positive.")
    if tie_break not in {"conservative", "take_profit", "stop_loss", "closest_to_open"}:
        raise ValueError(
            "candidate_expected_r target tie_break must be one of: conservative, take_profit, stop_loss, closest_to_open."
        )

    required = [candidate_col, price_col, open_col, high_col, low_col, close_col]
    if stop_mode == "volatility_stop":
        required.append(volatility_col)
    _require_columns(df, required)

    out = df.copy()
    n = len(out)
    prices = pd.to_numeric(out[price_col], errors="coerce").to_numpy(dtype=float)
    opens = pd.to_numeric(out[open_col], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(out[high_col], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(out[low_col], errors="coerce").to_numpy(dtype=float)
    closes = pd.to_numeric(out[close_col], errors="coerce").to_numpy(dtype=float)
    vol_values = (
        pd.to_numeric(out[volatility_col], errors="coerce").to_numpy(dtype=float)
        if stop_mode == "volatility_stop"
        else np.full(n, np.nan, dtype=float)
    )

    candidates = pd.to_numeric(out[candidate_col], errors="coerce").fillna(0.0).to_numpy(dtype=float) > 0.0
    if side_col in out.columns:
        sides = pd.to_numeric(out[side_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        candidates &= sides > 0.0

    labels = np.full(n, np.nan, dtype=float)
    event_rets = np.full(n, np.nan, dtype=float)
    trade_rs = np.full(n, np.nan, dtype=float)
    clipped_rs = np.full(n, np.nan, dtype=float)
    entry_prices = np.full(n, np.nan, dtype=float)
    exit_prices = np.full(n, np.nan, dtype=float)
    stop_prices = np.full(n, np.nan, dtype=float)
    take_profit_prices = np.full(n, np.nan, dtype=float)
    bars_held_values = np.full(n, np.nan, dtype=float)
    hit_steps = np.full(n, np.nan, dtype=float)
    mfe_values = np.full(n, np.nan, dtype=float)
    mae_values = np.full(n, np.nan, dtype=float)
    time_to_mfe_values = np.full(n, np.nan, dtype=float)
    time_to_mae_values = np.full(n, np.nan, dtype=float)
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
            take_profit_distance_return = risk_distance_return * take_profit_r / stop_loss_r
        if not np.isfinite(risk_distance_return) or risk_distance_return <= 0.0:
            exit_reasons[start_idx] = "invalid_entry"
            continue
        if not np.isfinite(take_profit_distance_return) or take_profit_distance_return <= 0.0:
            exit_reasons[start_idx] = "invalid_entry"
            continue

        stop_price = entry_price * max(1.0 - risk_distance_return, 1e-12)
        take_profit_price = entry_price * (1.0 + take_profit_distance_return)
        risk_distance_price = entry_price - stop_price
        entry_prices[start_idx] = entry_price
        stop_prices[start_idx] = stop_price
        take_profit_prices[start_idx] = take_profit_price
        mfe, mae, time_to_mfe, time_to_mae = _time_to_extreme_r(
            highs=highs,
            lows=lows,
            entry_idx=entry_idx,
            max_exit_idx=max_exit_idx,
            entry_price=entry_price,
            risk_distance_price=risk_distance_price,
        )
        mfe_values[start_idx] = mfe
        mae_values[start_idx] = mae
        time_to_mfe_values[start_idx] = time_to_mfe
        time_to_mae_values[start_idx] = time_to_mae

        try:
            path = simulate_long_trade_path(
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                signals=None,
                entry_idx=entry_idx,
                max_exit_idx=max_exit_idx,
                entry_price=entry_price,
                initial_stop_price=stop_price,
                take_profit_price=take_profit_price,
                dynamic_exits=None,
                tie_break=tie_break,
            )
        except ValueError:
            exit_reasons[start_idx] = "invalid_entry"
            continue

        exit_idx = int(path["exit_idx"])
        exit_price = float(path["raw_exit_price"])
        if not np.isfinite(exit_price) or exit_price <= 0.0:
            exit_reasons[start_idx] = "invalid_entry"
            continue
        trade_ret = exit_price / entry_price - 1.0
        trade_r = trade_ret / risk_distance_return
        event_rets[start_idx] = trade_ret
        trade_rs[start_idx] = trade_r
        clipped_rs[start_idx] = float(np.clip(trade_r, clip_low, clip_high))
        exit_prices[start_idx] = exit_price
        bars_held_values[start_idx] = float(path["bars_held"])
        hit_steps[start_idx] = float(exit_idx - entry_idx)
        exit_reasons[start_idx] = str(path["exit_reason"])
        labels[start_idx] = 1.0 if trade_r >= target_r_min else 0.0

    out[candidate_out_col] = candidates.astype("float32")
    out[event_ret_col] = event_rets.astype("float32")
    out[trade_r_col] = trade_rs.astype("float32")
    out[trade_r_clipped_col] = clipped_rs.astype("float32")
    out[entry_price_col] = entry_prices.astype("float64")
    out[exit_price_col] = exit_prices.astype("float64")
    out[stop_price_col] = stop_prices.astype("float64")
    out[take_profit_price_col] = take_profit_prices.astype("float64")
    out[exit_reason_col] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out[bars_held_col] = bars_held_values.astype("float32")
    out[hit_type_col] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out[hit_step_col] = hit_steps.astype("float32")
    out[mfe_r_col] = mfe_values.astype("float32")
    out[mae_r_col] = mae_values.astype("float32")
    out[time_to_mfe_col] = time_to_mfe_values.astype("float32")
    out[time_to_mae_col] = time_to_mae_values.astype("float32")
    out[label_col] = labels.astype("float32")

    label_series = pd.Series(labels, index=out.index)
    valid_labels = label_series.notna()
    trade_r_series = pd.Series(trade_rs, index=out.index).dropna().astype(float)
    mfe_series = pd.Series(mfe_values, index=out.index).dropna().astype(float)
    mae_series = pd.Series(mae_values, index=out.index).dropna().astype(float)
    exit_reason_series = pd.Series(exit_reasons, index=out.index, dtype="object")
    exit_counts = exit_reason_series.value_counts(dropna=True).to_dict()
    label_counts = label_series.loc[valid_labels].astype(int).value_counts().sort_index()
    output_cols = [
        label_col,
        trade_r_col,
        trade_r_clipped_col,
        event_ret_col,
        candidate_out_col,
        entry_price_col,
        exit_price_col,
        stop_price_col,
        take_profit_price_col,
        exit_reason_col,
        bars_held_col,
        hit_type_col,
        hit_step_col,
        mfe_r_col,
        mae_r_col,
        time_to_mfe_col,
        time_to_mae_col,
    ]
    meta = {
        "kind": "candidate_expected_r",
        "label_col": label_col,
        "fwd_col": event_ret_col,
        "event_ret_col": event_ret_col,
        "trade_r_col": trade_r_col,
        "trade_r_clipped_col": trade_r_clipped_col,
        "candidate_col": candidate_col,
        "candidate_out_col": candidate_out_col,
        "candidate_rows": int(candidates.sum()),
        "labeled_rows": int(valid_labels.sum()),
        "positive_rate": float(label_series.loc[valid_labels].mean()) if bool(valid_labels.any()) else None,
        "avg_trade_r": _numeric_mean(trade_r_series),
        "median_trade_r": _numeric_median(trade_r_series),
        "q25_trade_r": _numeric_quantile(trade_r_series, 0.25),
        "q75_trade_r": _numeric_quantile(trade_r_series, 0.75),
        "avg_mfe_r": _numeric_mean(mfe_series),
        "avg_mae_r": _numeric_mean(mae_series),
        "exit_reason_counts": {str(key): int(value) for key, value in exit_counts.items()},
        "label_distribution": {
            "rows": int(valid_labels.sum()),
            "class_counts": {str(int(key)): int(value) for key, value in label_counts.items()},
            "positive_rate": float(label_series.loc[valid_labels].mean()) if bool(valid_labels.any()) else None,
        },
        "output_cols": sorted(set(output_cols)),
        "entry_price_mode": entry_price_mode,
        "side": side,
        "side_col": side_col if side_col in out.columns else None,
        "stop_mode": stop_mode,
        "stop_loss_r": stop_loss_r,
        "take_profit_r": take_profit_r,
        "max_holding_bars": max_holding_bars,
        "target_r_min": target_r_min,
        "clip_r": [clip_low, clip_high],
        "tie_break": tie_break,
        "allow_partial_horizon": allow_partial_horizon,
        "mfe_r_col": mfe_r_col,
        "mae_r_col": mae_r_col,
        "time_to_mfe_col": time_to_mfe_col,
        "time_to_mae_col": time_to_mae_col,
    }
    return out, label_col, event_ret_col, meta


__all__ = ["CANDIDATE_EXPECTED_R_OUTPUT_COLS", "build_candidate_expected_r_target"]
