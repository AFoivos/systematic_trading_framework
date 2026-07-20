from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.experiments.evolutionary import cli


def test_validate_only_cli_does_not_run_search(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = SimpleNamespace(
        search=SimpleNamespace(name="synthetic", family="test", backend="optuna_nsga2"),
        genome=SimpleNamespace(decoder="synthetic_decoder", decoder_version=1, genes={"x": 1}),
        base_config_path="base.yaml",
    )
    monkeypatch.setattr(
        cli,
        "validate_evolutionary_spec",
        lambda path: (spec, {}, [SimpleNamespace()]),
    )

    def _unexpected_run(path):
        raise AssertionError("validate-only must not start a search")

    monkeypatch.setattr(cli, "run_evolutionary_search", _unexpected_run)

    assert cli.main(["--spec", "synthetic.yaml", "--validate-only"]) == 0
    assert "No experiment or evolutionary search was executed." in capsys.readouterr().out
