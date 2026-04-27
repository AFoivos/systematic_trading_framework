from __future__ import annotations

import inspect
from typing import Any

import pandas as pd

from src.experiments.registry import get_feature_fn, get_signal_fn


def _apply_output_mapping(
    df: pd.DataFrame,
    outputs: dict[str, Any] | None,
    *,
    owner: str,
) -> pd.DataFrame:
    if not outputs:
        return df
    if not isinstance(outputs, dict):
        raise TypeError(f"{owner}.outputs must be a mapping when provided.")

    rename_map: dict[str, str] = {}
    for source_col, target_col in outputs.items():
        if not isinstance(source_col, str) or not source_col.strip():
            raise ValueError(f"{owner}.outputs keys must be non-empty strings.")
        if not isinstance(target_col, str) or not target_col.strip():
            raise ValueError(f"{owner}.outputs values must be non-empty strings.")
        if source_col not in df.columns:
            raise KeyError(
                f"{owner}.outputs refers to source column '{source_col}' which was not emitted by the step."
            )
        rename_map[source_col] = target_col

    renamed = df.rename(columns=rename_map)
    if len(set(renamed.columns)) != len(renamed.columns):
        duplicates = renamed.columns[renamed.columns.duplicated()].unique().tolist()
        raise ValueError(
            f"{owner}.outputs resolves to duplicate column names after renaming: {duplicates}."
        )
    return renamed


def _call_feature_fn(
    fn: Any,
    df: pd.DataFrame,
    params: dict[str, Any],
    *,
    asset: str | None,
) -> pd.DataFrame:
    call_params = dict(params)
    if asset is not None and "asset" not in call_params:
        try:
            accepts_asset = "asset" in inspect.signature(fn).parameters
        except (TypeError, ValueError):
            accepts_asset = False
        if accepts_asset:
            call_params["asset"] = asset
    return fn(df, **call_params)


def apply_feature_steps(
    df: pd.DataFrame,
    steps: list[dict[str, Any]],
    *,
    asset: str | None = None,
) -> pd.DataFrame:
    out = df
    for idx, step in enumerate(steps):
        if "step" not in step:
            raise ValueError("Each feature step must include a 'step' key.")
        if step.get("enabled", True) is False:
            continue
        name = step["step"]
        params = step.get("params", {}) or {}
        fn = get_feature_fn(name)
        out = _call_feature_fn(fn, out, params, asset=asset)
        out = _apply_output_mapping(out, step.get("outputs"), owner=f"features[{idx}]")
    return out


def apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame:
    kind = signals_cfg.get("kind", "none")
    if kind == "none":
        return df
    params = signals_cfg.get("params", {}) or {}
    fn = get_signal_fn(kind)
    out = fn(df, **params)
    if isinstance(out, pd.DataFrame):
        return _apply_output_mapping(out, signals_cfg.get("outputs"), owner="signals")
    if isinstance(out, pd.Series):
        frame = df.copy()
        frame[out.name] = out
        return _apply_output_mapping(frame, signals_cfg.get("outputs"), owner="signals")
    raise TypeError(f"Signal function for kind='{kind}' returned unsupported type: {type(out)}")


def apply_steps_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    feature_steps: list[dict[str, Any]],
) -> dict[str, pd.DataFrame]:
    return {
        asset: apply_feature_steps(df, feature_steps, asset=asset)
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
