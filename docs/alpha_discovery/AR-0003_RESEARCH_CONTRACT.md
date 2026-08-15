# AR-0003 — Multi-Horizon Trend Quality × Volatility Regime

## Status

`AR-0003` is an approval- and specification-hash-bound, executable
`DISCOVERY` experiment. Its hash is
`459f9bc8411843dfee1c6d352dc2a4b01115ea379ada87ed38422cc5660048e0`.
It is screening-only: no result is canonical validation, a portfolio backtest,
or authority for paper/demo/live execution. `AR-0001` and `AR-0002` are not
modified.

## 1. Frozen hypothesis

Across the frozen multi-asset universe, assets with directionally consistent
16/32/64-bar momentum, high 16/32/48-bar path efficiency, and non-extreme
realized volatility are hypothesized to have stronger same-direction future
executable returns over 16–32 bars. The primary preregistered member uses a
32-bar horizon, a 0.70 path-efficiency percentile, and a 0.20–0.80 volatility
percentile interval.

Previous STF conditional-effect outputs are hypothesis-generation evidence
only. They are not independent validation or final evidence for `AR-0003`.

## 2. Data and evidence roles

All 15 source files and their SHA-256 values are frozen in the YAML. The runner
verifies every hash before loading data and builds two STF-owned R1
`PanelResearchDataset` values in memory. The chronological segments are:

- `TRAINING`: `[2020-01-06, 2024-01-01)`;
- `TUNING`: `[2024-01-01, 2025-01-01)`;
- `SCREENING`: `[2025-01-01, 2026-04-28)`.

Every segment remains `DISCOVERY`. The names `SCREENING` and “OOS” do not turn
these data into `VALIDATION` or `PROSPECTIVE_FINAL` evidence. The deterministic
primary score is evaluated only on prediction-eligible `SCREENING` rows.

## 3. Frozen asset universe

The universe is `AR-0003-DUKASCOPY-15-ASSET-30M-V1`:

`AUS200`, `BRENT`, `ETHUSD`, `EU50`, `EURUSD`, `FRA40`, `GER40`,
`NIKKEI225`, `SPX500`, `UK100`, `US100`, `US30`, `USOIL`, `XAGUSD`,
`XAUUSD`.

The source contract is `OBSERVED_PROVIDER_30M_BARS_NO_MINUTE_RECONSTRUCTION`.
Raw gaps remain gaps. No Cartesian densification, forward fill, backfill, or
calendar substitution is performed. Any feature or target window crossing a
non-30-minute transition is missing and ineligible. This contract does not
claim exact reconstruction from 30 observed one-minute candles.

## 4. Feature definitions

Features are computed independently per asset and are available at
`close[t]`:

- log return over 16, 32, and 64 bars;
- path efficiency over 16, 32, and 48 bars;
- realized volatility as the square root of the sum of squared one-bar log
  returns over 16, 32, 64, and 192 bars;
- `volatility_ratio_32_192 = RV32 / RV192`.

All rolling windows require exact 30-minute continuity. Missing values remain
missing; there is no imputation or globally fitted preprocessing.

## 5. Target and causal timing

For horizon `h`, information is available at `close[t]`, entry is at
`open[t+1]`, and exit is at `open[t+h+1]`. The base long coordinate used for
cross-sectional rank IC is:

```text
bid_open[t+h+1] / ask_open[t+1] - 1
```

The corresponding short executable diagnostic is:

```text
(bid_open[t+1] - ask_open[t+h+1]) / bid_open[t+1]
```

The same-direction return selects the long value for a non-negative score and
the short value for a negative score. No same-close fill and no zero-cost
fallback exist. A target is missing if the entire future bar path is not
30-minute-contiguous.

## 6. Primary alpha score and regime

At each timestamp, population z-scores (`ddof=0`) are computed only across
currently observed assets. At least five finite assets are required.

```text
trend_score = median(
    zscore_cs(log_return_16),
    zscore_cs(log_return_32),
    zscore_cs(log_return_64)
)

quality_score = median(
    path_efficiency_16,
    path_efficiency_32,
    path_efficiency_48
)

alpha_score = trend_score * quality_score
```

At least two momentum horizons must have the same non-zero direction. The
primary regime requires `quality_score` percentile `>= 0.70` and an inclusive
`volatility_ratio_32_192` percentile in `[0.20, 0.80]`, using average-tie ranks
within the same timestamp. No future row enters either percentile.

## 7. Cross-sectional evaluation

At every eligible screening timestamp, the run records individual asset
scores and evaluates mean/median Spearman rank IC, IC dispersion, positive-IC
period count, top/bottom 20% executable-target means, and their spread. It also
writes per-asset coverage/predictive diagnostics and calendar-year stability.
Top-minus-bottom is a prediction diagnostic only; it is not a shared-capital
portfolio return.

## 8. Costs

The base cost uses the observed entry/exit bid and ask. Cost stress widens each
observed half-spread deterministically by `1.00×`, `1.25×`, and `1.50×` before
recomputing long and short executable returns. These are directional screening
diagnostics, not a portfolio ledger. Commission, funding, slippage, or other
costs are not silently invented.

## 9. Inference and multiple testing

The full deterministic family has 12 variants:

```text
PE percentile:       0.60, 0.70, 0.80
volatility interval: 0.10–0.90, 0.20–0.80
forward horizon:     16, 32
```

The primary member is evaluated first. Every variant, including invalid ones,
remains in the family. Rank IC is placed back on the unsqueezed 30-minute
screening timeline. Inference uses Newey–West with lag 32 and a calendar-year
stratified, non-circular moving-block bootstrap with block length 32, 1,000
resamples, 95% confidence, and deterministic per-hypothesis seeds. The binding
correction is global Benjamini–Yekutieli at FDR 0.05 over all 12 members; an
invalid member receives raw `p=1.0`. At least 500 finite rank-IC periods are
required per variant. Discovery eligibility requires a positive mean rank IC,
a bootstrap lower confidence bound above zero, and passage of the global BY
gate. Eligibility still does not promote a candidate automatically.

## 10. Optional LightGBM extension

The existing framework-owned `MultiAssetSearchExecutor` remains available for
a separately approved LightGBM search, but it is disabled in this run. It is
not part of the 12-member deterministic family and cannot replace the primary
preregistered test. Enabling it would create separate search breadth and a new
scientific hash.

## 11. Resource and safety contract

The frozen caps are 100 assets, 1,500,000 panel rows, 12 deterministic variants,
and zero model fits. Resource checks occur after verified source loading and
before alpha evaluation. The run does not construct a portfolio, run the
canonical backtester, access validation/final evidence, promote a candidate,
or contact a broker.

## 12. Exact command

From the repository root in Lightning AI Studio:

```bash
mkdir -p logs/console
export PYTHONPATH="$PWD"
export PYTHONHASHSEED=7

python -m src.experiments.runner \
  config/research/alpha_discovery/AR-0003_multi_asset_trend_quality.yaml \
  2>&1 | tee logs/console/AR-0003-lightning-native.log
```

The runner refuses before alpha calculation if the approval hash, source hash,
schema, universe, cost/timing policy, resource cap, or immutable output path
does not match the contract.

## 13. Artifacts

The immutable run root is:

```text
logs/experiments/alpha_discovery/AR-0003/459f9bc8411843df/
```

It contains:

- `run_manifest.json`;
- `contracts/resolved_specification.yaml`;
- `datasets/panel_h16_metadata.json` and `panel_h32_metadata.json`;
- `data_quality/source_quality.json`;
- `predictions/primary_score_predictions.csv.gz`;
- `reports/cross_sectional_diagnostics.json`;
- `reports/per_asset_diagnostics.json`;
- `reports/temporal_stability.json`;
- `reports/robustness_family.json`;
- `reports/search_breadth.json`.

The full derived panels are fingerprinted but not duplicated to disk. Their
metadata and fingerprints are immutable artifacts; the inputs remain the
frozen source CSVs.

## 14. Approval and interpretation

The YAML is `APPROVED_TO_RUN`, and `approved_specification_hash` exactly matches
the scientific hash above. Approval authorizes this discovery measurement only.
It does not approve a strategy, canonical validation, portfolio allocation, or
execution. Any material change to data, universe, feature/target semantics,
timing, costs, inference, thresholds, or family breadth creates a new hash and
requires new approval. Any later candidate remains at most
`PENDING_CANONICAL_VALIDATION`, with canonical validation STF-owned.
