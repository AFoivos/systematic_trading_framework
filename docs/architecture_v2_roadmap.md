# Architecture V2 Roadmap

Το roadmap είναι incremental. Κάθε phase πρέπει να παραδίδει independently
testable contracts και compatibility, χωρίς να ενεργοποιεί το επόμενο phase
σιωπηλά. Οι external dependencies προστίθενται μόνο στη phase που τις χρειάζεται
και μετά από explicit έγκριση.

## Cross-phase invariants

Ισχύουν σε όλες τις phases:

- Το υπάρχον repository, YAML schema και canonical runner παραμένουν owners.
- Δεν επιτρέπεται lookahead, leakage, train/test contamination ή relabeling
  inspected history ως final evidence.
- External backends επιστρέφουν framework-owned portable records.
- Canonical validation επανατρέχει candidates με framework data, timing, costs,
  OOS και robustness rules.
- Backtest, paper, demo και live είναι διαφορετικά modes με fail-closed
  transitions.
- Κάθε migration έχει import/config/artifact inventory, facade και parity tests.
- Δεν γίνεται mass move για αισθητικούς λόγους.

## PHASE 0 — Architecture foundation

Κατάσταση: **implemented in this foundation change**

### Στόχος

Να οριστούν Architecture V2 boundaries, neutral research contracts, adapter
policy, evidence mapping, compatibility rules και tests χωρίς external trading
dependencies ή behavioral αλλαγές.

### Expected modules/deliverables

- `src/research/contracts.py`
- `src/research/candidate.py`
- `src/research/backends/base.py`
- `docs/ARCHITECTURE_V2.md`
- `docs/architecture_v2_roadmap.md`
- `docs/adr/0001` έως `0005`
- expanded root `AGENTS.md`
- `tests/test_architecture_v2.py`

### Dependencies

- Python standard library.
- Existing `src.src_data.research_roles.EvidenceRole`.
- Existing registry/canonical-pipeline contracts.
- Καμία VectorBT, PyBroker, Qlib, skfolio ή NautilusTrader dependency.

### Migration risks

- Δημιουργία duplicate evidence/hypothesis concepts.
- Υπερβολικά generic contracts που επιτρέπουν backend objects.
- Architecture tests που παγώνουν incidental file layout.
- Accidentally changing canonical pipeline/config behavior.

### Exit criteria

- Το `canonical_experiment` παραμένει ίδιο public pipeline.
- Research foundation εισάγεται χωρίς optional libraries.
- Candidate/request/result είναι backend-neutral και serializable.
- `development`, `validation`, `final_holdout` συνδέονται με τα υπάρχοντα
  immutable evidence roles.
- Documentation, ADRs και architecture tests υπάρχουν.
- Targeted registry και V2 tests περνούν σε authoritative environment.

## PHASE 1 — Research layer + evidence model

Κατάσταση: **complete — Phase 1/architecture criteria passed**

### Στόχος

Να μετατραπούν τα σημερινά research/evidence pieces σε συνεκτικό public
research layer χωρίς να μετακινηθεί ή να ξαναγραφτεί όλο το
`src/experiments/support`.

### Delivered modules

```text
src/research/
  hypothesis.py
  run.py
  selection.py
  evidence.py
  robustness.py
  decisions.py
  lifecycle.py
  serialization.py
  storage/
    base.py
    filesystem.py
```

Compatibility facades μπορεί να παραμείνουν στα:

- `src/experiments/alpha_contracts.py`
- `src/experiments/alpha_registry.py`
- `src/src_data/research_*`

### Dependencies

- Existing snapshot/access/role contracts.
- Existing evaluation splits, diagnostics και robustness functions.
- Existing run metadata/config hashing.
- Δεν απαιτεί external research backend.

### Work items

1. Inventory όλων των modules του `src/experiments/support` με target owner,
   priority και compatibility risk.
2. Canonical portable hypothesis, run/search, candidate/selection, evidence,
   validation, robustness και promotion-decision records.
3. Deterministic strict JSON serialization και schema-versioned immutable
   filesystem records κάτω από caller-provided artifact root.
4. Explicit evidence-completeness policy και material-change/final-holdout
   refusal.
5. Guarded candidate transitions και first-class rejection history.
6. Compatibility imports και focused round-trip/invalid-state tests.

### Migration risks

- Breaking append-only hypothesis records ή snapshot manifests.
- Confusing validation with prospective final evidence.
- Moving algorithms μαζί με orchestration I/O.
- Changing artifact layout/hashes without versioning.

### Exit criteria

- Ένας candidate συνδέεται με hypothesis, frozen data roles, costs, code/config
  fingerprint και evidence records.
- Validation/final evidence δεν μπορεί να καταναλωθεί από discovery API.
- Existing alpha-discovery flow συνεχίζει να λειτουργεί μέσω facade.
- Serializers reject NaN, unknown schema versions και backend-native objects.
- Lifecycle/role/parity tests περνούν.

### Exit verification

- Το required architecture/research/evidence/causality baseline είναι
  **73 passed, 0 failed**.
- Το AR-0001 είναι intentionally `APPROVED_TO_RUN`, με approval δεμένο στο
  frozen specification hash. Το status και τα approval/data-access gates
  παραμένουν canonical και δεν αλλάζουν στη Phase 2.

## PHASE 2 — Alpha discovery / candidate lifecycle

Κατάσταση: **complete — framework-owned discovery lifecycle implemented**

### Στόχος

Να υπάρχει end-to-end framework-owned lifecycle από preregistered hypothesis
μέχρι candidate selection και canonical validation request, ανεξάρτητα από το
ποιος backend έκανε screening.

### Delivered modules

```text
src/research/discovery/
  __init__.py
  contracts.py
  search_space.py
  service.py
  validation.py
  artifacts.py

src/experiments/
  optuna_discovery.py
```

Τα ranking/selection/validation boundaries έμειναν στο μικρό discovery package
αντί να δημιουργηθούν άδεια nested packages. Το Phase 1 candidate lifecycle,
evidence records και filesystem store παραμένουν οι authoritative owners.

### Dependencies

- Phase 1 lifecycle/evidence contracts.
- Domain registries και canonical pipeline.
- Evaluation/robustness/cost diagnostics.
- Existing immutable artifact/run metadata.

### Delivered work

- Compositional `DiscoverySpecification` με canonical config hashing,
  DISCOVERY-only evidence role, dataset fingerprint, costs και seed.
- Library-independent categorical/integer/float/log/fixed search spaces.
- Portable completed/failed/pruned/invalid trials και explicit search breadth.
- Configuration-driven eligibility, deterministic ranking/tie-breaks και top-k
  selection πριν από Phase 1 candidate conversion.
- Deterministic candidate identity από frozen specification + parameters,
  independent από mutable metrics, με intentional-rerun metadata.
- Thin `ExistingOptunaSearchExecutor` που επαναχρησιμοποιεί
  `src.experiments.optuna_search.optimize_experiment` και μεταφράζει όλα τα
  study states χωρίς Optuna objects στα research contracts.
- Canonical-validation request builder που παγώνει candidates σε
  `PENDING_CANONICAL_VALIDATION` και απαιτεί `VALIDATION` role χωρίς να δίνει
  validation/final data στο discovery service.
- Reuse των Phase 1 robustness/evidence/promotion gates και του immutable
  `FilesystemResearchStore`.
- Create-once JSON/JSONL/Markdown discovery artifacts κάτω από caller-provided
  run root.
- Portable observed parameter-neighborhood stability representation.
- Ελληνική τεκμηρίωση στο `docs/alpha_discovery.md`.

### Migration risks

- Ranking by a single metric ή selection-period Sharpe.
- Tuning πάνω σε validation/final data μέσω automatic loops.
- Treating backend cost semantics as canonical.
- Candidate identity instability μετά από harmless serialization changes.

### Exit criteria

- [x] Candidate selection είναι deterministic και audit-ready.
- [x] Κάθε selected candidate έχει explicit cost/sample/search provenance.
- [x] Failed/pruned/invalid trials παραμένουν στο audit trail και search breadth.
- [x] Canonical validation request ανακατασκευάζει config/parameters χωρίς
  backend runtime objects και απαιτεί role-bound `VALIDATION` evidence.
- [x] Discovery winner σταματά σε `PENDING_CANONICAL_VALIDATION`.
- [x] Promotion παραμένει evidence-gated από τα Phase 1 contracts/store.
- [x] Final holdout δεν είναι διαθέσιμο ως discovery/tuning source.
- [x] Ένα end-to-end synthetic lifecycle ολοκληρώνεται χωρίς external trading
  library και χωρίς backend-native objects.
- [x] Existing Optuna support επαναχρησιμοποιείται αντί να δημιουργηθεί
  δεύτερος optimizer.
- [x] Δεν άλλαξε YAML schema, stable runner ή strategy/runtime behavior.

### Exit verification

- New Phase 2 discovery + Optuna adapter tests: **13 passed**.
- Phase 0/1 research, Architecture V2/registries και Phase 2 focused scope:
  **45 passed**.
- Phase 1 required baseline μαζί με τα νέα Phase 2 tests: **86 passed,
  0 failed**.

## PHASE 3A — VectorBT backend

Κατάσταση: **complete — optional finite-grid screening adapter implemented**

### Στόχος

Fast vectorized screening και parameter search για rule-based hypotheses, χωρίς
να γίνει το VectorBT final validation engine.

### Delivered modules

```text
src/research/backends/vectorbt/
  adapter.py
  contracts.py
  optional_dependency.py
  __init__.py
```

Το orchestration-side `src/experiments/discovery_executors.py` επιλέγει
explicit `GridCandidateGenerator`, `ExistingOptunaSearchExecutor` ή
`VectorBTSearchExecutor` χωρίς silent fallback. Η πλήρης operational σύμβαση
τεκμηριώνεται στο [VectorBT Research Backend](vectorbt_backend.md).

### Dependencies

- Phase 2 candidate lifecycle.
- Explicit, approved, pinned VectorBT dependency.
- Framework data/signal/position-intent contracts.

### Adapter contract

- Input: Phase 2 `DiscoverySpecification`, frozen `DISCOVERY` reference,
  validated single-asset market data και framework-owned signal builder.
- Output: deterministic portable `DiscoveryTrial` values, τα οποία περνούν από
  το υπάρχον selection service και σταματούν στο
  `PENDING_CANONICAL_VALIDATION`.
- Capabilities: `vectorized_screening`, `parameter_grid_search`,
  `rule_based_strategy_screening`.
- Backend portfolio/trades παραμένουν adapter-internal ή versioned artifacts.

### Migration risks

- Signal/fill alignment mismatch και same-bar lookahead.
- Different fee, cash, leverage, shorting ή missing-data semantics.
- Parameter-grid multiple-testing inflation.
- Treating vectorized approximations as event-realistic execution.

### Exit criteria

- [x] Missing dependency produces clear capability error only when selected.
- [x] Deterministic fixtures reconcile signals/positions/costs with documented
  tolerances.
- [x] Candidate records contain backend/version/parameter-grid provenance.
- [x] Adapter cannot promote candidates; it emits only a canonical-validation
  request through the existing lifecycle.
- [x] Core imports/tests pass without eager VectorBT import.
- [x] Finite search breadth, stable trial IDs, batching and pre-allocation
  resource guards have synthetic contract coverage.
- [x] Same-close fills, unsupported sizing/direction/multi-asset semantics και
  ambiguous costs fail closed.

### Exit verification

- New VectorBT contract/parity/resource tests: **15 passed**.
- Architecture V2 + VectorBT focused scope: **27 passed**.
- Phase 0–2 required baseline μαζί με Phase 3A: **102 passed, 0 failed**
  (**86** προηγούμενο baseline + **16** Phase 3A checks).
- Το repository-wide suite επιχειρήθηκε, αλλά σταμάτησε στην collection με
  **9 unrelated errors** από προϋπάρχουσες missing dashboard dependencies και
  already-deleted scripts· δεν έγινε unrelated repair.

## PHASE 3B — PyBroker backend

Κατάσταση: **complete — optional supervised ML OOS screening adapter implemented**

### Στόχος

Fast ML walk-forward screening με fold-safe fit/predict lifecycle και portable
candidate output.

### Delivered modules

```text
src/research/backends/pybroker/
  adapter.py
  contracts.py
  diagnostics.py
  optional_dependency.py
  __init__.py
```

Το orchestration-side `src/experiments/discovery_executors.py` επιλέγει
explicit `PyBrokerSearchExecutor` πίσω από το ίδιο Phase 2 abstraction, χωρίς
silent fallback. Η operational σύμβαση τεκμηριώνεται στο
[PyBroker ML Walk-Forward Research Backend](pybroker_backend.md).

### Dependencies

- Phase 2 candidate lifecycle.
- Explicit, approved, pinned PyBroker dependency.
- Existing model/target/split contracts.

### Adapter contract

- Capabilities: `ml_walk_forward`, `supervised_model_screening`,
  `oos_prediction_screening`, `chronological_fold_evaluation` και
  `probability_signal_screening`.
- Preprocessors/thresholds/models fit μόνο σε train folds.
- Predictions φέρουν OOS mask, fold id και coverage.
- PyBroker objects δεν εμφανίζονται στο domain/candidate API.
- STF folds, target horizon, purge και embargo είναι authoritative· το native
  PyBroker fold policy δεν αλλάζει τα boundaries.
- Initial scope: single asset, binary classification, existing logistic model,
  long/flat threshold signal και mandatory next-open timing.

### Migration risks

- PyBroker split callbacks που δεν εφαρμόζουν purge/embargo/horizon semantics.
- In-sample fitted preprocessing ή threshold tuning.
- Different order/fill/cost lifecycle από canonical engine.
- Missing predictions hidden by aggregate metrics.

### Exit criteria

- [x] Synthetic leakage tests prove train-only fitting.
- [x] OOS coverage/fold chronology and missing predictions are explicit.
- [x] Same-close execution, undersized purge, ambiguous costs και unsupported
  preprocessing semantics fail closed.
- [x] Failed/single-class/insufficient folds remain auditable trials.
- [x] Portable candidate and `CanonicalValidationRequest` use the existing
  lifecycle and stop at `PENDING_CANONICAL_VALIDATION`.
- [x] Framework works unchanged without eager PyBroker import.
- [x] Native PyBroker objects do not appear in portable contracts/artifacts.

### Exit verification

- New PyBroker contract/OOS/leakage/parity tests: **15 passed**.
- Architecture V2 + PyBroker focused scope: **28 passed**.
- Phase 0–3A required baseline μαζί με Phase 3B: **118 passed, 0 failed**
  (**102** προηγούμενο baseline + **16** Phase 3B checks).
- Το repository-wide suite επιχειρήθηκε και σταμάτησε στην collection με
  **8 unrelated errors**: missing optional dashboard `fastapi` και επτά
  references σε ήδη-απόντα script modules. Δεν έγινε unrelated repair.

## PHASE 3C-R1 — STF-native multi-asset research dataset contracts

Κατάσταση: **complete — dependency-free data-contract infrastructure**

### Απόφαση

Το Qlib παραμένει **reference-only / runtime blocked** στο canonical Linux
aarch64 environment. Η R1 δεν εγκαθιστά Qlib, δεν κάνει source build, δεν
δημιουργεί amd64 image και δεν αντιγράφει Qlib-native classes.

Το χρήσιμο dataset boundary υλοποιείται ως μικρό STF-owned contract:

```text
STF snapshot
  -> PanelResearchDataset
  -> canonical (timestamp, asset_id) rows
  -> STF features + STF target
  -> TRAINING / TUNING / SCREENING
  -> explicit prediction eligibility
```

### Delivered module

```text
src/research/dataset.py
```

Η αναλυτική σύμβαση βρίσκεται στο
[STF-native Multi-Asset Research Dataset](multi_asset_research_dataset.md).

### Reused ownership

- Existing `EvidenceRole`, χωρίς δεύτερο evidence enum.
- Existing deterministic JSON και strict portable-contract validation.
- Existing `compute_dataframe_fingerprint` και immutable snapshot SHA-256
  provenance.
- Existing `src/features` και `src/targets` references, χωρίς δεύτερα
  registries.

### Delivered contract

- Canonical unique/sorted long-form `(timestamp, asset_id)` identity.
- Explicit asset universe, IANA timezone και sample boundaries.
- Feature-set και target-specification references με positive target horizon.
- Reconstructible, non-overlapping `TRAINING`, `TUNING`, `SCREENING` segments.
- Fail-closed invariant ότι όλα τα workflow segments είναι `DISCOVERY` only.
- Row eligibility και explicit ineligibility reasons χωρίς prediction
  generation.
- Missing-observation coverage χωρίς Cartesian fill.
- Warmup/target missing values preserved χωρίς imputation.
- Deterministic portable metadata round-trip και table fingerprint validation.

### Exit criteria

- [x] Κανένα external backend/native type στο contract.
- [x] Κανένα model, signal, candidate ranking ή portfolio execution.
- [x] Κανένα Qlib, MLflow, DuckDB ή νέο dependency.
- [x] Κανένα νέο database/artifact root.
- [x] Synthetic multi-asset contract/causality tests.
- [x] Phase 0–3B required regression παραμένει πράσινο.

## PHASE 3C-R2 — STF-native multi-asset/cross-sectional prediction research

Κατάσταση: **complete — discovery-stage prediction research only**

Η R2 επαναχρησιμοποιεί το canonical R1 `PanelResearchDataset` και προσθέτει:

- explicit `per_asset` και `cross_sectional` modes,
- existing `lightgbm_regressor` model ownership/factory,
- `TRAINING+TUNING` fit και `SCREENING` OOS prediction semantics,
- authoritative target-horizon purge και train-only scaler fit,
- strict portable `MultiAssetPredictionRecord`,
- overall/per-asset coverage, predictive metrics και concentration diagnostics,
- per-timestamp average-tie Spearman rank IC με explicit minimum asset count,
- optional top/bottom realized-target spread χωρίς portfolio interpretation,
- deterministic temporal stability subperiods,
- finite Phase 2 search mapping και pre-fit model/prediction resource caps,
- canonical `DiscoveryTrial` → ranking → `ResearchCandidate` lifecycle.

Η αναλυτική σύμβαση βρίσκεται στο
[STF-native Multi-Asset Alpha Research](multi_asset_alpha_research.md).

### Exit criteria

- [x] Κανένα δεύτερο dataset/search/trial/candidate/model registry.
- [x] Κάθε screening prediction είναι OOS με model-fit provenance.
- [x] Preprocessing fit μόνο στο purged training sample.
- [x] Missing observations δεν densify/fillάρονται.
- [x] Rank IC/quantile spread παραμένουν prediction diagnostics.
- [x] Candidate status το πολύ `PENDING_CANONICAL_VALIDATION`.
- [x] Κανένα Qlib, MLflow, skfolio ή νέο dependency.
- [x] Κανένα real-market research ή AR-0001 execution.

### Επόμενα optional βήματα μέσα στη Phase 3C

- **R3 optional:** framework-owned experiment recorder/index πάνω στα υπάρχοντα
  immutable artifacts, μόνο αν υπάρξει συγκεκριμένη operational ανάγκη.
- **R4 Qlib proof-of-concept optional/reference-only:** μόνο μετά από νέο
  compatibility review· κανένα runtime integration είναι προαπαιτούμενο για
  Phase 4.

Με ολοκληρωμένα R1/R2, η Phase 4 είναι αρχιτεκτονικά unblocked. Αυτό δεν σημαίνει
ότι τα discovery predictions είναι portfolio weights ή canonical validation.

## PHASE 4 — skfolio portfolio backend

### Στόχος

Να προστεθεί optional portfolio optimization πίσω από framework-owned portfolio
contract, με σαφή διάκριση alpha score από final portfolio weight.

### Expected modules

```text
src/portfolio/adapters/
  base.py
  skfolio/
    adapter.py
    conversion.py
    optional_dependency.py
```

### Dependencies

- Stable portfolio input/output contract.
- Existing `PortfolioConstraints`, construction και covariance contracts.
- Explicit, approved, pinned skfolio dependency.

### Work items

- Define expected returns/risk/constraint inputs with units and timestamps.
- Map skfolio solution to framework weights.
- Reapply/verify feasibility: bounds, gross/net, group caps, turnover.
- Record objective, solver status, fallback και training window.

### Migration risks

- Infeasible/unstable optimization hidden by silent fallback.
- Lookahead covariance/expected-return estimates.
- Solver/version nondeterminism.
- Double application ή inconsistent interpretation constraints/costs.

### Exit criteria

- Alpha/signal layers never output skfolio objects.
- All returned weights pass framework feasibility checks.
- Chronological estimation και deterministic fallback are tested.
- Existing portfolio backend remains default.
- Core/framework tests pass without skfolio installed.

## PHASE 5 — NautilusTrader event-driven backend

### Στόχος

Event-driven simulation και, αργότερα, execution translation χωρίς να
αντικατασταθούν τα domain contracts ή το canonical bar-validation path.

### Expected modules

```text
src/backtesting/adapters/nautilus/
  simulation.py
  conversion.py
src/execution/adapters/nautilus/
  execution.py
  lifecycle.py
```

Μπορεί να υλοποιηθεί μόνο simulation adapter πρώτα. Execution adapter απαιτεί
ξεχωριστό safety review.

### Dependencies

- Framework signal, desired-position και order-intent contracts.
- Event/clock/instrument/unit mapping.
- Explicit, approved, pinned NautilusTrader dependency.
- Phase 4 portfolio output και existing risk gates όπου εφαρμόζεται.

### Migration risks

- Timestamp/timezone, bar-close/event ordering και instrument precision mismatch.
- Fill model, latency, fees, funding, partial fills και cancel semantics.
- Divergence μεταξύ simulation και restart/live lifecycle.
- Accidental live connectivity during research tests.

### Exit criteria

- Domain imports contain no NautilusTrader classes.
- Deterministic event fixtures validate signal -> position -> order mapping.
- Simulation costs/fills are reconciled and deltas documented.
- Execution remains disabled by default and fail-closed.
- Paper-only soak/restart/idempotency tests pass before any demo consideration.

## PHASE 6 — Research → Paper → Demo → Live lifecycle

### Στόχος

Να οριστεί auditable, gated promotion από validated research σε operational
modes, με explicit approvals, immutable artifacts, monitoring και rollback.

### Expected modules

```text
src/research/evidence/promotion.py
src/execution/lifecycle/
src/monitoring/promotion_health.py
```

Οι ακριβείς paths εξαρτώνται από το Phase 5 ownership review.

### Dependencies

- Canonically validated candidate και portfolio/risk contract.
- Immutable model/config/data artifacts.
- Broker adapter safety, secrets management και reconciliation.
- Monitoring/drift/health/latency/PnL services.

### Lifecycle

```text
research candidate
  -> canonical validation
  -> paper shadow
  -> demo
  -> explicitly approved live
  -> continuous monitoring
  -> pause / rollback / retire
```

### Migration risks

- Treating backtest success as deployment authorization.
- Model/config/data skew μεταξύ modes.
- Missing account-wide risk, restart parity ή stale order reconciliation.
- Monitoring that reports but cannot fail closed.
- Implicit promotion by config/default change.

### Exit criteria

- Every transition has explicit actor, artifact hashes, gates and audit event.
- Paper/demo/live use the same versioned strategy/model contract.
- Live is impossible without explicit configuration and approval.
- Restart/idempotency/order reconciliation and kill-switch behavior are tested.
- Monitoring supports drift, execution quality, exposure, PnL and safety alerts.
- Rollback/retirement preserves complete evidence and operational history.

## Deferred structural migrations

Οι παρακάτω κινήσεις δεν συνδέονται αυτόματα με συγκεκριμένη external backend
phase και χρειάζονται ξεχωριστή proposal/ADR όταν ωριμάσουν:

- potential `src/src_data -> src/data` rename,
- reduction του broad runner `__all__`,
- decomposition `orchestration/artifacts.py`, `reporting.py` και
  `backtest_stage.py`,
- classification/migration reusable logic από `experiments/support`,
- extraction tested domain logic από `scripts`,
- convergence της registry lazy-loading policy,
- creation `src/core` only for proven shared contracts.

Exit criterion για κάθε τέτοια migration είναι parity και zero untracked usage,
όχι απλώς καθαρότερο directory tree.
