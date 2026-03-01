from __future__ import annotations

import os
import random
from typing import Any, Mapping

import numpy as np

_ALLOWED_REPRO_MODES = {"strict", "relaxed"}
_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


class RuntimeConfigError(ValueError):
    """Raised for invalid runtime/reproducibility configuration."""


def normalize_runtime_config(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Normalize runtime config into a canonical representation used throughout the infrastructure
    layer. This avoids repeated formatting logic and makes hashing or comparisons stable.
    """
    runtime = dict(runtime_cfg or {})
    runtime.setdefault("seed", 7)
    runtime.setdefault("deterministic", True)
    runtime.setdefault("threads", None)
    runtime.setdefault("repro_mode", "strict")
    runtime.setdefault("seed_torch", False)
    return runtime


def validate_runtime_config(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Validate runtime config before downstream logic depends on it. The function raises early
    when assumptions of the infrastructure layer are violated, which keeps failures
    deterministic and easier to diagnose.
    """
    runtime = normalize_runtime_config(runtime_cfg)

    seed = runtime.get("seed")
    if not isinstance(seed, int) or seed < 0:
        raise RuntimeConfigError("runtime.seed must be an integer >= 0.")

    deterministic = runtime.get("deterministic")
    if not isinstance(deterministic, bool):
        raise RuntimeConfigError("runtime.deterministic must be a boolean.")

    threads = runtime.get("threads")
    if threads is not None and (not isinstance(threads, int) or threads <= 0):
        raise RuntimeConfigError("runtime.threads must be null or a positive integer.")

    repro_mode = runtime.get("repro_mode")
    if repro_mode not in _ALLOWED_REPRO_MODES:
        raise RuntimeConfigError(f"runtime.repro_mode must be one of {_ALLOWED_REPRO_MODES}.")

    seed_torch = runtime.get("seed_torch", False)
    if not isinstance(seed_torch, bool):
        raise RuntimeConfigError("runtime.seed_torch must be a boolean.")

    if repro_mode == "strict" and runtime.get("threads") is None:
        runtime["threads"] = 1

    return runtime


def apply_runtime_reproducibility(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Apply runtime reproducibility to the provided inputs in a controlled and reusable way. The
    helper makes a single transformation step explicit inside the broader infrastructure
    workflow.
    """
    runtime = validate_runtime_config(runtime_cfg)

    seed = int(runtime["seed"])
    deterministic = bool(runtime["deterministic"])
    threads = runtime.get("threads")
    repro_mode = runtime["repro_mode"]
    seed_torch = bool(runtime.get("seed_torch", False))

    pyhash_before = os.getenv("PYTHONHASHSEED")
    os.environ["PYTHONHASHSEED"] = str(seed)
    pyhash_after = os.getenv("PYTHONHASHSEED")

    random.seed(seed)
    np.random.seed(seed)

    thread_env: dict[str, str] = {}
    if threads is not None:
        for var_name in _THREAD_ENV_VARS:
            os.environ[var_name] = str(threads)
            thread_env[var_name] = os.environ[var_name]

    torch_info: dict[str, Any] = {"available": False}
    if deterministic and seed_torch:
        try:
            import torch
        except Exception as exc:  # pragma: no cover - environment dependent
            torch_info = {
                "available": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        else:
            torch.manual_seed(seed)
            cuda_available = bool(torch.cuda.is_available())
            if cuda_available:
                torch.cuda.manual_seed_all(seed)

            det_algorithms_enabled = False
            try:
                torch.use_deterministic_algorithms(True)
                det_algorithms_enabled = True
            except Exception:
                det_algorithms_enabled = False

            if hasattr(torch.backends, "cudnn"):
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False

            torch_info = {
                "available": True,
                "cuda_available": cuda_available,
                "deterministic_algorithms": det_algorithms_enabled,
            }

    return {
        "seed": seed,
        "deterministic": deterministic,
        "threads": threads,
        "repro_mode": repro_mode,
        "seed_torch": seed_torch,
        "pythonhashseed_before": pyhash_before,
        "pythonhashseed_after": pyhash_after,
        "pythonhashseed_matches_seed": pyhash_after == str(seed),
        "thread_env": thread_env,
        "torch": torch_info,
    }


__all__ = [
    "RuntimeConfigError",
    "normalize_runtime_config",
    "validate_runtime_config",
    "apply_runtime_reproducibility",
]
