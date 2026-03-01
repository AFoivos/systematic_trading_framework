## 2. Αρχιτεκτονική Συστήματος

### 2.1 Αρχιτεκτονικό Pattern

Η υλοποίηση ακολουθεί υβριδικό pattern:

- `Layered architecture` για σαφή separation of concerns.
- `Pipeline orchestration` μέσω του `src/experiments/runner.py`.
- `Registry pattern` για dynamic resolution feature/model/signal functions.
- `Contract-first validation` για data και target assumptions.
- `Artifact-driven reproducibility` για config/data/runtime traceability.

Η επιλογή αυτή είναι κατάλληλη για quant/ML projects επειδή επιτρέπει γρήγορη εναλλαγή πειραμάτων χωρίς να
θυσιάζεται η αναπαραγωγιμότητα. Ο orchestrator είναι παχύς μόνο ως προς τη ροή και όχι ως προς την
αριθμητική λογική: οι υπολογισμοί παραμένουν αποκεντρωμένοι σε εξειδικευμένα modules.

### 2.2 Layered Breakdown

- `Configuration layer`: `src/utils/config.py`, YAMLs.
- `Infrastructure/repro layer`: `src/utils/repro.py`, `src/utils/run_metadata.py`, `src/utils/paths.py`.
- `Data layer`: `src/src_data/*`.
- `Feature layer`: `src/features/*`.
- `Model layer`: `src/experiments/models.py`, `src/models/lightgbm_baseline.py`.
- `Signal layer`: `src/signals/*`, `src/backtesting/strategies.py`.
- `Backtesting/evaluation layer`: `src/backtesting/engine.py`, `src/evaluation/*`.
- `Portfolio layer`: `src/portfolio/*`.
- `Monitoring layer`: `src/monitoring/drift.py`.
- `Execution layer`: `src/execution/paper.py`.
- `Test/assurance layer`: `tests/*`.

### 2.3 ASCII Διάγραμμα Συστήματος

```text
[YAML Configs] ---> [utils.config]
      |                    |
      v                    v
[runtime/repro] ---> [experiments.runner] <-----------------------------+
                             |                                           |
                             v                                           |
                      [src_data.loaders] ---> [providers]                |
                             |                                           |
                             v                                           |
                      [src_data.pit] ---> [validation] ---> [storage]    |
                             |                                           |
                             v                                           |
                          [features] ---> [experiments.models] ---> [signals]
                             |                   |                    |
                             |                   v                    |
                             |            [time_splits]               |
                             |                   |                    |
                             +---------> [backtesting.engine] <-------+
                                                 |
                      +--------------------------+--------------------------+
                      |                                                     |
                      v                                                     v
               [portfolio.*]                                        [evaluation.metrics]
                      |                                                     |
                      +-------------------> [monitoring] <------------------+
                                                 |
                                                 v
                                          [execution.paper]
                                                 |
                                                 v
                                        [logs/experiments artifacts]
```

### 2.4 Σχόλιο για την Κατεύθυνση των Εξαρτήσεων

Οι χαμηλότεροι layers (`src_data`, `features`, `risk`, `evaluation`, `portfolio`) δεν γνωρίζουν τίποτε για
τον orchestrator. Αντίθετα, ο orchestrator εξαρτάται από όλους. Αυτή είναι υγιής κατεύθυνση σύζευξης. Το
μοναδικό σημείο που εμφανίζεται πιο κεντρικό από όσο ιδανικά θα θέλαμε είναι το `runner.py`, το οποίο
συγκεντρώνει orchestration, artifact persistence και μέρος της evaluation/reporting assembly. Αυτό δεν είναι
σφάλμα, αλλά αποτελεί τον κύριο υποψήφιο μελλοντικού decomposition.

### 2.5 ASCII Class Diagram

```text
+-----------------------+        +-----------------------+
| MarketDataProvider    |<-------| YahooFinanceProvider   |
|-----------------------|        +-----------------------+
| +get_ohlcv(...)       |<-------| AlphaVantageFXProvider |
+-----------------------+        +-----------------------+

+-----------------------+        +-----------------------+
| DataContract          |        | TargetContract        |
+-----------------------+        +-----------------------+

+-----------------------+        +-----------------------+
| BacktestResult        |        | PortfolioPerformance  |
+-----------------------+        +-----------------------+
          ^                                   ^
          |                                   |
          +----------- ExperimentResult ------+

+-----------------------+        +-----------------------+
| PortfolioConstraints  |        | TimeSplit             |
+-----------------------+        +-----------------------+

+-----------------------+
| LGBMBaselineConfig    |
+-----------------------+
```
