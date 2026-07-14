from __future__ import annotations

from collections.abc import Callable, Mapping

import pandas as pd

from src.utils.registry import build_registry, get_registered_component, registry_names

from .global_session_relay_laggard import global_session_relay_laggard_signal

PanelSignalFn = Callable[..., dict[str, pd.DataFrame]]
PANEL_SIGNAL_REGISTRY: Mapping[str, PanelSignalFn] = build_registry(
    "panel signal", (("global_session_relay_laggard", global_session_relay_laggard_signal),)
)
PANEL_SIGNAL_KINDS = registry_names(PANEL_SIGNAL_REGISTRY)


def get_panel_signal_fn(name: str) -> PanelSignalFn:
    return get_registered_component(PANEL_SIGNAL_REGISTRY, name, category="panel signal")


__all__ = ["PANEL_SIGNAL_KINDS", "PANEL_SIGNAL_REGISTRY", "PanelSignalFn", "get_panel_signal_fn"]
