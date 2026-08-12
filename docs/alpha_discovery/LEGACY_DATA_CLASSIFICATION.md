# Legacy data classification

## Απόφαση

Κανένα παλιό dataset ή experiment artifact δεν διαγράφεται και κανένα historical result δεν αναγεννάται σιωπηρά. Η ταξινόμηση αφορά την επιλεξιμότητα για νέο alpha discovery, όχι τη χρησιμότητα ενός artifact για ιστορική αναπαραγωγή ή debugging.

## `REGENERATE_REQUIRED` + `LEGACY_AMBIGUOUS_UNITS`

Τα παρακάτω 15 αρχεία έχουν ελεγχθεί σε όλες τις γραμμές τους. Σε κάθε αρχείο το υφιστάμενο `spread_bps` ισούται με `spread_close / close` (fraction) και δεν ισούται με `10_000 × spread_close / close` (basis points):

- `data/raw/dukascopy_30m_clean/aus200_30m.csv`
- `data/raw/dukascopy_30m_clean/brent_30m.csv`
- `data/raw/dukascopy_30m_clean/ethusd_30m.csv`
- `data/raw/dukascopy_30m_clean/eu50_30m.csv`
- `data/raw/dukascopy_30m_clean/eurusd_30m.csv`
- `data/raw/dukascopy_30m_clean/fra40_30m.csv`
- `data/raw/dukascopy_30m_clean/ger40_30m.csv`
- `data/raw/dukascopy_30m_clean/nikkei225_30m.csv`
- `data/raw/dukascopy_30m_clean/spx500_30m.csv`
- `data/raw/dukascopy_30m_clean/uk100_30m.csv`
- `data/raw/dukascopy_30m_clean/us100_30m.csv`
- `data/raw/dukascopy_30m_clean/us30_30m.csv`
- `data/raw/dukascopy_30m_clean/usoil_30m.csv`
- `data/raw/dukascopy_30m_clean/xagusd_30m.csv`
- `data/raw/dukascopy_30m_clean/xauusd_30m.csv`

Απαιτείται regeneration από τα original BID/ASK inputs. Το αναμενόμενο directory `data/raw/dukascopy_30m/` και τα pre-merge source files δεν υπάρχουν στο checkout. Επομένως δεν μπορεί να επαληθευτεί αναδρομικά το input SHA, το dedup policy ή το BID/ASK inner-join loss.

Το migration script μπορεί να δημιουργήσει μόνο μη καταστροφικό unit-corrected diagnostic copy και sidecar με `research_eligible=false`. Δεν το προάγει σε `VALID`.

## `NOT_RESEARCH_SOURCE`

- Και τα 35 `data/processed/processed/*/dataset.csv` είναι processed experiment datasets. Η ίδια subtree περιέχει 35 `metadata.json` και lock files. Παραμένουν διαθέσιμα τοπικά, αλλά δεν αποτελούν νέα alpha-discovery source data.
- Τα `logs/**`, historical run outputs και `config/experiments/foundation_alpha/best_runs/**` είναι experiment evidence/artifacts, όχι raw immutable market-data snapshots.
- Model bundles, predictions, signals, target/label frames και OOS-marker datasets παραμένουν σε καραντίνα ανεξάρτητα από το αν το αρχείο τους έχει σταθερό hash.

## `VALID` — περιορισμένη έννοια

Το `VALID` αποδίδεται μόνο μετά από επιτυχή quality contract, explicit units/semantics, immutable freeze και SHA enforcement. Το `data/raw/dukascopy_30m_clean/btcusd_1m.csv` δεν περιέχει το λανθασμένο πεδίο και δεν επηρεάζεται από το συγκεκριμένο spread bug, αλλά δεν χαρακτηρίζεται αυτόματα execution-valid επειδή δεν έχει bid/ask quotes.

Τα true-bps order-book/market-making contracts είναι canonical ως προς τη μονάδα τους, αλλά αυτό δεν τα μετατρέπει αυτομάτως σε approved alpha-discovery snapshots.
