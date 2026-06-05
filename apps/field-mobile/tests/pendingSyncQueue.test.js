const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const pending = require(path.join(buildDir, "utils/pendingSyncQueue.js"));

function buildPayload(syncId = "SYNC-001") {
  return {
    session: {
      session_id: "SESSION-001",
      sync_id: syncId,
      site_id: "SITE-001",
      subject_id: "SUBJ-001",
      operator_id: "OP-001",
      attempt_number: 1,
      measured_at: "2026-06-04T00:00:00Z",
      platform: "ios",
      device_model: "iPhone",
      app_version: "0.1.0",
      capture_mode: "water_impact",
    },
  };
}

function buildPendingSubmission(overrides = {}) {
  return {
    id: "PENDING-001",
    created_at: "2026-06-04T00:00:00.000Z",
    endpoint: "paired_measurements",
    payload: buildPayload(),
    request_headers: {
      api_key: "",
      actor_role: "operator",
      site_id: "SITE-QUEUED",
      operator_id: "OP-QUEUED",
      request_id: "REQ-QUEUED",
    },
    attempt_count: 0,
    last_attempt_at: null,
    last_error: null,
    last_status_code: null,
    ...overrides,
  };
}

test("splitPendingSyncBatch caps sync batches and preserves deferred order", () => {
  const queue = Array.from({ length: 12 }, (_, index) =>
    buildPendingSubmission({ id: `PENDING-${String(index).padStart(3, "0")}` }),
  );

  const { batch, deferred } = pending.splitPendingSyncBatch(queue);

  assert.equal(batch.length, pending.MAX_PENDING_SYNC_BATCH_SIZE);
  assert.equal(deferred.length, 2);
  assert.equal(batch[0].id, "PENDING-000");
  assert.equal(batch.at(-1).id, "PENDING-009");
  assert.deepEqual(
    deferred.map((item) => item.id),
    ["PENDING-010", "PENDING-011"],
  );
});

test("buildPendingSyncAttempt records successful capture package submissions", () => {
  const headerContext = {
    api_key: "current-key",
    actor_role: "admin",
    site_id: "SITE-CURRENT",
    operator_id: "OP-CURRENT",
    request_id: "REQ-CURRENT",
  };

  const attempt = pending.buildPendingSyncAttempt({
    item: buildPendingSubmission({
      endpoint: "capture_packages",
      payload: {
        session: buildPayload("SYNC-CAPTURE").session,
        package_type: "capture_contract_json",
        capture_payload: {},
        paired_measurement_id: null,
        notes: null,
      },
      attempt_count: 2,
      last_error: "previous failure",
      last_status_code: 503,
    }),
    headerContext,
    result: { ok: true, statusCode: 201, body: '{"id":7}', retryable: false },
    attemptedAtIso: "2026-06-04T01:02:03.000Z",
  });

  assert.equal(attempt.outcome, "synced_capture");
  assert.equal(attempt.attemptedItem.attempt_count, 3);
  assert.equal(attempt.attemptedItem.last_attempt_at, "2026-06-04T01:02:03.000Z");
  assert.equal(attempt.attemptedItem.last_status_code, 201);
  assert.equal(attempt.attemptedItem.last_error, null);
  assert.deepEqual(attempt.attemptedItem.request_headers, headerContext);
});

test("buildPendingSyncAttempt keeps retryable failures queued with attempt metadata", () => {
  const attempt = pending.buildPendingSyncAttempt({
    item: buildPendingSubmission({ attempt_count: Number.NaN }),
    headerContext: {
      api_key: "current-key",
      actor_role: "operator",
      site_id: "SITE-CURRENT",
      operator_id: "OP-CURRENT",
      request_id: "REQ-CURRENT",
    },
    result: { ok: false, statusCode: 503, body: "upstream unavailable", retryable: true },
    attemptedAtIso: "2026-06-04T01:02:03.000Z",
  });

  assert.equal(attempt.outcome, "retryable");
  assert.equal(attempt.attemptedItem.attempt_count, 1);
  assert.equal(attempt.attemptedItem.last_status_code, 503);
  assert.equal(attempt.attemptedItem.last_error, "upstream unavailable");
});

test("buildPendingSyncAttempt drops non-retryable failed paired submissions", () => {
  const attempt = pending.buildPendingSyncAttempt({
    item: buildPendingSubmission(),
    headerContext: {
      api_key: "current-key",
      actor_role: "operator",
      site_id: "SITE-CURRENT",
      operator_id: "OP-CURRENT",
      request_id: "REQ-CURRENT",
    },
    result: { ok: false, statusCode: 422, body: "validation error", retryable: false },
    attemptedAtIso: "2026-06-04T01:02:03.000Z",
  });

  assert.equal(attempt.outcome, "dropped_non_retryable");
  assert.equal(attempt.attemptedItem.attempt_count, 1);
  assert.equal(attempt.attemptedItem.last_status_code, 422);
});

test("buildPendingSyncStatusMessage preserves operator-facing sync wording", () => {
  assert.equal(
    pending.buildPendingSyncStatusMessage({
      batchCount: 10,
      totalCount: 12,
      syncedPaired: 3,
      syncedCapture: 2,
      remainingQueued: 7,
      deferred: 2,
      droppedNonRetryable: 1,
    }),
    "Sync batch completed (10/12). Synced paired: 3, synced capture: 2, remaining queued: 7, deferred: 2, dropped non-retryable: 1.",
  );
});
