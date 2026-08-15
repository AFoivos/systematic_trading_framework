from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.experiments.support.ethusd_pattern_atlas import (
    PatternSpec,
    _non_overlapping_values,
    _report_markdown,
    build_pattern_frame,
    candidate_grid,
    candidate_triggers,
    fixed_holding_ledger,
    stable_pattern_ranking,
)


def _raw_frame(periods: int = 500) -> pd.DataFrame:
    index = pd.date_range("2021-01-01", periods=periods, freq="30min")
    steps = 0.0005 * np.sin(np.arange(periods) / 11.0) + 0.0001
    close = 100.0 * np.exp(np.cumsum(steps))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.001
    low = np.minimum(open_, close) * 0.999
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100.0 + (np.arange(periods) % 23),
        },
        index=index,
    )


def _compression_spec() -> PatternSpec:
    return PatternSpec(
        family="compression_release",
        primary_threshold=0.85,
        secondary_threshold=1.5,
        release_threshold=0.50,
        holding_bars=2,
        session_start_hour=0,
        session_end_hour=24,
    )


def test_pattern_features_are_prefix_invariant() -> None:
    raw = _raw_frame()
    baseline = build_pattern_frame(raw)
    changed = raw.copy()
    changed.loc[changed.index[400] :, ["open", "high", "low", "close", "volume"]] *= 7.0
    mutated = build_pattern_frame(changed)
    causal_columns = [column for column in baseline if not column.startswith("future_")]
    pd.testing.assert_frame_equal(
        baseline.loc[: baseline.index[399], causal_columns],
        mutated.loc[: mutated.index[399], causal_columns],
    )


def test_stage2_candidate_grid_is_deterministic_and_distinct() -> None:
    specs = candidate_grid("stage2")
    assert len(specs) == 256
    assert len({spec.candidate_id for spec in specs}) == len(specs)
    assert {spec.family for spec in specs} == {
        "efficient_state_continuation",
        "efficiency_acceleration_state",
        "efficient_anti_persistence",
        "compression_acceptance_impulse",
        "volume_wick_fade",
        "pullback_resume_cross",
    }


def test_signal_function_does_not_read_future_outcome_columns() -> None:
    featured = build_pattern_frame(_raw_frame())
    baseline = candidate_triggers(featured, _compression_spec())
    changed = featured.copy()
    future_columns = [column for column in changed if column.startswith("future_")]
    changed.loc[:, future_columns] = 999.0
    mutated = candidate_triggers(changed, _compression_spec())
    pd.testing.assert_series_equal(baseline, mutated)


def test_fixed_holding_replay_enters_next_open() -> None:
    index = pd.date_range("2025-01-01", periods=8, freq="30min")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 101.0, 102.0, 104.0, 103.0, 102.0, 102.0],
            "high": [101.0] * 8,
            "low": [99.0] * 8,
            "close": [100.0] * 8,
            "atlas_signed_efficiency_8": [0.0] * 8,
            "atlas_signed_efficiency_16": [0.0, 0.7, 0.7, 0.0, -0.7, -0.7, 0.0, 0.0],
            "atlas_signed_efficiency_32": [0.0] * 8,
            "atlas_signed_efficiency_64": [0.0] * 8,
            "atlas_release": [0.0, 2.0, 2.0, 0.0, 2.0, 2.0, 0.0, 0.0],
            "atlas_acceptance": [0.0, 0.8, 0.8, 0.0, -0.8, -0.8, 0.0, 0.0],
            "atlas_efficiency_agreement": [1.0] * 8,
            "atlas_compression": [1.0, 0.5, 0.5, 1.0, 0.5, 0.5, 1.0, 1.0],
            "atlas_entry_hour_utc": list(range(8)),
            "atlas_contiguous_bars": [200] * 8,
            "atlas_gap_flag": [False] * 8,
        },
        index=index,
    )
    triggers = candidate_triggers(frame, _compression_spec())
    assert triggers.tolist() == [0, 1, 0, 0, -1, 0, 0, 0]
    ledger = fixed_holding_ledger(
        frame,
        _compression_spec(),
        start=index.min(),
        end=index.max(),
        round_trip_cost_bps=0.0,
    )
    first = ledger.iloc[0]
    assert first["signal_timestamp"] == index[1]
    assert first["entry_timestamp"] == index[2]
    assert first["exit_timestamp"] == index[4]
    assert first["gross_return"] == pytest.approx(104.0 / 101.0 - 1.0)


def test_stable_pattern_direction_is_fixed_from_discovery() -> None:
    records = []
    means = {
        "discovery": -2.0,
        "validation_2023": -1.5,
        "validation_2024": -0.7,
        "confirmation_2025h1": -0.4,
        "historical_diagnostic": 0.2,
    }
    for split, mean in means.items():
        records.append(
            {
                "split": split,
                "view": "efficiency_32_quintile",
                "group": "high",
                "outcome_kind": "continuation_32",
                "horizon_bars": 8,
                "event_count": 120,
                "mean_return_bps": mean,
                "median_return_bps": mean,
                "hit_rate": 0.5,
                "t_stat": 1.0,
            }
        )
    ranked = stable_pattern_ranking(pd.DataFrame(records))
    row = ranked.iloc[0]
    assert row["discovery_direction"] == "negative"
    assert bool(row["stable_across_selection_splits"])
    assert not bool(row["historical_direction_persisted"])


def test_non_overlapping_sampler_treats_nullable_mask_as_false() -> None:
    outcome = pd.Series([0.1, 0.2, 0.3, 0.4])
    mask = pd.Series([True, pd.NA, True, False], dtype="boolean")
    sampled = _non_overlapping_values(outcome, mask, horizon=1)
    assert sampled.tolist() == [0.1, 0.3]


def test_report_states_historical_period_is_not_prospective() -> None:
    summary = {
        "verdict": "NO ROBUST STRATEGY CANDIDATE",
        "candidate_grid_count": 10,
        "selection_status": {"eligible_candidate_count": 0},
        "selected_candidate": None,
        "selection_metrics": {},
        "historical_diagnostic_metrics": {},
        "exact_tick_base_metrics": {},
        "stable_pattern_count_selection": 0,
        "stable_pattern_count_persisting_historical": 0,
        "pattern_cells_tested": 1,
        "base_round_trip_cost_bps": 3.0,
    }
    inventory = pd.DataFrame(
        [
            {
                "source": "bars_M30.csv",
                "kind": "bar",
                "canonical_rows": 100,
                "timestamp_start": "2020-01-01",
                "timestamp_end": "2025-01-01",
                "row_cap_suspected": False,
            }
        ]
    )
    consistency = pd.DataFrame(
        [{"comparison": "M15_to_M30", "common_complete_rows": 10}]
    )
    report = _report_markdown(summary, inventory=inventory, consistency=consistency)
    assert "historical pseudo-holdout, not prospective" in report
    assert "Only after passing may it access" in report
