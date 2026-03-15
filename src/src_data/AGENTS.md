# Data Layer Guardrails

## Scope
- These rules apply to `src/src_data/` and supplement the repo root `AGENTS.md`.

## PIT Invariants
- Normalize timestamps explicitly.
- Make timezone assumptions explicit; never rely on implicit local time behavior.
- Keep universe membership, duplicate handling, and corporate-action policy explicit.
- Do not forward-fill, backfill, or align data in ways that leak future information.

## Canonical Contracts
- Keep provider quirks isolated inside provider adapters.
- Preserve the project's canonical OHLCV and metadata schema after loading.
- Keep raw snapshots distinct from processed feature snapshots.
- Preserve symbol-level and timestamp-level traceability needed for reproducibility.

## Storage and Path Safety
- Use project-safe paths and existing path helpers.
- Keep writes inside configured storage or artifact locations.
- Preserve metadata needed for snapshot provenance, hashes, and run manifests.
- Fail loudly on invalid schema, missing required columns, or unsafe paths.

## Change Coupling
- Pair schema changes with validation updates and round-trip tests.
- Pair PIT behavior changes with targeted regression tests.
- Pair provider normalization changes with tests that lock the canonical output shape.
- Keep external API assumptions localized to provider modules.

## Validate
- Run the relevant PIT, contracts, and storage tests.
- Re-check that snapshot loading, saving, and membership enforcement remain deterministic.
