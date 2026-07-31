# Κατάλογος Signals

Τελευταία ενημέρωση: 2026-06-29

Αυτό το αρχείο τεκμηριώνει τα signal kinds που είναι διαθέσιμα μέσω του
`SIGNAL_REGISTRY` στο `src/signals/registry.py`.

Τα signals είναι το στάδιο που μετατρέπει features, rules, model forecasts ή
probabilities σε εκτελέσιμη πρόθεση: long, short, flat ή continuous exposure.
Δεν είναι όλα τα signals ίδιας φύσης. Άλλα είναι απλά indicator baselines, άλλα
παράγουν primary candidates, άλλα φιλτράρουν candidates με model probability και
άλλα δίνουν continuous sizing. Για αυτό το catalog εξηγεί για κάθε signal:

- τι μετρά ή τι συνδυάζει,
- τι πληροφορία δίνουν οι τιμές που παράγει,
- πώς να το ερμηνεύεις πρακτικά σε ένα experiment,
- ένα μικρό παράδειγμα ανάγνωσης.

## Πώς διαβάζεις τις τιμές των signals

Οι πιο συνηθισμένες output στήλες είναι:

- `signal`, `signal_side` ή custom `signal_col`: η τελική πλευρά ή έκθεση.
- `candidate_col` ή `signal_candidate`: αν το row είναι υποψήφιο setup.
- `position`: κρατούμενη θέση, όταν το signal έχει state/hold λογική.
- `entry_*` και `exit_*`: event flags για άνοιγμα/κλείσιμο θέσης.
- Diagnostic flags όπως `*_pass`, `*_setup`, `*_candidate`: εξηγούν γιατί ένα
  row έγινε ή δεν έγινε signal.

Η γενική ερμηνεία τιμών είναι:

- `1`: long πρόθεση ή θετικό candidate.
- `-1`: short πρόθεση.
- `0`: flat, καμία πρόθεση, ή setup που δεν πέρασε τα filters.
- Continuous τιμές, π.χ. `0.35` ή `-0.70`: μέγεθος έκθεσης/conviction, όχι
  απαραίτητα διακριτή θέση. Το πρόσημο δείχνει πλευρά και το απόλυτο μέγεθος
  δείχνει ένταση.
- `candidate_col = 1`: το row είναι trade candidate. Δεν σημαίνει πάντα ότι θα
  εκτελεστεί, ειδικά αν ακολουθεί model filter.
- `entry_col = 1`: event στο συγκεκριμένο bar. Συνήθως το backtest εφαρμόζει
  execution lag, π.χ. signal στο close και εκτέλεση στο επόμενο open.

Σημαντικός κανόνας: όποιο signal χρησιμοποιεί `pred_prob`, `pred_ret`,
`pred_vol` ή άλλο model output πρέπει να τροφοδοτείται από out-of-sample
prediction. In-sample probability μέσα σε trading signal είναι leakage.

## Κατηγορίες

| Κατηγορία | Signals | Τι αντιπροσωπεύει |
| --- | --- | --- |
| No-op / diagnostic | `none` | Τρέχεις pipeline χωρίς πραγματικό trading signal ή με explicit flat signal. |
| Indicator baselines | `trend_state`, `rsi`, `momentum`, `stochastic`, `volatility_regime` | Απλοί κανόνες από ένα βασικό feature ή regime. |
| Probability και forecast signals | `probability_threshold`, `probability_conviction`, `probability_vol_adjusted`, `meta_probability_side`, `manual_long_model_filter`, `dense_return_forecast`, `forecast_threshold`, `forecast_vol_adjusted` | Μετατροπή model probability ή return forecast σε side, filter ή sizing. |
| Primary candidate generators | `orb_candidate_side`, `roc_long_only_conditions`, `ema_stoch_rsi_pullback`, `indicator_model_adaptive_pullback`, `quote_flow_scalp_router`, `ppo_adx_stochrsi_trend`, `stc_roofing_hilbert` | Παράγουν υποψήφια trades από rule logic πριν από model filtering. |
| VWAP / EMA / RMS composite setups | `vwap_rms_ema_cross_long`, `vwap_rms_ema_cross_long_hmm_gate`, `vwap_rms_ema_cross_long_fractal_filter`, `ema_rms_ppo_vwap`, `c1_trend_pullback_vwap`, `c2_regime_aware_momentum` | Συνδυάζουν trend, VWAP/RMS, PPO, volatility/regime και pullback context. |
| Ehlers / cycle-based setups | `ehlers_continuation_long`, `ehlers_continuation_short`, `ehlers_decycler_continuation`, `ehlers_semiscalp_long` | Χρησιμοποιούν MAMA/FAMA, Roofing, Hilbert, Decycler και cycle context. |
| Wrapper / filter | `regime_filtered` | Κρατά ένα base signal μόνο όταν ένα regime column είναι ενεργό. |
| Deprecated aliases | `ehlers_continuation_long_signal`, `ehlers_continuation_short_signal` | Παλιά ονόματα που δείχνουν στα αντίστοιχα Ehlers continuation signals. |

## Γλωσσάρι signal όρων

- Signal: η τελική πρόθεση θέσης ή έκθεσης που μπορεί να διαβαστεί από
  backtest/execution layer.
- Candidate: υποψήφιο setup. Δεν είναι υποχρεωτικά τελικό trade, γιατί μπορεί
  να ακολουθήσει model filter ή regime filter.
- Side: πλευρά του trade, συνήθως `1` για long και `-1` για short.
- Entry/exit event: σημαία που ανάβει μόνο στο bar όπου ανοίγει ή κλείνει η
  λογική θέση.
- Continuous exposure: αριθμός όπως `0.35` ή `-0.70`, όπου το πρόσημο είναι
  πλευρά και το μέγεθος είναι conviction/sizing.
- Filter/gate: συνθήκη που επιτρέπει ή απορρίπτει ένα ήδη υπάρχον signal.

## No-op και βασικά baselines

### `none`

Τι μετρά:

- Δεν μετρά market condition και δεν παράγει πραγματικό trading setup.
- Είναι επιλογή για EDA, feature-only runs ή sanity checks.

Τι σημαίνουν οι τιμές:

- Αν δεν ζητηθεί output column, πρακτικά δεν αλλάζει το dataframe.
- Αν δοθεί `signal_col`, γράφει flat `0` σε όλα τα rows.

Παράδειγμα:

- Σε feature research run θέλεις να δεις distributions, correlations και target
  diagnostics χωρίς backtest. Χρησιμοποιείς `signals.kind: none`. Αν το output
  γράψει `signal = 0`, κάθε row λέει "καμία θέση".

### `trend_state`

Τι μετρά:

- Μετατρέπει ένα ήδη υπολογισμένο trend/regime state σε directional exposure.
- Συνήθως το `state_col` προέρχεται από moving average state ή άλλο trend
  classifier.

Τι σημαίνουν οι τιμές:

- `state_col > 0` -> long.
- `state_col < 0` -> short.
- `state_col = 0` -> flat, εκτός αν χρησιμοποιείται hold mode που κρατά την
  προηγούμενη πλευρά.

Παράδειγμα:

- Αν `ema_fast > ema_slow`, το upstream feature γράφει `trend_state = 1`.
  Το `trend_state` signal παράγει `signal_trend_state = 1`, δηλαδή long bias.
  Αν στο επόμενο row το state γίνει `0`, σε απλό mode γίνεται flat, ενώ σε
  `long_short_hold` μπορεί να κρατήσει την προηγούμενη θέση μέχρι να αλλάξει η
  πλευρά.

### `rsi`

Τι μετρά:

- Τη θέση του RSI σε σχέση με oversold/overbought thresholds.
- Είναι oscillator baseline, συνήθως mean-reversion rule.

Τι σημαίνουν οι τιμές:

- `RSI < buy_level` -> long.
- `RSI > sell_level` -> short, αν το mode επιτρέπει shorts.
- Ενδιάμεσες τιμές -> flat ή διατήρηση θέσης σε hold mode.

Παράδειγμα:

- Με `buy_level = 30` και `sell_level = 70`, row με `RSI = 24` δίνει long
  signal γιατί η αγορά θεωρείται oversold. Row με `RSI = 78` δίνει short signal
  γιατί θεωρείται overbought. Σε ισχυρό trend αυτό μπορεί να δώσει πρόωρα
  contrarian trades, άρα θέλει regime έλεγχο.

### `momentum`

Τι μετρά:

- Ένα precomputed momentum column σε σχέση με θετικό και αρνητικό threshold.
- Είναι απλό trend/momentum baseline.

Τι σημαίνουν οι τιμές:

- `momentum > long_threshold` -> long.
- `momentum < short_threshold` -> short.
- Αν δεν δοθεί `short_threshold`, συνήθως χρησιμοποιείται συμμετρικό
  `-abs(long_threshold)`.

Παράδειγμα:

- Αν `momentum_20 = 0.035` και `long_threshold = 0.02`, το signal λέει ότι το
  πρόσφατο momentum είναι αρκετά θετικό για long. Αν `momentum_20 = -0.03`, σε
  long-short mode η ένδειξη γίνεται short.

### `stochastic`

Τι μετρά:

- Τη θέση του Stochastic `%K` μέσα στο πρόσφατο high-low range.
- Είναι oscillator baseline, χρήσιμο σε range-bound συνθήκες.

Τι σημαίνουν οι τιμές:

- `%K < buy_level` -> long/oversold.
- `%K > sell_level` -> short/overbought.
- Ενδιάμεσες τιμές -> flat ή hold.

Παράδειγμα:

- Αν `%K = 12` με `buy_level = 20`, το close βρίσκεται κοντά στο κάτω μέρος του
  πρόσφατου range και το signal μπορεί να δώσει long mean-reversion setup. Αν
  `%K = 91`, δίνει short exhaustion setup.

### `volatility_regime`

Τι μετρά:

- Αν το τρέχον volatility είναι κάτω ή πάνω από causal expanding quantile.
- Είναι risk-on/risk-off regime baseline.

Τι σημαίνουν οι τιμές:

- `vol <= shifted_threshold` -> low-vol regime, συνήθως long/risk-on.
- `vol > shifted_threshold` -> high-vol regime, short/risk-off αν επιτρέπεται.
- Το threshold είναι causal όταν γίνεται `shift(1)`.

Παράδειγμα:

- Αν το rolling volatility είναι στο χαμηλότερο 40% της ιστορίας, το signal
  μπορεί να γράψει `1`, δηλαδή περιβάλλον που επιτρέπει risk-on exposure. Αν
  περάσει πάνω από το quantile threshold, γράφει `-1` ή flat ανάλογα με το mode.

## Probability και forecast signals

### `probability_threshold`

Τι μετρά:

- Μετατρέπει classifier probability σε discrete long/short/flat signal.
- Με `base_signal_col`, λειτουργεί ως model filter πάνω σε ήδη υπάρχον signal.

Τι σημαίνουν οι τιμές:

- `prob > upper` -> long ή αποδοχή long base signal.
- `prob < lower` -> short ή αποδοχή short base signal.
- `lower <= prob <= upper` -> dead-zone, flat ή διατήρηση state με hysteresis.
- `upper_exit` και `lower_exit` μειώνουν flip-flopping γύρω από threshold.

Παράδειγμα:

- Με `upper = 0.58` και `lower = 0.42`, `pred_prob = 0.64` σημαίνει ότι το
  model έχει αρκετά θετική πιθανότητα για long. `pred_prob = 0.51` δεν είναι
  αρκετά μακριά από την αβεβαιότητα, άρα το row μένει flat.

### `probability_conviction`

Τι μετρά:

- Τη signed απόσταση της πιθανότητας από το `0.5`.
- Είναι continuous sizing rule.

Τι σημαίνουν οι τιμές:

- Τύπος: `clip * (prob - 0.5) * 2`.
- `prob = 0.5` -> `0`, καμία conviction.
- `prob > 0.5` -> positive exposure.
- `prob < 0.5` -> negative exposure.
- Το `clip` ορίζει μέγιστη απόλυτη έκθεση.

Παράδειγμα:

- Με `clip = 1`, `pred_prob = 0.60` δίνει περίπου `0.20`. Δεν λέει "full long",
  λέει "ήπιο long conviction". `pred_prob = 0.80` δίνει περίπου `0.60`, άρα
  ισχυρότερη θέση.

### `probability_vol_adjusted`

Τι μετρά:

- Συνδυάζει model probability, volatility forecast και optional activation
  filters.
- Είναι risk-adjusted continuous exposure.

Τι σημαίνουν οι τιμές:

- Το πρόσημο έρχεται από το probability conviction γύρω από `prob_center`.
- Το μέγεθος αυξάνεται όταν η πιθανότητα είναι πιο ακραία.
- Το μέγεθος μειώνεται όταν το volatility είναι υψηλό, αν χρησιμοποιείται
  `vol_target`.
- Με `top_quantile` ή `max_trade_rate`, κρατά μόνο τις ισχυρότερες ιστορικά
  convictions με shifted threshold.

Παράδειγμα:

- Δύο rows έχουν `pred_prob = 0.65`. Αν στο πρώτο `pred_vol = 0.01` και στο
  δεύτερο `pred_vol = 0.04`, το πρώτο μπορεί να πάρει μεγαλύτερο exposure,
  επειδή το ίδιο directional edge έχει χαμηλότερο αναμενόμενο risk.

### `meta_probability_side`

Τι μετρά:

- Την πιθανότητα επιτυχίας ενός ήδη προτεινόμενου candidate.
- Δεν προβλέπει απαραίτητα αν η αγορά θα ανέβει. Προβλέπει αν η προτεινόμενη
  πλευρά αξίζει εκτέλεση.

Τι σημαίνουν οι τιμές:

- `candidate_col = 1` και `prob >= threshold` -> εκτέλεσε την πλευρά του
  `side_col`.
- `prob < threshold` -> flat.
- Δεν αντιστρέφει πλευρά. Αν το primary side είναι long και το probability
  χαμηλό, το output είναι `0`, όχι short.

Παράδειγμα:

- Το primary setup δίνει `side_col = -1` για short και `candidate_col = 1`.
  Το meta model δίνει `pred_prob = 0.63` με threshold `0.60`. Το
  `meta_probability_side` γράφει `-1`, δηλαδή αποδέχεται το short candidate.

### `manual_long_model_filter`

Τι μετρά:

- Αν ένα manual long candidate έχει αρκετή model probability για να κρατηθεί.
- Είναι ειδική long-only meta-labeling διαδρομή.

Τι σημαίνουν οι τιμές:

- Candidate ενεργό και `prob >= threshold` -> κρατά το long exposure του
  `base_signal_col`.
- Candidate ανενεργό ή probability χαμηλή -> `0`.
- Δεν παράγει shorts.

Παράδειγμα:

- Manual rule γράφει `base_signal = 0.8` και `candidate = 1`. Αν το model δώσει
  `pred_prob = 0.57` με threshold `0.55`, το filtered signal μένει `0.8`. Αν
  δώσει `0.49`, μηδενίζεται.

### `dense_return_forecast`

Τι μετρά:

- Ένα dense return forecast αφού αφαιρεθεί εκτιμώμενο κόστος και slippage.
- Είναι καθαρή αναμενόμενη απόδοση μετά από friction, όχι binary signal.

Τι σημαίνουν οι τιμές:

- Θετική τιμή -> θετικό net expected return.
- Αρνητική τιμή -> αρνητικό net expected return.
- Κοντά στο `0` -> forecast που δεν ξεπερνά costs/noise.
- Αν `forecast_is_vol_normalized = true`, το κόστος μετατρέπεται στην ίδια
  volatility-normalized μονάδα.

Παράδειγμα:

- Raw forecast `0.0018`, round-trip κόστος `0.0006` και slippage `0.0002`
  οδηγούν σε net περίπου `0.0010`. Το signal δεν λέει απλώς long, λέει ότι το
  καθαρό forecast είναι +10 bps στην κλίμακα του target.

### `forecast_threshold`

Τι μετρά:

- Μετατρέπει return forecast, συνήθως `pred_ret`, σε discrete long/short/flat.

Τι σημαίνουν οι τιμές:

- `forecast > upper` -> long.
- `forecast < lower` -> short.
- Ανάμεσα στα thresholds -> flat ή hold.
- Αν δεν δοθεί `lower`, χρησιμοποιείται `-abs(upper)`.

Παράδειγμα:

- Με `upper = 0.002`, forecast `0.0031` σημαίνει ότι το predicted return
  ξεπερνά το trade threshold και δίνει long. Forecast `0.0004` μένει flat γιατί
  είναι μικρό σε σχέση με costs και estimation error.

### `forecast_threshold_candidate`

What it measures:

- The same discrete forecast-threshold signal as `forecast_threshold`.
- OOS-only candidate metadata for downstream path-dependent target construction.

Outputs:

- Signal output from `signal_col`, for example `signal_structured_tail`.
- `primary_candidate`: `1` only when the row is OOS, thresholded, and all activation filters pass.
- `primary_candidate_side`: `+1` for long candidates, `-1` for short candidates, `0` otherwise.
- `primary_candidate_strength`: `abs(pred_ret)` on candidate rows, `0` otherwise.
- `primary_candidate_threshold_distance`: `pred_ret - upper` for long candidates and `abs(pred_ret) - abs(lower)` for short candidates.

Leakage policy:

- `pred_is_oos_col` is required by default.
- In-sample predictions never create candidates even if `pred_ret` crosses the forecast threshold.
- Activation filters are evaluated on already-materialized point-in-time feature columns.

Minimal YAML:

```yaml
signals:
  kind: forecast_threshold_candidate
  params:
    forecast_col: pred_ret
    pred_is_oos_col: pred_is_oos
    signal_col: signal_structured_tail
    upper: 0.7
    lower: -0.85
    mode: long_short
    activation_filters:
      - {col: atr_pct_rank_192, op: ge, value: 0.25}
      - {col: atr_pct_rank_192, op: le, value: 0.85}
      - {col: range_to_atr, op: ge, value: 0.9}
      - {col: bollinger_bandwidth_rank_192, op: ge, value: 0.4}
```

### `forecast_vol_adjusted`

Τι μετρά:

- Το forecast ως signal-to-risk ratio: `forecast / volatility`.
- Είναι continuous sizing από regression forecast και volatility forecast.

Τι σημαίνουν οι τιμές:

- Θετικό output -> long exposure.
- Αρνητικό output -> short exposure.
- Μεγαλύτερο απόλυτο output -> forecast μεγάλο σε σχέση με risk.
- Το `tanh` και το `clip` περιορίζουν ακραίες τιμές.

Παράδειγμα:

- `pred_ret = 0.004` και `pred_vol = 0.02` δίνουν ratio `0.20`, άρα ήπιο long
  sizing. Αν το ίδιο forecast είχε `pred_vol = 0.005`, το ratio θα ήταν πολύ
  ισχυρότερο, άρα μεγαλύτερο exposure.

## Primary candidate generators

Στα ελληνικά, αυτή η ενότητα αφορά generators υποψήφιων setups: κανόνες που
λένε "εδώ υπάρχει πιθανό trade" πριν αποφασίσει ένα meta model ή άλλο φίλτρο αν
το trade θα εκτελεστεί.

### `orb_candidate_side`

Τι μετρά:

- Τη raw πλευρά ενός Opening Range Breakout candidate.
- Είναι diagnostic baseline πριν από model filtering και δεν χρησιμοποιεί ML.
- Διαβάζει μόνο τα ήδη υπολογισμένα `orb_candidate` και `orb_side` από το
  `opening_range_breakout` feature· δεν ξαναϋπολογίζει session, range, buffer
  ή breakout condition.

Τι σημαίνουν οι τιμές:

- `candidate_col = 1` -> γράφει την πλευρά του `side_col`.
- `candidate_col = 0` -> flat.
- `mode: long_only` κρατά μόνο positive side, `short_only` μόνο negative side
  και `long_short` και τις δύο πλευρές.
- Δεν χρησιμοποιεί probabilities, thresholds, ATR/trend filters ή risk logic.

Το `post_breakout_active_bars` ανήκει στο upstream feature. Με τιμή `1`, το
raw signal είναι event-like και εμφανίζεται μόνο στο πρώτο breakout bar. Με
μεγαλύτερη τιμή, το ίδιο candidate/side παραμένει ενεργό για τόσα bars και
εκφράζει exposure window, όχι πολλαπλά ανεξάρτητα breakout trades. Η entry
timing, execution lag και exits αξιολογούνται στο backtest/execution layer.

Παράδειγμα:

- Αν το ORB rule γράψει `side_col = 1` μετά από breakout πάνω από το opening
  range, το `orb_candidate_side` γράφει `1`. Αν μετά το meta model κρατά μόνο
  το 40% αυτών των trades, αυτό το raw signal είναι το benchmark σύγκρισης.

### `roc_long_only_conditions`

Τι μετρά:

- Συνδυασμό χειροκίνητων long-only συνθηκών: ROC, volatility regime, z-score
  τιμής, candle confirmation, multi-timeframe trend και optional macro condition.

Τι σημαίνουν οι τιμές:

- Τα `cond_*` columns δείχνουν ποιες επιμέρους συνθήκες πέρασαν.
- `manual_conviction_score` δείχνει πόση confluence υπάρχει.
- Το τελικό signal είναι long-only και συχνά volatility-adjusted.
- Υψηλότερο score σημαίνει περισσότερες συνθήκες υπέρ του setup, όχι εγγύηση
  κέρδους.

Παράδειγμα:

- Ένα row δεν είναι weekend, έχει θετικό ROC, όχι bearish 1h/4h trend και
  bullish candle. Αν περάσει το score threshold, γράφει long candidate. Αν όμως
  το volatility z-score είναι πολύ υψηλό, το exposure μπορεί να μειωθεί.

### `ema_stoch_rsi_pullback`

Τι μετρά:

- Πρώτο StochRSI pullback μετά από EMA trend cross.
- Συνδυάζει EMA fast/slow trend shift, StochRSI oversold/overbought reset ή
  cross και optional price confirmation.

Τι σημαίνουν οι τιμές:

- `side_col = 1` -> long pullback μετά από bullish EMA cross.
- `side_col = -1` -> short pullback μετά από bearish EMA cross.
- `candidate_col = 1` -> ενεργό setup στο συγκεκριμένο bar.
- Diagnostic columns όπως `*_bars_since_bull_cross`, `*_first_oversold_*` και
  `*_long_entry` δείχνουν την ακριβή αιτία.

Παράδειγμα:

- Η `ema_50` περνά πάνω από την `ema_150`. Μέσα στα επόμενα 30 bars το StochRSI
  πέφτει oversold και μετά ανακτά πάνω από το threshold με `%K > %D`. Το signal
  γράφει `1`, δηλαδή long pullback entry μέσα σε νέο ανοδικό regime.

### `indicator_model_adaptive_pullback`

Τι μετρά:

- Interpretable long/short pullback candidates από trend, pullback distance,
  momentum confirmation και volatility/bandwidth regime.
- Σχεδιάστηκε ως primary signal πριν από `meta_probability_side`.

Τι σημαίνουν οι τιμές:

- `candidate_long = 1` -> ανοδικό trend, αποδεκτό pullback, bullish momentum,
  αποδεκτό volatility.
- `candidate_short = 1` -> αντίστοιχο bearish setup.
- `direction` ή `signal = 1/-1/0` δείχνει προτεινόμενη πλευρά.
- `signal_score` μετρά πόσα βασικά blocks πέρασαν.

Παράδειγμα:

- EMA stack `20 > 50 > 100`, θετικές slopes, ADX σε λογικό εύρος, τιμή κοντά
  στην EMA fast/mid, StochRSI cross up και MACD histogram που βελτιώνεται. Το
  signal δίνει `candidate_long = 1` και `direction = 1`.

### `quote_flow_scalp_router`

Τι μετρά:

- Deterministic primary scalp candidates από ήδη υπολογισμένα quote/spread,
  candle-flow proxy, VWAP distance, support/resistance, volume και session
  features.
- Δεν κάνει heavy feature engineering εσωτερικά. Οι proxy flow columns πρέπει
  να έχουν παραχθεί από `scalp_microstructure_proxy`, `order_flow_imbalance`,
  `vpin` και helpers.

Τι σημαίνουν οι τιμές:

- `signal_candidate = 1` -> υπάρχει primary scalp setup στο current closed bar.
- `signal_side = 1/-1/0` -> long, short ή flat candidate side.
- `signal_mode = 1` -> toxic-flow continuation, `2` -> liquidity-sweep fade,
  `3` -> VWAP snapback.
- `quote_flow_score` είναι deterministic mode score για audit/model input, όχι
  fitted probability.
- `qfs_cond_*` columns δείχνουν ποια mode/filter conditions πέρασαν.

Λογική:

- Global gates: spread rank/z-score κάτω από thresholds και optional liquid
  session flag.
- Toxic continuation: high VPIN rank, aligned fast/slow OFI proxy, high
  relative volume και close near bar extreme.
- Sweep fade: large wick, recovery/rejection close position, close κοντά σε
  support/resistance και OFI proxy που δείχνει sweep pressure.
- VWAP snapback: large ATR-scaled VWAP displacement, moderate VPIN rank και
  wick/recovery confirmation.
- Αν περάσουν πολλά modes στο ίδιο row, priority είναι sweep fade, μετά toxic
  continuation, μετά VWAP snapback.

Παράδειγμα:

- Row με low spread rank, liquid session, `lower_wick_atr=0.5`,
  `close_pos_in_bar=0.7`, `close_minus_support_atr=0.2` και αρνητικό fast OFI
  proxy γράφει long sweep-fade candidate (`signal_side=1`, `signal_mode=2`).
  Αν ακολουθεί meta model, το top-level `meta_probability_side` κρατά το
  candidate μόνο όταν το OOS `pred_prob` περνά threshold.

### `ppo_adx_stochrsi_trend`

Τι μετρά:

- Stateful trend-continuation strategy με EMA trend, PPO, ADX/DI, StochRSI
  trigger και ATR stop/take-profit diagnostics.

Τι σημαίνουν οι τιμές:

- `entry_long = 1` ή `entry_short = 1` -> νέο entry event.
- `position = 1/-1/0` -> τρέχουσα κρατούμενη θέση.
- `signal` συνήθως αντιγράφει το `position`.
- `exit_*` flags δείχνουν έξοδο λόγω αντίθετης κατεύθυνσης, PPO slope ή price
  κάτω/πάνω από EMA fast.
- ATR stop/take-profit columns δείχνουν ενδεικτικά risk levels.

Παράδειγμα:

- EMA fast πάνω από EMA slow, PPO και PPO signal θετικά, `+DI > -DI`, ADX πάνω
  από 20 και StochRSI bullish reset. Γράφεται `entry_long = 1` και το
  `position` γίνεται `1` μέχρι να εμφανιστεί exit rule ή αντίθετο entry.

### `stc_roofing_hilbert`

Τι μετρά:

- STC cross μαζί με Roofing Filter, optional EMA regime, optional Hilbert cycle
  filter, optional z-score/ADX/volatility filters.

Τι σημαίνουν οι τιμές:

- `stc_cross_up` πάνω από `stc_long_cross_level` και bullish filters -> long.
- `stc_cross_down` κάτω από `stc_short_cross_level` και bearish filters -> short.
- `hilbert_pass`, `adx_pass`, `volatility_pass` δείχνουν ποια optional gates
  πέρασαν.
- `candidate_col = 1` όταν υπάρχει τελικό long/short candidate.

Παράδειγμα:

- STC περνά ανοδικά το 25, EMA fast πάνω από EMA slow, Roofing positive και
  roofing slope positive. Αν τα optional filters είναι off ή περνάνε, το
  `stc_roofing_signal` γίνεται `1`.

### `regime_filtered`

Τι μετρά:

- Δεν φτιάχνει νέο alpha. Φιλτράρει ένα υπάρχον `base_signal_col` με βάση ένα
  regime column.

Τι σημαίνουν οι τιμές:

- Αν `regime_col == active_value`, κρατά την αρχική τιμή του base signal.
- Αν όχι, γράφει `0`.

Παράδειγμα:

- Έχεις `signal_momentum = 1`, αλλά θέλεις να το επιτρέπεις μόνο όταν
  `volatility_regime = 0`. Σε row με `volatility_regime = 2`, το
  `regime_filtered` μηδενίζει το momentum signal.

## VWAP / EMA / RMS composite setups

### `vwap_rms_ema_cross_long`

Τι μετρά:

- Long-only VWAP RMS cross πάνω από EMA RMS μέσα σε ανοδικό EMA regime, με PPO
  confirmation και optional MFI filter.

Τι σημαίνουν οι τιμές:

- `signal_side = 1` -> long setup.
- `signal_candidate = 1` -> το row είναι υποψήφιο long event.
- Cross flags δείχνουν ότι το VWAP RMS πέρασε πάνω από το EMA RMS.
- PPO flags δείχνουν ότι το momentum confirmation είναι θετικό.

Παράδειγμα:

- `ema_mid > ema_slow`, `vwap_rms` περνά πάνω από `ema_mid_rms`, PPO histogram
  είναι θετικό και το MFI δεν είναι ακραίο. Το signal γράφει `1`, δηλαδή long
  continuation/reclaim setup.

### `vwap_rms_ema_cross_long_hmm_gate`

Τι μετρά:

- Το ίδιο βασικό VWAP RMS / EMA RMS long setup, αλλά επιτρέπεται μόνο όταν ένα
  HMM regime είναι αρκετά ευνοϊκό.

Τι σημαίνουν οι τιμές:

- `hmm_regime >= hmm_min_regime` -> regime gate περνά.
- Αν δοθούν `hmm_prob_col` και `hmm_prob_min`, απαιτείται και αρκετή πιθανότητα
  του HMM state.
- `signal_side = 1` μόνο όταν περνούν trend, cross, PPO και HMM gate.

Παράδειγμα:

- Το VWAP RMS cross είναι bullish, αλλά `hmm_regime = 0` ενώ απαιτείται
  `hmm_min_regime = 1`. Το setup απορρίπτεται και το signal μένει `0`. Αν το
  regime γίνει `2`, το ίδιο pattern μπορεί να γίνει long candidate.

### `vwap_rms_ema_cross_long_fractal_filter`

Τι μετρά:

- Το VWAP RMS / EMA RMS long setup gated από fractal dimension trend-quality
  filter.

Τι σημαίνουν οι τιμές:

- `fractal_dimension < fractal_max` -> trend-like structure αρκετά καθαρή.
- `fractal_dimension >= fractal_max` -> πιο noisy/mean-reverting δομή, reject.
- `signal_side = 1` μόνο όταν trend, cross, PPO και fractal gate περνούν.

Παράδειγμα:

- Αν `fractal_dimension_128 = 1.32` και `fractal_max = 1.45`, το fractal gate
  περνά. Αν τα υπόλοιπα bullish conditions ισχύουν, το signal γράφει long. Με
  `fractal_dimension_128 = 1.58`, το ίδιο cross αγνοείται ως υπερβολικά noisy.

### `ema_rms_ppo_vwap`

Τι μετρά:

- EMA RMS stack, PPO confirmation και VWAP reclaim/reject κοντά στο VWAP σε ATR
  μονάδες.

Τι σημαίνουν οι τιμές:

- `ema_rms_bull_stack = 1` όταν `fast_rms > mid_rms > slow_rms`.
- `ema_rms_bear_stack = 1` όταν η σειρά είναι καθοδική.
- `vwap_reclaim = 1` -> close πέρασε πάνω από VWAP.
- `vwap_reject = 1` -> close πέρασε κάτω από VWAP.
- `signal_side = 1/-1/0` δείχνει long/short/flat setup.

Παράδειγμα:

- Σε bullish RMS stack, PPO πάνω από το signal και θετικό histogram, η τιμή
  κάνει reclaim του VWAP και απέχει λιγότερο από `1 ATR`. Το signal δίνει long.
  Στο bearish mirror, με VWAP reject και αρνητικό PPO, δίνει short.

### `c1_trend_pullback_vwap`

Τι μετρά:

- Composite trend-pullback setup γύρω από VWAP. Συνδυάζει trend regime, trigger
  πλευράς, PPO, MFI, StochRSI, z-score momentum, volatility regime και trend
  quality.

Τι σημαίνουν οι τιμές:

- `c1_long_candidate = 1` -> bullish trend, long trigger και όλα τα quality
  filters περνούν.
- `c1_short_candidate = 1` -> bearish mirror.
- `c1_*_strict_candidate = 1` -> πιο αυστηρή έκδοση με μεγαλύτερη trend quality
  και αυστηρότερα momentum/MFI thresholds.
- `signal_side = 1/-1/0` δίνει την τελική πλευρά.

Παράδειγμα:

- Trend regime bullish, long trigger ενεργό, PPO histogram θετικό, MFI μέσα στο
  επιτρεπτό εύρος, StochRSI `%K > %D`, z-score momentum πάνω από threshold και
  volatility regime όχι υπερβολικό. Το `c1_long_candidate` γίνεται `1`.

### `c2_regime_aware_momentum`

Τι μετρά:

- Regime-aware momentum continuation. Συνδυάζει trend regime, PPO/PPO signal,
  ROC, z-score momentum, ADX και allowed volatility regimes.

Τι σημαίνουν οι τιμές:

- `c2_long_candidate = 1` -> bullish trend και θετικό momentum με επαρκή ADX.
- `c2_short_candidate = 1` -> bearish trend και αρνητικό momentum.
- Τα pass flags, όπως `*_adx_pass` ή `*_volatility_pass`, εξηγούν κάθε gate.

Παράδειγμα:

- Trend regime `1`, PPO histogram θετικό, ROC θετικό, z-score momentum πάνω από
  `long_zscore_min`, ADX πάνω από `adx_min` και volatility regime μέσα στη
  whitelist. Το signal παράγει long candidate.

## Ehlers και cycle-based setups

### `ehlers_continuation_long`

Τι μετρά:

- Long-only bullish continuation από Ehlers-style features: EMA regime,
  MAMA/FAMA, Roofing Filter, Roofing slope και Decycler oscillator.

Τι σημαίνουν οι τιμές:

- `signal_side = 1` όταν το bullish state ή entry condition περνά.
- `signal_candidate = 1` όταν υπάρχει ενεργό long candidate.
- Σε `entry_mode = state`, γράφει όσο το state παραμένει αληθές.
- Σε `entry_mode = transition`, γράφει μόνο στο false-to-true entry event.

Παράδειγμα:

- EMA fast πάνω από EMA slow, MAMA πάνω από FAMA, Roofing positive και rising,
  Decycler oscillator positive. Σε transition mode το πρώτο bar που όλα
  γίνονται true γράφει `1`, τα επόμενα μπορεί να είναι `0` μέχρι νέο transition.

### `ehlers_continuation_short`

Τι μετρά:

- Short-only mirror του Ehlers continuation.

Τι σημαίνουν οι τιμές:

- `signal_side = -1` όταν EMA fast κάτω από EMA slow, MAMA κάτω από FAMA,
  Roofing negative/rising προς την short κατεύθυνση και Decycler oscillator
  negative.
- `0` όταν το bearish state δεν περνά.

Παράδειγμα:

- Σε καθοδικό EMA/MAMA regime με Roofing κάτω από το μηδέν και αρνητικό
  Decycler oscillator, το signal γράφει `-1`, δηλαδή short continuation setup.

### `ehlers_decycler_continuation`

Τι μετρά:

- Long-only continuation με βάση Decycler oscillator και decycler/close ratio.
- Χρησιμοποιεί thresholds όπως `decycler_osc_min` και `decycler_ratio_max`.

Τι σημαίνουν οι τιμές:

- `1` -> ο decycler δείχνει επαρκή ανοδική τάση/απόκλιση.
- `0` -> δεν περνά το long continuation condition.
- `entry_mode` ορίζει state ή transition συμπεριφορά.

Παράδειγμα:

- Αν ο decycler oscillator είναι `0.62` με threshold `0.45` και ο decycler ratio
  δείχνει ότι η τιμή είναι αρκετά πάνω από το decycler baseline, το signal δίνει
  long continuation.

### `ehlers_semiscalp_long`

Τι μετρά:

- Causal long-only semi-scalp setup από MAMA/FAMA, close πάνω από Decycler,
  Hilbert amplitude, Roofing trigger, Laguerre RSI, Fisher rising και optional
  dominant cycle range.

Τι σημαίνουν οι τιμές:

- `1` -> long semi-scalp entry.
- `0` -> κάποιο setup/gate δεν πέρασε.
- Diagnostic columns όπως `ehlers_semiscalp_*` δείχνουν ποιο block πέρασε.

Παράδειγμα:

- MAMA πάνω από FAMA, close πάνω από Decycler, Hilbert amplitude πάνω από το
  rolling median, Roofing cross up, Laguerre RSI πάνω από threshold και Fisher
  rising. Το signal γράφει `1` στο entry event.

## Deprecated aliases

Αυτή η ενότητα κρατά παλιά ονόματα για συμβατότητα. Σε νέα YAML προτίμησε τα
canonical names που αναφέρονται σε κάθε alias.

### `ehlers_continuation_long_signal`

Παλαιό όνομα για το long Ehlers continuation signal. Χρησιμοποίησε
`ehlers_continuation_long` σε νέα YAML configs.

Παράδειγμα:

- Αν παλιό config δηλώνει `kind: ehlers_continuation_long_signal`, η πρόθεση
  είναι η ίδια με το `ehlers_continuation_long`: long-only Ehlers continuation.

### `ehlers_continuation_short_signal`

Παλαιό όνομα για το short Ehlers continuation signal. Χρησιμοποίησε
`ehlers_continuation_short` σε νέα YAML configs.

Παράδειγμα:

- Αν παλιό config δηλώνει `kind: ehlers_continuation_short_signal`, η πρόθεση
  είναι η ίδια με το `ehlers_continuation_short`: short-only Ehlers continuation.

## Παράδειγμα YAML

```yaml
signals:
  kind: meta_probability_side
  params:
    prob_col: pred_prob
    side_col: signal_side
    candidate_col: signal_candidate
    threshold: 0.58
    signal_col: signal_meta_side
```

Ερμηνεία:

- Το primary signal έχει ήδη αποφασίσει πλευρά στο `signal_side`.
- Το model δίνει `pred_prob`, δηλαδή πιθανότητα επιτυχίας του candidate.
- Αν `pred_prob >= 0.58`, κρατάμε την ίδια πλευρά.
- Αν `pred_prob < 0.58`, δεν κάνουμε trade.

## Πρακτικός κανόνας επιλογής

- Θέλεις απλό baseline; ξεκίνα με `trend_state`, `momentum`, `rsi`,
  `stochastic` ή `volatility_regime`.
- Θέλεις primary setup πριν από meta-labeling; χρησιμοποίησε
  `indicator_model_adaptive_pullback`, `ema_stoch_rsi_pullback`,
  `roc_long_only_conditions`, `orb_candidate_side` ή κάποιο composite VWAP/Ehlers
  signal.
- Θέλεις να μετατρέψεις model outputs σε trades; χρησιμοποίησε
  `probability_threshold`, `meta_probability_side`, `forecast_threshold` ή τις
  volatility-adjusted εκδόσεις.
- Θέλεις sizing και όχι on/off trades; χρησιμοποίησε
  `probability_conviction`, `probability_vol_adjusted`,
  `dense_return_forecast` ή `forecast_vol_adjusted`.
## `meta_probability_side` OOS Gate Addendum

`meta_probability_side` accepts an optional `pred_is_oos_col` parameter. When
set, the signal remains flat unless that column is true. This is intended for
stacked meta-filter workflows where the probability column is produced by a
walk-forward classifier and must be out-of-sample before it can gate an existing
candidate side.

The signal never creates a new side. It reads `side_col`, optionally requires
`candidate_col`, optionally requires `pred_is_oos_col`, and emits:

```text
side_col when prob_col >= threshold and all gates pass
0 otherwise
```

Example:

```yaml
signals:
  kind: meta_probability_side
  params:
    prob_col: meta_pred_prob
    side_col: primary_candidate_side
    candidate_col: primary_candidate
    pred_is_oos_col: meta_pred_is_oos
    threshold: 0.65
    signal_col: signal_meta_filtered
    mode: long_short
```

Leakage policy: `pred_is_oos_col` should refer to the meta-model prediction
mask, not the primary model mask. Primary predictions must already be OOS before
candidate construction and meta-feature construction.

## `matb_candidate`

Μετατρέπει τα deterministic `matb_candidate`/`matb_side` σε `0`, `+1`, `-1`.
Υποστηρίζει `long_only`, `short_only`, `long_short` και δεν κρατά state. Το
default output name είναι `signal_side` μέσω `signal_col`.

## `matb_meta_filter`

Κρατά αποκλειστικά την ήδη καθορισμένη deterministic πλευρά όταν ισχύουν όλα:

```text
matb_candidate == 1
matb_pred_is_oos == 1
matb_pred_success_prob >= 0.55
matb_pred_ev_r >= 0.10
```

NaN prediction, non-candidate row ή in-sample/OOS-false row μένει flat. Το
signal δεν επιτρέπεται να δημιουργήσει κατεύθυνση. Στο αρχικό MATB audit το ML
sample gate απέτυχε, συνεπώς αυτό το signal παραμένει διαθέσιμο και tested αλλά
δεν ενεργοποιείται στο deterministic config.

<!-- BEGIN GENERATED EXHAUSTIVE REFERENCE -->

# Πλήρης registry-backed αναφορά

Η ενότητα αυτή παράγεται από τα ενεργά registries και τις υπογραφές του κώδικα. Έτσι κάθε διαθέσιμο component έχει αυτοτελή παράγραφο και copy-ready YAML. Τιμές όπως `<required>` πρέπει να αντικατασταθούν, ενώ `<configured>` δηλώνει runtime επιλογή που δεν έχει ασφαλές καθολικό default.

## Canonical signals

### `barrier_expected_value`

Convert calibrated barrier probabilities to a cost-aware causal position. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

The transform implements five explicit QMS alpha hypotheses. All adaptive thresholds are rolling quantiles shifted by one bar, so the current signal uses only information available before or at the current closed bar. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

signals: kind: qms_trend_momentum_vol params: combination: trend_momentum_vol mode: long_short. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

```yaml
signals:
  kind: qms_trend_momentum_vol
  params:
    combination: trend_momentum_vol
    mode: long_short
```

### `ehlers_continuation_long`

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal consumes already-built feature/helper columns and writes a deterministic long-only candidate/signal without training or target access. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

signals: kind: trend_state params: state_col: trend_regime. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

```yaml
signals:
  kind: trend_state
  params:
    state_col: <required>
    signal_col: null
    mode: long_short_hold
```

### `ema_rms_ppo_vwap`

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses current-bar and trailing feature columns only. It emits a long-only candidate for EURUSD 30m session Bollinger/RSI washout mean-reversion research. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

Map probability forecasts to {-1,0,1} signal with dead-zone. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

Linear map prob in [0, 1] to exposure in [-clip, clip]. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

```yaml
signals:
  kind: probability_conviction
  params:
    prob_col: <required>
    signal_col: null
    clip: 1.0
```

### `probability_vol_adjusted`

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal builds deterministic scalp candidates from point-in-time quote-flow, spread, volume, wick, support/resistance, and session features. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

Convert deterministic MATB candidate events to a stateless trade side. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

Accept MATB candidates only with genuine OOS probability and EV evidence. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

Emit the thresholded forecast signal plus OOS-only primary candidate columns. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

Apply a stateful hysteresis threshold to regression forecasts. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

Emit a fixed-time weekday reversal signal after a weak previous daily return. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

```yaml
signals:
  kind: regime_filtered
  params:
    base_signal_col: <required>
    regime_col: <required>
    signal_col: null
    active_value: 1.0
```

## Deprecated signal aliases

### `ehlers_continuation_long_signal`

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Κατάσταση: **deprecated alias**.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

This signal uses configured dataframe inputs and writes deterministic outputs without changing temporal ordering assumptions. Inputs must already be available at the timestamp where the transform is evaluated. Η έξοδος εκφράζει απόφαση ή έκθεση: θετική τιμή σημαίνει long, αρνητική short και μηδέν flat· candidate/score στήλες είναι διαγνωστικές και δεν αποτελούν από μόνες τους εκτελέσιμη θέση.

Κατάσταση: **deprecated alias**.

Πλήρες YAML παράδειγμα με το διαθέσιμο parameter contract:

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

<!-- END GENERATED EXHAUSTIVE REFERENCE -->
