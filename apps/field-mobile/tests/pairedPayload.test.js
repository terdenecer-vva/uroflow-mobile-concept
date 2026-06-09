const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const paired = require(path.join(buildDir, "payload/pairedPayload.js"));

function buildForm(overrides = {}) {
  return {
    sessionId: " SESSION-001 ",
    syncId: " SYNC-001 ",
    siteId: " SITE-001 ",
    subjectId: " SUBJ-001 ",
    operatorId: " OP-001 ",
    attemptNumber: "2",
    measuredAt: " 2026-06-04T00:00:00Z ",
    platform: "ios",
    deviceModel: " iPhone 15 ",
    appVersion: " 0.1.0 ",
    captureMode: "water_impact",
    appQmax: "12.5",
    appQavg: "8.25",
    appVvoid: "250",
    appFlowTime: "18",
    appTqmax: "4.5",
    appQualityStatus: "valid",
    appQualityScore: "91.5",
    appModelId: " fusion-v0.1 ",
    refQmax: "13.2",
    refQavg: "8.8",
    refVvoid: "260",
    refFlowTime: "19",
    refTqmax: "4.8",
    refDeviceModel: " Reference Uroflow ",
    refDeviceSerial: " REF-123 ",
    notes: " field notes ",
    ...overrides,
  };
}

test("buildPairedPayloadFromForm trims identifiers and parses metrics", () => {
  const payload = paired.buildPairedPayloadFromForm(buildForm());

  assert.deepEqual(payload.session, {
    session_id: "SESSION-001",
    sync_id: "SYNC-001",
    site_id: "SITE-001",
    subject_id: "SUBJ-001",
    operator_id: "OP-001",
    attempt_number: 2,
    measured_at: "2026-06-04T00:00:00Z",
    platform: "ios",
    device_model: "iPhone 15",
    app_version: "0.1.0",
    capture_mode: "water_impact",
  });
  assert.deepEqual(payload.app.metrics, {
    qmax_ml_s: 12.5,
    qavg_ml_s: 8.25,
    vvoid_ml: 250,
    flow_time_s: 18,
    tqmax_s: 4.5,
  });
  assert.equal(payload.app.quality_score, 91.5);
  assert.equal(payload.app.model_id, "fusion-v0.1");
  assert.equal(payload.reference.device_model, "Reference Uroflow");
  assert.equal(payload.reference.device_serial, "REF-123");
  assert.equal(payload.notes, "field notes");
});

test("buildPairedPayloadFromForm converts blank optional fields to null", () => {
  const payload = paired.buildPairedPayloadFromForm(
    buildForm({
      syncId: " ",
      deviceModel: "",
      appVersion: "",
      appFlowTime: "",
      appTqmax: "",
      appQualityScore: "",
      appModelId: "",
      refFlowTime: "",
      refTqmax: "",
      refDeviceModel: "",
      refDeviceSerial: "",
      notes: "",
    }),
  );

  assert.equal(payload.session.sync_id, null);
  assert.equal(payload.session.device_model, null);
  assert.equal(payload.session.app_version, null);
  assert.equal(payload.app.metrics.flow_time_s, null);
  assert.equal(payload.app.metrics.tqmax_s, null);
  assert.equal(payload.app.quality_score, null);
  assert.equal(payload.app.model_id, null);
  assert.equal(payload.reference.metrics.flow_time_s, null);
  assert.equal(payload.reference.metrics.tqmax_s, null);
  assert.equal(payload.reference.device_model, null);
  assert.equal(payload.reference.device_serial, null);
  assert.equal(payload.notes, null);
});

test("validatePairedPayloadForSubmission reports required field failures", () => {
  const validPayload = paired.buildPairedPayloadFromForm(buildForm());

  assert.equal(
    paired.validatePairedPayloadForSubmission(validPayload, { captureRunning: true }),
    "Stop runtime capture before submitting.",
  );
  assert.equal(
    paired.validatePairedPayloadForSubmission(
      paired.buildPairedPayloadFromForm(buildForm({ sessionId: "" })),
      { captureRunning: false },
    ),
    "session_id is required",
  );
  assert.equal(
    paired.validatePairedPayloadForSubmission(
      paired.buildPairedPayloadFromForm(buildForm({ attemptNumber: "0" })),
      { captureRunning: false },
    ),
    "attempt_number must be >= 1",
  );
  assert.equal(
    paired.validatePairedPayloadForSubmission(
      paired.buildPairedPayloadFromForm(buildForm({ appQmax: "" })),
      { captureRunning: false },
    ),
    "App metrics qmax/qavg/vvoid are required",
  );
  assert.equal(
    paired.validatePairedPayloadForSubmission(
      paired.buildPairedPayloadFromForm(buildForm({ refVvoid: "" })),
      { captureRunning: false },
    ),
    "Reference metrics qmax/qavg/vvoid are required",
  );
});

test("validatePairedPayloadForSubmission blocks runtime low-quality status upgrades", () => {
  const runtimeRepeatPayload = {
    analysis: {
      runtime_quality: {
        quality_status: "repeat",
      },
    },
  };

  assert.match(
    paired.validatePairedPayloadForSubmission(
      paired.buildPairedPayloadFromForm(buildForm({ appQualityStatus: "valid" })),
      { captureRunning: false, runtimeCaptureContractPayload: runtimeRepeatPayload },
    ),
    /app quality_status cannot be valid/,
  );
  assert.equal(
    paired.validatePairedPayloadForSubmission(
      paired.buildPairedPayloadFromForm(buildForm({ appQualityStatus: "repeat" })),
      { captureRunning: false, runtimeCaptureContractPayload: runtimeRepeatPayload },
    ),
    null,
  );
});

test("validatePairedPayloadForSubmission accepts a complete payload", () => {
  assert.equal(
    paired.validatePairedPayloadForSubmission(
      paired.buildPairedPayloadFromForm(buildForm()),
      { captureRunning: false },
    ),
    null,
  );
});
