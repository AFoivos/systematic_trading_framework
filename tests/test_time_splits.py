from __future__ import annotations

import numpy as np

from src.evaluation.time_splits import (
    build_time_splits,
    purged_walk_forward_split_indices,
    walk_forward_split_indices,
)


def test_walk_forward_splits_are_time_ordered_and_non_overlapping() -> None:
    splits = walk_forward_split_indices(
        n_samples=220,
        train_size=100,
        test_size=20,
        step_size=20,
        expanding=True,
    )

    assert len(splits) >= 2

    prev_test_end = None
    for split in splits:
        assert split.train_start == 0
        assert split.train_end <= split.test_start
        assert split.test_start < split.test_end
        assert np.max(split.train_idx) < np.min(split.test_idx)
        if prev_test_end is not None:
            assert split.test_start >= prev_test_end
        prev_test_end = split.test_end


def test_purged_walk_forward_respects_purge_and_embargo() -> None:
    purge_bars = 3
    embargo_bars = 2
    step_size = 10
    splits = purged_walk_forward_split_indices(
        n_samples=180,
        train_size=80,
        test_size=10,
        step_size=step_size,
        purge_bars=purge_bars,
        embargo_bars=embargo_bars,
        expanding=True,
    )

    assert len(splits) >= 2
    for split in splits:
        assert split.train_end == split.test_start - purge_bars
        assert np.max(split.train_idx) <= split.test_start - purge_bars - 1

    for prev, curr in zip(splits[:-1], splits[1:]):
        assert curr.test_start - prev.test_start == step_size + embargo_bars
        assert curr.test_start >= prev.test_end + embargo_bars


def test_build_time_splits_uses_target_horizon_for_default_purge() -> None:
    splits = build_time_splits(
        method="purged",
        n_samples=150,
        split_cfg={
            "train_size": 60,
            "test_size": 15,
            "step_size": 15,
            "expanding": True,
        },
        target_horizon=5,
    )
    first = splits[0]
    assert first.train_end == first.test_start - 5
