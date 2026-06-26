# Quickstart

Τελευταία ενημέρωση: 2026-06-27

Ο οδηγός αυτός δείχνει το ελάχιστο workflow για να στήσεις το repo, να τρέξεις
tests και να εκτελέσεις ένα YAML experiment.

## 1. Προαπαιτούμενα

Προτεινόμενη επιλογή:

- Docker και Docker Compose.

Εναλλακτικά:

- Python 3.10+.
- Τα packages από `requirements.txt`.
- Προαιρετικά extra requirements για specialized flows, όπως
  `requirements.tsfresh.txt`.

## 2. Εκτέλεση με Docker

Build:

```bash
docker compose build
```

Interactive shell:

```bash
docker compose run --rm app
```

Tests:

```bash
docker compose run --rm app pytest
```

Experiment:

```bash
docker compose run --rm app python -m src.experiments.runner config/experiments/lab/feature_signal_target_lab.yaml
```

Αν χρειάζεσαι secrets, βάλε τα σε τοπικό `.env` που δεν μπαίνει σε Git:

```bash
docker compose --env-file .env run --rm app python -m src.experiments.runner path/to/config.yaml
```

## 3. Εκτέλεση με local Python

```bash
python -m pip install -r requirements.txt
python -m pytest
python -m src.experiments.runner config/experiments/lab/feature_signal_target_lab.yaml
```

Αν χρησιμοποιείς Conda ή venv, κράτα το περιβάλλον σταθερό για κάθε σειρά
πειραμάτων. Μην αναμειγνύεις artifacts από διαφορετικά dependency sets χωρίς να
το καταγράφεις.

## 4. Τι κάνει το πρώτο experiment

Ο runner:

1. Φορτώνει και κάνει validation το YAML.
2. Φορτώνει data από το δηλωμένο `data` block.
3. Εφαρμόζει point-in-time hardening και OHLCV validation.
4. Εκτελεί τα `features`.
5. Εκτελεί `target` και `model`, αν δηλώνονται.
6. Παράγει `signals`.
7. Τρέχει backtest/evaluation.
8. Γράφει artifacts/logs.

Το αποτέλεσμα επιστρέφεται ως `ExperimentResult` όταν καλείς Python API:

```python
from src.experiments.runner import run_experiment

result = run_experiment("config/experiments/lab/feature_signal_target_lab.yaml")
print(result.evaluation["primary_summary"])
```

## 5. Πού κοιτάς μετά την εκτέλεση

- Terminal summary: γρήγορη εικόνα απόδοσης.
- `logs/`: runtime logs και JSONL streams.
- `tmp/` ή configured artifact paths: intermediate/generated outputs.
- YAML config: η πηγή αλήθειας για το τι ακριβώς έτρεξε.

## 6. Συχνά προβλήματα

### Άγνωστο feature/signal/model name

Έλεγξε το αντίστοιχο registry:

- `src/features/registry.py`
- `src/signals/registry.py`
- `src/targets/registry.py`
- `src/models/registry.py`

### Missing dataframe columns

Συνήθως σημαίνει ότι:

- λείπει upstream feature step,
- άλλαξε output column name,
- ένα helper διαβάζει λάθος `source_col`,
- multi-asset override δεν παράγει την ίδια στήλη για όλα τα assets.

### Ύποπτα καλά backtest αποτελέσματα

Έλεγξε πρώτα:

- αν target/feature χρησιμοποιεί future bars,
- αν scaler έγινε fit σε όλο το dataset,
- αν το signal εκτελείται στο ίδιο bar που υπολόγισε feature από το close,
- αν transaction costs/spread/slippage είναι ρεαλιστικά.

## 7. Επόμενα βήματα

Διάβασε τον [οδηγό YAML experiments](yaml_experiments_guide_gr.md) και μετά το
[feature catalog](catalog/features.md).
