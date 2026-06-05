const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const settings = require(path.join(buildDir, "storage/appSettingsStorage.js"));

test("default app settings do not point release devices at localhost", () => {
  assert.equal(settings.DEFAULT_API_BASE_URL, "");
});

test("parseStoredAppSettings builds defaults when only secure API key remains", () => {
  assert.deepEqual(settings.parseStoredAppSettings(null, "secure-key"), {
    api_base_url: settings.DEFAULT_API_BASE_URL,
    api_key: "secure-key",
    actor_role: "operator",
    site_id: settings.DEFAULT_SITE_ID,
    operator_id: settings.DEFAULT_OPERATOR_ID,
    summary_quality_status: "valid",
    summary_sync_id: "",
    request_timeout_ms: "15000",
  });
});

test("parseStoredAppSettings normalizes migrated plain settings and prefers secure key", () => {
  const parsed = settings.parseStoredAppSettings(
    JSON.stringify({
      api_base_url: "   ",
      api_key: "plain-key",
      actor_role: " Admin ",
      site_id: 123,
      operator_id: null,
      summary_quality_status: "unknown",
      summary_sync_id: 456,
      request_timeout_ms: "",
    }),
    "secure-key",
  );

  assert.deepEqual(parsed, {
    api_base_url: settings.DEFAULT_API_BASE_URL,
    api_key: "secure-key",
    actor_role: "admin",
    site_id: settings.DEFAULT_SITE_ID,
    operator_id: settings.DEFAULT_OPERATOR_ID,
    summary_quality_status: "valid",
    summary_sync_id: "",
    request_timeout_ms: "15000",
  });
});

test("parseStoredAppSettings falls back to legacy plain API key when secure key is absent", () => {
  const parsed = settings.parseStoredAppSettings(
    JSON.stringify({
      api_base_url: "https://clinical.example.test",
      api_key: "legacy-plain-key",
      actor_role: "data_manager",
      site_id: "SITE-002",
      operator_id: "OP-99",
      summary_quality_status: "all",
      summary_sync_id: "SYNC-123",
      request_timeout_ms: "45000",
    }),
    "",
  );

  assert.equal(parsed.api_key, "legacy-plain-key");
  assert.equal(parsed.api_base_url, "https://clinical.example.test");
  assert.equal(parsed.actor_role, "data_manager");
  assert.equal(parsed.summary_quality_status, "all");
});

test("parseStoredAppSettings rejects invalid JSON and empty settings without secrets", () => {
  assert.equal(settings.parseStoredAppSettings("{broken", "secure-key"), null);
  assert.equal(settings.parseStoredAppSettings(null, ""), null);
});

test("buildPlainStoredAppSettings strips API key before AsyncStorage persistence", () => {
  const stored = settings.buildPlainStoredAppSettings(
    settings.buildDefaultAppSettings("secret-api-key"),
  );

  assert.equal(stored.api_key, "");
  assert.equal(stored.api_base_url, settings.DEFAULT_API_BASE_URL);
});
