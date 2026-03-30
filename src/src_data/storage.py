from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import pandas as pd

from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path
from src.utils.run_metadata import compute_dataframe_fingerprint, file_sha256

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

_REQUIRED_OHLC_COLUMNS = ("open", "high", "low", "close")


def _resolve_path(path: str | Path) -> Path:
    """
    Handle path inside the data ingestion and storage layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    p = Path(path)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    return enforce_safe_absolute_path(p)


def _resolve_snapshot_dir(
    *,
    root_dir: str | Path,
    stage: str,
    dataset_id: str,
) -> Path:
    """
    Handle snapshot dir inside the data ingestion and storage layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ValueError("dataset_id must be a non-empty string.")

    stage_root = (_resolve_path(root_dir) / stage).resolve()
    snapshot_dir = (stage_root / dataset_id).resolve()
    try:
        snapshot_dir.relative_to(stage_root)
    except ValueError as exc:
        raise ValueError(
            f"Unsafe dataset_id '{dataset_id}': escapes snapshot root."
        ) from exc
    return snapshot_dir


@contextmanager
def _snapshot_lock(snapshot_dir: Path):
    """
    Serialize writers targeting the same snapshot directory so concurrent saves cannot
    clobber each other's temporary files.
    """
    lock_path = snapshot_dir / ".snapshot.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        if fcntl is None:
            yield
            return
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _filter_asset_frames(
    asset_frames: dict[str, pd.DataFrame],
    *,
    requested_assets: list[str] | None,
    start: str | None,
    end: str | None,
) -> dict[str, pd.DataFrame]:
    out = dict(asset_frames)
    if requested_assets:
        missing_assets = [asset for asset in requested_assets if asset not in out]
        if missing_assets:
            raise ValueError(f"Dataset snapshot is missing requested assets: {missing_assets}.")
        out = {str(asset): out[str(asset)] for asset in requested_assets}

    start_ts = _coerce_time_boundary(start)
    end_ts = _coerce_time_boundary(end)
    filtered: dict[str, pd.DataFrame] = {}
    for asset, asset_frame in sorted(out.items()):
        cur = asset_frame
        if start_ts is not None:
            cur = cur.loc[cur.index >= start_ts]
        if end_ts is not None:
            cur = cur.loc[cur.index < end_ts]
        if cur.empty:
            raise ValueError(
                f"Dataset snapshot has no rows left for asset '{asset}' "
                f"after applying start={start!r}, end={end!r}."
            )
        filtered[str(asset)] = cur
    return filtered


def asset_frames_to_long_frame(asset_frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Handle asset frames to long frame inside the data ingestion and storage layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    if not asset_frames:
        raise ValueError("asset_frames cannot be empty.")

    rows: list[pd.DataFrame] = []
    for asset in sorted(asset_frames):
        df = asset_frames[asset]
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"asset_frames[{asset!r}] must be a pandas DataFrame.")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError(f"asset_frames[{asset!r}] must have a DatetimeIndex.")

        out = df.sort_index().copy()
        out.insert(0, "asset", str(asset))
        out.insert(0, "timestamp", pd.to_datetime(out.index))
        rows.append(out.reset_index(drop=True))

    frame = pd.concat(rows, axis=0, ignore_index=True, sort=False)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame = frame.sort_values(["timestamp", "asset"], kind="mergesort").reset_index(drop=True)
    return frame


def long_frame_to_asset_frames(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Handle long frame to asset frames inside the data ingestion and storage layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    if "timestamp" not in frame.columns or "asset" not in frame.columns:
        raise ValueError("Stored dataset frame must include 'timestamp' and 'asset' columns.")

    out: dict[str, pd.DataFrame] = {}
    data = frame.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="raise")

    for asset, group in data.groupby("asset", sort=True):
        df = group.drop(columns=["asset"]).set_index("timestamp").sort_index()
        out[str(asset)] = df
    return out


def _infer_epoch_unit(values: pd.Series) -> str:
    """
    Infer integer epoch units conservatively so external CSV timestamps can be normalized
    without relying on implicit pandas heuristics.
    """
    numeric = pd.to_numeric(values, errors="raise")
    if numeric.empty:
        raise ValueError("timestamp column cannot be empty.")
    max_abs = float(numeric.abs().max())
    if max_abs >= 1e17:
        return "ns"
    if max_abs >= 1e14:
        return "us"
    if max_abs >= 1e11:
        return "ms"
    return "s"


def _coerce_external_timestamp_index(values: pd.Series) -> pd.DatetimeIndex:
    """
    Normalize external timestamps explicitly to UTC-naive datetimes. Numeric epochs are
    interpreted as UTC; naive string timestamps are also treated as UTC to avoid local-time
    ambiguity in ingestion.
    """
    series = pd.Series(values)
    if series.empty:
        raise ValueError("timestamp column cannot be empty.")

    if pd.api.types.is_numeric_dtype(series):
        unit = _infer_epoch_unit(series)
        idx = pd.to_datetime(pd.to_numeric(series, errors="raise"), unit=unit, utc=True, errors="raise")
    else:
        stripped = series.astype(str).str.strip()
        if stripped.str.fullmatch(r"[+-]?\d+").all():
            numeric = pd.to_numeric(stripped, errors="raise")
            unit = _infer_epoch_unit(numeric)
            idx = pd.to_datetime(numeric, unit=unit, utc=True, errors="raise")
        else:
            idx = pd.to_datetime(series, errors="raise", utc=True)

    return pd.DatetimeIndex(idx).tz_convert("UTC").tz_localize(None)


def _coerce_time_boundary(value: str | None) -> pd.Timestamp | None:
    """
    Normalize config-style start/end boundaries to UTC-naive timestamps so external CSV loads
    behave like live providers when slicing by data window.
    """
    if value is None:
        return None
    ts = pd.Timestamp(pd.to_datetime(value, errors="raise", utc=True))
    return ts.tz_convert("UTC").tz_localize(None)


def _normalize_external_csv_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Lower-case CSV column names for explicit external load paths so canonical schema matching
    remains case-insensitive without altering persisted snapshot formats.
    """
    out = frame.copy()
    out.columns = [str(col).strip().lower() for col in out.columns]
    return out


def _coerce_external_single_asset_frame(
    frame: pd.DataFrame,
    *,
    asset: str,
) -> pd.DataFrame:
    """
    Convert a raw single-asset OHLCV CSV into the project's canonical per-asset frame.
    """
    out = frame.copy()
    out.index = _coerce_external_timestamp_index(out["timestamp"])
    out = out.drop(columns=["timestamp"])

    for col in _REQUIRED_OHLC_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="raise")
    if "volume" in out.columns:
        out["volume"] = pd.to_numeric(out["volume"], errors="raise")
    else:
        out["volume"] = 0.0

    # Preserve any extra columns such as adj_close while keeping OHLCV first.
    preferred = ["open", "high", "low", "close", "volume"]
    trailing = [col for col in out.columns if col not in preferred]
    out = out[preferred + trailing]
    out.index.name = "timestamp"
    return out


def _load_external_csv_asset_frames(
    path: Path,
    *,
    requested_assets: list[str] | None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """
    Support explicit `load_path` CSV files that are not framework snapshots. Accepted shapes:
    1. `timestamp,open,high,low,close[,volume,...]` for single-asset data
    2. `timestamp,asset,open,high,low,close[,volume,...]` for long multi-asset data
    """
    frame = _normalize_external_csv_columns(pd.read_csv(path))
    if "timestamp" not in frame.columns:
        raise ValueError(
            f"External CSV '{path}' must include a 'timestamp' column."
        )
    missing_ohlc = [col for col in _REQUIRED_OHLC_COLUMNS if col not in frame.columns]
    if missing_ohlc:
        raise ValueError(
            f"External CSV '{path}' is missing OHLC columns: {missing_ohlc}."
        )

    assets = list(requested_assets or [])
    if "asset" in frame.columns:
        frame["asset"] = frame["asset"].astype(str)
        if assets:
            missing_assets = [asset for asset in assets if asset not in set(frame["asset"])]
            if missing_assets:
                raise ValueError(
                    f"External CSV '{path}' is missing requested assets: {missing_assets}."
                )
            frame = frame.loc[frame["asset"].isin(assets)].copy()
        asset_frames = long_frame_to_asset_frames(
            frame.assign(timestamp=_coerce_external_timestamp_index(frame["timestamp"]))
        )
        for asset, asset_frame in list(asset_frames.items()):
            asset_frames[asset] = _coerce_external_single_asset_frame(
                asset_frame.reset_index(),
                asset=asset,
            )
        format_name = "external_long_ohlcv_csv"
    else:
        if len(assets) != 1:
            raise ValueError(
                "Single-asset external CSV load_path requires exactly one configured symbol."
            )
        asset = str(assets[0])
        asset_frames = {asset: _coerce_external_single_asset_frame(frame, asset=asset)}
        format_name = "external_single_asset_ohlcv_csv"

    start_ts = _coerce_time_boundary(start)
    end_ts = _coerce_time_boundary(end)
    if start_ts is not None or end_ts is not None:
        filtered_frames: dict[str, pd.DataFrame] = {}
        for asset, asset_frame in sorted(asset_frames.items()):
            out = asset_frame
            if start_ts is not None:
                out = out.loc[out.index >= start_ts]
            if end_ts is not None:
                out = out.loc[out.index < end_ts]
            if out.empty:
                raise ValueError(
                    f"External CSV '{path}' has no rows left for asset '{asset}' "
                    f"after applying start={start!r}, end={end!r}."
                )
            filtered_frames[asset] = out
        asset_frames = filtered_frames

    metadata = {
        "data_path": str(path),
        "format": format_name,
        "explicit_load_path": True,
        "requires_pit_hardening": True,
        "assets": sorted(asset_frames),
        "requested_start": start,
        "requested_end": end,
    }
    return asset_frames, metadata


def build_dataset_snapshot_metadata(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    dataset_id: str,
    stage: str,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build dataset snapshot metadata as an explicit intermediate object used by the data
    ingestion and storage pipeline. Keeping this assembly step separate makes the orchestration
    code easier to reason about and test.
    """
    long_frame = asset_frames_to_long_frame(asset_frames)
    fingerprint = compute_dataframe_fingerprint(long_frame)

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "stage": stage,
        "assets": sorted(str(asset) for asset in asset_frames),
        "rows_by_asset": {
            str(asset): int(len(df))
            for asset, df in sorted(asset_frames.items(), key=lambda kv: str(kv[0]))
        },
        "columns": sorted(str(col) for col in long_frame.columns),
        "fingerprint": fingerprint,
        "context": dict(context or {}),
    }


def save_dataset_snapshot(
    asset_frames: Mapping[str, pd.DataFrame],
    *,
    dataset_id: str,
    stage: str,
    root_dir: str | Path,
    context: Mapping[str, Any] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Save dataset snapshot for the data ingestion and storage layer together with the metadata
    needed to reproduce or inspect the generated artifact later. The function isolates
    persistence concerns from the core analytical logic.
    """
    snapshot_dir = _resolve_snapshot_dir(root_dir=root_dir, stage=stage, dataset_id=dataset_id)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    data_path = snapshot_dir / "dataset.csv"
    metadata_path = snapshot_dir / "metadata.json"
    with _snapshot_lock(snapshot_dir):
        if not overwrite and (data_path.exists() or metadata_path.exists()):
            raise FileExistsError(
                f"Dataset snapshot already exists for dataset_id='{dataset_id}' at '{snapshot_dir}'. "
                "Use a versioned dataset_id or pass overwrite=True."
            )

        data_tmp_path = snapshot_dir / f"dataset.{uuid4().hex}.csv.tmp"
        metadata_tmp_path = snapshot_dir / f"metadata.{uuid4().hex}.json.tmp"

        long_frame = asset_frames_to_long_frame(asset_frames)
        long_frame.to_csv(data_tmp_path, index=False)
        data_tmp_path.replace(data_path)

        metadata = build_dataset_snapshot_metadata(
            asset_frames,
            dataset_id=dataset_id,
            stage=stage,
            context=context,
        )
        metadata["data_path"] = str(data_path)
        metadata["data_sha256"] = file_sha256(data_path)

        with metadata_tmp_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)

        metadata_tmp_path.replace(metadata_path)

    return {
        "dataset_id": dataset_id,
        "stage": stage,
        "snapshot_dir": str(snapshot_dir),
        "data_path": str(data_path),
        "metadata_path": str(metadata_path),
        "fingerprint": metadata["fingerprint"],
    }


def load_dataset_snapshot(
    *,
    stage: str,
    root_dir: str | Path | None = None,
    dataset_id: str | None = None,
    load_path: str | Path | None = None,
    requested_assets: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """
    Load dataset snapshot for the data ingestion and storage layer and normalize it into the
    shape expected by the rest of the project. The helper centralizes path or provider handling
    so callers do not duplicate I/O logic.
    """
    if load_path is not None:
        p = _resolve_path(load_path)
        if p.is_dir():
            data_path = p / "dataset.csv"
            metadata_path = p / "metadata.json"
        else:
            data_path = p
            metadata_path = p.with_name("metadata.json")
    else:
        if root_dir is None or dataset_id is None:
            raise ValueError("root_dir and dataset_id are required when load_path is not provided.")
        snapshot_dir = _resolve_snapshot_dir(root_dir=root_dir, stage=stage, dataset_id=dataset_id)
        data_path = snapshot_dir / "dataset.csv"
        metadata_path = snapshot_dir / "metadata.json"

    if not data_path.exists():
        raise FileNotFoundError(f"Dataset snapshot not found: {data_path}")

    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
        frame = pd.read_csv(data_path)
        asset_frames = long_frame_to_asset_frames(frame)
    elif load_path is not None and data_path.suffix.lower() == ".csv":
        asset_frames, metadata = _load_external_csv_asset_frames(
            data_path,
            requested_assets=requested_assets,
            start=start,
            end=end,
        )
        metadata.setdefault("verified_fingerprint", False)
        return asset_frames, metadata
    else:
        frame = pd.read_csv(data_path)
        asset_frames = long_frame_to_asset_frames(frame)

    asset_frames = _filter_asset_frames(
        asset_frames,
        requested_assets=requested_assets,
        start=start,
        end=end,
    )

    expected_data_sha256 = metadata.get("data_sha256")
    if expected_data_sha256 is not None:
        actual_data_sha256 = file_sha256(data_path)
        if actual_data_sha256 != expected_data_sha256:
            raise ValueError(
                f"Dataset snapshot checksum mismatch for '{data_path}'."
            )
        metadata["verified_fingerprint"] = True
    else:
        expected_fingerprint = dict(metadata.get("fingerprint", {}) or {})
        if expected_fingerprint:
            actual_fingerprint = compute_dataframe_fingerprint(asset_frames_to_long_frame(asset_frames))
            if actual_fingerprint.get("sha256") != expected_fingerprint.get("sha256"):
                raise ValueError(
                    f"Dataset snapshot fingerprint mismatch for '{data_path}'."
                )
            metadata["verified_fingerprint"] = True

    metadata.setdefault("data_path", str(data_path))
    return asset_frames, metadata


__all__ = [
    "asset_frames_to_long_frame",
    "long_frame_to_asset_frames",
    "build_dataset_snapshot_metadata",
    "save_dataset_snapshot",
    "load_dataset_snapshot",
]
