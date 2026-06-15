from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.paths import DashboardPaths, get_paths
from app.services.schema_mapper import (
    DataSchemaError,
    catalog_columns,
    filter_by_date,
    frame_to_candles,
    frame_to_series,
    group_catalog_items,
    infer_asset_from_name,
    infer_timeframe_from_name,
    normalize_market_frame,
    normalize_timeframe,
)


SUPPORTED_DATA_SUFFIXES = {".csv", ".parquet"}


@dataclass(frozen=True)
class DatasetInfo:
    id: str
    path: Path
    stage: str
    source: str
    assets: tuple[str, ...]
    timeframe: str | None
    format: str
    columns: tuple[str, ...]
    metadata_path: Path | None = None

    def to_api(self, project_root: Path) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": str(self.path),
            "relative_path": str(self.path.relative_to(project_root)) if self.path.is_relative_to(project_root) else str(self.path),
            "stage": self.stage,
            "source": self.source,
            "assets": list(self.assets),
            "timeframe": self.timeframe,
            "format": self.format,
            "columns": list(self.columns),
            "metadata_path": str(self.metadata_path) if self.metadata_path else None,
        }


def _safe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _read_columns(path: Path) -> tuple[str, ...]:
    if path.suffix.lower() == ".csv":
        return tuple(str(column) for column in pd.read_csv(path, nrows=0).columns)
    if path.suffix.lower() == ".parquet":
        try:
            return tuple(str(column) for column in pd.read_parquet(path).columns)
        except ImportError as exc:
            raise DataSchemaError("Parquet support requires pyarrow or fastparquet.") from exc
    return ()


def _read_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".parquet":
        try:
            return pd.read_parquet(path)
        except ImportError as exc:
            raise DataSchemaError("Parquet support requires pyarrow or fastparquet.") from exc
    raise DataSchemaError(f"Unsupported dataset format: {path.suffix}")


def _relative_id(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _source_from_data_path(path: Path, data_root: Path) -> str:
    try:
        rel = path.relative_to(data_root)
    except ValueError:
        return "data"
    if not rel.parts:
        return "data"
    stage = rel.parts[0]
    if stage == "processed":
        return "processed"
    if len(rel.parts) > 2:
        return rel.parts[1]
    return stage


def _stage_from_data_path(path: Path, data_root: Path) -> str:
    try:
        rel = path.relative_to(data_root)
    except ValueError:
        return "data"
    return rel.parts[0] if len(rel.parts) > 1 else "data"


def _metadata_path_for_dataset(path: Path) -> Path:
    if path.name in {"dataset.csv", "dataset.parquet"}:
        return path.with_name("metadata.json")
    sidecar_path = path.with_suffix(".metadata.json")
    if sidecar_path.exists():
        return sidecar_path
    snapshot_metadata_path = path.with_name("metadata.json")
    return snapshot_metadata_path if snapshot_metadata_path.exists() else sidecar_path


def _extract_timeframe_from_metadata(metadata: dict[str, Any], fallback_name: str) -> str | None:
    context = dict(metadata.get("context", {}) or {})
    for key in ("interval", "timeframe"):
        if key in context:
            return normalize_timeframe(str(context[key]))
    data_cfg = dict(context.get("data", {}) or {})
    for key in ("interval", "timeframe"):
        if key in data_cfg:
            return normalize_timeframe(str(data_cfg[key]))
    return infer_timeframe_from_name(fallback_name)


class DataLoader:
    def __init__(self, paths: DashboardPaths | None = None) -> None:
        self.paths = paths or get_paths()

    def discover_datasets(self) -> list[DatasetInfo]:
        datasets = self._discover_data_datasets()
        return sorted(datasets, key=lambda item: (item.stage, item.source, item.id))

    def _discover_data_datasets(self) -> list[DatasetInfo]:
        root = self.paths.data_root
        if not root.exists():
            return []
        datasets: list[DatasetInfo] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_DATA_SUFFIXES:
                continue
            metadata_path = _metadata_path_for_dataset(path)
            metadata = _safe_load_json(metadata_path)
            fallback_name = path.parent.name if path.name in {"dataset.csv", "dataset.parquet"} else path.name
            assets = tuple(str(asset).upper() for asset in metadata.get("assets", []) or [])
            if not assets:
                asset = infer_asset_from_name(fallback_name)
                assets = (asset,) if asset else ()
            datasets.append(
                DatasetInfo(
                    id=_relative_id(path, self.paths.project_root),
                    path=path,
                    stage=_stage_from_data_path(path, root),
                    source=_source_from_data_path(path, root),
                    assets=assets,
                    timeframe=_extract_timeframe_from_metadata(metadata, fallback_name),
                    format=path.suffix.lower().lstrip("."),
                    columns=_read_columns(path),
                    metadata_path=metadata_path if metadata_path.exists() else None,
                )
            )
        return datasets

    def list_assets(self) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for dataset in self.discover_datasets():
            for asset in dataset.assets:
                counts[asset] = counts.get(asset, 0) + 1
        return [{"symbol": symbol, "dataset_count": count} for symbol, count in sorted(counts.items())]

    def list_timeframes(self, asset: str) -> list[str]:
        symbol = asset.upper()
        values = {
            dataset.timeframe
            for dataset in self.discover_datasets()
            if dataset.timeframe is not None and (not dataset.assets or symbol in dataset.assets)
        }
        return sorted(values)

    def _resolve_dataset(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        source: str | None = None,
        dataset_id: str | None = None,
    ) -> DatasetInfo:
        datasets = self.discover_datasets()
        if dataset_id:
            matches = [dataset for dataset in datasets if dataset.id == dataset_id]
            if not matches:
                raise FileNotFoundError(f"Unknown dataset_id: {dataset_id}")
            return matches[0]

        symbol = asset.upper() if asset else None
        normalized_tf = normalize_timeframe(timeframe)
        source_query = str(source or "").lower().strip()
        candidates: list[DatasetInfo] = []
        for dataset in datasets:
            if symbol and dataset.assets and symbol not in dataset.assets:
                continue
            if normalized_tf and dataset.timeframe and normalize_timeframe(dataset.timeframe) != normalized_tf:
                continue
            if source_query and source_query not in {"all", "*"}:
                stage_match = dataset.stage.lower() == source_query
                source_match = dataset.source.lower() == source_query
                if not stage_match and not source_match:
                    continue
            candidates.append(dataset)

        if not candidates:
            raise FileNotFoundError(
                f"No dataset found for asset={asset!r}, timeframe={timeframe!r}, source={source!r}."
            )
        return sorted(candidates, key=lambda item: (item.stage != "processed", item.id))[0]

    def _load_frame(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        source: str | None = None,
        dataset_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        require_ohlcv: bool = False,
    ) -> tuple[pd.DataFrame, DatasetInfo]:
        dataset = self._resolve_dataset(asset=asset, timeframe=timeframe, source=source, dataset_id=dataset_id)
        raw = _read_frame(dataset.path)
        frame = normalize_market_frame(raw, require_ohlcv=require_ohlcv)
        effective_asset = asset or (dataset.assets[0] if len(dataset.assets) == 1 else None)
        if effective_asset and "asset" in frame.columns:
            frame = frame.loc[frame["asset"].astype(str).str.upper() == effective_asset.upper()]
        frame = filter_by_date(frame, start=start, end=end)
        if frame.empty:
            raise DataSchemaError(
                f"Dataset {dataset.id!r} has no rows after applying asset/start/end filters."
            )
        return frame, dataset

    def load_frame(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        source: str | None = None,
        dataset_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        require_ohlcv: bool = False,
    ) -> tuple[pd.DataFrame, DatasetInfo]:
        return self._load_frame(
            asset=asset,
            timeframe=timeframe,
            source=source,
            dataset_id=dataset_id,
            start=start,
            end=end,
            require_ohlcv=require_ohlcv,
        )

    def load_ohlcv(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        source: str | None = None,
        dataset_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        frame, _ = self._load_frame(
            asset=asset,
            timeframe=timeframe,
            source=source,
            dataset_id=dataset_id,
            start=start,
            end=end,
            require_ohlcv=True,
        )
        return frame_to_candles(frame)

    def load_series(
        self,
        *,
        asset: str | None = None,
        columns: list[str],
        timeframe: str | None = None,
        source: str | None = None,
        dataset_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        frame, _ = self._load_frame(
            asset=asset,
            timeframe=timeframe,
            source=source,
            dataset_id=dataset_id,
            start=start,
            end=end,
            require_ohlcv=False,
        )
        if limit:
            frame = frame.tail(limit)
        return frame_to_series(frame, columns)

    def catalog(
        self,
        *,
        source_type: str,
        asset: str | None = None,
        timeframe: str | None = None,
        source: str | None = None,
        dataset_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]] | list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if dataset_id or asset:
            frame, dataset = self._load_frame(
                asset=asset,
                timeframe=timeframe,
                source=source,
                dataset_id=dataset_id,
                require_ohlcv=False,
            )
            for item in catalog_columns(frame, source_type=source_type):
                item["dataset_id"] = dataset.id
                items.append(item)
        else:
            for dataset in self.discover_datasets():
                frame = normalize_market_frame(_read_frame(dataset.path), require_ohlcv=False)
                for item in catalog_columns(frame, source_type=source_type):
                    item["dataset_id"] = dataset.id
                    items.append(item)

        deduped = {f"{item['dataset_id']}::{item['name']}": item for item in items}
        values = sorted(deduped.values(), key=lambda item: (str(item.get("category")), str(item.get("name"))))
        if source_type == "feature":
            return group_catalog_items(values)
        return values


def parse_csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
