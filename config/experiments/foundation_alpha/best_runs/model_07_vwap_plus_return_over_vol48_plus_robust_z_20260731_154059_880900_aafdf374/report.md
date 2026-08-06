# Experiment Report: model_07_vwap_plus_return_over_vol48_plus_robust_z

## Overview
- Config path: `/workspace/config/experiments/foundation_alpha/BEST/ethusd/trial0041_full_exit_model_research/02_frozen_model_additions/model_07_vwap_plus_return_over_vol48_plus_robust_z.yaml`
- Model kind: `lightgbm_regressor`
- Symbols: `ETHUSD`
- Data source: `dukascopy_csv` at interval `30m`
- Data window: `None` to `2026-06-09 23:30:00`
- Rows / columns: `109005` rows, `130` columns
- Target: `future_return_regression` horizon `24`
- Feature count: `49`
- Runtime seed: `7`

## Pipeline Trace

### 1. Entry Point
- `runner.run_experiment` -> `src.experiments.runner.run_experiment(config_path: 'str | Path') -> 'ExperimentResult | Any'`
- `runner._load_asset_frames` -> `src.experiments.runner._load_asset_frames(data_cfg: 'dict[str, object]')`
- `pipeline.run_experiment_pipeline` -> `src.experiments.orchestration.pipeline.run_experiment_pipeline(config_path: 'str | Path', *, load_asset_frames_fn: 'LoadAssetFramesFn', save_processed_snapshot_fn: 'SaveProcessedFn') -> 'ExperimentResult'`

```yaml
config_path: /workspace/config/experiments/foundation_alpha/BEST/ethusd/trial0041_full_exit_model_research/02_frozen_model_additions/model_07_vwap_plus_return_over_vol48_plus_robust_z.yaml
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
  params={'high_col': 'high', 'low_col': 'low', 'close_col': 'close', 'volume_col': 'volume', 'windows': [48]}

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
- step: vwap
  params:
    high_col: high
    low_col: low
    close_col: close
    volume_col: volume
    windows:
    - 48
  outputs: {}
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: close
        denominator_col: vwap_48
        output_col: close_over_vwap_48
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
- close_over_vwap_48
- close_ret_over_vol_48
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
  - close_over_vwap_48
  - close_ret_over_vol_48
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
| cumulative_return | 4.959869 |
| annualized_return | 1.042183 |
| annualized_vol | 0.296689 |
| sharpe | 3.512708 |
| sortino | 4.097941 |
| calmar | 5.394929 |
| max_drawdown | -0.193178 |
| profit_factor | 1.171629 |
| hit_rate | 0.494473 |
| annualization_mode | fixed_periods |
| metric_scope | bar_returns |
| avg_turnover | 0.013699 |
| total_turnover | 600.000000 |
| gross_pnl | 5.328458 |
| net_pnl | 4.959869 |
| total_cost | 0.060000 |
| cost_drag | 0.368589 |
| cost_to_gross_pnl | 0.069174 |
| gross_return_sum | 1.954384 |
| net_return_sum | 1.894384 |
| cost_return_sum | 0.060000 |
| conventional_sharpe | 2.554030 |
| return_over_vol_sharpe | 3.512708 |
| sharpe_legacy_alias | return_over_vol_sharpe |
| bar_return_profit_factor | 1.171629 |
| profit_factor_scope | bar_returns |
| evaluation_scope | strict_oos_only |
| evaluation_start | 2022-03-14T15:00:00 |
| evaluation_end | 2024-09-17T10:30:00 |
| evaluation_rows | 43800 |
| trade_count | 300 |
| average_r | 0.788960 |
| median_r | 0.528904 |
| mtm_cumulative_return | 4.959869 |
| mtm_annualized_return | 1.042183 |
| mtm_annualized_vol | 0.296689 |
| mtm_sharpe | 3.512708 |
| mtm_conventional_sharpe | 2.554030 |
| mtm_return_over_vol_sharpe | 3.512708 |
| mtm_max_drawdown | -0.193178 |
| mtm_profit_factor | 1.171629 |
| mtm_bar_return_profit_factor | 1.171629 |
| flat_rate | 0.957123 |
| long_rate | 0.024543 |
| short_rate | 0.018333 |
| avg_max_favorable_r | 3.607623 |
| avg_max_adverse_r | -2.717824 |
| loser_was_positive_rate | 0.984496 |
| avg_giveback_r | 2.818663 |
| avg_capture_ratio | -4.822343 |
| robustness_walk_forward_total_calendar_periods | 7.000000 |
| robustness_walk_forward_active_oos_periods | 3.000000 |
| robustness_walk_forward_positive_active_periods | 3.000000 |
| robustness_walk_forward_positive_active_period_ratio | 1.000000 |
| robustness_walk_forward_min_active_period_cumulative_return | 0.381739 |
| robustness_walk_forward_worst_active_period_max_drawdown | -0.193178 |
| robustness_walk_forward_mean_active_period_sharpe | 4.049344 |
| robustness_walk_forward_std_active_period_sharpe | 1.906851 |
| robustness_cost_x1_cumulative_return | 4.959869 |
| robustness_cost_x1_sharpe | 3.512708 |
| robustness_cost_x1_max_drawdown | -0.193178 |
| robustness_cost_x1_profit_factor | 1.171629 |
| robustness_cost_x2_cumulative_return | 4.612713 |
| robustness_cost_x2_sharpe | 3.349197 |
| robustness_cost_x2_max_drawdown | -0.200570 |
| robustness_cost_x2_profit_factor | 1.165505 |
| robustness_cost_x3_cumulative_return | 4.285748 |
| robustness_cost_x3_sharpe | 3.189480 |
| robustness_cost_x3_max_drawdown | -0.207895 |
| robustness_cost_x3_profit_factor | 1.159423 |
| robustness_cost_x5_cumulative_return | 3.687763 |
| robustness_cost_x5_sharpe | 2.881112 |
| robustness_cost_x5_max_drawdown | -0.222347 |
| robustness_cost_x5_profit_factor | 1.147402 |
| robustness_delay_1_bars_cumulative_return | 4.445548 |
| robustness_delay_1_bars_sharpe | 3.300036 |
| robustness_delay_1_bars_max_drawdown | -0.178450 |
| robustness_delay_1_bars_profit_factor | 1.164070 |
| robustness_delay_2_bars_cumulative_return | 4.789325 |
| robustness_delay_2_bars_sharpe | 3.482851 |
| robustness_delay_2_bars_max_drawdown | -0.185574 |
| robustness_delay_2_bars_profit_factor | 1.171158 |
| completed_trade_count | 300 |
| win_rate | 0.570000 |
| trade_return_profit_factor | 2.100022 |
| trade_r_profit_factor | 1.722727 |
| trade_profit_factor | 2.100022 |
| entry_trade_cost | 0.030000 |
| exit_trade_cost | 0.030394 |
| holding_trade_cost | 0.0 |
| total_trade_cost | 0.060394 |
| position_transition_count | 598 |
| turnover_event_count | 598 |
| exposed_bar_count | 7244 |
| bar_return_profit_factor_scope | bar_returns |
| trade_return_profit_factor_scope | completed_trade_net_returns |
| trade_r_profit_factor_scope | completed_trade_net_r_multiples |
| trade_profit_factor_scope | completed_trade_net_returns |

## OOS Policy Summary
| Metric | Value |
| --- | --- |
| evaluation_rows | 43800 |
| signal_rows | 43800 |
| mean_abs_signal | 0.042877 |
| signal_turnover | 0.050822 |
| long_rate | 0.024543 |
| short_rate | 0.018333 |
| flat_rate | 0.957123 |
| executed_trade_count | 7244 |
| trade_rate | 0.165388 |
| avg_signal_executed | 0.036030 |
| avg_pred_prob_executed | 0.507062 |
| avg_realized_r_executed |  |


## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 43800 |
| classification.positive_rate | 0.497032 |
| classification.accuracy | 0.526461 |
| classification.brier | 0.253972 |
| classification.roc_auc | 0.530611 |
| classification.log_loss | 0.701814 |
| regression.evaluation_rows | 43800 |
| regression.mae | 2.171279 |
| regression.rmse | 2.634320 |
| regression.mse | 6.939641 |
| regression.r2 | -0.111414 |
| regression.correlation | 0.055443 |
| regression.directional_accuracy | 0.526347 |
| regression.mean_prediction | -0.022193 |
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
| prediction_distribution.mean | -0.022193 |
| prediction_distribution.std | 0.983644 |
| prediction_distribution.min | -4.706107 |
| prediction_distribution.max | 4.005913 |
| prediction_distribution.median | 0.001930 |
| prediction_distribution.q01 | -2.524924 |
| prediction_distribution.q05 | -1.695720 |
| prediction_distribution.q25 | -0.621903 |
| prediction_distribution.q75 | 0.609381 |
| prediction_distribution.q95 | 1.558922 |
| prediction_distribution.q99 | 2.287890 |
| prediction_distribution.skew | -0.191320 |
| prediction_distribution.kurtosis | 0.522426 |
| prediction_distribution.positive_rate | 0.500662 |
| prediction_distribution.negative_rate | 0.499338 |
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
| probability_distribution.mean | 0.498038 |
| probability_distribution.std | 0.092482 |
| probability_distribution.min | 0.137950 |
| probability_distribution.max | 0.826171 |
| probability_distribution.median | 0.500190 |
| probability_distribution.q01 | 0.270938 |
| probability_distribution.q05 | 0.339633 |
| probability_distribution.q25 | 0.439300 |
| probability_distribution.q75 | 0.559383 |
| probability_distribution.q95 | 0.647757 |
| probability_distribution.q99 | 0.709956 |
| probability_distribution.skew | -0.145275 |
| probability_distribution.kurtosis | 0.115509 |
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
| model_strategy | 2.103547 | 0.573053 | 0.232914 | 2.460362 | 3.292493 | 4.473800 | -0.128091 | 1.172061 | 0.498005 | 380.000000 | 0.054067 |
| buy_and_hold | -0.102619 | -0.042385 | 0.665486 | -0.063691 | 0.375698 | -0.056670 | -0.747935 | 1.006790 | 0.507216 | 1.000000 | 0.000875 |
| random_sign_same_rate | -0.476519 | -0.228101 | 0.343808 | -0.663454 | -0.794566 | -0.408922 | -0.557811 | 0.973164 | 0.477894 | 1.036e+03 | 0.136232 |
| volatility_regime_only | -0.166762 | -0.070375 | 0.404959 | -0.173784 | 0.031471 | -0.120210 | -0.585437 | 1.000890 | 0.494392 | 862.000000 | 0.818224 |
| simple_trend | -0.532426 | -0.262198 | 0.436182 | -0.601119 | -0.674248 | -0.419772 | -0.624619 | 0.983873 | 0.490531 | 772.000000 | 0.075969 |


## Fold Robustness
| Metric | Value |
| --- | --- |
| fold_count | 10.000000 |
| median_fold_return | 0.102815 |
| mean_fold_return | 0.127911 |
| fold_return_std | 0.144055 |
| worst_fold_return | -0.061281 |
| best_fold_return | 0.401564 |
| worst_3_fold_average_return | -0.021310 |
| profitable_fold_count | 8.000000 |
| profitable_fold_rate | 0.800000 |
| median_fold_sharpe | 2.862313 |
| feature_importance_rank_stability.available | true |
| feature_importance_rank_stability.folds_with_importance | 10 |
| feature_importance_rank_stability.top_features | [{'feature': 'atr_48', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.4, 'best_rank': 1, 'mean_importance': 1100.5, 'mean_importance_normalized': 0.101510078288733, 'folds': [{'fold': 0, 'rank': 1, 'importance': 1105.0, 'importance_normalized': 0.10636249879680432}, {'fold': 1, 'rank': 1, 'importance': 1086.0, 'importance_normalized': 0.10070474777448071}, {'fold': 2, 'rank': 1, 'importance': 1147.0, 'importance_normalized': 0.10483502422082076}, {'fold': 3, 'rank': 1, 'importance': 1168.0, 'importance_normalized': 0.10668615272195835}, {'fold': 4, 'rank': 2, 'importance': 1059.0, 'importance_normalized': 0.09707580896507471}, {'fold': 5, 'rank': 1, 'importance': 1061.0, 'importance_normalized': 0.09840474865516602}, {'fold': 6, 'rank': 1, 'importance': 1135.0, 'importance_normalized': 0.10473378241210667}, {'fold': 7, 'rank': 2, 'importance': 1069.0, 'importance_normalized': 0.09734996812676441}, {'fold': 8, 'rank': 2, 'importance': 1084.0, 'importance_normalized': 0.09946779225545972}, {'fold': 9, 'rank': 2, 'importance': 1091.0, 'importance_normalized': 0.09948025895869426}], 'stability_rank': 1}, {'feature': 'vol_rolling_192', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 1.6, 'best_rank': 1, 'mean_importance': 1078.9, 'mean_importance_normalized': 0.09947334380124653, 'folds': [{'fold': 0, 'rank': 2, 'importance': 996.0, 'importance_normalized': 0.09587063239965347}, {'fold': 1, 'rank': 2, 'importance': 1025.0, 'importance_normalized': 0.09504821958456973}, {'fold': 2, 'rank': 2, 'importance': 1057.0, 'importance_normalized': 0.09660908509277032}, {'fold': 3, 'rank': 2, 'importance': 1017.0, 'importance_normalized': 0.09289367921081476}, {'fold': 4, 'rank': 1, 'importance': 1119.0, 'importance_normalized': 0.10257585479878999}, {'fold': 5, 'rank': 2, 'importance': 1055.0, 'importance_normalized': 0.09784826562789835}, {'fold': 6, 'rank': 2, 'importance': 1086.0, 'importance_normalized': 0.10021223585863247}, {'fold': 7, 'rank': 1, 'importance': 1097.0, 'importance_normalized': 0.09989982697386394}, {'fold': 8, 'rank': 1, 'importance': 1181.0, 'importance_normalized': 0.10836850798311617}, {'fold': 9, 'rank': 1, 'importance': 1156.0, 'importance_normalized': 0.10540713048235616}], 'stability_rank': 2}, {'feature': 'bollinger_bandwidth', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 3.0, 'best_rank': 3, 'mean_importance': 907.5, 'mean_importance_normalized': 0.08365918258576639, 'folds': [{'fold': 0, 'rank': 3, 'importance': 820.0, 'importance_normalized': 0.07892963711618058}, {'fold': 1, 'rank': 3, 'importance': 834.0, 'importance_normalized': 0.07733679525222552}, {'fold': 2, 'rank': 3, 'importance': 886.0, 'importance_normalized': 0.08097980074947446}, {'fold': 3, 'rank': 3, 'importance': 919.0, 'importance_normalized': 0.08394227256119839}, {'fold': 4, 'rank': 3, 'importance': 948.0, 'importance_normalized': 0.08690072417270144}, {'fold': 5, 'rank': 3, 'importance': 914.0, 'importance_normalized': 0.08477091448710815}, {'fold': 6, 'rank': 3, 'importance': 915.0, 'importance_normalized': 0.08443296115161023}, {'fold': 7, 'rank': 3, 'importance': 939.0, 'importance_normalized': 0.08551133776523086}, {'fold': 8, 'rank': 3, 'importance': 936.0, 'importance_normalized': 0.085887318774087}, {'fold': 9, 'rank': 3, 'importance': 964.0, 'importance_normalized': 0.08790006382784718}], 'stability_rank': 3}, {'feature': 'vol_rolling_96', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.2, 'best_rank': 4, 'mean_importance': 775.1, 'mean_importance_normalized': 0.07142590576830601, 'folds': [{'fold': 0, 'rank': 5, 'importance': 642.0, 'importance_normalized': 0.061796130522668205}, {'fold': 1, 'rank': 5, 'importance': 709.0, 'importance_normalized': 0.06574554896142433}, {'fold': 2, 'rank': 4, 'importance': 781.0, 'importance_normalized': 0.07138287176674893}, {'fold': 3, 'rank': 4, 'importance': 823.0, 'importance_normalized': 0.07517354767994154}, {'fold': 4, 'rank': 4, 'importance': 768.0, 'importance_normalized': 0.07040058667155559}, {'fold': 5, 'rank': 4, 'importance': 793.0, 'importance_normalized': 0.0735485067705435}, {'fold': 6, 'rank': 4, 'importance': 787.0, 'importance_normalized': 0.07262157423641229}, {'fold': 7, 'rank': 4, 'importance': 815.0, 'importance_normalized': 0.07421910572807577}, {'fold': 8, 'rank': 4, 'importance': 814.0, 'importance_normalized': 0.07469260414755001}, {'fold': 9, 'rank': 4, 'importance': 819.0, 'importance_normalized': 0.07467858119813987}], 'stability_rank': 4}, {'feature': 'ema_trend_48_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 4.8, 'best_rank': 4, 'mean_importance': 741.3, 'mean_importance_normalized': 0.06840874246843427, 'folds': [{'fold': 0, 'rank': 4, 'importance': 791.0, 'importance_normalized': 0.07613822312060833}, {'fold': 1, 'rank': 4, 'importance': 771.0, 'importance_normalized': 0.07149480712166172}, {'fold': 2, 'rank': 5, 'importance': 697.0, 'importance_normalized': 0.0637053285805685}, {'fold': 3, 'rank': 5, 'importance': 713.0, 'importance_normalized': 0.06512605042016807}, {'fold': 4, 'rank': 5, 'importance': 758.0, 'importance_normalized': 0.06948391236593639}, {'fold': 5, 'rank': 5, 'importance': 745.0, 'importance_normalized': 0.06909664255240215}, {'fold': 6, 'rank': 5, 'importance': 732.0, 'importance_normalized': 0.06754636892128818}, {'fold': 7, 'rank': 5, 'importance': 743.0, 'importance_normalized': 0.06766232583553411}, {'fold': 8, 'rank': 5, 'importance': 751.0, 'importance_normalized': 0.06891172692237107}, {'fold': 9, 'rank': 5, 'importance': 712.0, 'importance_normalized': 0.06492203884380414}], 'stability_rank': 5}, {'feature': 'bollinger_bandwidth_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 6.2, 'best_rank': 6, 'mean_importance': 601.1, 'mean_importance_normalized': 0.05543183585383016, 'folds': [{'fold': 0, 'rank': 6, 'importance': 569.0, 'importance_normalized': 0.05476946770622774}, {'fold': 1, 'rank': 6, 'importance': 604.0, 'importance_normalized': 0.05600890207715133}, {'fold': 2, 'rank': 6, 'importance': 598.0, 'importance_normalized': 0.054656795539713005}, {'fold': 3, 'rank': 7, 'importance': 590.0, 'importance_normalized': 0.05389112166605773}, {'fold': 4, 'rank': 7, 'importance': 584.0, 'importance_normalized': 0.05353377944816207}, {'fold': 5, 'rank': 6, 'importance': 614.0, 'importance_normalized': 0.05694676312372473}, {'fold': 6, 'rank': 6, 'importance': 599.0, 'importance_normalized': 0.05527359970471533}, {'fold': 7, 'rank': 6, 'importance': 631.0, 'importance_normalized': 0.05746289044713596}, {'fold': 8, 'rank': 6, 'importance': 606.0, 'importance_normalized': 0.05560653330886401}, {'fold': 9, 'rank': 6, 'importance': 616.0, 'importance_normalized': 0.05616850551654965}], 'stability_rank': 6}, {'feature': 'atr_over_price_48', 'family': 'atr_adx_range', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.1, 'best_rank': 6, 'mean_importance': 576.9, 'mean_importance_normalized': 0.05320533743109292, 'folds': [{'fold': 0, 'rank': 7, 'importance': 563.0, 'importance_normalized': 0.05419193377610935}, {'fold': 1, 'rank': 7, 'importance': 568.0, 'importance_normalized': 0.052670623145400594}, {'fold': 2, 'rank': 7, 'importance': 587.0, 'importance_normalized': 0.05365140297961795}, {'fold': 3, 'rank': 6, 'importance': 608.0, 'importance_normalized': 0.055535257581293386}, {'fold': 4, 'rank': 6, 'importance': 591.0, 'importance_normalized': 0.054175451462095514}, {'fold': 5, 'rank': 7, 'importance': 586.0, 'importance_normalized': 0.05434984232980894}, {'fold': 6, 'rank': 8, 'importance': 546.0, 'importance_normalized': 0.05038294731014118}, {'fold': 7, 'rank': 7, 'importance': 559.0, 'importance_normalized': 0.0509061105545943}, {'fold': 8, 'rank': 8, 'importance': 566.0, 'importance_normalized': 0.051936135070655164}, {'fold': 9, 'rank': 8, 'importance': 595.0, 'importance_normalized': 0.05425367010121273}], 'stability_rank': 7}, {'feature': 'vol_rolling_48', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 7.8, 'best_rank': 7, 'mean_importance': 557.7, 'mean_importance_normalized': 0.05141689563646077, 'folds': [{'fold': 0, 'rank': 8, 'importance': 513.0, 'importance_normalized': 0.049379151025122726}, {'fold': 1, 'rank': 9, 'importance': 519.0, 'importance_normalized': 0.04812685459940653}, {'fold': 2, 'rank': 8, 'importance': 554.0, 'importance_normalized': 0.05063522529933279}, {'fold': 3, 'rank': 8, 'importance': 588.0, 'importance_normalized': 0.05370843989769821}, {'fold': 4, 'rank': 8, 'importance': 563.0, 'importance_normalized': 0.05160876340636172}, {'fold': 5, 'rank': 8, 'importance': 538.0, 'importance_normalized': 0.049897978111667594}, {'fold': 6, 'rank': 7, 'importance': 585.0, 'importance_normalized': 0.05398172926086555}, {'fold': 7, 'rank': 8, 'importance': 536.0, 'importance_normalized': 0.048811583644476825}, {'fold': 8, 'rank': 7, 'importance': 576.0, 'importance_normalized': 0.05285373463020738}, {'fold': 9, 'rank': 7, 'importance': 605.0, 'importance_normalized': 0.055165496489468405}], 'stability_rank': 8}, {'feature': 'atr_pct_rank_192', 'family': 'unclassified', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 8.9, 'best_rank': 8, 'mean_importance': 470.5, 'mean_importance_normalized': 0.04339520690301315, 'folds': [{'fold': 0, 'rank': 9, 'importance': 460.0, 'importance_normalized': 0.04427760130907691}, {'fold': 1, 'rank': 8, 'importance': 520.0, 'importance_normalized': 0.04821958456973294}, {'fold': 2, 'rank': 9, 'importance': 479.0, 'importance_normalized': 0.04378027602595741}, {'fold': 3, 'rank': 9, 'importance': 470.0, 'importance_normalized': 0.042930215564486666}, {'fold': 4, 'rank': 9, 'importance': 481.0, 'importance_normalized': 0.04409203410028417}, {'fold': 5, 'rank': 9, 'importance': 448.0, 'importance_normalized': 0.04155073270265257}, {'fold': 6, 'rank': 9, 'importance': 439.0, 'importance_normalized': 0.04050936606071791}, {'fold': 7, 'rank': 9, 'importance': 488.0, 'importance_normalized': 0.04444039704944905}, {'fold': 8, 'rank': 9, 'importance': 457.0, 'importance_normalized': 0.04193429987153606}, {'fold': 9, 'rank': 9, 'importance': 463.0, 'importance_normalized': 0.042217561776237804}], 'stability_rank': 9}, {'feature': 'vol_rolling_24', 'family': 'volatility', 'fold_count': 10, 'fold_coverage': 1.0, 'mean_rank': 10.2, 'best_rank': 10, 'mean_importance': 413.1, 'mean_importance_normalized': 0.038112802877646776, 'folds': [{'fold': 0, 'rank': 10, 'importance': 428.0, 'importance_normalized': 0.04119742034844547}, {'fold': 1, 'rank': 10, 'importance': 438.0, 'importance_normalized': 0.04061572700296736}, {'fold': 2, 'rank': 10, 'importance': 420.0, 'importance_normalized': 0.03838771593090211}, {'fold': 3, 'rank': 10, 'importance': 404.0, 'importance_normalized': 0.03690171720862258}, {'fold': 4, 'rank': 10, 'importance': 442.0, 'importance_normalized': 0.040517004308369235}, {'fold': 5, 'rank': 11, 'importance': 375.0, 'importance_normalized': 0.03478018920422927}, {'fold': 6, 'rank': 10, 'importance': 418.0, 'importance_normalized': 0.03857156039494325}, {'fold': 7, 'rank': 10, 'importance': 398.0, 'importance_normalized': 0.03624442218377197}, {'fold': 8, 'rank': 10, 'importance': 410.0, 'importance_normalized': 0.03762158194164067}, {'fold': 9, 'rank': 11, 'importance': 398.0, 'importance_normalized': 0.03629069025257591}], 'stability_rank': 10}] |


## Regime Performance
| Feature | Bucket | Rows | Cum Return | Sharpe | Max DD | Profit Factor | Cost/Gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atr_pct_rank_192 | low | 1.358e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| atr_pct_rank_192 | medium | 2.167e+04 | 1.111397 | 2.780535 | -0.158739 | 1.129456 | 0.061649 |
| atr_pct_rank_192 | high | 8.547e+03 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| bollinger_bandwidth_rank_192 | low | 2.251e+04 | 0.419020 | 1.874152 | -0.130852 | 1.210130 | 0.031641 |
| bollinger_bandwidth_rank_192 | high | 2.129e+04 | 1.406483 | 3.542686 | -0.141890 | 1.166438 | 0.050826 |
| ema_trend_48_192 | negative | 2.183e+04 | 0.941503 | 2.753188 | -0.128127 | 1.184876 | 0.040394 |
| ema_trend_48_192 | positive | 2.197e+04 | 0.580918 | 2.011641 | -0.147830 | 1.139524 | 0.050624 |
| range_to_atr | calm | 2.190e+04 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| range_to_atr | shock | 2.190e+04 | 1.212549 | 2.327801 | -0.225051 | 1.107774 | 0.051965 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| test_rows_without_prediction | 0 |
| folds_with_zero_predictions | 0 |


## Trade Diagnostics
| Metric | Value |
| --- | --- |
| trade_count | 300 |
| average_r | 0.788960 |
| median_r | 0.528904 |
| exit_reason_counts.position_exit | 298 |
| exit_reason_counts.reversal | 2 |
| avg_max_favorable_r | 3.607623 |
| median_max_favorable_r | 2.548930 |
| avg_max_adverse_r | -2.717824 |
| median_max_adverse_r | -1.866892 |
| partial_exit_count_total | 0 |
| partial_exit_trade_count | 0 |
| avg_partial_exit_fraction_total |  |
| avg_partial_exit_realized_r |  |
| loser_was_positive_rate | 0.984496 |
| avg_giveback_r | 2.818663 |
| avg_capture_ratio | -4.822343 |
| completed_trade_count | 300 |
| win_rate | 0.570000 |
| trade_return_profit_factor | 2.100022 |
| trade_r_profit_factor | 1.722727 |
| trade_profit_factor | 2.100022 |
| entry_trade_cost | 0.030000 |
| exit_trade_cost | 0.030394 |
| holding_trade_cost | 0.0 |
| total_trade_cost | 0.060394 |
| position_transition_count | 598 |
| turnover_event_count | 598 |
| exposed_bar_count | 7244 |


## Trade Path Diagnostics
### Losing Trades Could-Have-Been-Profitable
| Metric | Value |
| --- | --- |
| loser_was_positive_rate | 0.984496 |
| avg_mfe_r_of_losers | 1.417973 |
| median_mfe_r_of_losers | 1.084080 |
| avg_mfe_r_before_loss | 1.417973 |
| median_mfe_r_before_loss | 1.084080 |
| loser_reached_0_5r_rate | 0.775194 |
| loser_reached_1r_rate | 0.550388 |
| loser_reached_1_5r_rate | 0.364341 |
| loser_reached_2r_rate | 0.240310 |

### Capture / Giveback
| Metric | Value |
| --- | --- |
| avg_capture_ratio | -4.822343 |
| median_capture_ratio | 0.214473 |
| avg_giveback_r | 2.818663 |
| median_giveback_r | 2.006915 |
| avg_giveback_r_winners | 1.960161 |
| avg_giveback_r_losers | 3.956677 |
| median_giveback_r_winners | 1.506131 |
| median_giveback_r_losers | 3.153686 |

### MAE Before Win
| Metric | Value |
| --- | --- |
| winner_had_negative_mae_rate | 0.994152 |
| winner_had_mae_below_minus_0_25r_rate | 0.836257 |
| winner_had_mae_below_minus_0_5r_rate | 0.654971 |
| winner_had_mae_below_minus_1r_rate | 0.502924 |
| avg_mae_r_of_winners | -1.297679 |
| median_mae_r_of_winners | -1.016956 |
| p90_abs_mae_r_of_winners | 2.934026 |
| avg_mae_r | -2.717824 |
| median_mae_r | -1.866892 |
| q10_mae_r | -6.072926 |
| q25_mae_r | -3.308011 |
| q75_mae_r | -0.811108 |
| q90_mae_r | -0.269039 |

### Conditional Probabilities
| Metric | Value |
| --- | --- |
| prob_final_win | 0.570000 |
| prob_final_loss | 0.430000 |
| prob_final_win_given_mae_gt_minus_0_5r | 1.000000 |
| prob_final_win_given_mae_gt_minus_1r | 1.000000 |
| prob_mfe_ge_0_5r | 0.903333 |
| prob_final_loss_given_mfe_ge_0_5r | 0.369004 |
| prob_mfe_ge_1r | 0.796667 |
| prob_final_loss_given_mfe_ge_1r | 0.297071 |
| prob_mfe_ge_1_5r | 0.690000 |
| prob_final_loss_given_mfe_ge_1_5r | 0.227053 |
| prob_mfe_ge_2r | 0.590000 |
| prob_final_loss_given_mfe_ge_2r | 0.175141 |
| prob_stop_loss_given_mfe_ge_0_5r | 0.0 |
| prob_stop_loss_given_mfe_ge_1r | 0.0 |

### Timing Diagnostics
| Metric | Value |
| --- | --- |
| avg_time_to_mfe | 12.120000 |
| median_time_to_mfe | 12.000000 |
| avg_time_to_mae | 9.536667 |
| median_time_to_mae | 8.000000 |
| prob_mfe_ge_0_5r_within_1_bar | 0.066667 |
| prob_mfe_ge_0_5r_within_2_bars | 0.123333 |
| prob_mfe_ge_1r_within_4_bars | 0.116667 |
| avg_r_by_bars_held_bucket.1 |  |
| avg_r_by_bars_held_bucket.2 |  |
| avg_r_by_bars_held_bucket.3-4 |  |
| avg_r_by_bars_held_bucket.5-8 |  |
| avg_r_by_bars_held_bucket.9-16 |  |
| avg_r_by_bars_held_bucket.17+ | 0.788960 |
| win_rate_by_bars_held_bucket.1 |  |
| win_rate_by_bars_held_bucket.2 |  |
| win_rate_by_bars_held_bucket.3-4 |  |
| win_rate_by_bars_held_bucket.5-8 |  |
| win_rate_by_bars_held_bucket.9-16 |  |
| win_rate_by_bars_held_bucket.17+ | 0.570000 |

### Counterfactual Exits
| Metric | Value |
| --- | --- |
| counterfactual.baseline.trade_count | 300 |
| counterfactual.baseline.avg_r | 0.788960 |
| counterfactual.baseline.median_r | 0.528904 |
| counterfactual.baseline.win_rate | 0.570000 |
| counterfactual.baseline.profit_factor | 1.722727 |
| counterfactual.breakeven_after_0_5r.trade_count | 300 |
| counterfactual.breakeven_after_0_5r.avg_r | -0.066689 |
| counterfactual.breakeven_after_0_5r.median_r | 0.0 |
| counterfactual.breakeven_after_0_5r.win_rate | 0.016667 |
| counterfactual.breakeven_after_0_5r.profit_factor | 0.396908 |
| counterfactual.breakeven_after_1_0r.trade_count | 300 |
| counterfactual.breakeven_after_1_0r.avg_r | 0.228663 |
| counterfactual.breakeven_after_1_0r.median_r | 0.0 |
| counterfactual.breakeven_after_1_0r.win_rate | 0.143333 |
| counterfactual.breakeven_after_1_0r.profit_factor | 1.676285 |
| counterfactual.exit_at_first_0_5r.trade_count | 300 |
| counterfactual.exit_at_first_0_5r.avg_r | 0.369421 |
| counterfactual.exit_at_first_0_5r.median_r | 0.500000 |
| counterfactual.exit_at_first_0_5r.win_rate | 0.960000 |
| counterfactual.exit_at_first_0_5r.profit_factor | 4.340800 |
| counterfactual.exit_at_first_1_0r.trade_count | 300 |
| counterfactual.exit_at_first_1_0r.avg_r | 0.536126 |
| counterfactual.exit_at_first_1_0r.median_r | 1.000000 |
| counterfactual.exit_at_first_1_0r.win_rate | 0.880000 |
| counterfactual.exit_at_first_1_0r.profit_factor | 2.585629 |
| counterfactual.partial_50pct_at_1r.trade_count | 300 |
| counterfactual.partial_50pct_at_1r.avg_r | 0.662543 |
| counterfactual.partial_50pct_at_1r.median_r | 0.757702 |
| counterfactual.partial_50pct_at_1r.win_rate | 0.693333 |
| counterfactual.partial_50pct_at_1r.profit_factor | 2.117865 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.trade_count | 300 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.avg_r | 0.767885 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.median_r | 0.427663 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.win_rate | 0.556667 |
| counterfactual.time_exit_after_4_bars_if_mfe_lt_0_3r.profit_factor | 1.705357 |
| counterfactual.trail_0_5r_after_1_0r.trade_count | 300 |
| counterfactual.trail_0_5r_after_1_0r.avg_r | 0.747457 |
| counterfactual.trail_0_5r_after_1_0r.median_r | 0.838476 |
| counterfactual.trail_0_5r_after_1_0r.win_rate | 0.880000 |
| counterfactual.trail_0_5r_after_1_0r.profit_factor | 3.210653 |
| counterfactual.best_policy_by_avg_r | baseline |
| counterfactual.best_policy_by_profit_factor | exit_at_first_0_5r |

### Exit Reason Quality
| Exit Reason | Trades | Avg R | Median R | Win Rate | Avg MFE | Avg MAE | Avg Giveback | Avg Bars | Profit Factor | Stop After + | Stop After 0.5R | Stop After 1R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| position_exit | 298 | 0.785642 | 0.524473 | 0.567114 | 3.614055 | -2.713164 | 2.828413 | 24.147651 | 1.714890 | 0.993289 | 0.902685 | 0.795302 |
| reversal | 2 | 1.283335 | 1.283335 | 1.000000 | 2.649306 | -3.412088 | 1.365970 | 24.000000 | inf | 1.000000 | 1.000000 | 1.000000 |


## Baseline VWAP/RMS Diagnostics
### Primary
| Metric | Value |
| --- | --- |
| trade_count | 300 |
| gross_pnl | 5.328458 |
| net_pnl | 4.959869 |
| total_cost | 0.060000 |
| cost_to_gross_pnl | 0.069174 |

### Trade Count By Asset
| Asset | Trades |
| --- | --- |
| ETHUSD | 300 |

### Performance Breakdowns
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asset | ETHUSD | 300 | 1.953251 | 0.030000 | 0.030394 | 0.0 | 0.060394 | 1.892857 | 2.100022 | 0.570000 |
| side | long | 173 | 1.298513 | 0.017300 | 0.017562 | 0.0 | 0.034862 | 1.263651 | 2.306305 | 0.572254 |
| side | short | 127 | 0.654738 | 0.012700 | 0.012831 | 0.0 | 0.025531 | 0.629207 | 1.835159 | 0.566929 |
| volatility_regime | missing | 300 | 1.953251 | 0.030000 | 0.030394 | 0.0 | 0.060394 | 1.892857 | 2.100022 | 0.570000 |
| year | 2022 | 106 | 0.811520 | 0.010600 | 0.010760 | 0.0 | 0.021360 | 0.790159 | 1.989373 | 0.575472 |
| year | 2023 | 122 | 0.373952 | 0.012200 | 0.012275 | 0.0 | 0.024475 | 0.349478 | 1.519283 | 0.483607 |
| year | 2024 | 72 | 0.767779 | 0.007200 | 0.007358 | 0.0 | 0.014558 | 0.753220 | 4.023797 | 0.708333 |


## STC Roofing Hilbert Diagnostics
### Signal Counts
| Metric | Value |
| --- | --- |
| total_rows | 109005 |
| final_signal_rows | 1878 |
| actual_trade_count | 300 |

### Performance
| Metric | Value |
| --- | --- |
| cumulative_return | 4.959869 |
| sharpe | 3.512708 |
| sortino | 4.097941 |
| calmar | 5.394929 |
| max_drawdown | -0.193178 |
| profit_factor | 1.171629 |
| hit_rate | 0.494473 |
| trade_count | 300 |
| gross_pnl | 5.328458 |
| net_pnl | 4.959869 |
| total_cost | 0.060000 |
| cost_to_gross_pnl | 0.069174 |
| average_r | 0.788960 |
| median_r | 0.528904 |

### Side Diagnostics
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| side | long | 173 | 1.298513 |  |  |  | 0.0 | 1.263651 | 2.306305 | 0.572254 |
| side | short | 127 | 0.654738 |  |  |  | 0.0 | 0.629207 | 1.835159 | 0.566929 |

### Year Diagnostics
| Group | Bucket | Trades | Gross PnL | Entry Cost | Exit Cost | Holding Cost | Total Cost | Net PnL | Profit Factor | Hit Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| year | 2022 | 106 | 0.811520 |  |  |  | 0.0 | 0.790159 | 1.989373 | 0.575472 |
| year | 2023 | 122 | 0.373952 |  |  |  | 0.0 | 0.349478 | 1.519283 | 0.483607 |
| year | 2024 | 72 | 0.767779 |  |  |  | 0.0 | 0.753220 | 4.023797 | 0.708333 |


## Robustness Diagnostics
### Cost Stress
| Metric | Value |
| --- | --- |
| cost_x1.cumulative_return | 4.959869 |
| cost_x1.annualized_return | 1.042183 |
| cost_x1.annualized_vol | 0.296689 |
| cost_x1.sharpe | 3.512708 |
| cost_x1.sortino | 4.097941 |
| cost_x1.calmar | 5.394929 |
| cost_x1.max_drawdown | -0.193178 |
| cost_x1.profit_factor | 1.171629 |
| cost_x1.hit_rate | 0.494473 |
| cost_x1.bar_return_profit_factor | 1.171629 |
| cost_x1.conventional_sharpe | 2.554030 |
| cost_x1.return_over_vol_sharpe | 3.512708 |
| cost_x1.profit_factor_scope | bar_returns |
| cost_x1.metric_scope | bar_returns |
| cost_x1.annualization_mode | fixed_periods |
| cost_x1.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x1.gross_pnl | 5.328458 |
| cost_x1.net_pnl | 4.959869 |
| cost_x1.total_cost | 0.060000 |
| cost_x1.cost_drag | 0.368589 |
| cost_x1.cost_to_gross_pnl | 0.069174 |
| cost_x1.gross_return_sum | 1.954384 |
| cost_x1.net_return_sum | 1.894384 |
| cost_x1.cost_return_sum | 0.060000 |
| cost_x1.avg_turnover | 0.013699 |
| cost_x1.total_turnover | 600.000000 |
| cost_x1.evaluation_scope | strict_oos_only |
| cost_x1.evaluation_start | 2022-03-14T15:00:00 |
| cost_x1.evaluation_end | 2024-09-17T10:30:00 |
| cost_x1.evaluation_rows | 43800 |
| cost_x2.cumulative_return | 4.612713 |
| cost_x2.annualized_return | 0.993743 |
| cost_x2.annualized_vol | 0.296711 |
| cost_x2.sharpe | 3.349197 |
| cost_x2.sortino | 3.965648 |
| cost_x2.calmar | 4.954585 |
| cost_x2.max_drawdown | -0.200570 |
| cost_x2.profit_factor | 1.165505 |
| cost_x2.hit_rate | 0.493674 |
| cost_x2.bar_return_profit_factor | 1.165505 |
| cost_x2.conventional_sharpe | 2.472958 |
| cost_x2.return_over_vol_sharpe | 3.349197 |
| cost_x2.profit_factor_scope | bar_returns |
| cost_x2.metric_scope | bar_returns |
| cost_x2.annualization_mode | fixed_periods |
| cost_x2.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x2.gross_pnl | 5.328458 |
| cost_x2.net_pnl | 4.612713 |
| cost_x2.total_cost | 0.120000 |
| cost_x2.cost_drag | 0.715744 |
| cost_x2.cost_to_gross_pnl | 0.134325 |
| cost_x2.gross_return_sum | 1.954384 |
| cost_x2.net_return_sum | 1.834384 |
| cost_x2.cost_return_sum | 0.120000 |
| cost_x2.avg_turnover | 0.013699 |
| cost_x2.total_turnover | 600.000000 |
| cost_x2.evaluation_scope | strict_oos_only |
| cost_x2.evaluation_start | 2022-03-14T15:00:00 |
| cost_x2.evaluation_end | 2024-09-17T10:30:00 |
| cost_x2.evaluation_rows | 43800 |
| cost_x3.cumulative_return | 4.285748 |
| cost_x3.annualized_return | 0.946447 |
| cost_x3.annualized_vol | 0.296740 |
| cost_x3.sharpe | 3.189480 |
| cost_x3.sortino | 3.833317 |
| cost_x3.calmar | 4.552513 |
| cost_x3.max_drawdown | -0.207895 |
| cost_x3.profit_factor | 1.159423 |
| cost_x3.hit_rate | 0.493142 |
| cost_x3.bar_return_profit_factor | 1.159423 |
| cost_x3.conventional_sharpe | 2.391834 |
| cost_x3.return_over_vol_sharpe | 3.189480 |
| cost_x3.profit_factor_scope | bar_returns |
| cost_x3.metric_scope | bar_returns |
| cost_x3.annualization_mode | fixed_periods |
| cost_x3.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x3.gross_pnl | 5.328458 |
| cost_x3.net_pnl | 4.285748 |
| cost_x3.total_cost | 0.180000 |
| cost_x3.cost_drag | 1.042710 |
| cost_x3.cost_to_gross_pnl | 0.195687 |
| cost_x3.gross_return_sum | 1.954384 |
| cost_x3.net_return_sum | 1.774384 |
| cost_x3.cost_return_sum | 0.180000 |
| cost_x3.avg_turnover | 0.013699 |
| cost_x3.total_turnover | 600.000000 |
| cost_x3.evaluation_scope | strict_oos_only |
| cost_x3.evaluation_start | 2022-03-14T15:00:00 |
| cost_x3.evaluation_end | 2024-09-17T10:30:00 |
| cost_x3.evaluation_rows | 43800 |
| cost_x5.cumulative_return | 3.687763 |
| cost_x5.annualized_return | 0.855181 |
| cost_x5.annualized_vol | 0.296823 |
| cost_x5.sharpe | 2.881112 |
| cost_x5.sortino | 3.568621 |
| cost_x5.calmar | 3.846153 |
| cost_x5.max_drawdown | -0.222347 |
| cost_x5.profit_factor | 1.147402 |
| cost_x5.hit_rate | 0.492209 |
| cost_x5.bar_return_profit_factor | 1.147402 |
| cost_x5.conventional_sharpe | 2.229453 |
| cost_x5.return_over_vol_sharpe | 2.881112 |
| cost_x5.profit_factor_scope | bar_returns |
| cost_x5.metric_scope | bar_returns |
| cost_x5.annualization_mode | fixed_periods |
| cost_x5.sharpe_legacy_alias | return_over_vol_sharpe |
| cost_x5.gross_pnl | 5.328458 |
| cost_x5.net_pnl | 3.687763 |
| cost_x5.total_cost | 0.300000 |
| cost_x5.cost_drag | 1.640694 |
| cost_x5.cost_to_gross_pnl | 0.307912 |
| cost_x5.gross_return_sum | 1.954384 |
| cost_x5.net_return_sum | 1.654384 |
| cost_x5.cost_return_sum | 0.300000 |
| cost_x5.avg_turnover | 0.013699 |
| cost_x5.total_turnover | 600.000000 |
| cost_x5.evaluation_scope | strict_oos_only |
| cost_x5.evaluation_start | 2022-03-14T15:00:00 |
| cost_x5.evaluation_end | 2024-09-17T10:30:00 |
| cost_x5.evaluation_rows | 43800 |

### Slippage Stress
| Metric | Value |
| --- | --- |
| slippage_x1.cumulative_return | 4.959869 |
| slippage_x1.annualized_return | 1.042183 |
| slippage_x1.annualized_vol | 0.296689 |
| slippage_x1.sharpe | 3.512708 |
| slippage_x1.sortino | 4.097941 |
| slippage_x1.calmar | 5.394929 |
| slippage_x1.max_drawdown | -0.193178 |
| slippage_x1.profit_factor | 1.171629 |
| slippage_x1.hit_rate | 0.494473 |
| slippage_x1.bar_return_profit_factor | 1.171629 |
| slippage_x1.conventional_sharpe | 2.554030 |
| slippage_x1.return_over_vol_sharpe | 3.512708 |
| slippage_x1.profit_factor_scope | bar_returns |
| slippage_x1.metric_scope | bar_returns |
| slippage_x1.annualization_mode | fixed_periods |
| slippage_x1.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x1.gross_pnl | 4.959869 |
| slippage_x1.net_pnl | 4.959869 |
| slippage_x1.total_cost | 0.0 |
| slippage_x1.cost_drag | 0.0 |
| slippage_x1.cost_to_gross_pnl | 0.0 |
| slippage_x1.gross_return_sum | 1.894384 |
| slippage_x1.net_return_sum | 1.894384 |
| slippage_x1.cost_return_sum | 0.0 |
| slippage_x1.avg_turnover | 0.0 |
| slippage_x1.total_turnover | 0.0 |
| slippage_x1.evaluation_scope | strict_oos_only |
| slippage_x1.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x1.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x1.evaluation_rows | 43800 |
| slippage_x2.cumulative_return | 4.959869 |
| slippage_x2.annualized_return | 1.042183 |
| slippage_x2.annualized_vol | 0.296689 |
| slippage_x2.sharpe | 3.512708 |
| slippage_x2.sortino | 4.097941 |
| slippage_x2.calmar | 5.394929 |
| slippage_x2.max_drawdown | -0.193178 |
| slippage_x2.profit_factor | 1.171629 |
| slippage_x2.hit_rate | 0.494473 |
| slippage_x2.bar_return_profit_factor | 1.171629 |
| slippage_x2.conventional_sharpe | 2.554030 |
| slippage_x2.return_over_vol_sharpe | 3.512708 |
| slippage_x2.profit_factor_scope | bar_returns |
| slippage_x2.metric_scope | bar_returns |
| slippage_x2.annualization_mode | fixed_periods |
| slippage_x2.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x2.gross_pnl | 4.959869 |
| slippage_x2.net_pnl | 4.959869 |
| slippage_x2.total_cost | 0.0 |
| slippage_x2.cost_drag | 0.0 |
| slippage_x2.cost_to_gross_pnl | 0.0 |
| slippage_x2.gross_return_sum | 1.894384 |
| slippage_x2.net_return_sum | 1.894384 |
| slippage_x2.cost_return_sum | 0.0 |
| slippage_x2.avg_turnover | 0.0 |
| slippage_x2.total_turnover | 0.0 |
| slippage_x2.evaluation_scope | strict_oos_only |
| slippage_x2.evaluation_start | 2022-03-14T15:00:00 |
| slippage_x2.evaluation_end | 2024-09-17T10:30:00 |
| slippage_x2.evaluation_rows | 43800 |
| slippage_x3.cumulative_return | 4.959869 |
| slippage_x3.annualized_return | 1.042183 |
| slippage_x3.annualized_vol | 0.296689 |
| slippage_x3.sharpe | 3.512708 |
| slippage_x3.sortino | 4.097941 |
| slippage_x3.calmar | 5.394929 |
| slippage_x3.max_drawdown | -0.193178 |
| slippage_x3.profit_factor | 1.171629 |
| slippage_x3.hit_rate | 0.494473 |
| slippage_x3.bar_return_profit_factor | 1.171629 |
| slippage_x3.conventional_sharpe | 2.554030 |
| slippage_x3.return_over_vol_sharpe | 3.512708 |
| slippage_x3.profit_factor_scope | bar_returns |
| slippage_x3.metric_scope | bar_returns |
| slippage_x3.annualization_mode | fixed_periods |
| slippage_x3.sharpe_legacy_alias | return_over_vol_sharpe |
| slippage_x3.gross_pnl | 4.959869 |
| slippage_x3.net_pnl | 4.959869 |
| slippage_x3.total_cost | 0.0 |
| slippage_x3.cost_drag | 0.0 |
| slippage_x3.cost_to_gross_pnl | 0.0 |
| slippage_x3.gross_return_sum | 1.894384 |
| slippage_x3.net_return_sum | 1.894384 |
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
| delay_1_bars.cumulative_return | 4.445548 |
| delay_1_bars.annualized_return | 0.969775 |
| delay_1_bars.annualized_vol | 0.293868 |
| delay_1_bars.sharpe | 3.300036 |
| delay_1_bars.sortino | 3.918783 |
| delay_1_bars.calmar | 5.434424 |
| delay_1_bars.max_drawdown | -0.178450 |
| delay_1_bars.profit_factor | 1.164070 |
| delay_1_bars.hit_rate | 0.495338 |
| delay_1_bars.bar_return_profit_factor | 1.164070 |
| delay_1_bars.conventional_sharpe | 2.452909 |
| delay_1_bars.return_over_vol_sharpe | 3.300036 |
| delay_1_bars.profit_factor_scope | bar_returns |
| delay_1_bars.metric_scope | bar_returns |
| delay_1_bars.annualization_mode | fixed_periods |
| delay_1_bars.sharpe_legacy_alias | return_over_vol_sharpe |
| delay_1_bars.gross_pnl | 4.445548 |
| delay_1_bars.net_pnl | 4.445548 |
| delay_1_bars.total_cost | 0.0 |
| delay_1_bars.cost_drag | 0.0 |
| delay_1_bars.cost_to_gross_pnl | 0.0 |
| delay_1_bars.gross_return_sum | 1.802079 |
| delay_1_bars.net_return_sum | 1.802079 |
| delay_1_bars.cost_return_sum | 0.0 |
| delay_1_bars.avg_turnover | 0.0 |
| delay_1_bars.total_turnover | 0.0 |
| delay_1_bars.evaluation_scope | strict_oos_only |
| delay_1_bars.evaluation_start | 2022-03-14T15:00:00 |
| delay_1_bars.evaluation_end | 2024-09-17T10:30:00 |
| delay_1_bars.evaluation_rows | 43800 |
| delay_2_bars.cumulative_return | 4.789325 |
| delay_2_bars.annualized_return | 1.018604 |
| delay_2_bars.annualized_vol | 0.292463 |
| delay_2_bars.sharpe | 3.482851 |
| delay_2_bars.sortino | 4.094379 |
| delay_2_bars.calmar | 5.488941 |
| delay_2_bars.max_drawdown | -0.185574 |
| delay_2_bars.profit_factor | 1.171158 |
| delay_2_bars.hit_rate | 0.494674 |
| delay_2_bars.bar_return_profit_factor | 1.171158 |
| delay_2_bars.conventional_sharpe | 2.547008 |
| delay_2_bars.return_over_vol_sharpe | 3.482851 |
| delay_2_bars.profit_factor_scope | bar_returns |
| delay_2_bars.metric_scope | bar_returns |
| delay_2_bars.annualization_mode | fixed_periods |
| delay_2_bars.sharpe_legacy_alias | return_over_vol_sharpe |
| delay_2_bars.gross_pnl | 4.789325 |
| delay_2_bars.net_pnl | 4.789325 |
| delay_2_bars.total_cost | 0.0 |
| delay_2_bars.cost_drag | 0.0 |
| delay_2_bars.cost_to_gross_pnl | 0.0 |
| delay_2_bars.gross_return_sum | 1.862262 |
| delay_2_bars.net_return_sum | 1.862262 |
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
| min_active_period_cumulative_return | 0.381739 |
| median_active_period_cumulative_return | 1.068513 |
| mean_active_period_cumulative_return | 0.845158 |
| mean_active_period_sharpe | 4.049344 |
| std_active_period_sharpe | 1.906851 |
| worst_active_period_max_drawdown | -0.193178 |

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
| oos_prediction.mean | -0.022193 |
| oos_prediction.std | 0.983644 |
| oos_prediction.min | -4.706107 |
| oos_prediction.max | 4.005913 |
| oos_prediction.median | 0.001930 |
| oos_prediction.q01 | -2.524924 |
| oos_prediction.q05 | -1.695720 |
| oos_prediction.q25 | -0.621903 |
| oos_prediction.q75 | 0.609381 |
| oos_prediction.q95 | 1.558922 |
| oos_prediction.q99 | 2.287890 |
| oos_prediction.skew | -0.191320 |
| oos_prediction.kurtosis | 0.522426 |
| oos_prediction.positive_rate | 0.500662 |
| oos_prediction.negative_rate | 0.499338 |
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
| 1 | atr_48 | 1.100e+03 | 0.101510 | 10 | feature_importances_ |
| 2 | vol_rolling_192 | 1.079e+03 | 0.099473 | 10 | feature_importances_ |
| 3 | bollinger_bandwidth | 907.500000 | 0.083659 | 10 | feature_importances_ |
| 4 | vol_rolling_96 | 775.100000 | 0.071426 | 10 | feature_importances_ |
| 5 | ema_trend_48_192 | 741.300000 | 0.068409 | 10 | feature_importances_ |
| 6 | bollinger_bandwidth_rank_192 | 601.100000 | 0.055432 | 10 | feature_importances_ |
| 7 | atr_over_price_48 | 576.900000 | 0.053205 | 10 | feature_importances_ |
| 8 | vol_rolling_48 | 557.700000 | 0.051417 | 10 | feature_importances_ |
| 9 | atr_pct_rank_192 | 470.500000 | 0.043395 | 10 | feature_importances_ |
| 10 | vol_rolling_24 | 413.100000 | 0.038113 | 10 | feature_importances_ |
| 11 | mama_minus_fama_over_atr | 389.300000 | 0.035910 | 10 | feature_importances_ |
| 12 | close_over_bb_upper_192 | 292.400000 | 0.026973 | 10 | feature_importances_ |
| 13 | ret_48 | 289.800000 | 0.026720 | 10 | feature_importances_ |
| 14 | close_over_bb_mid_192 | 282.500000 | 0.026038 | 10 | feature_importances_ |
| 15 | bollinger_percent_b | 243.600000 | 0.022452 | 10 | feature_importances_ |
| 16 | distance_from_ema96_atr | 186.000000 | 0.017162 | 10 | feature_importances_ |
| 17 | close_over_vwap_48 | 177.300000 | 0.016340 | 10 | feature_importances_ |
| 18 | ret_24 | 168.300000 | 0.015519 | 10 | feature_importances_ |
| 19 | roofing_filter_over_atr | 161.100000 | 0.014860 | 10 | feature_importances_ |
| 20 | atr_pct | 138.400000 | 0.012757 | 10 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 5.328458 |
| net_pnl | 4.959869 |
| total_cost | 0.060000 |
| cost_drag | 0.368589 |
| cost_to_gross_pnl | 0.069174 |
| avg_turnover | 0.013699 |
| total_turnover | 600.000000 |
| mean_abs_signal | 0.042877 |
| signal_turnover | 0.050822 |
| flat_rate | 0.957123 |
| long_rate | 0.024543 |
| short_rate | 0.018333 |
| trade_rate | 0.165388 |
| executed_trade_count | 7244 |
| avg_signal_executed | 0.036030 |
| avg_pred_prob_executed | 0.507062 |
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
| 0 |  | 0.025804 | 0.021910 | 0.003800 | 0.351297 | 0.008676 |  |  |  |  |
| 1 |  | 0.409998 | 0.401564 | 0.006000 | 6.542464 | 0.013699 |  |  |  |  |
| 2 |  | 0.207994 | 0.203654 | 0.003600 | 3.586143 | 0.008219 |  |  |  |  |
| 3 |  | 0.312513 | 0.307013 | 0.004200 | 9.344546 | 0.009589 |  |  |  |  |
| 4 |  | 0.095462 | 0.091306 | 0.003800 | 2.682026 | 0.008676 |  |  |  |  |
| 5 |  | -0.020845 | -0.024559 | 0.003800 | -0.907324 | 0.008676 |  |  |  |  |
| 6 |  | -0.058084 | -0.061281 | 0.003400 | -1.526017 | 0.007763 |  |  |  |  |
| 7 |  | 0.117672 | 0.114323 | 0.003000 | 3.042601 | 0.006849 |  |  |  |  |
| 8 |  | 0.086320 | 0.082630 | 0.003400 | 2.142601 | 0.007763 |  |  |  |  |
| 9 |  | 0.145990 | 0.142554 | 0.003000 | 4.052153 | 0.006849 |  |  |  |  |


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
| unclassified | 36 | 3 | 0.083333 | 0.103939 | 1.187111 |
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
| 47 | close_over_vwap_48 |
| 48 | close_ret_over_vol_48 |
| 49 | close_ret_robust_z_192 |

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
- step: vwap
  params:
    high_col: high
    low_col: low
    close_col: close
    volume_col: volume
    windows:
    - 48
  outputs: {}
  enabled: true
  transforms:
    ratio:
      enabled: true
      items:
      - numerator_col: close
        denominator_col: vwap_48
        output_col: close_over_vwap_48
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
  - close_over_vwap_48
  - close_ret_over_vol_48
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
