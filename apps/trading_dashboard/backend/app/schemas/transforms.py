from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.market import NamedSeries


ParameterKind = Literal["string", "integer", "number", "boolean", "list", "object", "any"]
BuilderSourceType = Literal["feature", "signal", "target"]


class ParameterDefinition(BaseModel):
    name: str
    kind: ParameterKind = "any"
    required: bool = False
    default_value: Any = None
    annotation: str | None = None
    options: list[Any] | None = None
    description: str | None = None


class BuilderDefinition(BaseModel):
    name: str
    source_type: BuilderSourceType
    import_path: str | None = None
    parameters: list[ParameterDefinition] = Field(default_factory=list)
    docstring: str | None = None


class TransformStepConfig(BaseModel):
    step: str
    params: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, str] | None = None
    enabled: bool = True


class TransformSeriesRequest(BaseModel):
    asset: str | None = None
    timeframe: str | None = None
    source: str | None = None
    dataset_id: str | None = None
    start: str | None = None
    end: str | None = None
    limit: int | None = Field(default=None, ge=1)
    features: list[TransformStepConfig] = Field(default_factory=list)
    signals: list[TransformStepConfig] = Field(default_factory=list)
    targets: list[TransformStepConfig] = Field(default_factory=list)


class TransformStepResult(BaseModel):
    source_type: BuilderSourceType
    step: str
    output_columns: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransformSeriesResponse(BaseModel):
    series: list[NamedSeries] = Field(default_factory=list)
    steps: list[TransformStepResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
