from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.experiments.orchestration.feature_stage import apply_signal_step
from src.experiments.registry import SIGNAL_REGISTRY
from src.signals.vwap_rms_ema_cross_long_fractal_filter import (
    build_vwap_rms_ema_cross_long_fractal_filter_signal,
    vwap_rms_ema_cross_long_fractal_filter_signal,
)
from src.utils.config import load_experiment_config


def _require_config_fixture(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.exists():
        pytest.skip(f"optional config fixture not present: {resolved}")
    return resolved


EXPECTED_COLUMNS = {
    "ema_50_above_ema_96",
    "vwap_40_rms_cross_above_ema_50_rms",
    "ppo_hist_12_36_9",
    "ppo_hist_12_36_9_positive",
    "ppo_12_36_above_ppo_signal_9",
    "fractal_dimension_128_trend_ok",
    "vwap_40_rms_ema_50_cross_long_fractal_setup",
    "signal_side",
    "signal_candidate",
}

FLAG_COLUMNS = EXPECTED_COLUMNS - {"ppo_hist_12_36_9"}


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=10, freq="30min", tz="UTC")
    return pd.DataFrame(
        {
            "ema_50": [101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 99.0, 101.0, 101.0],
            "ema_96": [100.0] * 10,
            "ema_50__root_mean_square": [100.0] * 10,
            "vwap_40__root_mean_square": [99.0, 100.5, 99.0, 100.5, 99.0, 100.5, 99.0, 100.5, 99.0, 100.5],
            "ppo_12_36": [0.0010, 0.0010, 0.0010, 0.0010, 0.0010, 0.0001, 0.0010, 0.0010, 0.0010, 0.0010],
            "ppo_signal_9": [0.0] * 10,
            "fractal_dimension_128": [1.30, 1.30, 1.30, 1.45, 1.30, 1.30, 1.30, 1.30, 1.30, 1.30],
        },
        index=idx,
    )


def test_vwap_rms_ema_cross_long_fractal_filter_emits_expected_columns_and_registry() -> None:
    out, meta = build_vwap_rms_ema_cross_long_fractal_filter_signal(_frame())

    assert meta["kind"] == "vwap_rms_ema_cross_long_fractal_filter"
    assert EXPECTED_COLUMNS.issubset(out.columns)
    assert (
        SIGNAL_REGISTRY["vwap_rms_ema_cross_long_fractal_filter"]
        is vwap_rms_ema_cross_long_fractal_filter_signal
    )
    for column in FLAG_COLUMNS:
        assert str(out[column].dtype) == "int8"
    assert out["signal_side"].tolist() == [0, 1, 0, 0, 0, 0, 0, 0, 0, 1]
    assert out["signal_candidate"].sum() == 2

    stepped = apply_signal_step(_frame(), {"kind": "vwap_rms_ema_cross_long_fractal_filter"})
    assert stepped["signal_candidate"].sum() == 2


def test_vwap_rms_ema_cross_long_fractal_filter_does_not_mutate_input() -> None:
    frame = _frame()
    original = frame.copy(deep=True)

    out, _ = build_vwap_rms_ema_cross_long_fractal_filter_signal(frame)

    assert out is not frame
    pd.testing.assert_frame_equal(frame, original)


def test_vwap_rms_ema_cross_long_fractal_filter_requires_fractal_column() -> None:
    with pytest.raises(KeyError, match="fractal_dimension_128"):
        build_vwap_rms_ema_cross_long_fractal_filter_signal(
            _frame().drop(columns=["fractal_dimension_128"])
        )


def test_vwap_rms_ema_cross_long_fractal_filter_blocks_high_fractal_dimension() -> None:
    frame = _frame()
    out, _ = build_vwap_rms_ema_cross_long_fractal_filter_signal(frame)
    blocked_idx = frame.index[3]

    assert out.loc[blocked_idx, "ema_50_above_ema_96"] == 1
    assert out.loc[blocked_idx, "vwap_40_rms_cross_above_ema_50_rms"] == 1
    assert out.loc[blocked_idx, "ppo_hist_12_36_9"] > 0.0002
    assert out.loc[blocked_idx, "fractal_dimension_128_trend_ok"] == 0
    assert out.loc[blocked_idx, "vwap_40_rms_ema_50_cross_long_fractal_setup"] == 0
    assert out.loc[blocked_idx, "signal_side"] == 0
    assert out.loc[blocked_idx, "signal_candidate"] == 0


def test_vwap_rms_ema_cross_long_fractal_filter_signals_only_when_all_conditions_are_true() -> None:
    out, _ = build_vwap_rms_ema_cross_long_fractal_filter_signal(_frame())
    all_conditions = (
        out["ema_50_above_ema_96"].eq(1)
        & out["vwap_40_rms_cross_above_ema_50_rms"].eq(1)
        & out["ppo_hist_12_36_9"].gt(0.0002)
        & out["ppo_hist_12_36_9_positive"].eq(1)
        & out["ppo_12_36_above_ppo_signal_9"].eq(1)
        & out["fractal_dimension_128_trend_ok"].eq(1)
    ).astype("int8")

    pd.testing.assert_series_equal(
        out["vwap_40_rms_ema_50_cross_long_fractal_setup"],
        all_conditions,
        check_names=False,
    )
    pd.testing.assert_series_equal(out["signal_side"], all_conditions, check_names=False)


def test_vwap_rms_ema_cross_long_fractal_filter_cross_logic_does_not_look_ahead() -> None:
    idx = pd.date_range("2024-02-01", periods=3, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "ema_50": [101.0, 101.0, 101.0],
            "ema_96": [100.0, 100.0, 100.0],
            "ema_50__root_mean_square": [100.0, 100.0, 100.0],
            "vwap_40__root_mean_square": [99.0, 99.5, 100.5],
            "ppo_12_36": [0.001, 0.001, 0.001],
            "ppo_signal_9": [0.0, 0.0, 0.0],
            "fractal_dimension_128": [1.30, 1.30, 1.30],
        },
        index=idx,
    )

    baseline, _ = build_vwap_rms_ema_cross_long_fractal_filter_signal(frame)

    assert baseline.loc[idx[1], "vwap_40_rms_cross_above_ema_50_rms"] == 0
    assert baseline.loc[idx[1], "signal_side"] == 0
    assert baseline.loc[idx[2], "vwap_40_rms_cross_above_ema_50_rms"] == 1
    assert baseline.loc[idx[2], "signal_side"] == 1

    mutated = frame.copy()
    mutated.loc[idx[2], "vwap_40__root_mean_square"] = 80.0
    changed, _ = build_vwap_rms_ema_cross_long_fractal_filter_signal(mutated)

    pd.testing.assert_frame_equal(
        baseline.loc[: idx[1], sorted(EXPECTED_COLUMNS)],
        changed.loc[: idx[1], sorted(EXPECTED_COLUMNS)],
    )


def test_us100_vwap_rms_fractal_filter_config_loads() -> None:
    cfg = load_experiment_config(
        _require_config_fixture("config/experiments/us100_30m_vwap_rms_cross_fractal_filter.yaml")
    )

    assert cfg["signals"]["kind"] == "vwap_rms_ema_cross_long_fractal_filter"
    assert cfg["signals"]["params"]["fractal_col"] == "fractal_dimension_128"
    assert cfg["signals"]["params"]["fractal_max"] == 1.45
    assert any(step["step"] == "fractal_dimension" for step in cfg["features"])
    assert "fractal_dimension_128" in cfg["target"]["diagnostic_feature_cols"]
    assert "fractal_dimension_128_trend_ok" in cfg["target"]["diagnostic_feature_cols"]
    assert "vwap_40_rms_ema_50_cross_long_fractal_setup" in cfg["target"]["diagnostic_feature_cols"]
    assert cfg["logging"]["run_name"] == "us100_30m_vwap_rms_cross_fractal_filter"
