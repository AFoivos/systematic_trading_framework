from __future__ import annotations

import pandas as pd

from src.backtesting.engine import BacktestResult
from src.execution.paper import build_rebalance_orders
from src.experiments.orchestration.common import align_asset_column
from src.experiments.schemas import ExecutionPayload
from src.portfolio import PortfolioPerformance


def build_execution_output(
    *,
    asset_frames: dict[str, pd.DataFrame],
    execution_cfg: dict[str, object],
    portfolio_weights: pd.DataFrame | None,
    performance: BacktestResult | PortfolioPerformance,
    alignment: str,
) -> tuple[dict[str, object], pd.DataFrame | None]:
    if not bool(execution_cfg.get("enabled", False)):
        return {}, None

    capital = float(execution_cfg.get("capital", 1_000_000.0))
    price_col = str(execution_cfg.get("price_col", "close"))
    current_weights_cfg = dict(execution_cfg.get("current_weights", {}) or {})
    current_weights = pd.Series(current_weights_cfg, dtype=float) if current_weights_cfg else None

    if portfolio_weights is not None and (portfolio_weights.empty or len(portfolio_weights.columns) == 0):
        empty_orders = pd.DataFrame(columns=["target_weight", "current_weight", "delta_weight", "price"])
        payload = ExecutionPayload(
            mode="paper",
            capital=capital,
            as_of=None,
            order_count=0,
            gross_target=0.0,
        )
        return payload.to_dict(), empty_orders

    if portfolio_weights is not None:
        target_weights = portfolio_weights.iloc[-1].astype(float)
        prices = align_asset_column(asset_frames, column=price_col, how=alignment).reindex(portfolio_weights.index)
        latest_prices = prices.iloc[-1].astype(float)
        as_of = portfolio_weights.index[-1]
    else:
        asset = next(iter(sorted(asset_frames)))
        bt = performance
        assert isinstance(bt, BacktestResult)
        if bt.positions.empty or bt.returns.empty:
            empty_orders = pd.DataFrame(columns=["target_weight", "current_weight", "delta_weight", "price"])
            payload = ExecutionPayload(
                mode="paper",
                capital=capital,
                as_of=None,
                order_count=0,
                gross_target=0.0,
            )
            return payload.to_dict(), empty_orders
        target_weights = pd.Series({asset: float(bt.positions.iloc[-1])}, dtype=float)
        latest_price = float(asset_frames[asset][price_col].reindex(bt.returns.index).iloc[-1])
        latest_prices = pd.Series({asset: latest_price}, dtype=float)
        as_of = bt.returns.index[-1]

    orders = build_rebalance_orders(
        target_weights,
        prices=latest_prices,
        capital=capital,
        current_weights=current_weights,
        min_trade_notional=float(execution_cfg.get("min_trade_notional", 0.0)),
    )
    payload = ExecutionPayload(
        mode="paper",
        capital=capital,
        as_of=str(pd.Timestamp(as_of)),
        order_count=int(len(orders)),
        gross_target=float(target_weights.abs().sum()),
    )
    return payload.to_dict(), orders


__all__ = ["build_execution_output"]
