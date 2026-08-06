# Experiment Report: model07_vwap32_rov64_rz256

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/BEST/ethusd/trial0041_validation_suite_v2/06_feature_window_surface/model07/model07_vwap32_rov64_rz256.yaml`
- Model kind: `lightgbm_regressor`
- Symbols: `ETHUSD`
- Data source: `dukascopy_csv` at interval `30m`
- Data window: `None` to `2026-06-09 23:30:00`
- Rows / columns: `109005` rows, `131` columns
- Target: `future_return_regression` horizon `24`
- Feature count: `49`
- Runtime seed: `7`

## Pipeline Trace

### 1. Entry Point
- `runner.run_experiment` -> `src.experiments.runner.run_experiment(config_path: 'str | Path') -> 'ExperimentResult | Any'`
- `runner._load_asset_frames` -> `src.experiments.runner._load_asset_frames(data_cfg: 'dict[str, object]')`
- `pipeline.run_experiment_pipeline` -> `src.experiments.orchestration.pipeline.run_experiment_pipeline(config_path: 'str | Path', *, load_asset_frames_fn: 'LoadAssetFramesFn', save_processed_snapshot_fn: 'SaveProcessedFn') -> 'ExperimentResult'`

```yaml
config_path: /workspace/config/experiments/foundation_alpha/BEST/ethusd/trial0041_validation_suite_v2/06_feature_window_surface/model07/model07_vwap32_rov64_rz256.yaml
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
  params={'returns_col': 'close_ret', 'rolling_windows': [24, 48, 64, 96, 192], 'ewma_spans': [], 'annualization_factor': None}
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
    - 64
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
        volatility_col: vol_rolling_64
        output_col: close_ret_over_vol_64
    robust_zscore:
      params:
        source_col: close_ret
        window: 256
        output_col: close_ret_robust_z_256
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
- close_ret_over_vol_64
- close_ret_robust_z_256
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
  - close_ret_over_vol_64
  - close_ret_robust_z_256
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
| cumulative_return | 5.179175 |
| annualized_return | 1.071916 |
| annualized_vol | 0.300820 |
| sharpe | 3.563315 |
| sortino | 4.092358 |
| calmar | 7.156652 |
| max_drawdown | -0.149779 |
| profit_factor | 1.165149 |
| hit_rate | 0.492469 |
| annualization_mode | fixed_periods |
| metric_scope | bar_returns |
| avg_turnover | 0.014658 |
| total_turnover | 642.000000 |
| gross_pnl | 5.588923 |
| net_pnl | 5.179175 |
| total_cost | 0.064200 |
| cost_drag | 0.409748 |
| cost_to_gross_pnl | 0.073314 |
| gross_return_sum | 1.997844 |
| net_return_sum | 1.933644 |
| cost_return_sum | 0.064200 |
| conventional_sharpe | 2.571165 |
| return_over_vol_sharpe | 3.563315 |
| sharpe_legacy_alias | return_over_vol_sharpe |
| bar_return_profit_factor | 1.165149 |
| profit_factor_scope | bar_returns |
| evaluation_scope | strict_oos_only |
| evaluation_start | 2022-03-14T15:00:00 |
| evaluation_end | 2024-09-17T10:30:00 |
| evaluation_rows | 43800 |
| trade_count | 321 |
| average_r | 0.761942 |
| median_r | 0.549160 |
| mtm_cumulative_return | 5.179175 |
| mtm_annualized_return | 1.071916 |
| mtm_annualized_vol | 0.300820 |
| mtm_sharpe | 3.563315 |
| mtm_conventional_sharpe | 2.571165 |
| mtm_return_over_vol_sharpe | 3.563315 |
| mtm_max_drawdown | -0.149779 |
| mtm_profit_factor | 1.165149 |
| mtm_bar_return_profit_factor | 1.165149 |
| flat_rate | 0.956187 |
| long_rate | 0.025822 |
| short_rate | 0.017991 |
| avg_max_favorable_r | 3.610313 |
| avg_max_adverse_r | -2.747318 |
| loser_was_positive_rate | 0.984848 |
| avg_giveback_r | 2.848371 |
| avg_capture_ratio | -5.817798 |
| robustness_walk_forward_total_calendar_periods | 7.000000 |
| robustness_walk_forward_active_oos_periods | 3.000000 |
| robustness_walk_forward_positive_active_periods | 3.000000 |
| robustness_walk_forward_positive_active_period_ratio | 1.000000 |
| robustness_walk_forward_min_active_period_cumulative_return | 0.402843 |
| robustness_walk_forward_worst_active_period_max_drawdown | -0.149779 |
| robustness_walk_forward_mean_active_period_sharpe | 3.925629 |
| robustness_walk_forward_std_active_period_sharpe | 1.445502 |
| robustness_cost_x1_cumulative_return | 5.179175 |
| robustness_cost_x1_sharpe | 3.563315 |
| robustness_cost_x1_max_drawdown | -0.149779 |
| robustness_cost_x1_profit_factor | 1.165149 |
| robustness_cost_x2_cumulative_return | 4.794870 |
| robustness_cost_x2_sharpe | 3.388458 |
| robustness_cost_x2_max_drawdown | -0.151650 |
| robustness_cost_x2_profit_factor | 1.159003 |
| robustness_cost_x3_cumulative_return | 4.434431 |
| robustness_cost_x3_sharpe | 3.217941 |
| robustness_cost_x3_max_drawdown | -0.153517 |
| robustness_cost_x3_profit_factor | 1.152898 |
| robustness_cost_x5_cumulative_return | 3.779323 |
| robustness_cost_x5_sharpe | 2.889541 |
| robustness_cost_x5_max_drawdown | -0.166380 |
| robustness_cost_x5_profit_factor | 1.140831 |
| robustness_delay_1_bars_cumulative_return | 4.973662 |
| robustness_delay_1_bars_sharpe | 3.490869 |
| robustness_delay_1_bars_max_drawdown | -0.147056 |
| robustness_delay_1_bars_profit_factor | 1.163210 |
| robustness_delay_2_bars_cumulative_return | 4.387070 |
| robustness_delay_2_bars_sharpe | 3.253649 |
| robustness_delay_2_bars_max_drawdown | -0.153970 |
| robustness_delay_2_bars_profit_factor | 1.155150 |
| completed_trade_count | 321 |
| win_rate | 0.585670 |
| trade_return_profit_factor | 2.029596 |
| trade_r_profit_factor | 1.663997 |
| trade_profit_factor | 2.029596 |
| entry_trade_cost | 0.032100 |
| exit_trade_cost | 0.032500 |
| holding_trade_cost | 0.0 |
| total_trade_cost | 0.064600 |
| position_transition_count | 636 |
| turnover_event_count | 636 |
| exposed_bar_count | 7750 |
| bar_return_profit_factor_scope | bar_returns |
| trade_return_profit_factor_scope | completed_trade_net_returns |
| trade_r_profit_factor_scope | completed_trade_net_r_multiples |
| trade_profit_factor_scope | completed_trade_net_returns |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.043813 |
| signal_turnover | 0.052740 |
| long_rate | 0.025822 |
| short_rate | 0.017991 |
| flat_rate | 0.956187 |
| executed_trade_count | 7750 |
| trade_rate | 0.176941 |
| avg_signal_executed | 0.036774 |
| avg_pred_prob_executed | 0.509165 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.523265 |
| classification.brier | 0.254381 |
| classification.roc_auc | 0.528487 |
| classification.log_loss | 0.702705 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.175898 |
| regression.rmse | 2.641956 |
| regression.mse | 6.979932 |
| regression.r2 | -0.117866 |
| regression.correlation | 0.046881 |
| regression.directional_accuracy | 0.523151 |
| regression.mean_prediction | -0.008525 |
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
| prediction_distribution.mean | -0.008525 |
| prediction_distribution.std | 0.982910 |
| prediction_distribution.min | -4.394032 |
| prediction_distribution.max | 4.176103 |
| prediction_distribution.median | 0.015470 |
| prediction_distribution.q01 | -2.571181 |
| prediction_distribution.q05 | -1.694337 |
| prediction_distribution.q25 | -0.605182 |
| prediction_distribution.q75 | 0.619243 |
| prediction_distribution.q95 | 1.569277 |
| prediction_distribution.q99 | 2.288592 |
| prediction_distribution.skew | -0.185424 |
| prediction_distribution.kurtosis | 0.493809 |
| prediction_distribution.positive_rate | 0.506324 |
| prediction_distribution.negative_rate | 0.493676 |
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
| probability_distribution.mean | 0.499327 |
| probability_distribution.std | 0.092422 |
| probability_distribution.min | 0.153046 |
| probability_distribution.max | 0.835477 |
| probability_distribution.median | 0.501525 |
| probability_distribution.q01 | 0.268263 |
| probability_distribution.q05 | 0.339947 |
| probability_distribution.q25 | 0.440989 |
| probability_distribution.q75 | 0.560436 |
| probability_distribution.q95 | 0.648985 |
| probability_distribution.q99 | 0.709706 |
| probability_distribution.skew | -0.147972 |
| probability_distribution.kurtosis | 0.126212 |
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
| model_strategy | 1.809407 | 0.511631 | 0.230271 | 2.221867 | 3.008574 | 3.558856 | -0.143763 | 1.154503 | 0.496535 | 392.000000 | 0.058444 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | 0.375698 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000875 |
| random_sign_same_rate | -0.467114 | -0.222584 | 0.346100 | -0.643120 | -0.758126 | -0.404796 | -0.549867 | 0.974700 | 0.479530 | 1.058e+03 | 0.145870 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | 0.031471 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.818224 |
| simple_trend | -0.532426 | -0.262198 | 0.436182 | -0.601119 | -0.674248 | -0.419772 | -0.624619 | 0.983873 | 0.490531 | 772.000000 | 0.075969 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.053903 |
| mean_fold_return | 0.115550 |
| fold_return_std | 0.133402 |
| worst_fold_return | 0.003569 |
| best_fold_return | 0.369633 |
| worst_3_fold_average_return | 0.012169 |
| profitable_fold_count | 10.000000 |
| profitable_fold_rate | 1.000000 |
| median_fold_sharpe | 1.388776 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.5, 'best_rank': 1, 'mean_importance': 1094.9, 'mean_importance_normalized': 0.10131478076155967, 'folds': [{'fold': 0, 'rank': 1, 'importance': 1172.0, 'importance_normalized': 0.11304012345679013}, {'fold': 1, 'rank': 1, 'importance': 1079.0, 'importance_normalized': 0.10078460676256305}, {'fold': 2, 'rank': 1, 'importance': 1144.0, 'importance_normalized': 0.1045417161655853}, {'fold': 3, 'rank': 1, 'importance': 1156.0, 'importance_normalized': 0.10601614086573734}, {'fold': 4, 'rank': 1, 'importance': 1104.0, 'importance_normalized': 0.1024213748956304}, {'fold': 5, 'rank': 2, 'importance': 1050.0, 'importance_normalized': 0.0971682398667407}, {'fold': 6, 'rank': 2, 'importance': 1095.0, 'importance_normalized': 0.10051404442812557}, {'fold': 7, 'rank': 2, 'importance': 1065.0, 'importance_normalized': 0.09739368998628258}, {'fold': 8, 'rank': 2, 'importance': 1080.0, 'importance_normalized': 0.09930121368150055}, {'fold': 9, 'rank': 2, 'importance': 1004.0, 'importance_normalized': 0.09196665750664101}], 'stability_rank': 1}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.5, 'best_rank': 1, 'mean_importance': 1073.1, 'mean_importance_normalized': 0.09921761577674751, 'folds': [{'fold': 0, 'rank': 2, 'importance': 998.0, 'importance_normalized': 0.09625771604938271}, {'fold': 1, 'rank': 2, 'importance': 1024.0, 'importance_normalized': 0.09564730057911451}, {'fold': 2, 'rank': 2, 'importance': 1065.0, 'importance_normalized': 0.09732248926254226}, {'fold': 3, 'rank': 2, 'importance': 1017.0, 'importance_normalized': 0.09326852531181218}, {'fold': 4, 'rank': 2, 'importance': 1015.0, 'importance_normalized': 0.09416457927451526}, {'fold': 5, 'rank': 1, 'importance': 1078.0, 'importance_normalized': 0.09975939292985378}, {'fold': 6, 'rank': 1, 'importance': 1127.0, 'importance_normalized': 0.1034514411602717}, {'fold': 7, 'rank': 1, 'importance': 1109.0, 'importance_normalized': 0.10141746684956561}, {'fold': 8, 'rank': 1, 'importance': 1129.0, 'importance_normalized': 0.10380654652445752}, {'fold': 9, 'rank': 1, 'importance': 1169.0, 'importance_normalized': 0.10708069982595951}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 3.0, 'best_rank': 3, 'mean_importance': 903.4, 'mean_importance_normalized': 0.08349847130410294, 'folds': [{'fold': 0, 'rank': 3, 'importance': 773.0, 'importance_normalized': 0.07455632716049383}, {'fold': 1, 'rank': 3, 'importance': 860.0, 'importance_normalized': 0.0803287875957407}, {'fold': 2, 'rank': 3, 'importance': 894.0, 'importance_normalized': 0.08169606140911999}, {'fold': 3, 'rank': 3, 'importance': 923.0, 'importance_normalized': 0.08464783565663976}, {'fold': 4, 'rank': 3, 'importance': 918.0, 'importance_normalized': 0.08516559977734484}, {'fold': 5, 'rank': 3, 'importance': 868.0, 'importance_normalized': 0.08032574495650564}, {'fold': 6, 'rank': 3, 'importance': 918.0, 'importance_normalized': 0.08426656875344227}, {'fold': 7, 'rank': 3, 'importance': 931.0, 'importance_normalized': 0.08513946044810243}, {'fold': 8, 'rank': 3, 'importance': 954.0, 'importance_normalized': 0.08771607208532549}, {'fold': 9, 'rank': 3, 'importance': 995.0, 'importance_normalized': 0.09114225519831455}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.2, 'best_rank': 4, 'mean_importance': 781.6, 'mean_importance_normalized': 0.07223126189574859, 'folds': [{'fold': 0, 'rank': 5, 'importance': 647.0, 'importance_normalized': 0.06240354938271605}, {'fold': 1, 'rank': 5, 'importance': 697.0, 'importance_normalized': 0.0651036801793387}, {'fold': 2, 'rank': 4, 'importance': 809.0, 'importance_normalized': 0.07392853879192178}, {'fold': 3, 'rank': 4, 'importance': 747.0, 'importance_normalized': 0.06850696991929567}, {'fold': 4, 'rank': 4, 'importance': 820.0, 'importance_normalized': 0.0760738472956675}, {'fold': 5, 'rank': 4, 'importance': 826.0, 'importance_normalized': 0.07643901536183602}, {'fold': 6, 'rank': 4, 'importance': 816.0, 'importance_normalized': 0.07490361666972646}, {'fold': 7, 'rank': 4, 'importance': 802.0, 'importance_normalized': 0.07334247828074988}, {'fold': 8, 'rank': 4, 'importance': 832.0, 'importance_normalized': 0.07649871276204487}, {'fold': 9, 'rank': 4, 'importance': 820.0, 'importance_normalized': 0.07511221031418888}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.8, 'best_rank': 4, 'mean_importance': 720.8, 'mean_importance_normalized': 0.06668857903105474, 'folds': [{'fold': 0, 'rank': 4, 'importance': 741.0, 'importance_normalized': 0.07146990740740741}, {'fold': 1, 'rank': 4, 'importance': 720.0, 'importance_normalized': 0.0672520082196899}, {'fold': 2, 'rank': 5, 'importance': 709.0, 'importance_normalized': 0.06479027688933565}, {'fold': 3, 'rank': 5, 'importance': 678.0, 'importance_normalized': 0.06217901687454145}, {'fold': 4, 'rank': 5, 'importance': 708.0, 'importance_normalized': 0.0656832730308934}, {'fold': 5, 'rank': 5, 'importance': 739.0, 'importance_normalized': 0.06838793263002035}, {'fold': 6, 'rank': 5, 'importance': 761.0, 'importance_normalized': 0.06985496603635029}, {'fold': 7, 'rank': 5, 'importance': 717.0, 'importance_normalized': 0.06556927297668039}, {'fold': 8, 'rank': 5, 'importance': 732.0, 'importance_normalized': 0.06730415593968371}, {'fold': 9, 'rank': 5, 'importance': 703.0, 'importance_normalized': 0.06439498030594486}], 'stability_rank': 5}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.4, 'best_rank': 6, 'mean_importance': 604.9, 'mean_importance_normalized': 0.05594295244576083, 'folds': [{'fold': 0, 'rank': 6, 'importance': 577.0, 'importance_normalized': 0.055652006172839504}, {'fold': 1, 'rank': 6, 'importance': 606.0, 'importance_normalized': 0.05660377358490566}, {'fold': 2, 'rank': 6, 'importance': 621.0, 'importance_normalized': 0.056748606415059855}, {'fold': 3, 'rank': 6, 'importance': 610.0, 'importance_normalized': 0.05594277329420396}, {'fold': 4, 'rank': 7, 'importance': 608.0, 'importance_normalized': 0.056405974580202245}, {'fold': 5, 'rank': 6, 'importance': 609.0, 'importance_normalized': 0.056357579122709604}, {'fold': 6, 'rank': 7, 'importance': 575.0, 'importance_normalized': 0.05278134753075087}, {'fold': 7, 'rank': 6, 'importance': 620.0, 'importance_normalized': 0.0566986739826246}, {'fold': 8, 'rank': 6, 'importance': 613.0, 'importance_normalized': 0.05636263332107393}, {'fold': 9, 'rank': 8, 'importance': 610.0, 'importance_normalized': 0.05587615645323807}], 'stability_rank': 6}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.0, 'best_rank': 6, 'mean_importance': 583.9, 'mean_importance_normalized': 0.05400403503896707, 'folds': [{'fold': 0, 'rank': 7, 'importance': 551.0, 'importance_normalized': 0.05314429012345679}, {'fold': 1, 'rank': 7, 'importance': 597.0, 'importance_normalized': 0.05576312348215954}, {'fold': 2, 'rank': 7, 'importance': 586.0, 'importance_normalized': 0.05355021474915471}, {'fold': 3, 'rank': 7, 'importance': 591.0, 'importance_normalized': 0.05420029347028613}, {'fold': 4, 'rank': 6, 'importance': 615.0, 'importance_normalized': 0.057055385471750625}, {'fold': 5, 'rank': 7, 'importance': 602.0, 'importance_normalized': 0.055709790856931334}, {'fold': 6, 'rank': 8, 'importance': 551.0, 'importance_normalized': 0.05057829998164127}, {'fold': 7, 'rank': 7, 'importance': 573.0, 'importance_normalized': 0.052400548696845}, {'fold': 8, 'rank': 7, 'importance': 554.0, 'importance_normalized': 0.050937844795880836}, {'fold': 9, 'rank': 7, 'importance': 619.0, 'importance_normalized': 0.05670055876156453}], 'stability_rank': 7}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.7, 'best_rank': 6, 'mean_importance': 552.1, 'mean_importance_normalized': 0.05103567073142105, 'folds': [{'fold': 0, 'rank': 9, 'importance': 485.0, 'importance_normalized': 0.04677854938271605}, {'fold': 1, 'rank': 8, 'importance': 540.0, 'importance_normalized': 0.05043900616476742}, {'fold': 2, 'rank': 8, 'importance': 564.0, 'importance_normalized': 0.05153979713058576}, {'fold': 3, 'rank': 8, 'importance': 585.0, 'importance_normalized': 0.05365003668378577}, {'fold': 4, 'rank': 8, 'importance': 574.0, 'importance_normalized': 0.05325169310696725}, {'fold': 5, 'rank': 8, 'importance': 499.0, 'importance_normalized': 0.0461780492319082}, {'fold': 6, 'rank': 6, 'importance': 585.0, 'importance_normalized': 0.05369928400954654}, {'fold': 7, 'rank': 8, 'importance': 524.0, 'importance_normalized': 0.04791952446273434}, {'fold': 8, 'rank': 8, 'importance': 540.0, 'importance_normalized': 0.049650606840750275}, {'fold': 9, 'rank': 6, 'importance': 625.0, 'importance_normalized': 0.05725016030044884}], 'stability_rank': 8}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 9.0, 'best_rank': 8, 'mean_importance': 469.9, 'mean_importance_normalized': 0.04348535757766267, 'folds': [{'fold': 0, 'rank': 8, 'importance': 496.0, 'importance_normalized': 0.047839506172839504}, {'fold': 1, 'rank': 9, 'importance': 509.0, 'importance_normalized': 0.04754343358864188}, {'fold': 2, 'rank': 9, 'importance': 503.0, 'importance_normalized': 0.04596545737000823}, {'fold': 3, 'rank': 9, 'importance': 466.0, 'importance_normalized': 0.04273661041819516}, {'fold': 4, 'rank': 9, 'importance': 471.0, 'importance_normalized': 0.043696075702755355}, {'fold': 5, 'rank': 9, 'importance': 464.0, 'importance_normalized': 0.04293910790301684}, {'fold': 6, 'rank': 9, 'importance': 456.0, 'importance_normalized': 0.04185790343308243}, {'fold': 7, 'rank': 9, 'importance': 447.0, 'importance_normalized': 0.040877914951989024}, {'fold': 8, 'rank': 10, 'importance': 429.0, 'importance_normalized': 0.039444648767929386}, {'fold': 9, 'rank': 9, 'importance': 458.0, 'importance_normalized': 0.04195291746816891}], 'stability_rank': 9}, {'feature': 'vol_rolling_24', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 9.9, 'best_rank': 9, 'mean_importance': 427.9, 'mean_importance_normalized': 0.03959091195037228, 'folds': [{'fold': 0, 'rank': 10, 'importance': 445.0, 'importance_normalized': 0.04292052469135803}, {'fold': 1, 'rank': 10, 'importance': 440.0, 'importance_normalized': 0.04109844946758827}, {'fold': 2, 'rank': 10, 'importance': 445.0, 'importance_normalized': 0.04066526546650827}, {'fold': 3, 'rank': 10, 'importance': 396.0, 'importance_normalized': 0.03631694790902421}, {'fold': 4, 'rank': 10, 'importance': 409.0, 'importance_normalized': 0.03794415066332684}, {'fold': 5, 'rank': 10, 'importance': 430.0, 'importance_normalized': 0.03979270775495095}, {'fold': 6, 'rank': 10, 'importance': 402.0, 'importance_normalized': 0.03690104644758583}, {'fold': 7, 'rank': 10, 'importance': 435.0, 'importance_normalized': 0.039780521262002745}, {'fold': 8, 'rank': 9, 'importance': 452.0, 'importance_normalized': 0.04155939683707245}, {'fold': 9, 'rank': 10, 'importance': 425.0, 'importance_normalized': 0.03893010900430521}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.863024 | 2.186421 | -0.156919 | 1.106993 | 0.069858 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.295909 | 1.370319 | -0.144811 | 1.160463 | 0.040547 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 0.871323 | 2.274589 | -0.173639 | 1.115558 | 0.065684 |
| ema_trend_48_192 | negative | 2.183e+04 | 0.928974 | 2.734881 | -0.128127 | 1.174948 | 0.042597 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.383062 | 1.347628 | -0.142735 | 1.096994 | 0.068611 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 1.587522 | 3.061523 | -0.226294 | 1.130518 | 0.046696 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 321 |
| average_r | 0.761942 |
| median_r | 0.549160 |
| exit_reason_counts.position_exit | 315 |
| exit_reason_counts.reversal | 6 |
| avg_max_favorable_r | 3.610313 |
| median_max_favorable_r | 2.512684 |
| avg_max_adverse_r | -2.747318 |
| median_max_adverse_r | -1.722170 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.984848 |
| avg_giveback_r | 2.848371 |
| avg_capture_ratio | -5.817798 |
| completed_trade_count | 321 |
| win_rate | 0.585670 |
| trade_return_profit_factor | 2.029596 |
| trade_r_profit_factor | 1.663997 |
| trade_profit_factor | 2.029596 |
| entry_trade_cost | 0.032100 |
| exit_trade_cost | 0.032500 |
| holding_trade_cost | 0.0 |
| total_trade_cost | 0.064600 |
| position_transition_count | 636 |
| turnover_event_count | 636 |
| exposed_bar_count | 7750 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.984848 |
| avg_mfe_r_of_losers | 1.302137 |
| median_mfe_r_of_losers | 1.028530 |
| avg_mfe_r_before_loss | 1.302137 |
| median_mfe_r_before_loss | 1.028530 |
| loser_reached_0_5r_rate | 0.742424 |
| loser_reached_1r_rate | 0.507576 |
| loser_reached_1_5r_rate | 0.303030 |
| loser_reached_2r_rate | 0.196970 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -5.817798 |
| median_capture_ratio | 0.272338 |
| avg_giveback_r | 2.848371 |
| median_giveback_r | 2.053232 |
| avg_giveback_r_winners | 1.979340 |
| avg_giveback_r_losers | 4.092666 |
| median_giveback_r_winners | 1.559358 |
| median_giveback_r_losers | 3.290346 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.984127 |
| winner_had_mae_below_minus_0_25r_rate | 0.820106 |
| winner_had_mae_below_minus_0_5r_rate | 0.703704 |
| winner_had_mae_below_minus_1r_rate | 0.481481 |
| avg_mae_r_of_winners | -1.254524 |
| median_mae_r_of_winners | -0.943679 |
| p90_abs_mae_r_of_winners | 2.635680 |
| avg_mae_r | -2.747318 |
| median_mae_r | -1.722170 |
| q10_mae_r | -6.321813 |
| q25_mae_r | -3.379185 |
| q75_mae_r | -0.782989 |
| q90_mae_r | -0.231845 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.588785 |
| prob_final_loss | 0.411215 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 0.970297 |
| prob_mfe_ge_0_5r | 0.890966 |
| prob_final_loss_given_mfe_ge_0_5r | 0.342657 |
| prob_mfe_ge_1r | 0.791277 |
| prob_final_loss_given_mfe_ge_1r | 0.263780 |
| prob_mfe_ge_1_5r | 0.676012 |
| prob_final_loss_given_mfe_ge_1_5r | 0.184332 |
| prob_mfe_ge_2r | 0.585670 |
| prob_final_loss_given_mfe_ge_2r | 0.138298 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 12.401869 |
| median_time_to_mfe | 13.000000 |
| avg_time_to_mae | 9.305296 |
| median_time_to_mae | 7.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.049844 |
| prob_mfe_ge_0_5r_within_2_bars | 0.109034 |
| prob_mfe_ge_1r_within_4_bars | 0.121495 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.761942 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.588785 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 321 |
| counterfactual.baseline.avg_r | 0.761942 |
| counterfactual.baseline.median_r | 0.549160 |
| counterfactual.baseline.win_rate | 0.588785 |
| counterfactual.baseline.profit_factor | 1.663997 |
| counterfactual.breakeven_after_0_5r.trade_count | 321 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.058211 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.009346 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.252520 |
| counterfactual.breakeven_after_1_0r.trade_count | 321 |
| counterfactual.breakeven_after_1_0r.avg_r | 0.132404 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.130841 |
| counterfactual.breakeven_after_1_0r.profit_factor | 1.345633 |
| counterfactual.exit_at_first_0_5r.trade_count | 321 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.404990 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.965732 |
| counterfactual.exit_at_first_0_5r.profit_factor | 6.200446 |
| counterfactual.exit_at_first_1_0r.trade_count | 321 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.497451 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.884735 |
| counterfactual.exit_at_first_1_0r.profit_factor | 2.298564 |
| counterfactual.partial_50pct_at_1r.trade_count | 321 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.629696 |
| counterfactual.partial_50pct_at_1r.median_r | 0.766398 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.694704 |
| counterfactual.partial_50pct_at_1r.profit_factor | 1.973048 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 321 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.652234 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.399016 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.566978 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.560391 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 321 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.653914 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.828526 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.884735 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 2.707000 |
| counterfactual.best_policy_by_avg_r | baseline |
| counterfactual.best_policy_by_profit_factor | exit_at_first_0_5r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 315 | 0.760300 | 0.525012 | 0.584127 | 3.619150 | -2.755710 | 2.858850 | 24.146032 | 1.662838 | 0.993651 | 0.892063 | 0.790476 |
| reversal | 6 | 0.848148 | 1.483240 | 0.833333 | 3.146362 | -2.306715 | 2.298214 | 24.000000 | 1.723561 | 1.000000 | 0.833333 | 0.833333 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 321 |
| gross_pnl | 5.588923 |
| net_pnl | 5.179175 |
| total_cost | 0.064200 |
| cost_to_gross_pnl | 0.073314 |

### Trade Count By Asset
| Asset | Trades |
| --- | --- |
| ETHUSD | 321 |

### Performance Breakdowns
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asset | ETHUSD | 321 | 2.007489 | 0.032100 | 0.032500 | 0.0 | 0.064600 | 1.942889 | 2.029596 | 0.585670 |
| side | long | 178 | 1.130236 | 0.017800 | 0.018022 | 0.0 | 0.035822 | 1.094414 | 2.147622 | 0.567416 |
| side | short | 143 | 0.877253 | 0.014300 | 0.014478 | 0.0 | 0.028778 | 0.848475 | 1.909011 | 0.608392 |
| volatility_regime | missing | 321 | 2.007489 | 0.032100 | 0.032500 | 0.0 | 0.064600 | 1.942889 | 2.029596 | 0.585670 |
| year | 2022 | 109 | 0.919556 | 0.010900 | 0.011078 | 0.0 | 0.021978 | 0.897579 | 2.067529 | 0.614679 |
| year | 2023 | 135 | 0.390988 | 0.013500 | 0.013578 | 0.0 | 0.027078 | 0.363910 | 1.534929 | 0.570370 |
| year | 2024 | 77 | 0.696944 | 0.007700 | 0.007843 | 0.0 | 0.015543 | 0.681401 | 2.862033 | 0.571429 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1919 |
| actual_trade_count | 321 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 5.179175 |
| sharpe | 3.563315 |
| sortino | 4.092358 |
| calmar | 7.156652 |
| max_drawdown | -0.149779 |
| profit_factor | 1.165149 |
| hit_rate | 0.492469 |
| trade_count | 321 |
| gross_pnl | 5.588923 |
| net_pnl | 5.179175 |
| total_cost | 0.064200 |
| cost_to_gross_pnl | 0.073314 |
| average_r | 0.761942 |
| median_r | 0.549160 |

### Side Diagnostics
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| side | long | 178 | 1.130236 |  |  |  | 0.0 | 1.094414 | 2.147622 | 0.567416 |
| side | short | 143 | 0.877253 |  |  |  | 0.0 | 0.848475 | 1.909011 | 0.608392 |

### Year Diagnostics
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| year | 2022 | 109 | 0.919556 |  |  |  | 0.0 | 0.897579 | 2.067529 | 0.614679 |
| year | 2023 | 135 | 0.390988 |  |  |  | 0.0 | 0.363910 | 1.534929 | 0.570370 |
| year | 2024 | 77 | 0.696944 |  |  |  | 0.0 | 0.681401 | 2.862033 | 0.571429 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 5.179175 |
| cost_x1.annualized_return | 1.071916 |
| cost_x1.annualized_vol | 0.300820 |
| cost_x1.sharpe | 3.563315 |
| cost_x1.sortino | 4.092358 |
| cost_x1.calmar | 7.156652 |
| cost_x1.max_drawdown | -0.149779 |
| cost_x1.profit_factor | 1.165149 |
| cost_x1.hit_rate | 0.492469 |
| cost_x1.bar_return_profit_factor | 1.165149 |
| cost_x1.conventional_sharpe | 2.571165 |
| cost_x1.return_over_vol_sharpe | 3.563315 |
| cost_x1.profit_factor_scope | bar_returns |
| cost_x1.metric_scope | bar_returns |
| cost_x1.annualization_mode | fixed_periods |
| cost_x1.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x1.gross_pnl | 5.588923 |
| cost_x1.net_pnl | 5.179175 |
| cost_x1.total_cost | 0.064200 |
| cost_x1.cost_drag | 0.409748 |
| cost_x1.cost_to_gross_pnl | 0.073314 |
| cost_x1.gross_return_sum | 1.997844 |
| cost_x1.net_return_sum | 1.933644 |
| cost_x1.cost_return_sum | 0.064200 |
| cost_x1.avg_turnover | 0.014658 |
| cost_x1.total_turnover | 642.000000 |
| cost_x1.evaluation_scope | strict_oos_only |
| cost_x1.evaluation_start | 2022-03-14T15:00:00 |
| cost_x1.evaluation_end | 2024-09-17T10:30:00 |
| cost_x1.evaluation_rows | 43800 |
| cost_x2.cumulative_return | 4.794870 |
| cost_x2.annualized_return | 1.019377 |
| cost_x2.annualized_vol | 0.300838 |
| cost_x2.sharpe | 3.388458 |
| cost_x2.sortino | 3.954034 |
| cost_x2.calmar | 6.721900 |
| cost_x2.max_drawdown | -0.151650 |
| cost_x2.profit_factor | 1.159003 |
| cost_x2.hit_rate | 0.491224 |
| cost_x2.bar_return_profit_factor | 1.159003 |
| cost_x2.conventional_sharpe | 2.485648 |
| cost_x2.return_over_vol_sharpe | 3.388458 |
| cost_x2.profit_factor_scope | bar_returns |
| cost_x2.metric_scope | bar_returns |
| cost_x2.annualization_mode | fixed_periods |
| cost_x2.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x2.gross_pnl | 5.588923 |
| cost_x2.net_pnl | 4.794870 |
| cost_x2.total_cost | 0.128400 |
| cost_x2.cost_drag | 0.794052 |
| cost_x2.cost_to_gross_pnl | 0.142076 |
| cost_x2.gross_return_sum | 1.997844 |
| cost_x2.net_return_sum | 1.869444 |
| cost_x2.cost_return_sum | 0.128400 |
| cost_x2.avg_turnover | 0.014658 |
| cost_x2.total_turnover | 642.000000 |
| cost_x2.evaluation_scope | strict_oos_only |
| cost_x2.evaluation_start | 2022-03-14T15:00:00 |
| cost_x2.evaluation_end | 2024-09-17T10:30:00 |
| cost_x2.evaluation_rows | 43800 |
| cost_x3.cumulative_return | 4.434431 |
| cost_x3.annualized_return | 0.968166 |
| cost_x3.annualized_vol | 0.300865 |
| cost_x3.sharpe | 3.217941 |
| cost_x3.sortino | 3.815670 |
| cost_x3.calmar | 6.306550 |
| cost_x3.max_drawdown | -0.153517 |
| cost_x3.profit_factor | 1.152898 |
| cost_x3.hit_rate | 0.490850 |
| cost_x3.bar_return_profit_factor | 1.152898 |
| cost_x3.conventional_sharpe | 2.400072 |
| cost_x3.return_over_vol_sharpe | 3.217941 |
| cost_x3.profit_factor_scope | bar_returns |
| cost_x3.metric_scope | bar_returns |
| cost_x3.annualization_mode | fixed_periods |
| cost_x3.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x3.gross_pnl | 5.588923 |
| cost_x3.net_pnl | 4.434431 |
| cost_x3.total_cost | 0.192600 |
| cost_x3.cost_drag | 1.154491 |
| cost_x3.cost_to_gross_pnl | 0.206568 |
| cost_x3.gross_return_sum | 1.997844 |
| cost_x3.net_return_sum | 1.805244 |
| cost_x3.cost_return_sum | 0.192600 |
| cost_x3.avg_turnover | 0.014658 |
| cost_x3.total_turnover | 642.000000 |
| cost_x3.evaluation_scope | strict_oos_only |
| cost_x3.evaluation_start | 2022-03-14T15:00:00 |
| cost_x3.evaluation_end | 2024-09-17T10:30:00 |
| cost_x3.evaluation_rows | 43800 |
| cost_x5.cumulative_return | 3.779323 |
| cost_x5.annualized_return | 0.869591 |
| cost_x5.annualized_vol | 0.300944 |
| cost_x5.sharpe | 2.889541 |
| cost_x5.sortino | 3.538911 |
| cost_x5.calmar | 5.226549 |
| cost_x5.max_drawdown | -0.166380 |
| cost_x5.profit_factor | 1.140831 |
| cost_x5.hit_rate | 0.490103 |
| cost_x5.bar_return_profit_factor | 1.140831 |
| cost_x5.conventional_sharpe | 2.228777 |
| cost_x5.return_over_vol_sharpe | 2.889541 |
| cost_x5.profit_factor_scope | bar_returns |
| cost_x5.metric_scope | bar_returns |
| cost_x5.annualization_mode | fixed_periods |
| cost_x5.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x5.gross_pnl | 5.588923 |
| cost_x5.net_pnl | 3.779323 |
| cost_x5.total_cost | 0.321000 |
| cost_x5.cost_drag | 1.809600 |
| cost_x5.cost_to_gross_pnl | 0.323783 |
| cost_x5.gross_return_sum | 1.997844 |
| cost_x5.net_return_sum | 1.676844 |
| cost_x5.cost_return_sum | 0.321000 |
| cost_x5.avg_turnover | 0.014658 |
| cost_x5.total_turnover | 642.000000 |
| cost_x5.evaluation_scope | strict_oos_only |
| cost_x5.evaluation_start | 2022-03-14T15:00:00 |
| cost_x5.evaluation_end | 2024-09-17T10:30:00 |
| cost_x5.evaluation_rows | 43800 |

### Slippage Stress
| Metric | Value |
| --- | --- |
| slippage_x1.cumulative_return | 5.179175 |
| slippage_x1.annualized_return | 1.071916 |
| slippage_x1.annualized_vol | 0.300820 |
| slippage_x1.sharpe | 3.563315 |
| slippage_x1.sortino | 4.092358 |
| slippage_x1.calmar | 7.156652 |
| slippage_x1.max_drawdown | -0.149779 |
| slippage_x1.profit_factor | 1.165149 |
| slippage_x1.hit_rate | 0.492469 |
| slippage_x1.bar_return_profit_factor | 1.165149 |
| slippage_x1.conventional_sharpe | 2.571165 |
| slippage_x1.return_over_vol_sharpe | 3.563315 |
| slippage_x1.profit_factor_scope | bar_returns |
| slippage_x1.metric_scope | bar_returns |
| slippage_x1.annualization_mode | fixed_periods |
| slippage_x1.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x1.gross_pnl | 5.179175 |
| slippage_x1.net_pnl | 5.179175 |
| slippage_x1.total_cost | 0.0 |
| slippage_x1.cost_drag | 0.0 |
| slippage_x1.cost_to_gross_pnl | 0.0 |
| slippage_x1.gross_return_sum | 1.933644 |
| slippage_x1.net_return_sum | 1.933644 |
| slippage_x1.cost_return_sum | 0.0 |
| slippage_x1.avg_turnover | 0.0 |
| slippage_x1.total_turnover | 0.0 |
| slippage_x1.evaluation_scope | strict_oos_only |
| slippage_x1.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x1.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x1.evaluation_rows | 43800 |
| slippage_x2.cumulative_return | 5.179175 |
| slippage_x2.annualized_return | 1.071916 |
| slippage_x2.annualized_vol | 0.300820 |
| slippage_x2.sharpe | 3.563315 |
| slippage_x2.sortino | 4.092358 |
| slippage_x2.calmar | 7.156652 |
| slippage_x2.max_drawdown | -0.149779 |
| slippage_x2.profit_factor | 1.165149 |
| slippage_x2.hit_rate | 0.492469 |
| slippage_x2.bar_return_profit_factor | 1.165149 |
| slippage_x2.conventional_sharpe | 2.571165 |
| slippage_x2.return_over_vol_sharpe | 3.563315 |
| slippage_x2.profit_factor_scope | bar_returns |
| slippage_x2.metric_scope | bar_returns |
| slippage_x2.annualization_mode | fixed_periods |
| slippage_x2.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x2.gross_pnl | 5.179175 |
| slippage_x2.net_pnl | 5.179175 |
| slippage_x2.total_cost | 0.0 |
| slippage_x2.cost_drag | 0.0 |
| slippage_x2.cost_to_gross_pnl | 0.0 |
| slippage_x2.gross_return_sum | 1.933644 |
| slippage_x2.net_return_sum | 1.933644 |
| slippage_x2.cost_return_sum | 0.0 |
| slippage_x2.avg_turnover | 0.0 |
| slippage_x2.total_turnover | 0.0 |
| slippage_x2.evaluation_scope | strict_oos_only |
| slippage_x2.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x2.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x2.evaluation_rows | 43800 |
| slippage_x3.cumulative_return | 5.179175 |
| slippage_x3.annualized_return | 1.071916 |
| slippage_x3.annualized_vol | 0.300820 |
| slippage_x3.sharpe | 3.563315 |
| slippage_x3.sortino | 4.092358 |
| slippage_x3.calmar | 7.156652 |
| slippage_x3.max_drawdown | -0.149779 |
| slippage_x3.profit_factor | 1.165149 |
| slippage_x3.hit_rate | 0.492469 |
| slippage_x3.bar_return_profit_factor | 1.165149 |
| slippage_x3.conventional_sharpe | 2.571165 |
| slippage_x3.return_over_vol_sharpe | 3.563315 |
| slippage_x3.profit_factor_scope | bar_returns |
| slippage_x3.metric_scope | bar_returns |
| slippage_x3.annualization_mode | fixed_periods |
| slippage_x3.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x3.gross_pnl | 5.179175 |
| slippage_x3.net_pnl | 5.179175 |
| slippage_x3.total_cost | 0.0 |
| slippage_x3.cost_drag | 0.0 |
| slippage_x3.cost_to_gross_pnl | 0.0 |
| slippage_x3.gross_return_sum | 1.933644 |
| slippage_x3.net_return_sum | 1.933644 |
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
| delay_1_bars.cumulative_return | 4.973662 |
| delay_1_bars.annualized_return | 1.044072 |
| delay_1_bars.annualized_vol | 0.299087 |
| delay_1_bars.sharpe | 3.490869 |
| delay_1_bars.sortino | 4.052948 |
| delay_1_bars.calmar | 7.099847 |
| delay_1_bars.max_drawdown | -0.147056 |
| delay_1_bars.profit_factor | 1.163210 |
| delay_1_bars.hit_rate | 0.492405 |
| delay_1_bars.bar_return_profit_factor | 1.163210 |
| delay_1_bars.conventional_sharpe | 2.539077 |
| delay_1_bars.return_over_vol_sharpe | 3.490869 |
| delay_1_bars.profit_factor_scope | bar_returns |
| delay_1_bars.metric_scope | bar_returns |
| delay_1_bars.annualization_mode | fixed_periods |
| delay_1_bars.sharpe_legacy_alias | return_over_vol_sharpe |
| delay_1_bars.gross_pnl | 4.973662 |
| delay_1_bars.net_pnl | 4.973662 |
| delay_1_bars.total_cost | 0.0 |
| delay_1_bars.cost_drag | 0.0 |
| delay_1_bars.cost_to_gross_pnl | 0.0 |
| delay_1_bars.gross_return_sum | 1.898510 |
| delay_1_bars.net_return_sum | 1.898510 |
| delay_1_bars.cost_return_sum | 0.0 |
| delay_1_bars.avg_turnover | 0.0 |
| delay_1_bars.total_turnover | 0.0 |
| delay_1_bars.evaluation_scope | strict_oos_only |
| delay_1_bars.evaluation_start | 2022-03-14T15:00:00 |
| delay_1_bars.evaluation_end | 2024-09-17T10:30:00 |
| delay_1_bars.evaluation_rows | 43800 |
| delay_2_bars.cumulative_return | 4.387070 |
| delay_2_bars.annualized_return | 0.961287 |
| delay_2_bars.annualized_vol | 0.295449 |
| delay_2_bars.sharpe | 3.253649 |
| delay_2_bars.sortino | 3.858942 |
| delay_2_bars.calmar | 6.243330 |
| delay_2_bars.max_drawdown | -0.153970 |
| delay_2_bars.profit_factor | 1.155150 |
| delay_2_bars.hit_rate | 0.491226 |
| delay_2_bars.bar_return_profit_factor | 1.155150 |
| delay_2_bars.conventional_sharpe | 2.426796 |
| delay_2_bars.return_over_vol_sharpe | 3.253649 |
| delay_2_bars.profit_factor_scope | bar_returns |
| delay_2_bars.metric_scope | bar_returns |
| delay_2_bars.annualization_mode | fixed_periods |
| delay_2_bars.sharpe_legacy_alias | return_over_vol_sharpe |
| delay_2_bars.gross_pnl | 4.387070 |
| delay_2_bars.net_pnl | 4.387070 |
| delay_2_bars.total_cost | 0.0 |
| delay_2_bars.cost_drag | 0.0 |
| delay_2_bars.cost_to_gross_pnl | 0.0 |
| delay_2_bars.gross_return_sum | 1.792484 |
| delay_2_bars.net_return_sum | 1.792484 |
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
| min_active_period_cumulative_return | 0.402843 |
| median_active_period_cumulative_return | 0.904165 |
| mean_active_period_cumulative_return | 0.873409 |
| mean_active_period_sharpe | 3.925629 |
| std_active_period_sharpe | 1.445502 |
| worst_active_period_max_drawdown | -0.149779 |

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
| oos_prediction.mean | -0.008525 |
| oos_prediction.std | 0.982910 |
| oos_prediction.min | -4.394032 |
| oos_prediction.max | 4.176103 |
| oos_prediction.median | 0.015470 |
| oos_prediction.q01 | -2.571181 |
| oos_prediction.q05 | -1.694337 |
| oos_prediction.q25 | -0.605182 |
| oos_prediction.q75 | 0.619243 |
| oos_prediction.q95 | 1.569277 |
| oos_prediction.q99 | 2.288592 |
| oos_prediction.skew | -0.185424 |
| oos_prediction.kurtosis | 0.493809 |
| oos_prediction.positive_rate | 0.506324 |
| oos_prediction.negative_rate | 0.493676 |
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
| 1 | atr_48 | 1.095e+03 | 0.101315 | 10 | feature_importances_ |
| 2 | vol_rolling_192 | 1.073e+03 | 0.099218 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 903.400000 | 0.083498 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 781.600000 | 0.072231 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 720.800000 | 0.066689 | 10 | feature_importances_ |
| 6 | bollinger_bandwidth_rank_192 | 604.900000 | 0.055943 | 10 | feature_importances_ |
| 7 | atr_over_price_48 | 583.900000 | 0.054004 | 10 | feature_importances_ |
| 8 | vol_rolling_48 | 552.100000 | 0.051036 | 10 | feature_importances_ |
| 9 | atr_pct_rank_192 | 469.900000 | 0.043485 | 10 | feature_importances_ |
| 10 | vol_rolling_24 | 427.900000 | 0.039591 | 10 | feature_importances_ |
| 11 | mama_minus_fama_over_atr | 387.900000 | 0.035896 | 10 | feature_importances_ |
| 12 | close_over_bb_upper_192 | 300.500000 | 0.027801 | 10 | feature_importances_ |
| 13 | ret_48 | 297.700000 | 0.027533 | 10 | feature_importances_ |
| 14 | close_over_bb_mid_192 | 286.100000 | 0.026437 | 10 | feature_importances_ |
| 15 | bollinger_percent_b | 250.700000 | 0.023158 | 10 | feature_importances_ |
| 16 | distance_from_ema96_atr | 192.900000 | 0.017843 | 10 | feature_importances_ |
| 17 | ret_24 | 174.000000 | 0.016082 | 10 | feature_importances_ |
| 18 | roofing_filter_over_atr | 168.700000 | 0.015602 | 10 | feature_importances_ |
| 19 | atr_pct | 139.800000 | 0.012932 | 10 | feature_importances_ |
| 20 | ret_16 | 122.900000 | 0.011369 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 5.588923 |
| net_pnl | 5.179175 |
| total_cost | 0.064200 |
| cost_drag | 0.409748 |
| cost_to_gross_pnl | 0.073314 |
| avg_turnover | 0.014658 |
| total_turnover | 642.000000 |
| mean_abs_signal | 0.043813 |
| signal_turnover | 0.052740 |
| flat_rate | 0.956187 |
| long_rate | 0.025822 |
| short_rate | 0.017991 |
| trade_rate | 0.176941 |
| executed_trade_count | 7750 |
| avg_signal_executed | 0.036774 |
| avg_pred_prob_executed | 0.509165 |
| avg_realized_r_executed |  |

## Diagnostics
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
| 0 |  | 0.032970 | 0.029050 | 0.003800 | 0.459826 | 0.008676 |  |  |  |  |
| 1 |  | 0.308975 | 0.301934 | 0.005400 | 4.622182 | 0.012329 |  |  |  |  |
| 2 |  | 0.376499 | 0.369633 | 0.005000 | 7.697860 | 0.011416 |  |  |  |  |
| 3 |  | 0.229828 | 0.224921 | 0.004000 | 6.451147 | 0.009132 |  |  |  |  |
| 4 |  | 0.040364 | 0.036210 | 0.004000 | 1.080053 | 0.009132 |  |  |  |  |
| 5 |  | 0.012678 | 0.008433 | 0.004200 | 0.322651 | 0.009589 |  |  |  |  |
| 6 |  | 0.007188 | 0.003569 | 0.003600 | 0.102526 | 0.008219 |  |  |  |  |
| 7 |  | 0.074817 | 0.071597 | 0.003000 | 1.697499 | 0.006849 |  |  |  |  |
| 8 |  | 0.089131 | 0.085651 | 0.003200 | 2.033245 | 0.007306 |  |  |  |  |
| 9 |  | 0.027583 | 0.024503 | 0.003000 | 0.597808 | 0.006849 |  |  |  |  |


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
- Drifted feature count: `8` / `49`
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
| unclassified | 36 | 3 | 0.083333 | 0.104073 | 1.187111 |
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
| 48 | close_ret_over_vol_64 |
| 49 | close_ret_robust_z_256 |

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
    - 64
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
        volatility_col: vol_rolling_64
        output_col: close_ret_over_vol_64
    robust_zscore:
      params:
        source_col: close_ret
        window: 256
        output_col: close_ret_robust_z_256
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
  - close_ret_over_vol_64
  - close_ret_robust_z_256
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
