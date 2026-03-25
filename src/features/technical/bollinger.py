from __future__ import annotations

import pandas as pd


def add_bollinger_features(
    df: pd.DataFrame,
    price_col: str = "close",
    window: int = 20,
    n_std: float = 2.0,
    inplace: bool = False,
) -> pd.DataFrame:
    if price_col not in df.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    out = df if inplace else df.copy()
    close = out[price_col].astype(float)
    return out.join(add_bollinger_bands(close, window=window, n_std=n_std))


def add_bollinger_bands(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.DataFrame:
    ma = close.rolling(window=window, min_periods=window).mean()
    sd = close.rolling(window=window, min_periods=window).std(ddof=0)
    upper = ma + n_std * sd
    lower = ma - n_std * sd
    band_width = (upper - lower) / ma
    percent_b = (close - lower) / (upper - lower)
    return pd.DataFrame(
        {
            f"bb_ma_{window}": ma,
            f"bb_upper_{window}_{n_std}": upper,
            f"bb_lower_{window}_{n_std}": lower,
            f"bb_width_{window}_{n_std}": band_width,
            f"bb_percent_b_{window}_{n_std}": percent_b,
        }
    )

__all__ = ["add_bollinger_bands", "add_bollinger_features"]
