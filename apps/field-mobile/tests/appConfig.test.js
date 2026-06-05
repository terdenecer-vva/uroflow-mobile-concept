const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const appConfig = require(path.join(buildDir, "config/appConfig.js"));

test("app runtime config defines pilot defaults and privacy-by-default switches", () => {
  assert.equal(appConfig.APP_RUNTIME_MODE, "pilot");
  assert.equal(appConfig.APP_DEFAULT_CAPTURE_MODE, "water_impact");
  assert.equal(appConfig.APP_STORE_RAW_VIDEO, false);
  assert.equal(appConfig.APP_STORE_RAW_AUDIO, false);
  assert.equal(appConfig.APP_ROI_ONLY, true);
  assert.deepEqual(appConfig.APP_PRIVACY_POLICY, {
    storeRawVideo: false,
    storeRawAudio: false,
    roiOnly: true,
  });
  assert.deepEqual(appConfig.APP_RUNTIME_CONFIG, {
    runtimeMode: "pilot",
    defaultCaptureMode: "water_impact",
    privacyPolicy: appConfig.APP_PRIVACY_POLICY,
  });
});
