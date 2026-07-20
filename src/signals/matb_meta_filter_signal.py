from __future__ import annotations

import numpy as np
import pandas as pd

from src.signals._common import resolve_signal_output_name


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})


def matb_meta_filter_signal(
    df: pd.DataFrame,
    candidate_col: str = "matb_candidate",
    side_col: str = "matb_side",
    probability_col: str = "matb_pred_success_prob",
    expected_r_col: str = "matb_pred_ev_r",
    oos_col: str = "matb_pred_is_oos",
    minimum_probability: float = 0.55,
    minimum_expected_r: float = 0.10,
    signal_col: str | None = "signal_side",
    mode: str = "long_short",
) -> pd.Series:
    """
    Accept MATB candidates only with genuine OOS probability and EV evidence.

    YAML declaration::

        signals:
          kind: matb_meta_filter
          params:
            candidate_col: matb_candidate
            side_col: matb_side
            probability_col: matb_pred_success_prob
            expected_r_col: matb_pred_ev_r
            oos_col: matb_pred_is_oos
            minimum_probability: 0.55
            minimum_expected_r: 0.10

    Required input columns
    ----------------------
    candidate_col, side_col:
        Causal deterministic MATB event and its fixed direction.
    probability_col, expected_r_col, oos_col:
        Pooled model outputs. The OOS flag is mandatory and false rows remain flat.

    Parameters
    ----------
    minimum_probability:
        Minimum calibrated candidate-success probability in ``(0, 1)``.
    minimum_expected_r:
        Minimum fold-training-derived expected R.
    mode:
        One of ``long_only``, ``short_only`` or ``long_short``.
    """
    required = [candidate_col, side_col, probability_col, expected_r_col, oos_col]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"Missing required MATB meta-filter columns: {missing}")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {sorted(_ALLOWED_MODES)}.")
    probability_threshold = float(minimum_probability)
    expected_r_threshold = float(minimum_expected_r)
    if not np.isfinite(probability_threshold) or not 0.0 < probability_threshold < 1.0:
        raise ValueError("minimum_probability must be finite and in (0, 1).")
    if not np.isfinite(expected_r_threshold):
        raise ValueError("minimum_expected_r must be finite.")

    candidate = pd.to_numeric(df[candidate_col], errors="coerce").fillna(0.0).eq(1.0)
    side = np.sign(pd.to_numeric(df[side_col], errors="coerce").fillna(0.0)).astype(float)
    probability = pd.to_numeric(df[probability_col], errors="coerce").astype(float)
    expected_r = pd.to_numeric(df[expected_r_col], errors="coerce").astype(float)
    is_oos = df[oos_col].fillna(False).astype(bool)
    active = (
        candidate
        & side.ne(0.0)
        & is_oos
        & probability.notna()
        & expected_r.notna()
        & probability.ge(probability_threshold)
        & expected_r.ge(expected_r_threshold)
    )
    if mode == "long_only":
        active &= side.gt(0.0)
    elif mode == "short_only":
        active &= side.lt(0.0)

    signal = pd.Series(
        0.0,
        index=df.index,
        name=resolve_signal_output_name(signal_col=signal_col, default="signal_side"),
        dtype=float,
    )
    signal.loc[active] = side.loc[active]
    return signal


__all__ = ["matb_meta_filter_signal"]
