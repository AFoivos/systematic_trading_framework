from __future__ import annotations

import pandas as pd

from src.features.support_resistance_v2 import _breakout_retest_events


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.RangeIndex(len(values)), dtype=float)


def test_breakout_bar_is_not_also_a_retest_and_later_touch_is_one_shot() -> None:
    breakout_up, _, retest, _ = _breakout_retest_events(
        close=_series([100.0, 102.0, 101.0, 101.0]),
        high=_series([100.0, 103.0, 102.0, 103.0]),
        low=_series([100.0, 100.5, 99.8, 100.0]),
        resistance_level=_series([100.0] * 4),
        support_level=_series([90.0] * 4),
        breakout_tol=_series([1.0] * 4),
        touch_tol=_series([0.25] * 4),
        expiry_bars=3,
    )

    assert breakout_up.tolist() == [0.0, 1.0, 0.0, 0.0]
    assert retest.tolist() == [0.0, 0.0, 1.0, 0.0]


def test_breakout_retest_state_expires_and_invalidates() -> None:
    _, _, expired_retest, _ = _breakout_retest_events(
        close=_series([100.0, 102.0, 102.0, 101.0]),
        high=_series([100.0, 103.0, 103.0, 102.0]),
        low=_series([100.0, 101.5, 101.5, 99.9]),
        resistance_level=_series([100.0] * 4),
        support_level=_series([90.0] * 4),
        breakout_tol=_series([1.0] * 4),
        touch_tol=_series([0.25] * 4),
        expiry_bars=1,
    )
    _, _, invalidated_retest, _ = _breakout_retest_events(
        close=_series([100.0, 102.0, 99.0, 100.5]),
        high=_series([100.0, 103.0, 100.0, 101.0]),
        low=_series([100.0, 101.5, 98.0, 99.9]),
        resistance_level=_series([100.0] * 4),
        support_level=_series([90.0] * 4),
        breakout_tol=_series([1.0] * 4),
        touch_tol=_series([0.25] * 4),
        expiry_bars=3,
    )

    assert expired_retest.sum() == 0.0
    assert invalidated_retest.sum() == 0.0
