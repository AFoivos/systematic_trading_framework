# YAML-only FTMO risk overlay v2

Source model/config:
`config/experiments/foundation_alpha/best_runs/model06_vwap32_rz128_20260801_191133_164398_3475c432/config_used.yaml`

No Python source files are changed. Each YAML is fully self-contained.

## Files

- `00_scaled_0625_no_guard.yaml`: 62.5% exposure control, no guards.
- `01_balanced_0625_daily015_total080.yaml`: balanced candidate; 62.5% exposure, 1.0% soft stop, 1.5% hard daily stop, 8.0% total-loss and drawdown guards.
- `02_conservative_0600_daily015_total075.yaml`: conservative candidate with 60% exposure and 7.5% total/drawdown limits.
- `03_high_return_0750_daily020_total085.yaml`: higher-return candidate with 75% exposure, 2.0% hard daily stop and 8.5% total/drawdown limits.

## Important

The generic portfolio guard validates `timezone: Europe/Prague`, but the current generic vectorized guard groups days from the timestamp index. Verify the produced `risk_guard_timeline` before treating the reset as exact FTMO local-calendar behavior.
