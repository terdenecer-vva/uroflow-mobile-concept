const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const connectionCheck = require(path.join(buildDir, "api/connectionCheck.js"));

test("connection check URL builders normalize API base URL", () => {
  assert.equal(
    connectionCheck.buildAuthContextUrl("https://clinical.example.test/"),
    "https://clinical.example.test/api/v1/auth-context",
  );
  assert.equal(
    connectionCheck.buildHealthUrl("https://clinical.example.test"),
    "https://clinical.example.test/health",
  );
});

test("connection check failure messages preserve HTTP status and body", () => {
  assert.equal(
    connectionCheck.buildHealthCheckFailedMessage(503),
    "Health check failed: HTTP 503",
  );
  assert.equal(
    connectionCheck.buildAuthContextCheckFailedMessage(403, "forbidden"),
    "Auth-context check failed: HTTP 403 forbidden",
  );
});

test("buildAuthContextOkMessage summarizes actor context with n/a fallbacks", () => {
  assert.equal(
    connectionCheck.buildAuthContextOkMessage({
      auth_result: "api_key_valid",
      actor_role: null,
      actor_site_id: null,
      actor_operator_id: "OP-001",
      cross_site_allowed: false,
    }),
    "Auth context OK: auth=api_key_valid, role=n/a, site=n/a",
  );
});

test("buildApiCheckFailedMessage stringifies thrown errors", () => {
  assert.equal(
    connectionCheck.buildApiCheckFailedMessage(new Error("network down")),
    "API check failed: Error: network down",
  );
});
