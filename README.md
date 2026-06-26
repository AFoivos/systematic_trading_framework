# Systematic Trading Framework

Ερευνητικό framework για συστηματικό trading, time-series forecasting,
machine learning και portfolio/backtest workflows. Ο στόχος του repo είναι να
επιτρέπει πειράματα που είναι αναπαράξιμα, time-aware και ελέγξιμα, όχι να
λειτουργεί ως συλλογή από ad-hoc trading scripts.

Το project είναι φτιαγμένο γύρω από YAML experiments. Ένα experiment δηλώνει
data, features, targets, model, signals, backtest, monitoring και execution
outputs. Ο runner φορτώνει το YAML, εκτελεί το pipeline με σταθερή σειρά και
γράφει artifacts για audit και σύγκριση.

## Για ποιον είναι

- Για quant/data science έρευνα σε χρηματοοικονομικές χρονοσειρές.
- Για σύγκριση rule-based signals, ML classifiers/regressors, forecasting
  models και reinforcement learning agents.
- Για backtests με χρονική αιτιότητα, walk-forward/OOS λογική και explicit
  risk controls.
- Για παραγωγή paper/demo execution artifacts με ξεκάθαρα safety guards.

Δεν είναι turnkey live-trading bot. Κάθε στρατηγική πρέπει να αξιολογείται με
out-of-sample discipline, transaction costs, spread assumptions και data-quality
checks.

## Γρήγορη εκκίνηση

Προτεινόμενη εκτέλεση μέσω Docker:

```bash
docker compose build
docker compose run --rm app pytest
docker compose run --rm app python -m src.experiments.runner config/experiments/lab/feature_signal_target_lab.yaml
```

Για local Python περιβάλλον:

```bash
python -m pip install -r requirements.txt
python -m pytest
python -m src.experiments.runner config/experiments/lab/feature_signal_target_lab.yaml
```

Τα περισσότερα production-like experiments βρίσκονται κάτω από
`config/experiments/`. Τα generated artifacts και logs γράφονται κυρίως σε
`logs/`, `tmp/` ή στα paths που δηλώνονται στο YAML.

## Βασική δομή

```text
config/                  YAML configs για experiments, execution και labs
data/                    raw/processed datasets και local snapshots
docs/                    ελληνική τεκμηρίωση, catalogs και strategy notes
scripts/                 βοηθητικά scripts για data prep, diagnostics, MT5
src/
  backtesting/           backtest engines και trade-path logic
  evaluation/            metrics και performance analysis
  execution/             paper/demo execution outputs και MT5 demo runner
  experiments/           orchestration, runner, reporting, Optuna support
  features/              raw features, technical indicators και helpers
  models/                ML/forecasting/RL wrappers και model registry
  pipelines/             canonical pipeline facade και registry
  portfolio/             portfolio construction και constraints
  risk/                  sizing, costs και exposure controls
  signals/               signal builders που διαβάζουν feature/model columns
  src_data/              data loading, PIT hardening και OHLCV validation
  targets/               target builders και label generation
  utils/                 config loader, validation, schemas και shared utils
tests/                   unit/integration tests
```

## Κεντρική ροή experiment

1. Φόρτωση YAML και validation.
2. Φόρτωση OHLCV ή panel data.
3. Point-in-time hardening και data validation.
4. Feature generation.
5. Target generation και model training, όταν υπάρχει model block.
6. Signal generation.
7. Backtest/evaluation.
8. Monitoring, execution outputs και artifact writing.

Το stable entrypoint είναι:

```bash
python -m src.experiments.runner path/to/experiment.yaml
```

Προγραμματιστικά:

```python
from src.experiments.runner import run_experiment

result = run_experiment("config/experiments/lab/feature_signal_target_lab.yaml")
print(result.evaluation["primary_summary"])
```

## Features και helpers

Κανόνας του repo: τα raw feature modules παράγουν μόνο raw/βασικές στήλες.
Παράγωγες στήλες όπως ratios, distances, slopes, flags, crossings,
rolling z-scores και clipping πρέπει να δηλώνονται με helpers μέσα στο ίδιο
feature step.

Παράδειγμα:

```yaml
features:
  - step: atr
    params:
      high_col: high
      low_col: low
      close_col: close
      window: 14
      atr_col: atr_14
    transforms:
      ratio:
        params:
          numerator_col: atr_14
          denominator_col: close
          output_col: atr_over_price_14
```

Αυτό κρατά το feature space καθαρό: παράγονται μόνο οι στήλες που ζητάει το
experiment, χωρίς άχρηστα default diagnostics.

## Registries

Τα components λύνονται από registries:

- `src/features/registry.py`
- `src/signals/registry.py`
- `src/targets/registry.py`
- `src/models/registry.py`
- `src/pipelines/registry.py`

Για να προσθέσεις νέο component, γράφεις καθαρό module στο σωστό package,
προσθέτεις registry entry, validation/tests και μετά το χρησιμοποιείς από YAML.

## Κύρια docs

- [Κέντρο τεκμηρίωσης](docs/index.md)
- [Quickstart στα ελληνικά](docs/quickstart_gr.md)
- [Αρχιτεκτονική](docs/architecture.md)
- [Οδηγός YAML experiments](docs/yaml_experiments_guide_gr.md)
- [Feature catalog](docs/catalog/features.md)
- [Signal catalog](docs/catalog/signals.md)
- [Target catalog](docs/catalog/targets.md)

## Κανόνες ποιότητας

- Δεν εισάγουμε lookahead bias ή data leakage.
- Δεν κάνουμε fit scalers/encoders σε όλο το dataset πριν από split.
- Δεν αλλάζουμε runtime defaults σιωπηλά.
- Κάθε νέο feature πρέπει να είναι causal ή να σημειώνεται ρητά ως diagnostic.
- Τα configs πρέπει να είναι self-contained και αναπαράξιμα.
- Τα tests πρέπει να καλύπτουν contract, missing columns και causality όπου
  υπάρχει κίνδυνος leakage.

## MT5 demo execution

Υπάρχει demo execution runner για MetaTrader 5:

```bash
python scripts/run_mt5_demo_bot.py --config config/execution/mt5_demo.yaml --once
```

Η default συμπεριφορά είναι dry-run. Πραγματικό `order_send` επιτρέπεται μόνο
με explicit demo config, verified demo account και safety gates. Τα credentials
διαβάζονται από environment variables και δεν πρέπει να μπαίνουν σε Git.

Περισσότερα στο [project workflow](docs/project_workflow_gr.md).

## License

Δες το [LICENSE](LICENSE).
