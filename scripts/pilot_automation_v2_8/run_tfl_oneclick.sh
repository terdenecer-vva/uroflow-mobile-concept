#!/usr/bin/env bash
set -euo pipefail

DATASET_ROOT="${1:-}"
MANIFEST_PATH="${2:-}"

if [[ -z "${DATASET_ROOT}" || -z "${MANIFEST_PATH}" ]]; then
  echo "Usage: $0 <DATASET_ROOT> <MANIFEST_PATH>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "${SCRIPT_DIR}/scripts/run_tfl_from_golden_dataset.py" --dataset_root "${DATASET_ROOT}" --manifest "${MANIFEST_PATH}" --out_dir "${SCRIPT_DIR}/outputs/tfl" --make_plots --make_pdf
echo "Done. Outputs: ${SCRIPT_DIR}/outputs/tfl"
