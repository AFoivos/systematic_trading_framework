from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.backtesting.engine import BacktestResult
from src.evaluation.model_diagnostics import (
    build_dense_forecast_diagnostic_frames,
    write_dense_diagnostic_plots,
)
from src.evaluation.trade_path_diagnostics import (
    build_trade_ledger_from_position_transitions,
    build_trade_paths,
    enrich_trade_lifecycle_columns,
    simulate_counterfactual_exits,
    summarize_probability_trade_quality,
    summarize_trade_lifecycle,
)
from src.experiments.orchestration.common import data_stats_payload, redact_sensitive_values, resolved_feature_columns
from src.experiments.orchestration.reporting import build_experiment_report_markdown
from src.experiments.support.execution_source_audit import write_execution_source_audit
from src.plots.trade_diagnostics import (
    build_trade_event_frame,
)
from src.portfolio import PortfolioPerformance
from src.utils.run_metadata import build_artifact_manifest

_FORECASTER_MODEL_KINDS = {
    "sarimax_forecaster",
    "garch_forecaster",
    "lstm_forecaster",
    "patchtst_forecaster",
    "tft_forecaster",
    "chronos_bolt_forecaster",
    "chronos_2_forecaster",
    "timesfm_2p5_200m_forecaster",
    "timesfm_1p0_200m_forecaster",
    "lightgbm_regressor",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping at {path}")
    return payload


def _read_numeric_timeseries(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame()
    index_col = df.columns[0]
    index_values = pd.to_datetime(df[index_col], errors="coerce")
    if float(index_values.notna().mean()) >= 0.8:
        df = df.drop(columns=[index_col])
        df.index = index_values
        df.index.name = index_col
    numeric = df.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.loc[:, numeric.notna().any(axis=0)]
    return numeric.sort_index()


def _first_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    if frame.shape[1] == 1:
        series = frame.iloc[:, 0]
    else:
        series = frame.iloc[:, 0]
    return series.astype(float)


def _returns_to_curve(returns: pd.Series, *, returns_type: str) -> pd.Series:
    series = returns.fillna(0.0).astype(float)
    if returns_type == "log":
        values = np.exp(series.cumsum().to_numpy()) - 1.0
    else:
        values = (1.0 + series).cumprod().to_numpy() - 1.0
    return pd.Series(values, index=series.index, name=series.name)


def _drawdown_from_equity(equity_curve: pd.Series) -> pd.Series:
    if equity_curve.empty:
        return pd.Series(dtype=float)
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    drawdown.name = "drawdown"
    return drawdown.astype(float)


def _rolling_window_length(series: pd.Series, *, default: int = 48) -> int:
    if series.empty:
        return default
    return max(8, min(default, max(len(series) // 4, 8)))


def _ensure_matplotlib_backend(run_dir: Path) -> None:
    mpl_dir = run_dir / ".mplconfig"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(mpl_dir)
    import matplotlib

    matplotlib.use("Agg", force=True)


def _save_line_chart(
    path: Path,
    *,
    title: str,
    ylabel: str,
    series_map: dict[str, pd.Series],
) -> None:
    _ensure_matplotlib_backend(path.parent.parent)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 4))
    for label, series in series_map.items():
        if series.empty:
            continue
        ax.plot(series.index, series.to_numpy(), label=label, linewidth=1.6)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.3)
    if len(series_map) > 1:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _save_histogram_chart(
    path: Path,
    *,
    title: str,
    xlabel: str,
    series_map: dict[str, pd.Series],
    bins: int = 40,
) -> None:
    _ensure_matplotlib_backend(path.parent.parent)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4))
    plotted = False
    for label, series in series_map.items():
        values = series.dropna().astype(float)
        if values.empty:
            continue
        ax.hist(values.to_numpy(), bins=bins, alpha=0.55, label=label, density=False)
        plotted = True
    if not plotted:
        plt.close(fig)
        return
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Count")
    ax.grid(alpha=0.25)
    if len(series_map) > 1:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _save_dual_panel_chart(
    path: Path,
    *,
    top_title: str,
    bottom_title: str,
    top_series: pd.Series,
    bottom_series: pd.Series,
    top_ylabel: str,
    bottom_ylabel: str,
) -> None:
    _ensure_matplotlib_backend(path.parent.parent)
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    axes[0].plot(top_series.index, top_series.to_numpy(), linewidth=1.5)
    axes[0].set_title(top_title)
    axes[0].set_ylabel(top_ylabel)
    axes[0].grid(alpha=0.3)
    axes[1].plot(bottom_series.index, bottom_series.to_numpy(), linewidth=1.5, color="tab:orange")
    axes[1].set_title(bottom_title)
    axes[1].set_ylabel(bottom_ylabel)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _save_monthly_bar_chart(path: Path, *, net_returns: pd.Series, gross_returns: pd.Series) -> None:
    _ensure_matplotlib_backend(path.parent.parent)
    import matplotlib.pyplot as plt

    monthly = pd.DataFrame({"net": net_returns, "gross": gross_returns}).copy()
    monthly["month"] = monthly.index.to_period("M").astype(str)
    grouped = monthly.groupby("month")[["net", "gross"]].sum()
    if grouped.empty:
        return

    x = np.arange(len(grouped))
    width = 0.38
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.bar(x - width / 2, grouped["gross"].to_numpy(), width=width, label="gross")
    ax.bar(x + width / 2, grouped["net"].to_numpy(), width=width, label="net")
    ax.set_xticks(x)
    ax.set_xticklabels(grouped.index.tolist(), rotation=30, ha="right")
    ax.set_title("Monthly Gross vs Net Returns")
    ax.set_ylabel("Return")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _save_fold_bar_chart(path: Path, *, fold_summaries: list[dict[str, Any]]) -> None:
    if not fold_summaries:
        return
    _ensure_matplotlib_backend(path.parent.parent)
    import matplotlib.pyplot as plt

    folds = [int(item.get("fold", idx)) for idx, item in enumerate(fold_summaries)]
    net_pnl = [float(dict(item.get("metrics", {}) or {}).get("net_pnl", 0.0) or 0.0) for item in fold_summaries]
    colors = ["tab:green" if value >= 0 else "tab:red" for value in net_pnl]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([str(fold) for fold in folds], net_pnl, color=colors)
    ax.set_title("Fold Net PnL")
    ax.set_ylabel("Net PnL")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _save_fold_metric_bar_chart(
    path: Path,
    *,
    rows: list[dict[str, Any]],
    metric: str,
    title: str,
    ylabel: str,
) -> None:
    if not rows:
        return
    _ensure_matplotlib_backend(path.parent.parent)
    import matplotlib.pyplot as plt

    folds = [str(int(row.get("fold", idx))) for idx, row in enumerate(rows)]
    values = [float(row.get(metric, 0.0) or 0.0) for row in rows]
    colors = ["tab:green" if value >= 0 else "tab:red" for value in values]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(folds, values, color=colors)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _save_horizontal_bar_chart(
    path: Path,
    *,
    title: str,
    xlabel: str,
    labels: list[str],
    values: list[float],
) -> None:
    if not labels or not values:
        return
    _ensure_matplotlib_backend(path.parent.parent)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.35 * len(labels))))
    y = np.arange(len(labels))
    ax.barh(y, values, color="tab:blue")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _save_category_bar_chart(
    path: Path,
    *,
    title: str,
    xlabel: str,
    ylabel: str,
    categories: list[str],
    values: list[float],
) -> None:
    if not categories or not values:
        return
    _ensure_matplotlib_backend(path.parent.parent)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(categories, values, color="tab:purple")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _save_rolling_line_chart(
    path: Path,
    *,
    title: str,
    ylabel: str,
    series_map: dict[str, pd.Series],
    window: int,
) -> None:
    rolled = {
        label: series.astype(float).rolling(window, min_periods=max(3, window // 4)).sum()
        for label, series in series_map.items()
        if not series.empty
    }
    if not rolled:
        return
    _save_line_chart(path, title=title, ylabel=ylabel, series_map=rolled)


def _save_portfolio_exposure_chart(path: Path, *, weights: pd.DataFrame) -> None:
    if weights.empty:
        return
    gross = weights.abs().sum(axis=1).astype(float)
    net = weights.sum(axis=1).astype(float)
    _save_dual_panel_chart(
        path,
        top_title="Portfolio Gross Exposure",
        bottom_title="Portfolio Net Exposure",
        top_series=gross,
        bottom_series=net,
        top_ylabel="Gross",
        bottom_ylabel="Net",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def _write_dense_forecast_diagnostic_artifacts(
    *,
    run_dir: Path,
    data: pd.DataFrame | dict[str, pd.DataFrame],
    cfg: dict[str, Any],
    performance: BacktestResult | PortfolioPerformance,
    model_meta: dict[str, Any],
    portfolio_weights: pd.DataFrame | None,
) -> dict[str, str]:
    diagnostics_cfg = dict(cfg.get("diagnostics", {}) or {})
    if not bool(diagnostics_cfg.get("enabled", False)):
        return {}
    model_kind = str(dict(cfg.get("model", {}) or {}).get("kind", "none"))
    strategy_name = str(dict(cfg.get("strategy", {}) or {}).get("name", ""))
    if model_kind not in _FORECASTER_MODEL_KINDS and strategy_name != "dense_return_forecasting_v2":
        return {}

    if isinstance(data, dict):
        asset_frames = {str(asset): frame for asset, frame in sorted(data.items())}
    else:
        data_cfg = dict(cfg.get("data", {}) or {})
        asset = str(data_cfg.get("symbol") or next(iter(data_cfg.get("symbols", []) or ["asset"])))
        asset_frames = {asset: data}

    diagnostics_dir = run_dir / "artifacts" / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(performance, BacktestResult):
        net_returns = performance.returns
    else:
        net_returns = performance.net_returns

    frames = build_dense_forecast_diagnostic_frames(
        asset_frames,
        model_meta=model_meta,
        portfolio_weights=portfolio_weights,
        net_returns=net_returns,
        gross_returns=performance.gross_returns,
        costs=performance.costs,
        turnover=performance.turnover,
        cfg=cfg,
    )
    artifact_paths: dict[str, str] = {}

    table_specs = {
        "prediction_distribution": frames.get("prediction_frame"),
        "prediction_metrics": frames.get("prediction_metrics"),
        "prediction_quantiles": frames.get("prediction_quantiles"),
        "prediction_autocorrelation": frames.get("prediction_autocorrelation"),
        "regime_diagnostics": frames.get("regime_diagnostics"),
    }
    shap_summary, shap_sample, shap_per_prediction = frames.get(
        "shap",
        (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
    )
    table_specs.update(
        {
            "shap_feature_importance": shap_summary,
            "shap_values_sample": shap_sample,
            "shap_per_prediction": shap_per_prediction,
            "shap_status": frames.get("shap_status"),
            "lightgbm_importance": frames.get("lightgbm_importance"),
        }
    )
    turnover_cost = dict(frames.get("turnover_cost", {}) or {})
    turnover_ts = turnover_cost.get("timeseries")
    if isinstance(turnover_ts, pd.DataFrame):
        table_specs["turnover_cost_timeseries"] = turnover_ts

    for name, table in table_specs.items():
        if isinstance(table, pd.DataFrame) and not table.empty:
            path = diagnostics_dir / f"{name}.csv"
            table.to_csv(path, index=True if name == "turnover_cost_timeseries" else False)
            artifact_paths[f"diagnostics_{name}"] = str(path.relative_to(run_dir))

    summary_path = diagnostics_dir / "summary.json"
    summary_payload = dict(frames.get("summary", {}) or {})
    summary_payload["turnover_cost"] = dict(turnover_cost.get("summary", {}) or {})
    summary_payload["residual_diagnostics"] = dict(frames.get("residual_diagnostics", {}) or {})
    _write_json(summary_path, summary_payload)
    artifact_paths["diagnostics_summary"] = str(summary_path.relative_to(run_dir))

    chart_paths = write_dense_diagnostic_plots(diagnostics_dir, frames)
    for label, path in chart_paths.items():
        artifact_paths[f"diagnostics_{label}"] = str(path.relative_to(run_dir))
    return artifact_paths


def _selected_feature_detail_rows(model_meta: dict[str, Any]) -> list[dict[str, Any]]:
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    if per_asset_meta:
        rows: list[dict[str, Any]] = []
        for asset, asset_meta in sorted(per_asset_meta.items()):
            feature_selection = dict(asset_meta.get("feature_selection", {}) or {})
            for row in list(feature_selection.get("selected_feature_details", []) or []):
                rows.append({"asset": str(asset)} | dict(row or {}))
        return rows

    feature_selection = dict(model_meta.get("feature_selection", {}) or {})
    return [dict(row or {}) for row in list(feature_selection.get("selected_feature_details", []) or [])]


def _fold_selected_feature_rows(model_meta: dict[str, Any]) -> list[dict[str, Any]]:
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    if per_asset_meta:
        rows: list[dict[str, Any]] = []
        for asset, asset_meta in sorted(per_asset_meta.items()):
            for fold in list(asset_meta.get("folds", []) or []):
                for row in list(fold.get("selected_features", []) or []):
                    rows.append(
                        {
                            "asset": str(asset),
                            "fold": int(fold.get("fold", 0)),
                        }
                        | dict(row or {})
                    )
        return rows

    rows = []
    for fold in list(model_meta.get("folds", []) or []):
        for row in list(fold.get("selected_features", []) or []):
            rows.append({"fold": int(fold.get("fold", 0))} | dict(row or {}))
    return rows


def _extracted_feature_detail_rows(model_meta: dict[str, Any]) -> list[dict[str, Any]]:
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    if per_asset_meta:
        rows: list[dict[str, Any]] = []
        for asset, asset_meta in sorted(per_asset_meta.items()):
            feature_selection = dict(asset_meta.get("feature_selection", {}) or {})
            for row in list(feature_selection.get("extracted_feature_details", []) or []):
                rows.append({"asset": str(asset)} | dict(row or {}))
        return rows

    feature_selection = dict(model_meta.get("feature_selection", {}) or {})
    return [dict(row or {}) for row in list(feature_selection.get("extracted_feature_details", []) or [])]


def _dropped_feature_detail_rows(model_meta: dict[str, Any]) -> list[dict[str, Any]]:
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    if per_asset_meta:
        rows: list[dict[str, Any]] = []
        for asset, asset_meta in sorted(per_asset_meta.items()):
            feature_selection = dict(asset_meta.get("feature_selection", {}) or {})
            for row in list(feature_selection.get("dropped_feature_details", []) or []):
                rows.append({"asset": str(asset)} | dict(row or {}))
        return rows

    feature_selection = dict(model_meta.get("feature_selection", {}) or {})
    return [dict(row or {}) for row in list(feature_selection.get("dropped_feature_details", []) or [])]


def _fold_feature_cleaning_rows(model_meta: dict[str, Any]) -> list[dict[str, Any]]:
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    if per_asset_meta:
        rows: list[dict[str, Any]] = []
        for asset, asset_meta in sorted(per_asset_meta.items()):
            feature_selection = dict(asset_meta.get("feature_selection", {}) or {})
            for row in list(feature_selection.get("fold_feature_cleaning", []) or []):
                rows.append({"asset": str(asset)} | dict(row or {}))
        return rows

    feature_selection = dict(model_meta.get("feature_selection", {}) or {})
    return [dict(row or {}) for row in list(feature_selection.get("fold_feature_cleaning", []) or [])]


def _tsfresh_feature_dataset_rows(
    frame: pd.DataFrame,
    *,
    feature_name_prefixes: list[str],
    label_col: str,
    label_code_col: str,
    eligible_col: str,
) -> pd.DataFrame:
    prefix_tokens = tuple(f"{prefix}__" for prefix in feature_name_prefixes if str(prefix).strip())
    feature_cols = [
        col
        for col in frame.columns
        if prefix_tokens and any(str(col).startswith(token) for token in prefix_tokens)
    ]
    if not feature_cols or eligible_col not in frame.columns:
        return pd.DataFrame()

    eligible_mask = frame[eligible_col].fillna(False).astype(bool)
    if not bool(eligible_mask.any()):
        return pd.DataFrame()

    export_cols = [
        col
        for col in frame.columns
        if col in {"open", "high", "low", "close", "volume", label_col, label_code_col, eligible_col}
        or col in feature_cols
    ]
    export_frame = frame.loc[eligible_mask, export_cols].copy()
    export_frame.index.name = frame.index.name or "datetime"
    return export_frame.reset_index()


def _write_tsfresh_feature_dataset_artifacts(
    *,
    run_dir: Path,
    data: pd.DataFrame | dict[str, pd.DataFrame],
    model_meta: dict[str, Any],
) -> dict[str, str]:
    feature_dataset_meta = dict(model_meta.get("feature_dataset", {}) or {})
    if not bool(feature_dataset_meta.get("available", False)):
        return {}

    if isinstance(data, dict):
        return {}

    feature_name_prefixes = [str(value) for value in list(feature_dataset_meta.get("feature_name_prefixes", []) or [])]
    label_col = str(feature_dataset_meta.get("label_col", "tsfresh_extrema_label"))
    label_code_col = str(feature_dataset_meta.get("label_code_col", "tsfresh_extrema_label_code"))
    eligible_col = str(feature_dataset_meta.get("eligible_col", "tsfresh_extrema_eligible"))
    export_frame = _tsfresh_feature_dataset_rows(
        data,
        feature_name_prefixes=feature_name_prefixes,
        label_col=label_col,
        label_code_col=label_code_col,
        eligible_col=eligible_col,
    )
    if export_frame.empty:
        return {}

    artifact_paths: dict[str, str] = {}
    run_dir.mkdir(parents=True, exist_ok=True)
    run_copy_path = run_dir / "tsfresh_feature_dataset.csv"
    export_frame.to_csv(run_copy_path, index=False)
    artifact_paths["tsfresh_feature_dataset"] = str(run_copy_path.relative_to(run_dir))

    if bool(feature_dataset_meta.get("export_enabled", False)):
        raw_export_path = feature_dataset_meta.get("export_dataset_path")
        if isinstance(raw_export_path, str) and raw_export_path.strip():
            external_path = Path(raw_export_path)
            if not external_path.is_absolute():
                external_path = Path.cwd() / external_path
            external_path.parent.mkdir(parents=True, exist_ok=True)
            export_frame.to_csv(external_path, index=False)
            artifact_paths["tsfresh_feature_dataset_export"] = str(external_path.resolve())

    return artifact_paths


def _write_model_diagnostic_artifacts(
    *,
    run_dir: Path,
    model_meta: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    chart_paths: dict[str, str] = {}
    artifact_paths: dict[str, str] = {}
    report_assets_dir = run_dir / "report_assets"
    report_assets_dir.mkdir(parents=True, exist_ok=True)

    feature_importance = dict(model_meta.get("feature_importance", {}) or {})
    top_features = list(feature_importance.get("top_features", []) or [])
    if top_features:
        feature_importance_path = run_dir / "feature_importance.csv"
        pd.DataFrame(top_features).to_csv(feature_importance_path, index=False)
        artifact_paths["feature_importance"] = str(feature_importance_path.relative_to(run_dir))

        feature_chart_path = report_assets_dir / "feature_importance.png"
        _save_horizontal_bar_chart(
            feature_chart_path,
            title="Feature Importance",
            xlabel="Mean Importance",
            labels=[str(row.get("feature")) for row in top_features],
            values=[float(row.get("mean_importance", row.get("importance", 0.0)) or 0.0) for row in top_features],
        )
        if feature_chart_path.exists():
            chart_paths["feature_importance_chart"] = str(feature_chart_path.relative_to(run_dir))

    selected_feature_rows = _selected_feature_detail_rows(model_meta)
    if selected_feature_rows:
        selected_features_path = run_dir / "selected_features.csv"
        pd.DataFrame(selected_feature_rows).to_csv(selected_features_path, index=False)
        artifact_paths["selected_features"] = str(selected_features_path.relative_to(run_dir))

    fold_selected_feature_rows = _fold_selected_feature_rows(model_meta)
    if fold_selected_feature_rows:
        fold_selected_features_path = run_dir / "fold_selected_features.csv"
        pd.DataFrame(fold_selected_feature_rows).to_csv(fold_selected_features_path, index=False)
        artifact_paths["fold_selected_features"] = str(fold_selected_features_path.relative_to(run_dir))

    extracted_feature_rows = _extracted_feature_detail_rows(model_meta)
    if extracted_feature_rows:
        extracted_features_path = run_dir / "extracted_features.csv"
        pd.DataFrame(extracted_feature_rows).to_csv(extracted_features_path, index=False)
        artifact_paths["extracted_features"] = str(extracted_features_path.relative_to(run_dir))

    dropped_feature_rows = _dropped_feature_detail_rows(model_meta)
    if dropped_feature_rows:
        dropped_features_path = run_dir / "dropped_features.csv"
        pd.DataFrame(dropped_feature_rows).to_csv(dropped_features_path, index=False)
        artifact_paths["dropped_features"] = str(dropped_features_path.relative_to(run_dir))

    fold_feature_cleaning_rows = _fold_feature_cleaning_rows(model_meta)
    if fold_feature_cleaning_rows:
        fold_feature_cleaning_path = run_dir / "fold_feature_cleaning.csv"
        pd.DataFrame(fold_feature_cleaning_rows).to_csv(fold_feature_cleaning_path, index=False)
        artifact_paths["fold_feature_cleaning"] = str(fold_feature_cleaning_path.relative_to(run_dir))

    target_meta = dict(model_meta.get("target", {}) or {})
    target_label_distribution = dict(target_meta.get("label_distribution", {}) or {})
    if target_label_distribution:
        target_label_path = run_dir / "target_label_distribution.csv"
        class_counts = dict(target_label_distribution.get("class_counts", {}) or {})
        pd.DataFrame(
            [
                {
                    "label": label,
                    "count": int(count),
                    "positive_rate": target_label_distribution.get("positive_rate"),
                }
                for label, count in sorted(class_counts.items())
            ]
        ).to_csv(target_label_path, index=False)
        artifact_paths["target_label_distribution"] = str(target_label_path.relative_to(run_dir))

    target_exit_counts = dict(target_meta.get("exit_reason_counts", {}) or {})
    if target_exit_counts:
        target_exit_path = run_dir / "target_exit_reason_counts.csv"
        pd.DataFrame(
            [{"exit_reason": reason, "count": int(count)} for reason, count in sorted(target_exit_counts.items())]
        ).to_csv(target_exit_path, index=False)
        artifact_paths["target_exit_reason_counts"] = str(target_exit_path.relative_to(run_dir))

    winner_loser = dict(target_meta.get("winner_loser_feature_summary", {}) or {})
    if winner_loser:
        winner_loser_path = run_dir / "target_winner_loser_features.csv"
        pd.DataFrame(
            [dict(payload or {}) | {"feature": feature} for feature, payload in sorted(winner_loser.items())]
        ).to_csv(winner_loser_path, index=False)
        artifact_paths["target_winner_loser_features"] = str(winner_loser_path.relative_to(run_dir))

    label_distribution = dict(model_meta.get("label_distribution", {}) or {})
    label_rows: list[dict[str, Any]] = []
    label_counts = dict(dict(label_distribution.get("oos_evaluation", {}) or {}).get("class_counts", {}) or {})
    if not label_counts:
        label_counts = dict(dict(label_distribution.get("full_target", {}) or {}).get("class_counts", {}) or {})
    if not label_counts:
        label_counts = dict(target_label_distribution.get("class_counts", {}) or {})
    for section, payload in sorted(label_distribution.items()):
        payload_dict = dict(payload or {})
        for label, count in dict(payload_dict.get("class_counts", {}) or {}).items():
            label_rows.append({"section": section, "label": label, "count": int(count)})
    if not label_rows and target_label_distribution:
        for label, count in dict(target_label_distribution.get("class_counts", {}) or {}).items():
            label_rows.append({"section": "target", "label": label, "count": int(count)})
    if label_rows:
        label_path = run_dir / "label_distribution.csv"
        pd.DataFrame(label_rows).to_csv(label_path, index=False)
        artifact_paths["label_distribution"] = str(label_path.relative_to(run_dir))
        if label_counts:
            label_chart_path = report_assets_dir / "label_distribution.png"
            categories = list(sorted(label_counts))
            _save_category_bar_chart(
                label_chart_path,
                title="OOS Label Distribution",
                xlabel="Label",
                ylabel="Count",
                categories=categories,
                values=[float(label_counts[label]) for label in categories],
            )
            if label_chart_path.exists():
                chart_paths["label_distribution_chart"] = str(label_chart_path.relative_to(run_dir))

    prediction_diagnostics = dict(model_meta.get("prediction_diagnostics", {}) or {})
    if prediction_diagnostics:
        prediction_path = run_dir / "prediction_diagnostics.json"
        _write_json(prediction_path, prediction_diagnostics)
        artifact_paths["prediction_diagnostics"] = str(prediction_path.relative_to(run_dir))

    missing_value_diagnostics = dict(model_meta.get("missing_value_diagnostics", {}) or {})
    if missing_value_diagnostics:
        missing_path = run_dir / "missing_value_diagnostics.json"
        _write_json(missing_path, missing_value_diagnostics)
        artifact_paths["missing_value_diagnostics"] = str(missing_path.relative_to(run_dir))

    model_folds = list(model_meta.get("folds", []) or [])
    if model_folds:
        rows: list[dict[str, Any]] = []
        for fold in model_folds:
            classification = dict(fold.get("classification_metrics", {}) or {})
            regression = dict(fold.get("regression_metrics", {}) or {})
            rows.append(
                {
                    "fold": int(fold.get("fold", 0)),
                    "train_rows_raw": fold.get("train_rows_raw"),
                    "train_rows": fold.get("train_rows"),
                    "train_rows_dropped_missing": fold.get("train_rows_dropped_missing"),
                    "train_rows_not_labeled": fold.get("train_rows_not_labeled", 0),
                    "train_rows_without_fit": fold.get(
                        "train_rows_without_fit",
                        fold.get("train_rows_dropped_missing", 0),
                    ),
                    "test_rows": fold.get("test_rows"),
                    "test_pred_rows": fold.get("test_pred_rows"),
                    "test_rows_missing_features": fold.get("test_rows_missing_features", 0),
                    "test_rows_not_candidates": fold.get("test_rows_not_candidates", 0),
                    "test_rows_without_prediction": fold.get(
                        "test_rows_without_prediction",
                        fold.get("test_rows_missing_features", 0),
                    ),
                    "classification_eval_rows": classification.get("evaluation_rows"),
                    "regression_eval_rows": regression.get("evaluation_rows"),
                    "classification_accuracy": classification.get("accuracy"),
                    "regression_rmse": regression.get("rmse"),
                }
            )
        fold_path = run_dir / "fold_model_summary.csv"
        pd.DataFrame(rows).to_csv(fold_path, index=False)
        artifact_paths["fold_model_summary"] = str(fold_path.relative_to(run_dir))

        coverage_chart_path = report_assets_dir / "prediction_coverage_by_fold.png"
        categories = [str(int(row["fold"])) for row in rows]
        values = [
            float(row["test_pred_rows"] or 0.0) / max(float(row["test_rows"] or 0.0), 1.0)
            for row in rows
        ]
        _save_category_bar_chart(
            coverage_chart_path,
            title="Prediction Coverage By Fold",
            xlabel="Fold",
            ylabel="Coverage",
            categories=categories,
            values=values,
        )
        if coverage_chart_path.exists():
            chart_paths["prediction_coverage_by_fold"] = str(coverage_chart_path.relative_to(run_dir))

    return chart_paths, artifact_paths


def _write_forecast_alpha_diagnostic_artifacts(
    *,
    run_dir: Path,
    evaluation: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    report_assets_dir = run_dir / "report_assets"
    diagnostics_dir = run_dir / "artifacts" / "diagnostics"
    report_assets_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: dict[str, str] = {}
    artifact_paths: dict[str, str] = {}

    table_sections = {
        "forecast_baselines": "forecast_baselines.csv",
        "threshold_grid": "threshold_grid.csv",
        "regime_performance": "regime_performance.csv",
    }
    for key, filename in table_sections.items():
        rows = list(dict(evaluation.get(key, {}) or {}).get("rows", []) or [])
        if rows:
            path = diagnostics_dir / filename
            pd.DataFrame(rows).to_csv(path, index=False)
            artifact_paths[key] = str(path.relative_to(run_dir))

    fold_payload = dict(evaluation.get("fold_backtest_diagnostics", {}) or {})
    fold_rows = list(fold_payload.get("rows", []) or [])
    if fold_rows:
        fold_path = diagnostics_dir / "fold_backtest_diagnostics.csv"
        pd.DataFrame(fold_rows).to_csv(fold_path, index=False)
        artifact_paths["fold_backtest_diagnostics"] = str(fold_path.relative_to(run_dir))

        for metric, title, ylabel, filename in (
            ("cumulative_return", "Fold Cumulative Return", "Return", "fold_cumulative_return.png"),
            ("sharpe", "Fold Sharpe", "Sharpe", "fold_sharpe.png"),
            ("cost_to_gross_pnl", "Fold Cost / Gross PnL", "Cost / Gross PnL", "fold_cost_to_gross_pnl.png"),
        ):
            chart_path = report_assets_dir / filename
            _save_fold_metric_bar_chart(
                chart_path,
                rows=fold_rows,
                metric=metric,
                title=title,
                ylabel=ylabel,
            )
            if chart_path.exists():
                chart_paths[filename.removesuffix(".png")] = str(chart_path.relative_to(run_dir))

    summary_sections = {
        key: dict(evaluation.get(key, {}) or {}).get("summary")
        or dict(evaluation.get(key, {}) or {}).get("best_by_sharpe")
        for key in (
            "fold_backtest_diagnostics",
            "threshold_grid",
            "forecast_baselines",
            "regime_performance",
        )
        if evaluation.get(key)
    }
    if summary_sections:
        summary_path = diagnostics_dir / "forecast_alpha_diagnostics_summary.json"
        _write_json(summary_path, {"sections": summary_sections})
        artifact_paths["forecast_alpha_diagnostics_summary"] = str(summary_path.relative_to(run_dir))
    return chart_paths, artifact_paths


def _safe_asset_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value))
    return safe.strip("_") or "asset"


def _coerce_diagnostic_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        for timestamp_col in ("timestamp", "datetime", "date"):
            if timestamp_col in out.columns:
                timestamp = pd.to_datetime(out[timestamp_col], errors="coerce")
                if float(timestamp.notna().mean()) >= 0.8:
                    out = out.loc[timestamp.notna()].copy()
                    out.index = pd.DatetimeIndex(timestamp.loc[timestamp.notna()])
                    out.index.name = timestamp_col
                    break
    return out.sort_index()


def _asset_frames_for_trade_diagnostics(
    data: pd.DataFrame | dict[str, pd.DataFrame],
    cfg: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    if isinstance(data, dict):
        return {str(asset): _coerce_diagnostic_frame(frame) for asset, frame in sorted(data.items())}

    data_cfg = dict(cfg.get("data", {}) or {})
    symbols = data_cfg.get("symbols")
    if isinstance(symbols, list) and len(symbols) == 1:
        asset = str(symbols[0])
    else:
        asset = str(data_cfg.get("symbol") or "asset")
    return {asset: _coerce_diagnostic_frame(data)}


def _positions_for_trade_diagnostics(
    *,
    asset_frames: dict[str, pd.DataFrame],
    performance: BacktestResult | PortfolioPerformance,
    portfolio_weights: pd.DataFrame | None,
) -> dict[str, pd.Series]:
    if isinstance(performance, BacktestResult):
        asset = next(iter(asset_frames), "asset")
        return {asset: performance.positions.astype(float)}

    weights = portfolio_weights
    if weights is None and performance.applied_weights is not None:
        weights = performance.applied_weights
    if weights is None or weights.empty:
        return {}
    return {
        str(asset): weights[str(asset)].astype(float)
        for asset in weights.columns
        if str(asset) in asset_frames
    }


_LAB_RAW_MARKET_COLUMNS = {
    "open",
    "high",
    "low",
    "close",
    "volume",
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
    "spread_close",
    "spread_bps",
}
_LAB_EXCLUDED_COLUMNS = {
    "timestamp",
    "datetime",
    "date",
    "asset",
    "label",
    "target",
    "position",
    "positions",
    "entry",
    "exit",
    "eda_flat_signal",
    "manual_long_signal",
    "manual_long_candidate",
    "manual_vol_adjusted_signal",
    "manual_vol_adjusted_candidate",
    "manual_all_conditions_signal",
    "short_signal",
    "combined_signal",
    "strategy_equity",
    "strategy_net_returns",
    "strategy_gross_returns",
    "strategy_costs",
    "strategy_positions",
    "strategy_turnover",
    "strategy_drawdown",
    "oos_mask",
    "pred_is_oos",
}
_LAB_EXCLUDED_PREFIXES = (
    "signal_",
    "pred_",
    "stage",
    "target_",
    "r_target_",
    "tb_",
    "strategy_",
    "shock_side_",
)
_SIGNAL_PARAM_COLUMN_KEYS = {
    "signal_col",
    "long_signal_col",
    "short_signal_col",
    "combined_signal_col",
    "vol_adjusted_col",
    "all_conditions_col",
}
_LAB_PRICE_OVERLAY_EXACT_COLUMNS = {
    "pivot_high_confirmed",
    "pivot_low_confirmed",
    "sr_v2_resistance_level",
    "sr_v2_support_level",
    "orb_range_high",
    "orb_range_low",
    "orb_range_mid",
    "orb_breakout_price",
}


def _enabled_catalog_item_exists(cfg: dict[str, Any], key: str) -> bool:
    catalog = cfg.get(key)
    if not isinstance(catalog, dict):
        return False
    return any(isinstance(payload, dict) and bool(payload.get("enabled", False)) for payload in catalog.values())


def _is_lab_eda_config(cfg: dict[str, Any]) -> bool:
    logging_cfg = dict(cfg.get("logging", {}) or {})
    model_kind = str(dict(cfg.get("model", {}) or {}).get("kind", "none")).strip().lower()
    path_tokens = " ".join(
        [
            str(cfg.get("config_path", "")),
            str(logging_cfg.get("output_dir", "")),
            str(logging_cfg.get("run_name", "")),
        ]
    ).lower()
    return model_kind == "none" or "lab" in path_tokens


def _has_enabled_target_config(cfg: dict[str, Any]) -> bool:
    if _enabled_catalog_item_exists(cfg, "targets_catalog"):
        return True
    for target_cfg in (
        cfg.get("target"),
        dict(dict(cfg.get("model", {}) or {}).get("target", {}) or {}),
    ):
        if not isinstance(target_cfg, dict):
            continue
        kind = str(target_cfg.get("kind", "")).strip().lower()
        if kind and kind != "none":
            return True
    return False


def _has_enabled_signal_config(cfg: dict[str, Any]) -> bool:
    if _enabled_catalog_item_exists(cfg, "signals_catalog"):
        return True
    signals_cfg = dict(cfg.get("signals", {}) or {})
    kind = str(signals_cfg.get("kind", "none")).strip().lower()
    return bool(kind and kind != "none")


def _configured_lab_signal_columns(cfg: dict[str, Any]) -> set[str]:
    columns: set[str] = set()
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    if backtest_cfg.get("signal_col"):
        columns.add(str(backtest_cfg["signal_col"]))

    sections: list[dict[str, Any]] = []
    signals_cfg = dict(cfg.get("signals", {}) or {})
    sections.append(dict(signals_cfg.get("params", {}) or {}))
    signals_catalog = cfg.get("signals_catalog")
    if isinstance(signals_catalog, dict):
        for payload in signals_catalog.values():
            if isinstance(payload, dict):
                sections.append(dict(payload.get("params", {}) or {}))

    for params in sections:
        for key in _SIGNAL_PARAM_COLUMN_KEYS:
            value = params.get(key)
            if isinstance(value, str) and value:
                columns.add(value)
    return columns


def _is_lab_feature_column(column: str, frame: pd.DataFrame, *, excluded_signal_cols: set[str]) -> bool:
    if column in _LAB_RAW_MARKET_COLUMNS or column in _LAB_EXCLUDED_COLUMNS or column in excluded_signal_cols:
        return False
    if column.startswith(_LAB_EXCLUDED_PREFIXES):
        return False
    if column not in frame.columns or not pd.api.types.is_numeric_dtype(frame[column]):
        return False
    series = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return bool(series.notna().any())


def _resolve_lab_feature_columns(frame: pd.DataFrame, cfg: dict[str, Any]) -> list[str]:
    excluded_signal_cols = _configured_lab_signal_columns(cfg)
    model_features = [
        str(column)
        for column in list(dict(cfg.get("model", {}) or {}).get("feature_cols", []) or [])
        if _is_lab_feature_column(str(column), frame, excluded_signal_cols=excluded_signal_cols)
    ]
    candidates = [
        str(column)
        for column in frame.columns
        if _is_lab_feature_column(str(column), frame, excluded_signal_cols=excluded_signal_cols)
    ]
    ordered: list[str] = []
    for column in [*model_features, *candidates]:
        if column not in ordered:
            ordered.append(column)
    return ordered


def _is_lab_price_overlay_column(column: str) -> bool:
    token = str(column)
    if token in _LAB_PRICE_OVERLAY_EXACT_COLUMNS:
        return True
    if re.fullmatch(r".+_(?:sma|ema)_\d+", token):
        return True
    if re.fullmatch(r"bb_(?:ma|upper|lower)_\d+(?:_[0-9.]+)?", token):
        return True
    if re.fullmatch(r"(?:support|resistance)_\d+", token):
        return True
    return bool(token.endswith("_price") and not token.startswith(("r_target_", "target_")))


def _split_lab_feature_columns(feature_cols: list[str]) -> tuple[list[str], list[str]]:
    price_overlay_cols: list[str] = []
    scaled_feature_cols: list[str] = []
    for column in feature_cols:
        if _is_lab_price_overlay_column(column):
            price_overlay_cols.append(column)
        else:
            scaled_feature_cols.append(column)
    return price_overlay_cols, scaled_feature_cols


def _write_lab_feature_diagnostic_artifacts(
    *,
    run_dir: Path,
    data: pd.DataFrame | dict[str, pd.DataFrame],
    cfg: dict[str, Any],
) -> dict[str, str]:
    if not _is_lab_eda_config(cfg):
        return {}

    asset_frames = _asset_frames_for_trade_diagnostics(data, cfg)
    if not asset_frames:
        return {}

    artifact_paths: dict[str, str] = {}
    for asset, frame in sorted(asset_frames.items()):
        feature_cols = _resolve_lab_feature_columns(frame, cfg)
        if not feature_cols:
            continue
        safe_asset = _safe_asset_filename(asset)
        diagnostics_dir = run_dir / "artifacts" / "diagnostics"
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = diagnostics_dir / f"lab_feature_diagnostics_{safe_asset}.json"
        price_overlay_cols, scaled_feature_cols = _split_lab_feature_columns(feature_cols)
        payload = {
            "asset": asset,
            "feature_count": len(feature_cols),
            "price_overlay_columns": price_overlay_cols,
            "scaled_feature_columns": scaled_feature_cols,
            "row_count": int(len(frame)),
        }
        metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        artifact_paths[f"lab_feature_diagnostics_{safe_asset}"] = str(metadata_path.relative_to(run_dir))
    return artifact_paths


def _should_write_trade_diagnostic_artifacts(cfg: dict[str, Any]) -> bool:
    if _is_lab_eda_config(cfg) and not _has_enabled_signal_config(cfg) and not _has_enabled_target_config(cfg):
        return False
    return True


def _first_existing_column(frame: pd.DataFrame, candidates: list[str | None]) -> str | None:
    for candidate in candidates:
        if candidate and str(candidate) in frame.columns:
            return str(candidate)
    return None


def _annotate_frame_with_trade_barriers(
    frame: pd.DataFrame,
    trades: pd.DataFrame | None,
    *,
    asset: str,
) -> pd.DataFrame:
    if trades is None or trades.empty:
        return frame
    out = frame.copy()
    asset_trades = trades
    if "asset" in asset_trades.columns:
        asset_trades = asset_trades.loc[asset_trades["asset"].astype(str) == str(asset)]
    if asset_trades.empty:
        return out

    for column in (
        "manual_target",
        "manual_take_profit_price",
        "manual_stop_loss_price",
        "manual_hit_step",
        "manual_trade_r",
    ):
        if column not in out.columns:
            out[column] = np.nan
    if "manual_exit_reason" not in out.columns:
        out["manual_exit_reason"] = pd.Series(pd.NA, index=out.index, dtype="object")
    else:
        out["manual_exit_reason"] = out["manual_exit_reason"].astype("object")

    for _, trade in asset_trades.iterrows():
        entry_ts = pd.Timestamp(trade.get("entry_timestamp"))
        if entry_ts not in out.index:
            continue
        exit_ts = pd.Timestamp(trade.get("exit_timestamp"))
        if exit_ts in out.index:
            bars_held = int(out.index.get_loc(exit_ts)) - int(out.index.get_loc(entry_ts))
        else:
            bars_held = pd.to_numeric(pd.Series([trade.get("bars_held")]), errors="coerce").iloc[0]
        out.loc[entry_ts, "manual_target"] = trade.get("target_price", trade.get("take_profit_price"))
        out.loc[entry_ts, "manual_take_profit_price"] = trade.get("take_profit_price")
        out.loc[entry_ts, "manual_stop_loss_price"] = trade.get("stop_loss_price")
        out.loc[entry_ts, "manual_hit_step"] = bars_held
        out.loc[entry_ts, "manual_exit_reason"] = trade.get("exit_reason")
        out.loc[entry_ts, "manual_trade_r"] = trade.get("trade_r")
    return out


def _resolve_trade_diagnostic_columns(
    frame: pd.DataFrame,
    cfg: dict[str, Any],
) -> dict[str, str | None]:
    backtest_cfg = dict(cfg.get("backtest", {}) or {})
    target_cfg = dict(
        cfg.get("target")
        or dict(dict(cfg.get("model", {}) or {}).get("target", {}) or {})
    )
    label_col = _first_existing_column(
        frame,
        [
            target_cfg.get("label_col"),
            "manual_target",
            "label",
            "target",
        ],
    )
    fwd_col = _first_existing_column(frame, [target_cfg.get("fwd_col")])
    r_col = _first_existing_column(
        frame,
        [
            "manual_trade_r",
            target_cfg.get("oriented_r_col"),
            target_cfg.get("r_col"),
            f"{label_col}_oriented_r" if label_col else None,
            "r_target_oriented_r",
            "r_target_trade_r",
            "tb_oriented_r",
            "tb_event_r",
        ],
    )
    return {
        "signal_col": _first_existing_column(frame, [backtest_cfg.get("signal_col"), "manual_long_signal", "signal"]),
        "target_col": label_col or fwd_col,
        "upper_barrier_col": (
            str(target_cfg.get("upper_barrier_col"))
            if target_cfg.get("upper_barrier_col") in frame.columns
            else f"{label_col}_upper_barrier"
            if label_col and f"{label_col}_upper_barrier" in frame.columns
            else _first_existing_column(
                frame,
                [
                    "manual_take_profit_price",
                    "take_profit_price",
                    "target_price",
                    target_cfg.get("take_profit_price_col"),
                    "r_target_take_profit_price",
                ],
            )
        ),
        "lower_barrier_col": (
            str(target_cfg.get("lower_barrier_col"))
            if target_cfg.get("lower_barrier_col") in frame.columns
            else f"{label_col}_lower_barrier"
            if label_col and f"{label_col}_lower_barrier" in frame.columns
            else _first_existing_column(
                frame,
                ["manual_stop_loss_price", "stop_loss_price", target_cfg.get("stop_price_col"), "r_target_stop_price"],
            )
        ),
        "hit_step_col": (
            str(target_cfg.get("hit_step_col"))
            if target_cfg.get("hit_step_col") in frame.columns
            else f"{label_col}_hit_step"
            if label_col and f"{label_col}_hit_step" in frame.columns
            else _first_existing_column(frame, ["manual_hit_step", "r_target_hit_step"])
        ),
        "hit_type_col": (
            str(target_cfg.get("hit_type_col"))
            if target_cfg.get("hit_type_col") in frame.columns
            else f"{label_col}_hit_type"
            if label_col and f"{label_col}_hit_type" in frame.columns
            else _first_existing_column(
                frame,
                ["manual_exit_reason", target_cfg.get("exit_reason_col"), "r_target_exit_reason", "r_target_hit_type"],
            )
        ),
        "r_col": r_col,
        "entry_price_col": _first_existing_column(frame, [target_cfg.get("entry_price_col"), "r_target_entry_price"]),
        "exit_price_col": _first_existing_column(frame, [target_cfg.get("exit_price_col"), "r_target_exit_price"]),
        "target_r_col": _first_existing_column(
            frame,
            [target_cfg.get("trade_r_col"), target_cfg.get("oriented_r_col"), "r_target_trade_r", "r_target_oriented_r"],
        ),
        "target_entry_price_col": _first_existing_column(frame, [target_cfg.get("entry_price_col"), "r_target_entry_price"]),
        "target_exit_price_col": _first_existing_column(frame, [target_cfg.get("exit_price_col"), "r_target_exit_price"]),
        "target_stop_col": _first_existing_column(frame, [target_cfg.get("stop_price_col"), "r_target_stop_price"]),
        "target_take_profit_col": _first_existing_column(
            frame,
            [target_cfg.get("take_profit_price_col"), "r_target_take_profit_price"],
        ),
        "target_exit_reason_col": _first_existing_column(
            frame,
            [target_cfg.get("exit_reason_col"), target_cfg.get("hit_type_col"), "r_target_exit_reason", "r_target_hit_type"],
        ),
    }


def _resolve_trade_diagnostic_feature_panels(
    frame: pd.DataFrame,
    cfg: dict[str, Any],
) -> list[str]:
    def _roc_long_only_params(config: dict[str, Any]) -> dict[str, Any]:
        for step in list(config.get("features", []) or []):
            if not isinstance(step, dict):
                continue
            if str(step.get("step", "")).strip() == "roc_long_only_conditions":
                return dict(step.get("params", {}) or {})
        signals_cfg = dict(config.get("signals", {}) or {})
        if str(signals_cfg.get("kind", "")).strip() == "roc_long_only_conditions":
            return dict(signals_cfg.get("params", {}) or {})
        return {}

    def _resolve_requested_column(
        requested: str,
        *,
        params: dict[str, Any],
    ) -> str | None:
        token = str(requested).strip()
        if not token:
            return None

        if token in frame.columns:
            return token

        roc_window = int(params.get("roc_window", 12) or 12)
        vol_short_window = int(params.get("vol_short_window", 24) or 24)
        vol_long_window = int(params.get("vol_long_window", 168) or 168)
        dynamic_map = {
            "roc_dynamic": str(params.get("roc_col") or f"roc_{roc_window}"),
            "regime_vol_ratio_z_dynamic": str(
                params.get("regime_vol_ratio_z_col") or f"regime_vol_ratio_z_{vol_short_window}_{vol_long_window}"
            ),
            "close_z_dynamic": str(params.get("close_z_col") or "close_z"),
            "close_open_ratio_dynamic": str(params.get("close_open_ratio_col") or "close_open_ratio"),
            "mtf_1h_dynamic": str(params.get("mtf_1h_col") or "mtf_1h_trend_score"),
            "mtf_4h_dynamic": str(params.get("mtf_4h_col") or "mtf_4h_trend_score"),
            "score_dynamic": str(params.get("score_col") or "manual_conviction_score"),
            "long_signal_dynamic": str(params.get("long_signal_col") or "manual_long_signal"),
            "vol_adjusted_dynamic": str(params.get("vol_adjusted_col") or "manual_vol_adjusted_signal"),
        }
        if token in dynamic_map and dynamic_map[token] in frame.columns:
            return dynamic_map[token]

        if re.fullmatch(r"roc_\d+", token):
            dynamic_col = dynamic_map["roc_dynamic"]
            if dynamic_col in frame.columns:
                return dynamic_col
        if re.fullmatch(r"regime_vol_ratio_z_\d+_\d+", token):
            dynamic_col = dynamic_map["regime_vol_ratio_z_dynamic"]
            if dynamic_col in frame.columns:
                return dynamic_col

        named_aliases = {
            "close_z": dynamic_map["close_z_dynamic"],
            "close_open_ratio": dynamic_map["close_open_ratio_dynamic"],
            "mtf_1h_trend_score": dynamic_map["mtf_1h_dynamic"],
            "mtf_4h_trend_score": dynamic_map["mtf_4h_dynamic"],
            "manual_conviction_score": dynamic_map["score_dynamic"],
            "manual_long_signal": dynamic_map["long_signal_dynamic"],
            "manual_long_candidate": dynamic_map["long_signal_dynamic"],
            "manual_vol_adjusted_signal": dynamic_map["vol_adjusted_dynamic"],
            "manual_vol_adjusted_candidate": dynamic_map["vol_adjusted_dynamic"],
        }
        alias_col = named_aliases.get(token)
        if alias_col in frame.columns:
            return alias_col
        return token if token in frame.columns else None

    model_cfg = dict(cfg.get("model", {}) or {})
    target_cfg = dict(cfg.get("target") or model_cfg.get("target", {}) or {})
    requested = list(target_cfg.get("diagnostic_feature_cols", []) or [])
    signal_params = _roc_long_only_params(cfg)
    ordered: list[str] = []
    for column in requested:
        if not isinstance(column, str) or not column.strip():
            continue
        resolved = _resolve_requested_column(column, params=signal_params)
        if resolved is None or resolved in ordered:
            continue
        ordered.append(resolved)
    return ordered


def _write_trade_diagnostic_artifacts(
    *,
    run_dir: Path,
    data: pd.DataFrame | dict[str, pd.DataFrame],
    performance: BacktestResult | PortfolioPerformance,
    cfg: dict[str, Any],
    portfolio_weights: pd.DataFrame | None,
) -> tuple[dict[str, str], dict[str, str]]:
    asset_frames = _asset_frames_for_trade_diagnostics(data, cfg)
    positions_by_asset = _positions_for_trade_diagnostics(
        asset_frames=asset_frames,
        performance=performance,
        portfolio_weights=portfolio_weights,
    )
    if not asset_frames or not positions_by_asset:
        return {}, {}

    report_assets_dir = run_dir / "report_assets"
    report_assets_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: dict[str, str] = {}
    artifact_paths: dict[str, str] = {}
    event_frames: list[pd.DataFrame] = []
    target_event_frames: list[pd.DataFrame] = []
    backtest_trades = getattr(performance, "trades", None)
    if isinstance(backtest_trades, pd.DataFrame) and not backtest_trades.empty:
        trades_path = report_assets_dir / "trades.csv"
        backtest_trades.to_csv(trades_path, index=False)
        artifact_paths["trades"] = str(trades_path.relative_to(run_dir))

    for asset, frame in sorted(asset_frames.items()):
        positions = positions_by_asset.get(asset)
        if positions is None:
            continue
        frame = _annotate_frame_with_trade_barriers(
            frame,
            backtest_trades if isinstance(backtest_trades, pd.DataFrame) else None,
            asset=asset,
        )
        feature_panel_cols = _resolve_trade_diagnostic_feature_panels(frame, cfg)
        target_candidate_col = _first_existing_column(frame, ["r_target_candidate"])
        if target_candidate_col is not None:
            target_cols = [
                col
                for col in [
                    target_candidate_col,
                    "label",
                    "r_target_event_ret",
                    "r_target_trade_r",
                    "r_target_oriented_r",
                    "r_target_entry_price",
                    "r_target_exit_price",
                    "r_target_stop_price",
                    "r_target_take_profit_price",
                    "r_target_exit_reason",
                    "r_target_bars_held",
                    "r_target_mfe_r",
                    "r_target_mae_r",
                    "r_target_time_to_mfe",
                    "r_target_time_to_mae",
                    "target_mfe_r",
                    "target_mae_r",
                    "target_time_to_mfe",
                    "target_time_to_mae",
                    "r_target_hit_type",
                    "r_target_hit_step",
                    *feature_panel_cols,
                ]
                if col in frame.columns
            ]
            target_rows = frame.loc[pd.to_numeric(frame[target_candidate_col], errors="coerce").fillna(0.0) > 0.0, target_cols]
            if not target_rows.empty:
                target_event_frame = target_rows.reset_index()
                first_col = str(target_event_frame.columns[0])
                if first_col != "timestamp":
                    target_event_frame = target_event_frame.rename(columns={first_col: "timestamp"})
                target_event_frame.insert(1, "asset", asset)
                target_event_frames.append(target_event_frame)
        columns = _resolve_trade_diagnostic_columns(frame, cfg)
        events = build_trade_event_frame(
            frame,
            positions=positions,
            asset=asset,
            signal_col=columns["signal_col"],
            target_col=columns["target_col"],
            upper_barrier_col=columns["upper_barrier_col"],
            lower_barrier_col=columns["lower_barrier_col"],
            hit_step_col=columns["hit_step_col"],
            hit_type_col=columns["hit_type_col"],
            r_col=columns["r_col"],
            entry_price_col=columns["entry_price_col"],
            exit_price_col=columns["exit_price_col"],
            price_col="close",
        )
        if not events.empty:
            event_frames.append(events)

    if event_frames:
        events_path = report_assets_dir / "trade_events.csv"
        pd.concat(event_frames, ignore_index=True).to_csv(events_path, index=False)
        artifact_paths["trade_events"] = str(events_path.relative_to(run_dir))
    if target_event_frames:
        target_events_path = report_assets_dir / "target_events.csv"
        pd.concat(target_event_frames, ignore_index=True).to_csv(target_events_path, index=False)
        artifact_paths["target_events"] = str(target_events_path.relative_to(run_dir))

    return chart_paths, artifact_paths


def write_experiment_report_from_run_dir(run_dir: Path) -> dict[str, str]:
    cfg = _load_yaml(run_dir / "config_used.yaml")
    summary_payload = _load_json(run_dir / "summary.json")
    run_metadata = _load_json(run_dir / "run_metadata.json")
    model_meta = dict(run_metadata.get("model_meta", {}) or {})

    returns_type = str(dict(cfg.get("backtest", {}) or {}).get("returns_type", "simple"))
    net_returns = _first_series(_read_numeric_timeseries(run_dir / "returns.csv"))
    gross_returns = _first_series(_read_numeric_timeseries(run_dir / "gross_returns.csv"))
    costs = _first_series(_read_numeric_timeseries(run_dir / "costs.csv"))
    turnover = _first_series(_read_numeric_timeseries(run_dir / "turnover.csv"))
    positions = _first_series(_read_numeric_timeseries(run_dir / "positions.csv"))
    equity_curve = _first_series(_read_numeric_timeseries(run_dir / "equity_curve.csv"))
    portfolio_weights = _read_numeric_timeseries(run_dir / "portfolio_weights.csv")

    report_assets_dir = run_dir / "report_assets"
    report_assets_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: dict[str, str] = {}
    diagnostics_dir = run_dir / "artifacts" / "diagnostics"
    diagnostic_artifact_paths: dict[str, str] = {}
    if diagnostics_dir.exists():
        for path in sorted(diagnostics_dir.glob("*")):
            if not path.is_file() or path.name == ".DS_Store":
                continue
            label = f"diagnostics_{path.stem}"
            rel_path = str(path.relative_to(run_dir))
            if path.suffix.lower() == ".png":
                chart_paths[label] = rel_path
            elif path.suffix.lower() in {".csv", ".json", ".html", ".htm"}:
                diagnostic_artifact_paths[label] = rel_path

    model_kind = str(dict(cfg.get("model", {}) or {}).get("kind", "none"))
    strategy_name = str(dict(cfg.get("strategy", {}) or {}).get("name", ""))
    logging_output_dir = str(dict(cfg.get("logging", {}) or {}).get("output_dir", ""))
    is_lab_forecast_run = (
        strategy_name.startswith("lab_")
        or logging_output_dir.endswith("logs/lab")
        or "/logs/lab" in logging_output_dir
    )
    forecast_first = (
        model_kind in _FORECASTER_MODEL_KINDS
        and is_lab_forecast_run
        and (diagnostics_dir / "prediction_distribution.csv").exists()
    )

    if not forecast_first and not equity_curve.empty:
        equity_path = report_assets_dir / "equity_curve.png"
        _save_line_chart(
            equity_path,
            title="Equity Curve",
            ylabel="Equity",
            series_map={"equity": equity_curve},
        )
        chart_paths["equity_curve_chart"] = str(equity_path.relative_to(run_dir))

        drawdown_path = report_assets_dir / "drawdown_curve.png"
        _save_line_chart(
            drawdown_path,
            title="Drawdown Curve",
            ylabel="Drawdown",
            series_map={"drawdown": _drawdown_from_equity(equity_curve)},
        )
        chart_paths["drawdown_curve"] = str(drawdown_path.relative_to(run_dir))

    if not forecast_first and not net_returns.empty and not gross_returns.empty:
        cumulative_path = report_assets_dir / "cumulative_returns.png"
        _save_line_chart(
            cumulative_path,
            title="Cumulative Gross vs Net Returns",
            ylabel="Cumulative Return",
            series_map={
                "gross": _returns_to_curve(gross_returns, returns_type=returns_type),
                "net": _returns_to_curve(net_returns, returns_type=returns_type),
            },
        )
        chart_paths["cumulative_returns"] = str(cumulative_path.relative_to(run_dir))

        monthly_path = report_assets_dir / "monthly_returns.png"
        _save_monthly_bar_chart(monthly_path, net_returns=net_returns, gross_returns=gross_returns)
        if monthly_path.exists():
            chart_paths["monthly_returns"] = str(monthly_path.relative_to(run_dir))

        rolling_window = _rolling_window_length(net_returns, default=48)
        rolling_pnl_path = report_assets_dir / "rolling_pnl.png"
        _save_rolling_line_chart(
            rolling_pnl_path,
            title=f"Rolling {rolling_window}-Bar Gross / Net PnL",
            ylabel="Rolling Sum",
            series_map={"gross": gross_returns, "net": net_returns, "cost_drag": -costs},
            window=rolling_window,
        )
        if rolling_pnl_path.exists():
            chart_paths["rolling_pnl"] = str(rolling_pnl_path.relative_to(run_dir))

        cumulative_cost_path = report_assets_dir / "cumulative_cost_drag.png"
        _save_line_chart(
            cumulative_cost_path,
            title="Cumulative Cost Drag",
            ylabel="Cost",
            series_map={"cost_drag": costs.cumsum()},
        )
        if cumulative_cost_path.exists():
            chart_paths["cumulative_cost_drag"] = str(cumulative_cost_path.relative_to(run_dir))

    if not forecast_first and not positions.empty and not turnover.empty:
        signal_turnover_path = report_assets_dir / "positions_turnover.png"
        _save_dual_panel_chart(
            signal_turnover_path,
            top_title="Signal / Position Path",
            bottom_title="Turnover",
            top_series=positions,
            bottom_series=turnover,
            top_ylabel="Signal",
            bottom_ylabel="Turnover",
        )
        chart_paths["positions_turnover"] = str(signal_turnover_path.relative_to(run_dir))

        behavior_window = _rolling_window_length(positions, default=48)
        rolling_behavior_path = report_assets_dir / "rolling_behavior.png"
        _save_dual_panel_chart(
            rolling_behavior_path,
            top_title=f"Rolling {behavior_window}-Bar Mean Abs Signal",
            bottom_title=f"Rolling {behavior_window}-Bar Mean Turnover",
            top_series=positions.abs().rolling(behavior_window, min_periods=max(3, behavior_window // 4)).mean(),
            bottom_series=turnover.rolling(behavior_window, min_periods=max(3, behavior_window // 4)).mean(),
            top_ylabel="Mean |Signal|",
            bottom_ylabel="Mean Turnover",
        )
        if rolling_behavior_path.exists():
            chart_paths["rolling_behavior"] = str(rolling_behavior_path.relative_to(run_dir))

        distribution_path = report_assets_dir / "signal_distribution.png"
        _save_histogram_chart(
            distribution_path,
            title="Signal Distribution",
            xlabel="Signal",
            series_map={"signal": positions},
            bins=25,
        )
        if distribution_path.exists():
            chart_paths["signal_distribution"] = str(distribution_path.relative_to(run_dir))

    fold_summaries = list(dict(summary_payload.get("evaluation", {}) or {}).get("fold_backtest_summaries", []) or [])
    if not forecast_first and fold_summaries:
        fold_path = report_assets_dir / "fold_net_pnl.png"
        _save_fold_bar_chart(fold_path, fold_summaries=fold_summaries)
        if fold_path.exists():
            chart_paths["fold_net_pnl"] = str(fold_path.relative_to(run_dir))

    if not forecast_first and not portfolio_weights.empty:
        exposure_path = report_assets_dir / "portfolio_exposures.png"
        _save_portfolio_exposure_chart(exposure_path, weights=portfolio_weights)
        if exposure_path.exists():
            chart_paths["portfolio_exposures"] = str(exposure_path.relative_to(run_dir))

    model_chart_paths, model_artifact_paths = _write_model_diagnostic_artifacts(
        run_dir=run_dir,
        model_meta=model_meta,
    )
    chart_paths.update(model_chart_paths)

    report_path = run_dir / "report.md"
    artifact_paths = {
        "report_markdown": "report.md",
        "config": "config_used.yaml",
        "summary": "summary.json",
        "run_metadata": "run_metadata.json",
        "equity_curve": "equity_curve.csv",
        "returns": "returns.csv",
        "gross_returns": "gross_returns.csv",
        "costs": "costs.csv",
        "turnover": "turnover.csv",
    }
    if (run_dir / "positions.csv").exists():
        artifact_paths["positions"] = "positions.csv"
    if (run_dir / "monitoring_report.json").exists():
        artifact_paths["monitoring"] = "monitoring_report.json"
    if (run_dir / "portfolio_weights.csv").exists():
        artifact_paths["portfolio_weights"] = "portfolio_weights.csv"
    if (report_assets_dir / "trade_events.csv").exists():
        artifact_paths["trade_events"] = str((report_assets_dir / "trade_events.csv").relative_to(run_dir))
    if (report_assets_dir / "target_events.csv").exists():
        artifact_paths["target_events"] = str((report_assets_dir / "target_events.csv").relative_to(run_dir))
    if (report_assets_dir / "trades.csv").exists():
        artifact_paths["trades"] = str((report_assets_dir / "trades.csv").relative_to(run_dir))
    for label, filename in (
        ("trades_enriched", "trades_enriched.csv"),
        ("target_trades_enriched", "target_trades_enriched.csv"),
        ("trade_path_summary", "trade_path_summary.json"),
        ("trade_paths", "trade_paths.parquet"),
        ("trade_paths", "trade_paths.csv"),
        ("trade_path_diagnostics", "trade_path_diagnostics.json"),
        ("probability_trade_quality", "probability_trade_quality.csv"),
        ("probability_trade_quality_diagnostics", "probability_trade_quality_diagnostics.json"),
        ("counterfactual_exit_summary", "counterfactual_exit_summary.csv"),
        ("counterfactual_exit_trades", "counterfactual_exit_trades.csv"),
    ):
        path = report_assets_dir / filename
        if path.exists():
            artifact_paths[label] = str(path.relative_to(run_dir))
    artifact_paths.update(model_artifact_paths)
    if (run_dir / "stage_tails.json").exists():
        artifact_paths["stage_tails"] = "stage_tails.json"
    artifact_paths.update(diagnostic_artifact_paths)
    for label, rel_path in chart_paths.items():
        artifact_paths[label] = rel_path

    report_markdown = build_experiment_report_markdown(
        cfg=cfg,
        summary_payload=summary_payload,
        run_metadata=run_metadata,
        chart_paths=chart_paths,
        artifact_paths=artifact_paths,
    )
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(report_markdown)

    report_artifacts = {
        "report": str(report_path),
    }
    for label, rel_path in chart_paths.items():
        report_artifacts[label] = str((run_dir / rel_path).resolve())
    if "trade_events" in artifact_paths:
        report_artifacts["trade_events"] = str((run_dir / artifact_paths["trade_events"]).resolve())
    if "target_events" in artifact_paths:
        report_artifacts["target_events"] = str((run_dir / artifact_paths["target_events"]).resolve())
    if "trades" in artifact_paths:
        report_artifacts["trades"] = str((run_dir / artifact_paths["trades"]).resolve())
    for label in (
        "trades_enriched",
        "target_trades_enriched",
        "trade_path_summary",
        "trade_paths",
        "trade_path_diagnostics",
        "probability_trade_quality",
        "probability_trade_quality_diagnostics",
        "counterfactual_exit_summary",
        "counterfactual_exit_trades",
    ):
        if label in artifact_paths:
            report_artifacts[label] = str((run_dir / artifact_paths[label]).resolve())
    for label, rel_path in model_artifact_paths.items():
        report_artifacts[label] = str((run_dir / rel_path).resolve())
    return report_artifacts


def _trade_path_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    diagnostics = dict(cfg.get("diagnostics", {}) or {})
    trade_path = dict(diagnostics.get("trade_path", {}) or {})
    if "enabled" not in trade_path:
        trade_path["enabled"] = bool(diagnostics.get("enabled", False))
    return trade_path


def _trade_path_enabled(cfg: dict[str, Any]) -> bool:
    return bool(_trade_path_cfg(cfg).get("enabled", False))


def _augment_trades_with_model_columns(
    trades: pd.DataFrame,
    *,
    asset_frames: dict[str, pd.DataFrame],
    model_meta: dict[str, Any],
) -> pd.DataFrame:
    if trades.empty or not asset_frames:
        return trades.copy()
    out = trades.copy()
    per_asset_meta = dict(model_meta.get("per_asset", {}) or {})
    default_asset = next(iter(sorted(asset_frames))) if len(asset_frames) == 1 else None
    for idx, trade in out.iterrows():
        asset = str(trade.get("asset", default_asset or ""))
        frame = asset_frames.get(asset)
        if frame is None or frame.empty:
            continue
        timestamp = trade.get("signal_timestamp", trade.get("signal_time", trade.get("entry_timestamp")))
        if pd.isna(timestamp):
            continue
        timestamp = pd.Timestamp(timestamp)
        if timestamp not in frame.index:
            pos = frame.index.searchsorted(timestamp, side="left")
            if pos >= len(frame.index):
                continue
            timestamp = frame.index[pos]
        meta = dict(per_asset_meta.get(asset, {}) or model_meta or {})
        prob_col = str(meta.get("pred_prob_col") or model_meta.get("pred_prob_col") or "pred_prob")
        oos_col = str(meta.get("pred_is_oos_col") or model_meta.get("pred_is_oos_col") or "pred_is_oos")
        if prob_col in frame.columns and "pred_prob" not in out.columns:
            out["pred_prob"] = np.nan
        if oos_col in frame.columns and "pred_is_oos" not in out.columns:
            out["pred_is_oos"] = False
        if prob_col in frame.columns:
            out.at[idx, "pred_prob"] = frame.at[timestamp, prob_col]
        if oos_col in frame.columns:
            out.at[idx, "pred_is_oos"] = bool(frame.at[timestamp, oos_col])
    return out


def _target_candidate_trades_from_asset_frames(asset_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for asset, frame in sorted(asset_frames.items()):
        candidate_col = _first_existing_column(frame, ["r_target_candidate", "target_candidate"])
        if candidate_col is None:
            continue
        candidate = pd.to_numeric(frame[candidate_col], errors="coerce").fillna(0.0).gt(0.0)
        if not bool(candidate.any()):
            continue
        column_map = {
            "trade_r": _first_existing_column(frame, ["r_target_trade_r", "target_trade_r", "target_r"]),
            "max_favorable_r": _first_existing_column(frame, ["r_target_mfe_r", "target_mfe_r", "mfe_r"]),
            "max_adverse_r": _first_existing_column(frame, ["r_target_mae_r", "target_mae_r", "mae_r"]),
            "bars_held": _first_existing_column(frame, ["r_target_bars_held", "target_bars_held"]),
            "exit_reason": _first_existing_column(frame, ["r_target_exit_reason", "target_exit_reason"]),
            "time_to_mfe": _first_existing_column(frame, ["r_target_time_to_mfe", "target_time_to_mfe"]),
            "time_to_mae": _first_existing_column(frame, ["r_target_time_to_mae", "target_time_to_mae"]),
            "entry_price": _first_existing_column(frame, ["r_target_entry_price", "target_entry_price"]),
            "exit_price": _first_existing_column(frame, ["r_target_exit_price", "target_exit_price"]),
            "stop_loss_price": _first_existing_column(frame, ["r_target_stop_price", "target_stop_price"]),
            "take_profit_price": _first_existing_column(frame, ["r_target_take_profit_price", "target_take_profit_price"]),
            "pred_prob": _first_existing_column(frame, ["pred_prob", "prob_positive"]),
            "pred_is_oos": _first_existing_column(frame, ["pred_is_oos"]),
        }
        selected_cols = [col for col in column_map.values() if col is not None]
        target_rows = frame.loc[candidate, selected_cols].copy()
        rename_map = {source: target for target, source in column_map.items() if source is not None}
        target_rows = target_rows.rename(columns=rename_map)
        target_rows.insert(0, "asset", asset)
        target_rows.insert(1, "signal_timestamp", target_rows.index)
        target_rows.insert(2, "entry_timestamp", target_rows.index)
        target_rows.insert(3, "side", "long")
        rows.append(target_rows.reset_index(drop=True))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def enrich_evaluation_with_trade_path_diagnostics(
    *,
    cfg: dict[str, Any],
    data: pd.DataFrame | dict[str, pd.DataFrame],
    performance: BacktestResult | PortfolioPerformance,
    model_meta: dict[str, Any],
    evaluation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not _trade_path_enabled(cfg):
        return evaluation, {}
    trade_path_cfg = _trade_path_cfg(cfg)
    thresholds = [float(value) for value in list(trade_path_cfg.get("thresholds_r", [0.5, 1.0, 1.5, 2.0]) or [])]
    buckets = [int(value) for value in list(trade_path_cfg.get("bars_held_buckets", [1, 2, 4, 8, 16]) or [])]
    asset_frames = _asset_frames_for_trade_diagnostics(data, cfg)
    trades = getattr(performance, "trades", None)
    has_executed_trades = isinstance(trades, pd.DataFrame) and not trades.empty
    ledger_diag: dict[str, Any] = {}
    if not has_executed_trades and isinstance(performance, BacktestResult):
        default_asset = next(iter(sorted(asset_frames))) if len(asset_frames) == 1 else None
        trades, ledger_diag = build_trade_ledger_from_position_transitions(
            asset_frames,
            positions=performance.positions,
            gross_returns=performance.gross_returns,
            net_returns=performance.returns,
            costs=performance.costs,
            turnover=performance.turnover,
            cfg=cfg,
            asset=default_asset,
        )
        has_executed_trades = isinstance(trades, pd.DataFrame) and not trades.empty
    enriched = pd.DataFrame()
    max_path_points = int(dict(trade_path_cfg.get("plots", {}) or {}).get("max_path_points", 200000))
    trade_paths = pd.DataFrame()
    path_diag: dict[str, Any] = {
        "trade_count": 0,
        "path_trade_count": 0,
        "warnings": ["trade path construction skipped: no executed trades"],
    }
    lifecycle: dict[str, Any] = {}
    if has_executed_trades:
        enriched = _augment_trades_with_model_columns(
            enrich_trade_lifecycle_columns(trades, thresholds),
            asset_frames=asset_frames,
            model_meta=model_meta,
        ).reset_index(drop=True)
        trade_paths, path_diag = build_trade_paths(asset_frames, enriched, max_path_points=max_path_points)
        if not trade_paths.empty:
            has_time_to_mfe = "time_to_mfe" in enriched.columns and pd.to_numeric(enriched["time_to_mfe"], errors="coerce").notna().sum() > 0
            if not has_time_to_mfe:
                time_to_mfe: dict[Any, int] = {}
                for trade_id, path in trade_paths.sort_values(["trade_id", "bar_in_trade"]).groupby("trade_id", sort=True):
                    high_r = pd.to_numeric(path["high_r"], errors="coerce")
                    if high_r.notna().any():
                        time_to_mfe[trade_id] = int(path.loc[high_r.idxmax(), "bar_in_trade"])
                enriched["time_to_mfe"] = enriched.index.map(time_to_mfe)
            has_time_to_mae = "time_to_mae" in enriched.columns and pd.to_numeric(enriched["time_to_mae"], errors="coerce").notna().sum() > 0
            if not has_time_to_mae:
                time_to_mae: dict[Any, int] = {}
                for trade_id, path in trade_paths.sort_values(["trade_id", "bar_in_trade"]).groupby("trade_id", sort=True):
                    low_r = pd.to_numeric(path["low_r"], errors="coerce")
                    if low_r.notna().any():
                        time_to_mae[trade_id] = int(path.loc[low_r.idxmin(), "bar_in_trade"])
                enriched["time_to_mae"] = enriched.index.map(time_to_mae)
        lifecycle = summarize_trade_lifecycle(enriched, thresholds_r=thresholds, bars_held_buckets=buckets)
    target_enriched = pd.DataFrame()
    target_summary: dict[str, Any] = {}
    if bool(trade_path_cfg.get("include_target_trades", True)):
        target_trades = _target_candidate_trades_from_asset_frames(asset_frames)
        if not target_trades.empty:
            target_enriched = enrich_trade_lifecycle_columns(target_trades, thresholds).reset_index(drop=True)
            target_summary = summarize_trade_lifecycle(
                target_enriched,
                thresholds_r=thresholds,
                bars_held_buckets=buckets,
            )
    counterfactuals, counter_diag = (
        simulate_counterfactual_exits(trade_paths)
        if has_executed_trades and bool(trade_path_cfg.get("include_counterfactuals", True))
        else (pd.DataFrame(), {})
    )
    updated = dict(evaluation)
    trade_diagnostics = dict(updated.get("trade_diagnostics", {}) or {})
    if lifecycle:
        trade_diagnostics.update(dict(lifecycle.get("primary_summary", {}) or {}))
    existing_trade_path = dict(trade_diagnostics.get("trade_path", {}) or {})
    trade_path_payload = {
        **existing_trade_path,
        **{key: value for key, value in lifecycle.items() if key != "primary_summary"},
    }
    if target_summary:
        trade_path_payload["target_candidates"] = {
            key: value
            for key, value in target_summary.items()
            if key in {"primary_summary", "could_have_been_profitable", "capture_giveback", "mae_before_win"}
        }
    warnings = list(trade_path_payload.get("warnings", []) or [])
    warnings.extend(list(ledger_diag.get("warnings", []) or []))
    warnings.extend(list(path_diag.get("warnings", []) or []))
    warnings.extend(list(counter_diag.get("warnings", []) or []))
    if not has_executed_trades and target_enriched.empty:
        warnings.append("trade_path diagnostics skipped: no executed trades or target candidate trades")
    trade_path_payload["warnings"] = warnings
    if ledger_diag:
        trade_path_payload["trade_ledger_construction"] = ledger_diag
    trade_path_payload["path_construction"] = path_diag
    if counter_diag:
        trade_path_payload["counterfactual"] = {
            key: value
            for key, value in counter_diag.items()
            if key != "warnings"
        }
    trade_diagnostics["trade_path"] = trade_path_payload
    updated["trade_diagnostics"] = trade_diagnostics
    primary = dict(updated.get("primary_summary", {}) or {})
    if lifecycle:
        for key, value in dict(lifecycle.get("primary_summary", {}) or {}).items():
            if key in {
                "trade_count",
                "average_r",
                "median_r",
                "avg_max_favorable_r",
                "avg_max_adverse_r",
                "loser_was_positive_rate",
                "avg_giveback_r",
                "avg_capture_ratio",
            }:
                primary[key] = value
    updated["primary_summary"] = primary
    return updated, {
        "trades_enriched": enriched,
        "asset_frames": asset_frames,
        "trade_paths": trade_paths,
        "counterfactuals": counterfactuals,
        "counterfactual_summary": counter_diag,
        "target_trades_enriched": target_enriched,
        "trade_path_summary": trade_path_payload,
    }


def _write_trade_path_lifecycle_artifacts(
    *,
    run_dir: Path,
    cfg: dict[str, Any],
    lifecycle_context: dict[str, Any],
    model_meta: dict[str, Any],
) -> dict[str, str]:
    if not _trade_path_enabled(cfg):
        return {}
    trades = lifecycle_context.get("trades_enriched")
    asset_frames = lifecycle_context.get("asset_frames")
    target_trades = lifecycle_context.get("target_trades_enriched")
    has_trades = isinstance(trades, pd.DataFrame) and not trades.empty
    has_target_trades = isinstance(target_trades, pd.DataFrame) and not target_trades.empty
    if not isinstance(asset_frames, dict) or (not has_trades and not has_target_trades):
        return {}
    trade_path_cfg = _trade_path_cfg(cfg)
    report_assets_dir = run_dir / "report_assets"
    report_assets_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    trade_path_summary = lifecycle_context.get("trade_path_summary")
    if isinstance(trade_path_summary, dict) and trade_path_summary:
        summary_path = report_assets_dir / "trade_path_summary.json"
        _write_json(summary_path, trade_path_summary)
        artifacts["trade_path_summary"] = str(summary_path.relative_to(run_dir))

    if has_trades:
        trades_path = report_assets_dir / "trades_enriched.csv"
        trades.to_csv(trades_path, index=False)
        artifacts["trades_enriched"] = str(trades_path.relative_to(run_dir))
    if has_target_trades:
        target_path = report_assets_dir / "target_trades_enriched.csv"
        target_trades.to_csv(target_path, index=False)
        artifacts["target_trades_enriched"] = str(target_path.relative_to(run_dir))

    max_path_points = int(dict(trade_path_cfg.get("plots", {}) or {}).get("max_path_points", 200000))
    cached_trade_paths = lifecycle_context.get("trade_paths")
    trade_paths = cached_trade_paths if isinstance(cached_trade_paths, pd.DataFrame) else pd.DataFrame()
    path_diagnostics = dict(dict(trade_path_summary or {}).get("path_construction", {}) or {})
    if has_trades and bool(trade_path_cfg.get("write_trade_paths", True)):
        if trade_paths.empty:
            trade_paths, path_diagnostics = build_trade_paths(
                asset_frames,
                trades,
                max_path_points=max_path_points,
            )
        else:
            path_diagnostics = {
                "trade_count": int(len(trades)),
                "path_trade_count": int(trade_paths["trade_id"].nunique()) if "trade_id" in trade_paths.columns else 0,
                "warnings": [],
            }
        if not trade_paths.empty:
            parquet_path = report_assets_dir / "trade_paths.parquet"
            try:
                trade_paths.to_parquet(parquet_path, index=False)
                artifacts["trade_paths"] = str(parquet_path.relative_to(run_dir))
            except (ImportError, ModuleNotFoundError, ValueError):
                csv_path = report_assets_dir / "trade_paths.csv"
                trade_paths.to_csv(csv_path, index=False)
                artifacts["trade_paths"] = str(csv_path.relative_to(run_dir))
        diagnostics_path = report_assets_dir / "trade_path_diagnostics.json"
        _write_json(diagnostics_path, path_diagnostics)
        artifacts["trade_path_diagnostics"] = str(diagnostics_path.relative_to(run_dir))
    elif path_diagnostics:
        diagnostics_path = report_assets_dir / "trade_path_diagnostics.json"
        _write_json(diagnostics_path, path_diagnostics)
        artifacts["trade_path_diagnostics"] = str(diagnostics_path.relative_to(run_dir))

    if has_trades and bool(trade_path_cfg.get("include_probability_quality", True)) and bool(trade_path_cfg.get("write_probability_quality", True)):
        prob_col = str(model_meta.get("pred_prob_col") or "pred_prob")
        oos_col = str(model_meta.get("pred_is_oos_col") or "pred_is_oos")
        quality, quality_diag = summarize_probability_trade_quality(trades, prob_col=prob_col, pred_is_oos_col=oos_col)
        if not quality.empty:
            quality_path = report_assets_dir / "probability_trade_quality.csv"
            quality.to_csv(quality_path, index=False)
            artifacts["probability_trade_quality"] = str(quality_path.relative_to(run_dir))
        if quality_diag.get("warnings"):
            quality_diag_path = report_assets_dir / "probability_trade_quality_diagnostics.json"
            _write_json(quality_diag_path, quality_diag)
            artifacts["probability_trade_quality_diagnostics"] = str(quality_diag_path.relative_to(run_dir))

    if has_trades and bool(trade_path_cfg.get("include_counterfactuals", True)):
        cached_counterfactuals = lifecycle_context.get("counterfactuals")
        cached_counter_diag = lifecycle_context.get("counterfactual_summary")
        if isinstance(cached_counterfactuals, pd.DataFrame) and isinstance(cached_counter_diag, dict):
            counterfactuals = cached_counterfactuals
            counter_diag = cached_counter_diag
        else:
            counterfactuals, counter_diag = simulate_counterfactual_exits(trade_paths)
        if not counterfactuals.empty:
            counter_path = report_assets_dir / "counterfactual_exit_summary.csv"
            summary_rows = [
                {"metric": key, "value": value}
                for key, value in sorted(counter_diag.items())
                if key != "warnings"
            ]
            pd.DataFrame(summary_rows).to_csv(counter_path, index=False)
            artifacts["counterfactual_exit_summary"] = str(counter_path.relative_to(run_dir))
            detail_path = report_assets_dir / "counterfactual_exit_trades.csv"
            counterfactuals.to_csv(detail_path, index=False)
            artifacts["counterfactual_exit_trades"] = str(detail_path.relative_to(run_dir))
    return artifacts


def save_artifacts(
    *,
    run_dir: Path,
    cfg: dict[str, Any],
    data: pd.DataFrame | dict[str, pd.DataFrame],
    performance: BacktestResult | PortfolioPerformance,
    model_meta: dict[str, Any],
    evaluation: dict[str, Any],
    monitoring: dict[str, Any],
    execution: dict[str, Any],
    execution_orders: pd.DataFrame | None,
    portfolio_weights: pd.DataFrame | None,
    portfolio_diagnostics: pd.DataFrame | None,
    portfolio_meta: dict[str, Any],
    storage_meta: dict[str, Any],
    run_metadata: dict[str, Any],
    config_hash_sha256: str,
    data_fingerprint: dict[str, Any],
    stage_tails: dict[str, Any] | None = None,
) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=False)

    cfg_path = run_dir / "config_used.yaml"
    safe_cfg = redact_sensitive_values(cfg)
    with cfg_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(safe_cfg, handle, sort_keys=False)

    source_audit_path = None
    source_audit_cfg = dict(dict(cfg.get("logging", {}) or {}).get("execution_source_audit", {}) or {})
    if bool(source_audit_cfg.get("enabled", False)):
        source_audit_path = write_execution_source_audit(
            run_dir / "execution_source_audit.py",
            cfg=safe_cfg,
        )

    evaluation, lifecycle_context = enrich_evaluation_with_trade_path_diagnostics(
        cfg=cfg,
        data=data,
        performance=performance,
        model_meta=model_meta,
        evaluation=evaluation,
    )

    summary_path = run_dir / "summary.json"
    payload = {
        "summary": evaluation.get("primary_summary", performance.summary),
        "timeline_summary": performance.summary,
        "mark_to_market_summary": getattr(performance, "mark_to_market_summary", None) or {},
        "evaluation": evaluation,
        "monitoring": monitoring,
        "execution": execution,
        "portfolio": portfolio_meta,
        "storage": storage_meta,
        "model_meta": model_meta,
        "config_features": cfg.get("features", []),
        "signals": cfg.get("signals", {}),
        "resolved_feature_columns": resolved_feature_columns(model_meta),
        "data_stats": data_stats_payload(data),
        "stage_tails": dict(stage_tails or {}),
        "reproducibility": {
            "config_hash_sha256": config_hash_sha256,
            "data_hash_sha256": data_fingerprint.get("sha256"),
            "runtime": run_metadata.get("runtime", {}),
        },
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)

    metadata_path = run_dir / "run_metadata.json"
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(run_metadata, handle, indent=2, default=str)

    stage_tails_path = None
    if stage_tails:
        stage_tails_path = run_dir / "stage_tails.json"
        _write_json(stage_tails_path, dict(stage_tails))

    equity_path = run_dir / "equity_curve.csv"
    performance.equity_curve.to_csv(equity_path, header=True)

    if isinstance(performance, BacktestResult):
        net_returns = performance.returns
        positions = performance.positions
        positions_path = run_dir / "positions.csv"
        positions.to_csv(positions_path, header=True)
    else:
        net_returns = performance.net_returns
        positions_path = None

    returns_path = run_dir / "returns.csv"
    net_returns.to_csv(returns_path, header=True)

    gross_returns_path = run_dir / "gross_returns.csv"
    performance.gross_returns.to_csv(gross_returns_path, header=True)

    costs_path = run_dir / "costs.csv"
    performance.costs.to_csv(costs_path, header=True)

    turnover_path = run_dir / "turnover.csv"
    performance.turnover.to_csv(turnover_path, header=True)

    mtm_returns_path = None
    mtm_equity_path = None
    mark_to_market_returns = getattr(performance, "mark_to_market_returns", None)
    mark_to_market_equity = getattr(performance, "mark_to_market_equity_curve", None)
    if mark_to_market_returns is not None:
        mtm_returns_path = run_dir / "mark_to_market_returns.csv"
        mark_to_market_returns.to_csv(mtm_returns_path, header=True)
    if mark_to_market_equity is not None:
        mtm_equity_path = run_dir / "mark_to_market_equity_curve.csv"
        mark_to_market_equity.to_csv(mtm_equity_path, header=True)

    monitoring_path = None
    if monitoring:
        monitoring_path = run_dir / "monitoring_report.json"
        with monitoring_path.open("w", encoding="utf-8") as handle:
            json.dump(monitoring, handle, indent=2, default=str)

    orders_path = None
    if execution_orders is not None:
        orders_path = run_dir / "paper_orders.csv"
        execution_orders.to_csv(orders_path)

    weights_path = None
    diagnostics_path = None
    if portfolio_weights is not None:
        weights_path = run_dir / "portfolio_weights.csv"
        portfolio_weights.to_csv(weights_path)
        if portfolio_diagnostics is not None:
            diagnostics_path = run_dir / "portfolio_diagnostics.csv"
            portfolio_diagnostics.to_csv(diagnostics_path)

    artifacts = {
        "run_dir": str(run_dir),
        "config": str(cfg_path),
        "summary": str(summary_path),
        "run_metadata": str(metadata_path),
        "equity_curve": str(equity_path),
        "returns": str(returns_path),
        "gross_returns": str(gross_returns_path),
        "costs": str(costs_path),
        "turnover": str(turnover_path),
    }
    if stage_tails_path is not None:
        artifacts["stage_tails"] = str(stage_tails_path)
    if source_audit_path is not None:
        artifacts["execution_source_audit"] = str(source_audit_path)
    if positions_path is not None:
        artifacts["positions"] = str(positions_path)
    if monitoring_path is not None:
        artifacts["monitoring"] = str(monitoring_path)
    if orders_path is not None:
        artifacts["paper_orders"] = str(orders_path)
    if weights_path is not None:
        artifacts["portfolio_weights"] = str(weights_path)
    if diagnostics_path is not None:
        artifacts["portfolio_diagnostics"] = str(diagnostics_path)
    if mtm_returns_path is not None:
        artifacts["mark_to_market_returns"] = str(mtm_returns_path)
    if mtm_equity_path is not None:
        artifacts["mark_to_market_equity_curve"] = str(mtm_equity_path)

    lab_chart_paths = _write_lab_feature_diagnostic_artifacts(
        run_dir=run_dir,
        data=data,
        cfg=cfg,
    )
    for label, rel_path in lab_chart_paths.items():
        artifacts[label] = str((run_dir / rel_path).resolve())

    trade_chart_paths: dict[str, str] = {}
    trade_artifact_paths: dict[str, str] = {}
    if _should_write_trade_diagnostic_artifacts(cfg):
        trade_chart_paths, trade_artifact_paths = _write_trade_diagnostic_artifacts(
            run_dir=run_dir,
            data=data,
            performance=performance,
            cfg=cfg,
            portfolio_weights=portfolio_weights,
        )
    for label, rel_path in {**trade_chart_paths, **trade_artifact_paths}.items():
        artifacts[label] = str((run_dir / rel_path).resolve())

    lifecycle_artifact_paths = _write_trade_path_lifecycle_artifacts(
        run_dir=run_dir,
        cfg=cfg,
        lifecycle_context=lifecycle_context,
        model_meta=model_meta,
    )
    for label, rel_path in lifecycle_artifact_paths.items():
        artifacts[label] = str((run_dir / rel_path).resolve())

    dense_diagnostic_paths = _write_dense_forecast_diagnostic_artifacts(
        run_dir=run_dir,
        data=data,
        cfg=cfg,
        performance=performance,
        model_meta=model_meta,
        portfolio_weights=portfolio_weights,
    )
    for label, rel_path in dense_diagnostic_paths.items():
        artifacts[label] = str((run_dir / rel_path).resolve())

    forecast_alpha_chart_paths, forecast_alpha_artifact_paths = _write_forecast_alpha_diagnostic_artifacts(
        run_dir=run_dir,
        evaluation=evaluation,
    )
    for label, rel_path in {**forecast_alpha_chart_paths, **forecast_alpha_artifact_paths}.items():
        artifacts[label] = str((run_dir / rel_path).resolve())

    tsfresh_dataset_artifacts = _write_tsfresh_feature_dataset_artifacts(
        run_dir=run_dir,
        data=data,
        model_meta=model_meta,
    )
    for label, rel_path in tsfresh_dataset_artifacts.items():
        if Path(rel_path).is_absolute():
            artifacts[label] = rel_path
        else:
            artifacts[label] = str((run_dir / rel_path).resolve())

    artifacts.update(write_experiment_report_from_run_dir(run_dir))

    manifest = build_artifact_manifest(artifacts)
    manifest_path = run_dir / "artifact_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)
    artifacts["manifest"] = str(manifest_path)

    return artifacts


__all__ = ["save_artifacts", "write_experiment_report_from_run_dir"]
