from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import compute_backtest_metrics
from src.experiments.contracts import TargetContract, validate_feature_target_contract
from src.experiments.models import train_lightgbm_classifier
from src.src_data.pit import (
    align_ohlcv_timestamps,
    apply_corporate_actions_policy,
    assert_symbol_in_snapshot,
    load_universe_snapshot,
)


def _synthetic_frame(n: int = 240) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    base = rng.normal(0.0005, 0.01, size=n)
    close = 100.0 * np.exp(np.cumsum(base))
    idx = pd.date_range("2021-01-01", periods=n, freq="D")

    df = pd.DataFrame({"close": close}, index=idx)
    df["feat_1"] = pd.Series(base, index=idx).shift(1)
    df["feat_2"] = pd.Series(base, index=idx).rolling(10, min_periods=2).std()
    return df


def test_forward_horizon_guard_trims_train_rows_in_time_split() -> None:
    df = _synthetic_frame()
    horizon = 5

    _, _, meta = train_lightgbm_classifier(
        df=df,
        model_cfg={
            "params": {"n_estimators": 20, "learning_rate": 0.05},
            "feature_cols": ["feat_1", "feat_2"],
            "target": {"kind": "forward_return", "price_col": "close", "horizon": horizon},
            "runtime": {"seed": 7, "deterministic": True, "threads": 1, "repro_mode": "strict"},
            "split": {"method": "time", "train_frac": 0.7},
        },
    )

    first_fold = meta["folds"][0]
    assert first_fold["effective_train_end"] == first_fold["test_start"] - horizon
    assert first_fold["trimmed_for_horizon_rows"] == horizon
    assert meta["anti_leakage"]["total_trimmed_train_rows"] >= horizon


def test_feature_contract_rejects_target_like_feature_columns() -> None:
    df = pd.DataFrame(
        {
            "f1": [0.1, 0.2, 0.3],
            "target_fwd_1": [0.01, 0.02, 0.03],
            "label": [0, 1, 0],
        }
    )
    with pytest.raises(ValueError):
        validate_feature_target_contract(
            df,
            feature_cols=["f1", "target_fwd_1"],
            target=TargetContract(target_col="label", horizon=1),
        )


def test_metrics_suite_includes_risk_and_cost_attribution() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    net_returns = pd.Series([0.03, -0.02, 0.01, -0.01], index=idx)
    gross_returns = pd.Series([0.031, -0.019, 0.011, -0.009], index=idx)
    costs = pd.Series([0.001, 0.001, 0.001, 0.001], index=idx)
    turnover = pd.Series([0.0, 1.0, 0.5, 0.2], index=idx)

    metrics = compute_backtest_metrics(
        net_returns=net_returns,
        periods_per_year=252,
        turnover=turnover,
        costs=costs,
        gross_returns=gross_returns,
    )

    for key in (
        "sortino",
        "calmar",
        "profit_factor",
        "hit_rate",
        "avg_turnover",
        "total_turnover",
        "total_cost",
        "cost_drag",
    ):
        assert key in metrics

    assert np.isclose(metrics["profit_factor"], 4.0 / 3.0)
    assert np.isclose(metrics["hit_rate"], 0.5)
    assert np.isclose(metrics["total_turnover"], 1.7)
    assert np.isclose(metrics["total_cost"], 0.004)
    assert np.isclose(metrics["cost_drag"], 0.004)


def test_align_ohlcv_timestamps_sorts_and_deduplicates() -> None:
    idx = pd.to_datetime(
        [
            "2024-01-02 16:00:00",
            "2024-01-01 16:00:00",
            "2024-01-01 16:00:00",
        ]
    )
    df = pd.DataFrame(
        {
            "open": [11.0, 10.0, 10.5],
            "high": [12.0, 11.0, 11.5],
            "low": [10.5, 9.5, 10.0],
            "close": [11.5, 10.2, 10.7],
            "volume": [100, 200, 300],
        },
        index=idx,
    )

    out = align_ohlcv_timestamps(
        df,
        source_timezone="America/New_York",
        output_timezone="UTC",
        normalize_daily=True,
        duplicate_policy="last",
    )

    assert out.index.is_monotonic_increasing
    assert not out.index.has_duplicates
    assert len(out) == 2
    assert np.isclose(out.loc[pd.Timestamp("2024-01-01"), "close"], 10.7)


def test_apply_corporate_actions_policy_adj_close_ratio() -> None:
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    df = pd.DataFrame(
        {
            "open": [100.0, 50.0],
            "high": [102.0, 51.0],
            "low": [99.0, 49.0],
            "close": [100.0, 50.0],
            "adj_close": [50.0, 25.0],
            "volume": [1000.0, 1200.0],
        },
        index=idx,
    )

    out, meta = apply_corporate_actions_policy(df, policy="adj_close_ratio")
    assert meta["policy"] == "adj_close_ratio"
    assert np.isclose(out.loc[idx[0], "open"], 50.0)
    assert np.isclose(out.loc[idx[1], "high"], 25.5)
    assert np.isclose(out.loc[idx[0], "close"], 50.0)
    assert "pit_adjustment_factor" in out.columns


def test_universe_snapshot_asof_membership_check(tmp_path) -> None:
    snapshot_path = tmp_path / "universe_snapshot.csv"
    pd.DataFrame(
        {
            "symbol": ["SPY", "QQQ"],
            "effective_from": ["2010-01-01", "2021-01-01"],
            "effective_to": [None, None],
        }
    ).to_csv(snapshot_path, index=False)

    snap = load_universe_snapshot(snapshot_path)
    assert_symbol_in_snapshot("SPY", snap, as_of="2020-06-01")
    with pytest.raises(ValueError):
        assert_symbol_in_snapshot("QQQ", snap, as_of="2020-06-01")

