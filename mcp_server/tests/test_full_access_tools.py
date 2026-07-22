from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from repo_mcp.command_tools import git_add, run_command, run_experiment, run_python, run_shell_command
from repo_mcp.config import FullAccessConfig, ServerConfig
from repo_mcp.git_tools import git_diff, git_status
from repo_mcp.repository import read_file, search_code
from repo_mcp.security import PathSecurityError
from repo_mcp.write_tools import (
    apply_patch,
    create_directory,
    delete_path,
    import_local_file,
    move_path,
    write_file,
)


CONFIRMATION = "The user explicitly requested this repository action."


def _config(
    root: Path,
    *,
    require_confirmation: bool = True,
    import_roots: tuple[Path, ...] = (),
    max_output_bytes: int = 200_000,
) -> ServerConfig:
    return ServerConfig(
        repo_root=root.resolve(),
        host="127.0.0.1",
        port=8765,
        max_read_bytes=200_000,
        max_search_results=100,
        max_tree_entries=500,
        script_timeout_seconds=30,
        approved_python_scripts=(),
        full_access=FullAccessConfig(
            enabled=True,
            require_confirmation=require_confirmation,
            confirmation_token="legacy-token-is-not-required",
            max_output_bytes=max_output_bytes,
            max_file_bytes=1_000_000,
            default_timeout_seconds=30,
            max_timeout_seconds=120,
            allowed_import_roots=import_roots,
            allow_shell=True,
            allow_write=True,
            allow_delete=True,
            allow_git_write=True,
        ),
    )


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "mcp-tests@example.invalid")
    _git(root, "config", "user.name", "MCP Tests")


def test_write_file_creates_atomic_utf8_file_and_returns_hashes(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    payload = write_file(cfg, "notes/example.txt", "hello\n")

    expected = hashlib.sha256(b"hello\n").hexdigest()
    assert payload["success"] is True
    assert payload["action"] == "created"
    assert payload["created_files"] == ["notes/example.txt"]
    assert payload["previous_sha256"] is None
    assert payload["new_sha256"] == expected
    assert payload["bytes_written"] == 6
    assert (tmp_path / "notes/example.txt").read_text(encoding="utf-8") == "hello\n"
    assert not list((tmp_path / "notes").glob(".*.tmp"))


def test_write_file_modifies_existing_file_with_optimistic_concurrency(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    created = write_file(cfg, "sample.txt", "old\n")

    updated = write_file(
        cfg,
        "sample.txt",
        "new\n",
        expected_sha256=created["new_sha256"],
    )

    assert updated["action"] == "updated"
    assert updated["changed_files"] == ["sample.txt"]
    assert updated["previous_sha256"] == created["new_sha256"]
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "new\n"


def test_write_file_expected_sha256_rejects_concurrent_change(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    target = tmp_path / "sample.txt"
    target.write_text("changed elsewhere\n", encoding="utf-8")

    payload = write_file(cfg, "sample.txt", "new\n", expected_sha256="0" * 64)

    assert payload["success"] is False
    assert payload["error"]["code"] == "sha256_mismatch"
    assert target.read_text(encoding="utf-8") == "changed elsewhere\n"


def test_write_file_rejects_absolute_and_traversal_paths(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    with pytest.raises(PathSecurityError):
        write_file(cfg, "/tmp/outside.txt", "no")
    with pytest.raises(PathSecurityError):
        write_file(cfg, "../../outside.txt", "no")


def test_write_file_rejects_symlink_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (repo / "escape").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlinks are unavailable: {exc}")

    with pytest.raises(PathSecurityError):
        write_file(_config(repo), "escape/file.txt", "no")


def test_create_directory_and_move_path_work_inside_repository(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    created = create_directory(cfg, "nested/source")
    (tmp_path / "nested/source/file.txt").write_text("value\n", encoding="utf-8")

    moved = move_path(cfg, source="nested/source", destination="nested/destination")

    assert created["created"] is True
    assert moved["success"] is True
    assert not (tmp_path / "nested/source").exists()
    assert (tmp_path / "nested/destination/file.txt").read_text(encoding="utf-8") == "value\n"


def test_apply_patch_handles_multi_file_change_and_dry_run(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (tmp_path / "first.txt").write_text("old\n", encoding="utf-8")
    patch = """diff --git a/first.txt b/first.txt
--- a/first.txt
+++ b/first.txt
@@ -1 +1 @@
-old
+new
diff --git a/second.txt b/second.txt
new file mode 100644
--- /dev/null
+++ b/second.txt
@@ -0,0 +1 @@
+created
"""

    checked = apply_patch(cfg, patch, check_only=True)
    assert checked["success"] is True
    assert (tmp_path / "first.txt").read_text(encoding="utf-8") == "old\n"
    assert not (tmp_path / "second.txt").exists()

    applied = apply_patch(cfg, patch)
    assert applied["success"] is True
    assert applied["changed_files"] == ["first.txt"]
    assert applied["created_files"] == ["second.txt"]
    assert (tmp_path / "first.txt").read_text(encoding="utf-8") == "new\n"
    assert (tmp_path / "second.txt").read_text(encoding="utf-8") == "created\n"


def test_apply_patch_failure_does_not_partially_modify_files(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first-old\n", encoding="utf-8")
    second.write_text("second-old\n", encoding="utf-8")
    patch = """diff --git a/first.txt b/first.txt
--- a/first.txt
+++ b/first.txt
@@ -1 +1 @@
-first-old
+first-new
diff --git a/second.txt b/second.txt
--- a/second.txt
+++ b/second.txt
@@ -1 +1 @@
-does-not-match
+second-new
"""

    payload = apply_patch(cfg, patch)

    assert payload["success"] is False
    assert payload["error"]["code"] == "patch_check_failed"
    assert payload["rejected_hunks"]
    assert first.read_text(encoding="utf-8") == "first-old\n"
    assert second.read_text(encoding="utf-8") == "second-old\n"


def test_apply_patch_rejects_repository_escape(tmp_path: Path) -> None:
    patch = """diff --git a/../../outside.txt b/../../outside.txt
--- /dev/null
+++ b/../../outside.txt
@@ -0,0 +1 @@
+escape
"""

    with pytest.raises(PathSecurityError):
        apply_patch(_config(tmp_path), patch)


def test_import_local_file_copies_and_hashes_allowed_upload(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    uploads = tmp_path / "mnt/data"
    repo.mkdir()
    uploads.mkdir(parents=True)
    source = uploads / "example.py"
    source.write_text("print('imported')\n", encoding="utf-8")
    cfg = _config(repo, import_roots=(uploads,))

    payload = import_local_file(cfg, source.as_posix(), "scripts/example.py")

    assert payload["success"] is True
    assert payload["source_sha256"] == payload["destination_sha256"]
    assert (repo / "scripts/example.py").read_bytes() == source.read_bytes()


def test_import_local_file_rejects_source_symlink_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    uploads = tmp_path / "uploads"
    repo.mkdir()
    uploads.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = uploads / "escape.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"Symlinks are unavailable: {exc}")

    with pytest.raises(PathSecurityError):
        import_local_file(_config(repo, import_roots=(uploads,)), link.as_posix(), "copy.txt")


def test_run_python_executes_non_allowlisted_repository_script(tmp_path: Path) -> None:
    script = tmp_path / "not_allowlisted.py"
    script.write_text("import sys\nprint('script', *sys.argv[1:])\n", encoding="utf-8")

    payload = run_python(
        _config(tmp_path),
        script_path="not_allowlisted.py",
        args=["works"],
        confirmation=CONFIRMATION,
    )

    assert payload["success"] is True
    assert payload["exit_code"] == 0
    assert payload["stdout"].strip() == "script works"


def test_run_command_requires_nonempty_confirmation(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    with pytest.raises(PermissionError, match="non-empty confirmation"):
        run_command(cfg, [sys.executable, "-c", "print('no')"])
    with pytest.raises(PermissionError, match="non-empty confirmation"):
        run_command(cfg, [sys.executable, "-c", "print('no')"], confirmation="  ")


def test_run_command_captures_stdout_stderr_and_nonzero_exit(tmp_path: Path) -> None:
    payload = run_command(
        _config(tmp_path),
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)"],
        confirmation=CONFIRMATION,
    )

    assert payload["success"] is False
    assert payload["exit_code"] == 7
    assert payload["stdout"].strip() == "out"
    assert payload["stderr"].strip() == "err"
    assert payload["error"]["code"] == "nonzero_exit"
    assert payload["timed_out"] is False


def test_run_command_enforces_timeout(tmp_path: Path) -> None:
    payload = run_command(
        _config(tmp_path),
        [sys.executable, "-c", "import time; print('before', flush=True); time.sleep(5)"],
        timeout_seconds=1,
        confirmation=CONFIRMATION,
    )

    assert payload["success"] is False
    assert payload["timed_out"] is True
    assert payload["exit_code"] is None
    assert "before" in payload["stdout"]


def test_run_command_redacts_secret_environment_values(tmp_path: Path) -> None:
    payload = run_command(
        _config(tmp_path),
        [sys.executable, "-c", "import os; print('API_KEY=' + os.environ['API_KEY'])"],
        env={"API_KEY": "super-secret-value"},
        confirmation=CONFIRMATION,
    )

    assert "super-secret-value" not in payload["stdout"]
    assert "API_KEY=<redacted>" in payload["stdout"]


def test_run_shell_command_remains_compatible(tmp_path: Path) -> None:
    payload = run_shell_command(
        _config(tmp_path),
        f"{sys.executable} -c \"print('ok')\"",
        confirmation=CONFIRMATION,
    )

    assert payload["exit_code"] == 0
    assert payload["stdout"].strip() == "ok"


def test_delete_path_requires_confirmation_and_returns_deleted_paths(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    target = tmp_path / "delete-me.txt"
    target.write_text("gone\n", encoding="utf-8")

    with pytest.raises(PermissionError, match="non-empty confirmation"):
        delete_path(cfg, "delete-me.txt")

    payload = delete_path(cfg, "delete-me.txt", confirmation=CONFIRMATION)
    assert payload["success"] is True
    assert payload["deleted_files"] == ["delete-me.txt"]
    assert not target.exists()


def test_delete_path_refuses_repository_metadata(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (tmp_path / ".git").mkdir()

    with pytest.raises(PermissionError, match=r"\.git"):
        delete_path(cfg, ".git", recursive=True, confirmation=CONFIRMATION)


def test_existing_read_search_git_and_staged_diff_tools_still_work(tmp_path: Path) -> None:
    _init_git(tmp_path)
    source = tmp_path / "src/module.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "src/module.py")
    _git(tmp_path, "commit", "-m", "initial")
    source.write_text("VALUE = 2\n", encoding="utf-8")

    cfg = _config(tmp_path)
    read = read_file(cfg, "src/module.py")
    search = search_code(cfg, "VALUE", root=".")
    status = git_status(cfg)
    unstaged = git_diff(cfg, mode="name_only")
    _git(tmp_path, "add", "src/module.py")
    staged = git_diff(cfg, staged=True)

    assert read["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert search["results"]
    assert "src/module.py" in status["porcelain"]
    assert "src/module.py" in (unstaged["output"] or "")
    assert "-VALUE = 1" in staged["diff"]


def test_run_experiment_rejects_configs_outside_experiments(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    config_path = tmp_path / "config/not_experiments.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("experiment: {}\n", encoding="utf-8")

    with pytest.raises(PathSecurityError, match="config/experiments"):
        run_experiment(cfg, "config/not_experiments.yaml", confirmation=CONFIRMATION)


def test_git_write_tools_require_nonempty_confirmation(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    target = tmp_path / "tracked.txt"
    target.write_text("hello\n", encoding="utf-8")

    with pytest.raises(PermissionError, match="non-empty confirmation"):
        git_add(cfg, ["tracked.txt"])
