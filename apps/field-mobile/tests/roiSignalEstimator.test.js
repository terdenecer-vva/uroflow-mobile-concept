const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const roi = require(path.join(buildDir, "capture/roiSignalEstimator.js"));

const texturedFrame =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".repeat(16);

test("estimateRoiSignalFromBase64 rejects low-texture frames", () => {
  const signal = roi.estimateRoiSignalFromBase64({
    frameBase64: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    prevHash: null,
    prevLength: null,
  });

  assert.equal(signal.frameLength, 32);
  assert.equal(signal.motionProxy, 0);
  assert.equal(signal.textureProxy, 0);
  assert.equal(signal.roiValid, false);
});

test("estimateRoiSignalFromBase64 accepts textured stable frames", () => {
  const signal = roi.estimateRoiSignalFromBase64({
    frameBase64: texturedFrame,
    prevHash: null,
    prevLength: null,
  });

  assert.ok(signal.textureProxy > 0.18);
  assert.equal(signal.motionProxy, 0);
  assert.equal(signal.roiValid, true);
});

test("estimateRoiSignalFromBase64 is deterministic for the same frame", () => {
  const first = roi.estimateRoiSignalFromBase64({
    frameBase64: texturedFrame,
    prevHash: null,
    prevLength: null,
  });
  const second = roi.estimateRoiSignalFromBase64({
    frameBase64: texturedFrame,
    prevHash: first.frameHash,
    prevLength: first.frameLength,
  });

  assert.equal(second.frameHash, first.frameHash);
  assert.equal(second.frameLength, first.frameLength);
  assert.equal(second.motionProxy, 0);
  assert.equal(second.roiValid, true);
});

test("estimateRoiSignalFromBase64 rejects high-motion frame transitions", () => {
  const signal = roi.estimateRoiSignalFromBase64({
    frameBase64: texturedFrame,
    prevHash: 0,
    prevLength: 1,
  });

  assert.equal(signal.motionProxy, 1);
  assert.equal(signal.roiValid, false);
});
