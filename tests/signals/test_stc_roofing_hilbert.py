from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.experiments.registry import FEATURE_REGISTRY, SIGNAL_REGISTRY
from src.experiments.support.stc_roofing_hilbert_diagnostics import (
    compute_stc_roofing_hilbert_diagnostics,
)
from src.signals.stc_roofing_hilbert import build_stc_roofing_hilbert_signal
from src.utils.config import load_experiment_config


CONFIG_PATH = Path("config/experiments/stc_roofing_hilbert_30m_v1.yaml")


def _require_config_fixture(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.exists():
        pytest.skip(f"optional config fixture not present: {resolved}")
    return resolved


def _synthetic_ohlcv(periods: int = 320) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="30min", tz="UTC")
    t = np.arange(periods, dtype=float)
    close = 100.0 + 0.025 * t + 1.2 * np.sin(t / 8.0) + 0.35 * np.cos(t / 3.0)
    open_ = close - 0.04 * np.cos(t / 5.0)
    high = np.maximum(open_, close) + 0.45
    low = np.minimum(open_, close) - 0.45
    volume = 1_000.0 + 80.0 * (1.0 + np.sin(t / 13.0))
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
            "ema_50": [101.0, 101.0, 99.0, 99.0, 101.0, 101.0],
            "ema_100": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "roofing_filter": [0.20, 0.50, -0.40, -0.60, 0.50, 0.40],
            "roofing_slope": [np.nan, 0.20, -0.10, -0.20, 0.15, -0.10],
            "stc": [20.0, 30.0, 80.0, 70.0, 20.0, 30.0],
            "hilbert_cycle_ok": [1, 0, 1, 1, 1, 1],
            "hilbert_amplitude_rising": [1, 1, 1, 1, 1, 1],
        },
        index=idx,
    )


def test_stc_roofing_config_loads_and_resolves_registered_steps() -> None:
    cfg = load_experiment_config(_require_config_fixture(CONFIG_PATH))

    assert cfg["strategy"]["name"] == "stc_roofing_ema_30m_v1"
    assert cfg["data"]["interval"] == "30m"
    assert cfg["signals"]["kind"] == "stc_roofing_hilbert"
    assert cfg["signals"]["kind"] in SIGNAL_REGISTRY
    assert cfg["backtest"]["engine"] == "manual_barrier"
    assert cfg["backtest"]["stop_loss_r"] == 1.5
    assert cfg["backtest"]["take_profit_r"] == 3.0
    assert cfg["backtest"]["max_holding_bars"] is None
    assert [step["step"] for step in cfg["features"]] == [
        "returns",
        "trend",
        "atr",
        "roofing_filter",
        "schaff_trend_cycle",
    ]
    for step in cfg["features"]:
        assert step["step"] in FEATURE_REGISTRY


def test_stc_roofing_signal_produces_long_short_and_signal_columns() -> None:
    out, meta = build_stc_roofing_hilbert_signal(_signal_frame())

    assert meta["kind"] == "stc_roofing_hilbert"
    assert SIGNAL_REGISTRY["stc_roofing_hilbert"] is not None
    assert out["stc_roofing_long_candidate"].tolist() == [0, 1, 0, 0, 0, 0]
    assert out["stc_roofing_short_candidate"].tolist() == [0, 0, 0, 1, 0, 0]
    assert out["stc_roofing_signal"].tolist() == [0, 1, 0, -1, 0, 0]
    assert set(out["stc_roofing_signal"].unique()).issubset({-1, 0, 1})


def test_stc_roofing_signal_handles_rolling_window_nans_without_crashing() -> None:
    frame = _signal_frame()
    frame.loc[frame.index[:3], ["ema_50", "roofing_filter", "roofing_slope", "stc"]] = np.nan

    out, _ = build_stc_roofing_hilbert_signal(frame)

    assert len(out) == len(frame)
    assert out["stc_roofing_signal"].iloc[:3].eq(0).all()


def test_stc_roofing_hilbert_filter_overrides_final_candidates_when_enabled() -> None:
    out, _ = build_stc_roofing_hilbert_signal(_signal_frame(), use_hilbert_filter=True)

    assert out["stc_roofing_long_candidate"].tolist() == [0, 0, 0, 0, 0, 0]
    assert out["stc_roofing_short_candidate"].tolist() == [0, 0, 0, 1, 0, 0]
    assert out["stc_roofing_hilbert_long_candidate"].tolist() == [0, 0, 0, 0, 0, 0]
    assert out["stc_roofing_hilbert_short_candidate"].tolist() == [0, 0, 0, 1, 0, 0]
    assert out["stc_roofing_signal"].tolist() == [0, 0, 0, -1, 0, 0]


def test_stc_roofing_entry_delay_shifts_signal() -> None:
    out, _ = build_stc_roofing_hilbert_signal(_signal_frame(), entry_delay_bars=1)

    assert out["stc_roofing_signal"].tolist() == [0, 0, 1, 0, -1, 0]
    assert out["stc_roofing_long_candidate"].tolist() == [0, 1, 0, 0, 0, 0]
    assert out["stc_roofing_short_candidate"].tolist() == [0, 0, 0, 1, 0, 0]


def test_stc_roofing_feature_signal_pipeline_aligns_on_synthetic_data() -> None:
    cfg = load_experiment_config(_require_config_fixture(CONFIG_PATH))
    features = apply_feature_steps(_synthetic_ohlcv(), cfg["features"], asset="SPX500")
    signaled = apply_signal_step(features, cfg["signals"], asset="SPX500")

    assert len(features) == len(signaled)
    assert "stc_roofing_signal" in signaled.columns
    assert "stc_roofing_signal_candidate" in signaled.columns
    assert signaled["stc_roofing_signal"].isin([-1, 0, 1]).all()

    performance = run_manual_barrier_backtest(
        signaled,
        signal_col="stc_roofing_signal",
        stop_mode="volatility_stop",
        vol_col="atr_over_price_14",
        take_profit_r=3.0,
        stop_loss_r=1.5,
        max_holding_bars=None,
        allow_short=True,
    )
    assert len(performance.returns) == len(signaled)
    assert performance.returns.index.equals(signaled.index)


def test_stc_roofing_signal_current_bar_logic_does_not_look_ahead() -> None:
    baseline, _ = build_stc_roofing_hilbert_signal(_signal_frame())
    mutated = _signal_frame()
    mutated.loc[mutated.index[-1], "ema_50"] = 99.0
    mutated.loc[mutated.index[-1], "ema_100"] = 101.0
    mutated.loc[mutated.index[-1], "roofing_filter"] = -1.0
    mutated.loc[mutated.index[-1], "roofing_slope"] = -1.0
    mutated.loc[mutated.index[-1], "stc"] = 10.0
    changed, _ = build_stc_roofing_hilbert_signal(mutated)

    compare_cols = [
        "stc_roofing_long_candidate",
        "stc_roofing_short_candidate",
        "stc_roofing_signal",
        "stc_roofing_signal_candidate",
    ]
    pd.testing.assert_frame_equal(
        baseline.iloc[:-1][compare_cols],
        changed.iloc[:-1][compare_cols],
    )


def test_stc_roofing_diagnostics_return_expected_keys() -> None:
    signaled, _ = build_stc_roofing_hilbert_signal(_signal_frame())
    signaled["volatility_regime"] = [0, 1, 1, 2, 2, 2]
    trades = pd.DataFrame(
        {
            "side": ["long", "short"],
            "entry_timestamp": [signaled.index[1], signaled.index[3]],
            "gross_return": [0.03, -0.01],
            "net_return": [0.02, -0.015],
            "cost": [0.01, 0.005],
            "realized_r": [1.5, -0.8],
        }
    )
    performance = SimpleNamespace(
        trades=trades,
        summary={
            "cumulative_return": 0.005,
            "sharpe": 1.2,
            "sortino": 1.1,
            "calmar": 0.9,
            "max_drawdown": -0.02,
            "cost_to_gross_pnl": 0.5,
        },
    )

    diagnostics = compute_stc_roofing_hilbert_diagnostics(
        signaled,
        performance=performance,
        signal_col="stc_roofing_signal",
    )

    assert diagnostics["signal_counts"]["total_rows"] == len(signaled)
    assert diagnostics["signal_counts"]["final_signal_rows"] == 2
    assert diagnostics["signal_counts"]["actual_trade_count"] == 2
    assert diagnostics["performance_diagnostics"]["trade_count"] == 2
    assert diagnostics["performance_diagnostics"]["average_r"] == 0.35
    assert set(diagnostics["side_diagnostics"]) == {"long", "short"}
    assert "2024" in diagnostics["performance_by_year"]
    assert set(diagnostics["performance_by_volatility_regime"]) == {"1", "2"}
