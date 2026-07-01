# OANDA Execution

This framework now exposes a broker-agnostic execution interface through:

```python
from src.execution import create_execution_engine

broker = create_execution_engine(config)
broker.connect()
```

The OANDA implementation uses the v20 REST API and keeps broker-specific logic inside `src/execution`.
Signals, features, models, targets, experiments, and backtesting are unchanged.

## Practice Account

1. Create an OANDA demo/practice account from OANDA's account portal.
2. Open the OANDA developer/API token page for that account.
3. Generate a personal access token.
4. Store it outside YAML:

```bash
export OANDA_API_TOKEN="..."
```

## Configuration

Use `config/execution/oanda_practice.yaml` as a starting point:

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
```

For live trading, set:

```yaml
execution:
  broker: oanda
  oanda:
    environment: live
```

Keep `api_token_env` preferred over inline `api_token` so secrets do not enter versioned configs.

## Symbol Mapping

Mappings are configurable under `execution.oanda.symbols`.

```yaml
symbols:
  SPX500:
    oanda_symbol: US500_USD
    enabled: true
  EURUSD:
    oanda_symbol: EUR_USD
    enabled: true
```

Default mappings are provided for `SPX500`, `US100`, `GER40`, `US30`, `XAUUSD`, `EURUSD`, `GBPUSD`, `USDJPY`, and `BTCUSD`.

## Historical Bars

`get_historical_bars(symbol, timeframe, count)` returns:

```text
datetime, open, high, low, close, volume
```

Supported framework timeframes are `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, and `D1`.

## Example Bot Skeleton

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

Order methods support market, limit, stop, take-profit, stop-loss, trailing-stop, full close, and partial close.
Use practice first and keep strategy/risk orchestration explicit around the broker adapter.
