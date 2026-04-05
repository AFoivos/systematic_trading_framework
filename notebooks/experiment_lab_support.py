from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yaml
from plotly.subplots import make_subplots

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.experiments.registry import FEATURE_REGISTRY
from src.experiments.orchestration.types import ExperimentResult
from src.experiments.runner import _load_asset_frames, run_experiment
from src.utils.config import load_experiment_config


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve()).resolve()
    current = current if current.is_dir() else current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise FileNotFoundError("Could not locate the repository root from notebooks/experiment_lab_support.py.")


REPO_ROOT = find_repo_root()


TOP_EXPERIMENTS: dict[str, dict[str, Any]] = {
    "shock_meta_long_only": {
        "label": "Shock Meta XGBoost Long Only",
        "config_path": "config/experiments/btcusd_1h_shock_meta_xgboost_long_only.yaml",
        "logged_run_dir": "logs/experiments/btcusd_1h_shock_meta_xgboost_long_only_20260326_145348_444032_d1c5b87d",
        "selection_note": (
            "Strongest logged family in the repo. It pairs causal shock features with a long-only "
            "meta-label XGBoost filter and produced the best logged OOS Sharpe among distinct families."
        ),
        "logged_metrics": {
            "sharpe": 0.6530762489440064,
            "net_pnl": 0.49740010899811,
            "cumulative_return": 0.5739825555302343,
            "max_drawdown": -0.16778413167995676,
        },
    },
    "xgboost_garch_baseline": {
        "label": "XGBoost Triple-Barrier + GARCH Baseline",
        "config_path": "config/experiments/btcusd_1h_dukas_xgboost_triple_barrier_garch_long_oos.yaml",
        "logged_run_dir": "logs/experiments/btcusd_1h_dukas_xgboost_triple_barrier_garch_long_oos_baseline_v3_20260324_224625_567765_76437e4f",
        "selection_note": (
            "Best canonical baseline family currently tracked in config/. It is simpler than the "
            "shock-meta path and is the cleanest benchmark for feature, target, and signal sweeps."
        ),
        "logged_metrics": {
            "sharpe": 0.41875472601143626,
            "net_pnl": 0.017863291235971506,
            "cumulative_return": 0.017862104040601068,
            "max_drawdown": -0.012322474049278775,
        },
    },
}


SUMMARY_ORDER = [
    "sharpe",
    "sortino",
    "calmar",
    "annualized_return",
    "annualized_vol",
    "cumulative_return",
    "net_pnl",
    "gross_pnl",
    "total_cost",
    "cost_drag",
    "profit_factor",
    "hit_rate",
    "avg_turnover",
    "total_turnover",
    "max_drawdown",
]


BASE_PRICE_COLUMNS = {"open", "high", "low", "close", "volume"}
STRATEGY_OUTPUT_COLUMNS = {
    "strategy_equity",
    "strategy_net_returns",
    "strategy_gross_returns",
    "strategy_costs",
    "strategy_positions",
    "strategy_turnover",
    "strategy_drawdown",
    "oos_mask",
    "pred_is_oos",
}


def resolve_repo_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        workspace_prefix = Path("/workspace")
        try:
            relative_to_workspace = path.relative_to(workspace_prefix)
        except ValueError:
            return path
        return (REPO_ROOT / relative_to_workspace).resolve()
    return (REPO_ROOT / path).resolve()


def load_yaml(path_like: str | Path) -> dict[str, Any]:
    path = resolve_repo_path(path_like)
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping at {path}")
    return payload


def load_json(path_like: str | Path) -> dict[str, Any]:
    path = resolve_repo_path(path_like)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def merge_nested_overrides(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(base))
    for key, value in overrides.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = merge_nested_overrides(existing, value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _update_named_feature_steps(
    features: list[dict[str, Any]],
    step_param_updates: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    updated_features = deepcopy(list(features))
    for step_name, params_update in step_param_updates.items():
        matched = False
        for step_cfg in updated_features:
            if str(step_cfg.get("step")) != str(step_name):
                continue
            params = dict(step_cfg.get("params", {}) or {})
            step_cfg["params"] = merge_nested_overrides(params, dict(params_update))
            matched = True
        if not matched:
            raise KeyError(f"Feature step '{step_name}' was not found in the config.")
    return updated_features


def _select_named_feature_steps(
    features: list[dict[str, Any]],
    selected_steps: list[str],
) -> list[dict[str, Any]]:
    requested = {str(step_name) for step_name in list(selected_steps or [])}
    available = {str(step_cfg.get("step")) for step_cfg in list(features)}
    missing = sorted(requested - available)
    if missing:
        raise KeyError(f"Feature steps were requested but not found in the config: {missing}")
    return [deepcopy(step_cfg) for step_cfg in list(features) if str(step_cfg.get("step")) in requested]


def build_mutated_config(
    config_path: str | Path,
    *,
    overrides: Mapping[str, Any] | None = None,
    selected_feature_steps: list[str] | None = None,
    feature_step_updates: Mapping[str, Mapping[str, Any]] | None = None,
    signal_param_updates: Mapping[str, Any] | None = None,
    model_param_updates: Mapping[str, Any] | None = None,
    model_feature_cols: list[str] | None = None,
    target_updates: Mapping[str, Any] | None = None,
    risk_updates: Mapping[str, Any] | None = None,
    backtest_updates: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_yaml(resolve_repo_path(config_path))
    cfg = merge_nested_overrides(cfg, overrides or {})

    if selected_feature_steps is not None:
        cfg["features"] = _select_named_feature_steps(list(cfg.get("features", []) or []), selected_feature_steps)

    if feature_step_updates:
        cfg["features"] = _update_named_feature_steps(list(cfg.get("features", []) or []), feature_step_updates)

    if signal_param_updates:
        signals_cfg = dict(cfg.get("signals", {}) or {})
        params = dict(signals_cfg.get("params", {}) or {})
        signals_cfg["params"] = merge_nested_overrides(params, dict(signal_param_updates))
        cfg["signals"] = signals_cfg

    if model_param_updates or model_feature_cols is not None or target_updates:
        model_cfg = dict(cfg.get("model", {}) or {})
        if model_param_updates:
            model_cfg["params"] = merge_nested_overrides(dict(model_cfg.get("params", {}) or {}), dict(model_param_updates))
        if model_feature_cols is not None:
            model_cfg["feature_cols"] = list(model_feature_cols)
        if target_updates:
            model_cfg["target"] = merge_nested_overrides(dict(model_cfg.get("target", {}) or {}), dict(target_updates))
        cfg["model"] = model_cfg

    if risk_updates:
        cfg["risk"] = merge_nested_overrides(dict(cfg.get("risk", {}) or {}), dict(risk_updates))
    if backtest_updates:
        cfg["backtest"] = merge_nested_overrides(dict(cfg.get("backtest", {}) or {}), dict(backtest_updates))

    return cfg


def parse_override_text(text: str | None) -> dict[str, Any]:
    if not text or not text.strip():
        return {}
    payload = yaml.safe_load(text)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Override text must parse into a YAML/JSON mapping.")
    return payload


def _read_numeric_series(path_like: str | Path, *, default_name: str) -> pd.Series:
    path = resolve_repo_path(path_like)
    if not path.exists():
        return pd.Series(dtype=float, name=default_name)
    frame = pd.read_csv(path)
    if frame.empty:
        return pd.Series(dtype=float, name=default_name)
    index_col = frame.columns[0]
    frame[index_col] = pd.to_datetime(frame[index_col], errors="coerce")
    numeric_cols = [
        col for col in frame.columns[1:] if pd.to_numeric(frame[col], errors="coerce").notna().any()
    ]
    if not numeric_cols:
        return pd.Series(dtype=float, name=default_name)
    series = pd.to_numeric(frame[numeric_cols[0]], errors="coerce")
    series.index = frame[index_col]
    series = series.sort_index()
    series.name = default_name
    return series


def _load_price_frame_from_config(cfg: Mapping[str, Any]) -> pd.DataFrame:
    data_cfg = dict(cfg.get("data", {}) or {})
    storage_cfg = dict(data_cfg.get("storage", {}) or {})
    source = str(data_cfg.get("source", "") or "")
    if source != "dukascopy_csv":
        return pd.DataFrame()

    load_path = storage_cfg.get("load_path")
    if not load_path:
        return pd.DataFrame()

    frame = pd.read_csv(resolve_repo_path(str(load_path)))
    if frame.empty:
        return pd.DataFrame()

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    frame = frame.set_index("timestamp").sort_index()

    start = data_cfg.get("start")
    end = data_cfg.get("end")
    if start:
        start_ts = pd.to_datetime(start, utc=True).tz_localize(None)
        frame = frame.loc[frame.index >= start_ts]
    if end:
        end_ts = pd.to_datetime(end, utc=True).tz_localize(None)
        frame = frame.loc[frame.index <= end_ts]

    return frame.loc[:, ["open", "high", "low", "close", "volume"]].copy()


def _extract_primary_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    evaluation = dict(payload.get("evaluation", {}) or {})
    primary = dict(evaluation.get("primary_summary", {}) or {})
    return primary or dict(payload.get("summary", {}) or {})


def build_summary_frame(summary: Mapping[str, Any]) -> pd.DataFrame:
    ordered_metrics = [metric for metric in SUMMARY_ORDER if metric in summary]
    remaining = [metric for metric in summary if metric not in ordered_metrics]
    metrics = ordered_metrics + sorted(remaining)
    rows = [{"metric": metric, "value": summary[metric]} for metric in metrics]
    return pd.DataFrame(rows)


def list_available_feature_steps() -> pd.DataFrame:
    rows = [
        {
            "step": step_name,
            "function": getattr(feature_fn, "__name__", type(feature_fn).__name__),
        }
        for step_name, feature_fn in sorted(FEATURE_REGISTRY.items())
    ]
    return pd.DataFrame(rows)


def build_configured_feature_steps_frame(cfg: Mapping[str, Any]) -> pd.DataFrame:
    rows = []
    for idx, step_cfg in enumerate(list(cfg.get("features", []) or []), start=1):
        rows.append(
            {
                "step_order": idx,
                "step": step_cfg.get("step"),
                "enabled": bool(step_cfg.get("enabled", True)),
                "params": dict(step_cfg.get("params", {}) or {}),
                "outputs": dict(step_cfg.get("outputs", {}) or {}) or None,
            }
        )
    return pd.DataFrame(rows)


def build_feature_step_inventory(
    raw_frame: pd.DataFrame,
    feature_steps: list[dict[str, Any]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    current = raw_frame.copy()
    for idx, raw_step in enumerate(list(feature_steps or []), start=1):
        step_cfg = deepcopy(dict(raw_step))
        if step_cfg.get("enabled", True) is False:
            continue
        step_name = str(step_cfg.get("step", f"step_{idx}"))
        before_columns = list(current.columns)
        current = apply_feature_steps(current, [step_cfg])
        added_columns = [column for column in current.columns if column not in before_columns]
        for feature_column in added_columns:
            rows.append(
                {
                    "step_order": idx,
                    "step": step_name,
                    "feature_column": feature_column,
                    "params": dict(step_cfg.get("params", {}) or {}),
                }
            )
    return pd.DataFrame(rows)


def build_feature_column_catalog(
    frame: pd.DataFrame,
    *,
    step_inventory: pd.DataFrame | None = None,
    price_col: str = "close",
) -> pd.DataFrame:
    reserved_columns = BASE_PRICE_COLUMNS | STRATEGY_OUTPUT_COLUMNS
    numeric_cols = [
        col
        for col in frame.columns
        if col not in reserved_columns and pd.api.types.is_numeric_dtype(frame[col]) and frame[col].notna().any()
    ]
    step_lookup: dict[str, str] = {}
    step_order_lookup: dict[str, int] = {}
    if step_inventory is not None and not step_inventory.empty:
        for row in step_inventory.itertuples(index=False):
            feature_column = str(getattr(row, "feature_column"))
            step_lookup[feature_column] = str(getattr(row, "step"))
            step_order_lookup[feature_column] = int(getattr(row, "step_order"))

    price_series = _coerce_numeric_series(frame, price_col) if price_col in frame.columns else pd.Series(dtype=float)
    rows: list[dict[str, Any]] = []
    for feature_column in numeric_cols:
        series = _coerce_numeric_series(frame, feature_column).replace([np.inf, -np.inf], np.nan)
        corr_to_close = float(series.corr(price_series)) if not price_series.empty else np.nan
        last_valid = series.dropna()
        rows.append(
            {
                "step_order": step_order_lookup.get(feature_column),
                "step": step_lookup.get(feature_column),
                "feature_column": feature_column,
                "non_null_pct": float(series.notna().mean()),
                "na_pct": float(series.isna().mean()),
                "mean": float(series.mean()) if series.notna().any() else np.nan,
                "std": float(series.std(ddof=0)) if series.notna().any() else np.nan,
                "min": float(series.min()) if series.notna().any() else np.nan,
                "max": float(series.max()) if series.notna().any() else np.nan,
                "last_value": float(last_valid.iloc[-1]) if not last_valid.empty else np.nan,
                "corr_to_close": corr_to_close,
                "abs_corr_to_close": abs(corr_to_close) if np.isfinite(corr_to_close) else np.nan,
            }
        )

    columns = [
        "step_order",
        "step",
        "feature_column",
        "non_null_pct",
        "na_pct",
        "mean",
        "std",
        "min",
        "max",
        "last_value",
        "corr_to_close",
        "abs_corr_to_close",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    catalog = pd.DataFrame(rows)
    return catalog.sort_values(["step_order", "feature_column"], na_position="last").reset_index(drop=True)


def _configured_signal_columns(cfg: Mapping[str, Any]) -> list[str]:
    signals_cfg = dict(cfg.get("signals", {}) or {})
    params = dict(signals_cfg.get("params", {}) or {})
    keys = [
        "signal_col",
        "base_signal_col",
        "prob_col",
        "vol_col",
        "action_col",
        "returns_input_col",
    ]
    values = [str(params[key]) for key in keys if params.get(key)]
    backtest_signal = dict(cfg.get("backtest", {}) or {}).get("signal_col")
    if backtest_signal:
        values.append(str(backtest_signal))
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def build_feature_signal_catalog(frame: pd.DataFrame, cfg: Mapping[str, Any]) -> dict[str, list[str]]:
    numeric_cols = [
        col
        for col in frame.columns
        if pd.api.types.is_numeric_dtype(frame[col]) and frame[col].notna().any()
    ]
    configured_model_features = [
        str(col)
        for col in list(dict(cfg.get("model", {}) or {}).get("feature_cols", []) or [])
        if str(col) in numeric_cols
    ]
    configured_signal_cols = [col for col in _configured_signal_columns(cfg) if col in numeric_cols]

    prediction_candidates = sorted(
        {
            col
            for col in numeric_cols
            if col.startswith("pred_")
            or col.startswith("stage")
            or col.endswith("_prob")
            or col.endswith("_ret")
            or col.endswith("_vol")
        }
    )
    signal_candidates = sorted(
        {
            *configured_signal_cols,
            *[col for col in numeric_cols if col.startswith("signal_")],
            *[col for col in numeric_cols if col.startswith("shock_side_")],
        }
    )
    reserved = BASE_PRICE_COLUMNS | STRATEGY_OUTPUT_COLUMNS | set(signal_candidates) | set(prediction_candidates)
    feature_candidates = sorted({*configured_model_features, *[col for col in numeric_cols if col not in reserved]})

    return {
        "model_feature_cols": configured_model_features,
        "feature_candidates": feature_candidates,
        "signal_candidates": signal_candidates,
        "prediction_candidates": prediction_candidates,
        "strategy_columns": sorted([col for col in STRATEGY_OUTPUT_COLUMNS if col in frame.columns]),
    }


def _coerce_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise KeyError(f"Column '{column}' is not present in the analysis frame.")
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _zscore_series(series: pd.Series) -> pd.Series:
    clean = series.replace([np.inf, -np.inf], np.nan).astype(float)
    mean = clean.mean()
    std = clean.std(ddof=0)
    if not np.isfinite(std) or std == 0.0:
        return (clean - mean).fillna(0.0)
    return ((clean - mean) / std).fillna(0.0)


def _weighted_combo(series_map: Mapping[str, pd.Series], weights: Mapping[str, float] | None, *, name: str) -> pd.Series:
    if not series_map:
        return pd.Series(dtype=float, name=name)
    ordered_columns = list(series_map)
    vector = np.array([float((weights or {}).get(column, 1.0)) for column in ordered_columns], dtype=float)
    total = float(np.abs(vector).sum())
    if total == 0.0:
        vector = np.ones(len(ordered_columns), dtype=float)
        total = float(len(ordered_columns))
    matrix = pd.concat([series_map[column] for column in ordered_columns], axis=1).fillna(0.0)
    combo = matrix.to_numpy() @ vector / total
    return pd.Series(combo, index=matrix.index, name=name)


def build_feature_signal_combo_frame(
    frame: pd.DataFrame,
    *,
    feature_cols: list[str],
    signal_cols: list[str],
    feature_weights: Mapping[str, float] | None = None,
    signal_weights: Mapping[str, float] | None = None,
    normalize: bool = True,
) -> pd.DataFrame:
    selected = list(feature_cols) + list(signal_cols)
    if len(selected) < 2:
        raise ValueError("Select at least two feature and/or signal columns to build a combination plot.")

    combo_frame = pd.DataFrame(index=frame.index)
    normalized_series: dict[str, pd.Series] = {}
    for column in selected:
        series = _coerce_numeric_series(frame, column)
        normalized = _zscore_series(series) if normalize else series.fillna(0.0)
        normalized_series[column] = normalized
        combo_frame[column] = series
        combo_frame[f"{column}__scaled"] = normalized

    if feature_cols:
        feature_map = {column: normalized_series[column] for column in feature_cols}
        combo_frame["feature_combo"] = _weighted_combo(feature_map, feature_weights, name="feature_combo")
    if signal_cols:
        signal_map = {column: normalized_series[column] for column in signal_cols}
        combo_frame["signal_combo"] = _weighted_combo(signal_map, signal_weights, name="signal_combo")

    combo_inputs = {}
    if "feature_combo" in combo_frame:
        combo_inputs["feature_combo"] = combo_frame["feature_combo"]
    if "signal_combo" in combo_frame:
        combo_inputs["signal_combo"] = combo_frame["signal_combo"]
    if combo_inputs:
        combo_frame["joint_combo"] = _weighted_combo(combo_inputs, None, name="joint_combo")

    return combo_frame


def build_feature_combo_frame(
    frame: pd.DataFrame,
    *,
    feature_cols: list[str],
    feature_weights: Mapping[str, float] | None = None,
    normalize: bool = True,
) -> pd.DataFrame:
    combo_frame = build_feature_signal_combo_frame(
        frame,
        feature_cols=feature_cols,
        signal_cols=[],
        feature_weights=feature_weights,
        signal_weights=None,
        normalize=normalize,
    )
    if "joint_combo" in combo_frame.columns and "feature_combo" in combo_frame.columns:
        combo_frame = combo_frame.drop(columns=["joint_combo"])
    return combo_frame


def get_experiment_spec(experiment_key: str) -> dict[str, Any]:
    if experiment_key not in TOP_EXPERIMENTS:
        raise KeyError(f"Unknown experiment key: {experiment_key}")
    return dict(TOP_EXPERIMENTS[experiment_key])


def load_logged_artifact_bundle(experiment_key: str) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    spec = get_experiment_spec(experiment_key)
    run_dir = resolve_repo_path(spec["logged_run_dir"])
    summary_payload = load_json(run_dir / "summary.json")
    config_used = load_yaml(run_dir / "config_used.yaml")
    summary = _extract_primary_summary(summary_payload)

    frame = _load_price_frame_from_config(config_used)
    if frame.empty:
        frame = pd.DataFrame(index=_read_numeric_series(run_dir / "equity_curve.csv", default_name="strategy_equity").index)

    series_files = {
        "strategy_equity": "equity_curve.csv",
        "strategy_net_returns": "returns.csv",
        "strategy_gross_returns": "gross_returns.csv",
        "strategy_costs": "costs.csv",
        "strategy_positions": "positions.csv",
        "strategy_turnover": "turnover.csv",
    }
    for column, filename in series_files.items():
        series = _read_numeric_series(run_dir / filename, default_name=column)
        frame[column] = series.reindex(frame.index)

    if "strategy_equity" in frame:
        running_max = frame["strategy_equity"].cummax()
        frame["strategy_drawdown"] = frame["strategy_equity"] / running_max - 1.0
    else:
        frame["strategy_drawdown"] = pd.Series(dtype=float)

    frame["oos_mask"] = frame["strategy_equity"].notna()
    non_null_strategy = frame[[col for col in series_files if col in frame.columns]].notna().any(axis=1)
    if bool(non_null_strategy.any()):
        first = non_null_strategy[non_null_strategy].index.min()
        last = non_null_strategy[non_null_strategy].index.max()
        frame = frame.loc[first:last].copy()

    return frame, summary, config_used


def _single_asset_frame(result: ExperimentResult) -> pd.DataFrame:
    if isinstance(result.data, dict):
        if len(result.data) != 1:
            raise ValueError("The experiment explorer only supports single-asset results.")
        return next(iter(result.data.values())).copy()
    return result.data.copy()


def build_analysis_frame_from_result(result: ExperimentResult) -> pd.DataFrame:
    frame = _single_asset_frame(result)
    backtest = result.backtest
    frame["strategy_net_returns"] = backtest.returns.reindex(frame.index)
    frame["strategy_gross_returns"] = backtest.gross_returns.reindex(frame.index)
    frame["strategy_costs"] = backtest.costs.reindex(frame.index)
    frame["strategy_positions"] = backtest.positions.reindex(frame.index)
    frame["strategy_turnover"] = backtest.turnover.reindex(frame.index)
    frame["strategy_equity"] = backtest.equity_curve.reindex(frame.index)
    running_max = frame["strategy_equity"].cummax()
    frame["strategy_drawdown"] = frame["strategy_equity"] / running_max - 1.0

    if "pred_is_oos" in frame.columns:
        frame["oos_mask"] = frame["pred_is_oos"].fillna(False).astype(bool)
    else:
        frame["oos_mask"] = True
    return frame


def _write_temp_config_file(cfg: Mapping[str, Any], *, config_path: str | Path) -> Path:
    tmp_dir = resolve_repo_path("tmp/notebook_experiments")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    config_stem = resolve_repo_path(config_path).stem
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".yaml",
        prefix=f"{config_stem}_",
        dir=tmp_dir,
        delete=False,
        encoding="utf-8",
    ) as handle:
        yaml.safe_dump(dict(cfg), handle, sort_keys=False)
        return Path(handle.name)


def resolve_config_from_mapping(
    cfg: Mapping[str, Any],
    *,
    config_path: str | Path = "notebooks_dynamic_config.yaml",
) -> dict[str, Any]:
    temp_config_path = _write_temp_config_file(cfg, config_path=config_path)
    try:
        return load_experiment_config(temp_config_path)
    finally:
        temp_config_path.unlink(missing_ok=True)


def build_feature_frame_from_config(
    config_path: str | Path,
    *,
    overrides: Mapping[str, Any] | None = None,
    selected_feature_steps: list[str] | None = None,
    feature_step_updates: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    cfg = build_mutated_config(
        config_path,
        overrides=overrides,
        selected_feature_steps=selected_feature_steps,
        feature_step_updates=feature_step_updates,
    )
    resolved_cfg = resolve_config_from_mapping(cfg, config_path=config_path)
    raw_asset_frames, storage_meta = _load_asset_frames(dict(resolved_cfg.get("data", {}) or {}))
    if len(raw_asset_frames) != 1:
        raise ValueError("The feature visualization notebook only supports single-asset experiment configs.")

    asset = next(iter(sorted(raw_asset_frames)))
    raw_frame = raw_asset_frames[asset].copy()
    feature_steps = list(resolved_cfg.get("features", []) or [])
    feature_frame = apply_feature_steps(raw_frame.copy(), feature_steps)
    step_inventory = build_feature_step_inventory(raw_frame, feature_steps)
    feature_catalog = build_feature_column_catalog(feature_frame, step_inventory=step_inventory)

    meta = {
        "asset": asset,
        "storage_meta": storage_meta,
        "configured_steps": build_configured_feature_steps_frame(resolved_cfg),
        "step_inventory": step_inventory,
        "feature_catalog": feature_catalog,
    }
    return raw_frame, feature_frame, resolved_cfg, meta


def run_experiment_with_overrides(
    config_path: str | Path,
    overrides: Mapping[str, Any] | None = None,
    *,
    logging_enabled: bool = False,
) -> ExperimentResult:
    merged_cfg = build_mutated_config(config_path, overrides=overrides)
    return run_experiment_from_config(merged_cfg, config_path=config_path, logging_enabled=logging_enabled)


def run_experiment_from_config(
    cfg: Mapping[str, Any],
    *,
    config_path: str | Path = "notebooks_dynamic_config.yaml",
    logging_enabled: bool = False,
) -> ExperimentResult:
    merged_cfg = deepcopy(dict(cfg))
    logging_cfg = dict(merged_cfg.get("logging", {}) or {})
    stage_tails = dict(logging_cfg.get("stage_tails", {}) or {})
    stage_tails["enabled"] = False
    stage_tails["stdout"] = False
    stage_tails["report"] = False
    logging_cfg["enabled"] = bool(logging_enabled)
    logging_cfg["stage_tails"] = stage_tails
    merged_cfg["logging"] = logging_cfg

    temp_config_path = _write_temp_config_file(merged_cfg, config_path=config_path)
    try:
        return run_experiment(temp_config_path)
    finally:
        temp_config_path.unlink(missing_ok=True)


def build_feature_signal_combo_frames(
    frame: pd.DataFrame,
    combo_specs: list[Mapping[str, Any]],
    *,
    normalize: bool = True,
) -> dict[str, pd.DataFrame]:
    combo_frames: dict[str, pd.DataFrame] = {}
    for index, spec in enumerate(combo_specs, start=1):
        name = str(spec.get("name") or spec.get("title") or f"combo_{index}")
        combo_frames[name] = build_feature_signal_combo_frame(
            frame,
            feature_cols=list(spec.get("feature_cols", []) or []),
            signal_cols=list(spec.get("signal_cols", []) or []),
            feature_weights=spec.get("feature_weights"),
            signal_weights=spec.get("signal_weights"),
            normalize=bool(spec.get("normalize", normalize)),
        )
    return combo_frames


def build_feature_combo_frames(
    frame: pd.DataFrame,
    combo_specs: list[Mapping[str, Any]],
    *,
    normalize: bool = True,
) -> dict[str, pd.DataFrame]:
    combo_frames: dict[str, pd.DataFrame] = {}
    for index, spec in enumerate(combo_specs, start=1):
        name = str(spec.get("name") or spec.get("title") or f"combo_{index}")
        combo_frames[name] = build_feature_combo_frame(
            frame,
            feature_cols=list(spec.get("feature_cols", []) or []),
            feature_weights=spec.get("feature_weights"),
            normalize=bool(spec.get("normalize", normalize)),
        )
    return combo_frames


def plot_price_signal_probability(
    frame: pd.DataFrame,
    *,
    title: str,
    signal_col: str = "signal_prob_threshold",
    prob_col: str = "pred_prob",
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.65, 0.35],
    )

    if "close" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["close"],
                name="close",
                mode="lines",
                line={"color": "#1f77b4", "width": 1.8},
            ),
            row=1,
            col=1,
        )

    if "strategy_positions" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_positions"],
                name="position",
                mode="lines",
                line={"color": "#d62728", "width": 1.4},
            ),
            row=2,
            col=1,
        )

    if signal_col in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[signal_col],
                name=signal_col,
                mode="lines",
                line={"color": "#2ca02c", "width": 1.2},
            ),
            row=2,
            col=1,
        )

    if prob_col in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[prob_col],
                name=prob_col,
                mode="lines",
                line={"color": "#9467bd", "width": 1.1},
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, rangeslider={"visible": True})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Signal / Position")
    return fig


def plot_equity_drawdown(frame: pd.DataFrame, *, title: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.65, 0.35],
    )

    if "strategy_equity" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_equity"],
                name="equity",
                mode="lines",
                line={"color": "#111827", "width": 2.0},
            ),
            row=1,
            col=1,
        )

    if "strategy_drawdown" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_drawdown"],
                name="drawdown",
                mode="lines",
                fill="tozeroy",
                line={"color": "#ef4444", "width": 1.2},
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, rangeslider={"visible": True})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Equity")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Drawdown")
    return fig


def plot_positions_turnover(frame: pd.DataFrame, *, title: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.55, 0.45],
    )

    if "strategy_positions" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_positions"],
                name="position",
                mode="lines",
                line={"color": "#2563eb", "width": 1.5},
            ),
            row=1,
            col=1,
        )

    if "strategy_turnover" in frame.columns:
        fig.add_trace(
            go.Bar(
                x=frame.index,
                y=frame["strategy_turnover"],
                name="turnover",
                marker_color="#f59e0b",
                opacity=0.75,
            ),
            row=2,
            col=1,
        )

    if "strategy_costs" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_costs"],
                name="costs",
                mode="lines",
                line={"color": "#b91c1c", "width": 1.2},
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, rangeslider={"visible": True})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Position")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Turnover / Costs")
    return fig


def plot_price_with_features(
    frame: pd.DataFrame,
    *,
    title: str,
    feature_cols: list[str],
    normalize: bool = True,
    price_col: str = "close",
) -> go.Figure:
    if not feature_cols:
        raise ValueError("Select at least one feature column to plot against price.")

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.55, 0.45],
    )

    if price_col in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[price_col],
                name=price_col,
                mode="lines",
                line={"color": "#111827", "width": 1.8},
            ),
            row=1,
            col=1,
        )

    palette = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#be123c", "#4f46e5"]
    for idx, feature_column in enumerate(feature_cols):
        series = _coerce_numeric_series(frame, feature_column)
        y = _zscore_series(series) if normalize else series
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=y,
                name=feature_column,
                mode="lines",
                line={"color": palette[idx % len(palette)], "width": 1.2},
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        dragmode="zoom",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, row=1, col=1, rangeslider={"visible": False})
    fig.update_xaxes(showgrid=True, row=2, col=1, rangeslider={"visible": False})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Features (scaled)" if normalize else "Features")
    return fig


def plot_price_with_feature_combo(
    frame: pd.DataFrame,
    *,
    title: str,
    feature_cols: list[str],
    feature_weights: Mapping[str, float] | None = None,
    normalize: bool = True,
    price_col: str = "close",
) -> go.Figure:
    combo_frame = build_feature_combo_frame(
        frame,
        feature_cols=feature_cols,
        feature_weights=feature_weights,
        normalize=normalize,
    )
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        row_heights=[0.45, 0.30, 0.25],
    )

    if price_col in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[price_col],
                name=price_col,
                mode="lines",
                line={"color": "#111827", "width": 1.8},
            ),
            row=1,
            col=1,
        )

    palette = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#be123c", "#4f46e5"]
    for idx, feature_column in enumerate(feature_cols):
        fig.add_trace(
            go.Scatter(
                x=combo_frame.index,
                y=combo_frame[f"{feature_column}__scaled"],
                name=feature_column,
                mode="lines",
                line={"color": palette[idx % len(palette)], "width": 1.2},
            ),
            row=2,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=combo_frame.index,
            y=combo_frame["feature_combo"],
            name="feature_combo",
            mode="lines",
            line={"color": "#0f766e", "width": 1.8},
        ),
        row=3,
        col=1,
    )

    fig.update_layout(
        title=title,
        template="plotly_white",
        dragmode="zoom",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, row=1, col=1, rangeslider={"visible": False})
    fig.update_xaxes(showgrid=True, row=2, col=1, rangeslider={"visible": False})
    fig.update_xaxes(showgrid=True, row=3, col=1, rangeslider={"visible": False})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Features (scaled)")
    fig.update_yaxes(showgrid=True, row=3, col=1, title_text="Feature Combo")
    return fig


def plot_feature_signal_combo(
    frame: pd.DataFrame,
    *,
    title: str,
    feature_cols: list[str],
    signal_cols: list[str],
    feature_weights: Mapping[str, float] | None = None,
    signal_weights: Mapping[str, float] | None = None,
    normalize: bool = True,
    price_col: str = "close",
) -> go.Figure:
    combo_frame = build_feature_signal_combo_frame(
        frame,
        feature_cols=feature_cols,
        signal_cols=signal_cols,
        feature_weights=feature_weights,
        signal_weights=signal_weights,
        normalize=normalize,
    )

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        row_heights=[0.45, 0.30, 0.25],
    )

    if price_col in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[price_col],
                name=price_col,
                mode="lines",
                line={"color": "#111827", "width": 1.8},
            ),
            row=1,
            col=1,
        )

    palette = [
        "#2563eb",
        "#dc2626",
        "#059669",
        "#7c3aed",
        "#ea580c",
        "#0891b2",
        "#be123c",
        "#4f46e5",
    ]
    scaled_columns = [f"{column}__scaled" for column in [*feature_cols, *signal_cols]]
    for idx, scaled_column in enumerate(scaled_columns):
        fig.add_trace(
            go.Scatter(
                x=combo_frame.index,
                y=combo_frame[scaled_column],
                name=scaled_column.replace("__scaled", ""),
                mode="lines",
                line={"color": palette[idx % len(palette)], "width": 1.2},
            ),
            row=2,
            col=1,
        )

    for name, color in [
        ("feature_combo", "#0f766e"),
        ("signal_combo", "#b45309"),
        ("joint_combo", "#7c2d12"),
    ]:
        if name not in combo_frame.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=combo_frame.index,
                y=combo_frame[name],
                name=name,
                mode="lines",
                line={"color": color, "width": 1.8},
            ),
            row=3,
            col=1,
        )

    if "strategy_positions" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame["strategy_positions"],
                name="strategy_positions",
                mode="lines",
                line={"color": "#1d4ed8", "width": 1.0, "dash": "dot"},
            ),
            row=3,
            col=1,
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.0},
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, rangeslider={"visible": True})
    fig.update_yaxes(showgrid=True, row=1, col=1, title_text="Price")
    fig.update_yaxes(showgrid=True, row=2, col=1, title_text="Scaled Inputs")
    fig.update_yaxes(showgrid=True, row=3, col=1, title_text="Composites")
    return fig


def plot_feature_signal_combo_suite(
    frame: pd.DataFrame,
    combo_specs: list[Mapping[str, Any]],
    *,
    normalize: bool = True,
    price_col: str = "close",
) -> dict[str, go.Figure]:
    figures: dict[str, go.Figure] = {}
    for index, spec in enumerate(combo_specs, start=1):
        name = str(spec.get("name") or spec.get("title") or f"combo_{index}")
        title = str(spec.get("title") or name.replace("_", " ").title())
        figures[name] = plot_feature_signal_combo(
            frame,
            title=title,
            feature_cols=list(spec.get("feature_cols", []) or []),
            signal_cols=list(spec.get("signal_cols", []) or []),
            feature_weights=spec.get("feature_weights"),
            signal_weights=spec.get("signal_weights"),
            normalize=bool(spec.get("normalize", normalize)),
            price_col=str(spec.get("price_col") or price_col),
        )
    return figures


def plot_feature_combo_suite(
    frame: pd.DataFrame,
    combo_specs: list[Mapping[str, Any]],
    *,
    normalize: bool = True,
    price_col: str = "close",
) -> dict[str, go.Figure]:
    figures: dict[str, go.Figure] = {}
    for index, spec in enumerate(combo_specs, start=1):
        name = str(spec.get("name") or spec.get("title") or f"combo_{index}")
        title = str(spec.get("title") or name.replace("_", " ").title())
        figures[name] = plot_price_with_feature_combo(
            frame,
            title=title,
            feature_cols=list(spec.get("feature_cols", []) or []),
            feature_weights=spec.get("feature_weights"),
            normalize=bool(spec.get("normalize", normalize)),
            price_col=str(spec.get("price_col") or price_col),
        )
    return figures


def plot_returns_distribution(frame: pd.DataFrame, *, title: str) -> go.Figure:
    returns = frame.get("strategy_net_returns", pd.Series(dtype=float)).dropna()
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=returns,
            nbinsx=80,
            name="net returns",
            marker_color="#0f766e",
            opacity=0.8,
        )
    )
    fig.update_layout(
        title=title,
        template="plotly_white",
        hovermode="x unified",
        bargap=0.05,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.update_xaxes(showgrid=True, title_text="Strategy Net Return")
    fig.update_yaxes(showgrid=True, title_text="Count")
    return fig


def plotly_chart_config() -> dict[str, Any]:
    return {
        "displaylogo": False,
        "displayModeBar": True,
        "scrollZoom": True,
        "responsive": True,
        "doubleClick": "reset",
    }


__all__ = [
    "REPO_ROOT",
    "SUMMARY_ORDER",
    "TOP_EXPERIMENTS",
    "build_configured_feature_steps_frame",
    "build_feature_column_catalog",
    "build_feature_combo_frame",
    "build_feature_combo_frames",
    "build_feature_frame_from_config",
    "build_feature_step_inventory",
    "build_feature_signal_combo_frames",
    "build_feature_signal_catalog",
    "build_feature_signal_combo_frame",
    "build_mutated_config",
    "build_analysis_frame_from_result",
    "build_summary_frame",
    "find_repo_root",
    "get_experiment_spec",
    "list_available_feature_steps",
    "load_logged_artifact_bundle",
    "merge_nested_overrides",
    "parse_override_text",
    "plot_equity_drawdown",
    "plot_feature_combo_suite",
    "plot_feature_signal_combo",
    "plot_feature_signal_combo_suite",
    "plot_positions_turnover",
    "plot_price_with_feature_combo",
    "plot_price_with_features",
    "plot_price_signal_probability",
    "plot_returns_distribution",
    "plotly_chart_config",
    "resolve_config_from_mapping",
    "resolve_repo_path",
    "run_experiment_from_config",
    "run_experiment_with_overrides",
]
