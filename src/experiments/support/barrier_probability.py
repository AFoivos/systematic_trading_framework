from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult
from src.targets.first_passage_barrier import build_first_passage_barrier_target


def _numeric_summary(series: pd.Series) -> dict[str, float | int | None]:
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if values.empty:
        return {"rows": 0, "mean": None, "median": None, "q05": None, "q95": None}
    return {
        "rows": int(len(values)),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "q05": float(values.quantile(0.05)),
        "q95": float(values.quantile(0.95)),
    }


def _bucket_summary(
    score: pd.Series,
    realized: pd.Series,
    *,
    buckets: int = 10,
) -> list[dict[str, float | int | None]]:
    aligned = pd.concat(
        [pd.to_numeric(score, errors="coerce").rename("score"), pd.to_numeric(realized, errors="coerce").rename("realized")],
        axis=1,
    ).dropna()
    if aligned.empty or int(aligned["score"].nunique()) < 2:
        return []
    count = min(int(buckets), int(aligned["score"].nunique()))
    groups = pd.qcut(aligned["score"], q=count, labels=False, duplicates="drop")
    rows: list[dict[str, float | int | None]] = []
    for bucket, group in aligned.groupby(groups, observed=True):
        rows.append(
            {
                "bucket": int(bucket),
                "rows": int(len(group)),
                "score_min": float(group["score"].min()),
                "score_max": float(group["score"].max()),
                "score_mean": float(group["score"].mean()),
                "realized_mean": float(group["realized"].mean()),
                "realized_median": float(group["realized"].median()),
                "positive_rate": float((group["realized"] > 0.0).mean()),
            }
        )
    return rows


def _group_performance(
    values: pd.Series,
    groups: pd.Series,
) -> list[dict[str, float | int | str | None]]:
    aligned = pd.concat(
        [pd.to_numeric(values, errors="coerce").rename("return"), groups.rename("group")],
        axis=1,
    ).dropna()
    rows: list[dict[str, float | int | str | None]] = []
    for group, frame in aligned.groupby("group", observed=True):
        returns = frame["return"].astype(float)
        rows.append(
            {
                "group": str(group),
                "rows": int(len(returns)),
                "mean_return": float(returns.mean()),
                "median_return": float(returns.median()),
                "positive_rate": float((returns > 0.0).mean()),
                "cumulative_return": float((1.0 + returns).prod() - 1.0),
            }
        )
    return rows


def _trade_regime_inputs(
    df: pd.DataFrame,
    performance: BacktestResult,
) -> tuple[pd.Series, pd.DataFrame, pd.Series] | None:
    trades = performance.trades
    if trades is None or trades.empty or "net_return" not in trades.columns:
        return None
    timestamp_col = next(
        (
            column
            for column in ("signal_timestamp", "signal_time")
            if column in trades.columns
        ),
        None,
    )
    if timestamp_col is None or not isinstance(df.index, pd.DatetimeIndex):
        return None
    timestamps = pd.DatetimeIndex(pd.to_datetime(trades[timestamp_col], errors="coerce"))
    if timestamps.isna().any():
        return None
    if df.index.tz is None and timestamps.tz is not None:
        timestamps = timestamps.tz_localize(None)
    elif df.index.tz is not None and timestamps.tz is None:
        timestamps = timestamps.tz_localize(df.index.tz)
    elif df.index.tz is not None and timestamps.tz is not None:
        timestamps = timestamps.tz_convert(df.index.tz)
    positions = df.index.get_indexer(timestamps)
    if bool((positions < 0).any()):
        return None
    row_index = pd.RangeIndex(len(trades))
    decision_features = df.iloc[positions].copy()
    decision_features.index = row_index
    trade_returns = pd.Series(
        pd.to_numeric(trades["net_return"], errors="coerce").to_numpy(dtype=float),
        index=row_index,
        dtype=float,
    )
    return trade_returns, decision_features, pd.Series(timestamps, index=row_index)


def _regime_reports(df: pd.DataFrame, performance: BacktestResult) -> dict[str, list[dict[str, Any]]]:
    trade_inputs = _trade_regime_inputs(df, performance)
    if trade_inputs is None:
        return {}
    returns, decision_features, timestamps = trade_inputs
    reports: dict[str, list[dict[str, Any]]] = {}
    reports["hour"] = _group_performance(returns, timestamps.dt.hour)
    session_columns = [
        column
        for column in (
            "session_asia",
            "session_london",
            "session_new_york",
            "session_london_new_york_overlap",
        )
        if column in decision_features.columns
    ]
    if session_columns:
        session_name = pd.Series("other", index=returns.index, dtype="object")
        for column in session_columns:
            session_name.loc[
                decision_features[column].fillna(0.0).astype(float) > 0.0
            ] = column.removeprefix("session_")
        reports["session"] = _group_performance(returns, session_name)

    atr_percentile_cols = [
        column
        for column in decision_features.columns
        if str(column).startswith("atr_percentile_")
    ]
    if atr_percentile_cols:
        values = pd.to_numeric(decision_features[atr_percentile_cols[0]], errors="coerce")
        groups = pd.cut(values, bins=[-np.inf, 1 / 3, 2 / 3, np.inf], labels=["low", "mid", "high"])
        reports["volatility_regime"] = _group_performance(returns, pd.Series(groups, index=returns.index))

    entropy_cols = [
        column for column in decision_features.columns if "entropy_percentile" in str(column)
    ]
    if entropy_cols:
        values = pd.to_numeric(decision_features[entropy_cols[0]], errors="coerce")
        groups = pd.cut(values, bins=[-np.inf, 1 / 3, 2 / 3, np.inf], labels=["organized", "mid", "disorganized"])
        reports["entropy_regime"] = _group_performance(returns, pd.Series(groups, index=returns.index))

    variance_ratio_cols = [
        column
        for column in decision_features.columns
        if str(column).startswith("variance_ratio_")
    ]
    if variance_ratio_cols:
        values = pd.to_numeric(decision_features[variance_ratio_cols[0]], errors="coerce")
        groups = pd.cut(values, bins=[-np.inf, 0.9, 1.1, np.inf], labels=["mean_reverting", "random", "persistent"])
        reports["persistence_regime"] = _group_performance(returns, pd.Series(groups, index=returns.index))

    trades = performance.trades
    assert trades is not None
    if "side" in trades.columns:
        applied_side = pd.Series(trades["side"].astype(str).str.lower().to_numpy(), index=returns.index)
    elif "signal" in trades.columns:
        applied_side = pd.Series(
            np.sign(pd.to_numeric(trades["signal"], errors="coerce").fillna(0.0).to_numpy(dtype=float)),
            index=returns.index,
        ).map({-1.0: "short", 0.0: "flat", 1.0: "long"})
    else:
        applied_side = pd.Series("unknown", index=returns.index, dtype="object")
    reports["side"] = _group_performance(
        returns,
        applied_side,
    )
    return reports


def _sensitivity_rows(
    df: pd.DataFrame,
    *,
    target_meta: dict[str, Any],
    sensitivity_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    if not bool(sensitivity_cfg.get("enabled", False)):
        return []
    horizons = [int(value) for value in sensitivity_cfg.get("horizons", [6, 12, 24])]
    multipliers = [float(value) for value in sensitivity_cfg.get("multipliers", [0.5, 0.75, 1.0, 1.25])]
    asymmetric = list(sensitivity_cfg.get("asymmetric", [{"upper": 1.0, "lower": 0.75}]) or [])
    pairs = [(value, value, "symmetric") for value in multipliers]
    pairs.extend(
        (float(item["upper"]), float(item["lower"]), "asymmetric")
        for item in asymmetric
    )
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        for upper, lower, kind in pairs:
            _, _, _, meta = build_first_passage_barrier_target(
                df,
                {
                    "kind": "first_passage_barrier_multiclass",
                    "horizon_bars": horizon,
                    "upper_atr_multiplier": upper,
                    "lower_atr_multiplier": lower,
                    "atr_period": int(target_meta.get("atr_period", 14)),
                    "atr_col": str(target_meta.get("atr_col", "atr_14")),
                    "entry_delay_bars": int(target_meta.get("entry_delay_bars", 1)),
                    "entry_price_type": str(target_meta.get("entry_price_type", "open")),
                    "ambiguous_policy": "exclude",
                    "use_intrabar_resolution": False,
                    "minimum_barrier_to_cost_ratio": float(
                        target_meta.get("minimum_barrier_to_cost_ratio", 0.0)
                    ),
                    "round_trip_cost": float(target_meta.get("round_trip_cost", 0.0)),
                },
            )
            rows.append(
                {
                    "horizon_bars": horizon,
                    "upper_atr_multiplier": upper,
                    "lower_atr_multiplier": lower,
                    "barrier_kind": kind,
                    "labeled_rows": int(meta.get("labeled_rows", 0)),
                    "ambiguous_rate": meta.get("ambiguous_rate"),
                    "class_rates": dict(meta.get("label_distribution", {}).get("class_rates", {}) or {}),
                }
            )
    return rows


def build_barrier_probability_diagnostics(
    df: pd.DataFrame,
    *,
    model_meta: dict[str, Any],
    performance: BacktestResult,
    diagnostics_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble barrier-specific research tables into the standard evaluation artifact."""
    target_meta = dict(model_meta.get("target", {}) or {})
    if target_meta.get("kind") != "first_passage_barrier_multiclass":
        return {}
    cfg = dict(diagnostics_cfg or {})
    label_col = str(target_meta.get("label_col", "first_passage_label"))
    fwd_col = str(target_meta.get("fwd_col", "first_passage_exit_return"))
    signal_col = str(cfg.get("signal_col", "barrier_ev_signal"))
    oos_col = str(model_meta.get("pred_is_oos_col", "pred_is_oos"))
    oos = df[oos_col].fillna(False).astype(bool) if oos_col in df.columns else pd.Series(False, index=df.index)
    labels = pd.to_numeric(df[label_col], errors="coerce") if label_col in df.columns else pd.Series(np.nan, index=df.index)
    realized_long = pd.to_numeric(df[fwd_col], errors="coerce") if fwd_col in df.columns else pd.Series(np.nan, index=df.index)
    signal = pd.to_numeric(df[signal_col], errors="coerce").fillna(0.0) if signal_col in df.columns else pd.Series(0.0, index=df.index)
    realized_selected = np.sign(signal) * realized_long

    probability_buckets: dict[str, list[dict[str, Any]]] = {}
    for label, column in dict(model_meta.get("class_probability_cols", {}) or {}).items():
        if column not in df.columns:
            continue
        event = (labels == int(label)).astype(float).where(labels.notna())
        probability_buckets[str(label)] = _bucket_summary(df[column].where(oos), event.where(oos))

    expected_edge = (
        pd.to_numeric(df["barrier_expected_edge"], errors="coerce")
        if "barrier_expected_edge" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    selected_ev = (
        pd.to_numeric(df["barrier_ev_selected"], errors="coerce")
        if "barrier_ev_selected" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    return {
        "label_distribution": dict(target_meta.get("label_distribution", {}) or {}),
        "ambiguous": {
            "count": target_meta.get("ambiguous_count"),
            "rate": target_meta.get("ambiguous_rate"),
            "unresolved_count": target_meta.get("unresolved_ambiguous_count"),
            "unresolved_rate": target_meta.get("unresolved_ambiguous_rate"),
            "sensitivity": dict(target_meta.get("sensitivity", {}) or {}),
        },
        "path_distributions": {
            "mfe": dict(target_meta.get("mfe_summary", {}) or {}),
            "mae": dict(target_meta.get("mae_summary", {}) or {}),
            "mfe_atr": dict(target_meta.get("mfe_atr_summary", {}) or {}),
            "mae_atr": dict(target_meta.get("mae_atr_summary", {}) or {}),
            "time_to_first_hit": dict(target_meta.get("time_to_first_hit_summary", {}) or {}),
            "terminal_return": dict(target_meta.get("terminal_return_summary", {}) or {}),
        },
        "calibration": {
            "method": dict(model_meta.get("calibration", {}) or {}).get("method"),
            "raw": dict(model_meta.get("oos_raw_classification_summary", {}) or {}),
            "calibrated": dict(model_meta.get("oos_classification_summary", {}) or {}),
        },
        "probability_buckets": probability_buckets,
        "expected_value_buckets": _bucket_summary(selected_ev.where(oos), realized_selected.where(oos)),
        "predicted_edge_buckets": _bucket_summary(expected_edge.where(oos), realized_selected.where(oos)),
        "oos_selected_realized_return": _numeric_summary(realized_selected.where(oos & signal.ne(0.0))),
        "performance_by_regime": _regime_reports(df, performance),
        "barrier_sensitivity": _sensitivity_rows(
            df,
            target_meta=target_meta,
            sensitivity_cfg=dict(cfg.get("sensitivity_grid", {}) or {}),
        ),
        "folds": [
            {
                "fold": fold.get("fold"),
                "classification_metrics": dict(fold.get("classification_metrics", {}) or {}),
                "raw_classification_metrics": dict(fold.get("raw_classification_metrics", {}) or {}),
                "baseline_metrics": dict(fold.get("baseline_metrics", {}) or {}),
                "train_label_distribution": dict(fold.get("train_label_distribution", {}) or {}),
                "eval_label_distribution": dict(fold.get("eval_label_distribution", {}) or {}),
                "ambiguity": dict(fold.get("ambiguity", {}) or {}),
                "calibration": dict(fold.get("calibration", {}) or {}),
            }
            for fold in list(model_meta.get("folds", []) or [])
        ],
    }


__all__ = ["build_barrier_probability_diagnostics"]
