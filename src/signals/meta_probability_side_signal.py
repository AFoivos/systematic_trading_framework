from __future__ import annotations

import numpy as np
import pandas as pd

from src.signals._common import resolve_signal_output_name


def meta_probability_side_signal(
    df: pd.DataFrame,
    prob_col: str = "pred_prob",
    side_col: str = "primary_side",
    candidate_col: str | None = None,
    signal_col: str | None = None,
    threshold: float | None = None,
    upper: float | None = None,
    clip: float = 1.0,
) -> pd.Series:
    """
    Convert a meta-label success probability into same-side-only execution.

    pred_prob is interpreted as P(candidate succeeds), not P(price goes up). A high probability
    activates the configured side; a low probability stays flat and never flips to the opposite
    direction.
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    if side_col not in df.columns:
        raise KeyError(f"side_col '{side_col}' not found in DataFrame")
    if candidate_col is not None and candidate_col not in df.columns:
        raise KeyError(f"candidate_col '{candidate_col}' not found in DataFrame")
    if clip <= 0:
        raise ValueError("clip must be > 0.")

    activation_threshold = float(threshold if threshold is not None else (upper if upper is not None else 0.5))
    if not 0.0 < activation_threshold < 1.0:
        raise ValueError("threshold must be in (0, 1).")

    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default="signal_meta_side",
    )
    probs = df[prob_col].astype(float).clip(lower=0.0, upper=1.0)
    side = np.sign(df[side_col].astype(float).fillna(0.0).clip(lower=-1.0, upper=1.0))
    candidate = side.ne(0.0)
    if candidate_col is not None:
        candidate &= df[candidate_col].astype(float).fillna(0.0).ne(0.0)
    active = probs.ge(activation_threshold) & candidate & probs.notna()

    signal = pd.Series(0.0, index=df.index, name=output_col, dtype=float)
    signal.loc[active] = side.loc[active].astype(float) * float(clip)
    return signal.astype(float)


__all__ = ["meta_probability_side_signal"]
