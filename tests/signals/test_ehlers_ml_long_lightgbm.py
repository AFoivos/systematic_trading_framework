from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from src.evaluation.time_splits import assert_no_forward_label_leakage, build_time_splits
from src.experiments.optuna_search import (
    extract_objective_value,
    get_nested_value,
    load_optuna_spec_yaml,
    run_optuna_spec,
)
from src.experiments.support.ehlers_ml_ablation import (
    RAW_EHLERS_FEATURES,
    build_ehlers_ml_ablation_configs,
)
from src.experiments.orchestration.feature_stage import apply_signal_step
from src.experiments.orchestration.model_stage import synchronize_asset_frames_for_model
from src.experiments.orchestration.types import ExperimentResult
from src.models.classification.base import train_forward_classifier
from src.features.ehlers_ml_long_candidate import ehlers_ml_long_candidate_feature
from src.utils.config import load_experiment_config
from src.utils.config_validation import validate_resolved_config


EXPERIMENT = "config/experiments/ehlers/ehlers_ml_long_lightgbm_30m_v1.yaml"
SMOKE_OPTUNA = "config/optuna/ehlers/optuna_ehlers_ml_long_lightgbm_30m_v1_smoke.yaml"
EXPERIMENT_V2 = "config/experiments/ehlers/ehlers_ml_long_lightgbm_30m_v2.yaml"

EXPECTED_MODEL_FEATURES = {
    "mama",
    "fama",
    "mama_minus_fama",
    "close_minus_decycler",
    "instantaneous_trendline_slope",
    "decycler_slope",
    "frama_slope",
    "supersmoother_slope",
    "roofing_filter",
    "roofing_filter_slope",
    "hilbert_amplitude",
    "hilbert_instantaneous_frequency",
    "dominant_cycle_period",
    "dominant_cycle_phase_normalized",
    "sinewave",
    "lead_sine",
    "cyber_cycle",
    "cyber_cycle_signal",
    "even_better_sinewave",
    "autocorrelation_periodogram_period",
    "homodyne_period",
    "fisher_transform",
    "inverse_fisher_transform",
    "decycler_oscillator",
    "laguerre_rsi",
    "center_of_gravity",
}


def _require_config_fixture(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.exists():
        pytest.skip(f"optional config fixture not present: {resolved}")
    return resolved


def _candidate_input(n: int = 900) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=n, freq="30min", tz="UTC")
    x = np.arange(n, dtype=float)
    close = 100.0 + 1.8 * np.sin(2.0 * np.pi * x / 20.0) + 0.002 * x
    amplitude = 1.0 + 0.8 * np.sin(2.0 * np.pi * x / 37.0)
    return pd.DataFrame(
        {
            "open": close + 0.05 * np.sin(x),
            "high": close + 0.65,
            "low": close - 0.65,
            "close": close,
            "mama": close + 0.10 * np.sin(x / 3.0),
            "fama": close - 0.10 * np.sin(x / 3.0),
            "decycler": close - 0.15 * np.cos(x / 5.0),
            "instantaneous_trendline": close - 0.05 * np.sin(x / 4.0),
            "frama": close - 0.08 * np.cos(x / 6.0),
            "supersmoother": close - 0.04 * np.cos(x / 7.0),
            "roofing_filter": np.sin(2.0 * np.pi * x / 20.0),
            "hilbert_amplitude": amplitude,
            "dominant_cycle_period": np.full(n, 20.0),
            "dominant_cycle_phase": np.mod(x * 18.0, 360.0),
            "atr_over_price_20": np.full(n, 0.004),
            "atr_20": np.full(n, 0.4),
        },
        index=index,
    )


def test_experiment_config_is_isolated_and_complete() -> None:
    cfg = load_experiment_config(_require_config_fixture(EXPERIMENT))

    assert cfg["strategy"]["assets"] == ["SPX500", "US100", "GER40", "XAUUSD", "EURUSD"]
    assert set(cfg["model"]["feature_cols"]) == EXPECTED_MODEL_FEATURES
    assert cfg["model"]["kind"] == "lightgbm_clf"
    assert cfg["model"]["target"]["entry_price_mode"] == "next_open"
    assert cfg["model"]["target"]["upper_mult"] == pytest.approx(2.0)
    assert cfg["model"]["target"]["lower_mult"] == pytest.approx(1.25)
    assert cfg["model"]["target"]["max_holding"] == 12
    assert cfg["signals"]["params"]["threshold"] == pytest.approx(0.55)
    assert "vwap" not in cfg["strategy"]["name"].lower()


def test_v2_enables_all_seven_improvement_contracts() -> None:
    cfg = load_experiment_config(_require_config_fixture(EXPERIMENT_V2))

    assert cfg["model"]["split"]["synchronize_assets"] is True
    assert cfg["model"]["split"]["max_folds"] is None
    assert cfg["model"]["calibration"]["method"] == "sigmoid"
    assert cfg["model"]["params"]["class_weight"] is None
    assert all("mama" != feature and "fama" != feature for feature in cfg["model"]["feature_cols"])
    assert cfg["features"][22]["params"]["amplitude_min_quantile"] == pytest.approx(0.55)
    assert cfg["signals"]["params"]["round_trip_cost_return"] == pytest.approx(0.00050)
    assert cfg["signals"]["params"]["min_expected_value_r"] == pytest.approx(0.0)


def test_v2_ablation_variants_are_standalone_and_comparable() -> None:
    _require_config_fixture(EXPERIMENT_V2)
    variants = build_ehlers_ml_ablation_configs(EXPERIMENT_V2)

    assert set(variants) == {"full_normalized", "indices_normalized", "full_raw"}
    for cfg in variants.values():
        validate_resolved_config(cfg)
        assert "extends" not in cfg
    assert variants["indices_normalized"]["strategy"]["assets"] == ["SPX500", "US100"]
    assert variants["full_raw"]["model"]["feature_cols"] == RAW_EHLERS_FEATURES
    assert variants["full_normalized"]["model"]["feature_cols"] != RAW_EHLERS_FEATURES


def test_candidate_rows_are_causal_generated_and_long_only() -> None:
    source = _candidate_input(300)
    original = source.copy(deep=True)
    out = ehlers_ml_long_candidate_feature(source, amplitude_lookback=32)
    prefix = ehlers_ml_long_candidate_feature(source.iloc[:220], amplitude_lookback=32)

    pd.testing.assert_frame_equal(source, original)
    assert int(out["ehlers_ml_candidate"].sum()) > 0
    assert set(out["signal_side"].unique()) <= {0, 1}
    pd.testing.assert_series_equal(
        out.loc[prefix.index, "ehlers_ml_candidate"],
        prefix["ehlers_ml_candidate"],
    )


def test_stationary_ehlers_features_are_atr_normalized() -> None:
    source = _candidate_input(300)
    out = ehlers_ml_long_candidate_feature(source, amplitude_lookback=32, atr_col="atr_20")

    expected = (source["mama"] - source["close"]) / source["atr_20"]
    pd.testing.assert_series_equal(
        out["mama_minus_close_over_atr"].astype(float),
        expected.rename("mama_minus_close_over_atr"),
        check_dtype=False,
    )
    assert np.isfinite(out["hilbert_amplitude_over_atr"].dropna()).all()


def test_asset_synchronization_uses_common_timestamps() -> None:
    left = _candidate_input(500)
    right = _candidate_input(500).iloc[25:].copy()
    frames, meta = synchronize_asset_frames_for_model(
        {"LEFT": left, "RIGHT": right},
        enabled=True,
    )

    assert frames["LEFT"].index.equals(frames["RIGHT"].index)
    assert frames["LEFT"].index.equals(right.index)
    assert meta["method"] == "common_timestamp_intersection"
    assert meta["dropped_rows"] == {"LEFT": 25, "RIGHT": 0}


def test_purged_walk_forward_has_no_forward_label_leakage() -> None:
    cfg = load_experiment_config(_require_config_fixture(EXPERIMENT))
    split_cfg = cfg["model"]["split"]
    horizon = int(cfg["model"]["target"]["max_holding"])
    splits = build_time_splits(
        method="purged",
        n_samples=60000,
        split_cfg=split_cfg,
        target_horizon=horizon,
    )

    assert splits
    assert split_cfg["purge_bars"] >= horizon
    assert split_cfg["embargo_bars"] >= horizon
    for split in splits:
        assert int(split.train_idx.max()) < int(split.test_idx.min()) - horizon
        assert_no_forward_label_leakage(
            split.train_idx,
            test_start=int(split.test_start),
            target_horizon=horizon,
        )


def test_lightgbm_emits_oos_probability_only_for_candidates() -> None:
    frame = ehlers_ml_long_candidate_feature(_candidate_input(), amplitude_lookback=32)
    frame["ehlers_ml_candidate"] = 0
    frame["signal_side"] = 0
    candidate_positions = np.arange(36, len(frame) - 7, 3)
    frame.iloc[candidate_positions, frame.columns.get_loc("ehlers_ml_candidate")] = 1
    frame.iloc[candidate_positions, frame.columns.get_loc("signal_side")] = 1
    frame["high"] = frame["close"] + 0.05
    frame["low"] = frame["close"] - 0.05
    for event_number, position in enumerate(candidate_positions):
        entry_position = position + 1
        entry = float(frame.iloc[position]["close"])
        frame.iloc[entry_position, frame.columns.get_loc("open")] = entry
        if event_number % 2 == 0:
            frame.iloc[entry_position, frame.columns.get_loc("high")] = entry * 1.01
            frame.iloc[entry_position, frame.columns.get_loc("low")] = entry * 0.999
        else:
            frame.iloc[entry_position, frame.columns.get_loc("high")] = entry * 1.001
            frame.iloc[entry_position, frame.columns.get_loc("low")] = entry * 0.99
    model_cfg = {
        "kind": "lightgbm_clf",
        "pred_prob_col": "ehlers_long_probability",
        "pred_is_oos_col": "pred_is_oos",
        "pred_raw_prob_col": "ehlers_long_probability_raw",
        "calibration": {"method": "sigmoid", "fraction": 0.20, "min_rows": 30},
        "feature_cols": ["mama_minus_fama", "roofing_filter", "dominant_cycle_phase_normalized"],
        "target": {
            "kind": "triple_barrier",
            "candidate_col": "ehlers_ml_candidate",
            "candidate_out_col": "ehlers_ml_target_candidate",
            "side_col": "signal_side",
            "label_mode": "meta",
            "label_col": "label",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "volatility_col": "atr_over_price_20",
            "entry_price_mode": "next_open",
            "upper_mult": 1.0,
            "lower_mult": 1.0,
            "max_holding": 6,
            "neutral_label": "lower",
            "tie_break": "closest_to_open",
        },
        "split": {
            "method": "purged",
            "train_size": 360,
            "test_size": 180,
            "step_size": 180,
            "max_folds": 3,
            "expanding": True,
            "purge_bars": 6,
            "embargo_bars": 6,
        },
        "params": {
            "n_estimators": 20,
            "learning_rate": 0.05,
            "num_leaves": 7,
            "random_state": 7,
            "n_jobs": 1,
            "verbosity": -1,
        },
    }

    out, _, meta = train_forward_classifier(
        frame,
        model_cfg,
        model_kind="lightgbm_clf",
        estimator_family="lightgbm",
        estimator_factory=lambda params: LogisticRegression(
            random_state=int(params.get("random_state", 7)),
            max_iter=200,
        ),
    )

    assert "ehlers_long_probability" in out.columns
    assert "ehlers_long_probability_raw" in out.columns
    predicted = out["ehlers_long_probability"].notna()
    assert bool(predicted.any())
    assert out.loc[predicted, "pred_is_oos"].all()
    assert out.loc[predicted, "ehlers_ml_candidate"].eq(1).all()
    assert meta["prediction_diagnostics"]["non_oos_prediction_rows"] == 0
    assert any(
        fold["calibration"]["enabled"]
        and fold["calibration"]["fit_end_position"]
        < fold["calibration"]["calibration_start_position"] - 6
        for fold in meta["folds"]
    )


def test_probability_threshold_signal_is_long_only() -> None:
    cfg = load_experiment_config(_require_config_fixture(EXPERIMENT))
    frame = ehlers_ml_long_candidate_feature(_candidate_input(300), amplitude_lookback=32)
    frame["ehlers_long_probability"] = np.where(frame["ehlers_ml_candidate"].eq(1), 0.60, 0.90)
    out = apply_signal_step(frame, cfg["signals"])

    assert set(out["ehlers_ml_long_signal"].unique()) <= {0.0, 1.0}
    assert out.loc[frame["ehlers_ml_candidate"].eq(0), "ehlers_ml_long_signal"].eq(0.0).all()


def test_cost_aware_expected_value_gate_rejects_thin_edge() -> None:
    frame = ehlers_ml_long_candidate_feature(_candidate_input(300), amplitude_lookback=32)
    frame["ehlers_long_probability"] = 0.55
    signal_cfg = {
        "kind": "manual_long_model_filter",
        "params": {
            "prob_col": "ehlers_long_probability",
            "candidate_col": "ehlers_ml_candidate",
            "base_signal_col": "signal_side",
            "threshold": 0.50,
            "profit_barrier_r": 2.0,
            "stop_barrier_r": 1.25,
            "volatility_col": "atr_over_price_20",
            "round_trip_cost_return": 0.01,
            "min_expected_value_r": 0.0,
            "signal_col": "cost_aware_signal",
        },
    }

    out = apply_signal_step(frame, signal_cfg)
    assert out["cost_aware_signal"].eq(0.0).all()


def test_summary_metric_paths_match_artifact_namespace() -> None:
    primary = {
        "sharpe": 1.2,
        "cumulative_return": 0.10,
        "max_drawdown": -0.08,
        "profit_factor": 1.25,
        "trade_count": 300.0,
        "cost_to_gross_pnl": 0.25,
        "robustness_cost_x2_profit_factor": 1.05,
        "robustness_cost_x3_max_drawdown": -0.09,
        "robustness_delay_1_bars_profit_factor": 1.02,
    }
    result = ExperimentResult(
        config={},
        data=pd.DataFrame(),
        backtest=SimpleNamespace(summary=primary),
        model=None,
        model_meta={},
        artifacts={},
        evaluation={"primary_summary": primary},
        monitoring={},
        execution={},
    )
    spec = load_optuna_spec_yaml(SMOKE_OPTUNA)

    assert extract_objective_value(result, spec["objective"]) == pytest.approx(1.2)
    for constraint in spec["objective"].constraints:
        assert get_nested_value(result, constraint.metric_path) is not None


def test_smoke_optuna_executes_at_least_two_trials(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_config_fixture(EXPERIMENT)
    _require_config_fixture(SMOKE_OPTUNA)
    from src.experiments import optuna_search as optuna_mod

    class Trial:
        def __init__(self, number: int) -> None:
            self.number = number
            self.params: dict[str, object] = {}
            self.user_attrs: dict[str, object] = {}

        def suggest_int(self, name: str, *, low: int, **_: object) -> int:
            self.params[name] = low
            return low

        def suggest_float(self, name: str, *, low: float, **_: object) -> float:
            self.params[name] = low
            return low

        def suggest_categorical(self, name: str, choices: list[object]) -> object:
            self.params[name] = choices[0]
            return choices[0]

        def set_user_attr(self, key: str, value: object) -> None:
            self.user_attrs[key] = value

    class Study:
        def __init__(self) -> None:
            self.user_attrs: dict[str, object] = {}
            self.trials: list[SimpleNamespace] = []

        def set_user_attr(self, key: str, value: object) -> None:
            self.user_attrs[key] = value

        def optimize(self, objective, *, n_trials: int, **_: object) -> None:
            for number in range(n_trials):
                trial = Trial(number)
                self.trials.append(SimpleNamespace(number=number, value=objective(trial), params=trial.params))

    class FakeOptuna:
        class samplers:
            class TPESampler:
                def __init__(self, **_: object) -> None:
                    pass

            RandomSampler = TPESampler

        class pruners:
            class NopPruner:
                def __init__(self, **_: object) -> None:
                    pass

        def create_study(self, **_: object) -> Study:
            return Study()

    metrics = {
        "sharpe": 1.0,
        "cumulative_return": 0.10,
        "max_drawdown": -0.05,
        "profit_factor": 1.25,
        "trade_count": 300.0,
        "cost_to_gross_pnl": 0.20,
        "robustness_cost_x2_profit_factor": 1.05,
        "robustness_cost_x3_max_drawdown": -0.09,
        "robustness_delay_1_bars_profit_factor": 1.05,
    }
    monkeypatch.setattr(optuna_mod, "_require_optuna", lambda: FakeOptuna())
    monkeypatch.setattr(
        optuna_mod,
        "_run_experiment_from_config",
        lambda cfg, config_path: SimpleNamespace(summary=metrics, evaluation={"primary_summary": metrics}, artifacts={}),
    )

    study = run_optuna_spec(SMOKE_OPTUNA, n_trials=2, no_report=True)

    assert len(study.trials) >= 2
    assert all(np.isfinite(trial.value) for trial in study.trials)
