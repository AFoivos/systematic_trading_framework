from __future__ import annotations

import pytest

from pathlib import Path

from src.utils.config import load_experiment_config
from src.utils.config_validation import ConfigValidationError, validate_panel_features_block


def test_global_session_relay_ladder_configs_validate() -> None:
    directory = Path("config/experiments/global_session_relay")
    for path in sorted(directory.glob("*.yaml")):
        loaded = load_experiment_config(path)
        assert loaded["backtest"]["signal_col"] == "signal_global_session_relay"


def test_invalid_panel_cluster_member_is_rejected() -> None:
    with pytest.raises(ConfigValidationError, match="absent from data.symbols"):
        validate_panel_features_block(
            [{"step": "global_session_relay", "params": {"clusters": {"usa": {"assets": ["SPX500", "MISSING"], "minimum_active_assets": 2, "require_all_assets": True}}}}],
            symbols={"SPX500"},
        )
