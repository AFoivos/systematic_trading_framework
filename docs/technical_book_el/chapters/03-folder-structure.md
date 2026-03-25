## 3. Ανάλυση Δομής Φακέλων

### 3.1 Root-Level Breakdown

- `.devcontainer`: VSCode Dev Container ορισμός για επαναλήψιμο development περιβάλλον.
- `config`: Declarative experiment/configuration layer με self-contained experiment YAMLs.
- `config/experiments`: Παραδείγματα και production-like experiment definitions, όπου κάθε tracked experiment είναι πλήρες και δεν εξαρτάται από checked-in parent YAML.
- `data`: Persisted datasets, snapshots και metadata.
- `data/raw`: Raw ή canonical point-in-time snapshots.
- `data/processed`: Feature-enriched snapshots μετά από feature pipeline.
- `data/metadata`: Universe snapshots ή auxiliary metadata.
- `logs`: Αρχεία run artifacts, summaries και reproducibility metadata.
- `logs/experiments`: Output root για experiment runs με timestamp.
- `notebooks`: Χώρος για exploratory analysis, όχι core runtime layer.
- `output`: Γενικός χώρος generated outputs.
- `output/pdf`: Target folder για export artifacts σχετιζόμενα με PDF/reporting.
- `plots`: Δυνητικός χώρος visualization artifacts.
- `src`: Κύριος application codebase με σαφή domain packages.
- `tests`: Regression suite με έμφαση σε anti-leakage, portfolio constraints και reproducibility.
- `tmp`: Προσωρινά artifacts / scratch space.

### 3.2 Folder-by-Folder Τεχνική Ερμηνεία

Ο φάκελος `src/` περιέχει τον πραγματικό πυρήνα του συστήματος. Μέσα του, η ονοματοδοσία είναι αρκετά
αυστηρή και domain-driven:

- `src/src_data`: Data ingestion και point-in-time hardening. Εδώ γίνονται provider selection, schema validation, snapshot storage και universe membership checks.
- `src/features`: Feature engineering για returns, lags, volatility και technical indicators. Όλες οι μετασχηματίσεις είναι causal και βασίζονται σε pandas time-series operations.
- `src/signals`: Primitive signal builders που μετατρέπουν features ή model probabilities σε directional ή sized exposures.
- `src/backtesting`: Vectorized single-asset backtesting και strategy wrappers γύρω από τα signal primitives.
- `src/evaluation`: Chronological splitting και metric computation για OOS evaluation με anti-leakage guarantees.
- `src/risk`: Position sizing και drawdown-based exposure control.
- `src/portfolio`: Portfolio constraints, optimization, signal-to-weight mapping και portfolio-level accounting.
- `src/monitoring`: Production-style drift diagnostics για features.
- `src/execution`: Paper execution export layer.
- `src/intraday`: Intraday interval/session defaults και annualization helpers.
- `src/models`: Καθαρά estimator/fold engines για SARIMAX, GARCH, TFT και lightweight notebook baselines.
- `src/experiments`: Experiment-facing domain με contracts, registries, façades και split subpackages για orchestration και modeling.
- `src/utils`: Infrastructure utilities για paths, config normalization, reproducibility και run metadata. Το config layer πλέον είναι σπασμένο σε `config_loader`, `config_defaults`, `config_validation`, `config_schemas`.
- `tests`: Regression suite που κωδικοποιεί τις θεμελιώδεις υποθέσεις correctness, anti-leakage και reproducibility.

Οι φάκελοι `data/`, `logs/`, `output/` και `tmp/` λειτουργούν ως operational surfaces. Δεν είναι μέρος της
επιχειρησιακής λογικής, αλλά είναι κρίσιμοι για reproducibility, artifact retention και report generation.
Ιδίως το `logs/experiments` αποτελεί quasi-run ledger: κάθε execution παράγει timestamped directory με summary,
equity curves, costs, orders και metadata manifests.

### 3.3 File Inventory με LOC

Η παρακάτω λίστα είναι snapshot του current modular layout στα core architecture files.

| Αρχείο | LOC | Ρόλος |
|---|---:|---|
| `config/experiments/btcusd_1h_dukas_lightgbm_triple_barrier_garch_long_oos.yaml` | 275 | Πλήρως self-contained BTCUSD LightGBM long-OOS experiment χωρίς `extends`, με local Dukas CSV ingest, triple-barrier target και GARCH overlay. |
| `config/experiments/btcusd_1h_dukas_xgboost_triple_barrier_garch_long_oos.yaml` | 276 | Πλήρως self-contained BTCUSD XGBoost long-OOS experiment χωρίς `extends`, με ίδιο causal pipeline για apples-to-apples σύγκριση. |
| `src/__init__.py` | 0 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/backtesting/__init__.py` | 22 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/backtesting/engine.py` | 115 | Single-asset vectorized backtest engine με cost model, vol targeting και drawdown cooloff guard. |
| `src/backtesting/strategies.py` | 225 | Υλοποίηση του module `strategies.py` μέσα στο package `backtesting`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/evaluation/__init__.py` | 47 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/evaluation/metrics.py` | 280 | Performance metrics layer για returns, risk, turnover και cost attribution. |
| `src/evaluation/time_splits.py` | 293 | Time-aware split generator με support για simple time split, walk-forward και purged walk-forward. |
| `src/execution/__init__.py` | 3 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/execution/paper.py` | 66 | Paper execution artifact builder που μετατρέπει target weights σε notional/share deltas. |
| `src/experiments/__init__.py` | 38 | Public API surface με lazy exports του runner ώστε τα package imports να μένουν σταθερά χωρίς circular-import side effects. |
| `src/experiments/contracts.py` | 130 | Υλοποίηση του module `contracts.py` μέσα στο package `experiments`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/experiments/models.py` | 19 | Stable façade προς το `src/models/*` ώστε registry και imports να μείνουν συμβατά. |
| `src/experiments/registry.py` | 88 | Υλοποίηση του module `registry.py` μέσα στο package `experiments`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/experiments/runner.py` | 130 | Thin façade που κρατά stable entrypoints και legacy monkeypatch/test surfaces προς το orchestration package. |
| `src/targets/*.py` | package | Canonical target builders και label helpers με explicit anti-leakage semantics. |
| `src/experiments/support/metrics.py` | 153 | Shared classification/regression/volatility diagnostics για fold-safe OOS evaluation. |
| `src/experiments/support/diagnostics.py` | 233 | Feature importance, label-distribution και prediction-alignment summaries για reports και artifacts. |
| `src/experiments/orchestration/pipeline.py` | 189 | End-to-end pipeline assembly που καλεί τα επιμέρους data/feature/model/backtest/reporting/execution stages. |
| `src/experiments/orchestration/data_stage.py` | 143 | Data ingestion, PIT hardening, raw snapshot loading/saving και storage context handling. |
| `src/experiments/orchestration/backtest_stage.py` | 185 | Single-asset και portfolio backtest orchestration, returns validation και portfolio constraints. |
| `src/experiments/orchestration/reporting.py` | 257 | OOS evaluation payloads, fold summaries και monitoring report assembly. |
| `src/experiments/orchestration/artifacts.py` | 144 | Artifact persistence για configs, summaries, returns, weights, orders και manifests. |
| `src/features/__init__.py` | 20 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/features/lags.py` | 35 | Υλοποίηση του module `lags.py` μέσα στο package `features`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/features/returns.py` | 64 | Υλοποίηση του module `returns.py` μέσα στο package `features`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/features/technical/__init__.py` | 55 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/features/technical/indicators.py` | 239 | Υλοποίηση του module `indicators.py` μέσα στο package `technical`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/features/technical/momentum.py` | 93 | Υλοποίηση του module `momentum.py` μέσα στο package `technical`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/features/technical/oscillators.py` | 122 | Υλοποίηση του module `oscillators.py` μέσα στο package `technical`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/features/technical/trend.py` | 190 | Υλοποίηση του module `trend.py` μέσα στο package `technical`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/features/volatility.py` | 100 | Υλοποίηση του module `volatility.py` μέσα στο package `features`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/models/__init__.py` | 25 | Public API surface που επανεξάγει estimator/fold engines και baseline helpers από το model layer. |
| `src/models/garch.py` | 198 | Καθαρό GARCH engine module με parameter fitting και fold predictor factory ανεξάρτητα από το experiment layer. |
| `src/models/lightgbm_baseline.py` | 128 | Lightweight baseline/model helper layer για notebooks και shared feature defaults. |
| `src/models/sarimax.py` | 139 | Καθαρό SARIMAX fold engine με local fallback policy και exogenous-feature handling. |
| `src/models/tft.py` | 262 | Καθαρό TFT-style sequence engine με sample construction και fold predictor factory. |
| `src/monitoring/__init__.py` | 6 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/monitoring/drift.py` | 113 | Monitoring layer για PSI-based feature drift και summary diagnostics. |
| `src/portfolio/__init__.py` | 35 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/portfolio/constraints.py` | 291 | Projection/constraint engine για weights, leverage, turnover και optional group exposures. |
| `src/portfolio/construction.py` | 221 | Portfolio construction layer για signal-to-weight mapping, rolling optimization και portfolio PnL accounting. |
| `src/portfolio/covariance.py` | 42 | Υλοποίηση του module `covariance.py` μέσα στο package `portfolio`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/portfolio/optimizer.py` | 179 | Mean-variance optimizer με hard constraints και safe fallback όταν ο solver αποτυγχάνει. |
| `src/risk/__init__.py` | 9 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/risk/controls.py` | 50 | Υλοποίηση του module `controls.py` μέσα στο package `risk`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/risk/position_sizing.py` | 54 | Υλοποίηση του module `position_sizing.py` μέσα στο package `risk`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/signals/__init__.py` | 13 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/signals/momentum_signal.py` | 40 | Υλοποίηση του module `momentum_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/signals/rsi_signal.py` | 35 | Υλοποίηση του module `rsi_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/signals/stochastic_signal.py` | 38 | Υλοποίηση του module `stochastic_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/signals/trend_signal.py` | 36 | Υλοποίηση του module `trend_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/signals/volatility_signal.py` | 46 | Υλοποίηση του module `volatility_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/src_data/__init__.py` | 34 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/src_data/loaders.py` | 84 | Facade για market data providers και panel loading. |
| `src/src_data/pit.py` | 250 | Point-in-time hardening layer για timestamp normalization, corporate actions policy και universe snapshot membership checks. |
| `src/src_data/providers/__init__.py` | 9 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/src_data/providers/alphavantage.py` | 86 | Alpha Vantage FX provider για daily FX series με API-backed HTTP requests. |
| `src/src_data/providers/base.py` | 24 | Abstract contract για providers εξωτερικών market data sources. |
| `src/src_data/providers/yahoo.py` | 79 | Yahoo Finance provider με normalization σε project OHLCV schema. |
| `src/src_data/storage.py` | 208 | Persistence layer για raw/processed dataset snapshots σε canonical long format. |
| `src/src_data/validation.py` | 57 | Υλοποίηση του module `validation.py` μέσα στο package `src_data`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/utils/__init__.py` | 0 | Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά. |
| `src/intraday/calendar.py` | 149 | Intraday interval parsing, annualization inference και guards για timestamp normalization. |
| `src/utils/config.py` | 69 | Stable façade που εκθέτει dict και typed config loading πάνω από τα επιμέρους config modules. |
| `src/utils/config_defaults.py` | 188 | Default policies ανά block, including intraday-aware volatility/backtest annualization defaults. |
| `src/utils/config_loader.py` | 57 | Self-contained YAML loading, safe path resolution, explicit rejection of `extends` και env secret injection. |
| `src/utils/config_schemas.py` | 490 | Typed resolved config objects για orchestration-facing usage. |
| `src/utils/config_validation.py` | 358 | Semantic validation για data/model/backtest/portfolio/execution blocks και intraday guards. |
| `src/utils/paths.py` | 63 | Υλοποίηση του module `paths.py` μέσα στο package `utils`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/utils/repro.py` | 149 | Υλοποίηση του module `repro.py` μέσα στο package `utils`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository. |
| `src/utils/run_metadata.py` | 294 | Reproducibility metadata layer: hashing config/data, συλλογή environment/git metadata και artifact manifesting. |
| `tests/conftest.py` | 8 | Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions. |
| `tests/test_contracts_metrics_pit.py` | 205 | Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions. |
| `tests/test_core.py` | 167 | Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions. |
| `tests/test_no_lookahead.py` | 150 | Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions. |
| `tests/test_portfolio.py` | 203 | Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions. |
| `tests/test_reproducibility.py` | 117 | Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions. |
| `tests/test_runner_extensions.py` | 223 | Integration-style tests που επιβεβαιώνουν end-to-end orchestration features πέρα από τον αρχικό πυρήνα. |
| `tests/test_time_splits.py` | 86 | Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions. |
