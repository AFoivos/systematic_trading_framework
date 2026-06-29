from __future__ import annotations

from fastapi import APIRouter, Query

from app.api._errors import raise_http_error
from app.schemas.market import DatasetSummary, OHLCVCandle
from app.services.data_loader import DataLoader


router = APIRouter()


@router.get("/datasets", response_model=list[DatasetSummary])
def get_datasets() -> list[dict]:
    loader = DataLoader()
    return [dataset.to_api(loader.paths.project_root) for dataset in loader.discover_datasets()]


@router.get("/ohlcv", response_model=list[OHLCVCandle])
def get_ohlcv(
    asset: str | None = None,
    timeframe: str | None = None,
    source: str | None = "processed",
    dataset_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> list[dict]:
    try:
        candles = DataLoader().load_ohlcv(
            asset=asset,
            timeframe=timeframe,
            source=source,
            dataset_id=dataset_id,
            start=start,
            end=end,
            limit=limit,
        )
        return candles
    except Exception as exc:
        raise_http_error(exc)
        return []
