# Other Strategy Families και Legacy Research Surfaces

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

Shock meta, FTMO swing, dense return forecasting, PPO trend και λοιπά standalone configs.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **14**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **2**.
- Κύρια model kinds: `none/unspecified` (7), `xgboost_clf` (2), `lightgbm_clf` (2), `lightgbm_regressor` (1), `none` (1), `tsfresh_extrema_feature_discovery` (1).
- Κύρια signal kinds: `meta_probability_side` (8), `probability_threshold` (2), `none` (2), `dense_return_forecast` (1), `ppo_adx_stochrsi_trend` (1).

## Φιλοσοφία

Ο φάκελος `others` περιέχει ανεξάρτητες research surfaces που δεν ανήκουν καθαρά στις μεγάλες οικογένειες. Εδώ υπάρχουν shock meta classifiers, FTMO swing panels, indicator pullback configs, PPO trend experiments και dense return forecasting.

Η φιλοσοφία είναι να διατηρούνται τα standalone experiments reproducible χωρίς να μολύνουν τα βασικά strategy families. Κάθε config πρέπει να εξηγείται από το δικό του target/model/signal contract και όχι από γενική αφήγηση.

Για αυτά τα configs η τεκμηρίωση είναι περισσότερο catalog/audit παρά ενιαία trading thesis. Όπου υπάρχουν logged best runs, τα αναφέρουμε· όπου δεν υπάρχουν, το doc το δηλώνει ρητά.

## Αρχιτεκτονική

- Shock meta: event/candidate generation και XGBoost probability thresholding.
- FTMO swing: panel/single-asset LightGBM alpha meta με barrier targets και account-style constraints.
- Indicator pullback: classic technical feature stack με model/barrier variants.
- Dense return forecasting: direct forecast-to-signal flow με portfolio/execution settings.
- PPO trend: reinforcement-learning style candidate, kept separate from deterministic supervised pipelines.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

| Config | Strategy | TF | Assets | Model | Target | Signal | Backtest | Features |
|---|---|---:|---|---|---|---|---|---:|
| [btcusd_1h_shock_meta_xgboost_long_only.yaml](../../config/experiments/others/btcusd_1h_shock_meta_xgboost_long_only.yaml) | `btcusd_1h_shock_meta_xgboost_long_only` | 1h | BTCUSD | `xgboost_clf` | `triple_barrier` | `probability_threshold` | `` | 8 |
| [btcusd_30m_shock_meta_xgboost_long_only_v1.yaml](../../config/experiments/others/btcusd_30m_shock_meta_xgboost_long_only_v1.yaml) | `btcusd_30m_shock_meta_xgboost_long_only_v1` | 30m | BTCUSD | `xgboost_clf` | `triple_barrier` | `probability_threshold` | `` | 8 |
| [dense_return_forecasting_v2.yaml](../../config/experiments/others/dense_return_forecasting_v2.yaml) | `dense_return_forecasting_v2` | 30m | XAUUSD, US100, US30, SPX500, GER40 | `lightgbm_regressor` | `future_return_regression` | `dense_return_forecast` | `` | 13 |
| [eurusd_m15_ppo_adx_stochrsi_trend.yaml](../../config/experiments/others/eurusd_m15_ppo_adx_stochrsi_trend.yaml) | `eurusd_m15_ppo_adx_stochrsi_trend` | 15m | EURUSD | `none` | `` | `ppo_adx_stochrsi_trend` | `` | 6 |
| [ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_barrier_v2.yaml](../../config/experiments/others/ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_barrier_v2.yaml) | `ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_barrier_v2` | 1h | EURUSD, GBPUSD, AUDUSD, USDJPY | `none` | `` | `meta_probability_side` | `` | 19 |
| [ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_barrier_v3.yaml](../../config/experiments/others/ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_barrier_v3.yaml) | `ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_barrier_v3` | 1h | EURUSD, GBPUSD, AUDUSD, USDJPY | `none` | `` | `meta_probability_side` | `` | 19 |
| [ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_v1.yaml](../../config/experiments/others/ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_v1.yaml) | `ftmo_fx_swing_panel_4pair_lightgbm_alpha_meta_v1` | 1h | EURUSD, GBPUSD, AUDUSD, USDJPY | `none` | `` | `meta_probability_side` | `` | 19 |
| [ftmo_fx_swing_singleasset_eurusd_m15_ablation_01_rules_only.yaml](../../config/experiments/others/ftmo_fx_swing_singleasset_eurusd_m15_ablation_01_rules_only.yaml) | `ftmo_fx_swing_singleasset_eurusd_m15_ablation_01_rules_only` | 15m | EURUSD | `none` | `` | `none` | `` | 19 |
| [ftmo_fx_swing_singleasset_eurusd_m15_ablation_02_ml_filter.yaml](../../config/experiments/others/ftmo_fx_swing_singleasset_eurusd_m15_ablation_02_ml_filter.yaml) | `ftmo_fx_swing_singleasset_eurusd_m15_ablation_02_ml_filter` | 15m | EURUSD | `none` | `` | `meta_probability_side` | `` | 19 |
| [ftmo_fx_swing_singleasset_eurusd_m15_ablation_03_full.yaml](../../config/experiments/others/ftmo_fx_swing_singleasset_eurusd_m15_ablation_03_full.yaml) | `ftmo_fx_swing_singleasset_eurusd_m15_ablation_03_full` | 15m | EURUSD | `none` | `` | `meta_probability_side` | `` | 19 |
| [ftmo_fx_swing_singleasset_eurusd_m15_lightgbm_alpha_meta_barrier_v3.yaml](../../config/experiments/others/ftmo_fx_swing_singleasset_eurusd_m15_lightgbm_alpha_meta_barrier_v3.yaml) | `ftmo_fx_swing_singleasset_eurusd_m15_lightgbm_alpha_meta_barrier_v3` | 15m | EURUSD | `none` | `` | `meta_probability_side` | `` | 19 |
| [indicator_model_adaptive_pullback_barrier.yaml](../../config/experiments/others/indicator_model_adaptive_pullback_barrier.yaml) | `indicator_model_adaptive_pullback` | 30m | XAUUSD, US100, US30, SPX500, GER40 | `lightgbm_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 12 |
| [indicator_model_adaptive_pullback_base.yaml](../../config/experiments/others/indicator_model_adaptive_pullback_base.yaml) | `indicator_model_adaptive_pullback` | 30m | XAUUSD, US100, US30, SPX500, GER40 | `lightgbm_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 12 |
| [tsfresh_extrema_discovery.yaml](../../config/experiments/others/tsfresh_extrema_discovery.yaml) | `tsfresh_extrema_discovery` | 30m | SPX500 | `tsfresh_extrema_feature_discovery` | `` | `none` | `` | 10 |

## Best διαθέσιμο run

Το καλύτερο διαθέσιμο run επιλέχθηκε μηχανικά με προτεραιότητα στο Sharpe όπου υπάρχει, και μετά στο cumulative return/PnL. Αυτό δεν σημαίνει ότι είναι το πιο production-ready run· σημαίνει ότι είναι το ισχυρότερο logged αποτέλεσμα με το διαθέσιμο scoring rule.

- Run: [02_btcusd_1h_shock_meta_xgboost_long_only_BEST](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST)
- Config path από metadata: `config/experiments/btcusd_1h_shock_meta_xgboost_long_only.yaml`
- Canonicality: **checked-in strategy config** στο `config/experiments/`.
- Strategy name: `02_btcusd_1h_shock_meta_xgboost_long_only_BEST`
- Model / Signal: `xgboost_clf` / `probability_threshold`
- Assets: n/a

| Metric | Τιμή |
|---|---:|
| Cumulative return / total PnL | 0.5589 |
| Annualized return | 0.0819 |
| Sharpe | 0.6442 |
| Sortino | 1.3560 |
| Max drawdown | -0.1720 |
| Profit factor | 1.3600 |
| Hit rate | 0.3947 |
| Total cost / fees | 0.2795 |
| Total turnover | 430.0000 |

Κύριο report: [report.md](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report.md)

### Plots του best run

![cumulative_cost_drag.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/cumulative_cost_drag.png)

![cumulative_returns.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/cumulative_returns.png)

![drawdown_curve.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/drawdown_curve.png)

![equity_curve.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/equity_curve.png)

![feature_importance.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/feature_importance.png)

![fold_net_pnl.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/fold_net_pnl.png)

![label_distribution.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/label_distribution.png)

![monthly_returns.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/monthly_returns.png)

![positions_turnover.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/positions_turnover.png)

![prediction_coverage_by_fold.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/prediction_coverage_by_fold.png)

![rolling_behavior.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/rolling_behavior.png)

![rolling_pnl.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/rolling_pnl.png)

![signal_distribution.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/signal_distribution.png)

### Πλήρες artifact inventory του best run

| Artifact | Ρόλος |
|---|---|
| [report.md](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report.md) | Κύριο Markdown report του runner. |
| [summary.json](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/summary.json) | Μηχανικά αναγνώσιμη σύνοψη metrics. |
| [run_metadata.json](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/run_metadata.json) | Metadata αναπαραγωγής, path config και runtime info. |
| [config_used.yaml](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/config_used.yaml) | Το ακριβές resolved config που χρησιμοποιήθηκε στο run. |
| [prediction_diagnostics.json](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/prediction_diagnostics.json) | Forecast/model diagnostic payload. |
| [monitoring_report.json](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/monitoring_report.json) | Drift/monitoring diagnostics. |
| [fold_model_summary.csv](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/fold_model_summary.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [feature_importance.csv](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/feature_importance.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [returns.csv](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [gross_returns.csv](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/gross_returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [equity_curve.csv](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/equity_curve.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [positions.csv](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/positions.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [costs.csv](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/costs.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [turnover.csv](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/turnover.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifact_manifest.json](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/artifact_manifest.json) | JSON diagnostic/metadata artifact. |
| [report_assets/cumulative_cost_drag.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/cumulative_cost_drag.png) | Σωρευτική επίδραση κόστους. |
| [report_assets/cumulative_returns.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/cumulative_returns.png) | Σωρευτικές αποδόσεις. |
| [report_assets/drawdown_curve.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/drawdown_curve.png) | Οπτική απεικόνιση drawdown. |
| [report_assets/equity_curve.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/equity_curve.png) | Οπτική απεικόνιση equity curve. |
| [report_assets/feature_importance.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/feature_importance.png) | Feature importance plot. |
| [report_assets/fold_net_pnl.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/fold_net_pnl.png) | Net PnL ανά fold. |
| [report_assets/label_distribution.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/label_distribution.png) | Plot artifact από το report/diagnostics. |
| [report_assets/monthly_returns.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/monthly_returns.png) | Μηνιαίες αποδόσεις. |
| [report_assets/positions_turnover.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/positions_turnover.png) | Θέσεις και turnover. |
| [report_assets/prediction_coverage_by_fold.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/prediction_coverage_by_fold.png) | Κάλυψη προβλέψεων ανά fold. |
| [report_assets/rolling_behavior.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/rolling_behavior.png) | Rolling behavior diagnostics. |
| [report_assets/rolling_pnl.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/rolling_pnl.png) | Rolling PnL. |
| [report_assets/signal_distribution.png](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report_assets/signal_distribution.png) | Plot artifact από το report/diagnostics. |

## Όλα τα logged runs αυτής της οικογένειας

| Run | Strategy | Sharpe | CumRet/PnL | MaxDD | PF | Cost | Report |
|---|---|---:|---:|---:|---:|---:|---|
| [02_btcusd_1h_shock_meta_xgboost_long_only_BEST](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST) | `02_btcusd_1h_shock_meta_xgboost_long_only_BEST` | 0.6442 | 0.5589 | -0.1720 | 1.3600 | 0.2795 | [report.md](../../logs/experiments/02_btcusd_1h_shock_meta_xgboost_long_only_BEST/report.md) |
| [07_btcusd_1h_shock_meta_xgboost_long_only_20260602_134419_970710_61d98b4c](../../logs/experiments/07_btcusd_1h_shock_meta_xgboost_long_only_20260602_134419_970710_61d98b4c) | `07_btcusd_1h_shock_meta_xgboost_long_only_20260602_134419_970710_61d98b4c` | 0.6442 | 0.5589 | -0.1720 | 1.3600 | 0.2795 | [report.md](../../logs/experiments/07_btcusd_1h_shock_meta_xgboost_long_only_20260602_134419_970710_61d98b4c/report.md) |

## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/others/btcusd_1h_shock_meta_xgboost_long_only.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
