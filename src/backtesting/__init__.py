from __future__ import annotations

from importlib import import_module
from typing import Any

from .engine import BacktestResult, run_backtest
from .manual_barrier import run_manual_barrier_backtest
from src.signals import (
    buy_and_hold_signal,
    momentum_strategy,
    rsi_strategy,
    stochastic_strategy,
    trend_state_long_only_signal,
    trend_state_signal,
    volatility_regime_strategy,
)


def __getattr__(name: str) -> Any:
    if name != "run_portfolio_barrier_backtest":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("src.backtesting.portfolio_barrier"), name)
    globals()[name] = value
    return value


__all__ = [
    "run_backtest",
    "run_manual_barrier_backtest",
    "run_portfolio_barrier_backtest",
    "BacktestResult",
    "buy_and_hold_signal",
    "trend_state_long_only_signal",
    "trend_state_signal",
    "rsi_strategy",
    "momentum_strategy",
    "stochastic_strategy",
    "volatility_regime_strategy",
]
