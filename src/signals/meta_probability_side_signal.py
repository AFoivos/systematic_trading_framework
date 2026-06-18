from __future__ import annotations

import numpy as np
import pandas as pd

from src.signals._common import resolve_signal_output_name

_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})


def meta_probability_side_signal(
    df: pd.DataFrame,
    prob_col: str = "pred_prob",
    side_col: str = "primary_side",
    candidate_col: str | None = None,
    expected_value_col: str | None = None,
    signal_col: str | None = None,
    threshold: float | None = None,
    upper: float | None = None,
    min_expected_value_r: float | None = None,
    profit_barrier_r: float = 1.0,
    stop_barrier_r: float = 1.0,
    clip: float = 1.0,
    mode: str = "long_short",
) -> pd.Series:
    """
    Convert a meta-label success probability into same-side-only execution.

    pred_prob is interpreted as P(candidate succeeds), not P(price goes up). A high probability
    activates the configured side; a low probability stays flat and never flips to the opposite
    direction.

    YAML declaration::

        signals:
          kind: meta_probability_side
          params: {}
    """
    if prob_col not in df.columns:
        raise KeyError(f"prob_col '{prob_col}' not found in DataFrame")
    if side_col not in df.columns:
        raise KeyError(f"side_col '{side_col}' not found in DataFrame")
    if candidate_col is not None and candidate_col not in df.columns:
        raise KeyError(f"candidate_col '{candidate_col}' not found in DataFrame")
    if expected_value_col is not None and expected_value_col not in df.columns:
        raise KeyError(f"expected_value_col '{expected_value_col}' not found in DataFrame")
    if clip <= 0:
        raise ValueError("clip must be > 0.")
    if profit_barrier_r <= 0:
        raise ValueError("profit_barrier_r must be > 0.")
    if stop_barrier_r <= 0:
        raise ValueError("stop_barrier_r must be > 0.")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {sorted(_ALLOWED_MODES)}.")

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
    if mode == "long_only":
        candidate &= side.gt(0.0)
    elif mode == "short_only":
        candidate &= side.lt(0.0)
    active = probs.ge(activation_threshold) & candidate & probs.notna()
    if min_expected_value_r is not None:
        threshold_ev = float(min_expected_value_r)
        if expected_value_col is not None:
            expected_value = df[expected_value_col].astype(float)
        else:
            expected_value = (
                probs.astype(float) * float(profit_barrier_r)
                - (1.0 - probs.astype(float)) * float(stop_barrier_r)
            )
        active &= expected_value.ge(threshold_ev) & expected_value.notna()

    signal = pd.Series(0.0, index=df.index, name=output_col, dtype=float)
    signal.loc[active] = side.loc[active].astype(float) * float(clip)
    return signal.astype(float)


__all__ = ["meta_probability_side_signal"]
