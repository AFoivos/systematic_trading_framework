from __future__ import annotations

from pathlib import Path

import yaml

from src.experiments.runner import run_experiment
from src.experiments.support.btcusd_dual_trend_ftmo import REQUIRED_ARTIFACTS, _validate_locked_config
from src.features.registry import FEATURE_REGISTRY
from src.pipelines.registry import PIPELINE_REGISTRY
from src.signals.registry import SIGNAL_REGISTRY
from src.utils.config import load_experiment_config


CONFIG_PATH = Path(
    "config/experiments/btcusd_dual_trend_ftmo/btcusd_1m_dual_trend_ftmo_22_16_v1.yaml"
)


def test_locked_yaml_and_components_are_registered() -> None:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    _validate_locked_config(cfg)
    assert cfg["pipeline"]["kind"] in PIPELINE_REGISTRY
    assert cfg["features"][0]["step"] in FEATURE_REGISTRY
    assert cfg["signals"]["kind"] in SIGNAL_REGISTRY
    assert cfg["evaluation"]["legacy_holdout"]["pristine"] is False
    assert len(REQUIRED_ARTIFACTS) == 18


def test_locked_yaml_loads_without_relaxing_canonical_typed_schemas() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    assert cfg["pipeline"]["kind"] == "btcusd_dual_trend_ftmo_v1"
    assert cfg["backtest"]["rebalance_bars"] == 48
    assert cfg["config_path"].endswith(CONFIG_PATH.as_posix())


def test_yaml_dispatches_through_main_experiment_runner(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_pipeline(path: str | Path) -> dict[str, object]:
        observed["path"] = Path(path)
        return {"status": "dispatched"}

    monkeypatch.setattr("src.pipelines.registry.get_pipeline_fn", lambda kind: fake_pipeline)
    result = run_experiment(CONFIG_PATH)
    assert result == {"status": "dispatched"}
    assert observed["path"] == CONFIG_PATH
