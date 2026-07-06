# Miscellaneous Logged Runs

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

Runs που δεν χαρτογραφήθηκαν καθαρά σε checked-in strategy family.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **0**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **24**.

## Φιλοσοφία

Αυτό το αρχείο υπάρχει για audit completeness. Περιλαμβάνει runs από temporary Optuna configs ή παλιότερα paths που δεν αντιστοιχούν άμεσα σε checked-in YAML family. Δεν πρέπει να χρησιμοποιούνται ως canonical strategy definitions χωρίς να βρεθεί ή να ανακατασκευαστεί το αντίστοιχο config.

## Αρχιτεκτονική

- Κάθε run πρέπει να αξιολογείται από το `config_used.yaml`, το `run_metadata.json` και το `report.md` του, όχι από το όνομα φακέλου μόνο.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

Δεν βρέθηκαν checked-in YAML configs για αυτή την οικογένεια.


## Best διαθέσιμο run

Το καλύτερο διαθέσιμο run επιλέχθηκε μηχανικά με προτεραιότητα στο Sharpe όπου υπάρχει, και μετά στο cumulative return/PnL. Αυτό δεν σημαίνει ότι είναι το πιο production-ready run· σημαίνει ότι είναι το ισχυρότερο logged αποτέλεσμα με το διαθέσιμο scoring rule.

- Run: [05_ema_stoch_pullback_meta_base_BEST](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST)
- Config path από metadata: `tmp/optuna_trials/ema_stoch_pullback_meta_base_blcie597.yaml`
- Canonicality: **temporary Optuna trial config**. Το run είναι χρήσιμο ως logged best result, αλλά το ακριβές source YAML δεν είναι checked-in canonical strategy config στο τρέχον tree. Για production/research continuation χρειάζεται να αναπαραχθεί ή να μεταφερθεί σε checked-in config.
- Strategy name: `05_ema_stoch_pullback_meta_base_BEST`
- Model / Signal: `xgboost_clf` / `meta_probability_side`
- Assets: n/a

| Metric | Τιμή |
|---|---:|
| Cumulative return / total PnL | 0.0016 |
| Annualized return | 0.0010 |
| Sharpe | 0.1908 |
| Sortino | 0.3915 |
| Max drawdown | -0.0041 |
| Profit factor | 1.1342 |
| Hit rate | 0.3261 |
| Total cost / fees | 0.0115 |
| Total turnover | 46.0000 |

Κύριο report: [report.md](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report.md)

### Plots του best run

![cumulative_cost_drag.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/cumulative_cost_drag.png)

![cumulative_returns.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/cumulative_returns.png)

![drawdown_curve.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/drawdown_curve.png)

![equity_curve.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/equity_curve.png)

![feature_importance.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/feature_importance.png)

![fold_net_pnl.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/fold_net_pnl.png)

![label_distribution.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/label_distribution.png)

![monthly_returns.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/monthly_returns.png)

![positions_turnover.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/positions_turnover.png)

![prediction_coverage_by_fold.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/prediction_coverage_by_fold.png)

![rolling_behavior.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/rolling_behavior.png)

![rolling_pnl.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/rolling_pnl.png)

![signal_distribution.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/signal_distribution.png)

### Πλήρες artifact inventory του best run

| Artifact | Ρόλος |
|---|---|
| [report.md](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report.md) | Κύριο Markdown report του runner. |
| [summary.json](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/summary.json) | Μηχανικά αναγνώσιμη σύνοψη metrics. |
| [run_metadata.json](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/run_metadata.json) | Metadata αναπαραγωγής, path config και runtime info. |
| [config_used.yaml](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/config_used.yaml) | Το ακριβές resolved config που χρησιμοποιήθηκε στο run. |
| [prediction_diagnostics.json](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/prediction_diagnostics.json) | Forecast/model diagnostic payload. |
| [monitoring_report.json](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/monitoring_report.json) | Drift/monitoring diagnostics. |
| [fold_model_summary.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/fold_model_summary.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [feature_importance.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/feature_importance.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [returns.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [gross_returns.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/gross_returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [equity_curve.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/equity_curve.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [positions.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/positions.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [costs.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/costs.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [turnover.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/turnover.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifact_manifest.json](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/artifact_manifest.json) | JSON diagnostic/metadata artifact. |
| [report_assets/cumulative_cost_drag.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/cumulative_cost_drag.png) | Σωρευτική επίδραση κόστους. |
| [report_assets/cumulative_returns.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/cumulative_returns.png) | Σωρευτικές αποδόσεις. |
| [report_assets/drawdown_curve.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/drawdown_curve.png) | Οπτική απεικόνιση drawdown. |
| [report_assets/equity_curve.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/equity_curve.png) | Οπτική απεικόνιση equity curve. |
| [report_assets/feature_importance.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/feature_importance.png) | Feature importance plot. |
| [report_assets/fold_net_pnl.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/fold_net_pnl.png) | Net PnL ανά fold. |
| [report_assets/label_distribution.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/label_distribution.png) | Plot artifact από το report/diagnostics. |
| [report_assets/monthly_returns.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/monthly_returns.png) | Μηνιαίες αποδόσεις. |
| [report_assets/positions_turnover.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/positions_turnover.png) | Θέσεις και turnover. |
| [report_assets/prediction_coverage_by_fold.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/prediction_coverage_by_fold.png) | Κάλυψη προβλέψεων ανά fold. |
| [report_assets/rolling_behavior.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/rolling_behavior.png) | Rolling behavior diagnostics. |
| [report_assets/rolling_pnl.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/rolling_pnl.png) | Rolling PnL. |
| [report_assets/signal_distribution.png](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/signal_distribution.png) | Plot artifact από το report/diagnostics. |
| [report_assets/trade_events.csv](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report_assets/trade_events.csv) | Trade events για audit. |

## Όλα τα logged runs αυτής της οικογένειας

| Run | Strategy | Sharpe | CumRet/PnL | MaxDD | PF | Cost | Report |
|---|---|---:|---:|---:|---:|---:|---|
| [05_ema_stoch_pullback_meta_base_BEST](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST) | `05_ema_stoch_pullback_meta_base_BEST` | 0.1908 | 0.0016 | -0.0041 | 1.1342 | 0.0115 | [report.md](../../logs/experiments/05_ema_stoch_pullback_meta_base_BEST/report.md) |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_garch_overlay_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_163128_876008_ae3471e3/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_garch_vol_filter_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_181216_114952_85d87588/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_155945_510449_8dde6ff5/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_160212_543986_fd038ad8/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h12_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_160827_328262_1bd6c114/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_hysteresis_20260704_143416_406462_47f5016a/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_no_raw_vol_levels_20260704_140951_265134_61cb2975/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_regime_gated_20260704_141159_183262_c78b2045/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v2_sparse_threshold_grid_20260704_140732_542073_e932ffe7/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_1_remove_calm_abs_20260704_193715_173084_6a63d359/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_2_remove_calm_rank_20260704_194247_008727_78d654d3/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_3_remove_calm_bb_expansion_20260704_194409_963904_67f68343/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_4_abs_range_bb_expansion_20260704_210256_965492_cd42de7e/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_5_gk_additive_20260705_111251_455043_5dd92491/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_6_ehlers_trend_replacement_20260705_122630_980027_bd9f9249/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_122927_309175_b6a5edd2/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_130557_085537_646b742f/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_141427_384967_748825c0/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142225_670698_b9f447a5/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142516_496102_80166fbd/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142659_931684_6c1094e2/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_tail_validation_20260705_142758_740331_64c1477f/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |
| [diagnostics](../../logs/experiments/ethusd_30m_lstm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid_20260705_164947_169834_34a2a425/artifacts/diagnostics) | `diagnostics` | n/a | n/a | n/a | n/a | n/a |  |

## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/<path>.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
