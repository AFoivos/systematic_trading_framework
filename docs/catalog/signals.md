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
- Είναι diagnostic baseline πριν από model filtering.

Τι σημαίνουν οι τιμές:

- `candidate_col = 1` -> γράφει την πλευρά του `side_col`.
- `candidate_col = 0` -> flat.
- Δεν χρησιμοποιεί probabilities ή thresholds.

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
