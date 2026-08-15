# ADR 0002 — Package boundaries and dependency direction

## Status

Accepted — Phase 0, 2026-08-14.

## Context

Το repository έχει ώριμα package owners, αλλά υπάρχουν compatibility imports,
strategy-specific bundles, μεγάλα orchestration/support modules και reusable
logic σε scripts. Ένα mass move θα άλλαζε imports/configs χωρίς να βελτιώσει
απαραίτητα contracts.

## Decision

Η V2 οργανώνεται σε Domain, Research, Simulation και Operations layers.
Orchestration εξαρτάται από reusable packages, όχι το αντίστροφο. Τα packages
κρατούν framework-owned types. Νέες reverse dependencies όπως
`features -> experiments`, `targets -> execution`,
`models -> experiments.runner` και `portfolio -> broker` απαγορεύονται.
Υφιστάμενο debt μετακινείται μόνο contract-first, με inventory, facade και
parity tests.

## Consequences

- Η νέα functionality αποκτά σαφή owner.
- Το σημερινό tree εξελίσσεται χωρίς mass rename.
- Ορισμένες legacy θέσεις παραμένουν μέχρι ελεγχόμενη migration.
- Architecture tests προστατεύουν σημαντικά boundaries, όχι κάθε πιθανό import.

## Alternatives considered

- **Immediate target-tree rewrite:** απορρίφθηκε ως υψηλού ρίσκου churn.
- **Καμία enforced direction:** απορρίφθηκε επειδή θα συνέχιζε coupling.
- **Ένα global `core` τώρα:** αναβλήθηκε μέχρι να υπάρχει πραγματικό shared
  contract και migration case.
