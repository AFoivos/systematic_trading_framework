from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.features.rolling_r2_trend_quality import add_rolling_r2_trend_quality

from ._helpers import assert_no_mutation


def _price_frame(values: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(values), freq="30min")
    return pd.DataFrame({"close": values.astype(float)}, index=idx)


def test_rolling_r2_trend_quality_contract_and_numeric_sanity() -> None:
    window = 12
    t = np.arange(80, dtype=float)
    df = _price_frame(10.0 + 2.0 * t)

    out = add_rolling_r2_trend_quality(
        df,
        window=window,
        output_col="r2",
        slope_col="slope",
        intercept_col="intercept",
        rising_col="r2_rising",
        trend_quality_col="r2_ok",
        trend_quality_threshold=0.99,
    )

    assert {"r2", "slope", "intercept", "r2_rising", "r2_ok"}.issubset(out.columns)
    assert_no_mutation(
        add_rolling_r2_trend_quality,
        df,
        window=window,
        output_col="r2",
        slope_col="slope",
        intercept_col="intercept",
        rising_col="r2_rising",
        trend_quality_col="r2_ok",
    )
    assert out["r2_rising"].dtype == np.dtype("int8")
    assert out["r2_ok"].dtype == np.dtype("int8")
    assert out["r2"].iloc[: window - 1].isna().all()
    assert out["slope"].iloc[: window - 1].isna().all()
    assert out["intercept"].iloc[: window - 1].isna().all()
    assert out["r2"].dropna().min() == pytest.approx(1.0)
    assert out["slope"].dropna().iloc[-1] == pytest.approx(2.0)
    assert out["intercept"].dropna().iloc[-1] == pytest.approx(df["close"].iloc[-window])
    assert out["r2_ok"].iloc[window - 1 :].eq(1).all()


def test_rolling_r2_trend_quality_noisy_series_has_lower_r2() -> None:
    rng = np.random.default_rng(7)
    window = 20
    clean = add_rolling_r2_trend_quality(
        _price_frame(100.0 + 0.5 * np.arange(160, dtype=float)),
        window=window,
        output_col="r2",
    )
    noisy = add_rolling_r2_trend_quality(
        _price_frame(100.0 + rng.normal(0.0, 1.0, size=160)),
        window=window,
        output_col="r2",
    )

    assert clean["r2"].dropna().mean() > 0.99
    assert noisy["r2"].dropna().mean() < clean["r2"].dropna().mean()


def test_rolling_r2_trend_quality_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_rolling_r2_trend_quality(_price_frame(np.arange(20, dtype=float)).drop(columns=["close"]))


def test_rolling_r2_trend_quality_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_rolling_r2_trend_quality(_price_frame(np.arange(20, dtype=float)), window=4)


def test_rolling_r2_trend_quality_yaml_registry_supports_step() -> None:
    out = apply_feature_steps(
        _price_frame(10.0 + np.arange(30, dtype=float)),
        [
            {
                "step": "rolling_r2_trend_quality",
                "params": {"window": 8, "output_col": "rolling_r2_8"},
            }
        ],
    )

    assert "rolling_r2_8" in out.columns
