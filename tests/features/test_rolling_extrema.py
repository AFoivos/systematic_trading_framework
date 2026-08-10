from __future__ import annotations

import pandas as pd

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.experiments.registry import FEATURE_REGISTRY
from src.features.rolling_extrema import add_extrema_feature


def _close_frame() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "close": [10.0, 11.0, 12.0, 11.0, 9.0, 8.0, 9.0, 13.0, 13.0, 7.0],
            "high": [10.2, 11.2, 12.2, 11.2, 9.2, 8.2, 9.2, 13.2, 13.2, 7.2],
            "low": [9.8, 10.8, 11.8, 10.8, 8.8, 7.8, 8.8, 12.8, 12.8, 6.8],
        },
        index=index,
    )


def test_extrema_close_marks_new_trailing_maximum_and_minimum() -> None:
    df = _close_frame()
    out = add_extrema_feature(df, window=3, price_col="close", output_col="extrema", strict=True)
    assert out["extrema"].tolist() == [0, 0, 0, 0, -1, -1, 0, 1, 0, -1]
    assert str(out["extrema"].dtype) == "int8"


def test_extrema_non_strict_counts_equal_rolling_maximum() -> None:
    df = _close_frame()
    out = add_extrema_feature(df, window=3, price_col="close", strict=False)
    assert out.iloc[8]["extrema"] == 1


def test_extrema_is_prefix_invariant() -> None:
    df = _close_frame()
    prefix = add_extrema_feature(df.iloc[:8], window=3, price_col="close")
    extended = add_extrema_feature(df, window=3, price_col="close").iloc[:8]
    pd.testing.assert_series_equal(prefix["extrema"], extended["extrema"])


def test_extrema_can_use_high_and_low_columns() -> None:
    df = _close_frame()
    out = add_extrema_feature(df, window=3, high_col="high", low_col="low", price_col=None)
    assert set(out["extrema"].unique()).issubset({-1, 0, 1})
    assert out.iloc[7]["extrema"] == 1
    assert out.iloc[9]["extrema"] == -1


def test_extrema_is_registered() -> None:
    assert FEATURE_REGISTRY["extrema"] is add_extrema_feature


def test_apply_feature_steps_adds_extrema_column() -> None:
    df = _close_frame()
    out = apply_feature_steps(
        df,
        [{
            "step": "extrema",
            "params": {"window": 3, "price_col": "close", "output_col": "my_extrema", "strict": True},
        }],
    )
    assert "my_extrema" in out.columns
    assert out.iloc[7]["my_extrema"] == 1
    assert out.iloc[9]["my_extrema"] == -1
