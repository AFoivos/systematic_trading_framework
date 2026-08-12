from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from src.src_data.quote_contract import (
    QuoteColumnNames,
    QuoteContractError,
    SpreadSemantics,
    classify_spread_bps_semantics,
    compute_quote_metrics,
    validate_canonical_quote_columns,
)
from src.utils.run_metadata import file_sha256


class QualitySeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class QualityStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


_SEVERITY_ORDER = {
    QualitySeverity.INFO: 0,
    QualitySeverity.WARNING: 1,
    QualitySeverity.ERROR: 2,
    QualitySeverity.CRITICAL: 3,
}

_QUALITY_CONTRACT_KEYS = {
    "asset",
    "timeframe",
    "timezone",
    "cadence",
    "timestamp_column",
    "required_columns",
    "ohlc_columns",
    "quote_columns",
    "require_canonical_quote_columns",
    "volume_column",
    "volume_semantics",
    "column_units",
    "require_all_column_units",
    "maximum_gap_multiple",
}
_QUOTE_COLUMN_KEYS = {
    "bid",
    "ask",
    "mid",
    "spread_absolute",
    "spread_fraction",
    "spread_bps",
}


def _require_non_empty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _require_boolean(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be boolean.")
    return value


def _require_name_sequence(
    value: Any,
    *,
    field_name: str,
    expected_length: int | None = None,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list or tuple of column names.")
    names = tuple(
        _require_non_empty_string(item, field_name=f"{field_name}[]") for item in value
    )
    if expected_length is not None and len(names) != expected_length:
        raise ValueError(f"{field_name} must contain exactly {expected_length} names.")
    if len(set(names)) != len(names):
        raise ValueError(f"{field_name} cannot contain duplicate names.")
    return names


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: QualitySeverity
    message: str
    count: int | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "count": self.count,
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class DataQualityContract:
    """Explicit quality assumptions for one market-data table."""

    asset: str
    timeframe: str
    timezone: str
    cadence: str | None
    timestamp_column: str = "timestamp"
    required_columns: tuple[str, ...] = ("open", "high", "low", "close")
    ohlc_columns: tuple[str, str, str, str] | None = ("open", "high", "low", "close")
    quote_columns: QuoteColumnNames | None = None
    require_canonical_quote_columns: bool = False
    volume_column: str | None = "volume"
    volume_semantics: str | None = None
    column_units: Mapping[str, str] = field(default_factory=dict)
    require_all_column_units: bool = True
    maximum_gap_multiple: float = 96.0

    def __post_init__(self) -> None:
        for field_name in ("asset", "timeframe", "timezone", "timestamp_column"):
            _require_non_empty_string(getattr(self, field_name), field_name=field_name)
        if self.cadence is not None:
            _require_non_empty_string(self.cadence, field_name="cadence")
        _require_name_sequence(self.required_columns, field_name="required_columns")
        if self.ohlc_columns is not None:
            _require_name_sequence(
                self.ohlc_columns,
                field_name="ohlc_columns",
                expected_length=4,
            )
        if self.quote_columns is not None:
            if not isinstance(self.quote_columns, QuoteColumnNames):
                raise ValueError("quote_columns must be QuoteColumnNames or null.")
            for field_name in _QUOTE_COLUMN_KEYS:
                _require_non_empty_string(
                    getattr(self.quote_columns, field_name),
                    field_name=f"quote_columns.{field_name}",
                )
        _require_boolean(
            self.require_canonical_quote_columns,
            field_name="require_canonical_quote_columns",
        )
        if self.require_canonical_quote_columns and self.quote_columns is None:
            raise ValueError(
                "require_canonical_quote_columns=true requires quote_columns."
            )
        _require_boolean(
            self.require_all_column_units,
            field_name="require_all_column_units",
        )
        if self.volume_column is not None:
            _require_non_empty_string(self.volume_column, field_name="volume_column")
        if self.volume_semantics is not None:
            _require_non_empty_string(
                self.volume_semantics, field_name="volume_semantics"
            )
        if not isinstance(self.column_units, Mapping):
            raise ValueError("column_units must be a mapping.")
        for column, unit in self.column_units.items():
            _require_non_empty_string(column, field_name="column_units key")
            _require_non_empty_string(unit, field_name=f"column_units.{column}")
        if (
            isinstance(self.maximum_gap_multiple, bool)
            or not isinstance(self.maximum_gap_multiple, (int, float))
            or not np.isfinite(float(self.maximum_gap_multiple))
            or float(self.maximum_gap_multiple) <= 1.0
        ):
            raise ValueError("maximum_gap_multiple must be finite and > 1.")

    def to_dict(self) -> dict[str, Any]:
        quote_columns = None
        if self.quote_columns is not None:
            quote_columns = {
                "bid": self.quote_columns.bid,
                "ask": self.quote_columns.ask,
                "mid": self.quote_columns.mid,
                "spread_absolute": self.quote_columns.spread_absolute,
                "spread_fraction": self.quote_columns.spread_fraction,
                "spread_bps": self.quote_columns.spread_bps,
            }
        return {
            "asset": self.asset,
            "timeframe": self.timeframe,
            "timezone": self.timezone,
            "cadence": self.cadence,
            "timestamp_column": self.timestamp_column,
            "required_columns": list(self.required_columns),
            "ohlc_columns": (
                None if self.ohlc_columns is None else list(self.ohlc_columns)
            ),
            "quote_columns": quote_columns,
            "require_canonical_quote_columns": self.require_canonical_quote_columns,
            "volume_column": self.volume_column,
            "volume_semantics": self.volume_semantics,
            "column_units": {
                str(key): str(value) for key, value in self.column_units.items()
            },
            "require_all_column_units": self.require_all_column_units,
            "maximum_gap_multiple": self.maximum_gap_multiple,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DataQualityContract:
        if not isinstance(payload, Mapping):
            raise ValueError("Serialized data-quality contract must be a mapping.")
        try:
            missing = sorted(_QUALITY_CONTRACT_KEYS.difference(payload))
            unexpected = sorted(set(payload).difference(_QUALITY_CONTRACT_KEYS))
            if missing or unexpected:
                raise ValueError(
                    "serialized keys mismatch; "
                    f"missing={missing}, unexpected={unexpected}"
                )
            quote_payload = payload["quote_columns"]
            quote_columns = None
            if quote_payload is not None:
                if not isinstance(quote_payload, Mapping):
                    raise ValueError("quote_columns must be a mapping or null.")
                quote_missing = sorted(_QUOTE_COLUMN_KEYS.difference(quote_payload))
                quote_unexpected = sorted(
                    set(quote_payload).difference(_QUOTE_COLUMN_KEYS)
                )
                if quote_missing or quote_unexpected:
                    raise ValueError(
                        "quote_columns keys mismatch; "
                        f"missing={quote_missing}, unexpected={quote_unexpected}"
                    )
                quote_columns = QuoteColumnNames(
                    **{
                        key: _require_non_empty_string(
                            quote_payload[key],
                            field_name=f"quote_columns.{key}",
                        )
                        for key in _QUOTE_COLUMN_KEYS
                    }
                )
            raw_ohlc = payload["ohlc_columns"]
            ohlc_columns = (
                None
                if raw_ohlc is None
                else _require_name_sequence(
                    raw_ohlc,
                    field_name="ohlc_columns",
                    expected_length=4,
                )
            )
            raw_units = payload["column_units"]
            if not isinstance(raw_units, Mapping):
                raise ValueError("column_units must be a mapping.")
            column_units = {
                _require_non_empty_string(
                    key, field_name="column_units key"
                ): _require_non_empty_string(value, field_name=f"column_units.{key}")
                for key, value in raw_units.items()
            }
            return cls(
                asset=_require_non_empty_string(payload["asset"], field_name="asset"),
                timeframe=_require_non_empty_string(
                    payload["timeframe"], field_name="timeframe"
                ),
                timezone=_require_non_empty_string(
                    payload["timezone"], field_name="timezone"
                ),
                cadence=(
                    None
                    if payload["cadence"] is None
                    else _require_non_empty_string(
                        payload["cadence"], field_name="cadence"
                    )
                ),
                timestamp_column=_require_non_empty_string(
                    payload["timestamp_column"], field_name="timestamp_column"
                ),
                required_columns=_require_name_sequence(
                    payload["required_columns"], field_name="required_columns"
                ),
                ohlc_columns=ohlc_columns,
                quote_columns=quote_columns,
                require_canonical_quote_columns=_require_boolean(
                    payload["require_canonical_quote_columns"],
                    field_name="require_canonical_quote_columns",
                ),
                volume_column=(
                    None
                    if payload["volume_column"] is None
                    else _require_non_empty_string(
                        payload["volume_column"], field_name="volume_column"
                    )
                ),
                volume_semantics=(
                    None
                    if payload["volume_semantics"] is None
                    else _require_non_empty_string(
                        payload["volume_semantics"], field_name="volume_semantics"
                    )
                ),
                column_units=column_units,
                require_all_column_units=_require_boolean(
                    payload["require_all_column_units"],
                    field_name="require_all_column_units",
                ),
                maximum_gap_multiple=payload["maximum_gap_multiple"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid serialized data-quality contract: {exc}"
            ) from exc


@dataclass(frozen=True)
class DataQualityReport:
    schema_version: int
    asset: str
    timeframe: str
    timezone: str
    status: QualityStatus
    research_eligible: bool
    metrics: dict[str, Any]
    issues: tuple[QualityIssue, ...]

    @property
    def maximum_severity(self) -> QualitySeverity:
        if not self.issues:
            return QualitySeverity.INFO
        return max(
            self.issues, key=lambda item: _SEVERITY_ORDER[item.severity]
        ).severity

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset": self.asset,
            "timeframe": self.timeframe,
            "timezone": self.timezone,
            "status": self.status.value,
            "research_eligible": self.research_eligible,
            "maximum_severity": self.maximum_severity.value,
            "metrics": dict(self.metrics),
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def human_summary(self) -> str:
        lines = [
            f"# Data Quality Report — {self.asset} {self.timeframe}",
            "",
            f"- Status: **{self.status.value}**",
            f"- Research eligible: **{str(self.research_eligible).lower()}**",
            f"- Timezone contract: `{self.timezone}`",
            f"- Rows: `{self.metrics.get('row_count', 0)}`",
            f"- First timestamp: `{self.metrics.get('first_timestamp')}`",
            f"- Last timestamp: `{self.metrics.get('last_timestamp')}`",
            f"- Duplicate timestamps: `{self.metrics.get('duplicate_timestamp_count', 0)}`",
            f"- Estimated missing intervals: `{self.metrics.get('estimated_missing_interval_count', 0)}`",
            "",
            "## Issues",
            "",
        ]
        if not self.issues:
            lines.append("No issues detected.")
        else:
            for issue in self.issues:
                suffix = f" (count={issue.count})" if issue.count is not None else ""
                lines.append(
                    f"- **{issue.severity.value} — {issue.code}**: {issue.message}{suffix}"
                )
        lines.append("")
        return "\n".join(lines)


def _issue(
    issues: list[QualityIssue],
    code: str,
    severity: QualitySeverity,
    message: str,
    *,
    count: int | None = None,
    context: Mapping[str, Any] | None = None,
) -> None:
    issues.append(
        QualityIssue(
            code=code,
            severity=severity,
            message=message,
            count=count,
            context=dict(context or {}),
        )
    )


def _timestamp_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column in frame.columns:
        return pd.Series(
            frame[column].to_numpy(copy=False), index=frame.index, name=column
        )
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(frame.index, index=frame.index, name=column)
    raise KeyError(
        f"Timestamp column '{column}' is missing and index is not DatetimeIndex."
    )


def _parse_explicit_timezone(
    values: pd.Series,
    *,
    timezone: str,
) -> tuple[pd.DatetimeIndex, int, int]:
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone '{timezone}'.") from exc

    parsed = pd.to_datetime(values, errors="coerce")
    invalid_before_timezone = int(pd.isna(parsed).sum())
    series = pd.Series(parsed)
    tz = getattr(series.dt, "tz", None)
    if tz is None:
        localized = series.dt.tz_localize(zone, ambiguous="NaT", nonexistent="NaT")
        dst_anomaly_count = int(localized.isna().sum()) - invalid_before_timezone
    else:
        localized = series.dt.tz_convert(zone)
        dst_anomaly_count = 0
    utc = localized.dt.tz_convert("UTC")
    return pd.DatetimeIndex(utc), invalid_before_timezone, max(dst_anomaly_count, 0)


def _numeric_frame(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {name: pd.to_numeric(frame[name], errors="coerce") for name in columns},
        index=frame.index,
    )


def run_data_quality_checks(
    frame: pd.DataFrame,
    contract: DataQualityContract,
) -> DataQualityReport:
    """Run fail-closed, machine-readable checks without mutating the input."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame.")
    issues: list[QualityIssue] = []
    metrics: dict[str, Any] = {
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": [str(column) for column in frame.columns],
        "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
        "column_units": {str(k): str(v) for k, v in contract.column_units.items()},
        "volume_semantics": contract.volume_semantics,
        "cadence_contract": contract.cadence,
    }

    if frame.empty:
        _issue(
            issues,
            "EMPTY_DATASET",
            QualitySeverity.CRITICAL,
            "Dataset contains zero rows.",
        )

    duplicated_column_mask = frame.columns.duplicated(keep=False)
    duplicate_column_count = int(duplicated_column_mask.sum())
    duplicated_column_names = {
        str(column)
        for column, duplicated in zip(frame.columns, duplicated_column_mask)
        if duplicated
    }
    metrics["duplicate_column_count"] = duplicate_column_count
    metrics["duplicate_column_names"] = sorted(duplicated_column_names)
    if duplicate_column_count:
        _issue(
            issues,
            "DUPLICATE_COLUMN_NAMES",
            QualitySeverity.CRITICAL,
            "Dataset schema contains duplicate column names.",
            count=duplicate_column_count,
        )

    missing_required = [
        name for name in contract.required_columns if name not in frame.columns
    ]
    if missing_required:
        _issue(
            issues,
            "MISSING_REQUIRED_COLUMNS",
            QualitySeverity.CRITICAL,
            f"Missing required columns: {missing_required}.",
            count=len(missing_required),
        )

    if contract.require_all_column_units:
        schema_names = {str(column) for column in frame.columns}
        if isinstance(frame.index, pd.DatetimeIndex):
            schema_names.add(contract.timestamp_column)
        missing_units = sorted(schema_names.difference(contract.column_units))
        if missing_units:
            _issue(
                issues,
                "MISSING_COLUMN_UNITS",
                QualitySeverity.ERROR,
                f"Column units are not declared for: {missing_units}.",
                count=len(missing_units),
            )
        extra_units = sorted(set(contract.column_units).difference(schema_names))
        if extra_units:
            _issue(
                issues,
                "UNMATCHED_COLUMN_UNITS",
                QualitySeverity.ERROR,
                f"Column units are declared for fields absent from the schema: {extra_units}.",
                count=len(extra_units),
            )

    try:
        if contract.timestamp_column in duplicated_column_names:
            raise ValueError(
                f"Timestamp column '{contract.timestamp_column}' is duplicated."
            )
        raw_timestamps = _timestamp_series(frame, contract.timestamp_column)
        timestamps, invalid_timestamp_count, dst_anomaly_count = (
            _parse_explicit_timezone(
                raw_timestamps,
                timezone=contract.timezone,
            )
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        timestamps = pd.DatetimeIndex([])
        invalid_timestamp_count = int(len(frame))
        dst_anomaly_count = 0
        _issue(issues, "INVALID_TIMESTAMP_CONTRACT", QualitySeverity.CRITICAL, str(exc))
    else:
        metrics["invalid_timestamp_count"] = invalid_timestamp_count
        metrics["dst_anomaly_count"] = dst_anomaly_count
        if invalid_timestamp_count:
            _issue(
                issues,
                "INVALID_TIMESTAMPS",
                QualitySeverity.CRITICAL,
                "Timestamp parsing produced invalid values.",
                count=invalid_timestamp_count,
            )
        if dst_anomaly_count:
            _issue(
                issues,
                "DST_LOCALIZATION_ANOMALY",
                QualitySeverity.ERROR,
                "Ambiguous or nonexistent local timestamps were detected during timezone localization.",
                count=dst_anomaly_count,
            )
        valid_timestamps = timestamps[~timestamps.isna()]
        metrics["first_timestamp"] = (
            valid_timestamps.min().isoformat() if len(valid_timestamps) else None
        )
        metrics["last_timestamp"] = (
            valid_timestamps.max().isoformat() if len(valid_timestamps) else None
        )
        duplicate_count = int(valid_timestamps.duplicated(keep=False).sum())
        metrics["duplicate_timestamp_count"] = duplicate_count
        if duplicate_count:
            _issue(
                issues,
                "DUPLICATE_TIMESTAMPS",
                QualitySeverity.ERROR,
                "Duplicate timestamps are not permitted in a research snapshot.",
                count=duplicate_count,
            )
        monotonic = bool(valid_timestamps.is_monotonic_increasing)
        metrics["timestamps_sorted"] = monotonic
        if not monotonic:
            _issue(
                issues,
                "UNSORTED_TIMESTAMPS",
                QualitySeverity.ERROR,
                "Timestamps must be sorted in non-decreasing order.",
            )

        metrics["estimated_missing_interval_count"] = 0
        metrics["gap_count"] = 0
        metrics["unexpected_short_interval_count"] = 0
        metrics["irregular_interval_count"] = 0
        metrics["maximum_gap_seconds"] = 0.0
        metrics["maximum_gap_multiple"] = 0.0
        if contract.cadence is not None and len(valid_timestamps) > 1:
            try:
                expected = pd.Timedelta(contract.cadence)
            except (TypeError, ValueError) as exc:
                _issue(issues, "INVALID_CADENCE", QualitySeverity.CRITICAL, str(exc))
            else:
                if expected <= pd.Timedelta(0):
                    _issue(
                        issues,
                        "INVALID_CADENCE",
                        QualitySeverity.CRITICAL,
                        "Cadence must be strictly positive.",
                    )
                else:
                    ordered_unique = valid_timestamps.sort_values().drop_duplicates()
                    deltas = pd.Series(ordered_unique[1:] - ordered_unique[:-1])
                    gap_mask = deltas > expected
                    short_interval_mask = deltas < expected
                    gaps = deltas[gap_mask]
                    short_intervals = deltas[short_interval_mask]
                    missing_count = int(
                        sum(
                            max(int(np.ceil(float(delta / expected))) - 1, 0)
                            for delta in gaps
                        )
                    )
                    maximum_gap = gaps.max() if len(gaps) else pd.Timedelta(0)
                    maximum_multiple = (
                        float(maximum_gap / expected)
                        if maximum_gap > pd.Timedelta(0)
                        else 0.0
                    )
                    metrics.update(
                        {
                            "expected_cadence_seconds": float(expected.total_seconds()),
                            "gap_count": int(len(gaps)),
                            "unexpected_short_interval_count": int(
                                len(short_intervals)
                            ),
                            "irregular_interval_count": int(
                                len(gaps) + len(short_intervals)
                            ),
                            "estimated_missing_interval_count": missing_count,
                            "maximum_gap_seconds": float(maximum_gap.total_seconds()),
                            "maximum_gap_multiple": maximum_multiple,
                        }
                    )
                    if len(gaps):
                        _issue(
                            issues,
                            "MISSING_INTERVALS",
                            QualitySeverity.WARNING,
                            "Observed timestamp gaps exceed the declared cadence.",
                            count=int(len(gaps)),
                            context={"estimated_missing_intervals": missing_count},
                        )
                    if len(short_intervals):
                        _issue(
                            issues,
                            "CADENCE_MISMATCH_SHORT_INTERVALS",
                            QualitySeverity.ERROR,
                            "Observed timestamp intervals are shorter than the declared cadence.",
                            count=int(len(short_intervals)),
                        )
                    if maximum_multiple > float(contract.maximum_gap_multiple):
                        _issue(
                            issues,
                            "SUSPICIOUS_GAP",
                            QualitySeverity.ERROR,
                            "Maximum gap exceeds the configured suspicious-gap threshold.",
                            context={
                                "observed_multiple": maximum_multiple,
                                "allowed_multiple": float(
                                    contract.maximum_gap_multiple
                                ),
                            },
                        )

    nan_counts: dict[str, int] = {}
    for position, column in enumerate(frame.columns):
        name = str(column)
        nan_counts[name] = nan_counts.get(name, 0) + int(
            frame.iloc[:, position].isna().sum()
        )
    metrics["nan_counts"] = nan_counts
    required_nan_count = sum(
        nan_counts.get(name, 0) for name in contract.required_columns
    )
    if required_nan_count:
        _issue(
            issues,
            "NAN_IN_REQUIRED_COLUMNS",
            QualitySeverity.ERROR,
            "Required columns contain NaN values.",
            count=int(required_nan_count),
        )
    optional_nan_count = sum(nan_counts.values()) - required_nan_count
    if optional_nan_count:
        _issue(
            issues,
            "NAN_IN_OPTIONAL_COLUMNS",
            QualitySeverity.WARNING,
            "Optional columns contain NaN values; semantics must remain explicit.",
            count=int(optional_nan_count),
        )

    numeric_candidate_names = {
        str(column) for column in frame.select_dtypes(include=[np.number]).columns
    }
    numeric_candidate_names.update(
        name for name in contract.required_columns if name in frame.columns
    )
    if contract.ohlc_columns is not None:
        numeric_candidate_names.update(
            name for name in contract.ohlc_columns if name in frame.columns
        )
    if contract.volume_column is not None and contract.volume_column in frame.columns:
        numeric_candidate_names.add(contract.volume_column)
    if contract.quote_columns is not None:
        numeric_candidate_names.update(
            name
            for name in (
                contract.quote_columns.bid,
                contract.quote_columns.ask,
                contract.quote_columns.mid,
                contract.quote_columns.spread_absolute,
                contract.quote_columns.spread_fraction,
                contract.quote_columns.spread_bps,
            )
            if name in frame.columns
        )
    inf_counts: dict[str, int] = {}
    for name in sorted(numeric_candidate_names.difference(duplicated_column_names)):
        values = pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=float)
        inf_counts[name] = int(np.isinf(values).sum())
    metrics["inf_counts"] = inf_counts
    total_inf = int(sum(inf_counts.values()))
    if total_inf:
        _issue(
            issues,
            "INFINITE_VALUES",
            QualitySeverity.ERROR,
            "Numeric columns contain infinite values.",
            count=total_inf,
        )

    numeric_required_invalid: dict[str, int] = {}
    for name in contract.required_columns:
        if name not in frame.columns or name in duplicated_column_names:
            continue
        observed = frame[name]
        converted = pd.to_numeric(observed, errors="coerce")
        invalid_count = int((observed.notna() & converted.isna()).sum())
        if invalid_count:
            numeric_required_invalid[name] = invalid_count
    metrics["non_numeric_required_counts"] = numeric_required_invalid
    if numeric_required_invalid:
        _issue(
            issues,
            "NON_NUMERIC_REQUIRED_VALUES",
            QualitySeverity.ERROR,
            "Required numeric fields contain values that cannot be parsed as numbers.",
            count=sum(numeric_required_invalid.values()),
            context={"counts_by_column": numeric_required_invalid},
        )

    if (
        contract.ohlc_columns is not None
        and set(contract.ohlc_columns).issubset(frame.columns)
        and not set(contract.ohlc_columns).intersection(duplicated_column_names)
    ):
        open_col, high_col, low_col, close_col = contract.ohlc_columns
        prices = _numeric_frame(frame, contract.ohlc_columns)
        finite = np.isfinite(prices.to_numpy(dtype=float)).all(axis=1)
        invalid_geometry = finite & (
            (prices[low_col] > prices[high_col])
            | (prices[open_col] < prices[low_col])
            | (prices[open_col] > prices[high_col])
            | (prices[close_col] < prices[low_col])
            | (prices[close_col] > prices[high_col])
        )
        nonpositive = finite & (prices <= 0.0).any(axis=1)
        metrics["invalid_ohlc_geometry_count"] = int(invalid_geometry.sum())
        metrics["nonpositive_ohlc_count"] = int(nonpositive.sum())
        if invalid_geometry.any():
            _issue(
                issues,
                "INVALID_OHLC_GEOMETRY",
                QualitySeverity.CRITICAL,
                "OHLC geometry requires low <= open/close <= high.",
                count=int(invalid_geometry.sum()),
            )
        if nonpositive.any():
            _issue(
                issues,
                "NONPOSITIVE_OHLC",
                QualitySeverity.CRITICAL,
                "OHLC prices must be strictly positive.",
                count=int(nonpositive.sum()),
            )

    if (
        contract.volume_column is not None
        and contract.volume_column not in frame.columns
    ):
        _issue(
            issues,
            "MISSING_VOLUME_COLUMN",
            QualitySeverity.ERROR,
            f"Declared volume column '{contract.volume_column}' is missing.",
        )
    elif (
        contract.volume_column is not None
        and contract.volume_column in frame.columns
        and contract.volume_column not in duplicated_column_names
    ):
        volume = pd.to_numeric(frame[contract.volume_column], errors="coerce")
        invalid_volume_count = int(
            (frame[contract.volume_column].notna() & volume.isna()).sum()
        )
        metrics["non_numeric_volume_count"] = invalid_volume_count
        if invalid_volume_count:
            _issue(
                issues,
                "NON_NUMERIC_VOLUME",
                QualitySeverity.ERROR,
                "Volume contains values that cannot be parsed as numbers.",
                count=invalid_volume_count,
            )
        negative_volume_count = int((volume < 0.0).sum())
        metrics["negative_volume_count"] = negative_volume_count
        if negative_volume_count:
            _issue(
                issues,
                "NEGATIVE_VOLUME",
                QualitySeverity.ERROR,
                "Volume must be non-negative.",
                count=negative_volume_count,
            )
        if not contract.volume_semantics or str(
            contract.volume_semantics
        ).strip().upper() in {
            "UNKNOWN",
            "AMBIGUOUS",
        }:
            _issue(
                issues,
                "AMBIGUOUS_VOLUME_SEMANTICS",
                QualitySeverity.ERROR,
                "A dataset containing volume must declare its provider-specific semantics.",
            )

    if contract.quote_columns is not None:
        columns = contract.quote_columns
        quote_source_columns = {columns.bid, columns.ask, columns.mid}
        quote_contract_columns = {
            columns.bid,
            columns.ask,
            columns.mid,
            columns.spread_absolute,
            columns.spread_fraction,
            columns.spread_bps,
        }
        duplicated_quotes = sorted(
            quote_contract_columns.intersection(duplicated_column_names)
        )
        if duplicated_quotes:
            _issue(
                issues,
                "DUPLICATE_QUOTE_COLUMNS",
                QualitySeverity.CRITICAL,
                f"Quote contract columns are duplicated: {duplicated_quotes}.",
                count=len(duplicated_quotes),
            )
        elif not quote_source_columns.issubset(frame.columns):
            missing = sorted(quote_source_columns.difference(frame.columns))
            _issue(
                issues,
                "MISSING_QUOTE_COLUMNS",
                QualitySeverity.CRITICAL,
                f"Missing declared bid/ask/mid columns: {missing}.",
                count=len(missing),
            )
        else:
            try:
                compute_quote_metrics(
                    frame[columns.bid],
                    frame[columns.ask],
                    mid=frame[columns.mid],
                    require_midpoint=True,
                    require_geometry=True,
                )
            except QuoteContractError as exc:
                _issue(
                    issues,
                    "INVALID_QUOTE_GEOMETRY",
                    QualitySeverity.CRITICAL,
                    str(exc),
                )
            semantics = classify_spread_bps_semantics(frame, columns=columns)
            metrics["spread_bps_semantics"] = semantics.value
            if semantics is SpreadSemantics.LEGACY_FRACTION:
                _issue(
                    issues,
                    "LEGACY_AMBIGUOUS_SPREAD_BPS",
                    QualitySeverity.CRITICAL,
                    "spread_bps stores a fraction rather than basis points.",
                )
            elif semantics is SpreadSemantics.INCONSISTENT:
                _issue(
                    issues,
                    "INCONSISTENT_SPREAD_BPS",
                    QualitySeverity.CRITICAL,
                    "spread_bps matches neither the canonical bps formula nor the known legacy fraction.",
                )
            elif (
                semantics is SpreadSemantics.INSUFFICIENT_COLUMNS
                and contract.require_canonical_quote_columns
            ):
                _issue(
                    issues,
                    "MISSING_CANONICAL_SPREAD_COLUMNS",
                    QualitySeverity.CRITICAL,
                    "Canonical spread_absolute, spread_fraction, and spread_bps columns are required.",
                )
            if contract.require_canonical_quote_columns:
                try:
                    validate_canonical_quote_columns(frame, columns=columns)
                except QuoteContractError as exc:
                    _issue(
                        issues,
                        "INVALID_CANONICAL_QUOTE_CONTRACT",
                        QualitySeverity.CRITICAL,
                        str(exc),
                    )

    blocking = any(
        issue.severity in {QualitySeverity.ERROR, QualitySeverity.CRITICAL}
        for issue in issues
    )
    warning = any(issue.severity is QualitySeverity.WARNING for issue in issues)
    status = (
        QualityStatus.FAIL
        if blocking
        else (QualityStatus.PASS_WITH_WARNINGS if warning else QualityStatus.PASS)
    )
    return DataQualityReport(
        schema_version=1,
        asset=contract.asset,
        timeframe=contract.timeframe,
        timezone=contract.timezone,
        status=status,
        research_eligible=not blocking,
        metrics=metrics,
        issues=tuple(issues),
    )


def assess_cross_asset_coverage(
    frames: Mapping[str, pd.DataFrame],
    *,
    timestamp_column: str = "timestamp",
) -> dict[str, Any]:
    """Measure union/intersection loss without performing an implicit inner join."""

    if not frames:
        raise ValueError("frames cannot be empty.")
    timestamp_sets: dict[str, set[pd.Timestamp]] = {}
    row_counts: dict[str, int] = {}
    for asset, frame in sorted(frames.items()):
        values = _timestamp_series(frame, timestamp_column)
        parsed = pd.to_datetime(values, errors="raise", utc=True)
        timestamp_sets[str(asset)] = set(pd.DatetimeIndex(parsed))
        row_counts[str(asset)] = int(len(frame))
    union = set().union(*timestamp_sets.values())
    intersection = set.intersection(*timestamp_sets.values())
    lost_by_asset = {
        asset: len(values) - len(intersection)
        for asset, values in timestamp_sets.items()
    }
    return {
        "assets": sorted(timestamp_sets),
        "rows_by_asset": row_counts,
        "unique_timestamps_by_asset": {
            asset: len(values) for asset, values in timestamp_sets.items()
        },
        "union_timestamp_count": len(union),
        "intersection_timestamp_count": len(intersection),
        "intersection_over_union": (len(intersection) / len(union)) if union else 0.0,
        "inner_join_loss_count": len(union) - len(intersection),
        "inner_join_rows_lost_by_asset": lost_by_asset,
        "inner_join_rows_lost_total": sum(lost_by_asset.values()),
    }


def assess_schema_consistency(frames: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    """Report exact column/dtype agreement across asset frames."""

    if not frames:
        raise ValueError("frames cannot be empty.")
    schemas = {
        str(asset): {
            "columns": [str(column) for column in frame.columns],
            "dtypes": {
                str(column): str(dtype) for column, dtype in frame.dtypes.items()
            },
        }
        for asset, frame in sorted(frames.items())
    }
    reference_asset = sorted(schemas)[0]
    reference = schemas[reference_asset]
    mismatches = {
        asset: schema for asset, schema in schemas.items() if schema != reference
    }
    return {
        "consistent": not mismatches,
        "reference_asset": reference_asset,
        "schemas": schemas,
        "mismatched_assets": sorted(mismatches),
    }


def find_exact_duplicate_files(paths: Iterable[str | Path]) -> dict[str, list[str]]:
    """Group byte-identical files by SHA-256."""

    groups: dict[str, list[str]] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"Dataset file not found: {path}")
        groups.setdefault(file_sha256(path), []).append(str(path))
    return {
        digest: sorted(group)
        for digest, group in sorted(groups.items())
        if len(group) > 1
    }


def write_quality_report(
    report: DataQualityReport,
    *,
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    """Persist the same reviewed report in machine- and human-readable forms."""

    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    markdown_target.write_text(report.human_summary(), encoding="utf-8")
    return json_target, markdown_target


__all__ = [
    "DataQualityContract",
    "DataQualityReport",
    "QualityIssue",
    "QualitySeverity",
    "QualityStatus",
    "assess_cross_asset_coverage",
    "assess_schema_consistency",
    "find_exact_duplicate_files",
    "run_data_quality_checks",
    "write_quality_report",
]
