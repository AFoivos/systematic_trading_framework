from __future__ import annotations

import pandas as pd
import pytest

from src.experiments.registry import SIGNAL_REGISTRY
from src.signals.orb_candidate_side_signal import orb_candidate_side_signal
from src.utils.config_validation import validate_signals_block


def test_orb_candidate_side_signal_gates_side_by_candidate() -> None:
    df = pd.DataFrame(
        {
            "orb_candidate": [0.0, 1.0, 2.0, None, -1.0],
            "orb_side": [1.0, 1.0, -1.0, -1.0, 0.5],
        }
    )

    signal = orb_candidate_side_signal(df)

    assert signal.name == "signal_orb_side"
    assert signal.tolist() == [0.0, 1.0, -1.0, 0.0, 0.5]


def test_orb_candidate_side_signal_is_registered_and_config_validates() -> None:
    assert SIGNAL_REGISTRY["orb_candidate_side"] is orb_candidate_side_signal

    validate_signals_block(
        {
            "kind": "orb_candidate_side",
            "params": {
                "candidate_col": "orb_candidate",
                "side_col": "orb_side",
                "signal_col": "signal_orb_side",
            },
        }
    )


def test_orb_candidate_side_signal_requires_columns() -> None:
    with pytest.raises(KeyError, match="candidate_col"):
        orb_candidate_side_signal(pd.DataFrame({"orb_side": [1.0]}))

    with pytest.raises(KeyError, match="side_col"):
        orb_candidate_side_signal(pd.DataFrame({"orb_candidate": [1.0]}))
