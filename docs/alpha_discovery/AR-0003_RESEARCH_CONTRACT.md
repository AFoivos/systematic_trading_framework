# AR-0003 — Multi-Horizon Trend Quality × Volatility Regime

## Status

`AR-0003` is implemented as a hash-bound `SPECIFICATION_ONLY` research
contract. The deterministic primary-score primitive and fail-closed stable
runner boundary exist, but a real experiment is deliberately blocked. The
repository currently contains no canonical multi-asset research universe or
validated `DISCOVERY` `PanelResearchDataset`; the available immutable research
snapshots are ETHUSD-only.

Raw multi-asset CSV files are not silently promoted to canonical research
snapshots. `AR-0001` and `AR-0002` are not modified.

## 1. Frozen hypothesis

Across a future explicitly bound canonical multi-asset universe, assets with
directionally consistent 16/32/64-bar momentum, high 16/32/48-bar path
efficiency, and non-extreme realized volatility are hypothesized to have
stronger same-direction future executable returns over 16–32 bars. The primary
preregistered horizon is 32 bars.

Previous STF conditional-effect outputs are hypothesis-generation evidence
only. They are not independent validation or final evidence for `AR-0003`.

## 2. Data and evidence roles

The intended input is the Phase 3C-R1 STF-owned `PanelResearchDataset` with
canonical row identity `(timestamp, asset_id)`, immutable source snapshot
fingerprints, explicit `TRAINING`, `TUNING`, and `SCREENING` segments, and
`DISCOVERY` evidence role.

The deterministic primary score needs no model fit, but its evaluation still
uses eligible `SCREENING` rows only. The optional LightGBM extension may fit on
purged chronological `TRAINING/TUNING` rows and emit true OOS `SCREENING`
predictions through the existing Phase 3C-R2 executor. Neither path may access
`VALIDATION`, `HISTORICAL_PSEUDO_OOS`, or `PROSPECTIVE_FINAL` in this research
cycle.

## 3. Asset universe

The asset universe is intentionally recorded as
`CANONICAL_MULTI_ASSET_UNIVERSE_UNRESOLVED`, with no fabricated asset IDs. A
ready universe must contain at least five explicit, sorted STF asset IDs, use
30-minute UTC observations, and be exactly matched by the validated panel
metadata.

Missing asset/timestamp observations remain absent. No Cartesian densification,
forward fill, backfill, or calendar substitution is permitted.

## 4. Feature definitions

All inputs are framework-owned feature outputs available at `close[t]`:

- momentum: `log_return_16`, `log_return_32`, `log_return_64`;
- path efficiency: `path_efficiency_16`, `path_efficiency_32`,
  `path_efficiency_48`;
- realized volatility: `realized_volatility_16/32/64/192`;
- primary volatility ratio: `realized_volatility_32 /
  realized_volatility_192`.

A non-positive or missing slow-volatility denominator yields a missing ratio.
Missing features stay missing and make the row ineligible; there is no
imputation.

## 5. Target definition

The primary target is a framework-owned 32-bar executable return whose
direction follows the sign of `alpha_score`. The required information and price
mapping is:

```text
features known at close[t]
entry at open[t+1]
exit at open[t+h+1], h=32
observed bid/ask sides required
```

The repository does not yet have this target bound to a validated multi-asset
panel. Therefore `panel_mapping_status=UNAVAILABLE` is a binding blocker. A
mid-price or zero-cost substitute is not accepted.

## 6. Causal timing

Per-asset rolling features may use only observations through `t`.
Cross-sectional transforms use only the observed assets at the same timestamp
`t`; they never fit on or inspect a later timestamp. The decision cannot fill at
the same close. Target horizon overlap must be purged before any optional model
fit.

## 7. Primary alpha-score formula

At each timestamp, population z-scores (`ddof=0`) are computed across observed
assets. At least five finite assets are required; a constant cross-section is
missing.

```text
trend_score = median(
    cross_sectional_zscore(log_return_16),
    cross_sectional_zscore(log_return_32),
    cross_sectional_zscore(log_return_64)
)

quality_score = median(
    path_efficiency_16,
    path_efficiency_32,
    path_efficiency_48
)

alpha_score = trend_score * quality_score
```

At least two of the three raw momentum horizons must have the same non-zero
direction. Zero is neutral. The deterministic implementation is
`src.research.trend_quality.build_multi_horizon_trend_quality_score`.

## 8. Volatility-regime policy

The primary regime uses deterministic average-tie percentile ranks within the
same contemporaneous cross-section:

- `quality_score` percentile is at least 0.70;
- `volatility_ratio_32_192` percentile is inclusively between 0.20 and 0.80;
- at least five finite observed assets are required.

This explicitly selects the cross-sectional interpretation of the prompt's
rolling/cross-sectional choice. It uses no future row and introduces no fitted
global percentile state.

## 9. Cross-sectional evaluation

At each eligible `SCREENING` timestamp, assets are ranked by `alpha_score`, with
`asset_id` as deterministic tie-breaker. Top and bottom 20% target diagnostics
are retained together with every individual asset prediction/score.

The planned metrics are mean and median Spearman rank IC, IC dispersion,
positive-IC-period ratio, top and bottom executable target means, their spread,
per-asset coverage and predictive metrics, and temporal stability. The
top-minus-bottom spread is a prediction-target diagnostic, not a shared-capital
portfolio return or canonical backtest.

## 10. Cost semantics

Base evaluation requires the canonical observed bid/ask mapping. Stress levels
are `1.00×`, `1.25×`, and `1.50×` only after the panel cost contract proves how
that multiplication applies. Commission, slippage, funding, or synthetic costs
are not invented. Turnover/cost diagnostics are permitted only when their
units and non-portfolio interpretation are explicit.

## 11. Multiple-testing family

The deterministic family contains all 12 combinations of the three path-
efficiency thresholds, two volatility intervals, and two horizons. Failed and
invalid alternatives remain in search-breadth accounting. The primary
preregistered member is `(0.70, 0.20–0.80, h=32)`.

The binding correction method is deliberately unresolved. It must be frozen
before approval; the framework will not borrow the AR-0001/AR-0002 correction
mechanically without an appropriate statistical design for these dependent
rank diagnostics.

## 12. Temporal-stability policy

Results are first separated by the dataset's explicit temporal segments and
then by calendar year where supported. Every period reports `n`, mean signed
executable return, rank IC, coverage, and hit rate where meaningful. Positive
aggregate performance cannot compensate for unreported or unstable periods.
A minimum-period gate will be bound only after the real dataset boundaries are
known.

## 13. Robustness family

Robustness is evaluated only after the primary member:

```text
PE percentile:       0.60, 0.70, 0.80
volatility interval: 0.10–0.90, 0.20–0.80
forward horizon:     16, 32
total:               3 × 2 × 2 = 12
```

Inspecting this family consumes discovery evidence. Any material change to the
feature, target, score, regime, cost, timing, or promotion contract starts a
new research cycle and produces a new hash.

## 14. Optional LightGBM extension

The extension is disabled by default and remains separate from the primary
test. If enabled later, it must use the existing framework
`lightgbm_regressor` and `MultiAssetSearchExecutor`, train-only preprocessing,
chronological purge, deterministic seeds, true OOS `SCREENING` predictions,
and independent search-breadth accounting. It cannot replace or retroactively
reinterpret the preregistered deterministic result.

## 15. Resource estimate

The deterministic score requires no model fit and has 12 bounded variants. Its
dominant cost is approximately linear in panel rows plus per-timestamp
cross-sectional sorting/ranking. The current caps are 100 assets, 1,000,000
rows, and 12 deterministic variants.

An exact row count, memory estimate, prediction-record count, and optional
LightGBM fit count cannot be reported before the universe and panel are bound.
The resource preflight must pass before data evaluation or model fitting.

## 16. Exact run command

The stable command is reserved as:

```bash
python -m src.experiments.runner \
  config/research/alpha_discovery/AR-0003_multi_asset_trend_quality.yaml
```

In the checked-in state it must fail before data access with
`SPECIFICATION_ONLY`. It is not currently an instruction to run the experiment.
There is no legitimate command that bypasses the missing universe, panel,
target/cost, statistical, resource, and approval gates.

## 17. Exact artifact locations

No result artifacts exist yet. Once an execution implementation and all gates
are approved, the immutable root is planned as:

```text
logs/experiments/alpha_discovery/AR-0003/<run-id>/
```

The specification reserves the manifest, resolved contract, panel metadata,
portable primary score records, cross-sectional diagnostics, per-asset
diagnostics, temporal stability, robustness family, and search-breadth files.
Native model objects and portfolio artifacts are not part of this contract.

## 18. Approval and hash status

The YAML stores a deterministic scientific hash while excluding mutable
workflow approval metadata, status, blockers, and the calculation switch from
the scientific digest. Human approval must bind the exact final complete hash.

The current hash is not approvable for execution because material bindings are
explicitly unresolved. Completing any of those fields changes the scientific
hash and requires a fresh review. No candidate can exceed
`PENDING_CANONICAL_VALIDATION`; canonical validation remains STF-owned, and no
paper/demo/live or portfolio action is authorized.
