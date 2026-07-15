from __future__ import annotations

import pytest

from pathlib import Path

from src.utils.config import load_experiment_config
from src.utils.config_validation import (
    ConfigValidationError,
    validate_panel_features_block,
    validate_panel_signals_block,
    validate_resolved_config,
)


def test_global_session_relay_ladder_configs_validate() -> None:
    directory = Path("config/experiments/global_session_relay")
    for path in sorted(directory.glob("*.yaml")):
        loaded = load_experiment_config(path)
        assert loaded["backtest"]["signal_col"] == "signal_global_session_relay"


def test_corrected_ladder_declares_exact_module_activation_and_midpoint_execution() -> None:
    directory = Path("config/experiments/global_session_relay")
    corrected = sorted(directory.glob("*_corrected.yaml"))
    assert len(corrected) == 6
    expected_modules = {
        "intra_asia", "intra_europe", "intra_usa", "intra_energy", "intra_metals",
        "asia_to_europe_relay", "europe_to_usa_relay",
    }
    expected_enabled = {
        "v1": {"intra_europe", "intra_usa", "intra_energy", "intra_metals"},
        "v2": {"intra_europe", "intra_usa", "intra_energy", "intra_metals", "europe_to_usa_relay"},
        "v3": {"intra_europe", "intra_usa", "intra_energy", "intra_metals", "europe_to_usa_relay", "asia_to_europe_relay"},
        "v4": {"intra_europe", "intra_usa", "intra_energy", "intra_metals", "europe_to_usa_relay", "asia_to_europe_relay"},
        "v5": {"intra_europe", "intra_usa", "intra_energy", "intra_metals", "europe_to_usa_relay", "asia_to_europe_relay"},
    }
    for path in corrected:
        cfg = load_experiment_config(path)
        modules = cfg["panel_signals"][0]["params"]["enabled_modules"]
        assert set(modules) == expected_modules
        assert not modules["intra_asia"]
        version = next(token for token in expected_enabled if f"_{token}_" in path.name)
        assert {name for name, enabled in modules.items() if enabled} >= expected_enabled[version]
        assert "execution_price_mode" not in cfg["backtest"]
        assert "missing_quote_policy" not in cfg["backtest"]
        assert cfg["backtest"]["annualization_mode"] == "calendar_daily"
        assert cfg["backtest"]["allow_short"] is True


def test_invalid_panel_cluster_member_is_rejected() -> None:
    with pytest.raises(ConfigValidationError, match="absent from data.symbols"):
        validate_panel_features_block(
            [{"step": "global_session_relay", "params": {"clusters": {"usa": {"assets": ["SPX500", "MISSING"], "minimum_active_assets": 2, "require_all_assets": True}}}}],
            symbols={"SPX500"},
        )


def test_unknown_global_session_relay_module_is_rejected() -> None:
    with pytest.raises(ConfigValidationError, match="unsupported modules"):
        validate_panel_signals_block(
            [{"step": "global_session_relay_laggard", "params": {"enabled_modules": {"typo": True}}}],
            symbols={"ETHUSD", "EURUSD", "XAUUSD", "BRENT"},
        )


def test_long_short_portfolio_rejects_explicitly_disabled_short_execution() -> None:
    cfg = load_experiment_config(
        Path("config/experiments/global_session_relay/global_session_relay_laggard_v1_intra_cluster_corrected.yaml")
    )
    cfg["backtest"]["allow_short"] = False
    with pytest.raises(ConfigValidationError, match="incompatible"):
        validate_resolved_config(cfg)
