from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.experiments.evolutionary.fitness import (
    compute_evolutionary_derived_metrics,
    evaluate_promotion,
    failed_fitness,
    score_candidate,
)
from src.experiments.evolutionary.schemas import (
    EvaluationPolicySpec,
    FitnessComponentSpec,
    FitnessSpec,
    HardConstraintSpec,
    PromotionGateSpec,
    PromotionSpec,
    load_evolutionary_spec,
)


SPEC_PATH = Path(
    "config/evolutionary/ethusd_foundation/ga_ethusd_feature_gate_v1.yaml"
)


def _result(*, sharpe: float = 1.0) -> SimpleNamespace:
    return SimpleNamespace(
        evaluation={"scope": "timeline", "primary_summary": {"sharpe": sharpe}},
        backtest=SimpleNamespace(turnover=None, positions=None, trades=None),
        portfolio_weights=None,
        data={},
        model_meta={},
        config={},
    )


def _spec(
    *,
    components: tuple[FitnessComponentSpec, ...],
    hard_constraints: tuple[HardConstraintSpec, ...] = (),
):
    source = load_evolutionary_spec(SPEC_PATH)
    fitness = FitnessSpec(
        mode="weighted_sum",
        direction="maximize",
        components=components,
        hard_constraints=hard_constraints,
        failure_score=-1234.0,
        evaluation_policy=EvaluationPolicySpec(
            allowed_scopes=("timeline",),
            require_walk_forward=False,
            forbidden_metric_tokens=("holdout",),
        ),
    )
    return replace(source, fitness=fitness)


def _component(
    name: str,
    path: str,
    weight: float = 1.0,
    *,
    missing_policy: str = "reject",
    missing_penalty: float | None = None,
) -> FitnessComponentSpec:
    return FitnessComponentSpec(
        name=name,
        metric_path=path,
        weight=weight,
        transform="identity",
        missing_policy=missing_policy,
        missing_penalty=missing_penalty,
    )


def test_missing_metric_policy_rejects_instead_of_using_zero() -> None:
    spec = _spec(components=(_component("missing", "evaluation.primary_summary.absent"),))

    fitness = score_candidate(_result(), spec, context={})

    assert fitness.rejected is True
    assert fitness.score == spec.fitness.failure_score
    assert "missing finite metric" in str(fitness.reason)


def test_explicit_missing_penalty_is_deterministic() -> None:
    spec = _spec(
        components=(
            _component(
                "missing",
                "evaluation.primary_summary.absent",
                missing_policy="penalize",
                missing_penalty=-7.5,
            ),
        )
    )

    first = score_candidate(_result(), spec, context={})
    second = score_candidate(_result(), spec, context={})

    assert first.rejected is False
    assert first.score == second.score == -7.5


def test_failed_candidate_uses_declared_failure_score() -> None:
    spec = _spec(components=(_component("sharpe", "evaluation.primary_summary.sharpe"),))

    fitness = failed_fitness(spec, "experiment failed")

    assert fitness.rejected is True
    assert fitness.score == -1234.0
    assert fitness.reason == "experiment failed"


def test_hard_constraint_rejects_candidate_before_weighted_score() -> None:
    constraint = HardConstraintSpec(
        name="minimum_sharpe",
        metric_path="evaluation.primary_summary.sharpe",
        operator="ge",
        threshold=2.0,
        missing_policy="reject",
    )
    spec = _spec(
        components=(_component("sharpe", "evaluation.primary_summary.sharpe"),),
        hard_constraints=(constraint,),
    )

    fitness = score_candidate(_result(sharpe=1.0), spec, context={})

    assert fitness.rejected is True
    assert "minimum_sharpe" in str(fitness.reason)


def test_promotion_failure_does_not_reject_or_change_fitness() -> None:
    spec = _spec(
        components=(_component("sharpe", "evaluation.primary_summary.sharpe"),)
    )
    spec = replace(
        spec,
        promotion=PromotionSpec(
            enabled=True,
            gates=(
                PromotionGateSpec(
                    name="strict_sharpe",
                    metric_path="evaluation.primary_summary.sharpe",
                    operator="ge",
                    threshold=2.0,
                    missing_policy="fail",
                ),
            ),
        ),
    )

    fitness = score_candidate(_result(sharpe=1.0), spec, context={})
    promotion = evaluate_promotion(_result(sharpe=1.0), spec, context={})

    assert fitness.rejected is False
    assert fitness.score == 1.0
    assert promotion.passed is False
    assert promotion.metrics == {"evaluation.primary_summary.sharpe": 1.0}
    assert "strict_sharpe" in promotion.failures[0]


def test_missing_promotion_metric_fails_promotion_without_exception() -> None:
    spec = _spec(
        components=(_component("sharpe", "evaluation.primary_summary.sharpe"),)
    )
    spec = replace(
        spec,
        promotion=PromotionSpec(
            enabled=True,
            gates=(
                PromotionGateSpec(
                    name="required_metric",
                    metric_path="evaluation.primary_summary.absent",
                    operator="ge",
                    threshold=0.0,
                    missing_policy="fail",
                ),
            ),
        ),
    )

    promotion = evaluate_promotion(_result(), spec, context={})

    assert promotion.passed is False
    assert promotion.metrics == {}
    assert "missing metric" in promotion.failures[0]


def test_complexity_penalty_and_score_calculation_are_deterministic() -> None:
    spec = _spec(
        components=(
            _component("sharpe", "evaluation.primary_summary.sharpe", 1.0),
            _component("complexity", "genome.complexity", -0.5),
        )
    )

    first = score_candidate(_result(sharpe=1.25), spec, context={"complexity": 0.4})
    second = score_candidate(_result(sharpe=1.25), spec, context={"complexity": 0.4})

    assert first.rejected is False
    assert first.score == second.score == 1.05
    assert first.components == {"sharpe": 1.25, "complexity": -0.2}


def test_matb_complexity_includes_diversification_concentration_and_robustness() -> None:
    trades = pd.DataFrame(
        {
            "asset": ["SPX500", "SPX500", "XAUUSD", "EURUSD"],
            "net_return": [0.04, 0.03, 0.02, 0.01],
            "entry_timestamp": pd.to_datetime(
                ["2022-01-01", "2022-06-01", "2023-01-01", "2023-06-01"], utc=True
            ),
        }
    )
    result = SimpleNamespace(
        evaluation={
            "scope": "timeline",
            "primary_summary": {"mtm_cumulative_return": 0.10},
            "robustness": {
                "walk_forward": {
                    "folds": [
                        {"sharpe": 0.20},
                        {"sharpe": 0.40},
                        {"sharpe": 0.90},
                    ]
                },
                "cost_stress": {"cost_x2": {"cumulative_return": 0.07}},
                "entry_delay": {"delay_1_bars": {"cumulative_return": 0.06}},
            },
        },
        backtest=SimpleNamespace(turnover=None, positions=None, trades=trades),
        portfolio_weights=None,
        data={},
        model_meta={},
        config={
            "portfolio": {
                "asset_groups": {
                    "SPX500": "equity_indices",
                    "XAUUSD": "metals",
                    "EURUSD": "fx",
                }
            }
        },
    )
    context = {
        "asset_count": 3,
        "baseline_asset_count": 10,
        "group_count": 3,
        "baseline_group_count": 5,
        "maximum_group_asset_share": 1 / 3,
    }

    derived = compute_evolutionary_derived_metrics(result, context=context)

    assert derived["maximum_asset_pnl_share"] == pytest.approx(0.7)
    assert derived["maximum_group_pnl_share"] == pytest.approx(0.7)
    assert derived["cost_sensitivity"] == pytest.approx(0.03)
    assert derived["delay_sensitivity"] == pytest.approx(0.04)
    assert derived["delay_1_retention_ratio"] == pytest.approx(0.60)
    assert derived["walk_forward_median_sharpe"] == pytest.approx(0.40)
    assert derived["matb_complexity"] > 0.0
