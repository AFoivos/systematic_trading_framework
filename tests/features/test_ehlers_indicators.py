from __future__ import annotations

from collections.abc import Callable

import pytest

from src.features.autocorrelation_periodogram import add_autocorrelation_periodogram
from src.features.center_of_gravity import add_center_of_gravity
from src.features.cyber_cycle import add_cyber_cycle
from src.features.decycler import add_decycler
from src.features.decycler_oscillator import add_decycler_oscillator
from src.features.dominant_cycle_period import add_dominant_cycle_period
from src.features.dominant_cycle_phase import add_dominant_cycle_phase
from src.features.even_better_sinewave import add_even_better_sinewave
from src.features.fama import add_fama
from src.features.fisher_transform import add_fisher_transform
from src.features.frama import add_frama
from src.features.homodyne_discriminator import add_homodyne_discriminator
from src.features.instantaneous_trendline import add_instantaneous_trendline
from src.features.inverse_fisher_transform import add_inverse_fisher_transform
from src.features.laguerre_rsi import add_laguerre_rsi
from src.features.mama import add_mama
from src.features.sinewave_indicator import add_sinewave_indicator

from ._helpers import assert_causal, assert_has_finite_values, assert_no_mutation, synthetic_ohlcv


FeatureFn = Callable[..., object]


FEATURE_CASES = [
    (
        "mama",
        add_mama,
        {"output_col": "custom_mama"},
        ["mama"],
        ["custom_mama"],
        ["close"],
        {"slow_limit": 0.7, "fast_limit": 0.2},
    ),
    (
        "fama",
        add_fama,
        {"output_col": "custom_fama"},
        ["fama"],
        ["custom_fama"],
        ["close"],
        {"slow_limit": 0.7, "fast_limit": 0.2},
    ),
    (
        "dominant_cycle_period",
        add_dominant_cycle_period,
        {"output_col": "custom_period"},
        ["dominant_cycle_period"],
        ["custom_period"],
        ["close"],
        {"output_col": ""},
    ),
    (
        "dominant_cycle_phase",
        add_dominant_cycle_phase,
        {"output_col": "custom_phase"},
        ["dominant_cycle_phase"],
        ["custom_phase"],
        ["close"],
        {"output_col": ""},
    ),
    (
        "instantaneous_trendline",
        add_instantaneous_trendline,
        {"output_col": "custom_itrend", "trigger_col": "custom_itrend_trigger"},
        ["instantaneous_trendline", "instantaneous_trendline_trigger"],
        ["custom_itrend", "custom_itrend_trigger"],
        ["close"],
        {"alpha": 1.5},
    ),
    (
        "fisher_transform",
        add_fisher_transform,
        {"window": 8, "output_col": "custom_fisher", "signal_col": "custom_fisher_signal"},
        ["fisher_transform_10", "fisher_transform_10_signal"],
        ["custom_fisher", "custom_fisher_signal"],
        ["close"],
        {"window": 1},
    ),
    (
        "inverse_fisher_transform",
        add_inverse_fisher_transform,
        {"window": 8, "output_col": "custom_inverse_fisher"},
        ["inverse_fisher_transform_10"],
        ["custom_inverse_fisher"],
        ["close"],
        {"scale": -1.0},
    ),
    (
        "sinewave_indicator",
        add_sinewave_indicator,
        {"output_col": "custom_sine", "lead_output_col": "custom_lead_sine"},
        ["sinewave", "lead_sinewave"],
        ["custom_sine", "custom_lead_sine"],
        ["close"],
        {"lead_degrees": float("nan")},
    ),
    (
        "cyber_cycle",
        add_cyber_cycle,
        {"output_col": "custom_cyber", "trigger_col": "custom_cyber_trigger"},
        ["cyber_cycle", "cyber_cycle_trigger"],
        ["custom_cyber", "custom_cyber_trigger"],
        ["close"],
        {"alpha": 1.5},
    ),
    (
        "decycler",
        add_decycler,
        {"period": 40, "output_col": "custom_decycler"},
        ["decycler_60"],
        ["custom_decycler"],
        ["close"],
        {"period": 2},
    ),
    (
        "decycler_oscillator",
        add_decycler_oscillator,
        {"fast_period": 20, "slow_period": 50, "output_col": "custom_decycler_osc"},
        ["decycler_oscillator_30_60"],
        ["custom_decycler_osc"],
        ["close"],
        {"fast_period": 60, "slow_period": 30},
    ),
    (
        "laguerre_rsi",
        add_laguerre_rsi,
        {"output_col": "custom_laguerre"},
        ["laguerre_rsi"],
        ["custom_laguerre"],
        ["close"],
        {"gamma": 1.5},
    ),
    (
        "frama",
        add_frama,
        {"window": 16, "output_col": "custom_frama"},
        ["frama_16"],
        ["custom_frama"],
        ["high"],
        {"window": 15},
    ),
    (
        "center_of_gravity",
        add_center_of_gravity,
        {"window": 8, "output_col": "custom_cog"},
        ["center_of_gravity_10"],
        ["custom_cog"],
        ["close"],
        {"window": 1},
    ),
    (
        "even_better_sinewave",
        add_even_better_sinewave,
        {"output_col": "custom_ebs"},
        ["even_better_sinewave"],
        ["custom_ebs"],
        ["close"],
        {"duration": 3},
    ),
    (
        "autocorrelation_periodogram",
        add_autocorrelation_periodogram,
        {"window": 96, "output_col": "custom_acp"},
        ["autocorrelation_periodogram_10_48"],
        ["custom_acp"],
        ["close"],
        {"window": 20, "max_period": 20},
    ),
    (
        "homodyne_discriminator",
        add_homodyne_discriminator,
        {"output_col": "custom_homodyne"},
        ["homodyne_discriminator"],
        ["custom_homodyne"],
        ["close"],
        {"use_smoothed_period": "yes"},
    ),
]


@pytest.mark.parametrize(
    ("name", "fn", "custom_params", "default_outputs", "custom_outputs", "missing_cols", "invalid_params"),
    FEATURE_CASES,
)
def test_ehlers_indicator_contract_and_numeric_sanity(
    name: str,
    fn: FeatureFn,
    custom_params: dict[str, object],
    default_outputs: list[str],
    custom_outputs: list[str],
    missing_cols: list[str],
    invalid_params: dict[str, object],
) -> None:
    df = synthetic_ohlcv(n=220)
    out = fn(df, **custom_params)

    assert set(custom_outputs).issubset(out.columns), name
    assert_no_mutation(fn, df, **custom_params)
    assert_has_finite_values(out[custom_outputs[0]])


@pytest.mark.parametrize(
    ("name", "fn", "custom_params", "default_outputs", "custom_outputs", "missing_cols", "invalid_params"),
    FEATURE_CASES,
)
def test_ehlers_indicator_missing_columns(
    name: str,
    fn: FeatureFn,
    custom_params: dict[str, object],
    default_outputs: list[str],
    custom_outputs: list[str],
    missing_cols: list[str],
    invalid_params: dict[str, object],
) -> None:
    with pytest.raises(KeyError, match="Missing columns"):
        fn(synthetic_ohlcv().drop(columns=missing_cols), **custom_params)


@pytest.mark.parametrize(
    ("name", "fn", "custom_params", "default_outputs", "custom_outputs", "missing_cols", "invalid_params"),
    FEATURE_CASES,
)
def test_ehlers_indicator_invalid_params(
    name: str,
    fn: FeatureFn,
    custom_params: dict[str, object],
    default_outputs: list[str],
    custom_outputs: list[str],
    missing_cols: list[str],
    invalid_params: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        fn(synthetic_ohlcv(), **invalid_params)


@pytest.mark.parametrize(
    ("name", "fn", "custom_params", "default_outputs", "custom_outputs", "missing_cols", "invalid_params"),
    FEATURE_CASES,
)
def test_ehlers_indicator_is_causal(
    name: str,
    fn: FeatureFn,
    custom_params: dict[str, object],
    default_outputs: list[str],
    custom_outputs: list[str],
    missing_cols: list[str],
    invalid_params: dict[str, object],
) -> None:
    assert_causal(
        fn,
        synthetic_ohlcv(n=220),
        output_cols=default_outputs,
        params={},
        cutoff=120,
    )


def test_laguerre_rsi_bounds_and_percent_mode() -> None:
    out = add_laguerre_rsi(synthetic_ohlcv(), as_percent=True, output_col="laguerre_percent")
    values = out["laguerre_percent"].dropna()
    assert values.between(0.0, 100.0).all()


def test_frama_optional_diagnostics() -> None:
    out = add_frama(synthetic_ohlcv(n=220), add_diagnostics=True)
    assert {"frama_16", "frama_16_alpha", "frama_16_fractal_dimension"}.issubset(out.columns)
    assert_has_finite_values(out["frama_16_alpha"])
