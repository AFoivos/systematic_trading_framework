from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.experiments.support.c2_scalp_grid import (
    C2ScalpVariant,
    default_c2_scalp_variants,
    run_c2_scalp_grid_for_frame,
    write_c2_scalp_grid_artifacts,
)


def _cfg() -> dict:
    return {
        "risk": {
            "cost_per_turnover": 0.00015,
            "slippage_per_turnover": 0.00010,
            "max_leverage": 1.0,
        },
        "backtest": {
            "signal_col": "c2_signal",
            "open_col": "open",
            "high_col": "high",
            "low_col": "low",
            "close_col": "close",
            "risk_per_trade": 0.006,
            "periods_per_year": 12096,
            "stop_mode": "volatility_stop",
            "vol_col": "atr_over_price_14",
            "dynamic_exits": {},
        },
    }


def _signaled_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=16, freq="30min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100.0] * len(idx),
            "high": [100.3] * len(idx),
            "low": [99.7] * len(idx),
            "close": [100.0] * len(idx),
            "close_ret": [0.0] * len(idx),
            "atr_over_price_14": [0.01] * len(idx),
            "c2_signal": [0.0] * len(idx),
        },
        index=idx,
    )
    frame.loc[idx[2], "c2_signal"] = 1.0
    frame.loc[idx[3], "high"] = 101.0
    frame.loc[idx[9], "c2_signal"] = -1.0
    frame.loc[idx[10], "low"] = 99.0
    return frame


def test_default_c2_scalp_variants_are_small_side_split_grid() -> None:
    variants = default_c2_scalp_variants()

    assert len(variants) == 12
    assert len({variant.name for variant in variants}) == len(variants)
    assert {variant.side_mode for variant in variants} == {"long_only", "short_only"}
    assert {variant.horizon_bars for variant in variants} == {4, 6, 8}


def test_c2_scalp_grid_for_frame_returns_expected_metrics() -> None:
    variants = [
        C2ScalpVariant(
            "long_test",
            horizon_bars=2,
            take_profit_atr=0.8,
            stop_loss_atr=0.6,
            side_mode="long_only",
        ),
        C2ScalpVariant(
            "short_test",
            horizon_bars=2,
            take_profit_atr=0.8,
            stop_loss_atr=0.6,
            side_mode="short_only",
        ),
    ]

    result = run_c2_scalp_grid_for_frame(_signaled_frame(), _cfg(), variants=variants, asset="SPX500")
    results = result["results"]

    assert result["variant_count"] == 2
    assert len(results) == 2
    assert set(results["name"]) == {"long_test", "short_test"}
    assert set(results["trade_count"]) == {1}
    assert results.loc[results["name"].eq("long_test"), "long_trade_count"].iloc[0] == 1
    assert results.loc[results["name"].eq("short_test"), "short_trade_count"].iloc[0] == 1
    for column in [
        "gross_pnl_per_trade",
        "cost_per_trade",
        "net_pnl_per_trade",
        "cost_x0_cumulative_return",
        "cost_x2_cumulative_return",
        "passes_cost_diagnostic",
    ]:
        assert column in results.columns


def test_c2_scalp_grid_artifacts_are_written(tmp_path: Path) -> None:
    result = run_c2_scalp_grid_for_frame(
        _signaled_frame(),
        _cfg(),
        variants=[
            C2ScalpVariant(
                "long_test",
                horizon_bars=2,
                take_profit_atr=0.8,
                stop_loss_atr=0.6,
                side_mode="long_only",
            )
        ],
        asset="SPX500",
    )

    artifacts = write_c2_scalp_grid_artifacts(
        result,
        config_path="config/experiments/c2_30m_regime_aware_momentum_v1.yaml",
        output_dir=tmp_path,
        run_name="unit_grid",
    )

    assert Path(artifacts["results_csv"]).exists()
    assert Path(artifacts["trades_csv"]).exists()
    assert Path(artifacts["summary_json"]).exists()
