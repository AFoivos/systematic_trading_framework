from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Integral, Real
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.special import ndtr

from .common import (
    causal_baseline,
    compute_gap_diagnostics,
    prepare_market_data,
    safe_ratio,
    validate_bar_minutes,
)
from .config import RLVSConfig, resolve_rlvs_config


RLVS_OUTPUT_COLUMNS = (
    "rlv_log_variance",
    "rlv_variance",
    "rlv_sigma",
    "rlv_state_std",
    "rlv_state_uncertainty",
    "rlv_regime_baseline",
    "rlv_regime_dispersion",
    "rlv_regime_z",
    "rlv_prob_high",
    "rlv_innovation",
    "rlv_shock_z",
    "rlv_vol_of_vol",
    "rlv_vol_of_vol_ratio",
    "rlv_sigma_fast",
    "rlv_sigma_slow",
    "rlv_fast_slow_ratio",
    "rlv_term_structure",
    "rlv_forecast_5",
    "rlv_forecast_15",
    "rlv_forecast_30",
    "rlv_expected_move_5",
    "rlv_expected_move_15",
    "rlv_expected_move_30",
    "rlv_regime",
    "volatility_estimator_disagreement",
)


@dataclass(frozen=True)
class RLVSFilterResult:
    log_variance: np.ndarray
    state_variance: np.ndarray
    innovation: np.ndarray
    shock_z: np.ndarray


def add_rlvs_features(
    df: pd.DataFrame,
    *,
    preset: str = "balanced",
    config: RLVSConfig | Mapping[str, object] | None = None,
    bar_minutes: float = 1.0,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply the registered ``rlvs`` feature transformation.

    RLVS robustly combines close-to-close, Parkinson, and Rogers-Satchell
    variance measurements in log-variance space, then filters a causal
    mean-reverting latent log-variance state.

    YAML declaration::

        features:
          - step: rlvs
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
        Optional mapping of transparent RLVSConfig overrides, or RLVSConfig.
    bar_minutes:
        Explicit duration of one input bar in minutes. State transitions use
        elapsed bar steps, while gap reporting remains expressed in minutes.
    inplace:
        If true, append outputs to the supplied dataframe. Default: ``false``.
    """
    resolved = resolve_rlvs_config(config, preset=preset)
    resolved_bar_minutes = validate_bar_minutes(bar_minutes)
    market = prepare_market_data(df)
    gaps = compute_gap_diagnostics(
        df.index,
        expected_bar_minutes=resolved_bar_minutes,
    )
    out = df if inplace else df.copy()

    measurements, disagreement, observed_log_variance = _volatility_measurements(
        market.as_frame(),
        is_gap=gaps.is_gap,
        config=resolved,
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
    log_range = np.log(market.high / market.low)
    range_baseline = causal_baseline(
        log_range,
        window=resolved.range_baseline_window,
    )
    range_ratio = safe_ratio(
        log_range,
        range_baseline,
        epsilon=resolved.epsilon,
        zero_over_zero=1.0,
    )
    state_baseline = (
        observed_log_variance.ewm(
            span=resolved.state_baseline_span,
            adjust=False,
            min_periods=resolved.measurement_min_periods,
        )
        .mean()
        .shift(1)
    )
    filtered = _run_rlvs_filter(
        observed_log_variance.to_numpy(dtype=float),
        state_baseline.to_numpy(dtype=float),
        spread_ratio.to_numpy(dtype=float),
        disagreement.to_numpy(dtype=float),
        range_ratio.to_numpy(dtype=float),
        gaps.elapsed_bars.to_numpy(dtype=float),
        gaps.is_hard_gap.to_numpy(dtype=bool),
        config=resolved,
    )

    index = out.index
    latent_h = pd.Series(filtered.log_variance, index=index, dtype="float64")
    state_variance = pd.Series(filtered.state_variance, index=index, dtype="float64")
    state_std = np.sqrt(state_variance.clip(lower=0.0))
    latent_variance = pd.Series(
        np.exp(
            latent_h.clip(
                lower=resolved.min_log_variance,
                upper=resolved.max_log_variance,
            )
        ),
        index=index,
        dtype="float64",
    ).where(latent_h.notna())
    sigma = np.sqrt(latent_variance)

    regime_baseline = (
        latent_h.ewm(
            span=resolved.regime_baseline_span,
            adjust=False,
            min_periods=resolved.regime_min_periods,
        )
        .mean()
        .shift(1)
    )
    regime_dispersion = (
        latent_h.ewm(
            span=resolved.regime_baseline_span,
            adjust=False,
            min_periods=resolved.regime_min_periods,
        )
        .std(bias=True)
        .shift(1)
    )
    regime_z = (latent_h - regime_baseline) / np.sqrt(
        regime_dispersion.pow(2) + state_variance + resolved.epsilon
    )
    probability_high = pd.Series(
        ndtr(regime_z.to_numpy(dtype=float)),
        index=index,
        dtype="float64",
    ).where(regime_z.notna())
    state_uncertainty = (
        state_std / ((latent_h - regime_baseline).abs() + state_std + resolved.epsilon)
    ).clip(lower=0.0, upper=1.0)

    delta_h = latent_h.diff().where(~gaps.is_hard_gap)
    vol_of_vol = np.sqrt(
        delta_h.pow(2)
        .ewm(
            span=resolved.vol_of_vol_span,
            adjust=False,
            min_periods=resolved.measurement_min_periods,
        )
        .mean()
    )
    vol_of_vol_baseline = (
        vol_of_vol.ewm(
            span=resolved.vol_of_vol_baseline_span,
            adjust=False,
            min_periods=resolved.regime_min_periods,
        )
        .mean()
        .shift(1)
    )
    vol_of_vol_ratio = safe_ratio(
        vol_of_vol,
        vol_of_vol_baseline,
        epsilon=resolved.epsilon,
        zero_over_zero=1.0,
    )

    fast_h = latent_h.ewm(
        span=resolved.sigma_fast_span,
        adjust=False,
        min_periods=resolved.measurement_min_periods,
    ).mean()
    slow_h = latent_h.ewm(
        span=resolved.sigma_slow_span,
        adjust=False,
        min_periods=resolved.measurement_min_periods,
    ).mean()
    sigma_fast = np.exp(
        0.5
        * fast_h.clip(
            lower=resolved.min_log_variance,
            upper=resolved.max_log_variance,
        )
    ).where(fast_h.notna())
    sigma_slow = np.exp(
        0.5
        * slow_h.clip(
            lower=resolved.min_log_variance,
            upper=resolved.max_log_variance,
        )
    ).where(slow_h.notna())
    fast_slow_ratio = safe_ratio(
        sigma_fast,
        sigma_slow,
        epsilon=resolved.epsilon,
        zero_over_zero=1.0,
    )
    term_structure = np.log(fast_slow_ratio.where(fast_slow_ratio > 0.0))
    shock_z = pd.Series(filtered.shock_z, index=index, dtype="float64")
    regimes = _classify_regime(
        regime_z,
        shock_z=shock_z,
        vol_of_vol_ratio=vol_of_vol_ratio,
        config=resolved,
    )

    values: dict[str, pd.Series | np.ndarray] = {
        "rlv_log_variance": latent_h,
        "rlv_variance": latent_variance,
        "rlv_sigma": sigma,
        "rlv_state_std": state_std,
        "rlv_state_uncertainty": state_uncertainty,
        "rlv_regime_baseline": regime_baseline,
        "rlv_regime_dispersion": regime_dispersion,
        "rlv_regime_z": regime_z,
        "rlv_prob_high": probability_high.clip(lower=0.0, upper=1.0),
        "rlv_innovation": filtered.innovation,
        "rlv_shock_z": shock_z,
        "rlv_vol_of_vol": vol_of_vol,
        "rlv_vol_of_vol_ratio": vol_of_vol_ratio,
        "rlv_sigma_fast": sigma_fast,
        "rlv_sigma_slow": sigma_slow,
        "rlv_fast_slow_ratio": fast_slow_ratio,
        "rlv_term_structure": term_structure,
        "rlv_regime": regimes,
        "volatility_estimator_disagreement": disagreement,
    }
    for horizon in (5, 15, 30):
        forecast = sigma * np.sqrt(float(horizon))
        values[f"rlv_forecast_{horizon}"] = forecast
        values[f"rlv_expected_move_{horizon}"] = market.close * forecast

    for column in RLVS_OUTPUT_COLUMNS:
        out[column] = values[column]
    out.attrs["rlvs_measurement_components"] = tuple(measurements.columns)
    return out


def _volatility_measurements(
    midpoint: pd.DataFrame,
    *,
    is_gap: pd.Series,
    config: RLVSConfig,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    open_ = midpoint["mid_open"].astype(float)
    high = midpoint["mid_high"].astype(float)
    low = midpoint["mid_low"].astype(float)
    close = midpoint["mid_close"].astype(float)

    close_to_close = np.log(close / close.shift(1)).pow(2).where(~is_gap)
    parkinson = np.log(high / low).pow(2) / (4.0 * np.log(2.0))
    rogers_satchell = (
        np.log(high / open_) * np.log(high / close)
        + np.log(low / open_) * np.log(low / close)
    ).clip(lower=0.0)
    raw = pd.DataFrame(
        {
            "close_to_close_variance": close_to_close,
            "parkinson_variance": parkinson,
            "rogers_satchell_variance": rogers_satchell,
        },
        index=midpoint.index,
    )
    smoothed = raw.ewm(
        span=config.measurement_span,
        adjust=False,
        min_periods=config.measurement_min_periods,
    ).mean()
    # pandas EWM otherwise carries the prior estimate across a missing bar.
    # A latent prediction is allowed there, but it must not be presented to the
    # measurement update as if a new OHLC observation had arrived.
    smoothed = smoothed.where(raw.notna())
    log_measurements = np.log(smoothed + config.epsilon)
    disagreement = log_measurements.std(axis=1, ddof=0, skipna=True)
    disagreement = disagreement.where(log_measurements.notna().sum(axis=1) >= 2)
    observed = log_measurements.median(axis=1, skipna=True)
    observed = observed.where(log_measurements.notna().sum(axis=1) >= 2)
    return smoothed, disagreement.astype("float64"), observed.astype("float64")


def _run_rlvs_filter(
    observations: np.ndarray,
    baselines: np.ndarray,
    spread_ratio: np.ndarray,
    disagreement: np.ndarray,
    range_ratio: np.ndarray,
    elapsed_bars: np.ndarray,
    hard_gap: np.ndarray,
    *,
    config: RLVSConfig,
) -> RLVSFilterResult:
    size = len(observations)
    states = np.full(size, np.nan, dtype=np.float64)
    state_variances = np.full(size, np.nan, dtype=np.float64)
    innovations = np.full(size, np.nan, dtype=np.float64)
    shock_z = np.full(size, np.nan, dtype=np.float64)
    state: float | None = None
    covariance: float | None = None

    for position, raw_observation in enumerate(observations):
        observation = float(raw_observation)
        if state is None or covariance is None:
            if not np.isfinite(observation):
                continue
            state = float(
                np.clip(observation, config.min_log_variance, config.max_log_variance)
            )
            covariance = config.initial_state_variance
            states[position] = state
            state_variances[position] = covariance
            innovations[position] = 0.0
            shock_z[position] = 0.0
            continue

        assert state is not None and covariance is not None
        baseline_value = float(baselines[position])
        baseline = baseline_value if np.isfinite(baseline_value) else state
        elapsed = max(float(elapsed_bars[position]), 1.0)
        phi_elapsed = float(config.phi_vol**elapsed)
        predicted_state = float(baseline + phi_elapsed * (state - baseline))
        process_scale = (
            config.hard_gap_process_noise_multiplier
            if bool(hard_gap[position])
            else elapsed
        )
        predicted_covariance = float(
            phi_elapsed**2 * covariance + config.process_noise * process_scale
        )
        if np.isfinite(observation):
            spread_value = float(spread_ratio[position])
            disagreement_value = float(disagreement[position])
            range_value = float(range_ratio[position])
            spread = spread_value if np.isfinite(spread_value) else 1.0
            estimator_disagreement = (
                disagreement_value if np.isfinite(disagreement_value) else 0.0
            )
            range_level = range_value if np.isfinite(range_value) else 1.0
            spread_penalty = max(spread - 1.0, 0.0)
            anomaly_penalty = max(range_level - 1.0, 0.0)
            measurement_variance = config.measurement_noise * (
                1.0
                + config.spread_noise_multiplier * spread_penalty**2
                + config.disagreement_noise_multiplier * estimator_disagreement**2
                + config.anomaly_noise_multiplier * anomaly_penalty**2
            )
            measurement_variance = max(float(measurement_variance), config.epsilon)
            innovation = float(observation - predicted_state)
            innovation_variance = predicted_covariance + measurement_variance
            scale = np.sqrt(max(innovation_variance, config.epsilon))
            clipped_innovation = float(
                np.clip(
                    innovation,
                    -config.huber_threshold * scale,
                    config.huber_threshold * scale,
                )
            )
            gain = predicted_covariance / innovation_variance
            state = predicted_state + gain * clipped_innovation
            covariance = (
                (1.0 - gain) ** 2 * predicted_covariance
                + gain**2 * measurement_variance
            )
            innovations[position] = innovation
            shock_z[position] = innovation / scale
        else:
            state = predicted_state
            covariance = predicted_covariance

        state = float(np.clip(state, config.min_log_variance, config.max_log_variance))
        covariance = max(float(covariance), config.epsilon)
        states[position] = state
        state_variances[position] = covariance

    return RLVSFilterResult(states, state_variances, innovations, shock_z)


def _classify_regime(
    regime_z: pd.Series,
    *,
    shock_z: pd.Series,
    vol_of_vol_ratio: pd.Series,
    config: RLVSConfig,
) -> pd.Series:
    regimes = pd.Series(pd.NA, index=regime_z.index, dtype="string")
    ready = regime_z.notna()
    regimes.loc[ready & (regime_z < config.low_regime_z)] = "low"
    regimes.loc[
        ready
        & (regime_z >= config.low_regime_z)
        & (regime_z <= config.high_regime_z)
    ] = "normal"
    regimes.loc[
        ready
        & (regime_z > config.high_regime_z)
        & (regime_z <= config.extreme_regime_z)
    ] = "high"
    regimes.loc[
        ready
        & (
            (regime_z > config.extreme_regime_z)
            | (shock_z.abs() >= config.extreme_shock_z)
        )
    ] = "extreme"
    transition = (
        ready
        & regime_z.between(config.low_regime_z, config.high_regime_z)
        & (vol_of_vol_ratio >= config.transition_vol_of_vol_ratio)
        & (shock_z.abs() < config.extreme_shock_z)
    )
    regimes.loc[transition] = "transition"
    return regimes


@dataclass
class HARVolatilityForecaster:
    """
    Explicitly fitted HAR-style latent-volatility forecaster.

    ``fit`` must receive only a training fold. If ``target`` is omitted, the
    class creates an in-fold endpoint target with ``shift(-horizon)``; rows
    whose label would fall beyond the supplied training frame are discarded.
    ``transform`` never changes fitted coefficients.
    """

    horizon: int = 15
    windows: tuple[int, ...] = (5, 15, 60, 240)
    ridge: float = 1e-8
    log_variance_col: str = "rlv_log_variance"
    coefficients_: np.ndarray | None = field(default=None, init=False, repr=False)
    feature_names_: tuple[str, ...] | None = field(default=None, init=False)
    training_rows_: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if isinstance(self.horizon, bool) or not isinstance(self.horizon, Integral) or self.horizon <= 0:
            raise ValueError("horizon must be a positive integer.")
        if not isinstance(self.windows, tuple) or not self.windows:
            raise ValueError("windows must be a non-empty tuple of positive integers.")
        if any(
            isinstance(window, bool) or not isinstance(window, Integral) or int(window) <= 0
            for window in self.windows
        ):
            raise ValueError("windows must contain positive integers.")
        if (
            isinstance(self.ridge, bool)
            or not isinstance(self.ridge, Real)
            or not np.isfinite(float(self.ridge))
            or float(self.ridge) < 0.0
        ):
            raise ValueError("ridge must be a finite number >= 0.")
        if not isinstance(self.log_variance_col, str) or not self.log_variance_col.strip():
            raise ValueError("log_variance_col must be a non-empty string.")

    def fit(
        self,
        frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> HARVolatilityForecaster:
        design = self._design(frame)
        if target is None:
            target_values = frame[self.log_variance_col].astype(float).shift(-self.horizon)
        else:
            target_values = target.reindex(frame.index).astype(float)
        joined = design.join(target_values.rename("__target__")).replace(
            [np.inf, -np.inf],
            np.nan,
        )
        joined = joined.dropna()
        if len(joined) <= design.shape[1]:
            raise ValueError("Insufficient finite training rows for HAR volatility fit.")
        x = joined[design.columns].to_numpy(dtype=float)
        y = joined["__target__"].to_numpy(dtype=float)
        x_with_intercept = np.column_stack([np.ones(len(x), dtype=float), x])
        penalty = np.eye(x_with_intercept.shape[1], dtype=float)
        penalty[0, 0] = 0.0
        gram = x_with_intercept.T @ x_with_intercept + float(self.ridge) * penalty
        rhs = x_with_intercept.T @ y
        self.coefficients_ = np.linalg.solve(gram, rhs)
        self.feature_names_ = tuple(design.columns)
        self.training_rows_ = len(joined)
        return self

    def transform(self, frame: pd.DataFrame) -> pd.Series:
        if self.coefficients_ is None or self.feature_names_ is None:
            raise RuntimeError("HARVolatilityForecaster must be fitted before transform.")
        design = self._design(frame)
        if tuple(design.columns) != self.feature_names_:
            raise RuntimeError("HAR design columns do not match the fitted model.")
        output = pd.Series(np.nan, index=frame.index, dtype="float64")
        valid = design.replace([np.inf, -np.inf], np.nan).notna().all(axis=1)
        if bool(valid.any()):
            x = design.loc[valid].to_numpy(dtype=float)
            predicted_log_variance = self.coefficients_[0] + x @ self.coefficients_[1:]
            predicted_sigma = np.exp(
                0.5 * np.clip(predicted_log_variance, -50.0, 5.0)
            )
            output.loc[valid] = predicted_sigma * np.sqrt(float(self.horizon))
        output.name = f"rlv_har_forecast_{self.horizon}"
        return output

    def _design(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self.log_variance_col not in frame.columns:
            raise KeyError(f"Missing HAR input column: {self.log_variance_col}.")
        latent = frame[self.log_variance_col].astype(float)
        design = pd.DataFrame(
            {f"har_current_{self.log_variance_col}": latent},
            index=frame.index,
        )
        for window in self.windows:
            design[f"har_mean_{int(window)}"] = latent.rolling(
                int(window),
                min_periods=int(window),
            ).mean()
        return design


__all__ = [
    "HARVolatilityForecaster",
    "RLVSFilterResult",
    "RLVS_OUTPUT_COLUMNS",
    "add_rlvs_features",
]
