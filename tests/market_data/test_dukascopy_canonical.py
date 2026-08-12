from __future__ import annotations

from datetime import date
from hashlib import sha256
import json

import pandas as pd
import pytest

from src.src_data.dukascopy_canonical import (
    DukascopyCanonicalError,
    DukascopyDailyClient,
    RawArtifact,
    audit_canonical_30m_frame,
    canonicalize_bid_ask_minutes,
    decode_daily_candles,
    dukascopy_daily_url,
    source_bundle_sha256,
)


def _payload(
    *,
    side_offset: float,
    times: list[int] | None = None,
    crossed_close: bool = False,
) -> dict[str, object]:
    deltas = times or list(range(30))
    encoded_times = [deltas[0], *[b - a for a, b in zip(deltas, deltas[1:])]]
    row_count = len(deltas)
    open_price = 100.0 + side_offset
    high_price = 100.2 + side_offset
    low_price = 99.8 + side_offset
    close_price = 100.1 + side_offset
    if crossed_close:
        close_price = 100.0
    return {
        "timestamp": 1767225600000,
        "multiplier": 0.1,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "shift": 60000,
        "times": encoded_times,
        "opens": [0] * row_count,
        "highs": [0] * row_count,
        "lows": [0] * row_count,
        "closes": [0] * row_count,
        "volumes": [0.001] * row_count,
    }


def test_decoder_preserves_only_observed_candles_and_converts_volume_units() -> None:
    frame = decode_daily_candles(_payload(side_offset=0.0, times=[0, 2]), side="BID")

    assert list(frame["timestamp"]) == [
        pd.Timestamp("2026-01-01T00:00:00Z"),
        pd.Timestamp("2026-01-01T00:02:00Z"),
    ]
    assert frame["bid_volume"].tolist() == pytest.approx([1000.0, 1000.0])


def test_decoder_preserves_a_provider_empty_day_without_fabricating_rows() -> None:
    payload = _payload(side_offset=0.0)
    payload.update(
        {
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "times": [],
            "opens": [],
            "highs": [],
            "lows": [],
            "closes": [],
            "volumes": [],
        }
    )

    frame = decode_daily_candles(payload, side="BID")

    assert frame.empty
    assert list(frame.columns) == [
        "timestamp",
        "bid_open",
        "bid_high",
        "bid_low",
        "bid_close",
        "bid_volume",
    ]


def test_canonicalizer_uses_paired_real_quotes_and_exact_spread_formulas() -> None:
    bid = decode_daily_candles(_payload(side_offset=0.0), side="BID")
    ask = decode_daily_candles(_payload(side_offset=0.2), side="ASK")

    bars = canonicalize_bid_ask_minutes(bid, ask)

    assert len(bars) == 1
    row = bars.iloc[0]
    assert row["timestamp"] == pd.Timestamp("2026-01-01T00:00:00Z")
    assert row["mid_close"] == pytest.approx(100.2)
    assert row["spread_absolute"] == pytest.approx(0.2)
    assert row["spread_fraction"] == pytest.approx(0.2 / 100.2)
    assert row["spread_bps"] == pytest.approx(10_000.0 * 0.2 / 100.2)
    assert row["bid_volume"] == pytest.approx(30_000.0)
    assert row["ask_volume"] == pytest.approx(30_000.0)
    assert row["volume"] == pytest.approx(60_000.0)
    assert row["observed_minute_count"] == 30


def test_canonicalizer_refuses_silent_bid_ask_coverage_loss() -> None:
    bid = decode_daily_candles(_payload(side_offset=0.0, times=[0, 1, 2]), side="BID")
    ask = decode_daily_candles(_payload(side_offset=0.2, times=[0, 2]), side="ASK")

    with pytest.raises(DukascopyCanonicalError, match="refuses an inner join"):
        canonicalize_bid_ask_minutes(bid, ask)


def test_canonicalizer_refuses_crossed_source_quotes() -> None:
    bid = decode_daily_candles(_payload(side_offset=0.0), side="BID")
    ask = decode_daily_candles(
        _payload(side_offset=0.2, crossed_close=True), side="ASK"
    )

    with pytest.raises(DukascopyCanonicalError, match="crossed BID/ASK"):
        canonicalize_bid_ask_minutes(bid, ask)


def test_daily_client_caches_exact_source_bytes(tmp_path) -> None:
    raw = json.dumps(_payload(side_offset=0.0), separators=(",", ":")).encode()
    calls: list[str] = []

    def transport(url: str) -> bytes:
        calls.append(url)
        return raw

    client = DukascopyDailyClient(
        transport=transport,
        request_pause_seconds=0.0,
    )
    first, first_artifact = client.fetch_day(
        date(2026, 1, 1), side="BID", raw_root=tmp_path
    )
    second, second_artifact = client.fetch_day(
        date(2026, 1, 1), side="BID", raw_root=tmp_path
    )

    assert len(calls) == 1
    assert calls[0] == dukascopy_daily_url(date(2026, 1, 1), "BID")
    assert first.equals(second)
    assert first_artifact == second_artifact
    assert first_artifact.sha256 == sha256(raw).hexdigest()
    assert (tmp_path / first_artifact.path).read_bytes() == raw


def test_source_bundle_fingerprint_is_order_independent() -> None:
    first = RawArtifact("2026-01-01", "BID", "a", "a" * 64, 1, 1)
    second = RawArtifact("2026-01-01", "ASK", "b", "b" * 64, 1, 1)

    assert source_bundle_sha256([first, second]) == source_bundle_sha256(
        [second, first]
    )


def test_canonical_audit_reports_partial_minutes_without_blocking() -> None:
    bid = decode_daily_candles(_payload(side_offset=0.0, times=[0, 1, 2]), side="BID")
    ask = decode_daily_candles(_payload(side_offset=0.2, times=[0, 1, 2]), side="ASK")
    bars = canonicalize_bid_ask_minutes(bid, ask)

    report = audit_canonical_30m_frame(bars)

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["research_eligible"] is True
    assert report["metrics"]["partial_30m_bar_count"] == 1
    assert [issue["code"] for issue in report["issues"]] == [
        "PARTIAL_SOURCE_MINUTE_COVERAGE"
    ]


def test_canonical_audit_blocks_any_spread_unit_mutation() -> None:
    bid = decode_daily_candles(_payload(side_offset=0.0), side="BID")
    ask = decode_daily_candles(_payload(side_offset=0.2), side="ASK")
    bars = canonicalize_bid_ask_minutes(bid, ask)
    bars["spread_bps"] = bars["spread_fraction"]

    report = audit_canonical_30m_frame(bars)

    assert report["status"] == "FAIL"
    assert report["research_eligible"] is False
    assert "INVALID_SPREAD_FORMULAS" in {issue["code"] for issue in report["issues"]}


def test_canonical_audit_checks_bid_mid_ask_for_every_ohlc_field() -> None:
    bid = decode_daily_candles(_payload(side_offset=0.0), side="BID")
    ask = decode_daily_candles(_payload(side_offset=0.2), side="ASK")
    bars = canonicalize_bid_ask_minutes(bid, ask)
    bars.loc[0, "mid_high"] = bars.loc[0, "ask_high"] + 1.0

    report = audit_canonical_30m_frame(bars)

    assert report["status"] == "FAIL"
    assert report["metrics"]["invalid_bid_mid_ask_order_by_field"]["high"] == 1
