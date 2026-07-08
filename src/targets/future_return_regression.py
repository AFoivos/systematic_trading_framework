from __future__ import annotations

from typing import Any

import pandas as pd

from src.targets.output_aliases import apply_target_output_aliases
from src.targets.regression_helpers import (
    build_future_return,
    flatten_target_cfg,
    numeric_stats,
    validate_clip,
    volatility_normalizer,
)


def build_future_return_regression_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    """
    Apply the registered ``future_return_regression`` target transformation.
    
    This target uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        target:
          kind: future_return_regression
          params:
            clip: <configured>
            fwd_col: <configured>
            horizon: <configured>
            horizon_bars: <configured>
            label_col: <configured>
            normalize_by_volatility: <configured>
            normalizer_col: <configured>
            price_col: <configured>
            raw_fwd_col: <configured>
            returns_col: <configured>
            returns_type: <configured>
            target_col: <configured>
            volatility_col: <configured>
            volatility_floor: <configured>
          outputs:
            - configured by label_col
    
    Required input columns
    ----------------------
    fwd_col:
        Input dataframe column configured by ``fwd_col``. Default: ``<configured>``.
    normalizer_col:
        Input dataframe column configured by ``normalizer_col``. Default: ``<configured>``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``<configured>``.
    raw_fwd_col:
        Input dataframe column configured by ``raw_fwd_col``. Default: ``<configured>``.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``<configured>``.
    target_col:
        Input dataframe column configured by ``target_col``. Default: ``<configured>``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``<configured>``.
    
    Parameters
    ----------
    clip:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    fwd_col:
        Input dataframe column configured by ``fwd_col``. Default: ``<configured>``.
    horizon:
        Trailing lookback or forecast horizon controlling this target. Default: ``<configured>``.
    horizon_bars:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    label_col:
        Output dataframe column configured by ``label_col``. Default: ``<configured>``.
    normalize_by_volatility:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    normalizer_col:
        Input dataframe column configured by ``normalizer_col``. Default: ``<configured>``.
    price_col:
        Input dataframe column configured by ``price_col``. Default: ``<configured>``.
    raw_fwd_col:
        Input dataframe column configured by ``raw_fwd_col``. Default: ``<configured>``.
    returns_col:
        Input dataframe column configured by ``returns_col``. Default: ``<configured>``.
    returns_type:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    target_col:
        Input dataframe column configured by ``target_col``. Default: ``<configured>``.
    volatility_col:
        Input dataframe column configured by ``volatility_col``. Default: ``<configured>``.
    volatility_floor:
        Configuration parameter accepted by this target. Default: ``<configured>``.
    """
    cfg = apply_target_output_aliases(flatten_target_cfg(target_cfg))
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
    raw_future = build_future_return(
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
        normalizer = volatility_normalizer(
            out,
            price_col=price_col,
            volatility_col=volatility_col,
            volatility_floor=volatility_floor,
        )
        out[normalizer_col] = normalizer.astype(float)
        target = target / normalizer

    clip_pair = validate_clip(clip)
    if clip_pair is not None:
        clip_low, clip_high = clip_pair
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
        "target_stats": numeric_stats(out.loc[valid_mask, fwd_col]),
        "raw_future_return_stats": numeric_stats(out.loc[out[raw_fwd_col].notna(), raw_fwd_col]),
        "output_cols": sorted(str(col) for col in output_cols),
    }
    return out, label_col, fwd_col, meta


__all__ = ["build_future_return_regression_target"]
