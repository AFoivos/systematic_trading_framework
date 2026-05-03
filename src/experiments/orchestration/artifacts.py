from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.backtesting.engine import BacktestResult
from src.experiments.orchestration.common import data_stats_payload, redact_sensitive_values, resolved_feature_columns
from src.experiments.orchestration.reporting import build_experiment_report_markdown, render_markdown_report_html
from src.experiments.orchestration.trade_diagnostics import (
    build_trade_event_frame,
    plot_trade_diagnostics,
    plotly_chart_config,
)
from src.portfolio import PortfolioPerformance
from src.utils.run_metadata import build_artifact_manifest


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
    target_cfg = dict(dict(cfg.get("model", {}) or {}).get("target", {}) or {})
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
            f"{label_col}_upper_barrier"
            if label_col and f"{label_col}_upper_barrier" in frame.columns
            else _first_existing_column(
                frame,
                ["manual_take_profit_price", "take_profit_price", "target_price", "r_target_take_profit_price"],
            )
        ),
        "lower_barrier_col": (
            f"{label_col}_lower_barrier"
            if label_col and f"{label_col}_lower_barrier" in frame.columns
            else _first_existing_column(frame, ["manual_stop_loss_price", "stop_loss_price", "r_target_stop_price"])
        ),
        "hit_step_col": (
            f"{label_col}_hit_step"
            if label_col and f"{label_col}_hit_step" in frame.columns
            else _first_existing_column(frame, ["manual_hit_step", "r_target_hit_step"])
        ),
        "hit_type_col": (
            f"{label_col}_hit_type"
            if label_col and f"{label_col}_hit_type" in frame.columns
            else _first_existing_column(frame, ["manual_exit_reason", "r_target_exit_reason", "r_target_hit_type"])
        ),
        "r_col": r_col,
        "entry_price_col": _first_existing_column(frame, ["r_target_entry_price"]),
        "exit_price_col": _first_existing_column(frame, ["r_target_exit_price"]),
        "target_r_col": _first_existing_column(frame, ["r_target_trade_r", "r_target_oriented_r"]),
        "target_entry_price_col": _first_existing_column(frame, ["r_target_entry_price"]),
        "target_exit_price_col": _first_existing_column(frame, ["r_target_exit_price"]),
        "target_stop_col": _first_existing_column(frame, ["r_target_stop_price"]),
        "target_take_profit_col": _first_existing_column(frame, ["r_target_take_profit_price"]),
        "target_exit_reason_col": _first_existing_column(frame, ["r_target_exit_reason", "r_target_hit_type"]),
    }


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
                    "r_target_hit_type",
                    "r_target_hit_step",
                    "roc_12",
                    "regime_vol_ratio_z_24_168",
                    "close_z",
                    "close_open_ratio",
                    "manual_conviction_score",
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

        safe_asset = _safe_asset_filename(asset)
        html_path = report_assets_dir / f"trade_diagnostics_{safe_asset}.html"
        fig = plot_trade_diagnostics(
            frame,
            positions=positions,
            asset=asset,
            title=f"Trade Diagnostics: {asset}",
            signal_col=columns["signal_col"],
            target_col=columns["target_col"],
            upper_barrier_col=columns["upper_barrier_col"],
            lower_barrier_col=columns["lower_barrier_col"],
            hit_step_col=columns["hit_step_col"],
            hit_type_col=columns["hit_type_col"],
            r_col=columns["r_col"],
            entry_price_col=columns["entry_price_col"],
            exit_price_col=columns["exit_price_col"],
            target_r_col=columns["target_r_col"],
            target_entry_price_col=columns["target_entry_price_col"],
            target_exit_price_col=columns["target_exit_price_col"],
            target_stop_col=columns["target_stop_col"],
            target_take_profit_col=columns["target_take_profit_col"],
            target_exit_reason_col=columns["target_exit_reason_col"],
            price_col="close",
        )
        fig.write_html(
            html_path,
            include_plotlyjs="cdn",
            full_html=True,
            config=plotly_chart_config(),
        )
        chart_paths[f"trade_diagnostics_{safe_asset}"] = str(html_path.relative_to(run_dir))

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
    for trade_plot_path in sorted(report_assets_dir.glob("trade_diagnostics_*.html")):
        chart_paths[trade_plot_path.stem] = str(trade_plot_path.relative_to(run_dir))

    if not equity_curve.empty:
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

    if not net_returns.empty and not gross_returns.empty:
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

    if not positions.empty and not turnover.empty:
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
    if fold_summaries:
        fold_path = report_assets_dir / "fold_net_pnl.png"
        _save_fold_bar_chart(fold_path, fold_summaries=fold_summaries)
        if fold_path.exists():
            chart_paths["fold_net_pnl"] = str(fold_path.relative_to(run_dir))

    if not portfolio_weights.empty:
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
    report_html_path = run_dir / "report.html"
    artifact_paths = {
        "report_markdown": "report.md",
        "report_html": "report.html",
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
    artifact_paths.update(model_artifact_paths)
    if (run_dir / "stage_tails.json").exists():
        artifact_paths["stage_tails"] = "stage_tails.json"
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
    report_html_path.write_text(
        render_markdown_report_html(report_markdown, title=f"Experiment Report: {cfg.get('logging', {}).get('run_name', run_dir.name)}"),
        encoding="utf-8",
    )

    report_artifacts = {
        "report": str(report_path),
        "report_html": str(report_html_path),
    }
    for label, rel_path in chart_paths.items():
        report_artifacts[label] = str((run_dir / rel_path).resolve())
    if "trade_events" in artifact_paths:
        report_artifacts["trade_events"] = str((run_dir / artifact_paths["trade_events"]).resolve())
    if "target_events" in artifact_paths:
        report_artifacts["target_events"] = str((run_dir / artifact_paths["target_events"]).resolve())
    if "trades" in artifact_paths:
        report_artifacts["trades"] = str((run_dir / artifact_paths["trades"]).resolve())
    for label, rel_path in model_artifact_paths.items():
        report_artifacts[label] = str((run_dir / rel_path).resolve())
    return report_artifacts


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

    summary_path = run_dir / "summary.json"
    payload = {
        "summary": evaluation.get("primary_summary", performance.summary),
        "timeline_summary": performance.summary,
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

    trade_chart_paths, trade_artifact_paths = _write_trade_diagnostic_artifacts(
        run_dir=run_dir,
        data=data,
        performance=performance,
        cfg=cfg,
        portfolio_weights=portfolio_weights,
    )
    for label, rel_path in {**trade_chart_paths, **trade_artifact_paths}.items():
        artifacts[label] = str((run_dir / rel_path).resolve())

    artifacts.update(write_experiment_report_from_run_dir(run_dir))

    manifest = build_artifact_manifest(artifacts)
    manifest_path = run_dir / "artifact_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)
    artifacts["manifest"] = str(manifest_path)

    return artifacts


__all__ = ["save_artifacts", "write_experiment_report_from_run_dir"]
