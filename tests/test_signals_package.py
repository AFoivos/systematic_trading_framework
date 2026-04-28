from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    ("module_name", "symbol"),
    [
        ("buy_and_hold_signal", "buy_and_hold_signal"),
        ("conviction_sizing_signal", "conviction_sizing_signal"),
        ("forecast_threshold_signal", "forecast_threshold_signal"),
        ("forecast_vol_adjusted_signal", "forecast_vol_adjusted_signal"),
        ("momentum_strategy", "momentum_strategy"),
        ("orb_candidate_side_signal", "orb_candidate_side_signal"),
        ("probability_vol_adjusted_signal", "probability_vol_adjusted_signal"),
        ("probabilistic_signal", "probabilistic_signal"),
        ("regime_filtered_signal", "regime_filtered_signal"),
        ("rsi_strategy", "rsi_strategy"),
        ("stochastic_strategy", "stochastic_strategy"),
        ("trend_state_long_only_signal", "trend_state_long_only_signal"),
        ("trend_state_signal", "trend_state_signal"),
        ("vol_targeted_signal", "vol_targeted_signal"),
        ("volatility_regime_strategy", "volatility_regime_strategy"),
    ],
)
def test_signal_modules_export_expected_symbol(module_name: str, symbol: str) -> None:
    package = importlib.import_module("src.signals")
    api = importlib.import_module("src.signals.api")
    module = importlib.import_module(f"src.signals.{module_name}")

    exported = getattr(module, symbol)
    assert getattr(package, symbol) is exported
    assert getattr(api, symbol) is exported
