from __future__ import annotations

import numpy as np
import pandas as pd

from src.experiments.orchestration.model_stage import apply_model_pipeline_to_assets
from src.features import (
    add_close_returns,
    add_shock_context_features,
    add_support_resistance_features,
    add_support_resistance_v2_features,
)
from src.models.classification import _apply_fold_feature_preprocessing
from src.experiments.models import train_logistic_regression_classifier


def _synthetic_price_frame(n: int = 260) -> pd.DataFrame:
    """
    Verify that synthetic price frame behaves as expected under a representative regression
    scenario. The test protects the intended contract of the surrounding component and makes
    failures easier to localize.
    """
    rng = np.random.default_rng(42)
    base = np.where(np.arange(n) % 2 == 0, 0.01, -0.01)
    rets = base + rng.normal(0.0, 0.001, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))

    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    df = pd.DataFrame({"close": close}, index=idx)
    df["feat_1"] = pd.Series(rets, index=idx).rolling(5, min_periods=1).mean()
    df["feat_2"] = pd.Series(rets, index=idx).rolling(10, min_periods=1).std().fillna(0.0)
    return df


def test_walk_forward_predictions_are_oos_only() -> None:
    """
    Verify that walk forward predictions are out-of-sample only behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    df = _synthetic_price_frame()
    out, _, meta = train_logistic_regression_classifier(
        df=df,
        model_cfg={
            "params": {"max_iter": 1000, "solver": "lbfgs"},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 2},
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {
                "method": "walk_forward",
                "train_size": 120,
                "test_size": 20,
                "step_size": 20,
                "expanding": True,
            },
        },
    )

    assert meta["split_method"] == "walk_forward"
    assert meta["n_folds"] > 1
    assert int(out["pred_is_oos"].sum()) == sum(f["test_rows"] for f in meta["folds"])
    assert meta["split_index"] == meta["folds"][0]["test_start"]


def test_purged_splits_respect_anti_leakage_gap() -> None:
    """
    Verify that purged splits respect anti leakage gap behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    df = _synthetic_price_frame()
    purge_bars = 3
    out, _, meta = train_logistic_regression_classifier(
        df=df,
        model_cfg={
            "params": {"max_iter": 1000, "solver": "lbfgs"},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 3},
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {
                "method": "purged",
                "train_size": 120,
                "test_size": 20,
                "step_size": 20,
                "purge_bars": purge_bars,
                "embargo_bars": 2,
                "expanding": True,
            },
        },
    )

    assert meta["split_method"] == "purged"
    assert out["pred_is_oos"].any()
    for fold in meta["folds"]:
        assert fold["train_end"] <= fold["test_start"] - purge_bars


def test_binary_forward_target_keeps_tail_labels_nan() -> None:
    """
    Verify that binary forward target keeps tail labels nan behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    horizon = 5
    df = _synthetic_price_frame()
    out, _, meta = train_logistic_regression_classifier(
        df=df,
        model_cfg={
            "params": {"max_iter": 1000, "solver": "lbfgs"},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": horizon},
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {"method": "time", "train_frac": 0.7},
        },
    )

    label_col = str(meta["label_col"])
    assert out[label_col].tail(horizon).isna().all()


def test_quantile_target_uses_train_only_distribution_per_fold() -> None:
    """
    Verify that quantile target uses train only distribution per fold behaves as expected under
    a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    df = _synthetic_price_frame()
    tail_idx = df.index[-40:]
    base = float(df.loc[df.index[-41], "close"])
    df.loc[tail_idx, "close"] = base * np.exp(np.linspace(0.0, 4.0, len(tail_idx)))

    out, _, meta = train_logistic_regression_classifier(
        df=df,
        model_cfg={
            "params": {"max_iter": 1000, "solver": "lbfgs"},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {
                "kind": "forward_return",
                "price_col": "close",
                "horizon": 1,
                "quantiles": [0.2, 0.8],
            },
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {
                "method": "walk_forward",
                "train_size": 120,
                "test_size": 40,
                "step_size": 40,
                "expanding": True,
            },
        },
    )

    fwd_col = str(meta["fwd_col"])
    first_fold = meta["folds"][0]
    fold_q_high = float(first_fold["quantile_high_value"])
    global_q_high = float(out[fwd_col].dropna().quantile(0.8))
    assert fold_q_high < global_q_high


def test_standard_scaler_uses_train_only_statistics() -> None:
    X_train = pd.DataFrame({"feat_1": [1.0, 2.0, 3.0, 4.0]})
    X_test = pd.DataFrame({"feat_1": [100.0]})

    X_train_scaled, X_test_scaled, meta = _apply_fold_feature_preprocessing(
        X_train,
        X_test,
        preprocessing_cfg={"scaler": "standard"},
    )

    assert meta["scaler"] == "standard"
    assert meta["train_only"] is True
    assert np.isclose(float(np.mean(X_train_scaled[:, 0])), 0.0)
    assert np.isclose(float(np.std(X_train_scaled[:, 0], ddof=0)), 1.0)
    assert float(X_test_scaled[0, 0]) > 50.0


def test_standard_scaler_accepts_empty_test_fold() -> None:
    X_train = pd.DataFrame({"feat_1": [1.0, 2.0, 3.0, 4.0]})
    X_test = pd.DataFrame({"feat_1": pd.Series(dtype=float)})

    _, X_test_scaled, meta = _apply_fold_feature_preprocessing(
        X_train,
        X_test,
        preprocessing_cfg={"scaler": "standard"},
    )

    assert meta["scaler"] == "standard"
    assert X_test_scaled.shape == (0, 1)


def test_multi_stage_model_pipeline_uses_upstream_oos_predictions_only() -> None:
    df = _synthetic_price_frame(320)
    df["feat_3"] = df["feat_1"].rolling(3, min_periods=1).mean()
    asset_frames = {"AAA": df}

    out_frames, models, meta = apply_model_pipeline_to_assets(
        asset_frames,
        model_cfg=None,
        model_stages=[
            {
                "name": "first_pass",
                "enabled": True,
                "stage": 2,
                "kind": "logistic_regression_clf",
                "params": {"max_iter": 400, "solver": "lbfgs"},
                "feature_cols": ["feat_1", "feat_2"],
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {"method": "time", "train_frac": 0.5},
                "pred_prob_col": "stage1_pred_prob",
            },
            {
                "name": "disabled_middle",
                "enabled": False,
                "stage": 1,
                "kind": "sarimax_forecaster",
                "feature_cols": ["feat_1"],
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {"method": "time", "train_frac": 0.55},
                "pred_ret_col": "unused_pred_ret",
            },
            {
                "name": "final_filter",
                "enabled": True,
                "stage": 3,
                "kind": "logistic_regression_clf",
                "params": {"max_iter": 400, "solver": "lbfgs"},
                "feature_cols": ["stage1_pred_prob", "feat_2", "feat_3"],
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {"method": "time", "train_frac": 0.75},
                "pred_prob_col": "pred_prob",
            },
        ],
        returns_col=None,
    )

    out = out_frames["AAA"]
    assert isinstance(models, dict)
    assert meta["pipeline_kind"] == "multi_stage"
    assert meta["stage_count"] == 2
    assert meta["stage_names"] == ["first_pass", "final_filter"]
    assert [stage["stage"] for stage in meta["stages"]] == [2, 3]
    assert out["stage1_pred_prob"].notna().any()
    assert "unused_pred_ret" not in out.columns
    assert out.loc[~out["pred_is_oos"], "pred_prob"].isna().all()
    assert meta["prediction_diagnostics"]["non_oos_prediction_rows"] == 0
    assert meta["stages"][0]["prediction_diagnostics"]["non_oos_prediction_rows"] == 0
    assert meta["stages"][1]["prediction_diagnostics"]["non_oos_prediction_rows"] == 0


def test_shock_context_is_point_in_time_safe() -> None:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2024-01-01", periods=96, freq="h")
    logrets = rng.normal(0.0, 0.002, size=len(idx))
    close = 100.0 * np.exp(np.cumsum(logrets))
    df = pd.DataFrame({"close": close}, index=idx)
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0])
    intrabar = np.abs(rng.normal(0.003, 0.0005, size=len(idx)))
    df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
    df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)
    df = add_close_returns(df, log=True, col_name="close_logret")

    baseline = add_shock_context_features(
        df,
        returns_col="close_logret",
        ema_window=24,
        atr_window=24,
        short_horizon=1,
        medium_horizon=4,
        vol_window=24,
    )

    modified = df.copy()
    modified.loc[idx[70]:, "close"] = modified.loc[idx[70]:, "close"] * 1.35
    modified.loc[idx[70]:, "open"] = (
        modified.loc[idx[70]:, "close"].shift(1).fillna(modified.loc[idx[70], "close"])
    )
    modified.loc[idx[70]:, "high"] = (
        np.maximum(modified.loc[idx[70]:, "open"], modified.loc[idx[70]:, "close"]) * 1.01
    )
    modified.loc[idx[70]:, "low"] = (
        np.minimum(modified.loc[idx[70]:, "open"], modified.loc[idx[70]:, "close"]) * 0.99
    )
    modified = add_close_returns(modified, log=True, col_name="close_logret")

    future_changed = add_shock_context_features(
        modified,
        returns_col="close_logret",
        ema_window=24,
        atr_window=24,
        short_horizon=1,
        medium_horizon=4,
        vol_window=24,
    )

    check_cols = [
        "shock_ret_1h",
        "shock_ret_4h",
        "shock_ret_z_1h",
        "shock_ret_z_4h",
        "shock_atr_multiple_1h",
        "shock_atr_multiple_4h",
        "shock_distance_ema",
        "shock_candidate",
        "shock_side_contrarian",
        "shock_side_contrarian_active",
        "shock_active_window",
        "shock_strength",
        "bars_since_shock",
    ]
    pd.testing.assert_frame_equal(
        baseline.loc[: idx[69], check_cols],
        future_changed.loc[: idx[69], check_cols],
        check_dtype=False,
    )


def test_support_resistance_is_point_in_time_safe() -> None:
    rng = np.random.default_rng(9)
    idx = pd.date_range("2024-01-01", periods=96, freq="h")
    logrets = rng.normal(0.0, 0.002, size=len(idx))
    close = 100.0 * np.exp(np.cumsum(logrets))
    df = pd.DataFrame({"close": close}, index=idx)
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0])
    intrabar = np.abs(rng.normal(0.003, 0.0005, size=len(idx)))
    df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
    df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)

    baseline = add_support_resistance_features(df, windows=[24], include_pct_distance=True, include_atr_distance=True)

    modified = df.copy()
    modified.loc[idx[70]:, "close"] = modified.loc[idx[70]:, "close"] * 1.20
    modified.loc[idx[70]:, "open"] = modified.loc[idx[70]:, "close"].shift(1).fillna(modified.loc[idx[70], "close"])
    modified.loc[idx[70]:, "high"] = np.maximum(modified.loc[idx[70]:, "open"], modified.loc[idx[70]:, "close"]) * 1.01
    modified.loc[idx[70]:, "low"] = np.minimum(modified.loc[idx[70]:, "open"], modified.loc[idx[70]:, "close"]) * 0.99

    future_changed = add_support_resistance_features(
        modified,
        windows=[24],
        include_pct_distance=True,
        include_atr_distance=True,
    )

    check_cols = [
        "support_24",
        "resistance_24",
        "support_distance_pct_24",
        "resistance_distance_pct_24",
        "support_distance_atr_24",
        "resistance_distance_atr_24",
    ]
    pd.testing.assert_frame_equal(
        baseline.loc[: idx[69], check_cols],
        future_changed.loc[: idx[69], check_cols],
        check_dtype=False,
    )


def test_support_resistance_v2_is_point_in_time_safe() -> None:
    rng = np.random.default_rng(19)
    idx = pd.date_range("2024-01-01", periods=140, freq="h")
    logrets = rng.normal(0.0, 0.002, size=len(idx))
    close = 100.0 * np.exp(np.cumsum(logrets))
    df = pd.DataFrame({"close": close}, index=idx)
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0])
    intrabar = np.abs(rng.normal(0.003, 0.0005, size=len(idx)))
    df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
    df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)

    baseline = add_support_resistance_v2_features(
        df,
        pivot_left_window=24,
        pivot_confirm_bars=6,
    )

    modified = df.copy()
    modified.loc[idx[100]:, "close"] = modified.loc[idx[100]:, "close"] * 1.25
    modified.loc[idx[100]:, "open"] = modified.loc[idx[100]:, "close"].shift(1).fillna(modified.loc[idx[100], "close"])
    modified.loc[idx[100]:, "high"] = np.maximum(modified.loc[idx[100]:, "open"], modified.loc[idx[100]:, "close"]) * 1.01
    modified.loc[idx[100]:, "low"] = np.minimum(modified.loc[idx[100]:, "open"], modified.loc[idx[100]:, "close"]) * 0.99

    future_changed = add_support_resistance_v2_features(
        modified,
        pivot_left_window=24,
        pivot_confirm_bars=6,
    )

    check_cols = [
        "pivot_high_confirmed",
        "pivot_low_confirmed",
        "sr_v2_resistance_level",
        "sr_v2_support_level",
        "sr_v2_resistance_touch_count",
        "sr_v2_support_touch_count",
        "sr_v2_resistance_age",
        "sr_v2_support_age",
        "sr_v2_breakout_up",
        "sr_v2_breakout_down",
        "sr_v2_retest_resistance",
        "sr_v2_retest_support",
    ]
    pd.testing.assert_frame_equal(
        baseline.loc[: idx[99], check_cols],
        future_changed.loc[: idx[99], check_cols],
        check_dtype=False,
    )
