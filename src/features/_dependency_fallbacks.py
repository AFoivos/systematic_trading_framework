from __future__ import annotations

import pandas as pd

from .helpers.normalizations.returns import add_close_returns


def infer_returns_log_flag(column_name: str) -> bool | None:
    """
    Apply the registered ``infer_returns_log_flag`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: infer_returns_log_flag
            params:
              column_name: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    column_name:
        Configuration parameter accepted by this feature.
    """
    normalized = str(column_name).strip()
    if normalized.endswith("_logret"):
        return True
    if normalized.endswith("_ret"):
        return False
    return None


def ensure_close_based_returns(
    df: pd.DataFrame,
    *,
    returns_col: str,
) -> pd.DataFrame:
    """
    Apply the registered ``ensure_close_based_returns`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: ensure_close_based_returns
            params:
              returns_col: <required>
    
    Required input columns
    ----------------------
    returns_col:
        Input dataframe column configured by ``returns_col``.
    
    Parameters
    ----------
    returns_col:
        Input dataframe column configured by ``returns_col``.
    """
    if returns_col in df.columns:
        return df
    if "close" not in df.columns:
        raise KeyError(
            f"returns_col '{returns_col}' not found in DataFrame and auto-compute requires a 'close' column."
        )

    log_flag = infer_returns_log_flag(returns_col)
    if log_flag is None:
        raise KeyError(
            f"returns_col '{returns_col}' not found in DataFrame. "
            "Auto-compute only supports close-based names ending in '_ret' or '_logret'."
        )
    return add_close_returns(df, log=log_flag, col_name=returns_col)


__all__ = ["ensure_close_based_returns", "infer_returns_log_flag"]
