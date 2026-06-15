from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ExecutionStatus(BaseModel):
    log_dir: str
    health: dict[str, Any]
    lock: dict[str, Any]
    command: str | None = None
    account: dict[str, Any] | None = None
    latest_by_asset: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]
    files: list[dict[str, Any]]


class ExecutionRecordList(BaseModel):
    log_dir: str
    records: list[dict[str, Any]]


class ExecutionFeatureSnapshot(BaseModel):
    log_dir: str
    asset: str
    mt5_symbol: str | None = None
    bar_time: str | None = None
    timeframe: str | None = None
    row_count: int
    columns: list[str]
    numeric_columns: list[str]
    feature_columns: list[str]
    market_columns: list[str]
    records: list[dict[str, Any]]


__all__ = ["ExecutionFeatureSnapshot", "ExecutionRecordList", "ExecutionStatus"]
