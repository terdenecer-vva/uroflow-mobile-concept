#!/usr/bin/env bash
set -euo pipefail

DATASET_ROOT="${1:-}"
MANIFEST="${2:-}"

if [[ -z "$DATASET_ROOT" || -z "$MANIFEST" ]]; then
  echo "Usage: $0 <DATASET_ROOT> <MANIFEST_PATH>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/3] Running TFL generator (with BA plots)..."
python3 "${SCRIPT_DIR}/scripts/run_tfl_from_golden_dataset.py" \
  --dataset_root "${DATASET_ROOT}" \
  --manifest "${MANIFEST}" \
  --make_plots

echo "[2/3] Generating CSR auto-draft (EN)..."
python3 "${SCRIPT_DIR}/scripts/generate_csr_autodraft.py" \
  --tfl_dir "${SCRIPT_DIR}/outputs/tfl" \
  --csr_template "${SCRIPT_DIR}/../05_Clinical/Uroflow_CSR_Template_v1.1_AUTOFILL.docx" \
  --out_dir "${SCRIPT_DIR}/outputs/csr_autodraft" \
  --lang EN

echo "[3/3] Generating CSR auto-draft (RU)..."
python3 "${SCRIPT_DIR}/scripts/generate_csr_autodraft.py" \
  --tfl_dir "${SCRIPT_DIR}/outputs/tfl" \
  --csr_template "${SCRIPT_DIR}/../05_Clinical/Uroflow_CSR_Template_v1.1_AUTOFILL_RU.docx" \
  --out_dir "${SCRIPT_DIR}/outputs/csr_autodraft" \
  --lang RU

echo "DONE. Outputs in: ${SCRIPT_DIR}/outputs/csr_autodraft"
