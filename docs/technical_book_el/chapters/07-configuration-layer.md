## 7. Configuration Layer

### 7.1 Γενική Φιλοσοφία

Το configuration layer είναι declarative και explicit-first. Τα tracked experiment YAMLs είναι
πλήρως self-contained και δεν βασίζονται σε checked-in parent configs. Η φόρτωση δεν είναι απλό parsing YAML:
περιλαμβάνει path normalization, default injection, semantic validation, env-based secret injection,
runtime normalization και typed resolved config objects.

Η υλοποίηση έχει πλέον σαφή modules:

- `src/utils/config.py`: stable façade με `load_experiment_config(...)` και `load_experiment_config_typed(...)`.
- `src/utils/config_loader.py`: path resolution, self-contained YAML loading, explicit rejection of `extends`, env secret injection.
- `src/utils/config_defaults.py`: default policies ανά block και intraday-aware annualization defaults.
- `src/utils/config_validation.py`: semantic validation και registry-aware checks.
- `src/utils/config_schemas.py`: typed resolved config objects για το orchestration layer.

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

Τα tracked configs του repository είναι πλέον standalone. Κάθε experiment YAML περιέχει ολόκληρο το
definition του: data/storage, feature steps, model block, split policy, signal mapping, risk, backtest,
monitoring και logging, χωρίς checked-in `config/base/*.yaml` parents. Ο loader απορρίπτει πλέον ρητά κάθε
`extends`.

Στο current repo state υπάρχουν δύο tracked experiment YAMLs:

#### `config/experiments/btcusd_1h_dukas_lightgbm_triple_barrier_garch_long_oos.yaml`

- local ingest από `data/raw/dukas_copy_bank/*.csv` μέσω `data.storage.load_path`
- `1h` BTCUSD state με OHLCV, regime features και volume-aware inputs
- `lightgbm_clf` με `triple_barrier` target
- `garch` overlay για volatility/risk-aware signal scaling
- long-OOS walk-forward evaluation χωρίς fixed `max_folds`

#### `config/experiments/btcusd_1h_dukas_xgboost_triple_barrier_garch_long_oos.yaml`

- ίδιο data / target / split contract με το LightGBM config
- `xgboost_clf` αντί για `lightgbm_clf`
- explicit `dukascopy_csv` external source με `data.storage.load_path`
- leaner ablation feature set με regime, RSI, Bollinger position, ADX και volume-aware inputs
- ίδιο signal, risk, backtest, monitoring και reporting surface για apples-to-apples comparison

Ενδεικτικό pattern self-contained YAML:

```yaml
data:
  source: dukascopy_csv
  symbol: BTCUSD
  interval: 1h
  storage:
    mode: cached_only
    load_path: data/raw/dukas_copy_bank/BTCUSD.csv
features:
  - step: returns
    params:
      log: true
      col_name: close_logret
  - step: volatility
    params:
      returns_col: close_logret
model:
  kind: xgboost_clf
  feature_cols:
    - lag_close_logret_1
    - close_rsi_14
    - regime_vol_ratio_24_168
  target:
    kind: triple_barrier
    price_col: close
    open_col: open
    high_col: high
    low_col: low
    max_holding: 24
  split:
    method: walk_forward
    train_size: 8760
    test_size: 336
    step_size: 336
    expanding: true
signals:
  kind: probability_vol_adjusted
  params:
    prob_col: pred_prob
    vol_col: pred_vol
    lower: 0.45
    upper: 0.55
    min_signal_abs: 0.01
```

Όταν οι παράμετροι feature generation αλλάζουν από Optuna και τα output column names αλλάζουν
(π.χ. `close_rsi_14` σε `close_rsi_21`), προτίμησε `model.feature_selectors` αντί για σταθερό
`feature_cols`:

```yaml
model:
  kind: xgboost_clf
  feature_selectors:
    exact:
      - shock_strength
    include:
      - startswith: close_rsi_
      - startswith: bb_percent_b_
      - regex: "^regime_vol_ratio_[0-9]+_[0-9]+$"
    exclude:
      - startswith: target_
      - startswith: pred_
      - startswith: signal_
    strict:
      min_count: 5
```

Οι selectors γίνονται resolve μετά τον υπολογισμό των features και πριν το training. Αν ένα
`include` rule δεν βρει columns ή το τελικό πλήθος πέσει κάτω από `strict.min_count`, το run
αποτυγχάνει νωρίς αντί να εκπαιδεύσει σιωπηλά με λάθος feature set.

Το ίδιο pattern ισχύει και για feature transforms ή signal filters που χρειάζονται generated
feature columns. Για single-column inputs χρησιμοποίησε selector που πρέπει να κάνει match ακριβώς
ένα column:

```yaml
features:
  - step: vol_normalized_momentum
    params:
      returns_col: close_logret
      vol_col: null
      vol_window: 24
      windows: [6, 24]
  - step: feature_transforms
    params:
      transforms:
        - kind: ratio
          numerator_selector:
            exact: lag_close_logret_1
          denominator_selector:
            regex: "^vol_rolling_[0-9]+$"
          output_col: lag_close_logret_1_over_selected_vol
signals:
  kind: probability_vol_adjusted
  params:
    activation_filters:
      - selector:
          regex: "^regime_vol_ratio_[0-9]+_[0-9]+$"
        op: ge
        value: 1.0
```

Σημείωση για sources:

- `yahoo`, `alpha`, `twelve_data`, `twelve`: provider-backed ingest
- `dukascopy_csv`: explicit external CSV source και απαιτεί `data.storage.load_path`

### 7.4 Environment Variables

- `PYTHONHASHSEED`: ρυθμίζεται programmatically από το reproducibility layer.
- `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS`: περιορίζονται όταν ζητείται deterministic ή fixed-thread runtime.
- `ALPHAVANTAGE_API_KEY`: απαιτείται όταν χρησιμοποιείται Alpha Vantage και δεν δοθεί explicit `api_key`.
- Προαιρετικά arbitrary env var μέσω `data.api_key_env`: ο loader διαβάζει το όνομα και inject-άρει secret στο `data.api_key`.
