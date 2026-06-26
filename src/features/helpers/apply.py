from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from .registry import NORMALIZATION_HELPERS, TRANSFORM_HELPERS, HelperFn


def _iter_helper_params(raw_block: Any, *, field: str) -> list[dict[str, Any]]:
    if raw_block in (None, False):
        return []
    if not isinstance(raw_block, Mapping):
        raise TypeError(f"{field} must be a mapping when provided.")
    if raw_block.get("enabled", True) is False:
        return []

    defaults = dict(raw_block.get("params", {}) or {})
    raw_items = raw_block.get("items")
    if raw_items is None:
        direct = {
            str(key): value
            for key, value in raw_block.items()
            if key not in {"enabled", "params", "items"}
        }
        params = {**direct, **defaults}
        return [params]

    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes, bytearray)):
        raise TypeError(f"{field}.items must be a list of mappings.")
    items: list[dict[str, Any]] = []
    for idx, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, Mapping):
            raise TypeError(f"{field}.items[{idx}] must be a mapping.")
        items.append({**defaults, **dict(raw_item)})
    return items


def _apply_section(
    df: pd.DataFrame,
    section: Mapping[str, Any] | None,
    *,
    registry: Mapping[str, HelperFn],
    owner: str,
) -> pd.DataFrame:
    if not section:
        return df
    if not isinstance(section, Mapping):
        raise TypeError(f"{owner} must be a mapping when provided.")

    out = df
    for helper_name, raw_block in section.items():
        if helper_name not in registry:
            allowed = ", ".join(sorted(registry))
            raise ValueError(f"Unsupported {owner} helper '{helper_name}'. Allowed: {allowed}.")
        helper = registry[str(helper_name)]
        for params in _iter_helper_params(raw_block, field=f"{owner}.{helper_name}"):
            out = helper(out, **params)
    return out


def apply_feature_helpers(
    df: pd.DataFrame,
    *,
    transforms: Mapping[str, Any] | None = None,
    normalizations: Mapping[str, Any] | None = None,
    owner: str = "features[]",
) -> pd.DataFrame:
    """
    Apply the ``apply_feature_helpers`` feature helper transformation.
    
    This feature helper uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        transforms:
          apply_feature_helpers:
            params:
              transforms: null
              normalizations: null
              owner: features[]
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    transforms:
        Configuration parameter accepted by this feature helper. Default: ``null``.
    normalizations:
        Configuration parameter accepted by this feature helper. Default: ``null``.
    owner:
        Error-message owner used while applying helper blocks. Default: ``features[]``.
    """
    out = _apply_section(df, transforms, registry=TRANSFORM_HELPERS, owner=f"{owner}.transforms")
    out = _apply_section(out, normalizations, registry=NORMALIZATION_HELPERS, owner=f"{owner}.normalizations")
    return out


__all__ = ["apply_feature_helpers"]
