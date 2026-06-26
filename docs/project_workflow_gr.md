# Project Workflow

Τελευταία ενημέρωση: 2026-06-27

Αυτό το αρχείο περιγράφει την πρακτική ροή εργασίας για χρήση και επέκταση του
framework.

## 1. Data workflow

Τα data modules βρίσκονται στο `src/src_data`.

Βασικές ευθύνες:

- φόρτωση OHLCV ή panel data,
- validation για timestamp/order/schema,
- point-in-time hardening,
- αποθήκευση raw/processed snapshots όταν το config το ζητάει.

Τα raw data πρέπει να αντιμετωπίζονται ως immutable inputs. Αν χρειάζεται
καθαρισμός ή resampling, γράψε νέο processed artifact ή explicit preparation
script. Μην αλλάζεις σιωπηλά raw snapshots.

## 2. Feature workflow

Τα raw features βρίσκονται σε:

- `src/features/`
- `src/features/technical/`

Τα helpers βρίσκονται σε:

- `src/features/helpers/`
- `src/features/helpers/normalizations/`

Κανόνας:

- raw feature = βασικός υπολογισμός indicator/statistic,
- helper = ratio, distance, slope, lag, flag, crossing, z-score, clipping,
  rolling aggregation ή normalization.

Παράδειγμα:

```yaml
features:
  - step: roofing_filter
    params:
      price_col: close
      output_col: roofing_filter_48_10
    transforms:
      difference:
        params:
          source_col: roofing_filter_48_10
          periods: 1
          output_col: roofing_filter_48_10_slope
      crossing_flag:
        items:
          - source_col: roofing_filter_48_10
            threshold: 0.0
            direction: up
            output_col: roofing_filter_48_10_cross_up
          - source_col: roofing_filter_48_10
            threshold: 0.0
            direction: down
            output_col: roofing_filter_48_10_cross_down
```

Αυτό αποφεύγει dataframe bloat και κάνει κάθε derived column audit-friendly.

## 3. Target workflow

Τα targets βρίσκονται στο `src/targets`.

Ένα target builder πρέπει:

- να παράγει label/future-return columns με explicit horizon,
- να επιστρέφει metadata όταν χρειάζεται,
- να μην εισάγει models/backtesting,
- να είναι ξεκάθαρο αν χρησιμοποιεί future bars, επειδή target generation
  επιτρέπεται να κοιτάει μπροστά μόνο για labels.

Παράδειγμα YAML:

```yaml
model:
  target:
    kind: directional_triple_barrier
    horizon: 16
    label_col: label
    fwd_col: fwd_ret
```

## 4. Model workflow

Τα models βρίσκονται στο `src/models`.

Κανόνες:

- το model δεν φορτώνει data,
- preprocessing/scaling γίνεται fold-safe,
- κάθε train/test split σέβεται χρονική σειρά,
- hyperparameters δηλώνονται στο YAML,
- registry entry μπαίνει στο `src/models/registry.py`.

Παράδειγμα:

```yaml
model:
  kind: logistic_regression_clf
  preprocessing:
    scaler: robust
  params:
    max_iter: 500
```

## 5. Signal workflow

Τα signals βρίσκονται στο `src/signals`.

Ένα signal πρέπει να διαβάζει ήδη υπάρχοντα columns και να παράγει signal side,
position intent ή probability-derived decision. Δεν πρέπει να κάνει βαρύ feature
engineering εσωτερικά. Αν χρειάζεται νέα στήλη, πρόσθεσέ τη ως feature/helper.

Παράδειγμα:

```yaml
signals:
  kind: ehlers_cycle_long
  params:
    signal_col: cycle_signal
```

## 6. Backtest και evaluation workflow

Τα backtest/evaluation modules βρίσκονται σε:

- `src/backtesting/`
- `src/evaluation/`
- `src/risk/`
- `src/portfolio/`

Πριν εμπιστευτείς αποτέλεσμα, έλεγξε:

- costs, spread, slippage,
- execution timing,
- max exposure και position sizing,
- fold-level metrics,
- OOS separation,
- trade count και concentration,
- sensitivity σε threshold/params.

## 7. Monitoring και execution workflow

Το `src/monitoring` παράγει drift/stability diagnostics.

Το `src/execution` παράγει paper/demo execution outputs. Το MT5 demo runner έχει
safety gates:

- dry-run default,
- demo-account requirement όταν ζητείται,
- max positions και duplicate-position guard,
- spread/drawdown/daily-loss checks,
- optional stop file όπως `STOP_TRADING`.

Παράδειγμα dry-run:

```bash
python scripts/run_mt5_demo_bot.py --config config/execution/mt5_demo.yaml --once
```

## 8. Πώς προσθέτεις νέο component

1. Διάβασε το κοντινό module και τα tests.
2. Πρόσθεσε καθαρό function στο σωστό package.
3. Πρόσθεσε registry entry.
4. Πρόσθεσε config validation αν υπάρχουν νέες YAML επιλογές.
5. Πρόσθεσε tests για contract, edge cases και causality.
6. Ενημέρωσε catalog/docs.
7. Τρέξε targeted tests και, για cross-cutting αλλαγές, όλο το test suite.

## 9. Anti-leakage checklist

- Το feature στο timestamp `t` χρησιμοποιεί μόνο πληροφορία διαθέσιμη μέχρι το
  `t`.
- Τα rolling statistics δεν χρησιμοποιούν future observations.
- Τα scalers γίνονται fit μόνο στο train fold.
- Το target κοιτάει μπροστά μόνο για label generation, ποτέ ως model input.
- Δεν γίνεται random split σε time series χωρίς explicit αιτιολόγηση.
- Οι αποφάσεις εκτέλεσης δεν χρησιμοποιούν close του ίδιου bar αν το trade
  υποτίθεται ότι εκτελείται πριν κλείσει το bar.
