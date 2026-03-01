## 6. Data Flow Trace

Θεωρούμε το configuration `config/experiments/logreg_spy.yaml` και μία ημερομηνία `t` του SPY:

1. Το raw OHLCV row εισέρχεται ως `(open_t, high_t, low_t, close_t, volume_t)` από Yahoo Finance ή cached snapshot.
2. Το PIT layer κανονικοποιεί το timestamp σε UTC ημερολογιακή ημερομηνία, αφαιρεί duplicates και αφήνει την τιμή `close_t` άθικτη επειδή το default corporate action policy είναι `none`.
3. Η feature layer δημιουργεί `close_ret_t`, rolling volatilities, moving-average ratios και lagged returns `lag_close_ret_1`, `lag_close_ret_2`, `lag_close_ret_5`.
4. Ο target builder δημιουργεί `target_fwd_5_t = close_{t+5}/close_t - 1` και label `label_t = 1[target_fwd_5_t > 0]`.
5. Η εγγραφή `t` επιτρέπεται στο training μόνο αν ανήκει σε training fold και αν `t < test_start - horizon`. Αλλιώς trim-άρεται ώστε να μη διαρρέει το forward window.
6. Αν η εγγραφή `t` ανήκει στο εκάστοτε test fold και όλες οι feature στήλες είναι μη κενές, το logistic regression παράγει `pred_prob_t`.
7. Το signal layer εφαρμόζει thresholds (`upper=0.55`, `lower=0.45`) και παράγει `signal_prob_t ∈ {-1, 0, 1}`.
8. Στο backtest, το PnL της ημέρας `t+1` χρησιμοποιεί τη θέση της ημέρας `t`, όχι της ίδιας στιγμής. Έτσι αποφεύγεται η lookahead χρήση του ίδιου bar.
9. Η turnover μεταβολή από `position_t - position_{t-1}` χρεώνεται με `risk.cost_per_turnover` και αφαιρείται από τα gross returns.
10. Η τελική χρονοσειρά `equity_curve` και τα OOS metrics αποθηκεύονται μαζί με `config_hash_sha256`, `data_hash_sha256` και git/environment metadata.
