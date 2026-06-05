const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const submitOutcome = require(path.join(buildDir, "utils/submitOutcome.js"));

test("buildQueuedCapturePackageMessage preserves retryable HTTP wording", () => {
  assert.equal(
    submitOutcome.buildQueuedCapturePackageMessage({
      ok: false,
      statusCode: 503,
      body: "upstream unavailable",
      retryable: true,
    }),
    "Paired uploaded; capture package queued for retry: HTTP 503 upstream unavailable",
  );
});

test("buildRejectedCapturePackageMessage uses ERROR fallback for non-HTTP failures", () => {
  assert.equal(
    submitOutcome.buildRejectedCapturePackageMessage({
      ok: false,
      statusCode: null,
      body: "invalid capture payload",
      retryable: false,
    }),
    "Paired measurement uploaded, but capture package rejected: ERROR invalid capture payload",
  );
});

test("buildNonRetryableUploadMessage preserves validation rejection wording", () => {
  assert.equal(
    submitOutcome.buildNonRetryableUploadMessage({
      ok: false,
      statusCode: 422,
      body: "validation error",
      retryable: false,
    }),
    "Upload rejected and not queued. HTTP 422 validation error",
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
    "Queued paired+capture for retry. Last paired error: NETWORK TypeError: failed to fetch",
  );
});
