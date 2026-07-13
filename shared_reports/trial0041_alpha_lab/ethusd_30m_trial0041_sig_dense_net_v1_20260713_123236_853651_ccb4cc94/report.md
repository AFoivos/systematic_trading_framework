# Experiment Report: ethusd_30m_trial0041_sig_dense_net_v1

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/05_signal_lab/ethusd_30m_trial0041_sig_dense_net_v1.yaml`
- Model kind: `lightgbm_regressor`
- Symbols: `ETHUSD`
- Data source: `dukascopy_csv` at interval `30m`
- Data window: `None` to `2026-06-09 23:30:00`
- Rows / columns: `109005` rows, `128` columns
- Target: `future_return_regression` horizon `24`
- Feature count: `46`
- Runtime seed: `7`

## Pipeline Trace

### 1. Entry Point
- `runner.run_experiment` -> `src.experiments.runner.run_experiment(config_path: 'str | Path') -> 'ExperimentResult'`
- `runner._load_asset_frames` -> `src.experiments.runner._load_asset_frames(data_cfg: 'dict[str, object]')`
- `pipeline.run_experiment_pipeline` -> `src.experiments.orchestration.pipeline.run_experiment_pipeline(config_path: 'str | Path', *, load_asset_frames_fn: 'LoadAssetFramesFn', save_processed_snapshot_fn: 'SaveProcessedFn') -> 'ExperimentResult'`

```yaml
config_path: /workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/05_signal_lab/ethusd_30m_trial0041_sig_dense_net_v1.yaml
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
- `model[lightgbm_regressor]` -> `src.models.forecasting.base.train_lightgbm_regressor(*args: 'object', **kwargs: 'object') -> 'object'`
- `modeling.runtime.resolve_runtime_for_model` -> `src.models.common.runtime.resolve_runtime_for_model(model_cfg: 'dict[str, Any]', model_params: 'dict[str, Any]', *, estimator_family: 'str') -> 'dict[str, Any]'`

```yaml
model:
  kind: lightgbm_regressor
  params:
    n_estimators: 800
    learning_rate: 0.0549537895493607
    max_depth: 6
    num_leaves: 15
    min_child_samples: 200
    subsample: 0.9
    colsample_bytree: 0.75
    reg_alpha: 0.019934229992965794
    reg_lambda: 1.8786413727433209
    random_state: 7
    n_jobs: 1
    verbosity: -1
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
- `signal[dense_return_forecast]` -> `src.signals.dense_return_forecast_signal.dense_return_forecast_signal(df: 'pd.DataFrame', *, forecast_col: 'str' = 'pred_ret', signal_col: 'str' = 'expected_net_return', expected_net_return_col: 'str' = 'expected_net_return', estimated_cost_col: 'str' = 'estimated_round_trip_cost', cost_per_turnover: 'float' = 0.0, slippage_per_turnover: 'float' = 0.0, cost_round_trip_mult: 'float' = 2.0, forecast_is_vol_normalized: 'bool' = False, volatility_col: 'str' = 'atr_14', price_col: 'str' = 'close', volatility_floor: 'float' = 1e-12, signed_cost_adjustment: 'bool' = True, clip: 'float | None' = None) -> 'pd.DataFrame'`  
  params={'forecast_col': 'pred_ret', 'signal_col': 'signal_dense_net', 'expected_net_return_col': 'expected_net_return', 'estimated_cost_col': 'estimated_round_trip_cost', 'cost_per_turnover': 0.0001, 'slippage_per_turnover': 0.0, 'cost_round_trip_mult': 2.0, 'forecast_is_vol_normalized': True, 'volatility_col': 'atr_48', 'price_col': 'close', 'volatility_floor': 1e-12, 'signed_cost_adjustment': True, 'clip': 1.0}

```yaml
signals:
  kind: dense_return_forecast
  params:
    forecast_col: pred_ret
    signal_col: signal_dense_net
    expected_net_return_col: expected_net_return
    estimated_cost_col: estimated_round_trip_cost
    cost_per_turnover: 0.0001
    slippage_per_turnover: 0.0
    cost_round_trip_mult: 2.0
    forecast_is_vol_normalized: true
    volatility_col: atr_48
    price_col: close
    volatility_floor: 1.0e-12
    signed_cost_adjustment: true
    clip: 1.0
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
  signal_col: signal_dense_net
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
| cumulative_return | 5.105845 |
| annualized_return | 1.062046 |
| annualized_vol | 0.447651 |
| sharpe | 2.372487 |
| sortino | 3.497547 |
| calmar | 2.923164 |
| max_drawdown | -0.363321 |
| profit_factor | 1.056878 |
| hit_rate | 0.499254 |
| avg_turnover | 0.024321 |
| total_turnover | 1.065e+03 |
| gross_pnl | 2.165936 |
| net_pnl | 2.059409 |
| total_cost | 0.106527 |
| cost_drag | 0.106527 |
| cost_to_gross_pnl | 0.049183 |
| flat_rate | 0.0 |
| long_rate | 0.499498 |
| short_rate | 0.500502 |
| trade_count | 691 |
| average_r | 0.518759 |
| median_r | 0.441317 |
| avg_max_favorable_r | 4.879135 |
| avg_max_adverse_r | -4.438782 |
| loser_was_positive_rate | 0.990132 |
| avg_giveback_r | 4.360376 |
| avg_capture_ratio | -9.014150 |
| robustness_walk_forward_positive_fold_ratio | 0.600000 |
| robustness_walk_forward_min_fold_cumulative_return | 0.0 |
| robustness_walk_forward_worst_fold_max_drawdown | -0.363321 |
| robustness_walk_forward_mean_fold_sharpe | 1.504346 |
| robustness_walk_forward_std_fold_sharpe | 1.654744 |
| robustness_cost_x1_cumulative_return | 5.067121 |
| robustness_cost_x1_sharpe | 1.546213 |
| robustness_cost_x1_max_drawdown | -0.363321 |
| robustness_cost_x1_profit_factor | 1.056683 |
| robustness_cost_x2_cumulative_return | 4.453848 |
| robustness_cost_x2_sharpe | 1.435367 |
| robustness_cost_x2_max_drawdown | -0.368246 |
| robustness_cost_x2_profit_factor | 1.053655 |
| robustness_cost_x3_cumulative_return | 3.902515 |
| robustness_cost_x3_sharpe | 1.327240 |
| robustness_cost_x3_max_drawdown | -0.373135 |
| robustness_cost_x3_profit_factor | 1.050631 |
| robustness_cost_x5_cumulative_return | 2.961291 |
| robustness_cost_x5_sharpe | 1.118903 |
| robustness_cost_x5_max_drawdown | -0.382799 |
| robustness_cost_x5_profit_factor | 1.044602 |
| robustness_delay_1_bars_cumulative_return | 4.093341 |
| robustness_delay_1_bars_sharpe | 1.053879 |
| robustness_delay_1_bars_max_drawdown | -0.367263 |
| robustness_delay_1_bars_profit_factor | 1.051761 |
| robustness_delay_2_bars_cumulative_return | 4.688814 |
| robustness_delay_2_bars_sharpe | 1.133223 |
| robustness_delay_2_bars_max_drawdown | -0.320541 |
| robustness_delay_2_bars_profit_factor | 1.054918 |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.571818 |
| signal_turnover | 0.168129 |
| long_rate | 0.499498 |
| short_rate | 0.500502 |
| flat_rate | 0.0 |
| executed_trade_count | 43800 |
| trade_rate | 1.000000 |
| avg_signal_executed | 0.001303 |
| avg_pred_prob_executed | 0.497021 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.524087 |
| classification.brier | 0.282160 |
| classification.roc_auc | 0.532113 |
| classification.log_loss | 0.783630 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.168720 |
| regression.rmse | 2.633556 |
| regression.mse | 6.935617 |
| regression.r2 | -0.110769 |
| regression.correlation | 0.053040 |
| regression.directional_accuracy | 0.523973 |
| regression.mean_prediction | -0.010636 |
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
| prediction_distribution.mean | -0.010636 |
| prediction_distribution.std | 0.974568 |
| prediction_distribution.min | -4.183777 |
| prediction_distribution.max | 3.706707 |
| prediction_distribution.median | -0.000887 |
| prediction_distribution.q01 | -2.492384 |
| prediction_distribution.q05 | -1.663680 |
| prediction_distribution.q25 | -0.610015 |
| prediction_distribution.q75 | 0.614556 |
| prediction_distribution.q95 | 1.585182 |
| prediction_distribution.q99 | 2.284676 |
| prediction_distribution.skew | -0.125653 |
| prediction_distribution.kurtosis | 0.403181 |
| prediction_distribution.positive_rate | 0.499658 |
| prediction_distribution.negative_rate | 0.500342 |
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
| probability_distribution.mean | 0.497021 |
| probability_distribution.std | 0.207907 |
| probability_distribution.min | 0.014782 |
| probability_distribution.max | 0.977911 |
| probability_distribution.median | 0.499762 |
| probability_distribution.q01 | 0.072399 |
| probability_distribution.q05 | 0.147944 |
| probability_distribution.q25 | 0.341639 |
| probability_distribution.q75 | 0.656493 |
| probability_distribution.q95 | 0.831565 |
| probability_distribution.q99 | 0.910521 |
| probability_distribution.skew | -0.056530 |
| probability_distribution.kurtosis | -0.771280 |
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
| lightgbm_importance | [open](artifacts/diagnostics/lightgbm_importance.csv) |
| prediction_distribution | [open](artifacts/diagnostics/prediction_distribution.csv) |
| prediction_metrics | [open](artifacts/diagnostics/prediction_metrics.csv) |
| regime_diagnostics | [open](artifacts/diagnostics/regime_diagnostics.csv) |
| regime_performance | [open](artifacts/diagnostics/regime_performance.csv) |
| shap_feature_importance | [open](artifacts/diagnostics/shap_feature_importance.csv) |
| shap_per_prediction | [open](artifacts/diagnostics/shap_per_prediction.csv) |
| shap_status | [open](artifacts/diagnostics/shap_status.csv) |
| shap_values_sample | [open](artifacts/diagnostics/shap_values_sample.csv) |
| summary | [open](artifacts/diagnostics/summary.json) |
| threshold_grid | [open](artifacts/diagnostics/threshold_grid.csv) |
| turnover_cost_timeseries | [open](artifacts/diagnostics/turnover_cost_timeseries.csv) |


## Forecast Baselines
| Name | Cum Return | Ann Return | Ann Vol | Sharpe | Sortino | Calmar | Max DD | Profit Factor | Hit Rate | Turnover | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| model_strategy | 5.105845 | 1.062046 | 0.447651 | 2.372487 | 3.497547 | 2.923164 | -0.363321 | 1.056878 | 0.499254 | 1.065e+03 | 0.049183 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | -0.089284 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000224 |
| random_sign_same_rate | -0.225407 | -0.097121 | 0.665486 | -0.145940 | -0.212393 | -0.146727 | -0.661916 | 1.004519 | 0.499771 | 3.507e+03 | 0.541366 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | -0.240522 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.789225 |
| simple_trend | -0.867002 | -0.553792 | 0.665797 | -0.831772 | -1.181822 | -0.608132 | -0.910644 | 0.978047 | 0.491683 | 1.545e+03 | 0.118038 |


## Threshold Grid
| Name | Upper | Lower | Net PnL | Sharpe | Max DD | Profit Factor | Cost/Gross | Turnover | Active Rows | Profitable Folds | Median Fold Return | Worst 3-Fold Avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sym_0.35 | 0.350000 | -0.350000 | 2.087582 | 1.114988 | -0.421632 | 1.036697 | 0.106739 | 1.737e+03 | 3.026e+04 | 6.000000 | 0.026682 | -0.062283 |
| sym_0.5 | 0.500000 | -0.500000 | 1.800397 | 1.026350 | -0.476245 | 1.036592 | 0.111865 | 1.685e+03 | 2.530e+04 | 6.000000 | 0.073574 | -0.205933 |
| sym_0.75 | 0.750000 | -0.750000 | 0.745973 | 0.539376 | -0.556882 | 1.025835 | 0.158704 | 1.556e+03 | 1.805e+04 | 8.000000 | 0.128478 | -0.169381 |
| sym_1 | 1.000000 | -1.000000 | 2.307097 | 1.394457 | -0.353362 | 1.052258 | 0.087705 | 1.382e+03 | 1.257e+04 | 6.000000 | 0.038018 | -0.082970 |
| sym_1.25 | 1.250000 | -1.250000 | 0.720362 | 0.625465 | -0.356827 | 1.033940 | 0.131578 | 1.106e+03 | 8.455e+03 | 5.000000 | 0.000863 | -0.118831 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.136535 |
| mean_fold_return | 0.236095 |
| fold_return_std | 0.352604 |
| worst_fold_return | -0.106985 |
| best_fold_return | 1.078710 |
| worst_3_fold_average_return | -0.058048 |
| profitable_fold_count | 8.000000 |
| profitable_fold_rate | 0.800000 |
| median_fold_sharpe | 1.729760 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.3, 'best_rank': 1, 'mean_importance': 1126.0, 'mean_importance_normalized': 0.10434712652023004, 'folds': [{'fold': 0, 'rank': 1, 'importance': 1164.0, 'importance_normalized': 0.11255076387545929}, {'fold': 1, 'rank': 1, 'importance': 1119.0, 'importance_normalized': 0.10409302325581396}, {'fold': 2, 'rank': 1, 'importance': 1168.0, 'importance_normalized': 0.10693033049528518}, {'fold': 3, 'rank': 1, 'importance': 1194.0, 'importance_normalized': 0.10946094609460946}, {'fold': 4, 'rank': 1, 'importance': 1137.0, 'importance_normalized': 0.10560044580663137}, {'fold': 5, 'rank': 1, 'importance': 1123.0, 'importance_normalized': 0.10413575667655786}, {'fold': 6, 'rank': 1, 'importance': 1115.0, 'importance_normalized': 0.10325986293758103}, {'fold': 7, 'rank': 2, 'importance': 1061.0, 'importance_normalized': 0.09685075308078503}, {'fold': 8, 'rank': 2, 'importance': 1083.0, 'importance_normalized': 0.09967786470317533}, {'fold': 9, 'rank': 2, 'importance': 1096.0, 'importance_normalized': 0.10091151827640181}], 'stability_rank': 1}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.7, 'best_rank': 1, 'mean_importance': 1076.9, 'mean_importance_normalized': 0.09972631547417042, 'folds': [{'fold': 0, 'rank': 2, 'importance': 984.0, 'importance_normalized': 0.09514600657513053}, {'fold': 1, 'rank': 2, 'importance': 999.0, 'importance_normalized': 0.09293023255813954}, {'fold': 2, 'rank': 2, 'importance': 1062.0, 'importance_normalized': 0.09722603680307608}, {'fold': 3, 'rank': 2, 'importance': 1022.0, 'importance_normalized': 0.09369270260359369}, {'fold': 4, 'rank': 2, 'importance': 1048.0, 'importance_normalized': 0.09733444784991177}, {'fold': 5, 'rank': 2, 'importance': 1091.0, 'importance_normalized': 0.10116839762611277}, {'fold': 6, 'rank': 2, 'importance': 1076.0, 'importance_normalized': 0.09964808297832932}, {'fold': 7, 'rank': 1, 'importance': 1139.0, 'importance_normalized': 0.10397078959379279}, {'fold': 8, 'rank': 1, 'importance': 1177.0, 'importance_normalized': 0.10832949838932351}, {'fold': 9, 'rank': 1, 'importance': 1171.0, 'importance_normalized': 0.10781695976429427}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 3.0, 'best_rank': 3, 'mean_importance': 940.5, 'mean_importance_normalized': 0.08709543705267477, 'folds': [{'fold': 0, 'rank': 3, 'importance': 838.0, 'importance_normalized': 0.08102881454264166}, {'fold': 1, 'rank': 3, 'importance': 902.0, 'importance_normalized': 0.08390697674418604}, {'fold': 2, 'rank': 3, 'importance': 933.0, 'importance_normalized': 0.08541609447953859}, {'fold': 3, 'rank': 3, 'importance': 978.0, 'importance_normalized': 0.08965896589658966}, {'fold': 4, 'rank': 3, 'importance': 925.0, 'importance_normalized': 0.0859106529209622}, {'fold': 5, 'rank': 3, 'importance': 926.0, 'importance_normalized': 0.0858679525222552}, {'fold': 6, 'rank': 3, 'importance': 1020.0, 'importance_normalized': 0.09446193739581404}, {'fold': 7, 'rank': 3, 'importance': 898.0, 'importance_normalized': 0.08197170241898677}, {'fold': 8, 'rank': 3, 'importance': 966.0, 'importance_normalized': 0.08890934192360792}, {'fold': 9, 'rank': 3, 'importance': 1019.0, 'importance_normalized': 0.09382193168216554}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.1, 'best_rank': 4, 'mean_importance': 783.1, 'mean_importance_normalized': 0.07253015194480629, 'folds': [{'fold': 0, 'rank': 5, 'importance': 709.0, 'importance_normalized': 0.06855540514407271}, {'fold': 1, 'rank': 4, 'importance': 755.0, 'importance_normalized': 0.07023255813953488}, {'fold': 2, 'rank': 4, 'importance': 777.0, 'importance_normalized': 0.07113430376270255}, {'fold': 3, 'rank': 4, 'importance': 756.0, 'importance_normalized': 0.06930693069306931}, {'fold': 4, 'rank': 4, 'importance': 846.0, 'importance_normalized': 0.07857341877960435}, {'fold': 5, 'rank': 4, 'importance': 832.0, 'importance_normalized': 0.0771513353115727}, {'fold': 6, 'rank': 4, 'importance': 775.0, 'importance_normalized': 0.07177255047230968}, {'fold': 7, 'rank': 4, 'importance': 788.0, 'importance_normalized': 0.07193062528525787}, {'fold': 8, 'rank': 4, 'importance': 802.0, 'importance_normalized': 0.07381500230096641}, {'fold': 9, 'rank': 4, 'importance': 791.0, 'importance_normalized': 0.07282938955897247}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.9, 'best_rank': 4, 'mean_importance': 727.2, 'mean_importance_normalized': 0.06737381630516576, 'folds': [{'fold': 0, 'rank': 4, 'importance': 714.0, 'importance_normalized': 0.0690388706246374}, {'fold': 1, 'rank': 5, 'importance': 735.0, 'importance_normalized': 0.06837209302325581}, {'fold': 2, 'rank': 5, 'importance': 692.0, 'importance_normalized': 0.06335255882083676}, {'fold': 3, 'rank': 5, 'importance': 687.0, 'importance_normalized': 0.06298129812981298}, {'fold': 4, 'rank': 5, 'importance': 728.0, 'importance_normalized': 0.06761400575833565}, {'fold': 5, 'rank': 5, 'importance': 716.0, 'importance_normalized': 0.0663946587537092}, {'fold': 6, 'rank': 5, 'importance': 751.0, 'importance_normalized': 0.06954991665123171}, {'fold': 7, 'rank': 5, 'importance': 775.0, 'importance_normalized': 0.07074395253308992}, {'fold': 8, 'rank': 5, 'importance': 712.0, 'importance_normalized': 0.0655315232397607}, {'fold': 9, 'rank': 5, 'importance': 762.0, 'importance_normalized': 0.07015928551698739}], 'stability_rank': 5}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.3, 'best_rank': 6, 'mean_importance': 600.4, 'mean_importance_normalized': 0.05561559886013534, 'folds': [{'fold': 0, 'rank': 6, 'importance': 572.0, 'importance_normalized': 0.05530845097660027}, {'fold': 1, 'rank': 6, 'importance': 596.0, 'importance_normalized': 0.05544186046511628}, {'fold': 2, 'rank': 7, 'importance': 589.0, 'importance_normalized': 0.05392291495010528}, {'fold': 3, 'rank': 6, 'importance': 626.0, 'importance_normalized': 0.057389072240557386}, {'fold': 4, 'rank': 6, 'importance': 612.0, 'importance_normalized': 0.05684034550013931}, {'fold': 5, 'rank': 6, 'importance': 598.0, 'importance_normalized': 0.05545252225519288}, {'fold': 6, 'rank': 6, 'importance': 604.0, 'importance_normalized': 0.0559362844971291}, {'fold': 7, 'rank': 6, 'importance': 620.0, 'importance_normalized': 0.05659516202647193}, {'fold': 8, 'rank': 6, 'importance': 612.0, 'importance_normalized': 0.056327657616198804}, {'fold': 9, 'rank': 8, 'importance': 575.0, 'importance_normalized': 0.05294171807384219}], 'stability_rank': 6}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.1, 'best_rank': 6, 'mean_importance': 578.5, 'mean_importance_normalized': 0.05358525315328122, 'folds': [{'fold': 0, 'rank': 7, 'importance': 559.0, 'importance_normalized': 0.05405144072713208}, {'fold': 1, 'rank': 7, 'importance': 553.0, 'importance_normalized': 0.05144186046511628}, {'fold': 2, 'rank': 8, 'importance': 583.0, 'importance_normalized': 0.05337361530715005}, {'fold': 3, 'rank': 7, 'importance': 625.0, 'importance_normalized': 0.0572973964063073}, {'fold': 4, 'rank': 7, 'importance': 569.0, 'importance_normalized': 0.05284666109408377}, {'fold': 5, 'rank': 7, 'importance': 562.0, 'importance_normalized': 0.05211424332344214}, {'fold': 6, 'rank': 7, 'importance': 588.0, 'importance_normalized': 0.054454528616410446}, {'fold': 7, 'rank': 7, 'importance': 591.0, 'importance_normalized': 0.0539479689639434}, {'fold': 8, 'rank': 8, 'importance': 560.0, 'importance_normalized': 0.05154164749194662}, {'fold': 9, 'rank': 6, 'importance': 595.0, 'importance_normalized': 0.05478316913728018}], 'stability_rank': 7}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.7, 'best_rank': 6, 'mean_importance': 551.9, 'mean_importance_normalized': 0.05110775136680991, 'folds': [{'fold': 0, 'rank': 8, 'importance': 510.0, 'importance_normalized': 0.049313479017598146}, {'fold': 1, 'rank': 9, 'importance': 523.0, 'importance_normalized': 0.04865116279069767}, {'fold': 2, 'rank': 6, 'importance': 596.0, 'importance_normalized': 0.05456376453355306}, {'fold': 3, 'rank': 8, 'importance': 575.0, 'importance_normalized': 0.052713604693802714}, {'fold': 4, 'rank': 8, 'importance': 564.0, 'importance_normalized': 0.0523822791864029}, {'fold': 5, 'rank': 8, 'importance': 472.0, 'importance_normalized': 0.04376854599406528}, {'fold': 6, 'rank': 8, 'importance': 578.0, 'importance_normalized': 0.05352843119096129}, {'fold': 7, 'rank': 8, 'importance': 557.0, 'importance_normalized': 0.0508443633044272}, {'fold': 8, 'rank': 7, 'importance': 564.0, 'importance_normalized': 0.051909802116889094}, {'fold': 9, 'rank': 7, 'importance': 580.0, 'importance_normalized': 0.05340208083970169}], 'stability_rank': 8}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 8.9, 'best_rank': 8, 'mean_importance': 478.9, 'mean_importance_normalized': 0.04436711412422099, 'folds': [{'fold': 0, 'rank': 9, 'importance': 453.0, 'importance_normalized': 0.043801972539160704}, {'fold': 1, 'rank': 8, 'importance': 552.0, 'importance_normalized': 0.05134883720930233}, {'fold': 2, 'rank': 9, 'importance': 478.0, 'importance_normalized': 0.04376087155543349}, {'fold': 3, 'rank': 9, 'importance': 482.0, 'importance_normalized': 0.044187752108544184}, {'fold': 4, 'rank': 9, 'importance': 482.0, 'importance_normalized': 0.04476641590043652}, {'fold': 5, 'rank': 9, 'importance': 469.0, 'importance_normalized': 0.04349035608308605}, {'fold': 6, 'rank': 9, 'importance': 467.0, 'importance_normalized': 0.04324874976847564}, {'fold': 7, 'rank': 9, 'importance': 470.0, 'importance_normalized': 0.042902784116841626}, {'fold': 8, 'rank': 9, 'importance': 487.0, 'importance_normalized': 0.04482282558674643}, {'fold': 9, 'rank': 9, 'importance': 449.0, 'importance_normalized': 0.041340576374182855}], 'stability_rank': 9}, {'feature': 'vol_rolling_24', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 10.4, 'best_rank': 10, 'mean_importance': 423.1, 'mean_importance_normalized': 0.03919258621640152, 'folds': [{'fold': 0, 'rank': 10, 'importance': 411.0, 'importance_normalized': 0.039740862502417325}, {'fold': 1, 'rank': 10, 'importance': 443.0, 'importance_normalized': 0.0412093023255814}, {'fold': 2, 'rank': 10, 'importance': 449.0, 'importance_normalized': 0.04110592328114987}, {'fold': 3, 'rank': 11, 'importance': 391.0, 'importance_normalized': 0.035845251191785846}, {'fold': 4, 'rank': 11, 'importance': 408.0, 'importance_normalized': 0.03789356366675954}, {'fold': 5, 'rank': 11, 'importance': 404.0, 'importance_normalized': 0.03746290801186944}, {'fold': 6, 'rank': 10, 'importance': 398.0, 'importance_normalized': 0.03685867753287646}, {'fold': 7, 'rank': 10, 'importance': 450.0, 'importance_normalized': 0.041077133728890915}, {'fold': 8, 'rank': 10, 'importance': 454.0, 'importance_normalized': 0.04178554993097101}, {'fold': 9, 'rank': 11, 'importance': 423.0, 'importance_normalized': 0.03894668999171347}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.188922 | 0.806657 | -0.232314 | 1.025335 | 0.149274 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.808614 | 1.504798 | -0.313531 | 1.040258 | 0.075001 |
| atr_pct_rank_192 | high | 8.547e+03 | -0.437854 | -1.035715 | -0.488196 | 0.958632 | 0.056052 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 1.206466 | 2.082423 | -0.268651 | 1.052073 | 0.059476 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 1.357831 | 2.049009 | -0.386097 | 1.052324 | 0.050250 |
| ema_trend_48_192 | negative | 2.183e+04 | 0.599430 | 0.908460 | -0.340981 | 1.032122 | 0.080411 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.915839 | 1.676653 | -0.240779 | 1.042577 | 0.073581 |
| range_to_atr | calm | 2.190e+04 | 0.019791 | 0.090955 | -0.197826 | 1.004481 | 0.609239 |
| range_to_atr | shock | 2.190e+04 | 0.553366 | 0.677248 | -0.504267 | 1.024069 | 0.087133 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 691 |
| average_r | 0.518759 |
| median_r | 0.441317 |
| avg_max_favorable_r | 4.879135 |
| avg_max_adverse_r | -4.438782 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.990132 |
| avg_giveback_r | 4.360376 |
| avg_capture_ratio | -9.014150 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.990132 |
| avg_mfe_r_of_losers | 2.019213 |
| median_mfe_r_of_losers | 1.446011 |
| avg_mfe_r_before_loss | 2.019213 |
| median_mfe_r_before_loss | 1.446011 |
| loser_reached_0_5r_rate | 0.773026 |
| loser_reached_1r_rate | 0.605263 |
| loser_reached_1_5r_rate | 0.486842 |
| loser_reached_2r_rate | 0.388158 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -9.014150 |
| median_capture_ratio | 0.169313 |
| avg_giveback_r | 4.360376 |
| median_giveback_r | 2.830083 |
| avg_giveback_r_winners | 2.495242 |
| avg_giveback_r_losers | 6.734741 |
| median_giveback_r_winners | 1.961405 |
| median_giveback_r_losers | 4.590041 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.981912 |
| winner_had_mae_below_minus_0_25r_rate | 0.875969 |
| winner_had_mae_below_minus_0_5r_rate | 0.762274 |
| winner_had_mae_below_minus_1r_rate | 0.578811 |
| avg_mae_r_of_winners | -1.966549 |
| median_mae_r_of_winners | -1.360969 |
| p90_abs_mae_r_of_winners | 4.672823 |
| avg_mae_r | -4.438782 |
| median_mae_r | -2.586121 |
| q10_mae_r | -9.785023 |
| q25_mae_r | -5.559814 |
| q75_mae_r | -1.034597 |
| q90_mae_r | -0.349311 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.560058 |
| prob_final_loss | 0.439942 |
| prob_final_win_given_mae_gt_minus_0_5r | 0.978723 |
| prob_final_win_given_mae_gt_minus_1r | 0.964497 |
| prob_mfe_ge_0_5r | 0.898698 |
| prob_final_loss_given_mfe_ge_0_5r | 0.378422 |
| prob_mfe_ge_1r | 0.814761 |
| prob_final_loss_given_mfe_ge_1r | 0.326821 |
| prob_mfe_ge_1_5r | 0.742402 |
| prob_final_loss_given_mfe_ge_1_5r | 0.288499 |
| prob_mfe_ge_2r | 0.678726 |
| prob_final_loss_given_mfe_ge_2r | 0.251599 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 31.199711 |
| median_time_to_mfe | 20.000000 |
| avg_time_to_mae | 30.345876 |
| median_time_to_mae | 16.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.041968 |
| prob_mfe_ge_0_5r_within_2_bars | 0.073806 |
| prob_mfe_ge_1r_within_4_bars | 0.062229 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.518759 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.560058 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 691 |
| counterfactual.baseline.avg_r | 0.518759 |
| counterfactual.baseline.median_r | 0.441317 |
| counterfactual.baseline.win_rate | 0.560058 |
| counterfactual.baseline.profit_factor | 1.250057 |
| counterfactual.breakeven_after_0_5r.trade_count | 691 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.201293 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.020260 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.458490 |
| counterfactual.breakeven_after_1_0r.trade_count | 691 |
| counterfactual.breakeven_after_1_0r.avg_r | -0.231383 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.108538 |
| counterfactual.breakeven_after_1_0r.profit_factor | 0.697330 |
| counterfactual.exit_at_first_0_5r.trade_count | 691 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.092162 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.929088 |
| counterfactual.exit_at_first_0_5r.profit_factor | 1.247930 |
| counterfactual.exit_at_first_1_0r.trade_count | 691 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.072229 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.845152 |
| counterfactual.exit_at_first_1_0r.profit_factor | 1.094482 |
| counterfactual.partial_50pct_at_1r.trade_count | 691 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.295494 |
| counterfactual.partial_50pct_at_1r.median_r | 0.720658 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.642547 |
| counterfactual.partial_50pct_at_1r.profit_factor | 1.227536 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 691 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.609377 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.173133 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.526773 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.331594 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 691 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.187323 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.759946 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.845152 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 1.245036 |
| counterfactual.best_policy_by_avg_r | time_exit_after_4_bars_if_mfe_lt_0_3r |
| counterfactual.best_policy_by_profit_factor | time_exit_after_4_bars_if_mfe_lt_0_3r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 1 | -4.632040 | -4.632040 | 0.0 | 0.390037 | -6.037772 | 5.022077 | 24.000000 | 0.0 | 1.000000 | 0.0 | 0.0 |
| reversal | 690 | 0.526223 | 0.464974 | 0.560870 | 4.885641 | -4.436465 | 4.359417 | 63.453623 | 1.254110 | 0.995652 | 0.900000 | 0.815942 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 0 |
| gross_pnl | 2.165936 |
| net_pnl | 2.059409 |
| total_cost | 0.106527 |
| cost_to_gross_pnl | 0.049183 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 43800 |
| actual_trade_count | 0 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 5.105845 |
| sharpe | 2.372487 |
| sortino | 3.497547 |
| calmar | 2.923164 |
| max_drawdown | -0.363321 |
| profit_factor | 1.056878 |
| hit_rate | 0.499254 |
| gross_pnl | 2.165936 |
| net_pnl | 2.059409 |
| total_cost | 0.106527 |
| cost_to_gross_pnl | 0.049183 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 5.067121 |
| cost_x1.annualized_return | 0.532725 |
| cost_x1.annualized_vol | 0.344535 |
| cost_x1.sharpe | 1.546213 |
| cost_x1.max_drawdown | -0.363321 |
| cost_x1.profit_factor | 1.056683 |
| cost_x1.hit_rate | 0.499255 |
| cost_x2.cumulative_return | 4.453848 |
| cost_x2.annualized_return | 0.494521 |
| cost_x2.annualized_vol | 0.344526 |
| cost_x2.sharpe | 1.435367 |
| cost_x2.max_drawdown | -0.368246 |
| cost_x2.profit_factor | 1.053655 |
| cost_x2.hit_rate | 0.498154 |
| cost_x3.cumulative_return | 3.902515 |
| cost_x3.annualized_return | 0.457266 |
| cost_x3.annualized_vol | 0.344523 |
| cost_x3.sharpe | 1.327240 |
| cost_x3.max_drawdown | -0.373135 |
| cost_x3.profit_factor | 1.050631 |
| cost_x3.hit_rate | 0.497213 |
| cost_x5.cumulative_return | 2.961291 |
| cost_x5.annualized_return | 0.385507 |
| cost_x5.annualized_vol | 0.344540 |
| cost_x5.sharpe | 1.118903 |
| cost_x5.max_drawdown | -0.382799 |
| cost_x5.profit_factor | 1.044602 |
| cost_x5.hit_rate | 0.495654 |

### Entry Delay
| Metric | Value |
| --- | --- |
| delay_1_bars.cumulative_return | 4.093341 |
| delay_1_bars.annualized_return | 0.299075 |
| delay_1_bars.annualized_vol | 0.283785 |
| delay_1_bars.sharpe | 1.053879 |
| delay_1_bars.max_drawdown | -0.367263 |
| delay_1_bars.profit_factor | 1.051761 |
| delay_1_bars.hit_rate | 0.498532 |
| delay_2_bars.cumulative_return | 4.688814 |
| delay_2_bars.annualized_return | 0.322367 |
| delay_2_bars.annualized_vol | 0.284469 |
| delay_2_bars.sharpe | 1.133223 |
| delay_2_bars.max_drawdown | -0.320541 |
| delay_2_bars.profit_factor | 1.054918 |
| delay_2_bars.hit_rate | 0.498498 |

### Walk Forward
| Metric | Value |
| --- | --- |
| fold_count | 5 |
| positive_fold_count | 3 |
| positive_fold_ratio | 0.600000 |
| min_fold_cumulative_return | 0.0 |
| median_fold_cumulative_return | 0.202126 |
| mean_fold_cumulative_return | 0.539142 |
| mean_fold_sharpe | 1.504346 |
| std_fold_sharpe | 1.654744 |
| worst_fold_max_drawdown | -0.363321 |

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
| oos_prediction.mean | -0.010636 |
| oos_prediction.std | 0.974568 |
| oos_prediction.min | -4.183777 |
| oos_prediction.max | 3.706707 |
| oos_prediction.median | -0.000887 |
| oos_prediction.q01 | -2.492384 |
| oos_prediction.q05 | -1.663680 |
| oos_prediction.q25 | -0.610015 |
| oos_prediction.q75 | 0.614556 |
| oos_prediction.q95 | 1.585182 |
| oos_prediction.q99 | 2.284676 |
| oos_prediction.skew | -0.125653 |
| oos_prediction.kurtosis | 0.403181 |
| oos_prediction.positive_rate | 0.499658 |
| oos_prediction.negative_rate | 0.500342 |
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
| 1 | atr_48 | 1.126e+03 | 0.104347 | 10 | feature_importances_ |
| 2 | vol_rolling_192 | 1.077e+03 | 0.099726 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 940.500000 | 0.087095 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 783.100000 | 0.072530 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 727.200000 | 0.067374 | 10 | feature_importances_ |
| 6 | bollinger_bandwidth_rank_192 | 600.400000 | 0.055616 | 10 | feature_importances_ |
| 7 | atr_over_price_48 | 578.500000 | 0.053585 | 10 | feature_importances_ |
| 8 | vol_rolling_48 | 551.900000 | 0.051108 | 10 | feature_importances_ |
| 9 | atr_pct_rank_192 | 478.900000 | 0.044367 | 10 | feature_importances_ |
| 10 | vol_rolling_24 | 423.100000 | 0.039193 | 10 | feature_importances_ |
| 11 | mama_minus_fama_over_atr | 413.800000 | 0.038323 | 10 | feature_importances_ |
| 12 | ret_48 | 311.300000 | 0.028848 | 10 | feature_importances_ |
| 13 | close_over_bb_upper_192 | 307.400000 | 0.028482 | 10 | feature_importances_ |
| 14 | close_over_bb_mid_192 | 289.800000 | 0.026838 | 10 | feature_importances_ |
| 15 | bollinger_percent_b | 253.700000 | 0.023491 | 10 | feature_importances_ |
| 16 | distance_from_ema96_atr | 184.400000 | 0.017084 | 10 | feature_importances_ |
| 17 | ret_24 | 180.600000 | 0.016723 | 10 | feature_importances_ |
| 18 | roofing_filter_over_atr | 162.600000 | 0.015061 | 10 | feature_importances_ |
| 19 | atr_pct | 135.400000 | 0.012545 | 10 | feature_importances_ |
| 20 | ret_16 | 131.400000 | 0.012163 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 2.165936 |
| net_pnl | 2.059409 |
| total_cost | 0.106527 |
| cost_drag | 0.106527 |
| cost_to_gross_pnl | 0.049183 |
| avg_turnover | 0.024321 |
| total_turnover | 1.065e+03 |
| mean_abs_signal | 0.571818 |
| signal_turnover | 0.168129 |
| flat_rate | 0.0 |
| long_rate | 0.499498 |
| short_rate | 0.500502 |
| trade_rate | 1.000000 |
| executed_trade_count | 43800 |
| avg_signal_executed | 0.001303 |
| avg_pred_prob_executed | 0.497021 |
| avg_realized_r_executed |  |

## Diagnostics
- The policy never meaningfully abstains; it chooses direction almost all the time instead of learning a true hold state.
- Fold outcomes are mixed, which points to regime dependence rather than a stable cross-period edge.
- Feature drift is present in OOS inputs; the largest drifted features are atr_48, atr_over_price_48, atr_pct, vol_rolling_192, vol_rolling_96.

## Charts
### Diagnostics Cost Vs Gross Pnl
![Diagnostics Cost Vs Gross Pnl](artifacts/diagnostics/cost_vs_gross_pnl.png)

### Diagnostics Lgbm Gain Importance
![Diagnostics Lgbm Gain Importance](artifacts/diagnostics/lgbm_gain_importance.png)

### Diagnostics Lgbm Split Importance
![Diagnostics Lgbm Split Importance](artifacts/diagnostics/lgbm_split_importance.png)

### Diagnostics Prediction Autocorrelation
![Diagnostics Prediction Autocorrelation](artifacts/diagnostics/prediction_autocorrelation.png)

### Diagnostics Prediction Histogram
![Diagnostics Prediction Histogram](artifacts/diagnostics/prediction_histogram.png)

### Diagnostics Prediction Quantiles
![Diagnostics Prediction Quantiles](artifacts/diagnostics/prediction_quantiles.png)

### Diagnostics Prediction Timeseries
![Diagnostics Prediction Timeseries](artifacts/diagnostics/prediction_timeseries.png)

### Diagnostics Prediction Vs Realized
![Diagnostics Prediction Vs Realized](artifacts/diagnostics/prediction_vs_realized.png)

### Diagnostics Residual Histogram
![Diagnostics Residual Histogram](artifacts/diagnostics/residual_histogram.png)

### Diagnostics Shap Dependence Atr 48
![Diagnostics Shap Dependence Atr 48](artifacts/diagnostics/shap_dependence_atr_48.png)

### Diagnostics Shap Dependence Atr Over Price 48
![Diagnostics Shap Dependence Atr Over Price 48](artifacts/diagnostics/shap_dependence_atr_over_price_48.png)

### Diagnostics Shap Dependence Ema Trend 48 192
![Diagnostics Shap Dependence Ema Trend 48 192](artifacts/diagnostics/shap_dependence_ema_trend_48_192.png)

### Diagnostics Shap Dependence Vol Rolling 192
![Diagnostics Shap Dependence Vol Rolling 192](artifacts/diagnostics/shap_dependence_vol_rolling_192.png)

### Diagnostics Shap Dependence Vol Rolling 24
![Diagnostics Shap Dependence Vol Rolling 24](artifacts/diagnostics/shap_dependence_vol_rolling_24.png)

### Diagnostics Shap Dependence Vol Rolling 96
![Diagnostics Shap Dependence Vol Rolling 96](artifacts/diagnostics/shap_dependence_vol_rolling_96.png)

### Diagnostics Shap Summary
![Diagnostics Shap Summary](artifacts/diagnostics/shap_summary.png)

### Diagnostics Turnover Timeseries
![Diagnostics Turnover Timeseries](artifacts/diagnostics/turnover_timeseries.png)

### Diagnostics Turnover Vs Net Pnl
![Diagnostics Turnover Vs Net Pnl](artifacts/diagnostics/turnover_vs_net_pnl.png)

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
| 0 |  | 0.258911 | 0.247199 | 0.011712 | 2.049459 | 0.026740 |  |  |  |  |
| 1 |  | 0.812706 | 0.803174 | 0.009532 | 23.342366 | 0.021763 |  |  |  |  |
| 2 |  | -0.064911 | -0.076228 | 0.011317 | -0.669694 | 0.025837 |  |  |  |  |
| 3 |  | 0.442421 | 0.431259 | 0.011162 | 10.711791 | 0.025485 |  |  |  |  |
| 4 |  | 0.338275 | 0.326226 | 0.012049 | 7.950943 | 0.027510 |  |  |  |  |
| 5 |  | 0.097798 | 0.086741 | 0.011057 | 1.409781 | 0.025244 |  |  |  |  |
| 6 |  | -0.088585 | -0.097736 | 0.009151 | -1.262760 | 0.020892 |  |  |  |  |
| 7 |  | 0.062875 | 0.052340 | 0.010535 | 0.380490 | 0.024053 |  |  |  |  |
| 8 |  | 0.153299 | 0.143718 | 0.009581 | 1.746657 | 0.021874 |  |  |  |  |
| 9 |  | 0.159701 | 0.149618 | 0.010083 | 1.712863 | 0.023021 |  |  |  |  |


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
  kind: lightgbm_regressor
  params:
    n_estimators: 800
    learning_rate: 0.0549537895493607
    max_depth: 6
    num_leaves: 15
    min_child_samples: 200
    subsample: 0.9
    colsample_bytree: 0.75
    reg_alpha: 0.019934229992965794
    reg_lambda: 1.8786413727433209
    random_state: 7
    n_jobs: 1
    verbosity: -1
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
  kind: dense_return_forecast
  params:
    forecast_col: pred_ret
    signal_col: signal_dense_net
    expected_net_return_col: expected_net_return
    estimated_cost_col: estimated_round_trip_cost
    cost_per_turnover: 0.0001
    slippage_per_turnover: 0.0
    cost_round_trip_mult: 2.0
    forecast_is_vol_normalized: true
    volatility_col: atr_48
    price_col: close
    volatility_floor: 1.0e-12
    signed_cost_adjustment: true
    clip: 1.0
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
  signal_col: signal_dense_net
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
- `diagnostics_lightgbm_importance`: `artifacts/diagnostics/lightgbm_importance.csv`
- `diagnostics_prediction_autocorrelation`: `artifacts/diagnostics/prediction_autocorrelation.png`
- `diagnostics_prediction_distribution`: `artifacts/diagnostics/prediction_distribution.csv`
- `diagnostics_prediction_metrics`: `artifacts/diagnostics/prediction_metrics.csv`
- `diagnostics_prediction_quantiles`: `artifacts/diagnostics/prediction_quantiles.png`
- `diagnostics_regime_diagnostics`: `artifacts/diagnostics/regime_diagnostics.csv`
- `diagnostics_regime_performance`: `artifacts/diagnostics/regime_performance.csv`
- `diagnostics_shap_feature_importance`: `artifacts/diagnostics/shap_feature_importance.csv`
- `diagnostics_shap_per_prediction`: `artifacts/diagnostics/shap_per_prediction.csv`
- `diagnostics_shap_status`: `artifacts/diagnostics/shap_status.csv`
- `diagnostics_shap_values_sample`: `artifacts/diagnostics/shap_values_sample.csv`
- `diagnostics_summary`: `artifacts/diagnostics/summary.json`
- `diagnostics_threshold_grid`: `artifacts/diagnostics/threshold_grid.csv`
- `diagnostics_turnover_cost_timeseries`: `artifacts/diagnostics/turnover_cost_timeseries.csv`
- `diagnostics_cost_vs_gross_pnl`: `artifacts/diagnostics/cost_vs_gross_pnl.png`
- `diagnostics_lgbm_gain_importance`: `artifacts/diagnostics/lgbm_gain_importance.png`
- `diagnostics_lgbm_split_importance`: `artifacts/diagnostics/lgbm_split_importance.png`
- `diagnostics_prediction_histogram`: `artifacts/diagnostics/prediction_histogram.png`
- `diagnostics_prediction_timeseries`: `artifacts/diagnostics/prediction_timeseries.png`
- `diagnostics_prediction_vs_realized`: `artifacts/diagnostics/prediction_vs_realized.png`
- `diagnostics_residual_histogram`: `artifacts/diagnostics/residual_histogram.png`
- `diagnostics_shap_dependence_atr_48`: `artifacts/diagnostics/shap_dependence_atr_48.png`
- `diagnostics_shap_dependence_atr_over_price_48`: `artifacts/diagnostics/shap_dependence_atr_over_price_48.png`
- `diagnostics_shap_dependence_ema_trend_48_192`: `artifacts/diagnostics/shap_dependence_ema_trend_48_192.png`
- `diagnostics_shap_dependence_vol_rolling_192`: `artifacts/diagnostics/shap_dependence_vol_rolling_192.png`
- `diagnostics_shap_dependence_vol_rolling_24`: `artifacts/diagnostics/shap_dependence_vol_rolling_24.png`
- `diagnostics_shap_dependence_vol_rolling_96`: `artifacts/diagnostics/shap_dependence_vol_rolling_96.png`
- `diagnostics_shap_summary`: `artifacts/diagnostics/shap_summary.png`
- `diagnostics_turnover_timeseries`: `artifacts/diagnostics/turnover_timeseries.png`
- `diagnostics_turnover_vs_net_pnl`: `artifacts/diagnostics/turnover_vs_net_pnl.png`
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
