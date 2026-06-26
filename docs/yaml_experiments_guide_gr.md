# Οδηγός YAML Experiments

Τελευταία ενημέρωση: 2026-06-26

## Βασική αρχή

Τα feature steps παράγουν raw columns μόνο. Κάθε παράγωγη στήλη, όπως ratio, RMS,
slope, rolling z-score ή clipping, δηλώνεται ως helper μέσα στο ίδιο feature step.

Το παλιό standalone `feature_transforms` step έχει καταργηθεί. Δεν υπάρχει
`tsfresh_rolling.py` helper και το `tsfresh_rolling` απορρίπτεται από το YAML
validation.

## Νέα δομή φακέλων

- `src/features/technical/`: raw indicators όπως `trend`, `atr`, `vwap`, `ppo`
- `src/features/helpers/`: γενικές μετατροπές όπως `ratio.py`, `rms.py`,
  `slope.py`, `rolling_clip.py`, `rolling_zscore.py`
- `src/features/helpers/normalizations/`: trading normalizations όπως
  `returns.py`, `atr_distances.py`, `volatility.py`, `rolling_zscores.py`
- `src/features/helpers/apply.py`: εφαρμόζει τα helper blocks μετά από κάθε raw
  feature step
- `src/features/helpers/registry.py`: registry για transform helpers και
  normalization helpers

## Σειρά εκτέλεσης

Για κάθε entry στο `features`:

1. Εκτελείται το raw feature function από το `step`.
2. Εφαρμόζονται τα `normalizations` του ίδιου step.
3. Εφαρμόζονται τα `transforms` του ίδιου step.
4. Εφαρμόζεται το optional `outputs` mapping.

Σε multi-asset run, τα `params_by_asset` αλλάζουν τα raw feature params.
Τα `transforms_by_asset` και `normalizations_by_asset` κάνουν override ανά helper
name, αλλά αφήνουν τα υπόλοιπα top-level helpers να ισχύουν.

## Παράδειγμα raw indicator με transforms

```yaml
features:
  - step: trend
    params:
      price_col: close
      sma_windows: []
      ema_spans: [50]
      ema_col_template: ema_50
      add_ratios: false
    transforms:
      ratio:
        enabled: true
        params:
          numerator_col: close
          denominator_col: ema_50
          output_col: close_over_ema_50
          subtract: 1.0
      rms:
        enabled: true
        params:
          source_col: ema_50
          window: 192
          shift: 0
          output_prefix: ema_50
```

Το `trend` παράγει μόνο `ema_50`. Τα `close_over_ema_50` και
`ema_50__root_mean_square` παράγονται από helpers.

## Παράδειγμα normalizations

```yaml
features:
  - step: atr
    params:
      high_col: high
      low_col: low
      close_col: close
      windows: [14]
      atr_col: atr_14
    normalizations:
      volatility:
        enabled: true
        params:
          close_col: close
          atr_col: atr_14
          add_atr_pct: true
          add_atr_percentile: true
          percentile_window: 252
      rolling_zscores:
        enabled: true
        params:
          columns: [atr_14]
          window: 96
          shift_stats: true
```

Τα normalizations δημιουργούν νέα columns, αλλά δεν είναι ML scalers. Οι ML
scalers γίνονται μόνο μέσα στα train folds.

## Παράδειγμα per-asset overrides

```yaml
features:
  - step: vwap
    params:
      high_col: high
      low_col: low
      close_col: close
      volume_col: volume
      windows: [20]
      vwap_col: vwap_20
    params_by_asset:
      GER40:
        windows: [32]
        vwap_col: vwap_32
    transforms:
      ratio:
        enabled: true
        params:
          numerator_col: close
          denominator_col: vwap_20
          output_col: close_over_vwap_20
          subtract: 1.0
    transforms_by_asset:
      GER40:
        ratio:
          enabled: true
          params:
            numerator_col: close
            denominator_col: vwap_32
            output_col: close_over_vwap_32
            subtract: 1.0
```

Για τα assets χωρίς override εφαρμόζεται το top-level `ratio`. Για `GER40`, το
`ratio` αντικαθίσταται από το asset-specific block.

## Διαθέσιμα transform helpers

- `ratio`: παράγει `numerator / denominator - subtract`
- `rms`: rolling root mean square
- `slope`: rolling linear slope
- `rolling_clip`: causal rolling quantile clipping
- `rolling_zscore`: causal rolling z-score helper

Κάθε helper δέχεται `enabled`, `params` ή `items`. Το `items` χρησιμοποιείται όταν
θέλουμε πολλαπλά outputs από τον ίδιο helper.

## Διαθέσιμα normalization helpers

- `returns`: past-looking simple και log returns
- `atr_distances`: ATR-normalized distances ανά ζεύγος columns
- `volatility`: `atr_pct` και rolling ATR percentile
- `rolling_zscores`: z-scores για λίστα columns με optional shifted stats

## Robust scaler στα models

Στα classifier models υποστηρίζονται πλέον:

```yaml
model:
  kind: logistic_regression_clf
  preprocessing:
    scaler: robust
```

Έγκυρες τιμές είναι `none`, `standard`, `robust`. Ο scaler γίνεται fit μόνο στο
train fold και εφαρμόζεται στο αντίστοιχο test fold.

## Migration κανόνες

- `trend.add_ratios` μένει `false` και τα ratios πάνε σε `transforms.ratio`.
- `vwap.add_distance` μένει `false` και το distance γίνεται `transforms.ratio`.
- `atr.add_over_price` μένει `false` και το normalized ATR γίνεται
  `transforms.ratio` ή `normalizations.volatility`.
- Παλιό `rolling_stat` με `root_mean_square` γίνεται `transforms.rms`.
- Παλιό `rolling_stat` με `slope` γίνεται `transforms.slope`.
- Δεν δημιουργείται `tsfresh_rolling.py`.
