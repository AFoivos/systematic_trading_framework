# Inventory του `src/experiments/support`

Ημερομηνία επιθεώρησης: 2026-08-14

Σκοπός του inventory είναι να καθορίσει ownership πριν από οποιαδήποτε
μετακίνηση. Στο Phase 1 **δεν μετακινήθηκε κανένα support module**. Τα target
owners είναι migration directions, όχι έγκριση για rename, schema change ή
behavioral refactor.

## Κατηγορίες

- **A — pure reusable research logic:** calculations που μπορούν να
  απομονωθούν από orchestration/I/O.
- **B — orchestration:** config/data/run assembly και workflow coordination.
- **C — reporting/diagnostics:** summaries, audit tables, plots ή compatibility
  facades προς evaluation diagnostics.
- **D — one-off/legacy experiment support:** asset/trial-specific research
  suites, reconstruction ή notebook generators.
- **E — unclear/compatibility surface:** ownership δεν πρέπει να αλλάξει πριν
  από import-usage inventory.

Priority `P1` σημαίνει πρώτο migration candidate στο Phase 2, `P2` μεταγενέστερο
decomposition και `P3` keep/facade μέχρι να υπάρχει συγκεκριμένος λόγος. Το
compatibility risk αξιολογεί πιθανότητα να σπάσουν imports, artifacts ή locked
research semantics, όχι ποιότητα κώδικα.

## Module inventory

| Module | Category | Current role | Target owner | Migration priority | Compatibility risk |
|---|---|---|---|---|---|
| `__init__.py` | E | Lazy compatibility exports για diagnostics, metrics και target builders | Παραμένει thin `src.experiments.support` facade μέχρι import inventory | P3 | Medium: public re-exports μπορεί να χρησιμοποιούνται από configs/tests |
| `barrier_probability.py` | C | Barrier-probability calibration, regime, sensitivity και cost diagnostics πάνω σε target/backtest outputs | `src/evaluation` diagnostics· orchestration μόνο στον caller | P2 | Medium: payload/artifact consumers μπορεί να βασίζονται σε σημερινά keys |
| `baseline_diagnostics.py` | C | VWAP/RMS/EMA/PPO/MFI/ATR baseline trade summaries ανά context | `src/evaluation` strategy diagnostics ή παραμονή compatibility wrapper | P3 | Medium: strategy-specific column vocabulary |
| `btcusd_dual_trend_ftmo.py` | B | Locked BTCUSD pipeline: data, features/signals, backtest, FTMO evaluation, parity, reports/artifacts | `src/experiments` orchestration με domain logic στους υπάρχοντες feature/backtest/evaluation owners | P2 | High: fixed paths, reference parity και artifact layout |
| `c2_diagnostics.py` | C | C2 regime/momentum signal-count και trade diagnostics | `src/evaluation` diagnostics | P3 | Medium: depends on C2-specific columns |
| `c2_scalp_grid.py` | D | Narrow C2 parameter grid, private runner loading, manual backtests και artifact writing | Μελλοντικό `src/research` screening coordinator + canonical experiment/artifact facade | P1 | High: imports private runner API και combines search/execution/reporting |
| `diagnostics.py` | C | Compatibility re-export facade προς `src.evaluation.diagnostics` | Παραμένει thin facade, canonical logic ήδη στο `src/evaluation` | P3 | Low: no local algorithm, αλλά imports μπορεί να είναι widespread |
| `ehlers_continuation_long_diagnostics.py` | C | Long-side Ehlers continuation counts/performance/robustness summary | `src/evaluation` strategy diagnostics ή compatibility wrapper | P3 | Medium: fixed output-column contract |
| `ehlers_continuation_short_diagnostics.py` | C | Short-side Ehlers continuation counts/performance/robustness summary | `src/evaluation` strategy diagnostics ή compatibility wrapper | P3 | Medium: fixed output-column contract |
| `ehlers_ml_ablation.py` | B | Builds ablation configs και invokes experiment runner | `src/experiments` research orchestration using Phase 1 run/selection records | P2 | Medium: generated-config and run naming compatibility |
| `ethusd_broker_alpha.py` | D | ETHUSD frozen-model transfer, approximate OOT, tick ledger, M1 gates και suite artifacts | Split only after audit: experiment coordinator; reusable ledger/evaluation logic to owning domain packages | P2 | High: broker-export, frozen-model και artifact assumptions |
| `ethusd_broker_alpha_notebook.py` | D | Generates a notebook around the ETHUSD broker-alpha suite | `notebooks`/experiment-facing generator; keep import facade if referenced | P3 | Medium: generated notebook cells/paths are an artifact contract |
| `ethusd_custom_indicator_alpha.py` | D | Candidate grid/selection, bar/tick barrier ledgers και custom indicator suite | Phase 2 research screening/selection + canonical backtesting/evaluation owners | P1 | High: selection-period semantics and exact-tick reconciliation |
| `ethusd_custom_indicator_alpha_notebook.py` | D | Generates notebook for custom-indicator alpha research | `notebooks`/experiment-facing generator | P3 | Medium: generated notebook and output paths |
| `ethusd_pattern_atlas.py` | D | Pattern definitions, candidate grids, ledgers, ranking/stability και full suite | Phase 2 hypothesis/screening/selection contracts; ledgers remain backtesting/evaluation-owned | P1 | High: large coupled research universe and selection history |
| `eurusd_ftmo_ml_v2.py` | D | EURUSD reference reconstruction, parity reporting, feature/candidate/backtest walk-forward workflow | `src/experiments` compatibility orchestrator over existing domain modules | P2 | High: reconstruction/reference hashes and FTMO semantics |
| `execution_source_audit.py` | C | Static audit of execution-related source/config surface and report writer | `src/evaluation`/architecture audit tooling; thin experiment writer facade | P2 | Low: primarily read-only reporting, but report schema may be consumed |
| `forecast_alpha_diagnostics.py` | C | Fold backtests, threshold grids, baseline και regime diagnostics | `src/evaluation` diagnostics | P2 | Medium: backtest timing and diagnostic payload keys |
| `fresh_alpha_discovery.py` | D | Monolithic config, data QA, causal features, signals, quote-aware backtest, walk-forward και baselines | Decompose in Phase 2 across `src/research`, features/signals/backtesting/evaluation; retain facade | P1 | High: broad behavior, cost/timing and split semantics |
| `funding_carry.py` | D | Funding-carry config/domain records, causal alignment/forecast, segment simulation, splits, acceptance και artifact orchestration | Experiment coordinator; reusable feature/backtest/validation logic to owning packages after parity tests | P2 | High: specialized funding timestamps, costs and locked data contract |
| `funding_carry_reporting.py` | C | Calendar/rolling/bootstrap metrics, ledger extraction και reporting tables | `src/evaluation` reporting/robustness | P2 | Medium: metric/table schema and resampling assumptions |
| `matb_diagnostics.py` | C | Target/backtest parity diagnostic using portfolio barrier engine | `src/evaluation` contract diagnostics | P2 | Medium: parity tolerance and engine semantics |
| `metrics.py` | C | Compatibility facade προς `src.evaluation.model_metrics` | Παραμένει thin facade; canonical logic ήδη στο `src/evaluation` | P3 | Low: no local calculations |
| `notebook_lab.py` | B | Notebook helpers for paths/config mutation, canonical run invocation και analysis frames | `src/experiments` interactive orchestration; portable selection records where candidates are emitted | P2 | Medium: public notebook API and private artifact conventions |
| `stc_roofing_hilbert_diagnostics.py` | C | STC/roofing/Hilbert signal counts and trade performance summaries | `src/evaluation` strategy diagnostics ή compatibility wrapper | P3 | Medium: fixed feature/signal columns |
| `targets.py` | E | Wildcard compatibility facade for target builders moved to `src.targets` | Keep facade until tracked imports/configs are migrated and deprecated | P3 | Medium: wildcard public surface |
| `trial0041_alpha_lab.py` | D | Large Trial0041 config generation, screening, diagnostics, finalist selection, locked runs and final report | Phase 2 research orchestration/selection; canonical runner and immutable historical artifacts remain authoritative | P1 | High: selection-heavy folds, locked-tail claims and many persisted artifacts |
| `trial0041_locked_confirmation.py` | D | Frozen locked-only confirmation configs/manifests, OOS assertions, robustness and reports | Canonical validation compatibility workflow using Phase 1 evidence records in a later approved migration | P1 | High: locked sample consumption, hashes and confirmation claims |
| `tsfresh_extrema_feature_discovery.py` | A | Fold-safe tsfresh extraction/relevance/importance aggregation for extrema research | `src/research` feature-discovery service with feature/model/evaluation contracts; optional dependency stays lazy | P1 | High: fold fitting, horizon purge and optional tsfresh semantics |

## Phase 2 migration order

1. Προσθήκη adapters που εκπέμπουν `ResearchRun`, `SelectionRecord` και
   `ResearchCandidate` γύρω από **ένα** existing workflow, χωρίς αλλαγή
   calculation ή artifact paths.
2. Εξαγωγή μόνο καθαρών functions όταν parity tests αποδεικνύουν ίδια outputs.
3. Διατήρηση one-directional facades στα παλιά imports.
4. Μεταφορά reporting ξεχωριστά από search/backtest logic.
5. Locked/Trial0041 flows τελευταίοι, επειδή η επιθεωρημένη ιστορική evidence
   δεν επιτρέπεται να relabeled ως prospective final.

Το inventory δεν εγκρίνει automatic feature mining, mass search ή external
backend integration. Αυτά παραμένουν εκτός Phase 1.
