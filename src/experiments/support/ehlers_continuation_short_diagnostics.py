from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


_SIGNAL_COUNT_COLUMNS = {
    "ema50_lt_ema100_rows": "ehlers_continuation_ema50_lt_ema100",
    "mama_lt_fama_rows": "ehlers_continuation_mama_lt_fama",
    "roofing_lt_zero_rows": "ehlers_continuation_roofing_lt_zero",
    "roofing_slope_lt_zero_rows": "ehlers_continuation_roofing_slope_lt_zero",
    "roofing_lt_slope_rows": "ehlers_continuation_roofing_lt_slope",
    "decycler_osc_lt_zero_rows": "ehlers_continuation_decycler_osc_lt_zero",
    "final_short_state_rows": "ehlers_continuation_short_state",
    "final_short_entry_rows": "ehlers_continuation_short_entry",
}


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def _truthy(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    return _numeric(frame[column]).fillna(0.0).ne(0.0)


def _truthy_count(frame: pd.DataFrame, column: str) -> int:
    return int(_truthy(frame, column).sum())


def _series_sum(value: Any) -> float:
    if value is None:
        return 0.0
    values = pd.to_numeric(pd.Series(value), errors="coerce").dropna().astype(float)
    return float(values.sum()) if not values.empty else 0.0


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


def _trade_cost(trades: pd.DataFrame) -> pd.Series:
    for column in ("cost", "cost_paid"):
        if column in trades.columns:
            return _numeric(trades[column])
    return pd.Series(dtype=float)


def _trade_r(trades: pd.DataFrame) -> pd.Series:
    for column in ("trade_r", "realized_r"):
        if column in trades.columns:
            return _numeric(trades[column]).dropna()
    return pd.Series(dtype=float)


def _trade_summary(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "trade_count": 0,
            "gross_pnl": 0.0,
            "cost": 0.0,
            "total_cost": 0.0,
            "net_pnl": 0.0,
            "profit_factor": None,
            "hit_rate": None,
            "average_r": None,
            "median_r": None,
        }
    gross = _numeric(trades["gross_return"]) if "gross_return" in trades.columns else pd.Series(dtype=float)
    net = _trade_net(trades)
    costs = _trade_cost(trades)
    r_values = _trade_r(trades)
    return {
        "trade_count": int(len(trades)),
        "gross_pnl": float(gross.sum()) if not gross.empty else 0.0,
        "cost": float(costs.sum()) if not costs.empty else 0.0,
        "total_cost": float(costs.sum()) if not costs.empty else 0.0,
        "net_pnl": float(net.sum()) if not net.empty else 0.0,
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
        out[label] = _trade_summary(group)
    return out


def _position_diagnostics(performance: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "mean_position": None,
        "mean_absolute_position": None,
        "max_position": None,
        "non_zero_position_count": 0,
        "total_turnover": 0.0,
    }
    positions = getattr(performance, "positions", None)
    if positions is not None:
        pos = pd.to_numeric(pd.Series(positions), errors="coerce").dropna().astype(float)
        if not pos.empty:
            out.update(
                {
                    "mean_position": float(pos.mean()),
                    "mean_absolute_position": float(pos.abs().mean()),
                    "max_position": float(pos.max()),
                    "non_zero_position_count": int(pos.abs().gt(1e-12).sum()),
                }
            )
    turnover = getattr(performance, "turnover", None)
    if turnover is not None:
        turn = pd.to_numeric(pd.Series(turnover), errors="coerce").dropna().astype(float)
        if not turn.empty:
            out["total_turnover"] = float(turn.sum())
    return out


def _performance_diagnostics(performance: Any, trades: pd.DataFrame) -> dict[str, Any]:
    summary = dict(getattr(performance, "summary", {}) or {})
    trade_summary = _trade_summary(trades)
    gross_pnl = _series_sum(getattr(performance, "gross_returns", None))
    net_pnl = _series_sum(getattr(performance, "returns", None))
    total_cost = _series_sum(getattr(performance, "costs", None))
    out: dict[str, Any] = {
        "gross_pnl": gross_pnl if gross_pnl != 0.0 else summary.get("gross_pnl", trade_summary["gross_pnl"]),
        "net_pnl": net_pnl if net_pnl != 0.0 else summary.get("net_pnl", trade_summary["net_pnl"]),
        "total_cost": total_cost if total_cost != 0.0 else summary.get("total_cost", trade_summary["total_cost"]),
        "cost_to_gross_pnl": summary.get("cost_to_gross_pnl"),
        "profit_factor": summary.get("profit_factor", trade_summary["profit_factor"]),
        "hit_rate": summary.get("hit_rate", trade_summary["hit_rate"]),
        "sharpe": summary.get("sharpe"),
        "max_drawdown": summary.get("max_drawdown"),
        "average_r": summary.get("average_r", trade_summary["average_r"]),
        "median_r": summary.get("median_r", trade_summary["median_r"]),
    }
    if out["cost_to_gross_pnl"] is None and abs(float(out["gross_pnl"] or 0.0)) > 1e-12:
        out["cost_to_gross_pnl"] = float(float(out["total_cost"] or 0.0) / abs(float(out["gross_pnl"])))
    return out


def _yearly_results(trades: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if trades.empty or "entry_timestamp" not in trades.columns:
        return {}
    years = pd.to_datetime(trades["entry_timestamp"], errors="coerce").dt.year
    return _group_summary(trades, years) if len(years) else {}


def _robustness_diagnostics(robustness: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(robustness or {})
    return {
        "cost_stress": dict(payload.get("cost_stress", {}) or {}),
        "entry_delay": dict(payload.get("entry_delay", {}) or {}),
        "walk_forward": dict(payload.get("walk_forward", {}) or {}),
    }


def compute_ehlers_continuation_short_diagnostics(
    df: pd.DataFrame,
    *,
    performance: Any,
    robustness: Mapping[str, Any] | None = None,
    signal_col: str = "ehlers_continuation_signal",
    state_col: str = "ehlers_continuation_short_state",
    entry_col: str = "ehlers_continuation_short_entry",
) -> dict[str, Any]:
    if state_col not in df.columns or entry_col not in df.columns:
        return {}

    trades = getattr(performance, "trades", None)
    trades = trades.copy() if isinstance(trades, pd.DataFrame) else pd.DataFrame()
    signal_counts: dict[str, Any] = {"total_rows": int(len(df))}
    for key, column in _SIGNAL_COUNT_COLUMNS.items():
        if column == "ehlers_continuation_short_state":
            column = state_col
        elif column == "ehlers_continuation_short_entry":
            column = entry_col
        signal_counts[key] = _truthy_count(df, column)
    signal_counts["actual_trade_count"] = int(len(trades))

    ema = _truthy(df, "ehlers_continuation_ema50_lt_ema100")
    mama = _truthy(df, "ehlers_continuation_mama_lt_fama")
    roofing = (
        _truthy(df, "ehlers_continuation_roofing_lt_zero")
        & _truthy(df, "ehlers_continuation_roofing_slope_lt_zero")
        & _truthy(df, "ehlers_continuation_roofing_lt_slope")
    )
    overlap_diagnostics = {
        "ema_only_rows": int(ema.sum()),
        "ema_mama_rows": int((ema & mama).sum()),
        "ema_mama_roofing_rows": int((ema & mama & roofing).sum()),
        "full_signal_rows": _truthy_count(df, state_col),
    }

    position_diagnostics = _position_diagnostics(performance)
    performance_diagnostics = _performance_diagnostics(performance, trades)
    return {
        "signal_counts": signal_counts,
        "overlap_diagnostics": overlap_diagnostics,
        "position_diagnostics": position_diagnostics,
        "performance_diagnostics": performance_diagnostics,
        "position_performance_diagnostics": {**position_diagnostics, **performance_diagnostics},
        "performance_by_year": _yearly_results(trades),
        "robustness_diagnostics": _robustness_diagnostics(robustness),
        "signal_col": signal_col,
    }


__all__ = ["compute_ehlers_continuation_short_diagnostics"]
