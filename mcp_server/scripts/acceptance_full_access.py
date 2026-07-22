from __future__ import annotations

"""Live MCP protocol acceptance test for repository write and execution tools."""

import asyncio
import json
import os
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


ENDPOINT = os.environ.get("MCP_ACCEPTANCE_ENDPOINT", "http://127.0.0.1:8765/mcp")
TEST_PATH = "tmp/mcp_write_test.txt"
IMPORT_SOURCE = os.environ.get("MCP_ACCEPTANCE_IMPORT_SOURCE")
IMPORT_DESTINATION = "tmp/mcp_import_test.py"
CONFIRMATION = "The user explicitly requested the documented MCP acceptance test."
REQUIRED_TOOLS = {
    "write_file",
    "apply_patch",
    "import_local_file",
    "run_command",
    "run_python",
}


def _payload(result: Any) -> dict[str, Any]:
    if getattr(result, "isError", False):
        texts = [getattr(item, "text", "") for item in result.content]
        raise RuntimeError("MCP tool returned an error: " + "\n".join(texts))
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        if set(structured) == {"result"} and isinstance(structured["result"], dict):
            return structured["result"]
        return structured
    for item in result.content:
        text = getattr(item, "text", None)
        if text:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    raise RuntimeError("MCP tool response did not contain a JSON object")


async def _call(session: ClientSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return _payload(await session.call_tool(name, arguments=arguments))


async def main() -> None:
    summary: dict[str, Any] = {"endpoint": ENDPOINT}
    async with streamablehttp_client(ENDPOINT) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            discovery = await session.list_tools()
            names = sorted(tool.name for tool in discovery.tools)
            schemas = {tool.name: tool.inputSchema for tool in discovery.tools}
            missing = sorted(REQUIRED_TOOLS - set(names))
            if missing:
                raise AssertionError(f"MCP discovery is missing required tools: {missing}")
            summary["discovery"] = {
                "tool_count": len(names),
                "required_tools": sorted(REQUIRED_TOOLS),
                "missing": missing,
                "schema_properties": {
                    name: sorted(schemas[name].get("properties", {}))
                    for name in sorted(REQUIRED_TOOLS)
                },
            }

            health = await _call(session, "mcp_health", {})
            summary["health"] = {
                "server_version": health.get("server_version"),
                "implementation_build_id": health.get("implementation_build_id"),
                "status": health.get("status"),
            }

            try:
                written = await _call(
                    session,
                    "write_file",
                    {
                        "path": TEST_PATH,
                        "content": "mcp write access works\n",
                        "create_parent_dirs": True,
                    },
                )
                if not written.get("success"):
                    raise AssertionError(f"write_file failed: {written}")

                read_back = await _call(session, "read_file", {"path": TEST_PATH})
                if read_back.get("text", "").strip() != "mcp write access works":
                    raise AssertionError(f"Unexpected read-back payload: {read_back}")

                patch = """diff --git a/tmp/mcp_write_test.txt b/tmp/mcp_write_test.txt
--- a/tmp/mcp_write_test.txt
+++ b/tmp/mcp_write_test.txt
@@ -1 +1 @@
-mcp write access works
+mcp patch access works
"""
                patched = await _call(session, "apply_patch", {"patch": patch})
                if not patched.get("success"):
                    raise AssertionError(f"apply_patch failed: {patched}")

                patched_read = await _call(session, "read_file", {"path": TEST_PATH})
                if patched_read.get("text", "").strip() != "mcp patch access works":
                    raise AssertionError(f"Unexpected patched payload: {patched_read}")

                executed = await _call(
                    session,
                    "run_command",
                    {
                        "command": ["python", "-c", "print('mcp execution works')"],
                        "confirmation": CONFIRMATION,
                    },
                )
                if executed.get("exit_code") != 0 or executed.get("stdout", "").strip() != "mcp execution works":
                    raise AssertionError(f"run_command failed: {executed}")

                summary["write"] = {
                    "action": written.get("action"),
                    "new_sha256": written.get("new_sha256"),
                    "read_back": read_back.get("text", "").strip(),
                }
                summary["patch"] = {
                    "changed_files": patched.get("changed_files"),
                    "read_back": patched_read.get("text", "").strip(),
                }
                summary["execution"] = {
                    "exit_code": executed.get("exit_code"),
                    "stdout": executed.get("stdout", "").strip(),
                    "timed_out": executed.get("timed_out"),
                }
            finally:
                deleted = await _call(
                    session,
                    "delete_path",
                    {"path": TEST_PATH, "confirmation": CONFIRMATION},
                )
                if not deleted.get("success") and deleted.get("error", {}).get("code") != "path_not_found":
                    raise AssertionError(f"delete_path failed: {deleted}")
                summary["delete"] = {
                    "deleted": deleted.get("deleted"),
                    "deleted_files": deleted.get("deleted_files"),
                }

            status = await _call(session, "git_status", {})
            porcelain = status.get("porcelain", "")
            if TEST_PATH in porcelain:
                raise AssertionError(f"Acceptance artifact remains in git status: {porcelain}")
            summary["git_status"] = {
                "acceptance_artifact_present": False,
                "clean": status.get("clean"),
            }

            if IMPORT_SOURCE:
                try:
                    imported = await _call(
                        session,
                        "import_local_file",
                        {
                            "source_path": IMPORT_SOURCE,
                            "destination_path": IMPORT_DESTINATION,
                        },
                    )
                    executed_import = await _call(
                        session,
                        "run_python",
                        {
                            "script_path": IMPORT_DESTINATION,
                            "confirmation": CONFIRMATION,
                        },
                    )
                    if not imported.get("success") or executed_import.get("exit_code") != 0:
                        raise AssertionError(
                            f"Live import/run verification failed: {imported}, {executed_import}"
                        )
                    summary["import_and_run_python"] = {
                        "source_sha256": imported.get("source_sha256"),
                        "destination_sha256": imported.get("destination_sha256"),
                        "exit_code": executed_import.get("exit_code"),
                        "stdout": executed_import.get("stdout", "").strip(),
                    }
                finally:
                    await _call(
                        session,
                        "delete_path",
                        {"path": IMPORT_DESTINATION, "confirmation": CONFIRMATION},
                    )
                final_status = await _call(session, "git_status", {})
                if IMPORT_DESTINATION in final_status.get("porcelain", ""):
                    raise AssertionError("Imported acceptance artifact remains in git status")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
