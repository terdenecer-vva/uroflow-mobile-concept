const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const storage = require(path.join(buildDir, "storage/pendingSubmissionStorage.js"));

function buildSession(overrides = {}) {
  return {
    session_id: "SESSION-001",
    sync_id: "SYNC-001",
    site_id: "SITE-001",
    subject_id: "SUBJ-001",
    operator_id: "OP-001",
    attempt_number: 1,
    measured_at: "2026-06-04T00:00:00Z",
    platform: "ios",
    device_model: "iPhone",
    app_version: "0.1.0",
    capture_mode: "water_impact",
    ...overrides,
  };
}

function buildPairedPayload(overrides = {}) {
  return {
    session: buildSession(),
    app: {
      metrics: {
        qmax_ml_s: null,
        qavg_ml_s: null,
        vvoid_ml: null,
        flow_time_s: null,
        tqmax_s: null,
      },
      quality_status: "valid",
      quality_score: null,
      model_id: null,
    },
    reference: {
      metrics: {
        qmax_ml_s: null,
        qavg_ml_s: null,
        vvoid_ml: null,
        flow_time_s: null,
        tqmax_s: null,
      },
      device_model: null,
      device_serial: null,
    },
    notes: null,
    ...overrides,
  };
}

test("normalizePendingSubmission fills migrated queue metadata deterministically", () => {
  const item = storage.normalizePendingSubmission(
    {
      id: "",
      created_at: "",
      endpoint: "legacy_endpoint",
      payload: buildPairedPayload(),
      request_headers: {
        actor_role: "Investigator",
        request_id: " REQ-001 ",
      },
      attempt_count: "2.6",
      last_attempt_at: 123,
      last_error: 456,
      last_status_code: "503",
    },
    {
      createId: () => "PENDING-FALLBACK",
      nowIso: () => "2026-06-04T01:02:03.000Z",
    },
  );

  assert.ok(item);
  assert.equal(item.id, "PENDING-FALLBACK");
  assert.equal(item.created_at, "2026-06-04T01:02:03.000Z");
  assert.equal(item.endpoint, "paired_measurements");
  assert.equal(item.attempt_count, 3);
  assert.equal(item.last_attempt_at, null);
  assert.equal(item.last_error, null);
  assert.equal(item.last_status_code, null);
  assert.deepEqual(item.request_headers, {
    api_key: "",
    actor_role: "investigator",
    site_id: "SITE-001",
    operator_id: "OP-001",
    request_id: "REQ-001",
  });
});

test("normalizePendingSubmission preserves capture package payloads", () => {
  const payload = {
    session: buildSession({ sync_id: "SYNC-CAPTURE" }),
    package_type: "capture_contract_json",
    capture_payload: { schema_version: "ios_capture_v1" },
    paired_measurement_id: 42,
    notes: null,
  };

  const item = storage.normalizePendingSubmission({
    id: "PENDING-CAPTURE",
    created_at: "2026-06-04T00:00:00.000Z",
    endpoint: "capture_packages",
    payload,
    request_headers: null,
    attempt_count: 0,
    last_attempt_at: null,
    last_error: null,
    last_status_code: 503,
  });

  assert.ok(item);
  assert.equal(item.endpoint, "capture_packages");
  assert.equal(item.payload, payload);
  assert.equal(item.request_headers.site_id, "SITE-001");
  assert.equal(item.request_headers.operator_id, "OP-001");
  assert.equal(item.last_status_code, 503);
});

test("normalizePendingSubmission drops corrupt payloads without session context", () => {
  assert.equal(
    storage.normalizePendingSubmission({
      id: "PENDING-BROKEN",
      endpoint: "paired_measurements",
      payload: { not_session: true },
    }),
    null,
  );
});
