from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.utils.column_selectors import resolve_single_column_selector


def require_columns(df: pd.DataFrame, cols: list[str], *, owner: str) -> None:
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for {owner}: {missing}")


def resolve_configured_column(
    df: pd.DataFrame,
    cfg: Mapping[str, Any],
    *,
    col_key: str,
    selector_key: str,
    field_prefix: str,
) -> str:
    raw_col = cfg.get(col_key)
    raw_selector = cfg.get(selector_key)
    has_col = raw_col is not None
    has_selector = raw_selector is not None
    if has_col == has_selector:
        raise ValueError(f"{field_prefix} must define exactly one of {col_key} or {selector_key}.")
    if has_col:
        if not isinstance(raw_col, str) or not raw_col.strip():
            raise ValueError(f"{field_prefix}.{col_key} must be a non-empty string.")
        if raw_col not in df.columns:
            raise KeyError(f"{field_prefix}.{col_key} '{raw_col}' not found in DataFrame.")
        return raw_col
    return resolve_single_column_selector(
        [str(col) for col in df.columns],
        raw_selector,
        field=f"{field_prefix}.{selector_key}",
    )


def output_column(value: Any, *, default: str, field: str = "output_col") -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string when provided.")
    return value


def positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return int(value)


def non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be an integer >= 0.")
    return int(value)


def probability(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be in [0, 1].")
    out = float(value)
    if not 0.0 <= out <= 1.0:
        raise ValueError(f"{field} must be in [0, 1].")
    return out


__all__ = [
    "non_negative_int",
    "output_column",
    "positive_int",
    "probability",
    "require_columns",
    "resolve_configured_column",
]
