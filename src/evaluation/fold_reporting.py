from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


FoldReporter = Callable[[str, int, Mapping[str, Any]], None]

_ACTIVE_FOLD_REPORTER: ContextVar[FoldReporter | None] = ContextVar(
    "active_optuna_fold_reporter",
    default=None,
)


@contextmanager
def optuna_fold_reporting_context(reporter: FoldReporter | None):
    """
    Scope fold-level Optuna progress reporting to the current experiment execution.
    """
    token = _ACTIVE_FOLD_REPORTER.set(reporter)
    try:
        yield
    finally:
        _ACTIVE_FOLD_REPORTER.reset(token)


def report_optuna_fold(stage: str, fold: int, payload: Mapping[str, Any]) -> None:
    """
    Forward one fold payload to the active Optuna reporter when a study has registered one.
    """
    reporter = _ACTIVE_FOLD_REPORTER.get()
    if reporter is None:
        return
    reporter(str(stage), int(fold), payload)


__all__ = [
    "FoldReporter",
    "optuna_fold_reporting_context",
    "report_optuna_fold",
]
