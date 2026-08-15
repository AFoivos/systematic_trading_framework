from __future__ import annotations

import pandas as pd


def add_extrema_feature(
    df: pd.DataFrame,
    *,
    window: int = 24,
    high_col: str = "high",
    low_col: str = "low",
    price_col: str | None = None,
    output_col: str = "extrema",
    strict: bool = True,
) -> pd.DataFrame:
    """Add a causal rolling-extrema feature with values in ``{-1, 0, 1}``.

    This feature is intentionally different from ``swing_extrema_context``.
    It does not use a centered window, future bars, pivot confirmation, or a
    delayed marker. At bar ``t`` it compares the current observation only with
    the previous ``window`` bars:

    - ``+1``: current value is a new rolling maximum;
    - ``-1``: current value is a new rolling minimum;
    - ``0``: neither condition is true.

    When ``price_col`` is provided, the same series is used for maxima and
    minima. Otherwise ``high_col`` is used for maxima and ``low_col`` for
    minima. With OHLC inputs, a bar can theoretically make both a new rolling
    high and a new rolling low; such an ambiguous bar is encoded as ``0``.

    YAML declaration::

        features:
          - step: extrema
            params:
              window: 24
              price_col: close
              output_col: extrema
              strict: true

    Required input columns
    ----------------------
    price_col:
        The configured single price series when provided.
    high_col, low_col:
        Causal high/low series used when ``price_col`` is not provided.

    Parameters
    ----------
    df:
        Input dataframe.
    window:
        Number of *previous* bars used as the comparison window. Must be >= 1.
    high_col:
        Column used for rolling maxima when ``price_col`` is None.
    low_col:
        Column used for rolling minima when ``price_col`` is None.
    price_col:
        Optional single price series, e.g. ``close``. When set, ``high_col``
        and ``low_col`` are ignored.
    output_col:
        Name of the emitted int8 feature column.
    strict:
        If True, maxima/minima must be strictly greater/lower than every value
        in the previous window. If False, equality with the previous rolling
        max/min also counts.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    if isinstance(window, bool) or not isinstance(window, int) or int(window) < 1:
        raise ValueError("window must be an integer >= 1.")
    if not isinstance(strict, bool):
        raise TypeError("strict must be boolean.")
    if not isinstance(output_col, str) or not output_col.strip():
        raise ValueError("output_col must be a non-empty string.")

    if price_col is not None:
        if not isinstance(price_col, str) or not price_col.strip():
            raise ValueError("price_col must be None or a non-empty string.")
        required = [price_col]
        high_source_col = price_col
        low_source_col = price_col
    else:
        required = [high_col, low_col]
        high_source_col = high_col
        low_source_col = low_col

    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for extrema feature: {missing}")

    high = pd.to_numeric(df[high_source_col], errors="coerce").astype(float)
    low = pd.to_numeric(df[low_source_col], errors="coerce").astype(float)

    # Shift before rolling: the current bar is never part of its own benchmark.
    previous_max = high.shift(1).rolling(window=int(window), min_periods=int(window)).max()
    previous_min = low.shift(1).rolling(window=int(window), min_periods=int(window)).min()

    if strict:
        is_max = high.gt(previous_max)
        is_min = low.lt(previous_min)
    else:
        is_max = high.ge(previous_max)
        is_min = low.le(previous_min)

    is_max = is_max & high.notna() & previous_max.notna()
    is_min = is_min & low.notna() & previous_min.notna()

    values = pd.Series(0, index=df.index, dtype="int8")
    values.loc[is_max & ~is_min] = 1
    values.loc[is_min & ~is_max] = -1

    out = df.copy()
    out[output_col.strip()] = values
    return out


__all__ = ["add_extrema_feature"]
