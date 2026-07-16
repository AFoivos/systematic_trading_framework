from __future__ import annotations

import numpy as np
import pandas as pd


def wilder_smooth(series: pd.Series, *, window: int) -> pd.Series:
    """Classic Wilder smoothing with an initial ``window``-observation SMA seed."""
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise ValueError("window must be a positive integer.")

    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    output = np.full(len(values), np.nan, dtype=float)
    seed: list[float] = []
    state: float | None = None

    for pos, value in enumerate(values):
        if not np.isfinite(value):
            seed.clear()
            state = None
            continue
        if state is None:
            seed.append(float(value))
            if len(seed) < window:
                continue
            state = float(np.mean(seed[-window:]))
        else:
            state = ((state * float(window - 1)) + float(value)) / float(window)
        output[pos] = state

    return pd.Series(output, index=series.index, name=series.name, dtype=float)


__all__ = ["wilder_smooth"]
