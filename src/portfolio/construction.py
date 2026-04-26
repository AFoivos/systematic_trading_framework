from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_backtest_metrics
from src.portfolio.constraints import PortfolioConstraints, apply_constraints
from src.portfolio.optimizer import optimize_mean_variance

_ALLOWED_MISSING_RETURN_POLICIES = {"raise", "raise_if_exposed", "fill_zero"}


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
    "PortfolioPerformance",
    "PortfolioRiskGuardConfig",
    "signal_to_raw_weights",
    "build_constrained_weights_from_exposures_over_time",
    "build_weights_from_signals_over_time",
    "build_optimized_weights_over_time",
    "compute_portfolio_performance",
]
