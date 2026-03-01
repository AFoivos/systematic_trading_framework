## 16. Appendix

### 16.1 Dependency Tree (Logical / Direct)

```text
systematic-trading-framework
├── Core numerical
│   ├── numpy
│   ├── pandas
│   ├── scipy
│   └── statsmodels (αναφέρεται στις εξαρτήσεις, όχι ακόμη σε active imports)
├── Machine learning
│   ├── scikit-learn
│   ├── lightgbm
│   └── xgboost (παρόν στις εξαρτήσεις, όχι ακόμη σε active imports)
├── Deep learning / RL roadmap
│   ├── torch
│   ├── torchmetrics
│   ├── pytorch-lightning
│   ├── gymnasium
│   └── stable-baselines3
├── Data acquisition
│   ├── yfinance
│   └── requests
├── Config / utilities
│   ├── pyyaml
│   ├── tqdm
│   ├── matplotlib
│   └── seaborn
├── Notebook tooling
│   ├── jupyterlab
│   ├── notebook
│   ├── ipykernel
│   └── ipywidgets
└── Testing
    └── pytest
```

### 16.2 Import Graph (Package-Level)

| From | To | Direct import edges |
|---|---|---:|
| `backtesting` | `evaluation` | 1 |
| `backtesting` | `risk` | 3 |
| `backtesting` | `signals` | 1 |
| `experiments` | `backtesting` | 2 |
| `experiments` | `evaluation` | 2 |
| `experiments` | `execution` | 1 |
| `experiments` | `experiments` | 4 |
| `experiments` | `features` | 5 |
| `experiments` | `models` | 1 |
| `experiments` | `monitoring` | 1 |
| `experiments` | `portfolio` | 1 |
| `experiments` | `src_data` | 4 |
| `experiments` | `utils` | 4 |
| `models` | `features` | 1 |
| `portfolio` | `evaluation` | 1 |
| `portfolio` | `portfolio` | 3 |
| `src_data` | `src_data` | 4 |
| `src_data` | `utils` | 3 |
| `tests` | `backtesting` | 1 |
| `tests` | `evaluation` | 2 |
| `tests` | `execution` | 1 |
| `tests` | `experiments` | 5 |
| `tests` | `features` | 2 |
| `tests` | `portfolio` | 2 |
| `tests` | `signals` | 1 |
| `tests` | `src_data` | 3 |
| `tests` | `utils` | 3 |
| `utils` | `utils` | 3 |

Ερμηνεία: ο package `experiments` είναι ο μεγαλύτερος consumer των υπόλοιπων layers. Αυτό είναι αναμενόμενο
λόγω του orchestration ρόλου του. Τα `portfolio` και `src_data` packages έχουν κυρίως εσωτερική συνοχή και
σχετικά περιορισμένες outbound εξαρτήσεις.

### 16.3 Call Graph (Κειμενικά)

**Primary orchestration path**

```text
run_experiment
  -> load_experiment_config
  -> apply_runtime_reproducibility
  -> compute_config_hash
  -> _load_asset_frames
       -> load_dataset_snapshot / load_ohlcv / load_ohlcv_panel
       -> apply_pit_hardening
       -> validate_ohlcv
       -> validate_data_contract
       -> save_dataset_snapshot (optional)
  -> _apply_steps_to_assets
       -> _apply_feature_steps
            -> get_feature_fn -> feature function
  -> _apply_model_to_assets
       -> _apply_model_step
            -> get_model_fn -> train_*_classifier
                 -> _train_forward_classifier
                      -> build_time_splits
                      -> trim_train_indices_for_horizon
                      -> assert_no_forward_label_leakage
  -> _apply_signals_to_assets
       -> _apply_signal_step
            -> get_signal_fn -> signal function
  -> _run_single_asset_backtest OR _run_portfolio_backtest
       -> run_backtest OR build_weights_* / optimize_mean_variance / compute_portfolio_performance
  -> _build_*_evaluation
  -> _compute_monitoring_report
       -> compute_feature_drift
  -> _build_execution_output
       -> build_rebalance_orders
  -> _save_artifacts
       -> build_artifact_manifest
```

**Portfolio optimization path**

```text
_run_portfolio_backtest
  -> _align_asset_column(signals)
  -> _align_asset_column(returns)
  -> _build_portfolio_constraints
  -> build_rolling_covariance_by_date (if mean_variance)
  -> build_optimized_weights_over_time / build_weights_from_signals_over_time
       -> optimize_mean_variance / apply_constraints
  -> compute_portfolio_performance
  -> compute_backtest_metrics
```

### 16.4 Data Schemas

**Canonical single-asset OHLCV schema**

| Field | Type | Περιγραφή |
|---|---|---|
| `index` | `DatetimeIndex` | Χρονικός άξονας, monotonic increasing, unique. |
| `open` | float | Τιμή ανοίγματος. |
| `high` | float | Υψηλό περιόδου. |
| `low` | float | Χαμηλό περιόδου. |
| `close` | float | Τιμή κλεισίματος. |
| `volume` | float | Όγκος. Στο Alpha Vantage FX μπαίνει τεχνητά `0.0`. |
| `adj_close` | float, optional | Adjusted close όταν υποστηρίζεται από provider. |
| `pit_adjustment_factor` | float, optional | Συντελεστής PIT adjustment όταν εφαρμόζονται corporate action policies. |

**Canonical snapshot long schema**

| Field | Type | Περιγραφή |
|---|---|---|
| `timestamp` | datetime | Χρονική στιγμή. |
| `asset` | str | Symbol/asset id. |
| υπόλοιπες στήλες | mixed | Όλες οι αρχικές ή feature-enriched στήλες του asset frame. |

**Summary artifact schema (ενδεικτικά πεδία)**

- `summary`
- `timeline_summary`
- `evaluation`
- `monitoring`
- `execution`
- `portfolio`
- `storage`
- `model_meta`
- `config_features`
- `signals`
- `resolved_feature_columns`
- `data_stats`
- `reproducibility`

### 16.5 Glossary

- **PIT (Point in Time)**: χρήση μόνο της πληροφορίας που ήταν διαθέσιμη τη συγκεκριμένη χρονική στιγμή.
- **Leakage / Lookahead Bias**: χρήση μελλοντικής πληροφορίας κατά το training ή backtesting.
- **OOS (Out of Sample)**: observations που δεν χρησιμοποιήθηκαν στο fit και αξιολογούνται ως pseudo-future.
- **Purged Split**: split όπου αφαιρούνται training rows κοντά στο test window ώστε να μη μοιράζονται overlapping label horizons.
- **Embargo**: χρονικό gap μεταξύ folds για αποφυγή dependence contamination.
- **Turnover**: απόλυτη μεταβολή θέσης ή weights ανά περίοδο.
- **Gross Leverage**: άθροισμα απολύτων weights/exposures.
- **Net Exposure**: αλγεβρικό άθροισμα weights/exposures.
- **PSI (Population Stability Index)**: μέτρο drift μεταξύ reference και current distribution.
- **Conviction Signal**: sized signal που χαρτογραφεί probability σε continuous exposure.
- **Artifact Manifest**: κατάλογος παραχθέντων αρχείων μαζί με hashes για integrity checks.

### 16.6 Τελική Αξιολόγηση Αρχιτεκτονικής

Το repository είναι σαφώς ανώτερο από ένα typical research notebook dump. Διαθέτει contracts, registry-based
composition, deterministic runtime controls, anti-leakage evaluation, portfolio constraints και artifact lineage.
Το σημαντικότερο επόμενο architectural βήμα δεν είναι η προσθήκη περισσότερων μοντέλων, αλλά η περαιτέρω
διάσπαση του orchestration/reporting layer και η ενίσχυση operational observability. Ακόμη και στην τρέχουσα
μορφή του όμως, το codebase είναι αρκετά ώριμο για σοβαρό onboarding senior engineer, αρκεί να γίνει κατανοητό
ότι η φιλοσοφία του είναι “research-first with production discipline”, όχι “live trading platform”.
