from __future__ import annotations

"""Point-in-time-safe primitive features for preregistered alpha discovery."""

from typing import Final, Sequence

import numpy as np
import pandas as pd

from src.src_data.alpha_discovery_eligibility import build_bar_eligibility

LOG_RETURN_WINDOWS: Final[tuple[int, ...]] = (1, 4, 16, 48)
PATH_EFFICIENCY_WINDOWS: Final[tuple[int, ...]] = (8, 16, 48)
REALIZED_VOLATILITY_WINDOWS: Final[tuple[int, ...]] = (16, 48, 192)
CONTINUOUS_FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    *(f"log_return_{window}" for window in LOG_RETURN_WINDOWS),
    *(f"path_efficiency_{window}" for window in PATH_EFFICIENCY_WINDOWS),
    *(f"realized_volatility_{window}" for window in REALIZED_VOLATILITY_WINDOWS),
    "normalized_range",
    "close_location",
)
CATEGORICAL_FEATURE_COLUMNS: Final[tuple[str, ...]] = ("utc_hour", "weekday")
PRIMITIVE_FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    *CONTINUOUS_FEATURE_COLUMNS,
    *CATEGORICAL_FEATURE_COLUMNS,
)
STATE_ELIGIBLE_COLUMN: Final[str] = "eligible_state"
GAP_SEGMENT_COLUMN: Final[str] = "gap_segment_id"


class AlphaDiscoveryFeatureError(ValueError):
    """Raised when primitive features cannot be constructed causally."""


def feature_eligibility_column(feature: str) -> str:
    if feature not in PRIMITIVE_FEATURE_COLUMNS:
        raise AlphaDiscoveryFeatureError(f"Unknown primitive feature column: {feature!r}.")
    return f"eligible_feature__{feature}"


def _validated_source(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame.")
    required = {"timestamp", "mid_high", "mid_low", "mid_close"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise AlphaDiscoveryFeatureError(f"Missing primitive inputs: {missing}.")
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        raise AlphaDiscoveryFeatureError(
            "Primitive input timestamps must be valid UTC."
        )
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise AlphaDiscoveryFeatureError(
            "Primitive input timestamps must be unique and sorted."
        )
    close = pd.to_numeric(frame["mid_close"], errors="coerce")
    if close.isna().any() or not np.isfinite(close.to_numpy(dtype=float)).all():
        raise AlphaDiscoveryFeatureError("mid_close must be finite and non-missing.")
    if (close <= 0.0).any():
        raise AlphaDiscoveryFeatureError("mid_close must be strictly positive.")
    return timestamps, close


def build_alpha_discovery_features(
    frame: pd.DataFrame,
    *,
    log_return_windows: Sequence[int] = LOG_RETURN_WINDOWS,
    path_efficiency_windows: Sequence[int] = PATH_EFFICIENCY_WINDOWS,
    realized_volatility_windows: Sequence[int] = REALIZED_VOLATILITY_WINDOWS,
) -> pd.DataFrame:
    """Build features using information available no later than ``close[t]``.

    ``timestamp`` is the canonical left-labelled UTC bar timestamp.  Calendar
    features therefore describe the bar-open timestamp and become available
    together with the remaining fields at that bar's close.
    """

    timestamps, close = _validated_source(frame)
    eligibility = build_bar_eligibility(frame)
    high = pd.to_numeric(frame["mid_high"], errors="coerce")
    low = pd.to_numeric(frame["mid_low"], errors="coerce")
    if high.isna().any() or low.isna().any():
        raise AlphaDiscoveryFeatureError("mid_high and mid_low must be numeric.")
    if ((high < close) | (low > close) | (high < low)).any():
        raise AlphaDiscoveryFeatureError("MID OHLC geometry is invalid.")

    log_close = np.log(close.astype(float))
    one_bar_log_return = log_close.diff()
    output = pd.DataFrame({"timestamp": timestamps})
    feature_masks: dict[str, np.ndarray] = {}

    for window in log_return_windows:
        if int(window) <= 0:
            raise AlphaDiscoveryFeatureError("Log-return windows must be positive.")
        column = f"log_return_{int(window)}"
        mask = eligibility.trailing_window(int(window))
        output[column] = log_close.diff(int(window)).where(mask)
        feature_masks[column] = mask

    absolute_steps = one_bar_log_return.abs()
    for window in path_efficiency_windows:
        resolved = int(window)
        if resolved <= 0:
            raise AlphaDiscoveryFeatureError(
                "Path-efficiency windows must be positive."
            )
        displacement = log_close.diff(resolved).abs()
        path_length = absolute_steps.rolling(resolved, min_periods=resolved).sum()
        efficiency = displacement / path_length
        column = f"path_efficiency_{resolved}"
        mask = eligibility.trailing_window(resolved)
        output[column] = efficiency.where((path_length > 0.0) & mask)
        feature_masks[column] = mask

    squared_returns = one_bar_log_return.pow(2)
    for window in realized_volatility_windows:
        resolved = int(window)
        if resolved <= 0:
            raise AlphaDiscoveryFeatureError(
                "Realized-volatility windows must be positive."
            )
        column = f"realized_volatility_{resolved}"
        mask = eligibility.trailing_window(resolved)
        output[column] = np.sqrt(
            squared_returns.rolling(resolved, min_periods=resolved).sum()
        ).where(mask)
        feature_masks[column] = mask

    state_mask = eligibility.full_bar
    output["normalized_range"] = ((high - low) / close).where(state_mask)
    bar_range = high - low
    output["close_location"] = ((close - low) / bar_range).where(
        (bar_range > 0.0) & state_mask
    )
    output["utc_hour"] = timestamps.dt.hour.astype("Int8").where(state_mask)
    output["weekday"] = timestamps.dt.weekday.astype("Int8").where(state_mask)
    for column in ("normalized_range", "close_location", "utc_hour", "weekday"):
        feature_masks[column] = state_mask
    output[STATE_ELIGIBLE_COLUMN] = state_mask
    output[GAP_SEGMENT_COLUMN] = eligibility.gap_segment_id
    for feature, mask in feature_masks.items():
        output[feature_eligibility_column(feature)] = mask
    ordered = [
        "timestamp",
        *PRIMITIVE_FEATURE_COLUMNS,
        STATE_ELIGIBLE_COLUMN,
        GAP_SEGMENT_COLUMN,
        *(feature_eligibility_column(feature) for feature in PRIMITIVE_FEATURE_COLUMNS),
    ]
    return output[ordered]


def primitive_feature_family(column: str) -> str:
    if column.startswith("log_return_"):
        return "log_returns"
    if column.startswith("path_efficiency_"):
        return "path_efficiency"
    if column.startswith("realized_volatility_"):
        return "realized_volatility"
    if column in {"normalized_range", "close_location", "utc_hour", "weekday"}:
        return column
    raise AlphaDiscoveryFeatureError(f"Unknown primitive feature column: {column!r}.")


__all__ = [
    "AlphaDiscoveryFeatureError",
    "CATEGORICAL_FEATURE_COLUMNS",
    "CONTINUOUS_FEATURE_COLUMNS",
    "LOG_RETURN_WINDOWS",
    "PATH_EFFICIENCY_WINDOWS",
    "PRIMITIVE_FEATURE_COLUMNS",
    "REALIZED_VOLATILITY_WINDOWS",
    "GAP_SEGMENT_COLUMN",
    "STATE_ELIGIBLE_COLUMN",
    "build_alpha_discovery_features",
    "feature_eligibility_column",
    "primitive_feature_family",
]
