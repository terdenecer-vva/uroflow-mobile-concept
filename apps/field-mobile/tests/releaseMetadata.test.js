const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const releaseMetadata = require(path.join(buildDir, "config/releaseMetadata.js"));

test("release metadata constants define app/model/schema traceability", () => {
  assert.equal(releaseMetadata.APP_RELEASE_VERSION, "0.1.0");
  assert.equal(releaseMetadata.APP_MODEL_ID, "fusion-v0.1");
  assert.equal(releaseMetadata.APP_CAPTURE_SCHEMA_VERSION, "ios_capture_v1");
  assert.deepEqual(releaseMetadata.APP_RELEASE_METADATA, {
    appVersion: "0.1.0",
    modelId: "fusion-v0.1",
    captureSchemaVersion: "ios_capture_v1",
  });
});
