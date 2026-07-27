from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd
from scipy.special import ndtr

from src.features.technical.wilder import wilder_smooth

from .common import (
    causal_baseline,
    compute_gap_diagnostics,
    prepare_market_data,
    safe_ratio,
    validate_bar_minutes,
)
from .config import KDSConfig, resolve_kds_config


KDS_OUTPUT_COLUMNS = (
    "kalman_level",
    "kalman_drift",
    "kalman_drift_std",
    "kalman_drift_z",
    "kalman_prob_up",
    "kalman_innovation",
    "kalman_innovation_z",
    "kdi_activity",
    "kdi_plus",
    "kdi_minus",
    "kdx",
    "kadx",
    "kadx_signed",
    "ktrend_score",
    "ktrend_direction",
    "ktrend_confidence",
    "ktrend_uncertainty",
    "local_realized_volatility",
    "spread_ratio",
    "volatility_ratio",
)


@dataclass(frozen=True)
class KDSFilterResult:
    level: np.ndarray
    drift: np.ndarray
    drift_variance: np.ndarray
    innovation: np.ndarray
    innovation_z: np.ndarray


def add_kds_features(
    df: pd.DataFrame,
    *,
    preset: str = "balanced",
    config: KDSConfig | Mapping[str, object] | None = None,
    bar_minutes: float = 1.0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``kds`` feature transformation.

    The Kalman Directional System is a robust causal local-linear-trend filter
    over log midpoint close. Its posterior drift is decomposed into ADX-like
    directional activity and confidence diagnostics.

    YAML declaration::

        features:
          - step: kds
            params:
              preset: balanced
              config: null
              bar_minutes: 1.0
              inplace: false

    Required input columns
    ----------------------
    Preferred:
        ``bid_open``, ``bid_high``, ``bid_low``, ``bid_close``,
        ``ask_open``, ``ask_high``, ``ask_low``, ``ask_close``.
    Fallback:
        ``open``, ``high``, ``low``, ``close``.
    Optional:
        ``spread_bps`` and ``tick_volume``.

    Parameters
    ----------
    preset:
        One of ``conservative``, ``balanced``, or ``responsive``.
    config:
        Optional mapping of transparent KDSConfig overrides, or a KDSConfig.
    bar_minutes:
        Explicit duration of one input bar in minutes. State transitions use
        elapsed bar steps, while gap reporting remains expressed in minutes.
    inplace:
        If true, append outputs to the supplied dataframe. Default: ``false``.
    """
    resolved = resolve_kds_config(config, preset=preset)
    resolved_bar_minutes = validate_bar_minutes(bar_minutes)
    market = prepare_market_data(df)
    gaps = compute_gap_diagnostics(
        df.index,
        expected_bar_minutes=resolved_bar_minutes,
    )
    out = df if inplace else df.copy()

    log_close = np.log(market.close)
    returns = log_close.diff().where(~gaps.is_gap)
    local_variance = (
        returns.pow(2)
        .ewm(
            span=resolved.local_volatility_span,
            adjust=False,
            min_periods=resolved.local_volatility_min_periods,
        )
        .mean()
    )
    local_volatility = np.sqrt(local_variance.clip(lower=0.0)).astype("float64")
    volatility_baseline = causal_baseline(
        local_volatility,
        window=resolved.volatility_baseline_window,
    )
    volatility_ratio = safe_ratio(
        local_volatility,
        volatility_baseline,
        epsilon=resolved.epsilon,
        zero_over_zero=1.0,
    )

    spread_baseline = causal_baseline(
        market.spread_bps,
        window=resolved.spread_baseline_window,
    )
    spread_ratio = safe_ratio(
        market.spread_bps,
        spread_baseline,
        epsilon=resolved.epsilon,
        zero_over_zero=1.0,
    )

    filtered = _run_kds_filter(
        log_close.to_numpy(dtype=float),
        local_variance.to_numpy(dtype=float),
        spread_ratio.to_numpy(dtype=float),
        volatility_ratio.to_numpy(dtype=float),
        gaps.elapsed_bars.to_numpy(dtype=float),
        gaps.is_hard_gap.to_numpy(dtype=bool),
        config=resolved,
    )
    index = out.index
    level = pd.Series(filtered.level, index=index, dtype="float64")
    drift = pd.Series(filtered.drift, index=index, dtype="float64")
    drift_std = pd.Series(
        np.sqrt(np.maximum(filtered.drift_variance, 0.0)),
        index=index,
        dtype="float64",
    )
    drift_z = drift / (drift_std + resolved.epsilon)
    probability_up = pd.Series(ndtr(drift_z.to_numpy(dtype=float)), index=index, dtype="float64")
    probability_up = probability_up.where(drift_z.notna())

    normal_density = np.exp(-0.5 * drift_z.pow(2)) / np.sqrt(2.0 * np.pi)
    positive_evidence = (drift_std * normal_density + drift * probability_up).clip(lower=0.0)
    negative_evidence = (
        drift_std * normal_density - drift * (1.0 - probability_up)
    ).clip(lower=0.0)
    total_evidence = positive_evidence + negative_evidence
    positive_share = positive_evidence / total_evidence
    negative_share = 1.0 - positive_share
    zero_evidence = total_evidence <= resolved.epsilon
    positive_share = positive_share.mask(zero_evidence, 0.5)
    negative_share = negative_share.mask(zero_evidence, 0.5)

    confidence = (2.0 * probability_up - 1.0).abs().clip(lower=0.0, upper=1.0)
    magnitude = pd.Series(
        np.tanh(
            drift.abs().to_numpy(dtype=float)
            / (
                resolved.activity_scale * local_volatility.fillna(0.0).to_numpy(dtype=float)
                + resolved.epsilon
            )
        ),
        index=index,
        dtype="float64",
    )
    activity = (confidence * magnitude).clip(lower=0.0, upper=1.0)
    activity = activity.where(local_volatility.notna())
    kdi_plus = (100.0 * activity * positive_share).clip(lower=0.0, upper=100.0)
    kdi_minus = (100.0 * activity * negative_share).clip(lower=0.0, upper=100.0)
    total_kdi = kdi_plus + kdi_minus
    kdx = 100.0 * (kdi_plus - kdi_minus).abs() / (total_kdi + resolved.epsilon)
    kdx = kdx.mask(total_kdi <= 100.0 * resolved.min_directional_activity, 0.0)
    kdx = kdx.clip(lower=0.0, upper=100.0)
    kadx = wilder_smooth(kdx, window=resolved.kadx_window).clip(lower=0.0, upper=100.0)
    direction = _thresholded_sign(drift, epsilon=resolved.min_directional_activity)
    kadx_signed = direction * kadx
    trend_score = (direction * (kadx / 100.0) * activity).clip(lower=-1.0, upper=1.0)
    uncertainty = (
        drift_std / (drift.abs() + drift_std + resolved.epsilon)
    ).clip(lower=0.0, upper=1.0)

    values: dict[str, pd.Series | np.ndarray] = {
        "kalman_level": level,
        "kalman_drift": drift,
        "kalman_drift_std": drift_std,
        "kalman_drift_z": drift_z,
        "kalman_prob_up": probability_up.clip(lower=0.0, upper=1.0),
        "kalman_innovation": filtered.innovation,
        "kalman_innovation_z": filtered.innovation_z,
        "kdi_activity": activity,
        "kdi_plus": kdi_plus,
        "kdi_minus": kdi_minus,
        "kdx": kdx,
        "kadx": kadx,
        "kadx_signed": kadx_signed.clip(lower=-100.0, upper=100.0),
        "ktrend_score": trend_score,
        "ktrend_direction": direction,
        "ktrend_confidence": confidence,
        "ktrend_uncertainty": uncertainty,
        "local_realized_volatility": local_volatility,
        "spread_ratio": spread_ratio,
        "volatility_ratio": volatility_ratio,
    }
    for column in KDS_OUTPUT_COLUMNS:
        out[column] = values[column]
    return out


def _run_kds_filter(
    observations: np.ndarray,
    local_variance: np.ndarray,
    spread_ratio: np.ndarray,
    volatility_ratio: np.ndarray,
    elapsed_bars: np.ndarray,
    hard_gap: np.ndarray,
    *,
    config: KDSConfig,
) -> KDSFilterResult:
    size = len(observations)
    levels = np.full(size, np.nan, dtype=np.float64)
    drifts = np.full(size, np.nan, dtype=np.float64)
    drift_variances = np.full(size, np.nan, dtype=np.float64)
    innovations = np.full(size, np.nan, dtype=np.float64)
    innovation_z = np.full(size, np.nan, dtype=np.float64)
    if size == 0:
        return KDSFilterResult(levels, drifts, drift_variances, innovations, innovation_z)

    identity = np.eye(2, dtype=np.float64)
    observation_matrix = np.asarray([1.0, 0.0], dtype=np.float64)
    state: np.ndarray | None = None
    covariance: np.ndarray | None = None

    for position, raw_observation in enumerate(observations):
        observation = float(raw_observation)
        variance = float(local_variance[position])
        adaptive_variance = (
            float(max(variance, config.epsilon))
            if np.isfinite(variance)
            else config.epsilon
        )
        elapsed = max(float(elapsed_bars[position]), 1.0)
        is_hard_gap = bool(hard_gap[position])
        phi_elapsed = float(config.phi**elapsed)
        level_step = 0.0 if is_hard_gap else elapsed
        transition = np.asarray(
            [[1.0, level_step], [0.0, phi_elapsed]],
            dtype=np.float64,
        )
        process_scale = (
            config.hard_gap_process_noise_multiplier if is_hard_gap else elapsed
        )
        process_covariance = np.diag(
            [
                config.level_process_noise_multiplier * adaptive_variance * process_scale,
                config.drift_process_noise_multiplier * adaptive_variance * process_scale,
            ]
        )

        if state is None or covariance is None:
            if not np.isfinite(observation):
                continue
            initial_state = np.asarray([observation, 0.0], dtype=np.float64)
            initial_covariance = np.diag(
                [
                    config.initial_covariance_multiplier * adaptive_variance,
                    config.initial_covariance_multiplier * adaptive_variance,
                ]
            )
            state = initial_state
            covariance = initial_covariance
            levels[position] = float(initial_state[0])
            drifts[position] = float(initial_state[1])
            drift_variances[position] = float(initial_covariance[1, 1])
            innovations[position] = 0.0
            innovation_z[position] = 0.0
            continue

        predicted_state = transition @ state
        predicted_covariance = transition @ covariance @ transition.T + process_covariance
        predicted_covariance = 0.5 * (predicted_covariance + predicted_covariance.T)

        if np.isfinite(observation):
            spread_value = float(spread_ratio[position])
            volatility_value = float(volatility_ratio[position])
            spread = spread_value if np.isfinite(spread_value) else 1.0
            volatility = (
                volatility_value if np.isfinite(volatility_value) else 1.0
            )
            spread_penalty = max(float(spread) - 1.0, 0.0)
            volatility_penalty = max(float(volatility) - 1.0, 0.0)
            observation_variance = config.observation_noise_multiplier * adaptive_variance
            observation_variance *= (
                1.0
                + config.spread_noise_multiplier * spread_penalty**2
                + config.volatility_noise_multiplier * volatility_penalty**2
            )
            observation_variance = max(float(observation_variance), config.epsilon)
            raw_innovation = float(observation - predicted_state[0])
            innovation_variance = float(predicted_covariance[0, 0] + observation_variance)
            innovation_scale = np.sqrt(max(innovation_variance, config.epsilon))
            clipped_innovation = float(
                np.clip(
                    raw_innovation,
                    -config.huber_threshold * innovation_scale,
                    config.huber_threshold * innovation_scale,
                )
            )
            gain = predicted_covariance[:, 0] / innovation_variance
            state = predicted_state + gain * clipped_innovation
            residual_operator = identity - np.outer(gain, observation_matrix)
            covariance = (
                residual_operator @ predicted_covariance @ residual_operator.T
                + observation_variance * np.outer(gain, gain)
            )
            innovations[position] = raw_innovation
            innovation_z[position] = raw_innovation / innovation_scale
        else:
            state = predicted_state
            covariance = predicted_covariance

        assert state is not None and covariance is not None
        stabilized_covariance = 0.5 * (covariance + covariance.T)
        stabilized_covariance[np.diag_indices_from(stabilized_covariance)] = np.maximum(
            stabilized_covariance.diagonal(),
            config.epsilon,
        )
        covariance = stabilized_covariance
        levels[position] = float(state[0])
        drifts[position] = float(state[1])
        drift_variances[position] = float(stabilized_covariance[1, 1])

    return KDSFilterResult(levels, drifts, drift_variances, innovations, innovation_z)


def _thresholded_sign(series: pd.Series, *, epsilon: float) -> pd.Series:
    values = np.sign(series).astype("float64")
    return values.mask(series.abs() <= epsilon, 0.0).where(series.notna())


__all__ = [
    "KDSFilterResult",
    "KDS_OUTPUT_COLUMNS",
    "add_kds_features",
]
