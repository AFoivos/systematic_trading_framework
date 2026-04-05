from __future__ import annotations

import textwrap
from typing import Any

import pandas as pd
import streamlit as st

try:
    from streamlit_echarts import st_echarts
except ImportError:  # pragma: no cover - optional UI dependency
    st_echarts = None

try:
    from lightweight_charts_v5 import lightweight_charts_v5_component
except ImportError:  # pragma: no cover - optional UI dependency
    lightweight_charts_v5_component = None

from notebooks.experiment_lab_support import (
    TOP_EXPERIMENTS,
    build_analysis_frame_from_result,
    build_summary_frame,
    get_experiment_spec,
    load_logged_artifact_bundle,
    parse_override_text,
    plot_equity_drawdown,
    plot_positions_turnover,
    plot_price_signal_probability,
    plot_returns_distribution,
    plotly_chart_config,
    run_experiment_with_overrides,
)


DEFAULT_OVERRIDES = {
    "shock_meta_long_only": textwrap.dedent(
        """\
        signals:
          params:
            upper: 0.56
            upper_exit: 0.49
            lower: 0.43
            lower_exit: 0.48
        risk:
          dd_guard:
            cooloff_bars: 48
        """
    ),
    "xgboost_garch_baseline": textwrap.dedent(
        """\
        signals:
          params:
            upper: 0.57
            lower: 0.43
            clip: 0.6
        model:
          params:
            max_depth: 4
            n_estimators: 350
        """
    ),
}


ZOOM_CHART_PALETTE = [
    "#2563eb",
    "#dc2626",
    "#059669",
    "#7c3aed",
    "#ea580c",
    "#0891b2",
]


def _metric_text(summary: dict, key: str, *, pct: bool = False) -> str:
    value = summary.get(key)
    if value is None:
        return "n/a"
    if pct:
        return f"{value:.2%}"
    return f"{value:.3f}"


def _time_strings(index: pd.Index) -> list[str]:
    return pd.DatetimeIndex(pd.to_datetime(index)).strftime("%Y-%m-%d %H:%M:%S").tolist()


def _chart_frame(frame: pd.DataFrame, max_bars: int | None) -> pd.DataFrame:
    if max_bars is None:
        return frame.copy()
    return frame.tail(int(max_bars)).copy()


def _available_zoom_overlay_columns(frame: pd.DataFrame, signal_col: str) -> list[str]:
    candidates = [
        signal_col,
        "pred_prob",
        "strategy_positions",
        "strategy_turnover",
        "strategy_costs",
        "strategy_net_returns",
    ]
    ordered: list[str] = []
    seen: set[str] = set()
    for column in candidates:
        if column in seen or column not in frame.columns:
            continue
        if not pd.api.types.is_numeric_dtype(frame[column]):
            continue
        if not frame[column].notna().any():
            continue
        seen.add(column)
        ordered.append(column)
    return ordered


def _default_zoom_overlay_columns(frame: pd.DataFrame, signal_col: str) -> list[str]:
    preferred = [signal_col, "pred_prob", "strategy_positions"]
    return [column for column in preferred if column in _available_zoom_overlay_columns(frame, signal_col)]


def _render_zoom_help(engine: str) -> None:
    if engine == "ECharts":
        st.caption("Mouse wheel zoom, drag pan, and the bottom slider are enabled.")
    elif engine == "TradingView Style":
        st.caption("Mouse wheel zoom, drag pan, crosshair, and dense financial-chart interaction are enabled.")


def _build_echarts_price_indicator_options(
    frame: pd.DataFrame,
    *,
    overlay_cols: list[str],
    title: str,
) -> dict[str, Any]:
    price_frame = frame.loc[:, ["open", "high", "low", "close"]].dropna()
    if price_frame.empty:
        raise ValueError("Price frame is empty after dropping missing OHLC rows.")

    x_data = _time_strings(price_frame.index)
    candle_data = [
        [float(row.open), float(row.close), float(row.low), float(row.high)]
        for row in price_frame.itertuples()
    ]

    series: list[dict[str, Any]] = [
        {
            "name": "price",
            "type": "candlestick",
            "xAxisIndex": 0,
            "yAxisIndex": 0,
            "data": candle_data,
            "itemStyle": {
                "color": "#059669",
                "color0": "#dc2626",
                "borderColor": "#059669",
                "borderColor0": "#dc2626",
            },
        }
    ]

    for idx, column in enumerate(overlay_cols):
        aligned = pd.to_numeric(frame[column], errors="coerce").reindex(price_frame.index)
        series.append(
            {
                "name": column,
                "type": "line",
                "xAxisIndex": 1,
                "yAxisIndex": 1,
                "showSymbol": False,
                "smooth": False,
                "connectNulls": False,
                "lineStyle": {"width": 2},
                "data": [None if pd.isna(value) else float(value) for value in aligned],
                "color": ZOOM_CHART_PALETTE[idx % len(ZOOM_CHART_PALETTE)],
            }
        )

    legend_data = ["price", *overlay_cols]
    return {
        "animation": False,
        "title": {"text": title, "left": 16, "top": 8, "textStyle": {"fontSize": 14}},
        "legend": {"data": legend_data, "top": 8, "right": 12},
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross"},
            "backgroundColor": "rgba(17, 24, 39, 0.92)",
            "borderWidth": 0,
            "textStyle": {"color": "#f9fafb"},
        },
        "axisPointer": {"link": [{"xAxisIndex": [0, 1]}]},
        "toolbox": {
            "right": 12,
            "top": 36,
            "feature": {
                "dataZoom": {"yAxisIndex": "none"},
                "restore": {},
            },
        },
        "grid": [
            {"left": 52, "right": 24, "top": 72, "height": "52%"},
            {"left": 52, "right": 24, "top": "70%", "height": "18%"},
        ],
        "xAxis": [
            {
                "type": "category",
                "data": x_data,
                "scale": True,
                "boundaryGap": True,
                "axisLine": {"onZero": False},
                "splitLine": {"show": False},
                "min": "dataMin",
                "max": "dataMax",
            },
            {
                "type": "category",
                "gridIndex": 1,
                "data": x_data,
                "scale": True,
                "boundaryGap": True,
                "axisLine": {"onZero": False},
                "splitLine": {"show": False},
                "min": "dataMin",
                "max": "dataMax",
            },
        ],
        "yAxis": [
            {
                "scale": True,
                "splitArea": {"show": False},
                "splitLine": {"show": True, "lineStyle": {"color": "#e5e7eb"}},
            },
            {
                "gridIndex": 1,
                "scale": True,
                "splitArea": {"show": False},
                "splitLine": {"show": True, "lineStyle": {"color": "#f3f4f6"}},
            },
        ],
        "dataZoom": [
            {
                "type": "inside",
                "xAxisIndex": [0, 1],
                "filterMode": "filter",
                "zoomOnMouseWheel": True,
                "moveOnMouseMove": True,
                "moveOnMouseWheel": True,
            },
            {
                "type": "slider",
                "xAxisIndex": [0, 1],
                "bottom": 12,
                "height": 28,
            },
        ],
        "series": series,
    }


def _lightweight_line_points(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    times = _time_strings(series.index)
    return [{"time": time_value, "value": float(value)} for time_value, value in zip(times, series.tolist())]


def _lightweight_candles(frame: pd.DataFrame) -> list[dict[str, Any]]:
    price_frame = frame.loc[:, ["open", "high", "low", "close"]].dropna()
    times = _time_strings(price_frame.index)
    candles: list[dict[str, Any]] = []
    for time_value, row in zip(times, price_frame.itertuples()):
        candles.append(
            {
                "time": time_value,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
            }
        )
    return candles


def _render_lightweight_chart(
    frame: pd.DataFrame,
    *,
    overlay_cols: list[str],
    name: str,
) -> None:
    if lightweight_charts_v5_component is None:
        st.warning("`streamlit-lightweight-charts-v5` is not installed in this environment.")
        return

    charts: list[dict[str, Any]] = [
        {
            "chart": {
                "layout": {
                    "background": {"type": "solid", "color": "#ffffff"},
                    "textColor": "#111827",
                },
                "grid": {
                    "vertLines": {"color": "#f3f4f6"},
                    "horzLines": {"color": "#f3f4f6"},
                },
                "crosshair": {"mode": 0},
                "timeScale": {
                    "timeVisible": True,
                    "secondsVisible": False,
                    "borderVisible": False,
                    "rightOffset": 12,
                    "barSpacing": 6,
                    "minBarSpacing": 0.5,
                },
                "handleScroll": {
                    "mouseWheel": True,
                    "pressedMouseMove": True,
                    "horzTouchDrag": True,
                    "vertTouchDrag": False,
                },
                "handleScale": {
                    "axisPressedMouseMove": True,
                    "mouseWheel": True,
                    "pinch": True,
                },
            },
            "series": [
                {
                    "type": "Candlestick",
                    "data": _lightweight_candles(frame),
                    "options": {
                        "upColor": "#059669",
                        "downColor": "#dc2626",
                        "borderVisible": False,
                        "wickUpColor": "#059669",
                        "wickDownColor": "#dc2626",
                    },
                }
            ],
            "height": 420,
        }
    ]

    if overlay_cols:
        charts.append(
            {
                "chart": {
                    "layout": {
                        "background": {"type": "solid", "color": "#ffffff"},
                        "textColor": "#111827",
                    },
                    "grid": {
                        "vertLines": {"color": "#f3f4f6"},
                        "horzLines": {"color": "#f3f4f6"},
                    },
                    "crosshair": {"mode": 0},
                    "timeScale": {
                        "timeVisible": True,
                        "secondsVisible": False,
                        "borderVisible": False,
                        "rightOffset": 12,
                        "barSpacing": 6,
                        "minBarSpacing": 0.5,
                    },
                    "handleScroll": {
                        "mouseWheel": True,
                        "pressedMouseMove": True,
                        "horzTouchDrag": True,
                        "vertTouchDrag": False,
                    },
                    "handleScale": {
                        "axisPressedMouseMove": True,
                        "mouseWheel": True,
                        "pinch": True,
                    },
                },
                "series": [
                    {
                        "type": "Line",
                        "data": _lightweight_line_points(frame, column),
                        "options": {
                            "color": ZOOM_CHART_PALETTE[idx % len(ZOOM_CHART_PALETTE)],
                            "lineWidth": 2,
                            "title": column,
                            "priceLineVisible": False,
                            "lastValueVisible": True,
                        },
                    }
                    for idx, column in enumerate(overlay_cols)
                ],
                "height": 220,
            }
        )

    lightweight_charts_v5_component(
        name=name,
        charts=charts,
        height=sum(int(chart.get("height", 300)) for chart in charts),
    )


st.set_page_config(page_title="STF Experiment Explorer", layout="wide")

st.title("STF Experiment Explorer")
st.caption("Streamlit + Plotly lab for the two strongest logged experiment families in this repo.")

experiment_key = st.sidebar.selectbox(
    "Experiment",
    options=list(TOP_EXPERIMENTS),
    format_func=lambda key: TOP_EXPERIMENTS[key]["label"],
)
spec = get_experiment_spec(experiment_key)

st.sidebar.markdown("### Mode")
mode = st.sidebar.radio(
    "Data source",
    options=["Logged artifact snapshot", "Fresh rerun"],
    help="Logged mode is instant. Fresh rerun recomputes the experiment with your overrides.",
)

st.sidebar.markdown("### Overrides")
override_text = st.sidebar.text_area(
    "YAML overrides",
    value=DEFAULT_OVERRIDES[experiment_key],
    height=220,
    help="Nested YAML merged into the tracked config before a fresh rerun.",
)
load_clicked = st.sidebar.button("Load Experiment", type="primary", use_container_width=True)

with st.expander("Selection rationale", expanded=True):
    st.write(spec["selection_note"])
    st.write(
        {
            "config_path": spec["config_path"],
            "logged_run_dir": spec["logged_run_dir"],
            "logged_metrics": spec["logged_metrics"],
        }
    )

if not load_clicked:
    st.info("Choose an experiment and click `Load Experiment`.")
    st.stop()

if mode == "Logged artifact snapshot":
    frame, summary, active_config = load_logged_artifact_bundle(experiment_key)
    source_label = "logged artifacts"
else:
    overrides = parse_override_text(override_text)
    with st.spinner("Running experiment inside the current Python environment..."):
        result = run_experiment_with_overrides(spec["config_path"], overrides=overrides, logging_enabled=False)
    frame = build_analysis_frame_from_result(result)
    summary = dict(result.evaluation.get("primary_summary", {}) or {})
    active_config = result.config
    source_label = "fresh rerun"

st.subheader(f"{spec['label']} ({source_label})")
metric_cols = st.columns(4)
metric_cols[0].metric("Sharpe", _metric_text(summary, "sharpe"))
metric_cols[1].metric("Net PnL", _metric_text(summary, "net_pnl", pct=True))
metric_cols[2].metric("Cum Return", _metric_text(summary, "cumulative_return", pct=True))
metric_cols[3].metric("Max DD", _metric_text(summary, "max_drawdown", pct=True))

st.markdown("### Summary Metrics")
st.dataframe(build_summary_frame(summary), use_container_width=True, hide_index=True)

signal_col = str(dict(active_config.get("backtest", {}) or {}).get("signal_col", "signal_prob_threshold"))

st.sidebar.markdown("### Zoom Compare")
bars_option = st.sidebar.selectbox(
    "Bars to render",
    options=["1,000", "5,000", "10,000", "All"],
    index=1,
    help="Smaller windows feel faster and make zoom comparisons easier.",
)
max_bars = None if bars_option == "All" else int(bars_option.replace(",", ""))
zoom_frame = _chart_frame(frame, max_bars=max_bars)
overlay_candidates = _available_zoom_overlay_columns(zoom_frame, signal_col)
selected_overlays = st.sidebar.multiselect(
    "Indicator pane series",
    options=overlay_candidates,
    default=_default_zoom_overlay_columns(zoom_frame, signal_col),
    help="These series are rendered in the lower pane for both ECharts and TradingView-style charts.",
)

st.markdown("### Zoom Compare")
st.caption(
    f"Showing {len(zoom_frame):,} bars. Use the same dataset and overlays in both engines to compare the zoom feel directly."
)

zoom_tabs = st.tabs(["ECharts", "TradingView Style", "Plotly"])

with zoom_tabs[0]:
    _render_zoom_help("ECharts")
    if st_echarts is None:
        st.warning("`streamlit-echarts` is not installed in this environment.")
    else:
        st_echarts(
            options=_build_echarts_price_indicator_options(
                zoom_frame,
                overlay_cols=selected_overlays,
                title=f"{spec['label']}: ECharts Zoom Compare",
            ),
            height="720px",
            key=f"echarts-{experiment_key}-{mode}-{bars_option}",
        )

with zoom_tabs[1]:
    _render_zoom_help("TradingView Style")
    _render_lightweight_chart(
        zoom_frame,
        overlay_cols=selected_overlays,
        name=f"{experiment_key}-{source_label}-lightweight",
    )

with zoom_tabs[2]:
    st.caption("Existing Plotly version for baseline comparison.")
    st.plotly_chart(
        plot_price_signal_probability(
            zoom_frame,
            title=f"{spec['label']}: Price, Signal, Probability",
            signal_col=signal_col,
        ),
        use_container_width=True,
        config=plotly_chart_config(),
    )

st.markdown("### Supporting Charts")

st.plotly_chart(
    plot_equity_drawdown(frame, title=f"{spec['label']}: Equity and Drawdown"),
    use_container_width=True,
    config=plotly_chart_config(),
)
st.plotly_chart(
    plot_positions_turnover(frame, title=f"{spec['label']}: Position, Turnover, Costs"),
    use_container_width=True,
    config=plotly_chart_config(),
)
st.plotly_chart(
    plot_returns_distribution(frame, title=f"{spec['label']}: Net Return Distribution"),
    use_container_width=True,
    config=plotly_chart_config(),
)

with st.expander("Active overrides", expanded=False):
    st.code(override_text.strip() or "{}", language="yaml")

with st.expander("Resolved backtest config", expanded=False):
    st.write(
        {
            "backtest": active_config.get("backtest", {}),
            "signals": active_config.get("signals", {}),
            "risk": active_config.get("risk", {}),
            "model": active_config.get("model", {}),
        }
    )
