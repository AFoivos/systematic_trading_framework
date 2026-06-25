from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from src.utils.paths import PROJECT_ROOT


@dataclass(frozen=True)
class AuditModule:
    relative_path: str
    stage: str
    reason: str


_BASE_STAGE_MODULES: tuple[tuple[str, str, str], ...] = (
    ("01. CLI facade", "src/experiments/runner.py", "Stable experiment entrypoint."),
    ("02. Config resolution", "src/utils/config.py", "Load and resolve the experiment YAML."),
    ("02. Config resolution", "src/utils/config_loader.py", "Resolve config paths and YAML payloads."),
    ("02. Config resolution", "src/utils/config_defaults.py", "Apply explicit runtime defaults."),
    ("02. Config resolution", "src/utils/config_validation.py", "Validate the resolved config contract."),
    ("02. Config resolution", "src/utils/config_schemas.py", "Build the typed resolved config."),
    ("03. Pipeline orchestration", "src/experiments/orchestration/pipeline.py", "Execute the stage sequence."),
    ("03. Pipeline orchestration", "src/utils/repro.py", "Apply deterministic runtime settings."),
    ("04. Data loading and PIT", "src/experiments/orchestration/data_stage.py", "Load cached market data and enforce contracts."),
    ("04. Data loading and PIT", "src/src_data/storage.py", "Read the configured cached dataset."),
    ("04. Data loading and PIT", "src/src_data/validation.py", "Validate loaded OHLCV data."),
    ("04. Data loading and PIT", "src/experiments/contracts.py", "Validate experiment data assumptions."),
    ("05. Feature pipeline", "src/experiments/orchestration/feature_stage.py", "Apply configured feature and signal functions."),
    ("05. Feature pipeline", "src/experiments/registry.py", "Resolve configured registry implementations."),
    ("06. Model stage", "src/experiments/orchestration/model_stage.py", "Apply model.kind='none' passthrough or the configured model."),
    ("07. Signal stage", "src/experiments/orchestration/feature_stage.py", "Apply the configured signal function."),
    ("08. Target diagnostics", "src/experiments/orchestration/target_stage.py", "Build post-signal target diagnostics."),
    ("09. Backtest", "src/experiments/orchestration/backtest_stage.py", "Select and run the configured backtest engine."),
    ("10. Evaluation and monitoring", "src/experiments/orchestration/reporting.py", "Compute evaluation and monitoring payloads."),
    ("11. Execution output", "src/experiments/orchestration/execution_stage.py", "Return early when execution.enabled=false or build orders."),
    ("12. Artifact persistence", "src/experiments/orchestration/artifacts.py", "Persist experiment artifacts and reports."),
    ("12. Artifact persistence", "src/utils/run_metadata.py", "Persist reproducibility metadata and artifact hashes."),
)

_TARGET_MODULES = {
    "forward_return": "src/targets/forward_return.py",
    "triple_barrier": "src/targets/triple_barrier.py",
    "r_multiple": "src/targets/r_multiple.py",
}

_BACKTEST_MODULES = {
    "manual_barrier": (
        "src/backtesting/manual_barrier.py",
        "src/backtesting/trade_path.py",
    ),
    "vectorized": ("src/backtesting/engine.py",),
}


def _relative_source_path(fn: Callable[..., Any], *, project_root: Path) -> str:
    import inspect

    source_path = inspect.getsourcefile(fn)
    if source_path is None:
        raise ValueError(f"Cannot resolve source file for {fn!r}.")
    return Path(source_path).resolve().relative_to(project_root.resolve()).as_posix()


def _selected_modules(cfg: dict[str, Any], *, project_root: Path) -> list[AuditModule]:
    from src.features.registry import get_feature_fn
    from src.models.registry import get_model_fn
    from src.signals.registry import get_signal_fn

    modules = [
        AuditModule(relative_path=relative_path, stage=stage, reason=reason)
        for stage, relative_path, reason in _BASE_STAGE_MODULES
    ]
    for step in list(cfg.get("features", []) or []):
        if not isinstance(step, dict) or step.get("enabled", True) is False:
            continue
        name = str(step.get("step", "")).strip()
        if name:
            modules.append(
                AuditModule(
                    _relative_source_path(get_feature_fn(name), project_root=project_root),
                    "05. Feature pipeline",
                    f"Configured feature step: {name}.",
                )
            )

    model_cfg = dict(cfg.get("model", {}) or {})
    model_kind = str(model_cfg.get("kind", "none")).strip()
    if model_kind and model_kind != "none":
        modules.append(
            AuditModule(
                _relative_source_path(get_model_fn(model_kind), project_root=project_root),
                "06. Model stage",
                f"Configured model implementation: {model_kind}.",
            )
        )

    signals_cfg = dict(cfg.get("signals", {}) or {})
    signal_kind = str(signals_cfg.get("kind", "none")).strip()
    if signal_kind and signal_kind != "none":
        modules.append(
            AuditModule(
                _relative_source_path(get_signal_fn(signal_kind), project_root=project_root),
                "07. Signal stage",
                f"Configured signal implementation: {signal_kind}.",
            )
        )

    target_cfg = dict(cfg.get("target") or model_cfg.get("target", {}) or {})
    target_kind = str(target_cfg.get("kind", "")).strip()
    if target_kind:
        modules.append(
            AuditModule(
                "src/targets/classifier.py",
                "08. Target diagnostics",
                f"Target dispatcher for configured target: {target_kind}.",
            )
        )
        target_module = _TARGET_MODULES.get(target_kind)
        if target_module:
            modules.append(
                AuditModule(
                    target_module,
                    "08. Target diagnostics",
                    f"Configured target implementation: {target_kind}.",
                )
            )

    backtest_kind = str(dict(cfg.get("backtest", {}) or {}).get("engine", "vectorized")).strip()
    for module in _BACKTEST_MODULES.get(backtest_kind, ()):
        modules.append(
            AuditModule(
                module,
                "09. Backtest",
                f"Configured backtest implementation: {backtest_kind}.",
            )
        )
    return _dedupe_modules(modules)


def _dedupe_modules(modules: Iterable[AuditModule]) -> list[AuditModule]:
    seen: set[str] = set()
    out: list[AuditModule] = []
    for module in modules:
        if module.relative_path in seen:
            continue
        seen.add(module.relative_path)
        out.append(module)
    return out


def _module_name(relative_path: str) -> str:
    path = Path(relative_path)
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _relative_import_name(
    current_module: str,
    imported_module: str | None,
    level: int,
    *,
    is_package: bool,
) -> str:
    package_parts = current_module.split(".") if is_package else current_module.split(".")[:-1]
    prefix = package_parts[: len(package_parts) - max(level - 1, 0)]
    if imported_module:
        prefix.extend(imported_module.split("."))
    return ".".join(prefix)


def _module_path(module_name: str, *, project_root: Path) -> str | None:
    if not module_name.startswith("src"):
        return None
    base = project_root.joinpath(*module_name.split("."))
    candidates = (base.with_suffix(".py"), base / "__init__.py")
    for path in candidates:
        if path.is_file():
            return path.relative_to(project_root).as_posix()
    return None


def _local_import_paths(relative_path: str, *, project_root: Path) -> list[str]:
    source_path = project_root / relative_path
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=relative_path)
    current_module = _module_name(relative_path)
    is_package = Path(relative_path).name == "__init__.py"
    paths: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_name = _relative_import_name(
                    current_module,
                    node.module,
                    node.level,
                    is_package=is_package,
                )
                names.append(base_name)
                if node.module is None:
                    names.extend(f"{base_name}.{alias.name}" for alias in node.names)
            elif node.module:
                names.append(node.module)
        for name in names:
            path = _module_path(name, project_root=project_root)
            if path:
                paths.add(path)
    return sorted(paths)


def _required_modules(explicit_modules: list[AuditModule], *, project_root: Path) -> list[AuditModule]:
    modules = list(explicit_modules)
    seen = {module.relative_path for module in modules}
    queue = deque(modules)
    while queue:
        parent = queue.popleft()
        for relative_path in _local_import_paths(parent.relative_path, project_root=project_root):
            if relative_path in seen:
                continue
            seen.add(relative_path)
            dependency = AuditModule(
                relative_path=relative_path,
                stage="13. Imported repo-local dependencies",
                reason=f"Imported transitively from {parent.relative_path}.",
            )
            modules.append(dependency)
            queue.append(dependency)
    return modules


def _function_annotation_lines(
    source: str,
    *,
    relative_path: str,
    stage: str,
    function_order_start: int,
) -> tuple[str, int]:
    tree = ast.parse(source, filename=relative_path)
    insertions: dict[int, list[str]] = {}
    function_order = function_order_start
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for node in sorted(functions, key=lambda item: (item.lineno, item.col_offset)):
        function_order += 1
        first_line = min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])
        indent = " " * node.col_offset
        insertions.setdefault(first_line, []).extend(
            [
                f"{indent}# AUDIT FUNCTION {function_order:04d}",
                f"{indent}# Relative path: {relative_path}",
                f"{indent}# Runtime stage: {stage}",
            ]
        )

    rendered: list[str] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        rendered.extend(insertions.get(line_number, []))
        rendered.append(line)
    return "\n".join(rendered).rstrip() + "\n", function_order


def build_execution_source_audit(
    cfg: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
) -> str:
    explicit_modules = _selected_modules(cfg, project_root=project_root)
    modules = _required_modules(explicit_modules, project_root=project_root)
    config_snapshot = yaml.safe_dump(cfg, sort_keys=False).rstrip()
    lines = [
        "# GENERATED EXECUTION SOURCE AUDIT - READ-ONLY SNAPSHOT",
        "#",
        "# This file is generated for code review. It is not an executable monolith.",
        "# The stage list records the configured runtime order. Function annotations identify",
        "# the original repo-relative source path. Imported dependencies follow the explicit",
        "# stage modules because Python may call their helpers conditionally or inside loops.",
        "#",
        "# CONFIG SNAPSHOT",
        *[f"# {line}" for line in config_snapshot.splitlines()],
        "#",
        "# CONFIGURED RUNTIME MODULE ORDER",
    ]
    for index, module in enumerate(explicit_modules, start=1):
        lines.append(f"# {index:03d}. [{module.stage}] {module.relative_path} - {module.reason}")
    lines.extend(
        [
            "#",
            f"# Included repo-local modules: {len(modules)}",
            "",
        ]
    )

    function_order = 0
    for module_index, module in enumerate(modules, start=1):
        source = (project_root / module.relative_path).read_text(encoding="utf-8")
        annotated, function_order = _function_annotation_lines(
            source,
            relative_path=module.relative_path,
            stage=module.stage,
            function_order_start=function_order,
        )
        lines.extend(
            [
                "",
                "# " + "=" * 110,
                f"# AUDIT MODULE {module_index:03d}",
                f"# Relative path: {module.relative_path}",
                f"# Runtime stage: {module.stage}",
                f"# Inclusion reason: {module.reason}",
                "# " + "=" * 110,
                annotated.rstrip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_execution_source_audit(
    path: str | Path,
    *,
    cfg: dict[str, Any],
    project_root: Path = PROJECT_ROOT,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_execution_source_audit(cfg, project_root=project_root),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    import argparse

    from src.experiments.orchestration.common import redact_sensitive_values
    from src.utils.config import load_experiment_config

    parser = argparse.ArgumentParser(description="Generate a read-only execution source audit.")
    parser.add_argument("config", help="Experiment YAML path.")
    parser.add_argument("output", help="Output .py audit path.")
    args = parser.parse_args()
    cfg = redact_sensitive_values(load_experiment_config(args.config))
    write_execution_source_audit(args.output, cfg=cfg)


if __name__ == "__main__":
    main()


__all__ = ["build_execution_source_audit", "write_execution_source_audit"]
