# Experiment Report: ethusd_30m_trial0041_model_lgbm_tb_calibrated_v1

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/06_model_lab/ethusd_30m_trial0041_model_lgbm_tb_calibrated_v1.yaml`
- Model kind: `lightgbm_clf`
- Symbols: `ETHUSD`
- Data source: `dukascopy_csv` at interval `30m`
- Data window: `None` to `2026-06-09 23:30:00`
- Rows / columns: `109005` rows, `130` columns
- Target: `triple_barrier` horizon `24`
- Feature count: `46`
- Runtime seed: `7`

## Pipeline Trace

### 1. Entry Point
- `runner.run_experiment` -> `src.experiments.runner.run_experiment(config_path: 'str | Path') -> 'ExperimentResult'`
- `runner._load_asset_frames` -> `src.experiments.runner._load_asset_frames(data_cfg: 'dict[str, object]')`
- `pipeline.run_experiment_pipeline` -> `src.experiments.orchestration.pipeline.run_experiment_pipeline(config_path: 'str | Path', *, load_asset_frames_fn: 'LoadAssetFramesFn', save_processed_snapshot_fn: 'SaveProcessedFn') -> 'ExperimentResult'`

```yaml
config_path: /workspace/config/experiments/foundation_alpha/ethusd_30m_trial_0041_alpha_lab/06_model_lab/ethusd_30m_trial0041_model_lgbm_tb_calibrated_v1.yaml
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
- `model[lightgbm_clf]` -> `src.models.classification.lightgbm.train_lightgbm_classifier(*args: 'object', **kwargs: 'object') -> 'object'`
- `modeling.runtime.resolve_runtime_for_model` -> `src.models.common.runtime.resolve_runtime_for_model(model_cfg: 'dict[str, Any]', model_params: 'dict[str, Any]', *, estimator_family: 'str') -> 'dict[str, Any]'`

```yaml
model:
  kind: lightgbm_clf
  params:
    n_estimators: 500
    learning_rate: 0.04
    max_depth: 5
    num_leaves: 15
    min_child_samples: 250
    subsample: 0.9
    colsample_bytree: 0.75
    reg_alpha: 0.02
    reg_lambda: 1.8
    random_state: 7
    n_jobs: 1
    verbosity: -1
  outputs:
    pred_prob_col: pred_prob
    pred_is_oos_col: pred_is_oos
  preprocessing:
    scaler: none
  calibration:
    method: sigmoid
    fraction: 0.2
    min_rows: 200
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
    kind: triple_barrier
    price_col: close
    open_col: open
    high_col: high
    low_col: low
    returns_col: close_ret
    volatility_col: null
    vol_window: 48
    max_holding: 24
    upper_mult: 1.4
    lower_mult: 1.0
    min_vol: 1.0e-06
    neutral_label: drop
    tie_break: closest_to_open
    entry_price_mode: next_open
    label_mode: binary
    add_r_multiple: false
    label_col: tb_label_h24
    event_ret_col: tb_event_ret_h24
    fwd_col: tb_event_ret_h24
    hit_step_col: tb_hit_step_h24
    hit_type_col: tb_hit_type_h24
    upper_barrier_col: tb_upper_h24
    lower_barrier_col: tb_lower_h24
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
  pred_raw_prob_col: pred_prob_raw
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
- `signal[probability_threshold]` -> `src.signals.probabilistic_signal.probabilistic_signal(df: 'pd.DataFrame', prob_col: 'str', signal_col: 'str | None' = None, upper: 'float' = 0.55, lower: 'float' = 0.45, upper_exit: 'float | None' = None, lower_exit: 'float | None' = None, mode: 'str' = 'long_short_hold', base_signal_col: 'str | None' = None) -> 'pd.Series'`  
  params={'prob_col': 'pred_prob', 'signal_col': 'signal_tb_probability', 'upper': 0.56, 'lower': 0.44, 'mode': 'long_short'}

```yaml
signals:
  kind: probability_threshold
  params:
    prob_col: pred_prob
    signal_col: signal_tb_probability
    upper: 0.56
    lower: 0.44
    mode: long_short
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
  signal_col: signal_tb_probability
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
  allow_short: false
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
| cumulative_return | -0.611406 |
| annualized_return | -0.314830 |
| annualized_vol | 0.650844 |
| sharpe | -0.483725 |
| sortino | -0.688854 |
| calmar | -0.354494 |
| max_drawdown | -0.888111 |
| profit_factor | 0.993488 |
| hit_rate | 0.492098 |
| avg_turnover | 0.002489 |
| total_turnover | 109.000000 |
| gross_pnl | -0.404916 |
| net_pnl | -0.415816 |
| total_cost | 0.010900 |
| cost_drag | 0.010900 |
| cost_to_gross_pnl | 0.026919 |
| flat_rate | 0.012032 |
| long_rate | 0.0 |
| short_rate | 0.987968 |
| trade_count | 55 |
| average_r | -1.585347 |
| median_r | 0.642463 |
| avg_max_favorable_r | 7.505086 |
| avg_max_adverse_r | -11.315726 |
| loser_was_positive_rate | 1.000000 |
| avg_giveback_r | 9.090433 |
| avg_capture_ratio | -1.670304 |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.987968 |
| signal_turnover | 0.010205 |
| long_rate | 0.0 |
| short_rate | 0.987968 |
| flat_rate | 0.012032 |
| executed_trade_count | 42484 |
| trade_rate | 0.969954 |
| avg_signal_executed | -0.995857 |
| avg_pred_prob_executed | 0.408178 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43653 |
| classification.positive_rate | 0.410739 |
| classification.accuracy | 0.589238 |
| classification.brier | 0.242075 |
| classification.roc_auc | 0.503385 |
| classification.log_loss | 0.677214 |
| regression.evaluation_rows | 0 |
| regression.mae |  |
| regression.rmse |  |
| regression.mse |  |
| regression.r2 |  |
| regression.correlation |  |
| regression.directional_accuracy |  |
| regression.mean_prediction |  |
| regression.mean_target |  |
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
| prediction_distribution.mean | 0.408639 |
| prediction_distribution.std | 0.010958 |
| prediction_distribution.min | 0.332486 |
| prediction_distribution.max | 0.507175 |
| prediction_distribution.median | 0.407984 |
| prediction_distribution.q01 | 0.379924 |
| prediction_distribution.q05 | 0.392599 |
| prediction_distribution.q25 | 0.402759 |
| prediction_distribution.q75 | 0.417229 |
| prediction_distribution.q95 | 0.420634 |
| prediction_distribution.q99 | 0.442610 |
| prediction_distribution.skew | 0.441641 |
| prediction_distribution.kurtosis | 5.971526 |
| prediction_distribution.positive_rate | 1.000000 |
| prediction_distribution.negative_rate | 0.0 |
| prediction_distribution.zero_rate | 0.0 |
| target_distribution.rows | 43653 |
| target_distribution.mean | 0.410739 |
| target_distribution.std | 0.491974 |
| target_distribution.min | 0.0 |
| target_distribution.max | 1.000000 |
| target_distribution.median | 0.0 |
| target_distribution.q01 | 0.0 |
| target_distribution.q05 | 0.0 |
| target_distribution.q25 | 0.0 |
| target_distribution.q75 | 1.000000 |
| target_distribution.q95 | 1.000000 |
| target_distribution.q99 | 1.000000 |
| target_distribution.skew | 0.362885 |
| target_distribution.kurtosis | -1.868400 |
| target_distribution.positive_rate | 0.410739 |
| target_distribution.negative_rate | 0.0 |
| target_distribution.zero_rate | 0.589261 |
| probability_distribution.rows | 43800 |
| probability_distribution.mean | 0.408639 |
| probability_distribution.std | 0.010958 |
| probability_distribution.min | 0.332486 |
| probability_distribution.max | 0.507175 |
| probability_distribution.median | 0.407984 |
| probability_distribution.q01 | 0.379924 |
| probability_distribution.q05 | 0.392599 |
| probability_distribution.q25 | 0.402759 |
| probability_distribution.q75 | 0.417229 |
| probability_distribution.q95 | 0.420634 |
| probability_distribution.q99 | 0.442610 |
| probability_distribution.skew | 0.441641 |
| probability_distribution.kurtosis | 5.971526 |
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


## Forecast Baselines
| Name | Cum Return | Ann Return | Ann Vol | Sharpe | Sortino | Calmar | Max DD | Profit Factor | Hit Rate | Turnover | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| model_strategy | -0.611406 | -0.314830 | 0.650844 | -0.483725 | -0.688854 | -0.354494 | -0.888111 | 0.993488 | 0.492098 | 109.000000 | 0.026919 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | -0.089284 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000224 |
| random_sign_same_rate | -0.738568 | -0.415286 | 0.607076 | -0.684076 | -0.971954 | -0.468819 | -0.885813 | 0.983860 | 0.486132 | 663.000000 | 0.081387 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | -0.240522 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.789225 |
| simple_trend | -0.867002 | -0.553792 | 0.665797 | -0.831772 | -1.181822 | -0.608132 | -0.910644 | 0.978047 | 0.491683 | 1.545e+03 | 0.118038 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | -0.073667 |
| mean_fold_return | -0.037512 |
| fold_return_std | 0.357024 |
| worst_fold_return | -0.411932 |
| best_fold_return | 0.735956 |
| worst_3_fold_average_return | -0.372096 |
| profitable_fold_count | 3.000000 |
| profitable_fold_rate | 0.300000 |
| median_fold_sharpe | -0.463951 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.4, 'best_rank': 1, 'mean_importance': 325.7, 'mean_importance_normalized': 0.05151586322637203, 'folds': [{'fold': 0, 'rank': 2, 'importance': 295.0, 'importance_normalized': 0.048784521250206714}, {'fold': 1, 'rank': 1, 'importance': 295.0, 'importance_normalized': 0.048155403199477635}, {'fold': 2, 'rank': 1, 'importance': 310.0, 'importance_normalized': 0.05073649754500818}, {'fold': 3, 'rank': 2, 'importance': 277.0, 'importance_normalized': 0.04451944712311154}, {'fold': 4, 'rank': 1, 'importance': 371.0, 'importance_normalized': 0.05956968529222865}, {'fold': 5, 'rank': 1, 'importance': 335.0, 'importance_normalized': 0.05368589743589743}, {'fold': 6, 'rank': 2, 'importance': 351.0, 'importance_normalized': 0.055171329770512416}, {'fold': 7, 'rank': 1, 'importance': 327.0, 'importance_normalized': 0.04990842490842491}, {'fold': 8, 'rank': 2, 'importance': 341.0, 'importance_normalized': 0.05077427039904705}, {'fold': 9, 'rank': 1, 'importance': 355.0, 'importance_normalized': 0.05385315533980582}], 'stability_rank': 1}, {'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.7, 'best_rank': 1, 'mean_importance': 309.0, 'mean_importance_normalized': 0.04887786982698912, 'folds': [{'fold': 0, 'rank': 1, 'importance': 302.0, 'importance_normalized': 0.049942120059533655}, {'fold': 1, 'rank': 2, 'importance': 281.0, 'importance_normalized': 0.045870062030688864}, {'fold': 2, 'rank': 2, 'importance': 292.0, 'importance_normalized': 0.04779050736497545}, {'fold': 3, 'rank': 1, 'importance': 286.0, 'importance_normalized': 0.045965927354548373}, {'fold': 4, 'rank': 2, 'importance': 307.0, 'importance_normalized': 0.04929351316634554}, {'fold': 5, 'rank': 3, 'importance': 295.0, 'importance_normalized': 0.047275641025641024}, {'fold': 6, 'rank': 1, 'importance': 367.0, 'importance_normalized': 0.05768626218170387}, {'fold': 7, 'rank': 2, 'importance': 310.0, 'importance_normalized': 0.04731379731379731}, {'fold': 8, 'rank': 1, 'importance': 344.0, 'importance_normalized': 0.05122096486003574}, {'fold': 9, 'rank': 2, 'importance': 306.0, 'importance_normalized': 0.04641990291262136}], 'stability_rank': 2}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.1, 'best_rank': 2, 'mean_importance': 270.8, 'mean_importance_normalized': 0.042846797743092316, 'folds': [{'fold': 0, 'rank': 7, 'importance': 251.0, 'importance_normalized': 0.041508185877294525}, {'fold': 1, 'rank': 3, 'importance': 276.0, 'importance_normalized': 0.04505386875612145}, {'fold': 2, 'rank': 4, 'importance': 252.0, 'importance_normalized': 0.041243862520458266}, {'fold': 3, 'rank': 7, 'importance': 223.0, 'importance_normalized': 0.035840565734490515}, {'fold': 4, 'rank': 3, 'importance': 291.0, 'importance_normalized': 0.04672447013487476}, {'fold': 5, 'rank': 2, 'importance': 296.0, 'importance_normalized': 0.047435897435897434}, {'fold': 6, 'rank': 3, 'importance': 271.0, 'importance_normalized': 0.04259666771455517}, {'fold': 7, 'rank': 3, 'importance': 285.0, 'importance_normalized': 0.043498168498168496}, {'fold': 8, 'rank': 3, 'importance': 300.0, 'importance_normalized': 0.04466944609886837}, {'fold': 9, 'rank': 6, 'importance': 263.0, 'importance_normalized': 0.03989684466019418}], 'stability_rank': 3}, {'feature': 'mama_minus_fama_over_atr', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.7, 'best_rank': 3, 'mean_importance': 260.2, 'mean_importance_normalized': 0.04121451128702246, 'folds': [{'fold': 0, 'rank': 3, 'importance': 270.0, 'importance_normalized': 0.04465023978832479}, {'fold': 1, 'rank': 4, 'importance': 268.0, 'importance_normalized': 0.04374795951681358}, {'fold': 2, 'rank': 5, 'importance': 247.0, 'importance_normalized': 0.04042553191489362}, {'fold': 3, 'rank': 3, 'importance': 265.0, 'importance_normalized': 0.04259080681452909}, {'fold': 4, 'rank': 5, 'importance': 248.0, 'importance_normalized': 0.03982016698779704}, {'fold': 5, 'rank': 5, 'importance': 251.0, 'importance_normalized': 0.04022435897435898}, {'fold': 6, 'rank': 4, 'importance': 258.0, 'importance_normalized': 0.04055328513046212}, {'fold': 7, 'rank': 4, 'importance': 278.0, 'importance_normalized': 0.04242979242979243}, {'fold': 8, 'rank': 7, 'importance': 259.0, 'importance_normalized': 0.0385646217986897}, {'fold': 9, 'rank': 7, 'importance': 258.0, 'importance_normalized': 0.03913834951456311}], 'stability_rank': 4}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.0, 'best_rank': 3, 'mean_importance': 248.6, 'mean_importance_normalized': 0.03940121096840567, 'folds': [{'fold': 0, 'rank': 4, 'importance': 268.0, 'importance_normalized': 0.044319497271374235}, {'fold': 1, 'rank': 9, 'importance': 215.0, 'importance_normalized': 0.03509631080639895}, {'fold': 2, 'rank': 3, 'importance': 254.0, 'importance_normalized': 0.04157119476268412}, {'fold': 3, 'rank': 4, 'importance': 261.0, 'importance_normalized': 0.041947926711668276}, {'fold': 4, 'rank': 4, 'importance': 266.0, 'importance_normalized': 0.04271034039820167}, {'fold': 5, 'rank': 4, 'importance': 262.0, 'importance_normalized': 0.041987179487179484}, {'fold': 6, 'rank': 7, 'importance': 226.0, 'importance_normalized': 0.03552342030807922}, {'fold': 7, 'rank': 11, 'importance': 217.0, 'importance_normalized': 0.03311965811965812}, {'fold': 8, 'rank': 9, 'importance': 247.0, 'importance_normalized': 0.03677784395473496}, {'fold': 9, 'rank': 5, 'importance': 270.0, 'importance_normalized': 0.04095873786407767}], 'stability_rank': 5}, {'feature': 'vol_rolling_24', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.4, 'best_rank': 4, 'mean_importance': 244.7, 'mean_importance_normalized': 0.03871214543049959, 'folds': [{'fold': 0, 'rank': 5, 'importance': 267.0, 'importance_normalized': 0.04415412601289896}, {'fold': 1, 'rank': 8, 'importance': 216.0, 'importance_normalized': 0.03525954946131244}, {'fold': 2, 'rank': 9, 'importance': 232.0, 'importance_normalized': 0.037970540098199675}, {'fold': 3, 'rank': 5, 'importance': 238.0, 'importance_normalized': 0.03825136612021858}, {'fold': 4, 'rank': 8, 'importance': 217.0, 'importance_normalized': 0.03484264611432242}, {'fold': 5, 'rank': 6, 'importance': 249.0, 'importance_normalized': 0.03990384615384615}, {'fold': 6, 'rank': 5, 'importance': 245.0, 'importance_normalized': 0.03850990254636907}, {'fold': 7, 'rank': 6, 'importance': 252.0, 'importance_normalized': 0.038461538461538464}, {'fold': 8, 'rank': 4, 'importance': 280.0, 'importance_normalized': 0.04169148302561048}, {'fold': 9, 'rank': 8, 'importance': 251.0, 'importance_normalized': 0.03807645631067961}], 'stability_rank': 6}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.9, 'best_rank': 5, 'mean_importance': 241.5, 'mean_importance_normalized': 0.03825439459508678, 'folds': [{'fold': 0, 'rank': 6, 'importance': 251.0, 'importance_normalized': 0.041508185877294525}, {'fold': 1, 'rank': 5, 'importance': 260.0, 'importance_normalized': 0.042442050277505715}, {'fold': 2, 'rank': 6, 'importance': 243.0, 'importance_normalized': 0.0397708674304419}, {'fold': 3, 'rank': 6, 'importance': 223.0, 'importance_normalized': 0.035840565734490515}, {'fold': 4, 'rank': 6, 'importance': 239.0, 'importance_normalized': 0.03837508028259473}, {'fold': 5, 'rank': 7, 'importance': 244.0, 'importance_normalized': 0.0391025641025641}, {'fold': 6, 'rank': 10, 'importance': 207.0, 'importance_normalized': 0.03253693806978938}, {'fold': 7, 'rank': 8, 'importance': 243.0, 'importance_normalized': 0.03708791208791209}, {'fold': 8, 'rank': 6, 'importance': 260.0, 'importance_normalized': 0.03871351995235259}, {'fold': 9, 'rank': 9, 'importance': 245.0, 'importance_normalized': 0.03716626213592233}], 'stability_rank': 7}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.7, 'best_rank': 3, 'mean_importance': 234.1, 'mean_importance_normalized': 0.03701300584168013, 'folds': [{'fold': 0, 'rank': 8, 'importance': 249.0, 'importance_normalized': 0.04117744336034397}, {'fold': 1, 'rank': 10, 'importance': 210.0, 'importance_normalized': 0.034280117531831536}, {'fold': 2, 'rank': 7, 'importance': 240.0, 'importance_normalized': 0.03927986906710311}, {'fold': 3, 'rank': 9, 'importance': 212.0, 'importance_normalized': 0.03407264545162327}, {'fold': 4, 'rank': 7, 'importance': 223.0, 'importance_normalized': 0.035806037251123954}, {'fold': 5, 'rank': 9, 'importance': 211.0, 'importance_normalized': 0.03381410256410256}, {'fold': 6, 'rank': 9, 'importance': 209.0, 'importance_normalized': 0.03285130462118831}, {'fold': 7, 'rank': 10, 'importance': 235.0, 'importance_normalized': 0.035866910866910864}, {'fold': 8, 'rank': 5, 'importance': 270.0, 'importance_normalized': 0.04020250148898154}, {'fold': 9, 'rank': 3, 'importance': 282.0, 'importance_normalized': 0.042779126213592235}], 'stability_rank': 8}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.9, 'best_rank': 4, 'mean_importance': 230.5, 'mean_importance_normalized': 0.03646508836013729, 'folds': [{'fold': 0, 'rank': 9, 'importance': 230.0, 'importance_normalized': 0.03803538944931371}, {'fold': 1, 'rank': 6, 'importance': 226.0, 'importance_normalized': 0.036891936010447275}, {'fold': 2, 'rank': 8, 'importance': 232.0, 'importance_normalized': 0.037970540098199675}, {'fold': 3, 'rank': 10, 'importance': 206.0, 'importance_normalized': 0.03310832529733205}, {'fold': 4, 'rank': 9, 'importance': 211.0, 'importance_normalized': 0.033879254977520874}, {'fold': 5, 'rank': 8, 'importance': 229.0, 'importance_normalized': 0.03669871794871795}, {'fold': 6, 'rank': 8, 'importance': 210.0, 'importance_normalized': 0.03300848789688777}, {'fold': 7, 'rank': 5, 'importance': 259.0, 'importance_normalized': 0.03952991452991453}, {'fold': 8, 'rank': 12, 'importance': 223.0, 'importance_normalized': 0.03320428826682549}, {'fold': 9, 'rank': 4, 'importance': 279.0, 'importance_normalized': 0.042324029126213594}], 'stability_rank': 9}, {'feature': 'distance_from_ema96_atr', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 10.0, 'best_rank': 6, 'mean_importance': 213.2, 'mean_importance_normalized': 0.03364254888748965, 'folds': [{'fold': 0, 'rank': 10, 'importance': 199.0, 'importance_normalized': 0.03290888043658012}, {'fold': 1, 'rank': 7, 'importance': 220.0, 'importance_normalized': 0.03591250408096637}, {'fold': 2, 'rank': 16, 'importance': 162.0, 'importance_normalized': 0.026513911620294598}, {'fold': 3, 'rank': 8, 'importance': 220.0, 'importance_normalized': 0.0353584056573449}, {'fold': 4, 'rank': 16, 'importance': 171.0, 'importance_normalized': 0.02745664739884393}, {'fold': 5, 'rank': 12, 'importance': 175.0, 'importance_normalized': 0.028044871794871796}, {'fold': 6, 'rank': 6, 'importance': 238.0, 'importance_normalized': 0.03740961961647281}, {'fold': 7, 'rank': 7, 'importance': 245.0, 'importance_normalized': 0.03739316239316239}, {'fold': 8, 'rank': 8, 'importance': 259.0, 'importance_normalized': 0.0385646217986897}, {'fold': 9, 'rank': 10, 'importance': 243.0, 'importance_normalized': 0.0368628640776699}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | -0.697389 | -1.798876 | -0.708826 | 0.922749 | 0.003131 |
| atr_pct_rank_192 | medium | 2.167e+04 | -0.716510 | -1.077647 | -0.863472 | 0.966491 | 0.005496 |
| atr_pct_rank_192 | high | 8.547e+03 | 3.263596 | 19.070844 | -0.228800 | 1.093236 | 0.001367 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | -0.182207 | -0.253127 | -0.501227 | 1.000318 | 0.385523 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | -0.531927 | -0.642013 | -0.838390 | 0.987107 | 0.013092 |
| ema_trend_48_192 | negative | 2.183e+04 | 0.437398 | 0.476044 | -0.559805 | 1.020584 | 0.010092 |
| ema_trend_48_192 | positive | 2.197e+04 | -0.730793 | -1.105751 | -0.806918 | 0.964581 | 0.003938 |
| range_to_atr | calm | 2.190e+04 | -0.414105 | -1.380192 | -0.582025 | 0.967118 | 0.012480 |
| range_to_atr | shock | 2.190e+04 | -0.343266 | -0.326856 | -0.767897 | 1.001177 | 0.102835 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| train_rows_dropped_missing | 3820 |
| train_rows_not_labeled | 771 |
| train_rows_without_fit | 4591 |
| test_rows_missing_features | 0 |
| test_rows_not_candidates | 0 |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Label Distribution
| Metric | Value |
| --- | --- |
| oos_evaluation.labeled_rows | 43653 |
| oos_evaluation.class_counts.0 | 25723 |
| oos_evaluation.class_counts.1 | 17930 |
| oos_evaluation.positive_rate | 0.410739 |
| oos_evaluation.negative_rate | 0.589261 |
| train.labeled_rows | 433205 |
| train.class_counts.0 | 253543 |
| train.class_counts.1 | 179662 |
| train.positive_rate | 0.414727 |
| train.negative_rate | 0.585273 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 55 |
| average_r | -1.585347 |
| median_r | 0.642463 |
| avg_max_favorable_r | 7.505086 |
| avg_max_adverse_r | -11.315726 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 1.000000 |
| avg_giveback_r | 9.090433 |
| avg_capture_ratio | -1.670304 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 1.000000 |
| avg_mfe_r_of_losers | 3.885492 |
| median_mfe_r_of_losers | 1.602299 |
| avg_mfe_r_before_loss | 3.885492 |
| median_mfe_r_before_loss | 1.602299 |
| loser_reached_0_5r_rate | 0.791667 |
| loser_reached_1r_rate | 0.750000 |
| loser_reached_1_5r_rate | 0.541667 |
| loser_reached_2r_rate | 0.416667 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -1.670304 |
| median_capture_ratio | 0.129370 |
| avg_giveback_r | 9.090433 |
| median_giveback_r | 2.600870 |
| avg_giveback_r_winners | 3.699392 |
| avg_giveback_r_losers | 16.053861 |
| median_giveback_r_winners | 2.179308 |
| median_giveback_r_losers | 5.539607 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.967742 |
| winner_had_mae_below_minus_0_25r_rate | 0.806452 |
| winner_had_mae_below_minus_0_5r_rate | 0.677419 |
| winner_had_mae_below_minus_1r_rate | 0.516129 |
| avg_mae_r_of_winners | -4.014035 |
| median_mae_r_of_winners | -1.394731 |
| p90_abs_mae_r_of_winners | 4.968880 |
| avg_mae_r | -11.315726 |
| median_mae_r | -3.638023 |
| q10_mae_r | -19.277463 |
| q25_mae_r | -5.447781 |
| q75_mae_r | -0.808873 |
| q90_mae_r | -0.194840 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.563636 |
| prob_final_loss | 0.436364 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 0.937500 |
| prob_mfe_ge_0_5r | 0.909091 |
| prob_final_loss_given_mfe_ge_0_5r | 0.380000 |
| prob_mfe_ge_1r | 0.890909 |
| prob_final_loss_given_mfe_ge_1r | 0.367347 |
| prob_mfe_ge_1_5r | 0.781818 |
| prob_final_loss_given_mfe_ge_1_5r | 0.302326 |
| prob_mfe_ge_2r | 0.690909 |
| prob_final_loss_given_mfe_ge_2r | 0.263158 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 303.563636 |
| median_time_to_mfe | 19.000000 |
| avg_time_to_mae | 426.018182 |
| median_time_to_mae | 15.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.036364 |
| prob_mfe_ge_0_5r_within_2_bars | 0.036364 |
| prob_mfe_ge_1r_within_4_bars | 0.145455 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | -1.585347 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.563636 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 55 |
| counterfactual.baseline.avg_r | -1.585347 |
| counterfactual.baseline.median_r | 0.642463 |
| counterfactual.baseline.win_rate | 0.563636 |
| counterfactual.baseline.profit_factor | 0.701432 |
| counterfactual.breakeven_after_0_5r.trade_count | 55 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.189261 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.018182 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.350713 |
| counterfactual.breakeven_after_1_0r.trade_count | 55 |
| counterfactual.breakeven_after_1_0r.avg_r | 0.120662 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.127273 |
| counterfactual.breakeven_after_1_0r.profit_factor | 1.336275 |
| counterfactual.exit_at_first_0_5r.trade_count | 55 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.172146 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.927273 |
| counterfactual.exit_at_first_0_5r.profit_factor | 1.590574 |
| counterfactual.exit_at_first_1_0r.trade_count | 55 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.532090 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.890909 |
| counterfactual.exit_at_first_1_0r.profit_factor | 2.482895 |
| counterfactual.partial_50pct_at_1r.trade_count | 55 |
| counterfactual.partial_50pct_at_1r.avg_r | -0.526628 |
| counterfactual.partial_50pct_at_1r.median_r | 0.821231 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.618182 |
| counterfactual.partial_50pct_at_1r.profit_factor | 0.803881 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 55 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 1.148590 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.240166 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.527273 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.480610 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 55 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.793478 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.806108 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.890909 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 3.211363 |
| counterfactual.best_policy_by_avg_r | time_exit_after_4_bars_if_mfe_lt_0_3r |
| counterfactual.best_policy_by_profit_factor | trail_0_5r_after_1_0r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 55 | -1.585347 | 0.642463 | 0.563636 | 7.505086 | -11.315726 | 9.090433 | 772.436364 | 0.701432 | 1.000000 | 0.909091 | 0.890909 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 0 |
| gross_pnl | -0.404916 |
| net_pnl | -0.415816 |
| total_cost | 0.010900 |
| cost_to_gross_pnl | 0.026919 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 43273 |
| actual_trade_count | 0 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | -0.611406 |
| sharpe | -0.483725 |
| sortino | -0.688854 |
| calmar | -0.354494 |
| max_drawdown | -0.888111 |
| profit_factor | 0.993488 |
| hit_rate | 0.492098 |
| gross_pnl | -0.404916 |
| net_pnl | -0.415816 |
| total_cost | 0.010900 |
| cost_to_gross_pnl | 0.026919 |


## Target Diagnostics
| Metric | Value |
| --- | --- |
| kind | triple_barrier |
| label_mode | binary |
| max_holding | 24 |
| upper_mult | 1.400000 |
| lower_mult | 1.000000 |
| neutral_label | drop |
| tie_break | closest_to_open |
| entry_price_mode | next_open |
| vol_window | 48 |
| min_vol | 1.000e-06 |
| labeled_rows | 108637 |
| positive_rate | 0.412355 |
| upper_barrier_count | 44797 |
| lower_barrier_count | 63840 |
| neutral_count | 344 |
| unavailable_tail_count | 24 |
| avg_hit_step | 3.032024 |
| median_hit_step | 2.000000 |
| meta_labeling | false |
| candidate_rows |  |
| candidate_col |  |
| add_r_multiple | false |
| r_col |  |
| oriented_r_col |  |


## Feature Importance
| Rank | Feature | Mean Importance | Mean Importance Normalized | Fold Count | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | bollinger_bandwidth | 325.700000 | 0.051516 | 10 | feature_importances_ |
| 2 | atr_48 | 309.000000 | 0.048878 | 10 | feature_importances_ |
| 3 | vol_rolling_48 | 270.800000 | 0.042847 | 10 | feature_importances_ |
| 4 | mama_minus_fama_over_atr | 260.200000 | 0.041215 | 10 | feature_importances_ |
| 5 | vol_rolling_192 | 248.600000 | 0.039401 | 10 | feature_importances_ |
| 6 | vol_rolling_24 | 244.700000 | 0.038712 | 10 | feature_importances_ |
| 7 | bollinger_bandwidth_rank_192 | 241.500000 | 0.038254 | 10 | feature_importances_ |
| 8 | vol_rolling_96 | 234.100000 | 0.037013 | 10 | feature_importances_ |
| 9 | ema_trend_48_192 | 230.500000 | 0.036465 | 10 | feature_importances_ |
| 10 | distance_from_ema96_atr | 213.200000 | 0.033643 | 10 | feature_importances_ |
| 11 | close_over_bb_upper_192 | 192.100000 | 0.030384 | 10 | feature_importances_ |
| 12 | ret_24 | 186.800000 | 0.029556 | 10 | feature_importances_ |
| 13 | atr_pct_rank_192 | 186.400000 | 0.029417 | 10 | feature_importances_ |
| 14 | ret_48 | 183.200000 | 0.028911 | 10 | feature_importances_ |
| 15 | atr_over_price_48 | 180.600000 | 0.028575 | 10 | feature_importances_ |
| 16 | close_over_bb_mid_192 | 170.400000 | 0.026945 | 10 | feature_importances_ |
| 17 | bollinger_percent_b | 167.900000 | 0.026465 | 10 | feature_importances_ |
| 18 | roofing_filter_over_atr | 163.600000 | 0.025870 | 10 | feature_importances_ |
| 19 | dominant_cycle_phase_normalized | 132.000000 | 0.020917 | 10 | feature_importances_ |
| 20 | frama_slope_over_atr | 127.800000 | 0.020252 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | -0.404916 |
| net_pnl | -0.415816 |
| total_cost | 0.010900 |
| cost_drag | 0.010900 |
| cost_to_gross_pnl | 0.026919 |
| avg_turnover | 0.002489 |
| total_turnover | 109.000000 |
| mean_abs_signal | 0.987968 |
| signal_turnover | 0.010205 |
| flat_rate | 0.012032 |
| long_rate | 0.0 |
| short_rate | 0.987968 |
| trade_rate | 0.969954 |
| executed_trade_count | 42484 |
| avg_signal_executed | -0.995857 |
| avg_pred_prob_executed | 0.408178 |
| avg_realized_r_executed |  |

## Diagnostics
- Gross PnL is non-positive, so the dominant problem is missing edge rather than execution drag.
- Hit rate is close to coin-flip while gross PnL is negative, which is consistent with weak or noisy signal quality.
- Turnover is already low, so more cost tuning alone is unlikely to rescue the run.
- The policy spends most of its time near the configured signal cap, so it is saturating instead of sizing dynamically.
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

### Label Distribution Chart
![Label Distribution Chart](report_assets/label_distribution.png)

### Prediction Coverage By Fold
![Prediction Coverage By Fold](report_assets/prediction_coverage_by_fold.png)


## Fold Breakdown
| Fold | Rows | Gross PnL | Net PnL | Cost | Sharpe | Avg Turnover | Mean Reward | Mean Abs Signal | Signal Turnover | Flat Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 |  | 0.644121 | 0.644021 | 0.000100 | 9.378181 | 0.000228 |  |  |  |  |
| 1 |  | -0.387143 | -0.387243 | 0.000100 | -0.860395 | 0.000228 |  |  |  |  |
| 2 |  | 0.148687 | 0.138187 | 0.010500 | 0.620447 | 0.023973 |  |  |  |  |
| 3 |  | -0.256494 | -0.256594 | 0.000100 | -1.296798 | 0.000228 |  |  |  |  |
| 4 |  | -0.031038 | -0.031138 | 0.000100 | -0.445405 | 0.000228 |  |  |  |  |
| 5 |  | -0.003204 | -0.003304 | 0.000100 | -0.207220 | 0.000228 |  |  |  |  |
| 6 |  | -0.334299 | -0.334399 | 0.000100 | -1.745519 | 0.000228 |  |  |  |  |
| 7 |  | -0.486850 | -0.487150 | 0.000300 | -1.487448 | 0.000685 |  |  |  |  |
| 8 |  | -0.041171 | -0.041271 | 0.000100 | -0.482497 | 0.000228 |  |  |  |  |
| 9 |  | 0.344969 | 0.344869 | 0.000100 | 3.288729 | 0.000228 |  |  |  |  |


## Model Fold Diagnostics
| Fold | Train Raw | Train Used | Train Missing Features | Train Not Labeled | Train Without Fit | Test Rows | Pred Rows | Test Missing Features | Test Not Candidates | Test Without Prediction | Train Feature Missing | Test Feature Missing | Eval Rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 35016 | 34617 | 382 | 17 | 399 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4379 |
| 1 | 39396 | 38996 | 382 | 18 | 400 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4379 |
| 2 | 43752 | 43351 | 382 | 19 | 401 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4360 |
| 3 | 48108 | 47689 | 382 | 37 | 419 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4349 |
| 4 | 52464 | 52014 | 382 | 68 | 450 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4369 |
| 5 | 56820 | 56359 | 382 | 79 | 461 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4332 |
| 6 | 61176 | 60667 | 382 | 127 | 509 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4377 |
| 7 | 65532 | 65020 | 382 | 130 | 512 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4374 |
| 8 | 69888 | 69370 | 382 | 136 | 518 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4376 |
| 9 | 74244 | 73722 | 382 | 140 | 522 | 4380 | 4380 | 0 | 0 | 0 | 382 | 0 | 4358 |


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
  kind: lightgbm_clf
  params:
    n_estimators: 500
    learning_rate: 0.04
    max_depth: 5
    num_leaves: 15
    min_child_samples: 250
    subsample: 0.9
    colsample_bytree: 0.75
    reg_alpha: 0.02
    reg_lambda: 1.8
    random_state: 7
    n_jobs: 1
    verbosity: -1
  outputs:
    pred_prob_col: pred_prob
    pred_is_oos_col: pred_is_oos
  preprocessing:
    scaler: none
  calibration:
    method: sigmoid
    fraction: 0.2
    min_rows: 200
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
    kind: triple_barrier
    price_col: close
    open_col: open
    high_col: high
    low_col: low
    returns_col: close_ret
    volatility_col: null
    vol_window: 48
    max_holding: 24
    upper_mult: 1.4
    lower_mult: 1.0
    min_vol: 1.0e-06
    neutral_label: drop
    tie_break: closest_to_open
    entry_price_mode: next_open
    label_mode: binary
    add_r_multiple: false
    label_col: tb_label_h24
    event_ret_col: tb_event_ret_h24
    fwd_col: tb_event_ret_h24
    hit_step_col: tb_hit_step_h24
    hit_type_col: tb_hit_type_h24
    upper_barrier_col: tb_upper_h24
    lower_barrier_col: tb_lower_h24
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
  pred_raw_prob_col: pred_prob_raw
  pred_ret_col: pred_ret
  pred_is_oos_col: pred_is_oos
  returns_input_col: null
  signal_col: null
  action_col: null
signals:
  kind: probability_threshold
  params:
    prob_col: pred_prob
    signal_col: signal_tb_probability
    upper: 0.56
    lower: 0.44
    mode: long_short
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
  signal_col: signal_tb_probability
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
  allow_short: false
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
- `label_distribution`: `label_distribution.csv`
- `prediction_diagnostics`: `prediction_diagnostics.json`
- `missing_value_diagnostics`: `missing_value_diagnostics.json`
- `fold_model_summary`: `fold_model_summary.csv`
- `stage_tails`: `stage_tails.json`
- `diagnostics_fold_backtest_diagnostics`: `artifacts/diagnostics/fold_backtest_diagnostics.csv`
- `diagnostics_forecast_alpha_diagnostics_summary`: `artifacts/diagnostics/forecast_alpha_diagnostics_summary.json`
- `diagnostics_forecast_baselines`: `artifacts/diagnostics/forecast_baselines.csv`
- `diagnostics_lab_feature_diagnostics_ETHUSD`: `artifacts/diagnostics/lab_feature_diagnostics_ETHUSD.json`
- `diagnostics_regime_performance`: `artifacts/diagnostics/regime_performance.csv`
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
- `label_distribution_chart`: `report_assets/label_distribution.png`
- `prediction_coverage_by_fold`: `report_assets/prediction_coverage_by_fold.png`
