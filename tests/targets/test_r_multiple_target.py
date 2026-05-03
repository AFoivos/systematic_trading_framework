from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.targets.r_multiple import build_r_multiple_target


def _base_frame(rows: int = 4) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01 09:00", periods=rows, freq="30min")
    return pd.DataFrame(
        {
            "manual_long_signal": [1.0] + [0.0] * (rows - 1),
            "open": [50.0] + [100.0] * (rows - 1),
            "high": [50.0] + [101.0] * (rows - 1),
            "low": [50.0] + [99.5] * (rows - 1),
            "close": [50.0] + [100.0] * (rows - 1),
            "vol_rolling_24": [0.01] * rows,
        },
        index=idx,
    )


def _target_cfg(**overrides: object) -> dict[str, object]:
    cfg: dict[str, object] = {
        "kind": "r_multiple",
        "candidate_col": "manual_long_signal",
        "volatility_col": "vol_rolling_24",
        "entry_price_mode": "next_open",
        "target_r_min": 1.0,
        "take_profit_r": 2.0,
        "stop_loss_r": 1.0,
        "max_holding_bars": 2,
        "stop_mode": "volatility_stop",
        "tie_break": "conservative",
        "allow_partial_horizon": False,
    }
    cfg.update(overrides)
    return cfg


def test_long_candidate_take_profit_first_gets_positive_label() -> None:
    df = _base_frame()
    df.loc[df.index[1], "high"] = 102.2

    out, label_col, _, meta = build_r_multiple_target(df, _target_cfg())

    assert label_col == "label"
    assert out.loc[df.index[0], "r_target_exit_reason"] == "take_profit"
    assert out.loc[df.index[0], "label"] == pytest.approx(1.0)
    assert out.loc[df.index[0], "r_target_trade_r"] == pytest.approx(2.0)
    assert meta["take_profit_count"] == 1


def test_long_candidate_stop_loss_first_gets_zero_label() -> None:
    df = _base_frame()
    df.loc[df.index[1], "low"] = 98.8

    out, _, _, meta = build_r_multiple_target(df, _target_cfg())

    assert out.loc[df.index[0], "r_target_exit_reason"] == "stop_loss"
    assert out.loc[df.index[0], "label"] == pytest.approx(0.0)
    assert out.loc[df.index[0], "r_target_trade_r"] == pytest.approx(-1.0)
    assert meta["stop_loss_count"] == 1


def test_non_candidate_row_keeps_label_nan() -> None:
    df = _base_frame()
    df.loc[df.index[1], "high"] = 102.2

    out, _, _, _ = build_r_multiple_target(df, _target_cfg())

    assert np.isnan(out.loc[df.index[1], "label"])
    assert out.loc[df.index[1], "r_target_candidate"] == pytest.approx(0.0)


def test_next_open_entry_uses_following_bar_open() -> None:
    df = _base_frame()
    df.loc[df.index[0], "close"] = 75.0
    df.loc[df.index[1], "open"] = 101.0
    df.loc[df.index[1], "high"] = 103.2

    out, _, _, _ = build_r_multiple_target(df, _target_cfg())

    assert out.loc[df.index[0], "r_target_entry_price"] == pytest.approx(101.0)
    assert out.loc[df.index[0], "r_target_take_profit_price"] == pytest.approx(103.02)


def test_tail_rows_without_full_horizon_remain_unlabeled() -> None:
    df = _base_frame(rows=4)
    df["manual_long_signal"] = [0.0, 0.0, 1.0, 0.0]

    out, _, _, meta = build_r_multiple_target(df, _target_cfg(max_holding_bars=2))

    assert np.isnan(out.loc[df.index[2], "label"])
    assert out.loc[df.index[2], "r_target_exit_reason"] == "unavailable_tail"
    assert meta["unavailable_tail_count"] == 1


def test_double_touch_conservative_resolves_to_stop_loss() -> None:
    df = _base_frame()
    df.loc[df.index[1], "high"] = 102.2
    df.loc[df.index[1], "low"] = 98.8

    out, _, _, _ = build_r_multiple_target(df, _target_cfg(tie_break="conservative"))

    assert out.loc[df.index[0], "r_target_exit_reason"] == "stop_loss"
    assert out.loc[df.index[0], "label"] == pytest.approx(0.0)
    assert out.loc[df.index[0], "r_target_trade_r"] == pytest.approx(-1.0)


def test_max_holding_close_realizes_r_and_labels_against_threshold() -> None:
    df = _base_frame()
    df.loc[df.index[1], ["high", "low", "close"]] = [101.0, 99.5, 100.0]
    df.loc[df.index[2], ["high", "low", "close"]] = [101.0, 99.5, 100.6]

    out, _, _, meta = build_r_multiple_target(df, _target_cfg(target_r_min=0.5))

    assert out.loc[df.index[0], "r_target_exit_reason"] == "max_holding_close"
    assert out.loc[df.index[0], "r_target_trade_r"] == pytest.approx(0.6)
    assert out.loc[df.index[0], "label"] == pytest.approx(1.0)
    assert meta["max_holding_close_count"] == 1
