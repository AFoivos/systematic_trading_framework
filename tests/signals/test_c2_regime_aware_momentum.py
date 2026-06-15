from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.experiments.registry import FEATURE_REGISTRY, SIGNAL_REGISTRY
from src.experiments.support.c2_diagnostics import compute_c2_regime_aware_momentum_diagnostics
from src.signals.c2_regime_aware_momentum import build_c2_regime_aware_momentum_signal
from src.targets import build_classifier_target
from src.utils.config import load_experiment_config


CONFIG_PATH = Path("config/experiments/c2_30m_regime_aware_momentum_v1.yaml")


def _synthetic_ohlcv(periods: int = 260) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="30min", tz="UTC")
    t = np.arange(periods, dtype=float)
    close = 100.0 + 0.03 * t + 0.9 * np.sin(t / 9.0)
    open_ = close - 0.05 * np.cos(t / 6.0)
    high = np.maximum(open_, close) + 0.45
    low = np.minimum(open_, close) - 0.45
    volume = 1_000.0 + 100.0 * (1.0 + np.sin(t / 13.0))
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


def _signal_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=6, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "trend_regime": [np.nan, 1.0, -1.0, 1.0, -1.0, 1.0],
            "ppo": [np.nan, 0.020, -0.020, 0.010, -0.010, 0.020],
            "ppo_signal": [np.nan, 0.010, -0.010, 0.015, -0.005, 0.010],
            "ppo_hist": [np.nan, 0.010, -0.010, 0.010, -0.010, 0.010],
            "adx_14": [np.nan, 22.0, 24.0, 17.0, 25.0, 22.0],
            "roc_12": [np.nan, 0.010, -0.010, 0.010, -0.010, 0.010],
            "zscore_momentum_20": [np.nan, 0.30, -0.30, 0.40, -0.40, 0.30],
            "volatility_regime": [np.nan, 1.0, 1.0, 1.0, 2.0, 0.0],
        },
        index=idx,
    )


def test_c2_config_loads_and_resolves_registered_steps_and_target() -> None:
    cfg = load_experiment_config(CONFIG_PATH)

    assert cfg["strategy"]["name"] == "C2_v1_regime_aware_momentum"
    assert cfg["data"]["interval"] == "30m"
    assert cfg["signals"]["kind"] == "c2_regime_aware_momentum"
    assert cfg["signals"]["kind"] in SIGNAL_REGISTRY
    assert cfg["target"]["kind"] == "directional_triple_barrier"
    assert cfg["target"]["vertical_barrier_bars"] == 24
    assert cfg["target"]["profit_barrier_r"] == 3.0
    assert cfg["target"]["stop_barrier_r"] == 1.5
    for step in cfg["features"]:
        assert step["step"] in FEATURE_REGISTRY


def test_c2_signal_produces_long_short_and_signal_columns() -> None:
    out, meta = build_c2_regime_aware_momentum_signal(_signal_frame())

    assert meta["kind"] == "c2_regime_aware_momentum"
    assert SIGNAL_REGISTRY["c2_regime_aware_momentum"] is not None
    assert out["c2_long_candidate"].tolist() == [0, 1, 0, 0, 0, 1]
    assert out["c2_short_candidate"].tolist() == [0, 0, 1, 0, 0, 0]
    assert out["c2_signal"].tolist() == [0, 1, -1, 0, 0, 1]
    assert out["c2_signal_candidate"].tolist() == [0, 1, 1, 0, 0, 1]


def test_c2_signal_handles_rolling_window_nans_without_crashing() -> None:
    frame = _signal_frame()
    frame.loc[frame.index[:3], ["adx_14", "roc_12", "zscore_momentum_20"]] = np.nan

    out, _ = build_c2_regime_aware_momentum_signal(frame)

    assert len(out) == len(frame)
    assert out["c2_signal"].iloc[:3].eq(0).all()


def test_c2_feature_signal_target_pipeline_aligns_on_synthetic_data() -> None:
    cfg = load_experiment_config(CONFIG_PATH)
    features = apply_feature_steps(_synthetic_ohlcv(), cfg["features"], asset="SPX500")
    signaled = apply_signal_step(features, cfg["signals"], asset="SPX500")
    target, label_col, _, meta = build_classifier_target(signaled, cfg["target"])

    assert len(features) == len(signaled) == len(target)
    assert label_col == "label"
    assert meta["kind"] == "directional_triple_barrier"
    assert meta["horizon"] == 24
    assert "c2_signal" in signaled.columns
    assert "c2_signal_candidate" in signaled.columns
    assert "label_candidate" in target.columns
    assert "dtb_event_r" in target.columns
    assert int(target["label_candidate"].sum()) == int(signaled["c2_signal_candidate"].sum())


def test_c2_signal_current_bar_logic_does_not_look_ahead() -> None:
    baseline, _ = build_c2_regime_aware_momentum_signal(_signal_frame())
    mutated = _signal_frame()
    mutated.loc[mutated.index[-1], "trend_regime"] = -1.0
    mutated.loc[mutated.index[-1], "ppo"] = -0.020
    mutated.loc[mutated.index[-1], "ppo_signal"] = -0.010
    mutated.loc[mutated.index[-1], "ppo_hist"] = -0.010
    mutated.loc[mutated.index[-1], "roc_12"] = -0.010
    mutated.loc[mutated.index[-1], "zscore_momentum_20"] = -0.30
    changed, _ = build_c2_regime_aware_momentum_signal(mutated)

    compare_cols = [
        "c2_long_candidate",
        "c2_short_candidate",
        "c2_signal",
        "c2_signal_candidate",
    ]
    pd.testing.assert_frame_equal(
        baseline.iloc[:-1][compare_cols],
        changed.iloc[:-1][compare_cols],
    )


def test_c2_diagnostics_return_expected_keys() -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100.0] * 8,
            "high": [100.2, 103.2, 103.4, 100.2, 100.2, 100.2, 100.2, 100.2],
            "low": [99.8] * 8,
            "close": [100.0] * 8,
            "close_ret": [0.0] * 8,
            "atr_over_price_14": [0.01] * 8,
            "trend_regime": [1.0] * 8,
            "volatility_regime": [1.0] * 8,
            "c2_bullish_trend": [1] * 8,
            "c2_bearish_trend": [0] * 8,
            "c2_adx_pass": [1] * 8,
            "c2_ppo_long_pass": [1] * 8,
            "c2_ppo_short_pass": [0] * 8,
            "c2_roc_long_pass": [1] * 8,
            "c2_roc_short_pass": [0] * 8,
            "c2_zscore_long_pass": [1] * 8,
            "c2_zscore_short_pass": [0] * 8,
            "c2_volatility_regime_pass": [1] * 8,
            "c2_long_candidate": [1, 0, 0, 0, 0, 0, 0, 0],
            "c2_short_candidate": [0] * 8,
            "c2_signal": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "c2_signal_candidate": [1, 0, 0, 0, 0, 0, 0, 0],
        },
        index=idx,
    )
    performance = run_manual_barrier_backtest(
        frame,
        signal_col="c2_signal",
        stop_mode="volatility_stop",
        vol_col="atr_over_price_14",
        take_profit_r=3.0,
        stop_loss_r=1.5,
        max_holding_bars=4,
        allow_short=True,
    )

    diagnostics = compute_c2_regime_aware_momentum_diagnostics(
        frame,
        performance=performance,
        signal_col="c2_signal",
    )

    assert diagnostics["signal_counts"]["total_rows"] == len(frame)
    assert diagnostics["signal_counts"]["actual_trade_count"] == 1
    assert "position_diagnostics" in diagnostics
    assert diagnostics["side_diagnostics"]["long_trade_count"] == 1
    assert "performance_by_trend_regime" in diagnostics["regime_diagnostics"]
