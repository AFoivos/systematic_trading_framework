"""Lazy access to the optional VectorBT research dependency."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from types import ModuleType


VECTORBT_DISTRIBUTION = "vectorbt"
VECTORBT_PIN = "0.28.5"


class VectorBTDependencyError(RuntimeError):
    """Raised only when the VectorBT backend is selected but unavailable."""


def load_vectorbt() -> ModuleType:
    """Import VectorBT lazily and raise an actionable capability error."""

    installed_version = vectorbt_version()
    if installed_version != VECTORBT_PIN:
        raise VectorBTDependencyError(
            "VectorBT backend requires the reproducibility pin "
            f"'{VECTORBT_DISTRIBUTION}=={VECTORBT_PIN}', but found "
            f"'{installed_version}'. Install the bounded optional manifest with "
            "'python -m pip install -r requirements.vectorbt.txt'."
        )
    try:
        return import_module(VECTORBT_DISTRIBUTION)
    except ModuleNotFoundError as exc:
        if exc.name != VECTORBT_DISTRIBUTION:
            raise
        raise VectorBTDependencyError(
            "VectorBT backend requires optional dependency "
            f"'{VECTORBT_DISTRIBUTION}=={VECTORBT_PIN}'. Install it with "
            "'python -m pip install -r requirements.vectorbt.txt'."
        ) from exc


def vectorbt_version() -> str:
    """Return the installed distribution version without importing it eagerly."""

    try:
        return version(VECTORBT_DISTRIBUTION)
    except PackageNotFoundError as exc:
        raise VectorBTDependencyError(
            "VectorBT backend requires optional dependency "
            f"'{VECTORBT_DISTRIBUTION}=={VECTORBT_PIN}'. Install it with "
            "'python -m pip install -r requirements.vectorbt.txt'."
        ) from exc


__all__ = [
    "VECTORBT_DISTRIBUTION",
    "VECTORBT_PIN",
    "VectorBTDependencyError",
    "load_vectorbt",
    "vectorbt_version",
]
