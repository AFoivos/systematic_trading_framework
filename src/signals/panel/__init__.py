"""Panel-aware signal components."""

from .registry import PANEL_SIGNAL_KINDS, PANEL_SIGNAL_REGISTRY, get_panel_signal_fn

__all__ = ["PANEL_SIGNAL_KINDS", "PANEL_SIGNAL_REGISTRY", "get_panel_signal_fn"]
