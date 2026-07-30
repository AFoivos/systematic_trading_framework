from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


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
            "net_pnl": 0.0,
            "entry_cost": 0.0,
            "exit_cost": 0.0,
            "holding_cost": 0.0,
            "total_cost": 0.0,
            "profit_factor": None,
            "hit_rate": None,
            "average_r": None,
            "median_r": None,
        }
    gross = _numeric(group["gross_return"]) if "gross_return" in group.columns else pd.Series(dtype=float)
    net = _numeric(group["net_return"]) if "net_return" in group.columns else pd.Series(dtype=float)
    costs = pd.Series(dtype=float)
    for cost_col in ("cost_return", "total_cost", "cost_paid", "cost"):
        if cost_col in group.columns:
            costs = _numeric(group[cost_col]).fillna(0.0)
            break
    entry_cost = _numeric(group["entry_cost"]).fillna(0.0) if "entry_cost" in group.columns else pd.Series(0.0, index=group.index)
    exit_cost = _numeric(group["exit_cost"]).fillna(0.0) if "exit_cost" in group.columns else pd.Series(0.0, index=group.index)
    holding_cost = _numeric(group["holding_cost"]).fillna(0.0) if "holding_cost" in group.columns else pd.Series(0.0, index=group.index)
    gross_total = float(gross.sum()) if not gross.empty else 0.0
    net_total = float(net.sum()) if not net.empty else 0.0
    cost_total = float(costs.sum()) if not costs.empty else 0.0
    component_total = float(entry_cost.sum() + exit_cost.sum() + holding_cost.sum())
    if any(column in group.columns for column in ("entry_cost", "exit_cost", "holding_cost")) and not np.isclose(
        component_total,
        cost_total,
        rtol=1e-10,
        atol=1e-12,
    ):
        raise ValueError(
            "Completed-trade breakdown accounting mismatch: cost components != total_cost."
        )
    if gross.notna().any() and net.notna().any() and not np.isclose(
        gross_total - cost_total,
        net_total,
        rtol=1e-10,
        atol=1e-12,
    ):
        raise ValueError(
            "Completed-trade breakdown accounting mismatch: gross_pnl - total_cost != net_pnl."
        )
    r_values = pd.Series(dtype=float)
    for col in ("realized_r", "trade_r"):
        if col in group.columns:
            r_values = _numeric(group[col]).dropna()
            break
    return {
        "trade_count": int(len(group)),
        "gross_pnl": gross_total,
        "net_pnl": net_total,
        "entry_cost": float(entry_cost.sum()),
        "exit_cost": float(exit_cost.sum()),
        "holding_cost": float(holding_cost.sum()),
        "cost": cost_total,
        "total_cost": cost_total,
        "pnl_unit": "fractional_return",
        "profit_factor": _profit_factor(net),
        "hit_rate": _hit_rate(net),
        "average_r": float(r_values.mean()) if not r_values.empty else None,
        "median_r": float(r_values.median()) if not r_values.empty else None,
    }


def _group_summary(trades: pd.DataFrame, by: pd.Series | str) -> dict[str, dict[str, Any]]:
    if trades.empty:
        return {}
    out: dict[str, dict[str, Any]] = {}
    grouped = trades.groupby(by, sort=True, dropna=False)
    for key, group in grouped:
        if key is None or (isinstance(key, float) and np.isnan(key)):
            label = "missing"
        else:
            label = str(int(key)) if isinstance(key, float) and key.is_integer() else str(key)
        out[label] = _performance_summary(group)
    return out


def _attach_signal_context(
    trades: pd.DataFrame,
    asset_frames: dict[str, pd.DataFrame],
    *,
    columns: tuple[str, ...],
) -> pd.DataFrame:
    if trades.empty or "asset" not in trades.columns or "signal_timestamp" not in trades.columns:
        return trades.copy()
    out = trades.copy()
    for column in columns:
        out[column] = pd.NA
    for asset, group_idx in out.groupby(out["asset"].astype(str)).groups.items():
        frame = asset_frames.get(str(asset))
        if frame is None:
            continue
        available = [column for column in columns if column in frame.columns]
        if not available:
            continue
        timestamps = pd.Index(out.loc[group_idx, "signal_timestamp"])
        try:
            context = frame.reindex(timestamps)[available]
        except TypeError:
            context_frame = frame.copy()
            context_frame.index = pd.to_datetime(context_frame.index)
            context = context_frame.reindex(pd.to_datetime(timestamps))[available]
        for column in available:
            out.loc[group_idx, column] = context[column].to_numpy()
    return out


def _atr_volatility_bucket(trades: pd.DataFrame) -> pd.Series:
    if trades.empty or "atr_at_signal" not in trades.columns:
        return pd.Series(dtype="object")
    atr = pd.to_numeric(trades["atr_at_signal"], errors="coerce")
    valid = atr.dropna()
    if valid.empty or valid.nunique() < 3:
        return pd.Series("missing", index=trades.index, dtype="object")
    try:
        bucket = pd.qcut(atr, q=3, labels=["low", "medium", "high"], duplicates="drop")
    except ValueError:
        return pd.Series("missing", index=trades.index, dtype="object")
    return bucket.astype("object").where(bucket.notna(), other="missing")


def compute_baseline_vwap_rms_ema_ppo_mfi_atr_diagnostics(
    asset_frames: dict[str, pd.DataFrame],
    *,
    performance: Any,
    signal_col: str = "signal_side",
    volatility_regime_col: str = "volatility_regime",
) -> dict[str, Any]:
    """
    Summarize trade attribution for the formal VWAP/RMS/EMA/PPO/MFI/ATR baseline.

    The helper is intentionally read-only: it only consumes emitted signal columns and completed
    trade records from the backtest engine.
    """
    if not any(signal_col in frame.columns for frame in asset_frames.values()):
        return {}

    trades = getattr(performance, "trades", None)
    trades = trades.copy() if isinstance(trades, pd.DataFrame) else pd.DataFrame()
    primary: dict[str, Any] = {
        "trade_count": int(len(trades)),
        "gross_pnl": float(getattr(performance, "summary", {}).get("gross_pnl", 0.0) or 0.0),
        "net_pnl": float(getattr(performance, "summary", {}).get("net_pnl", 0.0) or 0.0),
        "total_cost": float(getattr(performance, "summary", {}).get("total_cost", 0.0) or 0.0),
        "cost_to_gross_pnl": getattr(performance, "summary", {}).get("cost_to_gross_pnl"),
    }
    if trades.empty:
        return {
            "primary": primary,
            "trade_count_by_asset": {},
            "performance_by_asset": {},
            "performance_by_side": {},
            "performance_by_year": {},
            "performance_by_volatility_regime": {},
        }

    trades_with_context = _attach_signal_context(
        trades,
        asset_frames,
        columns=(volatility_regime_col,),
    )
    if volatility_regime_col not in trades_with_context.columns or trades_with_context[volatility_regime_col].isna().all():
        trades_with_context["atr_volatility_bucket"] = _atr_volatility_bucket(trades_with_context)
        volatility_group_col = "atr_volatility_bucket"
    else:
        volatility_group_col = volatility_regime_col

    years = pd.to_datetime(trades_with_context.get("entry_timestamp"), errors="coerce").dt.year
    return {
        "primary": primary,
        "trade_count_by_asset": {
            str(asset): int(count)
            for asset, count in trades_with_context["asset"].astype(str).value_counts().sort_index().items()
        }
        if "asset" in trades_with_context.columns
        else {},
        "performance_by_asset": _group_summary(trades_with_context, "asset")
        if "asset" in trades_with_context.columns
        else {},
        "performance_by_side": _group_summary(trades_with_context, "side")
        if "side" in trades_with_context.columns
        else {},
        "performance_by_year": _group_summary(trades_with_context, years),
        "performance_by_volatility_regime": _group_summary(trades_with_context, volatility_group_col)
        if volatility_group_col in trades_with_context.columns
        else {},
    }


__all__ = ["compute_baseline_vwap_rms_ema_ppo_mfi_atr_diagnostics"]
