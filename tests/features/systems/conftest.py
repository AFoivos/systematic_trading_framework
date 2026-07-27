from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def fallback_m1() -> pd.DataFrame:
    return make_fallback_m1(480)


@pytest.fixture
def quoted_m1() -> pd.DataFrame:
    fallback = make_fallback_m1(480)
    half_spread = fallback["close"] * 0.8e-4 / 2.0
    quoted = pd.DataFrame(index=fallback.index)
    for field in ("open", "high", "low", "close"):
        quoted[f"bid_{field}"] = fallback[field] - half_spread
        quoted[f"ask_{field}"] = fallback[field] + half_spread
    quoted["spread_bps"] = 0.8
    quoted["tick_volume"] = 100.0 + np.arange(len(quoted), dtype=float)
    return quoted


def make_fallback_m1(
    periods: int,
    *,
    drift: float = 1.5e-5,
    acceleration: float = 0.0,
    noise_scale: float = 2.0e-5,
) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=periods, freq="min", tz="UTC")
    position = np.arange(periods, dtype=float)
    log_close = (
        np.log(1.10)
        + drift * position
        + acceleration * position**2
        + noise_scale * np.sin(position / 7.0)
    )
    close = np.exp(log_close)
    open_ = np.r_[close[0], close[:-1]]
    range_size = close * (2.0e-5 + 0.5e-5 * (1.0 + np.sin(position / 11.0)))
    high = np.maximum(open_, close) + range_size
    low = np.minimum(open_, close) - range_size
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "spread_bps": 0.8 + 0.05 * np.cos(position / 13.0),
            "tick_volume": 100.0 + position,
        },
        index=index,
    )


@pytest.fixture
def short_kds_config() -> dict[str, object]:
    return {
        "local_volatility_span": 8,
        "local_volatility_min_periods": 2,
        "volatility_baseline_window": 24,
        "spread_baseline_window": 24,
        "kadx_window": 5,
    }


@pytest.fixture
def short_rlvs_config() -> dict[str, object]:
    return {
        "measurement_span": 5,
        "measurement_min_periods": 2,
        "state_baseline_span": 24,
        "spread_baseline_window": 24,
        "range_baseline_window": 24,
        "regime_baseline_span": 36,
        "regime_min_periods": 12,
        "vol_of_vol_span": 8,
        "vol_of_vol_baseline_span": 24,
        "sigma_fast_span": 5,
        "sigma_slow_span": 30,
    }
