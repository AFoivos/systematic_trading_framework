# Reusable meta-label feature infrastructure

These components are generic feature infrastructure. They do not create trade
signals, execute orders, or encode an EURUSD-specific strategy.

## Nested transforms

Transforms run after their owning feature step, in declaration order:

```yaml
features:
  - step: rsi
    params: {windows: [14]}
    transforms:
      affine:
        items:
          - {source_col: close_rsi_14, output_col: rsi_14, scale: 0.04, offset: -2.0}
      product:
        items:
          - {left_col: direction, right_col: rsi_14, output_col: dir_rsi_14}
      log:
        items:
          - {source_col: di_ratio_with_offsets, output_col: di_logratio}
```

`log` calculates `log(source + offset)` and emits `NaN` where the adjusted
input is at or below `eps`. `affine` calculates `source * scale + offset`.
`product` performs index-aligned column multiplication with optional scaling.
All three emit `float32`, accept selectors, default to `inplace: false`, and are
row-local (therefore causal).

## Registered time-series features

```yaml
features:
  - step: path_efficiency
    params:
      price_col: close
      windows: [24, 48, 96, 192]
      use_log_prices: true
      output_template: eff_{window}
  - step: returns
    params: {log: false, col_name: close_ret}
  - step: rolling_autocorrelation
    params:
      source_col: close_ret
      windows: [48, 192]
      lag: 1
```

`path_efficiency` divides absolute N-bar displacement by trailing N-step path
length, returns `NaN` for a zero denominator, and can clip to `[0, 1]`.
`rolling_autocorrelation` is the trailing correlation of a series with its
configured lag. Both use only information available through the output row.

## Completed-trade history

`add_completed_trade_history_features` operates on candidate/event tables, not
bars. It emits rolling win rate and mean plus all-history win rate and mean.
Only trades whose completion precedes the candidate timestamp are visible by
default; `allow_same_timestamp: true` makes the boundary inclusive. Optional
`group_cols` isolates histories by asset, strategy family, or both. No visible
history produces `NaN` float32 outputs. `CompletedTradeHistoryState` provides
the same calculations for incremental/live event processing.
