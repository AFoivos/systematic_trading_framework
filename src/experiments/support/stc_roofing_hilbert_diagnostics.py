from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


_SIGNAL_COUNT_COLUMNS = {
    "ema_bullish_rows": "stc_roofing_ema_bullish",
    "ema_bearish_rows": "stc_roofing_ema_bearish",
    "roofing_positive_rows": "stc_roofing_roofing_positive",
    "roofing_negative_rows": "stc_roofing_roofing_negative",
    "roofing_slope_positive_rows": "stc_roofing_roofing_slope_positive",
    "roofing_slope_negative_rows": "stc_roofing_roofing_slope_negative",
    "stc_cross_up_rows": "stc_roofing_stc_cross_up",
    "stc_cross_down_rows": "stc_roofing_stc_cross_down",
    "hilbert_pass_rows": "stc_roofing_hilbert_pass",
    "zscore_long_pass_rows": "stc_roofing_zscore_long_pass",
    "zscore_short_pass_rows": "stc_roofing_zscore_short_pass",
    "adx_pass_rows": "stc_roofing_adx_pass",
    "volatility_pass_rows": "stc_roofing_volatility_pass",
    "final_long_candidate_rows": "stc_roofing_long_candidate",
    "final_short_candidate_rows": "stc_roofing_short_candidate",
}


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def _truthy_count(frame: pd.DataFrame, column: str) -> int | None:
    if column not in frame.columns:
        return None
    return int(_numeric(frame[column]).fillna(0.0).ne(0.0).sum())


def _profit_factor(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    if numeric.empty:
        return None
    gains = float(numeric[numeric > 0.0].sum())
    losses = float(numeric[numeric < 0.0].sum())
    if losses == 0.0:
        return float("inf") if gains > 0.0 else None
    return float(gains / abs(losses))


def _hit_rate(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    if numeric.empty:
        return None
    return float((numeric > 0.0).mean())


def _trade_net(trades: pd.DataFrame) -> pd.Series:
    if "net_return" in trades.columns:
        return _numeric(trades["net_return"])
    if "pnl" in trades.columns:
        return _numeric(trades["pnl"])
    return pd.Series(dtype=float)


def _performance_summary(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "trade_count": 0,
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "total_cost": 0.0,
            "profit_factor": None,
            "hit_rate": None,
            "average_r": None,
            "median_r": None,
        }
    gross = _numeric(trades["gross_return"]) if "gross_return" in trades.columns else pd.Series(dtype=float)
    net = _trade_net(trades)
    costs = _numeric(trades["cost"]) if "cost" in trades.columns else pd.Series(dtype=float)
    if costs.empty and "cost_paid" in trades.columns:
        costs = _numeric(trades["cost_paid"])
    r_values = pd.Series(dtype=float)
    for column in ("realized_r", "trade_r"):
        if column in trades.columns:
            r_values = _numeric(trades[column]).dropna()
            break
    return {
        "trade_count": int(len(trades)),
        "gross_pnl": float(gross.sum()) if not gross.empty else 0.0,
        "net_pnl": float(net.sum()) if not net.empty else 0.0,
        "total_cost": float(costs.sum()) if not costs.empty else 0.0,
        "profit_factor": _profit_factor(net),
        "hit_rate": _hit_rate(net),
        "average_r": float(r_values.mean()) if not r_values.empty else None,
        "median_r": float(r_values.median()) if not r_values.empty else None,
    }


def _group_summary(trades: pd.DataFrame, by: pd.Series | str) -> dict[str, dict[str, Any]]:
    if trades.empty:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, group in trades.groupby(by, sort=True, dropna=False):
        if key is None or (isinstance(key, float) and np.isnan(key)):
            label = "missing"
        else:
            label = str(int(key)) if isinstance(key, float) and key.is_integer() else str(key)
        out[label] = _performance_summary(group)
    return out


def _entry_feature_bucket(df: pd.DataFrame, trades: pd.DataFrame, column: str) -> pd.Series:
    if trades.empty or column not in df.columns:
        return pd.Series(dtype="object")
    timestamp_col = next(
        (candidate for candidate in ("entry_timestamp", "entry_time", "entry_ts") if candidate in trades.columns),
        None,
    )
    if timestamp_col is None:
        return pd.Series(dtype="object")

    feature = df[column]
    raw_index = pd.Index(trades[timestamp_col])
    values = feature.reindex(raw_index)
    if values.isna().all():
        parsed_index = pd.to_datetime(trades[timestamp_col], errors="coerce")
        values = feature.reindex(parsed_index)
    return pd.Series(values.to_numpy(), index=trades.index, name=column)


def compute_stc_roofing_hilbert_diagnostics(
    df: pd.DataFrame,
    *,
    performance: Any,
    signal_col: str = "stc_roofing_signal",
    long_candidate_col: str = "stc_roofing_long_candidate",
    short_candidate_col: str = "stc_roofing_short_candidate",
) -> dict[str, Any]:
    if signal_col not in df.columns:
        return {}

    trades = getattr(performance, "trades", None)
    trades = trades.copy() if isinstance(trades, pd.DataFrame) else pd.DataFrame()
    summary = dict(getattr(performance, "summary", {}) or {})
    signal_counts: dict[str, Any] = {
        "total_rows": int(len(df)),
        "final_signal_rows": _truthy_count(df, signal_col),
        "actual_trade_count": int(len(trades)),
    }
    for metric, column in _SIGNAL_COUNT_COLUMNS.items():
        if column == "stc_roofing_long_candidate":
            column = long_candidate_col
        elif column == "stc_roofing_short_candidate":
            column = short_candidate_col
        count = _truthy_count(df, column)
        if count is not None:
            signal_counts[metric] = count

    performance_keys = (
        "cumulative_return",
        "sharpe",
        "sortino",
        "calmar",
        "max_drawdown",
        "profit_factor",
        "hit_rate",
        "average_r",
        "median_r",
        "trade_count",
        "gross_pnl",
        "net_pnl",
        "total_cost",
        "cost_to_gross_pnl",
    )
    performance_diagnostics = {key: summary.get(key) for key in performance_keys if key in summary}
    if trades is not None and not trades.empty:
        for key, value in _performance_summary(trades).items():
            performance_diagnostics.setdefault(key, value)

    years = (
        pd.to_datetime(trades.get("entry_timestamp"), errors="coerce").dt.year
        if not trades.empty and "entry_timestamp" in trades.columns
        else pd.Series(dtype="float64")
    )
    volatility_regime = _entry_feature_bucket(df, trades, "volatility_regime")
    return {
        "signal_counts": signal_counts,
        "performance_diagnostics": performance_diagnostics,
        "side_diagnostics": _group_summary(trades, "side") if "side" in trades.columns else {},
        "performance_by_year": _group_summary(trades, years) if len(years) else {},
        "performance_by_volatility_regime": (
            _group_summary(trades, volatility_regime) if len(volatility_regime) else {}
        ),
    }


__all__ = ["compute_stc_roofing_hilbert_diagnostics"]
