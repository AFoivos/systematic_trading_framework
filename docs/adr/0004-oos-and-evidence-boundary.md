# ADR 0004 — OOS and evidence boundary

## Status

Accepted — Phase 0, 2026-08-14.

## Context

Το repository ήδη ορίζει immutable roles `DISCOVERY`, `VALIDATION`,
`HISTORICAL_PSEUDO_OOS` και `PROSPECTIVE_FINAL`, καθώς και role-bound data
access. Η V2 χρειάζεται user-facing stages `development`, `validation` και
`final_holdout` χωρίς δεύτερο, ασύμβατο evidence model.

## Decision

Η mapping είναι:

- `development -> DISCOVERY`,
- `validation -> VALIDATION`,
- `final_holdout -> PROSPECTIVE_FINAL`.

`HISTORICAL_PSEUDO_OOS` είναι diagnostics-only και δεν αναβαθμίζεται σε final
evidence. Κάθε material specification change μετά την κατανάλωση validation ή
final evidence εφαρμόζει τα υπάρχοντα contamination/restart rules. External
backend results είναι candidate metadata μέχρι canonical validation.

## Consequences

- Δεν δημιουργείται duplicate evidence hierarchy.
- Locked/inspected history δεν παρουσιάζεται ως genuinely final.
- Promotion απαιτεί role, sample και artifact provenance.
- Η prospective final απαίτηση είναι αυστηρότερη αλλά επιστημονικά auditable.

## Alternatives considered

- **Νέο enum μόνο για V2:** απορρίφθηκε ως duplicate contract.
- **Historical validation ως final holdout:** απορρίφθηκε λόγω reuse/inspection
  contamination.
- **Trust backend OOS labels:** απορρίφθηκε χωρίς framework role και split
  verification.
