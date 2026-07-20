from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src.experiments.evolutionary.fitness import FitnessResult
from src.experiments.evolutionary.runner import (
    _handle_duplicate,
    _validate_and_set_study_contract,
    run_evolutionary_search,
)
from src.experiments.evolutionary.schemas import load_evolutionary_spec


SPEC_PATH = Path(
    "config/evolutionary/ethusd_foundation/ga_ethusd_feature_gate_v1.yaml"
)


class FakeTrial:
    def __init__(self, number: int, genome: dict[str, object]) -> None:
        self.number = number
        self.params: dict[str, object] = {}
        self.user_attrs: dict[str, object] = {}
        self.system_attrs: dict[str, object] = {}
        self.state = SimpleNamespace(name="RUNNING")
        self.value = None
        self.values = []
        self.datetime_start = None
        self.datetime_complete = None
        self._genome = genome

    def set_user_attr(self, name: str, value: object) -> None:
        self.user_attrs[name] = value

    def suggest_categorical(self, name: str, choices: list[object]):
        value = self._genome[name]
        assert value in choices
        self.params[name] = value
        return value


class FakeStudy:
    def __init__(self) -> None:
        self.study_name = "fake"
        self.trials: list[FakeTrial] = []
        self.user_attrs: dict[str, object] = {}
        self._queued: list[dict[str, object]] = []
        self.best_trials = []

    def set_user_attr(self, name: str, value: object) -> None:
        self.user_attrs[name] = value

    def enqueue_trial(self, genome: dict[str, object], user_attrs=None) -> None:
        self._queued.append(dict(genome))

    def optimize(self, objective, *, n_trials: int, n_jobs: int, catch) -> None:
        assert n_jobs == 1
        assert n_trials == len(self._queued)
        for number, genome in enumerate(self._queued):
            trial = FakeTrial(number, genome)
            value = objective(trial)
            trial.value = value
            trial.values = [value]
            trial.state = SimpleNamespace(name="COMPLETE")
            self.trials.append(trial)


def test_runner_executes_mocked_experiments_and_records_identity_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    payload["search"]["population_size"] = 2
    payload["search"]["generations"] = 1
    payload["search"]["storage"] = f"sqlite:///{tmp_path / 'search' / 'study.db'}"
    payload["artifacts"]["output_dir"] = str(tmp_path / "search")
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    study = FakeStudy()
    fake_optuna = SimpleNamespace(
        samplers=SimpleNamespace(NSGAIISampler=lambda **kwargs: SimpleNamespace(**kwargs)),
        create_study=lambda **kwargs: study,
    )
    experiment_calls: list[str] = []

    monkeypatch.setattr(
        "src.experiments.evolutionary.runner._require_optuna", lambda: fake_optuna
    )
    monkeypatch.setattr(
        "src.experiments.evolutionary.runner._run_experiment_config",
        lambda candidate: experiment_calls.append(candidate.candidate_hash)
        or SimpleNamespace(),
    )
    monkeypatch.setattr(
        "src.experiments.evolutionary.runner.score_candidate",
        lambda result, spec, context: FitnessResult(
            score=1.0,
            rejected=False,
            reason=None,
            components={"mock": 1.0},
            resolved_metrics={"mock.metric": 1.0},
        ),
    )

    returned = run_evolutionary_search(spec_path)

    assert returned is study
    assert len(experiment_calls) == 2
    assert len(study.trials) == 2
    assert study.user_attrs["search_name"] == payload["search"]["name"]
    assert study.user_attrs["decoder_contract_hash"]
    assert study.user_attrs["search_contract_hash"]
    for trial in study.trials:
        assert trial.user_attrs["decoded_config_hash"]
        assert trial.user_attrs["decoder_contract_hash"]
        assert trial.user_attrs["search_contract_hash"]
        assert trial.user_attrs["fitness_components"] == {"mock": 1.0}
        assert trial.user_attrs["resolved_metrics"] == {"mock.metric": 1.0}
        assert trial.user_attrs["promotion_passed"] is False


@pytest.mark.parametrize(
    ("policy", "handled", "expected_value"),
    [
        ("reuse", True, 3.5),
        ("reject", True, -1000000000000.0),
        ("reevaluate", False, None),
    ],
)
def test_duplicate_policies(
    policy: str,
    handled: bool,
    expected_value: float | None,
) -> None:
    source = load_evolutionary_spec(SPEC_PATH)
    spec = replace(source, search=replace(source.search, duplicate_policy=policy))
    trial = FakeTrial(2, {})
    duplicate = {
        "trial": 1,
        "value": 3.5,
        "rejected": False,
        "failure_reason": None,
        "fitness_components": {"score": 3.5},
        "resolved_metrics": {"metric": 3.5},
        "promotion_passed": True,
        "promotion_failures": [],
        "promotion_metrics": {"gate": 1.0},
    }

    result = _handle_duplicate(trial, spec=spec, duplicate=deepcopy(duplicate))

    assert result == (handled, expected_value)
    if policy == "reuse":
        assert trial.user_attrs["duplicate_reused"] is True
        assert trial.user_attrs["promotion_passed"] is True
    elif policy == "reject":
        assert trial.user_attrs["rejected"] is True
        assert trial.user_attrs["promotion_passed"] is False
    else:
        assert "duplicate_of" not in trial.user_attrs


def test_existing_optuna_study_contract_mismatch_fails_closed() -> None:
    study = FakeStudy()
    study.user_attrs = {
        "search_name": "expected",
        "decoder_contract_hash": "decoder",
        "search_contract_hash": "old-search",
    }

    with pytest.raises(ValueError, match="search_contract_hash"):
        _validate_and_set_study_contract(
            study,
            search_name="expected",
            decoder_hash="decoder",
            search_hash="new-search",
            base_config_hash="base",
        )


def test_existing_optuna_study_with_same_contract_is_accepted() -> None:
    study = FakeStudy()
    study.user_attrs = {
        "search_name": "expected",
        "decoder_contract_hash": "decoder",
        "search_contract_hash": "search",
    }

    _validate_and_set_study_contract(
        study,
        search_name="expected",
        decoder_hash="decoder",
        search_hash="search",
        base_config_hash="base",
    )

    assert study.user_attrs["base_config_hash"] == "base"


def test_existing_optuna_study_decoder_contract_mismatch_fails_closed() -> None:
    study = FakeStudy()
    study.user_attrs = {
        "search_name": "expected",
        "decoder_contract_hash": "old-decoder",
        "search_contract_hash": "search",
    }

    with pytest.raises(ValueError, match="decoder_contract_hash"):
        _validate_and_set_study_contract(
            study,
            search_name="expected",
            decoder_hash="new-decoder",
            search_hash="search",
            base_config_hash="base",
        )


def test_existing_optuna_study_requires_explicit_search_name_match() -> None:
    study = FakeStudy()
    study.user_attrs = {
        "search_name": "old-name",
        "decoder_contract_hash": "decoder",
        "search_contract_hash": "search",
    }

    with pytest.raises(ValueError, match="search_name"):
        _validate_and_set_study_contract(
            study,
            search_name="new-name",
            decoder_hash="decoder",
            search_hash="search",
            base_config_hash="base",
        )
