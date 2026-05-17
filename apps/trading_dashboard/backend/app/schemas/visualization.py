from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RenderType = Literal[
    "candlestick",
    "line",
    "area",
    "histogram",
    "marker",
    "background_band",
    "horizontal_level",
    "trade_marker",
    "prediction_line",
    "probability_band",
]

ChartTarget = Literal["main_price_chart", "lower_panel", "candle_marker", "background"]


class SeriesStyle(BaseModel):
    color: str | None = None
    lineWidth: int | None = None
    opacity: float | None = None
    priceScaleId: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class VisualizationConfig(BaseModel):
    series_id: str
    source_type: str
    display_name: str
    chart_target: ChartTarget
    panel_id: str | None = None
    render_type: RenderType
    y_axis: Literal["left", "right"] = "right"
    visible: bool = True
    style: SeriesStyle = Field(default_factory=SeriesStyle)

