from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import annualized_return, compute_backtest_metrics
from src.experiments.contracts import TargetContract, validate_feature_target_contract
from src.experiments.models import train_logistic_regression_classifier
from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.features.technical.indicators import compute_mfi
from src.features.technical.oscillators import compute_rsi
from src.features.technical.stochastic_rsi import add_stochastic_rsi_features
from src.models.common.runtime import classify_feature_family
from src.src_data.pit import (
    align_ohlcv_timestamps,
    apply_corporate_actions_policy,
    apply_pit_hardening,
    assert_symbol_in_snapshot,
    load_universe_snapshot,
)
from src.utils.config import ConfigError, ResolvedExperimentConfig, load_experiment_config, load_experiment_config_typed
from src.utils.config_validation import validate_features_block


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


def _synthetic_ohlcv_for_stochastic_rsi(n: int = 80) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    steps = 0.002 * np.sin(np.arange(n) / 2.0) + 0.0003 * np.cos(np.arange(n) / 5.0)
    close = 100.0 * np.exp(np.cumsum(steps))
    frame = pd.DataFrame(index=idx)
    frame["close"] = close
    frame["open"] = frame["close"].shift(1).fillna(frame["close"].iloc[0])
    frame["high"] = np.maximum(frame["open"], frame["close"]) * 1.001
    frame["low"] = np.minimum(frame["open"], frame["close"]) * 0.999
    frame["volume"] = 1000.0
    return frame[["open", "high", "low", "close", "volume"]]


def test_forward_horizon_guard_trims_train_rows_in_time_split() -> None:
    """
    Verify that forward horizon guard trims train rows in time split behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    df = _synthetic_frame()
    horizon = 5

    _, _, meta = train_logistic_regression_classifier(
        df=df,
        model_cfg={
            "params": {"max_iter": 1000, "solver": "lbfgs"},
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


def test_annualized_return_is_nan_after_non_positive_terminal_wealth() -> None:
    """
    Annualized return should be undefined once the cumulative path breaches non-positive wealth.
    """
    out = annualized_return(pd.Series([-1.5], dtype=float), periods_per_year=252)
    assert np.isnan(out)


def test_rsi_saturates_to_100_in_monotonic_uptrend() -> None:
    """
    Verify that RSI saturates to 100 in monotonic uptrend behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], dtype=float)
    rsi = compute_rsi(prices, window=3)

    assert np.isclose(float(rsi.iloc[-1]), 100.0)


def test_stochastic_rsi_features_emit_expected_columns_and_values() -> None:
    df = _synthetic_ohlcv_for_stochastic_rsi()

    out = add_stochastic_rsi_features(
        df,
        price_col="close",
        rsi_period=5,
        stoch_period=6,
        k_period=2,
        d_period=3,
        oversold=0.2,
        overbought=0.8,
    )

    expected = [
        "stoch_rsi_k",
        "stoch_rsi_d",
        "stoch_rsi_k_minus_d",
        "stoch_rsi_cross_up",
        "stoch_rsi_cross_down",
        "stoch_rsi_oversold",
        "stoch_rsi_overbought",
        "stoch_rsi_slope",
        "stoch_rsi_recover_from_oversold",
    ]
    assert out.columns[-len(expected) :].tolist() == expected
    assert out["stoch_rsi_k"].dropna().between(0.0, 1.0).all()
    assert out["stoch_rsi_d"].dropna().between(0.0, 1.0).all()

    for column in [
        "stoch_rsi_cross_up",
        "stoch_rsi_cross_down",
        "stoch_rsi_oversold",
        "stoch_rsi_overbought",
        "stoch_rsi_recover_from_oversold",
    ]:
        assert set(out[column].dropna().unique()).issubset({0, 1})

    pd.testing.assert_series_equal(
        out["stoch_rsi_k_minus_d"],
        out["stoch_rsi_k"] - out["stoch_rsi_d"],
        check_names=False,
    )
    pd.testing.assert_series_equal(
        out["stoch_rsi_slope"],
        out["stoch_rsi_k"] - out["stoch_rsi_k"].shift(1),
        check_names=False,
    )


def test_stochastic_rsi_features_are_point_in_time_safe() -> None:
    df = _synthetic_ohlcv_for_stochastic_rsi()
    future = df.tail(3).copy()
    future.index = pd.date_range(df.index[-1], periods=4, freq="h")[1:]
    future["close"] = [500.0, 250.0, 750.0]

    params = {
        "price_col": "close",
        "rsi_period": 5,
        "stoch_period": 6,
        "k_period": 2,
        "d_period": 2,
    }
    base = add_stochastic_rsi_features(df, **params)
    extended = add_stochastic_rsi_features(pd.concat([df, future]), **params)
    cols = [column for column in base.columns if column.startswith("stoch_rsi_")]

    pd.testing.assert_frame_equal(base[cols], extended.loc[df.index, cols])


def test_stochastic_rsi_feature_step_is_yaml_driven_and_flat_price_safe() -> None:
    step = {
        "step": "stochastic_rsi",
        "params": {
            "price_col": "close",
            "rsi_period": 5,
            "stoch_period": 6,
            "k_period": 2,
            "d_period": 2,
            "oversold": 0.2,
            "overbought": 0.8,
            "prefix": "stoch_rsi",
        },
    }
    validate_features_block([step])

    out = apply_feature_steps(_synthetic_ohlcv_for_stochastic_rsi(), [step])
    assert "stoch_rsi_k" in out.columns
    assert classify_feature_family("stoch_rsi_k") == "momentum"

    flat = pd.DataFrame(
        {
            "open": [100.0] * 20,
            "high": [100.0] * 20,
            "low": [100.0] * 20,
            "close": [100.0] * 20,
            "volume": [1000.0] * 20,
        },
        index=pd.date_range("2024-01-01", periods=20, freq="h"),
    )
    flat_out = apply_feature_steps(flat, [step])
    assert flat_out["stoch_rsi_k"].isna().all()
    assert flat_out["stoch_rsi_d"].isna().all()
    assert flat_out["stoch_rsi_cross_up"].eq(0).all()


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


def test_intraday_configs_infer_intraday_annualization_defaults(tmp_path) -> None:
    """
    Intraday configs should derive annualization defaults from the configured interval.
    """
    cfg_path = tmp_path / "intraday_vol.yaml"
    cfg_path.write_text(
        """
data:
  symbol: "SPY"
  interval: "1h"
features:
  - step: "volatility"
backtest:
  returns_col: "close_ret"
  signal_col: "signal"
""".strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config(cfg_path)

    assert cfg["backtest"]["periods_per_year"] == 1638
    assert cfg["features"][0]["params"]["annualization_factor"] == 1638.0


def test_fx_intraday_defaults_infer_24h_business_day_annualization(tmp_path) -> None:
    """
    FX intraday configs should infer 24h annualization over trading days by default.
    """
    cfg_path = tmp_path / "fx_intraday_defaults.yaml"
    cfg_path.write_text(
        """
data:
  source: twelve_data
  interval: 1h
  symbol: EURUSD
features:
  - step: volatility
backtest:
  returns_col: close_ret
  signal_col: signal
""".strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config(cfg_path)

    assert cfg["backtest"]["periods_per_year"] == 6048
    assert cfg["features"][0]["params"]["annualization_factor"] == 6048.0


def test_crypto_intraday_defaults_infer_24h_calendar_day_annualization(tmp_path) -> None:
    """
    Crypto intraday configs should infer 24h calendar-day annualization by default.
    """
    cfg_path = tmp_path / "crypto_intraday_defaults.yaml"
    cfg_path.write_text(
        """
data:
  source: twelve_data
  interval: 1h
  symbol: BTC/USD
features:
  - step: volatility
backtest:
  returns_col: close_ret
  signal_col: signal
""".strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config(cfg_path)

    assert cfg["backtest"]["periods_per_year"] == 8760
    assert cfg["features"][0]["params"]["annualization_factor"] == 8760.0


def test_intraday_configs_reject_daily_timestamp_normalization(tmp_path) -> None:
    """
    Intraday configs should fail fast if a daily-normalization setting would collapse bars.
    """
    cfg_path = tmp_path / "intraday_bad.yaml"
    cfg_path.write_text(
        """
data:
  symbol: "SPY"
  interval: "1h"
  pit:
    timestamp_alignment:
      normalize_daily: true
backtest:
  returns_col: "close_ret"
  signal_col: "signal"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_experiment_config(cfg_path)


def test_typed_config_loader_returns_resolved_schema(tmp_path) -> None:
    """
    The typed config loader should expose a structured resolved config object for orchestration code.
    """
    cfg_path = tmp_path / "typed.yaml"
    cfg_path.write_text(
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

    cfg = load_experiment_config_typed(cfg_path)

    assert isinstance(cfg, ResolvedExperimentConfig)
    assert cfg.data.interval == "1d"
    assert cfg.backtest.periods_per_year == 252


def test_typed_config_loader_exposes_model_stages(tmp_path) -> None:
    cfg_path = tmp_path / "typed_multi_stage.yaml"
    cfg_path.write_text(
        """
data:
  symbol: "SPY"
  interval: "1d"
features: []
model_stages:
  - name: forecast
    enabled: true
    stage: 1
    kind: sarimax_forecaster
    feature_cols: ["feat_1"]
    target:
      kind: forward_return
      price_col: close
      horizon: 1
    split:
      method: time
      train_frac: 0.6
    pred_ret_col: forecast_pred_ret
    pred_prob_col: forecast_pred_prob
  - name: filter
    enabled: true
    stage: 2
    kind: logistic_regression_clf
    feature_cols: ["forecast_pred_ret"]
    target:
      kind: forward_return
      price_col: close
      horizon: 1
    split:
      method: time
      train_frac: 0.75
backtest:
  returns_col: "close_ret"
  signal_col: "signal"
""".strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config_typed(cfg_path)

    assert isinstance(cfg, ResolvedExperimentConfig)
    assert len(cfg.model_stages) == 2
    assert cfg.model_stages[0].name == "forecast"
    assert cfg.model_stages[0].enabled is True
    assert cfg.model_stages[0].stage == 1
    assert cfg.model.kind == "logistic_regression_clf"


def test_config_loader_rejects_legacy_extends(tmp_path) -> None:
    """
    Tracked experiment configs must be fully self-contained and no longer support inheritance.
    """
    parent_cfg = tmp_path / "parent.yaml"
    parent_cfg.write_text(
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
    child_cfg = tmp_path / "child.yaml"
    child_cfg.write_text(
        f"""
extends: "{parent_cfg}"
data:
  symbol: "QQQ"
backtest:
  returns_col: "close_ret"
  signal_col: "signal"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="extends"):
        load_experiment_config(child_cfg)


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


def test_universe_snapshot_rejects_invalid_effective_to_values(tmp_path) -> None:
    """
    Invalid effective_to values should fail loudly instead of becoming open-ended memberships.
    """
    snapshot_path = tmp_path / "bad_universe_snapshot.csv"
    pd.DataFrame(
        {
            "symbol": ["SPY"],
            "effective_from": ["2010-01-01"],
            "effective_to": ["not-a-date"],
        }
    ).to_csv(snapshot_path, index=False)

    with pytest.raises(ValueError, match="effective_to"):
        load_universe_snapshot(snapshot_path)


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
