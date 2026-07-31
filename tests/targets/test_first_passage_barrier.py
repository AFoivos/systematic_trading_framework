from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.targets.first_passage_barrier import build_first_passage_barrier_target


def _frame(rows: list[tuple[float, float, float, float]], *, atr: float = 1.0) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(rows), freq="30min")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index).assign(
        atr_2=atr
    )


def _config(**overrides: object) -> dict[str, object]:
    return {
        "kind": "first_passage_barrier_multiclass",
        "horizon_bars": 2,
        "upper_atr_multiplier": 1.0,
        "lower_atr_multiplier": 1.0,
        "atr_period": 2,
        "atr_col": "atr_2",
        "entry_delay_bars": 1,
        "entry_price_type": "open",
        "ambiguous_policy": "exclude",
        **overrides,
    }


def test_upper_barrier_hits_first() -> None:
    frame = _frame(
        [
            (100.0, 100.2, 99.8, 100.0),
            (100.0, 101.2, 99.6, 100.8),
            (100.8, 101.0, 100.4, 100.7),
            (100.7, 100.9, 100.3, 100.5),
        ]
    )
    out, label_col, _, _ = build_first_passage_barrier_target(frame, _config())

    assert out.iloc[0][label_col] == pytest.approx(1.0)
    assert out.iloc[0]["exit_price"] == pytest.approx(101.0)
    assert out.iloc[0]["exit_reason"] == "upper_barrier"
    assert out.iloc[0]["time_to_first_hit"] == pytest.approx(1.0)


def test_lower_barrier_hits_first() -> None:
    frame = _frame(
        [
            (100.0, 100.2, 99.8, 100.0),
            (100.0, 100.4, 98.8, 99.2),
            (99.2, 99.6, 99.0, 99.4),
            (99.4, 99.6, 99.1, 99.3),
        ]
    )
    out, label_col, _, _ = build_first_passage_barrier_target(frame, _config())

    assert out.iloc[0][label_col] == pytest.approx(-1.0)
    assert out.iloc[0]["exit_price"] == pytest.approx(99.0)
    assert out.iloc[0]["exit_reason"] == "lower_barrier"


def test_no_hit_uses_terminal_close() -> None:
    frame = _frame(
        [
            (100.0, 100.2, 99.8, 100.0),
            (100.0, 100.4, 99.7, 100.2),
            (100.2, 100.5, 99.8, 100.3),
            (100.3, 100.5, 100.0, 100.2),
        ]
    )
    out, label_col, fwd_col, _ = build_first_passage_barrier_target(frame, _config())

    assert out.iloc[0][label_col] == pytest.approx(0.0)
    assert out.iloc[0]["exit_reason"] == "no_hit"
    assert out.iloc[0]["exit_price"] == pytest.approx(100.3)
    assert out.iloc[0][fwd_col] == pytest.approx(0.003)
    assert np.isnan(out.iloc[0]["time_to_first_hit"])


def test_same_bar_double_touch_is_ambiguous_and_excluded() -> None:
    frame = _frame(
        [
            (100.0, 100.2, 99.8, 100.0),
            (100.0, 101.2, 98.8, 100.1),
            (100.1, 100.5, 99.7, 100.2),
            (100.2, 100.4, 100.0, 100.1),
        ]
    )
    out, label_col, _, meta = build_first_passage_barrier_target(frame, _config())

    assert np.isnan(out.iloc[0][label_col])
    assert bool(out.iloc[0]["ambiguous"])
    assert out.iloc[0]["exit_reason"] == "ambiguous"
    assert out.iloc[0]["first_passage_label_stop_first"] == pytest.approx(-1.0)
    assert out.iloc[0]["first_passage_label_target_first"] == pytest.approx(1.0)
    assert meta["ambiguous_count"] >= 1


def test_intrabar_data_resolves_parent_bar_ambiguity() -> None:
    frame = _frame(
        [
            (100.0, 100.2, 99.8, 100.0),
            (100.0, 101.2, 98.8, 100.1),
            (100.1, 100.5, 99.7, 100.2),
            (100.2, 100.4, 100.0, 100.1),
        ]
    )
    intrabar_index = pd.date_range(frame.index[1], periods=3, freq="10min")
    intrabar = pd.DataFrame(
        {
            "open": [100.0, 100.7, 100.3],
            "high": [100.8, 101.1, 100.6],
            "low": [99.7, 100.2, 98.8],
        },
        index=intrabar_index,
    )
    out, label_col, _, meta = build_first_passage_barrier_target(
        frame,
        _config(use_intrabar_resolution=True, intrabar_data=intrabar),
    )

    assert out.iloc[0][label_col] == pytest.approx(1.0)
    assert bool(out.iloc[0]["ambiguous"])
    assert bool(out.iloc[0]["intrabar_resolved"])
    assert meta["intrabar_resolved_count"] >= 1


def test_entry_delay_and_atr_are_anchored_to_feature_bar() -> None:
    frame = _frame(
        [
            (100.0, 100.1, 99.9, 100.0),
            (200.0, 250.0, 150.0, 200.0),
            (100.0, 101.2, 99.8, 100.8),
            (100.8, 101.0, 100.2, 100.7),
            (100.7, 100.9, 100.4, 100.6),
        ]
    )
    frame["atr_2"] = [1.0, 50.0, 50.0, 50.0, 50.0]
    out, label_col, _, meta = build_first_passage_barrier_target(
        frame,
        _config(entry_delay_bars=2),
    )

    assert out.iloc[0]["entry_price"] == pytest.approx(100.0)
    assert out.iloc[0]["upper_barrier"] == pytest.approx(101.0)
    assert out.iloc[0][label_col] == pytest.approx(1.0)
    assert out.iloc[0]["time_to_first_hit"] == pytest.approx(1.0)
    assert meta["horizon"] == 4


def test_mfe_mae_use_full_observed_ohlc_path_to_exit() -> None:
    frame = _frame(
        [
            (100.0, 100.1, 99.9, 100.0),
            (100.0, 100.6, 99.4, 100.2),
            (100.2, 100.8, 99.2, 100.3),
            (100.3, 100.5, 100.0, 100.2),
        ]
    )
    out, _, _, _ = build_first_passage_barrier_target(
        frame,
        _config(upper_atr_multiplier=10.0, lower_atr_multiplier=10.0),
    )

    assert out.iloc[0]["mfe"] == pytest.approx(0.8)
    assert out.iloc[0]["mae"] == pytest.approx(-0.8)
    assert out.iloc[0]["mfe_atr"] == pytest.approx(0.8)
    assert out.iloc[0]["mae_atr"] == pytest.approx(-0.8)


def test_minimum_barrier_to_cost_ratio_filters_expensive_observation() -> None:
    frame = _frame(
        [
            (100.0, 100.1, 99.9, 100.0),
            (100.0, 101.2, 99.5, 100.8),
            (100.8, 101.0, 100.4, 100.7),
            (100.7, 100.9, 100.3, 100.5),
        ]
    )
    out, label_col, _, _ = build_first_passage_barrier_target(
        frame,
        _config(round_trip_cost=0.02, minimum_barrier_to_cost_ratio=1.0),
    )

    assert np.isnan(out.iloc[0][label_col])
    assert np.isnan(out.iloc[0]["first_passage_label_stop_first"])
    assert np.isnan(out.iloc[0]["first_passage_label_target_first"])
    assert not bool(out.iloc[0]["barrier_cost_eligible"])
    assert out.iloc[0]["exit_reason"] == "barrier_to_cost_filter"
