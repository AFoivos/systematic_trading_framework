from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import require_columns


def add_return_features(
    df: pd.DataFrame,
    *,
    close_col: str = "close",
    windows: list[int] | tuple[int, ...] = (1, 4, 8, 20, 48),
    log_returns: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    require_columns(df, [close_col], owner="return normalization")
    out = df if inplace else df.copy()
    close = out[close_col].astype(float)

    for window in windows:
        if isinstance(window, bool) or int(window) <= 0:
            raise ValueError("Return windows must be positive integers.")
        resolved_window = int(window)
        out[f"return_{resolved_window}"] = close / close.shift(resolved_window) - 1.0
        if log_returns:
            out[f"log_return_{resolved_window}"] = np.log(close / close.shift(resolved_window))

    return out


__all__ = ["add_return_features"]
