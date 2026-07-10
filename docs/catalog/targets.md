# Κατάλογος Targets

Τελευταία ενημέρωση: 2026-07-08

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

## Regression targets για ML trading models

Τα παρακάτω targets είναι continuous regression labels. Κοιτούν future candles
μόνο στο target-construction στάδιο και γράφουν όλες τις τελικές και
intermediate στήλες στο `meta.output_cols`, ώστε το model feature resolver να
τις αποκλείει από features. Ο κοινός μηχανισμός υποστηρίζει `clip: [low, high]`
και metadata με `kind`, `price_col`, `horizon`, `horizon_bars`, `fwd_col`,
`label_col`, `labeled_rows`, `target_density`, `target_stats` και τα
intermediate columns. Το `target_stats` περιέχει rows, mean, std, min, max,
median, q01, q05, q25, q75, q95, q99, skew και kurtosis.

### `volatility_normalized_future_return`

- Τι κάνει: προβλέπει fixed-horizon return σε μονάδες τοπικής volatility.
- Formula: `raw = close[t+h] / close[t] - 1`, `normalizer = volatility_col[t] / abs(price_col[t])`, `target = raw / normalizer`.
- Required input columns: `price_col`, `volatility_col`, ή προαιρετικά `returns_col`.
- Params: `price_col`, `volatility_col`, `horizon_bars`, `returns_col`, `returns_type`, `volatility_floor`, `raw_fwd_col`, `normalizer_col`, `fwd_col`, `label_col`, `clip`.
- Output columns: `raw_fwd_col`, `normalizer_col`, `fwd_col`, και `label_col` αν διαφέρει.
- Leakage: το future return είναι label-only. Το normalizer χρησιμοποιεί μόνο volatility και price στο timestamp `t`.
- Πότε έχει νόημα: multi-asset ή multi-regime regressors όπου raw returns δεν είναι συγκρίσιμα.
- Τι σημαίνει η πρόβλεψη: `pred_ret = 1.5` σημαίνει αναμενόμενη κίνηση 1.5 volatility units, όχι 150%.

```yaml
target:
  kind: volatility_normalized_future_return
  params:
    price_col: close
    volatility_col: atr_14
    horizon_bars: 5
    clip: [-5, 5]
    fwd_col: target_vol_norm_return_5
```

### `risk_adjusted_future_return`

- Τι κάνει: διαιρεί το future return με τη realized volatility του ίδιου future horizon.
- Formula: `target = future_return / std(returns[t+1:t+h])`.
- Required input columns: `price_col` ή `returns_col`.
- Params: `price_col`, `returns_col`, `returns_type`, `horizon_bars`, `volatility_floor`, `raw_fwd_col`, `realized_vol_col`, `fwd_col`, `label_col`, `clip`.
- Output columns: `raw_fwd_col`, `realized_vol_col`, `fwd_col`, και optional `label_col`.
- Leakage: η future realized volatility είναι μέρος του label, όχι feature.
- Πότε έχει νόημα: όταν θέλεις return scaled από τη μελλοντική διαδρομή risk που πράγματι ακολούθησε.
- Τι σημαίνει η πρόβλεψη: θετικό value σημαίνει return που αποζημίωσε το realized future volatility.

```yaml
target:
  kind: risk_adjusted_future_return
  params:
    price_col: close
    horizon_bars: 5
    fwd_col: target_risk_adjusted_return_5
```

### `r_multiple_regression`

- Τι κάνει: μετατρέπει fixed-horizon return σε R units με ATR-based stop distance.
- Formula: `risk_distance = atr_multiple * volatility_col[t] / abs(price_col[t])`, `target = future_return / risk_distance`.
- Required input columns: `price_col`, `volatility_col`, ή optional `returns_col`.
- Params: `price_col`, `volatility_col`, `atr_multiple`, `horizon_bars`, `returns_col`, `returns_type`, `volatility_floor`, `raw_fwd_col`, `risk_distance_col`, `fwd_col`, `label_col`, `clip`.
- Output columns: `raw_fwd_col`, `risk_distance_col`, `fwd_col`, optional `label_col`.
- Leakage: το risk distance είναι causal γιατί βασίζεται στο volatility στο `t`; μόνο το return κοιτάει `t+h`.
- Πότε έχει νόημα: κύριο regression target για trading signals με stop/risk thinking.
- Τι σημαίνει η πρόβλεψη: `pred_ret = 1.2` σημαίνει expected +1.2R στο horizon.

```yaml
target:
  kind: r_multiple_regression
  params:
    price_col: close
    volatility_col: atr_14
    atr_multiple: 2.0
    horizon_bars: 5
    clip: [-5, 5]
    fwd_col: target_r_multiple_5
```

### `mfe_regression`

- Τι κάνει: μετρά maximum favorable excursion στο future path.
- Formula long: `max(high[t+1:t+h]) / close[t] - 1`. Formula short: `close[t] / min(low[t+1:t+h]) - 1`.
- Required input columns: `price_col`, `high_col`, `low_col`, και `volatility_col` αν γίνει volatility normalization.
- Params: `direction` (`long`, `short`, `signed`), `horizon_bars`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`, `fwd_col`, `label_col`, `clip`.
- Output columns: `fwd_col`, optional `label_col`.
- Signed convention: θετικό σημαίνει ότι κυριάρχησε upside favorable excursion, αρνητικό ότι κυριάρχησε downside favorable excursion.
- Leakage: το high/low future path χρησιμοποιείται μόνο για label diagnostics.
- Πότε έχει νόημα: upside potential modeling και ranking setups πριν από exit-policy design.
- Τι σημαίνει η πρόβλεψη: μεγαλύτερο θετικό value σημαίνει μεγαλύτερο διαθέσιμο favorable move.

```yaml
target:
  kind: mfe_regression
  params:
    price_col: close
    high_col: high
    low_col: low
    direction: long
    horizon_bars: 5
    fwd_col: target_mfe_5
```

### `mae_regression`

- Τι κάνει: μετρά maximum adverse excursion στο future path.
- Formula long: `min(low[t+1:t+h]) / close[t] - 1`. Formula short: `close[t] / max(high[t+1:t+h]) - 1`.
- Required input columns: `price_col`, `high_col`, `low_col`, και `volatility_col` αν γίνει normalization.
- Params: `direction` (`long`, `short`, `signed`), `horizon_bars`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`, `fwd_col`, `label_col`, `clip`.
- Output columns: `fwd_col`, optional `label_col`.
- Signed convention: αρνητικό σημαίνει downside adverse excursion, θετικό σημαίνει upside adverse excursion.
- Leakage: future lows/highs μένουν target-only.
- Πότε έχει νόημα: downside risk model, stop sizing και conservative filters.
- Τι σημαίνει η πρόβλεψη: πιο αρνητικό value για long σημαίνει μεγαλύτερο adverse path risk.

```yaml
target:
  kind: mae_regression
  params:
    price_col: close
    high_col: high
    low_col: low
    direction: long
    horizon_bars: 5
    fwd_col: target_mae_5
```

### `mfe_mae_ratio_regression`

- Τι κάνει: μετρά path reward/risk quality από MFE και MAE.
- Formula ratio: `target = MFE / abs(MAE)`. Formula difference: `target = MFE - abs(MAE)`.
- Required input columns: `price_col`, `high_col`, `low_col`.
- Params: `direction` (`long` ή `short`), `mode` (`ratio` ή `difference`), `denominator_floor`, `mfe_col`, `mae_col`, `fwd_col`, `label_col`, `clip`.
- Output columns: `mfe_col`, `mae_col`, `fwd_col`, optional `label_col`.
- Leakage: MFE/MAE είναι label path diagnostics και αποκλείονται μέσω `output_cols`.
- Πότε έχει νόημα: επιλογή setups που είχαν καθαρότερο upside/downside profile.
- Τι σημαίνει η πρόβλεψη: σε ratio mode, `2.0` σημαίνει MFE περίπου διπλάσιο από το adverse excursion.

```yaml
target:
  kind: mfe_mae_ratio_regression
  params:
    price_col: close
    high_col: high
    low_col: low
    direction: long
    mode: ratio
    horizon_bars: 5
    fwd_col: target_mfe_mae_ratio_5
```

### `downside_adjusted_future_return`

- Τι κάνει: τιμωρεί future returns που είχαν μεγάλο adverse excursion.
- Formula long: `future_return - penalty_lambda * abs(MAE)`. Για short χρησιμοποιεί short-oriented future return, ώστε θετικό target να σημαίνει καλή short ευκαιρία.
- Required input columns: `price_col`, `high_col`, `low_col`, και `volatility_col` αν γίνει normalization.
- Params: `direction`, `horizon_bars`, `penalty_lambda`, `normalize_by_volatility`, `raw_fwd_col`, `mae_col`, `fwd_col`, `label_col`, `clip`.
- Output columns: `raw_fwd_col`, `mae_col`, `fwd_col`, optional `label_col`.
- Leakage: το adverse path είναι label penalty, όχι feature.
- Πότε έχει νόημα: conservative regression signal που προτιμά smooth winners.
- Τι σημαίνει η πρόβλεψη: θετικό value σημαίνει expected return αφού αφαιρεθεί path-risk penalty.

```yaml
target:
  kind: downside_adjusted_future_return
  params:
    price_col: close
    high_col: high
    low_col: low
    direction: long
    horizon_bars: 5
    penalty_lambda: 1.0
    clip: [-5, 5]
    fwd_col: target_downside_adjusted_return_5
```

### `future_trend_slope`

- Τι κάνει: μετρά linear-regression slope στο future price window, όχι μόνο terminal return.
- Formula: slope πάνω στα `close[t+1:t+h]`, προαιρετικά normalized by price ή volatility.
- Required input columns: `price_col`, και `volatility_col` αν `normalize_by_volatility=true`.
- Params: `horizon_bars` (>=2), `normalize_by_price`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`, `fwd_col`, `label_col`, `clip`.
- Output columns: `fwd_col`, optional `label_col`.
- Leakage: η slope είναι future-path label και δεν μπαίνει σε feature set.
- Πότε έχει νόημα: trend quality/continuation targets όπου το terminal close είναι θορυβώδες.
- Τι σημαίνει η πρόβλεψη: θετικό value σημαίνει ανοδική future slope στην target scale.

```yaml
target:
  kind: future_trend_slope
  params:
    price_col: close
    horizon_bars: 5
    normalize_by_price: true
    fwd_col: target_future_trend_slope_5
```

### `future_path_efficiency`

- Τι κάνει: μετρά πόσο καθαρή ήταν η future κίνηση.
- Formula: `abs(close[t+h]-close[t]) / sum(abs(close[i]-close[i-1]))`. Με `signed=true` πολλαπλασιάζεται με το sign του net move.
- Required input columns: `price_col`.
- Params: `horizon_bars` (>=2), `signed`, `path_floor`, `fwd_col`, `label_col`, `clip`.
- Output columns: `fwd_col`, optional `label_col`.
- Leakage: χρησιμοποιεί future path μόνο ως label.
- Πότε έχει νόημα: trend-quality auxiliary target.
- Τι σημαίνει η πρόβλεψη: κοντά στο `1` σημαίνει καθαρό path, κοντά στο `0` choppy path.

```yaml
target:
  kind: future_path_efficiency
  params:
    price_col: close
    horizon_bars: 5
    signed: true
    fwd_col: target_path_efficiency_5
```

### `excess_return_regression`

- Τι κάνει: προβλέπει asset future return πάνω από benchmark future return.
- Formula: `target = future_return_asset - future_return_benchmark`.
- Required input columns: `price_col` και `benchmark_price_col`, ή αντίστοιχα returns columns.
- Params: `benchmark_price_col`, `returns_col`, `benchmark_returns_col`, `returns_type`, `benchmark_fwd_col`, `fwd_col`, `label_col`, `clip`.
- Output columns: `benchmark_fwd_col`, `fwd_col`, optional `label_col`.
- Leakage: benchmark future return είναι μέρος του label relative-performance, όχι feature.
- Πότε έχει νόημα: relative strength / alpha versus index or market proxy.
- Τι σημαίνει η πρόβλεψη: θετικό value σημαίνει expected outperformance έναντι benchmark.

```yaml
target:
  kind: excess_return_regression
  params:
    price_col: close
    benchmark_price_col: benchmark_close
    horizon_bars: 5
    fwd_col: target_excess_return_5
```

### `residual_return_regression`

- Τι κάνει: αφαιρεί rolling beta exposure προς benchmark από το asset future return.
- Formula: `target = asset_future_return - beta[t] * benchmark_future_return`.
- Required input columns: asset/benchmark price columns ή asset/benchmark returns columns.
- Params: `benchmark_price_col`, `beta_window`, `min_periods`, `returns_col`, `benchmark_returns_col`, `returns_type`, `raw_fwd_col`, `benchmark_fwd_col`, `beta_col`, `fwd_col`, `label_col`, `clip`.
- Output columns: `raw_fwd_col`, `benchmark_fwd_col`, `beta_col`, `fwd_col`, optional `label_col`.
- Leakage: το `beta_col` είναι rolling beta από returns μέχρι και το timestamp `t`. Το future benchmark return χρησιμοποιείται μόνο για το residual label.
- Πότε έχει νόημα: alpha modeling και market-neutral/relative-strength research.
- Τι σημαίνει η πρόβλεψη: θετικό value σημαίνει expected return πέρα από το beta-implied benchmark move.

```yaml
target:
  kind: residual_return_regression
  params:
    price_col: close
    benchmark_price_col: benchmark_close
    beta_window: 100
    horizon_bars: 5
    fwd_col: target_residual_return_5
```

### `future_range_regression`

- Τι κάνει: προβλέπει το μέγεθος future high-low range ανεξάρτητα από κατεύθυνση.
- Formula: `future_range = max(high[t+1:t+h]) - min(low[t+1:t+h])`; normalize by `price`, `volatility` ή `none`.
- Required input columns: `high_col`, `low_col`, και `price_col` ή `volatility_col` ανά normalization.
- Params: `normalize`, `volatility_col`, `volatility_floor`, `fwd_col`, `label_col`, `clip`.
- Output columns: `fwd_col`, optional `label_col`.
- Leakage: future range είναι volatility/range label, όχι feature.
- Πότε έχει νόημα: volatility expansion, breakout potential και position sizing.
- Τι σημαίνει η πρόβλεψη: μεγαλύτερο value σημαίνει μεγαλύτερο αναμενόμενο future range.

```yaml
target:
  kind: future_range_regression
  params:
    price_col: close
    high_col: high
    low_col: low
    normalize: price
    horizon_bars: 5
    fwd_col: target_future_range_5
```

### `future_realized_volatility`

- Τι κάνει: προβλέπει realized volatility των future one-step returns.
- Formula: `target = std(returns[t+1:t+h])`.
- Required input columns: `returns_col` ή `price_col`.
- Params: `returns_type`, `horizon_bars` (>=2), `annualize`, `periods_per_year`, `fwd_col`, `label_col`, `clip`.
- Output columns: `fwd_col`, optional `label_col`.
- Annualization convention: αν `annualize=true`, πολλαπλασιάζει με `sqrt(periods_per_year / horizon_bars)`.
- Leakage: future returns χρησιμοποιούνται μόνο ως risk label.
- Πότε έχει νόημα: risk model, volatility forecast και position sizing.
- Τι σημαίνει η πρόβλεψη: expected future realized volatility στην ίδια convention με το target.

```yaml
target:
  kind: future_realized_volatility
  params:
    price_col: close
    horizon_bars: 5
    annualize: false
    fwd_col: target_future_realized_vol_5
```

### `future_drawdown_regression`

- Τι κάνει: μετρά downside path risk στο future horizon.
- Formula long: `min(low[t+1:t+h] / close[t] - 1)`. Formula short: `close[t] / max(high[t+1:t+h]) - 1`.
- Required input columns: `price_col`, `high_col`, `low_col`, και `volatility_col` αν γίνει normalization.
- Params: `direction`, `horizon_bars`, `normalize_by_volatility`, `volatility_col`, `volatility_floor`, `fwd_col`, `label_col`, `clip`.
- Output columns: `fwd_col`, optional `label_col`.
- Leakage: future drawdown είναι label-only path risk.
- Πότε έχει νόημα: downside-aware filters, stop research και risk-aware regressors.
- Τι σημαίνει η πρόβλεψη: πιο αρνητικό value σημαίνει βαθύτερο expected adverse move.

```yaml
target:
  kind: future_drawdown_regression
  params:
    price_col: close
    high_col: high
    low_col: low
    direction: long
    horizon_bars: 5
    fwd_col: target_future_drawdown_5
```

## Recommended regression targets for trading

Προτεινόμενη σειρά χρήσης:

1. `r_multiple_regression` ως βασικό target για trading signal, επειδή η κλίμακα είναι σε risk units.
2. `volatility_normalized_future_return` ως auxiliary/diagnostic ή main target για multi-asset models.
3. `downside_adjusted_future_return` για πιο conservative signal που τιμωρεί κακή διαδρομή.
4. `future_path_efficiency` για trend quality.
5. `mfe_regression` και `mae_regression` για upside/downside modeling.
6. `future_realized_volatility` για risk model και position sizing.
7. `excess_return_regression` και `residual_return_regression` για alpha/relative strength.

M30 examples:

```yaml
target:
  kind: r_multiple_regression
  params:
    price_col: close
    volatility_col: atr_14
    atr_multiple: 2.0
    horizon_bars: 5
    clip: [-5, 5]
    fwd_col: target_r_multiple_5
```

```yaml
target:
  kind: volatility_normalized_future_return
  params:
    price_col: close
    volatility_col: atr_14
    horizon_bars: 5
    clip: [-5, 5]
    fwd_col: target_vol_norm_return_5
```

```yaml
target:
  kind: downside_adjusted_future_return
  params:
    price_col: close
    high_col: high
    low_col: low
    direction: long
    horizon_bars: 5
    penalty_lambda: 1.0
    clip: [-5, 5]
    fwd_col: target_downside_adjusted_return_5
```

```yaml
target:
  kind: future_path_efficiency
  params:
    price_col: close
    horizon_bars: 5
    signed: true
    fwd_col: target_path_efficiency_5
```
### `path_dependent_r`

What it measures:

- A side-oriented, path-dependent R outcome for already-built primary candidates.
- It is post-model only: it consumes OOS predictions/candidates and is not a primary training target.

Core convention:

- Signal is observed at the close of bar `t`.
- Default entry is `open[t+1]`, matching `manual_barrier`.
- The same shared barrier outcome helper used by the manual backtest computes entry, exit, TP/SL/time exit, costs, slippage, gross R, net R, MFE, and MAE.

R definition:

- `risk_distance = volatility_col[t] * stop_loss_r` when `stop_mode = volatility_stop`.
- `gross_r = gross_return / risk_distance`.
- `net_r = net_return / risk_distance`.
- Returns and R are side-oriented: profitable long and profitable short trades are positive; losing long and losing short trades are negative.

Costs and slippage:

- Gross return is measured before transaction costs and slippage.
- Net return subtracts fixed round-trip cost `2 * cost_per_unit_turnover` and slippage drag.
- `meta_net_r` is computed after those deductions.

Same-bar TP/SL:

- Default `tie_break = conservative` resolves a bar that touches TP and SL to the stop side.
- With `legacy_same_bar_stop_reason = true`, the target reports `stop_and_target_same_bar_stop_first`, matching the legacy manual backtest reason.

Outputs:

- Candidate metadata: `meta_candidate`, `meta_side`.
- Path outcomes: `meta_entry_price`, `meta_exit_price`, `meta_exit_reason`, `meta_hit_type`, `meta_hit_step`, `meta_holding_bars`, `meta_gross_return`, `meta_net_return`, `meta_gross_r`, `meta_net_r`, `meta_mfe_r`, `meta_mae_r`.
- Deterministic labels on candidate rows only: `meta_label_positive`, `meta_label_min_0_25r`, `meta_label_min_0_50r`, `meta_label_min_1_00r`.

Leakage policy:

- `require_oos = true` by default, so a row must have `pred_is_oos = true` as well as `candidate_col = 1`.
- Non-candidate rows keep NaN outcomes and NaN labels, not negative labels.
- Tail rows without the full future path keep NaN outcomes/labels unless `allow_partial_horizon = true`.

Minimal YAML:

```yaml
target:
  kind: path_dependent_r
  params:
    candidate_col: primary_candidate
    side_col: primary_candidate_side
    pred_is_oos_col: pred_is_oos
    volatility_col: atr_over_price_48
    stop_mode: volatility_stop
    take_profit_r: 5.0
    stop_loss_r: 2.0
    max_holding_bars: 24
    cost_per_turnover: 0.0001
    slippage_per_turnover: 0.0
```
