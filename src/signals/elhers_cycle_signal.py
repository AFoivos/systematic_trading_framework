from __future__ import annotations

from typing import Any, Mapping
import pandas as pd

_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short", "long_short_hold"})


def compute_elhers_cycle_signal(
    df: pd.DataFrame,
    acp_col: str,
    acp_power_col: str,
    acp_sdv_col: str,
    roofing_filter_col: str,
    decycler_osc_col: str,
    rolling_r2_col: str,
    rolling_r2_slope_col: str,
    mode: str = "long_only",
    signal_col: str = "cycle_signal",
    rolling_r2_threshold: float = 0.0,
    rolling_r2_slope_threshold: float = 0.0,
    acp_threshold: float = 30.0,
    acp_power_threshold: float = 50.0,
    acp_sdv_threshold: float = 5.0,
    roofing_filter_threshold: float = 0.0,
    decycler_osc_threshold: float = 0.0
) -> pd.DataFrame:
    
    cols = [acp_col, acp_power_col, roofing_filter_col, acp_sdv_col, decycler_osc_col, rolling_r2_col, rolling_r2_slope_col]
    
    for col in cols:
        if col not in df.columns:
            raise ValueError(f"{col} not found in Dataframe")
    
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}")
    
    out = df.copy()
    out[signal_col] = 0.0
    
    long_mask = 