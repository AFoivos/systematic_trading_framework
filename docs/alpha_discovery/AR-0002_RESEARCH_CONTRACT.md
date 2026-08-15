# AR-0002 — Spread-aware longer-horizon ETHUSD discovery

## Status

`AR-0002` is a `SPECIFICATION_ONLY` discovery experiment until a human approves
the exact checked-in scientific hash. It cannot access data or calculate effects
in this state. Approval metadata and `runtime.perform_alpha_calculation` are
workflow fields and do not change the scientific hash.

This experiment does not modify, supersede, or validate `AR-0001`.

## Why this is a new discovery experiment

The inspected `AR-0001` discovery artifacts contained 3,792 preregistered
effects. No positive executable-return effect passed global BY, bootstrap-CI,
and frozen-period temporal-stability gates. Observed bid/ask costs eliminated
most positive raw conditional returns, while the remaining positive indications
were concentrated at longer horizons.

Those observations are development evidence. `AR-0002` therefore records the
three source artifact hashes and declares its use as
`POST_HOC_HYPOTHESIS_GENERATION_ONLY`. It reuses already inspected `DISCOVERY`
data and can never describe its output as validation, an untouched holdout, or
prospective-final evidence.

## Falsifiable hypothesis

At ETHUSD 30-minute frequency, conditional directional returns may exceed the
observed bid/ask burden only at 16-, 32-, or 64-bar horizons and only in states
jointly defined by decision-time spread and a small frozen set of trend or
volatility measurements available at `close[t]`.

The hypothesis is rejected for candidate purposes if no positive effect passes
all of the following:

1. Full eligibility and coverage gates.
2. Global Benjamini–Yekutieli at 5% over all 720 preregistered effects.
3. Primary segmented moving-block bootstrap confidence interval excluding zero.
4. Positive sign in all six frozen calendar periods, with at least 30 observations
   in every period.
5. Mean executable return of at least `0.001` (10 bps) after observed bid/ask
   spread.

Negative statistically significant effects remain diagnostics and cannot pass
the binding candidate screen.

## Frozen feature and condition universe

The continuous feature columns are:

- `log_return_48`
- `path_efficiency_48`
- `realized_volatility_48`
- `spread_fraction`

`spread_fraction` is the canonical same-bar close spread divided by the same-bar
mid close. It is read directly from the validated quote contract, becomes
available at `close[t]`, and is never imputed, globally normalized, or fitted
using future rows.

Every continuous feature uses discovery-fitted quintiles. The edges are frozen,
hash-bound to the specification and discovery snapshot, and can later only be
applied—not refitted—outside discovery.

The experiment includes 20 one-dimensional states and exactly four
two-dimensional interaction families:

- `log_return_48 × spread_fraction`
- `path_efficiency_48 × spread_fraction`
- `realized_volatility_48 × spread_fraction`
- `path_efficiency_48 × realized_volatility_48`

Each pair contributes 25 quintile combinations. Therefore:

```text
20 one-dimensional states
+ 4 × 25 two-dimensional states
= 120 conditions

120 conditions × 3 horizons × 2 directions
= 720 preregistered effects
```

There are no arbitrary pairings, three-dimensional states, threshold search,
model fitting, signal optimization, stop-loss search, or backtests.

## Timing and costs

The state is observed at `close[t]`. Entry is at `open[t+1]` and exit at
`open[t+h+1]`.

- Long: buy actual ASK at entry and sell actual BID at exit.
- Short: sell actual BID at entry and cover actual ASK at exit.

The discovery cost scope remains `OBSERVED_BID_ASK_SPREAD_ONLY`. Commission,
slippage, swap, and latency are not silently invented. A surviving candidate
still requires separate cost assumptions and canonical STF validation.

## Statistical contract

The primary estimator remains the conditional-mean-ratio HAC estimator with
Newey–West/Bartlett lag 48. Lags 96 and 192 are non-binding diagnostics.

The primary bootstrap remains full-timeline, non-circular, gap-aware,
calendar-stratified segmented moving block with block length 48 and 2,000
resamples. Block lengths 96 and 192 are non-binding diagnostics. The AR-0002
deterministic bootstrap seed is 29.

Failed or ineligible hypotheses remain in the global family with `p=1`. Local
BH/BY and global BH remain diagnostics. Global BY over all 720 hypotheses is the
binding multiple-testing gate.

## Evidence boundary and next stage

An `AR-0002` survivor is only a discovery-stage conditional effect. It is not a
signal, strategy, validated candidate, or live-trading authorization.

VectorBT or PyBroker may consume a frozen survivor in a later, explicitly
declared screening stage. Their results remain discovery evidence and can at
most nominate a `ResearchCandidate` with
`PENDING_CANONICAL_VALIDATION`. Canonical validation remains STF-owned.

The historical pseudo-OOS partition is not automatically accessed by this
pipeline and cannot become prospective-final evidence.
