## 17. Αυτόματα Παραγόμενο Module Atlas και Πλήρης API Αναφορά

Η ενότητα αυτή παράγεται μηχανικά από το τρέχον codebase και λειτουργεί ως canonical αναφορά
για onboarding, architecture review και impact analysis. Συμπληρώνει το αφηγηματικό σώμα του
βιβλίου με αυστηρά αποτυπωμένα imports, globals, classes, functions, methods και direct callers.

### 17.1 Snapshot Codebase

- Python modules σε `src/` και `tests/`: `63`
- Top-level functions/tests: `264`
- Class methods: `4`
- Συνολικά callable definitions: `268`
- Classes/dataclasses/interfaces: `13`
- YAML configuration files: `5`
- Test suite snapshot: `51 passed, 2 warnings in 3.16s`

### 17.2 Raw Test Snapshot

```text
...................................................                      [100%]
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: Type google.protobuf.pyext._message.ScalarMapContainer uses PyType_Spec with a metaclass that has custom tp_new. This is deprecated and will no longer be allowed in Python 3.14.

<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: Type google.protobuf.pyext._message.MessageMapContainer uses PyType_Spec with a metaclass that has custom tp_new. This is deprecated and will no longer be allowed in Python 3.14.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
51 passed, 2 warnings in 3.16s
```

### 17.3 Local Import Graph

```text
src -> χωρις τοπικα imports
src.backtesting -> .engine, .strategies
src.backtesting.engine -> src.evaluation.metrics, src.risk.controls, src.risk.position_sizing
src.backtesting.strategies -> src.risk.position_sizing, src.signals
src.evaluation -> .metrics, .time_splits
src.evaluation.metrics -> χωρις τοπικα imports
src.evaluation.time_splits -> χωρις τοπικα imports
src.execution -> .paper
src.execution.paper -> χωρις τοπικα imports
src.experiments -> .contracts, .runner
src.experiments.contracts -> χωρις τοπικα imports
src.experiments.models -> src.evaluation.time_splits, src.experiments.contracts, src.models.lightgbm_baseline
src.experiments.registry -> src.backtesting.strategies, src.experiments.models, src.features, src.features.technical.indicators, src.features.technical.momentum, src.features.technical.oscillators, src.features.technical.trend
src.experiments.runner -> src.backtesting.engine, src.evaluation.metrics, src.execution.paper, src.experiments.contracts, src.experiments.registry, src.monitoring.drift, src.portfolio, src.src_data.loaders, src.src_data.pit, src.src_data.storage, src.src_data.validation, src.utils.config, src.utils.paths, src.utils.repro, src.utils.run_metadata
src.features -> .lags, .returns, .technical.trend, .volatility
src.features.lags -> χωρις τοπικα imports
src.features.returns -> χωρις τοπικα imports
src.features.technical -> .indicators, .momentum, .oscillators, .trend
src.features.technical.indicators -> χωρις τοπικα imports
src.features.technical.momentum -> χωρις τοπικα imports
src.features.technical.oscillators -> χωρις τοπικα imports
src.features.technical.trend -> χωρις τοπικα imports
src.features.volatility -> χωρις τοπικα imports
src.models -> χωρις τοπικα imports
src.models.lightgbm_baseline -> src.features.lags
src.monitoring -> .drift
src.monitoring.drift -> χωρις τοπικα imports
src.portfolio -> .constraints, .construction, .covariance, .optimizer
src.portfolio.constraints -> χωρις τοπικα imports
src.portfolio.construction -> src.evaluation.metrics, src.portfolio.constraints, src.portfolio.optimizer
src.portfolio.covariance -> χωρις τοπικα imports
src.portfolio.optimizer -> src.portfolio.constraints
src.risk -> .controls, .position_sizing
src.risk.controls -> χωρις τοπικα imports
src.risk.position_sizing -> χωρις τοπικα imports
src.signals -> .momentum_signal, .rsi_signal, .stochastic_signal, .trend_signal, .volatility_signal
src.signals.momentum_signal -> χωρις τοπικα imports
src.signals.rsi_signal -> χωρις τοπικα imports
src.signals.stochastic_signal -> χωρις τοπικα imports
src.signals.trend_signal -> χωρις τοπικα imports
src.signals.volatility_signal -> χωρις τοπικα imports
src.src_data -> .loaders, .pit, .storage, .validation
src.src_data.loaders -> src.src_data.providers.alphavantage, src.src_data.providers.yahoo
src.src_data.pit -> src.utils.paths
src.src_data.providers -> .alphavantage, .base, .yahoo
src.src_data.providers.alphavantage -> src.src_data.providers.base
src.src_data.providers.base -> χωρις τοπικα imports
src.src_data.providers.yahoo -> src.src_data.providers.base
src.src_data.storage -> src.utils.paths, src.utils.run_metadata
src.src_data.validation -> χωρις τοπικα imports
src.utils -> χωρις τοπικα imports
src.utils.config -> src.utils.paths, src.utils.repro
src.utils.paths -> χωρις τοπικα imports
src.utils.repro -> χωρις τοπικα imports
src.utils.run_metadata -> src.utils.paths
tests.conftest -> χωρις τοπικα imports
tests.test_contracts_metrics_pit -> src.evaluation.metrics, src.experiments.contracts, src.experiments.models, src.features.technical.indicators, src.features.technical.oscillators, src.src_data.pit, src.utils.config
tests.test_core -> src.backtesting.engine, src.features.returns, src.features.technical.trend, src.signals.volatility_signal, src.src_data.validation
tests.test_no_lookahead -> src.experiments.models
tests.test_portfolio -> src.portfolio
tests.test_reproducibility -> src.utils.config, src.utils.repro, src.utils.run_metadata
tests.test_runner_extensions -> src.execution.paper, src.experiments.models, src.experiments.runner, src.portfolio.construction, src.src_data.storage
tests.test_time_splits -> src.evaluation.time_splits
```

### 17.4 Call Graph Highlights

```text
src.backtesting.engine:run_backtest <- src.experiments.runner:_run_single_asset_backtest, tests.test_core:test_run_backtest_charges_initial_entry_turnover, tests.test_core:test_run_backtest_costs_and_slippage_reduce_returns, tests.test_core:test_run_backtest_log_returns_are_converted, tests.test_core:test_run_backtest_raises_on_missing_return_while_exposed, tests.test_core:test_run_backtest_vol_targeting_flattens_missing_vol_warmup
src.experiments.models:_train_forward_classifier <- src.experiments.models:train_lightgbm_classifier, src.experiments.models:train_logistic_regression_classifier
src.experiments.runner:run_experiment <- tests.test_runner_extensions:test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution
src.portfolio.construction:compute_portfolio_performance <- src.experiments.runner:_run_portfolio_backtest, tests.test_portfolio:test_compute_portfolio_performance_charges_initial_turnover, tests.test_portfolio:test_compute_portfolio_performance_raises_on_missing_exposed_return, tests.test_portfolio:test_compute_portfolio_performance_uses_shifted_weights
src.portfolio.optimizer:optimize_mean_variance <- src.portfolio.construction:build_optimized_weights_over_time, tests.test_portfolio:test_optimize_mean_variance_fallback_respects_max_gross_leverage, tests.test_portfolio:test_optimize_mean_variance_respects_core_constraints
src.src_data.pit:apply_pit_hardening <- src.experiments.runner:_load_asset_frames, tests.test_contracts_metrics_pit:test_apply_pit_hardening_can_drop_rows_outside_universe_snapshot, tests.test_contracts_metrics_pit:test_apply_pit_hardening_raises_when_symbol_exits_universe_mid_sample
```

### 17.5 Package `src/__init__.py`

- Ρόλος package: Miscellaneous
- Modules: `1`
- LOC: `0`
- Top-level callables: `0`
- Methods: `0`
- Classes: `0`

#### Module `src/__init__.py`

- Python module: `src`
- Ρόλος: Miscellaneous
- LOC: `0`
- Imports: Δεν υπάρχουν imports.
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] none
      |
      v
[module] src
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

### 17.6 Package `src/backtesting`

- Ρόλος package: Backtesting
- Modules: `3`
- LOC: `406`
- Top-level callables: `13`
- Methods: `0`
- Classes: `1`

#### Module `src/backtesting/__init__.py`

- Python module: `src.backtesting`
- Ρόλος: Backtesting
- LOC: `22`
- Imports: `.engine`, `.strategies`
- Global constants / exported symbols:
  - `__all__` = `['run_backtest', 'BacktestResult', 'buy_and_hold_signal', 'trend_state_long_only_signal', 'trend_...`
- ASCII dependency sketch:
```text
[imports] .engine, .strategies
      |
      v
[module] src.backtesting
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/backtesting/engine.py`

- Python module: `src.backtesting.engine`
- Ρόλος: Backtesting
- LOC: `159`
- Imports: `__future__`, `dataclasses`, `numpy`, `pandas`, `src.evaluation.metrics`, `src.risk.controls`, `src.risk.position_sizing`, `typing`
- Global constants / exported symbols:
  - `_ALLOWED_MISSING_RETURN_POLICIES` = `{'raise', 'raise_if_exposed', 'fill_zero'}`
- ASCII dependency sketch:
```text
[imports] __future__, dataclasses, numpy, pandas
      |
      v
[module] src.backtesting.engine
      |
      +-- functions: 2
      |
      +-- classes: 1
      |
[inbound] src.backtesting.engine:run_backtest, src.experiments.runner:_run_single_asset_bac...
```

- Classes στο module:
  - `BacktestResult`

##### Class `src.backtesting.engine:BacktestResult`

- Βάσεις: `-`
- LOC: `12`
- Σύνοψη ρόλου: Store the complete result of a single-asset backtest, including returns, positions, costs, turnover, and the precomputed summary metrics consumed by downstream reporting.
- Fields:
  - `equity_curve` (`pd.Series`, default `-`)
  - `returns` (`pd.Series`, default `-`)
  - `gross_returns` (`pd.Series`, default `-`)
  - `costs` (`pd.Series`, default `-`)
  - `positions` (`pd.Series`, default `-`)
  - `turnover` (`pd.Series`, default `-`)
  - `summary` (`dict`, default `-`)
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

- Top-level callables:
  - `_apply_missing_return_policy`
  - `run_backtest`

##### Callable `src.backtesting.engine:_apply_missing_return_policy`

- Signature: `def _apply_missing_return_policy(returns: pd.Series, prev_positions: pd.Series, missing_return_policy: str) -> pd.Series`
- Return type: `pd.Series`
- LOC: `34`
- Σύνοψη λογικής: Resolve missing-return handling explicitly so exposed positions cannot silently inherit flat PnL from missing market data.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `prev_positions` (keyword-only, `pd.Series`, default `χωρίς default`): Θέσεις της προηγούμενης περιόδου για έλεγχο missing-return exposure και turnover.
  - `missing_return_policy` (keyword-only, `str`, default `χωρίς default`): Policy flag που καθοριζει edge-case handling και validation behavior.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: `src.backtesting.engine:run_backtest`, `src.portfolio.construction:compute_portfolio_performance`

##### Callable `src.backtesting.engine:run_backtest`

- Signature: `def run_backtest(df: pd.DataFrame, signal_col: str, returns_col: str, returns_type: Literal['simple', 'log'] = 'simple', missing_return_policy: str = 'raise_if_exposed', cost_per_unit_turnover: float = 0.0, slippage_per_unit_turnover: float = 0.0, target_vol: Optional[float] = None, vol_col: Optional[str] = None, max_leverage: float = 3.0, dd_guard: bool = True, max_drawdown: float = 0.2, cooloff_bars: int = 20, periods_per_year: int = 252) -> BacktestResult`
- Return type: `BacktestResult`
- LOC: `93`
- Σύνοψη λογικής: Simple vectorized backtest with optional vol targeting, slippage, and drawdown guard.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `signal_col` (positional-or-keyword, `str`, default `χωρίς default`): Όνομα στήλης signal exposure ή conviction sizing.
  - `returns_col` (positional-or-keyword, `str`, default `χωρίς default`): Όνομα στήλης αποδόσεων που τροφοδοτεί backtest, metrics ή model layer.
  - `returns_type` (positional-or-keyword, `Literal['simple', 'log']`, default `'simple'`): Δηλώνει αν οι αποδόσεις ερμηνεύονται ως `simple` ή `log` στο downstream logic.
  - `missing_return_policy` (positional-or-keyword, `str`, default `'raise_if_exposed'`): Policy flag που καθοριζει edge-case handling και validation behavior.
  - `cost_per_unit_turnover` (positional-or-keyword, `float`, default `0.0`): Κόστος συναλλαγής ανά μονάδα turnover στο single-asset backtest.
  - `slippage_per_unit_turnover` (positional-or-keyword, `float`, default `0.0`): Υποτιθέμενο slippage ανά μονάδα turnover στο single-asset backtest.
  - `target_vol` (positional-or-keyword, `Optional[float]`, default `None`): Στοχευμένη ετησιοποιημένη μεταβλητότητα που χρησιμοποιείται για leverage scaling.
  - `vol_col` (positional-or-keyword, `Optional[str]`, default `None`): Όνομα στήλης volatility estimate για scaling ή targeting.
  - `max_leverage` (positional-or-keyword, `float`, default `3.0`): Άνω όριο leverage/exposure που δεν επιτρέπεται να υπερβεί ο allocator/backtester.
  - `dd_guard` (positional-or-keyword, `bool`, default `True`): Flag ενεργοποίησης drawdown guard που μειώνει ή μηδενίζει έκθεση μετά από drawdown.
  - `max_drawdown` (positional-or-keyword, `float`, default `0.2`): Κατώφλι drawdown πέρα από το οποίο ενεργοποιείται το προστατευτικό cooloff logic.
  - `cooloff_bars` (positional-or-keyword, `int`, default `20`): Αριθμός bars στους οποίους παραμένει ενεργός ο drawdown cooloff μηχανισμός.
  - `periods_per_year` (positional-or-keyword, `int`, default `252`): Annualization factor για returns και risk metrics.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`, `ValueError`
- Big-O: O(T) για vectorized single-asset backtest, με σταθερό πλήθος σειρών/μετασχηματισμών.
- Direct callers: `src.experiments.runner:_run_single_asset_backtest`, `tests.test_core:test_run_backtest_charges_initial_entry_turnover`, `tests.test_core:test_run_backtest_costs_and_slippage_reduce_returns`, `tests.test_core:test_run_backtest_log_returns_are_converted`, `tests.test_core:test_run_backtest_raises_on_missing_return_while_exposed`, `tests.test_core:test_run_backtest_vol_targeting_flattens_missing_vol_warmup`

#### Module `src/backtesting/strategies.py`

- Python module: `src.backtesting.strategies`
- Ρόλος: Backtesting
- LOC: `225`
- Imports: `__future__`, `pandas`, `src.risk.position_sizing`, `src.signals`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `buy_and_hold_signal`
  - `trend_state_long_only_signal`
  - `trend_state_signal`
  - `rsi_strategy`
  - `momentum_strategy`
  - `stochastic_strategy`
  - `volatility_regime_strategy`
  - `probabilistic_signal`
  - `conviction_sizing_signal`
  - `regime_filtered_signal`
  - `vol_targeted_signal`

##### Callable `src.backtesting.strategies:buy_and_hold_signal`

- Signature: `def buy_and_hold_signal(df: pd.DataFrame, signal_name: str = 'signal_bh') -> pd.Series`
- Return type: `pd.Series`
- LOC: `8`
- Σύνοψη λογικής: Long-only buy-and-hold signal.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_bh'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:trend_state_long_only_signal`

- Signature: `def trend_state_long_only_signal(df: pd.DataFrame, state_col: str, signal_name: str = 'signal_trend_state_long_only') -> pd.Series`
- Return type: `pd.Series`
- LOC: `13`
- Σύνοψη λογικής: Long-only signal based on a trend state column (expects 1 for bull).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `state_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_trend_state_long_only'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:trend_state_signal`

- Signature: `def trend_state_signal(df: pd.DataFrame, state_col: str, signal_name: str = 'signal_trend_state', mode: str = 'long_short_hold') -> pd.Series`
- Return type: `pd.Series`
- LOC: `16`
- Σύνοψη λογικής: Trend-state strategy wrapper (supports long/short/hold modes).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `state_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_trend_state'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:rsi_strategy`

- Signature: `def rsi_strategy(df: pd.DataFrame, rsi_col: str, buy_level: float = 30.0, sell_level: float = 70.0, signal_name: str = 'signal_rsi', mode: str = 'long_short_hold') -> pd.Series`
- Return type: `pd.Series`
- LOC: `20`
- Σύνοψη λογικής: RSI strategy wrapper (supports long/short/hold modes).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `rsi_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `buy_level` (positional-or-keyword, `float`, default `30.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `sell_level` (positional-or-keyword, `float`, default `70.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_rsi'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:momentum_strategy`

- Signature: `def momentum_strategy(df: pd.DataFrame, momentum_col: str, long_threshold: float = 0.0, short_threshold: float | None = None, signal_name: str = 'signal_momentum', mode: str = 'long_short_hold') -> pd.Series`
- Return type: `pd.Series`
- LOC: `20`
- Σύνοψη λογικής: Momentum strategy wrapper (supports long/short/hold modes).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `momentum_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `long_threshold` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `short_threshold` (positional-or-keyword, `float | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_momentum'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:stochastic_strategy`

- Signature: `def stochastic_strategy(df: pd.DataFrame, k_col: str, buy_level: float = 20.0, sell_level: float = 80.0, signal_name: str = 'signal_stochastic', mode: str = 'long_short_hold') -> pd.Series`
- Return type: `pd.Series`
- LOC: `20`
- Σύνοψη λογικής: Stochastic %K strategy wrapper (supports long/short/hold modes).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `k_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `buy_level` (positional-or-keyword, `float`, default `20.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `sell_level` (positional-or-keyword, `float`, default `80.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_stochastic'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:volatility_regime_strategy`

- Signature: `def volatility_regime_strategy(df: pd.DataFrame, vol_col: str, quantile: float = 0.5, signal_name: str = 'signal_volatility_regime', mode: str = 'long_short_hold') -> pd.Series`
- Return type: `pd.Series`
- LOC: `18`
- Σύνοψη λογικής: Volatility regime strategy wrapper (supports long/short/hold modes).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `vol_col` (positional-or-keyword, `str`, default `χωρίς default`): Όνομα στήλης volatility estimate για scaling ή targeting.
  - `quantile` (positional-or-keyword, `float`, default `0.5`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_volatility_regime'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:probabilistic_signal`

- Signature: `def probabilistic_signal(df: pd.DataFrame, prob_col: str, signal_name: str = 'signal_prob', upper: float = 0.55, lower: float = 0.45) -> pd.Series`
- Return type: `pd.Series`
- LOC: `17`
- Σύνοψη λογικής: Map probability forecasts to {-1,0,1} signal with dead-zone.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `prob_col` (positional-or-keyword, `str`, default `χωρίς default`): Όνομα στήλης probabilistic output από classifier.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_prob'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `upper` (positional-or-keyword, `float`, default `0.55`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `lower` (positional-or-keyword, `float`, default `0.45`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:conviction_sizing_signal`

- Signature: `def conviction_sizing_signal(df: pd.DataFrame, prob_col: str, signal_name: str = 'signal_prob_size', clip: float = 1.0) -> pd.Series`
- Return type: `pd.Series`
- LOC: `17`
- Σύνοψη λογικής: Linear map prob∈[0,1] to exposure∈[-clip, clip]: exposure = clip * (prob - 0.5) * 2
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `prob_col` (positional-or-keyword, `str`, default `χωρίς default`): Όνομα στήλης probabilistic output από classifier.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_prob_size'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `clip` (positional-or-keyword, `float`, default `1.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:regime_filtered_signal`

- Signature: `def regime_filtered_signal(df: pd.DataFrame, base_signal_col: str, regime_col: str, signal_name: str = 'signal_regime_filtered', active_value: float = 1.0) -> pd.Series`
- Return type: `pd.Series`
- LOC: `19`
- Σύνοψη λογικής: Keep base signal only when regime_col == active_value (else 0).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `base_signal_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `regime_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_regime_filtered'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `active_value` (positional-or-keyword, `float`, default `1.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.backtesting.strategies:vol_targeted_signal`

- Signature: `def vol_targeted_signal(df: pd.DataFrame, signal_col: str, vol_col: str, target_vol: float, max_leverage: float = 3.0, signal_name: str = 'signal_vol_tgt') -> pd.Series`
- Return type: `pd.Series`
- LOC: `23`
- Σύνοψη λογικής: Scale signal by volatility targeting using scale_signal_by_vol.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `signal_col` (positional-or-keyword, `str`, default `χωρίς default`): Όνομα στήλης signal exposure ή conviction sizing.
  - `vol_col` (positional-or-keyword, `str`, default `χωρίς default`): Όνομα στήλης volatility estimate για scaling ή targeting.
  - `target_vol` (positional-or-keyword, `float`, default `χωρίς default`): Στοχευμένη ετησιοποιημένη μεταβλητότητα που χρησιμοποιείται για leverage scaling.
  - `max_leverage` (positional-or-keyword, `float`, default `3.0`): Άνω όριο leverage/exposure που δεν επιτρέπεται να υπερβεί ο allocator/backtester.
  - `signal_name` (positional-or-keyword, `str`, default `'signal_vol_tgt'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) για vectorized operations πανω σε μια χρονοσειρα backtest.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

### 17.7 Package `src/evaluation`

- Ρόλος package: Evaluation
- Modules: `3`
- LOC: `652`
- Top-level callables: `23`
- Methods: `0`
- Classes: `1`

#### Module `src/evaluation/__init__.py`

- Python module: `src.evaluation`
- Ρόλος: Evaluation
- LOC: `47`
- Imports: `.metrics`, `.time_splits`
- Global constants / exported symbols:
  - `__all__` = `['TimeSplit', 'assert_no_forward_label_leakage', 'build_time_splits', 'purged_walk_forward_split_...`
- ASCII dependency sketch:
```text
[imports] .metrics, .time_splits
      |
      v
[module] src.evaluation
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/evaluation/metrics.py`

- Python module: `src.evaluation.metrics`
- Ρόλος: Evaluation
- LOC: `280`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['equity_curve_from_returns', 'max_drawdown', 'annualized_return', 'annualized_volatility', 'shar...`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `equity_curve_from_returns`
  - `max_drawdown`
  - `annualized_return`
  - `annualized_volatility`
  - `sharpe_ratio`
  - `downside_volatility`
  - `sortino_ratio`
  - `calmar_ratio`
  - `profit_factor`
  - `hit_rate`
  - `turnover_stats`
  - `cost_attribution`
  - `compute_backtest_metrics`
  - `merge_metric_overrides`

##### Callable `src.evaluation.metrics:equity_curve_from_returns`

- Signature: `def equity_curve_from_returns(returns: pd.Series) -> pd.Series`
- Return type: `pd.Series`
- LOC: `10`
- Σύνοψη λογικής: Handle equity curve from returns inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:calmar_ratio`, `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:max_drawdown`

- Signature: `def max_drawdown(equity: pd.Series) -> float`
- Return type: `float`
- LOC: `9`
- Σύνοψη λογικής: Handle max drawdown inside the evaluation layer.
- Παράμετροι:
  - `equity` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:calmar_ratio`, `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:annualized_return`

- Signature: `def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float`
- Return type: `float`
- LOC: `12`
- Σύνοψη λογικής: Handle annualized return inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `periods_per_year` (positional-or-keyword, `int`, default `252`): Annualization factor για returns και risk metrics.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:calmar_ratio`, `src.evaluation.metrics:compute_backtest_metrics`, `src.evaluation.metrics:sharpe_ratio`, `src.evaluation.metrics:sortino_ratio`

##### Callable `src.evaluation.metrics:annualized_volatility`

- Signature: `def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float`
- Return type: `float`
- LOC: `9`
- Σύνοψη λογικής: Handle annualized volatility inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `periods_per_year` (positional-or-keyword, `int`, default `252`): Annualization factor για returns και risk metrics.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:compute_backtest_metrics`, `src.evaluation.metrics:sharpe_ratio`

##### Callable `src.evaluation.metrics:sharpe_ratio`

- Signature: `def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252) -> float`
- Return type: `float`
- LOC: `8`
- Σύνοψη λογικής: Handle sharpe ratio inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `periods_per_year` (positional-or-keyword, `int`, default `252`): Annualization factor για returns και risk metrics.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:downside_volatility`

- Signature: `def downside_volatility(returns: pd.Series, periods_per_year: int = 252, minimum_acceptable_return: float = 0.0) -> float`
- Return type: `float`
- LOC: `16`
- Σύνοψη λογικής: Handle downside volatility inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `periods_per_year` (positional-or-keyword, `int`, default `252`): Annualization factor για returns και risk metrics.
  - `minimum_acceptable_return` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:sortino_ratio`

##### Callable `src.evaluation.metrics:sortino_ratio`

- Signature: `def sortino_ratio(returns: pd.Series, periods_per_year: int = 252, minimum_acceptable_return: float = 0.0) -> float`
- Return type: `float`
- LOC: `16`
- Σύνοψη λογικής: Handle sortino ratio inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `periods_per_year` (positional-or-keyword, `int`, default `252`): Annualization factor για returns και risk metrics.
  - `minimum_acceptable_return` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:calmar_ratio`

- Signature: `def calmar_ratio(returns: pd.Series, periods_per_year: int = 252) -> float`
- Return type: `float`
- LOC: `8`
- Σύνοψη λογικής: Handle calmar ratio inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `periods_per_year` (positional-or-keyword, `int`, default `252`): Annualization factor για returns και risk metrics.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:profit_factor`

- Signature: `def profit_factor(returns: pd.Series) -> float`
- Return type: `float`
- LOC: `13`
- Σύνοψη λογικής: Handle profit factor inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:hit_rate`

- Signature: `def hit_rate(returns: pd.Series) -> float`
- Return type: `float`
- LOC: `12`
- Σύνοψη λογικής: Handle hit rate inside the evaluation layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:turnover_stats`

- Signature: `def turnover_stats(turnover: pd.Series | None) -> dict[str, float]`
- Return type: `dict[str, float]`
- LOC: `14`
- Σύνοψη λογικής: Handle turnover stats inside the evaluation layer.
- Παράμετροι:
  - `turnover` (positional-or-keyword, `pd.Series | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:cost_attribution`

- Signature: `def cost_attribution(net_returns: pd.Series, gross_returns: pd.Series | None, costs: pd.Series | None) -> dict[str, float]`
- Return type: `dict[str, float]`
- LOC: `31`
- Σύνοψη λογικής: Handle cost attribution inside the evaluation layer.
- Παράμετροι:
  - `net_returns` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `gross_returns` (keyword-only, `pd.Series | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `costs` (keyword-only, `pd.Series | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.evaluation.metrics:compute_backtest_metrics`

##### Callable `src.evaluation.metrics:compute_backtest_metrics`

- Signature: `def compute_backtest_metrics(net_returns: pd.Series, periods_per_year: int = 252, turnover: pd.Series | None = None, costs: pd.Series | None = None, gross_returns: pd.Series | None = None) -> dict[str, float]`
- Return type: `dict[str, float]`
- LOC: `57`
- Σύνοψη λογικής: Compute backtest metrics for the evaluation layer.
- Παράμετροι:
  - `net_returns` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `periods_per_year` (keyword-only, `int`, default `252`): Annualization factor για returns και risk metrics.
  - `turnover` (keyword-only, `pd.Series | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `costs` (keyword-only, `pd.Series | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `gross_returns` (keyword-only, `pd.Series | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: `src.backtesting.engine:run_backtest`, `src.experiments.runner:_compute_subset_metrics`, `src.portfolio.construction:compute_portfolio_performance`, `tests.test_contracts_metrics_pit:test_metrics_suite_includes_risk_and_cost_attribution`

##### Callable `src.evaluation.metrics:merge_metric_overrides`

- Signature: `def merge_metric_overrides(base_metrics: Mapping[str, float], overrides: Mapping[str, float] | None) -> dict[str, float]`
- Return type: `dict[str, float]`
- LOC: `12`
- Σύνοψη λογικής: Merge metric overrides into one consolidated structure for the evaluation layer.
- Παράμετροι:
  - `base_metrics` (positional-or-keyword, `Mapping[str, float]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `overrides` (positional-or-keyword, `Mapping[str, float] | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα observations της σειρας returns/turnover/costs.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `src/evaluation/time_splits.py`

- Python module: `src.evaluation.time_splits`
- Ρόλος: Evaluation
- LOC: `325`
- Imports: `__future__`, `dataclasses`, `numpy`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['TimeSplit', 'time_split_indices', 'walk_forward_split_indices', 'purged_walk_forward_split_indi...`
- ASCII dependency sketch:
```text
[imports] __future__, dataclasses, numpy, typing
      |
      v
[module] src.evaluation.time_splits
      |
      +-- functions: 9
      |
      +-- classes: 1
      |
[inbound] src.evaluation.time_splits:assert_no_forward_label_leakage, src.evaluation.time_s...
```

- Classes στο module:
  - `TimeSplit`

##### Class `src.evaluation.time_splits:TimeSplit`

- Βάσεις: `-`
- LOC: `12`
- Σύνοψη ρόλου: Represent one chronological train/test fold with both scalar boundaries and the exact numpy indices used by the time-aware evaluation routines.
- Fields:
  - `fold` (`int`, default `-`)
  - `train_start` (`int`, default `-`)
  - `train_end` (`int`, default `-`)
  - `test_start` (`int`, default `-`)
  - `test_end` (`int`, default `-`)
  - `train_idx` (`np.ndarray`, default `-`)
  - `test_idx` (`np.ndarray`, default `-`)
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

- Top-level callables:
  - `_require_positive_int`
  - `_require_non_negative_int`
  - `_exclude_blocked_ranges`
  - `time_split_indices`
  - `walk_forward_split_indices`
  - `purged_walk_forward_split_indices`
  - `trim_train_indices_for_horizon`
  - `assert_no_forward_label_leakage`
  - `build_time_splits`

##### Callable `src.evaluation.time_splits:_require_positive_int`

- Signature: `def _require_positive_int(name: str, value: int) -> None`
- Return type: `None`
- LOC: `7`
- Σύνοψη λογικής: Handle require positive int inside the evaluation layer.
- Παράμετροι:
  - `name` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `value` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.evaluation.time_splits:assert_no_forward_label_leakage`, `src.evaluation.time_splits:purged_walk_forward_split_indices`, `src.evaluation.time_splits:trim_train_indices_for_horizon`

##### Callable `src.evaluation.time_splits:_require_non_negative_int`

- Signature: `def _require_non_negative_int(name: str, value: int) -> None`
- Return type: `None`
- LOC: `7`
- Σύνοψη λογικής: Handle require non negative int inside the evaluation layer.
- Παράμετροι:
  - `name` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `value` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.evaluation.time_splits:purged_walk_forward_split_indices`

##### Callable `src.evaluation.time_splits:_exclude_blocked_ranges`

- Signature: `def _exclude_blocked_ranges(train_idx: np.ndarray, blocked_ranges: list[tuple[int, int]]) -> np.ndarray`
- Return type: `np.ndarray`
- LOC: `19`
- Σύνοψη λογικής: Remove embargoed intervals from a candidate train index so later folds cannot silently reuse rows that were intentionally excluded after earlier test windows.
- Παράμετροι:
  - `train_idx` (positional-or-keyword, `np.ndarray`, default `χωρίς default`): Array/σειρα integer indices για chronological slicing.
  - `blocked_ranges` (keyword-only, `list[tuple[int, int]]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.evaluation.time_splits:purged_walk_forward_split_indices`

##### Callable `src.evaluation.time_splits:time_split_indices`

- Signature: `def time_split_indices(n_samples: int, train_frac: float = 0.7) -> list[TimeSplit]`
- Return type: `list[TimeSplit]`
- LOC: `27`
- Σύνοψη λογικής: Handle time split indices inside the evaluation layer.
- Παράμετροι:
  - `n_samples` (positional-or-keyword, `int`, default `χωρίς default`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
  - `train_frac` (positional-or-keyword, `float`, default `0.7`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.evaluation.time_splits:build_time_splits`

##### Callable `src.evaluation.time_splits:walk_forward_split_indices`

- Signature: `def walk_forward_split_indices(n_samples: int, train_size: int, test_size: int, step_size: int | None = None, expanding: bool = True, max_folds: int | None = None) -> list[TimeSplit]`
- Return type: `list[TimeSplit]`
- LOC: `23`
- Σύνοψη λογικής: Handle walk forward split indices inside the evaluation layer.
- Παράμετροι:
  - `n_samples` (positional-or-keyword, `int`, default `χωρίς default`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
  - `train_size` (positional-or-keyword, `int`, default `χωρίς default`): Μήκος train window σε αριθμό observations.
  - `test_size` (positional-or-keyword, `int`, default `χωρίς default`): Μήκος test window σε αριθμό observations.
  - `step_size` (positional-or-keyword, `int | None`, default `None`): Μετατόπιση του walk-forward παραθύρου μεταξύ διαδοχικών folds.
  - `expanding` (positional-or-keyword, `bool`, default `True`): Flag που δηλώνει αν το train window είναι expanding αντί rolling.
  - `max_folds` (positional-or-keyword, `int | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.evaluation.time_splits:build_time_splits`, `tests.test_time_splits:test_walk_forward_splits_are_time_ordered_and_non_overlapping`

##### Callable `src.evaluation.time_splits:purged_walk_forward_split_indices`

- Signature: `def purged_walk_forward_split_indices(n_samples: int, train_size: int, test_size: int, step_size: int | None = None, purge_bars: int = 0, embargo_bars: int = 0, expanding: bool = True, max_folds: int | None = None) -> list[TimeSplit]`
- Return type: `list[TimeSplit]`
- LOC: `90`
- Σύνοψη λογικής: Handle purged walk forward split indices inside the evaluation layer.
- Παράμετροι:
  - `n_samples` (positional-or-keyword, `int`, default `χωρίς default`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
  - `train_size` (positional-or-keyword, `int`, default `χωρίς default`): Μήκος train window σε αριθμό observations.
  - `test_size` (positional-or-keyword, `int`, default `χωρίς default`): Μήκος test window σε αριθμό observations.
  - `step_size` (positional-or-keyword, `int | None`, default `None`): Μετατόπιση του walk-forward παραθύρου μεταξύ διαδοχικών folds.
  - `purge_bars` (positional-or-keyword, `int`, default `0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `embargo_bars` (positional-or-keyword, `int`, default `0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `expanding` (positional-or-keyword, `bool`, default `True`): Flag που δηλώνει αν το train window είναι expanding αντί rolling.
  - `max_folds` (positional-or-keyword, `int | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.evaluation.time_splits:build_time_splits`, `src.evaluation.time_splits:walk_forward_split_indices`, `tests.test_time_splits:test_purged_walk_forward_excludes_prior_embargo_rows_from_future_training`, `tests.test_time_splits:test_purged_walk_forward_respects_purge_and_embargo`

##### Callable `src.evaluation.time_splits:trim_train_indices_for_horizon`

- Signature: `def trim_train_indices_for_horizon(train_idx: np.ndarray, test_start: int, target_horizon: int) -> np.ndarray`
- Return type: `np.ndarray`
- LOC: `23`
- Σύνοψη λογικής: Trim training indices so forward-looking labels cannot overlap the test window.
- Παράμετροι:
  - `train_idx` (positional-or-keyword, `np.ndarray`, default `χωρίς default`): Array/σειρα integer indices για chronological slicing.
  - `test_start` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `target_horizon` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.experiments.models:_train_forward_classifier`

##### Callable `src.evaluation.time_splits:assert_no_forward_label_leakage`

- Signature: `def assert_no_forward_label_leakage(train_idx: np.ndarray, test_start: int, target_horizon: int) -> None`
- Return type: `None`
- LOC: `22`
- Σύνοψη λογικής: Ensure train indices are safe for forward labels of length ``target_horizon``.
- Παράμετροι:
  - `train_idx` (positional-or-keyword, `np.ndarray`, default `χωρίς default`): Array/σειρα integer indices για chronological slicing.
  - `test_start` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `target_horizon` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.experiments.models:_train_forward_classifier`

##### Callable `src.evaluation.time_splits:build_time_splits`

- Signature: `def build_time_splits(method: Literal['time', 'walk_forward', 'purged'], n_samples: int, split_cfg: dict, target_horizon: int = 1) -> list[TimeSplit]`
- Return type: `list[TimeSplit]`
- LOC: `57`
- Σύνοψη λογικής: Build time splits as an explicit intermediate object used by the evaluation pipeline.
- Παράμετροι:
  - `method` (keyword-only, `Literal['time', 'walk_forward', 'purged']`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `n_samples` (keyword-only, `int`, default `χωρίς default`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
  - `split_cfg` (keyword-only, `dict`, default `χωρίς default`): Configuration block για time split policy.
  - `target_horizon` (keyword-only, `int`, default `1`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(N + S), οπου N samples και S αριθμος splits/blocked ranges.
- Direct callers: `src.experiments.models:_train_forward_classifier`, `tests.test_time_splits:test_build_time_splits_uses_target_horizon_for_default_purge`

### 17.8 Package `src/execution`

- Ρόλος package: Paper execution
- Modules: `2`
- LOC: `81`
- Top-level callables: `1`
- Methods: `0`
- Classes: `0`

#### Module `src/execution/__init__.py`

- Python module: `src.execution`
- Ρόλος: Paper execution
- LOC: `3`
- Imports: `.paper`
- Global constants / exported symbols:
  - `__all__` = `['build_rebalance_orders']`
- ASCII dependency sketch:
```text
[imports] .paper
      |
      v
[module] src.execution
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/execution/paper.py`

- Python module: `src.execution.paper`
- Ρόλος: Paper execution
- LOC: `78`
- Imports: `__future__`, `pandas`
- Global constants / exported symbols:
  - `_ZERO_TRADE_TOL` = `1e-12`
  - `__all__` = `['build_rebalance_orders']`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `build_rebalance_orders`

##### Callable `src.execution.paper:build_rebalance_orders`

- Signature: `def build_rebalance_orders(target_weights: pd.Series, prices: pd.Series, capital: float, current_weights: pd.Series | None = None, min_trade_notional: float = 0.0) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `67`
- Σύνοψη λογικής: Build rebalance orders as an explicit intermediate object used by the paper execution pipeline.
- Παράμετροι:
  - `target_weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `prices` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `capital` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `current_weights` (keyword-only, `pd.Series | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `min_trade_notional` (keyword-only, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:_build_execution_output`, `tests.test_runner_extensions:test_build_rebalance_orders_emits_liquidation_for_current_only_asset`, `tests.test_runner_extensions:test_build_rebalance_orders_ignores_flat_assets_with_missing_prices`, `tests.test_runner_extensions:test_build_rebalance_orders_reports_share_deltas`

### 17.9 Package `src/experiments`

- Ρόλος package: Experiment orchestration
- Modules: `5`
- LOC: `2039`
- Top-level callables: `47`
- Methods: `0`
- Classes: `3`

#### Module `src/experiments/__init__.py`

- Python module: `src.experiments`
- Ρόλος: Experiment orchestration
- LOC: `16`
- Imports: `.contracts`, `.runner`
- Global constants / exported symbols:
  - `__all__` = `['ExperimentResult', 'run_experiment', 'DataContract', 'TargetContract', 'validate_data_contract'...`
- ASCII dependency sketch:
```text
[imports] .contracts, .runner
      |
      v
[module] src.experiments
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/experiments/contracts.py`

- Python module: `src.experiments.contracts`
- Ρόλος: Experiment orchestration
- LOC: `130`
- Imports: `__future__`, `dataclasses`, `pandas`, `pandas.api.types`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['DataContract', 'TargetContract', 'validate_data_contract', 'validate_feature_target_contract']`
- ASCII dependency sketch:
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

- Classes στο module:
  - `DataContract`
  - `TargetContract`

##### Class `src.experiments.contracts:DataContract`

- Βάσεις: `-`
- LOC: `9`
- Σύνοψη ρόλου: Describe the minimum structural guarantees expected from market data before feature generation or model training proceeds.
- Fields:
  - `required_columns` (`tuple[str, ...]`, default `('open', 'high', 'low', 'close', 'volume')`)
  - `require_datetime_index` (`bool`, default `True`)
  - `require_unique_index` (`bool`, default `True`)
  - `require_monotonic_index` (`bool`, default `True`)
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

##### Class `src.experiments.contracts:TargetContract`

- Βάσεις: `-`
- LOC: `7`
- Σύνοψη ρόλου: Describe the label column and prediction horizon that the feature-to-target validation logic must enforce.
- Fields:
  - `target_col` (`str`, default `-`)
  - `horizon` (`int`, default `1`)
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

- Top-level callables:
  - `validate_data_contract`
  - `validate_feature_target_contract`

##### Callable `src.experiments.contracts:validate_data_contract`

- Signature: `def validate_data_contract(df: pd.DataFrame, contract: DataContract | None = None) -> dict[str, int]`
- Return type: `dict[str, int]`
- LOC: `27`
- Σύνοψη λογικής: Validate data contract before downstream logic depends on it.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `contract` (positional-or-keyword, `DataContract | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:_load_asset_frames`

##### Callable `src.experiments.contracts:validate_feature_target_contract`

- Signature: `def validate_feature_target_contract(df: pd.DataFrame, feature_cols: Sequence[str], target: TargetContract, forbidden_feature_prefixes: Iterable[str] = ('target_', 'label', 'pred_')) -> dict[str, int]`
- Return type: `dict[str, int]`
- LOC: `61`
- Σύνοψη λογικής: Validate feature target contract before downstream logic depends on it.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `feature_cols` (keyword-only, `Sequence[str]`, default `χωρίς default`): Ρητή λίστα feature columns για supervised learning.
  - `target` (keyword-only, `TargetContract`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `forbidden_feature_prefixes` (keyword-only, `Iterable[str]`, default `('target_', 'label', 'pred_')`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`, `TypeError`, `ValueError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.models:_train_forward_classifier`, `tests.test_contracts_metrics_pit:test_feature_contract_rejects_target_like_feature_columns`

#### Module `src/experiments/models.py`

- Python module: `src.experiments.models`
- Ρόλος: Experiment orchestration
- LOC: `499`
- Imports: `__future__`, `lightgbm`, `numpy`, `pandas`, `sklearn.linear_model`, `sklearn.metrics`, `src.evaluation.time_splits`, `src.experiments.contracts`, `src.models.lightgbm_baseline`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['infer_feature_columns', 'train_lightgbm_classifier', 'train_logistic_regression_classifier']`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `_resolve_runtime_for_model`
  - `infer_feature_columns`
  - `_build_forward_return_target`
  - `_assign_quantile_labels`
  - `_binary_classification_metrics`
  - `_train_forward_classifier`
  - `train_lightgbm_classifier`
  - `train_logistic_regression_classifier`

##### Callable `src.experiments.models:_resolve_runtime_for_model`

- Signature: `def _resolve_runtime_for_model(model_cfg: dict[str, Any], model_params: dict[str, Any], estimator_family: str) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `50`
- Σύνοψη λογικής: Handle runtime for model inside the experiment orchestration layer.
- Παράμετροι:
  - `model_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για model kind, params, target και split policy.
  - `model_params` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Χαμηλού επιπέδου estimator hyperparameters.
  - `estimator_family` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Κυριαρχειται απο cross-validation και estimator fit cost ως προς rows, features και αριθμο folds.
- Direct callers: `src.experiments.models:_train_forward_classifier`

##### Callable `src.experiments.models:infer_feature_columns`

- Signature: `def infer_feature_columns(df: pd.DataFrame, explicit_cols: Sequence[str] | None = None, exclude: Iterable[str] | None = None) -> list[str]`
- Return type: `list[str]`
- LOC: `32`
- Σύνοψη λογικής: Infer feature columns from the available inputs when the caller has not specified them explicitly.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `explicit_cols` (positional-or-keyword, `Sequence[str] | None`, default `None`): Λιστα στηλων pandas που συμμετεχουν σε transformation ή model fitting.
  - `exclude` (positional-or-keyword, `Iterable[str] | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Κυριαρχειται απο cross-validation και estimator fit cost ως προς rows, features και αριθμο folds.
- Direct callers: `src.experiments.models:_train_forward_classifier`

##### Callable `src.experiments.models:_build_forward_return_target`

- Signature: `def _build_forward_return_target(df: pd.DataFrame, target_cfg: dict[str, Any] | None) -> tuple[pd.DataFrame, str, str, dict[str, Any]]`
- Return type: `tuple[pd.DataFrame, str, str, dict[str, Any]]`
- LOC: `48`
- Σύνοψη λογικής: Handle forward return target inside the experiment orchestration layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `target_cfg` (positional-or-keyword, `dict[str, Any] | None`, default `χωρίς default`): Configuration block για target engineering, horizon και thresholds.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`, `ValueError`
- Big-O: Κυριαρχειται απο cross-validation και estimator fit cost ως προς rows, features και αριθμο folds.
- Direct callers: `src.experiments.models:_train_forward_classifier`

##### Callable `src.experiments.models:_assign_quantile_labels`

- Signature: `def _assign_quantile_labels(forward_returns: pd.Series, low_value: float, high_value: float) -> pd.Series`
- Return type: `pd.Series`
- LOC: `15`
- Σύνοψη λογικής: Handle assign quantile labels inside the experiment orchestration layer.
- Παράμετροι:
  - `forward_returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `low_value` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `high_value` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Κυριαρχειται απο cross-validation και estimator fit cost ως προς rows, features και αριθμο folds.
- Direct callers: `src.experiments.models:_train_forward_classifier`

##### Callable `src.experiments.models:_binary_classification_metrics`

- Signature: `def _binary_classification_metrics(y_true: pd.Series, pred_prob: pd.Series) -> dict[str, float | int | None]`
- Return type: `dict[str, float | int | None]`
- LOC: `35`
- Σύνοψη λογικής: Handle binary classification metrics inside the experiment orchestration layer.
- Παράμετροι:
  - `y_true` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `pred_prob` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Κυριαρχειται απο cross-validation και estimator fit cost ως προς rows, features και αριθμο folds.
- Direct callers: `src.experiments.models:_train_forward_classifier`

##### Callable `src.experiments.models:_train_forward_classifier`

- Signature: `def _train_forward_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], model_kind: str, estimator_family: str, estimator_factory: EstimatorFactory, returns_col: str | None = None) -> tuple[pd.DataFrame, object, dict[str, Any]]`
- Return type: `tuple[pd.DataFrame, object, dict[str, Any]]`
- LOC: `234`
- Σύνοψη λογικής: Handle forward classifier inside the experiment orchestration layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `model_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για model kind, params, target και split policy.
  - `model_kind` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `estimator_family` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `estimator_factory` (keyword-only, `EstimatorFactory`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `returns_col` (keyword-only, `str | None`, default `None`): Όνομα στήλης αποδόσεων που τροφοδοτεί backtest, metrics ή model layer.
- Side effects: Μεταβαλλει internal state estimator/model object με training.
- Exceptions: `ValueError`
- Big-O: O(S * fit_cost(N_s, P) + S * N_test * P), όπου S ο αριθμός folds, N_s τα train rows ανά fold και P ο αριθμός features.
- Direct callers: `src.experiments.models:train_lightgbm_classifier`, `src.experiments.models:train_logistic_regression_classifier`

##### Callable `src.experiments.models:train_lightgbm_classifier`

- Signature: `def train_lightgbm_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], returns_col: str | None = None) -> tuple[pd.DataFrame, LGBMClassifier, dict[str, Any]]`
- Return type: `tuple[pd.DataFrame, LGBMClassifier, dict[str, Any]]`
- LOC: `18`
- Σύνοψη λογικής: Train lightgbm classifier using the data and split conventions defined by the experiment orchestration workflow.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `model_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για model kind, params, target και split policy.
  - `returns_col` (positional-or-keyword, `str | None`, default `None`): Όνομα στήλης αποδόσεων που τροφοδοτεί backtest, metrics ή model layer.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Κληρονομεί την πολυπλοκότητα του `_train_forward_classifier`, με fit cost tree-boosting που εξαρτάται από αριθμό trees, depth και rows.
- Direct callers: `tests.test_contracts_metrics_pit:test_forward_horizon_guard_trims_train_rows_in_time_split`, `tests.test_no_lookahead:test_binary_forward_target_keeps_tail_labels_nan`, `tests.test_no_lookahead:test_purged_splits_respect_anti_leakage_gap`, `tests.test_no_lookahead:test_quantile_target_uses_train_only_distribution_per_fold`, `tests.test_no_lookahead:test_walk_forward_predictions_are_oos_only`

##### Callable `src.experiments.models:train_logistic_regression_classifier`

- Signature: `def train_logistic_regression_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], returns_col: str | None = None) -> tuple[pd.DataFrame, LogisticRegression, dict[str, Any]]`
- Return type: `tuple[pd.DataFrame, LogisticRegression, dict[str, Any]]`
- LOC: `25`
- Σύνοψη λογικής: Train logistic regression classifier using the data and split conventions defined by the experiment orchestration workflow.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `model_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για model kind, params, target και split policy.
  - `returns_col` (positional-or-keyword, `str | None`, default `None`): Όνομα στήλης αποδόσεων που τροφοδοτεί backtest, metrics ή model layer.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Κληρονομεί την πολυπλοκότητα του `_train_forward_classifier`, με fit cost περίπου O(S * iterations * N_s * P).
- Direct callers: `tests.test_runner_extensions:test_logistic_regression_model_registry_outputs_oos_metrics`

#### Module `src/experiments/registry.py`

- Python module: `src.experiments.registry`
- Ρόλος: Experiment orchestration
- LOC: `88`
- Imports: `__future__`, `pandas`, `src.backtesting.strategies`, `src.experiments.models`, `src.features`, `src.features.technical.indicators`, `src.features.technical.momentum`, `src.features.technical.oscillators`, `src.features.technical.trend`, `typing`
- Global constants / exported symbols:
  - `FEATURE_REGISTRY` = `{'returns': add_close_returns, 'volatility': add_volatility_features, 'trend': add_trend_features...`
  - `SIGNAL_REGISTRY` = `{'trend_state': trend_state_signal, 'probability_threshold': probabilistic_signal, 'probability_c...`
  - `MODEL_REGISTRY` = `{'lightgbm_clf': train_lightgbm_classifier, 'logistic_regression_clf': train_logistic_regression_...`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `get_feature_fn`
  - `get_signal_fn`
  - `get_model_fn`

##### Callable `src.experiments.registry:get_feature_fn`

- Signature: `def get_feature_fn(name: str) -> FeatureFn`
- Return type: `FeatureFn`
- LOC: `9`
- Σύνοψη λογικής: Handle get feature fn inside the experiment orchestration layer.
- Παράμετροι:
  - `name` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:_apply_feature_steps`

##### Callable `src.experiments.registry:get_signal_fn`

- Signature: `def get_signal_fn(name: str) -> SignalFn`
- Return type: `SignalFn`
- LOC: `9`
- Σύνοψη λογικής: Handle get signal fn inside the experiment orchestration layer.
- Παράμετροι:
  - `name` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:_apply_signal_step`

##### Callable `src.experiments.registry:get_model_fn`

- Signature: `def get_model_fn(name: str) -> ModelFn`
- Return type: `ModelFn`
- LOC: `9`
- Σύνοψη λογικής: Handle get model fn inside the experiment orchestration layer.
- Παράμετροι:
  - `name` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:_apply_model_step`

#### Module `src/experiments/runner.py`

- Python module: `src.experiments.runner`
- Ρόλος: Experiment orchestration
- LOC: `1306`
- Imports: `__future__`, `dataclasses`, `datetime`, `hashlib`, `json`, `numpy`, `pandas`, `pathlib`, `re`, `src.backtesting.engine`, `src.evaluation.metrics`, `src.execution.paper`, `src.experiments.contracts`, `src.experiments.registry`, `src.monitoring.drift`, `src.portfolio`, `src.src_data.loaders`, `src.src_data.pit`, `src.src_data.storage`, `src.src_data.validation`, `src.utils.config`, `src.utils.paths`, `src.utils.repro`, `src.utils.run_metadata`, `typing`, `yaml`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] __future__, dataclasses, datetime, hashlib
      |
      v
[module] src.experiments.runner
      |
      +-- functions: 34
      |
      +-- classes: 1
      |
[inbound] src.experiments.runner:_apply_model_to_assets, src.experiments.runner:_apply_sign...
```

- Classes στο module:
  - `ExperimentResult`

##### Class `src.experiments.runner:ExperimentResult`

- Βάσεις: `-`
- LOC: `16`
- Σύνοψη ρόλου: Collect the full output of an experiment run, including the resolved configuration, transformed data, fitted model objects, evaluation outputs, execution artifacts, and any port...
- Fields:
  - `config` (`dict[str, Any]`, default `-`)
  - `data` (`pd.DataFrame | dict[str, pd.DataFrame]`, default `-`)
  - `backtest` (`BacktestResult | PortfolioPerformance`, default `-`)
  - `model` (`object | dict[str, object] | None`, default `-`)
  - `model_meta` (`dict[str, Any]`, default `-`)
  - `artifacts` (`dict[str, str]`, default `-`)
  - `evaluation` (`dict[str, Any]`, default `-`)
  - `monitoring` (`dict[str, Any]`, default `-`)
  - `execution` (`dict[str, Any]`, default `-`)
  - `portfolio_weights` (`pd.DataFrame | None`, default `None`)
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

- Top-level callables:
  - `_slugify`
  - `_stable_json_dumps`
  - `_pit_config_hash`
  - `_resolve_symbols`
  - `_default_dataset_id`
  - `_apply_feature_steps`
  - `_apply_model_step`
  - `_apply_signal_step`
  - `_apply_steps_to_assets`
  - `_aggregate_model_meta`
  - `_apply_model_to_assets`
  - `_apply_signals_to_assets`
  - `_resolve_vol_col`
  - `_validate_returns_series`
  - `_validate_returns_frame`
  - `_build_storage_context`
  - `_snapshot_context_matches`
  - `_load_asset_frames`
  - `_save_processed_snapshot_if_enabled`
  - `_align_asset_column`
  - `_build_portfolio_constraints`
  - `_run_single_asset_backtest`
  - `_run_portfolio_backtest`
  - `_compute_subset_metrics`
  - `_build_fold_backtest_summaries`
  - `_build_single_asset_evaluation`
  - `_build_portfolio_evaluation`
  - `_compute_monitoring_for_asset`
  - `_compute_monitoring_report`
  - `_build_execution_output`
  - `_data_stats_payload`
  - `_resolved_feature_columns`
  - `_save_artifacts`
  - `run_experiment`

##### Callable `src.experiments.runner:_slugify`

- Signature: `def _slugify(value: str) -> str`
- Return type: `str`
- LOC: `7`
- Σύνοψη λογικής: Handle slugify inside the experiment orchestration layer.
- Παράμετροι:
  - `value` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_default_dataset_id`

##### Callable `src.experiments.runner:_stable_json_dumps`

- Signature: `def _stable_json_dumps(value: Any) -> str`
- Return type: `str`
- LOC: `6`
- Σύνοψη λογικής: Serialize a configuration fragment deterministically so cache identities and metadata comparisons are stable across runs.
- Παράμετροι:
  - `value` (positional-or-keyword, `Any`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_pit_config_hash`, `src.experiments.runner:_snapshot_context_matches`

##### Callable `src.experiments.runner:_pit_config_hash`

- Signature: `def _pit_config_hash(pit_cfg: dict[str, Any] | None) -> str`
- Return type: `str`
- LOC: `7`
- Σύνοψη λογικής: Compute a stable hash for the PIT configuration so cached datasets cannot be reused under a different PIT policy.
- Παράμετροι:
  - `pit_cfg` (positional-or-keyword, `dict[str, Any] | None`, default `χωρίς default`): Configuration block για point-in-time hardening.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_build_storage_context`, `src.experiments.runner:_default_dataset_id`

##### Callable `src.experiments.runner:_resolve_symbols`

- Signature: `def _resolve_symbols(data_cfg: dict[str, Any]) -> list[str]`
- Return type: `list[str]`
- LOC: `8`
- Σύνοψη λογικής: Handle symbols inside the experiment orchestration layer.
- Παράμετροι:
  - `data_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για source, σύμβολα, PIT και storage behavior.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_default_dataset_id`, `src.experiments.runner:_load_asset_frames`, `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_default_dataset_id`

- Signature: `def _default_dataset_id(data_cfg: dict[str, Any]) -> str`
- Return type: `str`
- LOC: `21`
- Σύνοψη λογικής: Handle default dataset id inside the experiment orchestration layer.
- Παράμετροι:
  - `data_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για source, σύμβολα, PIT και storage behavior.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_load_asset_frames`, `src.experiments.runner:_save_processed_snapshot_if_enabled`

##### Callable `src.experiments.runner:_apply_feature_steps`

- Signature: `def _apply_feature_steps(df: pd.DataFrame, steps: list[dict[str, Any]]) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `15`
- Σύνοψη λογικής: Handle feature steps inside the experiment orchestration layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `steps` (positional-or-keyword, `list[dict[str, Any]]`, default `χωρίς default`): Δηλωτική λίστα steps pipeline με ονόματα και παραμέτρους.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_apply_steps_to_assets`

##### Callable `src.experiments.runner:_apply_model_step`

- Signature: `def _apply_model_step(df: pd.DataFrame, model_cfg: dict[str, Any], returns_col: str | None) -> tuple[pd.DataFrame, object | None, dict[str, Any]]`
- Return type: `tuple[pd.DataFrame, object | None, dict[str, Any]]`
- LOC: `14`
- Σύνοψη λογικής: Handle model step inside the experiment orchestration layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `model_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για model kind, params, target και split policy.
  - `returns_col` (positional-or-keyword, `str | None`, default `χωρίς default`): Όνομα στήλης αποδόσεων που τροφοδοτεί backtest, metrics ή model layer.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_apply_model_to_assets`

##### Callable `src.experiments.runner:_apply_signal_step`

- Signature: `def _apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `19`
- Σύνοψη λογικής: Handle signal step inside the experiment orchestration layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `signals_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για signal function και παραμέτρους.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_apply_signals_to_assets`

##### Callable `src.experiments.runner:_apply_steps_to_assets`

- Signature: `def _apply_steps_to_assets(asset_frames: dict[str, pd.DataFrame], feature_steps: list[dict[str, Any]]) -> dict[str, pd.DataFrame]`
- Return type: `dict[str, pd.DataFrame]`
- LOC: `14`
- Σύνοψη λογικής: Handle steps to assets inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `feature_steps` (keyword-only, `list[dict[str, Any]]`, default `χωρίς default`): Δηλωτική λίστα feature transformations που εφαρμόζονται σειριακά.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_aggregate_model_meta`

- Signature: `def _aggregate_model_meta(per_asset_meta: dict[str, dict[str, Any]]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `47`
- Σύνοψη λογικής: Handle aggregate model meta inside the experiment orchestration layer.
- Παράμετροι:
  - `per_asset_meta` (positional-or-keyword, `dict[str, dict[str, Any]]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_apply_model_to_assets`

##### Callable `src.experiments.runner:_apply_model_to_assets`

- Signature: `def _apply_model_to_assets(asset_frames: dict[str, pd.DataFrame], model_cfg: dict[str, Any], returns_col: str | None) -> tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]`
- Return type: `tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]`
- LOC: `28`
- Σύνοψη λογικής: Handle model to assets inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `model_cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Configuration block για model kind, params, target και split policy.
  - `returns_col` (keyword-only, `str | None`, default `χωρίς default`): Όνομα στήλης αποδόσεων που τροφοδοτεί backtest, metrics ή model layer.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_apply_signals_to_assets`

- Signature: `def _apply_signals_to_assets(asset_frames: dict[str, pd.DataFrame], signals_cfg: dict[str, Any]) -> dict[str, pd.DataFrame]`
- Return type: `dict[str, pd.DataFrame]`
- LOC: `14`
- Σύνοψη λογικής: Handle signals to assets inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signals_cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Configuration block για signal function και παραμέτρους.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_resolve_vol_col`

- Signature: `def _resolve_vol_col(df: pd.DataFrame, backtest_cfg: dict[str, Any], risk_cfg: dict[str, Any]) -> str | None`
- Return type: `str | None`
- LOC: `13`
- Σύνοψη λογικής: Handle volatility col inside the experiment orchestration layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `backtest_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για return semantics, signal column και metrics horizon.
  - `risk_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για risk sizing, leverage και drawdown guard.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_run_single_asset_backtest`

##### Callable `src.experiments.runner:_validate_returns_series`

- Signature: `def _validate_returns_series(returns: pd.Series, returns_type: str) -> None`
- Return type: `None`
- LOC: `8`
- Σύνοψη λογικής: Handle returns series inside the experiment orchestration layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `returns_type` (positional-or-keyword, `str`, default `χωρίς default`): Δηλώνει αν οι αποδόσεις ερμηνεύονται ως `simple` ή `log` στο downstream logic.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_run_single_asset_backtest`

##### Callable `src.experiments.runner:_validate_returns_frame`

- Signature: `def _validate_returns_frame(returns: pd.DataFrame, returns_type: str) -> None`
- Return type: `None`
- LOC: `8`
- Σύνοψη λογικής: Handle returns frame inside the experiment orchestration layer.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `returns_type` (positional-or-keyword, `str`, default `χωρίς default`): Δηλώνει αν οι αποδόσεις ερμηνεύονται ως `simple` ή `log` στο downstream logic.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_run_portfolio_backtest`

##### Callable `src.experiments.runner:_build_storage_context`

- Signature: `def _build_storage_context(data_cfg: dict[str, Any], symbols: list[str], pit_cfg: dict[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `15`
- Σύνοψη λογικής: Handle storage context inside the experiment orchestration layer.
- Παράμετροι:
  - `data_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για source, σύμβολα, PIT και storage behavior.
  - `symbols` (keyword-only, `list[str]`, default `χωρίς default`): Λίστα tickers/asset identifiers για panel loading ή portfolio processing.
  - `pit_cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Configuration block για point-in-time hardening.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_load_asset_frames`, `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_snapshot_context_matches`

- Signature: `def _snapshot_context_matches(snapshot_meta: dict[str, Any], expected_context: dict[str, Any]) -> bool`
- Return type: `bool`
- LOC: `7`
- Σύνοψη λογικής: Verify that a cached snapshot was built under the same data and PIT context requested by the current run.
- Παράμετροι:
  - `snapshot_meta` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Metadata που διαβάστηκε από persisted snapshot.
  - `expected_context` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Canonical context που πρέπει να ταιριάξει με cached snapshot.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_load_asset_frames`

##### Callable `src.experiments.runner:_load_asset_frames`

- Signature: `def _load_asset_frames(data_cfg: dict[str, Any]) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]`
- Return type: `tuple[dict[str, pd.DataFrame], dict[str, Any]]`
- LOC: `88`
- Σύνοψη λογικής: Handle asset frames inside the experiment orchestration layer.
- Παράμετροι:
  - `data_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για source, σύμβολα, PIT και storage behavior.
- Side effects: Διαβαζει δεδομενα ή snapshots απο filesystem/provider. Γραφει artifacts/snapshots στο filesystem.
- Exceptions: `ValueError`
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`, `tests.test_runner_extensions:test_load_asset_frames_rejects_cached_snapshot_with_mismatched_pit_context`

##### Callable `src.experiments.runner:_save_processed_snapshot_if_enabled`

- Signature: `def _save_processed_snapshot_if_enabled(asset_frames: dict[str, pd.DataFrame], data_cfg: dict[str, Any], config_hash_sha256: str, feature_steps: list[dict[str, Any]]) -> dict[str, Any] | None`
- Return type: `dict[str, Any] | None`
- LOC: `29`
- Σύνοψη λογικής: Handle processed snapshot if enabled inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `data_cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Configuration block για source, σύμβολα, PIT και storage behavior.
  - `config_hash_sha256` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `feature_steps` (keyword-only, `list[dict[str, Any]]`, default `χωρίς default`): Δηλωτική λίστα feature transformations που εφαρμόζονται σειριακά.
- Side effects: Γραφει artifacts/snapshots στο filesystem.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_align_asset_column`

- Signature: `def _align_asset_column(asset_frames: dict[str, pd.DataFrame], column: str, how: str) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `22`
- Σύνοψη λογικής: Handle align asset column inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `column` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `how` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_build_execution_output`, `src.experiments.runner:_run_portfolio_backtest`

##### Callable `src.experiments.runner:_build_portfolio_constraints`

- Signature: `def _build_portfolio_constraints(portfolio_cfg: dict[str, Any]) -> PortfolioConstraints`
- Return type: `PortfolioConstraints`
- LOC: `22`
- Σύνοψη λογικής: Handle portfolio constraints inside the experiment orchestration layer.
- Παράμετροι:
  - `portfolio_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block για portfolio construction και constraints.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_run_portfolio_backtest`

##### Callable `src.experiments.runner:_run_single_asset_backtest`

- Signature: `def _run_single_asset_backtest(asset: str, df: pd.DataFrame, cfg: dict[str, Any], model_meta: dict[str, Any]) -> BacktestResult`
- Return type: `BacktestResult`
- LOC: `48`
- Σύνοψη λογικής: Handle single asset backtest inside the experiment orchestration layer.
- Παράμετροι:
  - `asset` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `model_meta` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_run_portfolio_backtest`

- Signature: `def _run_portfolio_backtest(asset_frames: dict[str, pd.DataFrame], cfg: dict[str, Any]) -> tuple[PortfolioPerformance, pd.DataFrame, pd.DataFrame, dict[str, Any]]`
- Return type: `tuple[PortfolioPerformance, pd.DataFrame, pd.DataFrame, dict[str, Any]]`
- LOC: `75`
- Σύνοψη λογικής: Handle portfolio backtest inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_compute_subset_metrics`

- Signature: `def _compute_subset_metrics(net_returns: pd.Series, turnover: pd.Series, costs: pd.Series, gross_returns: pd.Series, periods_per_year: int, mask: pd.Series) -> dict[str, float]`
- Return type: `dict[str, float]`
- LOC: `24`
- Σύνοψη λογικής: Handle subset metrics inside the experiment orchestration layer.
- Παράμετροι:
  - `net_returns` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `turnover` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `costs` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `gross_returns` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `periods_per_year` (keyword-only, `int`, default `χωρίς default`): Annualization factor για returns και risk metrics.
  - `mask` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_build_fold_backtest_summaries`, `src.experiments.runner:_build_portfolio_evaluation`, `src.experiments.runner:_build_single_asset_evaluation`

##### Callable `src.experiments.runner:_build_fold_backtest_summaries`

- Signature: `def _build_fold_backtest_summaries(source_index: pd.Index, net_returns: pd.Series, turnover: pd.Series, costs: pd.Series, gross_returns: pd.Series, periods_per_year: int, folds: list[dict[str, Any]]) -> list[dict[str, Any]]`
- Return type: `list[dict[str, Any]]`
- LOC: `37`
- Σύνοψη λογικής: Handle fold backtest summaries inside the experiment orchestration layer.
- Παράμετροι:
  - `source_index` (keyword-only, `pd.Index`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `net_returns` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `turnover` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `costs` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `gross_returns` (keyword-only, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `periods_per_year` (keyword-only, `int`, default `χωρίς default`): Annualization factor για returns και risk metrics.
  - `folds` (keyword-only, `list[dict[str, Any]]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_build_single_asset_evaluation`

##### Callable `src.experiments.runner:_build_single_asset_evaluation`

- Signature: `def _build_single_asset_evaluation(asset: str, df: pd.DataFrame, performance: BacktestResult, model_meta: dict[str, Any], periods_per_year: int) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `54`
- Σύνοψη λογικής: Handle single asset evaluation inside the experiment orchestration layer.
- Παράμετροι:
  - `asset` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `performance` (keyword-only, `BacktestResult`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `model_meta` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `periods_per_year` (keyword-only, `int`, default `χωρίς default`): Annualization factor για returns και risk metrics.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_build_portfolio_evaluation`

- Signature: `def _build_portfolio_evaluation(asset_frames: dict[str, pd.DataFrame], performance: PortfolioPerformance, model_meta: dict[str, Any], periods_per_year: int, alignment: str) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `62`
- Σύνοψη λογικής: Handle portfolio evaluation inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `performance` (keyword-only, `PortfolioPerformance`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `model_meta` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `periods_per_year` (keyword-only, `int`, default `χωρίς default`): Annualization factor για returns και risk metrics.
  - `alignment` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_compute_monitoring_for_asset`

- Signature: `def _compute_monitoring_for_asset(df: pd.DataFrame, meta: dict[str, Any], monitoring_cfg: dict[str, Any]) -> dict[str, Any] | None`
- Return type: `dict[str, Any] | None`
- LOC: `28`
- Σύνοψη λογικής: Handle monitoring for asset inside the experiment orchestration layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `meta` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `monitoring_cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Configuration block για drift diagnostics και thresholds.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_compute_monitoring_report`

##### Callable `src.experiments.runner:_compute_monitoring_report`

- Signature: `def _compute_monitoring_report(asset_frames: dict[str, pd.DataFrame], model_meta: dict[str, Any], monitoring_cfg: dict[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `45`
- Σύνοψη λογικής: Handle monitoring report inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `model_meta` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `monitoring_cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Configuration block για drift diagnostics και thresholds.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_build_execution_output`

- Signature: `def _build_execution_output(asset_frames: dict[str, pd.DataFrame], execution_cfg: dict[str, Any], portfolio_weights: pd.DataFrame | None, performance: BacktestResult | PortfolioPerformance, alignment: str) -> tuple[dict[str, Any], pd.DataFrame | None]`
- Return type: `tuple[dict[str, Any], pd.DataFrame | None]`
- LOC: `52`
- Σύνοψη λογικής: Handle execution output inside the experiment orchestration layer.
- Παράμετροι:
  - `asset_frames` (keyword-only, `dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `execution_cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Configuration block για paper execution export.
  - `portfolio_weights` (keyword-only, `pd.DataFrame | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `performance` (keyword-only, `BacktestResult | PortfolioPerformance`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `alignment` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:_data_stats_payload`

- Signature: `def _data_stats_payload(data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `25`
- Σύνοψη λογικής: Handle data stats payload inside the experiment orchestration layer.
- Παράμετροι:
  - `data` (positional-or-keyword, `pd.DataFrame | dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_save_artifacts`

##### Callable `src.experiments.runner:_resolved_feature_columns`

- Signature: `def _resolved_feature_columns(model_meta: dict[str, Any]) -> list[str] | dict[str, list[str]] | None`
- Return type: `list[str] | dict[str, list[str]] | None`
- LOC: `16`
- Σύνοψη λογικής: Handle resolved feature columns inside the experiment orchestration layer.
- Παράμετροι:
  - `model_meta` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:_save_artifacts`

##### Callable `src.experiments.runner:_save_artifacts`

- Signature: `def _save_artifacts(run_dir: Path, cfg: dict[str, Any], data: pd.DataFrame | dict[str, pd.DataFrame], performance: BacktestResult | PortfolioPerformance, model_meta: dict[str, Any], evaluation: dict[str, Any], monitoring: dict[str, Any], execution: dict[str, Any], execution_orders: pd.DataFrame | None, portfolio_weights: pd.DataFrame | None, portfolio_diagnostics: pd.DataFrame | None, portfolio_meta: dict[str, Any], storage_meta: dict[str, Any], run_metadata: dict[str, Any], config_hash_sha256: str, data_fingerprint: dict[str, Any]) -> dict[str, str]`
- Return type: `dict[str, str]`
- LOC: `129`
- Σύνοψη λογικής: Handle artifacts inside the experiment orchestration layer.
- Παράμετροι:
  - `run_dir` (keyword-only, `Path`, default `χωρίς default`): Filesystem path για read/write artifact handling.
  - `cfg` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `data` (keyword-only, `pd.DataFrame | dict[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `performance` (keyword-only, `BacktestResult | PortfolioPerformance`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `model_meta` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `evaluation` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `monitoring` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `execution` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `execution_orders` (keyword-only, `pd.DataFrame | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `portfolio_weights` (keyword-only, `pd.DataFrame | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `portfolio_diagnostics` (keyword-only, `pd.DataFrame | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `portfolio_meta` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `storage_meta` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `run_metadata` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `config_hash_sha256` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `data_fingerprint` (keyword-only, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Γραφει artifacts/snapshots στο filesystem.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Coordinator-level complexity. Κληρονομει το αθροισμα των downstream σταδιων που orchestrate-αρει.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.experiments.runner:run_experiment`

- Signature: `def run_experiment(config_path: str | Path) -> ExperimentResult`
- Return type: `ExperimentResult`
- LOC: `147`
- Σύνοψη λογικής: Run experiment end to end for the experiment orchestration layer.
- Παράμετροι:
  - `config_path` (positional-or-keyword, `str | Path`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Επηρεαζει global reproducibility state (random seeds / περιβαλλον εκτελεσης).
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνθετική πολυπλοκότητα που κυριαρχείται από data ingestion, feature pipeline, cross-validation training και backtesting. Πρακτικά O(A * (I/O + F(T, P) + CV_fit + B(T))).
- Direct callers: `tests.test_runner_extensions:test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution`

### 17.10 Package `src/features`

- Ρόλος package: Feature engineering
- Modules: `4`
- LOC: `219`
- Top-level callables: `6`
- Methods: `0`
- Classes: `0`

#### Module `src/features/__init__.py`

- Python module: `src.features`
- Ρόλος: Feature engineering
- LOC: `20`
- Imports: `.lags`, `.returns`, `.technical.trend`, `.volatility`
- Global constants / exported symbols:
  - `__all__` = `['compute_returns', 'add_close_returns', 'compute_rolling_vol', 'compute_ewma_vol', 'add_volatili...`
- ASCII dependency sketch:
```text
[imports] .lags, .returns, .technical.trend, .volatility
      |
      v
[module] src.features
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/features/lags.py`

- Python module: `src.features.lags`
- Ρόλος: Feature engineering
- LOC: `35`
- Imports: `__future__`, `pandas`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `add_lagged_features`

##### Callable `src.features.lags:add_lagged_features`

- Signature: `def add_lagged_features(df: pd.DataFrame, cols: Iterable[str], lags: Sequence[int] = (1, 2, 5), prefix: str = 'lag') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `27`
- Σύνοψη λογικής: Add lagged versions of specified columns.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `cols` (positional-or-keyword, `Iterable[str]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `lags` (positional-or-keyword, `Sequence[int]`, default `(1, 2, 5)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `prefix` (positional-or-keyword, `str`, default `'lag'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `src/features/returns.py`

- Python module: `src.features.returns`
- Ρόλος: Feature engineering
- LOC: `64`
- Imports: `__future__`, `numpy`, `pandas`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_returns`
  - `add_close_returns`

##### Callable `src.features.returns:compute_returns`

- Signature: `def compute_returns(prices: pd.Series, log: bool = False, dropna: bool = True) -> pd.Series`
- Return type: `pd.Series`
- LOC: `28`
- Σύνοψη λογικής: r_t = P_t / P_{t-1} - 1 (log=False) r_t = log(P_t / P_{t-1}) (log=True)
- Παράμετροι:
  - `prices` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `log` (positional-or-keyword, `bool`, default `False`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `dropna` (positional-or-keyword, `bool`, default `True`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.returns:add_close_returns`, `tests.test_core:test_compute_returns_simple_and_log`

##### Callable `src.features.returns:add_close_returns`

- Signature: `def add_close_returns(df: pd.DataFrame, log: bool = False, col_name: str | None = None) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `30`
- Σύνοψη λογικής: Parameters ---------- df : pd.DataFrame OHLCV dataframe log : bool If True -> log-returns, else returns.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `log` (positional-or-keyword, `bool`, default `False`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `col_name` (positional-or-keyword, `str | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `src/features/volatility.py`

- Python module: `src.features.volatility`
- Ρόλος: Feature engineering
- LOC: `100`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_rolling_vol`
  - `compute_ewma_vol`
  - `add_volatility_features`

##### Callable `src.features.volatility:compute_rolling_vol`

- Signature: `def compute_rolling_vol(returns: pd.Series, window: int, ddof: int = 1, annualization_factor: Optional[float] = None) -> pd.Series`
- Return type: `pd.Series`
- LOC: `25`
- Σύνοψη λογικής: Rolling realized volatility on a series of returns.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `window` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `ddof` (positional-or-keyword, `int`, default `1`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `annualization_factor` (positional-or-keyword, `Optional[float]`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.volatility:add_volatility_features`

##### Callable `src.features.volatility:compute_ewma_vol`

- Signature: `def compute_ewma_vol(returns: pd.Series, span: int, annualization_factor: Optional[float] = None) -> pd.Series`
- Return type: `pd.Series`
- LOC: `22`
- Σύνοψη λογικής: EWMA volatility (Exponentially Weighted Moving Std) span: like pandas ewm(span=...).
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `span` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `annualization_factor` (positional-or-keyword, `Optional[float]`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.volatility:add_volatility_features`

##### Callable `src.features.volatility:add_volatility_features`

- Signature: `def add_volatility_features(df: pd.DataFrame, returns_col: str = 'close_logret', rolling_windows: Sequence[int] = (10, 20, 60), ewma_spans: Sequence[int] = (10, 20), annualization_factor: Optional[float] = 252.0, inplace: bool = False) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `42`
- Σύνοψη λογικής: Assumes: - df[returns_col] Adds volatility features to DataFrame: - vol_rolling_{w} - vol_ewma_{span}
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `returns_col` (positional-or-keyword, `str`, default `'close_logret'`): Όνομα στήλης αποδόσεων που τροφοδοτεί backtest, metrics ή model layer.
  - `rolling_windows` (positional-or-keyword, `Sequence[int]`, default `(10, 20, 60)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `ewma_spans` (positional-or-keyword, `Sequence[int]`, default `(10, 20)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `annualization_factor` (positional-or-keyword, `Optional[float]`, default `252.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `inplace` (positional-or-keyword, `bool`, default `False`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

### 17.11 Package `src/features/technical`

- Ρόλος package: Feature engineering
- Modules: `5`
- LOC: `702`
- Top-level callables: `22`
- Methods: `0`
- Classes: `0`

#### Module `src/features/technical/__init__.py`

- Python module: `src.features.technical`
- Ρόλος: Feature engineering
- LOC: `55`
- Imports: `.indicators`, `.momentum`, `.oscillators`, `.trend`
- Global constants / exported symbols:
  - `__all__` = `['compute_sma', 'compute_ema', 'add_trend_features', 'add_trend_regime_features', 'compute_price_...`
- ASCII dependency sketch:
```text
[imports] .indicators, .momentum, .oscillators, .trend
      |
      v
[module] src.features.technical
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/features/technical/indicators.py`

- Python module: `src.features.technical.indicators`
- Ρόλος: Feature engineering
- LOC: `241`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_true_range`
  - `compute_atr`
  - `add_bollinger_bands`
  - `compute_macd`
  - `compute_ppo`
  - `compute_roc`
  - `compute_volume_zscore`
  - `compute_adx`
  - `compute_mfi`
  - `add_indicator_features`

##### Callable `src.features.technical.indicators:compute_true_range`

- Signature: `def compute_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series`
- Return type: `pd.Series`
- LOC: `14`
- Σύνοψη λογικής: True range as max of (high-low, |high-prev_close|, |low-prev_close|).
- Παράμετροι:
  - `high` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `low` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:compute_adx`, `src.features.technical.indicators:compute_atr`

##### Callable `src.features.technical.indicators:compute_atr`

- Signature: `def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14, method: str = 'wilder') -> pd.Series`
- Return type: `pd.Series`
- LOC: `17`
- Σύνοψη λογικής: Average True Range (ATR).
- Παράμετροι:
  - `high` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `low` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `14`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `method` (positional-or-keyword, `str`, default `'wilder'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:add_indicator_features`

##### Callable `src.features.technical.indicators:add_bollinger_bands`

- Signature: `def add_bollinger_bands(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `22`
- Σύνοψη λογικής: Bollinger bands and derived features: upper, lower, band_width, percent_b.
- Παράμετροι:
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `20`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `n_std` (positional-or-keyword, `float`, default `2.0`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:add_indicator_features`

##### Callable `src.features.technical.indicators:compute_macd`

- Signature: `def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `19`
- Σύνοψη λογικής: MACD line, signal line, histogram.
- Παράμετροι:
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `fast` (positional-or-keyword, `int`, default `12`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `slow` (positional-or-keyword, `int`, default `26`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal` (positional-or-keyword, `int`, default `9`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:add_indicator_features`

##### Callable `src.features.technical.indicators:compute_ppo`

- Signature: `def compute_ppo(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `19`
- Σύνοψη λογικής: Percentage Price Oscillator: normalized MACD.
- Παράμετροι:
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `fast` (positional-or-keyword, `int`, default `12`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `slow` (positional-or-keyword, `int`, default `26`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal` (positional-or-keyword, `int`, default `9`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:add_indicator_features`

##### Callable `src.features.technical.indicators:compute_roc`

- Signature: `def compute_roc(close: pd.Series, window: int = 10) -> pd.Series`
- Return type: `pd.Series`
- LOC: `8`
- Σύνοψη λογικής: Rate of Change: (P_t / P_{t-w}) - 1.
- Παράμετροι:
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `10`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:add_indicator_features`

##### Callable `src.features.technical.indicators:compute_volume_zscore`

- Signature: `def compute_volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series`
- Return type: `pd.Series`
- LOC: `10`
- Σύνοψη λογικής: Rolling z-score of volume.
- Παράμετροι:
  - `volume` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `20`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:add_indicator_features`

##### Callable `src.features.technical.indicators:compute_adx`

- Signature: `def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `29`
- Σύνοψη λογικής: ADX with DI+, DI- using Wilder smoothing.
- Παράμετροι:
  - `high` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `low` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `14`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:add_indicator_features`

##### Callable `src.features.technical.indicators:compute_mfi`

- Signature: `def compute_mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int = 14) -> pd.Series`
- Return type: `pd.Series`
- LOC: `22`
- Σύνοψη λογικής: Money Flow Index (uses typical price * volume).
- Παράμετροι:
  - `high` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `low` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `volume` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `14`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.indicators:add_indicator_features`, `tests.test_contracts_metrics_pit:test_mfi_saturates_to_100_when_negative_flow_is_zero`

##### Callable `src.features.technical.indicators:add_indicator_features`

- Signature: `def add_indicator_features(df: pd.DataFrame, price_col: str = 'close', high_col: str = 'high', low_col: str = 'low', volume_col: str = 'volume', bb_window: int = 20, bb_nstd: float = 2.0, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9, ppo_fast: int = 12, ppo_slow: int = 26, ppo_signal: int = 9, roc_windows: Sequence[int] = (10, 20), atr_window: int = 14, adx_window: int = 14, vol_z_window: int = 20, include_mfi: bool = True) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `55`
- Σύνοψη λογικής: Add a bundle of classic indicators to an OHLCV dataframe.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `price_col` (positional-or-keyword, `str`, default `'close'`): Όνομα στήλης τιμών που χρησιμοποιείται ως βάση υπολογισμού feature/target.
  - `high_col` (positional-or-keyword, `str`, default `'high'`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `low_col` (positional-or-keyword, `str`, default `'low'`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `volume_col` (positional-or-keyword, `str`, default `'volume'`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `bb_window` (positional-or-keyword, `int`, default `20`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `bb_nstd` (positional-or-keyword, `float`, default `2.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `macd_fast` (positional-or-keyword, `int`, default `12`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `macd_slow` (positional-or-keyword, `int`, default `26`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `macd_signal` (positional-or-keyword, `int`, default `9`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `ppo_fast` (positional-or-keyword, `int`, default `12`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `ppo_slow` (positional-or-keyword, `int`, default `26`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `ppo_signal` (positional-or-keyword, `int`, default `9`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `roc_windows` (positional-or-keyword, `Sequence[int]`, default `(10, 20)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `atr_window` (positional-or-keyword, `int`, default `14`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `adx_window` (positional-or-keyword, `int`, default `14`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `vol_z_window` (positional-or-keyword, `int`, default `20`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `include_mfi` (positional-or-keyword, `bool`, default `True`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `src/features/technical/momentum.py`

- Python module: `src.features.technical.momentum`
- Ρόλος: Feature engineering
- LOC: `93`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_price_momentum`
  - `compute_return_momentum`
  - `compute_vol_normalized_momentum`
  - `add_momentum_features`

##### Callable `src.features.technical.momentum:compute_price_momentum`

- Signature: `def compute_price_momentum(prices: pd.Series, window: int) -> pd.Series`
- Return type: `pd.Series`
- LOC: `13`
- Σύνοψη λογικής: Price momentum: P_t / P_{t-window} - 1
- Παράμετροι:
  - `prices` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.momentum:add_momentum_features`

##### Callable `src.features.technical.momentum:compute_return_momentum`

- Signature: `def compute_return_momentum(returns: pd.Series, window: int) -> pd.Series`
- Return type: `pd.Series`
- LOC: `14`
- Σύνοψη λογικής: Return-based momentum: sum of returns over window.
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `window` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.momentum:add_momentum_features`

##### Callable `src.features.technical.momentum:compute_vol_normalized_momentum`

- Signature: `def compute_vol_normalized_momentum(returns: pd.Series, volatility: pd.Series, window: int, eps: float = 1e-08) -> pd.Series`
- Return type: `pd.Series`
- LOC: `20`
- Σύνοψη λογικής: Volatility-normalized momentum: sum of returns / current volatility
- Παράμετροι:
  - `returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Series αποδόσεων που χρησιμοποιείται για metrics, validation ή PnL accounting.
  - `volatility` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `eps` (positional-or-keyword, `float`, default `1e-08`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.momentum:add_momentum_features`

##### Callable `src.features.technical.momentum:add_momentum_features`

- Signature: `def add_momentum_features(df: pd.DataFrame, price_col: str = 'close', returns_col: str = 'close_logret', vol_col: Optional[str] = 'vol_rolling_20', windows: Sequence[int] = (5, 20, 60), inplace: bool = False) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `32`
- Σύνοψη λογικής: Προσθέτει momentum features: - price momentum - return momentum - volatility-normalized momentum (αν υπάρχει vol_col)
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `price_col` (positional-or-keyword, `str`, default `'close'`): Όνομα στήλης τιμών που χρησιμοποιείται ως βάση υπολογισμού feature/target.
  - `returns_col` (positional-or-keyword, `str`, default `'close_logret'`): Όνομα στήλης αποδόσεων που τροφοδοτεί backtest, metrics ή model layer.
  - `vol_col` (positional-or-keyword, `Optional[str]`, default `'vol_rolling_20'`): Όνομα στήλης volatility estimate για scaling ή targeting.
  - `windows` (positional-or-keyword, `Sequence[int]`, default `(5, 20, 60)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `inplace` (positional-or-keyword, `bool`, default `False`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `src/features/technical/oscillators.py`

- Python module: `src.features.technical.oscillators`
- Ρόλος: Feature engineering
- LOC: `123`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] __future__, numpy, pandas, typing
      |
      v
[module] src.features.technical.oscillators
      |
      +-- functions: 4
      |
[inbound] src.features.technical.oscillators:add_oscillator_features, tests.test_contracts_...
```

- Classes: Καμία.

- Top-level callables:
  - `compute_rsi`
  - `compute_stoch_k`
  - `compute_stoch_d`
  - `add_oscillator_features`

##### Callable `src.features.technical.oscillators:compute_rsi`

- Signature: `def compute_rsi(prices: pd.Series, window: int = 14, method: str = 'wilder') -> pd.Series`
- Return type: `pd.Series`
- LOC: `36`
- Σύνοψη λογικής: RSI (Relative Strength Index).
- Παράμετροι:
  - `prices` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `14`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `method` (positional-or-keyword, `str`, default `'wilder'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.oscillators:add_oscillator_features`, `tests.test_contracts_metrics_pit:test_rsi_saturates_to_100_in_monotonic_uptrend`

##### Callable `src.features.technical.oscillators:compute_stoch_k`

- Signature: `def compute_stoch_k(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) -> pd.Series`
- Return type: `pd.Series`
- LOC: `22`
- Σύνοψη λογικής: Stochastic %K: %K_t = 100 * (close_t - lowest_low) / (highest_high - lowest_low)
- Παράμετροι:
  - `close` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `high` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `low` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `14`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.oscillators:add_oscillator_features`

##### Callable `src.features.technical.oscillators:compute_stoch_d`

- Signature: `def compute_stoch_d(k: pd.Series, smooth: int = 3) -> pd.Series`
- Return type: `pd.Series`
- LOC: `13`
- Σύνοψη λογικής: Stochastic %D: moving average του %K.
- Παράμετροι:
  - `k` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `smooth` (positional-or-keyword, `int`, default `3`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.oscillators:add_oscillator_features`

##### Callable `src.features.technical.oscillators:add_oscillator_features`

- Signature: `def add_oscillator_features(df: pd.DataFrame, price_col: str = 'close', high_col: str = 'high', low_col: str = 'low', rsi_windows: Sequence[int] = (14,), stoch_windows: Sequence[int] = (14,), stoch_smooth: int = 3, inplace: bool = False) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `38`
- Σύνοψη λογικής: Features: - {price_col}_rsi_{w} - {price_col}_stoch_k_{w} - {price_col}_stoch_k_{w}_d{stoch_smooth}
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `price_col` (positional-or-keyword, `str`, default `'close'`): Όνομα στήλης τιμών που χρησιμοποιείται ως βάση υπολογισμού feature/target.
  - `high_col` (positional-or-keyword, `str`, default `'high'`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `low_col` (positional-or-keyword, `str`, default `'low'`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `rsi_windows` (positional-or-keyword, `Sequence[int]`, default `(14,)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `stoch_windows` (positional-or-keyword, `Sequence[int]`, default `(14,)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `stoch_smooth` (positional-or-keyword, `int`, default `3`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `inplace` (positional-or-keyword, `bool`, default `False`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `src/features/technical/trend.py`

- Python module: `src.features.technical.trend`
- Ρόλος: Feature engineering
- LOC: `190`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_sma`
  - `compute_ema`
  - `add_trend_features`
  - `add_trend_regime_features`

##### Callable `src.features.technical.trend:compute_sma`

- Signature: `def compute_sma(prices: pd.Series, window: int, min_periods: Optional[int] = None) -> pd.Series`
- Return type: `pd.Series`
- LOC: `32`
- Σύνοψη λογικής: Simple Moving Average (SMA) .
- Παράμετροι:
  - `prices` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `window` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `min_periods` (positional-or-keyword, `Optional[int]`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.trend:add_trend_features`

##### Callable `src.features.technical.trend:compute_ema`

- Signature: `def compute_ema(prices: pd.Series, span: int, adjust: bool = False) -> pd.Series`
- Return type: `pd.Series`
- LOC: `28`
- Σύνοψη λογικής: Exponential Moving Average (EMA) .
- Παράμετροι:
  - `prices` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `span` (positional-or-keyword, `int`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `adjust` (positional-or-keyword, `bool`, default `False`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.features.technical.trend:add_trend_features`

##### Callable `src.features.technical.trend:add_trend_features`

- Signature: `def add_trend_features(df: pd.DataFrame, price_col: str = 'close', sma_windows: Sequence[int] = (20, 50, 200), ema_spans: Sequence[int] = (20, 50), inplace: bool = False) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `57`
- Σύνοψη λογικής: Προσθέτει βασικά trend features σε OHLCV DataFrame.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `price_col` (positional-or-keyword, `str`, default `'close'`): Όνομα στήλης τιμών που χρησιμοποιείται ως βάση υπολογισμού feature/target.
  - `sma_windows` (positional-or-keyword, `Sequence[int]`, default `(20, 50, 200)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `ema_spans` (positional-or-keyword, `Sequence[int]`, default `(20, 50)`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `inplace` (positional-or-keyword, `bool`, default `False`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `tests.test_core:test_add_trend_features_columns`

##### Callable `src.features.technical.trend:add_trend_regime_features`

- Signature: `def add_trend_regime_features(df: pd.DataFrame, price_col: str = 'close', base_sma_for_sign: int = 50, short_sma: int = 20, long_sma: int = 50, inplace: bool = False) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `61`
- Σύνοψη λογικής: trend "regime" features based on MAs.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `price_col` (positional-or-keyword, `str`, default `'close'`): Όνομα στήλης τιμών που χρησιμοποιείται ως βάση υπολογισμού feature/target.
  - `base_sma_for_sign` (positional-or-keyword, `int`, default `50`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `short_sma` (positional-or-keyword, `int`, default `20`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `long_sma` (positional-or-keyword, `int`, default `50`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `inplace` (positional-or-keyword, `bool`, default `False`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

### 17.12 Package `src/models`

- Ρόλος package: Model helpers / baselines
- Modules: `2`
- LOC: `128`
- Top-level callables: `5`
- Methods: `0`
- Classes: `1`

#### Module `src/models/__init__.py`

- Python module: `src.models`
- Ρόλος: Model helpers / baselines
- LOC: `0`
- Imports: Δεν υπάρχουν imports.
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] none
      |
      v
[module] src.models
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/models/lightgbm_baseline.py`

- Python module: `src.models.lightgbm_baseline`
- Ρόλος: Model helpers / baselines
- LOC: `128`
- Imports: `__future__`, `dataclasses`, `lightgbm`, `numpy`, `pandas`, `src.features.lags`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes στο module:
  - `LGBMBaselineConfig`

##### Class `src.models.lightgbm_baseline:LGBMBaselineConfig`

- Βάσεις: `-`
- LOC: `12`
- Σύνοψη ρόλου: Store the default hyperparameters used by the lightweight LightGBM baseline so notebooks and helper utilities can share one explicit parameter bundle.
- Fields:
  - `n_estimators` (`int`, default `400`)
  - `learning_rate` (`float`, default `0.03`)
  - `max_depth` (`int`, default `4`)
  - `subsample` (`float`, default `0.8`)
  - `colsample_bytree` (`float`, default `0.8`)
  - `min_child_samples` (`int`, default `40`)
  - `random_state` (`int`, default `7`)
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

- Top-level callables:
  - `default_feature_columns`
  - `train_regressor`
  - `predict_returns`
  - `prediction_to_signal`
  - `train_test_split_time`

##### Callable `src.models.lightgbm_baseline:default_feature_columns`

- Signature: `def default_feature_columns(df: pd.DataFrame) -> list[str]`
- Return type: `list[str]`
- LOC: `28`
- Σύνοψη λογικής: Select a reasonable feature set if the notebook does not override.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Fit/predict cost εξαρτωμενο απο estimator, με συνηθη πρακτικη συμπεριφορα O(T * P) ή χειροτερη για boosting.
- Direct callers: `src.experiments.models:infer_feature_columns`

##### Callable `src.models.lightgbm_baseline:train_regressor`

- Signature: `def train_regressor(train_df: pd.DataFrame, feature_cols: Sequence[str], target_col: str, cfg: LGBMBaselineConfig | None = None) -> LGBMRegressor`
- Return type: `LGBMRegressor`
- LOC: `26`
- Σύνοψη λογικής: Fit a LightGBM regressor on the provided split.
- Παράμετροι:
  - `train_df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): DataFrame που μεταφερει tabular time-series state μεταξυ layers.
  - `feature_cols` (positional-or-keyword, `Sequence[str]`, default `χωρίς default`): Ρητή λίστα feature columns για supervised learning.
  - `target_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `cfg` (positional-or-keyword, `LGBMBaselineConfig | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Μεταβαλλει internal state estimator/model object με training.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Fit/predict cost εξαρτωμενο απο estimator, με συνηθη πρακτικη συμπεριφορα O(T * P) ή χειροτερη για boosting.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.models.lightgbm_baseline:predict_returns`

- Signature: `def predict_returns(model: LGBMRegressor, df: pd.DataFrame, feature_cols: Sequence[str], pred_col: str = 'pred_next_ret') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `11`
- Σύνοψη λογικής: Generate next-period return predictions and attach to dataframe.
- Παράμετροι:
  - `model` (positional-or-keyword, `LGBMRegressor`, default `χωρίς default`): Estimator instance ή aggregate object που επιστρέφεται από το training layer.
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `feature_cols` (positional-or-keyword, `Sequence[str]`, default `χωρίς default`): Ρητή λίστα feature columns για supervised learning.
  - `pred_col` (positional-or-keyword, `str`, default `'pred_next_ret'`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Fit/predict cost εξαρτωμενο απο estimator, με συνηθη πρακτικη συμπεριφορα O(T * P) ή χειροτερη για boosting.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.models.lightgbm_baseline:prediction_to_signal`

- Signature: `def prediction_to_signal(df: pd.DataFrame, pred_col: str = 'pred_next_ret', signal_col: str = 'signal_lgb', long_threshold: float = 0.0, short_threshold: float | None = None) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `20`
- Σύνοψη λογικής: Convert predicted returns to a {-1,0,1} trading signal.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `pred_col` (positional-or-keyword, `str`, default `'pred_next_ret'`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `signal_col` (positional-or-keyword, `str`, default `'signal_lgb'`): Όνομα στήλης signal exposure ή conviction sizing.
  - `long_threshold` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `short_threshold` (positional-or-keyword, `float | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Fit/predict cost εξαρτωμενο απο estimator, με συνηθη πρακτικη συμπεριφορα O(T * P) ή χειροτερη για boosting.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.models.lightgbm_baseline:train_test_split_time`

- Signature: `def train_test_split_time(df: pd.DataFrame, train_frac: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]`
- Return type: `tuple[pd.DataFrame, pd.DataFrame]`
- LOC: `8`
- Σύνοψη λογικής: Time-ordered split (no shuffling).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `train_frac` (positional-or-keyword, `float`, default `0.7`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Fit/predict cost εξαρτωμενο απο estimator, με συνηθη πρακτικη συμπεριφορα O(T * P) ή χειροτερη για boosting.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

### 17.13 Package `src/monitoring`

- Ρόλος package: Monitoring
- Modules: `2`
- LOC: `119`
- Top-level callables: `2`
- Methods: `0`
- Classes: `0`

#### Module `src/monitoring/__init__.py`

- Python module: `src.monitoring`
- Ρόλος: Monitoring
- LOC: `6`
- Imports: `.drift`
- Global constants / exported symbols:
  - `__all__` = `['compute_feature_drift', 'population_stability_index']`
- ASCII dependency sketch:
```text
[imports] .drift
      |
      v
[module] src.monitoring
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/monitoring/drift.py`

- Python module: `src.monitoring.drift`
- Ρόλος: Monitoring
- LOC: `113`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['population_stability_index', 'compute_feature_drift']`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `population_stability_index`
  - `compute_feature_drift`

##### Callable `src.monitoring.drift:population_stability_index`

- Signature: `def population_stability_index(reference: pd.Series, current: pd.Series, n_bins: int = 10, eps: float = 1e-06) -> float`
- Return type: `float`
- LOC: `32`
- Σύνοψη λογικής: Handle population stability index inside the monitoring layer.
- Παράμετροι:
  - `reference` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `current` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `n_bins` (keyword-only, `int`, default `10`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
  - `eps` (keyword-only, `float`, default `1e-06`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.monitoring.drift:compute_feature_drift`

##### Callable `src.monitoring.drift:compute_feature_drift`

- Signature: `def compute_feature_drift(reference_df: pd.DataFrame, current_df: pd.DataFrame, feature_cols: Iterable[str] | None = None, psi_threshold: float = 0.2, n_bins: int = 10) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `65`
- Σύνοψη λογικής: Compute feature drift for the monitoring layer.
- Παράμετροι:
  - `reference_df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): DataFrame που μεταφερει tabular time-series state μεταξυ layers.
  - `current_df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): DataFrame που μεταφερει tabular time-series state μεταξυ layers.
  - `feature_cols` (keyword-only, `Iterable[str] | None`, default `None`): Ρητή λίστα feature columns για supervised learning.
  - `psi_threshold` (keyword-only, `float`, default `0.2`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `n_bins` (keyword-only, `int`, default `10`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:_compute_monitoring_for_asset`

### 17.14 Package `src/portfolio`

- Ρόλος package: Portfolio construction
- Modules: `5`
- LOC: `1078`
- Top-level callables: `22`
- Methods: `1`
- Classes: `2`

#### Module `src/portfolio/__init__.py`

- Python module: `src.portfolio`
- Ρόλος: Portfolio construction
- LOC: `35`
- Imports: `.constraints`, `.construction`, `.covariance`, `.optimizer`
- Global constants / exported symbols:
  - `__all__` = `['PortfolioConstraints', 'apply_weight_bounds', 'enforce_net_exposure', 'enforce_gross_leverage',...`
- ASCII dependency sketch:
```text
[imports] .constraints, .construction, .covariance, .optimizer
      |
      v
[module] src.portfolio
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/portfolio/constraints.py`

- Python module: `src.portfolio.constraints`
- Ρόλος: Portfolio construction
- LOC: `511`
- Imports: `__future__`, `dataclasses`, `numpy`, `pandas`, `scipy.optimize`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['PortfolioConstraints', 'apply_weight_bounds', 'enforce_net_exposure', 'enforce_gross_leverage',...`
- ASCII dependency sketch:
```text
[imports] __future__, dataclasses, numpy, pandas
      |
      v
[module] src.portfolio.constraints
      |
      +-- functions: 12
      |
      +-- classes: 1
      |
[inbound] src.portfolio.constraints:_build_diagnostics, src.portfolio.constraints:_constrai...
```

- Classes στο module:
  - `PortfolioConstraints`

##### Class `src.portfolio.constraints:PortfolioConstraints`

- Βάσεις: `-`
- LOC: `28`
- Σύνοψη ρόλου: Define the admissible region for portfolio weights, leverage, turnover, and optional group exposures so optimization and signal-to-weight projection share one explicit constrain...
- Fields:
  - `min_weight` (`float`, default `-1.0`)
  - `max_weight` (`float`, default `1.0`)
  - `max_gross_leverage` (`float`, default `1.0`)
  - `target_net_exposure` (`float`, default `0.0`)
  - `turnover_limit` (`float | None`, default `None`)
  - `group_max_exposure` (`Mapping[str, float] | None`, default `None`)
- Methods:
  - `__post_init__` -> `def __post_init__(self) -> None`

##### Callable `src.portfolio.constraints:PortfolioConstraints.__post_init__`

- Signature: `def __post_init__(self) -> None`
- Return type: `None`
- LOC: `15`
- Σύνοψη λογικής: Validate the dataclass fields immediately after initialization so invalid constraint combinations fail fast and cannot leak deeper into the portfolio pipeline.
- Παράμετροι:
  - `self` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Αναφορά στο instance της κλάσης.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

- Top-level callables:
  - `_as_weight_series`
  - `apply_weight_bounds`
  - `enforce_gross_leverage`
  - `_distribute_delta_with_bounds`
  - `enforce_net_exposure`
  - `enforce_group_caps`
  - `enforce_turnover_limit`
  - `_compute_group_gross_exposure`
  - `_constraint_violations`
  - `_build_diagnostics`
  - `_project_with_turnover_limit`
  - `apply_constraints`

##### Callable `src.portfolio.constraints:_as_weight_series`

- Signature: `def _as_weight_series(weights: pd.Series) -> pd.Series`
- Return type: `pd.Series`
- LOC: `9`
- Σύνοψη λογικής: Handle as weight series inside the portfolio construction layer.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:_build_diagnostics`, `src.portfolio.constraints:_constraint_violations`, `src.portfolio.constraints:_distribute_delta_with_bounds`, `src.portfolio.constraints:_project_with_turnover_limit`, `src.portfolio.constraints:apply_constraints`, `src.portfolio.constraints:apply_weight_bounds`, `src.portfolio.constraints:enforce_gross_leverage`, `src.portfolio.constraints:enforce_group_caps` και αλλοι 2 callers.

##### Callable `src.portfolio.constraints:apply_weight_bounds`

- Signature: `def apply_weight_bounds(weights: pd.Series, min_weight: float, max_weight: float) -> pd.Series`
- Return type: `pd.Series`
- LOC: `13`
- Σύνοψη λογικής: Apply weight bounds to the provided inputs in a controlled and reusable way.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `min_weight` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `max_weight` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:_project_with_turnover_limit`, `src.portfolio.constraints:apply_constraints`

##### Callable `src.portfolio.constraints:enforce_gross_leverage`

- Signature: `def enforce_gross_leverage(weights: pd.Series, max_gross_leverage: float) -> pd.Series`
- Return type: `pd.Series`
- LOC: `15`
- Σύνοψη λογικής: Enforce gross leverage as a hard constraint inside the portfolio construction layer.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `max_gross_leverage` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:_project_with_turnover_limit`, `src.portfolio.constraints:apply_constraints`

##### Callable `src.portfolio.constraints:_distribute_delta_with_bounds`

- Signature: `def _distribute_delta_with_bounds(weights: pd.Series, delta: float, min_weight: float, max_weight: float) -> pd.Series`
- Return type: `pd.Series`
- LOC: `47`
- Σύνοψη λογικής: Handle distribute delta with bounds inside the portfolio construction layer.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `delta` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `min_weight` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `max_weight` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:enforce_net_exposure`

##### Callable `src.portfolio.constraints:enforce_net_exposure`

- Signature: `def enforce_net_exposure(weights: pd.Series, target_net_exposure: float, min_weight: float, max_weight: float) -> pd.Series`
- Return type: `pd.Series`
- LOC: `22`
- Σύνοψη λογικής: Enforce net exposure as a hard constraint inside the portfolio construction layer.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `target_net_exposure` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `min_weight` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `max_weight` (keyword-only, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:_project_with_turnover_limit`, `src.portfolio.constraints:apply_constraints`

##### Callable `src.portfolio.constraints:enforce_group_caps`

- Signature: `def enforce_group_caps(weights: pd.Series, asset_to_group: Mapping[str, str] | None, group_max_exposure: Mapping[str, float] | None) -> pd.Series`
- Return type: `pd.Series`
- LOC: `24`
- Σύνοψη λογικής: Enforce group caps as a hard constraint inside the portfolio construction layer.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `χωρίς default`): Χαρτογράφηση asset -> group για exposure caps.
  - `group_max_exposure` (keyword-only, `Mapping[str, float] | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:_project_with_turnover_limit`, `src.portfolio.constraints:apply_constraints`

##### Callable `src.portfolio.constraints:enforce_turnover_limit`

- Signature: `def enforce_turnover_limit(weights: pd.Series, prev_weights: pd.Series | None, turnover_limit: float | None) -> pd.Series`
- Return type: `pd.Series`
- LOC: `22`
- Σύνοψη λογικής: Enforce turnover limit as a hard constraint inside the portfolio construction layer.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `prev_weights` (keyword-only, `pd.Series | None`, default `χωρίς default`): Weights της προηγούμενης περιόδου για turnover/cost accounting.
  - `turnover_limit` (keyword-only, `float | None`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:_project_with_turnover_limit`

##### Callable `src.portfolio.constraints:_compute_group_gross_exposure`

- Signature: `def _compute_group_gross_exposure(weights: pd.Series, constraints: PortfolioConstraints, asset_to_group: Mapping[str, str] | None) -> dict[str, float]`
- Return type: `dict[str, float]`
- LOC: `15`
- Σύνοψη λογικής: Compute per-group gross exposures for diagnostics and constraint validation.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `constraints` (keyword-only, `PortfolioConstraints`, default `χωρίς default`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `χωρίς default`): Χαρτογράφηση asset -> group για exposure caps.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:_build_diagnostics`, `src.portfolio.constraints:_constraint_violations`

##### Callable `src.portfolio.constraints:_constraint_violations`

- Signature: `def _constraint_violations(weights: pd.Series, constraints: PortfolioConstraints, prev_weights: pd.Series | None, asset_to_group: Mapping[str, str] | None, tol: float = 1e-08) -> dict[str, float | dict[str, float]]`
- Return type: `dict[str, float | dict[str, float]]`
- LOC: `49`
- Σύνοψη λογικής: Summarize hard-constraint violations so callers can fail loudly instead of accepting an invalid portfolio.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `constraints` (keyword-only, `PortfolioConstraints`, default `χωρίς default`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `prev_weights` (keyword-only, `pd.Series | None`, default `χωρίς default`): Weights της προηγούμενης περιόδου για turnover/cost accounting.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `χωρίς default`): Χαρτογράφηση asset -> group για exposure caps.
  - `tol` (keyword-only, `float`, default `1e-08`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:_project_with_turnover_limit`, `src.portfolio.constraints:apply_constraints`

##### Callable `src.portfolio.constraints:_build_diagnostics`

- Signature: `def _build_diagnostics(weights: pd.Series, constraints: PortfolioConstraints, prev_weights: pd.Series | None, asset_to_group: Mapping[str, str] | None) -> dict[str, float | dict[str, float]]`
- Return type: `dict[str, float | dict[str, float]]`
- LOC: `29`
- Σύνοψη λογικής: Build the standard diagnostics payload returned by constraint projection helpers.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `constraints` (keyword-only, `PortfolioConstraints`, default `χωρίς default`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `prev_weights` (keyword-only, `pd.Series | None`, default `χωρίς default`): Weights της προηγούμενης περιόδου για turnover/cost accounting.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `χωρίς default`): Χαρτογράφηση asset -> group για exposure caps.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:apply_constraints`

##### Callable `src.portfolio.constraints:_project_with_turnover_limit`

- Signature: `def _project_with_turnover_limit(weights: pd.Series, constraints: PortfolioConstraints, prev_weights: pd.Series, asset_to_group: Mapping[str, str] | None, n_projection_passes: int) -> pd.Series`
- Return type: `pd.Series`
- LOC: `122`
- Σύνοψη λογικής: Solve a closest-feasible projection when turnover is a hard constraint.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `constraints` (keyword-only, `PortfolioConstraints`, default `χωρίς default`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `prev_weights` (keyword-only, `pd.Series`, default `χωρίς default`): Weights της προηγούμενης περιόδου για turnover/cost accounting.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `χωρίς default`): Χαρτογράφηση asset -> group για exposure caps.
  - `n_projection_passes` (keyword-only, `int`, default `χωρίς default`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.constraints:apply_constraints`

##### Callable `src.portfolio.constraints:apply_constraints`

- Signature: `def apply_constraints(weights: pd.Series, constraints: PortfolioConstraints, prev_weights: pd.Series | None = None, asset_to_group: Mapping[str, str] | None = None, n_projection_passes: int = 3) -> tuple[pd.Series, dict[str, float | dict[str, float]]]`
- Return type: `tuple[pd.Series, dict[str, float | dict[str, float]]]`
- LOC: `70`
- Σύνοψη λογικής: Apply constraints to the provided inputs in a controlled and reusable way.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.Series`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `constraints` (keyword-only, `PortfolioConstraints`, default `χωρίς default`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `prev_weights` (keyword-only, `pd.Series | None`, default `None`): Weights της προηγούμενης περιόδου για turnover/cost accounting.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `None`): Χαρτογράφηση asset -> group για exposure caps.
  - `n_projection_passes` (keyword-only, `int`, default `3`): Ακεραια παραμετρος πληθους rows, bins, folds ή αλλου cardinality measure.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.construction:build_weights_from_signals_over_time`, `src.portfolio.optimizer:optimize_mean_variance`, `tests.test_portfolio:test_apply_constraints_respects_bounds_group_gross_and_turnover`, `tests.test_portfolio:test_apply_constraints_turnover_limit_raises_when_constraint_set_is_infeasible`

#### Module `src/portfolio/construction.py`

- Python module: `src.portfolio.construction`
- Ρόλος: Portfolio construction
- LOC: `278`
- Imports: `__future__`, `dataclasses`, `numpy`, `pandas`, `src.evaluation.metrics`, `src.portfolio.constraints`, `src.portfolio.optimizer`, `typing`
- Global constants / exported symbols:
  - `_ALLOWED_MISSING_RETURN_POLICIES` = `{'raise', 'raise_if_exposed', 'fill_zero'}`
  - `__all__` = `['PortfolioPerformance', 'signal_to_raw_weights', 'build_weights_from_signals_over_time', 'build_...`
- ASCII dependency sketch:
```text
[imports] __future__, dataclasses, numpy, pandas
      |
      v
[module] src.portfolio.construction
      |
      +-- functions: 5
      |
      +-- classes: 1
      |
[inbound] src.backtesting.engine:run_backtest, src.experiments.runner:_run_portfolio_backte...
```

- Classes στο module:
  - `PortfolioPerformance`

##### Class `src.portfolio.construction:PortfolioPerformance`

- Βάσεις: `-`
- LOC: `11`
- Σύνοψη ρόλου: Store the time series and aggregate statistics produced by a portfolio-level backtest, keeping net and gross performance decomposition available for diagnostics.
- Fields:
  - `equity_curve` (`pd.Series`, default `-`)
  - `net_returns` (`pd.Series`, default `-`)
  - `gross_returns` (`pd.Series`, default `-`)
  - `costs` (`pd.Series`, default `-`)
  - `turnover` (`pd.Series`, default `-`)
  - `summary` (`dict[str, float]`, default `-`)
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

- Top-level callables:
  - `_apply_missing_return_policy`
  - `signal_to_raw_weights`
  - `build_weights_from_signals_over_time`
  - `build_optimized_weights_over_time`
  - `compute_portfolio_performance`

##### Callable `src.portfolio.construction:_apply_missing_return_policy`

- Signature: `def _apply_missing_return_policy(asset_returns: pd.DataFrame, prev_weights: pd.DataFrame, missing_return_policy: str) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `40`
- Σύνοψη λογικής: Resolve missing-return handling explicitly so live positions cannot inherit synthetic flat PnL from missing panel data.
- Παράμετροι:
  - `asset_returns` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Panel realized returns ανά asset και timestamp.
  - `prev_weights` (keyword-only, `pd.DataFrame`, default `χωρίς default`): Weights της προηγούμενης περιόδου για turnover/cost accounting.
  - `missing_return_policy` (keyword-only, `str`, default `χωρίς default`): Policy flag που καθοριζει edge-case handling και validation behavior.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.backtesting.engine:run_backtest`, `src.portfolio.construction:compute_portfolio_performance`

##### Callable `src.portfolio.construction:signal_to_raw_weights`

- Signature: `def signal_to_raw_weights(signal_t: pd.Series, long_short: bool = True, gross_target: float = 1.0) -> pd.Series`
- Return type: `pd.Series`
- LOC: `31`
- Σύνοψη λογικής: Handle signal to raw weights inside the portfolio construction layer.
- Παράμετροι:
  - `signal_t` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Cross-sectional σήματα μίας χρονικής στιγμής.
  - `long_short` (keyword-only, `bool`, default `True`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `gross_target` (keyword-only, `float`, default `1.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.construction:build_weights_from_signals_over_time`, `tests.test_portfolio:test_signal_to_raw_weights_keeps_missing_assets_flat`

##### Callable `src.portfolio.construction:build_weights_from_signals_over_time`

- Signature: `def build_weights_from_signals_over_time(signals: pd.DataFrame, constraints: PortfolioConstraints | None = None, asset_to_group: Mapping[str, str] | None = None, long_short: bool = True, gross_target: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]`
- Return type: `tuple[pd.DataFrame, pd.DataFrame]`
- LOC: `48`
- Σύνοψη λογικής: Build weights from signals over time as an explicit intermediate object used by the portfolio construction pipeline.
- Παράμετροι:
  - `signals` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Panel cross-sectional signals ανά asset και timestamp.
  - `constraints` (keyword-only, `PortfolioConstraints | None`, default `None`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `None`): Χαρτογράφηση asset -> group για exposure caps.
  - `long_short` (keyword-only, `bool`, default `True`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `gross_target` (keyword-only, `float`, default `1.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: O(T * A) συν το κόστος projection constraints ανά timestamp.
- Direct callers: `src.experiments.runner:_run_portfolio_backtest`, `tests.test_portfolio:test_build_weights_from_signals_over_time_respects_constraints`

##### Callable `src.portfolio.construction:build_optimized_weights_over_time`

- Signature: `def build_optimized_weights_over_time(expected_returns: pd.DataFrame, covariance_by_date: Mapping[pd.Timestamp, pd.DataFrame] | None = None, constraints: PortfolioConstraints | None = None, asset_to_group: Mapping[str, str] | None = None, risk_aversion: float = 5.0, trade_aversion: float = 0.0) -> tuple[pd.DataFrame, pd.DataFrame]`
- Return type: `tuple[pd.DataFrame, pd.DataFrame]`
- LOC: `52`
- Σύνοψη λογικής: Build optimized weights over time as an explicit intermediate object used by the portfolio construction pipeline.
- Παράμετροι:
  - `expected_returns` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Panel expected returns που τροφοδοτεί optimization ή portfolio construction.
  - `covariance_by_date` (keyword-only, `Mapping[pd.Timestamp, pd.DataFrame] | None`, default `None`): Rolling dictionary covariance matrices ανά ημερομηνία.
  - `constraints` (keyword-only, `PortfolioConstraints | None`, default `None`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `None`): Χαρτογράφηση asset -> group για exposure caps.
  - `risk_aversion` (keyword-only, `float`, default `5.0`): Συντελεστής ποινής variance στο mean-variance objective.
  - `trade_aversion` (keyword-only, `float`, default `0.0`): Συντελεστής ποινής turnover/μεταβολής weights στο optimization objective.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: O(T * optimize_mean_variance(A)), όπου T timestamps και A assets.
- Direct callers: `src.experiments.runner:_run_portfolio_backtest`

##### Callable `src.portfolio.construction:compute_portfolio_performance`

- Signature: `def compute_portfolio_performance(weights: pd.DataFrame, asset_returns: pd.DataFrame, missing_return_policy: str = 'raise_if_exposed', cost_per_turnover: float = 0.0, slippage_per_turnover: float = 0.0, periods_per_year: int = 252) -> PortfolioPerformance`
- Return type: `PortfolioPerformance`
- LOC: `61`
- Σύνοψη λογικής: Compute portfolio performance for the portfolio construction layer.
- Παράμετροι:
  - `weights` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): DataFrame weights χαρτοφυλακίου ανά ημερομηνία και asset.
  - `asset_returns` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Panel realized returns ανά asset και timestamp.
  - `missing_return_policy` (keyword-only, `str`, default `'raise_if_exposed'`): Policy flag που καθοριζει edge-case handling και validation behavior.
  - `cost_per_turnover` (keyword-only, `float`, default `0.0`): Κόστος συναλλαγής ανά μονάδα portfolio turnover.
  - `slippage_per_turnover` (keyword-only, `float`, default `0.0`): Υποτιθέμενο slippage ανά μονάδα portfolio turnover.
  - `periods_per_year` (keyword-only, `int`, default `252`): Annualization factor για returns και risk metrics.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: O(T * A) για alignment, turnover και portfolio return aggregation.
- Direct callers: `src.experiments.runner:_run_portfolio_backtest`, `tests.test_portfolio:test_compute_portfolio_performance_charges_initial_turnover`, `tests.test_portfolio:test_compute_portfolio_performance_raises_on_missing_exposed_return`, `tests.test_portfolio:test_compute_portfolio_performance_uses_shifted_weights`

#### Module `src/portfolio/covariance.py`

- Python module: `src.portfolio.covariance`
- Ρόλος: Portfolio construction
- LOC: `42`
- Imports: `__future__`, `pandas`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['build_rolling_covariance_by_date']`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `build_rolling_covariance_by_date`

##### Callable `src.portfolio.covariance:build_rolling_covariance_by_date`

- Signature: `def build_rolling_covariance_by_date(asset_returns: pd.DataFrame, window: int = 60, min_periods: int | None = None) -> dict[pd.Timestamp, pd.DataFrame]`
- Return type: `dict[pd.Timestamp, pd.DataFrame]`
- LOC: `32`
- Σύνοψη λογικής: Build rolling covariance by date as an explicit intermediate object used by the portfolio construction pipeline.
- Παράμετροι:
  - `asset_returns` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Panel realized returns ανά asset και timestamp.
  - `window` (keyword-only, `int`, default `60`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `min_periods` (keyword-only, `int | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Περίπου O(T * W * A^2), όπου W το rolling window και A ο αριθμός assets.
- Direct callers: `src.experiments.runner:_run_portfolio_backtest`

#### Module `src/portfolio/optimizer.py`

- Python module: `src.portfolio.optimizer`
- Ρόλος: Portfolio construction
- LOC: `212`
- Imports: `__future__`, `numpy`, `pandas`, `scipy.optimize`, `src.portfolio.constraints`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['optimize_mean_variance']`
- ASCII dependency sketch:
```text
[imports] __future__, numpy, pandas, scipy.optimize
      |
      v
[module] src.portfolio.optimizer
      |
      +-- functions: 4
      |
[inbound] src.portfolio.construction:build_optimized_weights_over_time, src.portfolio.optim...
```

- Classes: Καμία.

- Top-level callables:
  - `_prepare_covariance`
  - `_initial_weights`
  - `_fallback_weights`
  - `optimize_mean_variance`

##### Callable `src.portfolio.optimizer:_prepare_covariance`

- Signature: `def _prepare_covariance(assets: pd.Index, covariance: pd.DataFrame | None) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `16`
- Σύνοψη λογικής: Handle prepare covariance inside the portfolio construction layer.
- Παράμετροι:
  - `assets` (positional-or-keyword, `pd.Index`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `covariance` (positional-or-keyword, `pd.DataFrame | None`, default `χωρίς default`): Covariance matrix που χρησιμοποιείται στο optimization step.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.optimizer:optimize_mean_variance`

##### Callable `src.portfolio.optimizer:_initial_weights`

- Signature: `def _initial_weights(assets: pd.Index, constraints: PortfolioConstraints, prev_weights: pd.Series | None) -> np.ndarray`
- Return type: `np.ndarray`
- LOC: `22`
- Σύνοψη λογικής: Handle initial weights inside the portfolio construction layer.
- Παράμετροι:
  - `assets` (positional-or-keyword, `pd.Index`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `constraints` (keyword-only, `PortfolioConstraints`, default `χωρίς default`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `prev_weights` (keyword-only, `pd.Series | None`, default `χωρίς default`): Weights της προηγούμενης περιόδου για turnover/cost accounting.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.optimizer:optimize_mean_variance`

##### Callable `src.portfolio.optimizer:_fallback_weights`

- Signature: `def _fallback_weights(expected_returns: pd.Series, constraints: PortfolioConstraints) -> pd.Series`
- Return type: `pd.Series`
- LOC: `16`
- Σύνοψη λογικής: Build a deterministic fallback portfolio from centered expected returns when optimization is unavailable or infeasible.
- Παράμετροι:
  - `expected_returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Panel expected returns που τροφοδοτεί optimization ή portfolio construction.
  - `constraints` (keyword-only, `PortfolioConstraints`, default `χωρίς default`): Αντικείμενο περιορισμών χαρτοφυλακίου.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Εξαρταται απο το cross-sectional panel. Τυπικα τουλαχιστον O(T * A), με A αριθμο assets.
- Direct callers: `src.portfolio.optimizer:optimize_mean_variance`

##### Callable `src.portfolio.optimizer:optimize_mean_variance`

- Signature: `def optimize_mean_variance(expected_returns: pd.Series, covariance: pd.DataFrame | None = None, constraints: PortfolioConstraints | None = None, prev_weights: pd.Series | None = None, asset_to_group: Mapping[str, str] | None = None, risk_aversion: float = 5.0, trade_aversion: float = 0.0, allow_fallback: bool = True) -> tuple[pd.Series, dict[str, float | str | bool | dict[str, float]]]`
- Return type: `tuple[pd.Series, dict[str, float | str | bool | dict[str, float]]]`
- LOC: `138`
- Σύνοψη λογικής: Handle optimize mean variance inside the portfolio construction layer.
- Παράμετροι:
  - `expected_returns` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Panel expected returns που τροφοδοτεί optimization ή portfolio construction.
  - `covariance` (keyword-only, `pd.DataFrame | None`, default `None`): Covariance matrix που χρησιμοποιείται στο optimization step.
  - `constraints` (keyword-only, `PortfolioConstraints | None`, default `None`): Αντικείμενο περιορισμών χαρτοφυλακίου.
  - `prev_weights` (keyword-only, `pd.Series | None`, default `None`): Weights της προηγούμενης περιόδου για turnover/cost accounting.
  - `asset_to_group` (keyword-only, `Mapping[str, str] | None`, default `None`): Χαρτογράφηση asset -> group για exposure caps.
  - `risk_aversion` (keyword-only, `float`, default `5.0`): Συντελεστής ποινής variance στο mean-variance objective.
  - `trade_aversion` (keyword-only, `float`, default `0.0`): Συντελεστής ποινής turnover/μεταβολής weights στο optimization objective.
  - `allow_fallback` (keyword-only, `bool`, default `True`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Solver-dependent. Για dense covariance είναι πρακτικά υπερ-γραμμική ως προς τα assets και συχνά προσεγγίζει O(A^3).
- Direct callers: `src.portfolio.construction:build_optimized_weights_over_time`, `tests.test_portfolio:test_optimize_mean_variance_fallback_respects_max_gross_leverage`, `tests.test_portfolio:test_optimize_mean_variance_respects_core_constraints`

### 17.15 Package `src/risk`

- Ρόλος package: Risk controls
- Modules: `3`
- LOC: `113`
- Top-level callables: `4`
- Methods: `0`
- Classes: `0`

#### Module `src/risk/__init__.py`

- Python module: `src.risk`
- Ρόλος: Risk controls
- LOC: `9`
- Imports: `.controls`, `.position_sizing`
- Global constants / exported symbols:
  - `__all__` = `['compute_vol_target_leverage', 'scale_signal_by_vol', 'compute_drawdown', 'drawdown_cooloff_mult...`
- ASCII dependency sketch:
```text
[imports] .controls, .position_sizing
      |
      v
[module] src.risk
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/risk/controls.py`

- Python module: `src.risk.controls`
- Ρόλος: Risk controls
- LOC: `50`
- Imports: `__future__`, `pandas`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_drawdown`
  - `drawdown_cooloff_multiplier`

##### Callable `src.risk.controls:compute_drawdown`

- Signature: `def compute_drawdown(equity: pd.Series) -> pd.Series`
- Return type: `pd.Series`
- LOC: `11`
- Σύνοψη λογικής: Drawdown series from an equity curve.
- Παράμετροι:
  - `equity` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.risk.controls:drawdown_cooloff_multiplier`

##### Callable `src.risk.controls:drawdown_cooloff_multiplier`

- Signature: `def drawdown_cooloff_multiplier(equity: pd.Series, max_drawdown: float = 0.2, cooloff_bars: int = 20, min_exposure: float = 0.0) -> pd.Series`
- Return type: `pd.Series`
- LOC: `32`
- Σύνοψη λογικής: When drawdown exceeds max_drawdown, reduce exposure to min_exposure for the next cooloff_bars periods.
- Παράμετροι:
  - `equity` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `max_drawdown` (positional-or-keyword, `float`, default `0.2`): Κατώφλι drawdown πέρα από το οποίο ενεργοποιείται το προστατευτικό cooloff logic.
  - `cooloff_bars` (positional-or-keyword, `int`, default `20`): Αριθμός bars στους οποίους παραμένει ενεργός ο drawdown cooloff μηχανισμός.
  - `min_exposure` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.backtesting.engine:run_backtest`

#### Module `src/risk/position_sizing.py`

- Python module: `src.risk.position_sizing`
- Ρόλος: Risk controls
- LOC: `54`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_vol_target_leverage`
  - `scale_signal_by_vol`

##### Callable `src.risk.position_sizing:compute_vol_target_leverage`

- Signature: `def compute_vol_target_leverage(vol: pd.Series, target_vol: float, max_leverage: float = 3.0, min_leverage: float = 0.0, eps: float = 1e-08) -> pd.Series`
- Return type: `pd.Series`
- LOC: `18`
- Σύνοψη λογικής: Compute leverage to target a given volatility level.
- Παράμετροι:
  - `vol` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `target_vol` (positional-or-keyword, `float`, default `χωρίς default`): Στοχευμένη ετησιοποιημένη μεταβλητότητα που χρησιμοποιείται για leverage scaling.
  - `max_leverage` (positional-or-keyword, `float`, default `3.0`): Άνω όριο leverage/exposure που δεν επιτρέπεται να υπερβεί ο allocator/backtester.
  - `min_leverage` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `eps` (positional-or-keyword, `float`, default `1e-08`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.risk.position_sizing:scale_signal_by_vol`

##### Callable `src.risk.position_sizing:scale_signal_by_vol`

- Signature: `def scale_signal_by_vol(signal: pd.Series, vol: pd.Series, target_vol: float, max_leverage: float = 3.0, min_leverage: float = 0.0, eps: float = 1e-08) -> pd.Series`
- Return type: `pd.Series`
- LOC: `26`
- Σύνοψη λογικής: Scale a trading signal by volatility targeting leverage.
- Παράμετροι:
  - `signal` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `vol` (positional-or-keyword, `pd.Series`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `target_vol` (positional-or-keyword, `float`, default `χωρίς default`): Στοχευμένη ετησιοποιημένη μεταβλητότητα που χρησιμοποιείται για leverage scaling.
  - `max_leverage` (positional-or-keyword, `float`, default `3.0`): Άνω όριο leverage/exposure που δεν επιτρέπεται να υπερβεί ο allocator/backtester.
  - `min_leverage` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `eps` (positional-or-keyword, `float`, default `1e-08`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.backtesting.engine:run_backtest`, `src.backtesting.strategies:vol_targeted_signal`

### 17.16 Package `src/signals`

- Ρόλος package: Signal generation
- Modules: `6`
- LOC: `208`
- Top-level callables: `5`
- Methods: `0`
- Classes: `0`

#### Module `src/signals/__init__.py`

- Python module: `src.signals`
- Ρόλος: Signal generation
- LOC: `13`
- Imports: `.momentum_signal`, `.rsi_signal`, `.stochastic_signal`, `.trend_signal`, `.volatility_signal`
- Global constants / exported symbols:
  - `__all__` = `['compute_rsi_signal', 'compute_trend_state_signal', 'compute_momentum_signal', 'compute_stochast...`
- ASCII dependency sketch:
```text
[imports] .momentum_signal, .rsi_signal, .stochastic_signal, .trend_signal
      |
      v
[module] src.signals
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/signals/momentum_signal.py`

- Python module: `src.signals.momentum_signal`
- Ρόλος: Signal generation
- LOC: `40`
- Imports: `__future__`, `pandas`
- Global constants / exported symbols:
  - `_ALLOWED_MODES` = `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_momentum_signal`

##### Callable `src.signals.momentum_signal:compute_momentum_signal`

- Signature: `def compute_momentum_signal(df: pd.DataFrame, momentum_col: str, long_threshold: float = 0.0, short_threshold: float | None = None, signal_col: str = 'momentum_signal', mode: str = 'long_short_hold') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `32`
- Σύνοψη λογικής: Momentum signal from a precomputed momentum column.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `momentum_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `long_threshold` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `short_threshold` (positional-or-keyword, `float | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal_col` (positional-or-keyword, `str`, default `'momentum_signal'`): Όνομα στήλης signal exposure ή conviction sizing.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`, `ValueError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.backtesting.strategies:momentum_strategy`

#### Module `src/signals/rsi_signal.py`

- Python module: `src.signals.rsi_signal`
- Ρόλος: Signal generation
- LOC: `35`
- Imports: `__future__`, `pandas`
- Global constants / exported symbols:
  - `_ALLOWED_MODES` = `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_rsi_signal`

##### Callable `src.signals.rsi_signal:compute_rsi_signal`

- Signature: `def compute_rsi_signal(df: pd.DataFrame, rsi_col: str, buy_level: float, sell_level: float, signal_col: str = 'rsi_signal', mode: str = 'long_short_hold') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `28`
- Σύνοψη λογικής: Compute RSI signal for the signal generation layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `rsi_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `buy_level` (positional-or-keyword, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `sell_level` (positional-or-keyword, `float`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal_col` (positional-or-keyword, `str`, default `'rsi_signal'`): Όνομα στήλης signal exposure ή conviction sizing.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.backtesting.strategies:rsi_strategy`

#### Module `src/signals/stochastic_signal.py`

- Python module: `src.signals.stochastic_signal`
- Ρόλος: Signal generation
- LOC: `38`
- Imports: `__future__`, `pandas`
- Global constants / exported symbols:
  - `_ALLOWED_MODES` = `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_stochastic_signal`

##### Callable `src.signals.stochastic_signal:compute_stochastic_signal`

- Signature: `def compute_stochastic_signal(df: pd.DataFrame, k_col: str, buy_level: float = 20.0, sell_level: float = 80.0, signal_col: str = 'stochastic_signal', mode: str = 'long_short_hold') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `30`
- Σύνοψη λογικής: Stochastic signal from %K.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `k_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `buy_level` (positional-or-keyword, `float`, default `20.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `sell_level` (positional-or-keyword, `float`, default `80.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal_col` (positional-or-keyword, `str`, default `'stochastic_signal'`): Όνομα στήλης signal exposure ή conviction sizing.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`, `ValueError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.backtesting.strategies:stochastic_strategy`

#### Module `src/signals/trend_signal.py`

- Python module: `src.signals.trend_signal`
- Ρόλος: Signal generation
- LOC: `36`
- Imports: `__future__`, `pandas`
- Global constants / exported symbols:
  - `_ALLOWED_MODES` = `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_trend_state_signal`

##### Callable `src.signals.trend_signal:compute_trend_state_signal`

- Signature: `def compute_trend_state_signal(df: pd.DataFrame, state_col: str, signal_col: str = 'trend_state_signal', long_value: float = 1.0, flat_value: float = 0.0, short_value: float = -1.0, mode: str = 'long_short_hold') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `28`
- Σύνοψη λογικής: Long-only signal based on a trend state column.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `state_col` (positional-or-keyword, `str`, default `χωρίς default`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `signal_col` (positional-or-keyword, `str`, default `'trend_state_signal'`): Όνομα στήλης signal exposure ή conviction sizing.
  - `long_value` (positional-or-keyword, `float`, default `1.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `flat_value` (positional-or-keyword, `float`, default `0.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `short_value` (positional-or-keyword, `float`, default `-1.0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`, `ValueError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.backtesting.strategies:trend_state_signal`

#### Module `src/signals/volatility_signal.py`

- Python module: `src.signals.volatility_signal`
- Ρόλος: Signal generation
- LOC: `46`
- Imports: `__future__`, `pandas`
- Global constants / exported symbols:
  - `_ALLOWED_MODES` = `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `compute_volatility_regime_signal`

##### Callable `src.signals.volatility_signal:compute_volatility_regime_signal`

- Signature: `def compute_volatility_regime_signal(df: pd.DataFrame, vol_col: str, quantile: float = 0.5, signal_col: str = 'volatility_regime_signal', mode: str = 'long_short_hold', causal: bool = True) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `38`
- Σύνοψη λογικής: Long when volatility is at or below the specified quantile, short when above (if mode allows shorts).
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `vol_col` (positional-or-keyword, `str`, default `χωρίς default`): Όνομα στήλης volatility estimate για scaling ή targeting.
  - `quantile` (positional-or-keyword, `float`, default `0.5`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `signal_col` (positional-or-keyword, `str`, default `'volatility_regime_signal'`): Όνομα στήλης signal exposure ή conviction sizing.
  - `mode` (positional-or-keyword, `str`, default `'long_short_hold'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `causal` (positional-or-keyword, `bool`, default `True`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `KeyError`, `ValueError`
- Big-O: Συνήθως O(T) ως προς το μηκος της χρονοσειρας, επειδη βασιζεται σε vectorized pandas/numpy transforms.
- Direct callers: `src.backtesting.strategies:volatility_regime_strategy`, `tests.test_core:test_volatility_regime_signal_is_causal_by_default`

### 17.17 Package `src/src_data`

- Ρόλος package: Data ingestion / PIT / storage
- Modules: `9`
- LOC: `922`
- Top-level callables: `19`
- Methods: `3`
- Classes: `3`

#### Module `src/src_data/__init__.py`

- Python module: `src.src_data`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `38`
- Imports: `.loaders`, `.pit`, `.storage`, `.validation`
- Global constants / exported symbols:
  - `__all__` = `['load_ohlcv', 'load_ohlcv_panel', 'validate_ohlcv', 'align_ohlcv_timestamps', 'apply_corporate_a...`
- ASCII dependency sketch:
```text
[imports] .loaders, .pit, .storage, .validation
      |
      v
[module] src.src_data
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/src_data/loaders.py`

- Python module: `src.src_data.loaders`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `84`
- Imports: `__future__`, `pandas`, `src.src_data.providers.alphavantage`, `src.src_data.providers.yahoo`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `load_ohlcv`
  - `load_ohlcv_panel`

##### Callable `src.src_data.loaders:load_ohlcv`

- Signature: `def load_ohlcv(symbol: str, start: str | None = None, end: str | None = None, interval: str = '1d', source: Literal['yahoo', 'alpha'] = 'yahoo', api_key: Optional[str] = None) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `45`
- Σύνοψη λογικής: Parameters ---------- symbol : str Ticker (π.χ.
- Παράμετροι:
  - `symbol` (positional-or-keyword, `str`, default `χωρίς default`): Ticker ή asset identifier ενός χρηματοοικονομικού μέσου.
  - `start` (positional-or-keyword, `str | None`, default `None`): Χρονικό lower bound φόρτωσης ή split construction.
  - `end` (positional-or-keyword, `str | None`, default `None`): Χρονικό upper bound φόρτωσης ή split construction.
  - `interval` (positional-or-keyword, `str`, default `'1d'`): Συχνότητα δεδομένων, π.χ. `1d`, `1h` ή intraday interval.
  - `source` (positional-or-keyword, `Literal['yahoo', 'alpha']`, default `'yahoo'`): Provider/source δεδομένων αγοράς ή configuration source.
  - `api_key` (positional-or-keyword, `Optional[str]`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Διαβαζει δεδομενα ή snapshots απο filesystem/provider.
- Exceptions: `ValueError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:_load_asset_frames`, `src.src_data.loaders:load_ohlcv_panel`

##### Callable `src.src_data.loaders:load_ohlcv_panel`

- Signature: `def load_ohlcv_panel(symbols: Sequence[str], start: str | None = None, end: str | None = None, interval: str = '1d', source: Literal['yahoo', 'alpha'] = 'yahoo', api_key: Optional[str] = None) -> dict[str, pd.DataFrame]`
- Return type: `dict[str, pd.DataFrame]`
- LOC: `27`
- Σύνοψη λογικής: Load OHLCV panel for the data ingestion and storage layer and normalize it into the shape expected by the rest of the project.
- Παράμετροι:
  - `symbols` (positional-or-keyword, `Sequence[str]`, default `χωρίς default`): Λίστα tickers/asset identifiers για panel loading ή portfolio processing.
  - `start` (positional-or-keyword, `str | None`, default `None`): Χρονικό lower bound φόρτωσης ή split construction.
  - `end` (positional-or-keyword, `str | None`, default `None`): Χρονικό upper bound φόρτωσης ή split construction.
  - `interval` (positional-or-keyword, `str`, default `'1d'`): Συχνότητα δεδομένων, π.χ. `1d`, `1h` ή intraday interval.
  - `source` (positional-or-keyword, `Literal['yahoo', 'alpha']`, default `'yahoo'`): Provider/source δεδομένων αγοράς ή configuration source.
  - `api_key` (positional-or-keyword, `Optional[str]`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Διαβαζει δεδομενα ή snapshots απο filesystem/provider.
- Exceptions: `ValueError`
- Big-O: O(A * fetch(T)) ως προς assets και μέγεθος remote payload, συν latency provider.
- Direct callers: `src.experiments.runner:_load_asset_frames`

#### Module `src/src_data/pit.py`

- Python module: `src.src_data.pit`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `334`
- Imports: `__future__`, `numpy`, `pandas`, `pathlib`, `src.utils.paths`, `typing`
- Global constants / exported symbols:
  - `_ALLOWED_DUPLICATE_POLICIES` = `{'first', 'last', 'raise'}`
  - `_ALLOWED_CORP_ACTION_POLICIES` = `{'none', 'adj_close_ratio', 'adj_close_replace_close'}`
  - `_ALLOWED_UNIVERSE_INACTIVE_POLICIES` = `{'raise', 'drop_inactive_rows'}`
  - `__all__` = `['align_ohlcv_timestamps', 'apply_corporate_actions_policy', 'load_universe_snapshot', 'symbols_a...`
- ASCII dependency sketch:
```text
[imports] __future__, numpy, pandas, pathlib
      |
      v
[module] src.src_data.pit
      |
      +-- functions: 9
      |
[inbound] src.experiments.runner:_load_asset_frames, src.src_data.pit:apply_pit_hardening, ...
```

- Classes: Καμία.

- Top-level callables:
  - `align_ohlcv_timestamps`
  - `apply_corporate_actions_policy`
  - `_resolve_snapshot_path`
  - `load_universe_snapshot`
  - `symbols_active_in_snapshot`
  - `assert_symbol_in_snapshot`
  - `symbol_active_mask_over_time`
  - `enforce_symbol_membership_over_time`
  - `apply_pit_hardening`

##### Callable `src.src_data.pit:align_ohlcv_timestamps`

- Signature: `def align_ohlcv_timestamps(df: pd.DataFrame, source_timezone: str = 'UTC', output_timezone: str = 'UTC', normalize_daily: bool = True, duplicate_policy: str = 'last') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `40`
- Σύνοψη λογικής: Handle align OHLCV timestamps inside the data ingestion and storage layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `source_timezone` (keyword-only, `str`, default `'UTC'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `output_timezone` (keyword-only, `str`, default `'UTC'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `normalize_daily` (keyword-only, `bool`, default `True`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `duplicate_policy` (keyword-only, `str`, default `'last'`): Policy flag που καθοριζει edge-case handling και validation behavior.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.src_data.pit:apply_pit_hardening`, `tests.test_contracts_metrics_pit:test_align_ohlcv_timestamps_sorts_and_deduplicates`

##### Callable `src.src_data.pit:apply_corporate_actions_policy`

- Signature: `def apply_corporate_actions_policy(df: pd.DataFrame, policy: str = 'none', adj_close_col: str = 'adj_close', price_cols: Iterable[str] = ('open', 'high', 'low', 'close')) -> tuple[pd.DataFrame, dict[str, Any]]`
- Return type: `tuple[pd.DataFrame, dict[str, Any]]`
- LOC: `45`
- Σύνοψη λογικής: Apply corporate actions policy to the provided inputs in a controlled and reusable way.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `policy` (keyword-only, `str`, default `'none'`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `adj_close_col` (keyword-only, `str`, default `'adj_close'`): Ονομα στηλης pandas που χρησιμοποιειται για lookup ή παραγωγη derived column.
  - `price_cols` (keyword-only, `Iterable[str]`, default `('open', 'high', 'low', 'close')`): Λιστα στηλων pandas που συμμετεχουν σε transformation ή model fitting.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.src_data.pit:apply_pit_hardening`, `tests.test_contracts_metrics_pit:test_apply_corporate_actions_policy_adj_close_ratio`

##### Callable `src.src_data.pit:_resolve_snapshot_path`

- Signature: `def _resolve_snapshot_path(path: str | Path) -> Path`
- Return type: `Path`
- LOC: `10`
- Σύνοψη λογικής: Handle snapshot path inside the data ingestion and storage layer.
- Παράμετροι:
  - `path` (positional-or-keyword, `str | Path`, default `χωρίς default`): Filesystem path προς artifact, snapshot ή configuration.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.src_data.pit:apply_pit_hardening`, `src.src_data.pit:load_universe_snapshot`

##### Callable `src.src_data.pit:load_universe_snapshot`

- Signature: `def load_universe_snapshot(path: str | Path) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `33`
- Σύνοψη λογικής: Load universe snapshot for the data ingestion and storage layer and normalize it into the shape expected by the rest of the project.
- Παράμετροι:
  - `path` (positional-or-keyword, `str | Path`, default `χωρίς default`): Filesystem path προς artifact, snapshot ή configuration.
- Side effects: Διαβαζει δεδομενα ή snapshots απο filesystem/provider.
- Exceptions: `FileNotFoundError`, `ValueError`
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.src_data.pit:apply_pit_hardening`, `tests.test_contracts_metrics_pit:test_universe_snapshot_asof_membership_check`

##### Callable `src.src_data.pit:symbols_active_in_snapshot`

- Signature: `def symbols_active_in_snapshot(snapshot_df: pd.DataFrame, as_of: str | pd.Timestamp) -> list[str]`
- Return type: `list[str]`
- LOC: `15`
- Σύνοψη λογικής: Handle symbols active in snapshot inside the data ingestion and storage layer.
- Παράμετροι:
  - `snapshot_df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Universe snapshot ή άλλο PIT dataframe αναφοράς.
  - `as_of` (positional-or-keyword, `str | pd.Timestamp`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.src_data.pit:apply_pit_hardening`, `src.src_data.pit:assert_symbol_in_snapshot`

##### Callable `src.src_data.pit:assert_symbol_in_snapshot`

- Signature: `def assert_symbol_in_snapshot(symbol: str, snapshot_df: pd.DataFrame, as_of: str | pd.Timestamp) -> None`
- Return type: `None`
- LOC: `15`
- Σύνοψη λογικής: Assert symbol in snapshot before the pipeline proceeds.
- Παράμετροι:
  - `symbol` (positional-or-keyword, `str`, default `χωρίς default`): Ticker ή asset identifier ενός χρηματοοικονομικού μέσου.
  - `snapshot_df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Universe snapshot ή άλλο PIT dataframe αναφοράς.
  - `as_of` (keyword-only, `str | pd.Timestamp`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.src_data.pit:apply_pit_hardening`, `tests.test_contracts_metrics_pit:test_universe_snapshot_asof_membership_check`

##### Callable `src.src_data.pit:symbol_active_mask_over_time`

- Signature: `def symbol_active_mask_over_time(snapshot_df: pd.DataFrame, symbol: str, index: pd.DatetimeIndex) -> pd.Series`
- Return type: `pd.Series`
- LOC: `26`
- Σύνοψη λογικής: Build a per-timestamp membership mask for one symbol from a universe snapshot so PIT enforcement can validate the whole time series instead of only a single as-of date.
- Παράμετροι:
  - `snapshot_df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Universe snapshot ή άλλο PIT dataframe αναφοράς.
  - `symbol` (keyword-only, `str`, default `χωρίς default`): Ticker ή asset identifier ενός χρηματοοικονομικού μέσου.
  - `index` (keyword-only, `pd.DatetimeIndex`, default `χωρίς default`): DatetimeIndex ή γενικός index πάνω στον οποίο γίνεται ο μετασχηματισμός.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.src_data.pit:enforce_symbol_membership_over_time`

##### Callable `src.src_data.pit:enforce_symbol_membership_over_time`

- Signature: `def enforce_symbol_membership_over_time(df: pd.DataFrame, snapshot_df: pd.DataFrame, symbol: str, inactive_policy: str = 'raise') -> tuple[pd.DataFrame, dict[str, Any]]`
- Return type: `tuple[pd.DataFrame, dict[str, Any]]`
- LOC: `41`
- Σύνοψη λογικής: Enforce symbol membership across the entire dataframe index using the universe snapshot.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `snapshot_df` (keyword-only, `pd.DataFrame`, default `χωρίς default`): Universe snapshot ή άλλο PIT dataframe αναφοράς.
  - `symbol` (keyword-only, `str`, default `χωρίς default`): Ticker ή asset identifier ενός χρηματοοικονομικού μέσου.
  - `inactive_policy` (keyword-only, `str`, default `'raise'`): Policy flag που καθοριζει edge-case handling και validation behavior.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.src_data.pit:apply_pit_hardening`

##### Callable `src.src_data.pit:apply_pit_hardening`

- Signature: `def apply_pit_hardening(df: pd.DataFrame, pit_cfg: Mapping[str, Any] | None = None, symbol: str | None = None) -> tuple[pd.DataFrame, dict[str, Any]]`
- Return type: `tuple[pd.DataFrame, dict[str, Any]]`
- LOC: `66`
- Σύνοψη λογικής: Apply point-in-time (PIT) hardening to the provided inputs in a controlled and reusable way.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `pit_cfg` (keyword-only, `Mapping[str, Any] | None`, default `None`): Configuration block για point-in-time hardening.
  - `symbol` (keyword-only, `str | None`, default `None`): Ticker ή asset identifier ενός χρηματοοικονομικού μέσου.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.experiments.runner:_load_asset_frames`, `tests.test_contracts_metrics_pit:test_apply_pit_hardening_can_drop_rows_outside_universe_snapshot`, `tests.test_contracts_metrics_pit:test_apply_pit_hardening_raises_when_symbol_exits_universe_mid_sample`

#### Module `src/src_data/providers/__init__.py`

- Python module: `src.src_data.providers`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `9`
- Imports: `.alphavantage`, `.base`, `.yahoo`
- Global constants / exported symbols:
  - `__all__` = `['MarketDataProvider', 'YahooFinanceProvider', 'AlphaVantageFXProvider']`
- ASCII dependency sketch:
```text
[imports] .alphavantage, .base, .yahoo
      |
      v
[module] src.src_data.providers
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/src_data/providers/alphavantage.py`

- Python module: `src.src_data.providers.alphavantage`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `86`
- Imports: `__future__`, `dataclasses`, `os`, `pandas`, `requests`, `src.src_data.providers.base`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes στο module:
  - `AlphaVantageFXProvider`

##### Class `src.src_data.providers.alphavantage:AlphaVantageFXProvider`

- Βάσεις: `MarketDataProvider`
- LOC: `73`
- Σύνοψη ρόλου: Lightweight wrapper around Alpha Vantage FX_DAILY endpoint.
- Fields:
  - `api_key` (`Optional[str]`, default `None`)
  - `outputsize` (`Literal['compact', 'full']`, default `'full'`)
- Methods:
  - `get_ohlcv` -> `def get_ohlcv(self, symbol: str, start: str | None = None, end: str | None = None, interval: str = '1d') -> pd.DataFrame`

##### Callable `src.src_data.providers.alphavantage:AlphaVantageFXProvider.get_ohlcv`

- Signature: `def get_ohlcv(self, symbol: str, start: str | None = None, end: str | None = None, interval: str = '1d') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `63`
- Σύνοψη λογικής: Implement the get OHLCV step required by the surrounding class.
- Παράμετροι:
  - `self` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Αναφορά στο instance της κλάσης.
  - `symbol` (positional-or-keyword, `str`, default `χωρίς default`): Ticker ή asset identifier ενός χρηματοοικονομικού μέσου.
  - `start` (positional-or-keyword, `str | None`, default `None`): Χρονικό lower bound φόρτωσης ή split construction.
  - `end` (positional-or-keyword, `str | None`, default `None`): Χρονικό upper bound φόρτωσης ή split construction.
  - `interval` (positional-or-keyword, `str`, default `'1d'`): Συχνότητα δεδομένων, π.χ. `1d`, `1h` ή intraday interval.
- Side effects: Μπορει να προκαλεσει network I/O προς market data provider.
- Exceptions: `ValueError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.src_data.loaders:load_ohlcv`

- Top-level callables: Κανένα.

#### Module `src/src_data/providers/base.py`

- Python module: `src.src_data.providers.base`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `24`
- Imports: `__future__`, `abc`, `pandas`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes στο module:
  - `MarketDataProvider`

##### Class `src.src_data.providers.base:MarketDataProvider`

- Βάσεις: `ABC`
- LOC: `18`
- Σύνοψη ρόλου: Define the abstract provider interface that every market data backend must implement in order to return normalized OHLCV data.
- Fields: Δεν δηλώνονται explicit class/dataclass fields στο AST surface.
- Methods:
  - `get_ohlcv` -> `def get_ohlcv(self, symbol: str, start: str | None = None, end: str | None = None, interval: str = '1d') -> pd.DataFrame`

##### Callable `src.src_data.providers.base:MarketDataProvider.get_ohlcv`

- Signature: `def get_ohlcv(self, symbol: str, start: str | None = None, end: str | None = None, interval: str = '1d') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `11`
- Σύνοψη λογικής: Fetch OHLCV data
- Παράμετροι:
  - `self` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Αναφορά στο instance της κλάσης.
  - `symbol` (positional-or-keyword, `str`, default `χωρίς default`): Ticker ή asset identifier ενός χρηματοοικονομικού μέσου.
  - `start` (positional-or-keyword, `str | None`, default `None`): Χρονικό lower bound φόρτωσης ή split construction.
  - `end` (positional-or-keyword, `str | None`, default `None`): Χρονικό upper bound φόρτωσης ή split construction.
  - `interval` (positional-or-keyword, `str`, default `'1d'`): Συχνότητα δεδομένων, π.χ. `1d`, `1h` ή intraday interval.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `NotImplementedError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.src_data.loaders:load_ohlcv`

- Top-level callables: Κανένα.

#### Module `src/src_data/providers/yahoo.py`

- Python module: `src.src_data.providers.yahoo`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `79`
- Imports: `__future__`, `dataclasses`, `pandas`, `src.src_data.providers.base`, `yfinance`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes στο module:
  - `YahooFinanceProvider`

##### Class `src.src_data.providers.yahoo:YahooFinanceProvider`

- Βάσεις: `MarketDataProvider`
- LOC: `68`
- Σύνοψη ρόλου: Implement the market data provider contract for Yahoo Finance and normalize the downloaded columns into the project OHLCV schema.
- Fields: Δεν δηλώνονται explicit class/dataclass fields στο AST surface.
- Methods:
  - `get_ohlcv` -> `def get_ohlcv(self, symbol: str, start: str | None = None, end: str | None = None, interval: str = '1d') -> pd.DataFrame`

##### Callable `src.src_data.providers.yahoo:YahooFinanceProvider.get_ohlcv`

- Signature: `def get_ohlcv(self, symbol: str, start: str | None = None, end: str | None = None, interval: str = '1d') -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `62`
- Σύνοψη λογικής: Implement the get OHLCV step required by the surrounding class.
- Παράμετροι:
  - `self` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Αναφορά στο instance της κλάσης.
  - `symbol` (positional-or-keyword, `str`, default `χωρίς default`): Ticker ή asset identifier ενός χρηματοοικονομικού μέσου.
  - `start` (positional-or-keyword, `str | None`, default `None`): Χρονικό lower bound φόρτωσης ή split construction.
  - `end` (positional-or-keyword, `str | None`, default `None`): Χρονικό upper bound φόρτωσης ή split construction.
  - `interval` (positional-or-keyword, `str`, default `'1d'`): Συχνότητα δεδομένων, π.χ. `1d`, `1h` ή intraday interval.
- Side effects: Μπορει να προκαλεσει network I/O προς market data provider.
- Exceptions: `ValueError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.src_data.loaders:load_ohlcv`

- Top-level callables: Κανένα.

#### Module `src/src_data/storage.py`

- Python module: `src.src_data.storage`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `208`
- Imports: `__future__`, `datetime`, `json`, `pandas`, `pathlib`, `src.utils.paths`, `src.utils.run_metadata`, `typing`
- Global constants / exported symbols:
  - `__all__` = `['asset_frames_to_long_frame', 'long_frame_to_asset_frames', 'build_dataset_snapshot_metadata', '...`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `_resolve_path`
  - `_resolve_snapshot_dir`
  - `asset_frames_to_long_frame`
  - `long_frame_to_asset_frames`
  - `build_dataset_snapshot_metadata`
  - `save_dataset_snapshot`
  - `load_dataset_snapshot`

##### Callable `src.src_data.storage:_resolve_path`

- Signature: `def _resolve_path(path: str | Path) -> Path`
- Return type: `Path`
- LOC: `9`
- Σύνοψη λογικής: Handle path inside the data ingestion and storage layer.
- Παράμετροι:
  - `path` (positional-or-keyword, `str | Path`, default `χωρίς default`): Filesystem path προς artifact, snapshot ή configuration.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(R) ως προς τα rows που γινονται serialize/deserialize.
- Direct callers: `src.src_data.storage:_resolve_snapshot_dir`, `src.src_data.storage:load_dataset_snapshot`

##### Callable `src.src_data.storage:_resolve_snapshot_dir`

- Signature: `def _resolve_snapshot_dir(root_dir: str | Path, stage: str, dataset_id: str) -> Path`
- Return type: `Path`
- LOC: `14`
- Σύνοψη λογικής: Handle snapshot dir inside the data ingestion and storage layer.
- Παράμετροι:
  - `root_dir` (keyword-only, `str | Path`, default `χωρίς default`): Filesystem path για read/write artifact handling.
  - `stage` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `dataset_id` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(R) ως προς τα rows που γινονται serialize/deserialize.
- Direct callers: `src.src_data.storage:load_dataset_snapshot`, `src.src_data.storage:save_dataset_snapshot`

##### Callable `src.src_data.storage:asset_frames_to_long_frame`

- Signature: `def asset_frames_to_long_frame(asset_frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `26`
- Σύνοψη λογικής: Handle asset frames to long frame inside the data ingestion and storage layer.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `Mapping[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Γενικα O(R) ως προς τα rows που γινονται serialize/deserialize.
- Direct callers: `src.experiments.runner:_data_stats_payload`, `src.experiments.runner:run_experiment`, `src.src_data.storage:build_dataset_snapshot_metadata`, `src.src_data.storage:save_dataset_snapshot`

##### Callable `src.src_data.storage:long_frame_to_asset_frames`

- Signature: `def long_frame_to_asset_frames(frame: pd.DataFrame) -> dict[str, pd.DataFrame]`
- Return type: `dict[str, pd.DataFrame]`
- LOC: `17`
- Σύνοψη λογικής: Handle long frame to asset frames inside the data ingestion and storage layer.
- Παράμετροι:
  - `frame` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Γενικα O(R) ως προς τα rows που γινονται serialize/deserialize.
- Direct callers: `src.src_data.storage:load_dataset_snapshot`

##### Callable `src.src_data.storage:build_dataset_snapshot_metadata`

- Signature: `def build_dataset_snapshot_metadata(asset_frames: Mapping[str, pd.DataFrame], dataset_id: str, stage: str, context: Mapping[str, Any] | None = None) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `28`
- Σύνοψη λογικής: Build dataset snapshot metadata as an explicit intermediate object used by the data ingestion and storage pipeline.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `Mapping[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `dataset_id` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `stage` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `context` (keyword-only, `Mapping[str, Any] | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(R) ως προς τα rows που γινονται serialize/deserialize.
- Direct callers: `src.src_data.storage:save_dataset_snapshot`

##### Callable `src.src_data.storage:save_dataset_snapshot`

- Signature: `def save_dataset_snapshot(asset_frames: Mapping[str, pd.DataFrame], dataset_id: str, stage: str, root_dir: str | Path, context: Mapping[str, Any] | None = None) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `41`
- Σύνοψη λογικής: Save dataset snapshot for the data ingestion and storage layer together with the metadata needed to reproduce or inspect the generated artifact later.
- Παράμετροι:
  - `asset_frames` (positional-or-keyword, `Mapping[str, pd.DataFrame]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `dataset_id` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `stage` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `root_dir` (keyword-only, `str | Path`, default `χωρίς default`): Filesystem path για read/write artifact handling.
  - `context` (keyword-only, `Mapping[str, Any] | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Γραφει artifacts/snapshots στο filesystem.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(R) ως προς τα rows που γράφονται σε parquet/csv/json metadata.
- Direct callers: `src.experiments.runner:_load_asset_frames`, `src.experiments.runner:_save_processed_snapshot_if_enabled`, `tests.test_runner_extensions:test_dataset_snapshot_roundtrip`, `tests.test_runner_extensions:test_load_asset_frames_rejects_cached_snapshot_with_mismatched_pit_context`

##### Callable `src.src_data.storage:load_dataset_snapshot`

- Signature: `def load_dataset_snapshot(stage: str, root_dir: str | Path | None = None, dataset_id: str | None = None, load_path: str | Path | None = None) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]`
- Return type: `tuple[dict[str, pd.DataFrame], dict[str, Any]]`
- LOC: `39`
- Σύνοψη λογικής: Load dataset snapshot for the data ingestion and storage layer and normalize it into the shape expected by the rest of the project.
- Παράμετροι:
  - `stage` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `root_dir` (keyword-only, `str | Path | None`, default `None`): Filesystem path για read/write artifact handling.
  - `dataset_id` (keyword-only, `str | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `load_path` (keyword-only, `str | Path | None`, default `None`): Filesystem path για read/write artifact handling.
- Side effects: Διαβαζει δεδομενα ή snapshots απο filesystem/provider.
- Exceptions: `FileNotFoundError`, `ValueError`
- Big-O: O(R) ως προς τα rows που διαβάζονται από persisted snapshot.
- Direct callers: `src.experiments.runner:_load_asset_frames`, `tests.test_runner_extensions:test_dataset_snapshot_roundtrip`

#### Module `src/src_data/validation.py`

- Python module: `src.src_data.validation`
- Ρόλος: Data ingestion / PIT / storage
- LOC: `60`
- Imports: `__future__`, `numpy`, `pandas`, `typing`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `validate_ohlcv`

##### Callable `src.src_data.validation:validate_ohlcv`

- Signature: `def validate_ohlcv(df: pd.DataFrame, required_columns: Iterable[str] = ('open', 'high', 'low', 'close', 'volume'), allow_missing_volume: bool = True) -> None`
- Return type: `None`
- LOC: `52`
- Σύνοψη λογικής: Validate OHLCV before downstream logic depends on it.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
  - `required_columns` (positional-or-keyword, `Iterable[str]`, default `('open', 'high', 'low', 'close', 'volume')`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `allow_missing_volume` (positional-or-keyword, `bool`, default `True`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ValueError`
- Big-O: Συνήθως O(T) ως προς τα rows του input dataframe.
- Direct callers: `src.experiments.runner:_load_asset_frames`, `tests.test_core:test_validate_ohlcv_flags_invalid_high_low`, `tests.test_core:test_validate_ohlcv_rejects_missing_core_prices`

### 17.18 Package `src/utils`

- Ρόλος package: Infrastructure utilities
- Modules: `5`
- LOC: `1119`
- Top-level callables: `41`
- Methods: `0`
- Classes: `2`

#### Module `src/utils/__init__.py`

- Python module: `src.utils`
- Ρόλος: Infrastructure utilities
- LOC: `0`
- Imports: Δεν υπάρχουν imports.
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] none
      |
      v
[module] src.utils
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `src/utils/config.py`

- Python module: `src.utils.config`
- Ρόλος: Infrastructure utilities
- LOC: `613`
- Imports: `__future__`, `os`, `pathlib`, `src.utils.paths`, `src.utils.repro`, `typing`, `yaml`
- Global constants / exported symbols:
  - `__all__` = `['ConfigError', '_resolve_config_path', 'load_experiment_config']`
- ASCII dependency sketch:
```text
[imports] __future__, os, pathlib, src.utils.paths
      |
      v
[module] src.utils.config
      |
      +-- functions: 23
      |
      +-- classes: 1
      |
[inbound] src.experiments.runner:run_experiment, src.utils.config:_deep_update, src.utils.c...
```

- Classes στο module:
  - `ConfigError`

##### Class `src.utils.config:ConfigError`

- Βάσεις: `ValueError`
- LOC: `2`
- Σύνοψη ρόλου: Raised for invalid or inconsistent experiment configs.
- Fields: Δεν δηλώνονται explicit class/dataclass fields στο AST surface.
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

- Top-level callables:
  - `_default_normalize_daily_for_interval`
  - `_resolve_config_path`
  - `_load_yaml`
  - `_deep_update`
  - `_load_with_extends`
  - `_default_risk_block`
  - `_default_data_block`
  - `_default_backtest_block`
  - `_default_portfolio_block`
  - `_default_monitoring_block`
  - `_default_execution_block`
  - `_resolve_logging_block`
  - `_validate_data_block`
  - `_inject_api_key_from_env`
  - `_validate_features_block`
  - `_validate_model_block`
  - `_validate_signals_block`
  - `_validate_risk_block`
  - `_validate_backtest_block`
  - `_validate_portfolio_block`
  - `_validate_monitoring_block`
  - `_validate_execution_block`
  - `load_experiment_config`

##### Callable `src.utils.config:_default_normalize_daily_for_interval`

- Signature: `def _default_normalize_daily_for_interval(interval: str) -> bool`
- Return type: `bool`
- LOC: `6`
- Σύνοψη λογικής: Infer a safe timestamp-normalization default from the configured data interval.
- Παράμετροι:
  - `interval` (positional-or-keyword, `str`, default `χωρίς default`): Συχνότητα δεδομένων, π.χ. `1d`, `1h` ή intraday interval.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:_default_data_block`

##### Callable `src.utils.config:_resolve_config_path`

- Signature: `def _resolve_config_path(config_path: str | Path) -> Path`
- Return type: `Path`
- LOC: `14`
- Σύνοψη λογικής: Resolve a config path relative to CONFIG_DIR and verify it exists.
- Παράμετροι:
  - `config_path` (positional-or-keyword, `str | Path`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`, `FileNotFoundError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:_load_with_extends`, `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_load_yaml`

- Signature: `def _load_yaml(path: Path) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `10`
- Σύνοψη λογικής: Handle YAML inside the infrastructure layer.
- Παράμετροι:
  - `path` (positional-or-keyword, `Path`, default `χωρίς default`): Filesystem path προς artifact, snapshot ή configuration.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:_load_with_extends`

##### Callable `src.utils.config:_deep_update`

- Signature: `def _deep_update(base: Mapping[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `9`
- Σύνοψη λογικής: Recursively merge mappings; lists and scalars are overwritten.
- Παράμετροι:
  - `base` (positional-or-keyword, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `updates` (positional-or-keyword, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:_deep_update`, `src.utils.config:_load_with_extends`

##### Callable `src.utils.config:_load_with_extends`

- Signature: `def _load_with_extends(path: Path, seen: set[Path] | None = None) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `19`
- Σύνοψη λογικής: Handle with extends inside the infrastructure layer.
- Παράμετροι:
  - `path` (positional-or-keyword, `Path`, default `χωρίς default`): Filesystem path προς artifact, snapshot ή configuration.
  - `seen` (positional-or-keyword, `set[Path] | None`, default `None`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:_load_with_extends`, `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_default_risk_block`

- Signature: `def _default_risk_block(risk: dict[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `17`
- Σύνοψη λογικής: Handle default risk block inside the infrastructure layer.
- Παράμετροι:
  - `risk` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_default_data_block`

- Signature: `def _default_data_block(data: dict[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `50`
- Σύνοψη λογικής: Handle default data block inside the infrastructure layer.
- Παράμετροι:
  - `data` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_default_backtest_block`

- Signature: `def _default_backtest_block(backtest: dict[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `11`
- Σύνοψη λογικής: Handle default backtest block inside the infrastructure layer.
- Παράμετροι:
  - `backtest` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_default_portfolio_block`

- Signature: `def _default_portfolio_block(portfolio: dict[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `18`
- Σύνοψη λογικής: Handle default portfolio block inside the infrastructure layer.
- Παράμετροι:
  - `portfolio` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_default_monitoring_block`

- Signature: `def _default_monitoring_block(monitoring: dict[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `11`
- Σύνοψη λογικής: Handle default monitoring block inside the infrastructure layer.
- Παράμετροι:
  - `monitoring` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_default_execution_block`

- Signature: `def _default_execution_block(execution: dict[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `14`
- Σύνοψη λογικής: Handle default execution block inside the infrastructure layer.
- Παράμετροι:
  - `execution` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_resolve_logging_block`

- Signature: `def _resolve_logging_block(logging_cfg: dict[str, Any], config_path: Path) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `11`
- Σύνοψη λογικής: Handle logging block inside the infrastructure layer.
- Παράμετροι:
  - `logging_cfg` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Configuration block με δηλωτικες παραμετρους για το συγκεκριμενο subsystem.
  - `config_path` (positional-or-keyword, `Path`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_data_block`

- Signature: `def _validate_data_block(data: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `100`
- Σύνοψη λογικής: Handle data block inside the infrastructure layer.
- Παράμετροι:
  - `data` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_inject_api_key_from_env`

- Signature: `def _inject_api_key_from_env(data: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `9`
- Σύνοψη λογικής: Handle inject API key from env inside the infrastructure layer.
- Παράμετροι:
  - `data` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_features_block`

- Signature: `def _validate_features_block(features: Any) -> None`
- Return type: `None`
- LOC: `14`
- Σύνοψη λογικής: Handle features block inside the infrastructure layer.
- Παράμετροι:
  - `features` (positional-or-keyword, `Any`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_model_block`

- Signature: `def _validate_model_block(model: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `84`
- Σύνοψη λογικής: Handle model block inside the infrastructure layer.
- Παράμετροι:
  - `model` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Estimator instance ή aggregate object που επιστρέφεται από το training layer.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_signals_block`

- Signature: `def _validate_signals_block(signals: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `9`
- Σύνοψη λογικής: Handle signals block inside the infrastructure layer.
- Παράμετροι:
  - `signals` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Panel cross-sectional signals ανά asset και timestamp.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_risk_block`

- Signature: `def _validate_risk_block(risk: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `24`
- Σύνοψη λογικής: Handle risk block inside the infrastructure layer.
- Παράμετροι:
  - `risk` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_backtest_block`

- Signature: `def _validate_backtest_block(backtest: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `19`
- Σύνοψη λογικής: Handle backtest block inside the infrastructure layer.
- Παράμετροι:
  - `backtest` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_portfolio_block`

- Signature: `def _validate_portfolio_block(portfolio: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `31`
- Σύνοψη λογικής: Handle portfolio block inside the infrastructure layer.
- Παράμετροι:
  - `portfolio` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_monitoring_block`

- Signature: `def _validate_monitoring_block(monitoring: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `12`
- Σύνοψη λογικής: Handle monitoring block inside the infrastructure layer.
- Παράμετροι:
  - `monitoring` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:_validate_execution_block`

- Signature: `def _validate_execution_block(execution: dict[str, Any]) -> None`
- Return type: `None`
- LOC: `17`
- Σύνοψη λογικής: Handle execution block inside the infrastructure layer.
- Παράμετροι:
  - `execution` (positional-or-keyword, `dict[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.utils.config:load_experiment_config`

##### Callable `src.utils.config:load_experiment_config`

- Signature: `def load_experiment_config(config_path: str | Path) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `37`
- Σύνοψη λογικής: Load an experiment YAML, apply inheritance, defaults, validation, and resolve logging paths.
- Παράμετροι:
  - `config_path` (positional-or-keyword, `str | Path`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Διαβαζει δεδομενα ή snapshots απο filesystem/provider.
- Exceptions: `ConfigError`
- Big-O: O(K) ως προς το μεγεθος του YAML tree και των nested blocks.
- Direct callers: `src.experiments.runner:run_experiment`, `tests.test_contracts_metrics_pit:test_intraday_configs_do_not_normalize_timestamps_by_default`, `tests.test_reproducibility:test_compute_config_hash_ignores_config_path_field`, `tests.test_reproducibility:test_runtime_defaults_are_loaded_from_config`

#### Module `src/utils/paths.py`

- Python module: `src.utils.paths`
- Ρόλος: Infrastructure utilities
- LOC: `63`
- Imports: `__future__`, `pathlib`
- Global constants / exported symbols:
  - `_THIS_FILE` = `Path(__file__).resolve()`
  - `PROJECT_ROOT` = `_THIS_FILE.parents[2]`
  - `SRC_DIR` = `PROJECT_ROOT / 'src'`
  - `CONFIG_DIR` = `PROJECT_ROOT / 'config'`
  - `DATA_DIR` = `PROJECT_ROOT / 'data'`
  - `RAW_DATA_DIR` = `DATA_DIR / 'raw'`
  - `PROCESSED_DATA_DIR` = `DATA_DIR / 'processed'`
  - `METADATA_DIR` = `DATA_DIR / 'metadata'`
  - `NOTEBOOKS_DIR` = `PROJECT_ROOT / 'notebooks'`
  - `LOGS_DIR` = `PROJECT_ROOT / 'logs'`
  - `TESTS_DIR` = `PROJECT_ROOT / 'tests'`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `in_project`
  - `ensure_directories_exist`
  - `describe_paths`

##### Callable `src.utils.paths:in_project`

- Signature: `def in_project(*parts: str | Path) -> Path`
- Return type: `Path`
- LOC: `6`
- Σύνοψη λογικής: Handle in project inside the infrastructure layer.
- Παράμετροι:
  - `parts` (var-positional, `str | Path`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:run_experiment`, `src.utils.config:_default_data_block`, `src.utils.config:_resolve_logging_block`

##### Callable `src.utils.paths:ensure_directories_exist`

- Signature: `def ensure_directories_exist() -> None`
- Return type: `None`
- LOC: `17`
- Σύνοψη λογικής: Handle ensure directories exist inside the infrastructure layer.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Γραφει artifacts/snapshots στο filesystem.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.utils.paths:describe_paths`

- Signature: `def describe_paths() -> None`
- Return type: `None`
- LOC: `16`
- Σύνοψη λογικής: Describe paths for quick inspection while working inside the infrastructure layer.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `src/utils/repro.py`

- Python module: `src.utils.repro`
- Ρόλος: Infrastructure utilities
- LOC: `149`
- Imports: `__future__`, `numpy`, `os`, `random`, `typing`
- Global constants / exported symbols:
  - `_ALLOWED_REPRO_MODES` = `{'strict', 'relaxed'}`
  - `_THREAD_ENV_VARS` = `('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR...`
  - `__all__` = `['RuntimeConfigError', 'normalize_runtime_config', 'validate_runtime_config', 'apply_runtime_repr...`
- ASCII dependency sketch:
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

- Classes στο module:
  - `RuntimeConfigError`

##### Class `src.utils.repro:RuntimeConfigError`

- Βάσεις: `ValueError`
- LOC: `2`
- Σύνοψη ρόλου: Raised for invalid runtime/reproducibility configuration.
- Fields: Δεν δηλώνονται explicit class/dataclass fields στο AST surface.
- Methods: Δεν υπάρχουν methods πέρα από inherited behavior.

- Top-level callables:
  - `normalize_runtime_config`
  - `validate_runtime_config`
  - `apply_runtime_reproducibility`

##### Callable `src.utils.repro:normalize_runtime_config`

- Signature: `def normalize_runtime_config(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `12`
- Σύνοψη λογικής: Normalize runtime config into a canonical representation used throughout the infrastructure layer.
- Παράμετροι:
  - `runtime_cfg` (positional-or-keyword, `Mapping[str, Any] | None`, default `χωρίς default`): Configuration block για reproducibility, seeds και threads.
- Side effects: Επηρεαζει global reproducibility state (random seeds / περιβαλλον εκτελεσης).
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.utils.repro:validate_runtime_config`

##### Callable `src.utils.repro:validate_runtime_config`

- Signature: `def validate_runtime_config(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `32`
- Σύνοψη λογικής: Validate runtime config before downstream logic depends on it.
- Παράμετροι:
  - `runtime_cfg` (positional-or-keyword, `Mapping[str, Any] | None`, default `χωρίς default`): Configuration block για reproducibility, seeds και threads.
- Side effects: Επηρεαζει global reproducibility state (random seeds / περιβαλλον εκτελεσης).
- Exceptions: `RuntimeConfigError`
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.utils.config:load_experiment_config`, `src.utils.repro:apply_runtime_reproducibility`, `tests.test_reproducibility:test_validate_runtime_config_rejects_invalid_threads`

##### Callable `src.utils.repro:apply_runtime_reproducibility`

- Signature: `def apply_runtime_reproducibility(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `71`
- Σύνοψη λογικής: Apply runtime reproducibility to the provided inputs in a controlled and reusable way.
- Παράμετροι:
  - `runtime_cfg` (positional-or-keyword, `Mapping[str, Any] | None`, default `χωρίς default`): Configuration block για reproducibility, seeds και threads.
- Side effects: Επηρεαζει global reproducibility state (random seeds / περιβαλλον εκτελεσης).
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `src.experiments.runner:run_experiment`, `tests.test_reproducibility:test_apply_runtime_reproducibility_sets_deterministic_numpy_stream`

#### Module `src/utils/run_metadata.py`

- Python module: `src.utils.run_metadata`
- Ρόλος: Infrastructure utilities
- LOC: `294`
- Imports: `__future__`, `copy`, `datetime`, `hashlib`, `importlib.metadata`, `json`, `numpy`, `pandas`, `pathlib`, `platform`, `src.utils.paths`, `subprocess`, `sys`, `typing`
- Global constants / exported symbols:
  - `_KEY_PACKAGES` = `('numpy', 'pandas', 'scikit-learn', 'lightgbm', 'pyyaml', 'yfinance', 'requests')`
  - `__all__` = `['canonical_json_dumps', 'compute_config_hash', 'compute_dataframe_fingerprint', 'collect_git_met...`
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `_normalize_path_string`
  - `_normalize_for_hash`
  - `_json_default`
  - `canonical_json_dumps`
  - `compute_config_hash`
  - `compute_dataframe_fingerprint`
  - `_safe_git`
  - `collect_git_metadata`
  - `collect_environment_metadata`
  - `build_run_metadata`
  - `file_sha256`
  - `build_artifact_manifest`

##### Callable `src.utils.run_metadata:_normalize_path_string`

- Signature: `def _normalize_path_string(value: str, project_root: Path) -> str`
- Return type: `str`
- LOC: `13`
- Σύνοψη λογικής: Handle path string inside the infrastructure layer.
- Παράμετροι:
  - `value` (positional-or-keyword, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `project_root` (positional-or-keyword, `Path`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.utils.run_metadata:_normalize_for_hash`

##### Callable `src.utils.run_metadata:_normalize_for_hash`

- Signature: `def _normalize_for_hash(value: Any, project_root: Path) -> Any`
- Return type: `Any`
- LOC: `31`
- Σύνοψη λογικής: Handle for hash inside the infrastructure layer.
- Παράμετροι:
  - `value` (positional-or-keyword, `Any`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `project_root` (positional-or-keyword, `Path`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.utils.run_metadata:_normalize_for_hash`, `src.utils.run_metadata:compute_config_hash`

##### Callable `src.utils.run_metadata:_json_default`

- Signature: `def _json_default(value: Any) -> Any`
- Return type: `Any`
- LOC: `16`
- Σύνοψη λογικής: Handle JSON default inside the infrastructure layer.
- Παράμετροι:
  - `value` (positional-or-keyword, `Any`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `src.utils.run_metadata:canonical_json_dumps`

- Signature: `def canonical_json_dumps(payload: Mapping[str, Any]) -> str`
- Return type: `str`
- LOC: `6`
- Σύνοψη λογικής: Handle canonical JSON dumps inside the infrastructure layer.
- Παράμετροι:
  - `payload` (positional-or-keyword, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.utils.run_metadata:compute_config_hash`

##### Callable `src.utils.run_metadata:compute_config_hash`

- Signature: `def compute_config_hash(cfg: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> tuple[str, dict[str, Any]]`
- Return type: `tuple[str, dict[str, Any]]`
- LOC: `9`
- Σύνοψη λογικής: Compute config hash for the infrastructure layer.
- Παράμετροι:
  - `cfg` (positional-or-keyword, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `project_root` (positional-or-keyword, `Path`, default `PROJECT_ROOT`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.experiments.runner:run_experiment`, `tests.test_reproducibility:test_compute_config_hash_ignores_config_path_field`

##### Callable `src.utils.run_metadata:compute_dataframe_fingerprint`

- Signature: `def compute_dataframe_fingerprint(df: pd.DataFrame) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `42`
- Σύνοψη λογικής: Compute dataframe fingerprint for the infrastructure layer.
- Παράμετροι:
  - `df` (positional-or-keyword, `pd.DataFrame`, default `χωρίς default`): Είσοδος DataFrame με χρονοσειρές αγοράς, features ή ενδιάμεσα artifacts.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: `TypeError`, `ValueError`
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.experiments.runner:run_experiment`, `src.src_data.storage:build_dataset_snapshot_metadata`, `tests.test_reproducibility:test_dataframe_fingerprint_is_stable_across_row_and_column_order`

##### Callable `src.utils.run_metadata:_safe_git`

- Signature: `def _safe_git(args: list[str]) -> str | None`
- Return type: `str | None`
- LOC: `19`
- Σύνοψη λογικής: Handle safe Git inside the infrastructure layer.
- Παράμετροι:
  - `args` (positional-or-keyword, `list[str]`, default `χωρίς default`): Variadic παραμετροι που προωθουνται σε χαμηλοτερο API surface.
- Side effects: Εκτελει subprocess calls για metadata συλλογη.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.utils.run_metadata:collect_git_metadata`

##### Callable `src.utils.run_metadata:collect_git_metadata`

- Signature: `def collect_git_metadata() -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `14`
- Σύνοψη λογικής: Collect Git metadata from the local environment and package it into a stable structure for reporting or reproducibility.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.utils.run_metadata:build_run_metadata`

##### Callable `src.utils.run_metadata:collect_environment_metadata`

- Signature: `def collect_environment_metadata() -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `19`
- Σύνοψη λογικής: Collect environment metadata from the local environment and package it into a stable structure for reporting or reproducibility.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.utils.run_metadata:build_run_metadata`

##### Callable `src.utils.run_metadata:build_run_metadata`

- Signature: `def build_run_metadata(config_path: str | Path, runtime_applied: Mapping[str, Any], config_hash_sha256: str, config_hash_input: Mapping[str, Any], data_fingerprint: Mapping[str, Any], data_context: Mapping[str, Any], model_meta: Mapping[str, Any]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `30`
- Σύνοψη λογικής: Build run metadata as an explicit intermediate object used by the infrastructure pipeline.
- Παράμετροι:
  - `config_path` (keyword-only, `str | Path`, default `χωρίς default`): Filesystem path για read/write artifact handling.
  - `runtime_applied` (keyword-only, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `config_hash_sha256` (keyword-only, `str`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `config_hash_input` (keyword-only, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `data_fingerprint` (keyword-only, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `data_context` (keyword-only, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `model_meta` (keyword-only, `Mapping[str, Any]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.experiments.runner:run_experiment`

##### Callable `src.utils.run_metadata:file_sha256`

- Signature: `def file_sha256(path: str | Path) -> str`
- Return type: `str`
- LOC: `11`
- Σύνοψη λογικής: Handle file sha256 inside the infrastructure layer.
- Παράμετροι:
  - `path` (positional-or-keyword, `str | Path`, default `χωρίς default`): Filesystem path προς artifact, snapshot ή configuration.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.utils.run_metadata:build_artifact_manifest`

##### Callable `src.utils.run_metadata:build_artifact_manifest`

- Signature: `def build_artifact_manifest(artifacts: Mapping[str, str | Path]) -> dict[str, Any]`
- Return type: `dict[str, Any]`
- LOC: `21`
- Σύνοψη λογικής: Build artifact manifest as an explicit intermediate object used by the infrastructure pipeline.
- Παράμετροι:
  - `artifacts` (positional-or-keyword, `Mapping[str, str | Path]`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Γενικα O(F) ως προς files/metadata entries που γινονται hash ή inspect.
- Direct callers: `src.experiments.runner:_save_artifacts`, `tests.test_reproducibility:test_artifact_manifest_contains_file_hashes`

### 17.19 Package `tests`

- Ρόλος package: Regression tests
- Modules: `8`
- LOC: `1530`
- Top-level callables: `54`
- Methods: `0`
- Classes: `0`

#### Module `tests/conftest.py`

- Python module: `tests.conftest`
- Ρόλος: Regression tests
- LOC: `8`
- Imports: `__future__`, `pathlib`, `sys`
- Global constants / exported symbols:
  - `PROJECT_ROOT` = `Path(__file__).resolve().parents[1]`
- ASCII dependency sketch:
```text
[imports] __future__, pathlib, sys
      |
      v
[module] tests.conftest
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables: Κανένα.

#### Module `tests/test_contracts_metrics_pit.py`

- Python module: `tests.test_contracts_metrics_pit`
- Ρόλος: Regression tests
- LOC: `351`
- Imports: `__future__`, `numpy`, `pandas`, `pytest`, `src.evaluation.metrics`, `src.experiments.contracts`, `src.experiments.models`, `src.features.technical.indicators`, `src.features.technical.oscillators`, `src.src_data.pit`, `src.utils.config`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] __future__, numpy, pandas, pytest
      |
      v
[module] tests.test_contracts_metrics_pit
      |
      +-- functions: 12
      |
[inbound] tests.test_contracts_metrics_pit:test_forward_horizon_guard_trims_train_rows_in_t...
```

- Classes: Καμία.

- Top-level callables:
  - `_synthetic_frame`
  - `test_forward_horizon_guard_trims_train_rows_in_time_split`
  - `test_feature_contract_rejects_target_like_feature_columns`
  - `test_metrics_suite_includes_risk_and_cost_attribution`
  - `test_rsi_saturates_to_100_in_monotonic_uptrend`
  - `test_mfi_saturates_to_100_when_negative_flow_is_zero`
  - `test_align_ohlcv_timestamps_sorts_and_deduplicates`
  - `test_intraday_configs_do_not_normalize_timestamps_by_default`
  - `test_apply_corporate_actions_policy_adj_close_ratio`
  - `test_universe_snapshot_asof_membership_check`
  - `test_apply_pit_hardening_raises_when_symbol_exits_universe_mid_sample`
  - `test_apply_pit_hardening_can_drop_rows_outside_universe_snapshot`

##### Callable `tests.test_contracts_metrics_pit:_synthetic_frame`

- Signature: `def _synthetic_frame(n: int = 240) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `15`
- Σύνοψη λογικής: Verify that synthetic frame behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `n` (positional-or-keyword, `int`, default `240`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `tests.test_contracts_metrics_pit:test_forward_horizon_guard_trims_train_rows_in_time_split`

##### Callable `tests.test_contracts_metrics_pit:test_forward_horizon_guard_trims_train_rows_in_time_split`

- Signature: `def test_forward_horizon_guard_trims_train_rows_in_time_split() -> None`
- Return type: `None`
- LOC: `24`
- Σύνοψη λογικής: Verify that forward horizon guard trims train rows in time split behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_feature_contract_rejects_target_like_feature_columns`

- Signature: `def test_feature_contract_rejects_target_like_feature_columns() -> None`
- Return type: `None`
- LOC: `19`
- Σύνοψη λογικής: Verify that feature contract rejects target like feature columns behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_metrics_suite_includes_risk_and_cost_attribution`

- Signature: `def test_metrics_suite_includes_risk_and_cost_attribution() -> None`
- Return type: `None`
- LOC: `37`
- Σύνοψη λογικής: Verify that metrics suite includes risk and cost attribution behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_rsi_saturates_to_100_in_monotonic_uptrend`

- Signature: `def test_rsi_saturates_to_100_in_monotonic_uptrend() -> None`
- Return type: `None`
- LOC: `10`
- Σύνοψη λογικής: Verify that RSI saturates to 100 in monotonic uptrend behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_mfi_saturates_to_100_when_negative_flow_is_zero`

- Signature: `def test_mfi_saturates_to_100_when_negative_flow_is_zero() -> None`
- Return type: `None`
- LOC: `13`
- Σύνοψη λογικής: Verify that MFI saturates to 100 when negative flow is zero behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_align_ohlcv_timestamps_sorts_and_deduplicates`

- Signature: `def test_align_ohlcv_timestamps_sorts_and_deduplicates() -> None`
- Return type: `None`
- LOC: `36`
- Σύνοψη λογικής: Verify that align OHLCV timestamps sorts and deduplicates behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_intraday_configs_do_not_normalize_timestamps_by_default`

- Signature: `def test_intraday_configs_do_not_normalize_timestamps_by_default(tmp_path) -> None`
- Return type: `None`
- LOC: `37`
- Σύνοψη λογικής: Verify that intraday configs do not normalize timestamps by default behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `tmp_path` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_apply_corporate_actions_policy_adj_close_ratio`

- Signature: `def test_apply_corporate_actions_policy_adj_close_ratio() -> None`
- Return type: `None`
- LOC: `25`
- Σύνοψη λογικής: Verify that corporate actions policy adj close ratio behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_universe_snapshot_asof_membership_check`

- Signature: `def test_universe_snapshot_asof_membership_check(tmp_path) -> None`
- Return type: `None`
- LOC: `19`
- Σύνοψη λογικής: Verify that universe snapshot asof membership check behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `tmp_path` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_apply_pit_hardening_raises_when_symbol_exits_universe_mid_sample`

- Signature: `def test_apply_pit_hardening_raises_when_symbol_exits_universe_mid_sample(tmp_path) -> None`
- Return type: `None`
- LOC: `33`
- Σύνοψη λογικής: Verify that PIT hardening raises when symbol exits universe mid sample behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `tmp_path` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_contracts_metrics_pit:test_apply_pit_hardening_can_drop_rows_outside_universe_snapshot`

- Signature: `def test_apply_pit_hardening_can_drop_rows_outside_universe_snapshot(tmp_path) -> None`
- Return type: `None`
- LOC: `40`
- Σύνοψη λογικής: Verify that PIT hardening can drop rows outside universe snapshot behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `tmp_path` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `tests/test_core.py`

- Python module: `tests.test_core`
- Ρόλος: Regression tests
- LOC: `244`
- Imports: `numpy`, `pandas`, `pytest`, `src.backtesting.engine`, `src.features.returns`, `src.features.technical.trend`, `src.signals.volatility_signal`, `src.src_data.validation`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] numpy, pandas, pytest, src.backtesting.engine
      |
      v
[module] tests.test_core
      |
      +-- functions: 10
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables:
  - `test_compute_returns_simple_and_log`
  - `test_add_trend_features_columns`
  - `test_validate_ohlcv_flags_invalid_high_low`
  - `test_validate_ohlcv_rejects_missing_core_prices`
  - `test_run_backtest_costs_and_slippage_reduce_returns`
  - `test_run_backtest_log_returns_are_converted`
  - `test_run_backtest_charges_initial_entry_turnover`
  - `test_run_backtest_raises_on_missing_return_while_exposed`
  - `test_run_backtest_vol_targeting_flattens_missing_vol_warmup`
  - `test_volatility_regime_signal_is_causal_by_default`

##### Callable `tests.test_core:test_compute_returns_simple_and_log`

- Signature: `def test_compute_returns_simple_and_log() -> None`
- Return type: `None`
- LOC: `13`
- Σύνοψη λογικής: Verify that returns simple and log behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_add_trend_features_columns`

- Signature: `def test_add_trend_features_columns() -> None`
- Return type: `None`
- LOC: `13`
- Σύνοψη λογικής: Verify that trend features columns behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_validate_ohlcv_flags_invalid_high_low`

- Signature: `def test_validate_ohlcv_flags_invalid_high_low() -> None`
- Return type: `None`
- LOC: `19`
- Σύνοψη λογικής: Verify that OHLCV flags invalid high low behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_validate_ohlcv_rejects_missing_core_prices`

- Signature: `def test_validate_ohlcv_rejects_missing_core_prices() -> None`
- Return type: `None`
- LOC: `20`
- Σύνοψη λογικής: Verify that OHLCV rejects missing core prices behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_run_backtest_costs_and_slippage_reduce_returns`

- Signature: `def test_run_backtest_costs_and_slippage_reduce_returns() -> None`
- Return type: `None`
- LOC: `33`
- Σύνοψη λογικής: Verify that backtest costs and slippage reduce returns behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_run_backtest_log_returns_are_converted`

- Signature: `def test_run_backtest_log_returns_are_converted() -> None`
- Return type: `None`
- LOC: `26`
- Σύνοψη λογικής: Verify that backtest log returns are converted behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_run_backtest_charges_initial_entry_turnover`

- Signature: `def test_run_backtest_charges_initial_entry_turnover() -> None`
- Return type: `None`
- LOC: `27`
- Σύνοψη λογικής: Verify that backtest charges initial entry turnover behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_run_backtest_raises_on_missing_return_while_exposed`

- Signature: `def test_run_backtest_raises_on_missing_return_while_exposed() -> None`
- Return type: `None`
- LOC: `22`
- Σύνοψη λογικής: Verify that backtest raises on missing return while exposed behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_run_backtest_vol_targeting_flattens_missing_vol_warmup`

- Signature: `def test_run_backtest_vol_targeting_flattens_missing_vol_warmup() -> None`
- Return type: `None`
- LOC: `29`
- Σύνοψη λογικής: Verify that backtest vol targeting flattens missing vol warmup behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_core:test_volatility_regime_signal_is_causal_by_default`

- Signature: `def test_volatility_regime_signal_is_causal_by_default() -> None`
- Return type: `None`
- LOC: `13`
- Σύνοψη λογικής: Verify that volatility regime signal is causal by default behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `tests/test_no_lookahead.py`

- Python module: `tests.test_no_lookahead`
- Ρόλος: Regression tests
- LOC: `150`
- Imports: `__future__`, `numpy`, `pandas`, `src.experiments.models`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `_synthetic_price_frame`
  - `test_walk_forward_predictions_are_oos_only`
  - `test_purged_splits_respect_anti_leakage_gap`
  - `test_binary_forward_target_keeps_tail_labels_nan`
  - `test_quantile_target_uses_train_only_distribution_per_fold`

##### Callable `tests.test_no_lookahead:_synthetic_price_frame`

- Signature: `def _synthetic_price_frame(n: int = 260) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `16`
- Σύνοψη λογικής: Verify that synthetic price frame behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `n` (positional-or-keyword, `int`, default `260`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `tests.test_no_lookahead:test_binary_forward_target_keeps_tail_labels_nan`, `tests.test_no_lookahead:test_purged_splits_respect_anti_leakage_gap`, `tests.test_no_lookahead:test_quantile_target_uses_train_only_distribution_per_fold`, `tests.test_no_lookahead:test_walk_forward_predictions_are_oos_only`

##### Callable `tests.test_no_lookahead:test_walk_forward_predictions_are_oos_only`

- Signature: `def test_walk_forward_predictions_are_oos_only() -> None`
- Return type: `None`
- LOC: `28`
- Σύνοψη λογικής: Verify that walk forward predictions are out-of-sample only behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_no_lookahead:test_purged_splits_respect_anti_leakage_gap`

- Signature: `def test_purged_splits_respect_anti_leakage_gap() -> None`
- Return type: `None`
- LOC: `31`
- Σύνοψη λογικής: Verify that purged splits respect anti leakage gap behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_no_lookahead:test_binary_forward_target_keeps_tail_labels_nan`

- Signature: `def test_binary_forward_target_keeps_tail_labels_nan() -> None`
- Return type: `None`
- LOC: `21`
- Σύνοψη λογικής: Verify that binary forward target keeps tail labels nan behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_no_lookahead:test_quantile_target_uses_train_only_distribution_per_fold`

- Signature: `def test_quantile_target_uses_train_only_distribution_per_fold() -> None`
- Return type: `None`
- LOC: `38`
- Σύνοψη λογικής: Verify that quantile target uses train only distribution per fold behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `tests/test_portfolio.py`

- Python module: `tests.test_portfolio`
- Ρόλος: Regression tests
- LOC: `257`
- Imports: `__future__`, `numpy`, `pandas`, `src.portfolio`, `warnings`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] __future__, numpy, pandas, src.portfolio
      |
      v
[module] tests.test_portfolio
      |
      +-- functions: 9
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables:
  - `test_apply_constraints_respects_bounds_group_gross_and_turnover`
  - `test_build_weights_from_signals_over_time_respects_constraints`
  - `test_signal_to_raw_weights_keeps_missing_assets_flat`
  - `test_optimize_mean_variance_respects_core_constraints`
  - `test_apply_constraints_turnover_limit_raises_when_constraint_set_is_infeasible`
  - `test_compute_portfolio_performance_uses_shifted_weights`
  - `test_compute_portfolio_performance_raises_on_missing_exposed_return`
  - `test_compute_portfolio_performance_charges_initial_turnover`
  - `test_optimize_mean_variance_fallback_respects_max_gross_leverage`

##### Callable `tests.test_portfolio:test_apply_constraints_respects_bounds_group_gross_and_turnover`

- Signature: `def test_apply_constraints_respects_bounds_group_gross_and_turnover() -> None`
- Return type: `None`
- LOC: `31`
- Σύνοψη λογικής: Verify that constraints respects bounds group gross and turnover behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_portfolio:test_build_weights_from_signals_over_time_respects_constraints`

- Signature: `def test_build_weights_from_signals_over_time_respects_constraints() -> None`
- Return type: `None`
- LOC: `35`
- Σύνοψη λογικής: Verify that weights from signals over time respects constraints behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_portfolio:test_signal_to_raw_weights_keeps_missing_assets_flat`

- Signature: `def test_signal_to_raw_weights_keeps_missing_assets_flat() -> None`
- Return type: `None`
- LOC: `12`
- Σύνοψη λογικής: Verify that signal to raw weights keeps missing assets flat behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_portfolio:test_optimize_mean_variance_respects_core_constraints`

- Signature: `def test_optimize_mean_variance_respects_core_constraints() -> None`
- Return type: `None`
- LOC: `30`
- Σύνοψη λογικής: Verify that optimize mean variance respects core constraints behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_portfolio:test_apply_constraints_turnover_limit_raises_when_constraint_set_is_infeasible`

- Signature: `def test_apply_constraints_turnover_limit_raises_when_constraint_set_is_infeasible() -> None`
- Return type: `None`
- LOC: `18`
- Σύνοψη λογικής: Verify that constraints turnover limit raises when constraint set is infeasible behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_portfolio:test_compute_portfolio_performance_uses_shifted_weights`

- Signature: `def test_compute_portfolio_performance_uses_shifted_weights() -> None`
- Return type: `None`
- LOC: `38`
- Σύνοψη λογικής: Verify that portfolio performance uses shifted weights behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_portfolio:test_compute_portfolio_performance_raises_on_missing_exposed_return`

- Signature: `def test_compute_portfolio_performance_raises_on_missing_exposed_return() -> None`
- Return type: `None`
- LOC: `12`
- Σύνοψη λογικής: Verify that portfolio performance raises on missing exposed return behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_portfolio:test_compute_portfolio_performance_charges_initial_turnover`

- Signature: `def test_compute_portfolio_performance_charges_initial_turnover() -> None`
- Return type: `None`
- LOC: `20`
- Σύνοψη λογικής: Verify that portfolio performance charges initial turnover behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_portfolio:test_optimize_mean_variance_fallback_respects_max_gross_leverage`

- Signature: `def test_optimize_mean_variance_fallback_respects_max_gross_leverage() -> None`
- Return type: `None`
- LOC: `28`
- Σύνοψη λογικής: Verify that optimize mean variance fallback respects max gross leverage behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `tests/test_reproducibility.py`

- Python module: `tests.test_reproducibility`
- Ρόλος: Regression tests
- LOC: `117`
- Imports: `__future__`, `copy`, `numpy`, `pandas`, `pytest`, `src.utils.config`, `src.utils.repro`, `src.utils.run_metadata`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
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

- Classes: Καμία.

- Top-level callables:
  - `test_runtime_defaults_are_loaded_from_config`
  - `test_validate_runtime_config_rejects_invalid_threads`
  - `test_apply_runtime_reproducibility_sets_deterministic_numpy_stream`
  - `test_compute_config_hash_ignores_config_path_field`
  - `test_dataframe_fingerprint_is_stable_across_row_and_column_order`
  - `test_artifact_manifest_contains_file_hashes`

##### Callable `tests.test_reproducibility:test_runtime_defaults_are_loaded_from_config`

- Signature: `def test_runtime_defaults_are_loaded_from_config() -> None`
- Return type: `None`
- LOC: `13`
- Σύνοψη λογικής: Verify that runtime defaults are loaded from config behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_reproducibility:test_validate_runtime_config_rejects_invalid_threads`

- Signature: `def test_validate_runtime_config_rejects_invalid_threads() -> None`
- Return type: `None`
- LOC: `8`
- Σύνοψη λογικής: Verify that runtime config rejects invalid threads behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_reproducibility:test_apply_runtime_reproducibility_sets_deterministic_numpy_stream`

- Signature: `def test_apply_runtime_reproducibility_sets_deterministic_numpy_stream() -> None`
- Return type: `None`
- LOC: `21`
- Σύνοψη λογικής: Verify that runtime reproducibility sets deterministic numpy stream behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_reproducibility:test_compute_config_hash_ignores_config_path_field`

- Signature: `def test_compute_config_hash_ignores_config_path_field() -> None`
- Return type: `None`
- LOC: `14`
- Σύνοψη λογικής: Verify that config hash ignores config path field behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_reproducibility:test_dataframe_fingerprint_is_stable_across_row_and_column_order`

- Signature: `def test_dataframe_fingerprint_is_stable_across_row_and_column_order() -> None`
- Return type: `None`
- LOC: `19`
- Σύνοψη λογικής: Verify that dataframe fingerprint is stable across row and column order behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_reproducibility:test_artifact_manifest_contains_file_hashes`

- Signature: `def test_artifact_manifest_contains_file_hashes(tmp_path) -> None`
- Return type: `None`
- LOC: `19`
- Σύνοψη λογικής: Verify that artifact manifest contains file hashes behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `tmp_path` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `tests/test_runner_extensions.py`

- Python module: `tests.test_runner_extensions`
- Ρόλος: Regression tests
- LOC: `295`
- Imports: `__future__`, `json`, `numpy`, `pandas`, `pathlib`, `pytest`, `src.execution.paper`, `src.experiments.models`, `src.experiments.runner`, `src.portfolio.construction`, `src.src_data.storage`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] __future__, json, numpy, pandas
      |
      v
[module] tests.test_runner_extensions
      |
      +-- functions: 8
      |
[inbound] tests.test_runner_extensions:test_dataset_snapshot_roundtrip, tests.test_runner_e...
```

- Classes: Καμία.

- Top-level callables:
  - `_synthetic_ohlcv`
  - `test_dataset_snapshot_roundtrip`
  - `test_load_asset_frames_rejects_cached_snapshot_with_mismatched_pit_context`
  - `test_build_rebalance_orders_reports_share_deltas`
  - `test_build_rebalance_orders_ignores_flat_assets_with_missing_prices`
  - `test_build_rebalance_orders_emits_liquidation_for_current_only_asset`
  - `test_logistic_regression_model_registry_outputs_oos_metrics`
  - `test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution`

##### Callable `tests.test_runner_extensions:_synthetic_ohlcv`

- Signature: `def _synthetic_ohlcv(periods: int = 180, seed: int = 0, amplitude: float = 0.01) -> pd.DataFrame`
- Return type: `pd.DataFrame`
- LOC: `24`
- Σύνοψη λογικής: Verify that synthetic OHLCV behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `periods` (keyword-only, `int`, default `180`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `seed` (keyword-only, `int`, default `0`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
  - `amplitude` (keyword-only, `float`, default `0.01`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Καμια εξωτερικη παρενεργεια περα απο in-memory allocations και παραγωγη νεων pandas αντικειμενων.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Χαμηλη αλγοριθμικη πολυπλοκοτητα σε module utility path. Συνήθως γραμμικη ως προς το input size.
- Direct callers: `tests.test_runner_extensions:test_dataset_snapshot_roundtrip`, `tests.test_runner_extensions:test_load_asset_frames_rejects_cached_snapshot_with_mismatched_pit_context`, `tests.test_runner_extensions:test_logistic_regression_model_registry_outputs_oos_metrics`, `tests.test_runner_extensions:test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution`

##### Callable `tests.test_runner_extensions:test_dataset_snapshot_roundtrip`

- Signature: `def test_dataset_snapshot_roundtrip(tmp_path) -> None`
- Return type: `None`
- LOC: `30`
- Σύνοψη λογικής: Verify that dataset snapshot roundtrip behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `tmp_path` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_runner_extensions:test_load_asset_frames_rejects_cached_snapshot_with_mismatched_pit_context`

- Signature: `def test_load_asset_frames_rejects_cached_snapshot_with_mismatched_pit_context(tmp_path) -> None`
- Return type: `None`
- LOC: `33`
- Σύνοψη λογικής: Verify that load asset frames rejects cached snapshot with mismatched PIT context behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `tmp_path` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Filesystem path για read/write artifact handling.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_runner_extensions:test_build_rebalance_orders_reports_share_deltas`

- Signature: `def test_build_rebalance_orders_reports_share_deltas() -> None`
- Return type: `None`
- LOC: `17`
- Σύνοψη λογικής: Verify that rebalance orders reports share deltas behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_runner_extensions:test_build_rebalance_orders_ignores_flat_assets_with_missing_prices`

- Signature: `def test_build_rebalance_orders_ignores_flat_assets_with_missing_prices() -> None`
- Return type: `None`
- LOC: `15`
- Σύνοψη λογικής: Verify that rebalance orders ignores flat assets with missing prices behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_runner_extensions:test_build_rebalance_orders_emits_liquidation_for_current_only_asset`

- Signature: `def test_build_rebalance_orders_emits_liquidation_for_current_only_asset() -> None`
- Return type: `None`
- LOC: `17`
- Σύνοψη λογικής: Verify that rebalance orders emits liquidation for current only asset behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_runner_extensions:test_logistic_regression_model_registry_outputs_oos_metrics`

- Signature: `def test_logistic_regression_model_registry_outputs_oos_metrics() -> None`
- Return type: `None`
- LOC: `32`
- Σύνοψη λογικής: Verify that logistic regression model registry outputs out-of-sample metrics behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_runner_extensions:test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution`

- Signature: `def test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution(tmp_path, monkeypatch) -> None`
- Return type: `None`
- LOC: `97`
- Σύνοψη λογικής: Verify that experiment supports multi asset portfolio storage monitoring and execution behaves as expected under a representative regression scenario.
- Παράμετροι:
  - `tmp_path` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Filesystem path για read/write artifact handling.
  - `monkeypatch` (positional-or-keyword, `μη δηλωμένο`, default `χωρίς default`): Operational parameter του callable. Η ακριβης σημασια του προκυπτει απο το module context.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

#### Module `tests/test_time_splits.py`

- Python module: `tests.test_time_splits`
- Ρόλος: Regression tests
- LOC: `108`
- Imports: `__future__`, `numpy`, `src.evaluation.time_splits`
- Global constants / exported symbols: Δεν υπάρχουν explicit globals πέρα από definitions.
- ASCII dependency sketch:
```text
[imports] __future__, numpy, src.evaluation.time_splits
      |
      v
[module] tests.test_time_splits
      |
      +-- functions: 4
      |
[inbound] external / CLI / registry
```

- Classes: Καμία.

- Top-level callables:
  - `test_walk_forward_splits_are_time_ordered_and_non_overlapping`
  - `test_purged_walk_forward_respects_purge_and_embargo`
  - `test_purged_walk_forward_excludes_prior_embargo_rows_from_future_training`
  - `test_build_time_splits_uses_target_horizon_for_default_purge`

##### Callable `tests.test_time_splits:test_walk_forward_splits_are_time_ordered_and_non_overlapping`

- Signature: `def test_walk_forward_splits_are_time_ordered_and_non_overlapping() -> None`
- Return type: `None`
- LOC: `25`
- Σύνοψη λογικής: Verify that walk forward splits are time ordered and non overlapping behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_time_splits:test_purged_walk_forward_respects_purge_and_embargo`

- Signature: `def test_purged_walk_forward_respects_purge_and_embargo() -> None`
- Return type: `None`
- LOC: `27`
- Σύνοψη λογικής: Verify that purged walk forward respects purge and embargo behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_time_splits:test_purged_walk_forward_excludes_prior_embargo_rows_from_future_training`

- Signature: `def test_purged_walk_forward_excludes_prior_embargo_rows_from_future_training() -> None`
- Return type: `None`
- LOC: `20`
- Σύνοψη λογικής: Verify that purged walk forward excludes prior embargo rows from future training behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.

##### Callable `tests.test_time_splits:test_build_time_splits_uses_target_horizon_for_default_purge`

- Signature: `def test_build_time_splits_uses_target_horizon_for_default_purge() -> None`
- Return type: `None`
- LOC: `19`
- Σύνοψη λογικής: Verify that time splits uses target horizon for default purge behaves as expected under a representative regression scenario.
- Παράμετροι: Δεν δέχεται ορίσματα.
- Side effects: Δεν εχει production side effects. Εκτελει assertions πανω σε synthetic ή controlled δεδομενα.
- Exceptions: Δεν ανιχνεύονται ρητά `raise` statements στο static AST.
- Big-O: Δεν αποτελει performance-critical production path. Το κοστος ειναι αναλογο του synthetic dataset του test.
- Direct callers: CLI entrypoint, registry resolution ή isolated test invocation.
