from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.targets.output_aliases import apply_target_output_aliases
from src.utils.trade_path import simulate_barrier_trade_outcome


PATH_DEPENDENT_R_OUTPUT_COLS = [
    "meta_candidate",
    "meta_side",
    "meta_entry_price",
    "meta_exit_price",
    "meta_exit_reason",
    "meta_hit_type",
    "meta_hit_step",
    "meta_holding_bars",
    "meta_gross_return",
    "meta_net_return",
    "meta_gross_r",
    "meta_net_r",
    "meta_mfe_r",
    "meta_mae_r",
    "meta_label_positive",
    "meta_label_min_0_25r",
    "meta_label_min_0_50r",
    "meta_label_min_1_00r",
]


def _flatten_cfg(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(target_cfg or {})
    params = cfg.pop("params", None)
    if params is not None:
        if not isinstance(params, dict):
            raise ValueError("path_dependent_r target params must be a mapping when provided.")
        cfg.update(dict(params))
    return cfg


def _as_col(value: Any, default: str, *, field: str) -> str:
    resolved = default if value is None else str(value)
    if not resolved.strip():
        raise ValueError(f"path_dependent_r {field} must be a non-empty string.")
    return resolved.strip()


def _finite_positive(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out <= 0.0:
        raise ValueError(f"path_dependent_r {field} must be finite and > 0.")
    return out


def _finite_non_negative(value: Any, *, field: str) -> float:
    out = float(value)
    if not np.isfinite(out) or out < 0.0:
        raise ValueError(f"path_dependent_r {field} must be finite and >= 0.")
    return out


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for path_dependent_r target: {missing}")


def _label_from_threshold(values: np.ndarray, threshold: float) -> np.ndarray:
    labels = np.full(len(values), np.nan, dtype=float)
    valid = np.isfinite(values)
    labels[valid] = (values[valid] >= float(threshold)).astype(float)
    return labels


def _numeric_summary(values: np.ndarray) -> dict[str, Any]:
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
            "positive_rate": None,
        }
    return {
        "rows": int(len(series)),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "q05": float(series.quantile(0.05)),
        "q25": float(series.quantile(0.25)),
        "q75": float(series.quantile(0.75)),
        "q95": float(series.quantile(0.95)),
        "positive_rate": float((series > 0.0).mean()),
    }


def build_path_dependent_r_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build path-dependent R outcomes for precomputed primary candidate rows.

    The default convention is causal and matches ``manual_barrier``: signal at
    bar close ``t``, entry at ``open[t+1]``, then TP/SL/time exit simulation on
    the future path. Non-candidates keep NaN target outcomes and NaN labels.

    YAML declaration::

        target:
          kind: path_dependent_r
          params:
            candidate_col: primary_candidate
            side_col: primary_candidate_side
            pred_is_oos_col: pred_is_oos
            require_oos: true
            open_col: open
            high_col: high
            low_col: low
            close_col: close
            volatility_col: atr_over_price_48
            stop_mode: volatility_stop
            take_profit_r: 5.0
            stop_loss_r: 2.0
            max_holding_bars: 24
            risk_per_trade: 0.006
            cost_per_unit_turnover: 0.0001
            slippage_per_unit_turnover: 0.0
            entry_price_mode: next_open
            tie_break: conservative
          outputs:
            - meta_net_r
            - meta_label_positive
            - meta_label_min_0_25r
            - meta_label_min_0_50r
            - meta_label_min_1_00r

    Required input columns
    ----------------------
    candidate_col:
        Boolean or numeric primary candidate flag.
    side_col:
        Candidate side, where positive is long and negative is short.
    pred_is_oos_col:
        Boolean OOS mask when ``require_oos`` is true.
    open_col, high_col, low_col, close_col:
        Causal OHLC path used for entry and barrier simulation.
    volatility_col:
        Point-in-time volatility or ATR-over-price estimate for volatility stops.

    Parameters
    ----------
    take_profit_r, stop_loss_r:
        Barrier multiples applied to the configured stop distance.
    max_holding_bars:
        Maximum number of bars from entry to time exit.
    cost_per_unit_turnover, slippage_per_unit_turnover:
        Round-trip trading frictions included in ``meta_net_r`` labels.
    entry_price_mode:
        ``next_open`` matches the manual-barrier convention.
    """
    cfg = apply_target_output_aliases(_flatten_cfg(target_cfg))
    candidate_col = _as_col(cfg.get("candidate_col"), "primary_candidate", field="candidate_col")
    side_col = _as_col(cfg.get("side_col"), "primary_candidate_side", field="side_col")
    pred_is_oos_col = _as_col(cfg.get("pred_is_oos_col"), "pred_is_oos", field="pred_is_oos_col")
    require_oos = bool(cfg.get("require_oos", True))

    open_col = _as_col(cfg.get("open_col"), "open", field="open_col")
    high_col = _as_col(cfg.get("high_col"), "high", field="high_col")
    low_col = _as_col(cfg.get("low_col"), "low", field="low_col")
    close_col = _as_col(cfg.get("close_col", cfg.get("price_col")), "close", field="close_col")
    volatility_col = _as_col(cfg.get("volatility_col"), "atr_over_price_48", field="volatility_col")

    meta_candidate_col = _as_col(cfg.get("meta_candidate_col"), "meta_candidate", field="meta_candidate_col")
    meta_side_col = _as_col(cfg.get("meta_side_col"), "meta_side", field="meta_side_col")
    entry_price_col = _as_col(cfg.get("entry_price_col"), "meta_entry_price", field="entry_price_col")
    exit_price_col = _as_col(cfg.get("exit_price_col"), "meta_exit_price", field="exit_price_col")
    exit_reason_col = _as_col(cfg.get("exit_reason_col"), "meta_exit_reason", field="exit_reason_col")
    hit_type_col = _as_col(cfg.get("hit_type_col"), "meta_hit_type", field="hit_type_col")
    hit_step_col = _as_col(cfg.get("hit_step_col"), "meta_hit_step", field="hit_step_col")
    holding_bars_col = _as_col(cfg.get("holding_bars_col"), "meta_holding_bars", field="holding_bars_col")
    gross_return_col = _as_col(cfg.get("gross_return_col"), "meta_gross_return", field="gross_return_col")
    net_return_col = _as_col(cfg.get("net_return_col"), "meta_net_return", field="net_return_col")
    gross_r_col = _as_col(cfg.get("gross_r_col"), "meta_gross_r", field="gross_r_col")
    net_r_col = _as_col(cfg.get("net_r_col"), "meta_net_r", field="net_r_col")
    mfe_r_col = _as_col(cfg.get("mfe_r_col"), "meta_mfe_r", field="mfe_r_col")
    mae_r_col = _as_col(cfg.get("mae_r_col"), "meta_mae_r", field="mae_r_col")
    positive_label_col = _as_col(cfg.get("positive_label_col"), "meta_label_positive", field="positive_label_col")
    min_025_label_col = _as_col(cfg.get("min_025_label_col"), "meta_label_min_0_25r", field="min_025_label_col")
    min_050_label_col = _as_col(cfg.get("min_050_label_col"), "meta_label_min_0_50r", field="min_050_label_col")
    min_100_label_col = _as_col(cfg.get("min_100_label_col"), "meta_label_min_1_00r", field="min_100_label_col")

    stop_mode = str(cfg.get("stop_mode", "volatility_stop"))
    if stop_mode not in {"volatility_stop", "fixed_return"}:
        raise ValueError("path_dependent_r stop_mode must be one of: volatility_stop, fixed_return.")
    entry_price_mode = str(cfg.get("entry_price_mode", "next_open"))
    if entry_price_mode not in {"next_open", "current_close"}:
        raise ValueError("path_dependent_r entry_price_mode must be one of: next_open, current_close.")
    tie_break = str(cfg.get("tie_break", "conservative"))
    if tie_break not in {"conservative", "take_profit", "stop_loss", "closest_to_open"}:
        raise ValueError("path_dependent_r tie_break must be one of: conservative, take_profit, stop_loss, closest_to_open.")

    take_profit_r = _finite_positive(cfg.get("take_profit_r", 5.0), field="take_profit_r")
    stop_loss_r = _finite_positive(cfg.get("stop_loss_r", 2.0), field="stop_loss_r")
    risk_per_trade = _finite_positive(cfg.get("risk_per_trade", 0.006), field="risk_per_trade")
    cost_per_unit_turnover = _finite_non_negative(
        cfg.get("cost_per_unit_turnover", cfg.get("cost_per_turnover", 0.0)),
        field="cost_per_unit_turnover",
    )
    slippage_per_unit_turnover = _finite_non_negative(
        cfg.get("slippage_per_unit_turnover", cfg.get("slippage_per_turnover", 0.0)),
        field="slippage_per_unit_turnover",
    )
    max_leverage = _finite_positive(cfg.get("max_leverage", 1.0), field="max_leverage")
    max_holding_raw = cfg.get("max_holding_bars", cfg.get("max_holding", 24))
    max_holding_bars = None if max_holding_raw is None else int(max_holding_raw)
    if max_holding_bars is not None and max_holding_bars <= 0:
        raise ValueError("path_dependent_r max_holding_bars must be positive or null.")
    allow_partial_horizon = bool(cfg.get("allow_partial_horizon", False))
    apply_risk_sizing = bool(cfg.get("apply_risk_sizing", False))
    legacy_same_bar_stop_reason = bool(cfg.get("legacy_same_bar_stop_reason", True))

    required = [candidate_col, side_col, open_col, high_col, low_col, close_col]
    if require_oos:
        required.append(pred_is_oos_col)
    if stop_mode == "volatility_stop":
        required.append(volatility_col)
    _require_columns(df, required)

    out = df.copy()
    n = len(out)
    opens = pd.to_numeric(out[open_col], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(out[high_col], errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(out[low_col], errors="coerce").to_numpy(dtype=float)
    closes = pd.to_numeric(out[close_col], errors="coerce").to_numpy(dtype=float)
    volatility = (
        pd.to_numeric(out[volatility_col], errors="coerce").to_numpy(dtype=float)
        if stop_mode == "volatility_stop"
        else None
    )
    candidate_input = pd.to_numeric(out[candidate_col], errors="coerce").fillna(0.0).to_numpy(dtype=float) > 0.0
    sides = np.sign(
        pd.to_numeric(out[side_col], errors="coerce").fillna(0.0).clip(lower=-1.0, upper=1.0).to_numpy(dtype=float)
    )
    if require_oos:
        oos_mask = out[pred_is_oos_col].fillna(False).astype(bool).to_numpy(dtype=bool)
        candidate_mask = candidate_input & oos_mask & (sides != 0.0)
    else:
        candidate_mask = candidate_input & (sides != 0.0)

    meta_candidate = candidate_mask.astype("float32")
    meta_side = np.where(candidate_mask, sides, 0.0).astype("float32")
    entry_prices = np.full(n, np.nan, dtype=float)
    exit_prices = np.full(n, np.nan, dtype=float)
    hit_steps = np.full(n, np.nan, dtype=float)
    holding_bars = np.full(n, np.nan, dtype=float)
    gross_returns = np.full(n, np.nan, dtype=float)
    net_returns = np.full(n, np.nan, dtype=float)
    gross_rs = np.full(n, np.nan, dtype=float)
    net_rs = np.full(n, np.nan, dtype=float)
    mfe_rs = np.full(n, np.nan, dtype=float)
    mae_rs = np.full(n, np.nan, dtype=float)
    exit_reasons = np.full(n, None, dtype=object)
    hit_types = np.full(n, None, dtype=object)
    invalid_counts: dict[str, int] = {}

    for signal_idx in np.flatnonzero(candidate_mask):
        outcome = simulate_barrier_trade_outcome(
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            signals=meta_side,
            signal_idx=int(signal_idx),
            side=int(sides[signal_idx]),
            take_profit_r=take_profit_r,
            stop_loss_r=stop_loss_r,
            risk_per_trade=risk_per_trade,
            max_holding_bars=max_holding_bars,
            cost_per_unit_turnover=cost_per_unit_turnover,
            slippage_per_unit_turnover=slippage_per_unit_turnover,
            max_leverage=max_leverage,
            stop_mode=stop_mode,
            volatility=volatility,
            vol_col=volatility_col if stop_mode == "volatility_stop" else None,
            dynamic_exits=None,
            entry_price_mode=entry_price_mode,
            tie_break=tie_break,
            allow_partial_horizon=allow_partial_horizon,
            apply_risk_sizing=apply_risk_sizing,
            signal_size=1.0,
            legacy_same_bar_stop_reason=legacy_same_bar_stop_reason,
        )
        if not bool(outcome["valid"]):
            reason = str(outcome["exit_reason"])
            exit_reasons[signal_idx] = reason
            hit_types[signal_idx] = reason
            invalid_counts[reason] = invalid_counts.get(reason, 0) + 1
            continue

        entry_prices[signal_idx] = float(outcome["entry_price"])
        exit_prices[signal_idx] = float(outcome["exit_price"])
        exit_reasons[signal_idx] = str(outcome["exit_reason"])
        hit_types[signal_idx] = str(outcome["hit_type"])
        hit_steps[signal_idx] = float(outcome["hit_step"])
        holding_bars[signal_idx] = float(outcome["bars_held"])
        gross_returns[signal_idx] = float(outcome["gross_return"])
        net_returns[signal_idx] = float(outcome["net_return"])
        gross_rs[signal_idx] = float(outcome["gross_r"])
        net_rs[signal_idx] = float(outcome["net_r"])
        mfe_rs[signal_idx] = float(outcome["max_favorable_r"])
        mae_rs[signal_idx] = float(outcome["max_adverse_r"])

    label_positive = _label_from_threshold(net_rs, np.nextafter(0.0, 1.0))
    label_025 = _label_from_threshold(net_rs, 0.25)
    label_050 = _label_from_threshold(net_rs, 0.50)
    label_100 = _label_from_threshold(net_rs, 1.00)

    out[meta_candidate_col] = meta_candidate
    out[meta_side_col] = meta_side
    out[entry_price_col] = entry_prices.astype("float64")
    out[exit_price_col] = exit_prices.astype("float64")
    out[exit_reason_col] = pd.Series(exit_reasons, index=out.index, dtype="object")
    out[hit_type_col] = pd.Series(hit_types, index=out.index, dtype="object")
    out[hit_step_col] = hit_steps.astype("float32")
    out[holding_bars_col] = holding_bars.astype("float32")
    out[gross_return_col] = gross_returns.astype("float32")
    out[net_return_col] = net_returns.astype("float32")
    out[gross_r_col] = gross_rs.astype("float32")
    out[net_r_col] = net_rs.astype("float32")
    out[mfe_r_col] = mfe_rs.astype("float32")
    out[mae_r_col] = mae_rs.astype("float32")
    out[positive_label_col] = label_positive.astype("float32")
    out[min_025_label_col] = label_025.astype("float32")
    out[min_050_label_col] = label_050.astype("float32")
    out[min_100_label_col] = label_100.astype("float32")

    valid_outcomes = np.isfinite(net_rs)
    exit_reason_series = pd.Series(exit_reasons, index=out.index, dtype="object")
    label_cols = [positive_label_col, min_025_label_col, min_050_label_col, min_100_label_col]
    label_distribution = {
        col: {
            "rows": int(out[col].notna().sum()),
            "class_counts": {
                str(int(key)): int(value)
                for key, value in out[col].dropna().astype(int).value_counts().sort_index().items()
            },
            "positive_rate": float(out[col].dropna().mean()) if out[col].notna().any() else None,
        }
        for col in label_cols
    }
    output_cols = [
        meta_candidate_col,
        meta_side_col,
        entry_price_col,
        exit_price_col,
        exit_reason_col,
        hit_type_col,
        hit_step_col,
        holding_bars_col,
        gross_return_col,
        net_return_col,
        gross_r_col,
        net_r_col,
        mfe_r_col,
        mae_r_col,
        *label_cols,
    ]
    meta = {
        "kind": "path_dependent_r",
        "candidate_col": candidate_col,
        "side_col": side_col,
        "pred_is_oos_col": pred_is_oos_col if require_oos else None,
        "require_oos": require_oos,
        "candidate_rows": int(candidate_mask.sum()),
        "long_candidate_rows": int(((candidate_mask) & (sides > 0.0)).sum()),
        "short_candidate_rows": int(((candidate_mask) & (sides < 0.0)).sum()),
        "labeled_rows": int(valid_outcomes.sum()),
        "invalid_candidate_rows": int(candidate_mask.sum() - valid_outcomes.sum()),
        "invalid_reason_counts": {str(key): int(value) for key, value in invalid_counts.items()},
        "exit_reason_counts": {
            str(key): int(value)
            for key, value in exit_reason_series.loc[valid_outcomes].value_counts(dropna=True).items()
        },
        "net_r_distribution": _numeric_summary(net_rs),
        "gross_r_distribution": _numeric_summary(gross_rs),
        "mfe_r_distribution": _numeric_summary(mfe_rs),
        "mae_r_distribution": _numeric_summary(mae_rs),
        "label_distribution": label_distribution,
        "positive_rate": label_distribution[positive_label_col]["positive_rate"],
        "take_profit_count": int((exit_reason_series.loc[valid_outcomes] == "take_profit").sum()),
        "stop_loss_count": int(exit_reason_series.loc[valid_outcomes].astype(str).str.contains("stop", regex=False).sum()),
        "max_holding_close_count": int((exit_reason_series.loc[valid_outcomes] == "max_holding_close").sum()),
        "entry_price_mode": entry_price_mode,
        "causal_convention": f"signal close t, entry {'open t+1' if entry_price_mode == 'next_open' else 'close t'}",
        "stop_mode": stop_mode,
        "volatility_col": volatility_col if stop_mode == "volatility_stop" else None,
        "take_profit_r": take_profit_r,
        "stop_loss_r": stop_loss_r,
        "max_holding_bars": max_holding_bars,
        "allow_partial_horizon": allow_partial_horizon,
        "tie_break": tie_break,
        "cost_per_unit_turnover": cost_per_unit_turnover,
        "slippage_per_unit_turnover": slippage_per_unit_turnover,
        "output_cols": sorted(set(output_cols)),
        "label_col": positive_label_col,
        "fwd_col": net_r_col,
        "net_r_col": net_r_col,
        "gross_r_col": gross_r_col,
        "entry_price_col": entry_price_col,
        "exit_price_col": exit_price_col,
        "exit_reason_col": exit_reason_col,
        "hit_type_col": hit_type_col,
        "hit_step_col": hit_step_col,
        "holding_bars_col": holding_bars_col,
    }
    return out, positive_label_col, net_r_col, meta


__all__ = ["PATH_DEPENDENT_R_OUTPUT_COLS", "build_path_dependent_r_target"]
