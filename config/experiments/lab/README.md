# Feature / Signal / Target Lab

`feature_signal_target_lab.yaml` is a runnable single-asset visual EDA config with no model
training stage:

- feature steps controlled by `features[].enabled`
- signal variants controlled by `signals_catalog.*.enabled`
- target variants controlled by top-level `targets_catalog.*.enabled`

Signal and target catalog entries are optional: enable zero or one signal and zero or one
target. With zero enabled signals, the loader emits a flat zero signal at `backtest.signal_col`
so the runner can still produce artifacts for feature-only EDA. Keep the selected signal aligned
with `backtest.signal_col` when you want trade diagnostics. Experiment artifacts are written
under `logs/experiments/lab/<run_name>_<timestamp>_<id>/`, including the interactive Plotly
diagnostics HTML in `report_assets/`.
