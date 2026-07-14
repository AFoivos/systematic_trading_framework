from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo_mcp.config import ServerConfig
from repo_mcp.git_tools import (
    get_code_review_bundle,
    get_repo_snapshot,
    git_diff,
    list_changed_paths,
    mcp_diagnostics,
    mcp_health,
    read_changed_files,
)
from repo_mcp.repository import read_files, search_source, stat_files


def _config(root: Path) -> ServerConfig:
    return ServerConfig(
        repo_root=root,
        host="127.0.0.1",
        port=8765,
        max_read_bytes=1_000_000,
        max_search_results=200,
        max_tree_entries=5_000,
        script_timeout_seconds=30,
        approved_python_scripts=(),
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _git_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "mcp-tests@example.invalid")
    _git(root, "config", "user.name", "MCP Tests")
    _write(root / "src" / "alpha.py", "VALUE = 1\n")
    _write(root / "src" / "delete_me.py", "DELETE = True\n")
    _write(root / "src" / "rename_me.py", "RENAME = True\n")
    _write(root / "tests" / "test_alpha.py", "def test_alpha():\n    assert True\n")
    _write(root / "config" / "alpha.yaml", "enabled: true\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial")
    return root


def test_search_source_excludes_large_default_paths_and_normalizes_windows_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "module.py", "needle = 'source'\n")
    _write(root / "data" / "prices.csv", "needle,data\n")
    _write(root / "logs" / "server.log", "needle\n")
    _write(root / "node_modules" / "pkg" / "index.js", "needle\n")
    config = _config(root)

    response = search_source(config, "needle")
    assert [item["path"] for item in response["items"]] == ["src/module.py"]

    opted_in = search_source(config, "needle", roots=["data"], include_globs=["*.csv"])
    assert [item["path"] for item in opted_in["items"]] == ["data/prices.csv"]

    read = read_files(config, ["src\\module.py"])
    assert read["files"][0]["path"] == "src/module.py"


def test_bulk_read_and_stat_are_safe_and_bounded(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "one.txt", "one\ntwo\nthree\nfour\n")
    _write(root / "src" / "two.txt", "second\n")
    binary = root / "src" / "payload.bin"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(b"\x00\x01\x02")
    _write(root / ".env", "TOKEN=secret\n")
    config = _config(root)

    response = read_files(config, ["src/one.txt", "missing.txt", "src/payload.bin", ".env"], max_lines_per_file=2, max_bytes_per_file=8, total_max_bytes=12)
    assert [item["path"] for item in response["files"]] == ["src/one.txt", "missing.txt", "src/payload.bin", ".env"]
    assert response["files"][0]["truncated"]
    assert response["files"][1]["error"] == "Path does not exist"
    assert response["files"][2]["is_binary"] and response["files"][2]["content"] == ""
    assert "Sensitive" in response["files"][3]["error"]
    assert response["total_returned_bytes"] <= 12

    stats = stat_files(config, ["src/one.txt", "src", "../outside.txt"])
    assert stats["items"][0]["is_file"]
    assert stats["items"][1]["is_directory"]
    assert stats["items"][2]["error"] is not None


def test_git_change_tools_are_paginated_and_exclude_data(tmp_path: Path) -> None:
    root = _git_repository(tmp_path)
    _write(root / "src" / "alpha.py", "VALUE = 2\n")
    (root / "src" / "delete_me.py").unlink()
    (root / "src" / "rename_me.py").rename(root / "src" / "renamed.py")
    _git(root, "add", "-A")
    _write(root / "src" / "new_file.py", "NEW = True\n")
    (root / "src" / "new_binary.bin").write_bytes(b"\x00\x01")
    _write(root / "data" / "prices.csv", "timestamp,price\n")
    config = _config(root)

    changed = list_changed_paths(config, max_paths=1)
    assert changed["truncated"] and changed["next_cursor"]
    page_two = list_changed_paths(config, max_paths=10, cursor=changed["next_cursor"])
    all_paths = [value for group in (changed, page_two) for key in ("modified", "added", "untracked", "deleted", "renamed", "copied", "conflicted") for value in group[key]]
    assert any(value == "src/new_file.py" for value in all_paths)

    review = read_changed_files(config, max_files=1, total_max_bytes=1000)
    assert review["truncated"] and review["next_cursor"]
    assert all(item["path"] != "data/prices.csv" for item in review["items"])
    next_review = read_changed_files(config, max_files=10, total_max_bytes=1000, cursor=review["next_cursor"])
    assert any(item["path"] == "src/new_file.py" for item in next_review["items"])
    assert any(item["path"] == "src/new_binary.bin" and item["reason"] == "Binary content is not returned" for item in next_review["skipped_paths"])

    diff = git_diff(config, path="src/alpha.py", mode="unified", max_bytes=10)
    assert diff["status"] in {"ok", "partial"}
    names = git_diff(config, mode="name_only")
    assert names["mode"] == "name_only"


def test_snapshot_bundle_and_health_use_only_synthetic_repository(tmp_path: Path) -> None:
    root = _git_repository(tmp_path)
    _write(root / "src" / "alpha.py", "VALUE = 3\n")
    config = _config(root)

    before = mcp_health(config)
    assert before["index"]["ready"] is False
    snapshot = get_repo_snapshot(config, include_untracked=False)
    assert snapshot["clean"] is False
    bundle = get_code_review_bundle(config, max_total_bytes=1000)
    assert any(item["path"] == "src/alpha.py" for item in bundle["changes"])
    assert "tests/test_alpha.py" in bundle["related_test_paths"]
    assert "config/alpha.yaml" in bundle["related_config_paths"]
    after = mcp_health(config)
    assert after["index"]["ready"] is True
    assert mcp_diagnostics(config)["tools"] == {}  # Direct implementation calls do not impersonate MCP requests.
