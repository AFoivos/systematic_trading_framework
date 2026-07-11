from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_ethusd_meta_model_comparison import _build_candidate_target_frame
from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.evaluation.metrics import (
    annualized_return,
    calmar_ratio,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
)
from src.evaluation.trade_path_diagnostics import build_trade_paths
from src.meta.stacked_trade_filter import (
    DEFAULT_META_FEATURE_COLS,
    build_meta_filtered_signal,
    train_stacked_meta_filter,
)


BASE_CONFIG = (
    ROOT
    / "config"
    / "experiments"
    / "foundation_alpha"
    / "BEST"
    / "ethusd"
    / "BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier.yaml"
)
META_CONFIG = (
    ROOT
    / "config"
    / "experiments"
    / "foundation_alpha"
    / "BEST"
    / "ethusd"
    / "meta_filter"
    / "ethusd_meta_lightgbm_filter.yaml"
)
PROCESSED_DATASET = (
    ROOT
    / "data"
    / "processed"
    / "processed"
    / "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_e7881346_trial_0149"
    / "dataset.csv"
)
PREDICTION_CSV = (
    ROOT
    / "logs"
    / "experiments"
    / "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier_trial_0149_20260710_040612_104038_08aefadd"
    / "artifacts"
    / "diagnostics"
    / "prediction_distribution.csv"
)
SAVED_TRADE_PATHS = (
    ROOT
    / "logs"
    / "experiments"
    / "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier_trial_0149_20260710_040612_104038_08aefadd"
    / "report_assets"
    / "trade_paths.parquet"
)
REPORT_PATH = ROOT / "reports" / "ethusd_exit_policy_comparison.md"

LOCKED_META_MODEL_NAME = "logistic_meta_filter"
LOCKED_META_MODEL_KIND = "logistic_regression_clf"
LOCKED_META_SCALER = "robust"
LOCKED_META_CALIBRATION = "none"
LOCKED_META_THRESHOLD = 0.75
LOCKED_META_LABEL = "meta_label_min_0_50r"

FIXED_STOP_GRID = [1.0, 1.5, 2.0, 2.5]
FIXED_TP_GRID = [2.0, 3.0, 4.0, 5.0]
FIXED_HOLD_GRID = [8, 12, 16, 24]
LONG_EXIT_GRID = [0.00, 0.10, 0.20, 0.30]
SHORT_EXIT_GRID = [0.00, -0.10, -0.20, -0.30]
PARTIAL_RULES = [
    ("partial_50pct_at_1_5r", 1.5),
    ("partial_50pct_at_2_0r", 2.0),
]
TREND_BREAK_INDICATORS = [
    "mama_minus_fama_over_atr",
    "roofing_filter_over_atr",
    "decycler_slope_over_atr",
    "instantaneous_trendline_slope_over_atr",
    "frama_slope_over_atr",
]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping at {path}.")
    return payload


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isnan(number):
            return ""
        if math.isinf(number):
            return str(number)
        if number == 0.0:
            return "0.0"
        if abs(number) >= 1000 or abs(number) < 1e-4:
            return f"{number:.6e}"
        return f"{number:.6f}"
    return str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_None_\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(value) for value in row) + " |")
    return "\n".join(lines) + "\n"


def _policy_slug(name: str) -> str:
    return (
        str(name)
        .lower()
        .replace(" ", "_")
        .replace("+", "plus")
        .replace("/", "_")
        .replace(".", "_")
        .replace("-", "_")
    )


def _scope_validation(frame: pd.DataFrame, *, max_holding_bars: int) -> pd.Series:
    folds = pd.to_numeric(frame["walk_forward_fold"], errors="coerce")
    final_fold = float(folds.dropna().max())
    first_test_pos = int(np.flatnonzero(folds.eq(final_fold).to_numpy(dtype=bool))[0])
    positions = np.arange(len(frame))
    return folds.notna() & folds.lt(final_fold) & ((positions + int(max_holding_bars)) < first_test_pos)


def _scope_test(frame: pd.DataFrame) -> pd.Series:
    folds = pd.to_numeric(frame["walk_forward_fold"], errors="coerce")
    return folds.eq(float(folds.dropna().max()))


def _dynamic_forecast_exit(long_exit: float, short_exit: float) -> dict[str, Any]:
    return {
        "enabled": True,
        "forecast_decay": {
            "enabled": True,
            "long_hold_threshold": 0.70,
            "long_exit_threshold": float(long_exit),
            "short_hold_threshold": -0.85,
            "short_exit_threshold": float(short_exit),
            "exit_price": "next_open",
            "min_bars_held": 1,
        },
    }


def _dynamic_trend_break(long_weakening: float, short_weakening: float) -> dict[str, Any]:
    return {
        "enabled": True,
        "trend_break": {
            "enabled": True,
            "long_weakening_level": float(long_weakening),
            "short_weakening_level": float(short_weakening),
            "exit_price": "next_open",
            "min_bars_held": 1,
            "min_disagreeing_indicators": 2,
            "indicator_cols": TREND_BREAK_INDICATORS,
        },
    }


def _partial_exit(trigger_r: float) -> dict[str, Any]:
    return {"enabled": True, "rules": [{"trigger_r": float(trigger_r), "fraction": 0.5}]}


def _run_policy(
    frame: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    signal: pd.Series,
    scope_mask: pd.Series | None,
    take_profit_r: float,
    stop_loss_r: float,
    max_holding_bars: int,
    dynamic_exits: dict[str, Any] | None = None,
    partial_exits: dict[str, Any] | None = None,
):
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    risk_cfg = dict(cfg.get("risk", {}) or {})
    run_frame = frame.copy()
    scoped_signal = signal.reindex(run_frame.index).fillna(0.0).astype(float)
    if scope_mask is not None:
        scoped_signal = scoped_signal.where(scope_mask.reindex(run_frame.index).fillna(False), 0.0)
    run_frame["__exit_policy_signal"] = scoped_signal
    needs_forecast = bool(dynamic_exits and dynamic_exits.get("enabled"))
    return run_manual_barrier_backtest(
        run_frame,
        signal_col="__exit_policy_signal",
        open_col=str(backtest_cfg.get("open_col", "open")),
        high_col=str(backtest_cfg.get("high_col", "high")),
        low_col=str(backtest_cfg.get("low_col", "low")),
        close_col=str(backtest_cfg.get("close_col", "close")),
        take_profit_r=float(take_profit_r),
        stop_loss_r=float(stop_loss_r),
        risk_per_trade=float(backtest_cfg.get("risk_per_trade", 0.006)),
        max_holding_bars=int(max_holding_bars),
        cost_per_unit_turnover=float(risk_cfg.get("cost_per_turnover", 0.0)),
        slippage_per_unit_turnover=float(risk_cfg.get("slippage_per_turnover", 0.0)),
        max_leverage=float(risk_cfg.get("max_leverage", 1.0)),
        periods_per_year=int(backtest_cfg.get("periods_per_year", 17520)),
        dynamic_exits=dynamic_exits,
        partial_exits=partial_exits,
        allow_short=bool(backtest_cfg.get("allow_short", True)),
        stop_mode=str(backtest_cfg.get("stop_mode", "volatility_stop")),
        vol_col=str(backtest_cfg.get("vol_col", "atr_over_price_48")),
        forecast_col="pred_ret" if needs_forecast else None,
    )


def _metrics(result: Any, *, periods_per_year: int) -> dict[str, Any]:
    returns = result.returns.astype(float)
    equity = result.equity_curve.astype(float)
    trades = result.trades.copy() if result.trades is not None else pd.DataFrame()
    trade_r = pd.to_numeric(trades.get("trade_r", pd.Series(dtype=float)), errors="coerce")
    mfe = pd.to_numeric(trades.get("max_favorable_r", pd.Series(dtype=float)), errors="coerce")
    giveback = mfe - trade_r
    positive_mfe = mfe.where(mfe.gt(0.0))
    realized_positive = trade_r.clip(lower=0.0)
    gross_sum = float(result.gross_returns.sum()) if result.gross_returns is not None else 0.0
    cost_sum = float(result.costs.sum()) if result.costs is not None else 0.0
    return {
        "cumulative_return": float(equity.iloc[-1] - 1.0) if len(equity) else 0.0,
        "annualized_return": annualized_return(returns, periods_per_year=periods_per_year),
        "sharpe": sharpe_ratio(returns, periods_per_year=periods_per_year),
        "sortino": sortino_ratio(returns, periods_per_year=periods_per_year),
        "calmar": calmar_ratio(returns, periods_per_year=periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "profit_factor": profit_factor(returns),
        "trade_count": int(len(trades)),
        "average_net_r": float(trade_r.mean()) if trade_r.notna().any() else None,
        "median_net_r": float(trade_r.median()) if trade_r.notna().any() else None,
        "r_skew": float(trade_r.skew()) if trade_r.notna().sum() >= 3 else None,
        "tail_loss": float(trade_r.quantile(0.05)) if trade_r.notna().any() else None,
        "average_holding": float(pd.to_numeric(trades.get("bars_held", pd.Series(dtype=float)), errors="coerce").mean())
        if not trades.empty
        else None,
        "turnover": float(result.turnover.sum()) if result.turnover is not None else 0.0,
        "costs": cost_sum,
        "cost_to_gross_pnl": float(cost_sum / abs(gross_sum)) if abs(gross_sum) > 1e-12 else None,
        "profit_giveback": float(giveback.mean()) if giveback.notna().any() else None,
        "mfe_capture_ratio": (
            float(realized_positive.sum() / positive_mfe.sum())
            if positive_mfe.notna().any() and float(positive_mfe.sum()) > 1e-12
            else None
        ),
    }


def _metrics_row(name: str, metrics: dict[str, Any]) -> list[Any]:
    return [
        name,
        metrics.get("cumulative_return"),
        metrics.get("annualized_return"),
        metrics.get("sharpe"),
        metrics.get("sortino"),
        metrics.get("calmar"),
        metrics.get("max_drawdown"),
        metrics.get("profit_factor"),
        metrics.get("trade_count"),
        metrics.get("average_net_r"),
        metrics.get("median_net_r"),
        metrics.get("r_skew"),
        metrics.get("tail_loss"),
        metrics.get("average_holding"),
        metrics.get("turnover"),
        metrics.get("costs"),
        metrics.get("profit_giveback"),
        metrics.get("mfe_capture_ratio"),
    ]


def _attach_context(frame: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame() if trades is None else trades.copy()
    context_cols = [
        "year",
        "quarter",
        "walk_forward_fold",
        "volatility_regime",
        "pred_ret",
        "meta_pred_prob",
    ]
    context = frame[[col for col in context_cols if col in frame.columns]].copy()
    out = trades.merge(context, left_on="signal_timestamp", right_index=True, how="left")
    out["side_bucket"] = out["side"].astype(str)
    if "meta_pred_prob" in out.columns:
        out["meta_probability_bucket"] = "missing"
        valid = pd.to_numeric(out["meta_pred_prob"], errors="coerce").notna()
        if valid.any():
            out.loc[valid, "meta_probability_bucket"] = pd.qcut(
                pd.to_numeric(out.loc[valid, "meta_pred_prob"], errors="coerce").rank(method="first"),
                q=min(4, int(valid.sum())),
                labels=["q1_low", "q2", "q3", "q4_high"][: min(4, int(valid.sum()))],
                duplicates="drop",
            ).astype(str)
    return out


def _trade_path_analysis(frame: pd.DataFrame, trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades is None or trades.empty:
        return pd.DataFrame(), pd.DataFrame()
    trade_paths, _ = build_trade_paths({"ETHUSD": frame.sort_index()}, trades)
    if trade_paths.empty:
        out = trades.copy()
        out["bar_of_mfe"] = np.nan
        out["bar_of_mae"] = np.nan
        out["r_at_time_exit"] = pd.to_numeric(out.get("trade_r"), errors="coerce")
        out["profit_giveback"] = pd.to_numeric(out.get("max_favorable_r"), errors="coerce") - out["r_at_time_exit"]
        return out, trade_paths
    rows: list[dict[str, Any]] = []
    for trade_id, path in trade_paths.groupby("trade_id", sort=True):
        high_r = pd.to_numeric(path["high_r"], errors="coerce")
        low_r = pd.to_numeric(path["low_r"], errors="coerce")
        close_r = pd.to_numeric(path["close_r"], errors="coerce")
        rows.append(
            {
                "trade_id": trade_id,
                "bar_of_mfe": int(path.loc[high_r.idxmax(), "bar_in_trade"]) if high_r.notna().any() else np.nan,
                "bar_of_mae": int(path.loc[low_r.idxmin(), "bar_in_trade"]) if low_r.notna().any() else np.nan,
                "r_at_time_exit": float(close_r.dropna().iloc[-1]) if close_r.notna().any() else np.nan,
            }
        )
    path_stats = pd.DataFrame(rows)
    enriched = trades.reset_index(drop=True).copy()
    enriched["trade_id"] = enriched.index
    enriched = enriched.merge(path_stats, on="trade_id", how="left")
    enriched["profit_giveback"] = (
        pd.to_numeric(enriched["max_favorable_r"], errors="coerce")
        - pd.to_numeric(enriched["trade_r"], errors="coerce")
    )
    return enriched, trade_paths


def _distribution_rows(trades: pd.DataFrame, by: str | None = None) -> list[list[Any]]:
    if trades is None or trades.empty:
        return []
    grouped = [("all", trades)] if by is None else list(trades.groupby(by, dropna=False))
    rows: list[list[Any]] = []
    for key, group in grouped:
        trade_r = pd.to_numeric(group["trade_r"], errors="coerce")
        mfe = pd.to_numeric(group["max_favorable_r"], errors="coerce")
        mae = pd.to_numeric(group["max_adverse_r"], errors="coerce")
        giveback = pd.to_numeric(group["profit_giveback"], errors="coerce")
        bar_mfe = pd.to_numeric(group.get("bar_of_mfe", pd.Series(dtype=float)), errors="coerce")
        bar_mae = pd.to_numeric(group.get("bar_of_mae", pd.Series(dtype=float)), errors="coerce")
        rows.append(
            [
                key,
                int(len(group)),
                float(trade_r.mean()) if trade_r.notna().any() else None,
                float(trade_r.median()) if trade_r.notna().any() else None,
                float(trade_r.quantile(0.05)) if trade_r.notna().any() else None,
                float(mfe.mean()) if mfe.notna().any() else None,
                float(mfe.median()) if mfe.notna().any() else None,
                float(mae.mean()) if mae.notna().any() else None,
                float(mae.median()) if mae.notna().any() else None,
                float(bar_mfe.median()) if bar_mfe.notna().any() else None,
                float(bar_mae.median()) if bar_mae.notna().any() else None,
                float(giveback.mean()) if giveback.notna().any() else None,
                float(pd.to_numeric(group["bars_held"], errors="coerce").mean()) if "bars_held" in group else None,
            ]
        )
    return rows


def _breakdown_rows(trades: pd.DataFrame, by: str) -> list[list[Any]]:
    if trades is None or trades.empty or by not in trades.columns:
        return []
    rows: list[list[Any]] = []
    for key, group in trades.groupby(by, dropna=False):
        trade_r = pd.to_numeric(group["trade_r"], errors="coerce")
        mfe = pd.to_numeric(group["max_favorable_r"], errors="coerce")
        giveback = pd.to_numeric(group.get("profit_giveback", pd.Series(dtype=float)), errors="coerce")
        gains = float(trade_r[trade_r > 0.0].sum())
        losses = float(-trade_r[trade_r < 0.0].sum())
        rows.append(
            [
                key,
                int(len(group)),
                float(trade_r.mean()) if trade_r.notna().any() else None,
                float(trade_r.median()) if trade_r.notna().any() else None,
                float((trade_r > 0.0).mean()) if trade_r.notna().any() else None,
                float(gains / losses) if losses > 1e-12 else None,
                float(giveback.mean()) if giveback.notna().any() else None,
                float(trade_r.clip(lower=0.0).sum() / mfe.where(mfe.gt(0.0)).sum())
                if mfe.where(mfe.gt(0.0)).sum() > 1e-12
                else None,
            ]
        )
    return rows


def _grid_neighbors(
    rows: pd.DataFrame,
    *,
    columns: list[str],
    values_by_col: dict[str, list[float]],
) -> pd.DataFrame:
    out = rows.copy()
    index_by_col = {col: {float(value): idx for idx, value in enumerate(values)} for col, values in values_by_col.items()}
    neighbor_counts: list[int] = []
    neighbor_medians: list[float] = []
    for _, row in rows.iterrows():
        masks = []
        for col in columns:
            row_idx = index_by_col[col][float(row[col])]
            masks.append(rows[col].map(lambda value, c=col, i=row_idx: abs(index_by_col[c][float(value)] - i) <= 1))
        mask = masks[0]
        for current in masks[1:]:
            mask = mask & current
        neighbors = pd.to_numeric(rows.loc[mask, "calmar"], errors="coerce").dropna()
        neighbor_counts.append(int(len(neighbors)))
        neighbor_medians.append(float(neighbors.median()) if len(neighbors) else float("-inf"))
    out["neighbor_count"] = neighbor_counts
    out["neighbor_median_calmar"] = neighbor_medians
    return out


def _select_stable_grid_row(
    rows: pd.DataFrame,
    *,
    param_cols: list[str],
    values_by_col: dict[str, list[float]],
) -> dict[str, Any]:
    scored = _grid_neighbors(rows, columns=param_cols, values_by_col=values_by_col)
    valid = scored.loc[pd.to_numeric(scored["trade_count"], errors="coerce").ge(5)].copy()
    if valid.empty:
        valid = scored.copy()
    best_calmar = float(pd.to_numeric(valid["calmar"], errors="coerce").max())
    plateau = valid.loc[pd.to_numeric(valid["calmar"], errors="coerce").ge(best_calmar * 0.85)].copy()
    if plateau.empty:
        plateau = valid.sort_values("calmar", ascending=False).head(1)
    plateau = plateau.sort_values(
        ["neighbor_median_calmar", "calmar", "profit_factor", "average_net_r", "trade_count"],
        ascending=[False, False, False, False, False],
    )
    selected = plateau.iloc[0].to_dict()
    selected["selection_reason"] = "validation plateau with strongest neighboring Calmar median"
    selected["best_validation_calmar"] = best_calmar
    return selected


def _policy_record(
    name: str,
    *,
    family: str,
    params: dict[str, Any],
    validation_metrics: dict[str, Any],
    validation_result: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "family": family,
        "params": params,
        "validation_metrics": validation_metrics,
        "validation_result": validation_result,
        "test_metrics": None,
        "test_result": None,
    }


def _positive_fold_count(trades: pd.DataFrame) -> int:
    if trades is None or trades.empty or "walk_forward_fold" not in trades.columns:
        return 0
    count = 0
    for _, group in trades.groupby("walk_forward_fold", dropna=True):
        if pd.to_numeric(group["trade_r"], errors="coerce").mean() > 0.0:
            count += 1
    return count


def _select_final_policy(records: list[dict[str, Any]], *, baseline: dict[str, Any], frame: pd.DataFrame) -> tuple[dict[str, Any], str]:
    baseline_metrics = baseline["validation_metrics"]
    baseline_trades = _attach_context(frame, baseline["validation_result"].trades.copy())
    baseline_positive_folds = _positive_fold_count(baseline_trades)
    candidates: list[tuple[float, dict[str, Any]]] = []
    warnings: list[str] = []
    for record in records:
        metrics = record["validation_metrics"]
        trades = _attach_context(frame, record["validation_result"].trades.copy())
        positive_folds = _positive_fold_count(trades)
        turnover_ok = float(metrics.get("turnover") or 0.0) <= 1.50 * max(float(baseline_metrics.get("turnover") or 0.0), 1e-12)
        expectancy_ok = float(metrics.get("average_net_r") or -999.0) >= 0.80 * float(baseline_metrics.get("average_net_r") or 0.0)
        stability_ok = positive_folds >= max(1, min(baseline_positive_folds, 2))
        calmar_ok = float(metrics.get("calmar") or -999.0) >= float(baseline_metrics.get("calmar") or -999.0)
        if record["name"] != baseline["name"] and not (turnover_ok and expectancy_ok and stability_ok and calmar_ok):
            warnings.append(
                f"{record['name']} rejected by validation stability gate "
                f"(turnover_ok={turnover_ok}, expectancy_ok={expectancy_ok}, "
                f"stability_ok={stability_ok}, calmar_ok={calmar_ok})."
            )
            continue
        score = (
            float(metrics.get("calmar") or 0.0)
            + 0.25 * float(metrics.get("profit_factor") or 0.0)
            + 0.10 * float(metrics.get("average_net_r") or 0.0)
            - 0.05 * max(float(metrics.get("profit_giveback") or 0.0), 0.0)
        )
        candidates.append((score, record))
    if not candidates:
        return baseline, "keep original exit; all alternatives failed validation stability gates"
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[0][1]
    if selected["name"] == baseline["name"]:
        return selected, "keep original exit; no alternative cleared validation stability with a better composite profile"
    return selected, f"adopt {selected['family']}; " + " ".join(warnings[:2])


def _build_locked_meta_frame(
    *,
    base_config: Path,
    meta_config: Path,
    processed_dataset: Path,
    prediction_csv: Path,
    meta_model_name: str,
    meta_model_kind: str,
    meta_scaler: str,
    meta_calibration: str,
    meta_threshold: float,
    meta_label: str,
) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    frame, meta = _build_candidate_target_frame(
        config_path=base_config,
        processed_dataset=processed_dataset,
        prediction_csv=prediction_csv,
    )
    meta_cfg = _load_yaml(meta_config)
    result = train_stacked_meta_filter(
        frame,
        label_col=str(meta_label),
        model_kind=str(meta_model_kind),
        feature_cols=DEFAULT_META_FEATURE_COLS,
        fold_col="walk_forward_fold",
        candidate_col="primary_candidate",
        side_col="primary_candidate_side",
        primary_oos_col="pred_is_oos",
        pred_col="pred_ret",
        purge_bars=24,
        embargo_bars=24,
        min_train_candidates=100,
        scaler=str(meta_scaler),
        calibration_method=str(meta_calibration),
        calibration_fraction=0.20,
        calibration_min_rows=50,
        random_state=7,
    )
    model_frame = result.frame.copy()
    threshold = float(meta_threshold)
    signal = build_meta_filtered_signal(model_frame, threshold=threshold)
    model_frame["signal_meta_filtered"] = signal
    model_frame["year"] = pd.to_datetime(model_frame["timestamp"]).dt.year
    model_frame["quarter"] = pd.to_datetime(model_frame["timestamp"]).dt.to_period("Q").astype(str)
    meta.update(
        {
            "meta_config": str(meta_config),
            "meta_config_declared_model": str(dict(meta_cfg.get("meta_filter", {}) or {}).get("model_kind", "")),
            "locked_meta_model_name": str(meta_model_name),
            "locked_meta_model": str(meta_model_kind),
            "locked_meta_scaler": str(meta_scaler),
            "locked_meta_calibration": str(meta_calibration),
            "locked_meta_threshold": threshold,
            "locked_meta_label": str(meta_label),
            "meta_fold_count": len(result.artifacts),
            "meta_feature_count": len(DEFAULT_META_FEATURE_COLS),
        }
    )
    return model_frame, signal, meta


def run_exit_policy_comparison(
    *,
    base_config: Path,
    meta_config: Path,
    processed_dataset: Path,
    prediction_csv: Path,
    saved_trade_paths: Path,
    report_path: Path,
    meta_model_name: str = LOCKED_META_MODEL_NAME,
    meta_model_kind: str = LOCKED_META_MODEL_KIND,
    meta_scaler: str = LOCKED_META_SCALER,
    meta_calibration: str = LOCKED_META_CALIBRATION,
    meta_threshold: float = LOCKED_META_THRESHOLD,
    meta_label: str = LOCKED_META_LABEL,
) -> dict[str, Any]:
    frame, locked_signal, meta = _build_locked_meta_frame(
        base_config=base_config,
        meta_config=meta_config,
        processed_dataset=processed_dataset,
        prediction_csv=prediction_csv,
        meta_model_name=meta_model_name,
        meta_model_kind=meta_model_kind,
        meta_scaler=meta_scaler,
        meta_calibration=meta_calibration,
        meta_threshold=meta_threshold,
        meta_label=meta_label,
    )
    cfg = meta["config"]
    periods_per_year = int(dict(cfg.get("backtest", {}) or {}).get("periods_per_year", 17520))
    test_scope = _scope_test(frame)
    baseline_validation_scope = _scope_validation(frame, max_holding_bars=24)

    baseline_validation = _run_policy(
        frame,
        cfg=cfg,
        signal=locked_signal,
        scope_mask=baseline_validation_scope,
        take_profit_r=5.0,
        stop_loss_r=2.0,
        max_holding_bars=24,
    )
    baseline_record = _policy_record(
        "A. Existing fixed exit",
        family="original fixed exit",
        params={"take_profit_r": 5.0, "stop_loss_r": 2.0, "max_holding_bars": 24},
        validation_metrics=_metrics(baseline_validation, periods_per_year=periods_per_year),
        validation_result=baseline_validation,
    )

    fixed_rows: list[dict[str, Any]] = []
    for stop_loss_r in FIXED_STOP_GRID:
        for take_profit_r in FIXED_TP_GRID:
            for max_holding_bars in FIXED_HOLD_GRID:
                result = _run_policy(
                    frame,
                    cfg=cfg,
                    signal=locked_signal,
                    scope_mask=_scope_validation(frame, max_holding_bars=max_holding_bars),
                    take_profit_r=take_profit_r,
                    stop_loss_r=stop_loss_r,
                    max_holding_bars=max_holding_bars,
                )
                fixed_rows.append(
                    {
                        "stop_loss_r": stop_loss_r,
                        "take_profit_r": take_profit_r,
                        "max_holding_bars": max_holding_bars,
                        **_metrics(result, periods_per_year=periods_per_year),
                    }
                )
    fixed_grid = pd.DataFrame(fixed_rows)
    fixed_selected = _select_stable_grid_row(
        fixed_grid,
        param_cols=["stop_loss_r", "take_profit_r", "max_holding_bars"],
        values_by_col={
            "stop_loss_r": FIXED_STOP_GRID,
            "take_profit_r": FIXED_TP_GRID,
            "max_holding_bars": FIXED_HOLD_GRID,
        },
    )
    fixed_validation = _run_policy(
        frame,
        cfg=cfg,
        signal=locked_signal,
        scope_mask=_scope_validation(frame, max_holding_bars=int(fixed_selected["max_holding_bars"])),
        take_profit_r=float(fixed_selected["take_profit_r"]),
        stop_loss_r=float(fixed_selected["stop_loss_r"]),
        max_holding_bars=int(fixed_selected["max_holding_bars"]),
    )
    fixed_record = _policy_record(
        "B. Best validation fixed exit",
        family="new fixed exit",
        params={
            "take_profit_r": float(fixed_selected["take_profit_r"]),
            "stop_loss_r": float(fixed_selected["stop_loss_r"]),
            "max_holding_bars": int(fixed_selected["max_holding_bars"]),
            "selection_reason": fixed_selected["selection_reason"],
        },
        validation_metrics=_metrics(fixed_validation, periods_per_year=periods_per_year),
        validation_result=fixed_validation,
    )

    forecast_rows: list[dict[str, Any]] = []
    for long_exit in LONG_EXIT_GRID:
        for short_exit in SHORT_EXIT_GRID:
            result = _run_policy(
                frame,
                cfg=cfg,
                signal=locked_signal,
                scope_mask=baseline_validation_scope,
                take_profit_r=5.0,
                stop_loss_r=2.0,
                max_holding_bars=24,
                dynamic_exits=_dynamic_forecast_exit(long_exit, short_exit),
            )
            forecast_rows.append(
                {
                    "long_exit_threshold": long_exit,
                    "short_exit_threshold": short_exit,
                    **_metrics(result, periods_per_year=periods_per_year),
                }
            )
    forecast_grid = pd.DataFrame(forecast_rows)
    forecast_selected = _select_stable_grid_row(
        forecast_grid,
        param_cols=["long_exit_threshold", "short_exit_threshold"],
        values_by_col={"long_exit_threshold": LONG_EXIT_GRID, "short_exit_threshold": SHORT_EXIT_GRID},
    )
    forecast_validation = _run_policy(
        frame,
        cfg=cfg,
        signal=locked_signal,
        scope_mask=baseline_validation_scope,
        take_profit_r=5.0,
        stop_loss_r=2.0,
        max_holding_bars=24,
        dynamic_exits=_dynamic_forecast_exit(
            float(forecast_selected["long_exit_threshold"]),
            float(forecast_selected["short_exit_threshold"]),
        ),
    )
    forecast_record = _policy_record(
        "C. Forecast-decay exit",
        family="forecast-decay exit",
        params={
            "long_exit_threshold": float(forecast_selected["long_exit_threshold"]),
            "short_exit_threshold": float(forecast_selected["short_exit_threshold"]),
            "selection_reason": forecast_selected["selection_reason"],
        },
        validation_metrics=_metrics(forecast_validation, periods_per_year=periods_per_year),
        validation_result=forecast_validation,
    )

    hybrid_rows: list[dict[str, Any]] = []
    for long_exit in LONG_EXIT_GRID:
        for short_exit in SHORT_EXIT_GRID:
            result = _run_policy(
                frame,
                cfg=cfg,
                signal=locked_signal,
                scope_mask=baseline_validation_scope,
                take_profit_r=5.0,
                stop_loss_r=2.0,
                max_holding_bars=24,
                dynamic_exits=_dynamic_trend_break(long_exit, short_exit),
            )
            hybrid_rows.append(
                {
                    "long_weakening_level": long_exit,
                    "short_weakening_level": short_exit,
                    **_metrics(result, periods_per_year=periods_per_year),
                }
            )
    hybrid_grid = pd.DataFrame(hybrid_rows)
    hybrid_selected = _select_stable_grid_row(
        hybrid_grid,
        param_cols=["long_weakening_level", "short_weakening_level"],
        values_by_col={"long_weakening_level": LONG_EXIT_GRID, "short_weakening_level": SHORT_EXIT_GRID},
    )
    hybrid_validation = _run_policy(
        frame,
        cfg=cfg,
        signal=locked_signal,
        scope_mask=baseline_validation_scope,
        take_profit_r=5.0,
        stop_loss_r=2.0,
        max_holding_bars=24,
        dynamic_exits=_dynamic_trend_break(
            float(hybrid_selected["long_weakening_level"]),
            float(hybrid_selected["short_weakening_level"]),
        ),
    )
    hybrid_record = _policy_record(
        "D. Forecast + trend-break exit",
        family="forecast plus trend-break exit",
        params={
            "long_weakening_level": float(hybrid_selected["long_weakening_level"]),
            "short_weakening_level": float(hybrid_selected["short_weakening_level"]),
            "selection_reason": hybrid_selected["selection_reason"],
        },
        validation_metrics=_metrics(hybrid_validation, periods_per_year=periods_per_year),
        validation_result=hybrid_validation,
    )

    baseline_path_trades, _ = _trade_path_analysis(frame, _attach_context(frame, baseline_validation.trades.copy()))
    mfe = pd.to_numeric(baseline_path_trades.get("max_favorable_r", pd.Series(dtype=float)), errors="coerce")
    trade_r = pd.to_numeric(baseline_path_trades.get("trade_r", pd.Series(dtype=float)), errors="coerce")
    partial_justified = bool(
        len(baseline_path_trades) >= 10
        and (mfe.ge(1.0).mean() >= 0.35 or mfe.ge(2.0).mean() >= 0.20)
        and ((mfe - trade_r).mean() >= 0.75)
    )
    partial_record: dict[str, Any] | None = None
    partial_grid = pd.DataFrame()
    if partial_justified:
        partial_rows: list[dict[str, Any]] = []
        for partial_name, trigger_r in PARTIAL_RULES:
            for remainder in ["original_tp", "forecast_decay"]:
                dyn = None
                if remainder == "forecast_decay":
                    dyn = _dynamic_forecast_exit(
                        float(forecast_selected["long_exit_threshold"]),
                        float(forecast_selected["short_exit_threshold"]),
                    )
                result = _run_policy(
                    frame,
                    cfg=cfg,
                    signal=locked_signal,
                    scope_mask=baseline_validation_scope,
                    take_profit_r=5.0,
                    stop_loss_r=2.0,
                    max_holding_bars=24,
                    dynamic_exits=dyn,
                    partial_exits=_partial_exit(trigger_r),
                )
                partial_rows.append(
                    {
                        "partial_name": partial_name,
                        "trigger_r": trigger_r,
                        "remainder": remainder,
                        **_metrics(result, periods_per_year=periods_per_year),
                    }
                )
        partial_grid = pd.DataFrame(partial_rows)
        partial_selected = partial_grid.sort_values(
            ["calmar", "profit_factor", "average_net_r", "trade_count"],
            ascending=[False, False, False, False],
        ).iloc[0]
        partial_dyn = None
        if str(partial_selected["remainder"]) == "forecast_decay":
            partial_dyn = _dynamic_forecast_exit(
                float(forecast_selected["long_exit_threshold"]),
                float(forecast_selected["short_exit_threshold"]),
            )
        partial_validation = _run_policy(
            frame,
            cfg=cfg,
            signal=locked_signal,
            scope_mask=baseline_validation_scope,
            take_profit_r=5.0,
            stop_loss_r=2.0,
            max_holding_bars=24,
            dynamic_exits=partial_dyn,
            partial_exits=_partial_exit(float(partial_selected["trigger_r"])),
        )
        partial_record = _policy_record(
            "E. Partial exit",
            family="partial exit",
            params={
                "trigger_r": float(partial_selected["trigger_r"]),
                "fraction": 0.5,
                "remainder": str(partial_selected["remainder"]),
                "partial_justification": "MFE/giveback validation analysis passed",
            },
            validation_metrics=_metrics(partial_validation, periods_per_year=periods_per_year),
            validation_result=partial_validation,
        )

    candidate_records = [baseline_record, fixed_record, forecast_record, hybrid_record]
    if partial_record is not None:
        candidate_records.append(partial_record)
    selected_record, recommendation = _select_final_policy(candidate_records, baseline=baseline_record, frame=frame)

    for record in candidate_records:
        params = record["params"]
        dynamic_exits = None
        partial_exits = None
        take_profit_r = 5.0
        stop_loss_r = 2.0
        max_holding_bars = 24
        if record["family"] == "new fixed exit":
            take_profit_r = float(params["take_profit_r"])
            stop_loss_r = float(params["stop_loss_r"])
            max_holding_bars = int(params["max_holding_bars"])
        elif record["family"] == "forecast-decay exit":
            dynamic_exits = _dynamic_forecast_exit(
                float(params["long_exit_threshold"]),
                float(params["short_exit_threshold"]),
            )
        elif record["family"] == "forecast plus trend-break exit":
            dynamic_exits = _dynamic_trend_break(
                float(params["long_weakening_level"]),
                float(params["short_weakening_level"]),
            )
        elif record["family"] == "partial exit":
            partial_exits = _partial_exit(float(params["trigger_r"]))
            if str(params["remainder"]) == "forecast_decay":
                dynamic_exits = _dynamic_forecast_exit(
                    float(forecast_selected["long_exit_threshold"]),
                    float(forecast_selected["short_exit_threshold"]),
                )
        test_result = _run_policy(
            frame,
            cfg=cfg,
            signal=locked_signal,
            scope_mask=test_scope,
            take_profit_r=take_profit_r,
            stop_loss_r=stop_loss_r,
            max_holding_bars=max_holding_bars,
            dynamic_exits=dynamic_exits,
            partial_exits=partial_exits,
        )
        record["test_result"] = test_result
        record["test_metrics"] = _metrics(test_result, periods_per_year=periods_per_year)

    selected_test_record = next(record for record in candidate_records if record["name"] == selected_record["name"])
    selected_context_trades = _attach_context(frame, selected_test_record["test_result"].trades.copy())
    selected_path_trades, _ = _trade_path_analysis(frame, selected_context_trades)
    baseline_context_all = _attach_context(
        frame,
        _run_policy(
            frame,
            cfg=cfg,
            signal=locked_signal,
            scope_mask=None,
            take_profit_r=5.0,
            stop_loss_r=2.0,
            max_holding_bars=24,
        ).trades.copy(),
    )
    baseline_path_all, _ = _trade_path_analysis(frame, baseline_context_all)

    if saved_trade_paths.exists():
        saved_path_count = int(pd.read_parquet(saved_trade_paths, columns=["trade_id"])["trade_id"].nunique())
    else:
        saved_path_count = 0

    _write_report(
        report_path,
        meta=meta,
        frame=frame,
        saved_path_count=saved_path_count,
        fixed_grid=fixed_grid,
        fixed_selected=fixed_selected,
        forecast_grid=forecast_grid,
        forecast_selected=forecast_selected,
        hybrid_grid=hybrid_grid,
        hybrid_selected=hybrid_selected,
        partial_grid=partial_grid,
        partial_justified=partial_justified,
        records=candidate_records,
        selected=selected_test_record,
        recommendation=recommendation,
        baseline_path_validation=baseline_path_trades,
        baseline_path_all=baseline_path_all,
        selected_path_test=selected_path_trades,
    )

    summary = {
        "selected_exit_policy": selected_test_record["name"],
        "selected_family": selected_test_record["family"],
        "selected_params": selected_test_record["params"],
        "validation_rationale": recommendation,
        "baseline_validation": baseline_record["validation_metrics"],
        "selected_validation": selected_test_record["validation_metrics"],
        "baseline_test": baseline_record["test_metrics"],
        "selected_test": selected_test_record["test_metrics"],
        "fixed_selected": {
            "stop_loss_r": float(fixed_selected["stop_loss_r"]),
            "take_profit_r": float(fixed_selected["take_profit_r"]),
            "max_holding_bars": int(fixed_selected["max_holding_bars"]),
            "neighbor_median_calmar": float(fixed_selected["neighbor_median_calmar"]),
        },
        "forecast_selected": {
            "long_exit_threshold": float(forecast_selected["long_exit_threshold"]),
            "short_exit_threshold": float(forecast_selected["short_exit_threshold"]),
            "neighbor_median_calmar": float(forecast_selected["neighbor_median_calmar"]),
        },
        "hybrid_selected": {
            "long_weakening_level": float(hybrid_selected["long_weakening_level"]),
            "short_weakening_level": float(hybrid_selected["short_weakening_level"]),
            "neighbor_median_calmar": float(hybrid_selected["neighbor_median_calmar"]),
        },
        "partial_justified": partial_justified,
        "report_path": str(report_path),
    }
    return summary


def _write_report(
    path: Path,
    *,
    meta: dict[str, Any],
    frame: pd.DataFrame,
    saved_path_count: int,
    fixed_grid: pd.DataFrame,
    fixed_selected: dict[str, Any],
    forecast_grid: pd.DataFrame,
    forecast_selected: dict[str, Any],
    hybrid_grid: pd.DataFrame,
    hybrid_selected: dict[str, Any],
    partial_grid: pd.DataFrame,
    partial_justified: bool,
    records: list[dict[str, Any]],
    selected: dict[str, Any],
    recommendation: str,
    baseline_path_validation: pd.DataFrame,
    baseline_path_all: pd.DataFrame,
    selected_path_test: pd.DataFrame,
) -> None:
    metric_headers = [
        "Policy",
        "Cum ret",
        "Ann ret",
        "Sharpe",
        "Sortino",
        "Calmar",
        "Max DD",
        "PF",
        "Trades",
        "Avg R",
        "Median R",
        "R skew",
        "Tail R",
        "Avg hold",
        "Turnover",
        "Costs",
        "Giveback",
        "MFE capture",
    ]
    validation_rows = [_metrics_row(f"{record['name']} validation", record["validation_metrics"]) for record in records]
    test_rows = [_metrics_row(f"{record['name']} untouched test", record["test_metrics"]) for record in records]
    fixed_top = (
        fixed_grid.assign(
            is_selected=lambda df: (
                df["stop_loss_r"].eq(float(fixed_selected["stop_loss_r"]))
                & df["take_profit_r"].eq(float(fixed_selected["take_profit_r"]))
                & df["max_holding_bars"].eq(int(fixed_selected["max_holding_bars"]))
            )
        )
        .sort_values(["calmar", "profit_factor", "average_net_r"], ascending=[False, False, False])
        .head(12)
    )
    forecast_top = (
        forecast_grid.assign(
            is_selected=lambda df: (
                df["long_exit_threshold"].eq(float(forecast_selected["long_exit_threshold"]))
                & df["short_exit_threshold"].eq(float(forecast_selected["short_exit_threshold"]))
            )
        )
        .sort_values(["calmar", "profit_factor", "average_net_r"], ascending=[False, False, False])
        .head(12)
    )
    hybrid_top = (
        hybrid_grid.assign(
            is_selected=lambda df: (
                df["long_weakening_level"].eq(float(hybrid_selected["long_weakening_level"]))
                & df["short_weakening_level"].eq(float(hybrid_selected["short_weakening_level"]))
            )
        )
        .sort_values(["calmar", "profit_factor", "average_net_r"], ascending=[False, False, False])
        .head(12)
    )
    selected_validation_trades = _attach_context(frame, selected["validation_result"].trades.copy())
    selected_validation_path, _ = _trade_path_analysis(frame, selected_validation_trades)
    path_headers = [
        "Bucket",
        "Trades",
        "Avg R",
        "Median R",
        "Tail R",
        "Avg MFE",
        "Median MFE",
        "Avg MAE",
        "Median MAE",
        "Median bar MFE",
        "Median bar MAE",
        "Avg giveback",
        "Avg hold",
    ]
    breakdown_headers = ["Bucket", "Trades", "Avg R", "Median R", "Win rate", "PF", "Giveback", "MFE capture"]
    lines = [
        "# ETHUSD Exit Policy Comparison",
        "",
        f"Recommendation: **{recommendation}**",
        "",
        "## Locked Inputs",
        _table(
            ["Field", "Value"],
            [
                ["base_config", meta["config_path"]],
                ["meta_config", meta["meta_config"]],
                ["processed_dataset", meta["processed_dataset"]],
                ["prediction_csv", meta["prediction_csv"]],
                ["saved_trade_paths_trade_count", saved_path_count],
                ["locked_primary_entry_long", 0.70],
                ["locked_primary_entry_short", -0.85],
                ["locked_meta_model_name", meta["locked_meta_model_name"]],
                ["locked_meta_model", meta["locked_meta_model"]],
                ["locked_meta_scaler", meta["locked_meta_scaler"]],
                ["locked_meta_calibration", meta["locked_meta_calibration"]],
                ["locked_meta_threshold", meta["locked_meta_threshold"]],
                ["locked_meta_feature_count", meta["meta_feature_count"]],
                ["diagnostic_meta_config_declared_model", meta["meta_config_declared_model"]],
                ["locked_meta_source", "reports/ethusd_meta_model_comparison.md selected model"],
            ],
        ),
        "## Validation Comparison",
        _table(metric_headers, validation_rows),
        "## Untouched Final Test",
        _table(metric_headers, test_rows),
        "## Selected Policy",
        _table(
            ["Field", "Value"],
            [
                ["selected_policy", selected["name"]],
                ["family", selected["family"]],
                ["params", yaml.safe_dump(selected["params"], sort_keys=True).strip().replace("\n", "<br>")],
                ["selection_basis", "validation stability gates and neighboring-parameter robustness; final test not used for selection"],
            ],
        ),
        "## Fixed Exit Grid Stability",
        _table(
            [
                "Selected",
                "SL R",
                "TP R",
                "Max hold",
                "Trades",
                "Calmar",
                "PF",
                "Avg R",
                "Turnover",
                "Giveback",
            ],
            [
                [
                    bool(row["is_selected"]),
                    row["stop_loss_r"],
                    row["take_profit_r"],
                    row["max_holding_bars"],
                    row["trade_count"],
                    row["calmar"],
                    row["profit_factor"],
                    row["average_net_r"],
                    row["turnover"],
                    row["profit_giveback"],
                ]
                for _, row in fixed_top.iterrows()
            ],
        ),
        "## Forecast-Decay Grid Stability",
        _table(
            [
                "Selected",
                "Long exit",
                "Short exit",
                "Trades",
                "Calmar",
                "PF",
                "Avg R",
                "Turnover",
                "Giveback",
            ],
            [
                [
                    bool(row["is_selected"]),
                    row["long_exit_threshold"],
                    row["short_exit_threshold"],
                    row["trade_count"],
                    row["calmar"],
                    row["profit_factor"],
                    row["average_net_r"],
                    row["turnover"],
                    row["profit_giveback"],
                ]
                for _, row in forecast_top.iterrows()
            ],
        ),
        "## Forecast + Trend-Break Grid Stability",
        _table(
            [
                "Selected",
                "Long weakening",
                "Short weakening",
                "Trades",
                "Calmar",
                "PF",
                "Avg R",
                "Turnover",
                "Giveback",
            ],
            [
                [
                    bool(row["is_selected"]),
                    row["long_weakening_level"],
                    row["short_weakening_level"],
                    row["trade_count"],
                    row["calmar"],
                    row["profit_factor"],
                    row["average_net_r"],
                    row["turnover"],
                    row["profit_giveback"],
                ]
                for _, row in hybrid_top.iterrows()
            ],
        ),
        "## Meta-Probability Decay Exit",
        (
            "Excluded. The current stacked meta model is trained and predicted only on candidate entry rows; "
            "`meta_pred_prob` is not a position-state probability for every held bar. A held-position "
            "meta-probability decay exit would require a separate position-state model."
        ),
        "",
        "## Partial Exit Gate",
        _table(
            ["Field", "Value"],
            [
                ["partial_experiments_enabled", partial_justified],
                ["baseline_validation_mfe_ge_1r_rate", pd.to_numeric(baseline_path_validation["max_favorable_r"], errors="coerce").ge(1.0).mean() if not baseline_path_validation.empty else None],
                ["baseline_validation_mfe_ge_2r_rate", pd.to_numeric(baseline_path_validation["max_favorable_r"], errors="coerce").ge(2.0).mean() if not baseline_path_validation.empty else None],
                ["baseline_validation_avg_giveback", pd.to_numeric(baseline_path_validation["profit_giveback"], errors="coerce").mean() if not baseline_path_validation.empty else None],
            ],
        ),
    ]
    if not partial_grid.empty:
        lines.extend(
            [
                "### Partial Exit Validation Results",
                _table(
                    ["Name", "Trigger R", "Remainder", "Trades", "Calmar", "PF", "Avg R", "Turnover", "Costs"],
                    [
                        [
                            row["partial_name"],
                            row["trigger_r"],
                            row["remainder"],
                            row["trade_count"],
                            row["calmar"],
                            row["profit_factor"],
                            row["average_net_r"],
                            row["turnover"],
                            row["costs"],
                        ]
                        for _, row in partial_grid.iterrows()
                    ],
                ),
            ]
        )
    lines.extend(
        [
            "## Trade-Path Distributions For Locked Baseline",
            "### All/Winners/Losers",
            _table(
                path_headers,
                _distribution_rows(baseline_path_all)
                + _distribution_rows(baseline_path_all.loc[pd.to_numeric(baseline_path_all["trade_r"], errors="coerce").gt(0.0)].assign(bucket="winners"), "bucket")
                + _distribution_rows(baseline_path_all.loc[pd.to_numeric(baseline_path_all["trade_r"], errors="coerce").lt(0.0)].assign(bucket="losers"), "bucket"),
            ),
            "### Long/Short",
            _table(path_headers, _distribution_rows(baseline_path_all, "side_bucket")),
            "### Year",
            _table(path_headers, _distribution_rows(baseline_path_all, "year")),
            "### Fold",
            _table(path_headers, _distribution_rows(baseline_path_all, "walk_forward_fold")),
            "### Volatility Regime",
            _table(path_headers, _distribution_rows(baseline_path_all, "volatility_regime")),
            "### Meta Probability Buckets",
            _table(path_headers, _distribution_rows(baseline_path_all, "meta_probability_bucket")),
            "## Selected Policy Stability",
            "### Year",
            _table(breakdown_headers, _breakdown_rows(selected_validation_path, "year")),
            "### Quarter",
            _table(breakdown_headers, _breakdown_rows(selected_validation_path, "quarter")),
            "### Fold",
            _table(breakdown_headers, _breakdown_rows(selected_validation_path, "walk_forward_fold")),
            "### Long/Short",
            _table(breakdown_headers, _breakdown_rows(selected_validation_path, "side_bucket")),
            "### Volatility Regime",
            _table(breakdown_headers, _breakdown_rows(selected_validation_path, "volatility_regime")),
            "### Meta Probability Buckets",
            _table(breakdown_headers, _breakdown_rows(selected_validation_path, "meta_probability_bucket")),
            "## Untouched Test Path Snapshot For Selected Policy",
            _table(path_headers, _distribution_rows(selected_path_test)),
            "## Leakage And Timing Controls",
            "- Primary predictions are precomputed OOS rows and are not refit in this step.",
            "- Meta-filter training remains candidate-only with the locked feature set, model kind, label, purge, embargo, and threshold.",
            "- Exit search uses only validation folds; signals near the final-fold boundary are excluded when their maximum holding period could spill into the final fold.",
            "- The final fold is evaluated after policy selection, for the selected comparison policies only.",
            "- Forecast-decay and trend-break decisions at bar `t` execute at next open `t+1` when available; TP/SL barriers on bar `t` retain priority.",
            "- Trend-break is never indicator-only: it requires forecast weakening plus at least two disagreeing trend indicators.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare ETHUSD exit policies on the locked meta-filtered strategy.")
    parser.add_argument("--base-config", type=Path, default=BASE_CONFIG)
    parser.add_argument("--meta-config", type=Path, default=META_CONFIG)
    parser.add_argument("--processed-dataset", type=Path, default=PROCESSED_DATASET)
    parser.add_argument("--prediction-csv", type=Path, default=PREDICTION_CSV)
    parser.add_argument("--saved-trade-paths", type=Path, default=SAVED_TRADE_PATHS)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH)
    parser.add_argument("--meta-model-name", default=LOCKED_META_MODEL_NAME)
    parser.add_argument("--meta-model-kind", default=LOCKED_META_MODEL_KIND)
    parser.add_argument("--meta-scaler", default=LOCKED_META_SCALER)
    parser.add_argument("--meta-calibration", default=LOCKED_META_CALIBRATION)
    parser.add_argument("--meta-threshold", type=float, default=LOCKED_META_THRESHOLD)
    parser.add_argument("--meta-label", default=LOCKED_META_LABEL)
    args = parser.parse_args()
    result = run_exit_policy_comparison(
        base_config=args.base_config,
        meta_config=args.meta_config,
        processed_dataset=args.processed_dataset,
        prediction_csv=args.prediction_csv,
        saved_trade_paths=args.saved_trade_paths,
        report_path=args.report_path,
        meta_model_name=args.meta_model_name,
        meta_model_kind=args.meta_model_kind,
        meta_scaler=args.meta_scaler,
        meta_calibration=args.meta_calibration,
        meta_threshold=args.meta_threshold,
        meta_label=args.meta_label,
    )
    print(yaml.safe_dump(result, sort_keys=False).rstrip())


if __name__ == "__main__":
    main()
