# ADR 0003 — External backend adapter policy

## Status

Accepted — Phase 0, 2026-08-14.

## Context

VectorBT, PyBroker, Qlib, skfolio και NautilusTrader έχουν διαφορετικά object
models, capabilities, timing, costs και installation surfaces. Direct use των
classes τους σε domain APIs θα έκανε το framework dependent σε library internals
και θα δυσκόλευε canonical replay.

## Decision

Κάθε external library συνδέεται μέσω optional adapter:

- Qlib/VectorBT/PyBroker πίσω από `src/research/backends`,
- skfolio πίσω από `src/portfolio/adapters`,
- NautilusTrader πίσω από `src/backtesting/adapters` και/ή
  `src/execution/adapters`.

Adapters δέχονται/επιστρέφουν framework-owned contracts, δηλώνουν explicit
capabilities, φορτώνουν dependencies lazy και κρατούν native objects εσωτερικά.
ML4T παραμένει methodological reference.

## Consequences

- Το framework μπορεί να λειτουργεί χωρίς optional backends.
- Κάθε adapter χρειάζεται conversion, parity και absent-dependency tests.
- Capabilities δεν θεωρούνται ίδιες μεταξύ backends.
- Προστίθεται μικρό translation overhead αλλά μειώνεται το lock-in.

## Alternatives considered

- **Native backend classes ως domain API:** απορρίφθηκε λόγω lock-in.
- **Ένα universal backend με implicit capabilities:** απορρίφθηκε επειδή κρύβει
  semantic gaps.
- **Install όλων των libraries από Phase 0:** απορρίφθηκε ως άσκοπο dependency
  και validation burden.
