from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any

import numpy as np
import pandas as pd


def _timestamp(value: Any, *, field: str) -> pd.Timestamp:
    try:
        result = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must contain valid timestamps.") from exc
    if pd.isna(result):
        raise ValueError(f"{field} must not contain NaT.")
    return result


def _group_key(values: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(("__nan__" if pd.isna(value) else value) for value in values)


class CompletedTradeHistoryState:
    """Stateful, event-time completed-trade feature calculator.

    Updates may arrive in any order: ``features_at`` sorts by completion time
    and admits only completions strictly before the query by default. Thus an
    overlapping or not-yet-completed trade cannot leak into a candidate.
    """

    def __init__(self, *, rolling_window: int = 20, win_threshold: float = 0.0,
                 allow_same_timestamp: bool = False) -> None:
        if isinstance(rolling_window, bool) or not isinstance(rolling_window, int) or rolling_window <= 0:
            raise ValueError("rolling_window must be a positive integer.")
        if isinstance(win_threshold, bool) or not isinstance(win_threshold, Real) or not np.isfinite(float(win_threshold)):
            raise ValueError("win_threshold must be finite.")
        if not isinstance(allow_same_timestamp, bool):
            raise ValueError("allow_same_timestamp must be boolean.")
        self.rolling_window = rolling_window
        self.win_threshold = float(win_threshold)
        self.allow_same_timestamp = allow_same_timestamp
        self._events: dict[tuple[Any, ...], list[tuple[pd.Timestamp, int, float]]] = defaultdict(list)
        self._sequence = 0

    def update_completed_trade(self, completion_time: Any, outcome: float,
                               *, group: Sequence[Any] | Any | None = None) -> None:
        """Record one completed trade for subsequent event-time queries."""
        if isinstance(outcome, bool) or not isinstance(outcome, Real) or not np.isfinite(float(outcome)):
            raise ValueError("outcome must be a finite number.")
        values = () if group is None else (tuple(group) if isinstance(group, (list, tuple)) else (group,))
        self._events[_group_key(values)].append(
            (_timestamp(completion_time, field="completion_time"), self._sequence, float(outcome))
        )
        self._sequence += 1

    def features_at(self, candidate_time: Any, *, group: Sequence[Any] | Any | None = None) -> dict[str, np.float32]:
        """Return rolling and expanding statistics visible at candidate time."""
        when = _timestamp(candidate_time, field="candidate_time")
        values = () if group is None else (tuple(group) if isinstance(group, (list, tuple)) else (group,))
        events = sorted(self._events.get(_group_key(values), ()), key=lambda item: (item[0], item[1]))
        visible = [
            outcome for completed, _, outcome in events
            if completed <= when if self.allow_same_timestamp
        ] if self.allow_same_timestamp else [
            outcome for completed, _, outcome in events if completed < when
        ]
        if not visible:
            nan = np.float32(np.nan)
            return {"past_win20": nan, "past_mean20": nan, "past_mean_all": nan, "past_win_all": nan}
        all_values = np.asarray(visible, dtype=float)
        recent = all_values[-self.rolling_window:]
        return {
            "past_win20": np.float32(np.mean(recent > self.win_threshold)),
            "past_mean20": np.float32(np.mean(recent)),
            "past_mean_all": np.float32(np.mean(all_values)),
            "past_win_all": np.float32(np.mean(all_values > self.win_threshold)),
        }


def add_completed_trade_history_features(
    candidates: pd.DataFrame, completed_trades: pd.DataFrame | None = None, *,
    candidate_time_col: str, completion_time_col: str, outcome_col: str,
    group_cols: Sequence[str] | None = None, rolling_window: int = 20,
    win_threshold: float = 0.0, allow_same_timestamp: bool = False,
    output_win_window_col: str = "past_win20", output_mean_window_col: str = "past_mean20",
    output_mean_all_col: str = "past_mean_all", output_win_all_col: str = "past_win_all",
) -> pd.DataFrame:
    """Add strictly causal completed-trade history to candidate rows.

    The trade source defaults to ``candidates``. Trades are ordered stably by
    completion timestamp within each configured group. The candidate index and
    original row order are preserved. With the default boundary, a completion
    at exactly t is unavailable to the candidate at t. With no visible history,
    all four float32 outputs are NaN.
    """
    trades = candidates if completed_trades is None else completed_trades
    groups = tuple(group_cols or ())
    required_candidates = [candidate_time_col, *groups]
    required_trades = [completion_time_col, outcome_col, *groups]
    for owner, frame, columns in (("candidates", candidates, required_candidates),
                                  ("completed_trades", trades, required_trades)):
        missing = [column for column in columns if column not in frame.columns]
        if missing:
            raise KeyError(f"Missing required columns in {owner}: {missing}")
    outputs = (output_win_window_col, output_mean_window_col, output_mean_all_col, output_win_all_col)
    if any(not isinstance(name, str) or not name.strip() for name in outputs) or len(set(outputs)) != 4:
        raise ValueError("output column names must be four distinct non-empty strings.")
    state = CompletedTradeHistoryState(rolling_window=rolling_window, win_threshold=win_threshold,
                                       allow_same_timestamp=allow_same_timestamp)
    ordered = trades.assign(__order=np.arange(len(trades))).sort_values(
        [completion_time_col, "__order"], kind="stable")
    for _, trade in ordered.iterrows():
        state.update_completed_trade(trade[completion_time_col], trade[outcome_col],
                                     group=tuple(trade[col] for col in groups))
    records: list[dict[str, np.float32]] = []
    for _, candidate in candidates.iterrows():
        records.append(state.features_at(candidate[candidate_time_col],
                                         group=tuple(candidate[col] for col in groups)))
    out = candidates.copy()
    canonical = ("past_win20", "past_mean20", "past_mean_all", "past_win_all")
    for canonical_name, output_name in zip(canonical, outputs):
        out[output_name] = pd.Series([row[canonical_name] for row in records], index=out.index, dtype="float32")
    return out


__all__ = ["CompletedTradeHistoryState", "add_completed_trade_history_features"]
