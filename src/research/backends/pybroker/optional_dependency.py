"""Lazy access to the optional PyBroker research dependency."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from types import ModuleType


PYBROKER_DISTRIBUTION = "lib-pybroker"
PYBROKER_IMPORT_NAME = "pybroker"
PYBROKER_PIN = "1.2.14"


class PyBrokerDependencyError(RuntimeError):
    """Raised only when the PyBroker backend is selected but unavailable."""


def pybroker_version() -> str:
    """Return the installed distribution version without importing PyBroker."""

    try:
        return version(PYBROKER_DISTRIBUTION)
    except PackageNotFoundError as exc:
        raise PyBrokerDependencyError(
            "PyBroker backend requires optional dependency "
            f"'{PYBROKER_DISTRIBUTION}=={PYBROKER_PIN}'. Install the bounded "
            "optional manifest with 'python -m pip install -r "
            "requirements.pybroker.txt'."
        ) from exc


def load_pybroker() -> ModuleType:
    """Import PyBroker lazily and reject version drift before adapter work."""

    installed_version = pybroker_version()
    if installed_version != PYBROKER_PIN:
        raise PyBrokerDependencyError(
            "PyBroker backend requires the reproducibility pin "
            f"'{PYBROKER_DISTRIBUTION}=={PYBROKER_PIN}', but found "
            f"'{installed_version}'. Install the bounded optional manifest with "
            "'python -m pip install -r requirements.pybroker.txt'."
        )
    try:
        return import_module(PYBROKER_IMPORT_NAME)
    except ModuleNotFoundError as exc:
        if exc.name != PYBROKER_IMPORT_NAME:
            raise
        raise PyBrokerDependencyError(
            "PyBroker backend requires optional dependency "
            f"'{PYBROKER_DISTRIBUTION}=={PYBROKER_PIN}'. Install it with "
            "'python -m pip install -r requirements.pybroker.txt'."
        ) from exc


__all__ = [
    "PYBROKER_DISTRIBUTION",
    "PYBROKER_IMPORT_NAME",
    "PYBROKER_PIN",
    "PyBrokerDependencyError",
    "load_pybroker",
    "pybroker_version",
]
