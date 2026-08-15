from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics, profit_factor
from src.experiments.support.ethusd_broker_alpha import STRESS_GRID, TickStressSpec
from src.features.ethusd_custom_alpha import add_ethusd_custom_alpha_features
from src.src_data.ctrader_export import load_ctrader_bar_export, load_ctrader_tick_export
from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path
from src.utils.run_metadata import collect_git_metadata, file_sha256


CTRADER_ROOT = PROJECT_ROOT / "data/ETHUSD"
DEVELOPMENT_END = pd.Timestamp("2023-12-31 23:59:59")
VALIDATION_START = pd.Timestamp("2024-01-01 00:00:00")
VALIDATION_END = pd.Timestamp("2025-06-30 23:59:59")
LOCKED_START = pd.Timestamp("2025-07-01 00:00:00")

BASE_COMMISSION_BPS_PER_SIDE = 0.5
LOCKED_WIN_RATE_GATE = 0.70
LOCKED_MIN_TRADES = 50
EXACT_MIN_TRADES = 30
PROFIT_FACTOR_GATE = 1.20
SHARPE_GATE = 1.0


@dataclass(frozen=True)
class CandidateSpec:
    score_threshold: float
    flow_threshold: float
    compression_max: float
    release_min: float
    target_r: float
    stop_r: float
    max_holding_bars: int

    @property
    def candidate_id(self) -> str:
        return (
            f"score_{self.score_threshold:.2f}__flow_{self.flow_threshold:.2f}__"
            f"comp_{self.compression_max:.2f}__release_{self.release_min:.2f}__"
            f"target_{self.target_r:.2f}r__stop_{self.stop_r:.2f}r__"
            f"hold_{self.max_holding_bars}"
        )


CANDIDATE_GRID = tuple(
    CandidateSpec(
        score_threshold=score,
        flow_threshold=flow,
        compression_max=compression,
        release_min=release,
        target_r=target,
        stop_r=1.0,
        max_holding_bars=holding,
    )
    for score, flow, compression, release, target, holding in itertools.product(
        (0.25, 0.35, 0.45),
        (0.15, 0.25),
        (0.90, 1.10),
        (0.90, 1.10),
        (0.60, 0.80),
        (16, 24),
    )
)


def candidate_triggers(frame: pd.DataFrame, spec: CandidateSpec) -> pd.Series:
    """Return sparse symmetric pulses from completed custom-indicator bars."""

    required = (
        "casc_score",
        "laf_directional_flow",
        "pcp_consensus",
        "pcp_scale_agreement",
        "cre_compression",
        "cre_release",
        "causal_range_energy",
    )
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise KeyError(f"Custom-alpha frame is missing columns: {missing}")
    score = pd.to_numeric(frame["casc_score"], errors="coerce")
    flow = pd.to_numeric(frame["laf_directional_flow"], errors="coerce")
    path = pd.to_numeric(frame["pcp_consensus"], errors="coerce")
    direction = np.sign(score).astype(float)
    aligned = (
        np.sign(flow).eq(direction)
        & np.sign(path).eq(direction)
        & pd.to_numeric(frame["pcp_scale_agreement"], errors="coerce").ge(2.0 / 3.0)
    )
    valid_risk = pd.to_numeric(frame["causal_range_energy"], errors="coerce").between(
        0.0005, 0.05
    )
    active = (
        score.abs().ge(spec.score_threshold)
        & flow.abs().ge(spec.flow_threshold)
        & pd.to_numeric(frame["cre_compression"], errors="coerce").le(
            spec.compression_max
        )
        & pd.to_numeric(frame["cre_release"], errors="coerce").ge(spec.release_min)
        & aligned
        & valid_risk
    )
    state = pd.Series(np.where(active, direction, 0.0), index=frame.index, dtype=float)
    pulse = state.where(state.ne(0.0) & state.ne(state.shift(1).fillna(0.0)), 0.0)
    pulse.name = "custom_signal"
    return pulse.astype("int8")


def bar_barrier_ledger(
    frame: pd.DataFrame,
    spec: CandidateSpec,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    round_trip_cost_bps: float,
) -> pd.DataFrame:
    """Replay next-bar entries with conservative OHLC first-passage barriers."""

    if start > end:
        raise ValueError("start must not be after end.")
    if not np.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0.0:
        raise ValueError("round_trip_cost_bps must be finite and non-negative.")
    triggers = candidate_triggers(frame, spec)
    index = frame.index
    candidate_positions = np.flatnonzero(
        triggers.ne(0.0).to_numpy()
        & (index >= pd.Timestamp(start))
        & (index <= pd.Timestamp(end))
    )
    rows: list[dict[str, Any]] = []
    last_exit_position = -1
    cost_return = float(round_trip_cost_bps) / 10_000.0
    for signal_position in candidate_positions:
        if signal_position <= last_exit_position:
            continue
        entry_position = int(signal_position + 1)
        if entry_position >= len(frame) or index[entry_position] > end:
            continue
        risk_fraction = float(frame["causal_range_energy"].iloc[signal_position])
        if not np.isfinite(risk_fraction) or not 0.0005 <= risk_fraction <= 0.05:
            continue
        side = int(triggers.iloc[signal_position])
        entry_price = float(frame["open"].iloc[entry_position])
        if not np.isfinite(entry_price) or entry_price <= 0.0:
            continue
        target_price = entry_price * (1.0 + side * spec.target_r * risk_fraction)
        stop_price = entry_price * (1.0 - side * spec.stop_r * risk_fraction)
        maximum_exit_position = min(
            entry_position + spec.max_holding_bars - 1,
            len(frame) - 1,
        )
        while maximum_exit_position >= entry_position and index[maximum_exit_position] > end:
            maximum_exit_position -= 1
        if maximum_exit_position < entry_position:
            continue

        exit_position = maximum_exit_position
        exit_price = float(frame["close"].iloc[maximum_exit_position])
        outcome = "timeout"
        for bar_position in range(entry_position, maximum_exit_position + 1):
            open_price = float(frame["open"].iloc[bar_position])
            high_price = float(frame["high"].iloc[bar_position])
            low_price = float(frame["low"].iloc[bar_position])
            if side > 0:
                if open_price <= stop_price:
                    exit_position, exit_price, outcome = bar_position, open_price, "stop_gap"
                    break
                if open_price >= target_price:
                    exit_position, exit_price, outcome = bar_position, open_price, "target_gap"
                    break
                stop_hit = low_price <= stop_price
                target_hit = high_price >= target_price
            else:
                if open_price >= stop_price:
                    exit_position, exit_price, outcome = bar_position, open_price, "stop_gap"
                    break
                if open_price <= target_price:
                    exit_position, exit_price, outcome = bar_position, open_price, "target_gap"
                    break
                stop_hit = high_price >= stop_price
                target_hit = low_price <= target_price
            if stop_hit:
                exit_position, exit_price, outcome = bar_position, stop_price, "stop_first"
                break
            if target_hit:
                exit_position, exit_price, outcome = bar_position, target_price, "target_first"
                break

        gross_return = side * (exit_price / entry_price - 1.0)
        net_return = gross_return - cost_return
        rows.append(
            {
                "candidate_id": spec.candidate_id,
                "signal_timestamp": index[signal_position],
                "entry_timestamp": index[entry_position],
                "exit_timestamp": index[exit_position] + pd.Timedelta(minutes=30),
                "side": "long" if side > 0 else "short",
                "side_numeric": side,
                "signal_score": float(frame["casc_score"].iloc[signal_position]),
                "risk_fraction": risk_fraction,
                "entry_price": entry_price,
                "target_price": target_price,
                "stop_price": stop_price,
                "exit_price": exit_price,
                "outcome": outcome,
                "holding_bars": int(exit_position - entry_position + 1),
                "gross_return": gross_return,
                "estimated_cost_return": cost_return,
                "net_return": net_return,
            }
        )
        last_exit_position = exit_position
    return pd.DataFrame(rows)


def trade_metrics(ledger: pd.DataFrame, *, evidence_scope: str) -> dict[str, Any]:
    if ledger.empty:
        return {
            "evidence_scope": evidence_scope,
            "trade_count": 0,
            "cumulative_return": 0.0,
            "conventional_sharpe": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "trade_profit_factor": 0.0,
            "average_trade_return": 0.0,
            "long_trade_count": 0,
            "short_trade_count": 0,
        }
    ordered = ledger.sort_values("exit_timestamp")
    index = pd.DatetimeIndex(ordered["exit_timestamp"])
    net = pd.Series(ordered["net_return"].to_numpy(dtype=float), index=index)
    gross = pd.Series(ordered["gross_return"].to_numpy(dtype=float), index=index)
    costs = gross - net
    metrics = compute_backtest_metrics(
        net_returns=net,
        gross_returns=gross,
        costs=costs,
        periods_per_year=365,
        annualization_mode="calendar_daily",
    )
    positive = ordered.loc[ordered["net_return"] > 0.0, "net_return"]
    positive_sum = float(positive.sum())
    metrics.update(
        {
            "evidence_scope": evidence_scope,
            "trade_count": int(len(ordered)),
            "win_rate": float((ordered["net_return"] > 0.0).mean()),
            "trade_profit_factor": float(profit_factor(ordered["net_return"])),
            "average_trade_return": float(ordered["net_return"].mean()),
            "median_trade_return": float(ordered["net_return"].median()),
            "long_trade_count": int(ordered["side"].eq("long").sum()),
            "short_trade_count": int(ordered["side"].eq("short").sum()),
            "best_trade_positive_pnl_concentration": (
                float(positive.max() / positive_sum) if positive_sum > 0.0 else 0.0
            ),
            "evaluation_start": pd.Timestamp(ordered["entry_timestamp"].min()).isoformat(),
            "evaluation_end": pd.Timestamp(ordered["exit_timestamp"].max()).isoformat(),
        }
    )
    return metrics


def select_candidate(
    frame: pd.DataFrame,
    *,
    round_trip_cost_bps: float,
) -> tuple[CandidateSpec | None, pd.DataFrame, dict[str, Any]]:
    """Select from development and validation only; locked rows are not read."""

    records: list[dict[str, Any]] = []
    for spec in CANDIDATE_GRID:
        development = (
            bar_barrier_ledger(
                frame,
                spec,
                start=frame.index.min(),
                end=DEVELOPMENT_END,
                round_trip_cost_bps=round_trip_cost_bps,
            )
            if frame.index.min() <= DEVELOPMENT_END
            else pd.DataFrame()
        )
        validation = (
            bar_barrier_ledger(
                frame,
                spec,
                start=VALIDATION_START,
                end=min(VALIDATION_END, frame.index.max()),
                round_trip_cost_bps=round_trip_cost_bps,
            )
            if frame.index.max() >= VALIDATION_START
            else pd.DataFrame()
        )
        dev_metrics = trade_metrics(development, evidence_scope="development bar first-passage")
        val_metrics = trade_metrics(validation, evidence_scope="validation bar first-passage")
        robust_win = min(float(dev_metrics["win_rate"]), float(val_metrics["win_rate"]))
        robust_pf = min(
            float(dev_metrics["trade_profit_factor"]),
            float(val_metrics["trade_profit_factor"]),
        )
        robust_sharpe = min(
            float(dev_metrics["conventional_sharpe"]),
            float(val_metrics["conventional_sharpe"]),
        )
        eligible = (
            int(dev_metrics["trade_count"]) >= 80
            and int(val_metrics["trade_count"]) >= 40
            and float(dev_metrics["cumulative_return"]) > 0.0
            and float(val_metrics["cumulative_return"]) > 0.0
            and float(dev_metrics["average_trade_return"]) > 0.0
            and float(val_metrics["average_trade_return"]) > 0.0
            and robust_pf > 1.0
        )
        selection_score = (
            3.0 * robust_win
            + np.log(max(robust_pf, 1.0e-6))
            + 0.20 * float(np.clip(robust_sharpe, -3.0, 3.0))
        )
        records.append(
            {
                "candidate_id": spec.candidate_id,
                **asdict(spec),
                "eligible": bool(eligible),
                "selection_score": float(selection_score),
                "robust_win_rate": robust_win,
                "robust_profit_factor": robust_pf,
                "robust_conventional_sharpe": robust_sharpe,
                **{f"development_{key}": value for key, value in dev_metrics.items()},
                **{f"validation_{key}": value for key, value in val_metrics.items()},
            }
        )
    table = pd.DataFrame(records).sort_values(
        ["eligible", "selection_score", "robust_win_rate", "robust_profit_factor"],
        ascending=[False, False, False, False],
    )
    eligible_rows = table.loc[table["eligible"]]
    diagnostic_leader = str(table.iloc[0]["candidate_id"])
    if eligible_rows.empty:
        status = {
            "status": "no_candidate_passed_development_gate",
            "candidate_count": int(len(table)),
            "eligible_candidate_count": 0,
            "selected_candidate_id": None,
            "diagnostic_leader_id": diagnostic_leader,
            "selection_inputs": "development and validation only; locked rows excluded",
            "locked_evaluation_authorized": False,
        }
        return None, table, status
    selected_row = eligible_rows.iloc[0]
    selected = CandidateSpec(
        score_threshold=float(selected_row["score_threshold"]),
        flow_threshold=float(selected_row["flow_threshold"]),
        compression_max=float(selected_row["compression_max"]),
        release_min=float(selected_row["release_min"]),
        target_r=float(selected_row["target_r"]),
        stop_r=float(selected_row["stop_r"]),
        max_holding_bars=int(selected_row["max_holding_bars"]),
    )
    status = {
        "status": "selected_from_eligible_set",
        "candidate_count": int(len(table)),
        "eligible_candidate_count": int(table["eligible"].sum()),
        "selected_candidate_id": selected.candidate_id,
        "diagnostic_leader_id": diagnostic_leader,
        "selection_inputs": "development and validation only; locked rows excluded",
        "locked_evaluation_authorized": True,
        "selection_score": float(selected_row["selection_score"]),
    }
    return selected, table, status


def exact_tick_barrier_ledger(
    frame: pd.DataFrame,
    ticks: pd.DataFrame,
    spec: CandidateSpec,
    *,
    stress: TickStressSpec,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Replay the locked custom signal on side-aware cTrader ticks."""

    triggers = candidate_triggers(frame, spec)
    tick_ns = ticks.index.asi8
    first_tick = ticks.index.min()
    last_tick = ticks.index.max()
    signal_positions = np.flatnonzero(triggers.ne(0.0).to_numpy())
    rows: list[dict[str, Any]] = []
    last_exit = pd.Timestamp.min
    excluded_outside_coverage = 0
    excluded_overlap = 0
    unfilled = 0
    for signal_position in signal_positions:
        signal_timestamp = pd.Timestamp(frame.index[signal_position])
        decision_timestamp = signal_timestamp + pd.Timedelta(minutes=30)
        if decision_timestamp < first_tick or decision_timestamp >= last_tick:
            excluded_outside_coverage += 1
            continue
        if decision_timestamp <= last_exit:
            excluded_overlap += 1
            continue
        delayed_entry = decision_timestamp + pd.Timedelta(seconds=stress.delay_seconds)
        entry_idx, entry_wait = _tick_index_at_or_after(
            tick_ns,
            delayed_entry,
            maximum_wait_seconds=stress.maximum_quote_wait_seconds,
        )
        deadline = delayed_entry + pd.Timedelta(minutes=30 * spec.max_holding_bars)
        if entry_idx is None or deadline > last_tick:
            unfilled += 1
            continue
        timeout_idx, timeout_wait = _tick_index_at_or_after(
            tick_ns,
            deadline,
            maximum_wait_seconds=stress.maximum_quote_wait_seconds,
        )
        if timeout_idx is None or timeout_idx <= entry_idx:
            unfilled += 1
            continue
        side = int(triggers.iloc[signal_position])
        risk_fraction = float(frame["causal_range_energy"].iloc[signal_position])
        entry_tick = ticks.iloc[entry_idx]
        entry_mid = float(entry_tick["mid"])
        entry_half_spread = float(entry_tick["spread"]) / 2.0
        slippage = stress.slippage_bps_per_side / 10_000.0
        entry_price = entry_mid + side * stress.spread_multiplier * entry_half_spread
        entry_price *= 1.0 + side * slippage
        target_price = entry_price * (1.0 + side * spec.target_r * risk_fraction)
        stop_price = entry_price * (1.0 - side * spec.stop_r * risk_fraction)

        path = ticks.iloc[entry_idx : timeout_idx + 1]
        exit_mid_path = path["mid"].to_numpy(dtype=float)
        half_spread_path = path["spread"].to_numpy(dtype=float) / 2.0
        executable_exit = exit_mid_path - side * stress.spread_multiplier * half_spread_path
        executable_exit *= 1.0 - side * slippage
        if side > 0:
            target_hits = np.flatnonzero(executable_exit >= target_price)
            stop_hits = np.flatnonzero(executable_exit <= stop_price)
        else:
            target_hits = np.flatnonzero(executable_exit <= target_price)
            stop_hits = np.flatnonzero(executable_exit >= stop_price)
        target_offset = int(target_hits[0]) if len(target_hits) else None
        stop_offset = int(stop_hits[0]) if len(stop_hits) else None
        if stop_offset is not None and (target_offset is None or stop_offset <= target_offset):
            exit_offset = stop_offset
            outcome = "stop_first"
        elif target_offset is not None:
            exit_offset = target_offset
            outcome = "target_first"
        else:
            exit_offset = int(timeout_idx - entry_idx)
            outcome = "timeout"
        exit_idx = int(entry_idx + exit_offset)
        exit_tick = ticks.iloc[exit_idx]
        exit_price = float(executable_exit[exit_offset])
        reference_mid_return = side * (float(exit_tick["mid"]) / entry_mid - 1.0)
        gross_return = side * (exit_price / entry_price - 1.0)
        commission_return = 2.0 * stress.commission_bps_per_side / 10_000.0
        net_return = gross_return - commission_return
        exit_timestamp = pd.Timestamp(ticks.index[exit_idx])
        rows.append(
            {
                "scenario_id": stress.scenario_id,
                "candidate_id": spec.candidate_id,
                "signal_timestamp": signal_timestamp,
                "entry_decision_timestamp": decision_timestamp,
                "entry_timestamp": ticks.index[entry_idx],
                "exit_timestamp": exit_timestamp,
                "side": "long" if side > 0 else "short",
                "side_numeric": side,
                "signal_score": float(frame["casc_score"].iloc[signal_position]),
                "risk_fraction": risk_fraction,
                "entry_mid": entry_mid,
                "entry_spread_bps": float(entry_tick["spread_bps"]),
                "entry_price": entry_price,
                "target_price": target_price,
                "stop_price": stop_price,
                "exit_mid": float(exit_tick["mid"]),
                "exit_spread_bps": float(exit_tick["spread_bps"]),
                "exit_price": exit_price,
                "outcome": outcome,
                "reference_mid_return": reference_mid_return,
                "gross_return": gross_return,
                "commission_return": commission_return,
                "net_return": net_return,
                "execution_cost_return": reference_mid_return - net_return,
                "entry_quote_wait_seconds": float(entry_wait or 0.0),
                "timeout_quote_wait_seconds": float(timeout_wait or 0.0),
                "holding_hours": float((exit_timestamp - ticks.index[entry_idx]).total_seconds() / 3_600.0),
            }
        )
        last_exit = exit_timestamp
    ledger = pd.DataFrame(rows)
    diagnostics = {
        "scenario_id": stress.scenario_id,
        "stress": asdict(stress),
        "signal_pulses": int(triggers.ne(0.0).sum()),
        "excluded_outside_tick_coverage": int(excluded_outside_coverage),
        "excluded_due_to_open_position": int(excluded_overlap),
        "unfilled_or_incomplete": int(unfilled),
        "executed_closed_trades": int(len(ledger)),
        "tick_coverage_start": first_tick.isoformat(),
        "tick_coverage_end": last_tick.isoformat(),
    }
    return ledger, diagnostics


def _tick_index_at_or_after(
    tick_index_ns: np.ndarray,
    desired: pd.Timestamp,
    *,
    maximum_wait_seconds: int,
) -> tuple[int | None, float | None]:
    position = int(np.searchsorted(tick_index_ns, int(pd.Timestamp(desired).value), side="left"))
    if position >= len(tick_index_ns):
        return None, None
    wait = float((int(tick_index_ns[position]) - int(pd.Timestamp(desired).value)) / 1e9)
    if wait > maximum_wait_seconds:
        return None, wait
    return position, wait


def run_suite(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    run_dir = _resolve_output_dir(output_dir)
    bars_export = load_ctrader_bar_export(
        CTRADER_ROOT / "bars_M30.csv",
        timeframe="M30",
        source_timezone="UTC",
        timestamp_convention="bar_open",
        drop_incomplete_tail=True,
    )
    tick_export = load_ctrader_tick_export(
        CTRADER_ROOT / "historical_ticks.csv",
        source_timezone="UTC",
    )
    bars = add_ethusd_custom_alpha_features(bars_export.frame)
    median_spread_bps = float(tick_export.frame["spread_bps"].median())
    round_trip_cost_bps = median_spread_bps + 2.0 * BASE_COMMISSION_BPS_PER_SIDE

    selected, candidate_table, selection_status = select_candidate(
        bars.loc[bars.index <= VALIDATION_END],
        round_trip_cost_bps=round_trip_cost_bps,
    )
    candidate_table.to_csv(run_dir / "candidate_search_development_validation.csv", index=False)
    _write_json(
        run_dir / "selected_candidate.json",
        {
            "spec": asdict(selected) if selected is not None else None,
            "candidate_id": selected.candidate_id if selected is not None else None,
            **selection_status,
        },
    )
    research_row = (
        candidate_table.loc[candidate_table["candidate_id"].eq(selected.candidate_id)].iloc[0]
        if selected is not None
        else candidate_table.iloc[0]
    )
    development_metrics = _metrics_from_search_row(research_row, prefix="development_")
    validation_metrics = _metrics_from_search_row(research_row, prefix="validation_")
    _write_json(
        run_dir / "development_validation_metrics.json",
        {
            "candidate_role": "selected" if selected is not None else "diagnostic_leader_only",
            "development": development_metrics,
            "validation": validation_metrics,
        },
    )
    if selected is None:
        locked_metrics = {
            "status": "not_evaluated",
            "reason": "No candidate passed development and validation; locked access denied.",
        }
        base_exact_metrics = {
            "status": "not_evaluated",
            "reason": "No candidate passed development and validation; exact tick access denied.",
        }
        stress_table = pd.DataFrame()
        stress_table.to_csv(run_dir / "exact_tick_stress_metrics.csv", index=False)
        _write_json(run_dir / "locked_bar_metrics.json", locked_metrics)
        _write_json(run_dir / "exact_tick_diagnostics.json", base_exact_metrics)
        positive_stress_count = 0
        locked_gate = {"evaluated": False, "passed": False}
        exact_gate = {"evaluated": False, "passed": False}
        verdict = (
            "NO-GO AT SELECTION GATE: no custom-indicator candidate was positive in both "
            "development and validation, so locked bars and exact ticks were not evaluated."
        )
    else:
        locked_ledger = bar_barrier_ledger(
            bars,
            selected,
            start=LOCKED_START,
            end=bars.index.max(),
            round_trip_cost_bps=round_trip_cost_bps,
        )
        locked_ledger.to_csv(run_dir / "locked_bar_trade_ledger.csv", index=False)
        locked_metrics = trade_metrics(
            locked_ledger,
            evidence_scope="single-use locked cTrader M30 OHLC first-passage approximation",
        )
        _write_json(run_dir / "locked_bar_metrics.json", locked_metrics)

        exact_dir = run_dir / "exact_tick_ledgers"
        exact_dir.mkdir(parents=True, exist_ok=True)
        stress_rows: list[dict[str, Any]] = []
        exact_diagnostics: dict[str, Any] = {}
        base_exact_metrics: dict[str, Any] = {}
        for stress_spec in STRESS_GRID:
            ledger, diagnostics = exact_tick_barrier_ledger(
                bars,
                tick_export.frame,
                selected,
                stress=stress_spec,
            )
            metrics = trade_metrics(
                ledger,
                evidence_scope="locked exact cTrader side-aware bid/ask first-passage replay",
            )
            ledger.to_csv(exact_dir / f"{stress_spec.scenario_id}.csv", index=False)
            stress_rows.append(
                {"scenario_id": stress_spec.scenario_id, **asdict(stress_spec), **metrics}
            )
            exact_diagnostics[stress_spec.scenario_id] = diagnostics
            if (
                stress_spec.delay_seconds == 0
                and stress_spec.spread_multiplier == 1.0
                and stress_spec.slippage_bps_per_side == 0.0
            ):
                base_exact_metrics = metrics
        stress_table = pd.DataFrame(stress_rows)
        stress_table.to_csv(run_dir / "exact_tick_stress_metrics.csv", index=False)
        _write_json(run_dir / "exact_tick_diagnostics.json", exact_diagnostics)
        positive_stress_count = int((stress_table["cumulative_return"] > 0.0).sum())
        locked_gate = {
            "evaluated": True,
            "minimum_trades": int(locked_metrics.get("trade_count", 0)) >= LOCKED_MIN_TRADES,
            "win_rate_at_least_70pct": float(locked_metrics.get("win_rate", 0.0)) >= LOCKED_WIN_RATE_GATE,
            "positive_cumulative_return": float(locked_metrics.get("cumulative_return", 0.0)) > 0.0,
            "profit_factor_at_least_1_20": float(locked_metrics.get("trade_profit_factor", 0.0)) >= PROFIT_FACTOR_GATE,
            "conventional_sharpe_at_least_1": float(locked_metrics.get("conventional_sharpe", 0.0)) >= SHARPE_GATE,
            "both_sides_present": int(locked_metrics.get("long_trade_count", 0)) > 0 and int(locked_metrics.get("short_trade_count", 0)) > 0,
        }
        exact_gate = {
            "evaluated": True,
            "minimum_trades": int(base_exact_metrics.get("trade_count", 0)) >= EXACT_MIN_TRADES,
            "win_rate_at_least_70pct": float(base_exact_metrics.get("win_rate", 0.0)) >= LOCKED_WIN_RATE_GATE,
            "positive_cumulative_return": float(base_exact_metrics.get("cumulative_return", 0.0)) > 0.0,
            "profit_factor_at_least_1_20": float(base_exact_metrics.get("trade_profit_factor", 0.0)) >= PROFIT_FACTOR_GATE,
            "all_stress_scenarios_positive": positive_stress_count == len(stress_table),
        }
        locked_passed = all(value for key, value in locked_gate.items() if key != "evaluated")
        exact_passed = all(value for key, value in exact_gate.items() if key != "evaluated")
        locked_gate["passed"] = locked_passed
        exact_gate["passed"] = exact_passed
        if locked_passed and exact_passed:
            verdict = (
                "RESEARCH-CANDIDATE: historical locked and exact-tick gates pass, but real "
                "alpha still requires prospective confirmation with the strategy frozen."
            )
        elif locked_passed:
            verdict = (
                "NO-GO FOR REAL-ALPHA CLAIM: locked bar gates pass, but exact cTrader "
                "evidence is insufficient or fails execution gates."
            )
        else:
            verdict = (
                "NO-GO: the selected custom-indicator strategy does not satisfy the "
                "predeclared locked 70% win-rate plus expectancy/robustness gate."
            )

    summary = {
        "suite": "ethusd_custom_indicator_alpha_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir.relative_to(PROJECT_ROOT)),
        "research_verdict": verdict,
        "provider": "cTrader CSV export",
        "timezone_contract": (
            "cTrader export timestamps assumed UTC bar-open for this run; exporter timezone "
            "must be confirmed from terminal settings"
        ),
        "split_contract": {
            "development_end": DEVELOPMENT_END.isoformat(),
            "validation_start": VALIDATION_START.isoformat(),
            "validation_end": VALIDATION_END.isoformat(),
            "locked_start": LOCKED_START.isoformat(),
            "locked_end": bars.index.max().isoformat(),
            "selection_reads_locked_rows": False,
        },
        "candidate_search": selection_status,
        "selected_candidate": (
            {"candidate_id": selected.candidate_id, **asdict(selected)}
            if selected is not None
            else None
        ),
        "development": development_metrics,
        "validation": validation_metrics,
        "locked_bar": locked_metrics,
        "exact_tick_base": base_exact_metrics,
        "exact_tick_stress": {
            "scenario_count": int(len(stress_table)),
            "positive_scenario_count": positive_stress_count,
            "median_cumulative_return": (
                float(stress_table["cumulative_return"].median())
                if not stress_table.empty
                else None
            ),
            "worst_cumulative_return": (
                float(stress_table["cumulative_return"].min())
                if not stress_table.empty
                else None
            ),
        },
        "gates": {"locked_bar": locked_gate, "exact_tick": exact_gate},
        "cost_contract": {
            "bar_round_trip_cost_bps": round_trip_cost_bps,
            "median_observed_tick_spread_bps": median_spread_bps,
            "commission_bps_per_side": BASE_COMMISSION_BPS_PER_SIDE,
            "exact_stress_scenarios": int(len(STRESS_GRID)),
        },
        "evidence_status": {
            "development": "selection",
            "validation": "selection",
            "locked_bar": (
                "single-use locked historical approximation"
                if selected is not None
                else "not evaluated because selection gate failed"
            ),
            "exact_tick": (
                "single-use locked exact replay within limited tick coverage"
                if selected is not None
                else "not evaluated because selection gate failed"
            ),
            "prospective": "not collected",
        },
    }
    _write_json(run_dir / "summary.json", summary)
    _write_json(
        run_dir / "provenance.json",
        {
            "created_at_utc": summary["created_at_utc"],
            "git": collect_git_metadata(),
            "data_files": {
                name: {
                    "path": str((CTRADER_ROOT / name).relative_to(PROJECT_ROOT)),
                    "sha256": file_sha256(CTRADER_ROOT / name),
                }
                for name in ("bars_M30.csv", "historical_ticks.csv")
            },
            "candidate_grid": [asdict(spec) for spec in CANDIDATE_GRID],
            "selection_policy": (
                "Candidate selection uses development and validation only; locked bars and "
                "exact ticks are evaluated once only when an eligible candidate exists"
            ),
        },
    )
    (run_dir / "report.md").write_text(_report_markdown(summary), encoding="utf-8")
    return summary


def _metrics_from_search_row(row: pd.Series, *, prefix: str) -> dict[str, Any]:
    return {
        key[len(prefix) :]: _jsonable(value)
        for key, value in row.items()
        if key.startswith(prefix)
    }


def _report_markdown(summary: Mapping[str, Any]) -> str:
    selected = dict(summary.get("selected_candidate", {}) or {})
    development = dict(summary.get("development", {}) or {})
    validation = dict(summary.get("validation", {}) or {})
    locked = dict(summary.get("locked_bar", {}) or {})
    exact = dict(summary.get("exact_tick_base", {}) or {})
    stress = dict(summary.get("exact_tick_stress", {}) or {})
    gates = dict(summary.get("gates", {}) or {})
    stress_median = stress.get("median_cumulative_return")
    stress_worst = stress.get("worst_cumulative_return")
    stress_median_text = (
        f"{100.0 * float(stress_median):.3f}%" if stress_median is not None else "not evaluated"
    )
    stress_worst_text = (
        f"{100.0 * float(stress_worst):.3f}%" if stress_worst is not None else "not evaluated"
    )
    if selected:
        selection_text = (
            "Selection used development and validation only; after the candidate passed those "
            "gates, the locked period and cTrader tick replay were evaluated once."
        )
        selected_rule = f"""## Selected frozen rule

- Candidate: `{selected.get('candidate_id')}`
- CASC threshold: `{selected.get('score_threshold')}`; LAF threshold: `{selected.get('flow_threshold')}`
- Prior compression maximum: `{selected.get('compression_max')}`; release minimum: `{selected.get('release_min')}`
- Target/stop: `{selected.get('target_r')}R / {selected.get('stop_r')}R`; maximum holding: `{selected.get('max_holding_bars')}` M30 bars
- Entry occurs at the next M30 open after a completed signal bar. Same-bar target/stop ambiguity is resolved conservatively as stop-first.
"""
        locked_row = (
            f"| Locked M30 | {locked.get('trade_count')} | "
            f"{100.0 * float(locked.get('win_rate', 0.0)):.2f}% | "
            f"{100.0 * float(locked.get('cumulative_return', 0.0)):.2f}% | "
            f"{float(locked.get('trade_profit_factor', 0.0)):.3f} | "
            f"{float(locked.get('conventional_sharpe', 0.0)):.3f} | "
            "single-use locked approximation |"
        )
        exact_row = (
            f"| Exact cTrader ticks | {exact.get('trade_count')} | "
            f"{100.0 * float(exact.get('win_rate', 0.0)):.2f}% | "
            f"{100.0 * float(exact.get('cumulative_return', 0.0)):.2f}% | "
            f"{float(exact.get('trade_profit_factor', 0.0)):.3f} | "
            f"{float(exact.get('conventional_sharpe', 0.0)):.3f} | limited exact overlap |"
        )
        next_step = (
            "If and only if the locked and exact gates pass, freeze the candidate id, code "
            "hash, parameters, and source hashes, then collect append-only prospective cTrader "
            "bars/ticks. No threshold or exit changes are allowed during that confirmation period."
        )
    else:
        selection_text = (
            "Selection used development and validation only. No candidate passed those gates, "
            "so the canonical run did not read the locked period or execute cTrader tick replay."
        )
        selected_rule = """## Selection outcome

- Selected candidate: none.
- Diagnostic leader: development/validation summary only; it is not a deployable rule.
- Locked-bar access: denied by the selection gate.
- Exact-tick access: denied by the selection gate.
- Entry semantics tested by the suite remain next-M30-open with conservative stop-first handling for same-bar barrier ambiguity.
"""
        locked_row = "| Locked M30 | — | — | — | — | — | not evaluated: selection gate failed |"
        exact_row = "| Exact cTrader ticks | — | — | — | — | — | not evaluated: selection gate failed |"
        next_step = (
            "Reject this continuation-rule family. Do not tune it against the now-exposed "
            "diagnostic locked result from the superseded v1 run. A new hypothesis must be "
            "predeclared and confirmed on newly accumulated append-only prospective cTrader data."
        )
    return f"""# ETHUSD custom-indicator alpha research

## Technical summary

**{summary.get('research_verdict')}**

The strategy uses four custom causal indicator families—Liquidity Acceptance Flow, Path Consensus Pressure, Compression-Release Energy, and Liquidity Absorption Divergence—combined into the CASC score. It uses no RSI, MACD, ATR, Bollinger, stochastic, or moving-average crossover signal. {selection_text}

{selected_rule}

## Evidence hierarchy

| Layer | Trades | Win rate | Net return | Profit factor | Conventional Sharpe | Status |
|---|---:|---:|---:|---:|---:|---|
| Development | {development.get('trade_count')} | {100.0 * float(development.get('win_rate', 0.0)):.2f}% | {100.0 * float(development.get('cumulative_return', 0.0)):.2f}% | {float(development.get('trade_profit_factor', 0.0)):.3f} | {float(development.get('conventional_sharpe', 0.0)):.3f} | selection |
| Validation | {validation.get('trade_count')} | {100.0 * float(validation.get('win_rate', 0.0)):.2f}% | {100.0 * float(validation.get('cumulative_return', 0.0)):.2f}% | {float(validation.get('trade_profit_factor', 0.0)):.3f} | {float(validation.get('conventional_sharpe', 0.0)):.3f} | selection |
{locked_row}
{exact_row}

## Predeclared 70% and real-alpha gates

- Locked-bar gates: `{gates.get('locked_bar')}`
- Exact-tick gates: `{gates.get('exact_tick')}`
- Exact stress: `{stress.get('positive_scenario_count')}/{stress.get('scenario_count')}` positive; median return `{stress_median_text}`; worst `{stress_worst_text}`.

A 70% win rate is accepted only with positive net return, profit factor at least 1.20, conventional Sharpe at least 1.0, enough trades, both sides represented, and execution-stress survival. Historical success cannot establish real alpha without a frozen prospective period.

## Limitations

- Bar selection uses cTrader OHLC as an approximate execution surface; exact bid/ask replay is authoritative only inside the tick file.
- The cTrader tick export covers a short interval and appears capped at 2,000,000 rows.
- Timestamps are assumed UTC; the cTrader exporter timezone still requires terminal-level confirmation.
- The 96-candidate search creates selection risk even though it never reads the locked period.
- Swap, rejected orders, market impact, and account-level FTMO constraints are not included.

## Next step

{next_step}
"""


def _resolve_output_dir(path: str | Path | None) -> Path:
    if path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        candidate = PROJECT_ROOT / "logs/experiments" / f"ethusd_custom_indicator_alpha_{stamp}"
    else:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
    candidate = enforce_safe_absolute_path(candidate.resolve())
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the causal ETHUSD custom-indicator alpha research suite."
    )
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    print(json.dumps(_jsonable(run_suite(output_dir=args.output_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "CANDIDATE_GRID",
    "CandidateSpec",
    "bar_barrier_ledger",
    "candidate_triggers",
    "exact_tick_barrier_ledger",
    "run_suite",
    "select_candidate",
    "trade_metrics",
]
