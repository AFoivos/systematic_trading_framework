from __future__ import annotations

import pandas as pd
import pytest

from src.signals.barrier_expected_value_signal import barrier_expected_value_signal


def _probability_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pred_prob_upper": [0.70, 0.10, 0.45],
            "pred_prob_lower": [0.10, 0.70, 0.45],
            "pred_prob_no_hit": [0.20, 0.20, 0.10],
            "pred_probability_calibrated": [True, True, False],
            "pred_is_oos": [True, True, True],
            "atr_14": [1.0, 1.0, 1.0],
            "close": [100.0, 100.0, 100.0],
            "spread_bps": [0.0001, 0.0001, 0.0001],
        }
    )


def test_expected_value_policy_selects_long_short_and_rejects_uncalibrated() -> None:
    out = barrier_expected_value_signal(
        _probability_frame(),
        minimum_expected_edge=0.001,
        minimum_class_probability=0.60,
        cost_per_turnover=0.0001,
        slippage_per_turnover=0.0001,
        cost_safety_factor=1.25,
        maximum_spread=0.001,
    )

    assert out["barrier_ev_signal"].tolist() == pytest.approx([1.0, -1.0, 0.0])
    assert out.loc[0, "barrier_ev_long"] == pytest.approx(0.0056)
    assert out.loc[1, "barrier_ev_short"] == pytest.approx(0.0056)
    assert out["barrier_round_trip_cost"].eq(0.0004).all()


def test_costs_and_entry_delay_can_suppress_or_delay_signal() -> None:
    expensive = barrier_expected_value_signal(
        _probability_frame(),
        minimum_expected_edge=0.001,
        minimum_class_probability=0.60,
        cost_per_turnover=0.004,
        slippage_per_turnover=0.0,
    )
    assert expensive["barrier_ev_signal"].eq(0.0).all()

    delayed = barrier_expected_value_signal(
        _probability_frame(),
        minimum_class_probability=0.60,
        entry_delay_bars=2,
    )
    assert delayed["barrier_ev_signal"].tolist() == pytest.approx([0.0, 1.0, -1.0])


def test_probability_rows_must_sum_to_one() -> None:
    frame = _probability_frame()
    frame.loc[0, "pred_prob_no_hit"] = 0.5
    out = barrier_expected_value_signal(frame, minimum_class_probability=0.1)

    assert out.loc[0, "barrier_ev_signal"] == 0.0
