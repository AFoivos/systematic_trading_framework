## 15. Refactor & Optimization Suggestions

### 15.1 Τεχνικό Χρέος

1. Το `src/experiments/runner.py` έχει 1,264 LOC και συγκεντρώνει orchestration, evaluation assembly, execution output και artifact persistence. Είναι λειτουργικό αλλά architectural hotspot.
2. Το artifact-centric logging είναι χρήσιμο, αλλά λείπει structured application logger για operational observability σε long-running jobs.
3. Το `src/models/lightgbm_baseline.py` χρησιμοποιεί `n_jobs=-1`, που δεν είναι απόλυτα ευθυγραμμισμένο με το strict reproducibility philosophy του υπόλοιπου framework.
4. Το optimizer fallback path επιτρέπει runtime warnings όταν του δοθούν pathological covariance matrices. Το test το θεωρεί αποδεκτό, αλλά production code θα ωφελούνταν από πιο καθαρή numerical sanitization.
5. Τα test configs γράφονται μερικές φορές ως JSON text σε `.yaml` path, κάτι που είναι νόμιμο για YAML parsers αλλά όχι ιδανικό για readability.

### 15.2 Συγκεκριμένες Προτάσεις Refactor

1. Διάσπαση του `runner.py` σε υπομονάδες όπως `orchestration/data_stage.py`, `orchestration/model_stage.py`, `orchestration/reporting.py`, `orchestration/artifacts.py`.
2. Εισαγωγή explicit typed schemas για `summary.json` και `run_metadata.json` μέσω dataclasses ή Pydantic-like validation layer.
3. Μετατροπή snapshot storage από CSV σε Parquet για ταχύτερο I/O και preservation dtypes.
4. Προσθήκη model calibration diagnostics (reliability curves, calibration error) πριν από probability-threshold signal mapping.
5. Εισαγωγή factor/exposure model στο portfolio layer για πιο ρεαλιστικές neutrality constraints.
6. Προσθήκη transaction-cost model δεύτερης τάξης (spread + impact) για intraday ή μεγαλύτερο universe.
7. Προσθήκη benchmark harness για runtime και memory profiling ανά module.

### 15.3 Extension Roadmap

1. Factor model / expected returns interface separation από raw signal column.
2. Advanced label generation (triple barrier, meta-labeling).
3. Dataset/version catalog με schema evolution tracking.
4. Broker/OMS adapters και real-time state reconciliation.
5. Alerting πάνω σε drift, drawdown, missing data και order generation anomalies.
6. Notebook-to-config promotion workflow ώστε ad hoc research να μετατρέπεται πιο γρήγορα σε reproducible pipeline.
