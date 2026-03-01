from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd
import requests

from src.src_data.providers.base import MarketDataProvider


@dataclass
class AlphaVantageFXProvider(MarketDataProvider):
    """
    Lightweight wrapper around Alpha Vantage FX_DAILY endpoint.

    Requires an API key (pass explicitly or set ALPHAVANTAGE_API_KEY env var).
    """

    api_key: Optional[str] = None
    outputsize: Literal["compact", "full"] = "full"

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
        if interval != "1d":
            raise ValueError("Alpha Vantage FX_DAILY supports only 1d interval")

        key = self.api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        if not key:
            raise ValueError("Alpha Vantage API key not provided (env ALPHAVANTAGE_API_KEY)")

        base_symbol = symbol.replace("=X", "")
        if len(base_symbol) != 6:
            raise ValueError("symbol must be 6 letters like 'EURUSD' or 'EURUSD=X'")
        from_symbol = base_symbol[:3]
        to_symbol = base_symbol[3:]

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "FX_DAILY",
            "from_symbol": from_symbol,
            "to_symbol": to_symbol,
            "apikey": key,
            "outputsize": self.outputsize,
            "datatype": "json",
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "Time Series FX (Daily)" not in data:
            raise ValueError(f"Alpha Vantage error: {data.get('Note') or data.get('Error Message') or data}")

        ts = data["Time Series FX (Daily)"]
        df = (
            pd.DataFrame(ts)
            .T.rename(
                columns={
                    "1. open": "open",
                    "2. high": "high",
                    "3. low": "low",
                    "4. close": "close",
                }
            )
            .astype(float)
        )
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        if start:
            df = df[df.index >= pd.to_datetime(start)]
        if end:
            df = df[df.index <= pd.to_datetime(end)]

        df["volume"] = 0.0
        return df
