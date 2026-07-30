from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.helpers import apply_feature_helpers
from src.features.helpers.normalizations import add_efficiency_ratio_features
from src.features.systems.lmds import add_lmds_features


def _lmds_ready_frame(periods: int = 140) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=periods, freq="min")
    close = 100.0 + np.cumsum(np.sin(np.arange(periods) / 7.0) + 0.2)
    frame = pd.DataFrame(
        {"open": close, "high": close + 0.1, "low": close - 0.1, "close": close},
        index=index,
    )
    frame["kalman_drift"] = 0.001
    frame["kalman_drift_std"] = 0.01
    frame["ktrend_score"] = 0.2
    frame["rlv_sigma"] = 0.01
    frame["rlv_forecast_5"] = 0.02
    frame["rlv_forecast_15"] = 0.03
    frame["rlv_forecast_30"] = 0.04
    frame["rlv_shock_z"] = 0.0
    frame["rlv_vol_of_vol_ratio"] = 1.0
    return frame


def test_efficiency_ratio_matches_lmds_equivalent_horizons() -> None:
    frame = _lmds_ready_frame()
    helper = add_efficiency_ratio_features(frame, windows=[5, 15, 30])
    lmds = add_lmds_features(frame)

    for window in (5, 15, 30):
        pd.testing.assert_series_equal(
            helper[f"efficiency_ratio_{window}"],
            lmds[f"lmom_efficiency_{window}"],
            check_names=False,
            rtol=1e-10,
            atol=1e-12,
        )


def test_arbitrary_windows_warmup_ranges_and_signed_direction() -> None:
    frame = _lmds_ready_frame(130)
    out = add_efficiency_ratio_features(frame, windows=[24, 48, 96])

    for window in (24, 48, 96):
        ratio = out[f"efficiency_ratio_{window}"]
        signed = out[f"signed_efficiency_ratio_{window}"]
        assert ratio.iloc[:window].isna().all()
        assert ratio.iloc[window:].dropna().between(0.0, 1.0).all()
        assert signed.iloc[window:].dropna().between(-1.0, 1.0).all()
        expected_sign = np.sign(frame["close"] - frame["close"].shift(window))
        np.testing.assert_array_equal(np.sign(signed.dropna()), expected_sign.loc[signed.dropna().index])


def test_zero_path_is_safe_and_custom_source_is_registered() -> None:
    index = pd.date_range("2025-01-01", periods=8, freq="min")
    frame = pd.DataFrame({"price": np.full(8, 10.0)}, index=index)
    out = apply_feature_helpers(
        frame,
        normalizations={
            "efficiency_ratio": {"params": {"source_col": "price", "windows": [3]}}
        },
    )
    assert out["efficiency_ratio_3"].iloc[:3].isna().all()
    assert out["efficiency_ratio_3"].iloc[3:].eq(0.0).all()
    assert out["signed_efficiency_ratio_3"].iloc[3:].eq(0.0).all()


def test_gap_restarts_warmup_and_prefix_is_invariant() -> None:
    frame = _lmds_ready_frame(80)
    shifted = frame.index.to_series()
    shifted.iloc[40:] += pd.Timedelta(minutes=5)
    frame.index = pd.DatetimeIndex(shifted)
    full = add_efficiency_ratio_features(frame, windows=[5])

    assert full["efficiency_ratio_5"].iloc[40:45].isna().all()
    assert np.isfinite(full["efficiency_ratio_5"].iloc[45])
    prefix = add_efficiency_ratio_features(frame.iloc[:60], windows=[5])
    pd.testing.assert_frame_equal(prefix, full.iloc[:60])


@pytest.mark.parametrize("windows", [[], [0], [3, 3]])
def test_invalid_windows_are_rejected(windows: list[int]) -> None:
    with pytest.raises(ValueError):
        add_efficiency_ratio_features(_lmds_ready_frame(), windows=windows)
