from __future__ import annotations

import src.utils.run_metadata as metadata


def test_collect_git_metadata_prefers_git_cli(monkeypatch) -> None:
    values = {
        ("rev-parse", "HEAD"): "abc123",
        ("branch", "--show-current"): "main",
        ("status", "--porcelain"): " M src/example.py",
    }
    monkeypatch.setattr(metadata, "_safe_git", lambda args: values.get(tuple(args)))
    assert metadata.collect_git_metadata() == {
        "commit": "abc123", "branch": "main", "is_dirty": True, "source": "git_cli"
    }


def test_collect_git_metadata_falls_back_to_environment(monkeypatch) -> None:
    monkeypatch.setattr(metadata, "_safe_git", lambda args: None)
    monkeypatch.setenv("GIT_COMMIT", "image-commit")
    monkeypatch.setenv("GIT_BRANCH", "image-branch")
    monkeypatch.setenv("GIT_DIRTY", "false")
    assert metadata.collect_git_metadata() == {
        "commit": "image-commit", "branch": "image-branch", "is_dirty": False, "source": "environment"
    }
