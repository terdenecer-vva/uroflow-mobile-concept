#!/bin/bash
set -euo pipefail
DATASET_ROOT="${1:-}"
MANIFEST="${2:-}"
PROFILE="${3:-P0}"

if [[ -z "$DATASET_ROOT" || -z "$MANIFEST" ]]; then
  echo "Usage: $0 <DATASET_ROOT> <MANIFEST.csv|xlsx> [PROFILE P0|P1|P2|P3]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/scripts/validate_artifacts_by_profile.py" \
  --dataset_root "$DATASET_ROOT" \
  --manifest "$MANIFEST" \
  --profile "$PROFILE" \
  --out_dir "$SCRIPT_DIR/outputs/validate_artifacts"
