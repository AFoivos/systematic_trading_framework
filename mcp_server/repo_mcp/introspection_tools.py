from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .config import ServerConfig
from .git_tools import git_current_branch, git_diff, git_log, git_status
from .project_tools import list_experiment_runs
from .repository import list_directory
from .security import PathSecurityError, is_probably_text, read_text_limited, resolve_repo_path, to_repo_relative


REGISTRY_FILES = {
    "feature": "src/features/registry.py",
    "signal": "src/signals/registry.py",
    "target": "src/targets/registry.py",
    "model": "src/models/registry.py",
    "pipeline": "src/pipelines/registry.py",
}
DOC_CATALOGS = {
    "feature": ["docs/catalog/features.md"],
    "signal": ["docs/catalog/signals.md"],
    "target": ["docs/catalog/targets.md"],
    "model": ["docs/models.md", "docs/catalog/models.md"],
    "component": ["docs/component_inventory_gr.md"],
}
SUSPICIOUS_FEATURE_PATTERNS = re.compile(
    r"(label|target|fwd|future|barrier|hit|exit|realized|trade_r|mfe|mae|event_ret|oriented_r)",
    re.IGNORECASE,
)
RAW_OHLC = {"open", "high", "low", "close", "ohlc4", "hl2", "hlc3"}
CONFIRM_TESTS = "RUN_APPROVED_REPOSITORY_TESTS"


def _safe_rel_path(config: ServerConfig, path: str, suffixes: set[str] | None = None) -> Path:
    resolved = resolve_repo_path(config.repo_root, path)
    if suffixes and resolved.suffix.lower() not in suffixes:
        raise ValueError(f"Unsupported file suffix for {path}; expected one of {sorted(suffixes)}")
    return resolved


def _read_text(config: ServerConfig, path: Path) -> tuple[str, bool]:
    return read_text_limited(path, config.max_read_bytes)


def _module_to_path(module: str) -> str | None:
    if not module.startswith("src."):
        return None
    return f"{module.replace('.', '/')}.py"


def _registry_module_prefix(registry_path: str) -> str:
    return registry_path.removesuffix("/registry.py").replace("/", ".")


def _import_map(tree: ast.AST, registry_path: str) -> dict[str, dict[str, str]]:
    imports: dict[str, dict[str, str]] = {}
    base = _registry_module_prefix(registry_path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if node.level:
            module = f"{base}.{module}" if module else base
        for alias in node.names:
            local = alias.asname or alias.name
            imports[local] = {
                "imported_name": alias.name,
                "module": module,
                "path": _module_to_path(module) or "",
            }
    return imports


def _callable_info(expr: ast.AST, imports: dict[str, dict[str, str]]) -> dict[str, Any]:
    if isinstance(expr, ast.Name):
        info = dict(imports.get(expr.id, {}))
        info["callable_name"] = expr.id
        info.setdefault("path", "")
        return info
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "lazy_callable":
        if len(expr.args) >= 2 and all(isinstance(arg, ast.Constant) for arg in expr.args[:2]):
            module = str(expr.args[0].value)
            callable_name = str(expr.args[1].value)
            return {"callable_name": callable_name, "module": module, "path": _module_to_path(module) or ""}
    if isinstance(expr, ast.Attribute):
        return {"callable_name": expr.attr, "path": ""}
    return {"callable_name": ast.unparse(expr) if hasattr(ast, "unparse") else "", "path": ""}


def _extract_tuple_entries(value: ast.AST, imports: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not isinstance(value, (ast.Tuple, ast.List)):
        return entries
    for item in value.elts:
        if not isinstance(item, (ast.Tuple, ast.List)) or len(item.elts) < 2:
            continue
        name_node = item.elts[0]
        if not isinstance(name_node, ast.Constant) or not isinstance(name_node.value, str):
            continue
        info = _callable_info(item.elts[1], imports)
        entries.append({"name": name_node.value, **info})
    return entries


def _extract_build_registry_items(call: ast.Call) -> list[ast.AST]:
    items: list[ast.AST] = []
    for arg in call.args:
        if isinstance(arg, (ast.Tuple, ast.List)):
            items.extend(arg.elts)
    return items


def _parse_registry_file(config: ServerConfig, registry_type: str, registry_path: str) -> dict[str, Any]:
    path = resolve_repo_path(config.repo_root, registry_path)
    if not path.exists():
        return {
            "registry_type": registry_type,
            "registry_path": registry_path,
            "exists": False,
            "component_names": [],
            "components": [],
            "component_count": 0,
            "deprecated_or_legacy_names": [],
            "parse_warnings": ["registry file missing"],
        }
    text, truncated = _read_text(config, path)
    warnings: list[str] = ["registry text truncated"] if truncated else []
    components: list[dict[str, Any]] = []
    deprecated: set[str] = set()
    try:
        tree = ast.parse(text)
        imports = _import_map(tree, registry_path)
        assigned_entries: dict[str, list[dict[str, Any]]] = {}
        legacy_vars: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
                value = node.value
            else:
                continue
            if any(re.search(r"(legacy|deprecated|compatibility|alias)", target, re.I) for target in targets):
                legacy_vars.update(targets)
            for target in targets:
                entries = _extract_tuple_entries(value, imports) if value is not None else []
                if entries:
                    assigned_entries[target] = entries
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            else:
                targets = []
            for target in targets:
                if target.endswith("_COMPONENTS") or "ALIASES" in target or "COMPATIBILITY" in target:
                    components.extend({**entry, "source_variable": target} for entry in assigned_entries.get(target, []))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "build_registry":
                for item in _extract_build_registry_items(node):
                    components.extend(_extract_tuple_entries(ast.Tuple(elts=[item], ctx=ast.Load()), imports))
        for entry in components:
            source = str(entry.get("source_variable", ""))
            if re.search(r"(legacy|deprecated|compatibility|alias)", source, re.I):
                deprecated.add(entry["name"])
    except SyntaxError as exc:
        warnings.append(f"AST parse failed: {exc}")
        components = []
    if not components:
        for match in re.finditer(r'\(\s*["\']([^"\']+)["\']\s*,\s*([A-Za-z_][\w.]*)', text):
            components.append({"name": match.group(1), "callable_name": match.group(2), "path": "", "source_variable": "regex"})
        if components:
            warnings.append("used regex fallback for registry entries")
    unique: dict[str, dict[str, Any]] = {}
    for component in components:
        unique.setdefault(component["name"], component)
    return {
        "registry_type": registry_type,
        "registry_path": registry_path,
        "exists": True,
        "component_names": sorted(unique),
        "components": [unique[name] for name in sorted(unique)],
        "component_count": len(unique),
        "deprecated_or_legacy_names": sorted(deprecated),
        "parse_warnings": warnings,
    }


def registry_inventory(config: ServerConfig) -> dict[str, Any]:
    registries = [_parse_registry_file(config, kind, path) for kind, path in REGISTRY_FILES.items()]
    return {"registries": registries, "parse_warnings": [w for reg in registries for w in reg["parse_warnings"]]}


def repo_overview_summary(config: ServerConfig) -> dict[str, Any]:
    key_folders = ["src", "config", "docs", "tests", "logs", "mcp_server"]
    registry_status = {
        kind: {"path": path, "exists": resolve_repo_path(config.repo_root, path).is_file()}
        for kind, path in REGISTRY_FILES.items()
    }
    warnings = [f"missing registry file: {item['path']}" for item in registry_status.values() if not item["exists"]]
    warnings.extend(f"missing key folder: {folder}" for folder in key_folders if not resolve_repo_path(config.repo_root, folder).is_dir())
    top = list_directory(config, ".", recursive=False, max_entries=80)
    runs = list_experiment_runs(config, "logs", max_runs=25)
    return {
        "current_git_branch": git_current_branch(config).get("branch"),
        "git_status_summary": git_status(config).get("status", ""),
        "recent_commit_summaries": git_log(config, max_count=5).get("commits", []),
        "top_level_repo_folders": [e["path"] for e in top["entries"] if e["type"] == "directory"],
        "key_folders": {folder: resolve_repo_path(config.repo_root, folder).is_dir() for folder in key_folders},
        "registry_files": registry_status,
        "recent_experiment_run_count": len(runs.get("runs", [])),
        "notable_warnings": warnings,
    }


def _find_definition(config: ServerConfig, implementation_path: str, callable_name: str) -> dict[str, Any]:
    if not implementation_path or not callable_name:
        return {}
    path = resolve_repo_path(config.repo_root, implementation_path)
    if not path.is_file():
        return {"warning": "implementation file not found"}
    text, _ = _read_text(config, path)
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"warning": f"implementation AST parse failed: {exc}"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == callable_name:
            signature = ""
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = ast.unparse(node.args) if hasattr(ast, "unparse") else ""
                signature = f"{node.name}({args})"
            return {
                "line": node.lineno,
                "signature": signature,
                "docstring_excerpt": (ast.get_docstring(node) or "")[:700],
            }
    return {"warning": "callable definition not found by AST"}


def _scan_text_refs(config: ServerConfig, roots: list[str], needles: list[str], suffixes: set[str], max_results: int = 40) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    lowered = [needle.lower() for needle in needles if needle]
    for root in roots:
        root_path = resolve_repo_path(config.repo_root, root)
        if not root_path.exists() or not root_path.is_dir():
            continue
        for item in sorted(root_path.rglob("*"), key=lambda p: p.as_posix()):
            if len(results) >= max_results:
                return results
            if not item.is_file() or item.suffix.lower() not in suffixes or not is_probably_text(item):
                continue
            rel = to_repo_relative(config.repo_root, item)
            text, _ = _read_text(config, item)
            haystack = text.lower()
            if not any(needle in haystack for needle in lowered):
                continue
            lines = text.splitlines()
            first = next((i for i, line in enumerate(lines, 1) if any(needle in line.lower() for needle in lowered)), None)
            results.append({"path": rel, "line": first})
    return results


def inspect_component(config: ServerConfig, name: str, component_type: str | None = None) -> dict[str, Any]:
    inventory = registry_inventory(config)["registries"]
    matches: list[dict[str, Any]] = []
    for registry in inventory:
        if component_type and registry["registry_type"] != component_type:
            continue
        for component in registry.get("components", []):
            if component["name"] == name:
                impl = component.get("path", "")
                definition = _find_definition(config, impl, component.get("callable_name", ""))
                matches.append(
                    {
                        "matched_registry_type": registry["registry_type"],
                        "registry_path": registry["registry_path"],
                        "implementation_callable_name": component.get("callable_name"),
                        "implementation_file_path": impl or None,
                        "definition": definition,
                    }
                )
    needles = [name]
    for match in matches:
        if match.get("implementation_callable_name"):
            needles.append(str(match["implementation_callable_name"]))
        if match.get("implementation_file_path"):
            needles.append(Path(str(match["implementation_file_path"])).stem)
    warnings: list[str] = []
    if not matches:
        warnings.append("component not found in canonical registries")
    if len(matches) > 1 and component_type is None:
        warnings.append("component name is ambiguous across registry types")
    deprecated = {
        entry
        for registry in inventory
        for entry in registry.get("deprecated_or_legacy_names", [])
        if entry == name
    }
    if deprecated:
        warnings.append("component is marked legacy/deprecated/compatibility in registry")
    return {
        "name": name,
        "matches": matches,
        "related_docs_references": _scan_text_refs(config, ["docs"], needles, {".md"}, max_results=25),
        "related_tests": _scan_text_refs(config, ["tests", "mcp_server/tests"], needles, {".py"}, max_results=25),
        "yaml_references": _scan_text_refs(config, ["config"], needles, {".yaml", ".yml"}, max_results=40),
        "warnings": warnings,
    }


def _doc_names(config: ServerConfig, path: str) -> tuple[set[str], list[str]]:
    warnings: list[str] = []
    doc_path = resolve_repo_path(config.repo_root, path)
    if not doc_path.exists():
        return set(), [f"missing doc file: {path}"]
    text, truncated = _read_text(config, doc_path)
    if truncated:
        warnings.append(f"doc file truncated: {path}")
    names = set(re.findall(r"`([a-zA-Z_][a-zA-Z0-9_]*)`", text))
    names.update(re.findall(r"^\s*[-*]\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", text, flags=re.MULTILINE))
    names.update(re.findall(r"^#+\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", text, flags=re.MULTILINE))
    return names, warnings


def docs_registry_sync_check(config: ServerConfig) -> dict[str, Any]:
    inventory = {reg["registry_type"]: set(reg["component_names"]) for reg in registry_inventory(config)["registries"]}
    missing_from_docs: dict[str, list[str]] = {}
    missing_from_registry: dict[str, list[str]] = {}
    warnings: list[str] = []
    for kind, paths in DOC_CATALOGS.items():
        docs: set[str] = set()
        for path in paths:
            found, path_warnings = _doc_names(config, path)
            docs.update(found)
            warnings.extend(path_warnings)
        if kind == "component":
            registry_names = set().union(*inventory.values()) if inventory else set()
        else:
            registry_names = inventory.get(kind, set())
        if registry_names:
            missing_from_docs[kind] = sorted(registry_names - docs)
        if docs:
            missing_from_registry[kind] = sorted(name for name in docs - registry_names if "_" in name)
    return {
        "registry_names_missing_from_docs": missing_from_docs,
        "doc_names_missing_from_registry": missing_from_registry,
        "possible_legacy_or_deprecated_doc_names": {
            kind: [name for name in names if re.search(r"(legacy|deprecated|old)", name, re.I)]
            for kind, names in missing_from_registry.items()
        },
        "parse_warnings": warnings,
    }


def _load_structured_config(config: ServerConfig, path: str) -> tuple[dict[str, Any] | None, list[str], str]:
    cfg_path = _safe_rel_path(config, path, {".yaml", ".yml", ".json"})
    text, truncated = _read_text(config, cfg_path)
    warnings = ["config text truncated"] if truncated else []
    try:
        if cfg_path.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        return None, [*warnings, f"parse error: {exc}"], to_repo_relative(config.repo_root, cfg_path)
    if not isinstance(data, dict):
        return None, [*warnings, "config root is not a mapping"], to_repo_relative(config.repo_root, cfg_path)
    return data, warnings, to_repo_relative(config.repo_root, cfg_path)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _kind(block: Any) -> str | None:
    if isinstance(block, dict):
        for key in ("kind", "name", "step", "type"):
            if block.get(key) is not None:
                return str(block[key])
    return None


def _feature_steps(data: dict[str, Any]) -> list[dict[str, Any]]:
    features = data.get("features") or data.get("feature_steps") or []
    if isinstance(features, dict):
        features = features.get("steps", [])
    steps = []
    for index, item in enumerate(_as_list(features)):
        if isinstance(item, str):
            steps.append({"index": index, "kind": item, "params": {}, "transforms": []})
        elif isinstance(item, dict):
            steps.append(
                {
                    "index": index,
                    "kind": _kind(item),
                    "params": _as_dict(item.get("params")),
                    "transforms": _as_list(item.get("transforms") or item.get("normalizations") or item.get("normalization")),
                }
            )
    return steps


def _model_block(data: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(data.get("model"))


def _target_block(data: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(data.get("target") or _model_block(data).get("target"))


def _signal_block(data: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(data.get("signal") or data.get("signals"))


def inspect_config(config: ServerConfig, path: str) -> dict[str, Any]:
    data, warnings, rel = _load_structured_config(config, path)
    if data is None:
        return {"path": path, "parsed": False, "warnings": warnings}
    model = _model_block(data)
    target = _target_block(data)
    signal = _signal_block(data)
    known = {
        "data", "features", "feature_steps", "target", "model", "signal", "signals", "split",
        "backtest", "evaluation", "risk", "artifacts", "logging", "pipeline", "experiment", "optuna",
    }
    refs = {
        "feature": [step["kind"] for step in _feature_steps(data) if step.get("kind")],
        "target": [_kind(target)] if _kind(target) else [],
        "model": [_kind(model)] if _kind(model) else [],
        "signal": [_kind(signal)] if _kind(signal) else [],
        "pipeline": [str(data["pipeline"])] if isinstance(data.get("pipeline"), str) else [],
    }
    return {
        "path": rel,
        "parsed": True,
        "data_block": _as_dict(data.get("data")),
        "feature_steps": _feature_steps(data),
        "target_block": target,
        "model": {
            "kind": _kind(model),
            "feature_cols": _as_list(model.get("feature_cols")),
            "feature_selectors": model.get("feature_selectors") or model.get("features"),
            "split": model.get("split") or data.get("split"),
            "preprocessing": model.get("preprocessing") or model.get("scaler") or model.get("scaling"),
        },
        "signal": {"kind": _kind(signal), "params": _as_dict(signal.get("params"))},
        "backtest": _as_dict(data.get("backtest")),
        "evaluation": _as_dict(data.get("evaluation")),
        "risk": _as_dict(data.get("risk")),
        "artifacts": _as_dict(data.get("artifacts")),
        "logging": _as_dict(data.get("logging")),
        "unknown_top_level_keys": sorted(set(data) - known),
        "referenced_component_names": refs,
        "warnings": warnings,
    }


def _column_hints(value: Any) -> list[str]:
    cols: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("_col") or key.endswith("_cols") or key in {"output_col", "output_cols", "items"}:
                cols.extend(str(v) for v in _as_list(item) if isinstance(v, (str, int, float)))
            else:
                cols.extend(_column_hints(item))
    elif isinstance(value, list):
        for item in value:
            cols.extend(_column_hints(item))
    return sorted(set(cols))


def feature_lineage(config: ServerConfig, path: str) -> dict[str, Any]:
    summary = inspect_config(config, path)
    if not summary.get("parsed"):
        return {"path": path, "nodes": [], "edges": [], "unresolved_columns": [], "possible_missing_upstream_columns": [], "notes": summary.get("warnings", [])}
    nodes: list[dict[str, Any]] = [{"id": col, "type": "raw_input", "confidence": "assumed"} for col in ["open", "high", "low", "close", "volume"]]
    edges: list[dict[str, Any]] = []
    produced = {"open", "high", "low", "close", "volume"}
    last_step = "raw_ohlcv"
    for step in summary["feature_steps"]:
        step_id = f"feature:{step['index']}:{step.get('kind') or 'unknown'}"
        outputs = _column_hints(step.get("params")) + _column_hints(step.get("transforms"))
        nodes.append({"id": step_id, "type": "feature_step", "kind": step.get("kind"), "outputs": outputs, "confidence": "approximate"})
        edges.append({"from": last_step, "to": step_id, "relationship": "executes_after"})
        for col in outputs:
            nodes.append({"id": col, "type": "feature_column_hint", "confidence": "configured"})
            edges.append({"from": step_id, "to": col, "relationship": "may_generate"})
            produced.add(col)
        last_step = step_id
    model_cols = [str(col) for col in summary["model"].get("feature_cols", [])]
    for col in model_cols:
        nodes.append({"id": col, "type": "model_feature", "confidence": "configured"})
        edges.append({"from": col, "to": "model", "relationship": "consumed_by"})
    target_outputs = _column_hints(summary.get("target_block", {}))
    for col in target_outputs:
        nodes.append({"id": col, "type": "target_column_hint", "confidence": "configured"})
        edges.append({"from": "target", "to": col, "relationship": "may_generate"})
    signal_cols = _column_hints(summary.get("signal", {}).get("params", {}))
    for col in signal_cols:
        nodes.append({"id": col, "type": "signal_column", "confidence": "configured"})
        edges.append({"from": col, "to": "signal", "relationship": "consumed_by"})
    unresolved = sorted(set(model_cols + signal_cols) - produced - set(target_outputs))
    return {
        "path": summary["path"],
        "nodes": nodes[:500],
        "edges": edges[:700],
        "unresolved_columns": unresolved,
        "possible_missing_upstream_columns": unresolved,
        "notes": ["Static lineage is approximate; dynamic feature expansion and runtime dataframe mutations are not executed."],
    }


def _contains_key(data: Any, pattern: str) -> bool:
    regex = re.compile(pattern, re.I)
    if isinstance(data, dict):
        return any(regex.search(str(key)) or _contains_key(value, pattern) for key, value in data.items())
    if isinstance(data, list):
        return any(_contains_key(item, pattern) for item in data)
    return bool(isinstance(data, str) and regex.search(data))


def _has_oos_marker(data: Any) -> bool:
    if isinstance(data, dict):
        return any(
            re.search(r"^(pred_)?is_oos$|^oos$|oos_prediction|prediction_oos", str(key), re.I)
            or _has_oos_marker(value)
            for key, value in data.items()
        )
    if isinstance(data, list):
        return any(_has_oos_marker(item) for item in data)
    return False


def leakage_audit_config(config: ServerConfig, path: str) -> dict[str, Any]:
    data, warnings, rel = _load_structured_config(config, path)
    issues: list[dict[str, Any]] = []
    if data is None:
        return {"path": path, "severity": "danger", "issues": [{"severity": "danger", "code": "CONFIG_PARSE_ERROR", "message": "; ".join(warnings), "path_in_config": "$", "recommendation": "Fix YAML/JSON syntax before auditing."}]}
    summary = inspect_config(config, path)
    feature_cols = [str(col) for col in summary["model"].get("feature_cols", [])]
    for col in feature_cols:
        if SUSPICIOUS_FEATURE_PATTERNS.search(col):
            issues.append({"severity": "danger", "code": "SUSPICIOUS_MODEL_FEATURE", "message": f"Model feature column looks target/diagnostic-derived: {col}", "path_in_config": "model.feature_cols", "recommendation": "Remove target, label, future, barrier, and trade diagnostic columns from model features."})
        if col.lower() in RAW_OHLC:
            issues.append({"severity": "warning", "code": "RAW_OHLC_MODEL_FEATURE", "message": f"Raw OHLC price level used as model feature: {col}", "path_in_config": "model.feature_cols", "recommendation": "Prefer stationary/normalized features unless raw levels are explicitly justified and tested."})
    selectors = summary["model"].get("feature_selectors")
    if selectors and _contains_key(selectors, r"(include|pattern|regex)") and not _contains_key(selectors, r"(exclude|deny|target|label|diagnostic)"):
        issues.append({"severity": "warning", "code": "BROAD_FEATURE_SELECTOR", "message": "Feature selectors appear to include broad rules without explicit target/diagnostic exclusions.", "path_in_config": "model.feature_selectors", "recommendation": "Add explicit exclusions for target, label, future, barrier, and diagnostic columns."})
    signal = summary.get("signal", {})
    signal_text = json.dumps(signal, default=str).lower()
    if ("prob" in signal_text or "forecast" in signal_text) and not _has_oos_marker(data):
        issues.append({"severity": "warning", "code": "MISSING_OOS_PRED_MARKER", "message": "Signal appears to consume probability/forecast columns but no OOS prediction marker is configured.", "path_in_config": "signal", "recommendation": "Ensure signals only consume out-of-sample predictions and preserve a pred_is_oos marker."})
    target = summary.get("target_block", {})
    split = _as_dict(summary["model"].get("split") or data.get("split"))
    if _contains_key(target, r"(horizon|max_holding)") and not (_contains_key(split, r"(purge|embargo)") or re.search(r"purged", str(split), re.I)):
        issues.append({"severity": "danger", "code": "MISSING_PURGE_EMBARGO", "message": "Target horizon/max_holding exists but split has no obvious purge/embargo configuration.", "path_in_config": "split", "recommendation": "Use purged splitting or set purge_bars/embargo_bars for overlapping label horizons."})
    for step in summary["feature_steps"]:
        if step.get("kind") == "multi_timeframe":
            params = step.get("params", {})
            if params.get("shift_to_last_closed") is not True:
                issues.append({"severity": "danger", "code": "MTF_ALIGNMENT_UNCLEAR", "message": "multi_timeframe feature lacks explicit shift_to_last_closed=true.", "path_in_config": f"features[{step['index']}].params.shift_to_last_closed", "recommendation": "Align higher-timeframe features to the last closed bar."})
        if step.get("kind") and re.search(r"(hmm|regime)", str(step["kind"]), re.I):
            issues.append({"severity": "warning", "code": "LEARNED_REGIME_FEATURE", "message": f"Learned/regime feature '{step['kind']}' may require fold-safe fitting.", "path_in_config": f"features[{step['index']}]", "recommendation": "Verify any learned state is fit inside each training fold only."})
        if step.get("kind") and re.search(r"(candle|orb|opening_range|geometry)", str(step["kind"]), re.I):
            issues.append({"severity": "warning", "code": "EXECUTION_TIMING_AMBIGUITY", "message": f"Current-candle geometry feature '{step['kind']}' may be ambiguous with same-bar execution.", "path_in_config": f"features[{step['index']}]", "recommendation": "Prefer next-open execution or explicitly document signal timestamp semantics."})
    if any(key in data for key in ("scaler", "scaling", "preprocessing")):
        issues.append({"severity": "warning", "code": "PREPROCESSING_OUTSIDE_MODEL", "message": "Scaler/preprocessing appears outside the model block.", "path_in_config": "$", "recommendation": "Keep preprocessing fold-safe inside model training/evaluation logic."})
    severity = "danger" if any(i["severity"] == "danger" for i in issues) else "warning" if issues else "ok"
    return {"path": rel, "severity": severity, "issues": issues, "parse_warnings": warnings}


def target_signal_compatibility_check(config: ServerConfig, path: str) -> dict[str, Any]:
    summary = inspect_config(config, path)
    if not summary.get("parsed"):
        return {"path": path, "warnings": summary.get("warnings", []), "recommendations": []}
    target_kind = _kind(summary.get("target_block", {})) or ""
    signal = summary.get("signal", {})
    signal_kind = signal.get("kind") or ""
    params = _as_dict(signal.get("params"))
    warnings: list[dict[str, str]] = []
    def add(code: str, message: str, recommendation: str) -> None:
        warnings.append({"code": code, "message": message, "recommendation": recommendation})
    if signal_kind == "meta_probability_side":
        for required in ("prob_col", "side_col"):
            if not params.get(required):
                add("META_SIGNAL_MISSING_INPUT", f"meta_probability_side missing {required}.", f"Configure signal.params.{required}.")
        if not params.get("candidate_col"):
            add("META_SIGNAL_NO_CANDIDATE", "meta_probability_side lacks candidate_col.", "Configure candidate_col so probability gates explicit candidate events.")
    if signal_kind == "manual_long_model_filter":
        for required in ("candidate_col", "base_signal_col", "prob_col"):
            if not params.get(required):
                add("MANUAL_FILTER_MISSING_INPUT", f"manual_long_model_filter missing {required}.", f"Configure signal.params.{required}.")
    if signal_kind == "probability_threshold" and re.search(r"(label|target)", str(params.get("prob_col") or params.get("prediction_col") or ""), re.I):
        add("PROBABILITY_SIGNAL_READS_LABEL", "probability_threshold appears to read a label/target column.", "Point probability_threshold at classifier probability output.")
    if signal_kind in {"forecast_threshold", "forecast_vol_adjusted"} and re.search(r"(label|target|class)", json.dumps(params), re.I):
        add("FORECAST_SIGNAL_READS_CLASS_LABEL", f"{signal_kind} should consume forecast columns, not classifier labels.", "Use a forecast/prediction return column from a regression or forecaster model.")
    if target_kind in {"triple_barrier", "directional_triple_barrier"} and any(params.get(k) for k in ("side_col", "candidate_col")) and "meta" not in signal_kind and "filter" not in signal_kind:
        add("TARGET_SIGNAL_META_ALIGNMENT", "Barrier target with side/candidate inputs is usually paired with a meta-labeling/filter signal.", "Verify signal semantics match directional/meta-label target outputs.")
    entry_mode = params.get("entry_price_mode") or summary.get("backtest", {}).get("entry_price_mode")
    if entry_mode != "next_open":
        add("ENTRY_PRICE_MODE_AMBIGUOUS", "entry_price_mode is not explicitly next_open.", "Use entry_price_mode=next_open when signals are computed on the current close.")
    return {"path": summary["path"], "target_kind": target_kind, "signal_kind": signal_kind, "warnings": warnings, "recommendations": [w["recommendation"] for w in warnings]}


def _read_json_if_exists(config: ServerConfig, path: Path) -> Any:
    if not path.is_file():
        return None
    text, _ = _read_text(config, path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _metric_summary(payloads: dict[str, Any]) -> dict[str, Any]:
    keys = ("primary_metric", "metric", "score", "sharpe", "sharpe_ratio", "max_drawdown", "drawdown", "win_rate", "trade_count", "n_trades")
    found: dict[str, Any] = {}
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in keys and key not in found:
                    found[key] = item
                if len(found) < 12:
                    walk(item)
        elif isinstance(value, list):
            for item in value[:20]:
                walk(item)
    walk(payloads)
    return found


def list_recent_runs_with_metrics(config: ServerConfig, root: str = "logs", max_runs: int = 20) -> dict[str, Any]:
    runs = list_experiment_runs(config, root=root, max_runs=max_runs).get("runs", [])
    enriched: list[dict[str, Any]] = []
    for run in runs[: max(1, min(max_runs, 100))]:
        run_dir = resolve_repo_path(config.repo_root, run["run_id"])
        payloads = {
            name: _read_json_if_exists(config, run_dir / name)
            for name in ("summary.json", "run_metadata.json", "artifact_manifest.json", "study_summary.json")
        }
        metadata = _as_dict(payloads.get("run_metadata.json"))
        enriched.append(
            {
                "run_id": run["run_id"],
                "modified_time": run.get("modified_time"),
                "config_path": metadata.get("config_path") or metadata.get("config") or _as_dict(payloads.get("summary.json")).get("config_path"),
                "primary_metric_summary": _metric_summary(payloads),
                "artifact_availability": {name: payload is not None for name, payload in payloads.items()},
            }
        )
    return {"root": root, "runs": enriched, "truncated": len(runs) >= max_runs}


def compare_experiment_runs(config: ServerConfig, run_ids: list[str]) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    for run_id in run_ids:
        run_dir = resolve_repo_path(config.repo_root, run_id)
        payloads = {
            name: _read_json_if_exists(config, run_dir / name)
            for name in ("summary.json", "run_metadata.json", "artifact_manifest.json", "study_summary.json")
        }
        comparisons.append({"run_id": to_repo_relative(config.repo_root, run_dir), "metrics": _metric_summary(payloads), "config_path": _as_dict(payloads.get("run_metadata.json")).get("config_path"), "available": {k: v is not None for k, v in payloads.items()}})
    metric_keys = sorted({key for item in comparisons for key in item["metrics"]})
    return {
        "runs": comparisons,
        "metric_differences": {key: {item["run_id"]: item["metrics"].get(key, "unavailable") for item in comparisons} for key in metric_keys},
        "config_paths": {item["run_id"]: item.get("config_path") or "unavailable" for item in comparisons},
        "missing_data": [item["run_id"] for item in comparisons if not any(item["available"].values())],
    }


def _changed_files_from_status(status: str) -> list[str]:
    files: list[str] = []
    for line in status.splitlines():
        if not line or line.startswith("##"):
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def _area(path: str) -> str:
    if path.startswith("config/"):
        return "config"
    if path.startswith("src/features/"):
        return "features"
    if path.startswith("src/signals/"):
        return "signals"
    if path.startswith("src/targets/"):
        return "targets"
    if path.startswith("src/models/"):
        return "models"
    if path.startswith("src/experiments/"):
        return "experiments"
    if path.startswith(("src/backtesting/", "src/evaluation/", "src/risk/")):
        return "backtesting/evaluation/risk"
    if path.startswith("docs/"):
        return "docs"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith("mcp_server/"):
        return "mcp_server"
    return "other"


def review_current_changes(config: ServerConfig) -> dict[str, Any]:
    status = git_status(config)["status"]
    files = _changed_files_from_status(status)
    grouped: dict[str, list[str]] = {}
    for path in files:
        grouped.setdefault(_area(path), []).append(path)
    diff = git_diff(config, max_bytes=config.max_read_bytes)["diff"]
    companions: list[str] = []
    if any(area in grouped for area in ("features", "signals", "targets", "models", "experiments")) and "tests" not in grouped:
        companions.append("code changed but no tests changed")
    if any(path.endswith("registry.py") for path in files) and "docs" not in grouped:
        companions.append("registry touched but docs/catalog files not touched")
    added_modules = [path for path in files if path.startswith("src/") and path.endswith(".py") and "registry.py" not in path]
    if added_modules and not any(path.endswith("registry.py") for path in files):
        companions.append("source module added/changed but registry not touched")
    if "config" in grouped:
        companions.append("config validation likely needed")
    warnings = []
    if SUSPICIOUS_FEATURE_PATTERNS.search(diff):
        warnings.append("diff mentions target/label/future/barrier/trade diagnostic terms; check feature leakage")
    if re.search(r"purge|embargo|split|default", diff, re.I):
        warnings.append("diff touches split/default semantics; verify no silent runtime default change")
    if re.search(r"shift\s*\(|rolling\(", diff):
        warnings.append("diff touches shift/rolling logic; verify temporal causality")
    return {"changed_files_by_area": grouped, "potential_missing_companion_changes": companions, "possible_leakage_architecture_warnings": warnings, "git_status_summary": status}


def suggest_tests_for_change(config: ServerConfig, path: str | None = None) -> dict[str, Any]:
    if path:
        resolved = resolve_repo_path(config.repo_root, path)
        files = [to_repo_relative(config.repo_root, resolved)]
    else:
        files = _changed_files_from_status(git_status(config)["status"])
    areas = sorted({_area(item) for item in files})
    pytest_paths = ["mcp_server/tests" if area == "mcp_server" else "tests" for area in areas if area != "docs"]
    new_cases = []
    if "config" in areas:
        new_cases.append("config schema/default validation for changed YAML keys")
    if any(area in areas for area in ("features", "signals", "targets", "models")):
        new_cases.append("registry resolution plus leakage/temporal-causality regression tests")
    if "mcp_server" in areas:
        new_cases.append("MCP tool security, bounded output, and server registration tests")
    return {
        "input_path": path,
        "changed_areas": areas,
        "suggested_pytest_paths": sorted(set(pytest_paths)),
        "suggested_new_test_cases": new_cases,
        "full_pytest_recommended": any(area in areas for area in ("experiments", "backtesting/evaluation/risk", "models", "targets")),
        "docs_config_validation_checks": ["validate touched YAML configs", "update docs/catalog when registries change"] if {"config", "features", "signals", "targets", "models"} & set(areas) else [],
    }


def run_pytest(config: ServerConfig, paths: list[str] | None = None, confirmation: str | None = None, timeout_seconds: int | None = None) -> dict[str, Any]:
    if confirmation != CONFIRM_TESTS:
        raise PermissionError(f"pytest execution requires confirmation='{CONFIRM_TESTS}'")
    safe_paths = paths or ["mcp_server/tests"]
    resolved_paths: list[str] = []
    for path in safe_paths:
        resolved = resolve_repo_path(config.repo_root, path)
        rel = to_repo_relative(config.repo_root, resolved)
        if not (rel == "tests" or rel.startswith("tests/") or rel == "mcp_server/tests" or rel.startswith("mcp_server/tests/")):
            raise PathSecurityError("pytest paths must be under tests/ or mcp_server/tests/")
        resolved_paths.append(rel)
    command = ["pytest", *resolved_paths]
    try:
        proc = subprocess.run(
            command,
            cwd=config.repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=min(timeout_seconds or config.script_timeout_seconds, config.script_timeout_seconds),
        )
        stdout = proc.stdout[-config.max_read_bytes :]
        stderr = proc.stderr[-config.max_read_bytes :]
        return {
            "command": command,
            "return_code": proc.returncode,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_tail": stdout,
            "stderr_tail": stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stdout = stdout[-config.max_read_bytes :]
        stderr = stderr[-config.max_read_bytes :]
        return {
            "command": command,
            "return_code": None,
            "returncode": None,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_tail": stdout,
            "stderr_tail": stderr,
            "timed_out": True,
        }
