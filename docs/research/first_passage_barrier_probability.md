# First-Passage Barrier Probability — Research Report

## Συμπέρασμα

Υλοποιήθηκε πλήρες multiclass research experiment που προβλέπει ποιο volatility-scaled barrier θα αγγίξει πρώτο η τιμή: lower (`-1`), κανένα (`0`) ή upper (`+1`). Το σύστημα δεν χρησιμοποιεί previous-return continuation ως trading thesis. Οι last-return continuation/reversal κανόνες υπάρχουν μόνο ως fold-local baselines σύγκρισης.

Το canonical development run του multinomial logistic model στο XAUUSD 30m, έως το τέλος του 2024, έδωσε θετικό αλλά περιορισμένο OOS net αποτέλεσμα:

| Metric | Development OOS result |
|---|---:|
| OOS rows | 21,900 |
| Classification rows | 21,626 |
| Net cumulative return | 1.578% |
| Gross PnL | 3.144% |
| Total costs | 1.529% |
| Cost / gross PnL | 49.79% |
| Annualised return | 0.869% |
| Annualised volatility | 1.954% |
| Sharpe | 0.452 |
| Sortino | 0.634 |
| Maximum drawdown | -1.810% |
| Profit factor | 1.066 |
| Trades | 144 |
| Trade hit rate | 55.56% |
| Mean / median net trade | 0.0111% / 0.1027% |
| Mean / median holding period | 4.61 / 3 bars |
| Mean MFE / MAE | 0.855R / -0.843R |
| Mean giveback | 0.815R |
| No-hit time exits | 22 trades; 0.0162% mean net; 63.64% hit rate |
| Flat / long / short rate | 98.443% / 1.511% / 0.046% |

Αυτό **δεν αποτελεί claim ύπαρξης alpha**. Το αποτέλεσμα είναι development-only, έχει μικρό trade sample και είναι σχεδόν αποκλειστικά long. Τα tree models είχαν καλύτερα probability scores αλλά αρνητικό net PnL, τα μεμονωμένα feature groups ήταν όλα αρνητικά και το cost stress μηδένισε σχεδόν το αποτέλεσμα ήδη στο `cost ×2`. Δεν εκτελέστηκε το structurally isolated confirmation segment, ούτε υπάρχει πλέον απολύτως pristine 2025+ holdout.

## Dataset και scope

- Dataset: `data/raw/dukascopy_30m_clean/xauusd_30m.csv`.
- Asset/timeframe: XAUUSD 30m, επειδή δεν υπάρχει ενσωματωμένο πραγματικό EURUSD M1 dataset στο repository.
- Development config window: `2020-01-01` έως exclusive `2024-12-31`· ο loader παρήγαγε 59,090 rows, με τελευταίο bar `2024-12-30 23:30 UTC`.
- Canonical OOS evaluation: 5 expanding purged walk-forward folds, 4,380 bars ανά test fold.
- Canonical feature set: 72 causal state features, χωρίς τα experimental microstructure proxies.
- Confirmation config: structurally απομονωμένο `2025-01-01+` test segment.

Σημαντική governance σημείωση: πριν κλειδωθεί το development end date εκτελέστηκε full-range implementation diagnostic για να ελεγχθεί το pipeline. Επομένως το διαθέσιμο 2025+ tail δεν μπορεί πλέον να χαρακτηριστεί απολύτως pristine ως προς την ανθρώπινη ερευνητική διαδικασία. Το `final_holdout_v1.yaml` παραμένει χρήσιμο ως structurally isolated confirmation run, αλλά για πραγματικά untouched validation απαιτείται νέο μελλοντικό sample ή εξωτερικό dataset.

## Αρχιτεκτονική

Η υλοποίηση επεκτείνει τις υπάρχουσες registries και το υπάρχον experiment pipeline:

1. Τα causal feature builders παράγουν κατάσταση αγοράς στο close του bar `t`.
2. Ο target αγκυρώνει `ATR_t`, εισέρχεται στο `open[t+1]` και εξετάζει το OHLC path για 12 bars.
3. Το υπάρχον purged walk-forward splitter επιβάλλει purge/embargo 13 bars, δηλαδή `horizon_bars + entry_delay_bars`.
4. Κάθε estimator εκπαιδεύεται στο πρώιμο τμήμα του fold.
5. Η calibration εκπαιδεύεται σε μεταγενέστερο, ξεχωριστό validation window μέσα στο fold, με επιπλέον purge 13 bars από το estimator fit.
6. Η EV policy χρησιμοποιεί μόνο calibrated OOS probabilities.
7. Το υπάρχον manual-barrier backtest εκτελεί στο επόμενο open και αφαιρεί commission/turnover cost και slippage.
8. Τα standard artifacts εμπλουτίζονται με barrier-specific tables και plots.

## First-passage target

Για feature row `t`:

```text
entry_price   = open[t + entry_delay_bars]
upper_barrier = entry_price + upper_atr_multiplier * ATR[t]
lower_barrier = entry_price - lower_atr_multiplier * ATR[t]
```

Το baseline χρησιμοποιεί horizon 12, delay 1 και symmetric 1 ATR barriers. Ο target αποθηκεύει label, first-hit time (σε observed path bars από το entry bar, με πρώτο πιθανό hit ίσο με 1), entry/exit, exit reason, MFE/MAE σε raw και ATR units, terminal return, barrier distances, ambiguity, cost eligibility και stop-first/target-first sensitivity labels.

Αν ένα parent OHLC bar αγγίξει και τα δύο barriers:

- επιχειρείται chronological resolution μόνο αν δοθεί lower-timeframe `intrabar_data`,
- διαφορετικά το observation σημειώνεται ambiguous και αφαιρείται από το primary training sample,
- οι stop-first και target-first παραδοχές καταγράφονται μόνο ως sensitivity.

### Label distribution

| Class | Rows | Rate |
|---|---:|---:|
| Lower first (`-1`) | 26,892 | 46.061% |
| No hit (`0`) | 3,600 | 6.166% |
| Upper first (`+1`) | 27,891 | 47.772% |

- Labeled rows: 58,383.
- Ambiguous rows: 682.
- Ambiguous rate: 1.155% των evaluable observations.
- Stop-first sensitivity: lower 46.684%, no-hit 6.095%, upper 47.221%.
- Target-first sensitivity: lower 45.530%, no-hit 6.095%, upper 48.376%.

## Feature families

| Family | Περιεχόμενο |
|---|---|
| Equilibrium / position | KDS Kalman level και drift, rolling median, robust rolling regression, range position, ATR deviations/z-scores, confirmed support/resistance distances |
| Path / asymmetry | positive/negative semivariance, wick ratios, close location, run lengths, path efficiency, backward excursions, roughness, max draw-up/down |
| Persistence | variance ratio, lagged autocorrelation, rolling slope/R², existing causal Hurst estimator, residual OU half-life, correlation trend, optional residual-only ADF |
| Volatility / shock | short/long realized volatility, bipower/jump variation, vol-of-vol, ATR percentile, Parkinson, Garman–Klass, Yang–Zhang, Kalman innovation, CUSUM και explicit change-point proxy |
| Organisation | return-sign Shannon entropy, permutation entropy, entropy changes και causal percentiles, optional sample entropy |
| Microstructure proxies | tick-flow proxy, signed activity imbalance proxy, activity ratio, impact/Amihud proxies και bullish/bearish absorption proxies |
| Time / session | cyclical hour/day, Asia/London/New York flags, overlap, session timing, trailing spread/activity percentiles |

Τα session-minute columns παράγονται ως diagnostics, αλλά δεν μπαίνουν στο complete-case baseline model επειδή είναι εκ φύσεως undefined εκτός του αντίστοιχου session. Τα microstructure outputs δεν ονομάζονται OFI. Το βασικό model τα αποκλείει· χρησιμοποιούνται μόνο στο ρητά επισημασμένο experimental ablation και στο all-features ablation.

## Models, baselines και calibration

Υποστηρίζονται από το κοινό classifier pipeline:

- majority-class baseline,
- empirical-class-probability random baseline,
- last-return continuation baseline,
- last-return reversal baseline,
- multinomial Logistic Regression,
- LightGBM multiclass,
- XGBoost multiclass.

Οι original labels `[-1, 0, 1]` κωδικοποιούνται μόνο εσωτερικά για estimators και επιστρέφονται με σταθερά probability columns:

- `pred_prob_lower`,
- `pred_prob_no_hit`,
- `pred_prob_upper`.

Υποστηρίζονται fold-local sigmoid/Platt και isotonic calibration. Το baseline χρησιμοποιεί sigmoid calibration.

### Raw έναντι calibrated probabilities

| Metric | Raw | Calibrated |
|---|---:|---:|
| Log loss | 1.0416 | 0.8473 |
| Multiclass Brier | 0.6395 | 0.5503 |
| Expected calibration error | 0.0635 | 0.0071 |
| Macro F1 | 0.3666 | 0.3069 |
| Balanced accuracy | 0.5158 | 0.3469 |
| ROC-AUC OVR macro | 0.6356 | 0.6314 |
| PR-AUC OVR macro | 0.4082 | 0.3973 |

Η calibration βελτίωσε ουσιαστικά τα proper scoring/calibration metrics, αλλά μείωσε τις argmax classification metrics. Η EV policy χρησιμοποιεί calibrated probabilities, όχι argmax class decisions.

### Model comparison

Όλα τα μοντέλα αξιολογήθηκαν στα ίδια πέντε OOS folds, με το ίδιο target, causal feature set, fold-local calibration και κοινή EV policy. Δεν έγινε επιλογή folds ή thresholds ανά μοντέλο.

| Model | Log loss | Brier | ECE | Macro F1 | ROC-AUC | Net return | Trades | Cost / gross |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Logistic | 0.8473 | 0.5503 | 0.0071 | 0.3069 | 0.6314 | +1.578% | 144 | 49.79% |
| LightGBM | 0.8310 | 0.5477 | 0.0149 | 0.3491 | 0.6494 | -3.095% | 776 | 153.29% |
| XGBoost | 0.8287 | 0.5466 | 0.0068 | 0.3574 | 0.6520 | -4.730% | 611 | 334.41% |

Το XGBoost ήταν το καλύτερο probability model στα περισσότερα classification metrics, αλλά όχι trading model υπό την προδηλωμένη policy. Αυτή η απόκλιση είναι ουσιώδης: καλύτερο class separation δεν συνεπάγεται οικονομικά αξιοποιήσιμη, cost-robust edge.

### Feature-group ablations

| Feature group | Features | Log loss | ROC-AUC | Net return | Trades |
|---|---:|---:|---:|---:|---:|
| Equilibrium / position | 19 | 0.8772 | 0.5729 | -0.082% | 103 |
| Path / asymmetry | 16 | 0.8790 | 0.5780 | -0.280% | 117 |
| Volatility / regime | 15 | 0.8553 | 0.6192 | -3.048% | 152 |
| Microstructure proxies | 9 | 0.8918 | 0.5481 | -2.403% | 59 |
| All features | 80 | 0.8460 | 0.6326 | +0.507% | 181 |

Κανένα μεμονωμένο group δεν έδωσε θετικό net αποτέλεσμα. Το all-features run ήταν οριακά θετικό, αλλά 79.38% του gross PnL απορροφήθηκε από costs και το exposure παρέμεινε έντονα long. Το all-features αποτέλεσμα είναι diagnostic, όχι αντικατάσταση του canonical baseline ούτε βάση post-hoc feature selection.

### Barrier sensitivity

Η sensitivity επανυπολογίζει τον ορισμό των labels στο ίδιο dataset· δεν επανεκπαιδεύει μοντέλο για κάθε κελί, άρα είναι target-geometry diagnostic και όχι trading grid search.

| Horizon | Multiplier | No-hit | Ambiguous |
|---:|---:|---:|---:|
| 6 | 0.50 | 1.998% | 8.045% |
| 6 | 1.00 | 20.338% | 1.065% |
| 6 | 1.25 | 32.483% | 0.611% |
| 12 | 0.50 | 0.157% | 8.081% |
| 12 | 1.00 | 6.166% | 1.155% |
| 12 | 1.25 | 13.150% | 0.709% |
| 24 | 0.50 | 0.000% | 8.084% |
| 24 | 1.00 | 0.738% | 1.162% |
| 24 | 1.25 | 2.735% | 0.733% |

Με asymmetric upper/lower multipliers `1.00/0.75`, το lower-first rate αυξήθηκε σε 49.53%, 54.73% και 56.34% για horizons 6, 12 και 24 αντίστοιχα. Αυτό δείχνει ότι η class balance εξαρτάται ουσιωδώς από τη barrier geometry.

### Cost, slippage και delay stress

Το stress κρατά σταθερά τα OOS signals και επανατιμολογεί την ίδια στρατηγική. Επομένως μετρά execution sensitivity, όχι retrained model performance.

| Scenario | Net cumulative return |
|---|---:|
| Cost ×1 | +1.578% |
| Cost ×2 | +0.037% |
| Cost ×3 | -1.481% |
| Cost ×5 | -4.449% |
| Slippage ×2 | +1.062% |
| Slippage ×3 | +0.548% |
| Additional entry delay +1 bar | +0.541% |
| Additional entry delay +2 bars | +0.657% |

Η σχεδόν πλήρης εξαφάνιση του PnL στο `cost ×2`, μαζί με μόνο δύο θετικά από τα πέντε OOS walk-forward folds, είναι ισχυρή ένδειξη οικονομικής ευθραυστότητας. Τα stress annualised metrics προέρχονται από mark-to-market repricing και δεν συγκρίνονται απευθείας με το primary trade-exit annualisation· ο πίνακας χρησιμοποιεί cumulative returns.

## Expected-value policy

Η policy υπολογίζει long και short EV από τις τρεις πιθανότητες, τα ATR-scaled payoffs και round-trip costs. Το baseline θέτει το pre-cost no-hit payoff σε μηδέν, αλλά καταγράφει το πραγματικό no-hit terminal return για ανάλυση.

Trade επιτρέπεται μόνο όταν:

- το prediction είναι OOS και calibrated,
- οι probabilities είναι έγκυρες και αθροίζουν σε 1,
- το class probability και το net EV περνούν τα thresholds,
- το gross EV υπερβαίνει τα costs με safety factor,
- το no-hit probability, spread και activity regime είναι αποδεκτά,
- δεν είναι ταυτόχρονα θετικά long και short EV.

## Leakage audit

Ελέγχθηκαν τα ακόλουθα:

- Όλα τα rolling windows είναι trailing και κανένα δεν χρησιμοποιεί `center=True`.
- Το ATR των barriers αγκυρώνεται στο feature bar `t`, όχι στο entry ή σε μελλοντικό bar.
- Η θεωρητική είσοδος του target και του backtest είναι next-open.
- MFE/MAE διαβάζουν ολόκληρο το μελλοντικό OHLC path μόνο ως target diagnostics και εξαιρούνται ρητά από model features.
- Όλα τα target output columns αφαιρούνται από feature inference.
- Purge και calibration purge είναι τουλάχιστον `12 + 1 = 13` bars.
- Το scaler fit γίνεται μόνο στα estimator-training rows κάθε fold.
- Η calibration γίνεται μόνο σε χρονικά μεταγενέστερο validation window και ποτέ με random CV.
- Δεν χρησιμοποιείται random train/test split ή random oversampling.
- Τα support/resistance pivots γίνονται διαθέσιμα μόνο μετά τα configured confirmation bars.
- Entropy, spread/activity percentiles και change-point proxy είναι trailing.
- Τα ambiguous observations δεν κρύβονται ούτε εισάγονται στο primary fit.
- Το final refit δεν χρησιμοποιείται για την παραγωγή των reported OOS probabilities.

## Configs

| Config | Ρόλος |
|---|---|
| `xauusd_30m_barrier_logistic_v1.yaml` | canonical multinomial baseline |
| `xauusd_30m_barrier_lightgbm_v1.yaml` | LightGBM comparison |
| `xauusd_30m_barrier_xgboost_v1.yaml` | XGBoost comparison |
| `ablation_equilibrium_v1.yaml` | equilibrium/position only |
| `ablation_path_v1.yaml` | path/asymmetry only |
| `ablation_volatility_regime_v1.yaml` | volatility/regime only |
| `ablation_microstructure_v1.yaml` | experimental activity proxies only |
| `ablation_all_features_v1.yaml` | all families, including caveated proxies |
| `barrier_sensitivity_v1.yaml` | horizons 6/12/24, ATR multipliers 0.50/0.75/1.00/1.25 και asymmetric 1.00/0.75 |
| `cost_stress_v1.yaml` | costs ×1/×2/×3/×5, slippage ×1/×2/×3 και entry delay +1/+2 |
| `final_holdout_v1.yaml` | structurally isolated 2025+ confirmation |

## Εκτέλεση

Από το repository root:

```bash
python -m src.experiments.runner experiments/barrier_probability/xauusd_30m_barrier_logistic_v1.yaml
```

Sensitivity και cost stress:

```bash
python -m src.experiments.runner experiments/barrier_probability/barrier_sensitivity_v1.yaml
python -m src.experiments.runner experiments/barrier_probability/cost_stress_v1.yaml
```

Το confirmation config πρέπει να εκτελείται μόνο αφού κλειδωθούν model, features, policy και costs:

```bash
python -m src.experiments.runner experiments/barrier_probability/final_holdout_v1.yaml
```

## Artifacts του canonical development run

Run directory:

```text
logs/experiments/barrier_probability/xauusd_30m_barrier_logistic_v1_20260728_222558_982478_abf12709
```

Παράγονται, μεταξύ άλλων:

- `summary.json` και πλήρες `report.md`,
- raw/calibrated reliability table και calibration plot,
- label και ambiguous reports,
- MFE/MAE, time-to-hit και no-hit terminal-return plots,
- probability/EV bucket tables,
- session/hour/volatility/entropy/persistence/side tables,
- class και ambiguous rates ανά fold,
- feature importance και permutation importance ανά fold,
- equity curves ανά fold και combined,
- gross/net/cost/turnover/trade-path artifacts,
- sensitivity και cost heatmaps όταν ενεργοποιούνται τα αντίστοιχα configs.

Συμπληρωματικά ολοκληρωμένα run directories:

```text
logs/experiments/barrier_probability/xauusd_30m_barrier_lightgbm_v1_20260728_225250_425752_4aab90e4
logs/experiments/barrier_probability/xauusd_30m_barrier_xgboost_v1_20260728_225121_166066_d38ded96
logs/experiments/barrier_probability/xauusd_30m_barrier_ablation_all_features_v1_20260728_224839_088072_b7ae4458
logs/experiments/barrier_probability/xauusd_30m_barrier_sensitivity_v1_20260728_223324_074744_54160ebe
logs/experiments/barrier_probability/xauusd_30m_barrier_cost_stress_v1_20260728_223309_711686_675521ad
```

## Tests

Στοχευμένα tests:

```bash
pytest -q \
  tests/targets/test_first_passage_barrier.py \
  tests/signals/test_barrier_expected_value_signal.py \
  tests/features/test_barrier_state.py \
  tests/integration/test_first_passage_multiclass_pipeline.py \
  tests/experiments/test_barrier_probability_diagnostics.py
```

Η κάλυψη περιλαμβάνει upper/lower/no-hit, same-bar ambiguity, intrabar resolution, entry delay, ATR anchoring, path-based MFE/MAE, time-to-hit, cost filtering, causal prefix invariance, purge length, EV/cost calculation, temporal calibration isolation και fixed-seed determinism.

## Assumptions και limitations

1. Το XAUUSD `volume` αντιμετωπίζεται μόνο ως provider activity proxy. Δεν έχει αποδειχθεί ότι είναι πραγματικό exchange volume ή πλήρες tick count.
2. Δεν υπάρχει lower-timeframe intrabar dataset στο runnable example. Το 1.155% ambiguous sample εξαιρείται.
3. Το baseline no-hit payoff είναι μηδέν πριν από costs. Δεν έχει υλοποιηθεί auxiliary conditional terminal-return regressor.
4. Τα configured costs/slippage είναι research assumptions και όχι broker-specific realized fills.
5. Η OHLC backtest διαδρομή δεν μοντελοποιεί queue position, partial fills ή market impact.
6. Τα session boundaries είναι UTC και δεν προσαρμόζουν χωριστά DST για London/New York.
7. Τα tree models, όλα τα feature-group ablations, η barrier sensitivity και το execution stress εκτελέστηκαν και αναφέρονται χωρίς επιλογή μόνο των καλών folds. Δεν έγινε nested tuning των hyperparameters ή των policy thresholds, οπότε οι συγκρίσεις είναι fixed-policy diagnostics και όχι exhaustive model selection.
8. SHAP δεν προστέθηκε, επειδή δεν απαιτήθηκε νέα βαριά dependency και η fold-local permutation importance καλύπτει το primary explainability contract.
9. Η θετική logistic development επίδοση βασίζεται σε 144 trades και πολύ χαμηλή exposure, μηδενίζεται περίπου στο διπλάσιο cost και δεν αναπαράγεται από τα tree models ή τα μεμονωμένα feature groups. Απαιτεί ισχυρότερη confirmation πριν από οποιοδήποτε alpha claim.
10. Το 2025+ confirmation segment είναι structurally isolated στα τελικά configs, αλλά όχι απολύτως pristine μετά το full-range implementation diagnostic αυτής της συνεδρίας.
