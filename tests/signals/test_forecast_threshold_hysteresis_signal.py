from __future__ import annotations

import pandas as pd
import pytest

from src.signals.forecast_threshold_hysteresis_signal import forecast_threshold_hysteresis_signal
from src.signals.forecast_threshold_signal import forecast_threshold_signal
from src.signals.registry import SIGNAL_REGISTRY


def test_forecast_threshold_hysteresis_enters_exits_and_cools_down() -> None:
    df = pd.DataFrame(
        {"pred_ret": [0.0, 0.8, 0.6, 0.1, 0.9, 0.8, 0.1, -0.8, -0.7, -0.1]},
        index=pd.date_range("2024-01-01", periods=10, freq="30min"),
    )

    signal = forecast_threshold_hysteresis_signal(
        df,
        long_entry=0.75,
        long_exit=0.25,
        short_entry=-0.75,
        short_exit=-0.25,
        cooldown_bars=2,
        min_holding_bars=1,
    )

    assert signal.tolist() == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, -1.0, -1.0, 0.0]


def test_forecast_threshold_hysteresis_validates_threshold_order() -> None:
    df = pd.DataFrame({"pred_ret": [0.1, 0.2]})

    with pytest.raises(ValueError, match="long_exit"):
        forecast_threshold_hysteresis_signal(df, long_entry=0.2, long_exit=0.2)


def test_forecast_threshold_hysteresis_is_registered() -> None:
    assert "forecast_threshold_hysteresis" in SIGNAL_REGISTRY


def test_forecast_threshold_supports_activation_filters() -> None:
    df = pd.DataFrame(
        {
            "pred_ret": [0.8, 0.8, -0.8, -0.8],
            "atr_pct_rank_192": [0.1, 0.5, 0.9, 0.5],
        }
    )

    signal = forecast_threshold_signal(
        df,
        upper=0.5,
        lower=-0.5,
        mode="long_short",
        activation_filters=[
            {"col": "atr_pct_rank_192", "op": "ge", "value": 0.2},
            {"col": "atr_pct_rank_192", "op": "le", "value": 0.85},
        ],
    )

    assert signal.tolist() == [0.0, 1.0, 0.0, -1.0]
