import {
  APP_CAPTURE_SCHEMA_VERSION,
  APP_RELEASE_VERSION,
} from "../config/releaseMetadata";
import { APP_PRIVACY_POLICY } from "../config/appConfig";

export type CaptureContractSample = {
  t_s: number;
  depth_level_mm: number | null;
  rgb_level_mm: number | null;
  depth_confidence: number;
  audio_rms_dbfs: number;
  motion_norm: number;
  roi_valid: boolean;
};

export type CaptureContractQualityStatus = "valid" | "repeat" | "reject";

export type CaptureContractRuntimeFlowPoint = {
  t_s: number;
  flow_ml_s: number;
};

export type CaptureContractRuntimeTimeline = {
  clock_source: "elapsed_wall_clock_ms";
  sample_count: number;
  duration_s: number;
  median_sample_step_s: number | null;
  max_sample_gap_s: number | null;
  max_sample_gap_ratio: number | null;
  monotonic: boolean;
  gap_warning: boolean;
};

export type CaptureContractRuntimeAlignment = {
  schema_version: "runtime_stream_alignment_v0.1";
  aligned_streams: string[];
  sample_count: number;
  paired_sample_count: number;
  max_allowed_drift_ms: number;
  max_stream_drift_ms: number | null;
  drift_warning: boolean;
};

export type CaptureContractAnalysis = {
  runtime_flow_series?: CaptureContractRuntimeFlowPoint[];
  runtime_timeline?: CaptureContractRuntimeTimeline;
  runtime_alignment?: CaptureContractRuntimeAlignment;
  runtime_quality?: {
    quality_score?: number;
    quality_status?: CaptureContractQualityStatus;
    roi_valid_ratio?: number;
    low_confidence_ratio?: number;
    high_motion_ratio?: number;
    timing_gap_warning?: boolean;
    alignment_drift_warning?: boolean;
  };
};

export type CaptureContractFeatureManifest = {
  version: "mobile_feature_manifest_v0.1";
  source: string;
  derivatives_only: true;
  sample_count: number;
  feature_keys: string[];
  raw_media: {
    store_raw_video: false;
    store_raw_audio: false;
    upload_raw_video: false;
    upload_raw_audio: false;
  };
  privacy: {
    roi_only: true;
    media_scope: "roi_derivatives_only";
  };
};

export type CaptureContractPayload = {
  schema_version: typeof APP_CAPTURE_SCHEMA_VERSION;
  session: {
    session_id: string;
    sync_id: string | null;
    started_at: string;
    mode: string;
    device: {
      model: string;
      ios_version: string;
    };
    app: {
      version: string;
    };
    calibration: {
      ml_per_mm: number;
      min_depth_confidence: number;
      camera_distance_mm: number;
    };
    privacy: {
      store_raw_video: false;
      store_raw_audio: false;
      roi_only: true;
    };
  };
  feature_manifest: CaptureContractFeatureManifest;
  samples: CaptureContractSample[];
  analysis?: CaptureContractAnalysis;
};

export type BuildCaptureContractInput = {
  sessionId: string;
  syncId: string | null;
  startedAtIso: string;
  captureMode: string;
  deviceModel: string | null;
  iosVersion: string;
  appVersion: string | null;
  qmaxMlS: number | null;
  qavgMlS: number | null;
  flowTimeS: number | null;
};

export type BuildCaptureContractFromSamplesInput = {
  sessionId: string;
  syncId: string | null;
  startedAtIso: string;
  captureMode: string;
  deviceModel: string | null;
  iosVersion: string;
  appVersion: string | null;
  samples: CaptureContractSample[];
  minDepthConfidence?: number;
  cameraDistanceMm?: number;
  sourceLabel?: string;
  analysis?: CaptureContractAnalysis;
};

const DEFAULT_ML_PER_MM = 8.0;
const DEFAULT_SAMPLE_STEP_S = 0.5;
export const RUNTIME_ALIGNMENT_MAX_DRIFT_MS = 50;
const FEATURE_MANIFEST_VERSION = "mobile_feature_manifest_v0.1";
const BASE_FEATURE_KEYS = Object.freeze([
  "t_s",
  "depth_level_mm",
  "rgb_level_mm",
  "depth_confidence",
  "audio_rms_dbfs",
  "motion_norm",
  "roi_valid",
]);

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value));
}

function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

function median(values: number[]): number | null {
  if (values.length === 0) {
    return null;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const midpoint = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) {
    return sorted[midpoint];
  }
  return (sorted[midpoint - 1] + sorted[midpoint]) / 2;
}

function normalizeStartedAt(startedAtIso: string): string {
  const parsed = new Date(startedAtIso);
  if (Number.isNaN(parsed.getTime())) {
    return new Date().toISOString();
  }
  return parsed.toISOString();
}

function sanitizeRuntimeFlowSeries(
  flowSeries: CaptureContractRuntimeFlowPoint[] | undefined,
): CaptureContractRuntimeFlowPoint[] {
  if (!flowSeries || flowSeries.length === 0) {
    return [];
  }
  const finite = flowSeries
    .filter(
      (point) =>
        Number.isFinite(point.t_s) && Number.isFinite(point.flow_ml_s) && point.t_s >= 0,
    )
    .map((point) => ({ t_s: round4(point.t_s), flow_ml_s: round4(Math.max(0, point.flow_ml_s)) }));
  if (finite.length <= 120) {
    return finite;
  }
  const step = Math.ceil(finite.length / 120);
  const reduced: CaptureContractRuntimeFlowPoint[] = [];
  for (let index = 0; index < finite.length; index += step) {
    reduced.push(finite[index]);
  }
  const lastPoint = finite[finite.length - 1];
  const tailPoint = reduced[reduced.length - 1];
  if (tailPoint.t_s !== lastPoint.t_s || tailPoint.flow_ml_s !== lastPoint.flow_ml_s) {
    reduced.push(lastPoint);
  }
  return reduced;
}

function sanitizeNullablePositiveMetric(value: number | null | undefined): number | null {
  if (value == null || !Number.isFinite(value)) {
    return null;
  }
  return round4(Math.max(0, value));
}

function sanitizeNonNegativeInteger(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.round(value));
}

export function deriveRuntimeTimeline(
  samples: CaptureContractSample[],
): CaptureContractRuntimeTimeline {
  const timestamps = samples
    .map((sample) => sample.t_s)
    .filter((timestamp) => Number.isFinite(timestamp) && timestamp >= 0);
  const deltas: number[] = [];
  for (let index = 1; index < timestamps.length; index += 1) {
    deltas.push(timestamps[index] - timestamps[index - 1]);
  }

  const monotonic = deltas.every((delta) => delta > 0);
  const positiveDeltas = deltas.filter((delta) => delta > 0);
  const medianStep = median(positiveDeltas);
  const maxGap = positiveDeltas.length > 0 ? Math.max(...positiveDeltas) : null;
  const maxGapRatio =
    medianStep != null && medianStep > 0 && maxGap != null ? maxGap / medianStep : null;
  const duration =
    timestamps.length >= 2 ? timestamps[timestamps.length - 1] - timestamps[0] : 0;

  return {
    clock_source: "elapsed_wall_clock_ms",
    sample_count: samples.length,
    duration_s: round4(Math.max(0, duration)),
    median_sample_step_s: sanitizeNullablePositiveMetric(medianStep),
    max_sample_gap_s: sanitizeNullablePositiveMetric(maxGap),
    max_sample_gap_ratio: sanitizeNullablePositiveMetric(maxGapRatio),
    monotonic,
    gap_warning:
      !monotonic ||
      (maxGapRatio != null && maxGapRatio > 2.5) ||
      (maxGap != null && maxGap > 1.5),
  };
}

export function deriveRuntimeAlignment(
  samples: CaptureContractSample[],
  flowSeries: CaptureContractRuntimeFlowPoint[],
  maxAllowedDriftMs = RUNTIME_ALIGNMENT_MAX_DRIFT_MS,
): CaptureContractRuntimeAlignment {
  const pairedSampleCount = Math.min(samples.length, flowSeries.length);
  let maxStreamDriftMs: number | null = null;
  for (let index = 0; index < pairedSampleCount; index += 1) {
    const sampleTimestamp = samples[index].t_s;
    const flowTimestamp = flowSeries[index].t_s;
    if (!Number.isFinite(sampleTimestamp) || !Number.isFinite(flowTimestamp)) {
      continue;
    }
    const driftMs = Math.abs(sampleTimestamp - flowTimestamp) * 1000;
    maxStreamDriftMs =
      maxStreamDriftMs == null ? driftMs : Math.max(maxStreamDriftMs, driftMs);
  }

  const safeMaxAllowedDriftMs =
    Number.isFinite(maxAllowedDriftMs) && maxAllowedDriftMs > 0
      ? round4(maxAllowedDriftMs)
      : RUNTIME_ALIGNMENT_MAX_DRIFT_MS;
  const hasMismatchedPairs =
    pairedSampleCount === 0 || samples.length !== flowSeries.length;
  const exceedsDriftLimit =
    maxStreamDriftMs != null && maxStreamDriftMs > safeMaxAllowedDriftMs;

  return {
    schema_version: "runtime_stream_alignment_v0.1",
    aligned_streams: ["samples", "runtime_flow_series"],
    sample_count: samples.length,
    paired_sample_count: pairedSampleCount,
    max_allowed_drift_ms: safeMaxAllowedDriftMs,
    max_stream_drift_ms: sanitizeNullablePositiveMetric(maxStreamDriftMs),
    drift_warning: hasMismatchedPairs || exceedsDriftLimit,
  };
}

function sanitizeRuntimeTimeline(
  timeline: CaptureContractRuntimeTimeline | undefined,
): CaptureContractRuntimeTimeline | undefined {
  if (!timeline) {
    return undefined;
  }
  return {
    clock_source: "elapsed_wall_clock_ms",
    sample_count: sanitizeNonNegativeInteger(timeline.sample_count),
    duration_s: Number.isFinite(timeline.duration_s)
      ? round4(Math.max(0, timeline.duration_s))
      : 0,
    median_sample_step_s: sanitizeNullablePositiveMetric(timeline.median_sample_step_s),
    max_sample_gap_s: sanitizeNullablePositiveMetric(timeline.max_sample_gap_s),
    max_sample_gap_ratio: sanitizeNullablePositiveMetric(timeline.max_sample_gap_ratio),
    monotonic: timeline.monotonic === true,
    gap_warning: timeline.gap_warning === true,
  };
}

function sanitizeRuntimeAlignment(
  alignment: CaptureContractRuntimeAlignment | undefined,
  sampleCount: number,
): CaptureContractRuntimeAlignment | undefined {
  if (!alignment) {
    return undefined;
  }
  const maxAllowedDriftMs =
    Number.isFinite(alignment.max_allowed_drift_ms) && alignment.max_allowed_drift_ms > 0
      ? round4(alignment.max_allowed_drift_ms)
      : RUNTIME_ALIGNMENT_MAX_DRIFT_MS;
  const maxStreamDriftMs = sanitizeNullablePositiveMetric(alignment.max_stream_drift_ms);
  const pairedSampleCount = sanitizeNonNegativeInteger(alignment.paired_sample_count);
  const alignedStreams = Array.isArray(alignment.aligned_streams)
    ? alignment.aligned_streams
        .filter((stream): stream is string => typeof stream === "string" && stream.trim().length > 0)
        .map((stream) => stream.trim())
    : [];
  const driftWarning =
    alignment.drift_warning === true ||
    pairedSampleCount !== sampleCount ||
    (maxStreamDriftMs != null && maxStreamDriftMs > maxAllowedDriftMs);

  return {
    schema_version: "runtime_stream_alignment_v0.1",
    aligned_streams: alignedStreams.length > 0 ? alignedStreams : ["samples", "runtime_flow_series"],
    sample_count: sampleCount,
    paired_sample_count: pairedSampleCount,
    max_allowed_drift_ms: maxAllowedDriftMs,
    max_stream_drift_ms: maxStreamDriftMs,
    drift_warning: driftWarning,
  };
}

function sanitizeNullableLevel(value: number | null): number | null {
  if (value == null || !Number.isFinite(value)) {
    return null;
  }
  return round4(Math.max(0, value));
}

function sanitizeSample(sample: CaptureContractSample): CaptureContractSample | null {
  if (!Number.isFinite(sample.t_s) || sample.t_s < 0) {
    return null;
  }
  return {
    t_s: round4(sample.t_s),
    depth_level_mm: sanitizeNullableLevel(sample.depth_level_mm),
    rgb_level_mm: sanitizeNullableLevel(sample.rgb_level_mm),
    depth_confidence: Number.isFinite(sample.depth_confidence)
      ? round4(clamp(sample.depth_confidence, 0, 1))
      : 0,
    audio_rms_dbfs: Number.isFinite(sample.audio_rms_dbfs)
      ? round4(clamp(sample.audio_rms_dbfs, -120, 0))
      : -120,
    motion_norm: Number.isFinite(sample.motion_norm)
      ? round4(clamp(sample.motion_norm, 0, 1))
      : 1,
    roi_valid: sample.roi_valid === true,
  };
}

function sanitizeRuntimeSamples(samples: CaptureContractSample[]): CaptureContractSample[] {
  return samples
    .map((sample) => sanitizeSample(sample))
    .filter((sample): sample is CaptureContractSample => sample != null)
    .sort((a, b) => a.t_s - b.t_s);
}

function sanitizeAnalysis(
  analysis: CaptureContractAnalysis | undefined,
  fallbackTimeline?: CaptureContractRuntimeTimeline,
  fallbackSamples?: CaptureContractSample[],
): CaptureContractAnalysis | undefined {
  const runtimeFlowSeries = sanitizeRuntimeFlowSeries(analysis?.runtime_flow_series);
  const runtimeTimeline =
    sanitizeRuntimeTimeline(analysis?.runtime_timeline) ?? fallbackTimeline;
  const runtimeAlignment =
    sanitizeRuntimeAlignment(analysis?.runtime_alignment, fallbackSamples?.length ?? 0) ??
    (fallbackSamples && runtimeFlowSeries.length > 0
      ? deriveRuntimeAlignment(fallbackSamples, runtimeFlowSeries)
      : undefined);
  const runtimeQualityRaw = analysis?.runtime_quality;
  const runtimeQuality: CaptureContractAnalysis["runtime_quality"] = {};
  if (runtimeQualityRaw) {
    if (Number.isFinite(runtimeQualityRaw.quality_score)) {
      runtimeQuality.quality_score = round4(Math.max(0, runtimeQualityRaw.quality_score as number));
    }
    if (
      runtimeQualityRaw.quality_status === "valid" ||
      runtimeQualityRaw.quality_status === "repeat" ||
      runtimeQualityRaw.quality_status === "reject"
    ) {
      runtimeQuality.quality_status = runtimeQualityRaw.quality_status;
    }
    if (Number.isFinite(runtimeQualityRaw.roi_valid_ratio)) {
      runtimeQuality.roi_valid_ratio = round4(
        clamp(runtimeQualityRaw.roi_valid_ratio as number, 0, 1),
      );
    }
    if (Number.isFinite(runtimeQualityRaw.low_confidence_ratio)) {
      runtimeQuality.low_confidence_ratio = round4(
        clamp(runtimeQualityRaw.low_confidence_ratio as number, 0, 1),
      );
    }
    if (Number.isFinite(runtimeQualityRaw.high_motion_ratio)) {
      runtimeQuality.high_motion_ratio = round4(
        clamp(runtimeQualityRaw.high_motion_ratio as number, 0, 1),
      );
    }
    if (typeof runtimeQualityRaw.timing_gap_warning === "boolean") {
      runtimeQuality.timing_gap_warning = runtimeQualityRaw.timing_gap_warning;
    }
    if (typeof runtimeQualityRaw.alignment_drift_warning === "boolean") {
      runtimeQuality.alignment_drift_warning = runtimeQualityRaw.alignment_drift_warning;
    }
  }
  const hasRuntimeQuality = Object.keys(runtimeQuality).length > 0;
  if (!hasRuntimeQuality && runtimeFlowSeries.length === 0 && !runtimeTimeline && !runtimeAlignment) {
    return undefined;
  }
  return {
    ...(runtimeFlowSeries.length > 0 ? { runtime_flow_series: runtimeFlowSeries } : {}),
    ...(runtimeTimeline ? { runtime_timeline: runtimeTimeline } : {}),
    ...(runtimeAlignment ? { runtime_alignment: runtimeAlignment } : {}),
    ...(hasRuntimeQuality ? { runtime_quality: runtimeQuality } : {}),
  };
}

function createSamples(input: BuildCaptureContractInput): CaptureContractSample[] {
  const qmax = input.qmaxMlS ?? 0;
  const qavg = input.qavgMlS ?? 0;
  const flowTime = clamp(input.flowTimeS ?? 10, 3, 60);

  const stepS = DEFAULT_SAMPLE_STEP_S;
  const sampleCount = Math.max(8, Math.floor(flowTime / stepS) + 1);
  const inferredPeak = Math.max(6, qmax, qavg > 0 ? qavg * 1.35 : 0);

  let cumulativeVolumeMl = 0;
  const samples: CaptureContractSample[] = [];

  for (let index = 0; index < sampleCount; index += 1) {
    const progress = sampleCount > 1 ? index / (sampleCount - 1) : 0;
    const bell = Math.sin(Math.PI * progress);
    const flow = Math.max(0, inferredPeak * bell);

    cumulativeVolumeMl += flow * stepS;
    const depthLevel = cumulativeVolumeMl / DEFAULT_ML_PER_MM;

    const confidence = progress > 0.65 && progress < 0.75 ? 0.55 : 0.92;
    const motion = 0.02 + (index % 3) * 0.01;

    samples.push({
      t_s: round4(index * stepS),
      depth_level_mm: round4(depthLevel),
      rgb_level_mm: round4(depthLevel * 0.97),
      depth_confidence: round4(confidence),
      audio_rms_dbfs: round4(-45 + Math.min(18, flow * 0.75)),
      motion_norm: round4(motion),
      roi_valid: true,
    });
  }

  return samples;
}

function buildPrivacyNode(): CaptureContractPayload["session"]["privacy"] {
  return {
    store_raw_video: APP_PRIVACY_POLICY.storeRawVideo,
    store_raw_audio: APP_PRIVACY_POLICY.storeRawAudio,
    roi_only: APP_PRIVACY_POLICY.roiOnly,
  };
}

function buildFeatureManifest(
  source: string,
  samples: CaptureContractSample[],
  analysis: CaptureContractAnalysis | undefined,
): CaptureContractFeatureManifest {
  const featureKeys = new Set<string>(BASE_FEATURE_KEYS);
  if (analysis?.runtime_flow_series && analysis.runtime_flow_series.length > 0) {
    featureKeys.add("runtime_flow_series.flow_ml_s");
  }
  if (analysis?.runtime_timeline) {
    Object.keys(analysis.runtime_timeline).forEach((key) => {
      featureKeys.add(`runtime_timeline.${key}`);
    });
  }
  if (analysis?.runtime_alignment) {
    Object.keys(analysis.runtime_alignment).forEach((key) => {
      featureKeys.add(`runtime_alignment.${key}`);
    });
  }
  if (analysis?.runtime_quality) {
    Object.keys(analysis.runtime_quality).forEach((key) => {
      featureKeys.add(`runtime_quality.${key}`);
    });
  }

  return {
    version: FEATURE_MANIFEST_VERSION,
    source: source.trim() || "mobile_scaffold",
    derivatives_only: true,
    sample_count: samples.length,
    feature_keys: Array.from(featureKeys).sort(),
    raw_media: {
      store_raw_video: APP_PRIVACY_POLICY.storeRawVideo,
      store_raw_audio: APP_PRIVACY_POLICY.storeRawAudio,
      upload_raw_video: false,
      upload_raw_audio: false,
    },
    privacy: {
      roi_only: APP_PRIVACY_POLICY.roiOnly,
      media_scope: "roi_derivatives_only",
    },
  };
}

export function buildCaptureContractPayload(
  input: BuildCaptureContractInput,
): CaptureContractPayload {
  const model = input.deviceModel?.trim() || "unknown-device";
  const appVersion = input.appVersion?.trim() || APP_RELEASE_VERSION;
  const samples = createSamples(input);

  return {
    schema_version: APP_CAPTURE_SCHEMA_VERSION,
    session: {
      session_id: input.sessionId,
      sync_id: input.syncId,
      started_at: normalizeStartedAt(input.startedAtIso),
      mode: input.captureMode,
      device: {
        model,
        ios_version: input.iosVersion,
      },
      app: {
        version: appVersion,
      },
      calibration: {
        ml_per_mm: DEFAULT_ML_PER_MM,
        min_depth_confidence: 0.6,
        camera_distance_mm: 650,
      },
      privacy: buildPrivacyNode(),
    },
    feature_manifest: buildFeatureManifest("mobile_scaffold", samples, undefined),
    samples,
  };
}

export function buildCaptureContractPayloadFromSamples(
  input: BuildCaptureContractFromSamplesInput,
): CaptureContractPayload {
  const model = input.deviceModel?.trim() || "unknown-device";
  const appVersion = input.appVersion?.trim() || APP_RELEASE_VERSION;
  const source = input.sourceLabel?.trim();
  let safeSamples: CaptureContractSample[] = sanitizeRuntimeSamples(input.samples);
  if (safeSamples.length === 0) {
    safeSamples = [
      {
        t_s: 0,
        depth_level_mm: 0,
        rgb_level_mm: 0,
        depth_confidence: 0.8,
        audio_rms_dbfs: -55,
        motion_norm: 0.02,
        roi_valid: true,
      },
      {
        t_s: DEFAULT_SAMPLE_STEP_S,
        depth_level_mm: 0.2,
        rgb_level_mm: 0.18,
        depth_confidence: 0.8,
        audio_rms_dbfs: -52,
        motion_norm: 0.02,
        roi_valid: true,
      },
    ];
  } else if (safeSamples.length === 1) {
    safeSamples = [
      { ...safeSamples[0], t_s: 0 },
      {
        ...safeSamples[0],
        t_s: DEFAULT_SAMPLE_STEP_S,
      },
    ];
  }
  const analysis = sanitizeAnalysis(input.analysis, deriveRuntimeTimeline(safeSamples), safeSamples);

  const payload: CaptureContractPayload = {
    schema_version: APP_CAPTURE_SCHEMA_VERSION,
    session: {
      session_id: input.sessionId,
      sync_id: input.syncId,
      started_at: normalizeStartedAt(input.startedAtIso),
      mode: input.captureMode,
      device: {
        model: source ? `${model}-${source}` : model,
        ios_version: input.iosVersion,
      },
      app: {
        version: appVersion,
      },
      calibration: {
        ml_per_mm: DEFAULT_ML_PER_MM,
        min_depth_confidence: input.minDepthConfidence ?? 0.6,
        camera_distance_mm: input.cameraDistanceMm ?? 650,
      },
      privacy: buildPrivacyNode(),
    },
    feature_manifest: buildFeatureManifest(
      source || "runtime-audio-imu-camera-proxy",
      safeSamples,
      analysis,
    ),
    samples: safeSamples,
  };
  if (analysis) {
    payload.analysis = analysis;
  }
  return payload;
}
