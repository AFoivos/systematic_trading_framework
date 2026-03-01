import pandas as pd
import numpy as np
import pytest

from src.features.returns import compute_returns
from src.features.technical.trend import add_trend_features
from src.src_data.validation import validate_ohlcv
from src.backtesting.engine import run_backtest
from src.signals.volatility_signal import compute_volatility_regime_signal


def test_compute_returns_simple_and_log() -> None:
    """
    Verify that returns simple and log behaves as expected under a representative regression
    scenario. The test protects the intended contract of the surrounding component and makes
    failures easier to localize.
    """
    prices = pd.Series([100.0, 110.0, 121.0], name="close")
    simple = compute_returns(prices, log=False, dropna=False)
    log = compute_returns(prices, log=True, dropna=False)

    assert np.isclose(simple.iloc[1], 0.10)
    assert np.isclose(simple.iloc[2], 0.10)
    assert np.isclose(log.iloc[1], np.log(1.1))


def test_add_trend_features_columns() -> None:
    """
    Verify that trend features columns behaves as expected under a representative regression
    scenario. The test protects the intended contract of the surrounding component and makes
    failures easier to localize.
    """
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    out = add_trend_features(df, sma_windows=(2,), ema_spans=(2,))

    assert "close_sma_2" in out.columns
    assert "close_ema_2" in out.columns
    assert "close_over_sma_2" in out.columns
    assert "close_over_ema_2" in out.columns


def test_validate_ohlcv_flags_invalid_high_low() -> None:
    """
    Verify that OHLCV flags invalid high low behaves as expected under a representative
    regression scenario. The test protects the intended contract of the surrounding component
    and makes failures easier to localize.
    """
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
    """
    Verify that backtest costs and slippage reduce returns behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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
    """
    Verify that backtest log returns are converted behaves as expected under a representative
    regression scenario. The test protects the intended contract of the surrounding component
    and makes failures easier to localize.
    """
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


def test_run_backtest_charges_initial_entry_turnover() -> None:
    """
    Verify that backtest charges initial entry turnover behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0],
            "returns": [0.0, 0.0, 0.0],
        },
        index=idx,
    )

    bt = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        cost_per_unit_turnover=0.01,
        slippage_per_unit_turnover=0.0,
        dd_guard=False,
    )

    assert np.isclose(bt.turnover.iloc[0], 1.0)
    assert np.isclose(bt.costs.iloc[0], 0.01)
    assert np.isclose(bt.returns.iloc[0], -0.01)


def test_run_backtest_raises_on_missing_return_while_exposed() -> None:
    """
    Verify that backtest raises on missing return while exposed behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0],
            "returns": [0.0, np.nan, 0.01],
        },
        index=idx,
    )

    with pytest.raises(ValueError):
        run_backtest(
            df,
            signal_col="signal",
            returns_col="returns",
            dd_guard=False,
        )


def test_volatility_regime_signal_is_causal_by_default() -> None:
    """
    Verify that volatility regime signal is causal by default behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    df = pd.DataFrame({"vol": [1.0, 2.0, 3.0, 100.0]}, index=idx)

    out = compute_volatility_regime_signal(df, vol_col="vol", quantile=0.5)

    assert np.isclose(out.loc[idx[0], "volatility_regime_signal"], 0.0)
    assert np.isclose(out.loc[idx[1], "volatility_regime_signal"], -1.0)
