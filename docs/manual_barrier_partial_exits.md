# Manual Barrier Partial Exits

`manual_barrier` supports opt-in partial exits. When `partial_exits` is absent or
`enabled: false`, the engine keeps the legacy single-exit behavior.

Partial-exit rules are sorted by `trigger_r` ascending. Stop-loss checks remain
conservative: if a bar touches both the stop and a partial trigger, the stop is
processed first. If a bar touches a partial trigger and the full take-profit,
trigger-priced partial exits are booked before the remaining position exits at
the take-profit.

```yaml
backtest:
  take_profit_r: 2.0
  stop_loss_r: 1.5
  max_holding_bars: 12
  dynamic_exits:
    enabled: false
  partial_exits:
    enabled: true
    rules:
      - trigger_r: 0.5
        fraction: 0.5
        exit_price: trigger
```
