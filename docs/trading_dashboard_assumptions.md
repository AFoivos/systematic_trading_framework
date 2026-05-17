# Trading Dashboard Assumptions

This MVP is intentionally additive and local-first. It does not import, modify, or execute the existing experiment pipeline.

## Repository Discovery

- Raw OHLCV datasets are discovered under `data/raw/**/*.csv` and `data/raw/**/*.parquet`.
- Processed framework snapshots are discovered under `data/processed/**/dataset.csv` and `data/processed/**/dataset.parquet`.
- Experiment runs are discovered under `logs/experiments/**` when a directory contains one of:
  - `run_metadata.json`
  - `summary.json`
  - `artifact_manifest.json`
  - `study_summary.json`
- Existing artifact manifests may contain container paths beginning with `/workspace`; the dashboard maps those back to the local repository root when possible.

## Asset and Timeframe Inference

- Raw single-asset CSVs infer asset and timeframe from filenames such as:
  - `xauusd_h1.csv` -> `XAUUSD`, `H1`
  - `xauusd_30m.csv` -> `XAUUSD`, `M30`
  - `XAUUSD_M5_bid.csv` -> `XAUUSD`, `M5`
- Processed snapshot assets are read from adjacent `metadata.json` when available.
- Processed snapshot timeframe is read from metadata context if present; otherwise it falls back to filename or directory inference.

## Date Filtering

- API `start` is inclusive.
- API `end` is exclusive, matching the existing storage loader behavior in `src/src_data/storage.py`.

## Column Normalization

- Timestamp columns are detected case-insensitively from:
  - `timestamp`
  - `datetime`
  - `date`
  - `time`
- OHLCV columns are normalized case-insensitively to:
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
- `/api/ohlcv` requires all OHLCV columns. Missing columns return a clear API error.
- Numeric epoch timestamps are interpreted as UTC seconds, milliseconds, microseconds, or nanoseconds by magnitude.

## Dynamic Catalogs

- Feature, signal, target, and prediction catalogs are inferred from dataset columns.
- Feature categories are heuristic and based on column names. This avoids hardcoding a closed feature registry into the dashboard.
- Signal columns are inferred from names containing `signal`, `candidate`, `side`, or `position`.
- Target columns are inferred from names containing `target`, `r_target`, or `label`.
- Prediction columns are inferred from names beginning with `pred` or containing `prediction`, `probability`, or `_prob`.

## Parameterized Builders

- The dashboard exposes existing builders from `src.experiments.registry.FEATURE_REGISTRY` and `SIGNAL_REGISTRY`.
- Target builders are exposed from `src.targets` as `forward_return`, `triple_barrier`, `r_multiple`, and `classifier`.
- Parameterized builder execution is a read-only preview path. It applies selected builders to an in-memory copy of the selected dataset and returns chartable numeric output columns.
- The dashboard does not persist computed feature/signal/target columns back into datasets, configs, or experiment artifacts.
- Builder parameter forms are generated from Python function signatures where possible. Target builder forms use explicit defaults from the existing target implementations because the target API accepts a single config dictionary.
- If a builder needs upstream columns, the user must include the required earlier feature/signal steps in the dashboard sequence. For example, a target depending on `manual_long_signal` must run or load a step that creates that column first.
- When no date range is selected, the frontend requests a capped preview for returned chart series. The backend computes the selected builder sequence before applying that return cap, so rolling/windowed features retain earlier context within the loaded dataset.

## Layout Storage

- Saved dashboard layouts are JSON files under `apps/trading_dashboard/layouts`.
- Layouts store selection state and visualization series configs only; they do not snapshot market data.

## Current MVP Boundaries

- The dashboard reads existing datasets and experiment outputs but does not launch experiments.
- The frontend renders candlesticks, line overlays, lower-panel line/histogram series, and simple trade entry/exit markers.
- Background regime shading, probability bands, and full prediction diagnostics are represented in the visualization schema but not fully rendered in the first MVP.
