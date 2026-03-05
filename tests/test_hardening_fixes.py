from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import src.experiments.runner as runner_mod
from src.features.technical.momentum import add_momentum_features
from src.portfolio.construction import PortfolioPerformance
from src.portfolio.covariance import build_rolling_covariance_by_date
from src.signals.forecast_signal import compute_forecast_threshold_signal
from src.signals.rsi_signal import compute_rsi_signal
from src.src_data.providers.alphavantage import _build_retry_session
from src.src_data.storage import save_dataset_snapshot
from src.utils.config import ConfigError, load_experiment_config
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


def test_run_metadata_redacts_config_hash_input_secrets() -> None:
    """
    Ensure run metadata never writes plaintext credentials from config payloads.
    """
    meta = build_run_metadata(
        config_path="config/experiments/logreg_spy.yaml",
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


def test_tft_config_feature_columns_exist_after_feature_pipeline() -> None:
    """
    TFT experiment config should request only features produced by configured steps.
    """
    cfg = load_experiment_config("experiments/tft_spy.yaml")
    df = _synthetic_ohlcv(periods=260, seed=4)
    features_df = runner_mod._apply_feature_steps(df, list(cfg.get("features", []) or []))
    missing = [c for c in cfg["model"]["feature_cols"] if c not in features_df.columns]
    assert not missing


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


def test_requirements_lock_contains_pinned_versions() -> None:
    """
    Lock requirements file should contain exact pins for reproducible installs.
    """
    content = Path("requirements.lock.txt").read_text(encoding="utf-8").splitlines()
    pins = [line for line in content if line.strip() and not line.strip().startswith("#")]
    assert pins
    assert all("==" in line for line in pins)
