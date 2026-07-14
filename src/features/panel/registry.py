from __future__ import annotations

from collections.abc import Callable, Mapping

import pandas as pd

from src.utils.registry import build_registry, get_registered_component, registry_names

from .global_session_relay import global_session_relay_features

PanelFeatureFn = Callable[..., dict[str, pd.DataFrame]]

PANEL_FEATURE_REGISTRY: Mapping[str, PanelFeatureFn] = build_registry(
    "panel feature",
    (("global_session_relay", global_session_relay_features),),
)
PANEL_FEATURE_KINDS = registry_names(PANEL_FEATURE_REGISTRY)


def get_panel_feature_fn(name: str) -> PanelFeatureFn:
    return get_registered_component(PANEL_FEATURE_REGISTRY, name, category="panel feature")


__all__ = ["PANEL_FEATURE_KINDS", "PANEL_FEATURE_REGISTRY", "PanelFeatureFn", "get_panel_feature_fn"]
