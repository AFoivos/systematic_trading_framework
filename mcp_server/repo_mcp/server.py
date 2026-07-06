from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .command_tools import git_add as git_add_impl
from .command_tools import git_checkout_new_branch as git_checkout_new_branch_impl
from .command_tools import git_commit as git_commit_impl
from .command_tools import git_restore as git_restore_impl
from .command_tools import run_experiment as run_experiment_impl
from .command_tools import run_shell_command as run_shell_command_impl
from .config import load_config
from .git_tools import git_current_branch as git_current_branch_impl
from .git_tools import git_diff as git_diff_impl
from .git_tools import git_log as git_log_impl
from .git_tools import git_status as git_status_impl
from .introspection_tools import compare_experiment_runs as compare_experiment_runs_impl
from .introspection_tools import docs_registry_sync_check as docs_registry_sync_check_impl
from .introspection_tools import feature_lineage as feature_lineage_impl
from .introspection_tools import inspect_component as inspect_component_impl
from .introspection_tools import inspect_config as inspect_config_impl
from .introspection_tools import leakage_audit_config as leakage_audit_config_impl
from .introspection_tools import list_recent_runs_with_metrics as list_recent_runs_with_metrics_impl
from .introspection_tools import registry_inventory as registry_inventory_impl
from .introspection_tools import repo_overview_summary as repo_overview_summary_impl
from .introspection_tools import review_current_changes as review_current_changes_impl
from .introspection_tools import run_pytest as run_pytest_impl
from .introspection_tools import suggest_tests_for_change as suggest_tests_for_change_impl
from .introspection_tools import target_signal_compatibility_check as target_signal_compatibility_check_impl
from .project_tools import (
    execute_approved_python_script as execute_approved_python_script_impl,
)
from .project_tools import list_experiment_runs as list_experiment_runs_impl
from .project_tools import read_config as read_config_impl
from .project_tools import read_experiment_result as read_experiment_result_impl
from .project_tools import read_log as read_log_impl
from .project_tools import read_optuna_database as read_optuna_database_impl
from .repository import fetch_standard, find_references as find_references_impl
from .repository import list_directory as list_directory_impl
from .repository import read_file as read_file_impl
from .repository import read_project_tree as read_project_tree_impl
from .repository import search_code as search_code_impl
from .repository import search_files as search_files_impl
from .repository import search_standard, search_symbols as search_symbols_impl
from .write_tools import append_file as append_file_impl
from .write_tools import apply_patch as apply_patch_impl
from .write_tools import delete_path as delete_path_impl
from .write_tools import move_path as move_path_impl
from .write_tools import write_file as write_file_impl


CONFIG = load_config()
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
SCRIPT_RUNNER = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
WRITE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
DESTRUCTIVE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)
COMMAND_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
mcp = FastMCP(
    "systematic-trading-framework-repository",
    host=CONFIG.host,
    port=CONFIG.port,
)


@mcp.tool(annotations=READ_ONLY)
def search(query: str) -> str:
    """Use this when searching repository files for ChatGPT/company-knowledge style retrieval."""
    return search_standard(CONFIG, query)


@mcp.tool(annotations=READ_ONLY)
def fetch(id: str) -> str:
    """Use this when fetching one repository file returned by search."""
    return fetch_standard(CONFIG, id)


@mcp.tool(annotations=READ_ONLY)
def list_directory(path: str = ".", recursive: bool = False, max_entries: int | None = None) -> dict[str, Any]:
    """Use this when listing repository directories, optionally recursively."""
    return list_directory_impl(CONFIG, path=path, recursive=recursive, max_entries=max_entries)


@mcp.tool(annotations=READ_ONLY)
def read_file(path: str, start_line: int | None = None, max_lines: int | None = None, max_bytes: int | None = None) -> dict[str, Any]:
    """Use this when reading any text-like file inside the repository."""
    return read_file_impl(CONFIG, path=path, start_line=start_line, max_lines=max_lines, max_bytes=max_bytes)


@mcp.tool(annotations=WRITE_TOOL)
def write_file(path: str, content: str, create_dirs: bool = True, overwrite: bool = True, confirmation: str | None = None) -> dict[str, Any]:
    """Use this when editing or creating a repository text file."""
    return write_file_impl(CONFIG, path=path, content=content, create_dirs=create_dirs, overwrite=overwrite, confirmation=confirmation)


@mcp.tool(annotations=WRITE_TOOL)
def append_file(path: str, content: str, create_dirs: bool = True, confirmation: str | None = None) -> dict[str, Any]:
    """Use this when appending UTF-8 text to a repository file."""
    return append_file_impl(CONFIG, path=path, content=content, create_dirs=create_dirs, confirmation=confirmation)


@mcp.tool(annotations=WRITE_TOOL)
def apply_patch(patch: str, confirmation: str | None = None, timeout_seconds: int | None = None) -> dict[str, Any]:
    """Use this when applying a unified diff patch to the repository."""
    return apply_patch_impl(CONFIG, patch=patch, confirmation=confirmation, timeout_seconds=timeout_seconds)


@mcp.tool(annotations=DESTRUCTIVE_TOOL)
def delete_path(path: str, recursive: bool = False, confirmation: str | None = None) -> dict[str, Any]:
    """Use this when deleting a repository file or, with recursive=True, a directory."""
    return delete_path_impl(CONFIG, path=path, recursive=recursive, confirmation=confirmation)


@mcp.tool(annotations=WRITE_TOOL)
def move_path(src: str, dst: str, overwrite: bool = False, confirmation: str | None = None) -> dict[str, Any]:
    """Use this when moving or renaming a repository file or directory."""
    return move_path_impl(CONFIG, src=src, dst=dst, overwrite=overwrite, confirmation=confirmation)


@mcp.tool(annotations=READ_ONLY)
def search_files(pattern: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    """Use this when finding repository paths by glob-style filename or path pattern."""
    return search_files_impl(CONFIG, pattern=pattern, root=root, max_results=max_results)


@mcp.tool(annotations=READ_ONLY)
def search_code(query: str, root: str = ".", file_glob: str | None = None, max_results: int | None = None, context_lines: int = 1) -> dict[str, Any]:
    """Use this when searching text content across source, configs, notebooks, docs, CSVs, SQL, Docker files, and logs."""
    return search_code_impl(CONFIG, query=query, root=root, file_glob=file_glob, max_results=max_results, context_lines=context_lines)


@mcp.tool(annotations=READ_ONLY)
def search_symbols(query: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    """Use this when searching Python classes/functions or Markdown headings by symbol name."""
    return search_symbols_impl(CONFIG, query=query, root=root, max_results=max_results)


@mcp.tool(annotations=READ_ONLY)
def find_references(symbol: str, root: str = ".", max_results: int | None = None) -> dict[str, Any]:
    """Use this when finding textual references to a function, class, config key, or symbol."""
    return find_references_impl(CONFIG, symbol=symbol, root=root, max_results=max_results)


@mcp.tool(annotations=READ_ONLY)
def read_project_tree(max_depth: int = 4, include_files: bool = True, max_entries: int | None = None) -> dict[str, Any]:
    """Use this when inspecting the repository tree at bounded depth."""
    return read_project_tree_impl(CONFIG, max_depth=max_depth, include_files=include_files, max_entries=max_entries)


@mcp.tool(annotations=READ_ONLY)
def git_status() -> dict[str, Any]:
    """Use this when checking the current git status without modifying the repository."""
    return git_status_impl(CONFIG)


@mcp.tool(annotations=READ_ONLY)
def git_diff(path: str | None = None, max_bytes: int | None = None) -> dict[str, Any]:
    """Use this when reading unstaged git diffs for the full repository or one path."""
    return git_diff_impl(CONFIG, path=path, max_bytes=max_bytes)


@mcp.tool(annotations=READ_ONLY)
def git_log(max_count: int = 20) -> dict[str, Any]:
    """Use this when reading recent git commit history."""
    return git_log_impl(CONFIG, max_count=max_count)


@mcp.tool(annotations=READ_ONLY)
def git_current_branch() -> dict[str, str]:
    """Use this when checking the current git branch."""
    return git_current_branch_impl(CONFIG)


@mcp.tool(annotations=WRITE_TOOL)
def git_add(paths: list[str], confirmation: str | None = None) -> dict[str, Any]:
    """Use this when staging repository changes with git add."""
    return git_add_impl(CONFIG, paths=paths, confirmation=confirmation)


@mcp.tool(annotations=WRITE_TOOL)
def git_commit(message: str, confirmation: str | None = None) -> dict[str, Any]:
    """Use this when creating a local git commit."""
    return git_commit_impl(CONFIG, message=message, confirmation=confirmation)


@mcp.tool(annotations=WRITE_TOOL)
def git_checkout_new_branch(branch_name: str, confirmation: str | None = None) -> dict[str, Any]:
    """Use this when creating and checking out a new local git branch."""
    return git_checkout_new_branch_impl(CONFIG, branch_name=branch_name, confirmation=confirmation)


@mcp.tool(annotations=DESTRUCTIVE_TOOL)
def git_restore(paths: list[str], confirmation: str | None = None) -> dict[str, Any]:
    """Use this when restoring tracked repository paths from git."""
    return git_restore_impl(CONFIG, paths=paths, confirmation=confirmation)


@mcp.tool(annotations=READ_ONLY)
def list_experiment_runs(root: str = "logs", max_runs: int = 100) -> dict[str, Any]:
    """Use this when discovering experiment or bot run artifact directories."""
    return list_experiment_runs_impl(CONFIG, root=root, max_runs=max_runs)


@mcp.tool(annotations=READ_ONLY)
def read_experiment_result(run_id: str, artifact: str = "summary.json", max_rows: int = 200) -> dict[str, Any]:
    """Use this when reading one artifact from an experiment run directory."""
    return read_experiment_result_impl(CONFIG, run_id=run_id, artifact=artifact, max_rows=max_rows)


@mcp.tool(annotations=READ_ONLY)
def read_optuna_database(path: str, max_trials: int = 100) -> dict[str, Any]:
    """Use this when inspecting an Optuna SQLite database in read-only mode."""
    return read_optuna_database_impl(CONFIG, path=path, max_trials=max_trials)


@mcp.tool(annotations=READ_ONLY)
def read_config(path: str) -> dict[str, Any]:
    """Use this when reading YAML or JSON project configuration files."""
    return read_config_impl(CONFIG, path=path)


@mcp.tool(annotations=READ_ONLY)
def read_log(path: str, tail_lines: int = 200) -> dict[str, Any]:
    """Use this when reading a bounded tail from repository log files."""
    return read_log_impl(CONFIG, path=path, tail_lines=tail_lines)


@mcp.tool(annotations=SCRIPT_RUNNER)
def execute_approved_python_script(script: str, args: list[str] | None = None, confirmation: str | None = None, timeout_seconds: int | None = None) -> dict[str, Any]:
    """Use this only when the user explicitly confirms running an allowlisted Python script."""
    return execute_approved_python_script_impl(CONFIG, script=script, args=args, confirmation=confirmation, timeout_seconds=timeout_seconds)


@mcp.tool(annotations=COMMAND_TOOL)
def run_shell_command(command: str, cwd: str = ".", timeout_seconds: int | None = None, confirmation: str | None = None, max_output_bytes: int | None = None) -> dict[str, Any]:
    """Use this when running a shell command inside the repository container."""
    return run_shell_command_impl(CONFIG, command=command, cwd=cwd, timeout_seconds=timeout_seconds, confirmation=confirmation, max_output_bytes=max_output_bytes)


@mcp.tool(annotations=COMMAND_TOOL)
def run_experiment(config_path: str, timeout_seconds: int | None = None, confirmation: str | None = None) -> dict[str, Any]:
    """Use this when running an experiment config under config/experiments/."""
    return run_experiment_impl(CONFIG, config_path=config_path, timeout_seconds=timeout_seconds, confirmation=confirmation)


@mcp.tool(annotations=READ_ONLY)
def repo_overview_summary() -> dict[str, Any]:
    """Use this for a compact repository health, registry, git, and recent-run overview."""
    return repo_overview_summary_impl(CONFIG)


@mcp.tool(annotations=READ_ONLY)
def registry_inventory() -> dict[str, Any]:
    """Use this to inspect canonical component registries without importing project modules."""
    return registry_inventory_impl(CONFIG)


@mcp.tool(annotations=READ_ONLY)
def inspect_component(name: str, component_type: str | None = None) -> dict[str, Any]:
    """Use this to locate one registered component, its implementation, references, docs, and tests."""
    return inspect_component_impl(CONFIG, name=name, component_type=component_type)


@mcp.tool(annotations=READ_ONLY)
def docs_registry_sync_check() -> dict[str, Any]:
    """Use this to compare registry component names with docs/catalog files."""
    return docs_registry_sync_check_impl(CONFIG)


@mcp.tool(annotations=READ_ONLY)
def inspect_config(path: str) -> dict[str, Any]:
    """Use this to statically summarize a YAML or JSON experiment config without executing it."""
    return inspect_config_impl(CONFIG, path=path)


@mcp.tool(annotations=READ_ONLY)
def feature_lineage(path: str) -> dict[str, Any]:
    """Use this to infer approximate feature, target, model, prediction, and signal lineage from a config."""
    return feature_lineage_impl(CONFIG, path=path)


@mcp.tool(annotations=READ_ONLY)
def leakage_audit_config(path: str) -> dict[str, Any]:
    """Use this for static leakage and temporal-causality checks on an experiment config."""
    return leakage_audit_config_impl(CONFIG, path=path)


@mcp.tool(annotations=READ_ONLY)
def target_signal_compatibility_check(path: str) -> dict[str, Any]:
    """Use this to check semantic compatibility among target, model outputs, signal inputs, and execution timing."""
    return target_signal_compatibility_check_impl(CONFIG, path=path)


@mcp.tool(annotations=READ_ONLY)
def list_recent_runs_with_metrics(root: str = "logs", max_runs: int = 20) -> dict[str, Any]:
    """Use this to list recent experiment runs with defensive metric and artifact summaries."""
    return list_recent_runs_with_metrics_impl(CONFIG, root=root, max_runs=max_runs)


@mcp.tool(annotations=READ_ONLY)
def compare_experiment_runs(run_ids: list[str]) -> dict[str, Any]:
    """Use this to compare available metrics, config paths, and artifacts across experiment run directories."""
    return compare_experiment_runs_impl(CONFIG, run_ids=run_ids)


@mcp.tool(annotations=READ_ONLY)
def review_current_changes() -> dict[str, Any]:
    """Use this to review current git changes for likely missing companion changes and leakage risks."""
    return review_current_changes_impl(CONFIG)


@mcp.tool(annotations=READ_ONLY)
def suggest_tests_for_change(path: str | None = None) -> dict[str, Any]:
    """Use this to suggest targeted tests and validation checks for a path or current git diff."""
    return suggest_tests_for_change_impl(CONFIG, path=path)


@mcp.tool(annotations=SCRIPT_RUNNER)
def run_pytest(paths: list[str] | None = None, confirmation: str | None = None, timeout_seconds: int | None = None) -> dict[str, Any]:
    """Use this only when the user explicitly confirms running pytest under tests/ or mcp_server/tests/."""
    return run_pytest_impl(CONFIG, paths=paths, confirmation=confirmation, timeout_seconds=timeout_seconds)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
