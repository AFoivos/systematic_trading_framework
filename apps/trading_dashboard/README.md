# Dashboard έρευνας trading

Το `apps/trading_dashboard` είναι ένα τοπικό dashboard FastAPI και React για
επιθεώρηση δεδομένων αγοράς, χαρακτηριστικών, σημάτων, targets, προβλέψεων,
συναλλαγών και artifacts πειραμάτων. Δεν εκτελεί το experiment pipeline και δεν
τροποποιεί datasets ή YAML configs.

## Δεδομένα που διαβάζει

- Αρχεία CSV και Parquet κάτω από `data/**`.
- Runs κάτω από `logs/experiments/**` και `logs/bot/**`.
- Συναλλαγές από `report_assets/trades.csv` ή `trade_events.csv`.
- Καμπύλες κεφαλαίου από `equity_curve.csv`.
- Αποθηκευμένες διατάξεις από `apps/trading_dashboard/layouts/`.

Η ανακάλυψη βασίζεται σε paths, metadata και ονόματα στηλών. Οι ακριβείς
συμβάσεις περιγράφονται στις
[τεχνικές παραδοχές](../../docs/trading_dashboard_assumptions.md).

## Εκκίνηση backend

Από το repository root:

```bash
cd apps/trading_dashboard/backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Σε PowerShell, η ενεργοποίηση του περιβάλλοντος είναι:

```powershell
.\.venv\Scripts\Activate.ps1
```

Αν το repository root δεν μπορεί να εξαχθεί από τη θέση του package:

```bash
TRADING_DASHBOARD_PROJECT_ROOT=/path/to/systematic_trading_framework \
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Εκκίνηση frontend

```bash
cd apps/trading_dashboard/frontend
npm install
npm run dev
```

Η τοπική διεπαφή είναι διαθέσιμη στο `http://127.0.0.1:5173`. Για διαφορετικό
backend:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## Εκκίνηση με Docker

Η Docker εικόνα σερβίρει το έτοιμο React bundle από το FastAPI container:

```bash
docker compose up -d --build trading-dashboard
```

Η διεπαφή και το API είναι διαθέσιμα στο `http://127.0.0.1:8000`. Τα τοπικά
`data/`, `logs/` και `apps/trading_dashboard/layouts/` προσαρτώνται ως volumes,
οπότε νέα artifacts γίνονται ορατά χωρίς rebuild.

```bash
docker compose logs -f trading-dashboard
docker compose stop trading-dashboard
```

## Βασικά API endpoints

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/datasets
curl http://127.0.0.1:8000/api/assets
curl http://127.0.0.1:8000/api/features/builders
curl http://127.0.0.1:8000/api/signals/builders
curl http://127.0.0.1:8000/api/targets/builders
curl http://127.0.0.1:8000/api/experiments
curl http://127.0.0.1:8000/api/layouts
```

Παράδειγμα χρονικού φίλτρου:

```bash
curl "http://127.0.0.1:8000/api/ohlcv?dataset_id=data/raw/dukascopy_30m_clean/xauusd_30m.csv&start=2024-01-01&end=2024-02-01"
```

Το `start` είναι συμπεριληπτικό και το `end` αποκλειστικό.

## Προεπισκόπηση builders

Το `POST /api/transform/series` εφαρμόζει επιλεγμένους builders σε αντίγραφο
του dataset στη μνήμη:

```bash
curl -X POST http://127.0.0.1:8000/api/transform/series \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "data/raw/dukascopy_30m_clean/xauusd_30m.csv",
    "limit": 5000,
    "features": [
      {
        "step": "trend",
        "params": {
          "price_col": "close",
          "sma_windows": [20, 50],
          "ema_spans": [20]
        },
        "enabled": true
      }
    ],
    "signals": [],
    "targets": [],
    "models": []
  }'
```

Οι previews δεν γράφουν computed columns πίσω στο dataset. Αν προστεθεί target,
η μελλοντική πληροφορία χρησιμοποιείται μόνο για οπτική έρευνα/label
construction και δεν επιτρέπεται να ερμηνευθεί ως διαθέσιμο live feature.

## Αποθήκευση διατάξεων

Το `POST /api/layouts` είναι το μόνο endpoint που γράφει αρχείο. Αποθηκεύει JSON
κάτω από `apps/trading_dashboard/layouts/`. Η διάταξη περιέχει επιλογές και
ρυθμίσεις απεικόνισης, όχι αντίγραφο δεδομένων αγοράς.

## Έλεγχοι

```bash
python -m pytest -q apps/trading_dashboard/backend/app_tests
```

Οι βασικές πηγές αλήθειας είναι τα `backend/app/api/routes_*.py`, οι services
κάτω από `backend/app/services/` και τα παραπάνω tests.
