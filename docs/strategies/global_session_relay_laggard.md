# Global Session Relay Laggard — Αναλυτικός ερευνητικός οδηγός

## Σκοπός και ερευνητική υπόθεση

Η `global_session_relay_laggard` είναι μια ντετερμινιστική, πολυ-περιουσιακή στρατηγική έρευνας σε χρονικό πλαίσιο 30 λεπτών. Εξετάζει την υπόθεση ότι όταν μια αγορά ή μια τοπική συνεδρία εμφανίζει ισχυρή και ομοιόμορφη κατεύθυνση, ένα «καθυστερημένο» μέλος του ίδιου cluster μπορεί να ακολουθήσει την κίνηση. Η καθυστέρηση μπορεί να αναγνωριστεί είτε μέσα στο ίδιο cluster είτε ως μετάδοση πληροφορίας από μία νωρίτερη γεωγραφική συνεδρία στην επόμενη.

Η στρατηγική δεν αποτελεί ισχυρισμό κερδοφορίας, παγκόσμιας μοναδικότητας ή παραγωγικής ετοιμότητας. Είναι μια νέα ερευνητική υπόθεση. Πριν από οποιαδήποτε πραγματική χρήση απαιτούνται frozen out-of-sample έλεγχοι, robustness tests, έλεγχος κόστους/ρευστότητας και αξιολόγηση των κινδύνων εκτέλεσης.

Η οικογένεια των πειραμάτων χρησιμοποιεί το όνομα `global_session_relay_laggard` και αποφεύγει σκόπιμα ML μοντέλα ή μελλοντικές ετικέτες: το `model.kind` είναι `none` και τα σήματα παράγονται από κανόνες panel.

## Σύμπαν και ρόλοι των assets

Το ερευνητικό σύμπαν έχει 15 καθαρισμένα αρχεία Dukascopy 30m:

| Ρόλος | Assets |
|---|---|
| Ασία | `NIKKEI225`, `AUS200` |
| Ευρώπη | `EU50`, `GER40`, `FRA40`, `UK100` |
| ΗΠΑ | `SPX500`, `US30`, `US100` |
| Ενέργεια | `BRENT`, `USOIL` |
| Πολύτιμα μέταλλα | `XAUUSD`, `XAGUSD` |
| Μακροοικονομικό context | `ETHUSD`, `EURUSD` |

Τα clusters έχουν τις παρακάτω συμβάσεις επιλεξιμότητας:

| Cluster | Ελάχιστα ενεργά μέλη | Απαιτούνται όλα τα μέλη |
|---|---:|---:|
| `asia` | 2 | Ναι |
| `europe` | 3 | Όχι |
| `usa` | 3 | Ναι |
| `energy` | 2 | Ναι |
| `metals` | 2 | Ναι |

Το `ETHUSD` και το `EURUSD` είναι context-only assets. Δεν μπορούν να παραγάγουν tradable θέση, ακόμη κι αν διαθέτουν τεχνικά χαρακτηριστικά ή ανήκουν στο data universe. Το `EURUSD` είναι αποκλειστικά διαγνωστικό. Το `ETHUSD` συμμετέχει μόνο στο προαιρετικό macro veto της v5.

## Κρίσιμη αρχή: άνιστες ιστορίες χωρίς τεχνητή ευθυγράμμιση

Τα assets δεν αρχίζουν, δεν τελειώνουν και δεν διαπραγματεύονται στις ίδιες χρονικές στιγμές. Για τον λόγο αυτό η υλοποίηση δεν κατασκευάζει ένα κοινό παγκόσμιο sample με inner join όλων των 15 assets.

Κάθε asset διατηρεί το δικό του native `DatetimeIndex`. Δεν γίνεται forward-fill σε:

- `open`, `high`, `low`, `close` ή άλλες τιμές OHLC,
- αποδόσεις, ATR ή realized volatility,
- σήματα, flags επιλεξιμότητας ή tradability,
- τιμές εκτέλεσης εισόδου/εξόδου.

Η μόνη επιτρεπτή «μεταφορά» είναι cross-asset context με as-of λογική. Δηλαδή, για timestamp στόχου `t` χρησιμοποιείται μόνο πηγή με `source_timestamp <= t`. Ένα κενό Σαββατοκύριακου, μια νυχτερινή παύση ή μια απουσία bar δεν θεωρείται ένα απλό bar παλιό context: η ηλικία υπολογίζεται με πραγματικό elapsed χρόνο.

Κάθε μεταφερόμενο context συνοδεύεται από:

- `context_timestamp`: το πραγματικό timestamp της πηγής,
- `context_age_minutes`: τα λεπτά από το source έως το target timestamp,
- `context_age_bars`: `context_age_minutes / 30`,
- `context_is_fresh`: αν η τιμή είναι ακόμη εντός του επιτρεπτού age limit.

Όταν το age limit ξεπεραστεί, το context καθίσταται unavailable (`NaN`) και δεν μπορεί να ενεργοποιήσει signal. Η στρατηγική χρησιμοποιεί ως default 8 bars/240 λεπτά για relay context και 4 bars/120 λεπτά για macro context.

## Per-asset χαρακτηριστικά

Πριν από οποιονδήποτε panel υπολογισμό, κάθε asset επεξεργάζεται ανεξάρτητα στο native dataframe του.

1. Απλή απόδοση κλεισίματος:

   `close_ret = close / close.shift(1) - 1`

2. Wilder ATR 20 περιόδων:

   `atr_20 = WilderATR(high, low, close, 20)`

3. Rolling realized volatility 96 πραγματικών παρατηρήσεων:

   `vol_rolling_96 = std(close_ret, 96)`

4. Volatility-normalized impulse:

   `return_12_real_bars = close / close.shift(12) - 1`

   `impulse_12_96 = return_12_real_bars / (vol_rolling_96 * sqrt(12))`

Οι 12 και 96 παρατηρήσεις είναι πραγματικές native παρατηρήσεις του συγκεκριμένου asset και όχι κοινές 30λεπτες θέσεις σε ένα τεχνητό panel. Η κύλιση είναι trailing, ποτέ centered. Μηδενική, αρνητική ή μη έγκυρη volatility, καθώς και άπειρες τιμές, μετατρέπονται σε `NaN`. Έτσι, τα warm-up rows δεν αποκτούν πλασματικό σήμα.

## Συνεδρίες, τοπικές ώρες και DST

Η στρατηγική διαθέτει configurable research-session metadata ανά asset. Δεν ισχυρίζεται ότι οι ώρες αυτές είναι επίσημα calendars χρηματιστηρίων. Χρησιμοποιεί `zoneinfo`, άρα η μετατροπή από UTC-naive timestamps σε τοπική ώρα σέβεται τις αλλαγές daylight saving time.

Ενδεικτικά, τα ευρωπαϊκά indices χρησιμοποιούν τοπικά ανοίγματα περίπου 08:00–09:00 και τα αμερικανικά 09:30 New York time. Τα πλήρη defaults βρίσκονται στο panel feature component και μπορούν να υπερκαλυφθούν από το YAML.

Για κάθε asset παράγονται:

- `is_in_primary_session`: αν το πραγματικό bar βρίσκεται στη configured συνεδρία,
- `is_primary_session_open_window`: αν είναι ένα από τα πρώτα τέσσερα πραγματικά bars της συνεδρίας,
- `session_id`: σταθερό audit-friendly αναγνωριστικό της μορφής `ASSET:YYYY-MM-DD`,
- `session_open_price`: το `open` του πρώτου πραγματικού bar που παρατηρήθηκε μέσα στη συνεδρία,
- `session_return`: μεταβολή του τελευταίου πραγματικού `close` έναντι του `session_open_price`,
- `bars_since_session_open`: πλήθος πραγματικών και όχι κατασκευασμένων bars από το άνοιγμα.

Αν λείπει ένα bar μέσα στη συνεδρία, δεν δημιουργείται. Επομένως το «πρώτα τέσσερα bars» σημαίνει τα πρώτα τέσσερα που υπάρχουν πραγματικά στο native αρχείο.

## Cluster features και ορισμός leader/laggard

Σε κάθε timestamp ενός μέλους cluster, η στρατηγική ευθυγραμμίζει causally τα πρόσφατα, fresh `impulse_12_96` των υπόλοιπων μελών. Από τα διαθέσιμα μέλη υπολογίζει:

- median και mean impulse,
- signed breadth: `mean(sign(member_impulse))`, με εύρος `[-1, 1]`,
- αριθμό μελών, θετικών και αρνητικών μελών,
- leader και laggard,
- robust dispersion ως median absolute deviation από το cluster median,
- eligibility του cluster και μέγιστη context age.

Για θετικό cluster direction (`median > 0`):

- leader είναι το asset με το μεγαλύτερο impulse,
- laggard είναι το asset με το μικρότερο μη αρνητικό impulse.

Για αρνητικό cluster direction (`median < 0`):

- leader είναι το asset με το μικρότερο impulse,
- laggard είναι το asset με το μεγαλύτερο μη θετικό impulse, δηλαδή το αρνητικό που βρίσκεται πλησιέστερα στο μηδέν.

Αν δεν υπάρχει laggard που να έχει το ίδιο πρόσημο με τη cluster direction, δεν υπάρχει laggard candidate. Σε ισοπαλία χρησιμοποιείται αλφαβητική σειρά symbol, ώστε η συμπεριφορά να είναι πλήρως ντετερμινιστική και επαναλήψιμη.

Οι στήλες γράφονται μόνο στα σχετικά native frames, για παράδειγμα `usa_cluster_impulse_median`, `usa_cluster_leader_asset`, `usa_cluster_laggard_asset`, `usa_cluster_dispersion` και `usa_cluster_eligible`.

## Κανόνες εισόδου intra-cluster

Οι intra-cluster είσοδοι εφαρμόζονται στα `europe`, `usa`, `energy` και `metals` clusters.

### Long

Απαιτούνται ταυτόχρονα:

- επιλέξιμο cluster,
- cluster median impulse τουλάχιστον `+0.80`,
- breadth τουλάχιστον `+0.75`,
- leader impulse τουλάχιστον `+1.25`,
- το target asset να είναι ο τρέχων cluster laggard,
- laggard impulse στο διάστημα `[0.00, +0.45]`,
- έγκυρα target `atr_20` και `vol_rolling_96`,
- πραγματικό επόμενο asset bar με έγκυρο `open` για εκτέλεση.

### Short

Η συμμετρική πλευρά απαιτεί median έως `-0.80`, breadth έως `-0.75`, leader έως `-1.25` και laggard impulse στο `[-0.45, 0.00]`.

Στα διμελή clusters `energy` και `metals`, και τα δύο μέλη πρέπει να έχουν το ίδιο μη μηδενικό πρόσημο. Αυτό αποτρέπει ένα median που μοιάζει ισχυρό αλλά προκύπτει από αντικρουόμενα μέλη.

## Relay από Ασία προς Ευρώπη

Το Asia→Europe relay αξιολογείται μόνο στα πρώτα τέσσερα πραγματικά European-session bars κάθε ευρωπαϊκού target asset. Οι πηγές είναι `NIKKEI225` και `AUS200` και απαιτούνται και οι δύο.

Για κάθε πηγή υπολογίζεται:

`normalized_session_return = session_return / (vol_rolling_96 * sqrt(max(bars_since_session_open, 1)))`

Το relay score είναι ο median των δύο fresh normalized session returns. Η πηγή πρέπει να έχει timestamp όχι μεταγενέστερο από το ευρωπαϊκό target bar και context age έως 8 bars.

Long relay candidate απαιτεί score τουλάχιστον `+0.80`, Europe cluster breadth τουλάχιστον `+0.50`, Europe laggard με impulse `[0.00, +0.50]`, και target ίσο με τον laggard. Η short πλευρά εφαρμόζει τη συμμετρική αρνητική λογική.

## Relay από Ευρώπη προς ΗΠΑ

Το Europe→USA relay αξιολογείται μόνο στα πρώτα τέσσερα πραγματικά USA-session bars. Πηγές είναι `EU50`, `GER40`, `FRA40` και `UK100`. Απαιτούνται τουλάχιστον τρεις από τις τέσσερις πηγές με fresh context.

Το score είναι ο median των διαθέσιμων normalized European session returns. Για long απαιτείται score τουλάχιστον `+0.80`, USA breadth τουλάχιστον `+0.333333`, και USA laggard impulse `[0.00, +0.50]`. Η short πλευρά είναι συμμετρική.

Τα relay diagnostics περιλαμβάνουν `*_relay_score`, `*_source_count`, `*_context_age_bars` και `*_eligible`. Όταν τα source ages διαφέρουν, η εκτεθειμένη primary age είναι η μέγιστη age, δηλαδή η πιο συντηρητική περιγραφή freshness.

## Προτεραιότητα σημάτων και diagnostics

Αν στο ίδιο asset και timestamp υπάρχουν περισσότεροι από ένας candidate κανόνες, δεν προστίθενται τα σήματα. Επιλέγεται ένα και μόνο final signal με τη σειρά:

1. `europe_to_usa_relay`
2. `asia_to_europe_relay`
3. `intra_cluster`

Το τελικό `signal_global_session_relay` είναι μόνο `+1.0`, `-1.0` ή `0.0`. Επιπλέον στήλες περιγράφουν `signal_module`, `signal_strength`, `entry_eligible`, `entry_rejection_reason`, cluster direction, laggard gap, relay score και macro score. Οι reasons είναι deterministic, ώστε να μπορούν να ομαδοποιηθούν σε artifacts.

## Προαιρετικό macro veto της v5

Το macro veto είναι απενεργοποιημένο στις v1–v4 και ενεργό μόνο στην v5. Για το target timestamp χρησιμοποιεί τις τελευταίες fresh impulse τιμές από `ETHUSD`, `XAUUSD` και `BRENT`:

`macro_score = (sign(ETH impulse) - sign(gold impulse) + sign(BRENT impulse)) / 3`

Για long equity-index entries απαιτεί `macro_score >= 0`; για short equity-index entries απαιτεί `macro_score <= 0`. Αν οποιοδήποτε από τα τρία required context values είναι stale ή unavailable, το equity entry απορρίπτεται με `macro_veto`.

Το φίλτρο εφαρμόζεται μόνο σε equity-index clusters (`asia`, `europe`, `usa`). Δεν εφαρμόζεται σε `BRENT`, `USOIL`, `XAUUSD` ή `XAGUSD`. Το `EURUSD` παραμένει διαγνωστικό και δεν ασκεί veto.

## Dynamic exits

Τα exit features υπολογίζονται causally στο κλείσιμο του current bar. Η εκτέλεσή τους δεν γίνεται στο ίδιο close, αλλά στο επόμενο πραγματικό `open` του ίδιου asset. Αυτό είναι σημαντικό τόσο για αποφυγή leakage όσο και για αποφυγή synthetic/foreign-asset execution timestamps.

Υπάρχουν convergence, cluster-failure και stale-context exits. Το convergence ισχύει όταν:

`abs(asset_impulse_12_96 - cluster_impulse_median) <= 0.20`

Για long, cluster failure εμφανίζεται όταν το cluster median είναι μη θετικό ή το απόλυτο median είναι μικρότερο από `0.30`. Για short, ισχύει το συμμετρικό μη αρνητικό condition. Relay trades κλείνουν όταν το απαιτούμενο relay context γίνει stale. Intra-cluster trades κλείνουν όταν το target cluster γίνει ineligible.

Υπάρχουν γενικές side-aware στήλες (`relay_dynamic_exit_long`, `relay_dynamic_exit_short`) και module-aware στήλες. Οι δεύτερες εμποδίζουν ένα stale Europe→USA feed να κλείσει κατά λάθος μια intra-cluster θέση USA.

Η σειρά γεγονότων στο `portfolio_barrier` είναι:

1. ήδη προγραμματισμένο dynamic exit εκτελείται στο τρέχον πραγματικό open,
2. διαφορετικά ελέγχονται stop-loss και take-profit ενδοσυνεδριακά,
3. σε double touch εφαρμόζεται το συντηρητικό `tie_break: stop`,
4. στο close αξιολογείται νέο dynamic exit,
5. νέο dynamic exit προγραμματίζεται για το επόμενο πραγματικό open,
6. το vertical barrier αποτελεί fallback.

Τα trade artifacts αποθηκεύουν `dynamic_exit_signal_time`, `dynamic_exit_execution_time` και `dynamic_exit_reason`.

## Portfolio, sizing και correlation guard

Το portfolio χρησιμοποιεί `signal_weights`, gross target `0.75`, per-asset cap `0.25` και group cap `0.25`. Το risk guard επιτρέπει έως τρεις ταυτόχρονες trades και έως μία ανοικτή trade ανά group. Με `risk_per_trade: 0.0025`, το θεωρητικό μέγιστο simultaneous stop risk είναι περίπου `3 × 0.25% = 0.75%` του equity.

Το stop είναι `1.25R`, ο στόχος `1.75R` και το vertical barrier οκτώ native bars. Η είσοδος γίνεται σε `next_open` και όχι στο bar του signal.

Στις v4/v5 ενεργοποιείται correlation guard. Πριν ανοίξει candidate θέση:

1. βρίσκονται οι ενεργές trades της ίδιας πλευράς,
2. χρησιμοποιείται μόνο η τομή των πραγματικών timestamps των returns,
3. οι παρατηρήσεις σταματούν αυστηρά πριν από το signal timestamp (`t-1`),
4. χρησιμοποιούνται έως 960 valid overlap observations,
5. απαιτούνται τουλάχιστον 240 observations,
6. η θέση απορρίπτεται όταν `abs(correlation) > 0.80`.

Δεν γίνεται forward-fill στις returns. Αν η ιστορία δεν επαρκεί, το trade επιτρέπεται αλλά καταγράφεται ως insufficient history. Τα accepted trades και τα rejected events περιλαμβάνουν correlation diagnostics.

## Fixed και dynamic universe modes

Στο `fixed` mode κάθε module προσδιορίζει τη δική του native eligible περίοδο από τα assets που χρειάζεται. Για παράδειγμα το USA module εξαρτάται από τα τρία USA assets, όχι από το πότε ξεκίνησε το `ETHUSD`. Το ίδιο ισχύει για energy, metals και Europe.

Στο `dynamic` mode κάθε module ενεργοποιείται αμέσως μόλις ικανοποιήσει το δικό του contract. Η `global_session_relay_laggard_v5_dynamic_universe.yaml` είναι robustness variant της v5 και όχι υποχρεωτικά ο επόμενος επιλεγμένος παραγωγικός κανόνας.

## Config ladder

Τα YAML αρχεία βρίσκονται στο `config/experiments/global_session_relay/`:

| Config | Διαφορά από το προηγούμενο |
|---|---|
| v1 | Μόνο intra Europe/USA/energy/metals |
| v2 | Προσθέτει Europe→USA relay |
| v3 | Προσθέτει Asia→Europe relay |
| v4 | Προσθέτει correlation guard |
| v5 | Προσθέτει equity-only macro veto |
| v5 dynamic | Ίδιοι v5 κανόνες με `universe_mode: dynamic` |

Το repository δεν υποστηρίζει YAML inheritance/`extends`. Για αυτό κάθε config είναι αυτοτελές και το λογικό parent αναφέρεται στο `research_metadata.parent_experiment`.

## Artifacts και coverage audit

Panel runs μπορούν να παράγουν:

- `panel_asset_eligibility.csv`,
- `panel_cluster_coverage.csv`,
- `panel_module_coverage.csv`,
- `panel_context_freshness.csv`,
- `panel_signal_diagnostics.csv`,
- `panel_rejection_reasons.csv`,
- `correlation_guard_events.csv`, όταν υπάρχουν rejection events.

Το audit coverage δεν είναι backtest. Ελέγχει αρχή/τέλος ιστορίας, duplicates, gap statistics, spread statistics, pairwise overlap, cluster/module coverage και session coverage. Τα outputs είναι CSV και ένα compact `coverage_summary.json`.

## Χειροκίνητοι έλεγχοι

```powershell
# Έλεγχος των νέων panel/backtest/audit/config tests
python -m pytest tests/panel/test_global_session_relay.py tests/backtesting/test_portfolio_barrier_panel_extensions.py tests/scripts/test_audit_dukascopy_30m_panel_coverage.py tests/utils/test_global_session_relay_config_validation.py -q

# Audit των πραγματικών καθαρισμένων CSV
python scripts/audit_dukascopy_30m_panel_coverage.py --input-dir data/raw/dukascopy_30m_clean --output-dir reports/global_session_relay_coverage

# Εκτέλεση του πρώτου research experiment
python -m src.experiments.runner config/experiments/global_session_relay/global_session_relay_laggard_v1_intra_cluster.yaml
```

Η τιμή `periods_per_year: 3276` αντιστοιχεί προσεγγιστικά σε `252 × 13` regular-session 30λεπτα bars. Επειδή το σύμπαν περιέχει αγορές με διαφορετικά ωράρια και coverage, η annualization είναι προσέγγιση και πρέπει να επανεξεταστεί μετά το coverage audit.

## Περιορισμοί

- Οι configured συνεδρίες είναι research definitions και όχι πλήρη exchange calendars.
- Το ιστορικό Dukascopy μπορεί να έχει gaps, διαφορετικές ώρες και διαφορετικές περίοδους κάλυψης.
- Το backtest δεν εξαλείφει slippage, liquidity, spread regime ή operational risk.
- Η αιτιότητα και η freshness μειώνουν το leakage risk, αλλά δεν υποκαθιστούν ανεξάρτητο out-of-sample validation.
- Η υλοποίηση δεν τεκμηριώνει ότι η στρατηγική είναι κερδοφόρα.
