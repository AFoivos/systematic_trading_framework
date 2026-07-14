from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


def _audit_module():
    path = Path("scripts/audit_dukascopy_30m_panel_coverage.py")
    spec = importlib.util.spec_from_file_location("coverage_audit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coverage_audit_writes_expected_schemas(tmp_path: Path) -> None:
    audit = _audit_module()
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    timestamps = pd.date_range("2024-01-02", periods=4, freq="30min")
    frame = pd.DataFrame({"timestamp": timestamps, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "spread_bps": 2.0})
    frame.to_csv(input_dir / "spx500_30m.csv", index=False)
    frame.iloc[[0, 2, 3]].to_csv(input_dir / "us30_30m.csv", index=False)
    audit.run_coverage_audit(input_dir=input_dir, output_dir=output_dir, assets=["SPX500", "US30"], interval_minutes=30)
    expected = {"asset_coverage.csv", "asset_gap_diagnostics.csv", "asset_session_diagnostics.csv", "pairwise_overlap.csv", "cluster_coverage.csv", "module_coverage.csv", "coverage_summary.json"}
    assert expected.issubset({path.name for path in output_dir.iterdir()})
    coverage = pd.read_csv(output_dir / "asset_coverage.csv")
    assert {"asset", "first_timestamp", "last_timestamp", "duplicate_timestamp_count", "observed_slot_ratio"}.issubset(coverage.columns)
    modules = pd.read_csv(output_dir / "module_coverage.csv")
    assert {"intra_europe", "intra_usa", "asia_to_europe", "europe_to_usa", "macro_context"}.issubset(modules["module"])
