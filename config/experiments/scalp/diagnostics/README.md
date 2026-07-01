# QFS Diagnostic Suite

This folder contains focused diagnostics for `quote_flow_proxy_scalp_meta_v1` on US100 30m data.

The suite keeps the target geometry fixed at `directional_triple_barrier`, `entry_price_mode: next_open`, `profit_barrier_r: 0.70`, `stop_barrier_r: 0.50`, and mostly `vertical_barrier_bars: 3`. The optional horizon checks use `vertical_barrier_bars: 2`.

## YAML Families

- `all_modes`: baseline with toxic continuation, liquidity sweep fade, and VWAP snapback enabled.
- `mode1_toxic`: only `signal_mode == 1`, toxic continuation.
- `mode2_sweep`: only `signal_mode == 2`, liquidity sweep fade.
- `mode3_vwap`: only `signal_mode == 3`, VWAP snapback.
- `modes12` and `modes23`: combined mode ablations.
- `thr040`, `thr046`, `thr048`, `thr050`: meta-probability threshold sensitivity on the all-modes setup.
- `spread075_z20` and `spread070_z18`: stricter spread filters.
- `ev005`: stricter expected-value filter via `min_expected_value_r: 0.05`.
- `h2`: small horizon check with `vertical_barrier_bars: 2`.

## Run Diagnostics

Run every diagnostic YAML:

```bash
./scripts/run_qfs_diagnostics.sh
```

Run only configs whose file name contains a substring:

```bash
./scripts/run_qfs_diagnostics.sh mode2
```

## Build Leaderboard

Print the top 30 QFS runs from `logs/experiments`:

```bash
python scripts/qfs_diagnostics_leaderboard.py
```

Choose root/top count and write CSV:

```bash
python scripts/qfs_diagnostics_leaderboard.py --root logs/experiments --top 30 --csv logs/experiments/qfs_diagnostics_leaderboard.csv
```

## Metrics To Inspect First

- `net_pnl`
- `gross_pnl`
- `total_cost`
- `cost_to_gross_pnl`
- `profit_factor`
- `sharpe`
- `max_drawdown`
- `executed_trade_count`
- model `roc_auc`
- model `accuracy`

Do not select only the best `net_pnl`. Prefer stable behavior with enough trades, tolerable drawdown, and low cost drag.
