from __future__ import annotations

from fastapi import APIRouter

from app.api._errors import raise_http_error
from app.schemas.market import AssetSummary
from app.services.data_loader import DataLoader


router = APIRouter()


@router.get("/assets", response_model=list[AssetSummary])
def get_assets() -> list[dict]:
    try:
        return DataLoader().list_assets()
    except Exception as exc:
        raise_http_error(exc)
        return []


@router.get("/timeframes", response_model=list[str])
def get_timeframes(asset: str) -> list[str]:
    try:
        return DataLoader().list_timeframes(asset)
    except Exception as exc:
        raise_http_error(exc)
        return []

