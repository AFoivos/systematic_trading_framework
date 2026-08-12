# Ερευνητικό συμβόλαιο Alpha Discovery — hardened specification

## Σκοπός και όριο

Η παρούσα φάση χτίζει την αλυσίδα ακεραιότητας μέτρησης:

`dataset bytes → schema → units → timestamps → data quality → evidence role → immutable snapshot`

Έχουν υλοποιηθεί μόνο τα preregistered primitive features, future outcomes, conditional scanner και statistical methods που απαιτούνται από το `AR-0001`. Έχουν εκτελεστεί μόνο synthetic/unit/integration tests και read-only snapshot validation. Δεν έχει γίνει πραγματικό feature mining ή εκτέλεση του `AR-0001`, ούτε backtest, παραγωγή signal, Optuna ή ML. Το checked-in `AR-0001` παραμένει `SPECIFICATION_ONLY` και δεν είναι εγκεκριμένο για εκτέλεση.

## Evidence roles

Κάθε immutable snapshot αποκτά έναν και μόνο ρόλο. Ο ρόλος δεν αλλάζει εκ των υστέρων.

- `DISCOVERY`: επιτρέπεται για διατύπωση υποθέσεων, exploratory feature analysis και fitting των bins.
- `VALIDATION`: χρησιμοποιείται μόνο σε ήδη παγωμένη υπόθεση, παγωμένα bins και παγωμένα promotion gates.
- `HISTORICAL_PSEUDO_OOS`: ιστορικό diagnostic evidence που έχει ήδη εξεταστεί. Δεν επιτρέπεται ποτέ να μετονομαστεί σε final holdout.
- `PROSPECTIVE_FINAL`: δεδομένα που συλλέγονται μετά το specification freeze. Δεν είναι ορατά στο discovery interface και απαιτούν ξεχωριστή, ρητή εξουσιοδότηση.

Η machine-readable μορφή βρίσκεται στα `research_contract.schema.json`, `alpha_discovery_spec.schema.json` και στα enums του `src/src_data/research_roles.py`.

## Contamination και material changes

Αν εξεταστούν validation αποτελέσματα και μετά αλλάξει η υπόθεση, το ίδιο validation sample θεωρείται contaminated για τη νέα εκδοχή. Η νέα εκδοχή χρειάζεται νέο version/spec hash και νέο validation evidence.

Μετά το prospective freeze, οποιαδήποτε από τις παρακάτω αλλαγές επανεκκινεί το prospective clock:

- feature definitions,
- feature windows,
- bins,
- horizons,
- costs,
- hypothesis conditions,
- promotion gates,
- execution semantics.

## Γιατί οι μονάδες spread είναι blocking contract

Οι τρεις επιτρεπτές αναπαραστάσεις είναι διαφορετικά μεγέθη:

```text
spread_absolute = ask - bid
spread_fraction = spread_absolute / mid
spread_bps      = 10_000 × spread_fraction
```

Για `bid=100` και `ask=100.10`, το `mid=100.05`, το absolute spread είναι `0.10`, το fraction περίπου `0.0009995` και τα bps περίπου `9.995`. Αν το fraction αποθηκευτεί με όνομα `spread_bps`, thresholds, execution costs και cross-dataset συγκρίσεις αποκτούν σφάλμα κλίμακας `10.000×`.

Το `spread_close` διατηρείται μόνο ως backward-compatible alias του `spread_absolute`. Δεν χρησιμοποιείται ως μονάδα χωρίς ρητό contract.

## Immutable snapshots και enforced hashes

Ένα research snapshot αντιγράφει ακριβώς τα source bytes σε write-once directory και καταγράφει manifest με:

- source path, asset, timeframe, timezone και cadence,
- row count, first/last timestamp,
- SHA-256 των bytes,
- column names, dtypes και units,
- quote/volume semantics,
- gaps, duplicates, NaN, Inf και συνολικό quality status,
- source classification, evidence role και role eligibility,
- code/config version και run-identity hash.

Το SHA της config δεν είναι πληροφοριακό. Κατά το load πρέπει να συμφωνούν και τα τρία: `config expected_sha256`, `manifest sha256`, actual frozen-file SHA-256. Μετά επαληθεύονται schema, dtypes και row count. Οποιαδήποτε απόκλιση αποτυγχάνει πριν δοθούν δεδομένα στο research layer.

Το `run_identity_sha256` δεσμεύει επίσης το evidence role, το source classification, το serialized data-quality contract, τα quote semantics και τις code/config versions. Επομένως ούτε μία συντακτικά έγκυρη χαλάρωση του quality policy μέσα στο manifest μπορεί να περάσει ως το ίδιο immutable run identity.

Το ίδιο ακριβές byte hash δεν επιτρέπεται να παγώσει κάτω από διαφορετικό evidence role μέσα στο ίδιο snapshot registry. Νέα contract version με τον ίδιο ρόλο μπορεί να διατηρηθεί ως ξεχωριστό immutable record, αλλά τα known historical bytes δεν μπορούν να παρουσιαστούν ξανά ως `PROSPECTIVE_FINAL`.

## Data quality

Τα reports χρησιμοποιούν `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Ελέγχονται timestamp parsing/order/duplicates, timezone και DST localization, cadence, missing/short intervals, suspicious gaps, NaN/Inf, OHLC και bid/ask geometry, canonical spread units, non-negative volume και δηλωμένα volume semantics. Υπάρχουν επίσης cross-asset coverage/join-loss, exact duplicate-file και schema-consistency checks.

`CRITICAL` απαγορεύει πάντοτε research use. Η τρέχουσα fail-closed πολιτική απαγορεύει και snapshots με `ERROR`.

## Processed-data quarantine

Αρχεία από `processed`, `artifacts`, predictions ή backtests και στήλες όπως targets, labels, predictions, signals, positions ή OOS markers δεν ταξινομούνται ως validated market data. Το `DiscoveryDataAccess` τα απορρίπτει by default.

Υπάρχει μόνο ρητό escape hatch για ειδικό diagnostic use: `enabled=true`, `warning_acknowledged=true` και μη κενός λόγος. Εκπέμπεται runtime warning. Το override δεν παρακάμπτει quality failures, legacy/unknown source classification ή evidence-role mismatch.

## Role firewall

Το μελλοντικό discovery execution boundary δέχεται μόνο `DiscoveryDataAccess`. Το validation χρησιμοποιεί διαφορετικό `ValidationDataAccess`. Το prospective layer έχει διαφορετικό class, απαιτεί πλήρες authorization object και δεσμεύει τόσο το snapshot reference όσο και το manifest config-version στο ακριβές frozen specification SHA. Έτσι:

- validation data δεν φορτώνονται σιωπηρά ως discovery,
- historical pseudo-OOS δεν γίνονται final,
- prospective data δεν είναι προσβάσιμα από το normal discovery pipeline.

## Τι σημαίνει `available_at`

Κάθε μελλοντικό feature δηλώνει πότε υπάρχει πραγματικά η πληροφορία. Η χρονική σειρά μέσα σε ένα bar είναι:

`open[t] < close[t] < open[t+1]`

Ένα bar-close feature έχει `available_at={bar_offset: 0, event: CLOSE}`. Μπορεί να καταναλωθεί στο `close[t]` ή αργότερα, αλλά όχι στο `open[t]`. Next-open execution δηλώνεται στο `{bar_offset: 1, event: OPEN}`. Ο κοινός contract απορρίπτει consume-before-available.

## Frozen measurement contract

Το `AR-0001` επιτρέπει αποκλειστικά:

- log returns στα 1, 4, 16 και 48 bars,
- path efficiency στα 8, 16 και 48 bars,
- realized volatility στα 16, 48 και 192 bars,
- normalized range, close location, UTC hour και weekday,
- future outcomes στα 1, 2, 4, 8, 16 και 32 bars,
- discovery-fitted quintiles που αποθηκεύονται με δικό τους hash και δεν επαναπροσαρμόζονται σε validation data,
- όλες τις 1D καταστάσεις και μόνο τα εννέα window-pairs της οικογένειας `path_efficiency × realized_volatility`,
- αυστηρή bar eligibility `FULL_30_OF_30_OBSERVED_MINUTES`, χωρίς repair ή imputation,
- ακύρωση κάθε feature/target dependency window που περιέχει partial bar ή διασχίζει timestamp gap,
- full-timeline, non-circular, segmented moving-block bootstrap, στρωματοποιημένο στα έξι παγωμένα calendar periods, με primary block 48 και diagnostic sensitivities 96/192,
- Newey–West HAC για τον conditional-mean ratio estimator, Bartlett kernel, primary fixed lag 48 και diagnostic sensitivities 96/192,
- global Benjamini–Yekutieli στο 5% ως binding statistical-screen gate πάνω σε ακριβώς 3.792 preregistered effects.

Τα effect rows δεν φιλτράρονται πριν από το multiple-testing gate. Αποτυχία λόγω eligibility, insufficient `N`, coverage, block coverage ή primary inference παραμένει στο registry ως `AUTOMATIC_FAIL` με `p=1`. Επομένως ο global denominator δεν μπορεί να μικρύνει εκ των υστέρων. Τα local BH/BY και το global BH είναι μόνο diagnostics· δεν αντικαθιστούν το binding global BY.

Τα έξι stability periods είναι ημερολογιακά (`Y2020`, …, `Y2024`, `Y2025H1`) και όχι equal-row partitions. Ο bootstrap και το HAC διατηρούν το αρχικό row spacing, δεν συμπιέζουν τα condition hits και δεν επιτρέπουν covariance/block pairs να διασχίζουν gap ή calendar-stratum boundary.

Η κατάσταση παρατηρείται στο `close[t]`. Η executable είσοδος γίνεται στο `open[t+1]` και η έξοδος στο `open[t+h+1]`. Το long αγοράζει στο πραγματικό ASK και πουλά στο πραγματικό BID· το short πουλά στο BID και καλύπτει στο ASK. Το δηλωμένο `net_cost_scope` είναι `OBSERVED_BID_ASK_SPREAD_ONLY`: commission, slippage και swap δεν κατασκευάζονται χωρίς ξεχωριστή frozen παραδοχή και παραμένουν υποχρεωτικό promotion-gate θέμα πριν από strategy validation.

Δεν υπάρχει arbitrary 2D/3D search, threshold optimization, autonomous hypothesis generation, signal/stops/take-profit optimization ή model fitting.

## Γιατί δεν γίνεται alpha mining τώρα

Η legacy Dukascopy 30m οικογένεια εξακολουθεί να είναι ακατάλληλη ως canonical research input λόγω της παλιάς αμφίσημης μονάδας `spread_bps` και της απουσίας των αρχικών pre-merge source bytes. Δεν διορθώθηκε αναδρομικά.

Αντί γι' αυτό ανακτήθηκαν ξεχωριστά genuine Dukascopy BID και ASK minute observations και παρήχθη το immutable parent `ETHUSD-30M-CANONICAL-V1`. Με παγωμένο cutoff `2025-07-01T00:00:00Z`, δημιουργήθηκαν δύο ξεχωριστά write-once children: το `ETHUSD-30M-DISCOVERY-PRE-2025-07-01-V1` και το `ETHUSD-30M-HISTORICAL-PSEUDO-OOS-POST-2025-07-01-V1`. Το pipeline δέχεται μόνο το πρώτο μέσω `DiscoveryDataAccess` και δεν έχει path που να φορτώνει αυτόματα το δεύτερο.

Η πραγματική conditional analysis δεν ξεκινά ακόμη: κατόπιν ρητής οδηγίας το status παραμένει `SPECIFICATION_ONLY`, το `runtime.perform_alpha_calculation` παραμένει `false` και το fail-closed boundary απορρίπτει την εκτέλεση πριν από data access.

## Προϋποθέσεις πριν τρέξει το AR-0001

Οι data-foundation και implementation προϋποθέσεις 1–6 έχουν ολοκληρωθεί και έχουν περάσει dry validation. Απομένει μόνο workflow authorization:

1. Ρητή ανθρώπινη έγκριση του ακριβούς checked-in `specification_hash`.
2. Αλλαγή του `status` σε `APPROVED_TO_RUN` με πλήρη approval metadata.
3. Αλλαγή του `runtime.perform_alpha_calculation` σε `true` και αφαίρεση του approval blocker. Αυτές είναι workflow μεταβολές και δεν αλλάζουν το scientific hash.
4. Εκτέλεση του approval-gated command:

```bash
docker compose run --rm app python -m src.experiments.orchestration.alpha_discovery_pipeline --config config/research/alpha_discovery/AR-0001_ethusd_30m.yaml
```

Με την τρέχουσα `SPECIFICATION_ONLY` κατάσταση, η ίδια εντολή αποτυγχάνει πριν από οποιοδήποτε data access ή alpha calculation, όπως απαιτεί το contract.
