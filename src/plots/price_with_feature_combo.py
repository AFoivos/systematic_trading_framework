from __future__ import annotations

from typing import Mapping

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.experiments.support.notebook_lab import build_feature_combo_frame


def plot_price_with_feature_combo(
    frame: pd.DataFrame,
    *,
    title: str,
    feature_cols: list[str],
    feature_weights: Mapping[str, float] | None = None,
    normalize: bool = True,
    price_col: str = "close",
) -> go.Figure:
    combo_frame = build_feature_combo_frame(
        frame,
        feature_cols=feature_cols,
        feature_weights=feature_weights,
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

    palette = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#be123c", "#4f46e5"]
    for idx, feature_column in enumerate(feature_cols):
        fig.add_trace(
            go.Scatter(
                x=combo_frame.index,
                y=combo_frame[f"{feature_column}__scaled"],
                name=feature_column,
                mode="lines",
                line={"color": palette[idx % len(palette)], "width": 1.2},
            ),
            row=2,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=combo_frame.index,
            y=combo_frame["feature_combo"],
            name="feature_combo",
            mode="lines",
            line={"color": "#0f766e", "width": 1.8},
        ),
        row=3,
        col=1,
    )

    fig.update_layout(
        title=title,
        template="plotly_white",
        dragmode="zoom",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, row=1, col=1, rangeslider={"visible": False})
    fig.update_xaxes(showgrid=True, row=2, col=1, rangeslider={"visible": False})
    fig.update_xaxes(showgrid=True, row=3, col=1, rangeslider={"visible": False})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Features (scaled)")
    fig.update_yaxes(showgrid=True, row=3, col=1, title_text="Feature Combo")
    return fig
