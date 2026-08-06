# cTrader Model06 local bridge

This integration keeps the trained LightGBM model and the complete feature pipeline in the normal Python repository environment. A thin C# cBot sends **closed M30 bars** to a localhost HTTP service and executes only the returned target signal.

## Locked strategy contract

- Symbol: `ETHUSD`
- Timeframe: `M30`
- Model: `model_06_vwap_plus_robust_z.pkl`
- Feature order: 48 columns from the model manifest
- Forecast thresholds: `+0.70 / -0.85`
- Activation filters: loaded directly from the experiment YAML
- Long and short positions
- Minimum 24 bars between position changes
- Target notional exposure: 60%
- Maximum one strategy position
- Daily equity loss stop: 1.5%
- Peak-to-current drawdown stop: 7.5%
- Fail closed: HTTP/model/schema/stale-bar errors never open a new order

## 1. Start the Python service on macOS

From the repository root:

```bash
python3 -m venv .venv-ctrader
source .venv-ctrader/bin/activate
python -m pip install --upgrade pip
python -m pip install -r integrations/ctrader_model06/requirements-macos.txt
export MODEL06_API_TOKEN='replace-with-a-random-local-token'
python integrations/ctrader_model06/service.py   --config integrations/ctrader_model06/service_config.yaml
```

Expected startup output contains `service_started`, the model SHA-256 and `feature_count: 48`.

Health check:

```bash
curl -H "X-Model06-Token: $MODEL06_API_TOKEN" http://127.0.0.1:8765/health
```

Model contract:

```bash
curl -H "X-Model06-Token: $MODEL06_API_TOKEN" http://127.0.0.1:8765/model-info
```

Historical smoke test (staleness bypass is allowed only when the environment variable is explicitly set):

```bash
export MODEL06_ALLOW_STALE=1
python integrations/ctrader_model06/smoke_test.py   --csv data/raw/dukascopy_30m_clean/ethusd_30m.csv   --token "$MODEL06_API_TOKEN"
```

## 2. Create the cBot

In cTrader Algo create a new **C# cBot**, then replace its source with:

`integrations/ctrader_model06/cbot/Model06ThinBridge.cs`

Build it and create one local instance with:

- FTMO demo account
- the broker's ETHUSD symbol
- timeframe `m30`
- `Inference URL`: `http://127.0.0.1:8765/predict`
- `API token`: same value as `MODEL06_API_TOKEN`
- `Enable demo orders`: **false** initially

The cBot uses cTrader network access with `AccessRights.None`, closed-bar events, volume normalization and local storage for restart-safe state. cTrader's official API supports these operations.

## 3. Dry-run sequence

1. Start the Python service.
2. Start the cBot with `Enable demo orders = false`.
3. Confirm `/health` succeeds in cBot logs.
4. At the next M30 close, verify prediction, bar timestamp, filters and signal.
5. Compare the service response against a repository prediction for the same bars.
6. Keep dry-run enabled until at least 20 closed-bar responses have exact timestamp and signal parity.

## 4. Demo orders

After parity is confirmed, set `Enable demo orders = true` on a demo account only.

The cBot calculates approximate 60% notional exposure as:

```text
equity × 0.60 ÷ ETHUSD mid-price
```

and normalizes it to the symbol's tradable volume step. Broker contract specifications must be checked before enabling orders. On a CFD where one volume unit is not one ETH base unit, this conversion must be adapted before trading.

## Logs

Python service logs:

```text
logs/ctrader_model06_service/http.jsonl
logs/ctrader_model06_service/predictions.jsonl
logs/ctrader_model06_service/rejections.jsonl
logs/ctrader_model06_service/errors.jsonl
```

cBot execution and risk events are written to the cTrader instance Logs tab. Runtime state is persisted with cTrader `LocalStorage`.

## Safety notes

- Keep the service bound to `127.0.0.1`.
- Use a non-empty API token.
- Do not expose port 8765 to the network.
- The cBot refuses stale or mismatched responses.
- The cBot closes its labeled position when daily or total equity limits are breached.
- The first phase is demo-only; this integration is not approved for a funded account.
