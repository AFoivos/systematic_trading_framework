from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import pandas as pd

from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path
from src.utils.run_metadata import compute_dataframe_fingerprint, file_sha256


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
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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

    frame = pd.read_csv(data_path)
    asset_frames = long_frame_to_asset_frames(frame)

    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f)

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
