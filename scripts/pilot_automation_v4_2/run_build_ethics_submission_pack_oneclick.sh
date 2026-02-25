#!/bin/bash
set -e
REGION="$1"
if [ -z "$REGION" ]; then
  echo "Usage: $0 <RU_EC|EU_Ethics|US_IRB>"
  exit 1
fi
python3 scripts/build_ethics_submission_pack.py --region "$REGION"
