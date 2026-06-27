from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .config import ServerConfig
from .repository import list_directory, read_file
from .security import read_text_limited, resolve_repo_path, to_repo_relative


SCRIPT_CONFIRMATION = "RUN_APPROVED_REPOSITORY_SCRIPT"


def read_config(config: ServerConfig, path: str) -> dict[str, Any]:
    payload = read_file(config, path)
    suffix = Path(path).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        parsed = yaml.safe_load(payload["text"])
    elif suffix == ".json":
        parsed = json.loads(payload["text"])
    elif suffix == ".toml":
        parsed = None
    else:
        parsed = None
    return {"path": payload["path"], "parsed": parsed, "raw": payload["text"], "truncated": payload["truncated"]}


def read_log(config: ServerConfig, path: str, tail_lines: int = 200) -> dict[str, Any]:
    payload = read_file(config, path, max_bytes=config.max_read_bytes)
    lines = payload["text"].splitlines()
    selected = lines[-max(1, min(tail_lines, 5_000)) :]
    return {"path": payload["path"], "tail_lines": len(selected), "text": "\n".join(selected), "truncated": payload["truncated"]}


def list_experiment_runs(config: ServerConfig, root: str = "logs", max_runs: int = 100) -> dict[str, Any]:
    logs_root = resolve_repo_path(config.repo_root, root)
    if not logs_root.exists():
        return {"root": root, "runs": []}
    if not logs_root.is_dir():
        raise NotADirectoryError(root)
    runs: list[dict[str, Any]] = []
    for manifest in sorted(logs_root.rglob("artifact_manifest.json"), key=lambda item: item.as_posix()):
        if len(runs) >= max_runs:
            break
        run_dir = manifest.parent
        summary = run_dir / "summary.json"
        metadata = run_dir / "run_metadata.json"
        runs.append(
            {
                "run_id": to_repo_relative(config.repo_root, run_dir),
                "manifest": to_repo_relative(config.repo_root, manifest),
                "has_summary": summary.exists(),
                "has_metadata": metadata.exists(),
                "modified_time": run_dir.stat().st_mtime,
            }
        )
    return {"root": root, "runs": runs, "truncated": len(runs) >= max_runs}


def read_experiment_result(config: ServerConfig, run_id: str, artifact: str = "summary.json", max_rows: int = 200) -> dict[str, Any]:
    run_dir = resolve_repo_path(config.repo_root, run_id)
    if not run_dir.is_dir():
        raise NotADirectoryError(run_id)
    artifact_path = resolve_repo_path(config.repo_root, f"{to_repo_relative(config.repo_root, run_dir)}/{artifact}")
    if not artifact_path.is_file():
        return list_directory(config, to_repo_relative(config.repo_root, run_dir))

    suffix = artifact_path.suffix.lower()
    if suffix == ".json":
        text, truncated = read_text_limited(artifact_path, config.max_read_bytes)
        return {"path": to_repo_relative(config.repo_root, artifact_path), "data": json.loads(text), "truncated": truncated}
    if suffix == ".csv":
        rows = []
        with artifact_path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            for index, row in enumerate(reader):
                if index >= max_rows:
                    break
                rows.append(row)
        return {"path": to_repo_relative(config.repo_root, artifact_path), "rows": rows, "truncated": len(rows) >= max_rows}
    return read_file(config, to_repo_relative(config.repo_root, artifact_path))


def read_optuna_database(config: ServerConfig, path: str, max_trials: int = 100) -> dict[str, Any]:
    db_path = resolve_repo_path(config.repo_root, path)
    if not db_path.is_file():
        raise FileNotFoundError(path)
    limit = max(1, min(max_trials, 1_000))
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = [row["name"] for row in conn.execute("select name from sqlite_master where type='table' order by name")]
        payload: dict[str, Any] = {"path": to_repo_relative(config.repo_root, db_path), "tables": tables}
        if "studies" in tables:
            payload["studies"] = [dict(row) for row in conn.execute("select * from studies order by study_id")]
        if "trials" in tables:
            payload["trials"] = [dict(row) for row in conn.execute("select * from trials order by trial_id limit ?", (limit,))]
        return payload
    finally:
        conn.close()


def execute_approved_python_script(config: ServerConfig, script: str, args: list[str] | None = None, confirmation: str | None = None, timeout_seconds: int | None = None) -> dict[str, Any]:
    if confirmation != SCRIPT_CONFIRMATION:
        raise PermissionError(f"Script execution requires confirmation='{SCRIPT_CONFIRMATION}'")
    if script not in config.approved_python_scripts:
        raise PermissionError(f"Script is not allowlisted: {script}")
    script_path = resolve_repo_path(config.repo_root, script)
    if not script_path.is_file() or script_path.suffix != ".py":
        raise FileNotFoundError(script)
    safe_args = [str(arg) for arg in (args or [])]
    proc = subprocess.run(
        ["python", to_repo_relative(config.repo_root, script_path), *safe_args],
        cwd=config.repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=min(timeout_seconds or config.script_timeout_seconds, config.script_timeout_seconds),
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-config.max_read_bytes :],
        "stderr": proc.stderr[-config.max_read_bytes :],
    }
