const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const capturePackage = require(path.join(buildDir, "payload/capturePackagePayload.js"));

function buildPairedPayload(overrides = {}) {
  const session = {
    session_id: "SESSION-001",
    sync_id: "SYNC-001",
    site_id: "SITE-001",
    subject_id: "SUBJ-001",
    operator_id: "OP-001",
    attempt_number: 1,
    measured_at: "2026-06-04T00:00:00Z",
    platform: "ios",
    device_model: "iPhone 15",
    app_version: "0.1.0",
    capture_mode: "water_impact",
    ...(overrides.session ?? {}),
  };
  return {
    session,
    app: {
      metrics: {
        qmax_ml_s: 12.5,
        qavg_ml_s: 8.2,
        vvoid_ml: 240,
        flow_time_s: 18,
        tqmax_s: 4.1,
      },
      quality_status: "valid",
      quality_score: 91,
      model_id: "fusion-v0.1",
    },
    reference: {
      metrics: {
        qmax_ml_s: 13,
        qavg_ml_s: 8.4,
        vvoid_ml: 245,
        flow_time_s: 18.2,
        tqmax_s: 4.2,
      },
      device_model: "reference",
      device_serial: "REF-001",
    },
    notes: null,
    ...overrides,
  };
}

test("buildCapturePackagePayloadFromPaired uses matching runtime capture payload", () => {
  const runtimePayload = {
    schema_version: "ios_capture_v1",
    session: {
      session_id: "SESSION-001",
      sync_id: "SYNC-001",
    },
    samples: [],
  };

  const payload = capturePackage.buildCapturePackagePayloadFromPaired({
    currentPayload: buildPairedPayload(),
    pairedMeasurementId: 42,
    runtimeCaptureContractPayload: runtimePayload,
    platformVersion: "19.0",
  });

  assert.equal(payload.capture_payload, runtimePayload);
  assert.equal(payload.paired_measurement_id, 42);
  assert.equal(payload.package_type, "capture_contract_json");
  assert.equal(payload.notes, "mobile_runtime_capture_contract_audio_imu_v0.1");
});

test("buildCapturePackagePayloadFromPaired falls back to scaffold when runtime session mismatches", () => {
  const payload = capturePackage.buildCapturePackagePayloadFromPaired({
    currentPayload: buildPairedPayload(),
    pairedMeasurementId: null,
    runtimeCaptureContractPayload: {
      schema_version: "ios_capture_v1",
      session: { session_id: "SESSION-OTHER", sync_id: "SYNC-001" },
    },
    platformVersion: "19.0",
  });

  assert.equal(payload.notes, "mobile_scaffold_capture_contract_v0.1");
  assert.equal(payload.paired_measurement_id, null);
  assert.equal(payload.capture_payload.schema_version, "ios_capture_v1");
  assert.equal(payload.capture_payload.session.session_id, "SESSION-001");
  assert.equal(payload.capture_payload.session.sync_id, "SYNC-001");
  assert.ok(payload.capture_payload.samples.length >= 8);
  assert.equal(
    payload.capture_payload.samples.every((sample) => sample.roi_valid === true),
    true,
  );
});

test("buildCapturePackagePayloadFromPaired creates scaffold when runtime payload is absent", () => {
  const payload = capturePackage.buildCapturePackagePayloadFromPaired({
    currentPayload: buildPairedPayload({ session: { sync_id: null } }),
    pairedMeasurementId: 7,
    runtimeCaptureContractPayload: null,
    platformVersion: "android-16",
  });

  assert.equal(payload.notes, "mobile_scaffold_capture_contract_v0.1");
  assert.equal(payload.capture_payload.session.sync_id, null);
  assert.equal(payload.capture_payload.session.device.ios_version, "android-16");
});
