from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_PALETTE = ["#111827", "#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#be123c"]


def plot_price_indicator_panel(
    frame: pd.DataFrame,
    *,
    price_cols: list[str],
    line_cols: list[str],
    bar_cols: list[str] | None = None,
    title: str,
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.55, 0.45],
    )

    for idx, column in enumerate(price_cols):
        if column not in frame.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                name=column,
                mode="lines",
                line={"width": 1.8 if idx == 0 else 1.2, "color": _PALETTE[idx % len(_PALETTE)]},
            ),
            row=1,
            col=1,
        )

    line_offset = len(price_cols)
    for idx, column in enumerate(line_cols):
        if column not in frame.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                name=column,
                mode="lines",
                line={"width": 1.5, "color": _PALETTE[(line_offset + idx) % len(_PALETTE)]},
            ),
            row=2,
            col=1,
        )

    for column in list(bar_cols or []):
        if column not in frame.columns:
            continue
        fig.add_trace(
            go.Bar(
                x=frame.index,
                y=frame[column],
                name=column,
                opacity=0.45,
                marker_color="#94a3b8",
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
        barmode="relative",
    )
    fig.update_xaxes(showgrid=True, row=1, col=1, rangeslider={"visible": False})
    fig.update_xaxes(showgrid=True, row=2, col=1, rangeslider={"visible": False})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Indicator")
    return fig
