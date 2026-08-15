from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.experiments.support.ethusd_custom_indicator_alpha import (
    CandidateSpec,
    _report_markdown,
    bar_barrier_ledger,
    candidate_triggers,
    select_candidate,
)


def _spec() -> CandidateSpec:
    return CandidateSpec(
        score_threshold=0.25,
        flow_threshold=0.15,
        compression_max=1.10,
        release_min=0.90,
        target_r=0.60,
        stop_r=1.0,
        max_holding_bars=4,
    )


def _frame() -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=8, freq="30min")
    frame = pd.DataFrame(
        {
            "open": [100.0] * 8,
            "high": [100.1] * 8,
            "low": [99.9] * 8,
            "close": [100.0] * 8,
            "casc_score": [0.0, 0.5, 0.5, 0.0, -0.5, -0.5, 0.0, 0.0],
            "laf_directional_flow": [0.0, 0.4, 0.4, 0.0, -0.4, -0.4, 0.0, 0.0],
            "pcp_consensus": [0.0, 0.3, 0.3, 0.0, -0.3, -0.3, 0.0, 0.0],
            "pcp_scale_agreement": [1.0] * 8,
            "cre_compression": [0.8] * 8,
            "cre_release": [1.2] * 8,
            "causal_range_energy": [0.01] * 8,
        },
        index=index,
    )
    return frame


def test_candidate_triggers_emit_transition_pulses_only() -> None:
    triggers = candidate_triggers(_frame(), _spec())
    assert triggers.tolist() == [0, 1, 0, 0, -1, 0, 0, 0]


def test_bar_replay_enters_next_bar_and_resolves_dual_hit_as_stop() -> None:
    frame = _frame()
    frame.loc[frame.index[2], ["open", "high", "low", "close"]] = [100.0, 101.0, 98.0, 100.0]
    ledger = bar_barrier_ledger(
        frame,
        _spec(),
        start=frame.index.min(),
        end=frame.index.max(),
        round_trip_cost_bps=0.0,
    )
    first = ledger.iloc[0]
    assert first["signal_timestamp"] == frame.index[1]
    assert first["entry_timestamp"] == frame.index[2]
    assert first["outcome"] == "stop_first"
    assert first["gross_return"] == pytest.approx(-0.01)


def test_bar_replay_is_prefix_invariant_before_future_mutation() -> None:
    frame = _frame()
    baseline = candidate_triggers(frame, _spec())
    changed = frame.copy()
    changed.loc[
        changed.index[6]:,
        ["casc_score", "laf_directional_flow", "pcp_consensus"],
    ] = 999.0
    mutated = candidate_triggers(changed, _spec())
    pd.testing.assert_series_equal(baseline.iloc[:6], mutated.iloc[:6])


def test_bar_replay_rejects_negative_cost() -> None:
    frame = _frame()
    with pytest.raises(ValueError):
        bar_barrier_ledger(
            frame,
            _spec(),
            start=frame.index.min(),
            end=frame.index.max(),
            round_trip_cost_bps=-1.0,
        )


def test_selection_fails_closed_without_an_eligible_candidate() -> None:
    selected, table, status = select_candidate(_frame(), round_trip_cost_bps=4.0)

    assert selected is None
    assert not table.empty
    assert status["status"] == "no_candidate_passed_development_gate"
    assert status["selected_candidate_id"] is None
    assert status["locked_evaluation_authorized"] is False


def test_report_marks_locked_and_exact_layers_as_not_evaluated() -> None:
    summary = {
        "research_verdict": "NO-GO AT SELECTION GATE",
        "selected_candidate": None,
        "development": {
            "trade_count": 10,
            "win_rate": 0.5,
            "cumulative_return": -0.1,
            "trade_profit_factor": 0.8,
            "conventional_sharpe": -1.0,
        },
        "validation": {
            "trade_count": 5,
            "win_rate": 0.4,
            "cumulative_return": -0.05,
            "trade_profit_factor": 0.7,
            "conventional_sharpe": -1.2,
        },
        "locked_bar": {"status": "not_evaluated"},
        "exact_tick_base": {"status": "not_evaluated"},
        "exact_tick_stress": {
            "scenario_count": 0,
            "positive_scenario_count": 0,
            "median_cumulative_return": None,
            "worst_cumulative_return": None,
        },
        "gates": {
            "locked_bar": {"evaluated": False, "passed": False},
            "exact_tick": {"evaluated": False, "passed": False},
        },
    }

    report = _report_markdown(summary)

    assert "canonical run did not read the locked period" in report
    assert report.count("not evaluated: selection gate failed") == 2
    assert "| Locked M30 | None" not in report
    assert "evaluated once afterward" not in report
