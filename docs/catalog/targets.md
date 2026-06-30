# Κατάλογος Targets

Τελευταία ενημέρωση: 2026-06-29

Αυτό το αρχείο τεκμηριώνει τους target builders που είναι διαθέσιμοι μέσω του
`TARGET_REGISTRY` στο `src/targets/registry.py`. Το παλιό
`build_classifier_target` παραμένει facade συμβατότητας, αλλά τα νέα configs
πρέπει να δηλώνουν ρητό target `kind`.

Τα targets είναι labels για training, evaluation και diagnostics. Από τη φύση
τους κοιτάνε το μέλλον για να ορίσουν το outcome ενός timestamp. Αυτό είναι σωστό
μόνο στο target-construction στάδιο. Οι target output στήλες δεν πρέπει να
μπαίνουν ποτέ σε features, signals ή filters που υπολογίζονται πριν την
εκτέλεση.

## Γλωσσάρι target όρων

- Label: η διακριτή απάντηση που μαθαίνει ένας classifier, π.χ. `1` για
  επιτυχία και `0` για αποτυχία.
- Outcome: το πραγματικό αποτέλεσμα που μετρήθηκε στο μέλλον, πριν γίνει
  πιθανή δυαδικοποίηση.
- Forward return: απόδοση από το timestamp `t` μέχρι `t + horizon`.
- Horizon: πόσα bars μπροστά κοιτάει το target.
- Candidate: row όπου υπάρχει υποψήφιο trade/setup. Τα candidate-based targets
  γράφουν labels μόνο εκεί.
- Entry: τιμή εισόδου που χρησιμοποιείται στο label simulation. Μπορεί να είναι
  `current_close` ή `next_open`.
- Profit/stop/time barrier: επίπεδο κέρδους, stop ή χρονικό όριο που κλείνει
  το simulated trade path.
- R-multiple: αποτέλεσμα σε μονάδες αρχικού risk. `+2R` σημαίνει κέρδος δύο
  φορές το αρχικό ρίσκο, `-1R` σημαίνει πλήρες stop.

## Πώς διαβάζεις target values

Τα targets παράγουν συνήθως δύο είδη πληροφορίας:

- Label columns, όπως `label`: διακριτή απάντηση για classification ή
  meta-labeling.
- Numeric outcome columns, όπως `target_fwd_5`, `event_return`, `trade_r` ή
  `oriented_r`: μέγεθος απόδοσης, risk-normalized αποτέλεσμα ή diagnostic.

Γενική ερμηνεία:

- `label = 1`: θετικό outcome σύμφωνα με τον ορισμό του target.
- `label = 0`: αρνητικό outcome ή stop/failure, ανάλογα με το target.
- `label = -1`: αρνητική κατεύθυνση σε ternary directional labels.
- `NaN`: δεν υπάρχει αρκετό μέλλον, δεν υπήρχε candidate, ή το neutral outcome
  έγινε drop.
- Θετικό forward return: η τιμή στο horizon είναι υψηλότερη από το entry/base.
- Αρνητικό forward return: η τιμή στο horizon είναι χαμηλότερη.
- Θετικό `oriented_r`: το αποτέλεσμα ήταν καλό για την προτεινόμενη πλευρά του
  trade.
- Αρνητικό `oriented_r`: το αποτέλεσμα ήταν κακό για την προτεινόμενη πλευρά.

## Κατηγορίες

| Κατηγορία | Targets | Τι απαντούν |
| --- | --- | --- |
| Fixed-horizon returns | `forward_return`, `future_return_regression` | Τι απόδοση θα έχει η τιμή μετά από συγκεκριμένο αριθμό bars; |
| Barrier / trade-path labels | `triple_barrier`, `directional_triple_barrier`, `r_multiple` | Πρώτα χτύπησε profit, stop ή time barrier; Πόσο R κέρδισε ή έχασε το trade; |

## Fixed-horizon targets

Στα ελληνικά, αυτή η ομάδα είναι τα targets σταθερού ορίζοντα: κοιτούν ακριβώς
`horizon` bars μπροστά και αγνοούν την ενδιάμεση διαδρομή της τιμής. Είναι
καθαρά και εύκολα για baseline, αλλά δεν ξέρουν αν στην πορεία θα είχε
χτυπηθεί stop.

### `forward_return`

Τι μετρά:

- Την απόδοση από το timestamp `t` μέχρι `t + horizon`.
- Είναι το απλούστερο supervised target για direction ή positive return
  prediction.

Πώς υπολογίζεται:

- Αν δοθεί `returns_col`, συνθέτει τις μελλοντικές returns από `t+1` έως
  `t+horizon`.
- Με `returns_type = log`, αθροίζει τις log returns.
- Με `returns_type = simple`, πολλαπλασιάζει τις simple returns:
  `(1 + r_{t+1}) * ... * (1 + r_{t+h}) - 1`.
- Αν δεν δοθεί `returns_col`, υπολογίζει price return:
  `price_{t+horizon} / price_t - 1`.
- Το binary label είναι `1` όταν `forward_return > threshold`, αλλιώς `0`.

Τι σημαίνουν οι τιμές:

- `target_fwd_5 = 0.012` σημαίνει ότι η τιμή μετά από 5 bars είναι περίπου
  `+1.2%` πάνω από την τιμή αναφοράς.
- `target_fwd_5 = -0.006` σημαίνει `-0.6%`.
- `label = 1` σημαίνει ότι η forward return ξεπέρασε το threshold.
- `label = 0` σημαίνει ότι δεν το ξεπέρασε.
- Τα tail rows γίνονται `NaN` γιατί δεν υπάρχει πλήρες future horizon.

Παράδειγμα:

- `close_t = 100`, `horizon = 3`, `close_{t+3} = 102`.
- Το forward return είναι `102 / 100 - 1 = 0.02`.
- Αν `threshold = 0`, τότε `label = 1`.
- Αν `threshold = 0.03`, τότε `label = 0`, γιατί η απόδοση ήταν θετική αλλά όχι
  αρκετά μεγάλη.

Χρησιμότητα:

- Καθαρό baseline πριν από path-dependent targets.
- Συνδέει άμεσα model horizon και trading horizon.
- Καλό για classifiers που προβλέπουν "positive return" και regressors που
  προβλέπουν μέγεθος μελλοντικής απόδοσης.

Αιτιότητα:

- Το target κοιτάει μέλλον by design. Δεν πρέπει να γίνει feature.
- Τα rows χωρίς πλήρη horizon μένουν unlabeled.

### `future_return_regression`

Τι μετρά:

- Continuous future return για regression models.
- Είναι fixed-horizon target, αλλά με περισσότερες επιλογές για raw output,
  normalized output και clipping.

Πώς υπολογίζεται:

- Δέχεται `horizon` ή `horizon_bars`.
- Αν δοθεί `returns_col`, συνθέτει future return από returns.
- Αν δοθεί `price_col`, χρησιμοποιεί future price change.
- Γράφει raw future return σε `raw_fwd_col`.
- Γράφει το τελικό regression label σε `fwd_col` ή `label_col`.
- Με `normalize_by_volatility = true`, διαιρεί το raw return με local volatility
  scale, συνήθως `volatility_col / abs(price_col)`.
- Με `clip`, περιορίζει ακραίες τιμές.

Τι σημαίνουν οι τιμές:

- `label = 0.004` σημαίνει αναμενόμενη ή πραγματική future return `+0.4%` στην
  κλίμακα του target.
- `label = -0.007` σημαίνει `-0.7%`.
- Αν το target είναι volatility-normalized, `label = 2.0` σημαίνει ότι η
  forward move ήταν περίπου δύο μονάδες τοπικής μεταβλητότητας, όχι 200%.
- `label = 0` σημαίνει ουδέτερη future return, όχι απαραίτητα "κακό trade".

Παράδειγμα:

- `close_t = 100`, `close_{t+4} = 101`, άρα raw future return `0.01`.
- Αν το volatility scale είναι `0.005`, τότε normalized target `0.01 / 0.005 =
  2.0`.
- Ένα regressor που προβλέπει `pred_ret = 1.5` στην ίδια normalized κλίμακα λέει
  "περιμένω κίνηση περίπου 1.5 volatility units προς τα πάνω".

Χρησιμότητα:

- Κατάλληλο για `lightgbm_regressor`, neural forecasters ή dense forecast
  workflows.
- Κρατά περισσότερη πληροφορία από binary labels, γιατί διατηρεί το μέγεθος της
  κίνησης.
- Το volatility normalization κάνει τις αποδόσεις πιο συγκρίσιμες μεταξύ
  ήρεμων και έντονων regimes.

Αιτιότητα:

- Όπως όλα τα targets, χρησιμοποιεί future prices/returns μόνο για labels.
- Τα target columns και normalizer diagnostics δεν πρέπει να χρησιμοποιούνται ως
  model features.

## Barrier και trade-path targets

Αυτή η ομάδα είναι path-dependent: δεν αρκεί η τελική τιμή στο horizon. Μετράει
ποιο επίπεδο χτυπήθηκε πρώτο μέσα στη διαδρομή, άρα ταιριάζει καλύτερα σε
πραγματική λογική trade management.

### `triple_barrier`

Τι μετρά:

- Αν μετά από ένα timestamp χτυπήθηκε πρώτα upper barrier, lower barrier ή
  vertical time barrier.
- Είναι path-dependent label, πιο κοντά σε πραγματικό trade management από
  fixed-horizon return.

Πώς υπολογίζεται:

- Ορίζει entry price στο `current_close` ή στο `next_open`.
- Ορίζει upper barrier πάνω από το entry και lower barrier κάτω από το entry.
- Το barrier distance βασίζεται σε volatility:
  `upper_mult * volatility` και `lower_mult * volatility`.
- Αν δεν δοθεί `volatility_col`, μπορεί να υπολογίσει rolling volatility από
  `returns_col` ή από `price_col.pct_change()`.
- Κάνει scan στο future OHLC path μέχρι `max_holding` bars.
- Αν upper και lower χτυπηθούν στο ίδιο bar, το `tie_break` αποφασίζει με
  `closest_to_open`, `upper` ή `lower`.

Τι σημαίνουν οι τιμές:

- Σε `binary` mode:
  - upper hit -> `label = 1`,
  - lower hit -> `label = 0`,
  - neutral -> ανάλογα με `neutral_label`.
- Σε `ternary` mode:
  - upper hit -> `1`,
  - lower hit -> `-1`,
  - neutral -> `0`.
- Σε `meta` mode με `side_col`, το label σημαίνει "πέτυχε η προτεινόμενη
  πλευρά;".
- `hit_type` δείχνει `upper`, `lower` ή `neutral`.
- `hit_step` δείχνει σε πόσα bars έγινε το hit.
- Με `add_r_multiple = true`, τα `event_r` και `oriented_r` δείχνουν αποτέλεσμα
  σε μονάδες αρχικού risk.

Παράδειγμα directional binary:

- Entry `100`, volatility distance `2`, `upper_mult = 1.5`, `lower_mult = 1.0`.
- Upper barrier `103`, lower barrier `98`.
- Αν μέσα στα επόμενα bars η αγορά πάει πρώτα `103`, `label = 1`.
- Αν πάει πρώτα `98`, `label = 0`.
- Αν δεν χτυπήσει τίποτα μέχρι `max_holding`, το label χειρίζεται με
  `neutral_label`.

Παράδειγμα meta-labeling:

- Primary signal προτείνει short (`side_col = -1`).
- Για short, profit είναι η κάτω barrier και stop η πάνω barrier.
- Αν χτυπηθεί πρώτα η κάτω barrier, το meta label είναι success, δηλαδή
  `label = 1`.
- Αν χτυπηθεί πρώτα η πάνω barrier, το meta label είναι failure, δηλαδή
  `label = 0`.

Χρησιμότητα:

- Ενσωματώνει profit-taking, stop-loss και time stop.
- Κατάλληλο για meta-labeling πάνω σε primary candidates.
- Παράγει diagnostics για barrier levels, event return, hit type και hit timing.

Αιτιότητα:

- Το future OHLC path χρησιμοποιείται μόνο για label construction.
- Τα barrier, hit και event return columns είναι target diagnostics και δεν
  πρέπει να μπουν σε features.

### `directional_triple_barrier`

Τι μετρά:

- Την επιτυχία ή αποτυχία μιας ήδη προτεινόμενης κατεύθυνσης, με profit/stop
  barriers προσανατολισμένα στην πλευρά του trade.
- Είναι πιο explicit meta-label target από ένα γενικό triple barrier.

Πώς υπολογίζεται:

- Απαιτεί `direction_col` ή `side_col`.
- Προαιρετικά χρησιμοποιεί `candidate_col`, ώστε να γράφει labels μόνο σε
  candidate rows.
- Υποστηρίζει entry στο `current_close` ή στο `next_open`.
- Χρησιμοποιεί `profit_barrier_r` και `stop_barrier_r`, ή defaults από
  `upper_mult` και `lower_mult`.
- Για long:
  - profit barrier πάνω από entry,
  - stop barrier κάτω από entry.
- Για short:
  - profit barrier κάτω από entry,
  - stop barrier πάνω από entry.
- Το neutral handling μπορεί να είναι `drop`, `profit` ή `stop`.

Τι σημαίνουν οι τιμές:

- `label = 1`: το προτεινόμενο trade πέτυχε profit barrier πρώτο.
- `label = 0`: το προτεινόμενο trade χτύπησε stop πρώτο ή απέτυχε σύμφωνα με
  neutral handling.
- `oriented_ret > 0`: η κίνηση ήταν υπέρ της προτεινόμενης πλευράς.
- `oriented_ret < 0`: η κίνηση ήταν εναντίον της προτεινόμενης πλευράς.
- `oriented_r = 1.4` σημαίνει κέρδος 1.4R για την πλευρά του trade.
- `oriented_r = -1.0` σημαίνει stop μιας μονάδας R.

Παράδειγμα long:

- Candidate long στο `100`, volatility/risk unit `2`.
- `profit_barrier_r = 1.4`, `stop_barrier_r = 1.0`.
- Profit price `102.8`, stop price `98.0`.
- Αν το high φτάσει `102.8` πριν το low φτάσει `98.0`, `label = 1` και
  `hit_type = profit`.
- Αν το stop χτυπηθεί πρώτο, `label = 0` και `hit_type = stop`.

Παράδειγμα short:

- Candidate short στο `100` με ίδιο risk unit `2`.
- Profit price `97.2`, stop price `102.0`.
- Αν η αγορά πέσει πρώτα στο `97.2`, το short πέτυχε και `label = 1`.
- Αν ανέβει πρώτα στο `102.0`, το short απέτυχε και `label = 0`.

Χρησιμότητα:

- Ταιριάζει σε workflows τύπου primary signal -> meta model -> execution
  filter.
- Διαχωρίζει καθαρά την ερώτηση "ποια πλευρά προτάθηκε;" από την ερώτηση
  "ήταν καλή αυτή η πρόταση;".
- Τα `oriented_*` columns κάνουν συγκρίσιμα long και short trades στην ίδια
  κλίμακα.

Αιτιότητα:

- Το `side_col`/`direction_col` και το `candidate_col` πρέπει να είναι causal
  outputs πριν από το target.
- Τα future OHLC bars χρησιμοποιούνται μόνο για label construction.

### `r_multiple`

Τι μετρά:

- Το αποτέλεσμα manual long candidates σε R-multiple units.
- Σήμερα υποστηρίζει long-only candidates.

Πώς υπολογίζεται:

- Απαιτεί `candidate_col` και OHLC columns.
- Με `stop_mode = volatility_stop`, το risk distance είναι
  `volatility_value * stop_loss_r`.
- Με `stop_mode = fixed_return`, το risk distance είναι `stop_loss_return`.
- Το take-profit distance ορίζεται από `take_profit_r` ή `take_profit_return`.
- Προσομοιώνει το long path μέχρι take profit, stop loss ή
  `max_holding_bars`.
- Υπολογίζει `trade_return` και `trade_r = trade_return / risk_distance`.
- Το label είναι `1` όταν `trade_r >= target_r_min`, αλλιώς `0`.

Τι σημαίνουν οι τιμές:

- `trade_r = 2.0`: το trade κέρδισε δύο φορές το αρχικό risk.
- `trade_r = -1.0`: το trade έχασε μία μονάδα risk.
- `trade_r = 0.4`: το trade κέρδισε, αλλά ίσως όχι αρκετά για να θεωρηθεί
  επιτυχημένο αν `target_r_min = 1.0`.
- `label = 1`: το trade πέτυχε τον ελάχιστο R στόχο.
- `label = 0`: δεν τον πέτυχε.
- `r_target_exit_reason`, `r_target_hit_type` και `r_target_bars_held` εξηγούν
  πώς έκλεισε.

Παράδειγμα:

- Candidate long στο `100`, stop στο `98`, άρα risk distance `2`.
- Take profit στα `104`, δηλαδή `+2R`.
- Αν το trade βγει στο `104`, `trade_r = 2.0`.
- Αν `target_r_min = 1.0`, τότε `label = 1`.
- Αν κλείσει στο `101`, `trade_r = 0.5`, άρα με `target_r_min = 1.0` το label
  είναι `0` παρότι το raw return ήταν θετικό.

Χρησιμότητα:

- Πολύ πρακτικό για manual long strategy EDA.
- Κανονικοποιεί κάθε outcome με βάση το αρχικό risk.
- Επιτρέπει να συγκρίνεις trades με διαφορετικό volatility ή stop distance.
- Καλό target για model filters πάνω σε manual candidates.

Αιτιότητα:

- Το candidate πρέπει να έχει παραχθεί causally πριν από το target.
- Με `entry_price_mode = next_open`, το target ταιριάζει σε σήμα που
  υπολογίζεται στο close και εκτελείται στο επόμενο open.
- Τα R-multiple outputs είναι labels/diagnostics, όχι features.

## Παράδειγμα YAML

```yaml
target:
  kind: directional_triple_barrier
  params:
    direction_col: signal_side
    candidate_col: signal_candidate
    entry_price_mode: next_open
    volatility_col: atr_14
    profit_barrier_r: 1.4
    stop_barrier_r: 1.0
    max_holding: 12
    label_col: label
```

Ερμηνεία:

- Το primary signal γράφει πλευρά στο `signal_side`.
- Το target κοιτάει μόνο rows με `signal_candidate = 1`.
- Για κάθε candidate, ελέγχει αν profit ή stop χτυπήθηκε πρώτο μέσα σε 12 bars.
- `label = 1` σημαίνει ότι η προτεινόμενη πλευρά πέτυχε.
- `label = 0` σημαίνει ότι η προτεινόμενη πλευρά απέτυχε.

## Πρακτικός κανόνας επιλογής

- Θέλεις απλό directional classifier; ξεκίνα με `forward_return`.
- Θέλεις regression forecast; χρησιμοποίησε `future_return_regression`.
- Θέλεις target που σέβεται stop, profit και time stop; χρησιμοποίησε
  `triple_barrier`.
- Θέλεις meta-labeling πάνω σε ήδη προτεινόμενη πλευρά; προτίμησε
  `directional_triple_barrier`.
- Θέλεις να αξιολογήσεις manual long candidates σε risk units; χρησιμοποίησε
  `r_multiple`.
