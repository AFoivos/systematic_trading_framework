# Experiment Report: exit_01_rtrail_a075_d040

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/BEST/ethusd/trial0041_full_exit_model_research/01_exit_research/exit_01_rtrail_a075_d040.yaml`
- Model kind: `lightgbm_regressor`
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
config_path: /workspace/config/experiments/foundation_alpha/BEST/ethusd/trial0041_full_exit_model_research/01_exit_research/exit_01_rtrail_a075_d040.yaml
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
  final_refit: true
model_stages: []
resolved_reward_config:
  cost_per_turnover: 0.0001
  slippage_per_turnover: 0.0
  inventory_penalty: 0.0
  drawdown_penalty: 0.0
  switching_penalty: 0.0
resolved_execution_config:
  backtest_min_holding_bars: 0
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
  engine: manual_barrier
  returns_col: close_ret
  signal_col: signal_structured_tail
  periods_per_year: 17520
  returns_type: simple
  missing_return_policy: raise_if_exposed
  min_holding_bars: 0
  subset: full
  stop_mode: volatility_stop
  vol_col: atr_over_price_48
  open_col: open
  high_col: high
  low_col: low
  close_col: close
  take_profit_r: 5.0
  stop_loss_r: 2.0
  volatility_col: null
  entry_price_mode: null
  profit_barrier_r: null
  stop_barrier_r: null
  vertical_barrier_bars: null
  tie_break: null
  event_time_remap_policy: null
  annualization_mode: null
  max_cost_r: null
  risk_per_trade: 0.006
  max_holding_bars: 24
  asset_params: {}
  dynamic_exit: {}
  strategy_path: {}
  dynamic_exits:
    enabled: true
    r_trailing:
      enabled: true
      activation_r: 0.75
      distance_r: 0.4
      risk_distance_col: atr_48
      intrabar_policy: adverse_first
  partial_exits: {}
  allow_short: true
  oos_mode: strict
  execution_price: next_open
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
| cumulative_return | 0.074167 |
| annualized_return | 0.029032 |
| annualized_vol | 0.083898 |
| sharpe | 0.346034 |
| sortino | 0.565119 |
| calmar | 0.248926 |
| max_drawdown | -0.116627 |
| profit_factor | 1.026210 |
| hit_rate | 0.455340 |
| annualization_mode | fixed_periods |
| metric_scope | bar_returns |
| avg_turnover | 0.025045 |
| total_turnover | 1.097e+03 |
| gross_pnl | 0.198793 |
| net_pnl | 0.074167 |
| total_cost | 0.109695 |
| cost_drag | 0.124626 |
| cost_to_gross_pnl | 0.626914 |
| gross_return_sum | 0.190033 |
| net_return_sum | 0.080337 |
| cost_return_sum | 0.109695 |
| conventional_sharpe | 0.383023 |
| return_over_vol_sharpe | 0.346034 |
| sharpe_legacy_alias | return_over_vol_sharpe |
| bar_return_profit_factor | 1.026210 |
| profit_factor_scope | bar_returns |
| evaluation_scope | strict_oos_only |
| evaluation_start | 2022-03-14T15:00:00 |
| evaluation_end | 2024-09-17T10:30:00 |
| evaluation_rows | 43800 |
| trade_count | 944 |
| average_r | 0.011935 |
| median_r | 0.209840 |
| mtm_cumulative_return | 0.074167 |
| mtm_annualized_return | 0.029032 |
| mtm_annualized_vol | 0.083898 |
| mtm_sharpe | 0.346034 |
| mtm_conventional_sharpe | 0.383023 |
| mtm_return_over_vol_sharpe | 0.346034 |
| mtm_max_drawdown | -0.116627 |
| mtm_profit_factor | 1.026210 |
| mtm_bar_return_profit_factor | 1.026210 |
| flat_rate | 0.957260 |
| long_rate | 0.025274 |
| short_rate | 0.017466 |
| avg_max_favorable_r | 0.668700 |
| avg_max_adverse_r | -0.634117 |
| loser_was_positive_rate | 0.967949 |
| avg_giveback_r | 0.656765 |
| avg_capture_ratio | -6.976075 |
| robustness_walk_forward_total_calendar_periods | 7.000000 |
| robustness_walk_forward_active_oos_periods | 3.000000 |
| robustness_walk_forward_positive_active_periods | 2.000000 |
| robustness_walk_forward_positive_active_period_ratio | 0.666667 |
| robustness_walk_forward_min_active_period_cumulative_return | -0.034158 |
| robustness_walk_forward_worst_active_period_max_drawdown | -0.116627 |
| robustness_walk_forward_mean_active_period_sharpe | 0.395923 |
| robustness_walk_forward_std_active_period_sharpe | 0.709916 |
| robustness_cost_x1_cumulative_return | 0.074167 |
| robustness_cost_x1_sharpe | 0.346034 |
| robustness_cost_x1_max_drawdown | -0.116627 |
| robustness_cost_x1_profit_factor | 1.026210 |
| robustness_cost_x2_cumulative_return | -0.037511 |
| robustness_cost_x2_sharpe | -0.180057 |
| robustness_cost_x2_max_drawdown | -0.151651 |
| robustness_cost_x2_profit_factor | 0.990674 |
| robustness_cost_x3_cumulative_return | -0.137585 |
| robustness_cost_x3_sharpe | -0.678629 |
| robustness_cost_x3_max_drawdown | -0.211008 |
| robustness_cost_x3_profit_factor | 0.956977 |
| robustness_cost_x5_cumulative_return | -0.307616 |
| robustness_cost_x5_sharpe | -1.596274 |
| robustness_cost_x5_max_drawdown | -0.341566 |
| robustness_cost_x5_profit_factor | 0.894654 |
| robustness_delay_1_bars_cumulative_return | 0.132416 |
| robustness_delay_1_bars_sharpe | 0.606005 |
| robustness_delay_1_bars_max_drawdown | -0.093156 |
| robustness_delay_1_bars_profit_factor | 1.041623 |
| robustness_delay_2_bars_cumulative_return | 0.185578 |
| robustness_delay_2_bars_sharpe | 0.828972 |
| robustness_delay_2_bars_max_drawdown | -0.091286 |
| robustness_delay_2_bars_profit_factor | 1.056261 |
| completed_trade_count | 944 |
| win_rate | 0.669492 |
| trade_return_profit_factor | 1.051060 |
| trade_r_profit_factor | 1.042299 |
| trade_profit_factor | 1.051060 |
| entry_trade_cost | 0.054848 |
| exit_trade_cost | 0.054848 |
| holding_trade_cost | 0.0 |
| total_trade_cost | 0.109695 |
| position_transition_count | 1774 |
| turnover_event_count | 1831 |
| exposed_bar_count | 3870 |
| bar_return_profit_factor_scope | bar_returns |
| trade_return_profit_factor_scope | completed_trade_net_returns |
| trade_r_profit_factor_scope | completed_trade_net_r_multiples |
| trade_profit_factor_scope | completed_trade_net_returns |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.042740 |
| signal_turnover | 0.050685 |
| long_rate | 0.025274 |
| short_rate | 0.017466 |
| flat_rate | 0.957260 |
| executed_trade_count | 3870 |
| trade_rate | 0.088356 |
| avg_signal_executed | 0.043411 |
| avg_pred_prob_executed | 0.512798 |
| avg_realized_r_executed |  |


## Warnings
- Backtest dynamic exits are enabled. The current pre-model r_multiple target still labels manual candidates with barrier semantics and does not use final model_filtered_long_signal for signal-off exits.

## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.524041 |
| classification.brier | 0.254301 |
| classification.roc_auc | 0.528245 |
| classification.log_loss | 0.702496 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.172709 |
| regression.rmse | 2.639110 |
| regression.mse | 6.964902 |
| regression.r2 | -0.115459 |
| regression.correlation | 0.046619 |
| regression.directional_accuracy | 0.523927 |
| regression.mean_prediction | -0.004979 |
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
| prediction_distribution.mean | -0.004979 |
| prediction_distribution.std | 0.973485 |
| prediction_distribution.min | -4.438581 |
| prediction_distribution.max | 3.706707 |
| prediction_distribution.median | 0.009550 |
| prediction_distribution.q01 | -2.538497 |
| prediction_distribution.q05 | -1.661385 |
| prediction_distribution.q25 | -0.595408 |
| prediction_distribution.q75 | 0.616244 |
| prediction_distribution.q95 | 1.574688 |
| prediction_distribution.q99 | 2.291646 |
| prediction_distribution.skew | -0.160894 |
| prediction_distribution.kurtosis | 0.477781 |
| prediction_distribution.positive_rate | 0.504087 |
| prediction_distribution.negative_rate | 0.495913 |
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
| probability_distribution.mean | 0.499632 |
| probability_distribution.std | 0.091624 |
| probability_distribution.min | 0.150811 |
| probability_distribution.max | 0.808812 |
| probability_distribution.median | 0.500942 |
| probability_distribution.q01 | 0.270488 |
| probability_distribution.q05 | 0.342753 |
| probability_distribution.q25 | 0.441799 |
| probability_distribution.q75 | 0.560072 |
| probability_distribution.q95 | 0.649201 |
| probability_distribution.q99 | 0.710053 |
| probability_distribution.skew | -0.128314 |
| probability_distribution.kurtosis | 0.121521 |
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
| model_strategy | 0.033167 | 0.013137 | 0.131859 | 0.099629 | 0.249871 | 0.080048 | -0.164113 | 1.025092 | 0.321694 | 1.282e+03 | 0.809915 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | 0.375698 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000875 |
| random_sign_same_rate | -0.373254 | -0.170461 | 0.104311 | -1.634170 | -2.140361 | -0.432562 | -0.394074 | 0.765820 | 0.243158 | 2.204e+03 | 0.706802 |
| volatility_regime_only | -0.322220 | -0.144075 | 0.398479 | -0.361563 | -0.269184 | -0.265526 | -0.542604 | 0.992542 | 0.484224 | 1.496e+03 | 0.514430 |
| simple_trend | -0.425119 | -0.198634 | 0.428807 | -0.463224 | -0.431139 | -0.339275 | -0.585465 | 0.989878 | 0.473221 | 2.090e+03 | 0.459939 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.007212 |
| mean_fold_return | 0.004407 |
| fold_return_std | 0.050371 |
| worst_fold_return | -0.079881 |
| best_fold_return | 0.091537 |
| worst_3_fold_average_return | -0.052263 |
| profitable_fold_count | 6.000000 |
| profitable_fold_rate | 0.600000 |
| median_fold_sharpe | 0.362327 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.3, 'best_rank': 1, 'mean_importance': 1122.4, 'mean_importance_normalized': 0.10376119733625697, 'folds': [{'fold': 0, 'rank': 1, 'importance': 1154.0, 'importance_normalized': 0.11005149723440778}, {'fold': 1, 'rank': 1, 'importance': 1119.0, 'importance_normalized': 0.10409302325581396}, {'fold': 2, 'rank': 1, 'importance': 1149.0, 'importance_normalized': 0.10508505578928114}, {'fold': 3, 'rank': 1, 'importance': 1209.0, 'importance_normalized': 0.11110090056974821}, {'fold': 4, 'rank': 1, 'importance': 1130.0, 'importance_normalized': 0.10452317084451022}, {'fold': 5, 'rank': 1, 'importance': 1117.0, 'importance_normalized': 0.1034930047252849}, {'fold': 6, 'rank': 1, 'importance': 1088.0, 'importance_normalized': 0.10075006945087508}, {'fold': 7, 'rank': 2, 'importance': 1061.0, 'importance_normalized': 0.09685075308078503}, {'fold': 8, 'rank': 2, 'importance': 1083.0, 'importance_normalized': 0.09967786470317533}, {'fold': 9, 'rank': 2, 'importance': 1114.0, 'importance_normalized': 0.10198663370868809}], 'stability_rank': 1}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.7, 'best_rank': 1, 'mean_importance': 1076.5, 'mean_importance_normalized': 0.0994688500432584, 'folds': [{'fold': 0, 'rank': 2, 'importance': 1011.0, 'importance_normalized': 0.09641426664123594}, {'fold': 1, 'rank': 2, 'importance': 999.0, 'importance_normalized': 0.09293023255813954}, {'fold': 2, 'rank': 2, 'importance': 1059.0, 'importance_normalized': 0.09685385037497714}, {'fold': 3, 'rank': 2, 'importance': 977.0, 'importance_normalized': 0.08978129020400662}, {'fold': 4, 'rank': 2, 'importance': 1057.0, 'importance_normalized': 0.09777078901119231}, {'fold': 5, 'rank': 2, 'importance': 1083.0, 'importance_normalized': 0.10034281478736218}, {'fold': 6, 'rank': 2, 'importance': 1063.0, 'importance_normalized': 0.09843504028150754}, {'fold': 7, 'rank': 1, 'importance': 1139.0, 'importance_normalized': 0.10397078959379279}, {'fold': 8, 'rank': 1, 'importance': 1177.0, 'importance_normalized': 0.10832949838932351}, {'fold': 9, 'rank': 1, 'importance': 1200.0, 'importance_normalized': 0.10985992859104642}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 3.0, 'best_rank': 3, 'mean_importance': 939.8, 'mean_importance_normalized': 0.08683438986720693, 'folds': [{'fold': 0, 'rank': 3, 'importance': 837.0, 'importance_normalized': 0.0798207133320618}, {'fold': 1, 'rank': 3, 'importance': 902.0, 'importance_normalized': 0.08390697674418604}, {'fold': 2, 'rank': 3, 'importance': 927.0, 'importance_normalized': 0.08478141576733127}, {'fold': 3, 'rank': 3, 'importance': 956.0, 'importance_normalized': 0.08785149788641794}, {'fold': 4, 'rank': 3, 'importance': 960.0, 'importance_normalized': 0.08879844602719453}, {'fold': 5, 'rank': 3, 'importance': 910.0, 'importance_normalized': 0.08431390716204948}, {'fold': 6, 'rank': 3, 'importance': 994.0, 'importance_normalized': 0.09204555977405315}, {'fold': 7, 'rank': 3, 'importance': 898.0, 'importance_normalized': 0.08197170241898677}, {'fold': 8, 'rank': 3, 'importance': 966.0, 'importance_normalized': 0.08890934192360792}, {'fold': 9, 'rank': 3, 'importance': 1048.0, 'importance_normalized': 0.09594433763618054}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.1, 'best_rank': 4, 'mean_importance': 785.3, 'mean_importance_normalized': 0.07254918365469676, 'folds': [{'fold': 0, 'rank': 5, 'importance': 677.0, 'importance_normalized': 0.06456227350753385}, {'fold': 1, 'rank': 4, 'importance': 755.0, 'importance_normalized': 0.07023255813953488}, {'fold': 2, 'rank': 4, 'importance': 816.0, 'importance_normalized': 0.07462959575635632}, {'fold': 3, 'rank': 4, 'importance': 786.0, 'importance_normalized': 0.07222936960117625}, {'fold': 4, 'rank': 4, 'importance': 845.0, 'importance_normalized': 0.07816113218018685}, {'fold': 5, 'rank': 4, 'importance': 787.0, 'importance_normalized': 0.07291763179838784}, {'fold': 6, 'rank': 4, 'importance': 769.0, 'importance_normalized': 0.07121029724974534}, {'fold': 7, 'rank': 4, 'importance': 788.0, 'importance_normalized': 0.07193062528525787}, {'fold': 8, 'rank': 4, 'importance': 802.0, 'importance_normalized': 0.07381500230096641}, {'fold': 9, 'rank': 4, 'importance': 828.0, 'importance_normalized': 0.07580335072782203}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.9, 'best_rank': 4, 'mean_importance': 731.3, 'mean_importance_normalized': 0.0675999866499972, 'folds': [{'fold': 0, 'rank': 4, 'importance': 737.0, 'importance_normalized': 0.07028418844173183}, {'fold': 1, 'rank': 5, 'importance': 735.0, 'importance_normalized': 0.06837209302325581}, {'fold': 2, 'rank': 5, 'importance': 701.0, 'importance_normalized': 0.06411194439363453}, {'fold': 3, 'rank': 5, 'importance': 649.0, 'importance_normalized': 0.05963977210071678}, {'fold': 4, 'rank': 5, 'importance': 738.0, 'importance_normalized': 0.06826380538340579}, {'fold': 5, 'rank': 5, 'importance': 744.0, 'importance_normalized': 0.06893356805336792}, {'fold': 6, 'rank': 5, 'importance': 742.0, 'importance_normalized': 0.0687100657468284}, {'fold': 7, 'rank': 5, 'importance': 775.0, 'importance_normalized': 0.07074395253308992}, {'fold': 8, 'rank': 5, 'importance': 712.0, 'importance_normalized': 0.0655315232397607}, {'fold': 9, 'rank': 5, 'importance': 780.0, 'importance_normalized': 0.07140895358418017}], 'stability_rank': 5}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.5, 'best_rank': 6, 'mean_importance': 601.4, 'mean_importance_normalized': 0.05558213786089074, 'folds': [{'fold': 0, 'rank': 6, 'importance': 572.0, 'importance_normalized': 0.054548922372687395}, {'fold': 1, 'rank': 6, 'importance': 596.0, 'importance_normalized': 0.05544186046511628}, {'fold': 2, 'rank': 8, 'importance': 574.0, 'importance_normalized': 0.052496798975672214}, {'fold': 3, 'rank': 6, 'importance': 642.0, 'importance_normalized': 0.05899650799485389}, {'fold': 4, 'rank': 7, 'importance': 585.0, 'importance_normalized': 0.05411155304782166}, {'fold': 5, 'rank': 6, 'importance': 621.0, 'importance_normalized': 0.05753729268970629}, {'fold': 6, 'rank': 7, 'importance': 607.0, 'importance_normalized': 0.056208908232243726}, {'fold': 7, 'rank': 6, 'importance': 620.0, 'importance_normalized': 0.05659516202647193}, {'fold': 8, 'rank': 6, 'importance': 612.0, 'importance_normalized': 0.056327657616198804}, {'fold': 9, 'rank': 7, 'importance': 585.0, 'importance_normalized': 0.05355671518813513}], 'stability_rank': 6}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.7, 'best_rank': 6, 'mean_importance': 587.7, 'mean_importance_normalized': 0.0543064277919678, 'folds': [{'fold': 0, 'rank': 7, 'importance': 546.0, 'importance_normalized': 0.0520694259012016}, {'fold': 1, 'rank': 7, 'importance': 553.0, 'importance_normalized': 0.05144186046511628}, {'fold': 2, 'rank': 6, 'importance': 596.0, 'importance_normalized': 0.05450887141027986}, {'fold': 3, 'rank': 7, 'importance': 622.0, 'importance_normalized': 0.057158610549531336}, {'fold': 4, 'rank': 6, 'importance': 599.0, 'importance_normalized': 0.05540653038571825}, {'fold': 5, 'rank': 7, 'importance': 580.0, 'importance_normalized': 0.053738534235152416}, {'fold': 6, 'rank': 6, 'importance': 613.0, 'importance_normalized': 0.056764515232891936}, {'fold': 7, 'rank': 7, 'importance': 591.0, 'importance_normalized': 0.0539479689639434}, {'fold': 8, 'rank': 8, 'importance': 560.0, 'importance_normalized': 0.05154164749194662}, {'fold': 9, 'rank': 6, 'importance': 617.0, 'importance_normalized': 0.05648631328389637}], 'stability_rank': 7}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.9, 'best_rank': 7, 'mean_importance': 551.1, 'mean_importance_normalized': 0.05092127587603479, 'folds': [{'fold': 0, 'rank': 8, 'importance': 514.0, 'importance_normalized': 0.04901773793629601}, {'fold': 1, 'rank': 9, 'importance': 523.0, 'importance_normalized': 0.04865116279069767}, {'fold': 2, 'rank': 7, 'importance': 592.0, 'importance_normalized': 0.054143040058533015}, {'fold': 3, 'rank': 8, 'importance': 568.0, 'importance_normalized': 0.05219628744716045}, {'fold': 4, 'rank': 8, 'importance': 548.0, 'importance_normalized': 0.05068911294052354}, {'fold': 5, 'rank': 8, 'importance': 490.0, 'importance_normalized': 0.04539979616418049}, {'fold': 6, 'rank': 8, 'importance': 591.0, 'importance_normalized': 0.05472728956384851}, {'fold': 7, 'rank': 8, 'importance': 557.0, 'importance_normalized': 0.0508443633044272}, {'fold': 8, 'rank': 7, 'importance': 564.0, 'importance_normalized': 0.051909802116889094}, {'fold': 9, 'rank': 8, 'importance': 564.0, 'importance_normalized': 0.05163416643779182}], 'stability_rank': 8}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 9.0, 'best_rank': 8, 'mean_importance': 488.5, 'mean_importance_normalized': 0.04514190712619447, 'folds': [{'fold': 0, 'rank': 10, 'importance': 437.0, 'importance_normalized': 0.04167461377074194}, {'fold': 1, 'rank': 8, 'importance': 552.0, 'importance_normalized': 0.05134883720930233}, {'fold': 2, 'rank': 9, 'importance': 520.0, 'importance_normalized': 0.04755807572708981}, {'fold': 3, 'rank': 9, 'importance': 492.0, 'importance_normalized': 0.045212277154934755}, {'fold': 4, 'rank': 9, 'importance': 507.0, 'importance_normalized': 0.04689667930811211}, {'fold': 5, 'rank': 9, 'importance': 454.0, 'importance_normalized': 0.042064300935791714}, {'fold': 6, 'rank': 9, 'importance': 477.0, 'importance_normalized': 0.04417075655153255}, {'fold': 7, 'rank': 9, 'importance': 470.0, 'importance_normalized': 0.042902784116841626}, {'fold': 8, 'rank': 9, 'importance': 487.0, 'importance_normalized': 0.04482282558674643}, {'fold': 9, 'rank': 9, 'importance': 489.0, 'importance_normalized': 0.04476792090085142}], 'stability_rank': 9}, {'feature': 'vol_rolling_24', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 10.0, 'best_rank': 9, 'mean_importance': 431.7, 'mean_importance_normalized': 0.039904630529649404, 'folds': [{'fold': 0, 'rank': 9, 'importance': 439.0, 'importance_normalized': 0.04186534426854854}, {'fold': 1, 'rank': 10, 'importance': 443.0, 'importance_normalized': 0.0412093023255814}, {'fold': 2, 'rank': 10, 'importance': 443.0, 'importance_normalized': 0.04051582220596305}, {'fold': 3, 'rank': 11, 'importance': 399.0, 'importance_normalized': 0.036666054034184895}, {'fold': 4, 'rank': 10, 'importance': 437.0, 'importance_normalized': 0.040421792618629174}, {'fold': 5, 'rank': 10, 'importance': 422.0, 'importance_normalized': 0.039099416288335034}, {'fold': 6, 'rank': 10, 'importance': 399.0, 'importance_normalized': 0.03694786554310584}, {'fold': 7, 'rank': 10, 'importance': 450.0, 'importance_normalized': 0.041077133728890915}, {'fold': 8, 'rank': 10, 'importance': 454.0, 'importance_normalized': 0.04178554993097101}, {'fold': 9, 'rank': 10, 'importance': 431.0, 'importance_normalized': 0.03945802435228417}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.365784 | 1.654469 | -0.126552 | 1.176992 | 0.335402 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.089402 | 0.743007 | -0.066745 | 1.287755 | 0.182864 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | -0.051261 | -0.258751 | -0.149508 | 0.980344 | 1.837904 |
| ema_trend_48_192 | negative | 2.183e+04 | 0.184751 | 0.975757 | -0.108892 | 1.159342 | 0.309619 |
| ema_trend_48_192 | positive | 2.197e+04 | -0.123369 | -0.893606 | -0.161063 | 0.877201 | 0.808178 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 0.184549 | 0.657619 | -0.167171 | 1.074657 | 0.378348 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 944 |
| average_r | 0.011935 |
| median_r | 0.209840 |
| exit_reason_counts.max_holding_close | 17 |
| exit_reason_counts.r_trailing_stop | 673 |
| exit_reason_counts.stop_loss | 248 |
| exit_reason_counts.take_profit | 6 |
| avg_max_favorable_r | 0.668700 |
| median_max_favorable_r | 0.542677 |
| avg_max_adverse_r | -0.634117 |
| median_max_adverse_r | -0.442213 |
| breakeven_activated_count | 0 |
| profit_lock_activated_count | 0 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.967949 |
| avg_giveback_r | 0.656765 |
| avg_capture_ratio | -6.976075 |
| completed_trade_count | 944 |
| win_rate | 0.669492 |
| trade_return_profit_factor | 1.051060 |
| trade_r_profit_factor | 1.042299 |
| trade_profit_factor | 1.051060 |
| entry_trade_cost | 0.054848 |
| exit_trade_cost | 0.054848 |
| holding_trade_cost | 0.0 |
| total_trade_cost | 0.109695 |
| position_transition_count | 1774 |
| turnover_event_count | 1831 |
| exposed_bar_count | 3870 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.967949 |
| avg_mfe_r_of_losers | 0.238493 |
| median_mfe_r_of_losers | 0.173426 |
| avg_mfe_r_before_loss | 0.238493 |
| median_mfe_r_before_loss | 0.173426 |
| loser_reached_0_5r_rate | 0.092949 |
| loser_reached_1r_rate | 0.012821 |
| loser_reached_1_5r_rate | 0.009615 |
| loser_reached_2r_rate | 0.003205 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -6.976075 |
| median_capture_ratio | 0.353582 |
| avg_giveback_r | 0.656765 |
| median_giveback_r | 0.471283 |
| avg_giveback_r_winners | 0.441800 |
| avg_giveback_r_losers | 1.092206 |
| median_giveback_r_winners | 0.346306 |
| median_giveback_r_losers | 1.118076 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.981013 |
| winner_had_mae_below_minus_0_25r_rate | 0.495253 |
| winner_had_mae_below_minus_0_5r_rate | 0.229430 |
| winner_had_mae_below_minus_1r_rate | 0.009494 |
| avg_mae_r_of_winners | -0.320777 |
| median_mae_r_of_winners | -0.247803 |
| p90_abs_mae_r_of_winners | 0.725506 |
| avg_mae_r | -0.634117 |
| median_mae_r | -0.442213 |
| q10_mae_r | -1.355967 |
| q25_mae_r | -1.040175 |
| q75_mae_r | -0.160753 |
| q90_mae_r | -0.055355 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.669492 |
| prob_final_loss | 0.330508 |
| prob_final_win_given_mae_gt_minus_0_5r | 0.945631 |
| prob_final_win_given_mae_gt_minus_1r | 0.911208 |
| prob_mfe_ge_0_5r | 0.558263 |
| prob_final_loss_given_mfe_ge_0_5r | 0.055028 |
| prob_mfe_ge_1r | 0.185381 |
| prob_final_loss_given_mfe_ge_1r | 0.022857 |
| prob_mfe_ge_1_5r | 0.068856 |
| prob_final_loss_given_mfe_ge_1_5r | 0.046154 |
| prob_mfe_ge_2r | 0.033898 |
| prob_final_loss_given_mfe_ge_2r | 0.031250 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.986717 |
| prob_stop_loss_given_mfe_ge_1r | 0.965714 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 2.643008 |
| median_time_to_mfe | 1.000000 |
| avg_time_to_mae | 1.995763 |
| median_time_to_mae | 1.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.241525 |
| prob_mfe_ge_0_5r_within_2_bars | 0.325212 |
| prob_mfe_ge_1r_within_4_bars | 0.151483 |
| avg_r_by_bars_held_bucket.1 | -0.902952 |
| avg_r_by_bars_held_bucket.2 | 0.129431 |
| avg_r_by_bars_held_bucket.3-4 | 0.103543 |
| avg_r_by_bars_held_bucket.5-8 | 0.066814 |
| avg_r_by_bars_held_bucket.9-16 | -0.054085 |
| avg_r_by_bars_held_bucket.17+ | -0.196358 |
| win_rate_by_bars_held_bucket.1 | 0.035088 |
| win_rate_by_bars_held_bucket.2 | 0.738806 |
| win_rate_by_bars_held_bucket.3-4 | 0.756458 |
| win_rate_by_bars_held_bucket.5-8 | 0.707317 |
| win_rate_by_bars_held_bucket.9-16 | 0.623762 |
| win_rate_by_bars_held_bucket.17+ | 0.452381 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 944 |
| counterfactual.baseline.avg_r | 0.011935 |
| counterfactual.baseline.median_r | 0.209840 |
| counterfactual.baseline.win_rate | 0.669492 |
| counterfactual.baseline.profit_factor | 1.042299 |
| counterfactual.breakeven_after_0_5r.trade_count | 944 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.146446 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.355932 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.460834 |
| counterfactual.breakeven_after_1_0r.trade_count | 944 |
| counterfactual.breakeven_after_1_0r.avg_r | -0.051880 |
| counterfactual.breakeven_after_1_0r.median_r | 0.168047 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.599576 |
| counterfactual.breakeven_after_1_0r.profit_factor | 0.814442 |
| counterfactual.exit_at_first_0_5r.trade_count | 944 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.031024 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.700212 |
| counterfactual.exit_at_first_0_5r.profit_factor | 1.114218 |
| counterfactual.exit_at_first_1_0r.trade_count | 944 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.046891 |
| counterfactual.exit_at_first_1_0r.median_r | 0.221149 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.673729 |
| counterfactual.exit_at_first_1_0r.profit_factor | 1.167713 |
| counterfactual.partial_50pct_at_1r.trade_count | 944 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.029413 |
| counterfactual.partial_50pct_at_1r.median_r | 0.218865 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.671610 |
| counterfactual.partial_50pct_at_1r.profit_factor | 1.105190 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 944 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.004095 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.171113 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.609110 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.015925 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 944 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.041960 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.221149 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.673729 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 1.150078 |
| counterfactual.best_policy_by_avg_r | exit_at_first_1_0r |
| counterfactual.best_policy_by_profit_factor | exit_at_first_1_0r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| max_holding_close | 17 | -0.220491 | -0.284211 | 0.235294 | 0.280581 | -0.836269 | 0.501072 | 24.000000 | 0.198168 | 1.000000 | 0.058824 | 0.0 |
| r_trailing_stop | 673 | 0.376606 | 0.304920 | 0.924220 | 0.830475 | -0.341939 | 0.453869 | 4.722140 | 31.247789 | 1.000000 | 0.763744 | 0.248143 |
| stop_loss | 248 | -1.021389 | -1.019540 | 0.0 | 0.172088 | -1.423101 | 1.193477 | 4.862903 | 0.0 | 0.959677 | 0.024194 | 0.008065 |
| take_profit | 6 | 2.477222 | 2.479746 | 1.000000 | 4.149163 | -0.222662 | 1.671940 | 3.666667 | inf | 1.000000 | 1.000000 | 1.000000 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 944 |
| gross_pnl | 0.198793 |
| net_pnl | 0.074167 |
| total_cost | 0.109695 |
| cost_to_gross_pnl | 0.626914 |

### Trade Count By Asset
| Asset | Trades |
| --- | --- |
| ETHUSD | 944 |

### Performance Breakdowns
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asset | ETHUSD | 944 | 0.189828 | 0.054848 | 0.054848 | 0.0 | 0.109695 | 0.080133 | 1.051060 | 0.669492 |
| side | long | 559 | -0.017835 | 0.031921 | 0.031921 | 0.0 | 0.063842 | -0.081677 | 0.916997 | 0.651163 |
| side | short | 385 | 0.207663 | 0.022927 | 0.022927 | 0.0 | 0.045853 | 0.161809 | 1.276421 | 0.696104 |
| volatility_regime | missing | 944 | 0.189828 | 0.054848 | 0.054848 | 0.0 | 0.109695 | 0.080133 | 1.051060 | 0.669492 |
| year | 2022 | 378 | 0.128842 | 0.016542 | 0.016542 | 0.0 | 0.033085 | 0.095757 | 1.163930 | 0.701058 |
| year | 2023 | 370 | 0.024058 | 0.027784 | 0.027784 | 0.0 | 0.055568 | -0.031510 | 0.952090 | 0.627027 |
| year | 2024 | 196 | 0.036928 | 0.010521 | 0.010521 | 0.0 | 0.021042 | 0.015886 | 1.048495 | 0.688776 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1872 |
| actual_trade_count | 944 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 0.074167 |
| sharpe | 0.217473 |
| sortino | 0.358223 |
| calmar | 0.099167 |
| max_drawdown | -0.116627 |
| profit_factor | 1.026210 |
| hit_rate | 0.455340 |
| trade_count | 944 |
| gross_pnl | 0.198793 |
| net_pnl | 0.074167 |
| total_cost | 0.109695 |
| cost_to_gross_pnl | 0.626914 |
| average_r | 0.011935 |
| median_r | 0.209840 |

### Side Diagnostics
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| side | long | 559 | -0.017835 |  |  |  | 0.063842 | -0.081677 | 0.916997 | 0.651163 |
| side | short | 385 | 0.207663 |  |  |  | 0.045853 | 0.161809 | 1.276421 | 0.696104 |

### Year Diagnostics
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| year | 2022 | 378 | 0.128842 |  |  |  | 0.033085 | 0.095757 | 1.163930 | 0.701058 |
| year | 2023 | 370 | 0.024058 |  |  |  | 0.055568 | -0.031510 | 0.952090 | 0.627027 |
| year | 2024 | 196 | 0.036928 |  |  |  | 0.021042 | 0.015886 | 1.048495 | 0.688776 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 0.074167 |
| cost_x1.annualized_return | 0.029032 |
| cost_x1.annualized_vol | 0.083898 |
| cost_x1.sharpe | 0.346034 |
| cost_x1.sortino | 0.565119 |
| cost_x1.calmar | 0.248926 |
| cost_x1.max_drawdown | -0.116627 |
| cost_x1.profit_factor | 1.026210 |
| cost_x1.hit_rate | 0.455340 |
| cost_x1.bar_return_profit_factor | 1.026210 |
| cost_x1.conventional_sharpe | 0.383023 |
| cost_x1.return_over_vol_sharpe | 0.346034 |
| cost_x1.profit_factor_scope | bar_returns |
| cost_x1.metric_scope | bar_returns |
| cost_x1.annualization_mode | fixed_periods |
| cost_x1.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x1.gross_pnl | 0.198793 |
| cost_x1.net_pnl | 0.074167 |
| cost_x1.total_cost | 0.109695 |
| cost_x1.cost_drag | 0.124626 |
| cost_x1.cost_to_gross_pnl | 0.626914 |
| cost_x1.gross_return_sum | 0.190033 |
| cost_x1.net_return_sum | 0.080337 |
| cost_x1.cost_return_sum | 0.109695 |
| cost_x1.avg_turnover | 0.025045 |
| cost_x1.total_turnover | 1.097e+03 |
| cost_x1.evaluation_scope | strict_oos_only |
| cost_x1.evaluation_start | 2022-03-14T15:00:00 |
| cost_x1.evaluation_end | 2024-09-17T10:30:00 |
| cost_x1.evaluation_rows | 43800 |
| cost_x2.cumulative_return | -0.037511 |
| cost_x2.annualized_return | -0.015177 |
| cost_x2.annualized_vol | 0.084288 |
| cost_x2.sharpe | -0.180057 |
| cost_x2.sortino | -0.203215 |
| cost_x2.calmar | -0.100076 |
| cost_x2.max_drawdown | -0.151651 |
| cost_x2.profit_factor | 0.990674 |
| cost_x2.hit_rate | 0.449303 |
| cost_x2.bar_return_profit_factor | 0.990674 |
| cost_x2.conventional_sharpe | -0.139322 |
| cost_x2.return_over_vol_sharpe | -0.180057 |
| cost_x2.profit_factor_scope | bar_returns |
| cost_x2.metric_scope | bar_returns |
| cost_x2.annualization_mode | fixed_periods |
| cost_x2.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x2.gross_pnl | 0.198793 |
| cost_x2.net_pnl | -0.037511 |
| cost_x2.total_cost | 0.219391 |
| cost_x2.cost_drag | 0.236304 |
| cost_x2.cost_to_gross_pnl | 1.188694 |
| cost_x2.gross_return_sum | 0.190033 |
| cost_x2.net_return_sum | -0.029358 |
| cost_x2.cost_return_sum | 0.219391 |
| cost_x2.avg_turnover | 0.025045 |
| cost_x2.total_turnover | 1.097e+03 |
| cost_x2.evaluation_scope | strict_oos_only |
| cost_x2.evaluation_start | 2022-03-14T15:00:00 |
| cost_x2.evaluation_end | 2024-09-17T10:30:00 |
| cost_x2.evaluation_rows | 43800 |
| cost_x3.cumulative_return | -0.137585 |
| cost_x3.annualized_return | -0.057489 |
| cost_x3.annualized_vol | 0.084713 |
| cost_x3.sharpe | -0.678629 |
| cost_x3.sortino | -0.946930 |
| cost_x3.calmar | -0.272448 |
| cost_x3.max_drawdown | -0.211008 |
| cost_x3.profit_factor | 0.956977 |
| cost_x3.hit_rate | 0.444930 |
| cost_x3.bar_return_profit_factor | 0.956977 |
| cost_x3.conventional_sharpe | -0.656585 |
| cost_x3.return_over_vol_sharpe | -0.678629 |
| cost_x3.profit_factor_scope | bar_returns |
| cost_x3.metric_scope | bar_returns |
| cost_x3.annualization_mode | fixed_periods |
| cost_x3.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x3.gross_pnl | 0.198793 |
| cost_x3.net_pnl | -0.137585 |
| cost_x3.total_cost | 0.329086 |
| cost_x3.cost_drag | 0.336378 |
| cost_x3.cost_to_gross_pnl | 1.692102 |
| cost_x3.gross_return_sum | 0.190033 |
| cost_x3.net_return_sum | -0.139053 |
| cost_x3.cost_return_sum | 0.329086 |
| cost_x3.avg_turnover | 0.025045 |
| cost_x3.total_turnover | 1.097e+03 |
| cost_x3.evaluation_scope | strict_oos_only |
| cost_x3.evaluation_start | 2022-03-14T15:00:00 |
| cost_x3.evaluation_end | 2024-09-17T10:30:00 |
| cost_x3.evaluation_rows | 43800 |
| cost_x5.cumulative_return | -0.307616 |
| cost_x5.annualized_return | -0.136746 |
| cost_x5.annualized_vol | 0.085666 |
| cost_x5.sharpe | -1.596274 |
| cost_x5.sortino | -2.361118 |
| cost_x5.calmar | -0.400349 |
| cost_x5.max_drawdown | -0.341566 |
| cost_x5.profit_factor | 0.894654 |
| cost_x5.hit_rate | 0.441183 |
| cost_x5.bar_return_profit_factor | 0.894654 |
| cost_x5.conventional_sharpe | -1.673689 |
| cost_x5.return_over_vol_sharpe | -1.596274 |
| cost_x5.profit_factor_scope | bar_returns |
| cost_x5.metric_scope | bar_returns |
| cost_x5.annualization_mode | fixed_periods |
| cost_x5.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x5.gross_pnl | 0.198793 |
| cost_x5.net_pnl | -0.307616 |
| cost_x5.total_cost | 0.548476 |
| cost_x5.cost_drag | 0.506409 |
| cost_x5.cost_to_gross_pnl | 2.547420 |
| cost_x5.gross_return_sum | 0.190033 |
| cost_x5.net_return_sum | -0.358444 |
| cost_x5.cost_return_sum | 0.548476 |
| cost_x5.avg_turnover | 0.025045 |
| cost_x5.total_turnover | 1.097e+03 |
| cost_x5.evaluation_scope | strict_oos_only |
| cost_x5.evaluation_start | 2022-03-14T15:00:00 |
| cost_x5.evaluation_end | 2024-09-17T10:30:00 |
| cost_x5.evaluation_rows | 43800 |

### Slippage Stress
| Metric | Value |
| --- | --- |
| slippage_x1.cumulative_return | 0.074167 |
| slippage_x1.annualized_return | 0.029032 |
| slippage_x1.annualized_vol | 0.083898 |
| slippage_x1.sharpe | 0.346034 |
| slippage_x1.sortino | 0.565119 |
| slippage_x1.calmar | 0.248926 |
| slippage_x1.max_drawdown | -0.116627 |
| slippage_x1.profit_factor | 1.026210 |
| slippage_x1.hit_rate | 0.455340 |
| slippage_x1.bar_return_profit_factor | 1.026210 |
| slippage_x1.conventional_sharpe | 0.383023 |
| slippage_x1.return_over_vol_sharpe | 0.346034 |
| slippage_x1.profit_factor_scope | bar_returns |
| slippage_x1.metric_scope | bar_returns |
| slippage_x1.annualization_mode | fixed_periods |
| slippage_x1.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x1.gross_pnl | 0.074167 |
| slippage_x1.net_pnl | 0.074167 |
| slippage_x1.total_cost | 0.0 |
| slippage_x1.cost_drag | 0.0 |
| slippage_x1.cost_to_gross_pnl | 0.0 |
| slippage_x1.gross_return_sum | 0.080337 |
| slippage_x1.net_return_sum | 0.080337 |
| slippage_x1.cost_return_sum | 0.0 |
| slippage_x1.avg_turnover | 0.0 |
| slippage_x1.total_turnover | 0.0 |
| slippage_x1.evaluation_scope | strict_oos_only |
| slippage_x1.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x1.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x1.evaluation_rows | 43800 |
| slippage_x2.cumulative_return | 0.074167 |
| slippage_x2.annualized_return | 0.029032 |
| slippage_x2.annualized_vol | 0.083898 |
| slippage_x2.sharpe | 0.346034 |
| slippage_x2.sortino | 0.565119 |
| slippage_x2.calmar | 0.248926 |
| slippage_x2.max_drawdown | -0.116627 |
| slippage_x2.profit_factor | 1.026210 |
| slippage_x2.hit_rate | 0.455340 |
| slippage_x2.bar_return_profit_factor | 1.026210 |
| slippage_x2.conventional_sharpe | 0.383023 |
| slippage_x2.return_over_vol_sharpe | 0.346034 |
| slippage_x2.profit_factor_scope | bar_returns |
| slippage_x2.metric_scope | bar_returns |
| slippage_x2.annualization_mode | fixed_periods |
| slippage_x2.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x2.gross_pnl | 0.074167 |
| slippage_x2.net_pnl | 0.074167 |
| slippage_x2.total_cost | 0.0 |
| slippage_x2.cost_drag | 0.0 |
| slippage_x2.cost_to_gross_pnl | 0.0 |
| slippage_x2.gross_return_sum | 0.080337 |
| slippage_x2.net_return_sum | 0.080337 |
| slippage_x2.cost_return_sum | 0.0 |
| slippage_x2.avg_turnover | 0.0 |
| slippage_x2.total_turnover | 0.0 |
| slippage_x2.evaluation_scope | strict_oos_only |
| slippage_x2.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x2.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x2.evaluation_rows | 43800 |
| slippage_x3.cumulative_return | 0.074167 |
| slippage_x3.annualized_return | 0.029032 |
| slippage_x3.annualized_vol | 0.083898 |
| slippage_x3.sharpe | 0.346034 |
| slippage_x3.sortino | 0.565119 |
| slippage_x3.calmar | 0.248926 |
| slippage_x3.max_drawdown | -0.116627 |
| slippage_x3.profit_factor | 1.026210 |
| slippage_x3.hit_rate | 0.455340 |
| slippage_x3.bar_return_profit_factor | 1.026210 |
| slippage_x3.conventional_sharpe | 0.383023 |
| slippage_x3.return_over_vol_sharpe | 0.346034 |
| slippage_x3.profit_factor_scope | bar_returns |
| slippage_x3.metric_scope | bar_returns |
| slippage_x3.annualization_mode | fixed_periods |
| slippage_x3.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x3.gross_pnl | 0.074167 |
| slippage_x3.net_pnl | 0.074167 |
| slippage_x3.total_cost | 0.0 |
| slippage_x3.cost_drag | 0.0 |
| slippage_x3.cost_to_gross_pnl | 0.0 |
| slippage_x3.gross_return_sum | 0.080337 |
| slippage_x3.net_return_sum | 0.080337 |
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
| delay_1_bars.cumulative_return | 0.132416 |
| delay_1_bars.annualized_return | 0.050999 |
| delay_1_bars.annualized_vol | 0.084156 |
| delay_1_bars.sharpe | 0.606005 |
| delay_1_bars.sortino | 0.956324 |
| delay_1_bars.calmar | 0.547458 |
| delay_1_bars.max_drawdown | -0.093156 |
| delay_1_bars.profit_factor | 1.041623 |
| delay_1_bars.hit_rate | 0.453693 |
| delay_1_bars.bar_return_profit_factor | 1.041623 |
| delay_1_bars.conventional_sharpe | 0.633096 |
| delay_1_bars.return_over_vol_sharpe | 0.606005 |
| delay_1_bars.profit_factor_scope | bar_returns |
| delay_1_bars.metric_scope | bar_returns |
| delay_1_bars.annualization_mode | fixed_periods |
| delay_1_bars.sharpe_legacy_alias | return_over_vol_sharpe |
| delay_1_bars.gross_pnl | 0.132416 |
| delay_1_bars.net_pnl | 0.132416 |
| delay_1_bars.total_cost | 0.0 |
| delay_1_bars.cost_drag | 0.0 |
| delay_1_bars.cost_to_gross_pnl | 0.0 |
| delay_1_bars.gross_return_sum | 0.133198 |
| delay_1_bars.net_return_sum | 0.133198 |
| delay_1_bars.cost_return_sum | 0.0 |
| delay_1_bars.avg_turnover | 0.0 |
| delay_1_bars.total_turnover | 0.0 |
| delay_1_bars.evaluation_scope | strict_oos_only |
| delay_1_bars.evaluation_start | 2022-03-14T15:00:00 |
| delay_1_bars.evaluation_end | 2024-09-17T10:30:00 |
| delay_1_bars.evaluation_rows | 43800 |
| delay_2_bars.cumulative_return | 0.185578 |
| delay_2_bars.annualized_return | 0.070464 |
| delay_2_bars.annualized_vol | 0.085002 |
| delay_2_bars.sharpe | 0.828972 |
| delay_2_bars.sortino | 1.265972 |
| delay_2_bars.calmar | 0.771902 |
| delay_2_bars.max_drawdown | -0.091286 |
| delay_2_bars.profit_factor | 1.056261 |
| delay_2_bars.hit_rate | 0.453949 |
| delay_2_bars.bar_return_profit_factor | 1.056261 |
| delay_2_bars.conventional_sharpe | 0.843534 |
| delay_2_bars.return_over_vol_sharpe | 0.828972 |
| delay_2_bars.profit_factor_scope | bar_returns |
| delay_2_bars.metric_scope | bar_returns |
| delay_2_bars.annualization_mode | fixed_periods |
| delay_2_bars.sharpe_legacy_alias | return_over_vol_sharpe |
| delay_2_bars.gross_pnl | 0.185578 |
| delay_2_bars.net_pnl | 0.185578 |
| delay_2_bars.total_cost | 0.0 |
| delay_2_bars.cost_drag | 0.0 |
| delay_2_bars.cost_to_gross_pnl | 0.0 |
| delay_2_bars.gross_return_sum | 0.179255 |
| delay_2_bars.net_return_sum | 0.179255 |
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
| positive_active_periods | 2 |
| positive_active_period_ratio | 0.666667 |
| min_active_period_cumulative_return | -0.034158 |
| median_active_period_cumulative_return | 0.013880 |
| mean_active_period_cumulative_return | 0.025551 |
| mean_active_period_sharpe | 0.395923 |
| std_active_period_sharpe | 0.709916 |
| worst_active_period_max_drawdown | -0.116627 |

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
| oos_prediction.mean | -0.004979 |
| oos_prediction.std | 0.973485 |
| oos_prediction.min | -4.438581 |
| oos_prediction.max | 3.706707 |
| oos_prediction.median | 0.009550 |
| oos_prediction.q01 | -2.538497 |
| oos_prediction.q05 | -1.661384 |
| oos_prediction.q25 | -0.595408 |
| oos_prediction.q75 | 0.616244 |
| oos_prediction.q95 | 1.574688 |
| oos_prediction.q99 | 2.291646 |
| oos_prediction.skew | -0.160894 |
| oos_prediction.kurtosis | 0.477781 |
| oos_prediction.positive_rate | 0.504087 |
| oos_prediction.negative_rate | 0.495913 |
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
| 1 | atr_48 | 1.122e+03 | 0.103761 | 10 | feature_importances_ |
| 2 | vol_rolling_192 | 1.076e+03 | 0.099469 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 939.800000 | 0.086834 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 785.300000 | 0.072549 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 731.300000 | 0.067600 | 10 | feature_importances_ |
| 6 | bollinger_bandwidth_rank_192 | 601.400000 | 0.055582 | 10 | feature_importances_ |
| 7 | atr_over_price_48 | 587.700000 | 0.054306 | 10 | feature_importances_ |
| 8 | vol_rolling_48 | 551.100000 | 0.050921 | 10 | feature_importances_ |
| 9 | atr_pct_rank_192 | 488.500000 | 0.045142 | 10 | feature_importances_ |
| 10 | vol_rolling_24 | 431.700000 | 0.039905 | 10 | feature_importances_ |
| 11 | mama_minus_fama_over_atr | 405.600000 | 0.037496 | 10 | feature_importances_ |
| 12 | close_over_bb_upper_192 | 313.300000 | 0.028965 | 10 | feature_importances_ |
| 13 | ret_48 | 311.500000 | 0.028796 | 10 | feature_importances_ |
| 14 | close_over_bb_mid_192 | 289.400000 | 0.026741 | 10 | feature_importances_ |
| 15 | bollinger_percent_b | 250.200000 | 0.023122 | 10 | feature_importances_ |
| 16 | distance_from_ema96_atr | 189.200000 | 0.017494 | 10 | feature_importances_ |
| 17 | ret_24 | 175.500000 | 0.016210 | 10 | feature_importances_ |
| 18 | roofing_filter_over_atr | 159.200000 | 0.014717 | 10 | feature_importances_ |
| 19 | atr_pct | 136.000000 | 0.012576 | 10 | feature_importances_ |
| 20 | ret_16 | 135.000000 | 0.012477 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 0.198793 |
| net_pnl | 0.074167 |
| total_cost | 0.109695 |
| cost_drag | 0.124626 |
| cost_to_gross_pnl | 0.626914 |
| avg_turnover | 0.025045 |
| total_turnover | 1.097e+03 |
| mean_abs_signal | 0.042740 |
| signal_turnover | 0.050685 |
| flat_rate | 0.957260 |
| long_rate | 0.025274 |
| short_rate | 0.017466 |
| trade_rate | 0.088356 |
| executed_trade_count | 3870 |
| avg_signal_executed | 0.043411 |
| avg_pred_prob_executed | 0.512798 |
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
| 0 |  | 0.004370 | -0.010781 | 0.015200 | -0.321584 | 0.034703 |  |  |  |  |
| 1 |  | 0.117607 | 0.091537 | 0.023600 | 1.446431 | 0.053881 |  |  |  |  |
| 2 |  | 0.042280 | 0.024919 | 0.016800 | 0.771962 | 0.038356 |  |  |  |  |
| 3 |  | -0.006213 | -0.022573 | 0.016600 | -0.660196 | 0.037900 |  |  |  |  |
| 4 |  | 0.069058 | 0.058004 | 0.010400 | 3.549360 | 0.023744 |  |  |  |  |
| 5 |  | -0.065969 | -0.079881 | 0.015000 | -3.613009 | 0.034247 |  |  |  |  |
| 6 |  | -0.042914 | -0.054334 | 0.012000 | -2.402838 | 0.027397 |  |  |  |  |
| 7 |  | 0.020218 | 0.013710 | 0.006400 | 0.685154 | 0.014612 |  |  |  |  |
| 8 |  | 0.029529 | 0.022758 | 0.006600 | 1.141781 | 0.015068 |  |  |  |  |
| 9 |  | 0.006332 | 0.000714 | 0.005600 | 0.039501 | 0.012785 |  |  |  |  |


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
- Drifted feature count: `8` / `46`
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
| unclassified | 33 | 3 | 0.090909 | 0.109534 | 1.187111 |
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
  engine: manual_barrier
  returns_col: close_ret
  signal_col: signal_structured_tail
  periods_per_year: 17520
  returns_type: simple
  missing_return_policy: raise_if_exposed
  min_holding_bars: 0
  subset: full
  stop_mode: volatility_stop
  vol_col: atr_over_price_48
  open_col: open
  high_col: high
  low_col: low
  close_col: close
  take_profit_r: 5.0
  stop_loss_r: 2.0
  volatility_col: null
  entry_price_mode: null
  profit_barrier_r: null
  stop_barrier_r: null
  vertical_barrier_bars: null
  tie_break: null
  event_time_remap_policy: null
  annualization_mode: null
  max_cost_r: null
  risk_per_trade: 0.006
  max_holding_bars: 24
  asset_params: {}
  dynamic_exit: {}
  strategy_path: {}
  dynamic_exits:
    enabled: true
    r_trailing:
      enabled: true
      activation_r: 0.75
      distance_r: 0.4
      risk_distance_col: atr_48
      intrabar_policy: adverse_first
  partial_exits: {}
  allow_short: true
  oos_mode: strict
  execution_price: next_open
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
- `probability_trade_quality_diagnostics`: `report_assets/probability_trade_quality_diagnostics.json`
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
