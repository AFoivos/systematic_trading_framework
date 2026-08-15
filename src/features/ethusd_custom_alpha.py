from __future__ import annotations

from collections.abc import Sequence
from numbers import Real

import numpy as np
import pandas as pd


CUSTOM_ALPHA_OUTPUT_COLUMNS = (
    "laf_bar_acceptance",
    "laf_activity_surprise",
    "laf_directional_flow",
    "pcp_path_short",
    "pcp_path_medium",
    "pcp_path_long",
    "pcp_consensus",
    "pcp_scale_agreement",
    "cre_compression",
    "cre_release",
    "cre_release_pressure",
    "lad_absorption_divergence",
    "casc_score",
    "causal_range_energy",
)


def add_ethusd_custom_alpha_features(
    df: pd.DataFrame,
    *,
    flow_window: int = 8,
    activity_window: int = 96,
    path_windows: Sequence[int] = (4, 12, 36),
    compression_window: int = 8,
    range_baseline_window: int = 96,
    release_baseline_window: int = 24,
    risk_window: int = 48,
    eps: float = 1.0e-12,
    inplace: bool = False,
) -> pd.DataFrame:
    """Add custom causal price-acceptance and liquidity-state indicators.

    The indicators are constructed directly from completed OHLCV bars.  They
    are not aliases for RSI, MACD, ATR, Bollinger bands, or another registered
    technical indicator.  Every rolling baseline is trailing; baselines used
    to judge the current bar are shifted by one row.

    ``LAF`` (Liquidity Acceptance Flow)
        A volume-surprise-weighted trailing mean of close location and body
        direction.  It asks whether unusual quote activity is being accepted
        near one side of the observed bar range.

    ``PCP`` (Path Consensus Pressure)
        A weighted multi-scale signed displacement divided by the complete
        absolute log-return path.  Its separate agreement output measures how
        many horizons share the composite direction.

    ``CRE`` (Compression-Release Energy)
        Prior short-range energy divided by its prior long baseline, combined
        with current range release and current-bar acceptance direction.

    ``LAD`` (Liquidity Absorption Divergence)
        Prior-normalized activity effort multiplied by wick imbalance and the
        fraction of range not converted into candle-body progress.

    ``CASC`` (Causal Acceptance-Structure Composite)
        A bounded directional score combining LAF, PCP, CRE, and a small LAD
        contribution.  It is a research feature, not a profitability claim.

    A signal calculated at bar-open label ``t`` may use that completed bar only
    if execution is delayed until the next bar.  The feature function itself
    never reads rows after ``t``.

    YAML declaration::

        features:
          - step: ethusd_custom_alpha
            params:
              flow_window: 8
              activity_window: 96
              path_windows: [4, 12, 36]
              compression_window: 8
              range_baseline_window: 96
              release_baseline_window: 24
              risk_window: 48

    Required input columns
    ----------------------
    open, high, low, close, volume:
        Completed causal OHLCV bars. ``close`` must be positive and finite
        wherever it is used; negative volume observations are treated as
        unavailable.

    Parameters
    ----------
    flow_window, activity_window:
        Positive trailing windows for acceptance flow and the prior-shifted
        activity baseline.
    path_windows:
        Three distinct, strictly increasing positive path horizons.
    compression_window, range_baseline_window, release_baseline_window:
        Positive trailing range-energy windows. Baselines used to assess the
        current bar are shifted by one observation.
    risk_window:
        Positive trailing window for prior-normalized causal range energy.
    eps:
        Positive numerical denominator floor.
    inplace:
        If true, write outputs into ``df``; otherwise return a copy.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    required = ("open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for ethusd_custom_alpha: {missing}")
    resolved_eps = _positive_real(eps, field="eps")
    resolved_flow = _positive_int(flow_window, field="flow_window")
    resolved_activity = _positive_int(activity_window, field="activity_window")
    resolved_compression = _positive_int(compression_window, field="compression_window")
    resolved_range_baseline = _positive_int(
        range_baseline_window, field="range_baseline_window"
    )
    resolved_release = _positive_int(
        release_baseline_window, field="release_baseline_window"
    )
    resolved_risk = _positive_int(risk_window, field="risk_window")
    if isinstance(path_windows, (str, bytes)) or not isinstance(path_windows, Sequence):
        raise ValueError("path_windows must be a sequence of three positive integers.")
    resolved_paths = tuple(_positive_int(value, field="path_windows entry") for value in path_windows)
    if len(resolved_paths) != 3 or len(set(resolved_paths)) != 3:
        raise ValueError("path_windows must contain three distinct positive integers.")
    if tuple(sorted(resolved_paths)) != resolved_paths:
        raise ValueError("path_windows must be strictly increasing.")

    out = df if inplace else df.copy()
    open_ = _numeric(out["open"])
    high = _numeric(out["high"])
    low = _numeric(out["low"])
    close = _numeric(out["close"])
    volume = _numeric(out["volume"]).where(lambda values: values >= 0.0)
    if bool((close.dropna() <= 0.0).any()):
        raise ValueError("close must be positive wherever it is finite.")

    absolute_range = (high - low).where(lambda values: values >= 0.0)
    safe_range = absolute_range.where(absolute_range > resolved_eps)
    close_location = ((2.0 * close - high - low) / safe_range).clip(-1.0, 1.0)
    body_direction = ((close - open_) / safe_range).clip(-1.0, 1.0)
    bar_acceptance = (0.65 * close_location + 0.35 * body_direction).clip(-1.0, 1.0)
    bar_acceptance = bar_acceptance.where(safe_range.notna(), 0.0)

    log_volume = np.log1p(volume)
    activity_median = log_volume.rolling(
        resolved_activity, min_periods=resolved_activity
    ).median().shift(1)
    activity_deviation = (log_volume - activity_median).abs()
    activity_mad = activity_deviation.rolling(
        resolved_activity, min_periods=resolved_activity
    ).median().shift(1)
    activity_surprise = (
        (log_volume - activity_median) / (1.4826 * activity_mad + resolved_eps)
    ).clip(-4.0, 4.0)
    activity_weight = np.exp(activity_surprise.clip(-1.0, 2.0)).where(
        activity_surprise.notna()
    )
    flow_numerator = (bar_acceptance * activity_weight).rolling(
        resolved_flow, min_periods=resolved_flow
    ).sum()
    flow_denominator = activity_weight.rolling(
        resolved_flow, min_periods=resolved_flow
    ).sum()
    directional_flow = (flow_numerator / flow_denominator.where(flow_denominator > 0.0)).clip(
        -1.0, 1.0
    )

    log_close = np.log(close)
    log_return = log_close.diff()
    path_features: list[pd.Series] = []
    for window in resolved_paths:
        full_path = log_return.abs().rolling(window, min_periods=window).sum()
        displacement = log_close - log_close.shift(window)
        path_features.append(
            (displacement / full_path.where(full_path > resolved_eps)).clip(-1.0, 1.0)
        )
    path_short, path_medium, path_long = path_features
    path_consensus = (0.50 * path_short + 0.30 * path_medium + 0.20 * path_long).clip(
        -1.0, 1.0
    )
    consensus_direction = np.sign(path_consensus)
    scale_agreement = (
        pd.concat(path_features, axis=1).apply(np.sign).eq(consensus_direction, axis=0).sum(axis=1)
        / 3.0
    ).where(path_consensus.notna())

    range_fraction = absolute_range / close.where(close.abs() > resolved_eps)
    prior_short_range = range_fraction.rolling(
        resolved_compression, min_periods=resolved_compression
    ).median().shift(1)
    prior_long_range = range_fraction.rolling(
        resolved_range_baseline, min_periods=resolved_range_baseline
    ).median().shift(1)
    compression = prior_short_range / prior_long_range.where(prior_long_range > resolved_eps)
    prior_release_baseline = range_fraction.rolling(
        resolved_release, min_periods=resolved_release
    ).median().shift(1)
    release = range_fraction / prior_release_baseline.where(prior_release_baseline > resolved_eps)
    release_pressure = (
        bar_acceptance * np.log(release.where(release > 0.0)).clip(-2.0, 2.0) / 2.0
    ).clip(-1.0, 1.0)

    upper_wick = (high - pd.concat([open_, close], axis=1).max(axis=1)).clip(lower=0.0)
    lower_wick = (pd.concat([open_, close], axis=1).min(axis=1) - low).clip(lower=0.0)
    wick_imbalance = ((lower_wick - upper_wick) / safe_range).clip(-1.0, 1.0)
    body_progress = ((close - open_).abs() / safe_range).clip(0.0, 1.0)
    positive_effort = activity_surprise.clip(lower=0.0) / 4.0
    absorption_divergence = (
        wick_imbalance * positive_effort * (1.0 - body_progress)
    ).clip(-1.0, 1.0)

    composite = (
        0.42 * directional_flow
        + 0.36 * path_consensus
        + 0.16 * release_pressure
        + 0.06 * absorption_divergence
    ).clip(-1.0, 1.0)
    range_energy = range_fraction.rolling(
        resolved_risk, min_periods=resolved_risk
    ).median().shift(1)

    out["laf_bar_acceptance"] = bar_acceptance.astype("float32")
    out["laf_activity_surprise"] = activity_surprise.astype("float32")
    out["laf_directional_flow"] = directional_flow.astype("float32")
    out["pcp_path_short"] = path_short.astype("float32")
    out["pcp_path_medium"] = path_medium.astype("float32")
    out["pcp_path_long"] = path_long.astype("float32")
    out["pcp_consensus"] = path_consensus.astype("float32")
    out["pcp_scale_agreement"] = scale_agreement.astype("float32")
    out["cre_compression"] = compression.astype("float32")
    out["cre_release"] = release.astype("float32")
    out["cre_release_pressure"] = release_pressure.astype("float32")
    out["lad_absorption_divergence"] = absorption_divergence.astype("float32")
    out["casc_score"] = composite.astype("float32")
    out["causal_range_energy"] = range_energy.astype("float32")
    return out


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float).replace([np.inf, -np.inf], np.nan)


def _positive_int(value: int, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or int(value) <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def _positive_real(value: Real, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a finite positive number.")
    resolved = float(value)
    if not np.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"{field} must be a finite positive number.")
    return resolved


__all__ = ["CUSTOM_ALPHA_OUTPUT_COLUMNS", "add_ethusd_custom_alpha_features"]
