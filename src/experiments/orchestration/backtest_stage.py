from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult, run_backtest
from src.backtesting.manual_barrier import run_manual_barrier_backtest
from src.backtesting.portfolio_barrier import run_portfolio_barrier_backtest
from src.backtesting.holding import apply_min_holding_bars_to_weights
from src.evaluation.metrics import compute_backtest_metrics
from src.evaluation.robustness import (
    calendar_walk_forward_diagnostics,
    cost_multiplier_stress,
    gap_penalty_stress,
    summarize_returns,
)
from src.experiments.orchestration.common import align_asset_column
from src.portfolio import (
    PortfolioConstraints,
    PortfolioPerformance,
    build_constrained_weights_from_exposures_over_time,
    build_optimized_weights_over_time,
    build_ranked_weights_from_scores_over_time,
    build_rolling_covariance_by_date,
    build_weights_from_signals_over_time,
    compute_portfolio_performance,
)
from src.risk.position_sizing import scale_signal_for_ftmo
from src.experiments.schemas import PortfolioMetaPayload


def resolve_vol_col(df: pd.DataFrame, backtest_cfg: dict[str, Any], risk_cfg: dict[str, Any]) -> str | None:
    vol_col = backtest_cfg.get("vol_col") or risk_cfg.get("vol_col")
    if vol_col:
        return vol_col
    for cand in ("vol_rolling_20", "vol_ewma_20", "vol_rolling_60", "vol_ewma_60"):
        if cand in df.columns:
            return cand
    return None


def validate_returns_series(returns: pd.Series, returns_type: str) -> None:
    if returns_type == "simple" and (returns < -1.0).any():
        raise ValueError("Simple returns contain values < -1.0; check returns_type or data.")


def validate_returns_frame(returns: pd.DataFrame, returns_type: str) -> None:
    if returns_type == "simple" and (returns < -1.0).any().any():
        raise ValueError("Simple returns contain values < -1.0; check returns_type or data.")


def build_portfolio_constraints(portfolio_cfg: dict[str, Any]) -> PortfolioConstraints:
    constraints_cfg = dict(portfolio_cfg.get("constraints", {}) or {})
    enforce_target_net_exposure = constraints_cfg.get("enforce_target_net_exposure", True)
    if not isinstance(enforce_target_net_exposure, bool):
        raise ValueError("portfolio.constraints.enforce_target_net_exposure must be boolean.")
    return PortfolioConstraints(
        min_weight=float(constraints_cfg.get("min_weight", -1.0)),
        max_weight=float(constraints_cfg.get("max_weight", 1.0)),
        max_gross_leverage=float(constraints_cfg.get("max_gross_leverage", 1.0)),
        target_net_exposure=float(constraints_cfg.get("target_net_exposure", 0.0)),
        enforce_target_net_exposure=enforce_target_net_exposure,
        turnover_limit=(
            float(constraints_cfg["turnover_limit"])
            if constraints_cfg.get("turnover_limit") is not None
            else None
        ),
        group_max_exposure=(
            {str(k): float(v) for k, v in dict(constraints_cfg.get("group_max_exposure", {}) or {}).items()}
            or None
        ),
    )


def _ftmo_sizing_config(risk_cfg: dict[str, Any]) -> dict[str, Any]:
    sizing = dict(risk_cfg.get("sizing", {}) or {})
    if str(sizing.get("kind", "none")) != "ftmo_risk_per_trade":
        return {}
    return sizing


def _scale_single_asset_signal_for_ftmo(
    df: pd.DataFrame,
    *,
    signal_col: str,
    sizing_cfg: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    vol_col = str(sizing_cfg.get("vol_col") or "")
    if not vol_col:
        raise ValueError("risk.sizing.vol_col is required for ftmo_risk_per_trade sizing.")
    if vol_col not in df.columns:
        raise KeyError(f"risk.sizing.vol_col '{vol_col}' not found in DataFrame")
    confidence_col = sizing_cfg.get("confidence_col")
    confidence = None
    if confidence_col is not None:
        confidence_col = str(confidence_col)
        if confidence_col not in df.columns:
            raise KeyError(f"risk.sizing.confidence_col '{confidence_col}' not found in DataFrame")
        confidence = df[confidence_col].astype(float)

    output_col = str(sizing_cfg.get("output_col") or f"{signal_col}_ftmo_sized")
    out = df.copy()
    out[output_col] = scale_signal_for_ftmo(
        signal=out[signal_col].astype(float),
        vol=out[vol_col].astype(float),
        target_vol=sizing_cfg.get("target_vol"),
        risk_per_trade=float(sizing_cfg.get("risk_per_trade", 0.0025)),
        stop_mult=float(sizing_cfg.get("stop_mult", 1.0)),
        max_leverage=float(sizing_cfg.get("max_leverage", 3.0)),
        min_leverage=float(sizing_cfg.get("min_leverage", 0.0)),
        min_abs_signal=float(sizing_cfg.get("min_abs_signal", 0.0)),
        confidence=confidence,
        confidence_floor=sizing_cfg.get("confidence_floor"),
        confidence_mode=str(sizing_cfg.get("confidence_mode", "directional_class1") or "directional_class1"),
        confidence_power=float(sizing_cfg.get("confidence_power", 1.0)),
    ).astype(float)
    return out, output_col


def _build_ftmo_sized_exposures(
    asset_frames: dict[str, pd.DataFrame],
    *,
    signal_col: str,
    sizing_cfg: dict[str, Any],
    alignment: str,
) -> pd.DataFrame:
    vol_col = str(sizing_cfg.get("vol_col") or "")
    if not vol_col:
        raise ValueError("risk.sizing.vol_col is required for ftmo_risk_per_trade sizing.")
    confidence_col = sizing_cfg.get("confidence_col")
    exposures: dict[str, pd.Series] = {}
    for asset, frame in sorted(asset_frames.items()):
        if signal_col not in frame.columns:
            raise KeyError(f"Column '{signal_col}' not found for asset '{asset}'.")
        if vol_col not in frame.columns:
            raise KeyError(f"risk.sizing.vol_col '{vol_col}' not found for asset '{asset}'.")
        confidence = None
        if confidence_col is not None:
            confidence_col_name = str(confidence_col)
            if confidence_col_name not in frame.columns:
                raise KeyError(
                    f"risk.sizing.confidence_col '{confidence_col_name}' not found for asset '{asset}'."
                )
            confidence = frame[confidence_col_name].astype(float)
        exposures[asset] = scale_signal_for_ftmo(
            signal=frame[signal_col].astype(float),
            vol=frame[vol_col].astype(float),
            target_vol=sizing_cfg.get("target_vol"),
            risk_per_trade=float(sizing_cfg.get("risk_per_trade", 0.0025)),
            stop_mult=float(sizing_cfg.get("stop_mult", 1.0)),
            max_leverage=float(sizing_cfg.get("max_leverage", 3.0)),
            min_leverage=float(sizing_cfg.get("min_leverage", 0.0)),
            min_abs_signal=float(sizing_cfg.get("min_abs_signal", 0.0)),
            confidence=confidence,
            confidence_floor=sizing_cfg.get("confidence_floor"),
            confidence_mode=str(sizing_cfg.get("confidence_mode", "directional_class1") or "directional_class1"),
            confidence_power=float(sizing_cfg.get("confidence_power", 1.0)),
        ).astype(float)
    out = pd.concat(exposures, axis=1, join=alignment).sort_index()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    out.columns = [str(col) for col in out.columns]
    return out


def run_single_asset_backtest(
    asset: str,
    df: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    model_meta: dict[str, Any],
) -> BacktestResult:
    backtest_cfg = cfg["backtest"]
    risk_cfg = cfg["risk"]
    signal_col = backtest_cfg["signal_col"]
    returns_col = backtest_cfg["returns_col"]
    returns_type = backtest_cfg.get("returns_type", "simple")
    validate_returns_series(df[returns_col].dropna(), returns_type)
    backtest_engine = str(backtest_cfg.get("engine", "vectorized"))

    dd_cfg = risk_cfg.get("dd_guard") or {}
    dd_guard = dd_cfg.get("enabled", True)
    vol_col = resolve_vol_col(df, backtest_cfg, risk_cfg)
    target_vol = risk_cfg.get("target_vol")
    if target_vol is not None and vol_col is None:
        raise ValueError("target_vol is set but no vol_col was found or configured.")

    bt_df = df
    bt_signal_col = signal_col
    sizing_cfg = _ftmo_sizing_config(risk_cfg)
    if backtest_engine == "manual_barrier":
        if bool(dd_guard):
            raise ValueError("backtest.engine='manual_barrier' currently requires risk.dd_guard.enabled=false.")
        if target_vol is not None:
            raise ValueError("backtest.engine='manual_barrier' does not support risk.target_vol.")
        if sizing_cfg:
            raise ValueError("backtest.engine='manual_barrier' does not support risk.sizing; size via the signal.")
        if backtest_cfg.get("subset", "full") != "full":
            raise ValueError("backtest.engine='manual_barrier' currently supports backtest.subset='full' only.")
        max_holding_bars = backtest_cfg.get("max_holding_bars", 16)
        result = run_manual_barrier_backtest(
            df,
            signal_col=signal_col,
            open_col=str(backtest_cfg.get("open_col", "open")),
            high_col=str(backtest_cfg.get("high_col", "high")),
            low_col=str(backtest_cfg.get("low_col", "low")),
            close_col=str(backtest_cfg.get("close_col", "close")),
            take_profit_r=float(backtest_cfg.get("take_profit_r", 1.8)),
            stop_loss_r=float(backtest_cfg.get("stop_loss_r", 1.0)),
            risk_per_trade=float(backtest_cfg.get("risk_per_trade", 0.006)),
            max_holding_bars=int(max_holding_bars) if max_holding_bars is not None else None,
            cost_per_unit_turnover=float(risk_cfg.get("cost_per_turnover", 0.0)),
            slippage_per_unit_turnover=float(risk_cfg.get("slippage_per_turnover", 0.0)),
            max_leverage=float(risk_cfg.get("max_leverage", 1.0)),
            periods_per_year=int(backtest_cfg.get("periods_per_year", 252)),
            dynamic_exits=dict(backtest_cfg.get("dynamic_exits", {}) or {}),
            partial_exits=dict(backtest_cfg.get("partial_exits", {}) or {}),
            allow_short=bool(backtest_cfg.get("allow_short", False)),
            stop_mode=str(backtest_cfg.get("stop_mode", "fixed_return")),
            vol_col=backtest_cfg.get("vol_col"),
        )
        if result.trades is not None and not result.trades.empty and "asset" not in result.trades.columns:
            result.trades = result.trades.copy()
            result.trades.insert(0, "asset", asset)
        return result
    if sizing_cfg:
        bt_df, bt_signal_col = _scale_single_asset_signal_for_ftmo(
            bt_df,
            signal_col=signal_col,
            sizing_cfg=sizing_cfg,
        )
        target_vol = None
    oos_mask: pd.Series | None = None
    if model_meta:
        bt_subset = backtest_cfg.get("subset", "test")
        pred_is_oos_col = str(model_meta.get("pred_is_oos_col") or "pred_is_oos")
        if bt_subset == "test" and pred_is_oos_col in df.columns:
            oos_mask = df[pred_is_oos_col].fillna(False).astype(bool)
            if bool(oos_mask.any()):
                # Preserve any pre-backtest signal transforms such as FTMO risk-per-trade sizing.
                # Rebuilding from the raw df here would drop bt_signal_col for OOS rows and
                # silently flatten the single-asset backtest despite valid accepted candidates.
                bt_df = bt_df.copy()
                bt_df.loc[~oos_mask, bt_signal_col] = 0.0
                first_oos_label = oos_mask[oos_mask].index[0]
                bt_df = bt_df.loc[first_oos_label:]
                oos_mask = oos_mask.reindex(bt_df.index).fillna(False).astype(bool)
        elif model_meta.get("split_index") is not None and backtest_cfg.get("subset", "test") == "test":
            bt_df = df.iloc[int(model_meta["split_index"]) :]

    result = run_backtest(
        bt_df,
        signal_col=bt_signal_col,
        returns_col=returns_col,
        returns_type=returns_type,
        missing_return_policy=backtest_cfg.get("missing_return_policy", "raise_if_exposed"),
        cost_per_unit_turnover=risk_cfg.get("cost_per_turnover", 0.0),
        slippage_per_unit_turnover=risk_cfg.get("slippage_per_turnover", 0.0),
        target_vol=target_vol,
        vol_col=vol_col,
        max_leverage=risk_cfg.get("max_leverage", 3.0),
        dd_guard=dd_guard,
        max_drawdown=dd_cfg.get("max_drawdown", 0.2),
        cooloff_bars=dd_cfg.get("cooloff_bars", 20),
        rearm_drawdown=dd_cfg.get("rearm_drawdown"),
        periods_per_year=backtest_cfg.get("periods_per_year", 252),
        min_holding_bars=backtest_cfg.get("min_holding_bars", 0),
    )
    if oos_mask is not None and bool(oos_mask.any()):
        aligned_oos_mask = oos_mask.reindex(result.returns.index).fillna(False).astype(bool)
        result.summary = compute_backtest_metrics(
            net_returns=result.returns.loc[aligned_oos_mask],
            periods_per_year=backtest_cfg.get("periods_per_year", 252),
            turnover=result.turnover.loc[aligned_oos_mask],
            costs=result.costs.loc[aligned_oos_mask],
            gross_returns=result.gross_returns.loc[aligned_oos_mask],
        )
    return result


def run_portfolio_backtest(
    asset_frames: dict[str, pd.DataFrame],
    *,
    cfg: dict[str, Any],
) -> tuple[PortfolioPerformance, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    backtest_cfg = cfg["backtest"]
    risk_cfg = cfg["risk"]
    portfolio_cfg = cfg["portfolio"]
    alignment = cfg["data"].get("alignment", "inner")

    signal_col = backtest_cfg["signal_col"]
    returns_col = backtest_cfg["returns_col"]
    returns_type = backtest_cfg.get("returns_type", "simple")
    bt_subset = str(backtest_cfg.get("subset", "full"))
    backtest_engine = str(backtest_cfg.get("engine", "vectorized"))

    if backtest_engine == "portfolio_barrier":
        if str(portfolio_cfg.get("construction", "signal_weights")) != "signal_weights":
            raise ValueError("backtest.engine='portfolio_barrier' requires portfolio.construction='signal_weights'.")
        if risk_cfg.get("target_vol") is not None:
            raise ValueError("backtest.engine='portfolio_barrier' does not support risk.target_vol.")
        if int(backtest_cfg.get("min_holding_bars", 0) or 0) != 0:
            raise ValueError("backtest.engine='portfolio_barrier' uses vertical_barrier_bars; min_holding_bars must be 0.")
        sizing_cfg = _ftmo_sizing_config(risk_cfg)
        barrier_asset_frames = asset_frames
        barrier_signal_col = signal_col
        if sizing_cfg:
            barrier_asset_frames = {}
            for asset, frame in sorted(asset_frames.items()):
                sized_frame, sized_signal_col = _scale_single_asset_signal_for_ftmo(
                    frame,
                    signal_col=signal_col,
                    sizing_cfg=sizing_cfg,
                )
                barrier_asset_frames[asset] = sized_frame
                barrier_signal_col = sized_signal_col
        constraints = build_portfolio_constraints(portfolio_cfg)
        asset_groups = {str(k): str(v) for k, v in dict(portfolio_cfg.get("asset_groups", {}) or {}).items()}
        vertical_barrier_bars = backtest_cfg.get("vertical_barrier_bars", 4)
        performance, weights, diagnostics, barrier_meta = run_portfolio_barrier_backtest(
            barrier_asset_frames,
            signal_col=barrier_signal_col,
            open_col=str(backtest_cfg.get("open_col", "open")),
            high_col=str(backtest_cfg.get("high_col", "high")),
            low_col=str(backtest_cfg.get("low_col", "low")),
            close_col=str(backtest_cfg.get("close_col", "close")),
            volatility_col=str(backtest_cfg.get("volatility_col", backtest_cfg.get("vol_col", "atr_14"))),
            entry_price_mode=str(backtest_cfg.get("entry_price_mode", "next_open")),
            profit_barrier_r=float(backtest_cfg.get("profit_barrier_r", 1.4)),
            stop_barrier_r=float(backtest_cfg.get("stop_barrier_r", 1.0)),
            vertical_barrier_bars=(
                int(vertical_barrier_bars) if vertical_barrier_bars is not None else None
            ),
            tie_break=str(backtest_cfg.get("tie_break", "closest_to_open")),
            subset=bt_subset,
            pred_is_oos_col=str(cfg.get("model", {}).get("pred_is_oos_col") or "pred_is_oos"),
            alignment=alignment,
            constraints=constraints,
            gross_target=float(portfolio_cfg.get("gross_target", 1.0)),
            cost_per_turnover=float(risk_cfg.get("cost_per_turnover", 0.0)),
            slippage_per_turnover=float(risk_cfg.get("slippage_per_turnover", 0.0)),
            periods_per_year=int(backtest_cfg.get("periods_per_year", 252)),
            asset_params=dict(backtest_cfg.get("asset_params", {}) or {}),
            asset_to_group=asset_groups or None,
            portfolio_guard=dict(risk_cfg.get("portfolio_guard", {}) or {}),
            event_time_remap_policy=str(backtest_cfg.get("event_time_remap_policy", "next_aligned")),
            max_cost_r=backtest_cfg.get("max_cost_r"),
            dynamic_exit=dict(backtest_cfg.get("dynamic_exit", {}) or {}),
            correlation_guard=dict(backtest_cfg.get("correlation_guard", {}) or {}),
        )
        portfolio_meta = PortfolioMetaPayload(
            construction="portfolio_barrier",
            asset_count=int(len(asset_frames)),
            alignment=alignment,
            expected_return_col=None,
            avg_gross_exposure=float(diagnostics["gross_exposure"].mean()) if not diagnostics.empty else 0.0,
            avg_net_exposure=float(diagnostics["net_exposure"].mean()) if not diagnostics.empty else 0.0,
            avg_turnover=float(diagnostics["turnover"].mean()) if not diagnostics.empty else 0.0,
            extra={
                "barrier": dict(barrier_meta),
                "risk_guard_summary": dict(performance.risk_guard_summary or {}),
                "sizing": dict(sizing_cfg or {}),
            },
        )
        return performance, weights, diagnostics, portfolio_meta.to_dict()

    signals = align_asset_column(asset_frames, column=signal_col, how=alignment)
    asset_returns = align_asset_column(asset_frames, column=returns_col, how=alignment)
    if returns_type == "log":
        asset_returns = np.expm1(asset_returns)
    elif returns_type != "simple":
        raise ValueError("backtest.returns_type must be 'simple' or 'log'.")
    validate_returns_frame(asset_returns, "simple")

    constraints = build_portfolio_constraints(portfolio_cfg)
    asset_groups = {str(k): str(v) for k, v in dict(portfolio_cfg.get("asset_groups", {}) or {}).items()}
    construction = str(portfolio_cfg.get("construction", "signal_weights"))
    sizing_cfg = _ftmo_sizing_config(risk_cfg)

    if sizing_cfg:
        expected_return_col = None
        exposures = _build_ftmo_sized_exposures(
            asset_frames,
            signal_col=signal_col,
            sizing_cfg=sizing_cfg,
            alignment=alignment,
        )
        weights, diagnostics = build_constrained_weights_from_exposures_over_time(
            exposures,
            constraints=constraints,
            asset_to_group=asset_groups or None,
        )
        construction = "ftmo_risk_per_trade"
    elif construction == "mean_variance":
        expected_return_col = str(portfolio_cfg.get("expected_return_col") or signal_col)
        expected_returns = align_asset_column(asset_frames, column=expected_return_col, how=alignment)
        covariance_by_date = build_rolling_covariance_by_date(
            asset_returns,
            window=int(portfolio_cfg.get("covariance_window") or 60),
            rebalance_step=int(portfolio_cfg.get("covariance_rebalance_step") or 1),
        )
        weights, diagnostics = build_optimized_weights_over_time(
            expected_returns,
            covariance_by_date=covariance_by_date,
            constraints=constraints,
            asset_to_group=asset_groups or None,
            risk_aversion=float(portfolio_cfg.get("risk_aversion", 5.0)),
            trade_aversion=float(portfolio_cfg.get("trade_aversion", 0.0)),
        )
    else:
        expected_return_col = None
        selection_cfg = dict(portfolio_cfg.get("selection", {}) or {})
        if bool(selection_cfg.get("enabled", False)):
            weights, diagnostics = build_ranked_weights_from_scores_over_time(
                signals,
                selection=selection_cfg,
                hysteresis=dict(cfg.get("execution", {}).get("hysteresis", {}) or {}),
                constraints=constraints,
                asset_to_group=asset_groups or None,
                long_short=bool(portfolio_cfg.get("long_short", True)),
                gross_target=float(portfolio_cfg.get("gross_target", 1.0)),
            )
            construction = "ranked_signal_weights"
        else:
            weights, diagnostics = build_weights_from_signals_over_time(
                signals,
                constraints=constraints,
                asset_to_group=asset_groups or None,
                long_short=bool(portfolio_cfg.get("long_short", True)),
                gross_target=float(portfolio_cfg.get("gross_target", 1.0)),
            )

    if bt_subset == "test":
        pred_is_oos_col = str(cfg.get("model", {}).get("pred_is_oos_col") or "pred_is_oos")
        oos_by_asset: dict[str, pd.Series] = {}
        for asset, frame in sorted(asset_frames.items()):
            if pred_is_oos_col not in frame.columns:
                continue
            oos_by_asset[asset] = frame[pred_is_oos_col].astype(float)
        if oos_by_asset:
            oos_df = pd.concat(oos_by_asset, axis=1, join=alignment).sort_index()
            if isinstance(oos_df.columns, pd.MultiIndex):
                oos_df.columns = oos_df.columns.get_level_values(0)
            oos_mask = oos_df.reindex(weights.index).fillna(0.0).astype(bool).all(axis=1)
            if bool(oos_mask.any()):
                weights = weights.copy()
                weights.loc[~oos_mask] = 0.0
                first_oos_label = oos_mask[oos_mask].index[0]
                weights = weights.loc[first_oos_label:]
                asset_returns = asset_returns.reindex(weights.index)
                diagnostics = diagnostics.reindex(weights.index)

    min_holding_bars = int(backtest_cfg.get("min_holding_bars", 0) or 0)
    if min_holding_bars > 0:
        weights = apply_min_holding_bars_to_weights(
            weights,
            min_holding_bars=min_holding_bars,
        )
        prev_weights = weights.shift(1).fillna(0.0)
        diagnostics = diagnostics.copy()
        diagnostics["net_exposure"] = weights.sum(axis=1).astype(float)
        diagnostics["gross_exposure"] = weights.abs().sum(axis=1).astype(float)
        diagnostics["turnover"] = (weights - prev_weights).abs().sum(axis=1).astype(float)

    performance = compute_portfolio_performance(
        weights,
        asset_returns,
        missing_return_policy=backtest_cfg.get("missing_return_policy", "raise_if_exposed"),
        cost_per_turnover=risk_cfg.get("cost_per_turnover", 0.0),
        slippage_per_turnover=risk_cfg.get("slippage_per_turnover", 0.0),
        periods_per_year=backtest_cfg.get("periods_per_year", 252),
        portfolio_guard=risk_cfg.get("portfolio_guard"),
        drawdown_sizing=risk_cfg.get("drawdown_sizing"),
    )
    if performance.applied_weights is not None:
        weights = performance.applied_weights.copy()
    if performance.risk_guard_timeline is not None and not performance.risk_guard_timeline.empty:
        diagnostics = diagnostics.join(performance.risk_guard_timeline, how="left")

    portfolio_meta = PortfolioMetaPayload(
        construction=construction,
        asset_count=int(len(asset_frames)),
        alignment=alignment,
        expected_return_col=expected_return_col,
        avg_gross_exposure=float(diagnostics["gross_exposure"].mean()) if not diagnostics.empty else 0.0,
        avg_net_exposure=float(diagnostics["net_exposure"].mean()) if not diagnostics.empty else 0.0,
        avg_turnover=float(diagnostics["turnover"].mean()) if not diagnostics.empty else 0.0,
        extra={
            "risk_guard_summary": dict(performance.risk_guard_summary or {}),
            "sizing": dict(sizing_cfg or {}),
            "selection": dict(portfolio_cfg.get("selection", {}) or {}),
            "hysteresis": dict(cfg.get("execution", {}).get("hysteresis", {}) or {}),
        },
    )
    return performance, weights, diagnostics, portfolio_meta.to_dict()


def _position_path(performance: BacktestResult | PortfolioPerformance) -> pd.Series | pd.DataFrame | None:
    if isinstance(performance, BacktestResult):
        return performance.positions
    return performance.applied_weights


def _primary_robustness_fields(payload: dict[str, Any]) -> dict[str, float]:
    fields: dict[str, float] = {}
    walk_forward = dict(payload.get("walk_forward", {}) or {})
    for key in (
        "positive_fold_ratio",
        "min_fold_cumulative_return",
        "worst_fold_max_drawdown",
        "mean_fold_sharpe",
        "std_fold_sharpe",
    ):
        if key in walk_forward:
            fields[f"robustness_walk_forward_{key}"] = float(walk_forward[key])
    cost_stress = dict(payload.get("cost_stress", {}) or {})
    for scenario, metrics in sorted(cost_stress.items()):
        if isinstance(metrics, dict):
            safe_name = str(scenario).replace(".", "_")
            for key in ("cumulative_return", "sharpe", "max_drawdown", "profit_factor"):
                if key in metrics:
                    fields[f"robustness_{safe_name}_{key}"] = float(metrics[key])
    entry_delay = dict(payload.get("entry_delay", {}) or {})
    for scenario, metrics in sorted(entry_delay.items()):
        if isinstance(metrics, dict):
            safe_name = str(scenario).replace(".", "_")
            for key in ("cumulative_return", "sharpe", "max_drawdown", "profit_factor"):
                if key in metrics:
                    fields[f"robustness_{safe_name}_{key}"] = float(metrics[key])
    gap_stress = dict(payload.get("gap_stress", {}) or {})
    gap_metrics = dict(gap_stress.get("metrics", {}) or {})
    for key in ("cumulative_return", "sharpe", "max_drawdown", "profit_factor"):
        if key in gap_metrics:
            fields[f"robustness_gap_{key}"] = float(gap_metrics[key])
    combined_stress = dict(payload.get("combined_stress", {}) or {})
    for scenario, metrics in sorted(combined_stress.items()):
        if isinstance(metrics, dict):
            safe_name = str(scenario).replace(".", "_").replace("-", "_")
            for key in (
                "cumulative_return",
                "sharpe",
                "max_drawdown",
                "profit_factor",
                "positive_asset_count",
                "positive_asset_ratio",
            ):
                if key in metrics:
                    fields[f"robustness_{safe_name}_{key}"] = float(metrics[key])
    return fields


def _run_single_asset_delay_stress(
    asset: str,
    df: pd.DataFrame,
    *,
    cfg: dict[str, Any],
    delay_bars: int,
) -> dict[str, float]:
    backtest_cfg = cfg["backtest"]
    signal_col = str(backtest_cfg["signal_col"])
    delayed = df.copy()
    delayed[signal_col] = delayed[signal_col].shift(int(delay_bars)).fillna(0.0)
    result = run_single_asset_backtest(
        asset,
        delayed,
        cfg=cfg,
        model_meta={},
    )
    returns = result.mark_to_market_returns if result.mark_to_market_returns is not None else result.returns
    return summarize_returns(
        returns,
        periods_per_year=int(backtest_cfg.get("periods_per_year", 252)),
    )


def _run_portfolio_delay_stress(
    asset_frames: dict[str, pd.DataFrame],
    *,
    cfg: dict[str, Any],
    delay_bars: int,
) -> dict[str, float]:
    signal_col = str(cfg["backtest"]["signal_col"])
    delayed_frames: dict[str, pd.DataFrame] = {}
    for asset, frame in sorted(asset_frames.items()):
        delayed = frame.copy()
        delayed[signal_col] = delayed[signal_col].shift(int(delay_bars)).fillna(0.0)
        delayed_frames[asset] = delayed
    performance, _, _, _ = run_portfolio_backtest(delayed_frames, cfg=cfg)
    returns = (
        performance.mark_to_market_returns
        if performance.mark_to_market_returns is not None
        else performance.net_returns
    )
    return summarize_returns(
        returns,
        periods_per_year=int(cfg["backtest"].get("periods_per_year", 252)),
    )


def _asset_net_contribution_summary(trades: pd.DataFrame | None, *, expected_assets: int) -> dict[str, Any]:
    if trades is None or trades.empty or "asset" not in trades.columns or "net_return" not in trades.columns:
        return {
            "positive_asset_count": 0,
            "asset_count": int(expected_assets),
            "positive_asset_ratio": 0.0,
            "asset_net_returns": {},
        }
    by_asset = (
        trades.assign(net_return=pd.to_numeric(trades["net_return"], errors="coerce").fillna(0.0))
        .groupby(trades["asset"].astype(str))["net_return"]
        .sum()
        .sort_index()
    )
    positive_count = int((by_asset > 0.0).sum())
    asset_count = int(max(expected_assets, len(by_asset)))
    return {
        "positive_asset_count": positive_count,
        "asset_count": asset_count,
        "positive_asset_ratio": float(positive_count / max(asset_count, 1)),
        "asset_net_returns": {str(asset): float(value) for asset, value in by_asset.items()},
    }


def _trade_attribution_summary(trades: pd.DataFrame | None) -> dict[str, Any]:
    if trades is None or trades.empty:
        return {}
    frame = trades.copy()
    for col in ("net_return", "realized_r", "estimated_cost_r", "bars_held"):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    out: dict[str, Any] = {"trade_count": int(len(frame))}
    if "estimated_cost_r" in frame.columns:
        cost_r = frame["estimated_cost_r"].dropna().astype(float)
        if not cost_r.empty:
            out["estimated_cost_r_quantiles"] = {
                f"q{int(q * 100):02d}": float(cost_r.quantile(q))
                for q in (0.1, 0.25, 0.5, 0.75, 0.9)
            } | {"max": float(cost_r.max())}
            bins = [0.0, 0.10, 0.15, 0.20, 0.30, float("inf")]
            labels = ["<=0.10", "0.10-0.15", "0.15-0.20", "0.20-0.30", ">0.30"]
            bucket = pd.cut(cost_r, bins=bins, labels=labels, right=True, include_lowest=True)
            bucket_frame = frame.loc[cost_r.index].assign(cost_r_bucket=bucket.astype(str))
            out["estimated_cost_r_buckets"] = _group_trade_summary(bucket_frame, "cost_r_bucket")
    if "exit_reason" in frame.columns:
        out["exit_reason"] = _group_trade_summary(frame, "exit_reason")
    return out


def _group_trade_summary(frame: pd.DataFrame, group_col: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if group_col not in frame.columns:
        return out
    for key, group in frame.groupby(frame[group_col].astype(str), sort=True):
        net = (
            pd.to_numeric(group["net_return"], errors="coerce").fillna(0.0)
            if "net_return" in group.columns
            else pd.Series(0.0, index=group.index)
        )
        realized_r = (
            pd.to_numeric(group["realized_r"], errors="coerce").dropna()
            if "realized_r" in group.columns
            else pd.Series(dtype=float)
        )
        out[str(key)] = {
            "trade_count": int(len(group)),
            "net_return": float(net.sum()),
            "avg_r": float(realized_r.mean()) if not realized_r.empty else float("nan"),
            "win_rate": float((realized_r > 0.0).mean()) if not realized_r.empty else float("nan"),
        }
    return out


def _run_portfolio_combined_stress(
    asset_frames: dict[str, pd.DataFrame],
    *,
    cfg: dict[str, Any],
    event_time_remap_policy: str,
    gross_cap: float,
    cost_multiplier: float,
    max_cost_r: float | None = None,
) -> dict[str, Any]:
    variant_cfg = deepcopy(cfg)
    variant_cfg["backtest"] = dict(variant_cfg.get("backtest", {}) or {})
    variant_cfg["backtest"]["event_time_remap_policy"] = str(event_time_remap_policy)
    if max_cost_r is None:
        variant_cfg["backtest"].pop("max_cost_r", None)
    else:
        variant_cfg["backtest"]["max_cost_r"] = float(max_cost_r)

    variant_cfg["risk"] = dict(variant_cfg.get("risk", {}) or {})
    variant_cfg["risk"]["cost_per_turnover"] = (
        float(cfg.get("risk", {}).get("cost_per_turnover", 0.0)) * float(cost_multiplier)
    )
    variant_cfg["risk"]["slippage_per_turnover"] = (
        float(cfg.get("risk", {}).get("slippage_per_turnover", 0.0)) * float(cost_multiplier)
    )

    variant_cfg["portfolio"] = dict(variant_cfg.get("portfolio", {}) or {})
    constraints = dict(variant_cfg["portfolio"].get("constraints", {}) or {})
    constraints["max_gross_leverage"] = float(gross_cap)
    variant_cfg["portfolio"]["constraints"] = constraints

    performance, _, diagnostics, meta = run_portfolio_backtest(asset_frames, cfg=variant_cfg)
    returns = (
        performance.mark_to_market_returns
        if performance.mark_to_market_returns is not None
        else performance.net_returns
    )
    metrics = summarize_returns(
        returns,
        periods_per_year=int(variant_cfg["backtest"].get("periods_per_year", 252)),
    )
    barrier_meta = dict(meta.get("barrier", {}) or {})
    trades = getattr(performance, "trades", None)
    trade_count = int(barrier_meta.get("trade_count", len(trades) if trades is not None else 0))
    metrics.update(
        {
            "event_time_remap_policy": str(event_time_remap_policy),
            "gross_cap": float(gross_cap),
            "cost_multiplier": float(cost_multiplier),
            "max_cost_r": None if max_cost_r is None else float(max_cost_r),
            "trade_count": trade_count,
            "avg_gross_exposure": float(diagnostics["gross_exposure"].mean()) if not diagnostics.empty else 0.0,
            "max_gross_exposure": float(diagnostics["gross_exposure"].max()) if not diagnostics.empty else 0.0,
        }
    )
    for key in (
        "remapped_entry_timestamps",
        "remapped_exit_timestamps",
        "skipped_remapped_event_timestamps",
        "skipped_remapped_entry_timestamps",
        "skipped_remapped_exit_timestamps",
        "skipped_unalignable_timestamp",
        "skipped_cost_filter",
    ):
        if key in barrier_meta:
            metrics[key] = int(barrier_meta[key])
    metrics["trade_attribution"] = _trade_attribution_summary(trades)
    metrics.update(
        _asset_net_contribution_summary(
            getattr(performance, "trades", None),
            expected_assets=len(asset_frames),
        )
    )
    return metrics


def build_robustness_diagnostics(
    asset_frames: dict[str, pd.DataFrame],
    *,
    cfg: dict[str, Any],
    performance: BacktestResult | PortfolioPerformance,
    is_portfolio: bool,
) -> dict[str, Any]:
    diagnostics_cfg = dict(cfg.get("diagnostics", {}) or {})
    robustness_cfg = dict(diagnostics_cfg.get("robustness", {}) or {})
    if not bool(robustness_cfg.get("enabled", False)):
        return {}

    periods_per_year = int(cfg["backtest"].get("periods_per_year", 252))
    if isinstance(performance, BacktestResult):
        net_returns = performance.returns
        gross_returns = performance.gross_returns
        costs = performance.costs
    else:
        net_returns = performance.net_returns
        gross_returns = performance.gross_returns
        costs = performance.costs
    mark_to_market_returns = getattr(performance, "mark_to_market_returns", None)
    position_path = _position_path(performance)

    cost_multipliers = list(robustness_cfg.get("cost_multipliers", [1.0, 2.0, 3.0, 5.0]) or [])
    entry_delay_bars = [
        int(value)
        for value in list(robustness_cfg.get("entry_delay_bars", [1, 2]) or [])
        if int(value) > 0
    ]
    combined_cost_multipliers = [
        float(value)
        for value in list(robustness_cfg.get("combined_cost_multipliers", []) or [])
    ]
    gross_cap_values = [
        float(value)
        for value in list(robustness_cfg.get("gross_cap_values", []) or [])
    ]
    cost_filter_max_cost_r_values = [
        float(value)
        for value in list(robustness_cfg.get("cost_filter_max_cost_r_values", []) or [])
    ]
    payload: dict[str, Any] = {
        "cost_stress": cost_multiplier_stress(
            gross_returns=gross_returns,
            costs=costs,
            periods_per_year=periods_per_year,
            multipliers=cost_multipliers,
        ),
        "walk_forward": calendar_walk_forward_diagnostics(
            mark_to_market_returns if mark_to_market_returns is not None else net_returns,
            periods_per_year=periods_per_year,
            frequency=str(robustness_cfg.get("walk_forward_frequency", "YE") or "YE"),
        ),
        "mark_to_market": dict(getattr(performance, "mark_to_market_summary", {}) or {}),
        "entry_delay": {},
    }
    if is_portfolio and (
        bool(robustness_cfg.get("strict_no_remap", False))
        or bool(combined_cost_multipliers)
        or bool(gross_cap_values)
    ):
        base_gross_cap = float(
            dict(cfg.get("portfolio", {}).get("constraints", {}) or {}).get(
                "max_gross_leverage",
                cfg.get("portfolio", {}).get("gross_target", 1.0),
            )
        )
        remap_policy = (
            "skip" if bool(robustness_cfg.get("strict_no_remap", False))
            else str(cfg["backtest"].get("event_time_remap_policy", "next_aligned"))
        )
        if not combined_cost_multipliers:
            combined_cost_multipliers = [1.0]
        if not gross_cap_values:
            gross_cap_values = [base_gross_cap]
        max_cost_r_values: list[float | None] = [None]
        max_cost_r_values.extend(cost_filter_max_cost_r_values)
        payload["combined_stress"] = {}
        for gross_cap in gross_cap_values:
            for cost_multiplier in combined_cost_multipliers:
                for max_cost_r in max_cost_r_values:
                    suffix = "" if max_cost_r is None else f"_maxcostr_{max_cost_r:g}"
                    key = f"strict_{remap_policy}_gross_{gross_cap:g}_cost_x{cost_multiplier:g}{suffix}"
                    try:
                        payload["combined_stress"][key] = _run_portfolio_combined_stress(
                            asset_frames,
                            cfg=cfg,
                            event_time_remap_policy=remap_policy,
                            gross_cap=float(gross_cap),
                            cost_multiplier=float(cost_multiplier),
                            max_cost_r=max_cost_r,
                        )
                    except Exception as exc:
                        payload["combined_stress"][key] = {"error": f"{type(exc).__name__}: {exc}"}

    if position_path is not None:
        payload["gap_stress"] = gap_penalty_stress(
            returns=mark_to_market_returns if mark_to_market_returns is not None else net_returns,
            positions=position_path,
            periods_per_year=periods_per_year,
            gap_loss_per_exposure=float(robustness_cfg.get("gap_loss_per_exposure", 0.0) or 0.0),
            max_gap_multiple=float(robustness_cfg.get("max_gap_multiple", 3.0) or 3.0),
        )

    for delay in entry_delay_bars:
        key = f"delay_{delay}_bars"
        try:
            if is_portfolio:
                payload["entry_delay"][key] = _run_portfolio_delay_stress(
                    asset_frames,
                    cfg=cfg,
                    delay_bars=delay,
                )
            else:
                asset = next(iter(sorted(asset_frames)))
                payload["entry_delay"][key] = _run_single_asset_delay_stress(
                    asset,
                    asset_frames[asset],
                    cfg=cfg,
                    delay_bars=delay,
                )
        except Exception as exc:
            payload["entry_delay"][key] = {"error": f"{type(exc).__name__}: {exc}"}

    payload["primary_summary_fields"] = _primary_robustness_fields(payload)
    return payload


__all__ = [
    "build_portfolio_constraints",
    "build_robustness_diagnostics",
    "resolve_vol_col",
    "run_portfolio_backtest",
    "run_single_asset_backtest",
    "validate_returns_frame",
    "validate_returns_series",
]
