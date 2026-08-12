# Audit quote/spread contract

## Canonical απόφαση

- `spread_absolute = ask - bid`, unit `price`.
- `spread_fraction = spread_absolute / mid`, unit `fraction`.
- `spread_bps = 10_000 × spread_fraction`, unit `basis_points`.
- `bid <= mid <= ask` και `spread_absolute >= 0` για synchronous quotes.
- Δεν γίνεται inference μονάδας από το μέγεθος ενός αριθμού και δεν γίνεται silent overwrite αντικρουόμενης στήλης.

## Producers που έφεραν την παλιά ασάφεια

- `scripts/prepare_dukascopy_30m_bid_ask_mid.py`: παλιότερα έγραφε fraction στο `spread_bps`. Τώρα παράγει και τις τρεις canonical στήλες και κρατά `spread_close` μόνο ως absolute alias.
- `scripts/prepare_dukascopy_ftmo_mid.py`: είχε το ίδιο σφάλμα και διορθώθηκε με το ίδιο contract.

Και οι δύο producers απορρίπτουν πλέον οποιοδήποτε crossed BID/ASK OHLC field, duplicate side timestamp ή BID/ASK coverage mismatch. Δεν γίνεται silent deduplication, silent inner-join loss ή τεχνητό zero-fill όταν λείπει volume. Το παλιό tolerance argument διατηρείται μόνο για CLI compatibility και δεν επιτρέπει invalid quote output.

## Consumers που απαιτούσαν migration

- `src/features/barrier_state.py`: default spread input από mislabeled `spread_bps` σε explicit `spread_fraction`.
- `src/signals/barrier_expected_value_signal.py`: το `maximum_spread` είναι fraction και πλέον συνδέεται by default με `spread_fraction`.
- `src/features/multi_asset_trend_breakout.py` και τα δύο MATB YAML: το dimensionless spread/median ratio χρησιμοποιεί πλέον explicit `spread_fraction` και `require_spread: true`. Έτσι τα σημερινά legacy αρχεία αποτυγχάνουν ρητά αντί να καταναλώνεται mislabeled `spread_bps` ή να απενεργοποιείται σιωπηρά το spread gate.
- Όλα τα YAML κάτω από `config/experiments/barrier_probability/` που χρησιμοποιούσαν το legacy fraction μεταφέρθηκαν σε `spread_fraction`.
- `config/experiments/eurusd_session_bb_reversion/eurusd_30m_session_bb_reversion_long_only_v1.yaml`: rank και diagnostic feature μεταφέρθηκαν σε `spread_fraction`.
- `src/experiments/orchestration/artifacts.py`: `spread_absolute` και `spread_fraction` δηλώνονται raw market columns ώστε να μη βαφτίζονται engineered features.
- `src/features/systems/common.py`: όταν υπάρχουν bid/ask και supplied `spread_bps`, η στήλη πρέπει να συμφωνεί με τα quotes ως πραγματικά bps. Legacy fraction ή inconsistent τιμή απορρίπτεται.

## Explicit legacy reproduction

Το locked `EURUSD FTMO ML v2` bundle παραμένει ιστορικό reproduction contract. Το συγκεκριμένο reference hash έχει δηλωθεί `REGENERATE_REQUIRED`, `LEGACY_AMBIGUOUS_UNITS`, `research_eligible=false`. Ο loader ταξινομεί ρητά κάθε input ως `CANONICAL_BPS` ή `LEGACY_FRACTION` και απορρίπτει οτιδήποτε ασυνεπές· δεν αλλάζει αριθμητικές τιμές. Canonical data και νέο model contract χρειάζονται νέο dataset/config/model version και δεν υποκαθιστούν σιωπηρά το locked artifact.

## References που είναι ήδη canonical bps

- `src/market_data/order_book.py` και η market-making οικογένεια υπολογίζουν/καταναλώνουν πραγματικά bps.
- `src/features/scalp_microstructure_proxy.py` υπολογίζει `10_000 × spread/mid`.
- Το local cTrader export implementation υπολογίζει πραγματικά bps. Παραμένει ανεξάρτητο user WIP και δεν τροποποιήθηκε από αυτή την εργασία.

## Exhaustive occurrence classification

Το `scripts/audit_quote_contract_references.py` σαρώνει `src`, `scripts`, `config`, `tests`, `apps` και `docs`. Για κάθε occurrence των `spread`, `spread_bps`, `spread_fraction`, `spread_absolute`, `bid`, `ask`, `mid` γράφει path, line, column, token, source text και μία από τις εξής κατηγορίες:

- canonical contract/producer,
- canonical fraction,
- canonical absolute,
- canonical bps ή explicit legacy,
- true-bps market microstructure,
- historical artifact legacy semantics,
- quote price field,
- contextual spread χωρίς implied unit,
- test contract,
- generated catalog reference.

Παράδειγμα μη μεταβαλλόμενου audit artifact:

```bash
python scripts/audit_quote_contract_references.py \
  --root . \
  --output-json /tmp/quote_contract_reference_audit.json
```

Το JSON προορίζεται για review/CI output και όχι για checked-in generated catalog, ώστε η καταγραφή line numbers να μη γίνεται αμέσως stale μετά από κάθε αλλαγή.
