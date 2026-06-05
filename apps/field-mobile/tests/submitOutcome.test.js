const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const submitOutcome = require(path.join(buildDir, "utils/submitOutcome.js"));

test("buildQueuedCapturePackageMessage preserves retryable HTTP status without raw body", () => {
  assert.equal(
    submitOutcome.buildQueuedCapturePackageMessage({
      ok: false,
      statusCode: 503,
      body: "upstream unavailable for patient Jane",
      retryable: true,
    }),
    "Paired uploaded; capture package queued for retry: HTTP 503 server_or_client_response",
  );
});

test("buildRejectedCapturePackageMessage uses ERROR fallback without raw body", () => {
  assert.equal(
    submitOutcome.buildRejectedCapturePackageMessage({
      ok: false,
      statusCode: null,
      body: "invalid capture payload for subject SUBJ-001",
      retryable: false,
    }),
    "Paired measurement uploaded, but capture package rejected: ERROR validation",
  );
});

test("buildNonRetryableUploadMessage preserves validation category", () => {
  assert.equal(
    submitOutcome.buildNonRetryableUploadMessage({
      ok: false,
      statusCode: 422,
      body: "validation error: patient name missing",
      retryable: false,
    }),
    "Upload rejected and not queued. HTTP 422 validation",
  );
});

test("buildQueuedPairedAndCaptureMessage uses NETWORK fallback for retryable network failures", () => {
  assert.equal(
    submitOutcome.buildQueuedPairedAndCaptureMessage({
      ok: false,
      statusCode: null,
      body: "TypeError: failed to fetch",
      retryable: true,
    }),
    "Queued paired+capture for retry. Last paired error: NETWORK network_or_timeout",
  );
});
