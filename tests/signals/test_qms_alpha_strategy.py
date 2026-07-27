from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.signals.qms_alpha_strategy import (
    QMS_ALPHA_STRATEGIES,
    build_qms_alpha_strategy_signal,
)
from src.signals.registry import SIGNAL_REGISTRY
from src.utils.config_validation import ConfigValidationError, validate_signals_block


def _frame(periods: int = 180) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="15min", tz="UTC")
    phase = np.arange(periods, dtype=float)
    return pd.DataFrame(
        {
            "ktrend_score": 0.10 + 0.01 * np.sin(phase / 9.0),
            "ktrend_uncertainty": 0.40 + 0.01 * np.cos(phase / 11.0),
            "kalman_innovation_z": 0.10 * np.sin(phase / 5.0),
            "lmom_score": 0.10 + 0.01 * np.cos(phase / 8.0),
            "qms_momentum_quality": 0.50 + 0.01 * np.sin(phase / 7.0),
            "lmom_efficiency": 0.50 + 0.01 * np.cos(phase / 13.0),
            "lmom_reversal_pressure": 0.10 + 0.01 * np.sin(phase / 6.0),
            "lmom_exhaustion": 0.10 + 0.01 * np.cos(phase / 10.0),
            "rlv_regime_z": 0.10 * np.sin(phase / 12.0),
            "rlv_fast_slow_ratio": 1.0 + 0.01 * np.cos(phase / 15.0),
            "rlv_vol_of_vol_ratio": 1.0 + 0.01 * np.sin(phase / 17.0),
            "rlv_shock_z": 0.20 * np.sin(phase / 4.0),
            "qms_state_uncertainty": 0.40 + 0.01 * np.cos(phase / 14.0),
            "qms_gap_flag": 0.0,
            "qms_unexpected_data_gap": 0.0,
        },
        index=index,
    )


def _strategy_frame(strategy: str, event: int = 120) -> tuple[pd.DataFrame, int]:
    frame = _frame()
    if strategy == "kds_pullback_continuation":
        frame.iloc[event, frame.columns.get_loc("ktrend_score")] = 0.80
        frame.iloc[event, frame.columns.get_loc("ktrend_uncertainty")] = 0.10
        frame.iloc[event, frame.columns.get_loc("kalman_innovation_z")] = -5.0
        frame.iloc[event, frame.columns.get_loc("rlv_vol_of_vol_ratio")] = 0.50
    elif strategy == "kalman_residual_reversion":
        frame.iloc[event, frame.columns.get_loc("ktrend_score")] = 0.0
        frame.iloc[event, frame.columns.get_loc("kalman_innovation_z")] = 5.0
        frame.iloc[event, frame.columns.get_loc("lmom_efficiency")] = 0.05
        frame.iloc[event, frame.columns.get_loc("rlv_vol_of_vol_ratio")] = 0.50
        frame.iloc[event, frame.columns.get_loc("rlv_shock_z")] = 0.0
    elif strategy == "volatility_compression_breakout":
        frame.iloc[event - 5 : event, frame.columns.get_loc("rlv_regime_z")] = -3.0
        frame.iloc[event - 5 : event, frame.columns.get_loc("rlv_fast_slow_ratio")] = 0.50
        frame.iloc[event - 5 : event, frame.columns.get_loc("rlv_vol_of_vol_ratio")] = 0.50
        frame.iloc[event, frame.columns.get_loc("ktrend_score")] = 0.80
        frame.iloc[event, frame.columns.get_loc("lmom_score")] = 0.80
        frame.iloc[event, frame.columns.get_loc("lmom_efficiency")] = 0.90
        frame.iloc[event, frame.columns.get_loc("rlv_shock_z")] = 5.0
    elif strategy == "lmds_exhaustion_reversal":
        frame.iloc[event, frame.columns.get_loc("ktrend_score")] = 0.80
        frame.iloc[event, frame.columns.get_loc("lmom_score")] = -0.80
        frame.iloc[event, frame.columns.get_loc("lmom_efficiency")] = 0.05
        frame.iloc[event, frame.columns.get_loc("lmom_reversal_pressure")] = 0.95
        frame.iloc[event, frame.columns.get_loc("lmom_exhaustion")] = 0.95
        frame.iloc[event, frame.columns.get_loc("rlv_shock_z")] = 5.0
    else:
        frame.iloc[event, frame.columns.get_loc("ktrend_score")] = 0.80
        frame.iloc[event, frame.columns.get_loc("lmom_score")] = 0.80
        frame.iloc[event, frame.columns.get_loc("qms_momentum_quality")] = 0.90
        frame.iloc[event, frame.columns.get_loc("lmom_efficiency")] = 0.90
        frame.iloc[event, frame.columns.get_loc("qms_state_uncertainty")] = 0.10
        frame.iloc[event, frame.columns.get_loc("rlv_shock_z")] = 0.0
    return frame, event


@pytest.mark.parametrize("strategy", QMS_ALPHA_STRATEGIES)
def test_each_qms_alpha_strategy_emits_expected_event_side(strategy: str) -> None:
    frame, event = _strategy_frame(strategy)

    out, meta = build_qms_alpha_strategy_signal(
        frame,
        {
            "strategy": strategy,
            "lookback_bars": 60,
            "min_periods": 40,
            "signal_on_crossing": False,
        },
    )

    expected = -1 if strategy in {"kalman_residual_reversion", "lmds_exhaustion_reversal"} else 1
    assert out["qms_alpha_signal"].iloc[event] == expected
    assert out["qms_alpha_candidate"].iloc[event] == 1
    assert out["qms_alpha_threshold_ready"].iloc[event] == 1
    assert meta["strategy"] == strategy
    assert set(out["qms_alpha_signal"].unique()).issubset({-1, 0, 1})


@pytest.mark.parametrize("strategy", QMS_ALPHA_STRATEGIES)
def test_qms_alpha_strategies_are_prefix_invariant(strategy: str) -> None:
    frame, _ = _strategy_frame(strategy)
    params = {
        "strategy": strategy,
        "lookback_bars": 60,
        "min_periods": 40,
        "signal_on_crossing": True,
    }

    prefix, _ = build_qms_alpha_strategy_signal(frame.iloc[:145], params)
    full, _ = build_qms_alpha_strategy_signal(frame, params)

    columns = [
        "qms_alpha_threshold_ready",
        "qms_alpha_direction",
        "qms_alpha_state",
        "qms_alpha_signal",
        "qms_alpha_candidate",
    ]
    pdt.assert_frame_equal(prefix[columns], full.iloc[:145][columns], check_exact=True)


def test_qms_alpha_signal_fails_closed_on_gap() -> None:
    frame, event = _strategy_frame("kds_pullback_continuation")
    frame.iloc[event, frame.columns.get_loc("qms_gap_flag")] = 1.0

    out, _ = build_qms_alpha_strategy_signal(
        frame,
        {
            "strategy": "kds_pullback_continuation",
            "lookback_bars": 60,
            "min_periods": 40,
            "signal_on_crossing": False,
        },
    )

    assert out["qms_alpha_signal"].iloc[event] == 0
    assert out["qms_alpha_state"].iloc[event] == 0


def test_qms_alpha_strategy_is_registered_and_config_validated() -> None:
    assert "qms_alpha_strategy" in SIGNAL_REGISTRY
    validate_signals_block(
        {
            "kind": "qms_alpha_strategy",
            "params": {
                "strategy": "time_series_momentum",
                "lookback_bars": 120,
                "min_periods": 60,
            },
        }
    )

    with pytest.raises(ConfigValidationError, match="strategy must be one of"):
        validate_signals_block(
            {"kind": "qms_alpha_strategy", "params": {"strategy": "unknown"}}
        )


def test_qms_alpha_strategy_rejects_unknown_parameters() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        build_qms_alpha_strategy_signal(_frame(), {"misspelled_quantile": 0.9})
