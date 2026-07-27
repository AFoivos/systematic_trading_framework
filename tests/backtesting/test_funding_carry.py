from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_series_equal
import pytest

from src.evaluation.metrics import compute_backtest_metrics
from src.experiments.support.funding_carry import (
    FundingCarryExecutionSpec,
    FundingCarryRunResult,
    FundingCarrySegmentResult,
    FundingCarrySignalSpec,
    add_causal_funding_forecast,
    align_funding_with_causal_prices,
    load_funding_carry_config,
    select_funding_carry_splits,
    simulate_funding_carry_segment,
    write_funding_carry_artifacts,
)
from src.experiments.support.funding_carry_reporting import (
    build_extended_metrics,
    build_reporting_tables,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "research"
    / "funding_carry"
    / "binance_btc_eth_positive_funding_v1.yaml"
)
V2_CONFIG_PATH = CONFIG_PATH.with_name("binance_btc_eth_positive_funding_v2.yaml")


def _price_frame(times: list[str], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes},
        index=pd.DatetimeIndex(pd.to_datetime(times, utc=True), name="timestamp"),
    )


def test_preregistered_funding_carry_config_is_strict_and_locked() -> None:
    config = load_funding_carry_config(CONFIG_PATH)
    assert config.data.symbols == ("BTCUSDT", "ETHUSDT")
    assert config.data.interval == "30m"
    assert config.signal.positive_funding_only is True
    assert config.execution.round_trip_transaction_cost == pytest.approx(0.0034)
    assert config.data.max_price_age_minutes == 240
    assert config.execution.max_execution_price_age_minutes == 31
    assert [split.name for split in config.research.splits] == [
        "development",
        "validation",
        "locked_test",
    ]
    assert config.research.splits[-1].locked is True
    with pytest.raises(PermissionError, match="Refusing to reveal locked"):
        select_funding_carry_splits(
            config,
            phase="locked_test",
            allow_locked_test=False,
        )


def test_v2_is_reporting_only_and_explicitly_enables_every_metric_family() -> None:
    version_one = load_funding_carry_config(CONFIG_PATH)
    version_two = load_funding_carry_config(V2_CONFIG_PATH)

    assert version_two.version == 2
    assert version_two.parent_strategy_id == version_one.strategy_id
    assert version_two.revision_scope == "reporting_only_no_signal_execution_or_split_parameter_changes"
    assert version_two.data == version_one.data
    assert version_two.signal == version_one.signal
    assert version_two.execution == version_one.execution
    assert version_two.research == version_one.research
    assert version_two.reporting.cost_stress_multipliers == (1.0, 1.25, 1.5, 2.0)
    assert all(
        (
            version_two.reporting.extended_performance_metrics,
            version_two.reporting.risk_and_tail_metrics,
            version_two.reporting.drawdown_metrics,
            version_two.reporting.trade_metrics,
            version_two.reporting.funding_and_basis_attribution,
            version_two.reporting.cost_attribution,
            version_two.reporting.exposure_and_leverage_metrics,
            version_two.reporting.calendar_metrics,
            version_two.reporting.rolling_metrics,
            version_two.reporting.data_quality_metrics,
            version_two.reporting.bootstrap.enabled,
        )
    )


def test_price_alignment_uses_last_closed_bar_and_never_future_bar() -> None:
    funding = pd.DataFrame(
        {"funding_rate": [0.0001]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-01T08:00:00Z")], name="timestamp"),
    )
    spot = _price_frame(
        ["2024-01-01T07:59:59.999Z", "2024-01-01T08:29:59.999Z"],
        [100.0, 999.0],
    )
    perpetual = _price_frame(
        ["2024-01-01T07:59:59.999Z", "2024-01-01T08:29:59.999Z"],
        [100.5, 999.5],
    )

    aligned = align_funding_with_causal_prices(
        funding,
        spot,
        perpetual,
        max_price_age_minutes=31,
    )
    assert aligned.iloc[0]["spot_close"] == 100.0
    assert aligned.iloc[0]["perpetual_close"] == 100.5
    assert aligned.iloc[0]["spot_price_time"] < aligned.index[0]


def test_trailing_funding_forecast_is_unchanged_when_future_rates_change() -> None:
    index = pd.date_range("2024-01-01", periods=12, freq="8h", tz="UTC")
    base = pd.DataFrame({"funding_rate": np.linspace(-0.0002, 0.0003, 12)}, index=index)
    baseline = add_causal_funding_forecast(base, lookback_events=3)

    changed = base.copy()
    changed.loc[index[7]:, "funding_rate"] = 0.02
    perturbed = add_causal_funding_forecast(changed, lookback_events=3)

    assert_series_equal(
        baseline.loc[: index[6], "funding_forecast"],
        perturbed.loc[: index[6], "funding_forecast"],
    )


def test_position_enters_after_observed_funding_and_exits_after_negative_event() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="8h", tz="UTC")
    events = pd.DataFrame(index=index)
    events["funding_rate"] = [0.0010, 0.0012, -0.0005, -0.0004, 0.0001]
    events["funding_forecast"] = [0.0010, 0.0011, -0.0001, -0.0002, 0.0001]
    events["spot_close"] = 100.0
    events["perpetual_close"] = 100.0
    events["spot_return"] = 0.0
    events["perpetual_return"] = 0.0
    events["spot_price_age_seconds"] = 0.001
    events["perpetual_price_age_seconds"] = 0.001
    signal = FundingCarrySignalSpec(
        lookback_events=1,
        expected_holding_events=10,
        expected_funding_interval_hours=8.0,
        entry_cost_multiplier=1.0,
        exit_forecast_rate=0.0,
        max_holding_events=20,
        positive_funding_only=True,
    )
    execution = FundingCarryExecutionSpec(
        spot_fee_bps_per_side=1.0,
        perpetual_fee_bps_per_side=1.0,
        spot_slippage_bps_per_side=0.0,
        perpetual_slippage_bps_per_side=0.0,
        capital_per_spot_notional=1.0,
        annual_financing_rate=0.0,
        max_execution_price_age_minutes=31,
    )

    result = simulate_funding_carry_segment(
        events,
        signal=signal,
        execution=execution,
        start=index[0],
        end=index[-1] + pd.Timedelta(hours=1),
    )

    assert result["position_for_interval"].tolist()[:4] == [0, 1, 1, 0]
    assert result.loc[index[0], "funding_pnl"] == 0.0
    assert result.loc[index[1], "funding_pnl"] == pytest.approx(0.0012)
    assert result.loc[index[2], "funding_pnl"] == pytest.approx(-0.0005)
    assert result.loc[index[0], "transaction_cost"] == pytest.approx(0.0002)
    assert result.loc[index[2], "transaction_cost"] == pytest.approx(0.0002 / 1.001)
    assert result.iloc[-1]["position_after_event"] == 0
    assert result.iloc[-1]["equity"] == pytest.approx((1.0 + result["net_return"]).prod())


def test_equal_underlying_units_do_not_create_free_interval_rebalancing() -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="8h", tz="UTC")
    events = pd.DataFrame(index=index)
    events["funding_rate"] = 0.0
    events["funding_forecast"] = [0.01, 0.01, 0.01]
    events["spot_close"] = [100.0, 110.0, 120.0]
    events["perpetual_close"] = [101.0, 111.0, 121.0]
    events["spot_return"] = events["spot_close"].pct_change()
    events["perpetual_return"] = events["perpetual_close"].pct_change()
    events["spot_price_age_seconds"] = 0.001
    events["perpetual_price_age_seconds"] = 0.001
    signal = FundingCarrySignalSpec(1, 2, 8.0, 1.0, 0.0, 4, True)
    execution = FundingCarryExecutionSpec(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 31)

    result = simulate_funding_carry_segment(
        events,
        signal=signal,
        execution=execution,
        start=index[0],
        end=index[-1] + pd.Timedelta(milliseconds=1),
    )

    assert result.loc[index[1], "hedge_units"] == pytest.approx(0.01)
    assert result.loc[index[1], "spot_pnl"] == pytest.approx(0.10)
    assert result.loc[index[1], "perpetual_pnl"] == pytest.approx(-0.10)
    assert result.loc[index[1], "gross_return"] == pytest.approx(0.0)


def test_v2_extended_metrics_and_tables_are_complete_and_reconciled(tmp_path: Path) -> None:
    config = load_funding_carry_config(V2_CONFIG_PATH)
    index = pd.date_range("2024-01-01", periods=8, freq="8h", tz="UTC")
    events = pd.DataFrame(index=index)
    events["funding_rate"] = [0.01, 0.01, 0.01, -0.01, -0.01, 0.01, 0.01, 0.01]
    events["funding_forecast"] = events["funding_rate"]
    events["spot_close"] = np.linspace(100.0, 103.5, len(index))
    events["perpetual_close"] = events["spot_close"] + 1.0
    events["spot_return"] = events["spot_close"].pct_change()
    events["perpetual_return"] = events["perpetual_close"].pct_change()
    events["spot_price_age_seconds"] = 0.001
    events["perpetual_price_age_seconds"] = 0.001
    reporting = replace(
        config.reporting,
        rolling_windows_days=(2,),
        bootstrap=replace(
            config.reporting.bootstrap,
            samples=20,
            block_length_days=2,
        ),
    )
    simulated = simulate_funding_carry_segment(
        events,
        signal=replace(config.signal, lookback_events=1, expected_holding_events=2),
        execution=replace(
            config.execution,
            spot_fee_bps_per_side=1.0,
            perpetual_fee_bps_per_side=1.0,
            spot_slippage_bps_per_side=0.0,
            perpetual_slippage_bps_per_side=0.0,
            capital_per_spot_notional=1.0,
            annual_financing_rate=0.0,
        ),
        start=index[0],
        end=index[-1] + pd.Timedelta(milliseconds=1),
    )
    base = compute_backtest_metrics(
        net_returns=simulated["net_return"],
        gross_returns=simulated["gross_return"],
        costs=simulated["transaction_cost"] + simulated["financing_cost"],
        turnover=simulated["turnover"],
        annualization_mode="calendar_daily",
    )
    metrics = build_extended_metrics(
        simulated,
        base_metrics=base,
        reporting=reporting,
        include_trades=True,
    )
    tables = build_reporting_tables(simulated, reporting=reporting, include_trades=True)

    assert metrics["trade_analysis"]["trade_count"] == 2.0
    assert metrics["bootstrap_uncertainty"]["available"] is True
    assert "calendar_analysis" in metrics
    assert "risk_and_tail" in metrics
    assert "funding_and_basis_attribution" in metrics
    assert "detailed_cost_attribution" in metrics
    assert "exposure_and_leverage" in metrics
    assert "data_quality" in metrics
    assert set(tables) == {
        "trades",
        "returns_daily",
        "returns_weekly",
        "returns_monthly",
        "returns_yearly",
        "rolling_metrics",
    }
    component_total = (
        simulated["spot_return_component"]
        + simulated["perpetual_return_component"]
        + simulated["funding_return_component"]
        - simulated["fee_cost"]
        - simulated["slippage_cost"]
        - simulated["financing_cost"]
    )
    assert_series_equal(component_total, simulated["net_return"], check_names=False)

    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "manifest.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    artifact_config = replace(config, data=replace(config.data, snapshot_dir=snapshot_dir))
    segment = FundingCarrySegmentResult(
        symbol_events={"BTCUSDT": simulated},
        symbol_metrics={"BTCUSDT": metrics},
        portfolio=simulated,
        portfolio_metrics=metrics,
    )
    run = FundingCarryRunResult(
        strategy_id=config.strategy_id,
        phase="validation",
        cost_multiplier=1.0,
        segments={"validation": segment},
        acceptance={"qualified": True},
        cost_stress={"1.0000": {"cost_multiplier": 1.0}},
    )
    output = write_funding_carry_artifacts(
        artifact_config,
        run,
        output_dir=tmp_path / "artifacts",
    )
    assert (output / "summary.json").is_file()
    assert (output / "metrics_flat.csv").is_file()
    assert (output / "cost_stress.json").is_file()
    assert (output / "validation" / "BTCUSDT_trades.csv").is_file()
    assert (output / "validation" / "BTCUSDT_rolling_metrics.csv").is_file()
    artifact_manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert "metrics_flat" in artifact_manifest["files"]
