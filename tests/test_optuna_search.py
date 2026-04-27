from __future__ import annotations

import json
from datetime import datetime, timezone
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
    build_study_report_payload,
    compute_derived_metrics,
    extract_objective_value,
    get_nested_value,
    load_search_space_yaml,
    normalize_objective_spec,
    normalize_pruning_spec,
    optimize_experiment,
    prepare_trial_config,
    score_experiment_result,
    validate_search_space_feature_contract,
    write_study_report,
)
from src.experiments.optuna_search import _run_dir_timestamp as _optuna_run_dir_timestamp
from src.experiments.optuna_runtime import report_optuna_fold
from src.experiments.orchestration.pipeline import _run_dir_timestamp as _experiment_run_dir_timestamp
from src.experiments.orchestration.types import ExperimentResult
from src.utils.config import load_experiment_config
from src.utils.config_validation import validate_resolved_config


class _FakeTrial:
    def __init__(self, *, number: int = 0) -> None:
        self.number = number
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


def test_run_dir_timestamps_use_athens_timezone() -> None:
    winter_utc = datetime(2024, 1, 1, 21, 30, 0, tzinfo=timezone.utc)
    summer_utc = datetime(2024, 7, 1, 21, 30, 0, tzinfo=timezone.utc)

    assert _experiment_run_dir_timestamp(winter_utc) == "20240101_233000_000000"
    assert _optuna_run_dir_timestamp(winter_utc) == "20240101_233000_000000"
    assert _experiment_run_dir_timestamp(summer_utc) == "20240702_003000_000000"
    assert _optuna_run_dir_timestamp(summer_utc) == "20240702_003000_000000"


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


def test_prepare_trial_config_appends_trial_number_to_logged_run_name() -> None:
    base_config = {
        "model": {"params": {"learning_rate": 0.03}},
        "logging": {
            "enabled": True,
            "run_name": "ftmo_fx_intraday_regime_xgboost_v1",
            "stage_tails": {
                "enabled": True,
                "stdout": True,
                "report": True,
            },
        },
    }
    search_space = [
        SearchDimension(
            name="learning_rate",
            path="model.params.learning_rate",
            kind="float",
            low=0.01,
            high=0.10,
        )
    ]

    trial_cfg = prepare_trial_config(
        base_config,
        trial_params={"learning_rate": 0.05},
        search_space=search_space,
        logging_enabled=True,
        trial_number=32,
    )

    assert trial_cfg["logging"]["enabled"] is True
    assert trial_cfg["logging"]["run_name"] == "ftmo_fx_intraday_regime_xgboost_v1_trial_0032"
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
                    metric_path="derived.turnover_event_count",
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
    # turnover_event_count = 2 => violated => -1.0
    assert score == pytest.approx(1.3)


def test_compute_derived_metrics_separates_turnover_events_from_entries() -> None:
    positions = pd.Series([0.0, 1.0, 1.0, 0.0, -1.0, -1.0, 0.0, 1.0, -1.0, 0.0])
    turnover = positions.diff().abs().fillna(0.0)
    result = SimpleNamespace(
        evaluation={
            "scope": "timeline",
            "fold_backtest_summaries": [
                {"fold": 0, "metrics": {"total_turnover": 0.0, "net_pnl": 0.0, "gross_pnl": 0.0}},
                {"fold": 1, "metrics": {"total_turnover": 1.0, "net_pnl": 0.2, "gross_pnl": 0.3}},
                {"fold": 2, "metrics": {"total_turnover": 0.5, "net_pnl": -0.1, "gross_pnl": -0.05}},
                {"fold": 3, "metrics": {"total_turnover": 0.0, "net_pnl": 0.0, "gross_pnl": 0.2}},
            ],
        },
        backtest=SimpleNamespace(positions=positions, turnover=turnover),
        data=pd.DataFrame(index=positions.index),
    )

    metrics = compute_derived_metrics(result)

    assert metrics["turnover_event_count"] == pytest.approx(7.0)
    assert metrics["trade_count"] == pytest.approx(metrics["turnover_event_count"])
    assert metrics["entry_count"] == pytest.approx(4.0)
    assert metrics["exit_count"] == pytest.approx(4.0)
    assert metrics["round_trip_count"] == pytest.approx(4.0)
    assert metrics["exposure_bar_count"] == pytest.approx(6.0)
    assert metrics["active_fold_count"] == pytest.approx(3.0)
    assert metrics["profitable_fold_count"] == pytest.approx(1.0)
    assert metrics["losing_fold_count"] == pytest.approx(1.0)


def test_compute_derived_metrics_weekly_participation_uses_strict_oos_entries() -> None:
    index = pd.date_range("2024-01-01", periods=26, freq="D", tz="UTC")
    positions = pd.Series(0.0, index=index)
    positions.loc["2024-01-02":"2024-01-08"] = 1.0
    positions.loc["2024-01-10":"2024-01-11"] = 1.0
    positions.loc["2024-01-15":"2024-01-17"] = -1.0
    positions.loc["2024-01-18":"2024-01-20"] = 1.0
    result = SimpleNamespace(
        evaluation={"scope": "strict_oos_only"},
        backtest=SimpleNamespace(
            positions=positions,
            turnover=positions.diff().abs().fillna(0.0),
        ),
        data=pd.DataFrame(
            {"pred_is_oos": index >= pd.Timestamp("2024-01-08", tz="UTC")},
            index=index,
        ),
    )

    metrics = compute_derived_metrics(result)

    assert metrics["entry_count"] == pytest.approx(3.0)
    assert metrics["total_week_count"] == pytest.approx(3.0)
    assert metrics["active_week_count"] == pytest.approx(2.0)
    assert metrics["inactive_week_count"] == pytest.approx(1.0)
    assert metrics["active_week_ratio"] == pytest.approx(2.0 / 3.0)
    assert metrics["min_entries_per_week"] == pytest.approx(0.0)
    assert metrics["median_entries_per_week"] == pytest.approx(1.0)
    assert metrics["mean_entries_per_week"] == pytest.approx(1.0)
    assert get_nested_value(result, "derived.active_week_ratio") == pytest.approx(2.0 / 3.0)


def test_compute_derived_metrics_weekly_participation_uses_portfolio_weights() -> None:
    index = pd.date_range("2024-01-01", periods=26, freq="D", tz="UTC")
    weights = pd.DataFrame(0.0, index=index, columns=["EURUSD", "GBPUSD"])
    weights.loc["2024-01-02":"2024-01-05", "EURUSD"] = 0.10
    weights.loc["2024-01-10":"2024-01-11", "EURUSD"] = 0.10
    weights.loc["2024-01-15":"2024-01-17", "GBPUSD"] = -0.10
    weights.loc["2024-01-18":"2024-01-20", "EURUSD"] = 0.10
    oos = pd.Series(index >= pd.Timestamp("2024-01-08", tz="UTC"), index=index)
    result = SimpleNamespace(
        evaluation={"scope": "strict_oos_only"},
        backtest=SimpleNamespace(turnover=weights.diff().abs().sum(axis=1).fillna(0.0)),
        portfolio_weights=weights,
        data={
            "EURUSD": pd.DataFrame({"pred_is_oos": oos}, index=index),
            "GBPUSD": pd.DataFrame({"pred_is_oos": oos}, index=index),
        },
    )

    metrics = compute_derived_metrics(result)

    assert metrics["entry_count"] == pytest.approx(3.0)
    assert metrics["exposure_bar_count"] == pytest.approx(8.0)
    assert metrics["total_week_count"] == pytest.approx(3.0)
    assert metrics["active_week_count"] == pytest.approx(2.0)
    assert metrics["active_week_ratio"] == pytest.approx(2.0 / 3.0)


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

    monkeypatch.setattr(
        optuna_mod,
        "load_experiment_config",
        lambda path: {"logging": {"enabled": True, "run_name": "unit_optuna"}},
    )
    monkeypatch.setattr(
        optuna_mod,
        "_run_experiment_from_config",
        lambda cfg, config_path: SimpleNamespace(
            evaluation={"primary_summary": {"sharpe": 2.25, "profit_factor": 1.8}},
            artifacts={
                "run_dir": "logs/experiments/unit_optuna_trial_0032_20260413_000000_deadbee",
                "report": "logs/experiments/unit_optuna_trial_0032_20260413_000000_deadbee/report.md",
                "report_html": "logs/experiments/unit_optuna_trial_0032_20260413_000000_deadbee/report.html",
            },
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
        logging_enabled=True,
        catch_exceptions=False,
    )

    trial = _FakeTrial(number=32)
    score = objective(trial)

    assert score == pytest.approx(2.25)
    assert trial.user_attrs["trial_failed"] is False
    assert trial.user_attrs["primary_summary"] == {"sharpe": 2.25, "profit_factor": 1.8}
    assert trial.user_attrs["experiment_run_name"] == "unit_optuna_trial_0032"
    assert trial.user_attrs["experiment_run_dir"] == "logs/experiments/unit_optuna_trial_0032_20260413_000000_deadbee"
    assert (
        trial.user_attrs["experiment_report"]
        == "logs/experiments/unit_optuna_trial_0032_20260413_000000_deadbee/report.md"
    )
    assert (
        trial.user_attrs["experiment_report_html"]
        == "logs/experiments/unit_optuna_trial_0032_20260413_000000_deadbee/report.html"
    )


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
    validate_search_space_feature_contract(base_cfg, search_space)

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
    assert payload["base_config"] == "config/experiments/btcusd_1h_shock_meta_xgboost_long_only.yaml"
    assert objective.metric_path == "evaluation.primary_summary.sharpe"
    assert pruning.metric_path == "classification_metrics.roc_auc"
    constraints_by_path = {constraint.metric_path: constraint for constraint in objective.constraints}
    assert constraints_by_path["derived.turnover_event_count"].threshold == pytest.approx(75.0)
    assert constraints_by_path["derived.turnover_event_count"].penalty == pytest.approx(1.0e12)
    assert constraints_by_path["evaluation.primary_summary.total_turnover"].threshold == pytest.approx(30.0)
    assert constraints_by_path["evaluation.primary_summary.total_turnover"].penalty == pytest.approx(1.0e12)
    assert trial_cfg["model"]["feature_selectors"]["strict"]["min_count"] == 21
    assert trial_cfg["model"]["target"]["max_holding"] == 12
    assert trial_cfg["signals"]["params"]["upper_exit"] == 0.50
    assert trial_cfg["signals"]["params"]["mode"] == "long_only"
    assert trial_cfg["backtest"]["min_holding_bars"] == 1
    assert trial_cfg["risk"]["dd_guard"]["cooloff_bars"] == 24
    assert trial_cfg["logging"]["enabled"] is False
    assert trial_cfg["logging"]["stage_tails"]["stdout"] is False


def test_ftmo_optuna_v2_yaml_matches_base_config_contract() -> None:
    optuna_cfg_path = Path("config/optuna/optuna_ftmo_fx_intraday_regime_xgboost_v2.yaml")
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
    constraints_by_path = {constraint.metric_path: constraint for constraint in objective.constraints}
    risk_leverage = {dimension.name: dimension for dimension in search_space}["risk_max_leverage"]
    signal_clip = {dimension.name: dimension for dimension in search_space}["signal_clip"]
    assert payload["base_config"] == "config/experiments/ftmo_fx_intraday_regime_xgboost_v1.yaml"
    assert payload["study"]["study_name"] == "optuna_ftmo_fx_intraday_regime_xgboost_v2"
    assert payload["report"]["run_name"] == "optuna_ftmo_fx_intraday_regime_xgboost_v2"
    assert objective.metric_path == "evaluation.primary_summary.sharpe"
    assert objective.stability_weight == pytest.approx(1.0)
    assert constraints_by_path["evaluation.primary_summary.cumulative_return"].threshold == pytest.approx(0.0)
    assert constraints_by_path["evaluation.primary_summary.cumulative_return"].penalty == pytest.approx(1.0e12)
    assert constraints_by_path["evaluation.primary_summary.sharpe"].threshold == pytest.approx(0.0)
    assert constraints_by_path["evaluation.primary_summary.sharpe"].penalty == pytest.approx(10.0)
    profit_factor_constraints = [
        constraint
        for constraint in objective.constraints
        if constraint.metric_path == "evaluation.primary_summary.profit_factor"
    ]
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(1.0)
        and constraint.penalty == pytest.approx(5.0)
        for constraint in profit_factor_constraints
    )
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(1.10)
        and constraint.penalty == pytest.approx(1.25)
        for constraint in profit_factor_constraints
    )
    assert constraints_by_path["derived.active_fold_count"].threshold == pytest.approx(6.0)
    assert constraints_by_path["derived.active_fold_count"].penalty == pytest.approx(2.0)
    active_week_ratio_constraints = [
        constraint for constraint in objective.constraints if constraint.metric_path == "derived.active_week_ratio"
    ]
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(0.60)
        and constraint.penalty == pytest.approx(4.0)
        for constraint in active_week_ratio_constraints
    )
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(0.80)
        and constraint.penalty == pytest.approx(1.5)
        for constraint in active_week_ratio_constraints
    )
    entry_count_constraints = [
        constraint for constraint in objective.constraints if constraint.metric_path == "derived.entry_count"
    ]
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(20.0)
        and constraint.penalty == pytest.approx(5.0)
        for constraint in entry_count_constraints
    )
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(50.0)
        and constraint.penalty == pytest.approx(1.5)
        for constraint in entry_count_constraints
    )
    assert risk_leverage.choices == [0.25]
    assert max(signal_clip.choices or []) == pytest.approx(0.25)
    assert pruning.metric_path == "classification_metrics.roc_auc"
    assert trial_cfg["model"]["split"]["max_folds"] == 24
    assert trial_cfg["model"]["target"]["max_holding"] == 18
    assert trial_cfg["data"]["storage"]["dataset_id"] == "ftmo_fx_intraday_regime_xgboost_v2"
    assert trial_cfg["risk"]["max_leverage"] == pytest.approx(0.25)
    assert trial_cfg["logging"]["run_name"] == "ftmo_fx_intraday_regime_xgboost_v2"
    assert trial_cfg["logging"]["enabled"] is False


def test_ftmo_panel_optuna_yaml_matches_base_config_contract() -> None:
    optuna_cfg_path = Path("config/optuna/optuna_ftmo_fx_intraday_panel_4pair_xgboost_garch_2y_v1.yaml")
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
    constraints_by_path = {constraint.metric_path: constraint for constraint in objective.constraints}
    search_dims_by_name = {dimension.name: dimension for dimension in search_space}
    search_names = set(search_dims_by_name)
    assert payload["base_config"] == "config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_garch_2y_v1.yaml"
    assert payload["study"]["study_name"] == "optuna_ftmo_fx_intraday_panel_4pair_xgboost_garch_2y_v1"
    assert payload["report"]["run_name"] == "optuna_ftmo_fx_intraday_panel_4pair_xgboost_garch_2y_v1"
    assert objective.metric_path == "evaluation.ftmo_objective.score"
    assert objective.failure_score == pytest.approx(-1.0e15)
    assert objective.stability_weight == pytest.approx(1.0)
    assert constraints_by_path["evaluation.primary_summary.cumulative_return"].threshold == pytest.approx(0.0)
    assert constraints_by_path["evaluation.primary_summary.cumulative_return"].penalty == pytest.approx(1.0e12)
    assert constraints_by_path["evaluation.primary_summary.max_drawdown"].threshold == pytest.approx(-0.08)
    assert constraints_by_path["evaluation.ftmo_metrics.worst_weekly_drawdown"].threshold == pytest.approx(-0.04)
    assert constraints_by_path["evaluation.ftmo_metrics.weekly_drawdown_breach_count"].penalty == pytest.approx(1.0e12)
    assert constraints_by_path["evaluation.ftmo_metrics.daily_loss_breach_count"].penalty == pytest.approx(1.0e12)
    assert constraints_by_path["evaluation.ftmo_metrics.max_total_loss_breach_count"].penalty == pytest.approx(1.0e12)
    assert constraints_by_path["derived.active_fold_count"].threshold == pytest.approx(8.0)
    assert constraints_by_path["derived.profitable_fold_count"].threshold == pytest.approx(5.0)
    active_week_ratio_constraints = [
        constraint for constraint in objective.constraints if constraint.metric_path == "derived.active_week_ratio"
    ]
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(0.55)
        and constraint.penalty == pytest.approx(4.0)
        for constraint in active_week_ratio_constraints
    )
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(0.75)
        and constraint.penalty == pytest.approx(1.5)
        for constraint in active_week_ratio_constraints
    )
    weekly_target_hit_ratio_constraints = [
        constraint
        for constraint in objective.constraints
        if constraint.metric_path == "evaluation.ftmo_metrics.weekly_target_hit_ratio"
    ]
    assert any(
        constraint.op == "lt"
        and constraint.threshold == pytest.approx(0.25)
        and constraint.penalty == pytest.approx(4.0)
        for constraint in weekly_target_hit_ratio_constraints
    )
    assert all(not name.startswith("tb_") for name in search_names)
    assert pruning.metric_path == "classification_metrics.roc_auc"
    assert trial_cfg["data"]["symbols"] == ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    assert sorted(trial_cfg["data"]["storage"]["load_paths"]) == ["AUDUSD", "EURUSD", "GBPUSD", "USDJPY"]
    assert trial_cfg["data"]["end"] == "2024-10-01 00:00:00"
    assert trial_cfg["model"]["split"]["max_folds"] == 20
    assert trial_cfg["model"]["target"]["kind"] == "forward_return"
    assert trial_cfg["model"]["target"]["horizon"] == 18
    assert trial_cfg["model"]["feature_selectors"]["profile"] == "ftmo_fx_intraday_balanced_v1"
    assert "vol_window_short" not in search_names
    assert "trend_sma_fast" not in search_names
    assert "trend_sma_slow" not in search_names
    assert "adx_window" not in search_names
    assert "regime_vol_short" not in search_names
    assert "regime_vol_long" not in search_names
    assert search_dims_by_name["vol_norm_vol_col"].choices == [
        "vol_rolling_12",
        "vol_rolling_24",
        "vol_rolling_48",
        "vol_rolling_72",
        "vol_rolling_96",
        "vol_rolling_120",
        "vol_rolling_168",
    ]
    assert search_dims_by_name["activation_adx_selector"].choices == ["adx_14", "adx_18", "adx_24", "adx_30"]
    assert trial_cfg["features"][13]["params"]["vol_col"] == "vol_rolling_12"
    assert trial_cfg["features"][3]["params"]["base_sma_for_sign"] == 72
    assert trial_cfg["features"][3]["params"]["short_sma"] == 24
    assert trial_cfg["features"][3]["params"]["long_sma"] == 72
    assert trial_cfg["signals"]["params"]["activation_filters"][2]["selector"]["exact"] == "adx_14"
    assert (
        trial_cfg["signals"]["params"]["activation_filters"][3]["selector"]["exact"]
        == "regime_vol_ratio_12_120"
    )
    assert trial_cfg["portfolio"]["enabled"] is True
    assert trial_cfg["portfolio"]["gross_target"] == pytest.approx(0.20)
    assert trial_cfg["portfolio"]["constraints"]["max_gross_leverage"] == pytest.approx(0.35)
    assert trial_cfg["portfolio"]["constraints"]["max_weight"] == pytest.approx(0.08)
    assert trial_cfg["portfolio"]["constraints"]["min_weight"] == pytest.approx(-0.08)
    assert trial_cfg["backtest"]["min_holding_bars"] == 4
    assert trial_cfg["logging"]["run_name"] == "ftmo_fx_intraday_panel_4pair_xgboost_garch_2y_v1"
    assert trial_cfg["logging"]["enabled"] is False


def test_ftmo_triple_barrier_meta_optuna_yaml_matches_base_config_contract() -> None:
    optuna_cfg_path = Path("config/optuna/optuna_ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1.yaml")
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
    search_dims_by_name = {dimension.name: dimension for dimension in search_space}
    search_paths = {dimension.path for dimension in search_space}
    assert (
        payload["base_config"]
        == "config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1.yaml"
    )
    assert payload["study"]["study_name"] == "optuna_ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1"
    assert payload["report"]["run_name"] == "optuna_ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1"
    assert objective.metric_path == "evaluation.ftmo_objective.score"
    assert objective.failure_score == pytest.approx(-1.0e15)
    assert objective.stability_weight == pytest.approx(0.5)
    assert objective.stability_std_penalty == pytest.approx(1.0)
    assert pruning.enabled is False
    assert pruning.metric_path == "classification_metrics.roc_auc"
    assert pruning.pruner == "none"

    assert trial_cfg["data"]["end"] == "2024-10-01 00:00:00"
    assert trial_cfg["data"]["storage"]["dataset_id"] == "ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1"
    assert trial_cfg["model"]["split"]["max_folds"] == 12
    assert trial_cfg["model"]["kind"] == "xgboost_clf"
    assert trial_cfg["model"]["feature_selectors"]["profile"] == "ftmo_fx_intraday_balanced_v1"
    assert trial_cfg["model"]["target"]["kind"] == "triple_barrier"
    assert trial_cfg["model"]["target"]["label_mode"] == "meta"
    assert trial_cfg["model"]["target"]["entry_price_mode"] == "next_open"
    assert trial_cfg["model"]["target"]["neutral_label"] == "lower"
    assert trial_cfg["model"]["target"]["tie_break"] == "lower"
    assert trial_cfg["model"]["target"]["side_col"] == "primary_side"
    assert trial_cfg["model"]["target"]["candidate_col"] == "trade_candidate"
    assert trial_cfg["model"]["target"]["max_holding"] == 12
    assert trial_cfg["model"]["target"]["upper_mult"] == pytest.approx(1.0)
    assert trial_cfg["model"]["target"]["lower_mult"] == pytest.approx(1.0)
    assert trial_cfg["model"]["target"]["vol_window"] == 12

    assert trial_cfg["features"][14]["step"] == "shock_context"
    assert trial_cfg["features"][14]["params"]["ret_z_threshold"] == pytest.approx(1.0)
    assert trial_cfg["features"][14]["params"]["atr_mult_threshold"] == pytest.approx(0.5)
    assert trial_cfg["features"][14]["params"]["distance_from_mean_threshold"] == pytest.approx(0.3)
    assert trial_cfg["features"][14]["params"]["post_shock_active_bars"] == 1
    assert trial_cfg["features"][14]["params"]["short_horizon"] == 1
    assert trial_cfg["features"][14]["params"]["medium_horizon"] == 4
    assert trial_cfg["features"][15]["step"] == "lags"
    assert trial_cfg["features"][15]["params"]["lags"][2] == 3
    assert trial_cfg["features"][15]["params"]["lags"][3] == 12

    assert trial_cfg["signals"]["kind"] == "meta_probability_side"
    assert trial_cfg["signals"]["params"]["side_col"] == "primary_side"
    assert trial_cfg["signals"]["params"]["candidate_col"] == "label_candidate"
    assert trial_cfg["signals"]["params"]["signal_col"] == "signal_meta_side"
    assert trial_cfg["signals"]["params"]["threshold"] == pytest.approx(0.50)
    assert trial_cfg["signals"]["params"]["upper"] == pytest.approx(0.62)
    assert trial_cfg["signals"]["params"]["clip"] == pytest.approx(0.5)
    assert "signals.params.upper" not in search_paths
    assert "signals.params.lower" not in search_paths
    assert not any(path.startswith("signals.params.activation_filters") for path in search_paths)

    assert trial_cfg["risk"]["sizing"]["kind"] == "ftmo_risk_per_trade"
    assert trial_cfg["risk"]["sizing"]["confidence_mode"] == "meta_success"
    assert trial_cfg["risk"]["sizing"]["risk_per_trade"] == pytest.approx(0.0025)
    assert trial_cfg["risk"]["sizing"]["confidence_floor"] == pytest.approx(0.50)
    assert trial_cfg["risk"]["sizing"]["confidence_power"] == pytest.approx(1.0)
    assert trial_cfg["risk"]["sizing"]["max_leverage"] == pytest.approx(1.0)
    assert trial_cfg["backtest"]["signal_col"] == "signal_meta_side"
    assert trial_cfg["portfolio"]["gross_target"] == pytest.approx(1.0)
    assert trial_cfg["portfolio"]["constraints"]["max_gross_leverage"] == pytest.approx(1.0)
    assert trial_cfg["portfolio"]["constraints"]["max_weight"] == pytest.approx(0.40)
    assert trial_cfg["portfolio"]["constraints"]["min_weight"] == pytest.approx(-0.40)

    assert trial_cfg["model"]["params"]["n_estimators"] == 150
    assert trial_cfg["model"]["params"]["learning_rate"] == pytest.approx(0.01)
    assert trial_cfg["model"]["params"]["max_depth"] == 2
    assert trial_cfg["model"]["params"]["min_child_weight"] == pytest.approx(4.0)
    assert trial_cfg["model"]["params"]["subsample"] == pytest.approx(0.6)
    assert trial_cfg["model"]["params"]["colsample_bytree"] == pytest.approx(0.6)
    assert trial_cfg["model"]["params"]["reg_lambda"] == pytest.approx(0.5)
    assert trial_cfg["model"]["params"]["reg_alpha"] == pytest.approx(0.0)
    assert trial_cfg["model"]["params"]["scale_pos_weight"] == pytest.approx(1.0)
    assert search_dims_by_name["vol_norm_vol_col"].choices == [
        "vol_rolling_12",
        "vol_rolling_24",
        "vol_rolling_48",
        "vol_rolling_72",
        "vol_rolling_96",
        "vol_rolling_120",
        "vol_rolling_168",
    ]
    assert trial_cfg["logging"]["run_name"] == "ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1"
    assert trial_cfg["logging"]["enabled"] is False


def test_optuna_feature_contract_rejects_unguaranteed_downstream_columns() -> None:
    base_cfg = load_experiment_config(
        "config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_garch_2y_v1.yaml"
    )
    search_space = [
        SearchDimension(
            name="trend_sma_fast",
            path="features.2.params.sma_windows.0",
            kind="categorical",
            choices=[36, 48],
        ),
        SearchDimension(
            name="adx_window",
            path="features.9.params.windows.2",
            kind="categorical",
            choices=[14, 18],
        ),
    ]

    with pytest.raises(ValueError, match="Optuna search_space feature contract is invalid"):
        validate_search_space_feature_contract(base_cfg, search_space)


def test_optuna_template_yaml_matches_declared_contract() -> None:
    optuna_cfg_path = Path("config/optuna/template_optuna_full.yaml")
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
    assert payload["base_config"] == "config/experiments/btcusd_1h_shock_meta_xgboost_long_only.yaml"
    assert objective.metric_path == "evaluation.primary_summary.sharpe"
    assert objective.constraints[1].metric_path == "derived.turnover_event_count"
    assert pruning.pruner == "median"
    assert {dimension.kind for dimension in search_space} == {"bool", "categorical", "float", "int"}


def test_optimize_experiment_wires_fake_optuna_study(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(
        optuna_mod,
        "write_study_report",
        lambda *args, **kwargs: {
            "report": str(tmp_path / "report.md"),
            "report_html": str(tmp_path / "report.html"),
        },
    )

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
        report_output_dir=tmp_path,
        report_run_name="optuna_unit",
    )

    assert study is fake_optuna.study
    assert study.create_kwargs["direction"] == "maximize"
    assert isinstance(study.create_kwargs["sampler"], _FakeTPESampler)
    assert study.create_kwargs["sampler"].seed == 11
    assert isinstance(study.create_kwargs["pruner"], _FakeOptuna.pruners.MedianPruner)
    assert study.user_attrs["config_path"] == "config/experiments/example.yaml"
    assert study.user_attrs["objective_metric"] == "evaluation.primary_summary.sharpe"
    assert study.user_attrs["pruning_metric"] == "classification_metrics.roc_auc"
    assert study.user_attrs["report_artifacts"] == {
        "report": str(tmp_path / "report.md"),
        "report_html": str(tmp_path / "report.html"),
    }
    assert study.optimize_args == {
        "objective": sentinel_objective,
        "n_trials": 7,
        "timeout": 12.5,
        "n_jobs": 2,
    }


def test_optuna_search_cli_runs_yaml_spec_without_real_study(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from src.experiments import optuna_search as optuna_mod

    spec_path = tmp_path / "optuna_cli.yaml"
    spec_path.write_text(
        """
base_config: config/experiments/example.yaml
study:
  study_name: cli_spec
  sampler: random
  seed: 3
  n_trials: 5
  n_jobs: 1
  logging_enabled: false
  catch_exceptions: true
objective:
  metric_path: evaluation.primary_summary.sharpe
  direction: maximize
pruning:
  enabled: false
search_space:
  - name: upper
    path: signals.params.upper
    kind: float
    low: 0.52
    high: 0.60
        """.strip(),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def _fake_optimize_experiment(config_path: str, **kwargs: object) -> SimpleNamespace:
        captured["config_path"] = config_path
        captured.update(kwargs)
        return SimpleNamespace(
            study_name=kwargs.get("study_name"),
            best_trial=SimpleNamespace(number=2, value=1.25, params={"upper": 0.57}),
            user_attrs={
                "report_artifacts": {
                    "report": str(tmp_path / "report.md"),
                    "report_html": str(tmp_path / "report.html"),
                }
            },
        )

    monkeypatch.setattr(optuna_mod, "optimize_experiment", _fake_optimize_experiment)

    exit_code = optuna_mod.main(
        [
            str(spec_path),
            "--n-trials",
            "2",
            "--timeout",
            "12.5",
            "--sampler",
            "tpe",
            "--seed",
            "11",
            "--study-name",
            "cli_override",
            "--report-output-dir",
            str(tmp_path),
            "--report-run-name",
            "cli_report",
        ]
    )

    assert exit_code == 0
    assert captured["config_path"] == "config/experiments/example.yaml"
    assert captured["n_trials"] == 2
    assert captured["timeout"] == pytest.approx(12.5)
    assert captured["sampler"] == "tpe"
    assert captured["seed"] == 11
    assert captured["study_name"] == "cli_override"
    assert captured["report_output_dir"] == str(tmp_path)
    assert captured["report_run_name"] == "cli_report"
    assert captured["search_space"][0].name == "upper"  # type: ignore[index,union-attr]
    assert captured["objective"].metric_path == "evaluation.primary_summary.sharpe"  # type: ignore[union-attr]
    assert captured["pruning"].enabled is False  # type: ignore[union-attr]
    out = capsys.readouterr().out
    assert "Optuna study completed" in out
    assert "Best trial: 2" in out
    assert f"HTML report: {tmp_path / 'report.html'}" in out


def test_write_study_report_persists_optuna_artifacts(tmp_path: Path) -> None:
    completed_trial = SimpleNamespace(
        number=3,
        state=SimpleNamespace(name="COMPLETE"),
        value=1.25,
        datetime_start=None,
        datetime_complete=None,
        params={"signal_upper": 0.57},
        user_attrs={
            "trial_failed": False,
            "primary_summary": {
                "sharpe": 1.25,
                "profit_factor": 1.4,
                "max_drawdown": -0.12,
                "total_turnover": 88.0,
            },
            "derived_metrics": {
                "turnover_event_count": 120.0,
                "trade_count": 120.0,
                "entry_count": 64.0,
                "round_trip_count": 63.0,
            },
            "experiment_run_name": "unit_trial_0003",
            "experiment_run_dir": str(tmp_path / "unit_trial_0003"),
            "experiment_report": str(tmp_path / "unit_trial_0003" / "report.md"),
            "experiment_report_html": str(tmp_path / "unit_trial_0003" / "report.html"),
        },
    )
    failed_trial = SimpleNamespace(
        number=4,
        state=SimpleNamespace(name="COMPLETE"),
        value=-1.0e12,
        datetime_start=None,
        datetime_complete=None,
        params={"signal_upper": 0.61},
        user_attrs={"trial_failed": True, "exception": "ValueError: all-NaN"},
    )
    study = SimpleNamespace(
        study_name="unit_study",
        trials=[failed_trial, completed_trial],
        best_trial=completed_trial,
    )

    artifacts = write_study_report(
        study,
        output_dir=tmp_path,
        run_name="optuna_unit",
        config_path="config/experiments/example.yaml",
        search_space=[
            SearchDimension(
                name="signal_upper",
                path="signals.params.upper",
                kind="float",
                low=0.52,
                high=0.60,
            )
        ],
        objective=ObjectiveSpec(metric_path="evaluation.primary_summary.sharpe"),
        pruning=PruningSpec(enabled=False),
    )

    run_dir = Path(artifacts["run_dir"])
    assert run_dir.parent == tmp_path
    assert Path(artifacts["report"]).exists()
    assert Path(artifacts["report_html"]).exists()
    assert Path(artifacts["trials"]).exists()
    assert Path(artifacts["study_summary"]).exists()
    assert Path(artifacts["manifest"]).exists()

    payload = json.loads(Path(artifacts["study_summary"]).read_text(encoding="utf-8"))
    assert payload["study_name"] == "unit_study"
    assert payload["state_counts"] == {"COMPLETE": 2}
    assert payload["best_trial"]["number"] == 3
    assert payload["best_trial"]["derived_metrics"]["turnover_event_count"] == pytest.approx(120.0)

    trials = pd.read_csv(artifacts["trials"])
    assert set(trials["number"]) == {3, 4}
    assert "summary_sharpe" in trials.columns
    assert "derived_turnover_event_count" in trials.columns
    assert "derived_trade_count" in trials.columns
    assert "param_signal_upper" in trials.columns
    assert "experiment_run_name" in trials.columns
    assert "experiment_run_dir" in trials.columns
    assert "experiment_report" in trials.columns
    assert "experiment_report_html" in trials.columns

    report_text = Path(artifacts["report"]).read_text(encoding="utf-8")
    assert "# Optuna Study Report" in report_text
    assert "Turnover event count" in report_text
    assert "Active week ratio" in report_text
    assert "Experiment run dir" in report_text
    assert "Experiment HTML report" in report_text
    report_html_text = Path(artifacts["report_html"]).read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in report_html_text
    assert "<h1>Optuna Study Report</h1>" in report_html_text


def test_study_report_payload_omits_failed_trials_from_best_trial() -> None:
    failed_trial = SimpleNamespace(
        number=1,
        state=SimpleNamespace(name="COMPLETE"),
        value=-1.0e15,
        datetime_start=None,
        datetime_complete=None,
        params={"x": 1},
        user_attrs={"trial_failed": True, "exception": "KeyError: missing feature"},
    )
    study = SimpleNamespace(
        study_name="all_failed",
        trials=[failed_trial],
        best_trial=failed_trial,
    )

    payload = build_study_report_payload(
        study,
        config_path="config/experiments/example.yaml",
        search_space=[
            SearchDimension(
                name="x",
                path="signals.params.upper",
                kind="categorical",
                choices=[1],
            )
        ],
        objective=ObjectiveSpec(metric_path="evaluation.ftmo_objective.score"),
        pruning=PruningSpec(enabled=False),
    )

    assert payload["clean_complete_count"] == 0
    assert payload["best_trial"] == {}
    assert payload["top_trials"] == []
