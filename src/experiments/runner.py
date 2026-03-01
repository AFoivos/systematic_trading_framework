from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import re
from typing import Any

import json
import numpy as np
import pandas as pd
import yaml

from src.backtesting.engine import BacktestResult, run_backtest
from src.evaluation.metrics import compute_backtest_metrics
from src.execution.paper import build_rebalance_orders
from src.experiments.contracts import validate_data_contract
from src.experiments.registry import get_feature_fn, get_model_fn, get_signal_fn
from src.monitoring.drift import compute_feature_drift
from src.portfolio import (
    PortfolioConstraints,
    PortfolioPerformance,
    build_optimized_weights_over_time,
    build_rolling_covariance_by_date,
    build_weights_from_signals_over_time,
    compute_portfolio_performance,
)
from src.src_data.loaders import load_ohlcv, load_ohlcv_panel
from src.src_data.pit import apply_pit_hardening
from src.src_data.storage import (
    asset_frames_to_long_frame,
    load_dataset_snapshot,
    save_dataset_snapshot,
)
from src.src_data.validation import validate_ohlcv
from src.utils.config import load_experiment_config
from src.utils.paths import in_project
from src.utils.repro import apply_runtime_reproducibility
from src.utils.run_metadata import (
    build_artifact_manifest,
    build_run_metadata,
    compute_config_hash,
    compute_dataframe_fingerprint,
)


@dataclass
class ExperimentResult:
    """
    Collect the full output of an experiment run, including the resolved configuration,
    transformed data, fitted model objects, evaluation outputs, execution artifacts, and any
    portfolio weights created during orchestration.
    """
    config: dict[str, Any]
    data: pd.DataFrame | dict[str, pd.DataFrame]
    backtest: BacktestResult | PortfolioPerformance
    model: object | dict[str, object] | None
    model_meta: dict[str, Any]
    artifacts: dict[str, str]
    evaluation: dict[str, Any]
    monitoring: dict[str, Any]
    execution: dict[str, Any]
    portfolio_weights: pd.DataFrame | None = None


def _slugify(value: str) -> str:
    """
    Handle slugify inside the experiment orchestration layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower()
    return slug or "dataset"


def _stable_json_dumps(value: Any) -> str:
    """
    Serialize a configuration fragment deterministically so cache identities and metadata
    comparisons are stable across runs.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _pit_config_hash(pit_cfg: dict[str, Any] | None) -> str:
    """
    Compute a stable hash for the PIT configuration so cached datasets cannot be reused under a
    different PIT policy.
    """
    payload = _stable_json_dumps(dict(pit_cfg or {})).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _resolve_symbols(data_cfg: dict[str, Any]) -> list[str]:
    """
    Handle symbols inside the experiment orchestration layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    if data_cfg.get("symbol") is not None:
        return [str(data_cfg["symbol"])]
    return [str(symbol) for symbol in data_cfg.get("symbols", [])]


def _default_dataset_id(data_cfg: dict[str, Any]) -> str:
    """
    Handle default dataset id inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    symbols = _resolve_symbols(data_cfg)
    symbol_part = "_".join(_slugify(symbol) for symbol in symbols[:6])
    if len(symbols) > 6:
        symbol_part = f"{symbol_part}_plus_{len(symbols) - 6}"
    pit_hash_short = _pit_config_hash(dict(data_cfg.get("pit", {}) or {}))[:8]
    return "_".join(
        [
            _slugify(data_cfg.get("source", "source")),
            _slugify(data_cfg.get("interval", "interval")),
            symbol_part,
            _slugify(data_cfg.get("start") or "start"),
            _slugify(data_cfg.get("end") or "open"),
            f"pit_{pit_hash_short}",
        ]
    )


def _apply_feature_steps(df: pd.DataFrame, steps: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Handle feature steps inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    out = df
    for step in steps:
        if "step" not in step:
            raise ValueError("Each feature step must include a 'step' key.")
        name = step["step"]
        params = step.get("params", {}) or {}
        fn = get_feature_fn(name)
        out = fn(out, **params)
    return out


def _apply_model_step(
    df: pd.DataFrame,
    model_cfg: dict[str, Any],
    returns_col: str | None,
) -> tuple[pd.DataFrame, object | None, dict[str, Any]]:
    """
    Handle model step inside the experiment orchestration layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    kind = model_cfg.get("kind", "none")
    if kind == "none":
        return df, None, {}
    fn = get_model_fn(kind)
    return fn(df, model_cfg, returns_col)


def _apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame:
    """
    Handle signal step inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    kind = signals_cfg.get("kind", "none")
    if kind == "none":
        return df
    params = signals_cfg.get("params", {}) or {}
    fn = get_signal_fn(kind)
    out = fn(df, **params)
    if isinstance(out, pd.DataFrame):
        return out
    if isinstance(out, pd.Series):
        df = df.copy()
        df[out.name] = out
        return df
    raise TypeError(f"Signal function for kind='{kind}' returned unsupported type: {type(out)}")


def _apply_steps_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    feature_steps: list[dict[str, Any]],
) -> dict[str, pd.DataFrame]:
    """
    Handle steps to assets inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    out: dict[str, pd.DataFrame] = {}
    for asset, df in sorted(asset_frames.items()):
        out[asset] = _apply_feature_steps(df, feature_steps)
    return out


def _aggregate_model_meta(per_asset_meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Handle aggregate model meta inside the experiment orchestration layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if not per_asset_meta:
        return {}

    first = next(iter(per_asset_meta.values()))
    total_eval_rows = sum(
        int(meta.get("oos_classification_summary", {}).get("evaluation_rows") or 0)
        for meta in per_asset_meta.values()
    )

    weighted_summary: dict[str, float | int | None] = {
        "evaluation_rows": int(total_eval_rows),
        "positive_rate": None,
        "accuracy": None,
        "brier": None,
        "roc_auc": None,
        "log_loss": None,
    }
    if total_eval_rows > 0:
        for key in ("positive_rate", "accuracy", "brier", "roc_auc", "log_loss"):
            weighted_value = 0.0
            weight_total = 0
            for meta in per_asset_meta.values():
                summary = dict(meta.get("oos_classification_summary", {}) or {})
                value = summary.get(key)
                rows = int(summary.get("evaluation_rows") or 0)
                if value is None or rows <= 0:
                    continue
                weighted_value += float(value) * rows
                weight_total += rows
            if weight_total > 0:
                weighted_summary[key] = float(weighted_value / weight_total)

    return {
        "model_kind": first.get("model_kind"),
        "assets": sorted(per_asset_meta),
        "per_asset": per_asset_meta,
        "train_rows": int(sum(int(meta.get("train_rows", 0)) for meta in per_asset_meta.values())),
        "test_pred_rows": int(sum(int(meta.get("test_pred_rows", 0)) for meta in per_asset_meta.values())),
        "oos_rows": int(sum(int(meta.get("oos_rows", 0)) for meta in per_asset_meta.values())),
        "oos_classification_summary": weighted_summary,
    }


def _apply_model_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_cfg: dict[str, Any],
    returns_col: str | None,
) -> tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]:
    """
    Handle model to assets inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if model_cfg.get("kind", "none") == "none":
        return asset_frames, None, {}

    out: dict[str, pd.DataFrame] = {}
    models: dict[str, object] = {}
    metas: dict[str, dict[str, Any]] = {}

    for asset, df in sorted(asset_frames.items()):
        frame, model, meta = _apply_model_step(df, model_cfg, returns_col)
        out[asset] = frame
        models[asset] = model
        metas[asset] = meta

    if len(out) == 1:
        only_asset = next(iter(sorted(out)))
        return out, models[only_asset], metas[only_asset]
    return out, models, _aggregate_model_meta(metas)


def _apply_signals_to_assets(
    asset_frames: dict[str, pd.DataFrame],
    *,
    signals_cfg: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """
    Handle signals to assets inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    out: dict[str, pd.DataFrame] = {}
    for asset, df in sorted(asset_frames.items()):
        out[asset] = _apply_signal_step(df, signals_cfg)
    return out


def _resolve_vol_col(df: pd.DataFrame, backtest_cfg: dict[str, Any], risk_cfg: dict[str, Any]) -> str | None:
    """
    Handle volatility col inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    vol_col = backtest_cfg.get("vol_col") or risk_cfg.get("vol_col")
    if vol_col:
        return vol_col
    for cand in ("vol_rolling_20", "vol_ewma_20", "vol_rolling_60", "vol_ewma_60"):
        if cand in df.columns:
            return cand
    return None


def _validate_returns_series(returns: pd.Series, returns_type: str) -> None:
    """
    Handle returns series inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if returns_type == "simple" and (returns < -1.0).any():
        raise ValueError("Simple returns contain values < -1.0; check returns_type or data.")


def _validate_returns_frame(returns: pd.DataFrame, returns_type: str) -> None:
    """
    Handle returns frame inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if returns_type == "simple" and (returns < -1.0).any().any():
        raise ValueError("Simple returns contain values < -1.0; check returns_type or data.")


def _build_storage_context(data_cfg: dict[str, Any], *, symbols: list[str], pit_cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Handle storage context inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    return {
        "symbols": list(symbols),
        "source": data_cfg.get("source"),
        "interval": data_cfg.get("interval"),
        "start": data_cfg.get("start"),
        "end": data_cfg.get("end"),
        "pit": dict(pit_cfg or {}),
        "pit_hash_sha256": _pit_config_hash(pit_cfg),
    }


def _snapshot_context_matches(snapshot_meta: dict[str, Any], expected_context: dict[str, Any]) -> bool:
    """
    Verify that a cached snapshot was built under the same data and PIT context requested by
    the current run.
    """
    snapshot_context = dict(snapshot_meta.get("context", {}) or {})
    return _stable_json_dumps(snapshot_context) == _stable_json_dumps(expected_context)


def _load_asset_frames(
    data_cfg: dict[str, Any],
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """
    Handle asset frames inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    symbols = _resolve_symbols(data_cfg)
    if not symbols:
        raise ValueError("No symbols resolved from config.")

    storage_cfg = dict(data_cfg.get("storage", {}) or {})
    storage_mode = str(storage_cfg.get("mode", "live"))
    dataset_id = str(storage_cfg.get("dataset_id") or _default_dataset_id(data_cfg))
    raw_dir = storage_cfg.get("raw_dir", "data/raw")
    load_path = storage_cfg.get("load_path")
    pit_cfg = dict(data_cfg.get("pit", {}) or {})
    expected_context = _build_storage_context(data_cfg, symbols=symbols, pit_cfg=pit_cfg)
    storage_meta: dict[str, Any] = {
        "mode": storage_mode,
        "dataset_id": dataset_id,
        "loaded_from_cache": False,
        "saved_raw_snapshot": None,
    }

    asset_frames: dict[str, pd.DataFrame] | None = None
    if storage_mode in {"live_or_cached", "cached_only"}:
        try:
            cached_frames, snapshot_meta = load_dataset_snapshot(
                stage="raw",
                root_dir=raw_dir,
                dataset_id=dataset_id,
                load_path=load_path,
            )
            if not _snapshot_context_matches(snapshot_meta, expected_context):
                storage_meta["cache_context_mismatch"] = True
                storage_meta["loaded_snapshot"] = snapshot_meta
                if storage_mode == "cached_only":
                    raise ValueError(
                        "Cached dataset snapshot context does not match the requested data/PIT configuration."
                    )
            else:
                asset_frames = cached_frames
                storage_meta["loaded_from_cache"] = True
                storage_meta["loaded_snapshot"] = snapshot_meta
        except FileNotFoundError:
            if storage_mode == "cached_only":
                raise

    if asset_frames is None:
        load_kwargs = {
            "start": data_cfg.get("start"),
            "end": data_cfg.get("end"),
            "interval": data_cfg.get("interval", "1d"),
            "source": data_cfg.get("source", "yahoo"),
            "api_key": data_cfg.get("api_key"),
        }
        raw_frames = (
            {symbols[0]: load_ohlcv(symbol=symbols[0], **load_kwargs)}
            if len(symbols) == 1
            else load_ohlcv_panel(symbols=symbols, **load_kwargs)
        )

        pit_meta_by_asset: dict[str, Any] = {}
        asset_frames = {}
        for asset, df in sorted(raw_frames.items()):
            hardened_df, pit_meta = apply_pit_hardening(df, pit_cfg=pit_cfg, symbol=asset)
            validate_ohlcv(hardened_df)
            validate_data_contract(hardened_df)
            asset_frames[asset] = hardened_df
            pit_meta_by_asset[asset] = pit_meta

        storage_meta["pit_meta_by_asset"] = pit_meta_by_asset
        if bool(storage_cfg.get("save_raw", False)):
            storage_meta["saved_raw_snapshot"] = save_dataset_snapshot(
                asset_frames,
                dataset_id=dataset_id,
                stage="raw",
                root_dir=raw_dir,
                context=_build_storage_context(data_cfg, symbols=symbols, pit_cfg=pit_cfg),
            )
    else:
        for asset, df in sorted(asset_frames.items()):
            validate_ohlcv(df)
            validate_data_contract(df)

    return asset_frames, storage_meta


def _save_processed_snapshot_if_enabled(
    asset_frames: dict[str, pd.DataFrame],
    *,
    data_cfg: dict[str, Any],
    config_hash_sha256: str,
    feature_steps: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Handle processed snapshot if enabled inside the experiment orchestration layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    storage_cfg = dict(data_cfg.get("storage", {}) or {})
    if not bool(storage_cfg.get("save_processed", False)):
        return None

    dataset_id = str(storage_cfg.get("dataset_id") or _default_dataset_id(data_cfg))
    processed_dataset_id = f"{dataset_id}_{config_hash_sha256[:8]}"
    return save_dataset_snapshot(
        asset_frames,
        dataset_id=processed_dataset_id,
        stage="processed",
        root_dir=storage_cfg.get("processed_dir", "data/processed"),
        context={
            "base_dataset_id": dataset_id,
            "config_hash_sha256": config_hash_sha256,
            "feature_steps": list(feature_steps),
        },
    )


def _align_asset_column(
    asset_frames: dict[str, pd.DataFrame],
    *,
    column: str,
    how: str,
) -> pd.DataFrame:
    """
    Handle align asset column inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    series_map: dict[str, pd.Series] = {}
    for asset, df in sorted(asset_frames.items()):
        if column not in df.columns:
            raise KeyError(f"Column '{column}' not found for asset '{asset}'.")
        series_map[asset] = df[column].astype(float)

    out = pd.concat(series_map, axis=1, join=how).sort_index()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    out.columns = [str(col) for col in out.columns]
    return out


def _build_portfolio_constraints(portfolio_cfg: dict[str, Any]) -> PortfolioConstraints:
    """
    Handle portfolio constraints inside the experiment orchestration layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    constraints_cfg = dict(portfolio_cfg.get("constraints", {}) or {})
    return PortfolioConstraints(
        min_weight=float(constraints_cfg.get("min_weight", -1.0)),
        max_weight=float(constraints_cfg.get("max_weight", 1.0)),
        max_gross_leverage=float(constraints_cfg.get("max_gross_leverage", 1.0)),
        target_net_exposure=float(constraints_cfg.get("target_net_exposure", 0.0)),
        turnover_limit=(
            float(constraints_cfg["turnover_limit"])
            if constraints_cfg.get("turnover_limit") is not None
            else None
        ),
        group_max_exposure=(
            {str(k): float(v) for k, v in dict(constraints_cfg.get("group_max_exposure", {}) or {}).items()}
            or None
        ),
    )


def _run_single_asset_backtest(
    asset: str,
    df: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    model_meta: dict[str, Any],
) -> BacktestResult:
    """
    Handle single asset backtest inside the experiment orchestration layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    backtest_cfg = cfg["backtest"]
    risk_cfg = cfg["risk"]
    signal_col = backtest_cfg["signal_col"]
    returns_col = backtest_cfg["returns_col"]
    returns_type = backtest_cfg.get("returns_type", "simple")
    _validate_returns_series(df[returns_col].dropna(), returns_type)

    dd_cfg = risk_cfg.get("dd_guard") or {}
    dd_guard = dd_cfg.get("enabled", True)
    vol_col = _resolve_vol_col(df, backtest_cfg, risk_cfg)
    target_vol = risk_cfg.get("target_vol")
    if target_vol is not None and vol_col is None:
        raise ValueError("target_vol is set but no vol_col was found or configured.")

    bt_df = df
    if model_meta and model_meta.get("split_index") is not None:
        bt_subset = backtest_cfg.get("subset", "test")
        if bt_subset == "test":
            bt_df = df.iloc[int(model_meta["split_index"]) :]

    return run_backtest(
        bt_df,
        signal_col=signal_col,
        returns_col=returns_col,
        returns_type=returns_type,
        missing_return_policy=backtest_cfg.get("missing_return_policy", "raise_if_exposed"),
        cost_per_unit_turnover=risk_cfg.get("cost_per_turnover", 0.0),
        slippage_per_unit_turnover=risk_cfg.get("slippage_per_turnover", 0.0),
        target_vol=target_vol,
        vol_col=vol_col,
        max_leverage=risk_cfg.get("max_leverage", 3.0),
        dd_guard=dd_guard,
        max_drawdown=dd_cfg.get("max_drawdown", 0.2),
        cooloff_bars=dd_cfg.get("cooloff_bars", 20),
        periods_per_year=backtest_cfg.get("periods_per_year", 252),
    )


def _run_portfolio_backtest(
    asset_frames: dict[str, pd.DataFrame],
    *,
    cfg: dict[str, Any],
) -> tuple[PortfolioPerformance, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """
    Handle portfolio backtest inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    backtest_cfg = cfg["backtest"]
    risk_cfg = cfg["risk"]
    portfolio_cfg = cfg["portfolio"]
    alignment = cfg["data"].get("alignment", "inner")

    signal_col = backtest_cfg["signal_col"]
    returns_col = backtest_cfg["returns_col"]
    returns_type = backtest_cfg.get("returns_type", "simple")

    signals = _align_asset_column(asset_frames, column=signal_col, how=alignment)
    asset_returns = _align_asset_column(asset_frames, column=returns_col, how=alignment)
    if returns_type == "log":
        asset_returns = np.expm1(asset_returns)
    elif returns_type != "simple":
        raise ValueError("backtest.returns_type must be 'simple' or 'log'.")
    _validate_returns_frame(asset_returns, "simple")

    constraints = _build_portfolio_constraints(portfolio_cfg)
    asset_groups = {str(k): str(v) for k, v in dict(portfolio_cfg.get("asset_groups", {}) or {}).items()}
    construction = str(portfolio_cfg.get("construction", "signal_weights"))

    if construction == "mean_variance":
        expected_return_col = str(portfolio_cfg.get("expected_return_col") or signal_col)
        expected_returns = _align_asset_column(asset_frames, column=expected_return_col, how=alignment)
        covariance_by_date = build_rolling_covariance_by_date(
            asset_returns,
            window=int(portfolio_cfg.get("covariance_window", 60)),
        )
        weights, diagnostics = build_optimized_weights_over_time(
            expected_returns,
            covariance_by_date=covariance_by_date,
            constraints=constraints,
            asset_to_group=asset_groups or None,
            risk_aversion=float(portfolio_cfg.get("risk_aversion", 5.0)),
            trade_aversion=float(portfolio_cfg.get("trade_aversion", 0.0)),
        )
    else:
        expected_return_col = None
        weights, diagnostics = build_weights_from_signals_over_time(
            signals,
            constraints=constraints,
            asset_to_group=asset_groups or None,
            long_short=bool(portfolio_cfg.get("long_short", True)),
            gross_target=float(portfolio_cfg.get("gross_target", 1.0)),
        )

    performance = compute_portfolio_performance(
        weights,
        asset_returns,
        missing_return_policy=backtest_cfg.get("missing_return_policy", "raise_if_exposed"),
        cost_per_turnover=risk_cfg.get("cost_per_turnover", 0.0),
        slippage_per_turnover=risk_cfg.get("slippage_per_turnover", 0.0),
        periods_per_year=backtest_cfg.get("periods_per_year", 252),
    )

    portfolio_meta = {
        "construction": construction,
        "asset_count": int(len(asset_frames)),
        "alignment": alignment,
        "expected_return_col": expected_return_col,
        "avg_gross_exposure": float(diagnostics["gross_exposure"].mean()) if not diagnostics.empty else 0.0,
        "avg_net_exposure": float(diagnostics["net_exposure"].mean()) if not diagnostics.empty else 0.0,
        "avg_turnover": float(diagnostics["turnover"].mean()) if not diagnostics.empty else 0.0,
    }
    return performance, weights, diagnostics, portfolio_meta


def _compute_subset_metrics(
    *,
    net_returns: pd.Series,
    turnover: pd.Series,
    costs: pd.Series,
    gross_returns: pd.Series,
    periods_per_year: int,
    mask: pd.Series,
) -> dict[str, float]:
    """
    Handle subset metrics inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    aligned_mask = mask.reindex(net_returns.index).fillna(False).astype(bool)
    if not bool(aligned_mask.any()):
        return {}
    return compute_backtest_metrics(
        net_returns=net_returns.loc[aligned_mask],
        periods_per_year=periods_per_year,
        turnover=turnover.loc[aligned_mask],
        costs=costs.loc[aligned_mask],
        gross_returns=gross_returns.loc[aligned_mask],
    )


def _build_fold_backtest_summaries(
    *,
    source_index: pd.Index,
    net_returns: pd.Series,
    turnover: pd.Series,
    costs: pd.Series,
    gross_returns: pd.Series,
    periods_per_year: int,
    folds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Handle fold backtest summaries inside the experiment orchestration layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    out: list[dict[str, Any]] = []
    for fold in folds:
        start = int(fold["test_start"])
        end = int(fold["test_end"])
        fold_index = source_index[start:end]
        mask = pd.Series(net_returns.index.isin(fold_index), index=net_returns.index)
        summary = _compute_subset_metrics(
            net_returns=net_returns,
            turnover=turnover,
            costs=costs,
            gross_returns=gross_returns,
            periods_per_year=periods_per_year,
            mask=mask,
        )
        out.append(
            {
                "fold": int(fold["fold"]),
                "test_rows": int(fold.get("test_rows", end - start)),
                "metrics": summary,
            }
        )
    return out


def _build_single_asset_evaluation(
    asset: str,
    df: pd.DataFrame,
    *,
    performance: BacktestResult,
    model_meta: dict[str, Any],
    periods_per_year: int,
) -> dict[str, Any]:
    """
    Handle single asset evaluation inside the experiment orchestration layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    evaluation = {
        "scope": "timeline",
        "primary_summary": dict(performance.summary),
        "timeline_summary": dict(performance.summary),
    }

    if "pred_is_oos" not in df.columns:
        return evaluation

    oos_mask = df["pred_is_oos"].reindex(performance.returns.index).fillna(False).astype(bool)
    oos_summary = _compute_subset_metrics(
        net_returns=performance.returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        mask=oos_mask,
    )
    fold_summaries = _build_fold_backtest_summaries(
        source_index=df.index,
        net_returns=performance.returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        folds=list(model_meta.get("folds", []) or []),
    )

    evaluation.update(
        {
            "scope": "strict_oos_only",
            "primary_summary": oos_summary or dict(performance.summary),
            "oos_only_summary": oos_summary,
            "oos_rows": int(oos_mask.sum()),
            "oos_coverage": float(oos_mask.mean()) if len(oos_mask) > 0 else 0.0,
            "fold_backtest_summaries": fold_summaries,
            "model_oos_summary": dict(model_meta.get("oos_classification_summary", {}) or {}),
            "asset": asset,
        }
    )
    return evaluation


def _build_portfolio_evaluation(
    asset_frames: dict[str, pd.DataFrame],
    *,
    performance: PortfolioPerformance,
    model_meta: dict[str, Any],
    periods_per_year: int,
    alignment: str,
) -> dict[str, Any]:
    """
    Handle portfolio evaluation inside the experiment orchestration layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    evaluation = {
        "scope": "timeline",
        "primary_summary": dict(performance.summary),
        "timeline_summary": dict(performance.summary),
    }

    if not model_meta:
        return evaluation

    oos_by_asset: dict[str, pd.Series] = {}
    if "per_asset" in model_meta:
        for asset in sorted(model_meta["per_asset"]):
            frame = asset_frames.get(asset)
            if frame is not None and "pred_is_oos" in frame.columns:
                oos_by_asset[asset] = frame["pred_is_oos"].astype(float)
    elif "pred_is_oos" in next(iter(asset_frames.values())).columns:
        only_asset = next(iter(sorted(asset_frames)))
        oos_by_asset[only_asset] = asset_frames[only_asset]["pred_is_oos"].astype(float)

    if not oos_by_asset:
        return evaluation

    oos_df = pd.concat(oos_by_asset, axis=1, join=alignment).sort_index()
    if isinstance(oos_df.columns, pd.MultiIndex):
        oos_df.columns = oos_df.columns.get_level_values(0)
    oos_mask = oos_df.reindex(performance.net_returns.index).fillna(0.0).astype(bool).any(axis=1)
    oos_summary = _compute_subset_metrics(
        net_returns=performance.net_returns,
        turnover=performance.turnover,
        costs=performance.costs,
        gross_returns=performance.gross_returns,
        periods_per_year=periods_per_year,
        mask=oos_mask,
    )
    evaluation.update(
        {
            "scope": "strict_oos_only",
            "primary_summary": oos_summary or dict(performance.summary),
            "oos_only_summary": oos_summary,
            "oos_active_dates": int(oos_mask.sum()),
            "oos_date_coverage": float(oos_mask.mean()) if len(oos_mask) > 0 else 0.0,
            "model_oos_summary": dict(model_meta.get("oos_classification_summary", {}) or {}),
            "folds_by_asset": {
                asset: list(meta.get("folds", []) or [])
                for asset, meta in dict(model_meta.get("per_asset", {}) or {}).items()
            },
        }
    )
    return evaluation


def _compute_monitoring_for_asset(
    df: pd.DataFrame,
    *,
    meta: dict[str, Any],
    monitoring_cfg: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Handle monitoring for asset inside the experiment orchestration layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    feature_cols = list(meta.get("feature_cols", []) or [])
    if not feature_cols or "pred_is_oos" not in df.columns:
        return None

    oos_mask = df["pred_is_oos"].astype(bool)
    ref = df.loc[~oos_mask, feature_cols]
    cur = df.loc[oos_mask, feature_cols]
    if ref.empty or cur.empty:
        return None

    return compute_feature_drift(
        ref,
        cur,
        feature_cols=feature_cols,
        psi_threshold=float(monitoring_cfg.get("psi_threshold", 0.2)),
        n_bins=int(monitoring_cfg.get("n_bins", 10)),
    )


def _compute_monitoring_report(
    asset_frames: dict[str, pd.DataFrame],
    *,
    model_meta: dict[str, Any],
    monitoring_cfg: dict[str, Any],
) -> dict[str, Any]:
    """
    Handle monitoring report inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if not bool(monitoring_cfg.get("enabled", False)):
        return {}

    per_asset: dict[str, Any] = {}
    if "per_asset" in model_meta:
        for asset, meta in sorted(dict(model_meta.get("per_asset", {}) or {}).items()):
            report = _compute_monitoring_for_asset(
                asset_frames[asset],
                meta=meta,
                monitoring_cfg=monitoring_cfg,
            )
            if report:
                per_asset[asset] = report
    elif model_meta:
        only_asset = next(iter(sorted(asset_frames)))
        report = _compute_monitoring_for_asset(
            asset_frames[only_asset],
            meta=model_meta,
            monitoring_cfg=monitoring_cfg,
        )
        if report:
            per_asset[only_asset] = report

    if not per_asset:
        return {}

    return {
        "asset_count": int(len(per_asset)),
        "drifted_feature_count": int(
            sum(int(report.get("drifted_feature_count", 0)) for report in per_asset.values())
        ),
        "feature_count": int(sum(int(report.get("feature_count", 0)) for report in per_asset.values())),
        "per_asset": per_asset,
    }


def _build_execution_output(
    *,
    asset_frames: dict[str, pd.DataFrame],
    execution_cfg: dict[str, Any],
    portfolio_weights: pd.DataFrame | None,
    performance: BacktestResult | PortfolioPerformance,
    alignment: str,
) -> tuple[dict[str, Any], pd.DataFrame | None]:
    """
    Handle execution output inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if not bool(execution_cfg.get("enabled", False)):
        return {}, None

    capital = float(execution_cfg.get("capital", 1_000_000.0))
    price_col = str(execution_cfg.get("price_col", "close"))
    current_weights_cfg = dict(execution_cfg.get("current_weights", {}) or {})
    current_weights = pd.Series(current_weights_cfg, dtype=float) if current_weights_cfg else None

    if portfolio_weights is not None:
        target_weights = portfolio_weights.iloc[-1].astype(float)
        prices = _align_asset_column(asset_frames, column=price_col, how=alignment).reindex(
            portfolio_weights.index
        )
        latest_prices = prices.iloc[-1].astype(float)
        as_of = portfolio_weights.index[-1]
    else:
        asset = next(iter(sorted(asset_frames)))
        bt = performance
        assert isinstance(bt, BacktestResult)
        target_weights = pd.Series({asset: float(bt.positions.iloc[-1])}, dtype=float)
        latest_price = float(asset_frames[asset][price_col].reindex(bt.returns.index).iloc[-1])
        latest_prices = pd.Series({asset: latest_price}, dtype=float)
        as_of = bt.returns.index[-1]

    orders = build_rebalance_orders(
        target_weights,
        prices=latest_prices,
        capital=capital,
        current_weights=current_weights,
        min_trade_notional=float(execution_cfg.get("min_trade_notional", 0.0)),
    )
    execution_meta = {
        "mode": "paper",
        "capital": capital,
        "as_of": str(pd.Timestamp(as_of)),
        "order_count": int(len(orders)),
        "gross_target": float(target_weights.abs().sum()),
    }
    return execution_meta, orders


def _data_stats_payload(data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict[str, Any]:
    """
    Handle data stats payload inside the experiment orchestration layer. The helper isolates one
    focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if isinstance(data, pd.DataFrame):
        return {
            "asset_count": 1,
            "rows": int(len(data)),
            "columns": int(len(data.columns)),
            "start": str(data.index.min()) if not data.empty else None,
            "end": str(data.index.max()) if not data.empty else None,
        }

    long_frame = asset_frames_to_long_frame(data)
    return {
        "asset_count": int(len(data)),
        "rows": int(len(long_frame)),
        "columns": int(len(long_frame.columns)),
        "assets": sorted(data),
        "rows_by_asset": {asset: int(len(df)) for asset, df in sorted(data.items())},
        "start": str(long_frame["timestamp"].min()) if not long_frame.empty else None,
        "end": str(long_frame["timestamp"].max()) if not long_frame.empty else None,
    }


def _resolved_feature_columns(model_meta: dict[str, Any]) -> list[str] | dict[str, list[str]] | None:
    """
    Handle resolved feature columns inside the experiment orchestration layer. The helper
    isolates one focused responsibility so the surrounding code remains modular, readable, and
    easier to test.
    """
    if not model_meta:
        return None
    if "feature_cols" in model_meta:
        return list(model_meta.get("feature_cols", []) or [])
    if "per_asset" in model_meta:
        return {
            asset: list(meta.get("feature_cols", []) or [])
            for asset, meta in sorted(dict(model_meta.get("per_asset", {}) or {}).items())
        }
    return None


def _save_artifacts(
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
    """
    Handle artifacts inside the experiment orchestration layer. The helper isolates one focused
    responsibility so the surrounding code remains modular, readable, and easier to test.
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = run_dir / "config_used.yaml"
    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

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
        "resolved_feature_columns": _resolved_feature_columns(model_meta),
        "data_stats": _data_stats_payload(data),
        "reproducibility": {
            "config_hash_sha256": config_hash_sha256,
            "data_hash_sha256": data_fingerprint.get("sha256"),
            "runtime": run_metadata.get("runtime", {}),
        },
    }
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    metadata_path = run_dir / "run_metadata.json"
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(run_metadata, f, indent=2, default=str)

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
        with monitoring_path.open("w", encoding="utf-8") as f:
            json.dump(monitoring, f, indent=2, default=str)

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
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    artifacts["manifest"] = str(manifest_path)

    return artifacts


def run_experiment(config_path: str | Path) -> ExperimentResult:
    """
    Run experiment end to end for the experiment orchestration layer. The function coordinates a
    higher-level workflow rather than leaving the caller to stitch together every step manually.
    """
    cfg = load_experiment_config(config_path)
    runtime_applied = apply_runtime_reproducibility(cfg.get("runtime", {}))
    config_hash_sha256, config_hash_input = compute_config_hash(cfg)

    data_cfg = cfg["data"]
    raw_asset_frames, storage_meta = _load_asset_frames(data_cfg)
    raw_long_frame = asset_frames_to_long_frame(raw_asset_frames)
    data_fingerprint = compute_dataframe_fingerprint(raw_long_frame)

    feature_asset_frames = _apply_steps_to_assets(
        raw_asset_frames,
        feature_steps=list(cfg.get("features", []) or []),
    )
    processed_snapshot = _save_processed_snapshot_if_enabled(
        feature_asset_frames,
        data_cfg=data_cfg,
        config_hash_sha256=config_hash_sha256,
        feature_steps=list(cfg.get("features", []) or []),
    )
    if processed_snapshot is not None:
        storage_meta["saved_processed_snapshot"] = processed_snapshot

    model_cfg = dict(cfg.get("model", {"kind": "none"}) or {})
    model_cfg.setdefault("runtime", cfg.get("runtime", {}))
    returns_col = cfg.get("backtest", {}).get("returns_col")
    model_asset_frames, model, model_meta = _apply_model_to_assets(
        feature_asset_frames,
        model_cfg=model_cfg,
        returns_col=returns_col,
    )

    asset_frames = _apply_signals_to_assets(
        model_asset_frames,
        signals_cfg=dict(cfg.get("signals", {}) or {}),
    )

    is_portfolio = bool(cfg.get("portfolio", {}).get("enabled")) or len(asset_frames) > 1
    portfolio_weights: pd.DataFrame | None = None
    portfolio_diagnostics: pd.DataFrame | None = None
    portfolio_meta: dict[str, Any] = {}

    if is_portfolio:
        performance, portfolio_weights, portfolio_diagnostics, portfolio_meta = _run_portfolio_backtest(
            asset_frames,
            cfg=cfg,
        )
        evaluation = _build_portfolio_evaluation(
            asset_frames,
            performance=performance,
            model_meta=model_meta,
            periods_per_year=cfg["backtest"].get("periods_per_year", 252),
            alignment=cfg["data"].get("alignment", "inner"),
        )
    else:
        asset = next(iter(sorted(asset_frames)))
        performance = _run_single_asset_backtest(
            asset,
            asset_frames[asset],
            cfg=cfg,
            model_meta=model_meta,
        )
        evaluation = _build_single_asset_evaluation(
            asset,
            asset_frames[asset],
            performance=performance,
            model_meta=model_meta,
            periods_per_year=cfg["backtest"].get("periods_per_year", 252),
        )

    monitoring = _compute_monitoring_report(
        asset_frames,
        model_meta=model_meta,
        monitoring_cfg=dict(cfg.get("monitoring", {}) or {}),
    )
    execution, execution_orders = _build_execution_output(
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
                _build_storage_context(
                    data_cfg,
                    symbols=_resolve_symbols(data_cfg),
                    pit_cfg=dict(data_cfg.get("pit", {}) or {}),
                )
                | {"storage": storage_meta}
            ),
            model_meta=model_meta,
        )
        base_dir = Path(logging_cfg.get("output_dir", "logs/experiments"))
        run_name = logging_cfg.get("run_name", Path(config_path).stem)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = in_project(base_dir) / f"{run_name}_{timestamp}"
        artifacts = _save_artifacts(
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a config-based trading experiment.")
    parser.add_argument("config", help="Path to experiment YAML (relative to config/ or absolute).")
    args = parser.parse_args()

    result = run_experiment(args.config)

    print("Experiment completed")
    print("Primary summary:")
    for k, v in result.evaluation.get("primary_summary", {}).items():
        print(f"  {k}: {v}")
    if result.artifacts:
        print("")
        print("Artifacts:")
        for k, v in result.artifacts.items():
            print(f"  {k}: {v}")
