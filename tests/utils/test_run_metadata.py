from __future__ import annotations

import src.utils.run_metadata as metadata


def test_collect_git_metadata_prefers_git_cli(monkeypatch) -> None:
    values = {
        ("rev-parse", "HEAD"): "abc123",
        ("branch", "--show-current"): "main",
        ("status", "--porcelain"): " M src/example.py",
    }
    monkeypatch.setattr(metadata, "_safe_git", lambda args: values.get(tuple(args)))
    result = metadata.collect_git_metadata()
    assert result["commit"] == "abc123"
    assert result["branch"] == "main"
    assert result["is_dirty"] is True
    assert result["source"] == "git_cli"
    assert result["source_identity_complete"] is True
    assert len(result["worktree_state_sha256"]) == 64


def test_collect_git_metadata_falls_back_to_environment(monkeypatch) -> None:
    monkeypatch.setattr(metadata, "_safe_git", lambda args: None)
    monkeypatch.setenv("GIT_COMMIT", "image-commit")
    monkeypatch.setenv("GIT_BRANCH", "image-branch")
    monkeypatch.setenv("GIT_DIRTY", "false")
    result = metadata.collect_git_metadata()
    assert result["commit"] == "image-commit"
    assert result["branch"] == "image-branch"
    assert result["is_dirty"] is False
    assert result["source"] == "environment"
    assert result["source_identity_complete"] is True


def test_strict_run_metadata_rejects_incomplete_source_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        metadata,
        "collect_git_metadata",
        lambda: {
            "commit": None,
            "branch": None,
            "is_dirty": None,
            "source": "unavailable",
            "worktree_state_sha256": None,
            "worktree_files": [],
            "source_identity_complete": False,
        },
    )

    try:
        metadata.build_run_metadata(
            config_path="config/example.yaml",
            runtime_applied={"repro_mode": "strict"},
            config_hash_sha256="x" * 64,
            config_hash_input={},
            data_fingerprint={},
            data_context={},
            model_meta={},
        )
    except RuntimeError as exc:
        assert "Strict reproducibility" in str(exc)
    else:
        raise AssertionError("strict metadata unexpectedly accepted incomplete source identity")
