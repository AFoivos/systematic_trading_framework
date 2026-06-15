from __future__ import annotations

from fastapi import APIRouter

from app.api._errors import raise_http_error
from app.schemas.execution import ExecutionFeatureSnapshot, ExecutionRecordList, ExecutionStatus
from app.services.execution_monitor import ExecutionMonitorService


router = APIRouter()


@router.get("/execution/status", response_model=ExecutionStatus)
def get_execution_status(log_dir: str | None = None) -> dict:
    try:
        return ExecutionMonitorService().status(log_dir=log_dir)
    except Exception as exc:
        raise_http_error(exc)
        return {}


@router.get("/execution/decisions", response_model=ExecutionRecordList)
def get_execution_decisions(
    log_dir: str | None = None,
    asset: str | None = None,
    limit: int = 100,
) -> dict:
    try:
        return ExecutionMonitorService().decisions(log_dir=log_dir, asset=asset, limit=limit)
    except Exception as exc:
        raise_http_error(exc)
        return {"log_dir": "", "records": []}


@router.get("/execution/events", response_model=ExecutionRecordList)
def get_execution_events(log_dir: str | None = None, limit: int = 100) -> dict:
    try:
        return ExecutionMonitorService().events(log_dir=log_dir, limit=limit)
    except Exception as exc:
        raise_http_error(exc)
        return {"log_dir": "", "records": []}


@router.get("/execution/features/{asset}", response_model=ExecutionFeatureSnapshot)
def get_execution_features(asset: str, log_dir: str | None = None) -> dict:
    try:
        return ExecutionMonitorService().feature_snapshot(asset, log_dir=log_dir)
    except Exception as exc:
        raise_http_error(exc)
        return {
            "log_dir": "",
            "asset": asset,
            "row_count": 0,
            "columns": [],
            "numeric_columns": [],
            "feature_columns": [],
            "market_columns": [],
            "records": [],
        }
