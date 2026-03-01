from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.utils.paths import PROJECT_ROOT
from src.utils.run_metadata import compute_dataframe_fingerprint


def _resolve_path(path: str | Path) -> Path:
    """
    Handle path inside the data ingestion and storage layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    p = Path(path)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    return p


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
    if not dataset_id:
        raise ValueError("dataset_id must be a non-empty string.")
    return _resolve_path(root_dir) / stage / dataset_id


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

    long_frame = asset_frames_to_long_frame(asset_frames)
    long_frame.to_csv(data_path, index=False)

    metadata = build_dataset_snapshot_metadata(
        asset_frames,
        dataset_id=dataset_id,
        stage=stage,
        context=context,
    )
    metadata["data_path"] = str(data_path)

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)

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
    metadata.setdefault("data_path", str(data_path))
    return asset_frames, metadata


__all__ = [
    "asset_frames_to_long_frame",
    "long_frame_to_asset_frames",
    "build_dataset_snapshot_metadata",
    "save_dataset_snapshot",
    "load_dataset_snapshot",
]
