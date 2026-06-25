from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.experiments.support.ehlers_continuation_short_diagnostics import (
    compute_ehlers_continuation_short_diagnostics,
)
from src.signals.ehlers_continuation_short_signal import build_ehlers_continuation_short_signal
from src.utils.config import load_experiment_config
from src.utils.config_kinds import FEATURE_KINDS, SIGNAL_KINDS


CONFIG_PATH = Path("config/experiments/ehlers_continuation_short_v1.yaml")
ABLATION_CONFIGS = [
    Path("config/experiments/ehlers_continuation_short_without_mama_fama.yaml"),
    Path("config/experiments/ehlers_continuation_short_without_decycler.yaml"),
    Path("config/experiments/ehlers_continuation_short_without_ema_regime.yaml"),
    Path("config/experiments/ehlers_continuation_short_roofing_simple.yaml"),
    Path("config/experiments/ehlers_continuation_short_entry_delay_1.yaml"),
    Path("config/experiments/ehlers_continuation_short_entry_delay_2.yaml"),
]


def _require_config_fixture(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.exists():
        pytest.skip(f"optional config fixture not present: {resolved}")
    return resolved


def _signal_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=7, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "ema_50": [101.0, 99.0, 99.0, 99.0, 99.0, 101.0, 99.0],
            "ema_100": [100.0] * 7,
            "mama": [1.0, 0.0, -1.0, -2.0, -3.0, -4.0, -5.0],
            "fama": [0.0, 1.0, 0.0, -1.0, -2.0, -3.0, -4.0],
            "roofing_filter_48_10": [-0.10, -0.30, -0.50, -0.40, 0.10, -0.60, -0.70],
            "roofing_filter_48_10_slope": [-0.20, -0.10, -0.20, -0.50, -0.10, -0.10, -0.20],
            "decycler_oscillator_30_60": [-0.10, -0.10, -0.10, -0.10, -0.10, -0.10, 0.10],
        },
        index=idx,
    )


def test_ehlers_continuation_short_config_loads_and_resolves_registered_steps() -> None:
    cfg = load_experiment_config(_require_config_fixture(CONFIG_PATH))

    assert cfg["strategy"]["name"] == "ehlers_continuation_short_v1"
    assert cfg["data"]["interval"] == "30m"
    assert cfg["signals"]["kind"] == "ehlers_continuation_short"
    assert cfg["signals"]["kind"] in SIGNAL_KINDS
    assert cfg["signals"]["params"]["entry_mode"] == "state"
    assert cfg["signals"]["params"]["short_only"] is True
    assert cfg["backtest"]["allow_short"] is True
    assert cfg["backtest"]["short_only"] is True
    assert cfg["backtest"]["take_profit_r"] == 3.0
    assert cfg["backtest"]["stop_loss_r"] == 1.5
    assert cfg["backtest"]["max_holding_bars"] is None
    assert cfg["diagnostics"]["robustness"]["cost_multipliers"] == [2.0, 3.0, 5.0]
    assert [step["step"] for step in cfg["features"]] == [
        "returns",
        "trend",
        "mama",
        "fama",
        "roofing_filter",
        "decycler_oscillator",
        "atr",
    ]
    for step in cfg["features"]:
        assert step["step"] in FEATURE_KINDS


def test_ehlers_continuation_signal_outputs_short_only_columns() -> None:
    out, meta = build_ehlers_continuation_short_signal(_signal_frame())

    assert meta["kind"] == "ehlers_continuation_short"
    assert "ehlers_continuation_short" in SIGNAL_KINDS
    assert "ehlers_continuation_short_signal" in SIGNAL_KINDS
    assert out["ehlers_continuation_short_state"].tolist() == [0, 1, 1, 0, 0, 0, 0]
    assert out["ehlers_continuation_short_entry"].tolist() == [0, 1, 0, 0, 0, 0, 0]
    assert out["ehlers_continuation_signal"].tolist() == [0, -1, -1, 0, 0, 0, 0]
    assert set(out["ehlers_continuation_signal"].unique()).issubset({-1, 0})
    assert out["ehlers_continuation_signal"].max() <= 0


def test_ehlers_continuation_short_is_available_from_runtime_registry() -> None:
    from src.experiments.registry import DEPRECATED_SIGNAL_ALIASES, SIGNAL_REGISTRY, get_signal_fn

    assert "ehlers_continuation_short" in SIGNAL_REGISTRY
    assert "ehlers_continuation_short_signal" not in SIGNAL_REGISTRY
    assert "ehlers_continuation_short_signal" in DEPRECATED_SIGNAL_ALIASES
    assert get_signal_fn("ehlers_continuation_short_signal") is SIGNAL_REGISTRY["ehlers_continuation_short"]


def test_ehlers_continuation_transition_mode_uses_short_entry() -> None:
    out, meta = build_ehlers_continuation_short_signal(_signal_frame(), {"entry_mode": "transition"})

    assert meta["entry_mode"] == "transition"
    assert out["ehlers_continuation_signal"].tolist() == [0, -1, 0, 0, 0, 0, 0]


def test_ehlers_continuation_entry_delay_shifts_selected_short_signal() -> None:
    out, meta = build_ehlers_continuation_short_signal(_signal_frame(), {"entry_delay_bars": 1})

    assert meta["entry_delay_bars"] == 1
    assert out["ehlers_continuation_short_state"].tolist() == [0, 1, 1, 0, 0, 0, 0]
    assert out["ehlers_continuation_signal"].tolist() == [0, 0, -1, -1, 0, 0, 0]


def test_ehlers_continuation_signal_handles_rolling_window_nans_without_crashing() -> None:
    frame = _signal_frame()
    frame.loc[frame.index[:3], ["ema_50", "mama", "roofing_filter_48_10", "decycler_oscillator_30_60"]] = np.nan

    out, _ = build_ehlers_continuation_short_signal(frame)

    assert len(out) == len(frame)
    assert out["ehlers_continuation_signal"].iloc[:3].eq(0).all()
    assert set(out["ehlers_continuation_signal"].unique()).issubset({-1, 0})


def test_ehlers_continuation_short_diagnostics_return_expected_keys() -> None:
    signaled, _ = build_ehlers_continuation_short_signal(_signal_frame())
    trades = pd.DataFrame(
        {
            "side": ["short"],
            "entry_timestamp": [signaled.index[1]],
            "gross_return": [0.03],
            "net_return": [0.02],
            "cost_paid": [0.01],
            "trade_r": [1.2],
        }
    )
    performance = SimpleNamespace(
        trades=trades,
        positions=pd.Series([0.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0], index=signaled.index),
        turnover=pd.Series([0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0], index=signaled.index),
        gross_returns=pd.Series([0.0, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0], index=signaled.index),
        returns=pd.Series([0.0, 0.02, 0.0, 0.0, 0.0, 0.0, 0.0], index=signaled.index),
        costs=pd.Series([0.0, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0], index=signaled.index),
        summary={
            "sharpe": 1.4,
            "max_drawdown": -0.01,
            "profit_factor": 2.0,
            "hit_rate": 1.0,
            "cost_to_gross_pnl": 1.0 / 3.0,
        },
    )

    diagnostics = compute_ehlers_continuation_short_diagnostics(
        signaled,
        performance=performance,
        robustness={
            "cost_stress": {"cost_x2": {"net_pnl": 0.01}},
            "entry_delay": {"delay_1_bars": {"net_pnl": 0.015}},
            "walk_forward": {"fold_count": 1},
        },
    )

    expected_signal_count_keys = {
        "total_rows",
        "ema50_lt_ema100_rows",
        "mama_lt_fama_rows",
        "roofing_lt_zero_rows",
        "roofing_slope_lt_zero_rows",
        "roofing_lt_slope_rows",
        "decycler_osc_lt_zero_rows",
        "final_short_state_rows",
        "final_short_entry_rows",
        "actual_trade_count",
    }
    expected_position_performance_keys = {
        "mean_position",
        "mean_absolute_position",
        "max_position",
        "non_zero_position_count",
        "total_turnover",
        "gross_pnl",
        "net_pnl",
        "total_cost",
        "cost_to_gross_pnl",
        "profit_factor",
        "hit_rate",
        "sharpe",
        "max_drawdown",
        "average_r",
        "median_r",
    }
    assert expected_signal_count_keys.issubset(diagnostics["signal_counts"])
    assert expected_position_performance_keys.issubset(diagnostics["position_performance_diagnostics"])
    assert diagnostics["signal_counts"]["total_rows"] == len(signaled)
    assert diagnostics["signal_counts"]["final_short_state_rows"] == 2
    assert diagnostics["signal_counts"]["final_short_entry_rows"] == 1
    assert diagnostics["signal_counts"]["actual_trade_count"] == 1
    assert diagnostics["overlap_diagnostics"] == {
        "ema_only_rows": 5,
        "ema_mama_rows": 5,
        "ema_mama_roofing_rows": 3,
        "full_signal_rows": 2,
    }
    assert diagnostics["position_diagnostics"]["total_turnover"] == 2.0
    assert diagnostics["performance_diagnostics"]["average_r"] == 1.2
    assert "2024" in diagnostics["performance_by_year"]
    assert set(diagnostics["robustness_diagnostics"]) == {"cost_stress", "entry_delay", "walk_forward"}


@pytest.mark.parametrize("path", ABLATION_CONFIGS)
def test_ehlers_continuation_short_ablation_configs_load(path: Path) -> None:
    cfg = load_experiment_config(_require_config_fixture(path))

    assert cfg["signals"]["kind"] == "ehlers_continuation_short"
    assert cfg["signals"]["params"]["short_only"] is True
    assert cfg["backtest"]["allow_short"] is True
    assert cfg["backtest"]["short_only"] is True
    assert cfg["diagnostics"]["robustness"]["enabled"] is True


def test_ehlers_continuation_short_ablation_config_params_match_intent() -> None:
    for path in ABLATION_CONFIGS:
        _require_config_fixture(path)

    assert load_experiment_config(ABLATION_CONFIGS[0])["signals"]["params"]["use_mama_fama"] is False
    assert load_experiment_config(ABLATION_CONFIGS[1])["signals"]["params"]["use_decycler"] is False
    assert load_experiment_config(ABLATION_CONFIGS[2])["signals"]["params"]["use_ema_regime"] is False
    assert load_experiment_config(ABLATION_CONFIGS[3])["signals"]["params"]["use_roofing_lt_slope"] is False
    assert load_experiment_config(ABLATION_CONFIGS[4])["signals"]["params"]["entry_delay_bars"] == 1
    assert load_experiment_config(ABLATION_CONFIGS[5])["signals"]["params"]["entry_delay_bars"] == 2


def test_ehlers_continuation_short_robustness_configs_load_if_supported() -> None:
    for path in [CONFIG_PATH, ABLATION_CONFIGS[4], ABLATION_CONFIGS[5]]:
        cfg = load_experiment_config(_require_config_fixture(path))
        robustness = cfg["diagnostics"]["robustness"]

        assert robustness["enabled"] is True
        assert robustness["cost_multipliers"] == [2.0, 3.0, 5.0]
        assert robustness["entry_delay_bars"] == [1, 2]
        assert robustness["walk_forward_frequency"] == "YE"
