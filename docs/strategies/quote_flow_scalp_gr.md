# Quote Flow Proxy Scalp Strategies

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

Scalp research με proxy microstructure/toxicity filters πάνω σε 5m/30m US100 diagnostics.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **22**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **0**.
- Κύρια model kinds: `xgboost_clf` (22).
- Κύρια signal kinds: `meta_probability_side` (22).

## Φιλοσοφία

Η quote-flow scalp οικογένεια προσπαθεί να μεταφέρει microstructure ιδέες σε bar-level proxy features. Αντί να υποθέτει ότι κάθε breakout ή momentum impulse είναι tradable, προσθέτει φίλτρα toxic flow, spread proxy και short-horizon holding.

Τα diagnostic configs είναι sweep surface: mode variants, thresholds, spread/z-score φίλτρα και EV gates. Σκοπός τους είναι να αποκαλύψουν ποια constraint αφαιρεί περισσότερο κακό flow και ποια απλώς κάνει curve fit.

Επειδή πρόκειται για scalp, το κόστος και η εκτελεσιμότητα είναι κεντρικά. Ένα θετικό gross edge χωρίς robust cost drag δεν πρέπει να θεωρείται usable.

## Αρχιτεκτονική

- Feature layer: quote-flow proxy, spread/toxicity approximations, short-horizon returns και volatility context.
- Signal layer: `quote_flow_proxy_scalp` ή diagnostic QFS modes ανά config.
- Model layer: όπου υπάρχει meta config, classifier/filter πάνω σε scalp candidates.
- Backtest: μικρό horizon, tight TP/SL style parameters και explicit trading cost assumptions.
- Diagnostics: mode sweeps, threshold comparisons, signal density και cost sensitivity.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

| Config | Strategy | TF | Assets | Model | Target | Signal | Backtest | Features |
|---|---|---:|---|---|---|---|---|---:|
| [us100_30m_qfs_all_modes_h2_tp070_sl050_thr043.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h2_tp070_sl050_thr043.yaml) | `us100_30m_qfs_all_modes_h2_tp070_sl050_thr043` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr040.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr040.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr040` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr043.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr043.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr043` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_ev005.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_ev005.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_ev005` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_spread070_z18.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_spread070_z18.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_spread070_z18` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_spread075_z20.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_spread075_z20.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr043_spread075_z20` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr046.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr046.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr046` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr046_ev005.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr046_ev005.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr046_ev005` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr048.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr048.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr048` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_all_modes_h3_tp070_sl050_thr050.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h3_tp070_sl050_thr050.yaml) | `us100_30m_qfs_all_modes_h3_tp070_sl050_thr050` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_mode1_toxic_h3_tp070_sl050_thr043.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_mode1_toxic_h3_tp070_sl050_thr043.yaml) | `us100_30m_qfs_mode1_toxic_h3_tp070_sl050_thr043` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_mode2_sweep_h2_tp070_sl050_thr043.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_mode2_sweep_h2_tp070_sl050_thr043.yaml) | `us100_30m_qfs_mode2_sweep_h2_tp070_sl050_thr043` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043.yaml) | `us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043_ev005.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043_ev005.yaml) | `us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043_ev005` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043_spread075_z20.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043_spread075_z20.yaml) | `us100_30m_qfs_mode2_sweep_h3_tp070_sl050_thr043_spread075_z20` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_mode3_vwap_h3_tp070_sl050_thr043.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_mode3_vwap_h3_tp070_sl050_thr043.yaml) | `us100_30m_qfs_mode3_vwap_h3_tp070_sl050_thr043` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_modes12_toxic_sweep_h3_tp070_sl050_thr043.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_modes12_toxic_sweep_h3_tp070_sl050_thr043.yaml) | `us100_30m_qfs_modes12_toxic_sweep_h3_tp070_sl050_thr043` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_modes23_sweep_vwap_h3_tp070_sl050_thr043.yaml](../../config/experiments/scalp/diagnostics/us100_30m_qfs_modes23_sweep_vwap_h3_tp070_sl050_thr043.yaml) | `us100_30m_qfs_modes23_sweep_vwap_h3_tp070_sl050_thr043` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [quote_flow_proxy_scalp_meta_v1.yaml](../../config/experiments/scalp/quote_flow_proxy_scalp_meta_v1.yaml) | `quote_flow_proxy_scalp_meta_v1` | 5m | REPLACE_ME | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_qfs_best_spread075_z20_v1.yaml](../../config/experiments/scalp/us100_30m_qfs_best_spread075_z20_v1.yaml) | `us100_30m_qfs_best_spread075_z20_v1` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_30m_quote_flow_proxy_scalp_meta_v1.yaml](../../config/experiments/scalp/us100_30m_quote_flow_proxy_scalp_meta_v1.yaml) | `us100_30m_quote_flow_proxy_scalp_meta_v1` | 30m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |
| [us100_5m_quote_flow_proxy_scalp_meta_v1.yaml](../../config/experiments/scalp/us100_5m_quote_flow_proxy_scalp_meta_v1.yaml) | `us100_5m_quote_flow_proxy_scalp_meta_v1` | 5m | US100 | `xgboost_clf` | `directional_triple_barrier` | `meta_probability_side` | `` | 15 |

## Best διαθέσιμο run

Δεν βρέθηκε logged run με `summary.json` για αυτή την οικογένεια. Το doc περιορίζεται στο checked-in config inventory και στην αρχιτεκτονική.

## Όλα τα logged runs αυτής της οικογένειας

Δεν υπάρχουν logged runs για αυτή την οικογένεια.


## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/scalp/diagnostics/us100_30m_qfs_all_modes_h2_tp070_sl050_thr043.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
