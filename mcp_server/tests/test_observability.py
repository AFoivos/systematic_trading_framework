from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from repo_mcp.observability import StructuredHTTPLoggingMiddleware, instrument_tool_manager


def _events(caplog: Any) -> list[dict[str, Any]]:
    return [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "repo_mcp.structured" and record.message.startswith("{")
    ]


def test_http_logging_records_initialize_lifecycle_without_body(caplog: Any) -> None:
    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"secret response", "more_body": False})

    request_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "test", "version": "1"}, "secret": "not-logged"},
        }
    ).encode()
    received = False

    async def receive() -> dict[str, Any]:
        nonlocal received
        assert not received
        received = True
        return {"type": "http.request", "body": request_body, "more_body": False}

    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    caplog.set_level(logging.INFO, logger="repo_mcp.structured")
    middleware = StructuredHTTPLoggingMiddleware(app)
    scope = {"type": "http", "method": "POST", "path": "/mcp", "client": ("127.0.0.1", 1234)}
    asyncio.run(middleware(scope, receive, send))

    events = _events(caplog)
    assert [event["event"] for event in events] == [
        "http_request_enter",
        "mcp_initialization_start",
        "http_response_start",
        "mcp_initialization_complete",
        "http_response_sent",
    ]
    rendered = "\n".join(record.message for record in caplog.records)
    assert "not-logged" not in rendered
    assert "secret response" not in rendered
    assert events[-1]["status"] == 200


def test_tool_manager_instrumentation_logs_names_not_values(caplog: Any) -> None:
    class FakeToolManager:
        async def call_tool(self, name: str, arguments: dict[str, Any], *args: Any, **kwargs: Any) -> dict[str, bool]:
            return {"ok": True}

    manager = FakeToolManager()
    caplog.set_level(logging.INFO, logger="repo_mcp.structured")
    instrument_tool_manager(manager, enabled=True)
    result = asyncio.run(manager.call_tool("list_directory", {"path": "secret-path", "max_entries": 5}))

    assert result == {"ok": True}
    events = _events(caplog)
    assert [event["event"] for event in events] == ["mcp_tool_start", "mcp_tool_complete"]
    assert events[0]["argument_names"] == ["max_entries", "path"]
    assert "secret-path" not in "\n".join(record.message for record in caplog.records)
