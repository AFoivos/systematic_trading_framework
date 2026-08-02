from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.backtesting.btcusd_dual_trend_ftmo import (
    BTCUSDDualTrendBacktestResult,
    run_btcusd_dual_trend_backtest,
)
from src.evaluation.btcusd_dual_trend_ftmo import flatten_ftmo_result, simulate_ftmo_two_step
from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.features.btcusd_dual_trend_ftmo import (
    aggregate_btcusd_1m_to_30m,
    feature_output_mapping,
    validate_btcusd_1m_data,
)
from src.utils.run_metadata import (
    build_run_metadata,
    compute_config_hash,
    compute_dataframe_fingerprint,
    file_sha256,
)


PERIODS_PER_YEAR = 365 * 48
REFERENCE_DIR = Path("/mnt/data/btcusd_dual_trend_ftmo_alpha")
REQUIRED_ARTIFACTS = (
    "summary.json",
    "report.md",
    "development_equity.csv",
    "legacy_holdout_equity.csv",
    "combined_equity.csv",
    "development_trades.csv",
    "legacy_holdout_trades.csv",
    "combined_trades.csv",
    "ftmo_rolling_starts.csv",
    "ftmo_cost_stress.csv",
    "parameter_neighborhood.csv",
    "combined_equity_curve.png",
    "drawdown_curve.png",
    "monthly_returns.png",
    "ftmo_completion_days.png",
    "parity_report.md",
    "resolved_config.yaml",
    "run_metadata.json",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(float(value)) else None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False, default=str),
        encoding="utf-8",
    )


def _nested(cfg: dict[str, Any], dotted: str) -> Any:
    value: Any = cfg
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"Locked BTCUSD config is missing '{dotted}'.")
        value = value[part]
    return value


def _normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    return value


def _validate_locked_config(cfg: dict[str, Any]) -> None:
    """Keep the supplied YAML authoritative and reject all execution-bearing drift."""
    exact = {
        "pipeline.kind": "btcusd_dual_trend_ftmo_v1",
        "strategy.name": "btcusd_dual_trend_ensemble_ftmo_22_16",
        "strategy.version": "v1",
        "strategy.symbol": "BTCUSD",
        "strategy.source_timeframe": "1m",
        "strategy.execution_timeframe": "30m",
        "data.source": "dukascopy_csv",
        "data.interval": "1m",
        "data.symbol": "BTCUSD",
        "data.pit.timestamp_alignment.source_timezone": "UTC",
        "data.pit.timestamp_alignment.output_timezone": "UTC",
        "data.pit.timestamp_alignment.normalize_daily": False,
        "data.pit.timestamp_alignment.duplicate_policy": "raise",
        "data.pit.corporate_actions.policy": "none",
        "data.storage.mode": "cached_only",
        "data.storage.load_path": "data/raw/dukascopy_30m_clean/btcusd_1m.csv",
        "data.storage.save_raw": False,
        "data.storage.save_processed": True,
        "data.storage.raw_dir": "data/raw",
        "data.storage.processed_dir": "data/processed",
        "aggregation.timeframe": "30min",
        "aggregation.label": "right",
        "aggregation.closed": "right",
        "aggregation.open_aggregation": "first",
        "aggregation.high_aggregation": "max",
        "aggregation.low_aggregation": "min",
        "aggregation.close_aggregation": "last",
        "aggregation.volume_aggregation": "sum",
        "aggregation.empty_bin_policy": "drop",
        "model.kind": "none",
        "signals.kind": "btcusd_dual_trend_ensemble",
        "signals.params.target_volatility": 0.22,
        "signals.params.max_leverage": 1.50,
        "signals.params.rebalance_bars": 48,
        "signals.params.allow_short": True,
        "signals.params.signal_col": "signal_position",
        "target.kind": "none",
        "risk.target_vol": None,
        "risk.max_leverage": 1.50,
        "risk.cost_per_turnover": 0.0004,
        "risk.slippage_per_turnover": 0.0,
        "risk.dd_guard.enabled": False,
        "risk.sizing.kind": "none",
        "backtest.engine": "btcusd_dual_trend_ftmo",
        "backtest.signal_col": "signal_position",
        "backtest.returns_col": "dual_execution_return",
        "backtest.returns_type": "simple",
        "backtest.periods_per_year": 17_520,
        "backtest.annualization_mode": "fixed_periods",
        "backtest.allow_short": True,
        "backtest.rebalance_bars": 48,
        "backtest.liquidate_at_end": True,
        "backtest.missing_return_policy": "raise_if_exposed",
        "ftmo.rules_web_verified": False,
        "ftmo.daily_timezone": "UTC",
        "ftmo.phase1.profit_target": 0.10,
        "ftmo.phase1.target_volatility": 0.22,
        "ftmo.phase1.max_leverage": 1.50,
        "ftmo.phase2.profit_target": 0.05,
        "ftmo.phase2.target_volatility": 0.16,
        "ftmo.phase2.max_leverage": 1.20,
        "ftmo.maximum_daily_loss": 0.05,
        "ftmo.maximum_total_loss": 0.10,
        "ftmo.minimum_trading_days_per_phase": 4,
        "ftmo.time_limit_days": None,
        "ftmo.rolling_start.frequency": "7D",
        "ftmo.intrabar_check": "next_30m_high_low",
        "evaluation.legacy_holdout.pristine": False,
        "runtime.seed": 7,
        "runtime.deterministic": True,
        "runtime.threads": 1,
        "validation.pit_hardening": True,
        "validation.data_quality_audit": True,
        "validation.target_backtest_parity_required": True,
        "validation.causality_tests_required": True,
        "logging.enabled": True,
        "logging.run_name": "btcusd_1m_dual_trend_ftmo_22_16_v1",
        "logging.output_dir": "logs/experiments/btcusd_dual_trend_ftmo",
    }
    for field, expected in exact.items():
        actual = _nested(cfg, field)
        if _normalized(actual) != _normalized(expected):
            raise ValueError(
                f"Locked BTCUSD strategy config mismatch at {field}: "
                f"expected {expected!r}, found {actual!r}."
            )

    feature_steps = list(cfg.get("features", []) or [])
    if len(feature_steps) != 1 or feature_steps[0].get("step") != "btcusd_dual_trend_30m":
        raise ValueError("BTCUSD Dual-Trend v1 requires exactly one btcusd_dual_trend_30m feature step.")
    expected_feature_params = {
        "open_col": "open",
        "high_col": "high",
        "low_col": "low",
        "close_col": "close",
        "volume_col": "volume",
        "ema_fast_span": 96,
        "ema_slow_span": 672,
        "donchian_window": 336,
        "volatility_ewma_span": 336,
        "periods_per_year": 17_520,
        "ema_weight": 0.60,
        "donchian_weight": 0.40,
        "execution_return_mode": "next_open_to_next_open",
        "adverse_excursion_mode": "next_30m_high_low",
    }
    if dict(feature_steps[0].get("params", {}) or {}) != expected_feature_params:
        raise ValueError("BTCUSD feature parameters do not match the locked v1 contract.")
    feature_output_mapping(feature_steps[0])

    expected_signal_params = {
        "ensemble_col": "dual_trend_score",
        "volatility_col": "dual_volatility_ann_336",
        "target_volatility": 0.22,
        "max_leverage": 1.50,
        "rebalance_bars": 48,
        "allow_short": True,
        "signal_col": "signal_position",
    }
    if dict(_nested(cfg, "signals.params")) != expected_signal_params:
        raise ValueError("BTCUSD signal parameters do not match the locked v1 contract.")

    expected_periods = {
        "evaluation.development.start": "2026-01-01",
        "evaluation.development.end_exclusive": "2026-06-01",
        "evaluation.legacy_holdout.start": "2026-06-01",
        "evaluation.legacy_holdout.end_exclusive": "2026-07-28",
        "evaluation.combined.start": "2026-01-01",
        "evaluation.combined.end_exclusive": "2026-07-28",
        "ftmo.rolling_start.start": "2026-01-05",
        "ftmo.rolling_start.end": "2026-04-13",
        "ftmo.evaluation_end_exclusive": "2026-07-28",
    }
    for field, expected in expected_periods.items():
        actual = _nested(cfg, field)
        if str(actual) != expected:
            raise ValueError(f"Locked BTCUSD date mismatch at {field}: {actual!r}.")
    if list(_nested(cfg, "evaluation.cost_stress_bps")) != [0, 8, 12, 16, 20]:
        raise ValueError("BTCUSD cost stress grid must remain [0, 8, 12, 16, 20].")
    neighborhood = dict(_nested(cfg, "evaluation.parameter_neighborhood"))
    if neighborhood != {
        "ema_weights": [0.50, 0.60, 0.75],
        "volatility_spans": [192, 336],
        "target_volatilities": [0.20, 0.22],
    }:
        raise ValueError("BTCUSD parameter neighborhood must remain the declared diagnostic grid.")


def _read_source(cfg: dict[str, Any]) -> tuple[pd.DataFrame, Path]:
    path = Path(str(_nested(cfg, "data.storage.load_path")))
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Locked BTCUSD source dataset not found: {path}.")
    raw = pd.read_csv(path)
    if "timestamp" not in raw.columns:
        raise ValueError("BTCUSD source CSV must contain a timestamp column.")
    raw = raw.set_index("timestamp", drop=True)
    normalized = validate_btcusd_1m_data(
        raw,
        source_timezone=str(_nested(cfg, "data.pit.timestamp_alignment.source_timezone")),
        output_timezone=str(_nested(cfg, "data.pit.timestamp_alignment.output_timezone")),
    )
    return normalized, path


def _timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def _period_frame(frame: pd.DataFrame, cfg: dict[str, Any], period: str) -> pd.DataFrame:
    period_cfg = dict(_nested(cfg, f"evaluation.{period}"))
    start = _timestamp(period_cfg["start"])
    end = _timestamp(period_cfg["end_exclusive"])
    return frame.loc[(frame.index >= start) & (frame.index < end)].copy()


def _validate_evaluation_coverage(bars_30m: pd.DataFrame, cfg: dict[str, Any]) -> None:
    """Fail before accounting when the locked intervals cannot be evaluated completely."""
    if bars_30m.empty:
        raise ValueError("BTCUSD aggregation produced no non-empty 30m bars.")
    evaluation_start = _timestamp(_nested(cfg, "evaluation.combined.start"))
    evaluation_end = _timestamp(_nested(cfg, "evaluation.combined.end_exclusive"))
    warmup_start_required = evaluation_start - pd.Timedelta(minutes=30 * 672)
    # The last decision bar before end_exclusive needs open.shift(-1) and
    # open.shift(-2), so a right-labeled bar through end + 30 minutes is needed.
    outcome_end_required = evaluation_end + pd.Timedelta(minutes=30)
    actual_start = pd.Timestamp(bars_30m.index.min())
    actual_end = pd.Timestamp(bars_30m.index.max())
    if actual_start > warmup_start_required or actual_end < outcome_end_required:
        raise ValueError(
            "BTCUSD source coverage is insufficient for the locked evaluation intervals: "
            f"aggregated coverage is [{actual_start.isoformat()}, {actual_end.isoformat()}], "
            f"but causal warmup/outcome coverage must span at least "
            f"[{warmup_start_required.isoformat()}, {outcome_end_required.isoformat()}]. "
            "No partial-period metrics or synthetic bars were produced."
        )


def _run_period(
    feature_frame: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    period: str,
    cost_per_turnover: float | None = None,
    signals_cfg: dict[str, Any] | None = None,
    scope: str | None = None,
) -> BTCUSDDualTrendBacktestResult:
    subset = _period_frame(feature_frame, cfg, period)
    positioned = apply_signal_step(subset, signals_cfg or dict(cfg["signals"]))
    return run_btcusd_dual_trend_backtest(
        positioned,
        signal_col=str(_nested(cfg, "backtest.signal_col")),
        returns_col=str(_nested(cfg, "backtest.returns_col")),
        cost_per_turnover=(
            float(_nested(cfg, "risk.cost_per_turnover"))
            if cost_per_turnover is None
            else float(cost_per_turnover)
        ),
        periods_per_year=int(_nested(cfg, "backtest.periods_per_year")),
        liquidate_at_end=bool(_nested(cfg, "backtest.liquidate_at_end")),
        missing_return_policy=str(_nested(cfg, "backtest.missing_return_policy")),
        evaluation_scope=scope or period,
    )


def _ftmo_kwargs(cfg: dict[str, Any], *, cost_per_turnover: float) -> dict[str, Any]:
    return {
        "end_exclusive": _nested(cfg, "ftmo.evaluation_end_exclusive"),
        "phase1_profit_target": float(_nested(cfg, "ftmo.phase1.profit_target")),
        "phase1_target_volatility": float(_nested(cfg, "ftmo.phase1.target_volatility")),
        "phase1_max_leverage": float(_nested(cfg, "ftmo.phase1.max_leverage")),
        "phase2_profit_target": float(_nested(cfg, "ftmo.phase2.profit_target")),
        "phase2_target_volatility": float(_nested(cfg, "ftmo.phase2.target_volatility")),
        "phase2_max_leverage": float(_nested(cfg, "ftmo.phase2.max_leverage")),
        "maximum_daily_loss": float(_nested(cfg, "ftmo.maximum_daily_loss")),
        "maximum_total_loss": float(_nested(cfg, "ftmo.maximum_total_loss")),
        "minimum_trading_days": int(_nested(cfg, "ftmo.minimum_trading_days_per_phase")),
        "cost_per_turnover": float(cost_per_turnover),
        "rebalance_bars": int(_nested(cfg, "backtest.rebalance_bars")),
    }


def _rolling_ftmo(
    feature_frame: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    cost_per_turnover: float,
) -> pd.DataFrame:
    starts = pd.date_range(
        str(_nested(cfg, "ftmo.rolling_start.start")),
        str(_nested(cfg, "ftmo.rolling_start.end")),
        freq=str(_nested(cfg, "ftmo.rolling_start.frequency")),
        tz="UTC",
    )
    rows = [
        flatten_ftmo_result(
            simulate_ftmo_two_step(
                feature_frame,
                start=start,
                **_ftmo_kwargs(cfg, cost_per_turnover=cost_per_turnover),
            )
        )
        for start in starts
    ]
    return pd.DataFrame(rows)


def _cost_stress(feature_frame: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for round_trip_bps in list(_nested(cfg, "evaluation.cost_stress_bps")):
        one_way = float(round_trip_bps) / 2.0 / 10_000.0
        combined = _run_period(
            feature_frame,
            cfg,
            period="combined",
            cost_per_turnover=one_way,
            scope=f"combined_cost_stress_{round_trip_bps}bps",
        )
        rolling = _rolling_ftmo(feature_frame, cfg, cost_per_turnover=one_way)
        passed = rolling.loc[rolling["status"].eq("passed")]
        rows.append(
            {
                "round_trip_cost_bps": int(round_trip_bps),
                "one_way_cost_per_turnover": one_way,
                "cumulative_return": combined.metrics["cumulative_return"],
                "sharpe": combined.metrics["sharpe"],
                "max_drawdown": combined.metrics["max_drawdown"],
                "total_cost": combined.metrics["total_cost"],
                "ftmo_start_count": int(len(rolling)),
                "ftmo_pass_count": int(len(passed)),
                "ftmo_fail_count": int(rolling["status"].str.startswith("failed").sum()),
                "ftmo_incomplete_count": int(rolling["status"].str.startswith("incomplete").sum()),
                "median_completion_days": (
                    float(passed["total_calendar_days"].median()) if len(passed) else None
                ),
                "maximum_completion_days": (
                    float(passed["total_calendar_days"].max()) if len(passed) else None
                ),
            }
        )
    return pd.DataFrame(rows)


def _parameter_neighborhood(
    bars_30m: pd.DataFrame,
    cfg: dict[str, Any],
) -> pd.DataFrame:
    neighborhood = dict(_nested(cfg, "evaluation.parameter_neighborhood"))
    baseline_step = dict(cfg["features"][0])
    rows: list[dict[str, Any]] = []
    for ema_weight in neighborhood["ema_weights"]:
        for volatility_span in neighborhood["volatility_spans"]:
            params = dict(baseline_step["params"])
            params["ema_weight"] = float(ema_weight)
            params["donchian_weight"] = float(1.0 - float(ema_weight))
            params["volatility_ewma_span"] = int(volatility_span)
            step = {**baseline_step, "params": params}
            outputs = dict(step["outputs"])
            outputs["volatility_ann"] = f"_diagnostic_volatility_ann_{volatility_span}"
            step["outputs"] = outputs
            features = apply_feature_steps(bars_30m, [step])
            for target_volatility in neighborhood["target_volatilities"]:
                signals_cfg = {
                    **dict(cfg["signals"]),
                    "params": {
                        **dict(cfg["signals"]["params"]),
                        "volatility_col": outputs["volatility_ann"],
                        "target_volatility": float(target_volatility),
                    },
                }
                result = _run_period(
                    features,
                    cfg,
                    period="combined",
                    signals_cfg=signals_cfg,
                    scope="parameter_neighborhood_diagnostic",
                )
                rows.append(
                    {
                        "ema_weight": float(ema_weight),
                        "donchian_weight": float(1.0 - float(ema_weight)),
                        "volatility_span": int(volatility_span),
                        "target_volatility": float(target_volatility),
                        "selected_baseline": bool(
                            float(ema_weight) == 0.60
                            and int(volatility_span) == 336
                            and float(target_volatility) == 0.22
                        ),
                        "cumulative_return": result.metrics["cumulative_return"],
                        "annualized_vol": result.metrics["annualized_vol"],
                        "sharpe": result.metrics["sharpe"],
                        "max_drawdown": result.metrics["max_drawdown"],
                        "total_turnover": result.metrics["total_turnover"],
                        "total_cost": result.metrics["total_cost"],
                    }
                )
    return pd.DataFrame(rows)


def _write_plots(
    output_dir: Path,
    combined: BTCUSDDualTrendBacktestResult,
    rolling: pd.DataFrame,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 5))
    combined.accounting["equity"].plot(color="#1565c0", linewidth=1.2)
    plt.title("BTCUSD Dual-Trend combined equity")
    plt.ylabel("Normalized equity")
    plt.tight_layout()
    plt.savefig(output_dir / "combined_equity_curve.png", dpi=150)
    plt.close()

    plt.figure(figsize=(10, 4))
    combined.accounting["drawdown"].plot(color="#b71c1c", linewidth=1.0)
    plt.axhline(0.0, color="black", linewidth=0.6)
    plt.title("BTCUSD Dual-Trend drawdown")
    plt.ylabel("Drawdown")
    plt.tight_layout()
    plt.savefig(output_dir / "drawdown_curve.png", dpi=150)
    plt.close()

    monthly = pd.Series(combined.metrics["monthly_returns"], dtype=float)
    plt.figure(figsize=(10, 4))
    colors = ["#2e7d32" if value >= 0.0 else "#c62828" for value in monthly]
    monthly.plot(kind="bar", color=colors)
    plt.title("BTCUSD Dual-Trend monthly returns")
    plt.ylabel("Return")
    plt.tight_layout()
    plt.savefig(output_dir / "monthly_returns.png", dpi=150)
    plt.close()

    completed = rolling.loc[rolling["status"].eq("passed")].copy()
    plt.figure(figsize=(10, 4))
    if len(completed):
        labels = pd.to_datetime(completed["start"], utc=True).dt.strftime("%Y-%m-%d")
        plt.bar(labels, completed["total_calendar_days"], color="#6a1b9a")
        plt.xticks(rotation=60, ha="right")
    else:
        plt.text(0.5, 0.5, "No completed rolling starts", ha="center", va="center")
        plt.xticks([])
    plt.title("FTMO completion days at 8 bps")
    plt.ylabel("Calendar days")
    plt.tight_layout()
    plt.savefig(output_dir / "ftmo_completion_days.png", dpi=150)
    plt.close()


def _first_parity_divergence(reference: pd.DataFrame, actual: pd.DataFrame) -> str | None:
    ref = reference.copy()
    act = actual.copy()
    for candidate in ("timestamp", "date", "datetime"):
        if candidate in ref.columns:
            ref[candidate] = pd.to_datetime(ref[candidate], utc=True)
            ref = ref.set_index(candidate)
            break
    if not isinstance(ref.index, pd.DatetimeIndex):
        try:
            ref.index = pd.to_datetime(ref.index, utc=True)
        except (TypeError, ValueError):
            return "Reference equity timestamp convention could not be parsed."
    if ref.index.tz is None:
        ref.index = ref.index.tz_localize("UTC")
    else:
        ref.index = ref.index.tz_convert("UTC")
    common_index = ref.index.intersection(act.index)
    categories = (
        ("features", ["dual_ema_fast_96", "dual_ema_slow_672", "dual_donchian_state", "dual_trend_score"]),
        ("signal", ["desired_position", "signal_position"]),
        ("position", ["position"]),
        ("turnover", ["turnover"]),
        ("cost", ["cost_return", "cost"]),
        ("equity", ["equity"]),
    )
    for category, columns in categories:
        for column in columns:
            if column not in ref.columns or column not in act.columns:
                continue
            left = pd.to_numeric(ref.loc[common_index, column], errors="coerce").to_numpy(dtype=float)
            right = pd.to_numeric(act.loc[common_index, column], errors="coerce").to_numpy(dtype=float)
            equal = np.isclose(left, right, rtol=1e-10, atol=1e-12, equal_nan=True)
            if not bool(equal.all()):
                first = common_index[int(np.flatnonzero(~equal)[0])]
                return f"First {category} divergence: `{column}` at `{first.isoformat()}`."
    if len(ref) != len(act):
        return f"Timestamp/row-count divergence: reference={len(ref)}, actual={len(act)}."
    return None


def _parity_report(
    summary: dict[str, Any],
    combined: pd.DataFrame,
    rolling: pd.DataFrame,
) -> tuple[str, str]:
    required = {
        "summary": REFERENCE_DIR / "summary.json",
        "combined_equity": REFERENCE_DIR / "combined_equity.csv",
        "ftmo_rolling_starts": REFERENCE_DIR / "ftmo_rolling_starts.csv",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        text = "\n".join(
            [
                "# BTCUSD Dual-Trend FTMO parity report",
                "",
                "> Status: reference artifacts missing; exact parity was not claimable.",
                "",
                "## Missing reference artifacts",
                "",
                *(f"- `{required[name]}`" for name in missing),
                "",
                "The implementation parameters were not changed or tuned to match expected metrics.",
                "",
            ]
        )
        return "reference_artifacts_missing", text

    reference_summary = json.loads(required["summary"].read_text(encoding="utf-8"))
    reference_combined = pd.read_csv(required["combined_equity"])
    reference_rolling = pd.read_csv(required["ftmo_rolling_starts"])
    divergence = _first_parity_divergence(reference_combined, combined)
    ref_metrics = dict(reference_summary.get("combined", reference_summary.get("metrics", reference_summary)))
    metric_differences: list[str] = []
    for key in ("cumulative_return", "sharpe", "max_drawdown"):
        if key in ref_metrics and key in summary:
            if not np.isclose(float(ref_metrics[key]), float(summary[key]), rtol=1e-10, atol=1e-12):
                metric_differences.append(
                    f"- `{key}`: reference={ref_metrics[key]!r}, actual={summary[key]!r}"
                )
    if len(reference_rolling) != len(rolling):
        metric_differences.append(
            f"- FTMO rolling row count: reference={len(reference_rolling)}, actual={len(rolling)}"
        )
    status = "exact_parity" if divergence is None and not metric_differences else "parity_mismatch"
    lines = [
        "# BTCUSD Dual-Trend FTMO parity report",
        "",
        f"> Status: {status}.",
        "",
        "## Comparison",
        "",
        *(metric_differences or ["- Selected summary metrics match within `rtol=1e-10`, `atol=1e-12`."]),
        f"- {divergence or 'No divergence found in common feature/signal/position/turnover/cost/equity columns.'}",
        "",
        "No parameters were optimized or changed to close a parity gap.",
        "",
    ]
    return status, "\n".join(lines)


def _report_markdown(summary: dict[str, Any]) -> str:
    development = summary["periods"]["development"]
    holdout = summary["periods"]["legacy_holdout_reused_not_pristine"]
    combined = summary["periods"]["combined"]
    ftmo = summary["ftmo_rolling"]
    return "\n".join(
        [
            "# BTCUSD Dual-Trend Ensemble FTMO 22/16 v1",
            "",
            "> Deterministic research implementation. This report does not claim production readiness.",
            "",
            "## Locked strategy",
            "",
            "- 60/40 log-close EMA and persistent prior-only Donchian ensemble.",
            "- 22% Phase 1 / 16% Phase 2 volatility targets.",
            "- Direction-change plus 48-exposed-bar scheduled rebalancing.",
            "- Baseline round-trip cost 8 bps (4 bps per unit turnover each way).",
            "",
            "## Backtest metrics",
            "",
            f"- Development: return `{development['cumulative_return']:.6f}`, Sharpe `{development['sharpe']:.4f}`, max drawdown `{development['max_drawdown']:.6f}`.",
            f"- Legacy holdout reused, not pristine: return `{holdout['cumulative_return']:.6f}`, Sharpe `{holdout['sharpe']:.4f}`, max drawdown `{holdout['max_drawdown']:.6f}`.",
            f"- Combined: return `{combined['cumulative_return']:.6f}`, Sharpe `{combined['sharpe']:.4f}`, max drawdown `{combined['max_drawdown']:.6f}`.",
            "",
            "## FTMO rolling research simulator",
            "",
            f"- Starts: `{ftmo['start_count']}`.",
            f"- Passed at 8 bps: `{ftmo['pass_count']}`.",
            f"- Median completion days: `{ftmo['median_completion_days']}`.",
            f"- Maximum completion days: `{ftmo['maximum_completion_days']}`.",
            "",
            "## Holdout status",
            "",
            "June–July 2026 is `legacy_holdout_reused_not_pristine`, not untouched OOS. New forward data is required.",
            "",
        ]
    )


def run_pipeline(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"BTCUSD config not found: {path}.")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(cfg, dict):
        raise TypeError("BTCUSD experiment config must be a mapping.")
    _validate_locked_config(cfg)

    source_1m, data_path = _read_source(cfg)
    bars_30m = aggregate_btcusd_1m_to_30m(source_1m)
    _validate_evaluation_coverage(bars_30m, cfg)
    feature_frame = apply_feature_steps(bars_30m, list(cfg["features"]))

    storage = dict(_nested(cfg, "data.storage"))
    if bool(storage["save_processed"]):
        processed_dir = Path(str(storage["processed_dir"])) / "btcusd_dual_trend_ftmo"
        processed_dir.mkdir(parents=True, exist_ok=True)
        bars_30m.to_csv(processed_dir / "btcusd_30m_v1.csv", index_label="timestamp")

    output_dir = Path(str(_nested(cfg, "logging.output_dir")))
    output_dir.mkdir(parents=True, exist_ok=True)
    development = _run_period(feature_frame, cfg, period="development", scope="development")
    legacy = _run_period(
        feature_frame,
        cfg,
        period="legacy_holdout",
        scope="legacy_holdout_reused_not_pristine",
    )
    combined = _run_period(feature_frame, cfg, period="combined", scope="combined")
    rolling = _rolling_ftmo(
        feature_frame,
        cfg,
        cost_per_turnover=float(_nested(cfg, "risk.cost_per_turnover")),
    )
    passed = rolling.loc[rolling["status"].eq("passed")]
    cost_stress = _cost_stress(feature_frame, cfg)
    neighborhood = _parameter_neighborhood(bars_30m, cfg)

    summary: dict[str, Any] = {
        **combined.metrics,
        "strategy_name": _nested(cfg, "strategy.name"),
        "strategy_version": _nested(cfg, "strategy.version"),
        "status": "completed",
        "periods": {
            "development": development.metrics,
            "legacy_holdout_reused_not_pristine": legacy.metrics,
            "combined": combined.metrics,
        },
        "model_overview": {
            "model_kind": "rule_based_dual_trend_ensemble",
            "n_folds": None,
            "train_rows": None,
            "test_pred_rows": None,
            "oos_rows": int(combined.metrics["evaluation_rows"]),
            "oos_prediction_coverage": 1.0,
            "pred_prob_col": None,
            "pred_is_oos_col": None,
        },
        "oos_classification": {"status": "not_applicable_no_classifier"},
        "prediction_diagnostics": {"status": "not_applicable_no_probabilistic_model"},
        "target_diagnostics": {
            "kind": "not_applicable_rule_based_strategy",
            "horizon_bars": None,
            "labeled_rows": None,
        },
        "ftmo_rolling": {
            "status": "completed_research_assumptions_not_web_verified",
            "start_count": int(len(rolling)),
            "pass_count": int(len(passed)),
            "failed_count": int(rolling["status"].str.startswith("failed").sum()),
            "incomplete_count": int(rolling["status"].str.startswith("incomplete").sum()),
            "median_completion_days": (
                float(passed["total_calendar_days"].median()) if len(passed) else None
            ),
            "maximum_completion_days": (
                float(passed["total_calendar_days"].max()) if len(passed) else None
            ),
        },
        "data_validation": {
            "source_rows": int(len(source_1m)),
            "aggregated_rows": int(len(bars_30m)),
            "source_start": source_1m.index.min().isoformat(),
            "source_end": source_1m.index.max().isoformat(),
            "aggregated_start": bars_30m.index.min().isoformat(),
            "aggregated_end": bars_30m.index.max().isoformat(),
            "timezone": "UTC",
            "duplicates": 0,
            "ohlc_forward_fill": False,
        },
        "selected_parameters": {
            "ema_weight": 0.60,
            "donchian_weight": 0.40,
            "volatility_span": 336,
            "phase1_target_volatility": 0.22,
            "phase2_target_volatility": 0.16,
            "baseline_round_trip_cost_bps": 8,
        },
    }

    development.accounting.to_csv(output_dir / "development_equity.csv", index_label="timestamp")
    legacy.accounting.to_csv(output_dir / "legacy_holdout_equity.csv", index_label="timestamp")
    combined.accounting.to_csv(output_dir / "combined_equity.csv", index_label="timestamp")
    development.trades.to_csv(output_dir / "development_trades.csv", index=False)
    legacy.trades.to_csv(output_dir / "legacy_holdout_trades.csv", index=False)
    combined.trades.to_csv(output_dir / "combined_trades.csv", index=False)
    rolling.to_csv(output_dir / "ftmo_rolling_starts.csv", index=False)
    cost_stress.to_csv(output_dir / "ftmo_cost_stress.csv", index=False)
    neighborhood.to_csv(output_dir / "parameter_neighborhood.csv", index=False)
    _write_plots(output_dir, combined, rolling)

    parity_status, parity_text = _parity_report(summary, combined.accounting, rolling)
    summary["parity"] = {
        "status": parity_status,
        "reference_directory": str(REFERENCE_DIR),
        "parameters_tuned_for_parity": False,
    }
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "report.md").write_text(_report_markdown(summary), encoding="utf-8")
    (output_dir / "parity_report.md").write_text(parity_text, encoding="utf-8")
    (output_dir / "resolved_config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    config_hash, config_hash_input = compute_config_hash(cfg)
    model_meta = {
        **summary["model_overview"],
        "oos_classification": summary["oos_classification"],
        "prediction_diagnostics": summary["prediction_diagnostics"],
        "target_diagnostics": summary["target_diagnostics"],
    }
    run_metadata = build_run_metadata(
        config_path=path,
        runtime_applied=dict(cfg["runtime"]),
        config_hash_sha256=config_hash,
        config_hash_input=config_hash_input,
        data_fingerprint=compute_dataframe_fingerprint(bars_30m),
        data_context={
            "source_path": str(data_path),
            "source_sha256": file_sha256(data_path),
            "aggregation": dict(cfg["aggregation"]),
        },
        model_meta=model_meta,
    )
    _write_json(output_dir / "run_metadata.json", run_metadata)

    missing_artifacts = [name for name in REQUIRED_ARTIFACTS if not (output_dir / name).is_file()]
    if missing_artifacts:
        raise RuntimeError(f"BTCUSD experiment failed to write artifacts: {missing_artifacts}.")
    return {
        "summary": _json_safe(summary),
        "output_dir": str(output_dir),
        "artifacts": list(REQUIRED_ARTIFACTS),
    }


__all__ = ["REQUIRED_ARTIFACTS", "run_pipeline"]
