from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.experiments.orchestration.target_stage import (
    apply_post_signal_target_to_assets,
    should_apply_post_signal_target,
)
from src.experiments.registry import FEATURE_REGISTRY, SIGNAL_REGISTRY
from src.signals.vwap_rms_ema_cross_long_signal import build_vwap_rms_ema_cross_long_signal
from src.targets import build_classifier_target
from src.utils.config import load_experiment_config


CONFIG_PATH = Path("config/experiments/c1_30m_trend_pullback_vwap_v1.yaml")


def _synthetic_ohlcv(periods: int = 260) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="30min", tz="UTC")
    t = np.arange(periods, dtype=float)
    close = 100.0 + 0.04 * t + 0.8 * np.sin(t / 7.0)
    open_ = close - 0.05 * np.cos(t / 5.0)
    high = np.maximum(open_, close) + 0.35
    low = np.minimum(open_, close) - 0.35
    volume = 1_000.0 + 100.0 * (1.0 + np.sin(t / 11.0))
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )


def test_c1_config_loads_and_resolves_registered_steps() -> None:
    cfg = load_experiment_config(CONFIG_PATH)

    assert cfg["strategy"]["name"] == "C1_v1_baseline"
    assert cfg["data"]["interval"] == "30m"
    assert cfg["signals"]["kind"] == "c1_trend_pullback_vwap"
    assert cfg["signals"]["kind"] in SIGNAL_REGISTRY
    assert cfg["target"]["kind"] == "directional_triple_barrier"
    assert cfg["target"]["vertical_barrier_bars"] == 16
    assert cfg["target"]["profit_barrier_r"] == 3.0
    assert cfg["target"]["stop_barrier_r"] == 1.5
    for step in cfg["features"]:
        assert step["step"] in FEATURE_REGISTRY


def test_c1_feature_signal_target_pipeline_aligns_on_synthetic_data() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    features = apply_feature_steps(_synthetic_ohlcv(), cfg["features"], asset="SPX500")
    signaled = apply_signal_step(features, cfg["signals"], asset="SPX500")
    target, label_col, _, meta = build_classifier_target(signaled, cfg["target"])

    assert len(features) == len(signaled) == len(target)
    assert label_col == "label"
    assert meta["kind"] == "directional_triple_barrier"
    assert meta["horizon"] == 16
    assert "signal_side" in signaled.columns
    assert "signal_candidate" in signaled.columns
    assert "label_candidate" in target.columns
    assert "dtb_event_r" in target.columns
    assert int(target["label_candidate"].sum()) == int(signaled["signal_candidate"].sum())


def test_post_signal_target_stage_applies_directional_triple_barrier() -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100.0] * 8,
            "high": [100.2, 103.2, 100.2, 100.2, 100.2, 100.2, 100.2, 100.2],
            "low": [99.8] * 8,
            "close": [100.0] * 8,
            "atr_14": [1.0] * 8,
            "signal_side": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "signal_candidate": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=idx,
    )
    target_cfg = {
        "kind": "directional_triple_barrier",
        "direction_col": "signal_side",
        "candidate_col": "signal_candidate",
        "volatility_col": "atr_14",
        "entry_price_mode": "next_open",
        "profit_barrier_r": 3.0,
        "stop_barrier_r": 1.5,
        "vertical_barrier_bars": 4,
        "neutral_label": "drop",
    }

    assert should_apply_post_signal_target({"kind": "none", "target": target_cfg}) is True
    out, meta = apply_post_signal_target_to_assets(
        {"SPX500": frame, "US100": frame.copy()},
        model_cfg={"kind": "none", "target": target_cfg},
        backtest_cfg={},
    )

    labeled = out["SPX500"]
    assert len(labeled) == len(frame)
    assert labeled.loc[idx[0], "label"] == 1.0
    assert meta["target"]["kind"] == "directional_triple_barrier"
    assert meta["target"]["labeled_rows"] == 2
    assert meta["target"]["profit_barrier_count"] == 2


def test_vwap_rms_ema_cross_long_backward_compatible_long_defaults_emit_short_columns() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "ema_50": [101.0] * 4,
            "ema_100": [100.0] * 4,
            "ema_50__root_mean_square": [100.0] * 4,
            "vwap_20__root_mean_square": [99.0, 100.5, 99.0, 100.5],
            "ppo": [0.02] * 4,
            "ppo_signal": [0.01] * 4,
        },
        index=idx,
    )

    out, meta = build_vwap_rms_ema_cross_long_signal(frame)

    assert meta["mode"] == "long_only"
    assert "vwap_rms_ema_cross_long_setup" in out.columns
    assert "vwap_rms_ema_cross_short_setup" in out.columns
    assert "vwap_rms_cross_below_ema_50_rms" in out.columns
    assert out["signal_side"].tolist() == [0, 1, 0, 1]
    assert out["vwap_rms_ema_cross_short_setup"].sum() == 0
