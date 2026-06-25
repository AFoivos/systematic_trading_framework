from __future__ import annotations

import inspect
import importlib
import json
from pathlib import Path
from collections.abc import Callable, Mapping

import numpy as np
import pandas as pd
import pytest
import yaml

from src.features.registry import FEATURE_COMPATIBILITY_REGISTRY, FEATURE_REGISTRY, get_feature_fn
from src.models.registry import MODEL_REGISTRY, get_model_fn
from src.pipelines.canonical_pipeline import run_canonical_pipeline
from src.pipelines.registry import PIPELINE_REGISTRY, get_pipeline_fn
from src.signals.registry import DEPRECATED_SIGNAL_ALIASES, SIGNAL_REGISTRY, get_signal_fn
from src.targets.registry import TARGET_REGISTRY, build_target, get_target_builder
from src.utils.registry import RegistryDefinitionError, RegistryLookupError, build_registry


def _extract_yaml_block(raw: str) -> str:
    lines = inspect.cleandoc(raw).splitlines()
    block: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if block and stripped in {"Required input columns", "Parameters", "Returns", "Notes", "Examples"}:
            break
        if block and index + 1 < len(lines) and stripped and set(lines[index + 1].strip()) <= {"-"}:
            break
        block.append(line)
    return "\n".join(block).strip()


def _assert_registered_docstring_contract(
    category: str,
    registry: Mapping[str, Callable[..., object]],
) -> None:
    for name, fn in registry.items():
        resolved = getattr(importlib.import_module(fn.__module__), fn.__name__)
        docstring = inspect.getdoc(resolved)
        assert docstring is not None, f"{category} '{name}' must define a docstring."
        assert "YAML declaration::" in docstring, f"{category} '{name}' must document YAML usage."
        assert "Required input columns" in docstring, f"{category} '{name}' must document input columns."
        assert "Parameters" in docstring, f"{category} '{name}' must document parameters."
        yaml_block = _extract_yaml_block(docstring.split("YAML declaration::", maxsplit=1)[1])
        assert isinstance(yaml.safe_load(yaml_block), dict), f"{category} '{name}' YAML block must parse."


def _synthetic_ohlcv(periods: int = 90) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="D")
    trend = np.linspace(0.0, 0.12, periods)
    seasonal = 0.01 * np.sin(np.arange(periods) / 4.0)
    close = 100.0 * (1.0 + trend + seasonal)
    frame = pd.DataFrame(index=idx)
    frame["close"] = close
    frame["open"] = frame["close"].shift(1).fillna(frame["close"].iloc[0])
    frame["high"] = np.maximum(frame["open"], frame["close"]) * 1.002
    frame["low"] = np.minimum(frame["open"], frame["close"]) * 0.998
    frame["volume"] = 10_000.0
    return frame[["open", "high", "low", "close", "volume"]]


def test_category_registries_expose_only_canonical_names() -> None:
    assert "roc" in FEATURE_REGISTRY
    assert "rate_of_change" not in FEATURE_REGISTRY
    assert "vwap_rms_ema_cross_long" not in FEATURE_REGISTRY
    assert "vwap_rms_ema_cross_long" in FEATURE_COMPATIBILITY_REGISTRY

    assert "ehlers_continuation_short" in SIGNAL_REGISTRY
    assert "ehlers_continuation_short_signal" not in SIGNAL_REGISTRY
    assert "ehlers_continuation_short_signal" in DEPRECATED_SIGNAL_ALIASES

    assert "forward_return" in TARGET_REGISTRY
    assert "logistic_regression_clf" in MODEL_REGISTRY
    assert "canonical_experiment" in PIPELINE_REGISTRY


def test_registry_duplicate_names_fail_fast() -> None:
    with pytest.raises(RegistryDefinitionError, match="Duplicate demo registry name"):
        build_registry("demo", [("x", object()), ("x", object())])


def test_unknown_component_errors_are_informative() -> None:
    with pytest.raises(RegistryLookupError, match="Unknown feature 'does_not_exist'.*roc"):
        get_feature_fn("does_not_exist")
    with pytest.raises(RegistryLookupError, match="Unknown signal 'does_not_exist'.*forecast_threshold"):
        get_signal_fn("does_not_exist")
    with pytest.raises(RegistryLookupError, match="Unknown target 'does_not_exist'.*forward_return"):
        get_target_builder("does_not_exist")
    with pytest.raises(RegistryLookupError, match="Unknown model 'does_not_exist'.*logistic_regression_clf"):
        get_model_fn("does_not_exist")
    with pytest.raises(RegistryLookupError, match="Unknown pipeline 'does_not_exist'.*canonical_experiment"):
        get_pipeline_fn("does_not_exist")


def test_config_name_resolution_uses_target_registry() -> None:
    frame = _synthetic_ohlcv(periods=8)
    out, label_col, fwd_col, meta = build_target(
        frame,
        {"kind": "forward_return", "price_col": "close", "horizon": 2},
    )

    assert label_col == "label"
    assert fwd_col == "target_fwd_2"
    assert meta["kind"] == "forward_return"
    assert out[fwd_col].notna().sum() == 6


def test_pipeline_registry_points_to_canonical_pipeline() -> None:
    assert get_pipeline_fn("canonical_experiment") is run_canonical_pipeline


def test_registered_components_have_usage_docstring_contract() -> None:
    _assert_registered_docstring_contract("feature", FEATURE_REGISTRY)
    _assert_registered_docstring_contract("signal", SIGNAL_REGISTRY)
    _assert_registered_docstring_contract("target", TARGET_REGISTRY)
    _assert_registered_docstring_contract("model", MODEL_REGISTRY)


def test_canonical_pipeline_smoke_experiment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("scipy")
    import src.experiments.runner as runner_mod

    def _mock_load_ohlcv(*args: object, **kwargs: object) -> pd.DataFrame:
        return _synthetic_ohlcv(periods=90)

    monkeypatch.setattr(runner_mod, "load_ohlcv", _mock_load_ohlcv)

    config_path = tmp_path / "canonical_smoke.yaml"
    config = {
        "data": {
            "symbol": "AAA",
            "source": "yahoo",
            "interval": "1d",
            "start": "2024-01-01",
        },
        "features": [
            {"step": "returns", "params": {"log": False, "col_name": "close_ret"}},
            {"step": "roc", "params": {"window": 3}},
        ],
        "model": {"kind": "none"},
        "signals": {"kind": "none", "params": {"signal_col": "flat_signal"}},
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 2},
        "portfolio": {"enabled": False},
        "backtest": {
            "returns_col": "close_ret",
            "signal_col": "flat_signal",
            "returns_type": "simple",
            "periods_per_year": 252,
        },
        "logging": {"enabled": False},
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = get_pipeline_fn("canonical_experiment")(config_path)

    assert isinstance(result.data, pd.DataFrame)
    assert {"close_ret", "roc_3", "flat_signal", "target_fwd_2", "label"}.issubset(result.data.columns)
    assert result.model is None
    assert result.evaluation["primary_summary"] is not None
