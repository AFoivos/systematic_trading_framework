# Lab Experiments

Ο φάκελος `config/experiments/lab/` είναι χώρος πειραματισμού, όχι χώρος
επιλογής τελικών trading strategies. Τα YAML εδώ χρησιμοποιούνται για να
δοκιμάζουμε υποθέσεις πάνω σε features, signals, targets, forecasts και
diagnostics με ελεγχόμενο και αναπαραγώγιμο τρόπο.

Ο βασικός στόχος δεν είναι να βρούμε άμεσα trades ή να βελτιστοποιήσουμε PnL.
Ο στόχος είναι να απαντάμε ερευνητικές ερωτήσεις όπως:

- έχει ένα feature σταθερή χρονική σχέση με κάποιο μελλοντικό target;
- δουλεύει καλύτερα ένα forecast σε συγκεκριμένο horizon ή asset;
- αλλάζει η συμπεριφορά του σήματος ανά regime, volatility bucket ή session;
- παράγει το μοντέλο χρήσιμη πληροφορία εκτός δείγματος ή απλώς noise;
- αξίζει μια ιδέα να μεταφερθεί αργότερα σε κανονικό experiment config;

## Πώς φτιάχνουμε lab YAML

Ξεκινάμε από υπάρχον lab config και το αντιγράφουμε με νέο, περιγραφικό όνομα.
Το όνομα πρέπει να δείχνει το ερώτημα του πειράματος, όχι το αναμενόμενο
αποτέλεσμα. Παραδείγματα:

```text
01_directional_return_chronos_bolt_h6.yaml
03_volatility_proxy_chronos_bolt_h24.yaml
feature_signal_target_lab.yaml
local_forecasters/01_spx500_lightgbm_return_h8.yaml
```

Κάθε tracked lab YAML πρέπει να είναι self-contained. Δεν χρησιμοποιούμε
`extends` και δεν κρύβουμε assumptions σε parent configs. Αν αλλάζει asset,
horizon, split, feature set, target ή model backend, αυτό πρέπει να φαίνεται
ρητά μέσα στο YAML.

## Τρόποι πειραματισμού

### Feature-only EDA

Χρησιμοποίησε το `feature_signal_target_lab.yaml` όταν θέλεις να δεις αν οι
στήλες φτιάχνονται σωστά, αν έχουν missing values, αν ευθυγραμμίζονται χρονικά
και αν έχουν λογική συμπεριφορά πριν μπουν σε signal ή model.

- Ενεργοποίησε ή απενεργοποίησε feature steps με `features[].enabled`.
- Πρόσθεσε helper transforms μέσα στο αντίστοιχο feature step.
- Κράτα μηδενικό ή inactive signal όταν δεν θέλεις trade diagnostics.
- Έλεγξε τα artifacts κάτω από `logs/lab/<run_name>_<timestamp>_<id>/`.

### Signal/target diagnostics

Χρησιμοποίησε τα catalog blocks όταν θέλεις να συγκρίνεις διαφορετικούς
ορισμούς signal ή target χωρίς να γράψεις νέο production strategy.

- Ενεργοποίησε μηδέν ή ένα `signals_catalog.*.enabled`.
- Ενεργοποίησε μηδέν ή ένα `targets_catalog.*.enabled`.
- Κράτα το `backtest.signal_col` ευθυγραμμισμένο με το επιλεγμένο signal μόνο
  όταν όντως θέλεις trade-path diagnostics.
- Μην ερμηνεύεις ένα καλό lab equity curve ως strategy approval. Είναι ένδειξη
  για επόμενο controlled experiment, όχι τελικό συμπέρασμα.

### Forecast-first labs

Τα configs `01_...` έως `10_...` είναι forecast-first labs. Εδώ η κύρια
αξιολόγηση είναι forecast quality και out-of-sample συμπεριφορά, όχι trading
PnL. Συνήθεις άξονες πειραματισμού:

- `model.target.horizon_bars`: διαφορετικά forecast horizons.
- `model.kind` και `model.params`: Chronos, TimesFM ή local forecasters.
- `model.split`: walk-forward παράθυρα, purge και embargo.
- `metrics.regression`: error, correlation, directional accuracy και rank
  diagnostics.
- `diagnostics.forecast`: quantile buckets, autocorrelation lags και volatility
  context.

Το `signals.kind: forecast_threshold` μπορεί να υπάρχει για να περάσει το
pipeline και να παραχθούν artifacts, αλλά δεν σημαίνει ότι το lab έχει έτοιμο
trading rule.

### Local forecaster labs

Ο φάκελος `local_forecasters/` είναι για μοντέλα που εκπαιδεύονται τοπικά, όπως
LightGBM, GARCH, LSTM, SARIMAX, PatchTST ή TFT. Χρησιμοποίησέ τον όταν θέλεις
να συγκρίνεις pretrained/foundation forecasts με κλασικά ή τοπικά trained
baselines.

## Πρακτικό workflow

1. Διάλεξε ένα καθαρό ερευνητικό ερώτημα.
2. Αντίγραψε το πιο κοντινό υπάρχον lab YAML.
3. Άλλαξε μόνο τα blocks που χρειάζονται για το ερώτημα: `data`, `features`,
   `model.target`, `model.split`, `signals`, `diagnostics`, `logging`.
4. Κράτα `logging.output_dir: logs/lab` και δώσε μοναδικό `run_name`.
5. Τρέξε το config:

```bash
python -m src.experiments.runner config/experiments/lab/feature_signal_target_lab.yaml
```

ή με Docker:

```bash
docker compose run --rm app python -m src.experiments.runner config/experiments/lab/feature_signal_target_lab.yaml
```

6. Διάβασε πρώτα forecast/model/diagnostic artifacts και μετά οποιοδήποτε
   backtest output.
7. Αν η υπόθεση επιβιώσει σε πολλαπλά assets, horizons και χρονικά splits,
   τότε μπορεί να μεταφερθεί σε κανονικό `config/experiments/...` strategy
   config.

## Guardrails

- Τα splits είναι πάντα chronological. Δεν χρησιμοποιούμε random shuffle σε
  time-series experiments.
- Τα future labels επιτρέπονται μόνο ως targets ή research diagnostics, ποτέ ως
  διαθέσιμα features.
- Purge και embargo πρέπει να συμβαδίζουν με το forecast horizon όταν υπάρχει
  overlap.
- Δεν κάνουμε tuning πάνω στο test subset και μετά δεν το παρουσιάζουμε ως
  καθαρό OOS αποτέλεσμα.
- Δεν μεταφέρουμε lab config σε production/trading folder χωρίς καθαρό
  validation story.
- Δεν αλλάζουμε runtime defaults, schemas ή config contracts για χάρη ενός lab
  πειράματος.

## Υπάρχον feature/signal/target lab

`feature_signal_target_lab.yaml` is a runnable single-asset visual EDA config
with no model training stage:

- feature steps controlled by `features[].enabled`
- signal variants controlled by `signals_catalog.*.enabled`
- target variants controlled by top-level `targets_catalog.*.enabled`

Signal and target catalog entries are optional: enable zero or one signal and
zero or one target. With zero enabled signals, the loader emits a flat zero
signal at `backtest.signal_col` so the runner can still produce artifacts for
feature-only EDA. Keep the selected signal aligned with `backtest.signal_col`
when you want trade diagnostics. Experiment artifacts are written under
`logs/lab/<run_name>_<timestamp>_<id>/` as structured JSON/CSV/Markdown and PNG
files; legacy HTML diagnostics are not emitted.
