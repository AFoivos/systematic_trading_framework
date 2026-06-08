from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal


def synthetic_ohlcv(n: int = 180) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    t = np.arange(n, dtype=float)
    close = 100.0 + 0.04 * t + 1.8 * np.sin(t / 8.0) + 0.3 * np.cos(t / 3.0)
    open_ = close + 0.15 * np.sin(t / 5.0)
    high = np.maximum(open_, close) + 0.6 + 0.04 * np.sin(t / 7.0)
    low = np.minimum(open_, close) - 0.6 - 0.04 * np.cos(t / 6.0)
    volume = 1_000.0 + 120.0 * np.sin(t / 9.0) + 0.5 * t
    buy_fraction = 0.52 + 0.08 * np.sin(t / 11.0)
    buy_volume = volume * buy_fraction
    sell_volume = volume - buy_volume
    bid_size = 450.0 + 30.0 * np.sin(t / 6.0)
    ask_size = 470.0 + 25.0 * np.cos(t / 7.0)

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "signed_volume": buy_volume - sell_volume,
            "ppo_hist": 0.01 * np.sin(t / 6.0) + 0.003 * np.cos(t / 13.0),
            "adx_14": 24.0 + 7.0 * np.sin(t / 14.0),
            "returns": pd.Series(close, index=idx).pct_change().fillna(0.0).to_numpy(),
            "vol": pd.Series(close, index=idx).pct_change().rolling(10, min_periods=10).std(ddof=0).to_numpy(),
            "bid_price": close - 0.01,
            "ask_price": close + 0.01,
            "bid_size": bid_size,
            "ask_size": ask_size,
        },
        index=idx,
    )


def assert_no_mutation(fn: Callable[..., pd.DataFrame], df: pd.DataFrame, **params: object) -> None:
    before = df.copy(deep=True)
    fn(df, **params)
    assert_frame_equal(df, before)


def assert_causal(
    fn: Callable[..., pd.DataFrame],
    df: pd.DataFrame,
    *,
    output_cols: Sequence[str],
    params: dict[str, object] | None = None,
    cutoff: int = 100,
    mutate_cols: Sequence[str] | None = None,
) -> None:
    resolved_params = dict(params or {})
    baseline = fn(df, **resolved_params)
    changed = df.copy(deep=True)
    columns = list(mutate_cols or changed.select_dtypes(include=[np.number]).columns)
    future_index = changed.index[cutoff + 1 :]
    for column in columns:
        changed.loc[future_index, column] = changed.loc[future_index, column] * 1.7 + 123.0

    changed_out = fn(changed, **resolved_params)
    for column in output_cols:
        assert_series_equal(
            baseline[column].iloc[: cutoff + 1],
            changed_out[column].iloc[: cutoff + 1],
            check_names=False,
        )


def assert_has_finite_values(series: pd.Series) -> None:
    values = series.dropna().to_numpy(dtype=float)
    assert values.size > 0
    assert np.isfinite(values).all()
