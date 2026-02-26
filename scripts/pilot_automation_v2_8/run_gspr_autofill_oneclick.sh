#!/usr/bin/env bash
set -euo pipefail

SUBMISSION_ROOT="${1:-}"

if [[ -z "$SUBMISSION_ROOT" ]]; then
  echo "Usage: $0 <SUBMISSION_BUILD_ROOT>"
  echo "Example: $0 ../.."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "${SCRIPT_DIR}/scripts/autofill_gspr_executed.py" \
  --build_root "${SUBMISSION_ROOT}" \
  --gspr_in "06_EU_MDR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.1_EXECUTED.xlsx" \
  --gspr_out "06_EU_MDR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.2_EXECUTED_AUTO.xlsx" \
  --evidence_manifest "05_Clinical/Uroflow_P0_Pilot_Readiness_Evidence_Manifest_v1.0.xlsx"

echo "DONE. Updated GSPR written to: 06_EU_MDR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.2_EXECUTED_AUTO.xlsx"
