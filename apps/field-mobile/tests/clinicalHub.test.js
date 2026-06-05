const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const clinicalHub = require(path.join(buildDir, "api/clinicalHub.js"));

function buildPayload() {
  return {
    session: {
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
    },
  };
}

test("buildBaseUrl and endpointPath normalize Clinical Hub targets", () => {
  assert.equal(clinicalHub.buildBaseUrl("https://clinical.example.test/"), "https://clinical.example.test");
  assert.equal(clinicalHub.buildBaseUrl("https://clinical.example.test"), "https://clinical.example.test");
  assert.equal(clinicalHub.endpointPath("paired_measurements"), "/api/v1/paired-measurements");
  assert.equal(clinicalHub.endpointPath("capture_packages"), "/api/v1/capture-packages");
});

test("attemptSubmitEndpoint posts serialized payloads with request headers", async () => {
  const originalFetch = global.fetch;
  try {
    global.fetch = async (url, init) => {
      assert.equal(url, "https://clinical.example.test/api/v1/paired-measurements");
      assert.equal(init.method, "POST");
      assert.equal(init.headers["Content-Type"], "application/json");
      assert.equal(init.headers["x-api-key"], "secret-key");
      assert.equal(init.headers["x-actor-role"], "operator");
      assert.equal(init.headers["x-site-id"], "SITE-001");
      assert.equal(init.headers["x-operator-id"], "OP-001");
      assert.equal(init.headers["x-request-id"], "REQ-001");
      assert.deepEqual(JSON.parse(init.body), buildPayload());
      return new Response('{"id": 17}', { status: 201 });
    };

    const result = await clinicalHub.attemptSubmitEndpoint({
      apiBaseUrl: "https://clinical.example.test/",
      requestTimeoutMs: "15000",
      endpoint: "paired_measurements",
      endpointPayload: buildPayload(),
      headerContext: {
        api_key: "secret-key",
        actor_role: "operator",
        site_id: "SITE-001",
        operator_id: "OP-001",
        request_id: "REQ-001",
      },
    });

    assert.deepEqual(result, {
      ok: true,
      statusCode: 201,
      body: '{"id": 17}',
      retryable: false,
    });
  } finally {
    global.fetch = originalFetch;
  }
});

test("attemptSubmitEndpoint marks validation responses non-retryable", async () => {
  const originalFetch = global.fetch;
  try {
    global.fetch = async () => new Response("validation error", { status: 422 });

    const result = await clinicalHub.attemptSubmitEndpoint({
      apiBaseUrl: "https://clinical.example.test",
      requestTimeoutMs: "15000",
      endpoint: "capture_packages",
      endpointPayload: buildPayload(),
      headerContext: {
        api_key: "",
        actor_role: "operator",
        site_id: "",
        operator_id: "",
        request_id: "REQ-422",
      },
    });

    assert.deepEqual(result, {
      ok: false,
      statusCode: 422,
      body: "validation error",
      retryable: false,
    });
  } finally {
    global.fetch = originalFetch;
  }
});

test("attemptSubmitEndpoint keeps network failures retryable", async () => {
  const originalFetch = global.fetch;
  try {
    global.fetch = async () => {
      throw new Error("failed to fetch");
    };

    const result = await clinicalHub.attemptSubmitEndpoint({
      apiBaseUrl: "https://clinical.example.test",
      requestTimeoutMs: "15000",
      endpoint: "paired_measurements",
      endpointPayload: buildPayload(),
      headerContext: {
        api_key: "",
        actor_role: "operator",
        site_id: "",
        operator_id: "",
        request_id: "REQ-NETWORK",
      },
    });

    assert.equal(result.ok, false);
    assert.equal(result.statusCode, null);
    assert.equal(result.retryable, true);
    assert.match(result.body, /failed to fetch/);
  } finally {
    global.fetch = originalFetch;
  }
});
