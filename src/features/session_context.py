from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd


def index_in_timezone(index: pd.Index, timezone: str) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(str(timezone))


def session_mask(hours: pd.Index, index: pd.Index, *, start_hour: int, end_hour: int) -> pd.Series:
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
