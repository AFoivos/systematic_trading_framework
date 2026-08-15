# STF-native Multi-Asset & Cross-Sectional Alpha Research — Phase 3C-R2

Κατάσταση: **implemented — discovery-stage prediction research only**

Η Phase 3C-R2 προσθέτει framework-native predictive research πάνω στο canonical
`PanelResearchDataset` της R1. Δεν προσθέτει external research framework,
portfolio optimizer, backtest engine ή νέα evidence authority.

```text
PanelResearchDataset
        ↓
TRAINING + TUNING -- target-horizon purge
        ↓
STF model factory + train-only preprocessing
        ↓
SCREENING OOS predictions
        ↓
per-asset / cross-sectional diagnostics
        ↓
DiscoveryTrial → ranking → ResearchCandidate
        ↓
PENDING_CANONICAL_VALIDATION
```

## Ownership

Το STF παραμένει authoritative για:

- το panel dataset, το `(timestamp, asset_id)` row identity και τα fingerprints,
- τα feature columns και το `feature_set_reference` από `src/features`,
- το target, τον horizon και το specification reference από `src/targets`,
- το LightGBM model kind/factory από `src/models`,
- τα `TRAINING`, `TUNING`, `SCREENING` segments και το `DISCOVERY` role,
- το Phase 2 `SearchSpace`, `DiscoveryTrial`, ranking και candidate lifecycle,
- τη μελλοντική canonical validation μέσω `canonical_experiment`.

Το `MultiAssetSearchExecutor` δεν δημιουργεί δεύτερο model registry, search
language, candidate type ή dataset abstraction.

## Research modes

### Per-asset

Το `per_asset` mode εκπαιδεύει ένα ανεξάρτητο model ανά asset με το δικό του
chronological fit sample και παράγει predictions μόνο για τα eligible observed
rows του ίδιου asset στο `SCREENING` segment. Απαντά στο ερώτημα αν η ίδια
feature/target σχέση είναι προβλέψιμη ξεχωριστά σε κάθε asset.

Αποθηκεύονται ανά asset prediction count, coverage, missing observations, MAE,
RMSE, Pearson και Spearman correlation όπου είναι στατιστικά διαθέσιμα.

### Cross-sectional

Το `cross_sectional` mode εκπαιδεύει ένα pooled tabular model στο επιτρεπόμενο
historical panel και συγκρίνει τα OOS scores μεταξύ assets στο ίδιο timestamp.
Απαντά στο ερώτημα ποια observed assets αναμένεται να έχουν σχετικά υψηλότερο
target στο ίδιο χρονικό σημείο.

Τα δύο modes δηλώνονται ρητά. Δεν γίνεται silent ανάμειξη model-fit ή metric
semantics.

## Αρχικό model scope

Η R2 υποστηρίζει μόνο το υπάρχον `lightgbm_regressor`. Η κατασκευή estimator
παραμένει στο `src.models.forecasting.lightgbm` και το canonical registry name
παραμένει `lightgbm_regressor`.

Δεν προστέθηκε νέο ML dependency. Το model τρέχει με deterministic seed,
`n_jobs=1`, χωρίς shuffle. Τα search dimensions χαρτογραφούνται ρητά σε
LightGBM parameters ή σε προδηλωμένα subsets των ήδη διαθέσιμων STF features.

## Chronological και OOS contract

Το fit sample είναι τα observed rows των `TRAINING` και `TUNING` segments. Πριν
από fit εφαρμόζεται purge με bars τουλάχιστον ίσα με το authoritative
`target_horizon_bars`. Για horizon `h` και πρώτο screening timestamp στη θέση
`s`, επιτρέπονται μόνο training timestamps με θέση μικρότερη από `s - h`.

Το evaluation/prediction sample αποτελείται αποκλειστικά από rows που:

- ανήκουν στο `SCREENING`,
- είναι `prediction_eligible=true`,
- έχουν όλα τα επιλεγμένα features και target,
- βρίσκονται μετά το τέλος του αντίστοιχου model fit.

Δεν παράγονται fitted training predictions, δεν backfillάρονται missing OOS
predictions και δεν κατασκευάζονται rows για asset/timestamp observations που
λείπουν.

Το `SCREENING` είναι discovery-stage OOS screening. Δεν είναι `VALIDATION`,
`PROSPECTIVE_FINAL` ή untouched final holdout, επειδή feature sets, model
parameters και alternatives συγκρίνονται πάνω στα αποτελέσματά του.

## Preprocessing isolation

Υποστηρίζονται μόνο `none`, `standard` και `robust` scaler. Ο scaler γίνεται fit
μόνο στο complete, purged training sample και μετά μετασχηματίζει τα eligible
screening rows. Global scaling απαγορεύεται. Imputation, calibration και feature
selection είναι explicit `unsupported` στην R2. Η initial missing-value policy
είναι deterministic drop· NaN δεν μετατρέπεται σε zero και δεν γίνεται fill.

## Portable prediction record

Κάθε OOS row γίνεται `MultiAssetPredictionRecord` με:

- deterministic `prediction_id`,
- timestamp και `asset_id`,
- research run, trial, segment και model-fit IDs,
- finite prediction και αξιολογήσιμο target,
- `prediction_eligible=true`, `trained_without_this_row=true`, `is_oos=true`,
- model-fit start/end timestamp και target horizon.

Το ID προκύπτει από timestamp, asset, run, trial και model-fit context. Metrics
δεν συμμετέχουν στην identity. Τα records είναι strict JSON-compatible values,
χωρίς fitted estimator ή NumPy/pandas/native backend object.

## Coverage και concentration

Το trial καταγράφει συνολικά total rows, eligible rows, OOS prediction rows,
missing OOS rows και coverage. Ανά asset καταγράφονται eligible/prediction/
missing rows, coverage, share των predictions, observed/possible screening rows
και missing observations. Έτσι ένα συνολικό metric δεν μπορεί να κρύψει ότι
λίγα assets κυριαρχούν στο sample. Δεν hardcodeάρεται rejection threshold
συγκέντρωσης.

## Rank IC

Για κάθε timestamp με τουλάχιστον τον explicit
`minimum_assets_per_timestamp`, το rank IC ορίζεται ως:

```text
Pearson correlation(
  average_rank(prediction across observed assets),
  average_rank(realized target across observed assets)
)
```

Αυτό είναι Spearman rank correlation με deterministic average-rank tie
handling. Timestamp με ανεπαρκή assets ή constant prediction/target ranks έχει
`status=not_run`, reason και null metric. Δεν κατασκευάζεται score.

Αποθηκεύονται mean/median rank IC, dispersion, positive-period count,
valid-period count και unavailable-period count. Το rank IC είναι discovery
prediction diagnostic, όχι canonical alpha evidence.

## Top/bottom quantile diagnostic

Προαιρετικά, τα assets ταξινομούνται deterministic κατά prediction και
`asset_id`. Υπολογίζονται το mean realized target του top quantile, το mean του
bottom quantile και το top-minus-bottom target spread.

Το spread δεν πολλαπλασιάζεται με capital, δεν είναι portfolio return, δεν έχει
shared-capital accounting και δεν δημιουργεί weights ή rebalancing. Η Phase 4
θα είναι ο μόνος owner portfolio construction semantics.

## Temporal stability

Τα screening timestamps χωρίζονται σε deterministic συνεχόμενα subperiods.
Ανά subperiod αποθηκεύονται range, prediction rows και το κατάλληλο predictive
metric. Το trial διατηρεί mean, median, worst, dispersion και positive
subperiod count. Δεν υπάρχει hardcoded financial pass/fail threshold.

## Search breadth και operational guards

Η R2 καταναλώνει μόνο finite Phase 2 `SearchSpace`. Adaptive search παραμένει
Optuna-owned. Πριν από οποιοδήποτε fit ελέγχονται rows, assets, planned trials,
`trials × fits_per_trial` και `trials × eligible_prediction_rows`.

Στο `per_asset`, `fits_per_trial = asset_count`. Στο `cross_sectional`, είναι
ένα pooled fit ανά trial. Υπέρβαση cap αποτυγχάνει πριν από training. Model
failures/invalid samples παραμένουν auditable `FAILED`/`INVALID`
`DiscoveryTrial` values και δεν εξαφανίζονται από το search breadth.

## Candidate και artifact boundary

Κάθε alternative επιστρέφει το canonical `DiscoveryTrial`. Το υπάρχον Phase 2
service εφαρμόζει eligibility, ranking, deterministic candidate identity και
γράφει create-once JSON/JSONL artifacts. Τα bounded portable prediction records
αποθηκεύονται στο runtime metadata του trial και συνεπώς στο υπάρχον
`trials.jsonl`. Δεν αποθηκεύονται pickled models.

Ένας selected candidate σταματά πάντα στο
`PENDING_CANONICAL_VALIDATION` και παράγει portable
`CanonicalValidationRequest` για το STF-owned `canonical_experiment`. Η R2 δεν
δημιουργεί validation, robustness ή final-evidence record.

## Ρητά non-goals

Η R2 δεν περιλαμβάνει Qlib, MLflow, skfolio, portfolio optimization,
covariance/weight/capital allocation, trading signal/backtest, real-market
discovery scan, AR-0001 execution/mutation ή live/paper/demo execution.

Το output είναι αρκετά portable για μελλοντική Phase 4 κατανάλωση: candidate/
run identity, timestamp, asset, prediction, coverage, model/feature/target
specification και immutable dataset provenance. Η Phase 4 πρέπει ακόμη να
ορίσει δικά της portfolio contracts, constraints, chronology και validation.
