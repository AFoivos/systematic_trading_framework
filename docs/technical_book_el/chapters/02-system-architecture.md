## 2. Αρχιτεκτονική Συστήματος

### 2.1 Αρχιτεκτονικό Pattern

Η υλοποίηση ακολουθεί υβριδικό pattern:

- `Layered architecture` για σαφή separation of concerns.
- `Pipeline orchestration` μέσω του `src/experiments/orchestration/*`, με το `src/experiments/runner.py` ως thin façade.
- `Registry pattern` για dynamic resolution feature/model/signal functions.
- `Contract-first validation` για data και target assumptions.
- `Typed configuration and orchestration payloads` για πιο καθαρά boundaries μεταξύ stages.
- `Artifact-driven reproducibility` για config/data/runtime traceability.

Η επιλογή αυτή είναι κατάλληλη για quant/ML projects επειδή επιτρέπει γρήγορη εναλλαγή πειραμάτων χωρίς να
θυσιάζεται η αναπαραγωγιμότητα. Ο orchestrator είναι παχύς μόνο ως προς τη ροή και όχι ως προς την
αριθμητική λογική: οι υπολογισμοί παραμένουν αποκεντρωμένοι σε εξειδικευμένα modules.

### 2.2 Layered Breakdown

- `Configuration layer`: YAMLs + `src/utils/config.py` façade + `src/utils/config_loader.py`, `src/utils/config_defaults.py`, `src/utils/config_validation.py`, `src/utils/config_schemas.py`.
- `Infrastructure/repro layer`: `src/utils/repro.py`, `src/utils/run_metadata.py`, `src/utils/paths.py`.
- `Data layer`: `src/src_data/*`.
- `Intraday layer`: `src/intraday/*`.
- `Feature layer`: `src/features/*`.
- `Model layer`: `src/models/*`, `src/models/lightgbm_baseline.py`.
- `Experiment-model adapter layer`: `src/experiments/models.py` façade + `src/experiments/support/*`.
- `Experiment orchestration layer`: `src/experiments/orchestration/*`, `src/experiments/registry.py`.
- `Signal layer`: `src/signals/*`, `src/backtesting/strategies.py`.
- `Backtesting/evaluation layer`: `src/backtesting/engine.py`, `src/evaluation/*`.
- `Portfolio layer`: `src/portfolio/*`.
- `Monitoring layer`: `src/monitoring/drift.py`.
- `Execution layer`: `src/execution/paper.py`.
- `Test/assurance layer`: `tests/*`.

### 2.3 ASCII Διάγραμμα Συστήματος

```text
[YAML Configs] ---> [utils.config façade]
      |                    |
      v                    v
[config_loader/defaults/validation/schemas] ---> [experiments.runner façade]
                                                      |
                                                      v
                                            [orchestration.pipeline]
                                                      |
             +-------------------+--------------------+-------------------+
             |                   |                    |                   |
             v                   v                    v                   v
   [data_stage + src_data] [feature_stage] [experiments/support + src.models] [signals]
             |                   |                    |                   |
             +-------------------+--------------------+-------------------+
                                                      |
                                                      v
                                   [backtest_stage] ---> [portfolio.*]
                                                      |
                              +-----------------------+----------------------+
                              |                                              |
                              v                                              v
                       [reporting/monitoring]                         [execution_stage]
                              |                                              |
                              +-----------------------+----------------------+
                                                      |
                                                      v
                                               [artifacts + logs]
```

### 2.4 Σχόλιο για την Κατεύθυνση των Εξαρτήσεων

Οι χαμηλότεροι layers (`src_data`, `features`, `risk`, `evaluation`, `portfolio`, `models`, `intraday`) δεν
γνωρίζουν τίποτε για τον orchestrator. Το `src/experiments/models.py` είναι πλέον façade προς το `src/models/*`,
τα canonical target builders βρίσκονται στο `src/targets/*`, ενώ τα experiment-side helpers για diagnostics και
split-safe summaries βρίσκονται στο `src/experiments/support/*`. Αντίστοιχα, το `src/experiments/runner.py`
είναι façade προς το `src/experiments/orchestration/*`, όπου
βρίσκονται τα data, feature, model, backtest, reporting, execution και artifact stages. Έτσι η σύζευξη
παραμένει κατευθυνόμενη προς τα πάνω και τα μεγάλα hotspots έχουν διασπαστεί σε μικρότερα, testable modules.

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
