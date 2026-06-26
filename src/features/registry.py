from __future__ import annotations

from collections.abc import Callable, Mapping

import pandas as pd

from src.utils.registry import build_registry, get_registered_component, lazy_callable, registry_names

from .autocorrelation_periodogram import add_autocorrelation_periodogram
from .center_of_gravity import add_center_of_gravity
from .cyber_cycle import add_cyber_cycle
from .decycler import add_decycler
from .decycler_oscillator import add_decycler_oscillator
from .dominant_cycle_period import add_dominant_cycle_period
from .dominant_cycle_phase import add_dominant_cycle_phase
from .ehlers_ml_long_candidate import ehlers_ml_long_candidate_feature
from .even_better_sinewave import add_even_better_sinewave
from .extrema_context import swing_extrema_context
from .fama import add_fama
from .fisher_transform import add_fisher_transform
from .fractal_dimension import add_fractal_dimension
from .frama import add_frama
from .garman_klass_volatility import add_garman_klass_volatility
from .hilbert_transform import add_hilbert_transform
from .hmm_regime import add_hmm_regime
from .homodyne_discriminator import add_homodyne_discriminator
from .hurst_exponent import add_hurst_exponent
from .instantaneous_trendline import add_instantaneous_trendline
from .inverse_fisher_transform import add_inverse_fisher_transform
from .laguerre_rsi import add_laguerre_rsi
from .lags import add_lagged_features
from .macro import add_macro_context_features
from .mama import add_mama
from .multi_timeframe import add_multi_timeframe_features
from .opening_range_breakout import add_opening_range_breakout_features
from .order_flow_imbalance import add_order_flow_imbalance
from .parkinson_volatility import add_parkinson_volatility
from .permutation_entropy import add_permutation_entropy
from .regime_context import add_regime_context_features
from .helpers.normalizations.returns import add_close_returns
from .rolling_r2_trend_quality import add_rolling_r2_trend_quality
from .roofing_filter import add_roofing_filter
from .session_context import add_session_context_features
from .shannon_entropy import add_shannon_entropy
from .shock_context import add_shock_context_features
from .sinewave_indicator import add_sinewave_indicator
from .supersmoother import add_supersmoother
from .support_resistance import add_support_resistance_features
from .support_resistance_v2 import add_support_resistance_v2_features
from .technical.adx import add_adx_features
from .technical.atr import add_atr_features
from .technical.bollinger import add_bollinger_features
from .technical.indicator_pullback import add_indicator_pullback_features
from .technical.macd import add_macd_features
from .technical.mfi import add_mfi_features
from .technical.ppo import add_ppo_features
from .technical.price_momentum import add_price_momentum_features
from .technical.return_momentum import add_return_momentum_features
from .technical.roc import add_roc_features
from .technical.rsi import add_rsi_features
from .technical.schaff_trend_cycle import add_schaff_trend_cycle_features
from .technical.stochastic import add_stochastic_features
from .technical.stochastic_rsi import add_stochastic_rsi_features
from .technical.trend import add_trend_features
from .technical.vol_normalized_momentum import add_vol_normalized_momentum_features
from .technical.volume_features import add_volume_features
from .technical.vwap import add_vwap_features
from .trend_regime import add_trend_regime
from .trend_slope_volatility import add_trend_slope_volatility
from .volatility import add_volatility_features
from .volatility_of_volatility import add_volatility_of_volatility
from .volatility_regime import add_volatility_regime
from .vpin import add_vpin
from .yang_zhang_volatility import add_yang_zhang_volatility
from .zscore_momentum import add_zscore_momentum

FeatureFn = Callable[..., pd.DataFrame]


_FEATURE_COMPONENTS: tuple[tuple[str, FeatureFn], ...] = (
    ("returns", add_close_returns),
    ("volatility", add_volatility_features),
    ("trend", add_trend_features),
    ("trend_regime", add_trend_regime),
    ("lags", add_lagged_features),
    ("bollinger", add_bollinger_features),
    ("macd", add_macd_features),
    ("ppo", add_ppo_features),
    ("roc", add_roc_features),
    ("atr", add_atr_features),
    ("adx", add_adx_features),
    ("volume_features", add_volume_features),
    ("vwap", add_vwap_features),
    ("mfi", add_mfi_features),
    ("rsi", add_rsi_features),
    ("stochastic", add_stochastic_features),
    ("stochastic_rsi", add_stochastic_rsi_features),
    ("price_momentum", add_price_momentum_features),
    ("return_momentum", add_return_momentum_features),
    ("vol_normalized_momentum", add_vol_normalized_momentum_features),
    ("session_context", add_session_context_features),
    ("regime_context", add_regime_context_features),
    ("shock_context", add_shock_context_features),
    ("support_resistance", add_support_resistance_features),
    ("support_resistance_v2", add_support_resistance_v2_features),
    ("macro_context", add_macro_context_features),
    ("multi_timeframe", add_multi_timeframe_features),
    ("opening_range_breakout", add_opening_range_breakout_features),
    ("swing_extrema_context", swing_extrema_context),
    ("indicator_pullback", add_indicator_pullback_features),
    ("ehlers_ml_long_candidate", ehlers_ml_long_candidate_feature),
    ("mama", add_mama),
    ("fama", add_fama),
    ("dominant_cycle_period", add_dominant_cycle_period),
    ("dominant_cycle_phase", add_dominant_cycle_phase),
    ("instantaneous_trendline", add_instantaneous_trendline),
    ("fisher_transform", add_fisher_transform),
    ("inverse_fisher_transform", add_inverse_fisher_transform),
    ("sinewave_indicator", add_sinewave_indicator),
    ("cyber_cycle", add_cyber_cycle),
    ("decycler", add_decycler),
    ("decycler_oscillator", add_decycler_oscillator),
    ("laguerre_rsi", add_laguerre_rsi),
    ("frama", add_frama),
    ("center_of_gravity", add_center_of_gravity),
    ("even_better_sinewave", add_even_better_sinewave),
    ("autocorrelation_periodogram", add_autocorrelation_periodogram),
    ("homodyne_discriminator", add_homodyne_discriminator),
    ("parkinson_volatility", add_parkinson_volatility),
    ("garman_klass_volatility", add_garman_klass_volatility),
    ("yang_zhang_volatility", add_yang_zhang_volatility),
    ("hurst_exponent", add_hurst_exponent),
    ("fractal_dimension", add_fractal_dimension),
    ("zscore_momentum", add_zscore_momentum),
    ("rolling_r2_trend_quality", add_rolling_r2_trend_quality),
    ("trend_slope_volatility", add_trend_slope_volatility),
    ("volatility_of_volatility", add_volatility_of_volatility),
    ("volatility_regime", add_volatility_regime),
    ("hmm_regime", add_hmm_regime),
    ("hilbert_transform", add_hilbert_transform),
    ("roofing_filter", add_roofing_filter),
    ("schaff_trend_cycle", add_schaff_trend_cycle_features),
    ("supersmoother", add_supersmoother),
    ("shannon_entropy", add_shannon_entropy),
    ("permutation_entropy", add_permutation_entropy),
    ("vpin", add_vpin),
    ("order_flow_imbalance", add_order_flow_imbalance),
)


FEATURE_REGISTRY: Mapping[str, FeatureFn] = build_registry("feature", _FEATURE_COMPONENTS)


def _legacy_signal_feature_steps() -> Mapping[str, FeatureFn]:
    return build_registry(
        "legacy feature-compatible signal step",
        (
            ("ehlers_semiscalp_long", lazy_callable("src.signals.ehlers_semiscalp_long_signal", "ehlers_semiscalp_long_feature")),
            ("ehlers_decycler_continuation", lazy_callable("src.signals.ehlers_decycler_continuation_signal", "ehlers_decycler_continuation_feature")),
            ("ema_stoch_rsi_pullback", lazy_callable("src.signals.ema_stoch_rsi_pullback_signal", "ema_stoch_rsi_pullback_signal")),
            ("indicator_model_adaptive_pullback", lazy_callable("src.signals.indicator_model_adaptive_pullback", "indicator_model_adaptive_pullback_signal")),
            ("roc_long_only_conditions", lazy_callable("src.signals.roc_long_only_conditions_signal", "roc_long_only_conditions_signal")),
            ("vwap_rms_ema_cross_long", lazy_callable("src.signals.vwap_rms_ema_cross_long_signal", "vwap_rms_ema_cross_long_signal")),
        ),
    )


# Compatibility entries are resolvable by configs, but intentionally kept out of
# FEATURE_REGISTRY so the canonical registry contains feature builders only.
FEATURE_COMPATIBILITY_REGISTRY: Mapping[str, FeatureFn] = _legacy_signal_feature_steps()
FEATURE_KINDS = registry_names(FEATURE_REGISTRY, FEATURE_COMPATIBILITY_REGISTRY)


def get_feature_fn(name: str) -> FeatureFn:
    """
    Apply the registered ``get_feature_fn`` feature transformation.
    
    This feature uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated.
    
    YAML declaration::
    
        features:
          - step: get_feature_fn
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
        Configuration parameter accepted by this feature.
    """
    return get_registered_component(
        FEATURE_REGISTRY,
        name,
        category="feature",
        aliases=FEATURE_COMPATIBILITY_REGISTRY,
    )


__all__ = [
    "FEATURE_COMPATIBILITY_REGISTRY",
    "FEATURE_KINDS",
    "FEATURE_REGISTRY",
    "FeatureFn",
    "get_feature_fn",
]
