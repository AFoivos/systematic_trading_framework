from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.experiments.orchestration.feature_stage import apply_signal_step
from src.signals.eurusd_session_bb_reversion import (
    build_eurusd_session_bb_reversion_signal,
    eurusd_session_bb_reversion_signal,
)
from src.signals.registry import get_signal_fn
from src.utils.config import load_experiment_config


def _frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [
            "2024-01-02 06:30:00+00:00",
            "2024-01-02 07:00:00+00:00",
            "2024-01-02 10:00:00+00:00",
            "2024-01-02 12:00:00+00:00",
            "2024-01-06 11:00:00+00:00",
            "2024-01-02 18:00:00+00:00",
        ],
        name="timestamp",
    )
    return pd.DataFrame(
        {
            "bb_percent_b_40_2.0": [0.10, 0.10, 0.20, 0.10, 0.10, 0.10],
            "close_rsi_28": [30.0, 30.0, 30.0, 40.0, 30.0, 30.0],
            "roc_8": [-0.001, -0.001, -0.001, -0.001, -0.001, -0.001],
            "close_over_ema_200": [0.001, 0.001, 0.001, 0.001, 0.001, 0.001],
            "atr_pct_rank_336": [0.50, 0.50, 0.50, 0.50, 0.50, 0.50],
            "spread_rank_336": [0.50, 0.50, 0.50, 0.50, 0.50, 0.50],
            "is_weekend": [0, 0, 0, 0, 1, 0],
        },
        index=idx,
    )


def test_eurusd_session_bb_reversion_emits_only_complete_long_candidates() -> None:
    out, meta = build_eurusd_session_bb_reversion_signal(_frame())

    assert meta["kind"] == "eurusd_session_bb_reversion"
    assert meta["side"] == "long_only"
    assert out["signal_candidate"].tolist() == [0, 1, 0, 0, 0, 0]
    assert out["signal_side"].tolist() == [0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    assert out["eurusd_bb_reversion_score"].tolist() == [7, 8, 7, 7, 7, 7]

    stepped = apply_signal_step(_frame(), {"kind": "eurusd_session_bb_reversion"})
    assert stepped["signal_side"].tolist() == out["signal_side"].tolist()


def test_eurusd_session_bb_reversion_uses_current_and_trailing_inputs_only() -> None:
    baseline = eurusd_session_bb_reversion_signal(_frame())
    mutated = _frame()
    mutated.loc[mutated.index[-1], "bb_percent_b_40_2.0"] = 0.01
    mutated.loc[mutated.index[-1], "close_rsi_28"] = 10.0
    mutated.loc[mutated.index[-1], "roc_8"] = -0.01
    changed = eurusd_session_bb_reversion_signal(mutated)

    compare_cols = ["signal_candidate", "signal_side", "eurusd_bb_reversion_score"]
    pd.testing.assert_frame_equal(
        baseline.iloc[:-1][compare_cols],
        changed.iloc[:-1][compare_cols],
    )


def test_eurusd_session_bb_reversion_requires_feature_columns() -> None:
    with pytest.raises(KeyError, match="close_rsi_28"):
        eurusd_session_bb_reversion_signal(_frame().drop(columns=["close_rsi_28"]))


def test_eurusd_session_bb_reversion_is_registered() -> None:
    assert get_signal_fn("eurusd_session_bb_reversion") is eurusd_session_bb_reversion_signal


def test_eurusd_session_bb_reversion_config_loads() -> None:
    cfg = load_experiment_config(
        Path("config/experiments/eurusd_session_bb_reversion/eurusd_30m_session_bb_reversion_long_only_v1.yaml")
    )

    assert cfg["model"]["kind"] == "none"
    assert cfg["signals"]["kind"] == "eurusd_session_bb_reversion"
    assert cfg["signals"]["params"]["bb_percent_b_max"] == 0.12
    assert cfg["signals"]["params"]["rsi_max"] == 35.0
    assert cfg["backtest"]["engine"] == "manual_barrier"
    assert cfg["backtest"]["allow_short"] is False
