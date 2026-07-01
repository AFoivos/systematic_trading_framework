#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="config/experiments/scalp/diagnostics"
PATTERN="${1:-}"

if [[ -n "${PATTERN}" ]]; then
  configs=("${CONFIG_DIR}"/*"${PATTERN}"*.yaml)
else
  configs=("${CONFIG_DIR}"/*.yaml)
fi

if [[ ${#configs[@]} -eq 0 || ! -e "${configs[0]}" ]]; then
  echo "No diagnostic YAMLs matched pattern '${PATTERN}' in ${CONFIG_DIR}" >&2
  exit 1
fi

for yaml_path in "${configs[@]}"; do
  echo ""
  echo "================================================================"
  echo "Running QFS diagnostic: ${yaml_path}"
  echo "================================================================"
  python -m src.experiments.runner "${yaml_path}"
done
