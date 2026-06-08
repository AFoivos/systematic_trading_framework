from __future__ import annotations

import pytest

from src.features.order_flow_imbalance import add_order_flow_imbalance

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_order_flow_imbalance_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_order_flow_imbalance(df, window=5, output_col="ofi")

    assert "ofi" in out.columns
    assert_no_mutation(add_order_flow_imbalance, df, window=5, output_col="ofi")
    assert_has_finite_values(out["ofi"])


def test_order_flow_imbalance_missing_real_flow_columns() -> None:
    df = synthetic_ohlcv().drop(columns=["buy_volume", "sell_volume"])
    with pytest.raises(KeyError, match="order flow imbalance"):
        add_order_flow_imbalance(df, buy_volume_col="buy_volume", sell_volume_col="sell_volume")


def test_order_flow_imbalance_invalid_params() -> None:
    with pytest.raises(ValueError, match="window"):
        add_order_flow_imbalance(synthetic_ohlcv(), window=0)


def test_order_flow_imbalance_is_causal() -> None:
    assert_causal(
        add_order_flow_imbalance,
        synthetic_ohlcv(),
        output_cols=["order_flow_imbalance_5"],
        params={"window": 5},
        mutate_cols=["buy_volume", "sell_volume"],
    )


def test_order_flow_imbalance_supports_quote_data() -> None:
    df = synthetic_ohlcv().drop(columns=["buy_volume", "sell_volume"])
    out = add_order_flow_imbalance(
        df,
        buy_volume_col=None,
        sell_volume_col=None,
        bid_price_col="bid_price",
        ask_price_col="ask_price",
        bid_size_col="bid_size",
        ask_size_col="ask_size",
        window=3,
    )

    assert "order_flow_imbalance_3" in out.columns
    assert_has_finite_values(out["order_flow_imbalance_3"])
