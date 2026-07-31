from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.eurusd_ftmo_ml_v2_contract import (
    COMMISSION_PIPS_PER_SIDE,
    PIP_SIZE,
    SLIPPAGE_PIPS_PER_SIDE,
)


def executable_trade_return(
    *,
    direction: int,
    entry_bid: float,
    entry_ask: float,
    exit_bid: float,
    exit_ask: float,
    pip_size: float = PIP_SIZE,
    commission_pips_per_side: float = COMMISSION_PIPS_PER_SIDE,
    slippage_pips_per_side: float = SLIPPAGE_PIPS_PER_SIDE,
) -> dict[str, float | int]:
    """Calculate one candidate outcome with spread embedded exactly once."""
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1.")
    prices = np.asarray([entry_bid, entry_ask, exit_bid, exit_ask], dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0.0).any():
        raise ValueError("Executable prices must be finite and positive.")
    if entry_bid > entry_ask or exit_bid > exit_ask:
        raise ValueError("Bid must not exceed ask.")
    if direction == 1:
        entry_price = float(entry_ask)
        exit_price = float(exit_bid)
        gross_return = (exit_price - entry_price) / entry_price
    else:
        entry_price = float(entry_bid)
        exit_price = float(exit_ask)
        gross_return = (entry_price - exit_price) / entry_price
    commission_return = 2.0 * float(commission_pips_per_side) * float(pip_size) / entry_price
    slippage_return = 2.0 * float(slippage_pips_per_side) * float(pip_size) / entry_price
    net_return = float(gross_return - commission_return - slippage_return)
    return {
        "entry_price": entry_price,
        "exit_price": exit_price,
        "gross_return": float(gross_return),
        "commission_return": float(commission_return),
        "slippage_return": float(slippage_return),
        "additional_cost_return": float(commission_return + slippage_return),
        "net_return": net_return,
        "target_positive_net": int(net_return > 0.0),
    }


def attach_candidate_targets(candidates: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    required = {"candidate_id", "entry_timestamp", "exit_timestamp", "direction"}
    missing = sorted(required.difference(candidates.columns))
    if missing:
        raise KeyError(f"Missing candidate target columns: {missing}")
    market_required = {"bid_open", "ask_open"}
    missing_market = sorted(market_required.difference(market.columns))
    if missing_market:
        raise KeyError(f"Missing market execution columns: {missing_market}")
    records: list[dict[str, float | int]] = []
    for candidate in candidates.itertuples(index=False):
        entry_time = pd.Timestamp(candidate.entry_timestamp)
        exit_time = pd.Timestamp(candidate.exit_timestamp)
        if entry_time not in market.index or exit_time not in market.index:
            raise ValueError(f"Candidate {candidate.candidate_id} references a missing execution bar.")
        entry = market.loc[entry_time]
        exit_ = market.loc[exit_time]
        records.append(
            executable_trade_return(
                direction=int(candidate.direction),
                entry_bid=float(entry["bid_open"]),
                entry_ask=float(entry["ask_open"]),
                exit_bid=float(exit_["bid_open"]),
                exit_ask=float(exit_["ask_open"]),
            )
        )
    out = candidates.copy().reset_index(drop=True)
    targets = pd.DataFrame.from_records(records, index=out.index)
    for column in targets.columns:
        out[column] = targets[column]
    return out


__all__ = ["attach_candidate_targets", "executable_trade_return"]
