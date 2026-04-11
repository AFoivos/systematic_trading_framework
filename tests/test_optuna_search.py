from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from src.backtesting.engine import BacktestResult
from src.experiments.optuna_search import (
    ConstraintPenalty,
    ObjectiveSpec,
    PruningSpec,
    SearchDimension,
    build_study_objective,
    extract_objective_value,
    load_search_space_yaml,
    normalize_objective_spec,
    normalize_pruning_spec,
    optimize_experiment,
    prepare_trial_config,
    score_experiment_result,
)
from src.experiments.optuna_runtime import report_optuna_fold
from src.experiments.orchestration.types import ExperimentResult
from src.utils.config import load_experiment_config
from src.utils.config_validation import validate_resolved_config


class _FakeTrial:
    def __init__(self) -> None:
        self.user_attrs: dict[str, object] = {}

    def suggest_int(self, name: str, **kwargs) -> int:
        low = int(kwargs["low"])
        step = int(kwargs.get("step", 1))
        return low + step

    def suggest_float(self, name: str, **kwargs) -> float:
        low = float(kwargs["low"])
        high = float(kwargs["high"])
        step = kwargs.get("step")
        if step is not None:
            return low + float(step)
        return (low + high) / 2.0

    def suggest_categorical(self, name: str, choices: list[object]) -> object:
        return choices[0]

    def set_user_attr(self, key: str, value: object) -> None:
        self.user_attrs[key] = value


def test_prepare_trial_config_updates_nested_paths_and_disables_logging() -> None:
    base_config = {
        "features": [
            {
                "step": "trend",
                "params": {
                    "ema_spans": [12, 24],
                },
            }
        ],
        "model": {
            "params": {
                "learning_rate": 0.03,
            }
        },
        "logging": {
            "enabled": True,
            "stage_tails": {
                "enabled": True,
                "stdout": True,
                "report": True,
            },
        },
    }
    search_space = [
        SearchDimension(
            name="fast_ema",
            path="features.0.params.ema_spans.0",
            kind="int",
            low=8,
            high=32,
            step=4,
        ),
        SearchDimension(
            name="learning_rate",
            path="model.params.learning_rate",
            kind="float",
            low=0.01,
            high=0.10,
        ),
    ]

    trial_cfg = prepare_trial_config(
        base_config,
        trial_params={
            "fast_ema": 16,
            "learning_rate": 0.05,
        },
        search_space=search_space,
        logging_enabled=False,
    )

    assert base_config["features"][0]["params"]["ema_spans"][0] == 12
    assert base_config["model"]["params"]["learning_rate"] == 0.03
    assert trial_cfg["features"][0]["params"]["ema_spans"][0] == 16
    assert trial_cfg["model"]["params"]["learning_rate"] == pytest.approx(0.05)
    assert trial_cfg["logging"]["enabled"] is False
    assert trial_cfg["logging"]["stage_tails"] == {
        "enabled": False,
        "stdout": False,
        "report": False,
    }


def test_extract_objective_value_from_experiment_result() -> None:
    returns = pd.Series([0.01, -0.005], dtype=float)
    backtest = BacktestResult(
        equity_curve=pd.Series([1.01, 1.00495], dtype=float),
        returns=returns,
        gross_returns=returns,
        costs=pd.Series([0.0, 0.0], dtype=float),
        positions=pd.Series([1.0, 1.0], dtype=float),
        turnover=pd.Series([0.0, 0.0], dtype=float),
        summary={"sharpe": 1.5},
    )
    result = ExperimentResult(
        config={},
        data=pd.DataFrame(),
        backtest=backtest,
        model=None,
        model_meta={},
        artifacts={},
        evaluation={"primary_summary": {"sharpe": 1.75}},
        monitoring={},
        execution={},
    )

    value = extract_objective_value(
        result,
        objective=ObjectiveSpec(metric_path="evaluation.primary_summary.sharpe"),
    )

    assert value == pytest.approx(1.75)


def test_score_experiment_result_applies_constraints_and_stability() -> None:
    result = SimpleNamespace(
        evaluation={
            "primary_summary": {
                "sharpe": 2.0,
                "max_drawdown": -0.35,
            },
            "fold_backtest_summaries": [
                {"fold": 0, "metrics": {"sharpe": 1.2}},
                {"fold": 1, "metrics": {"sharpe": 0.8}},
            ],
        },
        backtest=SimpleNamespace(
            turnover=pd.Series([1.0, 0.0, 1.0, 0.0], dtype=float),
        ),
        data=pd.DataFrame({"pred_is_oos": [True, True, True, True]}),
    )

    score = score_experiment_result(
        result,
        objective=ObjectiveSpec(
            metric_path="evaluation.primary_summary.sharpe",
            direction="maximize",
            constraints=(
                ConstraintPenalty(
                    metric_path="evaluation.primary_summary.max_drawdown",
                    op="lt",
                    threshold=-0.30,
                    penalty=0.5,
                ),
                ConstraintPenalty(
                    metric_path="derived.trade_count",
                    op="lt",
                    threshold=3.0,
                    penalty=1.0,
                ),
            ),
            stability_weight=1.0,
            stability_metric_path="metrics.sharpe",
            stability_std_penalty=1.0,
        ),
    )

    # base sharpe = 2.0
    # stability = mean(1.2, 0.8) - std = 1.0 - 0.2 = 0.8
    # drawdown constraint violated => -0.5
    # trade_count = 2 => violated => -1.0
    assert score == pytest.approx(1.3)


def test_build_study_objective_returns_failure_score_when_runner_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.experiments import optuna_search as optuna_mod

    monkeypatch.setattr(optuna_mod, "load_experiment_config", lambda path: {"logging": {"enabled": True}})
    monkeypatch.setattr(
        optuna_mod,
        "_run_experiment_from_config",
        lambda cfg, config_path: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    objective = build_study_objective(
        "config/experiments/example.yaml",
        search_space=[
            SearchDimension(
                name="logging_enabled",
                path="logging.enabled",
                kind="bool",
            )
        ],
        objective=ObjectiveSpec(
            metric_path="evaluation.primary_summary.sharpe",
            direction="maximize",
        ),
        catch_exceptions=True,
    )

    trial = _FakeTrial()
    score = objective(trial)

    assert score == pytest.approx(-1.0e12)
    assert trial.user_attrs["trial_failed"] is True
    assert "RuntimeError: boom" in str(trial.user_attrs["exception"])


def test_build_study_objective_records_primary_summary_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.experiments import optuna_search as optuna_mod

    monkeypatch.setattr(optuna_mod, "load_experiment_config", lambda path: {"logging": {"enabled": True}})
    monkeypatch.setattr(
        optuna_mod,
        "_run_experiment_from_config",
        lambda cfg, config_path: SimpleNamespace(
            evaluation={"primary_summary": {"sharpe": 2.25, "profit_factor": 1.8}}
        ),
    )
    objective = build_study_objective(
        "config/experiments/example.yaml",
        search_space=[
            SearchDimension(
                name="logging_enabled",
                path="logging.enabled",
                kind="bool",
            )
        ],
        objective=ObjectiveSpec(metric_path="evaluation.primary_summary.sharpe"),
        catch_exceptions=False,
    )

    trial = _FakeTrial()
    score = objective(trial)

    assert score == pytest.approx(2.25)
    assert trial.user_attrs["trial_failed"] is False
    assert trial.user_attrs["primary_summary"] == {"sharpe": 2.25, "profit_factor": 1.8}


def test_build_study_objective_supports_pruning(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.experiments import optuna_search as optuna_mod

    class _FakeTrialPruned(Exception):
        pass

    class _FakeOptuna:
        TrialPruned = _FakeTrialPruned

    class _PruningTrial(_FakeTrial):
        def __init__(self) -> None:
            super().__init__()
            self.report_calls: list[tuple[float, int]] = []

        def report(self, value: float, step: int) -> None:
            self.report_calls.append((value, step))

        def should_prune(self) -> bool:
            return len(self.report_calls) >= 1

    monkeypatch.setattr(optuna_mod, "_require_optuna", lambda: _FakeOptuna)
    monkeypatch.setattr(optuna_mod, "load_experiment_config", lambda path: {"logging": {"enabled": True}})

    def _mock_run(cfg, config_path):
        report_optuna_fold(
            "xgboost_clf",
            0,
            {"classification_metrics": {"roc_auc": 0.61}},
        )
        return SimpleNamespace(
            evaluation={"primary_summary": {"sharpe": 2.25}}
        )

    monkeypatch.setattr(optuna_mod, "_run_experiment_from_config", _mock_run)

    objective = build_study_objective(
        "config/experiments/example.yaml",
        search_space=[
            SearchDimension(
                name="logging_enabled",
                path="logging.enabled",
                kind="bool",
            )
        ],
        objective=ObjectiveSpec(metric_path="evaluation.primary_summary.sharpe"),
        pruning=PruningSpec(
            enabled=True,
            metric_path="classification_metrics.roc_auc",
            pruner="median",
        ),
        catch_exceptions=False,
    )

    trial = _PruningTrial()
    with pytest.raises(_FakeTrialPruned):
        objective(trial)
    assert trial.report_calls == [(0.61, 0)]
    assert trial.user_attrs["pruning_reports"] == [
        {
            "stage": "xgboost_clf",
            "fold": 0,
            "step": 0,
            "metric_path": "classification_metrics.roc_auc",
            "value": 0.61,
        }
    ]


def test_load_search_space_yaml_accepts_mapping_wrapper(tmp_path: Path) -> None:
    search_path = tmp_path / "space.yaml"
    search_path.write_text(
        """
search_space:
  - name: upper
    path: signals.params.upper
    kind: float
    low: 0.52
    high: 0.60
    step: 0.01
""".strip(),
        encoding="utf-8",
    )

    search_space = load_search_space_yaml(search_path)

    assert len(search_space) == 1
    assert search_space[0].name == "upper"
    assert search_space[0].path == "signals.params.upper"


def test_repo_shock_meta_optuna_yaml_matches_base_config_contract() -> None:
    optuna_cfg_path = Path("config/optuna/optuna_shock_meta_xgboost.yaml")
    payload = yaml.safe_load(optuna_cfg_path.read_text(encoding="utf-8"))

    search_space = load_search_space_yaml(optuna_cfg_path)
    objective = normalize_objective_spec(payload["objective"])
    pruning = normalize_pruning_spec(payload["pruning"])
    base_cfg = load_experiment_config(payload["base_config"])

    trial_params = {}
    for dimension in search_space:
        if dimension.kind == "categorical":
            trial_params[dimension.name] = list(dimension.choices or [])[0]
        elif dimension.kind == "int":
            trial_params[dimension.name] = int(dimension.low)
        elif dimension.kind == "float":
            trial_params[dimension.name] = float(dimension.low)
        else:
            trial_params[dimension.name] = False

    trial_cfg = prepare_trial_config(
        base_cfg,
        trial_params=trial_params,
        search_space=search_space,
        logging_enabled=False,
    )

    validate_resolved_config(trial_cfg)
    assert payload["base_config"] == "config/experiments/btcusd_1h_shock_meta_xgboost.yaml"
    assert objective.metric_path == "evaluation.primary_summary.sharpe"
    assert pruning.metric_path == "classification_metrics.roc_auc"
    assert trial_cfg["model"]["feature_selectors"]["strict"]["min_count"] == 21
    assert trial_cfg["model"]["target"]["max_holding"] == 12
    assert trial_cfg["signals"]["params"]["upper_exit"] == 0.50
    assert trial_cfg["backtest"]["min_holding_bars"] == 1
    assert trial_cfg["risk"]["dd_guard"]["cooloff_bars"] == 24
    assert trial_cfg["logging"]["enabled"] is False
    assert trial_cfg["logging"]["stage_tails"]["stdout"] is False


def test_optimize_experiment_wires_fake_optuna_study(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.experiments import optuna_search as optuna_mod

    class _FakeTPESampler:
        def __init__(self, seed: int | None = None) -> None:
            self.seed = seed

    class _FakeRandomSampler:
        def __init__(self, seed: int | None = None) -> None:
            self.seed = seed

    class _FakeStudy:
        def __init__(self, **kwargs) -> None:
            self.create_kwargs = kwargs
            self.user_attrs: dict[str, object] = {}
            self.optimize_args: dict[str, object] | None = None

        def set_user_attr(self, key: str, value: object) -> None:
            self.user_attrs[key] = value

        def optimize(self, objective, *, n_trials: int, timeout: float | None, n_jobs: int) -> None:
            self.optimize_args = {
                "objective": objective,
                "n_trials": n_trials,
                "timeout": timeout,
                "n_jobs": n_jobs,
            }

    class _FakeOptuna:
        class pruners:
            class NopPruner:
                def __init__(self, *args, **kwargs) -> None:
                    self.args = args
                    self.kwargs = kwargs

            class MedianPruner:
                def __init__(self, *args, **kwargs) -> None:
                    self.args = args
                    self.kwargs = kwargs

            class PercentilePruner:
                def __init__(self, *args, **kwargs) -> None:
                    self.args = args
                    self.kwargs = kwargs

        class samplers:
            TPESampler = _FakeTPESampler
            RandomSampler = _FakeRandomSampler

        def __init__(self) -> None:
            self.study = None

        def create_study(self, **kwargs):
            self.study = _FakeStudy(**kwargs)
            return self.study

    fake_optuna = _FakeOptuna()
    sentinel_objective = object()
    monkeypatch.setattr(optuna_mod, "_require_optuna", lambda: fake_optuna)
    monkeypatch.setattr(optuna_mod, "build_study_objective", lambda *args, **kwargs: sentinel_objective)

    study = optimize_experiment(
        "config/experiments/example.yaml",
        search_space=[
            SearchDimension(
                name="upper",
                path="signals.params.upper",
                kind="float",
                low=0.52,
                high=0.60,
            )
        ],
        objective=ObjectiveSpec(metric_path="evaluation.primary_summary.sharpe", direction="maximize"),
        pruning=PruningSpec(enabled=True, metric_path="classification_metrics.roc_auc", pruner="median"),
        sampler="tpe",
        seed=11,
        n_trials=7,
        timeout=12.5,
        n_jobs=2,
    )

    assert study is fake_optuna.study
    assert study.create_kwargs["direction"] == "maximize"
    assert isinstance(study.create_kwargs["sampler"], _FakeTPESampler)
    assert study.create_kwargs["sampler"].seed == 11
    assert isinstance(study.create_kwargs["pruner"], _FakeOptuna.pruners.MedianPruner)
    assert study.user_attrs["config_path"] == "config/experiments/example.yaml"
    assert study.user_attrs["objective_metric"] == "evaluation.primary_summary.sharpe"
    assert study.user_attrs["pruning_metric"] == "classification_metrics.roc_auc"
    assert study.optimize_args == {
        "objective": sentinel_objective,
        "n_trials": 7,
        "timeout": 12.5,
        "n_jobs": 2,
    }
