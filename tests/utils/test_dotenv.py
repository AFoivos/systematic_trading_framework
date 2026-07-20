from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.utils.dotenv import DotenvFormatError, load_project_dotenv


def test_dotenv_loads_supported_values_without_overriding_process_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(
            [
                "# credentials",
                "EMPTY=",
                "export SIMPLE=value",
                "SINGLE='literal # value'",
                'DOUBLE="line\\nvalue"',
                "COMMENTED=kept # trailing comment",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SIMPLE", "explicit")
    for name in ("EMPTY", "SINGLE", "DOUBLE", "COMMENTED"):
        monkeypatch.delenv(name, raising=False)

    loaded = load_project_dotenv(path)

    assert loaded == path
    assert os.environ["EMPTY"] == ""
    assert os.environ["SIMPLE"] == "explicit"
    assert os.environ["SINGLE"] == "literal # value"
    assert os.environ["DOUBLE"] == "line\nvalue"
    assert os.environ["COMMENTED"] == "kept"


def test_dotenv_rejects_shell_syntax_instead_of_evaluating_it(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("not an assignment\n", encoding="utf-8")

    with pytest.raises(DotenvFormatError, match="expected KEY=value"):
        load_project_dotenv(path)


def test_missing_dotenv_is_optional(tmp_path: Path) -> None:
    assert load_project_dotenv(tmp_path / "missing.env") is None
