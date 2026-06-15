# C1 30m Trend Pullback VWAP

## Purpose

`C1_v1_baseline` is a rules-first 30-minute trend-pullback experiment. It combines an EMA trend regime, VWAP/RMS pullback trigger, PPO/MFI/StochRSI/z-score momentum confirmation, and a volatility-regime filter before labeling accepted candidates with a directional triple barrier.

## Config

Primary config:

```bash
python -m src.experiments.runner config/experiments/c1_30m_trend_pullback_vwap_v1.yaml
```

The checked-in baseline is single-asset `SPX500` on cached Dukascopy 30m OHLCV data:

`data/raw/dukascopy_30m_clean/spx500_30m.csv`

Required input columns are `open`, `high`, `low`, `close`, and `volume`.

## Feature Groups

The config uses these registered feature steps:

- `returns`
- `lags`
- `trend`
- `trend_regime`
- `rolling_r2_trend_quality`
- `atr`
- `volatility_regime`
- `vwap`
- `ppo`
- `mfi`
- `stochastic_rsi`
- `zscore_momentum`
- `feature_transforms` for causal EMA/VWAP RMS columns
- `vwap_rms_ema_cross_long` for backward-compatible long/short RMS crossover triggers

## Signal

Final signal kind: `c1_trend_pullback_vwap`.

The signal emits:

- `c1_long_candidate`
- `c1_short_candidate`
- `c1_long_candidate_strict`
- `c1_short_candidate_strict`
- `signal_side`
- `signal_candidate`

`signal_side` is `1` for long candidates, `-1` for short candidates, and `0` otherwise. The default baseline uses the non-strict candidate columns for entries and records strict candidates as diagnostics.

## Target

Target kind: `directional_triple_barrier`.

Parameters:

- `vertical_barrier_bars: 16`
- `profit_barrier_r: 3.0`
- `stop_barrier_r: 1.5`
- `volatility_col: atr_14`
- `entry_price_mode: next_open`
- `neutral_label: drop`

Existing target convention is binary meta-labeling: `1.0` means the directional profit barrier was hit first, `0.0` means the stop barrier was hit first, and no-barrier timeouts are left as `NaN` when `neutral_label: drop`.

## Validation And Robustness

This v1 config is a rules-only baseline with top-level target diagnostics, so it does not define an ML walk-forward split. The target stage is post-signal and keeps the barrier look-forward confined to label creation.

Robustness diagnostics are enabled for:

- transaction cost multipliers `2.0` and `3.0`
- entry delays of `1` and `2` bars

## TODO

Staged configs are intentionally left for a later pass:

- `c1_30m_trend_pullback_vwap_v2_trend_quality.yaml`
- `c1_30m_trend_pullback_vwap_v3_structure.yaml`
- `c1_30m_trend_pullback_vwap_v4_context.yaml`

Before adding `v4_context`, re-check `multi_timeframe` settings so higher-timeframe features use only completed candles.
