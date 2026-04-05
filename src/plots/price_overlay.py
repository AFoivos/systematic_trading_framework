from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

_PALETTE = ["#111827", "#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#be123c"]


def plot_price_overlay(
    frame: pd.DataFrame,
    columns: list[str],
    *,
    title: str,
) -> go.Figure:
    fig = go.Figure()
    for idx, column in enumerate(columns):
        if column not in frame.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                name=column,
                mode="lines",
                line={"width": 1.8 if idx == 0 else 1.2, "color": _PALETTE[idx % len(_PALETTE)]},
            )
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        dragmode="zoom",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, rangeslider={"visible": False})
    fig.update_yaxes(showgrid=True)
    return fig
