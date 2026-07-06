# ROC Long-Only XGBoost R-Multiple Filter

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

Long-only momentum candidate με XGBoost quality filter και R-multiple target.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **0**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **3**.

## Φιλοσοφία

Η ROC long-only οικογένεια ξεκινά από απλή momentum υπόθεση: όταν rate-of-change και related filters δείχνουν θετική ώθηση, το long candidate μπορεί να έχει θετικό expectancy. Το XGBoost δεν δημιουργεί το trade από μηδέν· φιλτράρει candidates βάσει expected R-multiple quality.

Το strategy είναι συντηρητικό ως προς τη φορά: δεν προσπαθεί να κάνει symmetric shorting. Αυτό μειώνει τη dimensionality και επιτρέπει πιο καθαρή αξιολόγηση για assets όπου το long side έχει διαφορετική στατιστική βάση.

Η τεκμηρίωση πρέπει να εστιάζει σε hit rate, profit factor, cost-to-gross, target exit reasons και fold stability, γιατί ένα classifier μπορεί εύκολα να φαίνεται καλό αν απλώς αραιώνει υπερβολικά τα trades.

## Αρχιτεκτονική

- Candidate layer: manual long candidates από ROC/trend/momentum filters.
- Target layer: R-multiple ή barrier-derived labels για trade quality.
- Model layer: `xgboost_clf` quality filter με walk-forward splits.
- Signal layer: `manual_long_model_filter`, δηλαδή εκτέλεση μόνο όταν raw long candidate και model approval συμφωνούν.
- Artifacts: label distributions, target winner/loser features, feature importance, equity/drawdown/cost plots.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

Δεν βρέθηκαν checked-in YAML configs για αυτή την οικογένεια.

Σημείωση ROC: τα διαθέσιμα best runs δείχνουν ότι η οικογένεια υπήρχε σε temporary Optuna trial configs, αλλά στο τρέχον checked-in `config/experiments/` δεν βρέθηκαν canonical ROC YAML files. Γι αυτό το αρχείο λειτουργεί ως run-level τεκμηρίωση και όχι ως πλήρες config catalog.


## Best διαθέσιμο run

Το καλύτερο διαθέσιμο run επιλέχθηκε μηχανικά με προτεραιότητα στο Sharpe όπου υπάρχει, και μετά στο cumulative return/PnL. Αυτό δεν σημαίνει ότι είναι το πιο production-ready run· σημαίνει ότι είναι το ισχυρότερο logged αποτέλεσμα με το διαθέσιμο scoring rule.

- Run: [03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST)
- Config path από metadata: `tmp/optuna_trials/xauusd_roc_long_only_xgboost_r_multiple_filter_dynamic_stop_9389k7fp.yaml`
- Canonicality: **temporary Optuna trial config**. Το run είναι χρήσιμο ως logged best result, αλλά το ακριβές source YAML δεν είναι checked-in canonical strategy config στο τρέχον tree. Για production/research continuation χρειάζεται να αναπαραχθεί ή να μεταφερθεί σε checked-in config.
- Strategy name: `03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST`
- Model / Signal: `xgboost_clf` / `manual_long_model_filter`
- Assets: n/a

| Metric | Τιμή |
|---|---:|
| Cumulative return / total PnL | 0.2076 |
| Annualized return | 0.1072 |
| Sharpe | 1.5733 |
| Sortino | 2.6181 |
| Max drawdown | -0.0492 |
| Profit factor | 1.2290 |
| Hit rate | 0.4779 |
| Total cost / fees | 0.2245 |
| Total turnover | 857.1025 |

Κύριο report: [report.md](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report.md)

### Plots του best run

![cumulative_cost_drag.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/cumulative_cost_drag.png)

![cumulative_returns.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/cumulative_returns.png)

![drawdown_curve.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/drawdown_curve.png)

![equity_curve.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/equity_curve.png)

![feature_importance.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/feature_importance.png)

![fold_net_pnl.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/fold_net_pnl.png)

![label_distribution.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/label_distribution.png)

![monthly_returns.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/monthly_returns.png)

![positions_turnover.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/positions_turnover.png)

![prediction_coverage_by_fold.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/prediction_coverage_by_fold.png)

![rolling_behavior.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/rolling_behavior.png)

![rolling_pnl.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/rolling_pnl.png)

![signal_distribution.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/signal_distribution.png)

### Πλήρες artifact inventory του best run

| Artifact | Ρόλος |
|---|---|
| [report.md](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report.md) | Κύριο Markdown report του runner. |
| [summary.json](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/summary.json) | Μηχανικά αναγνώσιμη σύνοψη metrics. |
| [run_metadata.json](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/run_metadata.json) | Metadata αναπαραγωγής, path config και runtime info. |
| [config_used.yaml](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/config_used.yaml) | Το ακριβές resolved config που χρησιμοποιήθηκε στο run. |
| [prediction_diagnostics.json](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/prediction_diagnostics.json) | Forecast/model diagnostic payload. |
| [monitoring_report.json](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/monitoring_report.json) | Drift/monitoring diagnostics. |
| [fold_model_summary.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/fold_model_summary.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [feature_importance.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/feature_importance.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [returns.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [gross_returns.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/gross_returns.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [equity_curve.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/equity_curve.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [positions.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/positions.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [costs.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/costs.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [turnover.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/turnover.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [artifact_manifest.json](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/artifact_manifest.json) | JSON diagnostic/metadata artifact. |
| [report_assets/cumulative_cost_drag.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/cumulative_cost_drag.png) | Σωρευτική επίδραση κόστους. |
| [report_assets/cumulative_returns.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/cumulative_returns.png) | Σωρευτικές αποδόσεις. |
| [report_assets/drawdown_curve.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/drawdown_curve.png) | Οπτική απεικόνιση drawdown. |
| [report_assets/equity_curve.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/equity_curve.png) | Οπτική απεικόνιση equity curve. |
| [report_assets/feature_importance.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/feature_importance.png) | Feature importance plot. |
| [report_assets/fold_net_pnl.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/fold_net_pnl.png) | Net PnL ανά fold. |
| [report_assets/label_distribution.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/label_distribution.png) | Plot artifact από το report/diagnostics. |
| [report_assets/monthly_returns.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/monthly_returns.png) | Μηνιαίες αποδόσεις. |
| [report_assets/positions_turnover.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/positions_turnover.png) | Θέσεις και turnover. |
| [report_assets/prediction_coverage_by_fold.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/prediction_coverage_by_fold.png) | Κάλυψη προβλέψεων ανά fold. |
| [report_assets/rolling_behavior.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/rolling_behavior.png) | Rolling behavior diagnostics. |
| [report_assets/rolling_pnl.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/rolling_pnl.png) | Rolling PnL. |
| [report_assets/signal_distribution.png](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/signal_distribution.png) | Plot artifact από το report/diagnostics. |
| [report_assets/target_events.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/target_events.csv) | CSV artifact για audit ή περαιτέρω ανάλυση. |
| [report_assets/trade_events.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/trade_events.csv) | Trade events για audit. |
| [report_assets/trades.csv](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report_assets/trades.csv) | Executed trades. |

## Όλα τα logged runs αυτής της οικογένειας

| Run | Strategy | Sharpe | CumRet/PnL | MaxDD | PF | Cost | Report |
|---|---|---:|---:|---:|---:|---:|---|
| [03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST) | `03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST` | 1.5733 | 0.2076 | -0.0492 | 1.2290 | 0.2245 | [report.md](../../logs/experiments/03_xauusd_roc_long_only_xgboost_r_multiple_filter_trial_BEST/report.md) |
| [04_spx500_roc_long_only_xgboost_r_multiple_filter_BEST](../../logs/experiments/04_spx500_roc_long_only_xgboost_r_multiple_filter_BEST) | `04_spx500_roc_long_only_xgboost_r_multiple_filter_BEST` | 1.4780 | 0.0615 | -0.0211 | 1.4656 | 0.0498 | [report.md](../../logs/experiments/04_spx500_roc_long_only_xgboost_r_multiple_filter_BEST/report.md) |
| [01_xauusd_roc_long_only_xgboost_r_multiple_filter_BEST](../../logs/experiments/01_xauusd_roc_long_only_xgboost_r_multiple_filter_BEST) | `01_xauusd_roc_long_only_xgboost_r_multiple_filter_BEST` | 1.2917 | 0.1112 | -0.0352 | 1.3301 | 0.0851 | [report.md](../../logs/experiments/01_xauusd_roc_long_only_xgboost_r_multiple_filter_BEST/report.md) |

## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/<path>.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
