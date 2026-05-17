from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AssetSummary(BaseModel):
    symbol: str
    dataset_count: int


class DatasetSummary(BaseModel):
    id: str
    path: str
    relative_path: str
    stage: str
    source: str
    assets: list[str]
    timeframe: str | None = None
    format: str
    columns: list[str]
    metadata_path: str | None = None


class OHLCVCandle(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class CatalogItem(BaseModel):
    name: str
    category: str
    dtype: str
    dataset_id: str | None = None
    metadata: dict[str, Any] | None = None


class TimeValuePoint(BaseModel):
    time: str
    value: Any = None


class NamedSeries(BaseModel):
    series_id: str
    source_type: str
    points: list[TimeValuePoint]


class SeriesResponse(BaseModel):
    series: list[NamedSeries]

