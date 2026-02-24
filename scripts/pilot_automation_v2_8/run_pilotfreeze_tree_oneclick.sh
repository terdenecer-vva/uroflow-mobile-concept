#!/usr/bin/env bash
set -euo pipefail

SUBMISSION_ROOT="${1:-}"
OUT_DIR="${2:-}"
DRY_RUN="${3:-}"

if [[ -z "$SUBMISSION_ROOT" || -z "$OUT_DIR" ]]; then
  echo "Usage: $0 <SUBMISSION_BUILD_ROOT> <OUT_DIR> [--dry_run]"
  echo "Example: $0 ../.. ./outputs/pilotfreeze_tree"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

EXTRA_LIST="${SCRIPT_DIR}/config/pilotfreeze_extra_includes.txt"

CMD=(python3 "${SCRIPT_DIR}/scripts/build_pilotfreeze_submission_tree.py" \
  --build_root "${SUBMISSION_ROOT}" \
  --out_dir "${OUT_DIR}" \
  --eu_index "06_EU_MDR/Annex_II_III_Submission_Folder/EU_MDR_AnnexII_III_Submission_Folder_Index_v2.3.xlsx" \
  --us_index "07_US_FDA/FDA_Submission_Folder/FDA_Submission_Folder_Index_v2.3.xlsx" \
  --extra_list "${EXTRA_LIST}")

if [[ "$DRY_RUN" == "--dry_run" ]]; then
  CMD+=(--dry_run)
fi

"${CMD[@]}"

echo "DONE. Pilot-freeze tree built into: ${OUT_DIR}"
