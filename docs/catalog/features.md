# Feature Catalog

Τελευταία ενημέρωση: 2026-06-27

Αυτό το αρχείο τεκμηριώνει τα feature steps που είναι διαθέσιμα μέσω του
`FEATURE_REGISTRY` στο `src/features/registry.py`. Όλα τα features πρέπει να
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
- Τα raw feature steps δεν πρέπει να γεμίζουν το dataframe με derived helper
  columns by default. Ratios, lags, slopes, flags, crossings, z-scores και
  rolling aggregations δηλώνονται ως helpers στο YAML.

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

## returns

Υπολογίζει απλές ή λογαριθμικές αποδόσεις από το `close`.

- Output: `close_ret` όταν `log=false`, `close_logret` όταν `log=true`, ή όνομα από `col_name`.
- Τύπος: απλή απόδοση `close_t / close_{t-1} - 1`; log return `log(close_t / close_{t-1})`.
- Χρησιμότητα: βασική μεταβλητή για volatility, momentum, targets και backtests.
- Θεωρία: οι αποδόσεις είναι πιο stationary από τις τιμές και συγκρίνονται πιο εύκολα μεταξύ assets.
- Causality: χρησιμοποιεί μόνο `t` και `t-1`.

## volatility

Υπολογίζει realized volatility από ήδη υπάρχουσα στήλη returns.

- Outputs: `vol_rolling_{w}` για rolling standard deviation και `vol_ewma_{span}` για exponentially weighted volatility.
- Τύπος rolling: `std(returns_{t-w+1:t})`, προαιρετικά annualized με `sqrt(annualization_factor)`.
- Τύπος EWMA: exponentially weighted standard deviation.
- Χρησιμότητα: volatility regimes, risk scaling, stop distances, feature normalization.
- Θεωρία: το volatility clustering είναι κεντρικό χαρακτηριστικό χρηματοοικονομικών χρονοσειρών.
- Causality: rolling/EWMA χρησιμοποιούν μέχρι το current bar.

## trend

Υπολογίζει SMA/EMA. Relative distances/ratios δηλώνονται με helpers.

- Outputs: `{price_col}_sma_{window}`, `{price_col}_ema_{span}` ή configured column names.
- Ratio τύπος μέσω helper: `price / moving_average - 1`.
- Χρησιμότητα: μετρά κατεύθυνση και απόσταση από trend anchors.
- Θεωρία: moving averages είναι low-pass filters που εξομαλύνουν θόρυβο και αναδεικνύουν trend.
- Causality: SMA/EMA είναι trailing.

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
- Outputs: `{price_col}_trend_regime_sma_{base_sma}` και `{price_col}_trend_state_sma_{short}_{long}`.
- Τύπος regime: `sign(price_over_sma)`.
- Τύπος state: `1` όταν short SMA > long SMA, `-1` όταν short SMA < long SMA, `0` όταν λείπουν δεδομένα.
- Χρησιμότητα: απλή regime μεταβλητή για filters, signals και stratification.
- Θεωρία: trend following υποθέτει persistence όταν οι βραχυπρόθεσμοι μέσοι είναι πάνω από τους μακροπρόθεσμους.

## lags

Δημιουργεί καθυστερημένες εκδοχές επιλεγμένων columns.

- Outputs: `{prefix}_{col}_{lag}`.
- Τύπος: `x_{t-lag}`.
- Χρησιμότητα: δίνει στο μοντέλο ιστορική κατάσταση χωρίς sequence model.
- Θεωρία: autoregressive information, lagged dependence, persistence/reversal.
- Causality: ασφαλές, γιατί κοιτά μόνο παρελθόν.

## bollinger

Υπολογίζει Bollinger Bands γύρω από rolling mean.

- Outputs: `bb_ma_{window}`, `bb_upper_{window}_{n_std}`, `bb_lower_{window}_{n_std}`, `bb_width_{window}_{n_std}`, `bb_percent_b_{window}_{n_std}`.
- Τύπος: `MA +/- n_std * rolling_std`; `%B = (price - lower) / (upper - lower)`.
- Χρησιμότητα: mean-reversion context, volatility expansion/compression, overextension.
- Θεωρία: bands προσεγγίζουν κανονικοποιημένη απόσταση της τιμής από rolling equilibrium.

## macd

Υπολογίζει MACD από δύο EMAs και signal line.

- Outputs: `macd_{fast}_{slow}`, `macd_signal_{signal}`, `macd_hist_{fast}_{slow}_{signal}`.
- Τύπος: `EMA_fast - EMA_slow`; signal = EMA του MACD; histogram = MACD - signal.
- Χρησιμότητα: momentum/trend acceleration και crossovers.
- Θεωρία: σύγκριση γρήγορου και αργού φίλτρου για να εντοπιστεί αλλαγή momentum.

## ppo

Percentage Price Oscillator, normalized MACD.

- Outputs: `ppo_{fast}_{slow}`, `ppo_signal_{signal}`, `ppo_hist_{fast}_{slow}_{signal}`.
- Τύπος: `(EMA_fast - EMA_slow) / EMA_slow`.
- Χρησιμότητα: MACD-like momentum συγκρίσιμο μεταξύ assets/price levels.
- Θεωρία: scale normalization μειώνει price-level dependence.

## roc

Rate of Change για ένα ή περισσότερα windows.

- Outputs: `roc_{window}`.
- Τύπος: `close_t / close_{t-window} - 1`.
- Χρησιμότητα: direct momentum/reversal measure.
- Θεωρία: cumulative return over lookback. Θετικό ROC δείχνει πρόσφατη ανοδική τάση.

## atr

Average True Range.

- Outputs: `atr_{window}` ή configured ATR column. Το `atr_over_price` γίνεται
  με `transforms.ratio` ή `normalizations.volatility`.
- True Range: max από `high-low`, `abs(high-prev_close)`, `abs(low-prev_close)`.
- ATR: Wilder EWMA ή simple rolling mean του True Range.
- Χρησιμότητα: stop distances, volatility normalization, position sizing.
- Θεωρία: μετρά absolute range volatility, όχι κατεύθυνση.

## adx

Average Directional Index μαζί με directional indicators.

- Outputs: `plus_di_{window}`, `minus_di_{window}`, `adx_{window}`.
- Υπολογίζει positive/negative directional movement, τα εξομαλύνει με Wilder EWMA και παράγει ADX.
- Χρησιμότητα: strength filter για trend strategies, ανεξάρτητα από long/short direction.
- Θεωρία: ADX υψηλό σημαίνει directional structure, όχι απαραίτητα bullish.

## volume_features

Volume normalization και volume/range context.

- Outputs: `volume_z_{vol_z_window}`, `volume_over_atr_{atr_window}`.
- Τύπος z-score: `(volume - rolling_mean) / rolling_std`.
- `volume_over_atr`: volume divided by ATR.
- Χρησιμότητα: participation/liquidity proxy, abnormal activity detection.
- Θεωρία: volume spikes συχνά συνοδεύουν breakouts, capitulation ή regime changes.

## vwap

Rolling Volume Weighted Average Price από typical price και volume.

- Outputs: `vwap_{window}` ή configured VWAP column. Το distance/ratio από VWAP
  γίνεται με `transforms.ratio`.
- Τύπος: `sum(((high+low+close)/3) * volume) / sum(volume)` σε trailing rolling window.
- Χρησιμότητα: liquidity-weighted fair-value anchor και distance-from-VWAP context.
- Θεωρία: η απόσταση από VWAP δείχνει αν το current close είναι πάνω ή κάτω από την πρόσφατη volume-weighted consensus price.
- Causality: rolling window μέχρι το current bar, χωρίς future bars.

## mfi

Money Flow Index.

- Output: `mfi_{window}`.
- Τύπος: typical price `(high+low+close)/3`, raw money flow = typical price * volume, ratio positive/negative money flow, mapped to 0-100.
- Χρησιμότητα: oscillator που συνδυάζει price και volume.
- Θεωρία: RSI-like momentum με volume weighting.

## rsi

Relative Strength Index.

- Outputs: `{price_col}_rsi_{window}`.
- Τύπος: μέσο κέρδος / μέση ζημιά, με Wilder ή simple averaging, mapped σε 0-100.
- Χρησιμότητα: overbought/oversold context, mean reversion, momentum exhaustion.
- Θεωρία: συγκρίνει magnitude ανοδικών και καθοδικών κινήσεων.

## stochastic

Stochastic oscillator.

- Outputs: `{price_col}_stoch_k_{window}`, `{price_col}_stoch_d_{window}`.
- `%K = 100 * (close - rolling_low) / (rolling_high - rolling_low)`.
- `%D`: rolling mean του `%K`.
- Χρησιμότητα: θέση του close μέσα στο πρόσφατο high-low range.
- Θεωρία: σε trend οι τιμές κλείνουν συχνά κοντά στα range extremes.

## price_momentum

Price-based momentum.

- Outputs: `{price_col}_mom_{window}`.
- Τύπος: `price_t / price_{t-window} - 1`.
- Χρησιμότητα: απλή cumulative price move μέτρηση.
- Θεωρία: momentum/persistence ή contrarian reversal ανάλογα με horizon.

## return_momentum

Rolling sum returns.

- Outputs: `{returns_col}_mom_{window}`.
- Τύπος: `sum(returns_{t-window+1:t})`.
- Χρησιμότητα: momentum σε return space, ειδικά για log returns όπου το sum είναι cumulative log return.
- Θεωρία: aggregate drift over lookback.

## vol_normalized_momentum

Momentum divided by volatility.

- Outputs: `{returns_col}_norm_mom_{window}`.
- Τύπος: rolling sum returns / volatility column.
- Χρησιμότητα: risk-adjusted momentum, πιο συγκρίσιμο μεταξύ regimes.
- Θεωρία: παρόμοια λογική με Sharpe-like scaling: return per unit risk.

## session_context

Χρονικά και session features.

- Outputs: `hour_sin_24`, `hour_cos_24`, `day_of_week_sin_7`, `day_of_week_cos_7`, `session_{name}`, `session_europe_us_overlap`, `is_weekend`.
- Χρησιμότητα: intraday seasonality, session liquidity, weekend filtering.
- Θεωρία: οι αγορές έχουν διαφορετική συμπεριφορά ανά session λόγω liquidity, news flow και market participants.
- Causality: βασίζεται μόνο στο timestamp.

## regime_context

Volatility και trend regime context.

- Outputs: `regime_vol_ratio_{short}_{long}`, `regime_high_vol_state_*`, `regime_low_vol_state_*`, `regime_vol_ratio_z_*`, `regime_absret_z_*`, `regime_trend_ratio_{fast}_{slow}`, `regime_trend_state_{fast}_{slow}`.
- Τύπος volatility ratio: short rolling volatility / long rolling volatility.
- Χρησιμότητα: ξεχωρίζει high/low vol regimes και trend direction.
- Θεωρία: τα trading edges συνήθως εξαρτώνται από regime. Ένα momentum rule μπορεί να δουλεύει σε trend/high-vol και να αποτυγχάνει σε chop.

## shock_context

Shock/reversion context από returns, ATR και απόσταση από EMA.

- Outputs: `shock_ret_*`, `shock_ret_z_*`, `shock_atr_multiple_*`, `shock_distance_ema`, `shock_up_candidate`, `shock_down_candidate`, `shock_candidate`, `shock_side_contrarian`, `shock_side_contrarian_active`, `shock_active_window`, `shock_strength`, `bars_since_shock`.
- Χρησιμότητα: βρίσκει μεγάλα directional moves που μπορεί να είναι continuation ή mean-reversion candidates.
- Θεωρία: extreme standardized moves συχνά αλλάζουν short-term distribution. Το feature δίνει contrarian side, όχι πρόβλεψη από μόνο του.
- Causality: shock event είναι current-bar event και active window είναι forward-filled μόνο μετά το event.

## support_resistance

Rolling support/resistance.

- Outputs: `support_{window}`, `resistance_{window}`, optional percentage/ATR distances.
- Support: rolling low minimum. Resistance: rolling high maximum.
- Χρησιμότητα: distance-to-level context, breakout/reversion filters.
- Θεωρία: πρόσφατα extrema λειτουργούν ως liquidity/stop/reference levels.

## support_resistance_v2

Confirmed pivot-based support/resistance.

- Outputs: confirmed pivot levels, ages, touch counts, breakout/retest flags, ATR distances.
- Pivot confirmation γίνεται αφού περάσουν `pivot_confirm_bars`, ώστε τα live-safe levels να μην κοιτάνε μέλλον.
- Χρησιμότητα: πιο δομικά levels από απλό rolling min/max.
- Θεωρία: swing highs/lows γίνονται reference points μόνο αφού επιβεβαιωθεί ότι η αγορά απομακρύνθηκε από αυτά.
- Causality: τα raw pivot candidates δεν χρησιμοποιούνται πριν confirmation.

## macro_context

Transforms για exogenous/macro columns με explicit availability lag.

- Outputs: `{col}_avail_lag_{availability_lag}`, `{col}_lag_{lag}`, `{col}_pct_{period}`, `{col}_z_{window}`, `{col}_ema_gap_{span}`.
- Χρησιμότητα: ενσωματώνει macro/exogenous variables χωρίς να παραβιάζει publication lag.
- Θεωρία: macro variables μπορούν να εξηγήσουν regimes, αλλά η χρονική διαθεσιμότητα είναι κρίσιμη.
- Causality: πρώτα κάνει `shift(availability_lag)`, μετά παράγει derived features.

## feature_transforms

Generic post-feature transforms.

- `rolling_clip`: winsorization με rolling quantile bounds που είναι shifted.
- `ratio`: ratio δύο ήδη διαθέσιμων columns.
- `rolling_zscore`: `(x - shifted rolling mean) / shifted rolling std`.
- Χρησιμότητα: robust scaling, normalization, derived ratios.
- Θεωρία: τα μοντέλα συχνά μαθαίνουν πιο σταθερά όταν features είναι normalized ή bounded.
- Causality: rolling statistics είναι shifted by default.

## multi_timeframe

Higher-timeframe features aligned στο base timeframe.

- Outputs ανά timeframe: `mtf_{tf}_{returns_col}`, `mtf_{tf}_volatility`, `mtf_{tf}_trend_score`, `mtf_{tf}_atr`, `mtf_{tf}_adx`, `mtf_{tf}_regime_vol_ratio`.
- Resamples OHLCV σε higher timeframe, υπολογίζει features εκεί και τα κάνει backward `merge_asof` στο base frame.
- Χρησιμότητα: δίνει 1h/4h context σε 30m ή χαμηλότερο timeframe.
- Θεωρία: multi-timeframe confluence. Ένα short-term setup έχει διαφορετική πιθανότητα όταν το higher timeframe trend συμφωνεί.
- Causality: `shift_to_last_closed=true` απαιτείται. Δεν επιτρέπεται να πάρει HTF bar που δεν έχει κλείσει.

## opening_range_breakout

Opening Range Breakout candidate diagnostics.

- Outputs: `orb_range_high`, `orb_range_low`, `orb_candidate`, `orb_side`, breakout strength, active window, failed breakout flags, session labels.
- Υπολογίζει opening range από τα πρώτα `opening_range_bars` της session και μετά σηματοδοτεί breakouts πάνω/κάτω από το range.
- Χρησιμότητα: intraday breakout candidates σε London/New York sessions.
- Θεωρία: το opening range συχνά καθορίζει early-session liquidity boundaries. Breakouts μπορεί να δείχνουν order-flow imbalance.
- Causality: το range γράφεται μόνο αφού κλείσει το τελευταίο opening range bar.

## swing_extrema_context

Confirmed local swing high/low context.

- Outputs: raw local extrema, confirmed extrema, last confirmed high/low distances, near-high/near-low flags, overextension context. Τα exact names είναι prefixed με `prefix`, default `swing`.
- Χρησιμότητα: market structure context, απόσταση από τελευταίο swing high/low.
- Θεωρία: swing highs/lows είναι structural pivots για trend, support/resistance και exhaustion.
- Causality: confirmed extrema είναι live-safe μετά από `right_bars`. Raw local extrema και optional research labels είναι diagnostic/research-only και δεν πρέπει να μπουν σε production model features.

## roc_long_only_conditions

Manual long-only condition builder. Είναι διαθέσιμο και ως feature step και ως signal kind.

- Inputs: `roc_*`, `regime_vol_ratio_z_*`, `close_z`, `close_open_ratio`, `mtf_1h_trend_score`, `mtf_4h_trend_score`, `is_weekend`, optional macro condition.
- Outputs: condition flags (`cond_*`), score (`manual_conviction_score`), long candidate, short signal 0, combined signal, volatility-adjusted exposure.
- Λογική: μετρά πόσες συνθήκες περνάνε και ανοίγει long όταν το score >= `min_score_required`, με weekend/macro gates και optional required conditions.
- Vol adjustment: `1 / (1 + vol_adjustment_strength * max(regime_vol_z, 0))`, clipped σε `[min_exposure, max_exposure]`.
- Χρησιμότητα: interpretable manual candidate generator για EDA, meta-labeling και model filtering.
- Θεωρία: συνδυάζει momentum, regime, multi-timeframe confirmation, z-score location και candle confirmation σε rule-based score.
- Causality: δεν κάνει fit/predict. Χρησιμοποιεί current-bar closed features και το backtest πρέπει να εκτελεί στο επόμενο bar/open.
