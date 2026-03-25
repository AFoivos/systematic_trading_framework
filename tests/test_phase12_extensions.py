from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.experiments.support.targets import build_forward_return_target, build_triple_barrier_target
from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.models.runtime import probe_xgboost_runtime
from src.experiments.models import (
    train_logistic_regression_classifier,
    train_sarimax_forecaster,
    train_xgboost_classifier,
)
from src.experiments.registry import FEATURE_REGISTRY, MODEL_REGISTRY, SIGNAL_REGISTRY
from src.features import add_close_returns, add_feature_transforms
from src.features.regime_context import add_regime_context_features
from src.features.session_context import add_session_context_features
from src.features.technical.indicators import add_indicator_features


def _synthetic_hourly_ohlcv(periods: int = 420, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=periods, freq="H")
    hours = idx.hour.to_numpy(dtype=float)
    cyclical = 0.00025 * np.sin(2.0 * np.pi * hours / 24.0)
    regimes = np.where(np.arange(periods) < periods // 2, 0.00015, -0.00005)
    noise = rng.normal(0.0, 0.0008, size=periods)
    returns = cyclical + regimes + noise

    close = 100.0 * np.exp(np.cumsum(returns))
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
    intrabar = np.abs(rng.normal(0.0008, 0.0002, size=periods))
    df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
    df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)
    df["volume"] = 10_000.0 + rng.integers(0, 250, size=periods)
    return df[["open", "high", "low", "close", "volume"]]


def test_registry_contains_phase12_extensions() -> None:
    assert "session_context" in FEATURE_REGISTRY
    assert "regime_context" in FEATURE_REGISTRY
    assert "feature_transforms" in FEATURE_REGISTRY
    assert "bollinger" in FEATURE_REGISTRY
    assert "macd" in FEATURE_REGISTRY
    assert "ppo" in FEATURE_REGISTRY
    assert "roc" in FEATURE_REGISTRY
    assert "atr" in FEATURE_REGISTRY
    assert "adx" in FEATURE_REGISTRY
    assert "volume_features" in FEATURE_REGISTRY
    assert "mfi" in FEATURE_REGISTRY
    assert "rsi" in FEATURE_REGISTRY
    assert "stochastic" in FEATURE_REGISTRY
    assert "price_momentum" in FEATURE_REGISTRY
    assert "return_momentum" in FEATURE_REGISTRY
    assert "vol_normalized_momentum" in FEATURE_REGISTRY
    assert "xgboost_clf" in MODEL_REGISTRY
    assert "probability_vol_adjusted" in SIGNAL_REGISTRY


def test_signal_registry_points_to_signal_layer() -> None:
    assert SIGNAL_REGISTRY["trend_state"].__module__.startswith("src.signals")
    assert SIGNAL_REGISTRY["probability_vol_adjusted"].__module__.startswith("src.signals")
    assert SIGNAL_REGISTRY["forecast_vol_adjusted"].__module__.startswith("src.signals")


def test_apply_feature_steps_skips_disabled_steps() -> None:
    df = _synthetic_hourly_ohlcv(periods=72)
    out = apply_feature_steps(
        df,
        [
            {"step": "returns", "enabled": True, "params": {"log": True, "col_name": "close_logret"}},
            {"step": "rsi", "enabled": False, "params": {"price_col": "close", "windows": [14]}},
            {"step": "bollinger", "enabled": True, "params": {"price_col": "close", "window": 24, "n_std": 2.0}},
        ],
    )

    assert "close_logret" in out.columns
    assert "bb_percent_b_24_2.0" in out.columns
    assert "close_rsi_14" not in out.columns


def test_apply_signal_step_supports_signal_col_config() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="H")
    df = pd.DataFrame(
        {
            "pred_prob": [0.9, 0.5, 0.1],
            "pred_ret": [0.02, 0.0, -0.02],
            "pred_vol": [0.01, 0.01, 0.01],
        },
        index=idx,
    )

    legacy = apply_signal_step(
        df,
        {
            "kind": "probability_conviction",
            "params": {"prob_col": "pred_prob", "signal_col": "signal_prob_size", "clip": 1.0},
        },
    )
    canonical = apply_signal_step(
        df,
        {
            "kind": "forecast_threshold",
            "params": {
                "forecast_col": "pred_ret",
                "signal_col": "signal_forecast_custom",
                "upper": 0.01,
                "lower": -0.01,
                "mode": "long_short",
            },
        },
    )

    assert legacy["signal_prob_size"].tolist() == [0.8, 0.0, -0.8]
    assert canonical["signal_forecast_custom"].tolist() == [1.0, 0.0, -1.0]


def test_rolling_clip_transform_is_point_in_time_safe() -> None:
    idx = pd.date_range("2024-01-01", periods=7, freq="H")
    df = pd.DataFrame(
        {
            "volume_over_atr_24": [1.0, 1.1, 0.9, 1.05, 1.0, 100.0, -50.0],
        },
        index=idx,
    )

    out = add_feature_transforms(
        df,
        transforms=[
            {
                "source_col": "volume_over_atr_24",
                "kind": "rolling_clip",
                "output_col": "volume_over_atr_24_rollclip_4_q10_q90",
                "window": 4,
                "lower_q": 0.10,
                "upper_q": 0.90,
                "shift": 1,
            }
        ],
    )

    clipped = out["volume_over_atr_24_rollclip_4_q10_q90"]
    assert clipped.iloc[:4].isna().all()

    history = pd.Series([1.1, 0.9, 1.05, 1.0], index=idx[1:5])
    expected_upper = history.quantile(0.90)
    expected_lower = history.quantile(0.10)
    assert clipped.iloc[5] == pytest.approx(expected_upper)
    assert clipped.iloc[6] == pytest.approx(expected_lower)
    assert clipped.iloc[5] != df.iloc[5]["volume_over_atr_24"]
    assert clipped.iloc[6] != df.iloc[6]["volume_over_atr_24"]


def test_indicator_feature_transform_preserves_original_and_adds_clipped_variant() -> None:
    df = _synthetic_hourly_ohlcv(periods=120, seed=101)
    df = add_indicator_features(
        df,
        price_col="close",
        high_col="high",
        low_col="low",
        volume_col="volume",
        bb_window=20,
        bb_nstd=2.0,
        roc_windows=(),
        atr_window=24,
        adx_window=14,
        vol_z_window=72,
        include_mfi=False,
    )
    expected_upper = (
        df["volume_over_atr_24"]
        .rolling(48, min_periods=48)
        .quantile(0.99)
        .shift(1)
        .iloc[-1]
    )
    df.loc[df.index[-1], "volume_over_atr_24"] = float(expected_upper) * 5.0

    out = add_feature_transforms(
        df,
        transforms=[
            {
                "source_col": "volume_over_atr_24",
                "kind": "rolling_clip",
                "output_col": "volume_over_atr_24_rollclip_48_q01_q99",
                "window": 48,
                "lower_q": 0.01,
                "upper_q": 0.99,
                "shift": 1,
            }
        ],
    )

    assert "volume_over_atr_24" in out.columns
    assert "volume_over_atr_24_rollclip_48_q01_q99" in out.columns
    assert pd.notna(out.iloc[-1]["volume_over_atr_24"])
    assert pd.notna(out.iloc[-1]["volume_over_atr_24_rollclip_48_q01_q99"])
    assert out.iloc[-1]["volume_over_atr_24_rollclip_48_q01_q99"] == pytest.approx(expected_upper)
    assert out.iloc[-1]["volume_over_atr_24_rollclip_48_q01_q99"] < out.iloc[-1]["volume_over_atr_24"]


def test_session_and_regime_features_emit_expected_columns() -> None:
    df = _synthetic_hourly_ohlcv(periods=48)
    df = add_close_returns(df, log=True, col_name="close_logret")
    df = add_session_context_features(df)
    df = add_regime_context_features(
        df,
        price_col="close",
        returns_col="close_logret",
        vol_short_window=6,
        vol_long_window=12,
        trend_fast_span=6,
        trend_slow_span=12,
    )

    expected = {
        "hour_sin_24",
        "day_of_week_cos_7",
        "session_asia",
        "session_europe",
        "session_us",
        "session_europe_us_overlap",
        "regime_vol_ratio_6_12",
        "regime_high_vol_state_6_12",
        "regime_trend_ratio_6_12",
        "regime_trend_state_6_12",
    }
    assert expected.issubset(df.columns)
    assert float(df.loc[df.index[0], "session_asia"]) == 1.0
    overlap_ts = pd.Timestamp("2024-01-01 14:00:00")
    assert float(df.loc[overlap_ts, "session_europe_us_overlap"]) == 1.0


def test_triple_barrier_target_labels_upper_and_lower_events() -> None:
    idx = pd.date_range("2024-01-01", periods=6, freq="H")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 102.0, 99.0, 100.0, 100.0],
            "high": [100.2, 102.5, 102.5, 99.5, 100.5, 100.5],
            "low": [99.8, 99.5, 98.0, 97.5, 99.5, 99.5],
            "close": [100.0, 102.0, 99.0, 98.5, 100.0, 100.0],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000],
            "tb_vol": [0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
        },
        index=idx,
    )

    out, label_col, _, meta = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "volatility_col": "tb_vol",
            "upper_mult": 1.0,
            "lower_mult": 1.0,
            "max_holding": 2,
            "neutral_label": "drop",
        },
    )

    assert label_col == "label"
    assert float(out.iloc[0][label_col]) == 1.0
    assert float(out.iloc[1][label_col]) == 0.0
    assert meta["kind"] == "triple_barrier"
    assert meta["horizon"] == 2


def test_triple_barrier_target_records_barrier_level_event_returns() -> None:
    idx = pd.date_range("2024-01-01", periods=6, freq="H")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 102.0, 99.0, 100.0, 100.0],
            "high": [100.2, 102.5, 102.5, 99.5, 100.5, 100.5],
            "low": [99.8, 99.5, 98.0, 97.5, 99.5, 99.5],
            "close": [100.0, 102.0, 99.0, 98.5, 100.0, 100.0],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000],
            "tb_vol": [0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
        },
        index=idx,
    )

    out, _, fwd_col, _ = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "volatility_col": "tb_vol",
            "upper_mult": 1.0,
            "lower_mult": 1.0,
            "max_holding": 2,
            "neutral_label": "drop",
        },
    )

    assert float(out.iloc[0][fwd_col]) == pytest.approx(0.01)
    assert float(out.iloc[1][fwd_col]) == pytest.approx(-0.01)


def test_triple_barrier_target_keeps_incomplete_tail_unlabeled() -> None:
    idx = pd.date_range("2024-01-01", periods=6, freq="H")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 101.0, 101.5, 102.0, 102.5],
            "high": [100.3, 100.8, 101.4, 101.9, 102.4, 102.9],
            "low": [99.7, 99.8, 100.6, 101.1, 101.6, 102.1],
            "close": [100.0, 100.5, 101.0, 101.5, 102.0, 102.5],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000],
            "tb_vol": [0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
        },
        index=idx,
    )

    out, label_col, fwd_col, meta = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "volatility_col": "tb_vol",
            "upper_mult": 10.0,
            "lower_mult": 10.0,
            "max_holding": 3,
            "neutral_label": "drop",
        },
    )

    assert out[label_col].tail(3).isna().all()
    assert out[fwd_col].tail(3).isna().all()
    assert meta["labeled_rows"] == int(out[label_col].notna().sum())


def test_forward_return_target_can_use_log_return_inputs() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="H")
    step_logret = float(np.log(1.1))
    df = pd.DataFrame(
        {
            "close": [100.0, 110.0, 121.0, 133.1],
            "close_logret": [np.nan, step_logret, step_logret, step_logret],
        },
        index=idx,
    )

    out, label_col, fwd_col, meta = build_forward_return_target(
        df,
        {
            "kind": "forward_return",
            "price_col": "close",
            "returns_col": "close_logret",
            "returns_type": "log",
            "horizon": 2,
        },
    )

    expected = 2.0 * step_logret
    assert label_col == "label"
    assert float(out.iloc[0][fwd_col]) == pytest.approx(expected)
    assert float(out.iloc[1][fwd_col]) == pytest.approx(expected)
    assert pd.isna(out.iloc[2][fwd_col])
    assert meta["returns_col"] == "close_logret"
    assert meta["returns_type"] == "log"


def test_xgboost_classifier_supports_triple_barrier_target() -> None:
    available, reason = probe_xgboost_runtime()
    if not available:
        pytest.skip(f"XGBoost runtime unavailable in this environment: {reason}")

    df = _synthetic_hourly_ohlcv(periods=480, seed=19)
    df = add_close_returns(df, log=True, col_name="close_logret")
    df = add_session_context_features(df)
    df = add_regime_context_features(
        df,
        price_col="close",
        returns_col="close_logret",
        vol_short_window=12,
        vol_long_window=48,
        trend_fast_span=12,
        trend_slow_span=48,
    )

    feature_cols = [
        "hour_sin_24",
        "hour_cos_24",
        "session_asia",
        "session_europe",
        "session_us",
        "regime_vol_ratio_12_48",
        "regime_trend_ratio_12_48",
        "regime_trend_state_12_48",
        "regime_absret_z_12_48",
    ]
    out, _, meta = train_xgboost_classifier(
        df,
        {
            "feature_cols": feature_cols,
            "target": {
                "kind": "triple_barrier",
                "price_col": "close",
                "open_col": "open",
                "high_col": "high",
                "low_col": "low",
                "returns_col": "close_logret",
                "max_holding": 6,
                "upper_mult": 1.2,
                "lower_mult": 1.2,
                "vol_window": 24,
                "neutral_label": "drop",
            },
            "split": {
                "method": "walk_forward",
                "train_size": 240,
                "test_size": 48,
                "step_size": 48,
                "expanding": False,
                "max_folds": 3,
            },
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "params": {
                "n_estimators": 25,
                "max_depth": 3,
                "learning_rate": 0.1,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
            },
        },
        returns_col="close_logret",
    )

    assert meta["model_kind"] == "xgboost_clf"
    assert meta["target"]["kind"] == "triple_barrier"
    assert int(out["pred_is_oos"].sum()) > 0
    assert out.loc[out["pred_is_oos"], "pred_prob"].notna().any()
    assert meta["oos_classification_summary"]["evaluation_rows"] > 0


def test_classifier_garch_overlay_emits_pred_vol() -> None:
    df = _synthetic_hourly_ohlcv(periods=360, seed=29)
    df = add_close_returns(df, log=True, col_name="close_logret")
    df = add_session_context_features(df)
    df = add_regime_context_features(
        df,
        price_col="close",
        returns_col="close_logret",
        vol_short_window=12,
        vol_long_window=48,
        trend_fast_span=12,
        trend_slow_span=48,
    )

    out, _, meta = train_logistic_regression_classifier(
        df,
        {
            "feature_cols": [
                "session_asia",
                "session_europe",
                "session_us",
                "regime_vol_ratio_12_48",
                "regime_trend_ratio_12_48",
                "regime_absret_z_12_48",
            ],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 3},
            "split": {
                "method": "walk_forward",
                "train_size": 220,
                "test_size": 48,
                "step_size": 48,
                "expanding": False,
                "max_folds": 2,
            },
            "params": {
                "max_iter": 1000,
                "solver": "lbfgs",
            },
            "overlay": {
                "kind": "garch",
                "params": {
                    "returns_input_col": "close_logret",
                    "mean_model": "zero",
                },
            },
        },
        returns_col="close_logret",
    )

    oos_mask = out["pred_is_oos"]
    assert meta["overlay"]["kind"] == "garch"
    assert "pred_vol" in out.columns
    assert (out.loc[oos_mask, "pred_vol"].dropna() > 0.0).all()
    assert bool(meta["feature_importance"]["available"])
    assert meta["label_distribution"]["oos_evaluation"]["labeled_rows"] > 0
    assert meta["prediction_diagnostics"]["alignment_ok"] is True
    assert meta["prediction_diagnostics"]["non_oos_prediction_rows"] == 0


def test_classifier_records_missing_test_feature_diagnostics() -> None:
    df = _synthetic_hourly_ohlcv(periods=360, seed=37)
    df = add_close_returns(df, log=True, col_name="close_logret")
    df = add_session_context_features(df)
    df = add_regime_context_features(
        df,
        price_col="close",
        returns_col="close_logret",
        vol_short_window=12,
        vol_long_window=48,
        trend_fast_span=12,
        trend_slow_span=48,
    )
    df.loc[df.index[-90:], "regime_vol_ratio_12_48"] = np.nan

    out, _, meta = train_logistic_regression_classifier(
        df,
        {
            "feature_cols": [
                "session_asia",
                "session_europe",
                "session_us",
                "regime_vol_ratio_12_48",
                "regime_trend_ratio_12_48",
            ],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 3},
            "split": {
                "method": "walk_forward",
                "train_size": 220,
                "test_size": 48,
                "step_size": 48,
                "expanding": False,
                "max_folds": 2,
            },
            "params": {
                "max_iter": 1000,
                "solver": "lbfgs",
            },
        },
        returns_col="close_logret",
    )

    assert meta["missing_value_diagnostics"]["test_rows_missing_features"] > 0
    assert meta["prediction_diagnostics"]["oos_prediction_coverage"] < 1.0
    assert int(out.loc[~out["pred_is_oos"], "pred_prob"].notna().sum()) == 0


def test_sarimax_forecaster_garch_overlay_emits_volatility_predictions() -> None:
    df = _synthetic_hourly_ohlcv(periods=360, seed=41)
    df = add_close_returns(df, log=True, col_name="close_logret")
    df = add_session_context_features(df)
    df = add_regime_context_features(
        df,
        price_col="close",
        returns_col="close_logret",
        vol_short_window=12,
        vol_long_window=48,
        trend_fast_span=12,
        trend_slow_span=48,
    )
    df["lag_close_logret_1"] = df["close_logret"].shift(1)
    df["lag_close_logret_2"] = df["close_logret"].shift(2)

    out, _, meta = train_sarimax_forecaster(
        df,
        {
            "feature_cols": [
                "lag_close_logret_1",
                "lag_close_logret_2",
                "session_asia",
                "session_europe",
                "regime_vol_ratio_12_48",
                "regime_trend_ratio_12_48",
            ],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {
                "method": "walk_forward",
                "train_size": 220,
                "test_size": 48,
                "step_size": 48,
                "expanding": False,
                "max_folds": 2,
            },
            "params": {
                "order": [1, 0, 0],
                "seasonal_order": [0, 0, 0, 0],
                "trend": "c",
                "use_exog": True,
                "maxiter": 60,
                "allow_fallback": True,
            },
            "overlay": {
                "kind": "garch",
                "params": {
                    "returns_input_col": "close_logret",
                    "mean_model": "ar1",
                },
            },
        },
        returns_col="close_logret",
    )

    mask = out["pred_is_oos"]
    assert meta["overlay"]["kind"] == "garch"
    assert out.loc[mask, "pred_ret"].notna().any()
    assert (out.loc[mask, "pred_vol"].dropna() > 0.0).all()
    assert meta["prediction_diagnostics"]["alignment_ok"] is True
    assert meta["prediction_diagnostics"]["non_oos_prediction_rows"] == 0
    assert meta["target_distribution"]["oos_target"]["rows"] > 0
