from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Union

import pandas as pd

from src.utils.registry import build_registry, get_registered_component, registry_names

from .c1_trend_pullback_vwap import c1_trend_pullback_vwap_signal
from .c2_regime_aware_momentum import c2_regime_aware_momentum_signal
from .conviction_sizing_signal import conviction_sizing_signal
from .dense_return_forecast_signal import dense_return_forecast_signal
from .ehlers_continuation_long_signal import ehlers_continuation_long_signal
from .ehlers_continuation_short_signal import ehlers_continuation_short_signal
from .ehlers_decycler_continuation_signal import ehlers_decycler_continuation_signal
from .ehlers_semiscalp_long_signal import ehlers_semiscalp_long_signal
from .ehlers_trend_pullback_continuation_long_signal import ehlers_trend_pullback_continuation_long_signal
from .ema_rms_ppo_vwap_signal import ema_rms_ppo_vwap_signal
from .ema_stoch_rsi_pullback_signal import ema_stoch_rsi_pullback_signal
from .forecast_threshold_signal import forecast_threshold_signal
from .forecast_vol_adjusted_signal import forecast_vol_adjusted_signal
from .indicator_model_adaptive_pullback import indicator_model_adaptive_pullback_signal
from .manual_long_model_filter_signal import manual_long_model_filter_signal
from .meta_probability_side_signal import meta_probability_side_signal
from .momentum_strategy import momentum_strategy
from .orb_candidate_side_signal import orb_candidate_side_signal
from .ppo_adx_stochrsi_trend_signal import ppo_adx_stochrsi_trend_signal
from .probabilistic_signal import probabilistic_signal
from .probability_vol_adjusted_signal import probability_vol_adjusted_signal
from .quote_flow_scalp_router_signal import quote_flow_scalp_router_signal
from .regime_filtered_signal import regime_filtered_signal
from .roc_long_only_conditions_signal import roc_long_only_conditions_signal
from .rsi_strategy import rsi_strategy
from .stc_roofing_hilbert import stc_roofing_hilbert_signal
from .stochastic_strategy import stochastic_strategy
from .trend_state_signal import trend_state_signal
from .volatility_regime_strategy import volatility_regime_strategy
from .vwap_rms_ema_cross_long_fractal_filter import vwap_rms_ema_cross_long_fractal_filter_signal
from .vwap_rms_ema_cross_long_hmm_gate import vwap_rms_ema_cross_long_hmm_gate_signal
from .vwap_rms_ema_cross_long_signal import vwap_rms_ema_cross_long_signal

SignalFn = Callable[..., Union[pd.DataFrame, pd.Series]]


_SIGNAL_COMPONENTS: tuple[tuple[str, SignalFn], ...] = (
    ("c1_trend_pullback_vwap", c1_trend_pullback_vwap_signal),
    ("c2_regime_aware_momentum", c2_regime_aware_momentum_signal),
    ("ehlers_continuation_long", ehlers_continuation_long_signal),
    ("ehlers_continuation_short", ehlers_continuation_short_signal),
    ("ehlers_decycler_continuation", ehlers_decycler_continuation_signal),
    ("ehlers_semiscalp_long", ehlers_semiscalp_long_signal),
    ("ehlers_trend_pullback_continuation_long", ehlers_trend_pullback_continuation_long_signal),
    ("trend_state", trend_state_signal),
    ("ema_rms_ppo_vwap", ema_rms_ppo_vwap_signal),
    ("probability_threshold", probabilistic_signal),
    ("probability_conviction", conviction_sizing_signal),
    ("probability_vol_adjusted", probability_vol_adjusted_signal),
    ("meta_probability_side", meta_probability_side_signal),
    ("orb_candidate_side", orb_candidate_side_signal),
    ("ppo_adx_stochrsi_trend", ppo_adx_stochrsi_trend_signal),
    ("quote_flow_scalp_router", quote_flow_scalp_router_signal),
    ("roc_long_only_conditions", roc_long_only_conditions_signal),
    ("ema_stoch_rsi_pullback", ema_stoch_rsi_pullback_signal),
    ("indicator_model_adaptive_pullback", indicator_model_adaptive_pullback_signal),
    ("manual_long_model_filter", manual_long_model_filter_signal),
    ("dense_return_forecast", dense_return_forecast_signal),
    ("forecast_threshold", forecast_threshold_signal),
    ("forecast_vol_adjusted", forecast_vol_adjusted_signal),
    ("rsi", rsi_strategy),
    ("momentum", momentum_strategy),
    ("stochastic", stochastic_strategy),
    ("stc_roofing_hilbert", stc_roofing_hilbert_signal),
    ("volatility_regime", volatility_regime_strategy),
    ("vwap_rms_ema_cross_long_fractal_filter", vwap_rms_ema_cross_long_fractal_filter_signal),
    ("vwap_rms_ema_cross_long_hmm_gate", vwap_rms_ema_cross_long_hmm_gate_signal),
    ("vwap_rms_ema_cross_long", vwap_rms_ema_cross_long_signal),
    ("regime_filtered", regime_filtered_signal),
)


SIGNAL_REGISTRY: Mapping[str, SignalFn] = build_registry("signal", _SIGNAL_COMPONENTS)


# Deprecated 2026-06-25: kept only so older YAMLs using function-style kind names
# can still resolve. New configs should use ehlers_continuation_long/short.
DEPRECATED_SIGNAL_ALIASES: Mapping[str, SignalFn] = build_registry(
    "deprecated signal alias",
    (
        ("ehlers_continuation_long_signal", ehlers_continuation_long_signal),
        ("ehlers_continuation_short_signal", ehlers_continuation_short_signal),
    ),
)

SIGNAL_KINDS = registry_names(SIGNAL_REGISTRY, DEPRECATED_SIGNAL_ALIASES)


def get_signal_fn(name: str) -> SignalFn:
    """
    Apply the registered ``get_signal_fn`` signal transformation.
    
    This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        signals:
          kind: get_signal_fn
          params:
            name: <required>
    
    Required input columns
    ----------------------
    Direct inputs:
        This callable operates on supplied Series/arrays directly or resolves
        dataframe inputs from the configuration shown above at runtime.
    
    Parameters
    ----------
    name:
        Configuration parameter accepted by this signal.
    """
    return get_registered_component(
        SIGNAL_REGISTRY,
        name,
        category="signal",
        aliases=DEPRECATED_SIGNAL_ALIASES,
    )


__all__ = [
    "DEPRECATED_SIGNAL_ALIASES",
    "SIGNAL_KINDS",
    "SIGNAL_REGISTRY",
    "SignalFn",
    "get_signal_fn",
]
