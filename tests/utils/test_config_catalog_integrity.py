"""Repository-wide config and Optuna catalog integrity regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.experiments.optuna_search import (
    load_optuna_spec_yaml,
    prepare_trial_config,
    run_optuna_spec,
    validate_search_space_feature_contract,
)
from src.features.registry import (
    FEATURE_COMPATIBILITY_REGISTRY,
    FEATURE_COMPATIBILITY_VERSION,
    FEATURE_REGISTRY,
)
from src.utils.config import ConfigError, load_experiment_config
from src.utils.config_schemas import (
    BacktestConfig,
    DataConfig,
    ExecutionConfig,
    FeatureStep,
    LoggingConfig,
    ModelConfig,
    ModelStageConfig,
    MonitoringConfig,
    PortfolioConfig,
    RiskConfig,
    SignalsConfig,
)
from src.utils.config_validation import ConfigValidationError, validate_resolved_config
from src.utils.repro import RuntimeConfigError, validate_runtime_config


@pytest.mark.parametrize(
    ("factory", "payload"),
    [
        (FeatureStep.from_dict, {"step": "returns"}),
        (DataConfig.from_dict, {}),
        (ModelConfig.from_dict, {}),
        (ModelStageConfig.from_dict, {}),
        (SignalsConfig.from_dict, {}),
        (RiskConfig.from_dict, {}),
        (BacktestConfig.from_dict, {}),
        (PortfolioConfig.from_dict, {}),
        (MonitoringConfig.from_dict, {}),
        (ExecutionConfig.from_dict, {}),
        (LoggingConfig.from_dict, {}),
    ],
)
def test_execution_bearing_schema_blocks_reject_unknown_keys(
    factory: object,
    payload: dict[str, object],
) -> None:
    invalid = dict(payload)
    invalid["misspelled_knob"] = 1

    with pytest.raises(ValueError, match="unsupported keys.*misspelled_knob"):
        factory(invalid)  # type: ignore[operator]


def test_runtime_rejects_unknown_keys() -> None:
    with pytest.raises(RuntimeConfigError, match="unsupported keys.*sead"):
        validate_runtime_config({"sead": 7})


def test_config_loader_rejects_misspelled_execution_knob(tmp_path: Path) -> None:
    source = Path("config/experiments/others/dense_return_forecasting_v2.yaml")
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    payload["backtest"]["periods_per_yaer"] = 1
    invalid = tmp_path / "misspelled_backtest.yaml"
    invalid.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ConfigError, match="backtest has unsupported keys.*periods_per_yaer"):
        load_experiment_config(invalid)

    resolved = load_experiment_config(source)
    resolved["backtest"]["periods_per_yaer"] = 1
    with pytest.raises(
        ConfigValidationError,
        match="backtest has unsupported keys.*periods_per_yaer",
    ):
        validate_resolved_config(resolved)


def test_explicit_metadata_and_extension_namespaces_are_preserved() -> None:
    cfg = BacktestConfig.from_dict(
        {
            "metadata": {"owner": "research"},
            "extensions": {"vendor": {"knob": 1}},
        }
    )

    resolved = cfg.to_dict()
    assert resolved["metadata"] == {"owner": "research"}
    assert resolved["extensions"] == {"vendor": {"knob": 1}}


_LEGACY_FEATURE_CONFIGS = (
    "config/experiments/others/btcusd_1h_shock_meta_xgboost_long_only.yaml",
    "config/experiments/others/btcusd_30m_shock_meta_xgboost_long_only_v1.yaml",
    "config/experiments/others/dense_return_forecasting_v2.yaml",
    "config/experiments/others/ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_barrier_v2.yaml",
    "config/experiments/others/ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_barrier_v3.yaml",
    "config/experiments/others/ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_v1.yaml",
    "config/experiments/others/ftmo_fx_swing_singleasset_eurusd_m15_ablation_01_rules_only.yaml",
    "config/experiments/others/ftmo_fx_swing_singleasset_eurusd_m15_ablation_02_ml_filter.yaml",
    "config/experiments/others/ftmo_fx_swing_singleasset_eurusd_m15_ablation_03_full.yaml",
    "config/experiments/others/ftmo_fx_swing_singleasset_eurusd_m15_lightgbm_alpha_meta_barrier_v3.yaml",
    "config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_lightgbm_meta_v3.yaml",
    "config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_logistic_meta_v3.yaml",
    "config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_lstm_meta_v3.yaml",
    "config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_xgboost_meta_v3.yaml",
    "config/lab/feature_signal_target_lab.yaml",
)
_NON_EXPERIMENT_YAML_CONFIGS = {
    Path("config/experiments/matb/acceptance_gates.yaml"),
}
_TRACKED_EXPERIMENT_CONFIGS = tuple(
    sorted(
        path
        for path in Path("config/experiments").rglob("*.yaml")
        if path not in _NON_EXPERIMENT_YAML_CONFIGS
    )
    + sorted(Path("config/lab").rglob("*.yaml"))
)


def test_tracked_legacy_feature_configs_load_through_versioned_compatibility_registry() -> None:
    legacy_steps = {"lags", "return_momentum", "vol_normalized_momentum", "volume_features"}
    assert FEATURE_COMPATIBILITY_VERSION == 1
    assert legacy_steps.isdisjoint(FEATURE_REGISTRY)
    assert legacy_steps.issubset(FEATURE_COMPATIBILITY_REGISTRY)

    for config_path in _LEGACY_FEATURE_CONFIGS:
        load_experiment_config(config_path)


@pytest.mark.parametrize(
    "config_path",
    _TRACKED_EXPERIMENT_CONFIGS,
    ids=lambda path: path.as_posix(),
)
def test_every_tracked_experiment_config_loads(config_path: Path) -> None:
    load_experiment_config(config_path)


def test_optuna_catalog_is_runnable_or_explicitly_archived() -> None:
    manifest_path = Path("config/optuna/archive_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archived_paths = set(manifest["specs"])
    specs = sorted(Path("config/optuna").rglob("*.yaml"))

    assert len(specs) == 79
    assert len(archived_paths) == 45
    assert all(Path(path).is_file() for path in archived_paths)

    observed_archived: set[str] = set()
    for spec_path in specs:
        spec = load_optuna_spec_yaml(spec_path)
        repo_path = spec_path.as_posix()
        if spec["archived"]:
            observed_archived.add(repo_path)
            assert spec["archive_reason"]
            continue
        base_path = Path(spec["base_config"])
        assert base_path.is_file(), f"{spec_path} references missing base {base_path}"
        base_config = load_experiment_config(base_path)
        search_space = spec["search_space"]
        validate_search_space_feature_contract(base_config, search_space)
        trial_params: dict[str, object] = {}
        for dimension in search_space:
            if dimension.kind == "categorical":
                trial_params[dimension.name] = list(dimension.choices or [])[0]
            elif dimension.kind == "int":
                trial_params[dimension.name] = int(dimension.low)
            elif dimension.kind == "float":
                trial_params[dimension.name] = float(dimension.low)
            else:
                trial_params[dimension.name] = False
        trial_config = prepare_trial_config(
            base_config,
            trial_params=trial_params,
            search_space=search_space,
            logging_enabled=False,
        )
        validate_resolved_config(trial_config)

    assert observed_archived == archived_paths


def test_archived_optuna_spec_fails_closed_before_optimization() -> None:
    archived = "config/optuna/ehlers/optuna_all_assets_30m_ehlers_cycle_dqn_portfolio_v1.yaml"

    with pytest.raises(ValueError, match="archived and cannot be run"):
        run_optuna_spec(archived, no_report=True)
