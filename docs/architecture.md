# Αρχιτεκτονική Systematic Trading Framework

Τελευταία ενημέρωση: 2026-06-25

## Στόχος

Το framework είναι πλέον οργανωμένο γύρω από ένα config-driven canonical
experiment pipeline και ξεχωριστά registries ανά κατηγορία. Τα YAML configs
δηλώνουν ονόματα components και τα pipelines τα επιλύουν μέσω registries, χωρίς
scattered imports στο orchestration layer.

## Canonical Pipeline

Το canonical pipeline είναι:

- `src.pipelines.canonical_pipeline.run_canonical_pipeline`
- registry name: `canonical_experiment`
- implementation facade προς το υπάρχον `src.experiments.runner.run_experiment`
- πραγματική ενορχήστρωση στο `src.experiments.orchestration.pipeline.run_experiment_pipeline`

Η σειρά εκτέλεσης είναι:

1. data loading και PIT hardening
2. data validation
3. feature generation
4. model training ή model pipeline stages
5. signal generation
6. optional post-signal target diagnostics
7. backtesting/evaluation
8. monitoring/execution output
9. reporting/artifact writing

Το `src.experiments.runner` παραμένει stable legacy entrypoint, αλλά το
canonical public pipeline βρίσκεται στο `src/pipelines`.

## Registries

Τα canonical registries βρίσκονται πλέον ανά package:

- `src/features/registry.py`
- `src/signals/registry.py`
- `src/targets/registry.py`
- `src/models/registry.py`
- `src/pipelines/registry.py`

Κάθε registry:

- ορίζεται από λίστα `(name, callable)` ώστε να εντοπίζονται duplicate names
- περνά από `src.utils.registry.build_registry`
- αποτυγχάνει με informative `RegistryLookupError` για άγνωστα names
- εκθέτει `get_*_fn` ή `get_*_builder`

Το παλιό `src.experiments.registry` είναι compatibility facade και δεν είναι
πλέον ο ιδιοκτήτης των mappings.

## Features

Canonical feature names είναι μόνο όσα αντιστοιχούν σε πραγματικούς feature
builders. Παραδείγματα:

- `returns`
- `volatility`
- `trend`
- `roc`
- `atr`
- `adx`
- `vwap`
- `feature_transforms`
- `hmm_regime`
- `roofing_filter`

Τα παλιά feature-stage signal steps κρατήθηκαν χωριστά στο
`FEATURE_COMPATIBILITY_REGISTRY`:

- `ehlers_semiscalp_long`
- `ema_stoch_rsi_pullback`
- `indicator_model_adaptive_pullback`
- `roc_long_only_conditions`
- `vwap_rms_ema_cross_long`

Αυτά παραμένουν resolvable για υπάρχοντα configs, αλλά δεν θεωρούνται canonical
features. Μελλοντικά πρέπει να μεταφερθούν είτε σε κανονικά feature modules είτε
σε multi-signal-stage pipeline schema.

### Προσθήκη νέου feature

1. Δημιουργείς ένα αρχείο στο `src/features` ή `src/features/technical`, π.χ.
   `src/features/technical/my_indicator.py`.
2. Ορίζεις ένα καθαρό function που δέχεται `pd.DataFrame` και επιστρέφει νέο
   `pd.DataFrame`.
3. Δεν εισάγεις signals, models, backtesting ή experiments.
4. Προσθέτεις το `(name, callable)` στο `src/features/registry.py`.
5. Προσθέτεις focused tests για contract, missing columns και causality.
6. Χρησιμοποιείς το νέο name στο YAML:

```yaml
features:
  - step: my_indicator
    params:
      window: 20
```

## Signals

Canonical signal names είναι στο `src/signals/registry.py`. Deprecated aliases
υπάρχουν μόνο στο `DEPRECATED_SIGNAL_ALIASES`, όχι στο canonical
`SIGNAL_REGISTRY`.

Παράδειγμα:

- canonical: `ehlers_continuation_short`
- deprecated alias: `ehlers_continuation_short_signal`

### Προσθήκη νέου signal

1. Δημιουργείς ένα αρχείο στο `src/signals`.
2. Το signal χρησιμοποιεί ήδη υπάρχοντα feature/model columns.
3. Δεν εισάγει experiments ή models.
4. Δεν κάνει βαρύ feature engineering εσωτερικά.
5. Προσθέτεις το canonical name στο `src/signals/registry.py`.
6. Το YAML χρησιμοποιεί:

```yaml
signals:
  kind: my_signal
  params:
    signal_col: signal_side
```

## Targets

Το target dispatch γίνεται από `src/targets/registry.py`.

Canonical targets:

- `forward_return`
- `future_return_regression`
- `triple_barrier`
- `directional_triple_barrier`
- `r_multiple`

Το παλιό `build_classifier_target` παραμένει facade και καλεί `build_target`.

### Προσθήκη νέου target

1. Δημιουργείς ένα αρχείο στο `src/targets`.
2. Το function επιστρέφει `(frame, label_col, fwd_col, meta)`.
3. Δεν εισάγει models ή backtesting.
4. Προσθέτεις το `(kind, builder)` στο `src/targets/registry.py`.
5. Προσθέτεις validation/tests.
6. Το YAML χρησιμοποιεί:

```yaml
model:
  target:
    kind: my_target
    horizon: 5
```

## Models

Το model resolution γίνεται από `src/models/registry.py`. Τα entries είναι lazy
ώστε το import του registry να μη φορτώνει βαριές ML dependencies.

Παραδείγματα:

- `logistic_regression_clf`
- `elastic_net_clf`
- `xgboost_clf`
- `lightgbm_clf`
- `lightgbm_regressor`
- `sarimax_forecaster`
- `garch_forecaster`
- `lstm_forecaster`
- `patchtst_forecaster`
- `tft_forecaster`
- `ppo_agent`

### Προσθήκη νέου model

1. Δημιουργείς wrapper/definition σε ένα αρχείο κάτω από `src/models`.
2. Το model δεν κάνει data loading ή cleaning.
3. Το preprocessing μένει στο model training layer μόνο αν είναι train-fold safe.
4. Προσθέτεις lazy registry entry στο `src/models/registry.py`.
5. Το YAML αλλάζει μόνο το `model.kind` και τα params:

```yaml
model:
  kind: logistic_regression_clf
  params:
    max_iter: 500
```

## Duplicate Cleanup

Το duplicate `rate_of_change` αφαιρέθηκε υπέρ του canonical `roc`.

Λόγος:

- Τα YAML configs χρησιμοποιούν `roc`.
- Το output convention είναι ήδη `roc_<window>`.
- Το `rate_of_change` δεν χρησιμοποιούνταν από configs ή core imports.
- Η μικρή χρηστικότητα `window`/`output_col` μεταφέρθηκε στο `roc`.

Το `true_range.py` δεν αφαιρέθηκε, επειδή είναι πραγματικός shared helper:

- χρησιμοποιείται από `atr`
- χρησιμοποιείται από `adx`
- εκτίθεται από το technical package

## Layer Rules

Οι βασικοί κανόνες είναι:

- `features` δεν εξαρτώνται από `signals`, `models`, `backtesting`
- `targets` δεν εξαρτώνται από `models`, `backtesting`
- `signals` δεν εξαρτώνται από `experiments`, `models`
- `models` δεν κάνουν data loading
- `experiments` ενορχηστρώνουν και δεν φιλοξενούν canonical registries

Η κοινή trade-path προσομοίωση μετακινήθηκε στο `src/utils/trade_path.py` ώστε
το `r_multiple` target να μην εισάγει `src.backtesting`.

## Legacy Candidates

Δεν διαγράφηκαν χωρίς πλήρη ασφάλεια:

- feature-stage signal steps στο `FEATURE_COMPATIBILITY_REGISTRY`
- `src.experiments.registry` compatibility facade
- `src.experiments.models` compatibility export hub
- old experiment/support diagnostics κάτω από `src/experiments/support`
- `src.backtesting.trade_path` re-export path
- deprecated signal aliases `*_signal`

Αυτά πρέπει να αφαιρεθούν μόνο μετά από migration όλων των παλιών YAMLs και
τυχόν εξωτερικών scripts που τα χρησιμοποιούν.
