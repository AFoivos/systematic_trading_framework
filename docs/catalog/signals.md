<!-- Το αρχείο παράγεται από scripts/generate_component_catalog_appendices.py. Μην αλλάζετε χειροκίνητα τις registry-backed ενότητες. -->

# Κατάλογος Signals

Τελευταία ενημέρωση: 2026-07-31

Τα signals μετατρέπουν features ή OOS model outputs σε πλευρά ή μέγεθος θέσης. Κατά σύμβαση `+1` σημαίνει αγορά, `-1` πώληση και `0` ουδέτερη θέση, εκτός αν η συγκεκριμένη ενότητα ορίζει συνεχή έκθεση.

Ο κατάλογος συνδέεται απευθείας με τα registries: κάθε ενεργό όνομα του κώδικα έχει ξεχωριστή αναλυτική ενότητα, ερμηνεία τιμών, χρονικό συμβόλαιο και πλήρες YAML. Τα ονόματα κώδικα, οι στήλες και οι YAML τιμές παραμένουν στα αγγλικά για να αντιγράφονται αυτούσια· όλο το επεξηγηματικό κείμενο είναι ελληνικό.

Στα YAML, `<required>` σημαίνει υποχρεωτική τιμή που πρέπει να αντικατασταθεί και `<configured>` επιλογή χωρίς ασφαλή καθολική προεπιλογή. Το `null` σημαίνει ότι η λειτουργία είναι προαιρετική ή ότι ο υπολογιστής θα επιλέξει το προεπιλεγμένο όνομα/συμπεριφορά.

## Ενεργά signals

### `barrier_expected_value`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει calibrated πιθανότητες upper/lower/no-hit barrier σε cost-aware θέση αναμενόμενης αξίας. Υπολογίζει ξεχωριστό EV για αγορά και πώληση, αφαιρεί spread, προμήθειες και ολίσθηση, και εκπέμπει μόνο την πλευρά που περνά probability, calibration, OOS και minimum-edge gates.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `upper_probability_col`, `lower_probability_col`, `no_hit_probability_col`, `calibrated_col`, `pred_is_oos_col`, `atr_col`, `price_col`, `spread_col`, `activity_col`, `no_hit_long_return_col`, `no_hit_short_return_col`, `signal_col`, `long_ev_col`, `short_ev_col`, `selected_ev_col`, `expected_edge_col`, `round_trip_cost_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `upper_probability_col`, `lower_probability_col`, `no_hit_probability_col`, `calibrated_col`, `pred_is_oos_col`, `atr_col`, `price_col`, `spread_col`, `activity_col`, `no_hit_long_return_col`, `no_hit_short_return_col`, `upper_atr_multiplier`, `lower_atr_multiplier`, `minimum_expected_edge`, `minimum_class_probability`, `cost_safety_factor`, `cost_per_turnover`, `slippage_per_turnover`, `maximum_no_hit_probability`, `allow_long`, `allow_short`, `entry_delay_bars`, `maximum_spread`, `minimum_activity`, `maximum_position`, `signal_col`, `long_ev_col`, `short_ev_col`, `selected_ev_col`, `expected_edge_col`, `round_trip_cost_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: barrier_expected_value
  params:
    upper_probability_col: pred_prob_upper
    lower_probability_col: pred_prob_lower
    no_hit_probability_col: pred_prob_no_hit
    calibrated_col: pred_probability_calibrated
    pred_is_oos_col: pred_is_oos
    atr_col: atr_14
    price_col: close
    spread_col: spread_bps
    activity_col: null
    no_hit_long_return_col: null
    no_hit_short_return_col: null
    upper_atr_multiplier: 1.0
    lower_atr_multiplier: 1.0
    minimum_expected_edge: 0.0
    minimum_class_probability: 0.0
    cost_safety_factor: 1.25
    cost_per_turnover: 0.0
    slippage_per_turnover: 0.0
    maximum_no_hit_probability: 1.0
    allow_long: true
    allow_short: true
    entry_delay_bars: 1
    maximum_spread: null
    minimum_activity: null
    maximum_position: 1.0
    signal_col: barrier_ev_signal
    long_ev_col: barrier_ev_long
    short_ev_col: barrier_ev_short
    selected_ev_col: barrier_ev_selected
    expected_edge_col: barrier_expected_edge
    round_trip_cost_col: barrier_round_trip_cost
```

### `c1_trend_pullback_vwap`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει pullback προς VWAP μέσα σε επιβεβαιωμένη τάση, με φίλτρα ορμής, μεταβλητότητας και ποιότητας setup. Θετική ή αρνητική πλευρά δηλώνει κατεύθυνση continuation και μηδέν απόρριψη· τα diagnostic flags εξηγούν αν απέτυχε τάση, pullback, spread ή timing.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `trend_regime_col`, `long_trigger_col`, `short_trigger_col`, `ppo_hist_col`, `ppo_above_signal_col`, `ppo_below_signal_col`, `mfi_col`, `stoch_k_col`, `stoch_d_col`, `zscore_momentum_col`, `volatility_regime_col`, `trend_quality_col`, `long_candidate_col`, `short_candidate_col`, `long_candidate_strict_col`, `short_candidate_strict_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `mode`, `trend_regime_col`, `long_trigger_col`, `short_trigger_col`, `ppo_hist_col`, `ppo_above_signal_col`, `ppo_below_signal_col`, `mfi_col`, `stoch_k_col`, `stoch_d_col`, `zscore_momentum_col`, `volatility_regime_col`, `trend_quality_col`, `mfi_long_min`, `mfi_long_max`, `mfi_short_min`, `mfi_short_max`, `long_zscore_min`, `short_zscore_max`, `max_volatility_regime`, `strict_trend_quality_min`, `strict_mfi_long_min`, `strict_mfi_short_max`, `strict_long_zscore_min`, `strict_short_zscore_max`, `use_strict_signal`, `long_candidate_col`, `short_candidate_col`, `long_candidate_strict_col`, `short_candidate_strict_col`, `signal_col`, `candidate_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: c1_trend_pullback_vwap
  params:
    mode: long_short
    trend_regime_col: trend_regime
    long_trigger_col: vwap_rms_ema_cross_long_setup
    short_trigger_col: vwap_rms_ema_cross_short_setup
    ppo_hist_col: ppo_hist
    ppo_above_signal_col: ppo_above_signal
    ppo_below_signal_col: ppo_below_signal
    mfi_col: mfi_14
    stoch_k_col: stoch_rsi_k
    stoch_d_col: stoch_rsi_d
    zscore_momentum_col: zscore_momentum_20
    volatility_regime_col: volatility_regime
    trend_quality_col: rolling_r2_96
    mfi_long_min: 40.0
    mfi_long_max: 80.0
    mfi_short_min: 20.0
    mfi_short_max: 60.0
    long_zscore_min: 0.0
    short_zscore_max: 0.0
    max_volatility_regime: 1.0
    strict_trend_quality_min: 0.35
    strict_mfi_long_min: 50.0
    strict_mfi_short_max: 50.0
    strict_long_zscore_min: 0.5
    strict_short_zscore_max: -0.5
    use_strict_signal: false
    long_candidate_col: c1_long_candidate
    short_candidate_col: c1_short_candidate
    long_candidate_strict_col: c1_long_candidate_strict
    short_candidate_strict_col: c1_short_candidate_strict
    signal_col: signal_side
    candidate_col: signal_candidate
    output_cols:
    - c1_long_candidate
    - c1_short_candidate
    - signal_side
    - signal_candidate
```

### `c2_regime_aware_momentum`

**Τι μετρά και τι πληροφορία δίνει.** Εκπέμπει momentum θέση μόνο όταν το τρέχον regime τάσης και μεταβλητότητας θεωρείται κατάλληλο. Το signal συνδυάζει κατεύθυνση ορμής με gates regime και κόστους, ώστε ισχυρή ακατέργαστη κίνηση να απορρίπτεται όταν το περιβάλλον είναι ασταθές ή μη συμβατό.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `trend_regime_col`, `ppo_col`, `ppo_signal_col`, `ppo_hist_col`, `adx_col`, `roc_col`, `zscore_momentum_col`, `volatility_regime_col`, `long_candidate_col`, `short_candidate_col`, `signal_col`, `candidate_col`, `bullish_trend_col`, `bearish_trend_col`, `adx_pass_col`, `ppo_long_pass_col`, `ppo_short_pass_col`, `roc_long_pass_col`, `roc_short_pass_col`, `zscore_long_pass_col`, `zscore_short_pass_col`, `volatility_pass_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `mode`, `trend_regime_col`, `ppo_col`, `ppo_signal_col`, `ppo_hist_col`, `adx_col`, `roc_col`, `zscore_momentum_col`, `volatility_regime_col`, `adx_min`, `zscore_long_min`, `zscore_short_max`, `roc_long_min`, `roc_short_max`, `use_ppo_signal_cross`, `allowed_volatility_regimes`, `long_candidate_col`, `short_candidate_col`, `signal_col`, `candidate_col`, `bullish_trend_col`, `bearish_trend_col`, `adx_pass_col`, `ppo_long_pass_col`, `ppo_short_pass_col`, `roc_long_pass_col`, `roc_short_pass_col`, `zscore_long_pass_col`, `zscore_short_pass_col`, `volatility_pass_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: c2_regime_aware_momentum
  params:
    mode: long_short
    trend_regime_col: trend_regime
    ppo_col: ppo
    ppo_signal_col: ppo_signal
    ppo_hist_col: ppo_hist
    adx_col: adx_14
    roc_col: roc_12
    zscore_momentum_col: zscore_momentum_20
    volatility_regime_col: volatility_regime
    adx_min: 18.0
    zscore_long_min: 0.0
    zscore_short_max: 0.0
    roc_long_min: 0.0
    roc_short_max: 0.0
    use_ppo_signal_cross: true
    allowed_volatility_regimes:
    - 0
    - 1
    long_candidate_col: c2_long_candidate
    short_candidate_col: c2_short_candidate
    signal_col: c2_signal
    candidate_col: c2_signal_candidate
    bullish_trend_col: c2_bullish_trend
    bearish_trend_col: c2_bearish_trend
    adx_pass_col: c2_adx_pass
    ppo_long_pass_col: c2_ppo_long_pass
    ppo_short_pass_col: c2_ppo_short_pass
    roc_long_pass_col: c2_roc_long_pass
    roc_short_pass_col: c2_roc_short_pass
    zscore_long_pass_col: c2_zscore_long_pass
    zscore_short_pass_col: c2_zscore_short_pass
    volatility_pass_col: c2_volatility_regime_pass
    output_cols:
    - c2_long_candidate
    - c2_short_candidate
    - c2_signal
    - c2_signal_candidate
    - c2_adx_pass
    - c2_ppo_long_pass
    - c2_ppo_short_pass
    - c2_roc_long_pass
    - c2_roc_short_pass
    - c2_zscore_long_pass
    - c2_zscore_short_pass
    - c2_volatility_regime_pass
```

### `qms_alpha_strategy`

**Τι μετρά και τι πληροφορία δίνει.** Υλοποιεί επιλεγμένη υπόθεση alpha πάνω στις KDS, RLVS και LMDS καταστάσεις. Οι rolling thresholds είναι μετατοπισμένοι κατά ένα bar και το candidate ενεργοποιείται είτε στην είσοδο σε κατάσταση είτε όσο αυτή διαρκεί, ανάλογα με το `signal_on_crossing`.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `strategy`, `lookback_bars`, `min_periods`, `signal_on_crossing`, `signal_col`, `candidate_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: qms_alpha_strategy
  params:
    strategy: kds_pullback_continuation
    lookback_bars: 8064
    min_periods: 2016
    signal_on_crossing: true
    signal_col: qms_alpha_signal
    candidate_col: qms_alpha_candidate
```

### `qms_trend_momentum_vol`

**Τι μετρά και τι πληροφορία δίνει.** Συνδυάζει QMS κατεύθυνση τάσης, momentum και volatility state σε ενιαία πλευρά. Θέση εμφανίζεται μόνο όταν οι τρεις διαστάσεις συμφωνούν με τα configured thresholds· διαφορετικά παραμένει flat ώστε να αποφεύγεται trading σε αμφίσημο state.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των τις σταθερές προεπιλογές του υπολογιστή. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `combination`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: qms_trend_momentum_vol
  params:
    combination: trend_momentum_vol
    mode: long_short
```

### `ehlers_continuation_long`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει long continuation όταν Ehlers trend και cycle φίλτρα ευθυγραμμίζονται. Τιμή 1 σημαίνει επιλέξιμο long setup, 0 απόρριψη· η λογική χρησιμοποιεί κλεισμένο bar και απαιτεί εκτέλεση στο επόμενο διαθέσιμο σημείο.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `ema_fast_col`, `ema_slow_col`, `mama_col`, `fama_col`, `roofing_col`, `roofing_slope_col`, `decycler_osc_col`, `ema_condition_col`, `mama_condition_col`, `roofing_positive_col`, `roofing_slope_positive_col`, `roofing_gt_slope_col`, `decycler_positive_col`, `state_col`, `entry_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `entry_mode`, `entry_delay_bars`, `long_only`, `use_ema_regime`, `use_mama_fama`, `use_roofing_gt_slope`, `use_decycler`, `ema_fast_col`, `ema_slow_col`, `mama_col`, `fama_col`, `roofing_col`, `roofing_slope_col`, `decycler_osc_col`, `ema_condition_col`, `mama_condition_col`, `roofing_positive_col`, `roofing_slope_positive_col`, `roofing_gt_slope_col`, `decycler_positive_col`, `state_col`, `entry_col`, `signal_col`, `candidate_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ehlers_continuation_long
  params:
    entry_mode: state
    entry_delay_bars: 0
    long_only: true
    use_ema_regime: true
    use_mama_fama: true
    use_roofing_gt_slope: true
    use_decycler: true
    ema_fast_col: ema_50
    ema_slow_col: ema_100
    mama_col: mama
    fama_col: fama
    roofing_col: roofing_filter_48_10
    roofing_slope_col: roofing_filter_48_10_slope
    decycler_osc_col: decycler_oscillator_30_60
    ema_condition_col: ehlers_continuation_ema50_gt_ema100
    mama_condition_col: ehlers_continuation_mama_gt_fama
    roofing_positive_col: ehlers_continuation_roofing_gt_zero
    roofing_slope_positive_col: ehlers_continuation_roofing_slope_gt_zero
    roofing_gt_slope_col: ehlers_continuation_roofing_gt_slope
    decycler_positive_col: ehlers_continuation_decycler_osc_gt_zero
    state_col: ehlers_continuation_long_state
    entry_col: ehlers_continuation_long_entry
    signal_col: ehlers_continuation_signal
    candidate_col: ehlers_continuation_candidate
    output_cols:
    - ehlers_continuation_signal
    - ehlers_continuation_candidate
```

### `ehlers_continuation_short`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει short continuation όταν Ehlers trend και cycle φίλτρα ευθυγραμμίζονται καθοδικά. Τιμή -1 σημαίνει επιλέξιμο short setup και 0 flat· δεν πρέπει να χρησιμοποιηθεί σε backtest όπου τα shorts δεν είναι ενεργοποιημένα.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `ema_fast_col`, `ema_slow_col`, `mama_col`, `fama_col`, `roofing_col`, `roofing_slope_col`, `decycler_osc_col`, `ema_condition_col`, `mama_condition_col`, `roofing_negative_col`, `roofing_slope_negative_col`, `roofing_lt_slope_col`, `decycler_negative_col`, `state_col`, `entry_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `entry_mode`, `entry_delay_bars`, `short_only`, `use_ema_regime`, `use_mama_fama`, `use_roofing_lt_slope`, `use_decycler`, `ema_fast_col`, `ema_slow_col`, `mama_col`, `fama_col`, `roofing_col`, `roofing_slope_col`, `decycler_osc_col`, `ema_condition_col`, `mama_condition_col`, `roofing_negative_col`, `roofing_slope_negative_col`, `roofing_lt_slope_col`, `decycler_negative_col`, `state_col`, `entry_col`, `signal_col`, `candidate_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ehlers_continuation_short
  params:
    entry_mode: state
    entry_delay_bars: 0
    short_only: true
    use_ema_regime: true
    use_mama_fama: true
    use_roofing_lt_slope: true
    use_decycler: true
    ema_fast_col: ema_50
    ema_slow_col: ema_100
    mama_col: mama
    fama_col: fama
    roofing_col: roofing_filter_48_10
    roofing_slope_col: roofing_filter_48_10_slope
    decycler_osc_col: decycler_oscillator_30_60
    ema_condition_col: ehlers_continuation_ema50_lt_ema100
    mama_condition_col: ehlers_continuation_mama_lt_fama
    roofing_negative_col: ehlers_continuation_roofing_lt_zero
    roofing_slope_negative_col: ehlers_continuation_roofing_slope_lt_zero
    roofing_lt_slope_col: ehlers_continuation_roofing_lt_slope
    decycler_negative_col: ehlers_continuation_decycler_osc_lt_zero
    state_col: ehlers_continuation_short_state
    entry_col: ehlers_continuation_short_entry
    signal_col: ehlers_continuation_signal
    candidate_col: ehlers_continuation_candidate
    output_cols:
    - ehlers_continuation_signal
    - ehlers_continuation_candidate
```

### `ehlers_decycler_continuation`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει continuation setup από θέση τιμής, κλίση και απόκλιση γύρω από τον Decycler. Το candidate δείχνει ότι η υποκείμενη τάση και το timing συμφωνούν, ενώ τα μηδενικά rows δεν είναι αρνητικά labels αλλά απουσία setup.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `decycler_osc_col`, `decycler_ratio_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `decycler_osc_col`, `decycler_ratio_col`, `decycler_osc_min`, `decycler_ratio_max`, `entry_mode`, `signal_col`, `candidate_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ehlers_decycler_continuation
  params:
    decycler_osc_col: decycler_oscillator_30_60
    decycler_ratio_col: ehlers_decycler_over_close
    decycler_osc_min: 0.45
    decycler_ratio_max: 0.994
    entry_mode: state
    signal_col: signal_side
    candidate_col: signal_candidate
    output_cols:
    - signal_candidate
```

### `ehlers_semiscalp_long`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει βραχυχρόνιο long setup από Ehlers cycle, trend και χαμηλού lag φίλτρα. Η έξοδος είναι long-only candidate και όχι συνεχής εκτίμηση απόδοσης· προορίζεται για αυστηρό next-bar execution και προαιρετικό model filter.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `mama_col`, `fama_col`, `decycler_col`, `roofing_col`, `laguerre_col`, `fisher_col`, `hilbert_amplitude_col`, `dominant_cycle_period_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `entry_mode`, `require_mama_rising`, `roofing_trigger_mode`, `price_col`, `mama_col`, `fama_col`, `decycler_col`, `roofing_col`, `laguerre_col`, `fisher_col`, `hilbert_amplitude_col`, `dominant_cycle_period_col`, `amplitude_lookback`, `laguerre_min`, `min_cycle_period`, `max_cycle_period`, `use_cycle_period_filter`, `signal_col`, `candidate_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ehlers_semiscalp_long
  params:
    entry_mode: transition
    require_mama_rising: false
    roofing_trigger_mode: rising
    price_col: close
    mama_col: mama
    fama_col: fama
    decycler_col: decycler
    roofing_col: roofing_filter_48_10
    laguerre_col: laguerre_rsi
    fisher_col: fisher_transform
    hilbert_amplitude_col: hilbert_amplitude_64
    dominant_cycle_period_col: dominant_cycle_period
    amplitude_lookback: 100
    laguerre_min: 0.5
    min_cycle_period: 10.0
    max_cycle_period: 48.0
    use_cycle_period_filter: false
    signal_col: signal_side
    candidate_col: signal_candidate
    output_cols:
    - signal_side
    - signal_candidate
```

### `ehlers_trend_pullback_continuation_long`

**Τι μετρά και τι πληροφορία δίνει.** Συνδυάζει Ehlers trend identification με pullback και επανεκκίνηση ανοδικής ορμής. Εκπέμπει 1 όταν τάση, υποχώρηση και continuation trigger εμφανίζονται με τη σωστή σειρά, διαφορετικά 0, ώστε να μη γίνεται καταδίωξη ήδη εκτεταμένης κίνησης.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `entry_mode`, `entry_delay_bars`, `long_only`, `signal_col`, `candidate_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ehlers_trend_pullback_continuation_long
  params:
    entry_mode: state
    entry_delay_bars: 0
    long_only: true
    signal_col: signal_side
    candidate_col: signal_candidate
```

### `trend_state`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει μια υπάρχουσα διακριτή trend-state στήλη σε θέση. Ανάλογα με το mode, θετικό state γίνεται long, αρνητικό short ή κρατείται η προηγούμενη θέση· το μηδέν αντιστοιχεί σε ουδέτερο καθεστώς ή έξοδο.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `state_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `state_col`; με προεπιλογή `signal_col`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: trend_state
  params:
    state_col: <required>
    signal_col: null
    mode: long_short_hold
```

### `ema_rms_ppo_vwap`

**Τι μετρά και τι πληροφορία δίνει.** Συνδυάζει EMA/RMS trend, PPO momentum και θέση ως προς VWAP σε composite setup. Η πλευρά εμφανίζεται μόνο όταν trend anchor και momentum επιβεβαιώνουν την ίδια κατεύθυνση, ενώ condition columns επιτρέπουν audit κάθε φίλτρου.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `close_col`, `atr_col`, `ema_fast_rms_col`, `ema_mid_rms_col`, `ema_slow_rms_col`, `vwap_col`, `vwap_rms_col`, `ppo_col`, `ppo_signal_col`, `signal_col`, `candidate_col`, `bull_stack_col`, `bear_stack_col`, `fast_slope_col`, `vwap_distance_atr_col`, `vwap_reclaim_col`, `vwap_reject_col`, `vwap_rms_long_bias_col`, `vwap_rms_short_bias_col`, `ppo_hist_col`, `long_setup_col`, `short_setup_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `close_col`, `atr_col`, `ema_fast_rms_col`, `ema_mid_rms_col`, `ema_slow_rms_col`, `vwap_col`, `vwap_rms_col`, `ppo_col`, `ppo_signal_col`, `mode`, `require_vwap_rms_filter`, `require_rms_slope_filter`, `max_vwap_distance_atr`, `min_rms_slope`, `signal_col`, `candidate_col`, `bull_stack_col`, `bear_stack_col`, `fast_slope_col`, `vwap_distance_atr_col`, `vwap_reclaim_col`, `vwap_reject_col`, `vwap_rms_long_bias_col`, `vwap_rms_short_bias_col`, `ppo_hist_col`, `long_setup_col`, `short_setup_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ema_rms_ppo_vwap
  params:
    close_col: close
    atr_col: atr_14
    ema_fast_rms_col: ema_20__root_mean_square
    ema_mid_rms_col: ema_50__root_mean_square
    ema_slow_rms_col: ema_100__root_mean_square
    vwap_col: vwap_20
    vwap_rms_col: vwap_20__root_mean_square
    ppo_col: ppo
    ppo_signal_col: ppo_signal
    mode: long_short
    require_vwap_rms_filter: false
    require_rms_slope_filter: false
    max_vwap_distance_atr: 1.0
    min_rms_slope: 0.0
    signal_col: signal_side
    candidate_col: signal_candidate
    bull_stack_col: ema_rms_bull_stack
    bear_stack_col: ema_rms_bear_stack
    fast_slope_col: ema_rms_fast_slope
    vwap_distance_atr_col: vwap_distance_atr
    vwap_reclaim_col: vwap_reclaim
    vwap_reject_col: vwap_reject
    vwap_rms_long_bias_col: vwap_rms_long_bias
    vwap_rms_short_bias_col: vwap_rms_short_bias
    ppo_hist_col: ppo_hist
    long_setup_col: ema_rms_long_setup
    short_setup_col: ema_rms_short_setup
    output_cols:
    - atr_14
    - vwap_20
    - signal_side
    - signal_candidate
```

### `eurusd_session_bb_reversion`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει long-only EURUSD mean-reversion setup σε συγκεκριμένη συνεδρία μετά από Bollinger/RSI washout. Το candidate απαιτεί υπερβολικά χαμηλή θέση, αρνητικό ROC, αποδεκτή τάση, ATR rank, spread rank και weekday gate· το score δείχνει τον βαθμό συμφωνίας.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `bb_percent_b_col`, `rsi_col`, `roc_col`, `close_over_ema_col`, `atr_rank_col`, `spread_rank_col`, `is_weekend_col`, `signal_col`, `candidate_col`, `score_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `bb_percent_b_col`, `rsi_col`, `roc_col`, `close_over_ema_col`, `atr_rank_col`, `spread_rank_col`, `is_weekend_col`, `timezone`, `start_hour`, `end_hour`, `bb_percent_b_max`, `rsi_max`, `roc_max`, `max_abs_trend`, `min_atr_rank`, `max_atr_rank`, `max_spread_rank`, `signal_col`, `candidate_col`, `score_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: eurusd_session_bb_reversion
  params:
    bb_percent_b_col: bb_percent_b_40_2.0
    rsi_col: close_rsi_28
    roc_col: roc_8
    close_over_ema_col: close_over_ema_200
    atr_rank_col: atr_pct_rank_336
    spread_rank_col: spread_rank_336
    is_weekend_col: is_weekend
    timezone: UTC
    start_hour: 7
    end_hour: 18
    bb_percent_b_max: 0.12
    rsi_max: 35.0
    roc_max: -0.0005
    max_abs_trend: 0.005
    min_atr_rank: 0.1
    max_atr_rank: 0.8
    max_spread_rank: 0.75
    signal_col: signal_side
    candidate_col: signal_candidate
    score_col: eurusd_bb_reversion_score
```

### `probability_threshold`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει πιθανότητα θετικής κλάσης σε διακριτή θέση μέσω upper/lower thresholds. Πάνω από το upper παράγει long, κάτω από το lower short και μεταξύ τους flat ή διατήρηση θέσης ανά mode· τα exit thresholds δημιουργούν υστέρηση για μείωση εναλλαγών.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `prob_col`, `signal_col`, `base_signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `prob_col`; με προεπιλογή `signal_col`, `upper`, `lower`, `upper_exit`, `lower_exit`, `mode`, `base_signal_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: probability_threshold
  params:
    prob_col: <required>
    signal_col: null
    upper: 0.55
    lower: 0.45
    upper_exit: null
    lower_exit: null
    mode: long_short_hold
    base_signal_col: null
```

### `probability_conviction`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει την απόσταση της πιθανότητας από το 0,5 σε συνεχή conviction θέση. Πιθανότητα πάνω από 0,5 δίνει θετική έκθεση, κάτω αρνητική, και το clip περιορίζει το μέγιστο μέγεθος χωρίς να αλλάζει την κατεύθυνση.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `prob_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `prob_col`; με προεπιλογή `signal_col`, `clip`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: probability_conviction
  params:
    prob_col: <required>
    signal_col: null
    clip: 1.0
```

### `probability_vol_adjusted`

**Τι μετρά και τι πληροφορία δίνει.** Κλιμακώνει probability conviction με προβλεπόμενη ή πραγματοποιημένη μεταβλητότητα. Η ίδια πιθανότητα δίνει μικρότερη θέση όταν ο κίνδυνος είναι υψηλότερος· activation filters, quantile και trade-rate gates μπορούν να κρατήσουν μόνο τις ισχυρότερες αποφάσεις.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `prob_col`, `vol_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `prob_col`, `vol_col`, `signal_col`, `prob_center`, `upper`, `lower`, `vol_target`, `clip`, `vol_floor`, `min_signal_abs`, `activation_filters`, `top_quantile`, `top_quantile_window`, `max_trade_rate`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: probability_vol_adjusted
  params:
    prob_col: pred_prob
    vol_col: pred_vol
    signal_col: null
    prob_center: 0.5
    upper: null
    lower: null
    vol_target: 0.001
    clip: 1.0
    vol_floor: 1.0e-06
    min_signal_abs: 0.0
    activation_filters: null
    top_quantile: null
    top_quantile_window: null
    max_trade_rate: null
```

### `meta_probability_side`

**Τι μετρά και τι πληροφορία δίνει.** Φιλτράρει ήδη κατασκευασμένη candidate πλευρά με πιθανότητα επιτυχίας και προαιρετικό expected value. Δεν δημιουργεί νέα κατεύθυνση: διατηρεί το αρχικό side μόνο όταν candidate, OOS, probability και EV gates περνούν, διαφορετικά επιστρέφει μηδέν.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `prob_col`, `side_col`, `candidate_col`, `pred_is_oos_col`, `expected_value_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `prob_col`, `side_col`, `candidate_col`, `pred_is_oos_col`, `expected_value_col`, `signal_col`, `threshold`, `upper`, `min_expected_value_r`, `profit_barrier_r`, `stop_barrier_r`, `clip`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: meta_probability_side
  params:
    prob_col: pred_prob
    side_col: primary_side
    candidate_col: null
    pred_is_oos_col: null
    expected_value_col: null
    signal_col: null
    threshold: null
    upper: null
    min_expected_value_r: null
    profit_barrier_r: 1.0
    stop_barrier_r: 1.0
    clip: 1.0
    mode: long_short
```

### `orb_candidate_side`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει τις candidate και side στήλες του opening-range breakout σε τελικό signal. Εκπέμπει την ήδη αποφασισμένη πλευρά μόνο στα επιλέξιμα ORB rows και δεν κρατά θέση πέρα από το event εκτός αν το backtest εφαρμόζει δικό του holding rule.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `side_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `candidate_col`, `side_col`, `signal_col`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: orb_candidate_side
  params:
    candidate_col: orb_candidate
    side_col: orb_side
    signal_col: signal_orb_side
    mode: long_short
```

### `ppo_adx_stochrsi_trend`

**Τι μετρά και τι πληροφορία δίνει.** Συνδυάζει PPO κατεύθυνση, ADX ισχύ τάσης και Stochastic RSI timing. Η πλευρά ενεργοποιείται όταν momentum και trend strength συμφωνούν και ο oscillator βρίσκεται σε κατάλληλη φάση, μειώνοντας entries σε αδύναμη ή υπερεκτεταμένη αγορά.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `close_col`, `high_col`, `low_col`, `ema_fast_col`, `ema_slow_col`, `ppo_col`, `ppo_signal_col`, `adx_col`, `plus_di_col`, `minus_di_col`, `atr_col`, `stoch_k_col`, `stoch_d_col`, `signal_col`, `position_col`, `entry_long_col`, `entry_short_col`, `exit_long_col`, `exit_short_col`, `long_setup_col`, `short_setup_col`, `exit_long_rule_col`, `exit_short_rule_col`, `ppo_slope_col`, `ema_trend_state_col`, `directional_spread_col`, `stoch_bullish_reset_col`, `stoch_bearish_reset_col`, `stoch_bullish_cross_col`, `stoch_bearish_cross_col`, `atr_stop_distance_col`, `atr_take_profit_distance_col`, `atr_stop_long_col`, `atr_stop_short_col`, `atr_take_profit_long_col`, `atr_take_profit_short_col`, `atr_trailing_stop_long_col`, `atr_trailing_stop_short_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `close_col`, `high_col`, `low_col`, `ema_fast_col`, `ema_slow_col`, `ppo_col`, `ppo_signal_col`, `adx_col`, `plus_di_col`, `minus_di_col`, `atr_col`, `stoch_k_col`, `stoch_d_col`, `mode`, `require_adx`, `adx_threshold`, `ppo_slope_threshold`, `stoch_oversold`, `stoch_overbought`, `stoch_entry_mode`, `atr_stop_mult`, `atr_take_profit_mult`, `atr_trailing_mult`, `use_atr_trailing_stop`, `signal_col`, `position_col`, `entry_long_col`, `entry_short_col`, `exit_long_col`, `exit_short_col`, `long_setup_col`, `short_setup_col`, `exit_long_rule_col`, `exit_short_rule_col`, `ppo_slope_col`, `ema_trend_state_col`, `directional_spread_col`, `stoch_bullish_reset_col`, `stoch_bearish_reset_col`, `stoch_bullish_cross_col`, `stoch_bearish_cross_col`, `atr_stop_distance_col`, `atr_take_profit_distance_col`, `atr_stop_long_col`, `atr_stop_short_col`, `atr_take_profit_long_col`, `atr_take_profit_short_col`, `atr_trailing_stop_long_col`, `atr_trailing_stop_short_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ppo_adx_stochrsi_trend
  params:
    close_col: close
    high_col: high
    low_col: low
    ema_fast_col: ema_50
    ema_slow_col: ema_150
    ppo_col: ppo
    ppo_signal_col: ppo_signal
    adx_col: adx
    plus_di_col: plus_di
    minus_di_col: minus_di
    atr_col: atr
    stoch_k_col: stochrsi_k
    stoch_d_col: stochrsi_d
    mode: long_short
    require_adx: true
    adx_threshold: 20.0
    ppo_slope_threshold: 0.0
    stoch_oversold: 0.2
    stoch_overbought: 0.8
    stoch_entry_mode: reset_or_cross
    atr_stop_mult: 1.5
    atr_take_profit_mult: 2.0
    atr_trailing_mult: 1.0
    use_atr_trailing_stop: false
    signal_col: signal
    position_col: position
    entry_long_col: entry_long
    entry_short_col: entry_short
    exit_long_col: exit_long
    exit_short_col: exit_short
    long_setup_col: long_setup
    short_setup_col: short_setup
    exit_long_rule_col: exit_long_rule
    exit_short_rule_col: exit_short_rule
    ppo_slope_col: ppo_slope
    ema_trend_state_col: ema_trend_state
    directional_spread_col: directional_spread
    stoch_bullish_reset_col: stochrsi_bullish_reset
    stoch_bearish_reset_col: stochrsi_bearish_reset
    stoch_bullish_cross_col: stochrsi_bullish_cross
    stoch_bearish_cross_col: stochrsi_bearish_cross
    atr_stop_distance_col: atr_stop_distance
    atr_take_profit_distance_col: atr_take_profit_distance
    atr_stop_long_col: atr_stop_long
    atr_stop_short_col: atr_stop_short
    atr_take_profit_long_col: atr_take_profit_long
    atr_take_profit_short_col: atr_take_profit_short
    atr_trailing_stop_long_col: atr_trailing_stop_long
    atr_trailing_stop_short_col: atr_trailing_stop_short
    output_cols:
    - signal
```

### `quote_flow_scalp_router`

**Τι μετρά και τι πληροφορία δίνει.** Δρομολογεί long ή short scalp candidates από quote-flow proxies, spread, VWAP και market structure. Η έξοδος είναι event side μετά από liquidity και cost gates· επειδή οι ροές μπορεί να είναι proxies, το score εκφράζει σχετική πίεση και όχι εγγυημένη εκτέλεση.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `close_col`, `atr_col`, `vwap_distance_col`, `vpin_rank_col`, `ofi_fast_col`, `ofi_slow_col`, `spread_rank_col`, `spread_z_col`, `volume_relative_col`, `close_pos_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `mode`, `close_col`, `atr_col`, `vwap_distance_col`, `vpin_rank_col`, `ofi_fast_col`, `ofi_slow_col`, `spread_rank_col`, `spread_z_col`, `volume_relative_col`, `close_pos_col`, `signal_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: quote_flow_scalp_router
  params:
    mode: long_short
    close_col: close
    atr_col: atr_14
    vwap_distance_col: close_minus_vwap_20_atr
    vpin_rank_col: vpin_proxy_50_rank_252
    ofi_fast_col: ofi_proxy_5_norm
    ofi_slow_col: ofi_proxy_15_norm
    spread_rank_col: spread_bps_rank_252
    spread_z_col: spread_bps_z_252
    volume_relative_col: volume_relative_48
    close_pos_col: close_pos_in_bar
    signal_col: signal_side
```

### `roc_long_only_conditions`

**Τι μετρά και τι πληροφορία δίνει.** Παράγει long-only θέση από αριθμό επιβεβαιωμένων ROC, regime, candle και multi-timeframe συνθηκών. Το trade ενεργοποιείται όταν το score φτάσει το `min_score_required` και περνούν τα υποχρεωτικά gates· η έκθεση μπορεί να μειωθεί σε υψηλή μεταβλητότητα.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `roc_col`, `regime_vol_ratio_z_col`, `close_z_col`, `close_open_ratio_col`, `mtf_1h_col`, `mtf_4h_col`, `is_weekend_col`, `macro_condition_col`, `signal_col`, `long_signal_col`, `score_col`, `all_conditions_col`, `vol_adjusted_col`, `short_signal_col`, `combined_signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `roc_window`, `roc_col`, `roc_min`, `vol_short_window`, `vol_long_window`, `regime_vol_ratio_z_col`, `vol_z_min`, `vol_z_max`, `close_z_col`, `close_z_min`, `close_z_max`, `close_open_ratio_col`, `close_open_ratio_min`, `mtf_1h_col`, `mtf_1h_min`, `mtf_4h_col`, `mtf_4h_min`, `is_weekend_col`, `macro_condition_col`, `min_score_required`, `require_all_conditions`, `require_bullish_candle`, `required_condition_names`, `vol_adjustment_strength`, `min_exposure`, `max_exposure`, `signal_col`, `long_signal_col`, `score_col`, `all_conditions_col`, `vol_adjusted_col`, `short_signal_col`, `combined_signal_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: roc_long_only_conditions
  params:
    roc_window: 12
    roc_col: null
    roc_min: 0.0015
    vol_short_window: 24
    vol_long_window: 168
    regime_vol_ratio_z_col: null
    vol_z_min: -1.5
    vol_z_max: 1.75
    close_z_col: close_z
    close_z_min: -0.25
    close_z_max: 2.25
    close_open_ratio_col: close_open_ratio
    close_open_ratio_min: 0.0002
    mtf_1h_col: mtf_1h_trend_score
    mtf_1h_min: -0.001
    mtf_4h_col: mtf_4h_trend_score
    mtf_4h_min: -0.002
    is_weekend_col: is_weekend
    macro_condition_col: null
    min_score_required: 5
    require_all_conditions: false
    require_bullish_candle: false
    required_condition_names: null
    vol_adjustment_strength: 0.9
    min_exposure: 0.1
    max_exposure: 1.0
    signal_col: null
    long_signal_col: manual_long_signal
    score_col: manual_conviction_score
    all_conditions_col: manual_all_conditions_signal
    vol_adjusted_col: manual_vol_adjusted_signal
    short_signal_col: short_signal
    combined_signal_col: combined_signal
```

### `ema_stoch_rsi_pullback`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει pullback προς EMA trend με Stochastic RSI επανεκκίνηση. Long ή short candidate εμφανίζεται μόνο όταν η βασική τάση και η oscillator στροφή συμφωνούν· τα thresholds καθορίζουν πόσο βαθύ πρέπει να είναι το pullback.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `price_col`, `ema_fast_col`, `ema_slow_col`, `stoch_k_col`, `stoch_d_col`, `stoch_recover_col`, `stoch_fall_col`, `side_col`, `candidate_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `price_col`, `ema_fast_col`, `ema_slow_col`, `stoch_k_col`, `stoch_d_col`, `stoch_recover_col`, `stoch_fall_col`, `oversold`, `overbought`, `max_bars_after_cross`, `require_k_d_confirmation`, `require_price_above_slow_ema_for_long`, `require_price_below_slow_ema_for_short`, `use_first_pullback_only`, `prefix`, `side_col`, `candidate_col`, `signal_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ema_stoch_rsi_pullback
  params:
    price_col: close
    ema_fast_col: ema_50
    ema_slow_col: ema_150
    stoch_k_col: stoch_rsi_k
    stoch_d_col: stoch_rsi_d
    stoch_recover_col: stoch_rsi_recover_from_oversold
    stoch_fall_col: stoch_rsi_fall_from_overbought
    oversold: 0.2
    overbought: 0.8
    max_bars_after_cross: 30
    require_k_d_confirmation: true
    require_price_above_slow_ema_for_long: true
    require_price_below_slow_ema_for_short: true
    use_first_pullback_only: true
    prefix: ema_stoch
    side_col: signal_side
    candidate_col: signal_candidate
    signal_col: null
    output_cols:
    - configured by signal_col
```

### `indicator_model_adaptive_pullback`

**Τι μετρά και τι πληροφορία δίνει.** Συνδυάζει πολλούς indicators σε adaptive pullback candidate και score πριν από model filtering. Η πλευρά προέρχεται από deterministic τάση και timing, ενώ το score περιγράφει ποιότητα setup· το μοντέλο μπορεί στη συνέχεια να απορρίψει χαμηλής πιθανότητας candidates.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `close_col`, `ema_fast_col`, `ema_mid_col`, `ema_slow_col`, `ema_slope_fast_col`, `ema_slope_mid_col`, `adx_col`, `rsi_col`, `stoch_k_col`, `stoch_d_col`, `stoch_cross_up_col`, `stoch_cross_down_col`, `macd_hist_col`, `macd_hist_slope_col`, `atr_pct_rank_col`, `bb_bandwidth_col`, `bb_bandwidth_rank_col`, `distance_ema_fast_atr_col`, `candidate_long_col`, `candidate_short_col`, `direction_col`, `signal_col`, `candidate_col`, `signal_name_col`, `score_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `close_col`, `ema_fast`, `ema_mid`, `ema_slow`, `ema_fast_col`, `ema_mid_col`, `ema_slow_col`, `ema_slope_fast_col`, `ema_slope_mid_col`, `adx_col`, `min_adx`, `max_adx`, `rsi_col`, `rsi_long_min`, `rsi_long_max`, `rsi_short_min`, `rsi_short_max`, `stoch_k_col`, `stoch_d_col`, `stoch_cross_up_col`, `stoch_cross_down_col`, `stoch_long_max`, `stoch_short_min`, `macd_hist_col`, `macd_hist_slope_col`, `require_macd_confirmation`, `atr_pct_rank_col`, `min_atr_pct_rank`, `max_atr_pct_rank`, `bb_bandwidth_col`, `bb_bandwidth_rank_col`, `min_bb_bandwidth`, `min_bb_bandwidth_rank`, `distance_ema_fast_atr_col`, `max_distance_from_ema_atr`, `candidate_long_col`, `candidate_short_col`, `direction_col`, `signal_col`, `candidate_col`, `signal_name_col`, `score_col`, `signal_name`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: indicator_model_adaptive_pullback
  params:
    close_col: close
    ema_fast: 20
    ema_mid: 50
    ema_slow: 100
    ema_fast_col: null
    ema_mid_col: null
    ema_slow_col: null
    ema_slope_fast_col: null
    ema_slope_mid_col: null
    adx_col: null
    min_adx: 18.0
    max_adx: 45.0
    rsi_col: null
    rsi_long_min: 45.0
    rsi_long_max: 68.0
    rsi_short_min: 32.0
    rsi_short_max: 55.0
    stoch_k_col: stoch_rsi_k
    stoch_d_col: stoch_rsi_d
    stoch_cross_up_col: stoch_rsi_cross_up
    stoch_cross_down_col: stoch_rsi_cross_down
    stoch_long_max: 60.0
    stoch_short_min: 40.0
    macd_hist_col: macd_hist
    macd_hist_slope_col: macd_hist_slope
    require_macd_confirmation: true
    atr_pct_rank_col: null
    min_atr_pct_rank: 0.2
    max_atr_pct_rank: 0.9
    bb_bandwidth_col: bollinger_bandwidth
    bb_bandwidth_rank_col: bollinger_bandwidth_rank_100
    min_bb_bandwidth: 0.0
    min_bb_bandwidth_rank: 0.2
    distance_ema_fast_atr_col: null
    max_distance_from_ema_atr: 0.75
    candidate_long_col: candidate_long
    candidate_short_col: candidate_short
    direction_col: direction
    signal_col: signal
    candidate_col: signal_candidate
    signal_name_col: signal_name
    score_col: signal_score
    signal_name: indicator_model_adaptive_pullback
    output_cols:
    - signal
    - signal_candidate
```

### `manual_long_model_filter`

**Τι μετρά και τι πληροφορία δίνει.** Φιλτράρει long-only deterministic candidate με model probability, προαιρετικό EV και risk/cost gates. Δεν δημιουργεί trade όταν δεν υπάρχει base candidate· πάνω από το threshold κρατά ή κλιμακώνει το αρχικό signal και κάτω από αυτό παραμένει flat.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `prob_col`, `candidate_col`, `base_signal_col`, `gate_col`, `expected_value_col`, `volatility_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `prob_col`, `candidate_col`, `base_signal_col`, `threshold`, `gate_col`, `gate_cols_any`, `min_signal_abs`, `expected_value_col`, `min_expected_value_r`, `profit_barrier_r`, `stop_barrier_r`, `volatility_col`, `round_trip_cost_return`, `cost_buffer_r`, `signal_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: manual_long_model_filter
  params:
    prob_col: pred_prob
    candidate_col: manual_long_candidate
    base_signal_col: manual_vol_adjusted_candidate
    threshold: 0.55
    gate_col: null
    gate_cols_any: null
    min_signal_abs: 0.0
    expected_value_col: null
    min_expected_value_r: null
    profit_barrier_r: 1.0
    stop_barrier_r: 1.0
    volatility_col: null
    round_trip_cost_return: 0.0
    cost_buffer_r: 0.0
    signal_col: null
```

### `matb_candidate`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει τις deterministic MATB candidate/side στήλες σε signal χωρίς state retention. Εκπέμπει +1 ή -1 μόνο στο event row ανά επιλεγμένο mode και μηδέν αλλού, διατηρώντας σαφή διαχωρισμό candidate generation και execution.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `side_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `candidate_col`, `side_col`, `signal_col`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: matb_candidate
  params:
    candidate_col: matb_candidate
    side_col: matb_side
    signal_col: signal_side
    mode: long_short
```

### `matb_meta_filter`

**Τι μετρά και τι πληροφορία δίνει.** Φιλτράρει MATB πλευρά με OOS πιθανότητα επιτυχίας και αναμενόμενο R. Το side διατηρείται μόνο όταν candidate, OOS flag, minimum probability και minimum expected R ισχύουν ταυτόχρονα· NaN ή in-sample predictions δίνουν flat.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `candidate_col`, `side_col`, `probability_col`, `expected_r_col`, `oos_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `candidate_col`, `side_col`, `probability_col`, `expected_r_col`, `oos_col`, `minimum_probability`, `minimum_expected_r`, `signal_col`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: matb_meta_filter
  params:
    candidate_col: matb_candidate
    side_col: matb_side
    probability_col: matb_pred_success_prob
    expected_r_col: matb_pred_ev_r
    oos_col: matb_pred_is_oos
    minimum_probability: 0.55
    minimum_expected_r: 0.1
    signal_col: signal_side
    mode: long_short
```

### `dense_return_forecast`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει συνεχή πρόβλεψη απόδοσης σε αναμενόμενη καθαρή απόδοση μετά από friction adjustments. Αφαιρεί εκτιμώμενο round-trip κόστος και ολίσθηση με σωστό πρόσημο, μετατρέπει volatility-normalized forecast όταν χρειάζεται και μπορεί να περιορίσει την έκθεση.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `forecast_col`, `signal_col`, `expected_net_return_col`, `estimated_cost_col`, `volatility_col`, `price_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `forecast_col`, `signal_col`, `expected_net_return_col`, `estimated_cost_col`, `cost_per_turnover`, `slippage_per_turnover`, `cost_round_trip_mult`, `forecast_is_vol_normalized`, `volatility_col`, `price_col`, `volatility_floor`, `signed_cost_adjustment`, `clip`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: dense_return_forecast
  params:
    forecast_col: pred_ret
    signal_col: expected_net_return
    expected_net_return_col: expected_net_return
    estimated_cost_col: estimated_round_trip_cost
    cost_per_turnover: 0.0
    slippage_per_turnover: 0.0
    cost_round_trip_mult: 2.0
    forecast_is_vol_normalized: false
    volatility_col: atr_14
    price_col: close
    volatility_floor: 1.0e-12
    signed_cost_adjustment: true
    clip: null
```

### `forecast_threshold`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει πρόβλεψη απόδοσης σε long, short ή flat μέσω thresholds. Forecast πάνω από το upper ενεργοποιεί long και κάτω από το lower short, ενώ activation filters μπορούν να απαιτήσουν επιπλέον point-in-time συνθήκες.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `forecast_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `forecast_col`, `signal_col`, `upper`, `lower`, `mode`, `activation_filters`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: forecast_threshold
  params:
    forecast_col: pred_ret
    signal_col: null
    upper: 0.0
    lower: null
    mode: long_short_hold
    activation_filters: null
```

### `forecast_threshold_candidate`

**Τι μετρά και τι πληροφορία δίνει.** Κατασκευάζει primary candidate, side, strength και threshold distance από OOS forecast. Παράγει event μόνο σε rows με έγκυρη OOS πρόβλεψη που περνά αυστηρά ή inclusive thresholds· οι strength diagnostics μετρούν πόσο καθαρά ξεπεράστηκε το όριο.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `forecast_col`, `pred_is_oos_col`, `signal_col`, `candidate_col`, `side_col`, `strength_col`, `threshold_distance_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `forecast_col`, `pred_is_oos_col`, `signal_col`, `upper`, `lower`, `mode`, `activation_filters`, `candidate_col`, `side_col`, `strength_col`, `threshold_distance_col`, `inclusive`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: forecast_threshold_candidate
  params:
    forecast_col: pred_ret
    pred_is_oos_col: pred_is_oos
    signal_col: null
    upper: 0.0
    lower: null
    mode: long_short
    activation_filters: null
    candidate_col: primary_candidate
    side_col: primary_candidate_side
    strength_col: primary_candidate_strength
    threshold_distance_col: primary_candidate_threshold_distance
    inclusive: false
```

### `forecast_threshold_hysteresis`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει forecast σε stateful θέση με διαφορετικά entry και exit thresholds. Η υστέρηση, το cooldown και το minimum holding μειώνουν το churn: απαιτείται ισχυρότερη τιμή για είσοδο και ασθενέστερη αντίστροφη τιμή για έξοδο.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `forecast_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `forecast_col`, `signal_col`, `long_entry`, `long_exit`, `short_entry`, `short_exit`, `cooldown_bars`, `min_holding_bars`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: forecast_threshold_hysteresis
  params:
    forecast_col: pred_ret
    signal_col: null
    long_entry: 0.75
    long_exit: 0.25
    short_entry: -0.75
    short_exit: -0.25
    cooldown_bars: 0
    min_holding_bars: 0
```

### `forecast_vol_adjusted`

**Τι μετρά και τι πληροφορία δίνει.** Διαιρεί τη συνεχή πρόβλεψη απόδοσης με εκτίμηση μεταβλητότητας. Θετική πρόβλεψη δίνει long και αρνητική short, ενώ η θέση μικραίνει όταν ο αναμενόμενος κίνδυνος αυξάνεται και περιορίζεται από `clip`.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `forecast_col`, `vol_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `forecast_col`, `vol_col`, `signal_col`, `clip`, `vol_floor`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: forecast_vol_adjusted
  params:
    forecast_col: pred_ret
    vol_col: pred_vol
    signal_col: null
    clip: 1.0
    vol_floor: 1.0e-06
```

### `rsi`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει RSI oversold/overbought συνθήκες σε θέση. Κάτω από το buy level παράγει long mean-reversion πρόθεση και πάνω από το sell level short, με το mode να καθορίζει αν η θέση είναι event ή διατηρούμενη.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `rsi_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `rsi_col`; με προεπιλογή `buy_level`, `sell_level`, `signal_col`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: rsi
  params:
    rsi_col: <required>
    buy_level: 30.0
    sell_level: 70.0
    signal_col: null
    mode: long_short_hold
```

### `momentum`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει μια momentum στήλη σε θέση με long και short thresholds. Τιμή πάνω από το long threshold δίνει long, κάτω από το short threshold short και ενδιάμεσα flat ή hold σύμφωνα με το mode.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `momentum_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `momentum_col`; με προεπιλογή `long_threshold`, `short_threshold`, `signal_col`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: momentum
  params:
    momentum_col: <required>
    long_threshold: 0.0
    short_threshold: null
    signal_col: null
    mode: long_short_hold
```

### `stochastic`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει τη θέση του Stochastic K σε mean-reversion signal. Χαμηλή τιμή κάτω από το buy level υποδηλώνει long και υψηλή πάνω από το sell level short· χωρίς trend filter τα άκρα μπορεί να παραμένουν για μεγάλο διάστημα.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `k_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `k_col`; με προεπιλογή `buy_level`, `sell_level`, `signal_col`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: stochastic
  params:
    k_col: <required>
    buy_level: 20.0
    sell_level: 80.0
    signal_col: null
    mode: long_short_hold
```

### `stc_roofing_hilbert`

**Τι μετρά και τι πληροφορία δίνει.** Συνδυάζει Schaff Trend Cycle, Roofing Filter και Hilbert cycle diagnostics. Το signal απαιτεί συμφωνία trend-cycle κατεύθυνσης, filtered crossing και επαρκούς cycle ποιότητας, αποφεύγοντας trades όταν η φάση ή το πλάτος είναι ασαφή.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `ema_fast_col`, `ema_slow_col`, `roofing_col`, `roofing_slope_col`, `stc_col`, `hilbert_cycle_ok_col`, `hilbert_amplitude_rising_col`, `zscore_momentum_col`, `adx_col`, `volatility_regime_col`, `long_candidate_col`, `short_candidate_col`, `signal_col`, `candidate_col`, `hilbert_long_candidate_col`, `hilbert_short_candidate_col`, `hilbert_signal_col`, `ema_bullish_col`, `ema_bearish_col`, `roofing_positive_col`, `roofing_negative_col`, `roofing_slope_positive_col`, `roofing_slope_negative_col`, `stc_cross_up_col`, `stc_cross_down_col`, `hilbert_pass_col`, `zscore_long_pass_col`, `zscore_short_pass_col`, `adx_pass_col`, `volatility_pass_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `mode`, `ema_fast_col`, `ema_slow_col`, `roofing_col`, `roofing_slope_col`, `stc_col`, `hilbert_cycle_ok_col`, `hilbert_amplitude_rising_col`, `zscore_momentum_col`, `adx_col`, `volatility_regime_col`, `stc_long_cross_level`, `stc_short_cross_level`, `roofing_slope_bars`, `use_ema_regime`, `use_roofing_filter`, `use_roofing_slope`, `use_hilbert_filter`, `use_zscore_filter`, `use_adx_filter`, `adx_min`, `use_atr_vol_filter`, `allowed_volatility_regimes`, `entry_delay_bars`, `long_candidate_col`, `short_candidate_col`, `signal_col`, `candidate_col`, `hilbert_long_candidate_col`, `hilbert_short_candidate_col`, `hilbert_signal_col`, `ema_bullish_col`, `ema_bearish_col`, `roofing_positive_col`, `roofing_negative_col`, `roofing_slope_positive_col`, `roofing_slope_negative_col`, `stc_cross_up_col`, `stc_cross_down_col`, `hilbert_pass_col`, `zscore_long_pass_col`, `zscore_short_pass_col`, `adx_pass_col`, `volatility_pass_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: stc_roofing_hilbert
  params:
    mode: long_short
    ema_fast_col: ema_50
    ema_slow_col: ema_100
    roofing_col: roofing_filter
    roofing_slope_col: roofing_slope
    stc_col: stc
    hilbert_cycle_ok_col: hilbert_cycle_ok
    hilbert_amplitude_rising_col: hilbert_amplitude_rising
    zscore_momentum_col: zscore_momentum_20
    adx_col: adx_14
    volatility_regime_col: volatility_regime
    stc_long_cross_level: 25.0
    stc_short_cross_level: 75.0
    roofing_slope_bars: 3
    use_ema_regime: true
    use_roofing_filter: true
    use_roofing_slope: true
    use_hilbert_filter: false
    use_zscore_filter: false
    use_adx_filter: false
    adx_min: 18.0
    use_atr_vol_filter: false
    allowed_volatility_regimes:
    - 0
    - 1
    entry_delay_bars: 0
    long_candidate_col: stc_roofing_long_candidate
    short_candidate_col: stc_roofing_short_candidate
    signal_col: stc_roofing_signal
    candidate_col: stc_roofing_signal_candidate
    hilbert_long_candidate_col: stc_roofing_hilbert_long_candidate
    hilbert_short_candidate_col: stc_roofing_hilbert_short_candidate
    hilbert_signal_col: stc_roofing_hilbert_signal
    ema_bullish_col: stc_roofing_ema_bullish
    ema_bearish_col: stc_roofing_ema_bearish
    roofing_positive_col: stc_roofing_roofing_positive
    roofing_negative_col: stc_roofing_roofing_negative
    roofing_slope_positive_col: stc_roofing_roofing_slope_positive
    roofing_slope_negative_col: stc_roofing_roofing_slope_negative
    stc_cross_up_col: stc_roofing_stc_cross_up
    stc_cross_down_col: stc_roofing_stc_cross_down
    hilbert_pass_col: stc_roofing_hilbert_pass
    zscore_long_pass_col: stc_roofing_zscore_long_pass
    zscore_short_pass_col: stc_roofing_zscore_short_pass
    adx_pass_col: stc_roofing_adx_pass
    volatility_pass_col: stc_roofing_volatility_pass
    output_cols:
    - stc_roofing_long_candidate
    - stc_roofing_short_candidate
    - stc_roofing_signal
    - stc_roofing_signal_candidate
    - stc_roofing_hilbert_long_candidate
    - stc_roofing_hilbert_short_candidate
    - stc_roofing_hilbert_pass
    - stc_roofing_zscore_long_pass
    - stc_roofing_zscore_short_pass
    - stc_roofing_adx_pass
    - stc_roofing_volatility_pass
```

### `volatility_regime`

**Τι μετρά και τι πληροφορία δίνει.** Μετατρέπει την τρέχουσα μεταβλητότητα σε θέση ως προς rolling quantile. Η ακριβής κατεύθυνση εξαρτάται από το mode, αλλά το gate διαχωρίζει high-vol από low-vol περιβάλλον ώστε η στρατηγική να ενεργοποιείται μόνο στο επιλεγμένο regime.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `vol_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `vol_col`; με προεπιλογή `quantile`, `signal_col`, `mode`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: volatility_regime
  params:
    vol_col: <required>
    quantile: 0.5
    signal_col: null
    mode: long_short_hold
```

### `weekday_prev_daily_return_reversal`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει reversal event σε συγκεκριμένη τοπική ημέρα και ώρα όταν η προηγούμενη ημερήσια απόδοση περνά όριο. Εκπέμπει την configured πλευρά μόνο στο ακριβές χρονικό slot και καταγράφει previous-day return και τοπικό ημερολόγιο για πλήρες audit.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `close_col`, `timestamp_col`, `signal_col`, `candidate_col`, `prev_daily_return_col`, `local_weekday_col`, `local_hour_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `close_col`, `timestamp_col`, `timezone_input`, `timezone`, `weekday`, `signal_hour`, `signal_minute`, `prev_daily_return_max`, `side`, `signal_col`, `candidate_col`, `prev_daily_return_col`, `local_weekday_col`, `local_hour_col`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: weekday_prev_daily_return_reversal
  params:
    close_col: close
    timestamp_col: timestamp
    timezone_input: UTC
    timezone: America/New_York
    weekday: 3
    signal_hour: 9
    signal_minute: 0
    prev_daily_return_max: -0.0006369942365362478
    side: 1.0
    signal_col: null
    candidate_col: signal_candidate
    prev_daily_return_col: prev_daily_return
    local_weekday_col: local_weekday
    local_hour_col: local_hour
```

### `vwap_rms_ema_cross_long_fractal_filter`

**Τι μετρά και τι πληροφορία δίνει.** Εφαρμόζει fractal-dimension gate στο long VWAP/RMS/EMA cross setup. Το αρχικό candidate διατηρείται μόνο όταν η αγορά έχει την απαιτούμενη οργανωμένη ή trend-like fractal κατάσταση, διαφορετικά απορρίπτεται ως υπερβολικά θορυβώδες.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `ema_mid_col`, `ema_slow_col`, `ema_mid_rms_col`, `vwap_rms_col`, `ppo_col`, `ppo_signal_col`, `fractal_col`, `regime_col`, `cross_up_col`, `ppo_hist_col`, `ppo_hist_positive_col`, `ppo_above_signal_col`, `fractal_ok_col`, `long_setup_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `ema_mid_col`, `ema_slow_col`, `ema_mid_rms_col`, `vwap_rms_col`, `ppo_col`, `ppo_signal_col`, `ppo_hist_min`, `fractal_col`, `fractal_max`, `regime_col`, `cross_up_col`, `ppo_hist_col`, `ppo_hist_positive_col`, `ppo_above_signal_col`, `fractal_ok_col`, `long_setup_col`, `signal_col`, `candidate_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: vwap_rms_ema_cross_long_fractal_filter
  params:
    ema_mid_col: ema_50
    ema_slow_col: ema_96
    ema_mid_rms_col: ema_50__root_mean_square
    vwap_rms_col: vwap_40__root_mean_square
    ppo_col: ppo_12_36
    ppo_signal_col: ppo_signal_9
    ppo_hist_min: 0.0002
    fractal_col: fractal_dimension_128
    fractal_max: 1.45
    regime_col: ema_50_above_ema_96
    cross_up_col: vwap_40_rms_cross_above_ema_50_rms
    ppo_hist_col: ppo_hist_12_36_9
    ppo_hist_positive_col: ppo_hist_12_36_9_positive
    ppo_above_signal_col: ppo_12_36_above_ppo_signal_9
    fractal_ok_col: fractal_dimension_128_trend_ok
    long_setup_col: vwap_40_rms_ema_50_cross_long_fractal_setup
    signal_col: signal_side
    candidate_col: signal_candidate
    output_cols:
    - signal_side
    - signal_candidate
```

### `vwap_rms_ema_cross_long_hmm_gate`

**Τι μετρά και τι πληροφορία δίνει.** Εφαρμόζει επιτρεπόμενα HMM states στο long VWAP/RMS/EMA cross setup. Το gate δεν αλλάζει πλευρά αλλά κρατά το long candidate μόνο σε λανθάνουσες καταστάσεις που έχουν εγκριθεί από training analysis και OOS validation.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `ema_mid_col`, `ema_slow_col`, `ema_mid_rms_col`, `vwap_rms_col`, `ppo_col`, `ppo_signal_col`, `hmm_regime_col`, `hmm_prob_col`, `regime_col`, `cross_up_col`, `ppo_hist_col`, `ppo_hist_positive_col`, `ppo_above_signal_col`, `hmm_ok_col`, `long_setup_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `ema_mid_col`, `ema_slow_col`, `ema_mid_rms_col`, `vwap_rms_col`, `ppo_col`, `ppo_signal_col`, `ppo_hist_min`, `hmm_regime_col`, `hmm_min_regime`, `hmm_prob_col`, `hmm_prob_min`, `regime_col`, `cross_up_col`, `ppo_hist_col`, `ppo_hist_positive_col`, `ppo_above_signal_col`, `hmm_ok_col`, `long_setup_col`, `signal_col`, `candidate_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: vwap_rms_ema_cross_long_hmm_gate
  params:
    ema_mid_col: ema_50
    ema_slow_col: ema_96
    ema_mid_rms_col: ema_50__root_mean_square
    vwap_rms_col: vwap_40__root_mean_square
    ppo_col: ppo_12_36
    ppo_signal_col: ppo_signal_9
    ppo_hist_min: 0.0002
    hmm_regime_col: hmm_regime
    hmm_min_regime: 1
    hmm_prob_col: null
    hmm_prob_min: null
    regime_col: ema_50_above_ema_96
    cross_up_col: vwap_40_rms_cross_above_ema_50_rms
    ppo_hist_col: ppo_hist_12_36_9
    ppo_hist_positive_col: ppo_hist_12_36_9_positive
    ppo_above_signal_col: ppo_12_36_above_ppo_signal_9
    hmm_ok_col: hmm_regime_ok
    long_setup_col: vwap_40_rms_ema_50_cross_long_hmm_setup
    signal_col: signal_side
    candidate_col: signal_candidate
    output_cols:
    - signal_side
    - signal_candidate
```

### `vwap_rms_ema_cross_long`

**Τι μετρά και τι πληροφορία δίνει.** Εντοπίζει long cross setup από VWAP, RMS και EMA με προαιρετική PPO/MFI επιβεβαίωση. Το signal 1 εμφανίζεται στο configured crossing ή setup event όταν όλα τα trend, momentum και liquidity φίλτρα συμφωνούν, αλλιώς παραμένει 0.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `ema_mid_col`, `ema_slow_col`, `ema_mid_rms_col`, `vwap_rms_col`, `ppo_col`, `ppo_signal_col`, `mfi_col`, `regime_col`, `short_regime_col`, `cross_up_col`, `cross_down_col`, `ppo_hist_col`, `ppo_hist_positive_col`, `ppo_hist_negative_col`, `ppo_above_signal_col`, `ppo_below_signal_col`, `mfi_confirmation_col`, `long_setup_col`, `short_setup_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `ema_mid_col`, `ema_slow_col`, `ema_mid_rms_col`, `vwap_rms_col`, `ppo_col`, `ppo_signal_col`, `ppo_hist_min`, `use_ppo_confirmation`, `use_ema_regime`, `use_vwap_rms_cross`, `use_mfi_confirmation`, `mfi_col`, `mfi_lower`, `mfi_upper`, `entry_delay_bars`, `mode`, `regime_col`, `short_regime_col`, `cross_up_col`, `cross_down_col`, `ppo_hist_col`, `ppo_hist_positive_col`, `ppo_hist_negative_col`, `ppo_above_signal_col`, `ppo_below_signal_col`, `mfi_confirmation_col`, `long_setup_col`, `short_setup_col`, `signal_col`, `candidate_col`, `output_cols`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: vwap_rms_ema_cross_long
  params:
    ema_mid_col: ema_50
    ema_slow_col: ema_100
    ema_mid_rms_col: ema_50__root_mean_square
    vwap_rms_col: vwap_20__root_mean_square
    ppo_col: ppo
    ppo_signal_col: ppo_signal
    ppo_hist_min: 0.0
    use_ppo_confirmation: true
    use_ema_regime: true
    use_vwap_rms_cross: true
    use_mfi_confirmation: false
    mfi_col: mfi_14
    mfi_lower: 40.0
    mfi_upper: 80.0
    entry_delay_bars: 0
    mode: long_only
    regime_col: ema_50_above_ema_100
    short_regime_col: ema_50_below_ema_100
    cross_up_col: vwap_rms_cross_above_ema_50_rms
    cross_down_col: vwap_rms_cross_below_ema_50_rms
    ppo_hist_col: ppo_hist
    ppo_hist_positive_col: ppo_hist_positive
    ppo_hist_negative_col: ppo_hist_negative
    ppo_above_signal_col: ppo_above_signal
    ppo_below_signal_col: ppo_below_signal
    mfi_confirmation_col: mfi_confirmation
    long_setup_col: vwap_rms_ema_cross_long_setup
    short_setup_col: vwap_rms_ema_cross_short_setup
    signal_col: signal_side
    candidate_col: signal_candidate
    output_cols:
    - signal_side
    - signal_candidate
```

### `regime_filtered`

**Τι μετρά και τι πληροφορία δίνει.** Περνά ένα υπάρχον base signal μόνο όταν η regime στήλη έχει την ενεργή τιμή. Η κατεύθυνση και το μέγεθος του αρχικού signal διατηρούνται, ενώ όλα τα μη επιτρεπόμενα regimes μηδενίζονται· το φίλτρο δεν δημιουργεί δική του κατεύθυνση.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `base_signal_col`, `regime_col`, `signal_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: υποχρεωτικές `base_signal_col`, `regime_col`; με προεπιλογή `signal_col`, `active_value`.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: regime_filtered
  params:
    base_signal_col: <required>
    regime_col: <required>
    signal_col: null
    active_value: 1.0
```

## Παρωχημένα aliases signals

### `ehlers_continuation_long_signal`

**Τι μετρά και τι πληροφορία δίνει.** Είναι παλιό alias του `ehlers_continuation_long` και εκφράζει το ίδιο long continuation setup. Υπάρχει μόνο για αναπαραγωγή παλαιών YAML· νέα configs πρέπει να χρησιμοποιούν το canonical όνομα χωρίς κατάληξη `_signal`.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `ema_fast_col`, `ema_slow_col`, `mama_col`, `fama_col`, `roofing_col`, `roofing_slope_col`, `decycler_osc_col`, `ema_condition_col`, `mama_condition_col`, `roofing_positive_col`, `roofing_slope_positive_col`, `roofing_gt_slope_col`, `decycler_positive_col`, `state_col`, `entry_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `entry_mode`, `entry_delay_bars`, `long_only`, `use_ema_regime`, `use_mama_fama`, `use_roofing_gt_slope`, `use_decycler`, `ema_fast_col`, `ema_slow_col`, `mama_col`, `fama_col`, `roofing_col`, `roofing_slope_col`, `decycler_osc_col`, `ema_condition_col`, `mama_condition_col`, `roofing_positive_col`, `roofing_slope_positive_col`, `roofing_gt_slope_col`, `decycler_positive_col`, `state_col`, `entry_col`, `signal_col`, `candidate_col`, `output_cols`.

Κατάσταση: **παρωχημένο alias μόνο για συμβατότητα**.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ehlers_continuation_long_signal
  params:
    entry_mode: state
    entry_delay_bars: 0
    long_only: true
    use_ema_regime: true
    use_mama_fama: true
    use_roofing_gt_slope: true
    use_decycler: true
    ema_fast_col: ema_50
    ema_slow_col: ema_100
    mama_col: mama
    fama_col: fama
    roofing_col: roofing_filter_48_10
    roofing_slope_col: roofing_filter_48_10_slope
    decycler_osc_col: decycler_oscillator_30_60
    ema_condition_col: ehlers_continuation_ema50_gt_ema100
    mama_condition_col: ehlers_continuation_mama_gt_fama
    roofing_positive_col: ehlers_continuation_roofing_gt_zero
    roofing_slope_positive_col: ehlers_continuation_roofing_slope_gt_zero
    roofing_gt_slope_col: ehlers_continuation_roofing_gt_slope
    decycler_positive_col: ehlers_continuation_decycler_osc_gt_zero
    state_col: ehlers_continuation_long_state
    entry_col: ehlers_continuation_long_entry
    signal_col: ehlers_continuation_signal
    candidate_col: ehlers_continuation_candidate
    output_cols:
    - ehlers_continuation_signal
    - ehlers_continuation_candidate
```

### `ehlers_continuation_short_signal`

**Τι μετρά και τι πληροφορία δίνει.** Είναι παλιό alias του `ehlers_continuation_short` και εκφράζει το ίδιο short continuation setup. Υπάρχει μόνο για συμβατότητα και δεν πρέπει να χρησιμοποιείται σε νέα πειράματα, ώστε τα registries και τα reports να έχουν ενιαία ονοματολογία.

**Είσοδοι και έξοδοι.** Το signal δηλώνει τις στήλες εισόδου και τα παραμετροποιήσιμα ονόματα εξόδου μέσω των `ema_fast_col`, `ema_slow_col`, `mama_col`, `fama_col`, `roofing_col`, `roofing_slope_col`, `decycler_osc_col`, `ema_condition_col`, `mama_condition_col`, `roofing_negative_col`, `roofing_slope_negative_col`, `roofing_lt_slope_col`, `decycler_negative_col`, `state_col`, `entry_col`, `signal_col`, `candidate_col`. Η προηγούμενη παράγραφος εξηγεί την οικονομική σημασία της εξόδου, ενώ το YAML δείχνει τα ακριβή ονόματα στηλών που διαβάζονται ή γράφονται. Όλες οι παράμετροι, μαζί με τις προεπιλογές και τις υποχρεωτικές τιμές, εμφανίζονται παρακάτω.

**Χρονική ορθότητα και αποφυγή διαρροής.** Το signal χρησιμοποιεί μόνο στήλες διαθέσιμες στην κλεισμένη ράβδο `t`. Οι πιθανότητες ή προβλέψεις μοντέλου πρέπει να έχουν παραχθεί εκτός δείγματος όπου το συμβόλαιο το απαιτεί, και η θέση πρέπει να εκτελείται με τη χρονική σύμβαση της προσομοίωσης, συνήθως στο επόμενο άνοιγμα.

**Παράμετροι.** Οι παράμετροι του contract είναι: με προεπιλογή `entry_mode`, `entry_delay_bars`, `short_only`, `use_ema_regime`, `use_mama_fama`, `use_roofing_lt_slope`, `use_decycler`, `ema_fast_col`, `ema_slow_col`, `mama_col`, `fama_col`, `roofing_col`, `roofing_slope_col`, `decycler_osc_col`, `ema_condition_col`, `mama_condition_col`, `roofing_negative_col`, `roofing_slope_negative_col`, `roofing_lt_slope_col`, `decycler_negative_col`, `state_col`, `entry_col`, `signal_col`, `candidate_col`, `output_cols`.

Κατάσταση: **παρωχημένο alias μόνο για συμβατότητα**.

**Πλήρες YAML παράδειγμα:**

```yaml
signals:
  kind: ehlers_continuation_short_signal
  params:
    entry_mode: state
    entry_delay_bars: 0
    short_only: true
    use_ema_regime: true
    use_mama_fama: true
    use_roofing_lt_slope: true
    use_decycler: true
    ema_fast_col: ema_50
    ema_slow_col: ema_100
    mama_col: mama
    fama_col: fama
    roofing_col: roofing_filter_48_10
    roofing_slope_col: roofing_filter_48_10_slope
    decycler_osc_col: decycler_oscillator_30_60
    ema_condition_col: ehlers_continuation_ema50_lt_ema100
    mama_condition_col: ehlers_continuation_mama_lt_fama
    roofing_negative_col: ehlers_continuation_roofing_lt_zero
    roofing_slope_negative_col: ehlers_continuation_roofing_slope_lt_zero
    roofing_lt_slope_col: ehlers_continuation_roofing_lt_slope
    decycler_negative_col: ehlers_continuation_decycler_osc_lt_zero
    state_col: ehlers_continuation_short_state
    entry_col: ehlers_continuation_short_entry
    signal_col: ehlers_continuation_signal
    candidate_col: ehlers_continuation_candidate
    output_cols:
    - ehlers_continuation_signal
    - ehlers_continuation_candidate
```
