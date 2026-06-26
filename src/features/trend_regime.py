from __future__ import annotations

from numbers import Integral

import numpy as np
import pandas as pd

from src.features.technical.trend_regime_feature import add_trend_regime_features


def add_trend_regime(
    df: pd.DataFrame,
    price_col: str = "close",
    fast_span: int = 20,
    slow_span: int = 50,
    neutral_threshold: float = 0.0,
    output_col: str | None = None,
    method: str = "ema",
    base_sma_for_sign: int | None = None,
    short_sma: int | None = None,
    long_sma: int | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``trend_regime`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: trend_regime
            params:
              price_col: close
              fast_span: 20
              slow_span: 50
              neutral_threshold: 0.0
              output_col: null
              method: ema
              base_sma_for_sign: null
              short_sma: null
              long_sma: null
          output_cols:
            - configured by output_col
    
    Required input columns
    ----------------------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    
    Parameters
    ----------
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``close``.
    fast_span:
        Configuration parameter accepted by this feature. Default: ``20``.
    slow_span:
        Configuration parameter accepted by this feature. Default: ``50``.
    neutral_threshold:
        Numeric threshold used by this feature. Default: ``0.0``.
    output_col:
        Output dataframe column configured by ``output_col``. Default: ``null``.
    method:
        Configuration parameter accepted by this feature. Default: ``ema``.
    base_sma_for_sign:
        Configuration parameter accepted by this feature. Default: ``null``.
    short_sma:
        Configuration parameter accepted by this feature. Default: ``null``.
    long_sma:
        Configuration parameter accepted by this feature. Default: ``null``.
    """
    if method == "ema" and any(value is not None for value in (base_sma_for_sign, short_sma, long_sma)):
        method = "sma_legacy"
    if method not in {"ema", "sma_legacy"}:
        raise ValueError("method must be one of: ema, sma_legacy.")
    if method == "sma_legacy":
        return add_trend_regime_features(
            df,
            price_col=price_col,
            base_sma_for_sign=50 if base_sma_for_sign is None else base_sma_for_sign,
            short_sma=20 if short_sma is None else short_sma,
            long_sma=50 if long_sma is None else long_sma,
            inplace=False,
        )

    _validate_columns(df, [price_col])
    _validate_window(fast_span, name="fast_span")
    _validate_window(slow_span, name="slow_span")
    if fast_span >= slow_span:
        raise ValueError("fast_span must be smaller than slow_span.")
    if float(neutral_threshold) < 0.0:
        raise ValueError("neutral_threshold must be non-negative.")
    col = _resolve_output_col(output_col, "trend_regime")

    out = df.copy()
    price = out[price_col].astype(float)
    fast = price.ewm(span=fast_span, adjust=False, min_periods=fast_span).mean()
    slow = price.ewm(span=slow_span, adjust=False, min_periods=slow_span).mean()
    spread = (fast - slow) / slow.replace(0.0, np.nan)

    regime = pd.Series(0.0, index=out.index, dtype="float64")
    ready = spread.notna()
    threshold = float(neutral_threshold)
    regime.loc[ready & (spread > threshold)] = 1.0
    regime.loc[ready & (spread < -threshold)] = -1.0
    regime.loc[~ready] = np.nan
    out[col] = regime
    return out


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for trend regime: {missing}")


def _validate_window(window: int, *, name: str) -> None:
    if isinstance(window, bool) or not isinstance(window, Integral) or window <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _resolve_output_col(output_col: str | None, default: str) -> str:
    if output_col is None:
        return default
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")
    return output_col


__all__ = [
    "add_trend_regime",
]
