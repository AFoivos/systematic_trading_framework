from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from numbers import Integral, Real
from typing import Any, ClassVar, Mapping, TypeVar, cast

import numpy as np


PRESET_NAMES = ("conservative", "balanced", "responsive")


def _finite_float(value: object, *, field: str, lower: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a finite number.")
    resolved = float(value)
    if not np.isfinite(resolved):
        raise ValueError(f"{field} must be a finite number.")
    if lower is not None and resolved <= lower:
        raise ValueError(f"{field} must be > {lower}.")
    return resolved


def _positive_int(value: object, *, field: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}.")
    return int(value)


def _probability(value: object, *, field: str, inclusive: bool = True) -> float:
    resolved = _finite_float(value, field=field)
    valid = 0.0 <= resolved <= 1.0 if inclusive else 0.0 < resolved < 1.0
    if not valid:
        bounds = "[0, 1]" if inclusive else "(0, 1)"
        raise ValueError(f"{field} must be in {bounds}.")
    return resolved


ConfigT = TypeVar("ConfigT", bound="_PresetConfig")


class _PresetConfig:
    PRESETS: ClassVar[Mapping[str, Mapping[str, object]]]

    @classmethod
    def from_preset(
        cls: type[ConfigT],
        preset: str = "balanced",
        overrides: Mapping[str, object] | None = None,
    ) -> ConfigT:
        if not isinstance(preset, str) or preset not in cls.PRESETS:
            raise ValueError(f"preset must be one of: {', '.join(PRESET_NAMES)}.")
        allowed = {field.name for field in fields(cast(Any, cls))}
        supplied = dict(overrides or {})
        unknown = sorted(set(supplied).difference(allowed))
        if unknown:
            raise ValueError(f"Unsupported {cls.__name__} fields: {unknown}.")
        values = dict(cls.PRESETS[preset])
        values.update(supplied)
        return cls(**values)

    def to_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(cast(Any, self)))


@dataclass(frozen=True)
class KDSConfig(_PresetConfig):
    phi: float = 0.985
    level_process_noise_multiplier: float = 0.05
    drift_process_noise_multiplier: float = 0.005
    observation_noise_multiplier: float = 0.50
    spread_noise_multiplier: float = 1.00
    volatility_noise_multiplier: float = 0.75
    huber_threshold: float = 3.0
    local_volatility_span: int = 30
    local_volatility_min_periods: int = 5
    volatility_baseline_window: int = 1440
    spread_baseline_window: int = 1440
    kadx_window: int = 14
    activity_scale: float = 1.0
    initial_covariance_multiplier: float = 10.0
    min_directional_activity: float = 1e-8
    hard_gap_process_noise_multiplier: float = 25.0
    epsilon: float = 1e-12

    PRESETS: ClassVar[Mapping[str, Mapping[str, object]]] = {
        "conservative": {
            "phi": 0.990,
            "level_process_noise_multiplier": 0.025,
            "drift_process_noise_multiplier": 0.0025,
            "observation_noise_multiplier": 0.75,
            "spread_noise_multiplier": 1.50,
            "volatility_noise_multiplier": 1.00,
            "huber_threshold": 2.5,
            "local_volatility_span": 60,
            "local_volatility_min_periods": 10,
            "volatility_baseline_window": 2880,
            "spread_baseline_window": 2880,
            "kadx_window": 28,
            "activity_scale": 1.25,
            "initial_covariance_multiplier": 10.0,
            "min_directional_activity": 1e-8,
            "hard_gap_process_noise_multiplier": 20.0,
            "epsilon": 1e-12,
        },
        "balanced": {},
        "responsive": {
            "phi": 0.970,
            "level_process_noise_multiplier": 0.10,
            "drift_process_noise_multiplier": 0.012,
            "observation_noise_multiplier": 0.35,
            "spread_noise_multiplier": 0.75,
            "volatility_noise_multiplier": 0.50,
            "huber_threshold": 3.5,
            "local_volatility_span": 15,
            "local_volatility_min_periods": 3,
            "volatility_baseline_window": 720,
            "spread_baseline_window": 720,
            "kadx_window": 7,
            "activity_scale": 0.80,
            "initial_covariance_multiplier": 8.0,
            "min_directional_activity": 1e-8,
            "hard_gap_process_noise_multiplier": 20.0,
            "epsilon": 1e-12,
        },
    }

    def __post_init__(self) -> None:
        phi = _probability(self.phi, field="phi")
        if phi == 0.0:
            raise ValueError("phi must be > 0.")
        for name in (
            "level_process_noise_multiplier",
            "drift_process_noise_multiplier",
            "observation_noise_multiplier",
            "activity_scale",
            "initial_covariance_multiplier",
            "min_directional_activity",
            "hard_gap_process_noise_multiplier",
            "epsilon",
        ):
            _finite_float(getattr(self, name), field=name, lower=0.0)
        for name in ("spread_noise_multiplier", "volatility_noise_multiplier"):
            value = _finite_float(getattr(self, name), field=name)
            if value < 0.0:
                raise ValueError(f"{name} must be >= 0.")
        _finite_float(self.huber_threshold, field="huber_threshold", lower=0.0)
        for name in (
            "local_volatility_span",
            "local_volatility_min_periods",
            "volatility_baseline_window",
            "spread_baseline_window",
            "kadx_window",
        ):
            _positive_int(getattr(self, name), field=name)
        if self.local_volatility_min_periods > self.local_volatility_span:
            raise ValueError("local_volatility_min_periods must be <= local_volatility_span.")


@dataclass(frozen=True)
class RLVSConfig(_PresetConfig):
    phi_vol: float = 0.985
    process_noise: float = 0.025
    measurement_noise: float = 0.20
    spread_noise_multiplier: float = 0.75
    disagreement_noise_multiplier: float = 0.50
    anomaly_noise_multiplier: float = 0.25
    huber_threshold: float = 3.0
    measurement_span: int = 15
    measurement_min_periods: int = 3
    state_baseline_span: int = 1440
    spread_baseline_window: int = 1440
    range_baseline_window: int = 1440
    regime_baseline_span: int = 1440
    regime_min_periods: int = 60
    vol_of_vol_span: int = 30
    vol_of_vol_baseline_span: int = 720
    sigma_fast_span: int = 15
    sigma_slow_span: int = 240
    initial_state_variance: float = 1.0
    min_log_variance: float = -50.0
    max_log_variance: float = 5.0
    transition_vol_of_vol_ratio: float = 1.5
    low_regime_z: float = -1.0
    high_regime_z: float = 1.0
    extreme_regime_z: float = 2.5
    extreme_shock_z: float = 3.0
    hard_gap_process_noise_multiplier: float = 25.0
    epsilon: float = 1e-12

    PRESETS: ClassVar[Mapping[str, Mapping[str, object]]] = {
        "conservative": {
            "phi_vol": 0.992,
            "process_noise": 0.0125,
            "measurement_noise": 0.30,
            "spread_noise_multiplier": 1.00,
            "disagreement_noise_multiplier": 0.75,
            "anomaly_noise_multiplier": 0.40,
            "huber_threshold": 2.5,
            "measurement_span": 30,
            "measurement_min_periods": 6,
            "state_baseline_span": 2880,
            "spread_baseline_window": 2880,
            "range_baseline_window": 2880,
            "regime_baseline_span": 2880,
            "regime_min_periods": 120,
            "vol_of_vol_span": 60,
            "vol_of_vol_baseline_span": 1440,
            "sigma_fast_span": 30,
            "sigma_slow_span": 480,
            "initial_state_variance": 1.0,
            "min_log_variance": -50.0,
            "max_log_variance": 5.0,
            "transition_vol_of_vol_ratio": 1.75,
            "low_regime_z": -1.0,
            "high_regime_z": 1.0,
            "extreme_regime_z": 2.5,
            "extreme_shock_z": 3.0,
            "hard_gap_process_noise_multiplier": 20.0,
            "epsilon": 1e-12,
        },
        "balanced": {},
        "responsive": {
            "phi_vol": 0.960,
            "process_noise": 0.060,
            "measurement_noise": 0.14,
            "spread_noise_multiplier": 0.50,
            "disagreement_noise_multiplier": 0.35,
            "anomaly_noise_multiplier": 0.15,
            "huber_threshold": 3.5,
            "measurement_span": 7,
            "measurement_min_periods": 2,
            "state_baseline_span": 720,
            "spread_baseline_window": 720,
            "range_baseline_window": 720,
            "regime_baseline_span": 720,
            "regime_min_periods": 30,
            "vol_of_vol_span": 15,
            "vol_of_vol_baseline_span": 360,
            "sigma_fast_span": 7,
            "sigma_slow_span": 120,
            "initial_state_variance": 1.0,
            "min_log_variance": -50.0,
            "max_log_variance": 5.0,
            "transition_vol_of_vol_ratio": 1.25,
            "low_regime_z": -1.0,
            "high_regime_z": 1.0,
            "extreme_regime_z": 2.5,
            "extreme_shock_z": 3.0,
            "hard_gap_process_noise_multiplier": 30.0,
            "epsilon": 1e-12,
        },
    }

    def __post_init__(self) -> None:
        phi = _probability(self.phi_vol, field="phi_vol")
        if phi == 0.0:
            raise ValueError("phi_vol must be > 0.")
        for name in (
            "process_noise",
            "measurement_noise",
            "huber_threshold",
            "initial_state_variance",
            "transition_vol_of_vol_ratio",
            "hard_gap_process_noise_multiplier",
            "epsilon",
        ):
            _finite_float(getattr(self, name), field=name, lower=0.0)
        for name in (
            "spread_noise_multiplier",
            "disagreement_noise_multiplier",
            "anomaly_noise_multiplier",
        ):
            value = _finite_float(getattr(self, name), field=name)
            if value < 0.0:
                raise ValueError(f"{name} must be >= 0.")
        for name in (
            "measurement_span",
            "measurement_min_periods",
            "state_baseline_span",
            "spread_baseline_window",
            "range_baseline_window",
            "regime_baseline_span",
            "regime_min_periods",
            "vol_of_vol_span",
            "vol_of_vol_baseline_span",
            "sigma_fast_span",
            "sigma_slow_span",
        ):
            _positive_int(getattr(self, name), field=name)
        if self.measurement_min_periods > self.measurement_span:
            raise ValueError("measurement_min_periods must be <= measurement_span.")
        if self.sigma_fast_span >= self.sigma_slow_span:
            raise ValueError("sigma_fast_span must be < sigma_slow_span.")
        min_log_variance = _finite_float(self.min_log_variance, field="min_log_variance")
        max_log_variance = _finite_float(self.max_log_variance, field="max_log_variance")
        if min_log_variance >= max_log_variance:
            raise ValueError("min_log_variance must be < max_log_variance.")
        thresholds = (
            _finite_float(self.low_regime_z, field="low_regime_z"),
            _finite_float(self.high_regime_z, field="high_regime_z"),
            _finite_float(self.extreme_regime_z, field="extreme_regime_z"),
        )
        if not thresholds[0] < thresholds[1] < thresholds[2]:
            raise ValueError("Regime z thresholds must satisfy low < high < extreme.")
        _finite_float(self.extreme_shock_z, field="extreme_shock_z", lower=0.0)


@dataclass(frozen=True)
class LMDSConfig(_PresetConfig):
    impulse_horizons: tuple[int, ...] = (3, 5, 15, 30, 60)
    impulse_weights: tuple[float, ...] = (0.10, 0.20, 0.30, 0.25, 0.15)
    efficiency_horizons: tuple[int, ...] = (5, 15, 30)
    efficiency_weights: tuple[float, ...] = (0.25, 0.40, 0.35)
    momentum_weights: tuple[float, ...] = (0.50, 0.30, 0.20)
    impulse_scale: float = 1.5
    acceleration_scale: float = 2.0
    exhaustion_scale: float = 2.0
    raw_impulse_clip: float = 20.0
    persistence_span: int = 15
    persistence_min_periods: int = 3
    exhaustion_shock_weight: float = 0.25
    exhaustion_vol_of_vol_weight: float = 0.15
    exhaustion_shock_scale: float = 3.0
    exhaustion_vol_of_vol_scale: float = 1.0
    direction_epsilon: float = 1e-6
    epsilon: float = 1e-12

    PRESETS: ClassVar[Mapping[str, Mapping[str, object]]] = {
        "conservative": {
            "impulse_horizons": (3, 5, 15, 30, 60),
            "impulse_weights": (0.05, 0.15, 0.30, 0.30, 0.20),
            "efficiency_horizons": (5, 15, 30),
            "efficiency_weights": (0.15, 0.40, 0.45),
            "momentum_weights": (0.55, 0.20, 0.25),
            "impulse_scale": 2.0,
            "acceleration_scale": 2.5,
            "exhaustion_scale": 2.5,
            "raw_impulse_clip": 20.0,
            "persistence_span": 30,
            "persistence_min_periods": 6,
            "exhaustion_shock_weight": 0.25,
            "exhaustion_vol_of_vol_weight": 0.15,
            "exhaustion_shock_scale": 3.0,
            "exhaustion_vol_of_vol_scale": 1.0,
            "direction_epsilon": 1e-6,
            "epsilon": 1e-12,
        },
        "balanced": {},
        "responsive": {
            "impulse_horizons": (3, 5, 15, 30, 60),
            "impulse_weights": (0.20, 0.25, 0.30, 0.15, 0.10),
            "efficiency_horizons": (5, 15, 30),
            "efficiency_weights": (0.40, 0.40, 0.20),
            "momentum_weights": (0.45, 0.40, 0.15),
            "impulse_scale": 1.0,
            "acceleration_scale": 1.5,
            "exhaustion_scale": 1.5,
            "raw_impulse_clip": 20.0,
            "persistence_span": 7,
            "persistence_min_periods": 2,
            "exhaustion_shock_weight": 0.30,
            "exhaustion_vol_of_vol_weight": 0.20,
            "exhaustion_shock_scale": 2.5,
            "exhaustion_vol_of_vol_scale": 0.75,
            "direction_epsilon": 1e-6,
            "epsilon": 1e-12,
        },
    }

    def __post_init__(self) -> None:
        if tuple(self.impulse_horizons) != (3, 5, 15, 30, 60):
            raise ValueError("impulse_horizons must be exactly (3, 5, 15, 30, 60).")
        if tuple(self.efficiency_horizons) != (5, 15, 30):
            raise ValueError("efficiency_horizons must be exactly (5, 15, 30).")
        _validate_weights(
            self.impulse_weights,
            expected_length=len(self.impulse_horizons),
            field="impulse_weights",
        )
        _validate_weights(
            self.efficiency_weights,
            expected_length=len(self.efficiency_horizons),
            field="efficiency_weights",
        )
        _validate_weights(self.momentum_weights, expected_length=3, field="momentum_weights")
        for name in (
            "impulse_scale",
            "acceleration_scale",
            "exhaustion_scale",
            "raw_impulse_clip",
            "exhaustion_shock_scale",
            "exhaustion_vol_of_vol_scale",
            "direction_epsilon",
            "epsilon",
        ):
            _finite_float(getattr(self, name), field=name, lower=0.0)
        for name in ("exhaustion_shock_weight", "exhaustion_vol_of_vol_weight"):
            _probability(getattr(self, name), field=name)
        _positive_int(self.persistence_span, field="persistence_span")
        _positive_int(self.persistence_min_periods, field="persistence_min_periods")
        if self.persistence_min_periods > self.persistence_span:
            raise ValueError("persistence_min_periods must be <= persistence_span.")


def _validate_weights(
    weights: tuple[float, ...],
    *,
    expected_length: int,
    field: str,
) -> None:
    if not isinstance(weights, tuple) or len(weights) != expected_length:
        raise ValueError(f"{field} must be a tuple with {expected_length} entries.")
    resolved = np.asarray(weights, dtype=float)
    if not np.isfinite(resolved).all() or (resolved < 0.0).any():
        raise ValueError(f"{field} must contain finite non-negative values.")
    if not np.isclose(float(resolved.sum()), 1.0, rtol=0.0, atol=1e-12):
        raise ValueError(f"{field} must sum to one.")


def resolve_kds_config(
    config: KDSConfig | Mapping[str, object] | None = None,
    *,
    preset: str = "balanced",
) -> KDSConfig:
    if isinstance(config, KDSConfig):
        if preset != "balanced":
            raise ValueError("preset cannot be combined with an instantiated KDSConfig.")
        return config
    return KDSConfig.from_preset(preset, config)


def resolve_rlvs_config(
    config: RLVSConfig | Mapping[str, object] | None = None,
    *,
    preset: str = "balanced",
) -> RLVSConfig:
    if isinstance(config, RLVSConfig):
        if preset != "balanced":
            raise ValueError("preset cannot be combined with an instantiated RLVSConfig.")
        return config
    return RLVSConfig.from_preset(preset, config)


def resolve_lmds_config(
    config: LMDSConfig | Mapping[str, object] | None = None,
    *,
    preset: str = "balanced",
) -> LMDSConfig:
    if isinstance(config, LMDSConfig):
        if preset != "balanced":
            raise ValueError("preset cannot be combined with an instantiated LMDSConfig.")
        return config
    if config is None:
        return LMDSConfig.from_preset(preset)
    normalized = {
        key: tuple(value) if key.endswith(("_weights", "_horizons")) and isinstance(value, list) else value
        for key, value in dict(config).items()
    }
    return LMDSConfig.from_preset(preset, normalized)


def with_overrides(config: ConfigT, **overrides: object) -> ConfigT:
    """Return a validated copy of a system configuration."""
    return cast(ConfigT, replace(cast(Any, config), **overrides))


__all__ = [
    "KDSConfig",
    "LMDSConfig",
    "PRESET_NAMES",
    "RLVSConfig",
    "resolve_kds_config",
    "resolve_lmds_config",
    "resolve_rlvs_config",
    "with_overrides",
]
