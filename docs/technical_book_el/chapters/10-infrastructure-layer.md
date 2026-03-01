## 10. Infrastructure Layer

### 10.1 Paths

Το `src/utils/paths.py` καθορίζει `PROJECT_ROOT` δυναμικά από τη θέση του αρχείου και παράγει canonical paths
για `src`, `config`, `data`, `logs`, `tests` κ.λπ. Αυτή η επιλογή αποτρέπει hardcoded absolute paths στο
core runtime και επιτρέπει portable execution σε local, Docker και devcontainer περιβάλλοντα.

### 10.2 Reproducibility Runtime

Το `apply_runtime_reproducibility()` κάνει περισσότερα από απλό seeding:

- Θέτει `PYTHONHASHSEED`.
- Θέτει NumPy και Python RNG seeds.
- Περιορίζει thread env vars όταν ο config ζητά deterministic execution.
- Προαιρετικά προσπαθεί να ενεργοποιήσει deterministic PyTorch algorithms.

Αυτό είναι κρίσιμο σε quant research επειδή η reproducibility συχνά χαλά όχι από το model code αλλά από
threaded BLAS backends ή μη deterministic seeding across libraries.

### 10.3 Config/Data Hashing

Το `compute_config_hash()` αγνοεί το `config_path` field ώστε το ίδιο λογικό experiment να παράγει το ίδιο hash
ακόμη και αν μετακινηθεί το YAML. Το `compute_dataframe_fingerprint()` ταξινομεί rows/columns και normalizes
datetime indices πριν υπολογίσει SHA-256. Έτσι η αναπαραγωγιμότητα είναι structural και όχι εξαρτώμενη από
τυχαία row ordering.
