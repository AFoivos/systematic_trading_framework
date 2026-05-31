from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.targets.output_aliases import apply_target_output_aliases


def _numeric_stats(values: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    if numeric.empty:
        return {
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
    return {
        "rows": int(len(numeric)),
        "mean": float(numeric.mean()),
        "std": float(numeric.std(ddof=1)) if len(numeric) >= 2 else 0.0,
        "min": float(numeric.min()),
        "max": float(numeric.max()),
        "median": float(numeric.median()),
        "q01": float(numeric.quantile(0.01)),
        "q05": float(numeric.quantile(0.05)),
        "q25": float(numeric.quantile(0.25)),
        "q75": float(numeric.quantile(0.75)),
        "q95": float(numeric.quantile(0.95)),
        "q99": float(numeric.quantile(0.99)),
        "skew": float(numeric.skew()) if len(numeric) >= 3 else 0.0,
        "kurtosis": float(numeric.kurtosis()) if len(numeric) >= 4 else 0.0,
    }


def _build_future_return(
    out: pd.DataFrame,
    *,
    price_col: str,
    returns_col: str | None,
    returns_type: str,
    horizon: int,
) -> pd.Series:
    if returns_col is not None:
        if returns_col not in out.columns:
            raise KeyError(f"returns_col '{returns_col}' not found in DataFrame")
        future_returns = pd.concat(
            [
                out[returns_col].astype(float).shift(-step).rename(f"step_{step}")
                for step in range(1, horizon + 1)
            ],
            axis=1,
        )
        valid_mask = future_returns.notna().all(axis=1)
        future = pd.Series(np.nan, index=out.index, dtype=float)
        if bool(valid_mask.any()):
            if returns_type == "log":
                values = future_returns.loc[valid_mask].sum(axis=1)
            else:
                values = (1.0 + future_returns.loc[valid_mask]).prod(axis=1) - 1.0
            future.loc[valid_mask] = values.astype(float)
        return future

    if price_col not in out.columns:
        raise KeyError(f"price_col '{price_col}' not found in DataFrame")
    return out[price_col].astype(float).pct_change(periods=horizon).shift(-horizon)


def build_future_return_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Build a dense all-bar continuous future-return target for regression forecasters.

    The target intentionally uses future bars only in the target column. Feature selection later
    excludes every emitted target column, so the model can learn from current/past features while
    being evaluated against the configured forward horizon.
    """
    cfg = apply_target_output_aliases(target_cfg)
    price_col = str(cfg.get("price_col", "close"))
    returns_col_raw = cfg.get("returns_col")
    returns_col = str(returns_col_raw) if returns_col_raw is not None else None
    returns_type = str(cfg.get("returns_type", "simple"))
    if returns_type not in {"simple", "log"}:
        raise ValueError("target.returns_type must be 'simple' or 'log'.")
    if returns_col is None and returns_type != "simple":
        raise ValueError("target.returns_type='log' requires target.returns_col.")

    horizon = int(cfg.get("horizon_bars", cfg.get("horizon", 1)))
    if horizon <= 0:
        raise ValueError("target.horizon_bars must be a positive integer.")

    normalize_by_volatility = bool(cfg.get("normalize_by_volatility", False))
    volatility_col = str(cfg.get("volatility_col", "atr_14"))
    volatility_floor = float(cfg.get("volatility_floor", 1e-12))
    if volatility_floor <= 0.0:
        raise ValueError("target.volatility_floor must be > 0.")

    raw_fwd_col = str(cfg.get("raw_fwd_col", f"target_future_return_raw_{horizon}"))
    fwd_col = str(cfg.get("fwd_col", cfg.get("target_col", f"target_future_return_{horizon}")))
    label_col = str(cfg.get("label_col", fwd_col))
    clip = cfg.get("clip")

    out = df.copy()
    raw_future = _build_future_return(
        out,
        price_col=price_col,
        returns_col=returns_col,
        returns_type=returns_type,
        horizon=horizon,
    )
    out[raw_fwd_col] = raw_future.astype(float)

    target = raw_future.astype(float)
    normalizer_col: str | None = None
    if normalize_by_volatility:
        if volatility_col not in out.columns:
            raise KeyError(f"volatility_col '{volatility_col}' not found in DataFrame")
        if price_col not in out.columns:
            raise KeyError(f"price_col '{price_col}' not found in DataFrame")
        normalizer_col = str(cfg.get("normalizer_col", f"{volatility_col}_over_{price_col}"))
        normalizer = out[volatility_col].astype(float) / out[price_col].astype(float).abs()
        normalizer = normalizer.where(np.isfinite(normalizer) & (normalizer > volatility_floor))
        out[normalizer_col] = normalizer.astype(float)
        target = target / normalizer

    if clip is not None:
        if not isinstance(clip, (list, tuple)) or len(clip) != 2:
            raise ValueError("target.clip must be a [low, high] pair when provided.")
        clip_low, clip_high = float(clip[0]), float(clip[1])
        if not clip_low < clip_high:
            raise ValueError("target.clip must satisfy low < high.")
        target = target.clip(lower=clip_low, upper=clip_high)
    else:
        clip_low = clip_high = None

    out[fwd_col] = target.astype(float)
    if label_col != fwd_col:
        out[label_col] = out[fwd_col]

    valid_mask = out[fwd_col].notna()
    output_cols = {raw_fwd_col, fwd_col, label_col}
    if normalizer_col is not None:
        output_cols.add(normalizer_col)
    meta = {
        "kind": "future_return_regression",
        "price_col": price_col,
        "returns_col": returns_col,
        "returns_type": returns_type,
        "horizon": horizon,
        "horizon_bars": horizon,
        "fwd_col": fwd_col,
        "label_col": label_col,
        "raw_fwd_col": raw_fwd_col,
        "normalize_by_volatility": normalize_by_volatility,
        "volatility_col": volatility_col if normalize_by_volatility else None,
        "normalizer_col": normalizer_col,
        "clip": [clip_low, clip_high] if clip is not None else None,
        "labeled_rows": int(valid_mask.sum()),
        "unavailable_tail_count": int(len(out) - int(valid_mask.sum())),
        "target_density": float(valid_mask.mean()) if len(out) else 0.0,
        "target_stats": _numeric_stats(out.loc[valid_mask, fwd_col]),
        "raw_future_return_stats": _numeric_stats(out.loc[out[raw_fwd_col].notna(), raw_fwd_col]),
        "output_cols": sorted(str(col) for col in output_cols),
    }
    return out, label_col, fwd_col, meta


__all__ = ["build_future_return_regression_target"]
