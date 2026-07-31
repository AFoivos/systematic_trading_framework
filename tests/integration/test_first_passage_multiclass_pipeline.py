from __future__ import annotations

import numpy as np
import pandas as pd

from src.evaluation.time_splits import build_time_splits
from src.models.classification import train_logistic_regression_classifier
from src.models.classification.base import _split_fit_and_calibration_rows
from src.signals.barrier_expected_value_signal import barrier_expected_value_signal


def _synthetic_frame(rows: int = 1000) -> pd.DataFrame:
    rng = np.random.default_rng(23)
    index = pd.date_range("2024-01-01", periods=rows, freq="30min")
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.15, rows))
    open_ = np.r_[close[0], close[:-1]] + rng.normal(0.0, 0.02, rows)
    high = np.maximum(open_, close) + rng.uniform(0.03, 0.22, rows)
    low = np.minimum(open_, close) - rng.uniform(0.03, 0.22, rows)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "atr_14": np.full(rows, 0.30),
            "feature_return": pd.Series(close).pct_change().fillna(0.0).to_numpy(),
            "feature_range": (high - low) / close,
            "spread_bps": np.full(rows, 0.0001),
        },
        index=index,
    )


def _model_config() -> dict[str, object]:
    return {
        "feature_cols": ["feature_return", "feature_range", "atr_14"],
        "target": {
            "kind": "first_passage_barrier_multiclass",
            "horizon_bars": 6,
            "entry_delay_bars": 1,
            "atr_col": "atr_14",
            "upper_atr_multiplier": 1.0,
            "lower_atr_multiplier": 1.0,
            "ambiguous_policy": "exclude",
        },
        "split": {
            "method": "purged",
            "train_size": 550,
            "test_size": 150,
            "step_size": 150,
            "purge_bars": 7,
            "embargo_bars": 7,
            "max_folds": 2,
        },
        "preprocessing": {"scaler": "standard"},
        "calibration": {
            "method": "sigmoid",
            "fraction": 0.20,
            "min_rows": 80,
            "min_class_rows": 3,
        },
        "params": {
            "max_iter": 600,
            "solver": "lbfgs",
            "class_weight": "balanced",
            "random_state": 23,
        },
    }


def test_purge_uses_horizon_plus_entry_delay() -> None:
    splits = build_time_splits(
        method="purged",
        n_samples=200,
        split_cfg={"train_size": 100, "test_size": 20},
        target_horizon=7,
    )
    assert splits[0].train_end == splits[0].test_start - 7


def test_calibration_window_is_later_and_purged_from_estimator_fit() -> None:
    index = pd.RangeIndex(300)
    train = pd.DataFrame({"label": np.tile([-1, 0, 1], 100)}, index=index)
    fit, calibration, meta = _split_fit_and_calibration_rows(
        train,
        full_index=index,
        target_horizon=7,
        calibration_cfg={"method": "sigmoid", "fraction": 0.2, "min_rows": 50, "min_class_rows": 3},
    )

    assert fit.index.max() < calibration.index.min() - 7
    assert meta["purge_bars"] == 7
    assert calibration.index.min() > fit.index.max()


def test_multiclass_pipeline_and_ev_policy_are_deterministic() -> None:
    frame = _synthetic_frame()
    out_a, model_a, meta_a = train_logistic_regression_classifier(frame, _model_config())
    out_b, model_b, meta_b = train_logistic_regression_classifier(frame, _model_config())

    probability_cols = ["pred_prob_lower", "pred_prob_no_hit", "pred_prob_upper"]
    pd.testing.assert_frame_equal(out_a[probability_cols], out_b[probability_cols])
    predicted = out_a[probability_cols].dropna()
    np.testing.assert_allclose(predicted.sum(axis=1), 1.0, atol=1e-6)
    assert meta_a["oos_classification_summary"] == meta_b["oos_classification_summary"]
    assert all("ambiguity" in fold for fold in meta_a["folds"])
    assert all(
        0.0 <= fold["ambiguity"]["eval_ambiguous_rate"] <= 1.0
        for fold in meta_a["folds"]
    )
    assert model_a.predict_proba(frame[_model_config()["feature_cols"]].tail(3)).shape == (3, 3)
    assert model_b.predict_proba(frame[_model_config()["feature_cols"]].tail(3)).shape == (3, 3)

    signaled = barrier_expected_value_signal(
        out_a,
        atr_col="atr_14",
        price_col="close",
        spread_col="spread_bps",
        minimum_expected_edge=0.0001,
        minimum_class_probability=0.40,
        cost_per_turnover=0.00002,
        slippage_per_turnover=0.00001,
        maximum_no_hit_probability=0.80,
        maximum_spread=0.001,
    )
    assert signaled.loc[~signaled["pred_probability_calibrated"], "barrier_ev_signal"].eq(0.0).all()
    assert np.isfinite(signaled["barrier_ev_signal"]).all()
