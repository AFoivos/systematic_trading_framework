# ADR 0001 — Canonical experiment pipeline

## Status

Accepted — Phase 0, 2026-08-14.

## Context

Το repository έχει established YAML experiments, CLI
`python -m src.experiments.runner`, programmatic `run_experiment`, registry key
`canonical_experiment` και πραγματική orchestration στο
`src.experiments.orchestration.pipeline.run_experiment_pipeline`. Future
research backends θα μπορούσαν να δημιουργήσουν δεύτερα end-to-end entrypoints
με διαφορετικά data, timing, costs και evidence semantics.

## Decision

Το υπάρχον runner και το `canonical_experiment` παραμένουν τα stable canonical
entrypoints. External backends κάνουν screening και παράγουν portable
`ResearchCandidate` records. Candidate promotion απαιτεί replay/validation από
το framework-owned pipeline. Custom pipelines μπορούν να παραμένουν registered,
αλλά δεν χαρακτηρίζονται canonical χωρίς explicit contract.

## Consequences

- Διατηρούνται legacy YAMLs, imports και operational tooling.
- Backend metrics δεν γίνονται final evidence αυτόματα.
- Το broad runner facade παραμένει προσωρινά compatibility surface.
- Parity/conversion work απαιτείται για κάθε backend.

## Alternatives considered

- **Νέο V2 runner:** απορρίφθηκε επειδή δημιουργεί parallel framework.
- **External backend ως canonical engine:** απορρίφθηκε λόγω lock-in και
  semantic drift.
- **Immediate runner rewrite:** απορρίφθηκε λόγω μεγάλου compatibility risk.
