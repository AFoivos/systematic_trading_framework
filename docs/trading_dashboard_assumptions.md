# Τεχνικές παραδοχές του trading dashboard

Τελευταία ενημέρωση: 2026-07-11

Το dashboard είναι πρόσθετη, local-first επιφάνεια ανάγνωσης. Δεν εισάγει ούτε
εκτελεί το υπάρχον experiment pipeline. Μοναδική ελεγχόμενη εγγραφή είναι η
αποθήκευση layout JSON.

## Ανακάλυψη repository

- Αναζητούνται CSV και Parquet σε όλο το `data/**`.
- Τα datasets ομαδοποιούνται στη διεπαφή σύμφωνα με το directory path.
- Run directory θεωρείται directory κάτω από `logs/experiments/**` ή
  `logs/bot/**` που περιέχει τουλάχιστον ένα από `run_metadata.json`,
  `summary.json`, `artifact_manifest.json` ή `study_summary.json`.
- Container paths που αρχίζουν από `/workspace` αντιστοιχίζονται στο τοπικό
  repository root όταν είναι δυνατό.

## Εξαγωγή asset και timeframe

- Τα raw single-asset filenames μπορούν να δώσουν asset/timeframe, όπως
  `xauusd_h1.csv`, `xauusd_30m.csv` και `XAUUSD_M5_bid.csv`.
- Για processed snapshots προτιμάται το γειτονικό `metadata.json`.
- Το timeframe αναζητείται πρώτα στα metadata και έπειτα στο filename ή στο
  directory name.
- Με `dataset_id` δεν απαιτείται ρητό asset ή timeframe. Αν το dataset δηλώνει
  ακριβώς ένα asset και περιέχει στήλη `asset`, αυτό χρησιμοποιείται ως
  implicit row filter.

Οι παραπάνω κανόνες είναι heuristics ανακάλυψης και δεν αντικαθιστούν canonical
dataset manifests.

## Χρονικά φίλτρα

- Το `start` είναι συμπεριληπτικό.
- Το `end` είναι αποκλειστικό.
- Τα όρια μετατρέπονται σε UTC timestamps πριν από το filtering.

## Κανονικοποίηση στηλών

- Η timestamp στήλη εντοπίζεται case-insensitively μεταξύ `timestamp`,
  `datetime`, `date` και `time`.
- Οι `open`, `high`, `low`, `close` και `volume` κανονικοποιούνται
  case-insensitively.
- Το `/api/ohlcv` απαιτεί και τις πέντε OHLCV στήλες.
- Αριθμητικά epochs ερμηνεύονται ως seconds, milliseconds, microseconds ή
  nanoseconds σύμφωνα με το μέγεθός τους.
- Μετά την κανονικοποίηση, το index ταξινομείται και σε duplicate timestamps
  διατηρείται η τελευταία γραμμή.

## Δυναμικοί κατάλογοι

Οι κατάλογοι στηλών ενός ήδη υπολογισμένου dataset είναι heuristic:

- signal columns: ονόματα με `signal`, `candidate`, `side` ή `position`,
- target columns: ονόματα με `target`, `r_target` ή `label`,
- prediction columns: ονόματα που αρχίζουν από `pred` ή περιέχουν
  `prediction`, `probability` ή `_prob`.

Αντίθετα, οι parameterized builders επιλύονται από τα registries
`src.features.registry`, `src.signals.registry` και `src.targets.registry`.
Το `src.experiments.registry` είναι μόνο facade συμβατότητας.

## Parameterized builders

- Οι builders εφαρμόζονται σε in-memory αντίγραφο και δεν αποθηκεύουν στήλες.
- Η σειρά των steps έχει σημασία: ένα step πρέπει να ακολουθεί όποιο προηγούμενο
  step παράγει τις εισόδους του.
- Τα parameter forms προκύπτουν από Python signatures όπου αυτό είναι ασφαλές.
- Χωρίς date range, το backend υπολογίζει πρώτα ολόκληρη την επιλεγμένη
  ακολουθία και εφαρμόζει έπειτα το όριο επιστρεφόμενων σημείων. Έτσι τα rolling
  features διατηρούν το προγενέστερο context.
- Targets που κοιτούν το μέλλον είναι κατάλληλα μόνο για research preview.
  Δεν αποτελούν διαθέσιμες πληροφορίες στο timestamp απόφασης.

## Αποθήκευση και panels

- Τα layouts αποθηκεύονται κάτω από `apps/trading_dashboard/layouts`.
- Αποθηκεύουν selection state και series configuration, όχι market data.
- Μία lower-panel σειρά χωρίς `panel_id` λαμβάνει ξεχωριστό panel.
- Κοινό μη κενό `panel_id` ομαδοποιεί σειρές στο ίδιο panel.
- Οι `vwap_*` price-level σειρές προβάλλονται συνήθως πάνω στο κύριο chart,
  ενώ αποστάσεις όπως `close_over_vwap_*` παραμένουν σε lower panel.

## Όρια της τρέχουσας διεπαφής

- Το dashboard δεν ξεκινά experiments.
- Απεικονίζει candlesticks, line overlays, lower-panel line/histogram σειρές
  και απλούς trade markers.
- Regime shading, probability bands και ορισμένα πλήρη prediction diagnostics
  υπάρχουν στο schema αλλά δεν αποδίδονται όλα από το frontend.
- Τα inferred catalogs δεν αποτελούν εγγύηση ότι μια στήλη είναι causal ή
  κατάλληλη ως model input.

## Πηγές αλήθειας

- `apps/trading_dashboard/backend/app/services/data_loader.py`
- `apps/trading_dashboard/backend/app/services/schema_mapper.py`
- `apps/trading_dashboard/backend/app/services/experiment_loader.py`
- `apps/trading_dashboard/backend/app/api/routes_*.py`
- `apps/trading_dashboard/backend/app_tests/`
