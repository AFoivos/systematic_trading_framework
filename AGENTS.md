# Agent Guardrails

## Scope and Precedence
- These rules apply repo-wide.
- A nested `AGENTS.md` may add stricter local rules.
- Local rules must never relax root rules.

## Project Intent
- Treat this repo as a research-first systematic trading framework.
- Optimize for correctness, reproducibility, and modular architecture.
- Prefer temporal causality and auditability over convenience or speed.

## Non-Negotiables
- Do not introduce lookahead, leakage, or train/test contamination.
- Do not change config or runtime defaults silently.
- Do not blur boundaries among `src/models`, `src/experiments`, `src/src_data`, and `src/utils`.
- Do not move exploratory logic into production paths without explicit approval.

## Work Before Edits
- Read the touched module, its nearest `AGENTS.md`, and relevant tests before editing.
- Inspect existing docs, configs, and tests to preserve current contracts.
- Ask before making broad refactors, large renames, or cross-package reorganizations.

## Editing Rules
- Prefer minimal, local changes over repo-wide churn.
- Preserve stable facades such as `src/utils/config.py`, `src/experiments/runner.py`, and package `__init__` exports.
- Keep side effects explicit and isolated to the correct layer.
- If the request is advisory only, do not modify code or configs.

## Validate
- Run targeted tests for the touched area.
- Run `pytest -q` for cross-cutting changes or contract changes.
- Add or update regression coverage when behavior changes intentionally.
- Never delete or weaken anti-leakage or reproducibility tests to make a change pass.

## Escalate Before Proceeding
- New dependency or external service integration.
- New top-level package or major module move.
- Schema or config contract change.
- Artifact format or output layout change.
- Any change to time-split semantics, PIT logic, or portfolio constraints.
