from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


TRADE_R_ALIASES = ("trade_r", "realized_r", "target_trade_r", "r_target_trade_r", "target_r")
MFE_ALIASES = ("max_favorable_r", "target_mfe_r", "mfe_r")
MAE_ALIASES = ("max_adverse_r", "target_mae_r", "mae_r")
BARS_HELD_ALIASES = ("bars_held", "target_bars_held")
EXIT_REASON_ALIASES = ("exit_reason", "target_exit_reason", "r_target_exit_reason")
TIME_TO_MFE_ALIASES = ("time_to_mfe", "target_time_to_mfe")
TIME_TO_MAE_ALIASES = ("time_to_mae", "target_time_to_mae")
PROB_ALIASES = ("pred_prob", "prob_positive")
OOS_ALIASES = ("pred_is_oos",)


def _first_existing(frame: pd.DataFrame, aliases: Sequence[str]) -> str | None:
    for column in aliases:
        if column in frame.columns:
            return column
    return None


def _numeric(frame: pd.DataFrame, column: str | None) -> pd.Series:
    if column is None or column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _safe_mean(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(values.mean()) if not values.empty else None


def _safe_median(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(values.median()) if not values.empty else None


def _safe_quantile(series: pd.Series, q: float) -> float | None:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(values.quantile(q)) if not values.empty else None


def _prob(mask: pd.Series) -> float | None:
    valid = mask.dropna()
    return float(valid.mean()) if len(valid) else None


def _profit_factor(trade_r: pd.Series) -> float | None:
    values = pd.to_numeric(trade_r, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return None
    gains = float(values[values > 0.0].sum())
    losses = float(-values[values < 0.0].sum())
    if losses <= 0.0:
        return np.inf if gains > 0.0 else None
    return float(gains / losses)


def _cost_r_series(frame: pd.DataFrame) -> tuple[pd.Series | None, str | None]:
    if "total_cost_r" in frame.columns:
        return pd.to_numeric(frame["total_cost_r"], errors="coerce").astype(float), None
    component_cols = [col for col in ("cost_r", "estimated_cost_r", "commission_r", "slippage_r") if col in frame.columns]
    if component_cols:
        cost = pd.Series(0.0, index=frame.index, dtype=float)
        for col in component_cols:
            cost = cost.add(pd.to_numeric(frame[col], errors="coerce").fillna(0.0).astype(float), fill_value=0.0)
        return cost, None
    if any(col in frame.columns for col in ("cost_paid", "total_cost", "estimated_cost")):
        return None, "probability_trade_quality expected_r_after_cost skipped: cost columns are not in R units"
    return None, None


def _threshold_suffix(threshold: float) -> str:
    text = f"{float(threshold):g}".replace(".", "_")
    return f"{text}r"


def _canonical_columns(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    aliases = {
        "trade_r": TRADE_R_ALIASES,
        "max_favorable_r": MFE_ALIASES,
        "max_adverse_r": MAE_ALIASES,
        "bars_held": BARS_HELD_ALIASES,
        "exit_reason": EXIT_REASON_ALIASES,
        "time_to_mfe": TIME_TO_MFE_ALIASES,
        "time_to_mae": TIME_TO_MAE_ALIASES,
    }
    for canonical, names in aliases.items():
        if canonical in out.columns:
            continue
        source = _first_existing(out, names)
        if source is not None:
            out[canonical] = out[source]
    return out


def _position_sign(value: float, *, eps: float) -> int:
    if not np.isfinite(value) or abs(float(value)) <= float(eps):
        return 0
    return 1 if float(value) > 0.0 else -1


def _as_single_asset_series(
    values: pd.Series | pd.DataFrame | None,
    *,
    asset: str,
    index: pd.Index,
    field_name: str,
    diagnostics: dict[str, Any],
    default: float = 0.0,
) -> pd.Series | None:
    if values is None:
        return pd.Series(float(default), index=index, dtype=float)
    if isinstance(values, pd.DataFrame):
        if asset in values.columns:
            raw = values[asset]
        elif len(values.columns) == 1:
            raw = values.iloc[:, 0]
        else:
            diagnostics["warnings"].append(
                f"fallback trade ledger skipped {field_name}: multi-asset frames require an asset column"
            )
            return None
    elif isinstance(values, pd.Series):
        raw = values
    else:
        diagnostics["warnings"].append(f"fallback trade ledger skipped {field_name}: unsupported series type")
        return None
    return pd.to_numeric(raw, errors="coerce").reindex(index).fillna(float(default)).astype(float)


def _first_cfg_dict(cfg: Mapping[str, Any] | None, *path: str) -> dict[str, Any]:
    current: Any = cfg or {}
    for key in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key, {})
    return dict(current or {}) if isinstance(current, Mapping) else {}


def _unique_existing_candidates(*values: Any) -> list[str]:
    out: list[str] = []
    for value in values:
        if value is None:
            continue
        token = str(value)
        if token and token not in out:
            out.append(token)
    return out


def _resolve_ledger_columns(
    frame: pd.DataFrame,
    *,
    cfg: Mapping[str, Any] | None,
    price_col: str | None,
    high_col: str | None,
    low_col: str | None,
) -> tuple[str | None, str | None, str | None]:
    backtest_cfg = _first_cfg_dict(cfg, "backtest")
    target_cfg = _first_cfg_dict(cfg, "target")
    model_target_cfg = _first_cfg_dict(cfg, "model", "target")
    price = _first_existing(
        frame,
        _unique_existing_candidates(
            price_col,
            backtest_cfg.get("price_col"),
            backtest_cfg.get("close_col"),
            target_cfg.get("price_col"),
            model_target_cfg.get("price_col"),
            "close",
        ),
    )
    high = _first_existing(frame, _unique_existing_candidates(high_col, backtest_cfg.get("high_col"), "high"))
    low = _first_existing(frame, _unique_existing_candidates(low_col, backtest_cfg.get("low_col"), "low"))
    return price, high or price, low or price


def _numeric_value_at(frame: pd.DataFrame, timestamp: pd.Timestamp, column: str | None) -> float:
    if column is None or column not in frame.columns or timestamp not in frame.index:
        return np.nan
    value = pd.to_numeric(pd.Series([frame.at[timestamp, column]]), errors="coerce").iloc[0]
    return float(value) if np.isfinite(value) else np.nan


def _resolve_entry_risk_distance(
    frame: pd.DataFrame,
    *,
    entry_timestamp: pd.Timestamp,
    entry_price: float,
    cfg: Mapping[str, Any] | None,
    risk_col: str | None,
) -> tuple[float, str]:
    backtest_cfg = _first_cfg_dict(cfg, "backtest")
    target_cfg = _first_cfg_dict(cfg, "target")
    model_target_cfg = _first_cfg_dict(cfg, "model", "target")
    candidates = _unique_existing_candidates(
        risk_col,
        backtest_cfg.get("volatility_col"),
        target_cfg.get("volatility_col"),
        model_target_cfg.get("volatility_col"),
        "atr_48",
        "atr",
    )
    for column in candidates:
        value = _numeric_value_at(frame, entry_timestamp, column)
        if np.isfinite(value) and float(value) > 0.0:
            return float(value), column
    fallback = abs(float(entry_price)) if np.isfinite(entry_price) else np.nan
    return (float(fallback), "fallback_price") if np.isfinite(fallback) and fallback > 0.0 else (np.nan, "missing")


def _compound_simple_returns(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    return float((1.0 + clean.astype(float)).prod() - 1.0)


def _series_value_at(series: pd.Series, timestamp: pd.Timestamp) -> float:
    if timestamp not in series.index:
        return 0.0
    value = pd.to_numeric(pd.Series([series.loc[timestamp]]), errors="coerce").iloc[0]
    return float(value) if np.isfinite(value) else 0.0


def build_trade_ledger_from_position_transitions(
    asset_frames: dict[str, pd.DataFrame],
    *,
    positions: pd.Series | pd.DataFrame | None,
    gross_returns: pd.Series | pd.DataFrame | None,
    net_returns: pd.Series | pd.DataFrame | None = None,
    strategy_returns: pd.Series | pd.DataFrame | None = None,
    costs: pd.Series | pd.DataFrame | None = None,
    turnover: pd.Series | pd.DataFrame | None = None,
    cfg: Mapping[str, Any] | None = None,
    asset: str | None = None,
    price_col: str | None = None,
    high_col: str | None = None,
    low_col: str | None = None,
    risk_col: str | None = None,
    eps: float = 1e-12,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Build a trade-level ledger from vectorized position transitions.

    The ledger is diagnostic only: PnL is aggregated from the existing vectorized return
    streams over ``entry_timestamp < timestamp <= exit_timestamp`` and does not alter
    backtest accounting.
    """
    diagnostics: dict[str, Any] = {
        "ledger_source": "position_transitions",
        "trade_count": 0,
        "position_transition_count": 0,
        "fallback_price_risk_distance_count": 0,
        "end_of_data_exit_count": 0,
        "skipped_missing_price_count": 0,
        "warnings": [],
    }
    if not asset_frames:
        diagnostics["warnings"].append("fallback trade ledger skipped: missing asset frames")
        return pd.DataFrame(), diagnostics

    if asset is None:
        if len(asset_frames) != 1:
            diagnostics["warnings"].append(
                "fallback trade ledger skipped: multi-asset positions require explicit asset"
            )
            return pd.DataFrame(), diagnostics
        asset = next(iter(sorted(asset_frames)))
    asset = str(asset)
    if asset not in asset_frames:
        diagnostics["warnings"].append(f"fallback trade ledger skipped: missing asset frame for asset={asset}")
        return pd.DataFrame(), diagnostics

    frame = asset_frames[asset].sort_index()
    if frame.empty:
        diagnostics["warnings"].append(f"fallback trade ledger skipped: empty asset frame for asset={asset}")
        return pd.DataFrame(), diagnostics

    if positions is None:
        diagnostics["warnings"].append("fallback trade ledger skipped: missing positions")
        return pd.DataFrame(), diagnostics
    if isinstance(positions, pd.DataFrame):
        if asset in positions.columns:
            raw_positions = positions[asset]
        elif len(positions.columns) == 1:
            raw_positions = positions.iloc[:, 0]
        else:
            diagnostics["warnings"].append("fallback trade ledger skipped: multi-asset positions are not supported")
            return pd.DataFrame(), diagnostics
    elif isinstance(positions, pd.Series):
        raw_positions = positions
    else:
        diagnostics["warnings"].append("fallback trade ledger skipped: unsupported positions type")
        return pd.DataFrame(), diagnostics

    position_series = pd.to_numeric(raw_positions, errors="coerce").dropna().sort_index().astype(float)
    if position_series.empty:
        diagnostics["warnings"].append("fallback trade ledger skipped: empty positions")
        return pd.DataFrame(), diagnostics
    if not isinstance(position_series.index, pd.DatetimeIndex):
        position_series.index = pd.to_datetime(position_series.index, errors="coerce")
        position_series = position_series.loc[position_series.index.notna()].sort_index()
    if position_series.empty:
        diagnostics["warnings"].append("fallback trade ledger skipped: positions have no valid timestamps")
        return pd.DataFrame(), diagnostics

    index = position_series.index
    gross_series = _as_single_asset_series(
        gross_returns,
        asset=asset,
        index=index,
        field_name="gross_returns",
        diagnostics=diagnostics,
        default=0.0,
    )
    cost_series = _as_single_asset_series(
        costs,
        asset=asset,
        index=index,
        field_name="costs",
        diagnostics=diagnostics,
        default=0.0,
    )
    turnover_series = _as_single_asset_series(
        turnover,
        asset=asset,
        index=index,
        field_name="turnover",
        diagnostics=diagnostics,
        default=0.0,
    )
    if gross_series is None or cost_series is None or turnover_series is None:
        return pd.DataFrame(), diagnostics

    resolved_price_col, resolved_high_col, resolved_low_col = _resolve_ledger_columns(
        frame,
        cfg=cfg,
        price_col=price_col,
        high_col=high_col,
        low_col=low_col,
    )
    if resolved_price_col is None:
        diagnostics["warnings"].append("fallback trade ledger skipped: missing price column")
        return pd.DataFrame(), diagnostics

    previous = position_series.shift(1).fillna(0.0)
    rows: list[dict[str, Any]] = []
    open_trade: dict[str, Any] | None = None

    def open_position(
        timestamp: pd.Timestamp,
        position_value: float,
        *,
        entry_cost: float,
        entry_turnover: float,
    ) -> dict[str, Any]:
        return {
            "entry_timestamp": pd.Timestamp(timestamp),
            "signal_timestamp": pd.Timestamp(timestamp),
            "side": "long" if float(position_value) > 0.0 else "short",
            "position_size": abs(float(position_value)),
            "entry_cost": float(entry_cost),
            "entry_turnover": float(entry_turnover),
        }

    def close_position(
        open_state: dict[str, Any],
        exit_timestamp: pd.Timestamp,
        exit_reason: str,
        *,
        exit_cost: float,
        exit_turnover: float,
    ) -> None:
        entry_ts = pd.Timestamp(open_state["entry_timestamp"])
        exit_ts = pd.Timestamp(exit_timestamp)
        entry_price = _numeric_value_at(frame, entry_ts, resolved_price_col)
        exit_price = _numeric_value_at(frame, exit_ts, resolved_price_col)
        if not np.isfinite(entry_price) or not np.isfinite(exit_price):
            diagnostics["skipped_missing_price_count"] += 1
            return

        risk_distance, risk_source = _resolve_entry_risk_distance(
            frame,
            entry_timestamp=entry_ts,
            entry_price=entry_price,
            cfg=cfg,
            risk_col=risk_col,
        )
        if not np.isfinite(risk_distance) or float(risk_distance) <= 0.0:
            diagnostics["skipped_missing_price_count"] += 1
            return
        if risk_source == "fallback_price":
            diagnostics["fallback_price_risk_distance_count"] += 1

        pnl_mask = (gross_series.index > entry_ts) & (gross_series.index <= exit_ts)
        gross_slice = gross_series.loc[pnl_mask]
        if exit_reason == "end_of_data":
            holding_mask = (cost_series.index > entry_ts) & (cost_series.index <= exit_ts)
        else:
            holding_mask = (cost_series.index > entry_ts) & (cost_series.index < exit_ts)
        holding_cost_slice = cost_series.loc[holding_mask]
        holding_turnover_slice = turnover_series.loc[holding_mask]
        gross_return = _compound_simple_returns(gross_slice)
        entry_cost = float(open_state.get("entry_cost", 0.0))
        entry_turnover = float(open_state.get("entry_turnover", 0.0))
        holding_cost = float(pd.to_numeric(holding_cost_slice, errors="coerce").fillna(0.0).sum())
        holding_turnover = float(pd.to_numeric(holding_turnover_slice, errors="coerce").fillna(0.0).sum())
        total_cost = float(entry_cost + holding_cost + float(exit_cost))
        total_turnover = float(entry_turnover + holding_turnover + float(exit_turnover))

        net_mask = (gross_series.index >= entry_ts) & (gross_series.index <= exit_ts)
        net_components = pd.Series(0.0, index=gross_series.index[net_mask], dtype=float)
        if not net_components.empty:
            net_components.loc[gross_slice.index] = net_components.loc[gross_slice.index].add(
                gross_slice,
                fill_value=0.0,
            )
            if entry_ts in net_components.index:
                net_components.loc[entry_ts] -= entry_cost
            if exit_ts in net_components.index:
                net_components.loc[exit_ts] -= float(exit_cost)
            if not holding_cost_slice.empty:
                net_components.loc[holding_cost_slice.index] = net_components.loc[holding_cost_slice.index].sub(
                    holding_cost_slice,
                    fill_value=0.0,
                )
        net_return = _compound_simple_returns(net_components)

        path = frame.loc[(frame.index > entry_ts) & (frame.index <= exit_ts)]
        side = str(open_state["side"])
        gross_trade_r = (
            (entry_price - exit_price) / float(risk_distance)
            if side == "short"
            else (exit_price - entry_price) / float(risk_distance)
        )
        if path.empty:
            max_favorable_r = max(0.0, float(gross_trade_r))
            max_adverse_r = min(0.0, float(gross_trade_r))
            time_to_mfe = int(len(gross_slice))
            time_to_mae = int(len(gross_slice))
        else:
            high_path = pd.to_numeric(path[resolved_high_col], errors="coerce").astype(float)
            low_path = pd.to_numeric(path[resolved_low_col], errors="coerce").astype(float)
            if side == "short":
                favorable = (entry_price - low_path) / float(risk_distance)
                adverse = (entry_price - high_path) / float(risk_distance)
            else:
                favorable = (high_path - entry_price) / float(risk_distance)
                adverse = (low_path - entry_price) / float(risk_distance)
            max_favorable_r = max(0.0, float(favorable.max(skipna=True))) if favorable.notna().any() else 0.0
            max_adverse_r = min(0.0, float(adverse.min(skipna=True))) if adverse.notna().any() else 0.0
            entry_loc = int(frame.index.searchsorted(entry_ts, side="left"))
            if favorable.notna().any():
                time_to_mfe = int(frame.index.get_loc(favorable.idxmax()) - entry_loc)
            else:
                time_to_mfe = 0
            if adverse.notna().any():
                time_to_mae = int(frame.index.get_loc(adverse.idxmin()) - entry_loc)
            else:
                time_to_mae = 0

        total_cost_r = float(total_cost) * float(entry_price) / float(risk_distance)
        rows.append(
            {
                "trade_id": int(len(rows)),
                "asset": asset,
                "side": side,
                "signal_timestamp": open_state["signal_timestamp"],
                "entry_timestamp": entry_ts,
                "exit_timestamp": exit_ts,
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "raw_entry_price": float(entry_price),
                "raw_exit_price": float(exit_price),
                "bars_held": int(len(gross_slice)),
                "position_size": float(open_state["position_size"]),
                "gross_return": float(gross_return),
                "net_return": float(net_return),
                "entry_cost": float(entry_cost),
                "exit_cost": float(exit_cost),
                "holding_cost": float(holding_cost),
                "total_cost": float(total_cost),
                "entry_turnover": float(entry_turnover),
                "exit_turnover": float(exit_turnover),
                "holding_turnover": float(holding_turnover),
                "total_turnover": float(total_turnover),
                "trade_r": float(gross_trade_r - total_cost_r),
                "gross_trade_r": float(gross_trade_r),
                "total_cost_r": float(total_cost_r),
                "max_favorable_r": float(max_favorable_r),
                "max_adverse_r": float(max_adverse_r),
                "time_to_mfe": int(time_to_mfe),
                "time_to_mae": int(time_to_mae),
                "exit_reason": exit_reason,
                "risk_distance": float(risk_distance),
                "risk_distance_source": risk_source,
            }
        )

    for timestamp in index:
        prev_pos = float(previous.loc[timestamp])
        curr_pos = float(position_series.loc[timestamp])
        prev_sign = _position_sign(prev_pos, eps=eps)
        curr_sign = _position_sign(curr_pos, eps=eps)
        if prev_sign == curr_sign:
            continue
        if prev_sign == 0 and curr_sign != 0:
            diagnostics["position_transition_count"] += 1
            transition_ts = pd.Timestamp(timestamp)
            open_trade = open_position(
                transition_ts,
                curr_pos,
                entry_cost=_series_value_at(cost_series, transition_ts),
                entry_turnover=_series_value_at(turnover_series, transition_ts),
            )
        elif prev_sign != 0 and curr_sign == 0:
            diagnostics["position_transition_count"] += 1
            if open_trade is not None:
                transition_ts = pd.Timestamp(timestamp)
                close_position(
                    open_trade,
                    transition_ts,
                    "position_exit",
                    exit_cost=_series_value_at(cost_series, transition_ts),
                    exit_turnover=_series_value_at(turnover_series, transition_ts),
                )
            open_trade = None
        elif prev_sign != 0 and curr_sign != 0:
            diagnostics["position_transition_count"] += 2
            transition_ts = pd.Timestamp(timestamp)
            total_position_change = abs(curr_pos - prev_pos)
            close_fraction = abs(prev_pos) / total_position_change if total_position_change > 0.0 else 0.0
            entry_fraction = abs(curr_pos) / total_position_change if total_position_change > 0.0 else 0.0
            transition_cost = _series_value_at(cost_series, transition_ts)
            transition_turnover = _series_value_at(turnover_series, transition_ts)
            if open_trade is not None:
                close_position(
                    open_trade,
                    transition_ts,
                    "reversal",
                    exit_cost=transition_cost * close_fraction,
                    exit_turnover=transition_turnover * close_fraction,
                )
            open_trade = open_position(
                transition_ts,
                curr_pos,
                entry_cost=transition_cost * entry_fraction,
                entry_turnover=transition_turnover * entry_fraction,
            )

    if open_trade is not None:
        diagnostics["end_of_data_exit_count"] += 1
        close_position(
            open_trade,
            pd.Timestamp(index[-1]),
            "end_of_data",
            exit_cost=0.0,
            exit_turnover=0.0,
        )

    if diagnostics["fallback_price_risk_distance_count"] > 0:
        count = int(diagnostics["fallback_price_risk_distance_count"])
        diagnostics["warnings"].append(f"fallback trade ledger used entry price as risk distance for {count} trades")
    result = pd.DataFrame(rows)
    diagnostics["trade_count"] = int(len(result))
    if result.empty and diagnostics["position_transition_count"] == 0:
        diagnostics["warnings"].append("fallback trade ledger skipped: no position transitions")
    return result, diagnostics


def enrich_trade_lifecycle_columns(
    trades: pd.DataFrame,
    thresholds_r: Sequence[float],
    *,
    eps: float = 1e-12,
) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame() if trades is None else trades.copy()
    out = _canonical_columns(trades)
    trade_r = _numeric(out, "trade_r")
    mfe = _numeric(out, "max_favorable_r")
    mae = _numeric(out, "max_adverse_r")

    out["was_ever_positive"] = mfe.gt(0.0)
    for threshold in thresholds_r:
        suffix = _threshold_suffix(float(threshold))
        out[f"was_ever_{suffix}"] = mfe.ge(float(threshold))
        out[f"lost_but_reached_{suffix}"] = trade_r.lt(0.0) & mfe.ge(float(threshold))
    out["lost_but_was_positive"] = trade_r.lt(0.0) & mfe.gt(0.0)
    out["giveback_r"] = mfe - trade_r
    capture = trade_r / mfe.where(mfe.abs().gt(float(eps)))
    out["capture_ratio"] = capture.replace([np.inf, -np.inf], np.nan)
    out["positive_mfe_capture_ratio"] = (trade_r / mfe.where(mfe.gt(0.0))).replace([np.inf, -np.inf], np.nan)
    out["abs_mae_r"] = mae.abs()
    return out


def summarize_trade_lifecycle(
    trades: pd.DataFrame,
    thresholds_r: Sequence[float],
    bars_held_buckets: Sequence[int],
) -> dict[str, Any]:
    if trades is None or trades.empty:
        return {"primary_summary": {"trade_count": 0}, "warnings": ["trade_lifecycle diagnostics skipped: no trades"]}

    enriched = enrich_trade_lifecycle_columns(trades, thresholds_r)
    trade_r = _numeric(enriched, "trade_r")
    mfe = _numeric(enriched, "max_favorable_r")
    mae = _numeric(enriched, "max_adverse_r")
    bars = _numeric(enriched, "bars_held")
    partial_exit_count = _numeric(enriched, "partial_exit_count")
    partial_exit_fraction_total = _numeric(enriched, "partial_exit_fraction_total")
    partial_exit_realized_r = _numeric(enriched, "partial_exit_realized_r")
    winners = trade_r.gt(0.0)
    losers = trade_r.lt(0.0)
    warnings: list[str] = []
    if trade_r.notna().sum() == 0:
        warnings.append("trade_lifecycle diagnostics have no realized R column.")
    if mfe.notna().sum() == 0:
        warnings.append("trade_lifecycle diagnostics have no MFE column.")
    if mae.notna().sum() == 0:
        warnings.append("trade_lifecycle diagnostics have no MAE column.")

    loser_mfe = mfe.loc[losers & mfe.notna()]
    summary: dict[str, Any] = {
        "primary_summary": {
            "trade_count": int(len(enriched)),
            "average_r": _safe_mean(trade_r),
            "median_r": _safe_median(trade_r),
            "avg_max_favorable_r": _safe_mean(mfe),
            "avg_max_adverse_r": _safe_mean(mae),
            "partial_exit_count_total": int(partial_exit_count.fillna(0.0).sum())
            if "partial_exit_count" in enriched.columns
            else 0,
            "partial_exit_trade_count": int(partial_exit_count.fillna(0.0).gt(0.0).sum())
            if "partial_exit_count" in enriched.columns
            else 0,
            "avg_partial_exit_fraction_total": _safe_mean(
                partial_exit_fraction_total.loc[partial_exit_count.fillna(0.0).gt(0.0)]
            )
            if "partial_exit_fraction_total" in enriched.columns
            else None,
            "avg_partial_exit_realized_r": _safe_mean(
                partial_exit_realized_r.loc[partial_exit_count.fillna(0.0).gt(0.0)]
            )
            if "partial_exit_realized_r" in enriched.columns
            else None,
            "loser_was_positive_rate": _prob(enriched.loc[losers, "was_ever_positive"]) if bool(losers.any()) else None,
            "avg_giveback_r": _safe_mean(enriched.get("giveback_r", pd.Series(dtype=float))),
            "avg_capture_ratio": _safe_mean(enriched.get("positive_mfe_capture_ratio", pd.Series(dtype=float))),
        },
        "could_have_been_profitable": {
            "loser_was_positive_rate": _prob(enriched.loc[losers, "was_ever_positive"]) if bool(losers.any()) else None,
            "avg_mfe_r_of_losers": _safe_mean(loser_mfe),
            "median_mfe_r_of_losers": _safe_median(loser_mfe),
            "avg_mfe_r_before_loss": _safe_mean(loser_mfe),
            "median_mfe_r_before_loss": _safe_median(loser_mfe),
        },
        "capture_giveback": {
            "avg_capture_ratio": _safe_mean(enriched["positive_mfe_capture_ratio"]),
            "median_capture_ratio": _safe_median(enriched["positive_mfe_capture_ratio"]),
            "avg_giveback_r": _safe_mean(enriched["giveback_r"]),
            "median_giveback_r": _safe_median(enriched["giveback_r"]),
            "avg_giveback_r_winners": _safe_mean(enriched.loc[winners, "giveback_r"]),
            "avg_giveback_r_losers": _safe_mean(enriched.loc[losers, "giveback_r"]),
            "median_giveback_r_winners": _safe_median(enriched.loc[winners, "giveback_r"]),
            "median_giveback_r_losers": _safe_median(enriched.loc[losers, "giveback_r"]),
        },
        "mae_before_win": {
            "winner_had_negative_mae_rate": _prob(mae.loc[winners].lt(0.0)) if bool(winners.any()) else None,
            "winner_had_mae_below_minus_0_25r_rate": _prob(mae.loc[winners].le(-0.25)) if bool(winners.any()) else None,
            "winner_had_mae_below_minus_0_5r_rate": _prob(mae.loc[winners].le(-0.5)) if bool(winners.any()) else None,
            "winner_had_mae_below_minus_1r_rate": _prob(mae.loc[winners].le(-1.0)) if bool(winners.any()) else None,
            "avg_mae_r_of_winners": _safe_mean(mae.loc[winners]),
            "median_mae_r_of_winners": _safe_median(mae.loc[winners]),
            "p90_abs_mae_r_of_winners": _safe_quantile(mae.loc[winners].abs(), 0.90),
            "avg_mae_r": _safe_mean(mae),
            "median_mae_r": _safe_median(mae),
            "q10_mae_r": _safe_quantile(mae, 0.10),
            "q25_mae_r": _safe_quantile(mae, 0.25),
            "q75_mae_r": _safe_quantile(mae, 0.75),
            "q90_mae_r": _safe_quantile(mae, 0.90),
        },
        "conditional_probabilities": {
            "prob_final_win": _prob(trade_r.gt(0.0)),
            "prob_final_loss": _prob(trade_r.lt(0.0)),
            "prob_final_win_given_mae_gt_minus_0_5r": _prob(trade_r.loc[mae.gt(-0.5)].gt(0.0)) if bool(mae.gt(-0.5).any()) else None,
            "prob_final_win_given_mae_gt_minus_1r": _prob(trade_r.loc[mae.gt(-1.0)].gt(0.0)) if bool(mae.gt(-1.0).any()) else None,
        },
        "exit_reason_quality": {},
        "timing": {
            "avg_time_to_mfe": _safe_mean(_numeric(enriched, "time_to_mfe")),
            "median_time_to_mfe": _safe_median(_numeric(enriched, "time_to_mfe")),
            "avg_time_to_mae": _safe_mean(_numeric(enriched, "time_to_mae")),
            "median_time_to_mae": _safe_median(_numeric(enriched, "time_to_mae")),
            "prob_mfe_ge_0_5r_within_1_bar": None,
            "prob_mfe_ge_0_5r_within_2_bars": None,
            "prob_mfe_ge_1r_within_4_bars": None,
            "avg_r_by_bars_held_bucket": {},
            "win_rate_by_bars_held_bucket": {},
        },
        "warnings": warnings,
    }

    for threshold in thresholds_r:
        suffix = _threshold_suffix(float(threshold))
        reached = mfe.ge(float(threshold))
        summary["could_have_been_profitable"][f"loser_reached_{suffix}_rate"] = (
            _prob(reached.loc[losers]) if bool(losers.any()) else None
        )
        summary["conditional_probabilities"][f"prob_mfe_ge_{suffix}"] = _prob(reached)
        summary["conditional_probabilities"][f"prob_final_loss_given_mfe_ge_{suffix}"] = (
            _prob(trade_r.loc[reached].lt(0.0)) if bool(reached.any()) else None
        )

    if "exit_reason" in enriched.columns:
        reasons = enriched["exit_reason"].astype(str).replace({"nan": ""})
        for reason, group in enriched.groupby(reasons, dropna=False):
            reason_label = str(reason) if str(reason).strip() else "unknown"
            group_r = _numeric(group, "trade_r")
            group_mfe = _numeric(group, "max_favorable_r")
            summary["exit_reason_quality"][reason_label] = {
                "trade_count": int(len(group)),
                "avg_r": _safe_mean(group_r),
                "median_r": _safe_median(group_r),
                "win_rate": _prob(group_r.gt(0.0)),
                "avg_mfe_r": _safe_mean(group_mfe),
                "avg_mae_r": _safe_mean(_numeric(group, "max_adverse_r")),
                "avg_giveback_r": _safe_mean(group.get("giveback_r", pd.Series(dtype=float))),
                "avg_bars_held": _safe_mean(_numeric(group, "bars_held")),
                "profit_factor": _profit_factor(group_r),
                "stop_after_positive_rate": _prob(group_mfe.gt(0.0)),
                "stop_after_0_5r_rate": _prob(group_mfe.ge(0.5)),
                "stop_after_1r_rate": _prob(group_mfe.ge(1.0)),
            }
        stop_mask = reasons.str.contains("stop", case=False, na=False)
        for threshold in (0.5, 1.0):
            suffix = _threshold_suffix(threshold)
            reached = mfe.ge(threshold)
            summary["conditional_probabilities"][f"prob_stop_loss_given_mfe_ge_{suffix}"] = (
                _prob(stop_mask.loc[reached]) if bool(reached.any()) else None
            )

    time_to_mfe = _numeric(enriched, "time_to_mfe")
    if time_to_mfe.notna().any():
        summary["timing"]["prob_mfe_ge_0_5r_within_1_bar"] = _prob(mfe.ge(0.5) & time_to_mfe.le(1))
        summary["timing"]["prob_mfe_ge_0_5r_within_2_bars"] = _prob(mfe.ge(0.5) & time_to_mfe.le(2))
        summary["timing"]["prob_mfe_ge_1r_within_4_bars"] = _prob(mfe.ge(1.0) & time_to_mfe.le(4))

    if bars.notna().any():
        labels = _bucket_bars_held(bars, bars_held_buckets)
        for label, values in trade_r.groupby(labels, observed=False):
            summary["timing"]["avg_r_by_bars_held_bucket"][str(label)] = _safe_mean(values)
            summary["timing"]["win_rate_by_bars_held_bucket"][str(label)] = _prob(values.gt(0.0))

    return summary


def _bucket_bars_held(bars: pd.Series, buckets: Sequence[int]) -> pd.Series:
    ordered = [int(x) for x in buckets]
    labels: list[str] = []
    previous = 0
    for value in ordered:
        if value == 1:
            labels.append("1")
        elif value == previous + 1:
            labels.append(str(value))
        else:
            labels.append(f"{previous + 1}-{value}")
        previous = value
    labels.append(f"{ordered[-1] + 1}+")
    bins = [0, *ordered, np.inf]
    return pd.cut(bars, bins=bins, labels=labels, include_lowest=True, right=True)


def _infer_risk_distance(trade: pd.Series) -> float | None:
    for column in ("risk_distance", "risk_distance_price", "risk_points"):
        if column in trade.index:
            value = pd.to_numeric(pd.Series([trade[column]]), errors="coerce").iloc[0]
            if np.isfinite(value) and float(value) > 0.0:
                return float(value)
    entry = pd.to_numeric(pd.Series([trade.get("raw_entry_price", trade.get("entry_price"))]), errors="coerce").iloc[0]
    stop = pd.to_numeric(pd.Series([trade.get("stop_loss_price", trade.get("stop_price"))]), errors="coerce").iloc[0]
    if np.isfinite(entry) and np.isfinite(stop):
        distance = abs(float(entry) - float(stop))
        if distance > 0.0:
            return distance
    return None


def build_trade_paths(
    asset_frames: dict[str, pd.DataFrame],
    trades: pd.DataFrame,
    *,
    max_path_points: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    diagnostics = {
        "trade_count": int(0 if trades is None else len(trades)),
        "path_trade_count": 0,
        "skipped_trade_paths_missing_risk": 0,
        "skipped_trade_paths_missing_asset_frame": 0,
        "skipped_trade_paths_missing_timestamps": 0,
        "truncated": False,
        "warnings": [],
    }
    if trades is None or trades.empty or not asset_frames:
        diagnostics["warnings"].append("trade path construction skipped: missing trades or asset frames")
        return pd.DataFrame(), diagnostics

    rows: list[pd.DataFrame] = []
    default_asset = next(iter(sorted(asset_frames))) if len(asset_frames) == 1 else None
    point_budget = None if max_path_points is None or int(max_path_points) <= 0 else int(max_path_points)
    for trade_idx, trade in trades.reset_index(drop=True).iterrows():
        asset = str(trade.get("asset", default_asset or ""))
        frame = asset_frames.get(asset)
        if frame is None:
            diagnostics["skipped_trade_paths_missing_asset_frame"] += 1
            continue
        risk_distance = _infer_risk_distance(trade)
        if risk_distance is None:
            diagnostics["skipped_trade_paths_missing_risk"] += 1
            continue
        entry_ts = trade.get("entry_timestamp", trade.get("entry_time"))
        exit_ts = trade.get("exit_timestamp", trade.get("exit_time"))
        if pd.isna(entry_ts) or pd.isna(exit_ts):
            diagnostics["skipped_trade_paths_missing_timestamps"] += 1
            continue
        entry_ts = pd.Timestamp(entry_ts)
        exit_ts = pd.Timestamp(exit_ts)
        path = frame.sort_index().loc[(frame.sort_index().index >= entry_ts) & (frame.sort_index().index <= exit_ts)].copy()
        if path.empty:
            diagnostics["skipped_trade_paths_missing_timestamps"] += 1
            continue
        side = str(trade.get("side", "long")).lower()
        entry_price = float(pd.to_numeric(pd.Series([trade.get("raw_entry_price", trade.get("entry_price"))]), errors="coerce").iloc[0])
        if not np.isfinite(entry_price):
            diagnostics["skipped_trade_paths_missing_risk"] += 1
            continue
        out = pd.DataFrame(index=path.index)
        if side == "short":
            price_map = {
                "open_r": "open",
                "high_r": "low",
                "low_r": "high",
                "close_r": "close",
            }
            for out_col, price_col in price_map.items():
                if price_col not in path.columns:
                    out[out_col] = np.nan
                    continue
                prices = pd.to_numeric(path[price_col], errors="coerce").astype(float)
                out[out_col] = (entry_price - prices) / float(risk_distance)
        else:
            for price_col, out_col in (("open", "open_r"), ("high", "high_r"), ("low", "low_r"), ("close", "close_r")):
                if price_col not in path.columns:
                    out[out_col] = np.nan
                    continue
                prices = pd.to_numeric(path[price_col], errors="coerce").astype(float)
                out[out_col] = (prices - entry_price) / float(risk_distance)
        out["timestamp"] = out.index
        out["trade_id"] = trade.get("trade_id", trade_idx)
        out["asset"] = asset
        out["side"] = side
        out["signal_timestamp"] = trade.get("signal_timestamp", trade.get("signal_time"))
        out["entry_timestamp"] = entry_ts
        out["exit_timestamp"] = exit_ts
        out["bar_in_trade"] = np.arange(len(out), dtype=int)
        out["mfe_so_far_r"] = out["high_r"].cummax()
        out["mae_so_far_r"] = out["low_r"].cummin()
        out["drawdown_from_mfe_r"] = out["mfe_so_far_r"] - out["close_r"]
        out["exit_reason"] = trade.get("exit_reason", np.nan)
        out["trade_r"] = trade.get("trade_r", trade.get("realized_r", np.nan))
        ordered = [
            "trade_id",
            "asset",
            "side",
            "signal_timestamp",
            "entry_timestamp",
            "exit_timestamp",
            "timestamp",
            "bar_in_trade",
            "open_r",
            "high_r",
            "low_r",
            "close_r",
            "mfe_so_far_r",
            "mae_so_far_r",
            "drawdown_from_mfe_r",
            "exit_reason",
            "trade_r",
        ]
        rows.append(out[ordered].reset_index(drop=True))
        diagnostics["path_trade_count"] += 1
        if point_budget is not None and sum(len(item) for item in rows) >= point_budget:
            diagnostics["truncated"] = True
            diagnostics["warnings"].append("trade path construction truncated by max_path_points")
            break
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()), diagnostics


def summarize_probability_trade_quality(
    trades: pd.DataFrame,
    prob_col: str | None,
    pred_is_oos_col: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    diagnostics = {"warnings": []}
    if trades is None or trades.empty:
        return pd.DataFrame(), diagnostics
    frame = enrich_trade_lifecycle_columns(trades, [0.5, 1.0])
    resolved_prob_col = prob_col if prob_col and prob_col in frame.columns else _first_existing(frame, PROB_ALIASES)
    if resolved_prob_col is None:
        diagnostics["warnings"].append("probability_trade_quality skipped: missing predicted probability column")
        return pd.DataFrame(), diagnostics
    resolved_oos = pred_is_oos_col if pred_is_oos_col and pred_is_oos_col in frame.columns else _first_existing(frame, OOS_ALIASES)
    if resolved_oos is not None:
        frame = frame.loc[frame[resolved_oos].fillna(False).astype(bool)].copy()
    else:
        diagnostics["warnings"].append("probability_trade_quality computed without OOS marker")
    probs = pd.to_numeric(frame[resolved_prob_col], errors="coerce")
    frame = frame.loc[probs.notna()].copy()
    if frame.empty:
        return pd.DataFrame(), diagnostics
    frame["_prob"] = pd.to_numeric(frame[resolved_prob_col], errors="coerce")
    try:
        frame["decile"] = pd.qcut(frame["_prob"], q=min(10, frame["_prob"].nunique()), duplicates="drop")
    except ValueError:
        frame["decile"] = "all"
    rows: list[dict[str, Any]] = []
    cost_r, cost_warning = _cost_r_series(frame)
    if cost_warning is not None and cost_warning not in diagnostics["warnings"]:
        diagnostics["warnings"].append(cost_warning)
    for bucket, group in frame.groupby("decile", observed=True, dropna=False):
        trade_r = _numeric(group, "trade_r")
        group_cost_r = cost_r.reindex(group.index) if cost_r is not None else None
        row = {
            "probability_bucket": str(bucket),
            "decile": str(bucket),
            "trade_count": int(len(group)),
            "avg_pred_prob": _safe_mean(group["_prob"]),
            "actual_win_rate": _prob(trade_r.gt(0.0)),
            "avg_realized_r": _safe_mean(trade_r),
            "avg_trade_r": _safe_mean(trade_r),
            "median_trade_r": _safe_median(trade_r),
            "avg_mfe_r": _safe_mean(_numeric(group, "max_favorable_r")),
            "avg_mae_r": _safe_mean(_numeric(group, "max_adverse_r")),
            "avg_giveback_r": _safe_mean(group.get("giveback_r", pd.Series(dtype=float))),
            "profit_factor": _profit_factor(trade_r),
            "expected_r_after_cost": _safe_mean(trade_r - group_cost_r) if group_cost_r is not None else None,
            "avg_bars_held": _safe_mean(_numeric(group, "bars_held")),
        }
        rows.append(row)
    return pd.DataFrame(rows), diagnostics


def _baseline_r(path: pd.DataFrame, close_r: pd.Series) -> float:
    trade_r = pd.to_numeric(path["trade_r"], errors="coerce") if "trade_r" in path.columns else pd.Series(dtype=float)
    valid_trade_r = trade_r.replace([np.inf, -np.inf], np.nan).dropna()
    if not valid_trade_r.empty:
        return float(valid_trade_r.iloc[-1])
    valid_close = close_r.replace([np.inf, -np.inf], np.nan).dropna()
    return float(valid_close.iloc[-1]) if not valid_close.empty else np.nan


def _exit_at_first_threshold(high_r: pd.Series, baseline: float, threshold: float) -> float:
    hit = high_r.ge(float(threshold))
    return float(threshold) if bool(hit.any()) else float(baseline)


def _breakeven_after_trigger(high_r: pd.Series, low_r: pd.Series, baseline: float, trigger: float) -> float:
    armed = False
    for bar_high, bar_low in zip(high_r.to_numpy(dtype=float), low_r.to_numpy(dtype=float), strict=False):
        if not armed and np.isfinite(bar_high) and bar_high >= float(trigger):
            armed = True
        if armed and np.isfinite(bar_low) and bar_low <= 0.0:
            return 0.0
    return float(baseline)


def _trail_after_trigger(high_r: pd.Series, low_r: pd.Series, baseline: float, *, trigger: float, trail_distance: float) -> float:
    armed = False
    max_mfe = -np.inf
    for bar_high, bar_low in zip(high_r.to_numpy(dtype=float), low_r.to_numpy(dtype=float), strict=False):
        if np.isfinite(bar_high):
            max_mfe = max(float(max_mfe), float(bar_high))
        if not armed and max_mfe >= float(trigger):
            armed = True
        if armed and np.isfinite(bar_low):
            trailing_stop = float(max_mfe) - float(trail_distance)
            if float(bar_low) <= trailing_stop:
                return trailing_stop
    return float(baseline)


def _time_exit_if_slow_mfe(high_r: pd.Series, close_r: pd.Series, baseline: float) -> float:
    if len(high_r) < 5:
        return float(baseline)
    first_five_high = high_r.iloc[:5].replace([np.inf, -np.inf], np.nan)
    if first_five_high.notna().any() and float(first_five_high.max()) < 0.3:
        return float(close_r.iloc[4])
    return float(baseline)


def _partial_at_first_threshold(high_r: pd.Series, baseline: float, threshold: float) -> float:
    hit = high_r.ge(float(threshold))
    return float(0.5 * float(threshold) + 0.5 * float(baseline)) if bool(hit.any()) else float(baseline)


def simulate_counterfactual_exits(
    trade_paths: pd.DataFrame,
    policies: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    diagnostics: dict[str, Any] = {"warnings": []}
    if trade_paths is None or trade_paths.empty:
        diagnostics["warnings"].append("counterfactual exits skipped: trade paths unavailable")
        return pd.DataFrame(), diagnostics
    policies = policies or [
        "baseline",
        "breakeven_after_0_5r",
        "breakeven_after_1_0r",
        "exit_at_first_0_5r",
        "exit_at_first_1_0r",
        "trail_0_5r_after_1_0r",
        "time_exit_after_4_bars_if_mfe_lt_0_3r",
        "partial_50pct_at_1r",
    ]
    rows: list[dict[str, Any]] = []
    for trade_id, path in trade_paths.sort_values(["trade_id", "bar_in_trade"]).groupby("trade_id", sort=True):
        close_r = pd.to_numeric(path["close_r"], errors="coerce").astype(float).reset_index(drop=True)
        high_r = pd.to_numeric(path["high_r"], errors="coerce").astype(float).reset_index(drop=True)
        low_r = pd.to_numeric(path["low_r"], errors="coerce").astype(float).reset_index(drop=True)
        baseline = _baseline_r(path, close_r)
        for policy in policies:
            r = baseline
            if policy == "exit_at_first_0_5r":
                r = _exit_at_first_threshold(high_r, baseline, 0.5)
            elif policy == "exit_at_first_1_0r":
                r = _exit_at_first_threshold(high_r, baseline, 1.0)
            elif policy == "breakeven_after_0_5r":
                r = _breakeven_after_trigger(high_r, low_r, baseline, 0.5)
            elif policy == "breakeven_after_1_0r":
                r = _breakeven_after_trigger(high_r, low_r, baseline, 1.0)
            elif policy == "trail_0_5r_after_1_0r":
                r = _trail_after_trigger(high_r, low_r, baseline, trigger=1.0, trail_distance=0.5)
            elif policy == "time_exit_after_4_bars_if_mfe_lt_0_3r":
                r = _time_exit_if_slow_mfe(high_r, close_r, baseline)
            elif policy == "partial_50pct_at_1r":
                r = _partial_at_first_threshold(high_r, baseline, 1.0)
            rows.append({"trade_id": trade_id, "policy": policy, "counterfactual_r": float(r)})
    result = pd.DataFrame(rows)
    summary: dict[str, Any] = {}
    for policy, group in result.groupby("policy", sort=True):
        values = pd.to_numeric(group["counterfactual_r"], errors="coerce").astype(float)
        summary[f"counterfactual.{policy}.trade_count"] = int(len(group))
        summary[f"counterfactual.{policy}.avg_r"] = _safe_mean(values)
        summary[f"counterfactual.{policy}.median_r"] = _safe_median(values)
        summary[f"counterfactual.{policy}.win_rate"] = _prob(values.gt(0.0))
        summary[f"counterfactual.{policy}.profit_factor"] = _profit_factor(values)
    avg_candidates = {policy: summary.get(f"counterfactual.{policy}.avg_r") for policy in policies}
    pf_candidates = {policy: summary.get(f"counterfactual.{policy}.profit_factor") for policy in policies}
    finite_avg = {k: v for k, v in avg_candidates.items() if v is not None and np.isfinite(float(v))}
    finite_pf = {k: v for k, v in pf_candidates.items() if v is not None and np.isfinite(float(v))}
    summary["counterfactual.best_policy_by_avg_r"] = max(finite_avg, key=finite_avg.get) if finite_avg else None
    summary["counterfactual.best_policy_by_profit_factor"] = max(finite_pf, key=finite_pf.get) if finite_pf else None
    diagnostics.update(summary)
    return result, diagnostics


__all__ = [
    "build_trade_ledger_from_position_transitions",
    "build_trade_paths",
    "enrich_trade_lifecycle_columns",
    "simulate_counterfactual_exits",
    "summarize_probability_trade_quality",
    "summarize_trade_lifecycle",
]
