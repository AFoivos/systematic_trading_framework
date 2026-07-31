from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.barrier_state import (
    add_barrier_equilibrium_features,
    add_barrier_market_organization_features,
    add_barrier_microstructure_features,
    add_barrier_path_features,
    add_barrier_persistence_features,
    add_barrier_session_features,
    add_barrier_volatility_features,
)


def _market_frame(rows: int = 360) -> pd.DataFrame:
    rng = np.random.default_rng(17)
    index = pd.date_range("2024-01-01", periods=rows, freq="30min")
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.08, rows))
    open_ = np.r_[close[0], close[:-1]] + rng.normal(0.0, 0.01, rows)
    high = np.maximum(open_, close) + rng.uniform(0.02, 0.12, rows)
    low = np.minimum(open_, close) - rng.uniform(0.02, 0.12, rows)
    returns = pd.Series(close, index=index).pct_change()
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(50, 200, rows).astype(float),
            "spread_bps": rng.uniform(0.00005, 0.00030, rows),
            "atr_14": np.full(rows, 0.25),
            "kalman_level": np.log(pd.Series(close, index=index).ewm(span=10, adjust=False).mean()),
            "vwap_48": pd.Series(close, index=index).rolling(48, min_periods=48).mean(),
            "shannon_entropy_48": returns.abs().rolling(48, min_periods=48).mean(),
            "permutation_entropy_48": returns.rolling(48, min_periods=48).std(),
        },
        index=index,
    )


def _all_non_microstructure_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = add_barrier_equilibrium_features(frame, window=48, zscore_window=48)
    out = add_barrier_path_features(out, window=24)
    out = add_barrier_persistence_features(
        out,
        residual_col="deviation_kalman_atr",
        window=48,
        autocorrelation_lags=(1, 4),
    )
    out = add_barrier_volatility_features(
        out,
        short_window=12,
        long_window=48,
        percentile_window=96,
    )
    out = add_barrier_market_organization_features(
        out,
        window=48,
        percentile_window=96,
    )
    return add_barrier_session_features(out, percentile_window=96)


def test_barrier_feature_families_are_prefix_invariant() -> None:
    baseline_input = _market_frame()
    changed_input = baseline_input.copy()
    cutoff = 260
    changed_input.iloc[cutoff + 1 :, changed_input.columns.get_indexer(["open", "high", "low", "close", "volume"])] *= 5.0

    baseline = _all_non_microstructure_features(baseline_input)
    changed = _all_non_microstructure_features(changed_input)
    added = [column for column in baseline.columns if column not in baseline_input.columns]

    pd.testing.assert_frame_equal(
        baseline.iloc[: cutoff + 1][added],
        changed.iloc[: cutoff + 1][added],
        check_dtype=False,
        check_exact=False,
        rtol=1e-7,
        atol=1e-9,
    )


def test_microstructure_features_are_explicit_proxies() -> None:
    baseline_input = _market_frame()
    changed_input = baseline_input.copy()
    cutoff = 260
    changed_input.iloc[cutoff + 1 :, changed_input.columns.get_indexer(["open", "high", "low", "close", "volume"])] *= 5.0

    out = add_barrier_microstructure_features(
        baseline_input,
        window=24,
        baseline_window=96,
        volume_is_tick_activity=True,
    )
    changed = add_barrier_microstructure_features(
        changed_input,
        window=24,
        baseline_window=96,
        volume_is_tick_activity=True,
    )
    added = [column for column in out.columns if column not in baseline_input.columns]

    assert "tick_flow_proxy_24" in out
    assert "bullish_absorption_proxy" in out
    assert "bearish_absorption_proxy" in out
    assert not any(column == "ofi" for column in out.columns)
    pd.testing.assert_frame_equal(
        out.iloc[: cutoff + 1][added],
        changed.iloc[: cutoff + 1][added],
        check_dtype=False,
        check_exact=False,
        rtol=1e-7,
        atol=1e-9,
    )
