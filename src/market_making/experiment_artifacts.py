from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

from src.utils.run_metadata import (
    build_artifact_manifest,
    build_run_metadata,
    compute_config_hash,
    compute_dataframe_fingerprint,
)


def write_market_making_experiment_artifacts(
    *,
    run_dir: str | Path,
    cfg: Mapping[str, Any],
    dataset: pd.DataFrame,
    predictions: pd.DataFrame,
    comparison: pd.DataFrame,
    model_meta: Mapping[str, Any],
    split_summary: Mapping[str, Any],
    source_paths: Mapping[str, str | Path],
    report_markdown: str | None = None,
) -> dict[str, str]:
    """Write JSON/CSV/Markdown/Parquet artifacts using the classic experiment layout."""
    out = Path(run_dir)
    out.mkdir(parents=True, exist_ok=True)
    cfg_dict = dict(cfg)
    config_hash, config_hash_input = compute_config_hash(cfg_dict)
    artifacts: dict[str, str] = {}

    config_path = out / "config_used.yaml"
    config_path.write_text(yaml.safe_dump(cfg_dict, sort_keys=False), encoding="utf-8")
    artifacts["config"] = str(config_path)

    dataset_path = out / "moment_dataset.parquet"
    dataset.to_parquet(dataset_path, index=False)
    artifacts["moment_dataset"] = str(dataset_path)

    predictions_path = out / "moment_predictions.csv"
    predictions.to_csv(predictions_path, index=False)
    artifacts["moment_predictions"] = str(predictions_path)

    comparison_path = out / "baseline_vs_moment.csv"
    comparison.to_csv(comparison_path, index=False)
    artifacts["baseline_vs_moment"] = str(comparison_path)
    comparison_json_path = out / "baseline_vs_moment.json"
    comparison_json_path.write_text(json.dumps(_jsonable(comparison.to_dict(orient="records")), indent=2), encoding="utf-8")
    artifacts["baseline_vs_moment_json"] = str(comparison_json_path)

    _write_timeseries_artifacts(out, predictions, artifacts)
    _write_quote_and_trade_artifacts(out, dataset, predictions, artifacts)

    summary_payload = build_market_making_experiment_summary(
        dataset=dataset,
        predictions=predictions,
        comparison=comparison,
        model_meta=model_meta,
        split_summary=split_summary,
        cfg=cfg_dict,
    )
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(_jsonable(summary_payload), indent=2), encoding="utf-8")
    artifacts["summary"] = str(summary_path)

    metadata = build_run_metadata(
        config_path=source_paths.get("config_path", "config/experiments/market_making/market_making_moment.yaml"),
        runtime_applied={"pipeline": "market_making_moment_research", "live_trading": False},
        config_hash_sha256=config_hash,
        config_hash_input=config_hash_input,
        data_fingerprint=compute_dataframe_fingerprint(dataset.set_index("timestamp") if "timestamp" in dataset else dataset),
        data_context={
            "source_paths": {key: str(value) for key, value in source_paths.items()},
            "rows": int(len(dataset)),
            "splits": dict(split_summary),
        },
        model_meta=dict(model_meta),
    )
    metadata_path = out / "run_metadata.json"
    metadata_path.write_text(json.dumps(_jsonable(metadata), indent=2), encoding="utf-8")
    artifacts["run_metadata"] = str(metadata_path)

    if report_markdown:
        report_path = out / "report.md"
        report_path.write_text(report_markdown, encoding="utf-8")
        artifacts["report_markdown"] = str(report_path)

    for label, source_key in (("source_trades", "trades_path"), ("source_quote_events", "quote_events_path")):
        source = source_paths.get(source_key)
        if source and Path(source).exists():
            target_name = "trades.csv" if label == "source_trades" else "quote_decisions_source.csv"
            target = out / target_name
            shutil.copyfile(source, target)
            artifacts[label] = str(target)

    manifest = build_artifact_manifest(artifacts)
    manifest_path = out / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(_jsonable(manifest), indent=2), encoding="utf-8")
    artifacts["manifest"] = str(manifest_path)
    return artifacts


def build_market_making_experiment_summary(
    *,
    dataset: pd.DataFrame,
    predictions: pd.DataFrame,
    comparison: pd.DataFrame,
    model_meta: Mapping[str, Any],
    split_summary: Mapping[str, Any],
    cfg: Mapping[str, Any],
) -> dict[str, Any]:
    pnl = pd.to_numeric(predictions.get("moment_realized_edge_bps", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    equity = pnl.cumsum()
    costs = pd.to_numeric(predictions.get("maker_fee_bps", 0.0), errors="coerce").fillna(0.0)
    gross = pd.to_numeric(predictions.get("moment_gross_edge_bps", pnl), errors="coerce").fillna(0.0)
    returns = pnl / 10_000.0
    summary = _classic_metrics(returns=returns, equity=equity, gross=gross, net=pnl, costs=costs)
    market_summary = _market_making_summary(dataset=dataset, predictions=predictions, cfg=cfg)
    markout_summary = _markout_summary(dataset)
    risk_summary = _risk_summary(dataset)
    moment_summary = _moment_summary(predictions=predictions, model_meta=model_meta, split_summary=split_summary)
    return {
        "summary": summary,
        "timeline_summary": {
            "start": _timestamp_min(dataset),
            "end": _timestamp_max(dataset),
            "rows": int(len(dataset)),
        },
        "evaluation": {
            "primary_summary": summary,
            "trade_diagnostics": {
                "market_making_summary": market_summary,
                "markout_summary": markout_summary,
                "risk_summary": risk_summary,
                "moment_summary": moment_summary,
            },
        },
        "storage": {"artifact_format": "json_csv_markdown_parquet", "html": False, "pptx": False},
        "model_meta": dict(model_meta),
        "reproducibility": {
            "random_seed": dict(cfg.get("runtime", {}) or {}).get("random_seed"),
            "deterministic": dict(cfg.get("runtime", {}) or {}).get("deterministic", True),
        },
        "market_making_summary": market_summary,
        "markout_summary": markout_summary,
        "risk_summary": risk_summary,
        "moment_summary": moment_summary,
        "baseline_vs_moment": comparison.to_dict(orient="records"),
    }


def build_market_making_moment_report(summary: Mapping[str, Any]) -> str:
    primary = dict(summary.get("summary", {}) or {})
    mm = dict(summary.get("market_making_summary", {}) or {})
    moment = dict(summary.get("moment_summary", {}) or {})
    lines = [
        "# Market Making MOMENT Research Experiment",
        "",
        "## Objective",
        "Evaluate whether a MOMENT-based research quote filter can reduce toxic fills and improve fee-adjusted markout.",
        "",
        "## Primary Summary",
        f"- Net PnL: `{primary.get('net_pnl')}`",
        f"- Sharpe: `{primary.get('sharpe')}`",
        f"- Max drawdown: `{primary.get('max_drawdown')}`",
        f"- Trade count: `{primary.get('trade_count')}`",
        "",
        "## Market Making Summary",
        f"- Input events: `{mm.get('input_events')}`",
        f"- Quoted event rate: `{mm.get('quoted_event_rate')}`",
        f"- Fills per placed quote: `{mm.get('fills_per_placed_quote')}`",
        "",
        "## MOMENT Summary",
        f"- Checkpoint: `{moment.get('checkpoint')}`",
        f"- Backend: `{moment.get('backend')}`",
        f"- Quotes blocked by MOMENT: `{moment.get('quotes_blocked_by_moment')}`",
        f"- Quotes allowed by MOMENT: `{moment.get('quotes_allowed_by_moment')}`",
        "",
    ]
    return "\n".join(lines)


def _write_timeseries_artifacts(out: Path, predictions: pd.DataFrame, artifacts: dict[str, str]) -> None:
    timestamp = pd.to_datetime(predictions.get("timestamp"), utc=True, errors="coerce") if "timestamp" in predictions else pd.Series(range(len(predictions)))
    pnl = pd.to_numeric(predictions.get("moment_realized_edge_bps", 0.0), errors="coerce").fillna(0.0)
    gross = pd.to_numeric(predictions.get("moment_gross_edge_bps", pnl), errors="coerce").fillna(0.0)
    costs = pd.to_numeric(predictions.get("maker_fee_bps", 0.0), errors="coerce").fillna(0.0)
    turnover = pd.to_numeric(predictions.get("moment_allowed", False), errors="coerce").fillna(0.0)
    frames = {
        "returns": pd.DataFrame({"timestamp": timestamp, "return": pnl / 10_000.0}),
        "equity_curve": pd.DataFrame({"timestamp": timestamp, "equity": pnl.cumsum()}),
        "gross_returns": pd.DataFrame({"timestamp": timestamp, "gross_return": gross / 10_000.0}),
        "costs": pd.DataFrame({"timestamp": timestamp, "cost_bps": costs}),
        "turnover": pd.DataFrame({"timestamp": timestamp, "turnover": turnover}),
        "positions": pd.DataFrame({"timestamp": timestamp, "position": pd.to_numeric(predictions.get("inventory", 0.0), errors="coerce").fillna(0.0)}),
    }
    for label, frame in frames.items():
        path = out / f"{label}.csv"
        frame.to_csv(path, index=False)
        artifacts[label] = str(path)


def _write_quote_and_trade_artifacts(out: Path, dataset: pd.DataFrame, predictions: pd.DataFrame, artifacts: dict[str, str]) -> None:
    quote_path = out / "quote_decisions.csv"
    predictions.to_csv(quote_path, index=False)
    artifacts["quote_decisions"] = str(quote_path)
    trade_cols = [col for col in ["timestamp", "quote_event_id", "quoted_side_candidate", "buy_markout_bps_h5", "sell_markout_bps_h5"] if col in dataset]
    trades_path = out / "trades.csv"
    dataset.loc[:, trade_cols].dropna(how="all").to_csv(trades_path, index=False)
    artifacts["trades"] = str(trades_path)


def _classic_metrics(*, returns: pd.Series, equity: pd.Series, gross: pd.Series, net: pd.Series, costs: pd.Series) -> dict[str, Any]:
    positive = net[net > 0].sum()
    negative = abs(net[net < 0].sum())
    drawdown = _max_drawdown(equity)
    downside = returns[returns < 0].std(ddof=0)
    return {
        "cumulative_return": float(returns.sum()) if len(returns) else 0.0,
        "annualized_return": None,
        "annualized_vol": None,
        "sharpe": _safe_float(returns.mean() / returns.std(ddof=0)) if returns.std(ddof=0) not in (0, np.nan) else None,
        "sortino": _safe_float(returns.mean() / downside) if downside and not np.isnan(downside) else None,
        "calmar": None,
        "max_drawdown": float(drawdown),
        "profit_factor": _safe_div(float(positive), float(negative)),
        "hit_rate": float((net > 0).mean()) if len(net) else None,
        "avg_turnover": float((net != 0).mean()) if len(net) else 0.0,
        "total_turnover": float((net != 0).sum()),
        "gross_pnl": float(gross.sum()),
        "net_pnl": float(net.sum()),
        "total_cost": float(costs.sum()),
        "cost_drag": float((gross - net).sum()),
        "cost_to_gross_pnl": _safe_div(float(costs.sum()), float(abs(gross.sum()))),
        "trade_count": int((net != 0).sum()),
        "annualization_note": "Quote-event samples are irregular; annualized_return and annualized_vol are null by design.",
    }


def _market_making_summary(*, dataset: pd.DataFrame, predictions: pd.DataFrame, cfg: Mapping[str, Any]) -> dict[str, Any]:
    placed = _bool_series(dataset.get("placed", pd.Series(False, index=dataset.index)))
    allowed = _bool_series(predictions.get("moment_allowed", pd.Series(False, index=predictions.index)))
    fills = placed.sum()
    inventory = pd.to_numeric(dataset.get("inventory", 0.0), errors="coerce").fillna(0.0)
    max_inventory = float(dict(cfg.get("market_making", {}) or {}).get("max_inventory", max(float(inventory.abs().max()), 1.0)))
    return {
        "input_events": int(len(dataset)),
        "quoted_events": int(placed.sum()),
        "skipped_events": int((~placed).sum()),
        "quoted_event_rate": _safe_div(float(placed.sum()), float(len(dataset))),
        "skipped_event_rate": _safe_div(float((~placed).sum()), float(len(dataset))),
        "fills": int(fills),
        "buy_fills": int(dataset["buy_markout_bps_h5"].notna().sum()) if "buy_markout_bps_h5" in dataset else 0,
        "sell_fills": int(dataset["sell_markout_bps_h5"].notna().sum()) if "sell_markout_bps_h5" in dataset else 0,
        "fills_per_input_event": _safe_div(float(fills), float(len(dataset))),
        "fills_per_placed_quote": _safe_div(float(fills), float(placed.sum())),
        "cancel_to_quote_ratio": None,
        "avg_quoted_spread_bps": _mean(dataset.get("spread_bps")),
        "avg_book_spread_bps": _mean(dataset.get("book_spread_bps")),
        "quote_vs_book_spread_ratio": _safe_div(_mean(dataset.get("spread_bps")), _mean(dataset.get("book_spread_bps"))),
        "fees": _mean(predictions.get("maker_fee_bps")),
        "fee_drag_ratio": _safe_div(_mean(predictions.get("maker_fee_bps")), abs(_mean(predictions.get("moment_gross_edge_bps")))),
        "avg_inventory": float(inventory.mean()) if len(inventory) else 0.0,
        "avg_abs_inventory": float(inventory.abs().mean()) if len(inventory) else 0.0,
        "max_abs_inventory": float(inventory.abs().max()) if len(inventory) else 0.0,
        "inventory_limit_utilization": _safe_div(float(inventory.abs().max()), max_inventory),
        "pct_time_inventory_positive": float((inventory > 0).mean()) if len(inventory) else 0.0,
        "pct_time_inventory_negative": float((inventory < 0).mean()) if len(inventory) else 0.0,
        "pct_time_inventory_flat": float((inventory == 0).mean()) if len(inventory) else 0.0,
        "moment_allowed_event_rate": _safe_div(float(allowed.sum()), float(len(allowed))),
    }


def _markout_summary(dataset: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for horizon in (1, 5, 10, 30):
        key = f"h{horizon}"
        cols = [col for col in (f"buy_markout_bps_{key}", f"sell_markout_bps_{key}") if col in dataset]
        combined = pd.concat([pd.to_numeric(dataset[col], errors="coerce") for col in cols], ignore_index=True) if cols else pd.Series(dtype=float)
        out[f"avg_markout_bps_{key}"] = _mean(combined)
        out[f"adverse_selection_rate_{key}"] = float((combined < 0).mean()) if combined.notna().any() else None
        for side in ("buy", "sell"):
            col = f"{side}_markout_bps_{key}"
            values = pd.to_numeric(dataset.get(col, pd.Series(dtype=float)), errors="coerce")
            out[f"{side}_avg_markout_bps_{key}"] = _mean(values)
            out[f"{side}_adverse_selection_rate_{key}"] = float((values < 0).mean()) if values.notna().any() else None
    return out


def _risk_summary(dataset: pd.DataFrame) -> dict[str, Any]:
    allowed = _bool_series(dataset.get("risk_allowed", pd.Series(False, index=dataset.index)))
    reasons = dataset.get("risk_reason", pd.Series("", index=dataset.index)).fillna("").astype(str)
    reject_reasons = reasons[~allowed].value_counts().to_dict()
    return {
        "reject_counts_by_reason": {str(k): int(v) for k, v in reject_reasons.items()},
        "allowed_count": int(allowed.sum()),
        "rejected_count": int((~allowed).sum()),
        "kill_switch_count": int(_bool_series(dataset.get("risk_kill_switch", pd.Series(False, index=dataset.index))).sum()),
        "runtime_errors": None,
        "reconnects": None,
    }


def _moment_summary(*, predictions: pd.DataFrame, model_meta: Mapping[str, Any], split_summary: Mapping[str, Any]) -> dict[str, Any]:
    allowed = _bool_series(predictions.get("moment_allowed", pd.Series(False, index=predictions.index)))
    blocked = ~allowed
    return {
        "model_name": model_meta.get("model_name"),
        "checkpoint": model_meta.get("checkpoint"),
        "backend": model_meta.get("backend"),
        "frozen_encoder": model_meta.get("frozen_encoder"),
        "fine_tune": model_meta.get("fine_tune"),
        "lookback_length": model_meta.get("lookback_length"),
        "prediction_horizons": model_meta.get("prediction_horizons"),
        "target_definition": model_meta.get("target_definition"),
        "split": dict(split_summary),
        "buy_threshold": model_meta.get("buy_threshold"),
        "sell_threshold": model_meta.get("sell_threshold"),
        "uncertainty_threshold": model_meta.get("uncertainty_threshold"),
        "quotes_blocked_by_moment": int(blocked.sum()),
        "quotes_allowed_by_moment": int(allowed.sum()),
        "average_predicted_buy_edge": _mean(predictions.get("moment_buy_expected_edge_bps")),
        "average_predicted_sell_edge": _mean(predictions.get("moment_sell_expected_edge_bps")),
        "realized_markout_of_moment_allowed_fills": _mean(predictions.loc[allowed, "moment_realized_edge_bps"]) if "moment_realized_edge_bps" in predictions else None,
        "realized_markout_of_moment_blocked_hypothetical_opportunities": _mean(predictions.loc[blocked, "moment_hypothetical_edge_bps"]) if "moment_hypothetical_edge_bps" in predictions else None,
    }


def _timestamp_min(frame: pd.DataFrame) -> str | None:
    if "timestamp" not in frame or frame.empty:
        return None
    return pd.to_datetime(frame["timestamp"], utc=True).min().isoformat()


def _timestamp_max(frame: pd.DataFrame) -> str | None:
    if "timestamp" not in frame or frame.empty:
        return None
    return pd.to_datetime(frame["timestamp"], utc=True).max().isoformat()


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    return float((equity - peak).min())


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0 or np.isnan(den):
        return None
    return float(num) / float(den)


def _safe_float(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(out) or np.isinf(out) else out


def _mean(values: object) -> float | None:
    if values is None:
        return None
    series = pd.to_numeric(values, errors="coerce")
    return float(series.mean()) if series.notna().any() else None


def _bool_series(values: object) -> pd.Series:
    if isinstance(values, pd.Series):
        if values.dtype == bool:
            return values.fillna(False)
        return values.astype(str).str.lower().isin({"true", "1", "yes"})
    return pd.Series(values).astype(bool)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


__all__ = [
    "build_market_making_experiment_summary",
    "build_market_making_moment_report",
    "write_market_making_experiment_artifacts",
]
