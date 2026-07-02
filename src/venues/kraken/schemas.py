from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class KrakenCredentials:
    """Kraken Futures credentials loaded only from environment variables."""

    api_key: str
    api_secret: str

    @classmethod
    def from_env(cls) -> "KrakenCredentials":
        """Load demo credentials from environment and fail with a clear error if absent."""
        api_key = os.environ.get("KRAKEN_FUTURES_API_KEY")
        api_secret = os.environ.get("KRAKEN_FUTURES_API_SECRET")
        if not api_key or not api_secret:
            raise RuntimeError(
                "Missing Kraken Futures demo credentials. Set KRAKEN_FUTURES_API_KEY "
                "and KRAKEN_FUTURES_API_SECRET in the environment."
            )
        return cls(api_key=api_key, api_secret=api_secret)


@dataclass(frozen=True)
class KrakenOrderRequest:
    """Normalized Kraken limit order request."""

    symbol: str
    side: str
    price: float
    quantity: float


__all__ = ["KrakenCredentials", "KrakenOrderRequest"]
