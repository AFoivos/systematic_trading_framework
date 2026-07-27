from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analyze_ftmo_relative_value_spread import analyze_spread


def test_analyze_spread_produces_lagged_rolling_series() -> None:
    rng = np.random.default_rng(7)
    rows = 1_800
    timestamps = pd.date_range("2025-01-01T00:00:00Z", periods=rows, freq="h")
    eth = 8.0 + np.cumsum(rng.normal(0.0, 0.004, rows))
    stationary_noise = np.zeros(rows)
    for index in range(1, rows):
        stationary_noise[index] = 0.85 * stationary_noise[index - 1] + rng.normal(0.0, 0.002)
    btc = 3.0 + 0.7 * eth + stationary_noise
    frame = pd.DataFrame(
        {"btc_log_close": btc, "eth_log_close": eth},
        index=timestamps,
    )

    diagnostics, series = analyze_spread(frame, formation_hours=240, zscore_hours=48)

    assert diagnostics["rows"] == rows
    assert diagnostics["verdict"]["price_level_cointegration_supported_full_sample_5pct"] is True
    assert diagnostics["rolling"]["valid_zscore_rows"] > 1_000
    assert series["rolling_beta_lagged"].first_valid_index() > timestamps[0]

