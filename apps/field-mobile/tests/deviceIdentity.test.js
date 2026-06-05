const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const deviceIdentity = require(path.join(buildDir, "utils/deviceIdentity.js"));

test("buildDeviceModelLabel prefers Expo Device model name", () => {
  assert.equal(
    deviceIdentity.buildDeviceModelLabel({
      platform: "ios",
      modelName: " iPhone 15 Pro ",
      manufacturer: "Apple",
      brand: "Apple",
    }),
    "iPhone 15 Pro",
  );
});

test("buildDeviceModelLabel falls back to manufacturer and brand", () => {
  assert.equal(
    deviceIdentity.buildDeviceModelLabel({
      platform: "android",
      modelName: "",
      manufacturer: " Google ",
      brand: " Pixel ",
    }),
    "Google Pixel",
  );
  assert.equal(
    deviceIdentity.buildDeviceModelLabel({
      platform: "android",
      modelName: null,
      manufacturer: "Google",
      brand: "google",
    }),
    "Google",
  );
});

test("buildDeviceModelLabel uses platform fallback when device details are unavailable", () => {
  assert.equal(
    deviceIdentity.buildDeviceModelLabel({
      platform: "android",
      modelName: null,
      manufacturer: null,
      brand: null,
    }),
    "android-device",
  );
});

test("buildDeviceOsVersion prefers Expo Device OS name and version", () => {
  assert.equal(
    deviceIdentity.buildDeviceOsVersion({
      platform: "ios",
      osName: " iOS ",
      osVersion: " 18.3 ",
      platformVersion: "18.3",
    }),
    "iOS 18.3",
  );
  assert.equal(
    deviceIdentity.buildDeviceOsVersion({
      platform: "android",
      osName: null,
      osVersion: "15",
      platformVersion: "35",
    }),
    "15",
  );
  assert.equal(
    deviceIdentity.buildDeviceOsVersion({
      platform: "android",
      osName: null,
      osVersion: null,
      platformVersion: 35,
    }),
    "35",
  );
});
