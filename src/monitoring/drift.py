from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd


def population_stability_index(
    reference: pd.Series,
    current: pd.Series,
    *,
    n_bins: int = 10,
    eps: float = 1e-6,
) -> float:
    """
    Handle population stability index inside the monitoring layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    ref = pd.Series(reference, copy=False).dropna().astype(float)
    cur = pd.Series(current, copy=False).dropna().astype(float)
    if ref.empty or cur.empty:
        return 0.0

    quantiles = np.linspace(0.0, 1.0, int(n_bins) + 1)
    edges = np.unique(np.quantile(ref.to_numpy(dtype=float), quantiles))
    if len(edges) < 2:
        return 0.0

    bins = edges.astype(float)
    bins[0] = -np.inf
    bins[-1] = np.inf

    ref_counts, _ = np.histogram(ref.to_numpy(dtype=float), bins=bins)
    cur_counts, _ = np.histogram(cur.to_numpy(dtype=float), bins=bins)

    ref_pct = np.clip(ref_counts / max(ref_counts.sum(), 1), eps, None)
    cur_pct = np.clip(cur_counts / max(cur_counts.sum(), 1), eps, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def compute_feature_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    *,
    feature_cols: Iterable[str] | None = None,
    psi_threshold: float = 0.2,
    n_bins: int = 10,
) -> dict[str, Any]:
    """
    Compute feature drift for the monitoring layer. The helper keeps the calculation isolated so
    the calling pipeline can reuse the same logic consistently across experiments.
    """
    if not isinstance(reference_df, pd.DataFrame):
        raise TypeError("reference_df must be a pandas DataFrame.")
    if not isinstance(current_df, pd.DataFrame):
        raise TypeError("current_df must be a pandas DataFrame.")

    if feature_cols is None:
        cols = [
            str(col)
            for col in reference_df.select_dtypes(include=["number"]).columns
            if col in current_df.columns
        ]
    else:
        cols = [str(col) for col in feature_cols if col in reference_df.columns and col in current_df.columns]

    report: dict[str, dict[str, Any]] = {}
    drifted_features = 0

    for col in cols:
        ref = reference_df[col]
        cur = current_df[col]

        ref_non_null = ref.dropna().astype(float)
        cur_non_null = cur.dropna().astype(float)
        ref_std = float(ref_non_null.std(ddof=1)) if len(ref_non_null) >= 2 else 0.0
        cur_std = float(cur_non_null.std(ddof=1)) if len(cur_non_null) >= 2 else 0.0
        mean_shift = float(cur_non_null.mean() - ref_non_null.mean()) if not ref_non_null.empty and not cur_non_null.empty else 0.0
        normalized_mean_shift = float(abs(mean_shift) / ref_std) if ref_std > 0 else 0.0
        psi = population_stability_index(ref_non_null, cur_non_null, n_bins=n_bins)
        is_drifted = bool(psi >= psi_threshold)
        if is_drifted:
            drifted_features += 1

        report[col] = {
            "reference_rows": int(len(ref)),
            "current_rows": int(len(cur)),
            "reference_missing_rate": float(ref.isna().mean()),
            "current_missing_rate": float(cur.isna().mean()),
            "reference_mean": float(ref_non_null.mean()) if not ref_non_null.empty else None,
            "current_mean": float(cur_non_null.mean()) if not cur_non_null.empty else None,
            "reference_std": ref_std,
            "current_std": cur_std,
            "abs_mean_shift_in_ref_std": normalized_mean_shift,
            "psi": psi,
            "is_drifted": is_drifted,
        }

    return {
        "feature_count": int(len(cols)),
        "drifted_feature_count": int(drifted_features),
        "psi_threshold": float(psi_threshold),
        "n_bins": int(n_bins),
        "per_feature": report,
    }


__all__ = [
    "population_stability_index",
    "compute_feature_drift",
]
