# Market-Making Experiments

This folder contains research-only market-making experiment configs. They are
separate from execution configs under `config/execution/` and must not place
demo or live orders.

Current configs:

- `market_making_moment.yaml`: quote-level MOMENT research baseline for testing
  whether a pretrained time-series feature extractor plus a lightweight head can
  reduce toxic fills and improve fee-adjusted markout.
- `market_making_large_moment_pipeline.yaml`: single-command staged pipeline for
  large local order-book datasets. By default it does not collect new data; it
  reuses the configured `orderbook_events.csv`, runs paper replay, builds or
  reuses the MOMENT dataset, and then runs the MOMENT research experiment.

Outputs are written under `logs/experiments/market_making/` and must stay
JSON/CSV/Markdown/Parquet-only.
