from __future__ import annotations

import pandas as pd
import pytest

from src.features.technical.adx import compute_adx
from src.features.technical.atr import compute_atr
from src.features.technical.rsi import compute_rsi


def test_atr_wilder_uses_initial_sma_seed_and_withholds_warmup() -> None:
    high = pd.Series([1.0, 2.0, 4.0])
    low = pd.Series([0.0, 0.0, 0.0])
    close = pd.Series([0.5, 1.0, 2.0])

    atr = compute_atr(high, low, close, window=3, method="wilder")

    assert atr.iloc[:2].isna().all()
    assert atr.iloc[2] == pytest.approx((1.0 + 2.0 + 4.0) / 3.0)


def test_rsi_wilder_uses_classic_seed_then_recursive_update() -> None:
    prices = pd.Series([1.0, 2.0, 3.0, 2.0, 4.0], name="close")

    rsi = compute_rsi(prices, window=3, method="wilder")

    assert rsi.iloc[:3].isna().all()
    assert rsi.iloc[3] == pytest.approx(100.0 * (2.0 / 3.0))
    assert rsi.iloc[4] == pytest.approx(100.0 * 5.0 / 6.0)


def test_adx_wilder_has_two_stage_warmup_and_classic_seed() -> None:
    high = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    low = pd.Series([0.0, 1.0, 2.0, 3.0, 4.0])
    close = pd.Series([0.5, 1.5, 2.5, 3.5, 4.5])

    result = compute_adx(high, low, close, window=3)

    assert result["plus_di_3"].iloc[:2].isna().all()
    assert result["adx_3"].iloc[:4].isna().all()
    assert result["adx_3"].iloc[4] == pytest.approx(100.0)
