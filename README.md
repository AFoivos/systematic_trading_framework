# systematic-trading-framework

A **research-first, systematic trading framework** for quantitative finance, designed to support the full lifecycle from **hypothesis-driven research** to **robust backtesting** and **machine learning–based strategy evaluation**.

This repository prioritizes:

* statistical rigor,
* reproducibility,
* time-aware evaluation,
* and risk-aware modeling.

It is explicitly **not** a collection of ad-hoc trading strategies or heuristic-driven bots.

---

## 🎯 Project Philosophy

Financial markets are **non-stationary, noisy, and regime-dependent**.
Any serious quantitative system must therefore:

1. Respect the **temporal structure** of data
2. Avoid information leakage at all costs
3. Separate **research**, **evaluation**, and **execution logic**
4. Treat **risk management** as a first-class component
5. Benchmark all models against **simple, interpretable baselines**

This framework is built around those principles.

---

## 🧠 Core Objectives

* Systematic **alpha research** and feature experimentation
* Time-series–aware **backtesting & evaluation**
* Comparison of:

  * statistical models
  * machine learning models
  * deep learning architectures
  * reinforcement learning agents
* Explicit **risk modeling and control**
* Modular, extensible architecture suitable for research → production transition
* **Point-in-time data integrity** (survivorship-bias control, corporate actions, timestamp alignment)
* **Feature store & provenance** for reproducibility (data/feature versioning)
* **Signal aggregation layer** (rank/decay/confidence-weighted sizing)
* **Portfolio optimization with constraints** (market/sector neutrality, turnover caps)
* **Robustness & stress testing** (regime splits, sensitivity checks)
* **Monitoring & drift detection** for production-grade iteration

---

## 🧱 Repository Structure

```
quant-research-lab/
│
├── config/                 # YAML configs (models, experiments, backtests)
│
├── data/
│   ├── raw/                # Immutable raw market data
│   ├── processed/          # Cleaned & feature-engineered datasets
│   └── metadata/           # Contracts, calendars, asset info
│
├── notebooks/              # Exploratory research (EDA, diagnostics)
│
├── src/
│   ├── features/           # Feature engineering (lags, rolling stats, regimes)
│   ├── models/             # Statistical, ML, DL, RL models
│   ├── backtesting/        # Time-aware backtesting engine
│   ├── risk/               # Position sizing, exposure control, costs
│   ├── evaluation/         # Metrics & performance analysis
│   ├── signals/            # Signal aggregation (rank/decay/confidence)
│   ├── portfolio/          # Portfolio construction & optimization
│   ├── monitoring/         # Drift, data quality, and live diagnostics
│   └── utils/              # Shared utilities
│
├── tests/                  # Unit & integration tests
│
├── logs/                   # Experiment & backtest logs
│
└── README.md
```

---

## 🐳 Docker Workflow (No `venv`)

Use Docker/Compose to run everything inside a containerized Python environment.

Build the image:

```bash
docker compose build
```

Run an interactive shell:

```bash
docker compose run --rm app
```

Run tests:

```bash
docker compose run --rm app pytest
```

Run an experiment:

```bash
docker compose run --rm app python -m src.experiments.runner config/experiments/trend_spy.yaml
```

Notes:

* Source code is mounted into `/workspace`, so local edits are visible immediately in the container.
* You can keep API keys in a local `.env` file (already git-ignored) and pass them to Compose with:

```bash
docker compose --env-file .env run --rm app <command>
```

---

## ⚙️ Config-Based Experiments

Define experiments in YAML under `config/` (e.g., `config/experiments/trend_spy.yaml`). Inherit defaults via `extends: base/daily.yaml`. Load and run:

```python
from src.utils.config import load_experiment_config
cfg = load_experiment_config("experiments/trend_spy.yaml")
# then: load_ohlcv(**cfg["data"]), build features per cfg["features"], train model, map signals, run_backtest(...)
```

Keep secrets out of Git: store API keys in env vars and reference them with `data.api_key_env`.

---

## 📐 Modeling Approach

The framework supports and compares multiple modeling paradigms:

### Statistical Models

* ARIMA / SARIMAX
* VAR
* GARCH-style volatility models

### Machine Learning

* Linear & regularized models
* Tree-based models (e.g. gradient boosting)
* Feature importance & explainability analysis

### Deep Learning

* LSTM / temporal CNNs
* Sequence-to-signal architectures
* Strict walk-forward training loops

### Reinforcement Learning

* Custom trading environments
* Risk-aware reward functions
* Policy evaluation under transaction costs

All models:

* operate on **lagged, causal features**
* are evaluated **out-of-sample**
* are benchmarked against naive baselines
* are trained with **purged / embargoed time-series CV** when labels overlap

---

## 🧪 Evaluation & Backtesting

Evaluation follows strict time-series principles:

* ❌ No random train/test splits
* ✅ Walk-forward / expanding window validation
* ✅ Explicit transaction costs & slippage
* ✅ Capital-aware performance accounting
* ✅ **Point-in-time alignment** (avoid lookahead & survivorship leakage)
* ✅ **Robustness checks** (regime splits, sensitivity analysis)

### Key Metrics

* Cumulative & annualized returns
* Sharpe / Sortino ratios
* Maximum drawdown
* Profit factor
* Turnover & stability diagnostics

---

## 🛡️ Risk Management

Risk is modeled explicitly via:

* position sizing rules
* volatility scaling
* exposure limits
* drawdown-aware constraints
* liquidity-aware cost/impact models

In RL settings, **risk-adjusted reward functions** are used instead of raw returns.

---

## 🔍 Explainability & Diagnostics

Where applicable, the framework includes:

* feature importance analysis
* regime-conditional performance
* failure mode diagnostics
* model vs baseline attribution
* data quality & drift monitoring hooks

The goal is not just performance, but **understanding**.

---

## 🚧 Disclaimer

This repository is intended **solely for research and educational purposes**.

It does **not** constitute financial advice and is **not** designed for live trading without extensive validation, monitoring, and compliance considerations.

---

## 📌 Future Extensions

* Live data ingestion layer
* Paper trading & execution simulation
* Portfolio-level optimization
* Advanced regime detection
* Model ensemble & meta-learning
* Alternative data/NLP pipeline (news, filings, embeddings)
* Feature store with data/feature lineage
* Production monitoring & alerting (drift, performance decay)

---

## 👤 Author

Quantitative Research & Machine Learning Engineer
Focus areas: systematic trading, time-series modeling, and ML-driven alpha research.
