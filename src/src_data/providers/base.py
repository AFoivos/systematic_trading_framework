from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

class MarketDataProvider(ABC):
    """
    Define the abstract provider interface that every market data backend must implement in
    order to return normalized OHLCV data.
    """

    @abstractmethod
    def get_ohlcv(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data 
        """
        raise NotImplementedError
