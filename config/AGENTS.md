# Config Guardrails

## Scope
- These rules apply to `config/` and supplement the repo root `AGENTS.md`.

## Philosophy
- Treat config as a declarative public interface.
- Prefer explicit keys in fully self-contained experiment YAMLs over inheritance chains.
- Keep tracked experiment configs under `config/experiments/` standalone and reproducible on their own.

## Do
- Keep example experiments realistic and internally consistent.
- When adding a config key, update defaults, validation, typed schemas, and docs in the same change.
- Preserve backward compatibility unless the user explicitly requests a breaking change.
- Make daily versus intraday assumptions explicit in the config surface.

## Do Not
- Do not hide new behavior behind implicit fallback values inside orchestration code.
- Do not encode environment-specific paths, secrets, or one-off local assumptions in tracked configs.
- Do not silently override annualization, timestamp normalization, or alignment semantics.
- Do not duplicate the same default across multiple runtime layers.
- Do not reintroduce tracked `base/*.yaml` parents or make checked-in experiment YAMLs depend on `extends:`.
- The loader rejects `extends`; every tracked experiment YAML must stay fully self-contained.

## Validate
- Check that new keys are loaded by `src/utils/config_loader.py`.
- Check that semantics are enforced in `src/utils/config_validation.py`.
- Check that typed objects remain aligned in `src/utils/config_schemas.py`.
- Update example experiment configs when the public config surface changes.
