from __future__ import annotations


class BrokerError(RuntimeError):
    """Base error for broker execution failures."""


class AuthenticationError(BrokerError):
    """Raised when broker authentication fails or credentials are missing."""


class OrderRejected(BrokerError):
    """Raised when a broker rejects an order request."""


class ConnectionLost(BrokerError):
    """Raised when a broker connection cannot be established or recovered."""


class SymbolNotFound(BrokerError):
    """Raised when a framework symbol cannot be resolved at the broker."""


class RateLimitExceeded(BrokerError):
    """Raised when the broker rate limit is exceeded after retries."""


__all__ = [
    "AuthenticationError",
    "BrokerError",
    "ConnectionLost",
    "OrderRejected",
    "RateLimitExceeded",
    "SymbolNotFound",
]
