from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from src.src_data.providers.base import MarketDataProvider


@dataclass
class YahooFinanceProvider(MarketDataProvider):

    """
    Implement the market data provider contract for Yahoo Finance and normalize the downloaded
    columns into the project OHLCV schema.
    """
    def get_ohlcv(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Implement the get OHLCV step required by the surrounding class. The method keeps
        class-specific behavior explicit while preserving a predictable contract for callers of
        the data ingestion and storage layer.
        """
        df = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            progress=False,
        )

        if df.empty:
            raise ValueError(f"No data returned from Yahoo Finance for symbol={symbol}")

        if isinstance(df.columns, pd.MultiIndex):
            # κρατάμε το πρώτο level (Price: Open/High/Low/Close/Adj Close/Volume)
            df.columns = df.columns.get_level_values(0)

        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )

        expected_cols = ["open", "high", "low", "close", "volume"]
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing expected columns from Yahoo Finance after rename: {missing}. "
                f"Available columns: {list(df.columns)}"
            )

        output_cols = expected_cols + (["adj_close"] if "adj_close" in df.columns else [])
        df = df[output_cols]

        # Clean index
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]

        # Drop rows with NaN in critical fields
        df = df.dropna(subset=["open", "high", "low", "close"])

        # DatetimeIndex enforce
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        return df
