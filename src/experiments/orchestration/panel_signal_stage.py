from __future__ import annotations

from typing import Any

import pandas as pd

from src.signals.panel.registry import get_panel_signal_fn


def apply_panel_signal_steps(
    asset_frames: dict[str, pd.DataFrame], *, panel_signal_steps: list[dict[str, Any]]
) -> dict[str, pd.DataFrame]:
    """Run optional panel signal transformations while preserving each native index."""
    out = dict(asset_frames)
    for idx, step in enumerate(panel_signal_steps):
        if not isinstance(step, dict) or "step" not in step:
            raise ValueError("Each panel_signals step must include a 'step' key.")
        if step.get("enabled", True) is False:
            continue
        indexes = {asset: frame.index.copy() for asset, frame in out.items()}
        transformed = get_panel_signal_fn(str(step["step"]))(out, **dict(step.get("params", {}) or {}))
        if set(transformed) != set(out):
            raise ValueError(f"panel_signals[{idx}] must return the same asset keys it received.")
        for asset, frame in transformed.items():
            if not frame.index.equals(indexes[asset]):
                raise ValueError(f"panel_signals[{idx}] changed native index for asset '{asset}'.")
        out = {asset: transformed[asset] for asset in sorted(transformed)}
    return out


__all__ = ["apply_panel_signal_steps"]
