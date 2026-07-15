# ETHUSD Trial 0041 Alpha Research Lab

This is a controlled, baseline-centred research lab around Trial 0041. It does not reuse a
previous leaderboard as a selection source. The historical artifact is used only for baseline
provenance and descriptive diagnostics.

## Provenance and split discipline

- Immutable source: `config/experiments/foundation_alpha/BEST/ethusd/optuna_BEST_ethusd_30m_lightgbm_h24_structured_tail_alpha_v3_7_ehlers_trend_hybrid.yaml`.
- Exact copy: `00_baseline/ethusd_30m_trial_0041_baseline.yaml`.
- Local replay: `00_baseline/ethusd_30m_trial_0041_baseline_local_replay.yaml`. It changes only
  `/workspace` paths and disables duplicate processed snapshots; its trading semantics remain the
  source baseline.
- Screening uses the source purged expanding folds 0--9 only (through 2024-09-17).
- Folds 10--16 (2024-09-17 through 2026-06) are the locked continuation. They are opened only
  after finalist YAMLs are frozen and are reported separately.

The vectorized runner applies a one-bar-lagged close-return exposure, not an explicit next-open
fill. Final reports therefore treat quote-cost and delay checks as mandatory blockers for any
paper-trading claim.

## Matrix

| Family | YAMLs |
|---|---:|
| Baseline local replay | 1 |
| Target lab | 10 |
| Feature ablation | 10 |
| Feature additions | 12 |
| Normalization | 6 |
| Signal lab | 10 |
| Model lab | 6 |

## Reproducible sequence

```bash
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py generate
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py validate
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py diagnostics
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py screen
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py finalists
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py locked
PYTHONHASHSEED=7 python scripts/run_trial0041_alpha_lab.py report
```

`07_combined_finalists` is generated only from the screening leaderboard. `08_stress_validated`
contains no YAML unless a frozen finalist passes the stated locked-fold and execution stresses.
