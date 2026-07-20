from __future__ import annotations

import numpy as np
import pandas as pd

from src.signals._common import resolve_signal_output_name


_ALLOWED_MODES = frozenset({"long_only", "short_only", "long_short"})


def matb_candidate_signal(
    df: pd.DataFrame,
    candidate_col: str = "matb_candidate",
    side_col: str = "matb_side",
    signal_col: str | None = "signal_side",
    mode: str = "long_short",
) -> pd.Series:
    """
    Convert deterministic MATB candidate events to a stateless trade side.

    YAML declaration::

        signals:
          kind: matb_candidate
          params:
            candidate_col: matb_candidate
            side_col: matb_side
            signal_col: signal_side
            mode: long_short

    Required input columns
    ----------------------
    candidate_col:
        Deterministic MATB event flag.
    side_col:
        Event side encoded as ``+1`` long, ``-1`` short and ``0`` otherwise.

    Parameters
    ----------
    mode:
        One of ``long_only``, ``short_only`` or ``long_short``.
    signal_col:
        Output Series name. Default: ``signal_side``.
    """
    missing = [column for column in (candidate_col, side_col) if column not in df.columns]
    if missing:
        raise KeyError(f"Missing required MATB candidate signal columns: {missing}")
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {sorted(_ALLOWED_MODES)}.")

    candidate = pd.to_numeric(df[candidate_col], errors="coerce").fillna(0.0).eq(1.0)
    side = np.sign(pd.to_numeric(df[side_col], errors="coerce").fillna(0.0)).astype(float)
    active = candidate & side.ne(0.0)
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


__all__ = ["matb_candidate_signal"]
