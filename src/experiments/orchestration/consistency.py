from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult
from src.portfolio import PortfolioPerformance


_BASELINE_METRIC_KEYS = (
    "cumulative_return",
    "annualized_return",
    "annualized_vol",
    "sharpe",
    "sortino",
    "calmar",
    "conventional_sharpe",
    "return_over_vol_sharpe",
    "max_drawdown",
    "profit_factor",
    "bar_return_profit_factor",
    "hit_rate",
    "gross_pnl",
    "net_pnl",
    "total_cost",
    "gross_return_sum",
    "net_return_sum",
    "cost_return_sum",
    "avg_turnover",
    "total_turnover",
    "metric_scope",
    "profit_factor_scope",
    "annualization_mode",
)
_SCOPE_KEYS = ("evaluation_scope", "evaluation_start", "evaluation_end", "evaluation_rows")


def evaluation_row_index_sha256(mask: pd.Series) -> str:
    selected = mask.fillna(False).astype(bool)
    values = [str(value) for value in selected.index[selected]]
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _same_value(left: Any, right: Any, *, rtol: float = 1e-12, atol: float = 1e-14) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float, np.number)) and isinstance(right, (int, float, np.number)):
        left_float = float(left)
        right_float = float(right)
        if math.isnan(left_float) or math.isnan(right_float):
            return math.isnan(left_float) and math.isnan(right_float)
        if math.isinf(left_float) or math.isinf(right_float):
            return left_float == right_float
        return bool(np.isclose(left_float, right_float, rtol=rtol, atol=atol))
    return left == right


def _assert_mapping_fields_equal(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    keys: tuple[str, ...],
    label: str,
) -> None:
    mismatches = [
        key
        for key in keys
        if key not in left or key not in right or not _same_value(left.get(key), right.get(key))
    ]
    if mismatches:
        details = {key: {"left": left.get(key), "right": right.get(key)} for key in mismatches}
        raise RuntimeError(f"Run consistency check failed for {label}: {details}")


def apply_final_trade_accounting(
    evaluation: dict[str, Any],
    *,
    trade_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge ledger metrics once without ever changing a generic bar-return metric."""
    updated = dict(evaluation)
    for section_name in ("primary_summary", "timeline_summary", "oos_only_summary", "mark_to_market_summary"):
        if not isinstance(updated.get(section_name), dict):
            continue
        section = dict(updated[section_name])
        generic_pf = section.get("profit_factor", section.get("bar_return_profit_factor", 0.0))
        section.update(dict(trade_metrics))
        section["profit_factor"] = generic_pf
        section["bar_return_profit_factor"] = generic_pf
        section["profit_factor_scope"] = "bar_returns"
        section["bar_return_profit_factor_scope"] = "bar_returns"
        section["trade_return_profit_factor_scope"] = "completed_trade_net_returns"
        section["trade_r_profit_factor_scope"] = "completed_trade_net_r_multiples"
        section["trade_profit_factor_scope"] = "completed_trade_net_returns"
        updated[section_name] = section

    trade_diagnostics = dict(updated.get("trade_diagnostics", {}) or {})
    trade_diagnostics.update(dict(trade_metrics))
    updated["trade_diagnostics"] = trade_diagnostics
    return updated


def apply_evaluation_scope_metadata(
    evaluation: dict[str, Any],
    *,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    updated = dict(evaluation)
    updated.update(dict(metadata))
    if metadata.get("evaluation_scope") is not None:
        updated["scope"] = str(metadata["evaluation_scope"])
    for section_name in ("primary_summary", "oos_only_summary", "mark_to_market_summary"):
        if isinstance(updated.get(section_name), dict):
            section = dict(updated[section_name])
            section.update(dict(metadata))
            updated[section_name] = section
    return updated


def assert_run_consistency(
    *,
    evaluation: dict[str, Any],
    performance: BacktestResult | PortfolioPerformance,
    evaluation_mask: pd.Series,
    trade_metrics: Mapping[str, Any],
) -> None:
    primary = dict(evaluation.get("primary_summary", {}) or {})
    expected_scope_rows = int(evaluation_mask.fillna(False).astype(bool).sum())
    if int(primary.get("evaluation_rows", -1)) != expected_scope_rows:
        raise RuntimeError("Run consistency check failed: primary evaluation_rows does not match the canonical scope mask.")
    if str(primary.get("evaluation_scope")) != str(evaluation.get("evaluation_scope")):
        raise RuntimeError("Run consistency check failed: primary and evaluation scope labels differ.")
    if str(evaluation.get("scope")) != str(evaluation.get("evaluation_scope")):
        raise RuntimeError("Run consistency check failed: legacy scope and evaluation_scope differ.")

    for section_name in ("primary_summary", "oos_only_summary", "mark_to_market_summary"):
        section = evaluation.get(section_name)
        if not isinstance(section, dict):
            continue
        _assert_mapping_fields_equal(primary, section, keys=_SCOPE_KEYS, label=f"{section_name} evaluation scope")
        if not _same_value(section.get("profit_factor"), section.get("bar_return_profit_factor")):
            raise RuntimeError(f"Run consistency check failed: {section_name}.profit_factor changed away from bar-return scope.")
        if section.get("profit_factor_scope") != "bar_returns":
            raise RuntimeError(f"Run consistency check failed: {section_name}.profit_factor_scope is not bar_returns.")

    trades = getattr(performance, "trades", None)
    ledger_rows = int(len(trades)) if isinstance(trades, pd.DataFrame) else 0
    if int(trade_metrics.get("completed_trade_count", -1)) != ledger_rows:
        raise RuntimeError("Run consistency check failed: completed trade count differs from canonical ledger rows.")
    ledger_cost = 0.0
    if isinstance(trades, pd.DataFrame) and not trades.empty and "cost_return" in trades.columns:
        ledger_cost = float(pd.to_numeric(trades["cost_return"], errors="coerce").fillna(0.0).sum())
    if not _same_value(ledger_cost, trade_metrics.get("total_trade_cost", 0.0)):
        raise RuntimeError("Run consistency check failed: total trade costs differ from the canonical ledger sum.")

    robustness = dict(evaluation.get("robustness", {}) or {})
    cost_x1 = dict(dict(robustness.get("cost_stress", {}) or {}).get("cost_x1", {}) or {})
    if robustness and not cost_x1:
        raise RuntimeError("Run consistency check failed: enabled robustness is missing cost_x1 baseline.")
    if cost_x1:
        _assert_mapping_fields_equal(primary, cost_x1, keys=_BASELINE_METRIC_KEYS, label="cost_x1 versus primary baseline")
        _assert_mapping_fields_equal(primary, cost_x1, keys=_SCOPE_KEYS, label="cost_x1 evaluation scope")
    for section_name in ("mark_to_market",):
        section = robustness.get(section_name)
        if isinstance(section, dict):
            _assert_mapping_fields_equal(primary, section, keys=_SCOPE_KEYS, label=f"robustness.{section_name} scope")
    for scenario in dict(robustness.get("entry_delay", {}) or {}).values():
        if isinstance(scenario, dict) and "error" not in scenario:
            _assert_mapping_fields_equal(primary, scenario, keys=_SCOPE_KEYS, label="entry-delay scope")

    if primary.get("evaluation_scope") == "strict_oos_only":
        evaluation["oos_summary_non_oos_rows"] = 0
    evaluation["evaluation_row_index_sha256"] = evaluation_row_index_sha256(evaluation_mask)


def assert_saved_primary_summary(*, summary_path: str | Path, evaluation: Mapping[str, Any]) -> None:
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    saved = dict(payload.get("summary", {}) or {})
    saved_primary = dict(dict(payload.get("evaluation", {}) or {}).get("primary_summary", {}) or {})
    in_memory = dict(evaluation.get("primary_summary", {}) or {})
    if saved != saved_primary or saved != in_memory:
        raise RuntimeError("Run consistency check failed: CLI/in-memory primary summary differs from saved summary.json.")


__all__ = [
    "apply_evaluation_scope_metadata",
    "apply_final_trade_accounting",
    "assert_run_consistency",
    "assert_saved_primary_summary",
    "evaluation_row_index_sha256",
]
