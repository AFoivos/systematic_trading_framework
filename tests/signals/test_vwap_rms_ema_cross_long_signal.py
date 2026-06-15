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
            "mfi_14": [50.0] * 7,
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


def test_vwap_rms_ema_cross_long_signal_applies_mfi_confirmation() -> None:
    frame = _short_frame()
    frame["ema_50"] = [100.0] * len(frame)
    frame["ema_100"] = [99.0] * len(frame)
    frame["vwap_20__root_mean_square"] = [99.0, 99.5, 100.5, 99.5, 100.5, 99.5, 100.5]
    frame["ppo"] = [0.00, 0.01, 0.02, 0.01, 0.02, 0.01, 0.02]
    frame["ppo_signal"] = [0.00, 0.00, 0.01, 0.00, 0.01, 0.00, 0.01]
    frame["mfi_14"] = [50.0, 50.0, 35.0, 50.0, 50.0, 50.0, 85.0]

    out, meta = build_vwap_rms_ema_cross_long_signal(
        frame,
        {"use_mfi_confirmation": True, "mfi_lower": 40.0, "mfi_upper": 80.0},
    )

    assert meta["use_mfi_confirmation"] is True
    assert out["mfi_confirmation"].tolist() == [1, 1, 0, 1, 1, 1, 0]
    assert out["signal_side"].sum() == 1
    assert out.loc[frame.index[4], "signal_side"] == 1


def test_vwap_rms_ema_cross_long_signal_can_disable_ppo_requirement() -> None:
    frame = _short_frame().drop(columns=["ppo", "ppo_signal"])
    frame["ema_50"] = [100.0] * len(frame)
    frame["ema_100"] = [99.0] * len(frame)
    frame["vwap_20__root_mean_square"] = [99.0, 99.5, 100.5, 99.5, 100.5, 99.5, 100.5]

    out, meta = build_vwap_rms_ema_cross_long_signal(frame, {"use_ppo_confirmation": False})

    assert meta["use_ppo_confirmation"] is False
    assert out["signal_candidate"].sum() == 3


def test_vwap_rms_ema_cross_long_signal_delays_entries() -> None:
    frame = _short_frame()
    frame["ema_50"] = [100.0] * len(frame)
    frame["ema_100"] = [99.0] * len(frame)
    frame["vwap_20__root_mean_square"] = [99.0, 99.5, 100.5, 99.5, 100.5, 99.5, 100.5]
    frame["ppo"] = [0.00, 0.01, 0.02, 0.01, 0.02, 0.01, 0.02]
    frame["ppo_signal"] = [0.00, 0.00, 0.01, 0.00, 0.01, 0.00, 0.01]

    out, meta = build_vwap_rms_ema_cross_long_signal(frame, {"entry_delay_bars": 1})

    assert meta["entry_delay_bars"] == 1
    assert out["vwap_rms_ema_cross_long_setup"].tolist() == [0, 0, 1, 0, 1, 0, 1]
    assert out["signal_side"].tolist() == [0, 0, 0, 1, 0, 1, 0]


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
