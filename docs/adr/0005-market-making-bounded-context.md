# ADR 0005 — Market-making bounded context

## Status

Accepted — Phase 0, 2026-08-14.

## Context

Το `src/market_making` έχει quote generation, inventory/risk, paper/live
engines, diagnostics και venue/event assumptions. Το `src/backtesting` είναι
bar-based, ενώ το `src/simulation` περιέχει deterministic order-book replay.
Forced unification θα μπορούσε να χάσει sequence, queue, latency και partial
fill semantics.

## Decision

Το market making παραμένει ξεχωριστό bounded context. Μοιράζεται μόνο
framework-owned contracts όπου οι semantics είναι πραγματικά κοινές. Δεν
μετατρέπουμε order-book events σε bars για API ομοιομορφία. Future
NautilusTrader adapters διατηρούν explicit event/instrument/fill mapping και δεν
αντικαθιστούν το market-making domain.

## Consequences

- Προστατεύονται event-driven και venue-specific assumptions.
- Μπορεί να υπάρχει μικρή, δικαιολογημένη duplication μεταξύ bar και event
  metrics/risk concepts.
- Shared contracts απαιτούν semantic parity tests.
- Event-driven adapters χρειάζονται ξεχωριστή simulation και execution review.

## Alternatives considered

- **Ένα κοινό bar/event engine:** απορρίφθηκε ως false abstraction.
- **Μεταφορά market making στο backtesting:** απορρίφθηκε επειδή περιλαμβάνει
  operational/event lifecycle.
- **Πλήρης απομόνωση χωρίς shared contracts:** απορρίφθηκε επειδή εμποδίζει
  κοινό provenance, risk intent και monitoring όπου είναι ασφαλές.
