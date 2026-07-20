from __future__ import annotations

"""Event-table, purging, and hard sample-gate utilities for MATB meta-learning."""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MatbSampleGateResult:
    passed: bool
    fit_permitted: bool
    checks: tuple[dict[str, Any], ...]
    failure_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "PASSED" if self.passed else "FAILED",
            "passed": bool(self.passed),
            "fit_permitted": bool(self.fit_permitted),
            "checks": [dict(check) for check in self.checks],
            "failure_reasons": list(self.failure_reasons),
        }


def sort_matb_event_table(events: pd.DataFrame) -> pd.DataFrame:
    required = {
        "event_start_timestamp",
        "event_end_timestamp",
        "asset",
        "asset_group",
        "side",
    }
    missing = sorted(required - set(events.columns))
    if missing:
        raise KeyError(f"MATB event table is missing columns: {missing}")
    out = events.copy()
    for column in ("event_start_timestamp", "event_end_timestamp"):
        out[column] = pd.to_datetime(out[column], utc=True, errors="coerce")
    if bool(out[["event_start_timestamp", "event_end_timestamp"]].isna().any().any()):
        raise ValueError("MATB event timestamps must be non-missing and parseable.")
    if bool((out["event_end_timestamp"] < out["event_start_timestamp"]).any()):
        raise ValueError("MATB event_end_timestamp must be >= event_start_timestamp.")
    out["asset"] = out["asset"].astype(str)
    out["asset_group"] = out["asset_group"].astype(str)
    numeric_side = pd.to_numeric(out["side"], errors="coerce")
    if bool(numeric_side.isna().any()) or bool(numeric_side.eq(0.0).any()):
        raise ValueError("MATB event side must contain only non-zero numeric values.")
    out["side"] = np.sign(numeric_side).astype(int)
    return out.sort_values(
        ["event_start_timestamp", "event_end_timestamp", "asset"],
        kind="mergesort",
    ).reset_index(drop=True)


def purge_matb_event_overlap(
    events: pd.DataFrame,
    *,
    train_positions: Sequence[int],
    test_positions: Sequence[int],
    embargo: pd.Timedelta = pd.Timedelta(0),
) -> tuple[np.ndarray, dict[str, Any]]:
    """Remove train events overlapping the global test interval or its post-test embargo."""
    ordered = sort_matb_event_table(events)
    train = np.asarray(list(train_positions), dtype=int)
    test = np.asarray(list(test_positions), dtype=int)
    if len(test) == 0:
        raise ValueError("MATB overlap purge requires at least one test event.")
    if (train < 0).any() or (train >= len(ordered)).any() or (test < 0).any() or (test >= len(ordered)).any():
        raise IndexError("MATB train/test positions must reference the sorted event table.")
    if pd.Timedelta(embargo) < pd.Timedelta(0):
        raise ValueError("MATB embargo must be non-negative.")

    test_start = ordered.loc[test, "event_start_timestamp"].min()
    test_end = ordered.loc[test, "event_end_timestamp"].max()
    train_rows = ordered.loc[train]
    overlaps = (
        train_rows["event_start_timestamp"].le(test_end)
        & train_rows["event_end_timestamp"].ge(test_start)
    )
    embargo_end = test_end + pd.Timedelta(embargo)
    embargoed = (
        train_rows["event_start_timestamp"].gt(test_end)
        & train_rows["event_start_timestamp"].le(embargo_end)
    )
    keep = ~(overlaps | embargoed)
    retained = train[keep.to_numpy(dtype=bool)]

    # Explicitly verify both pooled and per-asset interval separation.
    retained_rows = ordered.loc[retained]
    post_overlap = (
        retained_rows["event_start_timestamp"].le(test_end)
        & retained_rows["event_end_timestamp"].ge(test_start)
    )
    if bool(post_overlap.any()):
        raise AssertionError("MATB pooled event overlap remained after purge.")
    for asset in sorted(set(retained_rows["asset"]) & set(ordered.loc[test, "asset"])):
        asset_train = retained_rows.loc[retained_rows["asset"].eq(asset)]
        asset_test = ordered.loc[test].loc[ordered.loc[test, "asset"].eq(asset)]
        if asset_train.empty or asset_test.empty:
            continue
        asset_overlap = (
            asset_train["event_start_timestamp"].le(asset_test["event_end_timestamp"].max())
            & asset_train["event_end_timestamp"].ge(asset_test["event_start_timestamp"].min())
        )
        if bool(asset_overlap.any()):
            raise AssertionError(f"MATB per-asset overlap remained after purge for {asset}.")
    return retained, {
        "test_start": test_start.isoformat(),
        "test_end": test_end.isoformat(),
        "embargo_end": embargo_end.isoformat(),
        "training_rows_before": int(len(train)),
        "purged_overlap_rows": int(overlaps.sum()),
        "purged_embargo_rows": int((embargoed & ~overlaps).sum()),
        "training_rows_after": int(len(retained)),
        "pooled_overlap_after": 0,
        "per_asset_overlap_after": 0,
    }


def build_matb_walk_forward_folds(
    events: pd.DataFrame,
    *,
    training_years: int = 4,
    testing_months: int = 6,
    step_months: int = 6,
    embargo: pd.Timedelta = pd.Timedelta(days=1),
    pseudo_holdout_start: str | pd.Timestamp = "2024-01-01",
) -> list[dict[str, Any]]:
    """Build rolling calendar folds and purge by realized event intervals."""
    if training_years <= 0 or testing_months <= 0 or step_months <= 0:
        raise ValueError("MATB walk-forward horizons must be positive.")
    ordered = sort_matb_event_table(events)
    if ordered.empty:
        return []
    holdout_start = pd.Timestamp(pseudo_holdout_start)
    holdout_start = holdout_start.tz_localize("UTC") if holdout_start.tz is None else holdout_start.tz_convert("UTC")
    first_start = ordered["event_start_timestamp"].min()
    test_start = first_start + pd.DateOffset(years=int(training_years))
    folds: list[dict[str, Any]] = []
    fold_id = 0
    while test_start < min(holdout_start, ordered["event_start_timestamp"].max()):
        test_end = min(test_start + pd.DateOffset(months=int(testing_months)), holdout_start)
        train_start = test_start - pd.DateOffset(years=int(training_years))
        train_mask = ordered["event_start_timestamp"].ge(train_start) & ordered[
            "event_start_timestamp"
        ].lt(test_start)
        test_mask = ordered["event_start_timestamp"].ge(test_start) & ordered[
            "event_start_timestamp"
        ].lt(test_end)
        train_positions = np.flatnonzero(train_mask.to_numpy(dtype=bool))
        test_positions = np.flatnonzero(test_mask.to_numpy(dtype=bool))
        if len(test_positions) > 0:
            purged, audit = purge_matb_event_overlap(
                ordered,
                train_positions=train_positions,
                test_positions=test_positions,
                embargo=embargo,
            )
            folds.append(
                {
                    "fold": int(fold_id),
                    "train_positions": purged,
                    "test_positions": test_positions,
                    "train_start": train_start.isoformat(),
                    "train_end": test_start.isoformat(),
                    "test_start": test_start.isoformat(),
                    "test_end": test_end.isoformat(),
                    "purge_audit": audit,
                }
            )
            fold_id += 1
        test_start = test_start + pd.DateOffset(months=int(step_months))
    return folds


def evaluate_matb_sample_gate(
    events: pd.DataFrame,
    *,
    folds: Sequence[Mapping[str, Any]] | None = None,
) -> MatbSampleGateResult:
    """Evaluate the immutable global and per-training-fold MATB sample gates."""
    ordered = sort_matb_event_table(events)
    checks: list[dict[str, Any]] = []

    def _record(metric: str, threshold: str, observed: Any, passed: bool, reason: str) -> None:
        checks.append(
            {
                "metric": metric,
                "threshold": threshold,
                "observed_value": observed,
                "passed": bool(passed),
                "reason": reason,
            }
        )

    total = int(len(ordered))
    long_count = int(ordered["side"].eq(1).sum())
    short_count = int(ordered["side"].eq(-1).sum())
    asset_counts = ordered.groupby("asset", observed=True).size()
    group_counts = ordered.groupby("asset_group", observed=True).size()
    qualifying_groups = int(group_counts.ge(100).sum())
    maximum_asset_share = float(asset_counts.max() / total) if total else 1.0
    maximum_group_share = float(group_counts.max() / total) if total else 1.0
    _record("total_candidate_events", ">= 1500", total, total >= 1500, "pooled candidate count")
    _record("long_candidate_events", ">= 150", long_count, long_count >= 150, "long-side coverage")
    _record("short_candidate_events", ">= 150", short_count, short_count >= 150, "short-side coverage")
    _record(
        "asset_groups_with_at_least_100_events",
        ">= 4",
        qualifying_groups,
        qualifying_groups >= 4,
        "cross-group coverage",
    )
    _record(
        "pooled_maximum_asset_share",
        "<= 0.45",
        maximum_asset_share,
        maximum_asset_share <= 0.45,
        "necessary pre-fit asset concentration condition",
    )
    _record(
        "pooled_maximum_group_share",
        "<= 0.45",
        maximum_group_share,
        maximum_group_share <= 0.45,
        "necessary pre-fit group concentration condition",
    )

    for raw_fold in list(folds or []):
        fold_id = int(raw_fold.get("fold", len(checks)))
        positions = np.asarray(list(raw_fold.get("train_positions", [])), dtype=int)
        train = ordered.loc[positions]
        train_count = int(len(train))
        _record(
            f"fold_{fold_id}_training_events",
            ">= 300",
            train_count,
            train_count >= 300,
            "post-purge training rows",
        )
        max_asset_share = (
            float(train.groupby("asset", observed=True).size().max() / train_count)
            if train_count
            else 1.0
        )
        max_group_share = (
            float(train.groupby("asset_group", observed=True).size().max() / train_count)
            if train_count
            else 1.0
        )
        _record(
            f"fold_{fold_id}_maximum_asset_share",
            "<= 0.45",
            max_asset_share,
            max_asset_share <= 0.45,
            "training-event concentration",
        )
        _record(
            f"fold_{fold_id}_maximum_group_share",
            "<= 0.45",
            max_group_share,
            max_group_share <= 0.45,
            "training-event concentration",
        )
        if "target_class" not in train.columns:
            _record(
                f"fold_{fold_id}_both_target_classes",
                "exactly {0, 1}",
                "unavailable",
                False,
                "target_class is required before fitting",
            )
        else:
            classes = sorted(
                pd.to_numeric(train["target_class"], errors="coerce").dropna().astype(int).unique()
            )
            _record(
                f"fold_{fold_id}_both_target_classes",
                "exactly {0, 1}",
                classes,
                classes == [0, 1],
                "training-label support",
            )

    failures = tuple(
        f"{check['metric']}: observed {check['observed_value']!r}, required {check['threshold']}"
        for check in checks
        if not bool(check["passed"])
    )
    passed = not failures
    return MatbSampleGateResult(
        passed=passed,
        fit_permitted=passed,
        checks=tuple(checks),
        failure_reasons=failures,
    )


def initialize_blocked_matb_predictions(
    asset_frames: Mapping[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Emit a fail-closed prediction surface when the sample gate blocks fitting."""
    out: dict[str, pd.DataFrame] = {}
    for asset, frame in sorted(asset_frames.items()):
        resolved = frame.copy()
        resolved["matb_pred_success_prob"] = np.nan
        resolved["matb_pred_ev_r"] = np.nan
        resolved["matb_pred_is_oos"] = np.int8(0)
        out[str(asset)] = resolved
    return out


__all__ = [
    "MatbSampleGateResult",
    "build_matb_walk_forward_folds",
    "evaluate_matb_sample_gate",
    "initialize_blocked_matb_predictions",
    "purge_matb_event_overlap",
    "sort_matb_event_table",
]
