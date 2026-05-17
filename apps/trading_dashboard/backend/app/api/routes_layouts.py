from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.api._errors import raise_http_error
from app.schemas.layout import DashboardLayout, LayoutSummary
from app.services.layout_store import LayoutStore


router = APIRouter()


@router.post("/layouts", response_model=DashboardLayout)
def save_layout(layout: DashboardLayout) -> dict:
    try:
        payload = layout.model_dump()
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        return LayoutStore().save_layout(payload)
    except Exception as exc:
        raise_http_error(exc)
        return {}


@router.get("/layouts", response_model=list[LayoutSummary])
def list_layouts() -> list[dict]:
    try:
        return LayoutStore().list_layouts()
    except Exception as exc:
        raise_http_error(exc)
        return []


@router.get("/layouts/{layout_id}", response_model=DashboardLayout)
def load_layout(layout_id: str) -> dict:
    try:
        return LayoutStore().load_layout(layout_id)
    except Exception as exc:
        raise_http_error(exc)
        return {}
