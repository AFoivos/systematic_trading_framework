# Audit πηγαίου κώδικα εκτέλεσης

Τελευταία ενημέρωση: 2026-07-11

Ένα experiment μπορεί προαιρετικά να παράγει read-only snapshot του σχετικού
Python source:

```yaml
logging:
  execution_source_audit:
    enabled: true
```

Η προεπιλογή είναι `enabled: false`. Όταν ενεργοποιείται, το run directory
περιέχει `execution_source_audit.py` και το artifact καταγράφεται στο
`artifact_manifest.json`.

## Τι περιλαμβάνει

- Το resolved experiment config ως σχολιασμένο YAML.
- Την configured σειρά των pipeline stages.
- Τις επιλεγμένες υλοποιήσεις feature, target, model, signal και backtest.
- Repo-local Python modules που εισάγονται transitively από αυτές τις
  υλοποιήσεις.
- Relative source path και runtime-stage σχόλιο πριν από κάθε function.

Η λίστα stages είναι η authoritative υψηλού επιπέδου σειρά. Η αρίθμηση των
helpers αποτελεί σταθερή σειρά ανάγνωσης, όχι dynamic profiler trace: ένας
helper μπορεί να εκτελεστεί υπό συνθήκη ή περισσότερες φορές μέσα σε loop.

## Τι δεν είναι

- Δεν είναι executable reproduction του run.
- Δεν αντικαθιστά `config_used.yaml`, hashes, dataset fingerprint ή environment
  metadata.
- Δεν αποδεικνύει από μόνο του ότι το run είναι απαλλαγμένο από leakage.
- Δεν πρέπει να εκτελείται ως Python script.

## Πηγές αλήθειας και tests

- `src/experiments/support/execution_source_audit.py`
- `src/experiments/orchestration/artifacts.py`
- `src/utils/config_defaults.py`
- `src/utils/config_validation.py`
- `tests/test_hardening_fixes.py`
- `tests/test_config_validation.py`
