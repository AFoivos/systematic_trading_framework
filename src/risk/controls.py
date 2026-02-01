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
) -> pd.Series:
    """
    When drawdown exceeds max_drawdown, reduce exposure to min_exposure
    for the next cooloff_bars periods.
    """
    if not isinstance(equity, pd.Series):
        raise TypeError("equity must be a pandas Series")
    if cooloff_bars < 0:
        raise ValueError("cooloff_bars must be >= 0")

    dd = compute_drawdown(equity)
    mult = pd.Series(1.0, index=equity.index, name="dd_cooloff_mult")

    cooldown = 0
    for i in range(len(dd)):
        if cooldown > 0:
            mult.iat[i] = min_exposure
            cooldown -= 1
            continue

        if dd.iat[i] <= -abs(max_drawdown):
            mult.iat[i] = min_exposure
            cooldown = cooloff_bars
        else:
            mult.iat[i] = 1.0

    return mult
