from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


def compute_context_age(
    target_index: pd.DatetimeIndex,
    context_timestamps: pd.Series | pd.DatetimeIndex,
    *,
    interval_minutes: int = 30,
) -> pd.DataFrame:
    """Return explicit elapsed-time age metadata for as-of aligned context."""
    if isinstance(interval_minutes, bool) or int(interval_minutes) <= 0:
        raise ValueError("interval_minutes must be a positive integer.")
    target = pd.DatetimeIndex(pd.to_datetime(target_index, errors="raise"))
    source = pd.to_datetime(pd.Series(context_timestamps).reset_index(drop=True), errors="coerce")
    if len(source) != len(target):
        raise ValueError("context_timestamps must have the same length as target_index.")
    elapsed = pd.Series(target, index=range(len(target))) - source
    age_minutes = elapsed.dt.total_seconds() / 60.0
    invalid = source.isna() | (age_minutes < 0.0)
    age_minutes = age_minutes.mask(invalid)
    result = pd.DataFrame(index=target)
    result["context_timestamp"] = source.to_numpy()
    result["context_age_minutes"] = age_minutes.to_numpy(dtype=float)
    result["context_age_bars"] = (age_minutes / float(interval_minutes)).to_numpy(dtype=float)
    return result


def align_latest_context(
    source: pd.DataFrame,
    target_index: pd.DatetimeIndex,
    *,
    value_columns: Sequence[str],
    max_age_bars: float,
    interval_minutes: int = 30,
) -> pd.DataFrame:
    """Causally align the most recent source row to a native target index.

    No source values are forward-filled into an OHLC frame.  The returned values are context
    values with timestamp and elapsed-time age metadata, and stale context is explicitly
    unavailable.  ``merge_asof`` gives the required ``source_timestamp <= target_timestamp``
    contract.
    """
    if max_age_bars <= 0 or not np.isfinite(float(max_age_bars)):
        raise ValueError("max_age_bars must be finite and > 0.")
    if not isinstance(source.index, pd.DatetimeIndex):
        raise TypeError("source must have a DatetimeIndex.")
    missing = [col for col in value_columns if col not in source.columns]
    if missing:
        raise KeyError(f"Context source is missing columns: {missing}")
    target = pd.DatetimeIndex(pd.to_datetime(target_index, errors="raise")).sort_values()
    if target.has_duplicates:
        raise ValueError("target_index must not contain duplicate timestamps.")
    source_frame = source.loc[:, list(value_columns)].copy().sort_index()
    if source_frame.index.has_duplicates:
        source_frame = source_frame.loc[~source_frame.index.duplicated(keep="last")]
    source_frame = source_frame.reset_index(names="context_timestamp")
    target_frame = pd.DataFrame({"target_timestamp": target})
    aligned = pd.merge_asof(
        target_frame,
        source_frame,
        left_on="target_timestamp",
        right_on="context_timestamp",
        direction="backward",
        allow_exact_matches=True,
    )
    metadata = compute_context_age(
        target,
        aligned["context_timestamp"],
        interval_minutes=interval_minutes,
    )
    metadata["context_is_fresh"] = (
        metadata["context_age_bars"].notna()
        & (metadata["context_age_bars"] <= float(max_age_bars))
    )
    result = aligned.loc[:, list(value_columns)].copy()
    result.index = target
    result = result.join(metadata)
    stale = ~result["context_is_fresh"].astype(bool)
    result.loc[stale, list(value_columns)] = np.nan
    return result


def build_panel_context(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    source_asset: str,
    target_assets: Sequence[str],
    value_columns: Sequence[str],
    max_age_bars: float,
    interval_minutes: int = 30,
) -> dict[str, pd.DataFrame]:
    """Build independent as-of context frames for target assets without changing their index."""
    if source_asset not in asset_frames:
        raise KeyError(f"Unknown source asset '{source_asset}'.")
    out: dict[str, pd.DataFrame] = {}
    source = asset_frames[source_asset]
    for asset in target_assets:
        if asset not in asset_frames:
            raise KeyError(f"Unknown target asset '{asset}'.")
        out[str(asset)] = align_latest_context(
            source,
            asset_frames[asset].index,
            value_columns=value_columns,
            max_age_bars=max_age_bars,
            interval_minutes=interval_minutes,
        )
    return out


__all__ = ["align_latest_context", "build_panel_context", "compute_context_age"]
