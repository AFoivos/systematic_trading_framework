"""STF-native multi-asset prediction research over R1 panel datasets.

This module is a discovery-stage executor.  It consumes framework-owned
features, targets, segments, search spaces, and models; it does not construct a
portfolio, backtest a strategy, or create canonical/final evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from math import floor, isfinite
import platform
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.model_diagnostics import prediction_realized_metrics
from src.evaluation.model_metrics import regression_metrics
from src.evaluation.time_splits import assert_no_forward_label_leakage
from src.models.classification.base import _apply_fold_feature_preprocessing
from src.models.forecasting.lightgbm import create_lightgbm_regressor_estimator
from src.models.registry import get_model_fn
from src.research.contracts import (
    ResearchContractError,
    _freeze_json_mapping,
    _require_exact_keys,
    _require_identifier,
    _require_non_empty,
)
from src.research.dataset import (
    ASSET_ID_COLUMN,
    TIMESTAMP_COLUMN,
    PanelResearchDataset,
    ResearchSegmentPurpose,
    validate_research_dataset,
)
from src.research.discovery.contracts import (
    DiscoverySpecification,
    DiscoveryTrial,
    SelectionMetricBasis,
    TrialStatus,
)
from src.research.discovery.service import TrialEvaluator
from src.src_data.research_roles import EvidenceRole
from src.utils.run_metadata import compute_config_hash


class MultiAssetResearchError(ResearchContractError):
    """Base error for fail-closed R2 prediction research."""


class MultiAssetInputError(MultiAssetResearchError):
    """Raised when panel data or research semantics are invalid."""


class MultiAssetResourceLimitError(MultiAssetResearchError):
    """Raised before model fitting when an operational cap is exceeded."""


class MultiAssetResearchMode(str, Enum):
    """Explicit, non-interchangeable R2 model/evaluation modes."""

    PER_ASSET = "per_asset"
    CROSS_SECTIONAL = "cross_sectional"


class CrossSectionalMetricStatus(str, Enum):
    COMPLETED = "completed"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class MultiAssetPreprocessingPolicy:
    """The intentionally small set of audited train-only processors."""

    scaler: str = "none"
    missing_value_policy: str = "drop_incomplete_required_rows"
    imputation: str = "unsupported"
    feature_selection: str = "unsupported"
    calibration: str = "unsupported"

    def __post_init__(self) -> None:
        scaler = str(self.scaler).strip().lower()
        if scaler not in {"none", "standard", "robust"}:
            raise MultiAssetInputError(
                "R2 preprocessing scaler must be none, standard, or robust."
            )
        if self.missing_value_policy != "drop_incomplete_required_rows":
            raise MultiAssetInputError(
                "R2 supports only deterministic dropping of incomplete required rows."
            )
        for name in ("imputation", "feature_selection", "calibration"):
            if getattr(self, name) != "unsupported":
                raise MultiAssetInputError(f"R2 {name} is unsupported.")
        object.__setattr__(self, "scaler", scaler)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scaler": self.scaler,
            "fit_sample": "training_and_tuning_after_target_horizon_purge",
            "transform_sample": "screening_prediction_eligible_rows_only",
            "train_only": True,
            "missing_value_policy": self.missing_value_policy,
            "imputation": self.imputation,
            "feature_selection": self.feature_selection,
            "calibration": self.calibration,
        }


@dataclass(frozen=True)
class CrossSectionalDiagnosticPolicy:
    """Explicit cross-sectional sample and diagnostic policy."""

    minimum_assets_per_timestamp: int
    quantile_fraction: float | None = None
    temporal_subperiods: int = 3

    def __post_init__(self) -> None:
        if (
            isinstance(self.minimum_assets_per_timestamp, bool)
            or not isinstance(self.minimum_assets_per_timestamp, int)
            or self.minimum_assets_per_timestamp < 3
        ):
            raise MultiAssetInputError(
                "minimum_assets_per_timestamp must be explicitly configured as an integer >= 3."
            )
        if self.quantile_fraction is not None and (
            isinstance(self.quantile_fraction, bool)
            or not isinstance(self.quantile_fraction, (int, float))
            or not isfinite(float(self.quantile_fraction))
            or not 0.0 < float(self.quantile_fraction) <= 0.5
        ):
            raise MultiAssetInputError(
                "quantile_fraction must be null or finite in (0, 0.5]."
            )
        if (
            isinstance(self.temporal_subperiods, bool)
            or not isinstance(self.temporal_subperiods, int)
            or self.temporal_subperiods < 1
        ):
            raise MultiAssetInputError("temporal_subperiods must be an integer >= 1.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "minimum_assets_per_timestamp": self.minimum_assets_per_timestamp,
            "quantile_fraction": self.quantile_fraction,
            "temporal_subperiods": self.temporal_subperiods,
            "tie_method": "average_rank_then_pearson",
            "non_finite_policy": "exclude_without_fill",
            "quantile_interpretation": "target_diagnostic_not_portfolio_return",
        }


@dataclass(frozen=True)
class MultiAssetResourcePolicy:
    """Bound a multi-asset discovery run before fitting any estimator."""

    max_trials: int = 32
    max_assets: int = 100
    max_model_fits: int = 256
    max_prediction_records: int = 250_000
    max_rows: int = 1_000_000
    minimum_train_rows: int = 20

    def __post_init__(self) -> None:
        for name in (
            "max_trials",
            "max_assets",
            "max_model_fits",
            "max_prediction_records",
            "max_rows",
            "minimum_train_rows",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise MultiAssetInputError(f"{name} must be an integer >= 1.")

    def validate(
        self,
        *,
        rows: int,
        assets: int,
        trials: int,
        fits_per_trial: int,
        eligible_rows: int,
    ) -> None:
        planned_fits = trials * fits_per_trial
        planned_records = trials * eligible_rows
        checks = {
            "rows": (rows, self.max_rows),
            "assets": (assets, self.max_assets),
            "trials": (trials, self.max_trials),
            "model_fits": (planned_fits, self.max_model_fits),
            "prediction_records": (planned_records, self.max_prediction_records),
        }
        exceeded = [
            f"{name}={actual}>{limit}"
            for name, (actual, limit) in checks.items()
            if actual > limit
        ]
        if exceeded:
            raise MultiAssetResourceLimitError(
                "R2 resource preflight rejected the run before fitting: "
                + ", ".join(exceeded)
            )

    def to_dict(self) -> dict[str, int]:
        return {
            "max_trials": self.max_trials,
            "max_assets": self.max_assets,
            "max_model_fits": self.max_model_fits,
            "max_prediction_records": self.max_prediction_records,
            "max_rows": self.max_rows,
            "minimum_train_rows": self.minimum_train_rows,
        }


@dataclass(frozen=True)
class MultiAssetParameterMapping:
    """Map the existing Phase 2 dimensions into model/feature inputs exactly once."""

    model_parameters: Mapping[str, str] = field(default_factory=dict)
    feature_set_parameter: str | None = None
    feature_sets: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.model_parameters, Mapping):
            raise MultiAssetInputError("model_parameters must be a mapping.")
        normalized: dict[str, str] = {}
        for dimension, parameter in sorted(self.model_parameters.items()):
            normalized[_require_non_empty(dimension, field_name="search dimension")] = (
                _require_non_empty(parameter, field_name="LightGBM parameter")
            )
        if len(set(normalized.values())) != len(normalized):
            raise MultiAssetInputError(
                "Each LightGBM parameter may be mapped from only one search dimension."
            )
        object.__setattr__(self, "model_parameters", MappingProxyType(normalized))

        feature_parameter = self.feature_set_parameter
        if feature_parameter is not None:
            feature_parameter = _require_non_empty(
                feature_parameter, field_name="feature_set_parameter"
            )
        if not isinstance(self.feature_sets, Mapping):
            raise MultiAssetInputError("feature_sets must be a mapping.")
        variants: dict[str, tuple[str, ...]] = {}
        for name, columns in sorted(self.feature_sets.items()):
            variant = _require_non_empty(name, field_name="feature-set variant")
            if isinstance(columns, (str, bytes, bytearray)):
                raise MultiAssetInputError("Feature-set columns must be a sequence.")
            resolved = tuple(columns)
            if not resolved or len(set(resolved)) != len(resolved):
                raise MultiAssetInputError(
                    "Every feature-set variant must contain unique feature names."
                )
            variants[variant] = resolved
        if (feature_parameter is None) != (not variants):
            raise MultiAssetInputError(
                "feature_set_parameter and feature_sets must be configured together."
            )
        object.__setattr__(self, "feature_set_parameter", feature_parameter)
        object.__setattr__(self, "feature_sets", MappingProxyType(variants))

    def validate_dimensions(self, dimensions: Sequence[str]) -> None:
        expected = set(self.model_parameters)
        if self.feature_set_parameter is not None:
            expected.add(self.feature_set_parameter)
        actual = set(dimensions)
        if actual != expected:
            raise MultiAssetInputError(
                "Every Phase 2 search dimension must map exactly once; "
                f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}."
            )

    def feature_columns(
        self,
        parameters: Mapping[str, Any],
        *,
        available: Sequence[str],
    ) -> tuple[str, ...]:
        if self.feature_set_parameter is None:
            return tuple(available)
        variant = str(parameters[self.feature_set_parameter])
        if variant not in self.feature_sets:
            raise MultiAssetInputError(f"Unknown feature-set variant {variant!r}.")
        columns = self.feature_sets[variant]
        missing = sorted(set(columns).difference(available))
        if missing:
            raise MultiAssetInputError(
                f"Feature-set variant {variant!r} references undeclared features: {missing}."
            )
        return columns

    def model_params(
        self,
        parameters: Mapping[str, Any],
        *,
        base_parameters: Mapping[str, Any],
        seed: int,
    ) -> dict[str, Any]:
        resolved = dict(base_parameters)
        for dimension, parameter in self.model_parameters.items():
            resolved[parameter] = parameters[dimension]
        resolved.update(
            {
                "random_state": seed,
                "n_jobs": 1,
                "verbosity": -1,
                "deterministic": True,
                "force_col_wise": True,
            }
        )
        return resolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_parameters": dict(self.model_parameters),
            "feature_set_parameter": self.feature_set_parameter,
            "feature_sets": {
                name: list(columns) for name, columns in self.feature_sets.items()
            },
        }


def _aware_timestamp(value: object, *, field_name: str) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise MultiAssetInputError(f"{field_name} must include a timezone.")
    return timestamp.isoformat()


def _finite_float(value: object, *, field_name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float, np.integer, np.floating))
        or not isfinite(float(value))
    ):
        raise MultiAssetInputError(f"{field_name} must be finite numeric.")
    return float(value)


@dataclass(frozen=True)
class MultiAssetPredictionRecord:
    """Portable OOS prediction and its model-fit provenance."""

    prediction_id: str
    timestamp: str
    asset_id: str
    research_run_id: str
    trial_id: str
    segment_id: str
    model_fit_id: str
    prediction: float
    target: float
    prediction_eligible: bool
    trained_without_this_row: bool
    is_oos: bool
    model_fit_start_timestamp: str
    model_fit_end_timestamp: str
    target_horizon_bars: int

    def __post_init__(self) -> None:
        for name in (
            "prediction_id",
            "asset_id",
            "research_run_id",
            "trial_id",
            "segment_id",
            "model_fit_id",
        ):
            object.__setattr__(
                self, name, _require_identifier(getattr(self, name), field_name=name)
            )
        timestamp = _aware_timestamp(self.timestamp, field_name="prediction timestamp")
        fit_start = _aware_timestamp(
            self.model_fit_start_timestamp, field_name="model fit start timestamp"
        )
        fit_end = _aware_timestamp(
            self.model_fit_end_timestamp, field_name="model fit end timestamp"
        )
        if pd.Timestamp(fit_start) > pd.Timestamp(fit_end):
            raise MultiAssetInputError("Model fit timestamps are reversed.")
        if pd.Timestamp(fit_end) >= pd.Timestamp(timestamp):
            raise MultiAssetInputError(
                "OOS prediction timestamp must be later than model_fit_end_timestamp."
            )
        for name in ("prediction_eligible", "trained_without_this_row", "is_oos"):
            if getattr(self, name) is not True:
                raise MultiAssetInputError(f"Portable screening record requires {name}=true.")
        if (
            isinstance(self.target_horizon_bars, bool)
            or not isinstance(self.target_horizon_bars, int)
            or self.target_horizon_bars < 1
        ):
            raise MultiAssetInputError("target_horizon_bars must be an integer >= 1.")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "model_fit_start_timestamp", fit_start)
        object.__setattr__(self, "model_fit_end_timestamp", fit_end)
        object.__setattr__(
            self, "prediction", _finite_float(self.prediction, field_name="prediction")
        )
        object.__setattr__(self, "target", _finite_float(self.target, field_name="target"))

    @classmethod
    def create(
        cls,
        *,
        timestamp: object,
        asset_id: str,
        research_run_id: str,
        trial_id: str,
        segment_id: str,
        model_fit_id: str,
        prediction: float,
        target: float,
        model_fit_start_timestamp: object,
        model_fit_end_timestamp: object,
        target_horizon_bars: int,
    ) -> "MultiAssetPredictionRecord":
        timestamp_value = _aware_timestamp(timestamp, field_name="prediction timestamp")
        digest, _ = compute_config_hash(
            {
                "timestamp": timestamp_value,
                "asset_id": asset_id,
                "research_run_id": research_run_id,
                "trial_id": trial_id,
                "model_fit_id": model_fit_id,
            }
        )
        return cls(
            prediction_id=f"prediction-{digest[:24]}",
            timestamp=timestamp_value,
            asset_id=asset_id,
            research_run_id=research_run_id,
            trial_id=trial_id,
            segment_id=segment_id,
            model_fit_id=model_fit_id,
            prediction=prediction,
            target=target,
            prediction_eligible=True,
            trained_without_this_row=True,
            is_oos=True,
            model_fit_start_timestamp=_aware_timestamp(
                model_fit_start_timestamp, field_name="model fit start timestamp"
            ),
            model_fit_end_timestamp=_aware_timestamp(
                model_fit_end_timestamp, field_name="model fit end timestamp"
            ),
            target_horizon_bars=target_horizon_bars,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "timestamp": self.timestamp,
            "asset_id": self.asset_id,
            "research_run_id": self.research_run_id,
            "trial_id": self.trial_id,
            "segment_id": self.segment_id,
            "model_fit_id": self.model_fit_id,
            "prediction": self.prediction,
            "target": self.target,
            "prediction_eligible": self.prediction_eligible,
            "trained_without_this_row": self.trained_without_this_row,
            "is_oos": self.is_oos,
            "model_fit_start_timestamp": self.model_fit_start_timestamp,
            "model_fit_end_timestamp": self.model_fit_end_timestamp,
            "target_horizon_bars": self.target_horizon_bars,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MultiAssetPredictionRecord":
        expected = {
            "prediction_id",
            "timestamp",
            "asset_id",
            "research_run_id",
            "trial_id",
            "segment_id",
            "model_fit_id",
            "prediction",
            "target",
            "prediction_eligible",
            "trained_without_this_row",
            "is_oos",
            "model_fit_start_timestamp",
            "model_fit_end_timestamp",
            "target_horizon_bars",
        }
        _require_exact_keys(payload, expected=expected, field_name="Prediction record")
        return cls(**{name: payload[name] for name in expected})


def _safe_metric(value: object) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise MultiAssetInputError("DiscoveryTrial metrics must be numeric or null.")
    return float(value) if isfinite(float(value)) else None


def _sanitize_metrics(values: Mapping[str, object]) -> dict[str, int | float | None]:
    return {str(name): _safe_metric(value) for name, value in values.items()}


def _rank_ic(group: pd.DataFrame) -> float | None:
    prediction_rank = group["prediction"].rank(method="average", ascending=True)
    target_rank = group["target"].rank(method="average", ascending=True)
    if prediction_rank.nunique() < 2 or target_rank.nunique() < 2:
        return None
    correlation = prediction_rank.corr(target_rank, method="pearson")
    return float(correlation) if pd.notna(correlation) and isfinite(float(correlation)) else None


def compute_cross_sectional_diagnostics(
    predictions: pd.DataFrame,
    *,
    minimum_assets_per_timestamp: int,
    quantile_fraction: float | None = None,
) -> dict[str, Any]:
    """Compute per-timestamp rank IC with average ranks for deterministic ties.

    ``predictions`` must contain timestamp, asset_id, prediction, and target. Any
    non-finite value is excluded, never replaced.  Quantile spreads are realized
    target diagnostics only and carry no portfolio-return interpretation.
    """

    policy = CrossSectionalDiagnosticPolicy(
        minimum_assets_per_timestamp=minimum_assets_per_timestamp,
        quantile_fraction=quantile_fraction,
    )
    required = {TIMESTAMP_COLUMN, ASSET_ID_COLUMN, "prediction", "target"}
    if not isinstance(predictions, pd.DataFrame):
        raise MultiAssetInputError("predictions must be a pandas DataFrame.")
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise MultiAssetInputError(
            f"Cross-sectional predictions are missing columns: {missing}."
        )
    work = predictions.loc[:, sorted(required)].copy()
    if not isinstance(work[TIMESTAMP_COLUMN].dtype, pd.DatetimeTZDtype):
        raise MultiAssetInputError("Cross-sectional timestamps must be timezone-aware.")
    if work.duplicated([TIMESTAMP_COLUMN, ASSET_ID_COLUMN]).any():
        raise MultiAssetInputError(
            "Cross-sectional predictions contain duplicate timestamp/asset rows."
        )
    work["prediction"] = pd.to_numeric(work["prediction"], errors="coerce")
    work["target"] = pd.to_numeric(work["target"], errors="coerce")
    finite = np.isfinite(work["prediction"].to_numpy(dtype=float)) & np.isfinite(
        work["target"].to_numpy(dtype=float)
    )
    work = work.loc[finite].sort_values(
        [TIMESTAMP_COLUMN, ASSET_ID_COLUMN], kind="mergesort"
    )

    rows: list[dict[str, Any]] = []
    for timestamp, group in work.groupby(TIMESTAMP_COLUMN, sort=True):
        asset_count = int(group[ASSET_ID_COLUMN].nunique())
        row: dict[str, Any] = {
            "timestamp": pd.Timestamp(timestamp).isoformat(),
            "asset_count": asset_count,
            "status": CrossSectionalMetricStatus.NOT_RUN.value,
            "reason": None,
            "rank_correlation": None,
            "top_mean_target": None,
            "bottom_mean_target": None,
            "top_bottom_target_spread": None,
        }
        if asset_count < policy.minimum_assets_per_timestamp:
            row["reason"] = "insufficient_assets"
            rows.append(row)
            continue
        rank_correlation = _rank_ic(group)
        if rank_correlation is None:
            row["reason"] = "constant_prediction_or_target_ranks"
            rows.append(row)
            continue
        row.update(
            {
                "status": CrossSectionalMetricStatus.COMPLETED.value,
                "rank_correlation": rank_correlation,
            }
        )
        if policy.quantile_fraction is not None:
            ordered = group.sort_values(
                ["prediction", ASSET_ID_COLUMN], kind="mergesort"
            )
            count = max(1, floor(len(ordered) * policy.quantile_fraction))
            count = min(count, len(ordered) // 2)
            if count >= 1:
                bottom = float(ordered.head(count)["target"].mean())
                top = float(ordered.tail(count)["target"].mean())
                row.update(
                    {
                        "top_mean_target": top,
                        "bottom_mean_target": bottom,
                        "top_bottom_target_spread": top - bottom,
                    }
                )
        rows.append(row)

    valid_values = [
        float(row["rank_correlation"])
        for row in rows
        if row["status"] == CrossSectionalMetricStatus.COMPLETED.value
    ]
    spreads = [
        float(row["top_bottom_target_spread"])
        for row in rows
        if row["top_bottom_target_spread"] is not None
    ]
    return {
        "definition": "per_timestamp_pearson_correlation_of_average_prediction_and_target_ranks",
        "minimum_assets_per_timestamp": policy.minimum_assets_per_timestamp,
        "tie_method": "average_rank_then_pearson",
        "periods": rows,
        "valid_period_count": len(valid_values),
        "unavailable_period_count": len(rows) - len(valid_values),
        "mean_rank_correlation": (
            float(np.mean(valid_values)) if valid_values else None
        ),
        "median_rank_correlation": (
            float(np.median(valid_values)) if valid_values else None
        ),
        "rank_correlation_dispersion": (
            float(np.std(valid_values, ddof=0)) if valid_values else None
        ),
        "positive_period_count": sum(value > 0.0 for value in valid_values),
        "mean_top_bottom_target_spread": (
            float(np.mean(spreads)) if spreads else None
        ),
        "quantile_interpretation": "prediction_target_diagnostic_only_not_portfolio_return",
    }


def _trial_id(research_run_id: str, parameters: Mapping[str, Any]) -> str:
    digest, _ = compute_config_hash(
        {"research_run_id": research_run_id, "parameters": dict(parameters)}
    )
    return f"{research_run_id}-multi-asset-{digest[:24]}"


def _trial_seed(
    base_seed: int, research_run_id: str, parameters: Mapping[str, Any]
) -> int:
    digest, _ = compute_config_hash(
        {
            "base_seed": base_seed,
            "research_run_id": research_run_id,
            "parameters": dict(parameters),
        }
    )
    return int(digest[:8], 16) % (2**31 - 1)


def _segment_mask(
    frame: pd.DataFrame,
    metadata: PanelResearchDataset,
    purposes: set[ResearchSegmentPurpose],
) -> pd.Series:
    mask = pd.Series(False, index=frame.index, dtype=bool)
    for segment in metadata.segments:
        if segment.purpose in purposes:
            mask |= segment.contains(frame[TIMESTAMP_COLUMN])
    return mask


def _screening_segment_id(
    timestamp: pd.Timestamp, metadata: PanelResearchDataset
) -> str:
    probe = pd.Series([timestamp])
    for segment in metadata.segments:
        if (
            segment.purpose is ResearchSegmentPurpose.SCREENING
            and bool(segment.contains(probe).iloc[0])
        ):
            return segment.segment_id
    raise MultiAssetInputError("Prediction timestamp is outside the screening segment.")


def _prediction_frame(records: Sequence[MultiAssetPredictionRecord]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                TIMESTAMP_COLUMN: pd.Timestamp(record.timestamp),
                ASSET_ID_COLUMN: record.asset_id,
                "prediction": record.prediction,
                "target": record.target,
            }
            for record in records
        ]
    ).sort_values([TIMESTAMP_COLUMN, ASSET_ID_COLUMN], kind="mergesort")


def _training_feature_summary(
    frame: pd.DataFrame, feature_columns: Sequence[str]
) -> dict[str, Any]:
    return {
        column: {
            "mean": float(frame[column].mean()),
            "std": float(frame[column].std(ddof=0)),
            "minimum": float(frame[column].min()),
            "maximum": float(frame[column].max()),
        }
        for column in feature_columns
    }


def _stability(values: Sequence[float]) -> dict[str, int | float | None]:
    finite_values = [float(value) for value in values if isfinite(float(value))]
    return {
        "mean_segment_metric": (
            float(np.mean(finite_values)) if finite_values else None
        ),
        "median_segment_metric": (
            float(np.median(finite_values)) if finite_values else None
        ),
        "worst_segment_metric": min(finite_values) if finite_values else None,
        "segment_metric_dispersion": (
            float(np.std(finite_values, ddof=0)) if finite_values else None
        ),
        "positive_segment_count": sum(value > 0.0 for value in finite_values),
    }


class MultiAssetSearchExecutor:
    """Finite Phase 2 executor for STF-native multi-asset prediction screening."""

    name = "multi_asset"
    backend_name = "stf_multi_asset"
    backend_version = "phase-3c-r2-v1"
    capabilities = frozenset(
        {
            "per_asset_prediction_research",
            "cross_sectional_prediction_research",
            "oos_prediction_screening",
            "per_asset_diagnostics",
            "cross_sectional_rank_diagnostics",
        }
    )

    def __init__(
        self,
        *,
        frame: pd.DataFrame,
        dataset: PanelResearchDataset,
        mode: MultiAssetResearchMode,
        diagnostics: CrossSectionalDiagnosticPolicy,
        parameter_mapping: MultiAssetParameterMapping | None = None,
        preprocessing: MultiAssetPreprocessingPolicy | None = None,
        resources: MultiAssetResourcePolicy | None = None,
        base_model_parameters: Mapping[str, Any] | None = None,
        purge_bars: int | None = None,
    ) -> None:
        if not isinstance(dataset, PanelResearchDataset):
            raise MultiAssetInputError("dataset must be the R1 PanelResearchDataset.")
        validate_research_dataset(frame, dataset)
        try:
            resolved_mode = MultiAssetResearchMode(mode)
        except (TypeError, ValueError) as exc:
            raise MultiAssetInputError(str(exc)) from exc
        if not isinstance(diagnostics, CrossSectionalDiagnosticPolicy):
            raise MultiAssetInputError(
                "diagnostics must be CrossSectionalDiagnosticPolicy."
            )
        if purge_bars is not None and (
            isinstance(purge_bars, bool)
            or not isinstance(purge_bars, int)
            or purge_bars < dataset.target_horizon_bars
        ):
            raise MultiAssetInputError(
                "purge_bars must be null or >= the authoritative target horizon."
            )
        self.frame = frame.copy(deep=False)
        self.dataset = dataset
        self.mode = resolved_mode
        self.diagnostics = diagnostics
        self.parameter_mapping = parameter_mapping or MultiAssetParameterMapping()
        self.preprocessing = preprocessing or MultiAssetPreprocessingPolicy()
        self.resources = resources or MultiAssetResourcePolicy()
        self.base_model_parameters = _freeze_json_mapping(
            base_model_parameters or {}, field_name="base_model_parameters"
        )
        self.purge_bars = purge_bars or dataset.target_horizon_bars

    def _validate_specification(
        self, specification: DiscoverySpecification
    ) -> tuple[int, int, int, pd.Series, pd.Series]:
        if specification.search_method != self.name:
            raise MultiAssetInputError(
                f"R2 executor cannot run search_method={specification.search_method!r}."
            )
        if tuple(sorted(specification.assets)) != self.dataset.asset_ids:
            raise MultiAssetInputError(
                "Discovery assets must exactly match the R1 dataset asset universe."
            )
        if specification.dataset_reference != self.dataset.dataset_id:
            raise MultiAssetInputError(
                "Discovery dataset_reference must match the R1 dataset_id."
            )
        if (
            specification.dataset_fingerprint.get("sha256")
            != self.dataset.dataset_fingerprint.get("sha256")
        ):
            raise MultiAssetInputError("Discovery and R1 dataset fingerprints differ.")
        if specification.target_family != self.dataset.target_name:
            raise MultiAssetInputError(
                "Discovery target_family differs from the R1 target contract."
            )
        if specification.model_families != ("lightgbm_regressor",):
            raise MultiAssetInputError(
                "R2 initially supports exactly model_families=('lightgbm_regressor',)."
            )
        if specification.signal_families:
            raise MultiAssetInputError(
                "R2 is prediction research and does not accept signal families."
            )
        if specification.selection.metric_basis is not SelectionMetricBasis.PREDICTION:
            raise MultiAssetInputError(
                "R2 ranking must use prediction metrics, not trading metrics."
            )
        if specification.evidence_reference.evidence_role is not EvidenceRole.DISCOVERY:
            raise MultiAssetInputError("R2 may consume only DISCOVERY evidence.")
        get_model_fn("lightgbm_regressor")
        self.parameter_mapping.validate_dimensions(
            specification.search_space.parameter_names
        )
        cardinality = specification.search_space.cardinality()
        if cardinality is None:
            raise MultiAssetInputError(
                "R2 requires a finite Phase 2 grid; adaptive search remains Optuna-owned."
            )
        planned = min(cardinality, specification.trial_budget)

        training_mask = _segment_mask(
            self.frame,
            self.dataset,
            {ResearchSegmentPurpose.TRAINING, ResearchSegmentPurpose.TUNING},
        )
        screening_mask = _segment_mask(
            self.frame, self.dataset, {ResearchSegmentPurpose.SCREENING}
        )
        eligibility = self.dataset.prediction_eligibility
        eligible_mask = screening_mask & self.frame[eligibility.eligible_column].astype(bool)
        if not bool(eligible_mask.any()):
            raise MultiAssetInputError("R2 has no prediction-eligible SCREENING rows.")

        timestamps = pd.Index(self.frame[TIMESTAMP_COLUMN].drop_duplicates())
        first_screen = self.frame.loc[screening_mask, TIMESTAMP_COLUMN].min()
        if self.frame.loc[training_mask, TIMESTAMP_COLUMN].max() >= first_screen:
            raise MultiAssetInputError(
                "All TRAINING/TUNING rows must precede the first SCREENING row."
            )
        first_screen_position = int(timestamps.get_loc(first_screen))
        timestamp_positions = self.frame[TIMESTAMP_COLUMN].map(
            {timestamp: index for index, timestamp in enumerate(timestamps)}
        )
        safe_training_mask = training_mask & timestamp_positions.lt(
            first_screen_position - self.purge_bars
        )
        safe_positions = np.asarray(
            sorted(timestamp_positions.loc[safe_training_mask].unique()), dtype=int
        )
        assert_no_forward_label_leakage(
            safe_positions,
            test_start=first_screen_position,
            target_horizon=self.dataset.target_horizon_bars,
        )
        if not bool(safe_training_mask.any()):
            raise MultiAssetInputError(
                "No training rows remain after target-horizon purge."
            )
        if self.frame.loc[safe_training_mask, TIMESTAMP_COLUMN].max() >= first_screen:
            raise MultiAssetInputError("Training and screening segments are not chronological.")

        fits_per_trial = (
            len(self.dataset.asset_ids)
            if self.mode is MultiAssetResearchMode.PER_ASSET
            else 1
        )
        self.resources.validate(
            rows=len(self.frame),
            assets=len(self.dataset.asset_ids),
            trials=planned,
            fits_per_trial=fits_per_trial,
            eligible_rows=int(eligible_mask.sum()),
        )
        return cardinality, planned, fits_per_trial, safe_training_mask, eligible_mask

    def _fit_one(
        self,
        *,
        train: pd.DataFrame,
        predict: pd.DataFrame,
        features: tuple[str, ...],
        model_parameters: Mapping[str, Any],
    ) -> tuple[np.ndarray, dict[str, Any]]:
        complete_train = train.loc[:, features].notna().all(axis=1) & train[
            self.dataset.target_column
        ].notna()
        fit_frame = train.loc[complete_train]
        if len(fit_frame) < self.resources.minimum_train_rows:
            raise MultiAssetInputError(
                "insufficient_training_rows:"
                f"{len(fit_frame)}<{self.resources.minimum_train_rows}"
            )
        if predict.empty:
            raise MultiAssetInputError("No eligible screening rows for model prediction.")
        if not predict.loc[:, features].notna().all(axis=1).all():
            raise MultiAssetInputError(
                "Prediction-eligible rows must have complete selected features."
            )
        X_train, X_predict, preprocessing_meta = _apply_fold_feature_preprocessing(
            fit_frame.loc[:, features],
            predict.loc[:, features],
            preprocessing_cfg={"scaler": self.preprocessing.scaler},
        )
        estimator = create_lightgbm_regressor_estimator(dict(model_parameters))
        estimator.fit(X_train, fit_frame[self.dataset.target_column].astype(float))
        values = np.asarray(estimator.predict(X_predict), dtype=float)
        if values.shape != (len(predict),) or not np.isfinite(values).all():
            raise MultiAssetInputError("Model emitted non-finite or misaligned predictions.")
        provenance = {
            "model_fit_start_timestamp": fit_frame[TIMESTAMP_COLUMN].min().isoformat(),
            "model_fit_end_timestamp": fit_frame[TIMESTAMP_COLUMN].max().isoformat(),
            "model_train_rows": int(len(fit_frame)),
            "dropped_incomplete_training_rows": int(len(train) - len(fit_frame)),
            "training_feature_summary": _training_feature_summary(
                fit_frame, features
            ),
            "preprocessing": preprocessing_meta,
        }
        return values, provenance

    def _completed_trial(
        self,
        *,
        specification: DiscoverySpecification,
        research_run_id: str,
        parameters: Mapping[str, Any],
        safe_training_mask: pd.Series,
        eligible_mask: pd.Series,
        full_cardinality: int,
        planned_trials: int,
        fits_per_trial: int,
    ) -> DiscoveryTrial:
        trial_id = _trial_id(research_run_id, parameters)
        seed = _trial_seed(specification.random_seed, research_run_id, parameters)
        features = self.parameter_mapping.feature_columns(
            parameters, available=self.dataset.feature_names
        )
        model_parameters = self.parameter_mapping.model_params(
            parameters,
            base_parameters=self.base_model_parameters,
            seed=seed,
        )
        train = self.frame.loc[safe_training_mask]
        predict = self.frame.loc[eligible_mask]
        fit_rows: list[dict[str, Any]] = []
        records: list[MultiAssetPredictionRecord] = []

        fit_groups: list[tuple[str, pd.DataFrame, pd.DataFrame]]
        if self.mode is MultiAssetResearchMode.PER_ASSET:
            fit_groups = [
                (
                    asset,
                    train.loc[train[ASSET_ID_COLUMN] == asset],
                    predict.loc[predict[ASSET_ID_COLUMN] == asset],
                )
                for asset in self.dataset.asset_ids
            ]
        else:
            fit_groups = [("pooled", train, predict)]

        for fit_index, (fit_scope, train_part, predict_part) in enumerate(fit_groups):
            values, provenance = self._fit_one(
                train=train_part,
                predict=predict_part,
                features=features,
                model_parameters=model_parameters,
            )
            model_fit_id = f"{trial_id}-fit-{fit_index:04d}-{fit_scope}"
            fit_rows.append(
                {
                    "model_fit_id": model_fit_id,
                    "fit_scope": fit_scope,
                    **provenance,
                }
            )
            for (_, row), prediction in zip(predict_part.iterrows(), values):
                records.append(
                    MultiAssetPredictionRecord.create(
                        timestamp=row[TIMESTAMP_COLUMN],
                        asset_id=row[ASSET_ID_COLUMN],
                        research_run_id=research_run_id,
                        trial_id=trial_id,
                        segment_id=_screening_segment_id(
                            row[TIMESTAMP_COLUMN], self.dataset
                        ),
                        model_fit_id=model_fit_id,
                        prediction=float(prediction),
                        target=float(row[self.dataset.target_column]),
                        model_fit_start_timestamp=provenance[
                            "model_fit_start_timestamp"
                        ],
                        model_fit_end_timestamp=provenance[
                            "model_fit_end_timestamp"
                        ],
                        target_horizon_bars=self.dataset.target_horizon_bars,
                    )
                )
        records.sort(key=lambda row: (row.timestamp, row.asset_id))
        prediction_frame = _prediction_frame(records)
        overall_raw = regression_metrics(
            prediction_frame["target"], prediction_frame["prediction"]
        )
        overall_diag = prediction_realized_metrics(
            prediction_frame["prediction"], prediction_frame["target"]
        )
        overall = {
            **overall_raw,
            "spearman_rank_correlation": overall_diag[
                "spearman_rank_correlation"
            ],
        }

        screen_mask = _segment_mask(
            self.frame, self.dataset, {ResearchSegmentPurpose.SCREENING}
        )
        screen_timestamp_count = int(
            self.frame.loc[screen_mask, TIMESTAMP_COLUMN].nunique()
        )
        total_predictions = len(records)
        eligible_rows = int(eligible_mask.sum())
        per_asset: list[dict[str, Any]] = []
        for asset in self.dataset.asset_ids:
            asset_records = prediction_frame.loc[
                prediction_frame[ASSET_ID_COLUMN] == asset
            ]
            asset_eligible = int(
                (eligible_mask & self.frame[ASSET_ID_COLUMN].eq(asset)).sum()
            )
            observed_screen = int(
                (screen_mask & self.frame[ASSET_ID_COLUMN].eq(asset)).sum()
            )
            raw_metrics = regression_metrics(
                asset_records["target"], asset_records["prediction"]
            )
            diagnostics = prediction_realized_metrics(
                asset_records["prediction"], asset_records["target"]
            )
            per_asset.append(
                {
                    "asset_id": asset,
                    "eligible_rows": asset_eligible,
                    "prediction_rows": int(len(asset_records)),
                    "missing_prediction_rows": asset_eligible - len(asset_records),
                    "coverage": float(len(asset_records) / max(asset_eligible, 1)),
                    "prediction_share": float(
                        len(asset_records) / max(total_predictions, 1)
                    ),
                    "observed_screening_rows": observed_screen,
                    "possible_screening_rows": screen_timestamp_count,
                    "missing_observation_rows": screen_timestamp_count
                    - observed_screen,
                    "metric_availability": {
                        "pearson": raw_metrics["correlation"] is not None,
                        "spearman": diagnostics["spearman_rank_correlation"]
                        is not None,
                    },
                    "metrics": {
                        **raw_metrics,
                        "spearman_rank_correlation": diagnostics[
                            "spearman_rank_correlation"
                        ],
                    },
                }
            )

        cross = compute_cross_sectional_diagnostics(
            prediction_frame,
            minimum_assets_per_timestamp=self.diagnostics.minimum_assets_per_timestamp,
            quantile_fraction=self.diagnostics.quantile_fraction,
        )
        if (
            self.mode is MultiAssetResearchMode.CROSS_SECTIONAL
            and cross["valid_period_count"] == 0
        ):
            raise MultiAssetInputError(
                "insufficient_cross_sectional_periods: no timestamp met the configured asset count."
            )

        temporal_rows: list[dict[str, Any]] = []
        temporal_values: list[float] = []
        timestamps = prediction_frame[TIMESTAMP_COLUMN].drop_duplicates().to_numpy()
        for period_index, values in enumerate(
            np.array_split(timestamps, min(self.diagnostics.temporal_subperiods, len(timestamps)))
        ):
            period = prediction_frame.loc[
                prediction_frame[TIMESTAMP_COLUMN].isin(values)
            ]
            if self.mode is MultiAssetResearchMode.CROSS_SECTIONAL:
                period_diag = compute_cross_sectional_diagnostics(
                    period,
                    minimum_assets_per_timestamp=self.diagnostics.minimum_assets_per_timestamp,
                    quantile_fraction=None,
                )
                metric = period_diag["mean_rank_correlation"]
                metric_name = "mean_rank_correlation"
            else:
                period_diag = prediction_realized_metrics(
                    period["prediction"], period["target"]
                )
                metric = period_diag["spearman_rank_correlation"]
                metric_name = "pooled_spearman_rank_correlation"
            if metric is not None:
                temporal_values.append(float(metric))
            temporal_rows.append(
                {
                    "subperiod_id": f"screening-subperiod-{period_index:03d}",
                    "start_timestamp": pd.Timestamp(values[0]).isoformat(),
                    "end_timestamp": pd.Timestamp(values[-1]).isoformat(),
                    "prediction_rows": int(len(period)),
                    "metric_name": metric_name,
                    "metric": metric,
                }
            )
        stability = _stability(temporal_values)

        top_metrics = {
            "evaluation_rows": overall["evaluation_rows"],
            "observation_count": len(self.frame),
            "oos_rows": total_predictions,
            "missing_rate": (eligible_rows - total_predictions)
            / max(eligible_rows, 1),
            "mae": overall["mae"],
            "rmse": overall["rmse"],
            "predictive_correlation": overall["correlation"],
            "pooled_spearman_rank_correlation": overall[
                "spearman_rank_correlation"
            ],
            "mean_rank_correlation": cross["mean_rank_correlation"],
            "median_rank_correlation": cross["median_rank_correlation"],
            "rank_correlation_dispersion": cross[
                "rank_correlation_dispersion"
            ],
            "positive_rank_period_count": cross["positive_period_count"],
            "valid_rank_period_count": cross["valid_period_count"],
            "cross_sectional_unavailable_period_count": cross[
                "unavailable_period_count"
            ],
            "mean_top_bottom_target_spread": cross[
                "mean_top_bottom_target_spread"
            ],
            "total_rows": len(self.frame),
            "eligible_prediction_rows": eligible_rows,
            "oos_prediction_rows": total_predictions,
            "missing_oos_rows": eligible_rows - total_predictions,
            "oos_coverage": total_predictions / max(eligible_rows, 1),
            "asset_count": len(self.dataset.asset_ids),
            "model_fit_count": len(fit_rows),
            **stability,
        }
        runtime_metadata = {
            "backend_name": self.backend_name,
            "backend_version": self.backend_version,
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "pandas_version": pd.__version__,
            "capabilities": sorted(self.capabilities),
            "research_mode": self.mode.value,
            "screening_stage": EvidenceRole.DISCOVERY.value,
            "screening_is_canonical_validation": False,
            "screening_is_prospective_final": False,
            "portfolio_interpretation": False,
            "model": {
                "framework_kind": "lightgbm_regressor",
                "registry_owner": "src.models.registry",
                "parameters": model_parameters,
                "seed": seed,
                "shuffle": False,
                "refit_scope": self.mode.value,
            },
            "feature_set": {
                "reference": self.dataset.feature_set_reference,
                "columns": list(features),
                "owner": "src.features",
            },
            "target": {
                "name": self.dataset.target_name,
                "column": self.dataset.target_column,
                "reference": self.dataset.target_specification_reference,
                "horizon_bars": self.dataset.target_horizon_bars,
                "owner": "src.targets",
            },
            "segments": [segment.to_dict() for segment in self.dataset.segments],
            "purge_bars": self.purge_bars,
            "preprocessing_policy": self.preprocessing.to_dict(),
            "model_fits": fit_rows,
            "prediction_coverage": {
                "total_rows": len(self.frame),
                "eligible_rows": eligible_rows,
                "prediction_rows": total_predictions,
                "missing_prediction_rows": eligible_rows - total_predictions,
                "coverage": total_predictions / max(eligible_rows, 1),
                "no_oos_backfill": True,
            },
            "per_asset_diagnostics": per_asset,
            "cross_sectional_diagnostics": cross,
            "temporal_stability": {
                "subperiods": temporal_rows,
                **stability,
            },
            "prediction_records": [record.to_dict() for record in records],
            "prediction_artifact_policy": (
                "bounded_portable_records_embedded_in_discovery_trial_and_supported_by_"
                "existing_phase2_jsonl_artifacts"
            ),
            "dataset_fingerprint": dict(self.dataset.dataset_fingerprint),
            "source_snapshot_fingerprints": dict(
                self.dataset.source_snapshot_fingerprints
            ),
            "discovery_specification_hash": specification.specification_hash,
            "framework_config_hash": specification.config_hash,
            "full_search_cardinality": full_cardinality,
            "planned_trials": planned_trials,
            "fits_per_trial": fits_per_trial,
            "planned_model_fits": planned_trials * fits_per_trial,
            "parameter_mapping": self.parameter_mapping.to_dict(),
            "resource_policy": self.resources.to_dict(),
            "native_or_pickled_models_persisted": False,
        }
        checks = {
            "causal_features": True,
            "target_signal_compatible": True,
            "fold_safe_preprocessing": True,
            "oos_predictions": True,
            "chronological_segments": True,
            "purge_applied": self.purge_bars >= self.dataset.target_horizon_bars,
            "minimum_cross_sectional_asset_count": (
                cross["valid_period_count"] > 0
            ),
            "data_quality": True,
            "screening_only": True,
            "no_portfolio_semantics": True,
        }
        return DiscoveryTrial(
            trial_id=trial_id,
            research_run_id=research_run_id,
            parameters=parameters,
            status=TrialStatus.COMPLETED,
            metrics=_sanitize_metrics(top_metrics),
            checks=checks,
            seed=seed,
            runtime_metadata=runtime_metadata,
        )

    def _failed_trial(
        self,
        *,
        specification: DiscoverySpecification,
        research_run_id: str,
        parameters: Mapping[str, Any],
        reason: str,
        status: TrialStatus,
        full_cardinality: int,
        planned_trials: int,
        fits_per_trial: int,
    ) -> DiscoveryTrial:
        return DiscoveryTrial(
            trial_id=_trial_id(research_run_id, parameters),
            research_run_id=research_run_id,
            parameters=parameters,
            status=status,
            metrics={},
            checks={},
            seed=_trial_seed(
                specification.random_seed, research_run_id, parameters
            ),
            failure_reason=reason,
            runtime_metadata={
                "backend_name": self.backend_name,
                "backend_version": self.backend_version,
                "research_mode": self.mode.value,
                "screening_stage": EvidenceRole.DISCOVERY.value,
                "canonical_validation_required": True,
                "portfolio_interpretation": False,
                "dataset_fingerprint": dict(self.dataset.dataset_fingerprint),
                "discovery_specification_hash": specification.specification_hash,
                "full_search_cardinality": full_cardinality,
                "planned_trials": planned_trials,
                "fits_per_trial": fits_per_trial,
                "planned_model_fits": planned_trials * fits_per_trial,
            },
        )

    def execute(
        self,
        specification: DiscoverySpecification,
        *,
        research_run_id: str,
        evaluator: TrialEvaluator | None = None,
    ) -> tuple[DiscoveryTrial, ...]:
        if evaluator is not None:
            raise MultiAssetInputError(
                "R2 owns model fitting; evaluator injection is unsupported."
            )
        (
            full_cardinality,
            planned_trials,
            fits_per_trial,
            safe_training_mask,
            eligible_mask,
        ) = self._validate_specification(specification)
        trials: list[DiscoveryTrial] = []
        for parameters in specification.search_space.iter_grid(limit=planned_trials):
            try:
                trial = self._completed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    parameters=parameters,
                    safe_training_mask=safe_training_mask,
                    eligible_mask=eligible_mask,
                    full_cardinality=full_cardinality,
                    planned_trials=planned_trials,
                    fits_per_trial=fits_per_trial,
                )
            except MultiAssetInputError as exc:
                trial = self._failed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    parameters=parameters,
                    reason=f"invalid_input:{exc}",
                    status=TrialStatus.INVALID,
                    full_cardinality=full_cardinality,
                    planned_trials=planned_trials,
                    fits_per_trial=fits_per_trial,
                )
            except Exception as exc:
                trial = self._failed_trial(
                    specification=specification,
                    research_run_id=research_run_id,
                    parameters=parameters,
                    reason=f"model_fit_failure:{type(exc).__name__}:{exc}",
                    status=TrialStatus.FAILED,
                    full_cardinality=full_cardinality,
                    planned_trials=planned_trials,
                    fits_per_trial=fits_per_trial,
                )
            trials.append(trial)
        return tuple(trials)


__all__ = [
    "CrossSectionalDiagnosticPolicy",
    "CrossSectionalMetricStatus",
    "MultiAssetInputError",
    "MultiAssetParameterMapping",
    "MultiAssetPredictionRecord",
    "MultiAssetPreprocessingPolicy",
    "MultiAssetResearchError",
    "MultiAssetResearchMode",
    "MultiAssetResourceLimitError",
    "MultiAssetResourcePolicy",
    "MultiAssetSearchExecutor",
    "compute_cross_sectional_diagnostics",
]
