# Test Guardrails

## Scope
- These rules apply to `tests/` and supplement the repo root `AGENTS.md`.

## Philosophy
- Treat tests as executable specifications of project invariants.
- Prefer regression-first additions when fixing bugs or hardening contracts.
- Keep failures informative and localized to one broken assumption when possible.

## Protected Invariants
- Protect no-lookahead guarantees.
- Protect split ordering, purge, embargo, and horizon semantics.
- Protect PIT integrity and canonical data contracts.
- Protect reproducibility, hashing stability, and deterministic runtime behavior.
- Protect portfolio feasibility, turnover, leverage, and fallback semantics.

## Writing Rules
- Prefer deterministic synthetic data and fixed seeds.
- Avoid live network calls, provider dependencies, or clock-dependent assertions.
- Keep tests close to the behavior being changed.
- Assert contracts and invariants, not incidental implementation trivia.

## Forbidden Moves
- Do not delete or relax a test that exposes a real invariant violation.
- Do not rewrite a test to match broken behavior without explicit approval.
- Do not replace a precise regression with a weaker smoke test.
- Do not introduce flaky tolerances or nondeterministic fixtures without strong justification.

## Validate
- Run the smallest relevant subset first, then `pytest -q` for cross-cutting changes.
- Confirm new tests fail before the fix when practical.
- Keep skipped tests rare and justified in code comments.
