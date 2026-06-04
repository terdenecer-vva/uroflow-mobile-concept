#!/bin/sh
set -eu

BUILD_DIR="${MOBILE_UNIT_BUILD_DIR:-/tmp/uroflow-field-mobile-unit}"

rm -rf "$BUILD_DIR"
tsc --ignoreConfig \
  src/utils/appHelpers.ts \
  src/api/clinicalHub.ts \
  src/capture/buildCaptureContract.ts \
  src/capture/runtimeMetrics.ts \
  src/capture/roiSignalEstimator.ts \
  --outDir "$BUILD_DIR" \
  --module Node16 \
  --target ES2022 \
  --moduleResolution node16 \
  --lib ES2022,DOM \
  --skipLibCheck \
  --esModuleInterop

MOBILE_UNIT_BUILD_DIR="$BUILD_DIR" node --test tests/*.test.js
