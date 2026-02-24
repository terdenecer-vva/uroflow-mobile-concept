#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <SUBMISSION_BUILD_ROOT>"
  exit 1
fi

BUILD_ROOT="$1"

python3 "${BUILD_ROOT}/10_Pilot_Automation/scripts/autofill_gspr_evidence_links.py" \
  --build_root "${BUILD_ROOT}" \
  --gspr_in "06_EU_MDR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.2_EXECUTED_AUTO.xlsx" \
  --gspr_out "06_EU_MDR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.3_EXECUTED_EVIDENCE_AUTO.xlsx" \
  --evidence_manifest "05_Clinical/Uroflow_P0_Pilot_Readiness_Evidence_Manifest_v1.0.xlsx"

echo "[OK] Evidence-link GSPR written to: ${BUILD_ROOT}/06_EU_MDR/Uroflow_EU_MDR_GSPR_Checklist_AnnexI_v1.3_EXECUTED_EVIDENCE_AUTO.xlsx"
