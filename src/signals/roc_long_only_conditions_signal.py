from __future__ import annotations

from collections.abc import Sequence
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
    require_bullish_candle: bool = False,
    required_condition_names: Sequence[str] | str | None = None,
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
    Apply the registered ``roc_long_only_conditions`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: roc_long_only_conditions
          params:
            roc_window: 12
            roc_col: null
            roc_min: 0.0015
            vol_short_window: 24
            vol_long_window: 168
            regime_vol_ratio_z_col: null
            vol_z_min: -1.5
            vol_z_max: 1.75
            close_z_col: close_z
            close_z_min: -0.25
            close_z_max: 2.25
            close_open_ratio_col: close_open_ratio
            close_open_ratio_min: 0.0002
            mtf_1h_col: mtf_1h_trend_score
            mtf_1h_min: -0.001
            mtf_4h_col: mtf_4h_trend_score
            mtf_4h_min: -0.002
            is_weekend_col: is_weekend
            macro_condition_col: null
            min_score_required: 5
            require_all_conditions: false
            require_bullish_candle: false
            required_condition_names: null
            vol_adjustment_strength: 0.9
            min_exposure: 0.1
            max_exposure: 1.0
            signal_col: null
            long_signal_col: manual_long_signal
            score_col: manual_conviction_score
            all_conditions_col: manual_all_conditions_signal
            vol_adjusted_col: manual_vol_adjusted_signal
            short_signal_col: short_signal
            combined_signal_col: combined_signal
            output_cols:
              - configured by signal_col
    
    Required input columns
    ----------------------
    roc_col:
        Input dataframe column configured by ``roc_col``. Default: ``null``.
    regime_vol_ratio_z_col:
        Input dataframe column configured by ``regime_vol_ratio_z_col``. Default: ``null``.
    close_z_col:
        Input dataframe column configured by ``close_z_col``. Default: ``close_z``.
    close_open_ratio_col:
        Input dataframe column configured by ``close_open_ratio_col``. Default: ``close_open_ratio``.
    mtf_1h_col:
        Input dataframe column configured by ``mtf_1h_col``. Default: ``mtf_1h_trend_score``.
    mtf_4h_col:
        Input dataframe column configured by ``mtf_4h_col``. Default: ``mtf_4h_trend_score``.
    is_weekend_col:
        Input dataframe column configured by ``is_weekend_col``. Default: ``is_weekend``.
    macro_condition_col:
        Input dataframe column configured by ``macro_condition_col``. Default: ``null``.
    score_col:
        Input dataframe column configured by ``score_col``. Default: ``manual_conviction_score``.
    all_conditions_col:
        Input dataframe column configured by ``all_conditions_col``. Default: ``manual_all_conditions_signal``.
    vol_adjusted_col:
        Input dataframe column configured by ``vol_adjusted_col``. Default: ``manual_vol_adjusted_signal``.
    
    Parameters
    ----------
    roc_window:
        Trailing lookback or forecast horizon controlling this signal. Default: ``12``.
    roc_col:
        Input dataframe column configured by ``roc_col``. Default: ``null``.
    roc_min:
        Numeric threshold used by this signal. Default: ``0.0015``.
    vol_short_window:
        Trailing lookback or forecast horizon controlling this signal. Default: ``24``.
    vol_long_window:
        Trailing lookback or forecast horizon controlling this signal. Default: ``168``.
    regime_vol_ratio_z_col:
        Input dataframe column configured by ``regime_vol_ratio_z_col``. Default: ``null``.
    vol_z_min:
        Numeric threshold used by this signal. Default: ``-1.5``.
    vol_z_max:
        Numeric threshold used by this signal. Default: ``1.75``.
    close_z_col:
        Input dataframe column configured by ``close_z_col``. Default: ``close_z``.
    close_z_min:
        Numeric threshold used by this signal. Default: ``-0.25``.
    close_z_max:
        Numeric threshold used by this signal. Default: ``2.25``.
    close_open_ratio_col:
        Input dataframe column configured by ``close_open_ratio_col``. Default: ``close_open_ratio``.
    close_open_ratio_min:
        Numeric threshold used by this signal. Default: ``0.0002``.
    mtf_1h_col:
        Input dataframe column configured by ``mtf_1h_col``. Default: ``mtf_1h_trend_score``.
    mtf_1h_min:
        Numeric threshold used by this signal. Default: ``-0.001``.
    mtf_4h_col:
        Input dataframe column configured by ``mtf_4h_col``. Default: ``mtf_4h_trend_score``.
    mtf_4h_min:
        Numeric threshold used by this signal. Default: ``-0.002``.
    is_weekend_col:
        Input dataframe column configured by ``is_weekend_col``. Default: ``is_weekend``.
    macro_condition_col:
        Input dataframe column configured by ``macro_condition_col``. Default: ``null``.
    min_score_required:
        Configuration parameter accepted by this signal. Default: ``5``.
    require_all_conditions:
        Configuration parameter accepted by this signal. Default: ``false``.
    require_bullish_candle:
        Configuration parameter accepted by this signal. Default: ``false``.
    required_condition_names:
        Configuration parameter accepted by this signal. Default: ``null``.
    vol_adjustment_strength:
        Configuration parameter accepted by this signal. Default: ``0.9``.
    min_exposure:
        Configuration parameter accepted by this signal. Default: ``0.1``.
    max_exposure:
        Configuration parameter accepted by this signal. Default: ``1.0``.
    signal_col:
        Output dataframe column configured by ``signal_col``. Default: ``null``.
    long_signal_col:
        Input dataframe column configured by ``long_signal_col``. Default: ``manual_long_signal``.
    score_col:
        Input dataframe column configured by ``score_col``. Default: ``manual_conviction_score``.
    all_conditions_col:
        Input dataframe column configured by ``all_conditions_col``. Default: ``manual_all_conditions_signal``.
    vol_adjusted_col:
        Input dataframe column configured by ``vol_adjusted_col``. Default: ``manual_vol_adjusted_signal``.
    short_signal_col:
        Input dataframe column configured by ``short_signal_col``. Default: ``short_signal``.
    combined_signal_col:
        Input dataframe column configured by ``combined_signal_col``. Default: ``combined_signal``.
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
    if not isinstance(require_bullish_candle, bool):
        raise TypeError("require_bullish_candle must be boolean.")

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

    if required_condition_names is None:
        required_conditions: tuple[str, ...] = ()
    elif isinstance(required_condition_names, str):
        required_conditions = (required_condition_names,)
    else:
        required_conditions = tuple(str(name) for name in required_condition_names)
    if bool(require_bullish_candle) and "cond_bullish_candle" not in required_conditions:
        required_conditions = (*required_conditions, "cond_bullish_candle")
    unknown_required = [name for name in required_conditions if name not in conditions]
    if unknown_required:
        allowed = ", ".join(sorted(conditions))
        raise ValueError(
            "required_condition_names contains unknown conditions: "
            f"{unknown_required}. Allowed: {allowed}."
        )

    out[score_col] = out[condition_cols].sum(axis=1).astype("int16")
    out[all_conditions_col] = out[condition_cols].all(axis=1).astype("int8")
    score_ok = out[score_col].ge(int(min_score_required))
    gates_ok = out["cond_not_weekend"].eq(1) & out["cond_macro_not_bearish"].eq(1)
    for condition_name in required_conditions:
        gates_ok &= out[condition_name].eq(1)
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
