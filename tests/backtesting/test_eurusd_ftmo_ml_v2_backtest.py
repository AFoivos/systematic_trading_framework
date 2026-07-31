from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtesting.eurusd_ftmo_ml_v2 import run_bar_backtest
from src.risk.eurusd_ftmo_ml_v2_sizing import drawdown_scale


def _market(index: pd.DatetimeIndex) -> pd.DataFrame:
    mid = pd.Series(1.10 + np.arange(len(index)) * 0.0001, index=index)
    return pd.DataFrame(
        {
            "mid_open": mid,
            "bid_open": mid - 0.00005,
            "ask_open": mid + 0.00005,
            "spread_open": 0.0001,
            "logret1": np.log(mid).diff(),
        },
        index=index,
    )


def test_drawdown_scale_exact_boundaries() -> None:
    assert drawdown_scale(-0.025) == 1.0
    assert drawdown_scale(-0.065) == 0.0
    assert np.isclose(drawdown_scale(-0.045), 0.5)


def test_backtest_applies_targets_at_open_and_accounts_for_reversal_costs(monkeypatch) -> None:
    index = pd.date_range("2024-01-01", periods=6, freq="30min")
    market = _market(index)

    def constant_vol(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out["volatility_factor"] = 1.0
        return out

    monkeypatch.setattr("src.backtesting.eurusd_ftmo_ml_v2.add_volatility_factor", constant_vol)
    signals = pd.DataFrame({"directional_signal": [0.0, 0.1, 0.1, -0.1, 0.0, 0.0]}, index=index)
    result = run_bar_backtest(market, signals)
    assert result.positions.loc[index[1], "actual_position_multiple"] == 2.2
    assert result.positions.loc[index[3], "turnover"] == 4.4
    assert result.orders.loc[index[3], "entry_turnover"] == 2.2
    assert result.orders.loc[index[3], "exit_turnover"] == 2.2
    assert result.positions["total_cost_return"].sum() > 0.0
    assert result.positions.loc[index[4], "actual_position_multiple"] == 0.0


def test_daily_circuit_breaker_blocks_increase_but_allows_exit(monkeypatch) -> None:
    index = pd.date_range("2024-01-01 00:00", periods=5, freq="30min")
    market = _market(index)
    market.loc[index[2]:, ["mid_open", "bid_open", "ask_open"]] -= 0.02

    def constant_vol(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out["volatility_factor"] = 1.0
        return out

    monkeypatch.setattr("src.backtesting.eurusd_ftmo_ml_v2.add_volatility_factor", constant_vol)
    signals = pd.DataFrame({"directional_signal": [0.0, 0.1, 0.2, 0.2, 0.0]}, index=index)
    result = run_bar_backtest(market, signals)
    assert result.positions.loc[index[2], "daily_circuit_active"]
    assert abs(result.positions.loc[index[2], "actual_position_multiple"]) <= 2.2
    assert result.positions.loc[index[4], "actual_position_multiple"] == 0.0
