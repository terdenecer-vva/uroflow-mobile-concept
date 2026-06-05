const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const helpers = require(path.join(buildDir, "utils/appHelpers.js"));
const clinicalHub = require(path.join(buildDir, "api/clinicalHub.js"));

function buildPendingSubmission(overrides = {}) {
  return {
    id: "PENDING-STABLE-ID",
    created_at: "2026-06-04T00:00:00.000Z",
    endpoint: "paired_measurements",
    payload: {
      session: {
        session_id: "SESSION-001",
        sync_id: "SYNC-001",
        site_id: "SITE-OLD",
        subject_id: "SUBJ-001",
        operator_id: "OP-OLD",
        attempt_number: 1,
        measured_at: "2026-06-04T00:00:00Z",
        platform: "ios",
        device_model: "iPhone",
        app_version: "0.1.0",
        capture_mode: "water_impact",
      },
    },
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

test("classifyRetryable separates transient and non-retryable statuses", () => {
  assert.equal(helpers.classifyRetryable(null), true);
  assert.equal(helpers.classifyRetryable(408), true);
  assert.equal(helpers.classifyRetryable(425), true);
  assert.equal(helpers.classifyRetryable(429), true);
  assert.equal(helpers.classifyRetryable(500), true);
  assert.equal(helpers.classifyRetryable(503), true);
  assert.equal(helpers.classifyRetryable(400), false);
  assert.equal(helpers.classifyRetryable(401), false);
  assert.equal(helpers.classifyRetryable(422), false);
});

test("summarizePendingError redacts raw response bodies into safe categories", () => {
  assert.equal(helpers.summarizePendingError(null), null);
  assert.equal(helpers.summarizePendingError("validation"), "validation");
  assert.equal(helpers.summarizePendingError("AbortError: request timed out"), "network_or_timeout");
  assert.equal(helpers.summarizePendingError("Unauthorized: bad API key"), "auth_or_permission");
  assert.equal(helpers.summarizePendingError("Validation error: field required"), "validation");
  assert.equal(helpers.summarizePendingError("Invalid capture payload"), "validation");
  assert.equal(helpers.summarizePendingError("HTTP 503 upstream unavailable"), "server_or_client_response");
});

test("formatSafeResponseProblem preserves status without leaking raw response bodies", () => {
  assert.equal(
    helpers.formatSafeResponseProblem(422, "Validation error: patient_name=Jane"),
    "HTTP 422 validation",
  );
  assert.equal(
    helpers.formatSafeResponseProblem(null, "TypeError: failed to fetch", "NETWORK"),
    "NETWORK network_or_timeout",
  );
});

test("formatSafeExceptionMessage redacts mobile PHI and secret-like details", () => {
  const message = helpers.formatSafeExceptionMessage(
    new Error(
      "Runtime failure for subject_id=SUBJ-001 site_id=SITE-001 operator_id=OP-01 api_key=secret-token",
    ),
  );

  assert.equal(message, "ERROR auth_or_permission");
  assert.equal(message.includes("SUBJ-001"), false);
  assert.equal(message.includes("SITE-001"), false);
  assert.equal(message.includes("OP-01"), false);
  assert.equal(message.includes("secret-token"), false);
});

test("summarizeSafeExceptionCategory returns safe categories without raw exception text", () => {
  assert.equal(
    helpers.summarizeSafeExceptionCategory(
      "Runtime failure subject_id=SUBJ-001 api_key=secret-token",
      "network_or_timeout",
    ),
    "auth_or_permission",
  );
  assert.equal(
    helpers.summarizeSafeExceptionCategory("Unexpected native bridge failure", "network_or_timeout"),
    "network_or_timeout",
  );
});

test("formatSafeExceptionMessage preserves network category without raw exception text", () => {
  assert.equal(
    helpers.formatSafeExceptionMessage("TypeError: failed to fetch subject_id=SUBJ-002", "NETWORK"),
    "NETWORK network_or_timeout",
  );
});

test("buildHeaderContextFromValues normalizes operator context and preserves request id", () => {
  assert.deepEqual(
    helpers.buildHeaderContextFromValues(
      "  secret-key  ",
      " Investigator ",
      " SITE-001 ",
      " OP-01 ",
      " REQ-001 ",
    ),
    {
      api_key: "secret-key",
      actor_role: "investigator",
      site_id: "SITE-001",
      operator_id: "OP-01",
      request_id: "REQ-001",
    },
  );
  assert.equal(
    helpers.buildHeaderContextFromValues("", "unknown-role", "", "").actor_role,
    "operator",
  );
});

test("resolvePendingHeaderContext reuses queued request id and queued site context", () => {
  const current = {
    api_key: "current-key",
    actor_role: "admin",
    site_id: "SITE-CURRENT",
    operator_id: "OP-CURRENT",
    request_id: "REQ-CURRENT",
  };
  assert.deepEqual(helpers.resolvePendingHeaderContext(buildPendingSubmission(), current), {
    api_key: "current-key",
    actor_role: "operator",
    site_id: "SITE-QUEUED",
    operator_id: "OP-QUEUED",
    request_id: "REQ-QUEUED",
  });
});

test("resolvePendingHeaderContext falls back to pending id for migrated queue items", () => {
  const item = buildPendingSubmission({
    request_headers: {
      api_key: "",
      actor_role: "",
      site_id: "",
      operator_id: "",
    },
  });
  const resolved = helpers.resolvePendingHeaderContext(item, {
    api_key: "current-key",
    actor_role: "data_manager",
    site_id: "SITE-CURRENT",
    operator_id: "OP-CURRENT",
    request_id: "REQ-CURRENT",
  });
  assert.equal(resolved.request_id, "PENDING-STABLE-ID");
  assert.equal(resolved.actor_role, "data_manager");
  assert.equal(resolved.site_id, "SITE-CURRENT");
});

test("buildRequestHeaders uses stable request id when provided", () => {
  const headers = clinicalHub.buildRequestHeaders(true, {
    api_key: "secret-key",
    actor_role: "operator",
    site_id: "SITE-001",
    operator_id: "OP-01",
    request_id: "REQ-STABLE",
  });
  assert.equal(headers["Content-Type"], "application/json");
  assert.equal(headers["x-api-key"], "secret-key");
  assert.equal(headers["x-actor-role"], "operator");
  assert.equal(headers["x-site-id"], "SITE-001");
  assert.equal(headers["x-operator-id"], "OP-01");
  assert.equal(headers["x-request-id"], "REQ-STABLE");
  assert.equal(headers["x-uroflow-app-version"], "0.1.0");
  assert.equal(headers["x-uroflow-model-id"], "fusion-v0.1");
  assert.equal(headers["x-uroflow-capture-schema-version"], "ios_capture_v1");
  assert.equal(headers["x-uroflow-runtime-mode"], "pilot");
  assert.equal(headers["x-uroflow-endpoint-set"], "clinical_hub_v1");
  assert.equal(headers["x-uroflow-data-residency-region"], "us");
  assert.equal(headers["x-uroflow-data-residency-boundary"], "single_region");
  assert.equal(headers["x-uroflow-region-match-required"], "true");
});

test("buildRequestHeaders creates a request id fallback without leaking empty headers", () => {
  const headers = clinicalHub.buildRequestHeaders(false, {
    api_key: "",
    actor_role: "operator",
    site_id: "",
    operator_id: "",
  });
  assert.equal(headers["Content-Type"], undefined);
  assert.equal(headers["x-api-key"], undefined);
  assert.equal(headers["x-site-id"], undefined);
  assert.equal(headers["x-operator-id"], undefined);
  assert.equal(headers["x-actor-role"], "operator");
  assert.equal(headers["x-uroflow-data-residency-region"], "us");
  assert.match(headers["x-request-id"], /^PENDING-\d+-[a-z0-9]+$/);
});
