# Bybit Demo market-making runbook

This runner uses Bybit mainnet public linear market data and Bybit Demo private execution only.
It never uses production private REST, production private WebSocket, or WebSocket order entry.

## Safety model

- Public book/trades: `wss://stream.bybit.com/v5/public/linear`
- Demo private REST: `https://api-demo.bybit.com`
- Demo private stream: `wss://stream-demo.bybit.com/v5/private`
- REST hostname and private/public WebSocket URLs are exact-match validated at startup.
- `BYBIT_EXECUTION_ENV` must equal `demo`.
- `live_dry_run` requires `execution.allow_order_submission: false`.
- `demo_submit` requires `execution.allow_order_submission: true`, Demo credentials, private-stream auth,
  account query, instrument metadata, clock-drift validation, and zero unknown open orders.
- Create timeouts are never blindly retried. The client reconciles by `orderLinkId` and stops quoting if
  the outcome remains uncertain.
- All ordinary quotes are `Limit` + `PostOnly` + `reduceOnly: false`. A market order is available only
  for an explicitly requested `flatten_at_boundary` emergency unwind and is `reduceOnly: true`.

## Environment variables

Συμπλήρωσε τα Bybit πεδία στο τοπικό `.env` του repository. Το αρχείο
αγνοείται από Git και από το Docker build context, ενώ το `docker-compose.yml`
περνά ρητά μόνο τα αναμενόμενα environment variables στο `app` container.

```dotenv
BYBIT_EXECUTION_ENV=demo
BYBIT_DEMO_API_KEY=<Demo Trading API key>
BYBIT_DEMO_API_SECRET=<Demo Trading API secret>
BYBIT_DEMO_REST_URL=https://api-demo.bybit.com
BYBIT_DEMO_PRIVATE_WS_URL=wss://stream-demo.bybit.com/v5/private
BYBIT_PUBLIC_WS_URL=wss://stream.bybit.com/v5/public/linear
```

Τα παρακάτω PowerShell exports παραμένουν εναλλακτική για process-local
overrides· οι ήδη ορισμένες process variables υπερισχύουν του `.env`.

```powershell
$env:BYBIT_EXECUTION_ENV = "demo"

# Required only for demo_submit:
$env:BYBIT_DEMO_API_KEY = "<Demo Trading API key>"
$env:BYBIT_DEMO_API_SECRET = "<Demo Trading API secret>"

# Optional exact-value overrides; any unsafe value is rejected:
$env:BYBIT_DEMO_REST_URL = "https://api-demo.bybit.com"
$env:BYBIT_DEMO_PRIVATE_WS_URL = "wss://stream-demo.bybit.com/v5/private"
$env:BYBIT_PUBLIC_WS_URL = "wss://stream.bybit.com/v5/public/linear"
```

Never put credentials in YAML, command-line arguments, shell history, reports, or committed files.

## Tests

```powershell
.\.venv312\Scripts\python.exe -m pytest -q tests\market_making
```

The optional integration test is disabled unless all three variables are present:

```powershell
$env:RUN_BYBIT_DEMO_INTEGRATION_TESTS = "1"
$env:BYBIT_DEMO_API_KEY = "<Demo Trading API key>"
$env:BYBIT_DEMO_API_SECRET = "<Demo Trading API secret>"
.\.venv312\Scripts\python.exe -m pytest -q `
  tests\integration\test_bybit_demo_market_making_integration.py
```

The integration test always issues Demo REST `cancel-all` in `finally`.

## Quote placement modes

The strategy YAML selects one placement mode; the Bybit live engine records both the requested and the
actually applied mode for every quote decision.

- `fair_price_bps` builds a reservation price around the configured fair-price model (`microprice` here),
  applies volatility-aware spread width and inventory skew, then rounds bid down and ask up to the runtime
  Bybit tick. Use it when the model, rather than the current best prices, should determine placement.
- `join_top_of_book` quotes exactly at the current best bid and best ask. Microprice is still calculated for
  diagnostics and the adaptive fee/edge gate, but the fair-price spread and inventory skew do not move the
  order prices. Use it to measure passive top-of-book participation with lower price aggressiveness.
- `improve_top_of_book` attempts `best_bid + one tick` and `best_ask - one tick`. It applies that mode only
  while the two resulting prices remain strictly ordered. If there is no room—including a one-tick market
  spread—it joins both best prices and records `fallback_to_join: true` plus
  `applied_quote_placement_mode: join_top_of_book`.

The unchanged `01_adaptive_inventory_microprice.yaml` remains the Kraken research-smoke variant. The two
Bybit variants keep the same strategy and experiment names required by the shared validator:

- `01_adaptive_inventory_microprice_bybit_join.yaml`
- `01_adaptive_inventory_microprice_bybit_improve.yaml`

## Bybit runtime instrument overrides

The strategy variants contain constraint placeholders only because the shared offline validator requires a
self-contained scenario. After `GET /v5/market/instruments-info`, the live engine discards those static values
for live sizing and validation:

| Strategy YAML field | Runtime source/application |
| --- | --- |
| `quote.tick_size` | Bybit `priceFilter.tickSize` |
| `quote.lot_size` | Bybit `lotSizeFilter.qtyStep` |
| `quote.min_order_size` | Bybit `lotSizeFilter.minOrderQty` |
| `quote.min_notional` | Bybit `lotSizeFilter.minNotionalValue` |
| `quote.order_size` | Smallest `qtyStep`-aligned quantity covering both `minOrderQty` and 102% of `minNotionalValue` at the startup reference price |
| `quote.max_inventory` and static risk equivalents | Runtime order size multiplied by `risk.maximum_inventory_order_multiple` (restricted to 3–5) |

The same runtime values configure the quote generator and central risk engine. Immediately before each
place/amend intent, `BybitInstrument.validate_order` again checks price range/tick alignment, quantity
range/step alignment, and minimum notional. The final order path therefore does not use Kraken tick, lot,
minimum quantity, minimum notional, default size, or maximum inventory values.

`run_metadata.json`, `summary.json`, and `config_used_redacted.yaml` expose these under `runtime_applied`:

```text
quote_placement_mode
instrument_tick_size
instrument_quantity_step
instrument_minimum_order_quantity
instrument_minimum_notional
runtime_order_size
runtime_maximum_inventory
```

## Manual join-top-of-book dry run

The following command is documentation only; run it manually when ready. It cannot submit orders because
the low-churn config has `mode: live_dry_run` and `allow_order_submission: false`.

```powershell
docker compose run --rm `
  -e BYBIT_EXECUTION_ENV=demo `
  app python scripts/run_bybit_demo_market_making.py `
  --config config/execution/bybit_demo_market_making_low_churn.yaml `
  --strategy-config config/market_making/strategies/01_adaptive_inventory_microprice_bybit_join.yaml `
  --mode live_dry_run `
  --duration-seconds 600 `
  --aligned-windows `
  --cancel-all-on-exit
```

## Manual improve-top-of-book dry run

```powershell
docker compose run --rm `
  -e BYBIT_EXECUTION_ENV=demo `
  app python scripts/run_bybit_demo_market_making.py `
  --config config/execution/bybit_demo_market_making_low_churn.yaml `
  --strategy-config config/market_making/strategies/01_adaptive_inventory_microprice_bybit_improve.yaml `
  --mode live_dry_run `
  --duration-seconds 600 `
  --aligned-windows `
  --cancel-all-on-exit
```

Use equal durations and comparable UTC/liquidity windows. For a complete two-hour report, change
`--duration-seconds` to `7200`, keep the configured 7200-second reporting interval, and start close to an
even UTC boundary.

## Metrics to compare after the two dry runs

- Requested/applied placement-mode counts, improve fallback-to-join count/rate, quoted spread in ticks and
  bps, and market spread in bps.
- Quote decisions, strategy/risk rejection reasons, placed/amended/cancelled intents, cancel-to-fill and
  amend-to-fill ratios, average order lifetime, and post-only rejection count.
- Fill ratio, fills per placed order, fills per quote attempt, maker/taker counts, and average time to fill.
- Markout mean/median and adverse-selection rate at every horizon, especially 1 s, 5 s, 30 s, and 60 s.
- Gross spread capture, fees, realized/unrealized/net PnL, PnL by side, volatility bucket, and spread bucket.
- Average/time-weighted/maximum inventory, inventory utilization, carried inventory, and buy/sell volume.
- API/market-data latency, disconnect/reconnect counts, sequence gaps, stale-book duration, and reconciled or
  unknown order state.

Interpret fill and PnL comparisons only after checking that applied-mode counts and market conditions are
similar; an improve run with frequent fallback is mostly a join run.

## Demo submission

Do not enable this until tests, the ten-minute dry run, and a full two-hour dry run have been reviewed.
Then change both fields in `config/execution/bybit_demo_market_making.yaml`:

```yaml
execution:
  mode: demo_submit
  allow_order_submission: true
```

Run with Demo credentials inherited from the current PowerShell environment:

```powershell
docker compose run --rm `
  -e BYBIT_EXECUTION_ENV=demo `
  -e BYBIT_DEMO_API_KEY `
  -e BYBIT_DEMO_API_SECRET `
  app python scripts/run_bybit_demo_market_making.py `
  --config config/execution/bybit_demo_market_making.yaml `
  --strategy-config config/market_making/strategies/01_adaptive_inventory_microprice.yaml `
  --mode demo_submit `
  --aligned-windows `
  --cancel-all-on-exit
```

## Continuous Demo submission

Το dedicated config `config/execution/bybit_demo_market_making_continuous.yaml`
είναι το μόνο tracked execution config που έχει σκόπιμα
`mode: demo_submit` και `allow_order_submission: true`. Χρησιμοποιεί τα
low-churn rate limits, session-loss όριο 2 USDT και συνεχίζει χωρίς χρονικό όριο
μέχρι `Ctrl+C` ή safety stop:

```bash
docker compose run --rm app \
  python scripts/run_bybit_demo_market_making.py \
  --config config/execution/bybit_demo_market_making_continuous.yaml \
  --strategy-config config/market_making/strategies/01_adaptive_inventory_microprice_bybit_join.yaml \
  --mode demo_submit \
  --aligned-windows \
  --cancel-all-on-exit
```

Πριν από το πρώτο continuous run, βάλε προσωρινά
`RUN_BYBIT_DEMO_INTEGRATION_TESTS=1` στο `.env` και τρέξε το opt-in integration
test. Μετά επανάφερέ το σε `0`. Μην εκκινείς δεύτερο instance και μην κάνεις
force-kill: το graceful shutdown ακυρώνει Demo orders και κάνει τελικό
reconciliation.

## Safe shutdown

Use `Ctrl+C` or stop the container normally. The runner stops new quotes, sends Demo REST cancel-all,
queries open orders, performs final reconciliation, writes a partial immutable report, and only then closes
the WebSockets. If the process is force-killed, verify and cancel Demo orders manually before restarting.

## Strict trade-through dry-fill limitations

The live dry-run fill model deliberately refuses to infer queue position. A resting buy is filled only when a
public sell-aggressor trade prints strictly below its price; a resting sell is filled only when a public
buy-aggressor trade prints strictly above its price. An equal-price print never fills, even if it may have
consumed queue ahead, so quiet or top-of-book runs can legitimately report zero fills.

When strict trade-through occurs, the model fills up to `min(remaining order quantity, public trade quantity)`
at the resting limit price. It does not model queue-ahead volume, matching-engine priority, competing liquidity,
cancel/amend races, hidden liquidity, trade allocation across price levels, network latency, slippage, or actual
fees (dry executions record zero fee). Consequently it can understate equal-price fills and still misstate
trade-through fill quantity/timing. Fill ratio, PnL, markouts, and adverse-selection results are scenario
diagnostics—not production execution forecasts.

Demo liquidity and fills likewise are not evidence of production queue position, latency, or achievable maker
edge. REST create/amend/cancel responses are asynchronous acknowledgements; the private execution stream is the
real-time fill source and REST execution history is only a reconciliation/backfill source.
