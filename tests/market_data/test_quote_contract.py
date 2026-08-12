from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.src_data.quote_contract import (
    QuoteContractError,
    SpreadSemantics,
    add_canonical_quote_columns,
    classify_spread_bps_semantics,
    compute_quote_metrics,
    validate_canonical_quote_columns,
)


def test_hand_calculated_spread_contract() -> None:
    metrics = compute_quote_metrics([100.0], [100.10])

    assert metrics.loc[0, "mid"] == pytest.approx(100.05)
    assert metrics.loc[0, "spread_absolute"] == pytest.approx(0.10)
    assert metrics.loc[0, "spread_fraction"] == pytest.approx(0.10 / 100.05)
    assert metrics.loc[0, "spread_bps"] == pytest.approx(10_000.0 * 0.10 / 100.05)


def test_crossed_quote_and_non_midpoint_are_rejected() -> None:
    with pytest.raises(QuoteContractError, match="bid <= ask"):
        compute_quote_metrics([100.10], [100.0])
    with pytest.raises(QuoteContractError, match="mid must equal"):
        compute_quote_metrics([100.0], [100.10], mid=[100.0])


def test_legacy_fraction_is_classified_and_never_silently_overwritten() -> None:
    frame = pd.DataFrame(
        {
            "bid": [100.0, 101.0],
            "ask": [100.10, 101.20],
            "mid": [100.05, 101.10],
        }
    )
    frame["spread_bps"] = (frame["ask"] - frame["bid"]) / frame["mid"]

    assert classify_spread_bps_semantics(frame) is SpreadSemantics.LEGACY_FRACTION
    with pytest.raises(QuoteContractError, match="Refusing to overwrite"):
        add_canonical_quote_columns(frame)


def test_canonical_columns_round_trip_and_validate() -> None:
    raw = pd.DataFrame({"bid": [100.0, 101.0], "ask": [100.10, 101.20]})
    canonical = add_canonical_quote_columns(raw)

    validate_canonical_quote_columns(canonical)
    assert classify_spread_bps_semantics(canonical) is SpreadSemantics.CANONICAL_BPS
    assert np.all(canonical["bid"] <= canonical["mid"])
    assert np.all(canonical["mid"] <= canonical["ask"])
    assert np.all(canonical["spread_absolute"] >= 0.0)


def test_existing_conflicting_fraction_requires_explicit_preservation() -> None:
    frame = pd.DataFrame(
        {
            "bid": [100.0],
            "ask": [100.10],
            "spread_bps": [0.10 / 100.05],
        }
    )
    migrated = frame.rename(columns={"spread_bps": "spread_bps_legacy_fraction"})
    migrated = add_canonical_quote_columns(migrated)

    assert migrated.loc[0, "spread_bps_legacy_fraction"] == pytest.approx(0.10 / 100.05)
    assert migrated.loc[0, "spread_bps"] == pytest.approx(10_000.0 * 0.10 / 100.05)
