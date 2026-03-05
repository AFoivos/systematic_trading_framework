from __future__ import annotations
import os
import tempfile
from pathlib import Path

_ALLOW_EXTERNAL_PATHS_ENV = "STF_ALLOW_EXTERNAL_PATHS"
_BLOCKED_ABSOLUTE_PREFIXES = (
    Path("/etc"),
    Path("/bin"),
    Path("/sbin"),
    Path("/usr"),
    Path("/System"),
    Path("/Library"),
    Path("/dev"),
    Path("/proc"),
    Path("/sys"),
)

_THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT: Path = _THIS_FILE.parents[2]

SRC_DIR: Path = PROJECT_ROOT / "src"
CONFIG_DIR: Path = PROJECT_ROOT / "config"
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
METADATA_DIR: Path = DATA_DIR / "metadata"
NOTEBOOKS_DIR: Path = PROJECT_ROOT / "notebooks"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
TESTS_DIR: Path = PROJECT_ROOT / "tests"


def _is_within(path: Path, root: Path) -> bool:
    """
    Return True when path is inside root.
    """
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def enforce_safe_absolute_path(path: str | Path) -> Path:
    """
    Enforce a conservative absolute-path policy for config-driven file I/O.

    By default only project-root and system temp paths are allowed. Set
    STF_ALLOW_EXTERNAL_PATHS=1 to allow any external path except blocked
    system directories.
    """
    p = Path(path).resolve()
    if not p.is_absolute():
        return p

    for blocked in _BLOCKED_ABSOLUTE_PREFIXES:
        if _is_within(p, blocked):
            raise ValueError(f"Access to protected path is not allowed: {p}")

    allow_external = os.getenv(_ALLOW_EXTERNAL_PATHS_ENV, "0") == "1"
    if allow_external:
        return p

    allowed_roots = (
        PROJECT_ROOT.resolve(),
        Path(tempfile.gettempdir()).resolve(),
    )
    if any(_is_within(p, root) for root in allowed_roots):
        return p

    raise ValueError(
        f"Absolute path outside allowed roots is not allowed: {p}. "
        f"Set {_ALLOW_EXTERNAL_PATHS_ENV}=1 to override."
    )

def in_project(*parts: str | Path) -> Path:
    """
    Handle in project inside the infrastructure layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    return PROJECT_ROOT.joinpath(*parts)


def ensure_directories_exist() -> None:
    """
    Handle ensure directories exist inside the infrastructure layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    for p in [
        CONFIG_DIR,
        DATA_DIR,
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        METADATA_DIR,
        NOTEBOOKS_DIR,
        LOGS_DIR,
        TESTS_DIR,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def describe_paths() -> None:
    """
    Describe paths for quick inspection while working inside the infrastructure layer. The
    helper keeps diagnostic output localized instead of scattering print logic across the
    codebase.
    """
    print(f"PROJECT_ROOT      = {PROJECT_ROOT}")
    print(f"SRC_DIR           = {SRC_DIR}")
    print(f"CONFIG_DIR        = {CONFIG_DIR}")
    print(f"DATA_DIR          = {DATA_DIR}")
    print(f"RAW_DATA_DIR      = {RAW_DATA_DIR}")
    print(f"PROCESSED_DATA_DIR= {PROCESSED_DATA_DIR}")
    print(f"METADATA_DIR      = {METADATA_DIR}")
    print(f"NOTEBOOKS_DIR     = {NOTEBOOKS_DIR}")
    print(f"LOGS_DIR          = {LOGS_DIR}")
    print(f"TESTS_DIR         = {TESTS_DIR}")

if __name__ == "__main__":
    ensure_directories_exist()
    describe_paths()
