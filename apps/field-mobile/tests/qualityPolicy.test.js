const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const qualityPolicy = require(path.join(buildDir, "utils/qualityPolicy.js"));

function runtimePayload(qualityStatus) {
  return {
    analysis: {
      runtime_quality: {
        quality_status: qualityStatus,
      },
    },
  };
}

test("extractRuntimeQualityStatus reads runtime contract quality status", () => {
  assert.equal(qualityPolicy.extractRuntimeQualityStatus(runtimePayload("repeat")), "repeat");
  assert.equal(qualityPolicy.extractRuntimeQualityStatus(runtimePayload("reject")), "reject");
  assert.equal(qualityPolicy.extractRuntimeQualityStatus(runtimePayload("unknown")), null);
  assert.equal(qualityPolicy.extractRuntimeQualityStatus(null), null);
});

test("blocks app quality upgrades above runtime capture quality", () => {
  assert.match(
    qualityPolicy.buildRuntimeQualitySubmissionError("valid", runtimePayload("repeat")),
    /app quality_status cannot be valid/,
  );
  assert.match(
    qualityPolicy.buildRuntimeQualitySubmissionError("repeat", runtimePayload("reject")),
    /app quality_status cannot be repeat/,
  );
  assert.equal(
    qualityPolicy.buildRuntimeQualitySubmissionError("reject", runtimePayload("repeat")),
    null,
  );
  assert.equal(
    qualityPolicy.buildRuntimeQualitySubmissionError("repeat", runtimePayload("repeat")),
    null,
  );
});

test("warns when app or runtime quality is repeat or reject", () => {
  assert.equal(qualityPolicy.buildLowQualitySubmissionWarning("valid", null), null);
  assert.match(
    qualityPolicy.buildLowQualitySubmissionWarning("repeat", null),
    /quality_status=repeat/,
  );
  assert.match(
    qualityPolicy.buildLowQualitySubmissionWarning("valid", runtimePayload("reject")),
    /quality_status=reject/,
  );
});
