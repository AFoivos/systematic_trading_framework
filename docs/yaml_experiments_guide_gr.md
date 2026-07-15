# Οδηγός YAML Experiments

Τελευταία ενημέρωση: 2026-07-03

## Βασική αρχή

Τα feature steps παράγουν raw columns μόνο. Κάθε παράγωγη στήλη, όπως ratio,
distance, slope, lag, crossing flag, threshold flag, rolling z-score ή clipping,
δηλώνεται ως helper μέσα στο ίδιο feature step.

Το παλιό standalone `feature_transforms` step έχει καταργηθεί. Δεν υπάρχει
`tsfresh_rolling.py` helper και το `tsfresh_rolling` απορρίπτεται από το YAML
validation.

## Trade Path Diagnostics

Τα trade lifecycle diagnostics είναι reporting/artifact layer και δεν μπαίνουν
ποτέ στο feature selection. Όταν το top-level `diagnostics.enabled` είναι
`true`, το `diagnostics.trade_path.enabled` γίνεται αυτόματα `true`, εκτός αν
δοθεί explicit opt-out.

```yaml
diagnostics:
  enabled: true
  # trade_path auto-enabled by default
  trade_path:
    thresholds_r: [0.5, 1.0, 1.5, 2.0]
    include_counterfactuals: true
    plots:
      enabled: true
```

Για explicit opt-out:

```yaml
diagnostics:
  enabled: true
  trade_path:
    enabled: false
```

Τα structured outputs γράφονται κάτω από `report_assets/` όταν υπάρχουν αρκετά trade
metadata: `trades_enriched.csv`, `trade_paths.parquet` ή fallback
`trade_paths.csv`, `probability_trade_quality.csv`,
`counterfactual_exit_summary.csv` και diagnostic JSON warnings. Τα legacy
HTML diagnostics όπως `trade_diagnostics_*.html` και `report.html` δεν παράγονται πλέον.

## Νέα δομή φακέλων

- `src/features/technical/`: raw indicators όπως `trend`, `atr`, `vwap`, `ppo`
- `src/features/helpers/`: γενικές μετατροπές όπως `ratio.py`, `difference.py`,
  `lag.py`, `reciprocal.py`, `flags.py`, `rolling_mean.py`,
  `rolling_std.py`, `rolling_sum.py`, `rolling_linear_regression.py`,
  `rms.py`, `slope.py`, `rolling_clip.py`, `rolling_zscore.py`
- `src/features/helpers/normalizations/`: trading normalizations όπως
  `returns.py`, `atr_distances.py`, `volatility.py`, `rolling_zscores.py`,
  `rolling_percent_rank.py`, `robust_zscore.py`,
  `volatility_scaled_return.py`, `atr_scaled_distance.py`,
  `range_position.py`, `realized_vol_percentile.py`, `volume_relative.py`,
  `rolling_beta_residual.py`
- `src/features/helpers/apply.py`: εφαρμόζει τα helper blocks μετά από κάθε raw
  feature step
- `src/features/helpers/registry.py`: registry για transform helpers και
  normalization helpers
- `config/experiments/market_making/`: research-only event-driven market-making
  experiments, όπως `market_making_moment.yaml`. Τα outputs γράφονται κάτω από
  `logs/experiments/market_making/` και δεν παράγουν HTML/PPTX artifacts.

Για πλήρη κατηγοριοποιημένη ερμηνεία κάθε helper, δες το
[`catalog/helpers.md`](catalog/helpers.md). Για πλήρη κατηγοριοποιημένη
ερμηνεία των raw feature steps, δες το [`catalog/features.md`](catalog/features.md).
Για το ίδιο επίπεδο ανάλυσης σε signals, targets και models, δες τα
[`catalog/signals.md`](catalog/signals.md), [`catalog/targets.md`](catalog/targets.md)
και [`catalog/models.md`](catalog/models.md).

## Market-making YAML experiments

Τα market-making experiments έχουν διαφορετικό YAML contract από το canonical
OHLCV/candle pipeline. Δεν χρησιμοποιούν top-level `features`, `model.target`,
`signals`, `backtest` με την ίδια σημασία. Είναι event-driven experiments που
δουλεύουν πάνω σε `orderbook_events.csv`, `quote_events.csv`, quote decisions
και markout targets.

Τα configs βρίσκονται κάτω από:

```text
config/experiments/market_making/
```

Τα outputs γράφονται κάτω από:

```text
logs/experiments/market_making/
```

και πρέπει να μένουν JSON/CSV/Markdown/Parquet-only. Δεν παράγονται HTML ή
PowerPoint artifacts.

### Γιατί είναι ξεχωριστό YAML shape

Το canonical pipeline παράγει trade signal τύπου:

```text
long / flat / short / weight
```

Το market maker παράγει quote decision τύπου:

```text
quote bid / quote ask / quote both / quote none
spread
size
inventory skew
cancel-replace behavior
```

Άρα το market-making YAML δεν πρέπει να αντιμετωπίζεται ως απλό `signals`
extension. Η σωστή σειρά είναι:

```text
orderbook events
  -> quote candidates
  -> context/features/filters
  -> quote policy
  -> risk filter
  -> paper replay / markout evaluation
  -> JSON/CSV/Markdown/Parquet artifacts
```

### Απλό MOMENT research config

Το `market_making_moment.yaml` είναι research-only config που καταναλώνει ήδη
υπάρχοντα local artifacts:

```yaml
data:
  orderbook_events_path: logs/experiments/market_making/orderbook_events.csv
  quote_events_paths:
    - logs/experiments/market_making/quote_events.csv
  trades_path: logs/experiments/market_making/trades.csv
  dataset_path: logs/experiments/market_making/datasets/moment_dataset.parquet
  reuse_dataset: true
  horizons: [1, 5, 10, 30]

market_making:
  maker_fee_bps: 2.0
  max_inventory: 1.0

model:
  backend: deterministic_fixture
  checkpoint: AutonLab/MOMENT-1-large
  frozen_encoder: true
  fine_tune: false
  lookback_length: 512
  target_horizon: h5
  batch_size: 8
  device: cpu

filter:
  expected_spread_capture_bps: 0.0
  safety_buffer_bps: 0.5
  max_uncertainty: 1.0
  min_expected_edge_bps: 0.0

split:
  train_fraction: 0.6
  validation_fraction: 0.2

output:
  root: logs/experiments/market_making
  run_name: market_making_moment
  write_report: true

runtime:
  random_seed: 42
  deterministic: true
```

Σημασία των blocks:

- `data`: δηλώνει quote-level inputs και πού θα γραφτεί/διαβαστεί το
  `moment_dataset.parquet`.
- `market_making`: δηλώνει fee και inventory assumptions για evaluation.
- `model`: δηλώνει MOMENT backend/checkpoint ή deterministic fixture backend
  για local tests.
- `filter`: δηλώνει thresholds για fee-aware expected edge και uncertainty.
- `split`: chronological train/validation/test split. Δεν επιτρέπεται random
  shuffle.
- `output`: namespace για artifacts κάτω από `logs/experiments/market_making/`.
- `runtime`: reproducibility controls.

### Staged market-making pipeline configs

Τα staged configs, όπως `market_making_large_moment_pipeline.yaml`,
`market_making_moment_collect_100k_pipeline.yaml` και
`market_making_large_moment_collect_2m_pipeline.yaml`, προσθέτουν top-level
`pipeline` block:

```yaml
pipeline:
  output_dir: logs/experiments/market_making/pipeline_runs/large_moment
  write_manifest: true
  collect_orderbook:
    enabled: true
    output_path: logs/experiments/market_making/orderbook_events.csv
    max_events: 1000000
  paper_replay:
    enabled: true
    output_dir: logs/experiments/market_making/runs/large_moment_replay
    use_outputs_for_moment: true
  moment_experiment:
    enabled: true
```

Αυτό το shape είναι orchestration config, όχι canonical experiment config.
Δηλώνει ποια stages θα τρέξουν:

- `collect_orderbook`: συλλογή public order-book events σε local CSV.
- `paper_replay`: deterministic paper replay πάνω στα collected events.
- `moment_experiment`: χτίσιμο/reuse quote-level dataset και MOMENT/filter
  evaluation.

Αν `paper_replay.use_outputs_for_moment: true`, τότε το pipeline πρέπει να
χρησιμοποιεί τα `quote_events.csv`, `trades.csv` και λοιπά outputs του replay ως
inputs για το MOMENT dataset.

### Market-making filters και combinations

Τα market-making filters περιορίζουν quote decisions πριν εμφανιστούν fills. Δεν
περιορίζουν απευθείας trades εκ των υστέρων. Η causal ροή είναι:

```text
context features -> quote filter stack -> allowed bid/ask quotes -> possible fills
```

Παραδείγματα φίλτρων:

- `use_adverse_selection_filter`: μπλοκάρει quotes όταν το book context δείχνει
  αυξημένο toxic-fill risk.
- `use_fee_aware_gate`: απαιτεί θετικό expected edge μετά από fees και safety
  buffer.
- `use_side_selection_gate`: επιτρέπει bid/ask πλευρές χωριστά.
- `use_directional_feature_gate`: χρησιμοποιεί directional context, όπως
  microprice offset, short-term trend ή imbalance.
- volatility filters: μπλοκάρουν ή widen quotes όταν η πρόσφατη μεταβλητότητα
  είναι υψηλή.
- trend/regime filters: επιτρέπουν μόνο bid, μόνο ask, both ή none ανάλογα με
  causal trend context.

Το σωστό abstraction είναι:

```text
QuoteCandidate
  + book context
  + trend context
  + volatility context
  + model predictions
  -> filter stack
  -> final QuoteDecision
```

Κάθε filter πρέπει να γράφει explainable reason fields, ώστε τα diagnostics να
δείχνουν γιατί έγινε block:

```text
filter_name
allowed
blocked_side
reason
thresholds
input_columns_used
```

### Σύνδεση με canonical features/models/signals

Μπορείς να χρησιμοποιήσεις outputs από τα canonical experiments ως causal
context στο market maker, αλλά όχι να συγχωνεύσεις αβίαστα τα schemas.

Επιτρεπτά inputs, αν είναι point-in-time:

- trend features από τελευταίο γνωστό κλεισμένο candle,
- volatility/regime features,
- OOS model predictions όπως `pred_prob`, `pred_ret`, `pred_vol`,
- signal columns ως context/gates,
- session/time filters,
- cross-asset context.

Απαγορευμένα ως model/filter inputs:

- future markout columns,
- `future_mid_return_*`,
- `buy_markout_bps_*`,
- `sell_markout_bps_*`,
- fill-only labels ως training base,
- in-sample predictions,
- current candle values που δεν ήταν γνωστά στο quote timestamp.

Το join πρέπει να γίνεται με as-of semantics:

```text
quote timestamp -> latest known closed candle/context timestamp
```

και όχι με forward-looking merge. Αν το trend feature προέρχεται από 30m candle,
στο quote timestamp επιτρέπεται μόνο το τελευταίο κλεισμένο 30m candle.

### Market-making targets

Τα market-making targets είναι quote-level/evaluation labels, όχι bar-level
trade targets:

- `future_mid_return_h1/h5/h10/h30`
- `buy_markout_bps_h1/h5/h10/h30`
- `sell_markout_bps_h1/h5/h10/h30`
- `buy_good_h5`
- `sell_good_h5`
- `buy_good_after_fees_h5`
- `sell_good_after_fees_h5`

Αυτά επιτρέπεται να κοιτάνε μέλλον μόνο για target/evaluation construction.
Δεν μπαίνουν ποτέ στα input features ή filters.

### Market-making artifacts

Ένα market-making research run πρέπει να γράφει artifacts στο ίδιο ύφος με τα
classic experiments:

- `summary.json`
- `run_metadata.json`
- `artifact_manifest.json`
- `config_used.yaml`
- `returns.csv`
- `equity_curve.csv`
- `gross_returns.csv`
- `costs.csv`
- `turnover.csv`
- `positions.csv`
- `trades.csv`
- `quote_decisions.csv`
- `moment_predictions.csv`
- `moment_dataset.parquet`
- optional `report.md`

Το `summary.json` πρέπει να έχει και classic metrics και market-making-specific
blocks:

- `summary`
- `timeline_summary`
- `evaluation.primary_summary`
- `evaluation.trade_diagnostics`
- `market_making_summary`
- `markout_summary`
- `risk_summary`
- `moment_summary`
- `model_meta`
- `reproducibility`

Δεν επιτρέπονται `.html` ή `.pptx` outputs.

## Σειρά εκτέλεσης

Για κάθε entry στο `features`:

1. Εκτελείται το raw feature function από το `step`.
2. Εφαρμόζονται τα `normalizations` του ίδιου step.
3. Εφαρμόζονται τα `transforms` του ίδιου step.
4. Εφαρμόζεται το optional `outputs` mapping.

Σε multi-asset run, τα `params_by_asset` αλλάζουν τα raw feature params.
Τα `transforms_by_asset` και `normalizations_by_asset` κάνουν override ανά helper
name, αλλά αφήνουν τα υπόλοιπα top-level helpers να ισχύουν.

## Συνολική pipeline σειρά

Η πραγματική σειρά στο canonical experiment pipeline είναι:

1. Φόρτωση data και PIT checks.
2. `features`: raw feature steps και οι helper μετατροπές τους.
3. `model` και `model_stages`: target construction για training, fit ανά split
   και out-of-sample predictions.
4. Top-level `signals`: μετατροπή feature/model outputs σε τελικό trading
   signal.
5. Optional top-level `target`: μόνο για post-signal diagnostics όταν
   `model.kind: none`.
6. `backtest` ή `portfolio` evaluation.
7. `diagnostics`, `monitoring`, artifacts και optional `execution`.

Δύο σημεία θέλουν προσοχή:

- Αν το target εκπαιδεύει model, μπαίνει μέσα στο `model.target`.
- Αν θέλεις target diagnostics πάνω σε rule-only signal χωρίς model, βάζεις
  top-level `target`, αλλά τότε το `model.kind` πρέπει να είναι `none`.

Το `model` stage τρέχει πριν από το top-level `signals`. Άρα ένα target μέσα στο
`model.target` δεν μπορεί να εξαρτάται από στήλες που παράγονται μόνο από το
top-level `signals`. Αν χρειάζεσαι primary candidate πριν από model training,
χρησιμοποίησε causal feature step ή compatibility signal step μέσα στο
`features`, όπως `ehlers_semiscalp_long`, `indicator_model_adaptive_pullback`,
`roc_long_only_conditions`, `ema_stoch_rsi_pullback` ή
`vwap_rms_ema_cross_long`.

## Causality και leakage rules

- Τα `features` κοιτάνε μόνο παρελθόν και current bar.
- Τα `normalizations` μέσα στα features πρέπει να είναι causal. Για rolling
  στατιστικά προτίμησε shifted stats όταν το helper το υποστηρίζει.
- Τα `targets` επιτρέπεται να κοιτάνε μέλλον, αλλά μόνο για label construction.
- Target columns όπως `label`, `target_fwd_*`, `event_ret`, `trade_r`,
  `oriented_r`, `hit_type` και barrier diagnostics δεν μπαίνουν ποτέ σε
  `feature_cols` ή signal filters.
- Τα model-driven signals πρέπει να χρησιμοποιούν out-of-sample outputs. Για
  classifier/regressor σήματα, έλεγξε ότι υπάρχει `pred_is_oos = 1` στα rows που
  αξιολογείς.
- Τα ML scalers δηλώνονται στο `model.preprocessing` και εφαρμόζονται μέσα στα
  train folds. Δεν είναι feature normalizations.

## Παράδειγμα raw indicator με transforms

```yaml
features:
  - step: trend
    params:
      price_col: close
      sma_windows: []
      ema_spans: [50]
      ema_col_template: ema_50
      add_ratios: false
    transforms:
      ratio:
        enabled: true
        params:
          numerator_col: close
          denominator_col: ema_50
          output_col: close_over_ema_50
          subtract: 1.0
      rms:
        enabled: true
        params:
          source_col: ema_50
          window: 192
          shift: 0
          output_prefix: ema_50
```

Το `trend` παράγει μόνο `ema_50`. Τα `close_over_ema_50` και
`ema_50__root_mean_square` παράγονται από helpers.

## Παράδειγμα normalizations

```yaml
features:
  - step: atr
    params:
      high_col: high
      low_col: low
      close_col: close
      windows: [14]
      atr_col: atr_14
    normalizations:
      volatility:
        enabled: true
        params:
          close_col: close
          atr_col: atr_14
          add_atr_pct: true
          add_atr_percentile: true
          percentile_window: 252
      rolling_zscores:
        enabled: true
        params:
          columns: [atr_14]
          window: 96
          shift_stats: true
```

Τα normalizations δημιουργούν νέα columns, αλλά δεν είναι ML scalers. Οι ML
scalers γίνονται μόνο μέσα στα train folds.

## Παράδειγμα per-asset overrides

```yaml
features:
  - step: vwap
    params:
      high_col: high
      low_col: low
      close_col: close
      volume_col: volume
      windows: [20]
      vwap_col: vwap_20
    params_by_asset:
      GER40:
        windows: [32]
        vwap_col: vwap_32
    transforms:
      ratio:
        enabled: true
        params:
          numerator_col: close
          denominator_col: vwap_20
          output_col: close_over_vwap_20
          subtract: 1.0
    transforms_by_asset:
      GER40:
        ratio:
          enabled: true
          params:
            numerator_col: close
            denominator_col: vwap_32
            output_col: close_over_vwap_32
            subtract: 1.0
```

Για τα assets χωρίς override εφαρμόζεται το top-level `ratio`. Για `GER40`, το
`ratio` αντικαθίσταται από το asset-specific block.

## Διαθέσιμα transform helpers

- `ratio`: παράγει `numerator / denominator - subtract`, με optional
  `denominator_offset`.
- `difference`: παράγει `source - source.shift(periods)`.
- `lag`: παράγει `source.shift(periods)`.
- `reciprocal`: παράγει `1 / source` ή `1 / abs(source)`.
- `threshold_flag`: παράγει binary flag με `gt`, `ge`, `lt`, `le`, `eq`, `ne`.
- `rising_flag`: παράγει flag όταν `source_t > source_{t-periods}`.
- `between_flag`: παράγει flag όταν η τιμή είναι μέσα σε `[lower, upper]`.
- `crossing_flag`: παράγει cross-up ή cross-down event σε numeric threshold.
- `rolling_mean`: trailing rolling mean.
- `rolling_std`: trailing rolling standard deviation.
- `rolling_sum`: trailing rolling sum.
- `rolling_linear_regression`: trailing slope/intercept/R2.
- `rms`: rolling root mean square.
- `slope`: rolling linear slope helper.
- `rolling_clip`: causal rolling quantile clipping.
- `rolling_zscore`: causal rolling z-score helper.

Κάθε helper δέχεται `enabled`, `params` ή `items`. Το `items` χρησιμοποιείται όταν
θέλουμε πολλαπλά outputs από τον ίδιο helper.

Παράδειγμα με `items`:

```yaml
features:
  - step: roofing_filter
    params:
      price_col: close
      output_col: roofing_filter_48_10
    transforms:
      crossing_flag:
        items:
          - source_col: roofing_filter_48_10
            threshold: 0.0
            direction: up
            output_col: roofing_filter_48_10_cross_up
          - source_col: roofing_filter_48_10
            threshold: 0.0
            direction: down
            output_col: roofing_filter_48_10_cross_down
```

Παράδειγμα Hilbert derived columns:

```yaml
features:
  - step: hilbert_transform
    params:
      price_col: close
      window: 64
      amplitude_col: hilbert_amplitude_64
      phase_col: hilbert_phase_64
      instantaneous_frequency_col: hilbert_frequency_64
    transforms:
      reciprocal:
        params:
          source_col: hilbert_frequency_64
          use_abs: true
          output_col: hilbert_dominant_cycle_64
      between_flag:
        params:
          source_col: hilbert_dominant_cycle_64
          lower: 10.0
          upper: 48.0
          output_col: hilbert_cycle_ok_64
      rising_flag:
        params:
          source_col: hilbert_amplitude_64
          periods: 3
          output_col: hilbert_amplitude_rising_64
```

## Διαθέσιμα normalization helpers

- `returns`: past-looking simple και log returns
- `atr_distances`: ATR-normalized distances ανά ζεύγος columns
- `volatility`: `atr_pct` και rolling ATR percentile
- `rolling_zscores`: z-scores για λίστα columns με optional shifted stats
- `rolling_percent_rank`: percentile rank του current value έναντι prior
  trailing window.
- `robust_zscore`: rolling median/MAD z-score με shifted stats by default.
- `volatility_scaled_return`: `return / volatility`.
- `atr_scaled_distance`: `(base - reference) / ATR`.
- `range_position`: θέση τιμής μέσα στο trailing high-low range.
- `realized_vol_percentile`: percentile rank για realized volatility column.
- `volume_relative`: `volume / rolling_mean(volume)` και optional volume
  z-score.
- `rolling_beta_residual`: single-factor rolling beta residual έναντι
  benchmark returns.

Παράδειγμα trading normalizations:

```yaml
features:
  - step: returns
    normalizations:
      rolling_percent_rank:
        params:
          source_col: close_logret_1
          window: 252
          output_col: close_logret_1_percent_rank_252
      robust_zscore:
        params:
          source_col: close_logret_1
          window: 252
          output_col: close_logret_1_robust_z_252
      volatility_scaled_return:
        params:
          return_col: close_logret_1
          volatility_col: vol_rolling_96
          output_col: close_logret_1_over_vol_96
      volume_relative:
        params:
          volume_col: volume
          window: 96
          output_col: volume_relative_96
```

## Targets

Τα targets απαντούν "τι έγινε μετά από αυτό το timestamp;". Χρησιμοποιούνται είτε
για να εκπαιδεύσουν model (`model.target`) είτε ως diagnostics σε rule-only
workflow (top-level `target` με `model.kind: none`).

Διαθέσιμα canonical target kinds:

- `forward_return`: fixed-horizon binary label από μελλοντική απόδοση.
- `future_return_regression`: continuous future return label για regressors.
- `triple_barrier`: upper/lower/time barrier label.
- `directional_triple_barrier`: meta-label για ήδη προτεινόμενη πλευρά.
- `r_multiple`: R-multiple outcome για manual long candidates.

### Παράδειγμα fixed-horizon classifier target

```yaml
model:
  kind: logistic_regression_clf
  pred_prob_col: pred_prob
  pred_is_oos_col: pred_is_oos
  target:
    kind: forward_return
    price_col: close
    horizon: 12
    threshold: 0.0
    fwd_col: target_fwd_12
    label_col: label
  split:
    method: purged
    train_size: 24000
    test_size: 4000
    step_size: 4000
    purge_bars: 12
    embargo_bars: 12
  feature_cols:
    - close_logret_1
    - atr_over_price_14
    - close_over_ema_50
```

Εδώ το `label = 1` σημαίνει ότι το `close` μετά από 12 bars είναι πάνω από το
τρέχον `close`. Το `pred_prob` είναι πιθανότητα positive label, όχι απευθείας
εντολή αγοράς.

### Παράδειγμα regression target

```yaml
model:
  kind: lightgbm_regressor
  pred_ret_col: pred_ret
  pred_is_oos_col: pred_is_oos
  target:
    kind: future_return_regression
    price_col: close
    horizon: 8
    label_col: label
    raw_fwd_col: raw_fwd_8
    normalize_by_volatility: true
    volatility_col: atr_14
    clip: [-5.0, 5.0]
  split:
    method: purged
    train_size: 30000
    test_size: 5000
    step_size: 5000
    purge_bars: 8
    embargo_bars: 8
  feature_selectors:
    include:
      - startswith: [ema_, atr_, ppo_]
```

Το `pred_ret` είναι forecast στην ίδια κλίμακα με το target. Αν το target είναι
volatility-normalized, `pred_ret = 1.2` σημαίνει περίπου 1.2 μονάδες τοπικής
μεταβλητότητας, όχι 120%.

### Παράδειγμα meta-label target με primary candidate

```yaml
features:
  - step: indicator_model_adaptive_pullback
    params:
      direction_col: direction
      signal_col: signal_raw
      candidate_col: signal_candidate
      score_col: signal_score

model:
  kind: lightgbm_clf
  outputs:
    pred_prob_col: pred_prob
    pred_is_oos_col: pred_is_oos
  target:
    kind: directional_triple_barrier
    outputs:
      label_col: label
      event_ret_col: dtb_event_ret
      r_col: dtb_event_r
      oriented_r_col: dtb_oriented_r
    direction_col: direction
    candidate_col: signal_candidate
    price_col: close
    open_col: open
    high_col: high
    low_col: low
    volatility_col: atr_14
    entry_price_mode: next_open
    profit_barrier_r: 1.4
    stop_barrier_r: 1.0
    vertical_barrier_bars: 6
    neutral_label: stop
    add_r_multiple: true
  feature_selectors:
    include:
      - startswith: [ema_, atr_, rsi_, stoch_]
      - exact: [direction, signal_score]
```

Η σειρά είναι: το feature-compatible primary step γράφει `direction` και
`signal_candidate`, το `model.target` φτιάχνει labels μόνο στα candidates, και
το model μαθαίνει πιθανότητα επιτυχίας του candidate. Το `direction` μπορεί να
είναι feature γιατί είναι causal output του primary rule. Το `label` και τα
`dtb_*` outputs δεν πρέπει να είναι features.

### Παράδειγμα rule-only diagnostic target

```yaml
model:
  kind: none

signals:
  kind: ppo_adx_stochrsi_trend
  params:
    signal_col: signal
    position_col: position
    entry_long_col: entry_long
    exit_long_col: exit_long

target:
  kind: triple_barrier
  label_col: tb_label
  fwd_col: tb_event_ret
  r_col: tb_event_r
  oriented_r_col: tb_oriented_r
  price_col: close
  open_col: open
  high_col: high
  low_col: low
  volatility_col: atr_over_price
  label_mode: meta
  side_col: signal
  candidate_mode: side_change
  entry_price_mode: next_open
  max_holding: 96
  upper_mult: 2.5
  lower_mult: 1.5
  add_r_multiple: true
```

Αυτό δεν εκπαιδεύει model. Χρησιμεύει για να δεις αν τα rule-only entries έχουν
καλό barrier outcome και R distribution.

## Signals

Τα signals μετατρέπουν features, model probabilities ή forecasts σε τελικό
`signal_col`. Το `backtest.signal_col` πρέπει να δείχνει στη στήλη που θέλεις να
αξιολογήσεις.

Συνηθισμένες κατηγορίες:

- Rule/indicator signals: `trend_state`, `rsi`, `momentum`, `stochastic`,
  `volatility_regime`.
- Primary candidate generators: `orb_candidate_side`, `roc_long_only_conditions`,
  `ema_stoch_rsi_pullback`, `indicator_model_adaptive_pullback`,
  `ppo_adx_stochrsi_trend`, `stc_roofing_hilbert`.
- Model probability signals: `probability_threshold`,
  `probability_conviction`, `probability_vol_adjusted`,
  `meta_probability_side`, `manual_long_model_filter`.
- Forecast signals: `dense_return_forecast`, `forecast_threshold`,
  `forecast_vol_adjusted`.
- Wrappers/filters: `regime_filtered`.

### Παράδειγμα flat/EDA signal

```yaml
signals:
  kind: none
  params:
    signal_col: eda_flat_signal

backtest:
  signal_col: eda_flat_signal
```

Χρήσιμο όταν θέλεις να τρέξει όλο το reporting χωρίς πραγματικές θέσεις.

### Παράδειγμα rule signal

```yaml
signals:
  kind: trend_state
  params:
    state_col: trend_regime
    signal_col: signal_trend_state
    mode: long_short_hold

backtest:
  engine: vectorized
  signal_col: signal_trend_state
  returns_col: close_ret
```

Το `trend_state` διαβάζει ήδη υπάρχον causal feature column και γράφει τελικό
long/short/flat signal.

### Παράδειγμα meta probability filter

```yaml
signals:
  kind: meta_probability_side
  outputs:
    signal_col: signal
  params:
    prob_col: pred_prob
    side_col: direction
    candidate_col: signal_candidate
    threshold: 0.58
    profit_barrier_r: 1.4
    stop_barrier_r: 1.0
    min_expected_value_r: 0.1
    mode: long_short

backtest:
  engine: manual_barrier
  signal_col: signal
```

Το signal κρατά την πλευρά του primary candidate μόνο αν το OOS `pred_prob`
περάσει threshold και, αν έχει δοθεί, expected-value φίλτρο. Δεν αντιστρέφει
πλευρά από μόνο του.

### Παράδειγμα long-only model filter

```yaml
signals:
  kind: manual_long_model_filter
  params:
    prob_col: pred_prob
    candidate_col: signal_candidate
    base_signal_col: signal_side
    threshold: 0.55
    signal_col: model_filtered_long_signal

backtest:
  engine: manual_barrier
  signal_col: model_filtered_long_signal
  long_only: true
```

Κατάλληλο όταν το primary setup είναι long-only και το model απλώς αποφασίζει αν
το trade αξίζει να κρατηθεί.

### Παράδειγμα forecast threshold signal

```yaml
signals:
  kind: forecast_threshold
  params:
    forecast_col: pred_ret
    signal_col: signal_forecast
    upper: 0.002
    lower: -0.002
    mode: long_short_hold

backtest:
  engine: vectorized
  signal_col: signal_forecast
```

Χρησιμοποιείται μετά από regressor/forecaster. Τα thresholds πρέπει να είναι
στην ίδια κλίμακα με το `pred_ret`.

## Models

Το `model.kind` επιλέγει τον trainer ή policy builder. Τα πιο συνηθισμένα
outputs είναι:

- `pred_prob`: πιθανότητα positive label ή candidate success.
- `pred_ret`: continuous return forecast.
- `pred_vol`: volatility/risk forecast.
- `pred_is_oos`: ένδειξη ότι το prediction είναι out-of-sample.
- `signal_rl` και `action_rl`: policy outputs από RL models.

Διαθέσιμα model groups:

- Classifiers: `logistic_regression_clf`, `elastic_net_clf`, `lightgbm_clf`,
  `xgboost_clf`, `event_transformer_encoder`.
- Regressors/forecasters: `lightgbm_regressor`, `sarimax_forecaster`,
  `garch_forecaster`, `lstm_forecaster`, `patchtst_forecaster`,
  `tft_forecaster`, `chronos_bolt_forecaster`, `chronos_2_forecaster`,
  `timesfm_2p5_200m_forecaster`, `timesfm_1p0_200m_forecaster`.
- Feature discovery: `tsfresh_extrema_feature_discovery`.
- Single-asset RL: `ppo_agent`, `dqn_agent`.
- Portfolio RL: `ppo_portfolio_agent`, `dqn_portfolio_agent`.

### Chronos-2 με historical covariates

Το `chronos_bolt_forecaster` και τα TimesFM foundation wrappers χρησιμοποιούν
μόνο το univariate `params.source_col`. Το `chronos_2_forecaster` μπορεί να
χρησιμοποιήσει το ήδη canonical `model.feature_cols` ή `model.feature_selectors`
ως numerical past covariates. Δεν υπάρχει δεύτερο `past_covariate_cols` field.

Με `use_features: true`, το framework αφαιρεί το `source_col`, target/label
outputs και prediction outputs από τις covariates. Το `source_col` επιτρέπεται
να υπάρχει στη feature list για compatibility, αλλά δεν περνάει δεύτερη φορά.
Target ή label outputs μέσα στα explicit `feature_cols` απορρίπτονται από το
validation. Με `use_features: false` ή `feature_cols: []`, το Chronos-2 μένει
στο backward-compatible univariate mode.

Για κάθε OOS origin το context είναι μόνο `[t-lookback+1, ..., t]`. Οι
covariates έχουν ακριβώς τα ίδια timestamps με το target, δεν γίνεται forward
fill, και μια εσωτερική NaN κόβει το context στο μεγαλύτερο contiguous finite
suffix. Κάθε origin έχει δικό του Chronos `item_id` με `cross_learning=false`:
διαφορετικά test timestamps δεν σχηματίζουν multivariate group. Future-known
covariates δεν υποστηρίζονται ακόμη.

```yaml
model:
  kind: chronos_2_forecaster
  use_features: true
  feature_cols: [close_ret, lag_close_ret_1, atr_over_price_48, ema_trend_48_192]
  outputs: {pred_ret_col: pred_ret, pred_prob_col: pred_prob, pred_is_oos_col: pred_is_oos}
  target:
    kind: future_return_regression
    price_col: close
    returns_col: close_ret
    returns_type: simple
    horizon_bars: 24
    normalize_by_volatility: true
    volatility_col: atr_48
    clip: [-4.0, 4.0]
    fwd_col: target_future_return_h24_atr
    label_col: target_future_return_h24_atr
  split: {method: purged, train_size: 35040, test_size: 4380, step_size: 4380, purge_bars: 24, embargo_bars: 24}
  params:
    model_id: amazon/chronos-2
    source_col: close_ret
    source_kind: returns
    source_returns_type: simple
    lookback: 384
    min_context: 96
    prediction_length: 24
    quantiles: [0.1, 0.5, 0.9]
    batch_size: 64
    freq: 30min
```

Το Chronos-2 παραμένει zero-shot: δεν κάνει fit ή scaler training στα folds.
Για source returns, το `pred_ret` συνθέτει τα forecasted step returns στο target
horizon και εφαρμόζει έπειτα το configured volatility normalization/clip.

### Παράδειγμα classifier model

```yaml
model:
  kind: xgboost_clf
  pred_prob_col: pred_prob
  pred_is_oos_col: pred_is_oos
  preprocessing:
    scaler: robust
  target:
    kind: forward_return
    price_col: close
    horizon: 8
    threshold: 0.001
    label_col: label
  split:
    method: purged
    train_size: 30000
    test_size: 5000
    step_size: 5000
    expanding: true
    purge_bars: 8
    embargo_bars: 8
  feature_cols:
    - close_logret_1
    - close_over_ema_50
    - atr_over_price_14
  params:
    n_estimators: 300
    max_depth: 3
    learning_rate: 0.03
    random_state: 7
```

Το model παράγει `pred_prob`. Για trading, το μετατρέπεις σε signal με
`probability_threshold`, `probability_conviction`, `meta_probability_side` ή
άλλο probability signal.

### Παράδειγμα sequence forecaster

```yaml
model:
  kind: lstm_forecaster
  pred_ret_col: pred_ret
  pred_is_oos_col: pred_is_oos
  target:
    kind: future_return_regression
    price_col: close
    horizon: 12
    label_col: label
    normalize_by_volatility: true
    volatility_col: atr_14
  split:
    method: purged
    train_size: 36000
    test_size: 6000
    step_size: 6000
    purge_bars: 12
    embargo_bars: 12
  feature_cols:
    - close_logret_1
    - atr_over_price_14
    - ppo_hist
    - stoch_rsi_k
  params:
    lookback: 64
    hidden_size: 64
    epochs: 20
    batch_size: 256
    scale_target: true
```

Sequence models χρειάζονται αυστηρό split και αρκετά δεδομένα. Μην συγκρίνεις
training confidence με OOS performance.

### Παράδειγμα staged model/overlay

```yaml
model:
  kind: xgboost_clf
  pred_prob_col: pred_prob_tree
  pred_is_oos_col: pred_is_oos
  target:
    kind: directional_triple_barrier
    direction_col: direction
    candidate_col: signal_candidate
    price_col: close
    open_col: open
    high_col: high
    low_col: low
    volatility_col: atr_14
    label_col: label
  feature_selectors:
    include:
      - startswith: [ema_, atr_, rsi_]

model_stages:
  - kind: tft_forecaster
    enabled: true
    pred_ret_col: pred_ret_tft
    target:
      kind: future_return_regression
      price_col: close
      horizon: 8
      label_col: tft_label
    feature_cols:
      - close_logret_1
      - pred_prob_tree
      - atr_over_price_14
```

Χρησιμοποίησε staged models μόνο όταν ξέρεις ποια outputs παράγει κάθε stage και
ότι τα downstream stages βλέπουν μόνο OOS-safe columns.

## Reinforcement learning

Τα RL models δεν εκπαιδεύουν classifier probability. Μαθαίνουν policy που γράφει
actions ή άμεσο signal. Συνήθως:

- `action_rl`: raw action ή action id.
- `signal_rl`: trading exposure που θα χρησιμοποιήσει το backtest.
- `pred_is_oos`: OOS policy evaluation flag.

Για RL runs, το top-level `signals` συνήθως μένει `none`, επειδή το model
παράγει ήδη `signal_rl`. Το `backtest.signal_col` πρέπει να δείχνει στο
`signal_rl`.

### Παράδειγμα single-asset PPO

```yaml
model:
  kind: ppo_agent
  signal_col: signal_rl
  action_col: action_rl
  pred_is_oos_col: pred_is_oos
  target:
    kind: forward_return
    price_col: close
    horizon: 1
  split:
    method: purged
    train_size: 30000
    test_size: 5000
    step_size: 5000
    expanding: true
    purge_bars: 1
    embargo_bars: 1
  backtest:
    returns_col: close_ret
    returns_type: simple
  feature_cols:
    - close_ret
    - atr_over_price_14
    - close_over_ema_50
    - ppo_hist
  env:
    window_size: 32
    execution_lag_bars: 1
    action_space: continuous
    max_signal_abs: 1.0
    reward:
      cost_per_turnover: 0.00015
      slippage_per_turnover: 0.0001
      inventory_penalty: 0.00002
      switching_penalty: 0.00005
  params:
    total_timesteps: 50000
    learning_rate: 0.0003
    gamma: 0.99
    device: cpu

signals:
  kind: none
  params: {}

backtest:
  engine: vectorized
  signal_col: signal_rl
  returns_col: close_ret
```

Το `signal_rl = 0.75` σημαίνει 75% long exposure στην κλίμακα του environment.
Δεν είναι πιθανότητα 75%.

### Παράδειγμα single-asset DQN

```yaml
model:
  kind: dqn_agent
  signal_col: signal_rl
  action_col: action_rl
  pred_is_oos_col: pred_is_oos
  target:
    kind: forward_return
    price_col: close
    horizon: 1
  split:
    method: purged
    train_size: 30000
    test_size: 5000
    step_size: 5000
    purge_bars: 1
    embargo_bars: 1
  feature_cols:
    - close_ret
    - atr_over_price_14
    - rsi_14
  env:
    window_size: 32
    execution_lag_bars: 1
    action_space: discrete
    max_signal_abs: 1.0
    reward:
      cost_per_turnover: 0.00015
      slippage_per_turnover: 0.0001
      switching_penalty: 0.00005
  params:
    total_timesteps: 25000
    learning_starts: 1000
    buffer_size: 100000
    batch_size: 256
    train_freq: 4
    gradient_steps: 1
    target_update_interval: 1000
    learning_rate: 0.0005
    gamma: 0.99
    device: cpu

signals:
  kind: none
  params: {}

backtest:
  engine: vectorized
  signal_col: signal_rl
```

Το `action_rl` είναι action id. Διάβασέ το μέσω του action mapping του
environment, όχι σαν αριθμητικό score.

### Παράδειγμα portfolio DQN

```yaml
model:
  kind: dqn_portfolio_agent
  signal_col: signal_rl
  action_col: action_rl
  pred_is_oos_col: pred_is_oos
  data_alignment: inner
  target:
    kind: forward_return
    price_col: close
    horizon: 1
  split:
    method: purged
    train_size: 36000
    test_size: 6000
    step_size: 6000
    expanding: true
    max_folds: 4
    purge_bars: 1
    embargo_bars: 1
  backtest:
    returns_col: close_ret
    returns_type: simple
  feature_cols:
    - close_ret
    - ehlers_roofing_atr
    - ehlers_hilbert_amplitude_z_252
    - atr_over_price_14
  env:
    window_size: 32
    execution_lag_bars: 1
    action_space: discrete
    max_signal_abs: 1.0
    reward:
      cost_per_turnover: 0.00015
      slippage_per_turnover: 0.0001
      inventory_penalty: 0.00002
      switching_penalty: 0.00005
  params:
    total_timesteps: 25000
    learning_starts: 1000
    buffer_size: 100000
    batch_size: 256
    train_freq: 4
    gradient_steps: 1
    target_update_interval: 1000
    learning_rate: 0.0005
    gamma: 0.99
    device: cpu

signals:
  kind: none
  params: {}

backtest:
  engine: vectorized
  signal_col: signal_rl
  returns_col: close_ret

portfolio:
  enabled: true
  construction: signal_weights
  long_short: true
  gross_target: 1.0
  constraints:
    min_weight: -0.5
    max_weight: 0.5
    max_gross_leverage: 1.0
    target_net_exposure: 0.0
```

Σε portfolio RL, το `signal_rl` κάθε asset είναι μέρος ενιαίας portfolio action.
Μην αξιολογείς κάθε asset σαν ανεξάρτητο strategy χωρίς να κοιτάς gross/net
exposure, turnover και constraints.

### Πότε προτιμάς RL

- Όταν η απόφαση είναι sequential policy/action και όχι απλή πρόβλεψη label.
- Όταν θέλεις το reward να περιλαμβάνει turnover, costs, inventory penalty ή
  portfolio constraints.
- Όταν έχεις αρκετά δεδομένα για σταθερό OOS policy evaluation.

Αν δεν έχεις καθαρό edge σε supervised labels, το RL σπάνια θα το δημιουργήσει
μαγικά. Ξεκίνα από rule baseline ή supervised meta-labeling και πήγαινε σε RL
μόνο όταν θες να μάθεις policy πάνω σε ήδη χρήσιμα state features.

## Robust scaler στα models

Στα classifier models υποστηρίζονται πλέον:

```yaml
model:
  kind: logistic_regression_clf
  preprocessing:
    scaler: robust
```
