from __future__ import annotations

import numpy as np
import pandas as pd

from src.experiments.orchestration.trade_diagnostics import plot_trade_diagnostics, plotly_chart_config


def test_plot_trade_diagnostics_adds_feature_panels_with_dropdown_switchers() -> None:
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
    assert len(fig.layout.updatemenus) == 2
    assert [button.label for button in fig.layout.updatemenus[0].buttons] == ["roc_12", "close_z"]
    trace_names = [str(getattr(trace, "name", "")) for trace in fig.data]
    assert "feature_panel_1: roc_12" in trace_names
    assert "feature_panel_2: close_z" in trace_names


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
