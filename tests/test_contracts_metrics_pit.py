from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import compute_backtest_metrics
from src.experiments.contracts import TargetContract, validate_feature_target_contract
from src.experiments.models import train_lightgbm_classifier
from src.features.technical.indicators import compute_mfi
from src.features.technical.oscillators import compute_rsi
from src.src_data.pit import (
    align_ohlcv_timestamps,
    apply_corporate_actions_policy,
    apply_pit_hardening,
    assert_symbol_in_snapshot,
    load_universe_snapshot,
)
from src.utils.config import load_experiment_config


def _synthetic_frame(n: int = 240) -> pd.DataFrame:
    """
    Verify that synthetic frame behaves as expected under a representative regression scenario.
    The test protects the intended contract of the surrounding component and makes failures
    easier to localize.
    """
    rng = np.random.default_rng(11)
    base = rng.normal(0.0005, 0.01, size=n)
    close = 100.0 * np.exp(np.cumsum(base))
    idx = pd.date_range("2021-01-01", periods=n, freq="D")

    df = pd.DataFrame({"close": close}, index=idx)
    df["feat_1"] = pd.Series(base, index=idx).shift(1)
    df["feat_2"] = pd.Series(base, index=idx).rolling(10, min_periods=2).std()
    return df


def test_forward_horizon_guard_trims_train_rows_in_time_split() -> None:
    """
    Verify that forward horizon guard trims train rows in time split behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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
    """
    Verify that feature contract rejects target like feature columns behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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
    """
    Verify that metrics suite includes risk and cost attribution behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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


def test_rsi_saturates_to_100_in_monotonic_uptrend() -> None:
    """
    Verify that RSI saturates to 100 in monotonic uptrend behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], dtype=float)
    rsi = compute_rsi(prices, window=3)

    assert np.isclose(float(rsi.iloc[-1]), 100.0)


def test_mfi_saturates_to_100_when_negative_flow_is_zero() -> None:
    """
    Verify that MFI saturates to 100 when negative flow is zero behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    high = pd.Series([2, 3, 4, 5, 6, 7, 8], dtype=float)
    low = pd.Series([1, 2, 3, 4, 5, 6, 7], dtype=float)
    close = pd.Series([1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5], dtype=float)
    volume = pd.Series([100.0] * len(high), dtype=float)
    mfi = compute_mfi(high, low, close, volume, window=3)

    assert np.isclose(float(mfi.iloc[-1]), 100.0)


def test_align_ohlcv_timestamps_sorts_and_deduplicates() -> None:
    """
    Verify that align OHLCV timestamps sorts and deduplicates behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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


def test_intraday_configs_do_not_normalize_timestamps_by_default(tmp_path) -> None:
    """
    Verify that intraday configs do not normalize timestamps by default behaves as expected
    under a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    intraday_cfg = tmp_path / "intraday.yaml"
    intraday_cfg.write_text(
        """
data:
  symbol: "SPY"
  interval: "1h"
backtest:
  returns_col: "close_ret"
  signal_col: "signal"
""".strip(),
        encoding="utf-8",
    )

    daily_cfg = tmp_path / "daily.yaml"
    daily_cfg.write_text(
        """
data:
  symbol: "SPY"
  interval: "1d"
backtest:
  returns_col: "close_ret"
  signal_col: "signal"
""".strip(),
        encoding="utf-8",
    )

    intraday = load_experiment_config(intraday_cfg)
    daily = load_experiment_config(daily_cfg)

    assert intraday["data"]["pit"]["timestamp_alignment"]["normalize_daily"] is False
    assert daily["data"]["pit"]["timestamp_alignment"]["normalize_daily"] is True


def test_apply_corporate_actions_policy_adj_close_ratio() -> None:
    """
    Verify that corporate actions policy adj close ratio behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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
    """
    Verify that universe snapshot asof membership check behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
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


def test_apply_pit_hardening_raises_when_symbol_exits_universe_mid_sample(tmp_path) -> None:
    """
    Verify that PIT hardening raises when symbol exits universe mid sample behaves as expected
    under a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    snapshot_path = tmp_path / "universe_snapshot.csv"
    pd.DataFrame(
        {
            "symbol": ["SPY"],
            "effective_from": ["2020-01-01"],
            "effective_to": ["2020-01-02"],
        }
    ).to_csv(snapshot_path, index=False)

    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "open": [1.0, 1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0, 1.0],
            "volume": [1.0, 1.0, 1.0, 1.0],
        },
        index=idx,
    )

    with pytest.raises(ValueError):
        apply_pit_hardening(
            df,
            pit_cfg={"universe_snapshot": {"path": str(snapshot_path)}},
            symbol="SPY",
        )


def test_apply_pit_hardening_can_drop_rows_outside_universe_snapshot(tmp_path) -> None:
    """
    Verify that PIT hardening can drop rows outside universe snapshot behaves as expected under
    a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    snapshot_path = tmp_path / "universe_snapshot.csv"
    pd.DataFrame(
        {
            "symbol": ["SPY"],
            "effective_from": ["2020-01-01"],
            "effective_to": ["2020-01-02"],
        }
    ).to_csv(snapshot_path, index=False)

    idx = pd.date_range("2020-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "open": [1.0, 1.0, 1.0, 1.0],
            "high": [1.0, 1.0, 1.0, 1.0],
            "low": [1.0, 1.0, 1.0, 1.0],
            "close": [1.0, 1.0, 1.0, 1.0],
            "volume": [1.0, 1.0, 1.0, 1.0],
        },
        index=idx,
    )

    out, meta = apply_pit_hardening(
        df,
        pit_cfg={
            "universe_snapshot": {
                "path": str(snapshot_path),
                "inactive_policy": "drop_inactive_rows",
            }
        },
        symbol="SPY",
    )

    assert len(out) == 2
    assert meta["universe_snapshot"]["inactive_rows"] == 2
