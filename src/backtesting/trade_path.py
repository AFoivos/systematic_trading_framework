from __future__ import annotations

"""Backward-compatible import path for shared trade-path simulation helpers."""

from src.utils.trade_path import (
    compute_trade_pnl,
    normalize_dynamic_exit_config,
    simulate_long_trade_path,
    simulate_short_trade_path,
    simulate_strategy_path_trade_outcome,
)

__all__ = [
    "compute_trade_pnl",
    "normalize_dynamic_exit_config",
    "simulate_long_trade_path",
    "simulate_short_trade_path",
    "simulate_strategy_path_trade_outcome",
]
