from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt

from src.signals.btcusd_dual_trend_ftmo_signal import btcusd_dual_trend_ensemble_signal


def _frame(scores: list[float], volatility: list[float] | None = None) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=len(scores), freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "dual_trend_score": scores,
            "dual_volatility_ann_336": volatility or [0.22] * len(scores),
        },
        index=index,
    )


def test_direction_change_rebalances_immediately() -> None:
    result = btcusd_dual_trend_ensemble_signal(_frame([1.0, 1.0, -1.0, -1.0]))
    assert result["signal_position"].tolist() == [1.0, 1.0, -1.0, -1.0]
    assert result["position_rebalanced"].tolist() == [True, False, True, False]


def test_scheduled_rebalance_occurs_after_48_exposed_bars() -> None:
    volatility = [0.22] + [0.44] * 48 + [0.88]
    result = btcusd_dual_trend_ensemble_signal(_frame([1.0] * 50, volatility))
    assert result["signal_position"].iloc[:48].eq(1.0).all()
    assert result["signal_position"].iloc[48] == 0.5
    assert result["position_rebalanced"].iloc[48]


def test_no_intermediate_volatility_rescaling() -> None:
    volatility = np.linspace(0.22, 0.88, 48).tolist()
    result = btcusd_dual_trend_ensemble_signal(_frame([1.0] * 48, volatility))
    expected = pd.Series(1.0, index=result.index, name="signal_position")
    pdt.assert_series_equal(result["signal_position"], expected)

