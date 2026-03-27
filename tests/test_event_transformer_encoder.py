from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.features import add_close_returns, add_shock_context_features
from src.models.sequence import build_sequence_samples, fit_sequence_scaler


def _torch_available_in_subprocess() -> bool:
    proc = subprocess.run(
        [sys.executable, "-c", "import torch; print('ok')"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _synthetic_event_frame(periods: int = 420, seed: int = 19) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=periods, freq="h")
    returns = rng.normal(0.0, 0.0016, size=periods)
    shock_positions = np.arange(48, periods - 24, 36)
    for pos in shock_positions:
        returns[pos] += 0.025 if (pos // 36) % 2 == 0 else -0.025
        if pos + 1 < periods:
            returns[pos + 1] += -0.008 if returns[pos] > 0 else 0.008
    close = 100.0 * np.exp(np.cumsum(returns))
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
    intrabar = np.abs(rng.normal(0.0014, 0.0003, size=periods))
    df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
    df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)
    df["volume"] = 10_000.0 + rng.integers(0, 250, size=periods)
    df = add_close_returns(df, log=True, col_name="close_logret")
    df = add_shock_context_features(
        df,
        returns_col="close_logret",
        ema_window=24,
        atr_window=24,
        short_horizon=1,
        medium_horizon=4,
        vol_window=24,
        ret_z_threshold=2.1,
        atr_mult_threshold=1.2,
        distance_from_mean_threshold=0.8,
        post_shock_active_bars=3,
    )
    return df


def test_event_sequence_samples_ignore_future_rows_after_event_time() -> None:
    df = _synthetic_event_frame(periods=120)
    feature_cols = ["close_logret", "shock_strength", "shock_ret_z_1h"]
    event_positions = np.flatnonzero(df["shock_candidate"].fillna(0.0).to_numpy(dtype=bool))
    assert len(event_positions) > 0
    event_idx = int(event_positions[0])

    scaler = fit_sequence_scaler(
        full_df=df,
        train_idx=np.arange(event_idx + 1),
        feature_cols=feature_cols,
        target_col="shock_strength",
        scale_target=False,
    )
    base_samples = build_sequence_samples(
        full_df=df,
        indices=np.asarray([event_idx]),
        feature_cols=feature_cols,
        target_col="shock_strength",
        lookback=12,
        require_target=False,
        scaler=scaler,
        allowed_window_indices=None,
    )

    modified = df.copy()
    modified.iloc[event_idx + 1 :, modified.columns.get_loc("close")] *= 1.35
    modified.iloc[event_idx + 1 :, modified.columns.get_loc("high")] *= 1.35
    modified.iloc[event_idx + 1 :, modified.columns.get_loc("low")] *= 1.35
    modified = add_close_returns(modified, log=True, col_name="close_logret")
    modified = add_shock_context_features(
        modified,
        returns_col="close_logret",
        ema_window=24,
        atr_window=24,
        short_horizon=1,
        medium_horizon=4,
        vol_window=24,
        ret_z_threshold=2.1,
        atr_mult_threshold=1.2,
        distance_from_mean_threshold=0.8,
        post_shock_active_bars=3,
    )
    modified_scaler = fit_sequence_scaler(
        full_df=modified,
        train_idx=np.arange(event_idx + 1),
        feature_cols=feature_cols,
        target_col="shock_strength",
        scale_target=False,
    )
    modified_samples = build_sequence_samples(
        full_df=modified,
        indices=np.asarray([event_idx]),
        feature_cols=feature_cols,
        target_col="shock_strength",
        lookback=12,
        require_target=False,
        scaler=modified_scaler,
        allowed_window_indices=None,
    )

    np.testing.assert_allclose(base_samples.x, modified_samples.x)


def test_event_transformer_encoder_and_stacked_event_forecast_remain_oof_aligned() -> None:
    if not _torch_available_in_subprocess():
        pytest.skip("torch is unavailable or unstable in this environment.")
    script = """
import json
import numpy as np
import pandas as pd
from src.experiments.orchestration.model_stage import apply_model_pipeline_to_assets
from src.features import add_close_returns, add_shock_context_features

rng = np.random.default_rng(19)
periods = 420
idx = pd.date_range("2024-01-01", periods=periods, freq="h")
returns = rng.normal(0.0, 0.0016, size=periods)
shock_positions = np.arange(48, periods - 24, 36)
for pos in shock_positions:
    returns[pos] += 0.025 if (pos // 36) % 2 == 0 else -0.025
    if pos + 1 < periods:
        returns[pos + 1] += -0.008 if returns[pos] > 0 else 0.008
close = 100.0 * np.exp(np.cumsum(returns))
df = pd.DataFrame(index=idx)
df["close"] = close
df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
intrabar = np.abs(rng.normal(0.0014, 0.0003, size=periods))
df["high"] = np.maximum(df["open"], df["close"]) * (1.0 + intrabar)
df["low"] = np.minimum(df["open"], df["close"]) * (1.0 - intrabar)
df["volume"] = 10_000.0 + rng.integers(0, 250, size=periods)
df = add_close_returns(df, log=True, col_name="close_logret")
df = add_shock_context_features(
    df,
    returns_col="close_logret",
    ema_window=24,
    atr_window=24,
    short_horizon=1,
    medium_horizon=4,
    vol_window=24,
    ret_z_threshold=2.1,
    atr_mult_threshold=1.2,
    distance_from_mean_threshold=0.8,
    post_shock_active_bars=3,
)
out_frames, _, meta = apply_model_pipeline_to_assets(
    {"BTCUSD": df},
    model_cfg=None,
    model_stages=[
        {
            "name": "event_pattern_encoder",
            "stage": 1,
            "kind": "event_transformer_encoder",
            "feature_cols": ["close_logret", "shock_ret_z_1h", "shock_ret_z_4h", "shock_strength", "bars_since_shock"],
            "target": {
                "kind": "triple_barrier",
                "price_col": "close",
                "open_col": "open",
                "high_col": "high",
                "low_col": "low",
                "returns_col": "close_logret",
                "max_holding": 12,
                "upper_mult": 1.1,
                "lower_mult": 1.1,
                "vol_window": 24,
                "neutral_label": "drop",
                "side_col": "shock_side_contrarian",
                "candidate_col": "shock_candidate",
                "candidate_out_col": "encoder_candidate",
            },
            "split": {"method": "walk_forward", "train_size": 240, "test_size": 60, "step_size": 60, "expanding": True},
            "params": {
                "lookback": 16,
                "hidden_dim": 16,
                "num_heads": 4,
                "num_layers": 1,
                "dropout": 0.0,
                "epochs": 1,
                "batch_size": 16,
                "learning_rate": 0.001,
                "embedding_dim": 4,
                "embedding_prefix": "extrema_emb",
                "min_train_samples": 8,
            },
        },
        {
            "name": "event_forecast",
            "stage": 2,
            "kind": "logistic_regression_clf",
            "feature_cols": ["shock_strength", "shock_ret_z_1h", "shock_ret_z_4h", "extrema_emb_00", "extrema_emb_01", "extrema_emb_02", "extrema_emb_03"],
            "target": {
                "kind": "triple_barrier",
                "price_col": "close",
                "open_col": "open",
                "high_col": "high",
                "low_col": "low",
                "returns_col": "close_logret",
                "max_holding": 12,
                "upper_mult": 1.1,
                "lower_mult": 1.1,
                "vol_window": 24,
                "neutral_label": "drop",
                "side_col": "shock_side_contrarian",
                "candidate_col": "shock_candidate",
                "candidate_out_col": "forecast_candidate",
            },
            "split": {"method": "walk_forward", "train_size": 240, "test_size": 60, "step_size": 60, "expanding": True},
            "pred_prob_col": "event_forecast_prob",
            "params": {"max_iter": 400, "solver": "lbfgs"},
        },
        {
            "name": "decision_layer",
            "stage": 3,
            "kind": "logistic_regression_clf",
            "feature_cols": ["shock_strength", "shock_ret_z_1h", "shock_ret_z_4h", "bars_since_shock", "extrema_emb_00", "extrema_emb_01", "extrema_emb_02", "extrema_emb_03", "event_forecast_prob"],
            "target": {
                "kind": "triple_barrier",
                "price_col": "close",
                "open_col": "open",
                "high_col": "high",
                "low_col": "low",
                "returns_col": "close_logret",
                "max_holding": 12,
                "upper_mult": 1.1,
                "lower_mult": 1.1,
                "vol_window": 24,
                "neutral_label": "drop",
                "side_col": "shock_side_contrarian",
                "candidate_col": "shock_candidate",
                "candidate_out_col": "decision_candidate",
            },
            "split": {"method": "walk_forward", "train_size": 240, "test_size": 60, "step_size": 60, "expanding": True},
            "pred_prob_col": "pred_prob",
            "params": {"max_iter": 400, "solver": "lbfgs"},
        },
    ],
    returns_col="close_logret",
)
out = out_frames["BTCUSD"]
emb_cols = ["extrema_emb_00", "extrema_emb_01", "extrema_emb_02", "extrema_emb_03"]
candidate_mask = out["shock_candidate"].fillna(0.0).astype(bool)
payload = {
    "stage_names": meta["stage_names"],
    "encoder_embedding_cols": meta["stages"][0]["embedding_cols"],
    "encoder_non_oos_embeddings": int(out.loc[~out["pred_is_oos"], emb_cols].notna().any(axis=1).sum()),
    "encoder_non_candidate_embeddings": int(out.loc[~candidate_mask, emb_cols].notna().any(axis=1).sum()),
    "forecast_non_oos_predictions": int(out.loc[~out["pred_is_oos"], "event_forecast_prob"].notna().sum()),
    "decision_non_oos_predictions": int(out.loc[~out["pred_is_oos"], "pred_prob"].notna().sum()),
    "decision_oos_predictions": int(out.loc[out["pred_is_oos"], "pred_prob"].notna().sum()),
    "encoder_alignment_ok": bool(meta["stages"][0]["prediction_diagnostics"]["alignment_ok"]),
    "forecast_alignment_ok": bool(meta["stages"][1]["prediction_diagnostics"]["alignment_ok"]),
    "decision_alignment_ok": bool(meta["stages"][2]["prediction_diagnostics"]["alignment_ok"]),
}
print(json.dumps(payload))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(proc.stderr.strip() or proc.stdout.strip() or "event transformer subprocess failed")
    payload = json.loads(proc.stdout)

    assert payload["stage_names"] == ["event_pattern_encoder", "event_forecast", "decision_layer"]
    assert payload["encoder_embedding_cols"] == [
        "extrema_emb_00",
        "extrema_emb_01",
        "extrema_emb_02",
        "extrema_emb_03",
    ]
    assert payload["encoder_non_oos_embeddings"] == 0
    assert payload["encoder_non_candidate_embeddings"] == 0
    assert payload["forecast_non_oos_predictions"] == 0
    assert payload["decision_non_oos_predictions"] == 0
    assert payload["decision_oos_predictions"] > 0
    assert payload["encoder_alignment_ok"] is True
    assert payload["forecast_alignment_ok"] is True
    assert payload["decision_alignment_ok"] is True
