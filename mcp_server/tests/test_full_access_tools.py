from __future__ import annotations

from pathlib import Path

import pytest

from repo_mcp.command_tools import git_add, run_experiment, run_shell_command
from repo_mcp.config import FullAccessConfig, ServerConfig
from repo_mcp.security import PathSecurityError
from repo_mcp.write_tools import apply_patch, delete_path, write_file


TOKEN = "RUN_FULL_ACCESS_REPOSITORY_ACTION"


def _config(root: Path, require_confirmation: bool = True) -> ServerConfig:
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
            confirmation_token=TOKEN,
            max_output_bytes=200_000,
            default_timeout_seconds=30,
            max_timeout_seconds=120,
            allow_shell=True,
            allow_write=True,
            allow_delete=True,
            allow_git_write=True,
        ),
    )


def test_write_file_can_create_file_inside_repo_root(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    payload = write_file(cfg, "notes/example.txt", "hello\n", confirmation=TOKEN)

    assert payload["ok"] is True
    assert payload["path"] == "notes/example.txt"
    assert (tmp_path / "notes/example.txt").read_text(encoding="utf-8") == "hello\n"


def test_write_file_rejects_absolute_paths(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    with pytest.raises(PathSecurityError):
        write_file(cfg, "/tmp/outside.txt", "no", confirmation=TOKEN)


def test_write_file_rejects_path_traversal(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    with pytest.raises(PathSecurityError):
        write_file(cfg, "../outside.txt", "no", confirmation=TOKEN)


def test_delete_path_refuses_to_delete_git(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (tmp_path / ".git").mkdir()

    with pytest.raises(PermissionError, match="\\.git"):
        delete_path(cfg, ".git", recursive=True, confirmation=TOKEN)


def test_apply_patch_applies_simple_patch(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    target = tmp_path / "sample.txt"
    target.write_text("old\n", encoding="utf-8")
    patch = """diff --git a/sample.txt b/sample.txt
--- a/sample.txt
+++ b/sample.txt
@@ -1 +1 @@
-old
+new
"""

    payload = apply_patch(cfg, patch, confirmation=TOKEN)

    assert payload["return_code"] == 0
    assert target.read_text(encoding="utf-8") == "new\n"


def test_run_shell_command_runs_harmless_command(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    payload = run_shell_command(cfg, "python -c \"print('ok')\"", confirmation=TOKEN)

    assert payload["return_code"] == 0
    assert payload["stdout"].strip() == "ok"
    assert payload["timed_out"] is False


def test_run_shell_command_requires_confirmation_when_configured(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    with pytest.raises(PermissionError, match=TOKEN):
        run_shell_command(cfg, "python -c \"print('ok')\"")


def test_run_experiment_rejects_configs_outside_experiments(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    config_path = tmp_path / "config/not_experiments.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("experiment: {}\n", encoding="utf-8")

    with pytest.raises(PathSecurityError, match="config/experiments"):
        run_experiment(cfg, "config/not_experiments.yaml", confirmation=TOKEN)


def test_git_write_tools_require_confirmation(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    target = tmp_path / "tracked.txt"
    target.write_text("hello\n", encoding="utf-8")

    with pytest.raises(PermissionError, match=TOKEN):
        git_add(cfg, ["tracked.txt"])
