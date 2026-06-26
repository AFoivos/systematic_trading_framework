from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd


def index_in_timezone(index: pd.Index, timezone: str) -> pd.DatetimeIndex:
    """
    Apply the registered ``index_in_timezone`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: index_in_timezone
            params:
              index: <required>
              timezone: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    index:
        Configuration parameter accepted by this feature.
    timezone:
        Configuration parameter accepted by this feature.
    """
    idx = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(str(timezone))


def session_mask(hours: pd.Index, index: pd.Index, *, start_hour: int, end_hour: int) -> pd.Series:
    """
    Apply the registered ``session_mask`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: session_mask
            params:
              hours: <required>
              index: <required>
              start_hour: <required>
              end_hour: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    hours:
        Configuration parameter accepted by this feature.
    index:
        Configuration parameter accepted by this feature.
    start_hour:
        Configuration parameter accepted by this feature.
    end_hour:
        Configuration parameter accepted by this feature.
    """
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 24):
        raise ValueError("Session hours must satisfy 0 <= start_hour <= 23 and 0 <= end_hour <= 24.")
    if start_hour == end_hour:
        return pd.Series(True, index=index, dtype="float32")
    if start_hour < end_hour:
        mask = (hours >= start_hour) & (hours < end_hour)
    else:
        mask = (hours >= start_hour) | (hours < end_hour)
    return pd.Series(mask.astype("float32"), index=index, dtype="float32")


def add_session_context_features(
    df: pd.DataFrame,
    *,
    timezone: str = "UTC",
    add_cyclical_time: bool = True,
    include_weekend_flag: bool = True,
    sessions: Mapping[str, Sequence[int]] | None = None,
) -> pd.DataFrame:
    """
    Apply the registered ``session_context`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: session_context
            params:
              timezone: UTC
              add_cyclical_time: true
              include_weekend_flag: true
              sessions: null
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    timezone:
        Configuration parameter accepted by this feature. Default: ``UTC``.
    add_cyclical_time:
        Boolean switch controlling optional feature behavior. Default: ``true``.
    include_weekend_flag:
        Configuration parameter accepted by this feature. Default: ``true``.
    sessions:
        Configuration parameter accepted by this feature. Default: ``null``.
    """
    out = df.copy()
    local_idx = index_in_timezone(out.index, timezone)
    hours = pd.Index(local_idx.hour, dtype="int32")
    day_of_week = pd.Index(local_idx.dayofweek, dtype="int32")

    if add_cyclical_time:
        out["hour_sin_24"] = np.sin(2.0 * np.pi * hours.to_numpy(dtype=float) / 24.0).astype("float32")
        out["hour_cos_24"] = np.cos(2.0 * np.pi * hours.to_numpy(dtype=float) / 24.0).astype("float32")
        out["day_of_week_sin_7"] = np.sin(2.0 * np.pi * day_of_week.to_numpy(dtype=float) / 7.0).astype(
            "float32"
        )
        out["day_of_week_cos_7"] = np.cos(2.0 * np.pi * day_of_week.to_numpy(dtype=float) / 7.0).astype(
            "float32"
        )

    default_sessions: dict[str, tuple[int, int]] = {
        "asia": (0, 8),
        "europe": (7, 16),
        "us": (13, 21),
    }
    raw_sessions = dict(default_sessions)
    if sessions is not None:
        for name, bounds in dict(sessions).items():
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                raise ValueError("sessions entries must be [start_hour, end_hour] pairs.")
            raw_sessions[str(name)] = (int(bounds[0]), int(bounds[1]))

    session_flags: dict[str, pd.Series] = {}
    for session_name, (start_hour, end_hour) in sorted(raw_sessions.items()):
        col_name = f"session_{session_name}"
        session_flags[col_name] = session_mask(hours, out.index, start_hour=start_hour, end_hour=end_hour)
        out[col_name] = session_flags[col_name]

    if {"session_europe", "session_us"}.issubset(session_flags):
        out["session_europe_us_overlap"] = (
            (session_flags["session_europe"] > 0.0) & (session_flags["session_us"] > 0.0)
        ).astype("float32")

    if include_weekend_flag:
        out["is_weekend"] = (day_of_week >= 5).astype("float32")

    return out


__all__ = ["add_session_context_features", "index_in_timezone", "session_mask"]
