from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

from src.experiments.orchestration.artifacts import _write_panel_artifacts
from src.features.panel.context import align_latest_context
from src.features.panel.global_session_relay import global_session_relay_features
from src.signals.panel.global_session_relay_laggard import global_session_relay_laggard_signal


ASSETS = [
    "AUS200", "BRENT", "ETHUSD", "EU50", "EURUSD", "FRA40", "GER40", "NIKKEI225", "SPX500",
    "UK100", "US30", "US100", "USOIL", "XAGUSD", "XAUUSD",
]


def _frame(index: pd.DatetimeIndex, impulse: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "close_ret": 0.001,
            "atr_20": 1.0,
            "vol_rolling_96": 0.01,
            "impulse_12_96": impulse,
        },
        index=index,
    )


def _panel(index: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    return {asset: _frame(index) for asset in ASSETS}


def test_context_age_is_elapsed_time_and_weekends_become_stale() -> None:
    source_index = pd.DatetimeIndex(["2024-01-05 16:00:00"])
    target_index = pd.DatetimeIndex(["2024-01-05 16:30:00", "2024-01-08 09:00:00"])
    source = pd.DataFrame({"value": [1.0]}, index=source_index)
    aligned = align_latest_context(source, target_index, value_columns=["value"], max_age_bars=8, interval_minutes=30)
    assert aligned.loc[target_index[0], "context_age_bars"] == 1.0
    assert bool(aligned.loc[target_index[0], "context_is_fresh"])
    assert aligned.loc[target_index[1], "context_age_minutes"] > 60 * 24
    assert not bool(aligned.loc[target_index[1], "context_is_fresh"])
    assert pd.isna(aligned.loc[target_index[1], "value"])


def test_native_indexes_are_preserved_and_late_eth_does_not_delay_usa() -> None:
    index = pd.date_range("2024-01-02", periods=120, freq="30min")
    frames = _panel(index)
    frames["ETHUSD"] = _frame(index[60:])
    out = global_session_relay_features(frames, universe_mode="fixed")
    assert out["SPX500"].index.equals(index)
    assert out["ETHUSD"].index.equals(index[60:])
    assert bool(out["SPX500"].loc[index[10], "usa_cluster_eligible"])
    assert out["SPX500"].index.name is None


def test_cluster_leader_laggard_and_alphabetical_negative_tie_break() -> None:
    index = pd.date_range("2024-01-02", periods=8, freq="30min")
    frames = _panel(index)
    frames["SPX500"] = _frame(index, 1.50)
    frames["US30"] = _frame(index, 0.20)
    frames["US100"] = _frame(index, 0.40)
    positive = global_session_relay_features(frames)
    row = positive["US100"].iloc[0]
    assert row["usa_cluster_leader_asset"] == "SPX500"
    assert row["usa_cluster_laggard_asset"] == "US30"

    frames["SPX500"] = _frame(index, -1.50)
    frames["US30"] = _frame(index, -0.20)
    frames["US100"] = _frame(index, -0.20)
    negative = global_session_relay_features(frames)
    row = negative["US30"].iloc[0]
    assert row["usa_cluster_leader_asset"] == "SPX500"
    assert row["usa_cluster_laggard_asset"] == "US100"
    assert np.isfinite(row["usa_cluster_dispersion"])


def test_future_mutation_cannot_change_prior_panel_features() -> None:
    index = pd.date_range("2024-01-02", periods=40, freq="30min")
    frames = _panel(index)
    baseline = global_session_relay_features(frames)
    changed = _panel(index)
    changed["US30"].loc[index[25]:, "impulse_12_96"] = -99.0
    mutated = global_session_relay_features(changed)
    pd.testing.assert_series_equal(
        baseline["SPX500"].loc[: index[20], "usa_cluster_impulse_median"],
        mutated["SPX500"].loc[: index[20], "usa_cluster_impulse_median"],
    )


def test_relay_priority_overrides_intra_cluster_and_context_assets_stay_flat() -> None:
    index = pd.date_range("2024-01-02 14:30", periods=2, freq="30min")
    usa = _frame(index, 0.2)
    usa["usa_cluster_eligible"] = True
    usa["usa_cluster_impulse_median"] = 1.0
    usa["usa_cluster_breadth_signed"] = 1.0
    usa["usa_cluster_leader_impulse"] = 1.5
    usa["usa_cluster_laggard_asset"] = "SPX500"
    usa["usa_cluster_laggard_impulse"] = 0.2
    usa["usa_cluster_member_count"] = 3.0
    usa["usa_cluster_positive_count"] = 3.0
    usa["usa_cluster_negative_count"] = 0.0
    usa["europe_to_usa_eligible"] = True
    usa["europe_to_usa_relay_score"] = 1.1
    usa["is_primary_session_open_window"] = True
    eth = _frame(index, 1.0)
    result = global_session_relay_laggard_signal({"SPX500": usa, "ETHUSD": eth})
    assert result["SPX500"].iloc[0]["signal_global_session_relay"] == 1.0
    assert result["SPX500"].iloc[0]["signal_module"] == "europe_to_usa_relay"
    assert (result["ETHUSD"]["signal_global_session_relay"] == 0.0).all()


def test_panel_artifact_writer_emits_required_csvs(tmp_path: Path) -> None:
    index = pd.date_range("2024-01-02", periods=2, freq="30min")
    frame = _frame(index)
    frame["usa_cluster_eligible"] = [True, False]
    frame["usa_cluster_context_age_bars"] = [0.0, 9.0]
    frame["macro_context_eligible"] = [True, False]
    frame["signal_global_session_relay"] = [1.0, 0.0]
    frame["signal_module"] = ["intra_cluster", "none"]
    frame["entry_cluster"] = ["usa", "usa"]
    frame["entry_candidate"] = [True, True]
    frame["entry_eligible"] = [True, False]
    frame["entry_rejection_reason"] = [pd.NA, "cluster_threshold"]
    frame["signal_strength"] = [1.0, 0.0]
    frame["entry_cluster_impulse"] = [0.2, 0.1]
    frame["entry_relay_score"] = [np.nan, np.nan]
    artifacts = _write_panel_artifacts(
        run_dir=tmp_path,
        data={"SPX500": frame},
        cfg={"panel_features": [{"step": "global_session_relay"}], "panel_signals": [{"step": "global_session_relay_laggard"}]},
        portfolio_meta={},
    )
    expected = {"panel_asset_eligibility", "panel_cluster_coverage", "panel_module_coverage", "panel_context_freshness", "panel_signal_diagnostics", "panel_rejection_reasons"}
    assert expected.issubset(artifacts)
    assert all((tmp_path / artifacts[key]).exists() for key in expected)
