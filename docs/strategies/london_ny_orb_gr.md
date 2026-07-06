# London/NY Opening Range Breakout v3

> Ελληνική τεκμηρίωση strategy family. Το αρχείο είναι source-backed από τα YAML configs και τα διαθέσιμα logged artifacts στο repo. Δεν αποτελεί επενδυτική σύσταση και δεν υποκαθιστά ανεξάρτητο leakage/reproducibility review πριν από production χρήση.

## Σύνοψη

Session breakout research για XAU/indices με raw, tree meta και stacked overlay layers.

- Πλήθος checked-in configs που χαρτογραφήθηκαν: **42**.
- Πλήθος logged runs που χαρτογραφήθηκαν: **0**.
- Κύρια model kinds: `none/unspecified` (24), `none` (18).
- Κύρια signal kinds: `meta_probability_side` (24), `orb_candidate_side` (18).

## Φιλοσοφία

Η οικογένεια London_NY εξετάζει αν η πρώτη φάση μιας συνεδρίας δημιουργεί πληροφορία για directional continuation. Το raw signal είναι opening-range breakout candidate και τα tree/stack layers προσπαθούν να φιλτράρουν χαμηλής ποιότητας breakouts.

Το design είναι σκόπιμα layered: πρώτα raw baseline, μετά per-asset/session tree meta, μετά basket-level stack. Αυτό μειώνει τον κίνδυνο να θεωρηθεί ότι ένα περίπλοκο μοντέλο έχει edge χωρίς να έχει κερδίσει το raw candidate set.

Κρίσιμο σημείο είναι η αιτιότητα των session windows: το opening range πρέπει να έχει ολοκληρωθεί πριν χρησιμοποιηθεί, τα breakouts πρέπει να εμφανίζονται μετά το range και τα labels να υπολογίζονται μόνο για evaluation/training folds.

## Αρχιτεκτονική

- Raw layer: `orb_candidate_side` χωρίς meta model, για καθαρό diagnostic baseline.
- Tree-only layer: `xgboost_clf`/`lightgbm_clf` meta classifiers πάνω στα ORB candidates.
- Stack layer: staged model pipeline `tree_meta_base -> tft_regime_overlay -> ensemble_decision` όπου το TFT λειτουργεί ως regime/quality overlay.
- Portfolio layer: one-sided variants και basket normalization με FTMO-style leverage/drawdown guards.
- Evaluation: raw-vs-meta-vs-stack σύγκριση, cost drag, turnover, FTMO breaches και fold-level stability.

## Causality, leakage και reproducibility guardrails

- Τα features πρέπει να υπολογίζονται μόνο από διαθέσιμες τιμές στο timestamp απόφασης. Rolling windows, lags και session aggregates δεν πρέπει να κοιτούν future bars.
- Τα model splits πρέπει να παραμένουν walk-forward/purged όπου ορίζεται, με OOS predictions να παράγονται μόνο για test rows.
- Τα labels, barrier outcomes και forward returns είναι training/evaluation targets. Δεν πρέπει να χρησιμοποιούνται στο signal layer εκτός OOS prediction output.
- Τα logged metrics πρέπει να διαβάζονται μαζί με costs, turnover, drawdown και fold dispersion. Υψηλό cumulative return με ασταθή folds ή τεράστιο cost drag δεν είναι robust edge.
- Τα links σε `logs/` είναι artifacts του τρέχοντος workspace. Αν λείπουν σε άλλο clone, το config παραμένει η canonical προδιαγραφή και το run πρέπει να αναπαραχθεί.

## Inventory configs

| Config | Strategy | TF | Assets | Model | Target | Signal | Backtest | Features |
|---|---|---:|---|---|---|---|---|---:|
| [ger40_london_orb_breakout_raw_long_only_v3.yaml](../../config/experiments/London_NY/raw/ger40_london_orb_breakout_raw_long_only_v3.yaml) | `ger40_london_orb_breakout_raw_long_only_v3` | 30m | GER40 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [ger40_london_orb_breakout_raw_short_only_v3.yaml](../../config/experiments/London_NY/raw/ger40_london_orb_breakout_raw_short_only_v3.yaml) | `ger40_london_orb_breakout_raw_short_only_v3` | 30m | GER40 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [ger40_london_orb_breakout_raw_v3.yaml](../../config/experiments/London_NY/raw/ger40_london_orb_breakout_raw_v3.yaml) | `ger40_london_orb_breakout_raw_v3` | 30m | GER40 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [london_basket_orb_breakout_raw_long_only_v3.yaml](../../config/experiments/London_NY/raw/london_basket_orb_breakout_raw_long_only_v3.yaml) | `london_basket_orb_breakout_raw_long_only_v3` | 30m |  | `none` | `` | `orb_candidate_side` | `` | 17 |
| [london_basket_orb_breakout_raw_short_only_v3.yaml](../../config/experiments/London_NY/raw/london_basket_orb_breakout_raw_short_only_v3.yaml) | `london_basket_orb_breakout_raw_short_only_v3` | 30m |  | `none` | `` | `orb_candidate_side` | `` | 17 |
| [london_basket_orb_breakout_raw_v3.yaml](../../config/experiments/London_NY/raw/london_basket_orb_breakout_raw_v3.yaml) | `london_basket_orb_breakout_raw_v3` | 30m |  | `none` | `` | `orb_candidate_side` | `` | 17 |
| [ny_cash_basket_no_us30_orb_breakout_raw_long_only_v3.yaml](../../config/experiments/London_NY/raw/ny_cash_basket_no_us30_orb_breakout_raw_long_only_v3.yaml) | `ny_cash_basket_no_us30_orb_breakout_raw_long_only_v3` | 30m |  | `none` | `` | `orb_candidate_side` | `` | 17 |
| [ny_cash_basket_no_us30_orb_breakout_raw_short_only_v3.yaml](../../config/experiments/London_NY/raw/ny_cash_basket_no_us30_orb_breakout_raw_short_only_v3.yaml) | `ny_cash_basket_no_us30_orb_breakout_raw_short_only_v3` | 30m |  | `none` | `` | `orb_candidate_side` | `` | 17 |
| [ny_cash_basket_no_us30_orb_breakout_raw_v3.yaml](../../config/experiments/London_NY/raw/ny_cash_basket_no_us30_orb_breakout_raw_v3.yaml) | `ny_cash_basket_no_us30_orb_breakout_raw_v3` | 30m |  | `none` | `` | `orb_candidate_side` | `` | 17 |
| [spx500_ny_cash_orb_breakout_raw_long_only_v3.yaml](../../config/experiments/London_NY/raw/spx500_ny_cash_orb_breakout_raw_long_only_v3.yaml) | `spx500_ny_cash_orb_breakout_raw_long_only_v3` | 30m | SPX500 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [spx500_ny_cash_orb_breakout_raw_short_only_v3.yaml](../../config/experiments/London_NY/raw/spx500_ny_cash_orb_breakout_raw_short_only_v3.yaml) | `spx500_ny_cash_orb_breakout_raw_short_only_v3` | 30m | SPX500 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [spx500_ny_cash_orb_breakout_raw_v3.yaml](../../config/experiments/London_NY/raw/spx500_ny_cash_orb_breakout_raw_v3.yaml) | `spx500_ny_cash_orb_breakout_raw_v3` | 30m | SPX500 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [us100_ny_cash_orb_breakout_raw_long_only_v3.yaml](../../config/experiments/London_NY/raw/us100_ny_cash_orb_breakout_raw_long_only_v3.yaml) | `us100_ny_cash_orb_breakout_raw_long_only_v3` | 30m | US100 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [us100_ny_cash_orb_breakout_raw_short_only_v3.yaml](../../config/experiments/London_NY/raw/us100_ny_cash_orb_breakout_raw_short_only_v3.yaml) | `us100_ny_cash_orb_breakout_raw_short_only_v3` | 30m | US100 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [us100_ny_cash_orb_breakout_raw_v3.yaml](../../config/experiments/London_NY/raw/us100_ny_cash_orb_breakout_raw_v3.yaml) | `us100_ny_cash_orb_breakout_raw_v3` | 30m | US100 | `none` | `` | `orb_candidate_side` | `` | 17 |
| [xauusd_london_orb_breakout_raw_long_only_v3.yaml](../../config/experiments/London_NY/raw/xauusd_london_orb_breakout_raw_long_only_v3.yaml) | `xauusd_london_orb_breakout_raw_long_only_v3` | 30m | XAUUSD | `none` | `` | `orb_candidate_side` | `` | 17 |
| [xauusd_london_orb_breakout_raw_short_only_v3.yaml](../../config/experiments/London_NY/raw/xauusd_london_orb_breakout_raw_short_only_v3.yaml) | `xauusd_london_orb_breakout_raw_short_only_v3` | 30m | XAUUSD | `none` | `` | `orb_candidate_side` | `` | 17 |
| [xauusd_london_orb_breakout_raw_v3.yaml](../../config/experiments/London_NY/raw/xauusd_london_orb_breakout_raw_v3.yaml) | `xauusd_london_orb_breakout_raw_v3` | 30m | XAUUSD | `none` | `` | `orb_candidate_side` | `` | 17 |
| [london_basket_tree_tft_overlay_long_only_v3.yaml](../../config/experiments/London_NY/stack/london_basket_tree_tft_overlay_long_only_v3.yaml) | `london_basket_tree_tft_overlay_long_only_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [london_basket_tree_tft_overlay_short_only_v3.yaml](../../config/experiments/London_NY/stack/london_basket_tree_tft_overlay_short_only_v3.yaml) | `london_basket_tree_tft_overlay_short_only_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [london_basket_tree_tft_overlay_v3.yaml](../../config/experiments/London_NY/stack/london_basket_tree_tft_overlay_v3.yaml) | `london_basket_tree_tft_overlay_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [ny_cash_basket_no_us30_tree_tft_overlay_long_only_v3.yaml](../../config/experiments/London_NY/stack/ny_cash_basket_no_us30_tree_tft_overlay_long_only_v3.yaml) | `ny_cash_basket_no_us30_tree_tft_overlay_long_only_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [ny_cash_basket_no_us30_tree_tft_overlay_short_only_v3.yaml](../../config/experiments/London_NY/stack/ny_cash_basket_no_us30_tree_tft_overlay_short_only_v3.yaml) | `ny_cash_basket_no_us30_tree_tft_overlay_short_only_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [ny_cash_basket_no_us30_tree_tft_overlay_v3.yaml](../../config/experiments/London_NY/stack/ny_cash_basket_no_us30_tree_tft_overlay_v3.yaml) | `ny_cash_basket_no_us30_tree_tft_overlay_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [ger40_london_tree_meta_long_only_v3.yaml](../../config/experiments/London_NY/tree_only/ger40_london_tree_meta_long_only_v3.yaml) | `ger40_london_tree_meta_long_only_v3` | 30m | GER40 | `none` | `` | `meta_probability_side` | `` | 17 |
| [ger40_london_tree_meta_short_only_v3.yaml](../../config/experiments/London_NY/tree_only/ger40_london_tree_meta_short_only_v3.yaml) | `ger40_london_tree_meta_short_only_v3` | 30m | GER40 | `none` | `` | `meta_probability_side` | `` | 17 |
| [ger40_london_tree_meta_v3.yaml](../../config/experiments/London_NY/tree_only/ger40_london_tree_meta_v3.yaml) | `ger40_london_tree_meta_v3` | 30m | GER40 | `none` | `` | `meta_probability_side` | `` | 17 |
| [london_basket_tree_meta_long_only_v3.yaml](../../config/experiments/London_NY/tree_only/london_basket_tree_meta_long_only_v3.yaml) | `london_basket_tree_meta_long_only_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [london_basket_tree_meta_short_only_v3.yaml](../../config/experiments/London_NY/tree_only/london_basket_tree_meta_short_only_v3.yaml) | `london_basket_tree_meta_short_only_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [london_basket_tree_meta_v3.yaml](../../config/experiments/London_NY/tree_only/london_basket_tree_meta_v3.yaml) | `london_basket_tree_meta_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [ny_cash_basket_no_us30_tree_meta_long_only_v3.yaml](../../config/experiments/London_NY/tree_only/ny_cash_basket_no_us30_tree_meta_long_only_v3.yaml) | `ny_cash_basket_no_us30_tree_meta_long_only_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [ny_cash_basket_no_us30_tree_meta_short_only_v3.yaml](../../config/experiments/London_NY/tree_only/ny_cash_basket_no_us30_tree_meta_short_only_v3.yaml) | `ny_cash_basket_no_us30_tree_meta_short_only_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [ny_cash_basket_no_us30_tree_meta_v3.yaml](../../config/experiments/London_NY/tree_only/ny_cash_basket_no_us30_tree_meta_v3.yaml) | `ny_cash_basket_no_us30_tree_meta_v3` | 30m |  | `none` | `` | `meta_probability_side` | `` | 17 |
| [spx500_ny_cash_tree_meta_long_only_v3.yaml](../../config/experiments/London_NY/tree_only/spx500_ny_cash_tree_meta_long_only_v3.yaml) | `spx500_ny_cash_tree_meta_long_only_v3` | 30m | SPX500 | `none` | `` | `meta_probability_side` | `` | 17 |
| [spx500_ny_cash_tree_meta_short_only_v3.yaml](../../config/experiments/London_NY/tree_only/spx500_ny_cash_tree_meta_short_only_v3.yaml) | `spx500_ny_cash_tree_meta_short_only_v3` | 30m | SPX500 | `none` | `` | `meta_probability_side` | `` | 17 |
| [spx500_ny_cash_tree_meta_v3.yaml](../../config/experiments/London_NY/tree_only/spx500_ny_cash_tree_meta_v3.yaml) | `spx500_ny_cash_tree_meta_v3` | 30m | SPX500 | `none` | `` | `meta_probability_side` | `` | 17 |
| [us100_ny_cash_tree_meta_long_only_v3.yaml](../../config/experiments/London_NY/tree_only/us100_ny_cash_tree_meta_long_only_v3.yaml) | `us100_ny_cash_tree_meta_long_only_v3` | 30m | US100 | `none` | `` | `meta_probability_side` | `` | 17 |
| [us100_ny_cash_tree_meta_short_only_v3.yaml](../../config/experiments/London_NY/tree_only/us100_ny_cash_tree_meta_short_only_v3.yaml) | `us100_ny_cash_tree_meta_short_only_v3` | 30m | US100 | `none` | `` | `meta_probability_side` | `` | 17 |
| [us100_ny_cash_tree_meta_v3.yaml](../../config/experiments/London_NY/tree_only/us100_ny_cash_tree_meta_v3.yaml) | `us100_ny_cash_tree_meta_v3` | 30m | US100 | `none` | `` | `meta_probability_side` | `` | 17 |
| [xauusd_london_tree_meta_long_only_v3.yaml](../../config/experiments/London_NY/tree_only/xauusd_london_tree_meta_long_only_v3.yaml) | `xauusd_london_tree_meta_long_only_v3` | 30m | XAUUSD | `none` | `` | `meta_probability_side` | `` | 17 |
| [xauusd_london_tree_meta_short_only_v3.yaml](../../config/experiments/London_NY/tree_only/xauusd_london_tree_meta_short_only_v3.yaml) | `xauusd_london_tree_meta_short_only_v3` | 30m | XAUUSD | `none` | `` | `meta_probability_side` | `` | 17 |
| [xauusd_london_tree_meta_v3.yaml](../../config/experiments/London_NY/tree_only/xauusd_london_tree_meta_v3.yaml) | `xauusd_london_tree_meta_v3` | 30m | XAUUSD | `none` | `` | `meta_probability_side` | `` | 17 |

## Best διαθέσιμο run

Δεν βρέθηκε logged run με `summary.json` για αυτή την οικογένεια. Το doc περιορίζεται στο checked-in config inventory και στην αρχιτεκτονική.

## Όλα τα logged runs αυτής της οικογένειας

Δεν υπάρχουν logged runs για αυτή την οικογένεια.


## Πώς να αναπαραχθεί

Ενδεικτικά, κάθε config μπορεί να τρέξει με τον official runner:

```bash
docker compose run --rm app python -m src.experiments.runner experiments/London_NY/raw/ger40_london_orb_breakout_raw_long_only_v3.yaml
```

Για serious comparison, κράτα σταθερά data snapshot, costs, split semantics, random seeds και config diff. Μην συγκρίνεις run που αλλάζει ταυτόχρονα target, features, model, signal threshold και backtest constraints χωρίς ablation table.
