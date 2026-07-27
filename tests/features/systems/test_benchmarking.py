from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt

from src.features.systems.benchmarking import (
    TRADITIONAL_BENCHMARK_COLUMNS,
    add_traditional_indicator_benchmarks,
    evaluate_feature_benchmarks,
)


def test_traditional_benchmark_builder_is_causal_and_non_mutating(
    fallback_m1: pd.DataFrame,
) -> None:
    before = fallback_m1.copy(deep=True)
    prefix = add_traditional_indicator_benchmarks(fallback_m1.iloc[:320])
    full = add_traditional_indicator_benchmarks(fallback_m1)

    pdt.assert_frame_equal(fallback_m1, before)
    assert set(TRADITIONAL_BENCHMARK_COLUMNS).issubset(full.columns)
    pdt.assert_frame_equal(
        prefix[list(TRADITIONAL_BENCHMARK_COLUMNS)],
        full.iloc[:320][list(TRADITIONAL_BENCHMARK_COLUMNS)],
        check_exact=True,
    )


def test_walk_forward_benchmark_reports_requested_metrics(
    fallback_m1: pd.DataFrame,
) -> None:
    benchmark = add_traditional_indicator_benchmarks(fallback_m1)
    forward_return = np.log(benchmark["close"].shift(-5) / benchmark["close"])
    target = pd.Series(
        (np.sin(np.arange(len(benchmark), dtype=float) / 5.0) > 0.0).astype(float),
        index=benchmark.index,
    ).mask(forward_return.isna())
    metrics = evaluate_feature_benchmarks(
        benchmark,
        feature_cols=["benchmark_roc_14", "benchmark_ppo_hist_12_26_9"],
        target=target,
        forward_returns=forward_return,
        costs=0.00001,
        n_splits=3,
        min_train_size=180,
    )

    assert set(metrics.index) == {"benchmark_roc_14", "benchmark_ppo_hist_12_26_9"}
    expected = {
        "spearman_ic_mean",
        "mutual_information_mean",
        "log_loss",
        "brier_score",
        "auc",
        "selective_precision",
        "turnover",
        "net_expectancy",
    }
    assert expected.issubset(metrics.columns)
    assert metrics["walk_forward_folds"].gt(0).all()
    assert metrics["log_loss"].notna().all()
    assert metrics["brier_score"].between(0.0, 1.0).all()
