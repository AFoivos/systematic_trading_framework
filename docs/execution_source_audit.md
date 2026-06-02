# Execution Source Audit

An experiment can opt into a generated, read-only Python source audit:

```yaml
logging:
  execution_source_audit:
    enabled: true
```

When enabled, the experiment run directory contains `execution_source_audit.py`.
The file is intended for manual code review, not execution. It includes:

- the resolved experiment config as commented YAML;
- the configured pipeline stage order;
- the selected feature, model, signal, target, and backtest implementations;
- transitively imported repo-local Python modules;
- a relative source path and runtime stage comment above every included function.

The stage list is the authoritative high-level execution order. Helper functions may execute
conditionally or repeatedly inside loops, so their generated numeric audit order is a stable
reading order rather than a dynamic profiler trace.
