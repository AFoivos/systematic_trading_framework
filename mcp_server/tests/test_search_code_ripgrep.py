from __future__ import annotations

from pathlib import Path

import pytest

from repo_mcp import repository
from repo_mcp.config import FullAccessConfig, ServerConfig
from repo_mcp.repository import search_code, search_source
from repo_mcp.write_tools import write_file


def _config(root: Path, *, writable: bool = False) -> ServerConfig:
    return ServerConfig(
        repo_root=root,
        host="127.0.0.1",
        port=0,
        max_read_bytes=1_000_000,
        max_search_results=200,
        max_tree_entries=5_000,
        script_timeout_seconds=30,
        approved_python_scripts=(),
        full_access=FullAccessConfig(enabled=writable, allow_write=writable, allow_delete=writable, confirmation_token="test-confirm"),
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _collect_source_pages(config: ServerConfig, query: str, **kwargs: object) -> list[dict[str, object]]:
    response = search_source(config, query, **kwargs)
    items = list(response["items"])
    while response["next_cursor"]:
        response = search_source(config, query, cursor=response["next_cursor"], **kwargs)
        items.extend(response["items"])
    return items


def test_search_code_cursor_pages_one_file_without_duplicates_and_legacy_calls(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "many.py", "\n".join(f"needle = {line}" for line in range(1, 9)) + "\n")
    config = _config(root)

    first = search_code(config, "needle", max_results=2, time_budget_ms=3_000)
    assert first["next_cursor"]
    pages = list(first["results"])
    response = first
    while response["next_cursor"]:
        response = search_code(config, "needle", max_results=2, time_budget_ms=3_000, cursor=response["next_cursor"])
        pages.extend(response["results"])
    assert [(item["path"], item["line"]) for item in pages] == [("src/many.py", line) for line in range(1, 9)]
    assert len({(item["path"], item["line"]) for item in pages}) == 8

    legacy = search_code(config, "needle", max_results=20)
    assert [item["line"] for item in legacy["results"]] == list(range(1, 9))


def test_default_candidate_search_includes_late_src_models_and_excludes_unsafe_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "a_early.py", "VALUE = 'ordinary'\n")
    _write(root / "src" / "models" / "z_late.py", "needle = 'src models'\n")
    _write(root / "models" / "checkpoint.py", "needle = 'generated root model'\n")
    _write(root / ".venv312" / "lib.py", "needle = 'venv'\n")
    _write(root / ".venv_map" / "lib.py", "needle = 'venv map'\n")
    _write(root / "data" / "prices.csv", "needle,data\n")
    _write(root / "logs" / "server.log", "needle\n")
    config = _config(root)

    found = search_source(config, "needle")
    assert [(item["path"], item["line"]) for item in found["items"]] == [("src/models/z_late.py", 1)]
    assert search_source(config, "definitely-no-source-match")["items"] == []


def test_default_search_falls_back_without_ripgrep_and_pages_deterministically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "a.py", "needle = 1\nneedle = 2\n")
    _write(root / "src" / "models" / "z.py", "needle = 3\nneedle = 4\n")
    config = _config(root)
    monkeypatch.setattr(repository.shutil, "which", lambda executable: None if executable == "rg" else None)

    pages = _collect_source_pages(config, "needle", max_results=1)
    assert [(item["path"], item["line"]) for item in pages] == [
        ("src/a.py", 1),
        ("src/a.py", 2),
        ("src/models/z.py", 1),
        ("src/models/z.py", 2),
    ]


def test_default_search_rejects_malformed_and_stale_cursors(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "many.py", "needle = 1\nneedle = 2\nneedle = 3\n")
    config = _config(root, writable=True)

    with pytest.raises(ValueError, match="Invalid or stale"):
        search_source(config, "needle", max_results=1, cursor="not-a-server-cursor")

    first = search_source(config, "needle", max_results=1)
    assert first["next_cursor"]
    write_file(config, "src/many.py", "needle = 4\nneedle = 5\n", confirmation="test-confirm")
    with pytest.raises(ValueError, match="stale"):
        search_source(config, "needle", max_results=1, cursor=first["next_cursor"])
