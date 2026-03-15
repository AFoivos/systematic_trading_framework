from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestResult, run_backtest
from src.experiments.orchestration.common import align_asset_column
from src.portfolio import (
    PortfolioConstraints,
    PortfolioPerformance,
    build_optimized_weights_over_time,
    build_rolling_covariance_by_date,
    build_weights_from_signals_over_time,
    compute_portfolio_performance,
)
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
    return PortfolioConstraints(
        min_weight=float(constraints_cfg.get("min_weight", -1.0)),
        max_weight=float(constraints_cfg.get("max_weight", 1.0)),
        max_gross_leverage=float(constraints_cfg.get("max_gross_leverage", 1.0)),
        target_net_exposure=float(constraints_cfg.get("target_net_exposure", 0.0)),
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

    dd_cfg = risk_cfg.get("dd_guard") or {}
    dd_guard = dd_cfg.get("enabled", True)
    vol_col = resolve_vol_col(df, backtest_cfg, risk_cfg)
    target_vol = risk_cfg.get("target_vol")
    if target_vol is not None and vol_col is None:
        raise ValueError("target_vol is set but no vol_col was found or configured.")

    bt_df = df
    if model_meta and model_meta.get("split_index") is not None:
        bt_subset = backtest_cfg.get("subset", "test")
        if bt_subset == "test":
            bt_df = df.iloc[int(model_meta["split_index"]) :]

    return run_backtest(
        bt_df,
        signal_col=signal_col,
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
        periods_per_year=backtest_cfg.get("periods_per_year", 252),
    )


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

    if construction == "mean_variance":
        expected_return_col = str(portfolio_cfg.get("expected_return_col") or signal_col)
        expected_returns = align_asset_column(asset_frames, column=expected_return_col, how=alignment)
        covariance_by_date = build_rolling_covariance_by_date(
            asset_returns,
            window=int(portfolio_cfg.get("covariance_window", 60)),
            rebalance_step=int(portfolio_cfg.get("covariance_rebalance_step", 1)),
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
        weights, diagnostics = build_weights_from_signals_over_time(
            signals,
            constraints=constraints,
            asset_to_group=asset_groups or None,
            long_short=bool(portfolio_cfg.get("long_short", True)),
            gross_target=float(portfolio_cfg.get("gross_target", 1.0)),
        )

    performance = compute_portfolio_performance(
        weights,
        asset_returns,
        missing_return_policy=backtest_cfg.get("missing_return_policy", "raise_if_exposed"),
        cost_per_turnover=risk_cfg.get("cost_per_turnover", 0.0),
        slippage_per_turnover=risk_cfg.get("slippage_per_turnover", 0.0),
        periods_per_year=backtest_cfg.get("periods_per_year", 252),
    )

    portfolio_meta = PortfolioMetaPayload(
        construction=construction,
        asset_count=int(len(asset_frames)),
        alignment=alignment,
        expected_return_col=expected_return_col,
        avg_gross_exposure=float(diagnostics["gross_exposure"].mean()) if not diagnostics.empty else 0.0,
        avg_net_exposure=float(diagnostics["net_exposure"].mean()) if not diagnostics.empty else 0.0,
        avg_turnover=float(diagnostics["turnover"].mean()) if not diagnostics.empty else 0.0,
    )
    return performance, weights, diagnostics, portfolio_meta.to_dict()


__all__ = [
    "build_portfolio_constraints",
    "resolve_vol_col",
    "run_portfolio_backtest",
    "run_single_asset_backtest",
    "validate_returns_frame",
    "validate_returns_series",
]
