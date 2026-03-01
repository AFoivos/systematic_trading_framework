## 4. Ανάλυση Modules

Η παρούσα ενότητα ακολουθεί package-by-package και file-by-file breakdown. Για κάθε αρχείο καταγράφονται ο
σκοπός, οι εισαγωγές, τα global constants, οι κλάσεις, οι συναρτήσεις και τα κυριότερα behavioural
χαρακτηριστικά. Στα μεγάλα modules (`runner.py`, `models.py`, `config.py`) η ανάλυση είναι βαθύτερη, επειδή
αυτά ελέγχουν τη συνολική συμπεριφορά του συστήματος.

### 4.1 Package `src/src_data`

Data ingestion και point-in-time hardening. Εδώ γίνονται provider selection, schema validation, snapshot storage και universe membership checks.

#### Αρχείο `src/src_data/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 34 LOC, 4 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.loaders` εισάγονται `load_ohlcv`, `load_ohlcv_panel`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.validation` εισάγονται `validate_ohlcv`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.pit` εισάγονται `align_ohlcv_timestamps`, `apply_corporate_actions_policy`, `apply_pit_hardening`, `assert_symbol_in_snapshot`, `load_universe_snapshot`, `symbols_active_in_snapshot`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.storage` εισάγονται `asset_frames_to_long_frame`, `long_frame_to_asset_frames`, `build_dataset_snapshot_metadata`, `save_dataset_snapshot`, `load_dataset_snapshot`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/src_data/loaders.py`

**Σκοπός**: Facade για market data providers και panel loading.

**Βασικά Μεγέθη**: 84 LOC, 5 import blocks, 0 global constants, 0 classes, 2 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Literal`, `Optional`, `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.src_data.providers.yahoo` εισάγονται `YahooFinanceProvider`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.src_data.providers.alphavantage` εισάγονται `AlphaVantageFXProvider`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `load_ohlcv`

**Signature**

```python
def load_ohlcv(symbol: str, start: str | None = None, end: str | None = None, interval: str = '1d', source: Literal['yahoo', 'alpha'] = 'yahoo', api_key: Optional[str] = None) -> pd.DataFrame
```

**Περιγραφή**

Parameters

**Παράμετροι**

- `symbol`: `str`. Identifier χρηματοοικονομικού μέσου ή λίστας μέσων.
- `start`: `str | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `end`: `str | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `interval`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'1d'`.
- `source`: `Literal['yahoo', 'alpha']`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'yahoo'`.
- `api_key`: `Optional[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Επιλύει path ή provider parameters.
2. Διαβάζει το εξωτερικό resource και το μετατρέπει στο canonical schema του framework.
3. Επιστρέφει object έτοιμο για τον επόμενο layer consumer.

**Edge Cases**: Μη έγκυρα paths, missing files, empty datasets ή απουσία required columns πρέπει να θεωρούνται expected failure modes.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`, `src.src_data.loaders.load_ohlcv_panel()`.

##### `load_ohlcv_panel`

**Signature**

```python
def load_ohlcv_panel(symbols: Sequence[str], start: str | None = None, end: str | None = None, interval: str = '1d', source: Literal['yahoo', 'alpha'] = 'yahoo', api_key: Optional[str] = None) -> dict[str, pd.DataFrame]
```

**Περιγραφή**

Load OHLCV panel for the data ingestion and storage layer and normalize it into the shape

**Παράμετροι**

- `symbols`: `Sequence[str]`. Identifier χρηματοοικονομικού μέσου ή λίστας μέσων.
- `start`: `str | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `end`: `str | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `interval`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'1d'`.
- `source`: `Literal['yahoo', 'alpha']`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'yahoo'`.
- `api_key`: `Optional[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `dict[str, pd.DataFrame]`.

**Λογική Βήμα-Βήμα**

1. Επιλύει path ή provider parameters.
2. Διαβάζει το εξωτερικό resource και το μετατρέπει στο canonical schema του framework.
3. Επιστρέφει object έτοιμο για τον επόμενο layer consumer.

**Edge Cases**: Μη έγκυρα paths, missing files, empty datasets ή απουσία required columns πρέπει να θεωρούνται expected failure modes.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: O(S * ProviderCost), όπου S=αριθμός symbols. Στην πράξη κυριαρχείται από network latency/API throughput.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`.

#### Αρχείο `src/src_data/pit.py`

**Σκοπός**: Point-in-time hardening layer για timestamp normalization, corporate actions policy και universe snapshot membership checks.

**Βασικά Μεγέθη**: 250 LOC, 6 import blocks, 2 global constants, 0 classes, 7 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pathlib` εισάγονται `Path`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `typing` εισάγονται `Any`, `Iterable`, `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.utils.paths` εισάγονται `PROJECT_ROOT`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- `_ALLOWED_DUPLICATE_POLICIES`: Whitelist ορθών τιμών για validation branches. Τρέχουσα τιμή: `{'first', 'last', 'raise'}`.
- `_ALLOWED_CORP_ACTION_POLICIES`: Whitelist ορθών τιμών για validation branches. Τρέχουσα τιμή: `{'none', 'adj_close_ratio', 'adj_close_replace_close'}`.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `align_ohlcv_timestamps`

**Signature**

```python
def align_ohlcv_timestamps(df: pd.DataFrame, *, source_timezone: str = 'UTC', output_timezone: str = 'UTC', normalize_daily: bool = True, duplicate_policy: str = 'last') -> pd.DataFrame
```

**Περιγραφή**

Handle align OHLCV timestamps inside the data ingestion and storage layer. The helper

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `source_timezone`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'UTC'`.
- `output_timezone`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'UTC'`.
- `normalize_daily`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.
- `duplicate_policy`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'last'`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.src_data.pit.apply_pit_hardening()`, `tests.test_contracts_metrics_pit.test_align_ohlcv_timestamps_sorts_and_deduplicates()`.

##### `apply_corporate_actions_policy`

**Signature**

```python
def apply_corporate_actions_policy(df: pd.DataFrame, *, policy: str = 'none', adj_close_col: str = 'adj_close', price_cols: Iterable[str] = ('open', 'high', 'low', 'close')) -> tuple[pd.DataFrame, dict[str, Any]]
```

**Περιγραφή**

Apply corporate actions policy to the provided inputs in a controlled and reusable way. The

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `policy`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'none'`.
- `adj_close_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'adj_close'`.
- `price_cols`: `Iterable[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `('open', 'high', 'low', 'close')`.

**Return Type**: `tuple[pd.DataFrame, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Κάνει copy ή normalization του input όπου χρειάζεται.
2. Εφαρμόζει μία συγκεκριμένη policy/transformation χωρίς να αναμιγνύει άσχετες ευθύνες.
3. Επιστρέφει transformed object και, όπου απαιτείται, metadata του applied step.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.src_data.pit.apply_pit_hardening()`, `tests.test_contracts_metrics_pit.test_apply_corporate_actions_policy_adj_close_ratio()`.

##### `_resolve_snapshot_path`

**Signature**

```python
def _resolve_snapshot_path(path: str | Path) -> Path
```

**Περιγραφή**

Handle snapshot path inside the data ingestion and storage layer. The helper isolates one

**Παράμετροι**

- `path`: `str | Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `Path`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.src_data.pit.apply_pit_hardening()`, `src.src_data.pit.load_universe_snapshot()`.

##### `load_universe_snapshot`

**Signature**

```python
def load_universe_snapshot(path: str | Path) -> pd.DataFrame
```

**Περιγραφή**

Load universe snapshot for the data ingestion and storage layer and normalize it into the

**Παράμετροι**

- `path`: `str | Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Επιλύει path ή provider parameters.
2. Διαβάζει το εξωτερικό resource και το μετατρέπει στο canonical schema του framework.
3. Επιστρέφει object έτοιμο για τον επόμενο layer consumer.

**Edge Cases**: Μη έγκυρα paths, missing files, empty datasets ή απουσία required columns πρέπει να θεωρούνται expected failure modes.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `FileNotFoundError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.src_data.pit.apply_pit_hardening()`, `tests.test_contracts_metrics_pit.test_universe_snapshot_asof_membership_check()`.

##### `symbols_active_in_snapshot`

**Signature**

```python
def symbols_active_in_snapshot(snapshot_df: pd.DataFrame, as_of: str | pd.Timestamp) -> list[str]
```

**Περιγραφή**

Handle symbols active in snapshot inside the data ingestion and storage layer. The helper

**Παράμετροι**

- `snapshot_df`: `pd.DataFrame`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `as_of`: `str | pd.Timestamp`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `list[str]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.src_data.pit.apply_pit_hardening()`, `src.src_data.pit.assert_symbol_in_snapshot()`.

##### `assert_symbol_in_snapshot`

**Signature**

```python
def assert_symbol_in_snapshot(symbol: str, snapshot_df: pd.DataFrame, *, as_of: str | pd.Timestamp) -> None
```

**Περιγραφή**

Assert symbol in snapshot before the pipeline proceeds. This helper exists to fail loudly

**Παράμετροι**

- `symbol`: `str`. Identifier χρηματοοικονομικού μέσου ή λίστας μέσων.
- `snapshot_df`: `pd.DataFrame`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `as_of`: `str | pd.Timestamp`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Εξάγει την κρίσιμη συνθήκη ασφαλείας ή membership check.
2. Αποτυγχάνει άμεσα όταν η συνθήκη δεν ικανοποιείται ώστε να προστατεύσει downstream βήματα.

**Edge Cases**: Empty inputs, λάθος types, duplicate timestamps και missing required columns είναι συνήθη failure modes που αντιμετωπίζονται με άμεσο exception.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.src_data.pit.apply_pit_hardening()`, `tests.test_contracts_metrics_pit.test_universe_snapshot_asof_membership_check()`.

##### `apply_pit_hardening`

**Signature**

```python
def apply_pit_hardening(df: pd.DataFrame, *, pit_cfg: Mapping[str, Any] | None = None, symbol: str | None = None) -> tuple[pd.DataFrame, dict[str, Any]]
```

**Περιγραφή**

Apply point-in-time (PIT) hardening to the provided inputs in a controlled and reusable way.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `pit_cfg`: `Mapping[str, Any] | None`. Configuration mapping με domain-specific παραμέτρους. Προεπιλογή: `None`.
- `symbol`: `str | None`. Identifier χρηματοοικονομικού μέσου ή λίστας μέσων. Προεπιλογή: `None`.

**Return Type**: `tuple[pd.DataFrame, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Διαβάζει nested PIT config blocks για timestamps, corporate actions και universe snapshot.
2. Ευθυγραμμίζει timestamps σε deterministic timezone/duplicate policy.
3. Εφαρμόζει πολιτική corporate actions είτε μέσω ratio adjustment είτε μέσω replace-close.
4. Προαιρετικά φορτώνει universe snapshot και αποτυγχάνει αν το symbol δεν ανήκει στο universe στο `as_of` date.
5. Επιστρέφει hardened frame μαζί με structured metadata για κάθε PIT υπο-βήμα.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`.

#### Αρχείο `src/src_data/providers/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 9 LOC, 3 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.base` εισάγονται `MarketDataProvider`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.yahoo` εισάγονται `YahooFinanceProvider`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.alphavantage` εισάγονται `AlphaVantageFXProvider`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/src_data/providers/alphavantage.py`

**Σκοπός**: Alpha Vantage FX provider για daily FX series με API-backed HTTP requests.

**Βασικά Μεγέθη**: 86 LOC, 7 import blocks, 0 global constants, 1 classes, 0 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `os` εισάγονται `os`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Literal`, `Optional`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `requests` εισάγονται `requests`. Ρόλος: Εξωτερικό I/O προς market data provider ή HTTP API.
- Από `src.src_data.providers.base` εισάγονται `MarketDataProvider`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `AlphaVantageFXProvider`: βάσεις MarketDataProvider. Lightweight wrapper around Alpha Vantage FX_DAILY endpoint.
  Πεδία:
  - `api_key`: `Optional[str]`. Προεπιλογή: `None`.
  - `outputsize`: `Literal['compact', 'full']`. Προεπιλογή: `'full'`.
  Μέθοδοι: `get_ohlcv`.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/src_data/providers/base.py`

**Σκοπός**: Abstract contract για providers εξωτερικών market data sources.

**Βασικά Μεγέθη**: 24 LOC, 3 import blocks, 0 global constants, 1 classes, 0 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `abc` εισάγονται `ABC`, `abstractmethod`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `MarketDataProvider`: βάσεις ABC. Define the abstract provider interface that every market data backend must implement in
  Μέθοδοι: `get_ohlcv`.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/src_data/providers/yahoo.py`

**Σκοπός**: Yahoo Finance provider με normalization σε project OHLCV schema.

**Βασικά Μεγέθη**: 79 LOC, 5 import blocks, 0 global constants, 1 classes, 0 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `yfinance` εισάγονται `yf`. Ρόλος: Εξωτερικό I/O προς market data provider ή HTTP API.
- Από `src.src_data.providers.base` εισάγονται `MarketDataProvider`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `YahooFinanceProvider`: βάσεις MarketDataProvider. Implement the market data provider contract for Yahoo Finance and normalize the downloaded
  Μέθοδοι: `get_ohlcv`.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/src_data/storage.py`

**Σκοπός**: Persistence layer για raw/processed dataset snapshots σε canonical long format.

**Βασικά Μεγέθη**: 208 LOC, 8 import blocks, 0 global constants, 0 classes, 7 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `json` εισάγονται `json`. Ρόλος: Serialization / configuration parsing.
- Από `datetime` εισάγονται `datetime`, `timezone`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.
- Από `pathlib` εισάγονται `Path`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `typing` εισάγονται `Any`, `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.utils.paths` εισάγονται `PROJECT_ROOT`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.utils.run_metadata` εισάγονται `compute_dataframe_fingerprint`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `_resolve_path`

**Signature**

```python
def _resolve_path(path: str | Path) -> Path
```

**Περιγραφή**

Handle path inside the data ingestion and storage layer. The helper isolates one focused

**Παράμετροι**

- `path`: `str | Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `Path`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.src_data.storage._resolve_snapshot_dir()`, `src.src_data.storage.load_dataset_snapshot()`.

##### `_resolve_snapshot_dir`

**Signature**

```python
def _resolve_snapshot_dir(*, root_dir: str | Path, stage: str, dataset_id: str) -> Path
```

**Περιγραφή**

Handle snapshot dir inside the data ingestion and storage layer. The helper isolates one

**Παράμετροι**

- `root_dir`: `str | Path`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `stage`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `dataset_id`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `Path`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.src_data.storage.load_dataset_snapshot()`, `src.src_data.storage.save_dataset_snapshot()`.

##### `asset_frames_to_long_frame`

**Signature**

```python
def asset_frames_to_long_frame(asset_frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame
```

**Περιγραφή**

Handle asset frames to long frame inside the data ingestion and storage layer. The helper

**Παράμετροι**

- `asset_frames`: `Mapping[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: O(total_rows * total_columns) συν κόστος concatenation across assets.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._data_stats_payload()`, `src.experiments.runner.run_experiment()`, `src.src_data.storage.build_dataset_snapshot_metadata()`, `src.src_data.storage.save_dataset_snapshot()`.

##### `long_frame_to_asset_frames`

**Signature**

```python
def long_frame_to_asset_frames(frame: pd.DataFrame) -> dict[str, pd.DataFrame]
```

**Περιγραφή**

Handle long frame to asset frames inside the data ingestion and storage layer. The helper

**Παράμετροι**

- `frame`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.

**Return Type**: `dict[str, pd.DataFrame]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: O(total_rows) για groupby ανά asset και index reconstruction.

**Πού Καλείται στο Pipeline**: `src.src_data.storage.load_dataset_snapshot()`.

##### `build_dataset_snapshot_metadata`

**Signature**

```python
def build_dataset_snapshot_metadata(asset_frames: Mapping[str, pd.DataFrame], *, dataset_id: str, stage: str, context: Mapping[str, Any] | None = None) -> dict[str, Any]
```

**Περιγραφή**

Build dataset snapshot metadata as an explicit intermediate object used by the data

**Παράμετροι**

- `asset_frames`: `Mapping[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `dataset_id`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `stage`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `context`: `Mapping[str, Any] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Συγκεντρώνει inputs από το ανώτερο orchestration layer.
2. Συνθέτει νέο ενδιάμεσο object ή report με deterministic schema.
3. Επιστρέφει αποτέλεσμα έτοιμο για downstream consumption ή persistence.

**Edge Cases**: Η συνάρτηση υποθέτει ότι τα upstream contracts έχουν ήδη ελεγχθεί, αλλά εξακολουθεί να αποτυγχάνει αν τα inputs είναι κενά ή μη ευθυγραμμισμένα.

**Side Effects**: Εκτυπώνει στο stdout.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.src_data.storage.save_dataset_snapshot()`.

##### `save_dataset_snapshot`

**Signature**

```python
def save_dataset_snapshot(asset_frames: Mapping[str, pd.DataFrame], *, dataset_id: str, stage: str, root_dir: str | Path, context: Mapping[str, Any] | None = None) -> dict[str, Any]
```

**Περιγραφή**

Save dataset snapshot for the data ingestion and storage layer together with the metadata

**Παράμετροι**

- `asset_frames`: `Mapping[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `dataset_id`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `stage`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `root_dir`: `str | Path`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `context`: `Mapping[str, Any] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Επιλύει canonical snapshot directory από stage και dataset id.
2. Μετατρέπει το asset dict σε long canonical frame με columns `timestamp` και `asset`.
3. Αποθηκεύει dataset και metadata σε σταθερή δομή αρχείων CSV/JSON.
4. Επιστρέφει manifest-friendly πληροφορίες διαδρομών και fingerprint.

**Edge Cases**: Μη έγκυρα paths, missing files, empty datasets ή απουσία required columns πρέπει να θεωρούνται expected failure modes.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: O(total_rows * total_columns) συν I/O serialization cost σε CSV/JSON.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`, `src.experiments.runner._save_processed_snapshot_if_enabled()`, `tests.test_runner_extensions.test_dataset_snapshot_roundtrip()`.

##### `load_dataset_snapshot`

**Signature**

```python
def load_dataset_snapshot(*, stage: str, root_dir: str | Path | None = None, dataset_id: str | None = None, load_path: str | Path | None = None) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]
```

**Περιγραφή**

Load dataset snapshot for the data ingestion and storage layer and normalize it into the

**Παράμετροι**

- `stage`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `root_dir`: `str | Path | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `dataset_id`: `str | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `load_path`: `str | Path | None`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving. Προεπιλογή: `None`.

**Return Type**: `tuple[dict[str, pd.DataFrame], dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Επιλύει path ή provider parameters.
2. Διαβάζει το εξωτερικό resource και το μετατρέπει στο canonical schema του framework.
3. Επιστρέφει object έτοιμο για τον επόμενο layer consumer.

**Edge Cases**: Μη έγκυρα paths, missing files, empty datasets ή απουσία required columns πρέπει να θεωρούνται expected failure modes.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: `FileNotFoundError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: O(total_rows * total_columns) συν I/O deserialization cost.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`, `tests.test_runner_extensions.test_dataset_snapshot_roundtrip()`.

#### Αρχείο `src/src_data/validation.py`

**Σκοπός**: Υλοποίηση του module `validation.py` μέσα στο package `src_data`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 57 LOC, 4 import blocks, 0 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Iterable`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `validate_ohlcv`

**Signature**

```python
def validate_ohlcv(df: pd.DataFrame, required_columns: Iterable[str] = ('open', 'high', 'low', 'close', 'volume'), allow_missing_volume: bool = True) -> None
```

**Περιγραφή**

Validate OHLCV before downstream logic depends on it. The function raises early when

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `required_columns`: `Iterable[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `('open', 'high', 'low', 'close', 'volume')`.
- `allow_missing_volume`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει τον τύπο και τα βασικά structural preconditions του input.
2. Συγκεντρώνει violations αντί να προχωρήσει σε downstream logic.
3. Σηκώνει deterministic exception όταν εντοπίζει contract breach ή επιστρέφει lightweight metadata.

**Edge Cases**: Empty inputs, λάθος types, duplicate timestamps και missing required columns είναι συνήθη failure modes που αντιμετωπίζονται με άμεσο exception.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`, `tests.test_core.test_validate_ohlcv_flags_invalid_high_low()`.

### 4.2 Package `src/features`

Feature engineering για returns, lags, volatility και technical indicators. Όλες οι μετασχηματίσεις είναι causal και βασίζονται σε pandas time-series operations.

#### Αρχείο `src/features/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 20 LOC, 4 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.returns` εισάγονται `compute_returns`, `add_close_returns`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.volatility` εισάγονται `compute_rolling_vol`, `compute_ewma_vol`, `add_volatility_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.lags` εισάγονται `add_lagged_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.technical.trend` εισάγονται `compute_sma`, `compute_ema`, `add_trend_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/features/lags.py`

**Σκοπός**: Υλοποίηση του module `lags.py` μέσα στο package `features`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 35 LOC, 3 import blocks, 0 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Iterable`, `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `add_lagged_features`

**Signature**

```python
def add_lagged_features(df: pd.DataFrame, cols: Iterable[str], lags: Sequence[int] = (1, 2, 5), prefix: str = 'lag') -> pd.DataFrame
```

**Περιγραφή**

Add lagged versions of specified columns.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `cols`: `Iterable[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `lags`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(1, 2, 5)`.
- `prefix`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'lag'`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

#### Αρχείο `src/features/returns.py`

**Σκοπός**: Υλοποίηση του module `returns.py` μέσα στο package `features`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 64 LOC, 3 import blocks, 0 global constants, 0 classes, 2 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_returns`

**Signature**

```python
def compute_returns(prices: pd.Series, log: bool = False, dropna: bool = True) -> pd.Series
```

**Περιγραφή**

r_t = P_t / P_{t-1} - 1           (log=False)

**Παράμετροι**

- `prices`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `log`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `False`.
- `dropna`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.features.returns.add_close_returns()`, `tests.test_core.test_compute_returns_simple_and_log()`.

##### `add_close_returns`

**Signature**

```python
def add_close_returns(df: pd.DataFrame, log: bool = False, col_name: str | None = None) -> pd.DataFrame
```

**Περιγραφή**

Parameters

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `log`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `False`.
- `col_name`: `str | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

#### Αρχείο `src/features/volatility.py`

**Σκοπός**: Υλοποίηση του module `volatility.py` μέσα στο package `features`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 100 LOC, 4 import blocks, 0 global constants, 0 classes, 3 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Optional`, `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_rolling_vol`

**Signature**

```python
def compute_rolling_vol(returns: pd.Series, window: int, ddof: int = 1, annualization_factor: Optional[float] = None) -> pd.Series
```

**Περιγραφή**

Rolling realized volatility on a series of returns.

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `ddof`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1`.
- `annualization_factor`: `Optional[float]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.volatility.add_volatility_features()`.

##### `compute_ewma_vol`

**Signature**

```python
def compute_ewma_vol(returns: pd.Series, span: int, annualization_factor: Optional[float] = None) -> pd.Series
```

**Περιγραφή**

EWMA volatility (Exponentially Weighted Moving Std) 

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `span`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `annualization_factor`: `Optional[float]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.volatility.add_volatility_features()`.

##### `add_volatility_features`

**Signature**

```python
def add_volatility_features(df: pd.DataFrame, returns_col: str = 'close_logret', rolling_windows: Sequence[int] = (10, 20, 60), ewma_spans: Sequence[int] = (10, 20), annualization_factor: Optional[float] = 252.0, inplace: bool = False) -> pd.DataFrame
```

**Περιγραφή**

Assumes:

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `returns_col`: `str`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance. Προεπιλογή: `'close_logret'`.
- `rolling_windows`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(10, 20, 60)`.
- `ewma_spans`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(10, 20)`.
- `annualization_factor`: `Optional[float]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252.0`.
- `inplace`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `False`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

### 4.3 Package `src/features/technical`

Package του repository.

#### Αρχείο `src/features/technical/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 55 LOC, 4 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.trend` εισάγονται `compute_sma`, `compute_ema`, `add_trend_features`, `add_trend_regime_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.momentum` εισάγονται `compute_price_momentum`, `compute_return_momentum`, `compute_vol_normalized_momentum`, `add_momentum_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.oscillators` εισάγονται `compute_rsi`, `compute_stoch_k`, `compute_stoch_d`, `add_oscillator_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.indicators` εισάγονται `compute_true_range`, `compute_atr`, `add_bollinger_bands`, `compute_macd`, `compute_ppo`, `compute_roc`, `compute_volume_zscore`, `compute_adx`, `compute_mfi`, `add_indicator_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/features/technical/indicators.py`

**Σκοπός**: Υλοποίηση του module `indicators.py` μέσα στο package `technical`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 239 LOC, 4 import blocks, 0 global constants, 0 classes, 10 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Optional`, `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_true_range`

**Signature**

```python
def compute_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series
```

**Περιγραφή**

True range as max of (high-low, |high-prev_close|, |low-prev_close|).

**Παράμετροι**

- `high`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `low`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.compute_adx()`, `src.features.technical.indicators.compute_atr()`.

##### `compute_atr`

**Signature**

```python
def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14, method: str = 'wilder') -> pd.Series
```

**Περιγραφή**

Average True Range (ATR). method: 'wilder' (EWMA) or 'simple' (SMA).

**Παράμετροι**

- `high`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `low`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `14`.
- `method`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'wilder'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.add_indicator_features()`.

##### `add_bollinger_bands`

**Signature**

```python
def add_bollinger_bands(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.DataFrame
```

**Περιγραφή**

Bollinger bands and derived features: upper, lower, band_width, percent_b.

**Παράμετροι**

- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20`.
- `n_std`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `2.0`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.add_indicator_features()`.

##### `compute_macd`

**Signature**

```python
def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame
```

**Περιγραφή**

MACD line, signal line, histogram.

**Παράμετροι**

- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `fast`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `12`.
- `slow`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `26`.
- `signal`: `int`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `9`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.add_indicator_features()`.

##### `compute_ppo`

**Signature**

```python
def compute_ppo(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame
```

**Περιγραφή**

Percentage Price Oscillator: normalized MACD.

**Παράμετροι**

- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `fast`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `12`.
- `slow`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `26`.
- `signal`: `int`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `9`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.add_indicator_features()`.

##### `compute_roc`

**Signature**

```python
def compute_roc(close: pd.Series, window: int = 10) -> pd.Series
```

**Περιγραφή**

Rate of Change: (P_t / P_{t-w}) - 1.

**Παράμετροι**

- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `10`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.add_indicator_features()`.

##### `compute_volume_zscore`

**Signature**

```python
def compute_volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series
```

**Περιγραφή**

Rolling z-score of volume.

**Παράμετροι**

- `volume`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.add_indicator_features()`.

##### `compute_adx`

**Signature**

```python
def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.DataFrame
```

**Περιγραφή**

ADX with DI+, DI- using Wilder smoothing.

**Παράμετροι**

- `high`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `low`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `14`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.add_indicator_features()`.

##### `compute_mfi`

**Signature**

```python
def compute_mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int = 14) -> pd.Series
```

**Περιγραφή**

Money Flow Index (uses typical price * volume).

**Παράμετροι**

- `high`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `low`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `volume`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `14`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.indicators.add_indicator_features()`.

##### `add_indicator_features`

**Signature**

```python
def add_indicator_features(df: pd.DataFrame, price_col: str = 'close', high_col: str = 'high', low_col: str = 'low', volume_col: str = 'volume', bb_window: int = 20, bb_nstd: float = 2.0, macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9, ppo_fast: int = 12, ppo_slow: int = 26, ppo_signal: int = 9, roc_windows: Sequence[int] = (10, 20), atr_window: int = 14, adx_window: int = 14, vol_z_window: int = 20, include_mfi: bool = True) -> pd.DataFrame
```

**Περιγραφή**

Add a bundle of classic indicators to an OHLCV dataframe.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `price_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'close'`.
- `high_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'high'`.
- `low_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'low'`.
- `volume_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'volume'`.
- `bb_window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20`.
- `bb_nstd`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `2.0`.
- `macd_fast`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `12`.
- `macd_slow`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `26`.
- `macd_signal`: `int`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `9`.
- `ppo_fast`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `12`.
- `ppo_slow`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `26`.
- `ppo_signal`: `int`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `9`.
- `roc_windows`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(10, 20)`.
- `atr_window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `14`.
- `adx_window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `14`.
- `vol_z_window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20`.
- `include_mfi`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

#### Αρχείο `src/features/technical/momentum.py`

**Σκοπός**: Υλοποίηση του module `momentum.py` μέσα στο package `technical`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 93 LOC, 4 import blocks, 0 global constants, 0 classes, 4 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Sequence`, `Optional`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_price_momentum`

**Signature**

```python
def compute_price_momentum(prices: pd.Series, window: int) -> pd.Series
```

**Περιγραφή**

Price momentum: P_t / P_{t-window} - 1

**Παράμετροι**

- `prices`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.features.technical.momentum.add_momentum_features()`.

##### `compute_return_momentum`

**Signature**

```python
def compute_return_momentum(returns: pd.Series, window: int) -> pd.Series
```

**Περιγραφή**

Return-based momentum: sum of returns over window.

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.momentum.add_momentum_features()`.

##### `compute_vol_normalized_momentum`

**Signature**

```python
def compute_vol_normalized_momentum(returns: pd.Series, volatility: pd.Series, window: int, eps: float = 1e-08) -> pd.Series
```

**Περιγραφή**

Volatility-normalized momentum:

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `volatility`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `eps`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1e-08`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.momentum.add_momentum_features()`.

##### `add_momentum_features`

**Signature**

```python
def add_momentum_features(df: pd.DataFrame, price_col: str = 'close', returns_col: str = 'close_logret', vol_col: Optional[str] = 'vol_rolling_20', windows: Sequence[int] = (5, 20, 60), inplace: bool = False) -> pd.DataFrame
```

**Περιγραφή**

Προσθέτει momentum features:

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `price_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'close'`.
- `returns_col`: `str`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance. Προεπιλογή: `'close_logret'`.
- `vol_col`: `Optional[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'vol_rolling_20'`.
- `windows`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(5, 20, 60)`.
- `inplace`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `False`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

#### Αρχείο `src/features/technical/oscillators.py`

**Σκοπός**: Υλοποίηση του module `oscillators.py` μέσα στο package `technical`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 122 LOC, 4 import blocks, 0 global constants, 0 classes, 4 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Optional`, `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_rsi`

**Signature**

```python
def compute_rsi(prices: pd.Series, window: int = 14, method: str = 'wilder') -> pd.Series
```

**Περιγραφή**

RSI (Relative Strength Index).

**Παράμετροι**

- `prices`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `14`.
- `method`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'wilder'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.oscillators.add_oscillator_features()`.

##### `compute_stoch_k`

**Signature**

```python
def compute_stoch_k(close: pd.Series, high: pd.Series, low: pd.Series, window: int = 14) -> pd.Series
```

**Περιγραφή**

Stochastic %K:

**Παράμετροι**

- `close`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `high`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `low`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `14`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.oscillators.add_oscillator_features()`.

##### `compute_stoch_d`

**Signature**

```python
def compute_stoch_d(k: pd.Series, smooth: int = 3) -> pd.Series
```

**Περιγραφή**

Stochastic %D: moving average του %K.

**Παράμετροι**

- `k`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `smooth`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `3`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.oscillators.add_oscillator_features()`.

##### `add_oscillator_features`

**Signature**

```python
def add_oscillator_features(df: pd.DataFrame, price_col: str = 'close', high_col: str = 'high', low_col: str = 'low', rsi_windows: Sequence[int] = (14,), stoch_windows: Sequence[int] = (14,), stoch_smooth: int = 3, inplace: bool = False) -> pd.DataFrame
```

**Περιγραφή**

Features:

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `price_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'close'`.
- `high_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'high'`.
- `low_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'low'`.
- `rsi_windows`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(14,)`.
- `stoch_windows`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(14,)`.
- `stoch_smooth`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `3`.
- `inplace`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `False`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

#### Αρχείο `src/features/technical/trend.py`

**Σκοπός**: Υλοποίηση του module `trend.py` μέσα στο package `technical`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 190 LOC, 4 import blocks, 0 global constants, 0 classes, 4 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Optional`, `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_sma`

**Signature**

```python
def compute_sma(prices: pd.Series, window: int, min_periods: Optional[int] = None) -> pd.Series
```

**Περιγραφή**

Simple Moving Average (SMA) .

**Παράμετροι**

- `prices`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `min_periods`: `Optional[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.trend.add_trend_features()`.

##### `compute_ema`

**Signature**

```python
def compute_ema(prices: pd.Series, span: int, adjust: bool = False) -> pd.Series
```

**Περιγραφή**

Exponential Moving Average (EMA) .

**Παράμετροι**

- `prices`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `span`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `adjust`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `False`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.features.technical.trend.add_trend_features()`.

##### `add_trend_features`

**Signature**

```python
def add_trend_features(df: pd.DataFrame, price_col: str = 'close', sma_windows: Sequence[int] = (20, 50, 200), ema_spans: Sequence[int] = (20, 50), inplace: bool = False) -> pd.DataFrame
```

**Περιγραφή**

Προσθέτει βασικά trend features σε OHLCV DataFrame.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `price_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'close'`.
- `sma_windows`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(20, 50, 200)`.
- `ema_spans`: `Sequence[int]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `(20, 50)`.
- `inplace`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `False`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `tests.test_core.test_add_trend_features_columns()`.

##### `add_trend_regime_features`

**Signature**

```python
def add_trend_regime_features(df: pd.DataFrame, price_col: str = 'close', base_sma_for_sign: int = 50, short_sma: int = 20, long_sma: int = 50, inplace: bool = False) -> pd.DataFrame
```

**Περιγραφή**

trend "regime" features based on MAs.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `price_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'close'`.
- `base_sma_for_sign`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `50`.
- `short_sma`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20`.
- `long_sma`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `50`.
- `inplace`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `False`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει ότι οι απαιτούμενες input στήλες υπάρχουν.
2. Υπολογίζει derived features με causal transformations.
3. Προσθέτει τις νέες στήλες σε αντίγραφο του DataFrame και το επιστρέφει.

**Edge Cases**: Αν λείπουν prerequisite columns ή το διαθέσιμο history είναι μικρότερο από το lookback, οι πρώτες γραμμές παραμένουν NaN ή το function σηκώνει `KeyError`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

### 4.4 Package `src/signals`

Primitive signal builders που μετατρέπουν features ή model probabilities σε directional ή sized exposures.

#### Αρχείο `src/signals/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 13 LOC, 5 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.rsi_signal` εισάγονται `compute_rsi_signal`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.trend_signal` εισάγονται `compute_trend_state_signal`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.momentum_signal` εισάγονται `compute_momentum_signal`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.stochastic_signal` εισάγονται `compute_stochastic_signal`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.volatility_signal` εισάγονται `compute_volatility_regime_signal`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/signals/momentum_signal.py`

**Σκοπός**: Υλοποίηση του module `momentum_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 40 LOC, 2 import blocks, 1 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- `_ALLOWED_MODES`: Whitelist ορθών τιμών για validation branches. Τρέχουσα τιμή: `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_momentum_signal`

**Signature**

```python
def compute_momentum_signal(df: pd.DataFrame, momentum_col: str, long_threshold: float = 0.0, short_threshold: float | None = None, signal_col: str = 'momentum_signal', mode: str = 'long_short_hold') -> pd.DataFrame
```

**Περιγραφή**

Momentum signal from a precomputed momentum column.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `momentum_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `long_threshold`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `short_threshold`: `float | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'momentum_signal'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.backtesting.strategies.momentum_strategy()`.

#### Αρχείο `src/signals/rsi_signal.py`

**Σκοπός**: Υλοποίηση του module `rsi_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 35 LOC, 2 import blocks, 1 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- `_ALLOWED_MODES`: Whitelist ορθών τιμών για validation branches. Τρέχουσα τιμή: `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_rsi_signal`

**Signature**

```python
def compute_rsi_signal(df: pd.DataFrame, rsi_col: str, buy_level: float, sell_level: float, signal_col: str = 'rsi_signal', mode: str = 'long_short_hold') -> pd.DataFrame
```

**Περιγραφή**

Compute RSI signal for the signal generation layer. The helper keeps the calculation

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `rsi_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `buy_level`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `sell_level`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'rsi_signal'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.backtesting.strategies.rsi_strategy()`.

#### Αρχείο `src/signals/stochastic_signal.py`

**Σκοπός**: Υλοποίηση του module `stochastic_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 38 LOC, 2 import blocks, 1 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- `_ALLOWED_MODES`: Whitelist ορθών τιμών για validation branches. Τρέχουσα τιμή: `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_stochastic_signal`

**Signature**

```python
def compute_stochastic_signal(df: pd.DataFrame, k_col: str, buy_level: float = 20.0, sell_level: float = 80.0, signal_col: str = 'stochastic_signal', mode: str = 'long_short_hold') -> pd.DataFrame
```

**Περιγραφή**

Stochastic signal from %K.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `k_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `buy_level`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20.0`.
- `sell_level`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `80.0`.
- `signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'stochastic_signal'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.backtesting.strategies.stochastic_strategy()`.

#### Αρχείο `src/signals/trend_signal.py`

**Σκοπός**: Υλοποίηση του module `trend_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 36 LOC, 2 import blocks, 1 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- `_ALLOWED_MODES`: Whitelist ορθών τιμών για validation branches. Τρέχουσα τιμή: `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_trend_state_signal`

**Signature**

```python
def compute_trend_state_signal(df: pd.DataFrame, state_col: str, signal_col: str = 'trend_state_signal', long_value: float = 1.0, flat_value: float = 0.0, short_value: float = -1.0, mode: str = 'long_short_hold') -> pd.DataFrame
```

**Περιγραφή**

Long-only signal based on a trend state column.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `state_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'trend_state_signal'`.
- `long_value`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1.0`.
- `flat_value`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `short_value`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `-1.0`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.backtesting.strategies.trend_state_signal()`.

#### Αρχείο `src/signals/volatility_signal.py`

**Σκοπός**: Υλοποίηση του module `volatility_signal.py` μέσα στο package `signals`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 46 LOC, 2 import blocks, 1 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- `_ALLOWED_MODES`: Whitelist ορθών τιμών για validation branches. Τρέχουσα τιμή: `{'long_only', 'short_only', 'long_short', 'long_short_hold'}`.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_volatility_regime_signal`

**Signature**

```python
def compute_volatility_regime_signal(df: pd.DataFrame, vol_col: str, quantile: float = 0.5, signal_col: str = 'volatility_regime_signal', mode: str = 'long_short_hold', causal: bool = True) -> pd.DataFrame
```

**Περιγραφή**

Long when volatility is at or below the specified quantile,

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `vol_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `quantile`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.5`.
- `signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'volatility_regime_signal'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.
- `causal`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `src.backtesting.strategies.volatility_regime_strategy()`, `tests.test_core.test_volatility_regime_signal_is_causal_by_default()`.

### 4.5 Package `src/backtesting`

Vectorized single-asset backtesting και strategy wrappers γύρω από τα signal primitives.

#### Αρχείο `src/backtesting/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 22 LOC, 2 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.engine` εισάγονται `run_backtest`, `BacktestResult`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.strategies` εισάγονται `buy_and_hold_signal`, `trend_state_long_only_signal`, `trend_state_signal`, `rsi_strategy`, `momentum_strategy`, `stochastic_strategy`, `volatility_regime_strategy`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/backtesting/engine.py`

**Σκοπός**: Single-asset vectorized backtest engine με cost model, vol targeting και drawdown cooloff guard.

**Βασικά Μεγέθη**: 115 LOC, 8 import blocks, 0 global constants, 1 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Literal`, `Optional`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.evaluation.metrics` εισάγονται `compute_backtest_metrics`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.risk.controls` εισάγονται `drawdown_cooloff_multiplier`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.risk.position_sizing` εισάγονται `scale_signal_by_vol`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `BacktestResult`: βάσεις χωρίς explicit base classes. Store the complete result of a single-asset backtest, including returns, positions, costs,
  Πεδία:
  - `equity_curve`: `pd.Series`.
  - `returns`: `pd.Series`.
  - `gross_returns`: `pd.Series`.
  - `costs`: `pd.Series`.
  - `positions`: `pd.Series`.
  - `turnover`: `pd.Series`.
  - `summary`: `dict`.

**Functions**

##### `run_backtest`

**Signature**

```python
def run_backtest(df: pd.DataFrame, signal_col: str, returns_col: str, returns_type: Literal['simple', 'log'] = 'simple', cost_per_unit_turnover: float = 0.0, slippage_per_unit_turnover: float = 0.0, target_vol: Optional[float] = None, vol_col: Optional[str] = None, max_leverage: float = 3.0, dd_guard: bool = True, max_drawdown: float = 0.2, cooloff_bars: int = 20, periods_per_year: int = 252) -> BacktestResult
```

**Περιγραφή**

Simple vectorized backtest with optional vol targeting, slippage, and drawdown guard.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης.
- `returns_col`: `str`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `returns_type`: `Literal['simple', 'log']`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance. Προεπιλογή: `'simple'`.
- `cost_per_unit_turnover`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `slippage_per_unit_turnover`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `target_vol`: `Optional[float]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `vol_col`: `Optional[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `max_leverage`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `3.0`.
- `dd_guard`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.
- `max_drawdown`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.2`.
- `cooloff_bars`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20`.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.

**Return Type**: `BacktestResult`.

**Λογική Βήμα-Βήμα**

1. Επικυρώνει ότι signal και returns columns υπάρχουν στο input frame.
2. Μετατρέπει log returns σε simple returns όταν χρειάζεται για σωστή PnL λογιστική.
3. Χτίζει θέσεις από signal και προαιρετικά εφαρμόζει vol targeting μέσω ex-ante volatility column.
4. Υπολογίζει turnover από μεταβολή θέσεων, explicit costs/slippage και gross strategy returns με μία περίοδο lag.
5. Αν το drawdown guard είναι ενεργό, επανυπολογίζει exposure με cooloff multiplier μετά από breach.
6. Κατασκευάζει equity curve και summary metrics μέσω της evaluation layer.
7. Επιστρέφει `BacktestResult` με όλες τις χρονοσειρές που χρειάζονται diagnostics και persistence.

**Edge Cases**: Simple returns κάτω από -100% θεωρούνται invalid upstream. Το initial turnover χρεώνεται στην πρώτη εγγραφή, άρα η equity curve ξεκινά ήδη cost-adjusted.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: O(N) vectorized σε pandas/NumPy, με ένα επιπλέον O(N) pass αν ενεργοποιηθεί drawdown cooloff.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_single_asset_backtest()`, `tests.test_core.test_run_backtest_charges_initial_entry_turnover()`, `tests.test_core.test_run_backtest_costs_and_slippage_reduce_returns()`, `tests.test_core.test_run_backtest_log_returns_are_converted()`.

#### Αρχείο `src/backtesting/strategies.py`

**Σκοπός**: Υλοποίηση του module `strategies.py` μέσα στο package `backtesting`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 225 LOC, 4 import blocks, 0 global constants, 0 classes, 11 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.signals` εισάγονται `compute_momentum_signal`, `compute_rsi_signal`, `compute_stochastic_signal`, `compute_trend_state_signal`, `compute_volatility_regime_signal`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.risk.position_sizing` εισάγονται `scale_signal_by_vol`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `buy_and_hold_signal`

**Signature**

```python
def buy_and_hold_signal(df: pd.DataFrame, signal_name: str = 'signal_bh') -> pd.Series
```

**Περιγραφή**

Long-only buy-and-hold signal.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_bh'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `trend_state_long_only_signal`

**Signature**

```python
def trend_state_long_only_signal(df: pd.DataFrame, state_col: str, signal_name: str = 'signal_trend_state_long_only') -> pd.Series
```

**Περιγραφή**

Long-only signal based on a trend state column (expects 1 for bull).

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `state_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_trend_state_long_only'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `trend_state_signal`

**Signature**

```python
def trend_state_signal(df: pd.DataFrame, state_col: str, signal_name: str = 'signal_trend_state', mode: str = 'long_short_hold') -> pd.Series
```

**Περιγραφή**

Trend-state strategy wrapper (supports long/short/hold modes).

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `state_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_trend_state'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `rsi_strategy`

**Signature**

```python
def rsi_strategy(df: pd.DataFrame, rsi_col: str, buy_level: float = 30.0, sell_level: float = 70.0, signal_name: str = 'signal_rsi', mode: str = 'long_short_hold') -> pd.Series
```

**Περιγραφή**

RSI strategy wrapper (supports long/short/hold modes).

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `rsi_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `buy_level`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `30.0`.
- `sell_level`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `70.0`.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_rsi'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `momentum_strategy`

**Signature**

```python
def momentum_strategy(df: pd.DataFrame, momentum_col: str, long_threshold: float = 0.0, short_threshold: float | None = None, signal_name: str = 'signal_momentum', mode: str = 'long_short_hold') -> pd.Series
```

**Περιγραφή**

Momentum strategy wrapper (supports long/short/hold modes).

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `momentum_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `long_threshold`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `short_threshold`: `float | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_momentum'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `stochastic_strategy`

**Signature**

```python
def stochastic_strategy(df: pd.DataFrame, k_col: str, buy_level: float = 20.0, sell_level: float = 80.0, signal_name: str = 'signal_stochastic', mode: str = 'long_short_hold') -> pd.Series
```

**Περιγραφή**

Stochastic %K strategy wrapper (supports long/short/hold modes).

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `k_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `buy_level`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20.0`.
- `sell_level`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `80.0`.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_stochastic'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `volatility_regime_strategy`

**Signature**

```python
def volatility_regime_strategy(df: pd.DataFrame, vol_col: str, quantile: float = 0.5, signal_name: str = 'signal_volatility_regime', mode: str = 'long_short_hold') -> pd.Series
```

**Περιγραφή**

Volatility regime strategy wrapper (supports long/short/hold modes).

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `vol_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `quantile`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.5`.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_volatility_regime'`.
- `mode`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'long_short_hold'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `probabilistic_signal`

**Signature**

```python
def probabilistic_signal(df: pd.DataFrame, prob_col: str, signal_name: str = 'signal_prob', upper: float = 0.55, lower: float = 0.45) -> pd.Series
```

**Περιγραφή**

Map probability forecasts to {-1,0,1} signal with dead-zone.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `prob_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_prob'`.
- `upper`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.55`.
- `lower`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.45`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `conviction_sizing_signal`

**Signature**

```python
def conviction_sizing_signal(df: pd.DataFrame, prob_col: str, signal_name: str = 'signal_prob_size', clip: float = 1.0) -> pd.Series
```

**Περιγραφή**

Linear map prob∈[0,1] to exposure∈[-clip, clip]:

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `prob_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_prob_size'`.
- `clip`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1.0`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `regime_filtered_signal`

**Signature**

```python
def regime_filtered_signal(df: pd.DataFrame, base_signal_col: str, regime_col: str, signal_name: str = 'signal_regime_filtered', active_value: float = 1.0) -> pd.Series
```

**Περιγραφή**

Keep base signal only when regime_col == active_value (else 0).

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `base_signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης.
- `regime_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_regime_filtered'`.
- `active_value`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1.0`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `vol_targeted_signal`

**Signature**

```python
def vol_targeted_signal(df: pd.DataFrame, signal_col: str, vol_col: str, target_vol: float, max_leverage: float = 3.0, signal_name: str = 'signal_vol_tgt') -> pd.Series
```

**Περιγραφή**

Scale signal by volatility targeting using scale_signal_by_vol.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης.
- `vol_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `target_vol`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `max_leverage`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `3.0`.
- `signal_name`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_vol_tgt'`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

### 4.6 Package `src/evaluation`

Chronological splitting και metric computation για OOS evaluation με anti-leakage guarantees.

#### Αρχείο `src/evaluation/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 47 LOC, 2 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.time_splits` εισάγονται `TimeSplit`, `assert_no_forward_label_leakage`, `build_time_splits`, `purged_walk_forward_split_indices`, `time_split_indices`, `trim_train_indices_for_horizon`, `walk_forward_split_indices`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.metrics` εισάγονται `annualized_return`, `annualized_volatility`, `calmar_ratio`, `compute_backtest_metrics`, `cost_attribution`, `downside_volatility`, `equity_curve_from_returns`, `hit_rate`, `max_drawdown`, `profit_factor`, `sharpe_ratio`, `sortino_ratio`, `turnover_stats`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/evaluation/metrics.py`

**Σκοπός**: Performance metrics layer για returns, risk, turnover και cost attribution.

**Βασικά Μεγέθη**: 280 LOC, 4 import blocks, 0 global constants, 0 classes, 14 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `equity_curve_from_returns`

**Signature**

```python
def equity_curve_from_returns(returns: pd.Series) -> pd.Series
```

**Περιγραφή**

Handle equity curve from returns inside the evaluation layer. The helper isolates one

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.calmar_ratio()`, `src.evaluation.metrics.compute_backtest_metrics()`.

##### `max_drawdown`

**Signature**

```python
def max_drawdown(equity: pd.Series) -> float
```

**Περιγραφή**

Handle max drawdown inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `equity`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.calmar_ratio()`, `src.evaluation.metrics.compute_backtest_metrics()`.

##### `annualized_return`

**Signature**

```python
def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float
```

**Περιγραφή**

Handle annualized return inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.calmar_ratio()`, `src.evaluation.metrics.compute_backtest_metrics()`, `src.evaluation.metrics.sharpe_ratio()`, `src.evaluation.metrics.sortino_ratio()`.

##### `annualized_volatility`

**Signature**

```python
def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float
```

**Περιγραφή**

Handle annualized volatility inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.compute_backtest_metrics()`, `src.evaluation.metrics.sharpe_ratio()`.

##### `sharpe_ratio`

**Signature**

```python
def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252) -> float
```

**Περιγραφή**

Handle sharpe ratio inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.compute_backtest_metrics()`.

##### `downside_volatility`

**Signature**

```python
def downside_volatility(returns: pd.Series, periods_per_year: int = 252, minimum_acceptable_return: float = 0.0) -> float
```

**Περιγραφή**

Handle downside volatility inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.
- `minimum_acceptable_return`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.sortino_ratio()`.

##### `sortino_ratio`

**Signature**

```python
def sortino_ratio(returns: pd.Series, periods_per_year: int = 252, minimum_acceptable_return: float = 0.0) -> float
```

**Περιγραφή**

Handle sortino ratio inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.
- `minimum_acceptable_return`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.compute_backtest_metrics()`.

##### `calmar_ratio`

**Signature**

```python
def calmar_ratio(returns: pd.Series, periods_per_year: int = 252) -> float
```

**Περιγραφή**

Handle calmar ratio inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.compute_backtest_metrics()`.

##### `profit_factor`

**Signature**

```python
def profit_factor(returns: pd.Series) -> float
```

**Περιγραφή**

Handle profit factor inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.compute_backtest_metrics()`.

##### `hit_rate`

**Signature**

```python
def hit_rate(returns: pd.Series) -> float
```

**Περιγραφή**

Handle hit rate inside the evaluation layer. The helper isolates one focused responsibility

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.compute_backtest_metrics()`.

##### `turnover_stats`

**Signature**

```python
def turnover_stats(turnover: pd.Series | None) -> dict[str, float]
```

**Περιγραφή**

Handle turnover stats inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `turnover`: `pd.Series | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, float]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.compute_backtest_metrics()`.

##### `cost_attribution`

**Signature**

```python
def cost_attribution(*, net_returns: pd.Series, gross_returns: pd.Series | None, costs: pd.Series | None) -> dict[str, float]
```

**Περιγραφή**

Handle cost attribution inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `net_returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `gross_returns`: `pd.Series | None`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `costs`: `pd.Series | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, float]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.metrics.compute_backtest_metrics()`.

##### `compute_backtest_metrics`

**Signature**

```python
def compute_backtest_metrics(*, net_returns: pd.Series, periods_per_year: int = 252, turnover: pd.Series | None = None, costs: pd.Series | None = None, gross_returns: pd.Series | None = None) -> dict[str, float]
```

**Περιγραφή**

Compute backtest metrics for the evaluation layer. The helper keeps the calculation isolated

**Παράμετροι**

- `net_returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.
- `turnover`: `pd.Series | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `costs`: `pd.Series | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `gross_returns`: `pd.Series | None`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance. Προεπιλογή: `None`.

**Return Type**: `dict[str, float]`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.backtesting.engine.run_backtest()`, `src.experiments.runner._compute_subset_metrics()`, `src.portfolio.construction.compute_portfolio_performance()`, `tests.test_contracts_metrics_pit.test_metrics_suite_includes_risk_and_cost_attribution()`.

##### `merge_metric_overrides`

**Signature**

```python
def merge_metric_overrides(base_metrics: Mapping[str, float], overrides: Mapping[str, float] | None) -> dict[str, float]
```

**Περιγραφή**

Merge metric overrides into one consolidated structure for the evaluation layer. The helper

**Παράμετροι**

- `base_metrics`: `Mapping[str, float]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `overrides`: `Mapping[str, float] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, float]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

#### Αρχείο `src/evaluation/time_splits.py`

**Σκοπός**: Time-aware split generator με support για simple time split, walk-forward και purged walk-forward.

**Βασικά Μεγέθη**: 293 LOC, 4 import blocks, 0 global constants, 1 classes, 8 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Literal`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `TimeSplit`: βάσεις χωρίς explicit base classes. Represent one chronological train/test fold with both scalar boundaries and the exact numpy
  Πεδία:
  - `fold`: `int`.
  - `train_start`: `int`.
  - `train_end`: `int`.
  - `test_start`: `int`.
  - `test_end`: `int`.
  - `train_idx`: `np.ndarray`.
  - `test_idx`: `np.ndarray`.

**Functions**

##### `_require_positive_int`

**Signature**

```python
def _require_positive_int(name: str, value: int) -> None
```

**Περιγραφή**

Handle require positive int inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `name`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `value`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.time_splits.assert_no_forward_label_leakage()`, `src.evaluation.time_splits.purged_walk_forward_split_indices()`, `src.evaluation.time_splits.trim_train_indices_for_horizon()`.

##### `_require_non_negative_int`

**Signature**

```python
def _require_non_negative_int(name: str, value: int) -> None
```

**Περιγραφή**

Handle require non negative int inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `name`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `value`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.time_splits.purged_walk_forward_split_indices()`.

##### `time_split_indices`

**Signature**

```python
def time_split_indices(n_samples: int, train_frac: float = 0.7) -> list[TimeSplit]
```

**Περιγραφή**

Handle time split indices inside the evaluation layer. The helper isolates one focused

**Παράμετροι**

- `n_samples`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `train_frac`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.7`.

**Return Type**: `list[TimeSplit]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.time_splits.build_time_splits()`.

##### `walk_forward_split_indices`

**Signature**

```python
def walk_forward_split_indices(n_samples: int, train_size: int, test_size: int, step_size: int | None = None, expanding: bool = True, max_folds: int | None = None) -> list[TimeSplit]
```

**Περιγραφή**

Handle walk forward split indices inside the evaluation layer. The helper isolates one

**Παράμετροι**

- `n_samples`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `train_size`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `test_size`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `step_size`: `int | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `expanding`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.
- `max_folds`: `int | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `list[TimeSplit]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.evaluation.time_splits.build_time_splits()`, `tests.test_time_splits.test_walk_forward_splits_are_time_ordered_and_non_overlapping()`.

##### `purged_walk_forward_split_indices`

**Signature**

```python
def purged_walk_forward_split_indices(n_samples: int, train_size: int, test_size: int, step_size: int | None = None, purge_bars: int = 0, embargo_bars: int = 0, expanding: bool = True, max_folds: int | None = None) -> list[TimeSplit]
```

**Περιγραφή**

Handle purged walk forward split indices inside the evaluation layer. The helper isolates

**Παράμετροι**

- `n_samples`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `train_size`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `test_size`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `step_size`: `int | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `purge_bars`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0`.
- `embargo_bars`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0`.
- `expanding`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.
- `max_folds`: `int | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `list[TimeSplit]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: O(Folds + N) για την παραγωγή index ranges, αμελητέο σε σχέση με training.

**Πού Καλείται στο Pipeline**: `src.evaluation.time_splits.build_time_splits()`, `src.evaluation.time_splits.walk_forward_split_indices()`, `tests.test_time_splits.test_purged_walk_forward_respects_purge_and_embargo()`.

##### `trim_train_indices_for_horizon`

**Signature**

```python
def trim_train_indices_for_horizon(train_idx: np.ndarray, test_start: int, target_horizon: int) -> np.ndarray
```

**Περιγραφή**

Trim training indices so forward-looking labels cannot overlap the test window.

**Παράμετροι**

- `train_idx`: `np.ndarray`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `test_start`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `target_horizon`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `np.ndarray`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`.

##### `assert_no_forward_label_leakage`

**Signature**

```python
def assert_no_forward_label_leakage(train_idx: np.ndarray, test_start: int, target_horizon: int) -> None
```

**Περιγραφή**

Ensure train indices are safe for forward labels of length ``target_horizon``.

**Παράμετροι**

- `train_idx`: `np.ndarray`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `test_start`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `target_horizon`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Εξάγει την κρίσιμη συνθήκη ασφαλείας ή membership check.
2. Αποτυγχάνει άμεσα όταν η συνθήκη δεν ικανοποιείται ώστε να προστατεύσει downstream βήματα.

**Edge Cases**: Empty inputs, λάθος types, duplicate timestamps και missing required columns είναι συνήθη failure modes που αντιμετωπίζονται με άμεσο exception.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`.

##### `build_time_splits`

**Signature**

```python
def build_time_splits(*, method: Literal['time', 'walk_forward', 'purged'], n_samples: int, split_cfg: dict, target_horizon: int = 1) -> list[TimeSplit]
```

**Περιγραφή**

Build time splits as an explicit intermediate object used by the evaluation pipeline.

**Παράμετροι**

- `method`: `Literal['time', 'walk_forward', 'purged']`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `n_samples`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `split_cfg`: `dict`. Configuration mapping με domain-specific παραμέτρους.
- `target_horizon`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1`.

**Return Type**: `list[TimeSplit]`.

**Λογική Βήμα-Βήμα**

1. Επιλέγει στρατηγική split με βάση το `method` του config.
2. Μετατρέπει train fraction σε absolute train size όταν απαιτείται.
3. Παίρνει υπόψη το target horizon ώστε το default purge να είναι τουλάχιστον ίσο με το horizon.
4. Επιστρέφει λίστα `TimeSplit` objects που περιγράφουν ακριβώς train/test index ranges.

**Edge Cases**: Για purged splits επιβάλλει `purge_bars >= target_horizon`, άρα misconfigured config απορρίπτεται αντί να επιτραπεί σιωπηλό leakage.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`, `tests.test_time_splits.test_build_time_splits_uses_target_horizon_for_default_purge()`.

### 4.7 Package `src/risk`

Position sizing και drawdown-based exposure control.

#### Αρχείο `src/risk/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 9 LOC, 2 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.position_sizing` εισάγονται `compute_vol_target_leverage`, `scale_signal_by_vol`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.controls` εισάγονται `compute_drawdown`, `drawdown_cooloff_multiplier`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/risk/controls.py`

**Σκοπός**: Υλοποίηση του module `controls.py` μέσα στο package `risk`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 50 LOC, 2 import blocks, 0 global constants, 0 classes, 2 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_drawdown`

**Signature**

```python
def compute_drawdown(equity: pd.Series) -> pd.Series
```

**Περιγραφή**

Drawdown series from an equity curve.

**Παράμετροι**

- `equity`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.risk.controls.drawdown_cooloff_multiplier()`.

##### `drawdown_cooloff_multiplier`

**Signature**

```python
def drawdown_cooloff_multiplier(equity: pd.Series, max_drawdown: float = 0.2, cooloff_bars: int = 20, min_exposure: float = 0.0) -> pd.Series
```

**Περιγραφή**

When drawdown exceeds max_drawdown, reduce exposure to min_exposure

**Παράμετροι**

- `equity`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `max_drawdown`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.2`.
- `cooloff_bars`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `20`.
- `min_exposure`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.backtesting.engine.run_backtest()`.

#### Αρχείο `src/risk/position_sizing.py`

**Σκοπός**: Υλοποίηση του module `position_sizing.py` μέσα στο package `risk`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 54 LOC, 4 import blocks, 0 global constants, 0 classes, 2 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Optional`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `compute_vol_target_leverage`

**Signature**

```python
def compute_vol_target_leverage(vol: pd.Series, target_vol: float, max_leverage: float = 3.0, min_leverage: float = 0.0, eps: float = 1e-08) -> pd.Series
```

**Περιγραφή**

Compute leverage to target a given volatility level.

**Παράμετροι**

- `vol`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `target_vol`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `max_leverage`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `3.0`.
- `min_leverage`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `eps`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1e-08`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.risk.position_sizing.scale_signal_by_vol()`.

##### `scale_signal_by_vol`

**Signature**

```python
def scale_signal_by_vol(signal: pd.Series, vol: pd.Series, target_vol: float, max_leverage: float = 3.0, min_leverage: float = 0.0, eps: float = 1e-08) -> pd.Series
```

**Περιγραφή**

Scale a trading signal by volatility targeting leverage.

**Παράμετροι**

- `signal`: `pd.Series`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης.
- `vol`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `target_vol`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `max_leverage`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `3.0`.
- `min_leverage`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `eps`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1e-08`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.backtesting.engine.run_backtest()`, `src.backtesting.strategies.vol_targeted_signal()`.

### 4.8 Package `src/portfolio`

Portfolio constraints, optimization, signal-to-weight mapping και portfolio-level accounting.

#### Αρχείο `src/portfolio/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 35 LOC, 4 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.constraints` εισάγονται `PortfolioConstraints`, `apply_constraints`, `apply_weight_bounds`, `enforce_gross_leverage`, `enforce_group_caps`, `enforce_net_exposure`, `enforce_turnover_limit`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.construction` εισάγονται `PortfolioPerformance`, `build_optimized_weights_over_time`, `build_weights_from_signals_over_time`, `compute_portfolio_performance`, `signal_to_raw_weights`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.covariance` εισάγονται `build_rolling_covariance_by_date`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.optimizer` εισάγονται `optimize_mean_variance`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/portfolio/constraints.py`

**Σκοπός**: Projection/constraint engine για weights, leverage, turnover και optional group exposures.

**Βασικά Μεγέθη**: 291 LOC, 5 import blocks, 0 global constants, 1 classes, 8 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `PortfolioConstraints`: βάσεις χωρίς explicit base classes. Define the admissible region for portfolio weights, leverage, turnover, and optional group
  Πεδία:
  - `min_weight`: `float`. Προεπιλογή: `-1.0`.
  - `max_weight`: `float`. Προεπιλογή: `1.0`.
  - `max_gross_leverage`: `float`. Προεπιλογή: `1.0`.
  - `target_net_exposure`: `float`. Προεπιλογή: `0.0`.
  - `turnover_limit`: `float | None`. Προεπιλογή: `None`.
  - `group_max_exposure`: `Mapping[str, float] | None`. Προεπιλογή: `None`.
  Μέθοδοι: `__post_init__`.

**Functions**

##### `_as_weight_series`

**Signature**

```python
def _as_weight_series(weights: pd.Series) -> pd.Series
```

**Περιγραφή**

Handle as weight series inside the portfolio construction layer. The helper isolates one

**Παράμετροι**

- `weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.portfolio.constraints._distribute_delta_with_bounds()`, `src.portfolio.constraints.apply_constraints()`, `src.portfolio.constraints.apply_weight_bounds()`, `src.portfolio.constraints.enforce_gross_leverage()`, `src.portfolio.constraints.enforce_group_caps()`, `src.portfolio.constraints.enforce_net_exposure()`, `src.portfolio.constraints.enforce_turnover_limit()`.

##### `apply_weight_bounds`

**Signature**

```python
def apply_weight_bounds(weights: pd.Series, *, min_weight: float, max_weight: float) -> pd.Series
```

**Περιγραφή**

Apply weight bounds to the provided inputs in a controlled and reusable way. The helper

**Παράμετροι**

- `weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.
- `min_weight`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `max_weight`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Κάνει copy ή normalization του input όπου χρειάζεται.
2. Εφαρμόζει μία συγκεκριμένη policy/transformation χωρίς να αναμιγνύει άσχετες ευθύνες.
3. Επιστρέφει transformed object και, όπου απαιτείται, metadata του applied step.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.portfolio.constraints.apply_constraints()`.

##### `enforce_gross_leverage`

**Signature**

```python
def enforce_gross_leverage(weights: pd.Series, *, max_gross_leverage: float) -> pd.Series
```

**Περιγραφή**

Enforce gross leverage as a hard constraint inside the portfolio construction layer. The

**Παράμετροι**

- `weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.
- `max_gross_leverage`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.portfolio.constraints.apply_constraints()`.

##### `_distribute_delta_with_bounds`

**Signature**

```python
def _distribute_delta_with_bounds(weights: pd.Series, *, delta: float, min_weight: float, max_weight: float) -> pd.Series
```

**Περιγραφή**

Handle distribute delta with bounds inside the portfolio construction layer. The helper

**Παράμετροι**

- `weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.
- `delta`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `min_weight`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `max_weight`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.portfolio.constraints.enforce_net_exposure()`.

##### `enforce_net_exposure`

**Signature**

```python
def enforce_net_exposure(weights: pd.Series, *, target_net_exposure: float, min_weight: float, max_weight: float) -> pd.Series
```

**Περιγραφή**

Enforce net exposure as a hard constraint inside the portfolio construction layer. The

**Παράμετροι**

- `weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.
- `target_net_exposure`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `min_weight`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `max_weight`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.portfolio.constraints.apply_constraints()`.

##### `enforce_group_caps`

**Signature**

```python
def enforce_group_caps(weights: pd.Series, *, asset_to_group: Mapping[str, str] | None, group_max_exposure: Mapping[str, float] | None) -> pd.Series
```

**Περιγραφή**

Enforce group caps as a hard constraint inside the portfolio construction layer. The helper

**Παράμετροι**

- `weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.
- `asset_to_group`: `Mapping[str, str] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `group_max_exposure`: `Mapping[str, float] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.portfolio.constraints.apply_constraints()`.

##### `enforce_turnover_limit`

**Signature**

```python
def enforce_turnover_limit(weights: pd.Series, *, prev_weights: pd.Series | None, turnover_limit: float | None) -> pd.Series
```

**Περιγραφή**

Enforce turnover limit as a hard constraint inside the portfolio construction layer. The

**Παράμετροι**

- `weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.
- `prev_weights`: `pd.Series | None`. Series/DataFrame βαρών ή exposure allocations.
- `turnover_limit`: `float | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.portfolio.constraints.apply_constraints()`.

##### `apply_constraints`

**Signature**

```python
def apply_constraints(weights: pd.Series, *, constraints: PortfolioConstraints, prev_weights: pd.Series | None = None, asset_to_group: Mapping[str, str] | None = None, n_projection_passes: int = 3) -> tuple[pd.Series, dict[str, float | dict[str, float]]]
```

**Περιγραφή**

Apply constraints to the provided inputs in a controlled and reusable way. The helper makes

**Παράμετροι**

- `weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.
- `constraints`: `PortfolioConstraints`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `prev_weights`: `pd.Series | None`. Series/DataFrame βαρών ή exposure allocations. Προεπιλογή: `None`.
- `asset_to_group`: `Mapping[str, str] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `n_projection_passes`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `3`.

**Return Type**: `tuple[pd.Series, dict[str, float | dict[str, float]]]`.

**Λογική Βήμα-Βήμα**

1. Κάνει copy ή normalization του input όπου χρειάζεται.
2. Εφαρμόζει μία συγκεκριμένη policy/transformation χωρίς να αναμιγνύει άσχετες ευθύνες.
3. Επιστρέφει transformed object και, όπου απαιτείται, metadata του applied step.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.portfolio.construction.build_weights_from_signals_over_time()`, `src.portfolio.optimizer.optimize_mean_variance()`, `tests.test_portfolio.test_apply_constraints_respects_bounds_group_gross_and_turnover()`.

#### Αρχείο `src/portfolio/construction.py`

**Σκοπός**: Portfolio construction layer για signal-to-weight mapping, rolling optimization και portfolio PnL accounting.

**Βασικά Μεγέθη**: 221 LOC, 8 import blocks, 0 global constants, 1 classes, 4 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.evaluation.metrics` εισάγονται `compute_backtest_metrics`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.portfolio.constraints` εισάγονται `PortfolioConstraints`, `apply_constraints`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.portfolio.optimizer` εισάγονται `optimize_mean_variance`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `PortfolioPerformance`: βάσεις χωρίς explicit base classes. Store the time series and aggregate statistics produced by a portfolio-level backtest,
  Πεδία:
  - `equity_curve`: `pd.Series`.
  - `net_returns`: `pd.Series`.
  - `gross_returns`: `pd.Series`.
  - `costs`: `pd.Series`.
  - `turnover`: `pd.Series`.
  - `summary`: `dict[str, float]`.

**Functions**

##### `signal_to_raw_weights`

**Signature**

```python
def signal_to_raw_weights(signal_t: pd.Series, *, long_short: bool = True, gross_target: float = 1.0) -> pd.Series
```

**Περιγραφή**

Handle signal to raw weights inside the portfolio construction layer. The helper isolates

**Παράμετροι**

- `signal_t`: `pd.Series`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης.
- `long_short`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.
- `gross_target`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1.0`.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.portfolio.construction.build_weights_from_signals_over_time()`.

##### `build_weights_from_signals_over_time`

**Signature**

```python
def build_weights_from_signals_over_time(signals: pd.DataFrame, *, constraints: PortfolioConstraints | None = None, asset_to_group: Mapping[str, str] | None = None, long_short: bool = True, gross_target: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]
```

**Περιγραφή**

Build weights from signals over time as an explicit intermediate object used by the

**Παράμετροι**

- `signals`: `pd.DataFrame`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης.
- `constraints`: `PortfolioConstraints | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `asset_to_group`: `Mapping[str, str] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `long_short`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.
- `gross_target`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1.0`.

**Return Type**: `tuple[pd.DataFrame, pd.DataFrame]`.

**Λογική Βήμα-Βήμα**

1. Συγκεντρώνει inputs από το ανώτερο orchestration layer.
2. Συνθέτει νέο ενδιάμεσο object ή report με deterministic schema.
3. Επιστρέφει αποτέλεσμα έτοιμο για downstream consumption ή persistence.

**Edge Cases**: Η συνάρτηση υποθέτει ότι τα upstream contracts έχουν ήδη ελεγχθεί, αλλά εξακολουθεί να αποτυγχάνει αν τα inputs είναι κενά ή μη ευθυγραμμισμένα.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: O(T * A * P), όπου T=χρονικά βήματα, A=assets και P=projection passes των constraints.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_portfolio_backtest()`, `tests.test_portfolio.test_build_weights_from_signals_over_time_respects_constraints()`.

##### `build_optimized_weights_over_time`

**Signature**

```python
def build_optimized_weights_over_time(expected_returns: pd.DataFrame, *, covariance_by_date: Mapping[pd.Timestamp, pd.DataFrame] | None = None, constraints: PortfolioConstraints | None = None, asset_to_group: Mapping[str, str] | None = None, risk_aversion: float = 5.0, trade_aversion: float = 0.0) -> tuple[pd.DataFrame, pd.DataFrame]
```

**Περιγραφή**

Build optimized weights over time as an explicit intermediate object used by the portfolio

**Παράμετροι**

- `expected_returns`: `pd.DataFrame`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `covariance_by_date`: `Mapping[pd.Timestamp, pd.DataFrame] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `constraints`: `PortfolioConstraints | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `asset_to_group`: `Mapping[str, str] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `risk_aversion`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `5.0`.
- `trade_aversion`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.

**Return Type**: `tuple[pd.DataFrame, pd.DataFrame]`.

**Λογική Βήμα-Βήμα**

1. Συγκεντρώνει inputs από το ανώτερο orchestration layer.
2. Συνθέτει νέο ενδιάμεσο object ή report με deterministic schema.
3. Επιστρέφει αποτέλεσμα έτοιμο για downstream consumption ή persistence.

**Edge Cases**: Η συνάρτηση υποθέτει ότι τα upstream contracts έχουν ήδη ελεγχθεί, αλλά εξακολουθεί να αποτυγχάνει αν τα inputs είναι κενά ή μη ευθυγραμμισμένα.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: O(T * Solver(A)), με επιπλέον κόστος για lookup covariance ανά ημερομηνία.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_portfolio_backtest()`.

##### `compute_portfolio_performance`

**Signature**

```python
def compute_portfolio_performance(weights: pd.DataFrame, asset_returns: pd.DataFrame, *, cost_per_turnover: float = 0.0, slippage_per_turnover: float = 0.0, periods_per_year: int = 252) -> PortfolioPerformance
```

**Περιγραφή**

Compute portfolio performance for the portfolio construction layer. The helper keeps the

**Παράμετροι**

- `weights`: `pd.DataFrame`. Series/DataFrame βαρών ή exposure allocations.
- `asset_returns`: `pd.DataFrame`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `cost_per_turnover`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `slippage_per_turnover`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `252`.

**Return Type**: `PortfolioPerformance`.

**Λογική Βήμα-Βήμα**

1. Ευθυγραμμίζει weights και returns σε κοινό index και κοινό asset universe.
2. Μετατοπίζει τα weights κατά μία περίοδο ώστε η απόδοση στη χρονική στιγμή `t` να χρησιμοποιεί θέση από `t-1`.
3. Υπολογίζει turnover, transaction costs, gross returns και net returns.
4. Χτίζει equity curve και summary metrics σε portfolio επίπεδο.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: O(T * A) για ευθυγράμμιση, turnover και PnL aggregation.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_portfolio_backtest()`, `tests.test_portfolio.test_compute_portfolio_performance_charges_initial_turnover()`, `tests.test_portfolio.test_compute_portfolio_performance_uses_shifted_weights()`.

#### Αρχείο `src/portfolio/covariance.py`

**Σκοπός**: Υλοποίηση του module `covariance.py` μέσα στο package `portfolio`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 42 LOC, 3 import blocks, 0 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `build_rolling_covariance_by_date`

**Signature**

```python
def build_rolling_covariance_by_date(asset_returns: pd.DataFrame, *, window: int = 60, min_periods: int | None = None) -> dict[pd.Timestamp, pd.DataFrame]
```

**Περιγραφή**

Build rolling covariance by date as an explicit intermediate object used by the portfolio

**Παράμετροι**

- `asset_returns`: `pd.DataFrame`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `window`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `60`.
- `min_periods`: `int | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `dict[pd.Timestamp, pd.DataFrame]`.

**Λογική Βήμα-Βήμα**

1. Συγκεντρώνει inputs από το ανώτερο orchestration layer.
2. Συνθέτει νέο ενδιάμεσο object ή report με deterministic schema.
3. Επιστρέφει αποτέλεσμα έτοιμο για downstream consumption ή persistence.

**Edge Cases**: Η συνάρτηση υποθέτει ότι τα upstream contracts έχουν ήδη ελεγχθεί, αλλά εξακολουθεί να αποτυγχάνει αν τα inputs είναι κενά ή μη ευθυγραμμισμένα.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Περίπου O(T * W * A^2), όπου W=rolling window, A=assets. Η pandas `cov()` κυριαρχεί στο κόστος.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_portfolio_backtest()`.

#### Αρχείο `src/portfolio/optimizer.py`

**Σκοπός**: Mean-variance optimizer με hard constraints και safe fallback όταν ο solver αποτυγχάνει.

**Βασικά Μεγέθη**: 179 LOC, 6 import blocks, 0 global constants, 0 classes, 3 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `scipy.optimize` εισάγονται `minimize`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.portfolio.constraints` εισάγονται `PortfolioConstraints`, `apply_constraints`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `_prepare_covariance`

**Signature**

```python
def _prepare_covariance(assets: pd.Index, covariance: pd.DataFrame | None) -> pd.DataFrame
```

**Περιγραφή**

Handle prepare covariance inside the portfolio construction layer. The helper isolates one

**Παράμετροι**

- `assets`: `pd.Index`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `covariance`: `pd.DataFrame | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.portfolio.optimizer.optimize_mean_variance()`.

##### `_initial_weights`

**Signature**

```python
def _initial_weights(assets: pd.Index, *, constraints: PortfolioConstraints, prev_weights: pd.Series | None) -> np.ndarray
```

**Περιγραφή**

Handle initial weights inside the portfolio construction layer. The helper isolates one

**Παράμετροι**

- `assets`: `pd.Index`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `constraints`: `PortfolioConstraints`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `prev_weights`: `pd.Series | None`. Series/DataFrame βαρών ή exposure allocations.

**Return Type**: `np.ndarray`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.portfolio.optimizer.optimize_mean_variance()`.

##### `optimize_mean_variance`

**Signature**

```python
def optimize_mean_variance(expected_returns: pd.Series, *, covariance: pd.DataFrame | None = None, constraints: PortfolioConstraints | None = None, prev_weights: pd.Series | None = None, asset_to_group: Mapping[str, str] | None = None, risk_aversion: float = 5.0, trade_aversion: float = 0.0, allow_fallback: bool = True) -> tuple[pd.Series, dict[str, float | str | bool | dict[str, float]]]
```

**Περιγραφή**

Handle optimize mean variance inside the portfolio construction layer. The helper isolates

**Παράμετροι**

- `expected_returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `covariance`: `pd.DataFrame | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `constraints`: `PortfolioConstraints | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `prev_weights`: `pd.Series | None`. Series/DataFrame βαρών ή exposure allocations. Προεπιλογή: `None`.
- `asset_to_group`: `Mapping[str, str] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `risk_aversion`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `5.0`.
- `trade_aversion`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `allow_fallback`: `bool`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `True`.

**Return Type**: `tuple[pd.Series, dict[str, float | str | bool | dict[str, float]]]`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί expected returns και covariance στην ίδια διάσταση assets.
2. Χτίζει objective που ισορροπεί alpha, risk penalty και optional trade penalty.
3. Ορίζει hard constraints για net exposure, gross leverage, turnover και group caps.
4. Λύνει πρόβλημα SLSQP με bounds ανά asset.
5. Αν ο solver αποτύχει και επιτρέπεται fallback, παράγει centered heuristic portfolio.
6. Περνάει το αποτέλεσμα από `apply_constraints` για τελικό projection σε admissible region.
7. Επιστρέφει weights και metadata για solver success, objective value και diagnostics.

**Edge Cases**: Μη αριθμητικές/ατελείς covariance matrices μπορεί να οδηγήσουν σε solver failure και fallback. Η τελική feasibility διασφαλίζεται από post-projection μέσω `apply_constraints`.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Εξαρτάται από τον iterative SLSQP solver. Κάθε objective/constraint evaluation είναι O(A^2) λόγω covariance term, ενώ ο συνολικός χρόνος είναι O(Iterations * A^2) έως O(Iterations * A^3) εμπειρικά.

**Πού Καλείται στο Pipeline**: `src.portfolio.construction.build_optimized_weights_over_time()`, `tests.test_portfolio.test_optimize_mean_variance_fallback_respects_max_gross_leverage()`, `tests.test_portfolio.test_optimize_mean_variance_respects_core_constraints()`.

### 4.9 Package `src/monitoring`

Production-style drift diagnostics για features.

#### Αρχείο `src/monitoring/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 6 LOC, 1 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.drift` εισάγονται `compute_feature_drift`, `population_stability_index`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/monitoring/drift.py`

**Σκοπός**: Monitoring layer για PSI-based feature drift και summary diagnostics.

**Βασικά Μεγέθη**: 113 LOC, 4 import blocks, 0 global constants, 0 classes, 2 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Any`, `Iterable`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `population_stability_index`

**Signature**

```python
def population_stability_index(reference: pd.Series, current: pd.Series, *, n_bins: int = 10, eps: float = 1e-06) -> float
```

**Περιγραφή**

Handle population stability index inside the monitoring layer. The helper isolates one

**Παράμετροι**

- `reference`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `current`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `n_bins`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `10`.
- `eps`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `1e-06`.

**Return Type**: `float`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.monitoring.drift.compute_feature_drift()`.

##### `compute_feature_drift`

**Signature**

```python
def compute_feature_drift(reference_df: pd.DataFrame, current_df: pd.DataFrame, *, feature_cols: Iterable[str] | None = None, psi_threshold: float = 0.2, n_bins: int = 10) -> dict[str, Any]
```

**Περιγραφή**

Compute feature drift for the monitoring layer. The helper keeps the calculation isolated so

**Παράμετροι**

- `reference_df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `current_df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `feature_cols`: `Iterable[str] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `psi_threshold`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.2`.
- `n_bins`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `10`.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Επιλέγει κοινά numeric features μεταξύ reference και current datasets.
2. Υπολογίζει missing rates, mean/std, normalized mean shift και PSI ανά feature.
3. Μαρκάρει features ως drifted όταν το PSI υπερβαίνει το config threshold.
4. Επιστρέφει aggregate report και per-feature diagnostics.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: O(F * N log N) περίπου, λόγω quantiles/histograms ανά feature, όπου F=features και N=rows.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._compute_monitoring_for_asset()`.

### 4.10 Package `src/execution`

Paper execution export layer.

#### Αρχείο `src/execution/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 3 LOC, 1 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.paper` εισάγονται `build_rebalance_orders`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/execution/paper.py`

**Σκοπός**: Paper execution artifact builder που μετατρέπει target weights σε notional/share deltas.

**Βασικά Μεγέθη**: 66 LOC, 2 import blocks, 0 global constants, 0 classes, 1 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `build_rebalance_orders`

**Signature**

```python
def build_rebalance_orders(target_weights: pd.Series, *, prices: pd.Series, capital: float, current_weights: pd.Series | None = None, min_trade_notional: float = 0.0) -> pd.DataFrame
```

**Περιγραφή**

Build rebalance orders as an explicit intermediate object used by the paper execution

**Παράμετροι**

- `target_weights`: `pd.Series`. Series/DataFrame βαρών ή exposure allocations.
- `prices`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `capital`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `current_weights`: `pd.Series | None`. Series/DataFrame βαρών ή exposure allocations. Προεπιλογή: `None`.
- `min_trade_notional`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Μετατρέπει target και current weights σε notionals χρησιμοποιώντας το συνολικό capital.
2. Υπολογίζει delta notionals και delta shares ανά asset.
3. Φιλτράρει μικρές συναλλαγές βάσει `min_trade_notional`.
4. Επιστρέφει ταξινομημένο order blotter έτοιμο για paper execution workflow.

**Edge Cases**: Η συνάρτηση υποθέτει ότι τα upstream contracts έχουν ήδη ελεγχθεί, αλλά εξακολουθεί να αποτυγχάνει αν τα inputs είναι κενά ή μη ευθυγραμμισμένα.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: O(A log A) λόγω sorting των orders μετά από O(A) vectorized υπολογισμούς.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._build_execution_output()`, `tests.test_runner_extensions.test_build_rebalance_orders_reports_share_deltas()`.

### 4.11 Package `src/experiments`

Top-level orchestration domain: contracts, registries, model training routines, end-to-end run coordination.

#### Αρχείο `src/experiments/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 16 LOC, 2 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `.runner` εισάγονται `ExperimentResult`, `run_experiment`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `.contracts` εισάγονται `DataContract`, `TargetContract`, `validate_data_contract`, `validate_feature_target_contract`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/experiments/contracts.py`

**Σκοπός**: Υλοποίηση του module `contracts.py` μέσα στο package `experiments`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 130 LOC, 5 import blocks, 0 global constants, 2 classes, 2 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Iterable`, `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas.api.types` εισάγονται `is_numeric_dtype`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `DataContract`: βάσεις χωρίς explicit base classes. Describe the minimum structural guarantees expected from market data before feature
  Πεδία:
  - `required_columns`: `tuple[str, ...]`. Προεπιλογή: `('open', 'high', 'low', 'close', 'volume')`.
  - `require_datetime_index`: `bool`. Προεπιλογή: `True`.
  - `require_unique_index`: `bool`. Προεπιλογή: `True`.
  - `require_monotonic_index`: `bool`. Προεπιλογή: `True`.
- `TargetContract`: βάσεις χωρίς explicit base classes. Describe the label column and prediction horizon that the feature-to-target validation logic
  Πεδία:
  - `target_col`: `str`.
  - `horizon`: `int`. Προεπιλογή: `1`.

**Functions**

##### `validate_data_contract`

**Signature**

```python
def validate_data_contract(df: pd.DataFrame, contract: DataContract | None = None) -> dict[str, int]
```

**Περιγραφή**

Validate data contract before downstream logic depends on it. The function raises early when

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `contract`: `DataContract | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `dict[str, int]`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει τον τύπο και τα βασικά structural preconditions του input.
2. Συγκεντρώνει violations αντί να προχωρήσει σε downstream logic.
3. Σηκώνει deterministic exception όταν εντοπίζει contract breach ή επιστρέφει lightweight metadata.

**Edge Cases**: Empty inputs, λάθος types, duplicate timestamps και missing required columns είναι συνήθη failure modes που αντιμετωπίζονται με άμεσο exception.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`.

##### `validate_feature_target_contract`

**Signature**

```python
def validate_feature_target_contract(df: pd.DataFrame, *, feature_cols: Sequence[str], target: TargetContract, forbidden_feature_prefixes: Iterable[str] = ('target_', 'label', 'pred_')) -> dict[str, int]
```

**Περιγραφή**

Validate feature target contract before downstream logic depends on it. The function raises

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `feature_cols`: `Sequence[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `target`: `TargetContract`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `forbidden_feature_prefixes`: `Iterable[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `('target_', 'label', 'pred_')`.

**Return Type**: `dict[str, int]`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει τον τύπο και τα βασικά structural preconditions του input.
2. Συγκεντρώνει violations αντί να προχωρήσει σε downstream logic.
3. Σηκώνει deterministic exception όταν εντοπίζει contract breach ή επιστρέφει lightweight metadata.

**Edge Cases**: Empty inputs, λάθος types, duplicate timestamps και missing required columns είναι συνήθη failure modes που αντιμετωπίζονται με άμεσο exception.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`, `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`, `tests.test_contracts_metrics_pit.test_feature_contract_rejects_target_like_feature_columns()`.

#### Αρχείο `src/experiments/models.py`

**Σκοπός**: Modeling layer για classification πάνω σε forward-return targets με leakage-safe chronological splits.

**Βασικά Μεγέθη**: 499 LOC, 10 import blocks, 0 global constants, 0 classes, 8 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Any`, `Callable`, `Iterable`, `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `lightgbm` εισάγονται `LGBMClassifier`. Ρόλος: Model training / αξιολόγηση classification models.
- Από `sklearn.linear_model` εισάγονται `LogisticRegression`. Ρόλος: Model training / αξιολόγηση classification models.
- Από `sklearn.metrics` εισάγονται `accuracy_score`, `brier_score_loss`, `log_loss`, `roc_auc_score`. Ρόλος: Model training / αξιολόγηση classification models.
- Από `src.evaluation.time_splits` εισάγονται `assert_no_forward_label_leakage`, `build_time_splits`, `trim_train_indices_for_horizon`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.experiments.contracts` εισάγονται `TargetContract`, `validate_feature_target_contract`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.models.lightgbm_baseline` εισάγονται `default_feature_columns`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `_resolve_runtime_for_model`

**Signature**

```python
def _resolve_runtime_for_model(model_cfg: dict[str, Any], model_params: dict[str, Any], *, estimator_family: str) -> dict[str, Any]
```

**Περιγραφή**

Handle runtime for model inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `model_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `model_params`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `estimator_family`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`.

##### `infer_feature_columns`

**Signature**

```python
def infer_feature_columns(df: pd.DataFrame, explicit_cols: Sequence[str] | None = None, exclude: Iterable[str] | None = None) -> list[str]
```

**Περιγραφή**

Infer feature columns from the available inputs when the caller has not specified them

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `explicit_cols`: `Sequence[str] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.
- `exclude`: `Iterable[str] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `list[str]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`.

##### `_build_forward_return_target`

**Signature**

```python
def _build_forward_return_target(df: pd.DataFrame, target_cfg: dict[str, Any] | None) -> tuple[pd.DataFrame, str, str, dict[str, Any]]
```

**Περιγραφή**

Handle forward return target inside the experiment orchestration layer. The helper isolates

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `target_cfg`: `dict[str, Any] | None`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `tuple[pd.DataFrame, str, str, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`.

##### `_assign_quantile_labels`

**Signature**

```python
def _assign_quantile_labels(forward_returns: pd.Series, *, low_value: float, high_value: float) -> pd.Series
```

**Περιγραφή**

Handle assign quantile labels inside the experiment orchestration layer. The helper isolates

**Παράμετροι**

- `forward_returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `low_value`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `high_value`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.Series`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`.

##### `_binary_classification_metrics`

**Signature**

```python
def _binary_classification_metrics(y_true: pd.Series, pred_prob: pd.Series) -> dict[str, float | int | None]
```

**Περιγραφή**

Handle binary classification metrics inside the experiment orchestration layer. The helper

**Παράμετροι**

- `y_true`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `pred_prob`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, float | int | None]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.models._train_forward_classifier()`.

##### `_train_forward_classifier`

**Signature**

```python
def _train_forward_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], *, model_kind: str, estimator_family: str, estimator_factory: EstimatorFactory, returns_col: str | None = None) -> tuple[pd.DataFrame, object, dict[str, Any]]
```

**Περιγραφή**

Handle forward classifier inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `model_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `model_kind`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `estimator_family`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `estimator_factory`: `EstimatorFactory`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `returns_col`: `str | None`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance. Προεπιλογή: `None`.

**Return Type**: `tuple[pd.DataFrame, object, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί runtime/model parameters και επιβάλλει deterministic options όπου υποστηρίζονται.
2. Κατασκευάζει forward-return target και binary ή quantile-based labels χωρίς να γράφει στο αρχικό input.
3. Επιλύει feature columns είτε από explicit config είτε από heuristic inference.
4. Επικυρώνει feature-target contract ώστε να αποκλείσει leakage-prone ή μη αριθμητικά features.
5. Χτίζει chronological splits (time, walk-forward ή purged) με γνώση του prediction horizon.
6. Trim-άρει training indices κοντά στο test boundary ώστε το forward label να μην αγγίζει το test window.
7. Εκπαιδεύει estimator ανά fold, κάνει prediction μόνο σε γραμμές με πλήρη features και γράφει `pred_prob`.
8. Συσσωρεύει fold-level και συνολικά OOS classification metrics και anti-leakage diagnostics.
9. Επιστρέφει enriched DataFrame, fitted estimator και rich metadata dict.

**Edge Cases**: Fold χωρίς train rows μετά από NaN filtering ή χωρίς δύο target classes σηκώνει `ValueError`. Τα quantile labels αφήνουν την middle περιοχή ως NaN, άρα evaluation coverage μπορεί να είναι μικρότερη από το test size.

**Side Effects**: Εκπαιδεύει estimator object και άρα μεταβάλλει internal model state.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Περίπου O(Folds * (TrainFit + TestPredict + N_features * N_rows)). Το training cost εξαρτάται από τον estimator: για logistic regression συνήθως iterative convex optimization, για LightGBM cost περίπου O(Trees * rows * log rows) εμπειρικά.

**Πού Καλείται στο Pipeline**: `src.experiments.models.train_lightgbm_classifier()`, `src.experiments.models.train_logistic_regression_classifier()`.

##### `train_lightgbm_classifier`

**Signature**

```python
def train_lightgbm_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], returns_col: str | None = None) -> tuple[pd.DataFrame, LGBMClassifier, dict[str, Any]]
```

**Περιγραφή**

Train lightgbm classifier using the data and split conventions defined by the experiment

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `model_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `returns_col`: `str | None`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance. Προεπιλογή: `None`.

**Return Type**: `tuple[pd.DataFrame, LGBMClassifier, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `tests.test_contracts_metrics_pit.test_forward_horizon_guard_trims_train_rows_in_time_split()`, `tests.test_no_lookahead.test_binary_forward_target_keeps_tail_labels_nan()`, `tests.test_no_lookahead.test_purged_splits_respect_anti_leakage_gap()`, `tests.test_no_lookahead.test_quantile_target_uses_train_only_distribution_per_fold()`, `tests.test_no_lookahead.test_walk_forward_predictions_are_oos_only()`.

##### `train_logistic_regression_classifier`

**Signature**

```python
def train_logistic_regression_classifier(df: pd.DataFrame, model_cfg: dict[str, Any], returns_col: str | None = None) -> tuple[pd.DataFrame, LogisticRegression, dict[str, Any]]
```

**Περιγραφή**

Train logistic regression classifier using the data and split conventions defined by the

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `model_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `returns_col`: `str | None`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance. Προεπιλογή: `None`.

**Return Type**: `tuple[pd.DataFrame, LogisticRegression, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `tests.test_runner_extensions.test_logistic_regression_model_registry_outputs_oos_metrics()`.

#### Αρχείο `src/experiments/registry.py`

**Σκοπός**: Υλοποίηση του module `registry.py` μέσα στο package `experiments`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 88 LOC, 10 import blocks, 0 global constants, 0 classes, 3 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Callable`, `Mapping`, `Optional`, `Union`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.features` εισάγονται `add_close_returns`, `add_lagged_features`, `add_volatility_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.features.technical.indicators` εισάγονται `add_indicator_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.features.technical.momentum` εισάγονται `add_momentum_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.features.technical.oscillators` εισάγονται `add_oscillator_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.features.technical.trend` εισάγονται `add_trend_features`, `add_trend_regime_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.backtesting.strategies` εισάγονται `conviction_sizing_signal`, `momentum_strategy`, `probabilistic_signal`, `rsi_strategy`, `stochastic_strategy`, `trend_state_signal`, `volatility_regime_strategy`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.experiments.models` εισάγονται `train_lightgbm_classifier`, `train_logistic_regression_classifier`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `get_feature_fn`

**Signature**

```python
def get_feature_fn(name: str) -> FeatureFn
```

**Περιγραφή**

Handle get feature fn inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `name`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `FeatureFn`.

**Λογική Βήμα-Βήμα**

1. Κάνει lookup σε registry ή mapping.
2. Επικυρώνει ότι το ζητούμενο key υπάρχει.
3. Επιστρέφει callable ή object contract που θα χρησιμοποιηθεί downstream.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._apply_feature_steps()`.

##### `get_signal_fn`

**Signature**

```python
def get_signal_fn(name: str) -> SignalFn
```

**Περιγραφή**

Handle get signal fn inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `name`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `SignalFn`.

**Λογική Βήμα-Βήμα**

1. Κάνει lookup σε registry ή mapping.
2. Επικυρώνει ότι το ζητούμενο key υπάρχει.
3. Επιστρέφει callable ή object contract που θα χρησιμοποιηθεί downstream.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._apply_signal_step()`.

##### `get_model_fn`

**Signature**

```python
def get_model_fn(name: str) -> ModelFn
```

**Περιγραφή**

Handle get model fn inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `name`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `ModelFn`.

**Λογική Βήμα-Βήμα**

1. Κάνει lookup σε registry ή mapping.
2. Επικυρώνει ότι το ζητούμενο key υπάρχει.
3. Επιστρέφει callable ή object contract που θα χρησιμοποιηθεί downstream.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._apply_model_step()`.

#### Αρχείο `src/experiments/runner.py`

**Σκοπός**: Κεντρικός orchestrator. Συνδέει config loading, data ingestion, PIT hardening, features, model fitting, signal generation, single-asset ή portfolio backtest, monitoring, execution και artifact persistence.

**Βασικά Μεγέθη**: 1264 LOC, 25 import blocks, 0 global constants, 1 classes, 31 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `datetime` εισάγονται `datetime`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.
- Από `pathlib` εισάγονται `Path`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `re` εισάγονται `re`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.
- Από `typing` εισάγονται `Any`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `json` εισάγονται `json`. Ρόλος: Serialization / configuration parsing.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `yaml` εισάγονται `yaml`. Ρόλος: Serialization / configuration parsing.
- Από `src.backtesting.engine` εισάγονται `BacktestResult`, `run_backtest`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.evaluation.metrics` εισάγονται `compute_backtest_metrics`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.execution.paper` εισάγονται `build_rebalance_orders`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.experiments.contracts` εισάγονται `validate_data_contract`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.experiments.registry` εισάγονται `get_feature_fn`, `get_model_fn`, `get_signal_fn`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.monitoring.drift` εισάγονται `compute_feature_drift`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.portfolio` εισάγονται `PortfolioConstraints`, `PortfolioPerformance`, `build_optimized_weights_over_time`, `build_rolling_covariance_by_date`, `build_weights_from_signals_over_time`, `compute_portfolio_performance`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.src_data.loaders` εισάγονται `load_ohlcv`, `load_ohlcv_panel`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.src_data.pit` εισάγονται `apply_pit_hardening`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.src_data.storage` εισάγονται `asset_frames_to_long_frame`, `load_dataset_snapshot`, `save_dataset_snapshot`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.src_data.validation` εισάγονται `validate_ohlcv`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.utils.config` εισάγονται `load_experiment_config`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.utils.paths` εισάγονται `in_project`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.utils.repro` εισάγονται `apply_runtime_reproducibility`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.utils.run_metadata` εισάγονται `build_artifact_manifest`, `build_run_metadata`, `compute_config_hash`, `compute_dataframe_fingerprint`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `ExperimentResult`: βάσεις χωρίς explicit base classes. Collect the full output of an experiment run, including the resolved configuration,
  Πεδία:
  - `config`: `dict[str, Any]`.
  - `data`: `pd.DataFrame | dict[str, pd.DataFrame]`.
  - `backtest`: `BacktestResult | PortfolioPerformance`.
  - `model`: `object | dict[str, object] | None`.
  - `model_meta`: `dict[str, Any]`.
  - `artifacts`: `dict[str, str]`.
  - `evaluation`: `dict[str, Any]`.
  - `monitoring`: `dict[str, Any]`.
  - `execution`: `dict[str, Any]`.
  - `portfolio_weights`: `pd.DataFrame | None`. Προεπιλογή: `None`.

**Functions**

##### `_slugify`

**Signature**

```python
def _slugify(value: str) -> str
```

**Περιγραφή**

Handle slugify inside the experiment orchestration layer. The helper isolates one focused

**Παράμετροι**

- `value`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `str`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._default_dataset_id()`.

##### `_resolve_symbols`

**Signature**

```python
def _resolve_symbols(data_cfg: dict[str, Any]) -> list[str]
```

**Περιγραφή**

Handle symbols inside the experiment orchestration layer. The helper isolates one focused

**Παράμετροι**

- `data_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `list[str]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._default_dataset_id()`, `src.experiments.runner._load_asset_frames()`, `src.experiments.runner.run_experiment()`.

##### `_default_dataset_id`

**Signature**

```python
def _default_dataset_id(data_cfg: dict[str, Any]) -> str
```

**Περιγραφή**

Handle default dataset id inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `data_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `str`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`, `src.experiments.runner._save_processed_snapshot_if_enabled()`.

##### `_apply_feature_steps`

**Signature**

```python
def _apply_feature_steps(df: pd.DataFrame, steps: list[dict[str, Any]]) -> pd.DataFrame
```

**Περιγραφή**

Handle feature steps inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `steps`: `list[dict[str, Any]]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._apply_steps_to_assets()`.

##### `_apply_model_step`

**Signature**

```python
def _apply_model_step(df: pd.DataFrame, model_cfg: dict[str, Any], returns_col: str | None) -> tuple[pd.DataFrame, object | None, dict[str, Any]]
```

**Περιγραφή**

Handle model step inside the experiment orchestration layer. The helper isolates one focused

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `model_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `returns_col`: `str | None`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.

**Return Type**: `tuple[pd.DataFrame, object | None, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._apply_model_to_assets()`.

##### `_apply_signal_step`

**Signature**

```python
def _apply_signal_step(df: pd.DataFrame, signals_cfg: dict[str, Any]) -> pd.DataFrame
```

**Περιγραφή**

Handle signal step inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `signals_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `TypeError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._apply_signals_to_assets()`.

##### `_apply_steps_to_assets`

**Signature**

```python
def _apply_steps_to_assets(asset_frames: dict[str, pd.DataFrame], *, feature_steps: list[dict[str, Any]]) -> dict[str, pd.DataFrame]
```

**Περιγραφή**

Handle steps to assets inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `feature_steps`: `list[dict[str, Any]]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, pd.DataFrame]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_aggregate_model_meta`

**Signature**

```python
def _aggregate_model_meta(per_asset_meta: dict[str, dict[str, Any]]) -> dict[str, Any]
```

**Περιγραφή**

Handle aggregate model meta inside the experiment orchestration layer. The helper isolates

**Παράμετροι**

- `per_asset_meta`: `dict[str, dict[str, Any]]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._apply_model_to_assets()`.

##### `_apply_model_to_assets`

**Signature**

```python
def _apply_model_to_assets(asset_frames: dict[str, pd.DataFrame], *, model_cfg: dict[str, Any], returns_col: str | None) -> tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]
```

**Περιγραφή**

Handle model to assets inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `model_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `returns_col`: `str | None`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.

**Return Type**: `tuple[dict[str, pd.DataFrame], object | dict[str, object] | None, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_apply_signals_to_assets`

**Signature**

```python
def _apply_signals_to_assets(asset_frames: dict[str, pd.DataFrame], *, signals_cfg: dict[str, Any]) -> dict[str, pd.DataFrame]
```

**Περιγραφή**

Handle signals to assets inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `signals_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `dict[str, pd.DataFrame]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_resolve_vol_col`

**Signature**

```python
def _resolve_vol_col(df: pd.DataFrame, backtest_cfg: dict[str, Any], risk_cfg: dict[str, Any]) -> str | None
```

**Περιγραφή**

Handle volatility col inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `backtest_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `risk_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `str | None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_single_asset_backtest()`.

##### `_validate_returns_series`

**Signature**

```python
def _validate_returns_series(returns: pd.Series, returns_type: str) -> None
```

**Περιγραφή**

Handle returns series inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `returns_type`: `str`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_single_asset_backtest()`.

##### `_validate_returns_frame`

**Signature**

```python
def _validate_returns_frame(returns: pd.DataFrame, returns_type: str) -> None
```

**Περιγραφή**

Handle returns frame inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `returns`: `pd.DataFrame`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `returns_type`: `str`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_portfolio_backtest()`.

##### `_build_storage_context`

**Signature**

```python
def _build_storage_context(data_cfg: dict[str, Any], *, symbols: list[str], pit_cfg: dict[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Handle storage context inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `data_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `symbols`: `list[str]`. Identifier χρηματοοικονομικού μέσου ή λίστας μέσων.
- `pit_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._load_asset_frames()`, `src.experiments.runner.run_experiment()`.

##### `_load_asset_frames`

**Signature**

```python
def _load_asset_frames(data_cfg: dict[str, Any]) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]
```

**Περιγραφή**

Handle asset frames inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `data_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `tuple[dict[str, pd.DataFrame], dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `RuntimeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_save_processed_snapshot_if_enabled`

**Signature**

```python
def _save_processed_snapshot_if_enabled(asset_frames: dict[str, pd.DataFrame], *, data_cfg: dict[str, Any], config_hash_sha256: str, feature_steps: list[dict[str, Any]]) -> dict[str, Any] | None
```

**Περιγραφή**

Handle processed snapshot if enabled inside the experiment orchestration layer. The helper

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `data_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `config_hash_sha256`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `feature_steps`: `list[dict[str, Any]]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any] | None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_align_asset_column`

**Signature**

```python
def _align_asset_column(asset_frames: dict[str, pd.DataFrame], *, column: str, how: str) -> pd.DataFrame
```

**Περιγραφή**

Handle align asset column inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `column`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `how`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `KeyError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._build_execution_output()`, `src.experiments.runner._run_portfolio_backtest()`.

##### `_build_portfolio_constraints`

**Signature**

```python
def _build_portfolio_constraints(portfolio_cfg: dict[str, Any]) -> PortfolioConstraints
```

**Περιγραφή**

Handle portfolio constraints inside the experiment orchestration layer. The helper isolates

**Παράμετροι**

- `portfolio_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `PortfolioConstraints`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._run_portfolio_backtest()`.

##### `_run_single_asset_backtest`

**Signature**

```python
def _run_single_asset_backtest(asset: str, df: pd.DataFrame, *, cfg: dict[str, Any], model_meta: dict[str, Any]) -> BacktestResult
```

**Περιγραφή**

Handle single asset backtest inside the experiment orchestration layer. The helper isolates

**Παράμετροι**

- `asset`: `str`. Identifier χρηματοοικονομικού μέσου ή λίστας μέσων.
- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `model_meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `BacktestResult`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_run_portfolio_backtest`

**Signature**

```python
def _run_portfolio_backtest(asset_frames: dict[str, pd.DataFrame], *, cfg: dict[str, Any]) -> tuple[PortfolioPerformance, pd.DataFrame, pd.DataFrame, dict[str, Any]]
```

**Περιγραφή**

Handle portfolio backtest inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `tuple[PortfolioPerformance, pd.DataFrame, pd.DataFrame, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_compute_subset_metrics`

**Signature**

```python
def _compute_subset_metrics(*, net_returns: pd.Series, turnover: pd.Series, costs: pd.Series, gross_returns: pd.Series, periods_per_year: int, mask: pd.Series) -> dict[str, float]
```

**Περιγραφή**

Handle subset metrics inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `net_returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `turnover`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `costs`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `gross_returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `mask`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, float]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._build_fold_backtest_summaries()`, `src.experiments.runner._build_portfolio_evaluation()`, `src.experiments.runner._build_single_asset_evaluation()`.

##### `_build_fold_backtest_summaries`

**Signature**

```python
def _build_fold_backtest_summaries(*, source_index: pd.Index, net_returns: pd.Series, turnover: pd.Series, costs: pd.Series, gross_returns: pd.Series, periods_per_year: int, folds: list[dict[str, Any]]) -> list[dict[str, Any]]
```

**Περιγραφή**

Handle fold backtest summaries inside the experiment orchestration layer. The helper

**Παράμετροι**

- `source_index`: `pd.Index`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `net_returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `turnover`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `costs`: `pd.Series`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `gross_returns`: `pd.Series`. Χρονοσειρά ή panel αποδόσεων για υπολογισμό feature, target ή performance.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `folds`: `list[dict[str, Any]]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `list[dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._build_single_asset_evaluation()`.

##### `_build_single_asset_evaluation`

**Signature**

```python
def _build_single_asset_evaluation(asset: str, df: pd.DataFrame, *, performance: BacktestResult, model_meta: dict[str, Any], periods_per_year: int) -> dict[str, Any]
```

**Περιγραφή**

Handle single asset evaluation inside the experiment orchestration layer. The helper

**Παράμετροι**

- `asset`: `str`. Identifier χρηματοοικονομικού μέσου ή λίστας μέσων.
- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `performance`: `BacktestResult`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `model_meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_build_portfolio_evaluation`

**Signature**

```python
def _build_portfolio_evaluation(asset_frames: dict[str, pd.DataFrame], *, performance: PortfolioPerformance, model_meta: dict[str, Any], periods_per_year: int, alignment: str) -> dict[str, Any]
```

**Περιγραφή**

Handle portfolio evaluation inside the experiment orchestration layer. The helper isolates

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `performance`: `PortfolioPerformance`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `model_meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `periods_per_year`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `alignment`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_compute_monitoring_for_asset`

**Signature**

```python
def _compute_monitoring_for_asset(df: pd.DataFrame, *, meta: dict[str, Any], monitoring_cfg: dict[str, Any]) -> dict[str, Any] | None
```

**Περιγραφή**

Handle monitoring for asset inside the experiment orchestration layer. The helper isolates

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `monitoring_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `dict[str, Any] | None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._compute_monitoring_report()`.

##### `_compute_monitoring_report`

**Signature**

```python
def _compute_monitoring_report(asset_frames: dict[str, pd.DataFrame], *, model_meta: dict[str, Any], monitoring_cfg: dict[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Handle monitoring report inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `model_meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `monitoring_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_build_execution_output`

**Signature**

```python
def _build_execution_output(*, asset_frames: dict[str, pd.DataFrame], execution_cfg: dict[str, Any], portfolio_weights: pd.DataFrame | None, performance: BacktestResult | PortfolioPerformance, alignment: str) -> tuple[dict[str, Any], pd.DataFrame | None]
```

**Περιγραφή**

Handle execution output inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `asset_frames`: `dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `execution_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `portfolio_weights`: `pd.DataFrame | None`. Series/DataFrame βαρών ή exposure allocations.
- `performance`: `BacktestResult | PortfolioPerformance`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `alignment`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `tuple[dict[str, Any], pd.DataFrame | None]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `_data_stats_payload`

**Signature**

```python
def _data_stats_payload(data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict[str, Any]
```

**Περιγραφή**

Handle data stats payload inside the experiment orchestration layer. The helper isolates one

**Παράμετροι**

- `data`: `pd.DataFrame | dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._save_artifacts()`.

##### `_resolved_feature_columns`

**Signature**

```python
def _resolved_feature_columns(model_meta: dict[str, Any]) -> list[str] | dict[str, list[str]] | None
```

**Περιγραφή**

Handle resolved feature columns inside the experiment orchestration layer. The helper

**Παράμετροι**

- `model_meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `list[str] | dict[str, list[str]] | None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._save_artifacts()`.

##### `_save_artifacts`

**Signature**

```python
def _save_artifacts(*, run_dir: Path, cfg: dict[str, Any], data: pd.DataFrame | dict[str, pd.DataFrame], performance: BacktestResult | PortfolioPerformance, model_meta: dict[str, Any], evaluation: dict[str, Any], monitoring: dict[str, Any], execution: dict[str, Any], execution_orders: pd.DataFrame | None, portfolio_weights: pd.DataFrame | None, portfolio_diagnostics: pd.DataFrame | None, portfolio_meta: dict[str, Any], storage_meta: dict[str, Any], run_metadata: dict[str, Any], config_hash_sha256: str, data_fingerprint: dict[str, Any]) -> dict[str, str]
```

**Περιγραφή**

Handle artifacts inside the experiment orchestration layer. The helper isolates one focused

**Παράμετροι**

- `run_dir`: `Path`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `data`: `pd.DataFrame | dict[str, pd.DataFrame]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `performance`: `BacktestResult | PortfolioPerformance`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `model_meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `evaluation`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `monitoring`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `execution`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `execution_orders`: `pd.DataFrame | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `portfolio_weights`: `pd.DataFrame | None`. Series/DataFrame βαρών ή exposure allocations.
- `portfolio_diagnostics`: `pd.DataFrame | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `portfolio_meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `storage_meta`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `run_metadata`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `config_hash_sha256`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `data_fingerprint`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, str]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Συνθετική πολυπλοκότητα: περίπου O(A * N + T * A + I/O), όπου A=assets, N=rows ανά asset, T=χρονικά βήματα. Κυριαρχείται από feature/model/backtest υπορουτίνες και όχι από τον coordinator ίδιο.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `run_experiment`

**Signature**

```python
def run_experiment(config_path: str | Path) -> ExperimentResult
```

**Περιγραφή**

Run experiment end to end for the experiment orchestration layer. The function coordinates a

**Παράμετροι**

- `config_path`: `str | Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `ExperimentResult`.

**Λογική Βήμα-Βήμα**

1. Φορτώνει και επικυρώνει το YAML config μέσω του configuration layer.
2. Εφαρμόζει deterministic runtime settings, seeds και thread limits.
3. Φορτώνει raw asset frames από provider ή snapshot cache και επιβάλλει PIT/data contracts.
4. Υπολογίζει data fingerprint για reproducibility πριν από downstream μετασχηματισμούς.
5. Εκτελεί διαδοχικά feature steps ανά asset, και προαιρετικά αποθηκεύει processed snapshot.
6. Τρέχει το model layer ανά asset, καταγράφει OOS predictions, folds και classification metrics.
7. Μετασχηματίζει predictions/features σε signals μέσω του registry-driven signal layer.
8. Αποφασίζει αν η run είναι single-asset ή portfolio και εκτελεί το κατάλληλο backtest path.
9. Παράγει evaluation summary, monitoring report, paper execution orders και run artifacts.
10. Επιστρέφει `ExperimentResult` ως in-memory aggregate object για downstream use ή CLI execution.

**Edge Cases**: Αποτυγχάνει νωρίς αν λείπουν σύμβολα, columns backtest, volatility column για vol targeting ή valid folds. Διακλαδώνει διαφορετικά για single-asset και portfolio mode.

**Side Effects**: Εκτυπώνει στο stdout.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Συνθετική πολυπλοκότητα: περίπου O(A * N + T * A + I/O), όπου A=assets, N=rows ανά asset, T=χρονικά βήματα. Κυριαρχείται από feature/model/backtest υπορουτίνες και όχι από τον coordinator ίδιο.

**Πού Καλείται στο Pipeline**: `tests.test_runner_extensions.test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution()`.

### 4.12 Package `src/models`

Package του repository.

#### Αρχείο `src/models/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 0 LOC, 0 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Το module δεν εξαρτάται άμεσα από άλλα imports ή είναι κενό export surface.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/models/lightgbm_baseline.py`

**Σκοπός**: Legacy/baseline modeling helpers για notebooks ή lightweight experiments, όχι ο βασικός production orchestrator.

**Βασικά Μεγέθη**: 128 LOC, 7 import blocks, 0 global constants, 1 classes, 5 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `dataclasses` εισάγονται `dataclass`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `typing` εισάγονται `Sequence`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `lightgbm` εισάγονται `LGBMRegressor`. Ρόλος: Model training / αξιολόγηση classification models.
- Από `src.features.lags` εισάγονται `add_lagged_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `LGBMBaselineConfig`: βάσεις χωρίς explicit base classes. Store the default hyperparameters used by the lightweight LightGBM baseline so notebooks and
  Πεδία:
  - `n_estimators`: `int`. Προεπιλογή: `400`.
  - `learning_rate`: `float`. Προεπιλογή: `0.03`.
  - `max_depth`: `int`. Προεπιλογή: `4`.
  - `subsample`: `float`. Προεπιλογή: `0.8`.
  - `colsample_bytree`: `float`. Προεπιλογή: `0.8`.
  - `min_child_samples`: `int`. Προεπιλογή: `40`.
  - `random_state`: `int`. Προεπιλογή: `7`.

**Functions**

##### `default_feature_columns`

**Signature**

```python
def default_feature_columns(df: pd.DataFrame) -> list[str]
```

**Περιγραφή**

Select a reasonable feature set if the notebook does not override.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.

**Return Type**: `list[str]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.models.infer_feature_columns()`.

##### `train_regressor`

**Signature**

```python
def train_regressor(train_df: pd.DataFrame, feature_cols: Sequence[str], target_col: str, cfg: LGBMBaselineConfig | None = None) -> LGBMRegressor
```

**Περιγραφή**

Fit a LightGBM regressor on the provided split.

**Παράμετροι**

- `train_df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `feature_cols`: `Sequence[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `target_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `cfg`: `LGBMBaselineConfig | None`. Configuration mapping με domain-specific παραμέτρους. Προεπιλογή: `None`.

**Return Type**: `LGBMRegressor`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Εκπαιδεύει estimator object και άρα μεταβάλλει internal model state.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `predict_returns`

**Signature**

```python
def predict_returns(model: LGBMRegressor, df: pd.DataFrame, feature_cols: Sequence[str], pred_col: str = 'pred_next_ret') -> pd.DataFrame
```

**Περιγραφή**

Generate next-period return predictions and attach to dataframe.

**Παράμετροι**

- `model`: `LGBMRegressor`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `feature_cols`: `Sequence[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `pred_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'pred_next_ret'`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `prediction_to_signal`

**Signature**

```python
def prediction_to_signal(df: pd.DataFrame, pred_col: str = 'pred_next_ret', signal_col: str = 'signal_lgb', long_threshold: float = 0.0, short_threshold: float | None = None) -> pd.DataFrame
```

**Περιγραφή**

Convert predicted returns to a {-1,0,1} trading signal.

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `pred_col`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `'pred_next_ret'`.
- `signal_col`: `str`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης. Προεπιλογή: `'signal_lgb'`.
- `long_threshold`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.0`.
- `short_threshold`: `float | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `train_test_split_time`

**Signature**

```python
def train_test_split_time(df: pd.DataFrame, train_frac: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]
```

**Περιγραφή**

Time-ordered split (no shuffling).

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.
- `train_frac`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.7`.

**Return Type**: `tuple[pd.DataFrame, pd.DataFrame]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ValueError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

### 4.13 Package `src/utils`

Infrastructure utilities για paths, config normalization, reproducibility και run metadata.

#### Αρχείο `src/utils/__init__.py`

**Σκοπός**: Public API surface που επανεξάγει symbols του package ώστε τα imports ανώτερου layer να μένουν σταθερά.

**Βασικά Μεγέθη**: 0 LOC, 0 import blocks, 0 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Το module δεν εξαρτάται άμεσα από άλλα imports ή είναι κενό export surface.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `src/utils/config.py`

**Σκοπός**: Configuration loader/validator με inheritance μέσω `extends`, defaults, normalization paths και semantic validation blocks.

**Βασικά Μεγέθη**: 590 LOC, 7 import blocks, 0 global constants, 1 classes, 22 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `os` εισάγονται `os`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `pathlib` εισάγονται `Path`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `typing` εισάγονται `Any`, `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `yaml` εισάγονται `yaml`. Ρόλος: Serialization / configuration parsing.
- Από `src.utils.paths` εισάγονται `CONFIG_DIR`, `PROJECT_ROOT`, `in_project`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.utils.repro` εισάγονται `RuntimeConfigError`, `validate_runtime_config`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- `ConfigError`: βάσεις ValueError. Raised for invalid or inconsistent experiment configs.

**Functions**

##### `_resolve_config_path`

**Signature**

```python
def _resolve_config_path(config_path: str | Path) -> Path
```

**Περιγραφή**

Resolve a config path relative to CONFIG_DIR and verify it exists.

**Παράμετροι**

- `config_path`: `str | Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `Path`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`, `FileNotFoundError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config._load_with_extends()`, `src.utils.config.load_experiment_config()`.

##### `_load_yaml`

**Signature**

```python
def _load_yaml(path: Path) -> dict[str, Any]
```

**Περιγραφή**

Handle YAML inside the infrastructure layer. The helper isolates one focused responsibility

**Παράμετροι**

- `path`: `Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config._load_with_extends()`.

##### `_deep_update`

**Signature**

```python
def _deep_update(base: Mapping[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Recursively merge mappings; lists and scalars are overwritten.

**Παράμετροι**

- `base`: `Mapping[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `updates`: `Mapping[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config._deep_update()`, `src.utils.config._load_with_extends()`.

##### `_load_with_extends`

**Signature**

```python
def _load_with_extends(path: Path, seen: set[Path] | None = None) -> dict[str, Any]
```

**Περιγραφή**

Handle with extends inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `path`: `Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.
- `seen`: `set[Path] | None`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `None`.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config._load_with_extends()`, `src.utils.config.load_experiment_config()`.

##### `_default_risk_block`

**Signature**

```python
def _default_risk_block(risk: dict[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Handle default risk block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `risk`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_default_data_block`

**Signature**

```python
def _default_data_block(data: dict[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Handle default data block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `data`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_default_backtest_block`

**Signature**

```python
def _default_backtest_block(backtest: dict[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Handle default backtest block inside the infrastructure layer. The helper isolates one

**Παράμετροι**

- `backtest`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_default_portfolio_block`

**Signature**

```python
def _default_portfolio_block(portfolio: dict[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Handle default portfolio block inside the infrastructure layer. The helper isolates one

**Παράμετροι**

- `portfolio`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_default_monitoring_block`

**Signature**

```python
def _default_monitoring_block(monitoring: dict[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Handle default monitoring block inside the infrastructure layer. The helper isolates one

**Παράμετροι**

- `monitoring`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_default_execution_block`

**Signature**

```python
def _default_execution_block(execution: dict[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Handle default execution block inside the infrastructure layer. The helper isolates one

**Παράμετροι**

- `execution`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_resolve_logging_block`

**Signature**

```python
def _resolve_logging_block(logging_cfg: dict[str, Any], config_path: Path) -> dict[str, Any]
```

**Περιγραφή**

Handle logging block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `logging_cfg`: `dict[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `config_path`: `Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_data_block`

**Signature**

```python
def _validate_data_block(data: dict[str, Any]) -> None
```

**Περιγραφή**

Handle data block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `data`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_inject_api_key_from_env`

**Signature**

```python
def _inject_api_key_from_env(data: dict[str, Any]) -> None
```

**Περιγραφή**

Handle inject API key from env inside the infrastructure layer. The helper isolates one

**Παράμετροι**

- `data`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_features_block`

**Signature**

```python
def _validate_features_block(features: Any) -> None
```

**Περιγραφή**

Handle features block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `features`: `Any`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_model_block`

**Signature**

```python
def _validate_model_block(model: dict[str, Any]) -> None
```

**Περιγραφή**

Handle model block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `model`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_signals_block`

**Signature**

```python
def _validate_signals_block(signals: dict[str, Any]) -> None
```

**Περιγραφή**

Handle signals block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `signals`: `dict[str, Any]`. Χρονοσειρά σήματος ή κατεύθυνσης θέσης.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_risk_block`

**Signature**

```python
def _validate_risk_block(risk: dict[str, Any]) -> None
```

**Περιγραφή**

Handle risk block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `risk`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_backtest_block`

**Signature**

```python
def _validate_backtest_block(backtest: dict[str, Any]) -> None
```

**Περιγραφή**

Handle backtest block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `backtest`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_portfolio_block`

**Signature**

```python
def _validate_portfolio_block(portfolio: dict[str, Any]) -> None
```

**Περιγραφή**

Handle portfolio block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `portfolio`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_monitoring_block`

**Signature**

```python
def _validate_monitoring_block(monitoring: dict[str, Any]) -> None
```

**Περιγραφή**

Handle monitoring block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `monitoring`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `_validate_execution_block`

**Signature**

```python
def _validate_execution_block(execution: dict[str, Any]) -> None
```

**Περιγραφή**

Handle execution block inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `execution`: `dict[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`.

##### `load_experiment_config`

**Signature**

```python
def load_experiment_config(config_path: str | Path) -> dict[str, Any]
```

**Περιγραφή**

Load an experiment YAML, apply inheritance, defaults, validation,

**Παράμετροι**

- `config_path`: `str | Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Επιλύει path του config είτε σχετικό με root είτε σχετικό με `config/`.
2. Φορτώνει inheritance chain μέσω `extends` και κάνει deep merge των mapping blocks.
3. Συμπληρώνει defaults για data, runtime, risk, backtest, portfolio, monitoring, execution και logging.
4. Εγχέει API keys από environment variables όπου το config δηλώνει `api_key_env`.
5. Επικυρώνει κάθε block με domain-specific semantic checks πριν χρησιμοποιηθεί από το runtime.
6. Επιστρέφει plain dict έτοιμο για orchestration, hashing και artifact persistence.

**Edge Cases**: Μη έγκυρα paths, missing files, empty datasets ή απουσία required columns πρέπει να θεωρούνται expected failure modes.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `ConfigError`.

**Big-O / Πολυπλοκότητα**: O(size of config tree). Το κόστος είναι μικρό και γραμμικό ως προς τα YAML nodes και validation checks.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`, `tests.test_reproducibility.test_compute_config_hash_ignores_config_path_field()`, `tests.test_reproducibility.test_runtime_defaults_are_loaded_from_config()`.

#### Αρχείο `src/utils/paths.py`

**Σκοπός**: Υλοποίηση του module `paths.py` μέσα στο package `utils`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 63 LOC, 2 import blocks, 1 global constants, 0 classes, 3 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `pathlib` εισάγονται `Path`. Ρόλος: Infrastructure / filesystem / environment introspection.

**Global Constants / Module State**

- `_THIS_FILE`: Global constant με τιμή `Path(__file__).resolve()` που επηρεάζει module-level συμπεριφορά.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `in_project`

**Signature**

```python
def in_project(*parts: str | Path) -> Path
```

**Περιγραφή**

Handle in project inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `*parts`: `str | Path`. Επιπλέον positional arguments.

**Return Type**: `Path`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`, `src.utils.config._default_data_block()`, `src.utils.config._resolve_logging_block()`.

##### `ensure_directories_exist`

**Signature**

```python
def ensure_directories_exist() -> None
```

**Περιγραφή**

Handle ensure directories exist inside the infrastructure layer. The helper isolates one

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `describe_paths`

**Signature**

```python
def describe_paths() -> None
```

**Περιγραφή**

Describe paths for quick inspection while working inside the infrastructure layer. The

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Εκτυπώνει στο stdout.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

#### Αρχείο `src/utils/repro.py`

**Σκοπός**: Υλοποίηση του module `repro.py` μέσα στο package `utils`, με ρόλο συμβατό με τη συνολική layered αρχιτεκτονική του repository.

**Βασικά Μεγέθη**: 149 LOC, 5 import blocks, 2 global constants, 1 classes, 3 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `os` εισάγονται `os`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `random` εισάγονται `random`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `typing` εισάγονται `Any`, `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.

**Global Constants / Module State**

- `_ALLOWED_REPRO_MODES`: Whitelist ορθών τιμών για validation branches. Τρέχουσα τιμή: `{'strict', 'relaxed'}`.
- `_THREAD_ENV_VARS`: Global constant με τιμή `('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')` που επηρεάζει module-level συμπεριφορά.

**Classes**

- `RuntimeConfigError`: βάσεις ValueError. Raised for invalid runtime/reproducibility configuration.

**Functions**

##### `normalize_runtime_config`

**Signature**

```python
def normalize_runtime_config(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]
```

**Περιγραφή**

Normalize runtime config into a canonical representation used throughout the infrastructure

**Παράμετροι**

- `runtime_cfg`: `Mapping[str, Any] | None`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.repro.validate_runtime_config()`.

##### `validate_runtime_config`

**Signature**

```python
def validate_runtime_config(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]
```

**Περιγραφή**

Validate runtime config before downstream logic depends on it. The function raises early

**Παράμετροι**

- `runtime_cfg`: `Mapping[str, Any] | None`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Ελέγχει τον τύπο και τα βασικά structural preconditions του input.
2. Συγκεντρώνει violations αντί να προχωρήσει σε downstream logic.
3. Σηκώνει deterministic exception όταν εντοπίζει contract breach ή επιστρέφει lightweight metadata.

**Edge Cases**: Empty inputs, λάθος types, duplicate timestamps και missing required columns είναι συνήθη failure modes που αντιμετωπίζονται με άμεσο exception.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: `RuntimeConfigError`.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.utils.config.load_experiment_config()`, `src.utils.repro.apply_runtime_reproducibility()`, `tests.test_reproducibility.test_validate_runtime_config_rejects_invalid_threads()`.

##### `apply_runtime_reproducibility`

**Signature**

```python
def apply_runtime_reproducibility(runtime_cfg: Mapping[str, Any] | None) -> dict[str, Any]
```

**Περιγραφή**

Apply runtime reproducibility to the provided inputs in a controlled and reusable way. The

**Παράμετροι**

- `runtime_cfg`: `Mapping[str, Any] | None`. Configuration mapping με domain-specific παραμέτρους.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Κάνει copy ή normalization του input όπου χρειάζεται.
2. Εφαρμόζει μία συγκεκριμένη policy/transformation χωρίς να αναμιγνύει άσχετες ευθύνες.
3. Επιστρέφει transformed object και, όπου απαιτείται, metadata του applied step.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Μεταβολή process-level runtime state / environment variables / random seeds.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`, `tests.test_reproducibility.test_apply_runtime_reproducibility_sets_deterministic_numpy_stream()`.

#### Αρχείο `src/utils/run_metadata.py`

**Σκοπός**: Reproducibility metadata layer: hashing config/data, συλλογή environment/git metadata και artifact manifesting.

**Βασικά Μεγέθη**: 294 LOC, 14 import blocks, 1 global constants, 0 classes, 12 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `hashlib` εισάγονται `hashlib`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `json` εισάγονται `json`. Ρόλος: Serialization / configuration parsing.
- Από `platform` εισάγονται `platform`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `subprocess` εισάγονται `subprocess`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `sys` εισάγονται `sys`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `copy` εισάγονται `deepcopy`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.
- Από `datetime` εισάγονται `datetime`, `timezone`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.
- Από `importlib.metadata` εισάγονται `PackageNotFoundError`, `version`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.
- Από `pathlib` εισάγονται `Path`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `typing` εισάγονται `Any`, `Mapping`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.utils.paths` εισάγονται `PROJECT_ROOT`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- `_KEY_PACKAGES`: Global constant με τιμή `('numpy', 'pandas', 'scikit-learn', 'lightgbm', 'pyyaml', 'yfinance', 'requests')` που επηρεάζει module-level συμπεριφορά.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `_normalize_path_string`

**Signature**

```python
def _normalize_path_string(value: str, project_root: Path) -> str
```

**Περιγραφή**

Handle path string inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `value`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `project_root`: `Path`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `str`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.run_metadata._normalize_for_hash()`.

##### `_normalize_for_hash`

**Signature**

```python
def _normalize_for_hash(value: Any, project_root: Path) -> Any
```

**Περιγραφή**

Handle for hash inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `value`: `Any`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `project_root`: `Path`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `Any`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.utils.run_metadata._normalize_for_hash()`, `src.utils.run_metadata.compute_config_hash()`.

##### `_json_default`

**Signature**

```python
def _json_default(value: Any) -> Any
```

**Περιγραφή**

Handle JSON default inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `value`: `Any`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `Any`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Δεν εντοπίστηκαν άμεσοι εσωτερικοί callers. Πιθανή χρήση μέσω public API export, CLI invocation ή tests.

##### `canonical_json_dumps`

**Signature**

```python
def canonical_json_dumps(payload: Mapping[str, Any]) -> str
```

**Περιγραφή**

Handle canonical JSON dumps inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `payload`: `Mapping[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `str`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.run_metadata.compute_config_hash()`.

##### `compute_config_hash`

**Signature**

```python
def compute_config_hash(cfg: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> tuple[str, dict[str, Any]]
```

**Περιγραφή**

Compute config hash for the infrastructure layer. The helper keeps the calculation isolated

**Παράμετροι**

- `cfg`: `Mapping[str, Any]`. Configuration mapping με domain-specific παραμέτρους.
- `project_root`: `Path`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `PROJECT_ROOT`.

**Return Type**: `tuple[str, dict[str, Any]]`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`, `tests.test_reproducibility.test_compute_config_hash_ignores_config_path_field()`.

##### `compute_dataframe_fingerprint`

**Signature**

```python
def compute_dataframe_fingerprint(df: pd.DataFrame) -> dict[str, Any]
```

**Περιγραφή**

Compute dataframe fingerprint for the infrastructure layer. The helper keeps the calculation

**Παράμετροι**

- `df`: `pd.DataFrame`. Κύριο DataFrame input πάνω στο οποίο εκτελείται η λογική του module.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Κανονικοποιεί τα numeric inputs σε pandas/NumPy compatible μορφή.
2. Υπολογίζει το ζητούμενο στατιστικό μέγεθος ή signal/transformation.
3. Επιστρέφει το αποτέλεσμα με σταθερό naming/schema για reuse από ανώτερα layers.

**Edge Cases**: NaNs, empty series, division by zero και insufficient lookback history είναι τα κύρια edge cases. Συνήθως επιστρέφονται NaNs ή safe defaults αντί για silent extrapolation.

**Side Effects**: Εκτυπώνει στο stdout.

**Exceptions**: `TypeError`, `ValueError`.

**Big-O / Πολυπλοκότητα**: O(N * C) για sorting/hashing rows και columns.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`, `src.src_data.storage.build_dataset_snapshot_metadata()`, `tests.test_reproducibility.test_dataframe_fingerprint_is_stable_across_row_and_column_order()`.

##### `_safe_git`

**Signature**

```python
def _safe_git(args: list[str]) -> str | None
```

**Περιγραφή**

Handle safe Git inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `args`: `list[str]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `str | None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Εξωτερικό I/O προς δίκτυο ή subprocess.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.run_metadata.collect_git_metadata()`.

##### `collect_git_metadata`

**Signature**

```python
def collect_git_metadata() -> dict[str, Any]
```

**Περιγραφή**

Collect Git metadata from the local environment and package it into a stable structure for

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.run_metadata.build_run_metadata()`.

##### `collect_environment_metadata`

**Signature**

```python
def collect_environment_metadata() -> dict[str, Any]
```

**Περιγραφή**

Collect environment metadata from the local environment and package it into a stable

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: `src.utils.run_metadata.build_run_metadata()`.

##### `build_run_metadata`

**Signature**

```python
def build_run_metadata(*, config_path: str | Path, runtime_applied: Mapping[str, Any], config_hash_sha256: str, config_hash_input: Mapping[str, Any], data_fingerprint: Mapping[str, Any], data_context: Mapping[str, Any], model_meta: Mapping[str, Any]) -> dict[str, Any]
```

**Περιγραφή**

Build run metadata as an explicit intermediate object used by the infrastructure pipeline.

**Παράμετροι**

- `config_path`: `str | Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.
- `runtime_applied`: `Mapping[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `config_hash_sha256`: `str`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `config_hash_input`: `Mapping[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `data_fingerprint`: `Mapping[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `data_context`: `Mapping[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.
- `model_meta`: `Mapping[str, Any]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Συνδυάζει config hash, runtime settings, data fingerprint, git metadata και environment metadata.
2. Παράγει σταθερό JSON-serializable payload που τεκμηριώνει πλήρως τις συνθήκες μιας εκτέλεσης.

**Edge Cases**: Η συνάρτηση υποθέτει ότι τα upstream contracts έχουν ήδη ελεγχθεί, αλλά εξακολουθεί να αποτυγχάνει αν τα inputs είναι κενά ή μη ευθυγραμμισμένα.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.experiments.runner.run_experiment()`.

##### `file_sha256`

**Signature**

```python
def file_sha256(path: str | Path) -> str
```

**Περιγραφή**

Handle file sha256 inside the infrastructure layer. The helper isolates one focused

**Παράμετροι**

- `path`: `str | Path`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `str`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `src.utils.run_metadata.build_artifact_manifest()`.

##### `build_artifact_manifest`

**Signature**

```python
def build_artifact_manifest(artifacts: Mapping[str, str | Path]) -> dict[str, Any]
```

**Περιγραφή**

Build artifact manifest as an explicit intermediate object used by the infrastructure

**Παράμετροι**

- `artifacts`: `Mapping[str, str | Path]`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `dict[str, Any]`.

**Λογική Βήμα-Βήμα**

1. Συγκεντρώνει inputs από το ανώτερο orchestration layer.
2. Συνθέτει νέο ενδιάμεσο object ή report με deterministic schema.
3. Επιστρέφει αποτέλεσμα έτοιμο για downstream consumption ή persistence.

**Edge Cases**: Η συνάρτηση υποθέτει ότι τα upstream contracts έχουν ήδη ελεγχθεί, αλλά εξακολουθεί να αποτυγχάνει αν τα inputs είναι κενά ή μη ευθυγραμμισμένα.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά κανόνα γραμμική ως προς το μέγεθος του input object που επεξεργάζεται ή serializes.

**Πού Καλείται στο Pipeline**: `src.experiments.runner._save_artifacts()`, `tests.test_reproducibility.test_artifact_manifest_contains_file_hashes()`.

### 4.14 Package `tests`

Regression suite που κωδικοποιεί τις θεμελιώδεις υποθέσεις correctness, anti-leakage και reproducibility.

#### Αρχείο `tests/conftest.py`

**Σκοπός**: Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions.

**Βασικά Μεγέθη**: 8 LOC, 3 import blocks, 1 global constants, 0 classes, 0 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `sys` εισάγονται `sys`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `pathlib` εισάγονται `Path`. Ρόλος: Infrastructure / filesystem / environment introspection.

**Global Constants / Module State**

- `PROJECT_ROOT`: Global constant με τιμή `Path(__file__).resolve().parents[1]` που επηρεάζει module-level συμπεριφορά.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

- Δεν υπάρχουν top-level functions. Ο ρόλος του αρχείου είναι κυρίως export surface ή abstract interface.

#### Αρχείο `tests/test_contracts_metrics_pit.py`

**Σκοπός**: Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions.

**Βασικά Μεγέθη**: 205 LOC, 8 import blocks, 0 global constants, 0 classes, 7 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pytest` εισάγονται `pytest`. Ρόλος: Testing framework για automated regression checks.
- Από `src.evaluation.metrics` εισάγονται `compute_backtest_metrics`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.experiments.contracts` εισάγονται `TargetContract`, `validate_feature_target_contract`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.experiments.models` εισάγονται `train_lightgbm_classifier`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.src_data.pit` εισάγονται `align_ohlcv_timestamps`, `apply_corporate_actions_policy`, `assert_symbol_in_snapshot`, `load_universe_snapshot`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `_synthetic_frame`

**Signature**

```python
def _synthetic_frame(n: int = 240) -> pd.DataFrame
```

**Περιγραφή**

Verify that synthetic frame behaves as expected under a representative regression scenario.

**Παράμετροι**

- `n`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `240`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `tests.test_contracts_metrics_pit.test_forward_horizon_guard_trims_train_rows_in_time_split()`.

##### `test_forward_horizon_guard_trims_train_rows_in_time_split`

**Signature**

```python
def test_forward_horizon_guard_trims_train_rows_in_time_split() -> None
```

**Περιγραφή**

Verify that forward horizon guard trims train rows in time split behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_feature_contract_rejects_target_like_feature_columns`

**Signature**

```python
def test_feature_contract_rejects_target_like_feature_columns() -> None
```

**Περιγραφή**

Verify that feature contract rejects target like feature columns behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_metrics_suite_includes_risk_and_cost_attribution`

**Signature**

```python
def test_metrics_suite_includes_risk_and_cost_attribution() -> None
```

**Περιγραφή**

Verify that metrics suite includes risk and cost attribution behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_align_ohlcv_timestamps_sorts_and_deduplicates`

**Signature**

```python
def test_align_ohlcv_timestamps_sorts_and_deduplicates() -> None
```

**Περιγραφή**

Verify that align OHLCV timestamps sorts and deduplicates behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_apply_corporate_actions_policy_adj_close_ratio`

**Signature**

```python
def test_apply_corporate_actions_policy_adj_close_ratio() -> None
```

**Περιγραφή**

Verify that corporate actions policy adj close ratio behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_universe_snapshot_asof_membership_check`

**Signature**

```python
def test_universe_snapshot_asof_membership_check(tmp_path) -> None
```

**Περιγραφή**

Verify that universe snapshot asof membership check behaves as expected under a

**Παράμετροι**

- `tmp_path`: `χωρίς annotation`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

#### Αρχείο `tests/test_core.py`

**Σκοπός**: Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions.

**Βασικά Μεγέθη**: 167 LOC, 8 import blocks, 0 global constants, 0 classes, 7 functions.

**Ανάλυση Imports**

- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pytest` εισάγονται `pytest`. Ρόλος: Testing framework για automated regression checks.
- Από `src.features.returns` εισάγονται `compute_returns`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.features.technical.trend` εισάγονται `add_trend_features`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.src_data.validation` εισάγονται `validate_ohlcv`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.backtesting.engine` εισάγονται `run_backtest`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.signals.volatility_signal` εισάγονται `compute_volatility_regime_signal`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `test_compute_returns_simple_and_log`

**Signature**

```python
def test_compute_returns_simple_and_log() -> None
```

**Περιγραφή**

Verify that returns simple and log behaves as expected under a representative regression

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_add_trend_features_columns`

**Signature**

```python
def test_add_trend_features_columns() -> None
```

**Περιγραφή**

Verify that trend features columns behaves as expected under a representative regression

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_validate_ohlcv_flags_invalid_high_low`

**Signature**

```python
def test_validate_ohlcv_flags_invalid_high_low() -> None
```

**Περιγραφή**

Verify that OHLCV flags invalid high low behaves as expected under a representative

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_run_backtest_costs_and_slippage_reduce_returns`

**Signature**

```python
def test_run_backtest_costs_and_slippage_reduce_returns() -> None
```

**Περιγραφή**

Verify that backtest costs and slippage reduce returns behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_run_backtest_log_returns_are_converted`

**Signature**

```python
def test_run_backtest_log_returns_are_converted() -> None
```

**Περιγραφή**

Verify that backtest log returns are converted behaves as expected under a representative

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_run_backtest_charges_initial_entry_turnover`

**Signature**

```python
def test_run_backtest_charges_initial_entry_turnover() -> None
```

**Περιγραφή**

Verify that backtest charges initial entry turnover behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_volatility_regime_signal_is_causal_by_default`

**Signature**

```python
def test_volatility_regime_signal_is_causal_by_default() -> None
```

**Περιγραφή**

Verify that volatility regime signal is causal by default behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

#### Αρχείο `tests/test_no_lookahead.py`

**Σκοπός**: Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions.

**Βασικά Μεγέθη**: 150 LOC, 4 import blocks, 0 global constants, 0 classes, 5 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.experiments.models` εισάγονται `train_lightgbm_classifier`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `_synthetic_price_frame`

**Signature**

```python
def _synthetic_price_frame(n: int = 260) -> pd.DataFrame
```

**Περιγραφή**

Verify that synthetic price frame behaves as expected under a representative regression

**Παράμετροι**

- `n`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `260`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Κατά βάση O(n) σε pandas vectorized primitives, με το constant factor να εξαρτάται από rolling/ewm internals.

**Πού Καλείται στο Pipeline**: `tests.test_no_lookahead.test_binary_forward_target_keeps_tail_labels_nan()`, `tests.test_no_lookahead.test_purged_splits_respect_anti_leakage_gap()`, `tests.test_no_lookahead.test_quantile_target_uses_train_only_distribution_per_fold()`, `tests.test_no_lookahead.test_walk_forward_predictions_are_oos_only()`.

##### `test_walk_forward_predictions_are_oos_only`

**Signature**

```python
def test_walk_forward_predictions_are_oos_only() -> None
```

**Περιγραφή**

Verify that walk forward predictions are out-of-sample only behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_purged_splits_respect_anti_leakage_gap`

**Signature**

```python
def test_purged_splits_respect_anti_leakage_gap() -> None
```

**Περιγραφή**

Verify that purged splits respect anti leakage gap behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_binary_forward_target_keeps_tail_labels_nan`

**Signature**

```python
def test_binary_forward_target_keeps_tail_labels_nan() -> None
```

**Περιγραφή**

Verify that binary forward target keeps tail labels nan behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_quantile_target_uses_train_only_distribution_per_fold`

**Signature**

```python
def test_quantile_target_uses_train_only_distribution_per_fold() -> None
```

**Περιγραφή**

Verify that quantile target uses train only distribution per fold behaves as expected under

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

#### Αρχείο `tests/test_portfolio.py`

**Σκοπός**: Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions.

**Βασικά Μεγέθη**: 203 LOC, 4 import blocks, 0 global constants, 0 classes, 6 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.portfolio` εισάγονται `PortfolioConstraints`, `apply_constraints`, `build_weights_from_signals_over_time`, `compute_portfolio_performance`, `optimize_mean_variance`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `test_apply_constraints_respects_bounds_group_gross_and_turnover`

**Signature**

```python
def test_apply_constraints_respects_bounds_group_gross_and_turnover() -> None
```

**Περιγραφή**

Verify that constraints respects bounds group gross and turnover behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_build_weights_from_signals_over_time_respects_constraints`

**Signature**

```python
def test_build_weights_from_signals_over_time_respects_constraints() -> None
```

**Περιγραφή**

Verify that weights from signals over time respects constraints behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_optimize_mean_variance_respects_core_constraints`

**Signature**

```python
def test_optimize_mean_variance_respects_core_constraints() -> None
```

**Περιγραφή**

Verify that optimize mean variance respects core constraints behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_compute_portfolio_performance_uses_shifted_weights`

**Signature**

```python
def test_compute_portfolio_performance_uses_shifted_weights() -> None
```

**Περιγραφή**

Verify that portfolio performance uses shifted weights behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_compute_portfolio_performance_charges_initial_turnover`

**Signature**

```python
def test_compute_portfolio_performance_charges_initial_turnover() -> None
```

**Περιγραφή**

Verify that portfolio performance charges initial turnover behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_optimize_mean_variance_fallback_respects_max_gross_leverage`

**Signature**

```python
def test_optimize_mean_variance_fallback_respects_max_gross_leverage() -> None
```

**Περιγραφή**

Verify that optimize mean variance fallback respects max gross leverage behaves as expected

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

#### Αρχείο `tests/test_reproducibility.py`

**Σκοπός**: Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions.

**Βασικά Μεγέθη**: 117 LOC, 8 import blocks, 0 global constants, 0 classes, 6 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `copy` εισάγονται `deepcopy`. Ρόλος: Γενική βιβλιοθήκη ή utility dependency.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pytest` εισάγονται `pytest`. Ρόλος: Testing framework για automated regression checks.
- Από `src.utils.config` εισάγονται `load_experiment_config`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.utils.repro` εισάγονται `RuntimeConfigError`, `apply_runtime_reproducibility`, `validate_runtime_config`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.utils.run_metadata` εισάγονται `build_artifact_manifest`, `compute_config_hash`, `compute_dataframe_fingerprint`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `test_runtime_defaults_are_loaded_from_config`

**Signature**

```python
def test_runtime_defaults_are_loaded_from_config() -> None
```

**Περιγραφή**

Verify that runtime defaults are loaded from config behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_validate_runtime_config_rejects_invalid_threads`

**Signature**

```python
def test_validate_runtime_config_rejects_invalid_threads() -> None
```

**Περιγραφή**

Verify that runtime config rejects invalid threads behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_apply_runtime_reproducibility_sets_deterministic_numpy_stream`

**Signature**

```python
def test_apply_runtime_reproducibility_sets_deterministic_numpy_stream() -> None
```

**Περιγραφή**

Verify that runtime reproducibility sets deterministic numpy stream behaves as expected

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_compute_config_hash_ignores_config_path_field`

**Signature**

```python
def test_compute_config_hash_ignores_config_path_field() -> None
```

**Περιγραφή**

Verify that config hash ignores config path field behaves as expected under a representative

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_dataframe_fingerprint_is_stable_across_row_and_column_order`

**Signature**

```python
def test_dataframe_fingerprint_is_stable_across_row_and_column_order() -> None
```

**Περιγραφή**

Verify that dataframe fingerprint is stable across row and column order behaves as expected

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Εκτυπώνει στο stdout.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_artifact_manifest_contains_file_hashes`

**Signature**

```python
def test_artifact_manifest_contains_file_hashes(tmp_path) -> None
```

**Περιγραφή**

Verify that artifact manifest contains file hashes behaves as expected under a

**Παράμετροι**

- `tmp_path`: `χωρίς annotation`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

#### Αρχείο `tests/test_runner_extensions.py`

**Σκοπός**: Integration-style tests που επιβεβαιώνουν end-to-end orchestration features πέρα από τον αρχικό πυρήνα.

**Βασικά Μεγέθη**: 223 LOC, 10 import blocks, 0 global constants, 0 classes, 5 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `json` εισάγονται `json`. Ρόλος: Serialization / configuration parsing.
- Από `pathlib` εισάγονται `Path`. Ρόλος: Infrastructure / filesystem / environment introspection.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `pandas` εισάγονται `pd`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.experiments.runner` εισάγονται `runner_mod`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.execution.paper` εισάγονται `build_rebalance_orders`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.experiments.models` εισάγονται `train_logistic_regression_classifier`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.portfolio.construction` εισάγονται `PortfolioPerformance`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.
- Από `src.src_data.storage` εισάγονται `load_dataset_snapshot`, `save_dataset_snapshot`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `_synthetic_ohlcv`

**Signature**

```python
def _synthetic_ohlcv(*, periods: int = 180, seed: int = 0, amplitude: float = 0.01) -> pd.DataFrame
```

**Περιγραφή**

Verify that synthetic OHLCV behaves as expected under a representative regression scenario.

**Παράμετροι**

- `periods`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `180`.
- `seed`: `int`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0`.
- `amplitude`: `float`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step. Προεπιλογή: `0.01`.

**Return Type**: `pd.DataFrame`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: `tests.test_runner_extensions.test_dataset_snapshot_roundtrip()`, `tests.test_runner_extensions.test_logistic_regression_model_registry_outputs_oos_metrics()`, `tests.test_runner_extensions.test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution()`.

##### `test_dataset_snapshot_roundtrip`

**Signature**

```python
def test_dataset_snapshot_roundtrip(tmp_path) -> None
```

**Περιγραφή**

Verify that dataset snapshot roundtrip behaves as expected under a representative regression

**Παράμετροι**

- `tmp_path`: `χωρίς annotation`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_build_rebalance_orders_reports_share_deltas`

**Signature**

```python
def test_build_rebalance_orders_reports_share_deltas() -> None
```

**Περιγραφή**

Verify that rebalance orders reports share deltas behaves as expected under a representative

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_logistic_regression_model_registry_outputs_oos_metrics`

**Signature**

```python
def test_logistic_regression_model_registry_outputs_oos_metrics() -> None
```

**Περιγραφή**

Verify that logistic regression model registry outputs out-of-sample metrics behaves as

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution`

**Signature**

```python
def test_run_experiment_supports_multi_asset_portfolio_storage_monitoring_and_execution(tmp_path, monkeypatch) -> None
```

**Περιγραφή**

Verify that experiment supports multi asset portfolio storage monitoring and execution

**Παράμετροι**

- `tmp_path`: `χωρίς annotation`. Path σε αρχείο ή φάκελο που χρησιμοποιείται για loading/saving.
- `monkeypatch`: `χωρίς annotation`. Είσοδος που καθορίζει τη συμπεριφορά του αλγορίθμου ή του transformation step.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Filesystem I/O (δημιουργία/γραφή αρχείων ή φακέλων).

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

#### Αρχείο `tests/test_time_splits.py`

**Σκοπός**: Regression test module που κωδικοποιεί συγκεκριμένα invariants του framework και προστατεύει από behavioural regressions.

**Βασικά Μεγέθη**: 86 LOC, 3 import blocks, 0 global constants, 0 classes, 3 functions.

**Ανάλυση Imports**

- Από `__future__` εισάγονται `annotations`. Ρόλος: Γλωσσικό/infrastructure support για types, annotations και immutable-ish data structures.
- Από `numpy` εισάγονται `np`. Ρόλος: Αριθμητικός/vectorized υπολογισμός και time-series manipulation.
- Από `src.evaluation.time_splits` εισάγονται `build_time_splits`, `purged_walk_forward_split_indices`, `walk_forward_split_indices`. Ρόλος: Εσωτερική εξάρτηση του framework για composition ανά layer.

**Global Constants / Module State**

- Δεν ορίζονται global constants που να αλλάζουν runtime semantics πέρα από imports και docstrings.

**Classes**

- Δεν υπάρχουν classes. Το module είναι procedural/function-oriented.

**Functions**

##### `test_walk_forward_splits_are_time_ordered_and_non_overlapping`

**Signature**

```python
def test_walk_forward_splits_are_time_ordered_and_non_overlapping() -> None
```

**Περιγραφή**

Verify that walk forward splits are time ordered and non overlapping behaves as expected

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_purged_walk_forward_respects_purge_and_embargo`

**Signature**

```python
def test_purged_walk_forward_respects_purge_and_embargo() -> None
```

**Περιγραφή**

Verify that purged walk forward respects purge and embargo behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Πολυπλοκότητα τουλάχιστον γραμμική ως προς τις εισόδους του, συχνά O(n * k) λόγω nested iteration ή επαναλαμβανόμενων transformations.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.

##### `test_build_time_splits_uses_target_horizon_for_default_purge`

**Signature**

```python
def test_build_time_splits_uses_target_horizon_for_default_purge() -> None
```

**Περιγραφή**

Verify that time splits uses target horizon for default purge behaves as expected under a

**Παράμετροι**

- Δεν υπάρχουν ρητές παράμετροι πέρα από το implicit runtime context.

**Return Type**: `None`.

**Λογική Βήμα-Βήμα**

1. Υλοποιεί στοχευμένο helper responsibility με χαμηλή σύζευξη.
2. Προστατεύει το surrounding layer από επαναλαμβανόμενη boilerplate λογική.
3. Επιστρέφει deterministic output σύμφωνα με το local contract του module.

**Edge Cases**: Τα edge cases εξαρτώνται από το calling context, αλλά ο κώδικας παραμένει συντηρητικός και προτιμά explicit failure αντί για silent coercion.

**Side Effects**: Δεν έχει παρατηρήσιμα side effects πέρα από CPU/RAM consumption και την επιστροφή νέου object.

**Exceptions**: Δεν υπάρχουν ρητές `raise` εκφράσεις ή οι εξαιρέσεις προέρχονται έμμεσα από pandas/NumPy/scikit-learn I/O operations.

**Big-O / Πολυπλοκότητα**: Αμελητέα ή γραμμική πολυπλοκότητα σε σχέση με το input size του helper.

**Πού Καλείται στο Pipeline**: Χρησιμοποιείται ως test case entry point από το `pytest` discovery mechanism.
