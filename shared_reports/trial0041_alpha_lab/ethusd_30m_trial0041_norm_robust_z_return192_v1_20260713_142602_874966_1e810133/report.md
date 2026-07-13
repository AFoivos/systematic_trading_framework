# Experiment Report: ethusd_30m_trial0041_norm_robust_z_return192_v1

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/04_normalization_lab/ethusd_30m_trial0041_norm_robust_z_return192_v1.yaml`
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
config_path: /workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/04_normalization_lab/ethusd_30m_trial0041_norm_robust_z_return192_v1.yaml
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
    robust_zscore:
      params:
        source_col: close_ret
        window: 192
        output_col: close_ret_robust_z_192
        shift_stats: true
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
- close_ret_robust_z_192
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
  - close_ret_robust_z_192
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
| cumulative_return | 3.703163 |
| annualized_return | 0.857616 |
| annualized_vol | 0.299082 |
| sharpe | 2.867496 |
| sortino | 4.556409 |
| calmar | 5.178192 |
| max_drawdown | -0.165621 |
| profit_factor | 1.140904 |
| hit_rate | 0.490898 |
| avg_turnover | 0.014475 |
| total_turnover | 634.000000 |
| gross_pnl | 1.722747 |
| net_pnl | 1.659347 |
| total_cost | 0.063400 |
| cost_drag | 0.063400 |
| cost_to_gross_pnl | 0.036802 |
| flat_rate | 0.956210 |
| long_rate | 0.025479 |
| short_rate | 0.018311 |
| trade_count | 317 |
| average_r | 0.593614 |
| median_r | 0.486118 |
| avg_max_favorable_r | 3.392307 |
| avg_max_adverse_r | -2.682182 |
| loser_was_positive_rate | 0.977444 |
| avg_giveback_r | 2.798693 |
| avg_capture_ratio | -4.604140 |
| robustness_walk_forward_positive_fold_ratio | 0.600000 |
| robustness_walk_forward_min_fold_cumulative_return | 0.0 |
| robustness_walk_forward_worst_fold_max_drawdown | -0.165621 |
| robustness_walk_forward_mean_fold_sharpe | 1.750693 |
| robustness_walk_forward_std_fold_sharpe | 1.938793 |
| robustness_cost_x1_cumulative_return | 3.703163 |
| robustness_cost_x1_sharpe | 1.924744 |
| robustness_cost_x1_max_drawdown | -0.165621 |
| robustness_cost_x1_profit_factor | 1.140904 |
| robustness_cost_x2_cumulative_return | 3.414270 |
| robustness_cost_x2_sharpe | 1.831360 |
| robustness_cost_x2_max_drawdown | -0.166124 |
| robustness_cost_x2_profit_factor | 1.134991 |
| robustness_cost_x3_cumulative_return | 3.143096 |
| robustness_cost_x3_sharpe | 1.739304 |
| robustness_cost_x3_max_drawdown | -0.166626 |
| robustness_cost_x3_profit_factor | 1.129119 |
| robustness_cost_x5_cumulative_return | 2.649626 |
| robustness_cost_x5_sharpe | 1.559123 |
| robustness_cost_x5_max_drawdown | -0.184932 |
| robustness_cost_x5_profit_factor | 1.117495 |
| robustness_delay_1_bars_cumulative_return | 3.132024 |
| robustness_delay_1_bars_sharpe | 1.362250 |
| robustness_delay_1_bars_max_drawdown | -0.183951 |
| robustness_delay_1_bars_profit_factor | 1.130465 |
| robustness_delay_2_bars_cumulative_return | 3.550034 |
| robustness_delay_2_bars_sharpe | 1.469032 |
| robustness_delay_2_bars_max_drawdown | -0.197559 |
| robustness_delay_2_bars_profit_factor | 1.139729 |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.043790 |
| signal_turnover | 0.051187 |
| long_rate | 0.025479 |
| short_rate | 0.018311 |
| flat_rate | 0.956210 |
| executed_trade_count | 7639 |
| trade_rate | 0.174406 |
| avg_signal_executed | 0.035476 |
| avg_pred_prob_executed | 0.517784 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.524589 |
| classification.brier | 0.283216 |
| classification.roc_auc | 0.529396 |
| classification.log_loss | 0.785899 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.171882 |
| regression.rmse | 2.637101 |
| regression.mse | 6.954301 |
| regression.r2 | -0.113762 |
| regression.correlation | 0.049069 |
| regression.directional_accuracy | 0.524475 |
| regression.mean_prediction | -0.019832 |
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
| prediction_distribution.mean | -0.019832 |
| prediction_distribution.std | 0.973977 |
| prediction_distribution.min | -4.544777 |
| prediction_distribution.max | 4.281687 |
| prediction_distribution.median | -0.005814 |
| prediction_distribution.q01 | -2.523928 |
| prediction_distribution.q05 | -1.683109 |
| prediction_distribution.q25 | -0.616327 |
| prediction_distribution.q75 | 0.603911 |
| prediction_distribution.q95 | 1.564759 |
| prediction_distribution.q99 | 2.263441 |
| prediction_distribution.skew | -0.148989 |
| prediction_distribution.kurtosis | 0.470121 |
| prediction_distribution.positive_rate | 0.497100 |
| prediction_distribution.negative_rate | 0.502900 |
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
| probability_distribution.mean | 0.494892 |
| probability_distribution.std | 0.207899 |
| probability_distribution.min | 0.008177 |
| probability_distribution.max | 0.986946 |
| probability_distribution.median | 0.498438 |
| probability_distribution.q01 | 0.069222 |
| probability_distribution.q05 | 0.141445 |
| probability_distribution.q25 | 0.339080 |
| probability_distribution.q75 | 0.655066 |
| probability_distribution.q95 | 0.828195 |
| probability_distribution.q99 | 0.907306 |
| probability_distribution.skew | -0.065687 |
| probability_distribution.kurtosis | -0.771914 |
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
| model_strategy | 3.703163 | 0.857616 | 0.299082 | 2.867496 | 4.556409 | 5.178192 | -0.165621 | 1.140904 | 0.490898 | 634.000000 | 0.036802 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | -0.089284 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000224 |
| random_sign_same_rate | 1.387394 | 0.416347 | 0.383326 | 1.086145 | 1.574092 | 1.256435 | -0.331372 | 1.047757 | 0.483141 | 1.274e+03 | 0.107858 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | -0.240522 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.789225 |
| simple_trend | -0.867002 | -0.553792 | 0.665797 | -0.831772 | -1.181822 | -0.608132 | -0.910644 | 0.978047 | 0.491683 | 1.545e+03 | 0.118038 |


## Threshold Grid
| Name | Upper | Lower | Net PnL | Sharpe | Max DD | Profit Factor | Cost/Gross | Turnover | Active Rows | Profitable Folds | Median Fold Return | Worst 3-Fold Avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sym_0.35 | 0.350000 | -0.350000 | 1.737430 | 0.972145 | -0.452276 | 1.033608 | 0.115386 | 1.738e+03 | 3.048e+04 | 7.000000 | 0.041901 | -0.086584 |
| sym_0.5 | 0.500000 | -0.500000 | 3.750074 | 1.772227 | -0.388605 | 1.050911 | 0.083404 | 1.688e+03 | 2.539e+04 | 6.000000 | 0.056294 | -0.065236 |
| sym_0.75 | 0.750000 | -0.750000 | 2.526394 | 1.427744 | -0.470838 | 1.048097 | 0.093434 | 1.570e+03 | 1.792e+04 | 8.000000 | 0.199333 | -0.117860 |
| sym_1 | 1.000000 | -1.000000 | 1.410755 | 0.998204 | -0.397368 | 1.041913 | 0.108024 | 1.336e+03 | 1.220e+04 | 8.000000 | 0.103874 | -0.053587 |
| sym_1.25 | 1.250000 | -1.250000 | 0.834331 | 0.697978 | -0.378012 | 1.037710 | 0.118734 | 1.078e+03 | 8.222e+03 | 5.000000 | 0.001401 | -0.090489 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.111426 |
| mean_fold_return | 0.178893 |
| fold_return_std | 0.201692 |
| worst_fold_return | -0.072100 |
| best_fold_return | 0.504320 |
| worst_3_fold_average_return | -0.008952 |
| profitable_fold_count | 9.000000 |
| profitable_fold_rate | 0.900000 |
| median_fold_sharpe | 2.161388 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.4, 'best_rank': 1, 'mean_importance': 1106.2, 'mean_importance_normalized': 0.10227212687975448, 'folds': [{'fold': 0, 'rank': 1, 'importance': 1121.0, 'importance_normalized': 0.10802736821817481}, {'fold': 1, 'rank': 1, 'importance': 1114.0, 'importance_normalized': 0.10365683446543221}, {'fold': 2, 'rank': 1, 'importance': 1167.0, 'importance_normalized': 0.10705439867902028}, {'fold': 3, 'rank': 1, 'importance': 1157.0, 'importance_normalized': 0.10593297930781909}, {'fold': 4, 'rank': 1, 'importance': 1106.0, 'importance_normalized': 0.10234107522901822}, {'fold': 5, 'rank': 1, 'importance': 1109.0, 'importance_normalized': 0.10233459444495709}, {'fold': 6, 'rank': 2, 'importance': 1078.0, 'importance_normalized': 0.09934568242558289}, {'fold': 7, 'rank': 2, 'importance': 1035.0, 'importance_normalized': 0.09494541785157325}, {'fold': 8, 'rank': 2, 'importance': 1075.0, 'importance_normalized': 0.09847929644558447}, {'fold': 9, 'rank': 2, 'importance': 1100.0, 'importance_normalized': 0.1006036217303823}], 'stability_rank': 1}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.6, 'best_rank': 1, 'mean_importance': 1081.2, 'mean_importance_normalized': 0.09992654074424791, 'folds': [{'fold': 0, 'rank': 2, 'importance': 1025.0, 'importance_normalized': 0.09877613953936591}, {'fold': 1, 'rank': 2, 'importance': 1044.0, 'importance_normalized': 0.09714338885270309}, {'fold': 2, 'rank': 2, 'importance': 1058.0, 'importance_normalized': 0.09705531602605266}, {'fold': 3, 'rank': 2, 'importance': 999.0, 'importance_normalized': 0.0914667643288775}, {'fold': 4, 'rank': 2, 'importance': 1087.0, 'importance_normalized': 0.10058295549181086}, {'fold': 5, 'rank': 2, 'importance': 1103.0, 'importance_normalized': 0.10178093568330719}, {'fold': 6, 'rank': 1, 'importance': 1112.0, 'importance_normalized': 0.1024790341903972}, {'fold': 7, 'rank': 1, 'importance': 1140.0, 'importance_normalized': 0.10457756169158793}, {'fold': 8, 'rank': 1, 'importance': 1140.0, 'importance_normalized': 0.1044338585562477}, {'fold': 9, 'rank': 1, 'importance': 1104.0, 'importance_normalized': 0.10096945308212914}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 3.0, 'best_rank': 3, 'mean_importance': 932.4, 'mean_importance_normalized': 0.08614672010907157, 'folds': [{'fold': 0, 'rank': 3, 'importance': 844.0, 'importance_normalized': 0.08133371880119496}, {'fold': 1, 'rank': 3, 'importance': 904.0, 'importance_normalized': 0.08411649762724481}, {'fold': 2, 'rank': 3, 'importance': 905.0, 'importance_normalized': 0.0830199064306027}, {'fold': 3, 'rank': 3, 'importance': 959.0, 'importance_normalized': 0.08780443142281634}, {'fold': 4, 'rank': 3, 'importance': 928.0, 'importance_normalized': 0.08587026926991764}, {'fold': 5, 'rank': 3, 'importance': 902.0, 'importance_normalized': 0.08323336716803544}, {'fold': 6, 'rank': 3, 'importance': 906.0, 'importance_normalized': 0.08349460879181642}, {'fold': 7, 'rank': 3, 'importance': 971.0, 'importance_normalized': 0.0890743968443262}, {'fold': 8, 'rank': 3, 'importance': 975.0, 'importance_normalized': 0.0893184316599487}, {'fold': 9, 'rank': 3, 'importance': 1030.0, 'importance_normalized': 0.09420157307481251}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.2, 'best_rank': 4, 'mean_importance': 784.2, 'mean_importance_normalized': 0.07244476840971834, 'folds': [{'fold': 0, 'rank': 5, 'importance': 691.0, 'importance_normalized': 0.06658957309434325}, {'fold': 1, 'rank': 5, 'importance': 695.0, 'importance_normalized': 0.0646692100120964}, {'fold': 2, 'rank': 4, 'importance': 776.0, 'importance_normalized': 0.07118612971287037}, {'fold': 3, 'rank': 4, 'importance': 791.0, 'importance_normalized': 0.07242263321735946}, {'fold': 4, 'rank': 4, 'importance': 812.0, 'importance_normalized': 0.07513648561117794}, {'fold': 5, 'rank': 4, 'importance': 810.0, 'importance_normalized': 0.07474393282273692}, {'fold': 6, 'rank': 4, 'importance': 802.0, 'importance_normalized': 0.07391023868767856}, {'fold': 7, 'rank': 4, 'importance': 800.0, 'importance_normalized': 0.07338776259058802}, {'fold': 8, 'rank': 4, 'importance': 825.0, 'importance_normalized': 0.07557713448149506}, {'fold': 9, 'rank': 4, 'importance': 840.0, 'importance_normalized': 0.07682458386683738}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.8, 'best_rank': 4, 'mean_importance': 755.4, 'mean_importance_normalized': 0.06983967901819257, 'folds': [{'fold': 0, 'rank': 4, 'importance': 764.0, 'importance_normalized': 0.0736243615688542}, {'fold': 1, 'rank': 4, 'importance': 763.0, 'importance_normalized': 0.07099655717874756}, {'fold': 2, 'rank': 5, 'importance': 713.0, 'importance_normalized': 0.06540684340886158}, {'fold': 3, 'rank': 5, 'importance': 721.0, 'importance_normalized': 0.06601355063175243}, {'fold': 4, 'rank': 5, 'importance': 750.0, 'importance_normalized': 0.06939946331081706}, {'fold': 5, 'rank': 5, 'importance': 758.0, 'importance_normalized': 0.06994555688843776}, {'fold': 6, 'rank': 5, 'importance': 769.0, 'importance_normalized': 0.07086904432771172}, {'fold': 7, 'rank': 5, 'importance': 765.0, 'importance_normalized': 0.07017704797724979}, {'fold': 8, 'rank': 5, 'importance': 751.0, 'importance_normalized': 0.06879809454012459}, {'fold': 9, 'rank': 5, 'importance': 800.0, 'importance_normalized': 0.07316627034936894}], 'stability_rank': 5}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.2, 'best_rank': 6, 'mean_importance': 591.1, 'mean_importance_normalized': 0.05463693547835411, 'folds': [{'fold': 0, 'rank': 6, 'importance': 573.0, 'importance_normalized': 0.055218271176640646}, {'fold': 1, 'rank': 6, 'importance': 596.0, 'importance_normalized': 0.055457336931236625}, {'fold': 2, 'rank': 6, 'importance': 607.0, 'importance_normalized': 0.05568296486560866}, {'fold': 3, 'rank': 7, 'importance': 574.0, 'importance_normalized': 0.05255447720197766}, {'fold': 4, 'rank': 6, 'importance': 591.0, 'importance_normalized': 0.054686777088923846}, {'fold': 5, 'rank': 6, 'importance': 569.0, 'importance_normalized': 0.05250530589646581}, {'fold': 6, 'rank': 6, 'importance': 590.0, 'importance_normalized': 0.0543728688600129}, {'fold': 7, 'rank': 6, 'importance': 609.0, 'importance_normalized': 0.05586643427208513}, {'fold': 8, 'rank': 6, 'importance': 614.0, 'importance_normalized': 0.05624770978380359}, {'fold': 9, 'rank': 7, 'importance': 588.0, 'importance_normalized': 0.05377720870678617}], 'stability_rank': 6}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.9, 'best_rank': 6, 'mean_importance': 570.3, 'mean_importance_normalized': 0.05271123621473219, 'folds': [{'fold': 0, 'rank': 7, 'importance': 554.0, 'importance_normalized': 0.05338729883395972}, {'fold': 1, 'rank': 7, 'importance': 551.0, 'importance_normalized': 0.05127012189448218}, {'fold': 2, 'rank': 7, 'importance': 600.0, 'importance_normalized': 0.055040821942941014}, {'fold': 3, 'rank': 6, 'importance': 596.0, 'importance_normalized': 0.0545687603003113}, {'fold': 4, 'rank': 7, 'importance': 590.0, 'importance_normalized': 0.05459424447117609}, {'fold': 5, 'rank': 7, 'importance': 562.0, 'importance_normalized': 0.051859370674540925}, {'fold': 6, 'rank': 8, 'importance': 533.0, 'importance_normalized': 0.04911989678370657}, {'fold': 7, 'rank': 7, 'importance': 548.0, 'importance_normalized': 0.050270617374552795}, {'fold': 8, 'rank': 7, 'importance': 577.0, 'importance_normalized': 0.05285818981311836}, {'fold': 9, 'rank': 6, 'importance': 592.0, 'importance_normalized': 0.054143040058533015}], 'stability_rank': 7}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.9, 'best_rank': 7, 'mean_importance': 544.4, 'mean_importance_normalized': 0.05029805468389289, 'folds': [{'fold': 0, 'rank': 8, 'importance': 488.0, 'importance_normalized': 0.047027079117278596}, {'fold': 1, 'rank': 8, 'importance': 537.0, 'importance_normalized': 0.049967432771936354}, {'fold': 2, 'rank': 8, 'importance': 577.0, 'importance_normalized': 0.05293092376846161}, {'fold': 3, 'rank': 8, 'importance': 566.0, 'importance_normalized': 0.05182201062076543}, {'fold': 4, 'rank': 8, 'importance': 557.0, 'importance_normalized': 0.05154066808550014}, {'fold': 5, 'rank': 8, 'importance': 463.0, 'importance_normalized': 0.04272400110731752}, {'fold': 6, 'rank': 7, 'importance': 577.0, 'importance_normalized': 0.05317482259699567}, {'fold': 7, 'rank': 8, 'importance': 547.0, 'importance_normalized': 0.05017888267131456}, {'fold': 8, 'rank': 8, 'importance': 560.0, 'importance_normalized': 0.05130084279956028}, {'fold': 9, 'rank': 8, 'importance': 572.0, 'importance_normalized': 0.052313883299798795}], 'stability_rank': 8}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 9.0, 'best_rank': 9, 'mean_importance': 472.0, 'mean_importance_normalized': 0.04362344925254176, 'folds': [{'fold': 0, 'rank': 9, 'importance': 444.0, 'importance_normalized': 0.04278693263949118}, {'fold': 1, 'rank': 9, 'importance': 495.0, 'importance_normalized': 0.04605936540429888}, {'fold': 2, 'rank': 9, 'importance': 460.0, 'importance_normalized': 0.04219796348958811}, {'fold': 3, 'rank': 9, 'importance': 490.0, 'importance_normalized': 0.04486357809924922}, {'fold': 4, 'rank': 9, 'importance': 472.0, 'importance_normalized': 0.04367539557694087}, {'fold': 5, 'rank': 9, 'importance': 455.0, 'importance_normalized': 0.04198578942511765}, {'fold': 6, 'rank': 9, 'importance': 467.0, 'importance_normalized': 0.04303750806377293}, {'fold': 7, 'rank': 9, 'importance': 479.0, 'importance_normalized': 0.043940922851114575}, {'fold': 8, 'rank': 9, 'importance': 467.0, 'importance_normalized': 0.04278123854891902}, {'fold': 9, 'rank': 9, 'importance': 491.0, 'importance_normalized': 0.044905798426925186}], 'stability_rank': 9}, {'feature': 'vol_rolling_24', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 10.4, 'best_rank': 10, 'mean_importance': 409.8, 'mean_importance_normalized': 0.037898659895005814, 'folds': [{'fold': 0, 'rank': 10, 'importance': 434.0, 'importance_normalized': 0.04182326298544859}, {'fold': 1, 'rank': 11, 'importance': 404.0, 'importance_normalized': 0.037591886107751}, {'fold': 2, 'rank': 11, 'importance': 409.0, 'importance_normalized': 0.03751949362443813}, {'fold': 3, 'rank': 11, 'importance': 380.0, 'importance_normalized': 0.03479216260758103}, {'fold': 4, 'rank': 10, 'importance': 414.0, 'importance_normalized': 0.03830850374757102}, {'fold': 5, 'rank': 10, 'importance': 424.0, 'importance_normalized': 0.03912521915659315}, {'fold': 6, 'rank': 10, 'importance': 432.0, 'importance_normalized': 0.03981199889411114}, {'fold': 7, 'rank': 10, 'importance': 405.0, 'importance_normalized': 0.03715255481148518}, {'fold': 8, 'rank': 10, 'importance': 405.0, 'importance_normalized': 0.037101502381824844}, {'fold': 9, 'rank': 11, 'importance': 391.0, 'importance_normalized': 0.03576001463325407}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.387894 | 0.907669 | -0.255931 | 1.043645 | 0.113933 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.334884 | 1.325814 | -0.143728 | 1.114567 | 0.049949 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 3.081681 | 5.677421 | -0.138767 | 1.157501 | 0.033475 |
| ema_trend_48_192 | negative | 2.183e+04 | 2.146651 | 4.645612 | -0.124508 | 1.200315 | 0.025733 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.930240 | 2.447158 | -0.124835 | 1.114518 | 0.046510 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 1.610052 | 2.631229 | -0.370239 | 1.091717 | 0.039345 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 317 |
| average_r | 0.593614 |
| median_r | 0.486118 |
| avg_max_favorable_r | 3.392307 |
| avg_max_adverse_r | -2.682182 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.977444 |
| avg_giveback_r | 2.798693 |
| avg_capture_ratio | -4.604140 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.977444 |
| avg_mfe_r_of_losers | 1.400348 |
| median_mfe_r_of_losers | 1.040026 |
| avg_mfe_r_before_loss | 1.400348 |
| median_mfe_r_before_loss | 1.040026 |
| loser_reached_0_5r_rate | 0.759398 |
| loser_reached_1r_rate | 0.511278 |
| loser_reached_1_5r_rate | 0.323308 |
| loser_reached_2r_rate | 0.225564 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -4.604140 |
| median_capture_ratio | 0.225540 |
| avg_giveback_r | 2.798693 |
| median_giveback_r | 2.103511 |
| avg_giveback_r_winners | 1.898961 |
| avg_giveback_r_losers | 4.043435 |
| median_giveback_r_winners | 1.504666 |
| median_giveback_r_losers | 3.451592 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.994565 |
| winner_had_mae_below_minus_0_25r_rate | 0.869565 |
| winner_had_mae_below_minus_0_5r_rate | 0.739130 |
| winner_had_mae_below_minus_1r_rate | 0.489130 |
| avg_mae_r_of_winners | -1.228385 |
| median_mae_r_of_winners | -0.996090 |
| p90_abs_mae_r_of_winners | 2.524460 |
| avg_mae_r | -2.682182 |
| median_mae_r | -1.777115 |
| q10_mae_r | -6.547224 |
| q25_mae_r | -3.310461 |
| q75_mae_r | -0.846177 |
| q90_mae_r | -0.286814 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.580442 |
| prob_final_loss | 0.419558 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 0.979167 |
| prob_mfe_ge_0_5r | 0.895899 |
| prob_final_loss_given_mfe_ge_0_5r | 0.355634 |
| prob_mfe_ge_1r | 0.779180 |
| prob_final_loss_given_mfe_ge_1r | 0.275304 |
| prob_mfe_ge_1_5r | 0.675079 |
| prob_final_loss_given_mfe_ge_1_5r | 0.200935 |
| prob_mfe_ge_2r | 0.583596 |
| prob_final_loss_given_mfe_ge_2r | 0.162162 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 12.059937 |
| median_time_to_mfe | 12.000000 |
| avg_time_to_mae | 9.413249 |
| median_time_to_mae | 8.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.078864 |
| prob_mfe_ge_0_5r_within_2_bars | 0.123028 |
| prob_mfe_ge_1r_within_4_bars | 0.110410 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.593614 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.580442 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 317 |
| counterfactual.baseline.avg_r | 0.593614 |
| counterfactual.baseline.median_r | 0.486118 |
| counterfactual.baseline.win_rate | 0.580442 |
| counterfactual.baseline.profit_factor | 1.535304 |
| counterfactual.breakeven_after_0_5r.trade_count | 317 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.055697 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.012618 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.405423 |
| counterfactual.breakeven_after_1_0r.trade_count | 317 |
| counterfactual.breakeven_after_1_0r.avg_r | -0.015207 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.135647 |
| counterfactual.breakeven_after_1_0r.profit_factor | 0.966686 |
| counterfactual.exit_at_first_0_5r.trade_count | 317 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.393706 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.974763 |
| counterfactual.exit_at_first_0_5r.profit_factor | 5.202854 |
| counterfactual.exit_at_first_1_0r.trade_count | 317 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.404938 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.870662 |
| counterfactual.exit_at_first_1_0r.profit_factor | 1.887107 |
| counterfactual.partial_50pct_at_1r.trade_count | 317 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.499276 |
| counterfactual.partial_50pct_at_1r.median_r | 0.731108 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.694006 |
| counterfactual.partial_50pct_at_1r.profit_factor | 1.747821 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 317 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.538245 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.349209 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.561514 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.475979 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 317 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.595348 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.795330 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.870662 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 2.304242 |
| counterfactual.best_policy_by_avg_r | trail_0_5r_after_1_0r |
| counterfactual.best_policy_by_profit_factor | exit_at_first_0_5r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 305 | 0.564407 | 0.398429 | 0.573770 | 3.391578 | -2.709429 | 2.827170 | 24.091803 | 1.504271 | 0.990164 | 0.895082 | 0.777049 |
| reversal | 12 | 1.335956 | 1.514194 | 0.750000 | 3.410851 | -1.989666 | 2.074895 | 24.250000 | 2.578196 | 1.000000 | 0.916667 | 0.833333 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 0 |
| gross_pnl | 1.722747 |
| net_pnl | 1.659347 |
| total_cost | 0.063400 |
| cost_to_gross_pnl | 0.036802 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1918 |
| actual_trade_count | 0 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 3.703163 |
| sharpe | 2.867496 |
| sortino | 4.556409 |
| calmar | 5.178192 |
| max_drawdown | -0.165621 |
| profit_factor | 1.140904 |
| hit_rate | 0.490898 |
| gross_pnl | 1.722747 |
| net_pnl | 1.659347 |
| total_cost | 0.063400 |
| cost_to_gross_pnl | 0.036802 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 3.703163 |
| cost_x1.annualized_return | 0.443006 |
| cost_x1.annualized_vol | 0.230164 |
| cost_x1.sharpe | 1.924744 |
| cost_x1.max_drawdown | -0.165621 |
| cost_x1.profit_factor | 1.140904 |
| cost_x1.hit_rate | 0.490898 |
| cost_x2.cumulative_return | 3.414270 |
| cost_x2.annualized_return | 0.421500 |
| cost_x2.annualized_vol | 0.230157 |
| cost_x2.sharpe | 1.831360 |
| cost_x2.max_drawdown | -0.166124 |
| cost_x2.profit_factor | 1.134991 |
| cost_x2.hit_rate | 0.490265 |
| cost_x3.cumulative_return | 3.143096 |
| cost_x3.annualized_return | 0.400313 |
| cost_x3.annualized_vol | 0.230157 |
| cost_x3.sharpe | 1.739304 |
| cost_x3.max_drawdown | -0.166626 |
| cost_x3.profit_factor | 1.129119 |
| cost_x3.hit_rate | 0.489381 |
| cost_x5.cumulative_return | 2.649626 |
| cost_x5.annualized_return | 0.358874 |
| cost_x5.annualized_vol | 0.230177 |
| cost_x5.sharpe | 1.559123 |
| cost_x5.max_drawdown | -0.184932 |
| cost_x5.profit_factor | 1.117495 |
| cost_x5.hit_rate | 0.488496 |

### Entry Delay
| Metric | Value |
| --- | --- |
| delay_1_bars.cumulative_return | 3.132024 |
| delay_1_bars.annualized_return | 0.256128 |
| delay_1_bars.annualized_vol | 0.188018 |
| delay_1_bars.sharpe | 1.362250 |
| delay_1_bars.max_drawdown | -0.183951 |
| delay_1_bars.profit_factor | 1.130465 |
| delay_1_bars.hit_rate | 0.490516 |
| delay_2_bars.cumulative_return | 3.550034 |
| delay_2_bars.annualized_return | 0.275735 |
| delay_2_bars.annualized_vol | 0.187698 |
| delay_2_bars.sharpe | 1.469032 |
| delay_2_bars.max_drawdown | -0.197559 |
| delay_2_bars.profit_factor | 1.139729 |
| delay_2_bars.hit_rate | 0.490645 |

### Walk Forward
| Metric | Value |
| --- | --- |
| fold_count | 5 |
| positive_fold_count | 3 |
| positive_fold_ratio | 0.600000 |
| min_fold_cumulative_return | 0.0 |
| median_fold_cumulative_return | 0.142713 |
| mean_fold_cumulative_return | 0.450616 |
| mean_fold_sharpe | 1.750693 |
| std_fold_sharpe | 1.938793 |
| worst_fold_max_drawdown | -0.165621 |

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
| oos_prediction.mean | -0.019832 |
| oos_prediction.std | 0.973977 |
| oos_prediction.min | -4.544777 |
| oos_prediction.max | 4.281687 |
| oos_prediction.median | -0.005814 |
| oos_prediction.q01 | -2.523928 |
| oos_prediction.q05 | -1.683109 |
| oos_prediction.q25 | -0.616327 |
| oos_prediction.q75 | 0.603911 |
| oos_prediction.q95 | 1.564759 |
| oos_prediction.q99 | 2.263441 |
| oos_prediction.skew | -0.148989 |
| oos_prediction.kurtosis | 0.470121 |
| oos_prediction.positive_rate | 0.497100 |
| oos_prediction.negative_rate | 0.502900 |
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
| 1 | atr_48 | 1.106e+03 | 0.102272 | 10 | feature_importances_ |
| 2 | vol_rolling_192 | 1.081e+03 | 0.099927 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 932.400000 | 0.086147 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 784.200000 | 0.072445 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 755.400000 | 0.069840 | 10 | feature_importances_ |
| 6 | bollinger_bandwidth_rank_192 | 591.100000 | 0.054637 | 10 | feature_importances_ |
| 7 | atr_over_price_48 | 570.300000 | 0.052711 | 10 | feature_importances_ |
| 8 | vol_rolling_48 | 544.400000 | 0.050298 | 10 | feature_importances_ |
| 9 | atr_pct_rank_192 | 472.000000 | 0.043623 | 10 | feature_importances_ |
| 10 | vol_rolling_24 | 409.800000 | 0.037899 | 10 | feature_importances_ |
| 11 | mama_minus_fama_over_atr | 405.000000 | 0.037434 | 10 | feature_importances_ |
| 12 | close_over_bb_upper_192 | 301.100000 | 0.027847 | 10 | feature_importances_ |
| 13 | close_over_bb_mid_192 | 291.800000 | 0.026957 | 10 | feature_importances_ |
| 14 | ret_48 | 289.500000 | 0.026756 | 10 | feature_importances_ |
| 15 | bollinger_percent_b | 256.000000 | 0.023647 | 10 | feature_importances_ |
| 16 | distance_from_ema96_atr | 193.200000 | 0.017867 | 10 | feature_importances_ |
| 17 | ret_24 | 187.500000 | 0.017327 | 10 | feature_importances_ |
| 18 | roofing_filter_over_atr | 171.200000 | 0.015819 | 10 | feature_importances_ |
| 19 | atr_pct | 155.500000 | 0.014368 | 10 | feature_importances_ |
| 20 | ret_16 | 138.100000 | 0.012761 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 1.722747 |
| net_pnl | 1.659347 |
| total_cost | 0.063400 |
| cost_drag | 0.063400 |
| cost_to_gross_pnl | 0.036802 |
| avg_turnover | 0.014475 |
| total_turnover | 634.000000 |
| mean_abs_signal | 0.043790 |
| signal_turnover | 0.051187 |
| flat_rate | 0.956210 |
| long_rate | 0.025479 |
| short_rate | 0.018311 |
| trade_rate | 0.174406 |
| executed_trade_count | 7639 |
| avg_signal_executed | 0.035476 |
| avg_pred_prob_executed | 0.517784 |
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
| 0 |  | 0.167606 | 0.160406 | 0.007200 | 2.555751 | 0.016438 |  |  |  |  |
| 1 |  | 0.395998 | 0.388398 | 0.007600 | 5.725461 | 0.017352 |  |  |  |  |
| 2 |  | 0.430914 | 0.424614 | 0.006300 | 11.353451 | 0.014384 |  |  |  |  |
| 3 |  | 0.082817 | 0.075017 | 0.007800 | 1.233636 | 0.017808 |  |  |  |  |
| 4 |  | 0.053720 | 0.047720 | 0.006000 | 0.844590 | 0.013699 |  |  |  |  |
| 5 |  | -0.066300 | -0.071900 | 0.005600 | -1.691201 | 0.012785 |  |  |  |  |
| 6 |  | 0.012582 | 0.005782 | 0.006800 | 0.060496 | 0.015525 |  |  |  |  |
| 7 |  | 0.123836 | 0.118236 | 0.005600 | 2.372615 | 0.012785 |  |  |  |  |
| 8 |  | 0.113151 | 0.107951 | 0.005200 | 1.950162 | 0.011872 |  |  |  |  |
| 9 |  | 0.379632 | 0.374232 | 0.005400 | 10.733658 | 0.012329 |  |  |  |  |


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
| unclassified | 34 | 3 | 0.088235 | 0.106471 | 1.195042 |
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
| 47 | close_ret_robust_z_192 |

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
    robust_zscore:
      params:
        source_col: close_ret
        window: 192
        output_col: close_ret_robust_z_192
        shift_stats: true
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
  - close_ret_robust_z_192
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
