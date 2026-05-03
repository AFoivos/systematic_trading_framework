import pandas as pd
import numpy as np
import pytest

from src.features.returns import compute_returns
from src.features.regime_context import add_regime_context_features
from src.features.technical.adx import add_adx_features
from src.features.technical.atr import add_atr_features
from src.features.technical.trend import add_trend_features
from src.src_data.validation import validate_ohlcv
from src.backtesting.engine import run_backtest
from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.signals.roc_long_only_conditions_signal import roc_long_only_conditions_signal
from src.signals.volatility_signal import compute_volatility_regime_signal
from src.utils.config import load_experiment_config


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


def test_range_features_support_superset_windows() -> None:
    df = pd.DataFrame(
        {
            "high": [2.0, 2.2, 2.4, 2.8, 3.0, 3.3],
            "low": [1.0, 1.1, 1.3, 1.7, 1.9, 2.0],
            "close": [1.5, 1.8, 2.0, 2.4, 2.5, 2.9],
        }
    )

    out = add_atr_features(df, windows=[2, 3])
    out = add_adx_features(out, windows=[2, 3])

    assert {"atr_2", "atr_over_price_2", "atr_3", "atr_over_price_3"}.issubset(out.columns)
    assert {"adx_2", "plus_di_2", "minus_di_2", "adx_3", "plus_di_3", "minus_di_3"}.issubset(out.columns)


def test_regime_context_supports_superset_vol_window_pairs() -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="h")
    df = pd.DataFrame({"close": [1.0, 1.1, 1.0, 1.2, 1.25, 1.2, 1.3, 1.35]}, index=idx)

    out = add_regime_context_features(
        df,
        returns_col="close_ret",
        vol_window_pairs=[(2, 4), (3, 5)],
    )

    assert "regime_vol_ratio_2_4" in out.columns
    assert "regime_vol_ratio_3_5" in out.columns
    assert "regime_absret_z_2_4" in out.columns
    assert "regime_absret_z_3_5" in out.columns


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


def test_validate_ohlcv_rejects_missing_core_prices() -> None:
    """
    Verify that OHLCV rejects missing core prices behaves as expected under a representative
    regression scenario. The test protects the intended contract of the surrounding component
    and makes failures easier to localize.
    """
    idx = pd.date_range("2020-01-01", periods=2, freq="D")
    df = pd.DataFrame(
        {
            "open": [10.0, np.nan],
            "high": [11.0, 12.0],
            "low": [9.0, 10.0],
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


def test_run_backtest_enforces_min_holding_bars() -> None:
    """
    Backtest-level minimum holding should suppress flips until the holding window expires.
    """
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, -1.0, -1.0, 0.0, 0.0],
            "returns": [0.0, 0.01, -0.02, 0.03, 0.0],
        },
        index=idx,
    )

    bt = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        dd_guard=False,
        min_holding_bars=2,
    )

    assert bt.positions.tolist() == [1.0, 1.0, -1.0, -1.0, 0.0]
    assert bt.turnover.tolist() == [1.0, 0.0, 2.0, 0.0, 1.0]


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


def test_roc_long_only_conditions_signal_is_score_based_and_long_only() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="30min")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "close": [101.0, 101.0, 101.0],
            "is_weekend": [0.0, 1.0, 0.0],
            "roc_12": [0.01, 0.01, -0.01],
            "regime_vol_ratio_z_24_168": [0.5, 0.5, 0.5],
            "mtf_1h_trend_score": [0.0, 0.0, 0.0],
            "mtf_4h_trend_score": [0.0, 0.0, 0.0],
            "close_z": [0.0, 0.0, 0.0],
        },
        index=idx,
    )

    out = roc_long_only_conditions_signal(
        df,
        roc_window=12,
        vol_short_window=24,
        vol_long_window=168,
        min_score_required=5,
        vol_adjustment_strength=1.0,
    )

    assert out["manual_long_signal"].tolist() == [1, 0, 1]
    assert out["short_signal"].eq(0).all()
    assert out["manual_vol_adjusted_signal"].iloc[0] == pytest.approx(1.0 / 1.5)
    assert "manual_conviction_score" in out.columns
    assert "close_open_ratio" in out.columns


def test_manual_barrier_backtest_enters_next_open_and_records_trade_levels() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="30min")
    df = pd.DataFrame(
        {
            "signal": [1.0, 0.0, 0.0, 0.0],
            "open": [999.0, 100.0, 100.0, 100.0],
            "high": [999.0, 101.5, 100.5, 100.5],
            "low": [999.0, 99.8, 99.8, 99.8],
            "close": [999.0, 101.0, 100.0, 100.0],
        },
        index=idx,
    )

    result = run_manual_barrier_backtest(
        df,
        signal_col="signal",
        take_profit_r=1.0,
        stop_loss_r=1.0,
        risk_per_trade=0.01,
        max_holding_bars=3,
        cost_per_unit_turnover=0.0,
        slippage_per_unit_turnover=0.0,
        periods_per_year=48,
    )

    assert result.trades is not None
    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["signal_timestamp"] == idx[0]
    assert trade["entry_timestamp"] == idx[1]
    assert trade["exit_timestamp"] == idx[1]
    assert trade["entry_price"] == pytest.approx(100.0)
    assert trade["take_profit_price"] == pytest.approx(101.0)
    assert trade["stop_loss_price"] == pytest.approx(99.0)
    assert trade["exit_reason"] == "take_profit"
    assert result.returns.loc[idx[1]] == pytest.approx(0.01)


def test_roc_long_only_configs_load_as_manual_barrier_experiments() -> None:
    config_paths = [
        "config/experiments/roc_long_only/xauusd_roc_long_only_manual_barrier.yaml",
        "config/experiments/roc_long_only/us100_roc_long_only_manual_barrier.yaml",
        "config/experiments/roc_long_only/us30_roc_long_only_manual_barrier.yaml",
        "config/experiments/roc_long_only/ger40_roc_long_only_manual_barrier.yaml",
        "config/experiments/roc_long_only/spx500_roc_long_only_manual_barrier.yaml",
    ]

    for config_path in config_paths:
        cfg = load_experiment_config(config_path)
        assert cfg["model"]["kind"] == "none"
        assert cfg["model"]["target"]["kind"] == "r_multiple"
        assert cfg["model"]["target"]["candidate_col"] == "manual_long_signal"
        assert cfg["signals"]["kind"] == "roc_long_only_conditions"
        assert cfg["backtest"]["engine"] == "manual_barrier"
        assert cfg["backtest"]["signal_col"] == "manual_vol_adjusted_signal"


def test_run_backtest_vol_targeting_flattens_missing_vol_warmup() -> None:
    """
    Verify that backtest vol targeting flattens missing vol warmup behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0, 1.0, 1.0],
            "returns": [0.01, 0.01, 0.01, 0.01, 0.01],
            "vol": [np.nan, np.nan, 0.2, 0.2, 0.2],
        },
        index=idx,
    )

    bt = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        target_vol=0.1,
        vol_col="vol",
        dd_guard=False,
    )

    assert bt.positions.iloc[:2].eq(0.0).all()
    assert bt.turnover.iloc[:2].eq(0.0).all()
    assert bt.costs.iloc[:2].eq(0.0).all()
    assert bt.equity_curve.notna().all()


def test_run_backtest_drawdown_guard_applies_from_next_bar() -> None:
    """
    Drawdown guard should reduce exposure only after the breach bar has completed.
    """
    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0, 1.0],
            "returns": [0.0, -0.30, 0.10, 0.10],
        },
        index=idx,
    )

    bt = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        dd_guard=True,
        max_drawdown=0.2,
        cooloff_bars=1,
    )

    assert np.isclose(bt.positions.iloc[1], 1.0)
    assert np.isclose(bt.positions.iloc[2], 0.0)
    assert np.isclose(bt.turnover.iloc[1], 0.0)


def test_run_backtest_drawdown_guard_respects_exact_cooloff_bars() -> None:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0, 1.0, 1.0],
            "returns": [0.0, -0.30, 0.50, 0.0, 0.0],
        },
        index=idx,
    )

    bt = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        dd_guard=True,
        max_drawdown=0.2,
        cooloff_bars=2,
    )

    assert bt.positions.tolist() == [1.0, 1.0, 0.0, 0.0, 1.0]


def test_run_backtest_drawdown_guard_does_not_permanently_retrigger_underwater() -> None:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0, 1.0, 1.0],
            "returns": [0.0, -0.20, 0.0, 0.0, 0.0],
        },
        index=idx,
    )

    bt = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        dd_guard=True,
        max_drawdown=0.1,
        cooloff_bars=1,
        rearm_drawdown=0.05,
    )

    assert bt.positions.tolist() == [1.0, 1.0, 0.0, 1.0, 1.0]


def test_run_backtest_drawdown_guard_can_rearm_after_recovery() -> None:
    idx = pd.date_range("2020-01-01", periods=6, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "returns": [0.0, -0.20, 0.25, 0.0, -0.15, 0.0],
        },
        index=idx,
    )

    bt = run_backtest(
        df,
        signal_col="signal",
        returns_col="returns",
        dd_guard=True,
        max_drawdown=0.1,
        cooloff_bars=1,
        rearm_drawdown=0.05,
    )

    assert bt.positions.iloc[2] == 0.0
    assert bt.positions.iloc[3] == 1.0
    assert bt.positions.iloc[5] == 0.0


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
