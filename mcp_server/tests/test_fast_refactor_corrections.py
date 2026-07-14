from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

import pytest

from repo_mcp.config import FullAccessConfig, ServerConfig
from repo_mcp.git_tools import GitCommandResult, GitState, get_code_review_bundle, get_repo_snapshot, git_diff, git_status, list_changed_paths, mcp_health, read_changed_files
from repo_mcp.repository import read_files, search_code, search_source, stat_files
from repo_mcp.runtime import get_runtime
from repo_mcp.scan_policy import RepositoryScanPolicy
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


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "mcp-tests@example.invalid")
    _git(root, "config", "user.name", "MCP Tests")
    _write(root / ".gitignore", "ignored/\n")
    _write(root / "src" / "base.py", "BASE = 1\n")
    _write(root / "src" / "staged.py", "STAGED = 1\n")
    _write(root / "src" / "remove.py", "REMOVE = 1\n")
    _write(root / "src" / "rename_old.py", "RENAME = 1\n")
    _write(root / "tests" / "test_base.py", "def test_base():\n    assert True\n")
    _write(root / "config" / "base.yaml", "enabled: true\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    return root


def _all_source_pages(config: ServerConfig, query: str, **kwargs: object) -> list[dict[str, object]]:
    response = search_source(config, query, **kwargs)
    items = list(response["items"])
    while response["next_cursor"]:
        response = search_source(config, query, cursor=response["next_cursor"], **kwargs)
        items.extend(response["items"])
    return items


def test_scan_policy_distinguishes_top_level_models_venvs_and_separators(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "models" / "registry.py", "needle = 'src models'\n")
    _write(root / "tests" / "models" / "test_registry.py", "needle = 'tests models'\n")
    _write(root / "models" / "checkpoint.py", "needle = 'root models'\n")
    _write(root / ".venv" / "lib.py", "needle = 'venv'\n")
    _write(root / ".venv312" / "lib.py", "needle = 'venv312'\n")
    _write(root / ".venv_map" / "lib.py", "needle = 'venv map'\n")
    _write(root / "src" / "node_modules" / "nested.py", "needle = 'node modules'\n")
    config = _config(root)

    result = search_source(config, "needle", roots=["."], include_globs=["*.py"])
    paths = [item["path"] for item in result["items"]]
    assert "src/models/registry.py" in paths
    assert "tests/models/test_registry.py" in paths
    assert "models/checkpoint.py" not in paths
    assert not any(".venv" in path or "node_modules" in path for path in paths)

    policy = RepositoryScanPolicy()
    assert not policy.should_skip_directory("src\\models")
    assert policy.should_skip_directory("models")
    assert policy.should_skip_directory(".venv312")
    assert policy.should_skip_directory("src/node_modules")


def test_search_code_default_uses_reusable_index_and_excludes_generated_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "models" / "registry.py", "def needle():\n    return 'ok'\n")
    _write(root / "data" / "prices.csv", "needle,price\n")
    _write(root / ".venv312" / "lib.py", "needle = True\n")
    config = _config(root)
    runtime = get_runtime(root)

    first = search_code(config, "needle", root=".")
    assert [item["path"] for item in first["results"]] == ["src/models/registry.py"]
    assert runtime.source_index.ready
    refreshes = runtime.source_index.refresh_count
    hits = runtime.cache_hits
    second = search_code(config, "needle", root="")
    assert second["results"] == first["results"]
    assert runtime.source_index.refresh_count == refreshes
    assert runtime.cache_hits > hits

    opted_in = search_source(config, "needle", roots=["data"], include_globs=["*.csv"])
    assert [item["path"] for item in opted_in["items"]] == ["data/prices.csv"]


def test_source_search_same_file_pagination_and_traversal_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "many.py", "\n".join(f"needle = {number}" for number in range(1, 8)) + "\n")
    config = _config(root)
    pages = _all_source_pages(config, "needle", max_results=2)
    assert [item["line"] for item in pages] == list(range(1, 8))

    from repo_mcp import repository

    original = repository._next_walk_file

    def delayed_next(*args: object, **kwargs: object) -> str | None:
        time.sleep(0.003)
        return original(*args, **kwargs)

    monkeypatch.setattr(repository, "_next_walk_file", delayed_next)
    partial = search_source(config, "needle", roots=["src"], time_budget_ms=1)
    assert partial["status"] == "partial"
    assert partial["next_cursor"]


def test_source_index_ttl_write_invalidation_and_health_no_refresh(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "module.py", "VALUE = 1\n")
    config = _config(root, writable=True)
    runtime = get_runtime(root)
    cold_health = mcp_health(config)
    assert cold_health["server_version"] and cold_health["implementation_build_id"]
    assert cold_health["index"]["ready"] is False
    search_source(config, "VALUE")
    assert runtime.source_index.ready
    refresh_count = runtime.source_index.refresh_count
    search_source(config, "VALUE")
    assert runtime.source_index.refresh_count == refresh_count

    write_file(config, "src/module.py", "VALUE = 2\n", confirmation="test-confirm")
    assert not runtime.source_index.ready
    before_health = runtime.source_index.refresh_count
    mcp_health(config)
    assert runtime.source_index.refresh_count == before_health
    assert search_source(config, "VALUE = 2")["items"]
    assert runtime.source_index.refresh_count == before_health + 1


def test_source_cursor_rejects_index_generation_change(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "many.py", "needle = 1\nneedle = 2\n")
    config = _config(root, writable=True)
    first = search_source(config, "needle", max_results=1)
    assert first["next_cursor"]
    write_file(config, "src/many.py", "needle = 3\nneedle = 4\n", confirmation="test-confirm")
    with pytest.raises(ValueError, match="stale"):
        search_source(config, "needle", max_results=1, cursor=first["next_cursor"])


def test_bounded_read_hashes_only_returned_content_and_binary_text_extensions_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    large = root / "src" / "large.txt"
    _write(large, "prefix\n" + "x" * 2_000_000)
    for suffix in (".bin", ".csv", ".json"):
        path = root / "src" / f"payload{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x00binary")
    _write(root / "src" / "unicode.py", "message = 'αθήνα'\n")
    config = _config(root)

    read = read_files(config, ["src/large.txt"], max_bytes_per_file=7)
    record = read["files"][0]
    with large.open("rb") as fh:
        expected = hashlib.sha256(fh.read(7)).hexdigest()
    assert record["returned_content_sha256"] == expected
    assert record["sha256"] == expected
    assert record["returned_content_sha256"] != hashlib.sha256(b"prefix\r\n" + b"x" * 2_000_000).hexdigest()
    binary = read_files(config, ["src/payload.bin", "src/payload.csv", "src/payload.json", "src/unicode.py"])["files"]
    assert all(item["is_binary"] for item in binary[:3])
    assert binary[3]["content"].startswith("message")


def test_non_git_responses_do_not_claim_clean_or_detached(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    config = _config(root)
    status = git_status(config)
    snapshot = get_repo_snapshot(config)
    assert status["git_worktree_valid"] is False
    assert status["clean"] is None and status["detached_head"] is None
    assert snapshot["status"] == "error"
    assert snapshot["clean"] is None and snapshot["detached_head"] is None
    assert mcp_health(config)["git_worktree_valid"] is False


def test_missing_git_or_timeout_is_structured_not_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    config = _config(root)
    import repo_mcp.git_tools as git_tools

    monkeypatch.setattr(git_tools, "_run_git", lambda *args, **kwargs: GitCommandResult(b"", b"git missing", None, False, False, False, 1, "git executable not found"))
    missing = git_status(config)
    assert missing["git_available"] is False
    assert missing["clean"] is None and missing["detached_head"] is None

    monkeypatch.setattr(git_tools, "_run_git", lambda *args, **kwargs: GitCommandResult(b"", b"", None, True, False, False, 1))
    timed_out = get_repo_snapshot(config)
    assert timed_out["status"] == "error"
    assert timed_out["clean"] is None and timed_out["detached_head"] is None


def test_file_level_untracked_review_without_committing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _write(root / "src" / "new_panel" / "__init__.py", "PANEL = 1\n")
    _write(root / "src" / "new_panel" / "feature.py", "FEATURE = 1\n")
    _write(root / "src" / "new_panel" / "helpers.py", "HELPER = 1\n")
    _write(root / "src" / "new_module.py", "SAFE = 1\n")
    _write(root / "data" / "prices.csv", "timestamp,price\n")
    _write(root / ".env", "SECRET=value\n")
    config = _config(root)

    changed = read_changed_files(config, max_files=20, total_max_bytes=100_000)
    paths = {item["path"] for item in changed["items"]}
    assert {"src/new_panel/__init__.py", "src/new_panel/feature.py", "src/new_panel/helpers.py", "src/new_module.py"}.issubset(paths)
    assert "data/prices.csv" not in paths
    assert ".env" not in paths
    bundle = get_code_review_bundle(config, max_total_bytes=100_000)
    assert {"src/new_panel/__init__.py", "src/new_panel/feature.py", "src/new_panel/helpers.py"}.issubset({item["path"] for item in bundle["changes"]})


def test_include_ignored_returns_ignored_group_without_committing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _write(root / ".gitignore", "ignored/\n")
    _write(root / "ignored" / "skip.txt", "ignored\n")
    response = list_changed_paths(_config(root), include_ignored=True)
    assert response["status"] == "ok"
    assert any(path.startswith("ignored/") for path in response["ignored"])


def test_review_bundle_never_claims_clean_when_only_generated_untracked_paths_exist(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _write(root / "data" / "prices.csv", "timestamp,price\n")
    bundle = get_code_review_bundle(_config(root), max_total_bytes=10_000)
    assert bundle["repository_snapshot"]["clean"] is False
    assert bundle["changes"] == []
    assert any(item["path"].startswith("data") for item in bundle["omitted_paths"])


def test_git_status_codes_untracked_directories_ignored_and_snapshot_state(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    _write(root / "src" / "base.py", "BASE = 2\n")  # unstaged:  M
    _write(root / "src" / "staged.py", "STAGED = 2\n")
    _git(root, "add", "src/staged.py")  # staged: M 
    (root / "src" / "remove.py").unlink()
    _git(root, "add", "src/remove.py")  # staged deletion: D 
    (root / "src" / "rename_old.py").rename(root / "src" / "rename_new.py")
    _git(root, "add", "-A", "src/rename_old.py", "src/rename_new.py")
    _write(root / "src" / "new_panel" / "__init__.py", "PANEL = 1\n")
    _write(root / "src" / "new_panel" / "feature.py", "FEATURE = 1\n")
    _write(root / "src" / "new_panel" / "helpers.py", "HELPER = 1\n")
    _write(root / "data" / "prices.csv", "timestamp,price\n")
    _write(root / ".env", "SECRET=value\n")
    _write(root / "ignored" / "skip.txt", "ignored\n")
    config = _config(root)

    status = git_status(config)
    assert " M src/base.py" in status["status"]
    assert "M  src/staged.py" in status["status"]
    assert "D  src/remove.py" in status["status"]
    assert "R  src/rename_old.py -> src/rename_new.py" in status["status"]
    assert "?? src/new_panel" in status["status"]

    ignored = list_changed_paths(config, include_ignored=True)
    assert "ignored/skip.txt" in ignored["ignored"]
    review = read_changed_files(config, max_files=20, total_max_bytes=100_000)
    review_paths = [item["path"] for item in review["items"]]
    assert {"src/new_panel/__init__.py", "src/new_panel/feature.py", "src/new_panel/helpers.py"}.issubset(review_paths)
    assert "data/prices.csv" not in review_paths
    assert ".env" not in review_paths
    bundle = get_code_review_bundle(config, max_total_bytes=100_000)
    assert {"src/new_panel/__init__.py", "src/new_panel/feature.py", "src/new_panel/helpers.py"}.issubset({item["path"] for item in bundle["changes"]})
    assert get_repo_snapshot(config, include_untracked=True)["clean"] is False


def test_git_diff_line_safe_unicode_pagination_and_stale_cursor(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    _write(root / "src" / "base.py", "BASE = 'αθήνα'\n" + "\n".join(f"line_{number} = 'é'" for number in range(50)) + "\n")
    _write(root / "src" / "staged.py", "STAGED = 'changed'\n")
    config = _config(root)
    first = git_diff(config, paths=["src/base.py", "src/staged.py"], max_bytes=180)
    assert first["status"] == "partial"
    assert first["diff"].encode("utf-8").decode("utf-8") == first["diff"]
    assert first["diff"].endswith("\n")
    assert first["next_cursor"]
    _write(root / "src" / "base.py", "BASE = 'changed again'\n")
    with pytest.raises(ValueError, match="stale"):
        git_diff(config, paths=["src/base.py", "src/staged.py"], max_bytes=180, cursor=first["next_cursor"])
    assert git_diff(config, mode="stat")["mode"] == "stat"
    assert git_diff(config, mode="name_only")["mode"] == "name_only"


def test_stat_files_batches_git_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    _write(root / "src" / "one.py", "ONE = 1\n")
    _write(root / "src" / "two.py", "TWO = 2\n")
    config = _config(root)
    calls = 0

    def fake_run(*args: object, **kwargs: object) -> GitCommandResult:
        nonlocal calls
        calls += 1
        return GitCommandResult(b" M src/one.py\0", b"", 0, False, False, False, 1)

    import repo_mcp.git_tools as git_tools

    monkeypatch.setattr(git_tools, "_run_git", fake_run)
    response = stat_files(config, ["src/one.py", "src/two.py"], include_git_status=True)
    assert calls == 1
    assert response["items"][0]["git_status"] == " M"
    assert response["items"][1]["git_status"] is None
