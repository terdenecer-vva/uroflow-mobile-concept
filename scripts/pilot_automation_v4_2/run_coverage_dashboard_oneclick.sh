#!/usr/bin/env bash
set -euo pipefail

DATASET_ROOT=${1:-}
MANIFEST=${2:-}

if [[ -z "$DATASET_ROOT" || -z "$MANIFEST" ]]; then
  echo "Usage: $0 <DATASET_ROOT> <MANIFEST.csv|xlsx>"
  exit 1
fi

python3 scripts/run_coverage_dashboard.py --dataset_root "$DATASET_ROOT" --manifest "$MANIFEST" --targets config/coverage_targets_config.json
