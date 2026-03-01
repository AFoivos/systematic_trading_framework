## 11. Logging & Monitoring

### 11.1 Logging Architecture

Το repository δεν υλοποιεί κλασικό application logger με rotating handlers. Αντί γι’ αυτό εφαρμόζει artifact-
centric logging: η “λογική μνήμη” κάθε run γράφεται σε JSON/CSV files. Αυτή η επιλογή είναι εύλογη για
research-heavy συστήματα όπου η πλήρης αναπαραγωγιμότητα των outputs έχει μεγαλύτερη αξία από real-time
console logs.

Κύρια artifacts:

- `summary.json`: condensed run outcome.
- `run_metadata.json`: runtime, git, environment και hash metadata.
- `artifact_manifest.json`: file hashes για integrity checks.
- `monitoring_report.json`: drift summary.

### 11.2 Monitoring

Το drift monitoring συγκρίνει IS/reference vs OOS/current feature distributions χρησιμοποιώντας PSI. Το report
δεν είναι απλώς aggregate boolean: διατηρεί mean, std, missing rates, normalized mean shift και `is_drifted`
ανά feature. Αυτό είναι σωστό architectural choice, επειδή σε quant systems η διάγνωση drift θέλει feature-level
forensics και όχι μόνο μία συνολική βαθμολογία.
