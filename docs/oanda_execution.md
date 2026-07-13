# Εκτέλεση μέσω OANDA

Τελευταία ενημέρωση: 2026-07-11

Το `src.execution` εκθέτει broker-agnostic factory και OANDA v20 REST adapter:

```python
from src.execution import create_execution_engine

broker = create_execution_engine(config)
broker.connect()
```

Η OANDA-specific λογική παραμένει στο `src/execution/oanda_execution.py`. Η
δημιουργία adapter δεν αλλάζει features, targets, models, signals ή backtests.

## Practice configuration

Χρησιμοποίησε ως αφετηρία το `config/execution/oanda_practice.yaml`:

```yaml
execution:
  broker: oanda
  oanda:
    environment: practice
    account_id: YOUR_ACCOUNT_ID
    api_token_env: OANDA_API_TOKEN
    request_timeout: 30
    reconnect: true
    max_retry: 5
    min_request_interval: 0.1
```

Το token αποθηκεύεται εκτός YAML:

```bash
export OANDA_API_TOKEN="..."
```

Το `account_id` είναι υποχρεωτικό. Αν λείπει token ή account id, ο adapter
αποτυγχάνει πριν από σύνδεση.

## Symbol mapping

Τα mappings δηλώνονται κάτω από `execution.oanda.symbols`:

```yaml
symbols:
  SPX500:
    oanda_symbol: US500_USD
    enabled: true
  EURUSD:
    oanda_symbol: EUR_USD
    enabled: true
```

Υπάρχουν default mappings για `SPX500`, `US100`, `GER40`, `US30`,
`XAUUSD`, `EURUSD`, `GBPUSD`, `USDJPY` και `BTCUSD`. Το ακριβές διαθέσιμο
instrument set εξαρτάται από τον λογαριασμό OANDA.

## Historical bars

Το `get_historical_bars(symbol, timeframe, count)` επιστρέφει μόνο completed
mid candles με στήλες:

```text
datetime, open, high, low, close, volume
```

Υποστηρίζονται `M1`, `M5`, `M15`, `M30`, `H1`, `H4` και `D1`.

## Διαθέσιμες λειτουργίες adapter

- Account summary, balance, equity και margin.
- Open positions και pending orders.
- Symbol metadata και latest bid/ask.
- Historical candles.
- Market, limit και stop orders.
- Take-profit, stop-loss και trailing-stop attachments.
- Ακύρωση order, κλείσιμο ολόκληρης ή μέρους θέσης.
- Retry για επιτρεπτά transient failures και ξεχωριστά errors για
  authentication, rate limits, connection loss και rejected orders.

Παράδειγμα read-only ανάκτησης:

```python
import yaml

from src.execution import create_execution_engine

with open("config/execution/oanda_practice.yaml", "r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle)

broker = create_execution_engine(config)
broker.connect()
bars = broker.get_historical_bars("EURUSD", "M30", 200)
price = broker.get_latest_price("EURUSD")
```

## Safety boundaries

Το `environment: live` αλλάζει το REST base URL σε live. Ο adapter δεν
μετατρέπει αυτόματα τη στρατηγική σε ασφαλές execution system και δεν εφαρμόζει
από μόνος του το top-level `risk` block. Ο caller είναι υπεύθυνος για signal
timing, position sizing, duplicate-order prevention, exposure limits και kill
switches.

Ξεκίνα μόνο από `practice`. Μην τοποθετείς orders κατά την επαλήθευση
τεκμηρίωσης και μην αποθηκεύεις credentials στο Git.

## Tests

```bash
python -m pytest -q tests/execution/test_oanda_execution.py
```

Τα tests χρησιμοποιούν fake transport και δεν κάνουν live network calls.
