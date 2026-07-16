from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics
from src.backtesting.holding import apply_min_holding_bars_to_positions
from src.risk.position_sizing import scale_signal_by_vol

_ALLOWED_MISSING_RETURN_POLICIES = {"raise", "raise_if_exposed", "fill_zero"}


@dataclass
class BacktestResult:
    """
    Store the complete result of a single-asset backtest, including returns, positions, costs,
    turnover, and the precomputed summary metrics consumed by downstream reporting.
    """
    equity_curve: pd.Series
    returns: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    positions: pd.Series
    turnover: pd.Series
    summary: dict
    trades: pd.DataFrame | None = None
    mark_to_market_returns: pd.Series | None = None
    mark_to_market_equity_curve: pd.Series | None = None
    mark_to_market_summary: dict | None = None
    realized_returns: pd.Series | None = None
    realized_gross_returns: pd.Series | None = None
    realized_equity_curve: pd.Series | None = None
    realized_summary: dict | None = None


def _apply_missing_return_policy(
    returns: pd.Series,
    *,
    prev_positions: pd.Series,
    missing_return_policy: str,
) -> pd.Series:
    """
    Resolve missing-return handling explicitly so exposed positions cannot silently inherit flat
    PnL from missing market data.
    """
    if missing_return_policy not in _ALLOWED_MISSING_RETURN_POLICIES:
        raise ValueError(
            f"missing_return_policy must be one of {_ALLOWED_MISSING_RETURN_POLICIES}."
        )

    rets = returns.astype(float)
    missing_mask = rets.isna()
    if not bool(missing_mask.any()):
        return rets

    if missing_return_policy == "raise":
        examples = ", ".join(str(ts) for ts in rets.index[missing_mask][:5])
        raise ValueError(f"Missing returns encountered at timestamps: {examples}")

    if missing_return_policy == "raise_if_exposed":
        exposed_missing = missing_mask & prev_positions.ne(0.0)
        if bool(exposed_missing.any()):
            examples = ", ".join(str(ts) for ts in rets.index[exposed_missing][:5])
            raise ValueError(
                "Missing returns encountered while positions were open at timestamps: "
                f"{examples}"
            )

    return rets.fillna(0.0)


def run_backtest(
    df: pd.DataFrame,
    signal_col: str,
    returns_col: str,
    returns_type: Literal["simple", "log"] = "simple",
    missing_return_policy: str = "raise_if_exposed",
    cost_per_unit_turnover: float = 0.0,
    slippage_per_unit_turnover: float = 0.0,
    target_vol: Optional[float] = None,
    vol_col: Optional[str] = None,
    max_leverage: float = 3.0,
    dd_guard: bool = True,
    max_drawdown: float = 0.2,
    cooloff_bars: int = 20,
    rearm_drawdown: Optional[float] = None,
    periods_per_year: int = 252,
    min_holding_bars: int = 0,
    liquidate_at_end: bool = False,
) -> BacktestResult:
    """
    Simple vectorized backtest with optional vol targeting, slippage, and drawdown guard.
    Returns are interpreted as simple returns by default. If returns_type="log",
    they are converted to simple returns via expm1 for PnL accounting. When
    drawdown guarding is enabled, rearm_drawdown controls how much recovery is
    required before a new cooloff can trigger.
    """
    if signal_col not in df.columns:
        raise KeyError(f"signal_col '{signal_col}' not found in DataFrame")
    if returns_col not in df.columns:
        raise KeyError(f"returns_col '{returns_col}' not found in DataFrame")

    signal = df[signal_col].astype(float).fillna(0.0)
    returns = df[returns_col].astype(float)
    if returns_type == "log":
        returns = np.expm1(returns)
    elif returns_type != "simple":
        raise ValueError("returns_type must be 'simple' or 'log'.")

    leverage_cap = abs(float(max_leverage))
    positions = signal.copy().clip(lower=-leverage_cap, upper=leverage_cap)

    if target_vol is not None:
        if vol_col is None:
            raise ValueError("vol_col must be provided when target_vol is set")
        if vol_col not in df.columns:
            raise KeyError(f"vol_col '{vol_col}' not found in DataFrame")
        positions = scale_signal_by_vol(
            signal=positions,
            vol=df[vol_col].astype(float),
            target_vol=target_vol,
            max_leverage=max_leverage,
        ).fillna(0.0)
        positions = positions.clip(lower=-leverage_cap, upper=leverage_cap)

    positions = apply_min_holding_bars_to_positions(
        positions,
        min_holding_bars=int(min_holding_bars),
    ).clip(lower=-leverage_cap, upper=leverage_cap)

    (
        positions,
        turnover,
        gross_returns,
        costs,
        strat_returns,
        equity_curve,
        accounting_meta,
    ) = _run_causal_accounting(
        desired_positions=positions,
        returns=returns,
        missing_return_policy=missing_return_policy,
        cost_rate=float(cost_per_unit_turnover + slippage_per_unit_turnover),
        dd_guard=bool(dd_guard),
        max_drawdown=float(max_drawdown),
        cooloff_bars=int(cooloff_bars),
        rearm_drawdown=rearm_drawdown,
        liquidate_at_end=bool(liquidate_at_end),
    )

    summary = compute_backtest_metrics(
        net_returns=strat_returns,
        periods_per_year=periods_per_year,
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )
    summary.update(accounting_meta)

    return BacktestResult(
        equity_curve=equity_curve,
        returns=strat_returns,
        gross_returns=gross_returns,
        costs=costs,
        positions=positions,
        turnover=turnover,
        summary=summary,
        trades=None,
    )


def _run_causal_accounting(
    *,
    desired_positions: pd.Series,
    returns: pd.Series,
    missing_return_policy: str,
    cost_rate: float,
    dd_guard: bool,
    max_drawdown: float,
    cooloff_bars: int,
    rearm_drawdown: float | None,
    liquidate_at_end: bool,
) -> tuple[
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    dict[str, object],
]:
    if cost_rate < 0.0:
        raise ValueError("combined turnover cost must be >= 0.")
    if cooloff_bars < 0:
        raise ValueError("cooloff_bars must be >= 0.")
    max_dd = abs(float(max_drawdown))
    if dd_guard and max_dd <= 0.0:
        raise ValueError("max_drawdown must be > 0 when dd_guard is enabled.")
    rearm_dd = max_dd if rearm_drawdown is None else abs(float(rearm_drawdown))
    if dd_guard and (rearm_dd <= 0.0 or rearm_dd > max_dd):
        raise ValueError("rearm_drawdown must be in (0, max_drawdown].")

    index = desired_positions.index
    applied = pd.Series(0.0, index=index, name="positions", dtype=float)
    turnover = pd.Series(0.0, index=index, name="turnover", dtype=float)
    gross = pd.Series(0.0, index=index, name="gross_returns", dtype=float)
    costs = pd.Series(0.0, index=index, name="costs", dtype=float)
    net = pd.Series(0.0, index=index, name="returns", dtype=float)
    equity_curve = pd.Series(1.0, index=index, name="equity", dtype=float)

    previous_position = 0.0
    equity = 1.0
    equity_peak = 1.0
    guard_armed = True
    cooloff_remaining = 0
    bankrupt = False
    bankruptcy_time: object | None = None
    guard_trigger_count = 0

    for offset, timestamp in enumerate(index):
        if bankrupt:
            applied.iat[offset] = 0.0
            equity_curve.iat[offset] = 0.0
            previous_position = 0.0
            continue

        raw_return = float(returns.iloc[offset]) if pd.notna(returns.iloc[offset]) else np.nan
        if not np.isfinite(raw_return):
            if missing_return_policy == "raise":
                raise ValueError(f"Missing returns encountered at timestamps: {timestamp}")
            if missing_return_policy == "raise_if_exposed" and abs(previous_position) > 1e-12:
                raise ValueError(
                    "Missing returns encountered while positions were open at timestamps: "
                    f"{timestamp}"
                )
            if missing_return_policy not in _ALLOWED_MISSING_RETURN_POLICIES:
                raise ValueError(
                    f"missing_return_policy must be one of {_ALLOWED_MISSING_RETURN_POLICIES}."
                )
            raw_return = 0.0

        gross_return = float(previous_position * raw_return)
        if not np.isfinite(gross_return):
            raise ValueError(f"Non-finite gross return at {timestamp}.")
        if gross_return <= -1.0:
            gross_return = -1.0

        projected_equity = equity * (1.0 + gross_return)
        projected_peak = max(equity_peak, projected_equity)
        projected_drawdown = (
            projected_equity / projected_peak - 1.0
            if projected_peak > 0.0
            else -1.0
        )
        if dd_guard and not guard_armed and projected_drawdown >= -rearm_dd:
            guard_armed = True

        breach = bool(
            dd_guard
            and cooloff_bars > 0
            and guard_armed
            and projected_drawdown <= -max_dd
        )
        if breach:
            guard_armed = False
            cooloff_remaining = max(cooloff_remaining, cooloff_bars)
            guard_trigger_count += 1

        guard_active = breach or cooloff_remaining > 0
        desired = float(desired_positions.iloc[offset])
        if liquidate_at_end and offset == len(index) - 1:
            desired = 0.0
        next_position = 0.0 if guard_active or gross_return <= -1.0 else desired
        turnover_value = abs(next_position - previous_position)
        cost_value = float(cost_rate * turnover_value)
        available_after_gross = max(1.0 + gross_return, 0.0)
        cost_value = min(cost_value, available_after_gross)
        net_return = gross_return - cost_value

        final_equity = equity * max(1.0 + net_return, 0.0)
        final_peak = max(equity_peak, final_equity)
        final_drawdown = final_equity / final_peak - 1.0 if final_peak > 0.0 else -1.0
        cost_breach = bool(
            dd_guard
            and cooloff_bars > 0
            and not breach
            and guard_armed
            and final_drawdown <= -max_dd
        )
        if cost_breach and next_position != 0.0:
            guard_armed = False
            cooloff_remaining = max(cooloff_remaining, cooloff_bars)
            guard_trigger_count += 1
            next_position = 0.0
            turnover_value = abs(previous_position)
            cost_value = min(float(cost_rate * turnover_value), available_after_gross)
            net_return = gross_return - cost_value
            final_equity = equity * max(1.0 + net_return, 0.0)
            final_peak = max(equity_peak, final_equity)
            guard_active = True

        if net_return <= -1.0 or final_equity <= 0.0:
            net_return = -1.0
            final_equity = 0.0
            next_position = 0.0
            bankrupt = True
            bankruptcy_time = timestamp

        applied.iat[offset] = next_position
        turnover.iat[offset] = turnover_value
        gross.iat[offset] = gross_return
        costs.iat[offset] = cost_value
        net.iat[offset] = net_return
        equity_curve.iat[offset] = final_equity

        equity = final_equity
        equity_peak = final_peak
        previous_position = next_position
        if guard_active and cooloff_remaining > 0:
            cooloff_remaining -= 1

    terminal_open_exposure = float(abs(applied.iloc[-1])) if not applied.empty else 0.0
    return (
        applied,
        turnover,
        gross,
        costs,
        net,
        equity_curve,
        {
            "bankrupt": bool(bankrupt),
            "bankruptcy_time": bankruptcy_time,
            "drawdown_guard_trigger_count": float(guard_trigger_count),
            "liquidate_at_end": bool(liquidate_at_end),
            "terminal_open_exposure": terminal_open_exposure,
            "terminal_liquidation_turnover": (
                float(turnover.iloc[-1])
                if liquidate_at_end and not turnover.empty
                else 0.0
            ),
        },
    )
