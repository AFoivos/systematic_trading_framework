# Μερικές έξοδοι στο `manual_barrier`

Τελευταία ενημέρωση: 2026-07-11

Το `manual_barrier` υποστηρίζει προαιρετικές μερικές εξόδους. Αν το block
`partial_exits` λείπει ή έχει `enabled: false`, η συμπεριφορά παραμένει
single-exit.

## Έγκυρο schema

```yaml
backtest:
  take_profit_r: 2.0
  stop_loss_r: 1.5
  max_holding_bars: 12
  dynamic_exits:
    enabled: false
  partial_exits:
    enabled: true
    rules:
      - trigger_r: 0.5
        fraction: 0.5
        exit_price: trigger
```

Για κάθε rule:

- `trigger_r` πρέπει να είναι θετικό.
- `fraction` πρέπει να ανήκει στο ανοικτό διάστημα `(0, 1)`.
- `exit_price` είναι `trigger`, `close` ή `next_open`.
- Το άθροισμα όλων των `fraction` πρέπει να είναι αυστηρά μικρότερο από `1.0`.
- Οι rules ταξινομούνται κατά αύξον `trigger_r`.

## Σειρά αποφάσεων μέσα σε bar

1. Ενημερώνονται MFE/MAE και τυχόν dynamic stops.
2. Ελέγχονται stop loss και full take profit.
3. Αν το ίδιο bar αγγίξει stop και take profit, εφαρμόζεται το configured
   `tie_break`.
4. Αν αγγίξει stop και partial trigger, προηγείται το stop και δεν καταγράφεται
   η μερική έξοδος.
5. Αν αγγίξει partial trigger και full take profit χωρίς stop, οι trigger/close
   partial exits καταγράφονται πριν κλείσει το υπόλοιπο στο take profit.
6. Έπειτα εξετάζονται dynamic exits και το χρονικό όριο.

Η πολιτική είναι direction-aware και εφαρμόζεται συμμετρικά σε long και short
paths. Η τιμή `next_open` απαιτεί διαθέσιμο επόμενο bar.

## Outputs και κόστος

Τα trade artifacts περιλαμβάνουν `partial_exit_count`,
`partial_exit_fraction_total` και τα επιμέρους events. Το gross return,
`trade_r`, turnover και κόστος σταθμίζουν τις μερικές και την τελική έξοδο.
Δεν επιτρέπεται σύγκριση partial-exit policy με single-exit policy χωρίς ίδιο
cost model και ίδια paths.

## Πηγές αλήθειας και tests

- `src/utils/trade_path.py`
- `src/backtesting/manual_barrier.py`
- `src/utils/config_validation.py`
- `tests/backtesting/test_manual_barrier_dynamic_exits.py`
- `tests/test_config_validation.py`
