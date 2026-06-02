from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from src.utils.column_selectors import resolve_single_column_selector


TSFRESH_ROLLING_CALCULATORS = (
    "sum_values",
    "median",
    "mean",
    "length",
    "standard_deviation",
    "variance",
    "root_mean_square",
    "maximum",
    "absolute_maximum",
    "minimum",
)


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


def compute_ratio_transform(
    numerator: pd.Series,
    denominator: pd.Series,
    *,
    eps: float = 1e-8,
) -> pd.Series:
    """
    Point-in-time safe ratio of two already-available feature columns.
    """
    if not isinstance(numerator, pd.Series):
        raise TypeError("numerator must be a pandas Series.")
    if not isinstance(denominator, pd.Series):
        raise TypeError("denominator must be a pandas Series.")
    denom = denominator.astype(float)
    out = numerator.astype(float) / denom.where(denom.abs() > float(eps), np.nan)
    out.name = numerator.name
    return out.astype("float32")


def compute_rolling_zscore_transform(
    series: pd.Series,
    *,
    window: int = 2520,
    shift: int = 1,
    ddof: int = 0,
) -> pd.Series:
    """
    Point-in-time safe rolling z-score via shifted rolling moments.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    if int(window) <= 1:
        raise ValueError("window must be > 1.")
    if int(shift) < 0:
        raise ValueError("shift must be >= 0.")

    base = series.astype(float)
    roll_mean = base.rolling(int(window), min_periods=int(window)).mean().shift(int(shift))
    roll_std = base.rolling(int(window), min_periods=int(window)).std(ddof=int(ddof)).shift(int(shift))
    out = (base - roll_mean) / roll_std.replace(0.0, np.nan)
    out.name = series.name
    return out.astype("float32")


def compute_tsfresh_rolling_transform(
    series: pd.Series,
    *,
    calculator: str,
    window: int = 48,
    shift: int = 0,
) -> pd.Series:
    """
    Reproduce a scalar tsfresh calculator over causal trailing windows.

    The tsfresh discovery workflow drops non-finite source values inside each otherwise-complete
    bar window before extraction. The rolling calculation mirrors that behavior while withholding
    output until a full trailing bar window is available.
    """
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    if int(window) <= 0:
        raise ValueError("window must be > 0.")
    if int(shift) < 0:
        raise ValueError("shift must be >= 0.")

    normalized_calculator = str(calculator).strip()
    if normalized_calculator not in TSFRESH_ROLLING_CALCULATORS:
        allowed = ", ".join(TSFRESH_ROLLING_CALCULATORS)
        raise ValueError(f"Unsupported tsfresh rolling calculator: {calculator!r}. Allowed: {allowed}.")

    source = pd.to_numeric(series, errors="coerce").astype(float)
    finite_source = source.where(np.isfinite(source), other=np.nan)
    rolling = finite_source.rolling(int(window), min_periods=1)
    if normalized_calculator == "sum_values":
        out = rolling.sum()
    elif normalized_calculator == "median":
        out = rolling.median()
    elif normalized_calculator == "mean":
        out = rolling.mean()
    elif normalized_calculator == "length":
        out = rolling.count().astype(float)
    elif normalized_calculator == "standard_deviation":
        out = rolling.std(ddof=0)
    elif normalized_calculator == "variance":
        out = rolling.var(ddof=0)
    elif normalized_calculator == "root_mean_square":
        out = finite_source.pow(2).rolling(int(window), min_periods=1).mean().pow(0.5)
    elif normalized_calculator == "maximum":
        out = rolling.max()
    elif normalized_calculator == "absolute_maximum":
        out = finite_source.abs().rolling(int(window), min_periods=1).max()
    else:
        out = rolling.min()

    complete_window = pd.Series(1.0, index=series.index).rolling(
        int(window),
        min_periods=int(window),
    ).count().eq(float(window))
    out = out.where(complete_window)
    if int(shift):
        out = out.shift(int(shift))
    out.name = f"{series.name}__{normalized_calculator}"
    return out


def add_tsfresh_rolling_transforms(
    df: pd.DataFrame,
    *,
    source_cols: Sequence[str],
    calculators: Sequence[str] = TSFRESH_ROLLING_CALCULATORS,
    window: int = 48,
    shift: int = 0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Add the scalar rolling tsfresh calculator family used by extrema discovery exports.
    """
    if not isinstance(source_cols, Sequence) or isinstance(source_cols, (str, bytes)) or not source_cols:
        raise ValueError("source_cols must be a non-empty sequence of column names.")
    if not isinstance(calculators, Sequence) or isinstance(calculators, (str, bytes)) or not calculators:
        raise ValueError("calculators must be a non-empty sequence of tsfresh calculator names.")

    out = df if inplace else df.copy()
    for source_col in source_cols:
        if not isinstance(source_col, str) or not source_col:
            raise ValueError("source_cols entries must be non-empty strings.")
        if source_col not in out.columns:
            raise KeyError(f"source_col '{source_col}' not found in DataFrame.")
        for calculator in calculators:
            transformed = compute_tsfresh_rolling_transform(
                out[source_col],
                calculator=str(calculator),
                window=int(window),
                shift=int(shift),
            )
            out[str(transformed.name)] = transformed
    return out


def _resolve_transform_column(
    df: pd.DataFrame,
    transform: dict[str, object],
    *,
    col_key: str,
    selector_key: str,
    field_prefix: str,
) -> str:
    raw_col = transform.get(col_key)
    raw_selector = transform.get(selector_key)
    has_col = raw_col is not None
    has_selector = raw_selector is not None
    if has_col == has_selector:
        raise ValueError(f"{field_prefix} must define exactly one of {col_key} or {selector_key}.")
    if has_col:
        if not isinstance(raw_col, str) or not raw_col:
            raise ValueError(f"{field_prefix}.{col_key} must be a non-empty string.")
        if raw_col not in df.columns:
            raise KeyError(f"{field_prefix}.{col_key} '{raw_col}' not found in DataFrame.")
        return raw_col
    return resolve_single_column_selector(
        [str(col) for col in df.columns],
        raw_selector,  # type: ignore[arg-type]
        field=f"{field_prefix}.{selector_key}",
    )


def add_feature_transforms(
    df: pd.DataFrame,
    *,
    transforms: Sequence[dict[str, object]],
) -> pd.DataFrame:
    """
    Add causal post-feature transforms declared from YAML.

    Supported transform kinds:
    - rolling_clip
    - ratio
    - rolling_zscore
    - tsfresh_rolling
    """
    if not isinstance(transforms, Sequence) or isinstance(transforms, (str, bytes)):
        raise TypeError("transforms must be a sequence of transform mappings.")

    out = df.copy()
    for idx, raw_transform in enumerate(transforms):
        if not isinstance(raw_transform, dict):
            raise TypeError(f"transforms[{idx}] must be a mapping.")
        kind = str(raw_transform.get("kind", ""))
        output_col = raw_transform.get("output_col")
        if kind != "tsfresh_rolling" and (not isinstance(output_col, str) or not output_col):
            raise ValueError(f"transforms[{idx}].output_col must be a non-empty string.")

        if kind == "tsfresh_rolling":
            source_col = _resolve_transform_column(
                out,
                raw_transform,
                col_key="source_col",
                selector_key="source_selector",
                field_prefix=f"transforms[{idx}]",
            )
            output_prefix = raw_transform.get("output_prefix", source_col)
            if not isinstance(output_prefix, str) or not output_prefix:
                raise ValueError(f"transforms[{idx}].output_prefix must be a non-empty string.")
            calculators = raw_transform.get("calculators", TSFRESH_ROLLING_CALCULATORS)
            generated = add_tsfresh_rolling_transforms(
                out[[source_col]],
                source_cols=[source_col],
                calculators=calculators,  # type: ignore[arg-type]
                window=int(raw_transform.get("window", 48)),
                shift=int(raw_transform.get("shift", 0)),
            )
            for calculator in calculators:  # type: ignore[union-attr]
                out[f"{output_prefix}__{calculator}"] = generated[f"{source_col}__{calculator}"]
        elif kind == "rolling_clip":
            source_col = _resolve_transform_column(
                out,
                raw_transform,
                col_key="source_col",
                selector_key="source_selector",
                field_prefix=f"transforms[{idx}]",
            )
            source = out[source_col].astype(float)
            out[output_col] = compute_rolling_clip_transform(
                source,
                window=int(raw_transform.get("window", 2520)),
                lower_q=float(raw_transform.get("lower_q", 0.01)),
                upper_q=float(raw_transform.get("upper_q", 0.99)),
                shift=int(raw_transform.get("shift", 1)),
            )
        elif kind == "ratio":
            numerator_col = _resolve_transform_column(
                out,
                raw_transform,
                col_key="numerator_col",
                selector_key="numerator_selector",
                field_prefix=f"transforms[{idx}]",
            )
            denominator_col = _resolve_transform_column(
                out,
                raw_transform,
                col_key="denominator_col",
                selector_key="denominator_selector",
                field_prefix=f"transforms[{idx}]",
            )
            out[output_col] = compute_ratio_transform(
                out[numerator_col],
                out[denominator_col],
                eps=float(raw_transform.get("eps", 1e-8)),
            )
        elif kind == "rolling_zscore":
            source_col = _resolve_transform_column(
                out,
                raw_transform,
                col_key="source_col",
                selector_key="source_selector",
                field_prefix=f"transforms[{idx}]",
            )
            source = out[source_col].astype(float)
            out[output_col] = compute_rolling_zscore_transform(
                source,
                window=int(raw_transform.get("window", 2520)),
                shift=int(raw_transform.get("shift", 1)),
                ddof=int(raw_transform.get("ddof", 0)),
            )
        else:
            raise ValueError(f"Unsupported feature transform kind: {kind}")

    return out


__all__ = [
    "TSFRESH_ROLLING_CALCULATORS",
    "add_feature_transforms",
    "add_tsfresh_rolling_transforms",
    "compute_rolling_clip_transform",
    "compute_ratio_transform",
    "compute_rolling_zscore_transform",
    "compute_tsfresh_rolling_transform",
]
