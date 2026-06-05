const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const capture = require(path.join(buildDir, "capture/buildCaptureContract.js"));

function assertDerivativesOnlyFeatureManifest(payload, source) {
  assert.equal(payload.feature_manifest.version, "mobile_feature_manifest_v0.1");
  assert.equal(payload.feature_manifest.source, source);
  assert.equal(payload.feature_manifest.derivatives_only, true);
  assert.equal(payload.feature_manifest.sample_count, payload.samples.length);
  assert.deepEqual(payload.feature_manifest.raw_media, {
    store_raw_video: false,
    store_raw_audio: false,
    upload_raw_video: false,
    upload_raw_audio: false,
  });
  assert.deepEqual(payload.feature_manifest.privacy, {
    roi_only: true,
    media_scope: "roi_derivatives_only",
  });
  assert.equal(payload.feature_manifest.feature_keys.includes("audio_rms_dbfs"), true);
  assert.equal(payload.feature_manifest.feature_keys.includes("motion_norm"), true);
  assert.equal(payload.feature_manifest.feature_keys.includes("roi_valid"), true);
}

test("buildCaptureContractPayload creates privacy-preserving scaffold payloads", () => {
  const payload = capture.buildCaptureContractPayload({
    sessionId: "SESSION-001",
    syncId: "SYNC-001",
    startedAtIso: "2026-06-04T01:02:03Z",
    captureMode: "water_impact",
    deviceModel: " iPhone 15 ",
    iosVersion: "19.0",
    appVersion: " 0.1.0 ",
    qmaxMlS: 12.5,
    qavgMlS: 8.1,
    flowTimeS: 4,
  });

  assert.equal(payload.schema_version, "ios_capture_v1");
  assert.equal(payload.session.session_id, "SESSION-001");
  assert.equal(payload.session.sync_id, "SYNC-001");
  assert.equal(payload.session.started_at, "2026-06-04T01:02:03.000Z");
  assert.equal(payload.session.device.model, "iPhone 15");
  assert.deepEqual(payload.session.privacy, {
    store_raw_video: false,
    store_raw_audio: false,
    roi_only: true,
  });
  assert.equal(payload.session.calibration.ml_per_mm, 8);
  assert.equal(payload.session.calibration.min_depth_confidence, 0.6);
  assert.ok(payload.samples.length >= 8);
  assert.equal(payload.samples.every((sample) => sample.roi_valid === true), true);
  assert.equal(payload.samples.every((sample) => sample.t_s >= 0), true);
  assertDerivativesOnlyFeatureManifest(payload, "mobile_scaffold");
});

test("buildCaptureContractPayloadFromSamples creates fallback samples for empty runtime input", () => {
  const payload = capture.buildCaptureContractPayloadFromSamples({
    sessionId: "SESSION-EMPTY",
    syncId: null,
    startedAtIso: "2026-06-04T01:02:03Z",
    captureMode: "water_impact",
    deviceModel: "",
    iosVersion: "android-16",
    appVersion: "",
    samples: [],
    minDepthConfidence: 0.7,
    cameraDistanceMm: 700,
    sourceLabel: " runtime-audio-imu ",
  });

  assert.equal(payload.session.device.model, "unknown-device-runtime-audio-imu");
  assert.equal(payload.session.app.version, "0.1.0");
  assert.equal(payload.session.calibration.min_depth_confidence, 0.7);
  assert.equal(payload.session.calibration.camera_distance_mm, 700);
  assert.equal(payload.samples.length, 2);
  assert.deepEqual(
    payload.samples.map((sample) => sample.t_s),
    [0, 0.5],
  );
  assert.deepEqual(payload.analysis.runtime_timeline, {
    clock_source: "elapsed_wall_clock_ms",
    sample_count: 2,
    duration_s: 0.5,
    median_sample_step_s: 0.5,
    max_sample_gap_s: 0.5,
    max_sample_gap_ratio: 1,
    monotonic: true,
    gap_warning: false,
  });
  assertDerivativesOnlyFeatureManifest(payload, "runtime-audio-imu");
});

test("buildCaptureContractPayloadFromSamples duplicates one-sample runtime captures safely", () => {
  const payload = capture.buildCaptureContractPayloadFromSamples({
    sessionId: "SESSION-ONE",
    syncId: "SYNC-ONE",
    startedAtIso: "2026-06-04T01:02:03Z",
    captureMode: "water_impact",
    deviceModel: "Pixel",
    iosVersion: "android-16",
    appVersion: "0.1.0",
    samples: [
      {
        t_s: 7,
        depth_level_mm: 1.23456,
        rgb_level_mm: 1.1,
        depth_confidence: 0.91,
        audio_rms_dbfs: -42,
        motion_norm: 0.03,
        roi_valid: true,
      },
    ],
  });

  assert.equal(payload.samples.length, 2);
  assert.equal(payload.samples[0].t_s, 0);
  assert.equal(payload.samples[1].t_s, 0.5);
  assert.equal(payload.samples[1].depth_level_mm, 1.2346);
});

test("buildCaptureContractPayloadFromSamples sanitizes malformed runtime samples", () => {
  const payload = capture.buildCaptureContractPayloadFromSamples({
    sessionId: "SESSION-SANITIZE",
    syncId: "SYNC-SANITIZE",
    startedAtIso: "2026-06-04T01:02:03Z",
    captureMode: "water_impact",
    deviceModel: "iPhone",
    iosVersion: "19.0",
    appVersion: "0.1.0",
    samples: [
      {
        t_s: 2.123456,
        depth_level_mm: -1,
        rgb_level_mm: Number.POSITIVE_INFINITY,
        depth_confidence: 2,
        audio_rms_dbfs: 6,
        motion_norm: 2,
        roi_valid: "yes",
      },
      {
        t_s: -1,
        depth_level_mm: 99,
        rgb_level_mm: 99,
        depth_confidence: 0.9,
        audio_rms_dbfs: -30,
        motion_norm: 0.1,
        roi_valid: true,
      },
      {
        t_s: 0.5,
        depth_level_mm: Number.NaN,
        rgb_level_mm: 0.123456,
        depth_confidence: Number.NaN,
        audio_rms_dbfs: Number.NaN,
        motion_norm: Number.NaN,
        roi_valid: true,
      },
    ],
  });

  assert.deepEqual(payload.samples, [
    {
      t_s: 0.5,
      depth_level_mm: null,
      rgb_level_mm: 0.1235,
      depth_confidence: 0,
      audio_rms_dbfs: -120,
      motion_norm: 1,
      roi_valid: true,
    },
    {
      t_s: 2.1235,
      depth_level_mm: 0,
      rgb_level_mm: null,
      depth_confidence: 1,
      audio_rms_dbfs: 0,
      motion_norm: 1,
      roi_valid: false,
    },
  ]);
});

test("buildCaptureContractPayloadFromSamples sanitizes runtime analysis", () => {
  const flowSeries = Array.from({ length: 130 }, (_, index) => ({
    t_s: index / 10,
    flow_ml_s: index === 3 ? -10 : index,
  }));
  flowSeries.push({ t_s: -1, flow_ml_s: 99 });
  flowSeries.push({ t_s: Number.POSITIVE_INFINITY, flow_ml_s: 99 });

  const payload = capture.buildCaptureContractPayloadFromSamples({
    sessionId: "SESSION-ANALYSIS",
    syncId: "SYNC-ANALYSIS",
    startedAtIso: "2026-06-04T01:02:03Z",
    captureMode: "water_impact",
    deviceModel: "iPhone",
    iosVersion: "19.0",
    appVersion: "0.1.0",
    samples: [
      {
        t_s: 0,
        depth_level_mm: 0,
        rgb_level_mm: 0,
        depth_confidence: 0.9,
        audio_rms_dbfs: -45,
        motion_norm: 0.02,
        roi_valid: true,
      },
      {
        t_s: 0.5,
        depth_level_mm: 0.2,
        rgb_level_mm: 0.19,
        depth_confidence: 0.8,
        audio_rms_dbfs: -44,
        motion_norm: 0.03,
        roi_valid: true,
      },
    ],
    analysis: {
      runtime_flow_series: flowSeries,
      runtime_quality: {
        quality_score: -5,
        quality_status: "repeat",
        roi_valid_ratio: 2,
        low_confidence_ratio: -1,
        high_motion_ratio: 1.5,
        timing_gap_warning: true,
      },
    },
  });

  assert.ok(payload.analysis);
  assert.ok(payload.analysis.runtime_flow_series.length <= 121);
  assert.deepEqual(payload.analysis.runtime_flow_series.at(-1), {
    t_s: 12.9,
    flow_ml_s: 129,
  });
  assert.equal(
    payload.analysis.runtime_flow_series.some((point) => point.t_s < 0),
    false,
  );
  assert.deepEqual(payload.analysis.runtime_quality, {
    quality_score: 0,
    quality_status: "repeat",
    roi_valid_ratio: 1,
    low_confidence_ratio: 0,
    high_motion_ratio: 1,
    timing_gap_warning: true,
  });
  assertDerivativesOnlyFeatureManifest(payload, "runtime-audio-imu-camera-proxy");
  assert.equal(
    payload.feature_manifest.feature_keys.includes("runtime_flow_series.flow_ml_s"),
    true,
  );
  assert.equal(
    payload.feature_manifest.feature_keys.includes("runtime_quality.high_motion_ratio"),
    true,
  );
  assert.equal(
    payload.feature_manifest.feature_keys.includes("runtime_quality.timing_gap_warning"),
    true,
  );
});

test("buildCaptureContractPayloadFromSamples adds runtime timeline analysis", () => {
  const payload = capture.buildCaptureContractPayloadFromSamples({
    sessionId: "SESSION-TIMELINE",
    syncId: "SYNC-TIMELINE",
    startedAtIso: "2026-06-04T01:02:03Z",
    captureMode: "water_impact",
    deviceModel: "Pixel",
    iosVersion: "android-16",
    appVersion: "0.1.0",
    samples: [
      {
        t_s: 0,
        depth_level_mm: 0,
        rgb_level_mm: 0,
        depth_confidence: 0.9,
        audio_rms_dbfs: -45,
        motion_norm: 0.02,
        roi_valid: true,
      },
      {
        t_s: 0.5,
        depth_level_mm: 0.2,
        rgb_level_mm: 0.19,
        depth_confidence: 0.8,
        audio_rms_dbfs: -44,
        motion_norm: 0.03,
        roi_valid: true,
      },
      {
        t_s: 0.99,
        depth_level_mm: 0.3,
        rgb_level_mm: 0.28,
        depth_confidence: 0.82,
        audio_rms_dbfs: -42,
        motion_norm: 0.04,
        roi_valid: true,
      },
      {
        t_s: 3.5,
        depth_level_mm: 0.8,
        rgb_level_mm: 0.76,
        depth_confidence: 0.78,
        audio_rms_dbfs: -41,
        motion_norm: 0.05,
        roi_valid: true,
      },
    ],
  });

  assert.deepEqual(payload.analysis.runtime_timeline, {
    clock_source: "elapsed_wall_clock_ms",
    sample_count: 4,
    duration_s: 3.5,
    median_sample_step_s: 0.5,
    max_sample_gap_s: 2.51,
    max_sample_gap_ratio: 5.02,
    monotonic: true,
    gap_warning: true,
  });
  assert.equal(
    payload.feature_manifest.feature_keys.includes("runtime_timeline.max_sample_gap_s"),
    true,
  );
  assert.equal(
    payload.feature_manifest.feature_keys.includes("runtime_timeline.clock_source"),
    true,
  );
});
