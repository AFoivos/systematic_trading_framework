from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def _validate_probability(value: float, *, field: str) -> float:
    out = float(value)
    if not 0.0 <= out <= 1.0:
        raise ValueError(f"{field} must be in [0, 1].")
    return out


def compute_rolling_clip_transform(
    series: pd.Series,
    *,
    window: int = 2520,
    lower_q: float = 0.01,
    upper_q: float = 0.99,
    shift: int = 1,
) -> pd.Series:
    """
    Point-in-time safe rolling winsorization via shifted rolling quantile bounds.

    The bounds are estimated on past values only and shifted forward so the current bar never
    contributes to its own clipping thresholds.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    if int(window) <= 1:
        raise ValueError("window must be > 1.")
    if int(shift) < 0:
        raise ValueError("shift must be >= 0.")

    q_low = _validate_probability(lower_q, field="lower_q")
    q_high = _validate_probability(upper_q, field="upper_q")
    if not q_low < q_high:
        raise ValueError("lower_q must be < upper_q.")

    lower = series.rolling(int(window), min_periods=int(window)).quantile(q_low).shift(int(shift))
    upper = series.rolling(int(window), min_periods=int(window)).quantile(q_high).shift(int(shift))
    valid_bounds = lower.notna() & upper.notna()

    out = pd.Series(np.nan, index=series.index, dtype="float32")
    if bool(valid_bounds.any()):
        out.loc[valid_bounds] = np.minimum(
            np.maximum(series.loc[valid_bounds].astype(float), lower.loc[valid_bounds].astype(float)),
            upper.loc[valid_bounds].astype(float),
        ).astype("float32")
    return out


def add_feature_transforms(
    df: pd.DataFrame,
    *,
    transforms: Sequence[dict[str, object]],
) -> pd.DataFrame:
    """
    Add causal post-feature transforms declared from YAML.

    Supported transform kinds:
    - rolling_clip
    """
    if not isinstance(transforms, Sequence) or isinstance(transforms, (str, bytes)):
        raise TypeError("transforms must be a sequence of transform mappings.")

    out = df.copy()
    for idx, raw_transform in enumerate(transforms):
        if not isinstance(raw_transform, dict):
            raise TypeError(f"transforms[{idx}] must be a mapping.")
        kind = str(raw_transform.get("kind", ""))
        source_col = raw_transform.get("source_col")
        output_col = raw_transform.get("output_col")
        if not isinstance(source_col, str) or not source_col:
            raise ValueError(f"transforms[{idx}].source_col must be a non-empty string.")
        if source_col not in out.columns:
            raise KeyError(f"transforms[{idx}].source_col '{source_col}' not found in DataFrame.")
        if not isinstance(output_col, str) or not output_col:
            raise ValueError(f"transforms[{idx}].output_col must be a non-empty string.")

        source = out[source_col].astype(float)
        if kind == "rolling_clip":
            out[output_col] = compute_rolling_clip_transform(
                source,
                window=int(raw_transform.get("window", 2520)),
                lower_q=float(raw_transform.get("lower_q", 0.01)),
                upper_q=float(raw_transform.get("upper_q", 0.99)),
                shift=int(raw_transform.get("shift", 1)),
            )
        else:
            raise ValueError(f"Unsupported feature transform kind: {kind}")

    return out


__all__ = [
    "add_feature_transforms",
    "compute_rolling_clip_transform",
]
