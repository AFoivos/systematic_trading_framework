from __future__ import annotations

import pandas as pd
import pytest

from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.risk.entry_modifiers import (
    entry_risk_modifier_for_candidate,
    normalize_entry_risk_modifiers,
)


def test_previous_stop_modifier_reduces_only_the_next_matching_side() -> None:
    index = pd.date_range("2024-01-01", periods=7, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": [100.0, 100.2, 100.0, 100.2, 100.0, 100.0, 100.0],
            "low": [100.0, 98.0, 100.0, 99.8, 100.0, 100.0, 100.0],
            "close": 100.0,
            "signal": [1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            "atr_over_price": 0.01,
        },
        index=index,
    )

    result = run_manual_barrier_backtest(
        frame,
        signal_col="signal",
        take_profit_r=10.0,
        stop_loss_r=1.0,
        risk_per_trade=0.01,
        max_holding_bars=1,
        max_leverage=1.0,
        allow_short=True,
        stop_mode="volatility_stop",
        vol_col="atr_over_price",
        entry_risk_modifiers={
            "enabled": True,
            "combine": "min",
            "rules": [
                {
                    "name": "after_stop_long",
                    "kind": "previous_stop",
                    "side": "long",
                    "multiplier": 0.5,
                }
            ],
        },
    )

    assert result.trades is not None
    assert len(result.trades) == 2
    assert result.trades.iloc[0]["exit_reason"] == "stop_loss"
    assert result.trades.iloc[0]["effective_risk_per_trade"] == pytest.approx(0.01)
    assert result.trades.iloc[1]["effective_risk_per_trade"] == pytest.approx(0.005)
    assert result.trades.iloc[1]["position_size"] == pytest.approx(0.5)
    assert result.trades.iloc[1]["entry_risk_modifier_rules"] == "after_stop_long"
    assert result.summary["entry_risk_modifier_match_counts"] == {"after_stop_long": 1}


def test_column_and_hour_rules_use_min_or_multiply_without_increasing_risk() -> None:
    row = pd.Series({"close_over_ema_96": 0.015})
    rules = {
        "enabled": True,
        "combine": "min",
        "rules": [
            {
                "name": "short_ema_zone",
                "kind": "column_range",
                "side": "short",
                "col": "close_over_ema_96",
                "min": 0.01,
                "max": 0.023,
                "multiplier": 0.5,
            },
            {
                "name": "short_hour_09",
                "kind": "local_hour",
                "side": "short",
                "hours": [9],
                "timezone": "UTC",
                "multiplier": 0.4,
            },
        ],
    }

    multiplier, matched = entry_risk_modifier_for_candidate(
        row,
        timestamp=pd.Timestamp("2024-01-01 09:30", tz="UTC"),
        signal=-1.0,
        previous_exit_reason=None,
        config=rules,
    )
    assert multiplier == pytest.approx(0.4)
    assert matched == ["short_ema_zone", "short_hour_09"]

    rules["combine"] = "multiply"
    multiplier, matched = entry_risk_modifier_for_candidate(
        row,
        timestamp=pd.Timestamp("2024-01-01 09:30", tz="UTC"),
        signal=-1.0,
        previous_exit_reason=None,
        config=rules,
    )
    assert multiplier == pytest.approx(0.2)
    assert matched == ["short_ema_zone", "short_hour_09"]


@pytest.mark.parametrize(
    "config, message",
    [
        ({"enabled": True, "rules": []}, "must not be empty"),
        (
            {
                "enabled": True,
                "rules": [
                    {
                        "name": "bad",
                        "kind": "previous_stop",
                        "multiplier": 1.1,
                    }
                ],
            },
            r"in \[0, 1\]",
        ),
        (
            {
                "enabled": True,
                "rules": [
                    {
                        "name": "bad",
                        "kind": "column_range",
                        "col": "x",
                        "min": 2.0,
                        "max": 1.0,
                        "multiplier": 0.5,
                    }
                ],
            },
            "min must be <=",
        ),
    ],
)
def test_invalid_entry_risk_modifier_contract_fails_closed(
    config: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        normalize_entry_risk_modifiers(config)
