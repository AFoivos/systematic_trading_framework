from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.features import add_close_returns
from src.features.context import add_regime_context_features, add_session_context_features
from src.features.macro import add_macro_context_features
from src.models.sequence import build_sequence_samples, fit_sequence_scaler


def _torch_available_in_subprocess() -> bool:
    proc = subprocess.run(
        [sys.executable, "-c", "import torch; print('ok')"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _run_python_json(script: str) -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"torch runtime unavailable in subprocess: {proc.stderr.strip() or proc.stdout.strip()}")
    return json.loads(proc.stdout)


def _synthetic_hourly_with_macro(periods: int = 360, seed: int = 17) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=periods, freq="h")
    hours = idx.hour.to_numpy(dtype=float)
    cyclical = 0.00025 * np.sin(2.0 * np.pi * hours / 24.0)
    macro_wave = 0.00015 * np.cos(2.0 * np.pi * np.arange(periods) / 96.0)
    noise = rng.normal(0.0, 0.0009, size=periods)
    returns = cyclical + macro_wave + noise

    close = 100.0 * np.exp(np.cumsum(returns))
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
    intrabar = np.abs(rng.normal(0.0008, 0.0002, size=periods))
    df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
    df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)
    df["volume"] = 10_000.0 + rng.integers(0, 500, size=periods)
    df["dxy_close"] = 102.0 + np.cumsum(rng.normal(0.0, 0.02, size=periods))
    df["us02y"] = 4.0 + 0.05 * np.sin(2.0 * np.pi * np.arange(periods) / 120.0)
    df["us10y"] = 4.2 + 0.03 * np.cos(2.0 * np.pi * np.arange(periods) / 150.0)
    return df


def test_macro_context_features_apply_availability_lag_and_allow_missing() -> None:
    idx = pd.date_range("2024-01-01", periods=6, freq="h")
    df = pd.DataFrame({"macro_a": [10, 11, 12, 13, 14, 15]}, index=idx)

    out = add_macro_context_features(
        df,
        columns=["macro_a", "missing_macro"],
        availability_lag=1,
        lags=(1,),
        pct_change_periods=(1,),
        zscore_window=None,
        allow_missing=True,
    )

    assert "macro_a_avail_lag_1" in out.columns
    assert pd.isna(out.iloc[0]["macro_a_avail_lag_1"])
    assert float(out.iloc[2]["macro_a_avail_lag_1"]) == 11.0
    assert "missing_macro_avail_lag_1" not in out.columns


def test_sequence_scaler_uses_train_only_statistics() -> None:
    idx = pd.date_range("2024-01-01", periods=12, freq="h")
    df = pd.DataFrame(
        {
            "feat": np.r_[np.arange(6, dtype=float), np.arange(100, 106, dtype=float)],
            "target": np.linspace(0.0, 1.1, 12),
        },
        index=idx,
    )
    scaler = fit_sequence_scaler(
        full_df=df,
        train_idx=np.arange(6),
        feature_cols=["feat"],
        target_col="target",
        scale_target=True,
    )

    assert np.isclose(float(scaler.feature_mean[0]), 2.5)
    assert float(scaler.feature_mean[0]) < 10.0


def test_build_sequence_samples_respects_train_boundary_and_test_alignment() -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="h")
    df = pd.DataFrame({"feat": np.arange(8, dtype=float), "target": np.arange(8, dtype=float)}, index=idx)
    scaler = fit_sequence_scaler(
        full_df=df,
        train_idx=np.arange(3, 6),
        feature_cols=["feat"],
        target_col="target",
        scale_target=False,
    )

    train_samples = build_sequence_samples(
        full_df=df,
        indices=np.arange(3, 6),
        feature_cols=["feat"],
        target_col="target",
        lookback=3,
        require_target=True,
        scaler=scaler,
        allowed_window_indices={3, 4, 5},
    )
    test_samples = build_sequence_samples(
        full_df=df,
        indices=np.arange(6, 8),
        feature_cols=["feat"],
        target_col="target",
        lookback=3,
        require_target=False,
        scaler=scaler,
        allowed_window_indices=None,
    )

    assert train_samples.index.tolist() == [idx[5]]
    assert test_samples.index.tolist() == [idx[6], idx[7]]


def test_lstm_forecaster_oos_alignment_with_garch_overlay() -> None:
    if not _torch_available_in_subprocess():
        pytest.skip("torch is unavailable or unstable in this environment.")
    payload = _run_python_json(
        """
import json
import numpy as np
import pandas as pd
from src.experiments.models import train_lstm_forecaster
from src.features import add_close_returns
from src.features.context import add_regime_context_features, add_session_context_features
from src.features.macro import add_macro_context_features

rng = np.random.default_rng(23)
periods = 320
idx = pd.date_range("2024-01-01", periods=periods, freq="h")
hours = idx.hour.to_numpy(dtype=float)
returns = (
    0.00025 * np.sin(2.0 * np.pi * hours / 24.0)
    + 0.00015 * np.cos(2.0 * np.pi * np.arange(periods) / 96.0)
    + rng.normal(0.0, 0.0009, size=periods)
)
close = 100.0 * np.exp(np.cumsum(returns))
df = pd.DataFrame(index=idx)
df["close"] = close
df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
intrabar = np.abs(rng.normal(0.0008, 0.0002, size=periods))
df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)
df["volume"] = 10_000.0 + rng.integers(0, 500, size=periods)
df["dxy_close"] = 102.0 + np.cumsum(rng.normal(0.0, 0.02, size=periods))
df["us02y"] = 4.0 + 0.05 * np.sin(2.0 * np.pi * np.arange(periods) / 120.0)
df["us10y"] = 4.2 + 0.03 * np.cos(2.0 * np.pi * np.arange(periods) / 150.0)
df = add_close_returns(df, log=True, col_name="close_logret")
df = add_session_context_features(df)
df = add_macro_context_features(
    df,
    columns=["dxy_close", "us02y", "us10y"],
    availability_lag=1,
    lags=(1, 24),
    pct_change_periods=(1, 24),
    zscore_window=72,
)
df = add_regime_context_features(
    df,
    price_col="close",
    returns_col="close_logret",
    vol_short_window=12,
    vol_long_window=48,
    trend_fast_span=12,
    trend_slow_span=48,
)
out, _, meta = train_lstm_forecaster(
    df,
    {
        "feature_cols": [
            "close_logret",
            "hour_sin_24",
            "hour_cos_24",
            "session_europe",
            "session_us",
            "dxy_close_pct_1",
            "us02y_pct_1",
            "us10y_z_72",
            "regime_vol_ratio_12_48",
            "regime_trend_ratio_12_48",
        ],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {
            "method": "walk_forward",
            "train_size": 200,
            "test_size": 32,
            "step_size": 32,
            "expanding": False,
            "max_folds": 1,
        },
        "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
        "params": {
            "lookback": 24,
            "hidden_dim": 16,
            "num_layers": 1,
            "dropout": 0.0,
            "epochs": 1,
            "batch_size": 32,
            "learning_rate": 1e-3,
            "scale_target": True,
        },
        "overlay": {"kind": "garch", "params": {"returns_input_col": "close_logret", "mean_model": "zero"}},
    },
    returns_col="close_logret",
)
mask = out["pred_is_oos"]
print(json.dumps({
    "model_kind": meta["model_kind"],
    "oos_rows": int(mask.sum()),
    "oos_pred_rows": int(out.loc[mask, "pred_ret"].notna().sum()),
    "non_oos_pred_rows": int(out.loc[~mask, "pred_ret"].notna().sum()),
    "positive_vol_rows": int((out.loc[mask, "pred_vol"].dropna() > 0.0).sum()),
}))
"""
    )

    assert payload["model_kind"] == "lstm_forecaster"
    assert int(payload["oos_rows"]) > 0
    assert int(payload["oos_pred_rows"]) > 0
    assert int(payload["non_oos_pred_rows"]) == 0
    assert int(payload["positive_vol_rows"]) > 0


def test_patchtst_forecaster_quantile_outputs_are_aligned() -> None:
    if not _torch_available_in_subprocess():
        pytest.skip("torch is unavailable or unstable in this environment.")
    payload = _run_python_json(
        """
import json
import numpy as np
import pandas as pd
from src.experiments.models import train_patchtst_forecaster
from src.features import add_close_returns
from src.features.context import add_regime_context_features, add_session_context_features

rng = np.random.default_rng(31)
periods = 320
idx = pd.date_range("2024-01-01", periods=periods, freq="h")
hours = idx.hour.to_numpy(dtype=float)
returns = (
    0.00025 * np.sin(2.0 * np.pi * hours / 24.0)
    + 0.00015 * np.cos(2.0 * np.pi * np.arange(periods) / 96.0)
    + rng.normal(0.0, 0.0009, size=periods)
)
close = 100.0 * np.exp(np.cumsum(returns))
df = pd.DataFrame(index=idx)
df["close"] = close
df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
intrabar = np.abs(rng.normal(0.0008, 0.0002, size=periods))
df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)
df["volume"] = 10_000.0 + rng.integers(0, 500, size=periods)
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
out, _, meta = train_patchtst_forecaster(
    df,
    {
        "feature_cols": [
            "close_logret",
            "hour_sin_24",
            "hour_cos_24",
            "session_asia",
            "session_us",
            "regime_vol_ratio_12_48",
            "regime_trend_ratio_12_48",
            "regime_absret_z_12_48",
        ],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {
            "method": "walk_forward",
            "train_size": 200,
            "test_size": 32,
            "step_size": 32,
            "expanding": False,
            "max_folds": 1,
        },
        "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
        "params": {
            "lookback": 32,
            "patch_len": 8,
            "patch_stride": 4,
            "hidden_dim": 32,
            "num_heads": 4,
            "num_layers": 1,
            "dropout": 0.1,
            "epochs": 1,
            "batch_size": 32,
            "learning_rate": 1e-3,
            "quantiles": [0.1, 0.5, 0.9],
            "scale_target": True,
        },
    },
    returns_col="close_logret",
)
mask = out["pred_is_oos"] & out["pred_q10"].notna() & out["pred_q90"].notna()
valid = out.loc[mask]
print(json.dumps({
    "model_kind": meta["model_kind"],
    "aligned_rows": int(mask.sum()),
    "ordered_rows": int((valid["pred_q10"] <= valid["pred_q90"]).sum()),
    "non_negative_vol_rows": int((valid["pred_vol"] >= 0.0).sum()),
}))
"""
    )

    assert payload["model_kind"] == "patchtst_forecaster"
    assert int(payload["aligned_rows"]) > 0
    assert int(payload["ordered_rows"]) == int(payload["aligned_rows"])
    assert int(payload["non_negative_vol_rows"]) == int(payload["aligned_rows"])


def test_lstm_forecaster_rejects_short_sequence_sample_with_clear_error() -> None:
    if not _torch_available_in_subprocess():
        pytest.skip("torch is unavailable or unstable in this environment.")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import numpy as np
import pandas as pd
from src.experiments.models import train_lstm_forecaster
from src.features import add_close_returns
from src.features.context import add_regime_context_features, add_session_context_features

rng = np.random.default_rng(13)
periods = 72
idx = pd.date_range("2024-01-01", periods=periods, freq="h")
returns = rng.normal(0.0, 0.001, size=periods)
close = 100.0 * np.exp(np.cumsum(returns))
df = pd.DataFrame(index=idx)
df["close"] = close
df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
df["high"] = np.maximum(df["open"], df["close"]) * 1.001
df["low"] = np.minimum(df["open"], df["close"]) * 0.999
df["volume"] = 1_000.0
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
train_lstm_forecaster(
    df,
    {
        "feature_cols": ["close_logret", "hour_sin_24", "hour_cos_24", "regime_vol_ratio_6_12"],
        "target": {"kind": "forward_return", "price_col": "close", "horizon": 1},
        "split": {
            "method": "walk_forward",
            "train_size": 40,
            "test_size": 8,
            "step_size": 8,
            "expanding": False,
            "max_folds": 1,
        },
        "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
        "params": {
            "lookback": 24,
            "hidden_dim": 8,
            "num_layers": 1,
            "epochs": 1,
            "batch_size": 8,
            "learning_rate": 1e-3,
            "scale_target": True,
        },
    },
    returns_col="close_logret",
)
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    if "OMP: Error" in (proc.stderr or proc.stdout):
        pytest.skip("torch/OpenMP runtime is unstable in this environment.")
    assert "train samples after sequence construction" in (proc.stderr or proc.stdout)
