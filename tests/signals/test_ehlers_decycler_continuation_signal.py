from __future__ import annotations

import pandas as pd
import pytest

from src.experiments.registry import FEATURE_KINDS, SIGNAL_REGISTRY
from src.signals.ehlers_decycler_continuation_signal import build_ehlers_decycler_continuation_signal


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "decycler_oscillator_30_60": [0.10, 0.25, 0.30, 0.20],
            "ehlers_decycler_over_close": [0.997, 0.995, 0.994, 0.994],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="30min", tz="UTC"),
    )


def test_decycler_continuation_state_signal_is_causal_and_registered() -> None:
    out, meta = build_ehlers_decycler_continuation_signal(
        _frame(),
        decycler_osc_min=0.239,
        decycler_ratio_max=0.996,
    )

    assert meta["kind"] == "ehlers_decycler_continuation"
    assert out["signal_side"].tolist() == [0, 1, 1, 0]
    assert out["signal_candidate"].equals(out["signal_side"])
    assert "ehlers_decycler_continuation" in SIGNAL_REGISTRY
    assert "ehlers_decycler_continuation" in FEATURE_KINDS


def test_decycler_continuation_transition_mode_emits_only_entries() -> None:
    out, _ = build_ehlers_decycler_continuation_signal(
        _frame(),
        decycler_osc_min=0.239,
        decycler_ratio_max=0.996,
        entry_mode="transition",
    )

    assert out["signal_side"].tolist() == [0, 1, 0, 0]


def test_decycler_continuation_validates_required_columns() -> None:
    with pytest.raises(KeyError, match="decycler_oscillator"):
        build_ehlers_decycler_continuation_signal(_frame().drop(columns="decycler_oscillator_30_60"))
