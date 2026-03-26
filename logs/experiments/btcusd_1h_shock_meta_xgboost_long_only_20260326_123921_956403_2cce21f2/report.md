# Experiment Report: btcusd_1h_shock_meta_xgboost_long_only

## Overview
- Config path: `/workspace/config/experiments/btcusd_1h_shock_meta_xgboost_long_only.yaml`
- Model kind: `xgboost_clf`
- Symbols: `BTCUSD`
- Data source: `dukascopy_csv` at interval `1h`
- Data window: `2017-05-07 23:00:00` to `2024-12-31 13:00:00`
- Rows / columns: `58186` rows, `52` columns
- Target: `triple_barrier` horizon `n/a`
- Feature count: `12`
- Runtime seed: `7`

## Pipeline Trace

### 1. Entry Point
- `runner.run_experiment` -> `src.experiments.runner.run_experiment(config_path: 'str | Path') -> 'ExperimentResult'`
- `runner._load_asset_frames` -> `src.experiments.runner._load_asset_frames(data_cfg: 'dict[str, object]')`
- `pipeline.run_experiment_pipeline` -> `src.experiments.orchestration.pipeline.run_experiment_pipeline(config_path: 'str | Path', *, load_asset_frames_fn: 'LoadAssetFramesFn', save_processed_snapshot_fn: 'SaveProcessedFn') -> 'ExperimentResult'`

```yaml
config_path: /workspace/config/experiments/btcusd_1h_shock_meta_xgboost_long_only.yaml
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
- `experiments.contracts.validate_data_contract` -> `src.experiments.contracts.validate_data_contract(df: 'pd.DataFrame', contract: 'DataContract | None' = None) -> 'dict[str, int]'`
- `schemas.StorageContext` -> `src.experiments.schemas.StorageContext(symbols: 'list[str]', source: 'str | None', interval: 'str | None', start: 'str | None', end: 'str | None', pit: 'dict[str, Any]' = <factory>, pit_hash_sha256: 'str | None' = None) -> None`  
  Context object persisted into snapshot metadata.
- `data_stage.save_processed_snapshot_if_enabled` -> `src.experiments.orchestration.data_stage.save_processed_snapshot_if_enabled(asset_frames: 'dict[str, pd.DataFrame]', *, data_cfg: 'dict[str, Any]', config_hash_sha256: 'str', feature_steps: 'list[dict[str, Any]]') -> 'dict[str, Any] | None'`

```yaml
data:
  source: dukascopy_csv
  interval: 1h
  start: '2017-05-07 23:00:00'
  end: '2024-12-31 14:00:00'
  alignment: inner
  symbol: BTCUSD
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
    dataset_id: btcusd_1h_shock_meta_xgboost_long_only
    save_raw: false
    save_processed: true
    load_path: /workspace/data/raw/dukas_copy_bank/btcusd_h1.csv
    raw_dir: /workspace/data/raw
    processed_dir: /workspace/data/processed
```

### 3. Feature Engineering
- `feature_stage.apply_steps_to_assets` -> `src.experiments.orchestration.feature_stage.apply_steps_to_assets(asset_frames: 'dict[str, pd.DataFrame]', *, feature_steps: 'list[dict[str, Any]]') -> 'dict[str, pd.DataFrame]'`
- `feature_stage.apply_feature_steps` -> `src.experiments.orchestration.feature_stage.apply_feature_steps(df: 'pd.DataFrame', steps: 'list[dict[str, Any]]') -> 'pd.DataFrame'`
- `feature[returns]` -> `src.features.returns.add_close_returns(df: 'pd.DataFrame', log: 'bool' = False, col_name: 'str | None' = None) -> 'pd.DataFrame'`  
  params={'log': True, 'col_name': 'close_logret'}
- `feature[trend]` -> `src.features.technical.trend.add_trend_features(df: 'pd.DataFrame', price_col: 'str' = 'close', sma_windows: 'Sequence[int]' = (20, 50, 200), ema_spans: 'Sequence[int]' = (20, 50), inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'sma_windows': [], 'ema_spans': [24]}
- `feature[regime_context]` -> `src.features.regime_context.add_regime_context_features(df: 'pd.DataFrame', *, price_col: 'str' = 'close', returns_col: 'str' = 'close_ret', vol_short_window: 'int' = 24, vol_long_window: 'int' = 168, trend_fast_span: 'int' = 24, trend_slow_span: 'int' = 72, vol_ratio_high_threshold: 'float' = 1.25, vol_ratio_low_threshold: 'float' = 0.85) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'returns_col': 'close_logret', 'vol_short_window': 24, 'vol_long_window': 168, 'trend_fast_span': 24, 'trend_slow_span': 72, 'vol_ratio_high_threshold': 1.35, 'vol_ratio_low_threshold': 0.8}
- `feature[bollinger]` -> `src.features.technical.bollinger.add_bollinger_features(df: 'pd.DataFrame', price_col: 'str' = 'close', window: 'int' = 20, n_std: 'float' = 2.0, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'window': 24, 'n_std': 2.0}
- `feature[atr]` -> `src.features.technical.atr.add_atr_features(df: 'pd.DataFrame', high_col: 'str' = 'high', low_col: 'str' = 'low', close_col: 'str' = 'close', window: 'int' = 14, method: 'str' = 'wilder', add_over_price: 'bool' = True, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'high_col': 'high', 'low_col': 'low', 'close_col': 'close', 'window': 24, 'method': 'wilder', 'add_over_price': True}
- `feature[shock_context]` -> `src.features.shock_context.add_shock_context_features(df: 'pd.DataFrame', *, price_col: 'str' = 'close', high_col: 'str' = 'high', low_col: 'str' = 'low', returns_col: 'str' = 'close_logret', ema_col: 'str | None' = None, ema_window: 'int' = 24, atr_col: 'str | None' = None, atr_window: 'int' = 24, short_horizon: 'int' = 1, medium_horizon: 'int' = 4, vol_window: 'int' = 24, ret_z_threshold: 'float' = 2.0, atr_mult_threshold: 'float' = 1.5, distance_from_mean_threshold: 'float' = 1.0, post_shock_active_bars: 'int' = 1, use_log_returns: 'bool' = True, inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'high_col': 'high', 'low_col': 'low', 'returns_col': 'close_logret', 'ema_col': 'close_ema_24', 'atr_col': 'atr_24', 'short_horizon': 1, 'medium_horizon': 4, 'vol_window': 24, 'ret_z_threshold': 2.6, 'atr_mult_threshold': 1.75, 'distance_from_mean_threshold': 1.1, 'post_shock_active_bars': 4}
- `feature[rsi]` -> `src.features.technical.rsi.add_rsi_features(df: 'pd.DataFrame', price_col: 'str' = 'close', windows: 'Sequence[int]' = (14,), method: 'str' = 'wilder', inplace: 'bool' = False) -> 'pd.DataFrame'`  
  params={'price_col': 'close', 'windows': [2, 14], 'method': 'wilder'}
- `feature[lags]` -> `src.features.lags.add_lagged_features(df: 'pd.DataFrame', cols: 'Iterable[str]', lags: 'Sequence[int]' = (1, 2, 5), prefix: 'str' = 'lag') -> 'pd.DataFrame'`  
  params={'cols': ['close_logret'], 'lags': [1]}

```yaml
features:
- step: returns
  params:
    log: true
    col_name: close_logret
  enabled: true
- step: trend
  params:
    price_col: close
    sma_windows: []
    ema_spans:
    - 24
  enabled: true
- step: regime_context
  params:
    price_col: close
    returns_col: close_logret
    vol_short_window: 24
    vol_long_window: 168
    trend_fast_span: 24
    trend_slow_span: 72
    vol_ratio_high_threshold: 1.35
    vol_ratio_low_threshold: 0.8
  enabled: true
- step: bollinger
  params:
    price_col: close
    window: 24
    n_std: 2.0
  enabled: true
- step: atr
  params:
    high_col: high
    low_col: low
    close_col: close
    window: 24
    method: wilder
    add_over_price: true
  enabled: true
- step: shock_context
  params:
    price_col: close
    high_col: high
    low_col: low
    returns_col: close_logret
    ema_col: close_ema_24
    atr_col: atr_24
    short_horizon: 1
    medium_horizon: 4
    vol_window: 24
    ret_z_threshold: 2.6
    atr_mult_threshold: 1.75
    distance_from_mean_threshold: 1.1
    post_shock_active_bars: 4
  enabled: true
- step: rsi
  params:
    price_col: close
    windows:
    - 2
    - 14
    method: wilder
  enabled: true
- step: lags
  params:
    cols:
    - close_logret
    lags:
    - 1
  enabled: true
resolved_feature_columns:
- shock_ret_z_1h
- shock_ret_z_4h
- shock_atr_multiple_1h
- shock_atr_multiple_4h
- shock_distance_ema
- shock_strength
- regime_vol_ratio_24_168
- regime_absret_z_24_168
- bb_percent_b_24_2.0
- close_rsi_2
- close_rsi_14
- lag_close_logret_1
```

### 4. Model And Training
- `model_stage.apply_model_pipeline_to_assets` -> `src.experiments.orchestration.model_stage.apply_model_pipeline_to_assets(asset_frames: 'dict[str, pd.DataFrame]', *, model_cfg: 'dict[str, Any] | None', model_stages: 'list[dict[str, Any]] | None', returns_col: 'str | None') -> 'tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]'`
- `model_stage.apply_model_to_assets` -> `src.experiments.orchestration.model_stage.apply_model_to_assets(asset_frames: 'dict[str, pd.DataFrame]', *, model_cfg: 'dict[str, Any]', returns_col: 'str | None') -> 'tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]'`
- `feature_stage.apply_model_step` -> `src.experiments.orchestration.model_stage.apply_model_step(df: 'pd.DataFrame', model_cfg: 'dict[str, Any]', returns_col: 'str | None') -> 'tuple[pd.DataFrame, object | None, dict[str, Any]]'`
- `model[xgboost_clf]` -> `src.models.classification.train_xgboost_classifier(df: 'pd.DataFrame', model_cfg: 'dict[str, Any]', returns_col: 'str | None' = None) -> 'tuple[pd.DataFrame, object, dict[str, Any]]'`
- `modeling.runtime.resolve_runtime_for_model` -> `src.models.runtime.resolve_runtime_for_model(model_cfg: 'dict[str, Any]', model_params: 'dict[str, Any]', *, estimator_family: 'str') -> 'dict[str, Any]'`

```yaml
model:
  kind: xgboost_clf
  params:
    n_estimators: 350
    learning_rate: 0.03
    num_leaves: null
    max_depth: 4
    subsample: 0.9
    colsample_bytree: 0.9
    min_child_samples: null
    random_state: 7
    min_child_weight: 5.0
    reg_lambda: 1.0
    objective: binary:logistic
    eval_metric: logloss
    tree_method: hist
  preprocessing:
    scaler: none
  feature_cols:
  - shock_ret_z_1h
  - shock_ret_z_4h
  - shock_atr_multiple_1h
  - shock_atr_multiple_4h
  - shock_distance_ema
  - shock_strength
  - regime_vol_ratio_24_168
  - regime_absret_z_24_168
  - bb_percent_b_24_2.0
  - close_rsi_2
  - close_rsi_14
  - lag_close_logret_1
  target:
    kind: triple_barrier
    price_col: close
    open_col: open
    high_col: high
    low_col: low
    returns_col: close_logret
    max_holding: 24
    upper_mult: 1.5
    lower_mult: 1.5
    vol_window: 24
    neutral_label: drop
    side_col: shock_side_contrarian
    candidate_col: shock_down_candidate
    candidate_out_col: meta_candidate
  split:
    method: walk_forward
    train_size: 8760
    test_size: 336
    step_size: 336
    expanding: true
    max_folds: null
  runtime: {}
  env: {}
  use_features: true
  pred_prob_col: null
  pred_ret_col: null
  returns_input_col: null
  signal_col: null
  action_col: null
model_stages: []
resolved_reward_config:
  cost_per_turnover: 0.0005
  slippage_per_turnover: 0.00015
  inventory_penalty: 0.0
  drawdown_penalty: 0.0
  switching_penalty: 0.0
resolved_execution_config:
  backtest_min_holding_bars: 3
  min_holding_bars: 0
  action_hysteresis: 0.0
  dd_guard_enabled: true
  max_drawdown: 0.12
  cooloff_bars: 48
  rearm_drawdown: 0.08
```

### 5. Signal Stage
- `feature_stage.apply_signals_to_assets` -> `src.experiments.orchestration.feature_stage.apply_signals_to_assets(asset_frames: 'dict[str, pd.DataFrame]', *, signals_cfg: 'dict[str, Any]') -> 'dict[str, pd.DataFrame]'`
- `feature_stage.apply_signal_step` -> `src.experiments.orchestration.feature_stage.apply_signal_step(df: 'pd.DataFrame', signals_cfg: 'dict[str, Any]') -> 'pd.DataFrame'`
- `signal[probability_threshold]` -> `src.signals.probabilistic_signal.probabilistic_signal(df: 'pd.DataFrame', prob_col: 'str', signal_col: 'str | None' = None, upper: 'float' = 0.55, lower: 'float' = 0.45, upper_exit: 'float | None' = None, lower_exit: 'float | None' = None, mode: 'str' = 'long_short_hold', base_signal_col: 'str | None' = None) -> 'pd.Series'`  
  params={'prob_col': 'pred_prob', 'signal_col': 'signal_prob_threshold', 'base_signal_col': 'shock_side_contrarian_active', 'upper': 0.555, 'upper_exit': 0.49, 'lower': 0.43, 'lower_exit': 0.48, 'mode': 'long_only'}

```yaml
signals:
  kind: probability_threshold
  params:
    prob_col: pred_prob
    signal_col: signal_prob_threshold
    base_signal_col: shock_side_contrarian_active
    upper: 0.555
    upper_exit: 0.49
    lower: 0.43
    lower_exit: 0.48
    mode: long_only
```

### 6. Backtest
- `backtest_stage.run_single_asset_backtest` -> `src.experiments.orchestration.backtest_stage.run_single_asset_backtest(asset: 'str', df: 'pd.DataFrame', *, cfg: 'dict[str, Any]', model_meta: 'dict[str, Any]') -> 'BacktestResult'`
- `backtesting.engine.run_backtest` -> `src.backtesting.engine.run_backtest(df: 'pd.DataFrame', signal_col: 'str', returns_col: 'str', returns_type: "Literal['simple', 'log']" = 'simple', missing_return_policy: 'str' = 'raise_if_exposed', cost_per_unit_turnover: 'float' = 0.0, slippage_per_unit_turnover: 'float' = 0.0, target_vol: 'Optional[float]' = None, vol_col: 'Optional[str]' = None, max_leverage: 'float' = 3.0, dd_guard: 'bool' = True, max_drawdown: 'float' = 0.2, cooloff_bars: 'int' = 20, rearm_drawdown: 'Optional[float]' = None, periods_per_year: 'int' = 252, min_holding_bars: 'int' = 0) -> 'BacktestResult'`
- `backtesting.engine.BacktestResult` -> `src.backtesting.engine.BacktestResult(equity_curve: 'pd.Series', returns: 'pd.Series', gross_returns: 'pd.Series', costs: 'pd.Series', positions: 'pd.Series', turnover: 'pd.Series', summary: 'dict') -> None`

```yaml
backtest:
  returns_col: close_logret
  signal_col: signal_prob_threshold
  periods_per_year: 8760
  returns_type: log
  missing_return_policy: raise_if_exposed
  min_holding_bars: 3
  subset: test
  vol_col: null
risk:
  cost_per_turnover: 0.0005
  slippage_per_turnover: 0.00015
  target_vol: null
  max_leverage: 1.0
  dd_guard:
    enabled: true
    max_drawdown: 0.12
    rearm_drawdown: 0.08
    cooloff_bars: 48
  vol_col: null
portfolio:
  enabled: false
  construction: signal_weights
  gross_target: 1.0
  long_short: false
  expected_return_col: null
  covariance_window: 60
  covariance_rebalance_step: 1
  risk_aversion: 5.0
  trade_aversion: 0.0
  constraints: {}
  asset_groups: {}
```

### 7. Monitoring And Execution
- `reporting.compute_monitoring_report` -> `src.experiments.orchestration.reporting.compute_monitoring_report(asset_frames: 'dict[str, pd.DataFrame]', *, model_meta: 'dict[str, Any]', monitoring_cfg: 'dict[str, Any]') -> 'dict[str, Any]'`
- `execution_stage.build_execution_output` -> `src.experiments.orchestration.execution_stage.build_execution_output(*, asset_frames: 'dict[str, pd.DataFrame]', execution_cfg: 'dict[str, object]', portfolio_weights: 'pd.DataFrame | None', performance: 'BacktestResult | PortfolioPerformance', alignment: 'str') -> 'tuple[dict[str, object], pd.DataFrame | None]'`
- `schemas.MonitoringPayload` -> `src.experiments.schemas.MonitoringPayload(asset_count: 'int', drifted_feature_count: 'int', feature_count: 'int', per_asset: 'dict[str, Any]' = <factory>) -> None`
- `schemas.ExecutionPayload` -> `src.experiments.schemas.ExecutionPayload(mode: 'str', capital: 'float', as_of: 'str | None', order_count: 'int', gross_target: 'float', extra: 'dict[str, Any]' = <factory>) -> None`
- `reporting.build_single_asset_evaluation` -> `src.experiments.orchestration.reporting.build_single_asset_evaluation(asset: 'str', df: 'pd.DataFrame', *, performance: 'BacktestResult', model_meta: 'dict[str, Any]', periods_per_year: 'int') -> 'dict[str, Any]'`
- `schemas.EvaluationPayload` -> `src.experiments.schemas.EvaluationPayload(scope: 'str', primary_summary: 'dict[str, Any]', timeline_summary: 'dict[str, Any]', oos_only_summary: 'dict[str, Any] | None' = None, extra: 'dict[str, Any]' = <factory>) -> None`

```yaml
monitoring:
  enabled: true
  psi_threshold: 0.15
  n_bins: 10
execution:
  enabled: false
  mode: paper
  capital: 1000000.0
  price_col: close
  min_trade_notional: 0.0
  current_weights: {}
  current_prices: {}
```

### 8. Artifact And Report
- `artifacts.save_artifacts` -> `src.experiments.orchestration.artifacts.save_artifacts(*, run_dir: 'Path', cfg: 'dict[str, Any]', data: 'pd.DataFrame | dict[str, pd.DataFrame]', performance: 'BacktestResult | PortfolioPerformance', model_meta: 'dict[str, Any]', evaluation: 'dict[str, Any]', monitoring: 'dict[str, Any]', execution: 'dict[str, Any]', execution_orders: 'pd.DataFrame | None', portfolio_weights: 'pd.DataFrame | None', portfolio_diagnostics: 'pd.DataFrame | None', portfolio_meta: 'dict[str, Any]', storage_meta: 'dict[str, Any]', run_metadata: 'dict[str, Any]', config_hash_sha256: 'str', data_fingerprint: 'dict[str, Any]', stage_tails: 'dict[str, Any] | None' = None) -> 'dict[str, str]'`
- `artifacts.write_experiment_report_from_run_dir` -> `src.experiments.orchestration.artifacts.write_experiment_report_from_run_dir(run_dir: 'Path') -> 'dict[str, str]'`
- `reporting.build_experiment_report_markdown` -> `src.experiments.orchestration.reporting.build_experiment_report_markdown(*, cfg: 'dict[str, Any]', summary_payload: 'dict[str, Any]', run_metadata: 'dict[str, Any]', chart_paths: 'dict[str, str]', artifact_paths: 'dict[str, str]') -> 'str'`

## Primary Summary
| Metric | Value |
| --- | --- |
| cumulative_return | -0.004430 |
| annualized_return | -0.000787 |
| annualized_vol | 0.107629 |
| sharpe | -0.007308 |
| sortino | -0.010609 |
| calmar | -0.003433 |
| max_drawdown | -0.229120 |
| profit_factor | 1.013471 |
| hit_rate | 0.430310 |
| avg_turnover | 0.007122 |
| total_turnover | 352.000000 |
| gross_pnl | 0.256994 |
| net_pnl | 0.028194 |
| total_cost | 0.228800 |
| cost_drag | 0.228800 |
| cost_to_gross_pnl | 0.890295 |


## Stage Tail Trace

### raw_loaded
| Metric | Value |
| --- | --- |
| asset_count | 1 |
| shown_asset_count | 1 |
| tail_limit | 10 |
| max_columns | 18 |
| max_assets | 1 |

#### Asset: BTCUSD
| Metric | Value |
| --- | --- |
| rows | 58186 |
| row_delta | 58186 |
| column_count | 5 |
| column_delta | 5 |
| added_columns | open, high, low, close, volume |
| removed_columns |  |
| shown_columns | timestamp, open, high, low, close, volume |
| truncated_columns |  |


```text
          timestamp    open    high     low   close  volume
2024-12-31 04:00:00 92303.6 92593.3 92172.7 92256.9  0.0143
2024-12-31 05:00:00 92243.5 92559.2 92160.0 92412.2  0.0160
2024-12-31 06:00:00 92413.9 92838.7 92397.1 92642.5  0.0142
2024-12-31 07:00:00 92647.2 92743.9 92611.7 92693.6  0.0119
2024-12-31 08:00:00 92693.1 94475.3 92674.7 93734.7  0.0212
2024-12-31 09:00:00 93729.2 93954.2 93641.0 93822.5  0.0243
2024-12-31 10:00:00 93825.2 94073.5 93471.7 93925.1  0.0231
2024-12-31 11:00:00 93924.6 94098.2 93808.3 94040.7  0.0160
2024-12-31 12:00:00 94041.0 94762.9 94040.7 94366.0  0.0217
2024-12-31 13:00:00 94365.6 95850.8 94360.0 95411.2  0.0258
```

### features_applied
| Metric | Value |
| --- | --- |
| asset_count | 1 |
| shown_asset_count | 1 |
| tail_limit | 10 |
| max_columns | 18 |
| max_assets | 1 |

#### Asset: BTCUSD
| Metric | Value |
| --- | --- |
| rows | 58186 |
| row_delta | 0 |
| column_count | 40 |
| column_delta | 35 |
| added_columns | close_logret, close_ema_24, close_over_ema_24, regime_vol_ratio_24_168, regime_high_vol_state_24_168, regime_low_vol_state_24_168, regime_vol_ratio_z_24_168, regime_trend_ratio_24_72, regime_trend_state_24_72, regime_absret_z_24_168, bb_ma_24, bb_upper_24_2.0, bb_lower_24_2.0, bb_width_24_2.0, bb_percent_b_24_2.0, atr_24, atr_over_price_24, shock_ret_1h, shock_ret_4h, shock_ret_z_1h, shock_ret_z_4h, shock_atr_multiple_1h, shock_atr_multiple_4h, shock_distance_ema, shock_up_candidate, shock_down_candidate, shock_candidate, shock_side_contrarian, shock_side_contrarian_active, shock_active_window, shock_strength, bars_since_shock, close_rsi_2, close_rsi_14, lag_close_logret_1 |
| removed_columns |  |
| shown_columns | timestamp, open, high, low, close, volume, close_logret, close_ema_24, close_over_ema_24, regime_vol_ratio_24_168, regime_high_vol_state_24_168, regime_low_vol_state_24_168, regime_vol_ratio_z_24_168, regime_trend_ratio_24_72, regime_trend_state_24_72, regime_absret_z_24_168, bb_ma_24, bb_upper_24_2.0 |
| truncated_columns | bb_lower_24_2.0, bb_width_24_2.0, bb_percent_b_24_2.0, atr_24, atr_over_price_24, shock_ret_1h, shock_ret_4h, shock_ret_z_1h, shock_ret_z_4h, shock_atr_multiple_1h, shock_atr_multiple_4h, shock_distance_ema, shock_up_candidate, shock_down_candidate, shock_candidate, shock_side_contrarian, shock_side_contrarian_active, shock_active_window, shock_strength, bars_since_shock, close_rsi_2, close_rsi_14, lag_close_logret_1 |


```text
          timestamp    open    high     low   close  volume  close_logret  close_ema_24  close_over_ema_24  regime_vol_ratio_24_168  regime_high_vol_state_24_168  regime_low_vol_state_24_168  regime_vol_ratio_z_24_168  regime_trend_ratio_24_72  regime_trend_state_24_72  regime_absret_z_24_168     bb_ma_24  bb_upper_24_2.0
2024-12-31 04:00:00 92303.6 92593.3 92172.7 92256.9  0.0143     -0.000496  92907.553392          -0.007003                 1.472636                           1.0                          0.0                   2.442034                 -0.009212                      -1.0                0.252469 92978.441667     94675.289473
2024-12-31 05:00:00 92243.5 92559.2 92160.0 92412.2  0.0160      0.001682  92867.925120          -0.004907                 1.481554                           1.0                          0.0                   2.424699                 -0.009241                      -1.0                0.251418 92940.137500     94644.862369
2024-12-31 06:00:00 92413.9 92838.7 92397.1 92642.5  0.0142      0.002489  92849.891111          -0.002234                 1.502966                           1.0                          0.0                   2.451223                 -0.009117                      -1.0                0.259810 92897.833333     94579.455490
2024-12-31 07:00:00 92647.2 92743.9 92611.7 92693.6  0.0119      0.000551  92837.387822          -0.001549                 1.504046                           1.0                          0.0                   2.410093                 -0.008958                      -1.0                0.253222 92863.370833     94526.318162
2024-12-31 08:00:00 92693.1 94475.3 92674.7 93734.7  0.0212      0.011169  92909.172796           0.008885                 1.552117                           1.0                          0.0                   2.516175                 -0.008208                      -1.0                0.343335 92867.583333     94538.805370
2024-12-31 09:00:00 93729.2 93954.2 93641.0 93822.5  0.0243      0.000936  92982.238972           0.009037                 1.555773                           1.0                          0.0                   2.477366                 -0.007470                      -1.0                0.353161 92873.554167     94557.309255
2024-12-31 10:00:00 93825.2 94073.5 93471.7 93925.1  0.0231      0.001093  93057.667855           0.009321                 1.556315                           1.0                          0.0                   2.430637                 -0.006736                      -1.0                0.356964 92887.083333     94598.965243
2024-12-31 11:00:00 93924.6 94098.2 93808.3 94040.7  0.0160      0.001230  93136.310426           0.009710                 1.559241                           1.0                          0.0                   2.389332                 -0.005999                      -1.0                0.361214 92900.591667     94643.279152
2024-12-31 12:00:00 94041.0 94762.9 94040.7 94366.0  0.0217      0.003453  93234.685592           0.012134                 1.561246                           1.0                          0.0                   2.347199                 -0.005143                      -1.0                0.379353 92932.979167     94752.801124
2024-12-31 13:00:00 94365.6 95850.8 94360.0 95411.2  0.0258      0.011015  93408.806745           0.021437                 1.507810                           1.0                          0.0                   2.145916                 -0.003779                      -1.0                0.350289 93055.908333     95114.490110
```

### model_applied
| Metric | Value |
| --- | --- |
| asset_count | 1 |
| shown_asset_count | 1 |
| tail_limit | 10 |
| max_columns | 18 |
| max_assets | 1 |

#### Asset: BTCUSD
| Metric | Value |
| --- | --- |
| rows | 58186 |
| row_delta | 0 |
| column_count | 51 |
| column_delta | 11 |
| added_columns | triple_barrier_vol_24, meta_candidate, label_meta_side, label_oriented_ret, tb_event_ret, label, label_hit_step, label_upper_barrier, label_lower_barrier, pred_prob, pred_is_oos |
| removed_columns |  |
| shown_columns | timestamp, open, high, low, close, volume, triple_barrier_vol_24, meta_candidate, label_meta_side, label_oriented_ret, tb_event_ret, label, label_hit_step, label_upper_barrier, label_lower_barrier, pred_prob, pred_is_oos, close_logret |
| truncated_columns | close_ema_24, close_over_ema_24, regime_vol_ratio_24_168, regime_high_vol_state_24_168, regime_low_vol_state_24_168, regime_vol_ratio_z_24_168, regime_trend_ratio_24_72, regime_trend_state_24_72, regime_absret_z_24_168, bb_ma_24, bb_upper_24_2.0, bb_lower_24_2.0, bb_width_24_2.0, bb_percent_b_24_2.0, atr_24, atr_over_price_24, shock_ret_1h, shock_ret_4h, shock_ret_z_1h, shock_ret_z_4h, shock_atr_multiple_1h, shock_atr_multiple_4h, shock_distance_ema, shock_up_candidate, shock_down_candidate, shock_candidate, shock_side_contrarian, shock_side_contrarian_active, shock_active_window, shock_strength, bars_since_shock, close_rsi_2, close_rsi_14, lag_close_logret_1 |


```text
          timestamp    open    high     low   close  volume  triple_barrier_vol_24  meta_candidate  label_meta_side  label_oriented_ret  tb_event_ret  label  label_hit_step  label_upper_barrier  label_lower_barrier  pred_prob  pred_is_oos  close_logret
2024-12-31 04:00:00 92303.6 92593.3 92172.7 92256.9  0.0143               0.007727             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True     -0.000496
2024-12-31 05:00:00 92243.5 92559.2 92160.0 92412.2  0.0160               0.007708             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.001682
2024-12-31 06:00:00 92413.9 92838.7 92397.1 92642.5  0.0142               0.007689             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.002489
2024-12-31 07:00:00 92647.2 92743.9 92611.7 92693.6  0.0119               0.007688             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.000551
2024-12-31 08:00:00 92693.1 94475.3 92674.7 93734.7  0.0212               0.008038             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.011169
2024-12-31 09:00:00 93729.2 93954.2 93641.0 93822.5  0.0243               0.008040             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.000936
2024-12-31 10:00:00 93825.2 94073.5 93471.7 93925.1  0.0231               0.008040             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.001093
2024-12-31 11:00:00 93924.6 94098.2 93808.3 94040.7  0.0160               0.008040             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.001230
2024-12-31 12:00:00 94041.0 94762.9 94040.7 94366.0  0.0217               0.008061             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.003453
2024-12-31 13:00:00 94365.6 95850.8 94360.0 95411.2  0.0258               0.007886             0.0              0.0                 NaN           NaN    NaN             NaN                  NaN                  NaN        NaN         True      0.011015
```

### signals_applied
| Metric | Value |
| --- | --- |
| asset_count | 1 |
| shown_asset_count | 1 |
| tail_limit | 10 |
| max_columns | 18 |
| max_assets | 1 |

#### Asset: BTCUSD
| Metric | Value |
| --- | --- |
| rows | 58186 |
| row_delta | 0 |
| column_count | 52 |
| column_delta | 1 |
| added_columns | signal_prob_threshold |
| removed_columns |  |
| shown_columns | timestamp, open, high, low, close, volume, signal_prob_threshold, close_logret, pred_is_oos, pred_prob, close_ema_24, close_over_ema_24, regime_vol_ratio_24_168, regime_high_vol_state_24_168, regime_low_vol_state_24_168, regime_vol_ratio_z_24_168, regime_trend_ratio_24_72, regime_trend_state_24_72 |
| truncated_columns | regime_absret_z_24_168, bb_ma_24, bb_upper_24_2.0, bb_lower_24_2.0, bb_width_24_2.0, bb_percent_b_24_2.0, atr_24, atr_over_price_24, shock_ret_1h, shock_ret_4h, shock_ret_z_1h, shock_ret_z_4h, shock_atr_multiple_1h, shock_atr_multiple_4h, shock_distance_ema, shock_up_candidate, shock_down_candidate, shock_candidate, shock_side_contrarian, shock_side_contrarian_active, shock_active_window, shock_strength, bars_since_shock, close_rsi_2, close_rsi_14, lag_close_logret_1, triple_barrier_vol_24, meta_candidate, label_meta_side, label_oriented_ret, tb_event_ret, label, label_hit_step, label_upper_barrier, label_lower_barrier |


```text
          timestamp    open    high     low   close  volume  signal_prob_threshold  close_logret  pred_is_oos  pred_prob  close_ema_24  close_over_ema_24  regime_vol_ratio_24_168  regime_high_vol_state_24_168  regime_low_vol_state_24_168  regime_vol_ratio_z_24_168  regime_trend_ratio_24_72  regime_trend_state_24_72
2024-12-31 04:00:00 92303.6 92593.3 92172.7 92256.9  0.0143                    0.0     -0.000496         True        NaN  92907.553392          -0.007003                 1.472636                           1.0                          0.0                   2.442034                 -0.009212                      -1.0
2024-12-31 05:00:00 92243.5 92559.2 92160.0 92412.2  0.0160                    0.0      0.001682         True        NaN  92867.925120          -0.004907                 1.481554                           1.0                          0.0                   2.424699                 -0.009241                      -1.0
2024-12-31 06:00:00 92413.9 92838.7 92397.1 92642.5  0.0142                    0.0      0.002489         True        NaN  92849.891111          -0.002234                 1.502966                           1.0                          0.0                   2.451223                 -0.009117                      -1.0
2024-12-31 07:00:00 92647.2 92743.9 92611.7 92693.6  0.0119                    0.0      0.000551         True        NaN  92837.387822          -0.001549                 1.504046                           1.0                          0.0                   2.410093                 -0.008958                      -1.0
2024-12-31 08:00:00 92693.1 94475.3 92674.7 93734.7  0.0212                    0.0      0.011169         True        NaN  92909.172796           0.008885                 1.552117                           1.0                          0.0                   2.516175                 -0.008208                      -1.0
2024-12-31 09:00:00 93729.2 93954.2 93641.0 93822.5  0.0243                    0.0      0.000936         True        NaN  92982.238972           0.009037                 1.555773                           1.0                          0.0                   2.477366                 -0.007470                      -1.0
2024-12-31 10:00:00 93825.2 94073.5 93471.7 93925.1  0.0231                    0.0      0.001093         True        NaN  93057.667855           0.009321                 1.556315                           1.0                          0.0                   2.430637                 -0.006736                      -1.0
2024-12-31 11:00:00 93924.6 94098.2 93808.3 94040.7  0.0160                    0.0      0.001230         True        NaN  93136.310426           0.009710                 1.559241                           1.0                          0.0                   2.389332                 -0.005999                      -1.0
2024-12-31 12:00:00 94041.0 94762.9 94040.7 94366.0  0.0217                    0.0      0.003453         True        NaN  93234.685592           0.012134                 1.561246                           1.0                          0.0                   2.347199                 -0.005143                      -1.0
2024-12-31 13:00:00 94365.6 95850.8 94360.0 95411.2  0.0258                    0.0      0.011015         True        NaN  93408.806745           0.021437                 1.507810                           1.0                          0.0                   2.145916                 -0.003779                      -1.0
```

## Model OOS Diagnostics
| Metric | Value |
| --- | --- |
| classification.evaluation_rows | 804 |
| classification.positive_rate | 0.455224 |
| classification.accuracy | 0.531095 |
| classification.brier | 0.282514 |
| classification.roc_auc | 0.510433 |
| classification.log_loss | 0.778505 |
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
| oos_rows | 49426 |
| predicted_rows | 806 |
| non_oos_prediction_rows | 0 |
| missing_oos_prediction_rows | 48620 |
| oos_prediction_coverage | 0.016307 |
| alignment_ok | true |
| first_prediction_index | 2018-10-25T01:00:00 |
| last_prediction_index | 2024-12-30T21:00:00 |
| prediction_distribution.rows | 806 |
| prediction_distribution.mean | 0.440455 |
| prediction_distribution.std | 0.194176 |
| prediction_distribution.min | 0.035834 |
| prediction_distribution.max | 0.951766 |
| prediction_distribution.median | 0.428162 |
| prediction_distribution.q05 | 0.145193 |
| prediction_distribution.q95 | 0.778624 |
| prediction_distribution.positive_rate | 1.000000 |
| prediction_distribution.negative_rate | 0.0 |
| prediction_distribution.zero_rate | 0.0 |
| target_distribution.rows | 804 |
| target_distribution.mean | 0.455224 |
| target_distribution.std | 0.498301 |
| target_distribution.min | 0.0 |
| target_distribution.max | 1.000000 |
| target_distribution.median | 0.0 |
| target_distribution.q05 | 0.0 |
| target_distribution.q95 | 1.000000 |
| target_distribution.positive_rate | 0.455224 |
| target_distribution.negative_rate | 0.0 |
| target_distribution.zero_rate | 0.544776 |
| probability_distribution.rows | 806 |
| probability_distribution.mean | 0.440455 |
| probability_distribution.std | 0.194176 |
| probability_distribution.min | 0.035834 |
| probability_distribution.max | 0.951766 |
| probability_distribution.median | 0.428162 |
| probability_distribution.q05 | 0.145193 |
| probability_distribution.q95 | 0.778624 |
| probability_distribution.positive_rate | 1.000000 |
| probability_distribution.negative_rate | 0.0 |
| probability_distribution.zero_rate | 0.0 |


## Missing-Value Diagnostics
| Metric | Value |
| --- | --- |
| train_rows_dropped_missing | 4862853 |
| test_rows_missing_features | 48620 |
| folds_with_zero_predictions | 1 |


## Label Distribution
| Metric | Value |
| --- | --- |
| oos_evaluation.labeled_rows | 804 |
| oos_evaluation.class_counts.0 | 438 |
| oos_evaluation.class_counts.1 | 366 |
| oos_evaluation.positive_rate | 0.455224 |
| oos_evaluation.negative_rate | 0.544776 |
| train.labeled_rows | 85083 |
| train.class_counts.0 | 46447 |
| train.class_counts.1 | 38636 |
| train.positive_rate | 0.454098 |
| train.negative_rate | 0.545902 |


## Feature Importance
| Rank | Feature | Mean Importance | Mean Importance Normalized | Fold Count | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | regime_vol_ratio_24_168 | 0.095488 | 0.095488 | 148 | feature_importances_ |
| 2 | lag_close_logret_1 | 0.088481 | 0.088481 | 148 | feature_importances_ |
| 3 | regime_absret_z_24_168 | 0.087908 | 0.087908 | 148 | feature_importances_ |
| 4 | shock_atr_multiple_1h | 0.086257 | 0.086257 | 148 | feature_importances_ |
| 5 | shock_distance_ema | 0.083529 | 0.083529 | 148 | feature_importances_ |
| 6 | shock_strength | 0.082574 | 0.082574 | 148 | feature_importances_ |
| 7 | shock_atr_multiple_4h | 0.082060 | 0.082060 | 148 | feature_importances_ |
| 8 | close_rsi_14 | 0.081850 | 0.081850 | 148 | feature_importances_ |
| 9 | bb_percent_b_24_2.0 | 0.080111 | 0.080111 | 148 | feature_importances_ |
| 10 | close_rsi_2 | 0.079096 | 0.079096 | 148 | feature_importances_ |
| 11 | shock_ret_z_4h | 0.077127 | 0.077127 | 148 | feature_importances_ |
| 12 | shock_ret_z_1h | 0.075517 | 0.075517 | 148 | feature_importances_ |


## Cost / Exposure / Turnover
| Metric | Value |
| --- | --- |
| gross_pnl | 0.256994 |
| net_pnl | 0.028194 |
| total_cost | 0.228800 |
| cost_drag | 0.228800 |
| cost_to_gross_pnl | 0.890295 |
| avg_turnover | 0.007122 |
| total_turnover | 352.000000 |
| mean_abs_signal |  |
| signal_turnover |  |
| flat_rate |  |

## Diagnostics
- The policy never meaningfully abstains; it chooses direction almost all the time instead of learning a true hold state.
- Fold outcomes are mixed, which points to regime dependence rather than a stable cross-period edge.
- Feature drift is present in OOS inputs; the largest drifted features are lag_close_logret_1.

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
| 0 | 336 | -0.001355 | -0.002655 | 0.001300 | -4.046683 | 0.005952 |  |  |  |  |
| 1 | 336 | -0.123261 | -0.125861 | 0.002600 | -2.295339 | 0.011905 |  |  |  |  |
| 2 | 336 | 0.008108 | 0.006808 | 0.001300 | 3.017973 | 0.005952 |  |  |  |  |
| 3 | 336 | 0.035336 | 0.031436 | 0.003900 | 12.908118 | 0.017857 |  |  |  |  |
| 4 | 336 | -0.009873 | -0.015073 | 0.005200 | -3.052914 | 0.023810 |  |  |  |  |
| 5 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 6 | 336 | -0.000523 | -0.003123 | 0.002600 | -2.329232 | 0.011905 |  |  |  |  |
| 7 | 336 | 0.013273 | 0.010673 | 0.002600 | 7.233250 | 0.011905 |  |  |  |  |
| 8 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 9 | 336 | 0.010220 | 0.008920 | 0.001300 | 2.831544 | 0.005952 |  |  |  |  |
| 10 | 336 | -0.000178 | -0.001478 | 0.001300 | -0.382205 | 0.005952 |  |  |  |  |
| 11 | 336 | 0.018944 | 0.016344 | 0.002600 | 4.800575 | 0.011905 |  |  |  |  |
| 12 | 336 | 0.015070 | 0.013770 | 0.001300 | 2.489494 | 0.005952 |  |  |  |  |
| 13 | 336 | -0.086807 | -0.092007 | 0.005200 | -4.401068 | 0.023810 |  |  |  |  |
| 14 | 336 | 0.0 | -0.000650 | 0.000650 | -5.064630 | 0.002976 |  |  |  |  |
| 15 | 336 | -0.004804 | -0.006754 | 0.001950 | -2.480343 | 0.008929 |  |  |  |  |
| 16 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 17 | 336 | 0.053386 | 0.049486 | 0.003900 | 10.764065 | 0.017857 |  |  |  |  |
| 18 | 336 | -0.004344 | -0.006944 | 0.002600 | -3.054283 | 0.011905 |  |  |  |  |
| 19 | 336 | -0.013890 | -0.017790 | 0.003900 | -2.857217 | 0.017857 |  |  |  |  |
| 20 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 21 | 336 | -0.004126 | -0.005426 | 0.001300 | -3.492450 | 0.005952 |  |  |  |  |
| 22 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 23 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 24 | 336 | 0.018802 | 0.014902 | 0.003900 | 5.451813 | 0.017857 |  |  |  |  |
| 25 | 336 | -0.018857 | -0.020157 | 0.001300 | -3.820948 | 0.005952 |  |  |  |  |
| 26 | 336 | 0.006159 | 0.004859 | 0.001300 | 2.375986 | 0.005952 |  |  |  |  |
| 27 | 336 | 0.015873 | 0.014573 | 0.001300 | 7.187561 | 0.005952 |  |  |  |  |
| 28 | 336 | -0.002154 | -0.003454 | 0.001300 | -1.206923 | 0.005952 |  |  |  |  |
| 29 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 30 | 336 | -0.009260 | -0.011860 | 0.002600 | -3.018003 | 0.011905 |  |  |  |  |
| 31 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 32 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 33 | 336 | 0.009871 | 0.007271 | 0.002600 | 2.292237 | 0.011905 |  |  |  |  |
| 34 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 35 | 336 | -4.778e-05 | -0.001348 | 0.001300 | -1.477726 | 0.005952 |  |  |  |  |
| 36 | 336 | -0.012665 | -0.015265 | 0.002600 | -2.841915 | 0.011905 |  |  |  |  |
| 37 | 336 | 0.006972 | 0.005672 | 0.001300 | 5.941988 | 0.005952 |  |  |  |  |
| 38 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 39 | 336 | 0.036580 | 0.033980 | 0.002600 | 14.090583 | 0.011905 |  |  |  |  |
| 40 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 41 | 336 | 0.025615 | 0.024315 | 0.001300 | 5.257578 | 0.005952 |  |  |  |  |
| 42 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 43 | 336 | 0.143834 | 0.141234 | 0.002600 | 99.995535 | 0.011905 |  |  |  |  |
| 44 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 45 | 336 | 0.015784 | 0.013184 | 0.002600 | 1.686756 | 0.011905 |  |  |  |  |
| 46 | 336 | 0.020456 | 0.017856 | 0.002600 | 2.675443 | 0.011905 |  |  |  |  |
| 47 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 48 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 49 | 336 | -0.010130 | -0.011430 | 0.001300 | -3.927491 | 0.005952 |  |  |  |  |
| 50 | 336 | 0.002525 | 0.001225 | 0.001300 | 0.807425 | 0.005952 |  |  |  |  |
| 51 | 336 | 0.057791 | 0.056491 | 0.001300 | 14.308875 | 0.005952 |  |  |  |  |
| 52 | 336 | -0.020958 | -0.023558 | 0.002600 | -2.271985 | 0.011905 |  |  |  |  |
| 53 | 336 | 0.131868 | 0.129268 | 0.002600 | 50.319734 | 0.011905 |  |  |  |  |
| 54 | 336 | -0.006412 | -0.007712 | 0.001300 | -3.341646 | 0.005952 |  |  |  |  |
| 55 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 56 | 336 | -0.006033 | -0.007333 | 0.001300 | -4.702308 | 0.005952 |  |  |  |  |
| 57 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 58 | 336 | -0.001728 | -0.003028 | 0.001300 | -1.570587 | 0.005952 |  |  |  |  |
| 59 | 336 | -0.004086 | -0.006686 | 0.002600 | -2.979004 | 0.011905 |  |  |  |  |
| 60 | 336 | 0.006374 | 0.003774 | 0.002600 | 0.691089 | 0.011905 |  |  |  |  |
| 61 | 336 | 0.005914 | 0.004614 | 0.001300 | 3.782221 | 0.005952 |  |  |  |  |
| 62 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 63 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 64 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 65 | 336 | -0.013551 | -0.014851 | 0.001300 | -2.307383 | 0.005952 |  |  |  |  |
| 66 | 336 | 0.012271 | 0.010971 | 0.001300 | 7.061045 | 0.005952 |  |  |  |  |
| 67 | 336 | -0.056787 | -0.058087 | 0.001300 | -2.874601 | 0.005952 |  |  |  |  |
| 68 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 69 | 336 | 0.010639 | 0.008039 | 0.002600 | 2.122201 | 0.011905 |  |  |  |  |
| 70 | 336 | -0.039962 | -0.045162 | 0.005200 | -2.539580 | 0.023810 |  |  |  |  |
| 71 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 72 | 336 | 0.003885 | 0.001935 | 0.001950 | 0.159095 | 0.008929 |  |  |  |  |
| 73 | 336 | 0.034981 | 0.029131 | 0.005850 | 7.430260 | 0.026786 |  |  |  |  |
| 74 | 336 | 0.011044 | 0.009744 | 0.001300 | 7.740062 | 0.005952 |  |  |  |  |
| 75 | 336 | 0.007837 | 0.006537 | 0.001300 | 7.612191 | 0.005952 |  |  |  |  |
| 76 | 336 | -0.001672 | -0.004272 | 0.002600 | -1.683707 | 0.011905 |  |  |  |  |
| 77 | 336 | -0.011815 | -0.014415 | 0.002600 | -4.820977 | 0.011905 |  |  |  |  |
| 78 | 336 | -0.027205 | -0.029805 | 0.002600 | -4.491061 | 0.011905 |  |  |  |  |
| 79 | 336 | -0.004537 | -0.005837 | 0.001300 | -3.113854 | 0.005952 |  |  |  |  |
| 80 | 336 | 0.083919 | 0.080019 | 0.003900 | 23.042659 | 0.017857 |  |  |  |  |
| 81 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 82 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 83 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 84 | 336 | 0.005887 | 0.003287 | 0.002600 | 2.693458 | 0.011905 |  |  |  |  |
| 85 | 336 | -0.002060 | -0.003360 | 0.001300 | -4.908444 | 0.005952 |  |  |  |  |
| 86 | 336 | -0.020964 | -0.024864 | 0.003900 | -3.743964 | 0.017857 |  |  |  |  |
| 87 | 336 | 0.006676 | 0.005376 | 0.001300 | 5.221983 | 0.005952 |  |  |  |  |
| 88 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 89 | 336 | 0.025553 | 0.021653 | 0.003900 | 9.743529 | 0.017857 |  |  |  |  |
| 90 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 91 | 336 | 0.015058 | 0.011158 | 0.003900 | 6.474279 | 0.017857 |  |  |  |  |
| 92 | 336 | -0.027269 | -0.031169 | 0.003900 | -4.543975 | 0.017857 |  |  |  |  |
| 93 | 336 | -0.021353 | -0.023953 | 0.002600 | -7.424374 | 0.011905 |  |  |  |  |
| 94 | 336 | -0.007753 | -0.009053 | 0.001300 | -3.689849 | 0.005952 |  |  |  |  |
| 95 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 96 | 336 | 0.001846 | 0.000546 | 0.001300 | 0.605127 | 0.005952 |  |  |  |  |
| 97 | 336 | -0.003734 | -0.005034 | 0.001300 | -7.015128 | 0.005952 |  |  |  |  |
| 98 | 336 | -0.005926 | -0.007226 | 0.001300 | -1.547548 | 0.005952 |  |  |  |  |
| 99 | 336 | -0.033715 | -0.038915 | 0.005200 | -3.154891 | 0.023810 |  |  |  |  |
| 100 | 336 | 0.021761 | 0.020461 | 0.001300 | 5.033572 | 0.005952 |  |  |  |  |
| 101 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 102 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 103 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 104 | 336 | -0.004599 | -0.007199 | 0.002600 | -1.577351 | 0.011905 |  |  |  |  |
| 105 | 336 | -0.000953 | -0.003553 | 0.002600 | -2.101309 | 0.011905 |  |  |  |  |
| 106 | 336 | 0.013614 | 0.008414 | 0.005200 | 3.806693 | 0.023810 |  |  |  |  |
| 107 | 336 | 0.002071 | 0.000771 | 0.001300 | 1.024319 | 0.005952 |  |  |  |  |
| 108 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 109 | 336 | 0.009547 | 0.008247 | 0.001300 | 3.683697 | 0.005952 |  |  |  |  |
| 110 | 336 | 0.002349 | -0.000251 | 0.002600 | -0.260372 | 0.011905 |  |  |  |  |
| 111 | 336 | -0.006520 | -0.007820 | 0.001300 | -3.408393 | 0.005952 |  |  |  |  |
| 112 | 336 | -0.020372 | -0.022972 | 0.002600 | -3.379158 | 0.011905 |  |  |  |  |
| 113 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 114 | 336 | -0.005551 | -0.008151 | 0.002600 | -3.556086 | 0.011905 |  |  |  |  |
| 115 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 116 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 117 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 118 | 336 | -0.007491 | -0.008791 | 0.001300 | -5.076986 | 0.005952 |  |  |  |  |
| 119 | 336 | 0.002277 | 0.000977 | 0.001300 | 0.483236 | 0.005952 |  |  |  |  |
| 120 | 336 | 0.017238 | 0.014638 | 0.002600 | 6.031105 | 0.011905 |  |  |  |  |
| 121 | 336 | 0.001970 | 0.000670 | 0.001300 | 0.378202 | 0.005952 |  |  |  |  |
| 122 | 336 | 0.009582 | 0.006982 | 0.002600 | 1.858923 | 0.011905 |  |  |  |  |
| 123 | 336 | 0.008765 | 0.007465 | 0.001300 | 5.426832 | 0.005952 |  |  |  |  |
| 124 | 336 | 0.001519 | 0.000219 | 0.001300 | 0.102333 | 0.005952 |  |  |  |  |
| 125 | 336 | 0.005483 | 0.004183 | 0.001300 | 4.155249 | 0.005952 |  |  |  |  |
| 126 | 336 | 0.007535 | 0.006235 | 0.001300 | 3.112536 | 0.005952 |  |  |  |  |
| 127 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 128 | 336 | -0.002884 | -0.004184 | 0.001300 | -1.955455 | 0.005952 |  |  |  |  |
| 129 | 336 | -0.009859 | -0.011159 | 0.001300 | -3.978899 | 0.005952 |  |  |  |  |
| 130 | 336 | -0.006284 | -0.008234 | 0.001950 | -2.601044 | 0.008929 |  |  |  |  |
| 131 | 336 | 0.003453 | 0.002803 | 0.000650 | 4.358980 | 0.002976 |  |  |  |  |
| 132 | 336 | 0.010655 | 0.009355 | 0.001300 | 4.942233 | 0.005952 |  |  |  |  |
| 133 | 336 | -0.003563 | -0.008763 | 0.005200 | -2.955465 | 0.023810 |  |  |  |  |
| 134 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 135 | 336 | -0.007061 | -0.008361 | 0.001300 | -3.601379 | 0.005952 |  |  |  |  |
| 136 | 336 | -0.016799 | -0.019399 | 0.002600 | -4.101001 | 0.011905 |  |  |  |  |
| 137 | 336 | -0.008116 | -0.010716 | 0.002600 | -3.099468 | 0.011905 |  |  |  |  |
| 138 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 139 | 336 | -0.005331 | -0.006631 | 0.001300 | -3.405794 | 0.005952 |  |  |  |  |
| 140 | 336 | -0.006545 | -0.007845 | 0.001300 | -4.582318 | 0.005952 |  |  |  |  |
| 141 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 142 | 336 | 0.003854 | 0.001254 | 0.002600 | 0.483975 | 0.011905 |  |  |  |  |
| 143 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 144 | 336 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |
| 145 | 336 | -0.009237 | -0.010537 | 0.001300 | -4.117437 | 0.005952 |  |  |  |  |
| 146 | 336 | -0.002075 | -0.003375 | 0.001300 | -3.028490 | 0.005952 |  |  |  |  |
| 147 | 34 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |  |  |  |  |


## Model Fold Diagnostics
| Fold | Train Raw | Train Used | Train Missing Drop | Test Rows | Pred Rows | Test Missing / No Pred | Train Feature Missing | Test Feature Missing | Eval Rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 8736 | 160 | 8576 | 336 | 7 | 329 | 168 | 0 | 7 |
| 1 | 9072 | 167 | 8905 | 336 | 14 | 322 | 168 | 0 | 14 |
| 2 | 9408 | 183 | 9225 | 336 | 6 | 330 | 168 | 0 | 6 |
| 3 | 9744 | 189 | 9555 | 336 | 4 | 332 | 168 | 0 | 4 |
| 4 | 10080 | 193 | 9887 | 336 | 13 | 323 | 168 | 0 | 13 |
| 5 | 10416 | 206 | 10210 | 336 | 5 | 331 | 168 | 0 | 5 |
| 6 | 10752 | 210 | 10542 | 336 | 7 | 329 | 168 | 0 | 7 |
| 7 | 11088 | 218 | 10870 | 336 | 5 | 331 | 168 | 0 | 5 |
| 8 | 11424 | 223 | 11201 | 336 | 3 | 333 | 168 | 0 | 3 |
| 9 | 11760 | 226 | 11534 | 336 | 7 | 329 | 168 | 0 | 7 |
| 10 | 12096 | 233 | 11863 | 336 | 2 | 334 | 168 | 0 | 2 |
| 11 | 12432 | 235 | 12197 | 336 | 7 | 329 | 168 | 0 | 7 |
| 12 | 12768 | 242 | 12526 | 336 | 3 | 333 | 168 | 0 | 3 |
| 13 | 13104 | 245 | 12859 | 336 | 14 | 322 | 168 | 0 | 14 |
| 14 | 13440 | 258 | 13182 | 336 | 4 | 332 | 168 | 0 | 4 |
| 15 | 13776 | 262 | 13514 | 336 | 8 | 328 | 168 | 0 | 8 |
| 16 | 14112 | 271 | 13841 | 336 | 7 | 329 | 168 | 0 | 7 |
| 17 | 14448 | 278 | 14170 | 336 | 11 | 325 | 168 | 0 | 11 |
| 18 | 14784 | 289 | 14495 | 336 | 7 | 329 | 168 | 0 | 7 |
| 19 | 15120 | 296 | 14824 | 336 | 8 | 328 | 168 | 0 | 8 |
| 20 | 15456 | 303 | 15153 | 336 | 8 | 328 | 168 | 0 | 8 |
| 21 | 15792 | 312 | 15480 | 336 | 3 | 333 | 168 | 0 | 3 |
| 22 | 16128 | 315 | 15813 | 336 | 5 | 331 | 168 | 0 | 5 |
| 23 | 16464 | 318 | 16146 | 336 | 2 | 334 | 168 | 0 | 2 |
| 24 | 16800 | 322 | 16478 | 336 | 12 | 324 | 168 | 0 | 12 |
| 25 | 17136 | 333 | 16803 | 336 | 9 | 327 | 168 | 0 | 9 |
| 26 | 17472 | 343 | 17129 | 336 | 4 | 332 | 168 | 0 | 4 |
| 27 | 17808 | 347 | 17461 | 336 | 5 | 331 | 168 | 0 | 5 |
| 28 | 18144 | 352 | 17792 | 336 | 3 | 333 | 168 | 0 | 3 |
| 29 | 18480 | 355 | 18125 | 336 | 4 | 332 | 168 | 0 | 4 |
| 30 | 18816 | 359 | 18457 | 336 | 6 | 330 | 168 | 0 | 6 |
| 31 | 19152 | 363 | 18789 | 336 | 5 | 331 | 168 | 0 | 5 |
| 32 | 19488 | 370 | 19118 | 336 | 4 | 332 | 168 | 0 | 4 |
| 33 | 19824 | 372 | 19452 | 336 | 3 | 333 | 168 | 0 | 3 |
| 34 | 20160 | 377 | 19783 | 336 | 7 | 329 | 168 | 0 | 7 |
| 35 | 20496 | 384 | 20112 | 336 | 5 | 331 | 168 | 0 | 5 |
| 36 | 20832 | 386 | 20446 | 336 | 7 | 329 | 168 | 0 | 7 |
| 37 | 21168 | 396 | 20772 | 336 | 5 | 331 | 168 | 0 | 5 |
| 38 | 21504 | 401 | 21103 | 336 | 7 | 329 | 168 | 0 | 7 |
| 39 | 21840 | 406 | 21434 | 336 | 3 | 333 | 168 | 0 | 3 |
| 40 | 22176 | 411 | 21765 | 336 | 4 | 332 | 168 | 0 | 4 |
| 41 | 22512 | 415 | 22097 | 336 | 5 | 331 | 168 | 0 | 5 |
| 42 | 22848 | 420 | 22428 | 336 | 2 | 334 | 168 | 0 | 2 |
| 43 | 23184 | 422 | 22762 | 336 | 2 | 334 | 168 | 0 | 2 |
| 44 | 23520 | 424 | 23096 | 336 | 3 | 333 | 168 | 0 | 3 |
| 45 | 23856 | 427 | 23429 | 336 | 3 | 333 | 168 | 0 | 3 |
| 46 | 24192 | 430 | 23762 | 336 | 5 | 331 | 168 | 0 | 5 |
| 47 | 24528 | 434 | 24094 | 336 | 0 | 336 | 168 | 0 | 0 |
| 48 | 24864 | 435 | 24429 | 336 | 4 | 332 | 168 | 0 | 4 |
| 49 | 25200 | 439 | 24761 | 336 | 2 | 334 | 168 | 0 | 2 |
| 50 | 25536 | 441 | 25095 | 336 | 5 | 331 | 168 | 0 | 5 |
| 51 | 25872 | 446 | 25426 | 336 | 5 | 331 | 168 | 0 | 5 |
| 52 | 26208 | 451 | 25757 | 336 | 7 | 329 | 168 | 0 | 7 |
| 53 | 26544 | 457 | 26087 | 336 | 3 | 333 | 168 | 0 | 3 |
| 54 | 26880 | 461 | 26419 | 336 | 6 | 330 | 168 | 0 | 6 |
| 55 | 27216 | 467 | 26749 | 336 | 5 | 331 | 168 | 0 | 5 |
| 56 | 27552 | 472 | 27080 | 336 | 7 | 329 | 168 | 0 | 7 |
| 57 | 27888 | 477 | 27411 | 336 | 3 | 333 | 168 | 0 | 3 |
| 58 | 28224 | 482 | 27742 | 336 | 4 | 332 | 168 | 0 | 4 |
| 59 | 28560 | 486 | 28074 | 336 | 4 | 332 | 168 | 0 | 4 |
| 60 | 28896 | 489 | 28407 | 336 | 7 | 329 | 168 | 0 | 7 |
| 61 | 29232 | 494 | 28738 | 336 | 8 | 328 | 168 | 0 | 8 |
| 62 | 29568 | 505 | 29063 | 336 | 5 | 331 | 168 | 0 | 5 |
| 63 | 29904 | 510 | 29394 | 336 | 2 | 334 | 168 | 0 | 2 |
| 64 | 30240 | 512 | 29728 | 336 | 2 | 334 | 168 | 0 | 2 |
| 65 | 30576 | 514 | 30062 | 336 | 5 | 331 | 168 | 0 | 5 |
| 66 | 30912 | 519 | 30393 | 336 | 3 | 333 | 168 | 0 | 3 |
| 67 | 31248 | 522 | 30726 | 336 | 7 | 329 | 168 | 0 | 7 |
| 68 | 31584 | 529 | 31055 | 336 | 1 | 335 | 168 | 0 | 1 |
| 69 | 31920 | 530 | 31390 | 336 | 7 | 329 | 168 | 0 | 7 |
| 70 | 32256 | 537 | 31719 | 336 | 11 | 325 | 168 | 0 | 11 |
| 71 | 32592 | 546 | 32046 | 336 | 5 | 331 | 168 | 0 | 5 |
| 72 | 32928 | 553 | 32375 | 336 | 9 | 327 | 168 | 0 | 9 |
| 73 | 33264 | 560 | 32704 | 336 | 8 | 328 | 168 | 0 | 8 |
| 74 | 33600 | 569 | 33031 | 336 | 2 | 334 | 168 | 0 | 2 |
| 75 | 33936 | 572 | 33364 | 336 | 2 | 334 | 168 | 0 | 2 |
| 76 | 34272 | 574 | 33698 | 336 | 8 | 328 | 168 | 0 | 8 |
| 77 | 34608 | 582 | 34026 | 336 | 8 | 328 | 168 | 0 | 8 |
| 78 | 34944 | 588 | 34356 | 336 | 7 | 329 | 168 | 0 | 7 |
| 79 | 35280 | 597 | 34683 | 336 | 8 | 328 | 168 | 0 | 8 |
| 80 | 35616 | 603 | 35013 | 336 | 9 | 327 | 168 | 0 | 9 |
| 81 | 35952 | 614 | 35338 | 336 | 8 | 328 | 168 | 0 | 8 |
| 82 | 36288 | 619 | 35669 | 336 | 1 | 335 | 168 | 0 | 1 |
| 83 | 36624 | 623 | 36001 | 336 | 2 | 334 | 168 | 0 | 2 |
| 84 | 36960 | 625 | 36335 | 336 | 5 | 331 | 168 | 0 | 5 |
| 85 | 37296 | 630 | 36666 | 336 | 5 | 331 | 168 | 0 | 5 |
| 86 | 37632 | 635 | 36997 | 336 | 12 | 324 | 168 | 0 | 12 |
| 87 | 37968 | 647 | 37321 | 336 | 11 | 325 | 168 | 0 | 11 |
| 88 | 38304 | 656 | 37648 | 336 | 2 | 334 | 168 | 0 | 2 |
| 89 | 38640 | 660 | 37980 | 336 | 9 | 327 | 168 | 0 | 9 |
| 90 | 38976 | 668 | 38308 | 336 | 2 | 334 | 168 | 0 | 2 |
| 91 | 39312 | 670 | 38642 | 336 | 8 | 328 | 168 | 0 | 8 |
| 92 | 39648 | 679 | 38969 | 336 | 6 | 330 | 168 | 0 | 6 |
| 93 | 39984 | 685 | 39299 | 336 | 7 | 329 | 168 | 0 | 7 |
| 94 | 40320 | 692 | 39628 | 336 | 7 | 329 | 168 | 0 | 7 |
| 95 | 40656 | 699 | 39957 | 336 | 1 | 335 | 168 | 0 | 1 |
| 96 | 40992 | 700 | 40292 | 336 | 5 | 331 | 168 | 0 | 5 |
| 97 | 41328 | 705 | 40623 | 336 | 5 | 331 | 168 | 0 | 5 |
| 98 | 41664 | 709 | 40955 | 336 | 5 | 331 | 168 | 0 | 5 |
| 99 | 42000 | 715 | 41285 | 336 | 11 | 325 | 168 | 0 | 11 |
| 100 | 42336 | 722 | 41614 | 336 | 1 | 335 | 168 | 0 | 1 |
| 101 | 42672 | 727 | 41945 | 336 | 5 | 331 | 168 | 0 | 5 |
| 102 | 43008 | 732 | 42276 | 336 | 5 | 331 | 168 | 0 | 5 |
| 103 | 43344 | 737 | 42607 | 336 | 5 | 331 | 168 | 0 | 5 |
| 104 | 43680 | 742 | 42938 | 336 | 5 | 331 | 168 | 0 | 5 |
| 105 | 44016 | 746 | 43270 | 336 | 4 | 332 | 168 | 0 | 4 |
| 106 | 44352 | 751 | 43601 | 336 | 11 | 325 | 168 | 0 | 11 |
| 107 | 44688 | 762 | 43926 | 336 | 3 | 333 | 168 | 0 | 3 |
| 108 | 45024 | 763 | 44261 | 336 | 3 | 333 | 168 | 0 | 3 |
| 109 | 45360 | 768 | 44592 | 336 | 6 | 330 | 168 | 0 | 6 |
| 110 | 45696 | 774 | 44922 | 336 | 6 | 330 | 168 | 0 | 6 |
| 111 | 46032 | 780 | 45252 | 336 | 8 | 328 | 168 | 0 | 8 |
| 112 | 46368 | 787 | 45581 | 336 | 5 | 331 | 168 | 0 | 5 |
| 113 | 46704 | 793 | 45911 | 336 | 2 | 334 | 168 | 0 | 2 |
| 114 | 47040 | 795 | 46245 | 336 | 7 | 329 | 168 | 0 | 7 |
| 115 | 47376 | 800 | 46576 | 336 | 5 | 331 | 168 | 0 | 5 |
| 116 | 47712 | 807 | 46905 | 336 | 2 | 334 | 168 | 0 | 2 |
| 117 | 48048 | 809 | 47239 | 336 | 4 | 332 | 168 | 0 | 4 |
| 118 | 48384 | 813 | 47571 | 336 | 4 | 332 | 168 | 0 | 4 |
| 119 | 48720 | 817 | 47903 | 336 | 5 | 331 | 168 | 0 | 5 |
| 120 | 49056 | 822 | 48234 | 336 | 5 | 331 | 168 | 0 | 5 |
| 121 | 49392 | 824 | 48568 | 336 | 7 | 329 | 168 | 0 | 7 |
| 122 | 49728 | 834 | 48894 | 336 | 7 | 329 | 168 | 0 | 7 |
| 123 | 50064 | 841 | 49223 | 336 | 4 | 332 | 168 | 0 | 4 |
| 124 | 50400 | 845 | 49555 | 336 | 3 | 333 | 168 | 0 | 3 |
| 125 | 50736 | 848 | 49888 | 336 | 3 | 333 | 168 | 0 | 3 |
| 126 | 51072 | 851 | 50221 | 336 | 4 | 332 | 168 | 0 | 4 |
| 127 | 51408 | 855 | 50553 | 336 | 3 | 333 | 168 | 0 | 3 |
| 128 | 51744 | 858 | 50886 | 336 | 11 | 325 | 168 | 0 | 11 |
| 129 | 52080 | 869 | 51211 | 336 | 5 | 331 | 168 | 0 | 5 |
| 130 | 52416 | 874 | 51542 | 336 | 4 | 332 | 168 | 0 | 4 |
| 131 | 52752 | 877 | 51875 | 336 | 2 | 334 | 168 | 0 | 2 |
| 132 | 53088 | 880 | 52208 | 336 | 7 | 329 | 168 | 0 | 7 |
| 133 | 53424 | 887 | 52537 | 336 | 7 | 329 | 168 | 0 | 7 |
| 134 | 53760 | 894 | 52866 | 336 | 5 | 331 | 168 | 0 | 5 |
| 135 | 54096 | 899 | 53197 | 336 | 2 | 334 | 168 | 0 | 2 |
| 136 | 54432 | 901 | 53531 | 336 | 12 | 324 | 168 | 0 | 12 |
| 137 | 54768 | 913 | 53855 | 336 | 10 | 326 | 168 | 0 | 10 |
| 138 | 55104 | 923 | 54181 | 336 | 10 | 326 | 168 | 0 | 10 |
| 139 | 55440 | 933 | 54507 | 336 | 3 | 333 | 168 | 0 | 3 |
| 140 | 55776 | 936 | 54840 | 336 | 6 | 330 | 168 | 0 | 6 |
| 141 | 56112 | 942 | 55170 | 336 | 2 | 334 | 168 | 0 | 2 |
| 142 | 56448 | 944 | 55504 | 336 | 6 | 330 | 168 | 0 | 6 |
| 143 | 56784 | 949 | 55835 | 336 | 1 | 335 | 168 | 0 | 1 |
| 144 | 57120 | 951 | 56169 | 336 | 2 | 334 | 168 | 0 | 2 |
| 145 | 57456 | 953 | 56503 | 336 | 6 | 330 | 168 | 0 | 6 |
| 146 | 57792 | 959 | 56833 | 336 | 6 | 330 | 168 | 0 | 6 |
| 147 | 58128 | 965 | 57163 | 34 | 3 | 31 | 168 | 0 | 1 |


## Monitoring
- Drifted feature count: `1` / `12`
| Asset | Feature | PSI |
| --- | --- | --- |
| BTCUSD | lag_close_logret_1 | 0.168190 |


## Feature Set
| Order | Feature |
| --- | --- |
| 1 | shock_ret_z_1h |
| 2 | shock_ret_z_4h |
| 3 | shock_atr_multiple_1h |
| 4 | shock_atr_multiple_4h |
| 5 | shock_distance_ema |
| 6 | shock_strength |
| 7 | regime_vol_ratio_24_168 |
| 8 | regime_absret_z_24_168 |
| 9 | bb_percent_b_24_2.0 |
| 10 | close_rsi_2 |
| 11 | close_rsi_14 |
| 12 | lag_close_logret_1 |

## Feature Steps
```yaml
- step: returns
  params:
    log: true
    col_name: close_logret
  enabled: true
- step: trend
  params:
    price_col: close
    sma_windows: []
    ema_spans:
    - 24
  enabled: true
- step: regime_context
  params:
    price_col: close
    returns_col: close_logret
    vol_short_window: 24
    vol_long_window: 168
    trend_fast_span: 24
    trend_slow_span: 72
    vol_ratio_high_threshold: 1.35
    vol_ratio_low_threshold: 0.8
  enabled: true
- step: bollinger
  params:
    price_col: close
    window: 24
    n_std: 2.0
  enabled: true
- step: atr
  params:
    high_col: high
    low_col: low
    close_col: close
    window: 24
    method: wilder
    add_over_price: true
  enabled: true
- step: shock_context
  params:
    price_col: close
    high_col: high
    low_col: low
    returns_col: close_logret
    ema_col: close_ema_24
    atr_col: atr_24
    short_horizon: 1
    medium_horizon: 4
    vol_window: 24
    ret_z_threshold: 2.6
    atr_mult_threshold: 1.75
    distance_from_mean_threshold: 1.1
    post_shock_active_bars: 4
  enabled: true
- step: rsi
  params:
    price_col: close
    windows:
    - 2
    - 14
    method: wilder
  enabled: true
- step: lags
  params:
    cols:
    - close_logret
    lags:
    - 1
  enabled: true
```

## Config Snapshot
```yaml
data:
  source: dukascopy_csv
  interval: 1h
  start: '2017-05-07 23:00:00'
  end: '2024-12-31 14:00:00'
  alignment: inner
  symbol: BTCUSD
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
    dataset_id: btcusd_1h_shock_meta_xgboost_long_only
    save_raw: false
    save_processed: true
    load_path: /workspace/data/raw/dukas_copy_bank/btcusd_h1.csv
    raw_dir: /workspace/data/raw
    processed_dir: /workspace/data/processed
model:
  kind: xgboost_clf
  params:
    n_estimators: 350
    learning_rate: 0.03
    num_leaves: null
    max_depth: 4
    subsample: 0.9
    colsample_bytree: 0.9
    min_child_samples: null
    random_state: 7
    min_child_weight: 5.0
    reg_lambda: 1.0
    objective: binary:logistic
    eval_metric: logloss
    tree_method: hist
  preprocessing:
    scaler: none
  feature_cols:
  - shock_ret_z_1h
  - shock_ret_z_4h
  - shock_atr_multiple_1h
  - shock_atr_multiple_4h
  - shock_distance_ema
  - shock_strength
  - regime_vol_ratio_24_168
  - regime_absret_z_24_168
  - bb_percent_b_24_2.0
  - close_rsi_2
  - close_rsi_14
  - lag_close_logret_1
  target:
    kind: triple_barrier
    price_col: close
    open_col: open
    high_col: high
    low_col: low
    returns_col: close_logret
    max_holding: 24
    upper_mult: 1.5
    lower_mult: 1.5
    vol_window: 24
    neutral_label: drop
    side_col: shock_side_contrarian
    candidate_col: shock_down_candidate
    candidate_out_col: meta_candidate
  split:
    method: walk_forward
    train_size: 8760
    test_size: 336
    step_size: 336
    expanding: true
    max_folds: null
  runtime: {}
  env: {}
  use_features: true
  pred_prob_col: null
  pred_ret_col: null
  returns_input_col: null
  signal_col: null
  action_col: null
signals:
  kind: probability_threshold
  params:
    prob_col: pred_prob
    signal_col: signal_prob_threshold
    base_signal_col: shock_side_contrarian_active
    upper: 0.555
    upper_exit: 0.49
    lower: 0.43
    lower_exit: 0.48
    mode: long_only
risk:
  cost_per_turnover: 0.0005
  slippage_per_turnover: 0.00015
  target_vol: null
  max_leverage: 1.0
  dd_guard:
    enabled: true
    max_drawdown: 0.12
    rearm_drawdown: 0.08
    cooloff_bars: 48
  vol_col: null
backtest:
  returns_col: close_logret
  signal_col: signal_prob_threshold
  periods_per_year: 8760
  returns_type: log
  missing_return_policy: raise_if_exposed
  min_holding_bars: 3
  subset: test
  vol_col: null
portfolio:
  enabled: false
  construction: signal_weights
  gross_target: 1.0
  long_short: false
  expected_return_col: null
  covariance_window: 60
  covariance_rebalance_step: 1
  risk_aversion: 5.0
  trade_aversion: 0.0
  constraints: {}
  asset_groups: {}
runtime:
  seed: 7
  repro_mode: strict
  deterministic: true
  threads: 1
  seed_torch: false
```

## Artifact Inventory
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
- `feature_importance`: `feature_importance.csv`
- `label_distribution`: `label_distribution.csv`
- `prediction_diagnostics`: `prediction_diagnostics.json`
- `missing_value_diagnostics`: `missing_value_diagnostics.json`
- `fold_model_summary`: `fold_model_summary.csv`
- `stage_tails`: `stage_tails.json`
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
