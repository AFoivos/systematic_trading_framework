# Shock Context

Το `shock_context` είναι feature step για contrarian shock-reversion research πάνω σε intraday bars.
Δεν αλλάζει τον υπάρχοντα backtester και δεν υλοποιεί intrabar stop/take πάνω στα πραγματικά spike levels.
Δίνει event approximation που μπορεί να χρησιμοποιηθεί είτε απευθείας σαν base rule είτε σαν primary rule για meta-labeling.

## Τι παράγει

- `shock_ret_1h`, `shock_ret_4h`: σωρευτικές αποδόσεις 1 και 4 bars.
- `shock_ret_z_1h`, `shock_ret_z_4h`: z-score των παραπάνω horizon returns σε rolling window.
- `shock_atr_multiple_1h`, `shock_atr_multiple_4h`: signed move σε μονάδες ATR.
- `shock_distance_ema`: signed απόσταση από EMA σε μονάδες ATR.
- `shock_up_candidate`, `shock_down_candidate`: event flags για ακραίο ανοδικό ή καθοδικό shock.
- `shock_candidate`: union των shock events.
- `shock_side_contrarian`: contrarian πλευρά του setup.
  - ανοδικό shock -> `-1`
  - καθοδικό shock -> `+1`
  - αλλιώς `0`
- `shock_side_contrarian_active`: κρατημένη contrarian πλευρά για μικρό post-shock execution window.
  - από default είναι event-only, όπως το `shock_side_contrarian`
  - αν ορίσεις `post_shock_active_bars > 1`, μένει ενεργή για τόσα bars συνολικά, μαζί με το shock bar
- `shock_active_window`: `1` όταν το post-shock active window είναι ανοιχτό, αλλιώς `0`
- `shock_strength`: συνεχές severity score από normalized return z-score, ATR multiple και EMA distance.
- `bars_since_shock`: bars από το πιο πρόσφατο `shock_candidate`.

## Λογική baseline

Ένα shock event ενεργοποιείται μόνο όταν συμφωνούν και τα τρία:

- αρκετά μεγάλο normalized return
- αρκετά μεγάλο move σε ATR units
- αρκετή απόσταση από EMA

Η κατεύθυνση του event καθορίζεται από το dominant horizon ανάμεσα σε `short_horizon` και `medium_horizon`.

## Χρήση για meta-labeling

Το feature step είναι συμβατό με το υπάρχον `triple_barrier` meta-label path:

```yaml
target:
  kind: triple_barrier
  price_col: close
  open_col: open
  high_col: high
  low_col: low
  returns_col: close_logret
  max_holding: 24
  upper_mult: 1.5
  lower_mult: 1.5
  vol_window: 24
  neutral_label: drop
  side_col: shock_side_contrarian
  candidate_col: shock_candidate
  candidate_out_col: meta_candidate
```

Για pure rule-based baseline δεν χρειάζεται νέο signal module.
Μπορείς να χρησιμοποιήσεις απευθείας:

```yaml
signals:
  kind: none

backtest:
  signal_col: shock_side_contrarian
  min_holding_bars: 2
```

Για classifier/meta-label filtering συνήθως θέλεις το `shock_side_contrarian_active` ως `base_signal_col`:

```yaml
signals:
  kind: probability_threshold
  params:
    prob_col: pred_prob
    signal_col: signal_prob_threshold
    base_signal_col: shock_side_contrarian_active
    upper: 0.57
    upper_exit: 0.52
    lower: 0.43
    lower_exit: 0.48
    mode: long_short
```

## Minimal example

```yaml
features:
  - step: returns
    enabled: true
    params:
      log: true
      col_name: close_logret

  - step: trend
    enabled: true
    params:
      price_col: close
      ema_spans: [24]

  - step: atr
    enabled: true
    params:
      high_col: high
      low_col: low
      close_col: close
      window: 24
      method: wilder
      add_over_price: true

  - step: shock_context
    enabled: true
    params:
      price_col: close
      high_col: high
      low_col: low
      returns_col: close_logret
      ema_col: close_ema_24
      atr_col: atr_24
      short_horizon: 1
      medium_horizon: 4
      vol_window: 24
      ret_z_threshold: 2.0
      atr_mult_threshold: 1.5
      distance_from_mean_threshold: 1.0
      post_shock_active_bars: 4
```

## Σημείωση execution

Το `shock_side_contrarian` είναι event column και ταιριάζει για `triple_barrier.side_col`.
Για πραγματικό post-shock trade gating συνήθως θέλεις `shock_side_contrarian_active` ως `base_signal_col`,
ώστε το μοντέλο να μπορεί να κρατήσει θέση και στα επόμενα bars του ίδιου shock window.
