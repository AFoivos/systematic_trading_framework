from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def plot_returns_distribution(frame: pd.DataFrame, *, title: str) -> go.Figure:
    returns = frame.get("strategy_net_returns", pd.Series(dtype=float)).dropna()
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=returns,
            nbinsx=80,
            name="net returns",
            marker_color="#0f766e",
            opacity=0.8,
        )
    )
    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        bargap=0.05,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, title_text="Strategy Net Return")
    fig.update_yaxes(showgrid=True, title_text="Count")
    return fig
