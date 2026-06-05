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

function buildCapturePackagePayload(syncId = "SYNC-001") {
  const pairedPayload = buildPayload(syncId);
  return {
    session: pairedPayload.session,
    package_type: "capture_contract_json",
    capture_payload: {
      schema_version: "ios_capture_v1",
      session: {
        session_id: pairedPayload.session.session_id,
        sync_id: pairedPayload.session.sync_id,
      },
      samples: [],
    },
    paired_measurement_id: null,
    notes: "mobile_runtime_capture_contract_audio_imu_v0.1",
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

test("shouldAutoSyncPendingQueue requires hydrated settings, pending work, and configured API", () => {
  assert.equal(
    pending.shouldAutoSyncPendingQueue({
      settingsHydrated: true,
      pendingCount: 1,
      apiConfigured: true,
    }),
    true,
  );
  assert.equal(
    pending.shouldAutoSyncPendingQueue({
      settingsHydrated: false,
      pendingCount: 1,
      apiConfigured: true,
    }),
    false,
  );
  assert.equal(
    pending.shouldAutoSyncPendingQueue({
      settingsHydrated: true,
      pendingCount: 0,
      apiConfigured: true,
    }),
    false,
  );
  assert.equal(
    pending.shouldAutoSyncPendingQueue({
      settingsHydrated: true,
      pendingCount: 1,
      apiConfigured: false,
    }),
    false,
  );
});

test("isNetworkReachableForSync treats connected unknown internet as usable", () => {
  assert.equal(pending.isNetworkReachableForSync(true, true), true);
  assert.equal(pending.isNetworkReachableForSync(true, null), true);
  assert.equal(pending.isNetworkReachableForSync(true, false), false);
  assert.equal(pending.isNetworkReachableForSync(false, true), false);
  assert.equal(pending.isNetworkReachableForSync(null, true), false);
});

test("shouldAutoSyncOnConnectivityRestore requires unreachable to reachable transition", () => {
  const baseGate = {
    settingsHydrated: true,
    pendingCount: 1,
    apiConfigured: true,
  };

  assert.equal(
    pending.shouldAutoSyncOnConnectivityRestore({
      ...baseGate,
      wasNetworkReachable: false,
      isNetworkReachable: true,
    }),
    true,
  );
  assert.equal(
    pending.shouldAutoSyncOnConnectivityRestore({
      ...baseGate,
      wasNetworkReachable: null,
      isNetworkReachable: true,
    }),
    false,
  );
  assert.equal(
    pending.shouldAutoSyncOnConnectivityRestore({
      ...baseGate,
      wasNetworkReachable: false,
      isNetworkReachable: false,
    }),
    false,
  );
  assert.equal(
    pending.shouldAutoSyncOnConnectivityRestore({
      ...baseGate,
      pendingCount: 0,
      wasNetworkReachable: false,
      isNetworkReachable: true,
    }),
    false,
  );
});

test("mobile E2E smoke replays queued paired and capture submissions after network restore", async () => {
  const queue = [
    buildPendingSubmission({
      id: "PENDING-PAIR",
      endpoint: "paired_measurements",
      payload: buildPayload("SYNC-E2E-001"),
    }),
    buildPendingSubmission({
      id: "PENDING-CAPTURE",
      endpoint: "capture_packages",
      payload: buildCapturePackagePayload("SYNC-E2E-001"),
      request_headers: {
        api_key: "",
        actor_role: "",
        site_id: "",
        operator_id: "",
        request_id: "",
      },
    }),
  ];
  const currentHeaders = {
    api_key: "current-key",
    actor_role: "operator",
    site_id: "SITE-CURRENT",
    operator_id: "OP-CURRENT",
    request_id: "REQ-CURRENT",
  };

  const offlineCalls = [];
  const offlineResult = await pending.runPendingSyncBatch({
    queue,
    requestHeaderContext: currentHeaders,
    attemptedAtIso: "2026-06-04T01:02:03.000Z",
    submitEndpoint: async ({ endpoint, endpointPayload, headerContext }) => {
      offlineCalls.push({
        endpoint,
        requestId: headerContext.request_id,
        sessionId: endpointPayload.session.session_id,
        syncId: endpointPayload.session.sync_id,
      });
      return {
        ok: false,
        statusCode: null,
        body: "TypeError: failed to fetch subject_id=SUBJ-001 api_key=secret-token",
        retryable: true,
      };
    },
  });

  assert.deepEqual(
    offlineCalls.map((call) => `${call.endpoint}:${call.sessionId}:${call.syncId}`),
    [
      "paired_measurements:SESSION-001:SYNC-E2E-001",
      "capture_packages:SESSION-001:SYNC-E2E-001",
    ],
  );
  assert.deepEqual(
    offlineCalls.map((call) => call.requestId),
    ["REQ-QUEUED", "PENDING-CAPTURE"],
  );
  assert.equal(offlineResult.remaining.length, 2);
  assert.deepEqual(
    offlineResult.remaining.map((item) => item.id),
    ["PENDING-PAIR", "PENDING-CAPTURE"],
  );
  assert.equal(offlineResult.remaining.every((item) => item.attempt_count === 1), true);
  assert.equal(offlineResult.remaining.every((item) => item.last_error === "network_or_timeout"), true);
  assert.deepEqual(offlineResult.summary, {
    batchCount: 2,
    totalCount: 2,
    syncedPaired: 0,
    syncedCapture: 0,
    remainingQueued: 2,
    deferred: 0,
    droppedNonRetryable: 0,
  });

  const restoredCalls = [];
  const restoredResult = await pending.runPendingSyncBatch({
    queue: offlineResult.remaining,
    requestHeaderContext: currentHeaders,
    attemptedAtIso: "2026-06-04T01:03:03.000Z",
    submitEndpoint: async ({ endpoint, endpointPayload }) => {
      restoredCalls.push(`${endpoint}:${endpointPayload.session.session_id}`);
      return {
        ok: true,
        statusCode: endpoint === "capture_packages" ? 201 : 200,
        body: endpoint === "capture_packages" ? '{"id": 102}' : '{"id": 101}',
        retryable: false,
      };
    },
  });

  assert.deepEqual(restoredCalls, [
    "paired_measurements:SESSION-001",
    "capture_packages:SESSION-001",
  ]);
  assert.deepEqual(
    restoredResult.attempts.map((attempt) => attempt.outcome),
    ["synced_paired", "synced_capture"],
  );
  assert.deepEqual(restoredResult.remaining, []);
  assert.deepEqual(restoredResult.summary, {
    batchCount: 2,
    totalCount: 2,
    syncedPaired: 1,
    syncedCapture: 1,
    remainingQueued: 0,
    deferred: 0,
    droppedNonRetryable: 0,
  });
  assert.equal(
    restoredResult.statusMessage,
    "Sync batch completed (2/2). Synced paired: 1, synced capture: 1, remaining queued: 0, deferred: 0, dropped non-retryable: 0.",
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
    result: {
      ok: false,
      statusCode: 503,
      body: "upstream unavailable for subject SUBJ-001",
      retryable: true,
    },
    attemptedAtIso: "2026-06-04T01:02:03.000Z",
  });

  assert.equal(attempt.outcome, "retryable");
  assert.equal(attempt.attemptedItem.attempt_count, 1);
  assert.equal(attempt.attemptedItem.last_status_code, 503);
  assert.equal(attempt.attemptedItem.last_error, "server_or_client_response");
});

test("buildPendingSyncAttempt keeps auth failures queued for credential repair", () => {
  const attempt = pending.buildPendingSyncAttempt({
    item: buildPendingSubmission({
      endpoint: "capture_packages",
      payload: buildCapturePackagePayload("SYNC-AUTH"),
    }),
    headerContext: {
      api_key: "fixed-later",
      actor_role: "operator",
      site_id: "SITE-CURRENT",
      operator_id: "OP-CURRENT",
      request_id: "REQ-AUTH",
    },
    result: {
      ok: false,
      statusCode: 403,
      body: "Forbidden: site scope mismatch for operator_id=OP-001",
      retryable: true,
    },
    attemptedAtIso: "2026-06-04T01:02:03.000Z",
  });

  assert.equal(attempt.outcome, "retryable");
  assert.equal(attempt.attemptedItem.attempt_count, 1);
  assert.equal(attempt.attemptedItem.last_status_code, 403);
  assert.equal(attempt.attemptedItem.last_error, "auth_or_permission");
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
    result: {
      ok: false,
      statusCode: 422,
      body: "validation error: patient name missing",
      retryable: false,
    },
    attemptedAtIso: "2026-06-04T01:02:03.000Z",
  });

  assert.equal(attempt.outcome, "dropped_non_retryable");
  assert.equal(attempt.attemptedItem.attempt_count, 1);
  assert.equal(attempt.attemptedItem.last_status_code, 422);
  assert.equal(attempt.attemptedItem.last_error, "validation");
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
