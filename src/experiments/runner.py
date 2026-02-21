from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import json
import yaml
import pandas as pd

from src.backtesting.engine import BacktestResult, run_backtest
from src.experiments.contracts import validate_data_contract
from src.src_data.loaders import load_ohlcv
from src.src_data.pit import apply_pit_hardening
from src.src_data.validation import validate_ohlcv
from src.experiments.registry import get_feature_fn, get_model_fn, get_signal_fn
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
    config: dict[str, Any]
    data: pd.DataFrame
    backtest: BacktestResult
    model: object | None
    model_meta: dict[str, Any]
    artifacts: dict[str, str]


def _apply_feature_steps(df: pd.DataFrame, steps: list[dict[str, Any]]) -> pd.DataFrame:
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
    kind = model_cfg.get("kind", "none")
    if kind == "none":
        return df, None, {}
    fn = get_model_fn(kind)
    return fn(df, model_cfg, returns_col)


def _apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame:
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


def _resolve_vol_col(df: pd.DataFrame, backtest_cfg: dict[str, Any], risk_cfg: dict[str, Any]) -> str | None:
    vol_col = backtest_cfg.get("vol_col") or risk_cfg.get("vol_col")
    if vol_col:
        return vol_col
    for cand in ("vol_rolling_20", "vol_ewma_20", "vol_rolling_60", "vol_ewma_60"):
        if cand in df.columns:
            return cand
    return None

def _validate_returns_series(returns: pd.Series, returns_type: str) -> None:
    if returns_type == "simple":
        if (returns < -1.0).any():
            raise ValueError("Simple returns contain values < -1.0; check returns_type or data.")

def _save_artifacts(
    run_dir: Path,
    cfg: dict[str, Any],
    data: pd.DataFrame,
    bt: BacktestResult,
    model_meta: dict[str, Any],
    run_metadata: dict[str, Any],
    config_hash_sha256: str,
    data_fingerprint: dict[str, Any],
) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = run_dir / "config_used.yaml"
    with cfg_path.open("w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    summary_path = run_dir / "summary.json"
    payload = {
        "summary": bt.summary,
        "model_meta": model_meta,
        "config_features": cfg.get("features", []),
        "signals": cfg.get("signals", {}),
        "resolved_feature_columns": model_meta.get("feature_cols"),
        "data_stats": {
            "rows": int(len(data)),
            "columns": int(len(data.columns)),
            "start": str(data.index.min()) if not data.empty else None,
            "end": str(data.index.max()) if not data.empty else None,
        },
        "reproducibility": {
            "config_hash_sha256": config_hash_sha256,
            "data_hash_sha256": data_fingerprint.get("sha256"),
            "runtime": run_metadata.get("runtime", {}),
        },
    }
    with summary_path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)

    metadata_path = run_dir / "run_metadata.json"
    with metadata_path.open("w") as f:
        json.dump(run_metadata, f, indent=2, default=str)

    equity_path = run_dir / "equity_curve.csv"
    bt.equity_curve.to_csv(equity_path, header=True)

    returns_path = run_dir / "returns.csv"
    bt.returns.to_csv(returns_path, header=True)

    gross_returns_path = run_dir / "gross_returns.csv"
    bt.gross_returns.to_csv(gross_returns_path, header=True)

    costs_path = run_dir / "costs.csv"
    bt.costs.to_csv(costs_path, header=True)

    positions_path = run_dir / "positions.csv"
    bt.positions.to_csv(positions_path, header=True)

    turnover_path = run_dir / "turnover.csv"
    bt.turnover.to_csv(turnover_path, header=True)

    artifacts = {
        "run_dir": str(run_dir),
        "config": str(cfg_path),
        "summary": str(summary_path),
        "run_metadata": str(metadata_path),
        "equity_curve": str(equity_path),
        "returns": str(returns_path),
        "gross_returns": str(gross_returns_path),
        "costs": str(costs_path),
        "positions": str(positions_path),
        "turnover": str(turnover_path),
    }

    manifest = build_artifact_manifest(artifacts)
    manifest_path = run_dir / "artifact_manifest.json"
    with manifest_path.open("w") as f:
        json.dump(manifest, f, indent=2, default=str)
    artifacts["manifest"] = str(manifest_path)

    return artifacts


def run_experiment(config_path: str | Path) -> ExperimentResult:
    cfg = load_experiment_config(config_path)
    runtime_applied = apply_runtime_reproducibility(cfg.get("runtime", {}))
    config_hash_sha256, config_hash_input = compute_config_hash(cfg)

    data_cfg = cfg["data"]
    data_kwargs = {
        k: v
        for k, v in data_cfg.items()
        if k in {"symbol", "start", "end", "interval", "source", "api_key"}
    }
    df = load_ohlcv(**data_kwargs)
    pit_cfg = data_cfg.get("pit", {}) or {}
    pit_meta: dict[str, Any] = {}
    if pit_cfg:
        df, pit_meta = apply_pit_hardening(
            df,
            pit_cfg=pit_cfg,
            symbol=data_cfg.get("symbol"),
        )
    validate_ohlcv(df)
    validate_data_contract(df)
    data_fingerprint = compute_dataframe_fingerprint(df)

    df = _apply_feature_steps(df, cfg.get("features", []))

    model_cfg = dict(cfg.get("model", {"kind": "none"}) or {})
    model_cfg.setdefault("runtime", cfg.get("runtime", {}))
    returns_col = cfg.get("backtest", {}).get("returns_col")
    df, model, model_meta = _apply_model_step(df, model_cfg, returns_col)

    df = _apply_signal_step(df, cfg.get("signals", {}))

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
    if model is not None and model_meta.get("split_index") is not None:
        bt_subset = backtest_cfg.get("subset", "test")
        if bt_subset == "test":
            bt_df = df.iloc[int(model_meta["split_index"]) :]

    bt = run_backtest(
        bt_df,
        signal_col=signal_col,
        returns_col=returns_col,
        returns_type=returns_type,
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
                {
                    k: data_cfg.get(k)
                    for k in ("symbol", "source", "interval", "start", "end")
                }
                | {
                    "pit_config": pit_cfg,
                    "pit_meta": pit_meta,
                }
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
            data=df,
            bt=bt,
            model_meta=model_meta,
            run_metadata=run_metadata,
            config_hash_sha256=config_hash_sha256,
            data_fingerprint=data_fingerprint,
        )

    return ExperimentResult(
        config=cfg,
        data=df,
        backtest=bt,
        model=model,
        model_meta=model_meta,
        artifacts=artifacts,
    )

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a config-based trading experiment.")
    parser.add_argument("config", help="Path to experiment YAML (relative to config/ or absolute).")
    args = parser.parse_args()

    result = run_experiment(args.config)

    print("Experiment completed")
    print("Summary:")
    for k, v in result.backtest.summary.items():
        print(f"  {k}: {v}")
    if result.artifacts:
        print("")
        print("Artifacts:")
        for k, v in result.artifacts.items():
            print(f"  {k}: {v}")
    print("Run summary:", result.backtest.summary)
    if result.artifacts:
        print("Artifacts saved to:", result.artifacts.get("run_dir"))
