from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def compute_drawdown(equity: pd.Series) -> pd.Series:
    """
    Drawdown series from an equity curve.
    """
    if not isinstance(equity, pd.Series):
        raise TypeError("equity must be a pandas Series")

    running_max = equity.astype(float).cummax().clip(lower=1.0)
    dd = equity.astype(float) / running_max - 1.0
    dd.name = f"{equity.name}_drawdown"
    return dd


def drawdown_cooloff_multiplier(
    equity: pd.Series,
    max_drawdown: float = 0.2,
    cooloff_bars: int = 20,
    min_exposure: float = 0.0,
    rearm_drawdown: float | None = None,
) -> pd.Series:
    """
    When drawdown exceeds max_drawdown, reduce exposure to min_exposure
    for the next cooloff_bars periods. A new cooloff can trigger only after
    drawdown has recovered above rearm_drawdown.
    """
    if not isinstance(equity, pd.Series):
        raise TypeError("equity must be a pandas Series")
    if cooloff_bars < 0:
        raise ValueError("cooloff_bars must be >= 0")

    max_drawdown = abs(float(max_drawdown))
    if max_drawdown <= 0.0:
        raise ValueError("max_drawdown must be > 0.")
    if rearm_drawdown is None:
        rearm_drawdown = max_drawdown
    rearm_drawdown = abs(float(rearm_drawdown))
    if rearm_drawdown <= 0.0:
        raise ValueError("rearm_drawdown must be > 0.")
    if rearm_drawdown > max_drawdown:
        raise ValueError("rearm_drawdown must be <= max_drawdown.")

    mult = pd.Series(1.0, index=equity.index, name="dd_cooloff_mult")
    if cooloff_bars == 0:
        return mult

    dd = compute_drawdown(equity)

    cooldown = 0
    guard_armed = True
    for i in range(len(dd)):
        if not guard_armed and dd.iat[i] >= -rearm_drawdown:
            guard_armed = True
        if cooldown > 0:
            mult.iat[i] = min_exposure
            cooldown -= 1
            continue

        if guard_armed and dd.iat[i] <= -max_drawdown:
            mult.iat[i] = min_exposure
            cooldown = cooloff_bars - 1
            guard_armed = False
        else:
            mult.iat[i] = 1.0

    return mult


def event_risk_guard_multiplier(
    realized_returns: pd.Series,
    *,
    at_position: int,
    config: dict[str, Any] | None,
) -> tuple[float, str | None]:
    """Resolve a causal entry-risk multiplier from realized daily/weekly PnL.

    Only returns booked strictly before ``at_position`` are observed.  This
    makes the helper suitable for event backtests in which a signal at bar
    ``t`` is executed at ``t+1``.  Thresholds may be supplied as positive loss
    magnitudes or negative returns.  The hard daily and weekly guards flatten;
    the soft daily guard applies the configured risk multiplier.
    """
    cfg = dict(config or {})
    if not bool(cfg.get("enabled", False)):
        return 1.0, None
    if not isinstance(realized_returns, pd.Series):
        raise TypeError("realized_returns must be a pandas Series.")
    if not isinstance(realized_returns.index, pd.DatetimeIndex):
        raise TypeError("event risk guards require a DatetimeIndex.")
    if isinstance(at_position, bool) or not isinstance(at_position, int):
        raise TypeError("at_position must be an integer.")
    if not 0 <= at_position < len(realized_returns):
        raise IndexError("at_position is outside realized_returns.")

    timezone = str(cfg.get("timezone", "UTC") or "UTC")
    index = realized_returns.index
    if index.tz is None:
        localized = index.tz_localize("UTC").tz_convert(timezone)
    else:
        localized = index.tz_convert(timezone)
    current = localized[at_position]
    prefix = pd.to_numeric(realized_returns.iloc[:at_position], errors="coerce").fillna(0.0)
    prefix_index = localized[:at_position]

    def loss_threshold(name: str) -> float | None:
        value = cfg.get(name)
        if value is None:
            return None
        numeric = float(value)
        if not np.isfinite(numeric) or numeric == 0.0:
            raise ValueError(f"portfolio_guard.{name} must be finite and non-zero.")
        return -abs(numeric)

    def compounded(mask: np.ndarray) -> float:
        values = prefix.to_numpy(dtype=float)[mask]
        return float(np.prod(1.0 + values) - 1.0) if values.size else 0.0

    current_day = current.date()
    day_mask = np.asarray([timestamp.date() == current_day for timestamp in prefix_index], dtype=bool)
    current_week = current.tz_localize(None).to_period(str(cfg.get("weekly_anchor", "W-FRI") or "W-FRI"))
    week_mask = np.asarray(
        [
            timestamp.tz_localize(None).to_period(str(cfg.get("weekly_anchor", "W-FRI") or "W-FRI"))
            == current_week
            for timestamp in prefix_index
        ],
        dtype=bool,
    )
    daily_return = compounded(day_mask)
    weekly_values = prefix.to_numpy(dtype=float)[week_mask]
    if weekly_values.size:
        weekly_equity = np.cumprod(1.0 + weekly_values)
        weekly_peak = np.maximum.accumulate(
            np.concatenate(([1.0], weekly_equity))
        )[-1]
        weekly_drawdown = float(weekly_equity[-1] / weekly_peak - 1.0)
    else:
        weekly_drawdown = 0.0

    weekly_stop = loss_threshold("weekly_drawdown")
    if weekly_stop is not None and weekly_drawdown <= weekly_stop:
        return 0.0, "weekly_stop"
    daily_hard_stop = loss_threshold("daily_hard_stop")
    if daily_hard_stop is not None and daily_return <= daily_hard_stop:
        return 0.0, "daily_hard_stop"
    daily_soft_stop = loss_threshold("daily_soft_stop")
    if daily_soft_stop is not None and daily_return <= daily_soft_stop:
        multiplier = float(cfg.get("daily_soft_stop_risk_multiplier", 0.5))
        if not np.isfinite(multiplier) or not 0.0 <= multiplier <= 1.0:
            raise ValueError("portfolio_guard.daily_soft_stop_risk_multiplier must be in [0, 1].")
        return multiplier, "daily_soft_stop"
    return 1.0, None


__all__ = [
    "compute_drawdown",
    "drawdown_cooloff_multiplier",
    "event_risk_guard_multiplier",
]
