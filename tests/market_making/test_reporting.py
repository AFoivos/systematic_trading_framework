from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from src.market_making.diagnostics import build_market_making_diagnostics
from src.market_making.reporting import write_market_making_markdown_report
from tests.market_making.test_diagnostics import _write_run


def test_markdown_report_writes_required_sections(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)
    diagnostics = build_market_making_diagnostics(run)

    report_path = write_market_making_markdown_report(run, diagnostics)

    text = report_path.read_text(encoding="utf-8")
    assert "# Market Making Run Diagnostics" in text
    assert "## Executive Summary" in text
    assert "## Diagnostics Gaps" in text
    assert "Fill sample sufficient for edge evaluation" in text


def test_analyze_market_making_run_cli_writes_diagnostics(tmp_path: Path) -> None:
    run = tmp_path / "run"
    _write_run(run)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_market_making_run.py",
            "--run-dir",
            str(run),
            "--no-plots",
            "--no-pptx",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Market-making diagnostics" in result.stdout
    assert (run / "diagnostics" / "summary.json").exists()
    assert (run / "diagnostics" / "report.md").exists()
