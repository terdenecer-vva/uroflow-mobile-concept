const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const captureModePolicy = require(path.join(buildDir, "utils/captureModePolicy.js"));

function runtimePayload(captureMode) {
  return {
    session: {
      mode: captureMode,
    },
  };
}

test("normalizeCaptureMode canonicalizes operator-entered capture modes", () => {
  assert.equal(captureModePolicy.normalizeCaptureMode(" Water_Impact "), "water_impact");
  assert.equal(captureModePolicy.normalizeCaptureMode("fallback_nonwater"), "fallback_nonwater");
  assert.equal(captureModePolicy.normalizeCaptureMode(null), "");
});

test("extractRuntimeCaptureMode reads runtime contract session mode", () => {
  assert.equal(
    captureModePolicy.extractRuntimeCaptureMode(runtimePayload(" Water_Impact ")),
    "water_impact",
  );
  assert.equal(
    captureModePolicy.extractRuntimeCaptureMode(runtimePayload("fallback_nonwater")),
    "fallback_nonwater",
  );
  assert.equal(captureModePolicy.extractRuntimeCaptureMode({ session: {} }), null);
  assert.equal(captureModePolicy.extractRuntimeCaptureMode(null), null);
});

test("capture mode submission guard allows only water_impact pilot mode", () => {
  assert.equal(captureModePolicy.buildCaptureModeSubmissionError("water_impact"), null);
  assert.match(
    captureModePolicy.buildCaptureModeSubmissionError("fallback_nonwater"),
    /capture_mode must be water_impact/,
  );
  assert.match(
    captureModePolicy.buildCaptureModeSubmissionError(
      "water_impact",
      runtimePayload("fallback_nonwater"),
    ),
    /Runtime capture mode is fallback_nonwater/,
  );
  assert.match(
    captureModePolicy.buildCaptureModeSubmissionError(" "),
    /capture_mode is required/,
  );
});

test("capture mode warning surfaces unsupported pilot modes before submission", () => {
  assert.equal(captureModePolicy.buildCaptureModeSubmissionWarning("water_impact"), null);
  assert.match(
    captureModePolicy.buildCaptureModeSubmissionWarning("jet_in_air"),
    /outside the validated water_impact pilot workflow/,
  );
  assert.match(
    captureModePolicy.buildCaptureModeSubmissionWarning(""),
    /set capture_mode=water_impact/,
  );
});
