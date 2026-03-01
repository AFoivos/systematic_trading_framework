from __future__ import annotations
from pathlib import Path

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
