#!/usr/bin/env bash
set -euo pipefail

SUBMISSION_ROOT="${1:-}"

if [[ -z "$SUBMISSION_ROOT" ]]; then
  echo "Usage: $0 <SUBMISSION_BUILD_ROOT>"
  echo "Example: $0 ../.."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "${SCRIPT_DIR}/scripts/build_g2_submission_bundle.py" \
  --submission_root "${SUBMISSION_ROOT}" \
  --out_dir "${SCRIPT_DIR}/outputs/g2_bundle" \
  --zip_bundle

echo "DONE. Bundle outputs in: ${SCRIPT_DIR}/outputs/g2_bundle"
