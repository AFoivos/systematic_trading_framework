from __future__ import annotations

import pandas as pd

from .returns import add_close_returns


def infer_returns_log_flag(column_name: str) -> bool | None:
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
