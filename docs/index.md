# Κέντρο τεκμηρίωσης

Τελευταία ενημέρωση: 2026-06-29

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
- [Κατάλογος features](catalog/features.md): διαθέσιμα feature steps και causal
  υποθέσεις, χωρισμένα σε οικογένειες με ερμηνεία τιμών.
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
