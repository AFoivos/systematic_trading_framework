from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_series_equal

from src.features.scalp_microstructure_proxy import add_scalp_microstructure_proxy

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation


def _quote_frame(n: int = 12) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")
    t = np.arange(n, dtype=float)
    open_ = 100.0 + t
    close = open_ + np.where(t % 2 == 0, 0.4, -0.3)
    high = np.maximum(open_, close) + 0.6
    low = np.minimum(open_, close) - 0.5
    volume = 1_000.0 + 10.0 * t
    spread = 0.02 + 0.001 * t
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "bid_open": open_ - spread / 2.0,
            "bid_high": high - spread / 2.0,
            "bid_low": low - spread / 2.0,
            "bid_close": close - spread / 2.0,
            "ask_open": open_ + spread / 2.0,
            "ask_high": high + spread / 2.0,
            "ask_low": low + spread / 2.0,
            "ask_close": close + spread / 2.0,
            "spread_close": spread,
            "spread_bps": spread / close * 10_000.0,
        },
        index=idx,
    )


def test_scalp_microstructure_proxy_outputs_and_mid_columns() -> None:
    df = _quote_frame()
    out = add_scalp_microstructure_proxy(df)

    expected = {
        "mid_open",
        "mid_high",
        "mid_low",
        "mid_close",
        "bid_ask_spread_abs",
        "bid_ask_spread_bps",
        "spread_bps_change",
        "bar_range",
        "bar_body",
        "close_pos_in_bar",
        "body_to_range",
        "upper_wick",
        "lower_wick",
        "candle_pressure",
        "signed_volume_proxy",
        "buy_volume_proxy",
        "sell_volume_proxy",
        "ofi_proxy_norm_1",
    }
    assert expected.issubset(out.columns)
    assert_series_equal(out["mid_open"], (df["bid_open"] + df["ask_open"]) / 2.0, check_names=False)
    assert_series_equal(out["mid_close"], (df["bid_close"] + df["ask_close"]) / 2.0, check_names=False)
    assert_has_finite_values(out["ofi_proxy_norm_1"])
    assert_no_mutation(add_scalp_microstructure_proxy, df)


def test_scalp_microstructure_proxy_clips_pressure_and_preserves_volume_split() -> None:
    df = _quote_frame()
    df.loc[df.index[0], "close"] = df.loc[df.index[0], "high"] + 10.0
    df.loc[df.index[1], "close"] = df.loc[df.index[1], "low"] - 10.0
    out = add_scalp_microstructure_proxy(df)

    assert out["close_pos_in_bar"].between(0.0, 1.0).all()
    assert out["candle_pressure"].between(-1.0, 1.0).all()
    np.testing.assert_allclose(
        out["buy_volume_proxy"] + out["sell_volume_proxy"],
        df["volume"],
        rtol=1e-12,
        atol=1e-12,
    )


def test_scalp_microstructure_proxy_missing_columns_raise_clear_key_error() -> None:
    with pytest.raises(KeyError, match="scalp_microstructure_proxy"):
        add_scalp_microstructure_proxy(_quote_frame().drop(columns=["bid_close"]))


def test_scalp_microstructure_proxy_zero_range_and_zero_volume_are_safe() -> None:
    df = _quote_frame()
    df.loc[df.index[0], ["high", "low", "open", "close"]] = 100.0
    df.loc[df.index[0], "volume"] = 0.0

    out = add_scalp_microstructure_proxy(df)

    assert np.isfinite(out.loc[df.index[0], "close_pos_in_bar"])
    assert np.isfinite(out.loc[df.index[0], "body_to_range"])
    assert out.loc[df.index[0], "ofi_proxy_norm_1"] == 0.0


def test_scalp_microstructure_proxy_invalid_params() -> None:
    with pytest.raises(ValueError, match="eps"):
        add_scalp_microstructure_proxy(_quote_frame(), eps=0.0)
    with pytest.raises(ValueError, match="output columns"):
        add_scalp_microstructure_proxy(_quote_frame(), mid_open_col="")


def test_scalp_microstructure_proxy_is_causal() -> None:
    assert_causal(
        add_scalp_microstructure_proxy,
        _quote_frame(n=180),
        output_cols=[
            "mid_close",
            "bid_ask_spread_bps",
            "spread_bps_change",
            "candle_pressure",
            "signed_volume_proxy",
            "ofi_proxy_norm_1",
        ],
        mutate_cols=[
            "open",
            "high",
            "low",
            "close",
            "volume",
            "bid_open",
            "bid_high",
            "bid_low",
            "bid_close",
            "ask_open",
            "ask_high",
            "ask_low",
            "ask_close",
        ],
    )
