from __future__ import annotations

import pandas as pd
import pytest

from src.experiments.support.ethusd_broker_alpha import TickStressSpec, tick_execution_ledger


def _scored(position: list[float]) -> pd.DataFrame:
    index = pd.date_range("2024-01-01 00:00:00", periods=len(position), freq="30min")
    return pd.DataFrame(
        {
            "position": position,
            "pred_ret": [0.0, 1.0, 1.0, 0.0],
            "atr_over_price_48": [0.01] * len(position),
        },
        index=index,
    )


def _ticks() -> pd.DataFrame:
    index = pd.DatetimeIndex(
        [
            "2024-01-01 00:59:59.900",
            "2024-01-01 01:00:00.100",
            "2024-01-01 02:00:00.200",
            "2024-01-01 02:00:01.000",
        ]
    )
    frame = pd.DataFrame(
        {
            "bid": [99.0, 100.0, 110.0, 110.0],
            "ask": [101.0, 102.0, 112.0, 112.0],
        },
        index=index,
    )
    frame["mid"] = (frame["bid"] + frame["ask"]) / 2.0
    frame["spread"] = frame["ask"] - frame["bid"]
    frame["spread_bps"] = frame["spread"] / frame["mid"] * 10_000.0
    return frame


def test_tick_replay_uses_completed_bar_decision_and_side_aware_quotes() -> None:
    stress = TickStressSpec(
        delay_seconds=0,
        spread_multiplier=1.0,
        slippage_bps_per_side=0.0,
        commission_bps_per_side=0.0,
        maximum_quote_wait_seconds=1,
    )

    ledger, diagnostics = tick_execution_ledger(_scored([0.0, 1.0, 1.0, 0.0]), _ticks(), stress=stress)

    assert diagnostics["executed_closed_trades"] == 1
    trade = ledger.iloc[0]
    assert trade["signal_timestamp"] == pd.Timestamp("2024-01-01 00:30:00")
    assert trade["entry_decision_timestamp"] == pd.Timestamp("2024-01-01 01:00:00")
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-01 01:00:00.100")
    assert trade["entry_price"] == pytest.approx(102.0)
    assert trade["exit_price"] == pytest.approx(110.0)
    assert trade["net_return"] == pytest.approx(110.0 / 102.0 - 1.0)


def test_tick_replay_short_enters_bid_and_exits_ask() -> None:
    stress = TickStressSpec(
        delay_seconds=0,
        spread_multiplier=1.0,
        slippage_bps_per_side=0.0,
        commission_bps_per_side=0.0,
        maximum_quote_wait_seconds=1,
    )

    ledger, _ = tick_execution_ledger(_scored([0.0, -1.0, -1.0, 0.0]), _ticks(), stress=stress)

    trade = ledger.iloc[0]
    assert trade["entry_price"] == pytest.approx(100.0)
    assert trade["exit_price"] == pytest.approx(112.0)
    assert trade["net_return"] == pytest.approx(1.0 - 112.0 / 100.0)
