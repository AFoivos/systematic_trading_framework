from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from src.features.helpers import add_rolling_clip_transform, add_rolling_zscore_transform
from src.features.helpers.common import require_columns


ROLLING_STAT_MODES: tuple[str, ...] = (
    "absolute_maximum",
    "maximum",
    "mean",
    "minimum",
    "root_mean_square",
    "standard_deviation",
    "sum_values",
    "variance",
)

TSFRESH_ROLLING_CALCULATORS: tuple[str, ...] = (
    "absolute_maximum",
    "length",
    "maximum",
    "mean",
    "minimum",
    "root_mean_square",
    "standard_deviation",
    "sum_values",
    "variance",
)


def _clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)


def _resolve_mode(mode: str) -> str:
    aliases = {
        "abs_max": "absolute_maximum",
        "max": "maximum",
        "min": "minimum",
        "rms": "root_mean_square",
        "std": "standard_deviation",
        "sum": "sum_values",
        "var": "variance",
    }
    return aliases.get(str(mode).strip(), str(mode).strip())


def compute_rolling_stat_transform(
    series: pd.Series,
    *,
    mode: str = "root_mean_square",
    window: int = 48,
    shift: int = 0,
) -> pd.Series:
    """
    Deprecated dashboard compatibility helper.

    New YAML configs should use ``features[].transforms`` helpers such as
    ``rms``, ``rolling_mean``, ``rolling_std`` or ``rolling_sum`` instead of the
    old standalone ``feature_transforms`` step.
    """
    if isinstance(window, bool) or int(window) <= 1:
        raise ValueError("window must be > 1.")
    if isinstance(shift, bool) or int(shift) < 0:
        raise ValueError("shift must be >= 0.")
    source = _clean_numeric(series)
    rolling = source.shift(int(shift)).rolling(int(window), min_periods=int(window))
    resolved_mode = _resolve_mode(mode)
    if resolved_mode == "absolute_maximum":
        out = rolling.apply(lambda values: float(np.nanmax(np.abs(values))), raw=True)
    elif resolved_mode == "maximum":
        out = rolling.max()
    elif resolved_mode == "mean":
        out = rolling.mean()
    elif resolved_mode == "minimum":
        out = rolling.min()
    elif resolved_mode == "root_mean_square":
        out = rolling.apply(lambda values: float(np.sqrt(np.nanmean(np.square(values)))), raw=True)
    elif resolved_mode == "standard_deviation":
        out = rolling.std(ddof=0)
    elif resolved_mode == "sum_values":
        out = rolling.sum()
    elif resolved_mode == "variance":
        out = rolling.var(ddof=0)
    else:
        raise ValueError(f"Unsupported rolling_stat mode: {mode!r}.")
    out.name = f"{series.name}__{resolved_mode}"
    return out.astype("float32")


def compute_rolling_zscore_transform(
    series: pd.Series,
    *,
    window: int = 96,
    shift: int = 1,
    ddof: int = 0,
) -> pd.Series:
    """
    Deprecated dashboard compatibility helper for old ``feature_transforms``.
    """
    if isinstance(window, bool) or int(window) <= 1:
        raise ValueError("window must be > 1.")
    if isinstance(shift, bool) or int(shift) < 0:
        raise ValueError("shift must be >= 0.")
    source = _clean_numeric(series)
    stats_source = source.shift(int(shift))
    mean = stats_source.rolling(int(window), min_periods=int(window)).mean()
    std = stats_source.rolling(int(window), min_periods=int(window)).std(ddof=int(ddof))
    out = (source - mean) / std.replace(0.0, np.nan)
    out.name = f"{series.name}__zscore"
    return out.astype("float32")


def compute_tsfresh_rolling_transform(
    series: pd.Series,
    *,
    calculator: str = "mean",
    window: int = 48,
) -> pd.Series:
    """
    Deprecated dashboard compatibility helper for a small supported subset of
    old tsfresh-style rolling calculators.
    """
    resolved = _resolve_mode(calculator)
    if resolved == "length":
        source = _clean_numeric(series)
        out = source.rolling(int(window), min_periods=int(window)).count()
        out.name = f"{series.name}__length"
        return out.astype("float32")
    return compute_rolling_stat_transform(series, mode=resolved, window=window, shift=0).rename(
        f"{series.name}__{resolved}"
    )


def add_feature_transforms(
    df: pd.DataFrame,
    *,
    transforms: Iterable[dict[str, Any]],
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``feature_transforms`` dashboard compatibility transformation.

    This deprecated facade supports older dashboard requests that still submit
    ``feature_transforms`` as a feature step. It is intentionally not registered
    as a canonical feature; new YAML configs should use nested
    ``features[].transforms`` helpers.

    YAML declaration::

        features:
          - step: feature_transforms
            params:
              transforms:
                - kind: rolling_stat
                  source_col: close_logret
                  mode: root_mean_square
                  window: 48
                  shift: 0
                  output_col: close_logret__root_mean_square
            output_cols:
              - close_logret__root_mean_square

    Required input columns
    ----------------------
    source_col:
        Source dataframe column configured inside each transform mapping.

    Parameters
    ----------
    transforms:
        List of transform mappings. Supported ``kind`` values are
        ``rolling_stat``, ``rolling_zscore``, ``rolling_clip``, and
        ``tsfresh_rolling``.
    inplace:
        Boolean switch controlling optional feature behavior.
    """
    out = df if inplace else df.copy()
    for idx, transform in enumerate(transforms):
        if not isinstance(transform, dict):
            raise TypeError(f"transforms[{idx}] must be a mapping.")
        kind = str(transform.get("kind", ""))
        if kind == "rolling_stat":
            source_col = str(transform.get("source_col", ""))
            require_columns(out, [source_col], owner="feature_transforms rolling_stat")
            output_col = str(transform.get("output_col") or f"{source_col}__{_resolve_mode(str(transform.get('mode', 'root_mean_square')))}")
            out[output_col] = compute_rolling_stat_transform(
                out[source_col],
                mode=str(transform.get("mode", "root_mean_square")),
                window=int(transform.get("window", 48)),
                shift=int(transform.get("shift", 0)),
            )
        elif kind == "rolling_zscore":
            source_col = str(transform.get("source_col", ""))
            require_columns(out, [source_col], owner="feature_transforms rolling_zscore")
            out = add_rolling_zscore_transform(
                out,
                source_col=source_col,
                window=int(transform.get("window", 96)),
                shift=int(transform.get("shift", 1)),
                ddof=int(transform.get("ddof", 0)),
                output_col=transform.get("output_col") or f"{source_col}__zscore",
            )
        elif kind == "rolling_clip":
            source_col = str(transform.get("source_col", ""))
            require_columns(out, [source_col], owner="feature_transforms rolling_clip")
            out = add_rolling_clip_transform(
                out,
                source_col=source_col,
                window=int(transform.get("window", 96)),
                lower_q=float(transform.get("lower_q", 0.01)),
                upper_q=float(transform.get("upper_q", 0.99)),
                shift=int(transform.get("shift", 1)),
                output_col=transform.get("output_col") or f"{source_col}__rolling_clip",
            )
        elif kind == "tsfresh_rolling":
            source_col = str(transform.get("source_col", ""))
            require_columns(out, [source_col], owner="feature_transforms tsfresh_rolling")
            calculators = transform.get("calculators")
            if calculators is None:
                resolved_calculators: list[str] = list(TSFRESH_ROLLING_CALCULATORS)
            elif isinstance(calculators, (str, bytes)):
                resolved_calculators = [str(calculators)]
            else:
                resolved_calculators = [str(value) for value in calculators]
            output_prefix = str(transform.get("output_prefix") or source_col)
            for calculator in resolved_calculators:
                out[f"{output_prefix}__{calculator}"] = compute_tsfresh_rolling_transform(
                    out[source_col],
                    calculator=calculator,
                    window=int(transform.get("window", 48)),
                )
        else:
            raise ValueError(f"Unsupported feature transform kind: {kind!r}.")
    return out


__all__ = [
    "ROLLING_STAT_MODES",
    "TSFRESH_ROLLING_CALCULATORS",
    "add_feature_transforms",
    "compute_rolling_stat_transform",
    "compute_rolling_zscore_transform",
    "compute_tsfresh_rolling_transform",
]
