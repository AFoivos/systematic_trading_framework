# Κατάλογος Features

Τελευταία ενημέρωση: 2026-06-29

Αυτό το αρχείο τεκμηριώνει τα feature steps που είναι διαθέσιμα μέσω του
`FEATURE_REGISTRY` στο `src/features/registry.py`. Όλα τα χαρακτηριστικά πρέπει να
διαβάζονται ως point-in-time transforms: στο timestamp `t` χρησιμοποιούν μόνο
τιμές που είναι διαθέσιμες μέχρι το `t`, εκτός αν σημειώνεται ρητά ότι ένα
diagnostic/research column δεν πρέπει να μπει σε model features.

## Γενικές αρχές

- Τα rolling features στην pandas περιλαμβάνουν το current bar. Αυτό είναι
  αποδεκτό όταν το σήμα εκτελείται στο επόμενο bar/open, γιατί το current bar
  έχει ήδη κλείσει.
- Τα transforms που εκτιμούν normalization bounds από ιστορία, όπως rolling
  z-score και rolling clip, κάνουν `shift` ώστε το current value να μη
  συμμετέχει στα δικά του statistics.
- Όταν ενεργοποιείς manual candidate features όπως `roc_long_only_conditions`,
  πρέπει πρώτα να ενεργοποιείς τις στήλες που απαιτεί, π.χ. `roc_12`,
  `regime_vol_ratio_z_24_168`, `close_z`, `mtf_1h_trend_score`,
  `mtf_4h_trend_score`, `is_weekend`.
- Τα raw feature steps δεν πρέπει να γεμίζουν το dataframe με παράγωγες helper
  στήλες από προεπιλογή. Λόγοι, υστερήσεις, κλίσεις, σημαίες, διασταυρώσεις,
  z-scores και rolling aggregations δηλώνονται ως helpers στο YAML.
- Τα παλιά helper-equivalent steps `lags`, `return_momentum`,
  `vol_normalized_momentum`, `volume_features`, `zscore_momentum`,
  `rolling_r2_trend_quality`, `trend_slope_volatility` και
  `volatility_of_volatility` δεν είναι canonical feature registry entries.
  Νέα configs πρέπει να τα εκφράζουν με `transforms` / `normalizations`.

## Γλωσσάρι τεχνικών όρων

Τα registry names, YAML keys και column names μένουν στα αγγλικά επειδή πρέπει
να ταιριάζουν ακριβώς με τον κώδικα. Στο κείμενο όμως η έννοια είναι η εξής:

- Feature/χαρακτηριστικό: στήλη εισόδου για signal ή model, διαθέσιμη στο
  τρέχον timestamp.
- Output/έξοδος: στήλη που γράφει το step στο dataframe.
- Input/είσοδος: στήλη που πρέπει να υπάρχει ήδη πριν τρέξει το step.
- Rolling/trailing: παράθυρο που τελειώνει στο τρέχον ή στο αμέσως προηγούμενο
  bar, ανάλογα με το αν υπάρχει `shift`.
- Current bar: το τρέχον κλειστό bar. Είναι causal μόνο αν η εκτέλεση γίνεται
  μετά το κλείσιμό του.
- Candidate: υποψήφιο setup/event, όχι απαραίτητα τελικό trade.
- Diagnostic/research column: στήλη για έλεγχο/ανάλυση. Δεν μπαίνει αυτόματα
  σε production model features.

## Πώς διαβάζεις τις τιμές

Κάθε feature πρέπει να απαντάει σε μία πρακτική ερώτηση: τι κατάσταση της αγοράς
βλέπω στο κλείσιμο του bar `t`; Η ερμηνεία δεν είναι ίδια για όλα τα features:

- Signed features, όπως returns, ROC, slopes και distances, διαβάζονται γύρω
  από το μηδέν. Θετική τιμή σημαίνει ανοδική/πάνω από reference κατάσταση,
  αρνητική τιμή σημαίνει καθοδική/κάτω από reference κατάσταση.
- Bounded oscillators, όπως RSI, Stochastic, MFI και STC, έχουν γνωστά ranges,
  συνήθως `0-100` ή `-1..1`. Η πληροφορία έρχεται από τη θέση μέσα στο range
  και από crossings, όχι από raw price scale.
- Risk/volatility features είναι μη αρνητικά. Υψηλή τιμή σημαίνει περισσότερο
  θόρυβο, μεγαλύτερα candles, μεγαλύτερα stop distances ή λιγότερη σταθερότητα.
- Percentile/rank features διαβάζονται σε `[0, 1]`: `0.90` σημαίνει ότι η τιμή
  είναι υψηλότερη από περίπου το 90% της πρόσφατης ιστορίας.
- Z-score features διαβάζονται σε standard deviations: `2.0` είναι πολύ υψηλή
  θετική απόκλιση, `-2.0` πολύ χαμηλή αρνητική απόκλιση, `0` κοντά στη rolling
  ισορροπία.
- Binary flags έχουν τιμές `0/1`. Το `1` σημαίνει ότι η συνθήκη ισχύει στο
  τρέχον κλειστό bar. Για execution πρέπει να υπάρχει next-bar/open convention
  ή άλλο explicit lag.

## Κατηγορίες feature steps

Οι παρακάτω κατηγορίες είναι ο πρακτικός χάρτης ανάγνωσης του
`FEATURE_REGISTRY`. Οι αναλυτικές ενότητες ανά feature πιο κάτω κρατούν τα outputs,
λεπτομέρειες τύπων και causality notes. Οι πίνακες εδώ εξηγούν τι μετρά το
κάθε feature, πώς μεταφράζονται οι τιμές του και δίνουν σύντομο παράδειγμα.

### 1. Τιμή, αποδόσεις και μνήμη

Αυτά τα features περιγράφουν την πρόσφατη κίνηση της τιμής χωρίς να προσπαθούν
να βγάλουν regime από μόνα τους. Είναι η βάση για momentum, reversal και
triple-barrier labels.

| Feature | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `returns` | Απλή ή λογαριθμική μεταβολή του close. | `> 0` σημαίνει ανοδικό bar/horizon, `< 0` καθοδικό, κοντά στο `0` μικρή καθαρή κίνηση. | Αν `close` πάει από `100` σε `101`, `close_ret=0.01`, δηλαδή +1%. |
| `lags` | Παλαιότερες τιμές ήδη υπαρχουσών columns. | Η τιμή διαβάζεται όπως η αρχική column, αλλά αφορά `t-lag`. Δίνει μνήμη σε tabular model. | `lag_close_ret_1=0.004` σημαίνει ότι το προηγούμενο bar είχε +0.4% return. |
| `roc` | Rate of Change, δηλαδή cumulative return σε συγκεκριμένο lookback. | Θετικό ROC δείχνει πρόσφατο ανοδικό momentum, αρνητικό ROC πρόσφατη πτώση. Μεγάλο απόλυτο ROC δείχνει έντονη κίνηση. | `roc_12=0.025` σημαίνει ότι το close είναι 2.5% πάνω από 12 bars πριν. |
| `price_momentum` | Κίνηση τιμής σε price units ή horizon-specific momentum. | Θετικό σημαίνει ανοδική μετατόπιση, αρνητικό καθοδική. Επειδή είναι price-scale, θέλει normalization για multi-asset model. | Στον US100, `price_momentum_8=45` είναι +45 μονάδες σε 8 bars, αλλά δεν συγκρίνεται άμεσα με XAUUSD. |
| `return_momentum` | Άθροισμα ή συσσώρευση returns σε rolling horizon. | Θετικό σημαίνει drift υπέρ long, αρνητικό υπέρ short/reversal. Μεγάλη απόλυτη τιμή σημαίνει έντονο move. | `return_mom_8=0.012` σημαίνει περίπου +1.2% cumulative return σε 8 bars. |
| `zscore_momentum` | Απόσταση της τιμής από rolling mean σε rolling standard deviations. | `0` κοντά στην ισορροπία, `> 1` πάνω από το πρόσφατο μέσο, `> 2` extreme θετική απόκλιση, `< -2` extreme αρνητική απόκλιση. | `zscore_momentum_96=2.3` δείχνει ότι η τιμή είναι πολύ ψηλά σε σχέση με τις τελευταίες 96 παρατηρήσεις. |

### 2. Μεταβλητότητα, ρίσκο και σταθερότητα regime

Αυτά τα features δεν λένε κατεύθυνση. Λένε πόσο μεγάλο είναι το risk/noise και
αν το περιβάλλον είναι ήρεμο, εκρηκτικό ή ασταθές.

| Feature | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `volatility` | Rolling ή EWMA standard deviation των returns. | Υψηλή τιμή σημαίνει μεγαλύτερη realized risk και πιο ασταθή επόμενα outcomes. Χαμηλή τιμή σημαίνει compressed/quiet περιβάλλον. | `vol_rolling_96=0.008` σημαίνει περίπου 0.8% rolling return volatility στο επιλεγμένο timeframe. |
| `atr` | Average True Range, δηλαδή absolute intrabar/gap range volatility. | Υψηλό ATR σημαίνει μεγάλα candles και μεγαλύτερα stop distances. Δεν δείχνει long ή short κατεύθυνση. | `atr_14=18` στον index σημαίνει μέσο true range 18 μονάδες. Με helper `atr_14_pct=0.006` γίνεται 0.6% του close. |
| `vol_normalized_momentum` | Momentum διαιρεμένο με volatility. | Θετικό και μεγάλο σημαίνει momentum ισχυρό σε σχέση με τον θόρυβο. Κοντά στο `0` σημαίνει αδύναμο drift. | `vol_norm_mom_16=1.4` δείχνει ανοδικό move περίπου 1.4 μονάδων volatility. |
| `volatility_regime` | Σχετική θέση τρέχουσας volatility απέναντι σε baseline/history. | Τιμές `> 1` ή high flags δείχνουν υψηλότερο από το σύνηθες risk. Τιμές `< 1` ή low flags δείχνουν quiet regime. | `volatility_regime=1.35` σημαίνει volatility περίπου 35% πάνω από baseline. |
| `volatility_of_volatility` | Πόσο μεταβάλλεται η ίδια η volatility. | Υψηλή τιμή σημαίνει ότι το risk regime αλλάζει γρήγορα, άρα fixed thresholds και position sizing είναι λιγότερο αξιόπιστα. | `vov_atr_96_ratio_192=1.4` σημαίνει ότι η vol-of-vol είναι 40% πάνω από το δικό της baseline. |
| `parkinson_volatility` | Volatility από high-low range. | Υψηλές τιμές δείχνουν μεγάλα intrabar ranges, ακόμη και αν close-to-close return φαίνεται μικρό. | Αν ένα bar κάνει μεγάλο high-low αλλά κλείσει κοντά στο open, το Parkinson volatility θα το δει καλύτερα από close return. |
| `garman_klass_volatility` | OHLC volatility από open/high/low/close ranges. | Υψηλή τιμή δείχνει έντονη intrabar κίνηση με καλύτερη χρήση του OHLC shape. | Σε assets με reliable OHLC, `garman_klass_vol_20` μπορεί να πιάσει intraday risk που δεν φαίνεται στο close-only volatility. |
| `yang_zhang_volatility` | Volatility που συνδυάζει overnight/open-close και range components. | Υψηλή τιμή δείχνει συνολικό risk μαζί με gaps/session opens. Χρήσιμη όταν τα opens έχουν πληροφορία. | Σε index CFD με session gaps, υψηλό `yang_zhang_vol_20` δείχνει ότι τα gaps συμμετέχουν ουσιαστικά στο risk. |

### 3. Τάση, anchors και market structure

Αυτά τα features απαντούν αν υπάρχει directional structure, πού είναι η τιμή σε
σχέση με reference levels και αν το trend είναι καθαρό ή θορυβώδες.

| Feature | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `trend` | SMA/EMA anchors. | Raw MA level είναι price-scale. Η χρήσιμη πληροφορία είναι η απόσταση `close - MA` ή `close / MA - 1`: θετική πάνω από trend anchor, αρνητική κάτω. | `close_over_ema_50=0.012` σημαίνει close 1.2% πάνω από EMA 50. |
| `trend_regime` | Discrete κατάσταση από σχέσεις price/SMA και short/long SMA. | `1` συνήθως bullish/uptrend, `-1` bearish/downtrend, `0` ουδέτερο ή insufficient data. | `close_trend_state_sma_20_100=1` σημαίνει ότι ο γρήγορος SMA είναι πάνω από τον αργό. |
| `adx` | Directional movement strength με `+DI`, `-DI` και ADX. | Υψηλό ADX σημαίνει ισχυρή directional δομή, όχι απαραίτητα long. Το long/short bias έρχεται από `+DI` vs `-DI`. | `adx_14=32` και `plus_di_14 > minus_di_14` δείχνουν ισχυρότερο ανοδικό directional pressure. |
| `bollinger` | Rolling mean, bands, band width και `%B`. | `%B > 1` είναι πάνω από upper band, `%B < 0` κάτω από lower band, `0.5` στο μέσο. Μεγάλο width δείχνει volatility expansion. | `bb_percent_b_20_2=1.15` σημαίνει close πάνω από το upper band, πιθανό overextension ή breakout. |
| `vwap` | Rolling volume-weighted fair-value anchor. | Close πάνω από VWAP δείχνει τιμή πάνω από πρόσφατη volume-weighted consensus. Απόσταση από VWAP θέλει ratio ή ATR scaling. | `close_over_vwap_20=0.004` σημαίνει close 0.4% πάνω από rolling VWAP. |
| `rolling_r2_trend_quality` | Πόσο καλά η πρόσφατη τιμή εξηγείται από ευθεία γραμμή. | `R2` κοντά στο `1` σημαίνει καθαρό linear trend, κοντά στο `0` σημαίνει chop/noise. Δεν λέει direction χωρίς slope. | `rolling_r2_96=0.78` δείχνει καθαρότερη τάση από `0.18`. |
| `trend_slope_volatility` | Trend slope κανονικοποιημένο με volatility. | Θετικό σημαίνει ανοδική κλίση, αρνητικό καθοδική. Απόλυτη τιμή `> 1` δείχνει slope μεγάλη σε σχέση με το noise. | `trend_slope_vol_ratio_96=1.25` σημαίνει ανοδικό trend ισχυρότερο από το τρέχον volatility unit. |
| `support_resistance` | Rolling support/resistance από πρόσφατα min/max levels. | Μικρή απόσταση από support/resistance δείχνει κοντινό structural level. Breakout flags δείχνουν υπέρβαση level. | `(close - support) / ATR = 0.3` σημαίνει close μόλις 0.3 ATR πάνω από support. |
| `support_resistance_v2` | Confirmed pivots, ages, touches και breakout/retest context. | Περισσότερα touches/νεότερα levels δείχνουν πιο σχετικό structure. Breakout/retest flags δείχνουν event state. | `resistance_touch_count=4` και μικρή ATR distance δείχνουν σημαντικό nearby resistance. |
| `multi_timeframe` | Higher-timeframe returns/trend/volatility ευθυγραμμισμένα στο base timeframe. | Θετικό HTF trend score ενισχύει long setups, αρνητικό ενισχύει short. Volatility/ATR HTF δίνει μεγαλύτερο regime context. | `mtf_4h_trend_score=1` σε 30m run σημαίνει ότι το 4h context είναι ανοδικό. |
| `opening_range_breakout` | Session opening range, breakout distance και candidates. | Breakout πάνω από range δείχνει long pressure, κάτω από range short pressure. Range/ATR λέει αν το opening range είναι μεγάλο ή συμπιεσμένο. | `orb_breakout_distance_atr=0.8` σημαίνει breakout 0.8 ATR έξω από το opening range. |
| `swing_extrema_context` | Confirmed swing highs/lows και αποστάσεις από pivots. | Κοντινή απόσταση σε swing high/low δείχνει structure που μπορεί να επηρεάσει stops, breakouts ή reversals. | `distance_to_last_swing_high_atr=0.5` σημαίνει resistance περίπου μισό ATR πάνω. |

### 4. Ταλαντωτές, momentum timing και pullbacks

Αυτά τα features βοηθούν στο timing. Συνήθως είναι bounded ή semi-bounded και
είναι πιο χρήσιμα με crossings, centered values και flags.

| Feature | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `macd` | Διαφορά fast/slow EMA, signal και histogram. | Θετικό MACD/hist δείχνει ανοδική momentum απόκλιση, αρνητικό καθοδική. Raw MACD είναι price-scale και θέλει normalization. | `macd_hist_12_26_9 > 0` μετά από cross μπορεί να δείξει ανοδική επιτάχυνση. |
| `ppo` | MACD ως ποσοστό του slow EMA. | Θετικό PPO δείχνει fast EMA πάνω από slow EMA σε scale-free μορφή. Αρνητικό δείχνει bearish momentum. | `ppo_12_26=0.006` σημαίνει fast EMA περίπου 0.6% πάνω από slow EMA. |
| `mfi` | Money Flow Index, RSI-like oscillator με volume. | `> 80` συχνά overbought/strong inflow, `< 20` oversold/outflow. Το `50` είναι ουδέτερο κέντρο. | `mfi_14=82` μαζί με high relative volume δείχνει έντονη participation. |
| `rsi` | Relative strength ανοδικών έναντι καθοδικών κινήσεων. | `> 70` overbought/strong momentum, `< 30` oversold, γύρω από `50` ουδέτερο. Η χρήση εξαρτάται από trend regime. | `rsi_14=28` κοντά σε support μπορεί να στηρίξει mean-reversion setup. |
| `stochastic` | Θέση close μέσα στο πρόσφατο high-low range. | `%K` κοντά στο `100` σημαίνει close κοντά στο range high, κοντά στο `0` κοντά στο range low. | `stoch_k=92` δείχνει ότι το close βρίσκεται πολύ κοντά στο πρόσφατο υψηλό. |
| `stochastic_rsi` | Stochastic normalization του RSI. | Πιο ευαίσθητο timing από RSI. Κοντά στο `100` σημαίνει RSI near its recent max, κοντά στο `0` near recent min. | `stoch_rsi_k` cross πάνω από `20` μπορεί να δείξει έξοδο από oversold RSI state. |
| `indicator_pullback` | Pullback diagnostics από συνδυασμό indicators. | Flags/scores δείχνουν αν υπάρχει pullback setup και σε ποια πλευρά. Distances πρέπει να είναι normalized. | `pullback_score=3` μπορεί να σημαίνει ότι πέρασαν τρεις από τις configured pullback συνθήκες. |

### 5. Sessions, regimes, shocks και εξωτερικό context

Αυτά τα features δεν είναι κλασικά indicators. Περιγράφουν πότε βρισκόμαστε,
τι regime επικρατεί ή αν συνέβη abnormal event.

| Feature | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `session_context` | Ώρα, ημέρα, session και intraday calendar flags. | Binary flags `1` δείχνουν ενεργό session/παράθυρο. Cyclical encodings δείχνουν θέση μέσα στην ημέρα/εβδομάδα. | `session_ny_cash=1` σημαίνει ότι το bar ανήκει στο NY cash window. |
| `regime_context` | Volatility ratios, return z-scores, trend states και άλλα market state summaries. | High vol ratio δείχνει stress/expansion. Trend state δείχνει directional context. Abs-return z δείχνει shockiness. | `regime_vol_ratio_z_24_168=2.1` δείχνει πολύ αυξημένη short-term volatility έναντι long baseline. |
| `shock_context` | Abnormal return/ATR shocks και active shock windows. | Shock flag `1` σημαίνει πρόσφατη υπερβολική κίνηση. Strength μεγαλύτερη σημαίνει πιο ακραίο event. | `shock_active=1` και `shock_atr_multiple=2.4` σημαίνει πρόσφατο move 2.4 ATR. |
| `macro_context` | Lagged ή aligned macro/exogenous variables. | Η ερμηνεία εξαρτάται από τη macro column. Η κρίσιμη πληροφορία είναι αν είναι διαθέσιμη point-in-time και με σωστό lag. | `dxy_ret_1=0.004` μπορεί να δώσει USD context σε FX/metal strategy, μόνο αν το timestamp availability είναι σωστό. |
| `hmm_regime` | Latent regime labels/probabilities από Hidden Markov Model. | Label `0/1/2` δεν έχει φυσική σημασία χωρίς profiling. Probabilities κοντά στο `1` δείχνουν confidence στο αντίστοιχο latent state. | Αν state `2` έχει ιστορικά high-vol negative returns, `hmm_state=2` διαβάζεται ως risk-off μόνο μετά από post-fit ανάλυση. |

### 6. Ehlers, κύκλοι και adaptive filters

Αυτά τα features προσπαθούν να χωρίσουν trend/cycle/noise ή να εκτιμήσουν phase
και dominant period. Τα price-like outputs συνήθως χρειάζονται `/ ATR`,
`/ close`, z-score ή percent rank πριν μπουν σε multi-asset model.

| Feature | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `ehlers_ml_long_candidate` | Deterministic Ehlers long candidate και supporting state. | Candidate flag `1` σημαίνει ότι οι configured Ehlers συνθήκες συμφωνούν για long setup. Supporting distances δείχνουν ποιότητα setup. | `ehlers_ml_candidate=1` μπορεί να γίνει side candidate για meta-labeling. |
| `mama` | MESA Adaptive Moving Average. | Close πάνω από MAMA ή MAMA πάνω από FAMA δείχνει adaptive bullish trend context. Raw MAMA είναι price-level. | `(close - mama) / ATR = 0.7` δείχνει close 0.7 ATR πάνω από adaptive average. |
| `fama` | Slower companion line του MAMA. | MAMA-FAMA spread θετικό δείχνει adaptive uptrend confirmation, αρνητικό downtrend. | `(mama - fama) / ATR = 0.4` δείχνει θετικό adaptive spread. |
| `dominant_cycle_period` | Εκτιμώμενο μήκος κυρίαρχου cycle. | Μεγαλύτερη τιμή σημαίνει πιο αργός κύκλος, μικρότερη πιο γρήγορος. Out-of-range τιμές συχνά γίνονται filter. | `dominant_cycle_period=34` σημαίνει εκτιμώμενος κύκλος περίπου 34 bars. |
| `dominant_cycle_phase` | Θέση μέσα στον εκτιμώμενο κύκλο. | Phase near turning zones μπορεί να βοηθήσει timing. Καλύτερα να μετατρέπεται σε sin/cos ή να συνδυάζεται με sinewave. | Phase που περνά συγκεκριμένο όριο μπορεί να σηματοδοτεί αλλαγή cycle segment. |
| `instantaneous_trendline` | Low-lag Ehlers trendline και optional trigger. | Close πάνω από trendline ή trigger cross δείχνει θετικό trend timing. Distance θέλει ATR scaling. | `close_minus_itl_over_atr=0.5` σημαίνει close μισό ATR πάνω από trendline. |
| `fisher_transform` | Fisher transform σε rolling-normalized price. | Θετικές τιμές δείχνουν upper normalized state, αρνητικές lower. Μεγάλα απόλυτα values τονίζουν extremes. | Fisher cross πάνω από `0` μετά από αρνητικό extreme μπορεί να δείξει reversal timing. |
| `inverse_fisher_transform` | Bounded nonlinear transform, συνήθως `tanh`-like. | Τιμές κοντά στο `1` δείχνουν θετικό extreme, κοντά στο `-1` αρνητικό extreme, κοντά στο `0` ουδέτερο. | `inverse_fisher=0.85` δείχνει έντονα θετικό oscillator state. |
| `sinewave_indicator` | Sine και lead-sine από cycle phase. | Cross sine/lead-sine δίνει cycle turning context. Τιμές σε `[-1, 1]` δείχνουν phase position. | Sine cross πάνω από lead-sine μπορεί να δηλώνει ανοδική cycle στροφή. |
| `cyber_cycle` | Detrended cycle oscillator. | Θετικό/αρνητικό δείχνει cycle side. Μεγάλη απόλυτη τιμή δείχνει ισχυρό cycle component, αλλά θέλει scaling. | `cyber_cycle` crossing πάνω από `0` μπορεί να γίνει event flag. |
| `decycler` | Smooth trend component με reduced cycle. | Close πάνω από decycler δείχνει τιμή πάνω από smooth trend. Raw level είναι price-scale. | `(close - decycler) / ATR = -0.6` δείχνει close 0.6 ATR κάτω από decycler. |
| `decycler_oscillator` | Spread fast/slow decyclers normalized by price. | Θετικό δείχνει fast trend πάνω από slow, αρνητικό το αντίθετο. | `decycler_oscillator=0.9` δείχνει θετικό continuation pressure. |
| `laguerre_rsi` | Laguerre-smoothed RSI. | Σε `0-1`, κοντά στο `1` overbought/strong, κοντά στο `0` oversold/weak. Σε percent mode διαβάζεται `0-100`. | `laguerre_rsi=0.18` δείχνει low/oversold oscillator state. |
| `frama` | Fractal Adaptive Moving Average και optional diagnostics. | Close-FRAMA distance δείχνει trend displacement. Alpha/fractal diagnostics δείχνουν αν το filter αντιδρά γρήγορα ή αργά. | `(close - frama) / ATR = 1.1` δείχνει close πάνω από adaptive average κατά 1.1 ATR. |
| `center_of_gravity` | Ehlers Center of Gravity oscillator. | Θετικό/αρνητικό και crossings δίνουν short-term turning context. | COG cross από αρνητικό σε θετικό μπορεί να δείξει ανοδική βραχυπρόθεσμη στροφή. |
| `even_better_sinewave` | Bounded Ehlers cycle oscillator. | Κοντά στο `1` θετικό cycle extreme, κοντά στο `-1` αρνητικό, γύρω από `0` transition. | `even_better_sinewave=-0.9` δείχνει αρνητικό cycle extreme. |
| `autocorrelation_periodogram` | Dominant period και optional power μέσω autocorrelation. | Period δείχνει εκτιμώμενο cycle length. Power υψηλό σημαίνει πιο αξιόπιστη periodic δομή. | `period=28` και high power δείχνουν δυνατό κύκλο περίπου 28 bars. |
| `homodyne_discriminator` | MESA cycle period estimate από phase dynamics. | Υψηλότερη τιμή σημαίνει πιο αργός cycle, χαμηλότερη πιο γρήγορος. Θέλει bounds. | `homodyne_discriminator=18` μπορεί να οδηγήσει adaptive lookback 18 bars. |
| `hilbert_transform` | Amplitude, phase και instantaneous frequency από trailing Hilbert endpoint. | Μεγάλη amplitude δείχνει δυνατό cycle component. Frequency υψηλότερη σημαίνει πιο γρήγορο cycle. Phase δείχνει timing. | `1 / abs(hilbert_frequency_64)=24` δείχνει dominant cycle περίπου 24 bars. |
| `roofing_filter` | Band-pass filtered price/cycle component. | Θετικό/αρνητικό δείχνει cycle side. Crossings στο `0` δείχνουν transitions. Θέλει ATR/z-score scaling. | `roofing_filter_48_10_cross_up=1` σημαίνει πέρασμα πάνω από το μηδέν στο τρέχον bar. |
| `schaff_trend_cycle` | MACD + stochastic cycle oscillator. | Σε `0-100`, υψηλές τιμές δείχνουν bullish/overbought trend-cycle state, χαμηλές bearish/oversold. Crossings βοηθούν timing. | `stc=82` δείχνει δυνατό bullish state αλλά όχι απαραίτητα fresh entry χωρίς cross/slope. |
| `supersmoother` | Ehlers low-pass smooth filter. | Ως raw level είναι smoothed price. Η χρήσιμη πληροφορία είναι distance/slope σε ATR units. | `supersmoother_slope_atr=0.25` δείχνει ήπια ανοδική smooth slope. |

### 7. Πολυπλοκότητα, entropy και fractal κατάσταση

Αυτά τα features λένε αν η αγορά είναι persistent, rough, chaotic ή πιο
δομημένη. Δεν δίνουν από μόνα τους side.

| Feature | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `hurst_exponent` | Persistence/anti-persistence της πρόσφατης χρονοσειράς. | `> 0.5` δείχνει persistence/trendiness, `< 0.5` anti-persistence/mean reversion, γύρω από `0.5` random-walk-like. | `hurst_256=0.62` υποστηρίζει momentum regime περισσότερο από reversal. |
| `fractal_dimension` | Roughness/choppiness της price path. | Υψηλότερη fractal dimension σημαίνει πιο rough/choppy κίνηση. Χαμηλότερη δείχνει πιο smooth path. | `fractal_dimension_128` σε υψηλό percentile μπορεί να κόψει trend-following entries. |
| `shannon_entropy` | Διασπορά/αβεβαιότητα της πρόσφατης κατανομής. | Υψηλή entropy σημαίνει πιο απρόβλεπτο/dispersed περιβάλλον. Χαμηλή σημαίνει πιο συγκεντρωμένη συμπεριφορά. | High entropy μαζί με χαμηλό ADX δείχνει noisy chop. |
| `permutation_entropy` | Ποικιλία ordinal/rank patterns. | Υψηλή τιμή δείχνει πολλά διαφορετικά patterns και λιγότερη απλή δομή. Χαμηλή δείχνει πιο επαναλαμβανόμενη σειρά. | `permutation_entropy` κοντά στο upper percentile μπορεί να λειτουργήσει ως no-trade filter για cycle setups. |

### 8. Όγκος και order-flow

Αυτά τα features μετρούν participation, flow pressure και liquidity stress.
Θέλουν αξιόπιστα volume/order-flow inputs. Σε FX/CFD tick volume, η ερμηνεία
είναι proxy και πρέπει να επιβεβαιώνεται ανά provider.

| Feature | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `volume_features` | Volume z-score και volume/range ή volume/ATR context. | Υψηλό z-score/relative volume δείχνει abnormal participation. Χαμηλό δείχνει αδύναμη συμμετοχή. | `volume_z_96=2.4` σημαίνει volume πάνω από το πρόσφατο baseline κατά 2.4 std. |
| `scalp_microstructure_proxy` | Quote mid, spread, candle geometry και signed-volume proxy από bid/ask OHLCV. | Spread ranks/z-scores δείχνουν liquidity stress, candle pressure δείχνει close location, signed-volume proxy δείχνει candle-implied flow. | `candle_pressure=0.8` και `volume_relative_48=1.5` δείχνουν strong close με αυξημένη συμμετοχή, αλλά είναι proxy flow, όχι aggressor-side tape. |
| `vpin` | Proxy για informed/toxic flow από volume imbalance. | Υψηλό VPIN δείχνει persistent imbalance και πιθανό liquidity stress. Χαμηλό δείχνει πιο balanced flow. | `vpin_50` στο 90ο percentile μπορεί να κόψει mean-reversion entries λόγω adverse flow. |
| `order_flow_imbalance` | Buy/sell ή bid/ask imbalance, raw ή rolling. | Θετικό δείχνει buy pressure, αρνητικό sell pressure. Μεγάλη απόλυτη τιμή δείχνει έντονη ανισορροπία. | `order_flow_imbalance=0.35` μπορεί να σημαίνει 35% καθαρό buy imbalance αν είναι normalized. |

### 9. Candidate και compatibility feature steps

Τα παρακάτω παράγουν candidate/signal-like state. Είναι χρήσιμα για
meta-labeling και diagnostics, αλλά πρέπει να διαβάζονται με execution lag.

| Step | Τι μετρά | Τι πληροφορία δίνουν οι τιμές | Παράδειγμα |
|---|---|---|---|
| `roc_long_only_conditions` | Rule-based long-only condition score. | `manual_conviction_score` μετρά πόσες συνθήκες πέρασαν. Candidate `1` σημαίνει ότι το score και τα gates επιτρέπουν long. | Αν `min_score_required=4` και score `5`, το long candidate ενεργοποιείται εκτός αν weekend/macro gate το κόψει. |
| `ehlers_semiscalp_long` | Compatibility long candidate από Ehlers semiscalp logic. | `signal_candidate=1` σημαίνει ότι οι configured setup flags συμφωνούν για long-only setup. | Χρήσιμο ως side input για triple-barrier meta-label. |
| `ehlers_decycler_continuation` | Compatibility decycler continuation candidate. | Candidate `1` δείχνει continuation setup σύμφωνα με decycler logic. | Μπαίνει ως candidate, όχι ως ανεξάρτητο target. |
| `ema_stoch_rsi_pullback` | EMA + StochRSI pullback candidate. | Side/candidate columns δείχνουν αν υπάρχει long/short pullback setup. | `candidate_long=1` όταν trend και oscillator pullback συνθήκες περνούν. |
| `indicator_model_adaptive_pullback` | Indicator-only adaptive pullback candidate. | Candidate/score columns δείχνουν setup state πριν από model filtering. | Score υψηλότερο σημαίνει περισσότερη συμφωνία indicators. |
| `quote_flow_scalp_router` | Compatibility quote-flow scalp candidate από ήδη υπάρχοντα microstructure, VWAP, S/R και session features. | `signal_candidate=1` και `signal_side=1/-1` δείχνουν primary setup πριν από meta-labeling. | Χρήσιμο ως feature-stage candidate ώστε `directional_triple_barrier` και meta model να τρέξουν πριν από top-level `signals`. |
| `vwap_rms_ema_cross_long` | VWAP/RMS/EMA cross long candidate με confirmations. | Candidate `1` σημαίνει ότι cross/regime/confirmation logic πέρασε. | Χρήσιμο για long-only execution parity tests ή meta-labeling. |

## Raw features και helpers

Το feature catalog περιγράφει τους raw builders. Αν χρειάζεσαι παράγωγη στήλη,
χρησιμοποίησε helper:

| Αν χρειάζεσαι | Χρησιμοποίησε |
|---|---|
| ratio/distance | `transforms.ratio` |
| slope/delta | `transforms.difference` ή `transforms.slope` |
| lag | `transforms.lag` |
| rising flag | `transforms.rising_flag` |
| threshold flag | `transforms.threshold_flag` |
| range flag | `transforms.between_flag` |
| cross-up/cross-down | `transforms.crossing_flag` |
| rolling mean/std/sum | `transforms.rolling_mean`, `rolling_std`, `rolling_sum` |
| rolling regression slope/R2 | `transforms.rolling_linear_regression` |
| z-score/clip | `transforms.rolling_zscore`, `rolling_clip` |
| trading normalization | `normalizations.rolling_percent_rank`, `robust_zscore`, `volatility_scaled_return`, `atr_scaled_distance`, `range_position`, `realized_vol_percentile`, `volume_relative`, `rolling_beta_residual` |

## Transform helpers

Τα transform helpers δηλώνονται κάτω από `transforms:` μέσα σε feature step και
δουλεύουν πάνω σε ήδη διαθέσιμες columns. Δεν πρέπει να κρύβουν νέα raw feature
logic. Είναι για deterministic derived columns όπως ratios, lags, slopes,
flags και rolling summaries.

| Helper | Προεπιλεγμένη έξοδος | Περιγραφή | Αιτιότητα |
|---|---|---|---|
| `ratio` | `{numerator}_over_{denominator}` | Διαιρεί δύο columns με `eps`, optional `subtract` και `denominator_offset`. | Ασφαλές αν numerator/denominator είναι PIT. |
| `reciprocal` | `{source}_reciprocal` | Υπολογίζει `1 / source` ή `1 / abs(source)` με `eps`. | Ασφαλές point-in-time transform. |
| `difference` | `{source}_diff_{periods}` | `source_t - source_{t-periods}`. | Χρησιμοποιεί μόνο lagged value. |
| `slope` | `{source}_slope_{periods}` | Slope/delta-style change over configured periods. | Χρησιμοποιεί only current και past values. |
| `lag` | `lag_{source}_{lag}` | `source.shift(lag)`. | Pure past value. |
| `rms` | `{source}_rms_{window}` | Rolling root-mean-square. | Trailing rolling window. |
| `rolling_mean` | `{source}_mean_{window}` | Trailing rolling mean. | Includes current closed bar. |
| `rolling_std` | `{source}_std_{window}` | Trailing rolling standard deviation. | Includes current closed bar. |
| `rolling_sum` | `{source}_sum_{window}` | Trailing rolling sum. | Includes current closed bar. |
| `rolling_linear_regression` | configured slope/R2 columns | Rolling regression slope, intercept/R2 style diagnostics depending on params. | Trailing window only. |
| `rolling_zscore` | `{source}_zscore_{window}` | Z-score from rolling mean/std, shifted by default where supported. | Use shifted stats for production features. |
| `rolling_clip` | configured/default clipped column | Clips source by rolling quantile bounds. | Bounds are shifted by default where supported. |
| `threshold_flag` | configured output | Binary comparison vs threshold with `gt/ge/lt/le/eq/ne`, optional absolute value. | Current-bar deterministic flag. |
| `between_flag` | configured output | Binary range membership with configurable inclusivity. | Current-bar deterministic flag. |
| `crossing_flag` | configured output | Cross-up/down through threshold using current and previous value. | Uses `t` and `t-1`. |
| `rising_flag` | configured output | `source_t > source_{t-periods}`. | Uses only lagged comparison. |

### Transform helper notes

- Helpers accept explicit source columns and, for several helpers, selector configs.
- `items:` can be used by helper application code for repeated transforms of the same helper kind.
- Flags are useful for model inputs, but for execution logic they still represent current-bar-close information. Backtests must apply the intended next-bar/open execution convention.
- For any helper using rolling statistics, prefer shifted statistics when the helper exposes that option. Self-normalizing the current value with statistics that include itself can dampen outliers and subtly change live behavior.

## Normalization helpers

Normalization helpers δηλώνονται κάτω από `normalizations:` και παράγουν
trading-specific scaled/standardized columns. Τα περισσότερα έχουν explicit
`shift_stats` ή `shift_window` defaults για να αποφύγουν self-inclusion στα
normalization statistics.

| Helper | Προεπιλεγμένη έξοδος | Περιγραφή | Αιτιότητα / leakage note |
|---|---|---|---|
| `returns` | `return_{window}`, `log_return_{window}` | Multi-horizon simple returns και optional log returns από `close_col`. | Uses `close_t / close_{t-window}`. |
| `rolling_zscores` | `{col}_zscore_{window}` | Batch rolling z-score για list of columns. | `shift_stats=true` by default. |
| `robust_zscore` | `{source}_robust_zscore_{window}` | Rolling median/MAD z-score. | `shift_stats=true` by default. |
| `rolling_percent_rank` | `{source}_percent_rank_{window}` | Percent rank του current value έναντι trailing history. | `shift_window=true` ranks `t` against history ending at `t-1`. |
| `volatility` | `{atr_col}_pct`, `{atr_col}_percentile_{window}` | ATR percentage of close και ATR percentile. | Percentile implementation ranks inside trailing window; use knowingly if self-inclusion matters. |
| `volatility_scaled_return` | `{return_col}_over_{volatility_col}` | Return divided by volatility estimate. | Safe if both inputs are PIT. |
| `atr_distances` | configured/default ATR distance columns | Distances from configured price/reference columns scaled by ATR. | Safe if ATR/reference are PIT. |
| `atr_scaled_distance` | configured/default ATR-scaled distance | Generic `(source - reference) / ATR` style scaling. | Safe if source/reference/ATR are PIT. |
| `range_position` | configured/default range-position column | Position of source/close inside trailing or configured high-low range. | Requires range columns/windows that are PIT. |
| `realized_vol_percentile` | configured/default realized-vol percentile | Percentile/rank context for realized volatility. | Use shifted history when available for production features. |
| `volume_relative` | `{volume}_relative_{window}`, optional z-score | Volume divided by rolling mean; optional shifted z-score. | `shift_stats=true` by default. |
| `rolling_beta_residual` | `{asset}_residual_vs_{benchmark}_{window}` | Single-factor trailing beta/alpha residual, optional beta/alpha outputs. | `shift_stats=true` by default, so residual uses beta/alpha estimated through `t-1`. |

### Normalization helper notes

- Prefer normalizations over ad hoc formulas in YAML when the helper exists; it makes leakage assumptions explicit.
- Do not fit global scalers on full data before temporal splits. These helpers are intended to compute rolling/PIT scaling inside the feature pipeline.
- `rolling_percent_rank`, `robust_zscore`, `volume_relative`, and `rolling_beta_residual` are the safer defaults for ML features because their statistics can exclude the current observation.
- `returns` here is a normalization helper; `returns` is also a canonical raw feature step for the single `close_ret` / `close_logret` legacy-compatible output.

## returns

Υπολογίζει απλές ή λογαριθμικές αποδόσεις από το `close`.

- Έξοδος: `close_ret` όταν `log=false`, `close_logret` όταν `log=true`, ή όνομα από `col_name`.
- Τύπος: απλή απόδοση `close_t / close_{t-1} - 1`; log return `log(close_t / close_{t-1})`.
- Χρησιμότητα: βασική μεταβλητή για volatility, momentum, targets και backtests.
- Θεωρία: οι αποδόσεις είναι πιο stationary από τις τιμές και συγκρίνονται πιο εύκολα μεταξύ assets.
- Αιτιότητα: χρησιμοποιεί μόνο `t` και `t-1`.

## volatility

Υπολογίζει realized volatility από ήδη υπάρχουσα στήλη returns.

- Έξοδοι: `vol_rolling_{w}` για rolling standard deviation και `vol_ewma_{span}` για exponentially weighted volatility.
- Τύπος rolling: `std(returns_{t-w+1:t})`, προαιρετικά annualized με `sqrt(annualization_factor)`.
- Τύπος EWMA: exponentially weighted standard deviation.
- Χρησιμότητα: volatility regimes, risk scaling, stop distances, feature normalization.
- Θεωρία: το volatility clustering είναι κεντρικό χαρακτηριστικό χρηματοοικονομικών χρονοσειρών.
- Αιτιότητα: rolling/EWMA χρησιμοποιούν μέχρι το current bar.

## trend

Υπολογίζει SMA/EMA. Relative distances/ratios δηλώνονται με helpers.

- Έξοδοι: `{price_col}_sma_{window}`, `{price_col}_ema_{span}` ή configured column names.
- Ratio τύπος μέσω helper: `price / moving_average - 1`.
- Χρησιμότητα: μετρά κατεύθυνση και απόσταση από trend anchors.
- Θεωρία: moving averages είναι low-pass filters που εξομαλύνουν θόρυβο και αναδεικνύουν trend.
- Αιτιότητα: SMA/EMA είναι trailing.

## quant trend/volatility snippet

Παράδειγμα για τα standalone quant feature steps που μετρούν trend quality,
trend slope σε σχέση με volatility, και volatility-of-volatility:

```yaml
features:
  - step: rolling_r2_trend_quality
    params:
      price_col: close
      window: 96
      output_col: rolling_r2_96
    transforms:
      rolling_linear_regression:
        params:
          source_col: close
          window: 96
          slope_col: rolling_r2_slope_96
          r2_col: rolling_r2_96
      threshold_flag:
        params:
          source_col: rolling_r2_96
          threshold: 0.60
          op: ge
          output_col: rolling_r2_96_ok

  - step: trend_slope_volatility
    params:
      price_col: close
      volatility_col: atr_over_price_20
      window: 96
      slope_col: trend_slope_96
      volatility_used_col: trend_vol_used_96
      slope_vol_ratio_col: trend_slope_vol_ratio_96
      strong_threshold: 1.0
    transforms:
      threshold_flag:
        items:
          - source_col: trend_slope_vol_ratio_96
            threshold: 0.0
            op: gt
            output_col: trend_slope_vol_ratio_96_positive
          - source_col: trend_slope_vol_ratio_96
            threshold: 1.0
            op: ge
            use_abs: true
            output_col: trend_slope_vol_ratio_96_strong

  - step: volatility_of_volatility
    params:
      volatility_col: atr_over_price_20
      window: 96
      output_col: vov_atr_96
    transforms:
      rolling_mean:
        params:
          source_col: vov_atr_96
          window: 192
          output_col: vov_atr_96_mean_192
      ratio:
        params:
          numerator_col: vov_atr_96
          denominator_col: vov_atr_96_mean_192
          output_col: vov_atr_96_ratio_192
      rising_flag:
        params:
          source_col: vov_atr_96
          output_col: vov_atr_96_rising
      threshold_flag:
        params:
          source_col: vov_atr_96_ratio_192
          threshold: 1.10
          op: gt
          output_col: vov_atr_96_high
```

## trend_regime

Μετατρέπει moving-average relationships σε discrete trend states.

- Απαιτεί να έχει προηγηθεί `trend` με τα αντίστοιχα SMA windows.
- Έξοδοι: `{price_col}_trend_regime_sma_{base_sma}` και `{price_col}_trend_state_sma_{short}_{long}`.
- Τύπος regime: `sign(price_over_sma)`.
- Τύπος state: `1` όταν short SMA > long SMA, `-1` όταν short SMA < long SMA, `0` όταν λείπουν δεδομένα.
- Χρησιμότητα: απλή regime μεταβλητή για filters, signals και stratification.
- Θεωρία: trend following υποθέτει persistence όταν οι βραχυπρόθεσμοι μέσοι είναι πάνω από τους μακροπρόθεσμους.

## lags

Δημιουργεί καθυστερημένες εκδοχές επιλεγμένων columns.

- Έξοδοι: `{prefix}_{col}_{lag}`.
- Τύπος: `x_{t-lag}`.
- Χρησιμότητα: δίνει στο μοντέλο ιστορική κατάσταση χωρίς sequence model.
- Θεωρία: autoregressive information, lagged dependence, persistence/reversal.
- Αιτιότητα: ασφαλές, γιατί κοιτά μόνο παρελθόν.

## bollinger

Υπολογίζει Bollinger Bands γύρω από rolling mean.

- Έξοδοι: `bb_ma_{window}`, `bb_upper_{window}_{n_std}`, `bb_lower_{window}_{n_std}`, `bb_width_{window}_{n_std}`, `bb_percent_b_{window}_{n_std}`.
- Τύπος: `MA +/- n_std * rolling_std`; `%B = (price - lower) / (upper - lower)`.
- Χρησιμότητα: mean-reversion context, volatility expansion/compression, overextension.
- Θεωρία: bands προσεγγίζουν κανονικοποιημένη απόσταση της τιμής από rolling equilibrium.

## macd

Υπολογίζει MACD από δύο EMAs και signal line.

- Έξοδοι: `macd_{fast}_{slow}`, `macd_signal_{signal}`, `macd_hist_{fast}_{slow}_{signal}`.
- Τύπος: `EMA_fast - EMA_slow`; signal = EMA του MACD; histogram = MACD - signal.
- Χρησιμότητα: momentum/trend acceleration και crossovers.
- Θεωρία: σύγκριση γρήγορου και αργού φίλτρου για να εντοπιστεί αλλαγή momentum.

## ppo

Percentage Price Oscillator, normalized MACD.

- Έξοδοι: `ppo_{fast}_{slow}`, `ppo_signal_{signal}`, `ppo_hist_{fast}_{slow}_{signal}`.
- Τύπος: `(EMA_fast - EMA_slow) / EMA_slow`.
- Χρησιμότητα: MACD-like momentum συγκρίσιμο μεταξύ assets/price levels.
- Θεωρία: scale normalization μειώνει price-level dependence.

## roc

Rate of Change για ένα ή περισσότερα windows.

- Έξοδοι: `roc_{window}`.
- Τύπος: `close_t / close_{t-window} - 1`.
- Χρησιμότητα: direct momentum/reversal measure.
- Θεωρία: cumulative return over lookback. Θετικό ROC δείχνει πρόσφατη ανοδική τάση.

## atr

Average True Range.

- Έξοδοι: `atr_{window}` ή configured ATR column. Το `atr_over_price` γίνεται
  με `transforms.ratio` ή `normalizations.volatility`.
- True Range: max από `high-low`, `abs(high-prev_close)`, `abs(low-prev_close)`.
- ATR: Wilder EWMA ή simple rolling mean του True Range.
- Χρησιμότητα: stop distances, volatility normalization, position sizing.
- Θεωρία: μετρά absolute range volatility, όχι κατεύθυνση.

## adx

Average Directional Index μαζί με directional indicators.

- Έξοδοι: `plus_di_{window}`, `minus_di_{window}`, `adx_{window}`.
- Υπολογίζει positive/negative directional movement, τα εξομαλύνει με Wilder EWMA και παράγει ADX.
- Χρησιμότητα: strength filter για trend strategies, ανεξάρτητα από long/short direction.
- Θεωρία: ADX υψηλό σημαίνει directional structure, όχι απαραίτητα bullish.

## volume_features

Volume normalization και volume/range context.

- Έξοδοι: `volume_z_{vol_z_window}`, `volume_over_atr_{atr_window}`.
- Τύπος z-score: `(volume - rolling_mean) / rolling_std`.
- `volume_over_atr`: volume divided by ATR.
- Χρησιμότητα: participation/liquidity proxy, abnormal activity detection.
- Θεωρία: volume spikes συχνά συνοδεύουν breakouts, capitulation ή regime changes.

## vwap

Rolling VWAP, δηλαδή όγκο-σταθμισμένη μέση τιμή από typical price και volume.

- Έξοδοι: `vwap_{window}` ή configured VWAP column. Το distance/ratio από VWAP
  γίνεται με `transforms.ratio`.
- Τύπος: `sum(((high+low+close)/3) * volume) / sum(volume)` σε trailing rolling window.
- Χρησιμότητα: liquidity-weighted fair-value anchor και distance-from-VWAP context.
- Θεωρία: η απόσταση από VWAP δείχνει αν το current close είναι πάνω ή κάτω από την πρόσφατη volume-weighted consensus price.
- Αιτιότητα: rolling window μέχρι το current bar, χωρίς future bars.

## mfi

Money Flow Index.

- Έξοδος: `mfi_{window}`.
- Τύπος: typical price `(high+low+close)/3`, raw money flow = typical price * volume, ratio positive/negative money flow, mapped to 0-100.
- Χρησιμότητα: oscillator που συνδυάζει price και volume.
- Θεωρία: RSI-like momentum με volume weighting.

## rsi

Relative Strength Index.

- Έξοδοι: `{price_col}_rsi_{window}`.
- Τύπος: μέσο κέρδος / μέση ζημιά, με Wilder ή simple averaging, mapped σε 0-100.
- Χρησιμότητα: overbought/oversold context, mean reversion, momentum exhaustion.
- Θεωρία: συγκρίνει magnitude ανοδικών και καθοδικών κινήσεων.

## stochastic

Stochastic oscillator.

- Έξοδοι: `{price_col}_stoch_k_{window}`, `{price_col}_stoch_d_{window}`.
- `%K = 100 * (close - rolling_low) / (rolling_high - rolling_low)`.
- `%D`: rolling mean του `%K`.
- Χρησιμότητα: θέση του close μέσα στο πρόσφατο high-low range.
- Θεωρία: σε trend οι τιμές κλείνουν συχνά κοντά στα range extremes.

## stochastic_rsi

Stochastic normalization του RSI.

- Έξοδοι: `stoch_rsi_k`, `stoch_rsi_d` ή configured column names.
- Τύπος: πρώτα υπολογίζεται RSI και μετά `%K = 100 * (RSI - rolling_min_RSI) / (rolling_max_RSI - rolling_min_RSI)`, με `%D` ως trailing smoothing του `%K`.
- Χρησιμότητα: πιο ευαίσθητο oscillator για pullback/mean-reversion context από απλό RSI.
- Θεωρία: μετρά πού βρίσκεται το RSI μέσα στο πρόσφατο RSI range, όχι μέσα στο price range.
- Αιτιότητα: όλα τα rolling extrema/smoothing είναι trailing.

## price_momentum

Price-based momentum.

- Έξοδοι: `{price_col}_mom_{window}`.
- Τύπος: `price_t / price_{t-window} - 1`.
- Χρησιμότητα: απλή cumulative price move μέτρηση.
- Θεωρία: momentum/persistence ή contrarian reversal ανάλογα με horizon.

## return_momentum

Rolling άθροισμα αποδόσεων.

- Έξοδοι: `{returns_col}_mom_{window}`.
- Τύπος: `sum(returns_{t-window+1:t})`.
- Χρησιμότητα: momentum σε return space, ειδικά για log returns όπου το sum είναι cumulative log return.
- Θεωρία: aggregate drift over lookback.

## vol_normalized_momentum

Momentum διαιρεμένο με μεταβλητότητα.

- Έξοδοι: `{returns_col}_norm_mom_{window}`.
- Τύπος: rolling sum returns / volatility column.
- Χρησιμότητα: risk-adjusted momentum, πιο συγκρίσιμο μεταξύ regimes.
- Θεωρία: παρόμοια λογική με Sharpe-like scaling: return per unit risk.

## session_context

Χρονικά και session features.

- Έξοδοι: `hour_sin_24`, `hour_cos_24`, `day_of_week_sin_7`, `day_of_week_cos_7`, `session_{name}`, `session_europe_us_overlap`, `is_weekend`.
- Χρησιμότητα: intraday seasonality, session liquidity, weekend filtering.
- Θεωρία: οι αγορές έχουν διαφορετική συμπεριφορά ανά session λόγω liquidity, news flow και market participants.
- Αιτιότητα: βασίζεται μόνο στο timestamp.

## regime_context

Πλαίσιο μεταβλητότητας και trend regime.

- Έξοδοι: `regime_vol_ratio_{short}_{long}`, `regime_high_vol_state_*`, `regime_low_vol_state_*`, `regime_vol_ratio_z_*`, `regime_absret_z_*`, `regime_trend_ratio_{fast}_{slow}`, `regime_trend_state_{fast}_{slow}`.
- Τύπος volatility ratio: short rolling volatility / long rolling volatility.
- Χρησιμότητα: ξεχωρίζει high/low vol regimes και trend direction.
- Θεωρία: τα trading edges συνήθως εξαρτώνται από regime. Ένα momentum rule μπορεί να δουλεύει σε trend/high-vol και να αποτυγχάνει σε chop.

## shock_context

Πλαίσιο shock/reversion από returns, ATR και απόσταση από EMA.

- Έξοδοι: `shock_ret_*`, `shock_ret_z_*`, `shock_atr_multiple_*`, `shock_distance_ema`, `shock_up_candidate`, `shock_down_candidate`, `shock_candidate`, `shock_side_contrarian`, `shock_side_contrarian_active`, `shock_active_window`, `shock_strength`, `bars_since_shock`.
- Χρησιμότητα: βρίσκει μεγάλα directional moves που μπορεί να είναι continuation ή mean-reversion candidates.
- Θεωρία: extreme standardized moves συχνά αλλάζουν short-term distribution. Το feature δίνει contrarian side, όχι πρόβλεψη από μόνο του.
- Αιτιότητα: shock event είναι current-bar event και active window είναι forward-filled μόνο μετά το event.

## support_resistance

Rolling support/resistance.

- Έξοδοι: `support_{window}`, `resistance_{window}`, optional percentage/ATR distances.
- Support: rolling low minimum. Resistance: rolling high maximum.
- Χρησιμότητα: distance-to-level context, breakout/reversion filters.
- Θεωρία: πρόσφατα extrema λειτουργούν ως liquidity/stop/reference levels.

## support_resistance_v2

Confirmed pivot-based support/resistance.

- Έξοδοι: confirmed pivot levels, ages, touch counts, breakout/retest flags, ATR distances.
- Pivot confirmation γίνεται αφού περάσουν `pivot_confirm_bars`, ώστε τα live-safe levels να μην κοιτάνε μέλλον.
- Χρησιμότητα: πιο δομικά levels από απλό rolling min/max.
- Θεωρία: swing highs/lows γίνονται reference points μόνο αφού επιβεβαιωθεί ότι η αγορά απομακρύνθηκε από αυτά.
- Αιτιότητα: τα raw pivot candidates δεν χρησιμοποιούνται πριν confirmation.

## macro_context

Μετασχηματισμοί για exogenous/macro στήλες με ρητό availability lag.

- Έξοδοι: `{col}_avail_lag_{availability_lag}`, `{col}_lag_{lag}`, `{col}_pct_{period}`, `{col}_z_{window}`, `{col}_ema_gap_{span}`.
- Χρησιμότητα: ενσωματώνει macro/exogenous variables χωρίς να παραβιάζει publication lag.
- Θεωρία: macro variables μπορούν να εξηγήσουν regimes, αλλά η χρονική διαθεσιμότητα είναι κρίσιμη.
- Αιτιότητα: πρώτα κάνει `shift(availability_lag)`, μετά παράγει derived features.

## feature_transforms

Γενικοί μετασχηματισμοί μετά το raw feature.

- `rolling_clip`: winsorization με rolling quantile bounds που είναι shifted.
- `ratio`: ratio δύο ήδη διαθέσιμων columns.
- `rolling_zscore`: `(x - shifted rolling mean) / shifted rolling std`.
- Χρησιμότητα: robust scaling, normalization, derived ratios.
- Θεωρία: τα μοντέλα συχνά μαθαίνουν πιο σταθερά όταν features είναι normalized ή bounded.
- Αιτιότητα: rolling statistics είναι shifted by default.

## multi_timeframe

Higher-timeframe features aligned στο base timeframe.

- Outputs ανά timeframe: `mtf_{tf}_{returns_col}`, `mtf_{tf}_volatility`, `mtf_{tf}_trend_score`, `mtf_{tf}_atr`, `mtf_{tf}_adx`, `mtf_{tf}_regime_vol_ratio`.
- Resamples OHLCV σε higher timeframe, υπολογίζει features εκεί και τα κάνει backward `merge_asof` στο base frame.
- Χρησιμότητα: δίνει 1h/4h context σε 30m ή χαμηλότερο timeframe.
- Θεωρία: multi-timeframe confluence. Ένα short-term setup έχει διαφορετική πιθανότητα όταν το higher timeframe trend συμφωνεί.
- Αιτιότητα: `shift_to_last_closed=true` απαιτείται. Δεν επιτρέπεται να πάρει HTF bar που δεν έχει κλείσει.

## opening_range_breakout

Διαγνωστικά υποψήφιου Opening Range Breakout.

- Έξοδοι: `orb_range_high`, `orb_range_low`, `orb_candidate`, `orb_side`, breakout strength, active window, failed breakout flags, session labels.
- Υπολογίζει opening range από τα πρώτα `opening_range_bars` της session και μετά σηματοδοτεί breakouts πάνω/κάτω από το range.
- Χρησιμότητα: intraday breakout candidates σε London/New York sessions.
- Θεωρία: το opening range συχνά καθορίζει early-session liquidity boundaries. Breakouts μπορεί να δείχνουν order-flow imbalance.
- Αιτιότητα: το range γράφεται μόνο αφού κλείσει το τελευταίο opening range bar.

## swing_extrema_context

Πλαίσιο επιβεβαιωμένων τοπικών swing high/low.

- Έξοδοι: raw local extrema, confirmed extrema, last confirmed high/low distances, near-high/near-low flags, overextension context. Τα exact names είναι prefixed με `prefix`, default `swing`.
- Χρησιμότητα: market structure context, απόσταση από τελευταίο swing high/low.
- Θεωρία: swing highs/lows είναι structural pivots για trend, support/resistance και exhaustion.
- Αιτιότητα: confirmed extrema είναι live-safe μετά από `right_bars`. Raw local extrema και optional research labels είναι diagnostic/research-only και δεν πρέπει να μπουν σε production model features.

## indicator_pullback

Πακέτο pullback χαρακτηριστικών μόνο από indicators για model/meta-label pipelines.

- Έξοδοι: EMA slopes/alignment, MACD histogram slope, RSI/StochRSI crosses, ATR percentage/ranks, Bollinger bandwidth ranks, candle body/wick/location metrics, EMA distances, rolling returns/realized volatility και `asset_id` όταν ζητηθεί.
- Υπολογίζει missing prerequisite indicators locally όταν δεν υπάρχουν οι configured columns.
- Χρησιμότητα: compact, causal indicator state για pullback candidates χωρίς να χρειάζεται κάθε YAML να δηλώνει όλο το ίδιο feature plumbing.
- Θεωρία: συνδυάζει trend alignment, momentum turn, volatility compression/expansion και candle structure.
- Αιτιότητα: χρησιμοποιεί current/previous closed bars και trailing rolling statistics.

## ehlers_ml_long_candidate

Builder χαρακτηριστικών long-candidate από Ehlers/cycle εισόδους.

- Είσοδοι: Hilbert amplitude, dominant cycle period/phase, roofing filter, MAMA/FAMA, decycler, instantaneous trendline, FRAMA, SuperSmoother και optional ATR.
- Έξοδοι: `mama_minus_fama`, `close_minus_decycler`, slopes για trend filters, normalized cycle phase, optional ATR-scaled stationary distances/slopes, `ehlers_ml_candidate`, `signal_side`.
- Χρησιμότητα: deterministic candidate generator και feature enricher για Ehlers ML/meta-label experiments.
- Θεωρία: απαιτεί συμφωνία cycle/trend filters και κρατά stationary transforms όπως ATR-scaled distances όταν υπάρχει ATR.
- Αιτιότητα: δεν κάνει fit/predict και διαβάζει μόνο ήδη διαθέσιμα feature columns στο current timestamp.

## mama

MESA Adaptive Moving Average του John Ehlers.

- Έξοδος: `mama` ή `output_col`.
- Χρησιμότητα: adaptive trend line που αλλάζει smoothing με βάση phase/cycle dynamics.
- Θεωρία: σε σχέση με EMA/SMA, προσαρμόζει το effective alpha με MESA phase information.
- Αιτιότητα: η implementation είναι recursive/trailing πάνω στο διαθέσιμο price history.

## fama

Following Adaptive Moving Average, η companion γραμμή του MAMA.

- Έξοδος: `fama` ή `output_col`.
- Χρησιμότητα: slower adaptive line για MAMA/FAMA crossovers και trend confirmation.
- Θεωρία: το lagged/adaptive companion filter μειώνει whipsaw σε σχέση με single adaptive line.
- Αιτιότητα: χρησιμοποιεί τα ίδια causal MESA components με το MAMA.

## dominant_cycle_period

Εκτίμηση dominant cycle period με MESA.

- Έξοδος: `dominant_cycle_period` ή `output_col`.
- Χρησιμότητα: adaptive lookback/context για cycle-aware filters.
- Θεωρία: εκτιμά το dominant market cycle length από phase dynamics αντί να επιβάλλει fixed window.
- Αιτιότητα: υπολογίζεται από recursive components μέχρι το current bar.

## dominant_cycle_phase

Εκτίμηση dominant cycle phase με MESA.

- Μονάδα: προεπιλογή σε μοίρες (`0..360`). Με `unit: radians` γράφει radians
  (`0..2*pi`).
- Έξοδος: `dominant_cycle_phase` ή `output_col`.
- Χρησιμότητα: cycle-position feature για turning-point/cycle regime models.
- Θεωρία: phase features επιτρέπουν στο μοντέλο να δει πού βρίσκεται η αγορά μέσα στον εκτιμώμενο κύκλο.
- Αιτιότητα: trailing recursive calculation.

## instantaneous_trendline

Instantaneous trendline του Ehlers με προαιρετική trigger line.

- Έξοδοι: `instantaneous_trendline` και, όταν `add_trigger=true`, `instantaneous_trendline_trigger` ή configured names.
- Τύπος trigger: `2 * trendline_t - trendline_{t-2}`.
- Χρησιμότητα: low-lag trend reference και crossover context.
- Θεωρία: recursive filter που προσπαθεί να αφαιρέσει cyclic noise με μικρότερο lag από κλασικούς MAs.
- Αιτιότητα: χρησιμοποιεί μόνο current και past trendline/price values.

## fisher_transform

Fisher Transform σε rolling-normalized τιμή.

- Έξοδοι: `fisher_transform_{window}` και optional `{col}_signal`.
- Τύπος: rolling min/max normalization σε `[-1, 1]`, clipping, μετά Fisher mapping.
- Χρησιμότητα: oscillator με πιο Gaussian-like tails για threshold/crossing logic.
- Θεωρία: η Fisher transform τονίζει extreme normalized moves.
- Αιτιότητα: rolling range και signal line είναι trailing/lagged.

## inverse_fisher_transform

Inverse Fisher / tanh μετασχηματισμός σε configured είσοδο.

- Έξοδος: `inverse_fisher_transform_{window}` ή `output_col`.
- Τύπος: optional rolling min/max normalization, scale, μετά `tanh`.
- Χρησιμότητα: compresses noisy unbounded indicators σε bounded oscillator.
- Θεωρία: bounded nonlinear mapping κάνει extremes πιο σταθερά για rules/models.
- Αιτιότητα: normalization window είναι trailing.

## sinewave_indicator

Ehlers sinewave και lead-sinewave από dominant phase.

- Έξοδοι: `sinewave`, `lead_sinewave` ή configured names.
- Τύπος: `sin(phase)` και `sin(phase + lead_degrees)`.
- Χρησιμότητα: cycle turning-point context.
- Θεωρία: phase-to-sine mapping μετατρέπει cycle phase σε bounded oscillator.
- Αιτιότητα: phase προκύπτει από causal MESA components.

## cyber_cycle

Ehlers Cyber Cycle oscillator.

- Έξοδοι: `cyber_cycle` και optional `{col}_trigger`.
- Χρησιμότητα: cycle component after smoothing, χρήσιμο για short-term turning points.
- Θεωρία: αφαιρεί trend-like movement και κρατά high-frequency cyclic component.
- Αιτιότητα: recursive filter και trigger as lagged cycle value.

## decycler

Decycler trend filter του Ehlers.

- Έξοδος: `decycler_{period}` ή `output_col`.
- Χρησιμότητα: smoother trend/regime anchor με reduced cyclic component.
- Θεωρία: high-pass derived filter που αφαιρεί short-term cycles και κρατά trend component.
- Αιτιότητα: recursive/trailing calculation.

## decycler_oscillator

Normalized spread μεταξύ fast και slow decyclers.

- Έξοδος: `decycler_oscillator_{fast}_{slow}` ή `output_col`.
- Τύπος: `100 * (decycler_fast - decycler_slow) / price`.
- Χρησιμότητα: trend acceleration/continuation context.
- Θεωρία: fast-vs-slow decycler spread δείχνει αν το shorter trend component οδηγεί το longer component.
- Αιτιότητα: και οι δύο decyclers είναι trailing.

## laguerre_rsi

Laguerre-filtered RSI.

- Έξοδος: `laguerre_rsi` ή `output_col`, ως 0-1 ή 0-100 όταν `as_percent=true`.
- Χρησιμότητα: smoother oscillator με λιγότερο lag από απλό RSI σε ορισμένα regimes.
- Θεωρία: Laguerre filter stages δημιουργούν adaptive-like smoothing και συγκρίνουν upward/downward movement των stages.
- Αιτιότητα: recursive state updates μόνο από παρελθόν/current price.

## frama

Fractal Adaptive Moving Average.

- Έξοδοι: `frama_{window}` και optional diagnostics `{col}_alpha`, `{col}_fractal_dimension`.
- Χρησιμότητα: trend filter που αυξομειώνει smoothing ανάλογα με roughness/choppiness.
- Θεωρία: fractal dimension του recent high-low structure ελέγχει το adaptive alpha.
- Αιτιότητα: χρησιμοποιεί trailing high/low/price window.

## center_of_gravity

Ehlers Center of Gravity oscillator.

- Έξοδος: `center_of_gravity_{window}` ή `output_col`.
- Χρησιμότητα: short-term cycle/turning-point oscillator.
- Θεωρία: weighted center της πρόσφατης price window, με μεγαλύτερο βάρος στα πιο πρόσφατα observations.
- Αιτιότητα: trailing fixed window.

## even_better_sinewave

Ehlers Even Better Sinewave.

- Έξοδος: `even_better_sinewave` ή `output_col`.
- Χρησιμότητα: bounded cycle oscillator για cycle regimes.
- Θεωρία: high-pass filtering, SuperSmoother και power normalization παράγουν oscillator clipped σε `[-1, 1]`.
- Αιτιότητα: filters και power window είναι trailing.

## autocorrelation_periodogram

Causal autocorrelation periodogram dominant-period estimate.

- Έξοδοι: `autocorrelation_periodogram_{min}_{max}` και optional `{col}_power`.
- Τύπος: rolling autocorrelations across candidate periods, positive correlations squared as power weights.
- Χρησιμότητα: dominant-cycle period estimate ανεξάρτητο από MESA path.
- Θεωρία: periodic structure εμφανίζεται ως high autocorrelation σε συγκεκριμένα lags.
- Αιτιότητα: κάθε estimate χρησιμοποιεί μόνο trailing window.

## homodyne_discriminator

MESA homodyne discriminator period estimate.

- Έξοδος: `homodyne_discriminator` ή `output_col`.
- Χρησιμότητα: cycle-length estimate για adaptive filters και regime checks.
- Θεωρία: χρησιμοποιεί MESA in-phase/quadrature dynamics για period estimation.
- Αιτιότητα: recursive components μέχρι το current bar.

## parkinson_volatility

Εκτιμητής μεταβλητότητας από high-low range.

- Έξοδος: `parkinson_vol_{window}` ή `output_col`.
- Τύπος: rolling Parkinson variance από `log(high/low)`.
- Χρησιμότητα: volatility estimate που χρησιμοποιεί intrabar range αντί close-to-close returns.
- Θεωρία: under Brownian assumptions, high-low range είναι πιο πληροφοριακό από close-to-close move.
- Αιτιότητα: trailing high/low window.

## garman_klass_volatility

Εκτιμητής OHLC μεταβλητότητας.

- Έξοδος: `garman_klass_vol_{window}` ή `output_col`.
- Τύπος: rolling estimator από open-high-low-close log ranges.
- Χρησιμότητα: intrabar volatility context όταν υπάρχουν reliable OHLC bars.
- Θεωρία: συνδυάζει range και open-close move για χαμηλότερη variance estimate από close-only volatility.
- Αιτιότητα: trailing OHLC window.

## yang_zhang_volatility

Εκτιμητής OHLC μεταβλητότητας Yang-Zhang.

- Έξοδοι: `yang_zhang_vol_{window}` και optional rolling mean, ratio, rising flag, high-vol regime flag.
- Τύπος: συνδυάζει overnight/open-close μεταβλητότητα, close-to-open move και
  Rogers-Satchell range component.
- Χρησιμότητα: πιο complete OHLC volatility estimate, ειδικά όταν open gaps έχουν σημασία.
- Θεωρία: διαχωρίζει overnight και intraday volatility components.
- Αιτιότητα: rolling windows μέχρι το current bar.

## hurst_exponent

Rolling εκτίμηση Hurst exponent.

- Έξοδος: `hurst_{window}` ή `output_col`.
- Χρησιμότητα: persistence/mean-reversion regime context.
- Θεωρία: H > 0.5 δείχνει persistence, H < 0.5 anti-persistence, με caveats για noisy finite windows.
- Αιτιότητα: trailing price window.

## fractal_dimension

Rolling Katz fractal dimension.

- Έξοδος: `fractal_dimension_{window}` ή `output_col`.
- Χρησιμότητα: choppiness/roughness measure για trend-vs-noise regimes.
- Θεωρία: πιο high-dimensional path σημαίνει πιο rough/choppy movement.
- Αιτιότητα: trailing price window.

## zscore_momentum

Z-score momentum τιμής.

- Έξοδος: `zscore_momentum_{window}` ή `output_col`.
- Τύπος: `(price - rolling_mean) / rolling_std`.
- Χρησιμότητα: standardized distance from recent equilibrium.
- Θεωρία: mean-reversion ή trend continuation μπορούν να εξαρτώνται από standardized displacement.
- Αιτιότητα: rolling statistics είναι trailing.

## rolling_r2_trend_quality

Rolling ποιότητα τάσης από γραμμική παλινδρόμηση.

- Έξοδοι: R2 column και optional slope, intercept, rising flag, trend-quality flag.
- Τύπος: rolling regression of price on time index και `R^2` ως quality/linearity measure.
- Χρησιμότητα: ξεχωρίζει directional, clean trends από noisy drift.
- Θεωρία: υψηλό R2 σημαίνει ότι η πρόσφατη τιμή εξηγείται καλά από linear trend.
- Αιτιότητα: regression window είναι trailing.

## trend_slope_volatility

Κλίση τάσης κανονικοποιημένη με μεταβλητότητα.

- Έξοδοι: `trend_slope_{window}`, volatility-used, slope/volatility ratio και optional positive/rising/strong flags.
- Τύπος: rolling price slope divided by configured volatility column ή internally resolved trailing volatility.
- Χρησιμότητα: trend strength normalized by current risk/noise.
- Θεωρία: slope χωρίς volatility scaling δεν συγκρίνεται εύκολα μεταξύ assets/regimes.
- Αιτιότητα: slope και volatility είναι trailing.

## volatility_of_volatility

Rolling μεταβλητότητα της μεταβλητότητας.

- Έξοδοι: `volatility_of_volatility_{volatility_col}_{window}` και optional mean, ratio, rising/high flags.
- Τύπος: rolling standard deviation/variation of an existing volatility column.
- Χρησιμότητα: regime instability, risk model confidence και volatility expansion diagnostics.
- Θεωρία: όταν η volatility itself είναι volatile, fixed thresholds/position sizing γίνονται λιγότερο stable.
- Αιτιότητα: απαιτεί υπάρχουσα volatility column και trailing window.

## volatility_regime

Σκορ volatility regime.

- Έξοδος: `volatility_regime` ή `output_col`.
- Τύπος: είτε configured `vol_col` divided by trailing baseline είτε returns-derived rolling regime score.
- Χρησιμότητα: high/low volatility filters και stratification.
- Θεωρία: edge και risk distributions αλλάζουν materially ανά volatility regime.
- Αιτιότητα: trailing baseline/returns.

## hmm_regime

Regime labels από Hidden Markov Model.

- Έξοδος: configured regime/state column.
- Χρησιμότητα: discrete latent regime context από returns/feature distributions.
- Θεωρία: HMM υποθέτει latent states με διαφορετικές emission distributions.
- Αιτιότητα: πρέπει να χρησιμοποιείται με προσοχή: fitting πρέπει να γίνεται μόνο σε training/history και όχι σε full sample πριν split.
- Σημείωση leakage: οποιοδήποτε offline fit σε όλο το dataset πριν από
  train/test split είναι leakage.

## hilbert_transform

Causal rolling Hilbert endpoint χαρακτηριστικά.

- Έξοδοι: `hilbert_amplitude_{window}`, `hilbert_phase_{window}`, `hilbert_instantaneous_frequency_{window}` ή configured names.
- Derived columns όπως dominant cycle reciprocal, cycle-ok flag και amplitude-rising flag δεν παράγονται πλέον από το raw builder. Χρησιμοποίησε `reciprocal`, `between_flag`, `rising_flag`.
- Χρησιμότητα: amplitude/phase/frequency context για cycle-aware strategies.
- Θεωρία: η αποσύνθεση αναλυτικού σήματος δίνει εκτιμήσεις στιγμιαίας
  phase/amplitude.
- Αιτιότητα: εφαρμόζει Hilbert σε trailing window και κρατά μόνο endpoint values.

## roofing_filter

Ehlers Roofing Filter.

- Έξοδος: `roofing_filter_{high_pass}_{low_pass}` ή `output_col`.
- Derived slope/positive/cross flags δεν παράγονται από το raw builder. Χρησιμοποίησε helpers.
- Χρησιμότητα: αφαιρεί slow trend και high-frequency noise, κρατώντας tradeable cycle band.
- Θεωρία: high-pass plus SuperSmoother-like low-pass band-pass filtering.
- Αιτιότητα: recursive/trailing filter.

## schaff_trend_cycle

Schaff Trend Cycle oscillator.

- Έξοδοι: `stc`, `stc_signal` ή configured names.
- Τύπος: EMA fast/slow oscillator, stochastic normalization, causal EMA smoothing passes.
- Derived cross/rising/falling flags πρέπει να δηλώνονται με helpers.
- Χρησιμότητα: trend/momentum oscillator με faster turning behavior από MACD.
- Θεωρία: combines MACD trend information with stochastic cycle normalization.
- Αιτιότητα: trailing EMAs και rolling stochastic windows.

## supersmoother

Low-pass φίλτρο Ehlers SuperSmoother.

- Έξοδος: `supersmoother_{period}` ή `output_col`.
- Χρησιμότητα: low-lag smoothing για noisy price/indicator inputs.
- Θεωρία: two-pole recursive filter που μειώνει high-frequency noise.
- Αιτιότητα: recursive filter με current/past values.

## shannon_entropy

Rolling Shannon entropy.

- Έξοδος: entropy column, default tied to configured `window`/bins.
- Χρησιμότητα: uncertainty/disorder context για returns ή price changes.
- Θεωρία: higher entropy σημαίνει πιο dispersed/unpredictable recent distribution.
- Αιτιότητα: trailing window.

## permutation_entropy

Rolling permutation entropy.

- Έξοδος: permutation entropy column, default tied to `window`/order/delay.
- Χρησιμότητα: ordinal-pattern complexity measure robust to monotone transforms.
- Θεωρία: μετρά diversity των rank-order patterns μέσα σε trailing window.
- Αιτιότητα: trailing ordinal patterns.

## vpin

Proxy για volume-synchronized probability of informed trading.

- Έξοδος: `vpin_{window}` ή `output_col`.
- Χρησιμότητα: order-flow toxicity/liquidity-stress proxy όταν υπάρχουν volume/buy-sell proxy inputs.
- Θεωρία: επίμονη ανισορροπία στα volume buckets μπορεί να δείχνει informed
  flow ή adverse selection.
- Αιτιότητα: trailing imbalance aggregation.

## order_flow_imbalance

Order-flow imbalance από buy/sell volume ή quote sizes.

- Έξοδος: `order_flow_imbalance` / `order_flow_imbalance_{window}` ή `output_col`.
- Τύπος: buy-sell imbalance, optionally normalized by total flow/size.
- Χρησιμότητα: microstructure pressure feature για short-horizon models.
- Θεωρία: directional pressure εμφανίζεται όταν το aggressive buy/sell flow ή
  το bid/ask depth είναι ανισορροπημένο.
- Αιτιότητα: απαιτεί στήλες διαθέσιμες στο timestamp. Το rolling aggregation
  είναι trailing.

## scalp_microstructure_proxy

Quote/spread-aware proxy feature builder για intraday/scalp datasets με bid/ask
OHLC bars.

- Είσοδοι: OHLCV, bid/ask OHLC, `spread_close`, `spread_bps`.
- Έξοδοι: `mid_open`, `mid_high`, `mid_low`, `mid_close`,
  `bid_ask_spread_abs`, `bid_ask_spread_bps`, `spread_bps_change`,
  `bar_range`, `bar_body`, `close_pos_in_bar`, `body_to_range`, wicks,
  `candle_pressure`, `signed_volume_proxy`, `buy_volume_proxy`,
  `sell_volume_proxy`, `ofi_proxy_norm_1`.
- Χρησιμότητα: δίνει causal candle/quote geometry και proxy buy/sell flow για
  short-horizon candidate generation, VPIN και order-flow imbalance inputs.
- Normalization: spread percent rank/z-score, wick/body/range divided by ATR,
  `volume_relative`, rolling z-scores για OFI proxy, VPIN percent rank.
- Περιορισμός: `signed_volume_proxy`, `buy_volume_proxy`, `sell_volume_proxy`,
  OFI και VPIN εδώ δεν είναι πραγματικό order flow, γιατί δεν υπάρχουν
  aggressor-side ticks, bid/ask sizes ή exchange prints.
- Αιτιότητα: χρησιμοποιεί only current closed bar και past `shift(1)` για
  `spread_bps_change`; πρέπει να εκτελείται με next-bar/open convention.

## roc_long_only_conditions

Manual long-only condition builder. Είναι διαθέσιμο και ως feature step και ως signal kind.

- Είσοδοι: `roc_*`, `regime_vol_ratio_z_*`, `close_z`, `close_open_ratio`, `mtf_1h_trend_score`, `mtf_4h_trend_score`, `is_weekend`, optional macro condition.
- Έξοδοι: condition flags (`cond_*`), score (`manual_conviction_score`), long candidate, short signal 0, combined signal, volatility-adjusted exposure.
- Λογική: μετρά πόσες συνθήκες περνάνε και ανοίγει long όταν το score >= `min_score_required`, με weekend/macro gates και optional required conditions.
- Vol adjustment: `1 / (1 + vol_adjustment_strength * max(regime_vol_z, 0))`, clipped σε `[min_exposure, max_exposure]`.
- Χρησιμότητα: interpretable manual candidate generator για EDA, meta-labeling και model filtering.
- Θεωρία: συνδυάζει momentum, regime, multi-timeframe confirmation, z-score location και candle confirmation σε rule-based score.
- Αιτιότητα: δεν κάνει fit/predict. Χρησιμοποιεί current-bar closed features και το backtest πρέπει να εκτελεί στο επόμενο bar/open.

## Compatibility signal-like feature steps

Στα ελληνικά, αυτά είναι compatibility feature steps που μοιάζουν με signals.
Υπάρχουν για παλιά configs ή dashboard compatibility και πρέπει να
χρησιμοποιούνται ως candidate/signal builders, όχι ως καθαρά transforms.

Τα παρακάτω steps είναι resolvable από configs μέσω `FEATURE_COMPATIBILITY_REGISTRY` ή/και από το dashboard compatibility layer, αλλά δεν ανήκουν στο canonical `FEATURE_REGISTRY` των raw feature builders. Να τα χρησιμοποιείς ως candidate/signal builders, όχι ως pure transforms.

| Step | Έξοδοι | Χρήση |
|---|---|---|
| `ehlers_semiscalp_long` | `signal_side`, `signal_candidate` και setup flags | Long-only Ehlers semiscalp candidate. |
| `ehlers_decycler_continuation` | `signal_side`, `signal_candidate` | Long-only decycler continuation candidate. |
| `ema_stoch_rsi_pullback` | side/candidate columns και EMA/StochRSI diagnostics | Long/short EMA + StochRSI pullback candidate. |
| `indicator_model_adaptive_pullback` | `candidate_long`, `candidate_short`, direction/signal/candidate/score columns | Indicator-only adaptive pullback candidate πριν από model filtering. |
| `vwap_rms_ema_cross_long` | regime/cross/PPO/MFI setup columns, `signal_side`, `signal_candidate` | VWAP/RMS/EMA cross candidate με προαιρετικό PPO/MFI confirmation. |

Σημείωση leakage: επειδή αυτά γράφουν signal/candidate columns, πρέπει να
επιβεβαιώνεται ότι το backtest/model χρησιμοποιεί next-bar execution ή άλλο
ρητό execution lag.
