# FTMO Optuna Meta V1 Plan

## Why This Is An Exploration Run

Το smoke run έδειξε ότι το FTMO meta pipeline είναι λειτουργικό αλλά υπερβολικά ανενεργό:
πολύ υψηλό `flat_rate`, χαμηλό `trade_rate`, χαμηλό `oos_prediction_coverage` και μηδενικό
`weekly_target_hit_ratio`. Για αυτό το πρώτο Optuna pass δίνει προτεραιότητα στην activity /
coverage discovery, ενώ κρατάει τα hard FTMO loss constraints ενεργά.

## What Gets Tuned

- Candidate generation από το `shock_context`, ώστε να ανοίξει το search πάνω στο candidate coverage.
- Triple-barrier target geometry με `max_holding`, `upper_mult` και `vol_window`, κρατώντας
  fixed το `lower_mult: 1.0`.
- Meta signal activity μέσω `signals.params.threshold` και `signals.params.clip`.
- FTMO risk sizing μέσω `risk_per_trade`, `confidence_floor`, `confidence_power`,
  `risk.sizing.max_leverage`.
- Portfolio aggressiveness μέσω `gross_target`, `max_gross_leverage`, `max_weight`, `min_weight`.
- XGBoost capacity / regularization / class balance.
- Selected feature windows που επηρεάζουν volatility, regime, session, ROC, RSI, momentum και lags.

## What Stays Fixed

- `model.target.kind: triple_barrier`
- `model.target.label_mode: meta`
- `model.target.entry_price_mode: next_open`
- `model.target.neutral_label: lower`
- `model.target.tie_break: lower`
- `model.target.side_col: primary_side`
- `model.target.candidate_col: trade_candidate`
- `signals.kind: meta_probability_side`
- `signals.params.side_col: primary_side`
- `signals.params.candidate_col: label_candidate`
- `signals.params.signal_col: signal_meta_side`
- `risk.sizing.kind: ftmo_risk_per_trade`
- `risk.sizing.confidence_mode: meta_success`
- `backtest.signal_col: signal_meta_side`

Σημείωση: το current Optuna spec δεν μπορεί να συγχρονίσει δύο διαφορετικά paths με μία sampled
τιμή, οπότε γίνεται tune μόνο στο `signals.params.threshold`, ενώ το `signals.params.upper`
μένει fixed ως alias στο base config.

## Metrics To Inspect After The Run

- `oos_prediction_coverage`
- `flat_rate`
- `trade_rate`
- `derived.active_week_ratio`
- `derived.entry_count`
- `weekly_return_mean`
- `weekly_target_hit_ratio`
- `max_drawdown`
- `cost_to_gross_pnl`
