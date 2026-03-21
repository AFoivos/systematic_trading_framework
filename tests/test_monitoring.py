from __future__ import annotations

import numpy as np
import pandas as pd

from src.monitoring.drift import compute_feature_drift, population_stability_index


def test_population_stability_index_detects_shift_from_constant_reference() -> None:
    """
    Constant-reference features should still emit a strong drift signal when current data shifts.
    """
    ref = pd.Series([0.0, 0.0, 0.0, 0.0], dtype=float)
    cur = pd.Series([1.0, 1.0, 1.0, 1.0], dtype=float)

    out = population_stability_index(ref, cur)

    assert np.isinf(out)


def test_compute_feature_drift_flags_constant_reference_shift() -> None:
    """
    Feature drift report should flag constant-to-shifted feature changes as drifted.
    """
    report = compute_feature_drift(
        pd.DataFrame({"f": [0.0, 0.0, 0.0, 0.0]}),
        pd.DataFrame({"f": [1.0, 1.0, 1.0, 1.0]}),
        feature_cols=["f"],
        psi_threshold=0.2,
    )

    assert report["drifted_feature_count"] == 1
    assert bool(report["per_feature"]["f"]["is_drifted"]) is True
    assert np.isinf(float(report["per_feature"]["f"]["psi"]))
