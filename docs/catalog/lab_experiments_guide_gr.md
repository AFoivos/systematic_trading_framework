# Οδηγός Lab Experiments

Τελευταία ενημέρωση: 2026-07-23

Ο οδηγός αυτός δείχνει πώς στήνουμε μικρά, ελεγχόμενα experiments για features,
helpers, normalizations, targets, models και signals. Το πλήρες, registry-backed
YAML ευρετήριο βρίσκεται στο
`docs/lab_components_reference.yaml`. Είναι reference αρχείο και όχι
runnable experiment: αντιγράφουμε μόνο τα blocks που θέλουμε να δοκιμάσουμε.

## Αρχεία αναφοράς

- `docs/lab_components_reference.yaml`: όλα τα registry names και όλες οι
  παράμετροι που εκτίθενται από callable signatures, μαζί με defaults.
- `config/lab/feature_signal_target_lab.yaml`: μεγάλο πρακτικό lab config.
- `docs/catalog/features.md`: outputs, inputs, causality και παραδείγματα feature.
- `docs/catalog/helpers.md`: πλήρη helper/normalization contracts.
- `docs/catalog/models.md`: nested model params, split, runtime και outputs.
- `docs/catalog/signals.md`: signal inputs, modes, thresholds και outputs.
- `docs/catalog/targets.md`: horizons, barriers, labels και target outputs.

## Ασφαλές workflow

1. Αντέγραψε ένα υπάρχον κοντινό experiment σε νέο αρχείο κάτω από
   `config/experiments/examples/` ή `config/lab/`.
2. Άλλαξε `dataset_id`, `run_name` και output directory ώστε να μη μπερδευτούν
   artifacts διαφορετικών δοκιμών.
3. Ενεργοποίησε πρώτα το ελάχιστο feature set που απαιτεί το component.
4. Πρόσθεσε ένα feature/helper/model/signal κάθε φορά. Έτσι το αποτέλεσμα του
   ablation παραμένει ερμηνεύσιμο.
5. Κράτησε χρονικό split ή walk-forward split. Μην κάνεις random shuffle σε
   trading labels.
6. Επιβεβαίωσε ότι το signal χρησιμοποιεί OOS prediction columns και ότι η
   εκτέλεση γίνεται στο επόμενο διαθέσιμο bar/open.
7. Φόρτωσε και επικύρωσε το config πριν από πλήρες run.

## Η σωστή δομή ενός feature step

```yaml
features:
  - step: volatility
    enabled: true
    params:
      returns_col: close_ret
      rolling_windows: [96]
      ewma_spans: []
      annualization_factor: null
    transforms:
      slope:
        params:
          source_col: close
          window: 96
          output_col: trend_slope_96
      ratio:
        items:
          - numerator_col: trend_slope_96
            denominator_col: close
            output_col: trend_fractional_slope_96
          - numerator_col: trend_fractional_slope_96
            denominator_col: vol_rolling_96
            output_col: trend_slope_vol_ratio_96
      threshold_flag:
        items:
          - source_col: trend_slope_vol_ratio_96
            threshold: 0.0
            op: gt
            output_col: trend_slope_positive_96
          - source_col: trend_slope_vol_ratio_96
            threshold: 1.0
            op: ge
            use_abs: true
            output_col: trend_slope_strong_96
      rising_flag:
        params:
          source_col: trend_slope_vol_ratio_96
          output_col: trend_slope_rising_96
```

Το `params` πρέπει να είναι παιδί του step. Το παλιό
`trend_slope_volatility` είναι compatibility-only, επειδή όλες οι στήλες του
συντίθενται πλέον από canonical helpers.

## Helpers και normalizations

Η σειρά μέσα σε κάθε feature step είναι:

```text
raw feature -> normalizations -> transforms -> outputs mapping
```

Παράδειγμα με normalization και δύο transform instances:

```yaml
features:
  - step: trend
    enabled: true
    params:
      price_col: close
      ema_spans: [50]
      sma_windows: []
    normalizations:
      range_position:
        params:
          value_col: close
          high_col: high
          low_col: low
          window: 96
          output_col: close_range_position_96
          clip: true
    transforms:
      ratio:
        items:
          - numerator_col: close
            denominator_col: close_ema_50
            subtract: 1.0
            output_col: close_over_ema_50
          - numerator_col: close
            denominator_col: atr_14
            subtract: 0.0
            output_col: close_over_atr_14
```

Χρησιμοποίησε `params` για μία εφαρμογή και `items` για πολλές εφαρμογές του
ίδιου helper. Ένα transform μπορεί να διαβάσει output προηγούμενου
normalization του ίδιου step.

## Target, model και signal

```yaml
model:
  kind: lightgbm_clf
  target:
    kind: forward_return
    horizon: 8
    threshold: 0.001
    label_col: label
    fwd_col: fwd_return
  feature_cols:
    - close_ret
    - atr_over_price_20
    - trend_slope_vol_ratio_96
  split:
    method: walk_forward
    train_size: 0.70
    test_size: 0.10
  runtime:
    seed: 7
    deterministic: true
    threads: 1
  params:
    n_estimators: 300
    learning_rate: 0.05

signals:
  kind: probability_threshold
  params:
    prob_col: pred_prob
    signal_col: signal
    upper: 0.60
    lower: 0.40
    mode: long_short_hold
```

Το target κοιτάζει μπροστά μόνο για να δημιουργήσει το label. Δεν επιτρέπεται
καμία target, future, signal ή in-sample prediction column μέσα στα
`feature_cols`. Για classifier signal χρησιμοποίησε OOS rows
(`pred_is_oos = true`).

## Γρήγορες δοκιμές

Από τη ρίζα του repository:

```powershell
.\.venv312\Scripts\python.exe -c "from src.utils.config import load_experiment_config; load_experiment_config('config/lab/my_experiment.yaml'); print('config OK')"
.\.venv312\Scripts\python.exe -m pytest tests/utils/test_config_catalog_integrity.py -q
```

Για να ανανεώσεις το YAML reference μετά από αλλαγή registry ή callable
signature:

```powershell
.\.venv312\Scripts\python.exe scripts/generate_lab_component_yaml_reference.py
```

## Checklist πριν από run

- Όλα τα `<required>` placeholders έχουν αντικατασταθεί.
- Κάθε input column παράγεται πριν χρησιμοποιηθεί.
- Τα output column names δεν συγκρούονται μεταξύ τους.
- Δεν υπάρχουν future/target columns στα model inputs.
- Το target horizon συμφωνεί με split trimming/purging.
- Το signal διαβάζει το σωστό prediction output.
- Το execution timing είναι explicit και causal.
- Costs, slippage και spread είναι ενεργά στο backtest.
- `run_name`, dataset και artifact paths είναι μοναδικά.

## Πώς διαβάζουμε το πλήρες YAML reference

Στο `docs/lab_components_reference.yaml`, κάτω από `features.canonical`, κάθε
entry αντιγράφεται αυτούσιο στη λίστα `features`.
Τα `features.compatibility_only` υπάρχουν για παλιά configs και δεν είναι η
προτιμώμενη επιλογή για νέο research. Τα `helpers.transforms` μπαίνουν κάτω από
`features[].transforms`, ενώ τα `normalizations.items` κάτω από
`features[].normalizations`.

Τα models και targets έχουν nested dictionary contracts που δεν φαίνονται στην
Python signature. Για αυτό το reference καταγράφει όλα τα registry kinds και
παραπέμπει στο αντίστοιχο πλήρες catalog, όπου υπάρχουν οι παράμετροι, τα
επιτρεπτά values και runnable YAML παραδείγματα. Signals που δέχονται dynamic
`**params` σημειώνονται με τον ίδιο τρόπο.
