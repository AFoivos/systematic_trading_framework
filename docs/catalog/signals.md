# Signal Catalog

Τελευταία ενημέρωση: 2026-06-27

Αυτό το αρχείο τεκμηριώνει τα signal kinds που είναι διαθέσιμα μέσω του
`SIGNAL_REGISTRY` στο `src/signals/registry.py`.

Signals μετατρέπουν features, forecasts ή probabilities σε exposure. Συνήθως
επιστρέφουν values όπως `-1`, `0`, `1` ή continuous exposure στο διάστημα που
ορίζει το `clip`. Το backtest/execution layer είναι υπεύθυνο να εφαρμόσει το
σωστό execution timing, π.χ. signal στο close και εκτέλεση στο επόμενο open.

## Γενικές αρχές

- `long_only`: επιτρέπει μόνο long ή flat.
- `short_only`: επιτρέπει μόνο short ή flat.
- `long_short`: επιτρέπει long, short ή flat χωρίς forward-fill state.
- `long_short_hold`: ανοίγει state όταν υπάρχει entry condition και κρατάει την
  τελευταία πλευρά μέχρι opposite/exit condition.
- Continuous signals, όπως volatility-adjusted forecasts, δεν είναι απαραίτητα
  discrete positions. Είναι conviction/exposure inputs.
- Probability signals απαιτούν out-of-sample probabilities όταν χρησιμοποιούνται
  σε πραγματικό experiment. In-sample probabilities είναι leakage.

## none

No-op signal mode στο experiment pipeline.

- Δεν παράγει νέο signal.
- Αν δοθεί `params.signal_col`, γράφει explicit flat zero signal σε αυτή τη
  στήλη. Αυτό είναι χρήσιμο για feature-only EDA runs που θέλουν να περάσουν
  από το runner/artifact pipeline χωρίς πραγματικό trading signal.
- Χρησιμοποιείται όταν το experiment είναι EDA/visualization ή όταν θέλεις να
  δεις features/targets χωρίς trading signal.

Χρησιμότητα:

- Καθαρίζει τη διάκριση ανάμεσα σε feature/target lab και κανονικό backtest.

## trend_state

Μετατρέπει ένα precomputed trend state column σε directional exposure.

- Input: `state_col`.
- Αν `state_col > 0`, παράγει long.
- Αν `state_col < 0`, παράγει short.
- Αν `state_col == 0` ή λείπει state, παράγει flat, εκτός αν το hold mode κρατά
  προηγούμενη πλευρά.
- Default output: `signal_trend_state`.
- Default mode: `long_short_hold`.

Χρησιμότητα:

- Απλό trend-following signal από ήδη υπολογισμένο regime state.
- Καλό baseline για να δεις αν το trend feature έχει μόνο του edge.

Θεωρία:

- Moving-average state ή άλλο trend state υποθέτει persistence: όταν η
  βραχυπρόθεσμη δομή είναι πάνω από τη μακροπρόθεσμη, η αγορά έχει ανοδική
  τάση.
- Το hold mode ταιριάζει σε trend following, γιατί δεν κλείνει τη θέση σε κάθε
  ουδέτερο bar.

## probability_threshold

Μετατρέπει classifier probability σε discrete directional signal.

- Input: `prob_col`.
- Long όταν `prob > upper`.
- Short όταν `prob < lower`.
- Η περιοχή `[lower, upper]` είναι dead-zone.
- Με `upper_exit` και `lower_exit`, λειτουργεί ως state machine με hysteresis.
- Με `base_signal_col`, το probability φιλτράρει/επιβεβαιώνει την πλευρά ενός
  ήδη υπάρχοντος base signal.
- Default output: `signal_prob`.
- Default mode: `long_short_hold`.

Χρησιμότητα:

- Μετατρέπει model probabilities σε εκτελέσιμη πλευρά.
- Το dead-zone μειώνει overtrading γύρω από αβέβαιες πιθανότητες.
- Τα exit thresholds μειώνουν flip-flopping όταν η πιθανότητα κινείται γύρω από
  το entry threshold.

Θεωρία:

- Ένα calibrated classifier probability μπορεί να ερμηνευτεί ως confidence για
  το θετικό class.
- Thresholding επιτρέπει να trade-άρεις μόνο όταν η αναμενόμενη πληροφορία
  ξεπερνά cost/noise.
- Το hysteresis είναι κλασικός τρόπος να μειωθεί η ευαισθησία σε μικρές
  μεταβολές σήματος.

Causality:

- Το `prob_col` πρέπει να είναι out-of-sample prediction για το row.

## probability_conviction

Μετατρέπει probability σε continuous exposure.

- Input: `prob_col`.
- Τύπος: `clip * (prob - 0.5) * 2`.
- Κάνει clipping στο `[-clip, clip]`.
- Default output: `signal_prob_size`.

Χρησιμότητα:

- Δίνει μικρότερη θέση όταν η πιθανότητα είναι κοντά στο 0.5 και μεγαλύτερη
  όταν η πιθανότητα είναι πιο ακραία.
- Καλό για sizing experiments αντί για binary on/off positions.

Θεωρία:

- Η απόσταση από το 0.5 είναι signed conviction για binary classifier.
- Linear sizing είναι απλό baseline πριν δοκιμαστούν πιο σύνθετα risk overlays.

## probability_vol_adjusted

Μετατρέπει classifier probability σε volatility-adjusted continuous exposure.

- Inputs: `prob_col`, `vol_col`.
- Κεντράρει την πιθανότητα γύρω από `prob_center`.
- Αν δοθούν `upper`/`lower`, ενεργοποιείται μόνο εκτός dead-zone.
- Αν δοθούν `activation_filters`, επιτρέπει trades μόνο όταν περνούν causal
  feature filters.
- Αν δοθεί `top_quantile` ή `max_trade_rate`, κρατά μόνο τα πιο δυνατά absolute
  conviction observations με shifted rolling/expanding threshold.
- Αν δοθεί `vol_target`, κλιμακώνει το conviction με `vol_target / vol`.
- Χρησιμοποιεί `tanh` και `clip` για bounded exposure.
- Με `min_signal_abs`, μικρά exposures μηδενίζονται.
- Default output: `signal_prob_vol_adj`.

Χρησιμότητα:

- Συνδυάζει directional confidence και risk sizing.
- Μειώνει θέση όταν το προβλεπόμενο volatility είναι υψηλό.
- Επιτρέπει sparse trading με `top_quantile`/`max_trade_rate`.

Θεωρία:

- Η πιθανότητα δίνει directional edge, ενώ το volatility εκφράζει uncertainty ή
  expected risk.
- Volatility targeting κρατά πιο σταθερό risk contribution ανά trade.
- Το `tanh` αποτρέπει extreme leverage από μικρό volatility ή υπερβολικό
  conviction.

Causality:

- Τα thresholds για top-quantile selection είναι shifted, ώστε το current row να
  μη συμμετέχει στο δικό του selection threshold.
- Το probability και volatility forecast πρέπει να είναι out-of-sample.

## meta_probability_side

Μετατρέπει meta-label success probability σε same-side execution.

- Inputs: `prob_col`, `side_col`, optional `candidate_col`.
- Το `prob_col` ερμηνεύεται ως `P(candidate succeeds)`, όχι ως πιθανότητα να
  ανέβει η τιμή.
- Αν `prob >= threshold`, ενεργοποιεί την πλευρά του `side_col`.
- Αν η πιθανότητα είναι χαμηλή, μένει flat.
- Δεν γυρίζει ποτέ στην αντίθετη πλευρά.
- Default output: `signal_meta_side`.

Χρησιμότητα:

- Κλασικό meta-labeling execution filter.
- Επιτρέπει σε ένα primary rule/model να αποφασίζει side και σε ένα secondary
  model να αποφασίζει αν αξίζει execution.

Θεωρία:

- Meta-labeling χωρίζει το directional problem από το bet selection problem.
- Το second-stage model μαθαίνει ποιες προτεινόμενες συναλλαγές έχουν θετικό
  expected outcome.

Causality:

- Το `side_col` και `candidate_col` πρέπει να είναι causal primary outputs.
- Το `prob_col` πρέπει να προέρχεται από out-of-sample meta model.

## orb_candidate_side

Diagnostic Opening Range Breakout baseline.

- Inputs: `candidate_col`, `side_col`.
- Όταν το candidate είναι nonzero, εκπέμπει την πλευρά του `side_col`.
- Δεν χρησιμοποιεί probabilities, thresholds ή model filters.
- Default output: `signal_orb_side`.

Χρησιμότητα:

- Raw comparator για ORB candidates.
- Δείχνει τι κάνει το primary ORB rule πριν από meta-labeling ή probability
  filtering.

Θεωρία:

- Το ORB signal υποθέτει ότι breakout έξω από το opening range δείχνει
  directional order-flow imbalance.
- Ως baseline, είναι χρήσιμο για να μετρήσεις αν το model filter προσθέτει αξία.

## roc_long_only_conditions

Manual long-only condition signal. Είναι διαθέσιμο και ως feature step.

- Inputs: `roc_*`, `regime_vol_ratio_z_*`, `close_z`, `close_open_ratio`,
  `mtf_1h_trend_score`, `mtf_4h_trend_score`, `is_weekend`, optional macro
  condition.
- Υπολογίζει condition flags:
  `cond_not_weekend`, `cond_roc`, `cond_vol_regime`,
  `cond_mtf_1h_not_bearish`, `cond_mtf_4h_not_bearish`, `cond_close_z`,
  `cond_bullish_candle`, `cond_macro_not_bearish`.
- Αθροίζει score στο `manual_conviction_score`.
- Παράγει long candidate όταν περνούν τα gates και το score είναι αρκετό.
- Δεν παράγει short signal.
- Κλιμακώνει το exposure με volatility adjustment:
  `1 / (1 + vol_adjustment_strength * max(regime_vol_z, 0))`.
- Default effective output είναι το volatility-adjusted long signal.

Χρησιμότητα:

- Interpretable manual candidate generator για EDA.
- Μπορεί να χρησιμοποιηθεί ως primary side/candidate για meta-labeling.
- Τα condition flags βοηθούν να δεις ποια συνθήκη κάνει reject ή accept κάθε
  setup.

Θεωρία:

- Συνδυάζει momentum, volatility regime, multi-timeframe confirmation, price
  location και candle confirmation.
- Η score-based λογική είναι additive rule model: δεν υποθέτει ότι μία μόνο
  συνθήκη αρκεί, αλλά ότι confluence αυξάνει την ποιότητα setup.

Causality:

- Δεν κάνει fit ή predict. Χρησιμοποιεί ήδη διαθέσιμα current-bar features.
- Η εκτέλεση πρέπει να μετατεθεί στο επόμενο bar/open από το backtest.

## manual_long_model_filter

Φιλτράρει manual long candidates με model probability.

- Inputs: `prob_col`, `candidate_col`, `base_signal_col`.
- Αν το candidate είναι ενεργό και `prob >= threshold`, κρατά το long exposure
  του `base_signal_col`.
- Αν δεν περνά το threshold, μηδενίζει το signal.
- Δεν δημιουργεί trades μόνο του.
- Δεν γυρίζει short.
- Default output: `model_filtered_long_signal`.

Χρησιμότητα:

- Δίνει καθαρό separation ανάμεσα σε manual setup generation και learned trade
  selection.
- Ιδανικό για το workflow: manual candidate -> target -> model -> filter.

Θεωρία:

- Είναι meta-labeling filter για long-only candidates.
- Το model δεν προβλέπει απαραίτητα direction της αγοράς. Προβλέπει αν το
  συγκεκριμένο long setup έχει αρκετή πιθανότητα επιτυχίας.

Causality:

- Το `prob_col` πρέπει να είναι out-of-sample.
- Το manual candidate και base exposure πρέπει να έχουν παραχθεί πριν από το
  target/model outcome.

## forecast_threshold

Μετατρέπει return forecast σε discrete directional exposure.

- Input: `forecast_col`, default `pred_ret`.
- Long όταν `forecast > upper`.
- Short όταν `forecast < lower`.
- Αν `lower` δεν δοθεί, γίνεται `-abs(upper)`.
- Default output: `signal_forecast`.
- Default mode: `long_short_hold`.

Χρησιμότητα:

- Απλός τρόπος να κάνεις trade regression forecasts.
- Το threshold αποφεύγει trades όταν το predicted return είναι πολύ μικρό σε
  σχέση με costs/noise.

Θεωρία:

- Ένα return forecast έχει οικονομική αξία μόνο αν ξεπερνά friction, estimation
  error και execution uncertainty.
- Το symmetric lower threshold είναι baseline για balanced long/short logic.

Causality:

- Το forecast πρέπει να είναι out-of-sample για το row.

## forecast_vol_adjusted

Μετατρέπει return forecast και volatility forecast σε continuous exposure.

- Inputs: `forecast_col`, `vol_col`.
- Τύπος: `tanh(forecast / max(vol, vol_floor)) * clip`.
- Default output: `signal_forecast_vol_adj`.

Χρησιμότητα:

- Παράγει μεγαλύτερη θέση όταν το forecast είναι μεγάλο σε σχέση με το
  predicted volatility.
- Μειώνει overexposure σε high-uncertainty regimes.

Θεωρία:

- `forecast / volatility` είναι signal-to-risk ratio.
- Το `tanh` κάνει bounded nonlinear sizing, ώστε τα ακραία ratios να μην
  παράγουν απεριόριστη θέση.

Causality:

- Και το forecast και το volatility πρέπει να είναι out-of-sample predictions.

## rsi

Contrarian oscillator signal από precomputed RSI column.

- Input: `rsi_col`.
- Long όταν `RSI < buy_level`.
- Short όταν `RSI > sell_level`.
- Default output: `signal_rsi`.
- Default mode: `long_short_hold`.

Χρησιμότητα:

- Μετατρέπει overbought/oversold context σε απλό trading rule.
- Χρήσιμο για mean-reversion baselines ή regime filters.

Θεωρία:

- RSI χαμηλό σημαίνει ότι πρόσφατες καθοδικές κινήσεις ήταν ισχυρές σε σχέση με
  ανοδικές κινήσεις.
- Σε mean-reverting αγορές, oversold μπορεί να έχει positive expected reversal.
- Σε strong trends, RSI μπορεί να μείνει overbought/oversold για μεγάλο διάστημα.

## momentum

Threshold signal από precomputed momentum column.

- Input: `momentum_col`.
- Long όταν `momentum > long_threshold`.
- Short όταν `momentum < short_threshold`.
- Αν `short_threshold` δεν δοθεί και το mode επιτρέπει shorts, γίνεται
  `-abs(long_threshold)`.
- Default output: `signal_momentum`.
- Default mode: `long_short_hold`.

Χρησιμότητα:

- Απλό momentum/trend baseline.
- Κατάλληλο για να δοκιμάσεις αν ένα momentum feature έχει direct predictive
  value.

Θεωρία:

- Momentum υποθέτει persistence: πρόσφατη θετική απόδοση μπορεί να συνεχιστεί.
- Σε μικρά horizons μπορεί να λειτουργήσει και αντίστροφα, άρα το threshold και
  το horizon πρέπει να ελεγχθούν εμπειρικά.

## stochastic

Contrarian oscillator signal από precomputed Stochastic %K.

- Input: `k_col`.
- Long όταν `%K < buy_level`.
- Short όταν `%K > sell_level`.
- Default output: `signal_stochastic`.
- Default mode: `long_short_hold`.

Χρησιμότητα:

- Mean-reversion baseline με βάση τη θέση του close στο πρόσφατο range.
- Χρήσιμο για να εντοπίσεις exhaustion κοντά στα range extremes.

Θεωρία:

- `%K` κοντά στο 0 σημαίνει close κοντά στο πρόσφατο low.
- `%K` κοντά στο 100 σημαίνει close κοντά στο πρόσφατο high.
- Σε range-bound regimes, τα extremes μπορεί να αντιστραφούν. Σε trends, τα
  extremes μπορεί να συνεχιστούν.

## volatility_regime

Directional regime signal από precomputed volatility column.

- Input: `vol_col`.
- Υπολογίζει threshold ως expanding quantile του volatility.
- Με default causal mode, το quantile threshold γίνεται `shift(1)`.
- Long όταν `vol <= threshold`.
- Short όταν `vol > threshold`, αν το mode επιτρέπει shorts.
- Default output: `signal_volatility_regime`.
- Default mode: `long_short_hold`.

Χρησιμότητα:

- Απλό risk-on/risk-off regime rule.
- Μπορεί να χρησιμοποιηθεί ως standalone baseline ή ως filter για άλλα signals.

Θεωρία:

- Το volatility clustering σημαίνει ότι high-vol και low-vol states έχουν
  persistence.
- Πολλά strategies έχουν διαφορετικό payoff σε ήρεμες και ταραγμένες αγορές.
- Το causal expanding quantile προσαρμόζεται στην ιστορία χωρίς να χρησιμοποιεί
  future volatility distribution.

Causality:

- Το default threshold είναι shifted, άρα το current volatility δεν επηρεάζει
  το δικό του regime cutoff.
