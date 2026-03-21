from __future__ import annotations

from typing import Any

import pandas as pd

from src.backtesting.engine import BacktestResult
from src.evaluation.metrics import compute_backtest_metrics
from src.experiments.schemas import EvaluationPayload, MonitoringPayload
from src.monitoring.drift import compute_feature_drift
from src.portfolio import PortfolioPerformance


def compute_subset_metrics(
    *,
    net_returns: pd.Series,
    turnover: pd.Series,
    costs: pd.Series,
    gross_returns: pd.Series,
    periods_per_year: int,
    mask: pd.Series,
) -> dict[str, float]:
    aligned_mask = mask.reindex(net_returns.index).fillna(False).astype(bool)
    if not bool(aligned_mask.any()):
        return {}
    return compute_backtest_metrics(
        net_returns=net_returns.loc[aligned_mask],
        periods_per_year=periods_per_year,
        turnover=turnover.loc[aligned_mask],
        costs=costs.loc[aligned_mask],
        gross_returns=gross_returns.loc[aligned_mask],
    )


def build_fold_backtest_summaries(
    *,
    source_index: pd.Index,
    net_returns: pd.Series,
    turnover: pd.Series,
    costs: pd.Series,
    gross_returns: pd.Series,
    periods_per_year: int,
    folds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fold in folds:
        start = int(fold["test_start"])
        end = int(fold["test_end"])
        fold_index = source_index[start:end]
        mask = pd.Series(net_returns.index.isin(fold_index), index=net_returns.index)
        summary = compute_subset_metrics(
            net_returns=net_returns,
            turnover=turnover,
            costs=costs,
            gross_returns=gross_returns,
            periods_per_year=periods_per_year,
            mask=mask,
        )
        out.append(
            {
                "fold": int(fold["fold"]),
                "test_rows": int(fold.get("test_rows", end - start)),
                "metrics": summary,
            }
        )
    return out


def build_single_asset_evaluation(
    asset: str,
    df: pd.DataFrame,
    *,
    performance: BacktestResult,
    model_meta: dict[str, Any],
    periods_per_year: int,
) -> dict[str, Any]:
    evaluation = EvaluationPayload(
        scope="timeline",
        primary_summary=dict(performance.summary),
        timeline_summary=dict(performance.summary),
    ).to_dict()

    if "pred_is_oos" not in df.columns:
        return evaluation

    oos_mask = df["pred_is_oos"].reindex(performance.returns.index).fillna(False).astype(bool)
    oos_summary = compute_subset_metrics(
        net_returns=performance.returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        mask=oos_mask,
    )
    fold_summaries = build_fold_backtest_summaries(
        source_index=df.index,
        net_returns=performance.returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        folds=list(model_meta.get("folds", []) or []),
    )

    return EvaluationPayload(
        scope="strict_oos_only",
        primary_summary=oos_summary or dict(performance.summary),
        timeline_summary=dict(performance.summary),
        oos_only_summary=oos_summary,
        extra={
            "oos_rows": int(oos_mask.sum()),
            "oos_coverage": float(oos_mask.mean()) if len(oos_mask) > 0 else 0.0,
            "fold_backtest_summaries": fold_summaries,
            "model_oos_summary": dict(model_meta.get("oos_classification_summary", {}) or {}),
            "model_oos_regression_summary": dict(model_meta.get("oos_regression_summary", {}) or {}),
            "model_oos_volatility_summary": dict(model_meta.get("oos_volatility_summary", {}) or {}),
            "model_oos_policy_summary": dict(model_meta.get("oos_policy_summary", {}) or {}),
            "asset": asset,
        },
    ).to_dict()


def build_portfolio_evaluation(
    asset_frames: dict[str, pd.DataFrame],
    *,
    performance: PortfolioPerformance,
    model_meta: dict[str, Any],
    periods_per_year: int,
    alignment: str,
) -> dict[str, Any]:
    evaluation = EvaluationPayload(
        scope="timeline",
        primary_summary=dict(performance.summary),
        timeline_summary=dict(performance.summary),
    ).to_dict()

    if not model_meta:
        return evaluation

    oos_by_asset: dict[str, pd.Series] = {}
    if "per_asset" in model_meta:
        for asset in sorted(model_meta["per_asset"]):
            frame = asset_frames.get(asset)
            if frame is not None and "pred_is_oos" in frame.columns:
                oos_by_asset[asset] = frame["pred_is_oos"].astype(float)
    elif "pred_is_oos" in next(iter(asset_frames.values())).columns:
        only_asset = next(iter(sorted(asset_frames)))
        oos_by_asset[only_asset] = asset_frames[only_asset]["pred_is_oos"].astype(float)

    if not oos_by_asset:
        return evaluation

    oos_df = pd.concat(oos_by_asset, axis=1, join=alignment).sort_index()
    if isinstance(oos_df.columns, pd.MultiIndex):
        oos_df.columns = oos_df.columns.get_level_values(0)
    oos_mask = oos_df.reindex(performance.net_returns.index).fillna(0.0).astype(bool).all(axis=1)
    oos_summary = compute_subset_metrics(
        net_returns=performance.net_returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        mask=oos_mask,
    )
    return EvaluationPayload(
        scope="strict_oos_only",
        primary_summary=oos_summary or dict(performance.summary),
        timeline_summary=dict(performance.summary),
        oos_only_summary=oos_summary,
        extra={
            "oos_active_dates": int(oos_mask.sum()),
            "oos_date_coverage": float(oos_mask.mean()) if len(oos_mask) > 0 else 0.0,
            "model_oos_summary": dict(model_meta.get("oos_classification_summary", {}) or {}),
            "model_oos_regression_summary": dict(model_meta.get("oos_regression_summary", {}) or {}),
            "model_oos_volatility_summary": dict(model_meta.get("oos_volatility_summary", {}) or {}),
            "model_oos_policy_summary": dict(model_meta.get("oos_policy_summary", {}) or {}),
            "folds_by_asset": {
                asset: list(meta.get("folds", []) or [])
                for asset, meta in dict(model_meta.get("per_asset", {}) or {}).items()
            },
        },
    ).to_dict()


def compute_monitoring_for_asset(
    df: pd.DataFrame,
    *,
    meta: dict[str, Any],
    monitoring_cfg: dict[str, Any],
) -> dict[str, Any] | None:
    feature_cols = list(meta.get("feature_cols", []) or [])
    if not feature_cols or "pred_is_oos" not in df.columns:
        return None

    oos_mask = df["pred_is_oos"].astype(bool)
    ref = df.loc[~oos_mask, feature_cols]
    cur = df.loc[oos_mask, feature_cols]
    if ref.empty or cur.empty:
        return None

    return compute_feature_drift(
        ref,
        cur,
        feature_cols=feature_cols,
        psi_threshold=float(monitoring_cfg.get("psi_threshold", 0.2)),
        n_bins=int(monitoring_cfg.get("n_bins", 10)),
    )


def compute_monitoring_report(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_meta: dict[str, Any],
    monitoring_cfg: dict[str, Any],
) -> dict[str, Any]:
    if not bool(monitoring_cfg.get("enabled", False)):
        return {}

    per_asset: dict[str, Any] = {}
    if "per_asset" in model_meta:
        for asset, meta in sorted(dict(model_meta.get("per_asset", {}) or {}).items()):
            report = compute_monitoring_for_asset(
                asset_frames[asset],
                meta=meta,
                monitoring_cfg=monitoring_cfg,
            )
            if report:
                per_asset[asset] = report
    elif model_meta:
        only_asset = next(iter(sorted(asset_frames)))
        report = compute_monitoring_for_asset(
            asset_frames[only_asset],
            meta=model_meta,
            monitoring_cfg=monitoring_cfg,
        )
        if report:
            per_asset[only_asset] = report

    if not per_asset:
        return {}

    return MonitoringPayload(
        asset_count=int(len(per_asset)),
        drifted_feature_count=int(
            sum(int(report.get("drifted_feature_count", 0)) for report in per_asset.values())
        ),
        feature_count=int(sum(int(report.get("feature_count", 0)) for report in per_asset.values())),
        per_asset=per_asset,
    ).to_dict()


__all__ = [
    "build_fold_backtest_summaries",
    "build_portfolio_evaluation",
    "build_single_asset_evaluation",
    "compute_monitoring_for_asset",
    "compute_monitoring_report",
    "compute_subset_metrics",
]
