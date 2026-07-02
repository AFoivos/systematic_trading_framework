# Market-Making Experiments

This folder contains research-only market-making experiment configs. They are
separate from execution configs under `config/execution/` and must not place
demo or live orders.

Current configs:

- `market_making_moment.yaml`: quote-level MOMENT research baseline for testing
  whether a pretrained time-series feature extractor plus a lightweight head can
  reduce toxic fills and improve fee-adjusted markout.

Outputs are written under `logs/experiments/market_making/` and must stay
JSON/CSV/Markdown/Parquet-only.
