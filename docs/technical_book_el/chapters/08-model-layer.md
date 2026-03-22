## 8. Model Layer

### 8.1 Υλοποιημένα Μοντέλα

- `lightgbm_clf`: gradient boosted decision trees με probabilistic output.
- `logistic_regression_clf`: γραμμικό probabilistic baseline/classifier με σαφή interpretability.
- `sarimax_forecaster`: κλασικό state-space forecaster με optional exogenous features.
- `garch_forecaster`: GARCH(1,1) engine με conditional-volatility forecast και optional AR(1) mean.
- `tft_forecaster`: compact transformer/TFT-style sequence forecaster με quantile outputs.

### 8.2 Layer Boundary

Ο model layer έχει πλέον δύο σαφή υποεπίπεδα:

- `src/models/`: estimator-specific fold engines. Εδώ ζει η καθαρή αριθμητική λογική των SARIMAX, GARCH και TFT folds.
- `src/experiments/support/`: experiment-side targets, metrics και diagnostics. Εδώ χτίζονται forward targets, fold-safe summaries και strict OOS support outputs.
- `src/experiments/models.py`: thin façade προς το `src/models/` για stable registry/import surface.

Αυτό σημαίνει ότι ο estimator code δεν γνωρίζει τίποτε για YAML configs, registries, artifacts ή reporting, ενώ το
experiment layer δεν κρατά πια την εσωτερική αριθμητική υλοποίηση κάθε model family.

Η διάσπαση μέσα στο `src/experiments/support/` είναι επίσης intentional:

- `targets.py`: forward-return target construction και quantile labels.
- `metrics.py`: classification, regression και volatility diagnostics.
- `diagnostics.py`: feature importance, label distributions και prediction-alignment diagnostics.

Το `src/experiments/modeling/` παραμένει μόνο ως compatibility façade για legacy imports και δεν είναι πλέον
source of truth για νέα ανάπτυξη.

### 8.3 Μηχανική του Target

Ο model layer δεν εκπαιδεύεται απευθείας σε raw returns του ίδιου bar αλλά σε future returns ορίζοντα `h`. Αυτό
είναι κρίσιμο επειδή κάθε row στο training set αντιπροσωπεύει “τι γνώριζα μέχρι το `t`” και label “τι συνέβη
από `t+1` έως `t+h`”. Η μέθοδος `trim_train_indices_for_horizon()` κόβει ακριβώς τα training rows που θα
δημιουργούσαν leakage στο test boundary.

### 8.4 Quant / ML Pro Tip Section

#### 8.4.1 Μαθηματική Ανάλυση Feature Engineering

Βασικές οικογένειες features:

- Simple return: $$r_t = \frac{P_t}{P_{t-1}} - 1$$
- Log return: $$\ell_t = \log\left(\frac{P_t}{P_{t-1}}\right)$$
- Rolling volatility: $$\sigma_t^{(w)} = \sqrt{\frac{1}{w-1}\sum_{i=0}^{w-1}(r_{t-i} - \bar r_t)^2}$$
- EWMA volatility: $$\sigma_t^2 = (1-\lambda)r_t^2 + \lambda \sigma_{t-1}^2$$
- SMA ratio: $$z_t^{(w)} = \frac{P_t}{\text{SMA}_w(P)_t} - 1$$
- Price momentum: $$m_t^{(w)} = \frac{P_t}{P_{t-w}} - 1$$
- Return momentum: $$m_t^{(w)} = \sum_{i=0}^{w-1} r_{t-i}$$
- Vol-normalized momentum: $$\tilde m_t^{(w)} = \frac{\sum_{i=0}^{w-1} r_{t-i}}{\sigma_t + \varepsilon}$$

Η κεντρική αρχή είναι ότι όλα τα παραπάνω χρησιμοποιούν μόνο παρελθοντικά ή τρέχοντα δεδομένα στο χρόνο `t`,
ποτέ μελλοντικές παρατηρήσεις. Ακόμη και όταν downstream label είναι forward-looking, το feature space παραμένει
causal.

#### 8.4.2 Στατιστικές Παραδοχές Μοντέλων

- Η logistic regression υποθέτει γραμμική σχέση στο logit space: $$\Pr(y=1\mid x)=\sigma(w^Tx+b)$$.
- Η LightGBM δεν απαιτεί γραμμικότητα, αλλά παραμένει ευαίσθητη σε regime shifts και train/test distribution drift.
- Το SARIMAX υποθέτει state-space δυναμική και σταθερή order structure ανά fold.
- Το GARCH υποθέτει conditional heteroskedasticity με θετικούς και stationarity-consistent parameters.
- Το TFT path υποθέτει ότι η sequence πληροφορία συμπυκνώνεται σε fixed lookback windows.
- Όλα τα μοντέλα υποθέτουν ότι τα labels και features ακολουθούν χρονική σειρά χωρίς sample shuffling.
- Το repository αποφεύγει την ψευδή υπόθεση IID μέσω walk-forward/purged evaluation.

#### 8.4.3 Rationale Επιλογής Μοντέλων

- Η logistic regression προσφέρει baseline με χαμηλή πολυπλοκότητα, υψηλή ερμηνευσιμότητα και σταθερότητα.
- Η LightGBM προσφέρει μη γραμμικές αλληλεπιδράσεις features και καλύτερη ικανότητα αποτύπωσης threshold effects.
- Το SARIMAX παρέχει interpretable parametric forecasting baseline με exogenous support.
- Το GARCH διαχωρίζει την εκτίμηση mean/volatility και είναι χρήσιμος για risk-aware signal sizing.
- Το TFT path επιτρέπει nonlinear sequence modeling με quantile-aware outputs.
- Τα classification models επιστρέφουν probabilities, ενώ τα forecasting models χαρτογραφούνται σε probability-like conviction στο experiment layer.

#### 8.4.4 Loss Functions

- Logistic regression / binary classification loss:

$$
\mathcal{L}(y, p) = -\left[y\log p + (1-y)\log(1-p)\right]
$$

- Brier score για calibration diagnostics:

$$
\text{Brier} = \frac{1}{N}\sum_{i=1}^N (p_i - y_i)^2
$$

Το repository δεν υλοποιεί custom loss για τα classical models, αλλά μετρά `log_loss`, `brier`, `roc_auc`,
`accuracy`, regression diagnostics και volatility diagnostics fold-by-fold. Ο TFT path χρησιμοποιεί quantile loss
ανά output quantile.

#### 8.4.5 Optimization Strategy

- Logistic regression: iterative convex optimization μέσω solver `lbfgs` by default.
- LightGBM: boosted tree ensemble με learning rate, number of estimators, tree depth και leaf constraints.
- SARIMAX: state-space maximum likelihood fitting ανά fold με controlled fallback path.
- GARCH: constrained numerical fit των `(omega, alpha, beta)` με recursive out-of-sample update.
- TFT: mini-batch training με AdamW πάνω σε fixed lookback windows.
- Portfolio mean-variance: numerical constrained optimization με SLSQP.

#### 8.4.6 Regularization Analysis

- Στο logistic regression, η παράμετρος `C` ελέγχει έμμεσα το regularization strength.
- Στο LightGBM, regularization προκύπτει κυρίως από `max_depth`, `num_leaves`, `subsample`, `colsample_bytree`, `min_child_samples` και lower learning rate.
- Στο TFT path, regularization προκύπτει από dropout, hidden size, weight decay και το finite lookback.
- Σε time-series settings, το πιο κρίσιμο regularizer παραμένει η σωστή evaluation protocol και όχι μόνο οι hyperparameters.

#### 8.4.7 Validation Logic και Overfitting Control

- Χρησιμοποιούνται only chronological splits.
- Το `pred_is_oos` ορίζει με ακρίβεια ποιες γραμμές είναι πραγματικά out-of-sample.
- Για forward targets, γίνεται horizon-aware trimming πριν από κάθε fold fit.
- Για quantile labeling, τα thresholds υπολογίζονται από train fold distribution και όχι από global sample distribution.
- Τα fold-level backtest summaries επιτρέπουν ανίχνευση temporal instability και όχι μόνο aggregate score chasing.

#### 8.4.8 Backtesting Assumptions

- Το PnL χρησιμοποιεί lagged position, άρα δεν υπάρχει same-bar execution leakage.
- Η initial entry turnover χρεώνεται ρητά.
- Τα transaction costs είναι linear in turnover, όχι nonlinear market impact model.
- Το drawdown guard είναι deterministic exposure gating mechanism και όχι stochastic risk model.

#### 8.4.9 Risk-Adjusted Return Analysis

- Sharpe ratio: $$\text{Sharpe} = \frac{\mu_a}{\sigma_a}$$ όπου $\mu_a$ η annualized return και $\sigma_a$ η annualized volatility.
- Sortino ratio: $$\text{Sortino} = \frac{\mu_a}{\sigma^-_a}$$ όπου $\sigma^-_a$ η annualized downside volatility.
- Maximum Drawdown: $$\text{MDD} = \min_t\left(\frac{E_t}{\max_{s \le t} E_s} - 1\right)$$
- Calmar ratio: $$\text{Calmar} = \frac{\mu_a}{|\text{MDD}|}$$
- Profit Factor: $$\text{PF} = \frac{\sum r_t^+}{\sum |r_t^-|}$$

#### 8.4.10 RL / Reward Function Σχόλιο

Το README αναφέρει RL ως μελλοντική οικογένεια μοντέλων, αλλά δεν υπάρχει executable RL policy logic ή reward
function στον τρέχοντα κώδικα. Συνεπώς κάθε σχετική αρχιτεκτονική συζήτηση παραμένει roadmap-level και όχι
implemented behavior.
