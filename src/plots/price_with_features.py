from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ._series import coerce_numeric_series, zscore_series


def plot_price_with_features(
    frame: pd.DataFrame,
    *,
    title: str,
    feature_cols: list[str],
    normalize: bool = True,
    price_col: str = "close",
) -> go.Figure:
    if not feature_cols:
        raise ValueError("Select at least one feature column to plot against price.")

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.55, 0.45],
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
        series = coerce_numeric_series(frame, feature_column)
        y = zscore_series(series) if normalize else series
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=y,
                name=feature_column,
                mode="lines",
                line={"color": palette[idx % len(palette)], "width": 1.2},
            ),
            row=2,
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
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Features (scaled)" if normalize else "Features")
    return fig
