## 15. Refactor & Optimization Suggestions

### 15.1 Τεχνικό Χρέος

1. Το μεγάλο orchestration hotspot έχει διασπαστεί σε `src/experiments/orchestration/*`, αλλά το `src/experiments/registry.py` παραμένει ενιαίο σημείο dynamic wiring για features/models/signals.
2. Το config layer έχει πλέον `loader/defaults/validation/schemas`, αλλά τα nested blocks εξακολουθούν να κουβαλούν αρκετά `dict[str, Any]` extras για συμβατότητα.
3. Το artifact-centric logging είναι χρήσιμο, αλλά λείπει structured application logger για operational observability σε long-running jobs.
4. Το `src/models/lightgbm_baseline.py` χρησιμοποιεί `n_jobs=-1`, που δεν είναι απόλυτα ευθυγραμμισμένο με το strict reproducibility philosophy του υπόλοιπου framework.
5. Το optimizer fallback path επιτρέπει runtime warnings όταν του δοθούν pathological covariance matrices. Το test το θεωρεί αποδεκτό, αλλά production code θα ωφελούνταν από πιο καθαρή numerical sanitization.

### 15.2 Συγκεκριμένες Προτάσεις Refactor

1. Διάσπαση του `registry.py` σε `feature_registry.py`, `signal_registry.py`, `model_registry.py` ώστε να συνεχίσει να μικραίνει το central wiring surface.
2. Επέκταση των typed schemas ώστε `summary.json`, `run_metadata.json` και execution artifacts να έχουν αυστηρότερη runtime validation.
3. Μετατροπή snapshot storage από CSV σε Parquet για ταχύτερο I/O και preservation dtypes.
4. Προσθήκη model calibration diagnostics (reliability curves, calibration error) πριν από probability-threshold signal mapping.
5. Εισαγωγή factor/exposure model στο portfolio layer για πιο ρεαλιστικές neutrality constraints.
6. Προσθήκη transaction-cost model δεύτερης τάξης (spread + impact) για intraday ή μεγαλύτερο universe.
7. Επέκταση του `src/intraday/` με session features όπως opening range, session VWAP και overnight gap handling.
8. Προσθήκη benchmark harness για runtime και memory profiling ανά module.

### 15.3 Extension Roadmap

1. Factor model / expected returns interface separation από raw signal column.
2. Advanced label generation (triple barrier, meta-labeling).
3. Dataset/version catalog με schema evolution tracking.
4. Broker/OMS adapters και real-time state reconciliation.
5. Alerting πάνω σε drift, drawdown, missing data και order generation anomalies.
6. Notebook-to-config promotion workflow ώστε ad hoc research να μετατρέπεται πιο γρήγορα σε reproducible pipeline.
