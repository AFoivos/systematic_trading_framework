from __future__ import annotations

"""Small process-local facilities shared by MCP inspection tools."""

import json
import os
import platform
import secrets
import sys
import time
from collections import OrderedDict, defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .scan_policy import DEFAULT_SOURCE_GLOBS, DEFAULT_SOURCE_ROOTS, RepositoryScanPolicy, classify_source_path


SERVER_VERSION = "2.1.0"
IMPLEMENTATION_BUILD_ID = "mcp-fast-20260714-2"
SOURCE_INDEX_TTL_SECONDS = 30.0


class OperationBudget:
    def __init__(self, time_budget_ms: int | None) -> None:
        self.limit_ms = max(1, int(time_budget_ms or 1))
        self.started = time.perf_counter()

    @property
    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)

    @property
    def remaining_ms(self) -> int:
        return max(0, self.limit_ms - self.elapsed_ms)

    @property
    def exhausted(self) -> bool:
        return self.elapsed_ms >= self.limit_ms


class CursorCodec:
    """Opaque, process-local cursors with expiry, validation, and bounded state."""

    def __init__(self, max_entries: int = 256, ttl_seconds: int = 900, max_state_bytes: int = 16_384) -> None:
        self._items: OrderedDict[str, tuple[float, str, str, dict[str, Any]]] = OrderedDict()
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._max_state_bytes = max_state_bytes

    def create(self, kind: str, fingerprint: str, state: dict[str, Any]) -> str:
        try:
            state_size = len(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Cursor state is not serializable") from exc
        if state_size > self._max_state_bytes:
            raise ValueError("Cursor state exceeds the safe size limit")
        self._purge()
        token = secrets.token_urlsafe(18)
        self._items[token] = (time.monotonic(), kind, fingerprint, state)
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)
        return token

    def read(self, token: str | None, kind: str, fingerprint: str) -> dict[str, Any]:
        if not token or len(token) > 128:
            raise ValueError("Invalid or stale continuation cursor")
        self._purge()
        item = self._items.get(token)
        if item is None or item[1] != kind or item[2] != fingerprint:
            raise ValueError("Invalid or stale continuation cursor")
        self._items.move_to_end(token)
        return item[3]

    def _purge(self) -> None:
        cutoff = time.monotonic() - self._ttl_seconds
        for token in [key for key, item in self._items.items() if item[0] < cutoff]:
            self._items.pop(token, None)


class SourceFileIndex:
    """A metadata-only source index that builds incrementally within a budget."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.entries: dict[str, dict[str, Any]] = {}
        self.ready = False
        self.generation = 0
        self.build_revision = 0
        self.last_refresh = 0.0
        self.refresh_interval_seconds = SOURCE_INDEX_TTL_SECONDS
        self.refresh_count = 0
        self._pending_entries: dict[str, dict[str, Any]] | None = None
        self._walk_stack: list[dict[str, Any]] = []

    def invalidate(self) -> None:
        self.ready = False
        self.entries = {}
        self._pending_entries = None
        self._walk_stack = []
        self.build_revision += 1

    def ensure_ready(self, budget: OperationBudget) -> bool:
        if self.ready and time.monotonic() - self.last_refresh < self.refresh_interval_seconds:
            return True
        if self._pending_entries is None:
            self._begin_refresh()
        self._advance_refresh(budget)
        return self.ready

    def paths(self) -> list[str]:
        return sorted(self.entries)

    def _begin_refresh(self) -> None:
        self.ready = False
        self.build_revision += 1
        self._pending_entries = {}
        roots = [name for name in DEFAULT_SOURCE_ROOTS if (self.repo_root / name).is_dir()]
        self._walk_stack = [{"directory": root, "position": 0} for root in reversed(roots)]

    def _advance_refresh(self, budget: OperationBudget) -> None:
        assert self._pending_entries is not None
        policy = RepositoryScanPolicy(include_globs=DEFAULT_SOURCE_GLOBS)
        while self._walk_stack and not budget.exhausted:
            frame = self._walk_stack[-1]
            relative_directory = str(frame["directory"])
            directory = self.repo_root / relative_directory
            if "children" not in frame:
                try:
                    frame["children"] = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
                except OSError:
                    self._walk_stack.pop()
                    continue
            children = frame["children"]
            position = int(frame["position"])
            if position >= len(children):
                self._walk_stack.pop()
                continue
            child = children[position]
            frame["position"] = position + 1
            try:
                relative = child.relative_to(self.repo_root).as_posix()
                if child.is_symlink():
                    resolved = child.resolve()
                    if resolved != self.repo_root and self.repo_root not in resolved.parents:
                        continue
                    if child.is_dir():
                        continue
                if child.is_dir():
                    if not policy.should_skip_directory(relative):
                        self._walk_stack.append({"directory": relative, "position": 0})
                    continue
                if not child.is_file() or policy.should_skip_file(relative, allow_included_type=policy.matches_include(relative)):
                    continue
                if not policy.matches_include(relative):
                    continue
                stat = child.stat()
                self._pending_entries[relative] = {
                    "path": relative,
                    "size_bytes": stat.st_size,
                    "modified_time": stat.st_mtime,
                    "extension": child.suffix.lower(),
                    "category": classify_source_path(relative),
                }
            except OSError:
                continue
        if self._walk_stack:
            return
        current = self._pending_entries
        self._pending_entries = None
        if current != self.entries:
            self.entries = current
            self.generation += 1
        self.ready = True
        self.last_refresh = time.monotonic()
        self.refresh_count += 1


@dataclass
class _ToolMetric:
    calls: int = 0
    success: int = 0
    errors: int = 0
    timeouts: int = 0
    durations_ms: deque[float] | None = None
    latest_error: str | None = None

    def __post_init__(self) -> None:
        if self.durations_ms is None:
            self.durations_ms = deque(maxlen=200)


class RuntimeState:
    def __init__(self, repo_root: Path) -> None:
        self.started = time.monotonic()
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.repo_root = repo_root
        self.cursors = CursorCodec()
        self.source_index = SourceFileIndex(repo_root)
        self.metrics: dict[str, _ToolMetric] = defaultdict(_ToolMetric)
        self.active_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0

    @contextmanager
    def measure(self, tool: str) -> Iterator[None]:
        metric = self.metrics[tool]
        metric.calls += 1
        self.active_requests += 1
        started = time.perf_counter()
        try:
            yield
        except Exception as exc:
            metric.errors += 1
            if isinstance(exc, TimeoutError):
                metric.timeouts += 1
            metric.latest_error = f"{type(exc).__name__}: {str(exc)[:240]}"
            raise
        else:
            metric.success += 1
        finally:
            metric.durations_ms.append((time.perf_counter() - started) * 1000)
            self.active_requests -= 1

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "server_version": SERVER_VERSION,
            "implementation_build_id": IMPLEMENTATION_BUILD_ID,
            "implementation_path": str(Path(__file__).resolve().parent),
            "process_started_at": self.started_at,
            "server_uptime_ms": int((time.monotonic() - self.started) * 1000),
            "repository_root": str(self.repo_root),
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "index": {
                "ready": self.source_index.ready,
                "indexed_file_count": len(self.source_index.entries),
                "generation": self.source_index.generation,
                "refresh_count": self.source_index.refresh_count,
            },
            "active_request_count": self.active_requests,
            "recent_timeout_count": sum(metric.timeouts for metric in self.metrics.values()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def diagnostics(self) -> dict[str, Any]:
        tools: dict[str, Any] = {}
        for name, metric in sorted(self.metrics.items()):
            values = sorted(metric.durations_ms or [])
            average = round(sum(values) / len(values), 2) if values else 0.0
            p50 = values[int((len(values) - 1) * 0.50)] if values else 0.0
            p95 = values[int((len(values) - 1) * 0.95)] if values else 0.0
            tools[name] = {
                "call_count": metric.calls,
                "success_count": metric.success,
                "error_count": metric.errors,
                "timeout_count": metric.timeouts,
                "average_duration_ms": average,
                "p50_duration_ms": round(p50, 2),
                "p95_duration_ms": round(p95, 2),
                "latest_error": metric.latest_error,
            }
        return {
            "tools": tools,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "source_index_refresh_count": self.source_index.refresh_count,
        }


_RUNTIMES: dict[str, RuntimeState] = {}


def get_runtime(repo_root: Path) -> RuntimeState:
    key = os.fspath(repo_root.resolve())
    if key not in _RUNTIMES:
        _RUNTIMES[key] = RuntimeState(repo_root.resolve())
    return _RUNTIMES[key]
