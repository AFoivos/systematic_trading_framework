from __future__ import annotations

"""Build MATB acceptance, concentration, pseudo-holdout, and blocked-ML artifacts."""

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.evaluation.metrics import compute_backtest_metrics, hit_rate, profit_factor
from src.experiments.support.matb_diagnostics import build_target_backtest_parity_diagnostics


def _latest_run() -> Path:
    candidates = sorted(
        (REPOSITORY_ROOT / "logs/experiments/matb").glob("00_matb_deterministic_*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No completed MATB deterministic run directory was found.")
    return candidates[0]


def _series(path: Path, value_col: str) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    index = pd.to_datetime(frame.pop("timestamp"), utc=True)
    return pd.Series(
        pd.to_numeric(frame[value_col], errors="coerce").fillna(0.0).to_numpy(dtype=float),
        index=index,
        name=value_col,
    ).sort_index()


def _calendar_metrics(
    net: pd.Series,
    *,
    gross: pd.Series | None = None,
    costs: pd.Series | None = None,
) -> dict[str, Any]:
    return compute_backtest_metrics(
        net_returns=net,
        gross_returns=gross,
        costs=costs,
        periods_per_year=365,
        annualization_mode="calendar_daily",
    )


def _gate(
    metric: str,
    threshold: str,
    observed: Any,
    passed: bool,
    reason: str,
    *,
    family: str = "deterministic",
) -> dict[str, Any]:
    return {
        "family": family,
        "metric": metric,
        "threshold": threshold,
        "observed_value": observed,
        "passed": bool(passed),
        "reason": reason,
    }


def _write_blocked_csv(path: Path, *, artifact: str, reason: str) -> None:
    pd.DataFrame(
        [{"artifact": artifact, "status": "NOT_RUN", "reason": reason}]
    ).to_csv(path, index=False)


def build_artifacts(*, run_dir: Path, audit_dir: Path) -> dict[str, Any]:
    summary_payload = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    summary = dict(summary_payload["summary"])
    net = _series(run_dir / "returns.csv", "net_returns")
    gross = _series(run_dir / "gross_returns.csv", "gross_returns")
    costs = _series(run_dir / "costs.csv", "costs")
    trades = pd.read_csv(
        run_dir / "trade_events.csv",
        parse_dates=["signal_time", "entry_time", "exit_time"],
    )
    for column in ("net_return", "gross_return", "realized_r", "risk_contribution", "cost"):
        trades[column] = pd.to_numeric(trades.get(column), errors="coerce")

    pseudo_start = pd.Timestamp("2024-01-01", tz="UTC")
    pseudo_net = net.loc[net.index >= pseudo_start]
    pseudo_gross = gross.reindex(pseudo_net.index).fillna(0.0)
    pseudo_costs = costs.reindex(pseudo_net.index).fillna(0.0)
    pseudo = _calendar_metrics(pseudo_net, gross=pseudo_gross, costs=pseudo_costs)
    pseudo_trades = trades.loc[pd.to_datetime(trades["exit_time"], utc=True) >= pseudo_start].copy()
    pseudo_trade_returns = pseudo_trades["net_return"].dropna().astype(float)
    pseudo_trade_r = pseudo_trades["realized_r"].dropna().astype(float)
    pseudo.update(
        {
            "profit_factor": profit_factor(pseudo_trade_returns),
            "hit_rate": hit_rate(pseudo_trade_returns),
            "trade_count": int(len(pseudo_trades)),
            "average_r": float(pseudo_trade_r.mean()) if not pseudo_trade_r.empty else None,
            "median_r": float(pseudo_trade_r.median()) if not pseudo_trade_r.empty else None,
            "scope": "pseudo_holdout_2024_onward",
            "pristine": False,
            "pristine_note": "Prior repository research means this historical pseudo-holdout is not fully pristine.",
        }
    )
    (run_dir / "pseudo_holdout_summary.json").write_text(
        json.dumps(pseudo, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    yearly_rows: list[dict[str, Any]] = []
    for year, year_net in net.groupby(net.index.year):
        metrics = _calendar_metrics(
            year_net,
            gross=gross.reindex(year_net.index).fillna(0.0),
            costs=costs.reindex(year_net.index).fillna(0.0),
        )
        year_trades = trades.loc[pd.to_datetime(trades["exit_time"], utc=True).dt.year.eq(int(year))]
        yearly_rows.append(
            {
                "year": int(year),
                "trade_count": int(len(year_trades)),
                "cumulative_return": metrics.get("cumulative_return"),
                "annualized_return": metrics.get("annualized_return"),
                "annualized_vol": metrics.get("annualized_vol"),
                "sharpe": metrics.get("sharpe"),
                "sortino": metrics.get("sortino"),
                "calmar": metrics.get("calmar"),
                "max_drawdown": metrics.get("max_drawdown"),
                "profit_factor": profit_factor(year_trades["net_return"].dropna().astype(float)),
                "hit_rate": hit_rate(year_trades["net_return"].dropna().astype(float)),
            }
        )
    yearly = pd.DataFrame(yearly_rows)
    yearly.to_csv(run_dir / "yearly_performance.csv", index=False)

    concentration_rows: list[dict[str, Any]] = []
    total_abs_pnl = float(trades.groupby("asset")["net_return"].sum().abs().sum())
    total_abs_group_pnl = float(trades.groupby("asset_group")["net_return"].sum().abs().sum())
    for scope, column, denominator in (
        ("asset", "asset", total_abs_pnl),
        ("asset_group", "asset_group", total_abs_group_pnl),
    ):
        for name, group in trades.groupby(column, observed=True):
            net_pnl = float(group["net_return"].sum())
            concentration_rows.append(
                {
                    "scope": scope,
                    "name": str(name),
                    "trade_count": int(len(group)),
                    "net_pnl": net_pnl,
                    "gross_pnl": float(group["gross_return"].sum()),
                    "cost": float(group["cost"].sum()),
                    "risk_contribution": float(group["risk_contribution"].sum()),
                    "absolute_pnl_share": abs(net_pnl) / max(float(denominator), 1e-12),
                }
            )
    concentration = pd.DataFrame(concentration_rows)
    concentration.to_csv(run_dir / "concentration_by_asset_group.csv", index=False)
    asset_concentration = concentration.loc[concentration["scope"].eq("asset"), "absolute_pnl_share"]
    group_concentration = concentration.loc[
        concentration["scope"].eq("asset_group"), "absolute_pnl_share"
    ]
    maximum_asset_share = float(asset_concentration.max()) if not asset_concentration.empty else 1.0
    maximum_group_share = float(group_concentration.max()) if not group_concentration.empty else 1.0

    cost_delay_rows: list[dict[str, Any]] = []
    for multiplier in (1, 2, 3, 5):
        prefix = f"robustness_cost_x{multiplier}_"
        cost_delay_rows.append(
            {
                "scenario": f"cost_x{multiplier}",
                "cumulative_return": summary.get(prefix + "cumulative_return"),
                "sharpe": summary.get(prefix + "sharpe"),
                "max_drawdown": summary.get(prefix + "max_drawdown"),
                "profit_factor": summary.get(prefix + "profit_factor"),
            }
        )
    for delay in (1, 2):
        prefix = f"robustness_delay_{delay}_bars_"
        cost_delay_rows.append(
            {
                "scenario": f"delay_{delay}_bars",
                "cumulative_return": summary.get(prefix + "cumulative_return"),
                "sharpe": summary.get(prefix + "sharpe"),
                "max_drawdown": summary.get(prefix + "max_drawdown"),
                "profit_factor": summary.get(prefix + "profit_factor"),
            }
        )
    pd.DataFrame(cost_delay_rows).to_csv(run_dir / "cost_delay_stress.csv", index=False)

    parity = build_target_backtest_parity_diagnostics()
    parity.to_csv(run_dir / "target_backtest_parity.csv", index=False)
    if not bool(parity["passed"].all()):
        raise AssertionError("MATB target/backtest parity artifact contains a failure.")

    audit = pd.read_csv(audit_dir / "matb_event_audit.csv")
    portfolio_audit = audit.loc[audit["asset"].eq("__PORTFOLIO__")].iloc[0]
    candidate_count = int(portfolio_audit["total_candidates"])
    sample_gate = json.loads((audit_dir / "matb_ml_sample_gate.json").read_text(encoding="utf-8"))
    complete_years = yearly.loc[yearly["year"].lt(int(net.index.max().year))]
    minimum_trades_per_year = int(complete_years["trade_count"].min())
    median_fold_sharpe = float(complete_years["sharpe"].median())
    positive_fold_ratio = float(complete_years["cumulative_return"].gt(0.0).mean())
    delay_1 = float(summary["robustness_delay_1_bars_cumulative_return"])
    base_return = float(summary["cumulative_return"])
    delay_retention = delay_1 / base_return if base_return > 0.0 else float("-inf")
    base_vol = float(summary["annualized_vol"])
    scaled_metrics = _calendar_metrics(net * (0.08 / base_vol)) if base_vol > 0.0 else {}
    scaled_max_drawdown = abs(float(scaled_metrics.get("max_drawdown", -1.0)))

    gates = [
        _gate("total_candidates", ">= 800", candidate_count, candidate_count >= 800, "immutable event audit"),
        _gate(
            "completed_portfolio_trades_per_year",
            ">= 60",
            minimum_trades_per_year,
            minimum_trades_per_year >= 60,
            "minimum across completed calendar years",
        ),
        _gate("net_oos_sharpe", ">= 0.50", pseudo.get("sharpe"), float(pseudo.get("sharpe", -np.inf)) >= 0.50, "2024 onward pseudo-holdout; not fully pristine"),
        _gate("median_fold_sharpe", "> 0", median_fold_sharpe, median_fold_sharpe > 0.0, "completed calendar-year folds"),
        _gate("positive_fold_ratio", ">= 0.60", positive_fold_ratio, positive_fold_ratio >= 0.60, "completed calendar-year folds"),
        _gate("cost_x2_cumulative_return", "> 0", summary.get("robustness_cost_x2_cumulative_return"), float(summary.get("robustness_cost_x2_cumulative_return", -np.inf)) > 0.0, "explicit costs/slippage doubled; quoted spread remains embedded"),
        _gate("delay_1_retention_ratio", ">= 0.60", delay_retention, delay_retention >= 0.60, "same candidate with one additional entry bar"),
        _gate("maximum_asset_pnl_share", "<= 0.30", maximum_asset_share, maximum_asset_share <= 0.30, "share of absolute net PnL contributions"),
        _gate("maximum_group_pnl_share", "<= 0.50", maximum_group_share, maximum_group_share <= 0.50, "share of absolute net PnL contributions"),
        _gate("max_drawdown_at_8pct_target_vol", "<= 0.10", scaled_max_drawdown, scaled_max_drawdown <= 0.10, "linear ex-post scaling from observed annualized volatility"),
    ]
    gates.extend(
        _gate(
            str(check["metric"]),
            str(check["threshold"]),
            check.get("observed_value"),
            bool(check["passed"]),
            str(check["reason"]),
            family="ml_sample",
        )
        for check in sample_gate["checks"]
    )
    blocked_reason = "ML sample gate failed before target folds; no model fit or placebo is permitted."
    for metric, threshold in (
        ("training_events_per_fold", ">= 300"),
        ("maximum_training_asset_share", "<= 0.45"),
        ("maximum_training_group_share", "<= 0.45"),
        ("both_target_classes_per_fold", "exactly {0,1}"),
        ("brier_improves_base_rate", "true"),
        ("calibration_slope", "[0.70,1.30]"),
        ("calibration_intercept_material_bias", "false"),
        ("accepted_trade_expected_r_improvement", "> 0"),
        ("sharpe_improvement_ratio", ">= 0.15"),
        ("improvement_survives_cost_x2", "true"),
        ("improvement_survives_delay_1", "true"),
        ("accepted_event_concentration_passes", "true"),
    ):
        gates.append(_gate(metric, threshold, None, False, blocked_reason, family="ml"))
    decision = "REJECTED"
    acceptance = {
        "decision": decision,
        "ml_gate": "FAILED",
        "ml_fit_attempted": False,
        "ml_config_run": False,
        "gates": gates,
    }
    (run_dir / "acceptance_gate_report.json").write_text(
        json.dumps(acceptance, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    shutil.copy2(audit_dir / "candidate_counts_by_asset_year.csv", run_dir / "candidate_counts_by_asset_year.csv")
    shutil.copy2(audit_dir / "candidate_counts_by_group_side.csv", run_dir / "candidate_counts_by_group_side.csv")
    shutil.copy2(
        REPOSITORY_ROOT / "config/experiments/matb/declared_trials.json",
        run_dir / "declared_trials.json",
    )
    for filename in (
        "fold_event_counts.csv",
        "fold_time_ranges.csv",
        "purged_overlap_audit.csv",
        "calibration_by_fold.csv",
        "classification_metrics_by_fold.csv",
        "accepted_vs_rejected_event_r.csv",
        "accepted_vs_rejected_by_asset.csv",
        "placebo_tests.csv",
    ):
        _write_blocked_csv(run_dir / filename, artifact=filename, reason=blocked_reason)
    parameter_path = run_dir / "parameter_neighborhood.csv"
    if not parameter_path.exists():
        _write_blocked_csv(
            parameter_path,
            artifact="parameter_neighborhood.csv",
            reason="Declared trial runner has not completed yet.",
        )
    return {
        "run_dir": str(run_dir),
        "decision": decision,
        "candidate_count": candidate_count,
        "pseudo_holdout": pseudo,
        "maximum_asset_pnl_share": maximum_asset_share,
        "maximum_group_pnl_share": maximum_group_share,
        "failed_deterministic_gates": [
            gate["metric"] for gate in gates if gate["family"] == "deterministic" and not gate["passed"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=Path("logs/experiments/matb/audit"),
    )
    args = parser.parse_args()
    run_dir = args.run_dir.resolve() if args.run_dir else _latest_run()
    audit_dir = (REPOSITORY_ROOT / args.audit_dir).resolve() if not args.audit_dir.is_absolute() else args.audit_dir
    result = build_artifacts(run_dir=run_dir, audit_dir=audit_dir)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
