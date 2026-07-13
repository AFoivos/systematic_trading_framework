# Experiment Report: ethusd_30m_trial0041_featadd_garman_klass48_v1

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/03_feature_additions/ethusd_30m_trial0041_featadd_garman_klass48_v1.yaml`
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
config_path: /workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/03_feature_additions/ethusd_30m_trial0041_featadd_garman_klass48_v1.yaml
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
- `feature[garman_klass_volatility]` -> `src.features.garman_klass_volatility.add_garman_klass_volatility(df: 'pd.DataFrame', open_col: 'str' = 'open', high_col: 'str' = 'high', low_col: 'str' = 'low', close_col: 'str' = 'close', window: 'int' = 20, output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'open_col': 'open', 'high_col': 'high', 'low_col': 'low', 'close_col': 'close', 'window': 48, 'output_col': 'garman_klass_vol_48'}

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
- step: garman_klass_volatility
  params:
    open_col: open
    high_col: high
    low_col: low
    close_col: close
    window: 48
    output_col: garman_klass_vol_48
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
- garman_klass_vol_48
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
  - garman_klass_vol_48
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
| cumulative_return | 2.416130 |
| annualized_return | 0.634609 |
| annualized_vol | 0.297320 |
| sharpe | 2.134431 |
| sortino | 3.366999 |
| calmar | 2.722758 |
| max_drawdown | -0.233076 |
| profit_factor | 1.115357 |
| hit_rate | 0.488315 |
| avg_turnover | 0.014155 |
| total_turnover | 620.000000 |
| gross_pnl | 1.400311 |
| net_pnl | 1.338311 |
| total_cost | 0.062000 |
| cost_drag | 0.062000 |
| cost_to_gross_pnl | 0.044276 |
| flat_rate | 0.958128 |
| long_rate | 0.024543 |
| short_rate | 0.017329 |
| trade_count | 310 |
| average_r | 0.421328 |
| median_r | 0.224261 |
| avg_max_favorable_r | 3.267571 |
| avg_max_adverse_r | -2.870234 |
| loser_was_positive_rate | 0.971831 |
| avg_giveback_r | 2.846243 |
| avg_capture_ratio | -4.663588 |
| robustness_walk_forward_positive_fold_ratio | 0.600000 |
| robustness_walk_forward_min_fold_cumulative_return | 0.0 |
| robustness_walk_forward_worst_fold_max_drawdown | -0.233076 |
| robustness_walk_forward_mean_fold_sharpe | 1.302148 |
| robustness_walk_forward_std_fold_sharpe | 1.505490 |
| robustness_cost_x1_cumulative_return | 2.416130 |
| robustness_cost_x1_sharpe | 1.476196 |
| robustness_cost_x1_max_drawdown | -0.233076 |
| robustness_cost_x1_profit_factor | 1.115357 |
| robustness_cost_x2_cumulative_return | 2.210746 |
| robustness_cost_x2_sharpe | 1.390916 |
| robustness_cost_x2_max_drawdown | -0.241771 |
| robustness_cost_x2_profit_factor | 1.109571 |
| robustness_cost_x3_cumulative_return | 2.017690 |
| robustness_cost_x3_sharpe | 1.306839 |
| robustness_cost_x3_max_drawdown | -0.250370 |
| robustness_cost_x3_profit_factor | 1.103828 |
| robustness_cost_x5_cumulative_return | 1.665655 |
| robustness_cost_x5_sharpe | 1.142246 |
| robustness_cost_x5_max_drawdown | -0.269494 |
| robustness_cost_x5_profit_factor | 1.092469 |
| robustness_delay_1_bars_cumulative_return | 2.358883 |
| robustness_delay_1_bars_sharpe | 1.162728 |
| robustness_delay_1_bars_max_drawdown | -0.175322 |
| robustness_delay_1_bars_profit_factor | 1.114925 |
| robustness_delay_2_bars_cumulative_return | 2.439746 |
| robustness_delay_2_bars_sharpe | 1.194822 |
| robustness_delay_2_bars_max_drawdown | -0.174555 |
| robustness_delay_2_bars_profit_factor | 1.117699 |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.041872 |
| signal_turnover | 0.049863 |
| long_rate | 0.024543 |
| short_rate | 0.017329 |
| flat_rate | 0.958128 |
| executed_trade_count | 7469 |
| trade_rate | 0.170525 |
| avg_signal_executed | 0.028652 |
| avg_pred_prob_executed | 0.512206 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.518790 |
| classification.brier | 0.283589 |
| classification.roc_auc | 0.526468 |
| classification.log_loss | 0.786074 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.175260 |
| regression.rmse | 2.639856 |
| regression.mse | 6.968837 |
| regression.r2 | -0.116090 |
| regression.correlation | 0.047618 |
| regression.directional_accuracy | 0.518699 |
| regression.mean_prediction | -0.020261 |
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
| prediction_distribution.mean | -0.020261 |
| prediction_distribution.std | 0.978325 |
| prediction_distribution.min | -4.676390 |
| prediction_distribution.max | 3.980745 |
| prediction_distribution.median | -0.002637 |
| prediction_distribution.q01 | -2.583332 |
| prediction_distribution.q05 | -1.695066 |
| prediction_distribution.q25 | -0.611146 |
| prediction_distribution.q75 | 0.597364 |
| prediction_distribution.q95 | 1.558513 |
| prediction_distribution.q99 | 2.279182 |
| prediction_distribution.skew | -0.178505 |
| prediction_distribution.kurtosis | 0.499299 |
| prediction_distribution.positive_rate | 0.498607 |
| prediction_distribution.negative_rate | 0.501393 |
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
| probability_distribution.mean | 0.495777 |
| probability_distribution.std | 0.207224 |
| probability_distribution.min | 0.009773 |
| probability_distribution.max | 0.985138 |
| probability_distribution.median | 0.499346 |
| probability_distribution.q01 | 0.066545 |
| probability_distribution.q05 | 0.143589 |
| probability_distribution.q25 | 0.343571 |
| probability_distribution.q75 | 0.654183 |
| probability_distribution.q95 | 0.827450 |
| probability_distribution.q99 | 0.906679 |
| probability_distribution.skew | -0.076546 |
| probability_distribution.kurtosis | -0.744639 |
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
| model_strategy | 2.416130 | 0.634609 | 0.297320 | 2.134431 | 3.366999 | 2.722758 | -0.233076 | 1.115357 | 0.488315 | 620.000000 | 0.044276 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | -0.089284 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000224 |
| random_sign_same_rate | 1.163502 | 0.361642 | 0.381837 | 0.947110 | 1.372658 | 0.998526 | -0.362176 | 1.043549 | 0.481618 | 1.264e+03 | 0.117007 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | -0.240522 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.789225 |
| simple_trend | -0.867002 | -0.553792 | 0.665797 | -0.831772 | -1.181822 | -0.608132 | -0.910644 | 0.978047 | 0.491683 | 1.545e+03 | 0.118038 |


## Threshold Grid
| Name | Upper | Lower | Net PnL | Sharpe | Max DD | Profit Factor | Cost/Gross | Turnover | Active Rows | Profitable Folds | Median Fold Return | Worst 3-Fold Avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sym_0.35 | 0.350000 | -0.350000 | 1.299502 | 0.758315 | -0.434442 | 1.028721 | 0.130288 | 1.756e+03 | 3.044e+04 | 7.000000 | 0.035406 | -0.112354 |
| sym_0.5 | 0.500000 | -0.500000 | 0.862910 | 0.558984 | -0.417283 | 1.025233 | 0.152683 | 1.697e+03 | 2.526e+04 | 5.000000 | 0.009432 | -0.181539 |
| sym_0.75 | 0.750000 | -0.750000 | 0.903587 | 0.622431 | -0.570620 | 1.028686 | 0.145021 | 1.564e+03 | 1.776e+04 | 7.000000 | 0.078261 | -0.257743 |
| sym_1 | 1.000000 | -1.000000 | 1.735089 | 1.149498 | -0.303696 | 1.046548 | 0.096711 | 1.326e+03 | 1.234e+04 | 8.000000 | 0.028964 | -0.036781 |
| sym_1.25 | 1.250000 | -1.250000 | 0.684153 | 0.586264 | -0.333940 | 1.032786 | 0.131585 | 1.086e+03 | 8.337e+03 | 6.000000 | 0.034571 | -0.130746 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.133642 |
| mean_fold_return | 0.145597 |
| fold_return_std | 0.203777 |
| worst_fold_return | -0.108898 |
| best_fold_return | 0.462912 |
| worst_3_fold_average_return | -0.082347 |
| profitable_fold_count | 7.000000 |
| profitable_fold_rate | 0.700000 |
| median_fold_sharpe | 2.789120 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.4, 'best_rank': 1, 'mean_importance': 1060.2, 'mean_importance_normalized': 0.09811962564856412, 'folds': [{'fold': 0, 'rank': 1, 'importance': 1100.0, 'importance_normalized': 0.10582010582010581}, {'fold': 1, 'rank': 1, 'importance': 1057.0, 'importance_normalized': 0.09759025020773705}, {'fold': 2, 'rank': 1, 'importance': 1086.0, 'importance_normalized': 0.09925059404130872}, {'fold': 3, 'rank': 1, 'importance': 1066.0, 'importance_normalized': 0.09822168985533954}, {'fold': 4, 'rank': 1, 'importance': 1064.0, 'importance_normalized': 0.09840007398501803}, {'fold': 5, 'rank': 1, 'importance': 1051.0, 'importance_normalized': 0.09817842129845866}, {'fold': 6, 'rank': 2, 'importance': 1037.0, 'importance_normalized': 0.0954265206588755}, {'fold': 7, 'rank': 2, 'importance': 1055.0, 'importance_normalized': 0.09691346683814073}, {'fold': 8, 'rank': 2, 'importance': 1042.0, 'importance_normalized': 0.09538630538264373}, {'fold': 9, 'rank': 2, 'importance': 1044.0, 'importance_normalized': 0.09600882839801361}], 'stability_rank': 1}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.7, 'best_rank': 1, 'mean_importance': 1017.7, 'mean_importance_normalized': 0.09413427748375128, 'folds': [{'fold': 0, 'rank': 2, 'importance': 952.0, 'importance_normalized': 0.09158249158249158}, {'fold': 1, 'rank': 2, 'importance': 943.0, 'importance_normalized': 0.08706490628750808}, {'fold': 2, 'rank': 2, 'importance': 1008.0, 'importance_normalized': 0.09212209833668433}, {'fold': 3, 'rank': 3, 'importance': 927.0, 'importance_normalized': 0.08541417119690409}, {'fold': 4, 'rank': 2, 'importance': 1021.0, 'importance_normalized': 0.0944233792656987}, {'fold': 5, 'rank': 2, 'importance': 1002.0, 'importance_normalized': 0.09360112097150865}, {'fold': 6, 'rank': 1, 'importance': 1063.0, 'importance_normalized': 0.09781908530413178}, {'fold': 7, 'rank': 1, 'importance': 1067.0, 'importance_normalized': 0.09801580011023332}, {'fold': 8, 'rank': 1, 'importance': 1107.0, 'importance_normalized': 0.10133650677407544}, {'fold': 9, 'rank': 1, 'importance': 1087.0, 'importance_normalized': 0.09996321500827662}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 2.9, 'best_rank': 2, 'mean_importance': 905.5, 'mean_importance_normalized': 0.08374372376596051, 'folds': [{'fold': 0, 'rank': 3, 'importance': 792.0, 'importance_normalized': 0.0761904761904762}, {'fold': 1, 'rank': 3, 'importance': 826.0, 'importance_normalized': 0.07626257963253624}, {'fold': 2, 'rank': 3, 'importance': 858.0, 'importance_normalized': 0.07841345275086821}, {'fold': 3, 'rank': 2, 'importance': 959.0, 'importance_normalized': 0.08836266470100433}, {'fold': 4, 'rank': 3, 'importance': 908.0, 'importance_normalized': 0.08397299546841765}, {'fold': 5, 'rank': 3, 'importance': 924.0, 'importance_normalized': 0.0863148061653433}, {'fold': 6, 'rank': 3, 'importance': 894.0, 'importance_normalized': 0.08226741510996595}, {'fold': 7, 'rank': 3, 'importance': 959.0, 'importance_normalized': 0.08809480066139996}, {'fold': 8, 'rank': 3, 'importance': 925.0, 'importance_normalized': 0.08467594287806664}, {'fold': 9, 'rank': 3, 'importance': 1010.0, 'importance_normalized': 0.09288210410152657}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.4, 'best_rank': 4, 'mean_importance': 758.0, 'mean_importance_normalized': 0.07009503163571153, 'folds': [{'fold': 0, 'rank': 6, 'importance': 641.0, 'importance_normalized': 0.061664261664261664}, {'fold': 1, 'rank': 6, 'importance': 709.0, 'importance_normalized': 0.0654602529775644}, {'fold': 2, 'rank': 4, 'importance': 734.0, 'importance_normalized': 0.06708097239992689}, {'fold': 3, 'rank': 4, 'importance': 775.0, 'importance_normalized': 0.0714088270524279}, {'fold': 4, 'rank': 4, 'importance': 790.0, 'importance_normalized': 0.07306020530842504}, {'fold': 5, 'rank': 4, 'importance': 777.0, 'importance_normalized': 0.07258290518449323}, {'fold': 6, 'rank': 4, 'importance': 819.0, 'importance_normalized': 0.07536578632557284}, {'fold': 7, 'rank': 4, 'importance': 780.0, 'importance_normalized': 0.07165166268601873}, {'fold': 8, 'rank': 4, 'importance': 775.0, 'importance_normalized': 0.07094470889783962}, {'fold': 9, 'rank': 4, 'importance': 780.0, 'importance_normalized': 0.07173073386058489}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 5.0, 'best_rank': 4, 'mean_importance': 716.5, 'mean_importance_normalized': 0.06631380661769277, 'folds': [{'fold': 0, 'rank': 4, 'importance': 723.0, 'importance_normalized': 0.06955266955266955}, {'fold': 1, 'rank': 4, 'importance': 771.0, 'importance_normalized': 0.071184562828917}, {'fold': 2, 'rank': 6, 'importance': 651.0, 'importance_normalized': 0.059495521842441966}, {'fold': 3, 'rank': 6, 'importance': 653.0, 'importance_normalized': 0.0601676955680457}, {'fold': 4, 'rank': 5, 'importance': 736.0, 'importance_normalized': 0.06806621659114029}, {'fold': 5, 'rank': 5, 'importance': 748.0, 'importance_normalized': 0.06987389070527791}, {'fold': 6, 'rank': 5, 'importance': 737.0, 'importance_normalized': 0.06782000552130303}, {'fold': 7, 'rank': 5, 'importance': 712.0, 'importance_normalized': 0.06540510747749403}, {'fold': 8, 'rank': 5, 'importance': 717.0, 'importance_normalized': 0.06563529842548517}, {'fold': 9, 'rank': 5, 'importance': 717.0, 'importance_normalized': 0.06593709766415302}], 'stability_rank': 5}, {'feature': 'garman_klass_vol_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 5.9, 'best_rank': 5, 'mean_importance': 633.6, 'mean_importance_normalized': 0.05863871784167388, 'folds': [{'fold': 0, 'rank': 5, 'importance': 670.0, 'importance_normalized': 0.06445406445406446}, {'fold': 1, 'rank': 5, 'importance': 716.0, 'importance_normalized': 0.06610654602529775}, {'fold': 2, 'rank': 5, 'importance': 690.0, 'importance_normalized': 0.06305976969475416}, {'fold': 3, 'rank': 5, 'importance': 686.0, 'importance_normalized': 0.06320832949414908}, {'fold': 4, 'rank': 6, 'importance': 648.0, 'importance_normalized': 0.059927864607416996}, {'fold': 5, 'rank': 7, 'importance': 564.0, 'importance_normalized': 0.052685660906118634}, {'fold': 6, 'rank': 7, 'importance': 584.0, 'importance_normalized': 0.05374068280114107}, {'fold': 7, 'rank': 6, 'importance': 609.0, 'importance_normalized': 0.055943413558699244}, {'fold': 8, 'rank': 7, 'importance': 578.0, 'importance_normalized': 0.05291102160380813}, {'fold': 9, 'rank': 6, 'importance': 591.0, 'importance_normalized': 0.054349825271289315}], 'stability_rank': 6}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.8, 'best_rank': 6, 'mean_importance': 578.6, 'mean_importance_normalized': 0.05352136845644086, 'folds': [{'fold': 0, 'rank': 7, 'importance': 543.0, 'importance_normalized': 0.052236652236652234}, {'fold': 1, 'rank': 7, 'importance': 581.0, 'importance_normalized': 0.05364232296186871}, {'fold': 2, 'rank': 7, 'importance': 584.0, 'importance_normalized': 0.05337232681411076}, {'fold': 3, 'rank': 8, 'importance': 552.0, 'importance_normalized': 0.05086151294572929}, {'fold': 4, 'rank': 7, 'importance': 562.0, 'importance_normalized': 0.051974475168778324}, {'fold': 5, 'rank': 6, 'importance': 575.0, 'importance_normalized': 0.05371321812237272}, {'fold': 6, 'rank': 6, 'importance': 591.0, 'importance_normalized': 0.05438483482101776}, {'fold': 7, 'rank': 7, 'importance': 605.0, 'importance_normalized': 0.05557596913466838}, {'fold': 8, 'rank': 6, 'importance': 615.0, 'importance_normalized': 0.056298059318930796}, {'fold': 9, 'rank': 7, 'importance': 578.0, 'importance_normalized': 0.053154313040279566}], 'stability_rank': 7}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 8.5, 'best_rank': 7, 'mean_importance': 502.7, 'mean_importance_normalized': 0.04648163994929318, 'folds': [{'fold': 0, 'rank': 11, 'importance': 425.0, 'importance_normalized': 0.040885040885040885}, {'fold': 1, 'rank': 8, 'importance': 518.0, 'importance_normalized': 0.047825685532268486}, {'fold': 2, 'rank': 8, 'importance': 519.0, 'importance_normalized': 0.04743191372692378}, {'fold': 3, 'rank': 7, 'importance': 562.0, 'importance_normalized': 0.05178291716576062}, {'fold': 4, 'rank': 9, 'importance': 473.0, 'importance_normalized': 0.04374364191251272}, {'fold': 5, 'rank': 8, 'importance': 488.0, 'importance_normalized': 0.04558617468472676}, {'fold': 6, 'rank': 9, 'importance': 499.0, 'importance_normalized': 0.04591883684549554}, {'fold': 7, 'rank': 8, 'importance': 519.0, 'importance_normalized': 0.04767591401800478}, {'fold': 8, 'rank': 9, 'importance': 483.0, 'importance_normalized': 0.04421457341633101}, {'fold': 9, 'rank': 8, 'importance': 541.0, 'importance_normalized': 0.04975170130586721}], 'stability_rank': 8}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 8.8, 'best_rank': 8, 'mean_importance': 489.5, 'mean_importance_normalized': 0.045270425575390516, 'folds': [{'fold': 0, 'rank': 8, 'importance': 466.0, 'importance_normalized': 0.04482924482924483}, {'fold': 1, 'rank': 10, 'importance': 447.0, 'importance_normalized': 0.041270427476687285}, {'fold': 2, 'rank': 9, 'importance': 492.0, 'importance_normalized': 0.04496435752147688}, {'fold': 3, 'rank': 9, 'importance': 516.0, 'importance_normalized': 0.047544457753616515}, {'fold': 4, 'rank': 8, 'importance': 482.0, 'importance_normalized': 0.044575973365393505}, {'fold': 5, 'rank': 10, 'importance': 402.0, 'importance_normalized': 0.03755254553946754}, {'fold': 6, 'rank': 8, 'importance': 532.0, 'importance_normalized': 0.04895555351062851}, {'fold': 7, 'rank': 9, 'importance': 509.0, 'importance_normalized': 0.04675730295792761}, {'fold': 8, 'rank': 8, 'importance': 509.0, 'importance_normalized': 0.046594653972903695}, {'fold': 9, 'rank': 9, 'importance': 540.0, 'importance_normalized': 0.04965973882655876}], 'stability_rank': 9}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 9.7, 'best_rank': 9, 'mean_importance': 444.6, 'mean_importance_normalized': 0.041140187274691174, 'folds': [{'fold': 0, 'rank': 9, 'importance': 449.0, 'importance_normalized': 0.043193843193843194}, {'fold': 1, 'rank': 9, 'importance': 475.0, 'importance_normalized': 0.04385559966762072}, {'fold': 2, 'rank': 10, 'importance': 455.0, 'importance_normalized': 0.041582891610308904}, {'fold': 3, 'rank': 10, 'importance': 453.0, 'importance_normalized': 0.041739611167419144}, {'fold': 4, 'rank': 10, 'importance': 470.0, 'importance_normalized': 0.043466198094885784}, {'fold': 5, 'rank': 9, 'importance': 413.0, 'importance_normalized': 0.03858010275572162}, {'fold': 6, 'rank': 10, 'importance': 418.0, 'importance_normalized': 0.03846507775835097}, {'fold': 7, 'rank': 10, 'importance': 424.0, 'importance_normalized': 0.03894910894727172}, {'fold': 8, 'rank': 10, 'importance': 440.0, 'importance_normalized': 0.040278286341999266}, {'fold': 9, 'rank': 10, 'importance': 449.0, 'importance_normalized': 0.041291153209490526}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.435929 | 1.024177 | -0.286099 | 1.048277 | 0.103504 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.454681 | 1.758761 | -0.120040 | 1.148940 | 0.038603 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 2.127774 | 4.031931 | -0.239086 | 1.134307 | 0.038007 |
| ema_trend_48_192 | negative | 2.183e+04 | 2.159987 | 4.523274 | -0.119859 | 1.197562 | 0.026024 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.352578 | 0.973966 | -0.293940 | 1.056910 | 0.086674 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 0.953080 | 1.621653 | -0.400229 | 1.067457 | 0.052415 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 310 |
| average_r | 0.421328 |
| median_r | 0.224261 |
| avg_max_favorable_r | 3.267571 |
| avg_max_adverse_r | -2.870234 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.971831 |
| avg_giveback_r | 2.846243 |
| avg_capture_ratio | -4.663588 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.971831 |
| avg_mfe_r_of_losers | 1.251600 |
| median_mfe_r_of_losers | 0.918680 |
| avg_mfe_r_before_loss | 1.251600 |
| median_mfe_r_before_loss | 0.918680 |
| loser_reached_0_5r_rate | 0.725352 |
| loser_reached_1r_rate | 0.464789 |
| loser_reached_1_5r_rate | 0.246479 |
| loser_reached_2r_rate | 0.190141 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -4.663588 |
| median_capture_ratio | 0.151316 |
| avg_giveback_r | 2.846243 |
| median_giveback_r | 2.115973 |
| avg_giveback_r_winners | 1.899391 |
| avg_giveback_r_losers | 3.966463 |
| median_giveback_r_winners | 1.504688 |
| median_giveback_r_losers | 3.248841 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.994048 |
| winner_had_mae_below_minus_0_25r_rate | 0.857143 |
| winner_had_mae_below_minus_0_5r_rate | 0.726190 |
| winner_had_mae_below_minus_1r_rate | 0.476190 |
| avg_mae_r_of_winners | -1.252305 |
| median_mae_r_of_winners | -0.933739 |
| p90_abs_mae_r_of_winners | 2.908927 |
| avg_mae_r | -2.870234 |
| median_mae_r | -2.053328 |
| q10_mae_r | -6.517333 |
| q25_mae_r | -3.934837 |
| q75_mae_r | -0.855050 |
| q90_mae_r | -0.307111 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.541935 |
| prob_final_loss | 0.458065 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 0.988764 |
| prob_mfe_ge_0_5r | 0.874194 |
| prob_final_loss_given_mfe_ge_0_5r | 0.380074 |
| prob_mfe_ge_1r | 0.748387 |
| prob_final_loss_given_mfe_ge_1r | 0.284483 |
| prob_mfe_ge_1_5r | 0.616129 |
| prob_final_loss_given_mfe_ge_1_5r | 0.183246 |
| prob_mfe_ge_2r | 0.535484 |
| prob_final_loss_given_mfe_ge_2r | 0.162651 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 11.703226 |
| median_time_to_mfe | 11.000000 |
| avg_time_to_mae | 9.661290 |
| median_time_to_mae | 8.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.083871 |
| prob_mfe_ge_0_5r_within_2_bars | 0.129032 |
| prob_mfe_ge_1r_within_4_bars | 0.125806 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.421328 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.541935 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 310 |
| counterfactual.baseline.avg_r | 0.421328 |
| counterfactual.baseline.median_r | 0.224261 |
| counterfactual.baseline.win_rate | 0.541935 |
| counterfactual.baseline.profit_factor | 1.338802 |
| counterfactual.breakeven_after_0_5r.trade_count | 310 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.087578 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.012903 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.307212 |
| counterfactual.breakeven_after_1_0r.trade_count | 310 |
| counterfactual.breakeven_after_1_0r.avg_r | 0.043232 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.119355 |
| counterfactual.breakeven_after_1_0r.profit_factor | 1.108555 |
| counterfactual.exit_at_first_0_5r.trade_count | 310 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.349392 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.951613 |
| counterfactual.exit_at_first_0_5r.profit_factor | 3.763872 |
| counterfactual.exit_at_first_1_0r.trade_count | 310 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.448824 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.848387 |
| counterfactual.exit_at_first_1_0r.profit_factor | 2.126975 |
| counterfactual.partial_50pct_at_1r.trade_count | 310 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.435076 |
| counterfactual.partial_50pct_at_1r.median_r | 0.606950 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.654839 |
| counterfactual.partial_50pct_at_1r.profit_factor | 1.624367 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 310 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.410282 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.180763 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.532258 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.332261 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 310 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.632118 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.784692 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.848387 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 2.587217 |
| counterfactual.best_policy_by_avg_r | trail_0_5r_after_1_0r |
| counterfactual.best_policy_by_profit_factor | exit_at_first_0_5r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 305 | 0.420543 | 0.216274 | 0.540984 | 3.274275 | -2.876991 | 2.853731 | 24.095082 | 1.336353 | 0.986885 | 0.875410 | 0.747541 |
| reversal | 5 | 0.469207 | 0.595414 | 0.600000 | 2.858669 | -2.458031 | 2.389462 | 24.000000 | 1.562885 | 1.000000 | 0.800000 | 0.800000 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 0 |
| gross_pnl | 1.400311 |
| net_pnl | 1.338311 |
| total_cost | 0.062000 |
| cost_to_gross_pnl | 0.044276 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1834 |
| actual_trade_count | 0 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 2.416130 |
| sharpe | 2.134431 |
| sortino | 3.366999 |
| calmar | 2.722758 |
| max_drawdown | -0.233076 |
| profit_factor | 1.115357 |
| hit_rate | 0.488315 |
| gross_pnl | 1.400311 |
| net_pnl | 1.338311 |
| total_cost | 0.062000 |
| cost_to_gross_pnl | 0.044276 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 2.416130 |
| cost_x1.annualized_return | 0.337758 |
| cost_x1.annualized_vol | 0.228803 |
| cost_x1.sharpe | 1.476196 |
| cost_x1.max_drawdown | -0.233076 |
| cost_x1.profit_factor | 1.115357 |
| cost_x1.hit_rate | 0.488315 |
| cost_x2.cumulative_return | 2.210746 |
| cost_x2.annualized_return | 0.318254 |
| cost_x2.annualized_vol | 0.228809 |
| cost_x2.sharpe | 1.390916 |
| cost_x2.max_drawdown | -0.241771 |
| cost_x2.profit_factor | 1.109571 |
| cost_x2.hit_rate | 0.487928 |
| cost_x3.cumulative_return | 2.017690 |
| cost_x3.annualized_return | 0.299032 |
| cost_x3.annualized_vol | 0.228821 |
| cost_x3.sharpe | 1.306839 |
| cost_x3.max_drawdown | -0.250370 |
| cost_x3.profit_factor | 1.103828 |
| cost_x3.hit_rate | 0.487282 |
| cost_x5.cumulative_return | 1.665655 |
| cost_x5.annualized_return | 0.261420 |
| cost_x5.annualized_vol | 0.228865 |
| cost_x5.sharpe | 1.142246 |
| cost_x5.max_drawdown | -0.269494 |
| cost_x5.profit_factor | 1.092469 |
| cost_x5.hit_rate | 0.486378 |

### Entry Delay
| Metric | Value |
| --- | --- |
| delay_1_bars.cumulative_return | 2.358883 |
| delay_1_bars.annualized_return | 0.214992 |
| delay_1_bars.annualized_vol | 0.184903 |
| delay_1_bars.sharpe | 1.162728 |
| delay_1_bars.max_drawdown | -0.175322 |
| delay_1_bars.profit_factor | 1.114925 |
| delay_1_bars.hit_rate | 0.488702 |
| delay_2_bars.cumulative_return | 2.439746 |
| delay_2_bars.annualized_return | 0.219647 |
| delay_2_bars.annualized_vol | 0.183832 |
| delay_2_bars.sharpe | 1.194822 |
| delay_2_bars.max_drawdown | -0.174555 |
| delay_2_bars.profit_factor | 1.117699 |
| delay_2_bars.hit_rate | 0.487282 |

### Walk Forward
| Metric | Value |
| --- | --- |
| fold_count | 5 |
| positive_fold_count | 3 |
| positive_fold_ratio | 0.600000 |
| min_fold_cumulative_return | 0.0 |
| median_fold_cumulative_return | 0.053047 |
| mean_fold_cumulative_return | 0.331102 |
| mean_fold_sharpe | 1.302148 |
| std_fold_sharpe | 1.505490 |
| worst_fold_max_drawdown | -0.233076 |

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
| oos_prediction.mean | -0.020261 |
| oos_prediction.std | 0.978325 |
| oos_prediction.min | -4.676390 |
| oos_prediction.max | 3.980745 |
| oos_prediction.median | -0.002637 |
| oos_prediction.q01 | -2.583332 |
| oos_prediction.q05 | -1.695066 |
| oos_prediction.q25 | -0.611146 |
| oos_prediction.q75 | 0.597364 |
| oos_prediction.q95 | 1.558513 |
| oos_prediction.q99 | 2.279182 |
| oos_prediction.skew | -0.178505 |
| oos_prediction.kurtosis | 0.499299 |
| oos_prediction.positive_rate | 0.498607 |
| oos_prediction.negative_rate | 0.501393 |
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
| 1 | atr_48 | 1.060e+03 | 0.098120 | 10 | feature_importances_ |
| 2 | vol_rolling_192 | 1.018e+03 | 0.094134 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 905.500000 | 0.083744 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 758.000000 | 0.070095 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 716.500000 | 0.066314 | 10 | feature_importances_ |
| 6 | garman_klass_vol_48 | 633.600000 | 0.058639 | 10 | feature_importances_ |
| 7 | bollinger_bandwidth_rank_192 | 578.600000 | 0.053521 | 10 | feature_importances_ |
| 8 | atr_over_price_48 | 502.700000 | 0.046482 | 10 | feature_importances_ |
| 9 | vol_rolling_48 | 489.500000 | 0.045270 | 10 | feature_importances_ |
| 10 | atr_pct_rank_192 | 444.600000 | 0.041140 | 10 | feature_importances_ |
| 11 | vol_rolling_24 | 388.300000 | 0.035948 | 10 | feature_importances_ |
| 12 | mama_minus_fama_over_atr | 386.800000 | 0.035795 | 10 | feature_importances_ |
| 13 | close_over_bb_upper_192 | 298.200000 | 0.027604 | 10 | feature_importances_ |
| 14 | close_over_bb_mid_192 | 282.900000 | 0.026163 | 10 | feature_importances_ |
| 15 | ret_48 | 276.200000 | 0.025554 | 10 | feature_importances_ |
| 16 | bollinger_percent_b | 236.200000 | 0.021844 | 10 | feature_importances_ |
| 17 | distance_from_ema96_atr | 184.100000 | 0.017036 | 10 | feature_importances_ |
| 18 | ret_24 | 177.400000 | 0.016404 | 10 | feature_importances_ |
| 19 | roofing_filter_over_atr | 159.900000 | 0.014795 | 10 | feature_importances_ |
| 20 | atr_pct | 132.300000 | 0.012235 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 1.400311 |
| net_pnl | 1.338311 |
| total_cost | 0.062000 |
| cost_drag | 0.062000 |
| cost_to_gross_pnl | 0.044276 |
| avg_turnover | 0.014155 |
| total_turnover | 620.000000 |
| mean_abs_signal | 0.041872 |
| signal_turnover | 0.049863 |
| flat_rate | 0.958128 |
| long_rate | 0.024543 |
| short_rate | 0.017329 |
| trade_rate | 0.170525 |
| executed_trade_count | 7469 |
| avg_signal_executed | 0.028652 |
| avg_pred_prob_executed | 0.512206 |
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

### Diagnostics Shap Dependence Garman Klass Vol 48
![Diagnostics Shap Dependence Garman Klass Vol 48](artifacts/diagnostics/shap_dependence_garman_klass_vol_48.png)

### Diagnostics Shap Dependence Vol Rolling 192
![Diagnostics Shap Dependence Vol Rolling 192](artifacts/diagnostics/shap_dependence_vol_rolling_192.png)

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
| 0 |  | -0.016972 | -0.023972 | 0.007000 | -0.431092 | 0.015982 |  |  |  |  |
| 1 |  | 0.421247 | 0.413647 | 0.007600 | 6.919196 | 0.017352 |  |  |  |  |
| 2 |  | 0.282689 | 0.276989 | 0.005700 | 5.269073 | 0.013014 |  |  |  |  |
| 3 |  | 0.205104 | 0.197704 | 0.007400 | 4.345679 | 0.016895 |  |  |  |  |
| 4 |  | 0.048799 | 0.042599 | 0.006200 | 0.714299 | 0.014155 |  |  |  |  |
| 5 |  | -0.099030 | -0.105030 | 0.006000 | -2.201648 | 0.013699 |  |  |  |  |
| 6 |  | -0.103865 | -0.110665 | 0.006800 | -1.922269 | 0.015525 |  |  |  |  |
| 7 |  | 0.067516 | 0.062716 | 0.004800 | 1.232562 | 0.010959 |  |  |  |  |
| 8 |  | 0.244503 | 0.239303 | 0.005200 | 5.130642 | 0.011872 |  |  |  |  |
| 9 |  | 0.337370 | 0.332170 | 0.005200 | 8.939628 | 0.011872 |  |  |  |  |


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
- Drifted feature count: `9` / `47`
| Asset | Feature | PSI |
| --- | --- | --- |
| ETHUSD | atr_48 | 1.195042 |
| ETHUSD | atr_over_price_48 | 0.665754 |
| ETHUSD | atr_pct | 0.665754 |
| ETHUSD | vol_rolling_192 | 0.612124 |
| ETHUSD | vol_rolling_96 | 0.551451 |
| ETHUSD | garman_klass_vol_48 | 0.493013 |
| ETHUSD | vol_rolling_48 | 0.474270 |
| ETHUSD | vol_rolling_24 | 0.406533 |
| ETHUSD | bollinger_bandwidth | 0.358901 |


## Drift By Family
| Family | Feature Count | Drifted Count | Drifted Ratio | Mean Abs PSI | Max Abs PSI |
| --- | --- | --- | --- | --- | --- |
| unclassified | 34 | 4 | 0.117647 | 0.120941 | 1.195042 |
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
| 47 | garman_klass_vol_48 |

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
- step: garman_klass_volatility
  params:
    open_col: open
    high_col: high
    low_col: low
    close_col: close
    window: 48
    output_col: garman_klass_vol_48
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
  - garman_klass_vol_48
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
- `diagnostics_shap_dependence_garman_klass_vol_48`: `artifacts/diagnostics/shap_dependence_garman_klass_vol_48.png`
- `diagnostics_shap_dependence_vol_rolling_192`: `artifacts/diagnostics/shap_dependence_vol_rolling_192.png`
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
