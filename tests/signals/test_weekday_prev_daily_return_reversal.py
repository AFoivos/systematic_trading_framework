from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.signals.registry import get_signal_fn
from src.signals.weekday_prev_daily_return_reversal import (
    weekday_prev_daily_return_reversal_signal,
)
from src.utils.config import load_experiment_config


def _frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [
            "2024-01-02 14:00:00+00:00",
            "2024-01-02 21:00:00+00:00",
            "2024-01-03 14:00:00+00:00",
            "2024-01-03 21:00:00+00:00",
            "2024-01-04 14:00:00+00:00",
            "2024-01-04 14:30:00+00:00",
            "2024-01-04 21:00:00+00:00",
        ],
        name="timestamp",
    )
    return pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 99.0, 99.0, 99.1, 101.0],
            "high": [100.0, 100.0, 100.0, 99.0, 99.0, 99.5, 101.0],
            "low": [100.0, 100.0, 100.0, 99.0, 99.0, 99.1, 101.0],
            "close": [100.0, 100.0, 100.0, 99.0, 99.0, 99.3, 101.0],
        },
        index=idx,
    )


def test_weekday_reversal_signals_at_configured_local_time_after_weak_prior_day() -> None:
    out = weekday_prev_daily_return_reversal_signal(
        _frame(),
        prev_daily_return_max=-0.005,
    )

    assert out["signal_side"].tolist() == [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert out["signal_candidate"].sum() == 1
    assert out.loc[pd.Timestamp("2024-01-04 14:00:00+00:00"), "prev_daily_return"] == pytest.approx(-0.01)
    assert out.loc[pd.Timestamp("2024-01-04 14:00:00+00:00"), "local_weekday"] == 3
    assert out.loc[pd.Timestamp("2024-01-04 14:00:00+00:00"), "local_hour"] == 9.0


def test_weekday_reversal_does_not_use_same_day_future_close_for_signal() -> None:
    base = _frame()
    changed = base.copy()
    changed.iloc[-1, changed.columns.get_loc("close")] = 70.0

    out_base = weekday_prev_daily_return_reversal_signal(base, prev_daily_return_max=-0.005)
    out_changed = weekday_prev_daily_return_reversal_signal(changed, prev_daily_return_max=-0.005)

    signal_ts = pd.Timestamp("2024-01-04 14:00:00+00:00")
    assert out_base.loc[signal_ts, "prev_daily_return"] == out_changed.loc[signal_ts, "prev_daily_return"]
    assert out_base.loc[signal_ts, "signal_side"] == out_changed.loc[signal_ts, "signal_side"]


def test_weekday_reversal_is_available_from_signal_registry() -> None:
    assert get_signal_fn("weekday_prev_daily_return_reversal") is weekday_prev_daily_return_reversal_signal


def test_spx500_thursday_reversal_config_loads() -> None:
    cfg = load_experiment_config(
        Path(
            "config/experiments/thursday_weak_prevday_reversal/"
            "spx500_30m_thursday_weak_prevday_reversal_v1.yaml"
        )
    )

    assert cfg["model"]["kind"] == "none"
    assert cfg["signals"]["kind"] == "weekday_prev_daily_return_reversal"
    assert cfg["signals"]["params"]["weekday"] == 3
    assert cfg["signals"]["params"]["signal_hour"] == 9
    assert cfg["backtest"]["engine"] == "manual_barrier"
    assert cfg["backtest"]["max_holding_bars"] == 6
