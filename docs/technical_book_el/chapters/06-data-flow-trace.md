## 6. Data Flow Trace

Θεωρούμε το configuration `config/experiments/btcusd_1h_dukas_xgboost_triple_barrier_garch_long_oos.yaml`
και μία ημερομηνία `t` του BTCUSD:

1. Το raw OHLCV row εισέρχεται ως `(open_t, high_t, low_t, close_t, volume_t)` από local Dukas CSV μέσω `data.storage.load_path`.
2. Το PIT layer κανονικοποιεί το timestamp σε UTC intraday bar, αφαιρεί duplicates και διατηρεί άθικτο το `volume_t`.
3. Η feature layer δημιουργεί log returns, rolling/EWMA vol, regime ratios, RSI, ATR-normalized range και lagged returns.
4. Ο target builder δημιουργεί triple-barrier event γύρω από το `t`, με upper/lower barriers και vertical barrier `max_holding`.
5. Η εγγραφή `t` επιτρέπεται στο training μόνο αν ανήκει σε training fold και αν `t < test_start - horizon`. Αλλιώς trim-άρεται ώστε να μη διαρρέει το forward window.
6. Αν η εγγραφή `t` ανήκει στο εκάστοτε test fold και όλες οι feature στήλες είναι μη κενές, το XGBoost παράγει `pred_prob_t`.
7. Το signal layer εφαρμόζει dead-zone (`lower`, `upper`), regime activation filters και volatility scaling, και μπορεί να αφήσει το `signal_t = 0`.
8. Στο backtest, το PnL της ώρας `t+1` χρησιμοποιεί τη θέση της ώρας `t`, όχι της ίδιας στιγμής. Έτσι αποφεύγεται η lookahead χρήση του ίδιου bar.
9. Η turnover μεταβολή από `position_t - position_{t-1}` χρεώνεται με `risk.cost_per_turnover` και `risk.slippage_per_turnover` και αφαιρείται από τα gross returns.
10. Η τελική χρονοσειρά `equity_curve` και τα OOS metrics αποθηκεύονται μαζί με `config_hash_sha256`, `data_hash_sha256` και git/environment metadata.
