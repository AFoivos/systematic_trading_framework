# STF-native Multi-Asset Research Dataset — Phase 3C-R1

Κατάσταση: **implemented — portable data-contract infrastructure only**

Η Phase 3C-R1 εισάγει framework-owned contracts για research tables με
περισσότερα από ένα assets. Δεν εισάγει research engine, model training,
candidate ranking, portfolio construction ή εξωτερικό dataset framework.

Η επιθυμητή διαδρομή είναι:

~~~
STF research snapshot
        ↓
validated PanelResearchDataset
        ↓
(timestamp, asset_id)
        ↓
STF features + STF target
        ↓
TRAINING / TUNING / SCREENING
        ↓
prediction eligibility
        ↓
canonical input to Phase 3C-R2
~~~

## Ownership και όρια

Το STF παραμένει authoritative για:

- market data και immutable research snapshots,
- asset identifiers,
- feature και target registries,
- target horizon,
- dataset fingerprint και source provenance,
- evidence roles,
- chronological segments,
- candidate lifecycle και canonical validation.

Το 'PanelResearchDataset' είναι backend-neutral metadata. Δεν περιέχει pandas
DataFrame, fitted model, backend-native object ή callable. Ο supplied πίνακας
χρησιμοποιείται μόνο από το 'validate_research_dataset' και δεν αποθηκεύεται
στο metadata contract.

Η R1 δεν εγκαθιστά ούτε εισάγει Qlib, MLflow, DuckDB, skfolio, VectorBT ή
PyBroker. Τα δύο υπάρχοντα screening backends δεν εκτελούνται από τον dataset
validator.

## Canonical row identity

Η authoritative long-form ταυτότητα γραμμής είναι ακριβώς:

~~~
(timestamp, asset_id)
~~~

Ο validator απαιτεί:

- timezone-aware pandas datetime column με όνομα 'timestamp',
- framework identifier column με όνομα 'asset_id',
- μοναδικό '(timestamp, asset_id)',
- deterministic row order πρώτα κατά 'timestamp' και μετά κατά 'asset_id',
- exact αντιστοίχιση του observed universe με το δηλωμένο 'asset_ids'.

Pivoted wide matrices μπορούν να παραχθούν αργότερα ως derived views, αλλά δεν
είναι το R1 canonical representation.

## Asset universe

Το 'asset_ids' είναι explicit και canonicalized σε λεξικογραφική σειρά. Τα
identifiers πρέπει να ακολουθούν το υπάρχον framework identifier vocabulary,
π.χ. 'EURUSD', 'US100', 'XAUUSD'. Backend-specific aliases δεν επιτρέπονται.

Ο validator απορρίπτει:

- κενό ή missing asset ID,
- malformed identifier,
- observed asset που δεν υπάρχει στο declared universe,
- declared asset που δεν εμφανίζεται στον supplied πίνακα.

## Timezone

Το metadata καταγράφει explicit IANA timezone, π.χ. 'UTC'. Η timestamp column
πρέπει να έχει ακριβώς την ίδια timezone metadata. Δεν γίνεται:

- implicit localization,
- μετατροπή στη system timezone,
- αφαίρεση timezone,
- locale-dependent parsing.

Τα sample και segment boundaries είναι timezone-aware ISO-8601 timestamps. Το
metadata sample start/end πρέπει να αντιστοιχεί στο πρώτο/τελευταίο observed
timestamp.

## Features

Τα features παραμένουν outputs του 'src/features'. Το contract καταγράφει:

- ordered 'feature_names',
- 'feature_set_reference',
- optional JSON-compatible transformation provenance.

Ο validator απαιτεί τα declared feature columns και απορρίπτει undeclared
columns. Δεν υπολογίζει indicators και δεν αποδέχεται backend-specific feature
universe.

Feature NaN επιτρέπεται μόνο ως explicit missing/warmup state. Δεν γίνεται
forward fill, backfill, zero fill ή mean imputation. Γραμμή με missing feature
δεν μπορεί να είναι prediction-eligible.

## Target και horizon

Το target παραμένει output του 'src/targets'. Το metadata καταγράφει:

- 'target_name',
- 'target_column',
- 'target_specification_reference',
- positive 'target_horizon_bars'.

Ο horizon δηλώνεται explicit και δεν προκύπτει με parsing του column name. Η R1
δεν εφαρμόζει purge/embargo ή split execution· παρέχει όμως το horizon που θα
χρειαστεί η authoritative STF split policy στην R2.

Missing target παραμένει missing. Η αντίστοιχη γραμμή πρέπει να είναι
prediction-ineligible και να φέρει explicit reason.

## Evidence role και chronological segments

Το dataset επαναχρησιμοποιεί το canonical
'src.src_data.research_roles.EvidenceRole'. Δεν υπάρχει δεύτερο evidence enum.

Η R1 ορίζει τρία workflow purposes:

| Segment purpose | Semantics | Evidence role |
|---|---|---|
| 'TRAINING' | discovery model fit sample | 'DISCOVERY' |
| 'TUNING' | discovery model/parameter selection sample | 'DISCOVERY' |
| 'SCREENING' | discovery-stage OOS screening sample | 'DISCOVERY' |

Τα purposes δεν είναι evidence roles. Το όνομα 'test', 'screening' ή παρόμοιο
δεν μπορεί να δημιουργήσει 'VALIDATION' ή 'PROSPECTIVE_FINAL' evidence.

Για fail-closed separation:

- ένα 'DISCOVERY' panel dataset απαιτεί και τα τρία purposes,
- τα segment IDs είναι μοναδικά,
- οι ranges είναι timezone-aware και reconstructible,
- reversed, empty, overlapping ή out-of-sample ranges απορρίπτονται,
- 'TRAINING/TUNING/SCREENING' segments απαγορεύονται σε dataset με
  'VALIDATION', 'HISTORICAL_PSEUDO_OOS' ή 'PROSPECTIVE_FINAL' role.

Υποστηρίζονται explicit closed και left-closed/right-open boundaries.

## Prediction eligibility

Η R1 δεν παράγει predictions. Περιγράφει μόνο την eligibility κάθε observed
row μέσω:

~~~
prediction_eligible
prediction_ineligibility_reason
~~~

Prediction-eligible row:

- πρέπει να ανήκει σε 'SCREENING' segment,
- πρέπει να έχει όλα τα required features,
- πρέπει να έχει target,
- δεν πρέπει να φέρει ineligibility reason.

Prediction-ineligible row πρέπει να έχει explicit reason από το portable
vocabulary:

- 'feature_warmup',
- 'missing_target',
- 'outside_screening_segment',
- 'insufficient_historical_context',
- 'explicit_exclusion'.

Η eligibility δεν είναι prediction mask και δεν αποδεικνύει OOS model
provenance. Αυτό ανήκει στην R2.

## Missing observations

Τα assets μπορεί να έχουν διαφορετικά calendars. Ο validator δεν απαιτεί
Cartesian densification και δεν δημιουργεί synthetic rows. Αν ένα asset λείπει
σε συγκεκριμένο timestamp, η απουσία παραμένει απουσία.

Το 'ResearchDatasetValidationReport' καταγράφει:

- observed rows,
- distinct timestamps,
- asset count,
- possible '(timestamp, asset_id)' pairs,
- missing-observation count,
- eligible/ineligible row counts.

Το missing-observation count είναι coverage diagnostic, όχι εντολή για fill.

## Fingerprinting και provenance

Το 'compute_research_dataset_fingerprint' επαναχρησιμοποιεί το υπάρχον
'compute_dataframe_fingerprint' αφού επιβάλει canonical long-form ordering.
Το metadata απαιτεί lowercase SHA-256 και ο validator επαληθεύει τον supplied
πίνακα έναντι του hash και του row count, όταν υπάρχει.

Το 'source_snapshot_fingerprints' συνδέει κάθε source snapshot reference με
immutable SHA-256. Μαζί με:

- asset universe,
- sample boundaries,
- feature-set reference,
- target reference και horizon,
- transformation metadata,

παρέχει τη lineage που χρειάζεται η μελλοντική R2 χωρίς να δημιουργεί δεύτερο
snapshot ή fingerprint authority.

## Portable serialization

Τα metadata contracts παρέχουν strict 'to_dict' / 'from_dict' και
χρησιμοποιούν το υπάρχον deterministic JSON serializer. Περιέχουν μόνο
JSON-compatible finite metadata:

- strings,
- integers/booleans,
- lists,
- mappings,
- explicit enum values.

Unknown/missing keys, pandas objects, NumPy arrays και backend-native objects
δεν γίνονται silently coerced.

## Persistence και Parquet

Η R1 δεν προσθέτει writer, database ή νέο artifact root. Επομένως δεν αλλάζει
την υπάρχουσα create-once storage συμπεριφορά.

Η long-form schema είναι συμβατή με μελλοντικό Parquet artifact
'metadata.json + data.parquet', αλλά persistence θα προστεθεί μόνο αν υπάρξει
ρητή ανάγκη και με reuse του υπάρχοντος immutable artifact/storage boundary.
Δεν προστέθηκαν DuckDB ή MLflow.

## Delivered consumer: Phase 3C-R2

Η R2 καταναλώνει το validated contract για:

- framework-owned multi-asset prediction execution,
- STF-authoritative chronological folds, purge και embargo,
- fold-safe model preprocessing,
- per-asset και cross-sectional predictive diagnostics,
- portable prediction records,
- μετατροπή σε υπάρχον 'DiscoveryTrial'.

Η R2 δεν πρέπει να θεωρήσει το 'SCREENING' segment canonical validation ή
untouched final holdout. Candidate selection θα παραμένει discovery evidence
και θα σταματά στο 'PENDING_CANONICAL_VALIDATION'.

Η υλοποίηση βρίσκεται στο `src/research/multi_asset.py` και τεκμηριώνεται στο
[STF-native Multi-Asset Alpha Research](multi_asset_alpha_research.md). Η R1
παραμένει το μοναδικό canonical dataset contract· η R2 δεν το αντιγράφει.
