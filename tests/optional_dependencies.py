from __future__ import annotations

from functools import lru_cache
import os
import subprocess
import sys
from collections.abc import Iterable


def _subprocess_env(*, limit_native_threads: bool) -> dict[str, str] | None:
    if not limit_native_threads:
        return None
    env = dict(os.environ)
    env.update(
        {
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "KMP_DUPLICATE_LIB_OK": "TRUE",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": env.get("TMPDIR", env.get("TEMP", ".")),
        }
    )
    return env


@lru_cache(maxsize=None)
def optional_dependency_stack_available(
    *modules: str,
    preimport: tuple[str, ...] = ("numpy", "pandas"),
    limit_native_threads: bool = False,
) -> bool:
    """
    Probe an optional native stack in the same import order used by model tests.

    Importing torch by itself can succeed on Windows while importing it after
    NumPy/Pandas fails to initialize ``c10.dll``.  The basic tensor operation
    also verifies that import success is not merely a partially initialized
    module.
    """
    ordered_modules = tuple(dict.fromkeys((*preimport, *modules)))
    lines = ["import importlib"]
    lines.extend(f"importlib.import_module({module!r})" for module in ordered_modules)
    if "torch" in ordered_modules:
        lines.extend(
            [
                "_torch = importlib.import_module('torch')",
                "assert float(_torch.ones(1).sum().item()) == 1.0",
            ]
        )
    proc = subprocess.run(
        [sys.executable, "-c", "\n".join(lines)],
        capture_output=True,
        text=True,
        check=False,
        env=_subprocess_env(limit_native_threads=limit_native_threads),
    )
    return proc.returncode == 0


def is_optional_dependency_runtime_failure(
    proc: subprocess.CompletedProcess[str],
    *,
    modules: Iterable[str],
) -> bool:
    """
    Return true only for recognizable optional dependency/runtime failures.

    Callers should still fail on ordinary tracebacks so working dependency
    environments do not hide regressions in production code or assertions.
    """
    module_names = tuple(str(module).lower() for module in modules)
    output = f"{proc.stderr or ''}\n{proc.stdout or ''}".lower()

    for module in module_names:
        normalized = module.replace("-", "_")
        missing_markers = (
            f"no module named '{module}'",
            f'no module named "{module}"',
            f"no module named '{normalized}'",
            f'no module named "{normalized}"',
        )
        if any(marker in output for marker in missing_markers):
            return True

    if "torch" not in module_names:
        return False

    torch_runtime_markers = (
        "winerror 1114",
        "c10.dll",
        "torch\\lib\\",
        "torch/lib/",
        "dll load failed while importing",
        "fatal python error: aborted",
        "windows fatal exception: access violation",
        "omp: error",
        "libiomp",
    )
    return any(marker in output for marker in torch_runtime_markers)
