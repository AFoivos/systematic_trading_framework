"""Framework-owned contracts for bounded PyBroker ML walk-forward screening."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.research.contracts import (
    ResearchContractError,
    _freeze_json_mapping,
    _require_non_empty,
    _require_unique_strings,
)


PYBROKER_CAPABILITIES = frozenset(
    {
        "ml_walk_forward",
        "supervised_model_screening",
        "oos_prediction_screening",
        "chronological_fold_evaluation",
        "probability_signal_screening",
    }
)


class PyBrokerBackendError(ResearchContractError):
    """Base error for fail-closed PyBroker adapter contracts."""


class PyBrokerUnsupportedSemanticsError(PyBrokerBackendError):
    """Raised when Phase 3B cannot reproduce requested semantics safely."""


class PyBrokerInputError(PyBrokerBackendError):
    """Raised for invalid or temporally ambiguous framework inputs."""


class PyBrokerResourceLimitError(PyBrokerBackendError):
    """Raised before execution when the bounded initial search is too large."""


class PyBrokerRuntimeError(PyBrokerBackendError):
    """Raised when PyBroker fails after validated contract mapping."""


def _positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PyBrokerInputError(f"{field_name} must be an integer >= 1.")
    return value


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PyBrokerInputError(f"{field_name} must be an integer >= 0.")
    return value


def _non_negative_rate(value: object, *, field_name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        or float(value) < 0.0
    ):
        raise PyBrokerInputError(f"{field_name} must be finite and >= 0.")
    return float(value)


def _probability(value: object, *, field_name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        or not 0.0 < float(value) < 1.0
    ):
        raise PyBrokerInputError(f"{field_name} must be finite and in (0, 1).")
    return float(value)


@dataclass(frozen=True)
class PyBrokerResearchData:
    """Framework-produced features and target supplied to the adapter.

    The adapter never builds an indicator universe or derives a target.  The
    caller supplies registry-produced columns together with explicit target
    metadata, including the future horizon needed by the canonical purge rule.
    """

    frame: pd.DataFrame
    asset: str
    timeframe: str
    feature_columns: tuple[str, ...]
    target_column: str
    target_family: str
    target_horizon: int
    checks: Mapping[str, bool]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.frame, pd.DataFrame) or self.frame.empty:
            raise PyBrokerInputError(
                "PyBroker research data must be a non-empty pandas DataFrame."
            )
        if not isinstance(self.frame.index, pd.DatetimeIndex):
            raise PyBrokerInputError(
                "PyBroker research data requires a DatetimeIndex."
            )
        if self.frame.index.tz is None:
            raise PyBrokerInputError(
                "PyBroker research-data timestamps must be timezone-aware."
            )
        if not self.frame.index.is_monotonic_increasing:
            raise PyBrokerInputError(
                "PyBroker research-data timestamps must be monotonic."
            )
        if not self.frame.index.is_unique:
            raise PyBrokerInputError(
                "PyBroker research-data timestamps must be unique."
            )
        object.__setattr__(
            self,
            "asset",
            _require_non_empty(self.asset, field_name="asset"),
        )
        object.__setattr__(
            self,
            "timeframe",
            _require_non_empty(self.timeframe, field_name="timeframe"),
        )
        object.__setattr__(
            self,
            "target_column",
            _require_non_empty(self.target_column, field_name="target_column"),
        )
        object.__setattr__(
            self,
            "target_family",
            _require_non_empty(self.target_family, field_name="target_family"),
        )
        object.__setattr__(
            self,
            "feature_columns",
            _require_unique_strings(
                self.feature_columns,
                field_name="feature_columns",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self,
            "target_horizon",
            _positive_int(self.target_horizon, field_name="target_horizon"),
        )
        if self.target_column in self.feature_columns:
            raise PyBrokerInputError(
                "target_column cannot also be a model feature."
            )
        required = {
            "open",
            "close",
            self.target_column,
            *self.feature_columns,
        }
        missing = sorted(required.difference(self.frame.columns))
        if missing:
            raise PyBrokerInputError(
                f"PyBroker research data is missing required columns: {missing}."
            )
        for column in ("open", "close"):
            values = pd.to_numeric(self.frame[column], errors="coerce")
            numeric = values.to_numpy(dtype=float)
            if not np.isfinite(numeric).all() or bool((numeric <= 0.0).any()):
                raise PyBrokerInputError(
                    f"Market-data column {column!r} must be finite and positive."
                )
        for column in self.feature_columns:
            numeric = pd.to_numeric(self.frame[column], errors="coerce")
            introduced_missing = numeric.isna() & self.frame[column].notna()
            if bool(introduced_missing.any()):
                raise PyBrokerInputError(
                    f"Feature column {column!r} must contain only numeric values or NaN."
                )
            finite = numeric.dropna().to_numpy(dtype=float)
            if finite.size and not np.isfinite(finite).all():
                raise PyBrokerInputError(
                    f"Feature column {column!r} contains non-finite values."
                )
        target = pd.to_numeric(self.frame[self.target_column], errors="coerce")
        introduced_target_missing = target.isna() & self.frame[self.target_column].notna()
        if bool(introduced_target_missing.any()):
            raise PyBrokerInputError(
                "Classification target must contain only numeric labels or NaN."
            )
        observed_labels = target.dropna().to_numpy(dtype=float)
        if observed_labels.size and not np.isfinite(observed_labels).all():
            raise PyBrokerInputError("Classification target contains non-finite labels.")
        labels = set(observed_labels.tolist())
        if not labels or not labels.issubset({0.0, 1.0}):
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B initially supports only binary classification targets {0, 1}."
            )
        if not isinstance(self.checks, Mapping):
            raise PyBrokerInputError("research-data checks must be a mapping.")
        normalized_checks: dict[str, bool] = {}
        for raw_name, raw_value in self.checks.items():
            name = _require_non_empty(raw_name, field_name="research-data check")
            if not isinstance(raw_value, bool):
                raise PyBrokerInputError(
                    f"research-data check {name!r} must be boolean."
                )
            normalized_checks[name] = raw_value
        object.__setattr__(self, "checks", MappingProxyType(normalized_checks))
        object.__setattr__(
            self,
            "metadata",
            _freeze_json_mapping(self.metadata, field_name="research-data metadata"),
        )
        object.__setattr__(self, "frame", self.frame.copy(deep=False))


@dataclass(frozen=True)
class PyBrokerFoldPolicy:
    """STF-authoritative purged chronological walk-forward policy."""

    train_size: int
    test_size: int
    step_size: int | None = None
    purge_bars: int | None = None
    embargo_bars: int = 0
    expanding: bool = True
    max_folds: int | None = None
    minimum_train_rows: int = 2
    single_class_policy: Literal["invalidate_trial"] = "invalidate_trial"
    refit_per_fold: Literal[True] = True
    refit_frequency: Literal["per_fold"] = "per_fold"

    def __post_init__(self) -> None:
        for field_name in ("train_size", "test_size", "minimum_train_rows"):
            object.__setattr__(
                self,
                field_name,
                _positive_int(getattr(self, field_name), field_name=field_name),
            )
        if self.step_size is not None:
            object.__setattr__(
                self,
                "step_size",
                _positive_int(self.step_size, field_name="step_size"),
            )
        if self.purge_bars is not None:
            object.__setattr__(
                self,
                "purge_bars",
                _non_negative_int(self.purge_bars, field_name="purge_bars"),
            )
        object.__setattr__(
            self,
            "embargo_bars",
            _non_negative_int(self.embargo_bars, field_name="embargo_bars"),
        )
        if self.max_folds is not None:
            object.__setattr__(
                self,
                "max_folds",
                _positive_int(self.max_folds, field_name="max_folds"),
            )
        if not isinstance(self.expanding, bool):
            raise PyBrokerInputError("expanding must be boolean.")
        if self.single_class_policy != "invalidate_trial":
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B supports only single_class_policy='invalidate_trial'."
            )
        if self.refit_per_fold is not True or self.refit_frequency != "per_fold":
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B requires refit_per_fold=true and refit_frequency='per_fold'."
            )

    def resolved_purge_bars(self, *, target_horizon: int) -> int:
        horizon = _positive_int(target_horizon, field_name="target_horizon")
        purge = horizon if self.purge_bars is None else self.purge_bars
        if purge < horizon:
            raise PyBrokerInputError(
                "purge_bars is too small for the target horizon; "
                "set purge_bars >= target_horizon."
            )
        return purge

    def to_dict(self, *, target_horizon: int) -> dict[str, Any]:
        return {
            "method": "purged",
            "train_size": self.train_size,
            "test_size": self.test_size,
            "step_size": self.step_size or self.test_size,
            "purge_bars": self.resolved_purge_bars(
                target_horizon=target_horizon
            ),
            "embargo_bars": self.embargo_bars,
            "expanding": self.expanding,
            "max_folds": self.max_folds,
            "minimum_train_rows": self.minimum_train_rows,
            "single_class_policy": self.single_class_policy,
            "shuffle": False,
            "refit_per_fold": self.refit_per_fold,
            "refit_frequency": self.refit_frequency,
        }


@dataclass(frozen=True)
class PyBrokerPreprocessingPolicy:
    """The supported fold-local preprocessing surface."""

    scaler: Literal["none", "standard", "robust"] = "standard"
    missing_values: Literal["drop_required_features"] = "drop_required_features"
    imputation: Literal["unsupported"] = "unsupported"
    calibration: Literal["unsupported"] = "unsupported"
    feature_selection: Literal["unsupported"] = "unsupported"

    def __post_init__(self) -> None:
        if self.scaler not in {"none", "standard", "robust"}:
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B scaler must be one of: none, standard, robust."
            )
        if self.missing_values != "drop_required_features":
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B supports only deterministic dropping of rows with missing required features."
            )
        for field_name in ("imputation", "calibration", "feature_selection"):
            if getattr(self, field_name) != "unsupported":
                raise PyBrokerUnsupportedSemanticsError(
                    f"Phase 3B {field_name} is unsupported until a fold-safe contract is added."
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scaler": self.scaler,
            "fit_scope": "train_fold_only",
            "missing_values": self.missing_values,
            "imputation": self.imputation,
            "calibration": self.calibration,
            "feature_selection": self.feature_selection,
        }


@dataclass(frozen=True)
class PyBrokerSignalPolicy:
    """Configuration-driven mapping from OOS probability to long/flat intent."""

    signal_family: Literal["meta_probability_side"] = "meta_probability_side"
    threshold_parameter: str | None = None
    fixed_threshold: float | None = None
    rule: Literal["probability_gte_threshold"] = "probability_gte_threshold"
    direction: Literal["long_only"] = "long_only"

    def __post_init__(self) -> None:
        if self.signal_family != "meta_probability_side":
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B supports only the framework meta_probability_side signal family."
            )
        if self.rule != "probability_gte_threshold" or self.direction != "long_only":
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B supports only probability_gte_threshold long-only signals."
            )
        has_parameter = self.threshold_parameter is not None
        has_fixed = self.fixed_threshold is not None
        if has_parameter == has_fixed:
            raise PyBrokerInputError(
                "Declare exactly one of threshold_parameter or fixed_threshold."
            )
        if has_parameter:
            object.__setattr__(
                self,
                "threshold_parameter",
                _require_non_empty(
                    self.threshold_parameter,
                    field_name="threshold_parameter",
                ),
            )
        if has_fixed:
            object.__setattr__(
                self,
                "fixed_threshold",
                _probability(self.fixed_threshold, field_name="fixed_threshold"),
            )

    def resolve_threshold(self, parameters: Mapping[str, Any]) -> float:
        value = (
            self.fixed_threshold
            if self.fixed_threshold is not None
            else parameters.get(self.threshold_parameter)
        )
        if value is None:
            raise PyBrokerInputError(
                f"Trial parameters are missing threshold dimension {self.threshold_parameter!r}."
            )
        return _probability(value, field_name="signal threshold")

    def to_dict(self, *, threshold: float) -> dict[str, Any]:
        return {
            "signal_family": self.signal_family,
            "rule": self.rule,
            "direction": self.direction,
            "threshold": _probability(threshold, field_name="signal threshold"),
            "threshold_source": (
                f"search_parameter:{self.threshold_parameter}"
                if self.threshold_parameter is not None
                else "fixed_specification"
            ),
        }


@dataclass(frozen=True)
class PyBrokerParameterMapping:
    """Map neutral Phase 2 dimensions to framework estimator parameters."""

    model_parameters: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.model_parameters, Mapping):
            raise PyBrokerInputError("model_parameters must be a mapping.")
        normalized: dict[str, str] = {}
        for raw_dimension, raw_parameter in self.model_parameters.items():
            dimension = _require_non_empty(
                raw_dimension, field_name="search dimension"
            )
            parameter = _require_non_empty(
                raw_parameter, field_name=f"model parameter for {dimension}"
            )
            normalized[dimension] = parameter
        if len(set(normalized.values())) != len(normalized):
            raise PyBrokerInputError(
                "Search dimensions must map to unique model parameters."
            )
        object.__setattr__(
            self,
            "model_parameters",
            MappingProxyType(normalized),
        )

    def validate_dimensions(
        self,
        dimensions: Sequence[str],
        *,
        signal_policy: PyBrokerSignalPolicy,
    ) -> None:
        declared = set(dimensions)
        consumed = set(self.model_parameters)
        if signal_policy.threshold_parameter is not None:
            consumed.add(signal_policy.threshold_parameter)
        missing = sorted(declared.difference(consumed))
        extra = sorted(consumed.difference(declared))
        if missing or extra:
            raise PyBrokerInputError(
                "Every Phase 2 search dimension must be consumed exactly once; "
                f"unmapped={missing}, mapping_without_dimension={extra}."
            )

    def resolve_model_parameters(
        self,
        parameters: Mapping[str, Any],
        *,
        base_parameters: Mapping[str, Any],
        seed: int,
    ) -> dict[str, Any]:
        resolved = dict(base_parameters)
        for dimension, model_parameter in self.model_parameters.items():
            resolved[model_parameter] = parameters[dimension]
        resolved.setdefault("random_state", seed)
        return resolved

    def to_dict(self) -> dict[str, Any]:
        return {"model_parameters": dict(self.model_parameters)}


@dataclass(frozen=True)
class PyBrokerTimingPolicy:
    """Mandatory close-information to next-open execution mapping."""

    signal_timestamp: Literal["bar_close"] = "bar_close"
    entry_delay_bars: Literal[1] = 1
    entry_price_source: Literal["open"] = "open"
    return_interval: Literal["next_open_to_following_open"] = (
        "next_open_to_following_open"
    )

    def __post_init__(self) -> None:
        if self.signal_timestamp != "bar_close":
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B signals must be known at bar close."
            )
        if self.entry_delay_bars != 1:
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B requires entry_delay_bars=1; same-close execution is forbidden."
            )
        if self.entry_price_source != "open":
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B supports only next-bar open execution."
            )
        if self.return_interval != "next_open_to_following_open":
            raise PyBrokerUnsupportedSemanticsError(
                "Phase 3B supports only next-open to following-open screening returns."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_timestamp": self.signal_timestamp,
            "entry_delay_bars": self.entry_delay_bars,
            "entry_price_source": self.entry_price_source,
            "return_interval": self.return_interval,
            "same_close_execution": False,
            "mapping_status": "exact_for_declared_one_bar_screening_model",
        }


@dataclass(frozen=True)
class PyBrokerCostMapping:
    """Explicit normalized cost assumptions for one-unit long/flat turnover."""

    cost_per_turnover: float
    holding_cost_per_exposed_bar: float
    normalized_assumptions: Mapping[str, Any]
    component_status: Mapping[str, str]

    @classmethod
    def from_stf_assumptions(
        cls,
        assumptions: Mapping[str, Any],
        *,
        allow_approximate_spread: bool = False,
    ) -> PyBrokerCostMapping:
        if not isinstance(assumptions, Mapping) or not assumptions:
            raise PyBrokerInputError(
                "PyBroker trading screening requires explicit cost assumptions."
            )
        allowed = {
            "cost_per_turnover",
            "commission_bps_per_side",
            "slippage_per_turnover",
            "slippage_bps_per_side",
            "spread_bps_per_side",
            "holding_cost_per_exposed_bar",
        }
        unexpected = sorted(set(assumptions).difference(allowed))
        if unexpected:
            raise PyBrokerUnsupportedSemanticsError(
                "Unsupported or ambiguous PyBroker cost assumptions: "
                f"{unexpected}. Use explicit per-turnover or per-side keys."
            )

        def value(name: str) -> float:
            return _non_negative_rate(assumptions.get(name, 0.0), field_name=name)

        commission_turnover = value("cost_per_turnover")
        commission_bps = value("commission_bps_per_side")
        if commission_turnover and commission_bps:
            raise PyBrokerInputError(
                "Specify either cost_per_turnover or commission_bps_per_side, not both."
            )
        slippage_turnover = value("slippage_per_turnover")
        slippage_bps = value("slippage_bps_per_side")
        if slippage_turnover and slippage_bps:
            raise PyBrokerInputError(
                "Specify either slippage_per_turnover or slippage_bps_per_side, not both."
            )
        spread_bps = value("spread_bps_per_side")
        if spread_bps and not allow_approximate_spread:
            raise PyBrokerUnsupportedSemanticsError(
                "Scalar spread mapping is approximate. Set allow_approximate_spread=True "
                "explicitly or use canonical quote-path validation."
            )
        commission = commission_turnover or commission_bps / 10_000.0
        slippage = slippage_turnover or slippage_bps / 10_000.0
        spread = spread_bps / 10_000.0
        holding = value("holding_cost_per_exposed_bar")
        normalized = {
            "cost_per_turnover": commission,
            "slippage_per_turnover": slippage,
            "spread_bps_per_side": spread_bps,
            "holding_cost_per_exposed_bar": holding,
        }
        statuses = {
            "commission": "exact_return_fraction_per_unit_turnover",
            "slippage": "exact_return_fraction_per_unit_turnover",
            "spread": (
                "approximate_scalar_midpoint_adverse_fraction"
                if spread_bps
                else "not_configured"
            ),
            "holding": (
                "exact_return_fraction_per_exposed_bar"
                if holding
                else "not_configured"
            ),
        }
        return cls(
            cost_per_turnover=commission + slippage + spread,
            holding_cost_per_exposed_bar=holding,
            normalized_assumptions=normalized,
            component_status=statuses,
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "cost_per_turnover",
            _non_negative_rate(
                self.cost_per_turnover, field_name="cost_per_turnover"
            ),
        )
        object.__setattr__(
            self,
            "holding_cost_per_exposed_bar",
            _non_negative_rate(
                self.holding_cost_per_exposed_bar,
                field_name="holding_cost_per_exposed_bar",
            ),
        )
        object.__setattr__(
            self,
            "normalized_assumptions",
            _freeze_json_mapping(
                self.normalized_assumptions,
                field_name="normalized cost assumptions",
            ),
        )
        object.__setattr__(
            self,
            "component_status",
            _freeze_json_mapping(
                self.component_status,
                field_name="cost component status",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cost_per_turnover": self.cost_per_turnover,
            "holding_cost_per_exposed_bar": self.holding_cost_per_exposed_bar,
            "normalized_assumptions": dict(self.normalized_assumptions),
            "component_status": dict(self.component_status),
            "screening_only": True,
        }


@dataclass(frozen=True)
class PyBrokerResourcePolicy:
    max_combinations: int = 1_000
    max_prediction_records: int = 5_000_000

    def __post_init__(self) -> None:
        for field_name in ("max_combinations", "max_prediction_records"):
            object.__setattr__(
                self,
                field_name,
                _positive_int(getattr(self, field_name), field_name=field_name),
            )

    def validate(self, *, rows: int, combinations: int) -> None:
        if combinations > self.max_combinations:
            raise PyBrokerResourceLimitError(
                "resource_limit: planned combination count "
                f"{combinations} exceeds max_combinations={self.max_combinations}."
            )
        estimated_records = _positive_int(rows, field_name="rows") * _positive_int(
            combinations, field_name="combinations"
        )
        if estimated_records > self.max_prediction_records:
            raise PyBrokerResourceLimitError(
                "resource_limit: estimated OOS provenance records "
                f"{estimated_records} exceeds max_prediction_records="
                f"{self.max_prediction_records}."
            )

    def to_dict(self) -> dict[str, int]:
        return {
            "max_combinations": self.max_combinations,
            "max_prediction_records": self.max_prediction_records,
        }


__all__ = [
    "PYBROKER_CAPABILITIES",
    "PyBrokerBackendError",
    "PyBrokerCostMapping",
    "PyBrokerFoldPolicy",
    "PyBrokerInputError",
    "PyBrokerParameterMapping",
    "PyBrokerPreprocessingPolicy",
    "PyBrokerResearchData",
    "PyBrokerResourceLimitError",
    "PyBrokerResourcePolicy",
    "PyBrokerRuntimeError",
    "PyBrokerSignalPolicy",
    "PyBrokerTimingPolicy",
    "PyBrokerUnsupportedSemanticsError",
]
