from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from src.portfolio import (
    PortfolioConstraints,
    apply_constraints,
    build_weights_from_signals_over_time,
    compute_portfolio_performance,
    optimize_mean_variance,
    signal_to_raw_weights,
)


def test_apply_constraints_respects_bounds_group_gross_and_turnover() -> None:
    """
    Verify that constraints respects bounds group gross and turnover behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    weights = pd.Series({"A": 0.9, "B": -0.8, "C": 0.6}, dtype=float)
    prev = pd.Series({"A": 0.0, "B": 0.0, "C": 0.0}, dtype=float)
    constraints = PortfolioConstraints(
        min_weight=-0.7,
        max_weight=0.7,
        max_gross_leverage=1.0,
        target_net_exposure=0.0,
        turnover_limit=0.5,
        group_max_exposure={"tech": 0.35},
    )
    asset_to_group = {"A": "tech", "B": "tech", "C": "rates"}

    out, diag = apply_constraints(
        weights,
        constraints=constraints,
        prev_weights=prev,
        asset_to_group=asset_to_group,
    )

    assert out.min() >= -0.7 - 1e-12
    assert out.max() <= 0.7 + 1e-12
    assert float(np.abs(out).sum()) <= 1.0 + 1e-12
    assert float(np.abs(out - prev).sum()) <= 0.5 + 1e-12
    assert float(np.abs(out.loc[["A", "B"]]).sum()) <= 0.35 + 1e-12
    assert abs(float(diag["net_exposure"])) <= 1e-6


def test_build_weights_from_signals_over_time_respects_constraints() -> None:
    """
    Verify that weights from signals over time respects constraints behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    signals = pd.DataFrame(
        {
            "A": [1.0, 1.0, -1.0, 0.5],
            "B": [-1.0, 0.5, 1.0, -0.5],
            "C": [0.2, -2.0, 0.3, 0.0],
        },
        index=idx,
    )
    constraints = PortfolioConstraints(
        min_weight=-0.6,
        max_weight=0.6,
        max_gross_leverage=1.0,
        target_net_exposure=0.0,
        turnover_limit=0.4,
    )

    weights, diagnostics = build_weights_from_signals_over_time(
        signals,
        constraints=constraints,
        long_short=True,
        gross_target=1.0,
    )

    assert weights.shape == signals.shape
    assert diagnostics.shape[0] == signals.shape[0]
    assert (weights.abs().sum(axis=1) <= 1.0 + 1e-10).all()
    assert diagnostics["turnover"].iloc[1:].max() <= 0.4 + 1e-10
    assert (weights.sum(axis=1).abs() <= 1e-6).all()


def test_signal_to_raw_weights_keeps_missing_assets_flat() -> None:
    """
    Verify that signal to raw weights keeps missing assets flat behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    signal_t = pd.Series({"A": 1.0, "B": -1.0, "C": np.nan}, dtype=float)
    weights = signal_to_raw_weights(signal_t, long_short=True, gross_target=1.0)

    assert np.isclose(weights["C"], 0.0)
    assert np.isclose(float(weights.abs().sum()), 1.0)
    assert np.isclose(float(weights.sum()), 0.0)


def test_optimize_mean_variance_respects_core_constraints() -> None:
    """
    Verify that optimize mean variance respects core constraints behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    mu = pd.Series({"A": 0.04, "B": 0.02, "C": -0.01, "D": -0.03}, dtype=float)
    cov = pd.DataFrame(np.eye(4), index=mu.index, columns=mu.index)
    constraints = PortfolioConstraints(
        min_weight=-0.5,
        max_weight=0.5,
        max_gross_leverage=1.0,
        target_net_exposure=0.0,
        group_max_exposure={"equity": 0.6},
    )
    asset_to_group = {"A": "equity", "B": "equity", "C": "rates", "D": "rates"}

    weights, meta = optimize_mean_variance(
        mu,
        covariance=cov,
        constraints=constraints,
        asset_to_group=asset_to_group,
        risk_aversion=3.0,
    )

    assert isinstance(meta["solver_success"], bool)
    assert float(np.abs(weights).sum()) <= 1.0 + 1e-8
    assert abs(float(weights.sum())) <= 1e-6
    assert float(np.abs(weights.loc[["A", "B"]]).sum()) <= 0.6 + 1e-8
    assert weights["A"] >= weights["D"]


def test_apply_constraints_turnover_limit_raises_when_constraint_set_is_infeasible() -> None:
    """
    Verify that constraints turnover limit raises when constraint set is infeasible behaves as
    expected under a representative regression scenario. The test protects the intended
    contract of the surrounding component and makes failures easier to localize.
    """
    target = pd.Series({"A": 1.0, "B": -1.0}, dtype=float)
    prev = pd.Series({"A": 0.5, "B": 0.0}, dtype=float)
    constraints = PortfolioConstraints(
        min_weight=-1.0,
        max_weight=1.0,
        max_gross_leverage=2.0,
        target_net_exposure=0.0,
        turnover_limit=0.2,
    )

    with np.testing.assert_raises(ValueError):
        apply_constraints(target, constraints=constraints, prev_weights=prev)


def test_compute_portfolio_performance_uses_shifted_weights() -> None:
    """
    Verify that portfolio performance uses shifted weights behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    weights = pd.DataFrame(
        {
            "A": [1.0, 0.0, 0.0],
            "B": [0.0, 1.0, 1.0],
        },
        index=idx,
    )
    returns = pd.DataFrame(
        {
            "A": [0.10, 0.00, 0.00],
            "B": [0.00, 0.20, 0.10],
        },
        index=idx,
    )

    perf = compute_portfolio_performance(
        weights,
        returns,
        cost_per_turnover=0.01,
        slippage_per_turnover=0.0,
    )

    # No-lookahead: return at t uses weights from t-1.
    assert np.isclose(perf.gross_returns.iloc[0], 0.0)
    assert np.isclose(perf.gross_returns.iloc[1], 0.0)
    assert np.isclose(perf.gross_returns.iloc[2], 0.10)

    # Day 2 had rebalance turnover 2.0, so cost is 0.02.
    assert np.isclose(perf.turnover.iloc[1], 2.0)
    assert np.isclose(perf.costs.iloc[1], 0.02)
    assert np.isclose(perf.net_returns.iloc[1], -0.02)


def test_compute_portfolio_performance_raises_on_missing_exposed_return() -> None:
    """
    Verify that portfolio performance raises on missing exposed return behaves as expected under
    a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    weights = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=idx)
    returns = pd.DataFrame({"A": [0.0, np.nan, 0.0]}, index=idx)

    with np.testing.assert_raises(ValueError):
        compute_portfolio_performance(weights, returns)


def test_compute_portfolio_performance_charges_initial_turnover() -> None:
    """
    Verify that portfolio performance charges initial turnover behaves as expected under a
    representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    weights = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=idx)
    returns = pd.DataFrame({"A": [0.0, 0.0, 0.0]}, index=idx)

    perf = compute_portfolio_performance(
        weights,
        returns,
        cost_per_turnover=0.01,
        slippage_per_turnover=0.0,
    )

    assert np.isclose(perf.turnover.iloc[0], 1.0)
    assert np.isclose(perf.costs.iloc[0], 0.01)
    assert np.isclose(perf.net_returns.iloc[0], -0.01)


def test_optimize_mean_variance_fallback_respects_max_gross_leverage() -> None:
    """
    Verify that optimize mean variance fallback respects max gross leverage behaves as expected
    under a representative regression scenario. The test protects the intended contract of the
    surrounding component and makes failures easier to localize.
    """
    mu = pd.Series({"A": 0.10, "B": -0.10, "C": 0.05}, dtype=float)
    cov = pd.DataFrame(np.full((3, 3), np.inf), index=mu.index, columns=mu.index)
    constraints = PortfolioConstraints(
        min_weight=-3.0,
        max_weight=3.0,
        max_gross_leverage=2.0,
        target_net_exposure=0.0,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        weights, meta = optimize_mean_variance(
            mu,
            covariance=cov,
            constraints=constraints,
            allow_fallback=True,
        )

    assert bool(meta["used_fallback"]) is True
    assert float(np.abs(weights).sum()) > 1.0
    assert float(np.abs(weights).sum()) <= 2.0 + 1e-8
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
