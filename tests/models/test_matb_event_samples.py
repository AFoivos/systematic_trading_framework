from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.matb_event_samples import (
    evaluate_matb_sample_gate,
    initialize_blocked_matb_predictions,
    purge_matb_event_overlap,
    sort_matb_event_table,
)


def _events(rows: int = 1600) -> pd.DataFrame:
    starts = pd.date_range("2015-01-01", periods=rows, freq="12h", tz="UTC")
    groups = np.array(["equity_indices", "metals", "energy", "fx", "crypto"])
    return pd.DataFrame(
        {
            "event_start_timestamp": starts,
            "event_end_timestamp": starts + pd.Timedelta(hours=6),
            "asset": [f"asset_{idx % 10}" for idx in range(rows)],
            "asset_group": groups[np.arange(rows) % len(groups)],
            "side": np.where(np.arange(rows) % 2 == 0, 1, -1),
            "target_class": np.arange(rows) % 2,
        }
    )


def test_matb_sample_gate_success() -> None:
    events = _events()
    result = evaluate_matb_sample_gate(
        events,
        folds=[{"fold": 0, "train_positions": np.arange(1200)}],
    )
    assert result.passed
    assert result.fit_permitted
    assert not result.failure_reasons


def test_matb_sample_gate_failure_is_fail_closed() -> None:
    events = _events(200)
    events["side"] = 1
    events["asset_group"] = "equity_indices"
    events["asset"] = "SPX500"
    result = evaluate_matb_sample_gate(
        events,
        folds=[{"fold": 0, "train_positions": np.arange(200)}],
    )
    assert not result.passed
    assert not result.fit_permitted
    assert any("total_candidate_events" in reason for reason in result.failure_reasons)
    assert any("short_candidate_events" in reason for reason in result.failure_reasons)
    assert any("maximum_asset_share" in reason for reason in result.failure_reasons)


def test_matb_sample_gate_reports_pooled_concentration_before_any_fit() -> None:
    events = _events(1500)
    events["asset"] = "dominant"
    events.loc[events.index[700:], "asset"] = [f"minor_{idx % 5}" for idx in range(800)]

    result = evaluate_matb_sample_gate(events)
    checks = {check["metric"]: check for check in result.checks}

    assert checks["pooled_maximum_asset_share"]["observed_value"] > 0.45
    assert checks["pooled_maximum_asset_share"]["passed"] is False
    assert result.fit_permitted is False


def test_event_table_is_stably_sorted_chronologically() -> None:
    events = _events(5).iloc[[4, 1, 3, 0, 2]].copy()
    ordered = sort_matb_event_table(events)
    assert ordered["event_start_timestamp"].is_monotonic_increasing
    assert list(ordered["event_start_timestamp"]) == sorted(events["event_start_timestamp"])


def test_event_overlap_and_post_test_embargo_are_removed() -> None:
    starts = pd.to_datetime(
        [
            "2020-01-01 00:00",
            "2020-01-02 00:00",
            "2020-01-03 00:00",
            "2020-01-03 18:00",
            "2020-01-06 00:00",
        ],
        utc=True,
    )
    events = pd.DataFrame(
        {
            "event_start_timestamp": starts,
            "event_end_timestamp": [
                starts[0] + pd.Timedelta(hours=1),
                starts[2] + pd.Timedelta(hours=1),  # overlaps the test event
                starts[2] + pd.Timedelta(hours=2),
                starts[3] + pd.Timedelta(hours=1),  # inside post-test embargo
                starts[4] + pd.Timedelta(hours=1),
            ],
            "asset": ["A", "A", "A", "B", "B"],
            "asset_group": ["g1", "g1", "g1", "g2", "g2"],
            "side": [1, 1, -1, 1, -1],
            "target_class": [1, 0, 1, 0, 1],
        }
    )
    retained, audit = purge_matb_event_overlap(
        events,
        train_positions=[0, 1, 3, 4],
        test_positions=[2],
        embargo=pd.Timedelta(days=1),
    )
    assert retained.tolist() == [0, 4]
    assert audit["purged_overlap_rows"] == 1
    assert audit["purged_embargo_rows"] == 1
    assert audit["pooled_overlap_after"] == 0
    assert audit["per_asset_overlap_after"] == 0


def test_gate_failure_emits_no_predictions_or_oos_flags() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="30min", tz="UTC")
    frame = pd.DataFrame({"matb_candidate": [0, 1, 0, 1]}, index=index)
    blocked = initialize_blocked_matb_predictions({"A": frame})["A"]
    assert blocked["matb_pred_success_prob"].isna().all()
    assert blocked["matb_pred_ev_r"].isna().all()
    assert blocked["matb_pred_is_oos"].eq(0).all()
    assert blocked.loc[blocked["matb_candidate"].eq(0), "matb_pred_success_prob"].isna().all()
