"""Framework-owned contracts for portable multi-asset research datasets.

The contracts in this module describe already-computed framework features and
targets. They do not load market data, create features or targets, fit models,
or persist tables. Pandas is used only by the validation boundary; no pandas
object is retained by a portable metadata contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from src.src_data.research_roles import EvidenceRole
from src.utils.run_metadata import compute_dataframe_fingerprint

from .contracts import (
    ResearchContractError,
    _freeze_json_mapping,
    _require_exact_keys,
    _require_identifier,
    _require_json_array,
    _require_non_empty,
    _require_sha256,
    _require_unique_strings,
)


TIMESTAMP_COLUMN = "timestamp"
ASSET_ID_COLUMN = "asset_id"


# Dataset validation participates in the package-wide portable-contract error
# boundary, so callers need only one fail-closed exception family.
ResearchDatasetError = ResearchContractError


class ResearchSegmentPurpose(str, Enum):
    """Discovery-workflow purposes; these are not evidence roles."""

    TRAINING = "training"
    TUNING = "tuning"
    SCREENING = "screening"

    @property
    def evidence_role(self) -> EvidenceRole:
        """All R1 workflow segments remain discovery-stage evidence."""

        return EvidenceRole.DISCOVERY


class SegmentBoundary(str, Enum):
    """Supported deterministic timestamp-boundary conventions."""

    CLOSED = "closed"
    LEFT_CLOSED_RIGHT_OPEN = "left_closed_right_open"


class PredictionIneligibilityReason(str, Enum):
    """Portable reasons why an observed row cannot receive a prediction."""

    FEATURE_WARMUP = "feature_warmup"
    MISSING_TARGET = "missing_target"
    OUTSIDE_SCREENING_SEGMENT = "outside_screening_segment"
    INSUFFICIENT_HISTORICAL_CONTEXT = "insufficient_historical_context"
    EXPLICIT_EXCLUSION = "explicit_exclusion"


def _normalize_aware_timestamp(value: object, *, field_name: str) -> str:
    timestamp = _require_non_empty(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchDatasetError(f"{field_name} must be ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchDatasetError(f"{field_name} must include a timezone.")
    return parsed.isoformat()


def _as_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value)


def _require_timezone(value: object) -> str:
    timezone = _require_non_empty(value, field_name="timezone")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ResearchDatasetError(
            "timezone must be a valid IANA timezone name such as 'UTC'."
        ) from exc
    return timezone


def _timezone_name(value: object) -> str:
    for attribute in ("key", "zone"):
        name = getattr(value, attribute, None)
        if isinstance(name, str) and name:
            return name
    return str(value)


def _require_positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResearchDatasetError(f"{field_name} must be an integer > 0.")
    return value


@dataclass(frozen=True)
class ResearchSegment:
    """A reconstructible chronological discovery-workflow segment."""

    segment_id: str
    purpose: ResearchSegmentPurpose
    start_timestamp: str
    end_timestamp: str
    boundary: SegmentBoundary = SegmentBoundary.CLOSED

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "segment_id",
            _require_identifier(self.segment_id, field_name="segment_id"),
        )
        try:
            purpose = ResearchSegmentPurpose(self.purpose)
            boundary = SegmentBoundary(self.boundary)
        except (TypeError, ValueError) as exc:
            raise ResearchDatasetError(str(exc)) from exc
        start = _normalize_aware_timestamp(
            self.start_timestamp, field_name="segment start_timestamp"
        )
        end = _normalize_aware_timestamp(
            self.end_timestamp, field_name="segment end_timestamp"
        )
        start_value = _as_timestamp(start)
        end_value = _as_timestamp(end)
        if end_value < start_value:
            raise ResearchDatasetError(
                f"Segment {self.segment_id!r} has a reversed timestamp range."
            )
        if (
            end_value == start_value
            and boundary is SegmentBoundary.LEFT_CLOSED_RIGHT_OPEN
        ):
            raise ResearchDatasetError(
                f"Segment {self.segment_id!r} is empty under "
                "left-closed/right-open boundaries."
            )
        object.__setattr__(self, "purpose", purpose)
        object.__setattr__(self, "boundary", boundary)
        object.__setattr__(self, "start_timestamp", start)
        object.__setattr__(self, "end_timestamp", end)

    @property
    def evidence_role(self) -> EvidenceRole:
        """A segment name or purpose can never promote its evidence role."""

        return EvidenceRole.DISCOVERY

    def contains(self, timestamps: pd.Series) -> pd.Series:
        """Return the deterministic membership mask for supplied aware timestamps."""

        start = _as_timestamp(self.start_timestamp)
        end = _as_timestamp(self.end_timestamp)
        if self.boundary is SegmentBoundary.CLOSED:
            return timestamps.ge(start) & timestamps.le(end)
        return timestamps.ge(start) & timestamps.lt(end)

    def to_dict(self) -> dict[str, str]:
        return {
            "segment_id": self.segment_id,
            "purpose": self.purpose.value,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "boundary": self.boundary.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ResearchSegment:
        _require_exact_keys(
            payload,
            expected={
                "segment_id",
                "purpose",
                "start_timestamp",
                "end_timestamp",
                "boundary",
            },
            field_name="Research segment",
        )
        return cls(
            segment_id=payload["segment_id"],
            purpose=ResearchSegmentPurpose(payload["purpose"]),
            start_timestamp=payload["start_timestamp"],
            end_timestamp=payload["end_timestamp"],
            boundary=SegmentBoundary(payload["boundary"]),
        )


@dataclass(frozen=True)
class PredictionEligibilitySpec:
    """Column-level representation of row prediction eligibility."""

    eligible_column: str = "prediction_eligible"
    ineligibility_reason_column: str = "prediction_ineligibility_reason"
    allowed_ineligibility_reasons: tuple[PredictionIneligibilityReason, ...] = field(
        default_factory=lambda: tuple(PredictionIneligibilityReason)
    )

    def __post_init__(self) -> None:
        eligible_column = _require_identifier(
            self.eligible_column, field_name="eligible_column"
        )
        reason_column = _require_identifier(
            self.ineligibility_reason_column,
            field_name="ineligibility_reason_column",
        )
        if eligible_column == reason_column:
            raise ResearchDatasetError(
                "Prediction eligibility and reason columns must be different."
            )
        if isinstance(
            self.allowed_ineligibility_reasons, (str, bytes, bytearray)
        ):
            raise ResearchDatasetError(
                "allowed_ineligibility_reasons must be a sequence."
            )
        try:
            reasons = tuple(
                PredictionIneligibilityReason(reason)
                for reason in self.allowed_ineligibility_reasons
            )
        except (TypeError, ValueError) as exc:
            raise ResearchDatasetError(str(exc)) from exc
        if not reasons:
            raise ResearchDatasetError(
                "allowed_ineligibility_reasons cannot be empty."
            )
        if len(set(reasons)) != len(reasons):
            raise ResearchDatasetError(
                "allowed_ineligibility_reasons cannot contain duplicates."
            )
        object.__setattr__(self, "eligible_column", eligible_column)
        object.__setattr__(self, "ineligibility_reason_column", reason_column)
        object.__setattr__(
            self,
            "allowed_ineligibility_reasons",
            tuple(sorted(reasons, key=lambda reason: reason.value)),
        )

    @property
    def eligible_segment_purpose(self) -> ResearchSegmentPurpose:
        """Predictions in R1 may only be eligible in discovery screening rows."""

        return ResearchSegmentPurpose.SCREENING

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible_column": self.eligible_column,
            "ineligibility_reason_column": self.ineligibility_reason_column,
            "allowed_ineligibility_reasons": [
                reason.value for reason in self.allowed_ineligibility_reasons
            ],
            "eligible_segment_purpose": self.eligible_segment_purpose.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PredictionEligibilitySpec:
        _require_exact_keys(
            payload,
            expected={
                "eligible_column",
                "ineligibility_reason_column",
                "allowed_ineligibility_reasons",
                "eligible_segment_purpose",
            },
            field_name="Prediction eligibility specification",
        )
        if (
            payload["eligible_segment_purpose"]
            != ResearchSegmentPurpose.SCREENING.value
        ):
            raise ResearchDatasetError(
                "Prediction eligibility is fixed to the discovery screening segment."
            )
        return cls(
            eligible_column=payload["eligible_column"],
            ineligibility_reason_column=payload["ineligibility_reason_column"],
            allowed_ineligibility_reasons=tuple(
                PredictionIneligibilityReason(value)
                for value in _require_json_array(
                    payload["allowed_ineligibility_reasons"],
                    field_name="allowed_ineligibility_reasons",
                )
            ),
        )


def _segments_overlap(left: ResearchSegment, right: ResearchSegment) -> bool:
    left_end = _as_timestamp(left.end_timestamp)
    right_start = _as_timestamp(right.start_timestamp)
    if right_start < left_end:
        return True
    if right_start > left_end:
        return False
    return left.boundary is SegmentBoundary.CLOSED


@dataclass(frozen=True)
class PanelResearchDataset:
    """Portable metadata for an STF-owned long-form research dataset.

    The canonical row identity is the fixed pair (timestamp, asset_id).
    Feature names and the target column reference already-computed STF outputs.
    The table itself stays outside this metadata value.
    """

    dataset_id: str
    asset_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    feature_set_reference: str
    target_name: str
    target_column: str
    target_specification_reference: str
    target_horizon_bars: int
    dataset_fingerprint: Mapping[str, Any]
    source_snapshot_fingerprints: Mapping[str, str]
    evidence_role: EvidenceRole
    timezone: str
    sample_start_timestamp: str
    sample_end_timestamp: str
    segments: tuple[ResearchSegment, ...]
    prediction_eligibility: PredictionEligibilitySpec = field(
        default_factory=PredictionEligibilitySpec
    )
    transformation_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dataset_id",
            _require_identifier(self.dataset_id, field_name="dataset_id"),
        )
        raw_assets = _require_unique_strings(
            self.asset_ids, field_name="asset_ids", allow_empty=False
        )
        assets = tuple(
            sorted(
                _require_identifier(asset, field_name="asset_id")
                for asset in raw_assets
            )
        )
        object.__setattr__(self, "asset_ids", assets)

        features = _require_unique_strings(
            self.feature_names, field_name="feature_names", allow_empty=False
        )
        for feature in features:
            _require_identifier(feature, field_name="feature_name")
        object.__setattr__(self, "feature_names", features)
        object.__setattr__(
            self,
            "feature_set_reference",
            _require_non_empty(
                self.feature_set_reference, field_name="feature_set_reference"
            ),
        )
        target_name = _require_identifier(self.target_name, field_name="target_name")
        target_column = _require_identifier(
            self.target_column, field_name="target_column"
        )
        if target_column in features:
            raise ResearchDatasetError(
                "target_column cannot also be declared as a feature."
            )
        object.__setattr__(self, "target_name", target_name)
        object.__setattr__(self, "target_column", target_column)
        object.__setattr__(
            self,
            "target_specification_reference",
            _require_non_empty(
                self.target_specification_reference,
                field_name="target_specification_reference",
            ),
        )
        object.__setattr__(
            self,
            "target_horizon_bars",
            _require_positive_int(
                self.target_horizon_bars, field_name="target_horizon_bars"
            ),
        )

        fingerprint = _freeze_json_mapping(
            self.dataset_fingerprint, field_name="dataset_fingerprint"
        )
        _require_sha256(
            fingerprint.get("sha256"), field_name="dataset_fingerprint.sha256"
        )
        object.__setattr__(self, "dataset_fingerprint", fingerprint)

        if not isinstance(self.source_snapshot_fingerprints, Mapping):
            raise ResearchDatasetError(
                "source_snapshot_fingerprints must be a mapping."
            )
        if not self.source_snapshot_fingerprints:
            raise ResearchDatasetError(
                "source_snapshot_fingerprints cannot be empty."
            )
        sources: dict[str, str] = {}
        for reference in sorted(self.source_snapshot_fingerprints):
            normalized_reference = _require_non_empty(
                reference, field_name="source snapshot reference"
            )
            sources[normalized_reference] = _require_sha256(
                self.source_snapshot_fingerprints[reference],
                field_name=f"source_snapshot_fingerprints.{normalized_reference}",
            )
        object.__setattr__(
            self, "source_snapshot_fingerprints", MappingProxyType(sources)
        )

        try:
            evidence_role = EvidenceRole(self.evidence_role)
        except (TypeError, ValueError) as exc:
            raise ResearchDatasetError(str(exc)) from exc
        object.__setattr__(self, "evidence_role", evidence_role)
        object.__setattr__(self, "timezone", _require_timezone(self.timezone))

        sample_start = _normalize_aware_timestamp(
            self.sample_start_timestamp, field_name="sample_start_timestamp"
        )
        sample_end = _normalize_aware_timestamp(
            self.sample_end_timestamp, field_name="sample_end_timestamp"
        )
        if _as_timestamp(sample_end) < _as_timestamp(sample_start):
            raise ResearchDatasetError("Dataset sample range is reversed.")
        object.__setattr__(self, "sample_start_timestamp", sample_start)
        object.__setattr__(self, "sample_end_timestamp", sample_end)

        if isinstance(self.segments, (str, bytes, bytearray)):
            raise ResearchDatasetError("segments must be a sequence.")
        segments = tuple(self.segments)
        if any(not isinstance(segment, ResearchSegment) for segment in segments):
            raise ResearchDatasetError(
                "segments must contain only ResearchSegment values."
            )
        if len({segment.segment_id for segment in segments}) != len(segments):
            raise ResearchDatasetError(
                "segments cannot contain duplicate segment_id values."
            )
        segments = tuple(
            sorted(
                segments,
                key=lambda segment: (
                    _as_timestamp(segment.start_timestamp),
                    _as_timestamp(segment.end_timestamp),
                    segment.segment_id,
                ),
            )
        )
        if segments and evidence_role is not EvidenceRole.DISCOVERY:
            raise ResearchDatasetError(
                "TRAINING/TUNING/SCREENING segments are DISCOVERY-only and cannot "
                f"be attached to {evidence_role.value} evidence."
            )
        if evidence_role is EvidenceRole.DISCOVERY:
            purposes = {segment.purpose for segment in segments}
            required = set(ResearchSegmentPurpose)
            if purposes != required:
                missing = sorted(purpose.value for purpose in required - purposes)
                raise ResearchDatasetError(
                    "DISCOVERY datasets require TRAINING, TUNING, and SCREENING "
                    f"segments; missing={missing}."
                )
        dataset_start = _as_timestamp(sample_start)
        dataset_end = _as_timestamp(sample_end)
        for segment in segments:
            segment_start = _as_timestamp(segment.start_timestamp)
            segment_end = _as_timestamp(segment.end_timestamp)
            if segment_start < dataset_start or segment_end > dataset_end:
                raise ResearchDatasetError(
                    f"Segment {segment.segment_id!r} lies outside dataset "
                    "sample boundaries."
                )
        for left, right in zip(segments, segments[1:]):
            if _segments_overlap(left, right):
                raise ResearchDatasetError(
                    f"Segments {left.segment_id!r} and {right.segment_id!r} overlap."
                )
        object.__setattr__(self, "segments", segments)

        if not isinstance(self.prediction_eligibility, PredictionEligibilitySpec):
            raise ResearchDatasetError(
                "prediction_eligibility must be PredictionEligibilitySpec."
            )
        reserved_columns = {
            TIMESTAMP_COLUMN,
            ASSET_ID_COLUMN,
            *features,
            target_column,
        }
        for column in (
            self.prediction_eligibility.eligible_column,
            self.prediction_eligibility.ineligibility_reason_column,
        ):
            if column in reserved_columns:
                raise ResearchDatasetError(
                    f"Prediction eligibility column {column!r} conflicts with "
                    "dataset columns."
                )

        object.__setattr__(
            self,
            "transformation_metadata",
            _freeze_json_mapping(
                self.transformation_metadata, field_name="transformation_metadata"
            ),
        )

    @property
    def timestamp_column(self) -> str:
        return TIMESTAMP_COLUMN

    @property
    def asset_id_column(self) -> str:
        return ASSET_ID_COLUMN

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "row_identity": [self.timestamp_column, self.asset_id_column],
            "asset_ids": list(self.asset_ids),
            "feature_names": list(self.feature_names),
            "feature_set_reference": self.feature_set_reference,
            "target_name": self.target_name,
            "target_column": self.target_column,
            "target_specification_reference": self.target_specification_reference,
            "target_horizon_bars": self.target_horizon_bars,
            "dataset_fingerprint": dict(self.dataset_fingerprint),
            "source_snapshot_fingerprints": dict(
                self.source_snapshot_fingerprints
            ),
            "evidence_role": self.evidence_role.value,
            "timezone": self.timezone,
            "sample_start_timestamp": self.sample_start_timestamp,
            "sample_end_timestamp": self.sample_end_timestamp,
            "segments": [segment.to_dict() for segment in self.segments],
            "prediction_eligibility": self.prediction_eligibility.to_dict(),
            "transformation_metadata": dict(self.transformation_metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PanelResearchDataset:
        _require_exact_keys(
            payload,
            expected={
                "dataset_id",
                "row_identity",
                "asset_ids",
                "feature_names",
                "feature_set_reference",
                "target_name",
                "target_column",
                "target_specification_reference",
                "target_horizon_bars",
                "dataset_fingerprint",
                "source_snapshot_fingerprints",
                "evidence_role",
                "timezone",
                "sample_start_timestamp",
                "sample_end_timestamp",
                "segments",
                "prediction_eligibility",
                "transformation_metadata",
            },
            field_name="Panel research dataset",
        )
        row_identity = _require_json_array(
            payload["row_identity"], field_name="row_identity"
        )
        if row_identity != [TIMESTAMP_COLUMN, ASSET_ID_COLUMN]:
            raise ResearchDatasetError(
                "row_identity must be exactly ['timestamp', 'asset_id']."
            )
        return cls(
            dataset_id=payload["dataset_id"],
            asset_ids=tuple(
                _require_json_array(payload["asset_ids"], field_name="asset_ids")
            ),
            feature_names=tuple(
                _require_json_array(
                    payload["feature_names"], field_name="feature_names"
                )
            ),
            feature_set_reference=payload["feature_set_reference"],
            target_name=payload["target_name"],
            target_column=payload["target_column"],
            target_specification_reference=payload[
                "target_specification_reference"
            ],
            target_horizon_bars=payload["target_horizon_bars"],
            dataset_fingerprint=payload["dataset_fingerprint"],
            source_snapshot_fingerprints=payload[
                "source_snapshot_fingerprints"
            ],
            evidence_role=EvidenceRole(payload["evidence_role"]),
            timezone=payload["timezone"],
            sample_start_timestamp=payload["sample_start_timestamp"],
            sample_end_timestamp=payload["sample_end_timestamp"],
            segments=tuple(
                ResearchSegment.from_dict(item)
                for item in _require_json_array(
                    payload["segments"], field_name="segments"
                )
            ),
            prediction_eligibility=PredictionEligibilitySpec.from_dict(
                payload["prediction_eligibility"]
            ),
            transformation_metadata=payload["transformation_metadata"],
        )


@dataclass(frozen=True)
class ResearchDatasetValidationReport:
    """Portable summary produced after a table satisfies its metadata contract."""

    dataset_id: str
    row_count: int
    timestamp_count: int
    asset_count: int
    observed_row_identities: int
    possible_row_identities: int
    missing_observation_count: int
    eligible_prediction_rows: int
    ineligible_prediction_rows: int
    dataset_fingerprint: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "row_count": self.row_count,
            "timestamp_count": self.timestamp_count,
            "asset_count": self.asset_count,
            "observed_row_identities": self.observed_row_identities,
            "possible_row_identities": self.possible_row_identities,
            "missing_observation_count": self.missing_observation_count,
            "eligible_prediction_rows": self.eligible_prediction_rows,
            "ineligible_prediction_rows": self.ineligible_prediction_rows,
            "dataset_fingerprint": dict(self.dataset_fingerprint),
        }


def compute_research_dataset_fingerprint(frame: pd.DataFrame) -> dict[str, Any]:
    """Reuse the existing dataframe fingerprint on canonical long-form row order."""

    if not isinstance(frame, pd.DataFrame):
        raise ResearchDatasetError("frame must be a pandas DataFrame.")
    if frame.columns.duplicated().any():
        raise ResearchDatasetError("Research dataset columns must be unique.")
    missing = [
        column
        for column in (TIMESTAMP_COLUMN, ASSET_ID_COLUMN)
        if column not in frame.columns
    ]
    if missing:
        raise ResearchDatasetError(
            f"Research dataset is missing row identity columns: {missing}."
        )
    canonical = frame.sort_values(
        [TIMESTAMP_COLUMN, ASSET_ID_COLUMN], kind="mergesort"
    ).reset_index(drop=True)
    return compute_dataframe_fingerprint(canonical)


def _validate_exact_columns(
    frame: pd.DataFrame, metadata: PanelResearchDataset
) -> None:
    eligibility = metadata.prediction_eligibility
    expected = {
        TIMESTAMP_COLUMN,
        ASSET_ID_COLUMN,
        *metadata.feature_names,
        metadata.target_column,
        eligibility.eligible_column,
        eligibility.ineligibility_reason_column,
    }
    missing = sorted(expected.difference(frame.columns))
    unexpected = sorted(set(frame.columns).difference(expected))
    if missing or unexpected:
        raise ResearchDatasetError(
            f"Research dataset columns mismatch; missing={missing}, "
            f"unexpected={unexpected}."
        )


def _validate_row_identity(
    frame: pd.DataFrame, metadata: PanelResearchDataset
) -> tuple[pd.Series, pd.Series]:
    timestamps = frame[TIMESTAMP_COLUMN]
    if not isinstance(timestamps.dtype, pd.DatetimeTZDtype):
        raise ResearchDatasetError(
            "timestamp must be a timezone-aware pandas datetime column."
        )
    if timestamps.isna().any():
        raise ResearchDatasetError("timestamp cannot contain missing values.")
    actual_timezone = _timezone_name(timestamps.dt.tz)
    if actual_timezone != metadata.timezone:
        raise ResearchDatasetError(
            f"timestamp timezone {actual_timezone!r} does not match metadata "
            f"timezone {metadata.timezone!r}."
        )

    assets = frame[ASSET_ID_COLUMN]
    if assets.isna().any():
        raise ResearchDatasetError("asset_id cannot contain missing values.")
    normalized_assets: list[str] = []
    for position, value in enumerate(assets.tolist()):
        if not isinstance(value, str) or value != value.strip():
            raise ResearchDatasetError(
                f"asset_id row {position} must be a canonical non-empty string."
            )
        normalized_assets.append(
            _require_identifier(value, field_name=f"asset_id row {position}")
        )
    asset_series = pd.Series(normalized_assets, index=frame.index, dtype="object")
    actual_assets = tuple(sorted(asset_series.unique().tolist()))
    if actual_assets != metadata.asset_ids:
        raise ResearchDatasetError(
            f"Table asset universe {actual_assets} does not match metadata "
            f"asset_ids {metadata.asset_ids}."
        )

    identity = pd.DataFrame(
        {TIMESTAMP_COLUMN: timestamps, ASSET_ID_COLUMN: asset_series}
    )
    if identity.duplicated([TIMESTAMP_COLUMN, ASSET_ID_COLUMN]).any():
        raise ResearchDatasetError(
            "Research dataset contains duplicate (timestamp, asset_id) row identities."
        )
    canonical_identity = identity.sort_values(
        [TIMESTAMP_COLUMN, ASSET_ID_COLUMN], kind="mergesort"
    ).reset_index(drop=True)
    if not identity.reset_index(drop=True).equals(canonical_identity):
        raise ResearchDatasetError(
            "Research dataset rows must be sorted by timestamp then asset_id."
        )
    if timestamps.iloc[0] != _as_timestamp(metadata.sample_start_timestamp):
        raise ResearchDatasetError(
            "sample_start_timestamp does not match the first observed timestamp."
        )
    if timestamps.iloc[-1] != _as_timestamp(metadata.sample_end_timestamp):
        raise ResearchDatasetError(
            "sample_end_timestamp does not match the last observed timestamp."
        )
    return timestamps, asset_series


def _validate_numeric_values(
    frame: pd.DataFrame, metadata: PanelResearchDataset
) -> pd.Series:
    value_columns = (*metadata.feature_names, metadata.target_column)
    for column in value_columns:
        if not (
            pd.api.types.is_numeric_dtype(frame[column])
            or pd.api.types.is_bool_dtype(frame[column])
        ):
            raise ResearchDatasetError(
                f"Research dataset column {column!r} must be numeric or boolean."
            )
        numeric = pd.to_numeric(frame[column], errors="coerce")
        values = numeric.to_numpy(dtype=float, na_value=np.nan)
        if np.isinf(values).any():
            raise ResearchDatasetError(
                f"Research dataset column {column!r} cannot contain infinity."
            )
    return frame.loc[:, list(value_columns)].isna().any(axis=1)


def _validate_segments(
    timestamps: pd.Series, metadata: PanelResearchDataset
) -> pd.Series:
    screening_mask = pd.Series(False, index=timestamps.index, dtype=bool)
    for segment in metadata.segments:
        membership = segment.contains(timestamps)
        if not membership.any():
            raise ResearchDatasetError(
                f"Segment {segment.segment_id!r} contains no observed rows."
            )
        if segment.purpose is ResearchSegmentPurpose.SCREENING:
            screening_mask |= membership
    return screening_mask


def _validate_prediction_eligibility(
    frame: pd.DataFrame,
    metadata: PanelResearchDataset,
    *,
    screening_mask: pd.Series,
    missing_required_values: pd.Series,
) -> pd.Series:
    specification = metadata.prediction_eligibility
    eligible = frame[specification.eligible_column]
    if not pd.api.types.is_bool_dtype(eligible.dtype):
        raise ResearchDatasetError(
            f"{specification.eligible_column} must be a boolean column."
        )
    if eligible.isna().any():
        raise ResearchDatasetError(
            f"{specification.eligible_column} cannot contain missing values."
        )
    eligible = eligible.astype(bool)
    if (eligible & ~screening_mask).any():
        raise ResearchDatasetError(
            "Prediction-eligible rows must belong to a SCREENING segment."
        )
    if (eligible & missing_required_values).any():
        raise ResearchDatasetError(
            "Prediction-eligible rows cannot have missing feature or target values."
        )

    reasons = frame[specification.ineligibility_reason_column]
    reason_missing = reasons.isna() | reasons.astype("string").str.strip().eq("")
    if (eligible & ~reason_missing).any():
        raise ResearchDatasetError(
            "Prediction-eligible rows cannot carry an ineligibility reason."
        )
    if ((~eligible) & reason_missing).any():
        raise ResearchDatasetError(
            "Prediction-ineligible rows require an explicit reason."
        )
    allowed = {
        reason.value for reason in specification.allowed_ineligibility_reasons
    }
    supplied = set(reasons.loc[~reason_missing].astype(str))
    unexpected = sorted(supplied.difference(allowed))
    if unexpected:
        raise ResearchDatasetError(
            f"Unknown prediction ineligibility reasons: {unexpected}."
        )
    return eligible


def validate_research_dataset(
    frame: pd.DataFrame,
    metadata: PanelResearchDataset,
) -> ResearchDatasetValidationReport:
    """Validate a supplied long-form table without modifying or densifying it."""

    if not isinstance(frame, pd.DataFrame):
        raise ResearchDatasetError("frame must be a pandas DataFrame.")
    if not isinstance(metadata, PanelResearchDataset):
        raise ResearchDatasetError("metadata must be PanelResearchDataset.")
    if frame.empty:
        raise ResearchDatasetError("Research dataset frame cannot be empty.")
    if frame.columns.duplicated().any():
        raise ResearchDatasetError("Research dataset columns must be unique.")

    _validate_exact_columns(frame, metadata)
    timestamps, _ = _validate_row_identity(frame, metadata)
    missing_required_values = _validate_numeric_values(frame, metadata)
    screening_mask = _validate_segments(timestamps, metadata)
    eligible = _validate_prediction_eligibility(
        frame,
        metadata,
        screening_mask=screening_mask,
        missing_required_values=missing_required_values,
    )

    actual_fingerprint = compute_research_dataset_fingerprint(frame)
    if actual_fingerprint["sha256"] != metadata.dataset_fingerprint["sha256"]:
        raise ResearchDatasetError(
            "Research dataset fingerprint does not match the supplied table."
        )
    if (
        "rows" in metadata.dataset_fingerprint
        and metadata.dataset_fingerprint["rows"] != actual_fingerprint["rows"]
    ):
        raise ResearchDatasetError(
            "Research dataset fingerprint row count does not match the supplied table."
        )

    timestamp_count = int(timestamps.nunique())
    asset_count = len(metadata.asset_ids)
    observed = len(frame)
    possible = timestamp_count * asset_count
    return ResearchDatasetValidationReport(
        dataset_id=metadata.dataset_id,
        row_count=observed,
        timestamp_count=timestamp_count,
        asset_count=asset_count,
        observed_row_identities=observed,
        possible_row_identities=possible,
        missing_observation_count=possible - observed,
        eligible_prediction_rows=int(eligible.sum()),
        ineligible_prediction_rows=int((~eligible).sum()),
        dataset_fingerprint=MappingProxyType(dict(actual_fingerprint)),
    )


__all__ = [
    "ASSET_ID_COLUMN",
    "TIMESTAMP_COLUMN",
    "PanelResearchDataset",
    "PredictionEligibilitySpec",
    "PredictionIneligibilityReason",
    "ResearchDatasetError",
    "ResearchDatasetValidationReport",
    "ResearchSegment",
    "ResearchSegmentPurpose",
    "SegmentBoundary",
    "compute_research_dataset_fingerprint",
    "validate_research_dataset",
]
