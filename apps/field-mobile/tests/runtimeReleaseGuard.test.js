const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const runtimeReleaseGuard = require(path.join(buildDir, "config/runtimeReleaseGuard.js"));
const appConfig = require(path.join(buildDir, "config/appConfig.js"));
const releaseMetadata = require(path.join(buildDir, "config/releaseMetadata.js"));

function cloneRuntimeConfig(overrides = {}) {
  return {
    ...appConfig.APP_RUNTIME_CONFIG,
    endpointPaths: { ...appConfig.APP_RUNTIME_CONFIG.endpointPaths },
    privacyPolicy: { ...appConfig.APP_RUNTIME_CONFIG.privacyPolicy },
    dataResidencyPolicy: { ...appConfig.APP_RUNTIME_CONFIG.dataResidencyPolicy },
    debugGates: { ...appConfig.APP_RUNTIME_CONFIG.debugGates },
    ...overrides,
  };
}

test("runtime release guard passes canonical release metadata and runtime config", () => {
  const guard = runtimeReleaseGuard.buildRuntimeReleaseGuard();

  assert.equal(guard.status, "pass");
  assert.deepEqual(guard.blockers, []);
  assert.match(guard.message, /Runtime release guard passed/);
  assert.match(guard.evidence, /capture_schema=ios_capture_v1/);
  assert.match(guard.evidence, /endpoint_set=clinical_hub_v1/);
  assert.equal(runtimeReleaseGuard.isRuntimeReleaseGuardActionAllowed(guard), true);
});

test("runtime release guard blocks unsupported capture schema", () => {
  const guard = runtimeReleaseGuard.buildRuntimeReleaseGuard({
    releaseMetadata: {
      ...releaseMetadata.APP_RELEASE_METADATA,
      captureSchemaVersion: "ios_capture_v2_experimental",
    },
  });

  assert.equal(guard.status, "blocked");
  assert.deepEqual(guard.blockers, ["capture_schema_unsupported"]);
  assert.match(guard.message, /capture_schema_unsupported/);
  assert.equal(runtimeReleaseGuard.isRuntimeReleaseGuardActionAllowed(guard), false);
});

test("runtime release guard blocks unsafe endpoint privacy and residency config", () => {
  const guard = runtimeReleaseGuard.buildRuntimeReleaseGuard({
    runtimeConfig: cloneRuntimeConfig({
      endpointSet: "debug_hub_v0",
      privacyPolicy: {
        storeRawVideo: true,
        storeRawAudio: false,
        roiOnly: false,
      },
      dataResidencyPolicy: {
        region: "eu",
        boundary: "multi_region",
        allowCrossRegionSync: true,
        requireRegionMatchedClinicalHub: false,
      },
      debugGates: {
        allowDebugControls: true,
        allowRawResponseDetails: false,
        enableVerboseLogging: false,
      },
    }),
  });

  assert.equal(guard.status, "blocked");
  assert.deepEqual(guard.blockers, [
    "endpoint_set_mismatch",
    "privacy_policy_mismatch",
    "data_residency_policy_mismatch",
    "debug_gates_enabled",
  ]);
  assert.match(guard.evidence, /endpoint_set=debug_hub_v0/);
  assert.match(guard.evidence, /data_residency=eu\/multi_region/);
});
