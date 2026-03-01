from __future__ import annotations

import pandas as pd


def build_rebalance_orders(
    target_weights: pd.Series,
    *,
    prices: pd.Series,
    capital: float,
    current_weights: pd.Series | None = None,
    min_trade_notional: float = 0.0,
) -> pd.DataFrame:
    """
    Build rebalance orders as an explicit intermediate object used by the paper execution
    pipeline. Keeping this assembly step separate makes the orchestration code easier to reason
    about and test.
    """
    if not isinstance(target_weights, pd.Series):
        raise TypeError("target_weights must be a pandas Series.")
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series.")
    if capital <= 0:
        raise ValueError("capital must be > 0.")
    if min_trade_notional < 0:
        raise ValueError("min_trade_notional must be >= 0.")

    target = target_weights.astype(float).fillna(0.0)
    px = prices.reindex(target.index).astype(float)
    if px.isna().any() or (px <= 0.0).any():
        raise ValueError("prices must be positive and available for all assets.")

    current = (
        current_weights.reindex(target.index).astype(float).fillna(0.0)
        if current_weights is not None
        else pd.Series(0.0, index=target.index, dtype=float)
    )

    target_notional = target * float(capital)
    current_notional = current * float(capital)
    delta_notional = target_notional - current_notional

    orders = pd.DataFrame(
        {
            "target_weight": target,
            "current_weight": current,
            "delta_weight": target - current,
            "price": px,
            "target_notional": target_notional,
            "current_notional": current_notional,
            "delta_notional": delta_notional,
        }
    )
    orders["target_shares"] = orders["target_notional"] / orders["price"]
    orders["delta_shares"] = orders["delta_notional"] / orders["price"]
    orders["abs_delta_notional"] = orders["delta_notional"].abs()

    if min_trade_notional > 0:
        orders = orders.loc[orders["abs_delta_notional"] >= float(min_trade_notional)]

    orders.index.name = "asset"
    orders = orders.sort_values("abs_delta_notional", ascending=False)
    return orders


__all__ = ["build_rebalance_orders"]
