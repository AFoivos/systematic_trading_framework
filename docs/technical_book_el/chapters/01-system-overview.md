## 1. Επισκόπηση Συστήματος

### 1.1 Σκοπός Project

Το framework στοχεύει να υποστηρίξει ολόκληρο τον κύκλο quantitative research για systematic trading:
συλλογή market data, point-in-time hardening, feature engineering, supervised model training με
χρονοσειριακά σωστά splits, μετατροπή predictions σε signals, κατασκευή χαρτοφυλακίου, cost-aware
backtesting, reproducibility metadata και παραγωγή execution-ready paper orders. Η αρχιτεκτονική είναι
σχεδιασμένη ώστε να υποστηρίζει μετάβαση από research σε production-like experimentation χωρίς να
αναμιγνύονται concerns.

### 1.2 Επιχειρησιακή Λογική

Η βασική επιχειρησιακή λογική είναι η εξής:

1. Η αγορά παράγει χρονοσειρές τιμών και όγκων.
2. Το σύστημα τις μετασχηματίζει σε αυστηρά causal features.
3. Ένας classifier εκτιμά την πιθανότητα θετικής forward απόδοσης σε δεδομένο horizon.
4. Ο probability output χαρτογραφείται σε signal, δυαδικό ή conviction-weighted.
5. Το signal περνά από risk/backtest ή portfolio layer για να αποτιμηθεί με costs, leverage και constraints.
6. Τα αποτελέσματα συνοδεύονται από metrics, drift diagnostics, artifact manifests και execution outputs.

### 1.3 Target Users

- Quant researchers που θέλουν reproducible πειράματα με anti-leakage discipline.
- ML engineers που χρειάζονται config-driven training/evaluation πάνω σε financial time series.
- Portfolio engineers που θέλουν constrained weight construction και portfolio PnL accounting.
- Technical leads / software architects που κάνουν onboarding ή code review σε quant systems.

### 1.4 Τι Υλοποιείται Σήμερα και Τι Όχι

Υλοποιούνται σήμερα:

- Yahoo/Alpha Vantage ingestion.
- PIT timestamp alignment και corporate action handling.
- Feature engineering για returns, lags, volatility, trend, momentum, oscillators, indicators.
- LightGBM και Logistic Regression classification με OOS predictions.
- Single-asset και multi-asset portfolio backtesting.
- Monitoring PSI drift reports.
- Paper rebalancing order generation.
- Artifact persistence και reproducibility metadata.

Δεν υλοποιούνται ακόμη στον παρόντα κώδικα, παρότι αναφέρονται στο README ως κατευθύνσεις:

- ARIMA/SARIMAX/VAR/GARCH production models.
- LSTM/temporal CNN training loops.
- RL environments, policies και reward functions σε executable form.
- Live broker adapters / OMS integration.
