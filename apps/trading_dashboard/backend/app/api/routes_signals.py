from __future__ import annotations

from fastapi import APIRouter

from app.api._errors import raise_http_error
from app.schemas.market import NamedSeries, SeriesResponse
from app.services.data_loader import DataLoader, parse_csv_list


router = APIRouter()


@router.get("/signals/catalog")
def get_signal_catalog(
    asset: str | None = None,
    timeframe: str | None = None,
    source: str | None = None,
    dataset_id: str | None = None,
):
    try:
        return DataLoader().catalog(
            source_type="signal",
            asset=asset,
            timeframe=timeframe,
            source=source,
            dataset_id=dataset_id,
        )
    except Exception as exc:
        raise_http_error(exc)
        return []


@router.get("/signals/series", response_model=SeriesResponse)
def get_signal_series(
    asset: str,
    signals: str,
    timeframe: str | None = None,
    source: str | None = None,
    dataset_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> SeriesResponse:
    try:
        columns = parse_csv_list(signals)
        series = DataLoader().load_series(
            asset=asset,
            columns=columns,
            timeframe=timeframe,
            source=source,
            dataset_id=dataset_id,
            start=start,
            end=end,
        )
        return SeriesResponse(
            series=[
                NamedSeries(series_id=name, source_type="signal", points=points)
                for name, points in series.items()
            ]
        )
    except Exception as exc:
        raise_http_error(exc)
        return SeriesResponse(series=[])

