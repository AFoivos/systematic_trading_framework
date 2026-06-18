from __future__ import annotations

import importlib
import inspect
import textwrap
from collections.abc import Mapping
from typing import Callable

import pytest
import yaml

from src.experiments.registry import FEATURE_REGISTRY, SIGNAL_REGISTRY
from src.signals import regime_filtered_signal
from src.utils.config_kinds import SIGNAL_KINDS


def _unique_registrations(registry: Mapping[str, Callable[..., object]]) -> list[tuple[str, Callable[..., object]]]:
    registrations: list[tuple[str, Callable[..., object]]] = []
    seen: set[int] = set()
    for name, fn in registry.items():
        if id(fn) in seen:
            continue
        seen.add(id(fn))
        registrations.append((name, fn))
    return registrations


def _yaml_declaration(fn: Callable[..., object]) -> dict[str, object]:
    docstring = inspect.getdoc(fn)
    assert docstring is not None, f"{fn.__name__} must define a docstring."
    marker = "YAML declaration::"
    assert marker in docstring, f"{fn.__name__} must document its YAML declaration."
    declaration = textwrap.dedent(docstring.split(marker, maxsplit=1)[1]).strip()
    parsed = yaml.safe_load(declaration)
    assert isinstance(parsed, dict), f"{fn.__name__} must contain a valid YAML mapping."
    return parsed


@pytest.mark.parametrize(
    ("module_name", "symbol"),
    [
        ("buy_and_hold_signal", "buy_and_hold_signal"),
        ("conviction_sizing_signal", "conviction_sizing_signal"),
        ("ehlers_continuation_long_signal", "ehlers_continuation_long_signal"),
        ("ehlers_continuation_short_signal", "ehlers_continuation_short_signal"),
        ("ema_rms_ppo_vwap_signal", "ema_rms_ppo_vwap_signal"),
        ("ema_stoch_rsi_pullback_signal", "ema_stoch_rsi_pullback_signal"),
        ("forecast_threshold_signal", "forecast_threshold_signal"),
        ("forecast_vol_adjusted_signal", "forecast_vol_adjusted_signal"),
        ("manual_long_model_filter_signal", "manual_long_model_filter_signal"),
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
        (
            "vwap_rms_ema_cross_long_fractal_filter",
            "vwap_rms_ema_cross_long_fractal_filter_signal",
        ),
        (
            "vwap_rms_ema_cross_long_hmm_gate",
            "vwap_rms_ema_cross_long_hmm_gate_signal",
        ),
        ("vwap_rms_ema_cross_long_signal", "vwap_rms_ema_cross_long_signal"),
    ],
)
def test_signal_modules_export_expected_symbol(module_name: str, symbol: str) -> None:
    package = importlib.import_module("src.signals")
    api = importlib.import_module("src.signals.api")
    module = importlib.import_module(f"src.signals.{module_name}")

    exported = getattr(module, symbol)
    assert getattr(package, symbol) is exported
    assert getattr(api, symbol) is exported


def test_all_registered_features_document_their_yaml_declaration() -> None:
    for name, fn in _unique_registrations(FEATURE_REGISTRY):
        declaration = _yaml_declaration(fn)
        features = declaration.get("features")
        assert isinstance(features, list)
        assert any(isinstance(step, dict) and step.get("step") == name for step in features)


def test_all_registered_signals_document_their_yaml_declaration() -> None:
    for name, fn in _unique_registrations(SIGNAL_REGISTRY):
        declaration = _yaml_declaration(fn)
        signals = declaration.get("signals")
        assert isinstance(signals, dict)
        assert signals.get("kind") == name


def test_all_yaml_signal_kinds_are_named_in_a_signal_docstring() -> None:
    standalone = {"regime_filtered": regime_filtered_signal}
    for name in SIGNAL_KINDS:
        fn = SIGNAL_REGISTRY.get(name, standalone.get(name))
        assert fn is not None
        docstring = inspect.getdoc(fn) or ""
        assert "YAML declaration::" in docstring
        assert name in docstring
