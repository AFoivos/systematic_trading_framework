from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

class MarketDataProvider(ABC):
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
