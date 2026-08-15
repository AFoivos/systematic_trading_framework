# PyBroker ML Walk-Forward Research Backend — Phase 3B

Κατάσταση: **implemented — discovery-stage OOS screening only**

Η Phase 3B ενσωματώνει το `lib-pybroker==1.2.14` ως optional, replaceable
backend για περιορισμένο supervised ML screening. Το framework εξακολουθεί να
ορίζει data, features, targets, models, signals, chronological folds,
purge/embargo, costs, evidence roles και candidate lifecycle.

Οι κρίσιμες ανισότητες είναι:

```text
PyBroker walk-forward screening ≠ canonical validation
PyBroker OOS predictions ≠ untouched final holdout
predictive metric ≠ trading screening metric
```

Τα OOS αποτελέσματα ανήκουν στο `DISCOVERY`, επειδή feature sets, model
parameters και signal thresholds μπορούν να επιλεγούν με βάση αυτά. Selected
candidates σταματούν στο `PENDING_CANONICAL_VALIDATION` και χρειάζονται
framework-owned replay μέσω `canonical_experiment`.

## Dependency και συμβατότητα

Το optional manifest είναι το `requirements.pybroker.txt`. Κλειδώνει:

- Python 3.11 από το project image,
- `lib-pybroker==1.2.14`,
- NumPy 1.26.4,
- pandas 2.2.2,
- scikit-learn 1.5.1,
- Numba 0.67.0.

Τα pins αποτρέπουν transitive broad upgrade του numerical stack. Το project
Docker image εγκαθιστά το manifest μετά από τα core, tsfresh και VectorBT
requirements. Σε ξεχωριστό περιβάλλον:

```bash
python -m pip install -r requirements.pybroker.txt
```

Το `import src.research` δεν εισάγει PyBroker. Η dependency φορτώνεται μόνο
μέσα στο `src.research.backends.pybroker` όταν εκτελεστεί ο
`PyBrokerSearchExecutor`. Missing dependency ή version drift παράγει
actionable optional-dependency error αντί για raw `ModuleNotFoundError` ή
silent fallback.

## Architecture boundary

```text
STF data snapshot / DiscoveryDataAccess
                 │
                 ▼
STF feature registry + STF target registry
                 │
                 ▼
PyBrokerResearchData (portable DataFrame contract)
                 │
                 ▼
STF purged chronological folds
                 │
                 ▼
train-fold preprocessing
                 │
                 ▼
PyBroker ModelTrainer callback + STF model factory
                 │
                 ▼
test-fold predict_proba only
                 │
                 ▼
STF signal mapping + next-open screening diagnostics
                 │
                 ▼
DiscoveryTrial[] → eligibility → ranking → selection
                 │
                 ▼
ResearchCandidate → PENDING_CANONICAL_VALIDATION
```

PyBroker δεν φορτώνει canonical datasets, δεν δημιουργεί indicators/labels,
δεν κατέχει model registry και δεν αποφασίζει portfolio weights. Native model,
`ModelTrainer`, strategy ή result objects δεν περνούν στα portable discovery
contracts και δεν γράφονται στα artifacts.

## Δηλωμένες capabilities

Ο adapter δηλώνει μόνο:

- `ml_walk_forward`,
- `supervised_model_screening`,
- `oos_prediction_screening`,
- `chronological_fold_evaluation`,
- `probability_signal_screening`.

Δεν δηλώνει vectorized rule screening, portfolio optimization, event-driven ή
live execution, reinforcement learning ή canonical validation.

## Αρχικό supported scope

Η πρώτη έκδοση υποστηρίζει σκόπιμα μόνο:

- ένα asset και ένα timezone-aware, monotonic, unique `DatetimeIndex`,
- framework-produced tabular numeric features,
- framework-produced binary classification target `{0, 1}`,
- explicit target family και positive target horizon,
- το υπάρχον `logistic_regression_clf` model factory,
- expanding ή rolling purged chronological folds,
- optional embargo και explicit minimum train rows,
- fold-local `standard`, `robust` ή no scaling,
- deterministic dropping rows με missing required features,
- framework `meta_probability_side` long/flat signal,
- explicit fixed ή Phase 2 search-space probability threshold,
- close-information με earliest execution στο next-bar open,
- one-bar next-open-to-following-open trading screening,
- explicit return-fraction/per-side costs.

Regression, multi-asset/shared-capital learning, shorting, deep sequence models,
RL, online learning, global resampling, calibration, imputation και feature
selection είναι unsupported. Προσθήκη τους απαιτεί νέο, test-covered contract·
δεν υπάρχει optimistic fallback.

## STF-authoritative fold semantics

Ο adapter δεν αφήνει το native PyBroker walk-forward API να επιλέξει folds.
Χρησιμοποιεί το canonical `src.evaluation.time_splits.build_time_splits` με
`method="purged"` και καταγράφει ανά fold:

- `fold_id`,
- train/test positional και timestamp ranges,
- `purge_bars` και `embargo_bars`,
- expanding/rolling mode,
- raw και fitted train-row counts,
- model fit end timestamp,
- OOS coverage και missing predictions,
- model parameters/seed,
- predictive και trading diagnostics.

Το default purge είναι το declared target horizon. Μικρότερο explicit purge
απορρίπτεται. Το canonical forward-label leakage assertion εκτελείται για κάθε
fold. Test folds δεν επιτρέπεται να επικαλύπτονται, επειδή κάθε timestamp πρέπει
να έχει το πολύ μία OOS prediction provenance.

## Fold-safe fit/predict contract

Για κάθε fold η μόνη επιτρεπτή ροή είναι:

```text
TRAIN rows
  → drop missing required features / missing labels
  → enforce minimum rows and at least two target classes
  → fit scaler on TRAIN only
  → fit STF logistic estimator through PyBroker ModelTrainer

TEST rows
  → transform with the TRAIN-fitted scaler
  → predict_proba only on complete TEST feature rows
  → leave all other predictions missing
```

Δεν γίνεται fit σε ολόκληρο το dataset, final refit ή in-sample prediction.
Δεν γίνεται forward/backward fill, train-prediction backfill ή neutral-score
substitution. Rows πριν από το πρώτο test fold μένουν χωρίς prediction και δεν
συμμετέχουν στα screening metrics.

Κάθε αποθηκευμένη prediction αποδεικνύει:

- trial και fold ID,
- prediction timestamp και bar-close information time,
- model fit end timestamp,
- `trained_without_this_row=true`,
- `is_oos=true`,
- earliest next-open execution timestamp ή explicit `null` στο fold end.

## OOS coverage

Κάθε trial καταγράφει:

- `total_rows`,
- `eligible_prediction_rows` (όλες οι test-fold rows),
- `oos_prediction_rows`,
- `missing_oos_rows`,
- `oos_coverage`,
- `non_oos_prediction_rows=0`,
- first/last OOS prediction timestamps.

Predictive και trading screening metrics καταναλώνουν μόνο test-fold output.
Missing feature rows παραμένουν missing predictions και μειώνουν την coverage.
Η Phase 2 eligibility policy αποφασίζει αν η coverage επαρκεί· ο adapter δεν
hardcode-άρει promotion threshold.

## Signal και timing mapping

Η probability μετατρέπεται σε framework signal με το canonical signal registry:

```text
pred_prob >= declared threshold → long intent
pred_prob < declared threshold  → flat intent
missing pred_prob               → no OOS signal
```

Το threshold είναι είτε explicit fixed specification είτε finite Phase 2
search dimension. Δεν υπάρχει implicit `0.5`.

| Έννοια | Phase 3B mapping | Κατάσταση |
|---|---|---|
| features/prediction known at `close[t]` | information timestamp `close[t]` | explicit |
| earliest entry | `open[t+1]` | mandatory |
| screening return | `open[t+1] → open[t+2]` | exact για το δηλωμένο one-bar model |
| same-close fill | καμία valid policy | unsupported |
| signal/return crossing fold boundary | δεν επιτρέπεται | fail-closed |

Η τελευταία prediction ενός fold μπορεί να αποθηκευτεί ως OOS predictive
output, αλλά δεν αποκτά execution return αν λείπει future row μέσα στο ίδιο
fold. Δεν δανείζεται τιμή από άλλο fold.

## Cost mapping

Trading screening απαιτεί non-empty explicit cost assumptions. Υποστηρίζονται:

| STF assumption | Mapping |
|---|---|
| `cost_per_turnover` | return fraction ανά unit position change |
| `commission_bps_per_side` | `bps / 10_000` ανά unit turnover |
| `slippage_per_turnover` | adverse return fraction ανά unit turnover |
| `slippage_bps_per_side` | `bps / 10_000` ανά unit turnover |
| `holding_cost_per_exposed_bar` | return fraction ανά exposed bar |
| `spread_bps_per_side` | scalar approximation μόνο με explicit opt-in |

Ambiguous/unknown keys, duplicate unit declarations και unapproved scalar
spread απορρίπτονται. Τα αποτελέσματα παραμένουν approximate screening, όχι
quote-path canonical execution evidence.

## Metrics και fold stability

Predictive metrics αποθηκεύονται χωριστά από trading metrics.

Predictive classification diagnostics περιλαμβάνουν evaluation-row count,
positive rate, accuracy, Brier score, ROC-AUC και log loss, μόνο όπου target
και OOS probability είναι διαθέσιμα. Trading diagnostics περιλαμβάνουν
gross/net return, conventional Sharpe, drawdown, bar profit factor, trade
count, turnover και total cost.

Ανά fold διατηρούνται και οι δύο ομάδες. Για το configured selection metric
καταγράφονται χωρίς hardcoded gate:

- mean και median fold metric,
- worst fold metric με σωστή maximize/minimize direction,
- positive fold count,
- fold dispersion.

Όλα τα trial metrics και runtime metadata είναι finite/null και
JSON-compatible. Predictive score και tradability δεν συγχέονται.

## Search, errors και determinism

Ο executor καταναλώνει το υπάρχον finite `SearchSpace`. Κάθε dimension πρέπει
να χαρτογραφείται ακριβώς μία φορά σε model parameter ή signal threshold.
Continuous/adaptive tuning ανήκει στον `ExistingOptunaSearchExecutor`.

Το full cardinality, planned/completed/failed/invalid/eligible/selected breadth
διατηρείται από τα Phase 2 records. Trial ID και seed παράγονται deterministic
από research run, frozen parameters και configured seed. Mutable performance
δεν συμμετέχει στην candidate identity.

Single-class ή insufficient-training fold μετατρέπει ολόκληρο το combination
σε `invalid` trial με reason. Convergence/model/non-finite prediction failure
γίνεται `failed` trial. Τα failures δεν εξαφανίζονται από το search archive.
Resource caps ελέγχονται πριν από το optional import και πριν από fit.

## Artifacts

Με νέο artifact root γράφονται create-once:

```text
pybroker_backend.json
pybroker_fold_diagnostics.json
pybroker_oos_predictions.jsonl
pybroker_search_summary.json
```

Τα artifacts περιέχουν backend/framework versions, config/specification hashes,
dataset fingerprint, model/feature/target/signal provenance, fold ranges,
purge/embargo, costs, seeds, OOS coverage, prediction provenance και search
breadth. Δεν γίνεται overwrite και δεν αποθηκεύεται fitted/native object.

## Candidate lifecycle boundary

Τα portable trials περνούν από το υπάρχον Phase 2 eligibility, ranking και
selection. Selected trial δημιουργεί `ResearchCandidate` και
`CanonicalValidationRequest`, αλλά ο adapter δεν μπορεί να δημιουργήσει
canonical validation, robustness, final evidence ή `VALIDATED` status.

| Executor | Χρήση |
|---|---|
| `GridCandidateGenerator` | μικρό deterministic search με injected evaluator |
| `ExistingOptunaSearchExecutor` | adaptive/continuous tuning |
| `VectorBTSearchExecutor` | finite rule-based vectorized screening |
| `PyBrokerSearchExecutor` | finite supervised ML walk-forward OOS screening |
