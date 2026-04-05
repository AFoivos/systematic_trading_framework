from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.experiments.support.notebook_lab import build_feature_signal_combo_frame


def plot_feature_signal_combo(
    frame: pd.DataFrame,
    *,
    title: str,
    feature_cols: list[str],
    signal_cols: list[str],
    feature_weights: Mapping[str, float] | None = None,
    signal_weights: Mapping[str, float] | None = None,
    normalize: bool = True,
    price_col: str = "close",
) -> go.Figure:
    combo_frame = build_feature_signal_combo_frame(
        frame,
        feature_cols=feature_cols,
        signal_cols=signal_cols,
        feature_weights=feature_weights,
        signal_weights=signal_weights,
        normalize=normalize,
    )

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        row_heights=[0.45, 0.30, 0.25],
    )

    if price_col in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[price_col],
                name=price_col,
                mode="lines",
                line={"color": "#111827", "width": 1.8},
            ),
            row=1,
            col=1,
        )

    palette = [
        "#2563eb",
        "#dc2626",
        "#059669",
        "#7c3aed",
        "#ea580c",
        "#0891b2",
        "#be123c",
        "#4f46e5",
    ]
    scaled_columns = [f"{column}__scaled" for column in [*feature_cols, *signal_cols]]
    for idx, scaled_column in enumerate(scaled_columns):
        fig.add_trace(
            go.Scatter(
                x=combo_frame.index,
                y=combo_frame[scaled_column],
                name=scaled_column.replace("__scaled", ""),
                mode="lines",
                line={"color": palette[idx % len(palette)], "width": 1.2},
            ),
            row=2,
            col=1,
        )

    for name, color in [
        ("feature_combo", "#0f766e"),
        ("signal_combo", "#b45309"),
        ("joint_combo", "#7c2d12"),
    ]:
        if name not in combo_frame.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=combo_frame.index,
                y=combo_frame[name],
                name=name,
                mode="lines",
                line={"color": color, "width": 1.8},
            ),
            row=3,
            col=1,
        )

    if "strategy_positions" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_positions"],
                name="strategy_positions",
                mode="lines",
                line={"color": "#1d4ed8", "width": 1.0, "dash": "dot"},
            ),
            row=3,
            col=1,
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, rangeslider={"visible": True})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Scaled Inputs")
    fig.update_yaxes(showgrid=True, row=3, col=1, title_text="Composites")
    return fig


def plot_feature_signal_combo_suite(
    frame: pd.DataFrame,
    combo_specs: list[Mapping[str, Any]],
    *,
    normalize: bool = True,
    price_col: str = "close",
) -> dict[str, go.Figure]:
    figures: dict[str, go.Figure] = {}
    for index, spec in enumerate(combo_specs, start=1):
        name = str(spec.get("name") or spec.get("title") or f"combo_{index}")
        title = str(spec.get("title") or name.replace("_", " ").title())
        figures[name] = plot_feature_signal_combo(
            frame,
            title=title,
            feature_cols=list(spec.get("feature_cols", []) or []),
            signal_cols=list(spec.get("signal_cols", []) or []),
            feature_weights=spec.get("feature_weights"),
            signal_weights=spec.get("signal_weights"),
            normalize=bool(spec.get("normalize", normalize)),
            price_col=str(spec.get("price_col") or price_col),
        )
    return figures
