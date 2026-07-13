#!/usr/bin/env bash
set -euo pipefail

docker compose run --rm app \
  python scripts/chatgpt_create_v37_rolling_validation_suite.py

CONFIG_DIR="config/experiments/foundation_alpha/ethusd/v3_7_validation/rolling_windows_normalized_rank"

for cfg in "${CONFIG_DIR}"/*.yaml; do
  echo "============================================================"
  echo "Running: ${cfg}"
  docker compose run --rm app \
    python -m src.experiments.runner "${cfg}"
done

docker compose run --rm app \
  python scripts/analyze_v37_rolling_random_bootstrap.py \
  --logs-dir logs/experiments \
  --prefix ethusd_30m_lightgbm_h24_v37_roll \
  --random-draws 1000 \
  --bootstrap-draws 5000 \
  --block-bars 96
