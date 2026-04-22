from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

from src.experiments.orchestration.artifacts import save_artifacts
from src.experiments.orchestration.backtest_stage import run_portfolio_backtest, run_single_asset_backtest
from src.experiments.orchestration.common import build_storage_context, resolve_symbols
from src.experiments.orchestration.execution_stage import build_execution_output
from src.experiments.orchestration.feature_stage import apply_signals_to_assets, apply_steps_to_assets
from src.experiments.orchestration.model_stage import apply_model_pipeline_to_assets
from src.experiments.orchestration.reporting import (
    build_portfolio_evaluation,
    build_single_asset_evaluation,
    compute_monitoring_report,
)
from src.experiments.orchestration.stage_trace import (
    build_stage_tail_snapshot,
    format_stage_tail_snapshot,
)
from src.experiments.orchestration.types import ExperimentResult
from src.utils.config import load_experiment_config
from src.utils.repro import runtime_reproducibility_context
from src.utils.run_metadata import (
    build_run_metadata,
    compute_config_hash,
    compute_dataframe_fingerprint,
)
from src.src_data.storage import asset_frames_to_long_frame


LoadAssetFramesFn = Callable[[dict[str, object]], tuple[dict[str, pd.DataFrame], dict[str, object]]]
SaveProcessedFn = Callable[..., dict[str, object] | None]
_RUN_DIR_TZ = ZoneInfo("Europe/Athens")


def _run_dir_timestamp(now: datetime | None = None) -> str:
    timestamp = now if now is not None else datetime.now(_RUN_DIR_TZ)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=_RUN_DIR_TZ)
    else:
        timestamp = timestamp.astimezone(_RUN_DIR_TZ)
    return timestamp.strftime("%Y%m%d_%H%M%S_%f")


def _stage_tail_config(cfg: dict[str, object]) -> dict[str, object]:
    logging_cfg = dict(cfg.get("logging", {}) or {})
    stage_tails = dict(logging_cfg.get("stage_tails", {}) or {})
    logging_enabled = bool(logging_cfg.get("enabled", True))
    return {
        "enabled": logging_enabled and bool(stage_tails.get("enabled", False)),
        "stdout": logging_enabled and bool(stage_tails.get("stdout", True)),
        "report": logging_enabled and bool(stage_tails.get("report", True)),
        "limit": int(stage_tails.get("limit", 10) or 10),
        "max_columns": int(stage_tails.get("max_columns", 16) or 16),
        "max_assets": int(stage_tails.get("max_assets", 3) or 3),
    }


def _record_stage_tail(
    *,
    traces: list[dict[str, object]],
    stage: str,
    asset_frames: dict[str, pd.DataFrame],
    previous_asset_frames: dict[str, pd.DataFrame] | None,
    stage_tail_cfg: dict[str, object],
) -> None:
    if not bool(stage_tail_cfg.get("enabled", False)):
        return
    snapshot = build_stage_tail_snapshot(
        stage=stage,
        asset_frames=asset_frames,
        previous_asset_frames=previous_asset_frames,
        limit=int(stage_tail_cfg.get("limit", 10) or 10),
        max_columns=int(stage_tail_cfg.get("max_columns", 16) or 16),
        max_assets=int(stage_tail_cfg.get("max_assets", 3) or 3),
    )
    traces.append(snapshot)
    if bool(stage_tail_cfg.get("stdout", True)):
        print(format_stage_tail_snapshot(snapshot))
        print("")


def run_experiment_pipeline(
    config_path: str | Path,
    *,
    load_asset_frames_fn: LoadAssetFramesFn,
    save_processed_snapshot_fn: SaveProcessedFn,
) -> ExperimentResult:
    """
    Execute the end-to-end experiment workflow using the split orchestration stages.
    """
    cfg = load_experiment_config(config_path)
    with runtime_reproducibility_context(cfg.get("runtime", {})) as runtime_applied:
        config_hash_sha256, config_hash_input = compute_config_hash(cfg)
        stage_tail_cfg = _stage_tail_config(cfg)
        stage_tails: list[dict[str, object]] = []

        data_cfg = cfg["data"]
        raw_asset_frames, storage_meta = load_asset_frames_fn(data_cfg)
        _record_stage_tail(
            traces=stage_tails,
            stage="raw_loaded",
            asset_frames=raw_asset_frames,
            previous_asset_frames=None,
            stage_tail_cfg=stage_tail_cfg,
        )
        raw_long_frame = asset_frames_to_long_frame(raw_asset_frames)
        data_fingerprint = compute_dataframe_fingerprint(raw_long_frame)

        feature_asset_frames = apply_steps_to_assets(
            raw_asset_frames,
            feature_steps=list(cfg.get("features", []) or []),
        )
        _record_stage_tail(
            traces=stage_tails,
            stage="features_applied",
            asset_frames=feature_asset_frames,
            previous_asset_frames=raw_asset_frames,
            stage_tail_cfg=stage_tail_cfg,
        )
        processed_snapshot = save_processed_snapshot_fn(
            feature_asset_frames,
            data_cfg=data_cfg,
            config_hash_sha256=config_hash_sha256,
            feature_steps=list(cfg.get("features", []) or []),
        )
        if processed_snapshot is not None:
            storage_meta["saved_processed_snapshot"] = processed_snapshot

        base_model_cfg = {
            "runtime": cfg.get("runtime", {}),
            "risk": cfg.get("risk", {}),
            "portfolio": cfg.get("portfolio", {}),
            "backtest": cfg.get("backtest", {}),
            "data_alignment": cfg.get("data", {}).get("alignment", "inner"),
        }
        model_cfg = dict(cfg.get("model", {"kind": "none"}) or {})
        for key, value in base_model_cfg.items():
            model_cfg.setdefault(key, value)
        model_stages_cfg: list[dict[str, object]] = []
        for raw_stage_cfg in list(cfg.get("model_stages", []) or []):
            stage_cfg = dict(raw_stage_cfg)
            for key, value in base_model_cfg.items():
                stage_cfg.setdefault(key, value)
            model_stages_cfg.append(stage_cfg)
        enabled_model_stage_count = sum(1 for stage_cfg in model_stages_cfg if bool(stage_cfg.get("enabled", True)))
        returns_col = cfg.get("backtest", {}).get("returns_col")
        model_asset_frames, model, model_meta = apply_model_pipeline_to_assets(
            feature_asset_frames,
            model_cfg=model_cfg,
            model_stages=model_stages_cfg,
            returns_col=returns_col,
        )
        _record_stage_tail(
            traces=stage_tails,
            stage="model_applied" if enabled_model_stage_count == 0 else f"model_applied[{enabled_model_stage_count}_stages]",
            asset_frames=model_asset_frames,
            previous_asset_frames=feature_asset_frames,
            stage_tail_cfg=stage_tail_cfg,
        )

        asset_frames = apply_signals_to_assets(
            model_asset_frames,
            signals_cfg=dict(cfg.get("signals", {}) or {}),
        )
        _record_stage_tail(
            traces=stage_tails,
            stage="signals_applied",
            asset_frames=asset_frames,
            previous_asset_frames=model_asset_frames,
            stage_tail_cfg=stage_tail_cfg,
        )

        portfolio_enabled = bool(cfg.get("portfolio", {}).get("enabled", False))
        if len(asset_frames) > 1 and not portfolio_enabled:
            raise ValueError(
                "Multiple assets were loaded but portfolio.enabled=false. "
                "Enable portfolio mode or reduce the run to a single asset."
            )

        is_portfolio = portfolio_enabled
        portfolio_weights: pd.DataFrame | None = None
        portfolio_diagnostics: pd.DataFrame | None = None
        portfolio_meta: dict[str, object] = {}

        if is_portfolio:
            performance, portfolio_weights, portfolio_diagnostics, portfolio_meta = run_portfolio_backtest(
                asset_frames,
                cfg=cfg,
            )
            evaluation = build_portfolio_evaluation(
                asset_frames,
                performance=performance,
                model_meta=model_meta,
                periods_per_year=cfg["backtest"].get("periods_per_year", 252),
                alignment=cfg["data"].get("alignment", "inner"),
            )
        else:
            asset = next(iter(sorted(asset_frames)))
            performance = run_single_asset_backtest(
                asset,
                asset_frames[asset],
                cfg=cfg,
                model_meta=model_meta,
            )
            evaluation = build_single_asset_evaluation(
                asset,
                asset_frames[asset],
                performance=performance,
                model_meta=model_meta,
                periods_per_year=cfg["backtest"].get("periods_per_year", 252),
            )

        monitoring = compute_monitoring_report(
            asset_frames,
            model_meta=model_meta,
            monitoring_cfg=dict(cfg.get("monitoring", {}) or {}),
        )
        execution, execution_orders = build_execution_output(
            asset_frames=asset_frames,
            execution_cfg=dict(cfg.get("execution", {}) or {}),
            portfolio_weights=portfolio_weights,
            performance=performance,
            alignment=cfg["data"].get("alignment", "inner"),
        )

        artifacts: dict[str, str] = {}
        logging_cfg = cfg.get("logging", {}) or {}
        if logging_cfg.get("enabled", True):
            run_metadata = build_run_metadata(
                config_path=cfg.get("config_path", config_path),
                runtime_applied=runtime_applied,
                config_hash_sha256=config_hash_sha256,
                config_hash_input=config_hash_input,
                data_fingerprint=data_fingerprint,
                data_context=(
                    build_storage_context(
                        data_cfg,
                        symbols=resolve_symbols(data_cfg),
                        pit_cfg=dict(data_cfg.get("pit", {}) or {}),
                    ).to_dict()
                    | {"storage": storage_meta}
                ),
                model_meta=model_meta,
            )
            base_dir = Path(logging_cfg.get("output_dir", "logs/experiments")).resolve()
            run_name = str(logging_cfg.get("run_name", Path(config_path).stem))
            timestamp = _run_dir_timestamp()
            run_dir = base_dir / f"{run_name}_{timestamp}_{uuid4().hex[:8]}"
            artifacts = save_artifacts(
                run_dir=run_dir,
                cfg=cfg,
                data=(asset_frames if is_portfolio else next(iter(asset_frames.values()))),
                performance=performance,
                model_meta=model_meta,
                evaluation=evaluation,
                monitoring=monitoring,
                execution=execution,
                execution_orders=execution_orders,
                portfolio_weights=portfolio_weights,
                portfolio_diagnostics=portfolio_diagnostics,
                portfolio_meta=portfolio_meta,
                storage_meta=storage_meta,
                run_metadata=run_metadata,
                config_hash_sha256=config_hash_sha256,
                data_fingerprint=data_fingerprint,
                stage_tails={
                    "config": stage_tail_cfg,
                    "stages": stage_tails,
                },
            )

        result_data: pd.DataFrame | dict[str, pd.DataFrame]
        if len(asset_frames) == 1 and not is_portfolio:
            result_data = next(iter(asset_frames.values()))
        else:
            result_data = asset_frames

        return ExperimentResult(
            config=cfg,
            data=result_data,
            backtest=performance,
            model=model,
            model_meta=model_meta,
            artifacts=artifacts,
            evaluation=evaluation,
            monitoring=monitoring,
            execution=execution,
            portfolio_weights=portfolio_weights,
        )


__all__ = ["run_experiment_pipeline"]
