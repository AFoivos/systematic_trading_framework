from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.utils.paths import PROJECT_ROOT

_KEY_PACKAGES = (
    "numpy",
    "pandas",
    "scikit-learn",
    "lightgbm",
    "pyyaml",
    "yfinance",
    "requests",
)


def _normalize_path_string(value: str, project_root: Path) -> str:
    candidate = Path(value)
    if not candidate.is_absolute():
        return value
    try:
        rel = candidate.resolve().relative_to(project_root.resolve())
    except Exception:
        return value
    return f"$PROJECT_ROOT/{rel.as_posix()}"


def _normalize_for_hash(value: Any, project_root: Path) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k in sorted(value.keys(), key=lambda x: str(x)):
            if str(k) == "config_path":
                continue
            out[str(k)] = _normalize_for_hash(value[k], project_root)
        return out
    if isinstance(value, list):
        return [_normalize_for_hash(v, project_root) for v in value]
    if isinstance(value, tuple):
        return [_normalize_for_hash(v, project_root) for v in value]
    if isinstance(value, set):
        return sorted(_normalize_for_hash(v, project_root) for v in value)
    if isinstance(value, Path):
        return _normalize_path_string(str(value), project_root)
    if isinstance(value, str):
        return _normalize_path_string(value, project_root)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return str(value)


def canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)


def compute_config_hash(cfg: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> tuple[str, dict[str, Any]]:
    normalized = _normalize_for_hash(deepcopy(dict(cfg)), project_root)
    canonical = canonical_json_dumps(normalized)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest, normalized


def compute_dataframe_fingerprint(df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if df.columns.duplicated().any():
        raise ValueError("DataFrame fingerprinting requires unique column names.")

    canonical = df.copy()
    canonical = canonical.sort_index()
    canonical = canonical.reindex(sorted(canonical.columns), axis=1)

    if isinstance(canonical.index, pd.DatetimeIndex):
        idx = canonical.index
        if idx.tz is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        canonical.index = idx

    row_hashes = pd.util.hash_pandas_object(canonical, index=True, categorize=False)
    digest = hashlib.sha256(row_hashes.to_numpy(dtype="uint64", copy=False).tobytes()).hexdigest()

    if isinstance(canonical.index, pd.DatetimeIndex) and len(canonical.index) > 0:
        idx_start = canonical.index[0].isoformat()
        idx_end = canonical.index[-1].isoformat()
    else:
        idx_start = str(canonical.index[0]) if len(canonical.index) > 0 else None
        idx_end = str(canonical.index[-1]) if len(canonical.index) > 0 else None

    return {
        "sha256": digest,
        "rows": int(len(canonical)),
        "columns": int(len(canonical.columns)),
        "column_names": list(canonical.columns),
        "dtypes": {col: str(dtype) for col, dtype in canonical.dtypes.items()},
        "index_type": type(canonical.index).__name__,
        "index_name": canonical.index.name,
        "index_start": idx_start,
        "index_end": idx_end,
        "is_index_monotonic": bool(canonical.index.is_monotonic_increasing),
    }


def _safe_git(args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def collect_git_metadata() -> dict[str, Any]:
    commit = _safe_git(["rev-parse", "HEAD"])
    branch = _safe_git(["rev-parse", "--abbrev-ref", "HEAD"])
    status = _safe_git(["status", "--porcelain"])
    return {
        "commit": commit,
        "branch": branch,
        "is_dirty": bool(status) if status is not None else None,
    }


def collect_environment_metadata() -> dict[str, Any]:
    package_versions: dict[str, str | None] = {}
    for pkg in _KEY_PACKAGES:
        try:
            package_versions[pkg] = version(pkg)
        except PackageNotFoundError:
            package_versions[pkg] = None

    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "package_versions": package_versions,
    }


def build_run_metadata(
    *,
    config_path: str | Path,
    runtime_applied: Mapping[str, Any],
    config_hash_sha256: str,
    config_hash_input: Mapping[str, Any],
    data_fingerprint: Mapping[str, Any],
    data_context: Mapping[str, Any],
    model_meta: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "cwd": str(Path.cwd()),
        "config_path": str(config_path),
        "config_hash_sha256": config_hash_sha256,
        "config_hash_input": dict(config_hash_input),
        "runtime": dict(runtime_applied),
        "data": {
            "context": dict(data_context),
            "fingerprint": dict(data_fingerprint),
        },
        "model_meta": dict(model_meta),
        "git": collect_git_metadata(),
        "environment": collect_environment_metadata(),
    }


def file_sha256(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_artifact_manifest(artifacts: Mapping[str, str | Path]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for key in sorted(artifacts):
        p = Path(artifacts[key])
        if not p.exists() or not p.is_file():
            continue
        files[key] = {
            "path": str(p),
            "bytes": int(p.stat().st_size),
            "sha256": file_sha256(p),
        }

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }


__all__ = [
    "canonical_json_dumps",
    "compute_config_hash",
    "compute_dataframe_fingerprint",
    "collect_git_metadata",
    "collect_environment_metadata",
    "build_run_metadata",
    "file_sha256",
    "build_artifact_manifest",
]
