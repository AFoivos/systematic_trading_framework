from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.signals.vwap_rms_ema_cross_long_signal import build_vwap_rms_ema_cross_long_signal
from src.utils.config import load_experiment_config


def _short_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=7, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "ema_50": [99.0] * 7,
            "ema_100": [100.0] * 7,
            "ema_50__root_mean_square": [100.0] * 7,
            "vwap_20__root_mean_square": [101.0, 100.5, 99.5, 100.5, 99.5, 100.5, 99.5],
            "ppo": [-0.01, -0.02, -0.03, -0.02, -0.03, -0.02, -0.03],
            "ppo_signal": [0.0, -0.01, -0.02, -0.01, -0.02, -0.01, -0.02],
        },
        index=idx,
    )


def test_vwap_rms_ema_cross_long_signal_supports_short_only_mode() -> None:
    out, meta = build_vwap_rms_ema_cross_long_signal(_short_frame(), {"mode": "short_only"})

    assert meta["mode"] == "short_only"
    assert meta["long_candidates"] == 0
    assert meta["short_candidates"] == 3
    assert out["signal_side"].tolist() == [0, 0, -1, 0, -1, 0, -1]
    assert out["signal_side"].max() == 0
    assert out["signal_candidate"].sum() == 3


def test_spx500_vwap_rms_ema_cross_short_only_config_loads_without_a_model() -> None:
    path = Path(
        "config/experiments/ema_rms_ppo_vwap/short_only/"
        "spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml"
    )
    cfg = load_experiment_config(path)

    assert cfg["model"]["kind"] == "none"
    assert cfg["signals"]["kind"] == "vwap_rms_ema_cross_long"
    assert cfg["signals"]["params"]["mode"] == "short_only"
    assert cfg["signals"]["params"]["short_regime_col"] == "ema_50_below_ema_100"
    assert cfg["target"]["diagnostic_feature_cols"][6] == "ema_50_below_ema_100"
    assert cfg["target"]["diagnostic_feature_cols"][13] == "vwap_rms_ema_cross_short_setup"
    assert cfg["backtest"]["engine"] == "manual_barrier"
    assert cfg["backtest"]["allow_short"] is True
