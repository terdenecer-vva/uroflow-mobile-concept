const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const releaseIdentity = require(path.join(buildDir, "utils/releaseIdentity.js"));

test("release identity snapshot exposes canonical runtime release metadata", () => {
  const snapshot = releaseIdentity.buildReleaseIdentitySnapshot({
    platform: "ios",
    payloadAppVersion: "0.1.0",
    payloadModelId: "fusion-v0.1",
    payloadCaptureMode: "water_impact",
  });
  const rows = Object.fromEntries(snapshot.canonicalRows.map((row) => [row.label, row.value]));

  assert.equal(snapshot.platform, "ios");
  assert.equal(rows["App version"], "0.1.0");
  assert.equal(rows["Model ID"], "fusion-v0.1");
  assert.equal(rows["Capture schema"], "ios_capture_v1");
  assert.equal(rows["Runtime mode"], "pilot");
  assert.equal(rows["Endpoint set"], "clinical_hub_v1");
  assert.equal(rows["Default capture mode"], "water_impact");
  assert.equal(rows.Privacy, "raw video off, raw audio off, ROI-only on");
  assert.equal(rows["Data residency"], "us/single_region, cross-region sync off");
  assert.equal(rows["Debug gates"], "debug controls off, raw details off, verbose logs off");
  assert.equal(rows["Device platform"], "ios");
  assert.equal(snapshot.payloadStatus, "aligned");
  assert.match(snapshot.artifactTraceabilityNote, /Mobile Build artifacts/);
});

test("release identity snapshot warns when payload traceability is edited", () => {
  const snapshot = releaseIdentity.buildReleaseIdentitySnapshot({
    platform: "android",
    payloadAppVersion: "0.1.1-local",
    payloadModelId: "experimental-model",
    payloadCaptureMode: "debug_capture",
  });

  assert.equal(snapshot.payloadStatus, "edited");
  assert.match(snapshot.payloadEvidence, /app_version=0.1.1-local/);
  assert.match(snapshot.payloadEvidence, /model_id=experimental-model/);
  assert.match(snapshot.payloadEvidence, /capture_mode=debug_capture/);
});
