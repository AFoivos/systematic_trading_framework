from __future__ import annotations

from typing import Any

import pandas as pd

from src.experiments.registry import get_feature_fn, get_signal_fn


def apply_feature_steps(df: pd.DataFrame, steps: list[dict[str, Any]]) -> pd.DataFrame:
    out = df
    for step in steps:
        if "step" not in step:
            raise ValueError("Each feature step must include a 'step' key.")
        if step.get("enabled", True) is False:
            continue
        name = step["step"]
        params = step.get("params", {}) or {}
        fn = get_feature_fn(name)
        out = fn(out, **params)
    return out


def apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame:
    kind = signals_cfg.get("kind", "none")
    if kind == "none":
        return df
    params = signals_cfg.get("params", {}) or {}
    fn = get_signal_fn(kind)
    out = fn(df, **params)
    if isinstance(out, pd.DataFrame):
        return out
    if isinstance(out, pd.Series):
        frame = df.copy()
        frame[out.name] = out
        return frame
    raise TypeError(f"Signal function for kind='{kind}' returned unsupported type: {type(out)}")


def apply_steps_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    feature_steps: list[dict[str, Any]],
) -> dict[str, pd.DataFrame]:
    return {
        asset: apply_feature_steps(df, feature_steps)
        for asset, df in sorted(asset_frames.items())
    }


def apply_signals_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    signals_cfg: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    return {
        asset: apply_signal_step(df, signals_cfg)
        for asset, df in sorted(asset_frames.items())
    }


__all__ = [
    "apply_feature_steps",
    "apply_signal_step",
    "apply_signals_to_assets",
    "apply_steps_to_assets",
]
