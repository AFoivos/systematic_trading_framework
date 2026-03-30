from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import src.experiments.runner as runner_mod
from src.backtesting.engine import BacktestResult, run_backtest
from src.experiments.orchestration.stage_trace import build_stage_tail_snapshot, format_stage_tail_snapshot
from src.features.technical.momentum import add_momentum_features
from src.portfolio.construction import PortfolioPerformance
from src.portfolio.covariance import build_rolling_covariance_by_date
from src.signals.forecast_signal import compute_forecast_threshold_signal
from src.signals.probabilistic_signal import probabilistic_signal
from src.signals.rsi_signal import compute_rsi_signal
from src.src_data.loaders import load_ohlcv, load_ohlcv_panel
from src.src_data.providers.alphavantage import AlphaVantageFXProvider, _build_retry_session
from src.src_data.providers.twelvedata import TwelveDataProvider
from src.src_data.storage import save_dataset_snapshot
from src.utils.config import ConfigError, load_experiment_config, load_experiment_config_typed
from src.utils.paths import enforce_safe_absolute_path
from src.utils.repro import apply_runtime_reproducibility
from src.utils.run_metadata import build_run_metadata


def _synthetic_ohlcv(periods: int = 240, seed: int = 123) -> pd.DataFrame:
    """
    Build deterministic OHLCV data for config/feature tests.
    """
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.01, size=periods)
    close = 100.0 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2020-01-01", periods=periods, freq="D")
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
    df["high"] = np.maximum(df["open"], df["close"]) * 1.002
    df["low"] = np.minimum(df["open"], df["close"]) * 0.998
    df["volume"] = 1_000_000 + rng.integers(0, 10_000, size=periods)
    return df[["open", "high", "low", "close", "volume"]]


def test_runner_sensitive_redaction_is_recursive() -> None:
    """
    Ensure nested secret-like keys are redacted before artifact persistence.
    """
    payload = {
        "data": {"api_key": "abc123", "nested": {"token": "ttt"}},
        "secrets": [{"password": "pw"}],
        "safe": {"value": 7},
    }
    redacted = runner_mod._redact_sensitive_values(payload)

    assert redacted["data"]["api_key"] == "***REDACTED***"
    assert redacted["data"]["nested"]["token"] == "***REDACTED***"
    assert redacted["secrets"][0]["password"] == "***REDACTED***"
    assert redacted["safe"]["value"] == 7


def test_optional_model_modules_import_without_xgboost_or_lightgbm() -> None:
    """
    Optional estimator dependencies should not break module import at framework load time.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib
import sys
sys.modules.pop("src.models.classification", None)
sys.modules.pop("src.models.lightgbm_baseline", None)
sys.modules["xgboost"] = None
sys.modules["lightgbm"] = None
import src.models.classification
import src.models.lightgbm_baseline
print("ok")
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_run_metadata_redacts_config_hash_input_secrets() -> None:
    """
    Ensure run metadata never writes plaintext credentials from config payloads.
    """
    meta = build_run_metadata(
        config_path="config/experiments/btcusd_1h_dukas_lightgbm_triple_barrier_garch_long_oos.yaml",
        runtime_applied={},
        config_hash_sha256="x" * 64,
        config_hash_input={"data": {"api_key": "top-secret", "symbol": "SPY"}},
        data_fingerprint={"sha256": "y" * 64},
        data_context={},
        model_meta={},
    )

    assert meta["config_hash_input"]["data"]["api_key"] == "***REDACTED***"
    assert meta["config_hash_input"]["data"]["symbol"] == "SPY"


def test_forecast_long_short_hold_keeps_previous_position() -> None:
    """
    long_short_hold should carry the latest active position through neutral zones.
    """
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame({"pred_ret": [0.02, 0.0, 0.001, -0.02]}, index=idx)

    out = compute_forecast_threshold_signal(
        df,
        forecast_col="pred_ret",
        upper=0.01,
        lower=-0.01,
        mode="long_short_hold",
    )
    assert out["forecast_threshold_signal"].tolist() == [1.0, 1.0, 1.0, -1.0]


def test_probability_threshold_accepts_long_short_mode() -> None:
    """
    Probability threshold signal should support the same directional modes as other threshold
    signal adapters.
    """
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame({"pred_prob": [0.60, 0.50, 0.40, 0.52]}, index=idx)

    out = probabilistic_signal(
        df,
        prob_col="pred_prob",
        upper=0.55,
        lower=0.45,
        mode="long_short",
    )

    assert out.tolist() == [1.0, 0.0, -1.0, 0.0]


def test_probability_threshold_long_short_hold_keeps_previous_position() -> None:
    """
    Probability threshold signal should carry the last active direction through the dead-zone
    when long_short_hold is requested.
    """
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame({"pred_prob": [0.60, 0.50, 0.48, 0.40]}, index=idx)

    out = probabilistic_signal(
        df,
        prob_col="pred_prob",
        upper=0.55,
        lower=0.45,
        mode="long_short_hold",
    )

    assert out.tolist() == [1.0, 1.0, 1.0, -1.0]


def test_rsi_signal_requires_existing_column() -> None:
    """
    RSI signal adapter should fail fast with a clear KeyError on missing input column.
    """
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    with pytest.raises(KeyError):
        compute_rsi_signal(df, rsi_col="missing_rsi", buy_level=30.0, sell_level=70.0)


def test_momentum_features_validate_required_columns() -> None:
    """
    Momentum features should fail fast when required columns are absent.
    """
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
    with pytest.raises(KeyError):
        add_momentum_features(df, price_col="close", returns_col="close_logret")


def test_covariance_rebalance_step_reduces_computation_points() -> None:
    """
    rebalance_step should reduce the number of emitted covariance timestamps.
    """
    idx = pd.date_range("2024-01-01", periods=12, freq="D")
    returns = pd.DataFrame(
        {
            "A": np.linspace(-0.01, 0.01, len(idx)),
            "B": np.linspace(0.02, -0.02, len(idx)),
        },
        index=idx,
    )
    cov_full = build_rolling_covariance_by_date(returns, window=5, min_periods=3, rebalance_step=1)
    cov_sparse = build_rolling_covariance_by_date(returns, window=5, min_periods=3, rebalance_step=2)

    assert len(cov_sparse) < len(cov_full)
    assert set(cov_sparse).issubset(set(cov_full))


def test_execution_output_handles_empty_portfolio_weights() -> None:
    """
    Execution output should gracefully handle empty portfolio weights.
    """
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    asset_frames = {"AAA": pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=idx)}
    perf = PortfolioPerformance(
        equity_curve=pd.Series(dtype=float),
        net_returns=pd.Series(dtype=float),
        gross_returns=pd.Series(dtype=float),
        costs=pd.Series(dtype=float),
        turnover=pd.Series(dtype=float),
        summary={},
    )

    meta, orders = runner_mod._build_execution_output(
        asset_frames=asset_frames,
        execution_cfg={"enabled": True, "capital": 100_000.0, "price_col": "close"},
        portfolio_weights=pd.DataFrame(),
        performance=perf,
        alignment="inner",
    )

    assert meta["order_count"] == 0
    assert orders.empty


def test_runner_completion_output_omits_artifact_inventory(capsys: pytest.CaptureFixture[str]) -> None:
    """
    CLI completion rendering should keep artifact creation silent in stdout.
    """
    result = runner_mod.ExperimentResult(
        config={},
        data=pd.DataFrame(),
        backtest=BacktestResult(
            equity_curve=pd.Series(dtype=float),
            returns=pd.Series(dtype=float),
            gross_returns=pd.Series(dtype=float),
            costs=pd.Series(dtype=float),
            turnover=pd.Series(dtype=float),
            positions=pd.Series(dtype=float),
            summary={},
        ),
        model=None,
        model_meta={},
        evaluation={"primary_summary": {"net_pnl": 0.123, "sharpe": 1.5}},
        monitoring={},
        execution={},
        artifacts={"run_dir": "/tmp/demo", "report": "/tmp/demo/report.md"},
    )

    runner_mod.print_experiment_completion(result)
    captured = capsys.readouterr()

    assert "Experiment completed" in captured.out
    assert "Primary summary:" in captured.out
    assert "net_pnl: 0.123" in captured.out
    assert "Artifacts:" not in captured.out
    assert "run_dir:" not in captured.out


def test_load_experiment_config_resolves_enabled_model_and_signal_catalogs(tmp_path: Path) -> None:
    config_path = tmp_path / "catalog.yaml"
    config_path.write_text(
        """
data:
  source: dukascopy_csv
  interval: 1h
  start: "2024-01-01 00:00:00"
  end: null
  alignment: inner
  symbol: BTCUSD
  pit:
    timestamp_alignment:
      source_timezone: UTC
      output_timezone: UTC
      normalize_daily: false
      duplicate_policy: last
    corporate_actions:
      policy: none
      adj_close_col: adj_close
    universe_snapshot:
      inactive_policy: raise
  storage:
    mode: cached_only
    dataset_id: catalog_test
    save_raw: false
    save_processed: true
    load_path: data/raw/dukas_copy_bank/btcusd_h1.csv
    raw_dir: data/raw
    processed_dir: data/processed
features:
  - step: returns
    params:
      log: true
      col_name: close_logret
models:
  none:
    enabled: false
  xgboost_clf:
    enabled: true
    params:
      n_estimators: 10
      max_depth: 3
      learning_rate: 0.1
      subsample: 1.0
      colsample_bytree: 1.0
      random_state: 7
      min_child_weight: 1.0
      reg_lambda: 1.0
      objective: binary:logistic
      eval_metric: logloss
      tree_method: hist
    feature_cols: [close_logret]
    target:
      kind: triple_barrier
      price_col: close
      open_col: open
      high_col: high
      low_col: low
      returns_col: close_logret
      max_holding: 12
      upper_mult: 1.5
      lower_mult: 1.5
      vol_window: 24
      neutral_label: drop
    split:
      method: walk_forward
      train_size: 100
      test_size: 20
      step_size: 20
      expanding: true
      max_folds: 2
signals_catalog:
  none:
    enabled: false
  probability_threshold:
    enabled: true
    params:
      prob_col: pred_prob
      signal_col: signal_prob_threshold
      upper: 0.55
      lower: 0.45
      mode: long_short
runtime:
  seed: 7
  repro_mode: strict
  deterministic: true
  threads: 1
  seed_torch: false
risk:
  cost_per_turnover: 0.0005
  slippage_per_turnover: 0.00015
  target_vol: null
  max_leverage: 1.0
  dd_guard:
    enabled: true
    max_drawdown: 0.12
    cooloff_bars: 48
  vol_col: null
backtest:
  returns_col: close_logret
  signal_col: signal_prob_threshold
  periods_per_year: 8760
  returns_type: log
  missing_return_policy: raise_if_exposed
  min_holding_bars: 0
  subset: test
  vol_col: null
portfolio:
  enabled: false
  construction: signal_weights
  gross_target: 1.0
  long_short: true
  expected_return_col: null
  covariance_window: 60
  covariance_rebalance_step: 1
  risk_aversion: 5.0
  trade_aversion: 0.0
  constraints: {}
  asset_groups: {}
monitoring:
  enabled: true
  psi_threshold: 0.15
  n_bins: 10
execution:
  enabled: false
  mode: paper
  capital: 1000000.0
  price_col: close
  min_trade_notional: 0.0
  current_weights: {}
  current_prices: {}
logging:
  enabled: true
  run_name: catalog_test
  output_dir: logs/experiments
""",
        encoding="utf-8",
    )

    cfg = load_experiment_config(config_path)

    assert cfg["model"]["kind"] == "xgboost_clf"
    assert cfg["signals"]["kind"] == "probability_threshold"
    assert "models" not in cfg
    assert "signals_catalog" not in cfg


def test_load_experiment_config_normalizes_outputs_aliases(tmp_path: Path) -> None:
    config_path = tmp_path / "outputs_aliases.yaml"
    config_path.write_text(
        """
data:
  source: dukascopy_csv
  interval: 1h
  start: "2024-01-01 00:00:00"
  end: null
  alignment: inner
  symbol: BTCUSD
  pit:
    timestamp_alignment:
      source_timezone: UTC
      output_timezone: UTC
      normalize_daily: false
      duplicate_policy: last
    corporate_actions:
      policy: none
      adj_close_col: adj_close
    universe_snapshot:
      inactive_policy: raise
  storage:
    mode: cached_only
    dataset_id: outputs_alias_test
    save_raw: false
    save_processed: true
    load_path: data/raw/dukas_copy_bank/btcusd_h1.csv
    raw_dir: data/raw
    processed_dir: data/processed
features:
  - step: returns
    outputs:
      close_logret: asset_logret_1h
    params:
      log: true
      col_name: close_logret
model:
  kind: logistic_regression_clf
  outputs:
    pred_prob_col: stage2_prob
    label_col: trend_label
    fwd_col: trend_fwd_4h
    candidate_out_col: meta_candidate
  feature_cols: [asset_logret_1h]
  target:
    kind: triple_barrier
    price_col: close
    open_col: open
    high_col: high
    low_col: low
    returns_col: asset_logret_1h
    max_holding: 12
    upper_mult: 1.5
    lower_mult: 1.5
    vol_window: 24
    neutral_label: drop
  split:
    method: walk_forward
    train_size: 100
    test_size: 20
    step_size: 20
signals:
  kind: probability_threshold
  outputs:
    signal_col: my_signal
  params:
    prob_col: stage2_prob
    upper: 0.55
    lower: 0.45
runtime:
  seed: 7
  repro_mode: strict
  deterministic: true
  threads: 1
  seed_torch: false
risk: {}
backtest:
  returns_col: asset_logret_1h
  signal_col: my_signal
  periods_per_year: 8760
  returns_type: log
  missing_return_policy: raise_if_exposed
portfolio:
  enabled: false
logging:
  enabled: false
""",
        encoding="utf-8",
    )

    cfg = load_experiment_config(config_path)

    assert cfg["model"]["outputs"]["pred_prob_col"] == "stage2_prob"
    assert cfg["model"]["pred_prob_col"] == "stage2_prob"
    assert cfg["model"]["target"]["label_col"] == "trend_label"
    assert cfg["model"]["target"]["fwd_col"] == "trend_fwd_4h"
    assert cfg["model"]["target"]["candidate_out_col"] == "meta_candidate"
    assert cfg["signals"]["outputs"]["signal_col"] == "my_signal"
    assert cfg["signals"]["params"]["signal_col"] == "my_signal"


def test_load_experiment_config_rejects_multiple_enabled_model_catalog_entries(tmp_path: Path) -> None:
    config_path = tmp_path / "bad_catalog.yaml"
    config_path.write_text(
        """
data:
  source: dukascopy_csv
  interval: 1h
  start: "2024-01-01 00:00:00"
  end: null
  alignment: inner
  symbol: BTCUSD
  pit:
    timestamp_alignment:
      source_timezone: UTC
      output_timezone: UTC
      normalize_daily: false
      duplicate_policy: last
    corporate_actions:
      policy: none
      adj_close_col: adj_close
    universe_snapshot:
      inactive_policy: raise
  storage:
    mode: cached_only
    dataset_id: bad_catalog
    save_raw: false
    save_processed: true
    load_path: data/raw/dukas_copy_bank/btcusd_h1.csv
    raw_dir: data/raw
    processed_dir: data/processed
features: []
models:
  none:
    enabled: true
  xgboost_clf:
    enabled: true
signals:
  kind: none
runtime:
  seed: 7
  repro_mode: strict
  deterministic: true
  threads: 1
  seed_torch: false
risk: {}
backtest:
  returns_col: close_logret
  signal_col: signal
  periods_per_year: 8760
  returns_type: log
  missing_return_policy: raise_if_exposed
portfolio: {}
monitoring: {}
execution: {}
logging:
  run_name: bad_catalog
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="exactly one entry with enabled=true"):
        load_experiment_config(config_path)


def test_load_experiment_config_rejects_model_and_model_stages_together(tmp_path: Path) -> None:
    config_path = tmp_path / "bad_multi_stage_mix.yaml"
    config_path.write_text(
        """
data:
  symbol: SPY
  source: yahoo
  interval: 1d
features: []
model:
  kind: logistic_regression_clf
  feature_cols: [feat_1]
  target:
    kind: forward_return
    price_col: close
    horizon: 1
  split:
    method: time
    train_frac: 0.7
model_stages:
  - name: forecast
    kind: sarimax_forecaster
    feature_cols: [feat_1]
    target:
      kind: forward_return
      price_col: close
      horizon: 1
    split:
      method: time
      train_frac: 0.6
signals:
  kind: none
runtime:
  seed: 7
  repro_mode: strict
  deterministic: true
  threads: 1
  seed_torch: false
risk: {}
backtest:
  returns_col: close_ret
  signal_col: signal
  periods_per_year: 252
  returns_type: simple
  missing_return_policy: raise_if_exposed
portfolio:
  enabled: false
monitoring:
  enabled: true
execution:
  enabled: false
logging:
  enabled: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="model_stages"):
        load_experiment_config(config_path)


def test_execution_output_can_liquidate_current_only_assets_with_current_prices() -> None:
    """
    Execution output should allow liquidation of assets present only in current_weights.
    """
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    asset_frames = {"AAA": pd.DataFrame({"close": [100.0, 101.0]}, index=idx)}
    perf = PortfolioPerformance(
        equity_curve=pd.Series([1.0, 1.0], index=idx),
        net_returns=pd.Series([0.0, 0.0], index=idx),
        gross_returns=pd.Series([0.0, 0.0], index=idx),
        costs=pd.Series([0.0, 0.0], index=idx),
        turnover=pd.Series([0.0, 0.0], index=idx),
        summary={},
    )

    meta, orders = runner_mod._build_execution_output(
        asset_frames=asset_frames,
        execution_cfg={
            "enabled": True,
            "capital": 100_000.0,
            "price_col": "close",
            "current_weights": {"BBB": 0.2},
            "current_prices": {"BBB": 50.0},
        },
        portfolio_weights=pd.DataFrame({"AAA": [0.1, 0.1]}, index=idx),
        performance=perf,
        alignment="inner",
    )

    assert meta["order_count"] == 2
    assert "BBB" in orders.index
    assert float(orders.loc["BBB", "target_weight"]) == 0.0
    assert float(orders.loc["BBB", "delta_weight"]) == -0.2


def test_execution_output_uses_latest_available_prices_per_asset_under_outer_alignment() -> None:
    idx_a = pd.to_datetime(["2024-01-01", "2024-01-02"])
    idx_b = pd.to_datetime(["2024-01-01", "2024-01-03"])
    asset_frames = {
        "AAA": pd.DataFrame({"close": [100.0, 101.0]}, index=idx_a),
        "BBB": pd.DataFrame({"close": [50.0, 55.0]}, index=idx_b),
    }
    portfolio_idx = pd.to_datetime(["2024-01-01", "2024-01-03"])
    perf = PortfolioPerformance(
        equity_curve=pd.Series([1.0, 1.0], index=portfolio_idx),
        net_returns=pd.Series([0.0, 0.0], index=portfolio_idx),
        gross_returns=pd.Series([0.0, 0.0], index=portfolio_idx),
        costs=pd.Series([0.0, 0.0], index=portfolio_idx),
        turnover=pd.Series([0.0, 0.0], index=portfolio_idx),
        summary={},
    )

    meta, orders = runner_mod._build_execution_output(
        asset_frames=asset_frames,
        execution_cfg={"enabled": True, "capital": 100_000.0, "price_col": "close"},
        portfolio_weights=pd.DataFrame({"AAA": [0.1, 0.2], "BBB": [0.0, 0.1]}, index=portfolio_idx),
        performance=perf,
        alignment="outer",
    )

    assert meta["order_count"] == 2
    assert float(orders.loc["AAA", "price"]) == 101.0
    assert float(orders.loc["BBB", "price"]) == 55.0


def test_portfolio_oos_mask_requires_all_assets_oos() -> None:
    """
    strict_oos_only date mask should require all assets to be OOS on the same date.
    """
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    asset_frames = {
        "AAA": pd.DataFrame({"pred_is_oos": [1.0, 1.0, 0.0]}, index=idx),
        "BBB": pd.DataFrame({"pred_is_oos": [0.0, 1.0, 1.0]}, index=idx),
    }
    perf = PortfolioPerformance(
        equity_curve=pd.Series([1.0, 1.01, 1.02], index=idx),
        net_returns=pd.Series([0.0, 0.01, 0.01], index=idx),
        gross_returns=pd.Series([0.0, 0.01, 0.01], index=idx),
        costs=pd.Series([0.0, 0.0, 0.0], index=idx),
        turnover=pd.Series([0.0, 0.0, 0.0], index=idx),
        summary={"sharpe": 1.0},
    )
    evaluation = runner_mod._build_portfolio_evaluation(
        asset_frames,
        performance=perf,
        model_meta={"per_asset": {"AAA": {}, "BBB": {}}},
        periods_per_year=252,
        alignment="inner",
    )

    assert evaluation["oos_active_dates"] == 1


def test_safe_absolute_path_blocks_protected_system_locations(monkeypatch) -> None:
    """
    Protected system paths should be denied by default.
    """
    monkeypatch.delenv("STF_ALLOW_EXTERNAL_PATHS", raising=False)
    with pytest.raises(ValueError):
        enforce_safe_absolute_path("/etc/hosts")


def test_safe_absolute_path_allows_tempdir_by_default(monkeypatch) -> None:
    """
    Temporary-directory absolute paths remain allowed in default policy.
    """
    monkeypatch.delenv("STF_ALLOW_EXTERNAL_PATHS", raising=False)
    p = Path(tempfile.gettempdir()) / "stf_dummy_path"
    assert enforce_safe_absolute_path(p) == p.resolve()


def test_config_validation_rejects_unknown_registry_entries(tmp_path) -> None:
    """
    Config loader should reject unknown feature/model/signal kinds at validation time.
    """
    cfg_path = tmp_path / "bad_config.yaml"
    cfg_path.write_text(
        """
data:
  symbol: SPY
features:
  - step: unknown_feature
model:
  kind: unknown_model
signals:
  kind: unknown_signal
backtest:
  returns_col: close_ret
  signal_col: signal
        """.strip(),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_experiment_config(cfg_path)


def test_config_validation_rejects_string_feature_cols(tmp_path) -> None:
    """
    feature_cols should fail fast unless provided as a list of column names.
    """
    cfg_path = tmp_path / "bad_feature_cols.yaml"
    cfg_path.write_text(
        """
data:
  symbol: SPY
model:
  kind: logistic_regression_clf
  feature_cols: close_ret
backtest:
  returns_col: close_ret
  signal_col: signal
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="feature_cols"):
        load_experiment_config(cfg_path)


def test_config_validation_rejects_duplicate_symbols(tmp_path) -> None:
    """
    Duplicate symbols should be rejected instead of being silently overwritten.
    """
    cfg_path = tmp_path / "dup_symbols.yaml"
    cfg_path.write_text(
        """
data:
  symbols: [SPY, SPY]
backtest:
  returns_col: close_ret
  signal_col: signal
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="must not contain duplicates"):
        load_experiment_config(cfg_path)


def test_load_ohlcv_panel_rejects_duplicate_symbols() -> None:
    """
    Direct panel-loading helper should reject duplicate symbols before touching providers.
    """
    with pytest.raises(ValueError, match="duplicates"):
        load_ohlcv_panel(["SPY", "SPY"])


def test_config_validation_rejects_provider_equivalent_duplicate_symbols(tmp_path) -> None:
    """
    Provider-level symbol aliases should be treated as duplicates during config validation.
    """
    cfg_path = tmp_path / "dup_twelve_symbols.yaml"
    cfg_path.write_text(
        """
data:
  source: twelve_data
  interval: 1h
  symbols: [EURUSD, EUR/USD]
backtest:
  returns_col: close_ret
  signal_col: signal
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="provider-equivalent duplicates"):
        load_experiment_config(cfg_path)


def test_load_ohlcv_panel_rejects_provider_equivalent_duplicate_symbols() -> None:
    """
    Direct panel loading should reject provider-equivalent symbol aliases before provider I/O.
    """
    with pytest.raises(ValueError, match="duplicates"):
        load_ohlcv_panel(["EURUSD", "EUR/USD"], source="twelve_data")


def test_logging_output_dir_must_stay_inside_project_root(tmp_path) -> None:
    """
    Logging output_dir should not be allowed to escape the repository root.
    """
    cfg_path = tmp_path / "bad_logging.yaml"
    cfg_path.write_text(
        """
data:
  symbol: SPY
backtest:
  returns_col: close_ret
  signal_col: signal
logging:
  output_dir: ../../../../tmp/stf_escape
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="project root"):
        load_experiment_config(cfg_path)


def test_logging_run_name_is_sanitized(tmp_path) -> None:
    """
    Logging run_name should be normalized to a safe path component.
    """
    cfg_path = tmp_path / "safe_logging.yaml"
    cfg_path.write_text(
        """
data:
  symbol: SPY
backtest:
  returns_col: close_ret
  signal_col: signal
logging:
  run_name: ../../evil
        """.strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config(cfg_path)
    assert cfg["logging"]["run_name"] == "evil"


def test_logging_stage_tails_defaults_are_resolved(tmp_path) -> None:
    """
    Stage-tail logging should resolve explicit defaults so runtime/reporting can rely on a
    stable logging contract.
    """
    cfg_path = tmp_path / "stage_tail_defaults.yaml"
    cfg_path.write_text(
        """
data:
  symbol: SPY
backtest:
  returns_col: close_ret
  signal_col: signal
        """.strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config(cfg_path)
    assert cfg["logging"]["stage_tails"] == {
        "enabled": True,
        "stdout": True,
        "report": True,
        "limit": 10,
        "max_columns": 16,
        "max_assets": 3,
    }


def test_stage_tail_snapshot_formats_added_columns_and_rows() -> None:
    """
    Stage-tail snapshots should report row/column deltas and render a readable tail preview.
    """
    idx = pd.date_range("2024-01-01", periods=4, freq="h", name="timestamp")
    prev = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2, 1.3],
            "high": [1.1, 1.2, 1.3, 1.4],
            "low": [0.9, 1.0, 1.1, 1.2],
            "close": [1.05, 1.15, 1.25, 1.35],
            "volume": [10.0, 11.0, 12.0, 13.0],
        },
        index=idx,
    )
    curr = prev.copy()
    curr["close_logret"] = [0.0, 0.1, 0.2, 0.3]
    curr["signal"] = [0.0, 1.0, -1.0, 0.0]

    snapshot = build_stage_tail_snapshot(
        stage="features_applied",
        asset_frames={"BTCUSD": curr},
        previous_asset_frames={"BTCUSD": prev},
        limit=2,
        max_columns=8,
        max_assets=1,
    )
    asset_payload = snapshot["assets"][0]

    assert snapshot["stage"] == "features_applied"
    assert asset_payload["added_columns"] == ["close_logret", "signal"]
    assert len(asset_payload["tail_rows"]) == 2
    assert "close_logret" in asset_payload["shown_columns"]

    rendered = format_stage_tail_snapshot(snapshot)
    assert "[stage_tails] stage=features_applied" in rendered
    assert "asset=BTCUSD" in rendered
    assert "close_logret" in rendered
    assert "tail(2):" in rendered


def test_config_validation_wraps_invalid_numeric_types_as_config_error(tmp_path) -> None:
    """
    Invalid numeric config values should raise ConfigError instead of raw TypeError.
    """
    cfg_path = tmp_path / "bad_numeric.yaml"
    cfg_path.write_text(
        """
data:
  symbol: SPY
backtest:
  returns_col: close_ret
  signal_col: signal
risk:
  cost_per_turnover: bad
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="finite number"):
        load_experiment_config(cfg_path)


def test_dataset_snapshot_atomic_write_leaves_no_tmp_files(tmp_path) -> None:
    """
    Snapshot persistence should not leave temporary files after a successful save.
    """
    frames = {"AAA": _synthetic_ohlcv(periods=32, seed=9)}
    result = save_dataset_snapshot(
        frames,
        dataset_id="atomic_demo",
        stage="raw",
        root_dir=tmp_path,
        context={"source": "synthetic"},
    )
    snapshot_dir = Path(result["snapshot_dir"])
    assert (snapshot_dir / "dataset.csv").exists()
    assert (snapshot_dir / "metadata.json").exists()
    assert not list(snapshot_dir.glob("*.tmp"))


def test_save_artifacts_refuses_existing_run_dir(tmp_path) -> None:
    """
    Artifact persistence should fail loudly instead of mixing files into an existing run folder.
    """
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    perf = PortfolioPerformance(
        equity_curve=pd.Series([1.0, 1.01], index=idx),
        net_returns=pd.Series([0.0, 0.01], index=idx),
        gross_returns=pd.Series([0.0, 0.01], index=idx),
        costs=pd.Series([0.0, 0.0], index=idx),
        turnover=pd.Series([0.0, 0.0], index=idx),
        summary={"sharpe": 1.0},
    )
    run_dir = tmp_path / "existing_run"
    run_dir.mkdir()

    kwargs = {
        "run_dir": run_dir,
        "cfg": {"features": [], "signals": {}},
        "data": pd.DataFrame({"close": [1.0, 1.1]}, index=idx),
        "performance": perf,
        "model_meta": {},
        "evaluation": {"primary_summary": {"sharpe": 1.0}},
        "monitoring": {},
        "execution": {},
        "execution_orders": None,
        "portfolio_weights": None,
        "portfolio_diagnostics": None,
        "portfolio_meta": {},
        "storage_meta": {},
        "run_metadata": {"runtime": {}},
        "config_hash_sha256": "a" * 64,
        "data_fingerprint": {"sha256": "b" * 64},
    }

    with pytest.raises(FileExistsError):
        runner_mod._save_artifacts(**kwargs)


def test_save_artifacts_writes_experiment_report(tmp_path) -> None:
    """
    Saving artifacts should also emit a human-readable experiment report with charts.
    """
    idx = pd.date_range("2024-01-01", periods=5, freq="D", name="datetime")
    perf = BacktestResult(
        equity_curve=pd.Series([1.0, 1.01, 1.005, 1.02, 1.03], index=idx, name="equity"),
        returns=pd.Series([0.0, 0.01, -0.00495, 0.01493, 0.00976], index=idx, name="signal_rl"),
        gross_returns=pd.Series([0.0, 0.011, -0.004, 0.015, 0.010], index=idx, name="signal_rl"),
        costs=pd.Series([0.0, 0.001, 0.00095, 0.00007, 0.00024], index=idx, name="signal_rl"),
        positions=pd.Series([0.0, 0.2, 0.2, 0.0, 0.2], index=idx, name="signal_rl"),
        turnover=pd.Series([0.0, 0.2, 0.0, 0.2, 0.2], index=idx, name="signal_rl"),
        summary={
            "sharpe": 1.0,
            "gross_pnl": 0.032,
            "net_pnl": 0.029,
            "total_cost": 0.003,
            "avg_turnover": 0.12,
            "hit_rate": 0.6,
        },
    )
    run_dir = tmp_path / "reported_run"
    artifacts = runner_mod._save_artifacts(
        run_dir=run_dir,
        cfg={
            "config_path": "config/experiments/demo.yaml",
            "data": {"source": "synthetic", "symbol": "TEST", "interval": "1h", "start": "2024-01-01"},
            "features": [{"step": "returns", "params": {"col_name": "close_logret", "log": True}}],
            "model": {
                "kind": "ppo_agent",
                "target": {"kind": "forward_return", "horizon": 1},
                "env": {"max_signal_abs": 0.2, "reward": {"inventory_penalty": 0.0}},
            },
            "signals": {"kind": "none", "params": {}},
            "risk": {},
            "backtest": {"returns_type": "log"},
            "portfolio": {"enabled": False},
            "runtime": {},
            "logging": {"run_name": "demo_report"},
        },
        data=pd.DataFrame({"close": [1.0, 1.1, 1.2, 1.3, 1.4]}, index=idx),
        performance=perf,
        model_meta={
            "feature_cols": ["lag_close_logret_1", "vol_rolling_24"],
            "contracts": {"n_features": 2},
            "feature_importance": {
                "available": True,
                "top_features": [
                    {
                        "rank": 1,
                        "feature": "lag_close_logret_1",
                        "mean_importance": 0.8,
                        "mean_importance_normalized": 0.8,
                        "fold_count": 1,
                        "source": "feature_importances_",
                    },
                    {
                        "rank": 2,
                        "feature": "vol_rolling_24",
                        "mean_importance": 0.2,
                        "mean_importance_normalized": 0.2,
                        "fold_count": 1,
                        "source": "feature_importances_",
                    },
                ],
            },
            "label_distribution": {
                "train": {"labeled_rows": 10, "class_counts": {"0": 4, "1": 6}, "positive_rate": 0.6},
                "oos_evaluation": {"labeled_rows": 5, "class_counts": {"0": 2, "1": 3}, "positive_rate": 0.6},
            },
            "prediction_diagnostics": {
                "oos_rows": 5,
                "predicted_rows": 5,
                "non_oos_prediction_rows": 0,
                "missing_oos_prediction_rows": 0,
                "oos_prediction_coverage": 1.0,
                "alignment_ok": True,
            },
            "missing_value_diagnostics": {
                "train_rows_dropped_missing": 1,
                "test_rows_missing_features": 0,
                "test_rows_not_candidates": 0,
                "test_rows_without_prediction": 0,
                "folds_with_zero_predictions": 0,
            },
            "folds": [
                {
                    "fold": 0,
                    "train_rows_raw": 10,
                    "train_rows": 9,
                    "train_rows_dropped_missing": 1,
                    "test_rows": 5,
                    "test_pred_rows": 5,
                    "test_rows_missing_features": 0,
                    "test_rows_not_candidates": 0,
                    "test_rows_without_prediction": 0,
                    "train_feature_availability": {"rows": 10, "complete_rows": 9, "missing_rows": 1},
                    "test_feature_availability": {"rows": 5, "complete_rows": 5, "missing_rows": 0},
                    "classification_metrics": {"evaluation_rows": 5, "accuracy": 0.6},
                    "feature_importance": [
                        {"feature": "lag_close_logret_1", "importance": 0.8, "importance_normalized": 0.8, "source": "feature_importances_"},
                        {"feature": "vol_rolling_24", "importance": 0.2, "importance_normalized": 0.2, "source": "feature_importances_"},
                    ],
                    "policy_metrics": {
                        "mean_reward": 0.001,
                        "mean_abs_signal": 0.16,
                        "signal_turnover": 0.1,
                        "flat_rate": 0.2,
                    },
                }
            ],
        },
        evaluation={
            "primary_summary": {
                "sharpe": 1.0,
                "gross_pnl": 0.032,
                "net_pnl": 0.029,
                "total_cost": 0.003,
                "avg_turnover": 0.12,
                "hit_rate": 0.6,
            },
            "fold_backtest_summaries": [
                {
                    "fold": 0,
                    "test_rows": 5,
                    "metrics": {
                        "gross_pnl": 0.032,
                        "net_pnl": 0.029,
                        "total_cost": 0.003,
                        "sharpe": 1.0,
                        "avg_turnover": 0.12,
                    },
                }
            ],
            "model_oos_policy_summary": {
                "mean_abs_signal": 0.16,
                "signal_turnover": 0.1,
                "long_rate": 0.6,
                "short_rate": 0.2,
                "flat_rate": 0.2,
            },
        },
        monitoring={},
        execution={},
        execution_orders=None,
        portfolio_weights=None,
        portfolio_diagnostics=None,
        portfolio_meta={},
        storage_meta={},
        run_metadata={
            "runtime": {},
            "model_meta": {
                "contracts": {"n_features": 2},
                "feature_importance": {
                    "available": True,
                    "top_features": [
                        {
                            "rank": 1,
                            "feature": "lag_close_logret_1",
                            "mean_importance": 0.8,
                            "mean_importance_normalized": 0.8,
                            "fold_count": 1,
                            "source": "feature_importances_",
                        }
                    ],
                },
                "label_distribution": {
                    "train": {"labeled_rows": 10, "class_counts": {"0": 4, "1": 6}, "positive_rate": 0.6},
                    "oos_evaluation": {"labeled_rows": 5, "class_counts": {"0": 2, "1": 3}, "positive_rate": 0.6},
                },
                "prediction_diagnostics": {
                    "oos_rows": 5,
                    "predicted_rows": 5,
                    "non_oos_prediction_rows": 0,
                    "missing_oos_prediction_rows": 0,
                    "oos_prediction_coverage": 1.0,
                    "alignment_ok": True,
                },
                "missing_value_diagnostics": {
                    "train_rows_dropped_missing": 1,
                    "test_rows_missing_features": 0,
                    "test_rows_not_candidates": 0,
                    "test_rows_without_prediction": 0,
                    "folds_with_zero_predictions": 0,
                },
                "folds": [
                    {
                        "fold": 0,
                        "train_rows_raw": 10,
                        "train_rows": 9,
                        "train_rows_dropped_missing": 1,
                        "test_rows": 5,
                        "test_pred_rows": 5,
                        "test_rows_missing_features": 0,
                        "test_rows_not_candidates": 0,
                        "test_rows_without_prediction": 0,
                        "train_feature_availability": {"rows": 10, "complete_rows": 9, "missing_rows": 1},
                        "test_feature_availability": {"rows": 5, "complete_rows": 5, "missing_rows": 0},
                        "classification_metrics": {"evaluation_rows": 5, "accuracy": 0.6},
                        "policy_metrics": {"mean_reward": 0.001},
                    }
                ],
            },
        },
        config_hash_sha256="a" * 64,
        data_fingerprint={"sha256": "b" * 64},
        stage_tails={
            "config": {"enabled": True, "stdout": True, "report": True, "limit": 2, "max_columns": 8, "max_assets": 1},
            "stages": [
                {
                    "stage": "raw_loaded",
                    "asset_count": 1,
                    "shown_asset_count": 1,
                    "limit": 2,
                    "max_columns": 8,
                    "max_assets": 1,
                    "assets": [
                        {
                            "asset": "TEST",
                            "rows": 5,
                            "row_delta": 5,
                            "column_count": 5,
                            "column_delta": 5,
                            "added_columns": ["open", "high", "low", "close", "volume"],
                            "removed_columns": [],
                            "shown_columns": ["datetime", "open", "high", "low", "close", "volume"],
                            "truncated_columns": [],
                            "tail_rows": [
                                {
                                    "datetime": "2024-01-04 00:00:00",
                                    "open": 1.0,
                                    "high": 1.0,
                                    "low": 1.0,
                                    "close": 1.3,
                                    "volume": 10.0,
                                },
                                {
                                    "datetime": "2024-01-05 00:00:00",
                                    "open": 1.0,
                                    "high": 1.0,
                                    "low": 1.0,
                                    "close": 1.4,
                                    "volume": 10.0,
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    )

    report_path = Path(artifacts["report"])
    assert report_path.exists()
    assert artifacts["equity_curve"].endswith("equity_curve.csv")
    assert artifacts["equity_curve_chart"].endswith("report_assets/equity_curve.png")
    assert artifacts["feature_importance"].endswith("feature_importance.csv")
    assert artifacts["label_distribution"].endswith("label_distribution.csv")
    assert artifacts["prediction_diagnostics"].endswith("prediction_diagnostics.json")
    assert artifacts["fold_model_summary"].endswith("fold_model_summary.csv")
    assert artifacts["stage_tails"].endswith("stage_tails.json")
    assert (run_dir / "report_assets" / "equity_curve.png").exists()
    assert (run_dir / "report_assets" / "drawdown_curve.png").exists()
    assert (run_dir / "report_assets" / "cumulative_returns.png").exists()
    assert (run_dir / "report_assets" / "rolling_pnl.png").exists()
    assert (run_dir / "report_assets" / "cumulative_cost_drag.png").exists()
    assert (run_dir / "report_assets" / "positions_turnover.png").exists()
    assert (run_dir / "report_assets" / "rolling_behavior.png").exists()
    assert (run_dir / "report_assets" / "signal_distribution.png").exists()
    assert (run_dir / "report_assets" / "feature_importance.png").exists()
    assert (run_dir / "report_assets" / "label_distribution.png").exists()
    assert (run_dir / "report_assets" / "prediction_coverage_by_fold.png").exists()
    report_text = report_path.read_text(encoding="utf-8")
    fold_summary = pd.read_csv(run_dir / "fold_model_summary.csv")
    assert "test_rows_not_candidates" in fold_summary.columns
    assert "test_rows_without_prediction" in fold_summary.columns
    assert "## Pipeline Trace" in report_text
    assert "## Stage Tail Trace" in report_text
    assert "### raw_loaded" in report_text
    assert "### 2. Data Load And PIT" in report_text
    assert "## Primary Summary" in report_text
    assert "## OOS Policy Summary" in report_text
    assert "## Prediction Diagnostics" in report_text
    assert "## Missing-Value Diagnostics" in report_text
    assert "Test Not Candidates" in report_text
    assert "Test Without Prediction" in report_text
    assert "## Label Distribution" in report_text
    assert "## Feature Importance" in report_text
    assert "## Model Fold Diagnostics" in report_text
    assert "## Cost / Exposure / Turnover" in report_text
    assert "## Diagnostics" in report_text


def test_run_backtest_caps_positions_at_max_leverage() -> None:
    """
    max_leverage should cap positions even when volatility targeting is disabled.
    """
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "signal": [10.0, -10.0, 2.0],
            "close_ret": [0.0, 0.01, -0.01],
        },
        index=idx,
    )

    result = run_backtest(
        df,
        signal_col="signal",
        returns_col="close_ret",
        max_leverage=3.0,
        dd_guard=False,
    )

    assert result.positions.max() <= 3.0
    assert result.positions.min() >= -3.0


def test_single_asset_backtest_summary_uses_strict_oos_rows() -> None:
    """
    subset=test should not let non-OOS gap rows contaminate the reported single-asset summary.
    """
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "signal": [1.0, 1.0, 1.0, 1.0],
            "close_ret": [0.0, 0.0, -0.9, 0.0],
            "pred_is_oos": [False, True, False, True],
        },
        index=idx,
    )
    cfg = {
        "backtest": {
            "returns_col": "close_ret",
            "signal_col": "signal",
            "periods_per_year": 252,
            "returns_type": "simple",
            "subset": "test",
        },
        "risk": {
            "cost_per_turnover": 0.0,
            "slippage_per_turnover": 0.0,
            "target_vol": None,
            "max_leverage": 3.0,
            "dd_guard": {"enabled": False, "max_drawdown": 0.2, "cooloff_bars": 1},
        },
    }

    result = runner_mod._run_single_asset_backtest(
        "AAA",
        df,
        cfg=cfg,
        model_meta={"split_index": 1},
    )

    assert np.isclose(result.summary["cumulative_return"], 0.0)


def test_alphavantage_retry_session_is_configured() -> None:
    """
    AlphaVantage session should have retry policy for transient HTTP failures.
    """
    session = _build_retry_session()
    try:
        adapter = session.get_adapter("https://")
        retries = adapter.max_retries
        assert retries.total == 4
        assert 429 in retries.status_forcelist
        assert 503 in retries.status_forcelist
    finally:
        session.close()


def test_alphavantage_config_rejects_intraday_interval(tmp_path) -> None:
    """
    AlphaVantage configs should fail fast when they request unsupported intraday intervals.
    """
    cfg_path = tmp_path / "alpha_intraday.yaml"
    cfg_path.write_text(
        """
data:
  symbol: EURUSD
  source: alpha
  interval: 1h
backtest:
  returns_col: close_ret
  signal_col: signal
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="must be '1d'"):
        load_experiment_config(cfg_path)


def test_alphavantage_provider_uses_end_exclusive_filter(monkeypatch) -> None:
    """
    AlphaVantage provider should align its end-date filtering with end-exclusive split semantics.
    """
    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "Time Series FX (Daily)": {
                    "2024-01-03": {
                        "1. open": "1.2",
                        "2. high": "1.3",
                        "3. low": "1.1",
                        "4. close": "1.25",
                    },
                    "2024-01-02": {
                        "1. open": "1.1",
                        "2. high": "1.2",
                        "3. low": "1.0",
                        "4. close": "1.15",
                    },
                    "2024-01-01": {
                        "1. open": "1.0",
                        "2. high": "1.1",
                        "3. low": "0.9",
                        "4. close": "1.05",
                    },
                }
            }

    class _FakeSession:
        def get(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(
        "src.src_data.providers.alphavantage._build_retry_session",
        lambda: _FakeSession(),
    )

    provider = AlphaVantageFXProvider(api_key="demo")
    df = provider.get_ohlcv("EURUSD", start="2024-01-01", end="2024-01-03")

    assert list(df.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]


def test_twelve_data_config_accepts_intraday_interval(tmp_path) -> None:
    """
    Twelve Data configs should allow intraday intervals for forex-style experiments.
    """
    cfg_path = tmp_path / "twelve_intraday.yaml"
    cfg_path.write_text(
        """
data:
  symbol: EURUSD
  source: twelve_data
  interval: 1h
backtest:
  returns_col: close_ret
  signal_col: signal
        """.strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config(cfg_path)
    assert cfg["data"]["source"] == "twelve_data"
    assert cfg["data"]["interval"] == "1h"


def test_twelve_data_provider_normalizes_fx_symbol_and_filters_end_exclusive(monkeypatch) -> None:
    """
    Twelve Data provider should normalize EURUSD aliases and preserve end-exclusive filtering.
    """
    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "meta": {"symbol": "EUR/USD", "interval": "1h"},
                "values": [
                    {
                        "datetime": "2024-01-03 02:00:00",
                        "open": "1.1030",
                        "high": "1.1040",
                        "low": "1.1020",
                        "close": "1.1035",
                    },
                    {
                        "datetime": "2024-01-03 01:00:00",
                        "open": "1.1020",
                        "high": "1.1030",
                        "low": "1.1010",
                        "close": "1.1025",
                    },
                    {
                        "datetime": "2024-01-03 00:00:00",
                        "open": "1.1010",
                        "high": "1.1020",
                        "low": "1.1000",
                        "close": "1.1015",
                    },
                ],
            }

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            captured["url"] = url
            captured["params"] = dict(params or {})
            captured["timeout"] = timeout
            return _FakeResponse()

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "src.src_data.providers.twelvedata._build_retry_session",
        lambda: _FakeSession(),
    )

    provider = TwelveDataProvider(api_key="demo")
    df = provider.get_ohlcv("EURUSD=X", start="2024-01-03 00:00:00", end="2024-01-03 02:00:00", interval="1h")

    assert captured["url"] == "https://api.twelvedata.com/time_series"
    assert captured["params"]["symbol"] == "EUR/USD"
    assert captured["params"]["interval"] == "1h"
    assert list(df.index) == [
        pd.Timestamp("2024-01-03 00:00:00"),
        pd.Timestamp("2024-01-03 01:00:00"),
    ]
    assert (df["volume"] == 0.0).all()


def test_twelve_data_provider_raises_on_truncated_history(monkeypatch) -> None:
    """
    Twelve Data provider should fail loudly when the response appears capped by outputsize.
    """

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "meta": {"symbol": "BTC/USD", "interval": "1h"},
                "values": [
                    {"datetime": "2024-01-05 02:00:00", "open": "1", "high": "1", "low": "1", "close": "1"},
                    {"datetime": "2024-01-05 01:00:00", "open": "1", "high": "1", "low": "1", "close": "1"},
                    {"datetime": "2024-01-05 00:00:00", "open": "1", "high": "1", "low": "1", "close": "1"},
                ],
            }

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            return _FakeResponse()

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "src.src_data.providers.twelvedata._build_retry_session",
        lambda: _FakeSession(),
    )

    provider = TwelveDataProvider(api_key="demo", outputsize=3)
    with pytest.raises(ValueError, match="truncated by outputsize"):
        provider.get_ohlcv("BTC/USD", start="2024-01-01 00:00:00", interval="1h")


def test_load_ohlcv_routes_twelve_data_source(monkeypatch) -> None:
    """
    load_ohlcv should instantiate the Twelve Data provider when requested.
    """
    calls: dict[str, object] = {}

    class _FakeProvider:
        def __init__(self, api_key=None):
            calls["api_key"] = api_key

        def get_ohlcv(self, symbol, start=None, end=None, interval="1d"):
            calls["symbol"] = symbol
            calls["start"] = start
            calls["end"] = end
            calls["interval"] = interval
            return pd.DataFrame(
                {
                    "open": [1.0],
                    "high": [1.1],
                    "low": [0.9],
                    "close": [1.05],
                    "volume": [0.0],
                },
                index=pd.DatetimeIndex([pd.Timestamp("2024-01-01 00:00:00")]),
            )

    monkeypatch.setattr("src.src_data.loaders.TwelveDataProvider", _FakeProvider)

    df = load_ohlcv(
        "EURUSD",
        start="2024-01-01",
        end="2024-01-02",
        interval="1h",
        source="twelve_data",
        api_key="demo",
    )

    assert calls == {
        "api_key": "demo",
        "symbol": "EURUSD",
        "start": "2024-01-01",
        "end": "2024-01-02",
        "interval": "1h",
    }
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_load_ohlcv_rejects_dukascopy_csv_provider_route() -> None:
    with pytest.raises(ValueError, match="requires data.storage.load_path"):
        load_ohlcv(
            "BTCUSD",
            start="2024-01-01",
            end="2024-01-02",
            interval="1h",
            source="dukascopy_csv",
        )


CURRENT_TRACKED_CONFIG_CASES = [
    ("experiments/btcusd_1h_dukas_xgboost_triple_barrier_garch_long_oos.yaml", 8760),
]


@pytest.mark.parametrize("config_name,expected_periods_per_year", CURRENT_TRACKED_CONFIG_CASES)
def test_tracked_experiment_configs_load_and_produce_declared_features(
    config_name: str,
    expected_periods_per_year: int,
) -> None:
    """
    The currently tracked experiment configs should load cleanly and request only features that
    the configured pipeline actually produces.
    """
    cfg = load_experiment_config(config_name)

    idx = pd.date_range("2024-01-01 00:00:00", periods=400, freq="h")
    base = np.linspace(0.0, 0.04, len(idx))
    cyc = 0.003 * np.sin(np.arange(len(idx)) / 9.0)
    close = 100.0 * np.exp(base + cyc)

    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.999)
    df["high"] = np.maximum(df["open"], df["close"]) * 1.001
    df["low"] = np.minimum(df["open"], df["close"]) * 0.999
    df["volume"] = 1000.0 + (np.arange(len(idx)) % 24) * 25.0
    df = df[["open", "high", "low", "close", "volume"]]

    features_df = runner_mod._apply_feature_steps(df, list(cfg.get("features", []) or []))

    assert cfg["data"]["symbol"] == "BTCUSD"
    assert cfg["portfolio"]["enabled"] is False
    assert cfg["backtest"]["periods_per_year"] == expected_periods_per_year
    assert "close_logret" in features_df.columns
    assert "vol_rolling_24" in features_df.columns

    model_cfg = dict(cfg.get("model", {}) or {})
    feature_cols = list(model_cfg.get("feature_cols", []) or [])
    missing = [c for c in feature_cols if c not in features_df.columns]
    assert not missing


def test_btcusd_dukas_hourly_config_feature_pipeline_computes_expected_features() -> None:
    """
    The tracked BTCUSD Dukas hourly config should produce the declared feature set with
    numerically consistent 24/7 annualization and volume-aware columns.
    """
    cfg = load_experiment_config("experiments/btcusd_1h_dukas_xgboost_triple_barrier_garch_long_oos.yaml")

    idx = pd.date_range("2024-01-01 00:00:00", periods=240, freq="h")
    base = np.linspace(0.0, 0.03, len(idx))
    cyc = 0.002 * np.sin(np.arange(len(idx)) / 8.0)
    close = 42_000.0 * np.exp(base + cyc)

    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0] * 0.9995)
    df["high"] = np.maximum(df["open"], df["close"]) * 1.0008
    df["low"] = np.minimum(df["open"], df["close"]) * 0.9992
    df["volume"] = 1000.0 + (np.arange(len(idx)) % 24) * 10.0
    df = df[["open", "high", "low", "close", "volume"]]

    features_df = runner_mod._apply_feature_steps(df, list(cfg.get("features", []) or []))

    assert cfg["backtest"]["periods_per_year"] == 8760
    assert cfg["features"][1]["params"]["annualization_factor"] == 8760.0

    missing = [c for c in cfg["model"]["feature_cols"] if c not in features_df.columns]
    assert not missing

    expected_logret = np.log(df["close"] / df["close"].shift(1))
    np.testing.assert_allclose(
        features_df["close_logret"].to_numpy(dtype=float),
        expected_logret.to_numpy(dtype=float),
        equal_nan=True,
    )

    expected_vol_24 = expected_logret.rolling(window=24).std(ddof=1) * np.sqrt(8760.0)
    np.testing.assert_allclose(
        features_df["vol_rolling_24"].to_numpy(dtype=float),
        expected_vol_24.to_numpy(dtype=float),
        equal_nan=True,
    )

    expected_lag_1 = expected_logret.shift(1)
    np.testing.assert_allclose(
        features_df["lag_close_logret_1"].to_numpy(dtype=float),
        expected_lag_1.to_numpy(dtype=float),
        equal_nan=True,
    )

    assert "volume_z_72" in features_df.columns
    assert "volume_over_atr_24" in features_df.columns
    assert "mfi_24" not in features_df.columns

    model_cfg = dict(cfg.get("model", {}) or {})
    feature_cols = list(model_cfg.get("feature_cols", []) or [])
    if feature_cols:
        missing = [c for c in feature_cols if c not in features_df.columns]
        assert not missing

    if cfg["signals"]["kind"] == "volatility_regime":
        assert cfg["signals"]["params"]["vol_col"] in features_df.columns


def test_typed_loader_accepts_null_covariance_window(tmp_path) -> None:
    """
    Nullable portfolio covariance parameters should remain loadable in typed configs.
    """
    cfg_path = tmp_path / "typed_portfolio_nulls.yaml"
    cfg_path.write_text(
        """
data:
  symbol: SPY
backtest:
  returns_col: close_ret
  signal_col: signal
portfolio:
  covariance_window: null
  covariance_rebalance_step: null
        """.strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config_typed(cfg_path)
    assert cfg.portfolio.covariance_window is None
    assert cfg.portfolio.covariance_rebalance_step is None


def test_typed_loader_accepts_execution_current_prices(tmp_path) -> None:
    """
    Typed config loader should preserve optional execution.current_prices mappings.
    """
    cfg_path = tmp_path / "execution_current_prices.yaml"
    cfg_path.write_text(
        """
data:
  symbol: SPY
backtest:
  returns_col: close_ret
  signal_col: signal
execution:
  current_weights:
    BBB: 0.2
  current_prices:
    BBB: 50.0
        """.strip(),
        encoding="utf-8",
    )

    cfg = load_experiment_config_typed(cfg_path)
    assert cfg.execution.current_weights == {"BBB": 0.2}
    assert cfg.execution.current_prices == {"BBB": 50.0}


def test_portfolio_backtest_accepts_null_covariance_settings() -> None:
    """
    Mean-variance portfolio path should treat null covariance settings as default runtime values.
    """
    idx = pd.date_range("2024-01-01", periods=8, freq="D")
    asset_frames = {
        "AAA": pd.DataFrame(
            {"close_ret": np.linspace(0.001, 0.008, len(idx)), "signal": np.linspace(0.01, 0.08, len(idx))},
            index=idx,
        ),
        "BBB": pd.DataFrame(
            {"close_ret": np.linspace(-0.002, 0.003, len(idx)), "signal": np.linspace(0.02, 0.01, len(idx))},
            index=idx,
        ),
    }
    cfg = {
        "data": {"alignment": "inner"},
        "backtest": {"returns_col": "close_ret", "signal_col": "signal", "returns_type": "simple"},
        "risk": {"cost_per_turnover": 0.0, "slippage_per_turnover": 0.0},
        "portfolio": {
            "enabled": True,
            "construction": "mean_variance",
            "expected_return_col": "signal",
            "covariance_window": None,
            "covariance_rebalance_step": None,
            "risk_aversion": 1.0,
            "trade_aversion": 0.0,
            "constraints": {"min_weight": -1.0, "max_weight": 1.0, "max_gross_leverage": 1.0},
        },
    }

    perf, weights, diagnostics, meta = runner_mod._run_portfolio_backtest(asset_frames, cfg=cfg)

    assert isinstance(perf.summary, dict)
    assert not weights.empty
    assert not diagnostics.empty
    assert meta["construction"] == "mean_variance"


def test_runtime_repro_metadata_marks_pythonhashseed_limitations() -> None:
    """
    Runtime reproducibility metadata should explicitly report PYTHONHASHSEED runtime limitation.
    """
    ctx = apply_runtime_reproducibility(
        {"seed": 123, "deterministic": True, "threads": 1, "repro_mode": "strict"}
    )
    assert ctx["pythonhashseed_effective_in_process"] is False


def test_dockerfile_runs_as_non_root_user() -> None:
    """
    Dockerfile should specify a non-root runtime user.
    """
    content = Path("Dockerfile").read_text(encoding="utf-8")
    assert "USER appuser" in content


def test_dockerfile_uses_lockfile_for_installs() -> None:
    """
    Docker builds should install from the pinned lockfile for reproducibility.
    """
    content = Path("Dockerfile").read_text(encoding="utf-8")
    assert "requirements.lock.txt" in content
    assert "pip install -r /tmp/requirements.lock.txt" in content


def test_requirements_lock_contains_pinned_versions() -> None:
    """
    Lock requirements file should contain exact pins for reproducible installs.
    """
    content = Path("requirements.lock.txt").read_text(encoding="utf-8").splitlines()
    pins = [line for line in content if line.strip() and not line.strip().startswith("#")]
    assert pins
    assert all("==" in line for line in pins)
