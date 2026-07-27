from __future__ import annotations

"""Extended, deterministic reporting for the funding-carry research harness."""

from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.evaluation.metrics import calendar_daily_returns, equity_curve_from_returns


def _finite_or_none(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _compound(values: pd.Series) -> float:
    clean = values.dropna().astype(float)
    return float((1.0 + clean).prod() - 1.0) if not clean.empty else 0.0


def calendar_return_tables(returns: pd.Series) -> dict[str, pd.DataFrame]:
    daily, _ = calendar_daily_returns(returns)
    if daily.empty:
        return {
            name: pd.DataFrame(columns=["return"])
            for name in ("daily", "weekly", "monthly", "yearly")
        }
    tables: dict[str, pd.DataFrame] = {"daily": daily.to_frame("return")}
    for name, frequency in (("weekly", "W-SUN"), ("monthly", "ME"), ("yearly", "YE")):
        values = daily.resample(frequency).apply(_compound).astype(float)
        tables[name] = values.to_frame("return")
    return tables


def _distribution_metrics(returns: pd.Series) -> dict[str, float | None]:
    values = returns.dropna().astype(float)
    if values.empty:
        return {
            "count": 0.0,
            "mean": None,
            "median": None,
            "standard_deviation": None,
            "skewness": None,
            "excess_kurtosis": None,
            "minimum": None,
            "maximum": None,
            "positive_fraction": None,
            "zero_fraction": None,
        }
    return {
        "count": float(len(values)),
        "mean": _finite_or_none(values.mean()),
        "median": _finite_or_none(values.median()),
        "standard_deviation": _finite_or_none(values.std(ddof=1)),
        "skewness": _finite_or_none(values.skew()),
        "excess_kurtosis": _finite_or_none(values.kurt()),
        "minimum": _finite_or_none(values.min()),
        "maximum": _finite_or_none(values.max()),
        "positive_fraction": float((values > 0.0).mean()),
        "zero_fraction": float((values == 0.0).mean()),
    }


def _risk_tail_metrics(
    returns: pd.Series,
    *,
    confidence_levels: tuple[float, ...],
) -> dict[str, Any]:
    values = returns.dropna().astype(float)
    if values.empty:
        return {"distribution": _distribution_metrics(values), "var_cvar": {}}
    positive = float(values.clip(lower=0.0).sum())
    negative = float((-values.clip(upper=0.0)).sum())
    quantile_95 = float(values.quantile(0.95))
    quantile_05 = float(values.quantile(0.05))
    downside = np.minimum(values.to_numpy(dtype=float), 0.0)
    var_cvar: dict[str, dict[str, float | None]] = {}
    for confidence in confidence_levels:
        cutoff = float(values.quantile(1.0 - confidence))
        tail = values.loc[values <= cutoff]
        var_cvar[f"{confidence:.4f}"] = {
            "historical_var_loss": _finite_or_none(-cutoff),
            "historical_cvar_expected_shortfall": _finite_or_none(-tail.mean()),
            "tail_observations": float(len(tail)),
        }
    return {
        "distribution": _distribution_metrics(values),
        "downside_deviation_unannualized": _finite_or_none(np.sqrt(np.mean(downside**2))),
        "gain_to_pain_ratio": _finite_or_none(positive / negative) if negative > 0.0 else None,
        "omega_ratio_zero_threshold": _finite_or_none(positive / negative)
        if negative > 0.0
        else None,
        "tail_ratio_95_to_05": _finite_or_none(quantile_95 / abs(quantile_05))
        if quantile_05 < 0.0
        else None,
        "var_cvar": var_cvar,
    }


def _drawdown_metrics(returns: pd.Series) -> dict[str, Any]:
    values = returns.dropna().astype(float).sort_index()
    if values.empty:
        return {}
    equity = equity_curve_from_returns(values)
    running_peak = equity.cummax().clip(lower=1.0)
    drawdown = equity / running_peak - 1.0
    trough_time = drawdown.idxmin()
    peak_candidates = equity.loc[:trough_time]
    peak_time = peak_candidates.idxmax() if not peak_candidates.empty else None
    recovery_time = None
    if peak_time is not None:
        peak_equity = max(1.0, float(equity.loc[peak_time]))
        recovered = equity.loc[trough_time:].loc[equity.loc[trough_time:] >= peak_equity]
        if not recovered.empty:
            recovery_time = recovered.index[0]

    underwater = drawdown < 0.0
    groups = (~underwater).cumsum()
    maximum_underwater_events = int(underwater.groupby(groups).sum().max()) if underwater.any() else 0
    maximum_underwater_days = 0.0
    if underwater.any():
        for _, group in drawdown.loc[underwater].groupby(groups.loc[underwater]):
            maximum_underwater_days = max(
                maximum_underwater_days,
                float((group.index.max() - group.index.min()).total_seconds() / 86_400.0),
            )
    return {
        "maximum_drawdown": float(drawdown.min()),
        "average_drawdown": float(drawdown.loc[drawdown < 0.0].mean())
        if (drawdown < 0.0).any()
        else 0.0,
        "ulcer_index": float(np.sqrt(np.mean(np.square(drawdown.to_numpy(dtype=float))))),
        "maximum_underwater_events": float(maximum_underwater_events),
        "maximum_underwater_days": maximum_underwater_days,
        "peak_timestamp": peak_time.isoformat() if peak_time is not None else None,
        "trough_timestamp": trough_time.isoformat(),
        "recovery_timestamp": recovery_time.isoformat() if recovery_time is not None else None,
        "recovered": recovery_time is not None,
        "peak_to_trough_days": float((trough_time - peak_time).total_seconds() / 86_400.0)
        if peak_time is not None
        else None,
        "trough_to_recovery_days": float(
            (recovery_time - trough_time).total_seconds() / 86_400.0
        )
        if recovery_time is not None
        else None,
    }


def _calendar_metrics(tables: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, table in tables.items():
        returns = table["return"].dropna().astype(float)
        output[name] = {
            "count": float(len(returns)),
            "compounded_return": _compound(returns),
            "mean_return": _finite_or_none(returns.mean()),
            "median_return": _finite_or_none(returns.median()),
            "standard_deviation": _finite_or_none(returns.std(ddof=1)),
            "positive_fraction": float((returns > 0.0).mean()) if not returns.empty else None,
            "best_return": _finite_or_none(returns.max()),
            "worst_return": _finite_or_none(returns.min()),
            "best_period": returns.idxmax().isoformat() if not returns.empty else None,
            "worst_period": returns.idxmin().isoformat() if not returns.empty else None,
        }
    output["year_by_year_returns"] = {
        str(timestamp.year): float(value)
        for timestamp, value in tables["yearly"]["return"].items()
    }
    return output


def rolling_metric_table(
    returns: pd.Series,
    *,
    windows_days: tuple[int, ...],
) -> pd.DataFrame:
    daily = calendar_return_tables(returns)["daily"]["return"]
    output = pd.DataFrame(index=daily.index)
    for window in windows_days:
        minimum = min(window, max(2, window // 3))
        rolling = daily.rolling(window, min_periods=minimum)
        output[f"return_{window}d"] = rolling.apply(lambda values: np.prod(1.0 + values) - 1.0)
        output[f"annualized_volatility_{window}d"] = rolling.std(ddof=1) * np.sqrt(365.25)
        standard_deviation = rolling.std(ddof=1)
        output[f"sharpe_{window}d"] = (
            rolling.mean() / standard_deviation.replace(0.0, np.nan) * np.sqrt(365.25)
        )
        output[f"max_drawdown_{window}d"] = rolling.apply(
            lambda values: float(
                np.min(
                    np.cumprod(1.0 + values)
                    / np.maximum.accumulate(np.maximum(1.0, np.cumprod(1.0 + values)))
                    - 1.0
                )
            )
        )
    return output


def _rolling_summary(table: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for column in table.columns:
        values = table[column].dropna().astype(float)
        output[column] = {
            "minimum": _finite_or_none(values.min()),
            "median": _finite_or_none(values.median()),
            "maximum": _finite_or_none(values.max()),
            "latest": _finite_or_none(values.iloc[-1]) if not values.empty else None,
            "observations": float(len(values)),
        }
    return output


def moving_block_bootstrap_metrics(
    returns: pd.Series,
    *,
    samples: int,
    block_length_days: int,
    confidence_level: float,
    random_seed: int,
) -> dict[str, Any]:
    daily = calendar_return_tables(returns)["daily"]["return"].to_numpy(dtype=float)
    count = len(daily)
    if count < 2:
        return {"available": False, "reason": "fewer_than_two_daily_observations"}
    block_length = min(int(block_length_days), count)
    blocks_needed = int(np.ceil(count / block_length))
    rng = np.random.default_rng(random_seed)
    annualized_returns = np.empty(samples, dtype=float)
    sharpes = np.empty(samples, dtype=float)
    for sample in range(samples):
        starts = rng.integers(0, count, size=blocks_needed)
        indices = np.concatenate(
            [(np.arange(start, start + block_length) % count) for start in starts]
        )[:count]
        draw = daily[indices]
        cumulative = float(np.prod(1.0 + draw))
        annualized_returns[sample] = cumulative ** (365.25 / count) - 1.0
        volatility = float(np.std(draw, ddof=1))
        sharpes[sample] = (
            float(np.mean(draw) / volatility * np.sqrt(365.25)) if volatility > 0.0 else 0.0
        )
    alpha = (1.0 - confidence_level) / 2.0
    lower, upper = alpha, 1.0 - alpha
    return {
        "available": True,
        "method": "circular_moving_block_bootstrap_on_calendar_daily_returns",
        "samples": float(samples),
        "block_length_days": float(block_length),
        "confidence_level": confidence_level,
        "random_seed": float(random_seed),
        "annualized_return": {
            "median": float(np.median(annualized_returns)),
            "confidence_interval_lower": float(np.quantile(annualized_returns, lower)),
            "confidence_interval_upper": float(np.quantile(annualized_returns, upper)),
            "probability_positive": float(np.mean(annualized_returns > 0.0)),
        },
        "sharpe": {
            "median": float(np.median(sharpes)),
            "confidence_interval_lower": float(np.quantile(sharpes, lower)),
            "confidence_interval_upper": float(np.quantile(sharpes, upper)),
            "probability_positive": float(np.mean(sharpes > 0.0)),
        },
    }


def extract_trade_ledger(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"position_for_interval", "position_after_event", "equity_before", "equity"}
    if not required.issubset(frame.columns):
        return pd.DataFrame()
    entries = frame.index[
        (frame["position_for_interval"] == 0) & (frame["position_after_event"] == 1)
    ]
    exits = frame.index[
        (frame["position_for_interval"] == 1) & (frame["position_after_event"] == 0)
    ]
    rows: list[dict[str, Any]] = []
    exit_cursor = 0
    exit_values = list(exits)
    for trade_id, entry_time in enumerate(entries, start=1):
        while exit_cursor < len(exit_values) and exit_values[exit_cursor] <= entry_time:
            exit_cursor += 1
        if exit_cursor >= len(exit_values):
            break
        exit_time = exit_values[exit_cursor]
        exit_cursor += 1
        trade = frame.loc[entry_time:exit_time]
        entry_equity = float(frame.loc[entry_time, "equity_before"])
        exit_equity = float(frame.loc[exit_time, "equity"])
        held = trade.loc[trade["position_for_interval"] == 1]
        row = {
            "trade_id": trade_id,
            "entry_timestamp": entry_time,
            "exit_timestamp": exit_time,
            "holding_events": int((trade["position_for_interval"] == 1).sum()),
            "holding_hours": float((exit_time - entry_time).total_seconds() / 3_600.0),
            "entry_spot_price": float(frame.loc[entry_time, "spot_close"]),
            "exit_spot_price": float(frame.loc[exit_time, "spot_close"]),
            "entry_perpetual_price": float(frame.loc[entry_time, "perpetual_close"]),
            "exit_perpetual_price": float(frame.loc[exit_time, "perpetual_close"]),
            "entry_basis_bps": float(frame.loc[entry_time, "basis_bps"]),
            "exit_basis_bps": float(frame.loc[exit_time, "basis_bps"]),
            "entry_equity": entry_equity,
            "exit_equity": exit_equity,
            "net_return": float(exit_equity / entry_equity - 1.0),
            "gross_return_sum": float(trade["gross_return"].sum()),
            "funding_return_sum": float(trade["funding_return_component"].sum()),
            "basis_return_sum": float(trade["basis_return_component"].sum()),
            "fee_cost_sum": float(trade["fee_cost"].sum()),
            "slippage_cost_sum": float(trade["slippage_cost"].sum()),
            "financing_cost_sum": float(trade["financing_cost"].sum()),
            "transaction_cost_sum": float(trade["transaction_cost"].sum()),
            "minimum_event_return": float(trade["net_return"].min()),
            "maximum_event_return": float(trade["net_return"].max()),
            "maximum_gross_leverage": float(held["gross_leverage"].max())
            if not held.empty
            else 0.0,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _maximum_streak(flags: pd.Series) -> int:
    if flags.empty:
        return 0
    groups = (flags != flags.shift()).cumsum()
    counts = flags.groupby(groups).agg(["first", "size"])
    selected = counts.loc[counts["first"].astype(bool), "size"]
    return int(selected.max()) if not selected.empty else 0


def _trade_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {"trade_count": 0.0}
    returns = trades["net_return"].astype(float)
    winners = returns > 0.0
    losers = returns < 0.0
    gross_profit = float(returns.loc[winners].sum())
    gross_loss = float((-returns.loc[losers]).sum())
    average_win = float(returns.loc[winners].mean()) if winners.any() else 0.0
    average_loss = float(returns.loc[losers].mean()) if losers.any() else 0.0
    return {
        "trade_count": float(len(trades)),
        "winning_trades": float(winners.sum()),
        "losing_trades": float(losers.sum()),
        "flat_trades": float((returns == 0.0).sum()),
        "win_rate": float(winners.mean()),
        "average_trade_return": float(returns.mean()),
        "median_trade_return": float(returns.median()),
        "trade_return_standard_deviation": _finite_or_none(returns.std(ddof=1)),
        "best_trade_return": float(returns.max()),
        "worst_trade_return": float(returns.min()),
        "average_win": average_win,
        "average_loss": average_loss,
        "payoff_ratio": _finite_or_none(average_win / abs(average_loss))
        if average_loss < 0.0
        else None,
        "profit_factor": _finite_or_none(gross_profit / gross_loss)
        if gross_loss > 0.0
        else None,
        "expectancy": float(returns.mean()),
        "maximum_consecutive_wins": float(_maximum_streak(winners)),
        "maximum_consecutive_losses": float(_maximum_streak(losers)),
        "average_holding_events": float(trades["holding_events"].mean()),
        "median_holding_events": float(trades["holding_events"].median()),
        "maximum_holding_events": float(trades["holding_events"].max()),
        "average_holding_hours": float(trades["holding_hours"].mean()),
        "median_holding_hours": float(trades["holding_hours"].median()),
        "maximum_holding_hours": float(trades["holding_hours"].max()),
        "average_funding_return": float(trades["funding_return_sum"].mean()),
        "average_basis_return": float(trades["basis_return_sum"].mean()),
        "average_total_cost": float(
            (
                trades["transaction_cost_sum"] + trades["financing_cost_sum"]
            ).mean()
        ),
    }


def _funding_basis_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    active = frame.loc[frame.get("position_for_interval", 0) > 0.0]
    if active.empty:
        return {"active_funding_events": 0.0}
    funding_rates = active["funding_rate"] if "funding_rate" in active else pd.Series(dtype=float)
    funding_return = float(active["funding_return_component"].sum())
    basis_return = float(active["basis_return_component"].sum())
    return {
        "active_funding_events": float(len(active)),
        "funding_return_sum": funding_return,
        "basis_return_sum": basis_return,
        "spot_return_component_sum": float(active["spot_return_component"].sum()),
        "perpetual_return_component_sum": float(active["perpetual_return_component"].sum()),
        "gross_component_return_sum": funding_return + basis_return,
        "funding_share_of_positive_gross_components": _finite_or_none(
            funding_return / (funding_return + basis_return)
        )
        if funding_return + basis_return > 0.0
        else None,
        "average_realized_funding_rate_while_active": _finite_or_none(funding_rates.mean()),
        "median_realized_funding_rate_while_active": _finite_or_none(funding_rates.median()),
        "minimum_realized_funding_rate_while_active": _finite_or_none(funding_rates.min()),
        "maximum_realized_funding_rate_while_active": _finite_or_none(funding_rates.max()),
        "positive_funding_fraction_while_active": float((funding_rates > 0.0).mean()),
        "negative_funding_events_while_active": float((funding_rates < 0.0).sum()),
        "average_basis_bps_while_active": _finite_or_none(active["basis_bps"].mean()),
        "median_basis_bps_while_active": _finite_or_none(active["basis_bps"].median()),
        "minimum_basis_bps_while_active": _finite_or_none(active["basis_bps"].min()),
        "maximum_basis_bps_while_active": _finite_or_none(active["basis_bps"].max()),
    }


def _cost_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    gross_sum = float(frame["gross_return"].sum())
    fee = float(frame["fee_cost"].sum())
    slippage = float(frame["slippage_cost"].sum())
    financing = float(frame["financing_cost"].sum())
    total = fee + slippage + financing
    return {
        "fee_cost_sum": fee,
        "slippage_cost_sum": slippage,
        "transaction_cost_sum": fee + slippage,
        "financing_cost_sum": financing,
        "all_costs_sum": total,
        "fees_fraction_of_all_costs": fee / total if total > 0.0 else 0.0,
        "slippage_fraction_of_all_costs": slippage / total if total > 0.0 else 0.0,
        "financing_fraction_of_all_costs": financing / total if total > 0.0 else 0.0,
        "cost_to_absolute_gross_return_sum": total / abs(gross_sum)
        if abs(gross_sum) > 0.0
        else None,
    }


def _exposure_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    active = frame.loc[frame.get("position_for_interval", 0) > 0.0]
    return {
        "exposure_fraction": float((frame.get("position_for_interval", 0) > 0.0).mean()),
        "average_gross_leverage_all_events": _finite_or_none(frame["gross_leverage"].mean()),
        "average_gross_leverage_while_active": _finite_or_none(active["gross_leverage"].mean()),
        "median_gross_leverage_while_active": _finite_or_none(active["gross_leverage"].median()),
        "maximum_gross_leverage": _finite_or_none(frame["gross_leverage"].max()),
        "average_net_mark_notional_ratio_while_active": _finite_or_none(
            active["net_mark_notional_ratio"].mean()
        ),
        "maximum_absolute_net_mark_notional_ratio": _finite_or_none(
            frame["net_mark_notional_ratio"].abs().max()
        ),
    }


def _data_quality_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    differences = frame.index.to_series().diff().dropna().dt.total_seconds() / 3_600.0
    result: dict[str, Any] = {
        "timestamp_start": frame.index.min().isoformat(),
        "timestamp_end": frame.index.max().isoformat(),
        "observations": float(len(frame)),
        "elapsed_calendar_days": float(
            (frame.index.max() - frame.index.min()).total_seconds() / 86_400.0
        ),
        "median_event_interval_hours": _finite_or_none(differences.median()),
        "maximum_event_interval_hours": _finite_or_none(differences.max()),
        "intervals_longer_than_12_hours": float((differences > 12.0).sum()),
    }
    if "execution_price_available" in frame:
        result["execution_price_available_fraction"] = float(
            frame["execution_price_available"].astype(float).mean()
        )
        result["execution_unavailable_events"] = float(
            (frame["execution_price_available"].astype(float) < 1.0).sum()
        )
    for prefix in ("spot", "perpetual"):
        column = f"{prefix}_price_age_seconds"
        if column in frame:
            result[f"{prefix}_median_price_age_seconds"] = _finite_or_none(frame[column].median())
            result[f"{prefix}_maximum_price_age_seconds"] = _finite_or_none(frame[column].max())
    return result


def _benchmark_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    if "spot_return" not in frame:
        return {}
    aligned = frame[["net_return", "spot_return"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(aligned) < 2:
        return {}
    benchmark_variance = float(aligned["spot_return"].var(ddof=1))
    covariance = float(aligned["net_return"].cov(aligned["spot_return"]))
    return {
        "spot_return_correlation": _finite_or_none(
            aligned["net_return"].corr(aligned["spot_return"])
        ),
        "spot_beta": covariance / benchmark_variance if benchmark_variance > 0.0 else None,
    }


def build_extended_metrics(
    frame: pd.DataFrame,
    *,
    base_metrics: Mapping[str, Any],
    reporting: Any,
    include_trades: bool,
) -> dict[str, Any]:
    metrics = dict(base_metrics)
    returns = frame["net_return"]
    tables = calendar_return_tables(returns)
    if reporting.extended_performance_metrics:
        daily = tables["daily"]["return"]
        metrics["extended_performance"] = {
            "arithmetic_annualized_daily_return": float(daily.mean() * 365.25),
            "geometric_mean_daily_return": float((1.0 + daily).prod() ** (1.0 / len(daily)) - 1.0),
            "return_to_volatility_ratio": _finite_or_none(
                float(metrics["annualized_return"]) / float(metrics["annualized_vol"])
            )
            if float(metrics["annualized_vol"]) > 0.0
            else None,
            "return_to_max_drawdown_ratio": _finite_or_none(
                float(metrics["annualized_return"]) / abs(float(metrics["max_drawdown"]))
            )
            if float(metrics["max_drawdown"]) < 0.0
            else None,
            "benchmark_exposure": _benchmark_metrics(frame),
        }
    if reporting.risk_and_tail_metrics:
        metrics["risk_and_tail"] = {
            "event_returns": _risk_tail_metrics(
                returns,
                confidence_levels=reporting.var_confidence_levels,
            ),
            "calendar_daily_returns": _risk_tail_metrics(
                tables["daily"]["return"],
                confidence_levels=reporting.var_confidence_levels,
            ),
        }
    if reporting.drawdown_metrics:
        metrics["drawdown_analysis"] = _drawdown_metrics(returns)
    if reporting.trade_metrics and include_trades:
        metrics["trade_analysis"] = _trade_metrics(extract_trade_ledger(frame))
    if reporting.funding_and_basis_attribution:
        metrics["funding_and_basis_attribution"] = _funding_basis_metrics(frame)
    if reporting.cost_attribution:
        metrics["detailed_cost_attribution"] = _cost_metrics(frame)
    if reporting.exposure_and_leverage_metrics:
        metrics["exposure_and_leverage"] = _exposure_metrics(frame)
    if reporting.calendar_metrics:
        metrics["calendar_analysis"] = _calendar_metrics(tables)
    if reporting.rolling_metrics:
        metrics["rolling_analysis"] = _rolling_summary(
            rolling_metric_table(returns, windows_days=reporting.rolling_windows_days)
        )
    if reporting.data_quality_metrics:
        metrics["data_quality"] = _data_quality_metrics(frame)
    if reporting.bootstrap.enabled:
        metrics["bootstrap_uncertainty"] = moving_block_bootstrap_metrics(
            returns,
            samples=reporting.bootstrap.samples,
            block_length_days=reporting.bootstrap.block_length_days,
            confidence_level=reporting.bootstrap.confidence_level,
            random_seed=reporting.bootstrap.random_seed,
        )
    return metrics


def build_reporting_tables(
    frame: pd.DataFrame,
    *,
    reporting: Any,
    include_trades: bool,
) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    if reporting.write_trade_ledger_csv and include_trades:
        tables["trades"] = extract_trade_ledger(frame)
    if reporting.write_calendar_returns_csv:
        for name, table in calendar_return_tables(frame["net_return"]).items():
            tables[f"returns_{name}"] = table
    if reporting.write_rolling_metrics_csv:
        tables["rolling_metrics"] = rolling_metric_table(
            frame["net_return"],
            windows_days=reporting.rolling_windows_days,
        )
    return tables


def flatten_metrics(metrics: Mapping[str, Any], *, prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(metrics):
        path = f"{prefix}.{key}" if prefix else str(key)
        value = metrics[key]
        if isinstance(value, Mapping):
            rows.extend(flatten_metrics(value, prefix=path))
        elif isinstance(value, (str, bool)) or value is None:
            rows.append({"metric": path, "value": value})
        else:
            rows.append({"metric": path, "value": _finite_or_none(value)})
    return rows


__all__ = [
    "build_extended_metrics",
    "build_reporting_tables",
    "calendar_return_tables",
    "extract_trade_ledger",
    "flatten_metrics",
    "moving_block_bootstrap_metrics",
    "rolling_metric_table",
]
