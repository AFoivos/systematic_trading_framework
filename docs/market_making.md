# Crypto Market Making Subsystem

Το market making subsystem είναι ξεχωριστό από το υπάρχον candle-based framework.
Το candle pipeline παραμένει:

```text
OHLCV candles -> features -> signals/models -> backtesting -> execution
```

Το market making pipeline είναι event-driven:

```text
order book / trades / ticks -> fair price -> bid/ask quotes -> risk gate -> paper/demo execution -> fills -> inventory/PnL/monitoring
```

## Γιατί δεν μπαίνει στον candle backtester

Market making αποφάσεις παίρνονται σε order-book χρόνο, όχι σε bar close χρόνο. Το fill logic εξαρτάται από top-of-book, spread, aggressive trades, stale feeds, latency, open order state και inventory. Αν αυτά μπουν πρόχειρα στον candle backtester, δημιουργούνται μη ρεαλιστικά fills και κίνδυνος lookahead. Για αυτό το νέο subsystem μπαίνει δίπλα στο υπάρχον framework, με δικά του modules κάτω από `src/market_data`, `src/market_making`, `src/venues` και `src/simulation`.

## Order book

Το `LocalOrderBook` κρατά level-2 bids/asks, δέχεται snapshot και incremental updates, αφαιρεί μηδενικές ή αρνητικές ποσότητες, ελέγχει ότι `best_bid < best_ask`, και εκθέτει:

- `best_bid`
- `best_ask`
- `mid_price`
- `spread`
- `spread_bps`
- depth σε N levels
- order book imbalance
- timestamp και sequence, όταν παρέχεται

## Fair price

Η πρώτη έκδοση υποστηρίζει:

- `mid_price`: απλό midpoint.
- `microprice`: top-of-book price weighted by opposite-side available volume.

## Spread model

Το spread model επιστρέφει bounded quote spread σε bps. Υποστηρίζει:

- fixed spread
- volatility-adjusted spread
- fee-aware spread

Τα bounds `min_spread_bps` και `max_spread_bps` εφαρμόζονται πάντα.

## Inventory skew

Το inventory skew μετακινεί τα quotes με βάση normalized inventory ratio:

- Αν inventory > 0, τα quotes μετακινούνται χαμηλότερα ώστε η πώληση να γίνει ευκολότερη και η αγορά δυσκολότερη.
- Αν inventory < 0, τα quotes μετακινούνται υψηλότερα ώστε η αγορά να γίνει ευκολότερη και η πώληση δυσκολότερη.

Το `max_inventory` ορίζει το όριο normalization.

## Adverse selection

Το `AdverseSelectionFilter` μπορεί να σταματήσει ή να ανοίξει quotes όταν υπάρχουν:

- extreme order book imbalance
- high recent volatility
- one-sided aggressive trade flow
- strong trend regime μέσω interface `TrendRegimeProvider`

Η σύνδεση με τα υπάρχοντα candle/regime features δεν γίνεται ακόμη αυτόματα. Υπάρχει interface ώστε να μπει χωρίς να μπερδευτεί το candle pipeline με το event-driven engine.

## Risk και kill switch

Το `RiskEngine` είναι κεντρικό gate. Καμία paper/demo εντολή δεν πρέπει να περνά χωρίς `check_quote`. Καλύπτει:

- max inventory
- max position value
- max daily loss
- max open orders
- max order size
- websocket disconnect
- stale order book
- extreme spread
- kill switch με cancel-all intent

## Modes

### Data-only mode

Δεν στέλνει καμία εντολή. Το τρέχεις με:

```bash
python scripts/collect_kraken_orderbook.py --config config/execution/kraken_futures_demo_market_making.yaml
```

Για καθαρό data-only run, βάλε στο YAML:

```yaml
execution:
  mode: data_only
```

Η πρώτη έκδοση γράφει ασφαλές scaffold event CSV και αφήνει το persistent Kraken public websocket collector ως explicit TODO.

### Paper mode

Τρέχει deterministic paper market making χωρίς API calls:

```bash
python scripts/run_market_making_paper.py --config config/execution/kraken_futures_demo_market_making.yaml --duration-seconds 3600
```

Παράγει:

- `logs/experiments/market_making/summary.json`
- `logs/experiments/market_making/trades.csv`
- `logs/experiments/market_making/orders.csv`
- `logs/experiments/market_making/quote_events.csv`
- `logs/experiments/market_making/pnl_timeseries.csv`
- `logs/experiments/market_making/inventory_timeseries.csv`

Το fill model είναι conservative:

- buy limit γεμίζει αν trade price <= bid order price
- sell limit γεμίζει αν trade price >= ask order price
- fees εφαρμόζονται από config

## Diagnostics

Κάθε paper run μπορεί να παράγει local-first diagnostics κάτω από:

```text
logs/experiments/market_making/diagnostics/
```

Χειροκίνητη ανάλυση υπάρχοντος run:

```bash
python scripts/analyze_market_making_run.py --run-dir logs/experiments/market_making
```

Docker-first:

```bash
docker compose run --rm app python scripts/analyze_market_making_run.py \
  --run-dir logs/experiments/market_making \
  --max-inventory 0.01 \
  --language el
```

Αν υπάρχει ξεχωριστό collector file:

```bash
python scripts/analyze_market_making_run.py \
  --run-dir logs/experiments/market_making \
  --orderbook-events logs/experiments/market_making/orderbook_events.csv \
  --max-inventory 0.01
```

Ανάλυση πιο πρόσφατου run:

```bash
python scripts/analyze_market_making_run.py --latest --reports-root logs/experiments
```

Ανάλυση όλων των runs και comparison report:

```bash
python scripts/analyze_market_making_run.py --all --reports-root logs/experiments
```

Timestamped Kraken CSV paper replay:

```bash
docker compose run --rm app python scripts/run_market_making_paper.py \
  --config config/execution/kraken_futures_demo_market_making.yaml \
  --input-events logs/experiments/market_making/orderbook_events.csv \
  --timestamped-output
```

Με `--timestamped-output`, το run γράφεται σε:

```text
logs/experiments/market_making/runs/YYYYMMDD_HHMMSS_<data_source>_<fill_model>
```

Με explicit output directory:

```bash
python scripts/run_market_making_paper.py \
  --config config/execution/kraken_futures_demo_market_making.yaml \
  --input-events logs/experiments/market_making/orderbook_events.csv \
  --output-dir logs/experiments/market_making/runs/my_replay
```

Generated files:

- `diagnostics/summary.json`
- `diagnostics/gaps.json`
- `diagnostics/report.md`
- `diagnostics/quote_diagnostics.csv`
- `diagnostics/fill_diagnostics.csv`
- `diagnostics/pnl_attribution.csv`
- `diagnostics/inventory_diagnostics.csv`
- `diagnostics/market_quality.csv`
- `diagnostics/risk_diagnostics.csv`
- `diagnostics/markout_diagnostics.csv`
- PNG plots για PnL, drawdown, inventory, spreads, markout, event funnel και risk reasons όταν υπάρχουν τα αντίστοιχα δεδομένα.

Interpretation:

- Fill ratio: μετρά πόσα virtual fills πήρε το paper engine σε σχέση με quotes/orders. Πολύ χαμηλό fill ratio συνήθως σημαίνει quote placement πολύ μακριά από top-of-book ή υπερβολικά συντηρητικό fill model.
- `fill_ratio`: backward-compatible alias του `fills_per_order`.
- `fills_per_quote_attempt`: fills / όλα τα quote attempts, συμπεριλαμβανομένων rejects/skips.
- `fills_per_placed_quote`: fills / placed quote decisions.
- `fills_per_order`: fills / virtual orders που δημιουργήθηκαν.
- `fills_per_input_event`: fills / input order-book events.
- Quote/order/fill lineage: το `quote_event_id` συνδέει quote events με generated orders μέσω `parent_quote_event_id`, και τα fills κληρονομούν το ίδιο `parent_quote_event_id`. Χωρίς lineage, fill-to-quote attribution και PnL attribution παραμένουν approximate.
- Markout: μετρά αν η τιμή μετά το fill κινήθηκε υπέρ ή κατά του bot. Αρνητικό markout σημαίνει adverse selection.
- Buy markout sign: για buy fill, θετικό markout σημαίνει ότι το future mid ανέβηκε πάνω από την fill price.
- Sell markout sign: για sell fill, θετικό markout σημαίνει ότι το future mid έπεσε κάτω από την fill price.
- Adverse selection rate: ποσοστό fills με αρνητικό markout. Δεν είναι αξιόπιστο όταν τα fills είναι λίγα.
- Inventory utilization: δείχνει πόσο συχνά το inventory πλησιάζει το `max_inventory`. Υψηλή χρήση θέλει αυστηρότερο skew/risk ή μικρότερα order sizes.

Known limitations:

- Δεν υπάρχει ακόμη queue-position model.
- Δεν υπάρχει ακόμη partial-fill model.
- Δεν υπάρχει ακόμη latency-aware fill model.
- Το markout απαιτεί διαθέσιμα `orderbook_events.csv`.
- Το PnL attribution είναι approximate εκτός αν υπάρχει πλήρης quote/order/fill linkage.
- Τα paper replay fills δεν είναι ακόμη venue-realistic, γιατί δεν υπάρχει queue position, partial fills ή latency-aware matching.
- Τα diagnostics είναι JSON/CSV/Markdown-first. Δεν παράγονται legacy PowerPoint decks.

### MOMENT research experiment

`config/experiments/market_making/market_making_moment.yaml` defines a research-only experiment that evaluates
MOMENT-style time-series features as a final quote filter. It does not place live or demo orders.
The runner consumes local order-book and quote-event CSVs, builds a quote-level dataset, applies a
chronological split, scores buy and sell quote candidates separately, and compares the current
baseline strategy against the MOMENT-filtered variant on the same events:

```bash
python scripts/run_market_making_moment_experiment.py \
  --config config/experiments/market_making/market_making_moment.yaml
```

The objective is not standalone price forecasting. The objective is reducing toxic fills and
improving fee-adjusted markout after maker fees and safety buffers. MOMENT is a general pretrained
time-series model, not a market-making- or stock-market-specialized model; it must be evaluated and,
when enabled, fine-tuned on local order-book data before any operational use.

Outputs are written under `logs/experiments/market_making/market_making_moment_<timestamp>_<hash>/` and follow the
classic experiment artifact style:

- `summary.json`
- `run_metadata.json`
- `artifact_manifest.json`
- `config_used.yaml`
- `returns.csv`, `equity_curve.csv`, `gross_returns.csv`, `costs.csv`, `turnover.csv`, `positions.csv`
- `trades.csv`, `quote_decisions.csv`, `moment_predictions.csv`
- `moment_dataset.parquet`
- `baseline_vs_moment.csv` and `baseline_vs_moment.json`
- optional `report.md`

The pipeline is JSON/CSV/Markdown/Parquet-only. It does not generate HTML or PowerPoint artifacts.
Production, demo, and live use remains disabled until queue-position, latency, and partial-fill
modeling are implemented and validated.

### Kraken Futures demo mode

Το demo mode απαιτεί:

```yaml
execution:
  mode: kraken_futures_demo
  allow_demo_orders: true
```

και environment variables:

```bash
export KRAKEN_FUTURES_API_KEY=...
export KRAKEN_FUTURES_API_SECRET=...
python scripts/run_kraken_futures_demo_mm.py --config config/execution/kraken_futures_demo_market_making.yaml
```

Η πρώτη έκδοση κάνει safe adapter validation και subscription scaffold. Η signed REST order placement υλοποίηση δεν έχει συνδεθεί ακόμη.

### Live mode

Live trading δεν έχει υλοποιηθεί. Αν ζητηθεί `mode: live`, ο adapter σηκώνει:

```text
Live trading is intentionally disabled.
```

## Τι δεν έχει υλοποιηθεί ακόμη

- Persistent Kraken Futures public websocket collector.
- Signed Kraken Futures Demo REST order placement/cancel.
- Partial fills και queue-position model.
- Latency-aware fill simulation.
- Αυτόματη σύνδεση με υπάρχοντα candle-based trend regime features.
- Πραγματικό live trading.

Πριν μπει οποιοδήποτε πραγματικό live trading χρειάζονται integration tests σε demo venue, idempotent order state reconciliation, retry/backoff policy, strict secrets handling, exchange-specific tick/lot metadata validation και independent kill-switch dry runs.
