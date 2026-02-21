from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import pandas as pd
from pandas.api.types import is_numeric_dtype


@dataclass(frozen=True)
class DataContract:
    required_columns: tuple[str, ...] = ("open", "high", "low", "close", "volume")
    require_datetime_index: bool = True
    require_unique_index: bool = True
    require_monotonic_index: bool = True


@dataclass(frozen=True)
class TargetContract:
    target_col: str
    horizon: int = 1


def validate_data_contract(
    df: pd.DataFrame,
    contract: DataContract | None = None,
) -> dict[str, int]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    contract = contract or DataContract()
    missing = [c for c in contract.required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Data contract violated: missing required columns: {missing}")

    if contract.require_datetime_index and not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Data contract violated: index must be DatetimeIndex.")

    if contract.require_unique_index and df.index.has_duplicates:
        raise ValueError("Data contract violated: index has duplicate timestamps.")

    if contract.require_monotonic_index and not df.index.is_monotonic_increasing:
        raise ValueError("Data contract violated: index must be monotonic increasing.")

    return {"rows": int(len(df)), "columns": int(len(df.columns))}


def validate_feature_target_contract(
    df: pd.DataFrame,
    *,
    feature_cols: Sequence[str],
    target: TargetContract,
    forbidden_feature_prefixes: Iterable[str] = ("target_", "label", "pred_"),
) -> dict[str, int]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if not feature_cols:
        raise ValueError("Feature contract violated: feature_cols cannot be empty.")
    if not isinstance(target.horizon, int) or target.horizon <= 0:
        raise ValueError("Target contract violated: horizon must be a positive integer.")

    target_col = target.target_col
    if target_col not in df.columns:
        raise KeyError(f"Target contract violated: '{target_col}' column not found.")

    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Feature contract violated: missing feature columns: {missing}")

    overlap = [c for c in feature_cols if c == target_col]
    if overlap:
        raise ValueError("Feature contract violated: target column cannot be used as feature.")

    bad_prefixes: list[str] = []
    forbidden = tuple(forbidden_feature_prefixes)
    for col in feature_cols:
        if col == target_col:
            bad_prefixes.append(col)
            continue
        if col.startswith(forbidden):
            bad_prefixes.append(col)
    if bad_prefixes:
        raise ValueError(
            "Feature contract violated: forbidden feature columns detected: "
            f"{sorted(set(bad_prefixes))}"
        )

    non_numeric = [c for c in feature_cols if not is_numeric_dtype(df[c])]
    if non_numeric:
        raise ValueError(f"Feature contract violated: non-numeric feature columns: {non_numeric}")

    all_nan = [c for c in feature_cols if df[c].dropna().empty]
    if all_nan:
        raise ValueError(f"Feature contract violated: all-NaN feature columns: {all_nan}")

    target_non_null = df[target_col].dropna()
    if target_non_null.empty:
        raise ValueError("Target contract violated: target column has no non-null values.")

    return {
        "n_features": int(len(feature_cols)),
        "target_non_null_rows": int(len(target_non_null)),
    }


__all__ = [
    "DataContract",
    "TargetContract",
    "validate_data_contract",
    "validate_feature_target_contract",
]

