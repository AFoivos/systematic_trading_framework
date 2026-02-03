import pandas as pd
import numpy as np
import pytest

from src.features.returns import compute_returns
from src.features.technical.trend import add_trend_features
from src.data.validation import validate_ohlcv
from src.backtesting.engine import run_backtest


def test_compute_returns_simple_and_log() -> None:
    prices = pd.Series([100.0, 110.0, 121.0], name="close")
    simple = compute_returns(prices, log=False, dropna=False)
    log = compute_returns(prices, log=True, dropna=False)

    assert np.isclose(simple.iloc[1], 0.10)
    assert np.isclose(simple.iloc[2], 0.10)
    assert np.isclose(log.iloc[1], np.log(1.1))


def test_add_trend_features_columns() -> None:
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    out = add_trend_features(df, sma_windows=(2,), ema_spans=(2,))

    assert "close_sma_2" in out.columns
    assert "close_ema_2" in out.columns
    assert "close_over_sma_2" in out.columns
    assert "close_over_ema_2" in out.columns


def test_validate_ohlcv_flags_invalid_high_low() -> None:
    idx = pd.date_range("2020-01-01", periods=2, freq="D")
    df = pd.DataFrame(
        {
            "open": [10.0, 12.0],
            "high": [11.0, 10.0],
            "low": [9.0, 11.0],
            "close": [10.5, 11.5],
            "volume": [100.0, 200.0],
        },
        index=idx,
    )
    with pytest.raises(ValueError):
        validate_ohlcv(df)


def test_run_backtest_costs_and_slippage_reduce_returns() -> None:
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "signal": [0.0, 1.0, 1.0],
            "returns": [0.0, 0.01, 0.01],
        },
        index=idx,
    )

    no_cost = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        cost_per_unit_turnover=0.0,
        slippage_per_unit_turnover=0.0,
        dd_guard=False,
    )
    with_cost = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        cost_per_unit_turnover=0.001,
        slippage_per_unit_turnover=0.002,
        dd_guard=False,
    )

    assert with_cost.returns.sum() < no_cost.returns.sum()


def test_run_backtest_log_returns_are_converted() -> None:
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    logret = float(np.log(1.1))
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0],
            "logret": [0.0, logret, logret],
        },
        index=idx,
    )

    bt = run_backtest(
        df,
        signal_col="signal",
        returns_col="logret",
        returns_type="log",
        dd_guard=False,
    )

    assert np.isclose(bt.returns.iloc[1], 0.1)
    assert np.isclose(bt.equity_curve.iloc[-1], 1.21)
