from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class TimeSplit:
    fold: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_idx: np.ndarray
    test_idx: np.ndarray


def _require_positive_int(name: str, value: int) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _require_non_negative_int(name: str, value: int) -> None:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be an integer >= 0.")


def time_split_indices(n_samples: int, train_frac: float = 0.7) -> list[TimeSplit]:
    if not isinstance(n_samples, int) or n_samples < 2:
        raise ValueError("n_samples must be an integer >= 2.")
    if not isinstance(train_frac, float) or not 0.0 < train_frac < 1.0:
        raise ValueError("train_frac must be in (0,1).")

    split_idx = int(n_samples * train_frac)
    if split_idx <= 0 or split_idx >= n_samples:
        raise ValueError("Invalid train_frac produced an empty train or test split.")

    train_idx = np.arange(0, split_idx, dtype=int)
    test_idx = np.arange(split_idx, n_samples, dtype=int)
    return [
        TimeSplit(
            fold=0,
            train_start=0,
            train_end=split_idx,
            test_start=split_idx,
            test_end=n_samples,
            train_idx=train_idx,
            test_idx=test_idx,
        )
    ]


def walk_forward_split_indices(
    n_samples: int,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    expanding: bool = True,
    max_folds: int | None = None,
) -> list[TimeSplit]:
    return purged_walk_forward_split_indices(
        n_samples=n_samples,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
        purge_bars=0,
        embargo_bars=0,
        expanding=expanding,
        max_folds=max_folds,
    )


def purged_walk_forward_split_indices(
    n_samples: int,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    purge_bars: int = 0,
    embargo_bars: int = 0,
    expanding: bool = True,
    max_folds: int | None = None,
) -> list[TimeSplit]:
    if not isinstance(n_samples, int) or n_samples < 2:
        raise ValueError("n_samples must be an integer >= 2.")
    _require_positive_int("train_size", train_size)
    _require_positive_int("test_size", test_size)
    if step_size is None:
        step_size = test_size
    _require_positive_int("step_size", step_size)
    _require_non_negative_int("purge_bars", purge_bars)
    _require_non_negative_int("embargo_bars", embargo_bars)
    if max_folds is not None:
        _require_positive_int("max_folds", max_folds)
    if train_size >= n_samples:
        raise ValueError("train_size must be < n_samples.")

    splits: list[TimeSplit] = []
    fold = 0
    test_start = train_size

    while test_start < n_samples:
        test_end = min(n_samples, test_start + test_size)
        if test_end <= test_start:
            break

        train_end = test_start - purge_bars
        if train_end <= 0:
            test_start += step_size + embargo_bars
            continue

        if expanding:
            train_start = 0
        else:
            train_start = max(0, train_end - train_size)

        if train_end <= train_start:
            test_start += step_size + embargo_bars
            continue

        train_idx = np.arange(train_start, train_end, dtype=int)
        test_idx = np.arange(test_start, test_end, dtype=int)

        if train_idx.size > 0 and test_idx.size > 0:
            splits.append(
                TimeSplit(
                    fold=fold,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_idx=train_idx,
                    test_idx=test_idx,
                )
            )
            fold += 1
            if max_folds is not None and fold >= max_folds:
                break

        if test_end >= n_samples:
            break
        test_start += step_size + embargo_bars

    if not splits:
        raise ValueError("No valid folds produced. Check train/test/purge/embargo settings.")

    return splits


def build_time_splits(
    *,
    method: Literal["time", "walk_forward", "purged"],
    n_samples: int,
    split_cfg: dict,
    target_horizon: int = 1,
) -> list[TimeSplit]:
    if method == "time":
        train_frac = float(split_cfg.get("train_frac", 0.7))
        return time_split_indices(n_samples=n_samples, train_frac=train_frac)

    train_size = split_cfg.get("train_size")
    if train_size is None:
        train_frac = float(split_cfg.get("train_frac", 0.7))
        train_size = int(n_samples * train_frac)
    test_size = int(split_cfg.get("test_size", 63))
    step_size = split_cfg.get("step_size")
    step_size = int(step_size) if step_size is not None else None
    expanding = bool(split_cfg.get("expanding", True))
    max_folds = split_cfg.get("max_folds")
    max_folds = int(max_folds) if max_folds is not None else None

    if method == "walk_forward":
        return walk_forward_split_indices(
            n_samples=n_samples,
            train_size=int(train_size),
            test_size=test_size,
            step_size=step_size,
            expanding=expanding,
            max_folds=max_folds,
        )

    if method == "purged":
        purge_default = max(int(target_horizon), 0)
        purge_bars = int(split_cfg.get("purge_bars", purge_default))
        if purge_bars < purge_default:
            raise ValueError(
                "purge_bars is too small for the target horizon; set purge_bars >= target_horizon."
            )
        embargo_bars = int(split_cfg.get("embargo_bars", 0))
        return purged_walk_forward_split_indices(
            n_samples=n_samples,
            train_size=int(train_size),
            test_size=test_size,
            step_size=step_size,
            purge_bars=purge_bars,
            embargo_bars=embargo_bars,
            expanding=expanding,
            max_folds=max_folds,
        )

    raise ValueError(f"Unsupported split.method: {method}")


__all__ = [
    "TimeSplit",
    "time_split_indices",
    "walk_forward_split_indices",
    "purged_walk_forward_split_indices",
    "build_time_splits",
]
