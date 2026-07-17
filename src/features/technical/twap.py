from __future__ import annotations

from typing import Sequence

import pandas as pd


def add_twap_features(
    df: pd.DataFrame,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    window: int = 20,
    windows: Sequence[int] | None = None,
    add_distance: bool = False,
    twap_col: str | None = None,
    distance_col: str | None = None,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``twap`` feature transformation.

    TWAP is the trailing arithmetic mean of each bar's typical price, so every
    bar receives equal weight. Inputs must already be available at the timestamp
    where the transform is evaluated.

    YAML declaration::

        features:
          - step: twap
            params:
              high_col: high
              low_col: low
              close_col: close
              window: 20
              windows: null
              add_distance: false
              twap_col: null
              distance_col: null
              inplace: false
            output_cols:
              - configured by twap_col
              - configured by distance_col

    Required input columns
    ----------------------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.

    Parameters
    ----------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    window:
        Trailing lookback controlling this feature. Default: ``20``.
    windows:
        Optional trailing lookbacks. When provided, overrides ``window``.
        Default: ``null``.
    add_distance:
        Deprecated derived-output switch. Use ``transforms.ratio`` instead.
        Default: ``false``.
    twap_col:
        Stable output column for a single window. Default: ``null``.
    distance_col:
        Deprecated derived-output column. Use ``transforms.ratio`` instead.
        Default: ``null``.
    inplace:
        Boolean switch controlling optional feature behavior. Default: ``false``.
    """
    missing = [column for column in (high_col, low_col, close_col) if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for TWAP features: {missing}")

    out = df if inplace else df.copy()
    high = out[high_col].astype(float)
    low = out[low_col].astype(float)
    close = out[close_col].astype(float)
    typical_price = (high + low + close) / 3.0
    typical_price.name = "typical_price"

    resolved_windows = _resolve_windows(window=window, windows=windows)
    _validate_stable_output_cols(
        resolved_windows=resolved_windows,
        add_distance=add_distance,
        twap_col=twap_col,
        distance_col=distance_col,
    )
    for resolved_window in resolved_windows:
        twap = compute_twap(typical_price, window=resolved_window)
        out[twap_col or f"twap_{resolved_window}"] = twap
    return out


def _validate_stable_output_cols(
    *,
    resolved_windows: Sequence[int],
    add_distance: bool,
    twap_col: str | None,
    distance_col: str | None,
) -> None:
    for field_name, value in (("twap_col", twap_col), ("distance_col", distance_col)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{field_name} must be a non-empty string when provided.")
    if twap_col is not None and twap_col == distance_col:
        raise ValueError("TWAP output columns must be unique.")
    if len(resolved_windows) != 1 and twap_col is not None:
        raise ValueError("Stable TWAP output columns require exactly one resolved window.")
    if add_distance or distance_col is not None:
        raise ValueError("TWAP distance outputs are no longer supported; use transforms.ratio helpers.")


def _resolve_windows(*, window: int, windows: Sequence[int] | None) -> list[int]:
    raw_windows = list(windows) if windows is not None else [window]
    resolved: list[int] = []
    for raw_window in raw_windows:
        if isinstance(raw_window, bool) or int(raw_window) <= 0:
            raise ValueError("TWAP windows must be positive integers.")
        value = int(raw_window)
        if value not in resolved:
            resolved.append(value)
    if not resolved:
        raise ValueError("TWAP windows must not be empty.")
    return resolved


def compute_twap(price: pd.Series, window: int = 20) -> pd.Series:
    """
    Compute the trailing time-weighted average price for equally spaced bars.

    Every observation in the trailing window receives equal weight, making this
    the arithmetic mean of the supplied bar-price series.

    YAML declaration::

        features:
          - step: compute_twap
            params:
              price: <required>
              window: 20

    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on a supplied Series directly.

    Parameters
    ----------
    price:
        Bar-price series to average.
    window:
        Trailing lookback controlling this feature. Default: ``20``.
    """
    if not isinstance(price, pd.Series):
        raise TypeError("price must be a pandas Series")
    if isinstance(window, bool) or int(window) <= 0:
        raise ValueError("TWAP window must be a positive integer.")

    resolved_window = int(window)
    twap = price.astype(float).rolling(window=resolved_window, min_periods=resolved_window).mean()
    twap.name = f"twap_{resolved_window}"
    return twap


__all__ = ["compute_twap", "add_twap_features"]
