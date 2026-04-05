from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_equity_drawdown(frame: pd.DataFrame, *, title: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.65, 0.35],
    )

    if "strategy_equity" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_equity"],
                name="equity",
                mode="lines",
                line={"color": "#111827", "width": 2.0},
            ),
            row=1,
            col=1,
        )

    if "strategy_drawdown" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_drawdown"],
                name="drawdown",
                mode="lines",
                fill="tozeroy",
                line={"color": "#ef4444", "width": 1.2},
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
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Equity")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Drawdown")
    return fig
