from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.features.volatility_of_volatility import add_volatility_of_volatility

from ._helpers import assert_no_mutation


def _vol_frame(values: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(values), freq="30min")
    return pd.DataFrame({"vol": values.astype(float)}, index=idx)


def test_volatility_of_volatility_contract_and_numeric_sanity() -> None:
    window = 5
    df = _vol_frame(np.full(40, 0.2, dtype=float))

    out = add_volatility_of_volatility(
        df,
        volatility_col="vol",
        window=window,
        output_col="vov",
    )

    assert "vov" in out.columns
    assert_no_mutation(
        add_volatility_of_volatility,
        df,
        volatility_col="vol",
        window=window,
        output_col="vov",
    )
    assert out["vov"].iloc[: window - 1].isna().all()
    assert out["vov"].dropna().abs().max() == pytest.approx(0.0)


def test_volatility_of_volatility_rejects_derived_outputs() -> None:
    with pytest.raises(ValueError, match="helper-derived"):
        add_volatility_of_volatility(
            _vol_frame(np.arange(20, dtype=float)),
            volatility_col="vol",
            window=3,
            mean_window=3,
            rising_col="vov_rising",
        )


def test_volatility_of_volatility_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_volatility_of_volatility(_vol_frame(np.arange(20, dtype=float)).drop(columns=["vol"]), "vol")


def test_volatility_of_volatility_invalid_window() -> None:
    with pytest.raises(ValueError, match="window"):
        add_volatility_of_volatility(_vol_frame(np.arange(20, dtype=float)), "vol", window=1)


def test_volatility_of_volatility_invalid_mean_window() -> None:
    with pytest.raises(ValueError, match="mean_window"):
        add_volatility_of_volatility(_vol_frame(np.arange(20, dtype=float)), "vol", window=3, mean_window=1)


def test_volatility_of_volatility_yaml_registry_supports_step() -> None:
    out = apply_feature_steps(
        _vol_frame(np.linspace(1.0, 3.0, 30)),
        [
            {
                "step": "volatility_of_volatility",
                "params": {
                    "volatility_col": "vol",
                    "window": 4,
                    "output_col": "vov",
                },
            }
        ],
    )

    assert "vov" in out.columns
