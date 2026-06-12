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
    mean_window = 4
    df = _vol_frame(np.full(40, 0.2, dtype=float))

    out = add_volatility_of_volatility(
        df,
        volatility_col="vol",
        window=window,
        mean_window=mean_window,
        output_col="vov",
        mean_col="vov_mean",
        ratio_col="vov_ratio",
        rising_col="vov_rising",
        high_vov_col="vov_high",
    )

    assert {"vov", "vov_mean", "vov_ratio", "vov_rising", "vov_high"}.issubset(out.columns)
    assert_no_mutation(
        add_volatility_of_volatility,
        df,
        volatility_col="vol",
        window=window,
        mean_window=mean_window,
        output_col="vov",
        mean_col="vov_mean",
        ratio_col="vov_ratio",
        rising_col="vov_rising",
        high_vov_col="vov_high",
    )
    assert out["vov_rising"].dtype == np.dtype("int8")
    assert out["vov_high"].dtype == np.dtype("int8")
    assert out["vov"].iloc[: window - 1].isna().all()
    assert out["vov_mean"].iloc[: window + mean_window - 2].isna().all()
    assert out["vov"].dropna().abs().max() == pytest.approx(0.0)
    assert out["vov_high"].eq(0).all()


def test_volatility_of_volatility_rising_and_high_flags() -> None:
    values = np.array([1, 1, 1, 1, 2, 4, 8, 16, 32, 64, 128, 256], dtype=float)
    out = add_volatility_of_volatility(
        _vol_frame(values),
        volatility_col="vol",
        window=3,
        mean_window=3,
        output_col="vov",
        high_vov_mult=1.0,
    )

    assert out["volatility_of_volatility_vol_3_rising"].sum() > 0
    assert out["volatility_of_volatility_vol_3_high"].sum() > 0


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
                    "mean_window": 5,
                    "output_col": "vov",
                },
            }
        ],
    )

    assert "vov" in out.columns
