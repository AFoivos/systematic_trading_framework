# SPX500 Thursday Weak-Prev-Day Reversal v1

## Thesis

This is an intraday calendar/session mean-reversion experiment for SPX500 30m data.
It does not use the existing EMA, VWAP, PPO, StochRSI, ORB, ML, or meta-label strategies.

The hypothesis is simple: after a weak completed trading day, Thursday's NY cash open has shown
mean-reversion behavior in the mock SPX500 sample. The strategy buys only that narrow setup and
does not hold overnight.

## Rule

1. Convert timestamps from UTC to `America/New_York`.
2. Compute the previous completed NY trading day's close-to-close return.
3. If today is Thursday and `prev_daily_return < -0.0006369942365362478`, emit a long signal at
   NY `09:00`.
4. The framework enters at the next bar open, which is expected to be the NY `09:30` bar on 30m data.
5. Exit through `max_holding_bars: 6`, approximately the NY `12:00` bar.
6. No overnight exposure. TP/SL are intentionally set very far away so the experiment measures
   the fixed intraday holding window rather than barrier optimization.

## Causality

The signal at Thursday `09:00` uses only:

- The current local timestamp.
- The current local weekday.
- The prior completed trading day's close-to-close return.

It does not use Thursday's later prices, Thursday's close, or any future return label.

## Research Evidence From Scratch Scan

The initial scratch scan used round-trip cost of 5 bps and selected the threshold from the
2015-2021 train period.

Train 2015-2021:

- Trades: 145
- Cumulative return: 1.8%
- Profit factor: 1.08
- Max drawdown: -4.8%

Test 2022-2026:

- Trades: 98
- Cumulative return: 14.6%
- Annualized return: about 3.2%
- Profit factor: 2.06
- Max drawdown: -2.1%

Full sample 2015-2026:

- Trades: 243
- Cumulative return: 16.6%
- Profit factor: 1.41
- Max drawdown: -4.8%

## Framework Backtest Result

The checked-in YAML was also run through the official experiment runner:

```bash
python -m src.experiments.runner config/experiments/codex/spx500_30m_thursday_weak_prevday_reversal_v1.yaml
```

Primary summary:

- Cumulative return: 19.55%
- Annualized return: 1.84%
- Sharpe: 0.62
- Sortino: 1.07
- Max drawdown: -5.23%
- Profit factor: 1.43
- Hit rate: 52.48%
- Trade count: 242
- Cost to gross PnL: 39.84%

## Interpretation

This is a candidate edge, not a finished deployable alpha. The train period is only mildly positive,
while the out-of-sample period is much stronger. That makes the pattern interesting but also
regime-sensitive. The YAML is intended for reproducible framework testing before any promotion.

## How To Run

```bash
python -m src.experiments.runner config/experiments/codex/spx500_30m_thursday_weak_prevday_reversal_v1.yaml
```
