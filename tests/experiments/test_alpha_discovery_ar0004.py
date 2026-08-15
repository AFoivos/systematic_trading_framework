from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from src.experiments.orchestration.cloud_alpha_pipeline import (
    CloudAlphaExecutionRefused,
    run_alpha_discovery_v4_pipeline,
)
from src.pipelines.registry import get_pipeline_fn
from src.research.ar0004_runtime import _add_cross_sectional_features, _fold_rows
from src.utils.alpha_discovery_v4_config import validate_alpha_discovery_v4_config
from src.utils.config import load_experiment_config


CONFIG = Path("config/research/alpha_discovery/AR-0004_cloud_alpha_tournament.yaml")


def test_ar0004_specification_is_hash_bound_and_registered() -> None:
    cfg = load_experiment_config(CONFIG)
    validate_alpha_discovery_v4_config(cfg)
    assert cfg["status"] == "SPECIFICATION_ONLY"
    assert cfg["runtime"]["perform_alpha_calculation"] is False
    assert get_pipeline_fn("alpha_discovery_v4") is run_alpha_discovery_v4_pipeline


def test_ar0004_specification_only_refuses_before_data_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("data/model access occurred before approval")

    monkeypatch.setattr("src.research.ar0004_runtime.build_ar0004_panel", forbidden)
    with pytest.raises(CloudAlphaExecutionRefused, match="SPECIFICATION_ONLY"):
        run_alpha_discovery_v4_pipeline(CONFIG)


def test_ar0004_cross_sectional_features_do_not_use_future_timestamps() -> None:
    timestamps = pd.to_datetime(
        ["2025-01-01T00:00:00Z"] * 5 + ["2025-01-01T00:30:00Z"] * 5,
        utc=True,
    )
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "asset_id": [f"A{i}" for i in range(5)] * 2,
            "log_return_16": list(range(5)) + list(range(10, 15)),
            "log_return_32": list(range(1, 6)) + list(range(11, 16)),
            "log_return_64": list(range(2, 7)) + list(range(12, 17)),
            "path_efficiency_16": [0.1, 0.2, 0.3, 0.4, 0.5] * 2,
            "path_efficiency_32": [0.2, 0.3, 0.4, 0.5, 0.6] * 2,
            "path_efficiency_48": [0.3, 0.4, 0.5, 0.6, 0.7] * 2,
            "volatility_ratio_32_192": [0.5, 0.6, 0.7, 0.8, 0.9] * 2,
        }
    )
    baseline = _add_cross_sectional_features(frame, minimum_assets=5)
    changed = frame.copy()
    changed.loc[changed["timestamp"].eq(timestamps[-1]), "log_return_16"] *= 1000
    recomputed = _add_cross_sectional_features(changed, minimum_assets=5)
    first = frame["timestamp"].eq(timestamps[0])
    pd.testing.assert_series_equal(
        baseline.loc[first, "cs_z_log_return_16"].reset_index(drop=True),
        recomputed.loc[first, "cs_z_log_return_16"].reset_index(drop=True),
    )


def test_ar0004_fold_purge_excludes_overlapping_targets() -> None:
    timestamps = pd.date_range("2024-12-20", periods=800, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "asset_id": "ETHUSD",
            "feature": 1.0,
            "future_executable_return_h16": 0.001,
        }
    )
    test_start = timestamps[500]
    train, test, safe_end, eligible_rows = _fold_rows(
        frame,
        test_start=test_start,
        test_end=timestamps[700],
        horizon=16,
        features=("feature",),
    )
    assert safe_end == test_start - 17 * pd.Timedelta(minutes=30)
    assert train["timestamp"].max() < safe_end
    assert test["timestamp"].min() == test_start
    assert eligible_rows == len(test)


def test_ar0004_runtime_has_no_vectorbt_pybroker_or_live_imports() -> None:
    tree = ast.parse(Path("src/research/ar0004_runtime.py").read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots.isdisjoint({"vectorbt", "pybroker", "qlib", "skfolio", "nautilustrader"})


def test_ar0004_material_scientific_change_invalidates_hash() -> None:
    cfg = load_experiment_config(CONFIG)
    changed = deepcopy(cfg)
    changed["model_search"]["trials"] = 385
    with pytest.raises(ValueError, match="model_search.trials drifted"):
        validate_alpha_discovery_v4_config(changed)
