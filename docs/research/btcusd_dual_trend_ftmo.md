# BTCUSD Dual-Trend Ensemble FTMO 22/16 v1

## Ερευνητικός σκοπός

Η στρατηγική είναι πλήρως deterministic και rule-based. Δεν χρησιμοποιεί ML, RL ή DL και δεν περιλαμβάνει optimization, parameter search ή feature selection. Το parameter-neighborhood grid αποτελεί diagnostic σταθερότητας και δεν αλλάζει το επιλεγμένο baseline.

Οι κανόνες FTMO είναι ρητές ερευνητικές παραδοχές του YAML (`rules_web_verified: false`) και όχι επαλήθευση των τρεχόντων εμπορικών όρων κάποιου broker.

## Αρχιτεκτονική και χρονικό συμβόλαιο

Το `btcusd_dual_trend_ftmo_v1` είναι custom registered pipeline. Ο διαχωρισμός ευθυνών είναι:

- `src/features/btcusd_dual_trend_ftmo.py`: validation UTC/OHLCV, ακριβές 1m→30m resampling και feature/outcome frame.
- `src/signals/btcusd_dual_trend_ftmo_signal.py`: volatility sizing και stateful rebalance ανά αλλαγή κατεύθυνσης ή 48 εκτεθειμένα bars.
- `src/backtesting/btcusd_dual_trend_ftmo.py`: open-to-open realized accounting, turnover, costs, forced liquidation και trade ledger.
- `src/evaluation/btcusd_dual_trend_ftmo.py`: metrics και ανεξάρτητος normalized FTMO two-step simulator.
- `src/experiments/support/btcusd_dual_trend_ftmo.py`: locked-config validation, period orchestration, diagnostics, parity και artifacts.

Η 30λεπτη ράβδος έχει `label="right"` και `closed="right"`. Η απόφαση χρησιμοποιεί το κλείσιμο της ράβδου `t`. Το realized return της απόφασης είναι `open.shift(-2) / open.shift(-1) - 1`, ενώ οι adverse approximations χρησιμοποιούν αποκλειστικά το επόμενο 30λεπτο high/low σε σχέση με το `next_open`. Αυτές οι outcome στήλες δεν διαβάζονται από το signal function.

Δεν γίνεται sort, deduplication ή OHLC forward fill. Missing 30λεπτα bins δεν δημιουργούνται τεχνητά και αφαιρούνται μόνο bins με `source_rows == 0`.

## Κλειδωμένη υπόθεση alpha

Το log-close EMA sleeve χρησιμοποιεί spans 96 και 672 με `adjust=False`. Το Donchian sleeve χρησιμοποιεί προηγούμενα όρια `shift(1).rolling(336)` και διατηρεί την τελευταία κατεύθυνση μέχρι αντίθετο breakout. Το ensemble παραμένει κατευθυντικό όταν τα sleeves διαφωνούν:

| EMA | Donchian | Score |
|---:|---:|---:|
| +1 | +1 | +1.0 |
| -1 | -1 | -1.0 |
| +1 | -1 | +0.2 |
| -1 | +1 | -0.2 |

Η ετησιοποιημένη μεταβλητότητα είναι EWM standard deviation των log returns με span 336 και συντελεστή `sqrt(365 * 48)`.

## Θέση και κόστη

Το baseline χρησιμοποιεί στόχο μεταβλητότητας 22%, μέγιστη μόχλευση 1.50 και one-way κόστος 4 bps ανά unit turnover. Η θέση αλλάζει αμέσως όταν αλλάζει το πρόσημο της επιθυμητής θέσης ή όταν αυτή μηδενίζεται. Στην ίδια κατεύθυνση διατηρείται ακριβώς μέχρι να συμπληρωθούν 48 εκτεθειμένες ράβδοι· ενδιάμεσες μεταβολές της volatility δεν αλλάζουν την εφαρμοζόμενη θέση.

Κάθε ανεξάρτητο evaluation interval ξεκινά με normalized equity 1.0 και θέση μηδέν. Στο τέλος γίνεται forced liquidation και χρεώνεται το αντίστοιχο one-way turnover cost.

## FTMO two-step simulator

Κάθε rolling start αρχίζει Phase 1 με normalized equity 1.0. Μετά από επιτυχή Phase 1, η Phase 2 αρχίζει στο πρώτο επόμενο διαθέσιμο bar και επανεκκινεί ανεξάρτητα με equity 1.0. Σε κάθε bar ελέγχονται current/close equity, adverse intrabar equity, UTC daily loss, total loss από 1.0 και peak drawdown.

Profit target αναγνωρίζεται μόνο αν:

1. έχουν συμπληρωθεί τουλάχιστον τέσσερις UTC trading days,
2. η equity παραμένει πάνω από τον στόχο μετά το κόστος κλεισίματος της θέσης.

Τα phase statuses είναι `passed`, `failed`, `incomplete`. Τα challenge statuses είναι `passed`, `failed_phase1`, `failed_phase2`, `incomplete_phase1`, `incomplete_phase2`.

## Περίοδοι και ερμηνεία

- Development: `[2026-01-01, 2026-06-01)` UTC.
- Legacy holdout: `[2026-06-01, 2026-07-28)` UTC.
- Combined: `[2026-01-01, 2026-07-28)` UTC.

Το June–July interval αναφέρεται υποχρεωτικά ως `legacy_holdout_reused_not_pristine`. Δεν είναι νέο untouched OOS. Η στρατηγική δεν θεωρείται production-ready και απαιτεί νέο forward data πριν από οποιοδήποτε ισχυρότερο συμπέρασμα.

## Εκτέλεση

```bash
python -m src.experiments.runner \
  config/experiments/btcusd_dual_trend_ftmo/btcusd_1m_dual_trend_ftmo_22_16_v1.yaml
```

Τα artifacts γράφονται στο `logs/experiments/btcusd_dual_trend_ftmo/`. Το `parity_report.md` δηλώνει αν υπήρχαν τα τρία προαιρετικά reference artifacts κάτω από `/mnt/data/btcusd_dual_trend_ftmo_alpha/` και, σε mismatch, αναφέρει την πρώτη διαθέσιμη απόκλιση σε feature, signal, position, turnover, cost ή equity χωρίς tuning.
