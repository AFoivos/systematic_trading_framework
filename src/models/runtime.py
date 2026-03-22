from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable, Sequence

import os
import subprocess
import sys

import pandas as pd

from src.models.lightgbm_baseline import default_feature_columns


@lru_cache(maxsize=1)
def probe_lightgbm_runtime() -> tuple[bool, str | None]:
    code = """
import numpy as np
from lightgbm import LGBMClassifier
X = np.random.randn(32, 4).astype("float32")
y = (np.random.rand(32) > 0.5).astype("int32")
model = LGBMClassifier(
    n_estimators=4,
    learning_rate=0.1,
    num_leaves=15,
    n_jobs=1,
    random_state=7,
)
model.fit(X, y)
print("ok")
"""
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode == 0:
        return True, None
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = stderr or stdout or f"child process exited with code {proc.returncode}"
    return False, detail


@lru_cache(maxsize=1)
def probe_xgboost_runtime() -> tuple[bool, str | None]:
    """
    Probe whether the local Python/XGBoost runtime can complete a tiny fit safely.

    Some sandboxed or partially provisioned environments import xgboost successfully but abort
    during the first OpenMP-backed fit. We isolate the probe in a child process so the caller can
    degrade gracefully instead of taking down the parent experiment process.
    """
    code = """
import numpy as np
from xgboost import XGBClassifier
X = np.random.randn(32, 4).astype("float32")
y = (np.random.rand(32) > 0.5).astype("int32")
model = XGBClassifier(
    n_estimators=2,
    max_depth=2,
    learning_rate=0.1,
    tree_method="hist",
    objective="binary:logistic",
    eval_metric="logloss",
    n_jobs=1,
    seed=7,
)
model.fit(X, y)
print("ok")
"""
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode == 0:
        return True, None
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = stderr or stdout or f"child process exited with code {proc.returncode}"
    return False, detail


def ensure_lightgbm_runtime_available() -> None:
    available, detail = probe_lightgbm_runtime()
    if available:
        return
    raise RuntimeError(
        "LightGBM runtime is unavailable in the current environment. "
        f"Probe failure: {detail}"
    )


def ensure_xgboost_runtime_available() -> None:
    available, detail = probe_xgboost_runtime()
    if available:
        return
    raise RuntimeError(
        "XGBoost runtime is unavailable in the current environment. "
        f"Probe failure: {detail}"
    )


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
    if estimator_family == "xgboost":
        model_params.setdefault("seed", seed)
        if deterministic:
            model_params.setdefault("subsample", model_params.get("subsample", 1.0))
            model_params.setdefault("colsample_bytree", model_params.get("colsample_bytree", 1.0))

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


__all__ = [
    "ensure_lightgbm_runtime_available",
    "ensure_xgboost_runtime_available",
    "infer_feature_columns",
    "probe_lightgbm_runtime",
    "probe_xgboost_runtime",
    "resolve_runtime_for_model",
]
