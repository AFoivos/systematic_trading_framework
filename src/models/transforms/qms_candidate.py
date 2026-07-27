from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.signals.qms_alpha_strategy import (
    QMS_ALPHA_STRATEGIES,
    build_qms_alpha_strategy_signal,
    validate_qms_alpha_strategy_params,
)


_OUTPUT_PARAM_KEYS = frozenset(
    {
        "signal_col",
        "candidate_col",
        "state_col",
        "direction_col",
        "ready_col",
    }
)
_TRANSFORM_KEYS = frozenset(
    {
        "strategies",
        "common_params",
        "params_by_strategy",
        "candidate_col",
        "side_col",
        "source_count_col",
        "conflict_col",
        "ready_col",
        "origin_prefix",
    }
)


def _non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def validate_qms_candidate_transform_params(
    params: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate the deterministic QMS candidate-union model transform."""
    if params is not None and not isinstance(params, Mapping):
        raise TypeError("qms_candidate_transform params must be a mapping.")
    raw = dict(params or {})
    unknown = sorted(set(raw).difference(_TRANSFORM_KEYS))
    if unknown:
        raise ValueError(f"Unsupported qms_candidate_transform parameters: {unknown}.")

    strategies_raw = raw.get(
        "strategies",
        ["kds_pullback_continuation", "lmds_exhaustion_reversal"],
    )
    if not isinstance(strategies_raw, (list, tuple)) or not strategies_raw:
        raise ValueError("strategies must be a non-empty list.")
    strategies = [str(item) for item in strategies_raw]
    if len(set(strategies)) != len(strategies):
        raise ValueError("strategies must not contain duplicates.")
    unsupported = [item for item in strategies if item not in QMS_ALPHA_STRATEGIES]
    if unsupported:
        raise ValueError(
            f"Unsupported QMS strategies: {unsupported}; expected values from {list(QMS_ALPHA_STRATEGIES)}."
        )

    common = raw.get("common_params", {}) or {}
    by_strategy = raw.get("params_by_strategy", {}) or {}
    if not isinstance(common, Mapping):
        raise TypeError("common_params must be a mapping.")
    if not isinstance(by_strategy, Mapping):
        raise TypeError("params_by_strategy must be a mapping.")
    unknown_strategy_blocks = sorted(set(by_strategy).difference(strategies))
    if unknown_strategy_blocks:
        raise ValueError(
            f"params_by_strategy contains entries not listed in strategies: {unknown_strategy_blocks}."
        )
    forbidden_common = sorted(set(common).intersection({"strategy", *_OUTPUT_PARAM_KEYS}))
    if forbidden_common:
        raise ValueError(f"common_params cannot override transform-owned keys: {forbidden_common}.")

    resolved_by_strategy: dict[str, dict[str, Any]] = {}
    for strategy in strategies:
        overrides = by_strategy.get(strategy, {}) or {}
        if not isinstance(overrides, Mapping):
            raise TypeError(f"params_by_strategy.{strategy} must be a mapping.")
        forbidden = sorted(set(overrides).intersection({"strategy", *_OUTPUT_PARAM_KEYS}))
        if forbidden:
            raise ValueError(
                f"params_by_strategy.{strategy} cannot override transform-owned keys: {forbidden}."
            )
        strategy_cfg = dict(common) | dict(overrides) | {"strategy": strategy}
        resolved_by_strategy[strategy] = validate_qms_alpha_strategy_params(strategy_cfg)

    output_defaults = {
        "candidate_col": "qms_meta_candidate",
        "side_col": "qms_meta_side",
        "source_count_col": "qms_meta_source_count",
        "conflict_col": "qms_meta_side_conflict",
        "ready_col": "qms_meta_threshold_ready",
        "origin_prefix": "qms_meta_origin",
    }
    outputs = {
        key: _non_empty_string(raw.get(key, default), field=key)
        for key, default in output_defaults.items()
    }
    return {
        "strategies": strategies,
        "strategy_params": resolved_by_strategy,
        **outputs,
    }


def apply_qms_candidate_transform(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None = None,
) -> tuple[pd.DataFrame, None, dict[str, Any]]:
    """Build a causal union of QMS entry candidates between model stages.

    YAML declaration::

        model_stages:
          - kind: qms_candidate_transform
            params:
              strategies: [kds_pullback_continuation, lmds_exhaustion_reversal]
              common_params: {lookback_bars: 4032, min_periods: 1008}
              candidate_col: qms_meta_candidate
              side_col: qms_meta_side

    Required input columns
    ----------------------
    Strategy-specific QMS columns:
        The causal KDS, RLVS, LMDS, and gap-diagnostic columns required by each
        configured QMS strategy.

    Parameters
    ----------
    strategies:
        Unique QMS hypotheses whose entry events form the candidate union.
    common_params, params_by_strategy:
        Validated parameters forwarded to the causal QMS signal builders.
    candidate_col, side_col, source_count_col, conflict_col, ready_col:
        Output column names. Opposite simultaneous sides are marked as a
        conflict and excluded from the candidate set.
    origin_prefix:
        Prefix for per-strategy candidate-origin flags.
    """
    del returns_col
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")
    cfg = validate_qms_candidate_transform_params(dict(model_cfg or {}).get("params"))
    out = df.copy()

    signed_entries: list[pd.Series] = []
    ready_flags: list[pd.Series] = []
    per_strategy_counts: dict[str, int] = {}
    origin_columns: dict[str, str] = {}
    for strategy in cfg["strategies"]:
        strategy_out, _ = build_qms_alpha_strategy_signal(
            out,
            cfg["strategy_params"][strategy],
        )
        signal_col = str(cfg["strategy_params"][strategy]["signal_col"])
        ready_col = str(cfg["strategy_params"][strategy]["ready_col"])
        entry = pd.to_numeric(strategy_out[signal_col], errors="coerce").fillna(0.0)
        entry = np.sign(entry).astype("int8")
        ready = strategy_out[ready_col].fillna(0.0).astype(bool)
        origin_col = f"{cfg['origin_prefix']}_{strategy}"
        out[origin_col] = entry.ne(0).astype("int8")
        origin_columns[strategy] = origin_col
        per_strategy_counts[strategy] = int(entry.ne(0).sum())
        signed_entries.append(entry)
        ready_flags.append(ready)

    entry_matrix = pd.concat(signed_entries, axis=1)
    positive = entry_matrix.gt(0).any(axis=1)
    negative = entry_matrix.lt(0).any(axis=1)
    conflict = positive & negative
    source_count = entry_matrix.ne(0).sum(axis=1).astype("int16")
    side = pd.Series(0, index=out.index, dtype="int8")
    side.loc[positive & ~negative] = 1
    side.loc[negative & ~positive] = -1
    candidate = source_count.gt(0) & ~conflict
    all_ready = pd.concat(ready_flags, axis=1).all(axis=1)

    out[str(cfg["candidate_col"])] = candidate.astype("int8")
    out[str(cfg["side_col"])] = side
    out[str(cfg["source_count_col"])] = source_count
    out[str(cfg["conflict_col"])] = conflict.astype("int8")
    out[str(cfg["ready_col"])] = all_ready.astype("int8")
    return out, None, {
        "model_kind": "qms_candidate_transform",
        "strategies": list(cfg["strategies"]),
        "candidate_col": str(cfg["candidate_col"]),
        "side_col": str(cfg["side_col"]),
        "source_count_col": str(cfg["source_count_col"]),
        "conflict_col": str(cfg["conflict_col"]),
        "ready_col": str(cfg["ready_col"]),
        "origin_columns": origin_columns,
        "candidate_rows": int(candidate.sum()),
        "conflict_rows": int(conflict.sum()),
        "per_strategy_candidate_rows": per_strategy_counts,
        "prediction_diagnostics": {
            "oos_rows": 0,
            "predicted_rows": 0,
            "non_oos_prediction_rows": 0,
            "missing_oos_prediction_rows": 0,
            "oos_prediction_coverage": 0.0,
            "alignment_ok": True,
        },
        "anti_leakage": {
            "fitted": False,
            "thresholds": "rolling_past_only_shift_1",
            "conflicting_sides_fail_closed": True,
        },
    }


__all__ = [
    "apply_qms_candidate_transform",
    "validate_qms_candidate_transform_params",
]
