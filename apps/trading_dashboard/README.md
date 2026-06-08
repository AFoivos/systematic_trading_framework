# Trading Research Dashboard

Local-first FastAPI + React dashboard for inspecting market data, engineered features, signals, targets, predictions, trades, and experiment artifacts from this repository.

## What It Reads

- CSV/parquet datasets anywhere under `data/**`, grouped in the UI by folder path
- Experiment runs under `logs/experiments` and bot run artifacts under `logs/bot`
- Trade overlays from `report_assets/trades.csv` or `trade_events.csv`
- Equity curves from `equity_curve.csv`
- Saved dashboard layouts under `apps/trading_dashboard/layouts`

## Backend

```bash
cd apps/trading_dashboard/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Optional path override:

```bash
TRADING_DASHBOARD_PROJECT_ROOT=/path/to/systematic_trading_framework uvicorn app.main:app --reload
```

## Frontend

```bash
cd apps/trading_dashboard/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

Set a custom backend URL if needed:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## Docker

The Dockerized dashboard serves the built React app from the FastAPI container, so the UI stays available for as long as the container is running.

From the repository root:

```bash
docker compose up --build trading-dashboard
```

Open `http://127.0.0.1:8000`.

Notes:

- The container serves both the API and the frontend on port `8000`.
- Local `data/`, `logs/`, and `apps/trading_dashboard/layouts/` are mounted into the container, so new datasets, experiment outputs, and saved layouts remain visible without rebuilding.
- Stop it with `docker compose stop trading-dashboard` or remove it with `docker compose down`.

## Example API Calls

```bash
curl http://127.0.0.1:8000/api/datasets
curl "http://127.0.0.1:8000/api/ohlcv?dataset_id=data/raw/dukascopy_30m_clean/xauusd_30m.csv&start=2024-01-01&end=2024-02-01"
curl "http://127.0.0.1:8000/api/features/catalog?dataset_id=data/raw/dukascopy_30m_clean/xauusd_30m.csv"
curl http://127.0.0.1:8000/api/features/builders
curl http://127.0.0.1:8000/api/signals/builders
curl http://127.0.0.1:8000/api/targets/builders
curl http://127.0.0.1:8000/api/experiments
```

Parameterized preview example:

```bash
curl -X POST http://127.0.0.1:8000/api/transform/series \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "data/raw/dukascopy_30m_clean/xauusd_30m.csv",
    "limit": 5000,
    "features": [
      {"step": "trend", "params": {"price_col": "close", "sma_windows": [20, 50], "ema_spans": [20]}, "enabled": true},
      {"step": "rsi", "params": {"price_col": "close", "windows": [14]}, "enabled": true}
    ],
    "signals": [],
    "targets": [
      {"step": "forward_return", "params": {"price_col": "close", "horizon": 4, "threshold": 0.0}, "enabled": true}
    ]
  }'
```

## Example Layout JSON

```json
{
  "name": "xauusd-m30-research",
  "selection": {
    "datasetId": "data/raw/dukascopy_30m_clean/xauusd_30m.csv",
    "start": "2024-01-01",
    "end": "2024-06-01",
    "runId": "01_xauusd_roc_long_only_xgboost_r_multiple_filter_BEST"
  },
  "series": [
    {
      "series_id": "ema_20",
      "source_type": "feature",
      "display_name": "EMA 20",
      "chart_target": "main_price_chart",
      "panel_id": null,
      "render_type": "line",
      "y_axis": "right",
      "visible": true,
      "style": {
        "color": "#0f766e",
        "lineWidth": 2
      }
    },
    {
      "series_id": "rsi_14",
      "source_type": "feature",
      "display_name": "RSI 14",
      "chart_target": "lower_panel",
      "panel_id": "oscillators",
      "render_type": "line",
      "y_axis": "right",
      "visible": true,
      "style": {
        "color": "#d97706",
        "lineWidth": 2
      }
    }
  ],
  "transformations": {
    "features": [
      {
        "step": "trend",
        "params": {
          "price_col": "close",
          "sma_windows": [20, 50],
          "ema_spans": [20],
          "inplace": false
        },
        "enabled": true
      }
    ],
    "signals": [],
    "targets": [
      {
        "step": "forward_return",
        "params": {
          "price_col": "close",
          "horizon": 4,
          "threshold": 0.0
        },
        "enabled": true
      }
    ]
  },
  "panels": {}
}
```

## Notes

- The API is read-only for research artifacts except `POST /api/layouts`, which writes layout JSON under this app directory.
- Parameterized feature/signal/target runs are in-memory previews. They do not update datasets, experiment configs, or logged artifacts.
- The first MVP uses folder path, filename, metadata, and column-name inference where this repo does not yet expose a dashboard-specific manifest.
- See `docs/trading_dashboard_assumptions.md` for the explicit assumptions.
