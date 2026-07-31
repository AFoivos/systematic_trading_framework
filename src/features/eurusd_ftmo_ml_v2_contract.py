from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.eurusd_ftmo_ml_v2_contract import FEATURE_COLUMNS


def feature_schema_hash(columns: tuple[str, ...] | list[str] = FEATURE_COLUMNS) -> str:
    return hashlib.sha256("\n".join(columns).encode("utf-8")).hexdigest()


def validate_feature_contract(columns: Any) -> list[str]:
    resolved = list(columns)
    expected = list(FEATURE_COLUMNS)
    if len(resolved) != 151:
        raise ValueError(f"Feature contract requires 151 columns, found {len(resolved)}.")
    duplicates = sorted({name for name in resolved if resolved.count(name) > 1})
    if duplicates:
        raise ValueError(f"Feature contract contains duplicates: {duplicates}")
    if resolved != expected:
        missing = [name for name in expected if name not in resolved]
        extra = [name for name in resolved if name not in expected]
        reordered = not missing and not extra
        raise ValueError(
            f"Feature contract mismatch (missing={missing}, extra={extra}, reordered={reordered})."
        )
    return resolved


def validate_model_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Model matrix must be a pandas DataFrame.")
    validate_feature_contract(frame.columns)
    return frame


def verify_reference_feature_contract(bundle_path: str | Path, dictionary_path: str | Path) -> list[str]:
    """Fail closed unless bundle, dictionary, and embedded order all agree."""
    import joblib

    bundle = joblib.load(Path(bundle_path))
    if not isinstance(bundle, dict) or "feature_columns" not in bundle:
        raise ValueError("Reference bundle must contain feature_columns.")
    bundle_columns = validate_feature_contract(bundle["feature_columns"])
    dictionary = pd.read_csv(Path(dictionary_path))
    candidates = [name for name in ("feature", "feature_name", "name", "column") if name in dictionary.columns]
    if len(candidates) != 1:
        raise ValueError("Feature dictionary must expose exactly one recognized feature-name column.")
    dictionary_columns = list(dictionary[candidates[0]].astype(str))
    validate_feature_contract(dictionary_columns)
    if dictionary_columns != bundle_columns:
        raise ValueError("Reference bundle and feature dictionary orders differ.")
    return bundle_columns


__all__ = [
    "feature_schema_hash",
    "validate_feature_contract",
    "validate_model_matrix",
    "verify_reference_feature_contract",
]
