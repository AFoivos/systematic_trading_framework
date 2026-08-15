# AR-0004 — Cross-Asset Walk-Forward Alpha Tournament

## Status and purpose

`AR-0004` is a cloud-scale, hash-bound `DISCOVERY` experiment. It is designed
to search aggressively while keeping the search, screening, cost, timing, and
candidate gates explicit. It cannot guarantee that an alpha exists. A run with
zero eligible candidates is a valid and scientifically useful outcome.

The experiment does not modify `AR-0001`, `AR-0002`, or the approved
`AR-0003`. Those research cycles are hypothesis-generation and architecture
context only; none of their results is validation or final evidence here.

The exact frozen hash was approved by Foivos Ampatzis on
`2026-08-15T19:36:44+03:00`. The YAML is `APPROVED_TO_RUN` for `DISCOVERY`
calculation only. All validation, final-evidence, canonical-backtest,
portfolio, promotion, and execution permissions remain disabled. The frozen
scientific hash is
`675bcf8d11e17203b66538b06392c974b0c02adb543866918e59f5d6827420d6`.

## Research question

The frozen hypothesis is that a pooled nonlinear model can rank a diversified
15-asset universe by future executable return using causal multi-horizon
momentum, path quality, volatility regime, and same-timestamp cross-sectional
features. A useful effect must survive later chronological screening folds,
observed bid/ask stress, temporal-stability gates, block-bootstrap uncertainty,
and global multiple-testing correction.

## Frozen data universe

The universe is the same 15-asset, 30-minute UTC Dukascopy source family bound
by SHA-256 in the YAML:

`AUS200`, `BRENT`, `ETHUSD`, `EU50`, `EURUSD`, `FRA40`, `GER40`,
`NIKKEI225`, `SPX500`, `UK100`, `US100`, `US30`, `USOIL`, `XAGUSD`,
`XAUUSD`.

The runtime verifies every source hash before parsing. Missing timestamps
remain absent. It performs no Cartesian densification, forward fill, backfill,
calendar substitution, or synthetic minute reconstruction. A feature or target
window crossing a non-30-minute transition remains missing.

## Feature ownership and causality

All features remain STF-owned and are available at `close[t]`. The base family
is:

- log returns at 16, 32, and 64 bars;
- path efficiency at 16, 32, and 48 bars;
- realized volatility at 16, 32, 64, and 192 bars;
- the 32/192 realized-volatility ratio.

The `full_cross_sectional` feature set adds only contemporaneous transforms:

- cross-sectional z-scores of the three momentum horizons;
- cross-sectional percentile ranks of path efficiency and the volatility ratio.

These transforms use only the observed assets at the same timestamp. They do
not fit a global scaler, use a future timestamp, fill a missing asset, or create
an independent Qlib/PyBroker feature universe. Missing required features are
dropped separately inside each model fold.

## Target and execution measurement

The model target is the framework-generated future executable long-coordinate
return at horizons 16 and 32. Information is known at `close[t]`, entry is at
`open[t+1]`, and exit is at `open[t+h+1]`. Observed bid/ask fields are required;
a mid-price or zero-cost fallback is forbidden.

Every fold removes training rows whose target horizon can touch the test
boundary. For horizon `h`, the safe training cutoff is before
`test_start - (h+1) × 30 minutes`. Models never see a label whose exit belongs
to the later fold.

## Search stage

Optuna TPE evaluates 384 model alternatives on four expanding tuning folds:

1. 2023 H1;
2. 2023 H2;
3. 2024 H1;
4. 2024 H2.

Every trial chooses one of four frozen feature sets, a 16- or 32-bar target,
and bounded LightGBM complexity/regularization parameters. The model is
retrained per fold with deterministic seeds and no shuffle. The objective is:

```text
mean fold rank IC
- 0.50 × fold IC dispersion
- 0.25 × negative-worst-fold penalty
```

This penalizes unstable trial performance rather than selecting the largest
single aggregate score. Median pruning begins only after the frozen startup and
warm-up requirements. Failed and pruned trials remain in search-breadth
artifacts.

Optuna uses only the tuning folds. It does not access any screening fold while
choosing parameters.

## Frozen screening family

After tuning, the top 24 complete trials are frozen. A twenty-fifth alternative
is an equal-weight ensemble of the top five finalists sharing the best tuning
horizon. These 25 alternatives are evaluated on three later expanding OOS
folds:

1. 2025 H1;
2. 2025 H2;
3. 2026 Q1 through 2026-04-28.

There are no fitted training predictions and no OOS backfill. Each stored row
records its fold, model-fit end timestamp, `is_oos=true`, and
`trained_without_this_row=true`.

The three screening folds are discovery-stage OOS evidence. Because their
results are used to select a candidate, they are not `VALIDATION` or
`PROSPECTIVE_FINAL` evidence.

## Predictive and economic diagnostics

Predictive diagnostics include mean and fold-level cross-sectional rank IC,
worst-fold IC, dispersion, positive-fold count, RMSE, prediction coverage, and
missing OOS rows.

The economic diagnostic ranks assets at each timestamp. The top 20% is measured
using the observed long executable return and the bottom 20% using the observed
short executable return. Both sides are recomputed at `1.50×` the observed
half-spread. Their sum is a directional tail diagnostic, not a shared-capital
portfolio return, equity curve, or canonical ledger.

Commission, slippage, funding/swap, capacity, and market impact are not silently
invented. A survivor still requires a separately frozen canonical validation
configuration containing those assumptions.

## Inference and multiple testing

Every one of the 25 screening alternatives remains in the binding family.
Invalid alternatives receive `p=1`. The rank-IC series is placed back onto the
unsqueezed 30-minute screening timeline before inference so missing market
timestamps do not become artificially adjacent observations.

The primary inference uses:

- Newey-West/Bartlett HAC lag 32;
- calendar-stratified, non-circular moving-block bootstrap;
- block length 32;
- 2,000 bootstrap resamples;
- global Benjamini-Yekutieli at FDR 5% over all 25 alternatives.

## Candidate gates

An alternative can be selected only when all of the following hold:

- at least 5,000 OOS prediction-eligible rows;
- at least 90% OOS prediction coverage;
- positive mean rank IC;
- positive rank IC in every one of the three screening folds;
- bootstrap lower confidence bound above zero;
- global BY adjusted p-value at most 0.05;
- positive top/bottom directional return under `1.50×` observed-spread stress;
- causal features, target-horizon purge, fold-safe preprocessing, and OOS-only
  provenance checks all pass.

Up to three eligible alternatives may be nominated. Each stops at
`PENDING_CANONICAL_VALIDATION` and receives a portable
`CanonicalValidationRequest`. No adapter or artifact may label it validated.

## Why VectorBT and PyBroker are not forced into this stage

VectorBT remains the appropriate adapter for finite single-asset vectorized
rule screening. The current adapter explicitly does not own multi-asset
shared-capital semantics. PyBroker remains the single-asset supervised
walk-forward screening adapter. Forcing either one into the pooled
cross-sectional model would create a false parity claim and duplicate the
STF-native R2 multi-asset contract.

If AR-0004 produces a survivor, its portable specification may be mapped into a
later, separately frozen single-asset threshold/timing screening run where
VectorBT or PyBroker has valid semantics. That later search consumes discovery
evidence and does not promote the candidate automatically.

## Resource envelope

The planned upper bounds are:

- 384 tuning trials;
- up to 1,536 tuning model fits before pruning;
- 25 screening alternatives;
- 72 finalist screening fits plus bounded selected-prediction reproduction;
- 1.5 million panel rows;
- four concurrent trials with one LightGBM thread each.

The recommended initial Lightning machine is 16 CPU cores and 64 GB RAM. GPU
is not required by the frozen implementation. The Optuna SQLite study is
resumable; the final run directory remains create-once and immutable.

## Stable command

With the exact hash-bound approval recorded, the stable command is:

```bash
mkdir -p logs/console
export PYTHONPATH="$PWD"
export PYTHONHASHSEED=7

python -m src.experiments.runner \
  config/research/alpha_discovery/AR-0004_cloud_alpha_tournament.yaml \
  2>&1 | tee logs/console/AR-0004-lightning-native.log
```

The runner accepts only the approved scientific hash. The approval enables
`runtime.perform_alpha_calculation` for `DISCOVERY` while all non-discovery
data roles, canonical validation, portfolio construction, promotion, and
execution remain fail-closed.

## Artifacts and interpretation

The immutable root is:

```text
logs/experiments/alpha_discovery/AR-0004/<specification-hash-prefix>/
```

It contains the resolved specification, verified source-quality report, panel
fingerprint, resumable Optuna study and trial table, all 25 screening trials,
fold/inference reports, selected OOS predictions, Phase 2 ranking/candidates,
canonical-validation requests, search breadth, and a run manifest containing
artifact hashes and Git provenance.

No artifact is authority to trade. A positive result means only that a
candidate survived this discovery tournament and is ready to be replayed under
the STF-owned canonical validation lifecycle.
