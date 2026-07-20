from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.classification.logistic_regression import train_logistic_regression_classifier
from src.models.forecasting.base import train_lightgbm_regressor
from src.models.common.runtime import probe_lightgbm_runtime
from src.experiments.orchestration.model_stage import apply_model_pipeline_to_assets
from src.targets.registry import TARGET_REGISTRY, build_target
from src.utils.config import load_experiment_config
from src.utils.config_validation import ConfigValidationError, validate_model_block


def _frame(rows: int = 8) -> pd.DataFrame:
    index = pd.date_range("2024-01-01 09:00", periods=rows, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "open": [100.0] * rows,
            "high": [100.2] * rows,
            "low": [99.8] * rows,
            "close": [100.0] * rows,
            "atr_over_price": [0.01] * rows,
            "candidate": [1.0] + [0.0] * (rows - 1),
            "side": [1.0] + [0.0] * (rows - 1),
            "feature_x": np.linspace(-1.0, 1.0, rows),
        },
        index=index,
    )


def _cfg(kind: str, **overrides: object) -> dict[str, object]:
    cfg: dict[str, object] = {
        "kind": kind,
        "candidate_col": "candidate",
        "side_col": "side",
        "volatility_col": "atr_over_price",
        "entry_price_mode": "next_open",
        "stop_mode": "volatility_stop",
        "take_profit_r": 2.0,
        "stop_loss_r": 1.0,
        "max_holding_bars": 3,
        "tie_break": "conservative",
        "allow_partial_horizon": False,
    }
    cfg.update(overrides)
    return cfg


def test_trade_evaluation_targets_are_registered() -> None:
    assert {
        "expected_realized_r",
        "target_before_stop_probability",
        "trade_mfe_mae_regression",
    } <= set(TARGET_REGISTRY)


def test_example_configs_load_and_use_purged_trade_horizons() -> None:
    config_dir = Path("config/experiments/examples/trade_evaluation")
    paths = sorted(config_dir.glob("*.yaml"))
    assert len(paths) == 3

    configs = {path.stem: load_experiment_config(path) for path in paths}
    expected = configs["us100_m30_trend_vwap_expected_realized_r"]
    probability = configs["us100_m30_trend_vwap_target_before_stop"]
    mfe_mae = configs["us100_m30_trend_vwap_mfe_mae"]

    assert expected["model"]["target"]["kind"] == "expected_realized_r"
    assert probability["model"]["target"]["kind"] == "target_before_stop_probability"
    assert probability["model"]["kind"] == "logistic_regression_clf"
    assert [stage["target"]["target_col"] for stage in mfe_mae["model_stages"]] == [
        "mfe_r",
        "mae_r",
    ]
    for cfg in (expected, probability, mfe_mae):
        stages = cfg.get("model_stages") or [cfg["model"]]
        for stage in stages:
            assert stage["split"]["method"] == "purged"
            assert stage["split"]["purge_bars"] >= stage["target"]["max_holding_bars"]


def test_expected_realized_r_target_first_uses_entry_stop_exit_and_timeout_contract() -> None:
    frame = _frame()
    frame.loc[frame.index[1], ["high", "low", "close"]] = [102.2, 99.9, 102.0]

    out, label_col, fwd_col, meta = build_target(frame, _cfg("expected_realized_r"))

    assert label_col == fwd_col == "target_realized_r"
    assert out.loc[frame.index[0], "target_entry_price"] == pytest.approx(100.0)
    assert out.loc[frame.index[0], "target_stop_distance"] == pytest.approx(1.0)
    assert out.loc[frame.index[0], "target_stop_price"] == pytest.approx(99.0)
    assert out.loc[frame.index[0], "target_take_profit_price"] == pytest.approx(102.0)
    assert out.loc[frame.index[0], "target_exit_price"] == pytest.approx(102.0)
    assert out.loc[frame.index[0], fwd_col] == pytest.approx(2.0)
    assert out.loc[frame.index[0], "target_exit_reason"] == "take_profit"
    assert meta["horizon"] == 3
    assert meta["task_type"] == "regression"


def test_expected_realized_r_stop_first_and_timeout() -> None:
    stopped = _frame()
    stopped.loc[stopped.index[1], ["high", "low", "close"]] = [100.2, 98.8, 99.0]
    stopped_out, _, stopped_col, _ = build_target(stopped, _cfg("expected_realized_r"))

    timeout = _frame()
    timeout.loc[timeout.index[3], "close"] = 100.5
    timeout_out, _, timeout_col, _ = build_target(timeout, _cfg("expected_realized_r"))

    assert stopped_out.loc[stopped.index[0], "target_exit_reason"] == "stop_loss"
    assert stopped_out.loc[stopped.index[0], stopped_col] == pytest.approx(-1.0)
    assert timeout_out.loc[timeout.index[0], "target_exit_reason"] == "max_holding_close"
    assert timeout_out.loc[timeout.index[0], "target_holding_bars"] == pytest.approx(3.0)
    assert timeout_out.loc[timeout.index[0], timeout_col] == pytest.approx(0.5)


def test_expected_realized_r_includes_round_trip_costs_and_slippage() -> None:
    frame = _frame()
    frame.loc[frame.index[1], ["high", "low", "close"]] = [102.2, 99.9, 102.0]

    out, _, fwd_col, _ = build_target(
        frame,
        _cfg(
            "expected_realized_r",
            cost_per_unit_turnover=0.0001,
            slippage_per_unit_turnover=0.0001,
        ),
    )

    expected_entry = 100.0 * 1.0001
    expected_exit = 102.0 * 0.9999
    expected_slippage_drag = 0.02 - (expected_exit / expected_entry - 1.0)
    expected_net_r = (0.02 - 0.0002 - expected_slippage_drag) / 0.01
    assert out.loc[frame.index[0], "target_entry_price"] == pytest.approx(expected_entry)
    assert out.loc[frame.index[0], "target_exit_price"] == pytest.approx(expected_exit)
    assert out.loc[frame.index[0], fwd_col] == pytest.approx(expected_net_r)


@pytest.mark.parametrize(
    ("high", "low", "close", "expected_label", "expected_reason"),
    [
        (102.2, 99.9, 102.0, 1.0, "take_profit"),
        (100.2, 98.8, 99.0, 0.0, "stop_loss"),
        (100.2, 99.8, 100.0, 0.0, "max_holding_close"),
        (102.2, 98.8, 100.0, 0.0, "stop_and_target_same_bar_stop_first"),
    ],
)
def test_target_before_stop_path_labels(
    high: float,
    low: float,
    close: float,
    expected_label: float,
    expected_reason: str,
) -> None:
    frame = _frame()
    frame.loc[frame.index[1], ["high", "low", "close"]] = [high, low, close]

    out, label_col, fwd_col, meta = build_target(
        frame,
        _cfg("target_before_stop_probability", max_holding_bars=1),
    )

    assert label_col == fwd_col == "target_before_stop"
    assert out.loc[frame.index[0], label_col] == expected_label
    assert out.loc[frame.index[0], "target_exit_reason"] == expected_reason
    assert meta["task_type"] == "binary_classification"


def test_trade_mfe_mae_are_side_oriented_r_units_and_selectable() -> None:
    frame = _frame()
    frame.loc[frame.index[1], ["high", "low", "close"]] = [101.5, 99.5, 100.4]
    frame.loc[frame.index[2], ["high", "low", "close"]] = [101.2, 98.8, 100.3]

    mfe_out, _, mfe_col, mfe_meta = build_target(
        frame,
        _cfg("trade_mfe_mae_regression", target_col="mfe_r", max_holding_bars=2),
    )
    mae_out, _, mae_col, mae_meta = build_target(
        frame,
        _cfg("trade_mfe_mae_regression", target_col="mae_r", max_holding_bars=2),
    )

    assert mfe_col == "target_mfe_r"
    assert mae_col == "target_mae_r"
    assert mfe_out.loc[frame.index[0], mfe_col] == pytest.approx(1.5)
    assert mfe_out.loc[frame.index[0], "target_mae_r"] == pytest.approx(-1.2)
    assert mae_out.loc[frame.index[0], mae_col] == pytest.approx(-1.2)
    assert mfe_meta["available_target_cols"] == ["target_mfe_r", "target_mae_r"]
    assert mfe_meta["target_selection"] == "mfe_r"
    assert mae_meta["target_selection"] == "mae_r"


def test_short_trade_mfe_mae_are_oriented_to_short_side() -> None:
    frame = _frame()
    frame.loc[frame.index[0], "side"] = -1.0
    frame.loc[frame.index[1], ["high", "low", "close"]] = [100.5, 98.5, 99.0]

    out, _, _, _ = build_target(
        frame,
        _cfg("trade_mfe_mae_regression", target_col="mfe_r", max_holding_bars=1),
    )

    assert out.loc[frame.index[0], "target_mfe_r"] == pytest.approx(1.5)
    assert out.loc[frame.index[0], "target_mae_r"] == pytest.approx(-0.5)


def test_trade_targets_preserve_index_and_candidate_label_alignment() -> None:
    frame = _frame()
    frame.index = pd.Index([f"event-{idx}" for idx in range(len(frame))], name="event_id")
    frame.loc[frame.index[1], "high"] = 102.2

    out, _, fwd_col, _ = build_target(frame, _cfg("expected_realized_r"))

    assert out.index.equals(frame.index)
    assert out[fwd_col].notna().tolist() == [True, False, False, False, False, False, False, False]
    assert out.loc[frame.index[0], "target_trade_candidate"] == 1.0
    assert out.loc[frame.index[1]:, "target_trade_candidate"].eq(0.0).all()


def test_nan_future_path_invalid_stop_distance_and_unavailable_tail_are_unlabeled() -> None:
    nan_path = _frame()
    nan_path.loc[nan_path.index[1], "high"] = np.nan
    nan_out, _, nan_col, nan_meta = build_target(nan_path, _cfg("expected_realized_r"))

    bad_risk = _frame()
    bad_risk.loc[bad_risk.index[0], "atr_over_price"] = 0.0
    risk_out, _, risk_col, _ = build_target(bad_risk, _cfg("expected_realized_r"))

    tail = _frame(rows=4)
    tail["candidate"] = [0.0, 0.0, 1.0, 0.0]
    tail["side"] = [0.0, 0.0, 1.0, 0.0]
    tail_out, _, tail_col, _ = build_target(tail, _cfg("expected_realized_r"))

    assert np.isnan(nan_out.loc[nan_path.index[0], nan_col])
    assert nan_out.loc[nan_path.index[0], "target_exit_reason"] == "invalid_future_path"
    assert nan_meta["invalid_future_path_count"] == 1
    assert np.isnan(risk_out.loc[bad_risk.index[0], risk_col])
    assert risk_out.loc[bad_risk.index[0], "target_exit_reason"] == "invalid_volatility"
    assert np.isnan(tail_out.loc[tail.index[2], tail_col])
    assert tail_out.loc[tail.index[2], "target_exit_reason"] == "unavailable_tail"


@pytest.mark.parametrize(
    "overrides",
    [
        {"stop_loss_r": 0.0},
        {"risk_per_trade": -0.1},
        {"take_profit_r": np.nan},
        {"max_holding_bars": 0},
    ],
)
def test_invalid_trade_risk_config_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        build_target(_frame(), _cfg("expected_realized_r", **overrides))


def test_config_validation_routes_targets_to_compatible_models_and_enforces_purge() -> None:
    common = {
        "candidate_col": "candidate",
        "side_col": "side",
        "volatility_col": "atr_over_price",
        "max_holding_bars": 3,
    }
    validate_model_block(
        {
            "kind": "lightgbm_regressor",
            "feature_cols": ["feature_x"],
            "target": {"kind": "expected_realized_r", **common},
            "split": {"method": "purged", "train_size": 40, "test_size": 10, "purge_bars": 3},
        }
    )
    validate_model_block(
        {
            "kind": "xgboost_regressor",
            "feature_cols": ["feature_x"],
            "target": {"kind": "trade_mfe_mae_regression", "target_col": "mae_r", **common},
            "split": {"method": "purged", "train_size": 40, "test_size": 10, "purge_bars": 3},
        }
    )
    validate_model_block(
        {
            "kind": "logistic_regression_clf",
            "feature_cols": ["feature_x"],
            "target": {"kind": "target_before_stop_probability", **common},
            "split": {"method": "purged", "train_size": 40, "test_size": 10, "purge_bars": 3},
        }
    )

    with pytest.raises(ConfigValidationError, match="only for classifiers"):
        validate_model_block(
            {
                "kind": "lightgbm_regressor",
                "feature_cols": ["feature_x"],
                "target": {"kind": "target_before_stop_probability", **common},
            }
        )
    with pytest.raises(ConfigValidationError, match="purge_bars"):
        validate_model_block(
            {
                "kind": "lightgbm_regressor",
                "feature_cols": ["feature_x"],
                "target": {"kind": "expected_realized_r", **common},
                "split": {"method": "purged", "train_size": 40, "test_size": 10, "purge_bars": 2},
            }
        )


def _model_frame(rows: int = 90) -> pd.DataFrame:
    frame = _frame(rows)
    frame["candidate"] = 0.0
    frame["side"] = 0.0
    frame["feature_x"] = np.sin(np.arange(rows, dtype=float) / 3.0)
    for event_number, signal_idx in enumerate(range(2, rows - 4, 4)):
        frame.iloc[signal_idx, frame.columns.get_loc("candidate")] = 1.0
        frame.iloc[signal_idx, frame.columns.get_loc("side")] = 1.0
        if event_number % 2 == 0:
            frame.iloc[signal_idx + 1, frame.columns.get_loc("high")] = 102.2
            frame.iloc[signal_idx, frame.columns.get_loc("feature_x")] = 1.0
        else:
            frame.iloc[signal_idx + 1, frame.columns.get_loc("low")] = 98.8
            frame.iloc[signal_idx, frame.columns.get_loc("feature_x")] = -1.0
    return frame


def test_target_before_stop_trains_sklearn_classifier_with_purged_walk_forward() -> None:
    frame = _model_frame()
    out, _, meta = train_logistic_regression_classifier(
        frame,
        {
            "feature_cols": ["feature_x"],
            "target": _cfg("target_before_stop_probability", max_holding_bars=2),
            "split": {
                "method": "purged",
                "train_size": 50,
                "test_size": 20,
                "step_size": 20,
                "purge_bars": 2,
                "embargo_bars": 1,
            },
            "params": {"random_state": 7, "max_iter": 200},
            "final_refit": False,
        },
    )

    predicted = out["pred_prob"].notna()
    assert predicted.any()
    assert out.loc[predicted, "candidate"].eq(1.0).all()
    assert out.loc[predicted, "pred_is_oos"].all()
    assert meta["target"]["kind"] == "target_before_stop_probability"
    assert meta["anti_leakage"]["target_horizon"] == 2


def test_expected_realized_r_trains_lightgbm_with_purged_walk_forward() -> None:
    available, detail = probe_lightgbm_runtime()
    if not available:
        pytest.skip(f"LightGBM runtime unavailable: {detail}")

    frame = _model_frame()
    out, _, meta = train_lightgbm_regressor(
        frame,
        {
            "feature_cols": ["feature_x"],
            "target": _cfg("expected_realized_r", max_holding_bars=2),
            "split": {
                "method": "purged",
                "train_size": 50,
                "test_size": 20,
                "step_size": 20,
                "purge_bars": 2,
                "embargo_bars": 1,
            },
            "params": {
                "n_estimators": 8,
                "learning_rate": 0.05,
                "num_leaves": 5,
                "min_child_samples": 2,
                "random_state": 7,
                "n_jobs": 1,
            },
            "final_refit": False,
        },
    )

    assert out.loc[out["pred_is_oos"], "pred_ret"].notna().any()
    assert meta["target"]["kind"] == "expected_realized_r"
    assert meta["anti_leakage"]["target_horizon"] == 2


def test_mfe_mae_two_regressor_stages_emit_aligned_oos_predictions() -> None:
    available, detail = probe_lightgbm_runtime()
    if not available:
        pytest.skip(f"LightGBM runtime unavailable: {detail}")

    common_stage = {
        "kind": "lightgbm_regressor",
        "feature_cols": ["feature_x"],
        "split": {
            "method": "purged",
            "train_size": 50,
            "test_size": 20,
            "step_size": 20,
            "purge_bars": 2,
            "embargo_bars": 1,
        },
        "params": {
            "n_estimators": 8,
            "learning_rate": 0.05,
            "num_leaves": 5,
            "min_child_samples": 2,
            "random_state": 7,
            "n_jobs": 1,
        },
        "final_refit": False,
    }
    stages = [
        {
            **common_stage,
            "name": "mfe",
            "stage": 1,
            "target": _cfg(
                "trade_mfe_mae_regression",
                target_col="mfe_r",
                max_holding_bars=2,
            ),
            "pred_ret_col": "pred_mfe_r",
            "pred_prob_col": "pred_mfe_positive",
            "pred_is_oos_col": "pred_mfe_is_oos",
        },
        {
            **common_stage,
            "name": "mae",
            "stage": 2,
            "target": _cfg(
                "trade_mfe_mae_regression",
                target_col="mae_r",
                max_holding_bars=2,
            ),
            "pred_ret_col": "pred_mae_r",
            "pred_prob_col": "pred_mae_positive",
            "pred_is_oos_col": "pred_mae_is_oos",
        },
    ]

    frames, models, meta = apply_model_pipeline_to_assets(
        {"US100": _model_frame()},
        model_cfg={"kind": "none"},
        model_stages=stages,
        returns_col=None,
    )
    out = frames["US100"]

    assert set(models) == {"mfe", "mae"}
    assert out["pred_mfe_is_oos"].equals(out["pred_mae_is_oos"])
    assert out.loc[out["pred_mfe_is_oos"], "pred_mfe_r"].notna().any()
    assert out.loc[out["pred_mae_is_oos"], "pred_mae_r"].notna().any()
    assert meta["pipeline_kind"] == "multi_stage"
    assert meta["stage_names"] == ["mfe", "mae"]
