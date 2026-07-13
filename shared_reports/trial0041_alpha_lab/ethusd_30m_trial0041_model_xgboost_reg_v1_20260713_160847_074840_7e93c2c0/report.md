# Experiment Report: ethusd_30m_trial0041_model_xgboost_reg_v1

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/06_model_lab/ethusd_30m_trial0041_model_xgboost_reg_v1.yaml`
- Model kind: `xgboost_regressor`
- Symbols: `ETHUSD`
- Data source: `dukascopy_csv` at interval `30m`
- Data window: `None` to `2026-06-09 23:30:00`
- Rows / columns: `109005` rows, `126` columns
- Target: `future_return_regression` horizon `24`
- Feature count: `46`
- Runtime seed: `7`

## Pipeline Trace

### 1. Entry Point
- `runner.run_experiment` -> `src.experiments.runner.run_experiment(config_path: 'str | Path') -> 'ExperimentResult'`
- `runner._load_asset_frames` -> `src.experiments.runner._load_asset_frames(data_cfg: 'dict[str, object]')`
- `pipeline.run_experiment_pipeline` -> `src.experiments.orchestration.pipeline.run_experiment_pipeline(config_path: 'str | Path', *, load_asset_frames_fn: 'LoadAssetFramesFn', save_processed_snapshot_fn: 'SaveProcessedFn') -> 'ExperimentResult'`

```yaml
config_path: /workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/06_model_lab/ethusd_30m_trial0041_model_xgboost_reg_v1.yaml
runtime:
  seed: 7
  repro_mode: strict
  deterministic: true
  threads: 1
  seed_torch: false
```

### 2. Data Load And PIT
- `data_stage.load_asset_frames` -> `src.experiments.orchestration.data_stage.load_asset_frames(data_cfg: 'dict[str, Any]', *, load_ohlcv_fn: 'SingleAssetLoader', load_ohlcv_panel_fn: 'PanelLoader', apply_pit_hardening_fn: 'PitFn', validate_ohlcv_fn: 'ValidateFrameFn', validate_data_contract_fn: 'ValidateFrameFn') -> 'tuple[dict[str, pd.DataFrame], dict[str, Any]]'`
- `src_data.loaders.load_ohlcv` -> `src.src_data.loaders.load_ohlcv(symbol: 'str', start: 'str | None' = None, end: 'str | None' = None, interval: 'str' = '1d', source: "Literal['yahoo', 'alpha', 'twelve_data', 'twelve', 'dukascopy_csv']" = 'yahoo', api_key: 'Optional[str]' = None) -> 'pd.DataFrame'`
- `src_data.loaders.load_ohlcv_panel` -> `src.src_data.loaders.load_ohlcv_panel(symbols: 'Sequence[str]', start: 'str | None' = None, end: 'str | None' = None, interval: 'str' = '1d', source: "Literal['yahoo', 'alpha', 'twelve_data', 'twelve', 'dukascopy_csv']" = 'yahoo', api_key: 'Optional[str]' = None) -> 'dict[str, pd.DataFrame]'`
- `src_data.pit.apply_pit_hardening` -> `src.src_data.pit.apply_pit_hardening(df: 'pd.DataFrame', *, pit_cfg: 'Mapping[str, Any] | None' = None, symbol: 'str | None' = None) -> 'tuple[pd.DataFrame, dict[str, Any]]'`
- `src_data.validation.validate_ohlcv` -> `src.src_data.validation.validate_ohlcv(df: 'pd.DataFrame', required_columns: 'Iterable[str]' = ('open', 'high', 'low', 'close', 'volume'), allow_missing_volume: 'bool' = True) -> 'None'`
- `experiments.contracts.validate_data_contract` -> `src.evaluation.contracts.validate_data_contract(df: 'pd.DataFrame', contract: 'DataContract | None' = None) -> 'dict[str, int]'`
- `schemas.StorageContext` -> `src.experiments.schemas.StorageContext(symbols: 'list[str]', source: 'str | None', interval: 'str | None', start: 'str | None', end: 'str | None', pit: 'dict[str, Any]' = <factory>, pit_hash_sha256: 'str | None' = None) -> None`  
  Context object persisted into snapshot metadata.
- `data_stage.save_processed_snapshot_if_enabled` -> `src.experiments.orchestration.data_stage.save_processed_snapshot_if_enabled(asset_frames: 'dict[str, pd.DataFrame]', *, data_cfg: 'dict[str, Any]', config_hash_sha256: 'str', feature_steps: 'list[dict[str, Any]]', logging_cfg: 'dict[str, Any] | None' = None) -> 'dict[str, Any] | None'`

```yaml
data:
  source: dukascopy_csv
  interval: 30m
  start: null
  end: null
  alignment: inner
  symbol: ETHUSD
  symbols: null
  api_key: null
  api_key_env: null
  pit:
    timestamp_alignment:
      source_timezone: UTC
      output_timezone: UTC
      normalize_daily: false
      duplicate_policy: last
    corporate_actions:
      policy: none
      adj_close_col: adj_close
    universe_snapshot:
      inactive_policy: raise
  storage:
    mode: cached_only
    dataset_id: ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid
    save_raw: false
    save_processed: false
    load_path: /workspace/data/raw/dukascopy_30m_clean/ethusd_30m.csv
    raw_dir: /workspace/data/raw
    processed_dir: /workspace/data/processed
    load_paths: null
```

### 3. Feature Engineering
- `feature_stage.apply_steps_to_assets` -> `src.experiments.orchestration.feature_stage.apply_steps_to_assets(asset_frames: 'dict[str, pd.DataFrame]', *, feature_steps: 'list[dict[str, Any]]') -> 'dict[str, pd.DataFrame]'`
- `feature_stage.apply_feature_steps` -> `src.experiments.orchestration.feature_stage.apply_feature_steps(df: 'pd.DataFrame', steps: 'list[dict[str, Any]]', *, asset: 'str | None' = None) -> 'pd.DataFrame'`
- `feature[returns]` -> `src.features.helpers.normalizations.returns.add_close_returns(df: 'pd.DataFrame', log: 'bool' = False, col_name: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'log': False, 'col_name': 'close_ret'}
- `feature[volatility]` -> `src.features.volatility.add_volatility_features(df: 'pd.DataFrame', returns_col: 'str' = 'close_logret', rolling_windows: 'Sequence[int]' = (10, 20, 60), ewma_spans: 'Sequence[int]' = (10, 20), annualization_factor: 'Optional[float]' = 252.0, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'returns_col': 'close_ret', 'rolling_windows': [24, 48, 96, 192], 'ewma_spans': [], 'annualization_factor': None}
- `feature[trend]` -> `src.features.technical.trend.add_trend_features(df: 'pd.DataFrame', price_col: 'str' = 'close', sma_windows: 'Sequence[int]' = (20, 50, 200), ema_spans: 'Sequence[int]' = (20, 50), sma_col_template: 'str | None' = None, ema_col_template: 'str | None' = None, add_ratios: 'bool' = False, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'sma_windows': [], 'ema_spans': [24, 48, 96, 192], 'ema_col_template': 'ema_{span}', 'add_ratios': False}
- `feature[atr]` -> `src.features.technical.atr.add_atr_features(df: 'pd.DataFrame', high_col: 'str' = 'high', low_col: 'str' = 'low', close_col: 'str' = 'close', window: 'int' = 14, windows: 'Sequence[int] | None' = None, method: 'str' = 'wilder', add_over_price: 'bool' = False, atr_col: 'str | None' = None, over_price_col: 'str | None' = None, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'high_col': 'high', 'low_col': 'low', 'close_col': 'close', 'window': 48, 'windows': [48], 'method': 'wilder', 'add_over_price': False, 'atr_col': 'atr_48'}
- `feature[hilbert_transform]` -> `src.features.hilbert_transform.add_hilbert_transform(df: 'pd.DataFrame', price_col: 'str' = 'close', window: 'int' = 64, amplitude_col: 'str | None' = None, phase_col: 'str | None' = None, instantaneous_frequency_col: 'str | None' = None, dominant_cycle_col: 'str | None' = None, cycle_ok_col: 'str | None' = None, amplitude_rising_col: 'str | None' = None, min_cycle: 'int' = 10, max_cycle: 'int' = 48, amplitude_slope_bars: 'int' = 3, add_derived: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'window': 64, 'amplitude_col': 'hilbert_amplitude', 'phase_col': 'hilbert_phase', 'instantaneous_frequency_col': 'hilbert_instantaneous_frequency', 'add_derived': False}
- `feature[dominant_cycle_period]` -> `src.features.dominant_cycle_period.add_dominant_cycle_period(df: 'pd.DataFrame', price_col: 'str' = 'close', output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'output_col': 'dominant_cycle_period'}
- `feature[dominant_cycle_phase]` -> `src.features.dominant_cycle_phase.add_dominant_cycle_phase(df: 'pd.DataFrame', price_col: 'str' = 'close', output_col: 'str | None' = None, unit: 'str' = 'degrees') -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'output_col': 'dominant_cycle_phase', 'unit': 'degrees'}
- `feature[mama]` -> `src.features.mama.add_mama(df: 'pd.DataFrame', price_col: 'str' = 'close', fast_limit: 'float' = 0.5, slow_limit: 'float' = 0.05, output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'fast_limit': 0.5, 'slow_limit': 0.05, 'output_col': 'mama'}
- `feature[fama]` -> `src.features.fama.add_fama(df: 'pd.DataFrame', price_col: 'str' = 'close', fast_limit: 'float' = 0.5, slow_limit: 'float' = 0.05, output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'fast_limit': 0.5, 'slow_limit': 0.05, 'output_col': 'fama'}
- `feature[decycler]` -> `src.features.decycler.add_decycler(df: 'pd.DataFrame', price_col: 'str' = 'close', period: 'int' = 60, output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'period': 60, 'output_col': 'decycler'}
- `feature[decycler_oscillator]` -> `src.features.decycler_oscillator.add_decycler_oscillator(df: 'pd.DataFrame', price_col: 'str' = 'close', fast_period: 'int' = 30, slow_period: 'int' = 60, output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'fast_period': 30, 'slow_period': 60, 'output_col': 'decycler_oscillator_30_60'}
- `feature[instantaneous_trendline]` -> `src.features.instantaneous_trendline.add_instantaneous_trendline(df: 'pd.DataFrame', price_col: 'str' = 'close', alpha: 'float' = 0.07, output_col: 'str | None' = None, trigger_col: 'str | None' = None, add_trigger: 'bool' = True) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'alpha': 0.07, 'output_col': 'instantaneous_trendline', 'add_trigger': False}
- `feature[frama]` -> `src.features.frama.add_frama(df: 'pd.DataFrame', price_col: 'str' = 'close', high_col: 'str' = 'high', low_col: 'str' = 'low', window: 'int' = 16, fast_period: 'int' = 4, slow_period: 'int' = 300, output_col: 'str | None' = None, alpha_col: 'str | None' = None, fractal_dimension_col: 'str | None' = None, add_diagnostics: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'high_col': 'high', 'low_col': 'low', 'window': 16, 'fast_period': 4, 'slow_period': 300, 'output_col': 'frama', 'add_diagnostics': False}
- `feature[supersmoother]` -> `src.features.supersmoother.add_supersmoother(df: 'pd.DataFrame', price_col: 'str' = 'close', period: 'int' = 10, output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'period': 10, 'output_col': 'supersmoother'}
- `feature[roofing_filter]` -> `src.features.roofing_filter.add_roofing_filter(df: 'pd.DataFrame', price_col: 'str' = 'close', high_pass_period: 'int' = 48, low_pass_period: 'int' = 10, output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'high_pass_period': 48, 'low_pass_period': 10, 'output_col': 'roofing_filter'}
- `feature[ehlers_ml_long_candidate]` -> `src.features.ehlers_ml_long_candidate.ehlers_ml_long_candidate_feature(df: 'pd.DataFrame', *, amplitude_col: 'str' = 'hilbert_amplitude', cycle_period_col: 'str' = 'dominant_cycle_period', roofing_col: 'str' = 'roofing_filter', mama_col: 'str' = 'mama', fama_col: 'str' = 'fama', close_col: 'str' = 'close', decycler_col: 'str' = 'decycler', instantaneous_trendline_col: 'str' = 'instantaneous_trendline', frama_col: 'str' = 'frama', supersmoother_col: 'str' = 'supersmoother', dominant_cycle_phase_col: 'str' = 'dominant_cycle_phase', dominant_cycle_phase_unit: 'str' = 'degrees', atr_col: 'str | None' = None, amplitude_lookback: 'int' = 128, amplitude_min_quantile: 'float' = 0.5, min_cycle_period: 'float' = 8.0, max_cycle_period: 'float' = 60.0, slope_bars: 'int' = 1, candidate_col: 'str' = 'ehlers_ml_candidate', side_col: 'str' = 'signal_side') -> 'pd.DataFrame'`  
  params={'amplitude_col': 'hilbert_amplitude', 'cycle_period_col': 'dominant_cycle_period', 'roofing_col': 'roofing_filter', 'mama_col': 'mama', 'fama_col': 'fama', 'close_col': 'close', 'decycler_col': 'decycler', 'instantaneous_trendline_col': 'instantaneous_trendline', 'frama_col': 'frama', 'supersmoother_col': 'supersmoother', 'dominant_cycle_phase_col': 'dominant_cycle_phase', 'dominant_cycle_phase_unit': 'degrees', 'atr_col': 'atr_48', 'amplitude_lookback': 128, 'amplitude_min_quantile': 0.5, 'min_cycle_period': 8.0, 'max_cycle_period': 60.0, 'slope_bars': 1, 'candidate_col': 'ehlers_ml_candidate', 'side_col': 'ehlers_ml_side'}
- `feature[macd]` -> `src.features.technical.macd.add_macd_features(df: 'pd.DataFrame', price_col: 'str' = 'close', fast: 'int' = 12, slow: 'int' = 26, signal: 'int' = 9, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'fast': 12, 'slow': 26, 'signal': 9}
- `feature[rsi]` -> `src.features.technical.rsi.add_rsi_features(df: 'pd.DataFrame', price_col: 'str' = 'close', windows: 'Sequence[int]' = (14,), method: 'str' = 'wilder', inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'windows': [14], 'method': 'wilder'}
- `feature[stochastic_rsi]` -> `src.features.technical.stochastic_rsi.add_stochastic_rsi_features(df: 'pd.DataFrame', price_col: 'str' = 'close', rsi_period: 'int' = 14, stoch_period: 'int' = 14, k_period: 'int' = 3, d_period: 'int' = 3, oversold: 'float' = 0.2, overbought: 'float' = 0.8, prefix: 'str' = 'stoch_rsi', method: 'str' = 'wilder', inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'rsi_period': 14, 'stoch_period': 14, 'k_period': 3, 'd_period': 3, 'oversold': 0.2, 'overbought': 0.8, 'prefix': 'stoch_rsi'}
- `feature[bollinger]` -> `src.features.technical.bollinger.add_bollinger_features(df: 'pd.DataFrame', price_col: 'str' = 'close', window: 'int' = 20, n_std: 'float' = 2.0, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'window': 192, 'n_std': 2.0}
- `feature[indicator_pullback]` -> `src.features.technical.indicator_pullback.add_indicator_pullback_features(df: 'pd.DataFrame', *, asset: 'str | None' = None, asset_vocab: 'Sequence[str] | None' = None, asset_aliases: 'Mapping[str, str] | None' = None, open_col: 'str' = 'open', high_col: 'str' = 'high', low_col: 'str' = 'low', close_col: 'str' = 'close', ema_fast_period: 'int' = 20, ema_mid_period: 'int' = 50, ema_slow_period: 'int' = 100, ema_fast_col: 'str | None' = None, ema_mid_col: 'str | None' = None, ema_slow_col: 'str | None' = None, atr_period: 'int' = 14, atr_col: 'str | None' = None, atr_pct_col: 'str' = 'atr_pct', atr_pct_rank_window: 'int' = 100, macd_hist_col: 'str' = 'macd_hist', rsi_period: 'int' = 14, rsi_col: 'str | None' = None, stoch_k_col: 'str' = 'stoch_rsi_k', stoch_d_col: 'str' = 'stoch_rsi_d', bollinger_bandwidth_col: 'str' = 'bollinger_bandwidth', bollinger_percent_b_col: 'str' = 'bollinger_percent_b', realized_vol_windows: 'Sequence[int] | None' = (10, 20), return_windows: 'Sequence[int] | None' = (1, 2, 3, 6), rolling_return_windows: 'Sequence[int] | None' = (4, 8), bb_bandwidth_rank_window: 'int | None' = 100, include_asset_id: 'bool' = True, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'asset_vocab': ['ETHUSD'], 'open_col': 'open', 'high_col': 'high', 'low_col': 'low', 'close_col': 'close', 'ema_fast_period': 24, 'ema_mid_period': 96, 'ema_slow_period': 192, 'atr_period': 48, 'atr_pct_rank_window': 192, 'macd_hist_col': 'macd_hist', 'rsi_period': 14, 'stoch_k_col': 'stoch_rsi_k', 'stoch_d_col': 'stoch_rsi_d', 'bollinger_bandwidth_col': 'bollinger_bandwidth', 'bollinger_percent_b_col': 'bollinger_percent_b', 'bb_bandwidth_rank_window': 192, 'realized_vol_windows': [24, 48, 96, 192], 'return_windows': [1, 4, 8, 16, 24, 48], 'rolling_return_windows': [24, 48]}

```yaml
features:
- step: returns
  params:
    log: false
    col_name: close_ret
  outputs: {}
  enabled: true
  transforms:
    lag:
      enabled: true
      items:
      - source_col: close_ret
        lag: 1
        output_col: lag_close_ret_1
      - source_col: close_ret
        lag: 2
        output_col: lag_close_ret_2
      - source_col: close_ret
        lag: 4
        output_col: lag_close_ret_4
      - source_col: close_ret
        lag: 8
        output_col: lag_close_ret_8
      - source_col: close_ret
        lag: 16
        output_col: lag_close_ret_16
      - source_col: close_ret
        lag: 24
        output_col: lag_close_ret_24
      - source_col: close_ret
        lag: 48
        output_col: lag_close_ret_48
- step: volatility
  params:
    returns_col: close_ret
    rolling_windows:
    - 24
    - 48
    - 96
    - 192
    ewma_spans: []
    annualization_factor: null
  outputs: {}
  enabled: true
- step: trend
  params:
    price_col: close
    sma_windows: []
    ema_spans:
    - 24
    - 48
    - 96
    - 192
    ema_col_template: ema_{span}
    add_ratios: false
  outputs: {}
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: ema_24
        denominator_col: ema_96
        output_col: ema_trend_24_96
        subtract: 1.0
      - numerator_col: ema_48
        denominator_col: ema_192
        output_col: ema_trend_48_192
        subtract: 1.0
      - numerator_col: close
        denominator_col: ema_96
        output_col: close_over_ema_96
        subtract: 1.0
      - numerator_col: close
        denominator_col: ema_192
        output_col: close_over_ema_192
        subtract: 1.0
- step: atr
  params:
    high_col: high
    low_col: low
    close_col: close
    window: 48
    windows:
    - 48
    method: wilder
    add_over_price: false
    atr_col: atr_48
  outputs: {}
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: atr_48
        denominator_col: close
        output_col: atr_over_price_48
- step: hilbert_transform
  params:
    price_col: close
    window: 64
    amplitude_col: hilbert_amplitude
    phase_col: hilbert_phase
    instantaneous_frequency_col: hilbert_instantaneous_frequency
    add_derived: false
  outputs: {}
  enabled: true
- step: dominant_cycle_period
  params:
    price_col: close
    output_col: dominant_cycle_period
  outputs: {}
  enabled: true
- step: dominant_cycle_phase
  params:
    price_col: close
    output_col: dominant_cycle_phase
    unit: degrees
  outputs: {}
  enabled: true
- step: mama
  params:
    price_col: close
    fast_limit: 0.5
    slow_limit: 0.05
    output_col: mama
  outputs: {}
  enabled: true
- step: fama
  params:
    price_col: close
    fast_limit: 0.5
    slow_limit: 0.05
    output_col: fama
  outputs: {}
  enabled: true
- step: decycler
  params:
    price_col: close
    period: 60
    output_col: decycler
  outputs: {}
  enabled: true
- step: decycler_oscillator
  params:
    price_col: close
    fast_period: 30
    slow_period: 60
    output_col: decycler_oscillator_30_60
  outputs: {}
  enabled: true
- step: instantaneous_trendline
  params:
    price_col: close
    alpha: 0.07
    output_col: instantaneous_trendline
    add_trigger: false
  outputs: {}
  enabled: true
- step: frama
  params:
    price_col: close
    high_col: high
    low_col: low
    window: 16
    fast_period: 4
    slow_period: 300
    output_col: frama
    add_diagnostics: false
  outputs: {}
  enabled: true
- step: supersmoother
  params:
    price_col: close
    period: 10
    output_col: supersmoother
  outputs: {}
  enabled: true
- step: roofing_filter
  params:
    price_col: close
    high_pass_period: 48
    low_pass_period: 10
    output_col: roofing_filter
  outputs: {}
  enabled: true
- step: ehlers_ml_long_candidate
  params:
    amplitude_col: hilbert_amplitude
    cycle_period_col: dominant_cycle_period
    roofing_col: roofing_filter
    mama_col: mama
    fama_col: fama
    close_col: close
    decycler_col: decycler
    instantaneous_trendline_col: instantaneous_trendline
    frama_col: frama
    supersmoother_col: supersmoother
    dominant_cycle_phase_col: dominant_cycle_phase
    dominant_cycle_phase_unit: degrees
    atr_col: atr_48
    amplitude_lookback: 128
    amplitude_min_quantile: 0.5
    min_cycle_period: 8.0
    max_cycle_period: 60.0
    slope_bars: 1
    candidate_col: ehlers_ml_candidate
    side_col: ehlers_ml_side
  outputs: {}
  enabled: true
- step: macd
  params:
    price_col: close
    fast: 12
    slow: 26
    signal: 9
  outputs:
    macd_12_26: macd
    macd_signal_9: macd_signal
    macd_hist_12_26_9: macd_hist
  enabled: true
- step: rsi
  params:
    price_col: close
    windows:
    - 14
    method: wilder
  outputs:
    close_rsi_14: rsi_14
  enabled: true
- step: stochastic_rsi
  params:
    price_col: close
    rsi_period: 14
    stoch_period: 14
    k_period: 3
    d_period: 3
    oversold: 0.2
    overbought: 0.8
    prefix: stoch_rsi
  outputs:
    stoch_rsi_k: stoch_rsi_k
    stoch_rsi_d: stoch_rsi_d
  enabled: true
- step: bollinger
  params:
    price_col: close
    window: 192
    n_std: 2.0
  outputs:
    bb_ma_192: bollinger_mid_192
    bb_upper_192_2.0: bollinger_upper_192
    bb_lower_192_2.0: bollinger_lower_192
    bb_width_192_2.0: bollinger_bandwidth
    bb_percent_b_192_2.0: bollinger_percent_b
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: close
        denominator_col: bb_upper_192_2.0
        output_col: close_over_bb_upper_192
        subtract: 1.0
      - numerator_col: close
        denominator_col: bb_ma_192
        output_col: close_over_bb_mid_192
        subtract: 1.0
- step: indicator_pullback
  params:
    asset_vocab:
    - ETHUSD
    open_col: open
    high_col: high
    low_col: low
    close_col: close
    ema_fast_period: 24
    ema_mid_period: 96
    ema_slow_period: 192
    atr_period: 48
    atr_pct_rank_window: 192
    macd_hist_col: macd_hist
    rsi_period: 14
    stoch_k_col: stoch_rsi_k
    stoch_d_col: stoch_rsi_d
    bollinger_bandwidth_col: bollinger_bandwidth
    bollinger_percent_b_col: bollinger_percent_b
    bb_bandwidth_rank_window: 192
    realized_vol_windows:
    - 24
    - 48
    - 96
    - 192
    return_windows:
    - 1
    - 4
    - 8
    - 16
    - 24
    - 48
    rolling_return_windows:
    - 24
    - 48
  outputs: {}
  enabled: true
resolved_feature_columns:
- close_ret
- lag_close_ret_1
- lag_close_ret_2
- lag_close_ret_4
- lag_close_ret_8
- lag_close_ret_16
- lag_close_ret_24
- lag_close_ret_48
- ret_1
- ret_4
- ret_8
- ret_16
- ret_24
- ret_48
- rolling_return_24
- rolling_return_48
- vol_rolling_24
- vol_rolling_48
- vol_rolling_96
- vol_rolling_192
- atr_48
- atr_over_price_48
- atr_pct
- atr_pct_rank_192
- ema_trend_48_192
- close_over_bb_upper_192
- close_over_bb_mid_192
- bollinger_percent_b
- bollinger_bandwidth
- bollinger_bandwidth_rank_192
- ema_alignment_score
- distance_from_ema24_atr
- distance_from_ema96_atr
- mama_minus_fama_over_atr
- close_minus_decycler_over_atr
- instantaneous_trendline_slope_over_atr
- decycler_slope_over_atr
- frama_slope_over_atr
- supersmoother_slope_over_atr
- roofing_filter_over_atr
- dominant_cycle_phase_normalized
- body_ratio
- upper_wick_ratio
- lower_wick_ratio
- close_location
- range_to_atr
```

### 4. Model And Training
- `model_stage.apply_model_pipeline_to_assets` -> `src.experiments.orchestration.model_stage.apply_model_pipeline_to_assets(asset_frames: 'dict[str, pd.DataFrame]', *, model_cfg: 'dict[str, Any] | None', model_stages: 'list[dict[str, Any]] | None', returns_col: 'str | None') -> 'tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]'`
- `model_stage.apply_model_to_assets` -> `src.experiments.orchestration.model_stage.apply_model_to_assets(asset_frames: 'dict[str, pd.DataFrame]', *, model_cfg: 'dict[str, Any]', returns_col: 'str | None') -> 'tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]'`
- `feature_stage.apply_model_step` -> `src.experiments.orchestration.model_stage.apply_model_step(df: 'pd.DataFrame', model_cfg: 'dict[str, Any]', returns_col: 'str | None') -> 'tuple[pd.DataFrame, object | None, dict[str, Any]]'`
- `model[xgboost_regressor]` -> `src.models.forecasting.base.train_xgboost_regressor(*args: 'object', **kwargs: 'object') -> 'object'`
- `modeling.runtime.resolve_runtime_for_model` -> `src.models.common.runtime.resolve_runtime_for_model(model_cfg: 'dict[str, Any]', model_params: 'dict[str, Any]', *, estimator_family: 'str') -> 'dict[str, Any]'`

```yaml
model:
  kind: xgboost_regressor
  params:
    n_estimators: 600
    learning_rate: 0.04
    max_depth: 4
    min_child_weight: 20
    subsample: 0.9
    colsample_bytree: 0.75
    reg_alpha: 0.05
    reg_lambda: 2.0
    objective: reg:squarederror
    eval_metric: rmse
    tree_method: hist
    random_state: 7
    n_jobs: 1
  outputs:
    pred_ret_col: pred_ret
    pred_prob_col: pred_prob
    pred_is_oos_col: pred_is_oos
  preprocessing:
    scaler: none
  calibration: {}
  feature_cols:
  - close_ret
  - lag_close_ret_1
  - lag_close_ret_2
  - lag_close_ret_4
  - lag_close_ret_8
  - lag_close_ret_16
  - lag_close_ret_24
  - lag_close_ret_48
  - ret_1
  - ret_4
  - ret_8
  - ret_16
  - ret_24
  - ret_48
  - rolling_return_24
  - rolling_return_48
  - vol_rolling_24
  - vol_rolling_48
  - vol_rolling_96
  - vol_rolling_192
  - atr_48
  - atr_over_price_48
  - atr_pct
  - atr_pct_rank_192
  - ema_trend_48_192
  - close_over_bb_upper_192
  - close_over_bb_mid_192
  - bollinger_percent_b
  - bollinger_bandwidth
  - bollinger_bandwidth_rank_192
  - ema_alignment_score
  - distance_from_ema24_atr
  - distance_from_ema96_atr
  - mama_minus_fama_over_atr
  - close_minus_decycler_over_atr
  - instantaneous_trendline_slope_over_atr
  - decycler_slope_over_atr
  - frama_slope_over_atr
  - supersmoother_slope_over_atr
  - roofing_filter_over_atr
  - dominant_cycle_phase_normalized
  - body_ratio
  - upper_wick_ratio
  - lower_wick_ratio
  - close_location
  - range_to_atr
  target:
    kind: future_return_regression
    price_col: close
    returns_col: close_ret
    returns_type: simple
    horizon_bars: 24
    normalize_by_volatility: true
    volatility_col: atr_48
    clip:
    - -4.0
    - 4.0
    fwd_col: target_future_return_h24_atr
    label_col: target_future_return_h24_atr
  split:
    method: purged
    train_size: 35040
    test_size: 4380
    step_size: 4380
    expanding: true
    max_folds: 10
    purge_bars: 24
    embargo_bars: 24
  runtime: {}
  env: {}
  use_features: true
  pred_prob_col: pred_prob
  pred_raw_prob_col: null
  pred_ret_col: pred_ret
  pred_is_oos_col: pred_is_oos
  returns_input_col: null
  signal_col: null
  action_col: null
model_stages: []
resolved_reward_config:
  cost_per_turnover: 0.0001
  slippage_per_turnover: 0.0
  inventory_penalty: 0.0
  drawdown_penalty: 0.0
  switching_penalty: 0.0
resolved_execution_config:
  backtest_min_holding_bars: 24
  min_holding_bars: 0
  action_hysteresis: 0.0
  dd_guard_enabled: false
  max_drawdown: 0.2
  cooloff_bars: 20
  rearm_drawdown: 0.2
```

### 5. Signal Stage
- `feature_stage.apply_signals_to_assets` -> `src.experiments.orchestration.feature_stage.apply_signals_to_assets(asset_frames: 'dict[str, pd.DataFrame]', *, signals_cfg: 'dict[str, Any]') -> 'dict[str, pd.DataFrame]'`
- `feature_stage.apply_signal_step` -> `src.experiments.orchestration.feature_stage.apply_signal_step(df: 'pd.DataFrame', signals_cfg: 'dict[str, Any]', *, asset: 'str | None' = None) -> 'pd.DataFrame'`
- `signal[forecast_threshold]` -> `src.signals.forecast_threshold_signal.forecast_threshold_signal(df: 'pd.DataFrame', forecast_col: 'str' = 'pred_ret', signal_col: 'str | None' = None, upper: 'float' = 0.0, lower: 'float | None' = None, mode: 'str' = 'long_short_hold', activation_filters: 'list[dict[str, object]] | None' = None) -> 'pd.Series'`  
  params={'forecast_col': 'pred_ret', 'signal_col': 'signal_structured_tail', 'upper': 0.7, 'lower': -0.85, 'mode': 'long_short', 'activation_filters': [{'col': 'atr_pct_rank_192', 'op': 'ge', 'value': 0.25}, {'col': 'atr_pct_rank_192', 'op': 'le', 'value': 0.85}, {'col': 'range_to_atr', 'op': 'ge', 'value': 0.8999999999999999}, {'col': 'bollinger_bandwidth_rank_192', 'op': 'ge', 'value': 0.4}]}

```yaml
signals:
  kind: forecast_threshold
  params:
    forecast_col: pred_ret
    signal_col: signal_structured_tail
    upper: 0.7
    lower: -0.85
    mode: long_short
    activation_filters:
    - col: atr_pct_rank_192
      op: ge
      value: 0.25
    - col: atr_pct_rank_192
      op: le
      value: 0.85
    - col: range_to_atr
      op: ge
      value: 0.8999999999999999
    - col: bollinger_bandwidth_rank_192
      op: ge
      value: 0.4
  outputs: {}
```

### 6. Backtest
- `backtest_stage.run_single_asset_backtest` -> `src.experiments.orchestration.backtest_stage.run_single_asset_backtest(asset: 'str', df: 'pd.DataFrame', *, cfg: 'dict[str, Any]', model_meta: 'dict[str, Any]') -> 'BacktestResult'`
- `backtesting.engine.run_backtest` -> `src.backtesting.engine.run_backtest(df: 'pd.DataFrame', signal_col: 'str', returns_col: 'str', returns_type: "Literal['simple', 'log']" = 'simple', missing_return_policy: 'str' = 'raise_if_exposed', cost_per_unit_turnover: 'float' = 0.0, slippage_per_unit_turnover: 'float' = 0.0, target_vol: 'Optional[float]' = None, vol_col: 'Optional[str]' = None, max_leverage: 'float' = 3.0, dd_guard: 'bool' = True, max_drawdown: 'float' = 0.2, cooloff_bars: 'int' = 20, rearm_drawdown: 'Optional[float]' = None, periods_per_year: 'int' = 252, min_holding_bars: 'int' = 0) -> 'BacktestResult'`
- `backtesting.engine.BacktestResult` -> `src.backtesting.engine.BacktestResult(equity_curve: 'pd.Series', returns: 'pd.Series', gross_returns: 'pd.Series', costs: 'pd.Series', positions: 'pd.Series', turnover: 'pd.Series', summary: 'dict', trades: 'pd.DataFrame | None' = None, mark_to_market_returns: 'pd.Series | None' = None, mark_to_market_equity_curve: 'pd.Series | None' = None, mark_to_market_summary: 'dict | None' = None) -> None`

```yaml
backtest:
  engine: vectorized
  returns_col: close_ret
  signal_col: signal_structured_tail
  periods_per_year: 17520
  returns_type: simple
  missing_return_policy: raise_if_exposed
  min_holding_bars: 24
  subset: test
  stop_mode: fixed_return
  vol_col: null
  open_col: open
  high_col: high
  low_col: low
  close_col: close
  take_profit_r: null
  stop_loss_r: null
  volatility_col: null
  entry_price_mode: null
  profit_barrier_r: null
  stop_barrier_r: null
  vertical_barrier_bars: null
  tie_break: null
  event_time_remap_policy: null
  max_cost_r: null
  risk_per_trade: null
  max_holding_bars: null
  asset_params: {}
  dynamic_exits: {}
  partial_exits: {}
  allow_short: true
risk:
  cost_per_turnover: 0.0001
  slippage_per_turnover: 0.0
  target_vol: null
  max_leverage: 1.0
  dd_guard:
    enabled: false
    max_drawdown: 0.2
    cooloff_bars: 20
    rearm_drawdown: 0.2
  portfolio_guard: {}
  sizing: {}
  drawdown_sizing: {}
  vol_col: null
portfolio:
  enabled: false
  construction: signal_weights
  gross_target: 1.0
  long_short: true
  expected_return_col: null
  covariance_window: 60
  covariance_rebalance_step: 1
  risk_aversion: 5.0
  trade_aversion: 0.0
  selection:
    enabled: false
    top_k: 1
    min_expected_net_return: 0.0
    rank_by_abs: true
    weighting: score
    rebalance_every_n_bars: 1
  constraints:
    enforce_target_net_exposure: true
  asset_groups: {}
```

### 7. Monitoring And Execution
- `reporting.compute_monitoring_report` -> `src.experiments.orchestration.reporting.compute_monitoring_report(asset_frames: 'dict[str, pd.DataFrame]', *, model_meta: 'dict[str, Any]', monitoring_cfg: 'dict[str, Any]') -> 'dict[str, Any]'`
- `execution_stage.build_execution_output` -> `src.experiments.orchestration.execution_stage.build_execution_output(*, asset_frames: 'dict[str, pd.DataFrame]', execution_cfg: 'dict[str, object]', portfolio_weights: 'pd.DataFrame | None', performance: 'BacktestResult | PortfolioPerformance', alignment: 'str') -> 'tuple[dict[str, object], pd.DataFrame | None]'`
- `schemas.MonitoringPayload` -> `src.experiments.schemas.MonitoringPayload(asset_count: 'int', drifted_feature_count: 'int', feature_count: 'int', per_asset: 'dict[str, Any]' = <factory>) -> None`
- `schemas.ExecutionPayload` -> `src.experiments.schemas.ExecutionPayload(mode: 'str', capital: 'float', as_of: 'str | None', order_count: 'int', gross_target: 'float', extra: 'dict[str, Any]' = <factory>) -> None`
- `reporting.build_single_asset_evaluation` -> `src.experiments.orchestration.reporting.build_single_asset_evaluation(asset: 'str', df: 'pd.DataFrame', *, performance: 'BacktestResult', model_meta: 'dict[str, Any]', periods_per_year: 'int', backtest_cfg: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'`
- `schemas.EvaluationPayload` -> `src.experiments.schemas.EvaluationPayload(scope: 'str', primary_summary: 'dict[str, Any]', timeline_summary: 'dict[str, Any]', oos_only_summary: 'dict[str, Any] | None' = None, extra: 'dict[str, Any]' = <factory>) -> None`

```yaml
monitoring:
  enabled: true
  psi_threshold: 0.2
  n_bins: 10
execution:
  enabled: false
  mode: paper
  capital: 1000000.0
  price_col: close
  min_trade_notional: 0.0
  hysteresis:
    enabled: false
    entry_threshold: 0.0
    exit_threshold: 0.0
    min_holding_bars: 0
  current_weights: {}
  current_prices: {}
```

### 8. Artifact And Report
- `artifacts.save_artifacts` -> `src.experiments.orchestration.artifacts.save_artifacts(*, run_dir: 'Path', cfg: 'dict[str, Any]', data: 'pd.DataFrame | dict[str, pd.DataFrame]', model: 'object | None' = None, performance: 'BacktestResult | PortfolioPerformance', model_meta: 'dict[str, Any]', evaluation: 'dict[str, Any]', monitoring: 'dict[str, Any]', execution: 'dict[str, Any]', execution_orders: 'pd.DataFrame | None', portfolio_weights: 'pd.DataFrame | None', portfolio_diagnostics: 'pd.DataFrame | None', portfolio_meta: 'dict[str, Any]', storage_meta: 'dict[str, Any]', run_metadata: 'dict[str, Any]', config_hash_sha256: 'str', data_fingerprint: 'dict[str, Any]', stage_tails: 'dict[str, Any] | None' = None) -> 'dict[str, str]'`
- `artifacts.write_experiment_report_from_run_dir` -> `src.experiments.orchestration.artifacts.write_experiment_report_from_run_dir(run_dir: 'Path') -> 'dict[str, str]'`
- `reporting.build_experiment_report_markdown` -> `src.experiments.orchestration.reporting.build_experiment_report_markdown(*, cfg: 'dict[str, Any]', summary_payload: 'dict[str, Any]', run_metadata: 'dict[str, Any]', chart_paths: 'dict[str, str]', artifact_paths: 'dict[str, str]') -> 'str'`

## Primary Summary
| Metric | Value |
| --- | --- |
| cumulative_return | 1.590371 |
| annualized_return | 0.463339 |
| annualized_vol | 0.274350 |
| sharpe | 1.688861 |
| sortino | 2.633944 |
| calmar | 2.286604 |
| max_drawdown | -0.202632 |
| profit_factor | 1.109795 |
| hit_rate | 0.490414 |
| avg_turnover | 0.011324 |
| total_turnover | 496.000000 |
| gross_pnl | 1.094884 |
| net_pnl | 1.045284 |
| total_cost | 0.049600 |
| cost_drag | 0.049600 |
| cost_to_gross_pnl | 0.045302 |
| flat_rate | 0.968242 |
| long_rate | 0.021073 |
| short_rate | 0.010685 |
| trade_count | 248 |
| average_r | 0.487360 |
| median_r | 0.231794 |
| avg_max_favorable_r | 3.367908 |
| avg_max_adverse_r | -3.028808 |
| loser_was_positive_rate | 0.991379 |
| avg_giveback_r | 2.880549 |
| avg_capture_ratio | -2.781681 |
| robustness_walk_forward_positive_fold_ratio | 0.600000 |
| robustness_walk_forward_min_fold_cumulative_return | 0.0 |
| robustness_walk_forward_worst_fold_max_drawdown | -0.202632 |
| robustness_walk_forward_mean_fold_sharpe | 1.010001 |
| robustness_walk_forward_std_fold_sharpe | 1.033063 |
| robustness_cost_x1_cumulative_return | 1.590371 |
| robustness_cost_x1_sharpe | 1.197820 |
| robustness_cost_x1_max_drawdown | -0.202632 |
| robustness_cost_x1_profit_factor | 1.109795 |
| robustness_cost_x2_cumulative_return | 1.465037 |
| robustness_cost_x2_sharpe | 1.128548 |
| robustness_cost_x2_max_drawdown | -0.205336 |
| robustness_cost_x2_profit_factor | 1.104192 |
| robustness_cost_x3_cumulative_return | 1.345755 |
| robustness_cost_x3_sharpe | 1.060047 |
| robustness_cost_x3_max_drawdown | -0.208031 |
| robustness_cost_x3_profit_factor | 1.098625 |
| robustness_cost_x5_cumulative_return | 1.124195 |
| robustness_cost_x5_sharpe | 0.925340 |
| robustness_cost_x5_max_drawdown | -0.216894 |
| robustness_cost_x5_profit_factor | 1.087609 |
| robustness_delay_1_bars_cumulative_return | 1.210055 |
| robustness_delay_1_bars_sharpe | 0.789110 |
| robustness_delay_1_bars_max_drawdown | -0.217106 |
| robustness_delay_1_bars_profit_factor | 1.092800 |
| robustness_delay_2_bars_cumulative_return | 1.275164 |
| robustness_delay_2_bars_sharpe | 0.821095 |
| robustness_delay_2_bars_max_drawdown | -0.193405 |
| robustness_delay_2_bars_profit_factor | 1.096197 |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.031758 |
| signal_turnover | 0.037580 |
| long_rate | 0.021073 |
| short_rate | 0.010685 |
| flat_rate | 0.968242 |
| executed_trade_count | 5984 |
| trade_rate | 0.136621 |
| avg_signal_executed | 0.062166 |
| avg_pred_prob_executed | 0.542498 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.519635 |
| classification.brier | 0.283753 |
| classification.roc_auc | 0.525686 |
| classification.log_loss | 0.788329 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.145172 |
| regression.rmse | 2.600781 |
| regression.mse | 6.764062 |
| regression.r2 | -0.083294 |
| regression.correlation | 0.046614 |
| regression.directional_accuracy | 0.519475 |
| regression.mean_prediction | 0.001392 |
| regression.mean_target | 0.003813 |
| volatility.evaluation_rows | 0 |
| volatility.mae |  |
| volatility.rmse |  |
| volatility.correlation |  |
| volatility.mean_prediction |  |
| volatility.mean_target |  |


## Prediction Diagnostics
| Metric | Value |
| --- | --- |
| oos_rows | 43800 |
| predicted_rows | 43800 |
| non_oos_prediction_rows | 0 |
| missing_oos_prediction_rows | 0 |
| oos_prediction_coverage | 1.000000 |
| alignment_ok | true |
| first_prediction_index | 2022-03-14T15:00:00 |
| last_prediction_index | 2024-09-17T10:30:00 |
| prediction_distribution.rows | 43800 |
| prediction_distribution.mean | 0.001392 |
| prediction_distribution.std | 0.846999 |
| prediction_distribution.min | -4.412574 |
| prediction_distribution.max | 4.545159 |
| prediction_distribution.median | 0.025936 |
| prediction_distribution.q01 | -2.359209 |
| prediction_distribution.q05 | -1.432354 |
| prediction_distribution.q25 | -0.468134 |
| prediction_distribution.q75 | 0.513688 |
| prediction_distribution.q95 | 1.337609 |
| prediction_distribution.q99 | 2.059301 |
| prediction_distribution.skew | -0.212664 |
| prediction_distribution.kurtosis | 1.455285 |
| prediction_distribution.positive_rate | 0.514703 |
| prediction_distribution.negative_rate | 0.485297 |
| prediction_distribution.zero_rate | 0.0 |
| target_distribution.rows | 43800 |
| target_distribution.mean | 0.003813 |
| target_distribution.std | 2.498824 |
| target_distribution.min | -4.000000 |
| target_distribution.max | 4.000000 |
| target_distribution.median | -0.015923 |
| target_distribution.q01 | -4.000000 |
| target_distribution.q05 | -4.000000 |
| target_distribution.q25 | -1.825757 |
| target_distribution.q75 | 1.873421 |
| target_distribution.q95 | 4.000000 |
| target_distribution.q99 | 4.000000 |
| target_distribution.skew | 0.008876 |
| target_distribution.kurtosis | -0.990125 |
| target_distribution.positive_rate | 0.497032 |
| target_distribution.negative_rate | 0.502671 |
| target_distribution.zero_rate | 0.000297 |
| probability_distribution.rows | 43800 |
| probability_distribution.mean | 0.500074 |
| probability_distribution.std | 0.206019 |
| probability_distribution.min | 0.011337 |
| probability_distribution.max | 0.987819 |
| probability_distribution.median | 0.508539 |
| probability_distribution.q01 | 0.062413 |
| probability_distribution.q05 | 0.140696 |
| probability_distribution.q25 | 0.351371 |
| probability_distribution.q75 | 0.656393 |
| probability_distribution.q95 | 0.825545 |
| probability_distribution.q99 | 0.909510 |
| probability_distribution.skew | -0.133521 |
| probability_distribution.kurtosis | -0.676971 |
| probability_distribution.positive_rate | 1.000000 |
| probability_distribution.negative_rate | 0.0 |
| probability_distribution.zero_rate | 0.0 |


## Dense Forecast Diagnostics
| Artifact | Link |
| --- | --- |
| fold_backtest_diagnostics | [open](artifacts/diagnostics/fold_backtest_diagnostics.csv) |
| forecast_alpha_summary | [open](artifacts/diagnostics/forecast_alpha_diagnostics_summary.json) |
| forecast_baselines | [open](artifacts/diagnostics/forecast_baselines.csv) |
| lab_feature_ETHUSD | [open](artifacts/diagnostics/lab_feature_diagnostics_ETHUSD.json) |
| regime_performance | [open](artifacts/diagnostics/regime_performance.csv) |
| threshold_grid | [open](artifacts/diagnostics/threshold_grid.csv) |


## Forecast Baselines
| Name | Cum Return | Ann Return | Ann Vol | Sharpe | Sortino | Calmar | Max DD | Profit Factor | Hit Rate | Turnover | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| model_strategy | 1.590371 | 0.463339 | 0.274350 | 1.688861 | 2.633944 | 2.286604 | -0.202632 | 1.109795 | 0.490414 | 496.000000 | 0.045302 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | -0.089284 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000224 |
| random_sign_same_rate | -0.325502 | -0.145736 | 0.373902 | -0.389769 | -0.537872 | -0.265938 | -0.548007 | 0.989432 | 0.477615 | 1.146e+03 | 1.102203 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | -0.240522 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.789225 |
| simple_trend | -0.867002 | -0.553792 | 0.665797 | -0.831772 | -1.181822 | -0.608132 | -0.910644 | 0.978047 | 0.491683 | 1.545e+03 | 0.118038 |


## Threshold Grid
| Name | Upper | Lower | Net PnL | Sharpe | Max DD | Profit Factor | Cost/Gross | Turnover | Active Rows | Profitable Folds | Median Fold Return | Worst 3-Fold Avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sym_0.35 | 0.350000 | -0.350000 | 1.138408 | 0.680297 | -0.582206 | 1.028060 | 0.131867 | 1.673e+03 | 2.741e+04 | 5.000000 | 0.089971 | -0.178053 |
| sym_0.5 | 0.500000 | -0.500000 | 0.300603 | 0.230078 | -0.454424 | 1.016150 | 0.218068 | 1.542e+03 | 2.157e+04 | 5.000000 | -0.013066 | -0.130734 |
| sym_0.75 | 0.750000 | -0.750000 | 0.268837 | 0.230255 | -0.480105 | 1.017181 | 0.215429 | 1.300e+03 | 1.394e+04 | 4.000000 | -0.004845 | -0.122006 |
| sym_1 | 1.000000 | -1.000000 | 3.175521 | 2.014120 | -0.271727 | 1.080774 | 0.058191 | 996.000000 | 8.851e+03 | 8.000000 | 0.154651 | -0.006193 |
| sym_1.25 | 1.250000 | -1.250000 | 0.501518 | 0.539090 | -0.364605 | 1.036450 | 0.123368 | 760.000000 | 5.600e+03 | 7.000000 | 0.056841 | -0.119574 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.058967 |
| mean_fold_return | 0.109540 |
| fold_return_std | 0.158815 |
| worst_fold_return | -0.103905 |
| best_fold_return | 0.362606 |
| worst_3_fold_average_return | -0.059073 |
| profitable_fold_count | 8.000000 |
| profitable_fold_rate | 0.800000 |
| median_fold_sharpe | 1.627973 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 2.8, 'best_rank': 1, 'mean_importance': 0.040219861268997195, 'mean_importance_normalized': 0.040219862892846014, 'folds': [{'fold': 0, 'rank': 1, 'importance': 0.04296223446726799, 'importance_normalized': 0.042962235867677494}, {'fold': 1, 'rank': 1, 'importance': 0.04235547408461571, 'importance_normalized': 0.04235548406461018}, {'fold': 2, 'rank': 4, 'importance': 0.03907858952879906, 'importance_normalized': 0.039078584014991785}, {'fold': 3, 'rank': 3, 'importance': 0.03982190042734146, 'importance_normalized': 0.039821904599633313}, {'fold': 4, 'rank': 1, 'importance': 0.04096860811114311, 'importance_normalized': 0.04096861246081239}, {'fold': 5, 'rank': 3, 'importance': 0.041335318237543106, 'importance_normalized': 0.04133531687091687}, {'fold': 6, 'rank': 4, 'importance': 0.0400761142373085, 'importance_normalized': 0.0400761142559704}, {'fold': 7, 'rank': 1, 'importance': 0.03980051726102829, 'importance_normalized': 0.039800520356133066}, {'fold': 8, 'rank': 5, 'importance': 0.03788132220506668, 'importance_normalized': 0.03788132541552243}, {'fold': 9, 'rank': 5, 'importance': 0.03791853412985802, 'importance_normalized': 0.03791853102219223}], 'stability_rank': 1}, {'feature': 'atr_pct', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 2.9, 'best_rank': 1, 'mean_importance': 0.04060510098934174, 'mean_importance_normalized': 0.040605102507512356, 'folds': [{'fold': 0, 'rank': 2, 'importance': 0.04291241243481636, 'importance_normalized': 0.04291241383360185}, {'fold': 1, 'rank': 5, 'importance': 0.03899122402071953, 'importance_normalized': 0.0389912332080137}, {'fold': 2, 'rank': 1, 'importance': 0.04288864880800247, 'importance_normalized': 0.042888642756613554}, {'fold': 3, 'rank': 1, 'importance': 0.043306510895490646, 'importance_normalized': 0.04330651543287838}, {'fold': 4, 'rank': 4, 'importance': 0.038976024836301804, 'importance_normalized': 0.038976028974416946}, {'fold': 5, 'rank': 6, 'importance': 0.03807659074664116, 'importance_normalized': 0.03807658948775481}, {'fold': 6, 'rank': 1, 'importance': 0.04214651510119438, 'importance_normalized': 0.042146515120820384}, {'fold': 7, 'rank': 6, 'importance': 0.03745546191930771, 'importance_normalized': 0.03745546483204822}, {'fold': 8, 'rank': 1, 'importance': 0.0417553074657917, 'importance_normalized': 0.041755311004569105}, {'fold': 9, 'rank': 2, 'importance': 0.039542313665151596, 'importance_normalized': 0.039542310424406715}], 'stability_rank': 2}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 3.1, 'best_rank': 1, 'mean_importance': 0.03972898609936237, 'mean_importance_normalized': 0.03972898757991248, 'folds': [{'fold': 0, 'rank': 10, 'importance': 0.03608428314328194, 'importance_normalized': 0.03608428431949574}, {'fold': 1, 'rank': 3, 'importance': 0.03933831676840782, 'importance_normalized': 0.039338326037485605}, {'fold': 2, 'rank': 2, 'importance': 0.040103983134031296, 'importance_normalized': 0.040103977475545755}, {'fold': 3, 'rank': 2, 'importance': 0.03990783542394638, 'importance_normalized': 0.039907839605241975}, {'fold': 4, 'rank': 3, 'importance': 0.03969283774495125, 'importance_normalized': 0.03969284195917098}, {'fold': 5, 'rank': 2, 'importance': 0.041670557111501694, 'importance_normalized': 0.0416705557337918}, {'fold': 6, 'rank': 2, 'importance': 0.04070175439119339, 'importance_normalized': 0.040701754410146625}, {'fold': 7, 'rank': 3, 'importance': 0.039056096225976944, 'importance_normalized': 0.03905609926319149}, {'fold': 8, 'rank': 3, 'importance': 0.0393589623272419, 'importance_normalized': 0.03935896566292818}, {'fold': 9, 'rank': 1, 'importance': 0.041375234723091125, 'importance_normalized': 0.04137523133212667}], 'stability_rank': 3}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.0, 'best_rank': 2, 'mean_importance': 0.03921270743012428, 'mean_importance_normalized': 0.03921270895296833, 'folds': [{'fold': 0, 'rank': 4, 'importance': 0.0386936292052269, 'importance_normalized': 0.0386936304664957}, {'fold': 1, 'rank': 6, 'importance': 0.038936369121074677, 'importance_normalized': 0.038936378295443684}, {'fold': 2, 'rank': 6, 'importance': 0.03815734386444092, 'importance_normalized': 0.03815733848061712}, {'fold': 3, 'rank': 4, 'importance': 0.03903202712535858, 'importance_normalized': 0.03903203121489241}, {'fold': 4, 'rank': 6, 'importance': 0.03799150139093399, 'importance_normalized': 0.03799150542452151}, {'fold': 5, 'rank': 4, 'importance': 0.03869222477078438, 'importance_normalized': 0.03869222349154396}, {'fold': 6, 'rank': 3, 'importance': 0.04054999351501465, 'importance_normalized': 0.04054999353389721}, {'fold': 7, 'rank': 2, 'importance': 0.039668694138526917, 'importance_normalized': 0.039668697223380414}, {'fold': 8, 'rank': 2, 'importance': 0.04090258106589317, 'importance_normalized': 0.040902584532401705}, {'fold': 9, 'rank': 3, 'importance': 0.03950271010398865, 'importance_normalized': 0.03950270686648953}], 'stability_rank': 4}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 5.1, 'best_rank': 2, 'mean_importance': 0.03821797408163548, 'mean_importance_normalized': 0.03821797556055038, 'folds': [{'fold': 0, 'rank': 5, 'importance': 0.03832235559821129, 'importance_normalized': 0.03832235684737795}, {'fold': 1, 'rank': 2, 'importance': 0.039561349898576736, 'importance_normalized': 0.03956135922020663}, {'fold': 2, 'rank': 3, 'importance': 0.03926846385002136, 'importance_normalized': 0.03926845830942371}, {'fold': 3, 'rank': 6, 'importance': 0.03813481703400612, 'importance_normalized': 0.03813482102953584}, {'fold': 4, 'rank': 8, 'importance': 0.03665243089199066, 'importance_normalized': 0.03665243478340802}, {'fold': 5, 'rank': 9, 'importance': 0.037350963801145554, 'importance_normalized': 0.03735096256624985}, {'fold': 6, 'rank': 6, 'importance': 0.036635491997003555, 'importance_normalized': 0.036635492014063284}, {'fold': 7, 'rank': 4, 'importance': 0.038839615881443024, 'importance_normalized': 0.03883961890182288}, {'fold': 8, 'rank': 4, 'importance': 0.03847505524754524, 'importance_normalized': 0.03847505850832008}, {'fold': 9, 'rank': 4, 'importance': 0.03893919661641121, 'importance_normalized': 0.03893919342509562}], 'stability_rank': 5}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.2, 'best_rank': 3, 'mean_importance': 0.03774200864136219, 'mean_importance_normalized': 0.03774201014149493, 'folds': [{'fold': 0, 'rank': 3, 'importance': 0.03902268782258034, 'importance_normalized': 0.03902268909457523}, {'fold': 1, 'rank': 4, 'importance': 0.03905044123530388, 'importance_normalized': 0.03905045043655109}, {'fold': 2, 'rank': 7, 'importance': 0.038040317595005035, 'importance_normalized': 0.03804031222769311}, {'fold': 3, 'rank': 5, 'importance': 0.038981348276138306, 'importance_normalized': 0.03898135236036232}, {'fold': 4, 'rank': 5, 'importance': 0.038344819098711014, 'importance_normalized': 0.03834482316981055}, {'fold': 5, 'rank': 10, 'importance': 0.03672466427087784, 'importance_normalized': 0.03672466305668881}, {'fold': 6, 'rank': 5, 'importance': 0.03666999191045761, 'importance_normalized': 0.03666999192753341}, {'fold': 7, 'rank': 7, 'importance': 0.037275902926921844, 'importance_normalized': 0.037275905825698875}, {'fold': 8, 'rank': 8, 'importance': 0.036271028220653534, 'importance_normalized': 0.03627103129463629}, {'fold': 9, 'rank': 8, 'importance': 0.037038885056972504, 'importance_normalized': 0.03703888202139957}], 'stability_rank': 6}, {'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.6, 'best_rank': 5, 'mean_importance': 0.037580748274922374, 'mean_importance_normalized': 0.03758074972394053, 'folds': [{'fold': 0, 'rank': 6, 'importance': 0.03824995085597038, 'importance_normalized': 0.038249952102776916}, {'fold': 1, 'rank': 7, 'importance': 0.0387478768825531, 'importance_normalized': 0.038747886012508684}, {'fold': 2, 'rank': 5, 'importance': 0.038495536893606186, 'importance_normalized': 0.03849553146206493}, {'fold': 3, 'rank': 7, 'importance': 0.038107726722955704, 'importance_normalized': 0.03810773071564707}, {'fold': 4, 'rank': 7, 'importance': 0.03698228299617767, 'importance_normalized': 0.03698228692261568}, {'fold': 5, 'rank': 5, 'importance': 0.038157012313604355, 'importance_normalized': 0.03815701105205911}, {'fold': 6, 'rank': 7, 'importance': 0.036563582718372345, 'importance_normalized': 0.03656358273539859}, {'fold': 7, 'rank': 8, 'importance': 0.036589980125427246, 'importance_normalized': 0.03658998297086319}, {'fold': 8, 'rank': 7, 'importance': 0.036486826837062836, 'importance_normalized': 0.0364868299293346}, {'fold': 9, 'rank': 7, 'importance': 0.03742670640349388, 'importance_normalized': 0.03742670333613651}], 'stability_rank': 7}, {'feature': 'ema_alignment_score', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 8.1, 'best_rank': 1, 'mean_importance': 0.036631565541028976, 'mean_importance_normalized': 0.03663156691420547, 'folds': [{'fold': 0, 'rank': 9, 'importance': 0.03734000027179718, 'importance_normalized': 0.0373400014889427}, {'fold': 1, 'rank': 13, 'importance': 0.03402990475296974, 'importance_normalized': 0.034029912771254715}, {'fold': 2, 'rank': 14, 'importance': 0.032529670745134354, 'importance_normalized': 0.03252966615534907}, {'fold': 3, 'rank': 8, 'importance': 0.034701500087976456, 'importance_normalized': 0.034701503723784506}, {'fold': 4, 'rank': 2, 'importance': 0.04044667258858681, 'importance_normalized': 0.04044667688284178}, {'fold': 5, 'rank': 1, 'importance': 0.044381994754076004, 'importance_normalized': 0.0443819932867207}, {'fold': 6, 'rank': 8, 'importance': 0.03468998149037361, 'importance_normalized': 0.03468998150652739}, {'fold': 7, 'rank': 5, 'importance': 0.03870527818799019, 'importance_normalized': 0.038705281197923214}, {'fold': 8, 'rank': 15, 'importance': 0.03174753114581108, 'importance_normalized': 0.03174753383642582}, {'fold': 9, 'rank': 6, 'importance': 0.03774312138557434, 'importance_normalized': 0.03774311829228475}], 'stability_rank': 8}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 9.6, 'best_rank': 8, 'mean_importance': 0.03529081977903843, 'mean_importance_normalized': 0.03529082112475622, 'folds': [{'fold': 0, 'rank': 8, 'importance': 0.03754429519176483, 'importance_normalized': 0.03754429641556961}, {'fold': 1, 'rank': 10, 'importance': 0.03572699800133705, 'importance_normalized': 0.03572700641949905}, {'fold': 2, 'rank': 9, 'importance': 0.03523532673716545, 'importance_normalized': 0.03523532176562469}, {'fold': 3, 'rank': 11, 'importance': 0.03343886137008667, 'importance_normalized': 0.033438864873603265}, {'fold': 4, 'rank': 10, 'importance': 0.03504868224263191, 'importance_normalized': 0.03504868596377801}, {'fold': 5, 'rank': 8, 'importance': 0.03764541819691658, 'importance_normalized': 0.03764541695228563}, {'fold': 6, 'rank': 9, 'importance': 0.034335657954216, 'importance_normalized': 0.03433565797020479}, {'fold': 7, 'rank': 10, 'importance': 0.034478556364774704, 'importance_normalized': 0.034478559046014844}, {'fold': 8, 'rank': 9, 'importance': 0.034801967442035675, 'importance_normalized': 0.034801970391514996}, {'fold': 9, 'rank': 12, 'importance': 0.034652434289455414, 'importance_normalized': 0.03465243144946735}], 'stability_rank': 9}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 11.3, 'best_rank': 8, 'mean_importance': 0.0343750424683094, 'mean_importance_normalized': 0.034375043813945946, 'folds': [{'fold': 0, 'rank': 13, 'importance': 0.03482967987656593, 'importance_normalized': 0.03482968101188432}, {'fold': 1, 'rank': 8, 'importance': 0.03634137287735939, 'importance_normalized': 0.03634138144028327}, {'fold': 2, 'rank': 8, 'importance': 0.035519953817129135, 'importance_normalized': 0.035519948805428816}, {'fold': 3, 'rank': 14, 'importance': 0.032448913902044296, 'importance_normalized': 0.03244891730184033}, {'fold': 4, 'rank': 11, 'importance': 0.03461804240942001, 'importance_normalized': 0.03461804608484474}, {'fold': 5, 'rank': 11, 'importance': 0.035079240798950195, 'importance_normalized': 0.03507923963916208}, {'fold': 6, 'rank': 11, 'importance': 0.033541541546583176, 'importance_normalized': 0.033541541562202175}, {'fold': 7, 'rank': 9, 'importance': 0.035128895193338394, 'importance_normalized': 0.03512889792515242}, {'fold': 8, 'rank': 13, 'importance': 0.03320787474513054, 'importance_normalized': 0.03320787755950993}, {'fold': 9, 'rank': 15, 'importance': 0.03303490951657295, 'importance_normalized': 0.03303490680915136}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.338922 | 0.872769 | -0.196878 | 1.049033 | 0.102332 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.093224 | 0.419924 | -0.200686 | 1.049639 | 0.103144 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 1.599063 | 3.316927 | -0.191733 | 1.132836 | 0.037624 |
| ema_trend_48_192 | negative | 2.183e+04 | 0.876764 | 2.099251 | -0.154320 | 1.127948 | 0.036842 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.412706 | 1.325895 | -0.264414 | 1.083850 | 0.063377 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 0.375893 | 0.715388 | -0.348238 | 1.041276 | 0.080599 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 248 |
| average_r | 0.487360 |
| median_r | 0.231794 |
| avg_max_favorable_r | 3.367908 |
| avg_max_adverse_r | -3.028808 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.991379 |
| avg_giveback_r | 2.880549 |
| avg_capture_ratio | -2.781681 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.991379 |
| avg_mfe_r_of_losers | 1.383740 |
| median_mfe_r_of_losers | 1.087010 |
| avg_mfe_r_before_loss | 1.383740 |
| median_mfe_r_before_loss | 1.087010 |
| loser_reached_0_5r_rate | 0.767241 |
| loser_reached_1r_rate | 0.560345 |
| loser_reached_1_5r_rate | 0.344828 |
| loser_reached_2r_rate | 0.232759 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -2.781681 |
| median_capture_ratio | 0.117931 |
| avg_giveback_r | 2.880549 |
| median_giveback_r | 2.149930 |
| avg_giveback_r_winners | 1.904835 |
| avg_giveback_r_losers | 3.990843 |
| median_giveback_r_winners | 1.632362 |
| median_giveback_r_losers | 3.125634 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 1.000000 |
| winner_had_mae_below_minus_0_25r_rate | 0.856061 |
| winner_had_mae_below_minus_0_5r_rate | 0.750000 |
| winner_had_mae_below_minus_1r_rate | 0.560606 |
| avg_mae_r_of_winners | -1.400784 |
| median_mae_r_of_winners | -1.090174 |
| p90_abs_mae_r_of_winners | 2.763924 |
| avg_mae_r | -3.028808 |
| median_mae_r | -2.135054 |
| q10_mae_r | -6.695847 |
| q25_mae_r | -3.877364 |
| q75_mae_r | -1.037236 |
| q90_mae_r | -0.351493 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.532258 |
| prob_final_loss | 0.467742 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 1.000000 |
| prob_mfe_ge_0_5r | 0.891129 |
| prob_final_loss_given_mfe_ge_0_5r | 0.402715 |
| prob_mfe_ge_1r | 0.790323 |
| prob_final_loss_given_mfe_ge_1r | 0.331633 |
| prob_mfe_ge_1_5r | 0.657258 |
| prob_final_loss_given_mfe_ge_1_5r | 0.245399 |
| prob_mfe_ge_2r | 0.568548 |
| prob_final_loss_given_mfe_ge_2r | 0.191489 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 11.798387 |
| median_time_to_mfe | 11.000000 |
| avg_time_to_mae | 10.044355 |
| median_time_to_mae | 9.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.072581 |
| prob_mfe_ge_0_5r_within_2_bars | 0.120968 |
| prob_mfe_ge_1r_within_4_bars | 0.120968 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.487360 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.532258 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 248 |
| counterfactual.baseline.avg_r | 0.487360 |
| counterfactual.baseline.median_r | 0.231794 |
| counterfactual.baseline.win_rate | 0.532258 |
| counterfactual.baseline.profit_factor | 1.399655 |
| counterfactual.breakeven_after_0_5r.trade_count | 248 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.108385 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.008065 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.137877 |
| counterfactual.breakeven_after_1_0r.trade_count | 248 |
| counterfactual.breakeven_after_1_0r.avg_r | -0.100239 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.096774 |
| counterfactual.breakeven_after_1_0r.profit_factor | 0.762332 |
| counterfactual.exit_at_first_0_5r.trade_count | 248 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.354120 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.959677 |
| counterfactual.exit_at_first_0_5r.profit_factor | 3.816770 |
| counterfactual.exit_at_first_1_0r.trade_count | 248 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.431443 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.854839 |
| counterfactual.exit_at_first_1_0r.profit_factor | 2.022957 |
| counterfactual.partial_50pct_at_1r.trade_count | 248 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.459401 |
| counterfactual.partial_50pct_at_1r.median_r | 0.611904 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.657258 |
| counterfactual.partial_50pct_at_1r.profit_factor | 1.661953 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 248 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.445784 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.118202 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.508065 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.365866 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 248 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.608487 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.839143 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.854839 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 2.442729 |
| counterfactual.best_policy_by_avg_r | trail_0_5r_after_1_0r |
| counterfactual.best_policy_by_profit_factor | exit_at_first_0_5r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 245 | 0.410970 | 0.216274 | 0.526531 | 3.309667 | -3.048891 | 2.898697 | 24.130612 | 1.332936 | 0.995918 | 0.889796 | 0.787755 |
| reversal | 3 | 6.725809 | 4.370889 | 1.000000 | 8.124275 | -1.388678 | 1.398466 | 24.000000 | inf | 1.000000 | 1.000000 | 1.000000 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 0 |
| gross_pnl | 1.094884 |
| net_pnl | 1.045284 |
| total_cost | 0.049600 |
| cost_to_gross_pnl | 0.045302 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1391 |
| actual_trade_count | 0 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 1.590371 |
| sharpe | 1.688861 |
| sortino | 2.633944 |
| calmar | 2.286604 |
| max_drawdown | -0.202632 |
| profit_factor | 1.109795 |
| hit_rate | 0.490414 |
| gross_pnl | 1.094884 |
| net_pnl | 1.045284 |
| total_cost | 0.049600 |
| cost_to_gross_pnl | 0.045302 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 1.590371 |
| cost_x1.annualized_return | 0.252889 |
| cost_x1.annualized_vol | 0.211124 |
| cost_x1.sharpe | 1.197820 |
| cost_x1.max_drawdown | -0.202632 |
| cost_x1.profit_factor | 1.109795 |
| cost_x1.hit_rate | 0.490414 |
| cost_x2.cumulative_return | 1.465037 |
| cost_x2.annualized_return | 0.238257 |
| cost_x2.annualized_vol | 0.211118 |
| cost_x2.sharpe | 1.128548 |
| cost_x2.max_drawdown | -0.205336 |
| cost_x2.profit_factor | 1.104192 |
| cost_x2.hit_rate | 0.489609 |
| cost_x3.cumulative_return | 1.345755 |
| cost_x3.annualized_return | 0.223794 |
| cost_x3.annualized_vol | 0.211117 |
| cost_x3.sharpe | 1.060047 |
| cost_x3.max_drawdown | -0.208031 |
| cost_x3.profit_factor | 1.098625 |
| cost_x3.hit_rate | 0.488964 |
| cost_x5.cumulative_return | 1.124195 |
| cost_x5.annualized_return | 0.195369 |
| cost_x5.annualized_vol | 0.211133 |
| cost_x5.sharpe | 0.925340 |
| cost_x5.max_drawdown | -0.216894 |
| cost_x5.profit_factor | 1.087609 |
| cost_x5.hit_rate | 0.488159 |

### Entry Delay
| Metric | Value |
| --- | --- |
| delay_1_bars.cumulative_return | 1.210055 |
| delay_1_bars.annualized_return | 0.135938 |
| delay_1_bars.annualized_vol | 0.172268 |
| delay_1_bars.sharpe | 0.789110 |
| delay_1_bars.max_drawdown | -0.217106 |
| delay_1_bars.profit_factor | 1.092800 |
| delay_1_bars.hit_rate | 0.488796 |
| delay_2_bars.cumulative_return | 1.275164 |
| delay_2_bars.annualized_return | 0.141252 |
| delay_2_bars.annualized_vol | 0.172029 |
| delay_2_bars.sharpe | 0.821095 |
| delay_2_bars.max_drawdown | -0.193405 |
| delay_2_bars.profit_factor | 1.096197 |
| delay_2_bars.hit_rate | 0.487109 |

### Walk Forward
| Metric | Value |
| --- | --- |
| fold_count | 5 |
| positive_fold_count | 3 |
| positive_fold_ratio | 0.600000 |
| min_fold_cumulative_return | 0.0 |
| median_fold_cumulative_return | 0.100246 |
| mean_fold_cumulative_return | 0.235443 |
| mean_fold_sharpe | 1.010001 |
| std_fold_sharpe | 1.033063 |
| worst_fold_max_drawdown | -0.202632 |

### Gap Stress
| Metric | Value |
| --- | --- |
| enabled | false |
| reason | gap_loss_per_exposure <= 0 |


## Target Diagnostics
| Metric | Value |
| --- | --- |
| kind | future_return_regression |
| labeled_rows | 108981 |
| unavailable_tail_count | 24 |


## Target Distribution
| Metric | Value |
| --- | --- |
| oos_direction.labeled_rows | 43800 |
| oos_direction.class_counts.0 | 22030 |
| oos_direction.class_counts.1 | 21770 |
| oos_direction.positive_rate | 0.497032 |
| oos_direction.negative_rate | 0.502968 |
| oos_prediction.rows | 43800 |
| oos_prediction.mean | 0.001392 |
| oos_prediction.std | 0.846999 |
| oos_prediction.min | -4.412574 |
| oos_prediction.max | 4.545159 |
| oos_prediction.median | 0.025936 |
| oos_prediction.q01 | -2.359209 |
| oos_prediction.q05 | -1.432354 |
| oos_prediction.q25 | -0.468134 |
| oos_prediction.q75 | 0.513688 |
| oos_prediction.q95 | 1.337609 |
| oos_prediction.q99 | 2.059301 |
| oos_prediction.skew | -0.212664 |
| oos_prediction.kurtosis | 1.455285 |
| oos_prediction.positive_rate | 0.514703 |
| oos_prediction.negative_rate | 0.485297 |
| oos_prediction.zero_rate | 0.0 |
| oos_target.rows | 43800 |
| oos_target.mean | 0.003813 |
| oos_target.std | 2.498824 |
| oos_target.min | -4.000000 |
| oos_target.max | 4.000000 |
| oos_target.median | -0.015923 |
| oos_target.q01 | -4.000000 |
| oos_target.q05 | -4.000000 |
| oos_target.q25 | -1.825757 |
| oos_target.q75 | 1.873421 |
| oos_target.q95 | 4.000000 |
| oos_target.q99 | 4.000000 |
| oos_target.skew | 0.008876 |
| oos_target.kurtosis | -0.990125 |
| oos_target.positive_rate | 0.497032 |
| oos_target.negative_rate | 0.502671 |
| oos_target.zero_rate | 0.000297 |


## Feature Importance
| Rank | Feature | Mean Importance | Mean Importance Normalized | Fold Count | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | atr_pct | 0.040605 | 0.040605 | 10 | feature_importances_ |
| 2 | bollinger_bandwidth | 0.040220 | 0.040220 | 10 | feature_importances_ |
| 3 | ema_trend_48_192 | 0.039729 | 0.039729 | 10 | feature_importances_ |
| 4 | vol_rolling_192 | 0.039213 | 0.039213 | 10 | feature_importances_ |
| 5 | vol_rolling_96 | 0.038218 | 0.038218 | 10 | feature_importances_ |
| 6 | atr_over_price_48 | 0.037742 | 0.037742 | 10 | feature_importances_ |
| 7 | atr_48 | 0.037581 | 0.037581 | 10 | feature_importances_ |
| 8 | ema_alignment_score | 0.036632 | 0.036632 | 10 | feature_importances_ |
| 9 | vol_rolling_48 | 0.035291 | 0.035291 | 10 | feature_importances_ |
| 10 | bollinger_bandwidth_rank_192 | 0.034375 | 0.034375 | 10 | feature_importances_ |
| 11 | close_over_bb_upper_192 | 0.034248 | 0.034248 | 10 | feature_importances_ |
| 12 | atr_pct_rank_192 | 0.034026 | 0.034026 | 10 | feature_importances_ |
| 13 | ret_48 | 0.033144 | 0.033144 | 10 | feature_importances_ |
| 14 | vol_rolling_24 | 0.031972 | 0.031972 | 10 | feature_importances_ |
| 15 | close_over_bb_mid_192 | 0.031438 | 0.031438 | 10 | feature_importances_ |
| 16 | distance_from_ema96_atr | 0.031019 | 0.031019 | 10 | feature_importances_ |
| 17 | bollinger_percent_b | 0.030133 | 0.030133 | 10 | feature_importances_ |
| 18 | mama_minus_fama_over_atr | 0.030047 | 0.030047 | 10 | feature_importances_ |
| 19 | rolling_return_48 | 0.029913 | 0.029913 | 10 | feature_importances_ |
| 20 | ret_24 | 0.028441 | 0.028441 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 1.094884 |
| net_pnl | 1.045284 |
| total_cost | 0.049600 |
| cost_drag | 0.049600 |
| cost_to_gross_pnl | 0.045302 |
| avg_turnover | 0.011324 |
| total_turnover | 496.000000 |
| mean_abs_signal | 0.031758 |
| signal_turnover | 0.037580 |
| flat_rate | 0.968242 |
| long_rate | 0.021073 |
| short_rate | 0.010685 |
| trade_rate | 0.136621 |
| executed_trade_count | 5984 |
| avg_signal_executed | 0.062166 |
| avg_pred_prob_executed | 0.542498 |
| avg_realized_r_executed |  |

## Diagnostics
- Fold outcomes are mixed, which points to regime dependence rather than a stable cross-period edge.
- Feature drift is present in OOS inputs; the largest drifted features are atr_48, atr_over_price_48, atr_pct, vol_rolling_192, vol_rolling_96.

## Charts
### Equity Curve Chart
![Equity Curve Chart](report_assets/equity_curve.png)

### Drawdown Curve
![Drawdown Curve](report_assets/drawdown_curve.png)

### Cumulative Returns
![Cumulative Returns](report_assets/cumulative_returns.png)

### Monthly Returns
![Monthly Returns](report_assets/monthly_returns.png)

### Rolling Pnl
![Rolling Pnl](report_assets/rolling_pnl.png)

### Cumulative Cost Drag
![Cumulative Cost Drag](report_assets/cumulative_cost_drag.png)

### Positions Turnover
![Positions Turnover](report_assets/positions_turnover.png)

### Rolling Behavior
![Rolling Behavior](report_assets/rolling_behavior.png)

### Signal Distribution
![Signal Distribution](report_assets/signal_distribution.png)

### Fold Net Pnl
![Fold Net Pnl](report_assets/fold_net_pnl.png)

### Feature Importance Chart
![Feature Importance Chart](report_assets/feature_importance.png)

### Prediction Coverage By Fold
![Prediction Coverage By Fold](report_assets/prediction_coverage_by_fold.png)


## Fold Breakdown
| Fold | Rows | Gross PnL | Net PnL | Cost | Sharpe | Avg Turnover | Mean Reward | Mean Abs Signal | Signal Turnover | Flat Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 |  | 0.025242 | 0.019442 | 0.005800 | 0.108226 | 0.013242 |  |  |  |  |
| 1 |  | 0.211672 | 0.205672 | 0.006000 | 2.083724 | 0.013699 |  |  |  |  |
| 2 |  | 0.332459 | 0.326059 | 0.006400 | 6.661125 | 0.014612 |  |  |  |  |
| 3 |  | 0.229779 | 0.222979 | 0.006800 | 5.177786 | 0.015525 |  |  |  |  |
| 4 |  | 0.062132 | 0.057032 | 0.005100 | 1.539487 | 0.011644 |  |  |  |  |
| 5 |  | -0.102419 | -0.107419 | 0.005000 | -2.629907 | 0.011416 |  |  |  |  |
| 6 |  | -0.077102 | -0.081902 | 0.004800 | -1.865413 | 0.010959 |  |  |  |  |
| 7 |  | 0.066795 | 0.063795 | 0.003000 | 1.716459 | 0.006849 |  |  |  |  |
| 8 |  | 0.061969 | 0.058569 | 0.003400 | 1.085912 | 0.007763 |  |  |  |  |
| 9 |  | 0.280247 | 0.277047 | 0.003200 | 6.814345 | 0.007306 |  |  |  |  |


## Model Fold Diagnostics
| Fold | Train Raw | Train Used | Train Missing Features | Train Not Labeled | Train Without Fit | Test Rows | Pred Rows | Test Missing Features | Test Not Candidates | Test Without Prediction | Train Feature Missing | Test Feature Missing | Eval Rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 35016 | 35016 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 1 | 39396 | 39396 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 2 | 43752 | 43752 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 3 | 48108 | 48108 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 4 | 52464 | 52464 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 5 | 56820 | 56820 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 6 | 61176 | 61176 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 7 | 65532 | 65532 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 8 | 69888 | 69888 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 9 | 74244 | 74244 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |


## Monitoring
- Drifted feature count: `8` / `46`
| Asset | Feature | PSI |
| --- | --- | --- |
| ETHUSD | atr_48 | 1.195042 |
| ETHUSD | atr_over_price_48 | 0.665754 |
| ETHUSD | atr_pct | 0.665754 |
| ETHUSD | vol_rolling_192 | 0.612124 |
| ETHUSD | vol_rolling_96 | 0.551451 |
| ETHUSD | vol_rolling_48 | 0.474270 |
| ETHUSD | vol_rolling_24 | 0.406533 |
| ETHUSD | bollinger_bandwidth | 0.358901 |


## Drift By Family
| Family | Feature Count | Drifted Count | Drifted Ratio | Mean Abs PSI | Max Abs PSI |
| --- | --- | --- | --- | --- | --- |
| unclassified | 33 | 3 | 0.090909 | 0.109666 | 1.195042 |
| atr_adx_range | 1 | 1 | 1.000000 | 0.665754 | 0.665754 |
| volatility | 4 | 4 | 1.000000 | 0.511094 | 0.612124 |
| returns_lags | 8 | 0 | 0.0 | 0.118134 | 0.118186 |


## Feature Set
| Order | Feature |
| --- | --- |
| 1 | close_ret |
| 2 | lag_close_ret_1 |
| 3 | lag_close_ret_2 |
| 4 | lag_close_ret_4 |
| 5 | lag_close_ret_8 |
| 6 | lag_close_ret_16 |
| 7 | lag_close_ret_24 |
| 8 | lag_close_ret_48 |
| 9 | ret_1 |
| 10 | ret_4 |
| 11 | ret_8 |
| 12 | ret_16 |
| 13 | ret_24 |
| 14 | ret_48 |
| 15 | rolling_return_24 |
| 16 | rolling_return_48 |
| 17 | vol_rolling_24 |
| 18 | vol_rolling_48 |
| 19 | vol_rolling_96 |
| 20 | vol_rolling_192 |
| 21 | atr_48 |
| 22 | atr_over_price_48 |
| 23 | atr_pct |
| 24 | atr_pct_rank_192 |
| 25 | ema_trend_48_192 |
| 26 | close_over_bb_upper_192 |
| 27 | close_over_bb_mid_192 |
| 28 | bollinger_percent_b |
| 29 | bollinger_bandwidth |
| 30 | bollinger_bandwidth_rank_192 |
| 31 | ema_alignment_score |
| 32 | distance_from_ema24_atr |
| 33 | distance_from_ema96_atr |
| 34 | mama_minus_fama_over_atr |
| 35 | close_minus_decycler_over_atr |
| 36 | instantaneous_trendline_slope_over_atr |
| 37 | decycler_slope_over_atr |
| 38 | frama_slope_over_atr |
| 39 | supersmoother_slope_over_atr |
| 40 | roofing_filter_over_atr |
| 41 | dominant_cycle_phase_normalized |
| 42 | body_ratio |
| 43 | upper_wick_ratio |
| 44 | lower_wick_ratio |
| 45 | close_location |
| 46 | range_to_atr |

## Feature Steps
```yaml
- step: returns
  params:
    log: false
    col_name: close_ret
  outputs: {}
  enabled: true
  transforms:
    lag:
      enabled: true
      items:
      - source_col: close_ret
        lag: 1
        output_col: lag_close_ret_1
      - source_col: close_ret
        lag: 2
        output_col: lag_close_ret_2
      - source_col: close_ret
        lag: 4
        output_col: lag_close_ret_4
      - source_col: close_ret
        lag: 8
        output_col: lag_close_ret_8
      - source_col: close_ret
        lag: 16
        output_col: lag_close_ret_16
      - source_col: close_ret
        lag: 24
        output_col: lag_close_ret_24
      - source_col: close_ret
        lag: 48
        output_col: lag_close_ret_48
- step: volatility
  params:
    returns_col: close_ret
    rolling_windows:
    - 24
    - 48
    - 96
    - 192
    ewma_spans: []
    annualization_factor: null
  outputs: {}
  enabled: true
- step: trend
  params:
    price_col: close
    sma_windows: []
    ema_spans:
    - 24
    - 48
    - 96
    - 192
    ema_col_template: ema_{span}
    add_ratios: false
  outputs: {}
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: ema_24
        denominator_col: ema_96
        output_col: ema_trend_24_96
        subtract: 1.0
      - numerator_col: ema_48
        denominator_col: ema_192
        output_col: ema_trend_48_192
        subtract: 1.0
      - numerator_col: close
        denominator_col: ema_96
        output_col: close_over_ema_96
        subtract: 1.0
      - numerator_col: close
        denominator_col: ema_192
        output_col: close_over_ema_192
        subtract: 1.0
- step: atr
  params:
    high_col: high
    low_col: low
    close_col: close
    window: 48
    windows:
    - 48
    method: wilder
    add_over_price: false
    atr_col: atr_48
  outputs: {}
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: atr_48
        denominator_col: close
        output_col: atr_over_price_48
- step: hilbert_transform
  params:
    price_col: close
    window: 64
    amplitude_col: hilbert_amplitude
    phase_col: hilbert_phase
    instantaneous_frequency_col: hilbert_instantaneous_frequency
    add_derived: false
  outputs: {}
  enabled: true
- step: dominant_cycle_period
  params:
    price_col: close
    output_col: dominant_cycle_period
  outputs: {}
  enabled: true
- step: dominant_cycle_phase
  params:
    price_col: close
    output_col: dominant_cycle_phase
    unit: degrees
  outputs: {}
  enabled: true
- step: mama
  params:
    price_col: close
    fast_limit: 0.5
    slow_limit: 0.05
    output_col: mama
  outputs: {}
  enabled: true
- step: fama
  params:
    price_col: close
    fast_limit: 0.5
    slow_limit: 0.05
    output_col: fama
  outputs: {}
  enabled: true
- step: decycler
  params:
    price_col: close
    period: 60
    output_col: decycler
  outputs: {}
  enabled: true
- step: decycler_oscillator
  params:
    price_col: close
    fast_period: 30
    slow_period: 60
    output_col: decycler_oscillator_30_60
  outputs: {}
  enabled: true
- step: instantaneous_trendline
  params:
    price_col: close
    alpha: 0.07
    output_col: instantaneous_trendline
    add_trigger: false
  outputs: {}
  enabled: true
- step: frama
  params:
    price_col: close
    high_col: high
    low_col: low
    window: 16
    fast_period: 4
    slow_period: 300
    output_col: frama
    add_diagnostics: false
  outputs: {}
  enabled: true
- step: supersmoother
  params:
    price_col: close
    period: 10
    output_col: supersmoother
  outputs: {}
  enabled: true
- step: roofing_filter
  params:
    price_col: close
    high_pass_period: 48
    low_pass_period: 10
    output_col: roofing_filter
  outputs: {}
  enabled: true
- step: ehlers_ml_long_candidate
  params:
    amplitude_col: hilbert_amplitude
    cycle_period_col: dominant_cycle_period
    roofing_col: roofing_filter
    mama_col: mama
    fama_col: fama
    close_col: close
    decycler_col: decycler
    instantaneous_trendline_col: instantaneous_trendline
    frama_col: frama
    supersmoother_col: supersmoother
    dominant_cycle_phase_col: dominant_cycle_phase
    dominant_cycle_phase_unit: degrees
    atr_col: atr_48
    amplitude_lookback: 128
    amplitude_min_quantile: 0.5
    min_cycle_period: 8.0
    max_cycle_period: 60.0
    slope_bars: 1
    candidate_col: ehlers_ml_candidate
    side_col: ehlers_ml_side
  outputs: {}
  enabled: true
- step: macd
  params:
    price_col: close
    fast: 12
    slow: 26
    signal: 9
  outputs:
    macd_12_26: macd
    macd_signal_9: macd_signal
    macd_hist_12_26_9: macd_hist
  enabled: true
- step: rsi
  params:
    price_col: close
    windows:
    - 14
    method: wilder
  outputs:
    close_rsi_14: rsi_14
  enabled: true
- step: stochastic_rsi
  params:
    price_col: close
    rsi_period: 14
    stoch_period: 14
    k_period: 3
    d_period: 3
    oversold: 0.2
    overbought: 0.8
    prefix: stoch_rsi
  outputs:
    stoch_rsi_k: stoch_rsi_k
    stoch_rsi_d: stoch_rsi_d
  enabled: true
- step: bollinger
  params:
    price_col: close
    window: 192
    n_std: 2.0
  outputs:
    bb_ma_192: bollinger_mid_192
    bb_upper_192_2.0: bollinger_upper_192
    bb_lower_192_2.0: bollinger_lower_192
    bb_width_192_2.0: bollinger_bandwidth
    bb_percent_b_192_2.0: bollinger_percent_b
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: close
        denominator_col: bb_upper_192_2.0
        output_col: close_over_bb_upper_192
        subtract: 1.0
      - numerator_col: close
        denominator_col: bb_ma_192
        output_col: close_over_bb_mid_192
        subtract: 1.0
- step: indicator_pullback
  params:
    asset_vocab:
    - ETHUSD
    open_col: open
    high_col: high
    low_col: low
    close_col: close
    ema_fast_period: 24
    ema_mid_period: 96
    ema_slow_period: 192
    atr_period: 48
    atr_pct_rank_window: 192
    macd_hist_col: macd_hist
    rsi_period: 14
    stoch_k_col: stoch_rsi_k
    stoch_d_col: stoch_rsi_d
    bollinger_bandwidth_col: bollinger_bandwidth
    bollinger_percent_b_col: bollinger_percent_b
    bb_bandwidth_rank_window: 192
    realized_vol_windows:
    - 24
    - 48
    - 96
    - 192
    return_windows:
    - 1
    - 4
    - 8
    - 16
    - 24
    - 48
    rolling_return_windows:
    - 24
    - 48
  outputs: {}
  enabled: true
```

## Config Snapshot
```yaml
data:
  source: dukascopy_csv
  interval: 30m
  start: null
  end: null
  alignment: inner
  symbol: ETHUSD
  symbols: null
  api_key: null
  api_key_env: null
  pit:
    timestamp_alignment:
      source_timezone: UTC
      output_timezone: UTC
      normalize_daily: false
      duplicate_policy: last
    corporate_actions:
      policy: none
      adj_close_col: adj_close
    universe_snapshot:
      inactive_policy: raise
  storage:
    mode: cached_only
    dataset_id: ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid
    save_raw: false
    save_processed: false
    load_path: /workspace/data/raw/dukascopy_30m_clean/ethusd_30m.csv
    raw_dir: /workspace/data/raw
    processed_dir: /workspace/data/processed
    load_paths: null
model:
  kind: xgboost_regressor
  params:
    n_estimators: 600
    learning_rate: 0.04
    max_depth: 4
    min_child_weight: 20
    subsample: 0.9
    colsample_bytree: 0.75
    reg_alpha: 0.05
    reg_lambda: 2.0
    objective: reg:squarederror
    eval_metric: rmse
    tree_method: hist
    random_state: 7
    n_jobs: 1
  outputs:
    pred_ret_col: pred_ret
    pred_prob_col: pred_prob
    pred_is_oos_col: pred_is_oos
  preprocessing:
    scaler: none
  calibration: {}
  feature_cols:
  - close_ret
  - lag_close_ret_1
  - lag_close_ret_2
  - lag_close_ret_4
  - lag_close_ret_8
  - lag_close_ret_16
  - lag_close_ret_24
  - lag_close_ret_48
  - ret_1
  - ret_4
  - ret_8
  - ret_16
  - ret_24
  - ret_48
  - rolling_return_24
  - rolling_return_48
  - vol_rolling_24
  - vol_rolling_48
  - vol_rolling_96
  - vol_rolling_192
  - atr_48
  - atr_over_price_48
  - atr_pct
  - atr_pct_rank_192
  - ema_trend_48_192
  - close_over_bb_upper_192
  - close_over_bb_mid_192
  - bollinger_percent_b
  - bollinger_bandwidth
  - bollinger_bandwidth_rank_192
  - ema_alignment_score
  - distance_from_ema24_atr
  - distance_from_ema96_atr
  - mama_minus_fama_over_atr
  - close_minus_decycler_over_atr
  - instantaneous_trendline_slope_over_atr
  - decycler_slope_over_atr
  - frama_slope_over_atr
  - supersmoother_slope_over_atr
  - roofing_filter_over_atr
  - dominant_cycle_phase_normalized
  - body_ratio
  - upper_wick_ratio
  - lower_wick_ratio
  - close_location
  - range_to_atr
  target:
    kind: future_return_regression
    price_col: close
    returns_col: close_ret
    returns_type: simple
    horizon_bars: 24
    normalize_by_volatility: true
    volatility_col: atr_48
    clip:
    - -4.0
    - 4.0
    fwd_col: target_future_return_h24_atr
    label_col: target_future_return_h24_atr
  split:
    method: purged
    train_size: 35040
    test_size: 4380
    step_size: 4380
    expanding: true
    max_folds: 10
    purge_bars: 24
    embargo_bars: 24
  runtime: {}
  env: {}
  use_features: true
  pred_prob_col: pred_prob
  pred_raw_prob_col: null
  pred_ret_col: pred_ret
  pred_is_oos_col: pred_is_oos
  returns_input_col: null
  signal_col: null
  action_col: null
signals:
  kind: forecast_threshold
  params:
    forecast_col: pred_ret
    signal_col: signal_structured_tail
    upper: 0.7
    lower: -0.85
    mode: long_short
    activation_filters:
    - col: atr_pct_rank_192
      op: ge
      value: 0.25
    - col: atr_pct_rank_192
      op: le
      value: 0.85
    - col: range_to_atr
      op: ge
      value: 0.8999999999999999
    - col: bollinger_bandwidth_rank_192
      op: ge
      value: 0.4
  outputs: {}
risk:
  cost_per_turnover: 0.0001
  slippage_per_turnover: 0.0
  target_vol: null
  max_leverage: 1.0
  dd_guard:
    enabled: false
    max_drawdown: 0.2
    cooloff_bars: 20
    rearm_drawdown: 0.2
  portfolio_guard: {}
  sizing: {}
  drawdown_sizing: {}
  vol_col: null
backtest:
  engine: vectorized
  returns_col: close_ret
  signal_col: signal_structured_tail
  periods_per_year: 17520
  returns_type: simple
  missing_return_policy: raise_if_exposed
  min_holding_bars: 24
  subset: test
  stop_mode: fixed_return
  vol_col: null
  open_col: open
  high_col: high
  low_col: low
  close_col: close
  take_profit_r: null
  stop_loss_r: null
  volatility_col: null
  entry_price_mode: null
  profit_barrier_r: null
  stop_barrier_r: null
  vertical_barrier_bars: null
  tie_break: null
  event_time_remap_policy: null
  max_cost_r: null
  risk_per_trade: null
  max_holding_bars: null
  asset_params: {}
  dynamic_exits: {}
  partial_exits: {}
  allow_short: true
portfolio:
  enabled: false
  construction: signal_weights
  gross_target: 1.0
  long_short: true
  expected_return_col: null
  covariance_window: 60
  covariance_rebalance_step: 1
  risk_aversion: 5.0
  trade_aversion: 0.0
  selection:
    enabled: false
    top_k: 1
    min_expected_net_return: 0.0
    rank_by_abs: true
    weighting: score
    rebalance_every_n_bars: 1
  constraints:
    enforce_target_net_exposure: true
  asset_groups: {}
runtime:
  seed: 7
  repro_mode: strict
  deterministic: true
  threads: 1
  seed_torch: false
```

## Artifact Inventory
- `report_markdown`: `report.md`
- `config`: `config_used.yaml`
- `summary`: `summary.json`
- `run_metadata`: `run_metadata.json`
- `equity_curve`: `equity_curve.csv`
- `returns`: `returns.csv`
- `gross_returns`: `gross_returns.csv`
- `costs`: `costs.csv`
- `turnover`: `turnover.csv`
- `positions`: `positions.csv`
- `monitoring`: `monitoring_report.json`
- `trade_events`: `report_assets/trade_events.csv`
- `trades_enriched`: `report_assets/trades_enriched.csv`
- `trade_path_summary`: `report_assets/trade_path_summary.json`
- `trade_paths`: `report_assets/trade_paths.parquet`
- `trade_path_diagnostics`: `report_assets/trade_path_diagnostics.json`
- `probability_trade_quality`: `report_assets/probability_trade_quality.csv`
- `counterfactual_exit_summary`: `report_assets/counterfactual_exit_summary.csv`
- `counterfactual_exit_trades`: `report_assets/counterfactual_exit_trades.csv`
- `feature_importance`: `feature_importance.csv`
- `prediction_diagnostics`: `prediction_diagnostics.json`
- `missing_value_diagnostics`: `missing_value_diagnostics.json`
- `fold_model_summary`: `fold_model_summary.csv`
- `stage_tails`: `stage_tails.json`
- `diagnostics_fold_backtest_diagnostics`: `artifacts/diagnostics/fold_backtest_diagnostics.csv`
- `diagnostics_forecast_alpha_diagnostics_summary`: `artifacts/diagnostics/forecast_alpha_diagnostics_summary.json`
- `diagnostics_forecast_baselines`: `artifacts/diagnostics/forecast_baselines.csv`
- `diagnostics_lab_feature_diagnostics_ETHUSD`: `artifacts/diagnostics/lab_feature_diagnostics_ETHUSD.json`
- `diagnostics_regime_performance`: `artifacts/diagnostics/regime_performance.csv`
- `diagnostics_threshold_grid`: `artifacts/diagnostics/threshold_grid.csv`
- `equity_curve_chart`: `report_assets/equity_curve.png`
- `drawdown_curve`: `report_assets/drawdown_curve.png`
- `cumulative_returns`: `report_assets/cumulative_returns.png`
- `monthly_returns`: `report_assets/monthly_returns.png`
- `rolling_pnl`: `report_assets/rolling_pnl.png`
- `cumulative_cost_drag`: `report_assets/cumulative_cost_drag.png`
- `positions_turnover`: `report_assets/positions_turnover.png`
- `rolling_behavior`: `report_assets/rolling_behavior.png`
- `signal_distribution`: `report_assets/signal_distribution.png`
- `fold_net_pnl`: `report_assets/fold_net_pnl.png`
- `feature_importance_chart`: `report_assets/feature_importance.png`
- `prediction_coverage_by_fold`: `report_assets/prediction_coverage_by_fold.png`
