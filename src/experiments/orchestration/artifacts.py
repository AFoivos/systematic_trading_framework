from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import pandas as pd
import yaml

from src.backtesting.engine import BacktestResult
from src.experiments.orchestration.common import data_stats_payload, redact_sensitive_values, resolved_feature_columns
from src.portfolio import PortfolioPerformance
from src.utils.run_metadata import build_artifact_manifest


def save_artifacts(
    *,
    run_dir: Path,
    cfg: dict[str, Any],
    data: pd.DataFrame | dict[str, pd.DataFrame],
    performance: BacktestResult | PortfolioPerformance,
    model_meta: dict[str, Any],
    evaluation: dict[str, Any],
    monitoring: dict[str, Any],
    execution: dict[str, Any],
    execution_orders: pd.DataFrame | None,
    portfolio_weights: pd.DataFrame | None,
    portfolio_diagnostics: pd.DataFrame | None,
    portfolio_meta: dict[str, Any],
    storage_meta: dict[str, Any],
    run_metadata: dict[str, Any],
    config_hash_sha256: str,
    data_fingerprint: dict[str, Any],
) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = run_dir / "config_used.yaml"
    safe_cfg = redact_sensitive_values(cfg)
    with cfg_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(safe_cfg, handle, sort_keys=False)

    summary_path = run_dir / "summary.json"
    payload = {
        "summary": evaluation.get("primary_summary", performance.summary),
        "timeline_summary": performance.summary,
        "evaluation": evaluation,
        "monitoring": monitoring,
        "execution": execution,
        "portfolio": portfolio_meta,
        "storage": storage_meta,
        "model_meta": model_meta,
        "config_features": cfg.get("features", []),
        "signals": cfg.get("signals", {}),
        "resolved_feature_columns": resolved_feature_columns(model_meta),
        "data_stats": data_stats_payload(data),
        "reproducibility": {
            "config_hash_sha256": config_hash_sha256,
            "data_hash_sha256": data_fingerprint.get("sha256"),
            "runtime": run_metadata.get("runtime", {}),
        },
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)

    metadata_path = run_dir / "run_metadata.json"
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(run_metadata, handle, indent=2, default=str)

    equity_path = run_dir / "equity_curve.csv"
    performance.equity_curve.to_csv(equity_path, header=True)

    if isinstance(performance, BacktestResult):
        net_returns = performance.returns
        positions = performance.positions
        positions_path = run_dir / "positions.csv"
        positions.to_csv(positions_path, header=True)
    else:
        net_returns = performance.net_returns
        positions_path = None

    returns_path = run_dir / "returns.csv"
    net_returns.to_csv(returns_path, header=True)

    gross_returns_path = run_dir / "gross_returns.csv"
    performance.gross_returns.to_csv(gross_returns_path, header=True)

    costs_path = run_dir / "costs.csv"
    performance.costs.to_csv(costs_path, header=True)

    turnover_path = run_dir / "turnover.csv"
    performance.turnover.to_csv(turnover_path, header=True)

    monitoring_path = None
    if monitoring:
        monitoring_path = run_dir / "monitoring_report.json"
        with monitoring_path.open("w", encoding="utf-8") as handle:
            json.dump(monitoring, handle, indent=2, default=str)

    orders_path = None
    if execution_orders is not None:
        orders_path = run_dir / "paper_orders.csv"
        execution_orders.to_csv(orders_path)

    weights_path = None
    diagnostics_path = None
    if portfolio_weights is not None:
        weights_path = run_dir / "portfolio_weights.csv"
        portfolio_weights.to_csv(weights_path)
        if portfolio_diagnostics is not None:
            diagnostics_path = run_dir / "portfolio_diagnostics.csv"
            portfolio_diagnostics.to_csv(diagnostics_path)

    artifacts = {
        "run_dir": str(run_dir),
        "config": str(cfg_path),
        "summary": str(summary_path),
        "run_metadata": str(metadata_path),
        "equity_curve": str(equity_path),
        "returns": str(returns_path),
        "gross_returns": str(gross_returns_path),
        "costs": str(costs_path),
        "turnover": str(turnover_path),
    }
    if positions_path is not None:
        artifacts["positions"] = str(positions_path)
    if monitoring_path is not None:
        artifacts["monitoring"] = str(monitoring_path)
    if orders_path is not None:
        artifacts["paper_orders"] = str(orders_path)
    if weights_path is not None:
        artifacts["portfolio_weights"] = str(weights_path)
    if diagnostics_path is not None:
        artifacts["portfolio_diagnostics"] = str(diagnostics_path)

    manifest = build_artifact_manifest(artifacts)
    manifest_path = run_dir / "artifact_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)
    artifacts["manifest"] = str(manifest_path)

    return artifacts


__all__ = ["save_artifacts"]
