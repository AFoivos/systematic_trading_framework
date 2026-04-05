from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_positions_turnover(frame: pd.DataFrame, *, title: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.55, 0.45],
    )

    if "strategy_positions" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_positions"],
                name="position",
                mode="lines",
                line={"color": "#2563eb", "width": 1.5},
            ),
            row=1,
            col=1,
        )

    if "strategy_turnover" in frame.columns:
        fig.add_trace(
            go.Bar(
                x=frame.index,
                y=frame["strategy_turnover"],
                name="turnover",
                marker_color="#f59e0b",
                opacity=0.75,
            ),
            row=2,
            col=1,
        )

    if "strategy_costs" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_costs"],
                name="costs",
                mode="lines",
                line={"color": "#b91c1c", "width": 1.2},
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
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Position")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Turnover / Costs")
    return fig
