from __future__ import annotations

"""Causal decision-time liquidity feature extension for alpha discovery v2."""

import numpy as np
import pandas as pd

from src.features.alpha_discovery_primitives import (
    GAP_SEGMENT_COLUMN,
    STATE_ELIGIBLE_COLUMN,
    build_alpha_discovery_features,
    feature_eligibility_column,
)

SPREAD_FRACTION_FEATURE = "spread_fraction"


class AlphaDiscoveryLiquidityFeatureError(ValueError):
    """Raised when canonical decision-time spread cannot be used safely."""


def build_alpha_discovery_liquidity_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add canonical close[t] spread fraction to the v1 primitive feature frame.

    The source value must already satisfy the canonical quote contract.  No
    rolling normalization, imputation, clipping, or future-derived fitting is
    performed here.  A row is eligible only when its complete 30-minute state
    bar is eligible under the existing gap-aware policy.
    """

    required = {SPREAD_FRACTION_FEATURE, "bid_close", "ask_close", "mid_close"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise AlphaDiscoveryLiquidityFeatureError(
            f"alpha_discovery_v2 is missing canonical quote fields: {missing}."
        )
    spread = pd.to_numeric(frame[SPREAD_FRACTION_FEATURE], errors="coerce")
    if spread.isna().any() or not np.isfinite(spread.to_numpy(dtype=float)).all():
        raise AlphaDiscoveryLiquidityFeatureError(
            "spread_fraction must be finite and non-missing."
        )
    if (spread < 0.0).any():
        raise AlphaDiscoveryLiquidityFeatureError(
            "spread_fraction must be non-negative."
        )
    bid_close = pd.to_numeric(frame["bid_close"], errors="coerce")
    ask_close = pd.to_numeric(frame["ask_close"], errors="coerce")
    mid_close = pd.to_numeric(frame["mid_close"], errors="coerce")
    quote_values = np.column_stack((bid_close, ask_close, mid_close))
    if not np.isfinite(quote_values).all() or (mid_close <= 0.0).any():
        raise AlphaDiscoveryLiquidityFeatureError(
            "Canonical close quotes must be finite with positive mid_close."
        )
    if (ask_close < bid_close).any():
        raise AlphaDiscoveryLiquidityFeatureError(
            "Canonical close quotes cannot be crossed."
        )
    expected_spread = (ask_close - bid_close) / mid_close
    if not np.allclose(
        spread.to_numpy(dtype=float),
        expected_spread.to_numpy(dtype=float),
        rtol=1e-9,
        atol=1e-12,
    ):
        raise AlphaDiscoveryLiquidityFeatureError(
            "spread_fraction is inconsistent with canonical bid/ask/mid closes."
        )

    base = build_alpha_discovery_features(frame)
    selected_price_features = (
        "log_return_48",
        "path_efficiency_48",
        "realized_volatility_48",
    )
    selected_columns = [
        "timestamp",
        *selected_price_features,
        STATE_ELIGIBLE_COLUMN,
        GAP_SEGMENT_COLUMN,
        *(feature_eligibility_column(name) for name in selected_price_features),
    ]
    output = base[selected_columns].copy()
    eligible = output[STATE_ELIGIBLE_COLUMN].astype(bool)
    output[SPREAD_FRACTION_FEATURE] = spread.astype(float).where(eligible)
    output[feature_eligibility_column(SPREAD_FRACTION_FEATURE)] = eligible
    ordered = [
        "timestamp",
        *selected_price_features,
        SPREAD_FRACTION_FEATURE,
        STATE_ELIGIBLE_COLUMN,
        GAP_SEGMENT_COLUMN,
        *(feature_eligibility_column(name) for name in selected_price_features),
        feature_eligibility_column(SPREAD_FRACTION_FEATURE),
    ]
    return output[ordered]


__all__ = [
    "AlphaDiscoveryLiquidityFeatureError",
    "SPREAD_FRACTION_FEATURE",
    "build_alpha_discovery_liquidity_features",
]
