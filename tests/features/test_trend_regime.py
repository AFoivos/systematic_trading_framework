from __future__ import annotations

import pytest

from src.experiments.orchestration.feature_stage import apply_feature_steps
from src.features.trend_regime import add_trend_regime

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


def test_trend_regime_contract_and_numeric_sanity() -> None:
    df = synthetic_ohlcv()
    out = add_trend_regime(df, fast_span=5, slow_span=15, output_col="ema_trend_regime")

    assert "ema_trend_regime" in out.columns
    assert_no_mutation(add_trend_regime, df, fast_span=5, slow_span=15, output_col="ema_trend_regime")
    assert_has_finite_values(out["ema_trend_regime"])
    assert set(out["ema_trend_regime"].dropna().unique()).issubset({-1.0, 0.0, 1.0})


def test_trend_regime_missing_columns() -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        add_trend_regime(synthetic_ohlcv().drop(columns=["close"]), fast_span=5, slow_span=15)


def test_trend_regime_invalid_params() -> None:
    with pytest.raises(ValueError, match="fast_span"):
        add_trend_regime(synthetic_ohlcv(), fast_span=20, slow_span=10)


def test_trend_regime_is_causal() -> None:
    assert_causal(
        add_trend_regime,
        synthetic_ohlcv(),
        output_cols=["trend_regime"],
        params={"fast_span": 5, "slow_span": 15},
    )


def test_trend_regime_yaml_registry_supports_ema_mode() -> None:
    out = apply_feature_steps(
        synthetic_ohlcv(),
        [{"step": "trend_regime", "params": {"method": "ema", "fast_span": 5, "slow_span": 15}}],
    )

    assert "trend_regime" in out.columns
