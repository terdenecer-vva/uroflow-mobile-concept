#!/usr/bin/env bash
set -euo pipefail

DATASET_ROOT="${1:-}"
MANIFEST_PATH="${2:-}"
SUBMISSION_BUILD_ROOT="${3:-}"

if [[ -z "${DATASET_ROOT}" || -z "${MANIFEST_PATH}" || -z "${SUBMISSION_BUILD_ROOT}" ]]; then
  echo "Usage: $0 <DATASET_ROOT> <MANIFEST_PATH> <SUBMISSION_BUILD_ROOT>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "${SCRIPT_DIR}/scripts/build_g1_evidence_bundle.py" --dataset_root "${DATASET_ROOT}" --manifest "${MANIFEST_PATH}" --submission_build_root "${SUBMISSION_BUILD_ROOT}" --out_dir "${SCRIPT_DIR}/outputs/g1" --make_plots --make_pdf
echo "Done. Outputs: ${SCRIPT_DIR}/outputs/g1"
