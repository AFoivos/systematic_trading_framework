from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.features.trend_slope_volatility import add_trend_slope_volatility

from ._helpers import assert_no_mutation


def _trend_frame(n: int = 80, *, volatility: float = 2.0) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    t = np.arange(n, dtype=float)
    return pd.DataFrame(
        {
            "close": 100.0 + 0.5 * t,
            "vol": volatility,
        },
        index=idx,
    )


def test_trend_slope_volatility_contract_and_numeric_sanity() -> None:
    window = 8
    df = _trend_frame()

    out = add_trend_slope_volatility(
        df,
        volatility_col="vol",
        window=window,
        slope_col="slope",
        volatility_used_col="vol_used",
        slope_vol_ratio_col="ratio",
        positive_col="ratio_positive",
        rising_col="ratio_rising",
        strong_trend_col="ratio_strong",
        strong_threshold=0.001,
    )

    assert {"slope", "vol_used", "ratio", "ratio_positive", "ratio_rising", "ratio_strong"}.issubset(
        out.columns
    )
    assert_no_mutation(
        add_trend_slope_volatility,
        df,
        volatility_col="vol",
        window=window,
        slope_col="slope",
        volatility_used_col="vol_used",
        slope_vol_ratio_col="ratio",
        positive_col="ratio_positive",
        rising_col="ratio_rising",
        strong_trend_col="ratio_strong",
        strong_threshold=0.001,
    )
    assert out["ratio_positive"].dtype == np.dtype("int8")
    assert out["ratio_rising"].dtype == np.dtype("int8")
    assert out["ratio_strong"].dtype == np.dtype("int8")
    assert out["slope"].iloc[: window - 1].isna().all()
    assert out["ratio"].iloc[: window - 1].isna().all()
    assert out["slope"].dropna().iloc[-1] == pytest.approx(0.5)
    assert out["ratio"].dropna().iloc[-1] == pytest.approx(0.5 / df["close"].iloc[-1] / 2.0)
    assert out["ratio"].dropna().gt(0.0).all()
    assert out["ratio_positive"].iloc[window - 1 :].eq(1).all()
    assert out["ratio_strong"].iloc[window - 1 :].eq(1).all()


def test_trend_slope_volatility_ratio_is_invariant_to_price_quote_scale() -> None:
    df = _trend_frame()
    scaled = df.copy()
    scaled["close"] *= 100.0

    base_out = add_trend_slope_volatility(
        df,
        volatility_col="vol",
        window=8,
        slope_vol_ratio_col="ratio",
    )
    scaled_out = add_trend_slope_volatility(
        scaled,
        volatility_col="vol",
        window=8,
        slope_vol_ratio_col="ratio",
    )

    pd.testing.assert_series_equal(base_out["ratio"], scaled_out["ratio"])


def test_trend_slope_volatility_zero_volatility_returns_nan_ratio() -> None:
    df = _trend_frame(volatility=0.0)

    out = add_trend_slope_volatility(df, volatility_col="vol", window=8, slope_vol_ratio_col="ratio")

    assert out["ratio"].isna().all()


def test_trend_slope_volatility_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_trend_slope_volatility(_trend_frame().drop(columns=["close"]), volatility_col="vol", window=8)
    with pytest.raises(KeyError, match="Missing columns"):
        add_trend_slope_volatility(_trend_frame().drop(columns=["vol"]), volatility_col="vol", window=8)


def test_trend_slope_volatility_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_trend_slope_volatility(_trend_frame(), volatility_col="vol", window=4)


def test_trend_slope_volatility_annualize_requires_periods_per_year() -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        add_trend_slope_volatility(_trend_frame(), volatility_col="vol", window=8, annualize=True)


def test_trend_slope_volatility_yaml_registry_supports_step() -> None:
    out = apply_feature_steps(
        _trend_frame(n=30),
        [
            {
                "step": "trend_slope_volatility",
                "params": {"volatility_col": "vol", "window": 8, "slope_vol_ratio_col": "ratio"},
            }
        ],
    )

    assert "ratio" in out.columns
