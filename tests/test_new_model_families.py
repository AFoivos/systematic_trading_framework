from __future__ import annotations

import os
import subprocess
import sys
import types

import numpy as np
import pandas as pd
import pytest

import src.models.forecasting.garch as garch_module
import src.models.forecasting.sarimax as sarimax_module
from src.evaluation.model_diagnostics import (
    build_dense_forecast_diagnostic_frames,
    compute_lightgbm_shap_diagnostics,
    prediction_quantile_table,
    prediction_realized_metrics,
    quantile_monotonicity,
    write_dense_diagnostic_plots,
)
from src.experiments.models import (
    train_chronos_bolt_forecaster,
    train_garch_forecaster,
    train_lightgbm_regressor,
    train_sarimax_forecaster,
    train_tft_forecaster,
    train_xgboost_regressor,
)
from src.experiments.registry import MODEL_REGISTRY, SIGNAL_REGISTRY
from src.models.classification import train_logistic_regression_classifier
from src.models.common.runtime import probe_lightgbm_runtime, probe_xgboost_runtime
from src.models.forecasting.base import prepare_forecaster_inputs, train_forward_forecaster
from src.models.forecasting.foundation import (
    FoundationForecastSpec,
    _assemble_prediction_output,
)
from src.models.forecasting.garch import GarchState, make_garch_fold_predictor
from src.models.forecasting.sarimax import train_sarimax_fold
from src.signals.dense_return_forecast_signal import dense_return_forecast_signal
from src.signals.forecast_signal import (
    compute_forecast_threshold_signal,
    compute_forecast_vol_adjusted_signal,
    compute_probability_vol_adjusted_signal,
)
from src.targets.candidate_expected_r import build_candidate_expected_r_target
from src.utils.config_validation import validate_model_block
from tests.optional_dependencies import optional_dependency_stack_available


def _synthetic_ohlcv_with_returns(n: int = 260, seed: int = 123) -> pd.DataFrame:
    """
    Build a deterministic synthetic OHLCV frame with mildly autocorrelated returns.
    """
    rng = np.random.default_rng(seed)
    eps = rng.normal(0.0, 0.008, size=n)
    rets = np.zeros(n, dtype=float)
    for i in range(1, n):
        rets[i] = 0.15 * rets[i - 1] + eps[i]
    close = 100.0 * np.exp(np.cumsum(rets))

    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
    df["high"] = np.maximum(df["open"], df["close"]) * 1.002
    df["low"] = np.minimum(df["open"], df["close"]) * 0.998
    df["volume"] = 1_000_000 + rng.integers(0, 5_000, size=n)
    df["close_ret"] = df["close"].pct_change()
    df["lag_close_ret_1"] = df["close_ret"].shift(1)
    df["lag_close_ret_2"] = df["close_ret"].shift(2)
    df["lag_close_ret_5"] = df["close_ret"].shift(5)
    df["vol_rolling_20"] = df["close_ret"].rolling(20, min_periods=5).std()
    return df


def test_registry_contains_new_models_and_signals() -> None:
    """
    Verify that registry wiring exposes new model families and signal adapters.
    """
    for model_kind in (
        "sarimax_forecaster",
        "garch_forecaster",
        "tft_forecaster",
        "lightgbm_regressor",
        "xgboost_regressor",
        "chronos_bolt_forecaster",
        "chronos_2_forecaster",
        "timesfm_2p5_200m_forecaster",
        "timesfm_1p0_200m_forecaster",
    ):
        assert model_kind in MODEL_REGISTRY
    for signal_kind in ("forecast_threshold", "forecast_vol_adjusted", "dense_return_forecast"):
        assert signal_kind in SIGNAL_REGISTRY


def test_chronos_bolt_forecaster_converts_price_forecast_to_oos_return(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify Chronos-Bolt wiring without requiring real checkpoint downloads.
    """
    class FakeTensor:
        def __init__(self, values: object, dtype: object = None) -> None:
            self._values = np.asarray(values, dtype=dtype)

        def __getitem__(self, key: object) -> object:
            return self._values[key]

        def detach(self) -> "FakeTensor":
            return self

        def cpu(self) -> "FakeTensor":
            return self

        def numpy(self) -> np.ndarray:
            return self._values

    fake_torch = types.SimpleNamespace(
        float32=np.float32,
        tensor=FakeTensor,
    )

    class FakeChronosBoltPipeline:
        @classmethod
        def from_pretrained(cls, *args: object, **kwargs: object) -> "FakeChronosBoltPipeline":
            return cls()

        def predict_quantiles(
            self,
            *,
            inputs: list[object],
            prediction_length: int,
            quantile_levels: list[float],
            **kwargs: object,
        ) -> tuple[FakeTensor, FakeTensor]:
            last_values = np.asarray([float(context[-1]) for context in inputs], dtype=float)
            mean = np.column_stack(
                [last_values * (1.0 + 0.01 * step) for step in range(1, prediction_length + 1)]
            )
            quantiles = np.stack(
                [mean * (1.0 + 0.02 * (float(q) - 0.5)) for q in quantile_levels],
                axis=2,
            )
            return (
                fake_torch.tensor(quantiles, dtype=fake_torch.float32),
                fake_torch.tensor(mean, dtype=fake_torch.float32),
            )

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "chronos", types.SimpleNamespace(ChronosBoltPipeline=FakeChronosBoltPipeline))
    df = _synthetic_ohlcv_with_returns(n=80)
    out, _, meta = train_chronos_bolt_forecaster(
        df,
        model_cfg={
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 2},
            "split": {
                "method": "walk_forward",
                "train_size": 40,
                "test_size": 8,
                "step_size": 8,
                "expanding": True,
                "max_folds": 1,
            },
            "params": {
                "model_id": "fake/chronos-bolt",
                "source_col": "close",
                "source_kind": "price",
                "lookback": 12,
                "min_context": 4,
                "quantiles": [0.1, 0.5, 0.9],
            },
        },
    )

    mask = out["pred_is_oos"] & out["pred_ret"].notna()
    assert int(mask.sum()) > 0
    assert out.loc[mask, "pred_ret"].round(6).eq(0.02).all()
    assert out.loc[mask, "pred_vol"].notna().all()
    assert meta["model_kind"] == "chronos_bolt_forecaster"
    assert meta["folds"][0]["zero_shot"] is True


def test_foundation_multi_step_return_marginals_are_not_reported_as_path_quantiles() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="h")
    full_df = pd.DataFrame({"close": [100.0], "close_ret": [0.0]}, index=index)
    spec = FoundationForecastSpec(
        model_family="test",
        model_id="test/model",
        source_col="close_ret",
        source_kind="returns",
        source_returns_type="simple",
        target_kind="forward_return",
        target_returns_type="simple",
        prediction_length=2,
        target_horizon=2,
        lookback=4,
        min_context=2,
        quantiles=(0.1, 0.5, 0.9),
        normalize_by_volatility=False,
        volatility_col=None,
        price_col="close",
        volatility_floor=1e-12,
        clip=None,
    )

    pred_ret, extra_cols = _assemble_prediction_output(
        index=index,
        row_positions=np.array([0]),
        last_context_values=np.array([0.0]),
        point_forecast=np.array([[0.01, 0.02]]),
        quantile_forecasts={
            0.1: np.array([[0.005, 0.005]]),
            0.5: np.array([[0.01, 0.02]]),
            0.9: np.array([[0.03, 0.03]]),
        },
        full_df=full_df,
        spec=spec,
    )

    assert pred_ret.iloc[0] == pytest.approx(1.01 * 1.02 - 1.0)
    assert extra_cols == {}


def test_foundation_terminal_price_marginals_remain_valid_return_quantiles() -> None:
    index = pd.date_range("2024-01-01", periods=1, freq="h")
    full_df = pd.DataFrame({"close": [100.0]}, index=index)
    spec = FoundationForecastSpec(
        model_family="test",
        model_id="test/model",
        source_col="close",
        source_kind="price",
        source_returns_type="simple",
        target_kind="forward_return",
        target_returns_type="simple",
        prediction_length=2,
        target_horizon=2,
        lookback=4,
        min_context=2,
        quantiles=(0.1, 0.5, 0.9),
        normalize_by_volatility=False,
        volatility_col=None,
        price_col="close",
        volatility_floor=1e-12,
        clip=None,
    )

    pred_ret, extra_cols = _assemble_prediction_output(
        index=index,
        row_positions=np.array([0]),
        last_context_values=np.array([100.0]),
        point_forecast=np.array([[101.0, 102.0]]),
        quantile_forecasts={
            0.1: np.array([[99.0, 98.0]]),
            0.5: np.array([[101.0, 102.0]]),
            0.9: np.array([[103.0, 104.0]]),
        },
        full_df=full_df,
        spec=spec,
    )

    assert pred_ret.iloc[0] == pytest.approx(0.02)
    assert extra_cols["pred_q10"].iloc[0] == pytest.approx(-0.02)
    assert extra_cols["pred_q50"].iloc[0] == pytest.approx(0.02)
    assert extra_cols["pred_q90"].iloc[0] == pytest.approx(0.04)
    assert extra_cols["pred_vol"].iloc[0] == pytest.approx(0.03)


def test_sarimax_forecaster_produces_oos_forecasts() -> None:
    """
    Verify SARIMAX forecaster integration with anti-leakage split framework.
    """
    df = _synthetic_ohlcv_with_returns()
    out, _, meta = train_sarimax_forecaster(
        df,
        model_cfg={
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "vol_rolling_20"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {
                "method": "walk_forward",
                "train_size": 140,
                "test_size": 30,
                "step_size": 30,
                "expanding": True,
            },
            "params": {
                "order": [1, 0, 1],
                "seasonal_order": [0, 0, 0, 0],
                "trend": "c",
                "use_exog": True,
                "maxiter": 80,
                "allow_fallback": True,
            },
        },
    )

    assert meta["model_kind"] == "sarimax_forecaster"
    assert int(out["pred_is_oos"].sum()) > 0
    assert out.loc[out["pred_is_oos"], "pred_ret"].notna().any()
    assert meta["oos_regression_summary"]["evaluation_rows"] > 0


def test_sarimax_forecaster_rejects_missing_test_exogenous_rows() -> None:
    """
    SARIMAX should fail loudly when test exogenous rows are missing and would misalign forecasts.
    """
    df = _synthetic_ohlcv_with_returns()
    train_size = 140
    df.loc[df.index[train_size], "lag_close_ret_1"] = np.nan

    with pytest.raises(ValueError, match="missing exogenous rows"):
        train_sarimax_forecaster(
            df,
            model_cfg={
                "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "vol_rolling_20"],
                "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
                "split": {
                    "method": "walk_forward",
                    "train_size": train_size,
                    "test_size": 30,
                    "step_size": 30,
                    "expanding": True,
                    "max_folds": 1,
                },
                "params": {
                    "order": [1, 0, 1],
                    "seasonal_order": [0, 0, 0, 0],
                    "trend": "c",
                    "use_exog": True,
                    "maxiter": 40,
                    "allow_fallback": True,
                },
            },
        )


def test_garch_forecaster_emits_volatility_forecast() -> None:
    """
    Verify GARCH forecaster emits positive volatility forecasts on OOS rows.
    """
    df = _synthetic_ohlcv_with_returns()
    out, _, meta = train_garch_forecaster(
        df,
        model_cfg={
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 4},
            "split": {
                "method": "walk_forward",
                "train_size": 140,
                "test_size": 30,
                "step_size": 30,
                "expanding": True,
            },
            "params": {"returns_input_col": "close_ret", "mean_model": "ar1"},
        },
        returns_col="close_ret",
    )

    assert meta["model_kind"] == "garch_forecaster"
    assert int(out["pred_is_oos"].sum()) > 0
    oos_pred_vol = out.loc[out["pred_is_oos"], "pred_vol"].dropna()
    assert not oos_pred_vol.empty
    assert (oos_pred_vol > 0.0).all()
    assert meta["oos_volatility_summary"]["evaluation_rows"] > 0
    assert meta["folds"][0]["forecast_horizon"] == 4


def test_tft_forecaster_emits_quantile_outputs() -> None:
    """
    Verify TFT forecaster outputs quantiles and median forecast under OOS split.
    """
    if os.getenv("RUN_TFT_TESTS", "0") != "1":
        pytest.skip("Set RUN_TFT_TESTS=1 to run TFT integration test.")
    if not optional_dependency_stack_available("torch"):
        pytest.skip("torch is unavailable or unstable in this environment.")
    df = _synthetic_ohlcv_with_returns()
    out, _, meta = train_tft_forecaster(
        df,
        model_cfg={
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "lag_close_ret_5", "vol_rolling_20"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
            "split": {
                "method": "walk_forward",
                "train_size": 150,
                "test_size": 20,
                "step_size": 20,
                "expanding": True,
            },
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "params": {
                "lookback": 12,
                "hidden_dim": 16,
                "num_heads": 4,
                "num_layers": 1,
                "dropout": 0.1,
                "epochs": 2,
                "batch_size": 32,
                "learning_rate": 1e-3,
                "weight_decay": 1e-4,
                "quantiles": [0.1, 0.5, 0.9],
            },
        },
    )

    assert meta["model_kind"] == "tft_forecaster"
    for col in ("pred_ret", "pred_q10", "pred_q50", "pred_q90"):
        assert col in out.columns
    mask = out["pred_is_oos"] & out["pred_q10"].notna() & out["pred_q90"].notna()
    assert bool(mask.any())
    assert (out.loc[mask, "pred_q10"] <= out.loc[mask, "pred_q90"]).all()


def test_tft_forecaster_is_reproducible_with_fixed_runtime() -> None:
    """
    TFT forecaster should emit identical OOS predictions across repeated runs with fixed runtime settings.
    """
    if not optional_dependency_stack_available("torch"):
        pytest.skip("torch is unavailable or unstable in this environment.")
    script = """
import json
import numpy as np
import pandas as pd

from src.experiments.models import train_tft_forecaster

rng = np.random.default_rng(321)
n = 220
eps = rng.normal(0.0, 0.008, size=n)
rets = np.zeros(n, dtype=float)
for i in range(1, n):
    rets[i] = 0.15 * rets[i - 1] + eps[i]
close = 100.0 * np.exp(np.cumsum(rets))

idx = pd.date_range("2020-01-01", periods=n, freq="D")
df = pd.DataFrame(index=idx)
df["close"] = close
df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
df["high"] = np.maximum(df["open"], df["close"]) * 1.002
df["low"] = np.minimum(df["open"], df["close"]) * 0.998
df["volume"] = 1_000_000
df["close_ret"] = df["close"].pct_change()
df["lag_close_ret_1"] = df["close_ret"].shift(1)
df["lag_close_ret_2"] = df["close_ret"].shift(2)
df["vol_rolling_20"] = df["close_ret"].rolling(20, min_periods=5).std()

out, _, meta = train_tft_forecaster(
    df,
    model_cfg={
        "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "vol_rolling_20"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {
            "method": "walk_forward",
            "train_size": 120,
            "test_size": 20,
            "step_size": 20,
            "expanding": True,
            "max_folds": 1,
        },
        "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
        "params": {
            "lookback": 10,
            "hidden_dim": 16,
            "num_heads": 4,
            "num_layers": 1,
            "dropout": 0.1,
            "epochs": 1,
            "batch_size": 16,
            "learning_rate": 1e-3,
            "weight_decay": 1e-4,
            "quantiles": [0.1, 0.5, 0.9],
        },
    },
)

mask = out["pred_is_oos"]
payload = {
    "predictions": out.loc[mask, ["pred_ret", "pred_q10", "pred_q50", "pred_q90"]].round(8).to_dict("records"),
    "runtime": meta["runtime"],
}
print(json.dumps(payload, sort_keys=True))
"""
    proc_a = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    proc_b = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    if proc_a.returncode != 0 or proc_b.returncode != 0:
        pytest.skip("torch subprocess run is unstable in this environment.")

    assert proc_a.stdout.strip() == proc_b.stdout.strip()


def test_forecast_signal_adapters_work_on_predictions() -> None:
    """
    Verify forecast signal adapters produce bounded outputs for downstream backtesting.
    """
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "pred_ret": [-0.02, -0.001, 0.004, 0.02],
            "pred_vol": [0.02, 0.01, 0.02, 0.01],
        },
        index=idx,
    )

    thresholded = compute_forecast_threshold_signal(
        df,
        forecast_col="pred_ret",
        upper=0.002,
        lower=-0.002,
        signal_col="signal_thr",
    )
    vol_adj = compute_forecast_vol_adjusted_signal(
        df,
        forecast_col="pred_ret",
        vol_col="pred_vol",
        signal_col="signal_vol",
        clip=1.0,
    )

    assert set(thresholded["signal_thr"].unique()) <= {-1.0, 0.0, 1.0}
    assert (vol_adj["signal_vol"].abs() <= 1.0 + 1e-12).all()


def test_lightgbm_regressor_future_return_target_emits_dense_oos_predictions() -> None:
    available, detail = probe_lightgbm_runtime()
    if not available:
        pytest.skip(f"LightGBM runtime unavailable: {detail}")

    df = _synthetic_ohlcv_with_returns(n=180)
    df["atr_14"] = df["close"] * 0.01
    out, _, meta = train_lightgbm_regressor(
        df,
        model_cfg={
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "vol_rolling_20"],
            "minimum_expected_features": 2,
            "target": {
                "kind": "future_return_regression",
                "price_col": "close",
                "returns_col": "close_ret",
                "horizon_bars": 3,
                "normalize_by_volatility": True,
                "volatility_col": "atr_14",
                "clip": [-3.0, 3.0],
                "fwd_col": "target_future_r",
            },
            "split": {
                "method": "walk_forward",
                "train_size": 100,
                "test_size": 30,
                "step_size": 30,
                "expanding": True,
            },
            "params": {
                "n_estimators": 8,
                "learning_rate": 0.05,
                "num_leaves": 7,
                "min_child_samples": 5,
                "random_state": 11,
                "n_jobs": 1,
            },
        },
    )

    assert meta["model_kind"] == "lightgbm_regressor"
    assert int(out["pred_is_oos"].sum()) > 0
    assert out.loc[out["pred_is_oos"], "pred_ret"].notna().any()
    assert meta["target"]["kind"] == "future_return_regression"
    assert meta["feature_pipeline"]["model_feature_count"] == 3
    assert meta["feature_pipeline"]["reported_feature_count"] == 3
    assert meta["feature_pipeline"]["reported_feature_count"] == meta["feature_pipeline"]["actual_model_feature_count"]
    assert len(meta["feature_selection"]["feature_coverage_heatmap"]) == 3
    assert meta["folds"][0]["target_density"] > 0.0
    assert "skew" in meta["folds"][0]["regression_target_stats"]


def test_lightgbm_regressor_records_diagnostics_metadata() -> None:
    available, detail = probe_lightgbm_runtime()
    if not available:
        pytest.skip(f"LightGBM runtime unavailable: {detail}")

    df = _synthetic_ohlcv_with_returns(n=170)
    out, _, meta = train_lightgbm_regressor(
        df,
        model_cfg={
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "vol_rolling_20"],
            "minimum_expected_features": 2,
            "target": {"kind": "future_return_regression", "price_col": "close", "horizon_bars": 2},
            "split": {
                "method": "walk_forward",
                "train_size": 100,
                "test_size": 25,
                "step_size": 25,
                "expanding": True,
                "max_folds": 1,
            },
            "diagnostics": {
                "enabled": True,
                "model": {
                    "enabled": True,
                    "shap": {
                        "enabled": True,
                        "max_rows": 20,
                        "top_n_features": 3,
                        "per_prediction_top_k": 2,
                        "per_prediction_row_limit": 1,
                        "random_state": 3,
                    },
                },
            },
            "params": {
                "n_estimators": 8,
                "learning_rate": 0.05,
                "num_leaves": 7,
                "min_child_samples": 5,
                "random_state": 11,
                "n_jobs": 1,
            },
        },
    )

    fold = meta["folds"][0]
    assert out.loc[out["pred_is_oos"], "pred_ret"].notna().any()
    assert fold["lightgbm_importance"]["gain"]
    assert fold["lightgbm_importance"]["split"]
    assert "shap" in fold
    assert fold["shap"]["enabled"] is True
    assert "feature_importance_stability" in meta
    assert meta["feature_pipeline"]["reported_feature_count"] == meta["feature_pipeline"]["actual_model_feature_count"]


def test_xgboost_regressor_future_return_target_emits_dense_oos_predictions() -> None:
    available, detail = probe_xgboost_runtime()
    if not available:
        pytest.skip(f"XGBoost runtime unavailable: {detail}")

    df = _synthetic_ohlcv_with_returns(n=180)
    df["atr_14"] = df["close"] * 0.01
    out, _, meta = train_xgboost_regressor(
        df,
        model_cfg={
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "vol_rolling_20"],
            "minimum_expected_features": 2,
            "target": {
                "kind": "future_return_regression",
                "price_col": "close",
                "returns_col": "close_ret",
                "horizon_bars": 3,
                "normalize_by_volatility": True,
                "volatility_col": "atr_14",
                "clip": [-3.0, 3.0],
                "fwd_col": "target_future_r",
            },
            "split": {
                "method": "walk_forward",
                "train_size": 100,
                "test_size": 30,
                "step_size": 30,
                "expanding": True,
            },
            "params": {
                "n_estimators": 8,
                "learning_rate": 0.05,
                "max_depth": 2,
                "min_child_weight": 1,
                "subsample": 1.0,
                "colsample_bytree": 1.0,
                "objective": "reg:squarederror",
                "eval_metric": "rmse",
                "tree_method": "hist",
                "random_state": 11,
                "n_jobs": 1,
            },
        },
    )

    oos_pred = out.loc[out["pred_is_oos"], "pred_ret"]
    assert meta["model_kind"] == "xgboost_regressor"
    assert int(out["pred_is_oos"].sum()) > 0
    assert oos_pred.notna().any()
    assert oos_pred.notna().mean() > 0.8
    assert out.loc[out["pred_is_oos"] & out["pred_ret"].notna(), "pred_prob"].notna().all()
    assert meta["target"]["kind"] == "future_return_regression"
    assert meta["feature_pipeline"]["model_feature_count"] == 3
    assert meta["feature_pipeline"]["reported_feature_count"] == 3
    assert meta["feature_pipeline"]["reported_feature_count"] == meta["feature_pipeline"]["actual_model_feature_count"]
    assert meta["oos_regression_summary"]["evaluation_rows"] > 0
    assert meta["oos_classification_summary"]["evaluation_rows"] > 0
    assert meta["prediction_diagnostics"]["predicted_rows"] > 0
    assert meta["feature_importance"]["available"] is True
    assert len(meta["feature_selection"]["feature_coverage_heatmap"]) == 3
    assert meta["folds"][0]["target_density"] > 0.0
    assert meta["folds"][0]["model_train_rows"] > 0
    assert "skew" in meta["folds"][0]["regression_target_stats"]


def test_xgboost_regressor_strips_lightgbm_only_params() -> None:
    available, detail = probe_xgboost_runtime()
    if not available:
        pytest.skip(f"XGBoost runtime unavailable: {detail}")

    df = _synthetic_ohlcv_with_returns(n=150)
    out, model, meta = train_xgboost_regressor(
        df,
        model_cfg={
            "feature_cols": ["lag_close_ret_1", "lag_close_ret_2", "vol_rolling_20"],
            "target": {"kind": "future_return_regression", "price_col": "close", "horizon_bars": 2},
            "split": {
                "method": "walk_forward",
                "train_size": 90,
                "test_size": 20,
                "step_size": 20,
                "expanding": True,
                "max_folds": 1,
            },
            "params": {
                "n_estimators": 4,
                "max_depth": 2,
                "num_leaves": 7,
                "min_child_samples": 5,
                "random_state": 11,
                "n_jobs": 1,
            },
        },
    )

    params = model.get_params()
    assert out.loc[out["pred_is_oos"], "pred_ret"].notna().any()
    assert "num_leaves" not in params
    assert "min_child_samples" not in params
    assert meta["folds"][0]["runtime"]["seed"] == 11


def test_shap_diagnostics_use_tree_explainer_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeExplainer:
        def __init__(self, model: object) -> None:
            self.model = model

        def shap_values(self, x: pd.DataFrame) -> np.ndarray:
            return x.to_numpy(dtype=float) * 0.1

    fake_shap = types.SimpleNamespace(TreeExplainer=FakeExplainer)
    monkeypatch.setitem(sys.modules, "shap", fake_shap)

    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    features = pd.DataFrame({"rsi_14": [45.0, 55.0, 65.0, 50.0], "adx_14": [18.0, 25.0, 30.0, 15.0]}, index=idx)
    prediction = pd.Series([0.1, 0.2, -0.1, 0.0], index=idx)
    realized = pd.Series([0.08, 0.18, -0.05, 0.01], index=idx)

    payload = compute_lightgbm_shap_diagnostics(
        model=object(),
        features=features,
        predictions=prediction,
        realized=realized,
        feature_cols=["rsi_14", "adx_14"],
        cfg={"enabled": True, "max_rows": 4, "top_n_features": 2, "per_prediction_row_limit": 1},
    )

    assert payload["available"] is True
    assert payload["sample_size"] == 4
    assert {row["feature"] for row in payload["summary"]} == {"rsi_14", "adx_14"}
    assert payload["sample_values"]
    assert payload["per_prediction"]


def test_dense_prediction_diagnostics_compute_rank_and_monotonicity() -> None:
    prediction = pd.Series([-0.3, -0.2, -0.1, 0.1, 0.2, 0.3], dtype=float)
    realized = pd.Series([-0.2, -0.15, -0.05, 0.05, 0.15, 0.25], dtype=float)

    metrics = prediction_realized_metrics(prediction, realized)
    quantiles = prediction_quantile_table(prediction, realized, quantiles=3)
    monotonicity = quantile_monotonicity(quantiles)

    assert metrics["correlation"] > 0.95
    assert metrics["spearman_rank_correlation"] > 0.95
    assert metrics["calibration_slope"] > 0.0
    assert len(quantiles) == 3
    assert monotonicity["monotonicity"] == pytest.approx(1.0)


def test_dense_diagnostic_frames_include_turnover_cost_and_regimes() -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="D")
    frame = pd.DataFrame(
        {
            "pred_ret": [-0.20, -0.15, -0.10, -0.05, 0.05, 0.10, 0.15, 0.20],
            "expected_net_return": [-0.18, -0.13, -0.08, -0.03, 0.03, 0.08, 0.13, 0.18],
            "target_future_return_v2": [-0.21, -0.16, -0.09, -0.02, 0.04, 0.12, 0.14, 0.22],
            "pred_is_oos": [True] * 8,
            "atr_pct_rank_100": np.linspace(0.1, 0.9, 8),
            "adx_14": [12.0, 15.0, 17.0, 19.0, 25.0, 30.0, 28.0, 16.0],
            "estimated_round_trip_cost": [0.01] * 8,
        },
        index=idx,
    )
    weights = pd.DataFrame({"AAA": [0.0, -0.5, -0.5, 0.0, 0.5, 0.5, 0.0, 0.0]}, index=idx)

    frames = build_dense_forecast_diagnostic_frames(
        {"AAA": frame},
        model_meta={
            "pred_ret_col": "pred_ret",
            "fwd_col": "target_future_return_v2",
            "pred_is_oos_col": "pred_is_oos",
            "target": {"label_col": "target_future_return_v2"},
            "per_asset": {
                "AAA": {
                    "folds": [
                        {
                            "fold": 0,
                            "shap": {
                                "enabled": True,
                                "available": False,
                                "reason": "shap unavailable: No module named 'shap'",
                            },
                        }
                    ]
                }
            },
        },
        portfolio_weights=weights,
        net_returns=pd.Series([0.0, -0.01, 0.0, 0.02, 0.01, 0.0, -0.005, 0.0], index=idx),
        gross_returns=pd.Series([0.0, -0.009, 0.001, 0.021, 0.011, 0.001, -0.004, 0.0], index=idx),
        costs=pd.Series([0.0, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.0], index=idx),
        turnover=pd.Series([0.0, 0.5, 0.0, 0.5, 0.5, 0.0, 0.5, 0.0], index=idx),
        cfg={
            "signals": {"params": {"expected_net_return_col": "expected_net_return"}},
            "diagnostics": {"forecast": {"quantiles": 4, "autocorrelation_lags": [1, 2]}},
        },
    )

    assert not frames["prediction_frame"].empty
    assert not frames["prediction_quantiles"].empty
    assert not frames["regime_diagnostics"].empty
    assert not bool(frames["shap_status"]["available"].iloc[0])
    assert frames["turnover_cost"]["summary"]["total_turnover"] == pytest.approx(2.0)


def test_dense_diagnostic_plots_write_png_artifacts(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    idx = pd.date_range("2024-01-01", periods=12, freq="D")
    prediction_frame = pd.DataFrame(
        {
            "prediction": np.linspace(-0.3, 0.3, 12),
            "expected_net_return": np.linspace(-0.25, 0.25, 12),
            "realized": np.linspace(-0.2, 0.2, 12),
            "residual": np.linspace(-0.2, 0.2, 12) - np.linspace(-0.3, 0.3, 12),
        },
        index=idx,
    )
    frames = {
        "prediction_frame": prediction_frame,
        "prediction_quantiles": pd.DataFrame(
            {
                "quantile": [0, 1, 2],
                "realized_mean": [-0.1, 0.0, 0.1],
                "net_return_mean": [-0.09, -0.01, 0.08],
            }
        ),
        "prediction_autocorrelation": pd.DataFrame({"lag": [1, 2], "autocorrelation": [0.6, 0.3]}),
        "turnover_cost": {
            "timeseries": pd.DataFrame(
                {
                    "turnover": np.linspace(0.0, 0.5, 12),
                    "rolling_turnover_mean": np.linspace(0.0, 0.3, 12),
                    "gross_return": np.linspace(-0.01, 0.01, 12),
                    "net_return": np.linspace(-0.011, 0.009, 12),
                    "cost": np.full(12, 0.001),
                },
                index=idx,
            )
        },
        "shap": (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
        "lightgbm_importance": pd.DataFrame(),
    }

    paths = write_dense_diagnostic_plots(tmp_path / "diagnostics", frames)

    assert paths["prediction_histogram"].exists()
    assert paths["prediction_vs_realized"].exists()
    assert paths["prediction_quantiles"].exists()
    assert paths["turnover_timeseries"].exists()


def test_dense_return_forecast_signal_subtracts_costs_in_vol_units() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "pred_ret": [0.50, -0.50, np.nan],
            "close": [100.0, 100.0, 100.0],
            "atr_14": [1.0, 1.0, 1.0],
        },
        index=idx,
    )

    out = dense_return_forecast_signal(
        df,
        forecast_col="pred_ret",
        signal_col="expected_net_return",
        expected_net_return_col="expected_net_return",
        cost_per_turnover=0.0001,
        slippage_per_turnover=0.0001,
        cost_round_trip_mult=2.0,
        forecast_is_vol_normalized=True,
        volatility_col="atr_14",
        price_col="close",
    )

    assert out["estimated_round_trip_cost"].iloc[0] == pytest.approx(0.04)
    assert out["expected_net_return"].iloc[0] == pytest.approx(0.46)
    assert out["expected_net_return"].iloc[1] == pytest.approx(-0.46)
    assert np.isnan(out["expected_net_return"].iloc[2])


def test_probability_vol_adjusted_signal_supports_dead_zone_and_floor() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "pred_prob": [0.30, 0.48, 0.50, 0.52, 0.70],
            "pred_vol": [0.02, 0.02, 0.02, 0.02, 0.02],
        },
        index=idx,
    )

    out = compute_probability_vol_adjusted_signal(
        df,
        prob_col="pred_prob",
        vol_col="pred_vol",
        signal_col="signal_prob_vol",
        prob_center=0.5,
        upper=0.55,
        lower=0.45,
        vol_target=0.01,
        clip=0.5,
        min_signal_abs=0.05,
    )

    signal = out["signal_prob_vol"]
    assert signal.iloc[1] == 0.0
    assert signal.iloc[2] == 0.0
    assert signal.iloc[3] == 0.0
    assert signal.iloc[0] < 0.0
    assert signal.iloc[4] > 0.0


def test_probability_vol_adjusted_signal_supports_activation_filters() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "pred_prob": [0.30, 0.30, 0.70, 0.70, 0.70],
            "pred_vol": [0.02, 0.02, 0.02, 0.02, 0.02],
            "regime_vol_ratio_24_168": [1.10, 0.80, 1.20, 1.10, 1.20],
            "adx_24": [25.0, 25.0, 18.0, 22.0, 30.0],
        },
        index=idx,
    )

    out = compute_probability_vol_adjusted_signal(
        df,
        prob_col="pred_prob",
        vol_col="pred_vol",
        signal_col="signal_prob_vol",
        prob_center=0.5,
        upper=0.55,
        lower=0.45,
        vol_target=0.01,
        clip=0.5,
        min_signal_abs=0.0,
        activation_filters=[
            {"col": "regime_vol_ratio_24_168", "op": "ge", "value": 1.0},
            {"col": "adx_24", "op": "ge", "value": 20.0},
        ],
    )

    signal = out["signal_prob_vol"]
    assert signal.iloc[0] < 0.0
    assert signal.iloc[1] == 0.0
    assert signal.iloc[2] == 0.0
    assert signal.iloc[3] > 0.0
    assert signal.iloc[4] > 0.0


def test_probability_vol_adjusted_signal_resolves_activation_filter_selectors() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "pred_prob": [0.30, 0.30, 0.70, 0.70, 0.70],
            "pred_vol": [0.02, 0.02, 0.02, 0.02, 0.02],
            "regime_vol_ratio_36_144": [1.10, 0.80, 1.20, 1.10, 1.20],
            "adx_36": [25.0, 25.0, 18.0, 22.0, 30.0],
        },
        index=idx,
    )

    out = compute_probability_vol_adjusted_signal(
        df,
        prob_col="pred_prob",
        vol_col="pred_vol",
        signal_col="signal_prob_vol",
        prob_center=0.5,
        upper=0.55,
        lower=0.45,
        vol_target=0.01,
        clip=0.5,
        min_signal_abs=0.0,
        activation_filters=[
            {"selector": {"regex": "^regime_vol_ratio_[0-9]+_[0-9]+$"}, "op": "ge", "value": 1.0},
            {"selector": {"startswith": "adx_"}, "op": "ge", "value": 20.0},
        ],
    )

    signal = out["signal_prob_vol"]
    assert signal.iloc[0] < 0.0
    assert signal.iloc[1] == 0.0
    assert signal.iloc[2] == 0.0
    assert signal.iloc[3] > 0.0
    assert signal.iloc[4] > 0.0


def test_sarimax_forecasts_through_purge_gap_before_assigning_test_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    class FakeForecast:
        def __init__(self, steps: int) -> None:
            self.predicted_mean = np.arange(1, steps + 1, dtype=float)
            self.var_pred_mean = np.ones(steps, dtype=float)

    class FakeFit:
        def get_forecast(self, *, steps: int, exog: np.ndarray | None) -> FakeForecast:
            recorded["steps"] = steps
            recorded["exog_rows"] = None if exog is None else int(len(exog))
            return FakeForecast(steps)

    class FakeSarimax:
        def __init__(self, **_: object) -> None:
            pass

        def fit(self, **_: object) -> FakeFit:
            return FakeFit()

    monkeypatch.setattr(sarimax_module, "SARIMAX", FakeSarimax)
    frame = pd.DataFrame(
        {
            "target": np.linspace(-0.02, 0.02, 40),
            "feature": np.linspace(1.0, 2.0, 40),
        },
        index=pd.date_range("2024-01-01", periods=40, freq="h"),
    )

    prediction, _, _, meta = train_sarimax_fold(
        frame,
        np.arange(0, 29, dtype=int),
        np.arange(35, 38, dtype=int),
        ["feature"],
        "target",
        {
            "order": [1, 0, 0],
            "seasonal_order": [0, 0, 0, 0],
            "use_exog": True,
            "allow_fallback": False,
        },
        {},
    )

    assert prediction.tolist() == pytest.approx([7.0, 8.0, 9.0])
    assert recorded == {"steps": 9, "exog_rows": 9}
    assert meta["forecast_origin_gap_rows"] == 6


def test_garch_rolls_observable_gap_and_current_return_before_forecast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        garch_module,
        "fit_garch11_state",
        lambda *_args, **_kwargs: GarchState(
            mu=0.0,
            omega=0.0,
            alpha=1.0,
            beta=0.0,
            phi=0.0,
            last_eps=0.0,
            last_h=0.01,
            used_fallback=False,
            optimizer_message="test",
        ),
    )
    frame = pd.DataFrame({"ret": [0.0, 0.0, 0.0, 0.2, 0.3, 0.9, 0.1]})
    predictor = make_garch_fold_predictor(returns_input_col="ret")

    _, extra, _, meta = predictor(
        frame,
        np.asarray([0, 1, 2], dtype=int),
        np.asarray([5, 6], dtype=int),
        [],
        "unused",
        {"mean_model": "zero", "_target_horizon": 1},
        {},
    )

    assert float(extra["pred_vol"].iloc[0]) == pytest.approx(0.9)
    assert meta["state_origin_position"] == 2
    assert meta["first_prediction_state_position"] == 5


def test_garch_aggregates_mean_and_variance_to_target_horizon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        garch_module,
        "fit_garch11_state",
        lambda *_args, **_kwargs: GarchState(
            mu=0.02,
            omega=0.01,
            alpha=0.0,
            beta=0.0,
            phi=0.0,
            last_eps=0.0,
            last_h=0.01,
            used_fallback=False,
            optimizer_message="test",
        ),
    )
    frame = pd.DataFrame({"ret": np.full(8, 0.02, dtype=float)})
    predictor = make_garch_fold_predictor(returns_input_col="ret")

    prediction, extra, _, meta = predictor(
        frame,
        np.asarray([0, 1, 2], dtype=int),
        np.asarray([4], dtype=int),
        [],
        "unused",
        {"mean_model": "constant", "_target_horizon": 4},
        {},
    )

    assert float(prediction.iloc[0]) == pytest.approx((1.02**4) - 1.0)
    assert float(extra["pred_vol"].iloc[0]) == pytest.approx(0.2)
    assert meta["forecast_horizon"] == 4


def test_candidate_expected_r_exposes_standard_horizon_and_trains_classifier() -> None:
    phase = np.arange(100, dtype=float)
    close = 100.0 + 2.0 * np.sin(phase * np.pi / 2.0)
    frame = pd.DataFrame(
        {
            "open": np.full(100, 100.0),
            "high": np.maximum(100.0, close) + 0.01,
            "low": np.minimum(100.0, close) - 0.01,
            "close": close,
            "candidate": np.ones(100),
            "feature": np.cos(phase * np.pi / 2.0),
        },
        index=pd.date_range("2024-01-01", periods=100, freq="h"),
    )
    target = {
        "kind": "candidate_expected_r",
        "candidate_col": "candidate",
        "stop_mode": "fixed_return",
        "stop_loss_return": 0.20,
        "target_r_min": 0.01,
        "max_holding_bars": 1,
    }

    _, _, _, target_meta = build_candidate_expected_r_target(frame, target)
    assert target_meta["horizon"] == 1

    out, _, meta = train_logistic_regression_classifier(
        frame,
        {
            "feature_cols": ["feature"],
            "target": target,
            "split": {
                "method": "walk_forward",
                "train_size": 60,
                "test_size": 15,
                "step_size": 15,
                "max_folds": 1,
            },
        },
    )

    assert meta["target"]["horizon"] == 1
    assert out.loc[out["pred_is_oos"], "pred_prob"].notna().any()


def _directional_barrier_frame() -> pd.DataFrame:
    rows = 80
    position = np.arange(rows, dtype=float)
    close = 100.0 + 0.02 * position
    profit_bar = (np.arange(rows) % 2) == 0
    return pd.DataFrame(
        {
            "open": close,
            "high": close + np.where(profit_bar, 2.0, 0.2),
            "low": close - np.where(profit_bar, 0.2, 2.0),
            "close": close,
            "direction": np.ones(rows),
            "atr": np.ones(rows),
            "feature_x": np.cos(position / 3.0),
        },
        index=pd.date_range("2024-01-01", periods=rows, freq="h"),
    )


def test_directional_barrier_forecaster_validation_matches_runtime() -> None:
    frame = _directional_barrier_frame()
    model_cfg = {
        "kind": "lightgbm_regressor",
        "feature_cols": ["feature_x"],
        "target": {
            "kind": "directional_triple_barrier",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "direction_col": "direction",
            "volatility_col": "atr",
            "vertical_barrier_bars": 2,
            "add_r_multiple": True,
            "target_col": "dtb_oriented_r",
        },
        "split": {
            "method": "walk_forward",
            "train_size": 40,
            "test_size": 10,
            "step_size": 10,
            "max_folds": 1,
        },
        "final_refit": False,
    }
    validate_model_block(model_cfg)

    def fold_predictor(
        full_df: pd.DataFrame,
        train_idx: np.ndarray,
        test_idx: np.ndarray,
        _feature_cols: list[str],
        target_col: str,
        _model_params: dict[str, object],
        _runtime_meta: dict[str, object],
    ) -> tuple[pd.Series, dict[str, pd.Series], object, dict[str, object]]:
        train_target = full_df.iloc[train_idx][target_col].dropna().astype(float)
        prediction = pd.Series(
            float(train_target.mean()),
            index=full_df.index[test_idx],
            dtype="float32",
        )
        return prediction, {}, {"model": "test"}, {"model_train_rows": len(train_target)}

    out, _, meta = train_forward_forecaster(
        frame,
        model_cfg,
        model_kind="lightgbm_regressor",
        fold_predictor=fold_predictor,
        required_features=True,
        runtime_estimator_family="sklearn",
    )

    assert meta["target"]["regression_target_col"] == "dtb_oriented_r"
    assert out.loc[out["pred_is_oos"], "pred_ret"].notna().all()


def test_minimum_expected_features_accepts_exact_boundary() -> None:
    frame = pd.DataFrame(
        {
            "close": np.linspace(100.0, 110.0, 60),
            "feature_a": np.linspace(0.0, 1.0, 60),
            "feature_b": np.linspace(1.0, 0.0, 60),
        },
        index=pd.date_range("2024-01-01", periods=60, freq="h"),
    )
    base_cfg = {
        "feature_cols": ["feature_a", "feature_b"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {"method": "time", "train_size": 40, "test_size": 10},
    }

    _, features, *_ = prepare_forecaster_inputs(
        df=frame,
        model_cfg={**base_cfg, "minimum_expected_features": 2},
        model_params={},
        pred_ret_col="pred_ret",
        pred_prob_col="pred_prob",
        required_features=True,
        runtime_estimator_family="sklearn",
    )
    assert features == ["feature_a", "feature_b"]

    with pytest.raises(ValueError, match=r"2 < minimum_expected_features=3"):
        prepare_forecaster_inputs(
            df=frame,
            model_cfg={**base_cfg, "minimum_expected_features": 3},
            model_params={},
            pred_ret_col="pred_ret",
            pred_prob_col="pred_prob",
            required_features=True,
            runtime_estimator_family="sklearn",
        )
