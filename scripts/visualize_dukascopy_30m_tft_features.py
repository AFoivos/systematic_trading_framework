#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.experiments.runner import _load_asset_frames
from src.models.runtime import infer_feature_columns
from src.plots import plot_price_with_feature_combo, plot_price_with_features, plotly_chart_config
from src.utils.config import load_experiment_config


DEFAULT_CONFIG = "config/experiments/dukascopy_30m_xauusd_tft_feature_forecast_v1.yaml"
DEFAULT_OUTPUT_DIR = "output/visualizations/dukascopy_30m_xauusd_tft_feature_forecast_v1"
CORE_FEATURE_CANDIDATES = (
    "close_logret",
    "vol_rolling_24",
    "vol_ewma_24",
    "close_over_ema_24",
    "close_logret_norm_mom_24",
    "regime_vol_ratio_24_192",
    "regime_trend_ratio_24_96",
    "hour_sin_24",
    "hour_cos_24",
    "spread_bps",
)


def _write_html(fig: go.Figure, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        str(path),
        include_plotlyjs="cdn",
        full_html=True,
        config=plotly_chart_config(),
    )
    return str(path)


def _select_existing(columns: list[str], candidates: tuple[str, ...], *, fallback_count: int) -> list[str]:
    selected = [column for column in candidates if column in columns]
    if selected:
        return selected
    return columns[:fallback_count]


def _resolve_feature_columns(feature_frame: pd.DataFrame, cfg: dict[str, object]) -> list[str]:
    model_cfg = dict(cfg.get("model", {}) or {})
    selected = infer_feature_columns(
        feature_frame,
        explicit_cols=model_cfg.get("feature_cols"),
        feature_selectors=model_cfg.get("feature_selectors"),
        exclude={"open", "high", "low", "close", "volume"},
    )
    numeric = feature_frame.select_dtypes(include=["number"]).columns
    numeric_set = {str(column) for column in numeric}
    return [column for column in selected if column in numeric_set]


def _availability_figure(frame: pd.DataFrame, feature_cols: list[str]) -> go.Figure:
    availability = frame[feature_cols].notna().mean().sort_values(ascending=True)
    shown = availability.head(40)
    fig = go.Figure(
        go.Bar(
            x=shown.to_numpy(dtype=float),
            y=shown.index.tolist(),
            orientation="h",
            marker={"color": "#2563eb"},
        )
    )
    fig.update_layout(
        title="Feature Availability",
        template="plotly_white",
        xaxis_title="Non-null fraction",
        yaxis_title="Feature",
        margin={"l": 180, "r": 24, "t": 60, "b": 40},
    )
    return fig


def _correlation_figure(frame: pd.DataFrame, feature_cols: list[str]) -> go.Figure:
    candidates = frame[feature_cols].dropna(axis=1, how="all")
    variance = candidates.var(numeric_only=True).sort_values(ascending=False)
    shown_cols = [str(column) for column in variance.head(24).index]
    corr = candidates[shown_cols].corr()
    fig = go.Figure(
        go.Heatmap(
            z=corr.to_numpy(dtype=float),
            x=corr.columns.tolist(),
            y=corr.index.tolist(),
            zmin=-1.0,
            zmax=1.0,
            colorscale="RdBu",
            reversescale=True,
            colorbar={"title": "corr"},
        )
    )
    fig.update_layout(
        title="Feature Correlation",
        template="plotly_white",
        margin={"l": 160, "r": 24, "t": 60, "b": 140},
    )
    return fig


def build_feature_visualizations(
    *,
    config_path: str,
    asset: str | None,
    output_dir: str,
    tail: int,
) -> dict[str, object]:
    cfg = load_experiment_config(config_path)
    raw_frames, storage_meta = _load_asset_frames(dict(cfg["data"]))
    resolved_asset = str(asset or cfg["data"].get("symbol") or next(iter(sorted(raw_frames))))
    if resolved_asset not in raw_frames:
        raise KeyError(f"Asset '{resolved_asset}' not loaded. Available assets: {sorted(raw_frames)}")

    raw_frame = raw_frames[resolved_asset]
    feature_frame = apply_feature_steps(
        raw_frame,
        list(cfg.get("features", []) or []),
        asset=resolved_asset,
    )
    feature_cols = _resolve_feature_columns(feature_frame, cfg)
    if not feature_cols:
        raise ValueError("No numeric model feature columns resolved for visualization.")

    plot_frame = feature_frame.tail(int(tail)).copy() if int(tail) > 0 else feature_frame.copy()
    visible_features = [column for column in feature_cols if column in plot_frame.columns]
    core_features = _select_existing(visible_features, CORE_FEATURE_CANDIDATES, fallback_count=8)
    combo_features = core_features[: min(8, len(core_features))]

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    feature_tail_path = output_root / "feature_snapshot_tail.csv"
    plot_frame[["open", "high", "low", "close", "volume", *visible_features]].to_csv(feature_tail_path)

    artifacts: dict[str, object] = {
        "asset": resolved_asset,
        "rows": int(len(feature_frame)),
        "visible_rows": int(len(plot_frame)),
        "resolved_feature_count": int(len(feature_cols)),
        "storage": storage_meta,
        "feature_snapshot_tail": str(feature_tail_path),
    }

    artifacts["price_core_features"] = _write_html(
        plot_price_with_features(
            plot_frame,
            title=f"{resolved_asset} 30m Price and Core TFT Features",
            feature_cols=core_features,
            normalize=True,
            price_col="close",
        ),
        output_root / "price_core_features.html",
    )

    if len(combo_features) >= 2:
        artifacts["price_feature_combo"] = _write_html(
            plot_price_with_feature_combo(
                plot_frame,
                title=f"{resolved_asset} 30m TFT Feature Combo",
                feature_cols=combo_features,
                normalize=True,
                price_col="close",
            ),
            output_root / "price_feature_combo.html",
        )

    artifacts["feature_availability"] = _write_html(
        _availability_figure(feature_frame, feature_cols),
        output_root / "feature_availability.html",
    )
    artifacts["feature_correlation"] = _write_html(
        _correlation_figure(plot_frame, visible_features),
        output_root / "feature_correlation.html",
    )

    return artifacts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TFT feature visualizations for 30m Dukascopy data.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Experiment YAML to use for data/features.")
    parser.add_argument("--asset", default=None, help="Asset symbol to visualize. Defaults to config data.symbol.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for HTML/chart artifacts.")
    parser.add_argument("--tail", type=int, default=2000, help="Last N rows to show in time-series charts; 0 keeps all rows.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = build_feature_visualizations(
        config_path=args.config,
        asset=args.asset,
        output_dir=args.output_dir,
        tail=args.tail,
    )
    print(json.dumps(artifacts, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
