# MATB — Multi-Asset Trend Breakout

## Κατάσταση έρευνας

Η τρέχουσα acceptance κατάσταση είναι **REJECTED**. Το immutable event audit
βρήκε 667 candidates, κάτω από το deterministic gate των 800 και το ML gate
των 1.500. Το pooled ML δεν εκπαιδεύτηκε και δεν έγινε αλλαγή thresholds. Η
υλοποίηση παραμένει χρήσιμη ως causal, reproducible research baseline, όχι ως
ένδειξη production readiness.

Το ιστορικό από 2024-01-01 και μετά χρησιμοποιείται ως pseudo-holdout. Δεν είναι
πλήρως pristine, επειδή το repository έχει χρησιμοποιηθεί σε προηγούμενα
experiments. Ακόμη και θετικό pseudo-holdout απαιτεί forward demo validation.

## Οικονομική υπόθεση

Η MATB ελέγχει αν σπάνια 20-day price breakouts, όταν συμφωνούν με
volatility-normalized momentum 5/20/60 ημερών, συνεχίζουν αρκετά ώστε ένα
volatility-scaled, long/short portfolio να αποζημιώνεται μετά από executable
bid/ask spread, transaction costs και slippage. Το pooled ML έχει μόνο πιθανό
ρόλο meta-filter· δεν επιτρέπεται να δημιουργήσει direction.

Universe και groups:

| Group | Assets |
|---|---|
| equity_indices | SPX500, US100, GER40, NIKKEI225 |
| metals | XAUUSD, XAGUSD |
| energy | USOIL, BRENT |
| fx | EURUSD |
| crypto | ETHUSD |

## Causal features

Όλα τα δεδομένα θεωρούνται 30-minute bars με bar-start timestamps και
`bars_per_day = 48`.

### ATR και gaps

Το true range χρησιμοποιεί προηγούμενο close μόνο όταν το timestamp delta
είναι θετικό και έως `1.5 * 30 minutes`. Σε μεγαλύτερο gap χρησιμοποιείται μόνο
`high - low`. Το `matb_atr` είναι Wilder EWMA 48 bars (`alpha=1/48`) και
`matb_atr_pct = matb_atr / close`.

### Volatility και momentum

Από `r_t = log(close_t / close_{t-1})` υπολογίζονται causal EWMA volatilities
240 και 2.880 bars:

```text
matb_vol_ratio_5d_60d = matb_vol_short / matb_vol_long
raw_momentum_h = log(close_t / close_{t-h})
matb_mom_h_z = clip(raw_momentum_h / (matb_vol_long * sqrt(h)), -3, 3)
matb_trend_score = mean(mom_5d_z, mom_20d_z, mom_60d_z)
```

### Donchian και crossing

Ο 20-day channel αποκλείει αυστηρά το current bar:

```python
prior_high = high.shift(1).rolling(960).max()
prior_low = low.shift(1).rolling(960).min()
```

Long crossing απαιτεί `close_t > prior_high_t` και
`close_{t-1} <= prior_high_{t-1}`. Το short είναι συμμετρικό. Έτσι ένα price
path που μένει έξω από το channel δεν παράγει επαναλαμβανόμενα events.

Additional features:

```text
channel_width_atr = (prior_high - prior_low) / ATR
breakout_distance_atr = distance from crossed boundary / ATR
close_location = (close - low) / (high - low)
bar_range_atr = (high - low) / ATR
gap_atr = abs(open - previous_close) / ATR
spread_to_median = spread_bps / shift(1).rolling(960).median()
```

Missing spread παραμένει NaN και καταγράφεται. Δεν γίνεται imputation σε zero.

## Candidate rules

Decision bars είναι μόνο `03:30`, `07:30`, `11:30`, `15:30`, `19:30`,
`23:30` UTC. Long candidate απαιτεί crossing, trend score `>=0.20`, positive
20d momentum, breakout distance `[0,0.50]` ATR, channel width `>=4` ATR,
volatility ratio `[0.50,2.50]` και spread ratio `<=2` όταν υπάρχει. Το short
είναι συμμετρικό με threshold `<=-0.20`.

Το `matb_candidate` signal μεταφέρει μόνο την deterministic πλευρά. Δεν υπάρχει
fit ή future information σε feature/signal generation.

## Κοινό trade path target/backtest

Target και actual portfolio backtest καλούν τον ίδιο low-level simulator:

1. Το signal είναι γνωστό στο decision-bar close.
2. Entry στο επόμενο διαθέσιμο 30-minute open: long `ask_open`, short
   `bid_open`. Midpoint χρησιμοποιείται μόνο ως audited fallback όταν δεν
   υπάρχει πλήρες bid/ask OHLC set.
3. Initial risk παγώνει σε `2 * matb_atr` του signal timestamp.
4. Emergency profit cap στο 8R.
5. Trailing ενεργοποιείται όταν MFE `>=1.5R`. Είναι monotone και απέχει
   `2.5 * current ATR` από highest/lowest executable price.
6. Η current bar high/low δεν ανεβάζει retroactively stop που ελέγχεται στο ίδιο
   OHLC bar. Το stop update γίνεται μετά τους current-bar barrier checks.
7. Trend score `<=0` για long ή `>=0` για short προγραμματίζει exit στο επόμενο
   executable open.
8. Maximum holding 1.440 bars. Δεν επιτρέπεται δεύτερη θέση στο ίδιο asset.
9. Gap-through-stop εκτελείται στο executable open. Same-bar stop/8R επιλύεται
   με `closest_to_open`.
10. Η ίδια side-oriented PnL/R function εφαρμόζει explicit costs και slippage.

Synthetic parity coverage απαιτεί absolute error `<=1e-12` για long/short stop,
long/short trailing, trend flip, max holding, emergency profit, bid/ask costs,
gap-through-stop και same-bar tie.

## Portfolio risk

- Equity risk budget ανά trade: 0,20%.
- Position cap από `risk_per_trade / (initial_stop_distance / entry_price)`, όχι
  ίσα nominal weights.
- Maximum 4 open trades.
- Group open-trade caps: indices 2, κάθε άλλο group 1.
- Gross leverage cap 1,25.
- Group gross caps: indices 0,55, metals 0,30, energy 0,30, FX 0,20, crypto
  0,15.
- Mark-to-market portfolio kill switch σε drawdown 8%.

Τα artifacts περιλαμβάνουν gross/net exposure, asset weights, group gross/net
exposure, risk/PnL contribution και portfolio-limit rejection counts.

## ML role και hard sample gate

Αν το gate περνούσε, το model question θα ήταν
`P(matb_net_trade_r > 0 | deterministic candidate features)` και το output θα
μπορούσε μόνο να απορρίψει candidates με probability `<0.55`, EV `<0.10R` ή
μη-OOS prediction. Encoders/calibration θα έκαναν fit μόνο σε κάθε training
fold, με event-interval purging και embargo.

Fit απαγορεύεται αν αποτύχει οποιοδήποτε:

- total events `>=1.500`, long `>=150`, short `>=150`,
- τουλάχιστον 4 groups με `>=100` events,
- post-purge train rows ανά fold `>=300`,
- maximum asset/group training share `<=45%`,
- και οι δύο target classes σε κάθε training fold.

Το audit έδωσε 667 events (504 long, 163 short), μόνο δύο groups με τουλάχιστον
100 events και maximum group share 61,62%. Συνεπώς δεν υλοποιήθηκε/εκτελέστηκε
pooled LightGBM και δεν εκτελέστηκαν calibration/placebo metrics. Τα blocked
artifacts δηλώνουν ρητά `NOT_RUN`, όχι μηδενικές επιδόσεις.

## Validation και acceptance

Το deterministic config είναι
`config/experiments/matb/00_matb_deterministic.yaml`. Τα immutable gates είναι
στο `config/experiments/matb/acceptance_gates.yaml` και τα ακριβώς 27
predeclared neighborhood trials στο `declared_trials.json`:

- trend threshold: 0,10 / 0,20 / 0,30,
- Donchian: 15d / 20d / 30d,
- stop: 1,5 / 2,0 / 2,5 ATR.

Δεν γίνεται επιλογή καλύτερου trial. DSR, CSCV-PBO και neighborhood stability
είναι diagnostics πολλαπλών δοκιμών, όχι tuning permission.

Kill gates περιλαμβάνουν candidate/trade sufficiency, pseudo-OOS Sharpe,
calendar-fold stability, 2× costs, +1 bar delay, PnL concentration και
drawdown μετά από ex-post scaling σε 8% annual volatility. Η αποτυχία ενός gate
αρκεί για `REJECTED`.

## Known limitations

- Τα raw assets έχουν διαφορετικές αρχικές ημερομηνίες και session gaps.
- Το `spread_bps` scaling βασίζεται στη διαθέσιμη source στήλη· η candidate
  filter χρησιμοποιεί μόνο ratio, ενώ execution χρησιμοποιεί actual bid/ask.
- Το OHLC tie-break δεν ανακατασκευάζει intrabar tick order.
- Explicit cost stress πολλαπλασιάζει commission/slippage, ενώ το observed
  bid/ask spread παραμένει ήδη ενσωματωμένο στο gross executable path.
- Το pseudo-holdout δεν είναι pristine και το sample είναι ανεπαρκές για ML.
- Καμία θετική historical metric δεν παρακάμπτει τα acceptance gates ή την
  ανάγκη για forward demo validation.
