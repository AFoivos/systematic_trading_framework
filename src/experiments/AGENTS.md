# Experiment Guardrails

## Scope
- These rules apply to `src/experiments/` and supplement the repo root `AGENTS.md`.

## Responsibility Boundary
- Keep orchestration, targets, split logic, run assembly, and reporting here.
- Keep experiment-side helper utilities under `src/experiments/support`, not mixed with estimator engines.
- Keep estimator-specific training and inference logic in `src/models/`, not here.
- Keep config parsing, defaults, and validation in `src/utils/config_*`, not stage modules.
- Keep raw data normalization and PIT enforcement in `src/src_data/`, not here.

## Anti-Leakage Rules
- Ensure predictions remain out-of-sample only.
- Compute fold thresholds, label cutoffs, and fitted statistics from training data only.
- Keep split logic chronological and purge-aware when applicable.
- Do not construct features or targets with future information.

## Stable Surfaces
- Keep `runner.py` as a thin facade.
- Keep stage modules focused and free of ad-hoc cross-layer logic.
- Keep disk writes inside artifact or storage layers, not arbitrary pipeline steps.
- Preserve existing return contracts unless the user requests a deliberate interface change.

## Change Coupling
- A new experiment config key requires defaults, validation, typed schema, and tests in the same change.
- A new model family requires registry wiring, typed config coverage, and reuse of shared split and runtime policy.
- Cross-asset or portfolio behavior changes require explicit evaluation and backtest coverage.
- Changes to metadata or artifact payloads must preserve reproducibility fields.

## Validate
- Run the relevant no-lookahead, runner, and orchestration tests for touched behavior.
- Re-check any changed fold metadata, evaluation payloads, or artifact contracts.
