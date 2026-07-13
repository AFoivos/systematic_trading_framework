from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.experiments.optuna_search import (
    load_search_space_yaml,
    normalize_pruning_spec,
    validate_search_space_feature_contract,
)
from src.experiments.orchestration.artifacts import _resolve_trade_diagnostic_feature_panels
from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.experiments.registry import FEATURE_COMPATIBILITY_REGISTRY, SIGNAL_REGISTRY
from src.signals.manual_long_model_filter_signal import manual_long_model_filter_signal
from src.targets.r_multiple import build_r_multiple_target
from src.utils.config import load_experiment_config


def _require_config_fixture(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.exists():
        pytest.skip(f"optional config fixture not present: {resolved}")
    return resolved


def _manual_condition_frame(periods: int = 4) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="30min")
    return pd.DataFrame(
        {
            "open": [100.0] * periods,
            "high": [101.5] * periods,
            "low": [99.5] * periods,
            "close": [101.0] * periods,
            "is_weekend": [0.0] * periods,
            "roc_12": [0.01] * periods,
            "regime_vol_ratio_z_24_168": [0.2] * periods,
            "mtf_1h_trend_score": [0.0] * periods,
            "mtf_4h_trend_score": [0.0] * periods,
            "close_z": [0.1] * periods,
        },
        index=index,
    )


def test_roc_long_only_conditions_runs_as_pre_model_feature_candidate_step() -> None:
    assert FEATURE_COMPATIBILITY_REGISTRY["roc_long_only_conditions"].__name__ == "roc_long_only_conditions_signal"
    assert SIGNAL_REGISTRY["roc_long_only_conditions"].__name__ == "roc_long_only_conditions_signal"

    out = apply_feature_steps(
        _manual_condition_frame(),
        [
            {
                "step": "roc_long_only_conditions",
                "params": {
                    "long_signal_col": "manual_long_candidate",
                    "vol_adjusted_col": "manual_vol_adjusted_candidate",
                    "score_col": "manual_conviction_score",
                    "all_conditions_col": "manual_all_conditions_signal",
                    "min_score_required": 5,
                    "vol_adjustment_strength": 0.0,
                },
            }
        ],
    )

    assert {"manual_long_candidate", "manual_vol_adjusted_candidate", "manual_conviction_score"}.issubset(out.columns)
    assert {"cond_roc", "cond_vol_regime", "cond_bullish_candle"}.issubset(out.columns)
    assert out["manual_long_candidate"].eq(1).all()
    assert out["manual_vol_adjusted_candidate"].eq(1.0).all()


def test_manual_long_model_filter_signal_only_filters_manual_long_candidates() -> None:
    frame = pd.DataFrame(
        {
            "pred_prob": [0.60, 0.60, 0.54, 0.80],
            "manual_long_candidate": [1, 0, 1, 1],
            "manual_vol_adjusted_candidate": [0.4, 0.7, 0.9, -0.5],
        }
    )

    signal = manual_long_model_filter_signal(frame, threshold=0.55)

    assert signal.name == "model_filtered_long_signal"
    assert signal.tolist() == pytest.approx([0.4, 0.0, 0.0, 0.0])
    assert bool(signal.ge(0.0).all())


def test_manual_long_model_filter_signal_applies_gate_and_min_signal_abs() -> None:
    frame = pd.DataFrame(
        {
            "pred_prob": [0.80, 0.80, 0.80, 0.80],
            "manual_long_candidate": [1, 1, 1, 1],
            "manual_vol_adjusted_candidate": [0.70, 0.80, 0.90, 1.00],
            "session_spx_power": [1, 0, 1, 1],
        }
    )

    signal = manual_long_model_filter_signal(
        frame,
        threshold=0.55,
        gate_col="session_spx_power",
        min_signal_abs=0.80,
    )

    assert signal.tolist() == pytest.approx([0.0, 0.0, 0.9, 1.0])


def test_manual_long_model_filter_signal_supports_any_gate_columns() -> None:
    frame = pd.DataFrame(
        {
            "pred_prob": [0.80, 0.80, 0.80],
            "manual_long_candidate": [1, 1, 1],
            "manual_vol_adjusted_candidate": [1.0, 1.0, 1.0],
            "session_spx_power": [1, 0, 0],
            "session_spx_late": [0, 1, 0],
        }
    )

    signal = manual_long_model_filter_signal(
        frame,
        threshold=0.55,
        gate_cols_any=["session_spx_power", "session_spx_late"],
    )

    assert signal.tolist() == pytest.approx([1.0, 1.0, 0.0])


def test_manual_long_model_filter_signal_can_filter_by_expected_value_r() -> None:
    frame = pd.DataFrame(
        {
            "pred_prob": [0.52, 0.55, 0.70],
            "manual_long_candidate": [1, 1, 1],
            "manual_vol_adjusted_candidate": [0.7, 0.8, 1.0],
        }
    )

    signal = manual_long_model_filter_signal(
        frame,
        threshold=0.50,
        min_expected_value_r=0.50,
        profit_barrier_r=1.8,
        stop_barrier_r=1.0,
    )

    assert signal.tolist() == pytest.approx([0.0, 0.8, 1.0])


def test_manual_long_model_filter_signal_validates_threshold_and_columns() -> None:
    frame = pd.DataFrame(
        {
            "pred_prob": [0.60],
            "manual_long_candidate": [1],
            "manual_vol_adjusted_candidate": [0.4],
        }
    )

    with pytest.raises(ValueError, match="threshold"):
        manual_long_model_filter_signal(frame, threshold=1.0)
    with pytest.raises(ValueError, match="min_signal_abs"):
        manual_long_model_filter_signal(frame, min_signal_abs=-0.1)
    with pytest.raises(ValueError, match="profit_barrier_r"):
        manual_long_model_filter_signal(frame, profit_barrier_r=0.0)
    with pytest.raises(KeyError, match="Missing columns"):
        manual_long_model_filter_signal(frame.drop(columns=["pred_prob"]))
    with pytest.raises(KeyError, match="Missing columns"):
        manual_long_model_filter_signal(frame, gate_col="session_spx_power")
    with pytest.raises(ValueError, match="gate_cols_any"):
        manual_long_model_filter_signal(frame, gate_cols_any="session_spx_power")  # type: ignore[arg-type]


def test_r_multiple_target_uses_manual_long_candidate_for_model_filtering() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="30min")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0, 100.0],
            "high": [100.0, 102.5, 100.0, 100.0, 100.0],
            "low": [100.0, 99.5, 100.0, 100.0, 100.0],
            "close": [100.0, 102.0, 100.0, 100.0, 100.0],
            "manual_long_candidate": [1, 0, 0, 0, 0],
        },
        index=index,
    )

    out, label_col, _, meta = build_r_multiple_target(
        frame,
        {
            "kind": "r_multiple",
            "candidate_col": "manual_long_candidate",
            "entry_price_mode": "next_open",
            "stop_mode": "fixed_return",
            "stop_loss_return": 0.01,
            "take_profit_return": 0.02,
            "target_r_min": 1.0,
            "max_holding_bars": 3,
        },
    )

    assert meta["candidate_col"] == "manual_long_candidate"
    assert label_col == "label"
    assert out.loc[index[0], "r_target_candidate"] == 1
    assert out.loc[index[0], "r_target_entry_price"] == pytest.approx(100.0)
    assert out.loc[index[0], "r_target_exit_reason"] == "take_profit"
    assert out.loc[index[0], "r_target_trade_r"] > 0.0
    assert out.loc[index[0], "label"] == 1.0
    assert np.isnan(out.loc[index[1], "label"])


def test_xauusd_xgboost_r_multiple_filter_config_contracts() -> None:
    cfg = load_experiment_config(_require_config_fixture(
        "config/experiments/roc_long_only/xauusd_roc_long_only_xgboost_r_multiple_filter.yaml"
    ))

    assert cfg["features"][7]["step"] == "roc_long_only_conditions"
    assert cfg["features"][7]["params"]["long_signal_col"] == "manual_long_candidate"
    assert cfg["model"]["kind"] == "xgboost_clf"
    assert cfg["model"]["target"]["kind"] == "r_multiple"
    assert cfg["model"]["target"]["candidate_col"] == "manual_long_candidate"
    assert cfg["model"]["target"]["target_r_min"] == pytest.approx(0.8)
    assert cfg["signals"]["kind"] == "manual_long_model_filter"
    assert cfg["signals"]["params"]["candidate_col"] == "manual_long_candidate"
    assert cfg["signals"]["params"]["threshold"] == pytest.approx(0.42)
    assert cfg["backtest"]["signal_col"] == "model_filtered_long_signal"
    assert cfg["backtest"]["risk_per_trade"] == pytest.approx(0.004)
    assert cfg["backtest"]["dynamic_exits"]["enabled"] is False
    assert cfg["backtest"]["dynamic_exits"]["signal_off_exit"]["exit_price"] == "next_open"
    assert cfg["backtest"]["dynamic_exits"]["profit_lock"]["lock_r"] == pytest.approx(0.3)

    excluded = set(cfg["model"]["feature_selectors"]["exclude"][0]["exact"])
    assert {
        "label",
        "r_target_trade_r",
        "r_target_hit_step",
        "manual_long_candidate",
        "manual_vol_adjusted_candidate",
        "pred_prob",
        "pred_is_oos",
    }.issubset(excluded)


def test_xauusd_xgboost_filter_optuna_yaml_matches_base_config_contract() -> None:
    optuna_path = _require_config_fixture(
        "config/optuna/roc_long_only/optuna_xauusd_roc_long_only_xgboost_r_multiple_filter.yaml"
    )
    payload = yaml.safe_load(optuna_path.read_text(encoding="utf-8"))
    _require_config_fixture(payload["base_config"])
    base_cfg = load_experiment_config(payload["base_config"])
    search_space = load_search_space_yaml(optuna_path)

    validate_search_space_feature_contract(base_cfg, search_space)
    paths = {dimension.path for dimension in search_space}
    by_name = {dimension.name: dimension for dimension in search_space}
    assert "features.7.params.roc_min" in paths
    assert "model.target.target_r_min" in paths
    assert "signals.params.threshold" in paths
    assert "backtest.risk_per_trade" in paths
    assert "model.target.take_profit_r" not in paths
    assert "backtest.take_profit_r" not in paths

    assert by_name["signal_roc_min"].low == pytest.approx(0.0005)
    assert by_name["signal_roc_min"].high == pytest.approx(0.0045)
    assert by_name["signal_min_score_required"].low == 4
    assert by_name["signal_min_score_required"].high == 7
    assert by_name["target_r_min"].low == pytest.approx(0.3)
    assert by_name["target_r_min"].high == pytest.approx(0.8)
    assert by_name["model_probability_threshold"].low == pytest.approx(0.35)
    assert by_name["model_probability_threshold"].high == pytest.approx(0.52)
    assert by_name["model_probability_threshold"].step == pytest.approx(0.01)
    assert by_name["xgb_min_child_weight"].low == pytest.approx(2.0)
    assert by_name["xgb_min_child_weight"].high == pytest.approx(12.0)
    assert list(by_name["backtest_risk_per_trade"].choices or []) == [0.0025, 0.003, 0.0035, 0.004]
    assert list(by_name["xgb_scale_pos_weight"].choices or []) == [1.0, 1.5, 2.0, 3.0]

    constraint_index = {
        (item["metric_path"], item["threshold"]): item
        for item in payload["objective"]["constraints"]
    }
    assert constraint_index[("evaluation.primary_summary.flat_rate", 0.99)]["penalty"] == pytest.approx(3.0)
    assert constraint_index[("evaluation.primary_summary.flat_rate", 0.985)]["penalty"] == pytest.approx(1.0)
    assert constraint_index[("derived.entry_count", 100.0)]["penalty"] == pytest.approx(5.0)
    assert constraint_index[("evaluation.primary_summary.cumulative_return", 0.05)]["penalty"] == pytest.approx(2.0)


def test_spx500_roc_ml_strong_config_wires_validated_gates_and_diagnostics() -> None:
    cfg = load_experiment_config(_require_config_fixture(
        "config/experiments/roc_long_only/V2/spx500_roc_long_only_xgboost_r_multiple_filter_strong.yaml"
    ))

    feature_steps = [step["step"] for step in cfg["features"]]
    assert "trend_slope_volatility" in feature_steps
    assert "volatility_of_volatility" in feature_steps

    roc_params = next(step["params"] for step in cfg["features"] if step["step"] == "roc_long_only_conditions")
    session_params = next(step["params"] for step in cfg["features"] if step["step"] == "session_context")
    assert session_params["sessions"]["spx_power"] == [15, 18]
    assert session_params["sessions"]["spx_late"] == [20, 23]
    assert roc_params["macro_condition_col"] is None
    assert roc_params["vol_adjustment_strength"] == pytest.approx(1.7)
    assert roc_params["vol_z_max"] == pytest.approx(2.1)
    assert cfg["model"]["target"]["target_r_min"] == pytest.approx(0.5)

    signal_params = cfg["signals"]["params"]
    assert signal_params["gate_cols_any"] == ["session_spx_power", "session_spx_late"]
    assert signal_params["min_signal_abs"] == pytest.approx(0.75)
    assert signal_params["min_expected_value_r"] == pytest.approx(0.18)
    assert signal_params["profit_barrier_r"] == pytest.approx(cfg["backtest"]["take_profit_r"])
    assert signal_params["stop_barrier_r"] == pytest.approx(cfg["backtest"]["stop_loss_r"])

    dynamic_exits = cfg["backtest"]["dynamic_exits"]
    assert dynamic_exits["enabled"] is False
    assert dynamic_exits["breakeven"]["enabled"] is True
    assert dynamic_exits["profit_lock"]["enabled"] is True


def test_xauusd_dynamic_exit_optuna_yaml_only_tunes_exit_params() -> None:
    optuna_path = _require_config_fixture(
        "config/optuna/roc_long_only/optuna_xauusd_roc_long_only_xgboost_r_multiple_filter_dynamic_exits.yaml"
    )
    payload = yaml.safe_load(optuna_path.read_text(encoding="utf-8"))
    _require_config_fixture(payload["base_config"])
    base_cfg = load_experiment_config(payload["base_config"])
    search_space = load_search_space_yaml(optuna_path)

    validate_search_space_feature_contract(base_cfg, search_space)
    paths = {dimension.path for dimension in search_space}
    assert paths == {
        "backtest.dynamic_exits.signal_off_exit.min_bars_held",
        "backtest.dynamic_exits.breakeven.trigger_r",
        "backtest.dynamic_exits.profit_lock.trigger_r",
        "backtest.dynamic_exits.profit_lock.lock_r",
        "backtest.dynamic_exits.no_progress.bars",
        "backtest.dynamic_exits.no_progress.min_favorable_r",
    }


def test_spx500_v2_config_and_optuna_contracts() -> None:
    base_path = _require_config_fixture(
        "config/experiments/roc_long_only/V2/spx500_roc_long_only_xgboost_r_multiple_filter_v2.yaml"
    )
    optuna_path = _require_config_fixture(
        "config/optuna/roc_long_only/V2/optuna_spx500_roc_long_only_xgboost_r_multiple_filter_v2.yaml"
    )

    cfg = load_experiment_config(base_path)
    payload = yaml.safe_load(optuna_path.read_text(encoding="utf-8"))
    search_space = load_search_space_yaml(optuna_path)

    assert payload["base_config"] == str(base_path)
    assert cfg["features"][6]["step"] == "swing_extrema_context"
    assert cfg["features"][7]["step"] == "roc_long_only_conditions"
    assert cfg["features"][7]["params"]["require_bullish_candle"] is True
    assert cfg["model"]["split"]["test_size"] == 5600
    assert cfg["model"]["split"]["max_folds"] == 8
    assert cfg["backtest"]["dynamic_exits"]["enabled"] is True
    assert cfg["backtest"]["dynamic_exits"]["breakeven"]["enabled"] is True
    assert cfg["backtest"]["dynamic_exits"]["profit_lock"]["enabled"] is True
    assert cfg["backtest"]["dynamic_exits"]["no_progress"]["enabled"] is False

    validate_search_space_feature_contract(cfg, search_space)
    paths = {dimension.path for dimension in search_space}
    assert "features.6.params.overextended_long_threshold_atr" in paths
    assert "features.7.params.roc_min" in paths
    assert "features.7.params.require_bullish_candle" in paths
    assert "signals.params.threshold" in paths
    assert "backtest.dynamic_exits.breakeven.trigger_r" in paths
    assert "backtest.dynamic_exits.profit_lock.lock_r" in paths

    excluded = set(cfg["model"]["feature_selectors"]["exclude"][0]["exact"])
    assert {
        "mtf_1h_atr",
        "mtf_4h_atr",
        "swing_raw_local_high",
        "swing_raw_local_low",
        "pre_local_high_3",
        "pre_local_low_3",
    }.issubset(excluded)


def test_spx500_v2_relaxed_config_and_optuna_contracts() -> None:
    base_path = _require_config_fixture(
        "config/experiments/roc_long_only/V2/spx500_roc_long_only_xgboost_r_multiple_filter_v2_relaxed.yaml"
    )
    optuna_path = _require_config_fixture(
        "config/optuna/roc_long_only/V2/optuna_spx500_roc_long_only_xgboost_r_multiple_filter_v2_relaxed.yaml"
    )

    cfg = load_experiment_config(base_path)
    payload = yaml.safe_load(optuna_path.read_text(encoding="utf-8"))
    search_space = load_search_space_yaml(optuna_path)
    pruning = normalize_pruning_spec(payload["pruning"])

    assert payload["base_config"] == str(base_path)
    assert payload["study"]["n_trials"] == 160
    assert cfg["features"][8]["params"]["mtf_1h_min"] == pytest.approx(0.0015)
    assert cfg["features"][8]["params"]["mtf_4h_min"] == pytest.approx(0.0005)
    assert cfg["features"][8]["params"]["min_score_required"] == 7
    assert cfg["features"][8]["params"]["require_bullish_candle"] is False
    assert cfg["signals"]["params"]["threshold"] == pytest.approx(0.44)
    assert cfg["backtest"]["dynamic_exits"]["breakeven"]["trigger_r"] == pytest.approx(0.9)
    assert cfg["backtest"]["dynamic_exits"]["breakeven"]["lock_r"] == pytest.approx(0.1)
    assert cfg["backtest"]["dynamic_exits"]["profit_lock"]["trigger_r"] == pytest.approx(1.2)
    assert cfg["backtest"]["dynamic_exits"]["profit_lock"]["lock_r"] == pytest.approx(0.4)

    validate_search_space_feature_contract(cfg, search_space)
    by_name = {dimension.name: dimension for dimension in search_space}
    assert by_name["signal_mtf_1h_min"].low == pytest.approx(-0.0020)
    assert by_name["signal_mtf_1h_min"].high == pytest.approx(0.0030)
    assert by_name["signal_mtf_4h_min"].low == pytest.approx(-0.0005)
    assert by_name["signal_mtf_4h_min"].high == pytest.approx(0.0030)
    assert list(by_name["signal_min_score_required"].choices or []) == [6, 7, 8]
    assert by_name["model_probability_threshold"].low == pytest.approx(0.41)
    assert by_name["model_probability_threshold"].high == pytest.approx(0.46)
    assert list(by_name["breakeven_trigger_r"].choices or []) == [0.9, 1.0]
    assert list(by_name["profit_lock_trigger_r"].choices or []) == [1.2, 1.3]
    assert list(by_name["profit_lock_r"].choices or []) == [0.3, 0.4]
    assert pruning.enabled is True
    assert pruning.metric_path == "classification_metrics.roc_auc"
    assert pruning.direction == "maximize"
    assert pruning.stage_filter == ("xgboost_clf",)
    assert pruning.pruner == "median"
    assert pruning.n_startup_trials == 20
    assert pruning.n_warmup_steps == 2
    assert pruning.interval_steps == 1


def test_trade_diagnostics_feature_panels_follow_trial_specific_column_names() -> None:
    frame = pd.DataFrame(
        {
            "roc_8": [0.001, 0.002],
            "regime_vol_ratio_z_12_96": [0.1, 0.2],
            "close_z": [0.0, 0.3],
            "close_open_ratio": [0.0001, 0.0002],
            "manual_conviction_score": [4, 6],
        }
    )
    cfg = {
        "features": [
            {"step": "returns", "params": {}},
            {
                "step": "roc_long_only_conditions",
                "params": {
                    "roc_window": 8,
                    "vol_short_window": 12,
                    "vol_long_window": 96,
                    "score_col": "manual_conviction_score",
                },
            },
        ],
        "model": {
            "target": {
                "diagnostic_feature_cols": [
                    "roc_12",
                    "regime_vol_ratio_z_24_168",
                    "close_z",
                    "close_open_ratio",
                    "manual_conviction_score",
                ]
            }
        },
    }

    resolved = _resolve_trade_diagnostic_feature_panels(frame, cfg)

    assert resolved == [
        "roc_8",
        "regime_vol_ratio_z_12_96",
        "close_z",
        "close_open_ratio",
        "manual_conviction_score",
    ]
