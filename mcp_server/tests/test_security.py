from pathlib import Path

import pytest

from repo_mcp.security import PathSecurityError, resolve_repo_path


def test_resolve_repo_path_accepts_relative_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    assert resolve_repo_path(root, "src/example.py") == root / "src/example.py"


def test_resolve_repo_path_rejects_absolute_paths(tmp_path: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_repo_path(tmp_path, "/etc/passwd")
    with pytest.raises(PathSecurityError):
        resolve_repo_path(tmp_path, "C:\\outside.txt")


def test_resolve_repo_path_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        (root / "outside.txt").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable for this Windows account: {exc}")

    with pytest.raises(PathSecurityError):
        resolve_repo_path(root, "outside.txt")
