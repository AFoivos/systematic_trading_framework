# Experiment Report: model06_vwap32_rz128

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/BEST/ethusd/trial0041_validation_suite_v2/06_feature_window_surface/model06/model06_vwap32_rz128.yaml`
- Model kind: `lightgbm_regressor`
- Symbols: `ETHUSD`
- Data source: `dukascopy_csv` at interval `30m`
- Data window: `None` to `2026-06-09 23:30:00`
- Rows / columns: `109005` rows, `129` columns
- Target: `future_return_regression` horizon `24`
- Feature count: `48`
- Runtime seed: `7`

## Pipeline Trace

### 1. Entry Point
- `runner.run_experiment` -> `src.experiments.runner.run_experiment(config_path: 'str | Path') -> 'ExperimentResult | Any'`
- `runner._load_asset_frames` -> `src.experiments.runner._load_asset_frames(data_cfg: 'dict[str, object]')`
- `pipeline.run_experiment_pipeline` -> `src.experiments.orchestration.pipeline.run_experiment_pipeline(config_path: 'str | Path', *, load_asset_frames_fn: 'LoadAssetFramesFn', save_processed_snapshot_fn: 'SaveProcessedFn') -> 'ExperimentResult'`

```yaml
config_path: /workspace/config/experiments/foundation_alpha/BEST/ethusd/trial0041_validation_suite_v2/06_feature_window_surface/model06/model06_vwap32_rz128.yaml
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
    save_processed: true
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
- `feature[vwap]` -> `src.features.technical.vwap.add_vwap_features(df: 'pd.DataFrame', high_col: 'str' = 'high', low_col: 'str' = 'low', close_col: 'str' = 'close', volume_col: 'str' = 'volume', window: 'int' = 20, windows: 'Sequence[int] | None' = None, add_distance: 'bool' = False, vwap_col: 'str | None' = None, distance_col: 'str | None' = None, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'high_col': 'high', 'low_col': 'low', 'close_col': 'close', 'volume_col': 'volume', 'windows': [32]}

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
        window: 128
        output_col: close_ret_robust_z_128
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
- step: vwap
  params:
    high_col: high
    low_col: low
    close_col: close
    volume_col: volume
    windows:
    - 32
  outputs: {}
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: close
        denominator_col: vwap_32
        output_col: close_over_vwap_32
        subtract: 1.0
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
- close_over_vwap_32
- close_ret_robust_z_128
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
  - close_over_vwap_32
  - close_ret_robust_z_128
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
  final_refit: true
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
- `backtesting.engine.run_backtest` -> `src.backtesting.engine.run_backtest(df: 'pd.DataFrame', signal_col: 'str', returns_col: 'str', returns_type: "Literal['simple', 'log']" = 'simple', missing_return_policy: 'str' = 'raise_if_exposed', cost_per_unit_turnover: 'float' = 0.0, slippage_per_unit_turnover: 'float' = 0.0, target_vol: 'Optional[float]' = None, vol_col: 'Optional[str]' = None, max_leverage: 'float' = 3.0, dd_guard: 'bool' = True, max_drawdown: 'float' = 0.2, cooloff_bars: 'int' = 20, rearm_drawdown: 'Optional[float]' = None, periods_per_year: 'int' = 252, min_holding_bars: 'int' = 0, liquidate_at_end: 'bool' = False, allow_short: 'bool' = False, holding_cost_per_exposed_bar: 'float' = 0.0) -> 'BacktestResult'`
- `backtesting.engine.BacktestResult` -> `src.backtesting.engine.BacktestResult(equity_curve: 'pd.Series', returns: 'pd.Series', gross_returns: 'pd.Series', costs: 'pd.Series', positions: 'pd.Series', turnover: 'pd.Series', summary: 'dict', trades: 'pd.DataFrame | None' = None, mark_to_market_returns: 'pd.Series | None' = None, mark_to_market_equity_curve: 'pd.Series | None' = None, mark_to_market_summary: 'dict | None' = None, realized_returns: 'pd.Series | None' = None, realized_gross_returns: 'pd.Series | None' = None, realized_equity_curve: 'pd.Series | None' = None, realized_summary: 'dict | None' = None) -> None`

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
  annualization_mode: null
  max_cost_r: null
  risk_per_trade: null
  max_holding_bars: null
  asset_params: {}
  dynamic_exit: {}
  strategy_path: {}
  dynamic_exits: {}
  partial_exits: {}
  allow_short: true
  oos_mode: strict
  execution_price: close_lagged
  execution_delay_bars: 0
  estimated_spread_cost_per_unit_turnover: 0.0
  commission_per_unit_turnover: 0.0
  slippage_per_unit_turnover: 0.0
  holding_cost_per_exposed_bar: 0.0
  allow_cost_layering: false
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
- `artifacts.save_artifacts` -> `src.experiments.orchestration.artifacts.save_artifacts(*, run_dir: 'Path', cfg: 'dict[str, Any]', data: 'pd.DataFrame | dict[str, pd.DataFrame]', model: 'object | None' = None, performance: 'BacktestResult | PortfolioPerformance', model_meta: 'dict[str, Any]', evaluation: 'dict[str, Any]', monitoring: 'dict[str, Any]', execution: 'dict[str, Any]', execution_orders: 'pd.DataFrame | None', portfolio_weights: 'pd.DataFrame | None', portfolio_diagnostics: 'pd.DataFrame | None', portfolio_meta: 'dict[str, Any]', storage_meta: 'dict[str, Any]', run_metadata: 'dict[str, Any]', config_hash_sha256: 'str', data_fingerprint: 'dict[str, Any]', stage_tails: 'dict[str, Any] | None' = None, lifecycle_context: 'dict[str, Any] | None' = None) -> 'dict[str, str]'`
- `artifacts.write_experiment_report_from_run_dir` -> `src.experiments.orchestration.artifacts.write_experiment_report_from_run_dir(run_dir: 'Path') -> 'dict[str, str]'`
- `reporting.build_experiment_report_markdown` -> `src.experiments.orchestration.reporting.build_experiment_report_markdown(*, cfg: 'dict[str, Any]', summary_payload: 'dict[str, Any]', run_metadata: 'dict[str, Any]', chart_paths: 'dict[str, str]', artifact_paths: 'dict[str, str]') -> 'str'`

## Primary Summary
| Metric | Value |
| --- | --- |
| cumulative_return | 5.244945 |
| annualized_return | 1.080709 |
| annualized_vol | 0.285470 |
| sharpe | 3.785716 |
| sortino | 4.388107 |
| calmar | 8.284249 |
| max_drawdown | -0.130454 |
| profit_factor | 1.176927 |
| hit_rate | 0.493578 |
| annualization_mode | fixed_periods |
| metric_scope | bar_returns |
| avg_turnover | 0.013927 |
| total_turnover | 610.000000 |
| gross_pnl | 5.637771 |
| net_pnl | 5.244945 |
| total_cost | 0.061000 |
| cost_drag | 0.392826 |
| cost_to_gross_pnl | 0.069678 |
| gross_return_sum | 1.993977 |
| net_return_sum | 1.932977 |
| cost_return_sum | 0.061000 |
| conventional_sharpe | 2.708481 |
| return_over_vol_sharpe | 3.785716 |
| sharpe_legacy_alias | return_over_vol_sharpe |
| bar_return_profit_factor | 1.176927 |
| profit_factor_scope | bar_returns |
| evaluation_scope | strict_oos_only |
| evaluation_start | 2022-03-14T15:00:00 |
| evaluation_end | 2024-09-17T10:30:00 |
| evaluation_rows | 43800 |
| trade_count | 305 |
| average_r | 0.811095 |
| median_r | 0.595414 |
| mtm_cumulative_return | 5.244945 |
| mtm_annualized_return | 1.080709 |
| mtm_annualized_vol | 0.285470 |
| mtm_sharpe | 3.785716 |
| mtm_conventional_sharpe | 2.708481 |
| mtm_return_over_vol_sharpe | 3.785716 |
| mtm_max_drawdown | -0.130454 |
| mtm_profit_factor | 1.176927 |
| mtm_bar_return_profit_factor | 1.176927 |
| flat_rate | 0.957534 |
| long_rate | 0.024110 |
| short_rate | 0.018356 |
| avg_max_favorable_r | 3.480115 |
| avg_max_adverse_r | -2.567866 |
| loser_was_positive_rate | 0.983607 |
| avg_giveback_r | 2.669020 |
| avg_capture_ratio | -3.576135 |
| robustness_walk_forward_total_calendar_periods | 7.000000 |
| robustness_walk_forward_active_oos_periods | 3.000000 |
| robustness_walk_forward_positive_active_periods | 3.000000 |
| robustness_walk_forward_positive_active_period_ratio | 1.000000 |
| robustness_walk_forward_min_active_period_cumulative_return | 0.566636 |
| robustness_walk_forward_worst_active_period_max_drawdown | -0.130454 |
| robustness_walk_forward_mean_active_period_sharpe | 4.022753 |
| robustness_walk_forward_std_active_period_sharpe | 1.058148 |
| robustness_cost_x1_cumulative_return | 5.244945 |
| robustness_cost_x1_sharpe | 3.785716 |
| robustness_cost_x1_max_drawdown | -0.130454 |
| robustness_cost_x1_profit_factor | 1.176927 |
| robustness_cost_x2_cumulative_return | 4.875330 |
| robustness_cost_x2_sharpe | 3.609782 |
| robustness_cost_x2_max_drawdown | -0.131150 |
| robustness_cost_x2_profit_factor | 1.170619 |
| robustness_cost_x3_cumulative_return | 4.527558 |
| robustness_cost_x3_sharpe | 3.437985 |
| robustness_cost_x3_max_drawdown | -0.131845 |
| robustness_cost_x3_profit_factor | 1.164360 |
| robustness_cost_x5_cumulative_return | 3.892460 |
| robustness_cost_x5_sharpe | 3.106459 |
| robustness_cost_x5_max_drawdown | -0.137895 |
| robustness_cost_x5_profit_factor | 1.151980 |
| robustness_delay_1_bars_cumulative_return | 4.152920 |
| robustness_delay_1_bars_sharpe | 3.274911 |
| robustness_delay_1_bars_max_drawdown | -0.133571 |
| robustness_delay_1_bars_profit_factor | 1.158987 |
| robustness_delay_2_bars_cumulative_return | 4.123202 |
| robustness_delay_2_bars_sharpe | 3.278728 |
| robustness_delay_2_bars_max_drawdown | -0.147939 |
| robustness_delay_2_bars_profit_factor | 1.159443 |
| completed_trade_count | 305 |
| win_rate | 0.596721 |
| trade_return_profit_factor | 2.190325 |
| trade_r_profit_factor | 1.786966 |
| trade_profit_factor | 2.190325 |
| entry_trade_cost | 0.030500 |
| exit_trade_cost | 0.030895 |
| holding_trade_cost | 0.0 |
| total_trade_cost | 0.061395 |
| position_transition_count | 608 |
| turnover_event_count | 608 |
| exposed_bar_count | 7354 |
| bar_return_profit_factor_scope | bar_returns |
| trade_return_profit_factor_scope | completed_trade_net_returns |
| trade_r_profit_factor_scope | completed_trade_net_r_multiples |
| trade_profit_factor_scope | completed_trade_net_returns |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.042466 |
| signal_turnover | 0.049269 |
| long_rate | 0.024110 |
| short_rate | 0.018356 |
| flat_rate | 0.957534 |
| executed_trade_count | 7354 |
| trade_rate | 0.167900 |
| avg_signal_executed | 0.034539 |
| avg_pred_prob_executed | 0.505220 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.523311 |
| classification.brier | 0.254368 |
| classification.roc_auc | 0.527174 |
| classification.log_loss | 0.702641 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.172941 |
| regression.rmse | 2.637654 |
| regression.mse | 6.957217 |
| regression.r2 | -0.114229 |
| regression.correlation | 0.049119 |
| regression.directional_accuracy | 0.523174 |
| regression.mean_prediction | -0.037288 |
| regression.mean_target | 0.003813 |
| volatility.status | ok |
| volatility.metric_scope | configured_volatility_rank_feature |
| volatility.configured_volatility_col | atr_pct_rank_100 |
| volatility.resolved_volatility_col | atr_pct_rank_192 |
| volatility.evaluation_value_rows | 43800 |
| volatility.missing_value_rows | 0 |
| volatility.mean | 0.467559 |
| volatility.std | 0.343002 |
| volatility.min | 0.005208 |
| volatility.max | 1.000000 |
| volatility.evaluation_scope | strict_oos_only |
| volatility.evaluation_start | 2022-03-14T15:00:00 |
| volatility.evaluation_end | 2024-09-17T10:30:00 |
| volatility.evaluation_rows | 43800 |


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
| prediction_distribution.mean | -0.037288 |
| prediction_distribution.std | 0.975167 |
| prediction_distribution.min | -4.455228 |
| prediction_distribution.max | 4.450357 |
| prediction_distribution.median | -0.019791 |
| prediction_distribution.q01 | -2.571539 |
| prediction_distribution.q05 | -1.693023 |
| prediction_distribution.q25 | -0.638109 |
| prediction_distribution.q75 | 0.595181 |
| prediction_distribution.q95 | 1.520995 |
| prediction_distribution.q99 | 2.226610 |
| prediction_distribution.skew | -0.186259 |
| prediction_distribution.kurtosis | 0.531709 |
| prediction_distribution.positive_rate | 0.491895 |
| prediction_distribution.negative_rate | 0.508105 |
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
| probability_distribution.mean | 0.496604 |
| probability_distribution.std | 0.091715 |
| probability_distribution.min | 0.149983 |
| probability_distribution.max | 0.849625 |
| probability_distribution.median | 0.498054 |
| probability_distribution.q01 | 0.267958 |
| probability_distribution.q05 | 0.339999 |
| probability_distribution.q25 | 0.437737 |
| probability_distribution.q75 | 0.558026 |
| probability_distribution.q95 | 0.644331 |
| probability_distribution.q99 | 0.704698 |
| probability_distribution.skew | -0.138291 |
| probability_distribution.kurtosis | 0.125116 |
| probability_distribution.positive_rate | 1.000000 |
| probability_distribution.negative_rate | 0.0 |
| probability_distribution.zero_rate | 0.0 |


## Dense Forecast Diagnostics
| Artifact | Link |
| --- | --- |
| fold_backtest_diagnostics | [open](artifacts/diagnostics/fold_backtest_diagnostics.csv) |
| forecast_alpha_summary | [open](artifacts/diagnostics/forecast_alpha_diagnostics_summary.json) |
| forecast_baselines | [open](artifacts/diagnostics/forecast_baselines.csv) |
| lightgbm_importance | [open](artifacts/diagnostics/lightgbm_importance.csv) |
| prediction_distribution | [open](artifacts/diagnostics/prediction_distribution.csv) |
| prediction_metrics | [open](artifacts/diagnostics/prediction_metrics.csv) |
| regime_diagnostics | [open](artifacts/diagnostics/regime_diagnostics.csv) |
| regime_performance | [open](artifacts/diagnostics/regime_performance.csv) |
| summary | [open](artifacts/diagnostics/summary.json) |
| turnover_cost_timeseries | [open](artifacts/diagnostics/turnover_cost_timeseries.csv) |


## Forecast Baselines
| Name | Cum Return | Ann Return | Ann Vol | Sharpe | Sortino | Calmar | Max DD | Profit Factor | Hit Rate | Turnover | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| model_strategy | 2.046243 | 0.561370 | 0.222356 | 2.524645 | 3.372257 | 4.670323 | -0.120199 | 1.179219 | 0.500760 | 368.000000 | 0.052846 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | 0.375698 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000875 |
| random_sign_same_rate | -0.457876 | -0.217220 | 0.343242 | -0.632850 | -0.740844 | -0.400729 | -0.542063 | 0.974885 | 0.477800 | 1.030e+03 | 0.147365 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | 0.031471 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.818224 |
| simple_trend | -0.532426 | -0.262198 | 0.436182 | -0.601119 | -0.674248 | -0.419772 | -0.624619 | 0.983873 | 0.490531 | 772.000000 | 0.075969 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.067777 |
| mean_fold_return | 0.125558 |
| fold_return_std | 0.144360 |
| worst_fold_return | -0.013096 |
| best_fold_return | 0.433528 |
| worst_3_fold_average_return | 0.005287 |
| profitable_fold_count | 9.000000 |
| profitable_fold_rate | 0.900000 |
| median_fold_sharpe | 2.064188 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.3, 'best_rank': 1, 'mean_importance': 1142.4, 'mean_importance_normalized': 0.10558200538255673, 'folds': [{'fold': 0, 'rank': 1, 'importance': 1203.0, 'importance_normalized': 0.1157621247113164}, {'fold': 1, 'rank': 1, 'importance': 1146.0, 'importance_normalized': 0.10582694616308062}, {'fold': 2, 'rank': 1, 'importance': 1205.0, 'importance_normalized': 0.11030757964115709}, {'fold': 3, 'rank': 1, 'importance': 1176.0, 'importance_normalized': 0.10802866066507441}, {'fold': 4, 'rank': 1, 'importance': 1124.0, 'importance_normalized': 0.10384331116038432}, {'fold': 5, 'rank': 1, 'importance': 1124.0, 'importance_normalized': 0.10384331116038432}, {'fold': 6, 'rank': 1, 'importance': 1150.0, 'importance_normalized': 0.10619632468371965}, {'fold': 7, 'rank': 2, 'importance': 1100.0, 'importance_normalized': 0.10062202707647273}, {'fold': 8, 'rank': 2, 'importance': 1086.0, 'importance_normalized': 0.09984370690447733}, {'fold': 9, 'rank': 2, 'importance': 1110.0, 'importance_normalized': 0.1015460616595005}], 'stability_rank': 1}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.7, 'best_rank': 1, 'mean_importance': 1077.5, 'mean_importance_normalized': 0.09951130722855439, 'folds': [{'fold': 0, 'rank': 2, 'importance': 987.0, 'importance_normalized': 0.09497690531177828}, {'fold': 1, 'rank': 2, 'importance': 1006.0, 'importance_normalized': 0.09289869794071474}, {'fold': 2, 'rank': 2, 'importance': 1095.0, 'importance_normalized': 0.10023800805565727}, {'fold': 3, 'rank': 2, 'importance': 1015.0, 'importance_normalized': 0.09323902259783208}, {'fold': 4, 'rank': 2, 'importance': 1091.0, 'importance_normalized': 0.10079453067257946}, {'fold': 5, 'rank': 2, 'importance': 1077.0, 'importance_normalized': 0.09950110864745011}, {'fold': 6, 'rank': 2, 'importance': 1069.0, 'importance_normalized': 0.09871640964077939}, {'fold': 7, 'rank': 1, 'importance': 1151.0, 'importance_normalized': 0.1052872301500183}, {'fold': 8, 'rank': 1, 'importance': 1132.0, 'importance_normalized': 0.10407281419509055}, {'fold': 9, 'rank': 1, 'importance': 1152.0, 'importance_normalized': 0.10538834507364377}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 3.0, 'best_rank': 3, 'mean_importance': 883.5, 'mean_importance_normalized': 0.0815688881850832, 'folds': [{'fold': 0, 'rank': 3, 'importance': 741.0, 'importance_normalized': 0.07130484988452655}, {'fold': 1, 'rank': 3, 'importance': 902.0, 'importance_normalized': 0.0832948564041001}, {'fold': 2, 'rank': 3, 'importance': 870.0, 'importance_normalized': 0.07964115708531673}, {'fold': 3, 'rank': 3, 'importance': 898.0, 'importance_normalized': 0.08249127319492927}, {'fold': 4, 'rank': 3, 'importance': 857.0, 'importance_normalized': 0.07917590539541759}, {'fold': 5, 'rank': 3, 'importance': 899.0, 'importance_normalized': 0.08305617147080561}, {'fold': 6, 'rank': 3, 'importance': 888.0, 'importance_normalized': 0.08200203158186352}, {'fold': 7, 'rank': 3, 'importance': 930.0, 'importance_normalized': 0.08507135016465422}, {'fold': 8, 'rank': 3, 'importance': 898.0, 'importance_normalized': 0.08255952928197113}, {'fold': 9, 'rank': 3, 'importance': 952.0, 'importance_normalized': 0.08709175738724728}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.1, 'best_rank': 4, 'mean_importance': 815.3, 'mean_importance_normalized': 0.07528567155929453, 'folds': [{'fold': 0, 'rank': 5, 'importance': 713.0, 'importance_normalized': 0.06861046959199384}, {'fold': 1, 'rank': 4, 'importance': 765.0, 'importance_normalized': 0.0706436420722135}, {'fold': 2, 'rank': 4, 'importance': 814.0, 'importance_normalized': 0.07451482973269864}, {'fold': 3, 'rank': 4, 'importance': 778.0, 'importance_normalized': 0.0714679404740033}, {'fold': 4, 'rank': 4, 'importance': 848.0, 'importance_normalized': 0.07834441980783444}, {'fold': 5, 'rank': 4, 'importance': 851.0, 'importance_normalized': 0.07862158167036216}, {'fold': 6, 'rank': 4, 'importance': 812.0, 'importance_normalized': 0.07498383968972204}, {'fold': 7, 'rank': 4, 'importance': 836.0, 'importance_normalized': 0.07647274057811929}, {'fold': 8, 'rank': 4, 'importance': 843.0, 'importance_normalized': 0.07750298795623793}, {'fold': 9, 'rank': 4, 'importance': 893.0, 'importance_normalized': 0.08169426401976032}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.9, 'best_rank': 4, 'mean_importance': 725.5, 'mean_importance_normalized': 0.06703826284995604, 'folds': [{'fold': 0, 'rank': 4, 'importance': 726.0, 'importance_normalized': 0.06986143187066975}, {'fold': 1, 'rank': 5, 'importance': 744.0, 'importance_normalized': 0.06870440483885862}, {'fold': 2, 'rank': 5, 'importance': 700.0, 'importance_normalized': 0.06407909190772611}, {'fold': 3, 'rank': 5, 'importance': 707.0, 'importance_normalized': 0.06494580194745544}, {'fold': 4, 'rank': 5, 'importance': 760.0, 'importance_normalized': 0.07021433850702144}, {'fold': 5, 'rank': 5, 'importance': 712.0, 'importance_normalized': 0.06577974870657798}, {'fold': 6, 'rank': 5, 'importance': 725.0, 'importance_normalized': 0.06694985686582325}, {'fold': 7, 'rank': 5, 'importance': 725.0, 'importance_normalized': 0.06631906330040249}, {'fold': 8, 'rank': 5, 'importance': 726.0, 'importance_normalized': 0.06674634549967821}, {'fold': 9, 'rank': 5, 'importance': 730.0, 'importance_normalized': 0.06678254505534718}], 'stability_rank': 5}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.3, 'best_rank': 6, 'mean_importance': 604.0, 'mean_importance_normalized': 0.05579498138134644, 'folds': [{'fold': 0, 'rank': 6, 'importance': 573.0, 'importance_normalized': 0.055138568129330254}, {'fold': 1, 'rank': 6, 'importance': 593.0, 'importance_normalized': 0.05476036568473543}, {'fold': 2, 'rank': 6, 'importance': 618.0, 'importance_normalized': 0.056572683998535336}, {'fold': 3, 'rank': 8, 'importance': 604.0, 'importance_normalized': 0.05548410802866067}, {'fold': 4, 'rank': 6, 'importance': 612.0, 'importance_normalized': 0.0565410199556541}, {'fold': 5, 'rank': 6, 'importance': 587.0, 'importance_normalized': 0.05423133776792313}, {'fold': 6, 'rank': 6, 'importance': 627.0, 'importance_normalized': 0.057900083110167144}, {'fold': 7, 'rank': 6, 'importance': 605.0, 'importance_normalized': 0.05534211489206001}, {'fold': 8, 'rank': 6, 'importance': 614.0, 'importance_normalized': 0.05644938861818516}, {'fold': 9, 'rank': 7, 'importance': 607.0, 'importance_normalized': 0.05553014362821334}], 'stability_rank': 6}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.3, 'best_rank': 6, 'mean_importance': 562.5, 'mean_importance_normalized': 0.051944368926938225, 'folds': [{'fold': 0, 'rank': 7, 'importance': 510.0, 'importance_normalized': 0.04907621247113164}, {'fold': 1, 'rank': 8, 'importance': 544.0, 'importance_normalized': 0.05023547880690738}, {'fold': 2, 'rank': 7, 'importance': 602.0, 'importance_normalized': 0.055108019040644454}, {'fold': 3, 'rank': 7, 'importance': 608.0, 'importance_normalized': 0.05585155245269153}, {'fold': 4, 'rank': 8, 'importance': 531.0, 'importance_normalized': 0.049057649667405764}, {'fold': 5, 'rank': 8, 'importance': 494.0, 'importance_normalized': 0.04563932002956393}, {'fold': 6, 'rank': 7, 'importance': 592.0, 'importance_normalized': 0.054668021054575675}, {'fold': 7, 'rank': 8, 'importance': 538.0, 'importance_normalized': 0.04921331869740212}, {'fold': 8, 'rank': 7, 'importance': 585.0, 'importance_normalized': 0.053783212282798566}, {'fold': 9, 'rank': 6, 'importance': 621.0, 'importance_normalized': 0.05681090476626109}], 'stability_rank': 7}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.5, 'best_rank': 6, 'mean_importance': 571.4, 'mean_importance_normalized': 0.05276346435745381, 'folds': [{'fold': 0, 'rank': 9, 'importance': 490.0, 'importance_normalized': 0.04715165511932255}, {'fold': 1, 'rank': 7, 'importance': 586.0, 'importance_normalized': 0.05411395327361714}, {'fold': 2, 'rank': 8, 'importance': 570.0, 'importance_normalized': 0.05217868912486269}, {'fold': 3, 'rank': 6, 'importance': 627.0, 'importance_normalized': 0.057596913466838144}, {'fold': 4, 'rank': 7, 'importance': 578.0, 'importance_normalized': 0.053399852180339984}, {'fold': 5, 'rank': 7, 'importance': 584.0, 'importance_normalized': 0.05395417590539542}, {'fold': 6, 'rank': 8, 'importance': 576.0, 'importance_normalized': 0.053190506972019574}, {'fold': 7, 'rank': 7, 'importance': 540.0, 'importance_normalized': 0.04939626783754116}, {'fold': 8, 'rank': 8, 'importance': 568.0, 'importance_normalized': 0.05222028132757194}, {'fold': 9, 'rank': 8, 'importance': 595.0, 'importance_normalized': 0.05443234836702955}], 'stability_rank': 8}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 8.9, 'best_rank': 8, 'mean_importance': 476.2, 'mean_importance_normalized': 0.044010745285178, 'folds': [{'fold': 0, 'rank': 8, 'importance': 496.0, 'importance_normalized': 0.04772902232486528}, {'fold': 1, 'rank': 9, 'importance': 499.0, 'importance_normalized': 0.04607997044971835}, {'fold': 2, 'rank': 9, 'importance': 463.0, 'importance_normalized': 0.04238374221896741}, {'fold': 3, 'rank': 9, 'importance': 490.0, 'importance_normalized': 0.045011941943781004}, {'fold': 4, 'rank': 9, 'importance': 493.0, 'importance_normalized': 0.045546932742054694}, {'fold': 5, 'rank': 9, 'importance': 449.0, 'importance_normalized': 0.04148189209164819}, {'fold': 6, 'rank': 9, 'importance': 477.0, 'importance_normalized': 0.04404838858620371}, {'fold': 7, 'rank': 9, 'importance': 463.0, 'importance_normalized': 0.04235272594218807}, {'fold': 8, 'rank': 9, 'importance': 464.0, 'importance_normalized': 0.042658821366185526}, {'fold': 9, 'rank': 9, 'importance': 468.0, 'importance_normalized': 0.04281401518616778}], 'stability_rank': 9}, {'feature': 'vol_rolling_24', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 10.2, 'best_rank': 10, 'mean_importance': 407.8, 'mean_importance_normalized': 0.03769209964872391, 'folds': [{'fold': 0, 'rank': 10, 'importance': 436.0, 'importance_normalized': 0.04195535026943803}, {'fold': 1, 'rank': 10, 'importance': 432.0, 'importance_normalized': 0.03989288022901468}, {'fold': 2, 'rank': 10, 'importance': 416.0, 'importance_normalized': 0.03808128890516294}, {'fold': 3, 'rank': 11, 'importance': 381.0, 'importance_normalized': 0.03499908138893992}, {'fold': 4, 'rank': 10, 'importance': 410.0, 'importance_normalized': 0.03787878787878788}, {'fold': 5, 'rank': 10, 'importance': 398.0, 'importance_normalized': 0.03677014042867702}, {'fold': 6, 'rank': 11, 'importance': 397.0, 'importance_normalized': 0.03666081817342322}, {'fold': 7, 'rank': 10, 'importance': 430.0, 'importance_normalized': 0.03933406512989389}, {'fold': 8, 'rank': 10, 'importance': 385.0, 'importance_normalized': 0.035395789280132386}, {'fold': 9, 'rank': 10, 'importance': 393.0, 'importance_normalized': 0.035952794803769096}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.825375 | 2.144099 | -0.156158 | 1.108997 | 0.068273 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.352515 | 1.710715 | -0.104619 | 1.208593 | 0.031356 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 1.037943 | 2.707306 | -0.146584 | 1.134349 | 0.058948 |
| ema_trend_48_192 | negative | 2.183e+04 | 0.968148 | 2.991308 | -0.117731 | 1.203629 | 0.037530 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.751573 | 2.700021 | -0.111079 | 1.179299 | 0.043649 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 1.322136 | 2.599868 | -0.260894 | 1.121499 | 0.047494 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 305 |
| average_r | 0.811095 |
| median_r | 0.595414 |
| exit_reason_counts.position_exit | 303 |
| exit_reason_counts.reversal | 2 |
| avg_max_favorable_r | 3.480115 |
| median_max_favorable_r | 2.596936 |
| avg_max_adverse_r | -2.567866 |
| median_max_adverse_r | -1.679154 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.983607 |
| avg_giveback_r | 2.669020 |
| avg_capture_ratio | -3.576135 |
| completed_trade_count | 305 |
| win_rate | 0.596721 |
| trade_return_profit_factor | 2.190325 |
| trade_r_profit_factor | 1.786966 |
| trade_profit_factor | 2.190325 |
| entry_trade_cost | 0.030500 |
| exit_trade_cost | 0.030895 |
| holding_trade_cost | 0.0 |
| total_trade_cost | 0.061395 |
| position_transition_count | 608 |
| turnover_event_count | 608 |
| exposed_bar_count | 7354 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.983607 |
| avg_mfe_r_of_losers | 1.379545 |
| median_mfe_r_of_losers | 1.065058 |
| avg_mfe_r_before_loss | 1.379545 |
| median_mfe_r_before_loss | 1.065058 |
| loser_reached_0_5r_rate | 0.795082 |
| loser_reached_1r_rate | 0.540984 |
| loser_reached_1_5r_rate | 0.336066 |
| loser_reached_2r_rate | 0.213115 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -3.576135 |
| median_capture_ratio | 0.288202 |
| avg_giveback_r | 2.669020 |
| median_giveback_r | 1.953316 |
| avg_giveback_r_winners | 1.810903 |
| avg_giveback_r_losers | 3.956196 |
| median_giveback_r_winners | 1.539245 |
| median_giveback_r_losers | 3.235554 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.983607 |
| winner_had_mae_below_minus_0_25r_rate | 0.808743 |
| winner_had_mae_below_minus_0_5r_rate | 0.672131 |
| winner_had_mae_below_minus_1r_rate | 0.497268 |
| avg_mae_r_of_winners | -1.196412 |
| median_mae_r_of_winners | -0.999472 |
| p90_abs_mae_r_of_winners | 2.599899 |
| avg_mae_r | -2.567866 |
| median_mae_r | -1.679154 |
| q10_mae_r | -5.979945 |
| q25_mae_r | -3.322479 |
| q75_mae_r | -0.817721 |
| q90_mae_r | -0.204711 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.600000 |
| prob_final_loss | 0.400000 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 1.000000 |
| prob_mfe_ge_0_5r | 0.914754 |
| prob_final_loss_given_mfe_ge_0_5r | 0.347670 |
| prob_mfe_ge_1r | 0.803279 |
| prob_final_loss_given_mfe_ge_1r | 0.269388 |
| prob_mfe_ge_1_5r | 0.698361 |
| prob_final_loss_given_mfe_ge_1_5r | 0.192488 |
| prob_mfe_ge_2r | 0.590164 |
| prob_final_loss_given_mfe_ge_2r | 0.144444 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 12.190164 |
| median_time_to_mfe | 12.000000 |
| avg_time_to_mae | 9.718033 |
| median_time_to_mae | 9.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.075410 |
| prob_mfe_ge_0_5r_within_2_bars | 0.114754 |
| prob_mfe_ge_1r_within_4_bars | 0.114754 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.811095 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.600000 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 305 |
| counterfactual.baseline.avg_r | 0.811095 |
| counterfactual.baseline.median_r | 0.595414 |
| counterfactual.baseline.win_rate | 0.600000 |
| counterfactual.baseline.profit_factor | 1.786966 |
| counterfactual.breakeven_after_0_5r.trade_count | 305 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.086310 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.009836 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.236246 |
| counterfactual.breakeven_after_1_0r.trade_count | 305 |
| counterfactual.breakeven_after_1_0r.avg_r | 0.172865 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.127869 |
| counterfactual.breakeven_after_1_0r.profit_factor | 1.523174 |
| counterfactual.exit_at_first_0_5r.trade_count | 305 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.373878 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.973770 |
| counterfactual.exit_at_first_0_5r.profit_factor | 4.308427 |
| counterfactual.exit_at_first_1_0r.trade_count | 305 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.560403 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.898361 |
| counterfactual.exit_at_first_1_0r.profit_factor | 2.696059 |
| counterfactual.partial_50pct_at_1r.trade_count | 305 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.685749 |
| counterfactual.partial_50pct_at_1r.median_r | 0.797707 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.711475 |
| counterfactual.partial_50pct_at_1r.profit_factor | 2.215775 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 305 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.782789 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.473504 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.583607 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.761170 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 305 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.744806 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.878030 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.898361 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 3.254156 |
| counterfactual.best_policy_by_avg_r | baseline |
| counterfactual.best_policy_by_profit_factor | exit_at_first_0_5r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 303 | 0.816267 | 0.595414 | 0.600660 | 3.482115 | -2.566272 | 2.665848 | 24.112211 | 1.790561 | 0.993399 | 0.914191 | 0.801980 |
| reversal | 2 | 0.027591 | 0.027591 | 0.500000 | 3.177087 | -2.809361 | 3.149496 | 24.000000 | 1.036811 | 1.000000 | 1.000000 | 1.000000 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 305 |
| gross_pnl | 5.637771 |
| net_pnl | 5.244945 |
| total_cost | 0.061000 |
| cost_to_gross_pnl | 0.069678 |

### Trade Count By Asset
| Asset | Trades |
| --- | --- |
| ETHUSD | 305 |

### Performance Breakdowns
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asset | ETHUSD | 305 | 1.994719 | 0.030500 | 0.030895 | 0.0 | 0.061395 | 1.933323 | 2.190325 | 0.596721 |
| side | long | 168 | 1.143716 | 0.016800 | 0.017020 | 0.0 | 0.033820 | 1.109896 | 2.265868 | 0.565476 |
| side | short | 137 | 0.851003 | 0.013700 | 0.013875 | 0.0 | 0.027575 | 0.823428 | 2.101705 | 0.635036 |
| volatility_regime | missing | 305 | 1.994719 | 0.030500 | 0.030895 | 0.0 | 0.061395 | 1.933323 | 2.190325 | 0.596721 |
| year | 2022 | 108 | 0.947463 | 0.010800 | 0.010985 | 0.0 | 0.021785 | 0.925678 | 2.509245 | 0.675926 |
| year | 2023 | 125 | 0.501214 | 0.012500 | 0.012596 | 0.0 | 0.025096 | 0.476118 | 1.748051 | 0.536000 |
| year | 2024 | 72 | 0.546042 | 0.007200 | 0.007315 | 0.0 | 0.014515 | 0.531527 | 2.419747 | 0.583333 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1860 |
| actual_trade_count | 305 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 5.244945 |
| sharpe | 3.785716 |
| sortino | 4.388107 |
| calmar | 8.284249 |
| max_drawdown | -0.130454 |
| profit_factor | 1.176927 |
| hit_rate | 0.493578 |
| trade_count | 305 |
| gross_pnl | 5.637771 |
| net_pnl | 5.244945 |
| total_cost | 0.061000 |
| cost_to_gross_pnl | 0.069678 |
| average_r | 0.811095 |
| median_r | 0.595414 |

### Side Diagnostics
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| side | long | 168 | 1.143716 |  |  |  | 0.0 | 1.109896 | 2.265868 | 0.565476 |
| side | short | 137 | 0.851003 |  |  |  | 0.0 | 0.823428 | 2.101705 | 0.635036 |

### Year Diagnostics
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| year | 2022 | 108 | 0.947463 |  |  |  | 0.0 | 0.925678 | 2.509245 | 0.675926 |
| year | 2023 | 125 | 0.501214 |  |  |  | 0.0 | 0.476118 | 1.748051 | 0.536000 |
| year | 2024 | 72 | 0.546042 |  |  |  | 0.0 | 0.531527 | 2.419747 | 0.583333 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 5.244945 |
| cost_x1.annualized_return | 1.080709 |
| cost_x1.annualized_vol | 0.285470 |
| cost_x1.sharpe | 3.785716 |
| cost_x1.sortino | 4.388107 |
| cost_x1.calmar | 8.284249 |
| cost_x1.max_drawdown | -0.130454 |
| cost_x1.profit_factor | 1.176927 |
| cost_x1.hit_rate | 0.493578 |
| cost_x1.bar_return_profit_factor | 1.176927 |
| cost_x1.conventional_sharpe | 2.708481 |
| cost_x1.return_over_vol_sharpe | 3.785716 |
| cost_x1.profit_factor_scope | bar_returns |
| cost_x1.metric_scope | bar_returns |
| cost_x1.annualization_mode | fixed_periods |
| cost_x1.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x1.gross_pnl | 5.637771 |
| cost_x1.net_pnl | 5.244945 |
| cost_x1.total_cost | 0.061000 |
| cost_x1.cost_drag | 0.392826 |
| cost_x1.cost_to_gross_pnl | 0.069678 |
| cost_x1.gross_return_sum | 1.993977 |
| cost_x1.net_return_sum | 1.932977 |
| cost_x1.cost_return_sum | 0.061000 |
| cost_x1.avg_turnover | 0.013927 |
| cost_x1.total_turnover | 610.000000 |
| cost_x1.evaluation_scope | strict_oos_only |
| cost_x1.evaluation_start | 2022-03-14T15:00:00 |
| cost_x1.evaluation_end | 2024-09-17T10:30:00 |
| cost_x1.evaluation_rows | 43800 |
| cost_x2.cumulative_return | 4.875330 |
| cost_x2.annualized_return | 1.030546 |
| cost_x2.annualized_vol | 0.285487 |
| cost_x2.sharpe | 3.609782 |
| cost_x2.sortino | 4.246779 |
| cost_x2.calmar | 7.857797 |
| cost_x2.max_drawdown | -0.131150 |
| cost_x2.profit_factor | 1.170619 |
| cost_x2.hit_rate | 0.492923 |
| cost_x2.bar_return_profit_factor | 1.170619 |
| cost_x2.conventional_sharpe | 2.622853 |
| cost_x2.return_over_vol_sharpe | 3.609782 |
| cost_x2.profit_factor_scope | bar_returns |
| cost_x2.metric_scope | bar_returns |
| cost_x2.annualization_mode | fixed_periods |
| cost_x2.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x2.gross_pnl | 5.637771 |
| cost_x2.net_pnl | 4.875330 |
| cost_x2.total_cost | 0.122000 |
| cost_x2.cost_drag | 0.762441 |
| cost_x2.cost_to_gross_pnl | 0.135238 |
| cost_x2.gross_return_sum | 1.993977 |
| cost_x2.net_return_sum | 1.871977 |
| cost_x2.cost_return_sum | 0.122000 |
| cost_x2.avg_turnover | 0.013927 |
| cost_x2.total_turnover | 610.000000 |
| cost_x2.evaluation_scope | strict_oos_only |
| cost_x2.evaluation_start | 2022-03-14T15:00:00 |
| cost_x2.evaluation_end | 2024-09-17T10:30:00 |
| cost_x2.evaluation_rows | 43800 |
| cost_x3.cumulative_return | 4.527558 |
| cost_x3.annualized_return | 0.981588 |
| cost_x3.annualized_vol | 0.285513 |
| cost_x3.sharpe | 3.437985 |
| cost_x3.sortino | 4.105395 |
| cost_x3.calmar | 7.445011 |
| cost_x3.max_drawdown | -0.131845 |
| cost_x3.profit_factor | 1.164360 |
| cost_x3.hit_rate | 0.492398 |
| cost_x3.bar_return_profit_factor | 1.164360 |
| cost_x3.conventional_sharpe | 2.537160 |
| cost_x3.return_over_vol_sharpe | 3.437985 |
| cost_x3.profit_factor_scope | bar_returns |
| cost_x3.metric_scope | bar_returns |
| cost_x3.annualization_mode | fixed_periods |
| cost_x3.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x3.gross_pnl | 5.637771 |
| cost_x3.net_pnl | 4.527558 |
| cost_x3.total_cost | 0.183000 |
| cost_x3.cost_drag | 1.110214 |
| cost_x3.cost_to_gross_pnl | 0.196924 |
| cost_x3.gross_return_sum | 1.993977 |
| cost_x3.net_return_sum | 1.810977 |
| cost_x3.cost_return_sum | 0.183000 |
| cost_x3.avg_turnover | 0.013927 |
| cost_x3.total_turnover | 610.000000 |
| cost_x3.evaluation_scope | strict_oos_only |
| cost_x3.evaluation_start | 2022-03-14T15:00:00 |
| cost_x3.evaluation_end | 2024-09-17T10:30:00 |
| cost_x3.evaluation_rows | 43800 |
| cost_x5.cumulative_return | 3.892460 |
| cost_x5.annualized_return | 0.887169 |
| cost_x5.annualized_vol | 0.285589 |
| cost_x5.sharpe | 3.106459 |
| cost_x5.sortino | 3.822554 |
| cost_x5.calmar | 6.433672 |
| cost_x5.max_drawdown | -0.137895 |
| cost_x5.profit_factor | 1.151980 |
| cost_x5.hit_rate | 0.491219 |
| cost_x5.bar_return_profit_factor | 1.151980 |
| cost_x5.conventional_sharpe | 2.365608 |
| cost_x5.return_over_vol_sharpe | 3.106459 |
| cost_x5.profit_factor_scope | bar_returns |
| cost_x5.metric_scope | bar_returns |
| cost_x5.annualization_mode | fixed_periods |
| cost_x5.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x5.gross_pnl | 5.637771 |
| cost_x5.net_pnl | 3.892460 |
| cost_x5.total_cost | 0.305000 |
| cost_x5.cost_drag | 1.745311 |
| cost_x5.cost_to_gross_pnl | 0.309575 |
| cost_x5.gross_return_sum | 1.993977 |
| cost_x5.net_return_sum | 1.688977 |
| cost_x5.cost_return_sum | 0.305000 |
| cost_x5.avg_turnover | 0.013927 |
| cost_x5.total_turnover | 610.000000 |
| cost_x5.evaluation_scope | strict_oos_only |
| cost_x5.evaluation_start | 2022-03-14T15:00:00 |
| cost_x5.evaluation_end | 2024-09-17T10:30:00 |
| cost_x5.evaluation_rows | 43800 |

### Slippage Stress
| Metric | Value |
| --- | --- |
| slippage_x1.cumulative_return | 5.244945 |
| slippage_x1.annualized_return | 1.080709 |
| slippage_x1.annualized_vol | 0.285470 |
| slippage_x1.sharpe | 3.785716 |
| slippage_x1.sortino | 4.388107 |
| slippage_x1.calmar | 8.284249 |
| slippage_x1.max_drawdown | -0.130454 |
| slippage_x1.profit_factor | 1.176927 |
| slippage_x1.hit_rate | 0.493578 |
| slippage_x1.bar_return_profit_factor | 1.176927 |
| slippage_x1.conventional_sharpe | 2.708481 |
| slippage_x1.return_over_vol_sharpe | 3.785716 |
| slippage_x1.profit_factor_scope | bar_returns |
| slippage_x1.metric_scope | bar_returns |
| slippage_x1.annualization_mode | fixed_periods |
| slippage_x1.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x1.gross_pnl | 5.244945 |
| slippage_x1.net_pnl | 5.244945 |
| slippage_x1.total_cost | 0.0 |
| slippage_x1.cost_drag | 0.0 |
| slippage_x1.cost_to_gross_pnl | 0.0 |
| slippage_x1.gross_return_sum | 1.932977 |
| slippage_x1.net_return_sum | 1.932977 |
| slippage_x1.cost_return_sum | 0.0 |
| slippage_x1.avg_turnover | 0.0 |
| slippage_x1.total_turnover | 0.0 |
| slippage_x1.evaluation_scope | strict_oos_only |
| slippage_x1.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x1.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x1.evaluation_rows | 43800 |
| slippage_x2.cumulative_return | 5.244945 |
| slippage_x2.annualized_return | 1.080709 |
| slippage_x2.annualized_vol | 0.285470 |
| slippage_x2.sharpe | 3.785716 |
| slippage_x2.sortino | 4.388107 |
| slippage_x2.calmar | 8.284249 |
| slippage_x2.max_drawdown | -0.130454 |
| slippage_x2.profit_factor | 1.176927 |
| slippage_x2.hit_rate | 0.493578 |
| slippage_x2.bar_return_profit_factor | 1.176927 |
| slippage_x2.conventional_sharpe | 2.708481 |
| slippage_x2.return_over_vol_sharpe | 3.785716 |
| slippage_x2.profit_factor_scope | bar_returns |
| slippage_x2.metric_scope | bar_returns |
| slippage_x2.annualization_mode | fixed_periods |
| slippage_x2.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x2.gross_pnl | 5.244945 |
| slippage_x2.net_pnl | 5.244945 |
| slippage_x2.total_cost | 0.0 |
| slippage_x2.cost_drag | 0.0 |
| slippage_x2.cost_to_gross_pnl | 0.0 |
| slippage_x2.gross_return_sum | 1.932977 |
| slippage_x2.net_return_sum | 1.932977 |
| slippage_x2.cost_return_sum | 0.0 |
| slippage_x2.avg_turnover | 0.0 |
| slippage_x2.total_turnover | 0.0 |
| slippage_x2.evaluation_scope | strict_oos_only |
| slippage_x2.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x2.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x2.evaluation_rows | 43800 |
| slippage_x3.cumulative_return | 5.244945 |
| slippage_x3.annualized_return | 1.080709 |
| slippage_x3.annualized_vol | 0.285470 |
| slippage_x3.sharpe | 3.785716 |
| slippage_x3.sortino | 4.388107 |
| slippage_x3.calmar | 8.284249 |
| slippage_x3.max_drawdown | -0.130454 |
| slippage_x3.profit_factor | 1.176927 |
| slippage_x3.hit_rate | 0.493578 |
| slippage_x3.bar_return_profit_factor | 1.176927 |
| slippage_x3.conventional_sharpe | 2.708481 |
| slippage_x3.return_over_vol_sharpe | 3.785716 |
| slippage_x3.profit_factor_scope | bar_returns |
| slippage_x3.metric_scope | bar_returns |
| slippage_x3.annualization_mode | fixed_periods |
| slippage_x3.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x3.gross_pnl | 5.244945 |
| slippage_x3.net_pnl | 5.244945 |
| slippage_x3.total_cost | 0.0 |
| slippage_x3.cost_drag | 0.0 |
| slippage_x3.cost_to_gross_pnl | 0.0 |
| slippage_x3.gross_return_sum | 1.932977 |
| slippage_x3.net_return_sum | 1.932977 |
| slippage_x3.cost_return_sum | 0.0 |
| slippage_x3.avg_turnover | 0.0 |
| slippage_x3.total_turnover | 0.0 |
| slippage_x3.evaluation_scope | strict_oos_only |
| slippage_x3.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x3.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x3.evaluation_rows | 43800 |

### Entry Delay
| Metric | Value |
| --- | --- |
| delay_1_bars.cumulative_return | 4.152920 |
| delay_1_bars.annualized_return | 0.926732 |
| delay_1_bars.annualized_vol | 0.282979 |
| delay_1_bars.sharpe | 3.274911 |
| delay_1_bars.sortino | 3.957168 |
| delay_1_bars.calmar | 6.938126 |
| delay_1_bars.max_drawdown | -0.133571 |
| delay_1_bars.profit_factor | 1.158987 |
| delay_1_bars.hit_rate | 0.491610 |
| delay_1_bars.bar_return_profit_factor | 1.158987 |
| delay_1_bars.conventional_sharpe | 2.458161 |
| delay_1_bars.return_over_vol_sharpe | 3.274911 |
| delay_1_bars.profit_factor_scope | bar_returns |
| delay_1_bars.metric_scope | bar_returns |
| delay_1_bars.annualization_mode | fixed_periods |
| delay_1_bars.sharpe_legacy_alias | return_over_vol_sharpe |
| delay_1_bars.gross_pnl | 4.152920 |
| delay_1_bars.net_pnl | 4.152920 |
| delay_1_bars.total_cost | 0.0 |
| delay_1_bars.cost_drag | 0.0 |
| delay_1_bars.cost_to_gross_pnl | 0.0 |
| delay_1_bars.gross_return_sum | 1.739022 |
| delay_1_bars.net_return_sum | 1.739022 |
| delay_1_bars.cost_return_sum | 0.0 |
| delay_1_bars.avg_turnover | 0.0 |
| delay_1_bars.total_turnover | 0.0 |
| delay_1_bars.evaluation_scope | strict_oos_only |
| delay_1_bars.evaluation_start | 2022-03-14T15:00:00 |
| delay_1_bars.evaluation_end | 2024-09-17T10:30:00 |
| delay_1_bars.evaluation_rows | 43800 |
| delay_2_bars.cumulative_return | 4.123202 |
| delay_2_bars.annualized_return | 0.922280 |
| delay_2_bars.annualized_vol | 0.281292 |
| delay_2_bars.sharpe | 3.278728 |
| delay_2_bars.sortino | 3.975810 |
| delay_2_bars.calmar | 6.234184 |
| delay_2_bars.max_drawdown | -0.147939 |
| delay_2_bars.profit_factor | 1.159443 |
| delay_2_bars.hit_rate | 0.489906 |
| delay_2_bars.bar_return_profit_factor | 1.159443 |
| delay_2_bars.conventional_sharpe | 2.462996 |
| delay_2_bars.return_over_vol_sharpe | 3.278728 |
| delay_2_bars.profit_factor_scope | bar_returns |
| delay_2_bars.metric_scope | bar_returns |
| delay_2_bars.annualization_mode | fixed_periods |
| delay_2_bars.sharpe_legacy_alias | return_over_vol_sharpe |
| delay_2_bars.gross_pnl | 4.123202 |
| delay_2_bars.net_pnl | 4.123202 |
| delay_2_bars.total_cost | 0.0 |
| delay_2_bars.cost_drag | 0.0 |
| delay_2_bars.cost_to_gross_pnl | 0.0 |
| delay_2_bars.gross_return_sum | 1.732052 |
| delay_2_bars.net_return_sum | 1.732052 |
| delay_2_bars.cost_return_sum | 0.0 |
| delay_2_bars.avg_turnover | 0.0 |
| delay_2_bars.total_turnover | 0.0 |
| delay_2_bars.evaluation_scope | strict_oos_only |
| delay_2_bars.evaluation_start | 2022-03-14T15:00:00 |
| delay_2_bars.evaluation_end | 2024-09-17T10:30:00 |
| delay_2_bars.evaluation_rows | 43800 |

### Walk Forward
| Metric | Value |
| --- | --- |
| aggregation_kind | calendar_periods |
| total_calendar_periods | 7 |
| active_oos_periods | 3 |
| positive_active_periods | 3 |
| positive_active_period_ratio | 1.000000 |
| min_active_period_cumulative_return | 0.566636 |
| median_active_period_cumulative_return | 0.656739 |
| mean_active_period_cumulative_return | 0.876478 |
| mean_active_period_sharpe | 4.022753 |
| std_active_period_sharpe | 1.058148 |
| worst_active_period_max_drawdown | -0.130454 |

### Gap Stress
| Metric | Value |
| --- | --- |
| enabled | false |
| reason | gap_loss_per_exposure <= 0 |


## Target Diagnostics
| Metric | Value |
| --- | --- |
| kind | future_return_regression |
| horizon_bars | 24 |
| labeled_rows | 108934 |
| unavailable_tail_count | 71 |


## Target Distribution
| Metric | Value |
| --- | --- |
| oos_direction.labeled_rows | 43800 |
| oos_direction.class_counts.0 | 22030 |
| oos_direction.class_counts.1 | 21770 |
| oos_direction.positive_rate | 0.497032 |
| oos_direction.negative_rate | 0.502968 |
| oos_prediction.rows | 43800 |
| oos_prediction.mean | -0.037288 |
| oos_prediction.std | 0.975167 |
| oos_prediction.min | -4.455228 |
| oos_prediction.max | 4.450357 |
| oos_prediction.median | -0.019791 |
| oos_prediction.q01 | -2.571539 |
| oos_prediction.q05 | -1.693023 |
| oos_prediction.q25 | -0.638109 |
| oos_prediction.q75 | 0.595181 |
| oos_prediction.q95 | 1.520995 |
| oos_prediction.q99 | 2.226610 |
| oos_prediction.skew | -0.186259 |
| oos_prediction.kurtosis | 0.531709 |
| oos_prediction.positive_rate | 0.491895 |
| oos_prediction.negative_rate | 0.508105 |
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
| 1 | atr_48 | 1.142e+03 | 0.105582 | 10 | feature_importances_ |
| 2 | vol_rolling_192 | 1.078e+03 | 0.099511 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 883.500000 | 0.081569 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 815.300000 | 0.075286 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 725.500000 | 0.067038 | 10 | feature_importances_ |
| 6 | bollinger_bandwidth_rank_192 | 604.000000 | 0.055795 | 10 | feature_importances_ |
| 7 | atr_over_price_48 | 571.400000 | 0.052763 | 10 | feature_importances_ |
| 8 | vol_rolling_48 | 562.500000 | 0.051944 | 10 | feature_importances_ |
| 9 | atr_pct_rank_192 | 476.200000 | 0.044011 | 10 | feature_importances_ |
| 10 | vol_rolling_24 | 407.800000 | 0.037692 | 10 | feature_importances_ |
| 11 | mama_minus_fama_over_atr | 396.800000 | 0.036663 | 10 | feature_importances_ |
| 12 | close_over_bb_upper_192 | 307.200000 | 0.028376 | 10 | feature_importances_ |
| 13 | ret_48 | 298.300000 | 0.027565 | 10 | feature_importances_ |
| 14 | close_over_bb_mid_192 | 290.800000 | 0.026844 | 10 | feature_importances_ |
| 15 | bollinger_percent_b | 262.000000 | 0.024202 | 10 | feature_importances_ |
| 16 | distance_from_ema96_atr | 186.500000 | 0.017232 | 10 | feature_importances_ |
| 17 | roofing_filter_over_atr | 166.400000 | 0.015371 | 10 | feature_importances_ |
| 18 | ret_24 | 166.100000 | 0.015342 | 10 | feature_importances_ |
| 19 | atr_pct | 148.200000 | 0.013687 | 10 | feature_importances_ |
| 20 | ret_16 | 121.900000 | 0.011266 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 5.637771 |
| net_pnl | 5.244945 |
| total_cost | 0.061000 |
| cost_drag | 0.392826 |
| cost_to_gross_pnl | 0.069678 |
| avg_turnover | 0.013927 |
| total_turnover | 610.000000 |
| mean_abs_signal | 0.042466 |
| signal_turnover | 0.049269 |
| flat_rate | 0.957534 |
| long_rate | 0.024110 |
| short_rate | 0.018356 |
| trade_rate | 0.167900 |
| executed_trade_count | 7354 |
| avg_signal_executed | 0.034539 |
| avg_pred_prob_executed | 0.505220 |
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
| 0 |  | 0.047523 | 0.043760 | 0.003600 | 0.761008 | 0.008219 |  |  |  |  |
| 1 |  | 0.441570 | 0.433528 | 0.005600 | 7.877336 | 0.012785 |  |  |  |  |
| 2 |  | 0.299223 | 0.293778 | 0.004200 | 5.792683 | 0.009589 |  |  |  |  |
| 3 |  | 0.211055 | 0.205981 | 0.004200 | 5.766997 | 0.009589 |  |  |  |  |
| 4 |  | 0.084440 | 0.080327 | 0.003800 | 2.311205 | 0.008676 |  |  |  |  |
| 5 |  | 0.031342 | 0.027843 | 0.003400 | 1.316910 | 0.007763 |  |  |  |  |
| 6 |  | 0.004924 | 0.001113 | 0.003800 | 0.032449 | 0.008676 |  |  |  |  |
| 7 |  | 0.129607 | 0.127125 | 0.002200 | 3.773452 | 0.005023 |  |  |  |  |
| 8 |  | -0.009534 | -0.013096 | 0.003600 | -0.265525 | 0.008219 |  |  |  |  |
| 9 |  | 0.057763 | 0.055226 | 0.002400 | 1.817171 | 0.005479 |  |  |  |  |


## Model Fold Diagnostics
| Fold | Train Raw | Train Used | Train Missing Features | Train Not Labeled | Train Without Fit | Test Rows | Pred Rows | Test Missing Features | Test Not Candidates | Test Without Prediction | Train Feature Missing | Test Feature Missing | Eval Rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 35016 | 34969 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 1 | 39396 | 39349 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 2 | 43752 | 43705 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 3 | 48108 | 48061 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 4 | 52464 | 52417 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 5 | 56820 | 56773 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 6 | 61176 | 61129 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 7 | 65532 | 65485 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 8 | 69888 | 69841 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |
| 9 | 74244 | 74197 | 0 | 0 | 0 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4380 |


## Monitoring
- Drifted feature count: `8` / `48`
| Asset | Feature | PSI |
| --- | --- | --- |
| ETHUSD | atr_48 | 1.187111 |
| ETHUSD | atr_over_price_48 | 0.669230 |
| ETHUSD | atr_pct | 0.669230 |
| ETHUSD | vol_rolling_192 | 0.612124 |
| ETHUSD | vol_rolling_96 | 0.551451 |
| ETHUSD | vol_rolling_48 | 0.474270 |
| ETHUSD | vol_rolling_24 | 0.406533 |
| ETHUSD | bollinger_bandwidth | 0.358901 |


## Drift By Family
| Family | Feature Count | Drifted Count | Drifted Ratio | Mean Abs PSI | Max Abs PSI |
| --- | --- | --- | --- | --- | --- |
| unclassified | 35 | 3 | 0.085714 | 0.106934 | 1.187111 |
| atr_adx_range | 1 | 1 | 1.000000 | 0.669230 | 0.669230 |
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
| 47 | close_over_vwap_32 |
| 48 | close_ret_robust_z_128 |

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
        window: 128
        output_col: close_ret_robust_z_128
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
- step: vwap
  params:
    high_col: high
    low_col: low
    close_col: close
    volume_col: volume
    windows:
    - 32
  outputs: {}
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: close
        denominator_col: vwap_32
        output_col: close_over_vwap_32
        subtract: 1.0
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
    save_processed: true
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
  - close_over_vwap_32
  - close_ret_robust_z_128
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
  final_refit: true
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
  annualization_mode: null
  max_cost_r: null
  risk_per_trade: null
  max_holding_bars: null
  asset_params: {}
  dynamic_exit: {}
  strategy_path: {}
  dynamic_exits: {}
  partial_exits: {}
  allow_short: true
  oos_mode: strict
  execution_price: close_lagged
  execution_delay_bars: 0
  estimated_spread_cost_per_unit_turnover: 0.0
  commission_per_unit_turnover: 0.0
  slippage_per_unit_turnover: 0.0
  holding_cost_per_exposed_bar: 0.0
  allow_cost_layering: false
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
- `trade_events`: `trade_events.csv`
- `positions`: `positions.csv`
- `monitoring`: `monitoring_report.json`
- `diagnostic_trade_events`: `report_assets/trade_events.csv`
- `trades`: `report_assets/trades.csv`
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
- `diagnostics_lightgbm_importance`: `artifacts/diagnostics/lightgbm_importance.csv`
- `diagnostics_prediction_autocorrelation`: `artifacts/diagnostics/prediction_autocorrelation.png`
- `diagnostics_prediction_distribution`: `artifacts/diagnostics/prediction_distribution.csv`
- `diagnostics_prediction_metrics`: `artifacts/diagnostics/prediction_metrics.csv`
- `diagnostics_prediction_quantiles`: `artifacts/diagnostics/prediction_quantiles.png`
- `diagnostics_regime_diagnostics`: `artifacts/diagnostics/regime_diagnostics.csv`
- `diagnostics_regime_performance`: `artifacts/diagnostics/regime_performance.csv`
- `diagnostics_summary`: `artifacts/diagnostics/summary.json`
- `diagnostics_turnover_cost_timeseries`: `artifacts/diagnostics/turnover_cost_timeseries.csv`
- `diagnostics_cost_vs_gross_pnl`: `artifacts/diagnostics/cost_vs_gross_pnl.png`
- `diagnostics_lgbm_gain_importance`: `artifacts/diagnostics/lgbm_gain_importance.png`
- `diagnostics_lgbm_split_importance`: `artifacts/diagnostics/lgbm_split_importance.png`
- `diagnostics_prediction_histogram`: `artifacts/diagnostics/prediction_histogram.png`
- `diagnostics_prediction_timeseries`: `artifacts/diagnostics/prediction_timeseries.png`
- `diagnostics_prediction_vs_realized`: `artifacts/diagnostics/prediction_vs_realized.png`
- `diagnostics_residual_histogram`: `artifacts/diagnostics/residual_histogram.png`
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
