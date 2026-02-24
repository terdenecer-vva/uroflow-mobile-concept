#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <SUBMISSION_BUILD_ROOT>"
  exit 1
fi

BUILD_ROOT="$1"

python3 "${BUILD_ROOT}/10_Pilot_Automation/scripts/update_dhf_status.py" \
  --build_root "${BUILD_ROOT}" \
  --dhf_in "01_Product_QMS/Uroflow_DHF_Index_Status_Register_v1.2.xlsx" \
  --dhf_out "01_Product_QMS/Uroflow_DHF_Index_Status_Register_v1.3_EXECUTED_AUTO.xlsx"

echo "[OK] DHF executed status written to: ${BUILD_ROOT}/01_Product_QMS/Uroflow_DHF_Index_Status_Register_v1.3_EXECUTED_AUTO.xlsx"
