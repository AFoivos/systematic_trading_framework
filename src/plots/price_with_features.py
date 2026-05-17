from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ._series import coerce_numeric_series, zscore_series


DEFAULT_MAX_PLOT_POINTS = 12_000


def _sample_frame_for_plot(frame: pd.DataFrame, max_plot_points: int | None) -> pd.DataFrame:
    if max_plot_points is None or max_plot_points <= 0 or len(frame) <= max_plot_points:
        return frame
    positions = np.linspace(0, len(frame) - 1, num=max_plot_points, dtype=int)
    return frame.iloc[np.unique(positions)].copy()


def _visibility_for_single_feature(
    *,
    trace_count: int,
    feature_trace_indices: list[int],
    selected_trace_idx: int | None,
    show_all_features: bool = False,
) -> list[bool]:
    visible = [True] * trace_count
    for trace_idx in feature_trace_indices:
        visible[trace_idx] = show_all_features or trace_idx == selected_trace_idx
    return visible


def plot_price_with_features(
    frame: pd.DataFrame,
    *,
    title: str,
    feature_cols: list[str],
    price_overlay_cols: list[str] | None = None,
    normalize: bool = True,
    price_col: str = "close",
    max_plot_points: int | None = DEFAULT_MAX_PLOT_POINTS,
    height: int = 720,
    initial_features_visible: bool = True,
) -> go.Figure:
    price_overlay_cols = list(price_overlay_cols or [])
    if not feature_cols and not price_overlay_cols:
        raise ValueError("Select at least one feature column to plot against price.")

    sampled = _sample_frame_for_plot(frame, max_plot_points=max_plot_points)
    display_title = title
    if len(sampled) < len(frame):
        display_title = f"{title} (displaying {len(sampled)}/{len(frame)} bars)"

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.055,
        row_heights=[0.5, 0.5],
        subplot_titles=(f"{price_col} with price-scale features", "Scaled features"),
    )
    feature_visibility: bool | str = True if initial_features_visible else "legendonly"

    if price_col in sampled.columns:
        fig.add_trace(
            go.Scatter(
                x=sampled.index,
                y=sampled[price_col],
                name=price_col,
                mode="lines",
                line={"color": "#111827", "width": 1.8},
                hovertemplate=f"{price_col}=%{{y:.6g}}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    palette = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#be123c", "#4f46e5"]
    overlay_palette = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#be123c", "#4f46e5"]
    feature_trace_indices: list[int] = []
    feature_trace_labels: list[tuple[int, str]] = []
    for idx, feature_column in enumerate(price_overlay_cols):
        series = coerce_numeric_series(sampled, feature_column)
        trace_idx = len(fig.data)
        fig.add_trace(
            go.Scatter(
                x=sampled.index,
                y=series,
                name=feature_column,
                mode="lines",
                visible=feature_visibility,
                line={"color": overlay_palette[idx % len(overlay_palette)], "width": 1.15},
                hovertemplate=f"{feature_column}=%{{y:.6g}}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        feature_trace_indices.append(trace_idx)
        feature_trace_labels.append((trace_idx, feature_column))

    for idx, feature_column in enumerate(feature_cols):
        series = coerce_numeric_series(sampled, feature_column)
        y = zscore_series(series) if normalize else series
        trace_idx = len(fig.data)
        fig.add_trace(
            go.Scatter(
                x=sampled.index,
                y=y,
                name=feature_column,
                mode="lines",
                visible=feature_visibility,
                line={"color": palette[idx % len(palette)], "width": 1.2},
                customdata=series.to_numpy(),
                hovertemplate=(
                    f"{feature_column}<br>"
                    + ("z=%{y:.4f}<br>raw=%{customdata:.6g}" if normalize else "value=%{y:.6g}")
                    + "<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )
        feature_trace_indices.append(trace_idx)
        feature_trace_labels.append((trace_idx, feature_column))

    updatemenus = []
    if feature_trace_indices:
        trace_count = len(fig.data)
        buttons = [
            {
                "label": "Hide features",
                "method": "update",
                "args": [
                    {
                        "visible": _visibility_for_single_feature(
                            trace_count=trace_count,
                            feature_trace_indices=feature_trace_indices,
                            selected_trace_idx=None,
                        )
                    }
                ],
            },
            {
                "label": "Show all features",
                "method": "update",
                "args": [
                    {
                        "visible": _visibility_for_single_feature(
                            trace_count=trace_count,
                            feature_trace_indices=feature_trace_indices,
                            selected_trace_idx=None,
                            show_all_features=True,
                        )
                    }
                ],
            },
        ]
        buttons.extend(
            {
                "label": label,
                "method": "update",
                "args": [
                    {
                        "visible": _visibility_for_single_feature(
                            trace_count=trace_count,
                            feature_trace_indices=feature_trace_indices,
                            selected_trace_idx=trace_idx,
                        )
                    }
                ],
            }
            for trace_idx, label in feature_trace_labels
        )
        updatemenus.append(
            {
                "type": "dropdown",
                "direction": "down",
                "x": 0.0,
                "xanchor": "left",
                "y": 1.16,
                "yanchor": "top",
                "buttons": buttons,
                "active": 0 if not initial_features_visible else 1,
            }
        )

    fig.update_layout(
        title=display_title,
        template="plotly_white",
        dragmode="zoom",
        hovermode="x unified",
        height=height,
        legend={"orientation": "v", "yanchor": "top", "y": 1.0, "xanchor": "left", "x": 1.01, "groupclick": "toggleitem"},
        margin={"l": 50, "r": 240, "t": 88, "b": 34},
        updatemenus=updatemenus,
    )
    fig.update_xaxes(showgrid=True, row=1, col=1, rangeslider={"visible": False})
    fig.update_xaxes(showgrid=True, row=2, col=1, rangeslider={"visible": False})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text=price_col)
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Features (z-score)" if normalize else "Features")
    return fig
