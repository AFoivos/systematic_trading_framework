from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from src.features.registry import FEATURE_REGISTRY
from src.signals.registry import SIGNAL_REGISTRY
from src.targets.registry import TARGET_REGISTRY
from src.utils.config import load_experiment_config
from src.utils.config_validation import ConfigValidationError, validate_resolved_config


CONFIG_PATH = Path("config/experiments/matb/00_matb_deterministic.yaml")
GATES_PATH = Path("config/experiments/matb/acceptance_gates.yaml")


def test_matb_deterministic_config_is_self_contained_and_valid() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    assert cfg["data"]["symbols"] == [
        "SPX500",
        "US100",
        "GER40",
        "NIKKEI225",
        "XAUUSD",
        "XAGUSD",
        "USOIL",
        "BRENT",
        "EURUSD",
        "ETHUSD",
    ]
    assert cfg["model"]["kind"] == "none"
    assert cfg["backtest"]["engine"] == "portfolio_barrier"
    assert cfg["backtest"]["strategy_path"]["kind"] == "matb"
    assert cfg["backtest"]["allow_short"] is True
    assert all(
        params["risk_per_trade"] == 0.002
        for params in cfg["backtest"]["asset_params"].values()
    )


def test_matb_target_backtest_structural_mismatch_is_rejected() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    invalid = deepcopy(cfg)
    invalid["backtest"]["strategy_path"]["stop_loss_atr"] = 2.5
    with pytest.raises(ConfigValidationError, match="parity mismatch"):
        validate_resolved_config(invalid)


def test_matb_strategy_path_rejects_unknown_keys() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    invalid = deepcopy(cfg)
    invalid["backtest"]["strategy_path"]["silent_override"] = 1
    with pytest.raises(ConfigValidationError, match="unsupported keys"):
        validate_resolved_config(invalid)


def test_matb_signal_rejects_unknown_runtime_parameter() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    invalid = deepcopy(cfg)
    invalid["signals"]["params"]["output_col"] = "signal_side"
    with pytest.raises(ConfigValidationError, match="unsupported keys"):
        validate_resolved_config(invalid)


def test_matb_components_resolve_through_normal_registries() -> None:
    assert "multi_asset_trend_breakout" in FEATURE_REGISTRY
    assert "matb_candidate" in SIGNAL_REGISTRY
    assert "matb_meta_filter" in SIGNAL_REGISTRY
    assert "strategy_path_r" in TARGET_REGISTRY


def test_matb_parameter_neighborhood_is_exactly_27_predeclared_trials() -> None:
    payload = json.loads(Path("config/experiments/matb/declared_trials.json").read_text())
    assert payload["declared_before_backtest"] is True
    assert payload["trial_count"] == 27
    assert len(payload["trials"]) == 27
    assert len(
        {
            (
                trial["trend_threshold"],
                trial["donchian_lookback_days"],
                trial["stop_multiplier_atr"],
            )
            for trial in payload["trials"]
        }
    ) == 27


def test_matb_acceptance_gate_document_has_separate_validated_contract() -> None:
    payload = yaml.safe_load(GATES_PATH.read_text(encoding="utf-8"))
    assert set(payload) == {
        "deterministic_baseline_kill_gates",
        "ml_sample_gates",
        "ml_kill_gates",
    }
    allowed_operators = {">=", ">", "<=", "==", "between"}
    for group in payload.values():
        assert isinstance(group, dict) and group
        for gate in group.values():
            assert set(gate) == {"operator", "threshold"}
            assert gate["operator"] in allowed_operators
