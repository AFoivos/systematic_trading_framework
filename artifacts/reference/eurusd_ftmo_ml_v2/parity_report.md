# EURUSD FTMO ML v2 parity report

> Status: documented reconstruction; not an exact reproduction.

## Exactly recovered from artifacts

- None: no authoritative artifact was available at the configured source path.

## Reconstructed from documented formula

- Four independent pullback state machines and causal next-open execution.
- Session fade using the previous completed UTC daily EMA20 regime.
- Fixed 151-feature candidate matrix and three-model LightGBM ensemble.
- Annual OOS schedule, frozen 2025 holdout, confidence aggregation, and FTMO overlays.

## Inferred because the original source was not persisted

- Rolling-standard-deviation `ddof=1` where the brief does not declare a ddof.
- M30 open-to-open equity marking for the daily circuit-breaker approximation.
- Baseline-only cost-stress output when the reference stress grid is unavailable.

## Not reproducible from available artifacts

- Missing: `eurusd_30m.csv`
- Missing: `eurusd_ftmo_ml_v2_strategy_spec.json`
- Missing: `eurusd_ftmo_ml_v2_strategy.py`
- Missing: `eurusd_ftmo_ml_v2_model_bundle.joblib`
- Missing: `eurusd_ftmo_ml_v2_feature_dictionary.csv`
- Missing: `eurusd_ftmo_ml_v2_feature_importance.csv`
- Missing: `eurusd_ftmo_ml_v2_period_metrics.csv`
- Missing: `eurusd_ftmo_ml_v2_parameter_sensitivity.csv`
- Missing: `eurusd_ftmo_ml_v2_cost_stress.csv`
- Missing: `eurusd_ftmo_ml_v2_risk_scenarios.csv`
- Missing: `eurusd_ftmo_ml_v2_strategy_report.html`
- Missing: `eurusd_ftmo_strategy_spec.json`
- Missing: `eurusd_ftmo_ml_strategy_spec.json`
- Missing: `eurusd_ftmo_ml_strategy.py`
- Original full v2 research-generation source and annual fold models were not supplied.
- Candidate-level historical reference predictions and fixtures were not supplied.
- Full experiment completed: `false`.

Exact parity may only be claimed after candidate counts, model audit, and period metrics align within a declared tolerance.
No parameters are optimized to close a parity gap.
