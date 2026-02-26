#!/usr/bin/env bash
set -euo pipefail

DATASET_ROOT="${1:-}"
MANIFEST_PATH="${2:-}"

if [[ -z "${DATASET_ROOT}" || -z "${MANIFEST_PATH}" ]]; then
  echo "Usage: ./run_daily_qa_oneclick.sh <DATASET_ROOT> <MANIFEST_PATH>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/scripts/run_daily_qa.py" --dataset_root "${DATASET_ROOT}" --manifest "${MANIFEST_PATH}" --out "${SCRIPT_DIR}/outputs" --write_checksums
