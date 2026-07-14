from __future__ import annotations

from typing import Any

import pandas as pd

from src.features.panel.registry import get_panel_feature_fn


def apply_panel_feature_steps(
    asset_frames: dict[str, pd.DataFrame], *, panel_feature_steps: list[dict[str, Any]]
) -> dict[str, pd.DataFrame]:
    """Run optional panel feature transformations without changing native asset indexes."""
    out = dict(asset_frames)
    for idx, step in enumerate(panel_feature_steps):
        if not isinstance(step, dict) or "step" not in step:
            raise ValueError("Each panel_features step must include a 'step' key.")
        if step.get("enabled", True) is False:
            continue
        previous_indexes = {asset: frame.index.copy() for asset, frame in out.items()}
        transformed = get_panel_feature_fn(str(step["step"]))(out, **dict(step.get("params", {}) or {}))
        if set(transformed) != set(out):
            raise ValueError(f"panel_features[{idx}] must return the same asset keys it received.")
        for asset, frame in transformed.items():
            if not frame.index.equals(previous_indexes[asset]):
                raise ValueError(f"panel_features[{idx}] changed native index for asset '{asset}'.")
        out = {asset: transformed[asset] for asset in sorted(transformed)}
    return out


__all__ = ["apply_panel_feature_steps"]
