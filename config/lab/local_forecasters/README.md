# Lab τοπικών forecasters

Τελευταία ενημέρωση: 2026-07-11

Τα δέκα configs αυτού του φακέλου εκπαιδεύουν μοντέλα τοπικά. Εξαιρούν
σκόπιμα pretrained/foundation forecasters όπως Chronos και TimesFM.

Όλα χρησιμοποιούν 30λεπτες μπάρες. Το suffix `hN` δηλώνει ορίζοντα σε ώρες,
όχι πλήθος input bars. Για παράδειγμα, `h8` αντιστοιχεί σε
`horizon_bars: 16`.

## Χάρτης πειραμάτων

| Αρχείο | Αντικείμενο πρόβλεψης | Model | Σκοπός σύγκρισης |
|---|---|---|---|
| `01_spx500_lightgbm_return_h8.yaml` | 8ωρη volatility-normalized απόδοση | `lightgbm_regressor` | Tabular baseline |
| `02_xauusd_garch_vol_h8.yaml` | Βραχυπρόθεσμη conditional volatility | `garch_forecaster` | Εξειδικευμένο volatility baseline |
| `03_us100_lstm_momentum_h12.yaml` | 12ωρη συνέχιση momentum | `lstm_forecaster` | Ordered sequence baseline |
| `04_eurusd_sarimax_mean_reversion_h6.yaml` | 6ωρη mean-reversion απόδοση | `sarimax_forecaster` | Ερμηνεύσιμο στατιστικό baseline |
| `05_ethusd_patchtst_tail_h24.yaml` | 24ωρη tail απόδοση | `patchtst_forecaster` | Patch-based sequence baseline |
| `06_ger40_tft_regime_h16.yaml` | 16ωρη regime-conditioned απόδοση | `tft_forecaster` | Sequence model με variable selection |
| `07_panel_lightgbm_cross_asset_h8.yaml` | 8ωρο panel πέντε assets | `lightgbm_regressor` | Cross-asset tabular baseline |
| `08_us30_lightgbm_trend_h24.yaml` | 24ωρη επιμονή trend | `lightgbm_regressor` | Μη γραμμικό trend/range baseline |
| `09_btcusd_lstm_vol_adjusted_h16.yaml` | 16ωρη volatility-adjusted κατεύθυνση | `lstm_forecaster` | Sequence και quantile-spread έλεγχος |
| `10_xagusd_sarimax_vol_overlay_h12.yaml` | 12ωρη απόδοση με GARCH overlay | `sarimax_forecaster` | Return baseline με τοπικό risk overlay |

## Εκτέλεση

```bash
python -m src.experiments.runner config/experiments/lab/local_forecasters/01_spx500_lightgbm_return_h8.yaml
```

## Guardrails

- Τα splits είναι chronological και purged όπου επικαλύπτονται horizons.
- Τα targets κατασκευάζονται μέσα στο experiment pipeline.
- Οι feature selectors αποκλείουν target, signal και prediction columns.
- Τα neural configs έχουν περιορισμένες lab ρυθμίσεις. Αύξηση epochs ή folds
  δικαιολογείται μόνο μετά από σταθερά OOS diagnostics.
