# Evolutionary search

The evolutionary runner searches over full experiment configurations; it is not a second
backtesting framework. Every genome is decoded over a deep copy of an existing base config,
validated by the normal config layer, and evaluated through
`src.experiments.runner.run_experiment`. Existing point-in-time, walk-forward, cost, portfolio,
and reporting behavior remains authoritative.

## Search flow and decision layers

```text
strict evolutionary YAML
    -> typed genome and deterministic decoder contract
    -> clean validated candidate config and candidate identity
    -> existing experiment runner
    -> viability hard constraints and weighted fitness
    -> Optuna NSGA-II search state
    -> independent promotion gates
    -> manifest, candidate configs, reports, and frequency analysis
```

V1 uses a single weighted objective with `optuna.samplers.NSGAIISampler`. A genome constraint
defines structural validity before evaluation (for example, a minimum selected-asset count). A
search hard constraint is a result-level viability rule: if it fails, the trial is rejected and
receives `fitness.failure_score`. A promotion gate is deliberately stricter and is evaluated only
after an otherwise accepted trial has real fitness. Promotion failure sets
`promotion_passed=false` and records the failed gates, but never rejects the trial and never
changes its fitness. Missing hard-constraint metrics use fail-closed `reject`; missing promotion
metrics use fail-closed `fail` only for promotion.

The trial attributes `promotion_passed`, `promotion_failures`, and `promotion_metrics` make this
separation auditable. `promotion_report.csv` reports all trials, while
`promoted_candidates/` contains configs only for COMPLETE, accepted, unique trials that pass all
promotion gates.

## Candidate identity and search contracts

Three hashes have distinct responsibilities:

- `decoded_config_hash` hashes the clean, validated decoded config before candidate provenance
  and candidate-specific logging are added.
- `decoder_contract_hash` hashes the decoder name/version, decoder parameters, every gene spec,
  and all genome constraints.
- `candidate_hash` hashes the canonical genome, base-config hash, decoder-contract hash, and
  clean decoded-config hash.

The same genome and decoding contract therefore produce a stable identity regardless of mapping
insertion order. A decoder-parameter or clean decoded-config change changes candidate identity.
A fitness-only change does not change candidate identity.

`search_contract_hash` covers the base-config hash, decoder-contract hash, fitness components,
viability hard constraints, promotion gates, evaluation policy, failure score, objective
direction, and sampler semantics. Search name is checked separately. The generation budget and
artifact flags are intentionally absent, so an otherwise compatible resume may increase
`generations` without invalidating the contract. Population size, seed, mutation/crossover
probabilities, backend, and duplicate policy remain contract-bound.

Both hashes and the explicit search name are stored in `search_manifest.json` and Optuna study
user attributes. With `resume: true`, a non-empty archive without a manifest fails closed. Any
missing or mismatched name/hash in either the manifest or an existing study also fails before
optimization resumes. This prevents silently combining trials produced by different decoding,
fitness, promotion, or base-config semantics.
An incompatible semantic change requires a new search name plus a new output directory/study;
only a contract-compatible budget increase may reuse the existing archive and study.

Duplicate policies are explicit:

- `reuse` copies the original score, rejection fields, resolved metrics, and promotion result;
- `reject` assigns the declared failure score;
- `reevaluate` runs the decoded candidate again.

Reused/rejected duplicates retain `duplicate_of` and are excluded from unique-candidate archive
and frequency cohorts.

## Validation only

Validation rejects unknown schema keys, validates the base config, genome, constraints, decoder,
and every seed, and validates each clean and provenance-enriched decoded config. It does not load
or create an Optuna study, create SQLite storage, run an experiment, or create the artifact
directory.

```bash
python -m src.experiments.evolutionary.cli \
  --spec config/evolutionary/ethusd_foundation/ga_ethusd_feature_gate_v1.yaml \
  --validate-only

python -m src.experiments.evolutionary.cli \
  --spec config/evolutionary/matb/ga_matb_asset_module_v1.yaml \
  --validate-only
```

## ETHUSD feature/gate search

`ga_ethusd_feature_gate_v1.yaml` preserves the base dataset, target, 24-bar horizon, LightGBM
settings, purged split, embargo, costs, holding, and risk configuration. Its 46 baseline feature
columns are an exact, non-overlapping partition across eight families:

- `returns_lags`, `medium_returns`, `volatility_atr`, `bollinger_range`;
- `ema_trend`, `ehlers_trend`, `ehlers_cycle`, `candle_structure`.

The two Ehlers cycle columns (`roofing_filter_over_atr` and
`dominant_cycle_phase_normalized`) are independent from the six Ehlers trend columns. Together
with two forecast thresholds and four activation gates, the genome has 14 genes. Between three
and eight feature families may be enabled; the `full_baseline` seed enables all eight. Selected
columns always retain base-config order. An explicit categorical `disabled` value removes only
the corresponding activation filter.

ETHUSD fitness remains strict-OOS only and never references a final holdout. The checked-in YAML
has no promotion section, so its accepted search trials are not implicitly treated as promoted.

## MATB asset/module search

`ga_matb_asset_module_v1.yaml` synchronizes selected assets, in base-universe order, across
`data.symbols`, load paths, asset parameters, asset groups, and group-level constraints. A genome
must select at least four assets and at least one non-crypto asset. There is no minimum distinct
group constraint. The `equity_high_vol_exact` seed therefore contains exactly SPX500, US100,
GER40, and NIKKEI225, with the high-volatility regime module enabled and no XAUUSD.

The module gene inserts exactly one registered `volatility_regime` step after
`multi_asset_trend_breakout` and switches to the registered `regime_filtered` signal. When
disabled, only that MATB-specific module is removed and the normal `matb_candidate` signal is
used.

MATB search viability requires only:

- finite `evaluation.primary_summary.mtm_sharpe`;
- at least 100 MATB candidates;
- at least 5 completed trades per year;
- at least 2 calendar walk-forward folds;
- actual mark-to-market maximum drawdown of at least -25%.

Independent promotion requires mark-to-market Sharpe at least 0.50, median walk-forward Sharpe
above zero, positive-fold ratio at least 0.60, positive 2x-cost return, one-bar-delay retention at
least 0.60, maximum asset and group absolute-PnL shares no greater than 0.30 and 0.50, actual
mark-to-market maximum drawdown of at least -10%, at least 60 completed trades per year, and at
least 800 MATB candidates. The drawdown gate uses the actual MTM series; it is not labeled as
target-vol normalized because the deterministic base exposes no such series.

MATB correctly reports `timeline` scope because `model.kind: none` has no fitted-model OOS mask.
Calendar walk-forward robustness is mandatory, and metric paths containing `holdout` or
`final_holdout` are forbidden in both fitness and promotion. A final holdout may be evaluated only
once after a candidate has been locked; it must not choose among search candidates.

## Artifacts and frequency cohorts

All frequency tables use COMPLETE, accepted, unique trials. Existing all-accepted reports remain:

- ETHUSD: `feature_family_frequency.csv`, `gate_frequency.csv`;
- MATB: `asset_frequency.csv`, `group_frequency.csv`, `module_frequency.csv`.

With `artifacts.frequency_analysis.enabled: true`, every enabled category also receives
`*_elite.csv` and, when requested, `*_final_generation.csv`. Elite trials are sorted according to
the declared objective direction and use
`min(n, max(elite_minimum_candidates, ceil(elite_fraction * n)))`. The final-generation cohort is
the accepted unique set at the maximum actual recorded generation, not the configured generation
budget.

Concretely, ETHUSD writes `feature_family_frequency_{elite,final_generation}.csv` and
`gate_frequency_{elite,final_generation}.csv`; MATB writes the corresponding
`asset_frequency_*`, `group_frequency_*`, and `module_frequency_*` files.

Other runtime artifacts include `search_manifest.json`, `evaluations.csv`,
`generation_summary.csv`, `failed_candidates.csv`, `candidate_configs/`, `best_candidates/`,
`promotion_report.csv`, and `promoted_candidates/` where enabled.

## Smoke budgets, persistence, and running later

Both checked-in searches are 16-candidate integration smoke searches: population 8, generations
2, seed 42, and one worker. They use persistent SQLite storage colocated with their archives and
`resume: true`. They are intended to validate integration and artifact semantics, not support a
research conclusion. Increase the budget only after validation, tests, and artifact inspection;
contract-compatible budget increases can resume the same study.

```bash
pytest -q tests/experiments/evolutionary

python -m src.experiments.evolutionary.cli \
  --spec config/evolutionary/ethusd_foundation/ga_ethusd_feature_gate_v1.yaml

python -m src.experiments.evolutionary.cli \
  --spec config/evolutionary/matb/ga_matb_asset_module_v1.yaml
```

Feature/gate and asset/module searches remain separate from exit optimization and broad numeric
parameter searches. This keeps decoder invariants auditable and limits simultaneous selection
pressure across discovery, execution, exits, and portfolio leverage.
