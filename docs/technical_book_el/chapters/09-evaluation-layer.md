## 9. Evaluation Layer

Η evaluation layer αποτελείται από δύο υποσυστήματα:

- Χρονικά splits (`time_splits.py`).
- Backtest/performance metrics (`metrics.py`).

### 9.1 Time Split Semantics

- `time`: ένα μόνο holdout split με `train_frac`.
- `walk_forward`: rolling ή expanding folds χωρίς purge/embargo.
- `purged`: walk-forward με explicit purge και embargo ώστε να αποφευχθεί label overlap ή market microstructure contamination.

### 9.2 Classification Metrics

Ο model layer μετρά:

- `positive_rate`
- `accuracy`
- `brier`
- `roc_auc` όταν υπάρχουν και οι δύο κλάσεις
- `log_loss` όταν υπάρχουν και οι δύο κλάσεις

### 9.3 Backtest Metrics

Το `compute_backtest_metrics()` ενοποιεί PnL και risk metrics: cumulative return, annualized return,
annualized vol, Sharpe, Sortino, Calmar, MDD, profit factor, hit rate, average/total turnover και cost
attribution. Το design είναι σημαντικό: metrics layer δεν ξέρει αν προέρχονται από single asset ή
portfolio, αρκεί να του δοθούν `net_returns`, `turnover`, `costs`, `gross_returns`. Αυτό μειώνει τη σύζευξη.
