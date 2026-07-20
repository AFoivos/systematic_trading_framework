from __future__ import annotations

import os
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DotenvFormatError(ValueError):
    """Raised when a local .env line cannot be interpreted safely."""


def load_project_dotenv(
    path: str | Path | None = None,
    *,
    override: bool = False,
) -> Path | None:
    """Load a local .env file without replacing explicit process variables.

    The parser intentionally supports a small, auditable subset: ``KEY=value``,
    optional ``export``, quoted values, blank lines, and comments. Shell
    expansion and command substitution are never evaluated.
    """

    resolved = Path(path) if path is not None else PROJECT_ROOT / ".env"
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    if not resolved.is_file():
        return None

    for line_number, raw_line in enumerate(
        resolved.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        parsed = _parse_line(raw_line, path=resolved, line_number=line_number)
        if parsed is None:
            continue
        name, value = parsed
        if override or name not in os.environ:
            os.environ[name] = value
    return resolved


def _parse_line(
    raw_line: str,
    *,
    path: Path,
    line_number: int,
) -> tuple[str, str] | None:
    line = raw_line.lstrip("\ufeff").strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].lstrip()
    if "=" not in line:
        raise DotenvFormatError(f"{path}:{line_number}: expected KEY=value.")

    name, raw_value = line.split("=", 1)
    name = name.strip()
    if not _ENV_NAME.fullmatch(name):
        raise DotenvFormatError(
            f"{path}:{line_number}: invalid environment variable name {name!r}."
        )
    return name, _parse_value(raw_value.strip(), path=path, line_number=line_number)


def _parse_value(raw_value: str, *, path: Path, line_number: int) -> str:
    if not raw_value:
        return ""
    if raw_value[0] not in {"'", '"'}:
        return re.split(r"\s+#", raw_value, maxsplit=1)[0].rstrip()

    quote = raw_value[0]
    escaped = False
    closing_index: int | None = None
    for index, character in enumerate(raw_value[1:], start=1):
        if quote == '"' and character == "\\" and not escaped:
            escaped = True
            continue
        if character == quote and not escaped:
            closing_index = index
            break
        escaped = False
    if closing_index is None:
        raise DotenvFormatError(f"{path}:{line_number}: unterminated quoted value.")

    suffix = raw_value[closing_index + 1 :].strip()
    if suffix and not suffix.startswith("#"):
        raise DotenvFormatError(
            f"{path}:{line_number}: unexpected content after quoted value."
        )
    value = raw_value[1:closing_index]
    if quote == '"':
        value = value.replace(r"\n", "\n").replace(r"\r", "\r").replace(r"\t", "\t")
        value = value.replace(r'\"', '"').replace(r"\\", "\\")
    return value


__all__ = ["DotenvFormatError", "load_project_dotenv"]
