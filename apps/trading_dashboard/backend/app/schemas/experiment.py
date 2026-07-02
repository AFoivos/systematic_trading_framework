from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExperimentSummary(BaseModel):
    run_id: str
    name: str
    run_type: str = "experiment"
    path: str
    created_at_utc: str | None = None
    asset: str | None = None
    timeframe: str | None = None
    config_hash_sha256: str | None = None
    processed_dataset_id: str | None = None
    processed_dataset_path: str | None = None
    has_trades: bool
    has_equity: bool
    metrics: dict[str, Any]


class ExperimentDetail(BaseModel):
    run_id: str
    name: str
    run_type: str = "experiment"
    path: str
    metadata: dict[str, Any]
    config: dict[str, Any]
    metrics: dict[str, Any]
    artifacts: list[dict[str, Any]]
    available_predictions: list[str]
    available_trades: list[str]
    available_equity: str | None = None
    processed_dataset_id: str | None = None
    processed_dataset_path: str | None = None


class TradeRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entry_time: str | None = None
    exit_time: str | None = None
    side: str
    entry_price: float | None = None
    exit_price: float | None = None
    pnl: float | None = None
    return_value: float | None = Field(default=None, alias="return")
    size: float | None = None
    exit_reason: str | None = None
