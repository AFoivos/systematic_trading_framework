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
_FIAT_CODES = {"AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NZD", "USD"}


def _looks_like_pair_symbol(symbol: str) -> tuple[str, str] | None:
    raw = str(symbol).strip().upper().replace("=X", "")
    for sep in ("/", "-"):
        if sep in raw:
            left, right = raw.split(sep, 1)
            if len(left) == 3 and len(right) == 3 and left.isalpha() and right.isalpha():
                return left, right
            return None
    if len(raw) == 6 and raw.isalpha():
        return raw[:3], raw[3:]
    return None


def _annualization_kwargs_for_data(data: dict[str, Any]) -> dict[str, float | int]:
    symbols = []
    if data.get("symbol") is not None:
        symbols = [str(data["symbol"])]
    elif data.get("symbols") is not None:
        symbols = [str(symbol) for symbol in list(data.get("symbols", []) or [])]

    pairs = [_looks_like_pair_symbol(symbol) for symbol in symbols]
    valid_pairs = [pair for pair in pairs if pair is not None]
    if valid_pairs and len(valid_pairs) == len(symbols):
        if all(left in _FIAT_CODES and right in _FIAT_CODES for left, right in valid_pairs):
            return {"trading_days_per_year": 252, "trading_hours_per_day": 24.0}
        if all(left not in _FIAT_CODES or right not in _FIAT_CODES for left, right in valid_pairs):
            return {"trading_days_per_year": 365, "trading_hours_per_day": 24.0}
    return {"trading_days_per_year": 252, "trading_hours_per_day": 6.5}


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
    storage.setdefault("load_paths", None)
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
    load_paths = storage.get("load_paths")
    if isinstance(load_paths, dict):
        storage["load_paths"] = {
            str(asset): str(in_project(path)) if isinstance(path, str) else path
            for asset, path in load_paths.items()
        }
    data["storage"] = storage
    return data


def default_feature_steps(
    features: list[dict[str, Any]],
    *,
    interval: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Apply feature-step defaults that depend on market frequency.
    """
    out: list[dict[str, Any]] = []
    annualization_kwargs = _annualization_kwargs_for_data(data)
    for step in list(features or []):
        step_cfg = dict(step)
        params = dict(step_cfg.get("params", {}) or {})
        if step_cfg.get("step") == "volatility":
            params.setdefault(
                "annualization_factor",
                infer_volatility_annualization_factor(interval, **annualization_kwargs),
            )
        step_cfg["params"] = params
        out.append(step_cfg)
    return out


def default_model_block(model: dict[str, Any]) -> dict[str, Any]:
    model = dict(model) if model else {}
    target = dict(model.get("target", {}) or {})
    if target:
        if str(target.get("kind", "forward_return")) == "forward_return":
            target.setdefault("returns_col", None)
            target.setdefault("returns_type", "simple")
        model["target"] = target
    kind = str(model.get("kind", "none"))
    if kind not in {"ppo_agent", "dqn_agent", "ppo_portfolio_agent", "dqn_portfolio_agent"}:
        return model

    env = dict(model.get("env", {}) or {})
    env.setdefault("window_size", 32)
    env.setdefault("execution_lag_bars", 1)
    env.setdefault("min_holding_bars", 0)
    env.setdefault("action_hysteresis", 0.0)
    if "max_signal_abs" not in env and "max_position" in env:
        env["max_signal_abs"] = env["max_position"]
    env.setdefault("max_signal_abs", 1.0)

    reward = dict(env.get("reward", {}) or {})
    reward.setdefault("cost_per_turnover", 0.0)
    reward.setdefault("slippage_per_turnover", 0.0)
    reward.setdefault("inventory_penalty", 0.0)
    reward.setdefault("drawdown_penalty", 0.0)
    reward.setdefault("switching_penalty", 0.0)
    env["reward"] = reward
    model["env"] = env
    return model


def _strip_model_stage_metadata(stage_cfg: dict[str, Any]) -> dict[str, Any]:
    out = dict(stage_cfg or {})
    out.pop("name", None)
    out.pop("stage", None)
    out.pop("enabled", None)
    return out


def default_model_stages_block(model_stages: Any) -> list[dict[str, Any]] | Any:
    if not isinstance(model_stages, list):
        return model_stages
    out: list[dict[str, Any]] = []
    for idx, raw_stage in enumerate(model_stages):
        if not isinstance(raw_stage, dict):
            out.append(raw_stage)
            continue
        stage_cfg = dict(raw_stage)
        stage_name = stage_cfg.get("name", f"stage_{idx + 1}")
        defaulted_stage = default_model_block(_strip_model_stage_metadata(stage_cfg))
        defaulted_stage["name"] = stage_name
        defaulted_stage["enabled"] = stage_cfg.get("enabled", True)
        defaulted_stage["stage"] = stage_cfg.get("stage", idx + 1)
        out.append(defaulted_stage)
    return out


def _enabled_model_stages(model_stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enabled_with_pos: list[tuple[int, dict[str, Any]]] = []
    for idx, raw_stage in enumerate(list(model_stages or [])):
        stage = dict(raw_stage)
        if stage.get("enabled", True) is False:
            continue
        enabled_with_pos.append((idx, stage))

    def _sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int, str]:
        idx, stage = item
        stage_value = stage.get("stage")
        if isinstance(stage_value, int) and not isinstance(stage_value, bool):
            return (0, int(stage_value), str(stage.get("name", "")))
        return (1, idx, str(stage.get("name", "")))

    enabled_with_pos.sort(key=_sort_key)
    return [stage for _, stage in enabled_with_pos]


def default_risk_block(risk: dict[str, Any]) -> dict[str, Any]:
    risk = dict(risk) if risk else {}
    risk.setdefault("cost_per_turnover", 0.0)
    risk.setdefault("slippage_per_turnover", 0.0)
    risk.setdefault("target_vol", None)
    risk.setdefault("max_leverage", 3.0)
    risk.setdefault("sizing", {})
    risk.setdefault("drawdown_sizing", {})
    dd = risk.get("dd_guard") or {}
    if not isinstance(dd, dict):
        raise ValueError("risk.dd_guard must be a mapping.")
    dd.setdefault("enabled", True)
    dd.setdefault("max_drawdown", 0.2)
    dd.setdefault("cooloff_bars", 20)
    dd.setdefault("rearm_drawdown", dd.get("max_drawdown", 0.2))
    risk["dd_guard"] = dd
    return risk


def default_backtest_block(
    backtest: dict[str, Any],
    *,
    interval: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    backtest = dict(backtest) if backtest else {}
    annualization_kwargs = _annualization_kwargs_for_data(data)
    backtest.setdefault("periods_per_year", infer_periods_per_year(interval, **annualization_kwargs))
    backtest.setdefault("returns_type", "simple")
    backtest.setdefault("missing_return_policy", "raise_if_exposed")
    backtest.setdefault("min_holding_bars", 0)
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
    portfolio["constraints"].setdefault("enforce_target_net_exposure", True)
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
    execution["current_prices"] = dict(execution.get("current_prices", {}) or {})
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
    stage_tails = dict(logging_cfg.get("stage_tails", {}) or {})
    stage_tails.setdefault("enabled", True)
    stage_tails.setdefault("stdout", True)
    stage_tails.setdefault("report", True)
    stage_tails.setdefault("limit", 10)
    stage_tails.setdefault("max_columns", 16)
    stage_tails.setdefault("max_assets", 3)
    logging_cfg["stage_tails"] = stage_tails
    return logging_cfg


def apply_top_level_defaults(cfg: dict[str, Any], *, config_path: Path) -> dict[str, Any]:
    """
    Apply all defaults to a partially specified experiment config.
    """
    out = dict(cfg)
    out["data"] = default_data_block(out.get("data", {}))
    interval = str(out["data"].get("interval", "1d"))
    out["features"] = default_feature_steps(
        list(out.get("features", []) or []),
        interval=interval,
        data=out["data"],
    )
    model_stages = out.get("model_stages")
    if model_stages is not None:
        out["model_stages"] = default_model_stages_block(model_stages)
    enabled_stages = (
        _enabled_model_stages(list(out.get("model_stages", []) or []))
        if isinstance(out.get("model_stages"), list)
        else []
    )
    if enabled_stages:
        final_stage = _strip_model_stage_metadata(dict(enabled_stages[-1]))
        out["model"] = default_model_block(final_stage)
    else:
        out["model"] = default_model_block(out.get("model", {"kind": "none"}) or {"kind": "none"})
    out["signals"] = dict(out.get("signals", {"kind": "none", "params": {}}) or {"kind": "none", "params": {}})
    out["runtime"] = dict(out.get("runtime", {}) or {})
    out["risk"] = default_risk_block(out.get("risk", {}))
    out["backtest"] = default_backtest_block(out.get("backtest", {}), interval=interval, data=out["data"])
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
    "default_model_block",
    "default_model_stages_block",
    "default_monitoring_block",
    "default_portfolio_block",
    "default_risk_block",
    "resolve_logging_block",
]
