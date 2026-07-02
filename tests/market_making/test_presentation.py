from __future__ import annotations

import builtins
from pathlib import Path

from src.market_making.diagnostics import build_market_making_diagnostics
from src.market_making.presentation import write_market_making_presentation
from tests.market_making.test_diagnostics import _write_run


def test_presentation_generation_gracefully_skips_without_python_pptx(tmp_path: Path, monkeypatch) -> None:
    run = tmp_path / "run"
    _write_run(run)
    diagnostics = build_market_making_diagnostics(run)
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pptx":
            raise ImportError("missing pptx")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    path = write_market_making_presentation(run, diagnostics)

    assert path.name == "market_making_diagnostics.pptx"
    assert any("PowerPoint generation skipped" in warning for warning in diagnostics["warnings"])
