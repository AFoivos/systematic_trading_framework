# systematic-trading-framework

A **research-first, systematic trading framework** for quantitative finance, designed to support the full lifecycle from **hypothesis-driven research** to **robust backtesting**, **machine learning–based strategy evaluation**, and **multi-asset portfolio construction**.

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
* **Persisted data/feature snapshots** for reproducibility (raw + processed dataset versioning)
* **Signal aggregation layer** (rank/decay/confidence-weighted sizing)
* **Portfolio optimization with constraints** (market/sector neutrality, turnover caps)
* **Robustness & strict OOS evaluation** (walk-forward, purged splits, fold-level diagnostics)
* **Monitoring & drift detection** for production-grade iteration
* **Paper execution artifacts** (target weights / rebalance order exports)

---

## 🧱 Repository Structure

```
systematic-trading-framework/
│
├── config/                 # YAML configs (models, experiments, backtests)
│
├── data/
│   ├── raw/                # Persisted raw/canonical snapshots
│   ├── processed/          # Persisted feature snapshots
│   └── metadata/           # Universe snapshots, asset metadata
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
│   ├── monitoring/         # Drift and feature stability diagnostics
│   ├── execution/          # Paper execution order exports
│   ├── src_data/           # Market data loading, PIT hardening, snapshot storage
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

### VSCode Dev Container

For full VSCode integration (Run/Debug, testing, Jupyter, extensions) directly in Docker:

1. Install the VSCode extension **Dev Containers** (`ms-vscode-remote.remote-containers`).
2. Open the project in VSCode.
3. Run: `Dev Containers: Reopen in Container`.

The container uses `.devcontainer/devcontainer.json` and auto-configures:

* Python interpreter: `/usr/local/bin/python`
* Pytest discovery under `tests/`
* Jupyter support
* Essential extensions (Python, Pylance, Debugpy, Jupyter, Docker, YAML)

---

## ⚙️ Config-Based Experiments

Define experiments in YAML under `config/` (e.g., `config/experiments/trend_spy.yaml`). Inherit defaults via `extends: base/daily.yaml`. Load and run:

```python
from src.utils.config import load_experiment_config
cfg = load_experiment_config("experiments/trend_spy.yaml")
# then: load/persist raw snapshots, build features, train model with time-aware splits,
# map signals, optionally construct portfolio weights, run backtest, save artifacts
```

Keep secrets out of Git: store API keys in env vars and reference them with `data.api_key_env`.

Key config blocks now supported:

* `data.symbol` or `data.symbols` for single-asset vs multi-asset runs
* `data.storage` for raw/processed dataset snapshots (`live`, `live_or_cached`, `cached_only`)
* `model.kind` for `lightgbm_clf` and `logistic_regression_clf`
* `portfolio` for signal-based or mean-variance portfolio construction
* `monitoring` for feature drift reports
* `execution` for paper-order export at the latest timestamp

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

Implemented model path today:

* LightGBM classifier with time-aware OOS predictions
* Logistic regression classifier with the same anti-leakage split framework

Planned / future model families:

* ARIMA / SARIMAX
* VAR
* GARCH-style volatility models
* LSTM / temporal CNNs
* RL agents

All implemented models:

* operate on **lagged, causal features**
* are evaluated **out-of-sample**
* are benchmarked against naive baselines
* are trained with **purged / embargoed time-series CV** when labels overlap

---

## 🧪 Evaluation & Backtesting

Evaluation follows strict time-series principles:

* ❌ No random train/test splits
* ✅ Walk-forward / expanding window validation
* ✅ Purged / embargoed split support
* ✅ Explicit transaction costs & slippage
* ✅ Capital-aware performance accounting
* ✅ **Point-in-time alignment** (avoid lookahead & survivorship leakage)
* ✅ **Strict OOS reporting** (fold-level diagnostics + primary OOS summary)
* ✅ Multi-asset portfolio backtests with constraints

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
* data quality & drift monitoring reports
* latest paper-order export for downstream execution workflows

The goal is not just performance, but **understanding**.

---

## 🚧 Disclaimer

This repository is intended **solely for research and educational purposes**.

It does **not** constitute financial advice and is **not** designed for live trading without extensive validation, monitoring, and compliance considerations.

---

## 📌 Future Extensions

* Broker / OMS adapters for real live execution
* Advanced regime detection
* Model ensemble & meta-learning
* Alternative data/NLP pipeline (news, filings, embeddings)
* Richer feature lineage / catalog metadata
* Production monitoring dashboards & alerting

---

## 📄 License

This project is licensed under the MIT License.
Copyright (c) 2026 FOIVOS GEORGIOS AMPATZIS.

See `/Users/foivosampatzis/Projects/personal/systematic_trading_framework/LICENSE` for details.

---

## 👤 Author

Quantitative Research & Machine Learning Engineer
Focus areas: systematic trading, time-series modeling, and ML-driven alpha research.
