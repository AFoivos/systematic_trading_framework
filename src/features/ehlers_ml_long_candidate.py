"""Candidate feature generation for the pure Ehlers ML long-only experiment.

This module does not encode a directional trading rule. It only identifies
rows with an observable cyclical regime; the classifier decides whether a
long entry is justified. All rolling statistics are trailing and shifted by
one bar so the current observation does not fit its own candidate threshold.
"""

from __future__ import annotations

from numbers import Integral, Real

import numpy as np
import pandas as pd


def _positive_int(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return int(value)


def _finite_number(value: float, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number.")
    return float(value)


def ehlers_ml_long_candidate_feature(
    df: pd.DataFrame,
    *,
    amplitude_col: str = "hilbert_amplitude",
    cycle_period_col: str = "dominant_cycle_period",
    roofing_col: str = "roofing_filter",
    mama_col: str = "mama",
    fama_col: str = "fama",
    close_col: str = "close",
    decycler_col: str = "decycler",
    instantaneous_trendline_col: str = "instantaneous_trendline",
    frama_col: str = "frama",
    supersmoother_col: str = "supersmoother",
    dominant_cycle_phase_col: str = "dominant_cycle_phase",
    atr_col: str | None = None,
    amplitude_lookback: int = 128,
    amplitude_min_quantile: float = 0.50,
    min_cycle_period: float = 8.0,
    max_cycle_period: float = 60.0,
    slope_bars: int = 1,
    candidate_col: str = "ehlers_ml_candidate",
    side_col: str = "signal_side",
) -> pd.DataFrame:
    """
    Add causal derived Ehlers features and long-only candidate columns.
    
    YAML declaration::
    
        features:
          - step: ehlers_ml_long_candidate
            params: {}
    
    Required input columns
    ----------------------
    amplitude_col:
        Input column configured by ``amplitude_col``. Default: ``hilbert_amplitude``.
    cycle_period_col:
        Input column configured by ``cycle_period_col``. Default: ``dominant_cycle_period``.
    roofing_col:
        Input column configured by ``roofing_col``. Default: ``roofing_filter``.
    mama_col:
        Input column configured by ``mama_col``. Default: ``mama``.
    fama_col:
        Input column configured by ``fama_col``. Default: ``fama``.
    close_col:
        Input column configured by ``close_col``. Default: ``close``.
    decycler_col:
        Input column configured by ``decycler_col``. Default: ``decycler``.
    instantaneous_trendline_col:
        Input column configured by ``instantaneous_trendline_col``. Default: ``instantaneous_trendline``.
    frama_col:
        Input column configured by ``frama_col``. Default: ``frama``.
    supersmoother_col:
        Input column configured by ``supersmoother_col``. Default: ``supersmoother``.
    dominant_cycle_phase_col:
        Input column configured by ``dominant_cycle_phase_col``. Default: ``dominant_cycle_phase``.
    candidate_col:
        Input column configured by ``candidate_col``. Default: ``ehlers_ml_candidate``.
    side_col:
        Input column configured by ``side_col``. Default: ``signal_side``.
    
    Parameters
    ----------
    amplitude_col:
        Input dataframe column name consumed by the component. Default: ``hilbert_amplitude``.
    cycle_period_col:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``dominant_cycle_period``.
    roofing_col:
        Input dataframe column name consumed by the component. Default: ``roofing_filter``.
    mama_col:
        Input dataframe column name consumed by the component. Default: ``mama``.
    fama_col:
        Input dataframe column name consumed by the component. Default: ``fama``.
    close_col:
        Input dataframe column name consumed by the component. Default: ``close``.
    decycler_col:
        Input dataframe column name consumed by the component. Default: ``decycler``.
    instantaneous_trendline_col:
        Input dataframe column name consumed by the component. Default: ``instantaneous_trendline``.
    frama_col:
        Input dataframe column name consumed by the component. Default: ``frama``.
    supersmoother_col:
        Input dataframe column name consumed by the component. Default: ``supersmoother``.
    dominant_cycle_phase_col:
        Input dataframe column name consumed by the component. Default: ``dominant_cycle_phase``.
    atr_col:
        Input dataframe column name consumed by the component. Default: ``None``.
    amplitude_lookback:
        Configuration value used by the registered component. Default: ``128``.
    amplitude_min_quantile:
        Configuration value used by the registered component. Default: ``0.5``.
    min_cycle_period:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``8.0``.
    max_cycle_period:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``60.0``.
    slope_bars:
        Lookback, forecast horizon, or bar-count parameter used by the component. Default: ``1``.
    candidate_col:
        Input dataframe column name consumed by the component. Default: ``ehlers_ml_candidate``.
    side_col:
        Input dataframe column name consumed by the component. Default: ``signal_side``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    lookback = _positive_int(amplitude_lookback, name="amplitude_lookback")
    slope_lag = _positive_int(slope_bars, name="slope_bars")
    quantile = _finite_number(amplitude_min_quantile, name="amplitude_min_quantile")
    min_period = _finite_number(min_cycle_period, name="min_cycle_period")
    max_period = _finite_number(max_cycle_period, name="max_cycle_period")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("amplitude_min_quantile must be in [0, 1].")
    if min_period <= 0.0 or max_period < min_period:
        raise ValueError("cycle period bounds must satisfy 0 < min_cycle_period <= max_cycle_period.")

    required = {
        amplitude_col,
        cycle_period_col,
        roofing_col,
        mama_col,
        fama_col,
        close_col,
        decycler_col,
        instantaneous_trendline_col,
        frama_col,
        supersmoother_col,
        dominant_cycle_phase_col,
    }
    if atr_col is not None:
        required.add(atr_col)
    missing = sorted(required.difference(df.columns))
    if missing:
        raise KeyError(f"Missing columns for Ehlers ML candidate: {missing}")

    out = df.copy()

    def numeric(column: str) -> pd.Series:
        return pd.to_numeric(out[column], errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)

    amplitude = numeric(amplitude_col)
    cycle_period = numeric(cycle_period_col)
    roofing = numeric(roofing_col)
    out["mama_minus_fama"] = (numeric(mama_col) - numeric(fama_col)).astype("float32")
    out["close_minus_decycler"] = (numeric(close_col) - numeric(decycler_col)).astype("float32")
    out["instantaneous_trendline_slope"] = numeric(instantaneous_trendline_col).diff(slope_lag).astype("float32")
    out["decycler_slope"] = numeric(decycler_col).diff(slope_lag).astype("float32")
    out["frama_slope"] = numeric(frama_col).diff(slope_lag).astype("float32")
    out["supersmoother_slope"] = numeric(supersmoother_col).diff(slope_lag).astype("float32")
    out["dominant_cycle_phase_normalized"] = (
        numeric(dominant_cycle_phase_col).mod(360.0) / 360.0
    ).astype("float32")
    if atr_col is not None:
        atr = numeric(atr_col).where(lambda values: values.gt(0.0))
        stationary_features = {
            "mama_minus_close_over_atr": numeric(mama_col) - numeric(close_col),
            "fama_minus_close_over_atr": numeric(fama_col) - numeric(close_col),
            "mama_minus_fama_over_atr": numeric(mama_col) - numeric(fama_col),
            "close_minus_decycler_over_atr": numeric(close_col) - numeric(decycler_col),
            "instantaneous_trendline_slope_over_atr": numeric(instantaneous_trendline_col).diff(slope_lag),
            "decycler_slope_over_atr": numeric(decycler_col).diff(slope_lag),
            "frama_slope_over_atr": numeric(frama_col).diff(slope_lag),
            "supersmoother_slope_over_atr": numeric(supersmoother_col).diff(slope_lag),
            "roofing_filter_over_atr": roofing,
            "roofing_filter_slope_over_atr": roofing.diff(slope_lag),
            "hilbert_amplitude_over_atr": amplitude,
        }
        for output_col, values in stationary_features.items():
            out[output_col] = (values / atr).replace([np.inf, -np.inf], np.nan).astype("float32")

    amplitude_threshold = (
        amplitude.rolling(lookback, min_periods=lookback).quantile(quantile).shift(1)
    )
    candidate = (
        amplitude.gt(amplitude_threshold)
        & cycle_period.between(min_period, max_period, inclusive="both")
        & roofing.notna()
    )
    out[candidate_col] = candidate.fillna(False).astype("int8")
    out[side_col] = out[candidate_col].astype("int8")
    return out


__all__ = ["ehlers_ml_long_candidate_feature"]
