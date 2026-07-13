# Experiment Report: ethusd_30m_trial0041_featadd_fractal96_v1

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/03_feature_additions/ethusd_30m_trial0041_featadd_fractal96_v1.yaml`
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
config_path: /workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/03_feature_additions/ethusd_30m_trial0041_featadd_fractal96_v1.yaml
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
- `feature[fractal_dimension]` -> `src.features.fractal_dimension.add_fractal_dimension(df: 'pd.DataFrame', price_col: 'str' = 'close', window: 'int' = 128, output_col: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'window': 96, 'output_col': 'fractal_dimension_96'}

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
- step: fractal_dimension
  params:
    price_col: close
    window: 96
    output_col: fractal_dimension_96
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
- fractal_dimension_96
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
  - fractal_dimension_96
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
| cumulative_return | 2.301749 |
| annualized_return | 0.612492 |
| annualized_vol | 0.296074 |
| sharpe | 2.068715 |
| sortino | 3.237043 |
| calmar | 3.336533 |
| max_drawdown | -0.183571 |
| profit_factor | 1.112391 |
| hit_rate | 0.486929 |
| avg_turnover | 0.014041 |
| total_turnover | 615.000000 |
| gross_pnl | 1.364884 |
| net_pnl | 1.303384 |
| total_cost | 0.061500 |
| cost_drag | 0.061500 |
| cost_to_gross_pnl | 0.045059 |
| flat_rate | 0.955320 |
| long_rate | 0.025457 |
| short_rate | 0.019224 |
| trade_count | 308 |
| average_r | 0.385492 |
| median_r | 0.224261 |
| avg_max_favorable_r | 3.334179 |
| avg_max_adverse_r | -2.881274 |
| loser_was_positive_rate | 0.985507 |
| avg_giveback_r | 2.948687 |
| avg_capture_ratio | -9.808038 |
| robustness_walk_forward_positive_fold_ratio | 0.600000 |
| robustness_walk_forward_min_fold_cumulative_return | 0.0 |
| robustness_walk_forward_worst_fold_max_drawdown | -0.183571 |
| robustness_walk_forward_mean_fold_sharpe | 1.200497 |
| robustness_walk_forward_std_fold_sharpe | 1.326972 |
| robustness_cost_x1_cumulative_return | 2.255895 |
| robustness_cost_x1_sharpe | 1.413092 |
| robustness_cost_x1_max_drawdown | -0.183571 |
| robustness_cost_x1_profit_factor | 1.110736 |
| robustness_cost_x2_cumulative_return | 2.061362 |
| robustness_cost_x2_sharpe | 1.329122 |
| robustness_cost_x2_max_drawdown | -0.194763 |
| robustness_cost_x2_profit_factor | 1.105016 |
| robustness_cost_x3_cumulative_return | 1.878434 |
| robustness_cost_x3_sharpe | 1.246329 |
| robustness_cost_x3_max_drawdown | -0.205802 |
| robustness_cost_x3_profit_factor | 1.099340 |
| robustness_cost_x5_cumulative_return | 1.544668 |
| robustness_cost_x5_sharpe | 1.084237 |
| robustness_cost_x5_max_drawdown | -0.227431 |
| robustness_cost_x5_profit_factor | 1.088119 |
| robustness_delay_1_bars_cumulative_return | 2.296276 |
| robustness_delay_1_bars_sharpe | 1.134723 |
| robustness_delay_1_bars_max_drawdown | -0.150561 |
| robustness_delay_1_bars_profit_factor | 1.112724 |
| robustness_delay_2_bars_cumulative_return | 2.442332 |
| robustness_delay_2_bars_sharpe | 1.185152 |
| robustness_delay_2_bars_max_drawdown | -0.190706 |
| robustness_delay_2_bars_profit_factor | 1.117058 |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.044680 |
| signal_turnover | 0.052237 |
| long_rate | 0.025457 |
| short_rate | 0.019224 |
| flat_rate | 0.955320 |
| executed_trade_count | 7416 |
| trade_rate | 0.169315 |
| avg_signal_executed | 0.033172 |
| avg_pred_prob_executed | 0.510998 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.522922 |
| classification.brier | 0.282901 |
| classification.roc_auc | 0.531011 |
| classification.log_loss | 0.784957 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.177549 |
| regression.rmse | 2.645483 |
| regression.mse | 6.998579 |
| regression.r2 | -0.120853 |
| regression.correlation | 0.053822 |
| regression.directional_accuracy | 0.522831 |
| regression.mean_prediction | -0.024345 |
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
| prediction_distribution.mean | -0.024345 |
| prediction_distribution.std | 1.013078 |
| prediction_distribution.min | -4.317914 |
| prediction_distribution.max | 3.997899 |
| prediction_distribution.median | 0.001709 |
| prediction_distribution.q01 | -2.600664 |
| prediction_distribution.q05 | -1.747562 |
| prediction_distribution.q25 | -0.657381 |
| prediction_distribution.q75 | 0.639077 |
| prediction_distribution.q95 | 1.611474 |
| prediction_distribution.q99 | 2.281949 |
| prediction_distribution.skew | -0.193852 |
| prediction_distribution.kurtosis | 0.308041 |
| prediction_distribution.positive_rate | 0.500685 |
| prediction_distribution.negative_rate | 0.499315 |
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
| probability_distribution.mean | 0.494717 |
| probability_distribution.std | 0.208960 |
| probability_distribution.min | 0.008590 |
| probability_distribution.max | 0.977909 |
| probability_distribution.median | 0.500469 |
| probability_distribution.q01 | 0.067620 |
| probability_distribution.q05 | 0.142739 |
| probability_distribution.q25 | 0.336817 |
| probability_distribution.q75 | 0.657242 |
| probability_distribution.q95 | 0.826877 |
| probability_distribution.q99 | 0.901917 |
| probability_distribution.skew | -0.083152 |
| probability_distribution.kurtosis | -0.804164 |
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
| model_strategy | 2.301749 | 0.612492 | 0.296074 | 2.068715 | 3.237043 | 3.336533 | -0.183571 | 1.112391 | 0.486929 | 615.000000 | 0.045059 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | -0.089284 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000224 |
| random_sign_same_rate | 0.794312 | 0.263453 | 0.383543 | 0.686894 | 0.989171 | 0.639950 | -0.411678 | 1.034375 | 0.480936 | 1.280e+03 | 0.142787 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | -0.240522 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.789225 |
| simple_trend | -0.867002 | -0.553792 | 0.665797 | -0.831772 | -1.181822 | -0.608132 | -0.910644 | 0.978047 | 0.491683 | 1.545e+03 | 0.118038 |


## Threshold Grid
| Name | Upper | Lower | Net PnL | Sharpe | Max DD | Profit Factor | Cost/Gross | Turnover | Active Rows | Profitable Folds | Median Fold Return | Worst 3-Fold Avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sym_0.35 | 0.350000 | -0.350000 | 0.257818 | 0.177589 | -0.518345 | 1.014126 | 0.225403 | 1.733e+03 | 3.115e+04 | 7.000000 | 0.095367 | -0.254671 |
| sym_0.5 | 0.500000 | -0.500000 | 1.393445 | 0.820528 | -0.481007 | 1.031058 | 0.124950 | 1.709e+03 | 2.620e+04 | 6.000000 | 0.085112 | -0.143608 |
| sym_0.75 | 0.750000 | -0.750000 | 0.093386 | 0.078556 | -0.502778 | 1.010786 | 0.306116 | 1.575e+03 | 1.917e+04 | 4.000000 | -0.065585 | -0.162124 |
| sym_1 | 1.000000 | -1.000000 | -0.054358 | -0.051040 | -0.559056 | 1.006352 | 0.437915 | 1.392e+03 | 1.348e+04 | 5.000000 | -0.025117 | -0.193795 |
| sym_1.25 | 1.250000 | -1.250000 | 0.462300 | 0.412760 | -0.418700 | 1.025140 | 0.166034 | 1.150e+03 | 9.062e+03 | 6.000000 | 0.119840 | -0.174464 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.149653 |
| mean_fold_return | 0.138588 |
| fold_return_std | 0.169899 |
| worst_fold_return | -0.070111 |
| best_fold_return | 0.481504 |
| worst_3_fold_average_return | -0.033349 |
| profitable_fold_count | 8.000000 |
| profitable_fold_rate | 0.800000 |
| median_fold_sharpe | 2.486061 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.2, 'best_rank': 1, 'mean_importance': 1038.1, 'mean_importance_normalized': 0.09560018983377264, 'folds': [{'fold': 0, 'rank': 2, 'importance': 959.0, 'importance_normalized': 0.09196394322976602}, {'fold': 1, 'rank': 1, 'importance': 1049.0, 'importance_normalized': 0.09695905351696091}, {'fold': 2, 'rank': 2, 'importance': 1025.0, 'importance_normalized': 0.09379575402635432}, {'fold': 3, 'rank': 1, 'importance': 1012.0, 'importance_normalized': 0.09287812041116006}, {'fold': 4, 'rank': 1, 'importance': 1032.0, 'importance_normalized': 0.09441039246180587}, {'fold': 5, 'rank': 1, 'importance': 1017.0, 'importance_normalized': 0.09342274480984751}, {'fold': 6, 'rank': 1, 'importance': 1055.0, 'importance_normalized': 0.09679787136434535}, {'fold': 7, 'rank': 1, 'importance': 1062.0, 'importance_normalized': 0.0972972972972973}, {'fold': 8, 'rank': 1, 'importance': 1061.0, 'importance_normalized': 0.09716117216117216}, {'fold': 9, 'rank': 1, 'importance': 1109.0, 'importance_normalized': 0.10131554905901699}], 'stability_rank': 1}, {'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.9, 'best_rank': 1, 'mean_importance': 979.5, 'mean_importance_normalized': 0.09023189477820799, 'folds': [{'fold': 0, 'rank': 1, 'importance': 965.0, 'importance_normalized': 0.09253931722286153}, {'fold': 1, 'rank': 2, 'importance': 987.0, 'importance_normalized': 0.09122839449117294}, {'fold': 2, 'rank': 1, 'importance': 1057.0, 'importance_normalized': 0.09672401171303074}, {'fold': 3, 'rank': 2, 'importance': 985.0, 'importance_normalized': 0.09040014684287812}, {'fold': 4, 'rank': 2, 'importance': 953.0, 'importance_normalized': 0.08718324032567926}, {'fold': 5, 'rank': 2, 'importance': 984.0, 'importance_normalized': 0.09039132831159287}, {'fold': 6, 'rank': 2, 'importance': 956.0, 'importance_normalized': 0.0877144692173594}, {'fold': 7, 'rank': 2, 'importance': 989.0, 'importance_normalized': 0.09060925332111773}, {'fold': 8, 'rank': 2, 'importance': 982.0, 'importance_normalized': 0.08992673992673993}, {'fold': 9, 'rank': 3, 'importance': 937.0, 'importance_normalized': 0.08560204640964736}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 2.9, 'best_rank': 2, 'mean_importance': 901.5, 'mean_importance_normalized': 0.083000985878234, 'folds': [{'fold': 0, 'rank': 3, 'importance': 800.0, 'importance_normalized': 0.07671653241273495}, {'fold': 1, 'rank': 3, 'importance': 852.0, 'importance_normalized': 0.07875034661244108}, {'fold': 2, 'rank': 3, 'importance': 877.0, 'importance_normalized': 0.08025256222547585}, {'fold': 3, 'rank': 3, 'importance': 926.0, 'importance_normalized': 0.08498531571218795}, {'fold': 4, 'rank': 3, 'importance': 919.0, 'importance_normalized': 0.08407282041899186}, {'fold': 5, 'rank': 3, 'importance': 878.0, 'importance_normalized': 0.08065405107477494}, {'fold': 6, 'rank': 3, 'importance': 891.0, 'importance_normalized': 0.08175061932287365}, {'fold': 7, 'rank': 3, 'importance': 947.0, 'importance_normalized': 0.08676133760879523}, {'fold': 8, 'rank': 3, 'importance': 933.0, 'importance_normalized': 0.08543956043956044}, {'fold': 9, 'rank': 2, 'importance': 992.0, 'importance_normalized': 0.09062671295450393}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.2, 'best_rank': 4, 'mean_importance': 770.5, 'mean_importance_normalized': 0.07093525021922883, 'folds': [{'fold': 0, 'rank': 5, 'importance': 669.0, 'importance_normalized': 0.0641542002301496}, {'fold': 1, 'rank': 5, 'importance': 709.0, 'importance_normalized': 0.065532858859414}, {'fold': 2, 'rank': 4, 'importance': 739.0, 'importance_normalized': 0.06762445095168375}, {'fold': 3, 'rank': 4, 'importance': 766.0, 'importance_normalized': 0.07030102790014685}, {'fold': 4, 'rank': 4, 'importance': 804.0, 'importance_normalized': 0.07355228249931388}, {'fold': 5, 'rank': 4, 'importance': 834.0, 'importance_normalized': 0.07661216241043542}, {'fold': 6, 'rank': 4, 'importance': 793.0, 'importance_normalized': 0.07275896871272594}, {'fold': 7, 'rank': 4, 'importance': 797.0, 'importance_normalized': 0.07301878149335776}, {'fold': 8, 'rank': 4, 'importance': 799.0, 'importance_normalized': 0.07316849816849817}, {'fold': 9, 'rank': 4, 'importance': 795.0, 'importance_normalized': 0.07262927096656313}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.8, 'best_rank': 4, 'mean_importance': 735.3, 'mean_importance_normalized': 0.06773444573028936, 'folds': [{'fold': 0, 'rank': 4, 'importance': 724.0, 'importance_normalized': 0.06942846183352512}, {'fold': 1, 'rank': 4, 'importance': 741.0, 'importance_normalized': 0.06849061835659488}, {'fold': 2, 'rank': 5, 'importance': 684.0, 'importance_normalized': 0.06259150805270863}, {'fold': 3, 'rank': 5, 'importance': 693.0, 'importance_normalized': 0.06360132158590308}, {'fold': 4, 'rank': 5, 'importance': 753.0, 'importance_normalized': 0.06888665263928277}, {'fold': 5, 'rank': 5, 'importance': 752.0, 'importance_normalized': 0.06907955171780268}, {'fold': 6, 'rank': 5, 'importance': 734.0, 'importance_normalized': 0.06734562803926966}, {'fold': 7, 'rank': 5, 'importance': 747.0, 'importance_normalized': 0.0684379294548786}, {'fold': 8, 'rank': 5, 'importance': 747.0, 'importance_normalized': 0.06840659340659341}, {'fold': 9, 'rank': 5, 'importance': 778.0, 'importance_normalized': 0.07107619221633474}], 'stability_rank': 5}, {'feature': 'fractal_dimension_96', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.3, 'best_rank': 6, 'mean_importance': 618.9, 'mean_importance_normalized': 0.05701910613958653, 'folds': [{'fold': 0, 'rank': 6, 'importance': 621.0, 'importance_normalized': 0.0595512082853855}, {'fold': 1, 'rank': 6, 'importance': 630.0, 'importance_normalized': 0.05823089010074868}, {'fold': 2, 'rank': 6, 'importance': 634.0, 'importance_normalized': 0.05801610541727672}, {'fold': 3, 'rank': 6, 'importance': 624.0, 'importance_normalized': 0.05726872246696035}, {'fold': 4, 'rank': 6, 'importance': 676.0, 'importance_normalized': 0.061842466380020125}, {'fold': 5, 'rank': 6, 'importance': 649.0, 'importance_normalized': 0.0596178577990079}, {'fold': 6, 'rank': 7, 'importance': 619.0, 'importance_normalized': 0.05679420130287182}, {'fold': 7, 'rank': 6, 'importance': 583.0, 'importance_normalized': 0.053412734768666974}, {'fold': 8, 'rank': 8, 'importance': 559.0, 'importance_normalized': 0.05119047619047619}, {'fold': 9, 'rank': 6, 'importance': 594.0, 'importance_normalized': 0.05426639868445094}], 'stability_rank': 6}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.0, 'best_rank': 6, 'mean_importance': 573.7, 'mean_importance_normalized': 0.05284315573478637, 'folds': [{'fold': 0, 'rank': 7, 'importance': 550.0, 'importance_normalized': 0.052742616033755275}, {'fold': 1, 'rank': 7, 'importance': 574.0, 'importance_normalized': 0.053054810980682134}, {'fold': 2, 'rank': 7, 'importance': 573.0, 'importance_normalized': 0.052434114202049784}, {'fold': 3, 'rank': 8, 'importance': 586.0, 'importance_normalized': 0.05378120411160059}, {'fold': 4, 'rank': 7, 'importance': 571.0, 'importance_normalized': 0.05223675784466197}, {'fold': 5, 'rank': 7, 'importance': 546.0, 'importance_normalized': 0.050156163880213114}, {'fold': 6, 'rank': 6, 'importance': 629.0, 'importance_normalized': 0.05771171667125424}, {'fold': 7, 'rank': 7, 'importance': 577.0, 'importance_normalized': 0.052863032524049475}, {'fold': 8, 'rank': 6, 'importance': 578.0, 'importance_normalized': 0.05293040293040293}, {'fold': 9, 'rank': 8, 'importance': 553.0, 'importance_normalized': 0.050520738169194224}], 'stability_rank': 7}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.7, 'best_rank': 7, 'mean_importance': 553.8, 'mean_importance_normalized': 0.05099861416892071, 'folds': [{'fold': 0, 'rank': 8, 'importance': 506.0, 'importance_normalized': 0.04852320675105485}, {'fold': 1, 'rank': 8, 'importance': 553.0, 'importance_normalized': 0.05111378131065718}, {'fold': 2, 'rank': 8, 'importance': 547.0, 'importance_normalized': 0.05005490483162518}, {'fold': 3, 'rank': 7, 'importance': 602.0, 'importance_normalized': 0.0552496328928047}, {'fold': 4, 'rank': 8, 'importance': 535.0, 'importance_normalized': 0.0489433720611106}, {'fold': 5, 'rank': 8, 'importance': 546.0, 'importance_normalized': 0.050156163880213114}, {'fold': 6, 'rank': 8, 'importance': 560.0, 'importance_normalized': 0.05138086062941554}, {'fold': 7, 'rank': 8, 'importance': 535.0, 'importance_normalized': 0.04901511681172698}, {'fold': 8, 'rank': 7, 'importance': 563.0, 'importance_normalized': 0.051556776556776554}, {'fold': 9, 'rank': 7, 'importance': 591.0, 'importance_normalized': 0.0539923259638224}], 'stability_rank': 8}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 9.0, 'best_rank': 9, 'mean_importance': 503.4, 'mean_importance_normalized': 0.04636949951475201, 'folds': [{'fold': 0, 'rank': 9, 'importance': 492.0, 'importance_normalized': 0.047180667433831994}, {'fold': 1, 'rank': 9, 'importance': 516.0, 'importance_normalized': 0.04769387189204178}, {'fold': 2, 'rank': 9, 'importance': 500.0, 'importance_normalized': 0.04575402635431918}, {'fold': 3, 'rank': 9, 'importance': 498.0, 'importance_normalized': 0.045704845814977975}, {'fold': 4, 'rank': 9, 'importance': 528.0, 'importance_normalized': 0.04830299149208673}, {'fold': 5, 'rank': 9, 'importance': 457.0, 'importance_normalized': 0.041980525445526364}, {'fold': 6, 'rank': 9, 'importance': 488.0, 'importance_normalized': 0.044774749977062114}, {'fold': 7, 'rank': 9, 'importance': 492.0, 'importance_normalized': 0.045075584058634904}, {'fold': 8, 'rank': 9, 'importance': 527.0, 'importance_normalized': 0.04826007326007326}, {'fold': 9, 'rank': 9, 'importance': 536.0, 'importance_normalized': 0.04896765941896583}], 'stability_rank': 9}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 10.0, 'best_rank': 10, 'mean_importance': 441.6, 'mean_importance_normalized': 0.0406878727264993, 'folds': [{'fold': 0, 'rank': 10, 'importance': 451.0, 'importance_normalized': 0.043248945147679324}, {'fold': 1, 'rank': 10, 'importance': 460.0, 'importance_normalized': 0.042517792771975225}, {'fold': 2, 'rank': 10, 'importance': 451.0, 'importance_normalized': 0.0412701317715959}, {'fold': 3, 'rank': 10, 'importance': 470.0, 'importance_normalized': 0.04313509544787078}, {'fold': 4, 'rank': 10, 'importance': 461.0, 'importance_normalized': 0.0421736346171439}, {'fold': 5, 'rank': 10, 'importance': 425.0, 'importance_normalized': 0.039040970053279445}, {'fold': 6, 'rank': 10, 'importance': 425.0, 'importance_normalized': 0.03899440315625287}, {'fold': 7, 'rank': 10, 'importance': 412.0, 'importance_normalized': 0.037746220797068256}, {'fold': 8, 'rank': 10, 'importance': 426.0, 'importance_normalized': 0.03901098901098901}, {'fold': 9, 'rank': 10, 'importance': 435.0, 'importance_normalized': 0.03974054449113831}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 0.444737 | 1.042579 | -0.330944 | 1.049273 | 0.102153 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.263179 | 1.064991 | -0.150847 | 1.093089 | 0.060198 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 2.146178 | 4.061117 | -0.152200 | 1.133110 | 0.038351 |
| ema_trend_48_192 | negative | 2.183e+04 | 1.392747 | 3.120292 | -0.186584 | 1.154981 | 0.031901 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.520753 | 1.458726 | -0.186144 | 1.079599 | 0.065823 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 1.379462 | 2.198359 | -0.340796 | 1.081866 | 0.043051 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 308 |
| average_r | 0.385492 |
| median_r | 0.224261 |
| avg_max_favorable_r | 3.334179 |
| avg_max_adverse_r | -2.881274 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.985507 |
| avg_giveback_r | 2.948687 |
| avg_capture_ratio | -9.808038 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.985507 |
| avg_mfe_r_of_losers | 1.322560 |
| median_mfe_r_of_losers | 0.992519 |
| avg_mfe_r_before_loss | 1.322560 |
| median_mfe_r_before_loss | 0.992519 |
| loser_reached_0_5r_rate | 0.739130 |
| loser_reached_1r_rate | 0.485507 |
| loser_reached_1_5r_rate | 0.340580 |
| loser_reached_2r_rate | 0.217391 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -9.808038 |
| median_capture_ratio | 0.122135 |
| avg_giveback_r | 2.948687 |
| median_giveback_r | 2.164158 |
| avg_giveback_r_winners | 1.957864 |
| avg_giveback_r_losers | 4.169267 |
| median_giveback_r_winners | 1.608519 |
| median_giveback_r_losers | 3.198835 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.982353 |
| winner_had_mae_below_minus_0_25r_rate | 0.870588 |
| winner_had_mae_below_minus_0_5r_rate | 0.694118 |
| winner_had_mae_below_minus_1r_rate | 0.452941 |
| avg_mae_r_of_winners | -1.228067 |
| median_mae_r_of_winners | -0.922437 |
| p90_abs_mae_r_of_winners | 2.741217 |
| avg_mae_r | -2.881274 |
| median_mae_r | -1.861353 |
| q10_mae_r | -6.846268 |
| q25_mae_r | -3.786839 |
| q75_mae_r | -0.838156 |
| q90_mae_r | -0.282800 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.551948 |
| prob_final_loss | 0.448052 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 0.989362 |
| prob_mfe_ge_0_5r | 0.883117 |
| prob_final_loss_given_mfe_ge_0_5r | 0.375000 |
| prob_mfe_ge_1r | 0.762987 |
| prob_final_loss_given_mfe_ge_1r | 0.285106 |
| prob_mfe_ge_1_5r | 0.662338 |
| prob_final_loss_given_mfe_ge_1_5r | 0.230392 |
| prob_mfe_ge_2r | 0.574675 |
| prob_final_loss_given_mfe_ge_2r | 0.169492 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 11.581169 |
| median_time_to_mfe | 11.000000 |
| avg_time_to_mae | 9.724026 |
| median_time_to_mae | 8.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.077922 |
| prob_mfe_ge_0_5r_within_2_bars | 0.123377 |
| prob_mfe_ge_1r_within_4_bars | 0.103896 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.385492 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.551948 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 308 |
| counterfactual.baseline.avg_r | 0.385492 |
| counterfactual.baseline.median_r | 0.224261 |
| counterfactual.baseline.win_rate | 0.551948 |
| counterfactual.baseline.profit_factor | 1.302234 |
| counterfactual.breakeven_after_0_5r.trade_count | 308 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.103421 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.019481 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.325854 |
| counterfactual.breakeven_after_1_0r.trade_count | 308 |
| counterfactual.breakeven_after_1_0r.avg_r | 0.013260 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.136364 |
| counterfactual.breakeven_after_1_0r.profit_factor | 1.028431 |
| counterfactual.exit_at_first_0_5r.trade_count | 308 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.325486 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.957792 |
| counterfactual.exit_at_first_0_5r.profit_factor | 3.121668 |
| counterfactual.exit_at_first_1_0r.trade_count | 308 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.380086 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.850649 |
| counterfactual.exit_at_first_1_0r.profit_factor | 1.814925 |
| counterfactual.partial_50pct_at_1r.trade_count | 308 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.382789 |
| counterfactual.partial_50pct_at_1r.median_r | 0.606950 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.668831 |
| counterfactual.partial_50pct_at_1r.profit_factor | 1.508134 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 308 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.345330 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.146848 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.535714 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.272389 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 308 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.573874 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.839525 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.850649 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 2.230417 |
| counterfactual.best_policy_by_avg_r | trail_0_5r_after_1_0r |
| counterfactual.best_policy_by_profit_factor | exit_at_first_0_5r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 304 | 0.361881 | 0.197679 | 0.546053 | 3.336017 | -2.907463 | 2.974136 | 24.148026 | 1.280038 | 0.993421 | 0.881579 | 0.759868 |
| reversal | 4 | 2.179886 | 2.232444 | 1.000000 | 3.194492 | -0.890911 | 1.014606 | 24.000000 | inf | 1.000000 | 1.000000 | 1.000000 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 0 |
| gross_pnl | 1.364884 |
| net_pnl | 1.303384 |
| total_cost | 0.061500 |
| cost_to_gross_pnl | 0.045059 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1957 |
| actual_trade_count | 0 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 2.301749 |
| sharpe | 2.068715 |
| sortino | 3.237043 |
| calmar | 3.336533 |
| max_drawdown | -0.183571 |
| profit_factor | 1.112391 |
| hit_rate | 0.486929 |
| gross_pnl | 1.364884 |
| net_pnl | 1.303384 |
| total_cost | 0.061500 |
| cost_to_gross_pnl | 0.045059 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 2.255895 |
| cost_x1.annualized_return | 0.322622 |
| cost_x1.annualized_vol | 0.228309 |
| cost_x1.sharpe | 1.413092 |
| cost_x1.max_drawdown | -0.183571 |
| cost_x1.profit_factor | 1.110736 |
| cost_x1.hit_rate | 0.487096 |
| cost_x2.cumulative_return | 2.061362 |
| cost_x2.annualized_return | 0.303461 |
| cost_x2.annualized_vol | 0.228317 |
| cost_x2.sharpe | 1.329122 |
| cost_x2.max_drawdown | -0.194763 |
| cost_x2.profit_factor | 1.105016 |
| cost_x2.hit_rate | 0.486189 |
| cost_x3.cumulative_return | 1.878434 |
| cost_x3.annualized_return | 0.284576 |
| cost_x3.annualized_vol | 0.228331 |
| cost_x3.sharpe | 1.246329 |
| cost_x3.max_drawdown | -0.205802 |
| cost_x3.profit_factor | 1.099340 |
| cost_x3.hit_rate | 0.485929 |
| cost_x5.cumulative_return | 1.544668 |
| cost_x5.annualized_return | 0.247617 |
| cost_x5.annualized_vol | 0.228379 |
| cost_x5.sharpe | 1.084237 |
| cost_x5.max_drawdown | -0.227431 |
| cost_x5.profit_factor | 1.088119 |
| cost_x5.hit_rate | 0.485021 |

### Entry Delay
| Metric | Value |
| --- | --- |
| delay_1_bars.cumulative_return | 2.296276 |
| delay_1_bars.annualized_return | 0.211324 |
| delay_1_bars.annualized_vol | 0.186234 |
| delay_1_bars.sharpe | 1.134723 |
| delay_1_bars.max_drawdown | -0.150561 |
| delay_1_bars.profit_factor | 1.112724 |
| delay_1_bars.hit_rate | 0.488007 |
| delay_2_bars.cumulative_return | 2.442332 |
| delay_2_bars.annualized_return | 0.219794 |
| delay_2_bars.annualized_vol | 0.185456 |
| delay_2_bars.sharpe | 1.185152 |
| delay_2_bars.max_drawdown | -0.190706 |
| delay_2_bars.profit_factor | 1.117058 |
| delay_2_bars.hit_rate | 0.488849 |

### Walk Forward
| Metric | Value |
| --- | --- |
| fold_count | 5 |
| positive_fold_count | 3 |
| positive_fold_ratio | 0.600000 |
| min_fold_cumulative_return | 0.0 |
| median_fold_cumulative_return | 0.096482 |
| mean_fold_cumulative_return | 0.313078 |
| mean_fold_sharpe | 1.200497 |
| std_fold_sharpe | 1.326972 |
| worst_fold_max_drawdown | -0.183571 |

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
| oos_prediction.mean | -0.024345 |
| oos_prediction.std | 1.013078 |
| oos_prediction.min | -4.317915 |
| oos_prediction.max | 3.997899 |
| oos_prediction.median | 0.001709 |
| oos_prediction.q01 | -2.600664 |
| oos_prediction.q05 | -1.747562 |
| oos_prediction.q25 | -0.657381 |
| oos_prediction.q75 | 0.639076 |
| oos_prediction.q95 | 1.611474 |
| oos_prediction.q99 | 2.281949 |
| oos_prediction.skew | -0.193852 |
| oos_prediction.kurtosis | 0.308041 |
| oos_prediction.positive_rate | 0.500685 |
| oos_prediction.negative_rate | 0.499315 |
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
| 1 | vol_rolling_192 | 1.038e+03 | 0.095600 | 10 | feature_importances_ |
| 2 | atr_48 | 979.500000 | 0.090232 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 901.500000 | 0.083001 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 770.500000 | 0.070935 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 735.300000 | 0.067734 | 10 | feature_importances_ |
| 6 | fractal_dimension_96 | 618.900000 | 0.057019 | 10 | feature_importances_ |
| 7 | bollinger_bandwidth_rank_192 | 573.700000 | 0.052843 | 10 | feature_importances_ |
| 8 | atr_over_price_48 | 553.800000 | 0.050999 | 10 | feature_importances_ |
| 9 | vol_rolling_48 | 503.400000 | 0.046369 | 10 | feature_importances_ |
| 10 | atr_pct_rank_192 | 441.600000 | 0.040688 | 10 | feature_importances_ |
| 11 | mama_minus_fama_over_atr | 392.600000 | 0.036166 | 10 | feature_importances_ |
| 12 | vol_rolling_24 | 383.800000 | 0.035362 | 10 | feature_importances_ |
| 13 | close_over_bb_upper_192 | 307.200000 | 0.028292 | 10 | feature_importances_ |
| 14 | close_over_bb_mid_192 | 282.600000 | 0.026021 | 10 | feature_importances_ |
| 15 | ret_48 | 276.900000 | 0.025512 | 10 | feature_importances_ |
| 16 | bollinger_percent_b | 228.600000 | 0.021040 | 10 | feature_importances_ |
| 17 | distance_from_ema96_atr | 185.100000 | 0.017048 | 10 | feature_importances_ |
| 18 | ret_24 | 179.900000 | 0.016565 | 10 | feature_importances_ |
| 19 | roofing_filter_over_atr | 157.000000 | 0.014466 | 10 | feature_importances_ |
| 20 | atr_pct | 151.700000 | 0.013971 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 1.364884 |
| net_pnl | 1.303384 |
| total_cost | 0.061500 |
| cost_drag | 0.061500 |
| cost_to_gross_pnl | 0.045059 |
| avg_turnover | 0.014041 |
| total_turnover | 615.000000 |
| mean_abs_signal | 0.044680 |
| signal_turnover | 0.052237 |
| flat_rate | 0.955320 |
| long_rate | 0.025457 |
| short_rate | 0.019224 |
| trade_rate | 0.169315 |
| executed_trade_count | 7416 |
| avg_signal_executed | 0.033172 |
| avg_pred_prob_executed | 0.510998 |
| avg_realized_r_executed |  |

## Diagnostics
- Fold outcomes are mixed, which points to regime dependence rather than a stable cross-period edge.
- Feature drift is present in OOS inputs; the largest drifted features are atr_48, atr_over_price_48, atr_pct, vol_rolling_192, fractal_dimension_96.

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
| 0 |  | 0.157973 | 0.151573 | 0.006400 | 2.497180 | 0.014612 |  |  |  |  |
| 1 |  | 0.434935 | 0.427335 | 0.007600 | 7.270403 | 0.017352 |  |  |  |  |
| 2 |  | 0.173933 | 0.167933 | 0.006000 | 2.474943 | 0.013699 |  |  |  |  |
| 3 |  | 0.154470 | 0.146670 | 0.007800 | 2.931189 | 0.017808 |  |  |  |  |
| 4 |  | 0.022449 | 0.016449 | 0.006000 | 0.259802 | 0.013699 |  |  |  |  |
| 5 |  | -0.063756 | -0.069556 | 0.005800 | -1.594935 | 0.013242 |  |  |  |  |
| 6 |  | -0.031322 | -0.038522 | 0.007200 | -0.842035 | 0.016438 |  |  |  |  |
| 7 |  | 0.041853 | 0.037253 | 0.004600 | 0.616287 | 0.010502 |  |  |  |  |
| 8 |  | 0.180519 | 0.175719 | 0.004800 | 3.136714 | 0.010959 |  |  |  |  |
| 9 |  | 0.301062 | 0.295762 | 0.005300 | 6.811069 | 0.012100 |  |  |  |  |


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
| ETHUSD | fractal_dimension_96 | 0.601367 |
| ETHUSD | vol_rolling_96 | 0.551451 |
| ETHUSD | vol_rolling_48 | 0.474270 |
| ETHUSD | vol_rolling_24 | 0.406533 |
| ETHUSD | bollinger_bandwidth | 0.358901 |


## Drift By Family
| Family | Feature Count | Drifted Count | Drifted Ratio | Mean Abs PSI | Max Abs PSI |
| --- | --- | --- | --- | --- | --- |
| unclassified | 34 | 4 | 0.117647 | 0.124128 | 1.195042 |
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
| 47 | fractal_dimension_96 |

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
- step: fractal_dimension
  params:
    price_col: close
    window: 96
    output_col: fractal_dimension_96
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
  - fractal_dimension_96
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
