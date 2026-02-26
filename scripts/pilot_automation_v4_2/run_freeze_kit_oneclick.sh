#!/bin/bash
set -e
DATASET_ROOT="$1"
DATASET_ID="$2"
OPERATOR_ID="$3"
if [ -z "$DATASET_ROOT" ]; then
  echo "Usage: $0 <DATASET_ROOT> [DATASET_ID] [OPERATOR_ID]"
  exit 1
fi
python3 scripts/build_pilot_freeze_kit.py \
  --dataset_root "$DATASET_ROOT" \
  ${DATASET_ID:+--dataset_id "$DATASET_ID"} \
  ${OPERATOR_ID:+--operator_id "$OPERATOR_ID"}
