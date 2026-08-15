from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.ethusd_meta_label import chronological_meta_label_evaluation


def test_meta_label_evaluation_is_expanding_and_fold_local() -> None:
    index = pd.date_range("2024-01-01", periods=100, freq="12h")
    target = np.tile([0, 1], 50)
    samples = pd.DataFrame(
        {
            "feature_a": target + np.linspace(-0.2, 0.2, 100),
            "feature_b": np.sin(np.arange(100) / 5.0),
            "meta_label": target,
        },
        index=index,
    )

    result = chronological_meta_label_evaluation(
        samples,
        feature_columns=["feature_a", "feature_b"],
        min_samples=60,
        min_class_samples=20,
        n_splits=3,
    )

    assert result.status == "evaluated"
    assert len(result.predictions) == 60
    assert result.predictions.index.min() > samples.index[:40].max()
    assert result.metrics["accuracy"] > 0.9
    assert len(result.fold_metadata) == 3
    for fold in result.fold_metadata:
        assert pd.Timestamp(fold["train_end"]) < pd.Timestamp(fold["test_start"])


def test_meta_label_evaluation_fails_closed_on_small_sample() -> None:
    samples = pd.DataFrame(
        {
            "feature": np.arange(20, dtype=float),
            "meta_label": np.tile([0, 1], 10),
        },
        index=pd.date_range("2024-01-01", periods=20, freq="D"),
    )

    result = chronological_meta_label_evaluation(
        samples,
        feature_columns=["feature"],
        min_samples=60,
        min_class_samples=20,
    )

    assert result.status == "insufficient_samples"
    assert result.predictions.empty
    assert result.metrics["rows"] == 20
