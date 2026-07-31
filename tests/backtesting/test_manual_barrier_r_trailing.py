from __future__ import annotations

import numpy as np
import pytest

from src.utils.trade_path import simulate_long_trade_path, simulate_short_trade_path


def _r_trailing(*, activation_r: float = 1.0, distance_r: float = 0.5) -> dict[str, object]:
    return {
        "enabled": True,
        "r_trailing": {
            "enabled": True,
            "activation_r": activation_r,
            "distance_r": distance_r,
            "risk_distance_col": "atr_48",
            "intrabar_policy": "adverse_first",
        },
    }


def test_long_r_trailing_uses_frozen_initial_risk_and_next_bar_stop() -> None:
    path = simulate_long_trade_path(
        opens=np.array([100.0, 101.0, 105.0]),
        highs=np.array([112.0, 111.0, 106.0]),
        lows=np.array([99.0, 105.0, 104.0]),
        closes=np.array([110.0, 106.0, 105.0]),
        signals=None,
        entry_idx=0,
        max_exit_idx=2,
        entry_price=100.0,
        initial_stop_price=90.0,
        take_profit_price=150.0,
        dynamic_exits=_r_trailing(),
        initial_risk_distance=10.0,
    )

    assert path["exit_idx"] == 1
    assert path["exit_reason"] == "r_trailing_stop"
    assert path["raw_exit_price"] == pytest.approx(107.0)
    assert path["initial_risk_distance"] == pytest.approx(10.0)
    assert path["effective_trailing_stop"] == pytest.approx(107.0)
    assert path["r_trailing_activated"] is True
    assert path["intrabar_policy"] == "adverse_first"


def test_short_r_trailing_is_symmetric_and_next_bar_only() -> None:
    path = simulate_short_trade_path(
        opens=np.array([100.0, 92.0, 95.0]),
        highs=np.array([101.0, 95.0, 96.0]),
        lows=np.array([88.0, 89.0, 94.0]),
        closes=np.array([90.0, 94.0, 95.0]),
        signals=None,
        entry_idx=0,
        max_exit_idx=2,
        entry_price=100.0,
        initial_stop_price=110.0,
        take_profit_price=50.0,
        dynamic_exits=_r_trailing(),
        initial_risk_distance=10.0,
    )

    assert path["exit_idx"] == 1
    assert path["exit_reason"] == "r_trailing_stop"
    assert path["raw_exit_price"] == pytest.approx(93.0)
    assert path["initial_risk_distance"] == pytest.approx(10.0)
    assert path["effective_trailing_stop"] == pytest.approx(93.0)
    assert path["r_trailing_activated"] is True


@pytest.mark.parametrize("risk_distance", [None, 0.0, -1.0, np.nan, np.inf])
def test_r_trailing_rejects_invalid_initial_risk_distance(risk_distance: float | None) -> None:
    with pytest.raises(ValueError, match="initial risk distance"):
        simulate_long_trade_path(
            opens=np.array([100.0]),
            highs=np.array([101.0]),
            lows=np.array([99.0]),
            closes=np.array([100.0]),
            signals=None,
            entry_idx=0,
            max_exit_idx=0,
            entry_price=100.0,
            initial_stop_price=90.0,
            take_profit_price=120.0,
            dynamic_exits=_r_trailing(),
            initial_risk_distance=risk_distance,
        )
