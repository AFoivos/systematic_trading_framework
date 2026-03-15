from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.backtesting.engine import BacktestResult
from src.portfolio import PortfolioPerformance


@dataclass
class ExperimentResult:
    """
    Collect the full output of an experiment run, including resolved config, transformed data,
    fitted models, evaluation payloads, execution artifacts, and portfolio weights.
    """
    config: dict[str, Any]
    data: pd.DataFrame | dict[str, pd.DataFrame]
    backtest: BacktestResult | PortfolioPerformance
    model: object | dict[str, object] | None
    model_meta: dict[str, Any]
    artifacts: dict[str, str]
    evaluation: dict[str, Any]
    monitoring: dict[str, Any]
    execution: dict[str, Any]
    portfolio_weights: pd.DataFrame | None = None


__all__ = ["ExperimentResult"]
