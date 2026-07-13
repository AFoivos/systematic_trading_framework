from __future__ import annotations

import math

import pandas as pd

from src.features.technical.extrema import (
    build_last_confirmed_extrema_context,
    confirm_extrema_without_lookahead,
    detect_local_extrema,
)


def swing_extrema_context(
    df: pd.DataFrame,
    *,
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
    normalizer_col: str | None = "mtf_1h_atr",
    normalizer_mode: str = "price",
    left_bars: int = 3,
    right_bars: int = 3,
    near_high_threshold_atr: float = 0.25,
    near_low_threshold_atr: float = 0.25,
    overextended_long_threshold_atr: float = 2.0,
    include_research_labels: bool = False,
    research_label_lead_bars: int = 3,
    prefix: str = "swing",
) -> pd.DataFrame:
    """
    Apply the registered ``swing_extrema_context`` feature transformation.

    Only confirmed extrema and context derived from those confirmed events are
    emitted. Raw extrema require ``right_bars`` future observations and remain
    internal to the confirmation calculation; they are never live/model
    feature outputs. A pivot at bar ``i`` first appears as confirmed at
    ``i + right_bars``.
    
    YAML declaration::
    
        features:
          - step: swing_extrema_context
            params:
              high_col: high
              low_col: low
              close_col: close
              normalizer_col: mtf_1h_atr
              normalizer_mode: price
              left_bars: 3
              right_bars: 3
              near_high_threshold_atr: 0.25
              near_low_threshold_atr: 0.25
              overextended_long_threshold_atr: 2.0
              prefix: swing
    
    Required input columns
    ----------------------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    normalizer_col:
        Input dataframe column configured by ``normalizer_col``. Default: ``mtf_1h_atr``.
    
    Parameters
    ----------
    high_col:
        Input dataframe column configured by ``high_col``. Default: ``high``.
    low_col:
        Input dataframe column configured by ``low_col``. Default: ``low``.
    close_col:
        Input dataframe column configured by ``close_col``. Default: ``close``.
    normalizer_col:
        Input dataframe column configured by ``normalizer_col``. Default: ``mtf_1h_atr``.
    normalizer_mode:
        Mode selector controlling how this feature is applied. Default: ``price``.
    left_bars:
        Configuration parameter accepted by this feature. Default: ``3``.
    right_bars:
        Configuration parameter accepted by this feature. Default: ``3``.
    near_high_threshold_atr:
        Numeric threshold used by this feature. Default: ``0.25``.
    near_low_threshold_atr:
        Numeric threshold used by this feature. Default: ``0.25``.
    overextended_long_threshold_atr:
        Numeric threshold used by this feature. Default: ``2.0``.
    prefix:
        Configuration parameter accepted by this feature. Default: ``swing``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    required = [high_col, low_col, close_col]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for swing_extrema_context: {missing}")

    for field_name, raw_value in (("left_bars", left_bars), ("right_bars", right_bars)):
        if isinstance(raw_value, bool) or not isinstance(raw_value, int) or int(raw_value) < 1:
            raise ValueError(f"{field_name} must be an integer >= 1.")

    for field_name, raw_value in (
        ("near_high_threshold_atr", near_high_threshold_atr),
        ("near_low_threshold_atr", near_low_threshold_atr),
        ("overextended_long_threshold_atr", overextended_long_threshold_atr),
    ):
        if not math.isfinite(float(raw_value)):
            raise ValueError(f"{field_name} must be finite.")

    if not isinstance(include_research_labels, bool):
        raise TypeError("include_research_labels must be boolean.")
    if include_research_labels:
        raise ValueError(
            "include_research_labels=True is not allowed in the live "
            "swing_extrema_context feature builder because pre_local_* labels "
            "contain future/research-only information and cannot be model features. "
            "Use make_pre_extrema_research_label explicitly in a research or target workflow."
        )
    if isinstance(research_label_lead_bars, bool) or not isinstance(research_label_lead_bars, int) or int(
        research_label_lead_bars
    ) < 1:
        raise ValueError("research_label_lead_bars must be an integer >= 1.")
    if not isinstance(prefix, str) or not prefix.strip():
        raise ValueError("prefix must be a non-empty string.")

    if normalizer_mode not in {"price", "return_vol"}:
        raise ValueError("normalizer_mode must be one of: 'price', 'return_vol'.")
    if normalizer_col is not None and normalizer_col not in df.columns:
        raise KeyError(
            f"normalizer_col '{normalizer_col}' not found in DataFrame. "
            "Provide an existing normalizer column or set normalizer_col=None."
        )

    out = df.copy()
    raw = detect_local_extrema(
        out,
        high_col=high_col,
        low_col=low_col,
        close_col=close_col,
        left_bars=int(left_bars),
        right_bars=int(right_bars),
        use_col_for_high=high_col,
        use_col_for_low=low_col,
        strict=True,
    )
    confirmed = confirm_extrema_without_lookahead(raw, right_bars=int(right_bars))

    context_input = out[[close_col]].copy()
    context_input = context_input.join(confirmed)
    context = build_last_confirmed_extrema_context(
        context_input if normalizer_col is None else context_input.join(out[[normalizer_col]]),
        confirmed_high_col="confirmed_local_high",
        confirmed_low_col="confirmed_local_low",
        confirmed_high_price_col="confirmed_local_high_price",
        confirmed_low_price_col="confirmed_local_low_price",
        close_col=close_col,
        normalizer_col=normalizer_col,
        normalizer_mode=normalizer_mode,
        near_high_threshold_atr=float(near_high_threshold_atr),
        near_low_threshold_atr=float(near_low_threshold_atr),
        overextended_long_threshold_atr=float(overextended_long_threshold_atr),
        prefix=prefix.strip(),
    )

    prefixed_confirmed = confirmed.rename(
        columns={col: f"{prefix.strip()}_{col}" for col in confirmed.columns}
    )

    out = out.join(prefixed_confirmed)
    out = out.join(context)

    return out


__all__ = ["swing_extrema_context"]
