## 7. Configuration Layer

### 7.1 Γενική Φιλοσοφία

Το configuration layer είναι declarative και inheritance-based. Το `extends` επιτρέπει base defaults και
κάθε experiment YAML περιγράφει μόνο τις διαφοροποιήσεις. Η φόρτωση δεν είναι απλό parsing YAML:
περιλαμβάνει path normalization, default injection, semantic validation, env-based secret injection και
runtime normalization.

### 7.2 Configuration Schema ανά Block

- `data`: source, symbol/symbols, interval, date range, alignment, PIT block, storage block, optional API key env.
- `features`: ordered list από transformations.
- `model`: kind, params, runtime overrides, target definition, split definition, explicit feature list.
- `signals`: signal kind και parameters.
- `risk`: cost/slippage, target vol, max leverage, drawdown guard.
- `backtest`: returns column, signal column, periods per year, returns type.
- `portfolio`: enable flag, construction method, constraints, group mappings, optimizer knobs.
- `monitoring`: enable flag, PSI threshold, bin count.
- `execution`: enable flag, capital, price column, current weights, min trade notional.
- `logging`: run name και output directory.

### 7.3 Ανάλυση Config Files

#### `config/base/daily.yaml`

```yaml
data:
  source: yahoo
  interval: 1d
  start: '2010-01-01'
  end: null
  pit:
    timestamp_alignment:
      source_timezone: UTC
      output_timezone: UTC
      normalize_daily: true
      duplicate_policy: last
    corporate_actions:
      policy: none
      adj_close_col: adj_close
    universe_snapshot: {}
runtime:
  seed: 7
  repro_mode: strict
  deterministic: true
  threads: 1
  seed_torch: false
risk:
  cost_per_turnover: 0.0005
  slippage_per_turnover: 0.0
  target_vol: null
  max_leverage: 3.0
  dd_guard:
    max_drawdown: 0.2
    cooloff_bars: 20
backtest:
  periods_per_year: 252
  returns_type: simple
logging:
  output_dir: logs/experiments
```

Ορίζει τα canonical defaults του repository: Yahoo daily data, strict reproducibility, βασικό risk model,
drawdown guard και default logging output directory. Είναι η βάση πάνω στην οποία κληρονομούν τα experiment
configs, επομένως λειτουργεί ως policy baseline.

#### `config/experiments/lgbm_spy.yaml`

```yaml
extends: base/daily.yaml
data:
  symbol: SPY
  start: '2015-01-01'
  end: null
features:
- step: returns
  params:
    log: false
    col_name: close_ret
- step: volatility
  params:
    returns_col: close_ret
    rolling_windows:
    - 20
    - 60
    ewma_spans:
    - 20
- step: trend
  params:
    price_col: close
    sma_windows:
    - 20
    - 50
    ema_spans:
    - 20
- step: indicators
  params:
    price_col: close
    high_col: high
    low_col: low
    volume_col: volume
- step: oscillators
  params:
    price_col: close
    high_col: high
    low_col: low
    rsi_windows:
    - 14
    stoch_windows:
    - 14
    stoch_smooth: 3
- step: lags
  params:
    cols:
    - close_ret
    lags:
    - 1
    - 2
    - 5
model:
  kind: lightgbm_clf
  params:
    n_estimators: 600
    learning_rate: 0.02
    num_leaves: 63
    max_depth: 6
    subsample: 0.8
    colsample_bytree: 0.8
    min_child_samples: 10
    random_state: 7
  split:
    method: time
    train_frac: 0.7
signals:
  kind: probability_threshold
  params:
    prob_col: pred_prob
    upper: 0.58
    lower: 0.42
    signal_name: signal_prob
risk:
  target_vol: 0.1
  max_leverage: 3.0
  cost_per_turnover: 0.0005
  dd_guard:
    max_drawdown: 0.2
    cooloff_bars: 20
backtest:
  returns_col: close_ret
  signal_col: signal_prob
  periods_per_year: 252
  returns_type: simple
logging:
  run_name: lgbm_spy_v1
```

Single-asset ML experiment με LightGBM classifier, time split και probability-threshold signal mapping.

#### `config/experiments/logreg_spy.yaml`

```yaml
extends: base/daily.yaml
data:
  symbol: SPY
  start: '2015-01-01'
  end: null
  storage:
    mode: live_or_cached
    dataset_id: spy_daily_core
    save_raw: true
    save_processed: true
features:
- step: returns
  params:
    log: false
    col_name: close_ret
- step: volatility
  params:
    returns_col: close_ret
    rolling_windows:
    - 20
    - 60
    ewma_spans:
    - 20
- step: trend
  params:
    price_col: close
    sma_windows:
    - 20
    - 50
    ema_spans:
    - 20
- step: lags
  params:
    cols:
    - close_ret
    lags:
    - 1
    - 2
    - 5
model:
  kind: logistic_regression_clf
  params:
    max_iter: 1000
    C: 0.5
  split:
    method: walk_forward
    train_size: 504
    test_size: 63
    step_size: 63
    expanding: true
  target:
    kind: forward_return
    price_col: close
    horizon: 5
signals:
  kind: probability_threshold
  params:
    prob_col: pred_prob
    upper: 0.55
    lower: 0.45
    signal_name: signal_prob
backtest:
  returns_col: close_ret
  signal_col: signal_prob
  periods_per_year: 252
  returns_type: simple
monitoring:
  enabled: true
  psi_threshold: 0.15
  n_bins: 10
execution:
  enabled: true
  mode: paper
  capital: 1000000
  price_col: close
  min_trade_notional: 1000
logging:
  run_name: logreg_spy_v1
```

Single-asset experiment με logistic regression, walk-forward evaluation, snapshot persistence, monitoring και
paper execution. Είναι το πιο κατάλληλο reference config για onboarding because activates many layers at once.

#### `config/experiments/portfolio_logreg_macro.yaml`

```yaml
extends: base/daily.yaml
data:
  symbols:
  - SPY
  - TLT
  - GLD
  start: '2015-01-01'
  end: null
  alignment: inner
  storage:
    mode: live_or_cached
    dataset_id: macro_triad_daily
    save_raw: true
    save_processed: true
features:
- step: returns
  params:
    log: false
    col_name: close_ret
- step: volatility
  params:
    returns_col: close_ret
    rolling_windows:
    - 20
    ewma_spans:
    - 20
- step: trend
  params:
    price_col: close
    sma_windows:
    - 20
    - 50
    ema_spans:
    - 20
- step: lags
  params:
    cols:
    - close_ret
    lags:
    - 1
    - 2
    - 5
model:
  kind: logistic_regression_clf
  params:
    max_iter: 1000
    C: 0.5
  feature_cols:
  - lag_close_ret_1
  - lag_close_ret_2
  - lag_close_ret_5
  - vol_rolling_20
  - vol_ewma_20
  - close_over_sma_20
  - close_over_sma_50
  split:
    method: walk_forward
    train_size: 504
    test_size: 63
    step_size: 63
    expanding: true
  target:
    kind: forward_return
    price_col: close
    horizon: 5
signals:
  kind: probability_conviction
  params:
    prob_col: pred_prob
    signal_name: signal_prob_size
    clip: 1.0
portfolio:
  enabled: true
  construction: signal_weights
  gross_target: 1.0
  long_short: true
  constraints:
    min_weight: -0.6
    max_weight: 0.6
    max_gross_leverage: 1.0
    target_net_exposure: 0.0
    turnover_limit: 0.5
  asset_groups:
    SPY: equity
    TLT: rates
    GLD: commodities
backtest:
  returns_col: close_ret
  signal_col: signal_prob_size
  periods_per_year: 252
  returns_type: simple
monitoring:
  enabled: true
  psi_threshold: 0.15
  n_bins: 10
execution:
  enabled: true
  mode: paper
  capital: 1000000
  price_col: close
  min_trade_notional: 2500
logging:
  run_name: portfolio_logreg_macro_v1
```

Multi-asset portfolio experiment με conviction-sized signals και constrained signal-weight portfolio
construction πάνω σε `SPY`, `TLT`, `GLD`. Αποτελεί το πληρέστερο παράδειγμα orchestrated portfolio flow.

#### `config/experiments/trend_spy.yaml`

```yaml
extends: base/daily.yaml
data:
  symbol: 6E=F
  start: '2020-01-01'
  end: null
features:
- step: returns
  params:
    log: true
    col_name: close_logret
- step: volatility
  params:
    returns_col: close_logret
    rolling_windows:
    - 20
    - 60
    ewma_spans:
    - 20
- step: trend
  params:
    price_col: close
    sma_windows:
    - 20
    - 50
    ema_spans:
    - 20
- step: trend_regime
  params:
    price_col: close
    base_sma_for_sign: 50
    short_sma: 20
    long_sma: 50
model:
  kind: none
signals:
  kind: trend_state
  params:
    state_col: close_trend_state_sma_20_50
    mode: long_short_hold
    signal_name: signal_trend_state
risk:
  target_vol: 0.1
  max_leverage: 3.0
  cost_per_turnover: 0.0005
  dd_guard:
    max_drawdown: 0.2
    cooloff_bars: 20
backtest:
  returns_col: close_logret
  signal_col: signal_trend_state
  periods_per_year: 252
  returns_type: log
logging:
  run_name: trend_spy_v1
```

Πείραμα rule-based trend strategy χωρίς μοντέλο. Ελέγχει ότι ο orchestrator υποστηρίζει “model.kind: none”
και μπορεί να βασιστεί αποκλειστικά σε engineered state features και deterministic signals.

### 7.4 Environment Variables

- `PYTHONHASHSEED`: ρυθμίζεται programmatically από το reproducibility layer.
- `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS`: περιορίζονται όταν ζητείται deterministic ή fixed-thread runtime.
- `ALPHAVANTAGE_API_KEY`: απαιτείται όταν χρησιμοποιείται Alpha Vantage και δεν δοθεί explicit `api_key`.
- Προαιρετικά arbitrary env var μέσω `data.api_key_env`: ο loader διαβάζει το όνομα και inject-άρει secret στο `data.api_key`.
