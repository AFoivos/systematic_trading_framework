from __future__ import annotations

"""Structured, payload-safe logging for the Streamable HTTP MCP boundary."""

import functools
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


LOGGER = logging.getLogger("repo_mcp.structured")
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def structured_logging_enabled() -> bool:
    return os.environ.get("MCP_STRUCTURED_LOGGING", "0").strip().lower() in TRUE_VALUES


def configure_structured_logger() -> None:
    """Keep each JSON event on one stderr line, independent of MCP's rich logger."""
    if not any(getattr(handler, "_repo_mcp_structured", False) for handler in LOGGER.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._repo_mcp_structured = True
        LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def emit_event(event: str, **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        **fields,
    }
    LOGGER.info(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))


def _rpc_metadata(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    metadata: dict[str, Any] = {}
    method = payload.get("method")
    if isinstance(method, str):
        metadata["rpc_method"] = method
    request_id = payload.get("id")
    if isinstance(request_id, (str, int)):
        metadata["rpc_id"] = request_id
    params = payload.get("params")
    if method == "tools/call" and isinstance(params, dict) and isinstance(params.get("name"), str):
        metadata["tool"] = params["name"]
    return metadata


class StructuredHTTPLoggingMiddleware:
    """Log the HTTP lifecycle without recording headers, arguments, or response bodies."""

    def __init__(self, app: Any, *, enabled: bool = True, max_inspected_body_bytes: int = 1_048_576) -> None:
        self.app = app
        self.enabled = enabled
        self.max_inspected_body_bytes = max_inspected_body_bytes

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[dict[str, Any]]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if not self.enabled or scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        metadata: dict[str, Any] = {}
        body_parts: list[bytes] = []
        inspected_bytes = 0
        body_complete = False
        response_status: int | None = None
        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))
        client = scope.get("client")
        client_host = client[0] if isinstance(client, (list, tuple)) and client else None
        emit_event("http_request_enter", http_method=method, path=path, client_host=client_host)

        async def logged_receive() -> dict[str, Any]:
            nonlocal inspected_bytes, body_complete
            message = await receive()
            if message.get("type") == "http.request" and not body_complete:
                chunk = message.get("body", b"")
                if isinstance(chunk, bytes) and inspected_bytes <= self.max_inspected_body_bytes:
                    inspected_bytes += len(chunk)
                    if inspected_bytes <= self.max_inspected_body_bytes:
                        body_parts.append(chunk)
                    else:
                        body_parts.clear()
                if not message.get("more_body", False):
                    body_complete = True
                    if body_parts:
                        metadata.update(_rpc_metadata(b"".join(body_parts)))
                    if metadata.get("rpc_method") == "initialize":
                        emit_event("mcp_initialization_start", path=path, rpc_id=metadata.get("rpc_id"))
            return message

        async def logged_send(message: dict[str, Any]) -> None:
            nonlocal response_status
            message_type = message.get("type")
            if message_type == "http.response.start":
                response_status = int(message.get("status", 0))
                emit_event(
                    "http_response_start",
                    http_method=method,
                    path=path,
                    status=response_status,
                    **metadata,
                )
            await send(message)
            if message_type == "http.response.body" and not message.get("more_body", False):
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                if metadata.get("rpc_method") == "initialize":
                    emit_event(
                        "mcp_initialization_complete",
                        path=path,
                        status=response_status,
                        elapsed_ms=elapsed_ms,
                        rpc_id=metadata.get("rpc_id"),
                    )
                emit_event(
                    "http_response_sent",
                    http_method=method,
                    path=path,
                    status=response_status,
                    elapsed_ms=elapsed_ms,
                    **metadata,
                )

        try:
            await self.app(scope, logged_receive, logged_send)
        except Exception as exc:
            emit_event(
                "http_request_exception",
                http_method=method,
                path=path,
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                exception_type=type(exc).__name__,
                error=str(exc)[:500],
                **metadata,
            )
            LOGGER.exception("MCP HTTP request failed")
            raise


def instrument_tool_manager(tool_manager: Any, *, enabled: bool) -> None:
    """Wrap the single FastMCP execution boundary once, preserving tool behavior."""
    if not enabled or getattr(tool_manager, "_repo_mcp_instrumented", False):
        return
    original_call_tool = tool_manager.call_tool

    @functools.wraps(original_call_tool)
    async def logged_call_tool(name: str, arguments: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        emit_event("mcp_tool_start", tool=name, argument_names=sorted(arguments))
        try:
            result = await original_call_tool(name, arguments, *args, **kwargs)
        except Exception as exc:
            emit_event(
                "mcp_tool_exception",
                tool=name,
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                exception_type=type(exc).__name__,
                error=str(exc)[:500],
            )
            LOGGER.exception("MCP tool failed: %s", name)
            raise
        emit_event(
            "mcp_tool_complete",
            tool=name,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return result

    tool_manager.call_tool = logged_call_tool
    tool_manager._repo_mcp_instrumented = True
