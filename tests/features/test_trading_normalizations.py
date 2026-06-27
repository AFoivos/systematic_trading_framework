from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers import apply_feature_helpers
from src.features.helpers.normalizations import (
    add_atr_scaled_distance_features,
    add_range_position_features,
    add_realized_vol_percentile_features,
    add_robust_zscore_features,
    add_rolling_beta_residual_features,
    add_rolling_percent_rank_features,
    add_volatility_scaled_return_features,
    add_volume_relative_features,
)


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=8, freq="h")
    return pd.DataFrame(
        {
            "close": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0],
            "high": [11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0],
            "low": [9.0, 9.5, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
            "level": [10.0, 10.5, 11.0, 12.0, 13.5, 14.0, 15.5, 16.0],
            "atr": [1.0, 1.0, 2.0, 2.0, 2.0, 2.5, 2.5, 2.5],
            "ret": [0.01, 0.02, -0.01, 0.03, 0.00, 0.02, -0.02, 0.01],
            "bench_ret": [0.01, 0.01, -0.02, 0.02, 0.00, 0.01, -0.01, 0.00],
            "vol": [0.10, 0.20, 0.15, 0.30, 0.25, 0.40, 0.35, 0.50],
            "volume": [100.0, 120.0, 80.0, 160.0, 200.0, 150.0, 220.0, 180.0],
        },
        index=idx,
    )


def test_rolling_percent_rank_uses_prior_window_by_default() -> None:
    out = add_rolling_percent_rank_features(
        _frame(),
        source_col="close",
        window=3,
        min_periods=3,
        output_col="close_pr",
    )

    assert np.isnan(out["close_pr"].iloc[2])
    assert out["close_pr"].iloc[3] == 1.0


def test_robust_zscore_uses_shifted_median_and_mad() -> None:
    out = add_robust_zscore_features(
        _frame(),
        source_col="close",
        window=3,
        min_periods=3,
        output_col="close_rz",
        mad_scale=1.0,
    )

    assert np.isnan(out["close_rz"].iloc[2])
    assert out["close_rz"].iloc[3] == 2.0


def test_volatility_scaled_return_and_atr_scaled_distance() -> None:
    out = add_volatility_scaled_return_features(
        _frame(),
        return_col="ret",
        volatility_col="vol",
        output_col="ret_over_vol",
    )
    out = add_atr_scaled_distance_features(
        out,
        base_col="close",
        ref_col="level",
        atr_col="atr",
        output_col="close_level_atr",
    )

    assert out["ret_over_vol"].iloc[0] == np.float32(0.1)
    assert out["close_level_atr"].iloc[2] == np.float32(0.5)


def test_range_position_and_realized_vol_percentile() -> None:
    out = add_range_position_features(
        _frame(),
        value_col="close",
        high_col="high",
        low_col="low",
        window=3,
        output_col="range_pos",
    )
    out = add_realized_vol_percentile_features(
        out,
        volatility_col="vol",
        window=3,
        min_periods=3,
        output_col="vol_pct",
    )

    assert out["range_pos"].dropna().between(0.0, 1.0).all()
    assert np.isnan(out["vol_pct"].iloc[2])
    assert out["vol_pct"].iloc[3] == 1.0


def test_volume_relative_emits_zscore_only_when_requested() -> None:
    out = add_volume_relative_features(
        _frame(),
        volume_col="volume",
        window=3,
        min_periods=3,
        output_col="rel_volume",
    )
    assert "rel_volume" in out.columns
    assert "volume_zscore_3" not in out.columns

    with_z = add_volume_relative_features(
        _frame(),
        volume_col="volume",
        window=3,
        min_periods=3,
        output_col="rel_volume",
        zscore_col="volume_z",
    )
    assert "volume_z" in with_z.columns


def test_rolling_beta_residual_emits_beta_only_when_requested() -> None:
    out = add_rolling_beta_residual_features(
        _frame(),
        asset_return_col="ret",
        benchmark_return_col="bench_ret",
        window=4,
        min_periods=4,
        residual_col="ret_resid",
    )
    assert "ret_resid" in out.columns
    assert "ret_beta" not in out.columns

    with_beta = add_rolling_beta_residual_features(
        _frame(),
        asset_return_col="ret",
        benchmark_return_col="bench_ret",
        window=4,
        min_periods=4,
        residual_col="ret_resid",
        beta_col="ret_beta",
        alpha_col="ret_alpha",
    )
    assert {"ret_beta", "ret_alpha"}.issubset(with_beta.columns)


def test_trading_normalizations_are_available_through_helper_registry() -> None:
    out = apply_feature_helpers(
        _frame(),
        normalizations={
            "rolling_percent_rank": {
                "params": {
                    "source_col": "close",
                    "window": 3,
                    "min_periods": 3,
                    "output_col": "close_pr",
                }
            },
            "atr_scaled_distance": {
                "params": {
                    "base_col": "close",
                    "ref_col": "level",
                    "atr_col": "atr",
                    "output_col": "close_level_atr",
                }
            },
        },
    )

    assert {"close_pr", "close_level_atr"}.issubset(out.columns)
