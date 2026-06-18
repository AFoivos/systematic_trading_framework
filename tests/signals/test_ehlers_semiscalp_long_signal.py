from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.experiments.registry import SIGNAL_REGISTRY
from src.signals.ehlers_semiscalp_long_signal import build_ehlers_semiscalp_long_signal
from src.utils.config import load_experiment_config
from src.utils.config_kinds import FEATURE_KINDS, SIGNAL_KINDS


CONFIG_PATH = Path("config/experiments/spx500_30m_ehlers_semiscalp_long_v1.yaml")


def _signal_frame() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=6, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "close": [9.0, 11.0, 12.0, 13.0, 14.0, 15.0],
            "ehlers_supersmoother_10": [10.0, 10.0, 11.0, 12.0, 13.0, 14.0],
            "ehlers_supersmoother_10_slope": [1.0] * 6,
            "ehlers_roofing_48_10": [1.0] * 6,
            "ehlers_roofing_48_10_slope": [1.0] * 6,
            "ehlers_hilbert_amplitude_64": [1.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            "dominant_cycle_period": [20.0] * 6,
            "atr_over_price_14": [1.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        },
        index=index,
    )


def test_ehlers_semiscalp_config_loads_and_resolves_registered_steps() -> None:
    cfg = load_experiment_config(CONFIG_PATH)

    assert cfg["strategy"]["name"] == "spx500_30m_ehlers_semiscalp_long_v1"
    assert cfg["data"]["storage"]["dataset_id"] == "spx500_30m_ehlers_semiscalp_long_v1"
    assert cfg["signals"]["kind"] == "ehlers_semiscalp_long"
    assert cfg["signals"]["kind"] in SIGNAL_KINDS
    assert cfg["signals"]["kind"] in SIGNAL_REGISTRY
    assert cfg["signals"]["params"]["entry_mode"] == "transition"
    assert cfg["backtest"]["allow_short"] is False
    assert cfg["backtest"]["max_holding_bars"] == 6
    assert cfg["target"]["max_holding"] == 6
    for step in cfg["features"]:
        assert step["step"] in FEATURE_KINDS


def test_ehlers_semiscalp_signal_emits_only_false_to_true_transitions() -> None:
    out, meta = build_ehlers_semiscalp_long_signal(
        _signal_frame(),
        amplitude_quantile_lookback=3,
        atr_quantile_lookback=3,
    )

    assert meta["kind"] == "ehlers_semiscalp_long"
    assert meta["entry_mode"] == "transition"
    assert out["ehlers_semiscalp_long_setup"].tolist() == [0, 0, 1, 1, 1, 1]
    assert out["ehlers_semiscalp_long_entry"].tolist() == [0, 0, 1, 0, 0, 0]
    assert out["signal_side"].tolist() == [0, 0, 1, 0, 0, 0]
    assert out["signal_candidate"].equals(out["signal_side"])
    assert set(out["signal_side"].unique()).issubset({0, 1})
    assert {
        "ehlers_trend_ok",
        "ehlers_timing_ok",
        "ehlers_cycle_ok",
        "ehlers_energy_ok",
        "ehlers_volatility_ok",
        "ehlers_semiscalp_long_setup",
        "ehlers_semiscalp_long_entry",
    }.issubset(out.columns)


def test_ehlers_semiscalp_state_mode_remains_available_for_diagnostics() -> None:
    out, meta = build_ehlers_semiscalp_long_signal(
        _signal_frame(),
        entry_mode="state",
        amplitude_quantile_lookback=3,
        atr_quantile_lookback=3,
    )

    assert meta["entry_mode"] == "state"
    assert out["signal_side"].tolist() == [0, 0, 1, 1, 1, 1]


def test_ehlers_semiscalp_signal_rejects_missing_inputs() -> None:
    with pytest.raises(KeyError, match="dominant_cycle_period"):
        build_ehlers_semiscalp_long_signal(_signal_frame().drop(columns=["dominant_cycle_period"]))


def test_ehlers_semiscalp_signal_validates_quantiles() -> None:
    with pytest.raises(ValueError, match="amplitude_min_quantile"):
        build_ehlers_semiscalp_long_signal(_signal_frame(), amplitude_min_quantile=1.1)
