# Agent Guardrails — Systematic Trading Framework Architecture V2

## Scope and precedence

- These rules apply repository-wide.
- A nested `AGENTS.md` may add stricter local rules; it must not relax this file.
- User instructions remain authoritative, but material schema, split, artifact,
  portfolio, dependency, or live-safety changes must be called out explicitly.

## Repository mission

- Evolve this repository as the canonical research-first systematic trading
  framework. Do not build a competing framework beside it.
- Optimize for temporal causality, correctness, reproducibility, auditability,
  modular architecture, and realistic execution assumptions.
- Keep the framework in control of its YAML schema, domain contracts,
  evidence rules, transaction-cost conventions, and promotion decisions.
- Treat external libraries as optional, replaceable adapters. Never make their
  classes the framework's core domain types.

## Stable entrypoints and canonical lifecycle

The stable CLI entrypoint is:

```bash
python -m src.experiments.runner path/to/config.yaml
```

The stable programmatic entrypoint is
`src.experiments.runner.run_experiment`. The canonical pipeline registry name
is `canonical_experiment`, exposed by
`src.pipelines.canonical_pipeline.run_canonical_pipeline`.

The canonical lifecycle is:

1. Load and validate the YAML experiment.
2. Resolve and load data through `src/src_data`.
3. Apply PIT hardening and data-contract validation.
4. Build causal features.
5. Build labels/targets and train models with chronological OOS splits.
6. Build signals from information available at decision time.
7. Construct portfolio/risk state where enabled.
8. Run backtesting with explicit timing and costs.
9. Evaluate OOS evidence and robustness.
10. Write monitoring, execution outputs, metadata, and artifacts.

Do not bypass this lifecycle for results described as canonical. A screening
backend may nominate a candidate, but canonical validation remains owned by
this repository.

## Architecture V2 layer ownership

### Domain layer

- `src/src_data`: loading, normalized market-data contracts, PIT hardening,
  research snapshots, data roles, and data quality.
- `src/features`: causal, reusable feature builders and explicit transforms.
- `src/targets`: label generation with explicit horizon and future-data use.
- `src/models`: estimator adapters, fold-safe preprocessing, training, and
  inference; models do not load their own datasets.
- `src/signals`: decisions over already available feature/model columns.
- `src/portfolio`: portfolio construction, weights, covariance, constraints.
- `src/risk`: sizing, limits, exposure, and risk-control logic.

### Research layer

- `src/research`: library-agnostic request, result, candidate, evidence, and
  backend contracts.
- `src/experiments/alpha_*`, `src/src_data/research_*`, and approved research
  workflows remain valid while they migrate incrementally.
- Research may use domain packages. Domain packages must not depend on research
  orchestration or optional screening libraries.

### Simulation layer

- `src/backtesting`: canonical bar-based engines, trade lifecycle, timing,
  slippage, costs, and backtest result contracts.
- `src/simulation`: deterministic event/order-book simulation helpers.
- `src/market_making`: separate event-driven market-making bounded context.
- Future event-driven libraries belong behind adapters; they do not replace
  framework-owned signal, position-intent, order-intent, or evidence contracts.

### Operations layer

- `src/execution`: paper/demo/live broker integration and order operations.
- `src/monitoring`: drift, stability, latency, health, and PnL monitoring.
- `src/experiments`: orchestration, reporting, search, and artifact assembly.
- `src/pipelines`: stable pipeline facades and pipeline registry.
- `src/utils`: stable shared configuration/reproducibility utilities, not a
  destination for arbitrary domain logic.

## Dependency direction

Prefer dependencies that flow from orchestration toward reusable components:

```text
experiments / pipelines
        |
        v
research / evaluation / backtesting / execution
        |
        v
portfolio / risk / signals / models
        |
        v
features / targets / src_data
        |
        v
small framework-owned contracts and utilities
```

Current compatibility imports may be narrower than this target. Do not add new
reverse dependencies to imitate legacy debt.

Forbidden examples:

- `features -> experiments`
- `targets -> execution`
- `models -> experiments.runner`
- `signals -> src.src_data.loaders`
- `portfolio -> broker/execution adapters`
- `evaluation -> model training`
- `research contracts -> optional backend libraries`
- domain objects typed as VectorBT, PyBroker, Qlib, skfolio, or NautilusTrader
  classes

If a boundary cannot yet be cleaned without a broad refactor, preserve current
behavior, document the debt, add no new coupling, and put the migration in the
roadmap.

## Non-negotiable leakage and OOS rules

- Never introduce lookahead, target leakage, train/test contamination, or
  survivorship hidden by data preparation.
- A feature at time `t` may use only data available at the declared decision
  time. Rolling windows must be backward-looking.
- Targets may use future observations only to create labels. Target-derived
  columns must never leak into model inputs or signal decisions.
- Fit scalers, encoders, imputers, thresholds, calibrators, feature selectors,
  and model state on training folds only.
- Use chronological splits. Purge/embargo overlapping horizons when needed.
- Generate predictions OOS only for evidence claims; record OOS coverage and
  missing predictions.
- Do not tune after inspecting validation/final evidence without treating that
  evidence as consumed and restarting the applicable lifecycle.
- Do not relabel inspected historical data as final evidence.

The existing evidence roles are canonical:

- `DISCOVERY`: development and tuning.
- `VALIDATION`: frozen-hypothesis validation.
- `HISTORICAL_PSEUDO_OOS`: historical diagnostics that can never become final.
- `PROSPECTIVE_FINAL`: separately sourced post-freeze final evidence.

Architecture V2 maps `development`, `validation`, and `final_holdout` onto
`DISCOVERY`, `VALIDATION`, and `PROSPECTIVE_FINAL` respectively.

## Configuration rules

- YAML remains the canonical user-facing experiment configuration.
- Do not change config keys, defaults, units, or runtime behavior silently.
- A new active config key requires loader/default handling, validation, typed
  schema coverage where used, documentation, and tests in the same change.
- Unsupported future backend syntax belongs in documentation until implemented.
  If accepted by a schema, it must fail clearly as unsupported rather than
  pretending to run.
- Preserve self-contained configs, stable hashing, seeds, resolved config
  artifacts, and provenance fields.
- Never put secrets or credentials in configs, source, logs, or artifacts.

## Registry rules

Canonical registries are owned by:

- `src/features/registry.py`
- `src/signals/registry.py`
- `src/targets/registry.py`
- `src/models/registry.py`
- `src/pipelines/registry.py`

For registry changes:

- Keep names stable and unique.
- Prefer lazy loading when a component has heavy or optional dependencies.
- Keep deprecated aliases separate from canonical names and document removal
  criteria.
- Unknown names must fail with informative errors.
- Do not turn `src.experiments.registry` back into an owner; it is a
  compatibility facade.
- Add contract, resolver, validation, and docstring/catalog coverage.

## Backtest timing and transaction costs

- State when a signal becomes available and when an order may fill.
- Do not use a bar close for a fill that logically occurs before that close.
- Apply configured execution delays without crossing OOS boundaries.
- Record gross returns, turnover, spread, commission, slippage, holding/funding
  costs, and net returns using explicit units and per-side/round-trip semantics.
- Do not double-charge or omit costs when combining generic and specialized
  engines.
- Stress costs and execution delay for claims that depend on execution quality.
- Keep canonical validation capable of replaying external candidates under this
  repository's timing, costs, risk, and robustness assumptions.

## Research, simulation, and execution separation

- Screening metrics are candidate metadata, not final evidence.
- Research backends return framework-owned `ResearchResult` and
  `ResearchCandidate` values or an explicitly compatible serialized form.
- Backend-native objects stay inside their adapter.
- Alpha/signal generation must not decide final portfolio weights when that is
  a portfolio responsibility.
- Portfolio construction must not place broker orders.
- Backtests must not silently trigger paper/demo/live execution.
- Research and backtest artifacts must be clearly separated from runtime/live
  state.

## External adapter policy

- ML4T is methodological guidance, not a runtime dependency.
- Qlib, VectorBT, and PyBroker belong behind `src/research/backends` adapters.
- skfolio belongs behind a future `src/portfolio/adapters` boundary.
- NautilusTrader belongs behind future `src/backtesting/adapters` and/or
  `src/execution/adapters` boundaries.
- Optional dependencies must be lazy, version-pinned when introduced, guarded
  by capability checks, and covered by adapter contract tests.
- Core/domain packages must import without optional backends installed.
- Adding a dependency or activating an external service requires explicit user
  approval and a documented compatibility/fallback plan.

## Market-making bounded context

- Keep `src/market_making` separate from bar-based research and backtesting.
- Preserve order-book, sequencing, queue, latency, inventory, and asynchronous
  assumptions.
- Share only genuinely common, framework-owned contracts.
- Do not force market-making events into bar abstractions or reuse bar metrics
  without validating their semantics.

## Compatibility and migration policy

- Prefer minimal, local, incremental changes. No blind rewrite or mass move.
- Preserve stable facades including `src/utils/config.py`,
  `src/experiments/runner.py`, package `__init__` exports, registry names, YAML
  behavior, and artifact paths unless a versioned migration is approved.
- Keep compatibility aliases thin and one-directional. New code uses canonical
  paths; old paths may forward to them temporarily.
- Do not remove a facade until tracked configs/imports have been inventoried,
  migrated, tested, and documented with a deprecation window.
- A possible future `src/src_data -> src/data` rename is migration work, not an
  opportunistic cleanup.
- Ask before broad refactors, large renames, cross-package moves, schema or
  artifact-contract changes, or time-split/portfolio semantic changes.

## Live execution safety

- Default to research, dry-run, or paper mode. Live activation must be explicit.
- Preserve environment/account checks, demo/live separation, duplicate-order
  guards, spread and exposure limits, drawdown/daily-loss gates, stop files,
  idempotency, and restart recovery.
- Never weaken a safety gate to make a test or demo pass.
- Never send orders, contact brokers, or alter live runtime state during a
  research task unless the user explicitly requests it and the configured
  safety gates pass.
- Credentials come from approved secret/environment mechanisms and must be
  redacted from output.

## Workflow for a new feature, target, model, or signal

1. Read the nearest `AGENTS.md`, touched module, registry, config validation,
   and relevant tests.
2. Decide whether the capability is generic and composable. Prefer existing
   EMA/ATR/PPO/MFI/RSI/regime/volatility components plus YAML composition over a
   strategy-specific Python module.
3. Put code in the owning package; keep orchestration and I/O outside it.
4. Declare timing, required columns, outputs, units, defaults, and failure
   behavior.
5. Add the canonical registry entry; use a separate compatibility alias only
   when preserving a real legacy contract.
6. Add config validation/schema coverage where applicable.
7. Add deterministic tests for contract, edge cases, missing inputs, causality,
   split safety, and reproducibility as applicable.
8. Update the relevant catalog/documentation.
9. Run targeted tests, then broader tests for cross-cutting changes.

Asset-specific modules are allowed only for genuinely asset-specific market
microstructure, contract, calendar, or execution behavior. Strategy branding by
itself is not sufficient.

## Test requirements

- Treat tests as executable specifications; never delete or weaken leakage,
  PIT, timing, reproducibility, cost, risk, or safety tests to make a change pass.
- Prefer deterministic synthetic inputs, fixed seeds, and no live network calls.
- Add regression coverage for intentional behavior changes.
- Run the smallest relevant subset first.
- Run `pytest -q` for cross-cutting contract changes when practical.
- Use Docker as the authoritative environment when local dependencies differ:

```bash
docker compose run --rm app pytest -q tests/test_architecture_registries.py
docker compose run --rm app pytest -q tests/test_architecture_v2.py
```

- Report exact commands, pass/fail/skip counts, and any unrun scope. Never claim
  a test passed unless it executed successfully.

## Completion checklist

Before declaring a task complete, verify:

- [ ] No lookahead, leakage, split contamination, or final-evidence relabeling.
- [ ] No silent config/default/timing/cost/risk behavior change.
- [ ] Package ownership and dependency direction are preserved or improved.
- [ ] Stable runner, canonical pipeline, registries, imports, and artifacts stay
      compatible.
- [ ] Optional libraries remain behind adapters and core imports work without
      them.
- [ ] Costs, fill timing, data roles, OOS coverage, and provenance are explicit.
- [ ] Live safety remains fail-closed.
- [ ] Relevant tests and docs were updated and exact validation was reported.
- [ ] Deferred migration work is documented instead of hidden in placeholders.
