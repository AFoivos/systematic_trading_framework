from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
import yaml

from src.backtesting.holding import apply_min_holding_bars_to_positions
from src.evaluation.metrics import compute_backtest_metrics, equity_curve_from_returns, profit_factor
from src.experiments.orchestration.feature_stage import apply_feature_steps, apply_signal_step
from src.models.artifacts import load_model_bundle, predict_with_model_bundle
from src.models.ethusd_meta_label import chronological_meta_label_evaluation
from src.src_data.ctrader_export import (
    CTraderExport,
    load_ctrader_bar_export,
    load_ctrader_tick_export,
)
from src.utils.paths import PROJECT_ROOT, enforce_safe_absolute_path
from src.utils.run_metadata import collect_git_metadata, file_sha256


MODEL07_ROOT = PROJECT_ROOT / "config/experiments/foundation_alpha/best_runs" / (
    "model07_vwap32_rov64_rz256_20260801_200744_865898_f136efc6"
)
MODEL07_CONFIG = MODEL07_ROOT / "config_used.yaml"
MODEL07_BUNDLE = MODEL07_ROOT / "artifacts/models/model_07_vwap_plus_return_over_vol48_plus_robust_z.pkl"
DUKASCOPY_M30 = PROJECT_ROOT / "data/raw/dukascopy_30m_clean/ethusd_30m.csv"
BROKER_ROOT = PROJECT_ROOT / "data/ETHUSD"


@dataclass(frozen=True)
class TickStressSpec:
    delay_seconds: int
    spread_multiplier: float
    slippage_bps_per_side: float
    commission_bps_per_side: float = 0.5
    maximum_quote_wait_seconds: int = 120

    @property
    def scenario_id(self) -> str:
        return (
            f"delay_{self.delay_seconds}s__spread_{self.spread_multiplier:g}x__"
            f"slip_{self.slippage_bps_per_side:g}bps"
        )


BASE_STRESS = TickStressSpec(delay_seconds=0, spread_multiplier=1.0, slippage_bps_per_side=0.0)
STRESS_GRID = tuple(
    TickStressSpec(delay_seconds=delay, spread_multiplier=spread, slippage_bps_per_side=slippage)
    for delay in (0, 60, 120, 300)
    for spread in (1.0, 2.0)
    for slippage in (0.0, 1.0)
)


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
    path.write_text(json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True), encoding="utf-8")


def _resolve_output_dir(path: str | Path | None) -> Path:
    if path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        candidate = PROJECT_ROOT / "logs/experiments" / f"ethusd_broker_alpha_suite_{stamp}"
    else:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
    candidate = enforce_safe_absolute_path(candidate.resolve())
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _load_model07_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    if not MODEL07_CONFIG.is_file() or not MODEL07_BUNDLE.is_file():
        raise FileNotFoundError("Frozen Model-07 config or model bundle is missing.")
    config = yaml.safe_load(MODEL07_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Frozen Model-07 config must contain a mapping.")
    bundle = load_model_bundle(MODEL07_BUNDLE)
    return config, bundle


def _load_dukascopy_m30() -> pd.DataFrame:
    frame = pd.read_csv(DUKASCOPY_M30)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Dukascopy frame is missing columns: {missing}")
    index = pd.DatetimeIndex(pd.to_datetime(frame.pop("timestamp"), errors="raise", utc=True))
    frame.index = index.tz_convert("UTC").tz_localize(None)
    frame.index.name = "timestamp"
    frame = frame.sort_index()
    if frame.index.has_duplicates:
        raise ValueError("Dukascopy M30 frame has duplicate timestamps.")
    return frame


def score_frozen_model07(
    frame: pd.DataFrame,
    *,
    config: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> pd.DataFrame:
    """Apply the frozen feature, model, signal, and holding contracts."""

    featured = apply_feature_steps(frame.copy(), list(config.get("features", []) or []), asset="ETHUSD")
    scored = predict_with_model_bundle(featured, bundle, asset="ETHUSD")
    scored = apply_signal_step(scored, dict(config.get("signals", {}) or {}), asset="ETHUSD")
    signal_col = str(dict(config.get("backtest", {}) or {}).get("signal_col") or "signal_structured_tail")
    if signal_col not in scored.columns:
        raise KeyError(f"Frozen signal column {signal_col!r} was not produced.")
    min_holding = int(dict(config.get("backtest", {}) or {}).get("min_holding_bars", 0) or 0)
    scored["position"] = apply_min_holding_bars_to_positions(
        scored[signal_col],
        min_holding_bars=min_holding,
    )
    return scored


def _population_stability_index(reference: pd.Series, candidate: pd.Series, bins: int = 10) -> float:
    ref = pd.to_numeric(reference, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    cur = pd.to_numeric(candidate, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(ref) < bins * 2 or len(cur) < bins * 2:
        return float("nan")
    edges = np.unique(ref.quantile(np.linspace(0.0, 1.0, bins + 1)).to_numpy(dtype=float))
    if len(edges) < 3:
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf
    ref_counts = pd.cut(ref, bins=edges, include_lowest=True).value_counts(sort=False).to_numpy(dtype=float)
    cur_counts = pd.cut(cur, bins=edges, include_lowest=True).value_counts(sort=False).to_numpy(dtype=float)
    ref_pct = np.clip(ref_counts / max(ref_counts.sum(), 1.0), 1e-6, None)
    cur_pct = np.clip(cur_counts / max(cur_counts.sum(), 1.0), 1e-6, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def transfer_audit(
    dukascopy: pd.DataFrame,
    broker: pd.DataFrame,
    *,
    feature_columns: Iterable[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    common = dukascopy.index.intersection(broker.index)
    rows: list[dict[str, Any]] = []
    for feature in feature_columns:
        if feature not in dukascopy.columns or feature not in broker.columns:
            continue
        left = pd.to_numeric(dukascopy.loc[common, feature], errors="coerce")
        right = pd.to_numeric(broker.loc[common, feature], errors="coerce")
        valid = left.notna() & right.notna() & np.isfinite(left) & np.isfinite(right)
        left = left.loc[valid]
        right = right.loc[valid]
        iqr = float(left.quantile(0.75) - left.quantile(0.25)) if not left.empty else float("nan")
        rows.append(
            {
                "feature": feature,
                "common_rows": int(len(left)),
                "pearson_correlation": float(left.corr(right)) if len(left) >= 2 else float("nan"),
                "median_reference": float(left.median()) if not left.empty else float("nan"),
                "median_broker": float(right.median()) if not right.empty else float("nan"),
                "median_shift_reference_iqr": (
                    float((right.median() - left.median()) / iqr)
                    if np.isfinite(iqr) and iqr > 0.0
                    else float("nan")
                ),
                "psi": _population_stability_index(left, right),
            }
        )
    feature_table = pd.DataFrame(rows).sort_values("psi", ascending=False, na_position="last")

    pred_left = pd.to_numeric(dukascopy.loc[common, "pred_ret"], errors="coerce")
    pred_right = pd.to_numeric(broker.loc[common, "pred_ret"], errors="coerce")
    valid_pred = pred_left.notna() & pred_right.notna()
    pred_left = pred_left.loc[valid_pred]
    pred_right = pred_right.loc[valid_pred]
    pos_left = dukascopy.loc[common, "position"].astype(float)
    pos_right = broker.loc[common, "position"].astype(float)
    active_union = pos_left.ne(0.0) | pos_right.ne(0.0)
    active_intersection = pos_left.eq(pos_right) & pos_left.ne(0.0)
    summary = {
        "evidence_scope": "descriptive cross-feed parity; not OOS performance",
        "common_timestamps": int(len(common)),
        "prediction_common_rows": int(len(pred_left)),
        "prediction_pearson_correlation": float(pred_left.corr(pred_right)) if len(pred_left) >= 2 else None,
        "prediction_sign_agreement": float(np.sign(pred_left).eq(np.sign(pred_right)).mean()) if len(pred_left) else None,
        "position_exact_agreement": float(pos_left.eq(pos_right).mean()) if len(common) else None,
        "active_signal_jaccard": (
            float(active_intersection.sum() / active_union.sum()) if int(active_union.sum()) else None
        ),
        "dukascopy_active_bars": int(pos_left.ne(0.0).sum()),
        "broker_active_bars": int(pos_right.ne(0.0).sum()),
        "dukascopy_only_timestamps": int(len(dukascopy.index.difference(broker.index))),
        "broker_only_timestamps": int(len(broker.index.difference(dukascopy.index))),
    }
    return feature_table, summary


def approximate_oot_backtest(
    broker_scored: pd.DataFrame,
    *,
    training_end: pd.Timestamp,
    median_tick_spread_bps: float,
    commission_bps_per_side: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = broker_scored.loc[broker_scored.index > training_end].copy()
    close_return = frame["close"].pct_change().fillna(0.0)
    position = frame["position"].astype(float).fillna(0.0)
    applied_position = position.shift(1).fillna(0.0)
    gross_return = applied_position * close_return
    turnover = position.diff().abs().fillna(position.abs())
    half_spread_cost = float(median_tick_spread_bps) / 2.0 / 10_000.0
    commission_cost = float(commission_bps_per_side) / 10_000.0
    costs = turnover * (half_spread_cost + commission_cost)
    net_return = gross_return - costs
    output = pd.DataFrame(
        {
            "close": frame["close"],
            "pred_ret": frame["pred_ret"],
            "desired_position": position,
            "applied_position": applied_position,
            "gross_return": gross_return,
            "turnover": turnover,
            "estimated_cost": costs,
            "net_return": net_return,
        }
    )
    metrics = compute_backtest_metrics(
        net_returns=output["net_return"],
        gross_returns=output["gross_return"],
        turnover=output["turnover"],
        costs=output["estimated_cost"],
        periods_per_year=17_520,
        annualization_mode="calendar_daily",
    )
    metrics.update(
        {
            "evidence_scope": "frozen-model OOT, approximate close-to-close execution",
            "training_end": training_end.isoformat(),
            "evaluation_start": output.index.min().isoformat() if not output.empty else None,
            "evaluation_end": output.index.max().isoformat() if not output.empty else None,
            "bars": int(len(output)),
            "median_tick_spread_bps_assumption": float(median_tick_spread_bps),
            "commission_bps_per_side_assumption": float(commission_bps_per_side),
            "position_change_count": int(position.ne(position.shift(1)).sum()),
        }
    )
    return output, metrics


def _position_segments(scored: pd.DataFrame) -> pd.DataFrame:
    required = ["position", "pred_ret", "atr_over_price_48"]
    missing = [column for column in required if column not in scored.columns]
    if missing:
        raise KeyError(f"Scored frame is missing execution columns: {missing}")
    events = pd.DataFrame(
        {
            "signal_timestamp": scored.index,
            "decision_timestamp": scored.index + pd.Timedelta(minutes=30),
            "position": scored["position"].fillna(0.0).astype(float).to_numpy(),
            "pred_ret": pd.to_numeric(scored["pred_ret"], errors="coerce").to_numpy(),
            "atr_over_price_48": pd.to_numeric(scored["atr_over_price_48"], errors="coerce").to_numpy(),
        }
    )
    changed = events["position"].ne(events["position"].shift(1).fillna(0.0))
    events = events.loc[changed].reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for idx in range(len(events) - 1):
        current = events.iloc[idx]
        if float(current["position"]) == 0.0:
            continue
        following = events.iloc[idx + 1]
        rows.append(
            {
                "signal_timestamp": current["signal_timestamp"],
                "entry_decision_timestamp": current["decision_timestamp"],
                "exit_decision_timestamp": following["decision_timestamp"],
                "side": int(np.sign(float(current["position"]))),
                "pred_ret": float(current["pred_ret"]),
                "atr_over_price_48": float(current["atr_over_price_48"]),
            }
        )
    return pd.DataFrame(rows)


def _fill_index(
    tick_index_ns: np.ndarray,
    desired: pd.Timestamp,
    *,
    maximum_quote_wait_seconds: int,
) -> tuple[int | None, float | None]:
    desired_ns = int(pd.Timestamp(desired).value)
    idx = int(np.searchsorted(tick_index_ns, desired_ns, side="left"))
    if idx >= len(tick_index_ns):
        return None, None
    wait_seconds = float((int(tick_index_ns[idx]) - desired_ns) / 1_000_000_000.0)
    if wait_seconds > maximum_quote_wait_seconds:
        return None, wait_seconds
    return idx, wait_seconds


def tick_execution_ledger(
    scored: pd.DataFrame,
    ticks: pd.DataFrame,
    *,
    stress: TickStressSpec,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Replay closed Model-07 position segments on side-aware broker ticks."""

    segments = _position_segments(scored)
    tick_ns = ticks.index.asi8
    first_tick = ticks.index.min()
    last_tick = ticks.index.max()
    rows: list[dict[str, Any]] = []
    excluded_before_coverage = 0
    excluded_after_coverage = 0
    unfilled_transitions = 0
    for _, segment in segments.iterrows():
        entry_decision = pd.Timestamp(segment["entry_decision_timestamp"])
        exit_decision = pd.Timestamp(segment["exit_decision_timestamp"])
        if entry_decision < first_tick:
            excluded_before_coverage += 1
            continue
        if exit_decision > last_tick:
            excluded_after_coverage += 1
            continue
        delayed_entry = entry_decision + pd.Timedelta(seconds=stress.delay_seconds)
        delayed_exit = exit_decision + pd.Timedelta(seconds=stress.delay_seconds)
        entry_idx, entry_wait = _fill_index(
            tick_ns,
            delayed_entry,
            maximum_quote_wait_seconds=stress.maximum_quote_wait_seconds,
        )
        exit_idx, exit_wait = _fill_index(
            tick_ns,
            delayed_exit,
            maximum_quote_wait_seconds=stress.maximum_quote_wait_seconds,
        )
        if entry_idx is None or exit_idx is None or exit_idx <= entry_idx:
            unfilled_transitions += 1
            continue

        side = int(segment["side"])
        entry_tick = ticks.iloc[entry_idx]
        exit_tick = ticks.iloc[exit_idx]
        entry_mid = float(entry_tick["mid"])
        exit_mid = float(exit_tick["mid"])
        entry_half_spread = float(entry_tick["spread"]) / 2.0
        exit_half_spread = float(exit_tick["spread"]) / 2.0
        entry_price = entry_mid + side * stress.spread_multiplier * entry_half_spread
        exit_price = exit_mid - side * stress.spread_multiplier * exit_half_spread
        slippage = stress.slippage_bps_per_side / 10_000.0
        entry_price *= 1.0 + side * slippage
        exit_price *= 1.0 - side * slippage
        gross_return = side * (exit_price / entry_price - 1.0)
        reference_mid_return = side * (exit_mid / entry_mid - 1.0)
        commission_return = 2.0 * stress.commission_bps_per_side / 10_000.0
        net_return = gross_return - commission_return
        rows.append(
            {
                "scenario_id": stress.scenario_id,
                "signal_timestamp": segment["signal_timestamp"],
                "entry_decision_timestamp": entry_decision,
                "exit_decision_timestamp": exit_decision,
                "entry_timestamp": ticks.index[entry_idx],
                "exit_timestamp": ticks.index[exit_idx],
                "side": "long" if side > 0 else "short",
                "side_numeric": side,
                "pred_ret": float(segment["pred_ret"]),
                "atr_over_price_48": float(segment["atr_over_price_48"]),
                "entry_bid": float(entry_tick["bid"]),
                "entry_ask": float(entry_tick["ask"]),
                "entry_mid": entry_mid,
                "entry_spread_bps": float(entry_tick["spread_bps"]),
                "exit_bid": float(exit_tick["bid"]),
                "exit_ask": float(exit_tick["ask"]),
                "exit_mid": exit_mid,
                "exit_spread_bps": float(exit_tick["spread_bps"]),
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "reference_mid_return": float(reference_mid_return),
                "gross_return": float(gross_return),
                "commission_return": float(commission_return),
                "net_return": float(net_return),
                "execution_cost_return": float(reference_mid_return - net_return),
                "entry_quote_wait_seconds": float(entry_wait or 0.0),
                "exit_quote_wait_seconds": float(exit_wait or 0.0),
                "holding_hours": float((ticks.index[exit_idx] - ticks.index[entry_idx]).total_seconds() / 3_600.0),
            }
        )

    ledger = pd.DataFrame(rows)
    diagnostics = {
        "scenario_id": stress.scenario_id,
        "stress": asdict(stress),
        "candidate_closed_segments": int(len(segments)),
        "excluded_started_before_tick_coverage": int(excluded_before_coverage),
        "excluded_ended_after_tick_coverage": int(excluded_after_coverage),
        "unfilled_transitions": int(unfilled_transitions),
        "executed_closed_trades": int(len(ledger)),
        "tick_coverage_start": first_tick.isoformat(),
        "tick_coverage_end": last_tick.isoformat(),
    }
    return ledger, diagnostics


def trade_ledger_metrics(ledger: pd.DataFrame) -> dict[str, Any]:
    if ledger.empty:
        return {
            "trade_count": 0,
            "cumulative_return": 0.0,
            "conventional_sharpe": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "trade_profit_factor": 0.0,
            "average_trade_return": 0.0,
        }
    returns = pd.Series(
        ledger["net_return"].to_numpy(dtype=float),
        index=pd.DatetimeIndex(ledger["exit_timestamp"]),
        name="net_return",
    ).sort_index()
    reference = pd.Series(
        ledger["reference_mid_return"].to_numpy(dtype=float),
        index=returns.index,
        name="reference_mid_return",
    )
    costs = reference - returns
    metrics = compute_backtest_metrics(
        net_returns=returns,
        gross_returns=reference,
        costs=costs,
        periods_per_year=365,
        annualization_mode="calendar_daily",
    )
    positive = ledger.loc[ledger["net_return"] > 0.0, "net_return"]
    positive_sum = float(positive.sum())
    metrics.update(
        {
            "trade_count": int(len(ledger)),
            "win_rate": float((ledger["net_return"] > 0.0).mean()),
            "trade_profit_factor": float(profit_factor(ledger["net_return"])),
            "average_trade_return": float(ledger["net_return"].mean()),
            "median_trade_return": float(ledger["net_return"].median()),
            "long_trade_count": int(ledger["side"].eq("long").sum()),
            "short_trade_count": int(ledger["side"].eq("short").sum()),
            "average_execution_cost_return": float(ledger["execution_cost_return"].mean()),
            "best_trade_positive_pnl_concentration": (
                float(positive.max() / positive_sum) if positive_sum > 0.0 else 0.0
            ),
            "evaluation_start": pd.Timestamp(ledger["entry_timestamp"].min()).isoformat(),
            "evaluation_end": pd.Timestamp(ledger["exit_timestamp"].max()).isoformat(),
            "evidence_scope": "frozen-model OOT exact side-aware bid/ask tick replay",
        }
    )
    return metrics


def _causal_m1_features(m1: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=m1.index)
    close = m1["close"].astype(float)
    one_minute_return = close.pct_change()
    out["m1_ret_1"] = one_minute_return
    out["m1_ret_5"] = close.pct_change(5)
    out["m1_realized_vol_15"] = one_minute_return.rolling(15, min_periods=15).std()
    path = close.diff().abs().rolling(15, min_periods=15).sum()
    out["m1_path_efficiency_15"] = (close - close.shift(15)).abs() / path.replace(0.0, np.nan)
    out["m1_range_over_close"] = (m1["high"].astype(float) - m1["low"].astype(float)) / close
    return out


def enrich_meta_label_samples(
    base_ledger: pd.DataFrame,
    *,
    m1: pd.DataFrame,
    ticks: pd.DataFrame,
) -> pd.DataFrame:
    if base_ledger.empty:
        return pd.DataFrame()
    features = _causal_m1_features(m1)
    decisions = pd.DatetimeIndex(base_ledger["entry_decision_timestamp"])
    locations = features.index.searchsorted(decisions, side="left") - 1
    valid = locations >= 0
    samples = base_ledger.loc[valid].copy().reset_index(drop=True)
    locations = locations[valid]
    sampled = features.iloc[locations].reset_index(drop=True)
    for column in sampled.columns:
        samples[column] = sampled[column]
    samples["side_m1_ret_1"] = samples["side_numeric"] * samples["m1_ret_1"]
    samples["side_m1_ret_5"] = samples["side_numeric"] * samples["m1_ret_5"]
    samples["abs_pred_ret"] = samples["pred_ret"].abs()
    samples["meta_label"] = (samples["net_return"] > 0.0).astype(int)
    samples["feature_timestamp"] = features.index[locations].to_numpy()

    tick_ns = ticks.index.asi8
    barrier_outcomes: list[str] = []
    barrier_labels: list[float] = []
    for _, row in samples.iterrows():
        entry_timestamp = pd.Timestamp(row["entry_timestamp"])
        entry_idx = int(np.searchsorted(tick_ns, entry_timestamp.value, side="left"))
        end_ns = int((entry_timestamp + pd.Timedelta(hours=12)).value)
        end_idx = int(np.searchsorted(tick_ns, end_ns, side="right"))
        if entry_idx >= len(ticks) or end_idx <= entry_idx:
            barrier_outcomes.append("unavailable")
            barrier_labels.append(float("nan"))
            continue
        side = int(row["side_numeric"])
        distance = float(row["atr_over_price_48"])
        entry_price = float(row["entry_price"])
        if not np.isfinite(distance) or distance <= 0.0:
            barrier_outcomes.append("unavailable")
            barrier_labels.append(float("nan"))
            continue
        exit_path = ticks["bid"].iloc[entry_idx:end_idx].to_numpy(dtype=float) if side > 0 else ticks["ask"].iloc[entry_idx:end_idx].to_numpy(dtype=float)
        if side > 0:
            target_hits = np.flatnonzero(exit_path >= entry_price * (1.0 + distance))
            stop_hits = np.flatnonzero(exit_path <= entry_price * (1.0 - distance))
        else:
            target_hits = np.flatnonzero(exit_path <= entry_price * (1.0 - distance))
            stop_hits = np.flatnonzero(exit_path >= entry_price * (1.0 + distance))
        first_target = int(target_hits[0]) if len(target_hits) else None
        first_stop = int(stop_hits[0]) if len(stop_hits) else None
        if first_target is None and first_stop is None:
            barrier_outcomes.append("timeout_12h")
            barrier_labels.append(float("nan"))
        elif first_stop is not None and (first_target is None or first_stop <= first_target):
            barrier_outcomes.append("stop_first")
            barrier_labels.append(0.0)
        else:
            barrier_outcomes.append("target_first")
            barrier_labels.append(1.0)
    samples["barrier_1atr_outcome_12h"] = barrier_outcomes
    samples["barrier_1atr_label_12h"] = barrier_labels
    samples.index = pd.DatetimeIndex(samples["entry_timestamp"], name="entry_timestamp_index")
    return samples


def evaluate_m1_gates(samples: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if samples.empty or len(samples) < 10:
        return pd.DataFrame(), {
            "status": "insufficient_samples",
            "reason": f"Need at least 10 exact trades for a chronological gate audit; observed {len(samples)}.",
        }
    split = max(5, int(np.floor(len(samples) * 0.60)))
    training = samples.iloc[:split]
    holdout = samples.iloc[split:]
    thresholds = {
        "spread_cap_bps": float(training["entry_spread_bps"].quantile(0.75)),
        "side_m1_ret_5_floor": float(training["side_m1_ret_5"].quantile(0.25)),
        "path_efficiency_floor": float(training["m1_path_efficiency_15"].quantile(0.25)),
    }
    gates = {
        "baseline": pd.Series(True, index=holdout.index),
        "spread_quality": holdout["entry_spread_bps"] <= thresholds["spread_cap_bps"],
        "no_adverse_impulse": holdout["side_m1_ret_5"] >= thresholds["side_m1_ret_5_floor"],
        "combined_predeclared": (
            (holdout["entry_spread_bps"] <= thresholds["spread_cap_bps"])
            & (holdout["side_m1_ret_5"] >= thresholds["side_m1_ret_5_floor"])
            & (holdout["m1_path_efficiency_15"] >= thresholds["path_efficiency_floor"])
        ),
    }
    rows: list[dict[str, Any]] = []
    for name, mask in gates.items():
        selected = holdout.loc[mask.fillna(False)]
        metrics = trade_ledger_metrics(selected)
        rows.append(
            {
                "gate": name,
                "training_rows_for_thresholds": int(len(training)),
                "holdout_rows": int(len(holdout)),
                "selected_holdout_trades": int(len(selected)),
                "selection_rate": float(len(selected) / len(holdout)) if len(holdout) else 0.0,
                "cumulative_return": float(metrics.get("cumulative_return", 0.0)),
                "average_trade_return": float(metrics.get("average_trade_return", 0.0)),
                "win_rate": float(metrics.get("win_rate", 0.0)),
                "trade_profit_factor": float(metrics.get("trade_profit_factor", 0.0)),
                "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
            }
        )
    return pd.DataFrame(rows), {
        "status": "evaluated",
        "evidence_scope": "chronological 60/40 descriptive holdout; not enough alone for deployment",
        "threshold_source": "first 60% of exact trades; feature-distribution quantiles only",
        "thresholds": thresholds,
        "training_start": training.index.min().isoformat(),
        "training_end": training.index.max().isoformat(),
        "holdout_start": holdout.index.min().isoformat(),
        "holdout_end": holdout.index.max().isoformat(),
    }


def data_quality_audit(
    exports: Mapping[str, CTraderExport], ticks: CTraderExport
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, export in exports.items():
        meta = export.metadata
        rows.append(
            {
                "dataset": label,
                "raw_rows": int(meta["raw_rows"]),
                "rows": int(meta["canonical_rows"]),
                "timestamp_start": meta["timestamp_start"],
                "timestamp_end": meta["timestamp_end"],
                "sha256": meta["file_sha256"],
                "tail_rows_dropped": int(meta.get("dropped_tail_rows", 0)),
            }
        )
    rows.append(
        {
            "dataset": "historical_ticks",
            "raw_rows": int(ticks.metadata["raw_rows"]),
            "rows": int(ticks.metadata["canonical_rows"]),
            "timestamp_start": ticks.metadata["timestamp_start"],
            "timestamp_end": ticks.metadata["timestamp_end"],
            "sha256": ticks.metadata["file_sha256"],
            "tail_rows_dropped": 0,
        }
    )
    m1 = exports["M1"].frame
    gaps = m1.index.to_series().diff().dropna()
    gap_events = gaps > pd.Timedelta(minutes=1)
    missing_slots = int(((gaps.loc[gap_events] / pd.Timedelta(minutes=1)).astype(int) - 1).sum())
    tick_frame = ticks.frame

    dom = pd.read_csv(BROKER_ROOT / "dom_snapshot.csv")
    bid_volume_cols = [column for column in dom.columns if column.startswith("bid") and column.endswith("_volume")]
    ask_volume_cols = [column for column in dom.columns if column.startswith("ask") and column.endswith("_volume")]
    bid_total = dom[bid_volume_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
    ask_total = dom[ask_volume_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
    imbalance = (bid_total - ask_total) / (bid_total + ask_total).replace(0.0, np.nan)
    timeframe_consistency: dict[str, Any] = {}
    aggregation_rules = {
        "M5": "5min",
        "M15": "15min",
        "M30": "30min",
        "H1": "1h",
    }
    for timeframe, frequency in aggregation_rules.items():
        aggregated = m1.resample(frequency, label="left", closed="left").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "tick_volume": "sum",
            }
        )
        exported = exports[timeframe].frame
        common = aggregated.index.intersection(exported.index)
        price_match = pd.Series(True, index=common)
        for column in ("open", "high", "low", "close"):
            price_match &= np.isclose(
                aggregated.loc[common, column].to_numpy(dtype=float),
                exported.loc[common, column].to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-8,
            )
        volume_match = np.isclose(
            aggregated.loc[common, "tick_volume"].to_numpy(dtype=float),
            exported.loc[common, "tick_volume"].to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-8,
        )
        mismatch_timestamps = common[~price_match.to_numpy()]
        timeframe_consistency[timeframe] = {
            "common_rows": int(len(common)),
            "exact_ohlc_rows": int(price_match.sum()),
            "ohlc_match_rate": float(price_match.mean()) if len(common) else None,
            "tick_volume_match_rate": float(volume_match.mean()) if len(common) else None,
            "ohlc_mismatch_count": int((~price_match).sum()),
            "first_ohlc_mismatch": mismatch_timestamps.min().isoformat() if len(mismatch_timestamps) else None,
            "last_ohlc_mismatch": mismatch_timestamps.max().isoformat() if len(mismatch_timestamps) else None,
        }
    summary = {
        "timezone_contract": (
            "cTrader export timestamps are explicitly assumed UTC for this run; "
            "canonical index is UTC-naive; exporter timezone remains to be confirmed"
        ),
        "bar_timestamp_convention": "bar_open",
        "tail_policy": "last row of every bar export dropped as potentially incomplete",
        "m1_gap_event_count": int(gap_events.sum()),
        "m1_missing_minute_slots": missing_slots,
        "m1_fill_policy": "none",
        "historical_tick_rows": int(len(tick_frame)),
        "historical_tick_export_cap_suspected": bool(len(tick_frame) == 2_000_000),
        "m1_export_cap_suspected": bool(int(exports["M1"].metadata["raw_rows"]) in {1_999_999, 2_000_000}),
        "tick_spread_usd_median": float(tick_frame["spread"].median()),
        "tick_spread_bps_median": float(tick_frame["spread_bps"].median()),
        "tick_spread_bps_p95": float(tick_frame["spread_bps"].quantile(0.95)),
        "dom_snapshot_rows": int(len(dom)),
        "dom_imbalance_unique_values": int(imbalance.dropna().nunique()),
        "dom_imbalance_standard_deviation": float(imbalance.std(ddof=0)),
        "dom_usable_for_alpha": bool(imbalance.dropna().nunique() > 1 and imbalance.std(ddof=0) > 0.0),
        "dom_exclusion_reason": "static symmetric 10/30/50 level volumes" if imbalance.dropna().nunique() <= 1 else None,
        "timeframe_consistency": timeframe_consistency,
    }
    return pd.DataFrame(rows), summary


def _report_markdown(summary: Mapping[str, Any]) -> str:
    exact = dict(summary.get("exact_tick_base", {}) or {})
    approximate = dict(summary.get("approximate_oot", {}) or {})
    transfer = dict(summary.get("prediction_transfer", {}) or {})
    meta = dict(summary.get("meta_label", {}) or {})
    gates = dict(summary.get("m1_gate", {}) or {})
    quality = dict(summary.get("data_quality", {}) or {})
    verdict = str(summary.get("research_verdict", "not assessed"))
    return f"""# ETHUSD cTrader broker-data alpha validation report

## Technical summary

This run applies the **unchanged frozen Model-07** feature/model/signal contract to the cTrader broker export, then evaluates it at three deliberately separate evidence levels. No threshold, model parameter, or stress setting was selected from the new return outcomes.

- Research verdict: **{verdict}**
- Frozen-model training-data end: `{summary.get('frozen_training_end')}`
- Exact tick coverage: `{exact.get('evaluation_start')}` to `{exact.get('evaluation_end')}`
- Exact closed trades: **{exact.get('trade_count', 0)}**
- Exact cumulative net return: **{100.0 * float(exact.get('cumulative_return', 0.0)):.3f}%**
- Exact conventional Sharpe: **{float(exact.get('conventional_sharpe', 0.0)):.3f}**
- Exact max drawdown: **{100.0 * float(exact.get('max_drawdown', 0.0)):.3f}%**

## What changed

1. Added a strict cTrader CSV adapter with an explicit UTC assumption for this run, bar-open timestamps, no interpolation, schema checks, file hashes, and deterministic incomplete-tail removal.
2. Replayed the frozen Model-07 on the broker M30 feed and measured cross-feed feature/prediction/signal transfer.
3. Added an approximate OOT close-to-close layer using the observed median tick spread.
4. Added canonical side-aware bid/ask tick fills with delay, spread, slippage, and commission stress.
5. Added causal pre-entry M1 features, a chronological gate audit, 12-hour first-passage barrier diagnostics, and a fail-closed meta-label model readiness gate.

## Key findings

- Prediction correlation on common timestamps: `{transfer.get('prediction_pearson_correlation')}`; exact position agreement: `{transfer.get('position_exact_agreement')}`. This is transfer evidence, not OOS return evidence.
- Approximate OOT cumulative return: `{100.0 * float(approximate.get('cumulative_return', 0.0)):.3f}%`; conventional Sharpe: `{float(approximate.get('conventional_sharpe', 0.0)):.3f}`.
- Base exact tick win rate: `{100.0 * float(exact.get('win_rate', 0.0)):.2f}%`; trade profit factor: `{float(exact.get('trade_profit_factor', 0.0)):.3f}`; average trade: `{100.0 * float(exact.get('average_trade_return', 0.0)):.4f}%`.
- Meta-label status: `{meta.get('status')}` — {meta.get('reason')}.
- M1 gate status: `{gates.get('status')}` — {gates.get('reason', gates.get('evidence_scope'))}.

## Scope, data, and definitions

- cTrader bars are treated as UTC bar-open timestamps for this run. The last row of each timeframe is excluded as potentially active.
- The cTrader M30 `tick_volume` is mapped to canonical `volume` only to reproduce Model-07 inference. It is not assumed equivalent to Dukascopy volume.
- Exact execution uses the first historical tick at or after decision time plus the scenario delay. Fills waiting more than 120 seconds for a quote are rejected.
- Long entries use ask and exits use bid; short entries use bid and exits use ask. Spread stress expands the observed half-spread around the contemporaneous midpoint.
- `conventional_sharpe` is arithmetic mean over sample volatility after UTC-daily compounding. The repository's legacy `sharpe` alias is not used for decisions.

## Methodology and validation

The frozen model was trained/refit only on the existing Dukascopy dataset ending `{summary.get('frozen_training_end')}`. Broker rows after that timestamp are treated as out-of-time for this frozen artifact. Model inference uses each completed M30 bar; a signal at bar-open timestamp `t` becomes executable at `t+30m`, never at the same bar's open.

The 16 execution scenarios form a fixed grid: delays 0/60/120/300 seconds, observed spread multipliers 1x/2x, and per-side slippage 0/1 bp. Commission is fixed at 0.5 bp per side. The base scenario is 0s/1x/0bp; robustness is judged from the whole grid, not its best row.

M1 features use only the last M1 bar whose open timestamp is strictly before the M30 decision timestamp. Gate thresholds come from feature-distribution quantiles in the first 60% of exact trades and are evaluated on the final 40%. The logistic meta-label model requires at least 60 trades and 20 examples per class, with all imputation/scaling fit inside expanding chronological folds.

## Data quality and limitations

- M1 gap events: `{quality.get('m1_gap_event_count')}`; missing minute slots: `{quality.get('m1_missing_minute_slots')}`. No gaps are filled.
- M1→M30 OHLC match rate: `{dict(quality.get('timeframe_consistency', {}) or {}).get('M30', {}).get('ohlc_match_rate')}`. H1 mismatches: `{dict(quality.get('timeframe_consistency', {}) or {}).get('H1', {}).get('ohlc_mismatch_count')}`; these require explicit session/DST handling rather than silent alignment.
- Historical ticks: `{quality.get('historical_tick_rows')}` rows. A 2,000,000-row export cap is suspected: `{quality.get('historical_tick_export_cap_suspected')}`.
- Median/p95 tick spread: `{quality.get('tick_spread_bps_median')}` / `{quality.get('tick_spread_bps_p95')}` bps.
- DOM usable for alpha: `{quality.get('dom_usable_for_alpha')}`; exclusion reason: `{quality.get('dom_exclusion_reason')}`.
- Exact tick evidence covers only trades with both entry and exit inside the tick file. It is not a prospective paper-trading result and does not prove live alpha.
- Swap/overnight financing, rejected orders, variable commission schedules, market impact, account-level constraints, and continuous FTMO equity enforcement are outside this ledger.

## Decision and next steps

`{verdict}`

The next promotion gate is prospective collection with append-only file fingerprints and no model/signal changes. A deployment claim requires stable exact-tick performance across more trades, delay/spread stress survival, side stability, and a meta-label sample large enough to pass the predeclared readiness gate.

## Further questions

- Does the broker feed continue beyond the apparent 2,000,000-row cap without overwriting early history?
- Are cTrader timestamps confirmed as UTC by the exporting terminal settings, rather than merely assumed from alignment?
- What are the exact commission, swap, and rejected-fill rules for the target account?
- Does the alpha remain after a genuinely prospective period with the frozen artifact hash unchanged?
"""


def run_suite(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    run_dir = _resolve_output_dir(output_dir)
    config, bundle = _load_model07_contract()

    exports = {
        timeframe: load_ctrader_bar_export(
            BROKER_ROOT / f"bars_{timeframe}.csv",
            timeframe=timeframe,
            source_timezone="UTC",
            timestamp_convention="bar_open",
            drop_incomplete_tail=True,
        )
        for timeframe in ("M1", "M5", "M15", "M30", "H1")
    }
    tick_export = load_ctrader_tick_export(
        BROKER_ROOT / "historical_ticks.csv", source_timezone="UTC"
    )
    inventory, quality = data_quality_audit(exports, tick_export)
    inventory.to_csv(run_dir / "data_inventory.csv", index=False)
    _write_json(run_dir / "data_quality.json", quality)

    dukascopy_raw = _load_dukascopy_m30()
    broker_m30 = exports["M30"].frame.copy()
    dukascopy_scored = score_frozen_model07(dukascopy_raw, config=config, bundle=bundle)
    broker_scored = score_frozen_model07(broker_m30, config=config, bundle=bundle)
    feature_columns = list(dict(bundle.get("model_meta", {}) or {}).get("feature_cols", []) or [])
    transfer_table, transfer_summary = transfer_audit(
        dukascopy_scored,
        broker_scored,
        feature_columns=feature_columns,
    )
    transfer_table.to_csv(run_dir / "feature_transfer.csv", index=False)
    _write_json(run_dir / "prediction_transfer.json", transfer_summary)

    training_end = dukascopy_raw.index.max()
    approximate, approximate_metrics = approximate_oot_backtest(
        broker_scored,
        training_end=training_end,
        median_tick_spread_bps=float(quality["tick_spread_bps_median"]),
        commission_bps_per_side=BASE_STRESS.commission_bps_per_side,
    )
    approximate.to_csv(run_dir / "approximate_oot_bar_returns.csv", index_label="timestamp")
    _write_json(run_dir / "approximate_oot_metrics.json", approximate_metrics)

    ledger_dir = run_dir / "tick_ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    stress_rows: list[dict[str, Any]] = []
    stress_diagnostics: dict[str, Any] = {}
    base_ledger = pd.DataFrame()
    base_metrics: dict[str, Any] = {}
    for stress in STRESS_GRID:
        ledger, diagnostics = tick_execution_ledger(broker_scored, tick_export.frame, stress=stress)
        metrics = trade_ledger_metrics(ledger)
        stress_rows.append({"scenario_id": stress.scenario_id, **asdict(stress), **metrics})
        stress_diagnostics[stress.scenario_id] = diagnostics
        ledger.to_csv(ledger_dir / f"{stress.scenario_id}.csv", index=False)
        if stress == BASE_STRESS:
            base_ledger = ledger
            base_metrics = metrics
    stress_table = pd.DataFrame(stress_rows)
    stress_table.to_csv(run_dir / "tick_stress_metrics.csv", index=False)
    _write_json(run_dir / "tick_execution_diagnostics.json", stress_diagnostics)
    base_ledger.to_csv(run_dir / "tick_trade_ledger_base.csv", index=False)

    samples = enrich_meta_label_samples(base_ledger, m1=exports["M1"].frame, ticks=tick_export.frame)
    samples.to_csv(run_dir / "meta_label_samples.csv", index=True)
    gate_table, gate_status = evaluate_m1_gates(samples)
    gate_table.to_csv(run_dir / "m1_gate_metrics.csv", index=False)
    _write_json(run_dir / "m1_gate_status.json", gate_status)

    meta_features = [
        "pred_ret",
        "abs_pred_ret",
        "atr_over_price_48",
        "entry_spread_bps",
        "side_m1_ret_1",
        "side_m1_ret_5",
        "m1_realized_vol_15",
        "m1_path_efficiency_15",
        "m1_range_over_close",
    ]
    if samples.empty:
        meta_payload = {
            "status": "insufficient_samples",
            "reason": "No exact closed trades were available for meta-labeling.",
            "metrics": {"rows": 0, "features": meta_features},
            "folds": [],
        }
        pd.DataFrame().to_csv(run_dir / "meta_label_predictions.csv", index=False)
    else:
        meta = chronological_meta_label_evaluation(
            samples,
            feature_columns=meta_features,
            target_column="meta_label",
            min_samples=60,
            min_class_samples=20,
            n_splits=3,
            seed=7,
        )
        meta.predictions.to_csv(run_dir / "meta_label_predictions.csv", index_label="entry_timestamp")
        meta_payload = {
            "status": meta.status,
            "reason": meta.reason,
            "metrics": meta.metrics,
            "folds": meta.fold_metadata,
        }
    _write_json(run_dir / "meta_label_status.json", meta_payload)

    base_cumulative = float(base_metrics.get("cumulative_return", 0.0))
    worst_cumulative = float(stress_table["cumulative_return"].min()) if not stress_table.empty else 0.0
    exact_trade_count = int(base_metrics.get("trade_count", 0))
    if base_cumulative <= 0.0 and exact_trade_count < 30:
        verdict = (
            "NO-GO: the frozen signal is negative in the base exact-tick replay, "
            "and the exact sample is too small to establish persistent alpha."
        )
    elif base_cumulative <= 0.0:
        verdict = "NO-GO: the frozen signal is not profitable in the base exact-tick replay."
    elif exact_trade_count < 30:
        verdict = "NO-GO: exact tick sample is too small to establish persistent alpha."
    elif worst_cumulative <= 0.0:
        verdict = "RESEARCH-ONLY: base result is positive but does not survive the full execution stress grid."
    else:
        verdict = "RESEARCH-ONLY: exact replay is positive across the grid, but prospective confirmation is still required."

    summary = {
        "suite": "ethusd_broker_alpha_suite_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir.relative_to(PROJECT_ROOT)),
        "research_verdict": verdict,
        "frozen_training_end": training_end.isoformat(),
        "frozen_contract": {
            "config_path": str(MODEL07_CONFIG.relative_to(PROJECT_ROOT)),
            "config_sha256": file_sha256(MODEL07_CONFIG),
            "model_path": str(MODEL07_BUNDLE.relative_to(PROJECT_ROOT)),
            "model_sha256": file_sha256(MODEL07_BUNDLE),
            "model_feature_count": int(len(feature_columns)),
            "signal_thresholds": dict(dict(config.get("signals", {}) or {}).get("params", {}) or {}),
            "minimum_holding_bars": int(dict(config.get("backtest", {}) or {}).get("min_holding_bars", 0)),
        },
        "data_quality": quality,
        "prediction_transfer": transfer_summary,
        "approximate_oot": approximate_metrics,
        "exact_tick_base": base_metrics,
        "stress_grid": {
            "scenario_count": int(len(stress_table)),
            "base_cumulative_return": base_cumulative,
            "median_cumulative_return": float(stress_table["cumulative_return"].median()),
            "worst_cumulative_return": worst_cumulative,
            "positive_scenario_count": int((stress_table["cumulative_return"] > 0.0).sum()),
        },
        "m1_gate": gate_status,
        "meta_label": meta_payload,
        "limitations": [
            "Tick export covers only 2026-07-02 to 2026-08-10 and appears capped at 2,000,000 rows.",
            "cTrader tick_volume is not economically equivalent to Dukascopy volume.",
            "Exact replay excludes segments without both entry and exit inside tick coverage.",
            "Swap, market impact, rejected fills, and account-wide FTMO controls are not modeled.",
            "This is frozen-model out-of-time historical evidence, not prospective evidence.",
        ],
    }
    _write_json(run_dir / "summary.json", summary)
    provenance = {
        "created_at_utc": summary["created_at_utc"],
        "git": collect_git_metadata(),
        "frozen_config_sha256": file_sha256(MODEL07_CONFIG),
        "frozen_model_sha256": file_sha256(MODEL07_BUNDLE),
        "data_files": {
            path.name: {"path": str(path.relative_to(PROJECT_ROOT)), "sha256": file_sha256(path)}
            for path in sorted(BROKER_ROOT.glob("*.csv"))
        },
        "stress_grid": [asdict(item) for item in STRESS_GRID],
        "selection_policy": "No return-based scenario selection; base, median, and worst are reported.",
    }
    _write_json(run_dir / "provenance.json", provenance)
    (run_dir / "report.md").write_text(_report_markdown(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen Model-07 ETHUSD broker alpha suite.")
    parser.add_argument("--output-dir", default=None, help="New artifact directory under the project root.")
    args = parser.parse_args()
    summary = run_suite(output_dir=args.output_dir)
    print(json.dumps(_jsonable(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "BASE_STRESS",
    "STRESS_GRID",
    "TickStressSpec",
    "approximate_oot_backtest",
    "enrich_meta_label_samples",
    "evaluate_m1_gates",
    "run_suite",
    "score_frozen_model07",
    "tick_execution_ledger",
    "trade_ledger_metrics",
    "transfer_audit",
]
