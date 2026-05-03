from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.signals._common import resolve_signal_output_name


def _resolve_col(explicit: str | None, default: str) -> str:
    return str(explicit or default)


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for roc_long_only_conditions_signal: {missing}")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def roc_long_only_conditions_signal(
    df: pd.DataFrame,
    *,
    roc_window: int = 12,
    roc_col: str | None = None,
    roc_min: float = 0.0015,
    vol_short_window: int = 24,
    vol_long_window: int = 168,
    regime_vol_ratio_z_col: str | None = None,
    vol_z_min: float = -1.5,
    vol_z_max: float = 1.75,
    close_z_col: str = "close_z",
    close_z_min: float = -0.25,
    close_z_max: float = 2.25,
    close_open_ratio_col: str = "close_open_ratio",
    close_open_ratio_min: float = 0.0002,
    mtf_1h_col: str = "mtf_1h_trend_score",
    mtf_1h_min: float = -0.001,
    mtf_4h_col: str = "mtf_4h_trend_score",
    mtf_4h_min: float = -0.002,
    is_weekend_col: str = "is_weekend",
    macro_condition_col: str | None = None,
    min_score_required: int = 5,
    require_all_conditions: bool = False,
    vol_adjustment_strength: float = 0.9,
    min_exposure: float = 0.10,
    max_exposure: float = 1.0,
    signal_col: str | None = None,
    long_signal_col: str = "manual_long_signal",
    score_col: str = "manual_conviction_score",
    all_conditions_col: str = "manual_all_conditions_signal",
    vol_adjusted_col: str = "manual_vol_adjusted_signal",
    short_signal_col: str = "short_signal",
    combined_signal_col: str = "combined_signal",
) -> pd.DataFrame:
    """
    Build a causal manual ROC long-only signal from already-computed market conditions.

    The function does not fit or predict a model. It only combines condition columns that are
    available at the current bar close. Backtesting remains responsible for shifting execution
    to the next bar/open.
    """
    if int(roc_window) <= 0:
        raise ValueError("roc_window must be positive.")
    if int(vol_short_window) <= 0 or int(vol_long_window) <= 0:
        raise ValueError("vol_short_window and vol_long_window must be positive.")
    if int(min_score_required) < 0:
        raise ValueError("min_score_required must be >= 0.")
    if float(vol_z_min) > float(vol_z_max):
        raise ValueError("vol_z_min must be <= vol_z_max.")
    if float(close_z_min) > float(close_z_max):
        raise ValueError("close_z_min must be <= close_z_max.")
    if float(min_exposure) < 0.0 or float(max_exposure) <= 0.0:
        raise ValueError("min_exposure must be >= 0 and max_exposure must be > 0.")
    if float(min_exposure) > float(max_exposure):
        raise ValueError("min_exposure must be <= max_exposure.")

    out = df.copy()
    output_col = resolve_signal_output_name(
        signal_col=signal_col,
        default=vol_adjusted_col,
    )
    roc_feature_col = _resolve_col(roc_col, f"roc_{int(roc_window)}")
    regime_z_feature_col = _resolve_col(
        regime_vol_ratio_z_col,
        f"regime_vol_ratio_z_{int(vol_short_window)}_{int(vol_long_window)}",
    )

    if close_open_ratio_col not in out.columns:
        _require_columns(out, ["open", "close"])
        out[close_open_ratio_col] = (
            _numeric(out, "close") / _numeric(out, "open").replace(0.0, np.nan) - 1.0
        ).astype("float32")

    required = [
        roc_feature_col,
        regime_z_feature_col,
        close_z_col,
        close_open_ratio_col,
        mtf_1h_col,
        mtf_4h_col,
        is_weekend_col,
    ]
    if macro_condition_col is not None:
        required.append(str(macro_condition_col))
    _require_columns(out, required)

    macro_ok = (
        _numeric(out, str(macro_condition_col)).gt(0.0)
        if macro_condition_col is not None
        else pd.Series(True, index=out.index)
    )

    conditions: dict[str, pd.Series] = {
        "cond_not_weekend": _numeric(out, is_weekend_col).fillna(1.0).eq(0.0),
        "cond_roc": _numeric(out, roc_feature_col).gt(float(roc_min)),
        "cond_vol_regime": _numeric(out, regime_z_feature_col).between(float(vol_z_min), float(vol_z_max)),
        "cond_mtf_1h_not_bearish": _numeric(out, mtf_1h_col).ge(float(mtf_1h_min)),
        "cond_mtf_4h_not_bearish": _numeric(out, mtf_4h_col).ge(float(mtf_4h_min)),
        "cond_close_z": _numeric(out, close_z_col).between(float(close_z_min), float(close_z_max)),
        "cond_bullish_candle": _numeric(out, close_open_ratio_col).ge(float(close_open_ratio_min)),
        "cond_macro_not_bearish": macro_ok,
    }

    condition_cols: list[str] = []
    for name, values in conditions.items():
        out[name] = values.fillna(False).astype("int8")
        condition_cols.append(name)

    out[score_col] = out[condition_cols].sum(axis=1).astype("int16")
    out[all_conditions_col] = out[condition_cols].all(axis=1).astype("int8")
    score_ok = out[score_col].ge(int(min_score_required))
    gates_ok = out["cond_not_weekend"].eq(1) & out["cond_macro_not_bearish"].eq(1)
    if bool(require_all_conditions):
        long_signal = gates_ok & out[all_conditions_col].eq(1)
    else:
        long_signal = gates_ok & score_ok

    out[long_signal_col] = long_signal.astype("int8")
    out[short_signal_col] = 0
    out[combined_signal_col] = out[long_signal_col].astype("int8")

    vol_z = _numeric(out, regime_z_feature_col).clip(lower=0.0).fillna(0.0)
    vol_adjustment = 1.0 / (1.0 + float(vol_adjustment_strength) * vol_z)
    adjusted = out[long_signal_col].astype(float) * vol_adjustment.clip(
        lower=float(min_exposure),
        upper=float(max_exposure),
    )
    out[vol_adjusted_col] = adjusted.astype("float32")
    if output_col != vol_adjusted_col:
        out[output_col] = out[vol_adjusted_col].astype("float32")

    return out


__all__ = ["roc_long_only_conditions_signal"]
