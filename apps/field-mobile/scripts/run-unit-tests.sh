#!/bin/sh
set -eu

BUILD_DIR="${MOBILE_UNIT_BUILD_DIR:-/tmp/uroflow-field-mobile-unit}"
TEST_FILES=""

rm -rf "$BUILD_DIR"
tsc --ignoreConfig \
  src/utils/appHelpers.ts \
  src/utils/deviceIdentity.ts \
  src/utils/claimsNotice.ts \
  src/utils/pendingSyncQueue.ts \
  src/utils/releaseIdentity.ts \
  src/utils/submitOutcome.ts \
  src/config/appConfig.ts \
  src/config/releaseMetadata.ts \
  src/config/runtimeReleaseGuard.ts \
  src/storage/appSettingsStorage.ts \
  src/storage/pendingSubmissionStorage.ts \
  src/payload/capturePackagePayload.ts \
  src/payload/pairedPayload.ts \
  src/api/clinicalHub.ts \
  src/api/clinicalHubPreflight.ts \
  src/api/connectionCheck.ts \
  src/api/summaryRequests.ts \
  src/capture/buildCaptureContract.ts \
  src/capture/rawMediaRetention.ts \
  src/capture/runtimeMetrics.ts \
  src/capture/roiSignalEstimator.ts \
  --outDir "$BUILD_DIR" \
  --module Node16 \
  --target ES2022 \
  --moduleResolution node16 \
  --lib ES2022,DOM \
  --skipLibCheck \
  --esModuleInterop

if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
  TEST_FILES="$(git ls-files --cached --others --exclude-standard 'tests/*.test.js')"
fi
if [ -z "$TEST_FILES" ]; then
  TEST_FILES="$(find tests -maxdepth 1 -name '*.test.js' | sort)"
fi

# Test filenames are repo-controlled and intentionally do not contain spaces.
# shellcheck disable=SC2086
MOBILE_UNIT_BUILD_DIR="$BUILD_DIR" node --test $TEST_FILES
