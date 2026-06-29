# Target Catalog

Τελευταία ενημέρωση: 2026-06-27

Αυτό το αρχείο τεκμηριώνει τα target builders που είναι διαθέσιμα μέσω του
`TARGET_REGISTRY` στο `src/targets/registry.py`. Το παλιό
`build_classifier_target` παραμένει compatibility facade, αλλά νέα configs
πρέπει να δηλώνουν target `kind`.

Targets είναι labels για training/evaluation. Από τη φύση τους κοιτάνε το
μέλλον για να ορίσουν το outcome ενός timestamp. Αυτό είναι σωστό μόνο στο
target-construction στάδιο. Οι target output στήλες δεν πρέπει να μπαίνουν ποτέ
σε model features, signals ή filters που υπολογίζονται πριν την εκτέλεση.

## Γενικές αρχές

- Το target στο timestamp `t` περιγράφει outcome μετά το `t`, όχι πληροφορία
  διαθέσιμη στο `t`.
- Τα τελευταία rows συνήθως μένουν `NaN`, γιατί δεν υπάρχει πλήρης forward
  horizon.
- Τα target outputs είναι χρήσιμα για EDA, diagnostics, training labels και
  stratification, αλλά είναι leakage αν χρησιμοποιηθούν ως input features.
- Η επιλογή `entry_price_mode='next_open'` είναι πιο κοντά σε εκτελέσιμη
  στρατηγική όταν το σήμα παράγεται στο close του current bar.

## forward_return

Fixed-horizon forward return target.

- Υπολογίζει την απόδοση από το current timestamp μέχρι `horizon` bars μπροστά.
- Output forward return: default `target_fwd_{horizon}` ή `fwd_col`.
- Output label: default `label` ή `label_col`.
- Όταν δίνεται `returns_col`, συνθέτει τις μελλοντικές returns από `t+1` έως
  `t+horizon`.
- Όταν `returns_type='log'`, αθροίζει τις μελλοντικές log returns.
- Όταν `returns_type='simple'`, πολλαπλασιάζει τις simple returns:
  `(1+r_{t+1}) * ... * (1+r_{t+h}) - 1`.
- Όταν δεν δίνεται `returns_col`, υπολογίζει απλό price return:
  `price_{t+horizon} / price_t - 1`.
- Το binary label είναι `1` όταν `forward_return > threshold`, αλλιώς `0`.
- Αν δοθεί `quantiles`, ο builder σήμερα κάνει validation των quantiles και
  κρατά metadata, αλλά δεν εκπέμπει quantile labels σε αυτή τη διαδρομή.

Χρησιμότητα:

- Είναι το πιο απλό supervised learning objective για direction ή positive
  return prediction.
- Είναι καλό baseline πριν πας σε πιο path-dependent labels.
- Δίνει καθαρή σύνδεση ανάμεσα στο horizon του μοντέλου και στο trading horizon.

Θεωρία:

- Το fixed-horizon target απαντά στην ερώτηση: "η τιμή θα είναι υψηλότερα μετά
  από `h` bars;".
- Είναι απλό και σταθερό στατιστικά, αλλά αγνοεί τη διαδρομή ενδιάμεσα. Ένα
  trade μπορεί να είχε χτυπήσει stop πριν τελικά κλείσει θετικά στο horizon.
- Για log returns, το άθροισμα είναι φυσικό γιατί οι log returns είναι
  additive στον χρόνο.

Causality:

- Το target κοιτάει μέλλον by design. Δεν πρέπει να γίνει feature.
- Τα rows χωρίς πλήρη horizon μένουν unlabeled.

## triple_barrier

Path-dependent target με upper barrier, lower barrier και vertical barrier.

- Ορίζει entry price στο `current_close` ή στο `next_open`.
- Ορίζει upper barrier πάνω από το entry και lower barrier κάτω από το entry.
- Το barrier distance βασίζεται σε volatility:
  `upper_mult * volatility` και `lower_mult * volatility`.
- Αν δεν δοθεί `volatility_col`, υπολογίζει rolling volatility από
  `returns_col` ή από `price_col.pct_change()`.
- Κάνει scan στο future OHLC path μέχρι `max_holding` bars.
- Αν χτυπηθεί πρώτα το upper barrier, το raw barrier label είναι `1`.
- Αν χτυπηθεί πρώτα το lower barrier, το raw barrier label είναι `0`.
- Αν δεν χτυπηθεί κανένα barrier μέχρι το vertical barrier, το event είναι
  neutral και χειρίζεται με `neutral_label`: `drop`, `lower` ή `upper`.
- Αν upper και lower χτυπηθούν στο ίδιο bar, το `tie_break` αποφασίζει με
  `closest_to_open`, `upper` ή `lower`.

Label modes:

- `binary`: upper hit `1`, lower hit `0`, neutral ανά `neutral_label`.
- `ternary`: upper hit `1`, lower hit `-1`, neutral `0`.
- `meta`: απαιτεί `side_col`. Το label γίνεται "πέτυχε η ήδη προτεινόμενη
  πλευρά;" αντί για "πήγε πάνω ή κάτω η αγορά;".

Meta-labeling behavior:

- Με `side_col > 0`, upper barrier σημαίνει profit και lower barrier stop.
- Με `side_col < 0`, lower barrier σημαίνει profit και upper barrier stop.
- Με `candidate_col`, labels γράφονται μόνο για candidate rows.
- Με `candidate_mode='side_change'`, candidate είναι η αλλαγή πλευράς.
- Εκπέμπονται auxiliary columns όπως candidate flag, meta side και oriented
  return.

Optional R-multiple outputs:

- Με `add_r_multiple=true`, γράφει `r_col` και `oriented_r_col`.
- `event_r = event_return / risk_distance`.
- `oriented_r` προσανατολίζει το αποτέλεσμα στην πλευρά του trade.
- `r_clip` μπορεί να περιορίσει extreme R values για πιο robust diagnostics.

Χρησιμότητα:

- Είναι πιο κοντά σε πραγματικό trade management από ένα fixed-horizon target.
- Ενσωματώνει profit-taking, stop-loss και time stop.
- Είναι κατάλληλο για meta-labeling, δηλαδή για να μάθεις πότε ένα primary
  signal αξίζει να εκτελεστεί.
- Δίνει diagnostics για hit type, hit step, barriers και event return.

Θεωρία:

- Βασίζεται στη triple-barrier λογική του López de Prado.
- Αντί να διαλέγεις αυθαίρετα μόνο ένα horizon, αφήνεις την ίδια τη διαδρομή
  της αγοράς να ορίσει αν πρώτα επιτεύχθηκε κέρδος, ζημιά ή time-out.
- Το volatility-scaled barrier κάνει το label πιο συγκρίσιμο μεταξύ ήρεμων και
  έντονων regimes.
- Το meta-labeling χωρίζει το πρόβλημα σε δύο επίπεδα: ένα primary model/rule
  προτείνει πλευρά και ένα secondary model αποφασίζει αν η πρόταση έχει
  επαρκή πιθανότητα επιτυχίας.

Causality:

- Το future path χρησιμοποιείται μόνο για label construction.
- Τα barrier, hit και event return columns είναι target diagnostics και δεν
  πρέπει να μπαίνουν σε features.
- Τα tail rows χωρίς πλήρες `max_holding` μένουν unlabeled.

## r_multiple

Long-only R-multiple target για ήδη παραγμένα manual candidates.

- Απαιτεί `candidate_col`, OHLC columns και, για `stop_mode='volatility_stop'`,
  `volatility_col`.
- Υποστηρίζει μόνο `side='long_only'`.
- Entry price: `next_open` ή `current_close`.
- Με `stop_mode='volatility_stop'`, το risk distance είναι:
  `volatility_value * stop_loss_r`.
- Με `stop_mode='fixed_return'`, το risk distance είναι `stop_loss_return`.
- Take profit distance:
  `risk_distance * take_profit_r / stop_loss_r` ή `take_profit_return`.
- Προσομοιώνει το long path μέχρι take profit, stop loss ή
  `max_holding_bars`.
- Υπολογίζει trade return και `trade_r = trade_return / risk_distance`.
- Το label είναι `1` όταν `trade_r >= target_r_min`, αλλιώς `0`.

Outputs:

- `label`
- `r_target_event_ret`
- `r_target_trade_r`
- `r_target_oriented_r`
- `r_target_candidate`
- `r_target_entry_price`
- `r_target_exit_price`
- `r_target_stop_price`
- `r_target_take_profit_price`
- `r_target_exit_reason`
- `r_target_bars_held`
- `r_target_hit_type`
- `r_target_hit_step`

Χρησιμότητα:

- Είναι πολύ πρακτικό για manual long strategy EDA.
- Κανονικοποιεί το αποτέλεσμα με βάση το αρχικό ρίσκο, άρα μπορείς να
  συγκρίνεις trades με διαφορετικό volatility ή stop distance.
- Τα diagnostics βοηθούν να δεις αν οι winners και losers έχουν διαφορετικά
  feature profiles.
- Είναι καλό target για model filter πάνω σε manual candidates.

Θεωρία:

- Το R-multiple μετρά απόδοση σε μονάδες αρχικού ρίσκου.
- Trade με `+2R` κέρδισε δύο φορές το ποσό που ρίσκαρε. Trade με `-1R`
  έχασε μία μονάδα ρίσκου.
- Αυτό συνδέει το label με trade management και όχι μόνο με raw return.
- Η threshold λογική `target_r_min` επιτρέπει να ορίσεις τι θεωρείται
  επιτυχημένο trade σύμφωνα με το payoff profile της στρατηγικής.

Causality:

- Το candidate πρέπει να έχει παραχθεί causally πριν από το target.
- Το future OHLC path χρησιμοποιείται μόνο για label construction.
- Με `entry_price_mode='next_open'`, το target ταιριάζει σε σήμα που
  υπολογίζεται στο close και εκτελείται στο επόμενο open.
- Τα R-multiple outputs είναι labels/diagnostics, όχι features.

## candidate_expected_r

Candidate-based expected-R target για manual/rule-based candidate signals.

Σε αντίθεση με generic forward return targets, γράφει labels μόνο όταν
`candidate_col == 1` και απαντά στο trade-level ερώτημα: αν το candidate
δόθηκε στο close του bar `t` και η είσοδος έγινε στο επόμενο open, πόσα R
παρήγαγε η διαδρομή με συγκεκριμένο volatility stop, take profit και maximum
holding;

Διαφορά από triple barrier:

- Είναι long-only και candidate-only by design.
- Το αποτέλεσμα αποθηκεύεται άμεσα ως realized trade R και clipped trade R.
- Το target είναι προσανατολισμένο στο quality μιας ήδη προτεινόμενης
  συναλλαγής, όχι στη γενική κατεύθυνση όλων των bars.

Outputs:

- `label`, binary success label με βάση `target_r_min`.
- `target_trade_r` και `target_trade_r_clipped`.
- `target_event_ret`, `target_candidate`, `target_entry_price`,
  `target_exit_price`, `target_stop_price`, `target_take_profit_price`.
- `target_exit_reason`, `target_bars_held`, `target_hit_type`,
  `target_hit_step`.
- MFE/MAE diagnostics: `target_mfe_r`, `target_mae_r`,
  `target_time_to_mfe`, `target_time_to_mae`.

Causality:

- Το future OHLC path χρησιμοποιείται μόνο στο target-construction στάδιο.
- Με `entry_price_mode='next_open'`, το label ταιριάζει σε signal που
  παράγεται στο close του current bar και εκτελείται στο επόμενο open.
- Non-candidate rows μένουν unlabeled, με `target_candidate=0`.
- Τα target output columns δεν πρέπει ποτέ να μπουν σε `model.feature_cols`,
  `feature_selectors`, signal filters ή execution rules. Είναι labels και
  diagnostics, άρα θα ήταν leakage αν χρησιμοποιηθούν ως inputs.

Χρησιμότητα:

- Κατάλληλο για το workflow: rule-based primary candidate -> expected-R target
  -> future meta-labeling/model filter.
- Επιτρέπει να μελετήσεις winners/losers σε trade units αντί για raw returns.
- Τα MFE/MAE και exit-reason diagnostics βοηθούν να αξιολογηθεί αν το candidate
  αποτυγχάνει λόγω stop placement, timing ή insufficient follow-through.
