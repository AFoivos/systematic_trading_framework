from __future__ import annotations

from collections.abc import Sequence
from numbers import Real

import numpy as np
import pandas as pd

from .helpers.common import positive_int, require_columns


def add_path_efficiency(
    df: pd.DataFrame, *, price_col: str = "close",
    windows: Sequence[int] = (24, 48, 96, 192), use_log_prices: bool = True,
    min_periods: int | None = None, eps: float = 1e-12,
    output_template: str = "eff_{window}", clip: bool = True,
    inplace: bool = False,
) -> pd.DataFrame:
    """Add causal price-path efficiency for arbitrary horizons.

    YAML declaration::

        features:
          - step: path_efficiency
            params:
              price_col: close
              windows: [24, 48, 96, 192]

    Required input columns
    ----------------------
    price_col:
        Positive prices in log mode, or finite numeric values in raw mode.

    Parameters
    ----------
    windows, min_periods:
        Each output compares t with t-window and divides by the trailing sum
        of absolute one-bar moves. No row after t is read. A zero path emits
        NaN; outputs are float32 and optionally clipped to [0, 1].
    """
    require_columns(df, [price_col], owner="path_efficiency")
    if isinstance(windows, (str, bytes)) or not isinstance(windows, Sequence) or not windows:
        raise ValueError("windows must be a non-empty sequence of positive integers.")
    resolved = tuple(positive_int(w, field="windows entry") for w in windows)
    if len(set(resolved)) != len(resolved):
        raise ValueError("windows must not contain duplicates.")
    if not isinstance(use_log_prices, bool) or not isinstance(clip, bool):
        raise ValueError("use_log_prices and clip must be boolean.")
    if isinstance(eps, bool) or not isinstance(eps, Real) or not np.isfinite(float(eps)) or float(eps) < 0:
        raise ValueError("eps must be a finite number >= 0.")
    if not isinstance(output_template, str) or "{window}" not in output_template:
        raise ValueError("output_template must be a string containing '{window}'.")
    if min_periods is not None:
        resolved_min = positive_int(min_periods, field="min_periods")
        if any(resolved_min > window for window in resolved):
            raise ValueError("min_periods must be <= every configured window.")
    else:
        resolved_min = None
    price = pd.to_numeric(df[price_col], errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)
    values = np.log(price.where(price > 0.0)) if use_log_prices else price
    steps = values.diff().abs()
    out = df if inplace else df.copy()
    for window in resolved:
        periods = window if resolved_min is None else resolved_min
        displacement = (values - values.shift(window)).abs()
        path = steps.rolling(window, min_periods=periods).sum()
        efficiency = displacement / path.where(path > float(eps))
        if clip:
            efficiency = efficiency.clip(0.0, 1.0)
        out[output_template.format(window=window)] = efficiency.astype("float32")
    return out


__all__ = ["add_path_efficiency"]
