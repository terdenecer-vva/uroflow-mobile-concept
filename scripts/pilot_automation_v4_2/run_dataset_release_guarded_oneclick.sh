#!/bin/bash
set -e
DATASET_ROOT="$1"
MANIFEST="$2"
DATASET_ID="$3"
OPERATOR_ID="$4"
if [ -z "$DATASET_ROOT" ] || [ -z "$MANIFEST" ]; then
  echo "Usage: $0 <DATASET_ROOT> <MANIFEST.csv|xlsx> [DATASET_ID] [OPERATOR_ID]"
  exit 1
fi
python3 scripts/build_dataset_release_bundle_guarded.py \
  --dataset_root "$DATASET_ROOT" \
  --manifest "$MANIFEST" \
  ${DATASET_ID:+--dataset_id "$DATASET_ID"} \
  ${OPERATOR_ID:+--operator_id "$OPERATOR_ID"}
