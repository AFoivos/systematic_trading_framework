from __future__ import annotations

import pandas as pd

from src.backtesting.engine import BacktestResult
from src.experiments.support.barrier_probability import _regime_reports


def test_regime_performance_is_attributed_at_trade_signal_timestamp() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="h")
    frame = pd.DataFrame(
        {
            "session_asia": [1.0, 1.0, 0.0, 0.0, 0.0],
            "session_london": [0.0, 0.0, 1.0, 1.0, 1.0],
            "atr_percentile_20": [0.1, 0.2, 0.5, 0.8, 0.9],
            "shannon_entropy_percentile_20": [0.2, 0.3, 0.5, 0.8, 0.9],
            "variance_ratio_4_20": [0.8, 0.85, 1.0, 1.2, 1.3],
        },
        index=index,
    )
    zeros = pd.Series(0.0, index=index)
    performance = BacktestResult(
        equity_curve=pd.Series(1.0, index=index),
        returns=zeros,
        gross_returns=zeros,
        costs=zeros,
        positions=zeros,
        turnover=zeros,
        summary={},
        trades=pd.DataFrame(
            {
                "signal_timestamp": [index[1], index[3]],
                "side": ["long", "short"],
                "net_return": [0.02, -0.01],
            }
        ),
    )

    reports = _regime_reports(frame, performance)

    assert {row["group"] for row in reports["hour"]} == {"1", "3"}
    session_returns = {
        row["group"]: row["mean_return"] for row in reports["session"]
    }
    assert session_returns == {"asia": 0.02, "london": -0.01}
    side_returns = {row["group"]: row["mean_return"] for row in reports["side"]}
    assert side_returns == {"long": 0.02, "short": -0.01}
