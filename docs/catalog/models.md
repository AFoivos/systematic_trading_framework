# Model Catalog

Τελευταία ενημέρωση: 2026-06-28

Αυτό το αρχείο τεκμηριώνει τα model kinds που είναι διαθέσιμα μέσω του
`MODEL_REGISTRY` στο `src/models/registry.py`. Τα models μετατρέπουν ήδη
υπολογισμένα feature columns και target definitions σε out-of-sample
predictions, forecasts, probabilities ή RL action signals.

Το `model.kind: none` είναι no-model mode του experiment pipeline και δεν είναι
entry του `MODEL_REGISTRY`. Χρησιμοποιείται για rules-only experiments,
feature/target labs και post-signal target diagnostics.

## Γενικές αρχές

- Τα models δεν φορτώνουν data. Data loading, PIT hardening και feature
  generation έχουν ήδη γίνει πριν από το model stage.
- Το target μπορεί να κοιτάει future bars μόνο στο target-construction stage.
  Target output columns δεν πρέπει να μπαίνουν ποτέ σε model features.
- Feature selection γίνεται από `feature_cols` ή `feature_selectors`. Αν δεν
  δοθούν, το runtime προσπαθεί να επιλέξει numeric non-target columns.
- Scalers/preprocessing γίνονται fit μόνο μέσα στο train fold και εφαρμόζονται
  στο αντίστοιχο test fold.
- Predictions που χρησιμοποιούνται από signals πρέπει να είναι out-of-sample.
  In-sample probabilities/forecasts είναι leakage για trading evaluation.
- Χρονική διάσπαση γίνεται μέσω `model.split`: `time`, `walk_forward` ή
  `purged`, ανάλογα με το model/target contract.
- Για strict reproducibility, χρησιμοποίησε deterministic runtime settings,
  seed και controlled thread count.

## Common YAML Contract

Τυπικό classifier/regressor block:

```yaml
model:
  kind: xgboost_clf
  feature_cols: null
  feature_selectors:
    families: [returns_lags, volatility, trend]
  preprocessing:
    scaler: none
  split:
    method: purged
    train_size: 0.70
    test_size: 0.30
    purge_bars: 16
    embargo_bars: 0
  target:
    kind: forward_return
    price_col: close
    horizon: 8
    label_col: label
  pred_prob_col: pred_prob
  pred_is_oos_col: pred_is_oos
  params:
    n_estimators: 300
    learning_rate: 0.05
```

Common outputs:

- Classifiers: `pred_prob_col`, default συνήθως `pred_prob`.
- Forecasters/regressors: `pred_ret_col` και συχνά derived `pred_prob_col`.
- OOS marker: `pred_is_oos_col`, συνήθως `pred_is_oos`.
- RL models: action/signal columns, συνήθως `signal_rl` ή configured
  `signal_col`.

## Feature Selectors

Τα model features μπορούν να οριστούν explicit:

```yaml
model:
  feature_cols:
    - close_ret
    - atr_over_price_14
    - rolling_r2_96
```

ή με selectors:

```yaml
model:
  feature_selectors:
    families: [returns_lags, volatility, trend, momentum]
    include:
      - {startswith: "ehlers_tp_cond_"}
    exclude:
      - {startswith: "target_"}
```

Χρησιμοποίησε selectors με προσοχή: πρέπει να αποκλείουν target outputs,
future diagnostics, realized trade metrics και οποιαδήποτε στήλη παράγεται
μετά το prediction timestamp.

## Preprocessing

Supported scaler values για classifier models:

- `none`: δεν εφαρμόζεται scaler.
- `standard`: standard scaler fit μόνο στο train fold.
- `robust`: robust scaler fit μόνο στο train fold.

Tree models συνήθως δεν χρειάζονται scaler. Linear models συχνά χρειάζονται
`standard` ή `robust`, ειδικά όταν τα features έχουν διαφορετικές μονάδες.

## none

No-model mode στο experiment pipeline.

- Δεν εκπαιδεύει model.
- Δεν παράγει probabilities ή forecasts.
- Επιτρέπει rules-only signals και target-only diagnostics όταν το config έχει
  top-level `target` ή `model.target` με supported target kind.

Χρησιμότητα:

- Baseline backtests για deterministic signals.
- Feature/target lab runs.
- Manual candidate -> target diagnostics πριν προστεθεί meta model.

## logistic_regression_clf

Sklearn logistic regression classifier.

- Target: binary target, συνήθως `forward_return`, `triple_barrier`,
  `directional_triple_barrier`, `r_multiple` ή candidate-based target όπου
  υποστηρίζεται από validation.
- Output: probability column για positive class.
- Default wrapper behavior: θέτει practical defaults όπως `max_iter` και
  standard scaler όταν δεν δοθεί preprocessing.

Χρησιμότητα:

- Interpretable linear baseline.
- Καλό sanity check για feature direction και calibration.
- Χρήσιμο πριν από πιο expressive tree/boosting models.

Causality:

- Τα coefficients πρέπει να εκπαιδεύονται μόνο σε train fold.
- Το probability signal πρέπει να χρησιμοποιεί OOS predictions.

## elastic_net_clf

Elastic-net regularized classifier.

- Target: binary classifier target.
- Output: probability/decision score ανάλογα με shared classifier pipeline.
- Regularization βοηθά σε πολλά correlated features.

Χρησιμότητα:

- Sparse/regularized linear baseline.
- Καλύτερο από απλό logistic όταν υπάρχουν πολλά correlated technical
  features.
- Χρήσιμο για feature selection diagnostics χωρίς να πας απευθείας σε boosting.

Causality:

- Scaling και regularization path πρέπει να είναι fold-safe.
- Μην κάνεις global feature pruning με future labels πριν το split.

## xgboost_clf

XGBoost binary classifier.

- Target: binary classification target.
- Output: `pred_prob_col`.
- Runtime κάνει probe για XGBoost availability και θέτει deterministic-ish
  defaults όπως seed/thread handling όπου υποστηρίζεται.

Χρησιμότητα:

- Nonlinear meta-labeling πάνω σε manual/rule candidates.
- Captures threshold interactions μεταξύ trend, volatility, pullback και timing
  features.
- Καλό production-grade baseline όταν χρειάζεται nonlinear classifier.

Causality:

- Feature importance και validation metrics πρέπει να βασίζονται σε OOS folds.
- Target outputs, barrier diagnostics και realized trade columns δεν είναι
  επιτρεπτά features.

## lightgbm_clf

LightGBM binary classifier μέσω του shared classifier pipeline.

- Target: binary classification target.
- Output: `pred_prob_col` και optional `pred_is_oos_col`.
- Υποστηρίζει LightGBM params όπως `n_estimators`, `learning_rate`,
  `num_leaves`, `max_depth`, `subsample`, `colsample_bytree`.

Χρησιμότητα:

- Fast nonlinear classifier για μεγάλα feature sets.
- Κατάλληλο για meta-labeling και probability filters.
- Καλό για Optuna search σε tabular technical features.

Causality:

- Το runtime πρέπει να κρατά train/test split χρονικά καθαρό.
- Calibration, αν ενεργοποιηθεί, πρέπει να γίνεται σε train/calibration
  subset, όχι στο full dataset.

## event_transformer_encoder

Transformer encoder για event/candidate representations.

- Target: candidate/event-style classification target, συνήθως path-dependent.
- Output: embedding columns και optional probability column.
- Χρησιμοποιείται όταν θες learned representation πάνω σε event windows αντί
  για απλό flat tabular row.

Χρησιμότητα:

- Candidate/event meta-labeling με richer temporal context.
- Representation learning για event embeddings που μπορούν να τροφοδοτήσουν
  downstream models ή diagnostics.

Causality:

- Το event window πρέπει να περιέχει μόνο πληροφορία διαθέσιμη μέχρι το event
  timestamp.
- Embeddings που παράγονται in-sample δεν πρέπει να χρησιμοποιούνται ως
  execution input χωρίς OOS discipline.

## lightgbm_regressor

LightGBM regression forecaster.

- Target: συνήθως `future_return_regression`, ή configured regression target
  από supported path-dependent targets.
- Output: `pred_ret_col`, και όπου χρειάζεται probability-like transform σε
  `pred_prob_col`.
- Μπορεί να χρησιμοποιήσει exogenous feature columns.

Χρησιμότητα:

- Direct return/alpha forecasting.
- Ranking ή sizing workflows όπου continuous forecast είναι πιο χρήσιμο από
  binary probability.
- Portfolio selection με expected return estimates.

Causality:

- Forecast horizon πρέπει να συμφωνεί με split purge/embargo.
- Μην χρησιμοποιείς future realized return columns ως features.

## sarimax_forecaster

Statistical time-series forecaster.

- Target: forward/future return style regression target.
- Features: μπορεί να λειτουργήσει με ή χωρίς exogenous features, ανά config.
- Output: forecast return column.

Χρησιμότητα:

- Classical baseline για autocorrelation/seasonality.
- Comparator απέναντι σε ML forecasters.
- Καλή επιλογή όταν θες interpretable statistical assumptions.

Causality:

- Το fit πρέπει να γίνεται ανά train fold.
- Forecasts στο test fold πρέπει να ξεκινούν μετά το train window.

## garch_forecaster

GARCH-style volatility/return forecaster.

- Target: forward/future return or volatility-style forecast, ανά config.
- Input: returns column, συνήθως `close_ret` ή `close_logret`.
- Output: forecast/volatility diagnostics through the forecasting pipeline.

Χρησιμότητα:

- Volatility regime and risk forecasting baseline.
- Overlay candidate για models που χρειάζονται volatility-adjusted decisions.
- Diagnostic comparator για clustering volatility assumptions.

Causality:

- GARCH state fit μόνο στο train fold.
- Volatility forecasts πρέπει να είναι OOS όταν χρησιμοποιούνται για signals ή
  sizing.

## lstm_forecaster

Sequence forecaster με LSTM backend.

- Target: regression/forecast target.
- Inputs: lagged/sequential windows από configured features.
- Output: forecast return/probability-derived columns.

Χρησιμότητα:

- Nonlinear sequence baseline όταν row-wise features δεν αρκούν.
- Μπορεί να συλλάβει temporal state πέρα από fixed helper lags.

Causality:

- Sequence windows πρέπει να τελειώνουν στο prediction timestamp.
- Scaling και sequence construction πρέπει να γίνονται μέσα στο fold contract.

## patchtst_forecaster

PatchTST-style deep time-series forecaster.

- Target: regression/forecast target.
- Inputs: patched sequence windows.
- Output: forecast return/probability-derived columns.
- Validation υποστηρίζει quantile-related config checks όπου υπάρχουν.

Χρησιμότητα:

- Deep forecasting baseline για longer context windows.
- Χρήσιμο όταν patterns είναι distributed μέσα σε sequence segments.

Causality:

- Patches δεν πρέπει να περιλαμβάνουν future bars.
- Evaluation πρέπει να βασίζεται σε OOS forecast rows.

## tft_forecaster

Temporal Fusion Transformer-style forecaster.

- Target: regression/forecast target, συχνά log/simple forward returns.
- Inputs: configured feature sequences and covariates.
- Output: forecast return/probability-derived columns.

Χρησιμότητα:

- Rich deep forecasting workflow με covariates.
- Κατάλληλο για multi-feature sequence forecasting experiments.

Causality:

- Known-future covariates πρέπει να είναι πραγματικά known in advance. Αν δεν
  είναι, είναι leakage.
- Scalers/encoders πρέπει να είναι train-fold safe.

## tsfresh_extrema_feature_discovery

Experimental discovery model για extrema/feature hypothesis exploration.

- Δεν είναι standard execution model.
- Διαχειρίζεται δικά του future-horizon labels και validation αποτρέπει
  explicit `model.target`.
- Χρησιμοποιείται για research discovery, όχι για production execution path.

Χρησιμότητα:

- Exploratory feature discovery.
- Statistical screening hypotheses around extrema.

Causality:

- Τα discovered features/hypotheses πρέπει να ξαναδοκιμάζονται σε καθαρό OOS
  workflow πριν θεωρηθούν tradable.
- Μην μεταφέρεις exploratory discovered logic σε production config χωρίς
  explicit validation.

## ppo_agent

Single-asset PPO reinforcement-learning agent.

- Scope: one asset at a time.
- Output: configured action/signal column.
- Environment settings βρίσκονται κάτω από `model.env`; rewards/execution
  constraints συνδέονται με risk/backtest assumptions.

Χρησιμότητα:

- Policy learning για position/exposure decisions.
- Research σε action/reward formulations πέρα από supervised labels.

Causality:

- Observation window πρέπει να περιέχει μόνο current/past features.
- Reward uses future realized returns by design during training, αλλά policy
  observations δεν πρέπει να έχουν future information.
- Evaluation πρέπει να γίνεται σε OOS periods.

## dqn_agent

Single-asset DQN reinforcement-learning agent.

- Scope: one asset at a time.
- Action space: discrete; validation rejects incompatible continuous-only DQN
  settings.
- Output: configured action/signal column.

Χρησιμότητα:

- Discrete position policy experiments.
- Useful when action templates are naturally flat/long/short or fixed exposure
  levels.

Causality:

- Same observation/reward separation as PPO.
- Position grid/action definitions must be fixed before evaluation.

## ppo_portfolio_agent

Portfolio-level PPO reinforcement-learning agent.

- Scope: multiple assets jointly.
- Output: per-asset signal/action frames.
- Requires portfolio-aware environment, asset alignment and portfolio
  constraints.

Χρησιμότητα:

- Joint allocation policy across assets.
- Research on portfolio-level reward functions and constraints.

Causality:

- Cross-asset observations must be synchronized point-in-time.
- Portfolio weights/actions must not depend on future returns, future
  membership changes or post-hoc feasible universe filters.

## dqn_portfolio_agent

Portfolio-level DQN reinforcement-learning agent.

- Scope: multiple assets jointly.
- Action space: discrete templates across assets.
- Output: per-asset signal/action frames.

Χρησιμότητα:

- Discrete portfolio allocation experiments.
- Useful when portfolio actions can be enumerated as templates.

Causality:

- Same PIT synchronization requirements as portfolio PPO.
- Discrete action templates must be declared ex ante and evaluated OOS.

## Model Stages

Το framework υποστηρίζει `model_stages` για chained workflows, π.χ. forecast
stage -> classifier stage. Κάθε stage πρέπει να έχει unique output columns και
να σέβεται το ίδιο temporal contract με standalone models.

Παράδειγμα:

```yaml
model_stages:
  - name: forecast
    kind: sarimax_forecaster
    pred_ret_col: sarimax_pred_ret
  - name: classifier
    kind: logistic_regression_clf
    pred_prob_col: pred_prob
```

Προσοχή:

- Stage outputs που είναι in-sample δεν πρέπει να γίνονται features για επόμενο
  stage χωρίς OOS construction.
- Κάθε stage πρέπει να δηλώνει outputs ώστε να αποφεύγονται column collisions.

## Signals After Models

Τα model outputs δεν είναι από μόνα τους trades. Συνήθως περνάνε σε signal:

- `probability_threshold` για binary classifier probabilities.
- `probability_vol_adjusted` για probability plus volatility sizing.
- `meta_probability_side` για candidate/meta-labeling workflows.
- `forecast_threshold` ή `forecast_vol_adjusted` για return forecasts.

Το signal πρέπει να διαβάζει OOS prediction columns. Αν το prediction column
περιέχει train-fold fitted/in-sample values, το backtest overstated.

## Reproducibility Checklist

- Δήλωσε `runtime.seed`, deterministic mode και threads όταν συγκρίνεις runs.
- Χρησιμοποίησε purged split όταν το target horizon ή barriers δημιουργούν
  overlap μεταξύ train/test observations.
- Κράτα τα `feature_cols`/selectors auditably explicit σε final experiments.
- Έλεγξε ότι `pred_is_oos_col` υπάρχει όταν το signal απαιτεί model output.
- Μην βάζεις `label`, `target_*`, barrier columns, realized R, hit/exit
  diagnostics ή future returns σε model features.
