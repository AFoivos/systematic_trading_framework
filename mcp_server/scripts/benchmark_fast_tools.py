"""Synthetic-only benchmark for the fast repository-inspection MCP tools.

It creates a temporary Git repository and never reads project market data, logs,
reports, artifacts, or strategy configurations.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


MCP_ROOT = Path(__file__).resolve().parents[1]
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))

from repo_mcp.config import ServerConfig
from repo_mcp.git_tools import get_code_review_bundle, get_repo_snapshot, list_changed_paths, mcp_diagnostics, mcp_health
from repo_mcp.repository import read_files, search_code, search_source


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _config(root: Path) -> ServerConfig:
    return ServerConfig(repo_root=root, host="127.0.0.1", port=0, max_read_bytes=1_000_000, max_search_results=200, max_tree_entries=5_000, script_timeout_seconds=30, approved_python_scripts=())


def _summary(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    items = result.get("items", result.get("results", result.get("files", [])))
    return {
        "result_count": len(items) if isinstance(items, list) else None,
        "files_scanned": result.get("scanned_files"),
        "status": result.get("status"),
        "truncated": result.get("truncated"),
    }


def _measure(name: str, operation: Callable[[], Any]) -> tuple[dict[str, Any], Any]:
    started = time.perf_counter()
    result = operation()
    return {"tool": name, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), **_summary(result)}, result


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mcp-fast-benchmark-") as temporary:
        root = Path(temporary) / "repo"
        for directory in ("src", "src/models", "tests", "config", "scripts", "docs", "models", ".venv312", ".venv_map", "data", "logs"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        for number in range(1_000):
            category = "src" if number < 800 else "tests" if number < 950 else "config"
            suffix = ".py" if category != "config" else ".yaml"
            (root / category / f"module_{number:04d}{suffix}").write_text(f"# synthetic source {number}\nVALUE_{number} = 'benchmark-root-needle'\n", encoding="utf-8")
        (root / "src/models/registry.py").write_text("MODEL_REGISTRY = 'model-only-needle'\n", encoding="utf-8")
        (root / "src/legacy_pagination.py").write_text("\n".join("LEGACY = 'legacy-page-needle'" for _ in range(8)) + "\n", encoding="utf-8")
        (root / "models/checkpoint.py").write_text("SHOULD_NOT_APPEAR = 'model-only-needle'\n", encoding="utf-8")
        (root / ".venv312/lib.py").write_text("SHOULD_NOT_APPEAR = 'model-only-needle'\n", encoding="utf-8")
        (root / ".venv_map/lib.py").write_text("SHOULD_NOT_APPEAR = 'model-only-needle'\n", encoding="utf-8")
        for number in range(50):
            (root / "data" / f"placeholder_{number}.csv").write_text("timestamp,value\n", encoding="utf-8")
            (root / "logs" / f"placeholder_{number}.log").write_text("synthetic log\n", encoding="utf-8")

        _git(root, "init")
        (root / ".gitignore").write_text(
            "/src/module_*\n/tests/module_*\n/config/module_*\n/data/\n/logs/\n/models/\n/.venv*\n",
            encoding="utf-8",
        )
        for number in range(25):
            (root / "src" / f"review_{number:04d}.py").write_text(f"# synthetic review file {number}\nVALUE_{number} = 'benchmark-root-needle-new'\n", encoding="utf-8")
        for number in range(25, 50):
            (root / "src" / f"untracked_{number:04d}.py").write_text("VALUE = 'benchmark-root-needle-new'\n", encoding="utf-8")

        config = _config(root)
        results: list[dict[str, Any]] = []
        health_cold, _ = _measure("mcp_health cold", lambda: mcp_health(config))
        results.append(health_cold)
        health_warm, _ = _measure("mcp_health warm", lambda: mcp_health(config))
        results.append(health_warm)

        def first_source_page(query: str) -> dict[str, Any]:
            response = search_source(config, query)
            while not response["items"] and response["next_cursor"]:
                response = search_source(config, query, cursor=response["next_cursor"])
            return response

        cold, _cold_payload = _measure("search_source cold root", lambda: first_source_page("benchmark-root-needle"))
        results.append(cold)
        warm, warm_payload = _measure("search_source warm root", lambda: search_source(config, "benchmark-root-needle"))
        results.append(warm)
        models, models_payload = _measure("search_source src/models positive", lambda: search_source(config, "model-only-needle"))
        results.append(models)

        def legacy_pages() -> dict[str, Any]:
            response = search_code(config, "legacy-page-needle", root=".", max_results=2)
            results_by_page = list(response["results"])
            while response["next_cursor"]:
                response = search_code(config, "legacy-page-needle", root=".", max_results=2, cursor=response["next_cursor"])
                results_by_page.extend(response["results"])
            return {"results": results_by_page, "truncated": False}

        legacy, _ = _measure("search_code legacy pagination", legacy_pages)
        results.append(legacy)
        no_match, _ = _measure("search_source full-scan no-match", lambda: search_source(config, "definitely-no-synthetic-match"))
        results.append(no_match)
        bulk, _ = _measure("read_files (10 files)", lambda: read_files(config, [f"src/module_{number:04d}.py" for number in range(10)]))
        results.append(bulk)
        changed, _ = _measure("list_changed_paths", lambda: list_changed_paths(config))
        results.append(changed)
        snapshot, _ = _measure("get_repo_snapshot", lambda: get_repo_snapshot(config))
        results.append(snapshot)
        bundle, _ = _measure("get_code_review_bundle", lambda: get_code_review_bundle(config))
        results.append(bundle)
        print(json.dumps({
            "synthetic_source_files": 1_002,
            "changed_or_untracked_source_files": 50,
            "results": results,
            "policy_checks": {
                "src_models_included": "src/models/registry.py" in {item["path"] for item in models_payload.get("items", [])},
                "root_models_excluded": "models/checkpoint.py" not in {item["path"] for item in models_payload.get("items", [])},
                "venv312_excluded": not any(".venv312" in item["path"] for item in models_payload.get("items", [])),
                "venv_map_excluded": not any(".venv_map" in item["path"] for item in models_payload.get("items", [])),
            },
            "diagnostics": mcp_diagnostics(config),
        }, indent=2))


if __name__ == "__main__":
    main()
