from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.intraday import (
    default_normalize_daily,
    infer_periods_per_year,
    infer_volatility_annualization_factor,
)
from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path, in_project

_RUN_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def default_data_block(data: dict[str, Any]) -> dict[str, Any]:
    """
    Apply data-layer defaults, including intraday-safe PIT behavior.
    """
    data = dict(data) if data else {}
    interval = str(data.get("interval", "1d"))

    data.setdefault("source", "yahoo")
    data.setdefault("interval", interval)
    data.setdefault("start", None)
    data.setdefault("end", None)
    data.setdefault("alignment", "inner")

    pit = dict(data.get("pit", {}) or {})
    ts = dict(pit.get("timestamp_alignment", {}) or {})
    ts.setdefault("source_timezone", "UTC")
    ts.setdefault("output_timezone", "UTC")
    ts.setdefault("normalize_daily", default_normalize_daily(interval))
    ts.setdefault("duplicate_policy", "last")
    pit["timestamp_alignment"] = ts

    corp = dict(pit.get("corporate_actions", {}) or {})
    corp.setdefault("policy", "none")
    corp.setdefault("adj_close_col", "adj_close")
    pit["corporate_actions"] = corp

    snapshot = dict(pit.get("universe_snapshot", {}) or {})
    snapshot.setdefault("inactive_policy", "raise")
    pit["universe_snapshot"] = snapshot
    data["pit"] = pit

    storage = dict(data.get("storage", {}) or {})
    storage.setdefault("mode", "live")
    storage.setdefault("dataset_id", None)
    storage.setdefault("load_path", None)
    storage.setdefault("save_raw", False)
    storage.setdefault("save_processed", False)
    raw_dir = storage.get("raw_dir", "data/raw")
    processed_dir = storage.get("processed_dir", "data/processed")
    storage["raw_dir"] = str(in_project(raw_dir)) if isinstance(raw_dir, str) else str(raw_dir)
    storage["processed_dir"] = (
        str(in_project(processed_dir)) if isinstance(processed_dir, str) else str(processed_dir)
    )
    load_path = storage.get("load_path")
    if isinstance(load_path, str):
        storage["load_path"] = str(in_project(load_path))
    data["storage"] = storage
    return data


def default_feature_steps(
    features: list[dict[str, Any]],
    *,
    interval: str,
) -> list[dict[str, Any]]:
    """
    Apply feature-step defaults that depend on market frequency.
    """
    out: list[dict[str, Any]] = []
    for step in list(features or []):
        step_cfg = dict(step)
        params = dict(step_cfg.get("params", {}) or {})
        if step_cfg.get("step") == "volatility":
            params.setdefault(
                "annualization_factor",
                infer_volatility_annualization_factor(interval),
            )
        step_cfg["params"] = params
        out.append(step_cfg)
    return out


def default_risk_block(risk: dict[str, Any]) -> dict[str, Any]:
    risk = dict(risk) if risk else {}
    risk.setdefault("cost_per_turnover", 0.0)
    risk.setdefault("slippage_per_turnover", 0.0)
    risk.setdefault("target_vol", None)
    risk.setdefault("max_leverage", 3.0)
    dd = risk.get("dd_guard") or {}
    if not isinstance(dd, dict):
        raise ValueError("risk.dd_guard must be a mapping.")
    dd.setdefault("max_drawdown", 0.2)
    dd.setdefault("cooloff_bars", 20)
    risk["dd_guard"] = dd
    return risk


def default_backtest_block(
    backtest: dict[str, Any],
    *,
    interval: str,
) -> dict[str, Any]:
    backtest = dict(backtest) if backtest else {}
    backtest.setdefault("periods_per_year", infer_periods_per_year(interval))
    backtest.setdefault("returns_type", "simple")
    backtest.setdefault("missing_return_policy", "raise_if_exposed")
    return backtest


def default_portfolio_block(portfolio: dict[str, Any]) -> dict[str, Any]:
    portfolio = dict(portfolio) if portfolio else {}
    portfolio.setdefault("enabled", False)
    portfolio.setdefault("construction", "signal_weights")
    portfolio.setdefault("gross_target", 1.0)
    portfolio.setdefault("long_short", True)
    portfolio.setdefault("expected_return_col", None)
    portfolio.setdefault("covariance_window", 60)
    portfolio.setdefault("covariance_rebalance_step", 1)
    portfolio.setdefault("risk_aversion", 5.0)
    portfolio.setdefault("trade_aversion", 0.0)
    portfolio["constraints"] = dict(portfolio.get("constraints", {}) or {})
    portfolio["asset_groups"] = dict(portfolio.get("asset_groups", {}) or {})
    return portfolio


def default_monitoring_block(monitoring: dict[str, Any]) -> dict[str, Any]:
    monitoring = dict(monitoring) if monitoring else {}
    monitoring.setdefault("enabled", True)
    monitoring.setdefault("psi_threshold", 0.2)
    monitoring.setdefault("n_bins", 10)
    return monitoring


def default_execution_block(execution: dict[str, Any]) -> dict[str, Any]:
    execution = dict(execution) if execution else {}
    execution.setdefault("enabled", False)
    execution.setdefault("mode", "paper")
    execution.setdefault("capital", 1_000_000.0)
    execution.setdefault("price_col", "close")
    execution.setdefault("min_trade_notional", 0.0)
    execution["current_weights"] = dict(execution.get("current_weights", {}) or {})
    return execution


def _sanitize_run_name(value: str) -> str:
    safe = _RUN_NAME_RE.sub("_", str(value)).strip("._")
    if not safe:
        raise ValueError("logging.run_name is empty after sanitization.")
    return safe


def resolve_logging_block(logging_cfg: dict[str, Any], config_path: Path) -> dict[str, Any]:
    logging_cfg = dict(logging_cfg) if logging_cfg else {}
    logging_cfg.setdefault("enabled", True)
    logging_cfg["run_name"] = _sanitize_run_name(logging_cfg.get("run_name", Path(config_path).stem))
    out_dir = logging_cfg.get("output_dir", "logs/experiments")
    if not isinstance(out_dir, str):
        raise ValueError("logging.output_dir must be a string.")

    resolved_out_dir = Path(out_dir)
    if not resolved_out_dir.is_absolute():
        resolved_out_dir = (PROJECT_ROOT / resolved_out_dir).resolve()
    else:
        resolved_out_dir = resolved_out_dir.resolve()

    try:
        resolved_out_dir.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("logging.output_dir must stay inside the project root.") from exc

    logging_cfg["output_dir"] = str(enforce_safe_absolute_path(resolved_out_dir))
    return logging_cfg


def apply_top_level_defaults(cfg: dict[str, Any], *, config_path: Path) -> dict[str, Any]:
    """
    Apply all defaults to a partially specified experiment config.
    """
    out = dict(cfg)
    out["data"] = default_data_block(out.get("data", {}))
    interval = str(out["data"].get("interval", "1d"))
    out["features"] = default_feature_steps(list(out.get("features", []) or []), interval=interval)
    out["model"] = dict(out.get("model", {"kind": "none"}) or {"kind": "none"})
    out["signals"] = dict(out.get("signals", {"kind": "none", "params": {}}) or {"kind": "none", "params": {}})
    out["runtime"] = dict(out.get("runtime", {}) or {})
    out["risk"] = default_risk_block(out.get("risk", {}))
    out["backtest"] = default_backtest_block(out.get("backtest", {}), interval=interval)
    out["portfolio"] = default_portfolio_block(out.get("portfolio", {}))
    out["monitoring"] = default_monitoring_block(out.get("monitoring", {}))
    out["execution"] = default_execution_block(out.get("execution", {}))
    out["logging"] = resolve_logging_block(out.get("logging", {}), config_path)
    return out


__all__ = [
    "apply_top_level_defaults",
    "default_backtest_block",
    "default_data_block",
    "default_execution_block",
    "default_feature_steps",
    "default_monitoring_block",
    "default_portfolio_block",
    "default_risk_block",
    "resolve_logging_block",
]
