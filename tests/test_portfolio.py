from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import compute_ftmo_style_metrics
from src.portfolio import (
    PortfolioConstraints,
    apply_constraints,
    build_constrained_weights_from_exposures_over_time,
    build_optimized_weights_over_time,
    build_rolling_covariance_by_date,
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


def test_constrained_exposures_can_skip_net_exposure_projection_for_sparse_events() -> None:
    """
    Sparse event strategies must be able to keep inactive assets flat instead of creating
    offsetting hedge weights to satisfy a target net exposure.
    """
    idx = pd.date_range("2024-01-01", periods=3, freq="30min")
    exposures = pd.DataFrame(
        {
            "A": [0.20, -0.10, 0.0],
            "B": [0.00, 0.00, 0.0],
            "C": [0.00, 0.30, 0.0],
        },
        index=idx,
    )
    constraints = PortfolioConstraints(
        min_weight=-1.0,
        max_weight=1.0,
        max_gross_leverage=1.0,
        target_net_exposure=0.0,
        enforce_target_net_exposure=False,
    )

    weights, diagnostics = build_constrained_weights_from_exposures_over_time(
        exposures,
        constraints=constraints,
    )

    pd.testing.assert_series_equal(weights["B"], pd.Series(0.0, index=idx, name="B"))
    assert weights.loc[idx[0], "A"] == pytest.approx(0.20)
    assert weights.loc[idx[0], "C"] == pytest.approx(0.0)
    assert weights.loc[idx[1], "A"] == pytest.approx(-0.10)
    assert weights.loc[idx[1], "C"] == pytest.approx(0.30)
    assert weights.loc[idx[2]].abs().sum() == pytest.approx(0.0)
    assert diagnostics.loc[idx[0], "net_exposure"] == pytest.approx(0.20)


def test_constrained_exposures_default_still_enforces_target_net_exposure() -> None:
    idx = pd.date_range("2024-01-01", periods=1, freq="30min")
    exposures = pd.DataFrame({"A": [0.20], "B": [0.0], "C": [0.0]}, index=idx)
    constraints = PortfolioConstraints(
        min_weight=-1.0,
        max_weight=1.0,
        max_gross_leverage=1.0,
        target_net_exposure=0.0,
    )

    weights, _ = build_constrained_weights_from_exposures_over_time(
        exposures,
        constraints=constraints,
    )

    assert abs(float(weights.iloc[0].sum())) <= 1e-10
    assert float(weights.loc[idx[0], ["B", "C"]].abs().sum()) > 0.0


def test_compute_portfolio_performance_respects_min_holding_bars_via_held_weights() -> None:
    """
    Portfolio weights can be held causally before performance so churn is reduced consistently.
    """
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    weights = pd.DataFrame(
        {
            "A": [1.0, -1.0, -1.0, 0.0],
            "B": [-1.0, 1.0, 1.0, 0.0],
        },
        index=idx,
    )
    asset_returns = pd.DataFrame(
        {
            "A": [0.0, 0.01, -0.01, 0.0],
            "B": [0.0, -0.01, 0.01, 0.0],
        },
        index=idx,
    )

    from src.backtesting.holding import apply_min_holding_bars_to_weights

    held = apply_min_holding_bars_to_weights(weights, min_holding_bars=2)
    perf = compute_portfolio_performance(
        held,
        asset_returns,
        cost_per_turnover=0.0,
        slippage_per_turnover=0.0,
        periods_per_year=252,
    )

    assert held.iloc[0].tolist() == [1.0, -1.0]
    assert held.iloc[1].tolist() == [1.0, -1.0]
    assert perf.turnover.tolist() == [2.0, 0.0, 4.0, 0.0]


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


def test_optimize_mean_variance_zeroes_assets_without_valid_covariance() -> None:
    """
    Assets with incomplete covariance estimates should stay flat instead of looking risk-free.
    """
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    returns = pd.DataFrame(
        {
            "AAA": [0.01, 0.02, -0.01, 0.015, 0.01],
            "BBB": [np.nan, np.nan, np.nan, 0.03, np.nan],
        },
        index=idx,
    )
    cov_by_date = build_rolling_covariance_by_date(returns, window=5, min_periods=2)
    cov = cov_by_date[idx[-1]]
    mu = pd.Series({"AAA": 0.01, "BBB": 0.25}, dtype=float)
    constraints = PortfolioConstraints(
        min_weight=0.0,
        max_weight=1.0,
        max_gross_leverage=1.0,
        target_net_exposure=1.0,
    )

    weights, meta = optimize_mean_variance(
        mu,
        covariance=cov,
        constraints=constraints,
        risk_aversion=1.0,
    )

    assert np.isclose(weights["AAA"], 1.0)
    assert np.isclose(weights["BBB"], 0.0)
    assert "BBB" in meta["unsupported_covariance_assets"]


def test_optimize_mean_variance_raises_on_pairwise_missing_covariance() -> None:
    """
    Pairwise-missing covariances should fail loudly instead of being treated as zero correlation.
    """
    mu = pd.Series({"A": 0.10, "B": 0.08}, dtype=float)
    cov = pd.DataFrame(
        [[0.04, np.nan], [np.nan, 0.05]],
        index=mu.index,
        columns=mu.index,
        dtype=float,
    )

    with np.testing.assert_raises(ValueError):
        optimize_mean_variance(mu, covariance=cov)


def test_build_optimized_weights_over_time_stays_flat_until_covariance_ready() -> None:
    """
    Mean-variance weights should remain flat before the first valid covariance snapshot exists.
    """
    idx = pd.date_range("2024-01-01", periods=6, freq="D")
    expected_returns = pd.DataFrame(
        {
            "A": [0.05, 0.05, 0.05, 0.05, 0.05, 0.05],
            "B": [0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
        },
        index=idx,
    )
    asset_returns = pd.DataFrame(
        {
            "A": [0.01, 0.02, -0.01, 0.01, 0.0, 0.01],
            "B": [0.0, -0.01, 0.01, 0.0, 0.02, -0.01],
        },
        index=idx,
    )
    cov_by_date = build_rolling_covariance_by_date(
        asset_returns,
        window=3,
        min_periods=3,
        rebalance_step=2,
    )

    weights, diagnostics = build_optimized_weights_over_time(
        expected_returns,
        covariance_by_date=cov_by_date,
        constraints=PortfolioConstraints(
            min_weight=0.0,
            max_weight=1.0,
            max_gross_leverage=1.0,
            target_net_exposure=1.0,
        ),
        risk_aversion=1.0,
    )

    first_cov_ts = min(cov_by_date)
    pre_cov = weights.loc[weights.index < first_cov_ts]
    assert not pre_cov.empty
    assert np.isclose(pre_cov.to_numpy(dtype=float), 0.0).all()
    assert diagnostics.loc[diagnostics.index < first_cov_ts, "turnover"].eq(0.0).all()


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


def test_compute_portfolio_performance_portfolio_guard_flattens_future_weights_after_daily_loss() -> None:
    idx = pd.date_range("2024-01-01 00:00:00", periods=6, freq="h", tz="UTC")
    weights = pd.DataFrame({"A": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]}, index=idx)
    returns = pd.DataFrame({"A": [0.0, -0.03, 0.01, 0.01, 0.0, 0.0]}, index=idx)

    perf = compute_portfolio_performance(
        weights,
        returns,
        cost_per_turnover=0.0,
        slippage_per_turnover=0.0,
        portfolio_guard={
            "enabled": True,
            "max_daily_loss": 0.02,
            "cooloff_bars": 2,
            "rearm_on_new_period": True,
            "weekly_anchor": "W-FRI",
        },
    )

    assert perf.applied_weights is not None
    assert perf.applied_weights.iloc[2:4, 0].eq(0.0).all()
    assert perf.risk_guard_summary["daily_loss_trigger_count"] == 1
    assert perf.risk_guard_summary["flattened_bar_count"] == 2
    assert perf.risk_guard_timeline is not None
    assert bool(perf.risk_guard_timeline["risk_guard_triggered"].iloc[1]) is True


def test_compute_portfolio_performance_supports_soft_stop_hard_stop_and_weekly_lock() -> None:
    idx = pd.date_range("2024-01-01 00:00:00", periods=6, freq="h", tz="UTC")
    weights = pd.DataFrame({"A": [1.0] * 6}, index=idx)

    soft_perf = compute_portfolio_performance(
        weights,
        pd.DataFrame({"A": [0.0, -0.011, 0.0, 0.0, 0.0, 0.0]}, index=idx),
        portfolio_guard={
            "enabled": True,
            "daily_soft_stop": 0.01,
            "daily_soft_stop_risk_multiplier": 0.5,
            "weekly_anchor": "W-FRI",
        },
    )
    assert soft_perf.applied_weights is not None
    assert soft_perf.applied_weights.iloc[2, 0] == pytest.approx(0.5)
    assert soft_perf.risk_guard_summary["soft_stop_trigger_count"] == 1

    hard_perf = compute_portfolio_performance(
        weights,
        pd.DataFrame({"A": [0.0, -0.03, 0.0, 0.0, 0.0, 0.0]}, index=idx),
        portfolio_guard={
            "enabled": True,
            "daily_hard_stop": 0.025,
            "weekly_anchor": "W-FRI",
        },
    )
    assert hard_perf.applied_weights is not None
    assert hard_perf.applied_weights.iloc[2:, 0].eq(0.0).all()
    assert hard_perf.risk_guard_summary["hard_stop_trigger_count"] == 1

    lock_perf = compute_portfolio_performance(
        weights,
        pd.DataFrame({"A": [0.0, 0.02, 0.0, 0.0, 0.0, 0.0]}, index=idx),
        portfolio_guard={
            "enabled": True,
            "weekly_profit_lock": 0.015,
            "after_target_mode": "flatten",
            "weekly_anchor": "W-FRI",
        },
    )
    assert lock_perf.applied_weights is not None
    assert lock_perf.applied_weights.iloc[2:, 0].eq(0.0).all()
    assert lock_perf.risk_guard_summary["weekly_lock_trigger_count"] == 1


def test_compute_ftmo_style_metrics_counts_weekly_and_daily_breaches() -> None:
    idx = pd.date_range("2024-01-01 00:00:00", periods=8, freq="12h", tz="UTC")
    returns = pd.Series([0.0, -0.03, 0.01, 0.02, 0.0, -0.05, 0.02, 0.01], index=idx, dtype=float)

    metrics = compute_ftmo_style_metrics(
        net_returns=returns,
        weekly_return_target=0.015,
        max_daily_loss=0.02,
        weekly_drawdown_limit=0.04,
        max_total_loss=0.05,
        weekly_anchor="W-FRI",
    )

    assert metrics["week_count"] == pytest.approx(1.0)
    assert metrics["daily_loss_breach_count"] == pytest.approx(2.0)
    assert metrics["weekly_drawdown_breach_count"] == pytest.approx(1.0)
    assert metrics["max_total_loss_breach_count"] == pytest.approx(1.0)
    assert metrics["weekly_target_hit_ratio"] == pytest.approx(0.0)


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
