const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const preflight = require(path.join(buildDir, "api/clinicalHubPreflight.js"));

test("blocks missing Clinical Hub URL before field actions", () => {
  const result = preflight.buildClinicalHubPreflight(" ");

  assert.equal(result.status, "blocked");
  assert.equal(result.code, "missing_url");
  assert.equal(
    result.message,
    "Configure Clinical Hub API Base URL before testing, submitting, or syncing.",
  );
  assert.equal(preflight.isClinicalHubPreflightActionAllowed(result), false);
});

test("blocks Clinical Hub URLs without supported protocol", () => {
  const result = preflight.buildClinicalHubPreflight("clinical.example.test");

  assert.equal(result.status, "blocked");
  assert.equal(result.code, "unsupported_url");
  assert.equal(preflight.isClinicalHubPreflightActionAllowed(result), false);
});

test("allows local Clinical Hub smoke URLs with warning", () => {
  const result = preflight.buildClinicalHubPreflight("http://192.168.1.20:8000/");

  assert.equal(result.status, "warning");
  assert.equal(result.code, "local_dev");
  assert.equal(result.normalizedBaseUrl, "http://192.168.1.20:8000");
  assert.equal(preflight.isClinicalHubPreflightActionAllowed(result), true);
  assert.equal(
    preflight.buildClinicalHubPreflight("http://[::1]:8000").code,
    "local_dev",
  );
});

test("passes obvious region-matched HTTPS Clinical Hub URLs", () => {
  const result = preflight.buildClinicalHubPreflight("https://clinical-us.example.test");

  assert.equal(result.status, "pass");
  assert.equal(result.code, "configured");
  assert.equal(result.expectedRegion, "us");
  assert.equal(result.inferredRegion, "us");
  assert.equal(preflight.isClinicalHubPreflightActionAllowed(result), true);
});

test("blocks obvious cross-region Clinical Hub URLs", () => {
  const result = preflight.buildClinicalHubPreflight("https://clinical-eu.example.test");

  assert.equal(result.status, "blocked");
  assert.equal(result.code, "region_mismatch");
  assert.equal(result.expectedRegion, "us");
  assert.equal(result.inferredRegion, "eu");
  assert.match(result.message, /requires us/);
  assert.equal(preflight.isClinicalHubPreflightActionAllowed(result), false);
});

test("warns when Clinical Hub URL region is not obvious", () => {
  const result = preflight.buildClinicalHubPreflight("https://clinical.example.test");

  assert.equal(result.status, "warning");
  assert.equal(result.code, "region_unknown");
  assert.equal(result.inferredRegion, null);
  assert.equal(preflight.isClinicalHubPreflightActionAllowed(result), true);
});
