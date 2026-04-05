from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_price_signal_probability(
    frame: pd.DataFrame,
    *,
    title: str,
    signal_col: str = "signal_prob_threshold",
    prob_col: str = "pred_prob",
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.65, 0.35],
    )

    if "close" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["close"],
                name="close",
                mode="lines",
                line={"color": "#1f77b4", "width": 1.8},
            ),
            row=1,
            col=1,
        )

    if "strategy_positions" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_positions"],
                name="position",
                mode="lines",
                line={"color": "#d62728", "width": 1.4},
            ),
            row=2,
            col=1,
        )

    if signal_col in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[signal_col],
                name=signal_col,
                mode="lines",
                line={"color": "#2ca02c", "width": 1.2},
            ),
            row=2,
            col=1,
        )

    if prob_col in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[prob_col],
                name=prob_col,
                mode="lines",
                line={"color": "#9467bd", "width": 1.1},
            ),
            row=2,
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
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Signal / Position")
    return fig
