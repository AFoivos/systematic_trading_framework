from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.risk.position_sizing import scale_signal_for_ftmo
from src.signals.meta_probability_side_signal import meta_probability_side_signal
from src.targets import build_triple_barrier_target
from src.utils.config import load_experiment_config


def test_triple_barrier_binary_asymmetric_neutral_and_tie_break_lower() -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="h")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.5, 100.0, 100.0, 100.0, 100.0],
            "high": [100.2, 102.5, 100.5, 102.5, 100.5, 100.5, 100.5, 100.5],
            "low": [99.8, 99.5, 98.5, 98.5, 99.5, 99.5, 99.5, 99.5],
            "close": [100.0] * 8,
            "vol": [0.01] * 8,
        },
        index=idx,
    )

    out, label_col, _, meta = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "volatility_col": "vol",
            "max_holding": 2,
            "upper_mult": 2.0,
            "lower_mult": 1.0,
            "neutral_label": "lower",
            "tie_break": "lower",
            "label_mode": "binary",
        },
    )

    assert out.iloc[0][label_col] == pytest.approx(1.0)
    assert out.iloc[1][label_col] == pytest.approx(0.0)
    assert out.iloc[2][label_col] == pytest.approx(0.0)
    assert out.iloc[4][label_col] == pytest.approx(0.0)
    assert out[label_col].tail(2).isna().all()
    assert meta["upper_barrier_count"] == 1
    assert meta["lower_barrier_count"] == 2
    assert meta["neutral_count"] >= 1

    dropped, dropped_label_col, _, _ = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "volatility_col": "vol",
            "max_holding": 2,
            "upper_mult": 2.0,
            "lower_mult": 1.0,
            "neutral_label": "drop",
            "tie_break": "lower",
        },
    )
    assert pd.isna(dropped.iloc[4][dropped_label_col])


def test_triple_barrier_next_open_entry_uses_next_open_and_keeps_tail_nan() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="h")
    df = pd.DataFrame(
        {
            "open": [100.0, 110.0, 110.0],
            "high": [101.0, 111.0, 111.0],
            "low": [99.0, 109.0, 109.0],
            "close": [100.0, 110.0, 110.0],
            "vol": [0.01, 0.01, 0.01],
        },
        index=idx,
    )

    current, current_label_col, _, _ = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "volatility_col": "vol",
            "max_holding": 1,
            "upper_mult": 2.0,
            "lower_mult": 1.0,
            "neutral_label": "drop",
            "entry_price_mode": "current_close",
        },
    )
    next_open, next_label_col, _, meta = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "volatility_col": "vol",
            "max_holding": 1,
            "upper_mult": 2.0,
            "lower_mult": 1.0,
            "neutral_label": "drop",
            "entry_price_mode": "next_open",
        },
    )

    assert current.iloc[0][current_label_col] == pytest.approx(1.0)
    assert pd.isna(next_open.iloc[0][next_label_col])
    assert next_open[next_label_col].tail(1).isna().all()
    assert meta["entry_price_mode"] == "next_open"


def test_triple_barrier_meta_labeling_candidates_and_r_multiple() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="h")
    df = pd.DataFrame(
        {
            "open": [100.0] * 5,
            "high": [100.5, 102.0, 100.5, 102.0, 100.5],
            "low": [99.5, 99.5, 98.0, 99.5, 99.5],
            "close": [100.0] * 5,
            "vol": [0.01] * 5,
            "primary_side": [1.0, -1.0, 1.0, 0.0, 0.0],
            "trade_candidate": [1.0, 1.0, 0.0, 0.0, 0.0],
        },
        index=idx,
    )

    out, label_col, _, meta = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "volatility_col": "vol",
            "max_holding": 1,
            "upper_mult": 1.0,
            "lower_mult": 1.0,
            "neutral_label": "lower",
            "label_mode": "meta",
            "side_col": "primary_side",
            "candidate_col": "trade_candidate",
            "candidate_out_col": "label_candidate",
            "add_r_multiple": True,
            "r_clip": [-1.0, 3.0],
        },
    )

    assert meta["meta_labeling"] is True
    assert meta["candidate_rows"] == 2
    assert out.iloc[0][label_col] == pytest.approx(1.0)
    assert out.iloc[1][label_col] == pytest.approx(1.0)
    assert pd.isna(out.iloc[2][label_col])
    assert out.iloc[0]["label_oriented_ret"] == pytest.approx(0.01)
    assert out.iloc[1]["label_oriented_ret"] == pytest.approx(0.01)
    assert out.iloc[0]["tb_oriented_r"] == pytest.approx(1.0)
    assert out.iloc[1]["tb_oriented_r"] == pytest.approx(1.0)


def test_triple_barrier_meta_neutral_lower_is_failure_not_oriented_return_success() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0],
            "high": [100.0, 100.4, 100.4, 100.4],
            "low": [100.0, 99.8, 99.8, 99.8],
            "close": [100.0, 100.3, 100.3, 100.3],
            "vol": [0.01] * 4,
            "primary_side": [1.0, 0.0, 0.0, 0.0],
            "trade_candidate": [1.0, 0.0, 0.0, 0.0],
        },
        index=idx,
    )

    out, label_col, _, _ = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "volatility_col": "vol",
            "max_holding": 2,
            "upper_mult": 2.0,
            "lower_mult": 1.0,
            "neutral_label": "lower",
            "label_mode": "meta",
            "side_col": "primary_side",
            "candidate_col": "trade_candidate",
        },
    )

    assert out.iloc[0][f"{label_col}_hit_type"] == "neutral"
    assert out.iloc[0][f"{label_col}_oriented_ret"] > 0.0
    assert out.iloc[0][label_col] == pytest.approx(0.0)


def test_triple_barrier_meta_short_asymmetric_profit_stop_r_multiple() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="h")
    df = pd.DataFrame(
        {
            "open": [100.0] * 5,
            "high": [100.0, 100.4, 101.2, 100.0, 100.0],
            "low": [100.0, 98.0, 99.4, 100.0, 100.0],
            "close": [100.0] * 5,
            "vol": [0.01] * 5,
            "primary_side": [-1.0, -1.0, 0.0, 0.0, 0.0],
            "trade_candidate": [1.0, 1.0, 0.0, 0.0, 0.0],
        },
        index=idx,
    )

    out, label_col, _, _ = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "volatility_col": "vol",
            "max_holding": 1,
            "upper_mult": 2.0,
            "lower_mult": 1.0,
            "neutral_label": "lower",
            "label_mode": "meta",
            "side_col": "primary_side",
            "candidate_col": "trade_candidate",
            "add_r_multiple": True,
        },
    )

    assert out.iloc[0][f"{label_col}_hit_type"] == "profit"
    assert out.iloc[0][label_col] == pytest.approx(1.0)
    assert out.iloc[0]["tb_oriented_r"] == pytest.approx(2.0)
    assert out.iloc[1][f"{label_col}_hit_type"] == "stop"
    assert out.iloc[1][label_col] == pytest.approx(0.0)
    assert out.iloc[1]["tb_oriented_r"] == pytest.approx(-1.0)


def test_meta_probability_side_signal_never_flips_low_probability_shorts() -> None:
    idx = pd.RangeIndex(4)
    df = pd.DataFrame(
        {
            "pred_prob": [0.80, 0.80, 0.40, 0.90],
            "primary_side": [1.0, -1.0, -1.0, -1.0],
            "label_candidate": [1.0, 1.0, 1.0, 0.0],
        },
        index=idx,
    )

    signal = meta_probability_side_signal(
        df,
        prob_col="pred_prob",
        side_col="primary_side",
        candidate_col="label_candidate",
        signal_col="signal_meta_side",
        threshold=0.60,
    )

    assert signal.iloc[0] == pytest.approx(1.0)
    assert signal.iloc[1] == pytest.approx(-1.0)
    assert signal.iloc[2] == pytest.approx(0.0)
    assert signal.iloc[3] == pytest.approx(0.0)


def test_ftmo_risk_sizing_threshold_clip_confidence_and_small_vol() -> None:
    idx = pd.RangeIndex(4)
    signal = pd.Series([0.01, 0.5, -0.5, 1.0], index=idx, name="signal")
    vol = pd.Series([0.0, 0.001, 0.002, 0.000001], index=idx, name="pred_vol")
    confidence = pd.Series([0.9, 0.7, 0.3, 0.5], index=idx, name="pred_prob")

    exposure = scale_signal_for_ftmo(
        signal,
        vol,
        risk_per_trade=0.002,
        stop_mult=1.0,
        max_leverage=1.0,
        min_abs_signal=0.05,
        confidence=confidence,
        confidence_floor=0.60,
        confidence_power=1.0,
    )

    assert exposure.iloc[0] == pytest.approx(0.0)
    assert exposure.iloc[1] == pytest.approx(0.125)
    assert exposure.iloc[2] == pytest.approx(-0.125)
    assert exposure.iloc[3] == pytest.approx(0.0)
    assert np.isfinite(exposure.to_numpy(dtype=float)).all()


def test_ftmo_risk_sizing_meta_success_confidence_does_not_invert_shorts() -> None:
    idx = pd.RangeIndex(2)
    signal = pd.Series([-1.0, -1.0], index=idx, name="signal")
    vol = pd.Series([0.001, 0.001], index=idx, name="pred_vol")
    confidence = pd.Series([0.8, 0.4], index=idx, name="pred_prob")

    exposure = scale_signal_for_ftmo(
        signal,
        vol,
        risk_per_trade=0.002,
        max_leverage=1.0,
        confidence=confidence,
        confidence_floor=0.60,
        confidence_mode="meta_success",
    )

    assert exposure.iloc[0] == pytest.approx(-0.5)
    assert exposure.iloc[1] == pytest.approx(0.0)


def test_new_ftmo_triple_barrier_configs_load_and_preserve_target_kind() -> None:
    meta_cfg = load_experiment_config(
        "experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1.yaml"
    )
    conservative_cfg = load_experiment_config(
        "experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_conservative_v1.yaml"
    )

    assert meta_cfg["model"]["target"]["kind"] == "triple_barrier"
    assert meta_cfg["model"]["target"]["label_mode"] == "meta"
    assert meta_cfg["signals"]["kind"] == "meta_probability_side"
    assert meta_cfg["backtest"]["signal_col"] == "signal_meta_side"
    assert meta_cfg["risk"]["sizing"]["confidence_mode"] == "meta_success"
    assert meta_cfg["model"]["feature_selectors"]["exact"] == ["primary_side"]
    assert meta_cfg["model"]["feature_selectors"]["include"] == [
        {"exact": "shock_strength"},
        {"exact": "shock_distance_ema"},
        {"startswith": "shock_ret_z_"},
        {"startswith": "shock_atr_multiple_"},
    ]
    assert meta_cfg["model"]["feature_selectors"]["exclude"] == [
        {"exact": "trade_candidate"},
        {"exact": "shock_candidate"},
        {"exact": "shock_up_candidate"},
        {"exact": "shock_down_candidate"},
        {"exact": "shock_side_contrarian"},
        {"exact": "shock_side_contrarian_active"},
        {"startswith": "label_"},
        {"startswith": "pred_"},
        {"startswith": "tb_"},
    ]
    assert conservative_cfg["model"]["target"]["kind"] == "triple_barrier"
    assert conservative_cfg["model"]["target"]["label_mode"] == "binary"
    assert meta_cfg["risk"]["sizing"]["kind"] == "ftmo_risk_per_trade"
