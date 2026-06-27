from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.helpers.common import output_column, positive_int, require_columns

from ._common import clean_numeric, optional_min_periods


def add_rolling_percent_rank_features(
    df: pd.DataFrame,
    *,
    source_col: str,
    window: int = 252,
    min_periods: int | None = None,
    output_col: str | None = None,
    shift_window: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``rolling_percent_rank`` normalization helper transformation.

    The default ranks ``source_col`` at ``t`` against the trailing window ending
    at ``t-1``. Set ``shift_window: false`` only for explicit diagnostic use
    where self-inclusion is intended.
    """
    require_columns(df, [source_col], owner="rolling percent-rank normalization")
    resolved_window = positive_int(window, field="window")
    if resolved_window <= 1:
        raise ValueError("window must be > 1.")
    resolved_min_periods = optional_min_periods(min_periods, window=resolved_window)

    out = df if inplace else df.copy()
    source = clean_numeric(out[source_col])
    col = output_column(output_col, default=f"{source_col}_percent_rank_{resolved_window}")
    if shift_window:
        values = source.to_numpy(dtype=float)
        ranks = np.full(values.shape[0], np.nan, dtype=float)
        for idx in range(values.shape[0]):
            start = max(0, idx - resolved_window)
            history = values[start:idx]
            history = history[np.isfinite(history)]
            current = values[idx]
            if history.size >= resolved_min_periods and np.isfinite(current):
                ranks[idx] = float((history <= current).sum() / history.size)
        out[col] = ranks.astype("float32")
    else:
        out[col] = (
            source.rolling(resolved_window, min_periods=resolved_min_periods)
            .apply(lambda values: pd.Series(values).rank(pct=True).iloc[-1], raw=False)
            .astype("float32")
        )
    return out


__all__ = ["add_rolling_percent_rank_features"]
