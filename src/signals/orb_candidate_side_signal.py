from __future__ import annotations

import pandas as pd

from src.signals._common import resolve_signal_output_name


def orb_candidate_side_signal(
    df: pd.DataFrame,
    candidate_col: str = "orb_candidate",
    side_col: str = "orb_side",
    signal_col: str | None = "signal_orb_side",
) -> pd.Series:
    """
    Diagnostic ORB baseline: trade every nonzero candidate on its emitted side.

    This intentionally does not apply model probabilities, thresholds, or side flipping. It is
    useful as a raw candidate-side comparator against `meta_probability_side`.
    """
    if candidate_col not in df.columns:
        raise KeyError(f"candidate_col '{candidate_col}' not found in DataFrame")
    if side_col not in df.columns:
        raise KeyError(f"side_col '{side_col}' not found in DataFrame")

    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_orb_side",
    )
    candidate = df[candidate_col].astype(float).fillna(0.0).ne(0.0)
    side = df[side_col].astype(float).fillna(0.0)

    signal = pd.Series(0.0, index=df.index, name=output_col, dtype=float)
    signal.loc[candidate] = side.loc[candidate].astype(float)
    return signal.astype(float)


__all__ = ["orb_candidate_side_signal"]
