# Κατάλογος Helpers

Τελευταία ενημέρωση: 2026-06-29

Αυτό το αρχείο τεκμηριώνει τους helpers του
`src/features/helpers/registry.py`. Οι helpers δεν είναι raw indicators. Είναι
παράγωγες, deterministic μετατροπές που εφαρμόζονται πάνω σε columns που έχουν
ήδη παραχθεί από feature steps ή από προηγούμενους helpers μέσα στο ίδιο step.

Στόχος τους είναι να κάνουν τα feature values πιο χρήσιμα για research και
models: ratios, ATR units, lags, slopes, flags, rolling summaries, z-scores,
percent ranks και volatility-adjusted values.

## Σειρά εκτέλεσης μέσα σε feature step

Για κάθε entry στο YAML `features`:

1. Τρέχει το raw `step`.
2. Τρέχουν τα `normalizations`.
3. Τρέχουν τα `transforms`.
4. Τρέχει το optional `outputs` mapping.

Αυτό σημαίνει ότι ένα `transform` μπορεί να χρησιμοποιήσει column που παρήχθη
από `normalizations` του ίδιου feature step. Αντίστροφα, ένα normalization δεν
πρέπει να βασίζεται σε transform που δηλώνεται πιο κάτω στο ίδιο step.

## Βασική YAML μορφή

Κάθε helper μπορεί να δηλωθεί με `params` όταν θες ένα output:

```yaml
features:
  - step: trend
    params:
      price_col: close
      ema_spans: [50]
      ema_col_template: ema_50
    transforms:
      ratio:
        params:
          numerator_col: close
          denominator_col: ema_50
          subtract: 1.0
          output_col: close_over_ema_50
```

Όταν θες πολλά outputs από τον ίδιο helper, χρησιμοποίησε `items`:

```yaml
features:
  - step: roofing_filter
    params:
      price_col: close
      output_col: roofing_filter_48_10
    transforms:
      crossing_flag:
        items:
          - source_col: roofing_filter_48_10
            threshold: 0.0
            direction: up
            output_col: roofing_filter_cross_up
          - source_col: roofing_filter_48_10
            threshold: 0.0
            direction: down
            output_col: roofing_filter_cross_down
```

`enabled: false` μπορεί να χρησιμοποιηθεί για να απενεργοποιηθεί block χωρίς να
σβηστεί από config.

## Πώς διαβάζεις helper values

- Ratios και distances γύρω από το `0` ή το `1` λένε σχέση με reference:
  `close / ema - 1 = 0.02` σημαίνει close 2% πάνω από EMA.
- ATR-scaled values είναι σε risk units: `1.5` σημαίνει απόσταση 1.5 ATR.
- Z-scores είναι σε standard deviations: `2.0` είναι υψηλή θετική έκπληξη.
- Percent ranks είναι σε `[0, 1]`: `0.95` σημαίνει πάνω από το 95% της
  πρόσφατης ιστορίας.
- Binary flags είναι `0/1`: `1` σημαίνει ότι η συνθήκη ισχύει στο current
  closed bar.
- Rolling helpers με `shift: 1`, `shift_stats: true` ή `shift_window: true`
  συγκρίνουν την τρέχουσα τιμή με ιστορία που τελειώνει στο `t-1`, άρα
  αποφεύγουν self-inclusion.

## Κατηγορίες helpers

| Κατηγορία | Helpers | Κύρια χρήση |
|---|---|---|
| Αριθμητικές σχέσεις | `ratio`, `reciprocal`, `difference`, `lag` | Scale-free σχέσεις, μνήμη και μεταβολές. |
| Rolling summaries | `rolling_mean`, `rolling_std`, `rolling_sum`, `rolling_linear_regression`, `rms`, `slope` | Baselines, dispersion, cumulative flow, trend quality και signal energy. |
| Rolling stabilization | `rolling_zscore`, `rolling_clip` | Causal normalization και outlier control. |
| Event flags | `threshold_flag`, `between_flag`, `crossing_flag`, `rising_flag` | Interpretable gates/events από continuous features. |
| Returns/risk normalizations | `returns`, `volatility`, `volatility_scaled_return`, `atr_distances`, `atr_scaled_distance` | Returns, ATR units και relative volatility. |
| Relative regime normalizations | `range_position`, `rolling_percent_rank`, `realized_vol_percentile`, `robust_zscore`, `rolling_zscores`, `volume_relative`, `rolling_beta_residual` | Regime position, robust scaling, participation και beta-adjusted residuals. |

## Transform helpers

### `ratio`

- Τι μετρά: τη σχέση δύο columns ως `numerator / denominator - subtract`, με
  optional `denominator_offset` και προστασία `eps` για μηδενικούς παρονομαστές.
- Προεπιλεγμένη έξοδος: `{numerator}_over_{denominator}`.
- Πώς διαβάζονται οι τιμές: όταν `subtract: 1.0`, το `0` σημαίνει ισότητα,
  `0.02` σημαίνει 2% πάνω, `-0.02` σημαίνει 2% κάτω. Χωρίς subtract, το `1.0`
  σημαίνει ισότητα.
- Πληροφορία: μετατρέπει raw price-level σχέση σε scale-free feature.
- Αιτιότητα: ασφαλές αν οι δύο input columns είναι point-in-time.

Παράδειγμα:

```yaml
transforms:
  ratio:
    params:
      numerator_col: close
      denominator_col: ema_50
      subtract: 1.0
      output_col: close_over_ema_50
```

Αν `close=101` και `ema_50=100`, το `close_over_ema_50` γίνεται `0.01`.

### `reciprocal`

- Τι μετρά: το αντίστροφο μιας column, `1 / source` ή `1 / abs(source)` όταν
  `use_abs: true`.
- Προεπιλεγμένη έξοδος: `{source}_reciprocal`.
- Πώς διαβάζονται οι τιμές: όσο μεγαλύτερο είναι το source, τόσο μικρότερο το
  reciprocal. Σε frequency features, reciprocal μπορεί να μετατρέψει frequency
  σε period.
- Πληροφορία: χρήσιμο για inverse volatility, inverse range ή cycle length από
  instantaneous frequency.
- Αιτιότητα: point-in-time transform. Τιμές με απόλυτο μέγεθος κάτω από `eps`
  γίνονται `NaN`.

Παράδειγμα:

```yaml
transforms:
  reciprocal:
    params:
      source_col: hilbert_frequency_64
      use_abs: true
      output_col: hilbert_dominant_cycle_64
```

Αν `hilbert_frequency_64=0.05`, τότε το reciprocal είναι `20`, δηλαδή κύκλος
περίπου 20 bars.

### `difference`

- Τι μετρά: μεταβολή μιας column έναντι παλαιότερης τιμής:
  `source_t - source_{t-periods}`. Με `reference_col`, μετρά διαφορά δύο
  columns στο ίδιο timestamp: `source_t - reference_t`.
- Προεπιλεγμένη έξοδος: `{source}_diff_{periods}`.
- Πώς διαβάζονται οι τιμές: θετικό σημαίνει ότι η column ανέβηκε σε σχέση με
  το lagged σημείο, αρνητικό ότι έπεσε, κοντά στο `0` ότι έμεινε σχεδόν ίδια.
- Πληροφορία: απλό slope/delta proxy για indicators, filters ή returns.
- Αιτιότητα: χρησιμοποιεί current και past values μόνο.

Παράδειγμα:

```yaml
transforms:
  difference:
    params:
      source_col: roofing_filter_48_10
      periods: 1
      output_col: roofing_filter_slope_1
```

Αν το roofing filter πάει από `-0.3` σε `0.2`, το difference είναι `0.5`.

### `lag`

- Τι μετρά: παρελθοντική τιμή μιας column με `source.shift(lag)`.
- Προεπιλεγμένη έξοδος: `{prefix}_{source}_{lag}`, με default `prefix: lag`.
- Πώς διαβάζονται οι τιμές: ίδια μονάδα με το source, αλλά αφορά `lag` bars
  πριν. Δεν είναι πρόβλεψη, είναι μνήμη.
- Πληροφορία: βοηθά tabular models να δουν persistence, reversal και state
  history χωρίς sequence model.
- Αιτιότητα: ασφαλές, γιατί κοιτά μόνο παρελθόν.

Παράδειγμα:

```yaml
transforms:
  lag:
    params:
      source_col: close_ret
      lag: 1
      output_col: lag_close_ret_1
```

Αν στο προηγούμενο bar το return ήταν `-0.004`, τότε στο current bar το
`lag_close_ret_1` είναι `-0.004`.

### `rolling_mean`

- Τι μετρά: trailing rolling mean μιας column.
- Προεπιλεγμένη έξοδος: `{source}_rolling_mean_{window}`.
- Πώς διαβάζονται οι τιμές: είναι το local baseline. Αν το source είναι πάνω
  από το rolling mean, βρίσκεται πάνω από την πρόσφατη μέση κατάσταση.
- Πληροφορία: baseline για ratios, deviations και regime comparisons.
- Αιτιότητα: το rolling window περιλαμβάνει το current closed bar. Με `shift: 1`
  το baseline τελειώνει στο `t-1`.

Παράδειγμα:

```yaml
transforms:
  rolling_mean:
    params:
      source_col: atr_14
      window: 192
      shift: 1
      output_col: atr_14_mean_192
```

Αν το `atr_14` είναι 20 και το shifted mean είναι 15, το ATR βρίσκεται πάνω από
το πρόσφατο baseline.

### `rolling_std`

- Τι μετρά: trailing rolling standard deviation μιας column.
- Προεπιλεγμένη έξοδος: `{source}_rolling_std_{window}`.
- Πώς διαβάζονται οι τιμές: υψηλή τιμή σημαίνει ότι το source είναι ασταθές ή
  έχει μεγάλη διασπορά στο lookback. Χαμηλή τιμή σημαίνει σταθερότητα.
- Πληροφορία: volatility-of-feature, dispersion και input για z-score.
- Αιτιότητα: trailing window, με optional `shift`.

Παράδειγμα:

```yaml
transforms:
  rolling_std:
    params:
      source_col: atr_14_pct
      window: 96
      output_col: atr_pct_vov_96
```

Υψηλό `atr_pct_vov_96` σημαίνει ότι η σχετική volatility αλλάζει απότομα.

### `rolling_sum`

- Τι μετρά: trailing άθροισμα μιας column.
- Προεπιλεγμένη έξοδος: `{source}_rolling_sum_{window}`.
- Πώς διαβάζονται οι τιμές: σε returns, θετικό sum σημαίνει cumulative upward
  drift, αρνητικό cumulative downward drift. Σε flow columns, δείχνει
  συσσωρευμένη πίεση.
- Πληροφορία: horizon momentum ή cumulative pressure.
- Αιτιότητα: trailing window, με optional `shift`.

Παράδειγμα:

```yaml
transforms:
  rolling_sum:
    params:
      source_col: close_logret
      window: 8
      output_col: close_logret_sum_8
```

`close_logret_sum_8=0.015` σημαίνει περίπου +1.5% log-return drift σε 8 bars.

### `rolling_linear_regression`

- Τι μετρά: trailing linear regression slope, intercept και `R2` πάνω σε μία
  source column.
- Προεπιλεγμένες έξοδοι: `{source}_rolling_slope_{window}`,
  `{source}_rolling_intercept_{window}`, `{source}_rolling_r2_{window}`.
- Πώς διαβάζονται οι τιμές: slope θετικό σημαίνει upward fitted trend, αρνητικό
  downward. `R2` κοντά στο `1` σημαίνει καθαρή γραμμική τάση, κοντά στο `0`
  noisy/choppy movement.
- Πληροφορία: χωρίζει trend direction από trend quality.
- Αιτιότητα: trailing window μόνο.

Παράδειγμα:

```yaml
features:
  - step: returns
    params:
      log: true
      col_name: close_logret
    transforms:
      rolling_linear_regression:
        source_col: close
        window: 96
        slope_col: rolling_r2_slope_96
        intercept_col: rolling_r2_intercept_96
        r2_col: rolling_r2_96
      rising_flag:
        source_col: rolling_r2_96
        periods: 1
        output_col: rolling_r2_96_rising
      threshold_flag:
        source_col: rolling_r2_96
        threshold: 0.60
        op: ge
        output_col: rolling_r2_96_ok
```

Το `rolling_r2_slope_96 > 0` με `rolling_r2_96=0.75` σημαίνει ανοδικό και
σχετικά καθαρό linear trend. Το helper χρησιμοποιεί πλήρες trailing window που
τελειώνει στο current timestamp· warm-up rows και windows με NaN/infinity
παραμένουν NaN. Σε finite flat window, slope είναι `0` και R2 `1`, σύμφωνα με
το canonical numerical contract.

### `rms`

- Τι μετρά: rolling root mean square, δηλαδή μέση ενέργεια/ένταση ενός signal.
- Προεπιλεγμένη έξοδος: `{source}__root_mean_square`.
- Πώς διαβάζονται οι τιμές: υψηλό RMS σημαίνει ότι το oscillator/return/filter
  έχει μεγάλη ένταση ανεξάρτητα από πρόσημο. Χαμηλό RMS σημαίνει αδύναμο signal.
- Πληροφορία: strength/energy feature, χρήσιμο για cycle amplitude ή volatility
  of an oscillator.
- Αιτιότητα: trailing window, με optional `shift`.

Παράδειγμα:

```yaml
transforms:
  rms:
    params:
      source_col: roofing_filter_48_10
      window: 48
      output_col: roofing_energy_48
```

Υψηλό `roofing_energy_48` σημαίνει ότι το cycle component έχει έντονη amplitude.

### `slope`

- Τι μετρά: fitted rolling linear slope μέσα σε trailing window.
- Προεπιλεγμένη έξοδος: `{source}_slope_{window}`.
- Πώς διαβάζονται οι τιμές: θετικό σημαίνει ότι το source ανεβαίνει μέσα στο
  window, αρνητικό ότι πέφτει. Μεγάλη απόλυτη τιμή σημαίνει γρήγορη αλλαγή.
- Πληροφορία: direction-of-change για indicators, όχι απλά level.
- Αιτιότητα: trailing window, με optional `shift`.

Παράδειγμα:

```yaml
transforms:
  slope:
    params:
      source_col: ema_50
      window: 8
      output_col: ema_50_slope_8
```

`ema_50_slope_8 > 0` δείχνει ότι το EMA ανεβαίνει στο πρόσφατο παράθυρο.

### `rolling_zscore`

- Τι μετρά: `(source - rolling_mean) / rolling_std` με default `shift: 1`.
- Προεπιλεγμένη έξοδος: `{source}_zscore_{window}`.
- Πώς διαβάζονται οι τιμές: `0` κοντά στο prior rolling baseline, `1` μία
  standard deviation πάνω, `2` πολύ υψηλή θετική απόκλιση, `-2` πολύ χαμηλή.
- Πληροφορία: κάνει unbounded/level-dependent columns συγκρίσιμες με τη δική
  τους πρόσφατη ιστορία.
- Αιτιότητα: default shifted stats, άρα το current value δεν συμμετέχει στο
  mean/std που το κανονικοποιεί.

Παράδειγμα:

```yaml
transforms:
  rolling_zscore:
    params:
      source_col: atr_14_pct
      window: 252
      output_col: atr_pct_z_252
```

`atr_pct_z_252=2.1` σημαίνει ότι το current ATR/close είναι πολύ υψηλό σε σχέση
με τις προηγούμενες 252 παρατηρήσεις.

### `rolling_clip`

- Τι μετρά: causal clipping μιας column μέσα σε rolling quantile bounds.
- Προεπιλεγμένη έξοδος: `{source}_rollclip_{window}`.
- Πώς διαβάζονται οι τιμές: οι ακραίες τιμές κόβονται στο prior lower/upper
  quantile. Αν δεν είναι ακραία, η τιμή μένει ίδια.
- Πληροφορία: winsorization για spikes, fat tails και unstable scalers.
- Αιτιότητα: default `shift: 1`, άρα τα quantile bounds προέρχονται από prior
  history.

Παράδειγμα:

```yaml
transforms:
  rolling_clip:
    params:
      source_col: close_ret
      window: 2520
      lower_q: 0.01
      upper_q: 0.99
      output_col: close_ret_clipped
```

Αν ένα return είναι πάνω από το ιστορικό 99ο percentile, αντικαθίσταται από το
rolling 99ο percentile.

### `threshold_flag`

- Τι μετρά: binary comparison με threshold (`gt`, `ge`, `lt`, `le`, `eq`, `ne`)
  και optional `use_abs`.
- Προεπιλεγμένη έξοδος: `{source}_{op}_{threshold}`.
- Πώς διαβάζονται οι τιμές: `1` σημαίνει ότι η σύγκριση ισχύει, `0` ότι δεν
  ισχύει ή ότι το source είναι missing.
- Πληροφορία: μετατρέπει continuous feature σε interpretable gate.
- Αιτιότητα: current-bar deterministic flag.

Παράδειγμα:

```yaml
transforms:
  threshold_flag:
    params:
      source_col: trend_slope_vol_ratio_96
      threshold: 1.0
      op: ge
      use_abs: true
      output_col: trend_slope_strong
```

`trend_slope_strong=1` σημαίνει ότι η απόλυτη trend strength είναι τουλάχιστον
1 volatility unit.

### `between_flag`

- Τι μετρά: αν μια τιμή βρίσκεται μέσα σε range `[lower, upper]`, με
  configurable boundary inclusion.
- Προεπιλεγμένη έξοδος: `{source}_between_{lower}_{upper}`.
- Πώς διαβάζονται οι τιμές: `1` σημαίνει μέσα στο αποδεκτό range, `0` έξω από
  αυτό.
- Πληροφορία: χρήσιμο για valid cycle periods, neutral oscillator zones ή
  allowed risk regimes.
- Αιτιότητα: current-bar deterministic flag.

Παράδειγμα:

```yaml
transforms:
  between_flag:
    params:
      source_col: hilbert_dominant_cycle_64
      lower: 10
      upper: 48
      output_col: hilbert_cycle_ok
```

`hilbert_cycle_ok=1` σημαίνει ότι το estimated cycle length είναι μεταξύ 10 και
48 bars.

### `crossing_flag`

- Τι μετρά: event όταν η τιμή περνά threshold από κάτω προς τα πάνω ή από πάνω
  προς τα κάτω.
- Προεπιλεγμένη έξοδος: `{source}_cross_{direction}_{threshold}`.
- Πώς διαβάζονται οι τιμές: `1` μόνο στο bar που έγινε το crossing. Δεν μένει
  ενεργό μετά το event.
- Πληροφορία: καλύτερο timing signal από static level όταν σε ενδιαφέρει η
  μετάβαση.
- Αιτιότητα: χρησιμοποιεί `t` και `t-1`.

Παράδειγμα:

```yaml
transforms:
  crossing_flag:
    params:
      source_col: roofing_filter_48_10
      threshold: 0.0
      direction: up
      output_col: roofing_cross_up
```

Αν το roofing filter ήταν `-0.1` στο προηγούμενο bar και `0.2` τώρα, το
`roofing_cross_up` γίνεται `1`.

### `rising_flag`

- Τι μετρά: αν `source_t > source_{t-periods}`.
- Προεπιλεγμένη έξοδος: `{source}_rising`.
- Πώς διαβάζονται οι τιμές: `1` σημαίνει ότι το feature ανέβηκε έναντι του
  lagged σημείου, `0` ότι δεν ανέβηκε ή λείπουν δεδομένα.
- Πληροφορία: απλό trend-of-feature flag.
- Αιτιότητα: χρησιμοποιεί μόνο lagged comparison.

Παράδειγμα:

```yaml
transforms:
  rising_flag:
    params:
      source_col: rolling_r2_96
      periods: 3
      output_col: rolling_r2_rising_3
```

`rolling_r2_rising_3=1` σημαίνει ότι η trend quality βελτιώθηκε σε σχέση με 3
bars πριν.

## Normalization helpers

### `returns`

- Τι μετρά: multi-horizon simple returns και optional log returns από
  `close_col`.
- Προεπιλεγμένες έξοδοι: `return_{window}` και, όταν `log_returns: true`,
  `log_return_{window}`.
- Πώς διαβάζονται οι τιμές: θετικό σημαίνει cumulative rise στο window,
  αρνητικό cumulative fall. Log returns αθροίζονται καλύτερα σε horizons.
- Πληροφορία: μετατρέπει price levels σε scale-free movement.
- Αιτιότητα: χρησιμοποιεί `close_t` και `close_{t-window}`.

Παράδειγμα:

```yaml
normalizations:
  returns:
    params:
      close_col: close
      windows: [1, 4, 8]
      log_returns: true
```

Αν `close_t=102` και `close_{t-4}=100`, τότε `return_4=0.02`.

### `volatility`

- Τι μετρά: normalized ATR context, συνήθως `ATR / close` και rolling ATR
  percentile.
- Προεπιλεγμένες έξοδοι: `{atr_col}_pct` και `{atr_col}_percentile_{window}`.
- Πώς διαβάζονται οι τιμές: `atr_pct=0.006` σημαίνει ATR ίσο με 0.6% του close.
  Percentile `0.90` σημαίνει ATR υψηλότερο από το 90% του trailing window.
- Πληροφορία: κάνει absolute ATR comparable μεταξύ assets και price levels.
- Αιτιότητα: `atr_pct` είναι point-in-time. Το percentile ranking γίνεται μέσα
  στο trailing window του helper.

Παράδειγμα:

```yaml
normalizations:
  volatility:
    params:
      close_col: close
      atr_col: atr_14
      add_atr_pct: true
      add_atr_percentile: true
      percentile_window: 252
```

Αν `atr_14=6` και `close=1000`, τότε `atr_14_pct=0.006`.

### `volatility_scaled_return`

- Τι μετρά: `return / volatility`.
- Προεπιλεγμένη έξοδος: `{return_col}_over_{volatility_col}`.
- Πώς διαβάζονται οι τιμές: θετικό σημαίνει positive return per unit risk,
  αρνητικό negative return per unit risk. Απόλυτη τιμή μεγαλύτερη σημαίνει
  μεγαλύτερη κίνηση σε σχέση με volatility.
- Πληροφορία: Sharpe-like local movement, συγκρίσιμο μεταξύ regimes.
- Αιτιότητα: ασφαλές αν return και volatility inputs είναι PIT.

Παράδειγμα:

```yaml
normalizations:
  volatility_scaled_return:
    params:
      return_col: return_8
      volatility_col: vol_rolling_96
      output_col: return_8_over_vol_96
```

Αν `return_8=0.012` και `vol_rolling_96=0.006`, το output είναι `2.0`.

### `atr_distances`

- Τι μετρά: πολλές pairwise αποστάσεις `(base_col - ref_col) / ATR`.
- Έξοδοι: όνομα από κάθε `pairs[].name`.
- Πώς διαβάζονται οι τιμές: `1.0` σημαίνει ότι το base είναι 1 ATR πάνω από
  το reference, `-0.5` σημαίνει μισό ATR κάτω.
- Πληροφορία: μετατρέπει price distances σε risk units για stop/target
  geometry και structural levels.
- Αιτιότητα: ασφαλές αν base/reference/ATR columns είναι PIT.

Παράδειγμα:

```yaml
normalizations:
  atr_distances:
    params:
      atr_col: atr_14
      pairs:
        - name: close_minus_vwap_atr
          base_col: close
          ref_col: vwap_20
```

Αν `close=101`, `vwap_20=100` και `atr_14=2`, τότε το output είναι `0.5`.

### `atr_scaled_distance`

- Τι μετρά: μία generic απόσταση `(base_col - ref_col) / atr_col`.
- Προεπιλεγμένη έξοδος: `{base_col}_minus_{ref_col}_over_{atr_col}`.
- Πώς διαβάζονται οι τιμές: ίδια ερμηνεία με `atr_distances`, αλλά για ένα
  ζεύγος columns.
- Πληροφορία: κεντρικό helper για price-like indicators όπως MA, VWAP,
  support/resistance και Ehlers lines.
- Αιτιότητα: ασφαλές αν inputs είναι PIT.

Παράδειγμα:

```yaml
normalizations:
  atr_scaled_distance:
    params:
      base_col: close
      ref_col: ema_50
      atr_col: atr_14
      output_col: close_minus_ema_50_atr
```

`close_minus_ema_50_atr=1.2` σημαίνει close 1.2 ATR πάνω από EMA 50.

### `range_position`

- Τι μετρά: θέση του `value_col` μέσα στο trailing high-low range:
  `(value - rolling_low) / (rolling_high - rolling_low)`.
- Προεπιλεγμένη έξοδος: `{value_col}_range_position_{window}`.
- Πώς διαβάζονται οι τιμές: `0` κοντά στο rolling low, `1` κοντά στο rolling
  high, `0.5` στο μέσο. Με `clip: true`, οι τιμές περιορίζονται στο `[0, 1]`.
- Πληροφορία: overextension, close pressure και range location.
- Αιτιότητα: trailing high/low window μέχρι το current closed bar.

Παράδειγμα:

```yaml
normalizations:
  range_position:
    params:
      value_col: close
      high_col: high
      low_col: low
      window: 48
      output_col: close_range_pos_48
```

`close_range_pos_48=0.9` σημαίνει ότι το close είναι κοντά στο υψηλό του
τελευταίου 48-bar range.

### `rolling_percent_rank`

- Τι μετρά: percentile rank της τρέχουσας τιμής απέναντι στο trailing history.
- Προεπιλεγμένη έξοδος: `{source_col}_percent_rank_{window}`.
- Πώς διαβάζονται οι τιμές: `0.95` σημαίνει ότι η τρέχουσα τιμή είναι πάνω από
  περίπου το 95% της prior ιστορίας. `0.05` σημαίνει πολύ χαμηλή τιμή.
- Πληροφορία: non-parametric regime position, robust σε outliers.
- Αιτιότητα: default `shift_window: true`, άρα η τρέχουσα τιμή κατατάσσεται
  απέναντι σε ιστορία που τελειώνει στο `t-1`.

Παράδειγμα:

```yaml
normalizations:
  rolling_percent_rank:
    params:
      source_col: atr_14_pct
      window: 252
      output_col: atr_pct_rank_252
```

`atr_pct_rank_252=0.92` σημαίνει high-vol regime σε σχέση με τις προηγούμενες
252 παρατηρήσεις.

### `realized_vol_percentile`

- Τι μετρά: percentile rank μιας realized volatility column.
- Προεπιλεγμένη έξοδος: `{volatility_col}_percentile_{window}`.
- Πώς διαβάζονται οι τιμές: ίδια με `rolling_percent_rank`, αλλά το όνομα και
  η πρόθεση είναι συγκεκριμένα για volatility.
- Πληροφορία: high/low volatility regime χωρίς να βασίζεται σε raw vol scale.
- Αιτιότητα: wrapper πάνω στο `rolling_percent_rank`, με default shifted
  history.

Παράδειγμα:

```yaml
normalizations:
  realized_vol_percentile:
    params:
      volatility_col: vol_rolling_96
      window: 504
      output_col: vol_96_percentile_504
```

`vol_96_percentile_504=0.10` σημαίνει πολύ ήσυχο realized-vol περιβάλλον.

### `robust_zscore`

- Τι μετρά: `(x - rolling_median) / (MAD * mad_scale)`.
- Προεπιλεγμένη έξοδος: `{source_col}_robust_zscore_{window}`.
- Πώς διαβάζονται οι τιμές: όπως z-score, αλλά με median/MAD. `2` σημαίνει
  υψηλή θετική απόκλιση, `-2` υψηλή αρνητική απόκλιση.
- Πληροφορία: standardized surprise που αντέχει καλύτερα fat tails και spikes.
- Αιτιότητα: default `shift_stats: true`.

Παράδειγμα:

```yaml
normalizations:
  robust_zscore:
    params:
      source_col: close_ret
      window: 252
      output_col: close_ret_robust_z_252
```

`close_ret_robust_z_252=-2.5` σημαίνει πολύ αρνητικό return σε σχέση με prior
median/MAD history.

### `rolling_zscores`

- Τι μετρά: rolling mean/std z-score για πολλές columns μαζί.
- Προεπιλεγμένες έξοδοι: `{col}_zscore_{window}` για κάθε column.
- Πώς διαβάζονται οι τιμές: `0` baseline, `> 2` high positive outlier,
  `< -2` high negative outlier.
- Πληροφορία: γρήγορο batch normalization για πολλά unbounded features.
- Αιτιότητα: default `shift_stats: true`.

Παράδειγμα:

```yaml
normalizations:
  rolling_zscores:
    params:
      columns: [atr_14, vov_atr_96]
      window: 96
      shift_stats: true
```

Παράγει `atr_14_zscore_96` και `vov_atr_96_zscore_96`.

### `volume_relative`

- Τι μετρά: `volume / rolling_mean(volume)` και optional shifted volume
  z-score όταν δοθεί `zscore_col`.
- Προεπιλεγμένη έξοδος: `{volume_col}_relative_{window}`.
- Πώς διαβάζονται οι τιμές: `1.0` σημαίνει normal volume, `2.0` διπλάσιο από
  το baseline, `0.5` μισό από το baseline.
- Πληροφορία: abnormal participation/liquidity context.
- Αιτιότητα: default `shift_stats: true`.

Παράδειγμα:

```yaml
normalizations:
  volume_relative:
    params:
      volume_col: volume
      window: 96
      output_col: volume_relative_96
      zscore_col: volume_z_96
```

`volume_relative_96=2.3` σημαίνει volume 2.3 φορές πάνω από το prior rolling
average.

### `rolling_beta_residual`

- Τι μετρά: residual του asset return αφού αφαιρεθεί trailing single-factor
  alpha/beta σχέση με benchmark return.
- Προεπιλεγμένη έξοδος: `{asset_return_col}_residual_vs_{benchmark_return_col}_{window}`.
- Πώς διαβάζονται οι τιμές: θετικό residual σημαίνει ότι το asset υπεραπέδωσε
  σε σχέση με ό,τι εξηγεί το benchmark beta. Αρνητικό σημαίνει underperformance.
- Πληροφορία: idiosyncratic move, χρήσιμο για index/asset baskets και
  cross-asset normalization.
- Αιτιότητα: default `shift_stats: true`, άρα beta/alpha εκτιμώνται μέχρι `t-1`.

Παράδειγμα:

```yaml
normalizations:
  rolling_beta_residual:
    params:
      asset_return_col: us100_return_1
      benchmark_return_col: spx500_return_1
      window: 252
      residual_col: us100_idio_ret_252
      beta_col: us100_beta_spx_252
```

Αν `us100_idio_ret_252=0.006`, το US100 έκανε περίπου +0.6% περισσότερο από
ό,τι θα περίμενε το rolling beta του έναντι SPX500.

## Πρακτικές επιλογές ανά ανάγκη

| Αν χρειάζεσαι | Προτίμησε | Γιατί |
|---|---|---|
| Price distance από EMA/VWAP/support | `atr_scaled_distance` ή `ratio` με `subtract: 1.0` | ATR units για risk, ratio για percent distance. |
| Momentum χωρίς price scale | `returns`, `rolling_sum`, `volatility_scaled_return` | Returns και risk-adjusted returns συγκρίνονται καλύτερα. |
| Outlier-safe continuous feature | `robust_zscore`, `rolling_clip`, `rolling_percent_rank` | Καλύτερα σε fat-tailed intraday data. |
| Event από oscillator | `crossing_flag`, `threshold_flag`, `between_flag` | Το event/gate είναι πιο ερμηνεύσιμο από raw level. |
| History για tabular model | `lag` μετά από normalization | Το μοντέλο βλέπει παρελθοντική κατάσταση χωρίς leakage. |
| Trend direction και quality | `slope` ή `rolling_linear_regression` | Η κλίση δίνει side, το `R2` δίνει καθαρότητα. |
| Volume participation | `volume_relative` | Κάνει volume συγκρίσιμο με το πρόσφατο baseline. |

## Anti-leakage checklist

- Για rolling z-score, percentile και clip, προτίμησε shifted stats/window.
- Μην κάνεις global scaler πριν από temporal split. Οι helpers είναι feature
  engineering, όχι αντικατάσταση του train-fold preprocessing.
- Μην βάζεις raw price distances σε multi-asset model. Μετέτρεψέ τα σε ATR
  units ή percent ratios.
- Binary flags από current candle είναι causal μόνο αν η εκτέλεση γίνεται αφού
  έχει κλείσει το candle, συνήθως next bar/open.
- Για HMM, beta residuals ή οποιοδήποτε learned/estimated regime, κράτα σαφές
  τι εκτιμάται στο train history και τι εφαρμόζεται out-of-sample.
## Shared Trade-Path Helpers

### `simulate_barrier_trade_outcome`

Location: `src/utils/trade_path.py`

Purpose:

- Central deterministic manual-barrier outcome simulation for single-entry, single-exit trades.
- Used by `manual_barrier` backtests and by `path_dependent_r` target construction.

Contract:

- Default causal timing is signal at close `t`, entry at `open[t+1]`.
- The helper delegates intrabar TP/SL/time-path decisions to the existing long/short path simulators.
- It centralizes stop/take-profit distances, long/short orientation, same-bar TP/SL tie-break, costs, slippage, gross/net return, gross/net R, MFE, and MAE.

R math:

- `risk_distance = volatility[t] * stop_loss_r` under `volatility_stop`.
- `gross_r = gross_return / risk_distance`.
- `net_r = (gross_return - round_trip_cost - slippage_drag) / risk_distance`.

Leakage policy:

- The helper does not build candidates. Callers must pass causal signal/candidate rows.
- Targets that call it, such as `path_dependent_r`, keep non-candidates and incomplete tail rows unlabeled by default.
## Stacked Trade-Filter Helpers

`src.meta.stacked_trade_filter` builds the controlled feature matrix and
walk-forward training loop for candidate-only meta filters.

Core helpers:

- `build_causal_meta_features`: adds primary forecast transforms, oriented
  trend features, regime features, candle/path-risk features, and rolling price
  slope/R2 trend-quality columns. Rolling transforms are trailing and causal.
- `train_stacked_meta_filter`: trains sequential meta folds on older completed
  candidates only. It rejects candidate rows whose primary `pred_ret` is not
  OOS, applies purge before each meta test fold, fits preprocessing inside each
  fold, and optionally fits sigmoid calibration on the last internal training
  slice only.
- `build_meta_filtered_signal`: emits `primary_candidate_side` only where
  `meta_pred_is_oos=true`, the row is a candidate, and `meta_pred_prob` passes
  the threshold.

Output convention:

```text
meta_pred_raw_prob  raw classifier probability
meta_pred_prob      calibrated probability when configured, otherwise raw
meta_pred_is_oos    true only on meta test-fold candidate rows
meta_fold           meta walk-forward fold id
```

Forbidden feature policy: target/path outcome columns such as `meta_net_r`,
`meta_label_*`, `meta_exit_reason`, and meta prediction columns are rejected
from the feature matrix.
