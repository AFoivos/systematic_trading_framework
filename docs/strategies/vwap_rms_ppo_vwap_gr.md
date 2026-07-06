# VWAP/RMS/PPO/EMA50 Regime Pullback Strategies

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

Κανόνες pullback/continuation γύρω από VWAP, RMS/PPO momentum και EMA50 regime filter.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **32**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **5**.
- Κύρια model kinds: `none` (28), `lightgbm_clf` (1), `logistic_regression_clf` (1), `lstm_forecaster` (1), `xgboost_clf` (1).
- Κύρια signal kinds: `vwap_rms_ema_cross_long` (28), `manual_long_model_filter` (4).

## Φιλοσοφία

Αυτή η οικογένεια είναι rule-based intraday continuation/pullback. Δεν ξεκινά από supervised alpha forecast, αλλά από market-structure υπόθεση: σε συγκεκριμένα 30m assets, όταν η τιμή έχει trend context και επιστρέφει γύρω από VWAP/RMS bands, η επόμενη κίνηση μπορεί να συνεχίσει προς τη φορά του regime.

Η χρήση EMA50 regime filter και ATR exits κρατά το trade bounded. Η στρατηγική είναι κυρίως long-only στα best configs, με ξεχωριστή short-only επιφάνεια για έλεγχο συμμετρίας. Αυτό είναι χρήσιμο γιατί πολλά index/metal CFDs έχουν διαφορετική συμπεριφορά σε long και short intraday setups.

Τα best configs πρέπει να ερμηνεύονται ως hand-engineered systematic rules με κόστος και turnover, όχι ως γενικός predictor. Η τεκμηρίωση των reports πρέπει να κοιτάει drawdown, trade count, cost drag και stability ανά asset.

## Αρχιτεκτονική

- Data layer: 30m OHLCV ανά asset ή basket, συνήθως cached CSV snapshots.
- Feature layer: VWAP/RMS cross, PPO/MFI/EMA regime, ATR normalization και session-aware filters όπου υπάρχουν.
- Model layer: στα rule-only configs `model.kind: none`; σε meta variants υπάρχουν classifiers ως δεύτερο decision layer.
- Signal layer: `vwap_rms_ema_cross_long`, με long-only ή short-only variants και no-time-exit/ATR-based exits.
- Backtest layer: manual/portfolio barrier style με explicit costs, turnover, positions, equity/drawdown plots και counterfactual exit diagnostics όπου παράγονται.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

| Config | Strategy | TF | Assets | Model | Target | Signal | Backtest | Features |
|---|---|---:|---|---|---|---|---|---:|
| [brent_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/brent_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `brent_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | BRENT | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [ethusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/ethusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `ethusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | ETHUSD | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | EU50 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [ger40_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/ger40_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `ger40_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | GER40 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [nikkei225_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/nikkei225_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `nikkei225_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | NIKKEI225 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | SPX500 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [us100_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/us100_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `us100_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | US100 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | US30 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [usoil_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/usoil_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `usoil_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | USOIL | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_lightgbm_meta_v3.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_lightgbm_meta_v3.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_lightgbm_meta_v3` | 30m | XAUUSD, XAGUSD, SPX500, US100, GER40, US30, BRENT, ETHUSD, EURUSD, NIKKEI225, USOIL | `lightgbm_clf` | `forward_return` | `manual_long_model_filter` | `` | 23 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_logistic_meta_v3.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_logistic_meta_v3.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_logistic_meta_v3` | 30m | XAUUSD, XAGUSD, SPX500, US100, GER40, US30, BRENT, ETHUSD, EURUSD, NIKKEI225, USOIL | `logistic_regression_clf` | `forward_return` | `manual_long_model_filter` | `` | 23 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_lstm_meta_v3.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_lstm_meta_v3.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_lstm_meta_v3` | 30m | XAUUSD, XAGUSD, SPX500, US100, GER40, US30, BRENT, ETHUSD, EURUSD, NIKKEI225, USOIL | `lstm_forecaster` | `future_return_regression` | `manual_long_model_filter` | `` | 23 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_v3.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_v3.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_v3` | 30m | XAUUSD, XAGUSD, SPX500, US100, GER40, US30, BRENT, ETHUSD, EURUSD, NIKKEI225, USOIL | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_xgboost_meta_v3.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_xgboost_meta_v3.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all11_xgboost_meta_v3` | 30m | XAUUSD, XAGUSD, SPX500, US100, GER40, US30, BRENT, ETHUSD, EURUSD, NIKKEI225, USOIL | `xgboost_clf` | `forward_return` | `manual_long_model_filter` | `` | 23 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all5.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all5.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all5` | 30m |  | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2` | 30m |  | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2_live_execution_best_exits.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2_live_execution_best_exits.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2_live_execution_best_exits` | 30m |  | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2_live_execution_parity.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2_live_execution_parity.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all9_v2_live_execution_parity` | 30m |  | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml](../../config/experiments/ema_rms_ppo_vwap/best_long_only/xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml) | `xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 30m | XAUUSD | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [spx500_30m_vwap_rms_cross_scalp_v1.yaml](../../config/experiments/ema_rms_ppo_vwap/long_only/spx500_30m_vwap_rms_cross_scalp_v1.yaml) | `spx500_30m_vwap_rms_cross_scalp_v1` | 30m | SPX500 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [brent_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/brent_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml) | `brent_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only` | 30m | BRENT | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [ethusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/ethusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml) | `ethusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only` | 30m | ETHUSD | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [eurusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/eurusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml) | `eurusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only` | 30m | EURUSD | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [ger40_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/ger40_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml) | `ger40_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only` | 30m | GER40 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [nikkei225_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/nikkei225_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml) | `nikkei225_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only` | 30m | NIKKEI225 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml) | `spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only` | 30m | SPX500 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [us100_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/us100_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml) | `us100_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only` | 30m | US100 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml) | `us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only` | 30m | US30 | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [usoil_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/usoil_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml) | `usoil_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only` | 30m | USOIL | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all5_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all5_short_only.yaml) | `vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_all5_short_only` | 30m |  | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [xagusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/xagusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only.yaml) | `xagusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_short_only` | 30m | XAGUSD | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |
| [xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml](../../config/experiments/ema_rms_ppo_vwap/short_only/xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only.yaml) | `xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_short_only` | 30m | XAUUSD | `none` | `` | `vwap_rms_ema_cross_long` | `` | 7 |

## Best διαθέσιμο run

Το καλύτερο διαθέσιμο run επιλέχθηκε μηχανικά με προτεραιότητα στο Sharpe όπου υπάρχει, και μετά στο cumulative return/PnL. Αυτό δεν σημαίνει ότι είναι το πιο production-ready run· σημαίνει ότι είναι το ισχυρότερο logged αποτέλεσμα με το διαθέσιμο scoring rule.

- Run: [eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c)
- Config path από metadata: `tmp/optuna_trials/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_rptka5or.yaml`
- Canonicality: **temporary Optuna trial config**. Το run είναι χρήσιμο ως logged best result, αλλά το ακριβές source YAML δεν είναι checked-in canonical strategy config στο τρέχον tree. Για production/research continuation χρειάζεται να αναπαραχθεί ή να μεταφερθεί σε checked-in config.
- Strategy name: `eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c`
- Model / Signal: `none` / `vwap_rms_ema_cross_long`
- Assets: n/a

| Metric | Τιμή |
|---|---:|
| Cumulative return / total PnL | 0.0339 |
| Annualized return | 0.0090 |
| Sharpe | 1.0136 |
| Sortino | 1.6142 |
| Max drawdown | -0.0148 |
| Profit factor | 1.7798 |
| Hit rate | 0.6735 |
| Total cost / fees | 0.0090 |
| Total turnover | 35.5633 |

Κύριο report: [report.md](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report.md)

### Plots του best run

![cumulative_cost_drag.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/cumulative_cost_drag.png)

![cumulative_returns.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/cumulative_returns.png)

![drawdown_curve.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/drawdown_curve.png)

![equity_curve.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/equity_curve.png)

![monthly_returns.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/monthly_returns.png)

![positions_turnover.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/positions_turnover.png)

![rolling_behavior.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/rolling_behavior.png)

![rolling_pnl.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/rolling_pnl.png)

![signal_distribution.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/signal_distribution.png)

### Πλήρες artifact inventory του best run

| Artifact | Ρόλος |
|---|---|
| [report.md](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report.md) | Κύριο Markdown report του runner. |
| [summary.json](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/summary.json) | Μηχανικά αναγνώσιμη σύνοψη metrics. |
| [run_metadata.json](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/run_metadata.json) | Metadata αναπαραγωγής, path config και runtime info. |
| [config_used.yaml](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/config_used.yaml) | Το ακριβές resolved config που χρησιμοποιήθηκε στο run. |
| [returns.csv](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [gross_returns.csv](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/gross_returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [equity_curve.csv](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/equity_curve.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [positions.csv](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/positions.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [costs.csv](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/costs.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [turnover.csv](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/turnover.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifact_manifest.json](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/artifact_manifest.json) | JSON diagnostic/metadata artifact. |
| [report_assets/cumulative_cost_drag.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/cumulative_cost_drag.png) | Σωρευτική επίδραση κόστους. |
| [report_assets/cumulative_returns.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/cumulative_returns.png) | Σωρευτικές αποδόσεις. |
| [report_assets/drawdown_curve.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/drawdown_curve.png) | Οπτική απεικόνιση drawdown. |
| [report_assets/equity_curve.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/equity_curve.png) | Οπτική απεικόνιση equity curve. |
| [report_assets/monthly_returns.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/monthly_returns.png) | Μηνιαίες αποδόσεις. |
| [report_assets/positions_turnover.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/positions_turnover.png) | Θέσεις και turnover. |
| [report_assets/rolling_behavior.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/rolling_behavior.png) | Rolling behavior diagnostics. |
| [report_assets/rolling_pnl.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/rolling_pnl.png) | Rolling PnL. |
| [report_assets/signal_distribution.png](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/signal_distribution.png) | Plot artifact από το report/diagnostics. |
| [report_assets/trade_events.csv](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/trade_events.csv) | Trade events για audit. |
| [report_assets/trades.csv](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report_assets/trades.csv) | Executed trades. |

## Όλα τα logged runs αυτής της οικογένειας

| Run | Strategy | Sharpe | CumRet/PnL | MaxDD | PF | Cost | Report |
|---|---|---:|---:|---:|---:|---:|---|
| [eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c) | `eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c` | 1.0136 | 0.0339 | -0.0148 | 1.7798 | 0.0090 | [report.md](../../logs/bot/eu50_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_trial_0004_20260622_033447_639899_ab2f2d7c/report.md) |
| [us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260613_192646_267514_3f622008](../../logs/bot/us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260613_192646_267514_3f622008) | `us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260613_192646_267514_3f622008` | 0.9252 | 0.0913 | -0.0205 | 1.5750 | 0.0417 | [report.md](../../logs/bot/us30_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260613_192646_267514_3f622008/report.md) |
| [xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260625_182041_175337_218e2e62](../../logs/bot/xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260625_182041_175337_218e2e62) | `xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260625_182041_175337_218e2e62` | 0.6719 | 0.1791 | -0.0486 | 1.3986 | 0.0914 | [report.md](../../logs/bot/xauusd_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260625_182041_175337_218e2e62/report.md) |
| [06_spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST](../../logs/experiments/06_spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST) | `06_spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST` | 0.6214 | 0.0749 | -0.0266 | 1.4068 | 0.0469 | [report.md](../../logs/experiments/06_spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST/report.md) |
| [spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260702_201224_582183_47e108bd](../../logs/bot/spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260702_201224_582183_47e108bd) | `spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260702_201224_582183_47e108bd` | 0.5340 | 0.1140 | -0.0481 | 1.4219 | 0.0433 | [report.md](../../logs/bot/spx500_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST_20260702_201224_582183_47e108bd/report.md) |

## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/ema_rms_ppo_vwap/best_long_only/brent_30m_vwap_rms_cross_ema50_regime_3atr_no_time_exit_BEST.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
