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

from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.evaluation.metrics import (
    annualized_return,
    annualized_volatility,
    calmar_ratio,
    hit_rate,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
)
from src.meta.stacked_trade_filter import (
    DEFAULT_META_FEATURE_COLS,
    ORIENTED_FEATURE_SOURCES,
    REGIME_FEATURES,
    CANDLE_PATH_RISK_FEATURES,
    build_causal_meta_features,
    build_meta_filtered_signal,
    compute_probability_diagnostics,
    permutation_importance,
    train_stacked_meta_filter,
)
from src.signals.forecast_signal import compute_forecast_threshold_candidates
from src.targets.path_dependent_r import build_path_dependent_r_target


DEFAULT_CONFIG = (
    ROOT
    / "config"
    / "experiments"
    / "foundation_alpha"
    / "BEST"
    / "ethusd"
    / "BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier.yaml"
)
DEFAULT_PROCESSED_DATASET = (
    ROOT
    / "data"
    / "processed"
    / "processed"
    / "ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_179ecc87_trial_0054"
    / "dataset.csv"
)
DEFAULT_COMPARISON_REPORT = ROOT / "reports" / "ethusd_meta_model_comparison.md"
DEFAULT_CALIBRATION_REPORT = ROOT / "reports" / "ethusd_meta_probability_calibration.md"
DEFAULT_DATASET_OUT = ROOT / "reports" / "ethusd_meta_model_predictions.csv"


THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
LABEL_COLS = ["meta_label_positive", "meta_label_min_0_50r", "meta_label_min_1_00r"]
PRIMARY_LABEL = "meta_label_min_0_50r"


def _latest_prediction_csv() -> Path:
    candidates = sorted(
        (ROOT / "logs" / "experiments").rglob("prediction_distribution.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No prediction_distribution.csv artifact found under logs/experiments.")
    return candidates[0]


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


def _required_processed_cols(cfg: dict[str, Any]) -> list[str]:
    signal_params = dict(dict(cfg.get("signals", {}) or {}).get("params", {}) or {})
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    activation_filters = list(signal_params.get("activation_filters", []) or [])
    filter_cols = [str(item["col"]) for item in activation_filters if isinstance(item, dict) and item.get("col")]
    raw_feature_cols = set(ORIENTED_FEATURE_SOURCES)
    raw_feature_cols.update(col for col in REGIME_FEATURES if col != "vol_ratio_24_192")
    raw_feature_cols.update(CANDLE_PATH_RISK_FEATURES)
    raw_feature_cols.update(
        [
            "timestamp",
            "asset",
            str(backtest_cfg.get("open_col", "open")),
            str(backtest_cfg.get("high_col", "high")),
            str(backtest_cfg.get("low_col", "low")),
            str(backtest_cfg.get("close_col", "close")),
            str(backtest_cfg.get("vol_col", "atr_over_price_48")),
            *filter_cols,
        ]
    )
    return sorted(raw_feature_cols)


def _load_analysis_frame(
    *,
    processed_dataset: Path,
    prediction_csv: Path,
    cfg: dict[str, Any],
) -> pd.DataFrame:
    required_cols = _required_processed_cols(cfg)
    required_set = set(required_cols)
    processed = pd.read_csv(processed_dataset, usecols=lambda col: col in required_set)
    missing = [col for col in required_cols if col not in processed.columns]
    if missing:
        raise KeyError(f"Processed dataset is missing required columns: {missing}")
    processed["timestamp"] = pd.to_datetime(processed["timestamp"])
    processed = processed.sort_values(["asset", "timestamp"]).reset_index(drop=True)

    prediction = pd.read_csv(prediction_csv, usecols=["timestamp", "asset", "prediction"])
    prediction["timestamp"] = pd.to_datetime(prediction["timestamp"])
    prediction = prediction.rename(columns={"prediction": "pred_ret"}).sort_values(["asset", "timestamp"]).reset_index(drop=True)
    split_cfg = dict(dict(cfg.get("model", {}) or {}).get("split", {}) or {})
    test_size = int(split_cfg.get("test_size") or 0)
    prediction["walk_forward_fold"] = (np.arange(len(prediction)) // test_size) + 1 if test_size > 0 else np.nan
    prediction["pred_is_oos"] = True

    merged = processed.merge(
        prediction,
        on=["timestamp", "asset"],
        how="left",
        validate="one_to_one",
    )
    merged["pred_is_oos"] = merged["pred_is_oos"].where(merged["pred_is_oos"].notna(), False).astype(bool)
    return merged.sort_values(["asset", "timestamp"]).set_index("timestamp", drop=False)


def _build_candidate_target_frame(
    *,
    config_path: Path,
    processed_dataset: Path,
    prediction_csv: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    cfg = _load_yaml(config_path)
    signal_params = dict(dict(cfg.get("signals", {}) or {}).get("params", {}) or {})
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    risk_cfg = dict(cfg.get("risk", {}) or {})

    frame = _load_analysis_frame(processed_dataset=processed_dataset, prediction_csv=prediction_csv, cfg=cfg)
    candidates = compute_forecast_threshold_candidates(
        frame,
        forecast_col=str(signal_params.get("forecast_col", "pred_ret")),
        pred_is_oos_col=str(dict(cfg.get("model", {}) or {}).get("pred_is_oos_col", "pred_is_oos")),
        upper=float(signal_params.get("upper", 0.7)),
        lower=float(signal_params.get("lower", -0.85)),
        mode=str(signal_params.get("mode", "long_short")),
        activation_filters=list(signal_params.get("activation_filters", []) or []),
    )
    target_cfg = {
        "kind": "path_dependent_r",
        "candidate_col": "primary_candidate",
        "side_col": "primary_candidate_side",
        "pred_is_oos_col": str(dict(cfg.get("model", {}) or {}).get("pred_is_oos_col", "pred_is_oos")),
        "require_oos": True,
        "open_col": str(backtest_cfg.get("open_col", "open")),
        "high_col": str(backtest_cfg.get("high_col", "high")),
        "low_col": str(backtest_cfg.get("low_col", "low")),
        "close_col": str(backtest_cfg.get("close_col", "close")),
        "volatility_col": str(backtest_cfg.get("vol_col", "atr_over_price_48")),
        "stop_mode": str(backtest_cfg.get("stop_mode", "volatility_stop")),
        "take_profit_r": float(backtest_cfg.get("take_profit_r", 5.0)),
        "stop_loss_r": float(backtest_cfg.get("stop_loss_r", 2.0)),
        "max_holding_bars": backtest_cfg.get("max_holding_bars", 24),
        "risk_per_trade": float(backtest_cfg.get("risk_per_trade", 0.006)),
        "cost_per_unit_turnover": float(risk_cfg.get("cost_per_turnover", 0.0)),
        "slippage_per_unit_turnover": float(risk_cfg.get("slippage_per_turnover", 0.0)),
        "max_leverage": float(risk_cfg.get("max_leverage", 1.0)),
        "entry_price_mode": "next_open",
        "tie_break": "conservative",
        "allow_partial_horizon": False,
        "legacy_same_bar_stop_reason": True,
    }
    target_frame, _, _, target_meta = build_path_dependent_r_target(candidates, target_cfg)
    feature_frame = build_causal_meta_features(
        target_frame,
        pred_col=str(signal_params.get("forecast_col", "pred_ret")),
        side_col="primary_candidate_side",
        price_col=str(backtest_cfg.get("close_col", "close")),
        volatility_col=str(backtest_cfg.get("vol_col", "atr_over_price_48")),
        group_col="asset",
    )
    feature_frame["year"] = pd.to_datetime(feature_frame["timestamp"]).dt.year
    feature_frame["quarter"] = pd.to_datetime(feature_frame["timestamp"]).dt.to_period("Q").astype(str)
    feature_frame["volatility_regime"] = pd.cut(
        pd.to_numeric(feature_frame["atr_pct_rank_192"], errors="coerce"),
        bins=[-np.inf, 0.33, 0.66, np.inf],
        labels=["low", "mid", "high"],
    ).astype("object")
    oos_candidates = feature_frame["primary_candidate"].fillna(0.0).astype(float).gt(0.0)
    feature_frame["primary_forecast_decile"] = np.nan
    if oos_candidates.any():
        feature_frame.loc[oos_candidates, "primary_forecast_decile"] = (
            pd.qcut(
                pd.to_numeric(feature_frame.loc[oos_candidates, "pred_ret"], errors="coerce").rank(method="first"),
                q=10,
                labels=False,
                duplicates="drop",
            )
            + 1
        )
    meta = {
        "config": cfg,
        "target_meta": target_meta,
        "config_path": str(config_path),
        "processed_dataset": str(processed_dataset),
        "prediction_csv": str(prediction_csv),
    }
    return feature_frame, meta


def _run_barrier(
    frame: pd.DataFrame,
    *,
    signal: pd.Series,
    cfg: dict[str, Any],
    signal_col: str = "__meta_signal",
) -> Any:
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    risk_cfg = dict(cfg.get("risk", {}) or {})
    run_frame = frame.copy()
    run_frame[signal_col] = signal.reindex(run_frame.index).fillna(0.0).astype(float)
    return run_manual_barrier_backtest(
        run_frame,
        signal_col=signal_col,
        open_col=str(backtest_cfg.get("open_col", "open")),
        high_col=str(backtest_cfg.get("high_col", "high")),
        low_col=str(backtest_cfg.get("low_col", "low")),
        close_col=str(backtest_cfg.get("close_col", "close")),
        take_profit_r=float(backtest_cfg.get("take_profit_r", 5.0)),
        stop_loss_r=float(backtest_cfg.get("stop_loss_r", 2.0)),
        risk_per_trade=float(backtest_cfg.get("risk_per_trade", 0.006)),
        max_holding_bars=backtest_cfg.get("max_holding_bars", 24),
        cost_per_unit_turnover=float(risk_cfg.get("cost_per_turnover", 0.0)),
        slippage_per_unit_turnover=float(risk_cfg.get("slippage_per_turnover", 0.0)),
        max_leverage=float(risk_cfg.get("max_leverage", 1.0)),
        periods_per_year=int(backtest_cfg.get("periods_per_year", 17520)),
        allow_short=bool(backtest_cfg.get("allow_short", False)),
        stop_mode=str(backtest_cfg.get("stop_mode", "volatility_stop")),
        vol_col=str(backtest_cfg.get("vol_col", "atr_over_price_48")),
    )


def _trade_metrics(result: Any, *, periods_per_year: int) -> dict[str, Any]:
    returns = result.returns.astype(float)
    equity = result.equity_curve.astype(float)
    trades = result.trades.copy() if result.trades is not None else pd.DataFrame()
    trade_r = pd.to_numeric(trades.get("trade_r", pd.Series(dtype=float)), errors="coerce")
    exit_reason = trades.get("exit_reason", pd.Series(dtype=object)).astype(str) if not trades.empty else pd.Series(dtype=object)
    gross_sum = float(result.gross_returns.sum()) if result.gross_returns is not None else 0.0
    cost_sum = float(result.costs.sum()) if result.costs is not None else 0.0
    return {
        "cumulative_return": float(equity.iloc[-1] - 1.0) if len(equity) else 0.0,
        "annualized_return": annualized_return(returns, periods_per_year=periods_per_year),
        "annualized_volatility": annualized_volatility(returns, periods_per_year=periods_per_year),
        "sharpe": sharpe_ratio(returns, periods_per_year=periods_per_year),
        "sortino": sortino_ratio(returns, periods_per_year=periods_per_year),
        "calmar": calmar_ratio(returns, periods_per_year=periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "profit_factor": profit_factor(returns),
        "hit_rate": hit_rate(returns),
        "trade_count": int(len(trades)),
        "average_net_r": float(trade_r.mean()) if len(trade_r.dropna()) else None,
        "median_net_r": float(trade_r.median()) if len(trade_r.dropna()) else None,
        "r_std": float(trade_r.std(ddof=1)) if len(trade_r.dropna()) > 1 else None,
        "turnover": float(result.turnover.sum()) if result.turnover is not None else None,
        "cost_to_gross_pnl": float(cost_sum / abs(gross_sum)) if abs(gross_sum) > 1e-12 else None,
        "average_holding_bars": float(pd.to_numeric(trades.get("bars_held", pd.Series(dtype=float)), errors="coerce").mean())
        if not trades.empty
        else None,
        "tp_rate": float((exit_reason == "take_profit").mean()) if len(exit_reason) else None,
        "sl_rate": float(exit_reason.str.contains("stop", regex=False).mean()) if len(exit_reason) else None,
        "time_exit_rate": float((exit_reason == "max_holding_close").mean()) if len(exit_reason) else None,
    }


def _metrics_row(name: str, metrics: dict[str, Any]) -> list[Any]:
    return [
        name,
        metrics.get("cumulative_return"),
        metrics.get("annualized_return"),
        metrics.get("annualized_volatility"),
        metrics.get("sharpe"),
        metrics.get("sortino"),
        metrics.get("calmar"),
        metrics.get("max_drawdown"),
        metrics.get("profit_factor"),
        metrics.get("hit_rate"),
        metrics.get("trade_count"),
        metrics.get("average_net_r"),
        metrics.get("median_net_r"),
        metrics.get("r_std"),
        metrics.get("turnover"),
        metrics.get("cost_to_gross_pnl"),
        metrics.get("average_holding_bars"),
        metrics.get("tp_rate"),
        metrics.get("sl_rate"),
        metrics.get("time_exit_rate"),
    ]


def _evaluate_signal(
    frame: pd.DataFrame,
    *,
    signal: pd.Series,
    cfg: dict[str, Any],
    scope_mask: pd.Series | None = None,
) -> dict[str, Any]:
    scoped_signal = signal.copy().astype(float)
    if scope_mask is not None:
        scoped_signal = scoped_signal.where(scope_mask.reindex(frame.index).fillna(False), 0.0)
    result = _run_barrier(frame, signal=scoped_signal, cfg=cfg)
    return _trade_metrics(result, periods_per_year=int(dict(cfg.get("backtest", {}) or {}).get("periods_per_year", 17520)))


def _attach_trade_context(frame: pd.DataFrame, trades: pd.DataFrame, *, prob_col: str | None = None) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    context_cols = [
        "year",
        "quarter",
        "walk_forward_fold",
        "volatility_regime",
        "primary_forecast_decile",
        "primary_candidate_side",
        "pred_ret",
    ]
    if prob_col and prob_col in frame.columns:
        context_cols.append(prob_col)
    context = frame[[col for col in context_cols if col in frame.columns]].copy()
    out = trades.merge(context, left_on="signal_timestamp", right_index=True, how="left")
    if prob_col and prob_col in out.columns:
        out["meta_probability_decile"] = np.nan
        valid = pd.to_numeric(out[prob_col], errors="coerce").notna()
        if valid.any():
            out.loc[valid, "meta_probability_decile"] = (
                pd.qcut(pd.to_numeric(out.loc[valid, prob_col], errors="coerce").rank(method="first"), q=10, labels=False, duplicates="drop")
                + 1
            )
    out["side_bucket"] = np.where(out["side"].astype(str).eq("long"), "long", "short")
    return out


def _breakdown_rows(trades: pd.DataFrame, by: str) -> list[list[Any]]:
    if trades.empty or by not in trades.columns:
        return []
    rows: list[list[Any]] = []
    for key, group in trades.groupby(by, dropna=False):
        trade_r = pd.to_numeric(group["trade_r"], errors="coerce")
        net_return = pd.to_numeric(group["net_return"], errors="coerce")
        gross_profit = float(net_return[net_return > 0].sum())
        gross_loss = float((-net_return[net_return < 0]).sum())
        exit_reason = group["exit_reason"].astype(str)
        rows.append(
            [
                key,
                int(len(group)),
                float(trade_r.mean()) if len(trade_r.dropna()) else None,
                float(trade_r.median()) if len(trade_r.dropna()) else None,
                float((trade_r > 0).mean()) if len(trade_r.dropna()) else None,
                float(gross_profit / gross_loss) if gross_loss > 1e-12 else None,
                float((exit_reason == "take_profit").mean()) if len(exit_reason) else None,
                float(exit_reason.str.contains("stop", regex=False).mean()) if len(exit_reason) else None,
                float((exit_reason == "max_holding_close").mean()) if len(exit_reason) else None,
            ]
        )
    return rows


def _aggregate_importance_rows(fold_diagnostics: list[dict[str, Any]], *, limit: int = 20) -> list[list[Any]]:
    rows: list[dict[str, Any]] = []
    for diag in fold_diagnostics:
        for feature, value in dict(diag.get("feature_importance", {}) or {}).items():
            rows.append({"feature": feature, "importance": float(value), "fold": diag.get("fold")})
    if not rows:
        return []
    frame = pd.DataFrame(rows)
    grouped = (
        frame.groupby("feature", as_index=False)
        .agg(mean_importance=("importance", "mean"), fold_count=("fold", "nunique"))
        .sort_values("mean_importance", ascending=False)
        .head(limit)
    )
    return grouped[["feature", "mean_importance", "fold_count"]].values.tolist()


def _fold_stability_rows(fold_diagnostics: list[dict[str, Any]], *, top_n: int = 5) -> list[list[Any]]:
    counts: dict[str, int] = {}
    total = 0
    for diag in fold_diagnostics:
        importance = dict(diag.get("feature_importance", {}) or {})
        if not importance:
            continue
        total += 1
        top = sorted(importance.items(), key=lambda item: float(item[1]), reverse=True)[:top_n]
        for feature, _ in top:
            counts[feature] = counts.get(feature, 0) + 1
    return [[feature, count, float(count / total) if total else None] for feature, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _select_threshold(validation_rows: pd.DataFrame) -> dict[str, Any]:
    valid = validation_rows.copy()
    valid["score"] = pd.to_numeric(valid["calmar"], errors="coerce")
    if valid["score"].dropna().empty:
        valid["score"] = pd.to_numeric(valid["average_net_r"], errors="coerce")
    valid = valid.sort_values(["score", "trade_count"], ascending=[False, False])
    best = valid.iloc[0].to_dict()
    best_score = float(best.get("score") or 0.0)
    plateau = validation_rows.loc[pd.to_numeric(validation_rows["calmar"], errors="coerce") >= best_score * 0.90].copy()
    if plateau.empty:
        plateau = valid.head(1)
    plateau = plateau.sort_values(["trade_count", "threshold"], ascending=[False, True])
    selected = plateau.iloc[0].to_dict()
    selected["selection_reason"] = "lowest practical threshold on validation plateau"
    selected["best_threshold_by_score"] = best.get("threshold")
    return selected


def _verdict(selected_test: dict[str, Any], baseline_test: dict[str, Any]) -> str:
    if not selected_test or not baseline_test:
        return "meta-model rejected due to leakage/fragility"
    baseline_return = float(baseline_test.get("cumulative_return") or 0.0)
    selected_return = float(selected_test.get("cumulative_return") or 0.0)
    baseline_dd = abs(float(baseline_test.get("max_drawdown") or 0.0))
    selected_dd = abs(float(selected_test.get("max_drawdown") or 0.0))
    pf_improved = float(selected_test.get("profit_factor") or 0.0) >= float(baseline_test.get("profit_factor") or 0.0)
    avg_r_improved = float(selected_test.get("average_net_r") or -999.0) >= float(baseline_test.get("average_net_r") or -999.0)
    retained = selected_return >= 0.70 * baseline_return if baseline_return > 0 else selected_return >= baseline_return
    dd_reduced = selected_dd <= 0.85 * baseline_dd if baseline_dd > 0 else selected_dd <= baseline_dd
    if retained and dd_reduced and (pf_improved or avg_r_improved):
        return "meta-model accepted"
    if retained and (dd_reduced or pf_improved or avg_r_improved):
        return "meta-model promising but unstable"
    if selected_return >= baseline_return and (pf_improved or avg_r_improved):
        return "meta-model promising but unstable"
    return "meta-model adds no value"


def run_comparison(
    *,
    config_path: Path,
    processed_dataset: Path,
    prediction_csv: Path,
    comparison_report: Path,
    calibration_report: Path,
    dataset_out: Path,
) -> dict[str, Any]:
    frame, meta = _build_candidate_target_frame(
        config_path=config_path,
        processed_dataset=processed_dataset,
        prediction_csv=prediction_csv,
    )
    cfg = meta["config"]
    final_fold = int(pd.to_numeric(frame["walk_forward_fold"], errors="coerce").dropna().max())
    validation_scope = frame["walk_forward_fold"].notna() & frame["walk_forward_fold"].astype(float).lt(float(final_fold))
    test_scope = frame["walk_forward_fold"].astype(float).eq(float(final_fold))
    candidate_scope = frame["primary_candidate"].fillna(0.0).astype(float).gt(0.0)
    valid_candidate_scope = candidate_scope & pd.to_numeric(frame[PRIMARY_LABEL], errors="coerce").notna()

    baseline_signal = pd.Series(0.0, index=frame.index, dtype=float)
    baseline_signal.loc[valid_candidate_scope] = pd.to_numeric(frame.loc[valid_candidate_scope, "primary_candidate_side"], errors="coerce").fillna(0.0)
    baseline_all = _evaluate_signal(frame, signal=baseline_signal, cfg=cfg)
    baseline_validation = _evaluate_signal(frame, signal=baseline_signal, cfg=cfg, scope_mask=validation_scope)
    baseline_test = _evaluate_signal(frame, signal=baseline_signal, cfg=cfg, scope_mask=test_scope)

    model_specs = [
        {"name": "logistic_meta_filter", "model_kind": "logistic_regression_clf", "calibration_method": "none", "scaler": "robust"},
        {"name": "lightgbm_meta_filter", "model_kind": "lightgbm_clf", "calibration_method": "none", "scaler": "none"},
        {"name": "lightgbm_calibrated_meta_filter", "model_kind": "lightgbm_clf", "calibration_method": "sigmoid", "scaler": "none"},
    ]

    comparison_rows: list[dict[str, Any]] = []
    model_results: dict[str, Any] = {}
    prediction_output = frame.copy()
    for spec in model_specs:
        result = train_stacked_meta_filter(
            frame,
            label_col=PRIMARY_LABEL,
            model_kind=spec["model_kind"],
            feature_cols=DEFAULT_META_FEATURE_COLS,
            fold_col="walk_forward_fold",
            candidate_col="primary_candidate",
            side_col="primary_candidate_side",
            primary_oos_col="pred_is_oos",
            pred_col="pred_ret",
            purge_bars=24,
            embargo_bars=24,
            min_train_candidates=100,
            scaler=spec["scaler"],
            calibration_method=spec["calibration_method"],
            calibration_fraction=0.20,
            calibration_min_rows=50,
            random_state=7,
        )
        model_frame = result.frame.copy()
        model_frame[f"{spec['name']}_prob"] = model_frame["meta_pred_prob"]
        model_frame[f"{spec['name']}_raw_prob"] = model_frame["meta_pred_raw_prob"]
        model_frame[f"{spec['name']}_is_oos"] = model_frame["meta_pred_is_oos"]
        prediction_output[f"{spec['name']}_prob"] = model_frame["meta_pred_prob"]
        prediction_output[f"{spec['name']}_raw_prob"] = model_frame["meta_pred_raw_prob"]
        prediction_output[f"{spec['name']}_is_oos"] = model_frame["meta_pred_is_oos"]
        validation_threshold_rows: list[dict[str, Any]] = []
        for threshold in THRESHOLDS:
            signal = build_meta_filtered_signal(model_frame, threshold=threshold)
            all_metrics = _evaluate_signal(model_frame, signal=signal, cfg=cfg)
            validation_metrics = _evaluate_signal(model_frame, signal=signal, cfg=cfg, scope_mask=validation_scope)
            test_metrics = _evaluate_signal(model_frame, signal=signal, cfg=cfg, scope_mask=test_scope)
            row = {
                "model": spec["name"],
                "threshold": threshold,
                **{f"all_{key}": value for key, value in all_metrics.items()},
                **{f"validation_{key}": value for key, value in validation_metrics.items()},
                **{f"test_{key}": value for key, value in test_metrics.items()},
            }
            comparison_rows.append(row)
            validation_threshold_rows.append(
                {
                    "model": spec["name"],
                    "threshold": threshold,
                    **validation_metrics,
                }
            )
        validation_df = pd.DataFrame(validation_threshold_rows)
        selected = _select_threshold(validation_df)
        selected_threshold = float(selected["threshold"])
        selected_signal = build_meta_filtered_signal(model_frame, threshold=selected_threshold)
        selected_result = _run_barrier(model_frame, signal=selected_signal, cfg=cfg)
        selected_trades = _attach_trade_context(model_frame, selected_result.trades.copy(), prob_col="meta_pred_prob")
        diagnostics = compute_probability_diagnostics(
            model_frame,
            label_cols=LABEL_COLS,
            prob_col="meta_pred_prob",
            meta_oos_col="meta_pred_is_oos",
            r_col="meta_net_r",
            bins=10,
        )
        permutation = permutation_importance(result, label_col=PRIMARY_LABEL, max_features=20, random_state=7)
        model_results[spec["name"]] = {
            "spec": spec,
            "result": result,
            "selected": selected,
            "selected_threshold": selected_threshold,
            "selected_signal": selected_signal,
            "selected_result": selected_result,
            "selected_trades": selected_trades,
            "diagnostics": diagnostics,
            "permutation": permutation,
            "validation_thresholds": validation_df,
            "all_metrics": _evaluate_signal(model_frame, signal=selected_signal, cfg=cfg),
            "validation_metrics": _evaluate_signal(model_frame, signal=selected_signal, cfg=cfg, scope_mask=validation_scope),
            "test_metrics": _evaluate_signal(model_frame, signal=selected_signal, cfg=cfg, scope_mask=test_scope),
        }

    comparison_df = pd.DataFrame(comparison_rows)
    selected_model_name = max(
        model_results,
        key=lambda name: float(model_results[name]["validation_metrics"].get("calmar") or -999.0),
    )
    selected_model = model_results[selected_model_name]
    verdict = _verdict(selected_model["test_metrics"], baseline_test)

    dataset_out.parent.mkdir(parents=True, exist_ok=True)
    out_cols = [
        "timestamp",
        "asset",
        "walk_forward_fold",
        "pred_ret",
        "pred_is_oos",
        "primary_candidate",
        "primary_candidate_side",
        "meta_net_r",
        *LABEL_COLS,
        *[f"{spec['name']}_prob" for spec in model_specs],
        *[f"{spec['name']}_is_oos" for spec in model_specs],
    ]
    prediction_output.loc[prediction_output["pred_is_oos"].astype(bool), [col for col in out_cols if col in prediction_output.columns]].to_csv(dataset_out, index=False)

    comparison_report.parent.mkdir(parents=True, exist_ok=True)
    _write_comparison_report(
        comparison_report,
        frame=frame,
        meta=meta,
        baseline_all=baseline_all,
        baseline_validation=baseline_validation,
        baseline_test=baseline_test,
        model_results=model_results,
        selected_model_name=selected_model_name,
        verdict=verdict,
        comparison_df=comparison_df,
        prediction_output_path=dataset_out,
    )
    _write_calibration_report(
        calibration_report,
        model_results=model_results,
        selected_model_name=selected_model_name,
    )
    return {
        "comparison_report": str(comparison_report),
        "calibration_report": str(calibration_report),
        "prediction_dataset": str(dataset_out),
        "selected_model": selected_model_name,
        "selected_threshold": float(selected_model["selected_threshold"]),
        "verdict": verdict,
        "baseline_test_trade_count": int(baseline_test.get("trade_count") or 0),
        "selected_test_trade_count": int(selected_model["test_metrics"].get("trade_count") or 0),
    }


def _write_comparison_report(
    path: Path,
    *,
    frame: pd.DataFrame,
    meta: dict[str, Any],
    baseline_all: dict[str, Any],
    baseline_validation: dict[str, Any],
    baseline_test: dict[str, Any],
    model_results: dict[str, Any],
    selected_model_name: str,
    verdict: str,
    comparison_df: pd.DataFrame,
    prediction_output_path: Path,
) -> None:
    cfg = meta["config"]
    candidate_rows = frame.loc[frame["primary_candidate"].fillna(0.0).astype(float).gt(0.0)]
    valid_candidates = candidate_rows.loc[pd.to_numeric(candidate_rows[PRIMARY_LABEL], errors="coerce").notna()]
    selected = model_results[selected_model_name]
    selected_trades = selected["selected_trades"]
    metric_headers = [
        "Experiment",
        "Cumulative return",
        "Annualized return",
        "Annualized vol",
        "Sharpe",
        "Sortino",
        "Calmar",
        "Max DD",
        "Profit factor",
        "Hit rate",
        "Trades",
        "Avg net R",
        "Median net R",
        "R std",
        "Turnover",
        "Cost/gross",
        "Avg holding",
        "TP rate",
        "SL rate",
        "Time exit",
    ]
    selected_rows = [
        _metrics_row("Primary baseline all OOS", baseline_all),
        _metrics_row("Primary baseline validation folds", baseline_validation),
        _metrics_row("Primary baseline untouched final fold", baseline_test),
    ]
    for name, payload in model_results.items():
        selected_rows.extend(
            [
                _metrics_row(f"{name} selected all OOS @ {payload['selected_threshold']:.2f}", payload["all_metrics"]),
                _metrics_row(
                    f"{name} selected validation @ {payload['selected_threshold']:.2f}",
                    payload["validation_metrics"],
                ),
                _metrics_row(
                    f"{name} selected untouched final fold @ {payload['selected_threshold']:.2f}",
                    payload["test_metrics"],
                ),
            ]
        )
    validation_rows = []
    for _, row in comparison_df.sort_values(["model", "threshold"]).iterrows():
        validation_rows.append(
            [
                row["model"],
                row["threshold"],
                row.get("validation_trade_count"),
                row.get("validation_cumulative_return"),
                row.get("validation_calmar"),
                row.get("validation_profit_factor"),
                row.get("validation_average_net_r"),
                row.get("test_trade_count"),
                row.get("test_cumulative_return"),
                row.get("test_calmar"),
                row.get("test_profit_factor"),
                row.get("test_average_net_r"),
            ]
        )
    lines = [
        "# ETHUSD Meta-Model Comparison",
        "",
        f"Final verdict: **{verdict}**.",
        "",
        "## Final Architecture",
        "- Primary alpha remains the existing ETHUSD 30m LightGBM regressor and is not replaced.",
        "- Primary threshold candidates are built only from OOS primary `pred_ret` rows.",
        "- Path-dependent labels are candidate-only and use the same manual-barrier TP/SL/max-holding convention.",
        "- The stacked meta layer trains only on older completed candidates, with 24-bar purge and 24-bar embargo metadata.",
        "- Fold-local preprocessing is fitted on each meta training fold. Sigmoid calibration, where used, is fitted only on the most recent internal slice of that training fold.",
        "- Final signal equals `primary_candidate_side` only when `meta_pred_is_oos=true` and `meta_pred_prob >= threshold`; otherwise it is flat.",
        "",
        "## Inputs",
        _table(
            ["Artifact", "Path"],
            [
                ["Locked baseline config", meta["config_path"]],
                ["Processed OHLC/features", meta["processed_dataset"]],
                ["OOS primary predictions", meta["prediction_csv"]],
                ["Meta prediction CSV", str(prediction_output_path)],
            ],
        ),
        "## Candidate Dataset",
        _table(
            ["Metric", "Value"],
            [
                ["OOS rows", int(frame["pred_is_oos"].fillna(False).astype(bool).sum())],
                ["Candidate rows", int(len(candidate_rows))],
                ["Valid completed candidates", int(len(valid_candidates))],
                ["Positive label rate, +0.50R", float(valid_candidates[PRIMARY_LABEL].mean())],
                ["Final untouched fold", int(pd.to_numeric(frame["walk_forward_fold"], errors="coerce").dropna().max())],
            ],
        ),
        "## Selected Model",
        _table(
            ["Field", "Value"],
            [
                ["selected_model", selected_model_name],
                ["selected_threshold", selected["selected_threshold"]],
                ["validation_selection_reason", selected["selected"].get("selection_reason")],
                ["best_threshold_by_score", selected["selected"].get("best_threshold_by_score")],
            ],
        ),
        "## Main Metrics",
        _table(metric_headers, selected_rows),
        "## Threshold Sweep",
        _table(
            [
                "Model",
                "Threshold",
                "Validation trades",
                "Validation return",
                "Validation Calmar",
                "Validation PF",
                "Validation avg R",
                "Test trades",
                "Test return",
                "Test Calmar",
                "Test PF",
                "Test avg R",
            ],
            validation_rows,
        ),
        "## Untouched Test Comparison",
        _table(
            metric_headers,
            [
                _metrics_row("Primary baseline untouched final fold", baseline_test),
                _metrics_row(
                    f"{selected_model_name} untouched final fold @ {selected['selected_threshold']:.2f}",
                    selected["test_metrics"],
                ),
            ],
        ),
        "## Breakdowns For Selected Model",
        "### By Year",
        _table(["Year", "Trades", "Avg R", "Median R", "Hit rate", "Profit factor", "TP", "SL", "Time exit"], _breakdown_rows(selected_trades, "year")),
        "### By Quarter",
        _table(["Quarter", "Trades", "Avg R", "Median R", "Hit rate", "Profit factor", "TP", "SL", "Time exit"], _breakdown_rows(selected_trades, "quarter")),
        "### By Walk-Forward Fold",
        _table(["Fold", "Trades", "Avg R", "Median R", "Hit rate", "Profit factor", "TP", "SL", "Time exit"], _breakdown_rows(selected_trades, "walk_forward_fold")),
        "### Long/Short",
        _table(["Side", "Trades", "Avg R", "Median R", "Hit rate", "Profit factor", "TP", "SL", "Time exit"], _breakdown_rows(selected_trades, "side_bucket")),
        "### Volatility Regime",
        _table(["Regime", "Trades", "Avg R", "Median R", "Hit rate", "Profit factor", "TP", "SL", "Time exit"], _breakdown_rows(selected_trades, "volatility_regime")),
        "### Primary Forecast Decile",
        _table(["Decile", "Trades", "Avg R", "Median R", "Hit rate", "Profit factor", "TP", "SL", "Time exit"], _breakdown_rows(selected_trades, "primary_forecast_decile")),
        "### Meta Probability Decile",
        _table(["Decile", "Trades", "Avg R", "Median R", "Hit rate", "Profit factor", "TP", "SL", "Time exit"], _breakdown_rows(selected_trades, "meta_probability_decile")),
        "## Feature Diagnostics",
    ]
    for name, payload in model_results.items():
        lines.extend(
            [
                f"### {name} Feature Importance",
                _table(["Feature", "Mean importance", "Fold count"], _aggregate_importance_rows(payload["result"].fold_diagnostics, limit=20)),
                f"### {name} Permutation Importance",
                _table(
                    ["Feature", "Mean log-loss delta", "Fold count"],
                    payload["permutation"][["feature", "mean_log_loss_delta", "fold_count"]].head(20).values.tolist()
                    if not payload["permutation"].empty
                    else [],
                ),
                f"### {name} Top-Feature Stability",
                _table(["Feature", "Top-5 fold count", "Share of fit folds"], _fold_stability_rows(payload["result"].fold_diagnostics, top_n=5)),
            ]
        )
    lines.extend(
        [
            "## Leakage Checks",
            "- Candidate rows with non-OOS primary predictions are rejected before training.",
            "- Training rows are completed candidates only.",
            "- For each meta fold, `train_max_pos < test_start_pos - purge_bars` by construction.",
            "- Calibration rows are split from the training fold only and never from test rows.",
            "- `meta_*` target/outcome/prediction columns are rejected from the feature matrix.",
            "",
            "SHAP summary: not produced in this run; the local environment does not include `shap`, and the permutation/LightGBM gain diagnostics above are the committed feature diagnostics.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_calibration_report(path: Path, *, model_results: dict[str, Any], selected_model_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ETHUSD Meta Probability Calibration",
        "",
        f"Selected model for signal comparison: **{selected_model_name}**.",
        "",
    ]
    for name, payload in model_results.items():
        diagnostics = payload["diagnostics"]
        lines.extend([f"## {name}", "### Probability Metrics"])
        metric_rows = []
        for label_col, metrics in diagnostics["metrics"].items():
            metric_rows.append(
                [
                    label_col,
                    metrics.get("rows"),
                    metrics.get("brier_score"),
                    metrics.get("log_loss"),
                    metrics.get("roc_auc"),
                    metrics.get("pr_auc"),
                    metrics.get("calibration_slope"),
                    metrics.get("calibration_intercept"),
                ]
            )
        lines.append(
            _table(
                ["Label", "Rows", "Brier", "Log loss", "ROC AUC", "PR AUC", "Calibration slope", "Calibration intercept"],
                metric_rows,
            )
        )
        lines.append("### Reliability Table For +0.50R")
        reliability = diagnostics["reliability"][PRIMARY_LABEL]
        lines.append(
            _table(
                ["Bucket", "Candidates", "Avg predicted probability", "Realized success rate", "Average net R"],
                reliability.values.tolist(),
            )
        )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--processed-dataset", type=Path, default=DEFAULT_PROCESSED_DATASET)
    parser.add_argument("--prediction-csv", type=Path, default=None)
    parser.add_argument("--comparison-report", type=Path, default=DEFAULT_COMPARISON_REPORT)
    parser.add_argument("--calibration-report", type=Path, default=DEFAULT_CALIBRATION_REPORT)
    parser.add_argument("--dataset-out", type=Path, default=DEFAULT_DATASET_OUT)
    args = parser.parse_args()

    prediction_csv = args.prediction_csv or _latest_prediction_csv()
    result = run_comparison(
        config_path=args.config,
        processed_dataset=args.processed_dataset,
        prediction_csv=prediction_csv,
        comparison_report=args.comparison_report,
        calibration_report=args.calibration_report,
        dataset_out=args.dataset_out,
    )
    print(yaml.safe_dump(result, sort_keys=False).rstrip())


if __name__ == "__main__":
    main()
