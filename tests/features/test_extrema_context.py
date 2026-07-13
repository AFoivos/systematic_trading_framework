from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.features.extrema_context import swing_extrema_context


def _swing_frame() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=12, freq="h", tz="UTC")
    close = pd.Series(
        [1.0, 2.0, 3.0, 6.0, 4.0, 3.0, 4.0, 5.0, 4.0, 2.0, 3.0, 4.0],
        index=index,
    )
    return pd.DataFrame(
        {
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "atr_proxy": np.ones(len(close)),
        },
        index=index,
    )


def _live_context(df: pd.DataFrame) -> pd.DataFrame:
    return swing_extrema_context(
        df,
        normalizer_col="atr_proxy",
        left_bars=1,
        right_bars=3,
        prefix="swing",
    )


def test_live_swing_context_emits_only_confirmed_and_causal_columns() -> None:
    out = _live_context(_swing_frame())

    assert not any("raw_local_" in column for column in out.columns)
    assert not any("pre_local_" in column for column in out.columns)
    assert {
        "swing_confirmed_local_high",
        "swing_confirmed_local_low",
        "swing_confirmed_local_high_price",
        "swing_confirmed_local_low_price",
        "swing_last_high",
        "swing_last_low",
        "swing_structure_score",
    }.issubset(out.columns)


def test_live_swing_confirmation_occurs_after_right_bars() -> None:
    out = _live_context(_swing_frame())
    pivot = pd.Timestamp("2024-01-01 03:00:00", tz="UTC")
    confirmation = pd.Timestamp("2024-01-01 06:00:00", tz="UTC")

    assert out.loc[pivot, "swing_confirmed_local_high"] == 0
    assert out.loc[confirmation, "swing_confirmed_local_high"] == 1
    assert out.loc[confirmation, "swing_confirmed_local_high_price"] == pytest.approx(6.2)


def test_live_swing_context_is_prefix_invariant() -> None:
    frame = _swing_frame()
    cutoff = 9

    prefix = _live_context(frame.iloc[:cutoff]).filter(regex="^swing_")
    extended = _live_context(frame).iloc[:cutoff].filter(regex="^swing_")

    assert_frame_equal(prefix, extended, check_exact=False, rtol=1e-7, atol=1e-7)


def test_live_swing_context_blocks_research_labels() -> None:
    with pytest.raises(ValueError, match="future/research-only.*model features"):
        swing_extrema_context(
            _swing_frame(),
            normalizer_col="atr_proxy",
            left_bars=1,
            right_bars=1,
            include_research_labels=True,
            research_label_lead_bars=2,
        )
