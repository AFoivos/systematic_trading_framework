from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

from src.evaluation.diagnostics import summarize_prediction_alignment
from src.models.forecasting.lightgbm_baseline import train_test_split_time


def test_experiment_configs_do_not_hardcode_container_workspace_root() -> None:
    config_root = Path(__file__).resolve().parents[1] / "config" / "experiments"
    offenders = [
        str(path.relative_to(config_root))
        for path in config_root.rglob("*.yaml")
        if "/workspace/" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_prediction_alignment_serializes_range_index() -> None:
    index = pd.RangeIndex(4)
    diagnostics = summarize_prediction_alignment(
        index=index,
        oos_mask=pd.Series([False, True, True, False], index=index),
        prediction=pd.Series([float("nan"), 0.1, 0.2, float("nan")], index=index),
    )

    assert diagnostics["first_prediction_index"] == 1
    assert diagnostics["last_prediction_index"] == 2


def test_standalone_time_split_purges_forward_horizon_and_embargoes_test() -> None:
    frame = pd.DataFrame({"value": range(10)})

    train, test = train_test_split_time(
        frame,
        train_frac=0.6,
        target_horizon=3,
        embargo_bars=1,
    )

    assert train.index.tolist() == [0, 1, 2]
    assert test.index.tolist() == [7, 8, 9]


def test_v37_sweep_script_preserves_variable_length_asset_symbols() -> None:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "chatgpt_create_v37_model_sweep.py"
    )
    spec = importlib.util.spec_from_file_location("v37_model_sweep", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.REPO_ROOT == Path(__file__).resolve().parents[1]
    assert module.asset_from_csv(Path("xauusd_30m.csv")) == "xauusd"
    assert module.asset_from_csv(Path("spx500_30m.csv")) == "spx500"
    config = module.build_config(
        {
            "strategy": {"name": "base", "assets": [], "description": ""},
            "data": {"symbol": "ETHUSD", "storage": {}},
            "features": [],
            "logging": {},
        },
        "xauusd",
        module.REPO_ROOT / "data/raw/dukascopy_30m_clean/xauusd_30m.csv",
    )
    assert config["strategy"]["name"].startswith("xauusd_")
    assert config["data"]["symbol"] == "XAUUSD"
