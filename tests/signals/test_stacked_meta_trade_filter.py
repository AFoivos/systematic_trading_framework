from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.meta.stacked_trade_filter import (
    ORIENTED_FEATURE_SOURCES,
    REGIME_FEATURES,
    CANDLE_PATH_RISK_FEATURES,
    build_causal_meta_features,
    build_meta_filtered_signal,
    train_stacked_meta_filter,
    validate_meta_feature_columns,
)
from src.signals.meta_probability_side_signal import meta_probability_side_signal


def _meta_frame(rows: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="30min")
    fold_size = rows // 6
    folds = np.minimum(np.arange(rows) // fold_size + 1, 6).astype(float)
    pred = np.sin(np.arange(rows) / 7.0)
    side = np.where(pred >= 0.0, 1.0, -1.0)
    frame = pd.DataFrame(
        {
            "timestamp": idx,
            "asset": "ETHUSD",
            "open": 100.0 + np.arange(rows) * 0.05,
            "high": 101.0 + np.arange(rows) * 0.05,
            "low": 99.0 + np.arange(rows) * 0.05,
            "close": 100.0 + np.arange(rows) * 0.05,
            "pred_ret": pred,
            "pred_is_oos": True,
            "walk_forward_fold": folds,
            "primary_candidate": 1.0,
            "primary_candidate_side": side,
            "primary_candidate_strength": np.abs(pred),
            "primary_candidate_threshold_distance": np.maximum(np.abs(pred) - 0.4, 0.0),
            "meta_net_r": np.where(np.cos(np.arange(rows) / 5.0) > 0.0, 0.8, -0.7),
        },
        index=idx,
    )
    frame["meta_label_min_0_50r"] = (frame["meta_net_r"] >= 0.5).astype(float)
    frame["meta_label_positive"] = (frame["meta_net_r"] > 0.0).astype(float)
    frame["meta_label_min_1_00r"] = (frame["meta_net_r"] >= 1.0).astype(float)
    for col in set(ORIENTED_FEATURE_SOURCES + REGIME_FEATURES + CANDLE_PATH_RISK_FEATURES):
        if col == "vol_ratio_24_192":
            continue
        frame[col] = np.linspace(0.1, 1.1, rows) + (hash(col) % 7) * 0.01
    frame["atr_over_price_48"] = 0.01
    frame["vol_rolling_24"] = 0.01
    frame["vol_rolling_48"] = 0.011
    frame["vol_rolling_96"] = 0.012
    frame["vol_rolling_192"] = 0.02
    return frame


def test_meta_probability_side_requires_oos_and_never_reverses_candidate_side() -> None:
    frame = pd.DataFrame(
        {
            "meta_pred_prob": [0.8, 0.9, 0.4, 0.95],
            "meta_pred_is_oos": [True, False, True, True],
            "primary_candidate": [1.0, 1.0, 1.0, 0.0],
            "primary_candidate_side": [1.0, -1.0, -1.0, 1.0],
        }
    )

    signal = meta_probability_side_signal(
        frame,
        prob_col="meta_pred_prob",
        side_col="primary_candidate_side",
        candidate_col="primary_candidate",
        pred_is_oos_col="meta_pred_is_oos",
        threshold=0.5,
    )

    assert signal.tolist() == [1.0, 0.0, 0.0, 0.0]


def test_build_meta_filtered_signal_keeps_non_candidates_flat() -> None:
    frame = pd.DataFrame(
        {
            "meta_pred_prob": [0.8, 0.8, 0.8],
            "meta_pred_is_oos": [True, True, False],
            "primary_candidate": [1.0, 0.0, 1.0],
            "primary_candidate_side": [-1.0, 1.0, 1.0],
        }
    )

    signal = build_meta_filtered_signal(frame, threshold=0.7)

    assert signal.tolist() == [-1.0, 0.0, 0.0]


def test_stacked_meta_filter_rejects_insample_primary_candidate() -> None:
    frame = build_causal_meta_features(_meta_frame())
    frame.iloc[10, frame.columns.get_loc("pred_is_oos")] = False

    with pytest.raises(ValueError, match="OOS primary predictions"):
        train_stacked_meta_filter(frame, min_train_candidates=5, purge_bars=2, embargo_bars=2)


def test_stacked_meta_filter_candidate_only_training_and_purge_boundary() -> None:
    frame = build_causal_meta_features(_meta_frame())

    result = train_stacked_meta_filter(
        frame,
        min_train_candidates=5,
        purge_bars=3,
        embargo_bars=3,
        calibration_method="none",
        model_kind="logistic_regression_clf",
    )

    assert result.artifacts
    for artifact in result.artifacts:
        assert artifact.train_max_pos is not None
        assert artifact.train_max_pos < artifact.test_start_pos - artifact.purge_bars
        assert frame.iloc[artifact.train_indices]["primary_candidate"].eq(1.0).all()
        assert frame.iloc[artifact.test_indices]["primary_candidate"].eq(1.0).all()
    pred_rows = result.frame["meta_pred_is_oos"].astype(bool)
    assert pred_rows.any()
    assert result.frame.loc[pred_rows, "primary_candidate"].eq(1.0).all()


def test_stacked_meta_filter_uses_fold_local_preprocessing_and_calibration() -> None:
    frame = build_causal_meta_features(_meta_frame())

    result = train_stacked_meta_filter(
        frame,
        min_train_candidates=10,
        purge_bars=2,
        embargo_bars=2,
        calibration_method="sigmoid",
        calibration_fraction=0.25,
        calibration_min_rows=5,
        model_kind="logistic_regression_clf",
        scaler="robust",
    )

    calibrated = [artifact for artifact in result.artifacts if artifact.calibration_rows > 0]
    assert calibrated
    first = calibrated[0]
    feature_idx = result.feature_cols.index("pred_ret")
    train_median = np.nanmedian(frame.iloc[first.model_train_indices]["pred_ret"].to_numpy(dtype=float))
    full_median = np.nanmedian(frame["pred_ret"].to_numpy(dtype=float))
    assert first.center[feature_idx] == pytest.approx(train_median)
    assert first.center[feature_idx] != pytest.approx(full_median)
    assert max(first.calibration_indices) < first.test_start_pos - first.purge_bars


def test_stacked_meta_filter_is_deterministic() -> None:
    frame = build_causal_meta_features(_meta_frame())

    first = train_stacked_meta_filter(frame, min_train_candidates=5, purge_bars=2, embargo_bars=2, random_state=7)
    second = train_stacked_meta_filter(frame, min_train_candidates=5, purge_bars=2, embargo_bars=2, random_state=7)

    np.testing.assert_allclose(
        first.frame["meta_pred_prob"].fillna(-1.0).to_numpy(),
        second.frame["meta_pred_prob"].fillna(-1.0).to_numpy(),
    )


def test_meta_feature_columns_reject_target_and_meta_prediction_columns() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        validate_meta_feature_columns(["pred_ret", "meta_net_r"])
    with pytest.raises(ValueError, match="not allowed"):
        validate_meta_feature_columns(["pred_ret", "meta_pred_prob"])
