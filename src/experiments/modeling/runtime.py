from __future__ import annotations

from typing import Any, Iterable, Sequence

import pandas as pd

from src.models.lightgbm_baseline import default_feature_columns


def resolve_runtime_for_model(
    model_cfg: dict[str, Any],
    model_params: dict[str, Any],
    *,
    estimator_family: str,
) -> dict[str, Any]:
    """
    Resolve reproducibility- and threading-related runtime settings for a model family.
    """
    runtime_cfg = dict(model_cfg.get("runtime", {}) or {})

    seed = runtime_cfg.get("seed", model_params.get("random_state", 7))
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("model.runtime.seed must be an integer >= 0.")

    deterministic = runtime_cfg.get("deterministic", True)
    if not isinstance(deterministic, bool):
        raise ValueError("model.runtime.deterministic must be a boolean.")

    repro_mode = runtime_cfg.get("repro_mode", "strict")
    if repro_mode not in {"strict", "relaxed"}:
        raise ValueError("model.runtime.repro_mode must be 'strict' or 'relaxed'.")

    threads = runtime_cfg.get("threads")
    if threads is not None and (not isinstance(threads, int) or threads <= 0):
        raise ValueError("model.runtime.threads must be null or a positive integer.")
    if repro_mode == "strict" and threads is None:
        threads = 1

    model_params.setdefault("random_state", seed)
    if estimator_family == "lightgbm":
        model_params.setdefault("seed", seed)
        if deterministic:
            model_params.setdefault("deterministic", True)
            model_params.setdefault("force_col_wise", True)
            model_params.setdefault("feature_fraction_seed", seed)
            model_params.setdefault("bagging_seed", seed)
            model_params.setdefault("data_random_seed", seed)

    if threads is not None:
        model_params.setdefault("n_jobs", threads)

    return {
        "seed": seed,
        "deterministic": deterministic,
        "threads": model_params.get("n_jobs", threads),
        "repro_mode": repro_mode,
    }


def infer_feature_columns(
    df: pd.DataFrame,
    explicit_cols: Sequence[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> list[str]:
    """
    Infer usable numeric feature columns when the config does not pin them explicitly.
    """
    if explicit_cols:
        missing = [c for c in explicit_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Missing feature columns: {missing}")
        return list(explicit_cols)

    inferred = default_feature_columns(df)
    if inferred:
        return inferred

    exclude_set = set(exclude or [])
    exclude_set.update({"open", "high", "low", "close", "adj_close", "volume"})

    numeric_cols = df.select_dtypes(include=["number"]).columns
    features: list[str] = []
    for col in numeric_cols:
        if col in exclude_set:
            continue
        if col.startswith(("signal_", "pred_", "target_")):
            continue
        features.append(col)
    return features


__all__ = ["infer_feature_columns", "resolve_runtime_for_model"]
