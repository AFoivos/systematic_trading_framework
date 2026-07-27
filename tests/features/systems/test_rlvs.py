from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from src.features.systems.rlvs import (
    HARVolatilityForecaster,
    RLVS_OUTPUT_COLUMNS,
    add_rlvs_features,
)

from .conftest import make_fallback_m1


def _volatility_path(
    low_scale: float,
    high_scale: float,
    *,
    periods: int = 480,
    switch: int = 280,
) -> pd.DataFrame:
    index = pd.date_range("2025-02-01", periods=periods, freq="min", tz="UTC")
    position = np.arange(periods, dtype=float)
    scale = np.where(position < switch, low_scale, high_scale)
    deterministic_return = scale * (
        np.sin(position * 1.71) + 0.55 * np.cos(position * 0.43)
    )
    close = 1.10 * np.exp(np.cumsum(deterministic_return))
    open_ = np.r_[close[0], close[:-1]]
    half_range = close * np.maximum(scale * 1.75, 1e-7)
    high = np.maximum(open_, close) + half_range
    low = np.minimum(open_, close) - half_range
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "spread_bps": 0.8,
        },
        index=index,
    )


def test_rlvs_contract_invariants_and_no_mutation(
    fallback_m1: pd.DataFrame,
    short_rlvs_config: dict[str, object],
) -> None:
    before = fallback_m1.copy(deep=True)
    out = add_rlvs_features(fallback_m1, config=short_rlvs_config)

    pdt.assert_frame_equal(fallback_m1, before)
    assert out.index.equals(fallback_m1.index)
    assert set(RLVS_OUTPUT_COLUMNS).issubset(out.columns)
    numeric = out[list(RLVS_OUTPUT_COLUMNS)].select_dtypes(include=[np.number])
    assert not np.isinf(numeric.to_numpy(dtype=float)).any()
    for column in (
        "rlv_variance",
        "rlv_sigma",
        "rlv_state_std",
        "rlv_forecast_5",
        "rlv_forecast_15",
        "rlv_forecast_30",
        "rlv_expected_move_5",
        "rlv_expected_move_15",
        "rlv_expected_move_30",
        "rlv_fast_slow_ratio",
    ):
        assert out[column].dropna().ge(0.0).all()
    assert out["rlv_prob_high"].dropna().between(0.0, 1.0).all()
    assert out["rlv_state_uncertainty"].dropna().between(0.0, 1.0).all()
    assert set(out["rlv_regime"].dropna().unique()).issubset(
        {"low", "normal", "high", "extreme", "transition"}
    )
    assert out.attrs["rlvs_measurement_components"] == (
        "close_to_close_variance",
        "parkinson_variance",
        "rogers_satchell_variance",
    )


def test_rlvs_prefix_invariance(
    fallback_m1: pd.DataFrame,
    short_rlvs_config: dict[str, object],
) -> None:
    cutoff = 310
    prefix = add_rlvs_features(fallback_m1.iloc[:cutoff], config=short_rlvs_config)
    full = add_rlvs_features(fallback_m1, config=short_rlvs_config)

    pdt.assert_frame_equal(
        prefix[list(RLVS_OUTPUT_COLUMNS)],
        full.iloc[:cutoff][list(RLVS_OUTPUT_COLUMNS)],
        check_exact=True,
    )


def test_rlvs_regime_baseline_is_shifted(
    fallback_m1: pd.DataFrame,
    short_rlvs_config: dict[str, object],
) -> None:
    out = add_rlvs_features(fallback_m1, config=short_rlvs_config)
    expected = (
        out["rlv_log_variance"]
        .ewm(span=36, adjust=False, min_periods=12)
        .mean()
        .shift(1)
    )

    pdt.assert_series_equal(
        out["rlv_regime_baseline"],
        expected,
        check_names=False,
        check_exact=True,
    )


def test_rlvs_constant_price_has_low_volatility(
    short_rlvs_config: dict[str, object],
) -> None:
    frame = make_fallback_m1(240, drift=0.0, noise_scale=0.0)
    frame[["open", "high", "low", "close"]] = 1.10
    out = add_rlvs_features(frame, config=short_rlvs_config)

    assert out["rlv_sigma"].iloc[-1] == pytest.approx(1e-6, rel=0.05)
    assert out["rlv_forecast_30"].iloc[-1] < 1e-5


def test_rlvs_detects_volatility_expansion_and_compression(
    short_rlvs_config: dict[str, object],
) -> None:
    expansion = add_rlvs_features(
        _volatility_path(1e-5, 2.5e-4),
        config=short_rlvs_config,
    )
    compression = add_rlvs_features(
        _volatility_path(2.5e-4, 1e-5),
        config=short_rlvs_config,
    )

    expansion_tail = expansion.iloc[-30:]
    compression_tail = compression.iloc[-30:]
    compression_transition = compression.iloc[290:350]
    assert expansion_tail["rlv_regime_z"].median() > 0.0
    assert expansion_tail["rlv_fast_slow_ratio"].median() > 1.0
    assert expansion["rlv_shock_z"].iloc[280:310].max() > 0.0
    assert compression_tail["rlv_regime_z"].median() < 0.0
    assert compression_transition["rlv_fast_slow_ratio"].median() < 1.0


def test_rlvs_outlier_is_finite_and_recovers(
    fallback_m1: pd.DataFrame,
    short_rlvs_config: dict[str, object],
) -> None:
    frame = fallback_m1.copy()
    position = 220
    frame.iloc[position, frame.columns.get_loc("close")] *= 1.20
    frame.iloc[position, frame.columns.get_loc("high")] = (
        frame.iloc[position, frame.columns.get_loc("close")] * 1.01
    )
    next_open = frame.iloc[position, frame.columns.get_loc("close")]
    frame.iloc[position + 1, frame.columns.get_loc("open")] = next_open
    frame.iloc[position + 1, frame.columns.get_loc("high")] = max(
        next_open,
        frame.iloc[position + 1, frame.columns.get_loc("close")],
    ) * 1.001
    frame.iloc[position + 1, frame.columns.get_loc("low")] = min(
        next_open,
        frame.iloc[position + 1, frame.columns.get_loc("close")],
    ) * 0.999
    out = add_rlvs_features(frame, config=short_rlvs_config)

    assert np.isfinite(out["rlv_log_variance"].iloc[position:]).all()
    assert abs(float(out["rlv_log_variance"].iloc[-1] - out["rlv_regime_baseline"].iloc[-1])) < 5.0


def test_rlvs_extreme_range_bar_raises_disagreement_without_overflow(
    fallback_m1: pd.DataFrame,
    short_rlvs_config: dict[str, object],
) -> None:
    frame = fallback_m1.copy()
    position = 180
    frame.iloc[position, frame.columns.get_loc("high")] *= 1.20
    frame.iloc[position, frame.columns.get_loc("low")] *= 0.80
    out = add_rlvs_features(frame, config=short_rlvs_config)

    assert np.isfinite(out["rlv_log_variance"].iloc[position])
    assert np.isfinite(out["volatility_estimator_disagreement"].iloc[position])
    assert (
        out["volatility_estimator_disagreement"].iloc[position]
        > out["volatility_estimator_disagreement"].iloc[position - 1]
    )


def test_rlvs_empty_all_nan_and_isolated_nan(
    short_rlvs_config: dict[str, object],
) -> None:
    empty_index = pd.DatetimeIndex([], tz="UTC")
    empty = pd.DataFrame(
        columns=["open", "high", "low", "close"],
        index=empty_index,
        dtype=float,
    )
    empty_out = add_rlvs_features(empty, config=short_rlvs_config)
    assert empty_out.empty
    assert set(RLVS_OUTPUT_COLUMNS).issubset(empty_out.columns)

    index = pd.date_range("2025-01-01", periods=20, freq="min", tz="UTC")
    all_nan = pd.DataFrame(
        np.nan,
        index=index,
        columns=["open", "high", "low", "close"],
    )
    all_nan_out = add_rlvs_features(all_nan, config=short_rlvs_config)
    assert all_nan_out[list(RLVS_OUTPUT_COLUMNS)].isna().all().all()

    isolated = make_fallback_m1(160)
    isolated.loc[isolated.index[80], ["open", "high", "low", "close"]] = np.nan
    isolated_out = add_rlvs_features(isolated, config=short_rlvs_config)
    assert np.isnan(isolated_out["rlv_innovation"].iloc[80])
    assert np.isfinite(isolated_out["rlv_log_variance"].iloc[81])


def test_har_forecaster_has_explicit_fit_transform_separation(
    fallback_m1: pd.DataFrame,
    short_rlvs_config: dict[str, object],
) -> None:
    featured = add_rlvs_features(fallback_m1, config=short_rlvs_config)
    train = featured.iloc[:360]
    validation = featured.iloc[360:]
    forecaster = HARVolatilityForecaster(horizon=5, windows=(5, 15, 30))

    with pytest.raises(RuntimeError, match="fitted"):
        forecaster.transform(validation)

    fitted = forecaster.fit(train)
    coefficients = fitted.coefficients_.copy()
    forecast = fitted.transform(validation)
    mutated = validation.copy()
    mutated["rlv_log_variance"] += 10.0
    fitted.transform(mutated)

    assert forecast.notna().any()
    assert forecast.dropna().ge(0.0).all()
    np.testing.assert_array_equal(fitted.coefficients_, coefficients)
    assert fitted.training_rows_ <= len(train) - fitted.horizon


def test_rlvs_rejects_invalid_configuration(fallback_m1: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="sigma_fast_span"):
        add_rlvs_features(
            fallback_m1,
            config={"sigma_fast_span": 30, "sigma_slow_span": 5},
        )
