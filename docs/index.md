# Κέντρο τεκμηρίωσης

Τελευταία ενημέρωση: 2026-08-15

Αυτός είναι ο κεντρικός χάρτης τεκμηρίωσης του repo. Αν χρησιμοποιείς πρώτη
φορά το framework, ξεκίνα από το quickstart και μετά πέρασε στον οδηγό YAML.

## Για νέους χρήστες

1. [README](../README.md): συνοπτική εικόνα του project, δομή φακέλων και
   βασικές εντολές.
2. [Quickstart](quickstart_gr.md): πώς στήνεις περιβάλλον, τρέχεις tests και
   εκτελείς το πρώτο experiment.
3. [Οδηγός YAML experiments](yaml_experiments_guide_gr.md): πώς γράφεις
   config-driven experiments με features, helpers, targets, models και signals.
4. [Οδηγός lab experiments](lab_experiments_guide_gr.md): ασφαλές workflow
   δοκιμών και πλήρες registry-backed YAML reference όλων των components.
5. [Project workflow](project_workflow_gr.md): πρακτική ροή εργασίας για data,
   research, backtesting, reporting και execution.

## Για ανάπτυξη και επέκταση

- [Αρχιτεκτονική](architecture.md): package boundaries, registries και canonical
  pipeline.
- [Architecture V2](ARCHITECTURE_V2.md): four-layer target architecture,
  research contracts, evidence boundary, external-adapter policy και
  compatibility strategy.
- [Architecture V2 roadmap](architecture_v2_roadmap.md): incremental phases,
  risks και exit criteria για research, portfolio και event-driven backends.
- [VectorBT Research Backend](vectorbt_backend.md): Phase 3A finite-grid
  screening adapter, timing/cost mapping, resource guards και canonical
  validation boundary.
- [PyBroker ML Walk-Forward Backend](pybroker_backend.md): Phase 3B supervised
  ML screening με STF-authoritative purged folds, train-only preprocessing,
  explicit OOS provenance και canonical-validation boundary.
- [STF-native Multi-Asset Research Dataset](multi_asset_research_dataset.md):
  Phase 3C-R1 canonical `(timestamp, asset_id)` contract, chronological
  discovery segments, prediction eligibility, missing-observation policy και
  portable fingerprint/provenance.
- [STF-native Multi-Asset Alpha Research](multi_asset_alpha_research.md): Phase
  3C-R2 per-asset/cross-sectional OOS prediction research, target-horizon purge,
  per-asset coverage, rank IC, bounded search και candidate-validation boundary.
- [Research & Evidence Layer](research_evidence_layer.md): Phase 1 hypothesis,
  run/search, candidate, evidence, robustness, final-holdout και promotion
  contracts.
- [Research Layer Inventory](research_layer_inventory.md): classification και
  migration risk όλων των modules του `src/experiments/support`.
- [Architecture decision records](adr/): concise canonical decisions για
  pipeline, package boundaries, adapters, evidence και market making.
- [Κατάλογος features](catalog/features.md): διαθέσιμα feature steps και causal
  υποθέσεις, χωρισμένα σε οικογένειες με ερμηνεία τιμών.
- [KDS / RLVS / LMDS market-state systems](features/quant_market_state.md):
  τύποι, presets, output reference, causal validation και benchmarks.
- [Κατάλογος helpers](catalog/helpers.md): διαθέσιμα transform και normalization
  helpers, με κατηγορίες, παραδείγματα και πρακτική ερμηνεία outputs.
- [Feature normalization playbook](feature_normalization_playbook_gr.md):
  ελληνικό playbook για normalizations, helpers και feature combinations με
  προτεραιότητα χρήσης.
- [Signal catalog](catalog/signals.md): διαθέσιμα signal builders, χωρισμένα σε
  κατηγορίες με ερμηνεία τιμών και παραδείγματα.
- [Target catalog](catalog/targets.md): targets/labels, forecast horizons,
  barrier outcomes και R-multiple ερμηνεία.
- [Model catalog](catalog/models.md): classifiers, forecasters, sequence models,
  feature discovery και RL policies με ερμηνεία outputs.
- [Market-making subsystem](market_making.md): event-driven paper/research
  market making, MOMENT quote-filter experiments και diagnostics artifacts.
- [Execution source audit](execution_source_audit.md): audit για execution
  πηγές και runtime assumptions.

## Βασικός κανόνας ανάγνωσης

Το framework είναι research-first. Κάθε feature, target, signal και model πρέπει
να ελέγχεται ως προς:

- χρονική αιτιότητα,
- data leakage,
- reproducibility,
- explicit assumptions για costs/spread/slippage,
- σταθερότητα εκτός δείγματος.

Όταν υπάρχει αμφιβολία, προτίμησε πιο απλό, πιο ελέγξιμο πείραμα.
