from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd


def _coerce_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise KeyError(f"Column '{column}' is not present in the analysis frame.")
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _zscore_series(series: pd.Series) -> pd.Series:
    clean = series.replace([np.inf, -np.inf], np.nan).astype(float)
    mean = clean.mean()
    std = clean.std(ddof=0)
    if not np.isfinite(std) or std == 0.0:
        return (clean - mean).fillna(0.0)
    return ((clean - mean) / std).fillna(0.0)


def _weighted_combo(series_map: Mapping[str, pd.Series], weights: Mapping[str, float] | None, *, name: str) -> pd.Series:
    if not series_map:
        return pd.Series(dtype=float, name=name)
    ordered_columns = list(series_map)
    vector = np.array([float((weights or {}).get(column, 1.0)) for column in ordered_columns], dtype=float)
    total = float(np.abs(vector).sum())
    if total == 0.0:
        vector = np.ones(len(ordered_columns), dtype=float)
        total = float(len(ordered_columns))
    matrix = pd.concat([series_map[column] for column in ordered_columns], axis=1).fillna(0.0)
    combo = matrix.to_numpy() @ vector / total
    return pd.Series(combo, index=matrix.index, name=name)


def build_feature_signal_combo_frame(
    frame: pd.DataFrame,
    *,
    feature_cols: list[str],
    signal_cols: list[str],
    feature_weights: Mapping[str, float] | None = None,
    signal_weights: Mapping[str, float] | None = None,
    normalize: bool = True,
) -> pd.DataFrame:
    selected = list(feature_cols) + list(signal_cols)
    if len(selected) < 2:
        raise ValueError("Select at least two feature and/or signal columns to build a combination plot.")

    combo_frame = pd.DataFrame(index=frame.index)
    normalized_series: dict[str, pd.Series] = {}
    for column in selected:
        series = _coerce_numeric_series(frame, column)
        normalized = _zscore_series(series) if normalize else series.fillna(0.0)
        normalized_series[column] = normalized
        combo_frame[column] = series
        combo_frame[f"{column}__scaled"] = normalized

    if feature_cols:
        feature_map = {column: normalized_series[column] for column in feature_cols}
        combo_frame["feature_combo"] = _weighted_combo(feature_map, feature_weights, name="feature_combo")
    if signal_cols:
        signal_map = {column: normalized_series[column] for column in signal_cols}
        combo_frame["signal_combo"] = _weighted_combo(signal_map, signal_weights, name="signal_combo")

    combo_inputs = {}
    if "feature_combo" in combo_frame:
        combo_inputs["feature_combo"] = combo_frame["feature_combo"]
    if "signal_combo" in combo_frame:
        combo_inputs["signal_combo"] = combo_frame["signal_combo"]
    if combo_inputs:
        combo_frame["joint_combo"] = _weighted_combo(combo_inputs, None, name="joint_combo")

    return combo_frame


def build_feature_combo_frame(
    frame: pd.DataFrame,
    *,
    feature_cols: list[str],
    feature_weights: Mapping[str, float] | None = None,
    normalize: bool = True,
) -> pd.DataFrame:
    combo_frame = build_feature_signal_combo_frame(
        frame,
        feature_cols=feature_cols,
        signal_cols=[],
        feature_weights=feature_weights,
        signal_weights=None,
        normalize=normalize,
    )
    if "joint_combo" in combo_frame.columns and "feature_combo" in combo_frame.columns:
        combo_frame = combo_frame.drop(columns=["joint_combo"])
    return combo_frame


__all__ = ["build_feature_combo_frame", "build_feature_signal_combo_frame"]
