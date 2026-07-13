# Ερευνητικά πειράματα lab

Τελευταία ενημέρωση: 2026-07-11

Ο φάκελος `config/experiments/lab/` περιέχει 21 configs για ελεγχόμενη διερεύνηση
features, signals, targets και forecasts. Δεν είναι κατάλογος εγκεκριμένων
στρατηγικών και ένα θετικό lab backtest δεν αποτελεί από μόνο του trading
evidence.

Κάθε tracked YAML είναι αυτοτελές. Δεν επιτρέπεται `extends` ούτε απόκρυψη
assumptions σε parent configs.

## Τύποι πειραμάτων

### Οπτική διερεύνηση features

Το `feature_signal_target_lab.yaml` ελέγχει:

- ενεργοποίηση feature steps μέσω `features[].enabled`,
- προαιρετική επιλογή έως ενός `signals_catalog.*.enabled`,
- προαιρετική επιλογή έως ενός `targets_catalog.*.enabled`,
- missing values, χρονική ευθυγράμμιση και παραγόμενες στήλες.

Με κανένα ενεργό signal, ο loader γράφει flat μηδενικό signal στη
`backtest.signal_col` ώστε να μπορούν να παραχθούν feature diagnostics χωρίς
συναλλαγές. Όταν ενεργοποιείται signal, το output column του πρέπει να
συμφωνεί με τη `backtest.signal_col`.

### Forecast-first πειράματα

Τα `01_*.yaml` έως `10_*.yaml` αξιολογούν forecast quality, όχι μόνο PnL.
Ελέγχονται horizon, OOS error/correlation, directional accuracy, quantile
buckets, autocorrelation και συμπεριφορά ανά volatility regime.

### Τοπικοί forecasters

Τα δέκα configs στο `local_forecasters/` εκπαιδεύουν LightGBM, GARCH, LSTM,
SARIMAX, PatchTST ή TFT. Δεν χρησιμοποιούν pretrained Chronos/TimesFM backends.

## Συνιστώμενη ροή

1. Όρισε ένα συγκεκριμένο ερευνητικό ερώτημα.
2. Αντίγραψε το πλησιέστερο YAML και άλλαξε μόνο τα απαιτούμενα blocks.
3. Κράτησε ρητά `data`, `features`, `model.target`, `model.split`,
   `signals`, `diagnostics` και `logging`.
4. Χρησιμοποίησε μοναδικό `run_name` κάτω από `logs/lab`.
5. Διάβασε πρώτα prediction/model diagnostics και έπειτα το backtest.
6. Έλεγξε την υπόθεση σε περισσότερα assets, horizons και χρονικά splits πριν
   από μεταφορά σε άλλη config family.

```bash
python -m src.experiments.runner config/experiments/lab/feature_signal_target_lab.yaml
```

ή:

```bash
docker compose run --rm app python -m src.experiments.runner config/experiments/lab/feature_signal_target_lab.yaml
```

## Guardrails χρονικής αιτιότητας

- Τα splits παραμένουν chronological και δεν χρησιμοποιούν random shuffle.
- Future labels επιτρέπονται μόνο ως targets ή diagnostics.
- Purge και embargo πρέπει να καλύπτουν το overlap του forecast horizon.
- Δεν γίνεται tuning στο test subset και μετέπειτα παρουσίασή του ως καθαρό OOS.
- Model preprocessing εκπαιδεύεται μόνο στο training μέρος κάθε fold.
- Τα artifacts γράφονται ως JSON, CSV, Markdown και PNG κάτω από
  `logs/lab/<run_name>_<timestamp>_<id>/`.
