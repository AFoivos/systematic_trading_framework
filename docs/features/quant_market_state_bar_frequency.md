# Quant Market State bar frequency

`kds`, `rlvs`, `lmds`, and `quant_market_state` accept an explicit
`bar_minutes` parameter. It must be finite and strictly positive. The default
is `1.0`, preserving the original one-minute behavior exactly.

```yaml
- step: quant_market_state
  params:
    preset: balanced
    bar_minutes: 30.0
```

All system windows and state-transition horizons remain expressed in bars.
Elapsed wall-clock time is converted to elapsed bars before Kalman transition
and volatility process-noise updates. Gap thresholds scale with the declared
bar duration: a small gap defaults to five bars and a hard reinitialization to
thirty bars. Weekend gaps remain separately identified.

The input frame is not resampled internally. Its index cadence must match
`bar_minutes`; callers are responsible for supplying already formed bars.
