from __future__ import annotations

from pathlib import Path
import sys
import types
from typing import Any

import pytest

from repo_mcp.config import ServerConfig
from repo_mcp.security import PathSecurityError


def _config(root: Path) -> ServerConfig:
    return ServerConfig(
        repo_root=root.resolve(),
        host="127.0.0.1",
        port=8765,
        max_read_bytes=200_000,
        max_search_results=100,
        max_tree_entries=500,
        script_timeout_seconds=30,
        approved_python_scripts=(),
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_registry_inventory_extracts_tuple_names_without_importing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from repo_mcp import introspection_tools as tools

    _write(
        tmp_path / "fake/registry.py",
        """
from definitely_missing_package import explode
from src.utils.registry import lazy_callable

_FEATURE_COMPONENTS = (
    ("returns", explode),
    ("xgboost_clf", lazy_callable("src.models.classification.xgboost", "train_xgboost_classifier")),
)
""",
    )
    monkeypatch.setattr(tools, "REGISTRY_FILES", {"feature": "fake/registry.py"})

    payload = tools.registry_inventory(_config(tmp_path))

    registry = payload["registries"][0]
    assert registry["component_names"] == ["returns", "xgboost_clf"]
    assert registry["component_count"] == 2
    assert registry["components"][1]["path"] == "src/models/classification/xgboost.py"


def test_registry_inventory_handles_missing_registry_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from repo_mcp import introspection_tools as tools

    monkeypatch.setattr(tools, "REGISTRY_FILES", {"feature": "missing/registry.py"})

    payload = tools.registry_inventory(_config(tmp_path))

    assert payload["registries"][0]["exists"] is False
    assert "registry file missing" in payload["registries"][0]["parse_warnings"]


def test_inspect_config_parses_minimal_yaml(tmp_path: Path) -> None:
    from repo_mcp.introspection_tools import inspect_config

    _write(
        tmp_path / "config/experiment.yaml",
        """
data:
  path: data.csv
features:
  - step: returns
    params:
      output_col: ret_1
model:
  kind: xgboost_clf
  feature_cols: [ret_1]
  split:
    method: walk_forward
target:
  kind: directional_triple_barrier
signal:
  kind: probability_threshold
  params:
    prob_col: pred_proba
""",
    )

    payload = inspect_config(_config(tmp_path), "config/experiment.yaml")

    assert payload["parsed"] is True
    assert payload["feature_steps"][0]["kind"] == "returns"
    assert payload["model"]["kind"] == "xgboost_clf"
    assert payload["target_block"]["kind"] == "directional_triple_barrier"
    assert payload["signal"]["kind"] == "probability_threshold"


def test_inspect_config_invalid_yaml_returns_warning(tmp_path: Path) -> None:
    from repo_mcp.introspection_tools import inspect_config

    _write(tmp_path / "config/broken.yaml", "model: [unterminated\n")

    payload = inspect_config(_config(tmp_path), "config/broken.yaml")

    assert payload["parsed"] is False
    assert any("parse error" in warning for warning in payload["warnings"])


def test_leakage_audit_flags_suspicious_features_probability_oos_and_missing_purge(tmp_path: Path) -> None:
    from repo_mcp.introspection_tools import leakage_audit_config

    _write(
        tmp_path / "config/leaky.yaml",
        """
features: []
model:
  kind: xgboost_clf
  feature_cols: [close, target_label, fwd_return, barrier_hit]
  split:
    method: walk_forward
target:
  kind: directional_triple_barrier
  horizon: 12
signal:
  kind: probability_threshold
  params:
    prob_col: pred_proba
""",
    )

    payload = leakage_audit_config(_config(tmp_path), "config/leaky.yaml")
    codes = {issue["code"] for issue in payload["issues"]}

    assert payload["severity"] == "danger"
    assert "SUSPICIOUS_MODEL_FEATURE" in codes
    assert "RAW_OHLC_MODEL_FEATURE" in codes
    assert "MISSING_OOS_PRED_MARKER" in codes
    assert "MISSING_PURGE_EMBARGO" in codes


def test_feature_lineage_extracts_feature_steps_and_helper_outputs(tmp_path: Path) -> None:
    from repo_mcp.introspection_tools import feature_lineage

    _write(
        tmp_path / "config/lineage.yaml",
        """
features:
  - step: returns
    params:
      output_col: ret_1
    transforms:
      - kind: zscore
        params:
          output_col: ret_1_z
model:
  kind: xgboost_clf
  feature_cols: [ret_1_z, missing_upstream]
signal:
  kind: probability_threshold
  params:
    prob_col: pred_proba
""",
    )

    payload = feature_lineage(_config(tmp_path), "config/lineage.yaml")
    output_nodes = {node["id"] for node in payload["nodes"]}

    assert "feature:0:returns" in output_nodes
    assert "ret_1" in output_nodes
    assert "ret_1_z" in output_nodes
    assert "missing_upstream" in payload["unresolved_columns"]


def test_target_signal_compatibility_warnings(tmp_path: Path) -> None:
    from repo_mcp.introspection_tools import target_signal_compatibility_check

    _write(
        tmp_path / "config/meta.yaml",
        """
target:
  kind: directional_triple_barrier
signal:
  kind: meta_probability_side
  params:
    prob_col: pred_proba
""",
    )
    _write(
        tmp_path / "config/prob.yaml",
        """
target:
  kind: forward_return
signal:
  kind: probability_threshold
  params:
    prob_col: target_label
""",
    )

    meta = target_signal_compatibility_check(_config(tmp_path), "config/meta.yaml")
    prob = target_signal_compatibility_check(_config(tmp_path), "config/prob.yaml")

    assert "META_SIGNAL_MISSING_INPUT" in {warning["code"] for warning in meta["warnings"]}
    assert "PROBABILITY_SIGNAL_READS_LABEL" in {warning["code"] for warning in prob["warnings"]}


def test_new_tools_reject_absolute_and_traversal_paths(tmp_path: Path) -> None:
    from repo_mcp.introspection_tools import feature_lineage, inspect_config, leakage_audit_config, suggest_tests_for_change

    cfg = _config(tmp_path)
    with pytest.raises(PathSecurityError):
        inspect_config(cfg, "/etc/passwd")
    with pytest.raises(PathSecurityError):
        feature_lineage(cfg, "../outside.yaml")
    with pytest.raises(PathSecurityError):
        leakage_audit_config(cfg, "../outside.yaml")
    with pytest.raises(PathSecurityError):
        suggest_tests_for_change(cfg, "/tmp/file.py")


def test_server_import_registers_new_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MCP_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("MCP_CONFIG_PATH", str(tmp_path / "missing-mcp-config.yaml"))

    class FakeFastMCP:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def tool(self, *args: Any, **kwargs: Any) -> Any:
            def decorator(func: Any) -> Any:
                return func

            return decorator

    class FakeToolAnnotations:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    mcp_pkg = types.ModuleType("mcp")
    mcp_server_pkg = types.ModuleType("mcp.server")
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = FakeFastMCP
    types_mod = types.ModuleType("mcp.types")
    types_mod.ToolAnnotations = FakeToolAnnotations
    monkeypatch.setitem(sys.modules, "mcp", mcp_pkg)
    monkeypatch.setitem(sys.modules, "mcp.server", mcp_server_pkg)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.types", types_mod)

    import repo_mcp.server as server

    assert callable(server.registry_inventory)
    assert callable(server.inspect_config)
    assert callable(server.leakage_audit_config)
    assert callable(server.review_current_changes)
    assert callable(server.write_file)
    assert callable(server.apply_patch)
    assert callable(server.run_shell_command)
    assert callable(server.run_experiment)
    assert callable(server.git_add)
    assert callable(server.search_source)
    assert callable(server.stat_files)
    assert callable(server.read_files)
    assert callable(server.list_changed_paths)
    assert callable(server.read_changed_files)
    assert callable(server.get_repo_snapshot)
    assert callable(server.get_code_review_bundle)
    assert callable(server.mcp_health)
    assert callable(server.mcp_diagnostics)

    _write(tmp_path / "src/module.py", "VALUE = 1\n")
    assert server.read_files(["src/module.py"])["files"][0]["content"].replace("\r\n", "\n") == "VALUE = 1\n"
    assert server.mcp_diagnostics()["tools"]["read_files"]["call_count"] == 1
