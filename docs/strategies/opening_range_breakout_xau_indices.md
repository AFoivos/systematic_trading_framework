# London/New York Opening Range Breakout for XAUUSD and Indices

## Idea

This strategy builds point-in-time opening ranges on 30-minute OHLCV data for London and New York sessions, then treats the first range breakout as a candidate trade. The breakout side is deterministic (`+1` for upside, `-1` for downside); an XGBoost meta-classifier decides whether the candidate has enough expected quality to trade.

The first target universe is high-movement FTMO-style instruments:

- `XAUUSD`
- `US100` / `NAS100`
- `US30`
- `GER40` / `DAX`
- `SPX500`

These markets often concentrate intraday range expansion around cash/session opens, which makes them a better first fit than low-volatility FX pairs. The implementation does not require every symbol to exist. The experiment keeps the broad `data.symbols` universe but uses `data.storage.allow_missing_load_paths: true`, so `load_paths` can contain only the locally available CSVs.

## Data Contract

Base data is 30-minute OHLCV with UTC timestamps. Dukascopy 30m files are bid/ask files labeled by bar start: `2020-01-02 00:00:00` represents the bar from 00:00 to 00:30. Before running the experiment, build canonical mid-price CSVs:

```bash
python scripts/prepare_dukascopy_30m_bid_ask_mid.py
```

The script reads `data/raw/dukascopy_30m/*_30m_bid.csv` and `*_30m_ask.csv`, then writes clean mid-price files under `data/raw/dukascopy_30m_clean/`. The canonical `open`, `high`, `low`, and `close` columns are mid prices. Bid, ask, and spread columns are retained for later analysis, but this version still uses the fixed cost and slippage configuration.

Required canonical fields are:

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `asset`

The experiment loader normalizes explicit CSV load paths to the repo's canonical per-asset frames. The ORB and multi-timeframe features sort by timestamp, keep the last duplicate timestamp per asset, avoid forward-filled prices, and process each asset independently.

## Multi-Timeframe Features

`src/features/multi_timeframe.py` derives 1h and 4h OHLCV bars from 30m data. Bars are labeled at the higher-timeframe close, and features are merged back with backward `merge_asof`, so a 30m row can only see the latest fully closed 1h/4h bar.

The ORB experiment sets `timestamp_convention: bar_start` for Dukascopy. In this mode, the 1h bar from 00:00 to 01:00 is labeled 01:00 and is not visible to the 00:30 row. The legacy `bar_close` mode remains available for datasets whose 30m timestamps are already bar closes.

Emitted columns include:

- `mtf_1h_close_logret`
- `mtf_1h_trend_score`
- `mtf_1h_volatility`
- `mtf_1h_atr`
- `mtf_1h_adx`
- `mtf_1h_regime_vol_ratio`
- the equivalent `mtf_4h_*` columns

Incomplete higher-timeframe bars caused by missing 30m rows are not used as completed HTF bars.

## Sessions and DST

Session times are defined in local exchange/session time and converted through IANA time zones:

- London: `Europe/London`, open `08:00`, first 2 bars, trade until `12:00`
- New York XAU: `America/New_York`, open `08:00`, first 2 bars, trade until `12:00` (supported, but disabled in the baseline after the first diagnostics showed negative drag)
- New York cash indices: `America/New_York`, open `09:30`, first 2 bars, trade until `12:00`

No fixed UTC open hour is hardcoded. Daylight saving changes are handled by timezone conversion.

Default asset-session mapping:

- `XAUUSD`: London
- `US100`, `NAS100`, `US30`, `SPX500`: New York cash
- `GER40`, `DAX`: London

`new_york_xau` remains defined in the experiment config for explicit ablation runs, but it is not part of the default baseline or Optuna session search space.

## ORB Features

`src/features/opening_range_breakout.py` emits only `orb_`-prefixed columns, including:

- range: `orb_range_high`, `orb_range_low`, `orb_range_mid`, `orb_range_width`, `orb_range_width_atr`
- candidate state: `orb_candidate`, `orb_side`, `orb_active_window`, `bars_since_orb_breakout`
- breakout strength: `orb_breakout_strength_atr`, `orb_breakout_strength_range`
- context: `orb_close_position_in_range`, `orb_pre_breakout_volatility`, `orb_failed_breakout_recent`

The range is unknown until the configured opening-range bars have completed. No candidate can be emitted during range formation. With `max_breakouts_per_session: 1`, only the first valid breakout event per session is activated.

## Target and Signal

The model target uses triple-barrier meta-labeling:

- `candidate_col: orb_candidate`
- `side_col: orb_side`
- entry at `next_open`
- `upper_mult: 2.0`
- `lower_mult: 1.0`
- `max_holding: 8`

The signal step is `meta_probability_side`: it trades only when `pred_prob >= threshold` and keeps the deterministic `orb_side`. It never flips a rejected long candidate into a short, or vice versa.

## FTMO Risk

The default risk settings are intentionally conservative for high-movement instruments:

- `risk_per_trade: 0.003`
- `max_leverage: 1.0`
- confidence floor from meta probability
- portfolio gross leverage capped at `1.0`
- max per-asset weight `0.35`
- daily and weekly FTMO-style guardrails enabled
- 30m cooloff set to 48 bars

No martingale, grid, or averaging-down logic is used.

## Run

First prepare the clean Dukascopy mid files:

```bash
python scripts/prepare_dukascopy_30m_bid_ask_mid.py
```

Then edit `data.storage.load_paths` if only a subset of symbols is available, and run:

```bash
python -m src.experiments.runner config/experiments/ftmo_30m_xau_indices_london_newyork_opening_range_breakout_xgboost_meta_v1.yaml
```

Run Optuna:

```bash
python -m src.experiments.optuna_search config/optuna/optuna_ftmo_30m_xau_indices_london_newyork_opening_range_breakout_xgboost_meta_v1.yaml
```

## Diagnostics to Inspect

The report and summary payload include ORB-specific diagnostics:

- candidate and accepted trade counts by asset/session
- PnL, gross PnL, and cost attribution by asset
- PnL by session
- success rate by asset/session
- average range width in ATR units
- breakout success rate
- FTMO target hit ratio, active week ratio, loss breach counts, and concentration metrics

## Limitations

The first version uses a simple deterministic opening-range event definition and one meta-classifier per asset. It does not model order-book liquidity, news embargoes, contract-specific trading breaks, or broker-specific execution constraints. Session definitions should be revisited for each data vendor's timestamp convention before live use.
