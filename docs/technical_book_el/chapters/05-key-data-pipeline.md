## 5. Key Data Pipeline

### 5.1 Entry Point

Το canonical entry point είναι η CLI εκτέλεση:

```bash
python -m src.experiments.runner config/experiments/logreg_spy.yaml
```

Ο πυρήνας της εκτέλεσης είναι η `run_experiment()` που ενοποιεί configuration, data retrieval, feature
engineering, model fitting, signal generation, evaluation, monitoring, execution και persistence.

### 5.2 Data Ingestion

- Ο `load_experiment_config()` παραδίδει normalized `data` block.
- Ο `_resolve_symbols()` επιλύει single-symbol ή multi-symbol μορφή.
- Ο `_load_asset_frames()` αποφασίζει αν θα φορτώσει από cache (`live_or_cached`, `cached_only`) ή από live provider.
- Οι providers (`YahooFinanceProvider`, `AlphaVantageFXProvider`) μετατρέπουν raw response στο canonical OHLCV schema.

### 5.3 Preprocessing / PIT Hardening

- Το `align_ohlcv_timestamps()` επιβάλλει timezone normalization, monotonic sorting και duplicate policy.
- Το `apply_corporate_actions_policy()` μετατρέπει raw ή adjusted prices βάσει policy.
- Προαιρετικά, το `load_universe_snapshot()` και `assert_symbol_in_snapshot()` αποκλείουν survivorship leakage ως προς το universe membership.
- Το `validate_ohlcv()` και `validate_data_contract()` διασφαλίζουν structural integrity πριν παραχθούν features.

### 5.4 Feature Engineering

Κάθε feature step είναι declarative YAML entry με `step` και `params`. Ο runner καλεί `get_feature_fn()` και
εκτελεί διαδοχικά pandas-based transforms. Αυτό σημαίνει ότι το feature pipeline είναι composable και
deterministic: η σειρά βημάτων στο YAML καθορίζει πλήρως το παραγόμενο feature space.

Χαρακτηριστικοί τύποι features:

- Returns: simple ή log returns.
- Volatility: rolling και EWMA realized vol.
- Trend: SMA/EMA levels και relative price-to-MA spreads.
- Trend regime: sign-based και MA-cross state encodings.
- Oscillators: RSI, Stochastic %K/%D.
- Indicators: Bollinger, MACD, PPO, ATR, ADX, ROC, MFI, volume z-score.
- Lags: explicit causal lagging των feature columns.

### 5.5 Modeling

Ο model layer παίρνει το feature-enriched DataFrame και χτίζει target labels τύπου forward return:

$$
r^{(h)}_t = 
rac{P_{t+h}}{P_t} - 1
$$

Για binary classification:

$$
y_t = \mathbf{1}[r^{(h)}_t > 	au]
$$

με τυπικό threshold $	au = 0$. Η εκπαίδευση γίνεται μόνο σε χρονικά έγκυρα folds, με trimming των
τελευταίων training rows ώστε το forward label window να μη διασταυρώνεται με το test window.

### 5.6 Evaluation

- Ο `build_time_splits()` παράγει chronological folds.
- Ο `_train_forward_classifier()` επιστρέφει `pred_is_oos` mask και fold-level classification metrics.
- Το `run_backtest()` ή `compute_portfolio_performance()` παράγει time-series performance.
- Το `_build_single_asset_evaluation()` ή `_build_portfolio_evaluation()` απομονώνει strict OOS summary όταν υπάρχουν model folds.

### 5.7 Output Storage

Τα artifacts γράφονται σε timestamped run directory και περιλαμβάνουν:

- `config_used.yaml`
- `summary.json`
- `run_metadata.json`
- `equity_curve.csv`, `returns.csv`, `gross_returns.csv`, `costs.csv`, `turnover.csv`
- `positions.csv` για single-asset
- `portfolio_weights.csv`, `portfolio_diagnostics.csv` για multi-asset
- `paper_orders.csv` όταν το execution layer είναι ενεργό
- `artifact_manifest.json` με SHA-256 hashes των παραχθέντων files

### 5.8 Sequence Explanation

**Single-Asset Path**

1. Ο operator εκκινεί `python -m src.experiments.runner <config>`.
2. Το `load_experiment_config()` φορτώνει inheritance chain, defaults και validations.
3. Το `apply_runtime_reproducibility()` παγώνει seed, thread env vars και deterministic runtime knobs.
4. Το `_load_asset_frames()` διαβάζει raw OHLCV από provider ή cached snapshot.
5. Το `apply_pit_hardening()` ευθυγραμμίζει timestamps, εφαρμόζει corporate action policy και universe membership checks.
6. Το `validate_ohlcv()` και `validate_data_contract()` απορρίπτουν malformed market data πριν από feature generation.
7. Το `_apply_feature_steps()` εκτελεί διαδοχικά feature transforms πάνω στο asset frame.
8. Το `_apply_model_step()` καλεί `train_lightgbm_classifier()` ή `train_logistic_regression_classifier()`.
9. Ο model layer χτίζει forward labels, chronological splits, OOS predictions και classification diagnostics.
10. Το `_apply_signal_step()` μετατρέπει predictions ή states σε trading signal.
11. Το `_run_single_asset_backtest()` περνά το signal στο `run_backtest()` για cost-aware PnL accounting.
12. Το `_build_single_asset_evaluation()` απομονώνει strict OOS metrics όταν υπάρχουν model folds.
13. Το `_compute_monitoring_report()` συγκρίνει IS vs OOS feature distributions για drift.
14. Το `_build_execution_output()` παράγει τελευταίο target weight/order export για paper execution.
15. Το `_save_artifacts()` γράφει summary, returns, equity curve, metadata και manifest στον φάκελο run.

**Multi-Asset / Portfolio Path**

1. Το config δηλώνει πολλαπλά `data.symbols` ή `portfolio.enabled: true`.
2. Ο loader επιστρέφει dict από asset -> DataFrame και κάθε asset περνά ανεξάρτητο PIT hardening και feature pipeline.
3. Ο model layer εκπαιδεύει ανά asset, συλλέγει per-asset metadata και παράγει aggregated OOS summary.
4. Τα signals ευθυγραμμίζονται σε κοινό panel μέσω `_align_asset_column()` με `inner` ή `outer` join.
5. Αν `construction = signal_weights`, τα signals προβάλλονται σε constrained weights. Αν `construction = mean_variance`, χρησιμοποιείται rolling covariance και expected returns panel.
6. Το `compute_portfolio_performance()` εφαρμόζει lagged weights, turnover costs και portfolio-level equity accounting.
7. Το portfolio evaluation ορίζει OOS dates ως union των ημερομηνιών όπου τουλάχιστον ένα asset έχει `pred_is_oos = True`.
8. Το execution layer μετατρέπει τα τελευταία portfolio weights σε rebalancing order blotter ανά asset.
