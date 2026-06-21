from __future__ import annotations

import pandas as pd
import pytest

from src.experiments.registry import SIGNAL_REGISTRY
from src.signals.ehlers_semiscalp_long_signal import build_ehlers_semiscalp_long_signal


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "mama": [100.0, 101.0, 103.0, 104.0, 105.0],
            "fama": [101.0, 102.0, 102.0, 103.0, 104.0],
            "decycler": [101.0, 102.0, 101.0, 102.0, 103.0],
            "roofing_filter_48_10": [-1.0, -0.5, 0.2, 0.4, 0.3],
            "laguerre_rsi": [0.2, 0.4, 0.6, 0.7, 0.8],
            "fisher_transform": [-1.0, -0.5, 0.0, 0.5, 0.4],
            "hilbert_amplitude_64": [1.0, 1.0, 1.0, 2.0, 3.0],
            "dominant_cycle_period": [20.0, 20.0, 20.0, 20.0, 60.0],
        },
        index=pd.date_range("2024-01-01", periods=5, freq="30min", tz="UTC"),
    )


def test_required_columns_are_validated() -> None:
    with pytest.raises(KeyError, match="mama"):
        build_ehlers_semiscalp_long_signal(_frame().drop(columns="mama"))


def test_input_is_not_mutated() -> None:
    frame = _frame()
    original = frame.copy(deep=True)

    out, _ = build_ehlers_semiscalp_long_signal(frame, amplitude_lookback=3)

    pd.testing.assert_frame_equal(frame, original)
    assert out is not frame


def test_long_signal_fires_on_causal_synthetic_data() -> None:
    out, metadata = build_ehlers_semiscalp_long_signal(_frame(), amplitude_lookback=3)

    assert metadata["kind"] == "ehlers_semiscalp_long"
    assert out["signal_side"].tolist() == [0, 0, 0, 1, 0]
    assert out["signal_candidate"].equals(out["signal_side"])
    assert "ehlers_semiscalp_long" in SIGNAL_REGISTRY


def test_transition_mode_emits_only_false_to_true_setup_changes() -> None:
    frame = _frame()
    frame.loc[frame.index[-1], "roofing_filter_48_10"] = 0.6
    frame.loc[frame.index[-1], "fisher_transform"] = 0.8

    transition, _ = build_ehlers_semiscalp_long_signal(frame, amplitude_lookback=3)
    state, _ = build_ehlers_semiscalp_long_signal(
        frame,
        amplitude_lookback=3,
        entry_mode="state",
    )

    assert transition["ehlers_semiscalp_long_setup"].tolist() == [0, 0, 0, 1, 1]
    assert transition["signal_side"].tolist() == [0, 0, 0, 1, 0]
    assert state["signal_side"].tolist() == [0, 0, 0, 1, 1]


def test_stricter_trend_and_roofing_filters_are_configurable() -> None:
    frame = _frame()
    frame.loc[frame.index[2], "hilbert_amplitude_64"] = 2.0

    out, metadata = build_ehlers_semiscalp_long_signal(
        frame,
        amplitude_lookback=3,
        require_mama_rising=True,
        roofing_trigger_mode="cross_up",
    )

    assert out["signal_side"].tolist() == [0, 0, 1, 0, 0]
    assert metadata["require_mama_rising"] is True
    assert metadata["roofing_trigger_mode"] == "cross_up"


def test_cycle_period_filter_is_optional_and_causal() -> None:
    frame = _frame()
    frame.loc[frame.index[-1], "roofing_filter_48_10"] = 0.6
    frame.loc[frame.index[-1], "fisher_transform"] = 0.8

    without_filter, _ = build_ehlers_semiscalp_long_signal(
        frame, amplitude_lookback=3, entry_mode="state"
    )
    with_filter, _ = build_ehlers_semiscalp_long_signal(
        frame,
        amplitude_lookback=3,
        entry_mode="state",
        use_cycle_period_filter=True,
        min_cycle_period=10,
        max_cycle_period=48,
    )

    assert without_filter["signal_side"].iloc[-1] == 1
    assert with_filter["signal_side"].iloc[-1] == 0


def test_output_columns_exist_and_flags_are_int8() -> None:
    out, _ = build_ehlers_semiscalp_long_signal(_frame(), amplitude_lookback=3)
    expected = {
        "signal_side",
        "signal_candidate",
        "ehlers_semiscalp_long_setup",
        "ehlers_semiscalp_trend_permission",
        "ehlers_semiscalp_active_cycle",
        "ehlers_semiscalp_roofing_trigger",
        "ehlers_semiscalp_momentum_confirm",
    }

    assert expected.issubset(out.columns)
    assert all(out[column].dtype == "int8" for column in expected)
