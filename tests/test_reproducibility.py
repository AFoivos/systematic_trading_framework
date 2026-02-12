from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from src.utils.config import load_experiment_config
from src.utils.repro import RuntimeConfigError, apply_runtime_reproducibility, validate_runtime_config
from src.utils.run_metadata import build_artifact_manifest, compute_config_hash, compute_dataframe_fingerprint


def test_runtime_defaults_are_loaded_from_config() -> None:
    cfg = load_experiment_config("experiments/lgbm_spy.yaml")
    runtime = cfg["runtime"]

    assert runtime["seed"] == 7
    assert runtime["deterministic"] is True
    assert runtime["repro_mode"] == "strict"
    assert runtime["threads"] == 1


def test_validate_runtime_config_rejects_invalid_threads() -> None:
    with pytest.raises(RuntimeConfigError):
        validate_runtime_config({"threads": 0})


def test_apply_runtime_reproducibility_sets_deterministic_numpy_stream() -> None:
    runtime = {
        "seed": 123,
        "deterministic": True,
        "threads": 1,
        "repro_mode": "strict",
    }
    ctx1 = apply_runtime_reproducibility(runtime)
    arr1 = np.random.rand(6)

    ctx2 = apply_runtime_reproducibility(runtime)
    arr2 = np.random.rand(6)

    assert np.array_equal(arr1, arr2)
    assert ctx1["thread_env"]["OMP_NUM_THREADS"] == "1"
    assert ctx2["pythonhashseed_matches_seed"] is True


def test_compute_config_hash_ignores_config_path_field() -> None:
    cfg = load_experiment_config("experiments/lgbm_spy.yaml")
    h1, _ = compute_config_hash(cfg)

    cfg2 = deepcopy(cfg)
    cfg2["config_path"] = "/tmp/another/path.yaml"
    h2, _ = compute_config_hash(cfg2)

    assert h1 == h2


def test_dataframe_fingerprint_is_stable_across_row_and_column_order() -> None:
    idx = pd.to_datetime(["2024-01-03", "2024-01-01", "2024-01-02"])
    df = pd.DataFrame({"b": [1.0, 2.0, 3.0], "a": [10.0, 20.0, 30.0]}, index=idx)
    fp1 = compute_dataframe_fingerprint(df)

    df_reordered = df[["a", "b"]].iloc[::-1]
    fp2 = compute_dataframe_fingerprint(df_reordered)

    df_changed = df_reordered.copy()
    df_changed.iloc[0, 0] += 1.0
    fp3 = compute_dataframe_fingerprint(df_changed)

    assert fp1["sha256"] == fp2["sha256"]
    assert fp1["sha256"] != fp3["sha256"]


def test_artifact_manifest_contains_file_hashes(tmp_path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("alpha", encoding="utf-8")
    b.write_text("beta", encoding="utf-8")

    manifest = build_artifact_manifest({"a": a, "b": b, "not_a_file": tmp_path})
    files = manifest["files"]

    assert "a" in files
    assert "b" in files
    assert "not_a_file" not in files
    assert files["a"]["bytes"] == 5
    assert len(files["a"]["sha256"]) == 64
