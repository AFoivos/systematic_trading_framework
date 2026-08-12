from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.src_data.quality import (
    DataQualityContract,
    QualitySeverity,
    QualityStatus,
    assess_cross_asset_coverage,
    assess_schema_consistency,
    find_exact_duplicate_files,
    run_data_quality_checks,
)
from src.src_data.quote_contract import QuoteColumnNames, add_canonical_quote_columns


def _contract(*, cadence: str = "30min") -> DataQualityContract:
    return DataQualityContract(
        asset="TEST",
        timeframe="30m",
        timezone="UTC",
        cadence=cadence,
        column_units={
            "timestamp": "datetime_utc",
            "open": "price",
            "high": "price",
            "low": "price",
            "close": "price",
            "volume": "base_units",
        },
        volume_semantics="provider_base_asset_volume",
        maximum_gap_multiple=4.0,
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=5, freq="30min", tz="UTC"),
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [10.0, 11.0, 12.0, 13.0, 14.0],
        }
    )


def _issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_clean_quality_contract_passes_with_explicit_timezone_and_cadence() -> None:
    report = run_data_quality_checks(_frame(), _contract())

    assert report.status is QualityStatus.PASS
    assert report.research_eligible is True
    assert report.metrics["timestamps_sorted"] is True
    assert report.metrics["irregular_interval_count"] == 0


def test_duplicate_gap_and_short_cadence_are_detected() -> None:
    duplicate = _frame()
    duplicate.loc[2, "timestamp"] = duplicate.loc[1, "timestamp"]
    duplicate_report = run_data_quality_checks(duplicate, _contract())
    assert "DUPLICATE_TIMESTAMPS" in _issue_codes(duplicate_report)
    assert duplicate_report.research_eligible is False

    gap = _frame().drop(index=2).reset_index(drop=True)
    gap_report = run_data_quality_checks(gap, _contract())
    assert "MISSING_INTERVALS" in _issue_codes(gap_report)
    assert gap_report.status is QualityStatus.PASS_WITH_WARNINGS
    assert gap_report.metrics["estimated_missing_interval_count"] == 1

    short = _frame()
    short["timestamp"] = pd.date_range("2026-01-01", periods=5, freq="15min", tz="UTC")
    short_report = run_data_quality_checks(short, _contract())
    assert "CADENCE_MISMATCH_SHORT_INTERVALS" in _issue_codes(short_report)
    assert short_report.status is QualityStatus.FAIL


def test_timezone_ohlc_volume_nan_and_inf_fail_loudly() -> None:
    frame = _frame()
    frame.loc[1, "high"] = 90.0
    frame.loc[2, "volume"] = -1.0
    frame.loc[3, "close"] = np.inf
    report = run_data_quality_checks(frame, _contract())

    assert {"INVALID_OHLC_GEOMETRY", "NEGATIVE_VOLUME", "INFINITE_VALUES"}.issubset(
        _issue_codes(report)
    )
    assert report.maximum_severity is QualitySeverity.CRITICAL
    assert report.research_eligible is False

    bad_timezone = DataQualityContract(
        asset="TEST",
        timeframe="30m",
        timezone="Not/A_Timezone",
        cadence="30min",
        column_units=_contract().column_units,
        volume_semantics="provider_base_asset_volume",
    )
    timezone_report = run_data_quality_checks(_frame(), bad_timezone)
    assert "INVALID_TIMESTAMP_CONTRACT" in _issue_codes(timezone_report)


def test_malformed_numeric_and_duplicate_schema_fail_as_reports_not_crashes() -> None:
    malformed = _frame()
    malformed["close"] = malformed["close"].astype(object)
    malformed.loc[2, "close"] = "not-a-price"
    malformed_report = run_data_quality_checks(malformed, _contract())
    assert "NON_NUMERIC_REQUIRED_VALUES" in _issue_codes(malformed_report)
    assert malformed_report.research_eligible is False

    duplicate_open = pd.concat([_frame(), _frame()[["open"]]], axis=1)
    duplicate_report = run_data_quality_checks(duplicate_open, _contract())
    assert "DUPLICATE_COLUMN_NAMES" in _issue_codes(duplicate_report)
    assert duplicate_report.maximum_severity is QualitySeverity.CRITICAL
    assert duplicate_report.research_eligible is False


def test_serialized_quality_contract_rejects_coerced_booleans_and_unknown_keys() -> (
    None
):
    payload = _contract().to_dict()
    payload["require_all_column_units"] = "false"
    with pytest.raises(ValueError, match="must be boolean"):
        DataQualityContract.from_dict(payload)

    payload = _contract().to_dict()
    payload["silent_override"] = True
    with pytest.raises(ValueError, match="unexpected=\\['silent_override'\\]"):
        DataQualityContract.from_dict(payload)


def test_quote_geometry_and_legacy_units_are_critical() -> None:
    prices = _frame()
    quote = pd.DataFrame({"bid": prices["close"] - 0.05, "ask": prices["close"] + 0.05})
    quote = add_canonical_quote_columns(quote)
    frame = pd.concat([prices, quote], axis=1)
    units = dict(_contract().column_units) | {
        "bid": "price",
        "ask": "price",
        "mid": "price",
        "spread_absolute": "price",
        "spread_fraction": "fraction",
        "spread_bps": "basis_points",
    }
    contract = DataQualityContract(
        asset="TEST",
        timeframe="30m",
        timezone="UTC",
        cadence="30min",
        quote_columns=QuoteColumnNames(),
        require_canonical_quote_columns=True,
        column_units=units,
        volume_semantics="provider_base_asset_volume",
    )
    assert run_data_quality_checks(frame, contract).status is QualityStatus.PASS

    legacy = frame.copy()
    legacy["spread_bps"] = legacy["spread_fraction"]
    legacy_report = run_data_quality_checks(legacy, contract)
    assert "LEGACY_AMBIGUOUS_SPREAD_BPS" in _issue_codes(legacy_report)
    assert legacy_report.maximum_severity is QualitySeverity.CRITICAL

    crossed = frame.copy()
    crossed["ask"] = crossed["bid"] - 0.01
    crossed_contract = DataQualityContract(
        asset="TEST",
        timeframe="30m",
        timezone="UTC",
        cadence="30min",
        quote_columns=QuoteColumnNames(),
        require_canonical_quote_columns=False,
        column_units=units,
        volume_semantics="provider_base_asset_volume",
    )
    crossed_report = run_data_quality_checks(crossed, crossed_contract)
    assert "INVALID_QUOTE_GEOMETRY" in _issue_codes(crossed_report)
    assert crossed_report.maximum_severity is QualitySeverity.CRITICAL


def test_cross_asset_join_loss_schema_and_duplicate_files(tmp_path: Path) -> None:
    first = _frame()
    second = _frame().iloc[1:].copy()
    coverage = assess_cross_asset_coverage({"A": first, "B": second})
    assert coverage["union_timestamp_count"] == 5
    assert coverage["intersection_timestamp_count"] == 4
    assert coverage["inner_join_loss_count"] == 1
    assert coverage["inner_join_rows_lost_by_asset"] == {"A": 1, "B": 0}
    assert coverage["inner_join_rows_lost_total"] == 1

    assert (
        assess_schema_consistency({"A": first, "B": first.copy()})["consistent"] is True
    )
    changed = first.assign(extra=1.0)
    assert assess_schema_consistency({"A": first, "B": changed})["consistent"] is False

    one = tmp_path / "one.csv"
    two = tmp_path / "two.csv"
    one.write_bytes(b"same-bytes\n")
    two.write_bytes(b"same-bytes\n")
    duplicates = find_exact_duplicate_files([one, two])
    assert list(duplicates.values()) == [[str(one), str(two)]]
