from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.src_data.binance_public import (
    BinancePublicClient,
    download_binance_snapshot,
    load_binance_snapshot_frame,
)


def _kline(open_ms: int, close_ms: int, close: float) -> list[object]:
    return [
        open_ms,
        str(close - 1.0),
        str(close + 1.0),
        str(close - 2.0),
        str(close),
        "10",
        close_ms,
        "1000",
        4,
        "5",
        "500",
        "0",
    ]


def test_binance_kline_timestamp_is_close_time_and_pagination_advances() -> None:
    calls: list[dict[str, object]] = []
    first_open = int(pd.Timestamp("2024-01-01T00:00:00Z").timestamp() * 1_000)
    second_open = int(pd.Timestamp("2024-01-01T00:30:00Z").timestamp() * 1_000)
    rows = [
        _kline(first_open, second_open - 1, 101.0),
        _kline(second_open, second_open + 30 * 60 * 1_000 - 1, 102.0),
    ]

    def transport(_url: str, params: dict[str, object]) -> list[list[object]]:
        calls.append(dict(params))
        return rows if len(calls) == 1 else []

    client = BinancePublicClient(transport=transport, pause_seconds=0.0)
    frame = client.fetch(
        dataset="spot_klines",
        symbol="BTCUSDT",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T01:00:00Z",
        interval="30m",
        limit=2,
    )

    assert frame.index[0] == pd.Timestamp("2024-01-01T00:29:59.999Z")
    assert frame.index[1] == pd.Timestamp("2024-01-01T00:59:59.999Z")
    assert calls[1]["startTime"] == second_open + 1
    assert frame["close"].tolist() == [101.0, 102.0]


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def endpoint_url(self, dataset: str) -> str:
        return f"https://example.invalid/{dataset}"

    def fetch(self, *, dataset: str, symbol: str, **_: object) -> pd.DataFrame:
        self.calls += 1
        if dataset == "funding_rates":
            index = pd.DatetimeIndex([pd.Timestamp("2024-01-01T08:00:00Z")], name="timestamp")
            return pd.DataFrame(
                {"symbol": [symbol], "funding_rate": [0.0001], "mark_price": [100.0]},
                index=index,
            )
        index = pd.DatetimeIndex([pd.Timestamp("2024-01-01T07:59:59.999Z")], name="timestamp")
        return pd.DataFrame(
            {
                "open_time": [pd.Timestamp("2024-01-01T07:30:00Z")],
                "open": [99.0],
                "high": [101.0],
                "low": [98.0],
                "close": [100.0],
                "volume": [10.0],
            },
            index=index,
        )


def test_snapshot_is_hashed_reused_and_tampering_is_detected(tmp_path: Path) -> None:
    client = _FakeClient()
    manifest = download_binance_snapshot(
        output_dir=tmp_path / "snapshot",
        symbols=["BTCUSDT"],
        start="2024-01-01T00:00:00Z",
        end="2024-01-02T00:00:00Z",
        datasets=["spot_klines", "perp_klines", "funding_rates"],
        client=client,  # type: ignore[arg-type]
    )
    assert client.calls == 3
    assert len(manifest["files"]) == 3

    cached = download_binance_snapshot(
        output_dir=tmp_path / "snapshot",
        symbols=["BTCUSDT"],
        start="2024-01-01T00:00:00Z",
        end="2024-01-02T00:00:00Z",
        datasets=["spot_klines", "perp_klines", "funding_rates"],
        client=client,  # type: ignore[arg-type]
    )
    assert cached["request_sha256"] == manifest["request_sha256"]
    assert client.calls == 3

    with pytest.raises(FileExistsError, match="does not match"):
        download_binance_snapshot(
            output_dir=tmp_path / "snapshot",
            symbols=["BTCUSDT"],
            start="2024-01-01T00:00:00Z",
            end="2024-01-03T00:00:00Z",
            datasets=["spot_klines", "perp_klines", "funding_rates"],
            client=client,  # type: ignore[arg-type]
        )

    loaded = load_binance_snapshot_frame(
        tmp_path / "snapshot",
        symbol="BTCUSDT",
        dataset="funding_rates",
    )
    assert loaded.iloc[0]["funding_rate"] == pytest.approx(0.0001)

    path = tmp_path / "snapshot" / "BTCUSDT" / "funding_rates.csv"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_binance_snapshot_frame(
            tmp_path / "snapshot",
            symbol="BTCUSDT",
            dataset="funding_rates",
        )
