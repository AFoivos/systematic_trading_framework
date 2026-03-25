from __future__ import annotations

import pandas as pd


def compute_drawdown(equity: pd.Series) -> pd.Series:
    """
    Drawdown series from an equity curve.
    """
    if not isinstance(equity, pd.Series):
        raise TypeError("equity must be a pandas Series")

    running_max = equity.cummax()
    dd = equity / running_max - 1.0
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
