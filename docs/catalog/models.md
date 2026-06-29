# Κατάλογος Models

Τελευταία ενημέρωση: 2026-06-29

Αυτό το αρχείο τεκμηριώνει τα model kinds που είναι διαθέσιμα μέσω του
`MODEL_REGISTRY` στο `src/models/registry.py`.

Τα models είναι το στάδιο που μαθαίνει σχέση ανάμεσα σε causal features και ένα
target. Το output τους δεν έχει πάντα την ίδια σημασία. Ένα classifier παράγει
probability, ένας regressor/forecaster παράγει expected return ή volatility, ένα
sequence model μπορεί να παράγει embeddings και ένα RL policy παράγει actions ή
portfolio weights. Για αυτό το catalog εξηγεί:

- τι μαθαίνει κάθε model,
- τι πληροφορία δίνουν οι τιμές που παράγει,
- πότε είναι κατάλληλο,
- πώς να διαβάζεις ένα πρακτικό παράδειγμα.

## Πώς διαβάζεις model outputs

Συνηθισμένες output στήλες:

- `pred_prob`: πιθανότητα θετικού class ή πιθανότητα επιτυχίας candidate.
- `pred_ret`: forecast μελλοντικής απόδοσης ή target value.
- `pred_vol`: forecast μεταβλητότητας/risk.
- `pred_is_oos`: flag ότι η πρόβλεψη είναι out-of-sample για το row.
- `event_emb_*`: learned event/sequence embeddings από transformer encoder.
- `signal_rl`: σήμα που προκύπτει από RL policy.
- `action_rl`: raw action ή discrete action id από RL policy.

Γενική ερμηνεία:

- `pred_prob` κοντά στο `0.5`: αβεβαιότητα για binary classifier.
- `pred_prob` υψηλό, π.χ. `0.70`: το model θεωρεί πιο πιθανό το positive
  label ή την επιτυχία του candidate.
- `pred_prob` χαμηλό, π.χ. `0.30`: το positive label θεωρείται λιγότερο πιθανό.
- `pred_ret > 0`: θετικό expected future return στην κλίμακα του target.
- `pred_ret < 0`: αρνητικό expected future return.
- `pred_vol` υψηλό: αυξημένο forecast risk, όχι απαραίτητα short signal.
- `pred_is_oos = 1`: η πρόβλεψη μπορεί να χρησιμοποιηθεί για signal/backtest
  diagnostics.
- `pred_is_oos = 0`: training/in-sample περιοχή, χρήσιμη για fit diagnostics
  αλλά όχι για trading signal.

Σημαντικός κανόνας: signal builders πρέπει να χρησιμοποιούν out-of-sample
predictions. Αν ένα signal βασιστεί σε in-sample `pred_prob` ή `pred_ret`, το
backtest έχει leakage.

## Κατηγορίες

| Κατηγορία | Models | Τι μαθαίνουν |
| --- | --- | --- |
| Tabular classifiers | `logistic_regression_clf`, `elastic_net_clf`, `lightgbm_clf`, `xgboost_clf` | Πιθανότητα binary label ή meta-label από tabular features. |
| Sequence / event classifier | `event_transformer_encoder` | Πιθανότητα και embeddings από rolling event sequences. |
| Return forecasters / regressors | `lightgbm_regressor`, `sarimax_forecaster`, `lstm_forecaster`, `patchtst_forecaster`, `tft_forecaster` | Μελλοντική απόδοση ή continuous target. |
| Volatility / risk forecaster | `garch_forecaster` | Κυρίως forecast volatility/risk από return dynamics. |
| Feature discovery | `tsfresh_extrema_feature_discovery` | PIT-safe tsfresh features και relevance για future extrema labels. |
| Single-asset RL | `ppo_agent`, `dqn_agent` | Policy για actions σε ένα asset. |
| Portfolio RL | `ppo_portfolio_agent`, `dqn_portfolio_agent` | Policy για allocation/actions σε πολλά assets. |

## Tabular classifiers

### `logistic_regression_clf`

Τι μαθαίνει:

- Γραμμική σχέση ανάμεσα στα features και την πιθανότητα του positive class.
- Είναι ισχυρό baseline γιατί είναι απλό, ερμηνεύσιμο και δύσκολα υπερπροσαρμόζει
  σε σχέση με πιο σύνθετα models.

Τι σημαίνουν οι τιμές:

- `pred_prob = 0.65` σημαίνει ότι, σύμφωνα με το γραμμικό μοντέλο, το positive
  label έχει πιθανότητα περίπου 65%.
- Coefficients με θετικό πρόσημο αυξάνουν το log-odds του positive class όταν
  το feature μεγαλώνει.
- Coefficients με αρνητικό πρόσημο μειώνουν το log-odds.

Παράδειγμα:

- Αν εκπαιδεύεις σε `forward_return` label με `threshold = 0`, τότε
  `pred_prob = 0.62` σημαίνει "το μοντέλο εκτιμά 62% πιθανότητα το future return
  να είναι θετικό". Ένα `probability_threshold` signal μπορεί να κάνει long μόνο
  πάνω από `0.58`.

Πότε το προτιμάς:

- Για πρώτο classifier baseline.
- Όταν θέλεις πιο καθαρή ερμηνεία feature directions.
- Όταν έχεις πολλά correlated features και θέλεις να δεις αν υπάρχει γραμμικό
  edge πριν πας σε trees.

### `elastic_net_clf`

Τι μαθαίνει:

- Logistic regression με elastic-net regularization.
- Συνδυάζει L1 sparsity και L2 shrinkage μέσω `l1_ratio`.

Τι σημαίνουν οι τιμές:

- `pred_prob` διαβάζεται όπως στο logistic regression.
- Features με coefficient κοντά στο `0` πρακτικά αγνοούνται.
- Μεγαλύτερο L1 μέρος κάνει το μοντέλο πιο επιλεκτικό σε features.

Παράδειγμα:

- Έχεις 400 technical και normalization features. Το `elastic_net_clf` μπορεί να
  κρατήσει μόνο μικρό subset με μη μηδενικά coefficients. Αν `pred_prob = 0.55`,
  είναι ήπια θετικό signal, αλλά ίσως όχι αρκετό αν τα costs απαιτούν threshold
  `0.60`.

Πότε το προτιμάς:

- Όταν έχεις πολλά features και θέλεις regularized feature selection.
- Όταν θες interpretable classifier αλλά το απλό logistic είναι ασταθές.

### `lightgbm_clf`

Τι μαθαίνει:

- Nonlinear tree-boosting classifier.
- Μαθαίνει thresholds, interactions και nonlinear σχέσεις ανάμεσα σε features.

Τι σημαίνουν οι τιμές:

- `pred_prob` είναι πιθανότητα positive class ή candidate success.
- Υψηλή πιθανότητα σημαίνει ότι πολλά learned tree paths δείχνουν σε θετικό
  outcome.
- Feature importance δείχνει ποια features χρησιμοποιήθηκαν συχνά ή με μεγάλο
  gain, αλλά δεν είναι causal proof.

Παράδειγμα:

- Σε meta-labeling target, `pred_prob = 0.68` δεν σημαίνει "η αγορά θα ανέβει".
  Σημαίνει "το candidate που έδωσε το primary signal έχει υψηλή πιθανότητα να
  πετύχει το target". Το σωστό signal είναι συχνά `meta_probability_side`, όχι
  απλό long/short threshold.

Πότε το προτιμάς:

- Όταν θες ισχυρό tabular baseline.
- Όταν περιμένεις nonlinear interactions, π.χ. momentum που δουλεύει μόνο σε
  συγκεκριμένο volatility regime.
- Όταν θέλεις γρήγορα πειράματα με feature importance diagnostics.

### `xgboost_clf`

Τι μαθαίνει:

- Nonlinear gradient-boosted trees με XGBoost.
- Παρόμοια χρήση με LightGBM, αλλά διαφορετική υλοποίηση και regularization
  συμπεριφορά.

Τι σημαίνουν οι τιμές:

- `pred_prob` είναι πιθανότητα positive class.
- Πιο ακραίες τιμές δείχνουν μεγαλύτερη classifier confidence, όχι απαραίτητα
  καλύτερη calibration.
- Χρειάζεται calibration/threshold diagnostics πριν γίνει trading signal.

Παράδειγμα:

- Αν `pred_prob = 0.80` σε training rows αλλά μόνο `0.53` σε OOS rows, το model
  μάλλον υπερπροσαρμόζει. Για signal πρέπει να κοιτάς OOS distribution και όχι
  training confidence.

Πότε το προτιμάς:

- Όταν θέλεις boosted-tree alternative για σύγκριση με LightGBM.
- Όταν συγκεκριμένα XGBoost params ή constraints ταιριάζουν καλύτερα στο
  πείραμα.

## Sequence και event models

### `event_transformer_encoder`

Τι μαθαίνει:

- Sequence representation γύρω από candidate events.
- Χρησιμοποιεί rolling lookback sequences από features και εκπαιδεύει
  transformer encoder ανά time split.
- Είναι κατάλληλο για candidate-based targets, ειδικά triple-barrier ή
  directional/meta labels.

Τι σημαίνουν οι τιμές:

- `pred_prob`, αν ενεργοποιηθεί, είναι πιθανότητα event success.
- `event_emb_0`, `event_emb_1`, ... είναι learned embeddings, δηλαδή compressed
  αναπαράσταση του πρόσφατου context.
- `pred_is_oos = 1` σημαίνει ότι το event prediction/embedding προέρχεται από
  fold όπου το row ήταν out-of-sample.

Παράδειγμα:

- Ένα pullback candidate έχει παρόμοιο current-bar setup με άλλα, αλλά το
  προηγούμενο 32-bar context δείχνει επιτάχυνση volatility. Το transformer μπορεί
  να το κωδικοποιήσει σε embeddings και να δώσει χαμηλότερο `pred_prob` από ένα
  tabular one-row classifier.

Πότε το προτιμάς:

- Όταν η σειρά των προηγούμενων bars έχει νόημα και όχι μόνο τα current feature
  values.
- Όταν θέλεις embeddings για downstream diagnostics ή second-stage models.
- Όταν έχεις αρκετά candidates για να εκπαιδευτεί sequence model χωρίς έντονο
  overfit.

## Return forecasters και regressors

### `lightgbm_regressor`

Τι μαθαίνει:

- Nonlinear tabular regression για continuous target, συνήθως future return.
- Μπορεί να χρησιμοποιηθεί με `future_return_regression` ή άλλο continuous label.

Τι σημαίνουν οι τιμές:

- `pred_ret > 0` -> θετικό expected return.
- `pred_ret < 0` -> αρνητικό expected return.
- Το μέγεθος έχει νόημα μόνο στην κλίμακα του target. Αν το target είναι
  volatility-normalized, τότε και το `pred_ret` είναι σε volatility units.

Παράδειγμα:

- `pred_ret = 0.003` σε raw-return target σημαίνει expected +0.3%.
- `pred_ret = 1.2` σε volatility-normalized target σημαίνει expected move
  περίπου +1.2 units τοπικής μεταβλητότητας.
- Ένα `forecast_threshold` signal μπορεί να κάνει long μόνο όταν `pred_ret`
  ξεπερνά το κόστος και το noise threshold.

Πότε το προτιμάς:

- Όταν θες να προβλέψεις μέγεθος return, όχι μόνο αν είναι θετικό.
- Όταν θες να μετατρέψεις forecast σε risk-adjusted sizing με
  `forecast_vol_adjusted`.

### `sarimax_forecaster`

Τι μαθαίνει:

- Στατιστικό time-series forecast με SARIMAX λογική.
- Είναι περισσότερο baseline για autocorrelation/seasonality structure παρά
  σύνθετο ML model.

Τι σημαίνουν οι τιμές:

- `pred_ret` δείχνει forecast του continuous target.
- Αν το forecast κινείται κοντά στο `0`, το μοντέλο δεν βρίσκει ισχυρή
  predictable structure στην κλίμακα του target.

Παράδειγμα:

- Σε ημερήσια data, αν υπάρχει εβδομαδιαίο/seasonal pattern, το SARIMAX μπορεί
  να δώσει μικρό θετικό `pred_ret` σε συγκεκριμένες περιόδους. Αν τα OOS metrics
  δεν ξεπερνούν naive baseline, δεν πρέπει να γίνει trading signal.

Πότε το προτιμάς:

- Για απλό statistical benchmark.
- Όταν θες να συγκρίνεις ML forecasters με κλασικό time-series model.

### `garch_forecaster`

Τι μαθαίνει:

- Volatility dynamics από returns.
- Το κύριο νόημα του είναι risk/volatility forecast, όχι directional alpha.

Τι σημαίνουν οι τιμές:

- `pred_vol` υψηλό -> αναμένεται μεγαλύτερη μεταβλητότητα.
- `pred_vol` χαμηλό -> αναμένεται πιο ήρεμο περιβάλλον.
- Αν υπάρχει `pred_ret`, διάβασέ το προσεκτικά ως output της συγκεκριμένης
  forecasting διαδρομής. Το δυνατό σημείο του GARCH είναι το volatility.

Παράδειγμα:

- Αν δύο rows έχουν ίδιο `pred_ret = 0.002`, αλλά το πρώτο έχει
  `pred_vol = 0.006` και το δεύτερο `pred_vol = 0.025`, το δεύτερο έχει πολύ
  χειρότερο signal-to-risk ratio. Ένα volatility-adjusted signal θα δώσει
  μικρότερη θέση στο δεύτερο.

Πότε το προτιμάς:

- Για volatility targeting.
- Για risk filters.
- Για να τροφοδοτήσεις `forecast_vol_adjusted` ή volatility-aware sizing.

### `lstm_forecaster`

Τι μαθαίνει:

- Sequence forecast με LSTM.
- Μαθαίνει temporal state από ordered lookback windows.

Τι σημαίνουν οι τιμές:

- `pred_ret` είναι forecast continuous target από sequence context.
- Υψηλό απόλυτο `pred_ret` σημαίνει ότι το μοντέλο βλέπει ισχυρότερο pattern
  στο πρόσφατο sequence, αλλά θέλει OOS έλεγχο γιατί neural models μπορούν να
  overfit.

Παράδειγμα:

- Αν μετά από συγκεκριμένο volatility squeeze και breakout sequence το model
  δίνει `pred_ret = 0.005`, αυτό σημαίνει ότι το learned recurrent state
  συνδέει τέτοια ακολουθία με θετική future return.

Πότε το προτιμάς:

- Όταν πιστεύεις ότι η σειρά των προηγούμενων bars έχει predictive πληροφορία.
- Όταν έχεις αρκετά δεδομένα και θέλεις neural sequence baseline.

### `patchtst_forecaster`

Τι μαθαίνει:

- Patch-based time-series forecasting representation.
- Χωρίζει το lookback σε patches και μαθαίνει patterns σε μεγαλύτερο context.

Τι σημαίνουν οι τιμές:

- `pred_ret` διαβάζεται ως expected continuous target.
- Το model μπορεί να πιάσει patterns που δεν φαίνονται σε single-row tabular
  features, αλλά η αξιοπιστία κρίνεται από OOS folds.

Παράδειγμα:

- Σε 128-bar lookback, το PatchTST μπορεί να μάθει ότι συγκεκριμένη ακολουθία
  compression -> expansion -> shallow pullback έχει θετικό expected return.
  Το αποτέλεσμα εμφανίζεται ως θετικό `pred_ret`.

Πότε το προτιμάς:

- Για μεγαλύτερα sequence contexts.
- Όταν θέλεις πιο σύγχρονο neural forecasting baseline από LSTM.

### `tft_forecaster`

Τι μαθαίνει:

- Temporal Fusion Transformer style forecasting.
- Στόχος του είναι να συνδυάζει temporal context και feature interactions σε
  sequence forecasting.

Τι σημαίνουν οι τιμές:

- `pred_ret` είναι forecast του continuous target.
- Αν υπάρχουν attention/feature diagnostics στο artifact, βοηθούν στην
  ερμηνεία, αλλά δεν αποδεικνύουν causality.

Παράδειγμα:

- Ένα row με θετικό momentum αλλά υψηλό volatility μπορεί να πάρει χαμηλότερο
  `pred_ret` από row με ίδιο momentum και χαμηλότερο risk, επειδή το sequence
  model βλέπει interaction ανάμεσα σε temporal state και risk regime.

Πότε το προτιμάς:

- Όταν θέλεις ισχυρό neural forecaster με πλουσιότερο temporal context.
- Όταν έχεις αρκετά rows και αυστηρά OOS splits.

## Feature discovery

### `tsfresh_extrema_feature_discovery`

Τι μαθαίνει:

- Δεν είναι κλασικός predictor που παράγει trading probabilities.
- Χτίζει PIT-safe rolling windows, εξάγει tsfresh features και ελέγχει ποια
  features σχετίζονται με future extrema labels:
  `neither`, `local_top`, `local_bottom`.

Τι σημαίνουν οι τιμές:

- `tsfresh_extrema_label` δείχνει αν το anchor row ήταν local top, local bottom
  ή neither σε future horizon.
- `tsfresh_extrema_label_code` κωδικοποιεί τα labels αριθμητικά.
- `tsfresh_extrema_eligible = true` σημαίνει ότι το row είχε πλήρες rolling
  feature window και future label horizon.
- Τα extracted tsfresh columns είναι candidate research features.
- Το metadata `selected_features` δείχνει ποια features πέρασαν relevance
  selection ανά folds.

Παράδειγμα:

- Με `window_size = 48` και `label_horizon = 8`, το component παίρνει τα 48
  προηγούμενα bars ως feature window και κοιτάει τα επόμενα 8 bars για να δει αν
  το anchor είναι local top ή bottom. Αν ένα tsfresh feature επιλέγεται σταθερά
  στα folds, είναι candidate για μελλοντικό feature engineering, όχι αυτόματο
  production signal.

Πότε το προτιμάς:

- Για research και feature discovery.
- Όταν θέλεις να βρεις ποιες time-series ιδιότητες σχετίζονται με local extrema.
- Όταν αποδέχεσαι ότι τα selected features πρέπει μετά να ελεγχθούν σε κανονικό
  model/backtest workflow.

## Single-asset reinforcement learning

### `ppo_agent`

Τι μαθαίνει:

- Policy optimization για ένα asset με PPO.
- Μαθαίνει actions που μεγιστοποιούν reward μέσα στο trading environment,
  λαμβάνοντας υπόψη returns, costs, execution lag και constraints.

Τι σημαίνουν οι τιμές:

- `action_rl` είναι raw action από την policy.
- `signal_rl` είναι η μεταφρασμένη trading έκθεση.
- Θετικό `signal_rl` σημαίνει long exposure.
- Αρνητικό `signal_rl` σημαίνει short exposure, αν το environment το επιτρέπει.
- Απόλυτο μέγεθος μεγαλύτερο σημαίνει μεγαλύτερη έκθεση ή stronger action.

Παράδειγμα:

- Αν `signal_rl = 0.75`, η PPO policy ζητά 75% long exposure στην κλίμακα του
  environment. Αν `signal_rl = -0.40`, ζητά short 40%, εφόσον το config επιτρέπει
  shorting.

Πότε το προτιμάς:

- Όταν το πρόβλημα είναι sequential decision-making και όχι απλή πρόβλεψη label.
- Όταν θέλεις το model να μάθει άμεσα trade actions με costs/reward.
- Όταν έχεις αρκετά δεδομένα για robust OOS policy evaluation.

### `dqn_agent`

Τι μαθαίνει:

- Discrete-action policy για ένα asset με DQN.
- Επιλέγει ανάμεσα σε διακριτές actions, π.χ. flat/long/short ή προκαθορισμένα
  position buckets.

Τι σημαίνουν οι τιμές:

- `action_rl` είναι το discrete action id.
- `signal_rl` είναι η έκθεση που αντιστοιχεί στο action.
- Η απόσταση μεταξύ action ids δεν σημαίνει απαραίτητα γραμμική διαφορά risk.
  Η σημασία ορίζεται από το action mapping του environment.

Παράδειγμα:

- Αν action `0 = flat`, `1 = long`, `2 = short`, τότε `action_rl = 1` γίνεται
  `signal_rl = 1`. Αν έχεις bucketed actions, π.χ. `0%, 50%, 100%`, τότε το
  action id πρέπει να διαβάζεται μέσω του mapping.

Πότε το προτιμάς:

- Όταν θέλεις discrete policy search.
- Όταν οι επιτρεπτές θέσεις είναι λίγες και ξεκάθαρες.

## Portfolio reinforcement learning

### `ppo_portfolio_agent`

Τι μαθαίνει:

- PPO policy για allocation ή actions σε πολλά assets.
- Λαμβάνει υπόψη portfolio constraints, gross exposure targets, asset groups και
  per-asset returns/features.

Τι σημαίνουν οι τιμές:

- Κάθε asset παίρνει δικό του `signal_rl`.
- Θετική τιμή σε asset σημαίνει long allocation ή long action.
- Αρνητική τιμή σημαίνει short allocation αν επιτρέπεται.
- Το σύνολο των per-asset signals πρέπει να διαβάζεται μαζί με portfolio
  constraints, όχι ανεξάρτητα.

Παράδειγμα:

- Για τρία assets, η policy μπορεί να γράψει `GER40 = 0.4`, `US500 = 0.3`,
  `XAUUSD = -0.2`. Αυτό δεν είναι τρία ανεξάρτητα signals. Είναι portfolio
  allocation που πρέπει να αξιολογηθεί με total gross/net exposure και group
  constraints.

Πότε το προτιμάς:

- Όταν η απόφαση είναι allocation μεταξύ assets.
- Όταν ενδιαφέρει correlation, diversification και group risk.

### `dqn_portfolio_agent`

Τι μαθαίνει:

- Discrete-action portfolio policy.
- Επιλέγει από διακριτές portfolio actions ή allocation buckets.

Τι σημαίνουν οι τιμές:

- `action_rl` δείχνει την discrete portfolio action.
- Per-asset `signal_rl` είναι η εφαρμογή αυτής της action στα assets.
- Όπως στο single-asset DQN, το action id διαβάζεται μόνο μέσω του configured
  mapping.

Παράδειγμα:

- Action `3` μπορεί να σημαίνει "long equity basket, flat metals" ή άλλο
  predefined allocation, ανάλογα με το environment. Δεν πρέπει να συγκρίνεται ως
  αριθμός με action `2` χωρίς να δεις το mapping.

Πότε το προτιμάς:

- Όταν θέλεις discrete allocation regimes.
- Όταν το portfolio action space είναι μικρό και σαφές.

## Παραδείγματα YAML

### Classifier για meta-labeling

```yaml
model:
  kind: lightgbm_clf
  target_col: label
  feature_selectors:
    - prefix: ema_
    - prefix: atr_
    - prefix: stoch_
  prediction_col: pred_prob
  split:
    method: walk_forward
```

Ερμηνεία:

- Το `label` πρέπει να έχει φτιαχτεί από target όπως
  `directional_triple_barrier`.
- Το model παράγει `pred_prob`.
- Για trading, χρησιμοποίησε μόνο rows όπου `pred_is_oos = 1`.
- Αν το primary signal έχει side/candidate, το κατάλληλο signal είναι συχνά
  `meta_probability_side`.

### Regressor για return forecast

```yaml
target:
  kind: future_return_regression
  params:
    price_col: close
    horizon: 8
    normalize_by_volatility: true
    volatility_col: atr_14

model:
  kind: lightgbm_regressor
  target_col: label
  prediction_col: pred_ret
  split:
    method: walk_forward
```

Ερμηνεία:

- Το `pred_ret` είναι forecast σε volatility-normalized units.
- `pred_ret = 1.0` σημαίνει περίπου μία μονάδα τοπικής μεταβλητότητας υπέρ της
  θετικής κατεύθυνσης.
- Για signal μπορείς να χρησιμοποιήσεις `forecast_threshold` ή
  `forecast_vol_adjusted`.

### RL policy

```yaml
model:
  kind: ppo_agent
  feature_cols:
    - close_logret_1
    - atr_pct_14
    - rsi_14
  params:
    window_size: 32
```

Ερμηνεία:

- Το model δεν παράγει `pred_prob`.
- Παράγει action/policy output, π.χ. `action_rl` και `signal_rl`.
- Το αποτέλεσμα αξιολογείται ως sequential strategy με costs και execution
  assumptions, όχι ως classifier probability.

## Πρακτικός κανόνας επιλογής

- Θέλεις καθαρό baseline; ξεκίνα με `logistic_regression_clf`.
- Θέλεις regularized interpretable classifier με πολλά features; δοκίμασε
  `elastic_net_clf`.
- Θέλεις ισχυρό tabular classifier; σύγκρινε `lightgbm_clf` και `xgboost_clf`.
- Θέλεις continuous return forecast; χρησιμοποίησε `lightgbm_regressor` ή
  sequence forecaster.
- Θέλεις volatility/risk forecast; χρησιμοποίησε `garch_forecaster`.
- Θέλεις να αξιοποιήσεις temporal sequence context; δοκίμασε
  `event_transformer_encoder`, `lstm_forecaster`, `patchtst_forecaster` ή
  `tft_forecaster`.
- Θέλεις feature research για local extrema; χρησιμοποίησε
  `tsfresh_extrema_feature_discovery`.
- Θέλεις direct policy/action learning; χρησιμοποίησε `ppo_agent`,
  `dqn_agent`, `ppo_portfolio_agent` ή `dqn_portfolio_agent` ανάλογα με single
  asset ή portfolio setup.
