from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.features.opening_range_breakout import add_opening_range_breakout_features
from src.signals.meta_probability_side_signal import meta_probability_side_signal
from src.targets.triple_barrier import build_triple_barrier_target
from src.utils.config import load_experiment_config
from src.utils.config_validation import ConfigValidationError, validate_data_block


def test_triple_barrier_meta_target_uses_orb_candidate_and_side() -> None:
    idx = pd.date_range("2024-01-01 00:00:00", periods=8, freq="30min", tz="UTC")
    close = pd.Series([100.0, 100.1, 100.2, 100.4, 103.0, 103.2, 103.4, 103.5], index=idx)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "close_logret": np.log(close / close.shift(1)),
            "orb_candidate": 0.0,
            "orb_side": 0.0,
        },
        index=idx,
    )
    df.loc[idx[2], "orb_candidate"] = 1.0
    df.loc[idx[2], "orb_side"] = 1.0
    df.loc[idx[3], "high"] = 110.0

    out, label_col, _, meta = build_triple_barrier_target(
        df,
        {
            "kind": "triple_barrier",
            "label_mode": "meta",
            "candidate_col": "orb_candidate",
            "side_col": "orb_side",
            "candidate_out_col": "label_candidate",
            "label_col": "label",
            "entry_price_mode": "next_open",
            "price_col": "close",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "returns_col": "close_logret",
            "upper_mult": 2.0,
            "lower_mult": 1.0,
            "max_holding": 2,
            "vol_window": 2,
            "min_vol": 0.0001,
            "neutral_label": "lower",
            "tie_break": "lower",
        },
    )

    assert label_col == "label"
    assert meta["candidate_input_col"] == "orb_candidate"
    assert meta["side_col"] == "orb_side"
    assert out["label_candidate"].sum() == pytest.approx(1.0)
    assert out.loc[idx[2], "label_meta_side"] == pytest.approx(1.0)
    assert pd.notna(out.loc[idx[2], "label"])


def test_meta_probability_side_signal_uses_orb_side_and_never_flips() -> None:
    df = pd.DataFrame(
        {
            "pred_prob": [0.90, 0.90, 0.40, 0.90],
            "orb_side": [1.0, -1.0, -1.0, 0.0],
            "label_candidate": [1.0, 1.0, 1.0, 1.0],
        }
    )

    signal = meta_probability_side_signal(
        df,
        prob_col="pred_prob",
        candidate_col="label_candidate",
        side_col="orb_side",
        signal_col="signal_orb_side",
        threshold=0.52,
    )

    assert signal.tolist() == [1.0, -1.0, 0.0, 0.0]


def test_orb_candidate_rows_have_no_missing_model_features() -> None:
    idx = pd.DatetimeIndex(
        pd.to_datetime(
            [
                "2024-06-03 06:30:00",
                "2024-06-03 07:00:00",
                "2024-06-03 07:30:00",
                "2024-06-03 08:00:00",
                "2024-06-03 08:30:00",
            ],
            utc=True,
        )
    )
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 102.0, 102.2],
            "high": [100.5, 101.0, 100.5, 102.5, 102.4],
            "low": [99.5, 99.0, 99.5, 101.8, 101.9],
            "close": [100.0, 100.0, 100.0, 102.0, 102.2],
            "volume": 100.0,
            "atr_24": 2.0,
            "vol_rolling_24": 0.01,
        },
        index=idx,
    )

    out = add_opening_range_breakout_features(
        df,
        sessions=[
            {
                "name": "london",
                "timezone": "Europe/London",
                "session_open_time": "08:00",
                "opening_range_bars": 2,
                "trade_until_time": "12:00",
            }
        ],
        enabled_sessions=["london"],
        asset="GER40",
        min_range_atr=0.1,
        max_range_atr=5.0,
        breakout_buffer_atr=0.0,
        post_breakout_active_bars=2,
    )
    feature_cols = [
        "orb_side",
        "orb_range_width",
        "orb_range_width_atr",
        "bars_since_orb_breakout",
        "orb_close_position_in_range",
        "orb_breakout_strength_atr",
        "orb_breakout_strength_range",
        "orb_pre_breakout_volatility",
        "orb_failed_breakout_recent",
    ]
    candidates = out["orb_candidate"].eq(1.0)

    assert bool(candidates.any())
    assert out.loc[candidates, feature_cols].notna().all().all()


def test_new_orb_experiment_config_validates_and_keeps_shock_config_valid() -> None:
    cfg = load_experiment_config(
        "config/experiments/ftmo_30m_xau_indices_london_newyork_opening_range_breakout_xgboost_meta_v1.yaml"
    )
    shock_cfg = load_experiment_config("config/experiments/btcusd_1h_shock_meta_xgboost.yaml")

    assert cfg["features"][14]["step"] == "multi_timeframe"
    assert cfg["features"][14]["params"]["timestamp_convention"] == "bar_start"
    assert cfg["features"][15]["step"] == "opening_range_breakout"
    assert shock_cfg["model"]["target"]["kind"] == "triple_barrier"


def test_dukascopy_load_paths_can_allow_missing_symbols_explicitly() -> None:
    data = {
        "source": "dukascopy_csv",
        "interval": "30m",
        "symbols": ["XAUUSD", "US100"],
        "storage": {
            "load_paths": {"XAUUSD": "data/raw/xauusd_30m.csv"},
            "allow_missing_load_paths": True,
        },
    }
    validate_data_block(data)

    data["storage"]["allow_missing_load_paths"] = False
    with pytest.raises(ConfigValidationError):
        validate_data_block(data)


def test_orb_optuna_tunes_threshold_without_independent_upper_alias() -> None:
    cfg = yaml.safe_load(
        Path(
            "config/optuna/optuna_ftmo_30m_xau_indices_london_newyork_opening_range_breakout_xgboost_meta_v1.yaml"
        ).read_text()
    )
    search_paths = {entry["path"] for entry in cfg["search_space"]}
    search_names = {entry["name"] for entry in cfg["search_space"]}

    assert "signals.params.threshold" in search_paths
    assert "signals.params.upper" not in search_paths
    assert "meta_signal_upper_alias" not in search_names
