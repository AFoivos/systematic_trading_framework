# Feature Normalization Playbook

Τελευταία ενημέρωση: 2026-06-27

Αυτό το αρχείο είναι πρακτικό research reference για όλα τα canonical feature
steps του `src/features/registry.py` και για τους διαθέσιμους transform /
normalization helpers του `src/features/helpers/registry.py`.

Στόχος: να μη δίνουμε στο μοντέλο raw τιμές που δεν συγκρίνονται μεταξύ assets
ή regimes, αλλά πληροφορία σε οικονομικά σταθερές μονάδες: returns, ATR units,
percent ranks, rolling z-scores, robust z-scores, ratios, range positions,
volatility-scaled values και causal lags.

## Βασική αρχή

Το target μπορεί να χρειάζεται raw OHLC prices. Για παράδειγμα το
`directional_triple_barrier` πρέπει να ξέρει αν το `high` ή το `low` χτύπησε
profit/stop levels. Αυτό δεν σημαίνει ότι το model πρέπει να δει raw
`open/high/low/close`.

Η σωστή διάκριση είναι:

```text
OHLC + ATR + side signal
  -> target builder / backtest realism

normalized feature state at t
  -> model input
```

Για meta-labeling, το πιο υγιές pattern είναι:

```text
label = did the candidate trade reach profit before stop?
features = scale-free state when the candidate appeared
```

## Προτεραιότητα normalizations

### Priority 1: πρέπει σχεδόν πάντα να υπάρχουν

1. `returns`: μετατρέπει price levels σε απλές ή log αποδόσεις.
2. `atr_scaled_distance`: μετατρέπει price distances σε R/ATR units.
3. `volatility`: παράγει `atr / close` και ATR percentile.
4. `volatility_scaled_return`: return ανά μονάδα volatility.
5. `range_position`: θέση close μέσα σε rolling high/low range.
6. `lag`: κάνει explicit την ιστορική πληροφορία και μειώνει ambiguity για
   decision timing.
7. `rolling_zscore` με shifted stats: κάνει level-dependent columns συγκρίσιμα
   με την πρόσφατη ιστορία τους.
8. `rolling_percent_rank` με shifted window: robust regime position σε `[0, 1]`.

### Priority 2: πολύ χρήσιμα για noisy intraday data

1. `robust_zscore`: median/MAD normalization για fat tails.
2. `rolling_clip`: causal winsorization για extreme spikes.
3. `volume_relative`: relative volume και optional volume z-score.
4. `rms`: energy/oscillation strength σε rolling window.
5. `rolling_linear_regression`: slope και R2 σε trailing windows.
6. `rolling_beta_residual`: idiosyncratic return vs benchmark.
7. `difference` / `slope`: momentum of indicator, όχι μόνο indicator level.

### Priority 3: regime flags και model interaction helpers

1. `threshold_flag`: μετρά αν ένα normalized feature πέρασε meaningful level.
2. `between_flag`: κρατά usable range, π.χ. cycle period within bounds.
3. `crossing_flag`: event detection σε oscillators/filters.
4. `rising_flag`: direction of feature change.
5. `ratio`: βασικό εργαλείο για price/volatility/indicator scaling.
6. `reciprocal`: χρήσιμο για inverse volatility / inverse range features.

## Helper catalog

| Helper | Τι υπολογίζει | Πληροφορία | Γιατί είναι σημαντικό | Leakage note |
|---|---|---|---|---|
| `returns` | `close_t / close_{t-w} - 1` και optional log return | cumulative move | Κάνει prices συγκρίσιμα μεταξύ assets | safe, trailing |
| `atr_distances` | distances από ATR-derived levels | απόσταση σε absolute/ATR context | Καλό για stop/profit geometry | safe αν ATR trailing |
| `atr_scaled_distance` | `(source - reference) / ATR` | distance σε risk units | Κεντρικό για multi-asset models | safe αν columns point-in-time |
| `range_position` | `(value - rolling_low) / (rolling_high - rolling_low)` | θέση στο πρόσφατο range | Μετρά overextension/mean reversion | rolling window trailing |
| `realized_vol_percentile` | percentile realized vol | volatility regime | Καλύτερο από raw vol level | window πρέπει να είναι trailing |
| `robust_zscore` | `(x - rolling median) / MAD` | robust standardized surprise | Αντέχει spikes και fat tails | default shifted stats |
| `rolling_beta_residual` | asset return minus rolling alpha/beta * benchmark | idiosyncratic move | Διαχωρίζει market beta από alpha | default shifted stats |
| `rolling_percent_rank` | rank current value vs trailing history | regime position `[0,1]` | Non-parametric, robust σε outliers | default excludes current from history |
| `rolling_zscores` | rolling mean/std z-score για πολλά columns | standardized deviation | Γρήγορο normalization πολλών features | default shifted stats |
| `volatility` | `ATR / close`, ATR percentile | relative volatility | Κάνει ATR comparable across prices | percentile currently rolling; prefer shifted alternative for strict PIT if needed |
| `volatility_scaled_return` | `return / volatility` | risk-adjusted return | Sharpe-like local signal | safe αν vol trailing |
| `volume_relative` | `volume / rolling_mean(volume)` και optional z-score | abnormal participation | Volume scale differs across assets/sessions | default shifted stats |
| `difference` | `x_t - x_{t-k}` | change/slope proxy | Πιο χρήσιμο από raw level για filters | safe |
| `lag` | `x_{t-k}` | explicit memory | Αποφεύγει ambiguity σε current-bar features | safe |
| `ratio` | numerator / denominator | scale-free σχέση | Core normalization primitive | safe if inputs safe |
| `reciprocal` | `1 / x` | inverse intensity | Χρήσιμο για inverse vol / inverse range | handle zero/eps |
| `rolling_clip` | clip με trailing quantiles | outlier control | Σταθεροποιεί tree splits και scalers | default shifted bounds |
| `rolling_linear_regression` | rolling slope/intercept/R2 | trend direction + quality | Διαχωρίζει trend από noise | trailing window |
| `rolling_mean` | trailing mean | local baseline | Για ratios/deviations | optional shift |
| `rolling_std` | trailing std | local dispersion | Για volatility/z-score | optional shift |
| `rolling_sum` | trailing sum | cumulative flow/return | Momentum over horizon | optional shift |
| `rolling_zscore` | `(x - shifted mean) / shifted std` | surprise vs history | Default normalization για unbounded columns | default shifted |
| `rms` | root mean square | signal energy | Καλή ένταση oscillators/returns | trailing |
| `slope` | `x_t - x_{t-window}` ή fitted slope depending config | direction of change | Μετρά acceleration/turning | safe |
| `threshold_flag` | binary comparison | regime/event gate | Κάνει interpretable filters | safe |
| `rising_flag` | `x_t > x_{t-k}` | monotonic direction | Απλό trend-of-feature | safe |
| `between_flag` | value in interval | valid/neutral zone | Χρήσιμο για cycles/oscillators | safe |
| `crossing_flag` | threshold crossing | transition event | Καλύτερο από static oscillator level | safe |

## Feature priority groups

### P0: core scale-free state για σχεδόν όλα τα models

- `returns`
- `atr`
- `volatility`
- `vol_normalized_momentum`
- `return_momentum`
- `range_position`
- `regime_context`
- `session_context`
- `rolling_r2_trend_quality`
- `trend_slope_volatility`
- `volatility_regime`

### P1: ισχυρά price/action/trend/cycle features, θέλουν normalization

- `trend`
- `bollinger`
- `roc`
- `adx`
- `vwap`
- `support_resistance`
- `support_resistance_v2`
- `multi_timeframe`
- `opening_range_breakout`
- `swing_extrema_context`
- `shock_context`
- `mama`
- `fama`
- `instantaneous_trendline`
- `supersmoother`
- `roofing_filter`
- `decycler`
- `decycler_oscillator`
- `hilbert_transform`

### P2: oscillators/entropy/regime diagnostics

- `macd`
- `ppo`
- `rsi`
- `stochastic`
- `stochastic_rsi`
- `mfi`
- `laguerre_rsi`
- `fisher_transform`
- `inverse_fisher_transform`
- `sinewave_indicator`
- `cyber_cycle`
- `center_of_gravity`
- `even_better_sinewave`
- `autocorrelation_periodogram`
- `dominant_cycle_period`
- `dominant_cycle_phase`
- `homodyne_discriminator`
- `hurst_exponent`
- `fractal_dimension`
- `shannon_entropy`
- `permutation_entropy`

### P3: specialized/exogenous/flow features

- `volume_features`
- `vpin`
- `order_flow_imbalance`
- `macro_context`
- `hmm_regime`
- `indicator_pullback`
- `ehlers_ml_long_candidate`
- `price_momentum`
- `zscore_momentum`
- `volatility_of_volatility`
- `parkinson_volatility`
- `garman_klass_volatility`
- `yang_zhang_volatility`

## Πλήρης feature-by-feature λίστα

Ο πίνακας δίνει recommended normalizations με σειρά σημαντικότητας. Όταν λέει
`/ ATR`, εννοεί helper όπως `ratio` ή `atr_scaled_distance` ανάλογα με το αν
το feature είναι distance από reference ή ήδη signed value.

| Priority | Feature | Τι υπολογίζει | Τι πληροφορία δίνει | Γιατί είναι σημαντικό | Normalizations / helpers που έχουν νόημα | Καλοί συνδυασμοί |
|---|---|---|---|---|---|---|
| P0 | `returns` | Απλές/log αποδόσεις από close | Τοπική κίνηση τιμής | Οι τιμές δεν είναι stationary, οι returns είναι πιο συγκρίσιμες | `lag`, `rolling_sum`, `volatility_scaled_return`, `rolling_zscore`, `rolling_percent_rank`, `rolling_clip` | `volatility`, `return_momentum`, `regime_context`, `shock_context` |
| P0 | `volatility` | Rolling/EWMA std returns | Realized risk | Volatility clustering καθορίζει edge και sizing | `rolling_percent_rank`, `robust_zscore`, `ratio short/long`, `volatility_of_volatility` | `vol_normalized_momentum`, `regime_context`, `risk sizing` |
| P1 | `trend` | SMA/EMA levels | Trend anchor / mean baseline | Χρήσιμο μόνο ως relative distance, όχι raw MA level | `price/MA - 1`, `(price-MA)/ATR`, `rolling_zscore`, `slope`, `crossing_flag` | `adx`, `regime_context`, `support_resistance` |
| P1 | `trend_regime` | Discrete SMA relationship states | Directional regime | Απλός interpretable filter | `threshold_flag` usually unnecessary, use as categorical/binary | `trend`, `adx`, `multi_timeframe` |
| P0 | `lags` | Delayed columns | Ιστορική μνήμη | Απαραίτητο για tabular models χωρίς sequence state | Use after normalization, not before raw price use | returns, oscillators, normalized distances |
| P1 | `bollinger` | Rolling mean/bands/width/%B | Mean reversion + vol expansion | `%B` και width είναι ήδη semi-normalized | `%B` raw ok, `bb_width/close`, `bb_width/ATR`, `rolling_percent_rank(width)` | `rsi`, `stochastic`, `volatility_regime` |
| P2 | `macd` | EMA fast - EMA slow, signal, hist | Momentum acceleration | Raw MACD price units δεν συγκρίνονται | `macd/close`, `macd/ATR`, `hist/ATR`, `rolling_zscore`, `crossing_flag` | `ppo`, `adx`, `trend` |
| P1 | `ppo` | Percentage MACD | Scale-free MACD | Καλύτερο από MACD για multi-asset | `rolling_zscore`, `rolling_percent_rank`, `slope`, `crossing_flag` | `macd`, `trend`, `regime_context` |
| P1 | `roc` | Price rate of change over windows | Direct momentum | Cumulative return over lookback | already return-like, add `volatility_scaled_return`, `rolling_zscore`, `lag`, `threshold_flag` | `return_momentum`, `multi_timeframe`, `adx` |
| P0 | `atr` | Average True Range | Absolute range volatility | Core risk unit για stops/targets | `atr/close`, `atr_percent_rank`, `atr_zscore`, `ATR slope`, `ATR short/long ratio` | `directional_triple_barrier`, `atr_scaled_distance`, candle geometry |
| P1 | `adx` | +DI, -DI, ADX | Trend strength + directional pressure | Φιλτράρει chop vs directional regimes | ADX bounded 0-100, use raw; `DI_diff = (+DI - -DI)/100`, `rolling_percent_rank(ADX)` | `trend`, `roc`, `multi_timeframe` |
| P3 | `volume_features` | Volume z-score, volume/ATR | Participation/activity | Volume regimes επηρεάζουν breakout/reversion | `volume_relative`, `robust_zscore`, `rolling_percent_rank`, `volume/rolling_mean` | `vwap`, `mfi`, `vpin`, `opening_range_breakout` |
| P1 | `vwap` | Rolling volume-weighted price | Liquidity-weighted fair value | Raw VWAP είναι price level, χρήσιμο ως anchor | `(close-vwap)/ATR`, `close/vwap-1`, `rolling_zscore(distance)`, `crossing_flag` | `volume_relative`, `trend`, `opening_range_breakout` |
| P2 | `mfi` | RSI-like oscillator with volume | Price-volume pressure | Βοηθά exhaustion/participation context | bounded 0-100; use `/100`, `between_flag`, `crossing_flag`, `rolling_percent_rank` | `rsi`, `volume_relative`, `bollinger` |
| P2 | `rsi` | Relative Strength Index | Overbought/oversold/momentum | Bounded oscillator, good for regimes | `/100`, `rsi-50`, `crossing_flag(50)`, `between_flag`, `rolling_percent_rank` | `bollinger`, `stochastic`, `trend` |
| P2 | `stochastic` | Close position in recent high/low | Range location | Captures close pressure within window | already 0-100; use `/100`, `%K-%D`, `crossing_flag`, `between_flag` | `rsi`, `range_position`, `support_resistance` |
| P2 | `stochastic_rsi` | Stochastic transform of RSI | RSI range location | More sensitive oscillator | bounded; `/100`, crossings, lag, slope | `rsi`, `fisher_transform`, `mean reversion` |
| P1 | `price_momentum` | Price cumulative move | Momentum/reversal | Equivalent to return over horizon | prefer `return_momentum`; add `volatility_scaled_return`, `rolling_zscore`, `lag` | `roc`, `trend`, `volatility` |
| P0 | `return_momentum` | Rolling sum returns | Drift over horizon | Scale-free momentum | `volatility_scaled_return`, `rolling_zscore`, `rolling_percent_rank`, `lag` | `vol_normalized_momentum`, `regime_context` |
| P0 | `vol_normalized_momentum` | Momentum divided by volatility | Risk-adjusted momentum | Comparable across regimes/assets | `rolling_zscore`, `rolling_percent_rank`, `threshold_flag`, `lag` | `adx`, `trend_slope_volatility`, `triple_barrier label` |
| P0 | `session_context` | Hour/day/session cyclic flags | Intraday seasonality | Edges vary by liquidity/news windows | usually raw/binary ok; interactions with vol/session | `opening_range_breakout`, `volume_relative`, `shock_context` |
| P0 | `regime_context` | Vol ratio, abs-return z, trend ratio/state | Market regime | Strategies are regime-dependent | already normalized-ish; add lags, flags, percent ranks | all strategies, especially meta-labeling |
| P1 | `shock_context` | Large return/ATR shock and active window | Shock/reversion/continuation setup | Event state after abnormal moves | `shock_strength` z/percentile, lag, active flags, side interactions | `rsi`, `bollinger`, `support_resistance` |
| P1 | `support_resistance` | Rolling min/max levels | Distance to recent extremes | Breakout/retest/mean-reversion context | `(close-support)/ATR`, `(resistance-close)/ATR`, `range_position`, flags near level | `trend`, `volume_relative`, `OR breakout` |
| P1 | `support_resistance_v2` | Confirmed pivots, ages, touch counts, breakouts | Market structure | More realistic S/R because pivots confirmed | ATR distances, age log/clip, touch count clip, breakout flags | `swing_extrema_context`, `vwap`, `adx` |
| P3 | `macro_context` | Lagged macro/exogenous transforms | External regime info | Useful only if availability is modeled | z-score, pct change, explicit availability lag, rolling beta residual | `regime_context`, `volatility`, asset returns |
| P1 | `multi_timeframe` | HTF returns/trend/vol/ATR/ADX aligned to base TF | Higher timeframe context | Reduces false signals against larger trend | HTF returns already scale-free; ATR/close, trend scores raw ok, lags | `trend`, `roc`, `adx`, signal filters |
| P1 | `opening_range_breakout` | Session range, breakout candidates/strength | Intraday breakout structure | Opening ranges are liquidity boundaries | range/ATR, breakout distance/ATR, volume relative, flags | `session_context`, `vwap`, `volume_relative` |
| P1 | `swing_extrema_context` | Confirmed swing highs/lows and distances | Structural pivots | Captures market structure without raw price levels | confirmed distances/ATR, age, near flags, range position | `support_resistance_v2`, `trend`, `shock_context` |
| P2 | `indicator_pullback` | Pullback diagnostics from indicators | Candidate setup state | Useful as interpretable candidate generator | Normalize all distances by ATR/close; use flags/scores raw | `adx`, `trend`, `rsi`, meta-labeling |
| P2 | `ehlers_ml_long_candidate` | Ehlers-derived long candidate | Candidate/event feature | Good for meta-label candidate side | Candidate flags raw; normalize supporting Ehlers columns | `roofing_filter`, `decycler`, `laguerre_rsi` |
| P1 | `mama` | MESA adaptive moving average | Adaptive trend anchor | More responsive than fixed MA | `(close-mama)/ATR`, `mama/fama spread / ATR`, slope, crossing | `fama`, `trend`, `dominant_cycle_period` |
| P1 | `fama` | Following adaptive moving average | Slower adaptive trend anchor | Confirms MAMA trend | `(mama-fama)/ATR`, slope, crossing flag | `mama`, `adx`, `cycle period` |
| P2 | `dominant_cycle_period` | Estimated cycle length | Market rhythm/horizon | Helps adapt windows/filters | `rolling_zscore`, `between_flag`, `lag`, `rolling_percent_rank` | Ehlers filters, `autocorrelation_periodogram` |
| P2 | `dominant_cycle_phase` | Cycle phase angle | Position in cycle | Useful for timing/reversal | sin/cos representation preferred if available; zscore not ideal | `sinewave_indicator`, `hilbert_transform` |
| P1 | `instantaneous_trendline` | Ehlers trendline | Smooth trend estimate | Trend anchor with less lag | `(close-itl)/ATR`, slope, crossing flag | `roofing_filter`, `decycler`, `adx` |
| P2 | `fisher_transform` | Fisher-normalized oscillator | Turning-point sensitivity | Sharpens bounded/range signals | `rolling_zscore`, clip, crossing zero, lag/slope | `rsi`, `stochastic`, `roofing_filter` |
| P2 | `inverse_fisher_transform` | Maps input to bounded oscillator | Bounded nonlinear signal | Stabilizes extremes | already bounded; use crossing, threshold, lag | `fisher_transform`, `rsi`, `stochastic_rsi` |
| P2 | `sinewave_indicator` | Ehlers sine/lead sine phase signals | Cycle turning context | Detects phase transitions | crossing sine vs lead, phase flags, percent rank of amplitude if present | `dominant_cycle_phase`, `roofing_filter` |
| P2 | `cyber_cycle` | Ehlers high-pass/cycle oscillator | Cycle component | Removes trend to isolate swings | `/ATR` if price-like, rolling zscore, RMS, crossings | `roofing_filter`, `fisher_transform` |
| P1 | `decycler` | Ehlers decycler low-pass component | Smooth trend without cycle | Raw level is price-scale | `decycler/close`, `(close-decycler)/ATR`, slope/ATR, zscore distance | `decycler_oscillator`, `supersmoother` |
| P1 | `decycler_oscillator` | Fast/slow decycler spread | Trend/cycle pressure | Usually signed oscillator | `/ATR`, `/close`, rolling zscore, crossing zero, RMS | `decycler`, `roofing_filter`, `laguerre_rsi` |
| P2 | `laguerre_rsi` | Laguerre-smoothed RSI | Smooth momentum oscillator | Less noisy overbought/oversold state | bounded raw ok; `/100` if percent, crossing, slope, percent rank | `decycler_oscillator`, `fisher_transform` |
| P1 | `frama` | Fractal adaptive moving average | Adaptive trend level | Adjusts smoothing to fractality | `(close-frama)/ATR`, slope/ATR, crossing | `fractal_dimension`, `trend`, `adx` |
| P2 | `center_of_gravity` | Ehlers COG oscillator | Cycle turning/phase | Timing-oriented oscillator | rolling zscore, crossing zero, slope, lag | `roofing_filter`, `sinewave_indicator` |
| P2 | `even_better_sinewave` | Ehlers sinewave variant | Cycle phase/turning | Improved cycle extraction | crossings, bounded scaling, RMS/amplitude normalization | `dominant_cycle_phase`, `roofing_filter` |
| P2 | `autocorrelation_periodogram` | Dominant period/power via autocorrelation | Cycle strength and period | Tells whether cycle estimate is meaningful | period percent rank/between flag, power zscore/percent rank | `dominant_cycle_period`, Ehlers filters |
| P2 | `homodyne_discriminator` | Ehlers phase/period discriminator | Instantaneous cycle period | Adaptive cycle horizon | period bounds, percent rank, lag, slope | `dominant_cycle_period`, `sinewave_indicator` |
| P0 | `parkinson_volatility` | High-low volatility estimator | Intrabar realized range risk | Uses OHLC range, no close-to-close only | `/close` if absolute, percent rank, zscore, ratio vs ATR | `garman_klass_volatility`, `yang_zhang_volatility` |
| P0 | `garman_klass_volatility` | OHLC volatility estimator | Intraday volatility | Uses open/high/low/close more efficiently | percent rank, zscore, ratio vs ATR/realized vol | `parkinson_volatility`, `yang_zhang_volatility` |
| P0 | `yang_zhang_volatility` | Open-close + overnight + range volatility | More complete volatility estimate | Useful where gaps/session opens matter | percent rank, zscore, ratio vs ATR | `session_context`, `regime_context` |
| P2 | `hurst_exponent` | Persistence/mean-reversion statistic | Trendiness vs anti-persistence | Helps choose momentum vs reversal regimes | raw bounded-ish; percent rank, flags above/below 0.5 | `fractal_dimension`, `trend_r2` |
| P2 | `fractal_dimension` | Price path roughness | Choppiness/complexity | Separates smooth trends from noisy paths | percent rank, flags, zscore | `frama`, `hurst_exponent`, `adx` |
| P2 | `zscore_momentum` | Z-scored momentum | Standardized momentum surprise | Useful if raw momentum distribution drifts | already zscored; clip, lag, threshold | `return_momentum`, `volatility` |
| P0 | `rolling_r2_trend_quality` | Rolling regression R2 on price | Trend quality/noise ratio | High slope alone is not enough; quality matters | R2 raw `[0,1]`, slope/ATR or slope/price, threshold flags | `trend_slope_volatility`, `adx` |
| P0 | `trend_slope_volatility` | Price slope scaled by volatility | Trend per unit risk | Cross-asset trend strength | already normalized if vol col relative; add zscore/flags | `rolling_r2`, `volatility_regime` |
| P1 | `volatility_of_volatility` | Rolling std/change of volatility | Stability of risk regime | Stops/edges degrade in unstable vol | percent rank, ratio to long mean, zscore, rising flag | `regime_context`, `shock_context` |
| P0 | `volatility_regime` | Volatility state flags/ratios | High/low vol regime | Controls strategy applicability | raw states ok; ratios zscore/percent rank | `return_momentum`, `triple_barrier R` |
| P3 | `hmm_regime` | Hidden Markov regime labels/probs | Learned latent regimes | Powerful but needs strict fit/split discipline | probabilities raw, labels categorical, avoid refit leakage | model stacking, regime-stratified analysis |
| P1 | `hilbert_transform` | Amplitude/phase/frequency | Cycle amplitude and timing | Useful for Ehlers-style cycle strategies | amplitude/ATR, amplitude zscore, phase sin/cos, frequency zscore | `roofing_filter`, `dominant_cycle_phase` |
| P1 | `roofing_filter` | Band-pass filtered price | Detrended cycle component | Removes trend and high-frequency noise | `/ATR`, rolling zscore, slope, RMS, crossings | `fisher_transform`, `hilbert_transform` |
| P2 | `schaff_trend_cycle` | MACD + stochastic cycle oscillator | Trend-cycle oscillator | Fast momentum timing | bounded; `/100`, crossing, slope, percent rank | `ppo`, `trend`, `adx` |
| P1 | `supersmoother` | Ehlers low-lag smoothing | Smooth price/trend level | Good anchor for slope/distance | `(close-ss)/ATR`, `slope/ATR`, `ss/close`, crossing | `decycler`, `roofing_filter` |
| P2 | `shannon_entropy` | Distribution entropy over window | Uncertainty/randomness | High entropy often means noisy edge | percent rank, zscore, flags high/low | `hurst_exponent`, `fractal_dimension` |
| P2 | `permutation_entropy` | Ordinal pattern entropy | Complexity of ordering | Robust nonlinear regime signal | percent rank, zscore, flags | `shannon_entropy`, `volatility_regime` |
| P3 | `vpin` | Volume-synchronized probability of informed trading | Order-flow imbalance proxy | Good for toxic flow/liquidity risk | percent rank, zscore, volume-relative interaction | `volume_relative`, `order_flow_imbalance` |
| P3 | `order_flow_imbalance` | Bid/ask or proxy flow imbalance | Buy/sell pressure | Direct microstructure signal when real columns exist | zscore, percent rank, rolling sum, clip | `vpin`, `volume_relative`, `shock_context` |

## Candle geometry features που αξίζει να προστεθούν ως helpers/combinations

Αν θες το model να μάθει candle patterns χωρίς raw price scale, χρησιμοποίησε
τα παρακάτω ως derived columns:

| Derived feature | Formula | Πληροφορία | Priority |
|---|---|---|---|
| `bar_body_atr` | `(close - open) / atr_14` | signed candle body σε risk units | P0 |
| `bar_range_atr` | `(high - low) / atr_14` | intrabar volatility | P0 |
| `upper_wick_atr` | `(high - max(open, close)) / atr_14` | rejection πάνω | P1 |
| `lower_wick_atr` | `(min(open, close) - low) / atr_14` | rejection κάτω | P1 |
| `close_pos_in_bar` | `(close - low) / (high - low)` | close pressure μέσα στο candle | P0 |
| `gap_open_atr` | `(open - prev_close) / atr_14` | gap/session jump | P1 |
| `body_to_range` | `abs(close-open) / (high-low)` | conviction vs wickiness | P1 |
| `range_percent_rank` | percent rank of `bar_range_atr` | abnormal range | P1 |
| `body_zscore` | robust z-score of `bar_body_atr` | abnormal directional candle | P1 |

Σημαντικό: αυτά πρέπει να χρησιμοποιούνται μόνο αν η απόφαση γίνεται αφού έχει
κλείσει το candle. Αν μπαίνεις `next_open`, είναι causal. Αν μπαίνεις μέσα στο
ίδιο candle, είναι leakage.

## Recommended feature sets για directional triple-barrier meta-labeling

### Minimal, production-first set

```yaml
feature_cols:
  - close_ret
  - lag_close_ret_1
  - lag_close_ret_2
  - atr_over_price_14
  - atr_over_price_z_252
  - return_mom_8_over_vol
  - rolling_r2_96
  - rolling_r2_slope_96_atr
  - trend_slope_vol_ratio_96
  - session_europe_us_overlap
```

Γιατί: λίγα, causal, scale-free, εύκολα να γίνουν audit.

### Ehlers continuation set

```yaml
feature_cols:
  - ehlers_supersmoother_slope_atr
  - ehlers_roofing_atr
  - ehlers_roofing_slope_atr
  - ehlers_hilbert_amplitude_atr
  - ehlers_hilbert_amplitude_z_252
  - ehlers_hilbert_phase_64
  - ehlers_hilbert_frequency_64
  - dominant_cycle_period
  - dominant_cycle_phase
  - ehlers_decycler_over_close
  - decycler_oscillator_30_60_atr
  - laguerre_rsi
  - fisher_transform
  - autocorrelation_periodogram_10_48_power_z
  - rolling_r2_96
  - rolling_r2_slope_96_atr
  - atr_over_price_14
  - atr_over_price_z_252
```

Γιατί: κρατά cycle/trend state, αλλά μετατρέπει price-like Ehlers outputs σε
ATR/close units.

### Breakout set

```yaml
feature_cols:
  - orb_breakout_distance_atr
  - orb_range_atr
  - close_above_vwap_atr
  - volume_relative_96
  - volume_zscore_96
  - adx_14
  - plus_minus_di_diff
  - mtf_1h_trend_score
  - mtf_4h_trend_score
  - atr_percent_rank_252
```

Γιατί: breakouts χρειάζονται range compression/expansion, participation και
higher-timeframe agreement.

### Mean-reversion/shock set

```yaml
feature_cols:
  - shock_ret_z_96
  - shock_atr_multiple_14
  - close_pos_in_bar
  - upper_wick_atr
  - lower_wick_atr
  - rsi_14_centered
  - bb_percent_b_20_2
  - distance_to_support_atr
  - distance_to_resistance_atr
  - volatility_regime_high
```

Γιατί: mean reversion είναι κυρίως abnormal move + exhaustion + nearby
structure.

## Συνδυασμοί ανά οικογένεια feature

### Returns + volatility

Πρώτη επιλογή:

```text
close_ret
lag_close_ret_1, lag_close_ret_2, lag_close_ret_4
rolling_sum(close_ret, 4/8/16)
rolling_sum(close_ret) / rolling_vol
rolling_percent_rank(rolling_vol)
```

Τι δίνει: local drift, recent persistence/reversal και risk-adjusted momentum.

Γιατί είναι σημαντικό: το triple-barrier label σε ATR units ευνοεί features που
περιγράφουν return ανά risk unit.

### Trend + volatility + quality

Πρώτη επιλογή:

```text
(close - EMA) / ATR
EMA_slope / ATR
rolling_regression_slope / ATR
rolling_regression_R2
ADX
```

Τι δίνει: όχι απλά αν υπάρχει trend, αλλά αν το trend είναι καθαρό και αρκετά
ισχυρό σε σχέση με volatility.

### Oscillator + range

Πρώτη επιλογή:

```text
RSI centered at 50
stochastic K/D
close position in rolling range
Bollinger percent_b
Fisher transform crossing zero
```

Τι δίνει: overextension, exhaustion και timing.

Γιατί είναι σημαντικό: oscillator raw values μόνα τους είναι ασταθή. Η θέση στο
range και τα crossings δίνουν καλύτερο event context.

### Ehlers cycle stack

Πρώτη επιλογή:

```text
roofing_filter / ATR
roofing_filter_slope / ATR
decycler / close
decycler_oscillator / ATR
Hilbert amplitude / ATR
cycle phase
dominant cycle period
cycle power z-score
```

Τι δίνει: trend/cycle decomposition, timing και αν το cycle είναι αρκετά ισχυρό
για να αξίζει.

### Structure + levels

Πρώτη επιλογή:

```text
distance_to_support / ATR
distance_to_resistance / ATR
confirmed_pivot_age
touch_count clipped
breakout/retest flags
range_position
```

Τι δίνει: proximity to liquidity/reference levels.

Γιατί είναι σημαντικό: stops/profits στο triple barrier συχνά επηρεάζονται από
το αν η είσοδος είναι κοντά σε structural levels.

### Volume / flow

Πρώτη επιλογή:

```text
volume / rolling_mean(volume)
volume z-score
VPin percent rank
OFI rolling sum z-score
MFI centered
```

Τι δίνει: participation και flow pressure.

Γιατί είναι σημαντικό: πολλά breakouts χωρίς participation αποτυγχάνουν, ενώ
shock moves με extreme flow έχουν διαφορετικό continuation/reversion profile.

### Regime

Πρώτη επιλογή:

```text
short_vol / long_vol
volatility percentile
volatility of volatility percentile
trend state
Hurst/fractal dimension percent rank
entropy percent rank
session flags
```

Τι δίνει: πότε το edge πρέπει να είναι ενεργό.

Γιατί είναι σημαντικό: το ίδιο setup έχει διαφορετικό expected value σε quiet
trend, high-vol breakout, high-entropy chop ή session overlap.

## Scaler μετά τα normalizations

Για XGBoost/LightGBM:

```yaml
preprocessing:
  scaler: none
```

ή για συγκρισιμότητα με άλλα experiments:

```yaml
preprocessing:
  scaler: standard
```

Ο scaler δεν πρέπει να είναι η βασική λύση για raw price scale. Η βασική λύση
είναι τα οικονομικά σωστά feature units. Αν `standard` αλλάζει δραματικά
XGBoost results, έλεγξε outliers, bad columns, leakage ή μη σταθερή κατανομή.

Για logistic/linear/neural models:

```yaml
preprocessing:
  scaler: standard
```

Για fat-tailed normalized features:

```yaml
preprocessing:
  scaler: robust
```

αλλά προτίμησε πρώτα `rolling_clip`, `robust_zscore` και percent ranks.

## YAML snippets

### ATR/close και shifted z-score volatility

```yaml
- step: atr
  params:
    high_col: high
    low_col: low
    close_col: close
    window: 14
    atr_col: atr_14
  transforms:
    ratio:
      items:
        - numerator_col: atr_14
          denominator_col: close
          output_col: atr_over_price_14
    rolling_zscore:
      items:
        - source_col: atr_over_price_14
          window: 252
          shift: 1
          output_col: atr_over_price_z_252
```

### Ehlers price-like output σε ATR units

```yaml
- step: roofing_filter
  params:
    price_col: close
    high_pass_period: 48
    low_pass_period: 10
    output_col: ehlers_roofing_48_10
  transforms:
    difference:
      source_col: ehlers_roofing_48_10
      periods: 1
      output_col: ehlers_roofing_48_10_slope
    ratio:
      items:
        - numerator_col: ehlers_roofing_48_10
          denominator_col: atr_14
          output_col: ehlers_roofing_atr
        - numerator_col: ehlers_roofing_48_10_slope
          denominator_col: atr_14
          output_col: ehlers_roofing_slope_atr
    crossing_flag:
      items:
        - source_col: ehlers_roofing_48_10
          threshold: 0.0
          direction: up
          output_col: ehlers_roofing_cross_up
        - source_col: ehlers_roofing_48_10
          threshold: 0.0
          direction: down
          output_col: ehlers_roofing_cross_down
```

### Return momentum ανά volatility

```yaml
- step: return_momentum
  params:
    returns_col: close_ret
    windows: [4, 8, 16]
  normalizations:
    volatility_scaled_return:
      items:
        - return_col: close_ret_mom_8
          volatility_col: vol_rolling_96
          output_col: close_ret_mom_8_over_vol_96
```

### Candle geometry σε ATR units

Αν δεν υπάρχει dedicated feature builder, αυτά μπορούν να προστεθούν ως
helpers μόνο αφού υπάρχουν οι ενδιάμεσες στήλες. Αν χρειάζεται συχνά, αξίζει
dedicated feature step με tests.

```yaml
# Conceptual recipe:
# body = close - open
# range = high - low
# upper_wick = high - max(open, close)
# lower_wick = min(open, close) - low
# normalize body/range/wicks by atr_14
```

## Anti-leakage checklist

- Μην βάζεις raw `close/open/high/low` στα `feature_cols` για multi-asset model,
  εκτός αν είναι single-asset και υπάρχει συγκεκριμένος λόγος.
- Για rolling z-score/percentile/clip, προτίμησε shifted stats/window.
- Για current candle geometry, εκτέλεση πρέπει να είναι στο επόμενο bar/open.
- Για higher timeframe features, κράτα `shift_to_last_closed: true`.
- Για confirmed pivots/extrema, χρησιμοποίησε confirmed columns, όχι raw
  research labels.
- Για macro/exogenous columns, δήλωσε explicit availability lag.
- Για HMM/learned regimes, το fit πρέπει να είναι μέσα σε train fold, όχι σε
  όλο το dataset.
- Για scalers, fit μόνο στο train fold. Μην κάνεις global scaler πριν split.

## Πρακτική σειρά υλοποίησης

1. Κράτα target/backtest OHLC raw.
2. Φτιάξε P0 normalized features.
3. Πρόσθεσε μόνο όσα P1 features εξηγούν το setup.
4. Πρόσθεσε P2/P3 features μόνο αν υπάρχει hypothesis.
5. Κάνε feature importance / SHAP / fold stability ανά feature family.
6. Αφαίρεσε raw-level duplicates και highly unstable columns.
7. Σύγκρινε `scaler: none` vs `standard` για XGBoost, όχι πριν διορθώσεις
   normalizations.

## Short recommendation για το τρέχον US100 Ehlers config

Για `us100_30m_ehlers_decycler_continuation_xgboost_meta_v1.yaml`, η σωστή
κατεύθυνση είναι:

- target: `price_col: close`, `open_col: open`, `high_col: high`,
  `low_col: low`, `volatility_col: atr_14`.
- features: μόνο normalized Ehlers/cycle/trend/volatility columns.
- scaler: `none` ή `standard`, αλλά όχι ως υποκατάστατο normalization.
- πρόσθεσε/κράτα ATR-scaled versions για κάθε price-like Ehlers output.
- πρόσθεσε lags/percent ranks για returns, volatility και oscillator strength.

Με αυτό το setup το model δεν μαθαίνει raw price levels. Μαθαίνει τη σχέση
μεταξύ normalized market state και πιθανότητας να πετύχει το ATR-based
triple-barrier trade.
