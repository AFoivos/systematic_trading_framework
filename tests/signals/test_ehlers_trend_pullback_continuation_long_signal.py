from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.experiments.optuna_search import load_optuna_spec_yaml, run_optuna_spec
from src.signals.ehlers_trend_pullback_continuation_long_signal import (
    build_ehlers_trend_pullback_continuation_long_signal,
)
from src.signals.registry import SIGNAL_KINDS


CONFIG_DIR = Path("config/experiments/ehlers_trend_pullback_continuation_long")
OPTUNA_DIR = Path("config/optuna/ehlers_trend_pullback_continuation_long")


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=6, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
            "ema_50": [99.0, 101.0, 102.0, 99.0, 104.0, 105.0],
            "ema_100": [100.0] * 6,
            "mama": [0.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "fama": [1.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            "decycler_oscillator_30_60": [0.1] * 6,
            "rolling_r2_96": [0.4] * 6,
            "atr_over_price_z_252": [0.0, 0.2, 0.4, 0.0, 2.0, 0.0],
            "close_minus_vwap_20_over_atr_14": [0.5] * 6,
            "close_minus_supersmoother_10_over_atr_14": [1.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            "roofing_filter_48_10": [0.1, 0.2, 0.3, 0.4, 0.5, -0.1],
            "roofing_filter_48_10_slope": [0.1] * 6,
            "stoch_rsi_k": [0.2, 0.6, 0.7, 0.8, 0.8, 0.8],
            "stoch_rsi_d": [0.3, 0.5, 0.6, 0.7, 0.7, 0.7],
        },
        index=idx,
    )


def test_basic_state_mode_outputs_long_only_columns() -> None:
    out, meta = build_ehlers_trend_pullback_continuation_long_signal(_frame())

    assert meta["kind"] == "ehlers_trend_pullback_continuation_long"
    assert "ehlers_trend_pullback_continuation_long" in SIGNAL_KINDS
    assert out["ehlers_trend_pullback_long_state"].tolist() == [0, 1, 1, 0, 0, 0]
    assert out["ehlers_trend_pullback_long_entry"].tolist() == [0, 1, 0, 0, 0, 0]
    assert out["signal_side"].tolist() == [0, 1, 1, 0, 0, 0]
    assert out["signal_candidate"].tolist() == [0, 1, 1, 0, 0, 0]
    assert out["signal_side"].min() >= 0
    for col in (
        "ehlers_tp_cond_ema_regime",
        "ehlers_tp_cond_mama_fama",
        "ehlers_tp_cond_decycler",
        "ehlers_tp_cond_rolling_r2",
        "ehlers_tp_cond_volatility",
        "ehlers_tp_cond_pullback",
        "ehlers_tp_cond_roofing",
        "ehlers_tp_cond_stoch_rsi",
        "ehlers_tp_cond_cycle",
        "ehlers_tp_cond_avoid",
        "ehlers_tp_score",
    ):
        assert col in out.columns


def test_transition_mode_uses_state_turn_on() -> None:
    out, meta = build_ehlers_trend_pullback_continuation_long_signal(
        _frame(),
        {"entry_mode": "transition"},
    )

    assert meta["entry_mode"] == "transition"
    assert out["signal_side"].tolist() == [0, 1, 0, 0, 0, 0]
    assert out["signal_candidate"].tolist() == [0, 1, 0, 0, 0, 0]


def test_entry_delay_shifts_final_signal_but_not_raw_candidate() -> None:
    out, meta = build_ehlers_trend_pullback_continuation_long_signal(
        _frame(),
        {"entry_delay_bars": 1},
    )

    assert meta["entry_delay_bars"] == 1
    assert out["signal_side"].tolist() == [0, 0, 1, 1, 0, 0]
    assert out["signal_candidate"].tolist() == [0, 1, 1, 0, 0, 0]


def test_missing_required_columns_raise_clear_key_error() -> None:
    frame = _frame().drop(columns=["rolling_r2_96"])

    with pytest.raises(KeyError, match="rolling_r2_96"):
        build_ehlers_trend_pullback_continuation_long_signal(frame)


def test_optional_filters_disabled_do_not_require_optional_columns() -> None:
    out, _ = build_ehlers_trend_pullback_continuation_long_signal(
        _frame(),
        {
            "require_trend_slope_positive": False,
            "require_acp_power": False,
            "require_hilbert_amplitude": False,
            "require_hilbert_cycle_ok": False,
            "avoid_near_resistance": False,
            "avoid_shock_active": True,
            "require_session_allowed": False,
        },
    )

    assert "signal_side" in out.columns


def test_pullback_mode_validation() -> None:
    with pytest.raises(ValueError, match="pullback_mode"):
        build_ehlers_trend_pullback_continuation_long_signal(_frame(), {"pullback_mode": "bad"})


def test_long_only_must_be_true() -> None:
    with pytest.raises(ValueError, match="long_only"):
        build_ehlers_trend_pullback_continuation_long_signal(_frame(), {"long_only": False})


def test_signal_uses_current_and_past_only_for_laguerre_rising() -> None:
    base = _frame()
    base["laguerre_rsi"] = [0.1, 0.3, 0.4, 0.5, 0.4, 0.6]
    changed_future = base.copy()
    changed_future.loc[changed_future.index[5], "laguerre_rsi"] = 0.0

    params = {"require_laguerre_rising": True}
    out_base, _ = build_ehlers_trend_pullback_continuation_long_signal(base, params)
    out_changed, _ = build_ehlers_trend_pullback_continuation_long_signal(changed_future, params)

    pd.testing.assert_series_equal(out_base["signal_side"].iloc[:5], out_changed["signal_side"].iloc[:5])


@pytest.mark.parametrize(
    ("path", "expected_optuna_references"),
    [
        (
            CONFIG_DIR / "us100_30m_ehlers_trend_pullback_continuation_long_v1.yaml",
            1,
        ),
        (
            CONFIG_DIR / "all6_30m_ehlers_trend_pullback_continuation_long_v1.yaml",
            0,
        ),
        (
            CONFIG_DIR / "us100_30m_ehlers_trend_pullback_continuation_target_lab_v1.yaml",
            1,
        ),
    ],
)
def test_retired_ehlers_trend_pullback_configs_are_not_referenced_by_active_specs(
    path: Path,
    expected_optuna_references: int,
) -> None:
    assert not path.is_file()

    specs = [
        load_optuna_spec_yaml(spec_path)
        for spec_path in sorted(OPTUNA_DIR.glob("*.yaml"))
    ]
    references = [
        spec
        for spec in specs
        if Path(spec["base_config"]).as_posix() == path.as_posix()
    ]

    assert len(references) == expected_optuna_references
    assert all(spec["archived"] is True for spec in references)


@pytest.mark.parametrize(
    "path",
    [
        OPTUNA_DIR / "optuna_us100_30m_ehlers_trend_pullback_continuation_long_v1.yaml",
        OPTUNA_DIR / "optuna_us100_30m_ehlers_trend_pullback_continuation_target_lab_v1.yaml",
    ],
)
def test_ehlers_trend_pullback_optuna_specs_are_archived_and_fail_closed(path: Path) -> None:
    spec = load_optuna_spec_yaml(path)

    assert spec["archived"] is True
    assert spec["archive_reason"]
    assert spec["search_space"]
    assert not Path(spec["base_config"]).is_file()
    with pytest.raises(ValueError, match="archived and cannot be run"):
        run_optuna_spec(path, no_report=True)
