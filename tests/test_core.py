import pandas as pd
import numpy as np
import pytest

from src.features.returns import compute_returns
from src.features.regime_context import add_regime_context_features
from src.features.technical.adx import add_adx_features
from src.features.technical.atr import add_atr_features
from src.features.technical.trend import add_trend_features
from src.features.technical.vwap import add_vwap_features, compute_vwap
from src.src_data.validation import validate_ohlcv
from src.backtesting.engine import run_backtest
from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.models.classification import train_logistic_regression_classifier
from src.signals.roc_long_only_conditions_signal import roc_long_only_conditions_signal
from src.signals.volatility_signal import compute_volatility_regime_signal
from src.targets.forward_return import build_forward_return_target
from src.targets.r_multiple import build_r_multiple_target
from src.targets.triple_barrier import build_triple_barrier_target
from src.utils.config import load_experiment_config
from src.utils.config_validation import ConfigValidationError, validate_features_block


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


def _vwap_ohlcv_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [9.0, 10.0, 12.0, 13.0, 14.0],
            "high": [10.0, 12.0, 14.0, 15.0, 16.0],
            "low": [8.0, 10.0, 12.0, 13.0, 14.0],
            "close": [9.0, 11.0, 13.0, 14.0, 15.0],
            "volume": [2.0, 3.0, 5.0, 7.0, 11.0],
        },
        index=pd.date_range("2024-01-01", periods=5, freq="h"),
    )


def test_compute_vwap_uses_trailing_price_volume_window() -> None:
    price = pd.Series([9.0, 11.0, 13.0], name="typical_price")
    volume = pd.Series([2.0, 3.0, 5.0], name="volume")

    vwap = compute_vwap(price, volume, window=2)

    assert np.isnan(vwap.iloc[0])
    assert vwap.iloc[1] == pytest.approx((9.0 * 2.0 + 11.0 * 3.0) / 5.0)
    assert vwap.iloc[2] == pytest.approx((11.0 * 3.0 + 13.0 * 5.0) / 8.0)
    assert vwap.name == "vwap_2"


def test_vwap_feature_step_emits_vwap_and_close_distance() -> None:
    step = {
        "step": "vwap",
        "params": {
            "high_col": "high",
            "low_col": "low",
            "close_col": "close",
            "volume_col": "volume",
            "windows": [2, 3],
        },
    }

    validate_features_block([step])
    out = apply_feature_steps(_vwap_ohlcv_frame(), [step])

    assert {"vwap_2", "close_over_vwap_2", "vwap_3", "close_over_vwap_3"}.issubset(out.columns)
    expected_vwap_2 = (11.0 * 3.0 + 13.0 * 5.0) / 8.0
    assert out["vwap_2"].iloc[2] == pytest.approx(expected_vwap_2)
    assert out["close_over_vwap_2"].iloc[2] == pytest.approx(13.0 / expected_vwap_2 - 1.0)


def test_vwap_feature_is_point_in_time_safe_when_future_changes() -> None:
    baseline = add_vwap_features(_vwap_ohlcv_frame(), windows=[3])

    future_changed = _vwap_ohlcv_frame()
    future_changed.loc[future_changed.index[-1], ["high", "low", "close", "volume"]] = [
        1000.0,
        900.0,
        950.0,
        10000.0,
    ]
    changed = add_vwap_features(future_changed, windows=[3])

    pd.testing.assert_series_equal(
        baseline["vwap_3"].iloc[:4],
        changed["vwap_3"].iloc[:4],
    )
    pd.testing.assert_series_equal(
        baseline["close_over_vwap_3"].iloc[:4],
        changed["close_over_vwap_3"].iloc[:4],
    )


def test_vwap_config_validation_rejects_invalid_window() -> None:
    with pytest.raises(ConfigValidationError, match="features\\[\\]\\.params\\.windows\\[0\\]"):
        validate_features_block([{"step": "vwap", "params": {"windows": [0]}}])


def _output_alias_price_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=6, freq="30min")
    return pd.DataFrame(
        {
            "open": [100.0, 100.0, 101.0, 102.0, 101.0, 100.0],
            "high": [100.5, 102.0, 102.5, 102.5, 101.5, 100.5],
            "low": [99.5, 99.5, 100.5, 100.5, 99.0, 99.0],
            "close": [100.0, 101.0, 102.0, 101.0, 100.0, 99.0],
            "ret": [0.0, 0.01, 0.0099, -0.0098, -0.0099, -0.01],
            "candidate": [1.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            "side": [1.0, 0.0, -1.0, 0.0, 0.0, 0.0],
            "vol": [0.01] * 6,
        },
        index=idx,
    )


def test_forward_return_target_outputs_aliases_columns() -> None:
    out, label_col, fwd_col, meta = build_forward_return_target(
        _output_alias_price_frame(),
        {
            "price_col": "close",
            "horizon": 1,
            "outputs": {
                "label_col": "my_label",
                "fwd_col": "my_forward_return",
            },
        },
    )

    assert label_col == "my_label"
    assert fwd_col == "my_forward_return"
    assert {"my_label", "my_forward_return"}.issubset(out.columns)
    assert meta["output_cols"] == ["my_forward_return", "my_label"]


def test_triple_barrier_target_outputs_aliases_all_diagnostic_columns() -> None:
    out, label_col, fwd_col, meta = build_triple_barrier_target(
        _output_alias_price_frame(),
        {
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "returns_col": "ret",
            "side_col": "side",
            "candidate_col": "candidate",
            "label_mode": "meta",
            "entry_price_mode": "next_open",
            "max_holding": 2,
            "upper_mult": 1.0,
            "lower_mult": 1.0,
            "vol_window": 2,
            "min_vol": 0.0001,
            "add_r_multiple": True,
            "outputs": {
                "label_col": "tb_label_custom",
                "event_ret_col": "tb_ret_custom",
                "fwd_col": "tb_fwd_custom",
                "candidate_out_col": "tb_candidate_custom",
                "r_col": "tb_r_custom",
                "oriented_r_col": "tb_oriented_r_custom",
                "hit_step_col": "tb_hit_step_custom",
                "hit_type_col": "tb_hit_type_custom",
                "upper_barrier_col": "tb_upper_custom",
                "lower_barrier_col": "tb_lower_custom",
                "meta_side_col": "tb_side_custom",
                "oriented_ret_col": "tb_oriented_ret_custom",
                "vol_source_col": "tb_vol_custom",
            },
        },
    )

    expected = {
        "tb_label_custom",
        "tb_ret_custom",
        "tb_fwd_custom",
        "tb_candidate_custom",
        "tb_r_custom",
        "tb_oriented_r_custom",
        "tb_hit_step_custom",
        "tb_hit_type_custom",
        "tb_upper_custom",
        "tb_lower_custom",
        "tb_side_custom",
        "tb_oriented_ret_custom",
        "tb_vol_custom",
    }
    assert label_col == "tb_label_custom"
    assert fwd_col == "tb_fwd_custom"
    assert expected.issubset(out.columns)
    assert expected.issubset(set(meta["output_cols"]))
    assert meta["hit_step_col"] == "tb_hit_step_custom"
    assert meta["upper_barrier_col"] == "tb_upper_custom"


def test_r_multiple_target_outputs_aliases_execution_columns() -> None:
    out, label_col, fwd_col, meta = build_r_multiple_target(
        _output_alias_price_frame(),
        {
            "candidate_col": "candidate",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "volatility_col": "vol",
            "max_holding_bars": 2,
            "allow_partial_horizon": True,
            "outputs": {
                "label_col": "r_label_custom",
                "fwd_col": "r_ret_custom",
                "candidate_out_col": "r_candidate_custom",
                "trade_r_col": "r_trade_custom",
                "oriented_r_col": "r_oriented_custom",
                "entry_price_col": "r_entry_custom",
                "exit_price_col": "r_exit_custom",
                "stop_price_col": "r_stop_custom",
                "take_profit_price_col": "r_take_custom",
                "exit_reason_col": "r_reason_custom",
                "bars_held_col": "r_bars_custom",
                "hit_type_col": "r_hit_type_custom",
                "hit_step_col": "r_hit_step_custom",
            },
        },
    )

    expected = {
        "r_label_custom",
        "r_ret_custom",
        "r_candidate_custom",
        "r_trade_custom",
        "r_oriented_custom",
        "r_entry_custom",
        "r_exit_custom",
        "r_stop_custom",
        "r_take_custom",
        "r_reason_custom",
        "r_bars_custom",
        "r_hit_type_custom",
        "r_hit_step_custom",
    }
    assert label_col == "r_label_custom"
    assert fwd_col == "r_ret_custom"
    assert expected.issubset(out.columns)
    assert expected.issubset(set(meta["output_cols"]))
    assert meta["trade_r_col"] == "r_trade_custom"
    assert meta["exit_reason_col"] == "r_reason_custom"


def test_signal_outputs_aliases_rename_emitted_signal_columns() -> None:
    frame = pd.DataFrame({"pred_prob": [0.40, 0.60, 0.50]})

    out = apply_signal_step(
        frame,
        {
            "kind": "probability_threshold",
            "params": {
                "prob_col": "pred_prob",
                "signal_col": "raw_signal",
                "upper": 0.55,
                "lower": 0.45,
                "mode": "long_short",
            },
            "outputs": {"raw_signal": "custom_signal"},
        },
    )

    assert "custom_signal" in out.columns
    assert "raw_signal" not in out.columns
    assert out["custom_signal"].tolist() == [-1.0, 1.0, 0.0]


def test_model_outputs_aliases_custom_probability_and_oos_columns() -> None:
    n = 80
    idx = pd.date_range("2024-01-01", periods=n, freq="30min")
    close = 100.0 + np.cumsum([((value % 6) - 3) * 0.1 for value in range(n)])
    frame = pd.DataFrame(
        {
            "close": close,
            "feat": [float(idx % 5) for idx in range(n)],
        },
        index=idx,
    )

    out, _, meta = train_logistic_regression_classifier(
        frame,
        {
            "kind": "logistic_regression_clf",
            "pred_prob_col": "custom_prob",
            "pred_is_oos_col": "custom_oos",
            "feature_cols": ["feat"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {"method": "walk_forward", "train_size": 40, "test_size": 20, "max_folds": 1},
        },
    )

    assert "custom_prob" in out.columns
    assert "custom_oos" in out.columns
    assert "pred_is_oos" not in out.columns
    assert int(out["custom_oos"].sum()) == 20
    assert meta["pred_prob_col"] == "custom_prob"
    assert meta["pred_is_oos_col"] == "custom_oos"


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


def test_roc_long_only_conditions_can_require_bullish_candle() -> None:
    idx = pd.date_range("2024-01-01", periods=2, freq="30min")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "close": [99.9, 101.0],
            "is_weekend": [0.0, 0.0],
            "roc_12": [0.01, 0.01],
            "regime_vol_ratio_z_24_168": [0.5, 0.5],
            "mtf_1h_trend_score": [0.0, 0.0],
            "mtf_4h_trend_score": [0.0, 0.0],
            "close_z": [0.0, 0.0],
        },
        index=idx,
    )

    out = roc_long_only_conditions_signal(
        df,
        min_score_required=5,
        close_open_ratio_min=0.0,
        require_bullish_candle=True,
        vol_adjustment_strength=0.0,
    )

    assert out["cond_bullish_candle"].tolist() == [0, 1]
    assert out["manual_long_signal"].tolist() == [0, 1]


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


def test_manual_barrier_backtest_supports_short_when_enabled() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="30min")
    df = pd.DataFrame(
        {
            "signal": [-1.0, 0.0, 0.0, 0.0],
            "open": [999.0, 100.0, 100.0, 100.0],
            "high": [999.0, 100.2, 100.2, 100.2],
            "low": [999.0, 98.8, 99.5, 99.5],
            "close": [999.0, 99.2, 100.0, 100.0],
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
        allow_short=True,
    )

    trade = result.trades.iloc[0]
    assert trade["side"] == "short"
    assert trade["entry_timestamp"] == idx[1]
    assert trade["exit_timestamp"] == idx[1]
    assert trade["take_profit_price"] == pytest.approx(99.0)
    assert trade["stop_loss_price"] == pytest.approx(101.0)
    assert trade["exit_reason"] == "take_profit"
    assert result.returns.loc[idx[1]] == pytest.approx(0.01)


def test_manual_barrier_short_configs_default_to_long_only_behavior() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="30min")
    df = pd.DataFrame(
        {
            "signal": [-1.0, 0.0, 0.0, 0.0],
            "open": [999.0, 100.0, 100.0, 100.0],
            "high": [999.0, 100.2, 98.8, 100.2],
            "low": [999.0, 98.8, 98.8, 99.8],
            "close": [999.0, 99.0, 99.5, 100.0],
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

    assert result.trades.empty


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


def test_stochrsi_cross_ma_manual_barrier_config_loads_short_execution() -> None:
    cfg = load_experiment_config(
        "config/experiments/stochrsi_cross_ma/stochrsi_cross_ma_raw_manual_barrier.yaml"
    )

    assert cfg["model"]["kind"] == "none"
    assert cfg["signals"]["kind"] == "none"
    assert cfg["backtest"]["engine"] == "manual_barrier"
    assert cfg["backtest"]["signal_col"] == "signal_side"
    assert cfg["backtest"]["allow_short"] is True


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
