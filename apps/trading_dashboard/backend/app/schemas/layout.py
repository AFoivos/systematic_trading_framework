from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.visualization import VisualizationConfig


class DashboardLayout(BaseModel):
    layout_id: str | None = None
    name: str
    description: str | None = None
    selection: dict[str, Any] = Field(default_factory=dict)
    series: list[VisualizationConfig] = Field(default_factory=list)
    panels: dict[str, Any] = Field(default_factory=dict)
    transformations: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None


class LayoutSummary(BaseModel):
    layout_id: str
    name: str
    path: str
    updated_at: str | None = None
