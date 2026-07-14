"""Panel-aware feature components for native-index multi-asset research."""

from .context import align_latest_context, build_panel_context, compute_context_age
from .registry import PANEL_FEATURE_KINDS, PANEL_FEATURE_REGISTRY, get_panel_feature_fn

__all__ = [
    "PANEL_FEATURE_KINDS",
    "PANEL_FEATURE_REGISTRY",
    "align_latest_context",
    "build_panel_context",
    "compute_context_age",
    "get_panel_feature_fn",
]
