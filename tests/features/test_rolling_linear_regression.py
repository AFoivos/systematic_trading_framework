from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.features.helpers.registry import TRANSFORM_HELPERS
from src.features.helpers.rolling_linear_regression import (
    add_rolling_linear_regression_transform,
    compute_rolling_linear_regression,
)
from src.features.registry import FEATURE_REGISTRY

from ._helpers import assert_no_mutation


def _price_frame(values: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(values), freq="30min")
    return pd.DataFrame({"close": values.astype(float)}, index=idx)


def _rolling_output(values: np.ndarray, *, window: int = 12) -> pd.DataFrame:
    return add_rolling_linear_regression_transform(
        _price_frame(values),
        source_col="close",
        window=window,
        slope_col="slope",
        intercept_col="intercept",
        r2_col="r2",
    )[["slope", "intercept", "r2"]]


def test_rolling_linear_regression_is_canonical_helper_only() -> None:
    assert TRANSFORM_HELPERS["rolling_linear_regression"] is add_rolling_linear_regression_transform
    assert "rolling_r2_trend_quality" not in FEATURE_REGISTRY
    assert not Path("src/features/rolling_r2_trend_quality.py").exists()


def test_rolling_linear_regression_is_prefix_invariant() -> None:
    rng = np.random.default_rng(7)
    values = 100.0 + np.cumsum(rng.normal(0.05, 0.4, size=160))
    cutoff = 96

    prefix = _rolling_output(values[:cutoff], window=20)
    extended = _rolling_output(values, window=20).iloc[:cutoff]

    assert_frame_equal(prefix, extended, check_exact=False, rtol=1e-7, atol=1e-7)


@pytest.mark.parametrize(
    ("values", "expected_sign"),
    [
        (10.0 + 2.0 * np.arange(80, dtype=float), 1),
        (200.0 - 1.5 * np.arange(80, dtype=float), -1),
    ],
)
def test_linear_series_has_unit_r2_and_expected_slope_sign(
    values: np.ndarray,
    expected_sign: int,
) -> None:
    window = 12
    out = _rolling_output(values, window=window)

    assert out.iloc[: window - 1].isna().all().all()
    assert out["r2"].dropna().eq(1.0).all()
    assert (np.sign(out["slope"].dropna()) == expected_sign).all()


def test_flat_series_preserves_defined_r2_behavior_without_infinities() -> None:
    out = _rolling_output(np.full(40, 5.0), window=8)
    finite_output = out.dropna()

    assert not np.isinf(out.to_numpy(dtype=float)).any()
    assert finite_output["slope"].abs().max() == pytest.approx(0.0)
    assert finite_output["intercept"].eq(5.0).all()
    assert finite_output["r2"].eq(1.0).all()


def test_noisy_series_has_lower_r2_than_clean_linear_series() -> None:
    rng = np.random.default_rng(11)
    clean = _rolling_output(100.0 + 0.5 * np.arange(160, dtype=float), window=20)
    noisy = _rolling_output(100.0 + rng.normal(0.0, 1.0, size=160), window=20)

    assert clean["r2"].dropna().mean() > 0.99
    assert noisy["r2"].dropna().mean() < clean["r2"].dropna().mean()


def test_missing_and_infinite_values_invalidate_only_affected_windows() -> None:
    values = np.arange(20, dtype=float)
    values[6] = np.nan
    values[12] = np.inf
    source = pd.Series(values, index=pd.date_range("2024-01-01", periods=20, freq="h"), name="close")

    slope, intercept, r2 = compute_rolling_linear_regression(source, window=4)

    for output in (slope, intercept, r2):
        assert output.index.equals(source.index)
        assert output.dtype == np.dtype("float32")
        assert output.iloc[:3].isna().all()
        assert output.iloc[6:10].isna().all()
        assert output.iloc[12:16].isna().all()
        assert output.iloc[[3, 4, 5, 10, 11, 16, 17, 18, 19]].notna().all()
        assert not np.isinf(output.to_numpy(dtype=float)).any()


def test_transform_contract_and_supported_yaml_composition() -> None:
    df = _price_frame(10.0 + np.arange(30, dtype=float))

    assert_no_mutation(
        add_rolling_linear_regression_transform,
        df,
        source_col="close",
        window=8,
        r2_col="rolling_r2_8",
    )
    out = apply_feature_steps(
        df,
        [
            {
                "step": "returns",
                "params": {"log": True, "col_name": "close_logret"},
                "transforms": {
                    "rolling_linear_regression": {
                        "source_col": "close",
                        "window": 8,
                        "slope_col": "rolling_r2_slope_8",
                        "intercept_col": "rolling_r2_intercept_8",
                        "r2_col": "rolling_r2_8",
                    },
                    "rising_flag": {
                        "source_col": "rolling_r2_8",
                        "output_col": "rolling_r2_8_rising",
                    },
                    "threshold_flag": {
                        "source_col": "rolling_r2_8",
                        "threshold": 0.99,
                        "op": "ge",
                        "output_col": "rolling_r2_8_ok",
                    },
                },
            }
        ],
    )

    assert {
        "rolling_r2_slope_8",
        "rolling_r2_intercept_8",
        "rolling_r2_8",
        "rolling_r2_8_rising",
        "rolling_r2_8_ok",
    }.issubset(out.columns)


def test_transform_rejects_missing_source_and_invalid_window() -> None:
    df = _price_frame(np.arange(20, dtype=float))
    with pytest.raises(KeyError, match="source_col"):
        add_rolling_linear_regression_transform(df.drop(columns=["close"]), source_col="close")
    with pytest.raises(ValueError, match="window"):
        add_rolling_linear_regression_transform(df, source_col="close", window=1)
