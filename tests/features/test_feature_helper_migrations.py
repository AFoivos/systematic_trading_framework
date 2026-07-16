from __future__ import annotations

import pandas as pd
from pandas.testing import assert_series_equal

from src.features.helpers import apply_feature_helpers
from src.features.helpers.normalizations.returns import add_close_returns, compute_returns
from src.features.lags import add_lagged_features
from src.features.technical.return_momentum import add_return_momentum_features
from src.features.technical.vol_normalized_momentum import add_vol_normalized_momentum_features
from src.features.trend_slope_volatility import add_trend_slope_volatility
from src.features.volatility_of_volatility import add_volatility_of_volatility
from src.features.zscore_momentum import add_zscore_momentum

from ._helpers import synthetic_ohlcv


def _assert_equal(left: pd.Series, right: pd.Series) -> None:
    assert_series_equal(left, right, check_dtype=False, check_names=False, check_exact=False, atol=1e-6)


def test_returns_helper_keeps_legacy_add_close_returns_contract() -> None:
    df = synthetic_ohlcv()

    out = add_close_returns(df, log=True, col_name="close_logret")

    _assert_equal(out["close_logret"], compute_returns(df["close"], log=True, dropna=False))


def test_lag_helper_replaces_lagged_feature_builder_for_single_columns() -> None:
    df = synthetic_ohlcv()
    legacy = add_lagged_features(df, cols=["close"], lags=(1, 3), prefix="lag")
    helper = apply_feature_helpers(
        df,
        transforms={
            "lag": {
                "items": [
                    {"source_col": "close", "lag": 1, "output_col": "lag_close_1"},
                    {"source_col": "close", "lag": 3, "output_col": "lag_close_3"},
                ]
            }
        },
    )

    _assert_equal(helper["lag_close_1"], legacy["lag_close_1"])
    _assert_equal(helper["lag_close_3"], legacy["lag_close_3"])


def test_rolling_zscore_helper_replaces_zscore_momentum() -> None:
    df = synthetic_ohlcv()
    legacy = add_zscore_momentum(df, price_col="close", window=20, output_col="zscore_momentum_20")
    helper = apply_feature_helpers(
        df,
        transforms={
            "rolling_zscore": {
                "source_col": "close",
                "window": 20,
                "shift": 0,
                "ddof": 0,
                "output_col": "zscore_momentum_20",
            }
        },
    )

    _assert_equal(helper["zscore_momentum_20"], legacy["zscore_momentum_20"])


def test_rolling_sum_helper_replaces_return_momentum() -> None:
    df = add_close_returns(synthetic_ohlcv(), log=True, col_name="close_logret")
    legacy = add_return_momentum_features(df, returns_col="close_logret", windows=(5,), inplace=False)
    helper = apply_feature_helpers(
        df,
        transforms={
            "rolling_sum": {
                "source_col": "close_logret",
                "window": 5,
                "output_col": "close_logret_mom_5",
            }
        },
    )

    _assert_equal(helper["close_logret_mom_5"], legacy["close_logret_mom_5"])


def test_rolling_sum_and_ratio_helpers_replace_vol_normalized_momentum() -> None:
    df = add_close_returns(synthetic_ohlcv(), log=True, col_name="close_logret")
    df["vol_rolling_10"] = df["close_logret"].rolling(10).std(ddof=1)
    legacy = add_vol_normalized_momentum_features(
        df,
        returns_col="close_logret",
        vol_col="vol_rolling_10",
        windows=(5,),
        eps=1e-8,
        inplace=False,
    )
    helper = apply_feature_helpers(
        df,
        transforms={
            "rolling_sum": {
                "source_col": "close_logret",
                "window": 5,
                "output_col": "close_logret_mom_5",
            },
            "ratio": {
                "numerator_col": "close_logret_mom_5",
                "denominator_col": "vol_rolling_10",
                "denominator_offset": 1e-8,
                "eps": 0.0,
                "output_col": "close_logret_norm_mom_5",
            },
        },
    )

    _assert_equal(helper["close_logret_norm_mom_5"], legacy["close_logret_norm_mom_5"])


def test_volatility_of_volatility_can_be_composed_from_helpers() -> None:
    df = synthetic_ohlcv()
    legacy = add_volatility_of_volatility(
        df,
        volatility_col="vol",
        window=12,
        mean_window=8,
        output_col="vov",
        mean_col="vov_mean",
        ratio_col="vov_ratio",
        rising_col="vov_rising",
        high_vov_col="vov_high",
        high_vov_mult=1.2,
    )
    helper = apply_feature_helpers(
        df,
        transforms={
            "rolling_std": {"source_col": "vol", "window": 12, "ddof": 0, "output_col": "vov"},
            "rolling_mean": {"source_col": "vov", "window": 8, "output_col": "vov_mean"},
            "ratio": {"numerator_col": "vov", "denominator_col": "vov_mean", "eps": 0.0, "output_col": "vov_ratio"},
            "threshold_flag": {"source_col": "vov_ratio", "threshold": 1.2, "op": "gt", "output_col": "vov_high"},
            "rising_flag": {"source_col": "vov", "output_col": "vov_rising"},
        },
    )

    for column in ["vov", "vov_mean", "vov_ratio", "vov_high", "vov_rising"]:
        _assert_equal(helper[column], legacy[column])


def test_trend_slope_volatility_can_be_composed_from_helpers() -> None:
    df = synthetic_ohlcv()
    df["close_pct_change"] = df["close"].pct_change()
    legacy = add_trend_slope_volatility(
        df,
        price_col="close",
        volatility_col=None,
        window=12,
        slope_col="trend_slope_12",
        volatility_used_col="trend_slope_volatility_used_12",
        slope_vol_ratio_col="trend_slope_vol_ratio_12",
        positive_col="trend_slope_vol_ratio_12_positive",
        rising_col="trend_slope_vol_ratio_12_rising",
        strong_trend_col="trend_slope_vol_ratio_12_strong",
        strong_threshold=1.0,
    )
    helper = apply_feature_helpers(
        df,
        transforms={
            "slope": {"source_col": "close", "window": 12, "output_col": "trend_slope_12"},
            "rolling_std": {
                "source_col": "close_pct_change",
                "window": 12,
                "ddof": 1,
                "output_col": "trend_slope_volatility_used_12",
            },
            "ratio": {
                "items": [
                    {
                        "numerator_col": "trend_slope_12",
                        "denominator_col": "close",
                        "eps": 0.0,
                        "output_col": "trend_fractional_slope_12",
                    },
                    {
                        "numerator_col": "trend_fractional_slope_12",
                        "denominator_col": "trend_slope_volatility_used_12",
                        "eps": 0.0,
                        "output_col": "trend_slope_vol_ratio_12",
                    },
                ],
            },
            "rising_flag": {
                "source_col": "trend_slope_vol_ratio_12",
                "output_col": "trend_slope_vol_ratio_12_rising",
            },
            "threshold_flag": {
                "items": [
                    {
                        "source_col": "trend_slope_vol_ratio_12",
                        "threshold": 0.0,
                        "op": "gt",
                        "output_col": "trend_slope_vol_ratio_12_positive",
                    },
                    {
                        "source_col": "trend_slope_vol_ratio_12",
                        "threshold": 1.0,
                        "op": "ge",
                        "use_abs": True,
                        "output_col": "trend_slope_vol_ratio_12_strong",
                    },
                ]
            },
        },
    )

    for column in [
        "trend_slope_12",
        "trend_slope_volatility_used_12",
        "trend_slope_vol_ratio_12",
        "trend_slope_vol_ratio_12_positive",
        "trend_slope_vol_ratio_12_rising",
        "trend_slope_vol_ratio_12_strong",
    ]:
        _assert_equal(helper[column], legacy[column])


def test_rolling_linear_regression_composes_with_canonical_flag_helpers() -> None:
    df = synthetic_ohlcv()
    helper = apply_feature_helpers(
        df,
        transforms={
            "rolling_linear_regression": {
                "source_col": "close",
                "window": 12,
                "r2_col": "rolling_r2_12",
                "slope_col": "rolling_r2_slope_12",
                "intercept_col": "rolling_r2_intercept_12",
            },
            "rising_flag": {"source_col": "rolling_r2_12", "output_col": "rolling_r2_12_rising"},
            "threshold_flag": {
                "source_col": "rolling_r2_12",
                "threshold": 0.60,
                "op": "ge",
                "output_col": "rolling_r2_12_ok",
            },
        },
    )

    assert helper["rolling_r2_12"].iloc[:11].isna().all()
    assert helper["rolling_r2_slope_12"].dropna().abs().gt(0.0).any()
    assert helper["rolling_r2_12"].dropna().between(0.0, 1.0).all()
    assert helper["rolling_r2_12_rising"].dtype == "int8"
    assert helper["rolling_r2_12_ok"].dtype == "int8"
