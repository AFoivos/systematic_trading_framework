from __future__ import annotations

import numpy as np
import pandas as pd

from src.experiments.orchestration.artifacts import (
    _resolve_lab_feature_columns,
    _split_lab_feature_columns,
    _should_write_trade_diagnostic_artifacts,
)
from src.experiments.orchestration.reporting import render_markdown_report_html
from src.experiments.orchestration.trade_diagnostics import plot_trade_diagnostics, plotly_chart_config
from src.plots.price_with_features import plot_price_with_features
from src.utils.html_reports import write_plotly_dashboard_html


def test_plot_trade_diagnostics_adds_feature_panels_without_dropdown_switchers() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.02, 1.03, 1.01],
            "high": [1.01, 1.05, 1.06, 1.04],
            "low": [0.99, 1.00, 1.01, 0.98],
            "close": [1.00, 1.04, 1.02, 1.00],
            "signal_long": [0.0, 0.7, 0.7, 0.0],
            "label": [np.nan, 1.0, 0.0, np.nan],
            "roc_12": [0.001, 0.003, 0.002, -0.001],
            "close_z": [0.1, 0.4, 0.2, -0.1],
            "manual_conviction_score": [4, 6, 5, 3],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 0.7, 0.7, 0.0], index=idx)

    fig = plot_trade_diagnostics(
        frame,
        positions=positions,
        asset="TEST",
        title="Trade Diagnostics: TEST",
        signal_col="signal_long",
        target_col="label",
        feature_panel_cols=["roc_12", "close_z"],
    )

    annotation_text = {annotation.text for annotation in fig.layout.annotations}
    assert "Feature Panel 1" in annotation_text
    assert "Feature Panel 2" in annotation_text
    assert len(fig.layout.updatemenus or ()) == 0
    trace_names = [str(getattr(trace, "name", "")) for trace in fig.data]
    assert "feature_panel_1: roc_12" in trace_names
    assert "feature_panel_2: close_z" in trace_names


def test_plot_price_with_features_uses_equal_price_and_feature_space() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="h")
    frame = pd.DataFrame(
        {
            "close": [1.0, 1.1, 1.05, 1.12, 1.2],
            "close_ema_5": [1.0, 1.03, 1.04, 1.07, 1.11],
            "close_ret": [0.0, 0.1, -0.045, 0.067, 0.071],
            "vol_rolling_6": [0.0, 0.02, 0.04, 0.03, 0.05],
            "eda_flat_signal": [0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=idx,
    )

    fig = plot_price_with_features(
        frame,
        title="Lab Feature Diagnostics: TEST",
        feature_cols=["close_ret", "vol_rolling_6"],
        price_overlay_cols=["close_ema_5"],
        price_col="close",
        initial_features_visible=False,
    )

    price_domain = fig.layout.yaxis.domain
    feature_domain = fig.layout.yaxis2.domain
    price_height = price_domain[1] - price_domain[0]
    feature_height = feature_domain[1] - feature_domain[0]
    trace_names = [str(trace.name) for trace in fig.data]

    assert abs(price_height - feature_height) < 1e-12
    assert fig.layout.height <= 720
    assert trace_names == ["close", "close_ema_5", "close_ret", "vol_rolling_6"]
    assert fig.data[0].visible is None
    assert fig.data[1].visible == "legendonly"
    assert fig.data[1].yaxis == "y"
    assert fig.data[2].visible == "legendonly"
    assert fig.data[2].yaxis == "y2"
    assert len(fig.layout.updatemenus or ()) == 1
    feature_picker = fig.layout.updatemenus[0]
    labels = [button.label for button in feature_picker.buttons]
    assert labels == ["Hide features", "Show all features", "close_ema_5", "close_ret", "vol_rolling_6"]
    assert feature_picker.buttons[3].args[0]["visible"] == [True, False, True, False]
    assert "eda_flat_signal" not in trace_names


def test_lab_feature_columns_skip_raw_targets_and_disabled_flat_signal() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2, 1.3],
            "close": [1.0, 1.2, 1.1, 1.4],
            "volume": [10.0, 11.0, 12.0, 13.0],
            "close_ema_5": [1.0, 1.05, 1.08, 1.2],
            "close_ret": [0.0, 0.2, -0.083, 0.273],
            "vol_rolling_6": [0.0, 0.1, 0.08, 0.12],
            "bb_upper_20_2.0": [1.2, 1.3, 1.35, 1.5],
            "manual_conviction_score": [1.0, 2.0, 3.0, 4.0],
            "eda_flat_signal": [0.0, 0.0, 0.0, 0.0],
            "signal_long": [0.0, 1.0, 0.0, 1.0],
            "label": [0.0, 1.0, 0.0, 1.0],
            "r_target_trade_r": [0.1, 0.2, 0.3, 0.4],
        },
        index=idx,
    )
    cfg = {
        "logging": {"run_name": "feature_signal_target_lab", "output_dir": "logs/experiments/lab"},
        "model": {"kind": "none"},
        "signals": {"kind": "none", "params": {"signal_col": "eda_flat_signal"}},
        "targets_catalog": {"forward_return": {"enabled": False}},
        "signals_catalog": {"none": {"enabled": False, "params": {"signal_col": "eda_flat_signal"}}},
        "backtest": {"signal_col": "eda_flat_signal"},
    }

    assert _resolve_lab_feature_columns(frame, cfg) == [
        "close_ema_5",
        "close_ret",
        "vol_rolling_6",
        "bb_upper_20_2.0",
        "manual_conviction_score",
    ]
    assert _split_lab_feature_columns(_resolve_lab_feature_columns(frame, cfg)) == (
        ["close_ema_5", "bb_upper_20_2.0"],
        ["close_ret", "vol_rolling_6", "manual_conviction_score"],
    )
    assert _should_write_trade_diagnostic_artifacts(cfg) is False


def test_plot_trade_diagnostics_html_is_self_contained(tmp_path) -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.02, 1.03, 1.01],
            "high": [1.01, 1.05, 1.06, 1.04],
            "low": [0.99, 1.00, 1.01, 0.98],
            "close": [1.00, 1.04, 1.02, 1.00],
            "signal_long": [0.0, 0.7, 0.7, 0.0],
            "label": [np.nan, 1.0, 0.0, np.nan],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 0.7, 0.7, 0.0], index=idx)

    fig = plot_trade_diagnostics(
        frame,
        positions=positions,
        asset="TEST",
        title="Trade Diagnostics: TEST",
        signal_col="signal_long",
        target_col="label",
    )
    html_path = tmp_path / "trade_diagnostics_TEST.html"
    fig.write_html(
        html_path,
        include_plotlyjs="directory",
        full_html=True,
        config=plotly_chart_config(),
    )

    html_text = html_path.read_text(encoding="utf-8")
    assert 'src="https://cdn.plot.ly/' not in html_text
    assert 'src="plotly.min.js"' in html_text
    assert (tmp_path / "plotly.min.js").exists()


def test_plotly_dashboard_html_uses_app_shell_and_local_plotly(tmp_path) -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.02, 1.03, 1.01],
            "high": [1.01, 1.05, 1.06, 1.04],
            "low": [0.99, 1.00, 1.01, 0.98],
            "close": [1.00, 1.04, 1.02, 1.00],
            "signal_long": [0.0, 0.7, 0.7, 0.0],
            "label": [np.nan, 1.0, 0.0, np.nan],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 0.7, 0.7, 0.0], index=idx)
    fig = plot_trade_diagnostics(
        frame,
        positions=positions,
        asset="TEST",
        title="Trade Diagnostics: TEST",
        signal_col="signal_long",
        target_col="label",
    )
    html_path = tmp_path / "trade_diagnostics_TEST.html"

    write_plotly_dashboard_html(fig, html_path, title="Trade Diagnostics: TEST")

    html_text = html_path.read_text(encoding="utf-8")
    assert 'class="app-shell"' in html_text
    assert 'class="top-bar"' in html_text
    assert 'class="chart-canvas"' in html_text
    assert 'src="https://cdn.plot.ly/' not in html_text
    assert 'src="plotly.min.js"' in html_text
    assert (tmp_path / "plotly.min.js").exists()


def test_markdown_report_html_uses_dashboard_shell() -> None:
    html_text = render_markdown_report_html(
        "# Experiment Report: demo\n\n| Metric | Value |\n| --- | --- |\n| sharpe | 1.2 |\n",
        title="Experiment Report: demo",
    )

    assert 'class="app-shell"' in html_text
    assert 'class="top-bar"' in html_text
    assert 'class="content-surface report-content"' in html_text
    assert "<h1>Experiment Report: demo</h1>" in html_text
    assert "<table>" in html_text


def test_plot_trade_diagnostics_downsamples_large_timeseries_payload() -> None:
    idx = pd.date_range("2024-01-01", periods=101, freq="min")
    frame = pd.DataFrame(
        {
            "open": np.linspace(1.0, 1.2, len(idx)),
            "high": np.linspace(1.01, 1.21, len(idx)),
            "low": np.linspace(0.99, 1.19, len(idx)),
            "close": np.linspace(1.0, 1.2, len(idx)),
            "signal_long": np.linspace(0.0, 1.0, len(idx)),
            "label": np.nan,
            "roc_12": np.linspace(-0.01, 0.01, len(idx)),
        },
        index=idx,
    )
    positions = pd.Series(0.0, index=idx)
    positions.iloc[55] = 1.0

    fig = plot_trade_diagnostics(
        frame,
        positions=positions,
        asset="TEST",
        title="Trade Diagnostics: TEST",
        signal_col="signal_long",
        target_col="label",
        feature_panel_cols=["roc_12"],
        max_plot_points=10,
    )

    ohlc_trace = next(trace for trace in fig.data if trace.name == "OHLC")
    position_trace = next(trace for trace in fig.data if trace.name == "executed_position")
    entry_trace = next(trace for trace in fig.data if trace.name == "entries")
    feature_trace = next(trace for trace in fig.data if str(trace.name).startswith("feature_panel_1:"))

    assert len(ohlc_trace.x) == 10
    assert len(position_trace.x) == 10
    assert len(feature_trace.x) == 10
    assert entry_trace.x[0] == idx[55]
    assert "displaying 10/101 bars" in str(fig.layout.title.text)


def test_plot_trade_diagnostics_adds_exit_reason_filter() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.02, 1.03, 1.01],
            "high": [1.01, 1.05, 1.06, 1.04],
            "low": [0.99, 1.00, 1.01, 0.98],
            "close": [1.00, 1.04, 1.02, 1.00],
            "signal_long": [0.0, 0.7, 0.7, 0.0],
            "label": [np.nan, 1.0, 0.0, 1.0],
            "r_target_exit_reason": [None, "take_profit", "stop_loss", "take_profit"],
        },
        index=idx,
    )
    positions = pd.Series([0.0, 0.7, 0.7, 0.0], index=idx)

    fig = plot_trade_diagnostics(
        frame,
        positions=positions,
        asset="TEST",
        title="Trade Diagnostics: TEST",
        signal_col="signal_long",
        target_col="label",
        target_exit_reason_col="r_target_exit_reason",
    )

    assert len(fig.layout.updatemenus) == 1
    labels = [button.label for button in fig.layout.updatemenus[0].buttons]
    assert labels == ["all exit_reason", "stop_loss", "take_profit"]
    take_profit_button = fig.layout.updatemenus[0].buttons[2]
    assert len(take_profit_button.args[0]["y"][0]) == 2
