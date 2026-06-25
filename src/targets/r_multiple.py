from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.utils.trade_path import simulate_long_trade_path
from src.targets.output_aliases import apply_target_output_aliases


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
    Build a long-only R-multiple meta-label target for already-emitted strategy
    candidates.
    
    This target evaluates only rows where ``candidate_col`` is positive. For
    each candidate row, it simulates a realistic long trade path using entry
    price, stop loss, take profit, and maximum holding period. The resulting
    trade is converted into R-multiple units and labeled according to whether
    the trade achieved at least ``target_r_min`` R.
    
    Labels:
    - 1.0 when the simulated trade reaches ``target_r_min`` or more.
    - 0.0 when the simulated trade produces less than ``target_r_min``.
    - NaN when the row is not a candidate or cannot be evaluated.
    
    This is mainly used for meta-labeling: the manual/rule-based strategy
    creates trade candidates, and the ML model learns which candidates are
    worth keeping.
    
    YAML declaration inside model config::
    
        model:
          kind: lightgbm_clf
          target:
            kind: r_multiple
    
            candidate_col: signal_candidate
    
            price_col: close
            open_col: open
            high_col: high
            low_col: low
    
            volatility_col: atr_over_price_14
            stop_mode: volatility_stop
    
            entry_price_mode: next_open
            side: long_only
    
            target_r_min: 1.0
            take_profit_r: 2.0
            stop_loss_r: 1.0
            max_holding_bars: 16
    
            tie_break: conservative
            allow_partial_horizon: false
    
            outputs:
              label_col: label
              fwd_col: r_target_event_ret
              candidate_out_col: r_target_candidate
              trade_r_col: r_target_trade_r
              oriented_r_col: r_target_oriented_r
              entry_price_col: r_target_entry_price
              exit_price_col: r_target_exit_price
              stop_price_col: r_target_stop_price
              take_profit_price_col: r_target_take_profit_price
              exit_reason_col: r_target_exit_reason
              bars_held_col: r_target_bars_held
              hit_type_col: r_target_hit_type
              hit_step_col: r_target_hit_step
    
            diagnostic_feature_cols: null
    
          output_cols:
            - label
            - r_target_event_ret
            - r_target_candidate
            - r_target_trade_r
            - r_target_oriented_r
            - r_target_entry_price
            - r_target_exit_price
            - r_target_stop_price
            - r_target_take_profit_price
            - r_target_exit_reason
            - r_target_bars_held
            - r_target_hit_type
            - r_target_hit_step
    
    YAML declaration with fixed-return stop mode::
    
        model:
          kind: lightgbm_clf
          target:
            kind: r_multiple
    
            candidate_col: signal_candidate
    
            price_col: close
            open_col: open
            high_col: high
            low_col: low
    
            stop_mode: fixed_return
            stop_loss_return: 0.005
            take_profit_return: 0.010
    
            entry_price_mode: next_open
            side: long_only
    
            target_r_min: 1.0
            max_holding_bars: 16
    
            tie_break: conservative
            allow_partial_horizon: false
    
            outputs:
              label_col: label
              fwd_col: r_target_event_ret
              candidate_out_col: r_target_candidate
              trade_r_col: r_target_trade_r
              oriented_r_col: r_target_oriented_r
              entry_price_col: r_target_entry_price
              exit_price_col: r_target_exit_price
              stop_price_col: r_target_stop_price
              take_profit_price_col: r_target_take_profit_price
              exit_reason_col: r_target_exit_reason
              bars_held_col: r_target_bars_held
              hit_type_col: r_target_hit_type
              hit_step_col: r_target_hit_step
    
          output_cols:
            - label
            - r_target_event_ret
            - r_target_candidate
            - r_target_trade_r
            - r_target_oriented_r
            - r_target_entry_price
            - r_target_exit_price
            - r_target_stop_price
            - r_target_take_profit_price
            - r_target_exit_reason
            - r_target_bars_held
            - r_target_hit_type
            - r_target_hit_step
    
    YAML declaration::
    
        target:
          kind: r_multiple
          params: {}
    
    Required input columns
    ----------------------
    bars_held:
        Required dataframe column read directly by this component.
    exit_idx:
        Required dataframe column read directly by this component.
    exit_reason:
        Required dataframe column read directly by this component.
    raw_exit_price:
        Required dataframe column read directly by this component.
    
    Parameters
    ----------
    candidate_col:
        Input column that marks candidate trades. Rows are evaluated only when
        this column is greater than zero.
    label_col:
        Output binary target column. A value of 1 means the candidate achieved
        at least ``target_r_min`` R; a value of 0 means it did not.
    fwd_col:
        Output event return column passed back to the model pipeline as the
        forward-return column.
    candidate_out_col:
        Output column showing which rows were candidate trades.
    trade_r_col:
        Output column containing the realized R-multiple of the simulated trade.
    oriented_r_col:
        Output oriented R-multiple column. For long-only targets this is the
        same as ``trade_r_col``.
    entry_price_col:
        Output column with the simulated entry price.
    exit_price_col:
        Output column with the simulated exit price.
    stop_price_col:
        Output column with the stop-loss price.
    take_profit_price_col:
        Output column with the take-profit price.
    exit_reason_col:
        Output column with the trade exit reason, such as ``take_profit``,
        ``stop_loss``, ``max_holding_close``, ``unavailable_tail``, or
        ``invalid_entry``.
    bars_held_col:
        Output column with the number of bars held.
    hit_type_col:
        Output column mirroring the exit reason.
    hit_step_col:
        Output column with the number of bars from entry until exit.
    
    price_col:
        Input close/price column. Used for current-close entry mode and as the
        close path during trade simulation.
    open_col:
        Input open column. Used for next-open entry mode and intrabar
        tie-break logic.
    high_col:
        Input high column used to detect take-profit and stop-loss touches.
    low_col:
        Input low column used to detect take-profit and stop-loss touches.
    volatility_col:
        Input volatility column used when ``stop_mode`` is
        ``volatility_stop``. This should usually be a return/ratio volatility
        column, for example ATR divided by price.
    entry_price_mode:
        Entry assumption. Allowed values are ``next_open`` and
        ``current_close``.
    side:
        Trade side. Current implementation supports only ``long_only``.
    
    target_r_min:
        Minimum realized R-multiple required for label 1.
    take_profit_r:
        Take-profit distance in R units when ``stop_mode`` is
        ``volatility_stop``.
    stop_loss_r:
        Stop-loss distance multiplier when ``stop_mode`` is
        ``volatility_stop``.
    max_holding_bars:
        Maximum number of bars the simulated trade can remain open.
    stop_mode:
        Stop/take-profit distance mode. Allowed values are
        ``volatility_stop`` and ``fixed_return``.
    stop_loss_return:
        Fixed stop-loss return distance used only when ``stop_mode`` is
        ``fixed_return``.
    take_profit_return:
        Fixed take-profit return distance used only when ``stop_mode`` is
        ``fixed_return``.
    tie_break:
        Rule used when stop loss and take profit are both touched inside the
        same bar. Allowed values are ``conservative``, ``take_profit``,
        ``stop_loss``, and ``closest_to_open``.
    allow_partial_horizon:
        If false, candidates near the end of the dataset are marked unavailable
        when the full max-holding horizon is not available. If true, the target
        allows a shortened final horizon.
    
    diagnostic_feature_cols:
        Optional list of feature columns used only for winner/loser diagnostic
        summaries in metadata.
    """

    cfg = apply_target_output_aliases(_flatten_cfg(target_cfg))
    candidate_col = str(cfg.get("candidate_col", "manual_long_signal"))
    label_col = str(cfg.get("label_col", "label"))
    fwd_col = str(cfg.get("fwd_col", "r_target_event_ret"))
    candidate_out_col = str(cfg.get("candidate_out_col", "r_target_candidate"))
    trade_r_col = str(cfg.get("trade_r_col", cfg.get("r_col", "r_target_trade_r")))
    oriented_r_col = str(cfg.get("oriented_r_col", "r_target_oriented_r"))
    entry_price_col = str(cfg.get("entry_price_col", "r_target_entry_price"))
    exit_price_col = str(cfg.get("exit_price_col", "r_target_exit_price"))
    stop_price_col = str(cfg.get("stop_price_col", "r_target_stop_price"))
    take_profit_price_col = str(cfg.get("take_profit_price_col", "r_target_take_profit_price"))
    exit_reason_col = str(cfg.get("exit_reason_col", "r_target_exit_reason"))
    bars_held_col = str(cfg.get("bars_held_col", "r_target_bars_held"))
    hit_type_col = str(cfg.get("hit_type_col", "r_target_hit_type"))
    hit_step_col = str(cfg.get("hit_step_col", "r_target_hit_step"))
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

        try:
            path = simulate_long_trade_path(
                opens=opens,
                highs=highs,
                lows=lows,
                closes=prices,
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
        exit_reason = str(path["exit_reason"])
        if not np.isfinite(exit_price) or exit_price <= 0.0:
            exit_reasons[start_idx] = "invalid_entry"
            continue

        trade_ret = exit_price / entry_price - 1.0
        trade_r = trade_ret / risk_distance_return
        event_rets[start_idx] = trade_ret
        trade_rs[start_idx] = trade_r
        exit_prices[start_idx] = exit_price
        bars_held_values[start_idx] = float(path["bars_held"])
        hit_steps[start_idx] = float(exit_idx - entry_idx)
        exit_reasons[start_idx] = exit_reason
        labels[start_idx] = 1.0 if trade_r >= target_r_min else 0.0

    out[candidate_out_col] = candidates.astype("float32")
    out[fwd_col] = event_rets.astype("float32")
    out[trade_r_col] = trade_rs.astype("float32")
    out[oriented_r_col] = trade_rs.astype("float32")
    out[entry_price_col] = entry_prices.astype("float64")
    out[exit_price_col] = exit_prices.astype("float64")
    out[stop_price_col] = stop_prices.astype("float64")
    out[take_profit_price_col] = take_profit_prices.astype("float64")
    out[exit_reason_col] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out[bars_held_col] = bars_held_values.astype("float32")
    out[hit_type_col] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out[hit_step_col] = hit_steps.astype("float32")
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
        trade_r_col,
        oriented_r_col,
        candidate_out_col,
        entry_price_col,
        exit_price_col,
        stop_price_col,
        take_profit_price_col,
        exit_reason_col,
        bars_held_col,
        hit_type_col,
        hit_step_col,
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
        "oriented_r_col": oriented_r_col,
        "r_col": trade_r_col,
        "trade_r_col": trade_r_col,
        "entry_price_col": entry_price_col,
        "exit_price_col": exit_price_col,
        "stop_price_col": stop_price_col,
        "take_profit_price_col": take_profit_price_col,
        "exit_reason_col": exit_reason_col,
        "bars_held_col": bars_held_col,
        "hit_type_col": hit_type_col,
        "hit_step_col": hit_step_col,
    }
    return out, label_col, fwd_col, meta


__all__ = ["R_MULTIPLE_TARGET_OUTPUT_COLS", "build_r_multiple_target"]
