# FTMO Triple Barrier Upgrade Review

## 1. Executive Summary

Η αναβάθμιση επεκτείνει το υπάρχον FTMO intraday FX pipeline χωρίς να αντικαθιστά το framework. Το βασικό αποτέλεσμα είναι ότι τα classifier experiments μπορούν πλέον να χρησιμοποιούν `model.target.kind: triple_barrier` με asymmetric TP/SL barriers, αυστηρό `neutral_label: lower`, `tie_break: lower`, προαιρετικό `entry_price_mode: next_open`, meta-labeling και R-multiple target columns.

Προστέθηκαν:

- routing και metadata για `triple_barrier` targets στο classifier/forecaster target pipeline
- asymmetric `upper_mult` / `lower_mult` με reportable barrier counts
- `entry_price_mode: current_close | next_open`
- `label_mode: binary | ternary | meta`
- `add_r_multiple`, `tb_event_r`, `tb_oriented_r`, optional clipping
- meta-labeling με side-aware `profit` / `stop` barriers, `side_col`, `candidate_col`, `label_candidate`, `label_meta_side`, `label_oriented_ret`
- `meta_probability_side` signal για meta success probabilities χωρίς opposite trades
- FTMO risk-per-trade sizing μέσω `risk.sizing.kind: ftmo_risk_per_trade` και `confidence_mode`
- portfolio guard extensions για daily soft stop, daily hard stop, weekly profit lock και drawdown sizing
- sparse execution diagnostics στο report: `flat_rate`, `long_rate`, `short_rate`, `trade_rate`, `signal_turnover`, executed trade metrics
- report section για triple-barrier target diagnostics και R diagnostics
- config-controlled drift warning surface μέσω `feature_selectors.drift_filter`
- δύο νέα FTMO example configs
- unit tests για target behavior, next-open alignment, meta-labeling, R multiples, FTMO sizing και guard behavior

Σκόπιμα δεν άλλαξαν:

- τα defaults των παλιών `forward_return` targets
- οι split/purge/trim semantics
- η βασική data-loading αρχιτεκτονική
- τα υπάρχοντα `compute_vol_target_leverage` / `scale_signal_by_vol`
- same-run feature dropping βάσει OOS drift, επειδή θα μπορούσε να εισάγει lookahead. Το `drop` action καταγράφεται ως μη εφαρμοζόμενο στο ίδιο evaluated fold.

## 2. Changed Files

| File | Type of change | Purpose |
| ---- | -------------- | ------- |
| `src/targets/triple_barrier.py` | modified | Added `entry_price_mode`, `label_mode`, R multiples, richer metadata |
| `src/models/classification.py` | modified | Preserves target metadata and excludes emitted target columns from features |
| `src/models/forecasting.py` | modified | Allows regression forecasters to select a triple-barrier emitted target column |
| `src/models/runtime.py` | modified | Accepts and reports `feature_selectors.drift_filter` |
| `src/risk/position_sizing.py` | modified | Added `scale_signal_for_ftmo` |
| `src/risk/__init__.py` | modified | Exported FTMO sizing helper |
| `src/portfolio/construction.py` | modified | Added pre-sized exposure construction, soft/hard stops, weekly lock, drawdown sizing |
| `src/portfolio/__init__.py` | modified | Exported pre-sized exposure construction helper |
| `src/experiments/orchestration/backtest_stage.py` | modified | Wired `risk.sizing.kind: ftmo_risk_per_trade` into single-asset and portfolio backtests |
| `src/experiments/orchestration/model_stage.py` | modified | Aggregates target metadata across assets |
| `src/experiments/orchestration/pipeline.py` | modified | Passes `backtest_cfg` into evaluation for signal diagnostics |
| `src/experiments/orchestration/reporting.py` | modified | Adds target diagnostics, signal execution diagnostics, drift warnings |
| `src/signals/forecast_signal.py` | modified | Allows `vol_target: null`, adds optional causal top-quantile gating |
| `src/signals/probability_vol_adjusted_signal.py` | modified | Passes new probability signal params through registry wrapper |
| `src/signals/meta_probability_side_signal.py` | new | Converts meta success probability and primary side into same-side-only signals |
| `src/utils/config_defaults.py` | modified | Adds explicit default containers for `risk.sizing` and `risk.drawdown_sizing` |
| `src/utils/config_schemas.py` | modified | Adds typed risk schema fields for sizing and drawdown sizing |
| `src/utils/config_validation.py` | modified | Validates new target, signal, risk, guard and drift-filter config keys |
| `config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1.yaml` | new | FTMO 4-pair XGBoost meta-labeling config |
| `config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_conservative_v1.yaml` | new | Conservative FTMO 4-pair XGBoost binary target config |
| `tests/test_ftmo_triple_barrier_upgrade.py` | new | Unit tests for target upgrade and FTMO sizing |
| `tests/test_portfolio.py` | modified | Added guard tests for soft stop, hard stop and weekly lock |
| `docs/reports/ftmo_triple_barrier_upgrade_review.md` | new | This external review report |

## 3. Target Pipeline Integration

Το classifier target routing υπήρχε ήδη ως stable facade και παραμένει backward-compatible: αν το YAML δεν ορίσει `target.kind`, χρησιμοποιείται `forward_return`. Αν ορίσει `triple_barrier`, καλείται ο triple-barrier builder.

```text
File: src/targets/classifier.py
Purpose: Parse target.kind and route to the correct target builder.
```

```python
def build_classifier_target(
    df: pd.DataFrame,
    target_cfg: dict[str, Any] | None,
) -> tuple[pd.DataFrame, str, str, dict[str, Any]]:
    cfg = dict(target_cfg or {})
    kind = str(cfg.get("kind", "forward_return"))
    if kind == "forward_return":
        return build_forward_return_target(df=df, target_cfg=cfg)
    if kind == "triple_barrier":
        return build_triple_barrier_target(df=df, target_cfg=cfg)
    raise ValueError(f"Unsupported target.kind: {kind}")
```

Στο classifier training, το target builder επιστρέφει `out`, `label_col`, `fwd_col`, `target_meta`. Το `target_meta` αποθηκεύεται αυτούσιο στο model metadata και καταλήγει στα artifacts/report.

```text
File: src/models/classification.py
Purpose: Build selected target, infer features, preserve target metadata.
```

```python
target_cfg = model_cfg.get("target", {}) or {}
out, label_col, fwd_col, target_meta = build_classifier_target(df=work_df, target_cfg=target_cfg)

target_output_cols = set(str(col) for col in list(target_meta.get("output_cols", []) or []))
feature_cols = infer_feature_columns(
    out,
    explicit_cols=model_cfg.get("feature_cols"),
    feature_selectors=model_cfg.get("feature_selectors"),
    exclude={label_col, fwd_col, pred_prob_col, *target_output_cols},
)
feature_cols = [col for col in feature_cols if col not in target_output_cols]
```

Το metadata που γράφεται στο τέλος του classifier training περιλαμβάνει πλέον το πραγματικό target. Αυτό είναι το πεδίο που χρησιμοποιεί το report για να μη δείχνει πλέον `forward_return` όταν το config ζητά `triple_barrier`.

```text
File: src/models/classification.py
Purpose: Persist selected target metadata in model_meta.
```

```python
meta = {
    "model_kind": model_kind,
    "runtime": runtime_meta,
    "feature_cols": feature_cols,
    "pred_prob_col": pred_prob_col,
    "label_col": label_col,
    "fwd_col": fwd_col,
    ...
    "target": target_meta,
    "returns_col": returns_col,
    "overlay": overlay_meta,
    "contracts": contract_meta,
}
```

## 4. Triple-Barrier Target Behavior

Η υλοποίηση παραμένει στο `src/targets/triple_barrier.py` και επεκτάθηκε τοπικά. Τα νέα config keys είναι:

- `entry_price_mode: current_close | next_open`
- `label_mode: binary | ternary | meta`
- `add_r_multiple`
- `r_col`
- `oriented_r_col`
- `r_clip`

```text
File: src/targets/triple_barrier.py
Purpose: Parse new triple-barrier target options while preserving defaults.
```

```python
entry_price_mode = str(cfg.get("entry_price_mode", "current_close"))
raw_label_mode = cfg.get("label_mode")
label_mode = str(raw_label_mode if raw_label_mode is not None else ("meta" if side_col is not None else "binary"))
add_r_multiple = bool(cfg.get("add_r_multiple", False))
r_col = str(cfg.get("r_col", "tb_event_r"))
oriented_r_col = str(cfg.get("oriented_r_col", "tb_oriented_r"))
r_clip = _parse_r_clip(cfg.get("r_clip"))
```

Το `next_open` χρησιμοποιεί `open[start_idx + 1]` ως entry price. Το scan ξεκινά από το επόμενο bar και τα tail rows χωρίς πλήρη vertical horizon μένουν `NaN`.

```text
File: src/targets/triple_barrier.py
Purpose: Entry alignment without using unavailable tail rows.
```

```python
if start_idx >= full_horizon_cutoff:
    continue

entry_idx = start_idx if entry_price_mode == "current_close" else start_idx + 1
if entry_idx >= len(out):
    continue

entry_price = float(prices[start_idx] if entry_price_mode == "current_close" else opens[entry_idx])
```

Τα barrier counts μετρώνται πλέον ως actual barrier outcomes, ενώ τα neutral events μετρώνται χωριστά. Αυτό αποφεύγει να συγχέεται το `neutral_label: lower` με πραγματικό lower-barrier hit.

```text
File: src/targets/triple_barrier.py
Purpose: Separate actual barrier hits from neutral fallback labels.
```

```python
upper_count = int((raw_label_series == 1.0).sum())
lower_count = int((raw_label_series == 0.0).sum())
neutral_count = int(neutral_events.sum())
```

## 5. Meta-Labeling And R Multiples

Για explicit `label_mode: meta`, το target απαιτεί `side_col` και το barrier scan είναι side-aware. Long candidates έχουν TP πάνω από το entry και SL κάτω από το entry. Short candidates έχουν TP κάτω από το entry και SL πάνω από το entry. Το binary meta label είναι `1` μόνο όταν το `hit_type` είναι `profit`; stop hits και neutral events με `neutral_label: lower` γίνονται failure labels `0`. Τα candidates ελέγχονται από `candidate_col` ή `candidate_mode`.

Για backward compatibility, παλιά configs που δίνουν `side_col` χωρίς explicit `label_mode`
μένουν στο legacy implicit meta path, δηλαδή κάνουν candidate labels από `oriented_ret > 0`.
Τα νέα FTMO meta configs δηλώνουν `label_mode: meta`, οπότε χρησιμοποιούν αποκλειστικά
profit/stop semantics.

```text
File: src/targets/triple_barrier.py
Purpose: Candidate-filtered meta-labeling.
```

```python
if meta_label_enabled:
    side_series = out[str(side_col)].astype(float).fillna(0.0).clip(lower=-1.0, upper=1.0)
    side_sign = np.sign(side_series.to_numpy(dtype=float))
    candidate_mask = side_series.ne(0.0)
    if candidate_col is not None:
        raw_candidate = out[str(candidate_col)].astype(float).fillna(0.0)
        candidate_mask &= raw_candidate.ne(0.0)
```

```text
File: src/targets/triple_barrier.py
Purpose: Make meta labels depend on profit/stop hit_type, not terminal oriented_ret.
```

```python
if legacy_implicit_meta:
    finite_oriented_ret = np.isfinite(oriented_rets)
    meta_labels[candidate_values & finite_oriented_ret] = (
        oriented_rets[candidate_values & finite_oriented_ret] > 0.0
    ).astype(float)
else:
    hit_type_values = np.asarray(hit_types, dtype=object)
    profit_mask = candidate_values & (hit_type_values == "profit")
    failure_mask = candidate_values & (hit_type_values == "stop")
    if neutral_label != "drop":
        failure_mask |= candidate_values & (hit_type_values == "neutral")
    meta_labels[profit_mask] = 1.0
    meta_labels[failure_mask] = 0.0
```

Τα R multiples υπολογίζονται ως `event_return / (lower_mult * sigma)`. Αν υπάρχει `side_col`, το oriented R πολλαπλασιάζεται με το side sign. Χωρίς side, το `oriented_r` ισούται με το `event_r`.

```text
File: src/targets/triple_barrier.py
Purpose: Add continuous Expected-R / realized-R target columns.
```

```python
finite_risk = np.isfinite(risk_distances) & (risk_distances > 0.0) & np.isfinite(event_rets)
event_r[finite_risk] = event_rets[finite_risk] / risk_distances[finite_risk]
if r_clip is not None:
    event_r = np.clip(event_r, r_clip[0], r_clip[1])
```

```python
if add_r_multiple:
    out[r_col] = event_r.astype("float32")
    out[oriented_r_col] = oriented_r.astype("float32")
```

Το target metadata περιλαμβάνει τα reportable diagnostics.

```text
File: src/targets/triple_barrier.py
Purpose: Emit report-ready target metadata.
```

```python
meta = {
    "kind": "triple_barrier",
    "max_holding": max_holding,
    "entry_price_mode": entry_price_mode,
    "label_mode": label_mode,
    "upper_mult": upper_mult,
    "lower_mult": lower_mult,
    "neutral_label": neutral_label,
    "tie_break": tie_break,
    "labeled_rows": int(valid.sum()),
    "positive_rate": positive_rate,
    "upper_barrier_count": upper_count,
    "lower_barrier_count": lower_count,
    "neutral_count": neutral_count,
}
```

## 6. Regression Target Hook

Οι forecasters εξακολουθούν να λειτουργούν με `forward_return` by default. Αν χρησιμοποιηθεί `target.kind: triple_barrier`, πρέπει να οριστεί `target_col` ή `regression_target_col`, ώστε να είναι σαφές αν ο regression model μαθαίνει `tb_event_r`, `tb_oriented_r` ή άλλο emitted target.

```text
File: src/models/forecasting.py
Purpose: Let regression models select a triple-barrier emitted target column.
```

```python
elif target_kind == "triple_barrier":
    out, label_col, event_col, target_meta = build_triple_barrier_target(df=df, target_cfg=target_cfg)
    regression_target_col = str(
        target_cfg.get("target_col")
        or target_cfg.get("regression_target_col")
        or target_meta.get("oriented_r_col")
        or target_meta.get("r_col")
        or event_col
    )
    if regression_target_col not in out.columns:
        raise KeyError(
            f"Configured triple_barrier regression target_col '{regression_target_col}' was not emitted."
        )
    fwd_col = regression_target_col
```

## 7. FTMO-Aware Risk Sizing

Προστέθηκε νέο helper, χωρίς αλλαγή στα υπάρχοντα vol-target helpers.

```text
File: src/risk/position_sizing.py
Purpose: Convert signal conviction into risk-per-trade exposure.
```

```python
stop_distance = (float(stop_mult) * vol_aligned).clip(lower=float(eps))
risk_based = float(risk_per_trade) / stop_distance
if target_vol is not None:
    vol_based = float(target_vol) / vol_aligned.clip(lower=float(eps))
    leverage = pd.concat([risk_based, vol_based], axis=1).min(axis=1)
else:
    leverage = risk_based
leverage = leverage.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(
    lower=float(min_leverage),
    upper=float(max_leverage),
)
```

Το confidence adjustment υποστηρίζει δύο modes:

- `directional_class1`: για short signal και `confidence_col: pred_prob`, χρησιμοποιείται `1 - pred_prob`, ώστε τα short trades να μη μηδενίζονται επειδή το class-1 probability είναι χαμηλό.
- `meta_success`: το `pred_prob` ερμηνεύεται ως probability ότι το candidate trade θα πετύχει, άρα χρησιμοποιείται αυτούσιο και για long και για short trades.

```text
File: src/risk/position_sizing.py
Purpose: Support both directional class-1 confidence and meta success confidence.
```

```python
if confidence_mode == "directional_class1":
    conf = conf.where(sig >= 0.0, 1.0 - conf)
if confidence_floor is not None:
    floor = float(confidence_floor)
    confidence_adj = ((conf - floor).clip(lower=0.0) / max(1.0 - floor, float(eps))).clip(
        lower=0.0,
        upper=1.0,
    )
```

Το FTMO meta config χρησιμοποιεί ρητά `confidence_mode: meta_success`, οπότε δεν γίνεται inversion στα short signals.

Το YAML integration γίνεται στο backtest stage.

```text
File: src/experiments/orchestration/backtest_stage.py
Purpose: Wire risk.sizing.kind into single-asset and portfolio paths.
```

```python
def _ftmo_sizing_config(risk_cfg: dict[str, Any]) -> dict[str, Any]:
    sizing = dict(risk_cfg.get("sizing", {}) or {})
    if str(sizing.get("kind", "none")) != "ftmo_risk_per_trade":
        return {}
    return sizing
```

Για portfolio mode, τα FTMO-sized exposures δεν περνάνε από gross-target normalization. Εφαρμόζονται μόνο portfolio constraints.

```text
File: src/experiments/orchestration/backtest_stage.py
Purpose: Use pre-sized signed exposures as desired weights.
```

```python
if sizing_cfg:
    expected_return_col = None
    exposures = _build_ftmo_sized_exposures(
        asset_frames,
        signal_col=signal_col,
        sizing_cfg=sizing_cfg,
        alignment=alignment,
    )
    weights, diagnostics = build_constrained_weights_from_exposures_over_time(
        exposures,
        constraints=constraints,
        asset_to_group=asset_groups or None,
    )
    construction = "ftmo_risk_per_trade"
```

## 8. Sparse Execution And Signal Diagnostics

Το probability-vol-adjusted signal δέχεται πλέον `vol_target: null`. Σε αυτό το mode χρησιμοποιεί thresholded probability conviction χωρίς volatility multiplier.

```text
File: src/signals/forecast_signal.py
Purpose: Allow probability signal to run without vol-target multiplier.
```

```python
if vol_target is None:
    scaled_input = centered
else:
    scaled_input = centered * (float(vol_target) / vol_active)
scaled_active = np.tanh(scaled_input).astype(float) * float(clip)
```

Υπάρχει επίσης optional causal top-quantile gating. Χωρίς explicit rolling window, χρησιμοποιείται expanding past threshold με `shift(1)`, όχι same-row OOS information.

```text
File: src/signals/forecast_signal.py
Purpose: Optional sparse gating by past absolute conviction.
```

```python
if top_quantile is not None:
    abs_conviction = centered_all.abs()
    threshold_q = max(0.0, 1.0 - float(top_quantile))
    if top_quantile_window is not None:
        threshold = (
            abs_conviction.rolling(int(top_quantile_window), min_periods=min_periods)
            .quantile(threshold_q)
            .shift(1)
        )
    else:
        threshold = abs_conviction.expanding(min_periods=2).quantile(threshold_q).shift(1)
    active_mask &= abs_conviction.ge(threshold.fillna(np.inf))
```

Τα report diagnostics υπολογίζονται στο evaluation layer, όπου υπάρχουν μαζί OOS masks, signals, probabilities, realized R columns και τελικά weights.

```text
File: src/experiments/orchestration/reporting.py
Purpose: Report no-trade and execution diagnostics for classifier signals.
```

```python
out: dict[str, Any] = {
    "evaluation_rows": int(len(signal)),
    "signal_rows": int(len(signal)),
    "mean_abs_signal": float(signal.abs().mean()),
    "signal_turnover": float(signal.diff().abs().fillna(signal.abs()).mean()),
    "long_rate": float((signal > 0.0).mean()),
    "short_rate": float((signal < 0.0).mean()),
    "flat_rate": float((signal == 0.0).mean()),
    "executed_trade_count": int(executed.sum()),
    "trade_rate": float(executed.mean()),
}
```

## 9. FTMO Guard Additions

Το portfolio guard υποστηρίζει:

- `daily_soft_stop`
- `daily_hard_stop`
- `weekly_profit_lock`
- `after_target_mode: reduce_risk | flatten`
- `after_target_risk_multiplier`
- `risk.drawdown_sizing`

```text
File: src/portfolio/construction.py
Purpose: Extend risk guard config surface.
```

```python
class PortfolioRiskGuardConfig:
    enabled: bool = False
    weekly_return_target: float | None = None
    weekly_profit_lock: float | None = None
    after_target_mode: str = "reduce_risk"
    after_target_risk_multiplier: float = 0.25
    daily_soft_stop: float | None = None
    daily_soft_stop_risk_multiplier: float = 0.5
    daily_hard_stop: float | None = None
```

Το hard stop flatten/block ισχύει από το επόμενο bar για την υπόλοιπη ημέρα. Το weekly lock είτε μηδενίζει είτε μειώνει risk για την υπόλοιπη εβδομάδα.

```text
File: src/portfolio/construction.py
Purpose: Apply soft/hard/weekly multipliers before desired weights become actual weights.
```

```python
soft_multiplier = float(guard_cfg.daily_soft_stop_risk_multiplier) if daily_soft_stopped else 1.0
weekly_lock_multiplier = 1.0
if weekly_locked:
    weekly_lock_multiplier = (
        0.0
        if guard_cfg.after_target_mode == "flatten"
        else float(guard_cfg.after_target_risk_multiplier)
    )
risk_multiplier = float(drawdown_multiplier * soft_multiplier * weekly_lock_multiplier)
guard_active = permanent_flat or cooloff_remaining > 0 or daily_hard_stopped or risk_multiplier <= 0.0
```

## 10. Feature Drift Handling

Προστέθηκε config surface για drift filtering:

```yaml
feature_selectors:
  drift_filter:
    enabled: true
    max_psi: 0.5
    action: warn
    apply_scope: train_only_report
```

Το runtime επιτρέπει το key και το report γράφει warnings ανά feature family όταν το drift ratio ξεπεράσει threshold. Same-run dropping δεν εφαρμόζεται, ώστε να μη χρησιμοποιηθεί OOS drift για να τροποποιηθεί το ίδιο OOS evaluation.

```text
File: src/experiments/orchestration/reporting.py
Purpose: Warn on high family-level drift ratios without same-run feature dropping.
```

```python
if bool(dict(drift_filter).get("enabled", False)):
    ratio_threshold = float(dict(drift_filter).get("family_drift_ratio_threshold", 0.5) or 0.5)
    for row in _feature_family_drift_rows(monitoring):
        family, _, _, drift_ratio, _, _ = row
        if float(drift_ratio) > ratio_threshold:
            diagnostics.append(
                f"Feature drift filter warning: family '{family}' has drift ratio "
                f"{float(drift_ratio):.3f}, above threshold {ratio_threshold:.3f}."
            )
```

## 11. Example FTMO Configs

Προστέθηκαν:

- `config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1.yaml`
- `config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_conservative_v1.yaml`

Το meta config χρησιμοποιεί shock-context rule columns ως Stage A side/candidate:

```text
File: config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1.yaml
Purpose: Emit primary side and candidate columns for meta-labeling.
```

```yaml
- step: shock_context
  params:
    price_col: close
    high_col: high
    low_col: low
    returns_col: close_logret
    atr_col: atr_24
    ema_window: 24
  outputs:
    shock_side_contrarian_active: primary_side
    shock_candidate: trade_candidate
```

Το target block είναι FTMO-oriented:

```yaml
target:
  kind: triple_barrier
  max_holding: 24
  upper_mult: 2.0
  lower_mult: 1.0
  neutral_label: lower
  tie_break: lower
  entry_price_mode: next_open
  add_r_multiple: true
  label_mode: meta
  side_col: primary_side
  candidate_col: trade_candidate
```

Το meta config δεν χρησιμοποιεί πλέον directional probability semantics. Το `pred_prob`
ερμηνεύεται ως `P(primary_side candidate succeeds)`, άρα το signal ενεργοποιεί μόνο την
προτεινόμενη πλευρά και δεν ανοίγει ποτέ αντίθετο trade όταν η πιθανότητα είναι χαμηλή:

```text
File: config/experiments/ftmo_fx_intraday_panel_4pair_xgboost_triple_barrier_meta_v1.yaml
Purpose: Use meta success probability with same-side-only execution and FTMO sizing.
```

```yaml
signals:
  kind: meta_probability_side
  params:
    prob_col: pred_prob
    side_col: primary_side
    candidate_col: label_candidate
    signal_col: signal_meta_side
    threshold: 0.62
    upper: 0.62
    clip: 1.0

risk:
  sizing:
    kind: ftmo_risk_per_trade
    confidence_col: pred_prob
    confidence_floor: 0.60
    confidence_mode: meta_success
```

Το backtest και τα portfolio constraints του ίδιου config διαβάζουν το νέο signal column
και επιτρέπουν FTMO-sized exposure μέχρι περίπου 2x gross με per-asset cap 0.75:

```yaml
backtest:
  signal_col: signal_meta_side

portfolio:
  constraints:
    min_weight: -0.75
    max_weight: 0.75
    max_gross_leverage: 2.0
```

Το conservative config χρησιμοποιεί binary target και αυστηρότερα probability thresholds:

```yaml
signals:
  kind: probability_vol_adjusted
  params:
    upper: 0.65
    lower: 0.35
    vol_target: null
    min_signal_abs: 0.05
```

## 12. Validation And Tests

Έτρεξαν επιτυχώς:

```text
pytest -q tests/test_phase12_extensions.py::test_logistic_meta_labels_predict_only_candidate_oos_rows tests/test_ftmo_triple_barrier_upgrade.py
```

Result:

```text
10 passed
```

```text
pytest -q tests/test_config_validation.py tests/test_feature_selectors.py tests/test_new_model_families.py::test_probability_vol_adjusted_signal_supports_dead_zone_and_floor tests/test_new_model_families.py::test_probability_vol_adjusted_signal_supports_activation_filters tests/test_new_model_families.py::test_probability_vol_adjusted_signal_resolves_activation_filter_selectors
```

Result:

```text
64 passed
```

```text
pytest -q tests/test_phase12_extensions.py::test_triple_barrier_target_labels_upper_and_lower_events tests/test_phase12_extensions.py::test_triple_barrier_target_records_barrier_level_event_returns tests/test_phase12_extensions.py::test_triple_barrier_target_keeps_incomplete_tail_unlabeled tests/test_phase12_extensions.py::test_triple_barrier_target_supports_side_change_meta_labels tests/test_phase12_extensions.py::test_xgboost_classifier_supports_triple_barrier_target tests/test_phase12_extensions.py::test_forward_return_target_can_use_log_return_inputs
```

Result:

```text
6 passed
```

Τελικό full-suite validation:

```text
pytest -q
```

Result:

```text
318 passed, 2 skipped, 22 warnings
```

Επιπλέον εκτελέστηκε μικρό synthetic smoke experiment με `target.kind: triple_barrier` και generated report. Το report περιείχε:

```text
- Target: `triple_barrier` horizon `3`
```

Το generated smoke report ήταν:

```text
logs/experiments_smoke/ftmo_tb_smoke_20260426_184313_027269_ee78be88/report.md
```

## 13. Residual Risks

- Το `label_mode: ternary` υποστηρίζεται στο target builder, αλλά το κύριο XGBoost example παραμένει binary/meta. Πριν χρησιμοποιηθεί ternary σε production classifier, χρειάζεται explicit multiclass objective/metric policy.
- Το drift `action: drop` δεν εφαρμόζεται στο ίδιο OOS run. Αυτό είναι συνειδητή επιλογή για να αποφευχθεί leakage. Το σωστό επόμενο βήμα είναι train-only ή next-fold drift exclusion.
- Το meta config χρησιμοποιεί rule-based shock side/candidate ως Stage A. Αν θέλεις learned primary side model, αυτό πρέπει να μπει ως ξεχωριστό model stage με explicit ownership των emitted columns.
- Το FTMO sizing θεωρεί ότι `vol_col` είναι stop-distance proxy σε return space. Για broker-accurate sizing θα χρειαστεί pip value / contract-size layer.
