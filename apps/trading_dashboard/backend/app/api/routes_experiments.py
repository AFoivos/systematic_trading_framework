from __future__ import annotations

from fastapi import APIRouter

from app.api._errors import raise_http_error
from app.schemas.experiment import ExperimentDetail, ExperimentSummary
from app.services.experiment_loader import ExperimentLoader


router = APIRouter()


@router.get("/experiments", response_model=list[ExperimentSummary])
def get_experiments() -> list[dict]:
    try:
        return ExperimentLoader().list_runs()
    except Exception as exc:
        raise_http_error(exc)
        return []


@router.get("/experiments/{run_id}", response_model=ExperimentDetail)
def get_experiment(run_id: str) -> dict:
    try:
        return ExperimentLoader().load_run(run_id)
    except Exception as exc:
        raise_http_error(exc)
        return {}

