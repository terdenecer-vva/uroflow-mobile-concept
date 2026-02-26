#!/usr/bin/env bash
set -euo pipefail

TFL_CSV="${1:-}"

if [[ -z "${TFL_CSV}" ]]; then
  echo "Usage: $0 <TFL_RECORD_LEVEL_CSV>"
  echo "Example: $0 outputs/tfl/tfl_record_level.csv"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "${SCRIPT_DIR}/scripts/run_drift_dashboard.py" --tfl_csv "${TFL_CSV}" --out_dir "${SCRIPT_DIR}/outputs/drift"
echo "Done. Outputs: ${SCRIPT_DIR}/outputs/drift"
