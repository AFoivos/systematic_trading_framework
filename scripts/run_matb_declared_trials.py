from __future__ import annotations

"""Run exactly the 27 predeclared MATB parameter-neighborhood trials."""

import argparse
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, rankdata, skew

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.experiments.orchestration.backtest_stage import run_portfolio_backtest
from src.experiments.orchestration.feature_stage import apply_signals_to_assets, apply_steps_to_assets
from src.experiments.runner import _load_asset_frames
from src.utils.config import load_experiment_config


def _latest_run() -> Path:
    runs = sorted(
        (REPOSITORY_ROOT / "logs/experiments/matb").glob("00_matb_deterministic_*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not runs:
        raise FileNotFoundError("Run the deterministic MATB config before declared trials.")
    return runs[0]


def _daily_return_matrix(returns_by_trial: dict[str, pd.Series]) -> pd.DataFrame:
    daily: dict[str, pd.Series] = {}
    for trial, values in returns_by_trial.items():
        resolved = values.copy()
        resolved.index = pd.to_datetime(resolved.index, utc=True)
        daily[trial] = resolved.groupby(resolved.index.normalize()).apply(
            lambda returns: float((1.0 + returns.astype(float)).prod() - 1.0)
        )
    return pd.concat(daily, axis=1).fillna(0.0).sort_index()


def _sharpe(values: np.ndarray) -> float:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if len(finite) < 2 or float(np.std(finite, ddof=1)) <= 0.0:
        return 0.0
    return float(np.mean(finite) / np.std(finite, ddof=1))


def _deflated_sharpe(daily: pd.DataFrame) -> dict[str, Any]:
    daily_sharpes = daily.apply(lambda series: _sharpe(series.to_numpy()), axis=0)
    best_trial = str(daily_sharpes.idxmax())
    best_sr = float(daily_sharpes.loc[best_trial])
    trials = int(len(daily_sharpes))
    sr_std = float(daily_sharpes.std(ddof=1)) if trials > 1 else 0.0
    euler_gamma = 0.5772156649015329
    expected_max = 0.0
    if trials > 1 and sr_std > 0.0:
        expected_max = sr_std * (
            (1.0 - euler_gamma) * norm.ppf(1.0 - 1.0 / trials)
            + euler_gamma * norm.ppf(1.0 - 1.0 / (trials * np.e))
        )
    best_returns = daily[best_trial].to_numpy(dtype=float)
    denominator = np.sqrt(
        max(
            1.0
            - float(skew(best_returns, bias=False)) * best_sr
            + ((float(kurtosis(best_returns, fisher=False, bias=False)) - 1.0) / 4.0)
            * best_sr**2,
            1e-12,
        )
    )
    z_score = (best_sr - expected_max) * np.sqrt(max(len(best_returns) - 1, 1)) / denominator
    return {
        "best_trial_diagnostic_only": best_trial,
        "best_annualized_sharpe": float(best_sr * np.sqrt(365.0)),
        "expected_max_daily_sharpe_under_multiple_trials": float(expected_max),
        "deflated_sharpe_probability": float(norm.cdf(z_score)),
        "trial_count": trials,
        "daily_observations": int(len(best_returns)),
        "selection_policy": "diagnostic_only_no_parameter_adoption",
    }


def _probability_of_backtest_overfitting(daily: pd.DataFrame, *, blocks: int = 8) -> dict[str, Any]:
    if blocks % 2 != 0 or blocks < 4:
        raise ValueError("PBO requires an even block count >= 4.")
    block_positions = [np.asarray(chunk, dtype=int) for chunk in np.array_split(np.arange(len(daily)), blocks)]
    logits: list[float] = []
    trial_count = daily.shape[1]
    values = daily.to_numpy(dtype=float)
    for chosen_blocks in combinations(range(blocks), blocks // 2):
        in_blocks = set(chosen_blocks)
        train_positions = np.concatenate([block_positions[idx] for idx in range(blocks) if idx in in_blocks])
        test_positions = np.concatenate([block_positions[idx] for idx in range(blocks) if idx not in in_blocks])
        train_sharpes = np.array([_sharpe(values[train_positions, col]) for col in range(trial_count)])
        test_sharpes = np.array([_sharpe(values[test_positions, col]) for col in range(trial_count)])
        selected = int(np.argmax(train_sharpes))
        ranks = rankdata(test_sharpes, method="average")
        omega = float(ranks[selected] / (trial_count + 1.0))
        omega = min(max(omega, 1e-12), 1.0 - 1e-12)
        logits.append(float(np.log(omega / (1.0 - omega))))
    return {
        "probability_of_backtest_overfitting": float(np.mean(np.asarray(logits) <= 0.0)),
        "cscv_block_count": int(blocks),
        "cscv_combinations": int(len(logits)),
        "median_oos_rank_logit": float(np.median(logits)),
    }


def run_declared_trials(*, config_path: Path, run_dir: Path) -> dict[str, Any]:
    cfg = load_experiment_config(config_path)
    declared = json.loads(
        (REPOSITORY_ROOT / "config/experiments/matb/declared_trials.json").read_text(
            encoding="utf-8"
        )
    )
    if int(declared.get("trial_count", 0)) != 27 or len(declared.get("trials", [])) != 27:
        raise ValueError("MATB declared-trial manifest must contain exactly 27 trials.")
    raw_frames, _ = _load_asset_frames(cfg["data"])
    base_feature_params = dict(cfg["features"][1]["params"])
    feature_cache: dict[tuple[float, int], dict[str, pd.DataFrame]] = {}
    rows: list[dict[str, Any]] = []
    returns_by_trial: dict[str, pd.Series] = {}

    for trial in declared["trials"]:
        trend = float(trial["trend_threshold"])
        lookback = int(trial["donchian_lookback_days"])
        stop = float(trial["stop_multiplier_atr"])
        cache_key = (trend, lookback)
        if cache_key not in feature_cache:
            params = dict(base_feature_params)
            params["trend_threshold"] = trend
            params["donchian_days"] = lookback
            feature_cache[cache_key] = apply_steps_to_assets(
                raw_frames,
                feature_steps=[
                    {"step": "returns", "params": {"log": False, "col_name": "close_ret"}},
                    {"step": "multi_asset_trend_breakout", "params": params},
                ],
            )
        frames = apply_signals_to_assets(
            feature_cache[cache_key],
            signals_cfg=dict(cfg["signals"]),
        )
        variant = deepcopy(cfg)
        variant["diagnostics"] = {"enabled": False}
        variant["backtest"] = dict(variant["backtest"])
        variant["backtest"]["stop_barrier_r"] = stop
        variant["backtest"]["strategy_path"] = dict(variant["backtest"]["strategy_path"])
        variant["backtest"]["strategy_path"]["stop_loss_atr"] = stop
        performance, _, _, _ = run_portfolio_backtest(frames, cfg=variant)
        trial_id = str(trial["trial_id"])
        returns_by_trial[trial_id] = performance.net_returns.copy()
        trades = performance.trades
        net_by_asset = trades.groupby("asset", observed=True)["net_return"].sum() if not trades.empty else pd.Series(dtype=float)
        net_by_group = trades.groupby("asset_group", observed=True)["net_return"].sum() if not trades.empty else pd.Series(dtype=float)
        rows.append(
            {
                **trial,
                "candidate_count": int(
                    sum(int(frame["matb_candidate"].sum()) for frame in frames.values())
                ),
                "trade_count": int(len(trades)),
                "cumulative_return": performance.summary.get("cumulative_return"),
                "annualized_return": performance.summary.get("annualized_return"),
                "annualized_vol": performance.summary.get("annualized_vol"),
                "sharpe": performance.summary.get("sharpe"),
                "sortino": performance.summary.get("sortino"),
                "calmar": performance.summary.get("calmar"),
                "max_drawdown": performance.summary.get("max_drawdown"),
                "profit_factor": performance.summary.get("profit_factor"),
                "hit_rate": performance.summary.get("hit_rate"),
                "average_r": performance.summary.get("average_r"),
                "median_r": performance.summary.get("median_r"),
                "maximum_asset_absolute_pnl_share": (
                    float(net_by_asset.abs().max() / net_by_asset.abs().sum())
                    if not net_by_asset.empty and float(net_by_asset.abs().sum()) > 0.0
                    else None
                ),
                "maximum_group_absolute_pnl_share": (
                    float(net_by_group.abs().max() / net_by_group.abs().sum())
                    if not net_by_group.empty and float(net_by_group.abs().sum()) > 0.0
                    else None
                ),
            }
        )
        print(
            f"completed {trial_id}: trend={trend:.2f} lookback={lookback} stop={stop:.1f}",
            flush=True,
        )

    results = pd.DataFrame(rows)
    results.to_csv(run_dir / "parameter_neighborhood.csv", index=False)
    daily = _daily_return_matrix(returns_by_trial)
    summary = {
        "declared_trial_count": int(len(results)),
        "positive_cumulative_return_ratio": float(results["cumulative_return"].gt(0.0).mean()),
        "positive_sharpe_ratio": float(results["sharpe"].gt(0.0).mean()),
        "median_cumulative_return": float(results["cumulative_return"].median()),
        "median_sharpe": float(results["sharpe"].median()),
        "minimum_cumulative_return": float(results["cumulative_return"].min()),
        "maximum_cumulative_return": float(results["cumulative_return"].max()),
        "parameter_neighborhood_stability": float(results["cumulative_return"].gt(0.0).mean()),
        **_deflated_sharpe(daily),
        **_probability_of_backtest_overfitting(daily),
    }
    (run_dir / "parameter_neighborhood_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"run_dir": str(run_dir), **summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/experiments/matb/00_matb_deterministic.yaml"),
    )
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    config_path = (REPOSITORY_ROOT / args.config).resolve() if not args.config.is_absolute() else args.config
    run_dir = args.run_dir.resolve() if args.run_dir else _latest_run()
    result = run_declared_trials(config_path=config_path, run_dir=run_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
