from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from src.utils.registry import build_registry, get_registered_component, registry_names

from .canonical_pipeline import run_canonical_pipeline

PipelineFn = Callable[[str | Path], Any]


_PIPELINE_COMPONENTS: tuple[tuple[str, PipelineFn], ...] = (
    ("canonical_experiment", run_canonical_pipeline),
)


PIPELINE_REGISTRY: Mapping[str, PipelineFn] = build_registry("pipeline", _PIPELINE_COMPONENTS)
PIPELINE_KINDS = registry_names(PIPELINE_REGISTRY)


def get_pipeline_fn(name: str) -> PipelineFn:
    return get_registered_component(PIPELINE_REGISTRY, name, category="pipeline")


__all__ = [
    "PIPELINE_KINDS",
    "PIPELINE_REGISTRY",
    "PipelineFn",
    "get_pipeline_fn",
]
