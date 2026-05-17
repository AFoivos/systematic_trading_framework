from __future__ import annotations

from fastapi import APIRouter

from app.api._errors import raise_http_error
from app.schemas.transforms import BuilderDefinition, TransformSeriesRequest, TransformSeriesResponse
from app.services.transform_catalog import feature_builders, run_transform_series, signal_builders, target_builders


router = APIRouter()


@router.get("/features/builders", response_model=list[BuilderDefinition])
def get_feature_builders() -> list[BuilderDefinition]:
    try:
        return feature_builders()
    except Exception as exc:
        raise_http_error(exc)
        return []


@router.get("/signals/builders", response_model=list[BuilderDefinition])
def get_signal_builders() -> list[BuilderDefinition]:
    try:
        return signal_builders()
    except Exception as exc:
        raise_http_error(exc)
        return []


@router.get("/targets/builders", response_model=list[BuilderDefinition])
def get_target_builders() -> list[BuilderDefinition]:
    try:
        return target_builders()
    except Exception as exc:
        raise_http_error(exc)
        return []


@router.post("/transform/series", response_model=TransformSeriesResponse)
def post_transform_series(payload: TransformSeriesRequest) -> TransformSeriesResponse:
    try:
        return run_transform_series(payload)
    except Exception as exc:
        raise_http_error(exc)
        return TransformSeriesResponse()
