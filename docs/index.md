# Κέντρο τεκμηρίωσης

Τελευταία ενημέρωση: 2026-06-27

Αυτός είναι ο κεντρικός χάρτης τεκμηρίωσης του repo. Αν χρησιμοποιείς πρώτη
φορά το framework, ξεκίνα από το quickstart και μετά πέρασε στον οδηγό YAML.

## Για νέους χρήστες

1. [README](../README.md): συνοπτική εικόνα του project, δομή φακέλων και
   βασικές εντολές.
2. [Quickstart](quickstart_gr.md): πώς στήνεις περιβάλλον, τρέχεις tests και
   εκτελείς το πρώτο experiment.
3. [Οδηγός YAML experiments](yaml_experiments_guide_gr.md): πώς γράφεις
   config-driven experiments με features, helpers, targets, models και signals.
4. [Project workflow](project_workflow_gr.md): πρακτική ροή εργασίας για data,
   research, backtesting, reporting και execution.

## Για ανάπτυξη και επέκταση

- [Αρχιτεκτονική](architecture.md): package boundaries, registries και canonical
  pipeline.
- [Feature catalog](catalog/features.md): διαθέσιμα feature steps και causal
  υποθέσεις.
- [Feature normalization playbook](feature_normalization_playbook_gr.md):
  ελληνικό playbook για normalizations, helpers και feature combinations με
  προτεραιότητα χρήσης.
- [Signal catalog](catalog/signals.md): διαθέσιμα signal builders.
- [Target catalog](catalog/targets.md): targets/labels και forecast horizons.
- [Model catalog](catalog/models.md): model kinds, outputs, split contracts και
  leakage guardrails.
- [Execution source audit](execution_source_audit.md): audit για execution
  πηγές και runtime assumptions.

## Strategy και experiment notes

- [C1 30m trend pullback VWAP](experiments/c1_30m_trend_pullback_vwap.md)
- [Opening range breakout για XAU/indices](strategies/opening_range_breakout_xau_indices.md)
- [Trading dashboard assumptions](trading_dashboard_assumptions.md)

## Reports

- [FTMO Optuna meta plan](reports/ftmo_optuna_meta_v1_plan.md)
- [FTMO triple-barrier upgrade review](reports/ftmo_triple_barrier_upgrade_review.md)

## Βασικός κανόνας ανάγνωσης

Το framework είναι research-first. Κάθε feature, target, signal και model πρέπει
να ελέγχεται ως προς:

- χρονική αιτιότητα,
- data leakage,
- reproducibility,
- explicit assumptions για costs/spread/slippage,
- σταθερότητα εκτός δείγματος.

Όταν υπάρχει αμφιβολία, προτίμησε πιο απλό, πιο ελέγξιμο πείραμα.
