from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.shock_context import add_shock_context_features


def _frame(index: pd.DatetimeIndex) -> pd.DataFrame:
    returns = pd.Series(0.01, index=index, dtype=float)
    close = 100.0 * (1.0 + returns).cumprod()
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "simple_ret": returns,
            "ema": close,
            "atr": 1.0,
        },
        index=index,
    )


def test_shock_hour_horizons_convert_to_bar_count_on_30_minute_data() -> None:
    frame = _frame(pd.date_range("2024-01-01", periods=20, freq="30min"))

    out = add_shock_context_features(
        frame,
        returns_col="simple_ret",
        ema_col="ema",
        atr_col="atr",
        short_horizon=2,
        medium_horizon=8,
        vol_window=2,
        use_log_returns=False,
    )

    assert out["shock_ret_2h"].iloc[3] == pytest.approx((1.01**4) - 1.0)
    assert np.isnan(out["shock_ret_8h"].iloc[14])
    assert out["shock_ret_8h"].iloc[15] == pytest.approx((1.01**16) - 1.0)


def test_shock_hour_horizons_reject_irregular_or_missing_bar_cadence() -> None:
    index = pd.DatetimeIndex(
        [
            "2024-01-01 00:00:00",
            "2024-01-01 00:30:00",
            "2024-01-01 01:30:00",
        ]
    )

    with pytest.raises(ValueError, match="regular cadence"):
        add_shock_context_features(
            _frame(index),
            returns_col="simple_ret",
            ema_col="ema",
            atr_col="atr",
            short_horizon=1,
            medium_horizon=2,
            vol_window=2,
            use_log_returns=False,
        )
