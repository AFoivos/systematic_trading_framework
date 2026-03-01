## 17. Module Atlas

Η enhanced έκδοση προσθέτει αυστηρότερα tables και local dependency diagrams ανά module, ώστε το
onboarding να επιτρέπει γρήγορη οπτική σύγκριση responsibilities, coupling και function surface χωρίς
να απαιτείται ανάγνωση όλου του narrative body.

### 17.1 Package `src/__init__.py`

| Metric | Value |
|---|---|
| Role | Miscellaneous |
| Module count | 1 |
| Total LOC | 0 |
| Total functions | 0 |
| Total classes | 0 |

#### Module Atlas `src/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/__init__.py` |
| Python module | `src` |
| Role | Miscellaneous |
| LOC | 0 |
| Imports | 0 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] none
      |
      v
[module] src
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

### 17.2 Package `src/backtesting`

| Metric | Value |
|---|---|
| Role | Backtesting |
| Module count | 3 |
| Total LOC | 362 |
| Total functions | 12 |
| Total classes | 1 |

#### Module Atlas `src/backtesting/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/backtesting/__init__.py` |
| Python module | `src.backtesting` |
| Role | Backtesting |
| LOC | 22 |
| Imports | 2 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .engine, .strategies
      |
      v
[module] src.backtesting
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/backtesting/engine.py`

| Metric | Value |
|---|---|
| Module path | `src/backtesting/engine.py` |
| Python module | `src.backtesting.engine` |
| Role | Backtesting |
| LOC | 115 |
| Imports | 8 |
| Functions | 1 |
| Classes | 1 |

```text
[imports] __future__, dataclasses, numpy, pandas
      |
      v
[module] src.backtesting.engine
      |
      +-- functions: 1
      |
      +-- classes: 1
      |
[inbound] src.experiments.runner:_run_single_asset_backtest, tests.test_core:test_run_backt...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `run_backtest` | `BacktestResult` | 87 | `KeyError, ValueError` | `def run_backtest(df: pd.DataFrame, signal_col: str, returns_col: str, returns_type: Liter...` |

| Class | Bases | LOC |
|---|---|---:|
| `BacktestResult` | `-` | 12 |

#### Module Atlas `src/backtesting/strategies.py`

| Metric | Value |
|---|---|
| Module path | `src/backtesting/strategies.py` |
| Python module | `src.backtesting.strategies` |
| Role | Backtesting |
| LOC | 225 |
| Imports | 4 |
| Functions | 11 |
| Classes | 0 |

```text
[imports] __future__, pandas, src.risk.position_sizing, src.signals
      |
      v
[module] src.backtesting.strategies
      |
      +-- functions: 11
      |
[inbound] external / CLI / registry
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `buy_and_hold_signal` | `pd.Series` | 8 | `ValueError` | `def buy_and_hold_signal(df: pd.DataFrame, signal_name: str = 'signal_bh') -> pd.Series` |
| `trend_state_long_only_signal` | `pd.Series` | 13 | `KeyError` | `def trend_state_long_only_signal(df: pd.DataFrame, state_col: str, signal_name: str = 'si...` |
| `trend_state_signal` | `pd.Series` | 16 | `-` | `def trend_state_signal(df: pd.DataFrame, state_col: str, signal_name: str = 'signal_trend...` |
| `rsi_strategy` | `pd.Series` | 20 | `-` | `def rsi_strategy(df: pd.DataFrame, rsi_col: str, buy_level: float = 30.0, sell_level: flo...` |
| `momentum_strategy` | `pd.Series` | 20 | `-` | `def momentum_strategy(df: pd.DataFrame, momentum_col: str, long_threshold: float = 0.0, s...` |
| `stochastic_strategy` | `pd.Series` | 20 | `-` | `def stochastic_strategy(df: pd.DataFrame, k_col: str, buy_level: float = 20.0, sell_level...` |
| `volatility_regime_strategy` | `pd.Series` | 18 | `-` | `def volatility_regime_strategy(df: pd.DataFrame, vol_col: str, quantile: float = 0.5, sig...` |
| `probabilistic_signal` | `pd.Series` | 17 | `KeyError` | `def probabilistic_signal(df: pd.DataFrame, prob_col: str, signal_name: str = 'signal_prob...` |
| `conviction_sizing_signal` | `pd.Series` | 17 | `KeyError` | `def conviction_sizing_signal(df: pd.DataFrame, prob_col: str, signal_name: str = 'signal_...` |
| `regime_filtered_signal` | `pd.Series` | 19 | `KeyError` | `def regime_filtered_signal(df: pd.DataFrame, base_signal_col: str, regime_col: str, signa...` |
| `vol_targeted_signal` | `pd.Series` | 23 | `KeyError` | `def vol_targeted_signal(df: pd.DataFrame, signal_col: str, vol_col: str, target_vol: floa...` |

### 17.3 Package `src/evaluation`

| Metric | Value |
|---|---|
| Role | Evaluation |
| Module count | 3 |
| Total LOC | 620 |
| Total functions | 22 |
| Total classes | 1 |

#### Module Atlas `src/evaluation/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/evaluation/__init__.py` |
| Python module | `src.evaluation` |
| Role | Evaluation |
| LOC | 47 |
| Imports | 2 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .metrics, .time_splits
      |
      v
[module] src.evaluation
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/evaluation/metrics.py`

| Metric | Value |
|---|---|
| Module path | `src/evaluation/metrics.py` |
| Python module | `src.evaluation.metrics` |
| Role | Evaluation |
| LOC | 280 |
| Imports | 4 |
| Functions | 14 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.evaluation.metrics
      |
      +-- functions: 14
      |
[inbound] src.backtesting.engine:run_backtest, src.evaluation.metrics:calmar_ratio, src.eva...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `equity_curve_from_returns` | `pd.Series` | 10 | `-` | `def equity_curve_from_returns(returns: pd.Series) -> pd.Series` |
| `max_drawdown` | `float` | 9 | `-` | `def max_drawdown(equity: pd.Series) -> float` |
| `annualized_return` | `float` | 12 | `-` | `def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float` |
| `annualized_volatility` | `float` | 9 | `-` | `def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float` |
| `sharpe_ratio` | `float` | 8 | `-` | `def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252) -> float` |
| `downside_volatility` | `float` | 16 | `-` | `def downside_volatility(returns: pd.Series, periods_per_year: int = 252, minimum_acceptab...` |
| `sortino_ratio` | `float` | 16 | `-` | `def sortino_ratio(returns: pd.Series, periods_per_year: int = 252, minimum_acceptable_ret...` |
| `calmar_ratio` | `float` | 8 | `-` | `def calmar_ratio(returns: pd.Series, periods_per_year: int = 252) -> float` |
| `profit_factor` | `float` | 13 | `-` | `def profit_factor(returns: pd.Series) -> float` |
| `hit_rate` | `float` | 12 | `-` | `def hit_rate(returns: pd.Series) -> float` |
| `turnover_stats` | `dict[str, float]` | 14 | `-` | `def turnover_stats(turnover: pd.Series \| None) -> dict[str, float]` |
| `cost_attribution` | `dict[str, float]` | 31 | `-` | `def cost_attribution(*, net_returns: pd.Series, gross_returns: pd.Series \| None, costs: ...` |
| `compute_backtest_metrics` | `dict[str, float]` | 57 | `-` | `def compute_backtest_metrics(*, net_returns: pd.Series, periods_per_year: int = 252, turn...` |
| `merge_metric_overrides` | `dict[str, float]` | 12 | `-` | `def merge_metric_overrides(base_metrics: Mapping[str, float], overrides: Mapping[str, flo...` |

#### Module Atlas `src/evaluation/time_splits.py`

| Metric | Value |
|---|---|
| Module path | `src/evaluation/time_splits.py` |
| Python module | `src.evaluation.time_splits` |
| Role | Evaluation |
| LOC | 293 |
| Imports | 4 |
| Functions | 8 |
| Classes | 1 |

```text
[imports] __future__, dataclasses, numpy, typing
      |
      v
[module] src.evaluation.time_splits
      |
      +-- functions: 8
      |
      +-- classes: 1
      |
[inbound] src.evaluation.time_splits:assert_no_forward_label_leakage, src.evaluation.time_s...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_require_positive_int` | `None` | 7 | `ValueError` | `def _require_positive_int(name: str, value: int) -> None` |
| `_require_non_negative_int` | `None` | 7 | `ValueError` | `def _require_non_negative_int(name: str, value: int) -> None` |
| `time_split_indices` | `list[TimeSplit]` | 27 | `ValueError` | `def time_split_indices(n_samples: int, train_frac: float = 0.7) -> list[TimeSplit]` |
| `walk_forward_split_indices` | `list[TimeSplit]` | 23 | `-` | `def walk_forward_split_indices(n_samples: int, train_size: int, test_size: int, step_size...` |
| `purged_walk_forward_split_indices` | `list[TimeSplit]` | 79 | `ValueError` | `def purged_walk_forward_split_indices(n_samples: int, train_size: int, test_size: int, st...` |
| `trim_train_indices_for_horizon` | `np.ndarray` | 23 | `ValueError` | `def trim_train_indices_for_horizon(train_idx: np.ndarray, test_start: int, target_horizon...` |
| `assert_no_forward_label_leakage` | `None` | 22 | `ValueError` | `def assert_no_forward_label_leakage(train_idx: np.ndarray, test_start: int, target_horizo...` |
| `build_time_splits` | `list[TimeSplit]` | 57 | `ValueError` | `def build_time_splits(*, method: Literal['time', 'walk_forward', 'purged'], n_samples: in...` |

| Class | Bases | LOC |
|---|---|---:|
| `TimeSplit` | `-` | 12 |

### 17.4 Package `src/execution`

| Metric | Value |
|---|---|
| Role | Paper execution |
| Module count | 2 |
| Total LOC | 69 |
| Total functions | 1 |
| Total classes | 0 |

#### Module Atlas `src/execution/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/execution/__init__.py` |
| Python module | `src.execution` |
| Role | Paper execution |
| LOC | 3 |
| Imports | 1 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .paper
      |
      v
[module] src.execution
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/execution/paper.py`

| Metric | Value |
|---|---|
| Module path | `src/execution/paper.py` |
| Python module | `src.execution.paper` |
| Role | Paper execution |
| LOC | 66 |
| Imports | 2 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, pandas
      |
      v
[module] src.execution.paper
      |
      +-- functions: 1
      |
[inbound] src.experiments.runner:_build_execution_output, tests.test_runner_extensions:test...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `build_rebalance_orders` | `pd.DataFrame` | 58 | `TypeError, ValueError` | `def build_rebalance_orders(target_weights: pd.Series, *, prices: pd.Series, capital: floa...` |

### 17.5 Package `src/experiments`

| Metric | Value |
|---|---|
| Role | Experiment orchestration |
| Module count | 5 |
| Total LOC | 1997 |
| Total functions | 44 |
| Total classes | 3 |

#### Module Atlas `src/experiments/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/experiments/__init__.py` |
| Python module | `src.experiments` |
| Role | Experiment orchestration |
| LOC | 16 |
| Imports | 2 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .contracts, .runner
      |
      v
[module] src.experiments
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/experiments/contracts.py`

| Metric | Value |
|---|---|
| Module path | `src/experiments/contracts.py` |
| Python module | `src.experiments.contracts` |
| Role | Experiment orchestration |
| LOC | 130 |
| Imports | 5 |
| Functions | 2 |
| Classes | 2 |

```text
[imports] __future__, dataclasses, pandas, pandas.api.types
      |
      v
[module] src.experiments.contracts
      |
      +-- functions: 2
      |
      +-- classes: 2
      |
[inbound] src.experiments.models:_train_forward_classifier, src.experiments.runner:_load_as...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `validate_data_contract` | `dict[str, int]` | 27 | `TypeError, ValueError` | `def validate_data_contract(df: pd.DataFrame, contract: DataContract \| None = None) -> di...` |
| `validate_feature_target_contract` | `dict[str, int]` | 61 | `KeyError, TypeError, ValueError` | `def validate_feature_target_contract(df: pd.DataFrame, *, feature_cols: Sequence[str], ta...` |

| Class | Bases | LOC |
|---|---|---:|
| `DataContract` | `-` | 9 |
| `TargetContract` | `-` | 7 |

#### Module Atlas `src/experiments/models.py`

| Metric | Value |
|---|---|
| Module path | `src/experiments/models.py` |
| Python module | `src.experiments.models` |
| Role | Experiment orchestration |
| LOC | 499 |
| Imports | 10 |
| Functions | 8 |
| Classes | 0 |

```text
[imports] __future__, lightgbm, numpy, pandas
      |
      v
[module] src.experiments.models
      |
      +-- functions: 8
      |
[inbound] src.experiments.models:_train_forward_classifier, src.experiments.models:train_li...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_resolve_runtime_for_model` | `dict[str, Any]` | 50 | `ValueError` | `def _resolve_runtime_for_model(model_cfg: dict[str, Any], model_params: dict[str, Any], *...` |
| `infer_feature_columns` | `list[str]` | 32 | `KeyError` | `def infer_feature_columns(df: pd.DataFrame, explicit_cols: Sequence[str] \| None = None, ...` |
| `_build_forward_return_target` | `tuple[pd.DataFrame, str, str, dict[str, Any]]` | 48 | `KeyError, ValueError` | `def _build_forward_return_target(df: pd.DataFrame, target_cfg: dict[str, Any] \| None) ->...` |
| `_assign_quantile_labels` | `pd.Series` | 15 | `-` | `def _assign_quantile_labels(forward_returns: pd.Series, *, low_value: float, high_value: ...` |
| `_binary_classification_metrics` | `dict[str, float | int | None]` | 35 | `-` | `def _binary_classification_metrics(y_true: pd.Series, pred_prob: pd.Series) -> dict[str, ...` |
| `_train_forward_classifier` | `tuple[pd.DataFrame, object, dict[str, Any]]` | 234 | `ValueError` | `def _train_forward_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], *, model_kind:...` |
| `train_lightgbm_classifier` | `tuple[pd.DataFrame, LGBMClassifier, dict[str, Any]]` | 18 | `-` | `def train_lightgbm_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], returns_col: s...` |
| `train_logistic_regression_classifier` | `tuple[pd.DataFrame, LogisticRegression, dict[str, Any]]` | 25 | `-` | `def train_logistic_regression_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], ret...` |

#### Module Atlas `src/experiments/registry.py`

| Metric | Value |
|---|---|
| Module path | `src/experiments/registry.py` |
| Python module | `src.experiments.registry` |
| Role | Experiment orchestration |
| LOC | 88 |
| Imports | 10 |
| Functions | 3 |
| Classes | 0 |

```text
[imports] __future__, pandas, src.backtesting.strategies, src.experiments.models
      |
      v
[module] src.experiments.registry
      |
      +-- functions: 3
      |
[inbound] src.experiments.runner:_apply_feature_steps, src.experiments.runner:_apply_model_...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `get_feature_fn` | `FeatureFn` | 9 | `KeyError` | `def get_feature_fn(name: str) -> FeatureFn` |
| `get_signal_fn` | `SignalFn` | 9 | `KeyError` | `def get_signal_fn(name: str) -> SignalFn` |
| `get_model_fn` | `ModelFn` | 9 | `KeyError` | `def get_model_fn(name: str) -> ModelFn` |

#### Module Atlas `src/experiments/runner.py`

| Metric | Value |
|---|---|
| Module path | `src/experiments/runner.py` |
| Python module | `src.experiments.runner` |
| Role | Experiment orchestration |
| LOC | 1264 |
| Imports | 25 |
| Functions | 31 |
| Classes | 1 |

```text
[imports] __future__, dataclasses, datetime, json
      |
      v
[module] src.experiments.runner
      |
      +-- functions: 31
      |
      +-- classes: 1
      |
[inbound] src.experiments.runner:_apply_model_to_assets, src.experiments.runner:_apply_sign...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_slugify` | `str` | 7 | `-` | `def _slugify(value: str) -> str` |
| `_resolve_symbols` | `list[str]` | 8 | `-` | `def _resolve_symbols(data_cfg: dict[str, Any]) -> list[str]` |
| `_default_dataset_id` | `str` | 19 | `-` | `def _default_dataset_id(data_cfg: dict[str, Any]) -> str` |
| `_apply_feature_steps` | `pd.DataFrame` | 15 | `ValueError` | `def _apply_feature_steps(df: pd.DataFrame, steps: list[dict[str, Any]]) -> pd.DataFrame` |
| `_apply_model_step` | `tuple[pd.DataFrame, object | None, dict[str, Any]]` | 14 | `-` | `def _apply_model_step(df: pd.DataFrame, model_cfg: dict[str, Any], returns_col: str \| No...` |
| `_apply_signal_step` | `pd.DataFrame` | 19 | `TypeError` | `def _apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame` |
| `_apply_steps_to_assets` | `dict[str, pd.DataFrame]` | 14 | `-` | `def _apply_steps_to_assets(asset_frames: dict[str, pd.DataFrame], *, feature_steps: list[...` |
| `_aggregate_model_meta` | `dict[str, Any]` | 47 | `-` | `def _aggregate_model_meta(per_asset_meta: dict[str, dict[str, Any]]) -> dict[str, Any]` |
| `_apply_model_to_assets` | `tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]` | 28 | `-` | `def _apply_model_to_assets(asset_frames: dict[str, pd.DataFrame], *, model_cfg: dict[str,...` |
| `_apply_signals_to_assets` | `dict[str, pd.DataFrame]` | 14 | `-` | `def _apply_signals_to_assets(asset_frames: dict[str, pd.DataFrame], *, signals_cfg: dict[...` |
| `_resolve_vol_col` | `str | None` | 13 | `-` | `def _resolve_vol_col(df: pd.DataFrame, backtest_cfg: dict[str, Any], risk_cfg: dict[str, ...` |
| `_validate_returns_series` | `None` | 8 | `ValueError` | `def _validate_returns_series(returns: pd.Series, returns_type: str) -> None` |
| `_validate_returns_frame` | `None` | 8 | `ValueError` | `def _validate_returns_frame(returns: pd.DataFrame, returns_type: str) -> None` |
| `_build_storage_context` | `dict[str, Any]` | 14 | `-` | `def _build_storage_context(data_cfg: dict[str, Any], *, symbols: list[str], pit_cfg: dict...` |
| `_load_asset_frames` | `tuple[dict[str, pd.DataFrame], dict[str, Any]]` | 78 | `ValueError` | `def _load_asset_frames(data_cfg: dict[str, Any]) -> tuple[dict[str, pd.DataFrame], dict[s...` |
| `_save_processed_snapshot_if_enabled` | `dict[str, Any] | None` | 29 | `-` | `def _save_processed_snapshot_if_enabled(asset_frames: dict[str, pd.DataFrame], *, data_cf...` |
| `_align_asset_column` | `pd.DataFrame` | 22 | `KeyError` | `def _align_asset_column(asset_frames: dict[str, pd.DataFrame], *, column: str, how: str) ...` |
| `_build_portfolio_constraints` | `PortfolioConstraints` | 22 | `-` | `def _build_portfolio_constraints(portfolio_cfg: dict[str, Any]) -> PortfolioConstraints` |
| `_run_single_asset_backtest` | `BacktestResult` | 47 | `ValueError` | `def _run_single_asset_backtest(asset: str, df: pd.DataFrame, *, cfg: dict[str, Any], mode...` |
| `_run_portfolio_backtest` | `tuple[PortfolioPerformance, pd.DataFrame, pd.DataFrame, dict[str, Any]]` | 74 | `ValueError` | `def _run_portfolio_backtest(asset_frames: dict[str, pd.DataFrame], *, cfg: dict[str, Any]...` |
| `_compute_subset_metrics` | `dict[str, float]` | 24 | `-` | `def _compute_subset_metrics(*, net_returns: pd.Series, turnover: pd.Series, costs: pd.Ser...` |
| `_build_fold_backtest_summaries` | `list[dict[str, Any]]` | 37 | `-` | `def _build_fold_backtest_summaries(*, source_index: pd.Index, net_returns: pd.Series, tur...` |
| `_build_single_asset_evaluation` | `dict[str, Any]` | 54 | `-` | `def _build_single_asset_evaluation(asset: str, df: pd.DataFrame, *, performance: Backtest...` |
| `_build_portfolio_evaluation` | `dict[str, Any]` | 62 | `-` | `def _build_portfolio_evaluation(asset_frames: dict[str, pd.DataFrame], *, performance: Po...` |
| `_compute_monitoring_for_asset` | `dict[str, Any] | None` | 28 | `-` | `def _compute_monitoring_for_asset(df: pd.DataFrame, *, meta: dict[str, Any], monitoring_c...` |
| `_compute_monitoring_report` | `dict[str, Any]` | 45 | `-` | `def _compute_monitoring_report(asset_frames: dict[str, pd.DataFrame], *, model_meta: dict...` |
| `_build_execution_output` | `tuple[dict[str, Any], pd.DataFrame | None]` | 52 | `-` | `def _build_execution_output(*, asset_frames: dict[str, pd.DataFrame], execution_cfg: dict...` |
| `_data_stats_payload` | `dict[str, Any]` | 25 | `-` | `def _data_stats_payload(data: pd.DataFrame \| dict[str, pd.DataFrame]) -> dict[str, Any]` |
| `_resolved_feature_columns` | `list[str] | dict[str, list[str]] | None` | 16 | `-` | `def _resolved_feature_columns(model_meta: dict[str, Any]) -> list[str] \| dict[str, list[...` |
| `_save_artifacts` | `dict[str, str]` | 129 | `-` | `def _save_artifacts(*, run_dir: Path, cfg: dict[str, Any], data: pd.DataFrame \| dict[str...` |
| `run_experiment` | `ExperimentResult` | 147 | `-` | `def run_experiment(config_path: str \| Path) -> ExperimentResult` |

| Class | Bases | LOC |
|---|---|---:|
| `ExperimentResult` | `-` | 16 |

### 17.6 Package `src/features`

| Metric | Value |
|---|---|
| Role | Feature engineering |
| Module count | 4 |
| Total LOC | 219 |
| Total functions | 6 |
| Total classes | 0 |

#### Module Atlas `src/features/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/features/__init__.py` |
| Python module | `src.features` |
| Role | Feature engineering |
| LOC | 20 |
| Imports | 4 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .lags, .returns, .technical.trend, .volatility
      |
      v
[module] src.features
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/features/lags.py`

| Metric | Value |
|---|---|
| Module path | `src/features/lags.py` |
| Python module | `src.features.lags` |
| Role | Feature engineering |
| LOC | 35 |
| Imports | 3 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, pandas, typing
      |
      v
[module] src.features.lags
      |
      +-- functions: 1
      |
[inbound] external / CLI / registry
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `add_lagged_features` | `pd.DataFrame` | 27 | `KeyError` | `def add_lagged_features(df: pd.DataFrame, cols: Iterable[str], lags: Sequence[int] = (1, ...` |

#### Module Atlas `src/features/returns.py`

| Metric | Value |
|---|---|
| Module path | `src/features/returns.py` |
| Python module | `src.features.returns` |
| Role | Feature engineering |
| LOC | 64 |
| Imports | 3 |
| Functions | 2 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas
      |
      v
[module] src.features.returns
      |
      +-- functions: 2
      |
[inbound] src.features.returns:add_close_returns, tests.test_core:test_compute_returns_simp...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_returns` | `pd.Series` | 28 | `-` | `def compute_returns(prices: pd.Series, log: bool = False, dropna: bool = True) -> pd.Series` |
| `add_close_returns` | `pd.DataFrame` | 30 | `ValueError` | `def add_close_returns(df: pd.DataFrame, log: bool = False, col_name: str \| None = None) ...` |

#### Module Atlas `src/features/volatility.py`

| Metric | Value |
|---|---|
| Module path | `src/features/volatility.py` |
| Python module | `src.features.volatility` |
| Role | Feature engineering |
| LOC | 100 |
| Imports | 4 |
| Functions | 3 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.features.volatility
      |
      +-- functions: 3
      |
[inbound] src.features.volatility:add_volatility_features
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_rolling_vol` | `pd.Series` | 25 | `TypeError` | `def compute_rolling_vol(returns: pd.Series, window: int, ddof: int = 1, annualization_fac...` |
| `compute_ewma_vol` | `pd.Series` | 22 | `TypeError` | `def compute_ewma_vol(returns: pd.Series, span: int, annualization_factor: Optional[float]...` |
| `add_volatility_features` | `pd.DataFrame` | 42 | `KeyError` | `def add_volatility_features(df: pd.DataFrame, returns_col: str = 'close_logret', rolling_...` |

### 17.7 Package `src/features/technical`

| Metric | Value |
|---|---|
| Role | Feature engineering |
| Module count | 5 |
| Total LOC | 699 |
| Total functions | 22 |
| Total classes | 0 |

#### Module Atlas `src/features/technical/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/features/technical/__init__.py` |
| Python module | `src.features.technical` |
| Role | Feature engineering |
| LOC | 55 |
| Imports | 4 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .indicators, .momentum, .oscillators, .trend
      |
      v
[module] src.features.technical
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/features/technical/indicators.py`

| Metric | Value |
|---|---|
| Module path | `src/features/technical/indicators.py` |
| Python module | `src.features.technical.indicators` |
| Role | Feature engineering |
| LOC | 239 |
| Imports | 4 |
| Functions | 10 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.features.technical.indicators
      |
      +-- functions: 10
      |
[inbound] src.features.technical.indicators:add_indicator_features, src.features.technical....
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_true_range` | `pd.Series` | 14 | `-` | `def compute_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series` |
| `compute_atr` | `pd.Series` | 17 | `ValueError` | `def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14, meth...` |
| `add_bollinger_bands` | `pd.DataFrame` | 22 | `-` | `def add_bollinger_bands(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.Dat...` |
| `compute_macd` | `pd.DataFrame` | 19 | `-` | `def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd...` |
| `compute_ppo` | `pd.DataFrame` | 19 | `-` | `def compute_ppo(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd....` |
| `compute_roc` | `pd.Series` | 8 | `-` | `def compute_roc(close: pd.Series, window: int = 10) -> pd.Series` |
| `compute_volume_zscore` | `pd.Series` | 10 | `-` | `def compute_volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series` |
| `compute_adx` | `pd.DataFrame` | 29 | `-` | `def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> p...` |
| `compute_mfi` | `pd.Series` | 20 | `-` | `def compute_mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, win...` |
| `add_indicator_features` | `pd.DataFrame` | 55 | `KeyError` | `def add_indicator_features(df: pd.DataFrame, price_col: str = 'close', high_col: str = 'h...` |

#### Module Atlas `src/features/technical/momentum.py`

| Metric | Value |
|---|---|
| Module path | `src/features/technical/momentum.py` |
| Python module | `src.features.technical.momentum` |
| Role | Feature engineering |
| LOC | 93 |
| Imports | 4 |
| Functions | 4 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.features.technical.momentum
      |
      +-- functions: 4
      |
[inbound] src.features.technical.momentum:add_momentum_features
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_price_momentum` | `pd.Series` | 13 | `TypeError` | `def compute_price_momentum(prices: pd.Series, window: int) -> pd.Series` |
| `compute_return_momentum` | `pd.Series` | 14 | `TypeError` | `def compute_return_momentum(returns: pd.Series, window: int) -> pd.Series` |
| `compute_vol_normalized_momentum` | `pd.Series` | 20 | `TypeError` | `def compute_vol_normalized_momentum(returns: pd.Series, volatility: pd.Series, window: in...` |
| `add_momentum_features` | `pd.DataFrame` | 32 | `-` | `def add_momentum_features(df: pd.DataFrame, price_col: str = 'close', returns_col: str = ...` |

#### Module Atlas `src/features/technical/oscillators.py`

| Metric | Value |
|---|---|
| Module path | `src/features/technical/oscillators.py` |
| Python module | `src.features.technical.oscillators` |
| Role | Feature engineering |
| LOC | 122 |
| Imports | 4 |
| Functions | 4 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.features.technical.oscillators
      |
      +-- functions: 4
      |
[inbound] src.features.technical.oscillators:add_oscillator_features
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_rsi` | `pd.Series` | 35 | `TypeError, ValueError` | `def compute_rsi(prices: pd.Series, window: int = 14, method: str = 'wilder') -> pd.Series` |
| `compute_stoch_k` | `pd.Series` | 22 | `TypeError` | `def compute_stoch_k(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) ...` |
| `compute_stoch_d` | `pd.Series` | 13 | `TypeError` | `def compute_stoch_d(k: pd.Series, smooth: int = 3) -> pd.Series` |
| `add_oscillator_features` | `pd.DataFrame` | 38 | `KeyError` | `def add_oscillator_features(df: pd.DataFrame, price_col: str = 'close', high_col: str = '...` |

#### Module Atlas `src/features/technical/trend.py`

| Metric | Value |
|---|---|
| Module path | `src/features/technical/trend.py` |
| Python module | `src.features.technical.trend` |
| Role | Feature engineering |
| LOC | 190 |
| Imports | 4 |
| Functions | 4 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.features.technical.trend
      |
      +-- functions: 4
      |
[inbound] src.features.technical.trend:add_trend_features, tests.test_core:test_add_trend_f...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_sma` | `pd.Series` | 32 | `TypeError` | `def compute_sma(prices: pd.Series, window: int, min_periods: Optional[int] = None) -> pd....` |
| `compute_ema` | `pd.Series` | 28 | `TypeError` | `def compute_ema(prices: pd.Series, span: int, adjust: bool = False) -> pd.Series` |
| `add_trend_features` | `pd.DataFrame` | 57 | `KeyError` | `def add_trend_features(df: pd.DataFrame, price_col: str = 'close', sma_windows: Sequence[...` |
| `add_trend_regime_features` | `pd.DataFrame` | 61 | `KeyError` | `def add_trend_regime_features(df: pd.DataFrame, price_col: str = 'close', base_sma_for_si...` |

### 17.8 Package `src/models`

| Metric | Value |
|---|---|
| Role | Model helpers / baselines |
| Module count | 2 |
| Total LOC | 128 |
| Total functions | 5 |
| Total classes | 1 |

#### Module Atlas `src/models/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/models/__init__.py` |
| Python module | `src.models` |
| Role | Model helpers / baselines |
| LOC | 0 |
| Imports | 0 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] none
      |
      v
[module] src.models
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/models/lightgbm_baseline.py`

| Metric | Value |
|---|---|
| Module path | `src/models/lightgbm_baseline.py` |
| Python module | `src.models.lightgbm_baseline` |
| Role | Model helpers / baselines |
| LOC | 128 |
| Imports | 7 |
| Functions | 5 |
| Classes | 1 |

```text
[imports] __future__, dataclasses, lightgbm, numpy
      |
      v
[module] src.models.lightgbm_baseline
      |
      +-- functions: 5
      |
      +-- classes: 1
      |
[inbound] src.experiments.models:infer_feature_columns
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `default_feature_columns` | `list[str]` | 28 | `-` | `def default_feature_columns(df: pd.DataFrame) -> list[str]` |
| `train_regressor` | `LGBMRegressor` | 26 | `-` | `def train_regressor(train_df: pd.DataFrame, feature_cols: Sequence[str], target_col: str,...` |
| `predict_returns` | `pd.DataFrame` | 11 | `-` | `def predict_returns(model: LGBMRegressor, df: pd.DataFrame, feature_cols: Sequence[str], ...` |
| `prediction_to_signal` | `pd.DataFrame` | 20 | `-` | `def prediction_to_signal(df: pd.DataFrame, pred_col: str = 'pred_next_ret', signal_col: s...` |
| `train_test_split_time` | `tuple[pd.DataFrame, pd.DataFrame]` | 8 | `ValueError` | `def train_test_split_time(df: pd.DataFrame, train_frac: float = 0.7) -> tuple[pd.DataFram...` |

| Class | Bases | LOC |
|---|---|---:|
| `LGBMBaselineConfig` | `-` | 12 |

### 17.9 Package `src/monitoring`

| Metric | Value |
|---|---|
| Role | Monitoring |
| Module count | 2 |
| Total LOC | 119 |
| Total functions | 2 |
| Total classes | 0 |

#### Module Atlas `src/monitoring/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/monitoring/__init__.py` |
| Python module | `src.monitoring` |
| Role | Monitoring |
| LOC | 6 |
| Imports | 1 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .drift
      |
      v
[module] src.monitoring
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/monitoring/drift.py`

| Metric | Value |
|---|---|
| Module path | `src/monitoring/drift.py` |
| Python module | `src.monitoring.drift` |
| Role | Monitoring |
| LOC | 113 |
| Imports | 4 |
| Functions | 2 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.monitoring.drift
      |
      +-- functions: 2
      |
[inbound] src.experiments.runner:_compute_monitoring_for_asset, src.monitoring.drift:comput...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `population_stability_index` | `float` | 32 | `-` | `def population_stability_index(reference: pd.Series, current: pd.Series, *, n_bins: int =...` |
| `compute_feature_drift` | `dict[str, Any]` | 65 | `TypeError` | `def compute_feature_drift(reference_df: pd.DataFrame, current_df: pd.DataFrame, *, featur...` |

### 17.10 Package `src/portfolio`

| Metric | Value |
|---|---|
| Role | Portfolio construction |
| Module count | 5 |
| Total LOC | 768 |
| Total functions | 16 |
| Total classes | 2 |

#### Module Atlas `src/portfolio/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/portfolio/__init__.py` |
| Python module | `src.portfolio` |
| Role | Portfolio construction |
| LOC | 35 |
| Imports | 4 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .constraints, .construction, .covariance, .optimizer
      |
      v
[module] src.portfolio
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/portfolio/constraints.py`

| Metric | Value |
|---|---|
| Module path | `src/portfolio/constraints.py` |
| Python module | `src.portfolio.constraints` |
| Role | Portfolio construction |
| LOC | 291 |
| Imports | 5 |
| Functions | 8 |
| Classes | 1 |

```text
[imports] __future__, dataclasses, numpy, pandas
      |
      v
[module] src.portfolio.constraints
      |
      +-- functions: 8
      |
      +-- classes: 1
      |
[inbound] src.portfolio.constraints:_distribute_delta_with_bounds, src.portfolio.constraint...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_as_weight_series` | `pd.Series` | 9 | `TypeError` | `def _as_weight_series(weights: pd.Series) -> pd.Series` |
| `apply_weight_bounds` | `pd.Series` | 13 | `-` | `def apply_weight_bounds(weights: pd.Series, *, min_weight: float, max_weight: float) -> p...` |
| `enforce_gross_leverage` | `pd.Series` | 15 | `-` | `def enforce_gross_leverage(weights: pd.Series, *, max_gross_leverage: float) -> pd.Series` |
| `_distribute_delta_with_bounds` | `pd.Series` | 47 | `-` | `def _distribute_delta_with_bounds(weights: pd.Series, *, delta: float, min_weight: float,...` |
| `enforce_net_exposure` | `pd.Series` | 22 | `-` | `def enforce_net_exposure(weights: pd.Series, *, target_net_exposure: float, min_weight: f...` |
| `enforce_group_caps` | `pd.Series` | 24 | `-` | `def enforce_group_caps(weights: pd.Series, *, asset_to_group: Mapping[str, str] \| None, ...` |
| `enforce_turnover_limit` | `pd.Series` | 22 | `-` | `def enforce_turnover_limit(weights: pd.Series, *, prev_weights: pd.Series \| None, turnov...` |
| `apply_constraints` | `tuple[pd.Series, dict[str, float | dict[str, float]]]` | 73 | `-` | `def apply_constraints(weights: pd.Series, *, constraints: PortfolioConstraints, prev_weig...` |

| Class | Bases | LOC |
|---|---|---:|
| `PortfolioConstraints` | `-` | 28 |

#### Module Atlas `src/portfolio/construction.py`

| Metric | Value |
|---|---|
| Module path | `src/portfolio/construction.py` |
| Python module | `src.portfolio.construction` |
| Role | Portfolio construction |
| LOC | 221 |
| Imports | 8 |
| Functions | 4 |
| Classes | 1 |

```text
[imports] __future__, dataclasses, numpy, pandas
      |
      v
[module] src.portfolio.construction
      |
      +-- functions: 4
      |
      +-- classes: 1
      |
[inbound] src.experiments.runner:_run_portfolio_backtest, src.portfolio.construction:build_...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `signal_to_raw_weights` | `pd.Series` | 24 | `TypeError` | `def signal_to_raw_weights(signal_t: pd.Series, *, long_short: bool = True, gross_target: ...` |
| `build_weights_from_signals_over_time` | `tuple[pd.DataFrame, pd.DataFrame]` | 48 | `TypeError` | `def build_weights_from_signals_over_time(signals: pd.DataFrame, *, constraints: Portfolio...` |
| `build_optimized_weights_over_time` | `tuple[pd.DataFrame, pd.DataFrame]` | 52 | `TypeError` | `def build_optimized_weights_over_time(expected_returns: pd.DataFrame, *, covariance_by_da...` |
| `compute_portfolio_performance` | `PortfolioPerformance` | 55 | `TypeError, ValueError` | `def compute_portfolio_performance(weights: pd.DataFrame, asset_returns: pd.DataFrame, *, ...` |

| Class | Bases | LOC |
|---|---|---:|
| `PortfolioPerformance` | `-` | 11 |

#### Module Atlas `src/portfolio/covariance.py`

| Metric | Value |
|---|---|
| Module path | `src/portfolio/covariance.py` |
| Python module | `src.portfolio.covariance` |
| Role | Portfolio construction |
| LOC | 42 |
| Imports | 3 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, pandas, typing
      |
      v
[module] src.portfolio.covariance
      |
      +-- functions: 1
      |
[inbound] src.experiments.runner:_run_portfolio_backtest
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `build_rolling_covariance_by_date` | `dict[pd.Timestamp, pd.DataFrame]` | 32 | `TypeError, ValueError` | `def build_rolling_covariance_by_date(asset_returns: pd.DataFrame, *, window: int = 60, mi...` |

#### Module Atlas `src/portfolio/optimizer.py`

| Metric | Value |
|---|---|
| Module path | `src/portfolio/optimizer.py` |
| Python module | `src.portfolio.optimizer` |
| Role | Portfolio construction |
| LOC | 179 |
| Imports | 6 |
| Functions | 3 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, scipy.optimize
      |
      v
[module] src.portfolio.optimizer
      |
      +-- functions: 3
      |
[inbound] src.portfolio.construction:build_optimized_weights_over_time, src.portfolio.optim...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_prepare_covariance` | `pd.DataFrame` | 16 | `TypeError` | `def _prepare_covariance(assets: pd.Index, covariance: pd.DataFrame \| None) -> pd.DataFrame` |
| `_initial_weights` | `np.ndarray` | 22 | `-` | `def _initial_weights(assets: pd.Index, *, constraints: PortfolioConstraints, prev_weights...` |
| `optimize_mean_variance` | `tuple[pd.Series, dict[str, float | str | bool | dict[str, float]]]` | 123 | `TypeError, ValueError` | `def optimize_mean_variance(expected_returns: pd.Series, *, covariance: pd.DataFrame \| No...` |

### 17.11 Package `src/risk`

| Metric | Value |
|---|---|
| Role | Risk controls |
| Module count | 3 |
| Total LOC | 113 |
| Total functions | 4 |
| Total classes | 0 |

#### Module Atlas `src/risk/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/risk/__init__.py` |
| Python module | `src.risk` |
| Role | Risk controls |
| LOC | 9 |
| Imports | 2 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .controls, .position_sizing
      |
      v
[module] src.risk
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/risk/controls.py`

| Metric | Value |
|---|---|
| Module path | `src/risk/controls.py` |
| Python module | `src.risk.controls` |
| Role | Risk controls |
| LOC | 50 |
| Imports | 2 |
| Functions | 2 |
| Classes | 0 |

```text
[imports] __future__, pandas
      |
      v
[module] src.risk.controls
      |
      +-- functions: 2
      |
[inbound] src.backtesting.engine:run_backtest, src.risk.controls:drawdown_cooloff_multiplier
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_drawdown` | `pd.Series` | 11 | `TypeError` | `def compute_drawdown(equity: pd.Series) -> pd.Series` |
| `drawdown_cooloff_multiplier` | `pd.Series` | 32 | `TypeError, ValueError` | `def drawdown_cooloff_multiplier(equity: pd.Series, max_drawdown: float = 0.2, cooloff_bar...` |

#### Module Atlas `src/risk/position_sizing.py`

| Metric | Value |
|---|---|
| Module path | `src/risk/position_sizing.py` |
| Python module | `src.risk.position_sizing` |
| Role | Risk controls |
| LOC | 54 |
| Imports | 4 |
| Functions | 2 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.risk.position_sizing
      |
      +-- functions: 2
      |
[inbound] src.backtesting.engine:run_backtest, src.backtesting.strategies:vol_targeted_sign...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_vol_target_leverage` | `pd.Series` | 18 | `TypeError` | `def compute_vol_target_leverage(vol: pd.Series, target_vol: float, max_leverage: float = ...` |
| `scale_signal_by_vol` | `pd.Series` | 26 | `TypeError` | `def scale_signal_by_vol(signal: pd.Series, vol: pd.Series, target_vol: float, max_leverag...` |

### 17.12 Package `src/signals`

| Metric | Value |
|---|---|
| Role | Signal generation |
| Module count | 6 |
| Total LOC | 208 |
| Total functions | 5 |
| Total classes | 0 |

#### Module Atlas `src/signals/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/signals/__init__.py` |
| Python module | `src.signals` |
| Role | Signal generation |
| LOC | 13 |
| Imports | 5 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .momentum_signal, .rsi_signal, .stochastic_signal, .trend_signal
      |
      v
[module] src.signals
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/signals/momentum_signal.py`

| Metric | Value |
|---|---|
| Module path | `src/signals/momentum_signal.py` |
| Python module | `src.signals.momentum_signal` |
| Role | Signal generation |
| LOC | 40 |
| Imports | 2 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, pandas
      |
      v
[module] src.signals.momentum_signal
      |
      +-- functions: 1
      |
[inbound] src.backtesting.strategies:momentum_strategy
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_momentum_signal` | `pd.DataFrame` | 32 | `KeyError, ValueError` | `def compute_momentum_signal(df: pd.DataFrame, momentum_col: str, long_threshold: float = ...` |

#### Module Atlas `src/signals/rsi_signal.py`

| Metric | Value |
|---|---|
| Module path | `src/signals/rsi_signal.py` |
| Python module | `src.signals.rsi_signal` |
| Role | Signal generation |
| LOC | 35 |
| Imports | 2 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, pandas
      |
      v
[module] src.signals.rsi_signal
      |
      +-- functions: 1
      |
[inbound] src.backtesting.strategies:rsi_strategy
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_rsi_signal` | `pd.DataFrame` | 28 | `ValueError` | `def compute_rsi_signal(df: pd.DataFrame, rsi_col: str, buy_level: float, sell_level: floa...` |

#### Module Atlas `src/signals/stochastic_signal.py`

| Metric | Value |
|---|---|
| Module path | `src/signals/stochastic_signal.py` |
| Python module | `src.signals.stochastic_signal` |
| Role | Signal generation |
| LOC | 38 |
| Imports | 2 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, pandas
      |
      v
[module] src.signals.stochastic_signal
      |
      +-- functions: 1
      |
[inbound] src.backtesting.strategies:stochastic_strategy
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_stochastic_signal` | `pd.DataFrame` | 30 | `KeyError, ValueError` | `def compute_stochastic_signal(df: pd.DataFrame, k_col: str, buy_level: float = 20.0, sell...` |

#### Module Atlas `src/signals/trend_signal.py`

| Metric | Value |
|---|---|
| Module path | `src/signals/trend_signal.py` |
| Python module | `src.signals.trend_signal` |
| Role | Signal generation |
| LOC | 36 |
| Imports | 2 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, pandas
      |
      v
[module] src.signals.trend_signal
      |
      +-- functions: 1
      |
[inbound] src.backtesting.strategies:trend_state_signal
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_trend_state_signal` | `pd.DataFrame` | 28 | `KeyError, ValueError` | `def compute_trend_state_signal(df: pd.DataFrame, state_col: str, signal_col: str = 'trend...` |

#### Module Atlas `src/signals/volatility_signal.py`

| Metric | Value |
|---|---|
| Module path | `src/signals/volatility_signal.py` |
| Python module | `src.signals.volatility_signal` |
| Role | Signal generation |
| LOC | 46 |
| Imports | 2 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, pandas
      |
      v
[module] src.signals.volatility_signal
      |
      +-- functions: 1
      |
[inbound] src.backtesting.strategies:volatility_regime_strategy, tests.test_core:test_volat...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `compute_volatility_regime_signal` | `pd.DataFrame` | 38 | `KeyError, ValueError` | `def compute_volatility_regime_signal(df: pd.DataFrame, vol_col: str, quantile: float = 0....` |

### 17.13 Package `src/src_data`

| Metric | Value |
|---|---|
| Role | Data ingestion / PIT / storage |
| Module count | 9 |
| Total LOC | 831 |
| Total functions | 17 |
| Total classes | 3 |

#### Module Atlas `src/src_data/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/__init__.py` |
| Python module | `src.src_data` |
| Role | Data ingestion / PIT / storage |
| LOC | 34 |
| Imports | 4 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .loaders, .pit, .storage, .validation
      |
      v
[module] src.src_data
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/src_data/loaders.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/loaders.py` |
| Python module | `src.src_data.loaders` |
| Role | Data ingestion / PIT / storage |
| LOC | 84 |
| Imports | 5 |
| Functions | 2 |
| Classes | 0 |

```text
[imports] __future__, pandas, src.src_data.providers.alphavantage, src.src_data.providers.y...
      |
      v
[module] src.src_data.loaders
      |
      +-- functions: 2
      |
[inbound] src.experiments.runner:_load_asset_frames, src.src_data.loaders:load_ohlcv_panel
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `load_ohlcv` | `pd.DataFrame` | 45 | `ValueError` | `def load_ohlcv(symbol: str, start: str \| None = None, end: str \| None = None, interval:...` |
| `load_ohlcv_panel` | `dict[str, pd.DataFrame]` | 27 | `ValueError` | `def load_ohlcv_panel(symbols: Sequence[str], start: str \| None = None, end: str \| None ...` |

#### Module Atlas `src/src_data/pit.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/pit.py` |
| Python module | `src.src_data.pit` |
| Role | Data ingestion / PIT / storage |
| LOC | 250 |
| Imports | 6 |
| Functions | 7 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, pathlib
      |
      v
[module] src.src_data.pit
      |
      +-- functions: 7
      |
[inbound] src.experiments.runner:_load_asset_frames, src.src_data.pit:apply_pit_hardening, ...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `align_ohlcv_timestamps` | `pd.DataFrame` | 40 | `TypeError, ValueError` | `def align_ohlcv_timestamps(df: pd.DataFrame, *, source_timezone: str = 'UTC', output_time...` |
| `apply_corporate_actions_policy` | `tuple[pd.DataFrame, dict[str, Any]]` | 45 | `ValueError` | `def apply_corporate_actions_policy(df: pd.DataFrame, *, policy: str = 'none', adj_close_c...` |
| `_resolve_snapshot_path` | `Path` | 10 | `-` | `def _resolve_snapshot_path(path: str \| Path) -> Path` |
| `load_universe_snapshot` | `pd.DataFrame` | 33 | `FileNotFoundError, ValueError` | `def load_universe_snapshot(path: str \| Path) -> pd.DataFrame` |
| `symbols_active_in_snapshot` | `list[str]` | 15 | `-` | `def symbols_active_in_snapshot(snapshot_df: pd.DataFrame, as_of: str \| pd.Timestamp) -> ...` |
| `assert_symbol_in_snapshot` | `None` | 15 | `ValueError` | `def assert_symbol_in_snapshot(symbol: str, snapshot_df: pd.DataFrame, *, as_of: str \| pd...` |
| `apply_pit_hardening` | `tuple[pd.DataFrame, dict[str, Any]]` | 55 | `-` | `def apply_pit_hardening(df: pd.DataFrame, *, pit_cfg: Mapping[str, Any] \| None = None, s...` |

#### Module Atlas `src/src_data/providers/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/providers/__init__.py` |
| Python module | `src.src_data.providers` |
| Role | Data ingestion / PIT / storage |
| LOC | 9 |
| Imports | 3 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] .alphavantage, .base, .yahoo
      |
      v
[module] src.src_data.providers
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/src_data/providers/alphavantage.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/providers/alphavantage.py` |
| Python module | `src.src_data.providers.alphavantage` |
| Role | Data ingestion / PIT / storage |
| LOC | 86 |
| Imports | 7 |
| Functions | 0 |
| Classes | 1 |

```text
[imports] __future__, dataclasses, os, pandas
      |
      v
[module] src.src_data.providers.alphavantage
      |
      +-- classes: 1
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

| Class | Bases | LOC |
|---|---|---:|
| `AlphaVantageFXProvider` | `MarketDataProvider` | 73 |

#### Module Atlas `src/src_data/providers/base.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/providers/base.py` |
| Python module | `src.src_data.providers.base` |
| Role | Data ingestion / PIT / storage |
| LOC | 24 |
| Imports | 3 |
| Functions | 0 |
| Classes | 1 |

```text
[imports] __future__, abc, pandas
      |
      v
[module] src.src_data.providers.base
      |
      +-- classes: 1
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

| Class | Bases | LOC |
|---|---|---:|
| `MarketDataProvider` | `ABC` | 18 |

#### Module Atlas `src/src_data/providers/yahoo.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/providers/yahoo.py` |
| Python module | `src.src_data.providers.yahoo` |
| Role | Data ingestion / PIT / storage |
| LOC | 79 |
| Imports | 5 |
| Functions | 0 |
| Classes | 1 |

```text
[imports] __future__, dataclasses, pandas, src.src_data.providers.base
      |
      v
[module] src.src_data.providers.yahoo
      |
      +-- classes: 1
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

| Class | Bases | LOC |
|---|---|---:|
| `YahooFinanceProvider` | `MarketDataProvider` | 68 |

#### Module Atlas `src/src_data/storage.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/storage.py` |
| Python module | `src.src_data.storage` |
| Role | Data ingestion / PIT / storage |
| LOC | 208 |
| Imports | 8 |
| Functions | 7 |
| Classes | 0 |

```text
[imports] __future__, datetime, json, pandas
      |
      v
[module] src.src_data.storage
      |
      +-- functions: 7
      |
[inbound] src.experiments.runner:_data_stats_payload, src.experiments.runner:_load_asset_fr...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_resolve_path` | `Path` | 9 | `-` | `def _resolve_path(path: str \| Path) -> Path` |
| `_resolve_snapshot_dir` | `Path` | 14 | `ValueError` | `def _resolve_snapshot_dir(*, root_dir: str \| Path, stage: str, dataset_id: str) -> Path` |
| `asset_frames_to_long_frame` | `pd.DataFrame` | 26 | `TypeError, ValueError` | `def asset_frames_to_long_frame(asset_frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame` |
| `long_frame_to_asset_frames` | `dict[str, pd.DataFrame]` | 17 | `ValueError` | `def long_frame_to_asset_frames(frame: pd.DataFrame) -> dict[str, pd.DataFrame]` |
| `build_dataset_snapshot_metadata` | `dict[str, Any]` | 28 | `-` | `def build_dataset_snapshot_metadata(asset_frames: Mapping[str, pd.DataFrame], *, dataset_...` |
| `save_dataset_snapshot` | `dict[str, Any]` | 41 | `-` | `def save_dataset_snapshot(asset_frames: Mapping[str, pd.DataFrame], *, dataset_id: str, s...` |
| `load_dataset_snapshot` | `tuple[dict[str, pd.DataFrame], dict[str, Any]]` | 39 | `FileNotFoundError, ValueError` | `def load_dataset_snapshot(*, stage: str, root_dir: str \| Path \| None = None, dataset_id...` |

#### Module Atlas `src/src_data/validation.py`

| Metric | Value |
|---|---|
| Module path | `src/src_data/validation.py` |
| Python module | `src.src_data.validation` |
| Role | Data ingestion / PIT / storage |
| LOC | 57 |
| Imports | 4 |
| Functions | 1 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.src_data.validation
      |
      +-- functions: 1
      |
[inbound] src.experiments.runner:_load_asset_frames, tests.test_core:test_validate_ohlcv_fl...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `validate_ohlcv` | `None` | 49 | `ValueError` | `def validate_ohlcv(df: pd.DataFrame, required_columns: Iterable[str] = ('open', 'high', '...` |

### 17.14 Package `src/utils`

| Metric | Value |
|---|---|
| Role | Infrastructure utilities |
| Module count | 5 |
| Total LOC | 1096 |
| Total functions | 40 |
| Total classes | 2 |

#### Module Atlas `src/utils/__init__.py`

| Metric | Value |
|---|---|
| Module path | `src/utils/__init__.py` |
| Python module | `src.utils` |
| Role | Infrastructure utilities |
| LOC | 0 |
| Imports | 0 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] none
      |
      v
[module] src.utils
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `src/utils/config.py`

| Metric | Value |
|---|---|
| Module path | `src/utils/config.py` |
| Python module | `src.utils.config` |
| Role | Infrastructure utilities |
| LOC | 590 |
| Imports | 7 |
| Functions | 22 |
| Classes | 1 |

```text
[imports] __future__, os, pathlib, src.utils.paths
      |
      v
[module] src.utils.config
      |
      +-- functions: 22
      |
      +-- classes: 1
      |
[inbound] src.experiments.runner:run_experiment, src.utils.config:_deep_update, src.utils.c...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_resolve_config_path` | `Path` | 14 | `ConfigError, FileNotFoundError` | `def _resolve_config_path(config_path: str \| Path) -> Path` |
| `_load_yaml` | `dict[str, Any]` | 10 | `ConfigError` | `def _load_yaml(path: Path) -> dict[str, Any]` |
| `_deep_update` | `dict[str, Any]` | 9 | `-` | `def _deep_update(base: Mapping[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]` |
| `_load_with_extends` | `dict[str, Any]` | 19 | `ConfigError` | `def _load_with_extends(path: Path, seen: set[Path] \| None = None) -> dict[str, Any]` |
| `_default_risk_block` | `dict[str, Any]` | 17 | `ConfigError` | `def _default_risk_block(risk: dict[str, Any]) -> dict[str, Any]` |
| `_default_data_block` | `dict[str, Any]` | 46 | `-` | `def _default_data_block(data: dict[str, Any]) -> dict[str, Any]` |
| `_default_backtest_block` | `dict[str, Any]` | 10 | `-` | `def _default_backtest_block(backtest: dict[str, Any]) -> dict[str, Any]` |
| `_default_portfolio_block` | `dict[str, Any]` | 18 | `-` | `def _default_portfolio_block(portfolio: dict[str, Any]) -> dict[str, Any]` |
| `_default_monitoring_block` | `dict[str, Any]` | 11 | `-` | `def _default_monitoring_block(monitoring: dict[str, Any]) -> dict[str, Any]` |
| `_default_execution_block` | `dict[str, Any]` | 14 | `-` | `def _default_execution_block(execution: dict[str, Any]) -> dict[str, Any]` |
| `_resolve_logging_block` | `dict[str, Any]` | 11 | `-` | `def _resolve_logging_block(logging_cfg: dict[str, Any], config_path: Path) -> dict[str, Any]` |
| `_validate_data_block` | `None` | 95 | `ConfigError` | `def _validate_data_block(data: dict[str, Any]) -> None` |
| `_inject_api_key_from_env` | `None` | 9 | `-` | `def _inject_api_key_from_env(data: dict[str, Any]) -> None` |
| `_validate_features_block` | `None` | 14 | `ConfigError` | `def _validate_features_block(features: Any) -> None` |
| `_validate_model_block` | `None` | 84 | `ConfigError` | `def _validate_model_block(model: dict[str, Any]) -> None` |
| `_validate_signals_block` | `None` | 9 | `ConfigError` | `def _validate_signals_block(signals: dict[str, Any]) -> None` |
| `_validate_risk_block` | `None` | 24 | `ConfigError` | `def _validate_risk_block(risk: dict[str, Any]) -> None` |
| `_validate_backtest_block` | `None` | 14 | `ConfigError` | `def _validate_backtest_block(backtest: dict[str, Any]) -> None` |
| `_validate_portfolio_block` | `None` | 31 | `ConfigError` | `def _validate_portfolio_block(portfolio: dict[str, Any]) -> None` |
| `_validate_monitoring_block` | `None` | 12 | `ConfigError` | `def _validate_monitoring_block(monitoring: dict[str, Any]) -> None` |
| `_validate_execution_block` | `None` | 17 | `ConfigError` | `def _validate_execution_block(execution: dict[str, Any]) -> None` |
| `load_experiment_config` | `dict[str, Any]` | 37 | `ConfigError` | `def load_experiment_config(config_path: str \| Path) -> dict[str, Any]` |

| Class | Bases | LOC |
|---|---|---:|
| `ConfigError` | `ValueError` | 2 |

#### Module Atlas `src/utils/paths.py`

| Metric | Value |
|---|---|
| Module path | `src/utils/paths.py` |
| Python module | `src.utils.paths` |
| Role | Infrastructure utilities |
| LOC | 63 |
| Imports | 2 |
| Functions | 3 |
| Classes | 0 |

```text
[imports] __future__, pathlib
      |
      v
[module] src.utils.paths
      |
      +-- functions: 3
      |
[inbound] src.experiments.runner:run_experiment, src.utils.config:_default_data_block, src....
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `in_project` | `Path` | 6 | `-` | `def in_project(*parts: str \| Path) -> Path` |
| `ensure_directories_exist` | `None` | 17 | `-` | `def ensure_directories_exist() -> None` |
| `describe_paths` | `None` | 16 | `-` | `def describe_paths() -> None` |

#### Module Atlas `src/utils/repro.py`

| Metric | Value |
|---|---|
| Module path | `src/utils/repro.py` |
| Python module | `src.utils.repro` |
| Role | Infrastructure utilities |
| LOC | 149 |
| Imports | 5 |
| Functions | 3 |
| Classes | 1 |

```text
[imports] __future__, numpy, os, random
      |
      v
[module] src.utils.repro
      |
      +-- functions: 3
      |
      +-- classes: 1
      |
[inbound] src.experiments.runner:run_experiment, src.utils.config:load_experiment_config, s...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `normalize_runtime_config` | `dict[str, Any]` | 12 | `-` | `def normalize_runtime_config(runtime_cfg: Mapping[str, Any] \| None) -> dict[str, Any]` |
| `validate_runtime_config` | `dict[str, Any]` | 32 | `RuntimeConfigError` | `def validate_runtime_config(runtime_cfg: Mapping[str, Any] \| None) -> dict[str, Any]` |
| `apply_runtime_reproducibility` | `dict[str, Any]` | 71 | `-` | `def apply_runtime_reproducibility(runtime_cfg: Mapping[str, Any] \| None) -> dict[str, Any]` |

| Class | Bases | LOC |
|---|---|---:|
| `RuntimeConfigError` | `ValueError` | 2 |

#### Module Atlas `src/utils/run_metadata.py`

| Metric | Value |
|---|---|
| Module path | `src/utils/run_metadata.py` |
| Python module | `src.utils.run_metadata` |
| Role | Infrastructure utilities |
| LOC | 294 |
| Imports | 14 |
| Functions | 12 |
| Classes | 0 |

```text
[imports] __future__, copy, datetime, hashlib
      |
      v
[module] src.utils.run_metadata
      |
      +-- functions: 12
      |
[inbound] src.experiments.runner:_save_artifacts, src.experiments.runner:run_experiment, sr...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_normalize_path_string` | `str` | 13 | `-` | `def _normalize_path_string(value: str, project_root: Path) -> str` |
| `_normalize_for_hash` | `Any` | 31 | `-` | `def _normalize_for_hash(value: Any, project_root: Path) -> Any` |
| `_json_default` | `Any` | 16 | `-` | `def _json_default(value: Any) -> Any` |
| `canonical_json_dumps` | `str` | 6 | `-` | `def canonical_json_dumps(payload: Mapping[str, Any]) -> str` |
| `compute_config_hash` | `tuple[str, dict[str, Any]]` | 9 | `-` | `def compute_config_hash(cfg: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> tup...` |
| `compute_dataframe_fingerprint` | `dict[str, Any]` | 42 | `TypeError, ValueError` | `def compute_dataframe_fingerprint(df: pd.DataFrame) -> dict[str, Any]` |
| `_safe_git` | `str | None` | 19 | `-` | `def _safe_git(args: list[str]) -> str \| None` |
| `collect_git_metadata` | `dict[str, Any]` | 14 | `-` | `def collect_git_metadata() -> dict[str, Any]` |
| `collect_environment_metadata` | `dict[str, Any]` | 19 | `-` | `def collect_environment_metadata() -> dict[str, Any]` |
| `build_run_metadata` | `dict[str, Any]` | 30 | `-` | `def build_run_metadata(*, config_path: str \| Path, runtime_applied: Mapping[str, Any], c...` |
| `file_sha256` | `str` | 11 | `-` | `def file_sha256(path: str \| Path) -> str` |
| `build_artifact_manifest` | `dict[str, Any]` | 21 | `-` | `def build_artifact_manifest(artifacts: Mapping[str, str \| Path]) -> dict[str, Any]` |

### 17.15 Package `tests`

| Metric | Value |
|---|---|
| Role | Regression tests |
| Module count | 8 |
| Total LOC | 1159 |
| Total functions | 39 |
| Total classes | 0 |

#### Module Atlas `tests/conftest.py`

| Metric | Value |
|---|---|
| Module path | `tests/conftest.py` |
| Python module | `tests.conftest` |
| Role | Regression tests |
| LOC | 8 |
| Imports | 3 |
| Functions | 0 |
| Classes | 0 |

```text
[imports] __future__, pathlib, sys
      |
      v
[module] tests.conftest
      |
[inbound] external / CLI / registry
```

Το module δεν περιέχει top-level functions.

#### Module Atlas `tests/test_contracts_metrics_pit.py`

| Metric | Value |
|---|---|
| Module path | `tests/test_contracts_metrics_pit.py` |
| Python module | `tests.test_contracts_metrics_pit` |
| Role | Regression tests |
| LOC | 205 |
| Imports | 8 |
| Functions | 7 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, pytest
      |
      v
[module] tests.test_contracts_metrics_pit
      |
      +-- functions: 7
      |
[inbound] tests.test_contracts_metrics_pit:test_forward_horizon_guard_trims_train_rows_in_t...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_synthetic_frame` | `pd.DataFrame` | 15 | `-` | `def _synthetic_frame(n: int = 240) -> pd.DataFrame` |
| `test_forward_horizon_guard_trims_train_rows_in_time_split` | `None` | 24 | `-` | `def test_forward_horizon_guard_trims_train_rows_in_time_split() -> None` |
| `test_feature_contract_rejects_target_like_feature_columns` | `None` | 19 | `-` | `def test_feature_contract_rejects_target_like_feature_columns() -> None` |
| `test_metrics_suite_includes_risk_and_cost_attribution` | `None` | 37 | `-` | `def test_metrics_suite_includes_risk_and_cost_attribution() -> None` |
| `test_align_ohlcv_timestamps_sorts_and_deduplicates` | `None` | 36 | `-` | `def test_align_ohlcv_timestamps_sorts_and_deduplicates() -> None` |
| `test_apply_corporate_actions_policy_adj_close_ratio` | `None` | 25 | `-` | `def test_apply_corporate_actions_policy_adj_close_ratio() -> None` |
| `test_universe_snapshot_asof_membership_check` | `None` | 19 | `-` | `def test_universe_snapshot_asof_membership_check(tmp_path) -> None` |

#### Module Atlas `tests/test_core.py`

| Metric | Value |
|---|---|
| Module path | `tests/test_core.py` |
| Python module | `tests.test_core` |
| Role | Regression tests |
| LOC | 167 |
| Imports | 8 |
| Functions | 7 |
| Classes | 0 |

```text
[imports] numpy, pandas, pytest, src.backtesting.engine
      |
      v
[module] tests.test_core
      |
      +-- functions: 7
      |
[inbound] external / CLI / registry
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `test_compute_returns_simple_and_log` | `None` | 13 | `-` | `def test_compute_returns_simple_and_log() -> None` |
| `test_add_trend_features_columns` | `None` | 13 | `-` | `def test_add_trend_features_columns() -> None` |
| `test_validate_ohlcv_flags_invalid_high_low` | `None` | 19 | `-` | `def test_validate_ohlcv_flags_invalid_high_low() -> None` |
| `test_run_backtest_costs_and_slippage_reduce_returns` | `None` | 33 | `-` | `def test_run_backtest_costs_and_slippage_reduce_returns() -> None` |
| `test_run_backtest_log_returns_are_converted` | `None` | 26 | `-` | `def test_run_backtest_log_returns_are_converted() -> None` |
| `test_run_backtest_charges_initial_entry_turnover` | `None` | 27 | `-` | `def test_run_backtest_charges_initial_entry_turnover() -> None` |
| `test_volatility_regime_signal_is_causal_by_default` | `None` | 13 | `-` | `def test_volatility_regime_signal_is_causal_by_default() -> None` |

#### Module Atlas `tests/test_no_lookahead.py`

| Metric | Value |
|---|---|
| Module path | `tests/test_no_lookahead.py` |
| Python module | `tests.test_no_lookahead` |
| Role | Regression tests |
| LOC | 150 |
| Imports | 4 |
| Functions | 5 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, src.experiments.models
      |
      v
[module] tests.test_no_lookahead
      |
      +-- functions: 5
      |
[inbound] tests.test_no_lookahead:test_binary_forward_target_keeps_tail_labels_nan, tests.t...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_synthetic_price_frame` | `pd.DataFrame` | 16 | `-` | `def _synthetic_price_frame(n: int = 260) -> pd.DataFrame` |
| `test_walk_forward_predictions_are_oos_only` | `None` | 28 | `-` | `def test_walk_forward_predictions_are_oos_only() -> None` |
| `test_purged_splits_respect_anti_leakage_gap` | `None` | 31 | `-` | `def test_purged_splits_respect_anti_leakage_gap() -> None` |
| `test_binary_forward_target_keeps_tail_labels_nan` | `None` | 21 | `-` | `def test_binary_forward_target_keeps_tail_labels_nan() -> None` |
| `test_quantile_target_uses_train_only_distribution_per_fold` | `None` | 38 | `-` | `def test_quantile_target_uses_train_only_distribution_per_fold() -> None` |

#### Module Atlas `tests/test_portfolio.py`

| Metric | Value |
|---|---|
| Module path | `tests/test_portfolio.py` |
| Python module | `tests.test_portfolio` |
| Role | Regression tests |
| LOC | 203 |
| Imports | 4 |
| Functions | 6 |
| Classes | 0 |

```text
[imports] __future__, numpy, pandas, src.portfolio
      |
      v
[module] tests.test_portfolio
      |
      +-- functions: 6
      |
[inbound] external / CLI / registry
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `test_apply_constraints_respects_bounds_group_gross_and_turnover` | `None` | 31 | `-` | `def test_apply_constraints_respects_bounds_group_gross_and_turnover() -> None` |
| `test_build_weights_from_signals_over_time_respects_constraints` | `None` | 35 | `-` | `def test_build_weights_from_signals_over_time_respects_constraints() -> None` |
| `test_optimize_mean_variance_respects_core_constraints` | `None` | 30 | `-` | `def test_optimize_mean_variance_respects_core_constraints() -> None` |
| `test_compute_portfolio_performance_uses_shifted_weights` | `None` | 38 | `-` | `def test_compute_portfolio_performance_uses_shifted_weights() -> None` |
| `test_compute_portfolio_performance_charges_initial_turnover` | `None` | 20 | `-` | `def test_compute_portfolio_performance_charges_initial_turnover() -> None` |
| `test_optimize_mean_variance_fallback_respects_max_gross_leverage` | `None` | 25 | `-` | `def test_optimize_mean_variance_fallback_respects_max_gross_leverage() -> None` |

#### Module Atlas `tests/test_reproducibility.py`

| Metric | Value |
|---|---|
| Module path | `tests/test_reproducibility.py` |
| Python module | `tests.test_reproducibility` |
| Role | Regression tests |
| LOC | 117 |
| Imports | 8 |
| Functions | 6 |
| Classes | 0 |

```text
[imports] __future__, copy, numpy, pandas
      |
      v
[module] tests.test_reproducibility
      |
      +-- functions: 6
      |
[inbound] external / CLI / registry
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `test_runtime_defaults_are_loaded_from_config` | `None` | 13 | `-` | `def test_runtime_defaults_are_loaded_from_config() -> None` |
| `test_validate_runtime_config_rejects_invalid_threads` | `None` | 8 | `-` | `def test_validate_runtime_config_rejects_invalid_threads() -> None` |
| `test_apply_runtime_reproducibility_sets_deterministic_numpy_stream` | `None` | 21 | `-` | `def test_apply_runtime_reproducibility_sets_deterministic_numpy_stream() -> None` |
| `test_compute_config_hash_ignores_config_path_field` | `None` | 14 | `-` | `def test_compute_config_hash_ignores_config_path_field() -> None` |
| `test_dataframe_fingerprint_is_stable_across_row_and_column_order` | `None` | 19 | `-` | `def test_dataframe_fingerprint_is_stable_across_row_and_column_order() -> None` |
| `test_artifact_manifest_contains_file_hashes` | `None` | 19 | `-` | `def test_artifact_manifest_contains_file_hashes(tmp_path) -> None` |

#### Module Atlas `tests/test_runner_extensions.py`

| Metric | Value |
|---|---|
| Module path | `tests/test_runner_extensions.py` |
| Python module | `tests.test_runner_extensions` |
| Role | Regression tests |
| LOC | 223 |
| Imports | 10 |
| Functions | 5 |
| Classes | 0 |

```text
[imports] __future__, json, numpy, pandas
      |
      v
[module] tests.test_runner_extensions
      |
      +-- functions: 5
      |
[inbound] tests.test_runner_extensions:test_dataset_snapshot_roundtrip, tests.test_runner_e...
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `_synthetic_ohlcv` | `pd.DataFrame` | 24 | `-` | `def _synthetic_ohlcv(*, periods: int = 180, seed: int = 0, amplitude: float = 0.01) -> pd...` |
| `test_dataset_snapshot_roundtrip` | `None` | 30 | `-` | `def test_dataset_snapshot_roundtrip(tmp_path) -> None` |
| `test_build_rebalance_orders_reports_share_deltas` | `None` | 17 | `-` | `def test_build_rebalance_orders_reports_share_deltas() -> None` |
| `test_logistic_regression_model_registry_outputs_oos_metrics` | `None` | 32 | `-` | `def test_logistic_regression_model_registry_outputs_oos_metrics() -> None` |
| `test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution` | `None` | 97 | `-` | `def test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution(t...` |

#### Module Atlas `tests/test_time_splits.py`

| Metric | Value |
|---|---|
| Module path | `tests/test_time_splits.py` |
| Python module | `tests.test_time_splits` |
| Role | Regression tests |
| LOC | 86 |
| Imports | 3 |
| Functions | 3 |
| Classes | 0 |

```text
[imports] __future__, numpy, src.evaluation.time_splits
      |
      v
[module] tests.test_time_splits
      |
      +-- functions: 3
      |
[inbound] external / CLI / registry
```

| Function | Return | LOC | Raises | Signature |
|---|---|---:|---|---|
| `test_walk_forward_splits_are_time_ordered_and_non_overlapping` | `None` | 25 | `-` | `def test_walk_forward_splits_are_time_ordered_and_non_overlapping() -> None` |
| `test_purged_walk_forward_respects_purge_and_embargo` | `None` | 27 | `-` | `def test_purged_walk_forward_respects_purge_and_embargo() -> None` |
| `test_build_time_splits_uses_target_horizon_for_default_purge` | `None` | 19 | `-` | `def test_build_time_splits_uses_target_horizon_for_default_purge() -> None` |
