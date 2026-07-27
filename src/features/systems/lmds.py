from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from .common import compute_gap_diagnostics, prepare_market_data, validate_bar_minutes
from .config import LMDSConfig, resolve_lmds_config


LMDS_REQUIRED_COLUMNS = (
    "kalman_drift",
    "kalman_drift_std",
    "ktrend_score",
    "rlv_sigma",
    "rlv_forecast_5",
    "rlv_forecast_15",
    "rlv_forecast_30",
    "rlv_shock_z",
    "rlv_vol_of_vol_ratio",
)

LMDS_OUTPUT_COLUMNS = (
    "lmom_acceleration",
    "lmom_acceleration_z",
    "lmom_acceleration_score",
    "lmom_impulse_3",
    "lmom_impulse_5",
    "lmom_impulse_15",
    "lmom_impulse_30",
    "lmom_impulse_60",
    "lmom_impulse",
    "lmom_breadth",
    "lmom_efficiency_5",
    "lmom_efficiency_15",
    "lmom_efficiency_30",
    "lmom_efficiency",
    "lmom_persistence",
    "lmom_activity",
    "lmom_plus",
    "lmom_minus",
    "lmom_strength",
    "lmom_score",
    "lmom_exhaustion",
    "lmom_reversal_pressure",
    "lmom_divergence",
    "lmom_alignment",
    "lmom_direction",
)


def add_lmds_features(
    df: pd.DataFrame,
    *,
    preset: str = "balanced",
    config: LMDSConfig | Mapping[str, object] | None = None,
    bar_minutes: float = 1.0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``lmds`` feature transformation.

    LMDS measures changes in KDS drift, volatility-scaled price impulses,
    cross-horizon agreement, path efficiency, persistence, exhaustion, and
    trend-momentum interaction. It consumes existing KDS and RLVS columns
    rather than recomputing latent states.

    YAML declaration::

        features:
          - step: lmds
            params:
              preset: balanced
              config: null
              bar_minutes: 1.0
              inplace: false

    Required input columns
    ----------------------
    Market data:
        Full bid/ask OHLC or fallback ``open``, ``high``, ``low``, ``close``.
    KDS:
        ``kalman_drift``, ``kalman_drift_std``, ``ktrend_score``.
    RLVS:
        ``rlv_sigma``, ``rlv_forecast_5``, ``rlv_forecast_15``,
        ``rlv_forecast_30``, ``rlv_shock_z``, ``rlv_vol_of_vol_ratio``.

    Parameters
    ----------
    preset:
        One of ``conservative``, ``balanced``, or ``responsive``.
    config:
        Optional mapping of transparent LMDSConfig overrides, or LMDSConfig.
    bar_minutes:
        Explicit duration of one input bar in minutes. LMDS horizons remain
        expressed in bars and gap continuity uses this duration.
    inplace:
        If true, append outputs to the supplied dataframe. Default: ``false``.
    """
    resolved = resolve_lmds_config(config, preset=preset)
    resolved_bar_minutes = validate_bar_minutes(bar_minutes)
    market = prepare_market_data(df)
    gaps = compute_gap_diagnostics(
        df.index,
        expected_bar_minutes=resolved_bar_minutes,
    )
    missing = [column for column in LMDS_REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise KeyError(f"Missing KDS/RLVS dependencies for LMDS: {missing}.")
    dependencies = {
        column: _numeric_dependency(df[column], field=column)
        for column in LMDS_REQUIRED_COLUMNS
    }
    out = df if inplace else df.copy()

    drift = dependencies["kalman_drift"]
    drift_std = dependencies["kalman_drift_std"]
    acceleration = drift.diff().where(~gaps.is_gap)
    acceleration_std = np.sqrt(
        drift_std.pow(2) + drift_std.shift(1).pow(2) + resolved.epsilon
    )
    acceleration_z = acceleration / acceleration_std
    acceleration_score = pd.Series(
        np.tanh(acceleration_z.to_numpy(dtype=float) / resolved.acceleration_scale),
        index=out.index,
        dtype="float64",
    ).where(acceleration_z.notna())

    log_close = np.log(market.close)
    raw_impulses: dict[int, pd.Series] = {}
    bounded_impulses: dict[int, pd.Series] = {}
    for horizon in resolved.impulse_horizons:
        horizon_return = log_close - log_close.shift(horizon)
        if horizon in (5, 15, 30):
            expected_volatility = dependencies[f"rlv_forecast_{horizon}"]
        else:
            expected_volatility = dependencies["rlv_sigma"] * np.sqrt(float(horizon))
        raw = horizon_return / (expected_volatility + resolved.epsilon)
        raw = raw.where(gaps.contiguous_bars >= horizon + 1)
        raw = raw.replace([np.inf, -np.inf], np.nan).astype("float64")
        raw_impulses[horizon] = raw
        bounded_impulses[horizon] = raw.clip(
            lower=-resolved.raw_impulse_clip,
            upper=resolved.raw_impulse_clip,
        )

    impulse = _weighted_sum(
        [
            np.tanh(bounded_impulses[horizon] / resolved.impulse_scale)
            for horizon in resolved.impulse_horizons
        ],
        resolved.impulse_weights,
    ).clip(lower=-1.0, upper=1.0)
    breadth = _weighted_sum(
        [np.tanh(bounded_impulses[horizon]) for horizon in resolved.impulse_horizons],
        resolved.impulse_weights,
    ).clip(lower=-1.0, upper=1.0)

    absolute_path = market.close.diff().abs()
    efficiencies: dict[int, pd.Series] = {}
    for horizon in resolved.efficiency_horizons:
        displacement = (market.close - market.close.shift(horizon)).abs()
        path_length = absolute_path.rolling(horizon, min_periods=horizon).sum()
        efficiency = (displacement / (path_length + resolved.epsilon)).clip(
            lower=0.0,
            upper=1.0,
        )
        efficiency = efficiency.where(gaps.contiguous_bars >= horizon + 1)
        efficiencies[horizon] = efficiency
    composite_efficiency = _weighted_sum(
        [efficiencies[horizon] for horizon in resolved.efficiency_horizons],
        resolved.efficiency_weights,
    ).clip(lower=0.0, upper=1.0)

    return_sign = np.sign(log_close.diff().where(~gaps.is_gap))
    segment = gaps.is_gap.astype("int64").cumsum()
    signed_persistence = return_sign.groupby(segment).transform(
        lambda values: values.ewm(
            span=resolved.persistence_span,
            adjust=False,
            min_periods=resolved.persistence_min_periods,
        ).mean()
    )
    signed_persistence = signed_persistence.clip(lower=-1.0, upper=1.0)
    signed_persistence = signed_persistence.mask(
        impulse.abs() <= resolved.direction_epsilon,
        0.0,
    )

    activity = (
        impulse.abs()
        * ((1.0 + breadth.abs()) / 2.0)
        * composite_efficiency
    ).clip(lower=0.0, upper=1.0)
    positive_share = ((1.0 + impulse) / 2.0).clip(lower=0.0, upper=1.0)
    negative_share = 1.0 - positive_share
    plus = (100.0 * activity * positive_share).clip(lower=0.0, upper=100.0)
    minus = (100.0 * activity * negative_share).clip(lower=0.0, upper=100.0)
    strength = (plus + minus).clip(lower=0.0, upper=100.0)

    impulse_weight, acceleration_weight, breadth_weight = resolved.momentum_weights
    raw_momentum = (
        impulse_weight * impulse
        + acceleration_weight * acceleration_score
        + breadth_weight * breadth
    )
    quality = np.sqrt(
        (
            composite_efficiency
            * ((1.0 + signed_persistence.abs()) / 2.0)
        ).clip(lower=0.0)
    )
    score = (
        pd.Series(
            np.tanh(raw_momentum.to_numpy(dtype=float)),
            index=out.index,
            dtype="float64",
        )
        * quality
    ).clip(lower=-1.0, upper=1.0)

    impulse_direction = _thresholded_sign(
        impulse,
        epsilon=resolved.direction_epsilon,
    )
    opposition = (
        -impulse_direction * acceleration_score
    ).clip(lower=0.0, upper=1.0)
    base_exhaustion = (
        np.tanh(raw_impulses[15].abs() / resolved.exhaustion_scale)
        * opposition
        * (1.0 - composite_efficiency)
    )
    shock_load = np.tanh(
        dependencies["rlv_shock_z"].abs() / resolved.exhaustion_shock_scale
    )
    vol_of_vol_excess = (
        dependencies["rlv_vol_of_vol_ratio"] - 1.0
    ).clip(lower=0.0)
    vol_of_vol_load = np.tanh(
        vol_of_vol_excess / resolved.exhaustion_vol_of_vol_scale
    )
    exhaustion = (
        base_exhaustion
        * (
            1.0
            + resolved.exhaustion_shock_weight * shock_load
            + resolved.exhaustion_vol_of_vol_weight * vol_of_vol_load
        )
    ).clip(lower=0.0, upper=1.0)

    trend = dependencies["ktrend_score"]
    trend_direction = _thresholded_sign(trend, epsilon=resolved.direction_epsilon)
    reversal_pressure = (-trend_direction * score).clip(lower=0.0, upper=1.0)
    reversal_pressure = reversal_pressure.mask(
        trend.abs() <= resolved.direction_epsilon,
        0.0,
    )
    divergence = score - trend
    alignment = (score * trend).clip(lower=-1.0, upper=1.0)
    direction = _thresholded_sign(score, epsilon=resolved.direction_epsilon)

    values: dict[str, pd.Series] = {
        "lmom_acceleration": acceleration,
        "lmom_acceleration_z": acceleration_z,
        "lmom_acceleration_score": acceleration_score,
        "lmom_impulse": impulse,
        "lmom_breadth": breadth,
        "lmom_efficiency": composite_efficiency,
        "lmom_persistence": signed_persistence,
        "lmom_activity": activity,
        "lmom_plus": plus,
        "lmom_minus": minus,
        "lmom_strength": strength,
        "lmom_score": score,
        "lmom_exhaustion": exhaustion,
        "lmom_reversal_pressure": reversal_pressure,
        "lmom_divergence": divergence,
        "lmom_alignment": alignment,
        "lmom_direction": direction,
    }
    for horizon, raw in raw_impulses.items():
        values[f"lmom_impulse_{horizon}"] = raw
    for horizon, efficiency in efficiencies.items():
        values[f"lmom_efficiency_{horizon}"] = efficiency

    for column in LMDS_OUTPUT_COLUMNS:
        out[column] = values[column]
    return out


def _weighted_sum(
    series: list[pd.Series],
    weights: tuple[float, ...],
) -> pd.Series:
    if not series:
        raise ValueError("weighted sum requires at least one series.")
    result = series[0].astype(float) * float(weights[0])
    for values, weight in zip(series[1:], weights[1:]):
        result = result + values.astype(float) * float(weight)
    return result.astype("float64")


def _numeric_dependency(series: pd.Series, *, field: str) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype("float64")
    invalid = values.isna() & ~series.isna()
    if bool(invalid.any()) or bool(np.isinf(values.to_numpy(dtype=float)).any()):
        raise ValueError(f"{field} must contain only finite numeric values or NaN.")
    return values


def _thresholded_sign(series: pd.Series, *, epsilon: float) -> pd.Series:
    direction = np.sign(series).astype("float64")
    return direction.mask(series.abs() <= epsilon, 0.0).where(series.notna())


__all__ = [
    "LMDS_OUTPUT_COLUMNS",
    "LMDS_REQUIRED_COLUMNS",
    "add_lmds_features",
]
