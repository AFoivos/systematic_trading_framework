from __future__ import annotations

"""Path-identical MATB target backed by the shared strategy-path simulator."""

from typing import Any

import numpy as np
import pandas as pd

from src.utils.trade_path import simulate_strategy_path_trade_outcome


STRATEGY_PATH_R_OUTPUT_COLS = (
    "matb_net_trade_r",
    "matb_gross_trade_r",
    "matb_trade_return",
    "matb_gross_trade_return",
    "matb_exit_reason",
    "matb_bars_held",
    "matb_mfe_r",
    "matb_mae_r",
    "matb_entry_timestamp",
    "matb_exit_timestamp",
    "matb_entry_price",
    "matb_exit_price",
    "matb_transaction_cost_r",
    "matb_event_available",
    "matb_label_success",
    "matb_execution_source",
    "matb_initial_stop_price",
    "matb_emergency_profit_price",
)


def _flatten_cfg(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(target_cfg or {})
    params = cfg.pop("params", None)
    if params is not None:
        if not isinstance(params, dict):
            raise ValueError("strategy_path_r target params must be a mapping when provided.")
        cfg.update(dict(params))
    return cfg


def _column(cfg: dict[str, Any], key: str, default: str) -> str:
    value = str(cfg.get(key, default)).strip()
    if not value:
        raise ValueError(f"strategy_path_r {key} must be a non-empty string.")
    return value


def _quote_arrays(
    frame: pd.DataFrame,
    *,
    columns: dict[str, str],
    strict_bid_ask: bool,
) -> dict[str, np.ndarray | None]:
    present = {key: column in frame.columns for key, column in columns.items()}
    if any(present.values()) and not all(present.values()) and strict_bid_ask:
        missing = [columns[key] for key, available in present.items() if not available]
        raise KeyError(f"strategy_path_r strict bid/ask execution is missing columns: {missing}")
    if not all(present.values()):
        return {key: None for key in columns}
    return {
        key: pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        for key, column in columns.items()
    }


def build_strategy_path_r_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build long/short MATB outcomes with the exact production trade-path policy.

    Only deterministic candidate rows are simulated. A later candidate in the
    same asset is unavailable while an earlier target trade is still open,
    matching the portfolio engine's one-position-per-asset rule.

    YAML declaration::

        target:
          kind: strategy_path_r
          params:
            candidate_col: matb_candidate
            side_col: matb_side
            volatility_col: matb_atr
            trend_score_col: matb_trend_score
            entry_price_mode: next_open
            stop_loss_r: 2.0
            emergency_profit_r: 8.0
            trailing_activation_r: 1.5
            trailing_distance_atr: 2.5
            max_holding_bars: 1440
            tie_break: closest_to_open
            strict_bid_ask: true

    Required input columns
    ----------------------
    candidate_col, side_col:
        Causal deterministic event flag and its fixed long/short side.
    open_col, high_col, low_col, close_col:
        Midpoint/reference OHLC fallback path.
    volatility_col, trend_score_col:
        Point-in-time ATR and causal MATB trend score.
    bid/ask columns:
        Used for executable paths whenever the complete quote set is present.

    Parameters
    ----------
    stop_loss_r:
        Initial stop distance in signal-time ATR units. Default: ``2.0``.
    emergency_profit_r:
        Emergency cap in initial-risk units. Default: ``8.0``.
    trailing_activation_r, trailing_distance_atr:
        Monotone dynamic trailing-stop policy.
    max_holding_bars:
        Maximum 30-minute bars in the trade. Default: ``1440``.
    """
    cfg = _flatten_cfg(target_cfg)
    candidate_col = _column(cfg, "candidate_col", "matb_candidate")
    side_col = _column(cfg, "side_col", "matb_side")
    open_col = _column(cfg, "open_col", "open")
    high_col = _column(cfg, "high_col", "high")
    low_col = _column(cfg, "low_col", "low")
    close_col = _column(cfg, "close_col", "close")
    volatility_col = _column(cfg, "volatility_col", "matb_atr")
    trend_score_col = _column(cfg, "trend_score_col", "matb_trend_score")
    label_col = _column(cfg, "label_col", "matb_label_success")
    fwd_col = _column(cfg, "fwd_col", "matb_net_trade_r")

    required = [
        candidate_col,
        side_col,
        open_col,
        high_col,
        low_col,
        close_col,
        volatility_col,
        trend_score_col,
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for strategy_path_r target: {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("strategy_path_r requires a DatetimeIndex.")
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError("strategy_path_r requires unique, chronologically sorted timestamps.")

    entry_price_mode = str(cfg.get("entry_price_mode", "next_open"))
    if entry_price_mode != "next_open":
        raise ValueError("strategy_path_r requires entry_price_mode='next_open'.")
    tie_break = str(cfg.get("tie_break", "closest_to_open"))
    strict_bid_ask = bool(cfg.get("strict_bid_ask", True))
    allow_partial_horizon = bool(cfg.get("allow_partial_horizon", False))
    enforce_single_position = bool(cfg.get("enforce_single_position", True))
    entry_delay_bars = int(cfg.get("entry_delay_bars", 0))
    max_holding_bars = int(cfg.get("max_holding_bars", 1440))
    stop_loss_atr = float(cfg.get("stop_loss_r", cfg.get("stop_loss_atr", 2.0)))
    emergency_profit_r = float(cfg.get("emergency_profit_r", 8.0))
    trailing_activation_r = float(cfg.get("trailing_activation_r", 1.5))
    trailing_distance_atr = float(cfg.get("trailing_distance_atr", 2.5))
    cost_per_unit_turnover = float(
        cfg.get("cost_per_unit_turnover", cfg.get("cost_per_turnover", 0.0))
    )
    slippage_per_unit_turnover = float(
        cfg.get("slippage_per_unit_turnover", cfg.get("slippage_per_turnover", 0.0))
    )

    out = df.copy()
    opens = pd.to_numeric(out[open_col], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(out[high_col], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(out[low_col], errors="coerce").to_numpy(dtype=float)
    closes = pd.to_numeric(out[close_col], errors="coerce").to_numpy(dtype=float)
    volatility = pd.to_numeric(out[volatility_col], errors="coerce").to_numpy(dtype=float)
    trend_score = pd.to_numeric(out[trend_score_col], errors="coerce").to_numpy(dtype=float)
    candidates = pd.to_numeric(out[candidate_col], errors="coerce").fillna(0.0).eq(1.0).to_numpy()
    sides = np.sign(pd.to_numeric(out[side_col], errors="coerce").fillna(0.0).to_numpy(dtype=float))
    quote_columns = {
        "bid_opens": _column(cfg, "bid_open_col", "bid_open"),
        "bid_highs": _column(cfg, "bid_high_col", "bid_high"),
        "bid_lows": _column(cfg, "bid_low_col", "bid_low"),
        "bid_closes": _column(cfg, "bid_close_col", "bid_close"),
        "ask_opens": _column(cfg, "ask_open_col", "ask_open"),
        "ask_highs": _column(cfg, "ask_high_col", "ask_high"),
        "ask_lows": _column(cfg, "ask_low_col", "ask_low"),
        "ask_closes": _column(cfg, "ask_close_col", "ask_close"),
    }
    quotes = _quote_arrays(out, columns=quote_columns, strict_bid_ask=strict_bid_ask)

    numeric_outputs = {
        "matb_net_trade_r": np.full(len(out), np.nan, dtype=float),
        "matb_gross_trade_r": np.full(len(out), np.nan, dtype=float),
        "matb_trade_return": np.full(len(out), np.nan, dtype=float),
        "matb_gross_trade_return": np.full(len(out), np.nan, dtype=float),
        "matb_bars_held": np.full(len(out), np.nan, dtype=float),
        "matb_mfe_r": np.full(len(out), np.nan, dtype=float),
        "matb_mae_r": np.full(len(out), np.nan, dtype=float),
        "matb_entry_price": np.full(len(out), np.nan, dtype=float),
        "matb_exit_price": np.full(len(out), np.nan, dtype=float),
        "matb_transaction_cost_r": np.full(len(out), np.nan, dtype=float),
        "matb_initial_stop_price": np.full(len(out), np.nan, dtype=float),
        "matb_emergency_profit_price": np.full(len(out), np.nan, dtype=float),
        label_col: np.full(len(out), np.nan, dtype=float),
    }
    event_available = np.zeros(len(out), dtype=np.int8)
    exit_reasons = np.full(len(out), None, dtype=object)
    execution_sources = np.full(len(out), None, dtype=object)
    timestamp_dtype = (
        f"datetime64[ns, {out.index.tz}]" if out.index.tz is not None else "datetime64[ns]"
    )
    entry_timestamps = pd.Series(pd.NaT, index=out.index, dtype=timestamp_dtype)
    exit_timestamps = pd.Series(pd.NaT, index=out.index, dtype=timestamp_dtype)
    occupied_until_idx = -1
    invalid_counts: dict[str, int] = {}

    for signal_idx in np.flatnonzero(candidates & (sides != 0.0)):
        if enforce_single_position and int(signal_idx) < int(occupied_until_idx):
            exit_reasons[signal_idx] = "overlapping_open_trade"
            invalid_counts["overlapping_open_trade"] = invalid_counts.get("overlapping_open_trade", 0) + 1
            continue
        outcome = simulate_strategy_path_trade_outcome(
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volatility=volatility,
            trend_score=trend_score,
            signal_idx=int(signal_idx),
            side=int(sides[signal_idx]),
            entry_price_mode=entry_price_mode,
            entry_delay_bars=entry_delay_bars,
            stop_loss_atr=stop_loss_atr,
            emergency_profit_r=emergency_profit_r,
            trailing_activation_r=trailing_activation_r,
            trailing_distance_atr=trailing_distance_atr,
            max_holding_bars=max_holding_bars,
            tie_break=tie_break,
            strict_bid_ask=strict_bid_ask,
            allow_partial_horizon=allow_partial_horizon,
            cost_per_unit_turnover=cost_per_unit_turnover,
            slippage_per_unit_turnover=slippage_per_unit_turnover,
            **quotes,
        )
        if not bool(outcome["valid"]):
            reason = str(outcome["exit_reason"])
            exit_reasons[signal_idx] = reason
            invalid_counts[reason] = invalid_counts.get(reason, 0) + 1
            continue

        entry_idx = int(outcome["entry_idx"])
        exit_idx = int(outcome["exit_idx"])
        occupied_until_idx = max(occupied_until_idx, exit_idx)
        event_available[signal_idx] = 1
        numeric_outputs["matb_net_trade_r"][signal_idx] = float(outcome["net_r"])
        numeric_outputs["matb_gross_trade_r"][signal_idx] = float(outcome["gross_r"])
        numeric_outputs["matb_trade_return"][signal_idx] = float(outcome["net_return"])
        numeric_outputs["matb_gross_trade_return"][signal_idx] = float(outcome["gross_return"])
        numeric_outputs["matb_bars_held"][signal_idx] = float(outcome["bars_held"])
        numeric_outputs["matb_mfe_r"][signal_idx] = float(outcome["max_favorable_r"])
        numeric_outputs["matb_mae_r"][signal_idx] = float(outcome["max_adverse_r"])
        numeric_outputs["matb_entry_price"][signal_idx] = float(outcome["entry_price"])
        numeric_outputs["matb_exit_price"][signal_idx] = float(outcome["exit_price"])
        numeric_outputs["matb_transaction_cost_r"][signal_idx] = float(outcome["transaction_cost_r"])
        numeric_outputs["matb_initial_stop_price"][signal_idx] = float(outcome["initial_stop_price"])
        numeric_outputs["matb_emergency_profit_price"][signal_idx] = float(outcome["emergency_profit_price"])
        numeric_outputs[label_col][signal_idx] = float(outcome["net_r"] > 0.0)
        exit_reasons[signal_idx] = str(outcome["exit_reason"])
        execution_sources[signal_idx] = str(outcome["execution_source"])
        entry_timestamps.iloc[signal_idx] = out.index[entry_idx]
        exit_timestamps.iloc[signal_idx] = out.index[exit_idx]

    for column, values in numeric_outputs.items():
        out[column] = values
    if fwd_col != "matb_net_trade_r":
        out[fwd_col] = out["matb_net_trade_r"].astype(float)
    out["matb_event_available"] = event_available
    out["matb_exit_reason"] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out["matb_execution_source"] = pd.Series(execution_sources, index=out.index, dtype="object")
    out["matb_entry_timestamp"] = entry_timestamps
    out["matb_exit_timestamp"] = exit_timestamps

    valid_r = pd.to_numeric(out["matb_net_trade_r"], errors="coerce").dropna()
    output_cols = sorted(
        set(STRATEGY_PATH_R_OUTPUT_COLS)
        | {label_col, fwd_col}
    )
    meta = {
        "kind": "strategy_path_r",
        "label_col": label_col,
        "fwd_col": fwd_col,
        "output_cols": output_cols,
        "candidate_rows": int(candidates.sum()),
        "labeled_rows": int(event_available.sum()),
        "event_available_rows": int(event_available.sum()),
        "positive_rate": float((valid_r > 0.0).mean()) if not valid_r.empty else None,
        "avg_trade_r": float(valid_r.mean()) if not valid_r.empty else None,
        "median_trade_r": float(valid_r.median()) if not valid_r.empty else None,
        "exit_reason_counts": {
            str(key): int(value)
            for key, value in out.loc[out["matb_event_available"].eq(1), "matb_exit_reason"]
            .value_counts(dropna=False)
            .items()
        },
        "invalid_counts": invalid_counts,
        "horizon": int(max_holding_bars),
        "max_holding": int(max_holding_bars),
        "event_start_col": "matb_entry_timestamp",
        "event_end_col": "matb_exit_timestamp",
        "trade_path_policy": {
            "entry_price_mode": entry_price_mode,
            "entry_delay_bars": int(entry_delay_bars),
            "stop_loss_atr": float(stop_loss_atr),
            "emergency_profit_r": float(emergency_profit_r),
            "trailing_activation_r": float(trailing_activation_r),
            "trailing_distance_atr": float(trailing_distance_atr),
            "max_holding_bars": int(max_holding_bars),
            "tie_break": tie_break,
            "strict_bid_ask": bool(strict_bid_ask),
            "enforce_single_position": bool(enforce_single_position),
        },
    }
    return out, label_col, fwd_col, meta


__all__ = ["STRATEGY_PATH_R_OUTPUT_COLS", "build_strategy_path_r_target"]
