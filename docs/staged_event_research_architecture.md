# BTCUSD 1h Staged Event Research Architecture

## Scope

This design targets contrarian trading after causal BTCUSD 1h shock events. It is explicitly not a generic trend-confirmation pipeline.

The modeling ladder is:

1. Baseline handcrafted event features -> XGBoost meta-label classifier
2. Baseline features + transformer event embeddings -> XGBoost meta-label classifier
3. Baseline features + transformer embeddings + OOF event forecast probability -> XGBoost meta-label classifier

## Stage Design

### Event Detector Layer

- Uses `shock_context` to emit causal event columns such as `shock_candidate`, `shock_side_contrarian`, `shock_strength`, and `bars_since_shock`.
- The detector only uses current and historical bars. There is no symmetric peak/trough confirmation and no repainting logic.
- Downstream targets use `triple_barrier` with `side_col=shock_side_contrarian` and `candidate_col=shock_candidate`, so labeling and training happen on event rows.

### Pattern Encoder Layer

- Uses `event_transformer_encoder` as a model stage.
- Sequence windows are constructed from past-only bars and end exactly at the event timestamp.
- Train windows are constrained to the train fold through `allowed_window_indices`; test windows may use historical context from the train segment but never future bars.
- The stage emits OOF embedding columns such as `extrema_emb_00` ... `extrema_emb_07`.

### Forecast Layer

- Version 3 adds a separate event-conditioned OOF forecast stage.
- The recommended default is a barrier-success probability model on the contrarian side, not a generic trend forecast.
- Train predictions are OOF only and test predictions come from a model fit on the train fold only.

### Decision Layer

- The final `xgboost_clf` consumes handcrafted event features, optional transformer embeddings, and optional event forecast probability.
- The output is a take/skip probability for the contrarian trade after the shock.

## Leakage Controls

### Extrema and Shock Detection

- `shock_context` is based on rolling and lagged quantities only.
- The no-lookahead regression test mutates future bars and confirms earlier shock columns are unchanged.

### Pattern Windows

- Sequence construction uses `build_sequence_samples`, which ends each window at the target row.
- The event-transformer path further restricts train windows to train-fold indices only.

### OOF Stacking

- Upstream stages write predictions and embeddings only on their OOS test windows.
- Downstream stages train on rows where upstream OOF features exist; they never consume in-sample upstream outputs.

### Index Alignment

- Every stage writes outputs back on the original index.
- Event rows remain sparse; non-candidate rows keep `NaN` embeddings and forecast values.
- Stage metadata exposes `prediction_diagnostics.alignment_ok`.

## Evaluation Plan

Compare versions in order:

1. `btcusd_1h_staged_event_meta_v1.yaml`
2. `btcusd_1h_staged_event_meta_v2.yaml`
3. `btcusd_1h_staged_event_meta_v3.yaml`

Track:

- Gross and net PnL
- Cost drag
- Sharpe
- Drawdown
- Turnover
- Prediction coverage
- AUC, log loss, and Brier score
- Fold-by-fold stability
- PSI drift diagnostics when available

The incremental-value question is strict: keep the later stage only if it improves OOS behavior relative to the simpler version.
