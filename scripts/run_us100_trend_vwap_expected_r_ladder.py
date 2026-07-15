"""Run and report the US100 M30 Trend-VWAP expected-R YAML ladder.

The script reuses successful experiment artifacts by default, runs missing
estimable stages, records zero-candidate stages as non-estimable, and builds
the requested technical comparison report plus audit-ready CSV/JSON inputs.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.generate_us100_trend_vwap_expected_r_ladder import (
    CONFIG_DIR,
    FILENAMES,
    STAGE_LABELS,
)
from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.experiments.orchestration.reporting import compute_subset_metrics
from src.experiments.runner import run_experiment
from src.features.trend_vwap_pullback_candidate import transition_pulse
from src.utils.config import load_experiment_config


LOG_DIR = ROOT / "logs/experiments/trend_vwap_expected_r_us100_m30"
REPORT_PATH = ROOT / "reports/us100_m30_trend_vwap_expected_r_ladder.md"
EVIDENCE_DIR = ROOT / "reports/us100_m30_trend_vwap_expected_r_ladder_data"
RAW_PATH = ROOT / "data/raw/dukascopy_30m_clean/us100_30m.csv"
RUN_INDEX_PATH = EVIDENCE_DIR / "run_index.json"

BLUE = "#2E5B88"
GOLD = "#C58B27"
ORANGE = "#D56A3A"
INK = "#252A31"
GRID = "#D9DEE5"
MUTED = "#8A949E"


def _json_load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return dict(json.load(handle))


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def _latest_run_dir(stage: int) -> Path | None:
    prefix = f"us100_m30_trend_vwap_expected_r_yaml{stage}_"
    candidates = [
        path
        for path in LOG_DIR.glob(f"{prefix}*")
        if path.is_dir() and (path / "summary.json").exists()
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def _snapshot_path(summary: dict[str, Any]) -> Path | None:
    storage = dict(summary.get("storage", {}) or {})
    snapshot = dict(storage.get("saved_processed_snapshot", {}) or {})
    value = snapshot.get("data_path")
    return Path(str(value)) if value else None


def _read_snapshot(summary: dict[str, Any]) -> pd.DataFrame:
    path = _snapshot_path(summary)
    if path is None or not path.exists():
        raise FileNotFoundError("Processed experiment snapshot is unavailable.")
    frame = pd.read_csv(path, parse_dates=["timestamp"], low_memory=False)
    if "asset" in frame.columns:
        frame = frame.loc[frame["asset"].astype(str).eq("US100")].copy()
    frame = frame.set_index("timestamp").sort_index()
    return frame


def _read_trades(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "trade_events.csv"
    if not path.exists():
        return pd.DataFrame()
    trades = pd.read_csv(path)
    for column in ("signal_time", "entry_time", "exit_time", "signal_timestamp", "entry_timestamp", "exit_timestamp"):
        if column in trades.columns:
            trades[column] = pd.to_datetime(trades[column], errors="coerce")
    return trades


def _as_bool(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    normalized = values.astype(str).str.strip().str.lower()
    return normalized.isin({"1", "1.0", "true", "t", "yes"})


def _finite_mean(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(numeric.mean()) if not numeric.empty else math.nan


def _finite_median(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(numeric.median()) if not numeric.empty else math.nan


def _safe_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return math.nan
    return parsed if math.isfinite(parsed) else math.nan


def _run_or_reuse(stage: int, *, rerun: bool) -> dict[str, Any]:
    existing = None if rerun else _latest_run_dir(stage)
    if existing is not None:
        return {"stage": stage, "status": "reused", "run_dir": str(existing)}
    config_path = CONFIG_DIR / FILENAMES[stage]
    print(f"[stage {stage}] running {config_path.name}", flush=True)
    try:
        result = run_experiment(config_path)
    except Exception as exc:  # keep the ladder audit even when one stage is non-estimable
        print(f"[stage {stage}] failed: {type(exc).__name__}: {exc}", flush=True)
        return {
            "stage": stage,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    run_dir = Path(result.artifacts["run_dir"])
    print(
        f"[stage {stage}] complete: trades={result.summary.get('trade_count')} "
        f"sharpe={result.summary.get('sharpe')}",
        flush=True,
    )
    return {"stage": stage, "status": "completed", "run_dir": str(run_dir)}


def _session_and_risk_preflight(stage6: pd.DataFrame) -> dict[str, Any]:
    index = stage6.index
    utc_index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    local = utc_index.tz_convert("America/New_York")
    minutes = local.hour * 60 + local.minute
    session_ok = pd.Series((minutes >= 10 * 60) & (minutes < 12 * 60 + 30), index=index)

    mandatory = stage6["ema_50"].gt(stage6["ema_100"]) & stage6["close"].gt(stage6["ema_50"])
    filters: list[tuple[str, pd.Series]] = [
        ("trend", mandatory & stage6["trend_vwap_trend_score"].ge(4)),
        ("expansion", stage6["trend_vwap_expansion_ok"].astype(bool)),
        ("pullback", stage6["trend_vwap_pullback_ok"].astype(bool)),
        ("momentum", stage6["trend_vwap_momentum_ok"].astype(bool)),
        ("session", session_ok),
    ]

    return_1 = pd.to_numeric(stage6["return_1"], errors="coerce")
    reference_vol = return_1.rolling(96, min_periods=96).std(ddof=1).shift(1)
    range_to_atr = pd.to_numeric(stage6["true_range"], errors="coerce") / pd.to_numeric(
        stage6["atr_20"], errors="coerce"
    ).replace(0.0, np.nan)
    shock_active = return_1.abs().gt(3.0 * reference_vol) | range_to_atr.gt(2.5)
    prior_resistance = pd.to_numeric(stage6["high"], errors="coerce").shift(1).rolling(48, min_periods=48).max()
    resistance_distance = (prior_resistance - pd.to_numeric(stage6["close"], errors="coerce")) / pd.to_numeric(
        stage6["atr_20"], errors="coerce"
    ).replace(0.0, np.nan)
    resistance_ok = ~(resistance_distance.ge(0.0) & resistance_distance.lt(0.50))

    atr_values = pd.to_numeric(stage6["atr_20"], errors="coerce").to_numpy(dtype=float)
    atr_rank = np.full(len(stage6), np.nan, dtype=float)
    window = 252
    if len(stage6) > window:
        windows = np.lib.stride_tricks.sliding_window_view(atr_values, window + 1)
        history = windows[:, :-1]
        current = windows[:, -1]
        valid = np.isfinite(current) & np.isfinite(history).all(axis=1)
        ranks = np.full(len(windows), np.nan, dtype=float)
        ranks[valid] = np.mean(history[valid] <= current[valid, None], axis=1)
        atr_rank[window:] = ranks
    volatility_ok = pd.Series(atr_rank, index=index).le(0.97) & pd.Series(atr_rank, index=index).notna()
    filters.extend(
        [
            ("shock", ~shock_active.fillna(False)),
            ("resistance", resistance_ok.fillna(False)),
            ("volatility", volatility_ok.fillna(False)),
        ]
    )

    universe = stage6["vwap_reclaim_cross"].astype(bool)
    remaining = universe.copy()
    attribution: dict[str, int] = {"reclaim_event_universe": int(universe.sum())}
    for name, rule in filters:
        rejected = remaining & ~rule.fillna(False)
        attribution[f"rejected_{name}"] = int(rejected.sum())
        remaining &= rule.fillna(False)
        attribution[f"remaining_after_{name}"] = int(remaining.sum())

    stage7_state = stage6["trend_vwap_base_state"].astype(bool) & session_ok
    stage7_candidate = transition_pulse(stage7_state)
    stage8_state = remaining
    stage8_candidate = transition_pulse(stage8_state)
    return {
        "stage6_candidates": int(stage6["trend_vwap_base_candidate"].sum()),
        "stage7_candidates": int(stage7_candidate.sum()),
        "stage8_candidates": int(stage8_candidate.sum()),
        "stage7_true_state_rows": int(stage7_state.sum()),
        "stage8_true_state_rows": int(stage8_state.sum()),
        "attribution": attribution,
        "timezone": "America/New_York",
        "entry_window": "10:00 <= local time < 12:30",
    }


def run_ladder(*, rerun: bool, attempt_empty: bool) -> list[dict[str, Any]]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    entries = [_run_or_reuse(stage, rerun=rerun) for stage in range(7)]
    stage6_entry = entries[6]
    if stage6_entry.get("run_dir"):
        summary = _json_load(Path(stage6_entry["run_dir"]) / "summary.json")
        preflight = _session_and_risk_preflight(_read_snapshot(summary))
    else:
        preflight = {
            "stage7_candidates": None,
            "stage8_candidates": None,
            "error": "YAML6 snapshot unavailable; session/risk preflight could not run.",
        }
    _json_dump(EVIDENCE_DIR / "preflight.json", preflight)

    zero_tail = preflight.get("stage7_candidates") == 0
    for stage in range(7, 11):
        feature_stage = min(stage, 8)
        candidate_count = preflight.get(f"stage{feature_stage}_candidates")
        if candidate_count is None and not attempt_empty:
            entries.append(
                {
                    "stage": stage,
                    "status": "blocked_preflight_unavailable",
                    "candidate_count": None,
                    "reason": "YAML6 did not produce a usable snapshot, so the dependent tail was not run.",
                }
            )
            continue
        if zero_tail and not attempt_empty:
            entries.append(
                {
                    "stage": stage,
                    "status": "blocked_zero_candidates",
                    "candidate_count": 0,
                    "reason": (
                        "The exact 10:00-12:30 America/New_York hard session gate leaves no "
                        "candidate/target rows; LightGBM fitting is not statistically estimable."
                    ),
                }
            )
            continue
        entry = _run_or_reuse(stage, rerun=rerun)
        entry.setdefault("candidate_count", candidate_count)
        entries.append(entry)
    _json_dump(RUN_INDEX_PATH, entries)
    return entries


def _stage_metrics(stage: int, entry: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame | None, pd.DataFrame]:
    base = {
        "stage": stage,
        "yaml": f"YAML{stage}",
        "label": STAGE_LABELS[stage],
        "status": entry.get("status", "missing"),
        "run_dir": entry.get("run_dir", ""),
    }
    if not entry.get("run_dir"):
        return base | {"candidate_count": entry.get("candidate_count", 0)}, None, pd.DataFrame()

    run_dir = Path(entry["run_dir"])
    payload = _json_load(run_dir / "summary.json")
    primary = dict(payload.get("summary", {}) or {})
    evaluation = dict(payload.get("evaluation", {}) or {})
    model_meta = dict(payload.get("model_meta", {}) or {})
    target_meta = dict(model_meta.get("target", {}) or {})
    frame = _read_snapshot(payload)
    trades = _read_trades(run_dir)

    candidate = frame["trend_vwap_base_candidate"].eq(1)
    pred = pd.to_numeric(frame.get("pred_tb_oriented_r"), errors="coerce")
    pred_oos = _as_bool(frame.get("pred_is_oos", pd.Series(False, index=frame.index)))
    oos_candidate = candidate & pred_oos
    scored_candidate = oos_candidate & pred.notna()
    accepted = pd.to_numeric(
        frame.get("accepted_trend_vwap_candidate", pd.Series(0.0, index=frame.index)),
        errors="coerce",
    ).fillna(0.0).gt(0.0)
    trade_r = pd.to_numeric(trades.get("trade_r", pd.Series(dtype=float)), errors="coerce")
    realized_target = pd.to_numeric(frame.get("tb_oriented_r"), errors="coerce")
    scored_count = int(scored_candidate.sum())

    row = base | {
        "candidate_count": int(candidate.sum()),
        "target_labeled_count": int(target_meta.get("labeled_rows", int(candidate.sum())) or 0),
        "oos_candidate_count": int(oos_candidate.sum()),
        "scored_oos_candidate_count": scored_count,
        "accepted_signal_count": int(accepted.sum()),
        "acceptance_rate": float(accepted.sum() / scored_count) if scored_count else math.nan,
        "trade_count": int(primary.get("trade_count", len(trades)) or 0),
        "cumulative_return": _safe_float(primary.get("cumulative_return")),
        "annualized_return": _safe_float(primary.get("annualized_return")),
        "annualized_vol": _safe_float(primary.get("annualized_vol")),
        "sharpe": _safe_float(primary.get("sharpe")),
        "sortino": _safe_float(primary.get("sortino")),
        "calmar": _safe_float(primary.get("calmar")),
        "max_drawdown": _safe_float(primary.get("max_drawdown")),
        "profit_factor": _safe_float(primary.get("profit_factor")),
        "hit_rate": _safe_float(primary.get("hit_rate")),
        "average_net_r": _finite_mean(trade_r),
        "median_net_r": _finite_median(trade_r),
        "avg_turnover": _safe_float(primary.get("avg_turnover")),
        "total_turnover": _safe_float(primary.get("total_turnover")),
        "gross_pnl": _safe_float(primary.get("gross_pnl")),
        "net_pnl": _safe_float(primary.get("net_pnl")),
        "total_cost": _safe_float(primary.get("total_cost")),
        "cost_to_gross_pnl": _safe_float(primary.get("cost_to_gross_pnl")),
        "exposure": _safe_float(primary.get("long_rate")),
        "oos_row_coverage": _safe_float(evaluation.get("oos_coverage")),
        "oos_prediction_coverage": _safe_float(model_meta.get("oos_prediction_coverage")),
        "avg_predicted_r": _finite_mean(pred.loc[scored_candidate]),
        "avg_realized_target_r": _finite_mean(realized_target.loc[scored_candidate]),
        "prediction_realized_spearman": _safe_float(
            pred.loc[scored_candidate].corr(realized_target.loc[scored_candidate], method="spearman")
        ),
        "walk_forward_positive_fold_ratio": _safe_float(
            primary.get("robustness_walk_forward_positive_fold_ratio")
        ),
        "cost_x2_cumulative_return": _safe_float(primary.get("robustness_cost_x2_cumulative_return")),
        "cost_x3_cumulative_return": _safe_float(primary.get("robustness_cost_x3_cumulative_return")),
        "cost_x5_cumulative_return": _safe_float(primary.get("robustness_cost_x5_cumulative_return")),
        "delay_1_cumulative_return": _safe_float(primary.get("robustness_delay_1_bars_cumulative_return")),
        "delay_2_cumulative_return": _safe_float(primary.get("robustness_delay_2_bars_cumulative_return")),
    }
    return row, frame, trades


def _calibration_rows(stage: int, frame: pd.DataFrame) -> list[dict[str, Any]]:
    candidate = frame["trend_vwap_base_candidate"].eq(1)
    pred = pd.to_numeric(frame["pred_tb_oriented_r"], errors="coerce")
    realized = pd.to_numeric(frame["tb_oriented_r"], errors="coerce")
    oos = _as_bool(frame["pred_is_oos"])
    work = pd.DataFrame({"predicted_r": pred, "realized_r": realized}).loc[candidate & oos].dropna()
    if work.empty:
        return []
    bins = min(5, len(work))
    work["bucket"] = pd.qcut(work["predicted_r"].rank(method="first"), q=bins, labels=False) + 1
    rows: list[dict[str, Any]] = []
    for bucket, group in work.groupby("bucket", sort=True):
        positive_r = float(group["realized_r"].clip(lower=0.0).sum())
        negative_r = float(-group["realized_r"].clip(upper=0.0).sum())
        rows.append(
            {
                "stage": stage,
                "bucket": int(bucket),
                "count": int(len(group)),
                "mean_predicted_r": float(group["predicted_r"].mean()),
                "mean_realized_r": float(group["realized_r"].mean()),
                "median_realized_r": float(group["realized_r"].median()),
                "realized_r_std": float(group["realized_r"].std(ddof=1)) if len(group) > 1 else math.nan,
                "positive_realized_rate": float(group["realized_r"].gt(0.0).mean()),
                "realized_r_profit_factor": positive_r / negative_r if negative_r > 0.0 else math.nan,
            }
        )
    return rows


def _year_rows(stage: int, run_dir: Path, trades: pd.DataFrame) -> list[dict[str, Any]]:
    returns = pd.read_csv(run_dir / "returns.csv", parse_dates=["timestamp"]).set_index("timestamp")["returns"]
    returns = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    trade_time = pd.to_datetime(trades.get("entry_time", pd.Series(dtype="datetime64[ns]")), errors="coerce")
    trade_r = pd.to_numeric(trades.get("trade_r", pd.Series(dtype=float)), errors="coerce")
    for year, year_returns in returns.groupby(returns.index.year):
        cumulative = float((1.0 + year_returns).prod() - 1.0)
        volatility = float(year_returns.std(ddof=1))
        sharpe = float(year_returns.mean() / volatility * math.sqrt(12096)) if volatility > 0 else math.nan
        equity = (1.0 + year_returns).cumprod()
        max_drawdown = float((equity / equity.cummax() - 1.0).min())
        positive_returns = float(year_returns.clip(lower=0.0).sum())
        negative_returns = float(-year_returns.clip(upper=0.0).sum())
        mask = trade_time.dt.year.eq(year)
        rows.append(
            {
                "stage": stage,
                "year": int(year),
                "cumulative_return": cumulative,
                "sharpe": sharpe,
                "max_drawdown": max_drawdown,
                "trade_count": int(mask.sum()),
                "profit_factor": positive_returns / negative_returns if negative_returns > 0.0 else math.nan,
                "average_r": _finite_mean(trade_r.loc[mask]),
            }
        )
    return rows


def _threshold_rows(stage: int, frame: pd.DataFrame, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    pred = pd.to_numeric(frame["pred_tb_oriented_r"], errors="coerce")
    candidate = frame["trend_vwap_base_candidate"].eq(1)
    oos = _as_bool(frame["pred_is_oos"])
    backtest = dict(cfg["backtest"])
    risk = dict(cfg["risk"])
    rows: list[dict[str, Any]] = []
    for threshold in (-0.25, 0.0, 0.25, 0.50, 0.75):
        signal_col = "_report_threshold_signal"
        work = frame.copy()
        work[signal_col] = (candidate & oos & pred.notna() & pred.ge(threshold)).astype(float)
        result = run_manual_barrier_backtest(
            work,
            signal_col=signal_col,
            open_col=str(backtest.get("open_col", "open")),
            high_col=str(backtest.get("high_col", "high")),
            low_col=str(backtest.get("low_col", "low")),
            close_col=str(backtest.get("close_col", "close")),
            take_profit_r=float(backtest["take_profit_r"]),
            stop_loss_r=float(backtest["stop_loss_r"]),
            risk_per_trade=float(backtest["risk_per_trade"]),
            max_holding_bars=int(backtest["max_holding_bars"]),
            cost_per_unit_turnover=float(risk.get("cost_per_turnover", 0.0)),
            slippage_per_unit_turnover=float(risk.get("slippage_per_turnover", 0.0)),
            max_leverage=float(risk.get("max_leverage", 1.0)),
            periods_per_year=int(backtest.get("periods_per_year", 12096)),
            allow_short=False,
            stop_mode=str(backtest.get("stop_mode", "volatility_stop")),
            vol_col=str(backtest.get("vol_col", "atr_over_price_20")),
        )
        subset_summary = compute_subset_metrics(
            net_returns=result.returns,
            turnover=result.turnover,
            costs=result.costs,
            gross_returns=result.gross_returns,
            periods_per_year=int(backtest.get("periods_per_year", 12096)),
            mask=oos,
        )
        trade_r = pd.to_numeric(result.trades.get("trade_r", pd.Series(dtype=float)), errors="coerce")
        rows.append(
            {
                "stage": stage,
                "threshold_r": threshold,
                "eligible_signal_count": int(work[signal_col].sum()),
                "trade_count": int(len(result.trades)),
                "cumulative_return": _safe_float(subset_summary.get("cumulative_return")),
                "sharpe": _safe_float(subset_summary.get("sharpe")),
                "max_drawdown": _safe_float(subset_summary.get("max_drawdown")),
                "profit_factor": _safe_float(subset_summary.get("profit_factor")),
                "average_r": _finite_mean(trade_r),
            }
        )
    return rows


def _apply_baseline_deltas(metrics: pd.DataFrame) -> pd.DataFrame:
    completed = metrics.loc[metrics["run_dir"].astype(str).ne("")].copy()
    if completed.empty or not completed["stage"].eq(0).any():
        return metrics
    baseline = completed.loc[completed["stage"].eq(0)].iloc[0]
    for column in ("cumulative_return", "sharpe", "max_drawdown", "profit_factor", "trade_count", "average_net_r"):
        metrics[f"delta_{column}_vs_yaml0"] = pd.to_numeric(metrics.get(column), errors="coerce") - _safe_float(
            baseline.get(column)
        )
    return metrics


def _style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color(GRID)
    axis.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.7)
    axis.set_axisbelow(True)
    axis.tick_params(colors=INK, labelsize=9)


def _build_charts(metrics: pd.DataFrame, calibration: pd.DataFrame) -> list[dict[str, Any]]:
    chart_map: list[dict[str, Any]] = []
    labels = metrics["yaml"].tolist()
    x = np.arange(len(labels))

    fig, axis = plt.subplots(figsize=(11, 5.5), constrained_layout=True)
    candidate = pd.to_numeric(metrics["candidate_count"], errors="coerce").fillna(0.0)
    accepted = pd.to_numeric(metrics.get("accepted_signal_count"), errors="coerce").fillna(0.0)
    width = 0.38
    bars_a = axis.bar(x - width / 2, candidate, width, color=BLUE, label="Base candidates")
    bars_b = axis.bar(x + width / 2, accepted, width, color=GOLD, label="Accepted OOS signals")
    axis.set_yscale("symlog", linthresh=1.0)
    axis.set_xticks(x, labels)
    axis.set_ylabel("Event count (symlog scale)")
    axis.set_title("Candidate and accepted-signal counts by YAML stage", color=INK, loc="left", weight="bold")
    axis.legend(frameon=False, ncols=2, loc="upper right")
    axis.bar_label(bars_a, labels=[f"{int(value):,}" for value in candidate], padding=2, fontsize=8, color=INK)
    axis.bar_label(bars_b, labels=[f"{int(value):,}" for value in accepted], padding=2, fontsize=8, color=INK)
    _style_axis(axis)
    candidate_chart = EVIDENCE_DIR / "candidate_acceptance_by_stage.png"
    fig.savefig(candidate_chart, dpi=170, facecolor="white")
    plt.close(fig)
    chart_map.append(
        {
            "section": "The exact session gate collapses the runnable tail",
            "question": "How do deterministic candidates and accepted OOS signals change through the ladder?",
            "family": "ordered stage comparison",
            "type": "grouped bar with symlog count axis",
            "fields": ["stage", "candidate_count", "accepted_signal_count"],
            "palette": {"candidate": BLUE, "accepted": GOLD},
            "artifact": str(candidate_chart),
        }
    )

    completed = metrics.loc[metrics["run_dir"].astype(str).ne("")].copy()
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7.2), constrained_layout=True, sharex=True)
    cx = np.arange(len(completed))
    returns = pd.to_numeric(completed["cumulative_return"], errors="coerce")
    sharpes = pd.to_numeric(completed["sharpe"], errors="coerce")
    axes[0].bar(cx, returns, color=[BLUE if value >= 0 else ORANGE for value in returns])
    axes[0].axhline(0.0, color=INK, linewidth=0.8)
    axes[0].set_ylabel("Net cumulative return")
    axes[0].set_title("Net performance of estimable ladder stages", color=INK, loc="left", weight="bold")
    axes[1].bar(cx, sharpes, color=[BLUE if value >= 0 else ORANGE for value in sharpes])
    axes[1].axhline(0.0, color=INK, linewidth=0.8)
    axes[1].set_ylabel("Annualized Sharpe")
    axes[1].set_xticks(cx, completed["yaml"].tolist())
    for axis in axes:
        _style_axis(axis)
    performance_chart = EVIDENCE_DIR / "performance_by_stage.png"
    fig.savefig(performance_chart, dpi=170, facecolor="white")
    plt.close(fig)
    chart_map.append(
        {
            "section": "Feature additions do not establish a robust net edge",
            "question": "Do cumulative additions improve net return and Sharpe versus YAML0?",
            "family": "comparison",
            "type": "aligned zero-baseline bars",
            "fields": ["stage", "cumulative_return", "sharpe"],
            "palette": {"nonnegative": BLUE, "negative": ORANGE},
            "artifact": str(performance_chart),
        }
    )

    available = sorted(calibration["stage"].unique()) if not calibration.empty else []
    selected = [available[0], available[-1]] if available else []
    selected = list(dict.fromkeys(selected))
    fig, axis = plt.subplots(figsize=(8.5, 5.5), constrained_layout=False)
    fig.subplots_adjust(left=0.10, right=0.97, bottom=0.13, top=0.88)
    for idx, stage in enumerate(selected):
        rows = calibration.loc[calibration["stage"].eq(stage)].sort_values("bucket")
        color = BLUE if idx == 0 else GOLD
        axis.plot(
            rows["mean_predicted_r"],
            rows["mean_realized_r"],
            marker="o",
            linewidth=1.8,
            color=color,
            label=f"YAML{stage}",
        )
        for _, row in rows.iterrows():
            bucket = int(row["bucket"])
            is_rightmost = idx == len(selected) - 1 and bucket == int(rows["bucket"].max())
            offset = (-5, 16) if is_rightmost else (4, 4)
            alignment = "right" if is_rightmost else "left"
            axis.annotate(
                f"Q{bucket} (n={int(row['count'])})",
                (row["mean_predicted_r"], row["mean_realized_r"]),
                xytext=offset,
                textcoords="offset points",
                fontsize=7,
                color=INK,
                ha=alignment,
            )
    axis.axhline(0.0, color=INK, linewidth=0.8)
    axis.axvline(0.0, color=INK, linewidth=0.8)
    axis.set_xlabel("Mean predicted R")
    axis.set_ylabel("Mean realized target R")
    axis.set_title("OOS predicted-R buckets versus realized target R", color=INK, loc="left", weight="bold")
    axis.margins(x=0.12, y=0.12)
    if selected:
        axis.legend(frameon=False, ncols=len(selected), loc="upper left")
    _style_axis(axis)
    calibration_chart = EVIDENCE_DIR / "predicted_vs_realized_r_buckets.png"
    fig.savefig(calibration_chart, dpi=170, facecolor="white")
    plt.close(fig)
    chart_map.append(
        {
            "section": "Expected-R ranking remains weak and sample-limited",
            "question": "Do higher predicted-R buckets realize higher oriented target R out of sample?",
            "family": "relationship",
            "type": "labeled line-dot calibration comparison",
            "fields": ["mean_predicted_r", "mean_realized_r", "count", "stage"],
            "palette": {"baseline": BLUE, "final_estimable": GOLD},
            "artifact": str(calibration_chart),
        }
    )
    _json_dump(EVIDENCE_DIR / "chart_map.json", chart_map)
    return chart_map


def _fmt(value: Any, *, percent: bool = False, decimals: int = 3) -> str:
    parsed = _safe_float(value)
    if not math.isfinite(parsed):
        return "NA"
    if percent:
        return f"{parsed * 100:.{decimals}f}%"
    return f"{parsed:.{decimals}f}"


def _markdown_table(rows: Iterable[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    materialized = list(rows)
    header = "| " + " | ".join(label for _, label in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(key, "")) for key, _ in columns) + " |" for row in materialized]
    return "\n".join([header, divider, *body])


def _render_report(
    metrics: pd.DataFrame,
    calibration: pd.DataFrame,
    yearly: pd.DataFrame,
    thresholds: pd.DataFrame,
    preflight: dict[str, Any],
) -> str:
    completed = metrics.loc[metrics["run_dir"].astype(str).ne("")].copy()
    baseline = completed.loc[completed["stage"].eq(0)].iloc[0]
    best = completed.loc[pd.to_numeric(completed["sharpe"], errors="coerce").idxmax()]
    final = completed.sort_values("stage").iloc[-1]
    status_rows = []
    for _, row in metrics.iterrows():
        status_rows.append(
            {
                "yaml": row["yaml"],
                "status": row["status"],
                "candidates": int(row.get("candidate_count", 0) or 0),
                "scored": int(row.get("scored_oos_candidate_count", 0) or 0) if pd.notna(row.get("scored_oos_candidate_count")) else "NA",
                "accepted": int(row.get("accepted_signal_count", 0) or 0) if pd.notna(row.get("accepted_signal_count")) else "NA",
                "trades": int(row.get("trade_count", 0) or 0) if pd.notna(row.get("trade_count")) else "NA",
                "return": _fmt(row.get("cumulative_return"), percent=True, decimals=2),
                "sharpe": _fmt(row.get("sharpe"), decimals=2),
                "dd": _fmt(row.get("max_drawdown"), percent=True, decimals=2),
                "delta": _fmt(row.get("delta_sharpe_vs_yaml0"), decimals=2),
            }
        )

    attribution = dict(preflight.get("attribution", {}) or {})
    attribution_rows = []
    for stage in (8, 9, 10):
        attribution_rows.append(
            {
                "yaml": f"YAML{stage}",
                "trend": attribution.get("rejected_trend", "NA"),
                "expansion": attribution.get("rejected_expansion", "NA"),
                "pullback": attribution.get("rejected_pullback", "NA"),
                "momentum": attribution.get("rejected_momentum", "NA"),
                "session": attribution.get("rejected_session", "NA"),
                "shock": attribution.get("rejected_shock", "NA"),
                "resistance": attribution.get("rejected_resistance", "NA"),
                "volatility": attribution.get("rejected_volatility", "NA"),
                "forecast": 0,
                "gap": 0 if stage == 10 else "NA",
                "cooldown": 0 if stage == 10 else "NA",
                "risk_guard": 0 if stage == 10 else "NA",
                "final": int(preflight.get("stage8_candidates", 0) or 0),
            }
        )

    final_years = yearly.loc[yearly["stage"].eq(int(final["stage"]))].copy()
    yearly_rows = [
        {
            "year": int(row["year"]),
            "return": _fmt(row["cumulative_return"], percent=True, decimals=2),
            "sharpe": _fmt(row["sharpe"], decimals=2),
            "dd": _fmt(row["max_drawdown"], percent=True, decimals=2),
            "trades": int(row["trade_count"]),
            "pf": _fmt(row["profit_factor"], decimals=2),
            "avg_r": _fmt(row["average_r"], decimals=3),
        }
        for _, row in final_years.iterrows()
    ]

    threshold_focus = thresholds.loc[thresholds["stage"].eq(int(final["stage"]))].copy()
    threshold_rows = [
        {
            "threshold": f"{row['threshold_r']:.2f}R",
            "signals": int(row["eligible_signal_count"]),
            "trades": int(row["trade_count"]),
            "return": _fmt(row["cumulative_return"], percent=True, decimals=2),
            "sharpe": _fmt(row["sharpe"], decimals=2),
            "dd": _fmt(row["max_drawdown"], percent=True, decimals=2),
            "avg_r": _fmt(row["average_r"], decimals=3),
        }
        for _, row in threshold_focus.iterrows()
    ]

    cost_rows = []
    for _, row in completed.iterrows():
        cost_rows.append(
            {
                "yaml": row["yaml"],
                "base": _fmt(row["cumulative_return"], percent=True, decimals=2),
                "x2": _fmt(row["cost_x2_cumulative_return"], percent=True, decimals=2),
                "x3": _fmt(row["cost_x3_cumulative_return"], percent=True, decimals=2),
                "x5": _fmt(row["cost_x5_cumulative_return"], percent=True, decimals=2),
                "delay1": _fmt(row["delay_1_cumulative_return"], percent=True, decimals=2),
                "delay2": _fmt(row["delay_2_cumulative_return"], percent=True, decimals=2),
                "positive_folds": _fmt(row["walk_forward_positive_fold_ratio"], percent=True, decimals=1),
            }
        )

    performance_detail_rows = [
        {
            "yaml": row["yaml"],
            "ann_return": _fmt(row["annualized_return"], percent=True, decimals=2),
            "ann_vol": _fmt(row["annualized_vol"], percent=True, decimals=2),
            "sortino": _fmt(row["sortino"], decimals=2),
            "calmar": _fmt(row["calmar"], decimals=2),
            "pf": _fmt(row["profit_factor"], decimals=2),
            "hit": _fmt(row["hit_rate"], percent=True, decimals=1),
            "avg_r": _fmt(row["average_net_r"], decimals=3),
            "median_r": _fmt(row["median_net_r"], decimals=3),
        }
        for _, row in completed.iterrows()
    ]
    execution_detail_rows = [
        {
            "yaml": row["yaml"],
            "acceptance": _fmt(row["acceptance_rate"], percent=True, decimals=1),
            "turnover": _fmt(row["total_turnover"], decimals=2),
            "cost": _fmt(row["total_cost"], decimals=3),
            "cost_gross": _fmt(row["cost_to_gross_pnl"], decimals=2),
            "exposure": _fmt(row["exposure"], percent=True, decimals=2),
            "oos_rows": _fmt(row["oos_row_coverage"], percent=True, decimals=1),
            "pred_coverage": _fmt(row["oos_prediction_coverage"], percent=True, decimals=1),
        }
        for _, row in completed.iterrows()
    ]
    delta_rows = [
        {
            "yaml": row["yaml"],
            "return": _fmt(row["delta_cumulative_return_vs_yaml0"], percent=True, decimals=2),
            "sharpe": _fmt(row["delta_sharpe_vs_yaml0"], decimals=2),
            "max_dd": _fmt(row["delta_max_drawdown_vs_yaml0"], percent=True, decimals=2),
            "pf": _fmt(row["delta_profit_factor_vs_yaml0"], decimals=2),
            "trades": _fmt(row["delta_trade_count_vs_yaml0"], decimals=0),
            "avg_r": _fmt(row["delta_average_net_r_vs_yaml0"], decimals=3),
        }
        for _, row in completed.iterrows()
    ]

    correlation_rows = [
        {
            "yaml": row["yaml"],
            "n": int(row.get("scored_oos_candidate_count", 0) or 0),
            "pred": _fmt(row["avg_predicted_r"], decimals=3),
            "realized": _fmt(row["avg_realized_target_r"], decimals=3),
            "rho": _fmt(row["prediction_realized_spearman"], decimals=3),
        }
        for _, row in completed.iterrows()
    ]

    monotonic_rows = []
    bucket_detail_rows = []
    for stage in sorted(calibration["stage"].unique()):
        stage_rows = calibration.loc[calibration["stage"].eq(stage)].sort_values("bucket")
        realized_means = pd.to_numeric(stage_rows["mean_realized_r"], errors="coerce")
        monotonic_rows.append(
            {
                "yaml": f"YAML{int(stage)}",
                "monotonic": "yes" if bool(realized_means.diff().dropna().ge(0.0).all()) else "no",
                "bucket_rho": _fmt(
                    stage_rows["bucket"].corr(realized_means, method="spearman"), decimals=3
                ),
            }
        )
        for _, row in stage_rows.iterrows():
            bucket_detail_rows.append(
                {
                    "yaml": f"YAML{int(stage)}",
                    "bucket": f"Q{int(row['bucket'])}",
                    "n": int(row["count"]),
                    "pred": _fmt(row["mean_predicted_r"], decimals=3),
                    "mean": _fmt(row["mean_realized_r"], decimals=3),
                    "median": _fmt(row["median_realized_r"], decimals=3),
                    "hit": _fmt(row["positive_realized_rate"], percent=True, decimals=1),
                    "pf": _fmt(row["realized_r_profit_factor"], decimals=2),
                }
            )

    run_commands = "\n".join(
        f".\\.venv312\\Scripts\\python.exe -m src.experiments.runner "
        f"config/experiments/foundation_alpha/trend_vwap_expected_r_us100_m30/{filename}"
        for filename in FILENAMES
    )
    inventory_rows = [
        {"path": "src/features/trend_vwap_pullback_candidate.py", "role": "Causal cumulative features, deterministic state, and event pulse."},
        {"path": "src/features/registry.py", "role": "Feature registry entry."},
        {"path": "src/signals/forecast_signal.py", "role": "Backward-compatible inclusive forecast thresholds."},
        {"path": "src/signals/forecast_threshold_candidate_signal.py", "role": "Candidate/OOS-gated signal adapter."},
        {"path": "src/backtesting/manual_barrier.py", "role": "Next-open gap, cooldown, and portfolio-risk execution guards."},
        {"path": "src/experiments/orchestration/backtest_stage.py", "role": "Execution-guard configuration wiring."},
        {"path": "src/risk/controls.py", "role": "Causal daily/weekly risk-guard multiplier."},
        {"path": "src/utils/config_validation.py", "role": "Validation for the new execution/risk fields."},
        {"path": "scripts/generate_us100_trend_vwap_expected_r_ladder.py", "role": "Deterministic standalone YAML generator."},
        {"path": "scripts/run_us100_trend_vwap_expected_r_ladder.py", "role": "Sequential runner, diagnostics, charts, and report builder."},
        {"path": "config/.../trend_vwap_expected_r_us100_m30/*.yaml", "role": "Eleven standalone cumulative experiment configs."},
        {"path": "tests/features/test_trend_vwap_pullback_candidate.py", "role": "Causality, DST/session, path, shock, and resistance tests."},
        {"path": "tests/experiments/test_us100_trend_vwap_expected_r.py", "role": "Config, target, OOS signal, gap, cooldown, and no-pyramiding tests."},
    ]

    data_start = "2015-01-02"
    data_end = "2026-05-19"
    report = f"""# US100 M30 Trend-VWAP Expected-R Ladder

## Technical summary

- **No tested configuration establishes a robust net edge.** The baseline YAML0 returned {_fmt(baseline['cumulative_return'], percent=True, decimals=2)} with Sharpe {_fmt(baseline['sharpe'], decimals=2)} after the locked 15 bp turnover cost plus 10 bp slippage model. The best estimable Sharpe is {_fmt(best['sharpe'], decimals=2)} at {best['yaml']}, and must be interpreted with its candidate/trade sample size.
- **The exact candidate path becomes statistically non-estimable at the session gate.** YAML6 has {int(final['candidate_count'])} full-history candidate events; enforcing `10:00 <= America/New_York time < 12:30` produces {int(preflight.get('stage7_candidates', 0) or 0)} YAML7 candidates. YAML7–10 therefore have no target rows and are reported as blocked, not as zero-return strategies.
- **The requested YAML0→YAML10 cumulative difference is `NA`, not +10.47 percentage points.** YAML10 has no estimable return series under the exact rules; subtracting YAML0 from an invented flat YAML10 result would be analytically false.
- **Costs are material and ranking quality is weak.** YAML0's cost-to-gross-PnL ratio is {_fmt(baseline['cost_to_gross_pnl'], decimals=2)}, while its OOS predicted-versus-realized Spearman correlation is {_fmt(baseline['prediction_realized_spearman'], decimals=3)}. Threshold and cost/delay sensitivity results below do not justify promoting the strategy.
- **Decision:** retain the implementation as a causal research scaffold, but do not designate YAML10 as production-ready on this dataset. The next admissible step is a pre-registered session-window sensitivity study or a longer independent US100 history, not post-hoc feature/threshold tuning on the same sample.

## The exact session gate collapses the runnable tail

The figure compares full-history deterministic candidates with OOS signals that pass the expected-R threshold. Counts use event pulses, not persistent state rows. A symlog axis keeps the zero-candidate tail visible while preserving the large YAML0–3 counts.

![Candidate and accepted-signal counts]({EVIDENCE_DIR.name}/candidate_acceptance_by_stage.png)

{_markdown_table(status_rows, [('yaml', 'Stage'), ('status', 'Run status'), ('candidates', 'Candidates'), ('scored', 'Scored OOS'), ('accepted', 'Accepted signals'), ('trades', 'Trades'), ('return', 'Net return'), ('sharpe', 'Sharpe'), ('dd', 'Max DD'), ('delta', 'Δ Sharpe vs YAML0')])}

Status `blocked_zero_candidates` means the exact deterministic rules produced no target rows; performance metrics are intentionally `NA`.

## Feature additions do not establish a robust net edge

All estimable stages use the same purged walk-forward LightGBM, target, execution timing, stops, profit target, holding horizon, sizing, and costs. The bars therefore isolate the cumulative YAML feature/candidate changes, though the changing candidate population prevents a causal feature-attribution claim.

![Net performance by stage]({EVIDENCE_DIR.name}/performance_by_stage.png)

YAML0 is the comparison baseline. Positive deltas are descriptive OOS differences on the same historical source, not independent confirmation; later stages have much smaller samples and wider uncertainty.

The next two tables expose the complete requested risk/performance and execution/cost metric set for every estimable YAML. `Total cost` and `turnover` are return-space accounting totals over the experiment timeline; exposure is the fraction of OOS bars held long.

{_markdown_table(performance_detail_rows, [('yaml', 'Stage'), ('ann_return', 'Ann. return'), ('ann_vol', 'Ann. vol'), ('sortino', 'Sortino'), ('calmar', 'Calmar'), ('pf', 'Profit factor'), ('hit', 'Hit rate'), ('avg_r', 'Mean net R'), ('median_r', 'Median net R')])}

{_markdown_table(execution_detail_rows, [('yaml', 'Stage'), ('acceptance', 'Acceptance'), ('turnover', 'Total turnover'), ('cost', 'Total cost'), ('cost_gross', 'Cost/gross PnL'), ('exposure', 'Exposure'), ('oos_rows', 'OOS row coverage'), ('pred_coverage', 'OOS prediction coverage')])}

Baseline deltas use `stage metric − YAML0 metric`. For maximum drawdown, a positive delta means a shallower (less negative) drawdown; a negative trade-count delta means fewer executed trades.

{_markdown_table(delta_rows, [('yaml', 'Stage'), ('return', 'Δ return'), ('sharpe', 'Δ Sharpe'), ('max_dd', 'Δ max DD'), ('pf', 'Δ profit factor'), ('trades', 'Δ trades'), ('avg_r', 'Δ mean net R')])}

## Expected-R ranking remains weak and sample-limited

The calibration view bins scored OOS candidate events into equal-count predicted-R buckets for YAML0 and the final estimable stage. A useful model should generally order the bucket-level realized target R upward; sparse late-stage buckets make this check especially uncertain.

![Predicted versus realized R buckets]({EVIDENCE_DIR.name}/predicted_vs_realized_r_buckets.png)

{_markdown_table(correlation_rows, [('yaml', 'Stage'), ('n', 'Scored OOS n'), ('pred', 'Mean predicted R'), ('realized', 'Mean realized target R'), ('rho', 'Spearman ρ')])}

The strict monotonicity test uses the five bucket-level mean realized-R values in predicted-R order. No stage is called monotonic unless every adjacent bucket is non-decreasing.

{_markdown_table(monotonic_rows, [('yaml', 'Stage'), ('monotonic', 'Monotonic realized R?'), ('bucket_rho', 'Bucket-mean Spearman ρ')])}

The audit table below provides every requested bucket statistic. Profit factor is the sum of positive realized target R divided by the absolute sum of negative realized target R inside the bucket.

{_markdown_table(bucket_detail_rows, [('yaml', 'Stage'), ('bucket', 'Bucket'), ('n', 'n'), ('pred', 'Mean predicted R'), ('mean', 'Mean realized R'), ('median', 'Median realized R'), ('hit', 'Hit rate'), ('pf', 'Profit factor')])}

The target R in this section is the candidate-aligned triple-barrier outcome. Trade-level net R differs because execution includes spread/slippage costs, non-pyramiding, and potentially overlapping signals.

## Candidate rejection attribution pinpoints the hard bottleneck

Attribution starts from current-bar VWAP reclaim events and applies the hard rules sequentially in the documented order. A row is counted at the first filter that rejects it; counts are therefore mutually exclusive within a row. Because the session step leaves no rows, shock, resistance, volatility, forecast, gap, cooldown, and portfolio guards have no eligible events to reject in YAML8–10.

{_markdown_table(attribution_rows, [('yaml', 'Stage'), ('trend', 'Trend'), ('expansion', 'Expansion'), ('pullback', 'Pullback'), ('momentum', 'Momentum'), ('session', 'Session'), ('shock', 'Shock'), ('resistance', 'Resistance'), ('volatility', 'Volatility'), ('forecast', 'Forecast'), ('gap', 'Gap'), ('cooldown', 'Cooldown'), ('risk_guard', 'Daily/weekly guard'), ('final', 'Final candidates')])}

The reclaim-event universe contains {int(attribution.get('reclaim_event_universe', 0) or 0):,} events. This diagnostic is a sequential rule funnel; it is not a count of independent causal reasons, since a rejected row may also fail later filters.

## Robustness checks do not rescue the final estimable specification

The table reports complete-run net returns under the configured cost multipliers and one-/two-bar entry delays. The final column is the share of yearly walk-forward slices with positive cumulative return.

{_markdown_table(cost_rows, [('yaml', 'Stage'), ('base', 'Base cost'), ('x2', '2× cost'), ('x3', '3× cost'), ('x5', '5× cost'), ('delay1', '+1 bar'), ('delay2', '+2 bars'), ('positive_folds', 'Positive WF folds')])}

The following threshold scan uses the final estimable stage ({final['yaml']}), holds the candidate definition fixed, requires a finite OOS prediction, and reruns the same next-open manual-barrier engine at each inclusive threshold.

{_markdown_table(threshold_rows, [('threshold', 'Threshold'), ('signals', 'Eligible signals'), ('trades', 'Trades'), ('return', 'Net return'), ('sharpe', 'Sharpe'), ('dd', 'Max DD'), ('avg_r', 'Mean net R')])}

Year-by-year results for {final['yaml']} show whether aggregate performance is broad or concentrated. The first partial year begins on {data_start}; 2026 is partial through {data_end}.

{_markdown_table(yearly_rows, [('year', 'Year'), ('return', 'Net return'), ('sharpe', 'Sharpe'), ('dd', 'Max DD'), ('trades', 'Trades'), ('pf', 'Profit factor'), ('avg_r', 'Mean net R')])}

## Scope, data, and metric definitions

- **Population:** one instrument (`US100`), 30-minute Dukascopy-derived OHLCV, {data_start} through {data_end}, 118,913 sorted unique bars. Naive source timestamps are normalized as UTC; session logic is converted to `America/New_York` with DST-aware timezone rules. Seven non-positive volume observations are treated as unavailable for VWAP accumulation; price fields have no missing or non-positive values.
- **Candidate denominator:** `candidate_count` is the full-history false→true deterministic event pulse. `scored_oos_candidate_count` additionally requires `pred_is_oos=true` and a finite predicted R. `acceptance_rate = accepted OOS signals / scored OOS candidates`.
- **Return metrics:** manual-barrier net return uses entry at the next bar open, 1.5R stop, 3.0R take profit, maximum 16 bars, 0.3% risk per trade, no pyramiding, 15 bp cost per unit turnover, and 10 bp slippage per unit turnover. Annualization uses 12,096 M30 periods/year.
- **Target:** candidate-masked long-oriented triple barrier, next-open entry, ATR20/price volatility, lower-tie priority, clipped to [−1.25R, 2.25R].
- **Baseline:** every `Δ ... vs YAML0` value subtracts YAML0's metric; blocked stages have no performance delta.

## Model specification and validation design

Every YAML is standalone. Estimable stages use a deterministic LightGBM regressor (`400` trees, `learning_rate=0.025`, `num_leaves=15`, `max_depth=5`, `min_child_samples=120`, `subsample=0.8`, `colsample_bytree=0.75`, `reg_alpha=0.25`, `reg_lambda=2.0`, seed 7, one thread). The purged expanding walk-forward split uses 35,040 training bars, 4,380 test bars, 4,380-bar step, 24-bar purge, 24-bar embargo, and at most 17 folds. Executable signals require both the deterministic candidate pulse and `pred_is_oos=true`; thresholds are inclusive.

Raw price-level EMA/Ehlers series are retained for deterministic rule construction but excluded from the predictive feature lists where a normalized economic representation exists. `session_id_ny` is context metadata rather than a numeric model input. These are explicit modeling assumptions, not inferred results.

## Implementation and reproducibility

{_markdown_table(inventory_rows, [('path', 'Path'), ('role', 'Role')])}

Run each standalone YAML from the repository root:

```powershell
{run_commands}
```

Run/reuse the entire ladder, preflight non-estimable stages, and rebuild the report:

```powershell
.\\.venv312\\Scripts\\python.exe scripts/run_us100_trend_vwap_expected_r_ladder.py --mode all
```

Use `--rerun` to force new completed experiment runs, or `--attempt-empty` to demonstrate the explicit zero-target model failure for YAML7–10 instead of preflight-skipping them.

## Limitations, uncertainty, and validation status

- **Overall assessment: Share with caveats.** Code paths and arithmetic are reproducible, but YAML7–10 are non-estimable under the locked rules, and late estimable stages have very small candidate samples.
- The comparison is predictive/descriptive, not causal. Each YAML changes both feature space and, from YAML2 onward, parts of the deterministic candidate definition.
- Purging and embargo address label overlap, not selection bias from designing the ladder on the same instrument/history. No untouched external confirmation dataset was supplied.
- The source is an index/CFD-style Dukascopy series with tick-volume-like `volume`; it is not consolidated NASDAQ cash volume. Session VWAP is therefore internally consistent with the requested source but not exchange-volume VWAP.
- `min_child_samples=120` is locked while YAML4–6 have fewer candidate labels than that in some or all training windows. LightGBM can still emit predictions, but model flexibility and calibration are severely constrained; late-stage metrics should not be generalized.
- The 2026 yearly row is partial. No claim is made that annual slices are independent, identically distributed, or statistically significant.
- The focused strategy suite passes 26/26 tests. A broader selected regression run passes 166 tests and has 10 unrelated baseline failures: missing legacy config files and one pre-existing unregistered `vol_normalized_momentum` component; those repository gaps were not changed for this task.

## Recommended next steps

1. Freeze this implementation and its current report as the negative/feasibility baseline.
2. Pre-register a small session-window sensitivity grid (for example, 10:00–12:30 versus 10:00–15:30 New York) and evaluate it on an untouched later period or separate feed; do not select the window on the same reported sample.
3. Require a minimum candidate/label count per training fold before model fitting and report confidence intervals or bootstrap dispersion for trade and calibration metrics.
4. If the exact session rule is non-negotiable, acquire a longer or higher-granularity US100 history before estimating YAML7–10.

## Further questions

- Is the 10:00–12:30 window a domain constraint or a tunable hypothesis?
- Should the VWAP anchor use exchange cash-volume data rather than the provided tick-volume proxy?
- What independent period or broker/feed should serve as the final confirmation sample?
"""
    return report


def build_report(entries: list[dict[str, Any]]) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    preflight_path = EVIDENCE_DIR / "preflight.json"
    preflight = _json_load(preflight_path) if preflight_path.exists() else {}

    metric_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    for stage in range(11):
        entry = next((item for item in entries if int(item.get("stage", -1)) == stage), {"stage": stage, "status": "missing"})
        row, frame, trades = _stage_metrics(stage, entry)
        metric_rows.append(row)
        if frame is None:
            continue
        calibration_rows.extend(_calibration_rows(stage, frame))
        run_dir = Path(entry["run_dir"])
        yearly_rows.extend(_year_rows(stage, run_dir, trades))
        cfg = load_experiment_config(CONFIG_DIR / FILENAMES[stage])
        threshold_rows.extend(_threshold_rows(stage, frame, cfg))

    metrics = _apply_baseline_deltas(pd.DataFrame(metric_rows).sort_values("stage").reset_index(drop=True))
    calibration = pd.DataFrame(calibration_rows)
    yearly = pd.DataFrame(yearly_rows)
    thresholds = pd.DataFrame(threshold_rows)
    metrics.to_csv(EVIDENCE_DIR / "stage_metrics.csv", index=False)
    calibration.to_csv(EVIDENCE_DIR / "predicted_r_calibration.csv", index=False)
    yearly.to_csv(EVIDENCE_DIR / "yearly_metrics.csv", index=False)
    thresholds.to_csv(EVIDENCE_DIR / "threshold_scan.csv", index=False)
    pd.DataFrame([dict(preflight.get("attribution", {}) or {})]).to_csv(
        EVIDENCE_DIR / "candidate_rejection_attribution.csv", index=False
    )
    _build_charts(metrics, calibration)
    report = _render_report(metrics, calibration, yearly, thresholds, preflight)
    REPORT_PATH.write_text(report, encoding="utf-8")
    _json_dump(
        EVIDENCE_DIR / "source_notes.json",
        {
            "audience": "technical",
            "delivery_surface": "repository Markdown report requested by the specification",
            "question": "Which cumulative YAML stage improves a causal US100 M30 expected-R strategy?",
            "comparison_baseline": "YAML0",
            "raw_source": str(RAW_PATH),
            "raw_period": ["2015-01-02", "2026-05-19"],
            "run_index": str(RUN_INDEX_PATH),
            "metric_source": str(EVIDENCE_DIR / "stage_metrics.csv"),
            "calibration_source": str(EVIDENCE_DIR / "predicted_r_calibration.csv"),
            "yearly_source": str(EVIDENCE_DIR / "yearly_metrics.csv"),
            "threshold_source": str(EVIDENCE_DIR / "threshold_scan.csv"),
            "validation": {
                "focused_tests": "26 passed",
                "selected_regression_tests": "166 passed, 10 unrelated baseline failures",
                "raw_rows": 118913,
                "raw_duplicate_timestamps": 0,
                "raw_missing_ohlcv_values": 0,
                "raw_nonpositive_price_values": 0,
                "raw_nonpositive_volume_values": 7,
                "candidate_equals_target_labels": "verified for YAML0-YAML6",
                "threshold_zero_reconciliation_max_abs_error": "< 6e-9 for return and Sharpe",
                "yearly_compound_reconciliation_max_abs_error": "< 3e-15",
            },
            "omissions": {
                "yaml7_to_yaml10_performance": "No exact-rule candidate or target rows; metrics are non-estimable.",
                "gap_cooldown_portfolio_guard_effect": "No YAML10 entries reach execution guards.",
            },
            "required_structure_mapping": {
                "technical_summary": "Technical summary",
                "key_findings": [
                    "The exact session gate collapses the runnable tail",
                    "Feature additions do not establish a robust net edge",
                    "Expected-R ranking remains weak and sample-limited",
                ],
                "scope_and_definitions": "Scope, data, and metric definitions",
                "methodology": "Model specification and validation design",
                "limitations": "Limitations, uncertainty, and validation status",
                "next_steps": "Recommended next steps",
                "further_questions": "Further questions",
            },
        },
    )
    return REPORT_PATH


def _load_run_index() -> list[dict[str, Any]]:
    if RUN_INDEX_PATH.exists():
        with RUN_INDEX_PATH.open("r", encoding="utf-8") as handle:
            return list(json.load(handle))
    entries: list[dict[str, Any]] = []
    for stage in range(11):
        run_dir = _latest_run_dir(stage)
        entries.append(
            {
                "stage": stage,
                "status": "reused" if run_dir else "missing",
                "run_dir": str(run_dir) if run_dir else "",
            }
        )
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("all", "run", "report"), default="all")
    parser.add_argument("--rerun", action="store_true", help="Rerun stages even when successful artifacts exist.")
    parser.add_argument(
        "--attempt-empty",
        action="store_true",
        help="Attempt YAML7-10 even when the causal preflight finds zero candidates.",
    )
    args = parser.parse_args()

    if args.mode in {"all", "run"}:
        entries = run_ladder(rerun=bool(args.rerun), attempt_empty=bool(args.attempt_empty))
    else:
        entries = _load_run_index()
    if args.mode in {"all", "report"}:
        report_path = build_report(entries)
        print(f"Report: {report_path}", flush=True)


if __name__ == "__main__":
    main()


__all__ = ["build_report", "run_ladder"]
