from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.market_making.experiment_artifacts import (
    build_market_making_experiment_summary,
    build_market_making_moment_report,
    write_market_making_experiment_artifacts,
)
from src.market_making.moment_dataset import (
    build_market_making_moment_dataset,
    chronological_split,
    feature_columns,
)
from src.market_making.moment_model import MomentModelConfig, MomentResearchModel
from src.market_making.moment_quote_filter import MomentQuoteFilter, MomentQuoteFilterConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a research-only market-making MOMENT experiment.")
    parser.add_argument("--config", default="config/experiments/market_making/market_making_moment.yaml")
    args = parser.parse_args(argv)
    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(cfg, dict):
        raise ValueError("config must be a YAML mapping")
    artifacts = run_experiment(cfg, config_path=cfg_path)
    print(f"Market-making MOMENT research run: {artifacts['run_dir']}")
    print(f"Summary: {artifacts['summary']}")
    return 0


def run_experiment(cfg: dict[str, Any], *, config_path: str | Path) -> dict[str, str]:
    data_cfg = dict(cfg.get("data", {}) or {})
    model_cfg = dict(cfg.get("model", {}) or {})
    filter_cfg = dict(cfg.get("filter", {}) or {})
    split_cfg = dict(cfg.get("split", {}) or {})
    market_cfg = dict(cfg.get("market_making", {}) or {})
    output_cfg = dict(cfg.get("output", {}) or {})
    runtime_cfg = dict(cfg.get("runtime", {}) or {})

    dataset_path = Path(data_cfg.get("dataset_path", "logs/experiments/market_making/datasets/moment_dataset.parquet"))
    horizons = [int(value) for value in data_cfg.get("horizons", [1, 5, 10, 30])]
    if dataset_path.exists() and bool(data_cfg.get("reuse_dataset", True)):
        dataset = pd.read_parquet(dataset_path)
    else:
        dataset = build_market_making_moment_dataset(
            orderbook_events_path=data_cfg["orderbook_events_path"],
            quote_events_paths=data_cfg["quote_events_paths"],
            output_path=dataset_path,
            horizons=horizons,
            maker_fee_bps=float(market_cfg.get("maker_fee_bps", 0.0)),
            max_inventory=market_cfg.get("max_inventory"),
        )

    dataset["timestamp"] = pd.to_datetime(dataset["timestamp"], utc=True)
    splits = chronological_split(
        dataset,
        train_fraction=float(split_cfg.get("train_fraction", 0.6)),
        validation_fraction=float(split_cfg.get("validation_fraction", 0.2)),
    )
    features = feature_columns(dataset)
    model = MomentResearchModel(
        MomentModelConfig(
            backend=str(model_cfg.get("backend", "deterministic_fixture")),
            checkpoint=str(model_cfg.get("checkpoint", "AutonLab/MOMENT-1-large")),
            frozen_encoder=bool(model_cfg.get("frozen_encoder", True)),
            fine_tune=bool(model_cfg.get("fine_tune", False)),
            random_seed=int(runtime_cfg.get("random_seed", 42)),
            target_horizon=str(model_cfg.get("target_horizon", "h5")),
            lookback_length=int(model_cfg.get("lookback_length", 512)),
            batch_size=int(model_cfg.get("batch_size", 8)),
            device=str(model_cfg.get("device", "cpu")),
            ridge_alpha=float(model_cfg.get("ridge_alpha", 1.0)),
            max_fit_rows=_optional_positive_int(model_cfg.get("max_fit_rows")),
            local_files_only=bool(model_cfg.get("local_files_only", False)),
        )
    ).fit(splits["train"], feature_columns=features)

    scored = dataset.copy()
    model_predictions = model.predict(scored)
    scored = pd.concat([scored.reset_index(drop=True), model_predictions.reset_index(drop=True)], axis=1)
    quote_filter = MomentQuoteFilter(
        MomentQuoteFilterConfig(
            maker_fee_bps=float(market_cfg.get("maker_fee_bps", 0.0)),
            expected_spread_capture_bps=float(filter_cfg.get("expected_spread_capture_bps", 0.0)),
            safety_buffer_bps=float(filter_cfg.get("safety_buffer_bps", 0.0)),
            max_uncertainty=float(filter_cfg.get("max_uncertainty", 1.0)),
            min_expected_edge_bps=float(filter_cfg.get("min_expected_edge_bps", 0.0)),
        )
    )
    decisions = [
        quote_filter.decide(row, candidate_side=str(row.get("quoted_side_candidate", "both"))).to_dict()
        for row in scored.to_dict(orient="records")
    ]
    decision_frame = pd.DataFrame(decisions)
    predictions = pd.concat([scored.reset_index(drop=True), decision_frame], axis=1)
    predictions["moment_allowed"] = predictions["allow_buy"] | predictions["allow_sell"]
    predictions["maker_fee_bps"] = float(market_cfg.get("maker_fee_bps", 0.0))
    predictions["moment_gross_edge_bps"] = predictions.apply(_selected_gross_edge, axis=1)
    predictions["moment_realized_edge_bps"] = predictions["moment_gross_edge_bps"] - predictions["maker_fee_bps"]
    predictions["moment_hypothetical_edge_bps"] = predictions.apply(_best_hypothetical_edge, axis=1)
    predictions.loc[~predictions["moment_allowed"], "moment_realized_edge_bps"] = 0.0

    comparison = _baseline_vs_moment(predictions)
    split_summary = _split_summary(splits)
    model_meta = {
        **model.metadata(),
        "lookback_length": model_cfg.get("lookback_length", 512),
        "prediction_horizons": horizons,
        "target_definition": "fee-adjusted quote-side markout in basis points",
        "buy_threshold": filter_cfg.get("min_expected_edge_bps", 0.0),
        "sell_threshold": filter_cfg.get("min_expected_edge_bps", 0.0),
        "uncertainty_threshold": filter_cfg.get("max_uncertainty", 1.0),
    }
    run_dir = _resolve_run_dir(output_cfg, cfg)
    summary_preview = build_market_making_experiment_summary(
        dataset=dataset,
        predictions=predictions,
        comparison=comparison,
        model_meta=model_meta,
        split_summary=split_summary,
        cfg=cfg,
    )
    report = build_market_making_moment_report(summary_preview) if bool(output_cfg.get("write_report", True)) else None
    artifacts = write_market_making_experiment_artifacts(
        run_dir=run_dir,
        cfg=cfg,
        dataset=dataset,
        predictions=predictions,
        comparison=comparison,
        model_meta=model_meta,
        split_summary=split_summary,
        source_paths={
            "config_path": config_path,
            "dataset_path": dataset_path,
            "orderbook_events_path": data_cfg.get("orderbook_events_path", ""),
            "quote_events_path": _first_path(data_cfg.get("quote_events_paths", [])),
            "trades_path": data_cfg.get("trades_path", ""),
        },
        report_markdown=report,
    )
    artifacts["run_dir"] = str(run_dir)
    return artifacts


def _baseline_vs_moment(predictions: pd.DataFrame) -> pd.DataFrame:
    baseline_edge = predictions.apply(_best_hypothetical_edge, axis=1) - pd.to_numeric(predictions["maker_fee_bps"], errors="coerce").fillna(0.0)
    moment_edge = pd.to_numeric(predictions["moment_realized_edge_bps"], errors="coerce").fillna(0.0)
    rows = [
        _comparison_row("baseline", baseline_edge, allowed=pd.Series(True, index=predictions.index)),
        _comparison_row("moment_filtered", moment_edge, allowed=predictions["moment_allowed"]),
    ]
    rows.append(
        {
            "strategy": "delta_moment_minus_baseline",
            "net_edge_bps": rows[1]["net_edge_bps"] - rows[0]["net_edge_bps"],
            "avg_edge_bps": rows[1]["avg_edge_bps"] - rows[0]["avg_edge_bps"],
            "event_count": rows[1]["event_count"],
            "allowed_event_count": rows[1]["allowed_event_count"],
            "blocked_event_count": rows[1]["blocked_event_count"],
            "hit_rate": rows[1]["hit_rate"],
        }
    )
    return pd.DataFrame(rows)


def _comparison_row(label: str, edge: pd.Series, *, allowed: pd.Series) -> dict[str, Any]:
    edge = pd.to_numeric(edge, errors="coerce").fillna(0.0)
    allowed_bool = allowed.astype(bool)
    active = edge[allowed_bool]
    return {
        "strategy": label,
        "net_edge_bps": float(active.sum()),
        "avg_edge_bps": float(active.mean()) if len(active) else 0.0,
        "event_count": int(len(edge)),
        "allowed_event_count": int(allowed_bool.sum()),
        "blocked_event_count": int((~allowed_bool).sum()),
        "hit_rate": float((active > 0).mean()) if len(active) else None,
    }


def _selected_gross_edge(row: pd.Series) -> float:
    candidates = []
    if bool(row.get("allow_buy")):
        candidates.append(row.get("buy_markout_bps_h5"))
    if bool(row.get("allow_sell")):
        candidates.append(row.get("sell_markout_bps_h5"))
    numeric = [float(value) for value in candidates if pd.notna(value)]
    return max(numeric) if numeric else 0.0


def _best_hypothetical_edge(row: pd.Series) -> float:
    candidates = [row.get("buy_markout_bps_h5"), row.get("sell_markout_bps_h5")]
    numeric = [float(value) for value in candidates if pd.notna(value)]
    return max(numeric) if numeric else 0.0


def _split_summary(splits: dict[str, pd.DataFrame]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, frame in splits.items():
        out[name] = {
            "rows": int(len(frame)),
            "start": pd.to_datetime(frame["timestamp"], utc=True).min().isoformat() if len(frame) else None,
            "end": pd.to_datetime(frame["timestamp"], utc=True).max().isoformat() if len(frame) else None,
        }
    return out


def _resolve_run_dir(output_cfg: dict[str, Any], cfg: dict[str, Any]) -> Path:
    root = Path(output_cfg.get("root", "logs/experiments/market_making"))
    name = str(output_cfg.get("run_name", "market_making_moment"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    digest = hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:8]
    return root / f"{name}_{timestamp}_{digest}"


def _first_path(paths: object) -> str:
    if isinstance(paths, list) and paths:
        return str(paths[0])
    return ""


def _optional_positive_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


if __name__ == "__main__":
    raise SystemExit(main())
