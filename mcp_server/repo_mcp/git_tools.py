from __future__ import annotations

import subprocess
from typing import Any

from .config import ServerConfig
from .security import resolve_repo_path, to_repo_relative


def _git(config: ServerConfig, args: list[str], timeout_seconds: int = 30) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=config.repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def git_status(config: ServerConfig) -> dict[str, Any]:
    return {"status": _git(config, ["status", "--short", "--branch"])}


def git_diff(config: ServerConfig, path: str | None = None, max_bytes: int | None = None) -> dict[str, Any]:
    args = ["diff", "--"]
    target = None
    if path:
        target_path = resolve_repo_path(config.repo_root, path)
        target = to_repo_relative(config.repo_root, target_path)
        args.append(target)
    text = _git(config, args)
    limit = min(max_bytes or config.max_read_bytes, config.max_read_bytes)
    truncated = len(text.encode("utf-8")) > limit
    return {"path": target, "diff": text[:limit], "truncated": truncated}


def git_log(config: ServerConfig, max_count: int = 20) -> dict[str, Any]:
    count = max(1, min(max_count, 100))
    text = _git(config, ["log", f"--max-count={count}", "--date=iso-strict", "--pretty=format:%H%x09%ad%x09%an%x09%s"])
    commits = []
    for line in text.splitlines():
        sha, date, author, subject = (line.split("\t", 3) + ["", "", "", ""])[:4]
        commits.append({"sha": sha, "date": date, "author": author, "subject": subject})
    return {"commits": commits}


def git_current_branch(config: ServerConfig) -> dict[str, str]:
    return {"branch": _git(config, ["branch", "--show-current"]).strip()}
