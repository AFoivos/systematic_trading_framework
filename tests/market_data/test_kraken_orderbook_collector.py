from __future__ import annotations

import csv

import pytest

from scripts.collect_kraken_orderbook import (
    CSV_FIELDS,
    apply_kraken_book_message,
    book_to_csv_row,
    build_book_subscription,
    parse_collector_config,
)
from src.market_data.order_book import LocalOrderBook


def test_build_book_subscription_uses_kraken_spot_v2_shape() -> None:
    payload = build_book_subscription("BTC/USD", 100)

    assert payload == {
        "method": "subscribe",
        "params": {
            "channel": "book",
            "symbol": ["BTC/USD"],
            "depth": 100,
        },
    }


def test_snapshot_message_updates_local_order_book_and_emits_metrics_row() -> None:
    book = LocalOrderBook("BTC/USD")
    message = {
        "channel": "book",
        "type": "snapshot",
        "data": [
            {
                "symbol": "BTC/USD",
                "bids": [
                    {"price": 100.0, "qty": 2.0},
                    {"price": 99.5, "qty": 3.0},
                ],
                "asks": [
                    {"price": 101.0, "qty": 4.0},
                    {"price": 101.5, "qty": 1.0},
                ],
                "timestamp": "2026-07-01T12:00:00.000000Z",
                "checksum": 12345,
            }
        ],
    }

    rows = apply_kraken_book_message(message, book)

    assert len(rows) == 1
    row = rows[0]
    assert row["timestamp"] == "2026-07-01T12:00:00+00:00"
    assert row["symbol"] == "BTC/USD"
    assert row["event_type"] == "snapshot"
    assert row["best_bid"] == 100.0
    assert row["best_ask"] == 101.0
    assert row["mid_price"] == 100.5
    assert row["spread"] == 1.0
    assert row["imbalance_1"] == pytest.approx(2.0 / 6.0)
    assert row["imbalance_5"] == pytest.approx(5.0 / 10.0)
    assert row["bid_depth_5"] == 5.0
    assert row["ask_depth_5"] == 5.0
    assert row["checksum"] == 12345


def test_update_message_applies_incremental_changes_and_removals() -> None:
    book = LocalOrderBook("BTC/USD")
    apply_kraken_book_message(
        {
            "channel": "book",
            "type": "snapshot",
            "data": [
                {
                    "bids": [{"price": 100.0, "qty": 2.0}],
                    "asks": [{"price": 101.0, "qty": 4.0}],
                    "timestamp": "2026-07-01T12:00:00Z",
                    "sequence": 10,
                }
            ],
        },
        book,
    )

    rows = apply_kraken_book_message(
        {
            "channel": "book",
            "type": "update",
            "data": [
                {
                    "bids": [{"price": 100.0, "qty": 0.0}, {"price": 99.0, "qty": 5.0}],
                    "asks": [{"price": 101.0, "qty": 2.0}],
                    "timestamp": "2026-07-01T12:00:01Z",
                    "sequence": 11,
                }
            ],
        },
        book,
    )

    assert len(rows) == 1
    assert book.best_bid == 99.0
    assert book.best_ask == 101.0
    assert rows[0]["sequence"] == 11
    assert rows[0]["event_type"] == "update"


def test_non_book_and_ack_messages_are_ignored() -> None:
    book = LocalOrderBook("BTC/USD")

    assert apply_kraken_book_message({"channel": "heartbeat"}, book) == []
    assert apply_kraken_book_message({"channel": "book", "type": "subscribed"}, book) == []


def test_csv_fields_cover_required_order_book_metrics(tmp_path) -> None:
    book = LocalOrderBook("BTC/USD")
    book.apply_snapshot(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)])
    row = book_to_csv_row(book, event_type="snapshot", checksum=1)
    output = tmp_path / "events.csv"

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow(row)

    assert output.read_text(encoding="utf-8").splitlines()[0].split(",") == CSV_FIELDS


def test_parse_collector_config_requires_data_only_kraken_public_mode(tmp_path) -> None:
    config = {
        "execution": {
            "mode": "data_only",
            "venue": "kraken_spot_public",
            "symbol": "BTC/USD",
            "depth": 100,
            "reconnect": True,
            "max_events": 7,
        },
        "logging": {"level": "INFO", "output_dir": str(tmp_path)},
    }

    parsed = parse_collector_config(config)

    assert parsed.symbol == "BTC/USD"
    assert parsed.depth == 100
    assert parsed.reconnect is True
    assert parsed.max_events == 7
    assert parsed.output_path == tmp_path / "orderbook_events.csv"


def test_parse_collector_config_rejects_non_data_only_mode() -> None:
    with pytest.raises(SystemExit, match="execution.mode: data_only"):
        parse_collector_config(
            {
                "execution": {
                    "mode": "paper",
                    "venue": "kraken_spot_public",
                    "symbol": "BTC/USD",
                }
            }
        )
