# Inventory Components

Τελευταία ενημέρωση: 2026-06-27

Αυτό το αρχείο είναι γρήγορη λίστα των διαθέσιμων component names για YAML
configs. Η πηγή αλήθειας είναι τα canonical registries:

- `src/features/registry.py`
- `src/signals/registry.py`
- `src/targets/registry.py`
- `src/models/registry.py`

Για νέα configs προτίμησε τα canonical names. Compatibility/deprecated aliases
υπάρχουν μόνο για migration παλιών YAMLs.

## Features

Canonical feature steps:

- `returns`
- `volatility`
- `trend`
- `trend_regime`
- `lags`
- `bollinger`
- `macd`
- `ppo`
- `roc`
- `atr`
- `adx`
- `volume_features`
- `vwap`
- `mfi`
- `rsi`
- `stochastic`
- `stochastic_rsi`
- `price_momentum`
- `return_momentum`
- `vol_normalized_momentum`
- `session_context`
- `regime_context`
- `shock_context`
- `support_resistance`
- `support_resistance_v2`
- `macro_context`
- `multi_timeframe`
- `opening_range_breakout`
- `swing_extrema_context`
- `indicator_pullback`
- `ehlers_ml_long_candidate`
- `mama`
- `fama`
- `dominant_cycle_period`
- `dominant_cycle_phase`
- `instantaneous_trendline`
- `fisher_transform`
- `inverse_fisher_transform`
- `sinewave_indicator`
- `cyber_cycle`
- `decycler`
- `decycler_oscillator`
- `laguerre_rsi`
- `frama`
- `center_of_gravity`
- `even_better_sinewave`
- `autocorrelation_periodogram`
- `homodyne_discriminator`
- `parkinson_volatility`
- `garman_klass_volatility`
- `yang_zhang_volatility`
- `hurst_exponent`
- `fractal_dimension`
- `zscore_momentum`
- `rolling_r2_trend_quality`
- `trend_slope_volatility`
- `volatility_of_volatility`
- `volatility_regime`
- `hmm_regime`
- `hilbert_transform`
- `roofing_filter`
- `schaff_trend_cycle`
- `supersmoother`
- `shannon_entropy`
- `permutation_entropy`
- `vpin`
- `order_flow_imbalance`
- `scalp_microstructure_proxy`

Feature-compatible legacy signal steps:

- `ehlers_semiscalp_long`
- `ehlers_decycler_continuation`
- `ema_stoch_rsi_pullback`
- `indicator_model_adaptive_pullback`
- `roc_long_only_conditions`
- `vwap_rms_ema_cross_long`

Σημείωση: τα legacy entries είναι resolvable για παλιά configs, αλλά δεν είναι
canonical raw feature builders.

## Signals

Canonical signal kinds:

- `c1_trend_pullback_vwap`
- `c2_regime_aware_momentum`
- `ehlers_continuation_long`
- `ehlers_continuation_short`
- `ehlers_decycler_continuation`
- `ehlers_semiscalp_long`
- `trend_state`
- `ema_rms_ppo_vwap`
- `probability_threshold`
- `probability_conviction`
- `probability_vol_adjusted`
- `meta_probability_side`
- `orb_candidate_side`
- `ppo_adx_stochrsi_trend`
- `roc_long_only_conditions`
- `ema_stoch_rsi_pullback`
- `indicator_model_adaptive_pullback`
- `manual_long_model_filter`
- `dense_return_forecast`
- `forecast_threshold`
- `forecast_vol_adjusted`
- `rsi`
- `momentum`
- `stochastic`
- `stc_roofing_hilbert`
- `volatility_regime`
- `vwap_rms_ema_cross_long_fractal_filter`
- `vwap_rms_ema_cross_long_hmm_gate`
- `vwap_rms_ema_cross_long`
- `regime_filtered`
- `quote_flow_scalp_router`

Deprecated signal aliases:

- `ehlers_continuation_long_signal`
- `ehlers_continuation_short_signal`

## Targets

Canonical target kinds:

- `forward_return`
- `future_return_regression`
- `triple_barrier`
- `directional_triple_barrier`
- `r_multiple`

## Models

Single-asset model kinds:

- `elastic_net_clf`
- `lightgbm_clf`
- `lightgbm_regressor`
- `logistic_regression_clf`
- `xgboost_clf`
- `event_transformer_encoder`
- `sarimax_forecaster`
- `garch_forecaster`
- `lstm_forecaster`
- `patchtst_forecaster`
- `tft_forecaster`
- `tsfresh_extrema_feature_discovery`
- `ppo_agent`
- `dqn_agent`

Portfolio model kinds:

- `ppo_portfolio_agent`
- `dqn_portfolio_agent`

RL model kinds:

- `dqn_agent`
- `dqn_portfolio_agent`
- `ppo_agent`
- `ppo_portfolio_agent`

## Σύντομο YAML Παράδειγμα

```yaml
features:
  - step: atr
    params:
      high_col: high
      low_col: low
      close_col: close
      window: 14
      atr_col: atr_14

model:
  kind: logistic_regression_clf
  target:
    kind: directional_triple_barrier

signals:
  kind: probability_threshold
  params:
    prob_col: prob_positive
    signal_col: signal_side
```

## Σχετικά Docs

- [Feature catalog](catalog/features.md)
- [Signal catalog](catalog/signals.md)
- [Target catalog](catalog/targets.md)
- [Model catalog](catalog/models.md)
- [Οδηγός YAML experiments](yaml_experiments_guide_gr.md)
