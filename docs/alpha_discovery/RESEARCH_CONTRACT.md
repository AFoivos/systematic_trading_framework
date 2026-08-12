# Ερευνητικό συμβόλαιο Alpha Discovery — PHASE 0–2

## Σκοπός και όριο

Η παρούσα φάση χτίζει μόνο την αλυσίδα ακεραιότητας μέτρησης:

`dataset bytes → schema → units → timestamps → data quality → evidence role → immutable snapshot`

Δεν γίνεται feature mining, conditional-return scanning, bootstrap/FDR υπολογισμός, backtest, παραγωγή signal, Optuna ή ML. Το `AR-0001` είναι προδιαγραφή και όχι εκτελέσιμο πείραμα.

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

## Γιατί δεν γίνεται alpha mining τώρα

Η τρέχουσα Dukascopy 30m οικογένεια έχει αποδεδειγμένα λανθασμένη μονάδα στο `spread_bps`, ενώ λείπουν τα original pre-merge BID/ASK αρχεία. Η διόρθωση των source producers δεν αποδεικνύει αναδρομικά το historical join, τις απώλειες coverage ή τα source bytes. Η έναρξη alpha search πάνω σε αυτά τα δεδομένα θα βελτιστοποιούσε μη αξιόπιστες μετρήσεις.

## Προϋποθέσεις πριν τρέξει το AR-0001

1. Να ανακτηθούν τα original ETHUSD 30m Dukascopy BID και ASK αρχεία με provenance και hashes.
2. Να γίνει regeneration με τον canonical producer και μηδενικά crossed close quotes.
3. Να περάσουν schema, unit, timestamp, cadence, gap, duplicate, OHLC/quote, NaN/Inf και volume-semantics checks.
4. Να παγώσει νέο `VALIDATED_MARKET_DATA` snapshot με ρόλο `DISCOVERY` και enforced SHA.
5. Να αντικατασταθούν στο AR-0001 τα pending/legacy snapshot fields και να ανανεωθεί το specification hash.
6. Να ολοκληρωθούν και να εγκριθούν ξεχωριστά οι PHASE 3 statistical implementations.
7. Να δοθεί ρητή έγκριση με `status: APPROVED_TO_RUN` για το ακριβές frozen specification hash.

Μέχρι να ισχύουν όλα, το pipeline αποτυγχάνει πριν από οποιοδήποτε data access ή alpha calculation.
