#!/usr/bin/env bash
set -euo pipefail
DATASET_ROOT="${1:-}"
MANIFEST="${2:-}"
if [[ -z "$DATASET_ROOT" || -z "$MANIFEST" ]]; then
  echo "Usage: $0 <DATASET_ROOT> <MANIFEST.csv|xlsx>"
  exit 1
fi
python3 scripts/validate_privacy_content_guardrails_v2.py --dataset_root "$DATASET_ROOT" --manifest "$MANIFEST" --config config/privacy_content_guardrails_v2_config.json
