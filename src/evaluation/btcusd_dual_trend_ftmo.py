from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.metrics import (
    annualized_return,
    annualized_volatility,
    calmar_ratio,
    hit_rate,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
)
from src.signals.btcusd_dual_trend_ftmo_signal import btcusd_dual_trend_ensemble_signal


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if np.isfinite(numeric) else None


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator == 0.0:
        return None
    return float(numerator / denominator)


def _daily_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return pd.Series(dtype=float, name="daily_return")
    utc_index = returns.index.tz_convert("UTC")
    values = pd.Series(returns.to_numpy(dtype=float), index=utc_index)
    daily = values.groupby(values.index.normalize()).apply(lambda group: (1.0 + group).prod() - 1.0)
    daily.name = "daily_return"
    return daily.astype(float)


def _monthly_returns(returns: pd.Series) -> dict[str, float]:
    if returns.empty:
        return {}
    utc_index = returns.index.tz_convert("UTC").tz_localize(None)
    values = pd.Series(returns.to_numpy(dtype=float), index=utc_index)
    monthly = values.groupby(values.index.to_period("M")).apply(lambda group: (1.0 + group).prod() - 1.0)
    return {str(key): float(value) for key, value in monthly.items()}


def compute_btcusd_strategy_metrics(
    accounting: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    periods_per_year: int = 17_520,
    evaluation_scope: str,
) -> dict[str, Any]:
    """Build the complete, explicitly scoped rule-based strategy summary contract."""
    returns = accounting["net_return"].astype(float)
    gross_returns = accounting["gross_return"].astype(float)
    costs = accounting["cost_return"].astype(float)
    equity = accounting["equity"].astype(float)
    daily = _daily_returns(returns)
    annual_vol = annualized_volatility(returns, periods_per_year)
    ann_return = annualized_return(returns, periods_per_year)
    gross_compound = float((1.0 + gross_returns).prod() - 1.0) if len(accounting) else 0.0
    net_compound = float((1.0 + returns).prod() - 1.0) if len(accounting) else 0.0
    completed = trades.loc[trades["completed"].astype(bool)] if not trades.empty else trades
    trade_returns = completed["net_return"].astype(float) if not completed.empty else pd.Series(dtype=float)
    trade_pf = _finite_or_none(profit_factor(trade_returns)) if len(trade_returns) else None
    bar_pf = _finite_or_none(profit_factor(returns)) if len(returns) else None
    conventional_sharpe = sharpe_ratio(returns, periods_per_year)
    total_cost_cash = float(accounting["cost"].sum()) if len(accounting) else 0.0
    gross_pnl_cash = float(accounting["gross_pnl"].sum()) if len(accounting) else 0.0
    metrics: dict[str, Any] = {
        "cumulative_return": net_compound,
        "annualized_return": ann_return,
        "annualized_vol": annual_vol,
        "sharpe": conventional_sharpe,
        "sortino": sortino_ratio(returns, periods_per_year),
        "calmar": calmar_ratio(returns, periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "profit_factor": bar_pf,
        "hit_rate": hit_rate(returns),
        "annualization_mode": "fixed_periods",
        "metric_scope": "rule_based_realized_next_open_to_next_open",
        "avg_turnover": float(accounting["turnover"].mean()) if len(accounting) else 0.0,
        "total_turnover": float(accounting["turnover"].sum()) if len(accounting) else 0.0,
        "gross_pnl": gross_pnl_cash,
        "net_pnl": float(equity.iloc[-1] - 1.0) if len(equity) else 0.0,
        "total_cost": total_cost_cash,
        "cost_drag": gross_compound - net_compound,
        "cost_to_gross_pnl": _safe_ratio(total_cost_cash, gross_pnl_cash),
        "gross_return_sum": float(gross_returns.sum()),
        "net_return_sum": float(returns.sum()),
        "cost_return_sum": float(costs.sum()),
        "conventional_sharpe": conventional_sharpe,
        "return_over_vol_sharpe": _safe_ratio(ann_return, annual_vol),
        "sharpe_legacy_alias": conventional_sharpe,
        "bar_return_profit_factor": bar_pf,
        "profit_factor_scope": "net_bar_returns",
        "evaluation_scope": evaluation_scope,
        "evaluation_start": accounting.index.min().isoformat() if len(accounting) else None,
        "evaluation_end": accounting.index.max().isoformat() if len(accounting) else None,
        "evaluation_rows": int(len(accounting)),
        "trade_count": int(len(trades)),
        "completed_trade_count": int(len(completed)),
        "win_rate": float((trade_returns > 0.0).mean()) if len(trade_returns) else None,
        "trade_return_profit_factor": trade_pf,
        "trade_r_profit_factor": None,
        "trade_profit_factor": trade_pf,
        "entry_trade_cost": float(trades["entry_cost"].sum()) if len(trades) else 0.0,
        "exit_trade_cost": float(trades["exit_cost"].sum()) if len(trades) else 0.0,
        "holding_trade_cost": float(trades["holding_cost"].sum()) if len(trades) else 0.0,
        "total_trade_cost": float(trades["total_cost"].sum()) if len(trades) else 0.0,
        "position_transition_count": int(accounting["turnover"].gt(0.0).sum()),
        "turnover_event_count": int(accounting["turnover"].gt(0.0).sum()),
        "exposed_bar_count": int(accounting["position"].ne(0.0).sum()),
        "bar_return_profit_factor_scope": "net_returns_all_evaluation_bars",
        "trade_return_profit_factor_scope": "completed_directional_position_segments",
        "trade_r_profit_factor_scope": "not_applicable_no_trade_r_definition",
        "trade_profit_factor_scope": "alias_of_trade_return_profit_factor",
        "worst_daily_return": float(daily.min()) if len(daily) else None,
        "best_daily_return": float(daily.max()) if len(daily) else None,
        "daily_return_mean": float(daily.mean()) if len(daily) else None,
        "daily_return_std": float(daily.std(ddof=1)) if len(daily) > 1 else None,
        "positive_day_rate": float(daily.gt(0.0).mean()) if len(daily) else None,
        "monthly_returns": _monthly_returns(returns),
    }
    return metrics


@dataclass(frozen=True)
class FTMOPhaseResult:
    status: str
    start_timestamp: pd.Timestamp | None
    completion_timestamp: pd.Timestamp | None
    next_phase_timestamp: pd.Timestamp | None
    calendar_days: float | None
    trading_days: int
    minimum_equity: float
    worst_daily_loss: float
    worst_intrabar_loss: float
    peak_drawdown: float
    ending_equity: float
    bars_evaluated: int
    failure_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "start_timestamp": self.start_timestamp,
            "completion_timestamp": self.completion_timestamp,
            "next_phase_timestamp": self.next_phase_timestamp,
            "calendar_days": self.calendar_days,
            "trading_days": self.trading_days,
            "minimum_equity": self.minimum_equity,
            "worst_daily_loss": self.worst_daily_loss,
            "worst_intrabar_loss": self.worst_intrabar_loss,
            "peak_drawdown": self.peak_drawdown,
            "ending_equity": self.ending_equity,
            "bars_evaluated": self.bars_evaluated,
            "failure_reason": self.failure_reason,
        }


def simulate_ftmo_phase(
    frame: pd.DataFrame,
    *,
    profit_target: float,
    target_volatility: float,
    max_leverage: float,
    maximum_daily_loss: float = 0.05,
    maximum_total_loss: float = 0.10,
    minimum_trading_days: int = 4,
    cost_per_turnover: float = 0.0004,
    rebalance_bars: int = 48,
    ensemble_col: str = "dual_trend_score",
    volatility_col: str = "dual_volatility_ann_336",
    execution_return_col: str = "dual_execution_return",
    adverse_long_col: str = "dual_adverse_long_return",
    adverse_short_col: str = "dual_adverse_short_price_return",
) -> FTMOPhaseResult:
    """Simulate one normalized FTMO research phase and fail on close or adverse marks."""
    required = {
        ensemble_col,
        volatility_col,
        execution_return_col,
        adverse_long_col,
        adverse_short_col,
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"Missing FTMO phase inputs: {missing}.")
    if frame.empty:
        return FTMOPhaseResult(
            "incomplete", None, None, None, None, 0, 1.0, 0.0, 0.0, 0.0, 1.0, 0, None
        )
    if str(frame.index.tz) != "UTC":
        raise ValueError("FTMO daily reset requires a UTC index.")

    positioned = btcusd_dual_trend_ensemble_signal(
        frame,
        ensemble_col=ensemble_col,
        volatility_col=volatility_col,
        target_volatility=target_volatility,
        max_leverage=max_leverage,
        rebalance_bars=rebalance_bars,
        allow_short=True,
        signal_col="_ftmo_position",
    )
    start_timestamp = pd.Timestamp(positioned.index[0])
    equity = 1.0
    peak = 1.0
    minimum_equity = 1.0
    worst_daily_loss = 0.0
    worst_intrabar_loss = 0.0
    peak_drawdown = 0.0
    current_day: object | None = None
    daily_start_equity = 1.0
    trading_dates: set[object] = set()
    previous_position = 0.0
    status = "incomplete"
    completion_timestamp: pd.Timestamp | None = None
    next_phase_timestamp: pd.Timestamp | None = None
    failure_reason: str | None = None
    bars_evaluated = 0

    for offset, (timestamp, row) in enumerate(positioned.iterrows()):
        timestamp = pd.Timestamp(timestamp)
        day = timestamp.tz_convert("UTC").date()
        if day != current_day:
            current_day = day
            daily_start_equity = equity

        position = float(row["_ftmo_position"])
        turnover = abs(position - previous_position)
        entry_cost = float(cost_per_turnover * turnover)
        execution_return = float(row[execution_return_col]) if pd.notna(row[execution_return_col]) else np.nan
        if position != 0.0 and not np.isfinite(execution_return):
            raise ValueError(f"Missing FTMO execution return while exposed at {timestamp}.")
        if not np.isfinite(execution_return):
            execution_return = 0.0
        gross_return = position * execution_return

        if position > 0.0:
            adverse_position_return = position * float(row[adverse_long_col])
        elif position < 0.0:
            adverse_position_return = position * float(row[adverse_short_col])
        else:
            adverse_position_return = 0.0
        if not np.isfinite(adverse_position_return):
            if position != 0.0:
                raise ValueError(f"Missing FTMO adverse excursion while exposed at {timestamp}.")
            adverse_position_return = 0.0

        equity_before = equity
        intrabar_equity = equity_before * (1.0 + adverse_position_return - entry_cost)
        close_equity = equity_before * (1.0 + gross_return - entry_cost)
        bars_evaluated += 1
        if position != 0.0:
            trading_dates.add(day)

        daily_close_loss = close_equity / daily_start_equity - 1.0
        daily_intrabar_loss = intrabar_equity / daily_start_equity - 1.0
        worst_daily_loss = min(worst_daily_loss, daily_close_loss)
        worst_intrabar_loss = min(worst_intrabar_loss, daily_intrabar_loss)
        minimum_equity = min(minimum_equity, close_equity, intrabar_equity)
        peak_drawdown = min(
            peak_drawdown,
            close_equity / peak - 1.0,
            intrabar_equity / peak - 1.0,
        )

        daily_breach = min(daily_close_loss, daily_intrabar_loss) <= -float(maximum_daily_loss)
        total_breach = min(close_equity, intrabar_equity) <= 1.0 - float(maximum_total_loss)
        equity = close_equity
        peak = max(peak, equity)
        previous_position = position

        if daily_breach or total_breach:
            liquidation_cost = float(cost_per_turnover * abs(position))
            equity *= max(1.0 - liquidation_cost, 0.0)
            minimum_equity = min(minimum_equity, equity)
            status = "failed"
            failure_reason = "maximum_daily_loss" if daily_breach else "maximum_total_loss"
            completion_timestamp = timestamp
            previous_position = 0.0
            break

        if len(trading_dates) >= int(minimum_trading_days):
            liquidation_cost = float(cost_per_turnover * abs(position))
            equity_after_close = equity_before * (
                1.0 + gross_return - entry_cost - liquidation_cost
            )
            if equity_after_close >= 1.0 + float(profit_target):
                equity = equity_after_close
                minimum_equity = min(minimum_equity, equity)
                status = "passed"
                completion_timestamp = timestamp
                previous_position = 0.0
                if offset + 1 < len(positioned):
                    next_phase_timestamp = pd.Timestamp(positioned.index[offset + 1])
                break

    if status == "incomplete" and previous_position != 0.0:
        equity *= max(1.0 - float(cost_per_turnover * abs(previous_position)), 0.0)
        minimum_equity = min(minimum_equity, equity)
    end_timestamp = completion_timestamp or pd.Timestamp(positioned.index[min(bars_evaluated, len(positioned)) - 1])
    calendar_days = (end_timestamp - start_timestamp).total_seconds() / 86_400.0
    return FTMOPhaseResult(
        status=status,
        start_timestamp=start_timestamp,
        completion_timestamp=completion_timestamp,
        next_phase_timestamp=next_phase_timestamp,
        calendar_days=float(calendar_days),
        trading_days=len(trading_dates),
        minimum_equity=float(minimum_equity),
        worst_daily_loss=float(worst_daily_loss),
        worst_intrabar_loss=float(worst_intrabar_loss),
        peak_drawdown=float(peak_drawdown),
        ending_equity=float(equity),
        bars_evaluated=int(bars_evaluated),
        failure_reason=failure_reason,
    )


def simulate_ftmo_two_step(
    frame: pd.DataFrame,
    *,
    start: str | pd.Timestamp,
    end_exclusive: str | pd.Timestamp,
    phase1_profit_target: float = 0.10,
    phase1_target_volatility: float = 0.22,
    phase1_max_leverage: float = 1.50,
    phase2_profit_target: float = 0.05,
    phase2_target_volatility: float = 0.16,
    phase2_max_leverage: float = 1.20,
    maximum_daily_loss: float = 0.05,
    maximum_total_loss: float = 0.10,
    minimum_trading_days: int = 4,
    cost_per_turnover: float = 0.0004,
    rebalance_bars: int = 48,
) -> dict[str, Any]:
    """Run independent normalized Phase 1 and Phase 2 ledgers."""
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end_exclusive)
    start_ts = start_ts.tz_localize("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
    end_ts = end_ts.tz_localize("UTC") if end_ts.tzinfo is None else end_ts.tz_convert("UTC")
    evaluation = frame.loc[(frame.index >= start_ts) & (frame.index < end_ts)]
    phase1 = simulate_ftmo_phase(
        evaluation,
        profit_target=phase1_profit_target,
        target_volatility=phase1_target_volatility,
        max_leverage=phase1_max_leverage,
        maximum_daily_loss=maximum_daily_loss,
        maximum_total_loss=maximum_total_loss,
        minimum_trading_days=minimum_trading_days,
        cost_per_turnover=cost_per_turnover,
        rebalance_bars=rebalance_bars,
    )
    phase2: FTMOPhaseResult | None = None
    if phase1.status == "failed":
        overall = "failed_phase1"
    elif phase1.status == "incomplete":
        overall = "incomplete_phase1"
    else:
        phase2_frame = evaluation
        if phase1.next_phase_timestamp is not None:
            phase2_frame = evaluation.loc[evaluation.index >= phase1.next_phase_timestamp]
        else:
            phase2_frame = evaluation.iloc[0:0]
        phase2 = simulate_ftmo_phase(
            phase2_frame,
            profit_target=phase2_profit_target,
            target_volatility=phase2_target_volatility,
            max_leverage=phase2_max_leverage,
            maximum_daily_loss=maximum_daily_loss,
            maximum_total_loss=maximum_total_loss,
            minimum_trading_days=minimum_trading_days,
            cost_per_turnover=cost_per_turnover,
            rebalance_bars=rebalance_bars,
        )
        overall = {
            "passed": "passed",
            "failed": "failed_phase2",
            "incomplete": "incomplete_phase2",
        }[phase2.status]

    completion = phase2.completion_timestamp if phase2 is not None else phase1.completion_timestamp
    end_for_days = completion or (pd.Timestamp(evaluation.index[-1]) if len(evaluation) else start_ts)
    return {
        "start": start_ts,
        "status": overall,
        "completion_timestamp": completion,
        "total_calendar_days": float((end_for_days - start_ts).total_seconds() / 86_400.0),
        "phase1": phase1.to_dict(),
        "phase2": phase2.to_dict() if phase2 is not None else None,
    }


def flatten_ftmo_result(result: dict[str, Any]) -> dict[str, Any]:
    phase1 = dict(result["phase1"] or {})
    phase2 = dict(result.get("phase2") or {})
    row: dict[str, Any] = {
        "start": result["start"],
        "status": result["status"],
        "completion_timestamp": result.get("completion_timestamp"),
        "total_calendar_days": result["total_calendar_days"],
    }
    for prefix, phase in (("phase1", phase1), ("phase2", phase2)):
        for key in (
            "status",
            "calendar_days",
            "trading_days",
            "minimum_equity",
            "worst_daily_loss",
            "worst_intrabar_loss",
            "peak_drawdown",
            "ending_equity",
            "completion_timestamp",
            "failure_reason",
        ):
            row[f"{prefix}_{key}"] = phase.get(key)
    return row


__all__ = [
    "FTMOPhaseResult",
    "compute_btcusd_strategy_metrics",
    "flatten_ftmo_result",
    "simulate_ftmo_phase",
    "simulate_ftmo_two_step",
]
