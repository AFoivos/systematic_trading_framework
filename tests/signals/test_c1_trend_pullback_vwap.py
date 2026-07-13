from __future__ import annotations

import pandas as pd
import pytest

from src.experiments.orchestration.feature_stage import apply_signal_step
from src.experiments.registry import SIGNAL_REGISTRY
from src.signals.c1_trend_pullback_vwap import (
    build_c1_trend_pullback_vwap_signal,
    c1_trend_pullback_vwap_signal,
)


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=5, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "trend_regime": [float("nan"), 1.0, -1.0, 1.0, -1.0],
            "vwap_rms_ema_cross_long_setup": [0, 1, 0, 1, 0],
            "vwap_rms_ema_cross_short_setup": [0, 0, 1, 0, 1],
            "ppo_hist": [float("nan"), 0.10, -0.10, 0.10, -0.10],
            "ppo_above_signal": [0, 1, 0, 1, 0],
            "ppo_below_signal": [0, 0, 1, 0, 1],
            "mfi_14": [float("nan"), 60.0, 40.0, 55.0, 45.0],
            "stoch_rsi_k": [float("nan"), 0.70, 0.30, 0.60, 0.40],
            "stoch_rsi_d": [float("nan"), 0.50, 0.50, 0.50, 0.50],
            "zscore_momentum_20": [float("nan"), 0.60, -0.60, 0.20, -0.20],
            "volatility_regime": [float("nan"), 1.0, 1.0, 2.0, 1.0],
            "rolling_r2_96": [float("nan"), 0.40, 0.40, 0.40, 0.20],
        },
        index=idx,
    )


def test_c1_trend_pullback_vwap_signal_emits_long_short_candidates_and_registry() -> None:
    out, meta = build_c1_trend_pullback_vwap_signal(_frame())

    assert meta["kind"] == "c1_trend_pullback_vwap"
    assert SIGNAL_REGISTRY["c1_trend_pullback_vwap"] is c1_trend_pullback_vwap_signal
    assert out["c1_long_candidate"].tolist() == [0, 1, 0, 0, 0]
    assert out["c1_short_candidate"].tolist() == [0, 0, 1, 0, 1]
    assert out["c1_long_candidate_strict"].tolist() == [0, 1, 0, 0, 0]
    assert out["c1_short_candidate_strict"].tolist() == [0, 0, 1, 0, 0]
    assert out["signal_side"].tolist() == [0, 1, -1, 0, -1]
    assert out["signal_candidate"].tolist() == [0, 1, 1, 0, 1]

    stepped = apply_signal_step(_frame(), {"kind": "c1_trend_pullback_vwap"})
    assert stepped["signal_side"].tolist() == [0, 1, -1, 0, -1]


def test_c1_trend_pullback_vwap_strict_signal_mode() -> None:
    out, meta = build_c1_trend_pullback_vwap_signal(_frame(), {"use_strict_signal": True})

    assert meta["use_strict_signal"] is True
    assert out["signal_side"].tolist() == [0, 1, -1, 0, 0]
    assert out["signal_candidate"].tolist() == [0, 1, 1, 0, 0]


def test_c1_trend_pullback_vwap_supports_directional_modes() -> None:
    long_only, _ = build_c1_trend_pullback_vwap_signal(_frame(), {"mode": "long_only"})
    short_only, _ = build_c1_trend_pullback_vwap_signal(_frame(), {"mode": "short_only"})

    assert long_only["signal_side"].tolist() == [0, 1, 0, 0, 0]
    assert short_only["signal_side"].tolist() == [0, 0, -1, 0, -1]


def test_c1_trend_pullback_vwap_does_not_mutate_input() -> None:
    frame = _frame()
    original = frame.copy(deep=True)

    out, _ = build_c1_trend_pullback_vwap_signal(frame)

    assert out is not frame
    pd.testing.assert_frame_equal(frame, original)


def test_c1_trend_pullback_vwap_requires_columns() -> None:
    with pytest.raises(KeyError, match="zscore_momentum_20"):
        build_c1_trend_pullback_vwap_signal(_frame().drop(columns=["zscore_momentum_20"]))


def test_c1_trend_pullback_vwap_current_bar_logic_does_not_look_ahead() -> None:
    baseline, _ = build_c1_trend_pullback_vwap_signal(_frame())
    mutated = _frame()
    mutated.loc[mutated.index[-1], "trend_regime"] = 1.0
    mutated.loc[mutated.index[-1], "vwap_rms_ema_cross_long_setup"] = 1
    mutated.loc[mutated.index[-1], "vwap_rms_ema_cross_short_setup"] = 0
    mutated.loc[mutated.index[-1], "zscore_momentum_20"] = 1.0
    changed, _ = build_c1_trend_pullback_vwap_signal(mutated)

    compare_cols = [
        "c1_long_candidate",
        "c1_short_candidate",
        "c1_long_candidate_strict",
        "c1_short_candidate_strict",
        "signal_side",
        "signal_candidate",
    ]
    pd.testing.assert_frame_equal(
        baseline.iloc[:-1][compare_cols],
        changed.iloc[:-1][compare_cols],
    )
