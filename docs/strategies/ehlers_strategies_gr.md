# Ehlers Cycle, Decycler και Trend Pullback Strategies

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

Cycle/trend signal research με Ehlers filters, semiscalp, decycler continuation και meta overlays.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **13**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **0**.
- Κύρια model kinds: `none` (6), `xgboost_clf` (3), `dqn_portfolio_agent` (1), `lightgbm_clf` (1), `logistic_regression_clf` (1), `lstm_forecaster` (1).
- Κύρια signal kinds: `manual_long_model_filter` (6), `ehlers_trend_pullback_continuation_long` (3), `ehlers_semiscalp_long` (2), `none` (1), `ehlers_decycler_continuation` (1).

## Φιλοσοφία

Τα Ehlers strategies χρησιμοποιούν ψηφιακά φίλτρα και cycle decomposition για να ξεχωρίσουν trend, cycle και noise components. Η υπόθεση είναι ότι κάποια intraday setups είναι καλύτερα περιγραφόμενα από phase/cycle state παρά από απλά moving averages.

Η οικογένεια περιλαμβάνει rule-based continuation, semiscalp και meta-model variants. Το σωστό research flow είναι να ελεγχθεί πρώτα το raw Ehlers candidate, μετά να αξιολογηθεί αν το meta model βελτιώνει quality χωρίς να εισάγει leakage.

Επειδή τα cycle filters είναι ευαίσθητα σε smoothing/phase lag, τα docs κρατούν ρητά την απαίτηση ότι κάθε feature πρέπει να βασίζεται μόνο σε παρελθοντικά/current bars. Δεν πρέπει να γίνονται centered filters ή future revisions σε production paths.

## Αρχιτεκτονική

- Feature layer: Hilbert/phase, dominant cycle, MAMA/FAMA, decycler, roofing filters, instantaneous trendline και related Ehlers transforms.
- Signal layer: Ehlers continuation, semiscalp ή ML long candidate filters.
- Model layer: raw/manual configs, XGBoost/LightGBM/logistic/LSTM meta variants και portfolio barrier variants.
- Backtest: barrier/manual holding logic με cost-aware evaluation και optional portfolio construction για multi-asset configs.
- Diagnostics: feature importance για meta models, trade path diagnostics όπου υπάρχουν trades, and fold summaries.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

| Config | Strategy | TF | Assets | Model | Target | Signal | Backtest | Features |
|---|---|---:|---|---|---|---|---|---:|
| [all_assets_30m_ehlers_cycle_dqn_portfolio_v1.yaml](../../config/experiments/ehlers/all_assets_30m_ehlers_cycle_dqn_portfolio_v1.yaml) | `all_assets_30m_ehlers_cycle_dqn_portfolio_v1` | 30m | XAUUSD, XAGUSD, SPX500, US100, GER40, US30, BRENT, ETHUSD, EURUSD, NIKKEI225, USOIL | `dqn_portfolio_agent` | `forward_return` | `none` | `` | 16 |
| [spx500_30m_ehlers_semiscalp_lightgbm_meta_v1.yaml](../../config/experiments/ehlers/spx500_30m_ehlers_semiscalp_lightgbm_meta_v1.yaml) | `spx500_30m_ehlers_semiscalp_lightgbm_meta_v1` | 30m | SPX500 | `lightgbm_clf` | `r_multiple` | `manual_long_model_filter` | `` | 9 |
| [spx500_30m_ehlers_semiscalp_logistic_meta_v1.yaml](../../config/experiments/ehlers/spx500_30m_ehlers_semiscalp_logistic_meta_v1.yaml) | `spx500_30m_ehlers_semiscalp_logistic_meta_v1` | 30m | SPX500 | `logistic_regression_clf` | `r_multiple` | `manual_long_model_filter` | `` | 9 |
| [spx500_30m_ehlers_semiscalp_long_v1.yaml](../../config/experiments/ehlers/spx500_30m_ehlers_semiscalp_long_v1.yaml) | `spx500_30m_ehlers_semiscalp_long_v1` | 30m | SPX500 | `none` | `` | `ehlers_semiscalp_long` | `` | 8 |
| [spx500_30m_ehlers_semiscalp_xgboost_meta_v1.yaml](../../config/experiments/ehlers/spx500_30m_ehlers_semiscalp_xgboost_meta_v1.yaml) | `spx500_30m_ehlers_semiscalp_xgboost_meta_v1` | 30m | SPX500 | `xgboost_clf` | `r_multiple` | `manual_long_model_filter` | `` | 9 |
| [us100_30m_ehlers_decycler_continuation_long_v1.yaml](../../config/experiments/ehlers/us100_30m_ehlers_decycler_continuation_long_v1.yaml) | `us100_30m_ehlers_decycler_continuation_long_v1` | 30m | US100 | `none` | `` | `ehlers_decycler_continuation` | `` | 13 |
| [us100_30m_ehlers_decycler_continuation_xgboost_meta_v1.yaml](../../config/experiments/ehlers/us100_30m_ehlers_decycler_continuation_xgboost_meta_v1.yaml) | `us100_30m_ehlers_decycler_continuation_xgboost_meta_v1` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `manual_long_model_filter` | `` | 14 |
| [xauusd_us100_30m_ehlers_cycle_lstm_meta_v1.yaml](../../config/experiments/ehlers/xauusd_us100_30m_ehlers_cycle_lstm_meta_v1.yaml) | `xauusd_us100_30m_ehlers_cycle_lstm_meta_v1` | 30m | XAUUSD, US100 | `lstm_forecaster` | `triple_barrier` | `manual_long_model_filter` | `` | 16 |
| [xauusd_us100_30m_ehlers_cycle_portfolio_barrier_v1.yaml](../../config/experiments/ehlers/xauusd_us100_30m_ehlers_cycle_portfolio_barrier_v1.yaml) | `xauusd_us100_30m_ehlers_cycle_portfolio_barrier_v1` | 30m | XAUUSD, US100 | `none` | `` | `ehlers_semiscalp_long` | `` | 15 |
| [xauusd_us100_30m_ehlers_cycle_xgboost_meta_v1.yaml](../../config/experiments/ehlers/xauusd_us100_30m_ehlers_cycle_xgboost_meta_v1.yaml) | `xauusd_us100_30m_ehlers_cycle_xgboost_meta_v1` | 30m | XAUUSD, US100 | `xgboost_clf` | `directional_triple_barrier` | `manual_long_model_filter` | `` | 16 |
| [all5_30m_ehlers_trend_pullback_continuation_long_v1.yaml](../../config/experiments/ehlers_trend_pullback_continuation_long/all5_30m_ehlers_trend_pullback_continuation_long_v1.yaml) | `all5_30m_ehlers_trend_pullback_continuation_long_v1` | 30m | XAUUSD, SPX500, US100, GER40, US30 | `none` | `` | `ehlers_trend_pullback_continuation_long` | `` | 12 |
| [us100_30m_ehlers_trend_pullback_continuation_long_v1.yaml](../../config/experiments/ehlers_trend_pullback_continuation_long/us100_30m_ehlers_trend_pullback_continuation_long_v1.yaml) | `us100_30m_ehlers_trend_pullback_continuation_long_v1` | 30m | US100 | `none` | `` | `ehlers_trend_pullback_continuation_long` | `` | 18 |
| [us100_30m_ehlers_trend_pullback_continuation_target_lab_v1.yaml](../../config/experiments/ehlers_trend_pullback_continuation_long/us100_30m_ehlers_trend_pullback_continuation_target_lab_v1.yaml) | `us100_30m_ehlers_trend_pullback_continuation_target_lab_v1` | 30m | US100 | `none` | `` | `ehlers_trend_pullback_continuation_long` | `` | 12 |

## Best διαθέσιμο run

Δεν βρέθηκε logged run με `summary.json` για αυτή την οικογένεια. Το doc περιορίζεται στο checked-in config inventory και στην αρχιτεκτονική.

## Όλα τα logged runs αυτής της οικογένειας

Δεν υπάρχουν logged runs για αυτή την οικογένεια.


## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/ehlers/all_assets_30m_ehlers_cycle_dqn_portfolio_v1.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
