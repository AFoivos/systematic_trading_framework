# Foundation Alpha και Structured Tail Forecasting

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

ETHUSD 30m forecast-driven tail alpha με LightGBM/XGBoost/deep/foundation forecasters.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **25**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **25**.
- Κύρια model kinds: `lightgbm_regressor` (16), `patchtst_forecaster` (2), `chronos_bolt_forecaster` (1), `lightgbm_clf` (1), `lstm_forecaster` (1), `sarimax_forecaster` (1), `tft_forecaster` (1), `timesfm_2p5_200m_forecaster` (1).
- Κύρια signal kinds: `forecast_threshold` (23), `forecast_threshold_hysteresis` (1), `meta_probability_side` (1).

## Φιλοσοφία

Η οικογένεια `foundation_alpha` αντιμετωπίζει το trading ως πρόβλημα πρόβλεψης κατανομής forward return και όχι ως απλό indicator crossover. Η βασική θέση είναι ότι στα 30m ETHUSD υπάρχουν λίγες, ασύμμετρες ουρές απόδοσης που δεν πρέπει να γίνονται overtrade. Το strategy προσπαθεί να τις πιάσει μόνο όταν το forecast ξεπερνά αυστηρά thresholds.

Η αρχιτεκτονική είναι research-first: παραγωγή αιτιακών features, walk-forward εκπαίδευση, strict OOS predictions, μετατροπή forecast σε sparse signal και backtest με explicit κόστος. Τα configs v3.x είναι ablation surface γύρω από volatility/trend/cycle features, Ehlers replacements και GARCH variants.

Το σημαντικό design constraint είναι ότι το μοντέλο δεν πρέπει να βλέπει labels ή μελλοντικές τιμές. Τα lags, rolling windows, Ehlers features και target horizons πρέπει να παραμένουν χρονικά αιτιακά. Το καλύτερο run πρέπει να διαβάζεται ως OOS research result, όχι ως deployable claim.

## Αρχιτεκτονική

- Data layer: cached Dukascopy 30m ETHUSD, UTC timestamps, PIT metadata και explicit processed snapshots.
- Feature layer: returns/volatility/trend/ATR, candlestick shape, Bollinger/RSI/StochRSI/MACD και Ehlers cycle/trend families στις v3.7 παραλλαγές.
- Model layer: κυρίως `lightgbm_regressor` με `future_return_regression`; συγκριτικά configs για XGBoost, LSTM, PatchTST, TFT, SARIMAX, Chronos και TimesFM.
- Signal layer: `forecast_threshold` ή συγγενικά threshold/hysteresis/vol filters που κάνουν sparse long/short exposure.
- Backtest/evaluation: strict OOS fold aggregation, fold diagnostics, feature importance, prediction coverage, cost drag και baseline diagnostics.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

| Config | Strategy | TF | Assets | Model | Target | Signal | Backtest | Features |
|---|---|---:|---|---|---|---|---|---:|
| [BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_chronos_bolt_h24_tail_alpha_v1.yaml](../../config/experiments/foundation_alpha/ethusd_30m_chronos_bolt_h24_tail_alpha_v1.yaml) | `ethusd_30m_chronos_bolt_h24_tail_alpha_v1` | 30m | ETHUSD | `chronos_bolt_forecaster` | `future_return_regression` | `forecast_threshold` | `` | 4 |
| [ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_lightgbm_garch_vol_filter_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_garch_vol_filter_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_lightgbm_garch_vol_filter_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v1.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v1.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v1` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_hysteresis.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_hysteresis.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_hysteresis` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold_hysteresis` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_no_raw_vol_levels.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_no_raw_vol_levels.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_no_raw_vol_levels` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_regime_gated.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_regime_gated.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_regime_gated` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_sparse_threshold_grid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_sparse_threshold_grid.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_sparse_threshold_grid` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_1_remove_calm_abs.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_1_remove_calm_abs.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_1_remove_calm_abs` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_2_remove_calm_rank.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_2_remove_calm_rank.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_2_remove_calm_rank` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_3_remove_calm_bb_expansion.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_3_remove_calm_bb_expansion.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_3_remove_calm_bb_expansion` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_4_abs_range_bb_expansion.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_4_abs_range_bb_expansion.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_4_abs_range_bb_expansion` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 9 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_5_gk_additive.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_5_gk_additive.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_5_gk_additive` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 13 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_6_ehlers_trend_replacement.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_6_ehlers_trend_replacement.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_6_ehlers_trend_replacement` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation.yaml) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation` | 30m | ETHUSD | `lightgbm_regressor` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_lightgbm_h24_trade_quality_meta_v1.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lightgbm_h24_trade_quality_meta_v1.yaml) | `ethusd_30m_lightgbm_h24_trade_quality_meta_v1` | 30m | ETHUSD | `lightgbm_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 9 |
| [ethusd_30m_lstm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_lstm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_lstm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `lstm_forecaster` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_patchtst_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_patchtst_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_patchtst_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `patchtst_forecaster` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_patchtst_h24_tail_alpha_baseline_v1.yaml](../../config/experiments/foundation_alpha/ethusd_30m_patchtst_h24_tail_alpha_baseline_v1.yaml) | `ethusd_30m_patchtst_h24_tail_alpha_baseline_v1` | 30m | ETHUSD | `patchtst_forecaster` | `future_return_regression` | `forecast_threshold` | `` | 5 |
| [ethusd_30m_sarimax_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_sarimax_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_sarimax_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `sarimax_forecaster` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_tft_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_tft_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_tft_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `tft_forecaster` | `future_return_regression` | `forecast_threshold` | `` | 21 |
| [ethusd_30m_timesfm_2p5_h24_tail_alpha_v1.yaml](../../config/experiments/foundation_alpha/ethusd_30m_timesfm_2p5_h24_tail_alpha_v1.yaml) | `ethusd_30m_timesfm_2p5_h24_tail_alpha_v1` | 30m | ETHUSD | `timesfm_2p5_200m_forecaster` | `future_return_regression` | `forecast_threshold` | `` | 3 |
| [ethusd_30m_xgboost_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml](../../config/experiments/foundation_alpha/ethusd_30m_xgboost_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml) | `ethusd_30m_xgboost_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 30m | ETHUSD | `xgboost_regressor` | `future_return_regression` | `forecast_threshold` | `` | 21 |

## Best διαθέσιμο run

Το καλύτερο διαθέσιμο run επιλέχθηκε μηχανικά με προτεραιότητα στο Sharpe όπου υπάρχει, και μετά στο cumulative return/PnL. Αυτό δεν σημαίνει ότι είναι το πιο production-ready run· σημαίνει ότι είναι το ισχυρότερο logged αποτέλεσμα με το διαθέσιμο scoring rule.

- Run: [ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3)
- Config path από metadata: `config/experiments/foundation_alpha/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml`
- Canonicality: **checked-in strategy config** στο `config/experiments/`.
- Strategy name: `ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid`
- Model / Signal: `lightgbm_regressor` / `forecast_threshold`
- Assets: ETHUSD

| Metric | Τιμή |
|---|---:|
| Cumulative return / total PnL | 2.6539 |
| Annualized return | 0.6792 |
| Sharpe | 2.2953 |
| Sortino | 3.5375 |
| Max drawdown | -0.2110 |
| Profit factor | 1.1142 |
| Hit rate | 0.4889 |
| Total cost / fees | 0.0666 |
| Total turnover | 666.0000 |

Κύριο report: [report.md](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report.md)

### Plots του best run

![cumulative_cost_drag.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/cumulative_cost_drag.png)

![cumulative_returns.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/cumulative_returns.png)

![drawdown_curve.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/drawdown_curve.png)

![equity_curve.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/equity_curve.png)

![feature_importance.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/feature_importance.png)

![fold_cost_to_gross_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/fold_cost_to_gross_pnl.png)

![fold_cumulative_return.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/fold_cumulative_return.png)

![fold_net_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/fold_net_pnl.png)

![fold_sharpe.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/fold_sharpe.png)

![monthly_returns.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/monthly_returns.png)

![positions_turnover.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/positions_turnover.png)

![prediction_coverage_by_fold.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/prediction_coverage_by_fold.png)

![rolling_behavior.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/rolling_behavior.png)

![rolling_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/rolling_pnl.png)

![signal_distribution.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/signal_distribution.png)

![cost_vs_gross_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/cost_vs_gross_pnl.png)

![lgbm_gain_importance.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/lgbm_gain_importance.png)

![lgbm_split_importance.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/lgbm_split_importance.png)

![prediction_autocorrelation.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_autocorrelation.png)

![prediction_histogram.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_histogram.png)

![prediction_quantiles.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_quantiles.png)

![prediction_timeseries.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_timeseries.png)

![prediction_vs_realized.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_vs_realized.png)

![residual_histogram.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/residual_histogram.png)

![turnover_timeseries.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/turnover_timeseries.png)

![turnover_vs_net_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/turnover_vs_net_pnl.png)

### Πλήρες artifact inventory του best run

| Artifact | Ρόλος |
|---|---|
| [report.md](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report.md) | Κύριο Markdown report του runner. |
| [summary.json](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/summary.json) | Μηχανικά αναγνώσιμη σύνοψη metrics. |
| [run_metadata.json](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/run_metadata.json) | Metadata αναπαραγωγής, path config και runtime info. |
| [config_used.yaml](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/config_used.yaml) | Το ακριβές resolved config που χρησιμοποιήθηκε στο run. |
| [prediction_diagnostics.json](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/prediction_diagnostics.json) | Forecast/model diagnostic payload. |
| [monitoring_report.json](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/monitoring_report.json) | Drift/monitoring diagnostics. |
| [fold_model_summary.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/fold_model_summary.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [feature_importance.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/feature_importance.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [returns.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [gross_returns.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/gross_returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [equity_curve.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/equity_curve.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [positions.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/positions.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [costs.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/costs.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [turnover.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/turnover.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifact_manifest.json](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifact_manifest.json) | JSON diagnostic/metadata artifact. |
| [report_assets/cumulative_cost_drag.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/cumulative_cost_drag.png) | Σωρευτική επίδραση κόστους. |
| [report_assets/cumulative_returns.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/cumulative_returns.png) | Σωρευτικές αποδόσεις. |
| [report_assets/drawdown_curve.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/drawdown_curve.png) | Οπτική απεικόνιση drawdown. |
| [report_assets/equity_curve.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/equity_curve.png) | Οπτική απεικόνιση equity curve. |
| [report_assets/feature_importance.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/feature_importance.png) | Feature importance plot. |
| [report_assets/fold_cost_to_gross_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/fold_cost_to_gross_pnl.png) | Plot artifact από το report/diagnostics. |
| [report_assets/fold_cumulative_return.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/fold_cumulative_return.png) | Plot artifact από το report/diagnostics. |
| [report_assets/fold_net_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/fold_net_pnl.png) | Net PnL ανά fold. |
| [report_assets/fold_sharpe.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/fold_sharpe.png) | Sharpe ανά fold. |
| [report_assets/monthly_returns.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/monthly_returns.png) | Μηνιαίες αποδόσεις. |
| [report_assets/positions_turnover.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/positions_turnover.png) | Θέσεις και turnover. |
| [report_assets/prediction_coverage_by_fold.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/prediction_coverage_by_fold.png) | Κάλυψη προβλέψεων ανά fold. |
| [report_assets/rolling_behavior.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/rolling_behavior.png) | Rolling behavior diagnostics. |
| [report_assets/rolling_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/rolling_pnl.png) | Rolling PnL. |
| [report_assets/signal_distribution.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/signal_distribution.png) | Plot artifact από το report/diagnostics. |
| [report_assets/trade_events.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report_assets/trade_events.csv) | Trade events για audit. |
| [artifacts/diagnostics/cost_vs_gross_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/cost_vs_gross_pnl.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/fold_backtest_diagnostics.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/fold_backtest_diagnostics.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/forecast_alpha_diagnostics_summary.json](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/forecast_alpha_diagnostics_summary.json) | JSON diagnostic/metadata artifact. |
| [artifacts/diagnostics/forecast_baselines.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/forecast_baselines.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/lgbm_gain_importance.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/lgbm_gain_importance.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/lgbm_split_importance.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/lgbm_split_importance.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/lightgbm_importance.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/lightgbm_importance.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/prediction_autocorrelation.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_autocorrelation.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/prediction_autocorrelation.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_autocorrelation.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/prediction_distribution.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_distribution.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/prediction_histogram.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_histogram.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/prediction_metrics.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_metrics.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/prediction_quantiles.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_quantiles.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/prediction_quantiles.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_quantiles.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/prediction_timeseries.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_timeseries.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/prediction_vs_realized.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/prediction_vs_realized.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/regime_diagnostics.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/regime_diagnostics.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/regime_performance.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/regime_performance.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/residual_histogram.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/residual_histogram.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/summary.json](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/summary.json) | Μηχανικά αναγνώσιμη σύνοψη metrics. |
| [artifacts/diagnostics/threshold_grid.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/threshold_grid.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/turnover_cost_timeseries.csv](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/turnover_cost_timeseries.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifacts/diagnostics/turnover_timeseries.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/turnover_timeseries.png) | Plot artifact από το report/diagnostics. |
| [artifacts/diagnostics/turnover_vs_net_pnl.png](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics/turnover_vs_net_pnl.png) | Plot artifact από το report/diagnostics. |

## Όλα τα logged runs αυτής της οικογένειας

| Run | Strategy | Sharpe | CumRet/PnL | MaxDD | PF | Cost | Report |
|---|---|---:|---:|---:|---:|---:|---|
| [ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3) | `ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 2.2953 | 2.6539 | -0.2110 | 1.1142 | 0.0666 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_122927_309175_b6a5edd2](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_122927_309175_b6a5edd2) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 2.2953 | 2.6539 | -0.2110 | 1.1142 | 0.0666 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_122927_309175_b6a5edd2/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_6_ehlers_trend_replacement_20260705_122630_980027_bd9f9249](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_6_ehlers_trend_replacement_20260705_122630_980027_bd9f9249) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_6_ehlers_trend_replacement` | 2.1198 | 2.5123 | -0.2696 | 1.1085 | 0.0670 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_6_ehlers_trend_replacement_20260705_122630_980027_bd9f9249/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_1_remove_calm_abs_20260704_193715_173084_6a63d359](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_1_remove_calm_abs_20260704_193715_173084_6a63d359) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_1_remove_calm_abs` | 2.0984 | 3.1738 | -0.3582 | 1.0835 | 0.1044 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_1_remove_calm_abs_20260704_193715_173084_6a63d359/report.md) |
| [ethusd_30m_xgboost_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_162305_894106_c49abbed](../../logs/experiments/ethusd_30m_xgboost_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_162305_894106_c49abbed) | `ethusd_30m_xgboost_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 2.0901 | 2.4276 | -0.2310 | 1.1067 | 0.0678 | [report.md](../../logs/experiments/ethusd_30m_xgboost_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_162305_894106_c49abbed/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_4_abs_range_bb_expansion_20260704_210256_965492_cd42de7e](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_4_abs_range_bb_expansion_20260704_210256_965492_cd42de7e) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_4_abs_range_bb_expansion` | 1.7456 | 1.9070 | -0.2840 | 1.0918 | 0.0682 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_4_abs_range_bb_expansion_20260704_210256_965492_cd42de7e/report.md) |
| [ethusd_30m_lightgbm_garch_vol_filter_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_181216_114952_85d87588](../../logs/experiments/ethusd_30m_lightgbm_garch_vol_filter_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_181216_114952_85d87588) | `ethusd_30m_lightgbm_garch_vol_filter_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 1.6299 | 1.4301 | -0.2251 | 1.0902 | 0.0594 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_garch_vol_filter_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_181216_114952_85d87588/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_3_remove_calm_bb_expansion_20260704_194409_963904_67f68343](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_3_remove_calm_bb_expansion_20260704_194409_963904_67f68343) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_3_remove_calm_bb_expansion` | 1.5614 | 1.6877 | -0.2763 | 1.0822 | 0.0720 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_3_remove_calm_bb_expansion_20260704_194409_963904_67f68343/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_2_remove_calm_rank_20260704_194247_008727_78d654d3](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_2_remove_calm_rank_20260704_194247_008727_78d654d3) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_2_remove_calm_rank` | 1.3027 | 1.6575 | -0.4028 | 1.0571 | 0.1096 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_2_remove_calm_rank_20260704_194247_008727_78d654d3/report.md) |
| [ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_160827_328262_1bd6c114](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_160827_328262_1bd6c114) | `ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 1.1884 | 1.2268 | -0.2441 | 1.0674 | 0.0708 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_160827_328262_1bd6c114/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_regime_gated_20260704_141159_183262_c78b2045](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_regime_gated_20260704_141159_183262_c78b2045) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_regime_gated` | 1.1694 | 1.5659 | -0.3688 | 1.0489 | 0.1156 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_regime_gated_20260704_141159_183262_c78b2045/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_5_gk_additive_20260705_111251_455043_5dd92491](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_5_gk_additive_20260705_111251_455043_5dd92491) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_5_gk_additive` | 1.1452 | 1.1057 | -0.4053 | 1.0661 | 0.0676 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_5_gk_additive_20260705_111251_455043_5dd92491/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_130557_085537_646b742f](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_130557_085537_646b742f) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation` | 1.0528 | 0.5698 | -0.2802 | 1.0642 | 0.0370 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_130557_085537_646b742f/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_141427_384967_748825c0](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_141427_384967_748825c0) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation` | 1.0528 | 0.5698 | -0.2802 | 1.0642 | 0.0370 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_141427_384967_748825c0/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_hysteresis_20260704_143416_406462_47f5016a](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_hysteresis_20260704_143416_406462_47f5016a) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_hysteresis` | 0.9953 | 1.4148 | -0.4552 | 1.0447 | 0.0924 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_hysteresis_20260704_143416_406462_47f5016a/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142225_670698_b9f447a5](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142225_670698_b9f447a5) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation` | 0.9556 | 0.5128 | -0.2850 | 1.0594 | 0.0740 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142225_670698_b9f447a5/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142516_496102_80166fbd](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142516_496102_80166fbd) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation` | 0.8605 | 0.4578 | -0.2899 | 1.0547 | 0.1110 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142516_496102_80166fbd/report.md) |
| [ethusd_30m_lightgbm_h24_trade_quality_meta_v1_20260704_143614_272498_421eebe2](../../logs/experiments/ethusd_30m_lightgbm_h24_trade_quality_meta_v1_20260704_143614_272498_421eebe2) | `ethusd_30m_lightgbm_h24_trade_quality_meta_v1` | 0.8467 | 0.4957 | -0.1577 | 1.1028 | 0.0240 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_trade_quality_meta_v1_20260704_143614_272498_421eebe2/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142659_931684_6c1094e2](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142659_931684_6c1094e2) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation` | 0.6762 | 0.3538 | -0.3066 | 1.0453 | 0.1850 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142659_931684_6c1094e2/report.md) |
| [ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_160212_543986_fd038ad8](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_160212_543986_fd038ad8) | `ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 0.4598 | 0.3400 | -0.2205 | 1.0387 | 0.0514 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_160212_543986_fd038ad8/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_sparse_threshold_grid_20260704_140732_542073_e932ffe7](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_sparse_threshold_grid_20260704_140732_542073_e932ffe7) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_sparse_threshold_grid` | 0.4231 | 0.6092 | -0.4953 | 1.0220 | 0.1554 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_sparse_threshold_grid_20260704_140732_542073_e932ffe7/report.md) |
| [ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_155945_510449_8dde6ff5](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_155945_510449_8dde6ff5) | `ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | 0.3343 | 0.2135 | -0.3037 | 1.0375 | 0.0680 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_155945_510449_8dde6ff5/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142758_740331_64c1477f](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142758_740331_64c1477f) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation` | 0.2486 | 0.1250 | -0.3657 | 1.0224 | 0.3700 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142758_740331_64c1477f/report.md) |
| [ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_no_raw_vol_levels_20260704_140951_265134_61cb2975](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_no_raw_vol_levels_20260704_140951_265134_61cb2975) | `ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_no_raw_vol_levels` | 0.0137 | 0.0165 | -0.5370 | 1.0087 | 0.1624 | [report.md](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_no_raw_vol_levels_20260704_140951_265134_61cb2975/report.md) |
| [ethusd_30m_lstm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_164947_169834_34a2a425](../../logs/experiments/ethusd_30m_lstm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_164947_169834_34a2a425) | `ethusd_30m_lstm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid` | -0.1892 | -0.1578 | -0.4767 | 0.9989 | 0.0811 | [report.md](../../logs/experiments/ethusd_30m_lstm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_164947_169834_34a2a425/report.md) |

## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/foundation_alpha/BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
