# Experiment Report: ethusd_30m_trial0041_norm_return_over_vol48_v1

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/04_normalization_lab/ethusd_30m_trial0041_norm_return_over_vol48_v1.yaml`
- Model kind: `lightgbm_regressor`
- Symbols: `ETHUSD`
- Data source: `dukascopy_csv` at interval `30m`
- Data window: `None` to `2026-06-09 23:30:00`
- Rows / columns: `109005` rows, `127` columns
- Target: `future_return_regression` horizon `24`
- Feature count: `47`
- Runtime seed: `7`

## Pipeline Trace

### 1. Entry Point
- `runner.run_experiment` -> `src.experiments.runner.run_experiment(config_path: 'str | Path') -> 'ExperimentResult'`
- `runner._load_asset_frames` -> `src.experiments.runner._load_asset_frames(data_cfg: 'dict[str, object]')`
- `pipeline.run_experiment_pipeline` -> `src.experiments.orchestration.pipeline.run_experiment_pipeline(config_path: 'str | Path', *, load_asset_frames_fn: 'LoadAssetFramesFn', save_processed_snapshot_fn: 'SaveProcessedFn') -> 'ExperimentResult'`

```yaml
config_path: /workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/04_normalization_lab/ethusd_30m_trial0041_norm_return_over_vol48_v1.yaml
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
  normalizations:
    volatility_scaled_return:
      params:
        return_col: close_ret
        volatility_col: vol_rolling_48
        output_col: close_ret_over_vol_48
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
- close_ret_over_vol_48
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
  - close_ret_over_vol_48
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
| cumulative_return | 3.947097 |
| annualized_return | 0.895572 |
| annualized_vol | 0.301644 |
| sharpe | 2.968966 |
| sortino | 4.708109 |
| calmar | 4.779211 |
| max_drawdown | -0.187389 |
| profit_factor | 1.148717 |
| hit_rate | 0.490089 |
| avg_turnover | 0.014132 |
| total_turnover | 619.000000 |
| gross_pnl | 1.773717 |
| net_pnl | 1.711817 |
| total_cost | 0.061900 |
| cost_drag | 0.061900 |
| cost_to_gross_pnl | 0.034898 |
| flat_rate | 0.957260 |
| long_rate | 0.024795 |
| short_rate | 0.017945 |
| trade_count | 310 |
| average_r | 0.581304 |
| median_r | 0.608039 |
| avg_max_favorable_r | 3.424441 |
| avg_max_adverse_r | -2.846544 |
| loser_was_positive_rate | 0.976378 |
| avg_giveback_r | 2.843137 |
| avg_capture_ratio | -7.794671 |
| robustness_walk_forward_positive_fold_ratio | 0.600000 |
| robustness_walk_forward_min_fold_cumulative_return | 0.0 |
| robustness_walk_forward_worst_fold_max_drawdown | -0.162848 |
| robustness_walk_forward_mean_fold_sharpe | 1.810870 |
| robustness_walk_forward_std_fold_sharpe | 2.117512 |
| robustness_cost_x1_cumulative_return | 3.878393 |
| robustness_cost_x1_sharpe | 1.958633 |
| robustness_cost_x1_max_drawdown | -0.187389 |
| robustness_cost_x1_profit_factor | 1.146890 |
| robustness_cost_x2_cumulative_return | 3.585078 |
| robustness_cost_x2_sharpe | 1.867312 |
| robustness_cost_x2_max_drawdown | -0.190149 |
| robustness_cost_x2_profit_factor | 1.140958 |
| robustness_cost_x3_cumulative_return | 3.309372 |
| robustness_cost_x3_sharpe | 1.777270 |
| robustness_cost_x3_max_drawdown | -0.192899 |
| robustness_cost_x3_profit_factor | 1.135067 |
| robustness_cost_x5_cumulative_return | 2.806625 |
| robustness_cost_x5_sharpe | 1.600977 |
| robustness_cost_x5_max_drawdown | -0.200410 |
| robustness_cost_x5_profit_factor | 1.123414 |
| robustness_delay_1_bars_cumulative_return | 3.392836 |
| robustness_delay_1_bars_sharpe | 1.418751 |
| robustness_delay_1_bars_max_drawdown | -0.182720 |
| robustness_delay_1_bars_profit_factor | 1.138473 |
| robustness_delay_2_bars_cumulative_return | 3.738972 |
| robustness_delay_2_bars_sharpe | 1.506921 |
| robustness_delay_2_bars_max_drawdown | -0.183993 |
| robustness_delay_2_bars_profit_factor | 1.146340 |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.042740 |
| signal_turnover | 0.051005 |
| long_rate | 0.024795 |
| short_rate | 0.017945 |
| flat_rate | 0.957260 |
| executed_trade_count | 7451 |
| trade_rate | 0.170114 |
| avg_signal_executed | 0.041203 |
| avg_pred_prob_executed | 0.520943 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.523995 |
| classification.brier | 0.283708 |
| classification.roc_auc | 0.527914 |
| classification.log_loss | 0.787163 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.173614 |
| regression.rmse | 2.639671 |
| regression.mse | 6.967862 |
| regression.r2 | -0.115933 |
| regression.correlation | 0.047703 |
| regression.directional_accuracy | 0.523904 |
| regression.mean_prediction | -0.017278 |
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
| prediction_distribution.mean | -0.017278 |
| prediction_distribution.std | 0.978076 |
| prediction_distribution.min | -4.583988 |
| prediction_distribution.max | 4.163758 |
| prediction_distribution.median | 0.010614 |
| prediction_distribution.q01 | -2.567341 |
| prediction_distribution.q05 | -1.705482 |
| prediction_distribution.q25 | -0.610701 |
| prediction_distribution.q75 | 0.615397 |
| prediction_distribution.q95 | 1.555855 |
| prediction_distribution.q99 | 2.255257 |
| prediction_distribution.skew | -0.214476 |
| prediction_distribution.kurtosis | 0.526824 |
| prediction_distribution.positive_rate | 0.504726 |
| prediction_distribution.negative_rate | 0.495274 |
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
| probability_distribution.mean | 0.496111 |
| probability_distribution.std | 0.207950 |
| probability_distribution.min | 0.006701 |
| probability_distribution.max | 0.985966 |
| probability_distribution.median | 0.502923 |
| probability_distribution.q01 | 0.066941 |
| probability_distribution.q05 | 0.142870 |
| probability_distribution.q25 | 0.341182 |
| probability_distribution.q75 | 0.656429 |
| probability_distribution.q95 | 0.826405 |
| probability_distribution.q99 | 0.907112 |
| probability_distribution.skew | -0.085491 |
| probability_distribution.kurtosis | -0.769209 |
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
| model_strategy | 3.947097 | 0.895572 | 0.301644 | 2.968966 | 4.708109 | 4.779211 | -0.187389 | 1.148717 | 0.490089 | 619.000000 | 0.034898 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | -0.089284 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000224 |
| random_sign_same_rate | 1.350835 | 0.407631 | 0.382543 | 1.065582 | 1.544068 | 1.232241 | -0.330805 | 1.047218 | 0.482521 | 1.270e+03 | 0.109050 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | -0.240522 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.789225 |
| simple_trend | -0.867002 | -0.553792 | 0.665797 | -0.831772 | -1.181822 | -0.608132 | -0.910644 | 0.978047 | 0.491683 | 1.545e+03 | 0.118038 |


## Threshold Grid
| Name | Upper | Lower | Net PnL | Sharpe | Max DD | Profit Factor | Cost/Gross | Turnover | Active Rows | Profitable Folds | Median Fold Return | Worst 3-Fold Avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sym_0.35 | 0.350000 | -0.350000 | 3.386812 | 1.574701 | -0.423123 | 1.044867 | 0.088999 | 1.765e+03 | 3.051e+04 | 8.000000 | 0.134279 | -0.044041 |
| sym_0.5 | 0.500000 | -0.500000 | 2.922523 | 1.479322 | -0.461503 | 1.045047 | 0.092120 | 1.693e+03 | 2.543e+04 | 7.000000 | 0.180201 | -0.123570 |
| sym_0.75 | 0.750000 | -0.750000 | 3.766332 | 1.841139 | -0.331132 | 1.057491 | 0.077532 | 1.545e+03 | 1.804e+04 | 7.000000 | 0.155631 | -0.093136 |
| sym_1 | 1.000000 | -1.000000 | 2.258646 | 1.372322 | -0.362400 | 1.052383 | 0.086402 | 1.346e+03 | 1.229e+04 | 8.000000 | 0.107736 | 0.000318 |
| sym_1.25 | 1.250000 | -1.250000 | 0.646215 | 0.574765 | -0.377096 | 1.032278 | 0.134627 | 1.062e+03 | 8.218e+03 | 7.000000 | 0.044951 | -0.093751 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.087267 |
| mean_fold_return | 0.191911 |
| fold_return_std | 0.226736 |
| worst_fold_return | -0.082484 |
| best_fold_return | 0.596308 |
| worst_3_fold_average_return | -0.010139 |
| profitable_fold_count | 9.000000 |
| profitable_fold_rate | 0.900000 |
| median_fold_sharpe | 1.549949 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.4, 'best_rank': 1, 'mean_importance': 1115.2, 'mean_importance_normalized': 0.10292579872203271, 'folds': [{'fold': 0, 'rank': 1, 'importance': 1152.0, 'importance_normalized': 0.11047180667433831}, {'fold': 1, 'rank': 1, 'importance': 1141.0, 'importance_normalized': 0.1056285872986484}, {'fold': 2, 'rank': 1, 'importance': 1173.0, 'importance_normalized': 0.10710372534696859}, {'fold': 3, 'rank': 1, 'importance': 1170.0, 'importance_normalized': 0.1075763148216256}, {'fold': 4, 'rank': 1, 'importance': 1126.0, 'importance_normalized': 0.103664150248573}, {'fold': 5, 'rank': 2, 'importance': 1068.0, 'importance_normalized': 0.09814372358022422}, {'fold': 6, 'rank': 1, 'importance': 1108.0, 'importance_normalized': 0.10226119058606369}, {'fold': 7, 'rank': 2, 'importance': 1042.0, 'importance_normalized': 0.09556126192223037}, {'fold': 8, 'rank': 2, 'importance': 1041.0, 'importance_normalized': 0.09529476382277555}, {'fold': 9, 'rank': 2, 'importance': 1131.0, 'importance_normalized': 0.10355246291887933}], 'stability_rank': 1}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.6, 'best_rank': 1, 'mean_importance': 1081.6, 'mean_importance_normalized': 0.09975225055335007, 'folds': [{'fold': 0, 'rank': 2, 'importance': 966.0, 'importance_normalized': 0.09263521288837745}, {'fold': 1, 'rank': 2, 'importance': 1016.0, 'importance_normalized': 0.09405665617478244}, {'fold': 2, 'rank': 2, 'importance': 1054.0, 'importance_normalized': 0.09623813002191381}, {'fold': 3, 'rank': 2, 'importance': 1021.0, 'importance_normalized': 0.09387642515630747}, {'fold': 4, 'rank': 2, 'importance': 1083.0, 'importance_normalized': 0.0997053949548886}, {'fold': 5, 'rank': 1, 'importance': 1108.0, 'importance_normalized': 0.10181951847086933}, {'fold': 6, 'rank': 2, 'importance': 1085.0, 'importance_normalized': 0.10013844023996309}, {'fold': 7, 'rank': 1, 'importance': 1153.0, 'importance_normalized': 0.10574101247248716}, {'fold': 8, 'rank': 1, 'importance': 1144.0, 'importance_normalized': 0.1047235444891981}, {'fold': 9, 'rank': 1, 'importance': 1186.0, 'importance_normalized': 0.10858817066471342}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 3.0, 'best_rank': 3, 'mean_importance': 932.1, 'mean_importance_normalized': 0.08598523388728825, 'folds': [{'fold': 0, 'rank': 3, 'importance': 871.0, 'importance_normalized': 0.08352512466436517}, {'fold': 1, 'rank': 3, 'importance': 930.0, 'importance_normalized': 0.08609516756156267}, {'fold': 2, 'rank': 3, 'importance': 898.0, 'importance_normalized': 0.08199415631848064}, {'fold': 3, 'rank': 3, 'importance': 966.0, 'importance_normalized': 0.08881941890400882}, {'fold': 4, 'rank': 3, 'importance': 915.0, 'importance_normalized': 0.08423863008654023}, {'fold': 5, 'rank': 3, 'importance': 897.0, 'importance_normalized': 0.08242970042271641}, {'fold': 6, 'rank': 3, 'importance': 917.0, 'importance_normalized': 0.08463313336409783}, {'fold': 7, 'rank': 3, 'importance': 942.0, 'importance_normalized': 0.08639031548055759}, {'fold': 8, 'rank': 3, 'importance': 989.0, 'importance_normalized': 0.09053460270963017}, {'fold': 9, 'rank': 3, 'importance': 996.0, 'importance_normalized': 0.0911920893609229}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.2, 'best_rank': 4, 'mean_importance': 793.6, 'mean_importance_normalized': 0.07317833735964126, 'folds': [{'fold': 0, 'rank': 5, 'importance': 677.0, 'importance_normalized': 0.06492136555427695}, {'fold': 1, 'rank': 5, 'importance': 718.0, 'importance_normalized': 0.06646917237548602}, {'fold': 2, 'rank': 4, 'importance': 796.0, 'importance_normalized': 0.07268078889700512}, {'fold': 3, 'rank': 4, 'importance': 768.0, 'importance_normalized': 0.07061419639573373}, {'fold': 4, 'rank': 4, 'importance': 816.0, 'importance_normalized': 0.07512428650340637}, {'fold': 5, 'rank': 4, 'importance': 852.0, 'importance_normalized': 0.07829443117074067}, {'fold': 6, 'rank': 4, 'importance': 825.0, 'importance_normalized': 0.07614213197969544}, {'fold': 7, 'rank': 4, 'importance': 795.0, 'importance_normalized': 0.0729090242112986}, {'fold': 8, 'rank': 4, 'importance': 837.0, 'importance_normalized': 0.07662028560966679}, {'fold': 9, 'rank': 4, 'importance': 852.0, 'importance_normalized': 0.07800769089910273}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.8, 'best_rank': 4, 'mean_importance': 752.4, 'mean_importance_normalized': 0.06942144982230228, 'folds': [{'fold': 0, 'rank': 4, 'importance': 737.0, 'importance_normalized': 0.07067510548523206}, {'fold': 1, 'rank': 4, 'importance': 741.0, 'importance_normalized': 0.06859840770227736}, {'fold': 2, 'rank': 5, 'importance': 757.0, 'importance_normalized': 0.06911979547114683}, {'fold': 3, 'rank': 5, 'importance': 694.0, 'importance_normalized': 0.06381022434718646}, {'fold': 4, 'rank': 5, 'importance': 774.0, 'importance_normalized': 0.07125759528631928}, {'fold': 5, 'rank': 5, 'importance': 749.0, 'importance_normalized': 0.06882925932732953}, {'fold': 6, 'rank': 5, 'importance': 756.0, 'importance_normalized': 0.06977388094139363}, {'fold': 7, 'rank': 5, 'importance': 755.0, 'importance_normalized': 0.06924064563462949}, {'fold': 8, 'rank': 5, 'importance': 773.0, 'importance_normalized': 0.07076162577810326}, {'fold': 9, 'rank': 5, 'importance': 788.0, 'importance_normalized': 0.07214795824940487}], 'stability_rank': 5}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.5, 'best_rank': 6, 'mean_importance': 600.0, 'mean_importance_normalized': 0.055355495835080204, 'folds': [{'fold': 0, 'rank': 6, 'importance': 572.0, 'importance_normalized': 0.05485232067510549}, {'fold': 1, 'rank': 6, 'importance': 602.0, 'importance_normalized': 0.05573042029253842}, {'fold': 2, 'rank': 6, 'importance': 601.0, 'importance_normalized': 0.05487582176771366}, {'fold': 3, 'rank': 8, 'importance': 588.0, 'importance_normalized': 0.054063994115483634}, {'fold': 4, 'rank': 7, 'importance': 611.0, 'importance_normalized': 0.05625115080095747}, {'fold': 5, 'rank': 6, 'importance': 610.0, 'importance_normalized': 0.0560558720823378}, {'fold': 6, 'rank': 6, 'importance': 591.0, 'importance_normalized': 0.05454545454545454}, {'fold': 7, 'rank': 6, 'importance': 638.0, 'importance_normalized': 0.05851063829787234}, {'fold': 8, 'rank': 6, 'importance': 623.0, 'importance_normalized': 0.05703039179787624}, {'fold': 9, 'rank': 8, 'importance': 564.0, 'importance_normalized': 0.05163889397546237}], 'stability_rank': 6}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.8, 'best_rank': 6, 'mean_importance': 579.7, 'mean_importance_normalized': 0.053480546755417815, 'folds': [{'fold': 0, 'rank': 7, 'importance': 546.0, 'importance_normalized': 0.0523590333716916}, {'fold': 1, 'rank': 7, 'importance': 577.0, 'importance_normalized': 0.05341603406776523}, {'fold': 2, 'rank': 7, 'importance': 591.0, 'importance_normalized': 0.0539627465303141}, {'fold': 3, 'rank': 6, 'importance': 616.0, 'importance_normalized': 0.05663847002574476}, {'fold': 4, 'rank': 6, 'importance': 626.0, 'importance_normalized': 0.057632111949917145}, {'fold': 5, 'rank': 7, 'importance': 606.0, 'importance_normalized': 0.05568829259327329}, {'fold': 6, 'rank': 7, 'importance': 552.0, 'importance_normalized': 0.050946008306414395}, {'fold': 7, 'rank': 7, 'importance': 527.0, 'importance_normalized': 0.048330887747615556}, {'fold': 8, 'rank': 7, 'importance': 569.0, 'importance_normalized': 0.05208714756499451}, {'fold': 9, 'rank': 7, 'importance': 587.0, 'importance_normalized': 0.053744735396447536}], 'stability_rank': 7}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.8, 'best_rank': 6, 'mean_importance': 544.4, 'mean_importance_normalized': 0.05021811560922287, 'folds': [{'fold': 0, 'rank': 8, 'importance': 509.0, 'importance_normalized': 0.048810893747602606}, {'fold': 1, 'rank': 9, 'importance': 515.0, 'importance_normalized': 0.04767635623032772}, {'fold': 2, 'rank': 8, 'importance': 563.0, 'importance_normalized': 0.05140613586559532}, {'fold': 3, 'rank': 7, 'importance': 606.0, 'importance_normalized': 0.05571901434350864}, {'fold': 4, 'rank': 8, 'importance': 557.0, 'importance_normalized': 0.051279690664702636}, {'fold': 5, 'rank': 8, 'importance': 499.0, 'importance_normalized': 0.04585554126079765}, {'fold': 6, 'rank': 8, 'importance': 536.0, 'importance_normalized': 0.04946931241347485}, {'fold': 7, 'rank': 8, 'importance': 517.0, 'importance_normalized': 0.04741379310344827}, {'fold': 8, 'rank': 8, 'importance': 548.0, 'importance_normalized': 0.05016477480776273}, {'fold': 9, 'rank': 6, 'importance': 594.0, 'importance_normalized': 0.05438564365500824}], 'stability_rank': 8}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 8.9, 'best_rank': 8, 'mean_importance': 484.5, 'mean_importance_normalized': 0.044697045901644264, 'folds': [{'fold': 0, 'rank': 9, 'importance': 448.0, 'importance_normalized': 0.04296125815113157}, {'fold': 1, 'rank': 8, 'importance': 527.0, 'importance_normalized': 0.04878726161821885}, {'fold': 2, 'rank': 9, 'importance': 509.0, 'importance_normalized': 0.04647552958363769}, {'fold': 3, 'rank': 9, 'importance': 498.0, 'importance_normalized': 0.04578889297535859}, {'fold': 4, 'rank': 9, 'importance': 466.0, 'importance_normalized': 0.04290185969434727}, {'fold': 5, 'rank': 9, 'importance': 479.0, 'importance_normalized': 0.0440176438154751}, {'fold': 6, 'rank': 9, 'importance': 495.0, 'importance_normalized': 0.04568527918781726}, {'fold': 7, 'rank': 9, 'importance': 485.0, 'importance_normalized': 0.04447909024211299}, {'fold': 8, 'rank': 9, 'importance': 481.0, 'importance_normalized': 0.04403149029659465}, {'fold': 9, 'rank': 9, 'importance': 457.0, 'importance_normalized': 0.04184215345174876}], 'stability_rank': 9}, {'feature': 'mama_minus_fama_over_atr', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 10.4, 'best_rank': 10, 'mean_importance': 411.6, 'mean_importance_normalized': 0.03797699893392281, 'folds': [{'fold': 0, 'rank': 11, 'importance': 404.0, 'importance_normalized': 0.03874184886843115}, {'fold': 1, 'rank': 11, 'importance': 392.0, 'importance_normalized': 0.03628957600444362}, {'fold': 2, 'rank': 10, 'importance': 420.0, 'importance_normalized': 0.038349159970781595}, {'fold': 3, 'rank': 10, 'importance': 421.0, 'importance_normalized': 0.03870908422214049}, {'fold': 4, 'rank': 10, 'importance': 421.0, 'importance_normalized': 0.03875897624746824}, {'fold': 5, 'rank': 10, 'importance': 432.0, 'importance_normalized': 0.039698584818967105}, {'fold': 6, 'rank': 10, 'importance': 405.0, 'importance_normalized': 0.0373788647900323}, {'fold': 7, 'rank': 11, 'importance': 384.0, 'importance_normalized': 0.03521643433602348}, {'fold': 8, 'rank': 11, 'importance': 409.0, 'importance_normalized': 0.03744049798608568}, {'fold': 9, 'rank': 10, 'importance': 428.0, 'importance_normalized': 0.03918696209485442}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.930707 | 2.097484 | -0.282964 | 1.083552 | 0.063392 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.346077 | 1.374839 | -0.106580 | 1.119219 | 0.048174 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 2.072247 | 3.889130 | -0.210996 | 1.130436 | 0.039012 |
| ema_trend_48_192 | negative | 2.183e+04 | 2.578382 | 5.332366 | -0.155131 | 1.225844 | 0.023186 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.596127 | 1.630567 | -0.143895 | 1.085927 | 0.059121 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 1.200636 | 1.980804 | -0.267441 | 1.076583 | 0.046243 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 310 |
| average_r | 0.581304 |
| median_r | 0.608039 |
| avg_max_favorable_r | 3.424441 |
| avg_max_adverse_r | -2.846544 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.976378 |
| avg_giveback_r | 2.843137 |
| avg_capture_ratio | -7.794671 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.976378 |
| avg_mfe_r_of_losers | 1.195185 |
| median_mfe_r_of_losers | 0.941370 |
| avg_mfe_r_before_loss | 1.195185 |
| median_mfe_r_before_loss | 0.941370 |
| loser_reached_0_5r_rate | 0.724409 |
| loser_reached_1r_rate | 0.456693 |
| loser_reached_1_5r_rate | 0.259843 |
| loser_reached_2r_rate | 0.181102 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -7.794671 |
| median_capture_ratio | 0.301020 |
| avg_giveback_r | 2.843137 |
| median_giveback_r | 2.046889 |
| avg_giveback_r_winners | 1.864618 |
| avg_giveback_r_losers | 4.253130 |
| median_giveback_r_winners | 1.516010 |
| median_giveback_r_losers | 3.282473 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.994536 |
| winner_had_mae_below_minus_0_25r_rate | 0.841530 |
| winner_had_mae_below_minus_0_5r_rate | 0.688525 |
| winner_had_mae_below_minus_1r_rate | 0.453552 |
| avg_mae_r_of_winners | -1.257723 |
| median_mae_r_of_winners | -0.892150 |
| p90_abs_mae_r_of_winners | 2.775757 |
| avg_mae_r | -2.846544 |
| median_mae_r | -1.713415 |
| q10_mae_r | -7.025644 |
| q25_mae_r | -3.867228 |
| q75_mae_r | -0.760479 |
| q90_mae_r | -0.264453 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.590323 |
| prob_final_loss | 0.409677 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 1.000000 |
| prob_mfe_ge_0_5r | 0.887097 |
| prob_final_loss_given_mfe_ge_0_5r | 0.334545 |
| prob_mfe_ge_1r | 0.770968 |
| prob_final_loss_given_mfe_ge_1r | 0.242678 |
| prob_mfe_ge_1_5r | 0.670968 |
| prob_final_loss_given_mfe_ge_1_5r | 0.158654 |
| prob_mfe_ge_2r | 0.590323 |
| prob_final_loss_given_mfe_ge_2r | 0.125683 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 11.841935 |
| median_time_to_mfe | 12.000000 |
| avg_time_to_mae | 9.432258 |
| median_time_to_mae | 8.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.070968 |
| prob_mfe_ge_0_5r_within_2_bars | 0.119355 |
| prob_mfe_ge_1r_within_4_bars | 0.096774 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.581304 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.590323 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 310 |
| counterfactual.baseline.avg_r | 0.581304 |
| counterfactual.baseline.median_r | 0.608039 |
| counterfactual.baseline.win_rate | 0.590323 |
| counterfactual.baseline.profit_factor | 1.464015 |
| counterfactual.breakeven_after_0_5r.trade_count | 310 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.144601 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.006452 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.125747 |
| counterfactual.breakeven_after_1_0r.trade_count | 310 |
| counterfactual.breakeven_after_1_0r.avg_r | -0.088303 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.125806 |
| counterfactual.breakeven_after_1_0r.profit_factor | 0.834611 |
| counterfactual.exit_at_first_0_5r.trade_count | 310 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.315245 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.961290 |
| counterfactual.exit_at_first_0_5r.profit_factor | 2.905957 |
| counterfactual.exit_at_first_1_0r.trade_count | 310 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.323007 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.861290 |
| counterfactual.exit_at_first_1_0r.profit_factor | 1.604983 |
| counterfactual.partial_50pct_at_1r.trade_count | 310 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.452156 |
| counterfactual.partial_50pct_at_1r.median_r | 0.804019 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.693548 |
| counterfactual.partial_50pct_at_1r.profit_factor | 1.575782 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 310 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.570932 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.537086 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.574194 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.461838 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 310 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.506278 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.819678 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.861290 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 1.948246 |
| counterfactual.best_policy_by_avg_r | baseline |
| counterfactual.best_policy_by_profit_factor | exit_at_first_0_5r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 302 | 0.576178 | 0.588399 | 0.586093 | 3.415808 | -2.848629 | 2.839629 | 24.096026 | 1.461883 | 0.990066 | 0.887417 | 0.771523 |
| reversal | 8 | 0.774804 | 2.546880 | 0.750000 | 3.750362 | -2.767820 | 2.975558 | 24.375000 | 1.533095 | 1.000000 | 0.875000 | 0.750000 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 0 |
| gross_pnl | 1.773717 |
| net_pnl | 1.711817 |
| total_cost | 0.061900 |
| cost_to_gross_pnl | 0.034898 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1872 |
| actual_trade_count | 0 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 3.947097 |
| sharpe | 2.968966 |
| sortino | 4.708109 |
| calmar | 4.779211 |
| max_drawdown | -0.187389 |
| profit_factor | 1.148717 |
| hit_rate | 0.490089 |
| gross_pnl | 1.773717 |
| net_pnl | 1.711817 |
| total_cost | 0.061900 |
| cost_to_gross_pnl | 0.034898 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 3.878393 |
| cost_x1.annualized_return | 0.455564 |
| cost_x1.annualized_vol | 0.232593 |
| cost_x1.sharpe | 1.958633 |
| cost_x1.max_drawdown | -0.187389 |
| cost_x1.profit_factor | 1.146890 |
| cost_x1.hit_rate | 0.490247 |
| cost_x2.cumulative_return | 3.585078 |
| cost_x2.annualized_return | 0.434341 |
| cost_x2.annualized_vol | 0.232602 |
| cost_x2.sharpe | 1.867312 |
| cost_x2.max_drawdown | -0.190149 |
| cost_x2.profit_factor | 1.140958 |
| cost_x2.hit_rate | 0.489472 |
| cost_x3.cumulative_return | 3.309372 |
| cost_x3.annualized_return | 0.413425 |
| cost_x3.annualized_vol | 0.232618 |
| cost_x3.sharpe | 1.777270 |
| cost_x3.max_drawdown | -0.192899 |
| cost_x3.profit_factor | 1.135067 |
| cost_x3.hit_rate | 0.488697 |
| cost_x5.cumulative_return | 2.806625 |
| cost_x5.annualized_return | 0.372498 |
| cost_x5.annualized_vol | 0.232669 |
| cost_x5.sharpe | 1.600977 |
| cost_x5.max_drawdown | -0.200410 |
| cost_x5.profit_factor | 1.123414 |
| cost_x5.hit_rate | 0.488051 |

### Entry Delay
| Metric | Value |
| --- | --- |
| delay_1_bars.cumulative_return | 3.392836 |
| delay_1_bars.annualized_return | 0.268546 |
| delay_1_bars.annualized_vol | 0.189283 |
| delay_1_bars.sharpe | 1.418751 |
| delay_1_bars.max_drawdown | -0.182720 |
| delay_1_bars.profit_factor | 1.138473 |
| delay_1_bars.hit_rate | 0.489342 |
| delay_2_bars.cumulative_return | 3.738972 |
| delay_2_bars.annualized_return | 0.284105 |
| delay_2_bars.annualized_vol | 0.188533 |
| delay_2_bars.sharpe | 1.506921 |
| delay_2_bars.max_drawdown | -0.183993 |
| delay_2_bars.profit_factor | 1.146340 |
| delay_2_bars.hit_rate | 0.489216 |

### Walk Forward
| Metric | Value |
| --- | --- |
| fold_count | 5 |
| positive_fold_count | 3 |
| positive_fold_ratio | 0.600000 |
| min_fold_cumulative_return | 0.0 |
| median_fold_cumulative_return | 0.153472 |
| mean_fold_cumulative_return | 0.474767 |
| mean_fold_sharpe | 1.810870 |
| std_fold_sharpe | 2.117512 |
| worst_fold_max_drawdown | -0.162848 |

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
| oos_prediction.mean | -0.017278 |
| oos_prediction.std | 0.978076 |
| oos_prediction.min | -4.583988 |
| oos_prediction.max | 4.163758 |
| oos_prediction.median | 0.010614 |
| oos_prediction.q01 | -2.567341 |
| oos_prediction.q05 | -1.705482 |
| oos_prediction.q25 | -0.610701 |
| oos_prediction.q75 | 0.615397 |
| oos_prediction.q95 | 1.555855 |
| oos_prediction.q99 | 2.255257 |
| oos_prediction.skew | -0.214476 |
| oos_prediction.kurtosis | 0.526824 |
| oos_prediction.positive_rate | 0.504726 |
| oos_prediction.negative_rate | 0.495274 |
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
| 1 | atr_48 | 1.115e+03 | 0.102926 | 10 | feature_importances_ |
| 2 | vol_rolling_192 | 1.082e+03 | 0.099752 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 932.100000 | 0.085985 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 793.600000 | 0.073178 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 752.400000 | 0.069421 | 10 | feature_importances_ |
| 6 | bollinger_bandwidth_rank_192 | 600.000000 | 0.055355 | 10 | feature_importances_ |
| 7 | atr_over_price_48 | 579.700000 | 0.053481 | 10 | feature_importances_ |
| 8 | vol_rolling_48 | 544.400000 | 0.050218 | 10 | feature_importances_ |
| 9 | atr_pct_rank_192 | 484.500000 | 0.044697 | 10 | feature_importances_ |
| 10 | mama_minus_fama_over_atr | 411.600000 | 0.037977 | 10 | feature_importances_ |
| 11 | vol_rolling_24 | 404.800000 | 0.037360 | 10 | feature_importances_ |
| 12 | close_over_bb_mid_192 | 298.300000 | 0.027515 | 10 | feature_importances_ |
| 13 | close_over_bb_upper_192 | 296.500000 | 0.027372 | 10 | feature_importances_ |
| 14 | ret_48 | 289.800000 | 0.026738 | 10 | feature_importances_ |
| 15 | bollinger_percent_b | 243.100000 | 0.022418 | 10 | feature_importances_ |
| 16 | distance_from_ema96_atr | 193.200000 | 0.017830 | 10 | feature_importances_ |
| 17 | ret_24 | 184.900000 | 0.017052 | 10 | feature_importances_ |
| 18 | roofing_filter_over_atr | 168.700000 | 0.015561 | 10 | feature_importances_ |
| 19 | atr_pct | 155.700000 | 0.014370 | 10 | feature_importances_ |
| 20 | ret_16 | 144.200000 | 0.013309 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 1.773717 |
| net_pnl | 1.711817 |
| total_cost | 0.061900 |
| cost_drag | 0.061900 |
| cost_to_gross_pnl | 0.034898 |
| avg_turnover | 0.014132 |
| total_turnover | 619.000000 |
| mean_abs_signal | 0.042740 |
| signal_turnover | 0.051005 |
| flat_rate | 0.957260 |
| long_rate | 0.024795 |
| short_rate | 0.017945 |
| trade_rate | 0.170114 |
| executed_trade_count | 7451 |
| avg_signal_executed | 0.041203 |
| avg_pred_prob_executed | 0.520943 |
| avg_realized_r_executed |  |

## Diagnostics
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
| 0 |  | 0.251489 | 0.245089 | 0.006400 | 5.229020 | 0.014612 |  |  |  |  |
| 1 |  | 0.513022 | 0.505222 | 0.007800 | 9.989315 | 0.017808 |  |  |  |  |
| 2 |  | 0.367813 | 0.361013 | 0.006800 | 7.837524 | 0.015525 |  |  |  |  |
| 3 |  | 0.051822 | 0.044022 | 0.007800 | 0.604469 | 0.017808 |  |  |  |  |
| 4 |  | 0.054216 | 0.048816 | 0.005400 | 1.154058 | 0.012329 |  |  |  |  |
| 5 |  | -0.077268 | -0.083068 | 0.005800 | -1.877291 | 0.013242 |  |  |  |  |
| 6 |  | 0.026501 | 0.019701 | 0.006800 | 0.343762 | 0.015525 |  |  |  |  |
| 7 |  | 0.071153 | 0.065553 | 0.005600 | 1.045637 | 0.012785 |  |  |  |  |
| 8 |  | 0.122956 | 0.118656 | 0.004300 | 1.945840 | 0.009817 |  |  |  |  |
| 9 |  | 0.393079 | 0.387979 | 0.005100 | 12.179757 | 0.011644 |  |  |  |  |


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
- Drifted feature count: `8` / `47`
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
| unclassified | 34 | 3 | 0.088235 | 0.106539 | 1.195042 |
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
| 47 | close_ret_over_vol_48 |

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
  normalizations:
    volatility_scaled_return:
      params:
        return_col: close_ret
        volatility_col: vol_rolling_48
        output_col: close_ret_over_vol_48
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
  - close_ret_over_vol_48
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
