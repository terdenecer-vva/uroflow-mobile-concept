const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const appConfig = require(path.join(buildDir, "config/appConfig.js"));

test("app runtime config defines pilot endpoints, privacy defaults, and debug gates", () => {
  assert.equal(appConfig.APP_RUNTIME_MODE, "pilot");
  assert.equal(appConfig.APP_ENDPOINT_SET, "clinical_hub_v1");
  assert.equal(appConfig.APP_DEFAULT_CAPTURE_MODE, "water_impact");
  assert.equal(
    appConfig.APP_PAIRED_MEASUREMENTS_ENDPOINT_PATH,
    "/api/v1/paired-measurements",
  );
  assert.equal(appConfig.APP_CAPTURE_PACKAGES_ENDPOINT_PATH, "/api/v1/capture-packages");
  assert.equal(appConfig.APP_STORE_RAW_VIDEO, false);
  assert.equal(appConfig.APP_STORE_RAW_AUDIO, false);
  assert.equal(appConfig.APP_ROI_ONLY, true);
  assert.equal(appConfig.APP_ALLOW_DEBUG_CONTROLS, false);
  assert.equal(appConfig.APP_ALLOW_RAW_RESPONSE_DETAILS, false);
  assert.equal(appConfig.APP_ENABLE_VERBOSE_LOGGING, false);
  assert.deepEqual(appConfig.APP_ENDPOINT_PATHS, {
    paired_measurements: "/api/v1/paired-measurements",
    capture_packages: "/api/v1/capture-packages",
  });
  assert.deepEqual(appConfig.APP_PRIVACY_POLICY, {
    storeRawVideo: false,
    storeRawAudio: false,
    roiOnly: true,
  });
  assert.deepEqual(appConfig.APP_DEBUG_GATES, {
    allowDebugControls: false,
    allowRawResponseDetails: false,
    enableVerboseLogging: false,
  });
  assert.deepEqual(appConfig.APP_RUNTIME_CONFIG, {
    runtimeMode: "pilot",
    endpointSet: "clinical_hub_v1",
    endpointPaths: appConfig.APP_ENDPOINT_PATHS,
    defaultCaptureMode: "water_impact",
    privacyPolicy: appConfig.APP_PRIVACY_POLICY,
    debugGates: appConfig.APP_DEBUG_GATES,
  });
});
