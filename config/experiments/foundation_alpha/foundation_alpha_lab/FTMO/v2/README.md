# Foundation Alpha FTMO v2

This suite keeps the selected model07 alpha contract frozen and separates model work from exit/risk research.

## Reuse contract

- `00_ftmo_v2_train_and_cache_model07.yaml` is the only config that trains a model. It uses the frozen purged
  walk-forward split, installs the final-refit bundle at
  `logs/models/foundation_alpha/FTMO/v2/ftmo_v2_model07_vwap32_rov64_rz256.pkl`, and writes the historical
  walk-forward OOS frame to
  `data/processed/processed/ftmo_v2_model07_vwap32_rov64_rz256_anchor_aa1f56f9/dataset.csv`.
- `01` through `23` use `model.kind: none` and load that OOS frame. They do not fit LightGBM or any second model.
- The final-refit `.pkl` is for forward, paper, demo, or live inference after its training cutoff. It must not be
  replayed over its own training history. Historical comparisons use only the cached `pred_is_oos=true`
  walk-forward predictions.
- A missing cache is a hard failure. Run `00` once before running the cached matrix.

The promoted model currently comes from the selected run
`model07_vwap32_rov64_rz256_20260801_200744_865898_f136efc6`. Running `00` regenerates and replaces the stable
installed bundle from the declared anchor contract.

## Matrix

- `01`: cached vectorized parity/control.
- `02`-`11`: risk-per-trade and 4/5/6 ATR catastrophe-stop frontier.
- `12`-`13`: 16/32-bar time-exit ablation around the frozen 24-bar horizon.
- `14`: half risk for the next long after a completed stop.
- `15`: half risk for shorts in the diagnosed `close_over_ema_96` countertrend zone `[0.01, 0.023]`.
- `16`: half risk for longs signaled at 09:00 or 15:00 UTC.
- `17`-`19`: combined non-stacking/minimum and multiplicative soft-risk overlays.
- `20`-`21`: causal session-context hard filter for 12:00-18:00 UTC, alone and with soft overlays.
- `22`: harder alpha thresholds with the combined overlay.
- `23`: combined overlay under 32.5 bp assumed round-trip crossing cost.

The new `backtest.entry_risk_modifiers` rules are causal and can only multiply risk by a value in `[0, 1]`.
`combine: min` avoids compounding several 0.5 modifiers on the same candidate; `combine: multiply` is included as
a deliberate stress test.

## Execution order

Run the anchor once:

```bash
docker compose run --rm app python -m src.experiments.runner \
  config/experiments/foundation_alpha/FTMO/v2/00_ftmo_v2_train_and_cache_model07.yaml
```

Then run every cached experiment without retraining:

```bash
for cfg in config/experiments/foundation_alpha/FTMO/v2/{01..23}_*.yaml; do
  echo "================================================================"
  echo "Running: $cfg"
  echo "================================================================"
  docker compose run --rm app python -m src.experiments.runner "$cfg" || break
done
```

Selection should require, on common OOS coverage, at least 30% annualized return, mark-to-market maximum drawdown
at or below 5%, positive calendar-year consistency, acceptable trade count, and survival under the adverse-cost
run. These backtests are still not exact FTMO compliance emulation: account-wide Prague-time floating equity,
balance rules, swaps, pending orders, and hard flatten/lock behavior remain a separate live risk-control layer.
