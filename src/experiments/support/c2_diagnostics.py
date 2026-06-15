from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


_SIGNAL_COUNT_COLUMNS = {
    "bullish_trend_rows": "c2_bullish_trend",
    "bearish_trend_rows": "c2_bearish_trend",
    "adx_pass_rows": "c2_adx_pass",
    "ppo_long_pass_rows": "c2_ppo_long_pass",
    "ppo_short_pass_rows": "c2_ppo_short_pass",
    "roc_long_pass_rows": "c2_roc_long_pass",
    "roc_short_pass_rows": "c2_roc_short_pass",
    "zscore_long_pass_rows": "c2_zscore_long_pass",
    "zscore_short_pass_rows": "c2_zscore_short_pass",
    "volatility_regime_pass_rows": "c2_volatility_regime_pass",
    "final_long_candidate_rows": "c2_long_candidate",
    "final_short_candidate_rows": "c2_short_candidate",
}


def _as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def _nonzero_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(_as_numeric(frame[column]).fillna(0.0).ne(0.0).sum())


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    values = _as_numeric(frame[column]).dropna()
    return float(values.sum()) if not values.empty else 0.0


def _safe_mean(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    values = _as_numeric(frame[column]).dropna()
    return float(values.mean()) if not values.empty else None


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


def _performance_summary(group: pd.DataFrame) -> dict[str, Any]:
    if group.empty:
        return {
            "trade_count": 0,
            "gross_pnl": 0.0,
            "cost": 0.0,
            "net_pnl": 0.0,
            "profit_factor": None,
            "hit_rate": None,
        }
    net = _as_numeric(group["net_return"]) if "net_return" in group.columns else pd.Series(dtype=float)
    return {
        "trade_count": int(len(group)),
        "gross_pnl": _safe_sum(group, "gross_return"),
        "cost": _safe_sum(group, "cost_paid"),
        "net_pnl": _safe_sum(group, "net_return"),
        "profit_factor": _profit_factor(net),
        "hit_rate": _hit_rate(net),
    }


def _normalize_bucket(value: Any) -> str:
    if value is None or pd.isna(value):
        return "missing"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if np.isfinite(numeric) and numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.6g}"


def _lookup_signal_context(
    trades: pd.DataFrame,
    frame: pd.DataFrame,
    *,
    columns: list[str],
) -> pd.DataFrame:
    out = trades.copy()
    if trades.empty or "signal_timestamp" not in trades.columns:
        return out
    available = [column for column in columns if column in frame.columns]
    if not available:
        return out

    lookup_index = pd.Index(trades["signal_timestamp"])
    try:
        context = frame.reindex(lookup_index)[available]
    except TypeError:
        context = frame.copy()
        context.index = pd.to_datetime(context.index)
        lookup_index = pd.to_datetime(lookup_index)
        context = context.reindex(lookup_index)[available]
    context = context.reset_index(drop=True)
    for column in available:
        out[column] = context[column].to_numpy()
    return out


def _group_trade_performance(
    trades: pd.DataFrame,
    *,
    column: str,
) -> dict[str, dict[str, Any]]:
    if trades.empty or column not in trades.columns:
        return {}
    buckets = trades[column].map(_normalize_bucket)
    out: dict[str, dict[str, Any]] = {}
    for bucket, group in trades.groupby(buckets, sort=True):
        out[str(bucket)] = _performance_summary(group)
    return out


def _year_trade_performance(trades: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if trades.empty or "entry_timestamp" not in trades.columns:
        return {}
    years = pd.to_datetime(trades["entry_timestamp"], errors="coerce").dt.year
    out: dict[str, dict[str, Any]] = {}
    for year, group in trades.groupby(years, sort=True):
        if pd.isna(year):
            continue
        out[str(int(year))] = _performance_summary(group)
    return out


def _signal_counts(frame: pd.DataFrame, *, signal_col: str, trade_count: int) -> dict[str, Any]:
    counts: dict[str, Any] = {"total_rows": int(len(frame))}
    for key, column in _SIGNAL_COUNT_COLUMNS.items():
        counts[key] = _nonzero_count(frame, column)
    counts["final_non_zero_signal_rows"] = _nonzero_count(frame, signal_col)
    counts["actual_trade_count"] = int(trade_count)
    return counts


def _position_diagnostics(performance: Any, *, trade_count: int) -> dict[str, Any]:
    positions = getattr(performance, "positions", None)
    turnover = getattr(performance, "turnover", None)
    summary = dict(getattr(performance, "summary", {}) or {})
    gross_returns = getattr(performance, "gross_returns", None)
    costs = getattr(performance, "costs", None)
    net_returns = getattr(performance, "returns", None)
    out: dict[str, Any] = {}

    if positions is not None:
        pos = pd.to_numeric(pd.Series(positions), errors="coerce").dropna().astype(float)
        if not pos.empty:
            out.update(
                {
                    "mean_position": float(pos.mean()),
                    "mean_absolute_position": float(pos.abs().mean()),
                    "max_position": float(pos.max()),
                    "min_position": float(pos.min()),
                    "non_zero_position_count": int(pos.abs().gt(1e-12).sum()),
                }
            )
    if turnover is not None:
        turn = pd.to_numeric(pd.Series(turnover), errors="coerce").dropna().astype(float)
        if not turn.empty:
            out["total_turnover"] = float(turn.sum())
            out["average_turnover"] = float(turn.mean())

    gross_pnl = float(pd.Series(gross_returns).sum()) if gross_returns is not None else float(summary.get("gross_pnl", 0.0) or 0.0)
    total_cost = float(pd.Series(costs).sum()) if costs is not None else float(summary.get("total_cost", 0.0) or 0.0)
    net_pnl = float(pd.Series(net_returns).sum()) if net_returns is not None else float(summary.get("net_pnl", 0.0) or 0.0)
    denominator = max(int(trade_count), 1)
    out.update(
        {
            "gross_pnl_per_trade": float(gross_pnl / denominator),
            "cost_per_trade": float(total_cost / denominator),
            "net_pnl_per_trade": float(net_pnl / denominator),
            "cost_to_gross_pnl": summary.get("cost_to_gross_pnl"),
        }
    )
    return out


def _side_diagnostics(trades: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {
        "long_trade_count": 0,
        "short_trade_count": 0,
        "long_profit_factor": None,
        "short_profit_factor": None,
        "long_hit_rate": None,
        "short_hit_rate": None,
        "long_net_pnl": 0.0,
        "short_net_pnl": 0.0,
    }
    if trades.empty or "side" not in trades.columns:
        return out
    for side in ("long", "short"):
        group = trades.loc[trades["side"].astype(str).eq(side)]
        summary = _performance_summary(group)
        out[f"{side}_trade_count"] = summary["trade_count"]
        out[f"{side}_profit_factor"] = summary["profit_factor"]
        out[f"{side}_hit_rate"] = summary["hit_rate"]
        out[f"{side}_net_pnl"] = summary["net_pnl"]
    return out


def compute_c2_regime_aware_momentum_diagnostics(
    frame: pd.DataFrame,
    *,
    performance: Any,
    signal_col: str = "c2_signal",
    trend_regime_col: str = "trend_regime",
    volatility_regime_col: str = "volatility_regime",
) -> dict[str, Any]:
    if "c2_long_candidate" not in frame.columns and "c2_short_candidate" not in frame.columns:
        return {}

    trades = getattr(performance, "trades", None)
    if trades is None:
        trades = pd.DataFrame()
    else:
        trades = trades.copy()
    trade_count = int(len(trades))
    trades_with_context = _lookup_signal_context(
        trades,
        frame,
        columns=[trend_regime_col, volatility_regime_col],
    )

    return {
        "signal_counts": _signal_counts(frame, signal_col=signal_col, trade_count=trade_count),
        "position_diagnostics": _position_diagnostics(performance, trade_count=trade_count),
        "side_diagnostics": _side_diagnostics(trades),
        "regime_diagnostics": {
            "performance_by_trend_regime": _group_trade_performance(
                trades_with_context,
                column=trend_regime_col,
            ),
            "performance_by_volatility_regime": _group_trade_performance(
                trades_with_context,
                column=volatility_regime_col,
            ),
            "performance_by_year": _year_trade_performance(trades_with_context),
        },
    }


__all__ = ["compute_c2_regime_aware_momentum_diagnostics"]
