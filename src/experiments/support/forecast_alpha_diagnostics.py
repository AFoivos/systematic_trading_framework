from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.engine import run_backtest
from src.evaluation.metrics import compute_backtest_metrics


_METRIC_KEYS = [
    "cumulative_return",
    "annualized_return",
    "annualized_vol",
    "sharpe",
    "sortino",
    "calmar",
    "max_drawdown",
    "profit_factor",
    "hit_rate",
    "total_turnover",
    "total_cost",
    "cost_to_gross_pnl",
]


@dataclass(frozen=True)
class _BacktestContext:
    returns_col: str
    returns_type: str
    signal_col: str
    pred_is_oos_col: str | None
    periods_per_year: int
    cost_per_turnover: float
    slippage_per_turnover: float
    target_vol: float | None
    vol_col: str | None
    max_leverage: float
    dd_guard: bool
    max_drawdown: float
    cooloff_bars: int
    rearm_drawdown: float | None
    min_holding_bars: int
    missing_return_policy: str


def _context(cfg: dict[str, Any], model_meta: dict[str, Any]) -> _BacktestContext:
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    risk_cfg = dict(cfg.get("risk", {}) or {})
    dd_cfg = dict(risk_cfg.get("dd_guard", {}) or {})
    target_vol = risk_cfg.get("target_vol")
    rearm_drawdown = dd_cfg.get("rearm_drawdown")
    return _BacktestContext(
        returns_col=str(backtest_cfg.get("returns_col", "close_ret")),
        returns_type=str(backtest_cfg.get("returns_type", "simple")),
        signal_col=str(backtest_cfg.get("signal_col", "signal")),
        pred_is_oos_col=str(model_meta.get("pred_is_oos_col") or "pred_is_oos"),
        periods_per_year=int(backtest_cfg.get("periods_per_year", 252) or 252),
        cost_per_turnover=float(risk_cfg.get("cost_per_turnover", 0.0) or 0.0),
        slippage_per_turnover=float(risk_cfg.get("slippage_per_turnover", 0.0) or 0.0),
        target_vol=float(target_vol) if target_vol is not None else None,
        vol_col=(
            str(backtest_cfg.get("vol_col") or risk_cfg.get("vol_col"))
            if backtest_cfg.get("vol_col") or risk_cfg.get("vol_col")
            else None
        ),
        max_leverage=float(risk_cfg.get("max_leverage", 3.0) or 3.0),
        dd_guard=bool(dd_cfg.get("enabled", True)),
        max_drawdown=float(dd_cfg.get("max_drawdown", 0.2) or 0.2),
        cooloff_bars=int(dd_cfg.get("cooloff_bars", 20) or 20),
        rearm_drawdown=float(rearm_drawdown) if rearm_drawdown is not None else None,
        min_holding_bars=int(backtest_cfg.get("min_holding_bars", 0) or 0),
        missing_return_policy=str(backtest_cfg.get("missing_return_policy", "raise_if_exposed")),
    )


def _resolve_vol_col(df: pd.DataFrame, ctx: _BacktestContext) -> str | None:
    if ctx.vol_col:
        return ctx.vol_col
    for candidate in ("vol_rolling_20", "vol_ewma_20", "vol_rolling_60", "vol_ewma_60"):
        if candidate in df.columns:
            return candidate
    return None


def _oos_frame(df: pd.DataFrame, ctx: _BacktestContext) -> pd.DataFrame:
    if ctx.pred_is_oos_col and ctx.pred_is_oos_col in df.columns:
        mask = df[ctx.pred_is_oos_col].fillna(False).astype(bool)
        if bool(mask.any()):
            return df.loc[mask].copy()
    return df.copy()


def _metrics_for_signal(df: pd.DataFrame, signal_col: str, ctx: _BacktestContext) -> dict[str, float]:
    if df.empty:
        return compute_backtest_metrics(
            net_returns=pd.Series(dtype=float),
            periods_per_year=ctx.periods_per_year,
        )
    vol_col = _resolve_vol_col(df, ctx) if ctx.target_vol is not None else None
    result = run_backtest(
        df,
        signal_col=signal_col,
        returns_col=ctx.returns_col,
        returns_type=ctx.returns_type,
        missing_return_policy=ctx.missing_return_policy,
        cost_per_unit_turnover=ctx.cost_per_turnover,
        slippage_per_unit_turnover=ctx.slippage_per_turnover,
        target_vol=ctx.target_vol,
        vol_col=vol_col,
        max_leverage=ctx.max_leverage,
        dd_guard=ctx.dd_guard,
        max_drawdown=ctx.max_drawdown,
        cooloff_bars=ctx.cooloff_bars,
        rearm_drawdown=ctx.rearm_drawdown,
        periods_per_year=ctx.periods_per_year,
        min_holding_bars=ctx.min_holding_bars,
    )
    out = dict(result.summary)
    out["trade_count"] = float((result.turnover > 0).sum())
    out["trade_rate"] = float((result.turnover > 0).mean()) if len(result.turnover) else 0.0
    return out


def _signal_rates(signal: pd.Series) -> dict[str, float]:
    values = signal.fillna(0.0).astype(float)
    if values.empty:
        return {"active_rows": 0.0, "long_rate": 0.0, "short_rate": 0.0, "flat_rate": 0.0}
    return {
        "active_rows": float(values.ne(0.0).sum()),
        "long_rate": float(values.gt(0.0).mean()),
        "short_rate": float(values.lt(0.0).mean()),
        "flat_rate": float(values.eq(0.0).mean()),
    }


def _fold_ranges(model_meta: dict[str, Any]) -> list[dict[str, Any]]:
    folds = list(model_meta.get("folds", []) or [])
    per_asset = dict(model_meta.get("per_asset", {}) or {})
    if not folds and per_asset:
        first = next(iter(per_asset.values()))
        folds = list(dict(first or {}).get("folds", []) or [])
    return [dict(fold or {}) for fold in folds]


def build_fold_backtest_diagnostics(
    df: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    model_meta: dict[str, Any],
) -> dict[str, Any]:
    ctx = _context(cfg, model_meta)
    if ctx.signal_col not in df.columns or ctx.returns_col not in df.columns:
        return {}
    rows: list[dict[str, Any]] = []
    for fold in _fold_ranges(model_meta):
        start = fold.get("test_start")
        end = fold.get("test_end")
        if start is None or end is None:
            continue
        fold_df = df.iloc[int(start) : int(end)].copy()
        if ctx.pred_is_oos_col in fold_df.columns:
            fold_df = fold_df.loc[fold_df[ctx.pred_is_oos_col].fillna(False).astype(bool)]
        if fold_df.empty:
            continue
        metrics = _metrics_for_signal(fold_df, ctx.signal_col, ctx)
        rows.append({"fold": int(fold.get("fold", len(rows))), **metrics})

    returns = pd.Series([float(row.get("cumulative_return", 0.0) or 0.0) for row in rows], dtype=float)
    sharpes = pd.Series([float(row.get("sharpe", 0.0) or 0.0) for row in rows], dtype=float)
    worst3 = float(returns.nsmallest(min(3, len(returns))).mean()) if not returns.empty else 0.0
    summary = {
        "fold_count": float(len(rows)),
        "median_fold_return": float(returns.median()) if not returns.empty else 0.0,
        "mean_fold_return": float(returns.mean()) if not returns.empty else 0.0,
        "fold_return_std": float(returns.std(ddof=1)) if len(returns) > 1 else 0.0,
        "worst_fold_return": float(returns.min()) if not returns.empty else 0.0,
        "best_fold_return": float(returns.max()) if not returns.empty else 0.0,
        "worst_3_fold_average_return": worst3,
        "profitable_fold_count": float(returns.gt(0.0).sum()) if not returns.empty else 0.0,
        "profitable_fold_rate": float(returns.gt(0.0).mean()) if not returns.empty else 0.0,
        "median_fold_sharpe": float(sharpes.median()) if not sharpes.empty else 0.0,
    }
    stability = dict(model_meta.get("feature_importance_stability", {}) or {})
    if stability:
        summary["feature_importance_rank_stability"] = stability
    return {"rows": rows, "summary": summary}


def build_forecast_threshold_grid_diagnostics(
    df: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    model_meta: dict[str, Any],
) -> dict[str, Any]:
    grid_cfg = dict(dict(cfg.get("diagnostics", {}) or {}).get("threshold_grid", {}) or {})
    if not bool(grid_cfg.get("enabled", False)):
        return {}
    forecast_col = str(grid_cfg.get("forecast_col") or dict(cfg.get("signals", {}).get("params", {}) or {}).get("forecast_col") or "pred_ret")
    if forecast_col not in df.columns:
        return {"warnings": [f"forecast_col '{forecast_col}' not found."]}
    thresholds = [float(value) for value in list(grid_cfg.get("symmetric_thresholds", []) or [])]
    pairs = [(value, -value, f"sym_{value:g}") for value in thresholds]
    for idx, raw_pair in enumerate(list(grid_cfg.get("asymmetric_thresholds", []) or [])):
        pair = dict(raw_pair or {})
        pairs.append((float(pair["upper"]), float(pair["lower"]), str(pair.get("name") or f"asym_{idx}")))

    ctx = _context(cfg, model_meta)
    oos = _oos_frame(df, ctx)
    rows: list[dict[str, Any]] = []
    for upper, lower, name in pairs:
        work = oos.copy()
        signal_col = f"threshold_grid_signal_{len(rows)}"
        forecast = work[forecast_col].astype(float)
        work[signal_col] = 0.0
        work.loc[forecast >= upper, signal_col] = 1.0
        work.loc[forecast <= lower, signal_col] = -1.0
        metrics = _metrics_for_signal(work, signal_col, ctx)
        fold_returns: list[float] = []
        for fold in _fold_ranges(model_meta):
            start = fold.get("test_start")
            end = fold.get("test_end")
            if start is None or end is None:
                continue
            fold_df = df.iloc[int(start) : int(end)].copy()
            if ctx.pred_is_oos_col in fold_df.columns:
                fold_df = fold_df.loc[fold_df[ctx.pred_is_oos_col].fillna(False).astype(bool)]
            if fold_df.empty:
                continue
            fold_df[signal_col] = 0.0
            f = fold_df[forecast_col].astype(float)
            fold_df.loc[f >= upper, signal_col] = 1.0
            fold_df.loc[f <= lower, signal_col] = -1.0
            fold_metrics = _metrics_for_signal(fold_df, signal_col, ctx)
            fold_returns.append(float(fold_metrics.get("cumulative_return", 0.0) or 0.0))
        fold_return_series = pd.Series(fold_returns, dtype=float)
        row = {
            "name": name,
            "upper": upper,
            "lower": lower,
            "net_pnl": metrics.get("cumulative_return", 0.0),
            "profitable_fold_count": float(fold_return_series.gt(0.0).sum()) if not fold_return_series.empty else 0.0,
            "median_fold_return": float(fold_return_series.median()) if not fold_return_series.empty else 0.0,
            "worst_3_fold_average_return": (
                float(fold_return_series.nsmallest(min(3, len(fold_return_series))).mean())
                if not fold_return_series.empty
                else 0.0
            ),
            **{key: metrics.get(key, 0.0) for key in _METRIC_KEYS if key in metrics},
            **_signal_rates(work[signal_col]),
        }
        rows.append(row)
    best = max(rows, key=lambda row: float(row.get("sharpe", 0.0) or 0.0), default={})
    return {"rows": rows, "best_by_sharpe": best}


def build_forecast_baseline_diagnostics(
    df: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    model_meta: dict[str, Any],
) -> dict[str, Any]:
    baseline_cfg = dict(dict(cfg.get("diagnostics", {}) or {}).get("baselines", {}) or {})
    if not bool(baseline_cfg.get("enabled", False)):
        return {}
    ctx = _context(cfg, model_meta)
    oos = _oos_frame(df, ctx)
    if oos.empty or ctx.returns_col not in oos.columns:
        return {}

    rng = np.random.default_rng(int(baseline_cfg.get("random_seed", 7) or 7))
    model_signal = oos[ctx.signal_col].fillna(0.0).astype(float) if ctx.signal_col in oos.columns else pd.Series(0.0, index=oos.index)
    active_rate = float(model_signal.ne(0.0).mean()) if len(model_signal) else 0.0
    long_share = float(model_signal.gt(0.0).sum() / max(model_signal.ne(0.0).sum(), 1))

    specs: dict[str, pd.Series] = {"model_strategy": model_signal, "buy_and_hold": pd.Series(1.0, index=oos.index)}
    random_active = rng.random(len(oos)) < active_rate
    random_long = rng.random(len(oos)) < long_share
    random_values = np.where(random_active, np.where(random_long, 1.0, -1.0), 0.0)
    specs["random_sign_same_rate"] = pd.Series(random_values, index=oos.index)

    if {"atr_pct_rank_192", "bollinger_bandwidth_rank_192"}.issubset(oos.columns):
        atr = oos["atr_pct_rank_192"].astype(float)
        bbw = oos["bollinger_bandwidth_rank_192"].astype(float)
        specs["volatility_regime_only"] = pd.Series(
            np.where((atr.between(0.2, 0.85)) & (bbw <= 0.9), 1.0, 0.0),
            index=oos.index,
        )
    if {"ema_trend_48_192", "ret_48"}.issubset(oos.columns):
        trend = oos["ema_trend_48_192"].astype(float) + oos["ret_48"].astype(float)
        specs["simple_trend"] = pd.Series(np.sign(trend).fillna(0.0), index=oos.index)

    rows = []
    for name, signal in specs.items():
        work = oos.copy()
        work["baseline_signal"] = signal.reindex(work.index).fillna(0.0).astype(float)
        rows.append({"name": name, **_metrics_for_signal(work, "baseline_signal", ctx), **_signal_rates(work["baseline_signal"])})
    return {"rows": rows}


def build_regime_performance_diagnostics(
    df: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    model_meta: dict[str, Any],
) -> dict[str, Any]:
    regime_cfg = dict(dict(cfg.get("diagnostics", {}) or {}).get("regime_performance", {}) or {})
    if not bool(regime_cfg.get("enabled", False)):
        return {}
    ctx = _context(cfg, model_meta)
    oos = _oos_frame(df, ctx)
    if oos.empty or ctx.signal_col not in oos.columns:
        return {}
    specs = []
    if "atr_pct_rank_192" in oos.columns:
        specs.extend([
            ("atr_pct_rank_192", "low", oos["atr_pct_rank_192"].astype(float) < 0.2),
            ("atr_pct_rank_192", "medium", oos["atr_pct_rank_192"].astype(float).between(0.2, 0.85)),
            ("atr_pct_rank_192", "high", oos["atr_pct_rank_192"].astype(float) > 0.85),
        ])
    if "bollinger_bandwidth_rank_192" in oos.columns:
        specs.extend([
            ("bollinger_bandwidth_rank_192", "low", oos["bollinger_bandwidth_rank_192"].astype(float) < 0.5),
            ("bollinger_bandwidth_rank_192", "high", oos["bollinger_bandwidth_rank_192"].astype(float) >= 0.5),
        ])
    if "ema_trend_48_192" in oos.columns:
        specs.extend([
            ("ema_trend_48_192", "negative", oos["ema_trend_48_192"].astype(float) < 0.0),
            ("ema_trend_48_192", "positive", oos["ema_trend_48_192"].astype(float) >= 0.0),
        ])
    if "range_to_atr" in oos.columns:
        specs.extend([
            ("range_to_atr", "calm", oos["range_to_atr"].astype(float) <= oos["range_to_atr"].astype(float).median()),
            ("range_to_atr", "shock", oos["range_to_atr"].astype(float) > oos["range_to_atr"].astype(float).median()),
        ])

    rows = []
    for feature, bucket, mask in specs:
        work = oos.loc[mask.fillna(False)].copy()
        if work.empty:
            continue
        rows.append({"feature": feature, "bucket": bucket, "row_count": float(len(work)), **_metrics_for_signal(work, ctx.signal_col, ctx)})
    return {"rows": rows}


__all__ = [
    "build_fold_backtest_diagnostics",
    "build_forecast_baseline_diagnostics",
    "build_forecast_threshold_grid_diagnostics",
    "build_regime_performance_diagnostics",
]
