#!/bin/bash
set -e
DATASET_ROOT="$1"
MANIFEST="$2"
if [ -z "$DATASET_ROOT" ] || [ -z "$MANIFEST" ]; then
  echo "Usage: $0 <DATASET_ROOT> <MANIFEST.csv|xlsx>"
  exit 1
fi
python3 scripts/compute_accuracy_acceptance.py --dataset_root "$DATASET_ROOT" --manifest "$MANIFEST"
