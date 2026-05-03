from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


DEFAULT_MAX_PLOT_POINTS = 12_000


def _as_aligned_series(
    values: pd.Series | None,
    index: pd.Index,
    *,
    name: str,
) -> pd.Series:
    if values is None:
        return pd.Series(0.0, index=index, name=name, dtype=float)
    series = pd.Series(values, copy=False).astype(float)
    return series.reindex(index).fillna(0.0).rename(name)


def _price_at(frame: pd.DataFrame, timestamp: Any, *, price_col: str) -> float:
    if price_col in frame.columns and timestamp in frame.index:
        return float(frame.loc[timestamp, price_col])
    return np.nan


def _side_label(value: float) -> str:
    if value > 0.0:
        return "long"
    if value < 0.0:
        return "short"
    return "flat"


def _optional_value(frame: pd.DataFrame, timestamp: Any, column: str | None) -> Any:
    if column and column in frame.columns and timestamp in frame.index:
        return frame.loc[timestamp, column]
    return np.nan


def _numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _resolve_feature_panel_columns(
    frame: pd.DataFrame,
    feature_panel_cols: list[str] | None,
) -> list[str]:
    ordered: list[str] = []
    for column in list(feature_panel_cols or []):
        if not isinstance(column, str) or not column.strip():
            continue
        if column in ordered or column not in frame.columns:
            continue
        if _numeric_series(frame, column).notna().sum() <= 0:
            continue
        ordered.append(column)
    return ordered


def _feature_panel_hovertemplate() -> str:
    return "timestamp=%{x}<br>feature=%{meta}<br>value=%{y:.6f}<extra></extra>"


def _sample_frame_for_plot(frame: pd.DataFrame, max_plot_points: int | None) -> pd.DataFrame:
    if max_plot_points is None or max_plot_points <= 0 or len(frame) <= max_plot_points:
        return frame
    sampled_positions = np.unique(np.linspace(0, len(frame) - 1, num=int(max_plot_points), dtype=int))
    return frame.iloc[sampled_positions].copy()


def _lookup_timestamp_for_event(
    frame: pd.DataFrame,
    timestamp: Any,
    *,
    event_type: str,
    columns: list[str | None],
) -> Any:
    if event_type != "entry" or timestamp not in frame.index:
        return timestamp
    if any(pd.notna(_optional_value(frame, timestamp, column)) for column in columns if column):
        return timestamp
    try:
        pos = int(frame.index.get_loc(timestamp))
    except (KeyError, TypeError, ValueError):
        return timestamp
    if pos <= 0:
        return timestamp
    previous_timestamp = frame.index[pos - 1]
    if any(pd.notna(_optional_value(frame, previous_timestamp, column)) for column in columns if column):
        return previous_timestamp
    return timestamp


def build_trade_event_frame(
    frame: pd.DataFrame,
    *,
    positions: pd.Series | None,
    asset: str,
    signal_col: str | None = None,
    target_col: str | None = None,
    upper_barrier_col: str | None = None,
    lower_barrier_col: str | None = None,
    hit_step_col: str | None = None,
    hit_type_col: str | None = None,
    r_col: str | None = None,
    entry_price_col: str | None = None,
    exit_price_col: str | None = None,
    target_r_col: str | None = None,
    target_entry_price_col: str | None = None,
    target_exit_price_col: str | None = None,
    target_stop_col: str | None = None,
    target_take_profit_col: str | None = None,
    target_exit_reason_col: str | None = None,
    price_col: str = "close",
) -> pd.DataFrame:
    """
    Derive timestamp-level entry/exit diagnostics from the executed position path.

    A trade event is an exposure state transition: flat-to-exposed, exposed-to-flat, or
    sign reversal. Position resizes that keep the same non-zero sign are omitted so the
    table stays focused on entries/exits.
    """
    if frame.empty:
        return pd.DataFrame()

    aligned_positions = _as_aligned_series(positions, frame.index, name="position")
    previous = aligned_positions.shift(1).fillna(0.0)
    current = aligned_positions.fillna(0.0)

    rows: list[dict[str, Any]] = []
    for timestamp in frame.index:
        prev_pos = float(previous.loc[timestamp])
        curr_pos = float(current.loc[timestamp])
        if prev_pos == curr_pos:
            continue

        prev_sign = float(np.sign(prev_pos))
        curr_sign = float(np.sign(curr_pos))
        event_types: list[tuple[str, float, float]] = []
        if prev_sign == 0.0 and curr_sign != 0.0:
            event_types.append(("entry", prev_pos, curr_pos))
        elif prev_sign != 0.0 and curr_sign == 0.0:
            event_types.append(("exit", prev_pos, curr_pos))
        elif prev_sign != 0.0 and curr_sign != 0.0 and prev_sign != curr_sign:
            event_types.append(("exit", prev_pos, 0.0))
            event_types.append(("entry", 0.0, curr_pos))

        if not event_types:
            continue

        for event_type, before, after in event_types:
            lookup_timestamp = _lookup_timestamp_for_event(
                frame,
                timestamp,
                event_type=event_type,
                columns=[
                    signal_col,
                    target_col,
                    upper_barrier_col,
                    lower_barrier_col,
                    hit_step_col,
                    hit_type_col,
                    r_col,
                    entry_price_col,
                    exit_price_col,
                ],
            )
            upper = _optional_value(frame, lookup_timestamp, upper_barrier_col)
            lower = _optional_value(frame, lookup_timestamp, lower_barrier_col)
            hit_step = _optional_value(frame, lookup_timestamp, hit_step_col)
            target_exit_timestamp = pd.NaT
            if pd.notna(hit_step):
                try:
                    target_pos = frame.index.get_loc(timestamp) + int(hit_step)
                    if 0 <= target_pos < len(frame.index):
                        target_exit_timestamp = frame.index[target_pos]
                except (KeyError, TypeError, ValueError):
                    target_exit_timestamp = pd.NaT
            active_side = after if event_type == "entry" else before
            side = _side_label(float(active_side))
            if side == "short":
                take_profit = lower
                stop_loss = upper
            else:
                take_profit = upper
                stop_loss = lower
            rows.append(
                {
                    "timestamp": timestamp,
                    "asset": asset,
                    "event_type": event_type,
                    "side": side,
                    "position_before": before,
                    "position_after": after,
                    "price": _price_at(frame, timestamp, price_col=price_col),
                    "signal": _optional_value(frame, lookup_timestamp, signal_col),
                    "target": _optional_value(frame, lookup_timestamp, target_col),
                    "target_hit_type": _optional_value(frame, lookup_timestamp, hit_type_col),
                    "target_hit_step": hit_step,
                    "target_exit_timestamp": target_exit_timestamp,
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "upper_barrier": upper,
                    "lower_barrier": lower,
                    "trade_r": _optional_value(frame, lookup_timestamp, r_col),
                    "target_entry_price": _optional_value(frame, lookup_timestamp, entry_price_col),
                    "target_exit_price": _optional_value(frame, lookup_timestamp, exit_price_col),
                    "target_lookup_timestamp": lookup_timestamp,
                }
            )

    return pd.DataFrame(rows)


def _customdata_for_events(events: pd.DataFrame) -> np.ndarray:
    if events.empty:
        return np.empty((0, 11), dtype=object)
    return np.column_stack(
        [
            events["asset"].astype(str),
            events["event_type"].astype(str),
            events["side"].astype(str),
            events["signal"].astype(str),
            events["target"].astype(str),
            events["take_profit"].astype(str),
            events["stop_loss"].astype(str),
            events["target_hit_type"].astype(str),
            events["trade_r"].astype(str),
            events["target_entry_price"].astype(str),
            events["target_exit_price"].astype(str),
        ]
    )


def _barrier_segments(
    events: pd.DataFrame,
    *,
    value_col: str,
    default_bars: int = 8,
) -> tuple[list[Any], list[float]]:
    xs: list[Any] = []
    ys: list[float] = []
    if events.empty or value_col not in events.columns:
        return xs, ys
    for _, row in events.loc[events["event_type"] == "entry"].iterrows():
        level = pd.to_numeric(pd.Series([row.get(value_col)]), errors="coerce").iloc[0]
        if not np.isfinite(level):
            continue
        start = row["timestamp"]
        end = row.get("target_exit_timestamp")
        if pd.isna(end):
            end = start + pd.Timedelta(minutes=30 * default_bars) if isinstance(start, pd.Timestamp) else start
        xs.extend([start, end, None])
        ys.extend([float(level), float(level), np.nan])
    return xs, ys


def plot_trade_diagnostics(
    frame: pd.DataFrame,
    *,
    positions: pd.Series | None,
    asset: str,
    title: str,
    signal_col: str | None = None,
    target_col: str | None = None,
    upper_barrier_col: str | None = None,
    lower_barrier_col: str | None = None,
    hit_step_col: str | None = None,
    hit_type_col: str | None = None,
    r_col: str | None = None,
    entry_price_col: str | None = None,
    exit_price_col: str | None = None,
    target_r_col: str | None = None,
    target_entry_price_col: str | None = None,
    target_exit_price_col: str | None = None,
    target_stop_col: str | None = None,
    target_take_profit_col: str | None = None,
    target_exit_reason_col: str | None = None,
    feature_panel_cols: list[str] | None = None,
    price_col: str = "close",
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    max_plot_points: int | None = DEFAULT_MAX_PLOT_POINTS,
) -> go.Figure:
    frame = frame.copy().sort_index()
    positions_aligned = _as_aligned_series(positions, frame.index, name="position")
    resolved_feature_panels = _resolve_feature_panel_columns(frame, feature_panel_cols)
    events = build_trade_event_frame(
        frame,
        positions=positions_aligned,
        asset=asset,
        signal_col=signal_col,
        target_col=target_col,
        upper_barrier_col=upper_barrier_col,
        lower_barrier_col=lower_barrier_col,
        hit_step_col=hit_step_col,
        hit_type_col=hit_type_col,
        r_col=r_col,
        entry_price_col=entry_price_col,
        exit_price_col=exit_price_col,
        price_col=price_col,
    )
    plot_frame = _sample_frame_for_plot(frame, max_plot_points)
    plot_positions = positions_aligned.reindex(plot_frame.index).fillna(0.0).rename("position")

    feature_panel_count = len(resolved_feature_panels)
    row_count = 2 + feature_panel_count
    if feature_panel_count <= 0:
        row_heights = [0.68, 0.32]
    else:
        price_height = 0.48
        signal_height = 0.16
        feature_height = max((1.0 - price_height - signal_height) / float(feature_panel_count), 0.06)
        row_heights = [price_height, signal_height, *([feature_height] * feature_panel_count)]
    subplot_titles = [
        "Price / Trade Events / Barriers",
        "Signal / Position / Target",
        *[f"Feature Panel {idx + 1}" for idx in range(feature_panel_count)],
    ]

    fig = make_subplots(
        rows=row_count,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03 if feature_panel_count <= 2 else 0.02,
        row_heights=row_heights,
        subplot_titles=tuple(subplot_titles),
    )

    has_ohlc = all(col in plot_frame.columns for col in (open_col, high_col, low_col, price_col))
    if has_ohlc:
        fig.add_trace(
            go.Candlestick(
                x=plot_frame.index,
                open=plot_frame[open_col],
                high=plot_frame[high_col],
                low=plot_frame[low_col],
                close=plot_frame[price_col],
                name="OHLC",
            ),
            row=1,
            col=1,
        )
    elif price_col in plot_frame.columns:
        fig.add_trace(
            go.Scatter(
                x=plot_frame.index,
                y=plot_frame[price_col],
                name=price_col,
                mode="lines",
                line={"color": "#111827", "width": 1.6},
            ),
            row=1,
            col=1,
        )

    entry_events = events.loc[events["event_type"] == "entry"] if not events.empty else pd.DataFrame()
    exit_events = events.loc[events["event_type"] == "exit"] if not events.empty else pd.DataFrame()
    if not entry_events.empty:
        fig.add_trace(
            go.Scatter(
                x=entry_events["timestamp"],
                y=entry_events["price"],
                name="entries",
                mode="markers",
                marker={"symbol": "triangle-up", "size": 10, "color": "#16a34a"},
                customdata=_customdata_for_events(entry_events),
                hovertemplate=(
                    "timestamp=%{x}<br>asset=%{customdata[0]}<br>event=%{customdata[1]}<br>"
                    "side=%{customdata[2]}<br>price=%{y:.6f}<br>signal=%{customdata[3]}<br>"
                    "target=%{customdata[4]}<br>take_profit=%{customdata[5]}<br>"
                    "stop_loss=%{customdata[6]}<br>target_hit_type=%{customdata[7]}<br>"
                    "trade_r=%{customdata[8]}<br>target_entry_price=%{customdata[9]}<br>"
                    "target_exit_price=%{customdata[10]}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )
    if not exit_events.empty:
        fig.add_trace(
            go.Scatter(
                x=exit_events["timestamp"],
                y=exit_events["price"],
                name="exits",
                mode="markers",
                marker={"symbol": "x", "size": 10, "color": "#dc2626"},
                customdata=_customdata_for_events(exit_events),
                hovertemplate=(
                    "timestamp=%{x}<br>asset=%{customdata[0]}<br>event=%{customdata[1]}<br>"
                    "side=%{customdata[2]}<br>price=%{y:.6f}<br>signal=%{customdata[3]}<br>"
                    "target=%{customdata[4]}<br>take_profit=%{customdata[5]}<br>"
                    "stop_loss=%{customdata[6]}<br>target_hit_type=%{customdata[7]}<br>"
                    "trade_r=%{customdata[8]}<br>target_entry_price=%{customdata[9]}<br>"
                    "target_exit_price=%{customdata[10]}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    tp_x, tp_y = _barrier_segments(events, value_col="take_profit")
    sl_x, sl_y = _barrier_segments(events, value_col="stop_loss")
    if tp_x:
        fig.add_trace(
            go.Scatter(
                x=tp_x,
                y=tp_y,
                name="take_profit",
                mode="lines",
                line={"color": "#2563eb", "width": 1.1, "dash": "dot"},
                hovertemplate="timestamp=%{x}<br>take_profit=%{y:.6f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
    if sl_x:
        fig.add_trace(
            go.Scatter(
                x=sl_x,
                y=sl_y,
                name="stop_loss",
                mode="lines",
                line={"color": "#f97316", "width": 1.1, "dash": "dot"},
                hovertemplate="timestamp=%{x}<br>stop_loss=%{y:.6f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    if signal_col and signal_col in plot_frame.columns:
        fig.add_trace(
            go.Scatter(
                x=plot_frame.index,
                y=plot_frame[signal_col],
                name=signal_col,
                mode="lines",
                line={"color": "#059669", "width": 1.2},
            ),
            row=2,
            col=1,
        )
    fig.add_trace(
        go.Scatter(
            x=plot_positions.index,
            y=plot_positions,
            name="executed_position",
            mode="lines",
            line={"color": "#1d4ed8", "width": 1.2, "dash": "dot"},
        ),
        row=2,
        col=1,
    )
    if target_col and target_col in plot_frame.columns:
        hit_type = (
            plot_frame[hit_type_col].astype(str).to_numpy()
            if hit_type_col and hit_type_col in plot_frame.columns
            else np.full(len(plot_frame), "")
        )
        target_customdata = np.column_stack(
            [
                hit_type,
                (
                    plot_frame[target_r_col].astype(str).to_numpy()
                    if target_r_col and target_r_col in plot_frame.columns
                    else (
                        plot_frame[r_col].astype(str).to_numpy()
                        if r_col and r_col in plot_frame.columns
                        else np.full(len(plot_frame), "")
                    )
                ),
                (
                    plot_frame[target_entry_price_col].astype(str).to_numpy()
                    if target_entry_price_col and target_entry_price_col in plot_frame.columns
                    else (
                        plot_frame[entry_price_col].astype(str).to_numpy()
                        if entry_price_col and entry_price_col in plot_frame.columns
                        else np.full(len(plot_frame), "")
                    )
                ),
                (
                    plot_frame[target_exit_price_col].astype(str).to_numpy()
                    if target_exit_price_col and target_exit_price_col in plot_frame.columns
                    else (
                        plot_frame[exit_price_col].astype(str).to_numpy()
                        if exit_price_col and exit_price_col in plot_frame.columns
                        else np.full(len(plot_frame), "")
                    )
                ),
                (
                    plot_frame[target_stop_col].astype(str).to_numpy()
                    if target_stop_col and target_stop_col in plot_frame.columns
                    else (
                        plot_frame[lower_barrier_col].astype(str).to_numpy()
                        if lower_barrier_col and lower_barrier_col in plot_frame.columns
                        else np.full(len(plot_frame), "")
                    )
                ),
                (
                    plot_frame[target_take_profit_col].astype(str).to_numpy()
                    if target_take_profit_col and target_take_profit_col in plot_frame.columns
                    else (
                        plot_frame[upper_barrier_col].astype(str).to_numpy()
                        if upper_barrier_col and upper_barrier_col in plot_frame.columns
                        else np.full(len(plot_frame), "")
                    )
                ),
                (
                    plot_frame[target_exit_reason_col].astype(str).to_numpy()
                    if target_exit_reason_col and target_exit_reason_col in plot_frame.columns
                    else np.full(len(plot_frame), "")
                ),
            ]
        )
        fig.add_trace(
            go.Scatter(
                x=plot_frame.index,
                y=plot_frame[target_col],
                name=target_col,
                mode="markers",
                marker={"symbol": "circle", "size": 5, "color": "#7c3aed", "opacity": 0.65},
                customdata=target_customdata,
                hovertemplate=(
                    "timestamp=%{x}<br>label=%{y}<br>hit_type=%{customdata[0]}<br>"
                    "trade_r=%{customdata[1]}<br>entry_price=%{customdata[2]}<br>"
                    "exit_price=%{customdata[3]}<br>stop_price=%{customdata[4]}<br>"
                    "take_profit_price=%{customdata[5]}<br>exit_reason=%{customdata[6]}<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    feature_trace_indices: list[int] = []
    feature_colors = ["#7c3aed", "#0891b2", "#ea580c", "#65a30d", "#dc2626", "#2563eb", "#0f766e"]
    for idx, column in enumerate(resolved_feature_panels):
        row = 3 + idx
        fig.add_trace(
            go.Scatter(
                x=plot_frame.index,
                y=_numeric_series(plot_frame, column),
                name=f"feature_panel_{idx + 1}: {column}",
                mode="lines",
                line={"color": feature_colors[idx % len(feature_colors)], "width": 1.1},
                meta=column,
                hovertemplate=_feature_panel_hovertemplate(),
            ),
            row=row,
            col=1,
        )
        feature_trace_indices.append(len(fig.data) - 1)

    display_title = title
    if len(plot_frame) < len(frame):
        display_title = f"{title} (displaying {len(plot_frame):,}/{len(frame):,} bars)"

    fig.update_layout(
        title=display_title,
        template="plotly_white",
        dragmode="zoom",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={
            "l": 40,
            "r": 20,
            "t": 70 + max(0, ((feature_panel_count + 1) // 2) * 42),
            "b": 40,
        },
    )
    fig.update_xaxes(showgrid=True, rangeslider={"visible": False})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Signal / Target")
    for idx, _column in enumerate(resolved_feature_panels):
        fig.update_yaxes(showgrid=True, row=3 + idx, col=1, title_text=f"Feature {idx + 1}")

    if resolved_feature_panels:
        updatemenus: list[dict[str, Any]] = []
        menus_per_row = 2
        menu_x_positions = [0.0, 0.52]
        menu_y_start = 1.18
        menu_y_step = 0.07
        for idx, trace_index in enumerate(feature_trace_indices):
            buttons: list[dict[str, Any]] = []
            for option_col in resolved_feature_panels:
                buttons.append(
                    {
                        "label": option_col,
                        "method": "restyle",
                        "args": [
                            {
                                "y": [_numeric_series(plot_frame, option_col).to_numpy()],
                                "meta": [option_col],
                                "name": [f"feature_panel_{idx + 1}: {option_col}"],
                                "hovertemplate": [_feature_panel_hovertemplate()],
                            },
                            [trace_index],
                        ],
                    }
                )
            menu_row = idx // menus_per_row
            menu_col = idx % menus_per_row
            active_idx = idx if idx < len(resolved_feature_panels) else 0
            updatemenus.append(
                {
                    "type": "dropdown",
                    "direction": "down",
                    "showactive": True,
                    "x": menu_x_positions[menu_col],
                    "xanchor": "left",
                    "y": menu_y_start - menu_row * menu_y_step,
                    "yanchor": "top",
                    "buttons": buttons,
                    "active": active_idx,
                    "pad": {"r": 8, "t": 4, "b": 4},
                }
            )
        fig.update_layout(updatemenus=updatemenus)
    return fig


def plotly_chart_config() -> dict[str, Any]:
    return {
        "displaylogo": False,
        "displayModeBar": True,
        "scrollZoom": True,
        "responsive": True,
        "doubleClick": "reset",
    }


__all__ = ["build_trade_event_frame", "plot_trade_diagnostics", "plotly_chart_config"]
