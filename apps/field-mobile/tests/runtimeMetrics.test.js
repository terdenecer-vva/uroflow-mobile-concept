const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const runtime = require(path.join(buildDir, "capture/runtimeMetrics.js"));

function sample(overrides = {}) {
  return {
    t_s: 0,
    depth_level_mm: 0,
    rgb_level_mm: 0,
    depth_confidence: 0.9,
    audio_rms_dbfs: -45,
    motion_norm: 0.05,
    roi_valid: true,
    ...overrides,
  };
}

test("deriveRuntimeCaptureMetrics computes event bounds and flow metrics", () => {
  const metrics = runtime.deriveRuntimeCaptureMetrics({
    permissions: { cameraGranted: true },
    samples: [
      sample({ t_s: 0 }),
      sample({ t_s: 1 }),
      sample({ t_s: 2 }),
      sample({ t_s: 3 }),
      sample({ t_s: 4 }),
    ],
    flowSeries: [
      { t_s: 0, flow_ml_s: 0.5 },
      { t_s: 1, flow_ml_s: 2 },
      { t_s: 2, flow_ml_s: 4 },
      { t_s: 3, flow_ml_s: 1 },
      { t_s: 4, flow_ml_s: 0.4 },
    ],
  });

  assert.deepEqual(metrics, {
    qmaxMlS: 4,
    qavgMlS: 2.3333,
    vvoidMl: 7.45,
    flowTimeS: 2,
    tqmaxS: 1,
    eventStartTs: 1,
    eventEndTs: 3,
  });
});

test("deriveRuntimeCaptureMetrics uses ROI gates when enough valid ROI samples exist", () => {
  const metrics = runtime.deriveRuntimeCaptureMetrics({
    permissions: { cameraGranted: true },
    samples: [
      sample({ t_s: 0, roi_valid: false }),
      sample({ t_s: 1, roi_valid: true }),
      sample({ t_s: 2, roi_valid: true }),
      sample({ t_s: 3, roi_valid: true }),
    ],
    flowSeries: [
      { t_s: 0, flow_ml_s: 5 },
      { t_s: 1, flow_ml_s: 1.5 },
      { t_s: 2, flow_ml_s: 0.9 },
      { t_s: 3, flow_ml_s: 0.2 },
    ],
  });

  assert.equal(metrics.eventStartTs, 1);
  assert.equal(metrics.eventEndTs, 2);
  assert.equal(metrics.tqmaxS, 0);
});

test("deriveRuntimeCaptureMetrics falls back to flow-only bounds when ROI is unavailable", () => {
  const metrics = runtime.deriveRuntimeCaptureMetrics({
    permissions: { cameraGranted: true },
    samples: [
      sample({ t_s: 0, roi_valid: false }),
      sample({ t_s: 1, roi_valid: false }),
      sample({ t_s: 2, roi_valid: false }),
    ],
    flowSeries: [
      { t_s: 0, flow_ml_s: 2 },
      { t_s: 1, flow_ml_s: 1 },
      { t_s: 2, flow_ml_s: 0.1 },
    ],
  });

  assert.equal(metrics.eventStartTs, 0);
  assert.equal(metrics.eventEndTs, 1);
});

test("scoreRuntimeCaptureQuality classifies valid, repeat, and reject captures", () => {
  const valid = runtime.scoreRuntimeCaptureQuality({
    averageMotionNorm: 0.1,
    samples: [sample(), sample(), sample(), sample()],
  });
  assert.equal(valid.qualityStatus, "valid");
  assert.equal(valid.highMotionRatio, 0);

  const repeat = runtime.scoreRuntimeCaptureQuality({
    averageMotionNorm: 0.05,
    samples: [
      sample(),
      sample(),
      sample(),
      sample({ roi_valid: false }),
    ],
  });
  assert.equal(repeat.qualityStatus, "repeat");
  assert.equal(repeat.roiValidRatio, 0.75);

  const reject = runtime.scoreRuntimeCaptureQuality({
    averageMotionNorm: 0.05,
    samples: [
      sample(),
      sample({ roi_valid: false }),
      sample({ roi_valid: false }),
      sample({ roi_valid: false }),
    ],
  });
  assert.equal(reject.qualityStatus, "reject");
  assert.equal(reject.roiValidRatio, 0.25);
});

test("scoreRuntimeCaptureQuality gates high-motion capture artifacts", () => {
  const repeat = runtime.scoreRuntimeCaptureQuality({
    averageMotionNorm: 0.17,
    samples: [
      sample({ motion_norm: 0.05 }),
      sample({ motion_norm: 0.36 }),
      sample({ motion_norm: 0.06 }),
      sample({ motion_norm: 0.38 }),
      sample({ motion_norm: 0.08 }),
    ],
  });
  assert.equal(repeat.qualityStatus, "repeat");
  assert.equal(repeat.highMotionRatio, 0.4);

  const reject = runtime.scoreRuntimeCaptureQuality({
    averageMotionNorm: 0.24,
    samples: [
      sample({ motion_norm: 0.36 }),
      sample({ motion_norm: 0.37 }),
      sample({ motion_norm: 0.38 }),
      sample({ motion_norm: 0.05 }),
      sample({ motion_norm: 0.04 }),
    ],
  });
  assert.equal(reject.qualityStatus, "reject");
  assert.equal(reject.highMotionRatio, 0.6);
});

test("scoreRuntimeCaptureQuality repeats high low-confidence captures", () => {
  const quality = runtime.scoreRuntimeCaptureQuality({
    averageMotionNorm: 0.05,
    samples: [
      sample(),
      sample(),
      sample({ depth_confidence: 0.4 }),
      sample({ depth_confidence: 0.4 }),
      sample(),
    ],
  });

  assert.equal(quality.qualityStatus, "repeat");
  assert.equal(quality.lowConfidenceRatio, 0.4);
  assert.equal(quality.highMotionRatio, 0);
});

test("scoreRuntimeCaptureQuality repeats timing-gap captures", () => {
  const quality = runtime.scoreRuntimeCaptureQuality({
    averageMotionNorm: 0.02,
    samples: [sample(), sample(), sample(), sample()],
    timingGapWarning: true,
  });

  assert.equal(quality.qualityStatus, "repeat");
  assert.equal(quality.timingGapWarning, true);
  assert.equal(quality.qualityScore, 83.4);
});

test("scoreRuntimeCaptureQuality rejects alignment drift hard failures", () => {
  const quality = runtime.scoreRuntimeCaptureQuality({
    averageMotionNorm: 0.02,
    samples: [sample(), sample(), sample(), sample()],
    alignmentDriftWarning: true,
  });

  assert.equal(quality.qualityStatus, "reject");
  assert.equal(quality.alignmentDriftWarning, true);
  assert.equal(quality.timingGapWarning, false);
});

test("calculateAverageMotionNorm handles empty samples", () => {
  assert.equal(runtime.calculateAverageMotionNorm([]), 0);
  assert.equal(
    runtime.calculateAverageMotionNorm([
      sample({ motion_norm: 0.1 }),
      sample({ motion_norm: 0.3 }),
    ]),
    0.2,
  );
});

test("buildRuntimeCaptureReadiness blocks unsafe capture starts", () => {
  assert.deepEqual(
    runtime.buildRuntimeCaptureReadiness({
      cameraPermissionGranted: false,
      cameraPreviewReady: true,
      roiLocked: true,
      roiFrameCount: 1,
      roiFrameValid: true,
    }),
    {
      ready: false,
      code: "camera_permission_missing",
      message: "Grant camera permission before starting runtime capture.",
    },
  );
  assert.equal(
    runtime.buildRuntimeCaptureReadiness({
      cameraPermissionGranted: true,
      cameraPreviewReady: false,
      roiLocked: true,
      roiFrameCount: 1,
      roiFrameValid: true,
    }).code,
    "camera_preview_not_ready",
  );
  assert.equal(
    runtime.buildRuntimeCaptureReadiness({
      cameraPermissionGranted: true,
      cameraPreviewReady: true,
      roiLocked: false,
      roiFrameCount: 1,
      roiFrameValid: true,
    }).code,
    "roi_not_locked",
  );
  assert.equal(
    runtime.buildRuntimeCaptureReadiness({
      cameraPermissionGranted: true,
      cameraPreviewReady: true,
      roiLocked: true,
      roiFrameCount: 0,
      roiFrameValid: true,
    }).code,
    "roi_frame_not_validated",
  );
  assert.equal(
    runtime.buildRuntimeCaptureReadiness({
      cameraPermissionGranted: true,
      cameraPreviewReady: true,
      roiLocked: true,
      roiFrameCount: 2,
      roiFrameValid: false,
    }).code,
    "roi_frame_invalid",
  );
});

test("buildRuntimeCaptureReadiness allows validated ROI capture starts", () => {
  assert.deepEqual(
    runtime.buildRuntimeCaptureReadiness({
      cameraPermissionGranted: true,
      cameraPreviewReady: true,
      roiLocked: true,
      roiFrameCount: 2,
      roiFrameValid: true,
    }),
    {
      ready: true,
      code: "ready",
      message: "Runtime capture preflight ready.",
    },
  );
});
