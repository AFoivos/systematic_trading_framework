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
| trading normalization | `normalizations.rolling_percent_rank`, `robust_zscore`, `volatility_scaled_return`, `atr_scaled_distance`, `range_position`, `realized_vol_percentile`, `volume_relative`, `rolling_beta_residual` |

## Transform helpers

Τα transform helpers δηλώνονται κάτω από `transforms:` μέσα σε feature step και
δουλεύουν πάνω σε ήδη διαθέσιμες columns. Δεν πρέπει να κρύβουν νέα raw feature
logic. Είναι για deterministic derived columns όπως ratios, lags, slopes,
flags και rolling summaries.

| Helper | Output default | Περιγραφή | Causality |
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

| Helper | Output default | Περιγραφή | Causality / leakage note |
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

## stochastic_rsi

Stochastic normalization του RSI.

- Outputs: `stoch_rsi_k`, `stoch_rsi_d` ή configured column names.
- Τύπος: πρώτα υπολογίζεται RSI και μετά `%K = 100 * (RSI - rolling_min_RSI) / (rolling_max_RSI - rolling_min_RSI)`, με `%D` ως trailing smoothing του `%K`.
- Χρησιμότητα: πιο ευαίσθητο oscillator για pullback/mean-reversion context από απλό RSI.
- Θεωρία: μετρά πού βρίσκεται το RSI μέσα στο πρόσφατο RSI range, όχι μέσα στο price range.
- Causality: όλα τα rolling extrema/smoothing είναι trailing.

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

## indicator_pullback

Indicator-only pullback feature bundle για model/meta-label pipelines.

- Outputs: EMA slopes/alignment, MACD histogram slope, RSI/StochRSI crosses, ATR percentage/ranks, Bollinger bandwidth ranks, candle body/wick/location metrics, EMA distances, rolling returns/realized volatility και `asset_id` όταν ζητηθεί.
- Υπολογίζει missing prerequisite indicators locally όταν δεν υπάρχουν οι configured columns.
- Χρησιμότητα: compact, causal indicator state για pullback candidates χωρίς να χρειάζεται κάθε YAML να δηλώνει όλο το ίδιο feature plumbing.
- Θεωρία: συνδυάζει trend alignment, momentum turn, volatility compression/expansion και candle structure.
- Causality: χρησιμοποιεί current/previous closed bars και trailing rolling statistics.

## ehlers_ml_long_candidate

Long-candidate feature builder από Ehlers/cycle inputs.

- Inputs: Hilbert amplitude, dominant cycle period/phase, roofing filter, MAMA/FAMA, decycler, instantaneous trendline, FRAMA, SuperSmoother και optional ATR.
- Outputs: `mama_minus_fama`, `close_minus_decycler`, slopes για trend filters, normalized cycle phase, optional ATR-scaled stationary distances/slopes, `ehlers_ml_candidate`, `signal_side`.
- Χρησιμότητα: deterministic candidate generator και feature enricher για Ehlers ML/meta-label experiments.
- Θεωρία: απαιτεί συμφωνία cycle/trend filters και κρατά stationary transforms όπως ATR-scaled distances όταν υπάρχει ATR.
- Causality: δεν κάνει fit/predict και διαβάζει μόνο ήδη διαθέσιμα feature columns στο current timestamp.

## mama

John Ehlers MESA Adaptive Moving Average.

- Output: `mama` ή `output_col`.
- Χρησιμότητα: adaptive trend line που αλλάζει smoothing με βάση phase/cycle dynamics.
- Θεωρία: σε σχέση με EMA/SMA, προσαρμόζει το effective alpha με MESA phase information.
- Causality: η implementation είναι recursive/trailing πάνω στο διαθέσιμο price history.

## fama

Following Adaptive Moving Average, companion line του MAMA.

- Output: `fama` ή `output_col`.
- Χρησιμότητα: slower adaptive line για MAMA/FAMA crossovers και trend confirmation.
- Θεωρία: το lagged/adaptive companion filter μειώνει whipsaw σε σχέση με single adaptive line.
- Causality: χρησιμοποιεί τα ίδια causal MESA components με το MAMA.

## dominant_cycle_period

MESA dominant cycle period estimate.

- Output: `dominant_cycle_period` ή `output_col`.
- Χρησιμότητα: adaptive lookback/context για cycle-aware filters.
- Θεωρία: εκτιμά το dominant market cycle length από phase dynamics αντί να επιβάλλει fixed window.
- Causality: υπολογίζεται από recursive components μέχρι το current bar.

## dominant_cycle_phase

MESA dominant cycle phase estimate.

- Output: `dominant_cycle_phase` ή `output_col`.
- Χρησιμότητα: cycle-position feature για turning-point/cycle regime models.
- Θεωρία: phase features επιτρέπουν στο μοντέλο να δει πού βρίσκεται η αγορά μέσα στον εκτιμώμενο κύκλο.
- Causality: trailing recursive calculation.

## instantaneous_trendline

Ehlers instantaneous trendline με optional trigger line.

- Outputs: `instantaneous_trendline` και, όταν `add_trigger=true`, `instantaneous_trendline_trigger` ή configured names.
- Τύπος trigger: `2 * trendline_t - trendline_{t-2}`.
- Χρησιμότητα: low-lag trend reference και crossover context.
- Θεωρία: recursive filter που προσπαθεί να αφαιρέσει cyclic noise με μικρότερο lag από κλασικούς MAs.
- Causality: χρησιμοποιεί μόνο current και past trendline/price values.

## fisher_transform

Fisher Transform σε rolling-normalized price.

- Outputs: `fisher_transform_{window}` και optional `{col}_signal`.
- Τύπος: rolling min/max normalization σε `[-1, 1]`, clipping, μετά Fisher mapping.
- Χρησιμότητα: oscillator με πιο Gaussian-like tails για threshold/crossing logic.
- Θεωρία: η Fisher transform τονίζει extreme normalized moves.
- Causality: rolling range και signal line είναι trailing/lagged.

## inverse_fisher_transform

Inverse Fisher / tanh transform σε configured input.

- Output: `inverse_fisher_transform_{window}` ή `output_col`.
- Τύπος: optional rolling min/max normalization, scale, μετά `tanh`.
- Χρησιμότητα: compresses noisy unbounded indicators σε bounded oscillator.
- Θεωρία: bounded nonlinear mapping κάνει extremes πιο σταθερά για rules/models.
- Causality: normalization window είναι trailing.

## sinewave_indicator

Ehlers sinewave και lead-sinewave από dominant phase.

- Outputs: `sinewave`, `lead_sinewave` ή configured names.
- Τύπος: `sin(phase)` και `sin(phase + lead_degrees)`.
- Χρησιμότητα: cycle turning-point context.
- Θεωρία: phase-to-sine mapping μετατρέπει cycle phase σε bounded oscillator.
- Causality: phase προκύπτει από causal MESA components.

## cyber_cycle

Ehlers Cyber Cycle oscillator.

- Outputs: `cyber_cycle` και optional `{col}_trigger`.
- Χρησιμότητα: cycle component after smoothing, χρήσιμο για short-term turning points.
- Θεωρία: αφαιρεί trend-like movement και κρατά high-frequency cyclic component.
- Causality: recursive filter και trigger as lagged cycle value.

## decycler

Ehlers decycler trend filter.

- Output: `decycler_{period}` ή `output_col`.
- Χρησιμότητα: smoother trend/regime anchor με reduced cyclic component.
- Θεωρία: high-pass derived filter που αφαιρεί short-term cycles και κρατά trend component.
- Causality: recursive/trailing calculation.

## decycler_oscillator

Normalized spread μεταξύ fast και slow decyclers.

- Output: `decycler_oscillator_{fast}_{slow}` ή `output_col`.
- Τύπος: `100 * (decycler_fast - decycler_slow) / price`.
- Χρησιμότητα: trend acceleration/continuation context.
- Θεωρία: fast-vs-slow decycler spread δείχνει αν το shorter trend component οδηγεί το longer component.
- Causality: και οι δύο decyclers είναι trailing.

## laguerre_rsi

Laguerre-filtered RSI.

- Output: `laguerre_rsi` ή `output_col`, ως 0-1 ή 0-100 όταν `as_percent=true`.
- Χρησιμότητα: smoother oscillator με λιγότερο lag από απλό RSI σε ορισμένα regimes.
- Θεωρία: Laguerre filter stages δημιουργούν adaptive-like smoothing και συγκρίνουν upward/downward movement των stages.
- Causality: recursive state updates μόνο από παρελθόν/current price.

## frama

Fractal Adaptive Moving Average.

- Outputs: `frama_{window}` και optional diagnostics `{col}_alpha`, `{col}_fractal_dimension`.
- Χρησιμότητα: trend filter που αυξομειώνει smoothing ανάλογα με roughness/choppiness.
- Θεωρία: fractal dimension του recent high-low structure ελέγχει το adaptive alpha.
- Causality: χρησιμοποιεί trailing high/low/price window.

## center_of_gravity

Ehlers Center of Gravity oscillator.

- Output: `center_of_gravity_{window}` ή `output_col`.
- Χρησιμότητα: short-term cycle/turning-point oscillator.
- Θεωρία: weighted center της πρόσφατης price window, με μεγαλύτερο βάρος στα πιο πρόσφατα observations.
- Causality: trailing fixed window.

## even_better_sinewave

Ehlers Even Better Sinewave.

- Output: `even_better_sinewave` ή `output_col`.
- Χρησιμότητα: bounded cycle oscillator για cycle regimes.
- Θεωρία: high-pass filtering, SuperSmoother και power normalization παράγουν oscillator clipped σε `[-1, 1]`.
- Causality: filters και power window είναι trailing.

## autocorrelation_periodogram

Causal autocorrelation periodogram dominant-period estimate.

- Outputs: `autocorrelation_periodogram_{min}_{max}` και optional `{col}_power`.
- Τύπος: rolling autocorrelations across candidate periods, positive correlations squared as power weights.
- Χρησιμότητα: dominant-cycle period estimate ανεξάρτητο από MESA path.
- Θεωρία: periodic structure εμφανίζεται ως high autocorrelation σε συγκεκριμένα lags.
- Causality: κάθε estimate χρησιμοποιεί μόνο trailing window.

## homodyne_discriminator

MESA homodyne discriminator period estimate.

- Output: `homodyne_discriminator` ή `output_col`.
- Χρησιμότητα: cycle-length estimate για adaptive filters και regime checks.
- Θεωρία: χρησιμοποιεί MESA in-phase/quadrature dynamics για period estimation.
- Causality: recursive components μέχρι το current bar.

## parkinson_volatility

High-low range volatility estimator.

- Output: `parkinson_vol_{window}` ή `output_col`.
- Τύπος: rolling Parkinson variance από `log(high/low)`.
- Χρησιμότητα: volatility estimate που χρησιμοποιεί intrabar range αντί close-to-close returns.
- Θεωρία: under Brownian assumptions, high-low range είναι πιο πληροφοριακό από close-to-close move.
- Causality: trailing high/low window.

## garman_klass_volatility

OHLC volatility estimator.

- Output: `garman_klass_vol_{window}` ή `output_col`.
- Τύπος: rolling estimator από open-high-low-close log ranges.
- Χρησιμότητα: intrabar volatility context όταν υπάρχουν reliable OHLC bars.
- Θεωρία: συνδυάζει range και open-close move για χαμηλότερη variance estimate από close-only volatility.
- Causality: trailing OHLC window.

## yang_zhang_volatility

Yang-Zhang OHLC volatility estimator.

- Outputs: `yang_zhang_vol_{window}` και optional rolling mean, ratio, rising flag, high-vol regime flag.
- Τύπος: combines overnight/open-close volatility, close-to-open move και Rogers-Satchell range component.
- Χρησιμότητα: πιο complete OHLC volatility estimate, ειδικά όταν open gaps έχουν σημασία.
- Θεωρία: διαχωρίζει overnight και intraday volatility components.
- Causality: rolling windows μέχρι το current bar.

## hurst_exponent

Rolling Hurst exponent estimate.

- Output: `hurst_{window}` ή `output_col`.
- Χρησιμότητα: persistence/mean-reversion regime context.
- Θεωρία: H > 0.5 δείχνει persistence, H < 0.5 anti-persistence, με caveats για noisy finite windows.
- Causality: trailing price window.

## fractal_dimension

Rolling Katz fractal dimension.

- Output: `fractal_dimension_{window}` ή `output_col`.
- Χρησιμότητα: choppiness/roughness measure για trend-vs-noise regimes.
- Θεωρία: πιο high-dimensional path σημαίνει πιο rough/choppy movement.
- Causality: trailing price window.

## zscore_momentum

Price z-score momentum.

- Output: `zscore_momentum_{window}` ή `output_col`.
- Τύπος: `(price - rolling_mean) / rolling_std`.
- Χρησιμότητα: standardized distance from recent equilibrium.
- Θεωρία: mean-reversion ή trend continuation μπορούν να εξαρτώνται από standardized displacement.
- Causality: rolling statistics είναι trailing.

## rolling_r2_trend_quality

Rolling linear-regression trend quality.

- Outputs: R2 column και optional slope, intercept, rising flag, trend-quality flag.
- Τύπος: rolling regression of price on time index και `R^2` ως quality/linearity measure.
- Χρησιμότητα: ξεχωρίζει directional, clean trends από noisy drift.
- Θεωρία: υψηλό R2 σημαίνει ότι η πρόσφατη τιμή εξηγείται καλά από linear trend.
- Causality: regression window είναι trailing.

## trend_slope_volatility

Trend slope scaled by volatility.

- Outputs: `trend_slope_{window}`, volatility-used, slope/volatility ratio και optional positive/rising/strong flags.
- Τύπος: rolling price slope divided by configured volatility column ή internally resolved trailing volatility.
- Χρησιμότητα: trend strength normalized by current risk/noise.
- Θεωρία: slope χωρίς volatility scaling δεν συγκρίνεται εύκολα μεταξύ assets/regimes.
- Causality: slope και volatility είναι trailing.

## volatility_of_volatility

Rolling volatility-of-volatility.

- Outputs: `volatility_of_volatility_{volatility_col}_{window}` και optional mean, ratio, rising/high flags.
- Τύπος: rolling standard deviation/variation of an existing volatility column.
- Χρησιμότητα: regime instability, risk model confidence και volatility expansion diagnostics.
- Θεωρία: όταν η volatility itself είναι volatile, fixed thresholds/position sizing γίνονται λιγότερο stable.
- Causality: απαιτεί υπάρχουσα volatility column και trailing window.

## volatility_regime

Volatility regime score.

- Output: `volatility_regime` ή `output_col`.
- Τύπος: είτε configured `vol_col` divided by trailing baseline είτε returns-derived rolling regime score.
- Χρησιμότητα: high/low volatility filters και stratification.
- Θεωρία: edge και risk distributions αλλάζουν materially ανά volatility regime.
- Causality: trailing baseline/returns.

## hmm_regime

Hidden Markov Model regime labels.

- Output: configured regime/state column.
- Χρησιμότητα: discrete latent regime context από returns/feature distributions.
- Θεωρία: HMM υποθέτει latent states με διαφορετικές emission distributions.
- Causality: πρέπει να χρησιμοποιείται με προσοχή: fitting πρέπει να γίνεται μόνο σε training/history και όχι σε full sample πριν split.
- Leakage note: οποιοδήποτε offline fit σε όλο το dataset πριν train/test split είναι leakage.

## hilbert_transform

Causal rolling Hilbert endpoint features.

- Outputs: `hilbert_amplitude_{window}`, `hilbert_phase_{window}`, `hilbert_instantaneous_frequency_{window}` ή configured names.
- Derived columns όπως dominant cycle reciprocal, cycle-ok flag και amplitude-rising flag δεν παράγονται πλέον από το raw builder. Χρησιμοποίησε `reciprocal`, `between_flag`, `rising_flag`.
- Χρησιμότητα: amplitude/phase/frequency context για cycle-aware strategies.
- Θεωρία: analytic signal decomposition gives instantaneous phase/amplitude estimates.
- Causality: εφαρμόζει Hilbert σε trailing window και κρατά μόνο endpoint values.

## roofing_filter

Ehlers Roofing Filter.

- Output: `roofing_filter_{high_pass}_{low_pass}` ή `output_col`.
- Derived slope/positive/cross flags δεν παράγονται από το raw builder. Χρησιμοποίησε helpers.
- Χρησιμότητα: αφαιρεί slow trend και high-frequency noise, κρατώντας tradeable cycle band.
- Θεωρία: high-pass plus SuperSmoother-like low-pass band-pass filtering.
- Causality: recursive/trailing filter.

## schaff_trend_cycle

Schaff Trend Cycle oscillator.

- Outputs: `stc`, `stc_signal` ή configured names.
- Τύπος: EMA fast/slow oscillator, stochastic normalization, causal EMA smoothing passes.
- Derived cross/rising/falling flags πρέπει να δηλώνονται με helpers.
- Χρησιμότητα: trend/momentum oscillator με faster turning behavior από MACD.
- Θεωρία: combines MACD trend information with stochastic cycle normalization.
- Causality: trailing EMAs και rolling stochastic windows.

## supersmoother

Ehlers SuperSmoother low-pass filter.

- Output: `supersmoother_{period}` ή `output_col`.
- Χρησιμότητα: low-lag smoothing για noisy price/indicator inputs.
- Θεωρία: two-pole recursive filter που μειώνει high-frequency noise.
- Causality: recursive filter με current/past values.

## shannon_entropy

Rolling Shannon entropy.

- Output: entropy column, default tied to configured `window`/bins.
- Χρησιμότητα: uncertainty/disorder context για returns ή price changes.
- Θεωρία: higher entropy σημαίνει πιο dispersed/unpredictable recent distribution.
- Causality: trailing window.

## permutation_entropy

Rolling permutation entropy.

- Output: permutation entropy column, default tied to `window`/order/delay.
- Χρησιμότητα: ordinal-pattern complexity measure robust to monotone transforms.
- Θεωρία: μετρά diversity των rank-order patterns μέσα σε trailing window.
- Causality: trailing ordinal patterns.

## vpin

Volume-synchronized probability of informed trading proxy.

- Output: `vpin_{window}` ή `output_col`.
- Χρησιμότητα: order-flow toxicity/liquidity-stress proxy όταν υπάρχουν volume/buy-sell proxy inputs.
- Θεωρία: persistent imbalance in volume buckets can indicate informed flow or adverse selection.
- Causality: trailing imbalance aggregation.

## order_flow_imbalance

Order-flow imbalance from buy/sell volume or quote sizes.

- Output: `order_flow_imbalance` / `order_flow_imbalance_{window}` ή `output_col`.
- Τύπος: buy-sell imbalance, optionally normalized by total flow/size.
- Χρησιμότητα: microstructure pressure feature για short-horizon models.
- Θεωρία: directional pressure appears when aggressive buy/sell flow or bid/ask depth is imbalanced.
- Causality: requires columns available at timestamp; rolling aggregation is trailing.

## roc_long_only_conditions

Manual long-only condition builder. Είναι διαθέσιμο και ως feature step και ως signal kind.

- Inputs: `roc_*`, `regime_vol_ratio_z_*`, `close_z`, `close_open_ratio`, `mtf_1h_trend_score`, `mtf_4h_trend_score`, `is_weekend`, optional macro condition.
- Outputs: condition flags (`cond_*`), score (`manual_conviction_score`), long candidate, short signal 0, combined signal, volatility-adjusted exposure.
- Λογική: μετρά πόσες συνθήκες περνάνε και ανοίγει long όταν το score >= `min_score_required`, με weekend/macro gates και optional required conditions.
- Vol adjustment: `1 / (1 + vol_adjustment_strength * max(regime_vol_z, 0))`, clipped σε `[min_exposure, max_exposure]`.
- Χρησιμότητα: interpretable manual candidate generator για EDA, meta-labeling και model filtering.
- Θεωρία: συνδυάζει momentum, regime, multi-timeframe confirmation, z-score location και candle confirmation σε rule-based score.
- Causality: δεν κάνει fit/predict. Χρησιμοποιεί current-bar closed features και το backtest πρέπει να εκτελεί στο επόμενο bar/open.

## Compatibility signal-like feature steps

Τα παρακάτω steps είναι resolvable από configs μέσω `FEATURE_COMPATIBILITY_REGISTRY` ή/και από το dashboard compatibility layer, αλλά δεν ανήκουν στο canonical `FEATURE_REGISTRY` των raw feature builders. Να τα χρησιμοποιείς ως candidate/signal builders, όχι ως pure transforms.

| Step | Outputs | Χρήση |
|---|---|---|
| `ehlers_semiscalp_long` | `signal_side`, `signal_candidate` και setup flags | Long-only Ehlers semiscalp candidate. |
| `ehlers_decycler_continuation` | `signal_side`, `signal_candidate` | Long-only decycler continuation candidate. |
| `ema_stoch_rsi_pullback` | side/candidate columns και EMA/StochRSI diagnostics | Long/short EMA + StochRSI pullback candidate. |
| `indicator_model_adaptive_pullback` | `candidate_long`, `candidate_short`, direction/signal/candidate/score columns | Indicator-only adaptive pullback candidate before model filtering. |
| `vwap_rms_ema_cross_long` | regime/cross/PPO/MFI setup columns, `signal_side`, `signal_candidate` | VWAP/RMS/EMA cross candidate with optional PPO/MFI confirmation. |

Leakage note: επειδή αυτά γράφουν signal/candidate columns, πρέπει να επιβεβαιώνεται ότι το backtest/model χρησιμοποιεί next-bar execution ή άλλο explicit execution lag.
