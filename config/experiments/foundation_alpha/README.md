# Πειράματα Foundation Alpha

Τελευταία ενημέρωση: 2026-07-11

Ο φάκελος περιέχει 32 αυτοτελή configs για forecast-driven έρευνα, κυρίως σε
ETHUSD 30m. Η οικογένεια μετατρέπει out-of-sample forecasts σε αραιούς
long/short candidates και αξιολογεί ρητά κόστος, χρονική αιτιότητα και
σταθερότητα ανά fold.

## Δομή

- `ethusd/`: 23 ερευνητικές και ablation προδιαγραφές.
- `BEST/ethusd/`: 8 επιλεγμένες, installed ή meta-filter προδιαγραφές.
- `usoil/`: 1 συγκριτικό LightGBM config.

Τα configs καλύπτουν `lightgbm_regressor`, `xgboost_regressor`,
`lstm_forecaster`, `patchtst_forecaster`, `tft_forecaster`,
`sarimax_forecaster`, `chronos_bolt_forecaster` και
`timesfm_2p5_200m_forecaster`. Η διαθεσιμότητα ενός config δεν σημαίνει ότι η
προαιρετική model dependency είναι εγκατεστημένη.

## Αντιπροσωπευτικά configs

- `ethusd/ethusd_30m_chronos_bolt_h24_tail_alpha_v1.yaml`: zero-shot Chronos
  σύγκριση.
- `ethusd/ethusd_30m_timesfm_2p5_200m_h24_structured_tail_alpha_v3_7_neural_native_v1.yaml`:
  TimesFM 2.5 200M παραλλαγή.
- `ethusd/ethusd_30m_patchtst_h24_structured_tail_alpha_v3_7_neural_native_v1.yaml`:
  τοπικό PatchTST baseline.
- `BEST/ethusd/BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier.yaml`:
  επιλεγμένη LightGBM/manual-barrier προδιαγραφή.
- `BEST/ethusd/meta_filter/`: ελεγχόμενες meta-filter συγκρίσεις.

## Χρονικές παραδοχές

- Τα features στο timestamp `t` πρέπει να προκύπτουν μόνο από κλεισμένα ή
  δημοσιευμένα δεδομένα έως το `t`.
- Το future-return target κοιτά το μέλλον μόνο για label construction.
- Τα model outputs που οδηγούν signal πρέπει να είναι out-of-sample.
- Preprocessing, scaling και calibration πρέπει να εφαρμόζονται μέσα στο
  αντίστοιχο training fold.
- Το purge/embargo και το minimum holding δεν είναι καθολικές σταθερές·
  διαβάζονται από κάθε YAML.

## Εκτέλεση

```bash
python -m src.experiments.runner config/experiments/foundation_alpha/ethusd/ethusd_30m_chronos_bolt_h24_tail_alpha_v1.yaml
```

Για τη συνήθη LightGBM προδιαγραφή:

```bash
python -m src.experiments.runner config/experiments/foundation_alpha/BEST/ethusd/BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_trial_0054_manual_barrier.yaml
```

Τα `BEST` filenames δηλώνουν ερευνητική επιλογή σε συγκεκριμένο snapshot και
δεν αποτελούν εγγύηση μελλοντικής απόδοσης ή άδεια παραγωγικής εκτέλεσης.
