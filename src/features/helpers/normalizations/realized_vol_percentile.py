from __future__ import annotations

import pandas as pd

from .rolling_percent_rank import add_rolling_percent_rank_features


def add_realized_vol_percentile_features(
    df: pd.DataFrame,
    *,
    volatility_col: str,
    window: int = 252,
    min_periods: int | None = None,
    output_col: str | None = None,
    shift_window: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the ``realized_vol_percentile`` normalization helper transformation.
    """
    return add_rolling_percent_rank_features(
        df,
        source_col=volatility_col,
        window=window,
        min_periods=min_periods,
        output_col=output_col or f"{volatility_col}_percentile_{window}",
        shift_window=shift_window,
        inplace=inplace,
    )


__all__ = ["add_realized_vol_percentile_features"]
