from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics
from src.portfolio.constraints import PortfolioConstraints, apply_constraints
from src.portfolio.optimizer import optimize_mean_variance

_ALLOWED_MISSING_RETURN_POLICIES = {"raise", "raise_if_exposed", "fill_zero"}
_POSITION_EPS = 1e-12


def compute_weight_transition_accounting(
    weights: pd.DataFrame,
    *,
    barrier_trade_count: int = 0,
) -> dict[str, float]:
    """
    Count vectorized portfolio activity with explicit semantics.

    `position_change_count` counts asset-level weight changes, including resizes.
    `rebalance_count` counts timestamps with any non-zero turnover.
    `discrete_trade_count` counts entry/exit state transitions and sign flips as exit+entry.
    `barrier_trade_count` is non-zero only for explicit trade-path engines.
    """
    if not isinstance(weights, pd.DataFrame):
        raise TypeError("weights must be a pandas DataFrame.")
    if weights.empty:
        return {
            "position_change_count": 0.0,
            "rebalance_count": 0.0,
            "discrete_trade_count": 0.0,
            "barrier_trade_count": float(barrier_trade_count),
            "trade_count": float(barrier_trade_count),
        }

    w = weights.fillna(0.0).astype(float)
    prev = w.shift(1).fillna(0.0)
    delta = w - prev
    position_change_count = int(delta.abs().gt(_POSITION_EPS).sum().sum())
    rebalance_count = int(delta.abs().sum(axis=1).gt(_POSITION_EPS).sum())

    prev_sign = np.sign(prev.where(prev.abs().gt(_POSITION_EPS), 0.0))
    curr_sign = np.sign(w.where(w.abs().gt(_POSITION_EPS), 0.0))
    entries = prev_sign.eq(0.0) & curr_sign.ne(0.0)
    exits = prev_sign.ne(0.0) & curr_sign.eq(0.0)
    flips = prev_sign.ne(0.0) & curr_sign.ne(0.0) & prev_sign.ne(curr_sign)
    discrete_trade_count = int(entries.sum().sum() + exits.sum().sum() + 2 * flips.sum().sum())
    canonical_trade_count = int(barrier_trade_count) if barrier_trade_count > 0 else discrete_trade_count
    return {
        "position_change_count": float(position_change_count),
        "rebalance_count": float(rebalance_count),
        "discrete_trade_count": float(discrete_trade_count),
        "barrier_trade_count": float(barrier_trade_count),
        "trade_count": float(canonical_trade_count),
    }


@dataclass
class PortfolioPerformance:
    """
    Store the time series and aggregate statistics produced by a portfolio-level backtest,
    keeping net and gross performance decomposition available for diagnostics.
    """
    equity_curve: pd.Series
    net_returns: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    turnover: pd.Series
    summary: dict[str, float]
    applied_weights: pd.DataFrame | None = None
    risk_guard_summary: dict[str, Any] = field(default_factory=dict)
    risk_guard_timeline: pd.DataFrame | None = None
    trades: pd.DataFrame | None = None


@dataclass(frozen=True)
class PortfolioRiskGuardConfig:
    enabled: bool = False
    weekly_return_target: float | None = None
    weekly_profit_lock: float | None = None
    after_target_mode: str = "reduce_risk"
    after_target_risk_multiplier: float = 0.25
    daily_soft_stop: float | None = None
    daily_soft_stop_risk_multiplier: float = 0.5
    daily_hard_stop: float | None = None
    max_daily_loss: float | None = None
    weekly_drawdown: float | None = None
    max_total_loss: float | None = None
    cooloff_bars: int = 0
    rearm_on_new_period: bool = True
    weekly_anchor: str = "W-FRI"


def _apply_missing_return_policy(
    asset_returns: pd.DataFrame,
    *,
    prev_weights: pd.DataFrame,
    missing_return_policy: str,
) -> pd.DataFrame:
    """
    Resolve missing-return handling explicitly so live positions cannot inherit synthetic flat
    PnL from missing panel data.
    """
    if missing_return_policy not in _ALLOWED_MISSING_RETURN_POLICIES:
        raise ValueError(
            f"missing_return_policy must be one of {_ALLOWED_MISSING_RETURN_POLICIES}."
        )

    returns = asset_returns.astype(float)
    missing_mask = returns.isna()
    if not bool(missing_mask.any().any()):
        return returns

    if missing_return_policy == "raise":
        missing_points = missing_mask.stack()
        examples = ", ".join(
            f"{ts}/{asset}" for ts, asset in missing_points[missing_points].index[:5]
        )
        raise ValueError(f"Missing portfolio returns encountered at: {examples}")

    if missing_return_policy == "raise_if_exposed":
        exposed_missing = missing_mask & prev_weights.ne(0.0)
        if bool(exposed_missing.any().any()):
            flagged = exposed_missing.stack()
            examples = ", ".join(
                f"{ts}/{asset}" for ts, asset in flagged[flagged].index[:5]
            )
            raise ValueError(
                "Missing portfolio returns encountered while positions were open at: "
                f"{examples}"
            )

    return returns.fillna(0.0)


def _normalize_portfolio_risk_guard_config(
    portfolio_guard: Mapping[str, Any] | None,
) -> PortfolioRiskGuardConfig:
    cfg = dict(portfolio_guard or {})
    return PortfolioRiskGuardConfig(
        enabled=bool(cfg.get("enabled", False)),
        weekly_return_target=(
            float(cfg["weekly_return_target"])
            if cfg.get("weekly_return_target") is not None
            else None
        ),
        weekly_profit_lock=(
            float(cfg["weekly_profit_lock"])
            if cfg.get("weekly_profit_lock") is not None
            else None
        ),
        after_target_mode=str(cfg.get("after_target_mode", "reduce_risk") or "reduce_risk"),
        after_target_risk_multiplier=float(cfg.get("after_target_risk_multiplier", 0.25)),
        daily_soft_stop=(
            float(cfg["daily_soft_stop"])
            if cfg.get("daily_soft_stop") is not None
            else None
        ),
        daily_soft_stop_risk_multiplier=float(cfg.get("daily_soft_stop_risk_multiplier", 0.5)),
        daily_hard_stop=(
            float(cfg["daily_hard_stop"])
            if cfg.get("daily_hard_stop") is not None
            else None
        ),
        max_daily_loss=(
            float(cfg["max_daily_loss"])
            if cfg.get("max_daily_loss") is not None
            else None
        ),
        weekly_drawdown=(
            float(cfg["weekly_drawdown"])
            if cfg.get("weekly_drawdown") is not None
            else None
        ),
        max_total_loss=(
            float(cfg["max_total_loss"])
            if cfg.get("max_total_loss") is not None
            else None
        ),
        cooloff_bars=int(cfg.get("cooloff_bars", 0) or 0),
        rearm_on_new_period=bool(cfg.get("rearm_on_new_period", True)),
        weekly_anchor=str(cfg.get("weekly_anchor", "W-FRI") or "W-FRI"),
    )


def _normalize_drawdown_sizing(drawdown_sizing: Mapping[str, Any] | None) -> dict[str, Any]:
    cfg = dict(drawdown_sizing or {})
    levels = []
    for raw_level in list(cfg.get("levels", []) or []):
        level = dict(raw_level or {})
        levels.append(
            {
                "max_dd": float(level.get("max_dd", 0.0)),
                "multiplier": float(level.get("multiplier", 1.0)),
            }
        )
    levels.sort(key=lambda item: float(item["max_dd"]))
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "levels": levels,
    }


def _drawdown_sizing_multiplier(current_drawdown: float, drawdown_sizing: Mapping[str, Any]) -> float:
    cfg = dict(drawdown_sizing or {})
    if not bool(cfg.get("enabled", False)):
        return 1.0
    levels = list(cfg.get("levels", []) or [])
    if not levels:
        return 1.0
    dd = abs(min(float(current_drawdown), 0.0))
    for level in levels:
        if dd <= float(level["max_dd"]):
            return float(level["multiplier"])
    return float(levels[-1]["multiplier"])


def _resolve_returns_row(
    returns_t: pd.Series,
    *,
    prev_weights: pd.Series,
    missing_return_policy: str,
    timestamp: pd.Timestamp,
) -> pd.Series:
    if missing_return_policy not in _ALLOWED_MISSING_RETURN_POLICIES:
        raise ValueError(
            f"missing_return_policy must be one of {_ALLOWED_MISSING_RETURN_POLICIES}."
        )

    rets = returns_t.astype(float)
    missing_mask = rets.isna()
    if not bool(missing_mask.any()):
        return rets

    if missing_return_policy == "raise":
        assets = [str(asset) for asset in rets.index[missing_mask][:5]]
        raise ValueError(f"Missing portfolio returns encountered at {timestamp}: {assets}")

    if missing_return_policy == "raise_if_exposed":
        exposed_missing = missing_mask & prev_weights.reindex(rets.index).fillna(0.0).ne(0.0)
        if bool(exposed_missing.any()):
            assets = [str(asset) for asset in rets.index[exposed_missing][:5]]
            raise ValueError(
                "Missing portfolio returns encountered while positions were open at "
                f"{timestamp}: {assets}"
            )

    return rets.fillna(0.0)


def _run_guarded_portfolio_performance(
    weights: pd.DataFrame,
    asset_returns: pd.DataFrame,
    *,
    missing_return_policy: str,
    cost_per_turnover: float,
    slippage_per_turnover: float,
    periods_per_year: int,
    guard_cfg: PortfolioRiskGuardConfig,
    drawdown_sizing: Mapping[str, Any] | None = None,
) -> PortfolioPerformance:
    index = asset_returns.index
    columns = asset_returns.columns
    applied_weights = pd.DataFrame(0.0, index=index, columns=columns, dtype=float)
    gross_returns = pd.Series(0.0, index=index, dtype=float, name="gross_returns")
    net_returns = pd.Series(0.0, index=index, dtype=float, name="net_returns")
    costs = pd.Series(0.0, index=index, dtype=float, name="costs")
    turnover = pd.Series(0.0, index=index, dtype=float, name="turnover")
    equity_curve = pd.Series(1.0, index=index, dtype=float, name="equity")
    timeline_rows: list[dict[str, Any]] = []

    prev_actual_weights = pd.Series(0.0, index=columns, dtype=float)
    equity = 1.0
    day_start_equity = 1.0
    week_start_equity = 1.0
    week_peak_equity = 1.0
    total_peak_equity = 1.0
    last_day: pd.Timestamp | None = None
    last_week: pd.Period | None = None
    cooloff_remaining = 0
    permanent_flat = False
    daily_armed = True
    weekly_armed = True
    daily_soft_stopped = False
    daily_hard_stopped = False
    weekly_locked = False
    drawdown_sizing_cfg = _normalize_drawdown_sizing(drawdown_sizing)

    for ts in index:
        timestamp = pd.Timestamp(ts)
        period_timestamp = timestamp.tz_localize(None) if timestamp.tzinfo is not None else timestamp
        day_key = timestamp.normalize()
        week_key = period_timestamp.to_period(str(guard_cfg.weekly_anchor))
        if last_day is None or day_key != last_day:
            day_start_equity = equity
            last_day = day_key
            if guard_cfg.rearm_on_new_period:
                daily_armed = True
                daily_soft_stopped = False
                daily_hard_stopped = False
        if last_week is None or week_key != last_week:
            week_start_equity = equity
            week_peak_equity = equity
            last_week = week_key
            if guard_cfg.rearm_on_new_period:
                weekly_armed = True
                weekly_locked = False

        current_total_drawdown = float(equity / total_peak_equity - 1.0) if total_peak_equity > 0.0 else 0.0
        drawdown_multiplier = _drawdown_sizing_multiplier(current_total_drawdown, drawdown_sizing_cfg)
        soft_multiplier = float(guard_cfg.daily_soft_stop_risk_multiplier) if daily_soft_stopped else 1.0
        weekly_lock_multiplier = 1.0
        if weekly_locked:
            weekly_lock_multiplier = (
                0.0
                if guard_cfg.after_target_mode == "flatten"
                else float(guard_cfg.after_target_risk_multiplier)
            )
        risk_multiplier = float(drawdown_multiplier * soft_multiplier * weekly_lock_multiplier)
        guard_active = permanent_flat or cooloff_remaining > 0 or daily_hard_stopped or risk_multiplier <= 0.0
        desired_weights = weights.loc[timestamp].astype(float)
        actual_weights = (
            pd.Series(0.0, index=columns, dtype=float)
            if guard_active
            else desired_weights.reindex(columns).fillna(0.0).astype(float) * risk_multiplier
        )

        returns_t = _resolve_returns_row(
            asset_returns.loc[timestamp],
            prev_weights=prev_actual_weights,
            missing_return_policy=missing_return_policy,
            timestamp=timestamp,
        )
        turnover_t = float((actual_weights - prev_actual_weights).abs().sum())
        gross_return_t = float((prev_actual_weights * returns_t).sum())
        cost_t = float((cost_per_turnover + slippage_per_turnover) * turnover_t)
        net_return_t = float(gross_return_t - cost_t)
        equity *= 1.0 + net_return_t
        week_peak_equity = max(week_peak_equity, equity)
        total_peak_equity = max(total_peak_equity, equity)

        daily_loss = float(equity / day_start_equity - 1.0)
        weekly_return = float(equity / week_start_equity - 1.0) if week_start_equity > 0.0 else 0.0
        weekly_drawdown = float(equity / week_peak_equity - 1.0) if week_peak_equity > 0.0 else 0.0
        total_loss = float(equity - 1.0)

        breach_reasons: list[str] = []
        soft_stop_triggered = False
        hard_stop_triggered = False
        weekly_lock_triggered = False
        if (
            guard_cfg.daily_soft_stop is not None
            and not daily_soft_stopped
            and daily_loss <= -float(guard_cfg.daily_soft_stop)
        ):
            breach_reasons.append("daily_soft_stop")
            daily_soft_stopped = True
            soft_stop_triggered = True
        if (
            guard_cfg.daily_hard_stop is not None
            and not daily_hard_stopped
            and daily_loss <= -float(guard_cfg.daily_hard_stop)
        ):
            breach_reasons.append("daily_hard_stop")
            daily_hard_stopped = True
            daily_armed = False
            hard_stop_triggered = True
        if (
            guard_cfg.max_daily_loss is not None
            and daily_armed
            and daily_loss <= -float(guard_cfg.max_daily_loss)
        ):
            breach_reasons.append("daily_loss")
            daily_armed = False
        if (
            guard_cfg.weekly_profit_lock is not None
            and not weekly_locked
            and weekly_return >= float(guard_cfg.weekly_profit_lock)
        ):
            breach_reasons.append("weekly_profit_lock")
            weekly_locked = True
            weekly_lock_triggered = True
        if (
            guard_cfg.weekly_drawdown is not None
            and weekly_armed
            and weekly_drawdown <= -float(guard_cfg.weekly_drawdown)
        ):
            breach_reasons.append("weekly_drawdown")
            weekly_armed = False
        if (
            guard_cfg.max_total_loss is not None
            and total_loss <= -float(guard_cfg.max_total_loss)
        ):
            breach_reasons.append("max_total_loss")
            permanent_flat = True

        triggered = bool(breach_reasons) and not guard_active
        starts_cooloff = any(
            reason in {"daily_loss", "weekly_drawdown", "max_total_loss"}
            for reason in breach_reasons
        )
        if triggered and starts_cooloff and not permanent_flat:
            cooloff_remaining = max(cooloff_remaining, int(guard_cfg.cooloff_bars))

        applied_weights.loc[timestamp] = actual_weights
        gross_returns.loc[timestamp] = gross_return_t
        net_returns.loc[timestamp] = net_return_t
        costs.loc[timestamp] = cost_t
        turnover.loc[timestamp] = turnover_t
        equity_curve.loc[timestamp] = equity
        timeline_rows.append(
            {
                "timestamp": timestamp,
                "risk_guard_active": bool(guard_active),
                "risk_guard_triggered": bool(triggered),
                "risk_guard_reason": ",".join(breach_reasons),
                "risk_guard_daily_soft_stop_breach": bool(soft_stop_triggered),
                "risk_guard_daily_hard_stop_breach": bool(hard_stop_triggered),
                "risk_guard_weekly_profit_lock": bool(weekly_lock_triggered),
                "risk_guard_daily_loss_breach": bool("daily_loss" in breach_reasons),
                "risk_guard_weekly_drawdown_breach": bool("weekly_drawdown" in breach_reasons),
                "risk_guard_max_total_loss_breach": bool("max_total_loss" in breach_reasons),
                "risk_guard_cooloff_remaining": int(cooloff_remaining),
                "risk_multiplier": float(risk_multiplier),
                "drawdown_sizing_multiplier": float(drawdown_multiplier),
                "daily_loss": daily_loss,
                "weekly_return": weekly_return,
                "weekly_drawdown": weekly_drawdown,
                "total_loss": total_loss,
                "equity": equity,
            }
        )

        if guard_active and cooloff_remaining > 0:
            cooloff_remaining -= 1
        prev_actual_weights = actual_weights

    timeline = pd.DataFrame(timeline_rows).set_index("timestamp")
    summary = compute_backtest_metrics(
        net_returns=net_returns,
        periods_per_year=periods_per_year,
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )
    summary.update(compute_weight_transition_accounting(applied_weights))
    risk_guard_summary = {
        "enabled": bool(guard_cfg.enabled),
        "weekly_return_target": guard_cfg.weekly_return_target,
        "weekly_profit_lock": guard_cfg.weekly_profit_lock,
        "after_target_mode": guard_cfg.after_target_mode,
        "after_target_risk_multiplier": guard_cfg.after_target_risk_multiplier,
        "daily_soft_stop": guard_cfg.daily_soft_stop,
        "daily_soft_stop_risk_multiplier": guard_cfg.daily_soft_stop_risk_multiplier,
        "daily_hard_stop": guard_cfg.daily_hard_stop,
        "max_daily_loss": guard_cfg.max_daily_loss,
        "weekly_drawdown": guard_cfg.weekly_drawdown,
        "max_total_loss": guard_cfg.max_total_loss,
        "cooloff_bars": int(guard_cfg.cooloff_bars),
        "rearm_on_new_period": bool(guard_cfg.rearm_on_new_period),
        "weekly_anchor": guard_cfg.weekly_anchor,
        "flattened_bar_count": int(timeline["risk_guard_active"].sum()),
        "trigger_count": int(timeline["risk_guard_triggered"].sum()),
        "soft_stop_trigger_count": int(timeline["risk_guard_daily_soft_stop_breach"].sum()),
        "hard_stop_trigger_count": int(timeline["risk_guard_daily_hard_stop_breach"].sum()),
        "weekly_lock_trigger_count": int(timeline["risk_guard_weekly_profit_lock"].sum()),
        "daily_loss_trigger_count": int(timeline["risk_guard_daily_loss_breach"].sum()),
        "weekly_drawdown_trigger_count": int(timeline["risk_guard_weekly_drawdown_breach"].sum()),
        "max_total_loss_trigger_count": int(timeline["risk_guard_max_total_loss_breach"].sum()),
        "drawdown_sizing_enabled": bool(drawdown_sizing_cfg.get("enabled", False)),
        "min_risk_multiplier": float(timeline["risk_multiplier"].min()) if "risk_multiplier" in timeline else 1.0,
        "first_triggered_at": (
            timeline.index[timeline["risk_guard_triggered"]][0].isoformat()
            if bool(timeline["risk_guard_triggered"].any())
            else None
        ),
        "permanent_flattened": bool(permanent_flat),
    }

    return PortfolioPerformance(
        equity_curve=equity_curve,
        net_returns=net_returns,
        gross_returns=gross_returns,
        costs=costs,
        turnover=turnover,
        summary=summary,
        applied_weights=applied_weights,
        risk_guard_summary=risk_guard_summary,
        risk_guard_timeline=timeline,
    )


def signal_to_raw_weights(
    signal_t: pd.Series,
    *,
    long_short: bool = True,
    gross_target: float = 1.0,
) -> pd.Series:
    """
    Handle signal to raw weights inside the portfolio construction layer. The helper isolates
    one focused responsibility so the surrounding code remains modular, readable, and easier to
    test.
    """
    if not isinstance(signal_t, pd.Series):
        raise TypeError("signal_t must be a pandas Series.")

    out = pd.Series(0.0, index=signal_t.index, dtype=float)
    valid_mask = signal_t.notna()
    if not bool(valid_mask.any()):
        return out

    s = signal_t.loc[valid_mask].astype(float)
    if long_short:
        s = s - float(s.mean())
    else:
        has_long = bool(s.gt(0.0).any())
        has_short = bool(s.lt(0.0).any())
        if has_long and has_short:
            raise ValueError(
                "portfolio.long_short=false requires one-sided signals only; mixed-sign signals detected."
            )
        if has_short:
            s = s.clip(upper=0.0)
        else:
            s = s.clip(lower=0.0)

    denom = float(np.abs(s).sum())
    if denom <= 0:
        return out

    out.loc[valid_mask] = s / denom * float(gross_target)
    return out


def build_weights_from_signals_over_time(
    signals: pd.DataFrame,
    *,
    constraints: PortfolioConstraints | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    long_short: bool = True,
    gross_target: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build weights from signals over time as an explicit intermediate object used by the
    portfolio construction pipeline. Keeping this assembly step separate makes the orchestration
    code easier to reason about and test.
    """
    if not isinstance(signals, pd.DataFrame):
        raise TypeError("signals must be a pandas DataFrame.")

    constraints = constraints or PortfolioConstraints()
    signals_df = signals.astype(float).sort_index().copy()

    weights = pd.DataFrame(index=signals_df.index, columns=signals_df.columns, dtype=float)
    diagnostics_rows: list[dict[str, float]] = []
    prev_w: pd.Series | None = None

    for ts, sig_t in signals_df.iterrows():
        raw_w = signal_to_raw_weights(
            sig_t,
            long_short=long_short,
            gross_target=min(float(gross_target), float(constraints.max_gross_leverage)),
        )
        constrained_w, diag = apply_constraints(
            raw_w,
            constraints=constraints,
            prev_weights=prev_w,
            asset_to_group=asset_to_group,
        )
        weights.loc[ts] = constrained_w
        diagnostics_rows.append(
            {
                "timestamp": ts,
                "net_exposure": float(diag["net_exposure"]),
                "gross_exposure": float(diag["gross_exposure"]),
                "turnover": float(diag["turnover"]),
            }
        )
        prev_w = constrained_w

    diagnostics = pd.DataFrame(diagnostics_rows).set_index("timestamp")
    return weights.fillna(0.0), diagnostics


def build_ranked_weights_from_scores_over_time(
    scores: pd.DataFrame,
    *,
    selection: Mapping[str, Any] | None = None,
    hysteresis: Mapping[str, Any] | None = None,
    constraints: PortfolioConstraints | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    long_short: bool = True,
    gross_target: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build portfolio weights from dense expected-return scores using cross-sectional ranking.

    This keeps PR2 dense forecasting separate from the legacy per-asset threshold stack: the
    model emits continuous scores for all bars, and the portfolio layer chooses the top current
    opportunities while optionally stabilizing holdings with hysteresis.
    """
    if not isinstance(scores, pd.DataFrame):
        raise TypeError("scores must be a pandas DataFrame.")

    selection_cfg = dict(selection or {})
    hysteresis_cfg = dict(hysteresis or {})
    constraints = constraints or PortfolioConstraints()
    score_df = scores.astype(float).sort_index().copy()
    columns = list(score_df.columns)

    top_k = int(selection_cfg.get("top_k", len(columns) if columns else 0))
    if top_k <= 0:
        raise ValueError("portfolio.selection.top_k must be a positive integer.")
    top_k = min(top_k, len(columns))
    min_expected_net_return = float(selection_cfg.get("min_expected_net_return", 0.0))
    if min_expected_net_return < 0.0:
        raise ValueError("portfolio.selection.min_expected_net_return must be >= 0.")
    rank_by_abs = bool(selection_cfg.get("rank_by_abs", long_short))
    weighting = str(selection_cfg.get("weighting", "score"))
    if weighting not in {"equal", "score"}:
        raise ValueError("portfolio.selection.weighting must be 'equal' or 'score'.")
    rebalance_every_n_bars = int(selection_cfg.get("rebalance_every_n_bars", 1) or 1)
    if rebalance_every_n_bars <= 0:
        raise ValueError("portfolio.selection.rebalance_every_n_bars must be a positive integer.")

    hysteresis_enabled = bool(hysteresis_cfg.get("enabled", False))
    entry_threshold = max(
        min_expected_net_return,
        float(hysteresis_cfg.get("entry_threshold", min_expected_net_return))
        if hysteresis_enabled
        else min_expected_net_return,
    )
    exit_threshold = (
        float(hysteresis_cfg.get("exit_threshold", min_expected_net_return))
        if hysteresis_enabled
        else min_expected_net_return
    )
    if entry_threshold < 0.0 or exit_threshold < 0.0:
        raise ValueError("execution.hysteresis thresholds must be >= 0.")
    min_holding_bars = (
        int(hysteresis_cfg.get("min_holding_bars", 0) or 0)
        if hysteresis_enabled
        else 0
    )
    if min_holding_bars < 0:
        raise ValueError("execution.hysteresis.min_holding_bars must be >= 0.")

    weights = pd.DataFrame(0.0, index=score_df.index, columns=columns, dtype=float)
    diagnostics_rows: list[dict[str, float | int]] = []
    prev_w: pd.Series | None = None
    active_side: dict[str, float] = {}
    active_age: dict[str, int] = {}
    active_strength: dict[str, float] = {}

    for row_number, (ts, score_t) in enumerate(score_df.iterrows()):
        should_rebalance = row_number == 0 or (row_number % rebalance_every_n_bars == 0)
        if not should_rebalance:
            for asset in list(active_side):
                active_age[asset] = int(active_age.get(asset, 0)) + 1
            held_w = (
                prev_w.reindex(columns).fillna(0.0).astype(float)
                if prev_w is not None
                else pd.Series(0.0, index=columns, dtype=float)
            )
            weights.loc[ts] = held_w
            diagnostics_rows.append(
                {
                    "timestamp": ts,
                    "net_exposure": float(held_w.sum()),
                    "gross_exposure": float(held_w.abs().sum()),
                    "turnover": 0.0,
                    "ranked_selected_count": int(len(active_side)),
                    "ranked_candidate_count": 0,
                    "hysteresis_active_count": int(len(active_side)),
                    "is_rebalance_bar": 0,
                    "rebalance_every_n_bars": int(rebalance_every_n_bars),
                }
            )
            prev_w = held_w
            continue

        numeric = pd.to_numeric(score_t, errors="coerce").astype(float)
        finite = numeric[np.isfinite(numeric)]
        current_active: dict[str, float] = {}

        for asset, side in list(active_side.items()):
            active_age[asset] = int(active_age.get(asset, 0)) + 1
            score_value = numeric.get(asset, np.nan)
            score_abs = abs(float(score_value)) if np.isfinite(score_value) else 0.0
            current_sign = float(np.sign(score_value)) if np.isfinite(score_value) and score_value != 0.0 else side
            can_exit = active_age[asset] >= min_holding_bars
            sign_flipped = bool(current_sign != side and np.isfinite(score_value) and score_value != 0.0)
            should_exit = can_exit and (score_abs < exit_threshold or sign_flipped)
            if should_exit:
                active_side.pop(asset, None)
                active_age.pop(asset, None)
                active_strength.pop(asset, None)
                continue
            current_active[asset] = side
            if score_abs > 0.0:
                active_strength[asset] = score_abs

        slots = max(top_k - len(current_active), 0)
        candidates: list[tuple[float, str, float, float]] = []
        for asset, score_value in finite.items():
            asset_name = str(asset)
            if asset_name in current_active:
                continue
            score_float = float(score_value)
            if score_float == 0.0:
                continue
            side = float(np.sign(score_float))
            if not long_short and side < 0.0:
                continue
            score_abs = abs(score_float)
            rank_score = score_abs if rank_by_abs else score_float
            hurdle_value = score_abs if long_short else score_float
            if hurdle_value < entry_threshold:
                continue
            candidates.append((float(rank_score), asset_name, side, score_abs))
        candidates.sort(key=lambda item: (-item[0], item[1]))

        for _, asset, side, score_abs in candidates[:slots]:
            current_active[asset] = side
            active_side[asset] = side
            active_age[asset] = 1
            active_strength[asset] = score_abs

        raw_w = pd.Series(0.0, index=columns, dtype=float)
        if current_active:
            if weighting == "equal":
                strengths = pd.Series(1.0, index=list(current_active), dtype=float)
            else:
                strengths = pd.Series(
                    {
                        asset: max(float(active_strength.get(asset, 0.0)), exit_threshold, 0.0)
                        for asset in current_active
                    },
                    dtype=float,
                )
                if float(strengths.sum()) <= 0.0:
                    strengths = pd.Series(1.0, index=list(current_active), dtype=float)
            denom = float(strengths.abs().sum())
            target_gross = min(float(gross_target), float(constraints.max_gross_leverage))
            for asset, side in current_active.items():
                raw_w.loc[asset] = float(side) * float(strengths.loc[asset]) / denom * target_gross

        constrained_w, diag = apply_constraints(
            raw_w,
            constraints=constraints,
            prev_weights=prev_w,
            asset_to_group=asset_to_group,
        )
        weights.loc[ts] = constrained_w
        diagnostics_rows.append(
            {
                "timestamp": ts,
                "net_exposure": float(diag["net_exposure"]),
                "gross_exposure": float(diag["gross_exposure"]),
                "turnover": float(diag["turnover"]),
                "ranked_selected_count": int(len(current_active)),
                "ranked_candidate_count": int(len(candidates)),
                "hysteresis_active_count": int(len(active_side)),
                "is_rebalance_bar": 1,
                "rebalance_every_n_bars": int(rebalance_every_n_bars),
            }
        )
        prev_w = constrained_w
        active_side = dict(current_active)
        active_age = {asset: active_age.get(asset, 1) for asset in active_side}
        active_strength = {asset: active_strength.get(asset, 0.0) for asset in active_side}

    diagnostics = pd.DataFrame(diagnostics_rows).set_index("timestamp")
    return weights.fillna(0.0), diagnostics


def build_constrained_weights_from_exposures_over_time(
    exposures: pd.DataFrame,
    *,
    constraints: PortfolioConstraints | None = None,
    asset_to_group: Mapping[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply portfolio constraints to pre-sized signed exposures without normalizing them into a
    fixed gross target. This is used by risk-per-trade sizing, where absolute exposure already
    carries risk information.
    """
    if not isinstance(exposures, pd.DataFrame):
        raise TypeError("exposures must be a pandas DataFrame.")

    constraints = constraints or PortfolioConstraints()
    exposure_df = exposures.astype(float).sort_index().copy()
    weights = pd.DataFrame(index=exposure_df.index, columns=exposure_df.columns, dtype=float)
    diagnostics_rows: list[dict[str, float]] = []
    prev_w: pd.Series | None = None

    for ts, exposure_t in exposure_df.iterrows():
        raw_w = exposure_t.reindex(exposure_df.columns).fillna(0.0).astype(float)
        constrained_w, diag = apply_constraints(
            raw_w,
            constraints=constraints,
            prev_weights=prev_w,
            asset_to_group=asset_to_group,
        )
        weights.loc[ts] = constrained_w
        diagnostics_rows.append(
            {
                "timestamp": ts,
                "net_exposure": float(diag["net_exposure"]),
                "gross_exposure": float(diag["gross_exposure"]),
                "turnover": float(diag["turnover"]),
            }
        )
        prev_w = constrained_w

    diagnostics = pd.DataFrame(diagnostics_rows).set_index("timestamp")
    return weights.fillna(0.0), diagnostics


def build_optimized_weights_over_time(
    expected_returns: pd.DataFrame,
    *,
    covariance_by_date: Mapping[pd.Timestamp, pd.DataFrame] | None = None,
    constraints: PortfolioConstraints | None = None,
    asset_to_group: Mapping[str, str] | None = None,
    risk_aversion: float = 5.0,
    trade_aversion: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build optimized weights over time as an explicit intermediate object used by the portfolio
    construction pipeline. Keeping this assembly step separate makes the orchestration code
    easier to reason about and test.
    """
    if not isinstance(expected_returns, pd.DataFrame):
        raise TypeError("expected_returns must be a pandas DataFrame.")

    constraints = constraints or PortfolioConstraints()
    mu_df = expected_returns.astype(float).sort_index().copy()

    weights = pd.DataFrame(index=mu_df.index, columns=mu_df.columns, dtype=float)
    meta_rows: list[dict[str, float | bool | str]] = []
    prev_w: pd.Series | None = None

    cov_dict = dict(covariance_by_date or {})
    last_cov: pd.DataFrame | None = None

    for ts, mu_t in mu_df.iterrows():
        cov_t = cov_dict.get(pd.Timestamp(ts))
        if cov_t is not None:
            last_cov = cov_t

        if covariance_by_date is not None and last_cov is None:
            if prev_w is None:
                w_t = pd.Series(0.0, index=mu_df.columns, dtype=float)
            else:
                w_t = prev_w.reindex(mu_df.columns).fillna(0.0).astype(float)
            meta = {
                "solver_success": False,
                "used_fallback": False,
                "net_exposure": float(w_t.sum()),
                "gross_exposure": float(np.abs(w_t).sum()),
                "turnover": 0.0,
            }
        else:
            w_t, meta = optimize_mean_variance(
                mu_t,
                covariance=last_cov,
                constraints=constraints,
                prev_weights=prev_w,
                asset_to_group=asset_to_group,
                risk_aversion=risk_aversion,
                trade_aversion=trade_aversion,
            )
        weights.loc[ts] = w_t
        meta_rows.append(
            {
                "timestamp": ts,
                "solver_success": bool(meta["solver_success"]),
                "used_fallback": bool(meta["used_fallback"]),
                "net_exposure": float(meta["net_exposure"]),
                "gross_exposure": float(meta["gross_exposure"]),
                "turnover": float(meta["turnover"]),
            }
        )
        prev_w = w_t

    diagnostics = pd.DataFrame(meta_rows).set_index("timestamp")
    return weights.fillna(0.0), diagnostics


def compute_portfolio_performance(
    weights: pd.DataFrame,
    asset_returns: pd.DataFrame,
    *,
    missing_return_policy: str = "raise_if_exposed",
    cost_per_turnover: float = 0.0,
    slippage_per_turnover: float = 0.0,
    periods_per_year: int = 252,
    portfolio_guard: Mapping[str, Any] | None = None,
    drawdown_sizing: Mapping[str, Any] | None = None,
) -> PortfolioPerformance:
    """
    Compute portfolio performance for the portfolio construction layer. The helper keeps the
    calculation isolated so the calling pipeline can reuse the same logic consistently across
    experiments.
    """
    if not isinstance(weights, pd.DataFrame):
        raise TypeError("weights must be a pandas DataFrame.")
    if not isinstance(asset_returns, pd.DataFrame):
        raise TypeError("asset_returns must be a pandas DataFrame.")

    common_index = asset_returns.index.intersection(weights.index)
    common_cols = asset_returns.columns.intersection(weights.columns)
    if len(common_index) == 0 or len(common_cols) == 0:
        raise ValueError("weights and asset_returns have no common index/columns.")

    w = weights.reindex(index=common_index, columns=common_cols).fillna(0.0).astype(float)
    r = asset_returns.reindex(index=common_index, columns=common_cols).astype(float)

    guard_cfg = _normalize_portfolio_risk_guard_config(portfolio_guard)
    drawdown_sizing_cfg = _normalize_drawdown_sizing(drawdown_sizing)
    if guard_cfg.enabled or bool(drawdown_sizing_cfg.get("enabled", False)):
        return _run_guarded_portfolio_performance(
            w,
            r,
            missing_return_policy=missing_return_policy,
            cost_per_turnover=cost_per_turnover,
            slippage_per_turnover=slippage_per_turnover,
            periods_per_year=periods_per_year,
            guard_cfg=guard_cfg,
            drawdown_sizing=drawdown_sizing_cfg,
        )

    prev_w = w.shift(1).fillna(0.0)
    r = _apply_missing_return_policy(
        r,
        prev_weights=prev_w,
        missing_return_policy=missing_return_policy,
    )
    turnover = (w - prev_w).abs().sum(axis=1)
    gross_returns = (w.shift(1).fillna(0.0) * r).sum(axis=1)
    costs = (cost_per_turnover + slippage_per_turnover) * turnover
    net_returns = gross_returns - costs

    equity = (1.0 + net_returns).cumprod()
    equity.name = "equity"
    gross_returns.name = "gross_returns"
    net_returns.name = "net_returns"
    costs.name = "costs"
    turnover.name = "turnover"

    summary = compute_backtest_metrics(
        net_returns=net_returns,
        periods_per_year=periods_per_year,
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )
    summary.update(compute_weight_transition_accounting(w))

    return PortfolioPerformance(
        equity_curve=equity,
        net_returns=net_returns,
        gross_returns=gross_returns,
        costs=costs,
        turnover=turnover,
        summary=summary,
        applied_weights=w,
        risk_guard_summary={"enabled": False},
        risk_guard_timeline=pd.DataFrame(index=w.index),
    )


__all__ = [
    "compute_weight_transition_accounting",
    "PortfolioPerformance",
    "PortfolioRiskGuardConfig",
    "signal_to_raw_weights",
    "build_constrained_weights_from_exposures_over_time",
    "build_weights_from_signals_over_time",
    "build_optimized_weights_over_time",
    "compute_portfolio_performance",
]
