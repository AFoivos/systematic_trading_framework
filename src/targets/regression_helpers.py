from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd


def flatten_target_cfg(target_cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(target_cfg or {})
    params = cfg.pop("params", None)
    if params is not None:
        if not isinstance(params, dict):
            raise ValueError("target.params must be a mapping when provided.")
        cfg.update(dict(params))
    return cfg


def require_columns(df: pd.DataFrame, columns: Iterable[str], *, context: str = "target") -> None:
    missing = [str(col) for col in columns if str(col) not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for {context}: {missing}")


def require_positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer.")
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{field} must be a positive integer.")
    if out <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return out


def require_min_int(value: Any, *, field: str, minimum: int) -> int:
    out = require_positive_int(value, field=field)
    if out < int(minimum):
        raise ValueError(f"{field} must be >= {int(minimum)}.")
    return out


def require_finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number.")
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number.") from exc
    if not np.isfinite(out):
        raise ValueError(f"{field} must be a finite number.")
    return out


def validate_returns_type(value: Any) -> str:
    returns_type = str(value)
    if returns_type not in {"simple", "log"}:
        raise ValueError("target.returns_type must be 'simple' or 'log'.")
    return returns_type


def validate_choice(value: Any, *, field: str, choices: set[str]) -> str:
    out = str(value)
    if out not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"{field} must be one of: {allowed}.")
    return out


def validate_clip(clip: Any) -> tuple[float, float] | None:
    if clip is None:
        return None
    if not isinstance(clip, (list, tuple)) or len(clip) != 2:
        raise ValueError("target.clip must be a [low, high] pair when provided.")
    low = require_finite_number(clip[0], field="target.clip[0]")
    high = require_finite_number(clip[1], field="target.clip[1]")
    if not low < high:
        raise ValueError("target.clip must satisfy low < high.")
    return low, high


def numeric_stats(values: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    empty = {
        "rows": 0,
        "mean": None,
        "std": None,
        "min": None,
        "max": None,
        "median": None,
        "q01": None,
        "q05": None,
        "q25": None,
        "q75": None,
        "q95": None,
        "q99": None,
        "skew": None,
        "kurtosis": None,
    }
    if numeric.empty:
        return empty

    def finite_or_none(value: Any) -> float | None:
        out = float(value)
        return out if np.isfinite(out) else None

    return {
        "rows": int(len(numeric)),
        "mean": finite_or_none(numeric.mean()),
        "std": finite_or_none(numeric.std(ddof=1)) if len(numeric) >= 2 else 0.0,
        "min": finite_or_none(numeric.min()),
        "max": finite_or_none(numeric.max()),
        "median": finite_or_none(numeric.median()),
        "q01": finite_or_none(numeric.quantile(0.01)),
        "q05": finite_or_none(numeric.quantile(0.05)),
        "q25": finite_or_none(numeric.quantile(0.25)),
        "q75": finite_or_none(numeric.quantile(0.75)),
        "q95": finite_or_none(numeric.quantile(0.95)),
        "q99": finite_or_none(numeric.quantile(0.99)),
        "skew": finite_or_none(numeric.skew()) if len(numeric) >= 3 else 0.0,
        "kurtosis": finite_or_none(numeric.kurtosis()) if len(numeric) >= 4 else 0.0,
    }


def as_float_series(df: pd.DataFrame, col: str) -> pd.Series:
    require_columns(df, [col])
    return pd.to_numeric(df[col], errors="coerce").astype(float)


def future_window(values: pd.Series, horizon: int, *, prefix: str = "step") -> pd.DataFrame:
    return pd.concat(
        [values.astype(float).shift(-step).rename(f"{prefix}_{step}") for step in range(1, horizon + 1)],
        axis=1,
    )


def build_return_series(
    df: pd.DataFrame,
    *,
    price_col: str,
    returns_col: str | None,
    returns_type: str,
) -> pd.Series:
    if returns_col is not None:
        return as_float_series(df, returns_col)
    price = as_float_series(df, price_col)
    if returns_type == "log":
        return np.log(price / price.shift(1)).astype(float)
    return price.pct_change().astype(float)


def build_future_return(
    df: pd.DataFrame,
    *,
    price_col: str,
    returns_col: str | None,
    returns_type: str,
    horizon: int,
) -> pd.Series:
    if returns_col is not None:
        returns = as_float_series(df, returns_col)
        steps = future_window(returns, horizon)
        valid = steps.notna().all(axis=1)
        out = pd.Series(np.nan, index=df.index, dtype=float)
        if bool(valid.any()):
            if returns_type == "log":
                values = steps.loc[valid].sum(axis=1)
            else:
                values = (1.0 + steps.loc[valid]).prod(axis=1) - 1.0
            out.loc[valid] = values.astype(float)
        return out

    price = as_float_series(df, price_col)
    future_price = price.shift(-horizon)
    valid = price.notna() & future_price.notna() & (price != 0.0)
    out = pd.Series(np.nan, index=df.index, dtype=float)
    if returns_type == "log":
        valid = valid & (price > 0.0) & (future_price > 0.0)
        out.loc[valid] = np.log(future_price.loc[valid] / price.loc[valid]).astype(float)
    else:
        out.loc[valid] = (future_price.loc[valid] / price.loc[valid] - 1.0).astype(float)
    return out


def build_future_realized_volatility(
    df: pd.DataFrame,
    *,
    price_col: str,
    returns_col: str | None,
    returns_type: str,
    horizon: int,
    annualize: bool = False,
    periods_per_year: float | None = None,
) -> pd.Series:
    returns = build_return_series(
        df,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
    )
    steps = future_window(returns, horizon)
    valid = steps.notna().all(axis=1)
    out = pd.Series(np.nan, index=df.index, dtype=float)
    if bool(valid.any()):
        values = steps.loc[valid].std(axis=1, ddof=0).astype(float)
        if annualize:
            if periods_per_year is None:
                raise ValueError("target.periods_per_year is required when annualize=true.")
            ppy = require_finite_number(periods_per_year, field="target.periods_per_year")
            if ppy <= 0.0:
                raise ValueError("target.periods_per_year must be > 0.")
            values = values * float(np.sqrt(ppy))
        out.loc[valid] = values
    return out


def volatility_normalizer(
    df: pd.DataFrame,
    *,
    price_col: str,
    volatility_col: str,
    volatility_floor: float,
) -> pd.Series:
    if volatility_floor <= 0.0:
        raise ValueError("target.volatility_floor must be > 0.")
    require_columns(df, [price_col, volatility_col])
    price = as_float_series(df, price_col).abs()
    volatility = as_float_series(df, volatility_col)
    normalizer = volatility / price
    return normalizer.where(np.isfinite(normalizer) & (normalizer > volatility_floor)).astype(float)


def positive_denominator(values: pd.Series, *, floor: float, field: str) -> pd.Series:
    if floor <= 0.0:
        raise ValueError(f"{field} must be > 0.")
    denom = pd.to_numeric(values, errors="coerce").astype(float)
    return denom.where(np.isfinite(denom) & (denom > floor)).astype(float)


def finalize_regression_target(
    out: pd.DataFrame,
    *,
    target: pd.Series,
    kind: str,
    price_col: str,
    horizon: int,
    fwd_col: str,
    label_col: str,
    clip: Any,
    intermediate_cols: Iterable[str] = (),
    meta_extra: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    clip_pair = validate_clip(clip)
    target_out = target.astype(float)
    if clip_pair is not None:
        target_out = target_out.clip(lower=clip_pair[0], upper=clip_pair[1])

    out[fwd_col] = target_out.astype(float)
    if label_col != fwd_col:
        out[label_col] = out[fwd_col]

    valid_mask = out[fwd_col].notna()
    output_cols = {str(fwd_col), str(label_col), *(str(col) for col in intermediate_cols if col)}
    meta = {
        "kind": kind,
        "price_col": price_col,
        "horizon": horizon,
        "horizon_bars": horizon,
        "fwd_col": fwd_col,
        "label_col": label_col,
        "clip": list(clip_pair) if clip_pair is not None else None,
        "labeled_rows": int(valid_mask.sum()),
        "target_density": float(valid_mask.mean()) if len(out) else 0.0,
        "target_stats": numeric_stats(out.loc[valid_mask, fwd_col]),
        "output_cols": sorted(output_cols),
    }
    if meta_extra:
        meta.update(meta_extra)
    return out, label_col, fwd_col, meta


__all__ = [
    "as_float_series",
    "build_future_realized_volatility",
    "build_future_return",
    "build_return_series",
    "finalize_regression_target",
    "flatten_target_cfg",
    "future_window",
    "numeric_stats",
    "positive_denominator",
    "require_columns",
    "require_finite_number",
    "require_min_int",
    "require_positive_int",
    "validate_choice",
    "validate_clip",
    "validate_returns_type",
    "volatility_normalizer",
]
