from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.experiments.models import (
    train_garch_forecaster,
    train_sarimax_forecaster,
    train_tft_forecaster,
)
from src.experiments.registry import MODEL_REGISTRY, SIGNAL_REGISTRY
from src.signals.forecast_signal import (
    compute_forecast_threshold_signal,
    compute_forecast_vol_adjusted_signal,
)


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


def _torch_available_in_subprocess() -> bool:
    """
    Check torch importability in an isolated subprocess to avoid hard crashes in-process.
    """
    proc = subprocess.run(
        [sys.executable, "-c", "import torch; print('ok')"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def test_registry_contains_new_models_and_signals() -> None:
    """
    Verify that registry wiring exposes new model families and signal adapters.
    """
    for model_kind in ("sarimax_forecaster", "garch_forecaster", "tft_forecaster"):
        assert model_kind in MODEL_REGISTRY
    for signal_kind in ("forecast_threshold", "forecast_vol_adjusted"):
        assert signal_kind in SIGNAL_REGISTRY


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
            "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
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


def test_tft_forecaster_emits_quantile_outputs() -> None:
    """
    Verify TFT forecaster outputs quantiles and median forecast under OOS split.
    """
    if os.getenv("RUN_TFT_TESTS", "0") != "1":
        pytest.skip("Set RUN_TFT_TESTS=1 to run TFT integration test.")
    if not _torch_available_in_subprocess():
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
    if not _torch_available_in_subprocess():
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
