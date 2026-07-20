from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.signals.matb_candidate_signal import matb_candidate_signal
from src.signals.matb_meta_filter_signal import matb_meta_filter_signal


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "matb_candidate": [1, 1, 0, 1],
            "matb_side": [1, -1, 0, 1],
            "matb_pred_success_prob": [0.60, 0.70, 0.99, 0.90],
            "matb_pred_ev_r": [0.20, 0.20, 9.0, 0.50],
            "matb_pred_is_oos": [1, 1, 1, 0],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="30min"),
    )


def test_matb_candidate_signal_is_stateless_and_mode_aware(frame: pd.DataFrame) -> None:
    both = matb_candidate_signal(frame)
    long_only = matb_candidate_signal(frame, mode="long_only")
    short_only = matb_candidate_signal(frame, mode="short_only")

    assert both.tolist() == [1.0, -1.0, 0.0, 1.0]
    assert long_only.tolist() == [1.0, 0.0, 0.0, 1.0]
    assert short_only.tolist() == [0.0, -1.0, 0.0, 0.0]
    assert both.name == "signal_side"


def test_matb_meta_filter_requires_candidate_probability_ev_and_oos(frame: pd.DataFrame) -> None:
    signal = matb_meta_filter_signal(frame)

    assert signal.tolist() == [1.0, -1.0, 0.0, 0.0]


def test_matb_meta_filter_never_uses_insample_prediction(frame: pd.DataFrame) -> None:
    frame = frame.copy()
    frame["matb_pred_is_oos"] = 0

    signal = matb_meta_filter_signal(frame)

    assert np.count_nonzero(signal.to_numpy()) == 0


def test_matb_meta_filter_validates_thresholds(frame: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="minimum_probability"):
        matb_meta_filter_signal(frame, minimum_probability=1.0)
