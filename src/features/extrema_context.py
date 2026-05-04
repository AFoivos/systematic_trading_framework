from __future__ import annotations

import math

import pandas as pd

from src.features.technical.extrema import (
    build_last_confirmed_extrema_context,
    confirm_extrema_without_lookahead,
    detect_local_extrema,
    make_pre_extrema_research_label,
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
    Add live-safe swing/extrema context features from confirmed local highs/lows.

    Raw local extrema are also emitted for diagnostics, but they are future-looking and should be
    excluded from model feature columns.
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

    prefixed_raw = raw.rename(columns={col: f"{prefix.strip()}_{col}" for col in raw.columns})
    prefixed_confirmed = confirmed.rename(
        columns={col: f"{prefix.strip()}_{col}" for col in confirmed.columns}
    )

    out = out.join(prefixed_raw)
    out = out.join(prefixed_confirmed)
    out = out.join(context)

    if include_research_labels:
        out[make_pre_extrema_research_label(raw, lead_bars=int(research_label_lead_bars), kind="high").name] = (
            make_pre_extrema_research_label(
                raw,
                lead_bars=int(research_label_lead_bars),
                kind="high",
            )
        )
        out[make_pre_extrema_research_label(raw, lead_bars=int(research_label_lead_bars), kind="low").name] = (
            make_pre_extrema_research_label(
                raw,
                lead_bars=int(research_label_lead_bars),
                kind="low",
            )
        )

    return out


__all__ = ["swing_extrema_context"]
